#!/bin/bash
# Partie 3 : mesure de la version corrigée de get_timeline (requêtes IN par groupes de 30 auteurs).
# Usage : bash scripts/campagne_p3.sh
#
# MÊME PROTOCOLE que la partie 1 (Fig. 1b) : une version à 1 instance fixe (B1, manual scaling,
# même configuration que fixed1), Locust avec 1 utilisateur (-u 1), 60 s par run, les 20 jeux
# f05 ... f100 (U = 120, P = 20) dans un ordre mélangé, 5 premières secondes écartées à l'analyse.
# Seul le code de get_timeline change. La version est déployée avec --no-promote.
#
# Sorties : raw/p3_<jeu>.csv, raw/p3_order.txt, raw/p3_<jeu>_locust.txt, raw/p3_instances_*.txt.
# La version est ARRÊTÉE à la fin (même après une erreur). Variantes :
#   SKIP_DEPLOY=1 bash scripts/campagne_p3.sh   : redémarre la version existante sans la redéployer
#   VERSION=autrenom bash scripts/campagne_p3.sh : change le nom de la version (défaut : fixchunk)
#   KEEP=1 ...                                   : ne pas arrêter la version à la fin (déconseillé)

set -u
cd "$(dirname "$0")/.." || exit 1
VERSION=${VERSION:-fixchunk}
YAML="app-${VERSION}.yaml"
APP=https://tinyinsta-510215.oa.r.appspot.com      # version par défaut (ancien code), pour comparer les résultats
DUREE=60
mkdir -p raw

stop_version() {
  rm -f "$YAML"
  if [ "${KEEP:-0}" = "1" ]; then
    echo "KEEP=1 : $VERSION reste allumée (ATTENTION : facturée tant qu'elle tourne)"
    return
  fi
  echo "=== Arrêt de $VERSION"
  timeout 180 gcloud app versions stop "$VERSION" --service default --quiet \
    || echo "ATTENTION : l'arrêt n'a pas abouti. Tape à la main : gcloud app versions stop $VERSION --service default --quiet"
}
trap stop_version EXIT

# Le correctif doit être dans main.py avant le déploiement
if [ "${SKIP_DEPLOY:-0}" != "1" ] && ! grep -q "MAX_IN" main.py; then
  echo "ERREUR : main.py ne contient pas le correctif. Lance d'abord : python3 scripts/appliquer_correctif_p3.py"
  exit 1
fi

# ---------- 1. Déploiement (même configuration que fixed1) ----------
deploy_version() {
  cat > "$YAML" <<EOF2
runtime: python312
entrypoint: gunicorn -b :\$PORT main:app
instance_class: B1
manual_scaling:
  instances: 1
handlers:
- url: /
  script: auto
env_variables:
  SEED_TOKEN: "change-me-seed-token"
EOF2
  timeout 600 gcloud app deploy "$YAML" --version "$VERSION" --no-promote --quiet
}

if [ "${SKIP_DEPLOY:-0}" = "1" ]; then
  echo "=== SKIP_DEPLOY=1 : pas de redéploiement, on redémarre la version existante $VERSION"
else
  echo "=== Déploiement de $VERSION  $(date +%T)"
  deploy_version; RC=$?
  if [ "$RC" != "0" ]; then
    echo "ERREUR : le déploiement a échoué (code $RC). Regarde : gcloud app operations list --limit=5"
    exit 1
  fi
fi
URL=$(gcloud app versions describe "$VERSION" --service default --format='value(versionUrl)')
echo "URL : $URL"

echo "=== Démarrage de $VERSION (sans effet si elle tourne déjà)"
timeout 300 gcloud app versions start "$VERSION" --service default --quiet \
  || echo "(démarrage : erreur ou déjà démarrée, on vérifie ci-dessous)"

OK=0
for i in $(seq 1 12); do
  ST=$(timeout 60 gcloud app versions describe "$VERSION" --service default --format='value(servingStatus)' 2>/dev/null)
  NB=$(timeout 60 gcloud app instances list --service default --version "$VERSION" --format='value(id)' 2>/dev/null | wc -l)
  echo "état : ${ST:-inconnu} | instances listées : $NB (attendu : 1)"
  if [ "$ST" = "SERVING" ] && [ "$NB" = "1" ]; then OK=1; break; fi
  sleep 20
done
[ "$OK" = "1" ] || { echo "ERREUR : $VERSION n'est pas SERVING avec 1 instance"; exit 1; }
gcloud app instances list --service default --version "$VERSION" > raw/p3_instances_avant.txt 2>&1

# ---------- 2. Vérifications ----------
curl -sI "$URL/api/timeline?user=f20_u00001" | grep -iE "x-instance|server-timing" > /dev/null \
  || { echo "ERREUR : en-têtes X-Instance / Server-Timing absents (mauvaise version ?)"; exit 1; }
echo "=== Les timelines de la version corrigée sont-elles identiques à celles de l'ancienne version ?"
python3 scripts/comparer_timelines.py "$APP" "$URL" f05_u00001 f20_u00001 f30_u00001 f100_u00001 \
  || echo "ATTENTION : des différences existent (voir ci-dessus). On continue les mesures, mais il faudra les expliquer."

# ---------- 3. Échauffement (comme en partie 1 : 20 s sur base, non conservé) ----------
echo "=== Échauffement  $(date +%T)"
TINY_PREFIX=base TINY_USERS=1000 TINY_LOG=/tmp/warmup_p3.csv \
  python -m locust -f bench/locustfile.py --headless -u 1 -r 1 -t 20s --only-summary --host "$URL" > /dev/null 2>&1

# ---------- 4. Mesures : les 20 jeux f05 ... f100, ordre mélangé ----------
JEUX=""
for f in $(seq 5 5 100); do JEUX="$JEUX $(printf 'f%02d' $f)"; done
ORDER=$(echo $JEUX | tr ' ' '\n' | shuf --random-source=<(yes 2026))
echo "$ORDER" > raw/p3_order.txt

for prefix in $ORDER; do
  F="raw/p3_${prefix}.csv"
  if [ -f "$F" ]; then echo "SKIP $prefix (déjà fait)"; continue; fi
  N20=$(curl -s "$URL/api/timeline?user=${prefix}_u00001" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])")
  if [ "$N20" != "20" ]; then echo "STOP : $prefix renvoie count=$N20"; exit 1; fi
  echo "=== RUN $prefix  $(date +%T)"
  TINY_PREFIX=$prefix TINY_USERS=120 TINY_LOG="$F" \
    timeout -k 20 -s INT $((DUREE+60)) \
    python -m locust -f bench/locustfile.py --headless -u 1 -r 1 -t "${DUREE}s" --only-summary --host "$URL" \
    > "raw/p3_${prefix}_locust.txt" 2>&1
  RC=$?
  if [ ! -s "$F" ]; then
    echo "ERREUR sur $prefix : pas de journal (code Locust : $RC)"; tail -15 "raw/p3_${prefix}_locust.txt"; exit 1
  fi
  NREQ=$(( $(wc -l < "$F") - 1 ))
  NINST=$(awk -F, 'NR>1 && $4!="" {print $4}' "$F" | sort -u | wc -l)
  CODES=$(tail -n +2 "$F" | cut -d, -f3 | sort | uniq -c | tr '\n' ' ')
  echo "OK $prefix : $NREQ requêtes, $NINST instance(s) | codes HTTP : $CODES| code Locust : $RC"
done

gcloud app instances list --service default --version "$VERSION" > raw/p3_instances_apres.txt 2>&1
echo "CAMPAGNE PARTIE 3 TERMINÉE  $(date +%T)"
