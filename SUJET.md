# PROJET DONNÉES MASSIVES ET CLOUD

**TinyInsta passe-t-elle à l’échelle ? — Benchmark, édition 2026**

Dernière mise à jour : 13/10/2026 · Rendu **individuel** · Date limite : **27 novembre 2026**

## 1. Objectif

TinyInsta (https://gitlab.univ-nantes.fr/molli-p/tinyinsta-2026) est un réseau social minimaliste déployé sur Google App Engine (PaaS), avec Google Cloud Datastore (Firestore en mode Datastore) pour le stockage. Un utilisateur poste des messages et suit d’autres utilisateurs. Sa *timeline* est la liste des 20 messages les plus récents des comptes qu’il suit et des siens (`GET /api/timeline?user=…`).

> **Question du projet : TinyInsta passe-t-elle à l’échelle ? Si la réponse est nuancée : qu’est-ce qui passe à l’échelle, jusqu’où, et pourquoi ?**

Vous devez répondre à cette question par des expériences rigoureuses et reproductibles, puis expliquer chaque résultat par le code de l’application ou par le fonctionnement de la plateforme. Ce qui est évalué n’est pas d’obtenir « les bons chiffres », mais de **démontrer** vos conclusions.

Dans ce projet, « passer à l’échelle » a deux sens précis :

- **Données** : quand un paramètre des données est multiplié par 10, le temps de traitement d’une requête reste à peu près constant.
- **Ressources** : quand le nombre d’instances est multiplié par k, le débit maximal (requêtes servies par seconde) est multiplié par environ k.

Les données sont décrites par trois paramètres :

| Paramètre | Signification | Valeur de référence |
|---|---|---|
| **U** | Nombre d’utilisateurs du jeu de données | 1000 |
| **P** | Nombre **exact** de posts de chaque utilisateur | 20 |
| **F** | Nombre **exact** de comptes suivis (*followees*) par chaque utilisateur | 20 |

## 2. Mise en place

1. Utilisez votre projet GCP personnel et Cloud Shell. **Créez une alerte budgétaire à 20 $** (Facturation › Budgets et alertes).
2. Clonez le dépôt et installez les outils de mesure : `pip install -r bench/requirements.txt`.
3. Déployez l’application en suivant le README du dépôt. Vérifiez qu’une timeline répond avant d’aller plus loin.
4. Générez les jeux de données ci-dessous avec `bench/seed_exact.py` (exemple : `python bench/seed_exact.py --prefix base --users 1000 --posts-per-user 20 --followees 20`). Chaque jeu a son propre préfixe ; relancer un préfixe *ajoute* des posts, donc purgez-le d’abord (`--purge`).

| Jeu (préfixe) | U | P | F | Utilisé dans |
|---|---|---|---|---|
| `base` | 1000 | 20 | 20 | Parties 1 (référence), 2, 3 |
| `u100`, `u10000` | 100 / 10 000 | 20 | 20 | Partie 1, facteur U |
| `p10`, `p100`, `p1000` | 100 | 10 / 100 / 1000 | 20 | Partie 1, facteur P |
| `f05`, `f10`, …, `f100` | 120 | 20 | 5, 10, 15, …, 100 (20 jeux) | Partie 1, facteur F |

Au total, environ 400 000 entités : quelques minutes depuis Cloud Shell, pour moins de 1 $.

## 3. Outils fournis

Le dépôt fournit les outils suivants ; leur usage détaillé est dans le README.

| Outil | Rôle |
|---|---|
| En-têtes de `/api/timeline` | `X-Instance` : instance App Engine qui a servi la requête. `Server-Timing: timeline;dur=…` : temps passé côté serveur (ms). |
| `app.yaml` | Déploiement par défaut de l’application (autoscaling, au plus 10 instances). |
| `./deploy_fixed.sh N` | Déploie la version `fixedN` avec exactement N instances, sans autoscaling (parties 1 et 2). **Facturée tant qu’elle tourne** : `gcloud app versions stop fixedN` après usage. |
| `bench/seed_exact.py` | Génère ou purge un jeu de données exact (U, P, F). |
| `bench/locustfile.py` | Charge constante avec Locust, en boucle fermée, un utilisateur TinyInsta distinct par utilisateur Locust. Écrit une ligne par requête. |

N’utilisez pas `ab` (apache-bench) : il interroge une seule URL, donc un seul utilisateur, et ne compte pas les réponses HTTP 5xx comme des échecs.

## 4. Charte expérimentale (obligatoire)

Toutes vos mesures doivent respecter les règles suivantes.

1. **Énoncer une hypothèse pour chaque expérience.** Dans le rapport, chaque partie commence par l’hypothèse testée et le mécanisme attendu, argumentés à partir du code (`main.py`) et du fonctionnement de la plateforme. Les résultats sont ensuite confrontés à cette hypothèse. Une hypothèse réfutée et bien expliquée vaut autant qu’une hypothèse confirmée.
2. **Un seul facteur varie à la fois.** Chaque figure indique les valeurs de tous les paramètres fixés.
3. **Mesurer l’état de la plateforme, ne pas le supposer.** Pour chaque mesure, rapportez le nombre d’instances qui ont **réellement servi** des requêtes (en-tête `X-Instance`), et non le nombre d’instances listées par `gcloud`.
4. **Tout est reproductible.** Les journaux bruts sont dans le dépôt, et une seule commande régénère toutes les figures à partir des données.

## 5. Partie 1 — Coût d’une requête

> **Question : de quoi dépend le temps de traitement d’une timeline ?**

**Hypothèse.** Pour chacun des facteurs U, P et F, indiquez comment le temps serveur d’une timeline devrait évoluer, et pourquoi (lisez `get_timeline` dans `main.py`).

**Protocole imposé.**

- Version `fixed1` (1 instance fixe), **1 requête à la fois** (`-u 1`). Cette configuration élimine l’effet de l’autoscaling et de la concurrence.
- Facteur U ∈ {100, 1000, 10 000} ; facteur P ∈ {10, 100, 1000} ; facteur F ∈ {5, 10, 15, …, 100} (20 valeurs). Les autres paramètres restent à leur valeur de référence (jeux de la section 2).
- Mesurez la latence côté client **et** le temps côté serveur (`Server-Timing`).

**Figures.** *Fig. 1a* : temps serveur médian en fonction de U et de P. *Fig. 1b* : temps serveur médian et latence client médiane en fonction de F (20 valeurs).

**Questions.**

- Vos hypothèses sont-elles confirmées ? Sinon, qu’aviez-vous manqué ?
- Quelle part de la latence client est due au réseau ?
- Combien d’entités Datastore une timeline lit-elle, selon U, P et F ? Déduisez-en le coût de 1 million de timelines dans chaque cas (grille tarifaire de Datastore).

## 6. Partie 2 — Capacité

> **Question : combien de timelines par seconde une instance peut-elle servir ? Le débit maximal est-il proportionnel au nombre d’instances ?**

**Protocole imposé.**

- Versions `fixed1`, `fixed2` et `fixed4` (N = 1, 2, 4 instances fixes), jeu `base`.
- Concurrence C ∈ {1, 2, 4, 8, 16, 32, 64} (nombre d’utilisateurs Locust simultanés).
- Pour limiter le coût, déployez une version à la fois, faites toutes ses mesures, puis arrêtez-la avant de passer à la suivante.
- Vérifiez pour chaque mesure que le nombre d’instances actives vaut bien N.
- On suppose que le client de charge (Locust) n’est pas un goulot.

**Figures.** *Fig. 2a* : débit en fonction de C, une courbe par valeur de N. *Fig. 2b* : latence médiane en fonction de C, avec la prédiction de la loi de Little (latence ≈ C / débit).

**Questions.**

- Où se situe le point de saturation pour chaque N ? Quelle est la capacité d’une instance, et qu’est-ce qui la limite ? (Indice : comment l’application est-elle lancée ?)
- La loi de Little est-elle vérifiée au-delà de la saturation ?
- Passer de 1 à 4 instances multiplie-t-il le débit maximal par 4 ? Sinon, où est le goulot ?

## 7. Partie 3 — Corriger et re-mesurer

Choisissez un des goulots identifiés dans les parties 1 et 2. Proposez une modification du code ou de la configuration qui le lève, déployez-la dans une version à part (`--no-promote`), puis ré-exécutez **exactement le même protocole** que la mesure d’origine.

**Figure.** *Fig. 3* : avant et après, sur la même figure. Expliquez le gain obtenu, ou son absence, et ce que la correction coûte (complexité, argent, cohérence des données).

## 8. Rendu

Vous déposez sur Madoc deux URL : celle de votre dépôt GitHub ou GitLab, et celle de votre application déployée (version par défaut, qui doit rester fonctionnelle jusqu’à la fin de la correction). Le dépôt contient :

- `README.md` : votre rapport, avec les sections imposées ci-dessous ;
- pour chaque figure, le fichier CSV des valeurs tracées (`figures/fig1a.csv`, …), avec un en-tête explicite et les unités dans les noms de colonnes ;
- le dossier `raw/` avec tous les journaux bruts produits par `bench/locustfile.py` (compressés si nécessaire) ;
- `figures/fig1a.png` … `figures/fig3.png`, affichées dans le README ;
- vos scripts : orchestration des mesures (Snakemake conseillé) et génération des figures en une commande.

**Sections imposées du README** : 1. Montage (projet, région, versions, dates, d’où tourne le client) ; 2. Résultats des parties 1 à 3 (pour chacune : hypothèse, figures, interprétation) ; 3. Tableau des verdicts ; 4. Validité ; 5. Coût de la campagne.

**Tableau des verdicts** (à remplir dans le README) :

| Dimension | Passe à l’échelle ? | Jusqu’où ? | Pourquoi (mécanisme) | Preuve |
|---|---|---|---|---|
| Utilisateurs (U) |   |   |   | Fig. … |
| Posts par utilisateur (P) |   |   |   | Fig. … |
| Followees (F) |   |   |   | Fig. … |
| Instances (N) |   |   |   | Fig. … |

**Questions de validité** (une réponse argumentée pour chacune, dans la section 4 du README) :

1. Combien d’instances ont réellement servi chacune de vos mesures ? Est-ce celles que vous attendiez ?
2. Vos runs sont-ils indépendants ? L’ordre dans lequel vous avez enchaîné les mesures influence-t-il les résultats ?
3. Quelle part de la latence est due au réseau ?
4. Qu’avez-vous compté comme un échec ? Quels codes HTTP avez-vous observés ?
5. Avez-vous vérifié que votre mesure exerce bien le chemin de code que vous croyez ?
6. Combien votre campagne a-t-elle coûté (lectures, écritures, heures d’instance) ?

## 9. Budget et garde-fous

- **Arrêtez chaque version** `fixedN` **dès la fin de ses mesures** (`gcloud app versions stop fixedN`) : en manual scaling, une instance est facturée en continu.
- Ne dépassez pas 64 utilisateurs simultanés ni 4 instances fixes.
- Les timelines à F élevé lisent beaucoup d’entités : ne relancez pas ces mesures sans raison.
- Estimation, d’après un run pilote : moins de 1 $ pour les données et 2 à 5 $ pour l’ensemble des mesures. Surveillez la page Facturation.
- À la fin du projet, supprimez les versions inutiles et purgez les jeux de données.

Bon courage !
