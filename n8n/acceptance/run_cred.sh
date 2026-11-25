#!/usr/bin/env bash
# Same 17 checks against the credential-based variant. Only the two webhook secrets are in the environment;
# tokens come from Header Auth "credentials" (CRED_MAP) and settings from the Config node.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 build_private.py --test-config
cd acceptance
env -i PATH="$PATH" META_APP_SECRET=s3cret WEBHOOK_VERIFY_TOKEN=vt \
 CRED_MAP='{"CommentFlow IG token":{"name":"Authorization","value":"Bearer igtok"},"CommentFlow Page token":{"name":"Authorization","value":"Bearer pagetok"},"CommentFlow Notion token":{"name":"Authorization","value":"Bearer nt"},"CommentFlow Supabase key":{"name":"apikey","value":"sk"}}' \
 bash -c 'python3 fake_services.py 9001 & F=$!
node emulator.js /tmp/workflows_cred/commentflow-instagram.json /tmp/workflows_cred/commentflow-facebook.json & E=$!
trap "kill $F $E 2>/dev/null || true" EXIT
for i in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:5679/webhook/x && break; sleep 0.3; done
python3 run_acceptance.py'
