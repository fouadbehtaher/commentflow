"""End-to-end check of both workflows inside a real n8n, against offline fake services.
Usage: python3 run_acceptance.py   (n8n on :5679 with the env from run_acceptance.sh, fakes on :9001)"""
import hashlib, hmac, json, sys, time, urllib.request, urllib.error

N8N, FAKE, SECRET = "http://127.0.0.1:5679", "http://127.0.0.1:9001", "s3cret"
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (" " + str(extra) if not cond else ""))
    if not cond:
        fails.append(name)


def get(url):
    try:
        r = urllib.request.urlopen(url); return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(path, body, secret=SECRET):
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    req = urllib.request.Request(N8N + path, raw, {"Content-Type": "application/json", "X-Hub-Signature-256": sig})
    try:
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code


def calls():
    return json.loads(get(FAKE + "/_calls")[1])


def wait_for(pred, secs=15):
    end = time.time() + secs
    while time.time() < end:
        c = calls()
        if pred(c):
            return c
        time.sleep(0.5)
    return calls()


def has(c, m, suffix):
    return [x for x in c if x["m"] == m and x["path"].split("?")[0].endswith(suffix)]


ig_comment = lambda cid, uid="u1", text="send the GUIDE please": {"object": "instagram", "entry": [{"id": "IG1", "changes": [
    {"field": "comments", "value": {"id": cid, "text": text, "from": {"id": uid, "username": "bob"}, "media": {"id": "m1"}}}]}]}
tap = lambda uid="u1": {"object": "instagram", "entry": [{"id": "IG1", "messaging": [
    {"sender": {"id": uid}, "message": {"quick_reply": {"payload": "CF_FOLLOWED:rule-ig"}}}]}]}

# verification handshake and signature enforcement
check("IG verify ok", get(N8N + "/webhook/commentflow-ig?hub.mode=subscribe&hub.verify_token=vt&hub.challenge=777") == (200, "777"))
check("IG verify bad token 403", get(N8N + "/webhook/commentflow-ig?hub.mode=subscribe&hub.verify_token=no&hub.challenge=1")[0] == 403)
check("bad signature 401", post("/webhook/commentflow-ig", ig_comment("cx"), secret="wrong") == 401)
time.sleep(1)
check("bad signature triggered nothing", calls() == [], calls())

# Instagram: comment -> public reply + follow prompt without the link
check("IG comment 200", post("/webhook/commentflow-ig", ig_comment("c1")) == 200)
c = wait_for(lambda c: has(c, "POST", "/IG1/messages") and has(c, "POST", "/events"))
pub, priv = has(c, "POST", "/c1/replies"), has(c, "POST", "/IG1/messages")
check("IG public reply", len(pub) == 1 and pub[0]["body"]["message"] == "Sent, check your DMs", pub)
check("IG private reply is follow prompt", len(priv) == 1 and priv[0]["body"]["recipient"] == {"comment_id": "c1"}
      and "THE IG LINK" not in json.dumps(priv[0]["body"]) and priv[0]["body"]["message"]["quick_replies"][0]["payload"] == "CF_FOLLOWED:rule-ig", priv)
check("IG bearer token used", priv[0]["auth"] == "Bearer igtok")

# duplicate and non-matching comments do nothing
n = len(calls())
post("/webhook/commentflow-ig", ig_comment("c1")); post("/webhook/commentflow-ig", ig_comment("c2", text="hello")); post("/webhook/commentflow-ig", ig_comment("c3", uid="IG1"))
time.sleep(3)
c = calls()
check("duplicate / keyword miss / own comment ignored", len(has(c, "POST", "/replies")) == 1 and len(has(c, "POST", "/IG1/messages")) == 1, [x["path"] for x in c[n:]])

# tap while not following -> reminder only; follow, tap again -> DM
post("/webhook/commentflow-ig", tap())
c = wait_for(lambda c: len(has(c, "POST", "/IG1/messages")) == 2)
last = has(c, "POST", "/IG1/messages")[-1]
check("reminder when not following", last["body"]["recipient"] == {"id": "u1"} and "THE IG LINK" not in json.dumps(last["body"]), last)
get(FAKE + "/_follow/u1")
post("/webhook/commentflow-ig", tap())
c = wait_for(lambda c: len(has(c, "POST", "/IG1/messages")) == 3)
last = has(c, "POST", "/IG1/messages")[-1]
check("DM delivered after follow", last["body"]["message"]["text"] == "THE IG LINK", last)

# Facebook
fb = lambda cid, uid="f1": {"object": "page", "entry": [{"id": "PAGE1", "changes": [{"field": "feed", "value": {
    "item": "comment", "verb": "add", "comment_id": cid, "post_id": "PAGE1_555", "message": "hi", "from": {"id": uid, "name": "Sam"}}}]}]}
check("FB comment 200", post("/webhook/commentflow-fb", fb("fc1")) == 200)
c = wait_for(lambda c: has(c, "POST", "/PAGE1/messages"))
check("FB public reply", len(has(c, "POST", "/fc1/comments")) == 1)
fm = has(c, "POST", "/PAGE1/messages")
check("FB private reply with link", len(fm) == 1 and fm[0]["body"]["recipient"] == {"comment_id": "fc1"}
      and fm[0]["body"]["message"]["text"] == "THE FB LINK" and fm[0]["auth"] == "Bearer pagetok", fm)
post("/webhook/commentflow-fb", fb("fc2", uid="PAGE1")); time.sleep(2)
check("FB own comment ignored", len(has(calls(), "POST", "/PAGE1/messages")) == 1)
n = len(calls())
gated = {"object": "page", "entry": [{"id": "PAGE1", "changes": [{"field": "feed", "value": {
    "item": "comment", "verb": "add", "comment_id": "fc3", "post_id": "PAGE1_777", "message": "hi", "from": {"id": "f2", "name": "Al"}}}]}]}
post("/webhook/commentflow-fb", gated)
c = wait_for(lambda c: [x for x in c if x["path"].endswith("/events") and "blocked_require_follow" in json.dumps(x["body"])])
check("FB require_follow fails closed (logged, nothing sent)", len([x for x in c[n:] if x["path"].split("?")[0].endswith(("/fc3/comments", "/PAGE1/messages"))]) == 0
      and any("blocked_require_follow" in json.dumps(x["body"]) for x in c[n:]), [x["path"] for x in c[n:]])
print("\nFAILED: %s" % fails if fails else "\nALL PASSED")
sys.exit(1 if fails else 0)
