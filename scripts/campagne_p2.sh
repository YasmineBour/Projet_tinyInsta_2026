#!/bin/bash
# Partie 2 : capacité.
# Usage : bash scripts/campagne_p2.sh N      (N = 1, 2 ou 4)
#   Variante : SUFFIX=b bash scripts/campagne_p2.sh 1   (déploie sous le nom fixed1b si fixed1 est bloquée)
#
# Ce script, pour UNE version fixedN :
#   1. déploie la version (./deploy_fixed.sh N) et attend que N instances existent ;
#   2. vérifie que le jeu "base" répond (20 posts) et que les en-têtes X-Instance / Server-Timing sont là ;
#   3. échauffe toutes les instances (non conservé) ;
#   4. mesure C = 1, 2, 4, 8, 16, 32, 64 utilisateurs Locust, dans un ordre mélangé (graine fixe) ;
#   5. ARRÊTE la version à la fin (même en cas d'erreur ou de Ctrl+C), pour ne plus être facturée.
#
# Sorties : raw/p2_N<N>_C<C>.csv (un journal brut par run), raw/p2_N<N>_order.txt,
#           raw/p2_N<N>_instances_avant.txt et raw/p2_N<N>_instances_apres.txt.
# Pour garder la version allumée à la fin (déconseillé) : KEEP=1 bash scripts/campagne_p2.sh N

set -u
N=${1:?"Usage : bash scripts/campagne_p2.sh N   (N = 1, 2 ou 4)"}
case $N in
  1|2|4) ;;
  *) echo "N doit valoir 1, 2 ou 4"; exit 1 ;;
esac

cd "$(dirname "$0")/.." || exit 1      # racine du dépôt
SUFFIX=${SUFFIX:-}                     # ex. SUFFIX=b pour déployer sous le nom fixed1b
VERSION=fixed${N}${SUFFIX}
YAML="app-fixed-${N}${SUFFIX}.yaml"
DUREE=60                               # secondes par run
mkdir -p raw

stop_version() {
  rm -f "$YAML"
  if [ "${KEEP:-0}" = "1" ]; then
    echo "KEEP=1 : $VERSION reste allumée (ATTENTION : elle est facturée tant qu'elle tourne)"
    return
  fi
  echo "=== Arrêt de $VERSION"
  timeout 180 gcloud app versions stop "$VERSION" --service default --quiet \
    || echo "ATTENTION : l'arrêt n'a pas abouti. Tape à la main : gcloud app versions stop $VERSION --service default --quiet"
}
trap stop_version EXIT

# ---------- 1. Déploiement ----------
# Sans SUFFIX : on utilise le script fourni (./deploy_fixed.sh), qui crée la version fixedN.
# Avec SUFFIX : même configuration (B1, manual scaling, gunicorn identique), mais sous un autre nom.
deploy_version() {
  if [ -z "$SUFFIX" ]; then timeout 600 ./deploy_fixed.sh "$N"; return; fi
  cat > "$YAML" <<EOF2
runtime: python312
entrypoint: gunicorn -b :\$PORT main:app
instance_class: B1
manual_scaling:
  instances: ${N}
handlers:
- url: /
  script: auto
env_variables:
  SEED_TOKEN: "change-me-seed-token"
EOF2
  timeout 600 gcloud app deploy "$YAML" --version "$VERSION" --no-promote --quiet
}

echo "=== Déploiement de $VERSION  $(date +%T)"
for TRY in 1 2 3 4 5; do
  deploy_version; RC=$?
  if [ "$RC" = "0" ]; then break; fi
  if [ "$RC" = "124" ]; then
    echo "ERREUR : le déploiement dépasse 10 minutes (opération App Engine probablement bloquée)."
    echo "Regarde : gcloud app operations list --limit=5   puis réessaie avec un autre SUFFIX."
    exit 1
  fi
  if [ "$TRY" = "5" ]; then echo "ERREUR : le déploiement a échoué 5 fois"; exit 1; fi
  echo "Déploiement refusé (une opération est peut-être déjà en cours sur $VERSION). Nouvel essai dans 90 s ($TRY/5)"
  sleep 90
