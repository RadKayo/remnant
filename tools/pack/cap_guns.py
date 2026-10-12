"""Write datapacks/remnant_guns: every gun projectile capped at MAX blocks of travel.

python tools/pack/cap_guns.py <create-gunsmithing.jar> <ntgl.jar> [...]     (from the repo root)

A fast projectile checks every block on its path each tick, and on a server that loads any chunk in the
way on the spot. A shot toward the horizon can drag the server thread through a chain of chunk loads,
which is the likely way ewewukek's Musket Mod froze Dragonfyre. Out of the box a Gunsmithing gatling
round flies 9,000 blocks. Travel is speed (blocks per tick) times life (ticks), so life is lowered to
MAX / speed. Weapons, ammo and projectile definitions are all covered; thrown items are skipped, because
their "life" is the fuse. The outputs are full copies of the mods' files with only "life" changed, so
re-run this whenever either mod updates.
"""
import json
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "datapacks", "remnant_guns")
MAX = 160  # inside the area that's loaded around the shooter


def cap(p):
    speed = float(p.get("speed", 1.0)) or 1.0
    limit = max(1, int(MAX / speed))
    if p.get("life", 0) > limit:
        p["life"] = limit
        return 1
    return 0


def walk(obj):
    n = 0
    if isinstance(obj, dict):
        if isinstance(obj.get("projectile"), dict) and "life" in obj["projectile"]:
            n += cap(obj["projectile"])
        for v in obj.values():
            n += walk(v)
    elif isinstance(obj, list):
        for v in obj:
            n += walk(v)
    return n


def main():
    shutil.rmtree(os.path.join(OUT, "data"), ignore_errors=True)
    total = files = 0
    for jar in sys.argv[1:]:
        z = zipfile.ZipFile(jar)
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) != 4 or parts[0] != "data" or not name.endswith(".json"):
                continue
            d = json.loads(z.read(name))
            if parts[2] == "weapons":
                if d.get("general", {}).get("action") == "ntgl:throw":
                    continue
                n = walk(d)
            elif parts[2] in ("ammo", "projectiles"):
                n = cap(d) if "life" in d else 0
            else:
                continue
            if n:
                out = os.path.join(OUT, name)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "w") as f:
                    json.dump(d, f, indent=1)
                total, files = total + n, files + 1
    print(f"capped {total} projectiles in {files} files at {MAX} blocks")


if __name__ == "__main__":
    main()
