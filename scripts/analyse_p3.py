#!/usr/bin/env python3
"""Partie 3 : compare la version d'origine (raw/f<F>.csv, partie 1) et la version corrigee
(raw/p3_f<F>.csv). Ecrit figures/fig3.csv, figures/fig3.png et figures/fig3_cout.csv.
Une seule commande : python3 scripts/analyse_p3.py
"""
import math
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WARMUP_S = 5                  # meme traitement que la partie 1
PRIX_LECTURE_MILLION = 0.42   # 0,042 $ / 100 000 lectures a Zurich -> 0,42 $ par "lecture par timeline" pour 1 million de timelines
os.makedirs("figures", exist_ok=True)


def stats(path):
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    t0 = d.T_START.min()
    ok = d[((d.T_START - t0) >= WARMUP_S) & (d.STATUS == 200)]
    return dict(n=len(ok), serveur=ok.SERVER_MS.median(), client=ok.LATENCY_MS.median(),
                instances=d.INSTANCE.nunique(), codes=str(d.STATUS.value_counts().to_dict()))


def lectures_avant(F):    # d'apres le code : IN si F + 1 <= 30 auteurs, sinon une requete par auteur (P = 20)
    return 21 if F + 1 <= 30 else 1 + 20 * (F + 1)


def lectures_apres(F):    # un IN par groupe de 30 auteurs au plus
    return 1 + 20 * math.ceil((F + 1) / 30)


rows = []
for F in range(5, 105, 5):
    jeu = f"f{F:02d}"
    av, ap = stats(f"raw/{jeu}.csv"), stats(f"raw/p3_{jeu}.csv")
    if av is None or ap is None:
        print("Donnees manquantes pour", jeu, "(avant :", av is not None, ", apres :", ap is not None, ")")
        continue
    rows.append({
        "F_followees": F, "U_utilisateurs": 120, "P_posts_par_user": 20,
        "n_requetes_http200_avant": av["n"], "n_requetes_http200_apres": ap["n"],
        "temps_serveur_median_avant_ms": av["serveur"], "temps_serveur_median_apres_ms": ap["serveur"],
        "latence_client_mediane_avant_ms": av["client"], "latence_client_mediane_apres_ms": ap["client"],
        "instances_distinctes_avant": av["instances"], "instances_distinctes_apres": ap["instances"],
        "codes_http_apres": ap["codes"],
    })

if not rows:
    raise SystemExit("Aucune paire de fichiers raw/f<F>.csv et raw/p3_f<F>.csv trouvee.")

res = pd.DataFrame(rows)
res["gain_temps_serveur"] = (res.temps_serveur_median_avant_ms / res.temps_serveur_median_apres_ms).round(2)
res.to_csv("figures/fig3.csv", index=False)
print(res[["F_followees", "n_requetes_http200_apres", "instances_distinctes_apres", "codes_http_apres",
           "temps_serveur_median_avant_ms", "temps_serveur_median_apres_ms", "gain_temps_serveur"]].to_string(index=False))

cout = pd.DataFrame({"F_followees": res.F_followees})
cout["entites_lues_par_timeline_avant"] = cout.F_followees.map(lectures_avant)
cout["entites_lues_par_timeline_apres"] = cout.F_followees.map(lectures_apres)
cout["cout_1M_timelines_avant_usd"] = (cout.entites_lues_par_timeline_avant * PRIX_LECTURE_MILLION).round(2)
cout["cout_1M_timelines_apres_usd"] = (cout.entites_lues_par_timeline_apres * PRIX_LECTURE_MILLION).round(2)
cout.to_csv("figures/fig3_cout.csv", index=False)
print("\nEntites lues (deduites du code) et cout de 1 million de timelines :")
print(cout.to_string(index=False))

fig, ax = plt.subplots(1, 2, figsize=(11, 4.3))
ax[0].plot(res.F_followees, res.temps_serveur_median_avant_ms, "o-", color="tab:blue", label="temps serveur, avant")
ax[0].plot(res.F_followees, res.temps_serveur_median_apres_ms, "o-", color="tab:green", label="temps serveur, apres")
ax[0].plot(res.F_followees, res.latence_client_mediane_avant_ms, "s--", color="tab:blue", alpha=.45, label="latence client, avant")
ax[0].plot(res.F_followees, res.latence_client_mediane_apres_ms, "s--", color="tab:green", alpha=.45, label="latence client, apres")
ax[0].set_xlabel("F (comptes suivis par utilisateur)"); ax[0].set_ylabel("Mediane (ms)")
ax[0].set_title("Echelle lineaire"); ax[0].grid(alpha=.3); ax[0].legend(fontsize=7)
ax[1].plot(res.F_followees, res.temps_serveur_median_avant_ms, "o-", color="tab:blue", label="avant (une requete par auteur si F >= 30)")
ax[1].plot(res.F_followees, res.temps_serveur_median_apres_ms, "o-", color="tab:green", label="apres (IN par groupes de 30)")
ax[1].set_yscale("log"); ax[1].set_xlabel("F (comptes suivis par utilisateur)")
ax[1].set_ylabel("Temps serveur median (ms, echelle log)")
ax[1].set_title("Temps serveur, echelle log"); ax[1].grid(alpha=.3, which="both"); ax[1].legend(fontsize=7)
fig.suptitle("Fig. 3 - avant / apres correction, fixed1 (1 instance), 1 requete a la fois (U=120, P=20)")
fig.tight_layout(); fig.savefig("figures/fig3.png", dpi=150)
print("\nFigure ecrite : figures/fig3.png")
