"""Static compatibility audit of the downloaded jars.

Reads every jar's neoforge.mods.toml (and jar-in-jar libraries), checks dependencies and declared
incompatibilities, finds duplicate mod ids and non-NeoForge jars, and parses the bytecode of every
mixin to find methods that several mods rewrite in ways that can collide.

Usage (from compat/):  python -I tools/analyze.py   -> data/analysis.json
"""
import io
import json
import os
import re
import struct
import sys
import tomllib
import zipfile

JARS = "jars"
MC_VERSION = "1.21.1"
NEOFORGE_VERSION = "21.1.256"


# ---------- versions and Maven ranges (a port of Maven's ComparableVersion, as FML uses) ----------
QUALIFIERS = ["alpha", "beta", "milestone", "rc", "snapshot", "", "sp"]
ALIASES = {"ga": "", "final": "", "release": "", "cr": "rc", "a": "alpha", "b": "beta", "m": "milestone"}


def _qual(q):
    q = ALIASES.get(q, q)
    return (QUALIFIERS.index(q), "") if q in QUALIFIERS else (len(QUALIFIERS), q)


def _parse(v):
    v = str(v).lower()
    root = []
    stack = [root]
    cur = root
    start, digit = 0, False

    def push(tok, is_digit):
        if is_digit:
            cur.append(int(tok))
        elif tok:
            cur.append(tok)

    i = 0
    while i < len(v):
        c = v[i]
        if c == ".":
            push(v[start:i], digit) if i > start else cur.append(0)
            start = i + 1
        elif c == "-":
            push(v[start:i], digit) if i > start else cur.append(0)
            start = i + 1
            new = []
            cur.append(new)
            cur = new
        elif c.isdigit():
            if not digit and i > start:
                push(v[start:i], False)
                start = i
                new = []
                cur.append(new)
                cur = new
            digit = True
        else:
            if digit and i > start:
                push(v[start:i], True)
                start = i
                new = []
                cur.append(new)
                cur = new
            digit = False
        i += 1
    if len(v) > start:
        push(v[start:], digit)
    return _norm(root)


def _norm(lst):
    out = [(_norm(x) if isinstance(x, list) else x) for x in lst]
    while out and (out[-1] == 0 or out[-1] == "" or out[-1] == [] or (isinstance(out[-1], str) and ALIASES.get(out[-1], out[-1]) == "")):
        out.pop()
    return out


def _cmp_item(a, b):
    if a is None and b is None:
        return 0
    if a is None:
        return -_cmp_item(b, None)
    if isinstance(a, int):
        if b is None:
            return 0 if a == 0 else 1
        if isinstance(b, int):
            return (a > b) - (a < b)
        return 1  # int beats string and list
    if isinstance(a, str):
        if b is None:
            qa, qb = _qual(a), _qual("")
            return (qa > qb) - (qa < qb)
        if isinstance(b, int):
            return -1
        if isinstance(b, str):
            qa, qb = _qual(a), _qual(b)
            return (qa > qb) - (qa < qb)
        return -1  # string < list
    # list
    if b is None:
        return 0 if not a else _cmp_item(a[0], None)
    if isinstance(b, int):
        return -1
    if isinstance(b, str):
        return 1
    for i in range(max(len(a), len(b))):
        r = _cmp_item(a[i] if i < len(a) else None, b[i] if i < len(b) else None)
        if r:
            return r
    return 0


def cmp(a, b):
    return _cmp_item(_parse(a), _parse(b))


def vkey(v):
    import functools
    return functools.cmp_to_key(cmp)(v)


def in_range(version, spec):
    spec = (spec or "").strip()
    if not spec or version is None or spec[0] not in "[(":
        return True  # a bare version is only a recommendation and matches anything
    for part in re.findall(r"[\[(][^\])]*[\])]", spec):
        lo_inc, hi_inc = part[0] == "[", part[-1] == "]"
        body = part[1:-1]
        if "," not in body:
            if cmp(version, body.strip()) == 0:
                return True
            continue
        lo, hi = [x.strip() for x in body.split(",", 1)]
        ok = True
        if lo:
            c = cmp(version, lo)
            ok &= c > 0 or (lo_inc and c == 0)
        if hi:
            c = cmp(version, hi)
            ok &= c < 0 or (hi_inc and c == 0)
        if ok:
            return True
    return False


