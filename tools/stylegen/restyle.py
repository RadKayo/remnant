"""Proof of concept: recolour a MineColonies blueprint for each Remnant bloodline and render previews.

Swaps materials only (woods, stones, roof, glass, lighting, bedding); every building's shape stays the
authors' own. Output stays private: the bundled styles are All Rights Reserved.
"""
import math
import os
import sys

import nbtlib
from nbtlib import String
from PIL import Image, ImageDraw, ImageFont

TEX = "tex/assets/minecraft/textures/block"
VALID = {f[:-5] for f in os.listdir("tex/assets/minecraft/blockstates")}

WOODS = ["dark_oak", "oak", "spruce", "birch", "jungle", "acacia", "mangrove", "cherry", "crimson", "warped"]


def stone_set(base, stairs=None, slab=None, wall=None):
    return {"block": base, "stairs": stairs, "slab": slab, "wall": wall}


def auto_set(block, stem=None):
    stem = stem or block.rstrip("s") if block.endswith("bricks") else (stem or block)
    s = {"block": block}
    for kind in ("stairs", "slab", "wall"):
        cand = f"{stem}_{kind}"
        s[kind] = cand if cand in VALID else None
    return s


# what each bloodline turns the base style's materials into
BLOODLINES = {
    "Bladebound": dict(wood="cherry", primary=auto_set("andesite"), secondary=auto_set("polished_andesite"),
                       roof="domum_ornamentum:black_brick_extra", infill="domum_ornamentum:white_paper_extra", accent="quartz_block", glass="white", light="lantern", cloth="red"),
    "Stormwalker": dict(wood="birch", primary=auto_set("diorite"), secondary=auto_set("polished_diorite"),
                        roof="minecraft:weathered_copper", infill="minecraft:calcite", accent="smooth_quartz", glass="light_blue", light="lantern",
                        cloth="light_blue"),
    "Ironsoul": dict(wood="spruce", primary=auto_set("tuff_bricks", "tuff_brick"), secondary=auto_set("polished_tuff"),
                     roof="domum_ornamentum:gray_brick_extra", infill="minecraft:tuff", accent="chiseled_tuff", glass="bars", light="lantern", cloth="gray"),
    "Weave-touched": dict(wood="warped", primary=auto_set("prismarine"),
                          secondary=stone_set("purpur_block", "purpur_stairs", "purpur_slab", "prismarine_wall"),
                          roof="domum_ornamentum:purple_brick_extra", infill="minecraft:dark_prismarine", accent="purpur_pillar", glass="purple", light="soul", cloth="purple"),
    "Riftborn": dict(wood="dark_oak", primary=auto_set("end_stone_bricks", "end_stone_brick"),
                     secondary=auto_set("polished_blackstone_bricks", "polished_blackstone_brick"),
                     roof="minecraft:obsidian", infill="minecraft:end_stone", accent="crying_obsidian", glass="magenta", light="soul", cloth="magenta"),
    "Deepdelver": dict(wood="spruce", primary=auto_set("cobbled_deepslate"),
                       secondary=auto_set("deepslate_bricks", "deepslate_brick"),
                       roof="minecraft:deepslate_tiles", infill="minecraft:smooth_basalt", accent="polished_deepslate", glass="gray", light="lantern", cloth="brown"),
    "Beastbound": dict(wood="mangrove", primary=auto_set("mossy_cobblestone"),
                       secondary=auto_set("mud_bricks", "mud_brick"), roof="minecraft:hay_block", infill="minecraft:packed_mud", accent="packed_mud",
                       glass="green", light="lantern", cloth="green"),
    "Graveborn": dict(wood="dark_oak", primary=auto_set("blackstone"),
                      secondary=auto_set("polished_blackstone_bricks", "polished_blackstone_brick"),
                      roof="domum_ornamentum:black_brick_extra", infill="minecraft:bone_block", accent="bone_block", glass="black", light="soul", cloth="black"),
    "Hearthborn": dict(wood="spruce", primary=auto_set("bricks", "brick"), secondary=auto_set("granite"),
                       roof="domum_ornamentum:orange_brick_extra", infill="domum_ornamentum:paper_extra", accent="smooth_sandstone", glass="orange", light="lantern", cloth="orange"),
}

# the base style's own material families (Medieval Oak)
BASE = {"wood": "oak", "primary": auto_set("cobblestone"), "secondary": auto_set("stone_bricks", "stone_brick"),
        "accent": "polished_andesite"}


def wood_name(wood, part):
    nether = wood in ("crimson", "warped")
    table = {"log": f"{wood}_stem" if nether else f"{wood}_log",
             "wood": f"{wood}_hyphae" if nether else f"{wood}_wood",
             "stripped_log": f"stripped_{wood}_stem" if nether else f"stripped_{wood}_log",
             "stripped_wood": f"stripped_{wood}_hyphae" if nether else f"stripped_{wood}_wood"}
    return table.get(part, f"{wood}_{part}")


