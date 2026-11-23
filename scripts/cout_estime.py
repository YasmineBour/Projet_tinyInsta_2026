#!/usr/bin/env python3
"""Estime les lectures et les ecritures Datastore de la campagne a partir des journaux bruts.
Usage (racine du depot) : python3 scripts/cout_estime.py   ->   ecrit aussi figures/cout_estime.csv

HYPOTHESES (a recopier dans le README) :
 - Chaque requete HTTP 200 d'une timeline lit 21 entites si F + 1 <= 30 (1 User + 20 Post, methode IN),
   1 + 20 * (F + 1) entites avec l'ancienne boucle (F >= 30, P = 20), et 1 + 20 * ceil((F + 1) / 30)
   avec la version corrigee. Valeurs DEDUITES DU CODE, pas mesurees.
 - Les echauffements, les runs de test et les tentatives ratees ne sont pas comptes : les lectures reelles
   sont donc un peu plus elevees.
 - Ecritures : chaque entite User et Post des 26 jeux est ecrite une fois (seeds uniques).
 - Les quotas gratuits (50 000 lectures et 20 000 ecritures par jour) ne sont pas deduits.
 - Prix de Zurich (europe-west6), mode Datastore : 0,042 $ / 100 000 lectures, 0,126 $ / 100 000 ecritures.
"""
import glob
import math
import os
import re
import pandas as pd

PRIX_LECTURE, PRIX_ECRITURE = 0.042 / 100_000, 0.126 / 100_000


def lectures_ancien(F):
    return 21 if F + 1 <= 30 else 1 + 20 * (F + 1)


def lectures_corrige(F):
    return 1 + 20 * math.ceil((F + 1) / 30)


def n200(path):
    d = pd.read_csv(path)
    return int((d.STATUS == 200).sum())


rows = []
# Partie 1 : raw/<jeu>.csv
for jeu in ["u100", "base", "u10000", "p10", "p100", "p1000"] + [f"f{f:02d}" for f in range(5, 105, 5)]:
    path = f"raw/{jeu}.csv"
    if not os.path.exists(path):
        continue
    F = int(jeu[1:]) if jeu.startswith("f") else 20
    n = n200(path)
    rows.append(dict(partie=1, run=jeu, requetes_200=n, entites_par_timeline=lectures_ancien(F)))
# Partie 2 : raw/p2_N<N>_C<C>.csv (jeu base, F = 20)
for path in sorted(glob.glob("raw/p2_N*_C*.csv")):
    m = re.search(r"p2_N(\d+)_C(\d+)\.csv$", path)
    rows.append(dict(partie=2, run=f"N{m.group(1)}_C{m.group(2)}", requetes_200=n200(path), entites_par_timeline=21))
# Partie 3 : raw/p3_f<F>.csv (journaux valides seulement, pas les ECHEC)
for path in sorted(glob.glob("raw/p3_f[0-9][0-9].csv")) + sorted(glob.glob("raw/p3_f100.csv")):
    F = int(re.search(r"p3_f(\d+)\.csv$", path).group(1))
    rows.append(dict(partie=3, run=f"f{F:02d}", requetes_200=n200(path), entites_par_timeline=lectures_corrige(F)))

d = pd.DataFrame(rows)
d["lectures"] = d.requetes_200 * d.entites_par_timeline
d.to_csv("figures/cout_estime.csv", index=False)

# Ecritures : seeds (U utilisateurs + U x P posts par jeu)
jeux = {"base": (1000, 20), "u100": (100, 20), "u10000": (10000, 20), "p10": (100, 10), "p100": (100, 100), "p1000": (100, 1000)}
jeux.update({f"f{f:02d}": (120, 20) for f in range(5, 105, 5)})
ecritures = sum(U + U * P for U, P in jeux.values())

print("Lectures estimees par partie :")
par_partie = d.groupby("partie").agg(requetes_200=("requetes_200", "sum"), lectures=("lectures", "sum"))
par_partie["cout_usd_sans_quota_gratuit"] = (par_partie.lectures * PRIX_LECTURE).round(2)
print(par_partie.to_string())
tot = int(d.lectures.sum())
print(f"\nTotal lectures (au moins) : {tot:,}  ->  {tot * PRIX_LECTURE:.2f} $".replace(",", " "))
print(f"Ecritures (generation des 26 jeux) : {ecritures:,}  ->  {ecritures * PRIX_ECRITURE:.2f} $".replace(",", " "))
print(f"Total estime sans les heures d'instance : {tot * PRIX_LECTURE + ecritures * PRIX_ECRITURE:.2f} $")
