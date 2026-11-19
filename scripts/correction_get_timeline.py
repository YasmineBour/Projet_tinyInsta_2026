#!/usr/bin/env python3
"""Partie 3 : remplace get_timeline dans main.py par la version corrigee
(requetes IN par groupes de 30 auteurs au plus, au lieu d'une requete par auteur).
Usage (racine du depot) : python3 scripts/appliquer_correctif_p3.py
Le script affiche les differences. Pour annuler : git checkout main.py
"""
import difflib
import sys

SRC = "main.py"

NOUVEAU = '''MAX_IN = 30  # Datastore refuse un filtre IN de plus de 30 valeurs


def _groupes(liste, taille):
    """Decoupe une liste en morceaux de `taille` elements au plus."""
    for i in range(0, len(liste), taille):
        yield liste[i:i + taille]


def get_timeline(user: str, limit: int = 20):
    """Retourne la liste des posts (entites) pour la timeline d'un utilisateur.

    Correction (partie 3) : les auteurs sont envoyes a Datastore par groupes de
    30 au plus (une requete IN par groupe), au lieu d'une requete par auteur
    quand il y a plus de 30 auteurs.
    """
    if not user:
        return []
    follow_key = client.key('User', user)
    user_entity = client.get(follow_key)
    follows = []
    if user_entity:
        follows = user_entity.get('follows', [])
    follows = list({*follows, user})

    posts = []
    for groupe in _groupes(follows, MAX_IN):
        query = client.query(kind='Post')
        query.add_filter('author', 'IN', groupe)
        query.order = ['-created']
        posts.extend(list(query.fetch(limit=limit)))
    # Les `limit` posts les plus recents de l'ensemble font partie des `limit`
    # plus recents de leur groupe : on trie l'ensemble puis on garde `limit` posts.
    return sorted(posts, key=lambda p: p.get('created'), reverse=True)[:limit]
'''

s = open(SRC, encoding="utf-8").read()
if "MAX_IN" in s:
    sys.exit("Correctif deja applique (MAX_IN existe dans main.py).")
a = s.find("def get_timeline(")
b = s.find("def seed_data(")
if a < 0 or b < 0 or b < a:
    sys.exit("Reperes introuvables : 'def get_timeline(' puis 'def seed_data(' attendus dans main.py.")
nouveau_fichier = s[:a] + NOUVEAU.rstrip("\n") + "\n\n\n" + s[b:]
compile(nouveau_fichier, SRC, "exec")          # verifie que le Python reste valide
for ligne in difflib.unified_diff(s.splitlines(), nouveau_fichier.splitlines(), "main.py (avant)", "main.py (apres)", lineterm=""):
    print(ligne)
open(SRC, "w", encoding="utf-8").write(nouveau_fichier)
print("\nmain.py modifie.")
