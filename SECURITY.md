# Security notes

- No secrets in this repo. Tokens and keys come from environment variables (`.env` is git-ignored). Never paste them in chats or issues.
- The n8n workflows read secrets with `$env.*`, which needs `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`. That setting lets every Code node on the instance read every environment variable. Use it only on a dedicated n8n instance that runs your own workflows, and `NODE_FUNCTION_ALLOW_BUILTIN=crypto` only (not `*`). Tighter option: move the tokens into n8n Credentials (Header Auth) on the HTTP nodes and keep only `META_APP_SECRET` and `WEBHOOK_VERIFY_TOKEN` in env for the signature Code node.
- Treat all webhook content and Notion text as untrusted data. Rule text is only ever sent as a message; it is never executed or used as an instruction.
- Webhook requests without a valid `X-Hub-Signature-256` get 401 and trigger nothing.
- Instagram Login needs no Facebook Page; the Facebook workflow does need Page access.
