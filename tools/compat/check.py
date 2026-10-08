"""Cross-check data/jars.json: dependencies, version ranges, declared incompatibilities,
duplicate mod ids and mixin collisions. Writes data/report.json and prints a summary.

Usage (from compat/):  python -I tools/check.py
"""
import collections
import json
import sys

sys.path.insert(0, "tools")
from analyze import MC_VERSION, NEOFORGE_VERSION, in_range  # noqa: E402

jars = json.load(open("data/jars.json"))
resolved = json.load(open("data/resolved.json"))
by_pid = {r.get("id"): r for r in resolved if r.get("id")}

provided = collections.defaultdict(list)  # mod id -> [(version, jar, nested?)]
owner = {}


def walk(j, top, nested):
    for m in j["mods"]:
        provided[m["id"]].append((m["version"], top["file"], nested))
        owner.setdefault(m["id"], top)
    for n in j.get("nested", []):
        walk(n, top, True)


for j in jars:
    walk(j, j, False)


def best_version(mid):
    vs = provided.get(mid)
    return max((v for v, _, _ in vs), key=lambda v: __import__("analyze").vkey(v)) if vs else None


issues = []


def add(level, kind, jar, text):
    issues.append({"level": level, "kind": kind, "jar": jar, "text": text})


# duplicates among top-level jars
for mid, vs in provided.items():
    tops = sorted({f for _, f, nested in vs if not nested})
    if len(tops) > 1:
        add("error", "duplicate", ", ".join(tops), f"mod id '{mid}' is provided by {len(tops)} jars")

# dependencies
for j in jars:
    for m in j["mods"]:
        for d in m["deps"]:
            did, typ, rng = d["id"], d["type"], d["range"]
            if did in ("java",):
                continue
            if did == "minecraft":
                have = MC_VERSION
            elif did in ("neoforge", "forge"):
                have = NEOFORGE_VERSION
            else:
                have = best_version(did)
            title = j.get("title") or j["file"]
            side = "" if d["side"] in ("BOTH", "", None) else f" ({d['side'].lower()} only)"
            if typ == "required":
                if have is None:
                    add("error", "missing", title, f"{m['id']} requires '{did}' {rng}{side}, which isn't in the pack")
                elif not in_range(have, rng):
                    add("error", "version", title, f"{m['id']} requires {did} {rng}{side}, the pack has {have}")
            elif typ == "optional":
                if have is not None and did not in ("minecraft", "neoforge") and not in_range(have, rng):
                    add("error", "version", title,
                        f"{m['id']} supports {did} only in {rng}{side}; the pack has {have} (NeoForge refuses to load)")
            elif typ == "incompatible":
                if have is not None and in_range(have, rng):
                    add("error", "incompatible", title,
                        f"{m['id']} declares itself incompatible with {did} {rng}{side}" + (f": {d['reason']}" if d['reason'] else ""))
            elif typ == "discouraged":
                if have is not None and in_range(have, rng):
                    add("warning", "discouraged", title,
                        f"{m['id']} discourages {did} {rng}{side}" + (f": {d['reason']}" if d['reason'] else ""))

# Modrinth-declared incompatibilities and odd required deps
for r in resolved:
    for d in r.get("deps", []):
        other = by_pid.get(d.get("project_id"))
        if d["type"] == "incompatible" and other:
            add("error", "incompatible", r["name"], f"Modrinth lists it as incompatible with {other['name']}")
        if d["type"] == "required" and other and not other.get("version"):
            add("error", "missing", r["name"], f"requires {other['name']}, which has no NeoForge 1.21.1 build")

# mixins
calls = collections.defaultdict(list)
per_class = collections.defaultdict(set)


def collect(j, top):
    for x in j.get("mixins", []):
        calls[(x["target"], x["method"])].append({**x, "jar": top.get("title") or top["file"]})
        per_class[x["target"]].add(top.get("title") or top["file"])
    for n in j.get("nested", []):
        collect(n, top)


for j in jars:
    collect(j, j)

collisions = []
for (tgt, meth), xs in calls.items():
    mods = {x["jar"] for x in xs}
    if len(mods) < 2:
        continue
    over = [x for x in xs if x["kind"] == "Overwrite"]
    if over:
        owners = {x["jar"] for x in over}
        rest = [x for x in xs if x["jar"] not in owners]
        if rest:
            # hooks at HEAD/RETURN/TAIL survive an overwrite; hooks aimed at a specific call inside it may not
            pinpoint = sorted({x["jar"] for x in rest if x["at"] not in (None, "HEAD", "RETURN", "TAIL")
                               and x["kind"] not in ("WrapMethod", "ModifyReturnValue")})
            collisions.append({"level": "high" if pinpoint else "low", "target": tgt, "method": meth,
                               "text": f"overwritten by {', '.join(sorted(owners))}; also hooked by "
                                       f"{', '.join(sorted({x['jar'] for x in rest}))}"
                                       + (f" (aimed inside the method: {', '.join(pinpoint)})" if pinpoint else " (only at its start or end)")})
    redirects = collections.defaultdict(set)
    for x in xs:
        if x["kind"] == "Redirect":
            redirects[x["at"]].add(x["jar"])
    for at, ms in redirects.items():
        if len(ms) > 1:
            collisions.append({"level": "high", "target": tgt, "method": meth,
                               "text": f"same call redirected by {', '.join(sorted(ms))} ({at})"})
    hard = {x["jar"] for x in xs if x["kind"] in ("Redirect", "ModifyConstant")}
    soft = {x["jar"] for x in xs} - hard
    if hard and soft and not over:
        collisions.append({"level": "medium", "target": tgt, "method": meth,
                           "text": f"redirect/constant change by {', '.join(sorted(hard))}; also hooked by {', '.join(sorted(soft))}"})

hot = sorted(((len(v), k, sorted(v)) for k, v in per_class.items()), reverse=True)[:40]

json.dump({"issues": issues, "collisions": collisions, "hotspots": hot}, open("data/report.json", "w"), indent=1)
for lvl in ("error", "warning"):
    xs = [i for i in issues if i["level"] == lvl]
    print(f"\n== {lvl}s: {len(xs)}")
    for i in sorted(xs, key=lambda i: (i["kind"], i["jar"])):
        print(f"  [{i['kind']}] {i['jar']}: {i['text']}")
print(f"\n== mixin collisions: {sum(c['level'] == 'high' for c in collisions)} high, {sum(c['level'] == 'medium' for c in collisions)} medium, {sum(c['level'] == 'low' for c in collisions)} low")
for c in sorted((c for c in collisions if c["level"] != "low"), key=lambda c: (c["level"] != "high", c["target"])):
    print(f"  [{c['level']}] {c['target'].rsplit('/', 1)[-1]}.{c['method']}: {c['text']}")
print("\n== most-patched classes")
for n, k, v in hot[:25]:
    print(f"  {n:3} {k.rsplit('/', 1)[-1]}")
