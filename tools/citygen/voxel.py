"""Voxel grid with a block-state palette, and writers for WorldEdit .schem and vanilla structure .nbt files.

Index 0 is structure_void: "leave the world as it is". Index 1 is air: "clear this block".
"""
import gzip
import struct

import numpy as np

DATA_VERSION = 3955  # Minecraft 1.21.1
VOID, AIR = 0, 1


def state_key(name, props):
    if ":" not in name:
        name = "minecraft:" + name
    if not props:
        return name
    inner = ",".join(f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in sorted(props.items()))
    return f"{name}[{inner}]"


def parse_state(key):
    name, _, rest = key.partition("[")
    props = dict(p.split("=", 1) for p in rest.rstrip("]").split(",")) if rest else {}
    return name, props


class Grid:
    def __init__(self, sx, sy, sz):
        self.shape = (sx, sy, sz)
        self.a = np.zeros(self.shape, np.uint16)
        self.built = np.zeros(self.shape, bool)  # structure blocks (decay applies)
        self.keep = np.zeros(self.shape, bool)  # protected from decay
        self.pal = ["minecraft:structure_void", "minecraft:air"]
        self.ids = {k: i for i, k in enumerate(self.pal)}
        self.block_nbt = {}  # (x, y, z) -> block entity compound (python dict, see nbt_* helpers)

    # ---- palette ----
    def s(self, name, **props):
        key = state_key(name, props)
        i = self.ids.get(key)
        if i is None:
            i = self.ids[key] = len(self.pal)
            self.pal.append(key)
        return i

    def name_of(self, i):
        return parse_state(self.pal[i])[0]

    def ids_where(self, pred):
        return np.array([i for i, k in enumerate(self.pal) if pred(k)], np.uint16)

    # ---- writing ----
    def inside(self, x, y, z):
        return 0 <= x < self.shape[0] and 0 <= y < self.shape[1] and 0 <= z < self.shape[2]

    def put(self, x, y, z, st, built=True, keep=False):
        if self.inside(x, y, z):
            self.a[x, y, z] = st
            self.built[x, y, z] = built
            if keep:
                self.keep[x, y, z] = True

    def get(self, x, y, z):
        return int(self.a[x, y, z]) if self.inside(x, y, z) else VOID

    def box(self, x0, y0, z0, x1, y1, z1, st, built=True, keep=False):
        """Fill an inclusive box, clipped to the grid."""
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        za, zb = sorted((z0, z1))
        xa, ya, za = max(xa, 0), max(ya, 0), max(za, 0)
        xb, yb, zb = min(xb, self.shape[0] - 1), min(yb, self.shape[1] - 1), min(zb, self.shape[2] - 1)
        if xa > xb or ya > yb or za > zb:
            return
        sl = (slice(xa, xb + 1), slice(ya, yb + 1), slice(za, zb + 1))
        self.a[sl] = st
        self.built[sl] = built
        if keep:
            self.keep[sl] = True

    def column_mask(self, mask2d, y0, y1, st, built=True, only=None):
        """Fill y0..y1 (inclusive) wherever the (x, z) mask is set; `only` limits it to cells currently in that id set."""
        ya, yb = max(y0, 0), min(y1, self.shape[1] - 1)
        if ya > yb:
            return
        sub = self.a[:, ya:yb + 1, :]
        m = np.repeat(mask2d[:, None, :], yb - ya + 1, axis=1)
        if only is not None:
            m &= np.isin(sub, only)
        sub[m] = st
        self.built[:, ya:yb + 1, :][m] = built

    # ---- export ----
    def used(self):
        ids = np.unique(self.a)
        remap = np.zeros(len(self.pal), np.uint32)
        remap[ids] = np.arange(len(ids))
        return ids, remap

    def write_schem(self, path, offset=(0, 0, 0)):
        """Sponge schematic v3, as read by WorldEdit 7.3. Paste with //paste -m !minecraft:structure_void."""
        sx, sy, sz = self.shape
        ids, remap = self.used()
        data = remap[self.a].transpose(1, 2, 0).ravel()  # index = (y * length + z) * width + x
        palette = {self.pal[i]: Int(n) for n, i in enumerate(ids)}
        bes = []
        for (x, y, z), be in sorted(self.block_nbt.items()):
            body = dict(be)
            ident = body.pop("id")
            bes.append({"Pos": IntArray([x, y, z]), "Id": String(ident), "Data": body})
        root = {"Schematic": {
            "Version": Int(3), "DataVersion": Int(DATA_VERSION),
            "Width": Short(sx), "Height": Short(sy), "Length": Short(sz),
            "Offset": IntArray(list(offset)),
            "Metadata": {"Name": String("Remnant city core"), "Author": String("Remnant citygen")},
            "Blocks": {"Palette": palette, "Data": ByteArray(varints(data)), "BlockEntities": List(10, bes)},
        }}
        with gzip.open(path, "wb") as f:
            f.write(encode_root(root))

    def write_structure(self, path, x0, x1, z0, z1):
        """Vanilla structure template for columns x0..x1-1, z0..z1-1 (full height); voids are left out."""
        sub = self.a[x0:x1, :, z0:z1]
        ids = np.unique(sub)
        ids = ids[ids != VOID]
        local = {int(i): n for n, i in enumerate(ids)}
        out = bytearray()
        xs, ys, zs = np.nonzero(sub != VOID)
        out += b"\x0a\x00\x00"
        out += tag_name(3, "DataVersion") + struct.pack(">i", DATA_VERSION)
        out += tag_name(9, "size") + b"\x03" + struct.pack(">i", 3) + struct.pack(">iii", *sub.shape)
        out += tag_name(9, "entities") + b"\x0a" + struct.pack(">i", 0)
        out += tag_name(9, "palette") + b"\x0a" + struct.pack(">i", len(ids))
        for i in ids:
            name, props = parse_state(self.pal[int(i)])
            out += tag_name(8, "Name") + string_bytes(name)
            if props:
                out += tag_name(10, "Properties")
                for k, v in props.items():
                    out += tag_name(8, k) + string_bytes(v)
                out += b"\x00"
            out += b"\x00"
        out += tag_name(9, "blocks") + b"\x0a" + struct.pack(">i", len(xs))
        pos_hdr = tag_name(9, "pos") + b"\x03" + struct.pack(">i", 3)
        st_hdr = tag_name(3, "state")
        vals = sub[xs, ys, zs]
        for x, y, z, v in zip(xs.tolist(), ys.tolist(), zs.tolist(), vals.tolist()):
            out += pos_hdr + struct.pack(">iii", x, y, z) + st_hdr + struct.pack(">i", local[v])
            be = self.block_nbt.get((x + x0, y, z + z0))
            if be:
                out += tag_name(10, "nbt") + encode_compound_body(be)
            out += b"\x00"
        out += b"\x00"
        with gzip.open(path, "wb") as f:
            f.write(bytes(out))


