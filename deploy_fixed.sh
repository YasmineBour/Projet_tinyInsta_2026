#!/usr/bin/env bash
# Déploie une version à N instances fixes (manual scaling, sans autoscaling),
# sans lui envoyer le trafic par défaut. Utilisé pour les parties 1 et 2.
#
#   ./deploy_fixed.sh 1        -> version "fixed1", URL https://fixed1-dot-<PROJET>.<REGION>.r.appspot.com
#   ./deploy_fixed.sh 4        -> version "fixed4"
#   ./deploy_fixed.sh 2 --project mon-projet   (arguments supplémentaires passés à gcloud)
#
# ATTENTION : une instance en manual scaling est facturée tant que la version tourne.
# Arrêtez-la dès la fin des mesures :  gcloud app versions stop fixed<N>
set -euo pipefail
N="${1:?usage: ./deploy_fixed.sh N [arguments gcloud]}"
shift
cd "$(dirname "$0")"
YAML="app-fixed-${N}.yaml"
trap 'rm -f "$YAML"' EXIT
cat > "$YAML" <<EOF
runtime: python312
entrypoint: gunicorn -b :\$PORT main:app

# Manual scaling : exactement ${N} instance(s), pas d'autoscaling.
# B1 a le même CPU et la même mémoire que F1.
instance_class: B1
manual_scaling:
  instances: ${N}

handlers:
- url: /
  script: auto
env_variables:
  SEED_TOKEN: "change-me-seed-token"
EOF
gcloud app deploy "$YAML" --version "fixed${N}" --no-promote --quiet "$@"
