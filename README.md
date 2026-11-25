# CommentFlow

> **Status: tested on a real n8n 2.49.6 against fake services only.** The workflows (credential variant, via the n8n CLI import path) passed the 16 acceptance checks on a local n8n 2.49.6 (Node 24) with fake Graph/Notion/Supabase servers. Not tested: live Meta, Docker/Caddy/HTTPS, a hosted server. The Instagram follow gate (an "I followed" button in the private reply) is a design that is untested live; Meta does not document whether the button shows in a private reply that lands in Requests. Facebook has no documented follow check, so follow-gated rules are blocked there.

**Two ways to run it**: n8n workflows for Instagram and Facebook (`n8n/`), and a standalone Python service for Instagram (`commentflow/`). Both read the same Notion rules and log to Supabase.

## n8n workflows (`n8n/workflows/`)
`commentflow-instagram.json` and `commentflow-facebook.json`. Import both, set the env vars in `.env.example`, set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` and `NODE_FUNCTION_ALLOW_BUILTIN=crypto`, activate, and point the Meta webhooks at `/webhook/commentflow-ig` and `/webhook/commentflow-fb`. The workflows are generated from `n8n/src/*.js` by `n8n/build.py`.

- Instagram: signed webhook, rule match (post + keyword), Supabase dedupe, public reply (random of 3), private reply. With "Require follow", the private reply carries an "I followed" button; the follow state is read only after the tap (Meta gives no follow data for a comment alone).
- Facebook: same flow, but Meta documents no follow check for Pages, so a rule with "Require follow" is blocked and logged, and nothing is sent.
- Tests: `n8n/acceptance/run_emulated.sh` runs the real workflow JSON and Code-node JS through a small emulator against fake Graph/Notion/Supabase servers (16 checks). `run_acceptance.sh` does the same inside real n8n; `run_real_n8n.sh` does it with the credential variant through the CLI import path. n8n 2.49.6 needs Node 24 or newer; with pnpm the install worked on a 2 GB machine (about 600 MB RAM while running). The emulator once hid a real bug (status codes as strings), so prefer the real-n8n run. Neither is a live Meta test.

---


Comment-to-DM automation for Instagram, using Meta's official Graph API. When someone comments a keyword on a post, CommentFlow replies publicly (one of up to three variants, picked at random), then sends the details by DM. Optionally (Instagram only, untested live) the DM is held until the person taps a follow-confirm button.

Uses the idea from a public LinkedIn post by Abdallah Helal about replacing ManyChat with n8n, Notion and Supabase, and adds signature checks, dedupe, keyword matching and a Facebook path. It is written from scratch and contains none of his workflow files.

## Flow
1. Meta sends a `comments` webhook (signature checked with `X-Hub-Signature-256`).
2. A rule matches the post and keyword. Duplicates and the account's own comments are ignored.
3. Public reply, then a private reply to the comment.
4. With "require follow": the private reply has an "I followed" button. When tapped, the follow state is read from the User Profile API. If following, the DM goes out. If not, a reminder with the same button is sent.
5. Every step is logged to SQLite, and mirrored to Supabase if configured.

Rules live in a JSON file or a Notion database (one row per post: Name, Post URL, Media ID, Keyword, Reply 1-3, DM, Require follow, Active). A post URL is enough; the media ID is resolved automatically.

## Run
    cp .env.example .env   # fill in, then: set -a; . ./.env; set +a
    python3 -m commentflow.server      # DRY_RUN=1 logs sends instead of calling Meta
    python3 -m unittest discover -s tests -v

Pure Python 3.10+ standard library, no installs. Point your Meta webhook callback at `https://<host>/` with your verify token and subscribe to `comments` and `messages`.

See `docs/META_REQUIREMENTS.md` for access, review and cost details. Supabase table: `supabase.sql`.

## Limits
Meta allows one private reply per comment, within 7 days. The follow button works only because the person taps it, which is what makes the follow state readable. Check Meta's platform terms and your audience's consent rules before sending automated messages.

License: MIT.