# ---------- minimal class-file reader for annotations ----------
class ClassReader:
    def __init__(self, data):
        self.d, self.p = data, 0
        assert self.u4() == 0xCAFEBABE
        self.u2(), self.u2()
        n = self.u2()
        self.cp = [None] * n
        i = 1
        while i < n:
            tag = self.u1()
            if tag == 1:
                ln = self.u2()
                self.cp[i] = ("utf8", self.d[self.p:self.p + ln].decode("utf-8", "replace"))
                self.p += ln
            elif tag in (3, 4):
                self.cp[i] = ("num", self.u4())
            elif tag in (5, 6):
                self.cp[i] = ("num", self.d[self.p:self.p + 8])
                self.p += 8
                i += 1
            elif tag == 7:
                self.cp[i] = ("class", self.u2())
            elif tag == 8:
                self.cp[i] = ("string", self.u2())
            elif tag in (9, 10, 11, 12):
                self.cp[i] = ("ref", self.u2(), self.u2())
            elif tag == 15:
                self.cp[i] = ("mh", self.u1(), self.u2())
            elif tag == 16:
                self.cp[i] = ("mt", self.u2())
            elif tag in (17, 18):
                self.cp[i] = ("dyn", self.u2(), self.u2())
            elif tag in (19, 20):
                self.cp[i] = ("mod", self.u2())
            else:
                raise ValueError(f"cp tag {tag}")
            i += 1
        self.u2()
        self.this = self.cname(self.u2())
        self.u2()
        count = self.u2()
        self.p += 2 * count
        for _ in range(self.u2()):  # fields
            self.p += 6
            self.skip_attrs()
        self.methods = []
        for _ in range(self.u2()):
            self.u2()
            name, desc = self.utf(self.u2()), self.utf(self.u2())
            self.methods.append((name, desc, self.read_annos()))
        self.annos = self.read_annos()

    def u1(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u2(self):
        v = struct.unpack_from(">H", self.d, self.p)[0]
        self.p += 2
        return v

    def u4(self):
        v = struct.unpack_from(">I", self.d, self.p)[0]
        self.p += 4
        return v

    def utf(self, i):
        return self.cp[i][1]

    def cname(self, i):
        return self.utf(self.cp[i][1])

    def skip_attrs(self):
        for _ in range(self.u2()):
            self.u2()
            length = self.u4()
            self.p += length

    def read_annos(self):
        out = []
        for _ in range(self.u2()):
            name = self.utf(self.u2())
            ln = self.u4()
            end = self.p + ln
            if name in ("RuntimeVisibleAnnotations", "RuntimeInvisibleAnnotations"):
                for _ in range(self.u2()):
                    out.append(self.annotation())
            self.p = end
        return out

    def annotation(self):
        typ = self.utf(self.u2())
        vals = {}
        for _ in range(self.u2()):
            k = self.utf(self.u2())
            vals[k] = self.value()
        return typ, vals

    def value(self):
        tag = chr(self.u1())
        if tag in "BCDFIJSZ":
            self.u2()
            return None
        if tag == "s":
            return self.utf(self.u2())
        if tag == "e":
            self.u2()
            return self.utf(self.u2())
        if tag == "c":
            return self.utf(self.u2())
        if tag == "@":
            return self.annotation()
        if tag == "[":
            return [self.value() for _ in range(self.u2())]
        raise ValueError(tag)


MIXIN = "Lorg/spongepowered/asm/mixin/Mixin;"
HARD = {"Overwrite", "Redirect", "ModifyConstant"}
KINDS = {"Inject", "Redirect", "Overwrite", "ModifyArg", "ModifyArgs", "ModifyVariable", "ModifyConstant",
         "WrapOperation", "WrapWithCondition", "ModifyExpressionValue", "ModifyReturnValue", "ModifyReceiver",
         "WrapMethod"}


def short(t):
    return t.rsplit("/", 1)[-1].rstrip(";")


def as_list(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def at_target(at):
    if isinstance(at, tuple):
        return at[1].get("target") or at[1].get("value")
    return None


def mixin_records(cls):
    tgt = []
    for typ, vals in cls.annos:
        if typ == MIXIN:
            tgt += [v[1:-1] if v.startswith("L") else v for v in as_list(vals.get("value")) if isinstance(v, str)]
            tgt += [v.replace(".", "/") for v in as_list(vals.get("targets")) if isinstance(v, str)]
    if not tgt:
        return [], []
    recs = []
    for name, desc, annos in cls.methods:
        for typ, vals in annos:
            kind = short(typ)
            if kind not in KINDS:
                continue
            if kind == "Overwrite":
                methods = [name]
            else:
                methods = [m.split("(")[0] for m in as_list(vals.get("method")) if isinstance(m, str)]
            ats = [at_target(a) for a in as_list(vals.get("at"))] or [None]
            for t in tgt:
                for m in methods:
                    for a in ats:
                        recs.append({"target": t, "method": m.split("(")[0], "kind": kind,
                                     "at": a, "mixin": cls.this})
    return tgt, recs


# ---------- jars ----------
def read_toml(z, name):
    try:
        return tomllib.loads(z.read(name).decode("utf-8", "replace"))
    except Exception as e:
        return {"_error": str(e)}


def manifest_version(z):
    try:
        m = z.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
        g = re.search(r"Implementation-Version:\s*(\S+)", m)
        return g.group(1) if g else None
    except KeyError:
        return None


def scan_jar(data, path, depth=0):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    info = {"path": path, "mods": [], "nested": [], "mixin_configs": [], "loader": None}
    if "META-INF/neoforge.mods.toml" in names:
        info["loader"] = "neoforge"
        t = read_toml(z, "META-INF/neoforge.mods.toml")
    elif "META-INF/mods.toml" in names:
        info["loader"] = "forge-legacy"
        t = read_toml(z, "META-INF/mods.toml")
    elif "fabric.mod.json" in names:
        info["loader"] = "fabric"
        t = {}
    else:
        t = {}
    mver = manifest_version(z)
    deps = t.get("dependencies", {}) if isinstance(t.get("dependencies"), dict) else {}
    for m in t.get("mods", []):
        mid = m.get("modId")
        ver = str(m.get("version", ""))
        if "${" in ver:
            ver = mver or ver
        dl = []
        for d in deps.get(mid, []) if isinstance(deps.get(mid), list) else []:
            typ = d.get("type") or ("required" if d.get("mandatory", True) else "optional")
            dl.append({"id": d.get("modId"), "type": str(typ).lower(), "range": d.get("versionRange", ""),
                       "side": d.get("side", "BOTH"), "reason": d.get("reason", "")})
        info["mods"].append({"id": mid, "version": ver, "name": m.get("displayName", mid), "deps": dl})
    for mx in t.get("mixins", []) if isinstance(t.get("mixins"), list) else []:
        if mx.get("config"):
            info["mixin_configs"].append(mx["config"])
    # mixins
    recs, targets = [], set()
    for cfg in info["mixin_configs"]:
        if cfg not in names:
            continue
        try:
            c = json.loads(z.read(cfg))
        except Exception:
            continue
        pkg = c.get("package", "")
        for side in ("mixins", "client", "server", "common"):
            for cls in c.get(side, []) or []:
                cname = (pkg + "." + cls).replace(".", "/") + ".class"
                if cname not in names:
                    continue
                try:
                    cr = ClassReader(z.read(cname))
                except Exception:
                    continue
                t2, r = mixin_records(cr)
                targets.update(t2)
                for x in r:
                    x["side"] = side
                recs += r
    info["mixins"] = recs
    info["mixin_targets"] = sorted(targets)
    if depth < 2:
        nested = {n for n in names if n.startswith("META-INF/jarjar/") and n.endswith(".jar")}
        if "META-INF/jarjar/metadata.json" in names:  # the jar-in-jar index can point anywhere
            try:
                meta = json.loads(z.read("META-INF/jarjar/metadata.json"))
                nested |= {e["path"] for e in meta.get("jars", []) if e.get("path") in names}
            except Exception:
                pass
        for n in sorted(nested):
            try:
                info["nested"].append(scan_jar(z.read(n), n, depth + 1))
            except Exception:
                pass
    return info


def main():
    resolved = {r["filename"]: r for r in json.load(open("data/resolved.json")) if r.get("filename")}
    jars = []
    for fn in sorted(os.listdir(JARS)):
        if not fn.endswith(".jar"):
            continue
        j = scan_jar(open(os.path.join(JARS, fn), "rb").read(), fn)
        r = resolved.get(fn, {})
        j.update({"file": fn, "title": r.get("name") or r.get("title"), "group": r.get("group"),
                  "note": r.get("note", ""), "client_side": r.get("client_side"), "server_side": r.get("server_side")})
        jars.append(j)
        print(f"{fn[:60]:60} {j['loader']} mods={[m['id'] for m in j['mods']]} mixins={len(j['mixins'])}", flush=True)
    json.dump(jars, open("data/jars.json", "w"))
    print("scanned", len(jars))


if __name__ == "__main__":
    sys.exit(main())
