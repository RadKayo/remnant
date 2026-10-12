"""Preview renders for a Grid: a shaded top-down plan and an isometric view.

Block colours come from the real models and textures, read straight out of the game and mod jars.
"""
import io
import json
import zipfile

import numpy as np
from PIL import Image, ImageDraw

from voxel import AIR, VOID, parse_state

GRASS, FOLIAGE = (0x91, 0xBD, 0x59), (0x77, 0xAB, 0x2F)
TINT = {"grass_block": GRASS, "short_grass": GRASS, "tall_grass": GRASS, "fern": GRASS, "large_fern": GRASS,
        "vine": FOLIAGE, "oak_leaves": FOLIAGE, "jungle_leaves": FOLIAGE, "dark_oak_leaves": FOLIAGE,
        "acacia_leaves": FOLIAGE, "mangrove_leaves": FOLIAGE, "birch_leaves": (0x80, 0xA7, 0x55),
        "spruce_leaves": (0x61, 0x99, 0x61), "lily_pad": (0x20, 0x80, 0x30)}


class Assets:
    def __init__(self, jars):
        self.zips = [zipfile.ZipFile(j) for j in jars]
        self.cache = {}

    def read(self, path):
        for z in self.zips:
            try:
                return z.read(path)
            except KeyError:
                pass
        return None

    def json(self, path):
        b = self.read(path)
        return json.loads(b) if b else None

    def model_textures(self, ref):
        ns, _, p = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
        m = self.json(f"assets/{ns}/models/{p}.json")
        if m is None:
            return {}
        tex = dict(self.model_textures(m["parent"])) if "parent" in m else {}
        tex.update(m.get("textures", {}))
        return tex

    def avg(self, ref):
        if ref in self.cache:
            return self.cache[ref]
        ns, _, p = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
        b = self.read(f"assets/{ns}/textures/{p}.png")
        col = None
        if b:
            im = Image.open(io.BytesIO(b)).convert("RGBA")
            im = im.crop((0, 0, im.width, im.width))  # first animation frame
            px = np.asarray(im).reshape(-1, 4)
            px = px[px[:, 3] > 40]
            if len(px):
                col = tuple(int(c) for c in px[:, :3].mean(axis=0))
        self.cache[ref] = col
        return col

    def colours(self, key):
        """(top, side) colours for a block state key, or None for invisible blocks."""
        name, props = parse_state(key)
        ns, _, bare = name.partition(":")
        bs = self.json(f"assets/{ns}/blockstates/{bare}.json")
        if bs is None:
            return None
        model = None
        if "variants" in bs:
            best = None
            for k, v in bs["variants"].items():
                conds = dict(c.split("=") for c in k.split(",")) if k else {}
                if all(props.get(a) == b for a, b in conds.items()):
                    best = v
                    break
            best = best or next(iter(bs["variants"].values()))
            model = (best[0] if isinstance(best, list) else best)["model"]
        else:
            for part in bs["multipart"]:
                ap = part["apply"]
                model = (ap[0] if isinstance(ap, list) else ap)["model"]
                break
        tex = self.model_textures(model)

        def pick(keys):
            for k in keys:
                v = tex.get(k)
                seen = 0
                while v and v.startswith("#") and seen < 8:
                    v, seen = tex.get(v[1:]), seen + 1
                if v and not v.startswith("#"):
                    c = self.avg(v)
                    if c:
                        return c
            return None
        top = pick(["top", "up", "end", "all", "texture", "cross", "plant", "wall", "pattern", "particle", "side"])
        side = pick(["side", "all", "texture", "front", "north", "cross", "plant", "wall", "particle", "top"])
        tint = TINT.get(bare)
        if tint:
            if bare == "grass_block":
                top = tuple(int(c * t / 255) for c, t in zip(top, tint))
            else:
                top = tuple(int(c * t / 255) for c, t in zip(top, tint))
                side = tuple(int(c * t / 255) for c, t in zip(side, tint))
        if top is None and side is None:
            return None
        return top or side, side or top


CARPET = ("carpet", "snow", "pressure_plate", "rail", "lily_pad")
PLANT = ("grass", "fern", "flower", "sapling", "bush", "tulip", "dandelion", "poppy", "orchid", "allium", "bluet",
         "daisy", "cornflower", "lily_of", "roots", "mushroom", "dead_bush", "cluster", "_bud", "candle",
         "campfire", "skull", "lantern", "torch", "pot")
POST = ("_wall", "fence", "bars", "chain", "pane", "rod", "pointed_dripstone", "bulb")
FLAT = ("vine", "lichen", "ladder", "sign", "banner", "button", "tripwire", "cobweb", "structure_void")


