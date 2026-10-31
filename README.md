## Partie 1 : coût d'une requête

**Question :** de quoi dépend le temps de traitement d'une timeline ?

#### Hypothèse

En lisant `get_timeline` dans `main.py`, je remarque que la fonction contient deux blocs `try`, donc deux méthodes pour construire la timeline.

**Méthode 1 : requête groupée.** Elle utilise une requête (de type SQL, ici une requête Datastore) qui sélectionne les posts dont l'auteur appartient à la liste de followees récupérée. Comme on sélectionne tous les posts de ces auteurs, plus P est grand, plus la requête va mettre du temps.

**Méthode 2 : boucle.** Elle parcourt chaque auteur de la liste `follows` pour récupérer les posts de chacun. Donc, si la liste est grande, le temps de réponse l'est aussi.

**Prédiction :** si P et F augmentent, le temps de réponse du serveur augmente. En revanche, U ne semble pas influer sur la fonction, car c'est un utilisateur qui est passé en paramètre.

| Facteur | Évolution attendue du temps serveur | Mécanisme (`get_timeline`) |
|---|---|---|
| U (utilisateurs) | Pas d'effet | L'utilisateur est passé en paramètre : la fonction ne travaille que sur sa liste de followees et sur leurs posts. |
| P (posts par utilisateur) | Augmente | La requête sélectionne les posts des auteurs de la liste : plus ils en ont, plus elle est longue. |
| F (followees) | Augmente | Plus la liste `follows` est grande, plus la requête est lourde (méthode 1) et plus il y a d'itérations dans la boucle (méthode 2). |

#### Protocole

**Montage.** Version `fixed1` on garanti ainsi exactement 1 instance, sans autoscaling, une requête à la fois (Locust `-u 1 -r 1`). Projet GCP `tinyinsta-510215`, région App Engine `europe-west6`. Client de charge : Locust 2.47.0, lancé depuis Cloud Shell. Mesures réalisées le 30/10/2026.

**Jeux de données.** Chaque jeu est généré avec `bench/seed_exact.py`. Un seul facteur varie à la fois, les autres restent à leur valeur de référence.

| Facteur étudié | Jeux utilisés | U | P | F |
|---|---|---|---|---|
| U | `u100`, `base`, `u10000` | 100 / 1 000 / 10 000 | 20 | 20 |
| P | `p10`, `u100`, `p100`, `p1000` | 100 | 10 / 20 / 100 / 1 000 | 20 |
| F | `f05`, `f10`, ..., `f100` (20 jeux) | 120 | 20 | 5 / 10 / ... / 100 |

**Déroulement.**
- 26 runs, un par jeu, de 60 secondes chacun. Chaque run produit un journal brut `raw/<jeu>.csv` (une ligne par requête : latence client, temps serveur, code HTTP, instance).
- Les runs sont lancés dans un **ordre mélangé** (tirage avec graine fixe, enregistré dans `raw/order.txt`), pour que l'ordre n'avantage ni ne pénalise un facteur plus qu'un autre.
- Chaque jeu n'est mesuré qu'une seule fois.

**Traitement.**
- Pour chaque run, on calcule la médiane du temps serveur (`SERVER_MS`, en-tête `Server-Timing`, durée de `get_timeline`) et la médiane de la latence client (`LATENCY_MS`, mesurée par Locust).
- Le nombre d'instances qui ont réellement répondu est compté à partir de la colonne `INSTANCE` (en-tête `X-Instance`) : il vaut 1 pour les 26 runs. Les 26 runs n'ont renvoyé que des codes 200.

**Reproductibilité.** `scripts/campagne_p1.sh` lance les mesures. `python3 scripts/analyse_p1.py` lit `raw/` et régénère tous les CSV et PNG de `figures/` ainsi que le résumé `figures/resume_p1.csv`.

#### Figures

![Fig. 1a](figures/fig1a.png)

**Fig. 1a** : temps serveur médian (ms) en fonction de U (à gauche, avec P = 20 et F = 20) et de P (à droite, avec U = 100 et F = 20), abscisses en échelle logarithmique. `fixed1`, une requête à la fois. Valeurs tracées : `figures/fig1a.csv`.

![Fig. 1b](figures/fig1b.png)

