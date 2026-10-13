#!/usr/bin/env bash
# Génère la version en ligne du sujet (public/index.html) à partir de SUJET.md.
# À relancer après chaque modification de SUJET.md, puis committer public/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p public
pandoc SUJET.md -f gfm -t html5 --standalone --embed-resources --css site/style.css \
  --metadata pagetitle="Projet Données massives et Cloud — TinyInsta 2026" --metadata lang=fr \
  -o public/index.html
echo "public/index.html régénéré"
