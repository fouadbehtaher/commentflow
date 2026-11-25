#!/usr/bin/env bash
# Real n8n acceptance for the credential variant, through the same CLI steps as deploy/bootstrap.sh (no Docker).
# Needs: n8n 2.49.x on Node >= 24 (set N8N_BIN="node /path/to/n8n/bin/n8n" if not on PATH), python3. Fully offline: fake services on 127.0.0.1:9001.
# Not a live Meta test. Uses throwaway test tokens and a temporary n8n data folder.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; N8N_BIN="${N8N_BIN:-n8n}"
export N8N_USER_FOLDER="$(mktemp -d)" N8N_PORT=5679 N8N_RUNNERS_BROKER_PORT=5681 N8N_DIAGNOSTICS_ENABLED=false N8N_PERSONALIZATION_ENABLED=false
export N8N_VERSION_NOTIFICATIONS_ENABLED=false N8N_RUNNERS_ENABLED=false N8N_SECURE_COOKIE=false
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false NODE_FUNCTION_ALLOW_BUILTIN=crypto META_APP_SECRET=s3cret WEBHOOK_VERIFY_TOKEN=vt
W=$(mktemp -d); trap 'kill ${FAKE:-} ${NPID:-} 2>/dev/null || true; rm -rf "$W"' EXIT
(cd "$HERE/.." && python3 build_private.py --test-config --out "$W/wf" >/dev/null)
printf 'IG_ACCESS_TOKEN=igtok\nPAGE_ACCESS_TOKEN=pagetok\nNOTION_TOKEN=nt\nSUPABASE_SERVICE_KEY=sk\n' > "$W/sec.env"
python3 "$HERE/../../deploy/make_credentials.py" "$W/sec.env" > "$W/cred.json"
$N8N_BIN import:credentials --input="$W/cred.json"
$N8N_BIN import:workflow --separate --input="$W/wf/"
for id in $($N8N_BIN list:workflow | grep 'CommentFlow' | cut -d'|' -f1); do $N8N_BIN publish:workflow --id="$id"; done
(cd "$HERE" && python3 fake_services.py 9001) & FAKE=$!
$N8N_BIN start > "$W/n8n.log" 2>&1 & NPID=$!
for i in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:5679/healthz | grep -q ok && break; sleep 1; done; sleep 3
(cd "$HERE" && python3 run_acceptance.py)
