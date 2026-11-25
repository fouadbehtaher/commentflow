"""Rules: one per post. Loaded from a JSON file or from a Notion database."""
import json
import random
from dataclasses import dataclass, field
from . import http


@dataclass
class Rule:
    id: str
    media_id: str = ""
    permalink: str = ""
    keyword: str = ""             # empty = any comment triggers
    replies: list = field(default_factory=list)   # public comment reply variants
    dm_text: str = ""
    require_follow: bool = False
    active: bool = True

    def matches(self, media_id, text):
        if not self.active or not self.media_id or self.media_id != media_id:
            return False
        return not self.keyword or self.keyword.lower() in (text or "").lower()

    def pick_reply(self, rng=random):
        return rng.choice(self.replies) if self.replies else ""


def load_file(path):
    with open(path, encoding="utf-8") as f:
        return [Rule(**r) for r in json.load(f)]


NOTION_VERSION = "2022-06-28"


def _txt(prop):
    if not prop:
        return ""
    t = prop.get("title") or prop.get("rich_text") or []
    return "".join(x.get("plain_text", "") for x in t)


def load_notion(token, database_id):
    """Notion database columns: Name (title), Post URL (url), Media ID (text),
    Keyword (text), Reply 1/2/3 (text), DM (text), Require follow (checkbox), Active (checkbox)."""
    h = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    rules, cursor = [], None
    while True:
        body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        r = http.request("POST", f"https://api.notion.com/v1/databases/{database_id}/query",
                         body=body, headers=h)
        for page in r["results"]:
            p = page["properties"]
            rules.append(Rule(
                id=page["id"],
                media_id=_txt(p.get("Media ID")),
                permalink=(p.get("Post URL") or {}).get("url") or "",
                keyword=_txt(p.get("Keyword")),
                replies=[x for x in (_txt(p.get(f"Reply {i}")) for i in (1, 2, 3)) if x],
                dm_text=_txt(p.get("DM")),
                require_follow=bool((p.get("Require follow") or {}).get("checkbox")),
                active=(p.get("Active") or {"checkbox": True}).get("checkbox", True),
            ))
        if not r.get("has_more"):
            return rules
        cursor = r["next_cursor"]