def block_map(line):
    """Build {old block id: new block id} for one bloodline, keeping only swaps the game knows."""
    m = {}
    base_w, w = BASE["wood"], line["wood"]
    for part in ["planks", "log", "wood", "stripped_log", "stripped_wood", "slab", "stairs", "door", "trapdoor",
                 "fence", "fence_gate", "button", "pressure_plate", "sign", "wall_sign", "hanging_sign",
                 "wall_hanging_sign", "leaves"]:
        a, b = wood_name(base_w, part), wood_name(w, part)
        if a in VALID and b in VALID:
            m[a] = b
    for fam in ("primary", "secondary"):
        for kind in ("block", "stairs", "slab", "wall"):
            a, b = BASE[fam].get(kind), line[fam].get(kind)
            if a and b and b in VALID:
                m[a] = b
    if line["accent"] in VALID:
        m[BASE["accent"]] = line["accent"]
    g = line["glass"]
    if g == "bars":
        m["glass_pane"] = "iron_bars"
    else:
        m["glass_pane"], m["glass"] = f"{g}_stained_glass_pane", f"{g}_stained_glass"
    if line["light"] == "soul":
        m.update({"torch": "soul_torch", "wall_torch": "soul_wall_torch", "lantern": "soul_lantern",
                  "campfire": "soul_campfire"})
    c = line["cloth"]
    for colour in ["white", "red", "orange", "yellow", "lime", "green", "blue", "light_blue", "purple", "magenta",
                   "pink", "brown", "gray", "light_gray", "black", "cyan"]:
        for item in ("bed", "carpet", "wool", "banner", "wall_banner"):
            a, b = f"{colour}_{item}", f"{c}_{item}"
            if a in VALID and b in VALID:
                m[a] = b
    return {k: v for k, v in m.items() if v in VALID}


ROOF_BLOCKS = ("domum_ornamentum:shingle", "domum_ornamentum:shingle_slab")


def restyle(path, line):
    f = nbtlib.load(path)
    m = block_map(line)
    for p in f["palette"]:
        ns, _, name = str(p["Name"]).partition(":")
        if ns == "minecraft" and name in m:
            p["Name"] = String("minecraft:" + m[name])
    pal = f["palette"]
    sx, sy, sz = int(f["size_x"]), int(f["size_y"]), int(f["size_z"])
    idx = blocks(f)
    for te in f["tile_entities"]:
        if "textureData" not in te:
            continue
        x, y, z = int(te["x"]), int(te["y"]), int(te["z"])
        here = str(pal[idx[(y * sz + z) * sx + x]]["Name"])
        for slot, mat in list(te["textureData"].items()):
            ns, name = str(mat).split(":", 1)
            if ns == "domum_ornamentum":  # the tile on a roof, the plaster in a wall
                te["textureData"][slot] = String(line["roof"] if here.startswith(ROOF_BLOCKS) else line["infill"])
            elif name in m:
                te["textureData"][slot] = String("minecraft:" + m[name])
    return f


def blocks(f):
    out = []
    for v in f["blocks"]:
        v = int(v) & 0xFFFFFFFF
        out += [v >> 16, v & 0xFFFF]
    return out


# ---------- preview rendering ----------
_colour_cache = {}


