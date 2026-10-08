"""Remnant's own items: 16x16 textures for the custom (KubeJS) items in the design.

Run from the branding/ folder:  python src/items.py
Writes textures to out/items/ and a preview sheet to drafts/items_preview.png.

Each item is a stack of layers. A layer is a set of pixels, each naming a material and a tone
(0 = darkest, 5 = brightest). render() then adds the depth:
  - light from the top left: lit edges step up a tone, shaded edges step down
  - round forms (stones, orbs, seals) shaded from a height field, with reflected light on the rim
  - cylinders (spines, legs, rolls) shaded across their width
  - each layer casts a one-pixel shadow down and right onto the layers beneath it
  - glowing materials ignore shadows and light up their neighbours
  - a selective outline: soft on the lit side, darkest on the shaded side
  - a little surface texture (wood grain, stone speckle, paper fibre)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = "out/items"
FONT = "fonts/Silkscreen-Regular.ttf"
FONT_BOLD = "fonts/Silkscreen-Bold.ttf"


def rgba(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


class Mat:
    def __init__(self, ramp, outline, shiny=False, noise=0.0, glow=False, bevel=True):
        assert len(ramp) == 6
        self.ramp = [rgba(c) for c in ramp]
        self.outline = rgba(outline)
        self.shiny, self.noise, self.glow, self.bevel = shiny, noise, glow, bevel


# Six tones each, dark to light; shadows lean cool, highlights lean warm.
MATS = {
    "flint": Mat(["#14141c", "#23242f", "#363845", "#4f5262", "#747a8d", "#b0b7c8"], "#0b0b10", shiny=True),
    "wood": Mat(["#26140b", "#432614", "#653d20", "#8a5a32", "#ad7a47", "#d2a26a"], "#170c06", noise=0.18),
    "twine": Mat(["#433420", "#6a5534", "#927a50", "#b79f72", "#d6c393", "#efe2bd"], "#2a1f12"),
    "stone": Mat(["#1b1e2a", "#2f3546", "#47506a", "#66718c", "#8e99b3", "#c3cce0"], "#10121a", noise=0.12),
    "ember": Mat(["#6e2205", "#b33a0b", "#f27a14", "#ffa53a", "#ffd36b", "#fff4cc"], "#3a1203", glow=True),
    "leather": Mat(["#2b160c", "#46261a", "#663a22", "#87512f", "#a96d40", "#cc9260"], "#1a0d07", noise=0.05),
    "hide": Mat(["#22110a", "#3a1f14", "#56301d", "#734327", "#935a35", "#b5794d"], "#150a05", noise=0.06),
    "brass": Mat(["#3a2604", "#664308", "#9a6b0e", "#cf9a1f", "#efc246", "#fff0a6"], "#241702", shiny=True),
    "iron": Mat(["#121318", "#1f2127", "#30333b", "#474b55", "#686d79", "#9ea4b0"], "#0a0b0e", shiny=True, noise=0.05),
    "steel": Mat(["#2a2c33", "#40434c", "#5a5e69", "#7a7f8b", "#a2a8b4", "#d9dee7"], "#16171b", shiny=True),
    "paper": Mat(["#5a4528", "#85703f", "#ad9563", "#d3bd8f", "#e9d9b0", "#f8efd6"], "#3a2c18", noise=0.10),
    "ink": Mat(["#16274d", "#1e3566", "#2e4f8f", "#3d66ad", "#5c84c9", "#8fb0e3"], "#0d1830", bevel=False),
    "sepia": Mat(["#2a1a0e", "#3d2716", "#523520", "#6b472b", "#86603c", "#a37d54"], "#1a1008", bevel=False),
    "amethyst": Mat(["#26103a", "#43226c", "#643a9e", "#8c5fd0", "#b99bee", "#f0e8ff"], "#170a24", shiny=True),
    "board": Mat(["#0a1a10", "#123020", "#1b4529", "#2a6339", "#3f8a50", "#8fd09a"], "#06110a", noise=0.08),
    "copper": Mat(["#3e1c0c", "#6b3219", "#a5552e", "#cf7a43", "#eca46e", "#ffd2a8"], "#24100a", shiny=True, bevel=False),
    "chip": Mat(["#09090c", "#121217", "#1c1c23", "#2a2a34", "#454554", "#7a7a8e"], "#050507", shiny=True),
    "cyan": Mat(["#0c3f52", "#125c76", "#1b86a6", "#36bfe0", "#8af3ff", "#f2feff"], "#06202b", glow=True),
    "navy": Mat(["#0a0f24", "#141d42", "#1f2d60", "#2c3f80", "#3f57a3", "#6680cc"], "#05081a", noise=0.05),
    "charcoal": Mat(["#111114", "#1d1d22", "#2c2c33", "#3d3d46", "#53535e", "#6e6e7a"], "#08080a", noise=0.35, bevel=False),
    "coal": Mat(["#0c0c0f", "#18181d", "#26262d", "#36363f", "#4c4c57", "#6a6a77"], "#050506", shiny=True),
    "ribbon": Mat(["#3a0a0a", "#5e1212", "#8a1c1c", "#b52a2a", "#d94848", "#f07a7a"], "#200505"),
    "white": Mat(["#8a8f9c", "#a9aebb", "#c5c9d4", "#dcdfe7", "#eef0f5", "#ffffff"], "#4a4d55", bevel=False),
}

LIGHT = (-1 / math.sqrt(3.69), -1 / math.sqrt(3.69), 1.3 / math.sqrt(3.69))


def layer(pixels, form="flat", shadow="cast", gain=1.0):
    """pixels: {(x, y): (material, tone)}. form: flat | round | cylv | cylh | none.
    shadow: cast (onto layers below) | inset (carved into them) | none."""
    return {"px": dict(pixels), "form": form, "shadow": shadow, "gain": gain}


def from_rows(rows, legend, ox=0, oy=0):
    return {(x + ox, y + oy): legend[ch] for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in legend}


def rect(x0, y0, x1, y1, mat, tone):
    return {(x, y): (mat, tone) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def noise_at(x, y, salt):
    return ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) % 997 / 997


def runs(sil, axis):
    """Yield (pixel, t, length) across each horizontal (axis=0) or vertical (axis=1) run."""
    out = {}
    lines = {}
    for p in sil:
        lines.setdefault(p[1 - axis], []).append(p[axis])
    for k, vals in lines.items():
        vals.sort()
        start = prev = vals[0]
        for v in vals[1:] + [None]:
            if v is not None and v == prev + 1:
                prev = v
                continue
            n = prev - start + 1
            for i in range(start, prev + 1):
                p = (i, k) if axis == 0 else (k, i)
                out[p] = ((i - start) / (n - 1) if n > 1 else 0.5, n, i - start)
            if v is not None:
                start = prev = v
    return out


def heights(sil):
    edge = [(x, y) for x in range(-1, 17) for y in range(-1, 17) if (x, y) not in sil]
    d = {p: min(math.hypot(p[0] - e[0], p[1] - e[1]) for e in edge) for p in sil}
    top = max(d.values())
    return {p: math.sqrt(max(0.0, 1 - (1 - v / top) ** 2)) for p, v in d.items()}, d


def render(layers):
    buf = {}  # (x, y) -> [material, tone]
    for li, L in enumerate(layers):
        sil = set(L["px"])
        if L["shadow"] in ("cast", "inset"):
            adjust = {}
            for (x, y) in sil:
                dirs = ((1, 0, -1), (0, 1, -1), (1, 1, -1)) if L["shadow"] == "cast" else \
                       ((-1, 0, -1), (0, -1, -1), (1, 0, 1), (0, 1, 1))
                for a, b, dv in dirs:
                    p = (x + a, y + b)
                    if p not in sil and p in buf and not MATS[buf[p][0]].glow:
                        adjust[p] = min(adjust.get(p, dv), dv)
            for p, dv in adjust.items():
                buf[p][1] += dv
        form = L["form"]
        hts = heights(sil) if form == "round" else None
        across = runs(sil, 0) if form == "cylv" else runs(sil, 1) if form == "cylh" else None
        best = None
        for (x, y), (mname, tone) in L["px"].items():
            m = MATS[mname]
            up, lf = (x, y - 1) in sil, (x - 1, y) in sil
            dn, rt = (x, y + 1) in sil, (x + 1, y) in sil
            off = 0.0
            if form == "flat" and m.bevel:
                lit, dark = (not up) + (not lf), (not dn) + (not rt)
                off = (1 if lit else 0) - (1 if dark else 0)
                if lit == 2 and not dark and m.shiny:
                    off = 2
            elif form == "round":
                h, dist = hts
                hv = lambda p: h.get(p, 0.0)
                gx = (hv((x + 1, y)) - hv((x - 1, y))) * 1.6
                gy = (hv((x, y + 1)) - hv((x, y - 1))) * 1.6
                n = (-gx, -gy, 1.0)
                ln = math.sqrt(sum(c * c for c in n))
                s = sum(a * b / ln for a, b in zip(n, LIGHT))
                off = max(-2, min(2, round((s - LIGHT[2]) * 5 * L["gain"])))
                if dist[(x, y)] < 1.5 and gx + gy > 0.4:  # reflected light along the shaded rim
                    off += 1
                if best is None or s > best[0]:
                    best = (s, (x, y))
            elif form in ("cylv", "cylh"):
                t, n, i = across[(x, y)]
                off = 1 if t <= 0.25 else -1 if t >= 0.75 else 0
                if m.shiny and n >= 4 and i == 1:
                    off = 2
                if m.bevel:  # the ends of the cylinder
                    ends = (up, dn) if form == "cylv" else (lf, rt)
                    off += (0 if ends[0] else 1) - (0 if ends[1] else 1)
            if m.noise and noise_at(x, y, li) < m.noise:
                off -= 1
            buf[(x, y)] = [mname, tone + off]
        if best and MATS[L["px"][best[1]][0]].shiny:
            buf[best[1]][1] = 5  # specular highlight
    glowing = [p for p, (m, _) in buf.items() if MATS[m].glow]
    lit = {(p[0] + a, p[1] + b) for p in glowing for a in (-1, 0, 1) for b in (-1, 0, 1)}
    for q in lit:
        if q in buf and not MATS[buf[q][0]].glow:
            buf[q][1] += 1
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    for (x, y), (m, tone) in buf.items():
        if 0 <= x < 16 and 0 <= y < 16:
            px[x, y] = MATS[m].ramp[max(0, min(5, round(tone)))]
    for y in range(16):
        for x in range(16):
            if (x, y) in buf:
                continue
            shaded = buf.get((x - 1, y)) or buf.get((x, y - 1))
            lit_side = buf.get((x + 1, y)) or buf.get((x, y + 1))
            if shaded:
                px[x, y] = MATS[shaded[0]].outline
            elif lit_side:
                m = MATS[lit_side[0]]
                px[x, y] = m.ramp[0] if not m.glow else m.outline
    return img


# The hearth flame from the Remming stamp ('#' body, 'o' core)
FLAME = ["..#..", ".##..", ".###.", "##o##", "#ooo#", "#ooo#", ".###."]
# A letter of the Ascendancy's script
RUNE = [".k..", ".kk.", ".k.k", ".kk.", ".k..", ".k.."]
GEAR = ["..k.k..", ".kkkkk.", "kk...kk", ".k.k.k.", "kk...kk", ".kkkkk.", "..k.k.."]


def flint_shard():
    # Two faces meeting at a ridge: a bright upper face with conchoidal ripples, a dark lower face
    rows = [
        "................",
        "................",
        "................",
        "..........H.....",
        ".........HwL....",
        "........HLLMm...",
        ".......HLMLmmd..",
        "......HLLMmmdd..",
        ".....HLMLmmdd...",
        "....HLLMmmddd...",
        "....LMLmmddd....",
        "...LMMmmddd.....",
        "...MmmdddD......",
        "....ddDD........",
        "................",
        "................",
    ]
    tones = {"D": 0, "d": 1, "m": 2, "M": 3, "L": 4, "H": 5, "w": 5}
    return [render([layer(from_rows(rows, {k: ("flint", v) for k, v in tones.items()}))])]


def flint_hatchet():
    handle = {}
    for x in range(3, 14):
        y = 17 - x
        handle[(x, y)] = ("wood", 4)
        handle[(x + 1, y)] = ("wood", 2)
    head = from_rows([
        "HL......",
        "HwLM....",
        "HLMMmd..",
        "HLMmmmdd",
        "HLmmmdd.",
        "LLmmdd..",
        "Lmdd....",
        "md......",
    ], {"d": ("flint", 1), "m": ("flint", 2), "M": ("flint", 3), "L": ("flint", 4), "H": ("flint", 5),
        "w": ("flint", 5)}, 3, 2)  # a ground cutting edge on the left
    twine = {(x, y): ("twine", 4 if (x + y) % 2 else 2) for x in range(10, 13) for y in (6, 7)}
    return [render([layer(handle, form="none"), layer(head), layer(twine, form="none")])]


def hearthstone(frames=4):
    stone = {}
    for y in range(16):
        for x in range(16):
            dx, dy = (x - 7.5) / 5.6, (y - 8.0) / 6.2
            if dx * dx + dy * dy <= 1:
                stone[(x, y)] = ("stone", 3)
    out = []
    for f in range(frames):
        flicker = [(5, 7), (6, 8), (7, 7), (6, 9)][f]
        flame = {}
        for fy, row in enumerate(FLAME):
            for fx, ch in enumerate(row):
                if ch != ".":
                    p = (5 + fx, 4 + fy)
                    flame[p] = ("ember", 5 if p == flicker else 4 if ch == "o" else 2)
        out.append(render([layer(stone, form="round", gain=1.2), layer(flame, shadow="inset")]))
    return out


def relay_kit():
    crystal = from_rows(["..A.", ".AaV", ".AaV", ".AaV", ".AaV"],
                        {"A": ("amethyst", 4), "a": ("amethyst", 3), "V": ("amethyst", 1)}, 2, 1)
    board = from_rows(["eEEe", "eEEe", "eEEe", "eeee"], {"e": ("board", 2), "E": ("board", 3)}, 10, 3)
    traces = {(11, 4): ("copper", 4), (11, 5): ("copper", 3), (12, 5): ("copper", 3), (12, 3): ("brass", 4)}
    body = rect(2, 8, 13, 14, "leather", 3)
    flap = from_rows([
        "FFFFFFFFFFFF",
        "FFFFFFFFFFFF",
        "FFFFFFFFFFFF",
        ".FFFFFFFFFF.",
    ], {"F": ("hide", 3)}, 2, 6)
    stitches = {(x, 8): ("twine", 4) for x in range(3, 13) if x % 2 and x not in (7, 9)}
    buckle = from_rows(["bbb", "b.b", "bbb"], {"b": ("brass", 3)}, 7, 8)
    return [render([layer(crystal), layer(board), layer(traces, form="none", shadow="none"),
                    layer(body, form="round", gain=0.7), layer(flap),
                    layer(stitches, form="none", shadow="none"), layer(buckle)])]


def salvaged_circuitry():
    board = from_rows([
        "lllllb..",
        "lmmmmmmlb.....",
        "lmmmmmmmmb....",
        "lmmmmmmmmmmb..",
        "lmmmmmmmmmmb..",
        "lmmmmmmmmmmmd.",
        "lmmmmmmmmmmmd.",
        "lmmmmmmmmmmmd.",
        "lmmmmmmmmmmmd.",
        "lmmmmmmmmmmdd.",
        "ldmmmmmmmdd...",
        ".ddddddd......",
    ], {"l": ("board", 3), "m": ("board", 2), "d": ("board", 1), "b": ("board", 5)}, 2, 2)
    traces = {}
    for x in range(4, 9):
        traces[(x, 4)] = ("copper", 4)
    for y in range(5, 11):
        traces[(10, y)] = ("copper", 3)
    for x in range(5, 10):
        traces[(x, 10)] = ("copper", 3)
    for p in ((4, 4), (4, 10), (10, 10), (6, 12)):
        traces[p] = ("brass", 4)
    pins = {(x, y): ("steel", 4) for x in (4, 6, 8) for y in (5, 9)}
    chip = rect(4, 6, 8, 8, "chip", 3)
    dot = {(5, 7): ("steel", 3)}
    return [render([layer(board), layer(traces, form="none", shadow="none"),
                    layer(pins, form="none", shadow="none"), layer(chip), layer(dot, form="none", shadow="none")])]


def gearwright_schematic():
    paper = rect(2, 3, 13, 12, "paper", 3)
    del paper[(2, 8)]  # a tear in the left edge
    top, bottom = rect(1, 1, 14, 2, "paper", 3), rect(1, 13, 14, 14, "paper", 3)
    ends = {(x, y): ("paper", 1) for x in (1, 14) for y in (1, 2, 13, 14)}  # the rolled ends
    ink = {}
    ink.update(from_rows(GEAR, {"k": ("ink", 2)}, 3, 4))
    ink.update(from_rows(["k.k", "...", "kkk"], {"k": ("ink", 3)}, 10, 4))
    ink.update(from_rows(["kk.kkk"], {"k": ("ink", 2)}, 3, 11))
    seal = from_rows([".GG.", "GGGG", "GGGG", ".GG."], {"G": ("brass", 3)}, 10, 8)
    return [render([layer(paper), layer(ink, form="none", shadow="none"), layer(top, form="cylh"),
                    layer(bottom, form="cylh"), layer(ends, form="none", shadow="none"), layer(seal, form="round")])]


def book(cover_mat, spine_mat, plate_mat, x0, y0, x1, y1, plates="all"):
    pages = {(x1 + 1, y): ("paper", 4 if y % 2 else 3) for y in range(y0 + 1, y1 + 2)}
    pages.update({(x, y1 + 1): ("paper", 3) for x in range(x0 + 1, x1 + 2)})
    cover = rect(x0, y0, x1, y1, cover_mat, 2)
    spine = rect(x0, y0, x0 + 1, y1, spine_mat, 2)
    bands = {(x, y): (plate_mat, 3) for x in (x0, x0 + 1) for y in (y0 + 2, y1 - 2)}
    corners = {}
    spots = [(x1 - 1, y0), (x1 - 1, y1 - 1)] + ([(x0 + 2, y0), (x0 + 2, y1 - 1)] if plates == "all" else [])
    if plates:
        for cx, cy in spots:
            corners.update(rect(cx, cy, cx + 1, cy + 1, plate_mat, 3))
    return [layer(pages, form="none"), layer(cover), layer(spine, form="cylv"),
            layer(bands, form="none", shadow="none"), layer(corners)]


def foundry_codex():
    layers = book("iron", "iron", "steel", 2, 1, 12, 13)
    emblem = from_rows([".F.F.", "FfffF", ".fxf.", "FfffF", ".F.F."],
                       {"F": ("ember", 3), "f": ("ember", 2), "x": ("ember", 0)}, 6, 4)
    seam = {(x, 10): ("ember", 2) for x in range(5, 11)}
    return [render(layers + [layer(emblem, shadow="inset"), layer(seam, form="none", shadow="inset")])]


def rune_primer():
    layers = book("leather", "hide", "brass", 3, 2, 11, 12, plates="front")
    rune = from_rows(RUNE, {"k": ("cyan", 3)}, 6, 4)
    ribbon = {(9, 14): ("ribbon", 3), (9, 15): ("ribbon", 2)}
    return [render(layers + [layer(rune, form="none", shadow="inset"), layer(ribbon, form="none")])]


def aether_core(frames=6):
    out = []
    for f in range(frames):
        pulse = 1 if f in (1, 2, 3) else 0
        orb = {(x, y): ("cyan", 3 + pulse) for x in range(16) for y in range(16)
               if math.hypot(x - 7.5, y - 7.5) <= 5.0}
        a = 2 * math.pi * f / frames
        spark = (round(7.5 + 2.6 * math.cos(a)), round(7.5 + 2.6 * math.sin(a)))
        orb[spark] = ("cyan", 5)
        cage = {}
        for y in range(16):
            for x in range(16):
                dx, dy = x - 7.5, y - 7.5
                mer = abs((dx / 2.3) ** 2 + (dy / 5.6) ** 2 - 1) < 0.22 and abs(dy) < 5.4
                equ = abs((dx / 5.6) ** 2 + (dy / 1.7) ** 2 - 1) < 0.25 and dy > -0.5
                if mer or equ:
                    cage[(x, y)] = ("brass", 3)
        caps = {(7, 1): ("brass", 3), (8, 1): ("brass", 3), (7, 14): ("brass", 2), (8, 14): ("brass", 2)}
        out.append(render([layer(orb, form="round", gain=0.8), layer(cage, form="none"), layer(caps)]))
    return out


def memory_shard(frames=6):
    rows = [
        "................",
        "........H.......",
        ".......HLR......",
        ".......LMMR.....",
        "......HLMMR.....",
        "......LLMcR.....",
        "......LMccR.....",
        ".....HLMcMRR....",
        ".....LLMMMRR....",
        ".....LMMMRRR....",
        "....HLMMMRR.....",
        "....LLMMRRR.....",
        "....LMMMRR......",
        ".....MMRR.......",
        "......RR........",
        "................",
    ]
    tone = {"H": 5, "L": 4, "M": 3, "R": 1}
    out = []
    for f in range(frames):
        band = 4 + f * 4  # a glint sweeping down the crystal
        crystal, glint = {}, {}
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "c":
                    glint[(x, y)] = ("cyan", 4)
                elif ch in tone:
                    crystal[(x, y)] = ("amethyst", tone[ch] + (1 if band <= x + y < band + 2 else 0))
        crystal.update({p: ("amethyst", 3) for p in glint})
        out.append(render([layer(crystal), layer(glint, form="none", shadow="inset")]))
    return out


def rubbing():
    paper = rect(3, 2, 12, 13, "paper", 3)
    rune = set(from_rows(RUNE, {"k": 0}, 6, 5))
    coal = {(x, y): ("charcoal", 2) for x in range(4, 12) for y in range(3, 13) if (x, y) not in rune}
    tack = rect(7, 1, 8, 2, "brass", 3)
    return [render([layer(paper), layer(coal, form="none", shadow="none"), layer(tack, form="round")])]


def torn_page():
    paper = {}
    for y, cut in zip(range(1, 15), [12, 12, 11, 12, 11, 10, 11, 12, 12, 11, 10, 11, 12, 12]):
        for x in range(3, cut + 1):
            tone = 5 if x == cut else 3  # torn fibres along the rip
            paper[(x, y)] = ("paper", tone)
    ink = from_rows(RUNE, {"k": ("sepia", 2)}, 5, 2)
    for y, marks in ((9, "kk.k.kk"), (11, "k.kkk.k"), (13, "kkk.k")):
        ink.update(from_rows([marks], {"k": ("sepia", 3)}, 4, y))
    return [render([layer(paper), layer(ink, form="none", shadow="none")])]


def presidential_pants():
    legs = from_rows([
        "nnnnnnnnnn",
        "nnnnnnnnnn",
        "nnnnnnnnnn",
        "nnnnnnnnnn",
        "nnnn..nnnn",
        "nnnn..nnnn",
        "nnkn..nkkn",
        "nknn..nnkn",
        "nnnn..nnnn",
        "nnnn..nnnn",
        "nnnn..nnnn",
    ], {"n": ("navy", 3), "k": ("navy", 2)}, 3, 3)
    belt = rect(3, 2, 12, 2, "navy", 1)
    stripes = {(x, y): ("brass", 3) for x in (4, 11) for y in range(7, 14)}
    cuffs = {**rect(3, 14, 6, 14, "brass", 3), **rect(9, 14, 12, 14, "brass", 3)}
    buckle = rect(7, 2, 8, 3, "brass", 3)
    star = {(5, 4): ("white", 5)}
    return [render([layer(legs, form="cylv"), layer(belt), layer(stripes, form="none", shadow="none"),
                    layer(cuffs, form="cylv"), layer(buckle), layer(star, form="none", shadow="none")])]


# id, display name, what it's for, drawing function
ITEMS = [
    ("flint_shard", "Flint Shard", "Age I: knapped from gravel", flint_shard),
    ("flint_hatchet", "Flint Hatchet", "Age I: the first axe", flint_hatchet),
    ("hearthstone", "Hearthstone", "Hourly home recall, bound at a hearth", hearthstone),
    ("relay_kit", "Relay Kit", "Rebuilds a ruined waystone", relay_kit),
    ("salvaged_circuitry", "Salvaged Circuitry", "Relay Kit part, from ruins", salvaged_circuitry),
    ("gearwright_schematic", "Gearwright Schematic", "Opens the Age of Steam", gearwright_schematic),
    ("foundry_codex", "Foundry Codex", "Opens the Age of Industry", foundry_codex),
    ("aether_core", "Aether Core", "Opens the Age of Reclamation", aether_core),
    ("memory_shard", "Memory Shard", "Teaches rune letters, holds a memory", memory_shard),
    ("rune_primer", "Rune Primer", "Shares runes you know", rune_primer),
    ("rubbing", "Rubbing", "Charcoal copy of an inscription", rubbing),
    ("torn_page", "Torn Page", "Lore scrap; pages combine into logs", torn_page),
    ("presidential_pants", "Chancellor Henry the President's Pants", "WHERE ARE THEY KAYO", presidential_pants),
]


def wrap(d, text, font, width):
    lines, line = [], ""
    for word in text.split():
        if line and d.textlength(line + " " + word, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return lines + [line]


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs("drafts", exist_ok=True)
    tiles = []
    for iid, name, note, make in ITEMS:
        frames = make()
        if len(frames) > 1:
            strip = Image.new("RGBA", (16, 16 * len(frames)))
            for i, fr in enumerate(frames):
                strip.paste(fr, (0, 16 * i))
            strip.save(f"{OUT}/{iid}.png")
            with open(f"{OUT}/{iid}.png.mcmeta", "w") as fh:
                fh.write('{"animation": {"frametime": 4, "interpolate": false}}\n')
        else:
            frames[0].save(f"{OUT}/{iid}.png")
        tiles.append((name, note, frames[0]))

    cols, scale, pad = 5, 10, 36
    cell = 16 * scale
    cw = cell + 120
    rows = (len(tiles) + cols - 1) // cols
    w = pad + cols * (cw + pad)
    h = 90 + rows * (cell + 110) + 150
    img = Image.new("RGBA", (w, h), "#14121a")
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_BOLD, 32)
    label = ImageFont.truetype(FONT, 17)
    small = ImageFont.truetype(FONT, 14)
    d.text((pad, 22), "REMNANT ITEMS - draft textures (16x16, shown at 10x)", font=title, fill="#e8d9b5")
    for i, (name, note, tile) in enumerate(tiles):
        x = pad + (i % cols) * (cw + pad)
        y = 90 + (i // cols) * (cell + 110)
        img.alpha_composite(tile.resize((cell, cell), Image.NEAREST), (x + 60, y))
        ly = y + cell + 10
        for text, font, colour, step in ((name.upper(), label, "#e8d9b5", 22), (note, small, "#9c8f78", 18)):
            for line in wrap(d, text, font, cw):
                d.text((x, ly), line, font=font, fill=colour)
                ly += step
            ly += 4
    sy = h - 120  # hotbar mock-up at 4x
    d.text((pad, sy), "In a hotbar (4x):", font=small, fill="#9c8f78")
    for i, (_, _, tile) in enumerate(tiles):
        x = pad + i * 76
        y = sy + 26
        d.rectangle([x, y, x + 71, y + 71], fill="#8b8b8b")
        d.line([x, y, x + 71, y], fill="#373737", width=4)
        d.line([x, y, x, y + 71], fill="#373737", width=4)
        d.line([x, y + 71, x + 71, y + 71], fill="#ffffff", width=4)
        d.line([x + 71, y, x + 71, y + 71], fill="#ffffff", width=4)
        img.alpha_composite(tile.resize((64, 64), Image.NEAREST), (x + 4, y + 4))
    img.save("drafts/items_preview.png")
    print("wrote", OUT, "and drafts/items_preview.png")


if __name__ == "__main__":
    main()
