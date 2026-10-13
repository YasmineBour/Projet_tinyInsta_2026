# Outils de mesure (Cloud Shell)

Ce dossier contient les outils du projet : le générateur de données (`seed_exact.py`) et le générateur de charge (`locustfile.py`, pour [Locust](https://locust.io)). Toutes les commandes ci-dessous se lancent dans **Cloud Shell**, depuis la racine du dépôt.

## 1. Installation

```sh
git clone https://gitlab.univ-nantes.fr/molli-p/tinyinsta-2026.git
cd tinyinsta-2026
pip install -r bench/requirements.txt
P=<VOTRE_PROJET>            # identifiant de votre projet GCP
gcloud config set project $P
```

La variable `P` est utilisée dans toutes les commandes suivantes. Si vous ouvrez un nouvel onglet Cloud Shell, redéfinissez-la.

## 2. Créer l'application App Engine et l'index

À faire une seule fois par projet. Commencez par associer un compte de facturation au projet : sans lui, `gcloud app deploy` échoue (*The project must have a billing account attached*). Utilisez le compte de vos crédits éducation, qui apparaît une fois le coupon utilisé.

```sh
gcloud billing accounts list                                   # repérez un compte ouvert (OPEN = True)
gcloud billing projects link $P --billing-account=<ID_DU_COMPTE>
gcloud billing projects describe $P --format='value(billingEnabled)'   # doit afficher True
```

Créez ensuite l'application, déployez-la et créez l'index :

```sh
gcloud app create --region=europe-west                 # la région ne pourra plus être changée ensuite
gcloud app deploy app.yaml                             # version par défaut de l'application
gcloud datastore indexes create index.yaml --quiet     # index composite Post(author, created desc)
gcloud datastore indexes list                          # attendez que l'index soit READY (quelques minutes)
```

Vérifiez que l'application répond, avec l'index en place :

```sh
APP=$(gcloud app browse --no-launch-browser)
curl -s "$APP/api/timeline?user=test"                 # doit renvoyer du JSON ({"count":0,...}), pas une erreur 500
```

Tant que l'index n'est pas prêt, les timelines échouent (erreur 500).

## 3. Peupler le store

Un jeu de données est identifié par un **préfixe**. Il contient `U` utilisateurs (`<préfixe>_u00000` … `<préfixe>_u<U-1>`). Chacun a **exactement** `P` posts et suit **exactement** `F` autres utilisateurs du même jeu.

```sh
python bench/seed_exact.py --project $P --prefix base --users 1000 --posts-per-user 20 --followees 20
```

Les jeux du sujet (environ 400 000 entités, quelques minutes) :

```sh
python bench/seed_exact.py --project $P --prefix base   --users 1000  --posts-per-user 20 --followees 20
python bench/seed_exact.py --project $P --prefix u100   --users 100   --posts-per-user 20 --followees 20
python bench/seed_exact.py --project $P --prefix u10000 --users 10000 --posts-per-user 20 --followees 20
for p in 10 100 1000; do
  python bench/seed_exact.py --project $P --prefix p$p --users 100 --posts-per-user $p --followees 20
done
for f in $(seq 5 5 100); do
  python bench/seed_exact.py --project $P --prefix $(printf 'f%02d' $f) --users 120 --posts-per-user 20 --followees $f
done
```

Options utiles :

- `--dry-run` : affiche ce qui serait écrit, sans rien écrire.
- `--purge` : supprime tout le jeu d'un préfixe (`python bench/seed_exact.py --project $P --prefix base --purge`).

**Ne relancez pas un préfixe déjà généré** : les nouveaux posts s'ajouteraient aux anciens. Purgez-le d'abord.

## 4. Déployer une version à instances fixes

```sh
./deploy_fixed.sh 1                       # version fixed1 : exactement 1 instance, sans autoscaling
URL=$(gcloud app versions describe fixed1 --service default --format='value(versionUrl)')
echo $URL
```

Vérifiez que l'URL vise bien la bonne version : la réponse doit contenir les en-têtes `X-Instance` et `Server-Timing`.

```sh
curl -sI "$URL/api/timeline?user=base_u00001" | grep -iE "x-instance|server-timing"
```

**Une version à instances fixes est facturée tant qu'elle tourne.** Arrêtez-la dès la fin de ses mesures, et redémarrez-la quand vous en avez besoin :

```sh
gcloud app versions stop fixed1
gcloud app versions start fixed1
```

## 5. Lancer une mesure avec Locust

Une commande correspond à un run : `C` utilisateurs Locust simultanés, pendant une durée fixe. Chaque utilisateur Locust interroge en boucle la timeline d'un utilisateur TinyInsta qui lui est propre : il envoie une nouvelle requête dès qu'il reçoit la réponse précédente.

```sh
TINY_PREFIX=base TINY_USERS=1000 TINY_LOG=raw/run1.csv \
  locust -f bench/locustfile.py --headless -u 16 -r 16 -t 45s --only-summary --host $URL
```

| Paramètre | Rôle |
|---|---|
| `TINY_PREFIX` | Préfixe du jeu de données interrogé |
| `TINY_USERS` | Nombre d'utilisateurs de ce jeu (le `--users` utilisé pour le générer) |
| `TINY_LOG` | Fichier CSV de sortie (le dossier est créé si besoin) |
| `TINY_LIMIT` | Taille de la timeline (20 par défaut) |
| `-u` / `-r` | Nombre d'utilisateurs simultanés, et nombre démarrés par seconde (mettez la même valeur) |
| `-t` | Durée du run (`40s`, `2m`…) |
| `--host` | URL de la version mesurée |

Le fichier `TINY_LOG` contient **une ligne par requête** :

| Colonne | Contenu |
|---|---|
| `T_START` | Instant d'envoi de la requête (secondes depuis 1970) |
| `LATENCY_MS` | Latence mesurée par le client (ms) |
| `STATUS` | Code HTTP (`0` si la requête n'a pas abouti) |
| `INSTANCE` | Instance App Engine qui a répondu (en-tête `X-Instance`) |
| `SERVER_MS` | Temps passé côté serveur dans `get_timeline` (en-tête `Server-Timing`, ms) |
| `ERROR` | Type d'erreur réseau éventuelle |
| `USERS` | Nombre d'utilisateurs Locust actifs à cet instant |

C'est à vous de calculer, à partir de ces fichiers, les indicateurs demandés par le sujet : médianes, débit, nombre d'instances actives, échecs…

## 6. Dépannage

- **Erreur d'authentification avec `seed_exact.py`** : lancez `gcloud auth application-default login`, puis recommencez.
- **Commande `locust` introuvable** : utilisez `python -m locust` à la place de `locust`.
- **Pas d'en-tête `X-Instance` dans la réponse** : vous interrogez sans doute une version qui n'existe pas. App Engine renvoie alors silencieusement la version par défaut. Vérifiez le nom de la version et `$URL`.
- **Longues séries de mesures** : Cloud Shell coupe une session inactive au bout d'environ une heure, et ce qui tourne dans le terminal s'arrête avec elle. Lancez vos séries dans `tmux`, gardez l'onglet ouvert, et découpez-les pour pouvoir reprendre. Vos fichiers dans `$HOME` sont conservés.