done
URL=$(gcloud app versions describe "$VERSION" --service default --format='value(versionUrl)')
echo "URL : $URL"

# Une version déjà arrêtée (cas d'un redéploiement) peut rester arrêtée : on la démarre explicitement.
echo "=== Démarrage de $VERSION (sans effet si elle tourne déjà)"
timeout 300 gcloud app versions start "$VERSION" --service default --quiet \
  || echo "(démarrage : erreur ou déjà démarrée, on vérifie ci-dessous)"

# attendre que l'état soit SERVING et que le nombre d'instances listées soit N
OK=0
for i in $(seq 1 12); do
  ST=$(timeout 60 gcloud app versions describe "$VERSION" --service default --format='value(servingStatus)' 2>/dev/null)
  NB=$(timeout 60 gcloud app instances list --service default --version "$VERSION" --format='value(id)' 2>/dev/null | wc -l)
  echo "état : ${ST:-inconnu} | instances listées : $NB (attendu : $N)"
  if [ "$ST" = "SERVING" ] && [ "$NB" = "$N" ]; then OK=1; break; fi
  sleep 20
done
[ "$OK" = "1" ] || { echo "ERREUR : $VERSION n'est pas SERVING avec $N instance(s)"; exit 1; }
gcloud app instances list --service default --version "$VERSION" > "raw/p2_N${N}_instances_avant.txt" 2>&1

# ---------- 2. Vérifications ----------
COUNT=$(curl -s "$URL/api/timeline?user=base_u00001" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])")
[ "$COUNT" = "20" ] || { echo "ERREUR : le jeu base renvoie count=$COUNT au lieu de 20"; exit 1; }
curl -sI "$URL/api/timeline?user=base_u00001" | grep -iE "x-instance|server-timing" > /dev/null \
  || { echo "ERREUR : en-têtes X-Instance / Server-Timing absents (mauvaise version ?)"; exit 1; }
echo "Vérifications OK (count=20, en-têtes présents)"

# ---------- 3. Échauffement ----------
echo "=== Échauffement  $(date +%T)"
TINY_PREFIX=base TINY_USERS=1000 TINY_LOG="/tmp/warmup_N${N}.csv" \
  python -m locust -f bench/locustfile.py --headless -u $((8*N)) -r $((8*N)) -t 25s --only-summary --host "$URL" > /dev/null 2>&1

# ---------- 4. Mesures ----------
ORDER=$(printf '%s\n' 1 2 4 8 16 32 64 | shuf --random-source=<(yes $((2026+N))))
echo "$ORDER" > "raw/p2_N${N}_order.txt"
echo "Ordre des runs : $(echo $ORDER)"

for C in $ORDER; do
  F="raw/p2_N${N}_C${C}.csv"
  if [ -f "$F" ]; then echo "SKIP C=$C (déjà fait)"; continue; fi
  echo "=== RUN N=$N C=$C  $(date +%T)"
  TINY_PREFIX=base TINY_USERS=1000 TINY_LOG="$F" \
    python -m locust -f bench/locustfile.py --headless -u "$C" -r "$C" -t "${DUREE}s" --only-summary --host "$URL" > /dev/null 2>&1 \
    || { echo "ERREUR sur C=$C"; exit 1; }
  NREQ=$(( $(wc -l < "$F") - 1 ))
  NINST=$(tail -n +2 "$F" | cut -d, -f4 | sort -u | wc -l)
  echo "OK C=$C : $NREQ requêtes, $NINST instance(s) ont répondu"
done

gcloud app instances list --service default --version "$VERSION" > "raw/p2_N${N}_instances_apres.txt" 2>&1
echo "CAMPAGNE N=$N TERMINÉE  $(date +%T)"
