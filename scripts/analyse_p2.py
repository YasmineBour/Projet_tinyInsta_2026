#!/usr/bin/env python3
"""Partie 2 : lit raw/p2_N<N>_C<C>.csv et ecrit
   figures/fig2a.csv/.png, figures/fig2b.csv/.png, figures/resume_p2.csv, figures/capacite_p2.csv.
   Une seule commande : python3 scripts/analyse_p2.py
"""
import glob
import os
import re
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WARMUP_S = 5                 # secondes ecartees au debut de chaque run
SEUIL_SATURATION = 0.90      # saturation : premier C qui atteint 90 % du debit maximal
HYP_DEBIT_PAR_INSTANCE = 40  # hypothese ecrite avant les mesures (req/s par instance)

os.makedirs("figures", exist_ok=True)
rows = []
for path in sorted(glob.glob("raw/p2_N*_C*.csv")):
    m = re.search(r"p2_N(\d+)_C(\d+)\.csv$", path)
    N, C = int(m.group(1)), int(m.group(2))
    d = pd.read_csv(path)
    t0 = d.T_START.min()
    kept = d[(d.T_START - t0) >= WARMUP_S]
    ok = kept[kept.STATUS == 200]
    if len(ok) < 2:
        print("Trop peu de requetes dans", path)
        continue
    fin = (ok.T_START + ok.LATENCY_MS / 1000).max()
    debut = ok.T_START.min()
    debit = len(ok) / (fin - debut)                     # requetes servies par seconde
    par_instance = ok.INSTANCE.value_counts(normalize=True)
    rows.append(dict(
        N_instances=N, C_utilisateurs_locust=C,
        n_requetes_total=len(d), n_requetes_gardees=len(kept), n_http200=len(ok),
        codes_http=str(d.STATUS.value_counts().to_dict()),
        instances_distinctes=d.INSTANCE.nunique(),
        part_max_une_instance=round(par_instance.max(), 3),
        debit_req_par_s=round(debit, 2),
        latence_mediane_ms=ok.LATENCY_MS.median(),
        latence_moyenne_ms=round(ok.LATENCY_MS.mean(), 2),
        latence_little_ms=round(C / debit * 1000, 2),     # C / debit
        temps_serveur_median_ms=ok.SERVER_MS.median(),
    ))

if not rows:
    raise SystemExit("Aucun fichier raw/p2_N*_C*.csv trouve.")

res = pd.DataFrame(rows).sort_values(["N_instances", "C_utilisateurs_locust"])
res.to_csv("figures/resume_p2.csv", index=False)
print(res[["N_instances", "C_utilisateurs_locust", "n_http200", "codes_http", "instances_distinctes",
           "part_max_une_instance", "debit_req_par_s", "latence_mediane_ms",
           "latence_little_ms", "temps_serveur_median_ms"]].to_string(index=False))

# ---------- capacite par N ----------
cap = []
for N, g in res.groupby("N_instances"):
    dmax = g.debit_req_par_s.max()
    csat = g[g.debit_req_par_s >= SEUIL_SATURATION * dmax].C_utilisateurs_locust.min()
    cap.append(dict(N_instances=N, debit_max_req_par_s=dmax, debit_max_par_instance_req_par_s=round(dmax / N, 2),
                    C_saturation=csat))
cap = pd.DataFrame(cap)
base = cap.loc[cap.N_instances == cap.N_instances.min(), "debit_max_req_par_s"].iloc[0]
cap["rapport_au_plus_petit_N"] = (cap.debit_max_req_par_s / base).round(2)
cap.to_csv("figures/capacite_p2.csv", index=False)
print("\nCapacite :")
print(cap.to_string(index=False))

# ---------- Fig 2a : debit vs C, une courbe par N ----------
res[["N_instances", "C_utilisateurs_locust", "debit_req_par_s", "n_http200", "instances_distinctes"]].rename(
    columns={"n_http200": "n_requetes_http200"}).to_csv("figures/fig2a.csv", index=False)

couleurs = {1: "tab:blue", 2: "tab:orange", 4: "tab:green"}
fig, ax = plt.subplots(figsize=(7, 4.5))
for N, g in res.groupby("N_instances"):
    c = couleurs.get(N)
    ax.plot(g.C_utilisateurs_locust, g.debit_req_par_s, "o-", color=c, label=f"N = {N} (mesure)")
    ax.axhline(HYP_DEBIT_PAR_INSTANCE * N, color=c, ls=":", lw=1,
               label=f"N = {N} (hypothese : {HYP_DEBIT_PAR_INSTANCE * N} req/s)")
ax.set_xscale("log", base=2)
ax.set_xticks(sorted(res.C_utilisateurs_locust.unique()))
ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.set_xlabel("C (utilisateurs Locust simultanes)")
ax.set_ylabel("Debit (requetes servies par seconde)")
ax.set_title("Fig. 2a - debit en fonction de C (jeu base, versions fixedN)")
ax.grid(alpha=.3); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig("figures/fig2a.png", dpi=150)

# ---------- Fig 2b : latence mediane vs C, avec la loi de Little ----------
res[["N_instances", "C_utilisateurs_locust", "latence_mediane_ms", "latence_moyenne_ms",
     "latence_little_ms", "temps_serveur_median_ms"]].to_csv("figures/fig2b.csv", index=False)

Ns = sorted(res.N_instances.unique())
fig, axes = plt.subplots(1, len(Ns), figsize=(4.2 * len(Ns), 4), sharey=True, squeeze=False)
for ax, N in zip(axes[0], Ns):
    g = res[res.N_instances == N]
    ax.plot(g.C_utilisateurs_locust, g.latence_mediane_ms, "o-", label="latence mediane (mesure)")
    ax.plot(g.C_utilisateurs_locust, g.latence_moyenne_ms, "^:", color="tab:green", label="latence moyenne (mesure)")
    ax.plot(g.C_utilisateurs_locust, g.latence_little_ms, "s--", label="loi de Little : C / debit")
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xticks(sorted(g.C_utilisateurs_locust.unique()))
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_title(f"N = {N}"); ax.set_xlabel("C (utilisateurs Locust)")
    ax.grid(alpha=.3, which="both")
axes[0][0].set_ylabel("Latence (ms, echelle log)")
axes[0][0].legend(fontsize=7)
fig.suptitle("Fig. 2b - latence mediane en fonction de C, et prediction de la loi de Little")
fig.tight_layout(); fig.savefig("figures/fig2b.png", dpi=150)
print("\nFigures ecrites dans figures/")
