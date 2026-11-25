"""Thin client for the Meta Graph API calls CommentFlow needs.

Endpoints (see docs/META_REQUIREMENTS.md for the official sources):
  POST /{ig-comment-id}/replies            public reply to a comment
  POST /{page-id}/messages                 private reply (recipient.comment_id) or DM (recipient.id)
  GET  /{igsid}?fields=is_user_follow_business   follow check (only after the user messaged you)
"""
from . import http


class MetaClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sent = []  # record of calls in dry-run mode

    def _call(self, method, path, params=None, body=None):
        if self.cfg.dry_run and method != "GET":
            self.sent.append((method, path, params, body))
            return {"dry_run": True}
        p = {"access_token": self.cfg.page_token, **(params or {})}
        return http.request(method, f"{self.cfg.graph_base}/{path}", params=p, body=body)

    def reply_to_comment(self, comment_id, text):
        return self._call("POST", f"{comment_id}/replies", params={"message": text})

    def private_reply(self, comment_id, message):
        return self._call("POST", f"{self.cfg.page_id}/messages",
                          body={"recipient": {"comment_id": comment_id}, "message": message})

    def send_dm(self, igsid, message):
        return self._call("POST", f"{self.cfg.page_id}/messages",
                          body={"recipient": {"id": igsid}, "message": message, "messaging_type": "RESPONSE"})

    def follows_business(self, igsid):
        r = self._call("GET", igsid, params={"fields": "is_user_follow_business"})
        return bool(r.get("is_user_follow_business"))

    def media_permalink_to_id(self, permalink):
        """Resolve a post URL to a media id by paging the account's media list."""
        path = f"{self.cfg.ig_id}/media"
        params = {"fields": "id,permalink", "limit": "50"}
        for _ in range(10):
            r = self._call("GET", path, params=params)
            for m in r.get("data", []):
                if m.get("permalink", "").rstrip("/") == permalink.rstrip("/"):
                    return m["id"]
            nxt = r.get("paging", {}).get("cursors", {}).get("after")
            if not nxt:
                return None
            params = {**params, "after": nxt}
        return None
