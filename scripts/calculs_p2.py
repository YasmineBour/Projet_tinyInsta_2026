#!/usr/bin/env python3
"""Partie 2 : calculs d aide a l analyse, a partir de figures/resume_p2.csv.
Usage (depuis la racine du depot) : python3 scripts/calculs_p2.py"""
import pandas as pd
pd.set_option("display.width", 200)
r = pd.read_csv("figures/resume_p2.csv")
r["n_echecs"] = r.codes_http.str.extract(r"(?<!\d)0: (\d+)")[0].fillna(0).astype(int)

print("A. Capacité par N (débit en req/s)")
rows = []
for N, g in r.groupby("N_instances"):
    g = g.sort_values("C_utilisateurs_locust")
    dmax, dfin = g.debit_req_par_s.max(), g.debit_req_par_s.tail(2).mean()
    rows.append(dict(N=N, debit_max=round(dmax, 1), moyenne_C32_C64=round(dfin, 1),
                     max_par_instance=round(dmax / N, 1), fin_par_instance=round(dfin / N, 1)))
a = pd.DataFrame(rows)
a["rapport_max"] = (a.debit_max / a.debit_max.iloc[0]).round(2)
a["rapport_fin"] = (a.moyenne_C32_C64 / a.moyenne_C32_C64.iloc[0]).round(2)
print(a.to_string(index=False))

print("\nB. Temps d'occupation d'une instance (1 / débit par instance) et temps serveur médian")
b = r[r.C_utilisateurs_locust == 64].copy()
b["occupation_ms_par_requete"] = (1000 * b.N_instances / b.debit_req_par_s).round(1)
print(b[["N_instances", "debit_req_par_s", "occupation_ms_par_requete", "temps_serveur_median_ms"]].to_string(index=False))

print("\nC. Loi de Little : écart entre C/débit et la latence moyenne, selon le nombre d'échecs")
r["ecart_little_vs_moyenne_pct"] = ((r.latence_little_ms - r.latence_moyenne_ms) / r.latence_moyenne_ms * 100).round(1)
print(r[["N_instances", "C_utilisateurs_locust", "n_echecs", "ecart_little_vs_moyenne_pct"]].to_string(index=False))

print("\nD. Répartition entre instances : part de la plus chargée, comparée à 1/N")
d = r[["N_instances", "C_utilisateurs_locust", "part_max_une_instance"]].copy()
d["ideal_1_sur_N"] = (1 / d.N_instances).round(3)
print(d[d.N_instances > 1].to_string(index=False))
