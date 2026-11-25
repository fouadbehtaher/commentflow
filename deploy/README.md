# Deploy (private, untested against real n8n, Docker, Lightsail or Meta)

Target: one small Linux VPS, n8n 2.49.6 (current "stable" on docs.n8n.io, 2026-11-25) + Caddy HTTPS.

Flow: launch-script.sh (no secrets, no settings) installs Docker and clones the repo. Then once, on the server: `sudo deploy/setup.sh`.
setup.sh asks for hostname, DuckDNS token, Meta app secret, verify token, 4 API tokens and 4 settings with hidden prompts, writes root-only files in /etc/commentflow (mode 600), starts the stack and runs bootstrap.sh.

Safety design:
- No secret in the repo, in the launch script, in cron, in compose or in logs. DuckDNS update: HTTPS only (`--proto =https`), URL with token only in a root-only curl config file, body checked for OK and never printed.
- Fail closed: bootstrap.sh builds the workflows with `build_private.py --strict`; any missing or placeholder setting stops it before import. Workflows are imported unpublished and only the two CommentFlow workflows are published, one by one.
- The n8n editor is not exposed by Caddy.

Open / unverified: how a user without a PC runs setup.sh (a browser SSH console on the host is the candidate, unchecked); the n8n CLI commands (import:credentials, import:workflow --separate, list:workflow output format, publish:workflow) are from the docs and NOT run against 2.49.6; Docker, Caddy and Let's Encrypt for a duckdns name never run; secrets still sit in plain files on the server and in container environment (visible to anyone with root).
Tested here: script syntax, compose YAML, strict build (missing and placeholder settings exit 3, nothing written), credential ids match workflow references, DuckDNS HTTPS transport with an invalid token (returns KO, updater exits 1, token not in process list), 17/17 acceptance on the credential variant (emulator).
