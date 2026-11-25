"""Credential-based variant (private, not the published workflows).
Reads workflows/*.json and writes workflows_cred/*.json:
 - Graph / Notion / Supabase tokens move out of $env into n8n Header Auth credentials.
 - Non-secret settings (base URLs, IG id, page id, Notion DB id, Supabase URL) move into one 'Config' node.
 - Only META_APP_SECRET and WEBHOOK_VERIFY_TOKEN stay in the server environment (Code nodes cannot read credentials).
Usage: python3 build_private.py [--test-config] [--config FILE --strict --out DIR]   (--test-config writes to /tmp/workflows_cred with fake local URLs)"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent
TEST = "--test-config" in sys.argv
STRICT = "--strict" in sys.argv   # fail closed: refuse to write workflows while any setting is missing or a placeholder


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


OUT = pathlib.Path(arg("--out")) if arg("--out") else (pathlib.Path("/tmp/workflows_cred") if TEST else HERE / "workflows_cred")
CFG = ["IG_GRAPH_BASE", "GRAPH_BASE", "NOTION_BASE", "NOTION_DATABASE_ID", "SUPABASE_URL", "IG_ID", "FB_PAGE_ID"]
DEFAULTS = {"IG_GRAPH_BASE": "https://graph.instagram.com/v21.0", "GRAPH_BASE": "https://graph.facebook.com/v21.0",
            "NOTION_BASE": "https://api.notion.com/v1", "NOTION_DATABASE_ID": "PUT_NOTION_DATABASE_ID",
            "SUPABASE_URL": "https://PUT_PROJECT.supabase.co", "IG_ID": "PUT_IG_ID", "FB_PAGE_ID": "PUT_PAGE_ID"}
TEST_VALUES = {"IG_GRAPH_BASE": "http://127.0.0.1:9001/ig", "GRAPH_BASE": "http://127.0.0.1:9001/fb",
               "NOTION_BASE": "http://127.0.0.1:9001/notion", "NOTION_DATABASE_ID": "db1",
               "SUPABASE_URL": "http://127.0.0.1:9001/sb", "IG_ID": "IG1", "FB_PAGE_ID": "PAGE1"}
CRED = {"IG_ACCESS_TOKEN": "CommentFlow IG token", "PAGE_ACCESS_TOKEN": "CommentFlow Page token",
        "NOTION_TOKEN": "CommentFlow Notion token", "SUPABASE_SERVICE_KEY": "CommentFlow Supabase key"}
CRED_IDS = {"CommentFlow IG token": "cfIgToken00000001", "CommentFlow Page token": "cfPageToken000001",
            "CommentFlow Notion token": "cfNotionToken0001", "CommentFlow Supabase key": "cfSupabaseKey0001"}
CFG_REF = "$('Config').first().json."


def swap(s):
    for k in CFG:
        s = s.replace("$env." + k, CFG_REF + k)
    return s


def walk(o):
    if isinstance(o, str):
        return swap(o)
    if isinstance(o, list):
        return [walk(x) for x in o]
    if isinstance(o, dict):
        return {k: walk(v) for k, v in o.items()}
    return o


def convert(wf, cfg):
    wf = walk(wf)
    for n in wf["nodes"]:
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        hs = n["parameters"].get("headerParameters", {}).get("parameters", [])
        keep, cred = [], None
        for h in hs:
            m = re.search(r"\$env\.(\w+)", h["value"])
            if m and m.group(1) in CRED:
                cred = CRED[m.group(1)]
            else:
                keep.append(h)
        if cred:
            n["parameters"]["authentication"] = "genericCredentialType"
            n["parameters"]["genericAuthType"] = "httpHeaderAuth"
            n["credentials"] = {"httpHeaderAuth": {"id": CRED_IDS[cred], "name": cred}}
        if keep:
            n["parameters"]["headerParameters"]["parameters"] = keep
        else:
            n["parameters"].pop("sendHeaders", None); n["parameters"].pop("headerParameters", None)
    # Config node after 'Signature ok' true branch, before 'Split events'
    assigns = [{"id": f"cfg{i}", "name": k, "value": cfg[k], "type": "string"} for i, k in enumerate(CFG)]
    cn = {"parameters": {"assignments": {"assignments": assigns}, "includeOtherFields": True, "options": {}},
          "id": "c0f1a000-0000-4000-8000-000000000001", "name": "Config", "type": "n8n-nodes-base.set",
          "typeVersion": 3.4, "position": [910, 120]}
    wf["nodes"].append(cn)
    ok = wf["connections"]["OK 200"]["main"][0]
    assert ok == [{"node": "Split events", "type": "main", "index": 0}], ok
    wf["connections"]["OK 200"]["main"][0] = [{"node": "Config", "type": "main", "index": 0}]
    wf["connections"]["Config"] = {"main": [[{"node": "Split events", "type": "main", "index": 0}]]}
    wf["name"] += " (credentials)"
    return wf


def load_config(path):
    cfg = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); cfg[k.strip()] = v.strip().strip('"')
    return cfg


CONFIG = DEFAULTS
if arg("--config"):
    CONFIG = {**DEFAULTS, **load_config(arg("--config"))}
if STRICT and not TEST:
    bad = [k for k in CFG if not CONFIG.get(k) or "PUT_" in CONFIG[k] or CONFIG[k] == DEFAULTS[k] and k in ("NOTION_DATABASE_ID", "SUPABASE_URL", "IG_ID", "FB_PAGE_ID")]
    if bad:
        print("refusing to build: missing or placeholder settings:", ", ".join(bad), file=sys.stderr)
        sys.exit(3)
OUT.mkdir(parents=True, exist_ok=True)
for name in ["commentflow-instagram.json", "commentflow-facebook.json"]:
    wf = json.loads((HERE / "workflows" / name).read_text())
    out = convert(wf, TEST_VALUES if TEST else CONFIG)
    (OUT / name).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    left = sorted(set(re.findall(r"\$env\.(\w+)", json.dumps(out))))
    print(name, "remaining $env:", left)
