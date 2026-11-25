#!/usr/bin/env bash
# PRIVATE, UNTESTED against real n8n 2.49.6 / Docker. Fails closed: nothing is published unless every setting is present.
set -euo pipefail
cd "$(dirname "$0")"; umask 077
CFG=/etc/commentflow/config.env; SEC=/etc/commentflow/secrets.env
[ -f "$CFG" ] && [ -f "$SEC" ] || { echo "config/secrets missing, nothing imported or published" >&2; exit 2; }
WF=$(mktemp -d)
trap 'rm -rf "$WF" /tmp/cf-credentials.json' EXIT
# 1. build workflows with the real settings; exits 3 if any is missing or still a placeholder
python3 ../n8n/build_private.py --strict --config "$CFG" --out "$WF"
python3 make_credentials.py "$SEC" > /tmp/cf-credentials.json
docker compose cp /tmp/cf-credentials.json n8n:/tmp/credentials.json
docker compose cp "$WF" n8n:/tmp/workflows
# 2. import (imported workflows start unpublished)
docker compose exec -T n8n n8n import:credentials --input=/tmp/credentials.json
docker compose exec -T n8n n8n import:workflow --separate --input=/tmp/workflows/
docker compose exec -T n8n rm -f /tmp/credentials.json
# 3. publish only the two CommentFlow workflows, individually
for id in $(docker compose exec -T n8n n8n list:workflow | grep 'CommentFlow' | cut -d'|' -f1); do
  docker compose exec -T n8n n8n publish:workflow --id="$id"
done
docker compose restart n8n
