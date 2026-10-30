#!/bin/bash
cd ~/tinyinsta-2026 || exit 1
URL=$(gcloud app versions describe fixed1 --service default --format='value(versionUrl)')
mkdir -p raw

# jeu:nombre_d_utilisateurs
RUNS="u100:100 base:1000 u10000:10000 p10:100 p100:100 p1000:100"
for f in $(seq 5 5 100); do RUNS="$RUNS $(printf 'f%02d' $f):120"; done

ORDER=$(echo $RUNS | tr ' ' '\n' | shuf --random-source=<(yes 2026))
echo "$ORDER" > raw/order.txt

# échauffement de l'instance (non conservé dans raw/)
TINY_PREFIX=base TINY_USERS=1000 TINY_LOG=/tmp/warmup.csv \
  python -m locust -f bench/locustfile.py --headless -u 1 -r 1 -t 20s --only-summary --host $URL > /dev/null 2>&1

for item in $ORDER; do
  prefix=${item%%:*}; users=${item##*:}
  if [ -f raw/$prefix.csv ]; then echo "SKIP $prefix"; continue; fi
  n=$(curl -s "$URL/api/timeline?user=${prefix}_u00001" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])")
  if [ "$n" != "20" ]; then echo "STOP : $prefix renvoie count=$n"; exit 1; fi
  echo "=== RUN $prefix $(date +%T)"
  TINY_PREFIX=$prefix TINY_USERS=$users TINY_LOG=raw/$prefix.csv \
    python -m locust -f bench/locustfile.py --headless -u 1 -r 1 -t 60s --only-summary --host $URL \
    > /dev/null 2>&1 || { echo "ERREUR sur $prefix"; exit 1; }
  echo "OK $prefix : $(($(wc -l < raw/$prefix.csv)-1)) requêtes"
done
echo "CAMPAGNE TERMINÉE"