# ---------- minimal NBT encoding ----------
class Int(int):
    pass


class Short(int):
    pass


class Byte(int):
    pass


class String(str):
    pass


class IntArray(list):
    pass


class ByteArray(bytes):
    pass


class List(list):
    def __init__(self, kind, items):
        super().__init__(items)
        self.kind = kind


def tag_name(t, name):
    return bytes([t]) + string_bytes(name)


def string_bytes(s):
    b = s.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def tag_type(v):
    if isinstance(v, Byte):
        return 1
    if isinstance(v, Short):
        return 2
    if isinstance(v, Int) or isinstance(v, int):
        return 3
    if isinstance(v, ByteArray):
        return 7
    if isinstance(v, str):
        return 8
    if isinstance(v, List):
        return 9
    if isinstance(v, dict):
        return 10
    if isinstance(v, IntArray):
        return 11
    raise TypeError(type(v))


def payload(v):
    t = tag_type(v)
    if t == 1:
        return struct.pack(">b", v)
    if t == 2:
        return struct.pack(">h", v)
    if t == 3:
        return struct.pack(">i", v)
    if t == 7:
        return struct.pack(">i", len(v)) + bytes(v)
    if t == 8:
        return string_bytes(v)
    if t == 9:
        return bytes([v.kind if v else 0]) + struct.pack(">i", len(v)) + b"".join(payload(i) for i in v)
    if t == 10:
        return encode_compound_body(v)
    if t == 11:
        return struct.pack(">i", len(v)) + struct.pack(f">{len(v)}i", *v)


def encode_compound_body(d):
    return b"".join(tag_name(tag_type(v), k) + payload(v) for k, v in d.items()) + b"\x00"


def encode_root(d):
    return b"\x0a" + string_bytes("") + encode_compound_body(d)


def varints(arr):
    out = bytearray()
    for v in arr.tolist():
        while v >= 0x80:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        out.append(v)
    return bytes(out)
