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

<!-- À compléter : fixed1, une requête à la fois (-u 1), durée des runs, 5 premières secondes écartées, ordre aléatoire des runs (raw/order.txt). -->

#### Figures

<!-- À compléter : figures/fig1a.png et figures/fig1b.png, avec les paramètres fixés dans chaque légende. -->

#### Interprétation

<!-- À compléter : hypothèse confirmée ou réfutée, ce que j'avais manqué, part du réseau, entités lues et coût de 1 million de timelines. -->

