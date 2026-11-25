import hashlib
import hmac
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Config
from .engine import Engine
from .meta import MetaClient
from .rules import load_file, load_notion
from .store import Store


def verify_signature(app_secret, raw, header):
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    mac = hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, header[7:])


def make_handler(cfg, engine):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body=b""):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # Meta webhook verification handshake
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == "/healthz":
                return self._send(200, b"ok")
            if (q.get("hub.mode") == ["subscribe"] and cfg.verify_token
                    and hmac.compare_digest(q.get("hub.verify_token", [""])[0], cfg.verify_token)):
                return self._send(200, q.get("hub.challenge", [""])[0].encode())
            self._send(403)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not verify_signature(cfg.app_secret, raw, self.headers.get("X-Hub-Signature-256")):
                return self._send(401)
            try:
                engine.handle_payload(json.loads(raw))
            except Exception:
                pass  # always 200 after auth so Meta does not retry-storm
            self._send(200)

        def log_message(self, *a):
            pass
    return H


def build(cfg):
    store = Store(cfg.db_path, cfg.supabase_url, cfg.supabase_key)
    meta = MetaClient(cfg)

    cache = {}

    def get_rules():
        rules = (load_notion(cfg.notion_token, cfg.notion_database_id)
                 if cfg.rules_source == "notion" else load_file(cfg.rules_file))
        for r in rules:  # a post URL is enough; resolve its media id once
            if not r.media_id and r.permalink:
                if r.permalink not in cache:
                    cache[r.permalink] = meta.media_permalink_to_id(r.permalink) or ""
                r.media_id = cache[r.permalink]
        return rules
    return Engine(cfg, store, meta, get_rules), store, meta


def main():
    cfg = Config.from_env()
    engine, _, _ = build(cfg)
    print(f"CommentFlow on {cfg.host}:{cfg.port} (dry_run={cfg.dry_run})")
    ThreadingHTTPServer((cfg.host, cfg.port), make_handler(cfg, engine)).serve_forever()


if __name__ == "__main__":
    main()
