"""Download every resolved jar into jars/ (verifying Modrinth sha1 when known)."""
import hashlib, json, os, sys, urllib.request
UA = {"User-Agent": "RadKayo/remnant-compat-audit (github.com/RadKayo/remnant)"}
rows = json.load(open("data/resolved.json"))
ok = bad = 0
for r in rows:
    if not r.get("url"):
        continue
    dest = os.path.join("jars", r["filename"])
    if os.path.exists(dest):
        ok += 1
        continue
    try:
        with urllib.request.urlopen(urllib.request.Request(r["url"], headers=UA), timeout=120) as resp:
            data = resp.read()
        if r.get("sha1") and hashlib.sha1(data).hexdigest() != r["sha1"]:
            print("sha1 mismatch", r["name"]); bad += 1; continue
        open(dest, "wb").write(data); ok += 1
    except Exception as e:
        print("failed", r["name"], e); bad += 1
print("downloaded", ok, "failed", bad)