def shape_of(key):
    name, props = parse_state(key)
    bare = name.split(":")[1]
    if bare in ("air", "structure_void", "cave_air") or any(bare.endswith(f) or f in bare for f in FLAT):
        return None
    if bare.endswith("_slab"):
        return {"top": "slab_top", "double": "cube"}.get(props.get("type"), "slab")
    if any(c in bare for c in CARPET):
        return "carpet"
    if bare.endswith("_wall") or any(p in bare for p in POST):
        return "post"
    if any(p in bare for p in PLANT) and not bare.endswith("_block"):
        return "plant"
    if bare.endswith("_trapdoor"):
        return "carpet" if props.get("open") == "false" else None
    if bare.endswith("_door"):
        return "post"
    return "cube"


def tables(grid, assets):
    n = len(grid.pal)
    top = np.zeros((n, 3), np.float32)
    side = np.zeros((n, 3), np.float32)
    shape = [None] * n
    for i, k in enumerate(grid.pal):
        sh = shape_of(k)
        cols = assets.colours(k) if sh else None
        if cols is None:
            continue
        top[i], side[i], shape[i] = cols[0], cols[1], sh
    return top, side, shape


def plan(grid, assets, ground, scale=4):
    """Top-down plan: each column shows its highest visible block, shaded by height."""
    top, _, shape = tables(grid, assets)
    visible = np.array([s is not None for s in shape])
    a = grid.a
    vis = visible[a]
    sy = a.shape[1]
    ys = np.where(vis.any(axis=1), sy - 1 - np.argmax(vis[:, ::-1, :], axis=1), 0)
    xs, zs = np.indices(ys.shape)
    ids = a[xs, ys, zs]
    col = top[ids]
    h = ys.astype(np.float32)
    shade = 1.0 + np.clip((h - ground) / 60.0, -0.4, 0.5) * 0.6
    dh = h - np.roll(np.roll(h, 1, 0), 1, 1)
    shade *= np.clip(1.0 + dh * 0.06, 0.6, 1.3)
    col = np.clip(col * shade[..., None], 0, 255)
    col[~vis.any(axis=1)] = (24, 24, 30)
    img = Image.fromarray(col.transpose(1, 0, 2).astype(np.uint8), "RGB")  # rows = z (south down), cols = x
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def iso(grid, assets, scale=4, bg=(22, 22, 28)):
    """Isometric view from the south-east (the +x, +z corner), drawn back to front."""
    top, side, shape = tables(grid, assets)
    solid_ids = np.array([s == "cube" for s in shape])
    a = grid.a
    sx, sy, sz = a.shape
    drawn = np.array([s is not None for s in shape])[a]
    solid = solid_ids[a]
    # a block can be skipped when the three faces we can see are all covered by full cubes
    cover = np.ones_like(solid)
    cover[:, :-1, :] &= solid[:, 1:, :]
    cover[:-1, :, :] &= solid[1:, :, :]
    cover[:, :, :-1] &= solid[:, :, 1:]
    cover[-1, :, :] = False
    cover[:, :, -1] = False
    cover[:, -1, :] = False
    xs, ys, zs = np.nonzero(drawn & ~cover)
    order = np.lexsort((ys, xs + zs + ys))
    xs, ys, zs = xs[order], ys[order], zs[order]
    s = scale
    w = (sx + sz) * s + 8
    h = (sx + sz) * s // 2 + sy * s + 8
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    ox, oy = sz * s + 4, sy * s + 4
    heights = {"cube": (0, 1, 0), "slab": (0, .5, 0), "slab_top": (.5, 1, 0), "carpet": (0, .08, 0),
               "plant": (0, .7, .3), "post": (0, 1, .3)}
    for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
        i = int(a[x, y, z])
        y0, y1, ins = heights[shape[i]]
        x0, x1, z0, z1 = x + ins, x + 1 - ins, z + ins, z + 1 - ins
        yb, yt = y + y0, y + y1

        def P(px, py, pz):
            return (ox + (px - pz) * s, oy + (px + pz) * s / 2 - py * s)
        t = tuple(int(c) for c in top[i])
        sd = side[i]
        d.polygon([P(x0, yt, z0), P(x1, yt, z0), P(x1, yt, z1), P(x0, yt, z1)], fill=t)
        d.polygon([P(x0, yt, z1), P(x1, yt, z1), P(x1, yb, z1), P(x0, yb, z1)], fill=tuple(int(c * .8) for c in sd))
        d.polygon([P(x1, yt, z0), P(x1, yt, z1), P(x1, yb, z1), P(x1, yb, z0)], fill=tuple(int(c * .62) for c in sd))
    box = Image.eval(img, lambda v: 0 if v == bg[0] or v == bg[1] or v == bg[2] else 255).convert("L").getbbox()
    return img.crop((max(0, box[0] - 8), max(0, box[1] - 8), box[2] + 8, box[3] + 8)) if box else img
