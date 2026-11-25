#!/usr/bin/env bash
# Needs: Node >= 22 with n8n installed (npm i n8n), python3. Fully offline; no Meta/Notion/Supabase account.
set -euo pipefail
cd "$(dirname "$0")"
N8N_BIN="${N8N_BIN:-n8n}"
export N8N_USER_FOLDER="$(mktemp -d)" N8N_PORT=5679 N8N_DIAGNOSTICS_ENABLED=false N8N_PERSONALIZATION_ENABLED=false
export N8N_BLOCK_ENV_ACCESS_IN_NODE=false NODE_FUNCTION_ALLOW_BUILTIN=crypto
export META_APP_SECRET=s3cret WEBHOOK_VERIFY_TOKEN=vt IG_ID=IG1 FB_PAGE_ID=PAGE1
export IG_ACCESS_TOKEN=igtok PAGE_ACCESS_TOKEN=pagetok NOTION_TOKEN=nt NOTION_DATABASE_ID=db1 SUPABASE_SERVICE_KEY=sk
export IG_GRAPH_BASE=http://127.0.0.1:9001/ig GRAPH_BASE=http://127.0.0.1:9001/fb
export NOTION_BASE=http://127.0.0.1:9001/notion SUPABASE_URL=http://127.0.0.1:9001/sb
python3 fake_services.py 9001 & FAKE=$!
trap 'kill $FAKE ${N8N_PID:-} 2>/dev/null || true' EXIT
$N8N_BIN import:workflow --input=../workflows/commentflow-instagram.json
$N8N_BIN import:workflow --input=../workflows/commentflow-facebook.json
for id in $($N8N_BIN list:workflow | cut -d'|' -f1); do $N8N_BIN publish:workflow --id="$id" 2>/dev/null || $N8N_BIN update:workflow --id="$id" --active=true; done
$N8N_BIN start > "$N8N_USER_FOLDER/n8n.log" 2>&1 & N8N_PID=$!
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:5679/healthz && break; sleep 2; done
python3 run_acceptance.py
