"""Writes n8n credentials JSON (Header Auth) from a secrets env file, for `n8n import:credentials`.
Usage: python3 make_credentials.py secrets.env > credentials.json   (run on the server; never commit the output)
secrets.env keys: IG_ACCESS_TOKEN PAGE_ACCESS_TOKEN NOTION_TOKEN SUPABASE_SERVICE_KEY"""
import json, sys
env = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
spec = [("cfIgToken00000001", "CommentFlow IG token", "Authorization", "Bearer ", "IG_ACCESS_TOKEN"),
        ("cfPageToken000001", "CommentFlow Page token", "Authorization", "Bearer ", "PAGE_ACCESS_TOKEN"),
        ("cfNotionToken0001", "CommentFlow Notion token", "Authorization", "Bearer ", "NOTION_TOKEN"),
        ("cfSupabaseKey0001", "CommentFlow Supabase key", "apikey", "", "SUPABASE_SERVICE_KEY")]
out = []
for cid, name, hdr, prefix, key in spec:
    if not env.get(key):
        print(f"missing {key} in {sys.argv[1]}", file=sys.stderr); sys.exit(2)
    out.append({"id": cid, "name": name, "type": "httpHeaderAuth", "data": {"name": hdr, "value": prefix + env[key]}})
print(json.dumps(out, indent=2))
