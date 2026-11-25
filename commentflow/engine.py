import json
import random

from .rules import Rule

PAYLOAD_PREFIX = "CF_FOLLOWED:"


def _follow_prompt(rule_id, first=True):
    text = ("Thanks for commenting! Follow this account first, then tap the button and I'll send it."
            if first else
            "I can't see the follow yet. Follow the account, wait a few seconds, then tap again.")
    return {"text": text,
            "quick_replies": [{"content_type": "text", "title": "I followed",
                               "payload": PAYLOAD_PREFIX + rule_id}]}


class Engine:
    def __init__(self, cfg, store, meta, get_rules, rng=random):
        self.cfg, self.store, self.meta, self.get_rules, self.rng = cfg, store, meta, get_rules, rng

    def _rule(self, rule_id):
        return next((r for r in self.get_rules() if r.id == rule_id), None)

    def handle_payload(self, body):
        """Process a webhook payload dict. Returns list of action names (for tests/logs)."""
        actions = []
        for entry in body.get("entry", []):
            for ch in entry.get("changes", []):
                if ch.get("field") == "comments":
                    actions += self.on_comment(ch["value"])
            for ev in entry.get("messaging", []):
                actions += self.on_message(ev)
        return actions

    def on_comment(self, v):
        cid, text = v.get("id"), v.get("text", "")
        sender = v.get("from", {}) or {}
        igsid, user = sender.get("id", ""), sender.get("username", "")
        media_id = (v.get("media") or {}).get("id", "")
        if not cid or igsid == self.cfg.ig_id:
            return []  # ignore our own replies (prevents loops)
        rule = next((r for r in self.get_rules() if r.matches(media_id, text)), None)
        if not rule:
            return []
        if not self.store.claim_comment(cid, igsid, user, rule.id):
            return ["duplicate"]
        out = []
        try:
            reply = rule.pick_reply(self.rng)
            if reply:
                self.meta.reply_to_comment(cid, reply)
                self.store.log("public_reply", cid, igsid, user, rule.id, reply)
                out.append("public_reply")
            if rule.require_follow:
                self.meta.private_reply(cid, _follow_prompt(rule.id))
                self.store.log("follow_missing", cid, igsid, user, rule.id, "prompted")
                out.append("follow_prompt")
            else:
                self.meta.private_reply(cid, {"text": rule.dm_text})
                self.store.log("dm_sent", cid, igsid, user, rule.id)
                out.append("dm_sent")
        except Exception as e:  # keep webhook handler alive; log for review
            self.store.log("error", cid, igsid, user, rule.id, str(e)[:300])
            out.append("error")
        return out

    def on_message(self, ev):
        igsid = (ev.get("sender") or {}).get("id", "")
        if igsid == self.cfg.ig_id:
            return []
        payload = ((ev.get("message") or {}).get("quick_reply") or {}).get("payload") \
            or (ev.get("postback") or {}).get("payload") or ""
        if not payload.startswith(PAYLOAD_PREFIX):
            return []
        rule = self._rule(payload[len(PAYLOAD_PREFIX):])
        if not rule:
            return []
        try:
            if self.meta.follows_business(igsid):
                self.meta.send_dm(igsid, {"text": rule.dm_text})
                self.store.log("follow_ok", igsid=igsid, rule_id=rule.id)
                self.store.log("dm_sent", igsid=igsid, rule_id=rule.id)
                return ["dm_sent"]
            self.meta.send_dm(igsid, _follow_prompt(rule.id, first=False))
            self.store.log("follow_missing", igsid=igsid, rule_id=rule.id, detail="reminded")
            return ["reminded"]
        except Exception as e:
            self.store.log("error", igsid=igsid, rule_id=rule.id, detail=str(e)[:300])
            return ["error"]
