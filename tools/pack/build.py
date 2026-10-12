"""Build Remnant's packwiz metadata from the resolved mod list.

python tools/pack/build.py <resolved.json> <jars dir>      (from the repo root, then: packwiz refresh)

- mods/<slug>.pw.toml for every resolved mod: Modrinth files by URL and sha512, CurseForge files by
  project and file id (the installer fetches them through CurseForge, as its terms require).
- Client-only mods (Modrinth marks them server-unsupported: rendering, HUD, tooltips) get side = "client".
  Everything else installs on both sides: worldgen and library mods that Modrinth calls server-only still
  register content, and the Oct 8 audit booted clients with all of them.
- Copies our own content into kubejs/: the Remming coin textures (over Create: Numismatics) and the
  datapacks in datapacks/ (KubeJS loads kubejs/data as a datapack and kubejs/assets as a resource pack).
"""
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def toml_str(s):
    return json.dumps(s, ensure_ascii=False)


# Server-only by our choice: pure worldgen with no blocks, items or network code, and blocked from automatic
# download by its author, so players are never asked to fetch it. The server gets the jar placed by hand once.
SERVER_ONLY = {"Ember's Ancient Remnants"}
# Client-only by our choice: Epic Tweaks applies a client mixin even on a dedicated server, which breaks Epic Fight
CLIENT_ONLY = {"Epic Tweaks"}


def metafile(r, jars):
    side = "server" if r["name"] in SERVER_ONLY else \
        "client" if r["name"] in CLIENT_ONLY or r.get("server_side") == "unsupported" else "both"
    lines = [f"name = {toml_str(r['name'])}", f"filename = {toml_str(r['filename'])}", f"side = {toml_str(side)}", ""]
    if r["source"] == "modrinth":
        lines += ["[download]", f"url = {toml_str(r['url'])}", 'hash-format = "sha512"', f"hash = {toml_str(r['sha512'])}",
                  "", "[update]", "[update.modrinth]", f"mod-id = {toml_str(r['id'])}", f"version = {toml_str(r['version_id'])}"]
        slug = r["slug"]
    else:
        data = open(os.path.join(jars, r["filename"]), "rb").read()
        lines += ["[download]", 'hash-format = "sha1"', f"hash = {toml_str(hashlib.sha1(data).hexdigest())}",
                  'mode = "metadata:curseforge"', "", "[update]", "[update.curseforge]",
                  f"file-id = {int(r['cf_file'])}", f"project-id = {int(r['cf_project'])}"]
        slug = slugify(r["name"])
    return slug, "\n".join(lines) + "\n", side


def main():
    resolved, jars = sys.argv[1], sys.argv[2]
    rows = [r for r in json.load(open(resolved)) if r.get("filename")]
    mods = os.path.join(ROOT, "mods")
    shutil.rmtree(mods, ignore_errors=True)
    os.makedirs(mods)
    sides = {"both": 0, "client": 0, "server": 0}
    for r in rows:
        slug, body, side = metafile(r, jars)
        with open(os.path.join(mods, f"{slug}.pw.toml"), "w") as f:
            f.write(body)
        sides[side] += 1

    kjs = os.path.join(ROOT, "kubejs")
    coins = os.path.join(kjs, "assets", "numismatics", "textures", "item", "coin")
    shutil.rmtree(os.path.join(kjs, "assets", "numismatics"), ignore_errors=True)
    os.makedirs(coins)
    for fn in os.listdir(os.path.join(ROOT, "branding", "out", "coins")):
        shutil.copy(os.path.join(ROOT, "branding", "out", "coins", fn), coins)
    data = os.path.join(kjs, "data")
    shutil.rmtree(data, ignore_errors=True)
    for pack in sorted(os.listdir(os.path.join(ROOT, "datapacks"))):
        src = os.path.join(ROOT, "datapacks", pack, "data")
        if os.path.isdir(src):
            shutil.copytree(src, data, dirs_exist_ok=True)
    print(f"{len(rows)} mods ({sides['both']} both sides, {sides['client']} client only, {sides['server']} server only); "
          "coins and datapacks copied")


if __name__ == "__main__":
    main()
