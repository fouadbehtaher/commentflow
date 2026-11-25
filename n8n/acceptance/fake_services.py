"""Offline stand-ins for Graph (IG + FB), Notion and Supabase, for n8n acceptance runs.
Prefixes: /ig, /fb, /notion, /sb. Records every call at GET /_calls; GET/POST /_follow/<id> sets follow state."""
import json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLS, FOLLOWS, SEEN = [], set(), set()
RULES = {"results": [
    {"id": "rule-fb-gated", "properties": {
        "Name": {"title": [{"plain_text": "FB gated"}]}, "Post URL": {"url": None},
        "Media ID": {"rich_text": [{"plain_text": "777"}]}, "Keyword": {"rich_text": []},
        "Reply 1": {"rich_text": [{"plain_text": "reply"}]}, "Reply 2": {"rich_text": []}, "Reply 3": {"rich_text": []},
        "DM": {"rich_text": [{"plain_text": "SHOULD NOT SEND"}]},
        "Require follow": {"checkbox": True}, "Active": {"checkbox": True}}},
    {"id": "rule-ig", "properties": {
        "Name": {"title": [{"plain_text": "IG demo"}]},
        "Post URL": {"url": "https://www.instagram.com/p/ABC123/"},
        "Media ID": {"rich_text": []},
        "Keyword": {"rich_text": [{"plain_text": "guide"}]},
        "Reply 1": {"rich_text": [{"plain_text": "Sent, check your DMs"}]},
        "Reply 2": {"rich_text": []}, "Reply 3": {"rich_text": []},
        "DM": {"rich_text": [{"plain_text": "THE IG LINK"}]},
        "Require follow": {"checkbox": True}, "Active": {"checkbox": True}}},
    {"id": "rule-fb", "properties": {
        "Name": {"title": [{"plain_text": "FB demo"}]},
        "Post URL": {"url": None},
        "Media ID": {"rich_text": [{"plain_text": "555"}]},
        "Keyword": {"rich_text": []},
        "Reply 1": {"rich_text": [{"plain_text": "Thanks!"}]},
        "Reply 2": {"rich_text": []}, "Reply 3": {"rich_text": []},
        "DM": {"rich_text": [{"plain_text": "THE FB LINK"}]},
        "Require follow": {"checkbox": False}, "Active": {"checkbox": True}}},
]}


class H(BaseHTTPRequestHandler):
    def _do(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode() if n else ""
        body = json.loads(raw) if raw.startswith("{") or raw.startswith("[") else raw
        path = self.path.split("?")[0]
        if path == "/_calls":
            return self._out(CALLS)
        if path.startswith("/_follow/"):
            FOLLOWS.add(path.split("/")[-1]); return self._out({"ok": 1})
        CALLS.append({"m": self.command, "path": self.path, "auth": self.headers.get("Authorization", ""), "body": body})
        if path.startswith("/ig/") and self.command == "GET":
            key = path.split("/")[-1]
            if "fields=permalink" in self.path:
                return self._out({"permalink": "https://www.instagram.com/p/ABC123/", "id": key})
            return self._out({"is_user_follow_business": key in FOLLOWS})
        if path.startswith("/notion/databases/"):
            return self._out(RULES)
        if path.startswith("/notion/pages/"):
            rid = path.split("/")[-1]
            return self._out(next(r for r in RULES["results"] if r["id"] == rid))
        if path.startswith("/sb/rest/v1/comments"):
            if body["comment_id"] in SEEN:
                return self._out([])
            SEEN.add(body["comment_id"]); return self._out([body])
        return self._out({"id": "ok"})
    do_GET = do_POST = _do

    def _out(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a): pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
