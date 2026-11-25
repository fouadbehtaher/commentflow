#!/usr/bin/env bash
# Offline acceptance without n8n: real workflow JSON + real Code-node JS, emulated runtime. Needs Node 22.
set -euo pipefail
cd "$(dirname "$0")"
export META_APP_SECRET=s3cret WEBHOOK_VERIFY_TOKEN=vt IG_ID=IG1 FB_PAGE_ID=PAGE1
export IG_ACCESS_TOKEN=igtok PAGE_ACCESS_TOKEN=pagetok NOTION_TOKEN=nt NOTION_DATABASE_ID=db1 SUPABASE_SERVICE_KEY=sk
export IG_GRAPH_BASE=http://127.0.0.1:9001/ig GRAPH_BASE=http://127.0.0.1:9001/fb
export NOTION_BASE=http://127.0.0.1:9001/notion SUPABASE_URL=http://127.0.0.1:9001/sb
python3 fake_services.py 9001 & F=$!
node emulator.js ../workflows/commentflow-instagram.json ../workflows/commentflow-facebook.json & E=$!
trap 'kill $F $E 2>/dev/null || true' EXIT
for i in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:5679/webhook/x && break; sleep 0.3; done
python3 run_acceptance.py
