"""Generates the two n8n workflow files from src/*.js. Run: python3 build.py"""
import json, pathlib, uuid

SRC = pathlib.Path(__file__).parent / "src"
COMMON = (SRC / "common.js").read_text()


def js(name):
    return (SRC / name).read_text().replace("//@@common", COMMON)


class WF:
    def __init__(self, name):
        self.name, self.nodes, self.conns, self.x = name, [], {}, 0

    def add(self, name, type_, params, ver=1, pos=None, **extra):
        n = {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, self.name + name)),
             "name": name, "type": type_, "typeVersion": ver, "position": pos or [self.x, 300]}
        n.update(extra)
        self.nodes.append(n)
        self.x += 260
        return name

    def link(self, a, b, out=0):
        self.conns.setdefault(a, {"main": []})
        m = self.conns[a]["main"]
        while len(m) <= out:
            m.append([])
        m[out].append({"node": b, "type": "main", "index": 0})

    def json(self):
        return {"name": self.name, "nodes": self.nodes, "connections": self.conns,
                "active": False, "settings": {"executionOrder": "v1"}, "pinData": {}}


def code(w, name, file, pos=None):
    return w.add(name, "n8n-nodes-base.code", {"jsCode": js(file)}, 2, pos)


def iff(w, name, expr, pos=None):
    return w.add(name, "n8n-nodes-base.if", {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
        "conditions": [{"id": "c1", "leftValue": expr, "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}, 2, pos)


def respond(w, name, body, code_="200", pos=None):
    return w.add(name, "n8n-nodes-base.respondToWebhook",
                 {"respondWith": "text", "responseBody": body,
                  "options": {"responseCode": code_}}, 1.1, pos)


def http(w, name, method, url, token_env, body=None, headers=None, pos=None, **extra):
    p = {"method": method, "url": url, "options": {}}
    hs = [{"name": "Authorization", "value": f"=Bearer {{{{ $env.{token_env} }}}}"}] if token_env else []
    hs += headers or []
    if hs:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": hs}
    if body is not None:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body
    return w.add(name, "n8n-nodes-base.httpRequest", p, 4.2, pos, **extra)


def entry(w, platform_path):
    """Verification GET + signed POST up to the 'Split events' node. Returns last node name."""
    g = w.add("Verify (GET)", "n8n-nodes-base.webhook",
              {"httpMethod": "GET", "path": platform_path, "responseMode": "responseNode", "options": {}}, 2,
              [0, 100], webhookId=str(uuid.uuid5(uuid.NAMESPACE_DNS, platform_path + "get")))
    c = code(w, "Challenge", "challenge.js", [260, 100])
    r = respond(w, "Respond challenge", "={{ $json.challenge }}", "={{ $json.ok ? 200 : 403 }}", [520, 100])
    w.link(g, c); w.link(c, r)
    w.x = 0
    p = w.add("Meta events (POST)", "n8n-nodes-base.webhook",
              {"httpMethod": "POST", "path": platform_path, "responseMode": "responseNode",
               "options": {"rawBody": True}}, 2, [0, 300],
              webhookId=str(uuid.uuid5(uuid.NAMESPACE_DNS, platform_path + "post")))
    w.x = 260
    v = code(w, "Verify signature", "verify.js")
    i = iff(w, "Signature ok", "={{ $json.ok }}")
    ok = respond(w, "OK 200", "ok", "200", [780, 200])
    bad = respond(w, "Unauthorized 401", "unauthorized", "401", [780, 420])
    w.x = 1040
    return p, v, i, ok, bad


SB = "={{ $env.SUPABASE_URL }}/rest/v1/"
SBH = [{"name": "apikey", "value": "={{ $env.SUPABASE_SERVICE_KEY }}"}, {"name": "Prefer", "value": "return=minimal"}]
NOTION_H = [{"name": "Notion-Version", "value": "2022-06-28"}]


def ig():
    w = WF("CommentFlow - Instagram")
    p, v, i, ok, bad = entry(w, "commentflow-ig")
    w.link(p, v); w.link(v, i); w.link(i, ok, 0); w.link(i, bad, 1)
    s = code(w, "Split events", "split_ig.js", [1040, 200])
    w.link(ok, s)
    isc = iff(w, "Is comment", "={{ $json.kind === 'comment' }}", [1300, 200])
    w.link(s, isc)
    # comment branch
    perm = http(w, "Media permalink", "GET",
                "={{ $env.IG_GRAPH_BASE }}/{{ $json.media_id }}?fields=permalink", "IG_ACCESS_TOKEN",
                pos=[1560, 100], onError="continueRegularOutput")
    notion = http(w, "Notion rules", "POST",
                  "={{ $env.NOTION_BASE }}/databases/{{ $env.NOTION_DATABASE_ID }}/query", "NOTION_TOKEN",
                  body="={{ { page_size: 100 } }}", headers=NOTION_H, pos=[1820, 100])
    m = code(w, "Match rule", "match_ig.js", [2080, 100])
    claim = http(w, "Claim comment", "POST", SB + "comments?on_conflict=comment_id", None,
                 body="={{ { comment_id: $json.comment_id, igsid: $json.igsid, username: $json.username, rule_id: $json.rule_id } }}",
                 headers=SBH[:1] + [{"name": "Prefer", "value": "resolution=ignore-duplicates,return=representation"}],
                 pos=[2340, 100])
    pub = http(w, "Public reply", "POST", "={{ $env.IG_GRAPH_BASE }}/{{ $('Match rule').item.json.comment_id }}/replies",
               "IG_ACCESS_TOKEN", body="={{ { message: $('Match rule').item.json.reply } }}", pos=[2600, 100],
               onError="continueRegularOutput")
    priv = http(w, "Private reply", "POST", "={{ $env.IG_GRAPH_BASE }}/{{ $env.IG_ID }}/messages", "IG_ACCESS_TOKEN",
                body="={{ { recipient: { comment_id: $('Match rule').item.json.comment_id }, message: $('Match rule').item.json.private_body } }}",
                pos=[2860, 100], onError="continueRegularOutput")
    log1 = http(w, "Log comment event", "POST", SB + "events", None,
                body="={{ { kind: $('Match rule').item.json.require_follow ? 'follow_prompt' : 'dm_sent', comment_id: $('Match rule').item.json.comment_id, igsid: $('Match rule').item.json.igsid, username: $('Match rule').item.json.username, rule_id: $('Match rule').item.json.rule_id, detail: $json.error ? JSON.stringify($json.error).slice(0, 300) : '' } }}",
                headers=SBH, pos=[3120, 100])
    for a, b in [(perm, notion), (notion, m), (m, claim), (claim, pub), (pub, priv), (priv, log1)]:
        w.link(a, b)
    w.link(isc, perm, 0)
    # tap branch
    page = http(w, "Notion rule page", "GET", "={{ $env.NOTION_BASE }}/pages/{{ $json.rule_id }}", "NOTION_TOKEN",
                headers=NOTION_H, pos=[1560, 420])
    tr = code(w, "Tap rule", "tap_rule.js", [1820, 420])
    fc = http(w, "Follow check", "GET", "={{ $env.IG_GRAPH_BASE }}/{{ $json.igsid }}?fields=is_user_follow_business",
              "IG_ACCESS_TOKEN", pos=[2080, 420], onError="continueRegularOutput")
    d = code(w, "Decide", "follow_decide.js", [2340, 420])
    dm = http(w, "Send DM", "POST", "={{ $env.IG_GRAPH_BASE }}/{{ $env.IG_ID }}/messages", "IG_ACCESS_TOKEN",
              body="={{ { recipient: { id: $json.igsid }, message: $json.dm } }}", pos=[2600, 420],
              onError="continueRegularOutput")
    log2 = http(w, "Log tap event", "POST", SB + "events", None,
                body="={{ { kind: $('Decide').item.json.log_kind, igsid: $('Decide').item.json.igsid, rule_id: $('Decide').item.json.rule_id } }}",
                headers=SBH, pos=[2860, 420])
    w.link(isc, page, 1)
    for a, b in [(page, tr), (tr, fc), (fc, d), (d, dm), (dm, log2)]:
        w.link(a, b)
    return w


def fb():
    w = WF("CommentFlow - Facebook")
    p, v, i, ok, bad = entry(w, "commentflow-fb")
    w.link(p, v); w.link(v, i); w.link(i, ok, 0); w.link(i, bad, 1)
    s = code(w, "Split events", "split_fb.js", [1040, 200])
    w.link(ok, s)
    notion = http(w, "Notion rules", "POST",
                  "={{ $env.NOTION_BASE }}/databases/{{ $env.NOTION_DATABASE_ID }}/query", "NOTION_TOKEN",
                  body="={{ { page_size: 100 } }}", headers=NOTION_H, pos=[1300, 200])
    m = code(w, "Match rule", "match_fb.js", [1560, 200])
    claim = http(w, "Claim comment", "POST", SB + "comments?on_conflict=comment_id", None,
                 body="={{ { comment_id: $json.comment_id, igsid: $json.igsid, username: $json.username, rule_id: $json.rule_id } }}",
                 headers=SBH[:1] + [{"name": "Prefer", "value": "resolution=ignore-duplicates,return=representation"}],
                 pos=[1820, 200])
    pub = http(w, "Public reply", "POST", "={{ $env.GRAPH_BASE }}/{{ $('Match rule').item.json.comment_id }}/comments",
               "PAGE_ACCESS_TOKEN", body="={{ { message: $('Match rule').item.json.reply } }}", pos=[2080, 200],
               onError="continueRegularOutput")
    priv = http(w, "Private reply", "POST", "={{ $env.GRAPH_BASE }}/{{ $env.FB_PAGE_ID }}/messages", "PAGE_ACCESS_TOKEN",
                body="={{ { recipient: { comment_id: $('Match rule').item.json.comment_id }, message: $('Match rule').item.json.private_body } }}",
                pos=[2340, 200], onError="continueRegularOutput")
    log = http(w, "Log event", "POST", SB + "events", None,
               body="={{ { kind: 'dm_sent', comment_id: $('Match rule').item.json.comment_id, igsid: $('Match rule').item.json.igsid, username: $('Match rule').item.json.username, rule_id: $('Match rule').item.json.rule_id, detail: $json.error ? JSON.stringify($json.error).slice(0, 250) : '' } }}",
               headers=SBH, pos=[2600, 200])
    en = iff(w, "Campaign enabled", "={{ !$json.require_follow }}", [1690, 200])
    blocked = http(w, "Log blocked (follow required)", "POST", SB + "events", None,
                   body="={{ { kind: 'blocked_require_follow', comment_id: $json.comment_id, igsid: $json.igsid, username: $json.username, rule_id: $json.rule_id, detail: 'Facebook has no documented follow check; nothing was sent' } }}",
                   headers=SBH, pos=[1950, 420])
    for a, b in [(s, notion), (notion, m), (m, en), (claim, pub), (pub, priv), (priv, log)]:
        w.link(a, b)
    w.link(en, claim, 0); w.link(en, blocked, 1)
    return w


if __name__ == "__main__":
    out = pathlib.Path(__file__).parent / "workflows"
    out.mkdir(exist_ok=True)
    for n, f in [("commentflow-instagram.json", ig()), ("commentflow-facebook.json", fb())]:
        (out / n).write_text(json.dumps(f.json(), indent=2, ensure_ascii=False))
        print("wrote", n)
