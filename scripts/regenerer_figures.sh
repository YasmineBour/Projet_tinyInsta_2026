#!/bin/bash
# Regenere TOUTES les figures et tous les CSV de figures a partir des journaux bruts de raw/.
# Une seule commande :  bash scripts/regenerer_figures.sh
set -e
cd "$(dirname "$0")/.."
python3 scripts/analyse_p1.py
python3 scripts/analyse_p2.py
if ls raw/p3_f*.csv > /dev/null 2>&1; then python3 scripts/analyse_p3.py; fi
echo "Toutes les figures ont ete regenerees dans figures/"
