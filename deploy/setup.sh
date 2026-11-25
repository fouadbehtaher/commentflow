#!/usr/bin/env bash
# PRIVATE, UNTESTED. Run once on the server as root. Collects secrets with hidden prompts (not echoed, not in shell history,
# not in process arguments), writes root-only files, then starts the stack. Nothing sensitive is printed or logged.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 2; }
cd "$(dirname "$0")"; umask 077
ask()  { local v; read -r -p "$1: " v; printf '%s' "$v"; }
asks() { local v; read -r -s -p "$1: " v; echo >&2; printf '%s' "$v"; }
need() { [ -n "$2" ] || { echo "$1 is empty, stopping (nothing started)" >&2; exit 3; }; }
DOMAIN=$(ask "Hostname (e.g. name.duckdns.org)"); need DOMAIN "$DOMAIN"
DUCK=$(asks "DuckDNS token"); need DUCK "$DUCK"
APPSECRET=$(asks "Meta app secret"); need APPSECRET "$APPSECRET"
VERIFY=$(asks "Webhook verify token"); need VERIFY "$VERIFY"
{ echo IG_ACCESS_TOKEN=$(asks "Instagram access token"); echo PAGE_ACCESS_TOKEN=$(asks "Facebook Page access token");
  echo NOTION_TOKEN=$(asks "Notion token"); echo SUPABASE_SERVICE_KEY=$(asks "Supabase service key"); } > /etc/commentflow/secrets.env
{ echo IG_ID=$(ask "Instagram business account id"); echo FB_PAGE_ID=$(ask "Facebook Page id");
  echo NOTION_DATABASE_ID=$(ask "Notion database id"); echo SUPABASE_URL=$(ask "Supabase URL (https://...supabase.co)"); } > /etc/commentflow/config.env
printf 'DOMAIN=%s\nWEBHOOK_URL=https://%s/\nN8N_HOST=%s\n' "$DOMAIN" "$DOMAIN" "$DOMAIN" > /etc/commentflow/domain.env
printf 'META_APP_SECRET=%s\nWEBHOOK_VERIFY_TOKEN=%s\n' "$APPSECRET" "$VERIFY" > /etc/commentflow/n8n.env
# DuckDNS update over HTTPS only. The URL (with the token) lives in a root-only curl config file, so it never appears in
# process arguments, cron lines or logs; output is discarded.
printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&ip="\n' "${DOMAIN%.duckdns.org}" "$DUCK" > /etc/commentflow/duckdns.curl
printf '#!/bin/sh\n# DuckDNS answers HTTP 200 with OK or KO, so check the body; the body is never printed\n[ "$(curl --proto =https --tlsv1.2 -fsS -K /etc/commentflow/duckdns.curl)" = OK ]\n' > /usr/local/bin/commentflow-duckdns
chmod 700 /usr/local/bin/commentflow-duckdns /etc/commentflow/*
echo '*/10 * * * * root /usr/local/bin/commentflow-duckdns' > /etc/cron.d/commentflow-duckdns
/usr/local/bin/commentflow-duckdns || { echo "DuckDNS update failed, stopping" >&2; exit 4; }
docker compose up -d
./bootstrap.sh