**Fig. 1b** : temps serveur médian et latence client médiane (ms) en fonction de F, pour 20 valeurs de F (U = 120, P = 20). `fixed1`, une requête à la fois. Valeurs tracées : `figures/fig1b.csv`.

Le résumé de tous les runs (nombre de requêtes, instances distinctes, codes HTTP, médianes) est dans `figures/resume_p1.csv`.
#### Interprétation et réponses aux questions

Dans `get_timeline`, il y a deux façons de récupérer les posts. J'appelle la première la **méthode IN** : une seule requête qui demande les posts de tous les auteurs d'un coup. J'appelle la deuxième la **méthode boucle** : une requête par auteur, l'une après l'autre.

Le code essaie d'abord la méthode IN. Si Datastore refuse, l'erreur est attrapée par le `except` et le code passe à la méthode boucle, sans afficher aucun message.

J'ai fait un test directement sur Datastore avec des `IN` de plus en plus grands. Avec 30 valeurs, ça marche. Avec 31 valeurs, Datastore répond « IN supports up to 30 values ». Une timeline demande les posts de F comptes suivis plus ceux de l'utilisateur, donc F + 1 auteurs. Jusqu'à F = 29, c'est la méthode IN qui répond. À partir de F = 30, c'est la méthode boucle.

##### Question 1 : mes hypothèses sont-elles confirmées ? Sinon, qu'avais-je manqué ?

**U : confirmé.** Je pensais que U n'avait pas d'effet, car l'utilisateur est donné en paramètre. Les mesures donnent 22,8 ms pour U = 100 et 26,0 ms pour U = 10 000. Le temps serveur ne monte que de 3 ms alors qu'il y a 100 fois plus d'utilisateurs.

**P : plutôt réfuté.** Je pensais que le temps augmentait avec P, car la requête parcourt tous les posts avant d'en renvoyer 20. Les mesures donnent 23,5 ms pour P = 10 et 29,1 ms pour P = 1 000. Le temps augmente d'environ 6 ms alors que P est multiplié par 100. Si la requête lisait tous les posts, le temps serait bien plus grand. Je n'avais pas vu le `limit=20` : la requête s'arrête dès qu'elle a 20 posts. Une explication probable (mais pas certaine) est que l'index `(author, created desc)` donne déjà les posts triés par date, donc Datastore lit directement les plus récents.
**F : plutôt confirmé.** Je pensais que le temps augmentait avec F à cause de la boucle. C'est vrai, mais seulement à partir de F = 30. Jusqu'à F = 25, le temps est presque plat (24,5 ms à F = 5 et 26,9 ms à F = 25). À F = 30, il saute à 420,9 ms. Ensuite il monte presque droit jusqu'à 1 318,8 ms à F = 100. Cela fait environ 13 ms par auteur (420,9 ms pour 31 auteurs et 1 318,8 ms pour 101 auteurs). De ce que je comprends chaque requête de la boucle est un aller-retour vers Datastore. Le code parcourt toute la liste des followees, pour chacun, il demande ses posts à Datastore (l’aller), puis il attend la réponse (le retour) avant d’interroger Datastore pour le suivant dans la liste.

**Ce que j'avais manqué :**
- La limite de 30 valeurs pour `IN`.
- Le passage automatique et silencieux à la boucle quand `IN` est refusé. C'est pour ça qu'il y a une marche à F = 30 et pas une pente douce.
- Le `limit=20` : il limite le travail de la méthode IN, et pas seulement l'affichage.

##### Question 2 : quelle part de la latence client est due au réseau ?

Sur la figure 1b, la latence client est toujours un peu plus grande que le temps serveur. On le voit facilement car la courbe orange est toujours supérieur a la bleu. La différence est d'environ 23 ms, quel que soit F (entre 22 et 26 ms selon les runs). Elle ne change pas quand le temps serveur monte, j'en déduis donc qu'elle ne dépend pas du travail fait dans Datastore.

La part en pourcentage, elle, change beaucoup avec F :

| F | Temps serveur (ms) | Latence client (ms) | Différence (ms) | Part de la latence client |
|---|---|---|---|---|
| 5 | 24,5 | 47,6 | 23,1 | environ 49 % |
| 25 | 26,85 | 50,15 | 23,3 | environ 46 % |
| 30 | 420,9 | 443,8 | 22,9 | environ 5 % |
| 100 | 1 318,8 | 1 341,8 | 23,0 | environ 1,7 % |

