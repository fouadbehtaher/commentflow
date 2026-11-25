import hashlib, hmac, json, os, sys, tempfile, threading, unittest, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from commentflow.config import Config
from commentflow.engine import Engine
from commentflow.meta import MetaClient
from commentflow.rules import Rule
from commentflow.server import make_handler, verify_signature
from commentflow.store import Store
from http.server import ThreadingHTTPServer


class FakeGraph:
    """Local stand-in for Graph API; records every call and serves follow state."""
    def __init__(self):
        self.calls, self.follows = [], set()
        outer = self

        class H(BaseHTTPRequestHandler):
            def _do(self):
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                u = urlparse(self.path)
                outer.calls.append((self.command, u.path, parse_qs(u.query), body))
                if self.command == "GET":
                    uid = u.path.strip("/")
                    resp = {"is_user_follow_business": uid in outer.follows}
                else:
                    resp = {"id": "ok"}
                data = json.dumps(resp).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(data)
            do_GET = do_POST = _do
            def log_message(self, *a): pass
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"


def comment(cid="c1", text="send the GUIDE please", uid="u1", media="m1"):
    return {"entry": [{"changes": [{"field": "comments", "value": {
        "id": cid, "text": text, "from": {"id": uid, "username": "bob"}, "media": {"id": media}}}]}]}


def tap(uid="u1", rule="r1"):
    return {"entry": [{"messaging": [{"sender": {"id": uid},
            "message": {"quick_reply": {"payload": "CF_FOLLOWED:" + rule}}}]}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.g = FakeGraph()
        self.cfg = Config(graph_base=self.g.base, page_id="PAGE", ig_id="IG", page_token="tok",
                          db_path=":memory:", dry_run=False, app_secret="s3cret", verify_token="vt")
        self.store = Store(":memory:")
        self.meta = MetaClient(self.cfg)
        self.rules = [Rule(id="r1", media_id="m1", keyword="guide", replies=["a", "b", "c"],
                           dm_text="THE LINK", require_follow=True)]
        self.eng = Engine(self.cfg, self.store, self.meta, lambda: self.rules)

    def posts(self):
        return [(p, b) for m, p, q, b in self.g.calls if m == "POST"]


class TestEngine(Base):
    def test_follow_gate_then_dm(self):
        self.assertEqual(self.eng.handle_payload(comment()), ["public_reply", "follow_prompt"])
        paths = [p for p, _ in self.posts()]
        self.assertEqual(paths, ["/c1/replies", "/PAGE/messages"])
        self.assertEqual(self.posts()[1][1]["recipient"], {"comment_id": "c1"})
        self.assertNotIn("THE LINK", json.dumps(self.posts()[1][1]))  # link withheld until follow
        # tap without following -> reminder only
        self.assertEqual(self.eng.handle_payload(tap()), ["reminded"])
        self.assertNotIn("THE LINK", json.dumps(self.posts()[-1][1]))
        # follow, tap again -> DM delivered
        self.g.follows.add("u1")
        self.assertEqual(self.eng.handle_payload(tap()), ["dm_sent"])
        self.assertEqual(self.posts()[-1][1]["message"]["text"], "THE LINK")
        self.assertEqual(self.posts()[-1][1]["recipient"], {"id": "u1"})

    def test_no_follow_required_sends_immediately(self):
        self.rules[0].require_follow = False
        self.assertEqual(self.eng.handle_payload(comment()), ["public_reply", "dm_sent"])
        self.assertEqual(self.posts()[1][1]["message"]["text"], "THE LINK")

    def test_duplicates_keyword_and_self_ignored(self):
        self.eng.handle_payload(comment())
        n = len(self.g.calls)
        self.assertEqual(self.eng.handle_payload(comment()), ["duplicate"])
        self.assertEqual(self.eng.handle_payload(comment("c2", "hello")), [])
        self.assertEqual(self.eng.handle_payload(comment("c3", uid="IG")), [])
        self.assertEqual(self.eng.handle_payload(comment("c4", media="other")), [])
        self.assertEqual(len(self.g.calls), n)

    def test_random_reply_variants(self):
        for i in range(40):
            self.eng.handle_payload(comment(f"x{i}", uid=f"u{i}"))
        replies = {q["message"][0] for m, p, q, b in self.g.calls if p.endswith("/replies")}
        self.assertEqual(replies, {"a", "b", "c"})

    def test_api_error_is_logged_not_raised(self):
        self.cfg.graph_base = "http://127.0.0.1:1"
        self.assertEqual(self.eng.handle_payload(comment()), ["error"])
        self.assertEqual(self.store.count("error"), 1)

    def test_dry_run_sends_nothing(self):
        self.cfg.dry_run = True
        self.assertEqual(self.eng.handle_payload(comment()), ["public_reply", "follow_prompt"])
        self.assertEqual(self.posts(), [])
        self.assertEqual(len(self.meta.sent), 2)


class TestServer(Base):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.cfg, self.eng))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def tearDown(self):
        self.srv.shutdown()

    def post(self, body, secret="s3cret"):
        raw = json.dumps(body).encode()
        sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        req = urllib.request.Request(self.url, raw, {"X-Hub-Signature-256": sig}, method="POST")
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code

    def test_verification_handshake(self):
        ok = urllib.request.urlopen(f"{self.url}/?hub.mode=subscribe&hub.verify_token=vt&hub.challenge=123")
        self.assertEqual(ok.read(), b"123")
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(f"{self.url}/?hub.mode=subscribe&hub.verify_token=bad&hub.challenge=1")
        self.assertEqual(c.exception.code, 403)

    def test_signature_enforced(self):
        self.assertEqual(self.post(comment(), secret="wrong"), 401)
        self.assertEqual(self.g.calls, [])
        self.assertEqual(self.post(comment()), 200)
        self.assertEqual(len(self.posts()), 2)

    def test_verify_signature_unit(self):
        self.assertFalse(verify_signature("", b"x", "sha256=00"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
