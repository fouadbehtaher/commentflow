"""Event log and dedupe. SQLite by default; Supabase (PostgREST) mirror optional."""
import sqlite3
import time
from . import http

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,          -- comment | public_reply | dm_sent | follow_ok | follow_missing | error
  comment_id TEXT,
  igsid TEXT,
  username TEXT,
  rule_id TEXT,
  detail TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_comment ON events(comment_id) WHERE kind = 'comment';
"""


class Store:
    def __init__(self, path, supabase_url="", supabase_key=""):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.sb = (supabase_url.rstrip("/"), supabase_key) if supabase_url and supabase_key else None

    def claim_comment(self, comment_id, igsid, username, rule_id):
        """Return True the first time a comment is seen (webhooks can repeat)."""
        try:
            self.db.execute(
                "INSERT INTO events(ts,kind,comment_id,igsid,username,rule_id) VALUES(?,?,?,?,?,?)",
                (time.time(), "comment", comment_id, igsid, username, rule_id))
            self.db.commit()
        except sqlite3.IntegrityError:
            return False
        self._mirror("comment", comment_id, igsid, username, rule_id, "")
        return True

    def log(self, kind, comment_id=None, igsid=None, username=None, rule_id=None, detail=""):
        self.db.execute(
            "INSERT INTO events(ts,kind,comment_id,igsid,username,rule_id,detail) VALUES(?,?,?,?,?,?,?)",
            (time.time(), kind, comment_id, igsid, username, rule_id, detail))
        self.db.commit()
        self._mirror(kind, comment_id, igsid, username, rule_id, detail)

    def count(self, kind, igsid=None, rule_id=None):
        q, a = "SELECT COUNT(*) FROM events WHERE kind=?", [kind]
        if igsid:
            q += " AND igsid=?"; a.append(igsid)
        if rule_id:
            q += " AND rule_id=?"; a.append(rule_id)
        return self.db.execute(q, a).fetchone()[0]

    def _mirror(self, kind, comment_id, igsid, username, rule_id, detail):
        if not self.sb:
            return
        url, key = self.sb
        try:
            http.request("POST", f"{url}/rest/v1/events",
                         body={"kind": kind, "comment_id": comment_id, "igsid": igsid,
                               "username": username, "rule_id": rule_id, "detail": detail},
                         headers={"apikey": key, "Authorization": f"Bearer {key}",
                                  "Prefer": "return=minimal"})
        except http.ApiError:
            pass  # local log is the source of truth; never fail a webhook on the mirror