Quand la requête est rapide, presque la moitié de la latence ne vient pas du serveur. Quand elle est lente, ça devient presque rien.

Ces 23 ms ne sont pas seulement du réseau. Ils contiennent aussi la préparation du JSON et le passage par le serveur web d'App Engine, que le temps serveur ne compte pas. La vraie part du réseau est donc au plus de 23 ms. Je ne l'ai pas séparée du reste.

##### Question 3 : combien d'entités Datastore une timeline lit-elle ? Quel coût pour 1 million de timelines ?

Une entité est un objet stocké dans Datastore, ici un `User` ou un `Post`. Google facture chaque entité lue. Plus une timeline lit d'entités, plus elle coûte cher.

**Méthode IN (F de 5 à 29) : 21 entités.**
- Le code lit d'abord l'entité `User` pour récupérer la liste des comptes suivis. C'est **1 entité**.
- Ensuite, une seule requête demande les posts de tous les auteurs, avec `limit=20`. Datastore s'arrête à 20 résultats. C'est **20 entités** `Post`, même si les auteurs ont beaucoup plus de posts.
- Au total : 1 + 20 = **21 entités**.

**Méthode boucle (F à partir de 30) : beaucoup plus.(logique)**
- Il y a toujours **1 entité** `User`.
- Ensuite, le code fait une requête par auteur, et il y a F + 1 auteurs. Le `limit=20` s'applique à **chaque requête**, donc chaque auteur donne jusqu'à 20 posts.
- Au total : 1 + 20 × (F + 1) entités.
- Pour F = 30 : 31 auteurs × 20 = 620, plus 1 = **621 entités**.
- Pour F = 100 : 101 auteurs × 20 = 2 020, plus 1 = **2 021 entités**.
- À la fin, le code trie tous ces posts et n'en garde que 20. Tout le reste a été lu, payé, et jeté (quel gâchis).

**Selon U, P et F :**
- **U** ne change rien : 21 entités. On lit toujours un `User` et 20 posts.
- **P** ne change rien dans mes mesures : 21 entités. Pour les jeux de P, F vaut 20, donc c'est la méthode IN. Même avec P = 10, les 21 auteurs ont 210 posts en tout, donc la requête en trouve toujours 20.
- **F** change tout : 21 entités jusqu'à F = 29, puis 621 à F = 30 et 2 021 à F = 100.

**Le prix.** Pour Zurich (europe-west6), en mode Datastore, une lecture d'entité coûte **0,042 $ pour 100 000 lectures**. Je l'ai lu sur la page de tarification de Google le 31/10/2026. Les 50 000 premières lectures par jour sont gratuites, mais je ne les compte pas.

**Le calcul pour 1 million de timelines :**
1. On multiplie le nombre d'entités par 1 000 000 pour avoir le nombre de lectures.
2. On divise par 100 000 pour savoir combien de paquets de 100 000 on paye.
3. On multiplie par 0,042 $.

Exemple pour 21 entités : 21 × 1 000 000 = 21 000 000 lectures, soit 210 paquets, soit 210 × 0,042 = 8,82 $.

Autrement dit, chaque entité lue par timeline coûte 0,42 $ pour 1 million de timelines.

| Cas | Méthode | Entités lues par timeline | Lectures pour 1 million de timelines | Coût de 1 million de timelines |
|---|---|---|---|---|
| U de 100 à 10 000 (P = 20, F = 20) | IN | 21 | 21 000 000 | 8,82 $ |
| P de 10 à 1 000 (U = 100, F = 20) | IN | 21 | 21 000 000 | 8,82 $ |
| F de 5 à 25 | IN | 21 | 21 000 000 | 8,82 $ |
| F = 30 | boucle | 621 | 621 000 000 | 260,82 $ |
| F = 100 | boucle | 2 021 | 2 021 000 000 | 848,82 $ |

Quand F passe de 25 à 30, le coût est multiplié par environ 30 (de 8,82 $ à 260,82 $). À F = 100, il est environ 96 fois plus élevé qu'à F = 25.

**Limites.** Ces nombres d'entités sont déduits du code. Je ne les ai pas mesurés dans la facturation réelle. Ils ne comptent pas non plus les éventuelles lectures d'entrées 
