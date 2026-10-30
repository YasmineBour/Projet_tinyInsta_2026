#!/usr/bin/env python3
"""Partie 1 : lit raw/<jeu>.csv, ecrit figures/fig1a.csv, fig1b.csv, resume_p1.csv et les PNG."""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WARMUP_S = 5  # secondes ecartees au debut de chaque run (demarrage a froid)
os.makedirs("figures", exist_ok=True)

# jeu -> (facteur, valeur du facteur, U, P, F)
JEUX = {
    "u100":   ("U", 100,   100,   20,   20),
    "base":   ("U", 1000,  1000,  20,   20),
    "u10000": ("U", 10000, 10000, 20,   20),
    "p10":    ("P", 10,    100,   10,   20),
    "p100":   ("P", 100,   100,   100,  20),
    "p1000":  ("P", 1000,  100,   1000, 20),
}
for f in range(5, 105, 5):
    JEUX[f"f{f:02d}"] = ("F", f, 120, 20, f)
# u100 sert aussi de point P = 20 (U = 100, F = 20)
P_REF = ("u100", 20)

rows = {}
for jeu, (fac, val, U, P, F) in JEUX.items():
    path = f"raw/{jeu}.csv"
    if not os.path.exists(path):
        print("MANQUANT :", path)
        continue
    d = pd.read_csv(path)
    t0 = d.T_START.min()
    kept = d[(d.T_START - t0) >= WARMUP_S]
    ok = kept[kept.STATUS == 200]
    rows[jeu] = dict(
        jeu=jeu, facteur=fac, valeur=val, U=U, P=P, F=F,
        n_requetes_total=len(d), n_requetes_gardees=len(kept), n_http200=len(ok),
        instances_distinctes=d.INSTANCE.nunique(),
        codes_http=str(d.STATUS.value_counts().to_dict()),
        temps_serveur_median_ms=ok.SERVER_MS.median(),
        latence_client_mediane_ms=ok.LATENCY_MS.median(),
    )

res = pd.DataFrame(rows.values())
res.to_csv("figures/resume_p1.csv", index=False)
print(res[["jeu", "n_requetes_gardees", "instances_distinctes", "codes_http",
           "temps_serveur_median_ms", "latence_client_mediane_ms"]].to_string(index=False))

def sel(fac):
    s = res[res.facteur == fac].copy()
    if fac == "P" and P_REF[0] in rows:
        r = res[res.jeu == P_REF[0]].iloc[0].copy()
        r["facteur"], r["valeur"] = "P", P_REF[1]
        s = pd.concat([s, r.to_frame().T], ignore_index=True)
    s["valeur"] = s["valeur"].astype(float)
    return s.sort_values("valeur")

# ---- Fig 1a : temps serveur median vs U et vs P
U_, P_ = sel("U"), sel("P")
pd.concat([U_, P_])[["facteur", "valeur", "jeu", "U", "P", "F", "n_http200",
                     "temps_serveur_median_ms"]].rename(columns={
    "valeur": "valeur_du_facteur", "U": "U_utilisateurs", "P": "P_posts_par_user",
    "F": "F_followees", "n_http200": "n_requetes_http200"
}).to_csv("figures/fig1a.csv", index=False)

fig, ax = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
ax[0].plot(U_.valeur, U_.temps_serveur_median_ms, "o-")
ax[0].set_xscale("log"); ax[0].set_xlabel("U (utilisateurs)")
ax[0].set_ylabel("Temps serveur median (ms)")
ax[0].set_title("Facteur U  (P=20, F=20)")
ax[1].plot(P_.valeur, P_.temps_serveur_median_ms, "o-")
ax[1].set_xscale("log"); ax[1].set_xlabel("P (posts par utilisateur)")
ax[1].set_title("Facteur P  (U=100, F=20)")
for a in ax: a.grid(alpha=.3)
fig.suptitle("Fig. 1a - fixed1, 1 requete a la fois")
fig.tight_layout(); fig.savefig("figures/fig1a.png", dpi=150)

# ---- Fig 1b : temps serveur et latence client vs F
F_ = sel("F")
F_[["valeur", "jeu", "U", "P", "n_http200", "temps_serveur_median_ms",
    "latence_client_mediane_ms"]].rename(columns={
    "valeur": "F_followees", "U": "U_utilisateurs", "P": "P_posts_par_user",
    "n_http200": "n_requetes_http200"
}).to_csv("figures/fig1b.csv", index=False)

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(F_.valeur, F_.temps_serveur_median_ms, "o-", label="Temps serveur (Server-Timing)")
ax.plot(F_.valeur, F_.latence_client_mediane_ms, "s-", label="Latence client (Locust)")
ax.set_xlabel("F (comptes suivis par utilisateur)")
ax.set_ylabel("Mediane (ms)")
ax.set_title("Fig. 1b - fixed1, 1 requete a la fois (U=120, P=20)")
ax.grid(alpha=.3); ax.legend()
fig.tight_layout(); fig.savefig("figures/fig1b.png", dpi=150)
print("Figures ecrites dans figures/")