def avg(name):
    if name in _colour_cache:
        return _colour_cache[name]
    p = f"{TEX}/{name}.png"
    if not os.path.exists(p):
        _colour_cache[name] = None
        return None
    im = Image.open(p).convert("RGBA").crop((0, 0, 16, 16))
    px = [c for c in im.getdata() if c[3] > 40]
    col = tuple(sum(c[i] for c in px) // max(1, len(px)) for i in range(3)) if px else None
    _colour_cache[name] = col
    return col


def avg_path(p):
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGBA").crop((0, 0, 16, 16))
    px = [c for c in im.getdata() if c[3] > 40]
    return tuple(sum(c[i] for c in px) // max(1, len(px)) for i in range(3)) if px else None


def texture_colour(block, face):
    stem = block
    for suf in ("_wall_hanging_sign", "_hanging_sign", "_wall_sign", "_sign", "_pressure_plate", "_button",
                "_fence_gate", "_fence", "_trapdoor", "_door", "_stairs", "_slab", "_wall", "_pane"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
            break
    cands = []
    if face == "top":
        cands += [stem + "_top", stem + "_log_top", stem + "_stem_top"]
    cands += [stem, stem + "s", stem + "_planks", stem + "_block", stem + "_side", stem + "_log", stem + "_stem",
              stem.replace("brick", "bricks"), stem.replace("stained_glass", "stained_glass")]
    for w in WOODS:
        if stem.startswith(w + "_") or stem == w:
            cands.append(w + "_planks")
    for c in cands:
        col = avg(c)
        if col:
            if "leaves" in c or c in ("grass_block_top",):
                col = tuple(int(v * t) for v, t in zip(col, (0.45, 0.75, 0.35)))
            return col
    return None


THIN = ("fence", "pane", "wall", "bars", "door", "trapdoor", "ladder", "torch", "lantern", "button", "plate",
        "carpet", "sign", "potted", "flower", "banner", "rail", "chain")
SKIP = ("air", "blocksubstitution", "blocksolidsubstitution", "blockfluidsubstitution", "torch", "button",
        "pressure_plate", "carpet", "ladder", "potted_", "sign", "banner", "flower", "rail")


def render(f, scale=9):
    pal = f["palette"]
    sx, sy, sz = int(f["size_x"]), int(f["size_y"]), int(f["size_z"])
    idx = blocks(f)
    te_mat = {}
    for te in f["tile_entities"]:
        if "textureData" in te and len(te["textureData"]):
            vals = [str(v) for v in te["textureData"].values()]
            frame = ("planks", "_log", "_wood", "_stem", "hyphae")
            shown = next((v for v in vals if not any(k in v for k in frame)), vals[0])  # tile or infill shows most
            te_mat[(int(te["x"]), int(te["y"]), int(te["z"]))] = shown
    a = scale
    w = (sx + sz) * a + 4
    h = (sx + sz) * a // 2 + sy * a + 4
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = sz * a + 2, sy * a + 2
    cells = []
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                p = pal[idx[(y * sz + z) * sx + x]]
                ns, _, name = str(p["Name"]).partition(":")
                if any(s in name for s in SKIP):
                    continue
                props = {k: str(v) for k, v in p.get("Properties", {}).items()}
                if ns == "domum_ornamentum":
                    mat = te_mat.get((x, y, z), "minecraft:oak_planks")
                    mns, mname = mat.split(":", 1)
                    if mns == "domum_ornamentum":
                        top = side = (avg_path(f"tex/assets/domum_ornamentum/textures/block/extra/{mname}.png")
                                      or (180, 160, 130))
                    else:
                        top = side = texture_colour(mname, "side")
                elif ns == "minecraft":
                    top, side = texture_colour(name, "top"), texture_colour(name, "side")
                else:
                    top = side = (150, 120, 90)
                if not top:
                    continue
                height = 0.5 if ("slab" in name and props.get("type") != "double") or name.endswith("_bed") else 1.0
                lift = 0.5 if props.get("type") == "top" else 0.0
                thin = any(t in name for t in THIN)
                cells.append((x + z, y, x, z, top, side or top, height, lift, thin, "glass" in name or "pane" in name))
    cells.sort(key=lambda c: (c[1], c[0]))
    for _, y, x, z, top, side, height, lift, thin, glassy in cells:
        inset = 0.3 if thin else 0.0
        x0, z0, x1, z1 = x + inset, z + inset, x + 1 - inset, z + 1 - inset
        yb, yt = y + lift, y + lift + height

        def P(px, py, pz):
            return (ox + (px - pz) * a, oy + (px + pz) * a / 2 - py * a)
        alpha = 150 if glassy else 255
        topc = tuple(top) + (alpha,)
        left = tuple(int(c * 0.78) for c in side) + (alpha,)
        right = tuple(int(c * 0.6) for c in side) + (alpha,)
        d.polygon([P(x0, yt, z0), P(x1, yt, z0), P(x1, yt, z1), P(x0, yt, z1)], fill=topc)
        d.polygon([P(x0, yt, z1), P(x1, yt, z1), P(x1, yb, z1), P(x0, yb, z1)], fill=left)
        d.polygon([P(x1, yt, z0), P(x1, yt, z1), P(x1, yb, z1), P(x1, yb, z0)], fill=right)
    return img


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    variants = [("Medieval Oak (original)", nbtlib.load(src))]
    for name, line in BLOODLINES.items():
        variants.append((name, restyle(src, line)))
    tiles = [(n, render(f)) for n, f in variants]
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles)
    cols = 5
    rows = math.ceil(len(tiles) / cols)
    font = ImageFont.truetype(os.environ.get("FONT_BOLD", "/fonts/Silkscreen-Bold.ttf"), 20)
    small = ImageFont.truetype(os.environ.get("FONT", "/fonts/Silkscreen-Regular.ttf"), 14)
    sheet = Image.new("RGBA", (cols * (tw + 30) + 30, rows * (th + 60) + 90), "#14121a")
    dd = ImageDraw.Draw(sheet)
    dd.text((30, 24), f"Bloodline restyles of one MineColonies building ({os.path.basename(src)})", font=font,
            fill="#e8d9b5")
    for i, (n, t) in enumerate(tiles):
        x = 30 + (i % cols) * (tw + 30)
        y = 80 + (i // cols) * (th + 60)
        sheet.alpha_composite(t, (x + (tw - t.width) // 2, y + th - t.height))
        dd.text((x, y + th + 10), n.upper(), font=small, fill="#e8d9b5")
    sheet.save(out)
    print("wrote", out, "| swaps for Graveborn:", len(block_map(BLOODLINES["Graveborn"])))


if __name__ == "__main__":
    main()
