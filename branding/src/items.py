"""Remnant's own items: 16x16 textures for the custom (KubeJS) items in the design.

Run from the branding/ folder:  python src/items.py
Writes textures to out/items/ and a preview sheet to drafts/items_preview.png.
Shapes are drawn without outlines; outline() adds the dark edge afterwards.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = "out/items"
FONT = "fonts/Silkscreen-Regular.ttf"
FONT_BOLD = "fonts/Silkscreen-Bold.ttf"


def rgba(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def blank():
    return Image.new("RGBA", (16, 16), (0, 0, 0, 0))


def grid(rows, pal, img=None, ox=0, oy=0):
    img = img or blank()
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and 0 <= x + ox < 16 and 0 <= y + oy < 16:
                px[x + ox, y + oy] = rgba(pal[ch])
    return img


def check(name, rows):
    assert len(rows) == 16, f"{name}: {len(rows)} rows"
    for y, row in enumerate(rows):
        assert len(row) == 16, f"{name} row {y}: {len(row)} wide: {row!r}"


def outline(img, color):
    px = img.load()
    filled = {(x, y) for x in range(16) for y in range(16) if px[x, y][3]}
    for y in range(16):
        for x in range(16):
            if (x, y) not in filled and any((x + a, y + b) in filled for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = rgba(color)
    return img


FLINT = {"d": "#2b2c33", "m": "#464954", "l": "#6b707c", "h": "#9aa1ae", "w": "#d6dbe3"}
WOOD = {"c": "#a8763f", "b": "#6e4724", "t": "#d9c391", "T": "#9a8256"}
BRASS = {"g": "#9a6b0e", "G": "#d9a521", "y": "#f2c94c", "Y": "#fff1a8"}
INK = {"k": "#2e4f8f"}
PARCHMENT = {"P": "#eedfba", "p": "#d8c49a", "q": "#b09a6e", "Q": "#8a7650"}

# The hearth flame from the Remming stamp ('#' body, 'o' core)
FLAME = ["..#..", ".##..", ".###.", "##o##", "#ooo#", "#ooo#", ".###."]
# A rune in the style of the Ascendancy's script
RUNE = [".k..", ".kk.", ".k.k", ".kk.", ".k..", ".k.."]


def flint_shard():
    rows = [
        "................",
        "................",
        "................",
        "..........h.....",
        ".........hwl....",
        "........hwlmm...",
        ".......hllmmmd..",
        "......hlmmmmdd..",
        ".....hlmmlmdd...",
        "....hlmlmmddd...",
        "....lmmmlddd....",
        "...lmmmdddd.....",
        "...mmddddd......",
        "....dddd........",
        "................",
        "................",
    ]
    check("flint_shard", rows)
    return [outline(grid(rows, FLINT), "#121216")]


def flint_hatchet():
    rows = [
        "................",
        "................",
        "...hh...........",
        "...hwll.........",
        "...hlmmmd....cb.",
        "...hlmmmmdd.cb..",
        "...lmmmmddtTt...",
        "...lmmmdd.TtT...",
        "...mmdd..cb.....",
        "...md...cb......",
        ".......cb.......",
        "......cb........",
        ".....cb.........",
        "....cb..........",
        "...cb...........",
        "................",
    ]
    check("flint_hatchet", rows)
    return [outline(grid(rows, {**FLINT, **WOOD}), "#17130f")]


def sheet(x0, y0, x1, y1):
    """A parchment rectangle lit from the top left."""
    img = blank()
    px = img.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c = "p"
            if y == y0 or x == x0:
                c = "P"
            elif y == y1 or x == x1:
                c = "q"
            px[x, y] = rgba(PARCHMENT[c])
    return img


GEAR7 = [
    "..k.k..",
    ".kkkkk.",
    "kk...kk",
    ".k.k.k.",
    "kk...kk",
    ".kkkkk.",
    "..k.k..",
]


def gearwright_schematic():
    img = sheet(2, 2, 13, 13)
    px = img.load()
    for x, y in ((13, 13), (12, 13), (13, 12)):  # curled corner
        px[x, y] = (0, 0, 0, 0)
    px[12, 12] = rgba(PARCHMENT["Q"])
    px[2, 8] = (0, 0, 0, 0)  # a tear in the left edge
    grid(GEAR7, INK, img, 3, 3)
    grid(["k.k", "...", "kkk", "...", "k.k"], INK, img, 10, 4)
    grid(["kk.kkk."], INK, img, 3, 11)
    grid(["gGg", "GyG", "gGg"], BRASS, img, 10, 9)  # the Gearwright's brass seal
    return [outline(img, "#3a2c18")]


def book(cover, light, shadow, spine, plate, rivet, x0, y0, x1, y1):
    img = blank()
    px = img.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if x < x0 + 2:
                c = plate if y in (y0 + 2, y1 - 2) else spine
            elif y == y0 or x == x0 + 2:
                c = light
            elif y == y1 or x == x1:
                c = shadow
            else:
                c = cover
            px[x, y] = rgba(c)
    for y in range(y0 + 1, y1 + 1):  # page edges
        px[x1 + 1, y] = rgba("#e8dcc0" if y % 2 else "#bfb08f")
    for cx, cy in ((x0 + 2, y0), (x1 - 1, y0), (x0 + 2, y1 - 1), (x1 - 1, y1 - 1)):  # corner plates
        for a in range(2):
            for b in range(2):
                px[cx + a, cy + b] = rgba(plate)
        if rivet:
            px[cx + (1 if cx > x0 + 2 else 0), cy + (1 if cy > y0 else 0)] = rgba(rivet)
    return img


def foundry_codex():
    img = book("#454950", "#6f747d", "#2f3237", "#24262b", "#8b9197", "#d6dbe3", 2, 1, 12, 14)
    glow = {"F": "#ffd36b", "f": "#ff8c1a", "x": "#7a2a06"}
    grid([".F.F.", "FfffF", ".fxf.", "FfffF", ".F.F."], glow, img, 6, 5)
    grid(["ffffff"], {"f": "#c2410c"}, img, 5, 11)  # a molten seam
    return [outline(img, "#121316")]


def rune_primer():
    img = book("#6b3a20", "#8f5530", "#4a2614", "#3a1d0e", "#b8873f", None, 3, 3, 11, 13)
    grid(RUNE, {"k": "#5ef0ff"}, img, 6, 5)
    return [outline(img, "#1f0f07")]


def aether_core(frames=6):
    out = []
    for f in range(frames):
        img = blank()
        px = img.load()
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * f / frames)
        for y in range(16):
            for x in range(16):
                dx, dy = x - 7.5, y - 7.5
                d = math.hypot(dx, dy)
                if d <= 5.0:
                    lit = d / 5.0 - 0.18 * (-(dx + dy) / 7.1)
                    core = 1.4 + 1.2 * pulse
                    if d < core:
                        c = "#f0feff"
                    elif lit < 0.45:
                        c = "#8ff6ff"
                    elif lit < 0.7:
                        c = "#3cc8e6"
                    elif lit < 0.9:
                        c = "#1f8fb0"
                    else:
                        c = "#145f7a"
                    px[x, y] = rgba(c)
        for y in range(16):  # a brass cage: one meridian and the equator
            for x in range(16):
                dx, dy = x - 7.5, y - 7.5
                mer = abs((dx / 2.3) ** 2 + (dy / 5.6) ** 2 - 1) < 0.22 and abs(dy) < 5.4
                equ = abs((dx / 5.6) ** 2 + (dy / 1.7) ** 2 - 1) < 0.25 and dy > -0.5
                if mer or equ:
                    lit = -(dx + dy)
                    px[x, y] = rgba(BRASS["y"] if lit > 3 else BRASS["G"] if lit > -3 else BRASS["g"])
        for x in (7, 8):  # caps
            px[x, 1] = rgba(BRASS["G"])
            px[x, 14] = rgba(BRASS["g"])
        out.append(outline(img, "#0b1220"))
    return out


def memory_shard(frames=6):
    rows = [
        "................",
        "........h.......",
        ".......hld......",
        ".......hlmd.....",
        "......hllmd.....",
        "......hlmmd.....",
        ".....hlmcmdd....",
        ".....hlccmd.....",
        ".....llmcmdd....",
        "....hlmmmdd.....",
        "....llmmmdd.....",
        "....lmmmdd......",
        "....mmmdd.......",
        ".....mdd........",
        "......d.........",
        "................",
    ]
    check("memory_shard", rows)
    pal = {"d": "#4b2a78", "m": "#7a4fc0", "l": "#a98be8", "h": "#e2d4ff", "c": "#5ef0ff"}
    brighter = {"d": "m", "m": "l", "l": "h", "h": "h", "c": "c"}
    out = []
    for f in range(frames):
        band = 4 + f * 4  # a glint sweeping down the crystal
        shifted = []
        for y, row in enumerate(rows):
            shifted.append("".join(brighter[ch] if ch != "." and band <= x + y < band + 2 else ch
                                   for x, ch in enumerate(row)))
        out.append(outline(grid(shifted, pal), "#24133a"))
    return out


def relay_kit():
    rows = [
        "................",
        "................",
        "....A...........",
        "...Aa.....eEEe..",
        "...Aav....ekEe..",
        "....av....eEke..",
        "..FFFFFFFFFFFF..",
        "..FllllllllllF..",
        "..FLLLLLLLLLLF..",
        "..sFFFFgGgFFFs..",
        "..LlLLLgGgLLLD..",
        "..LlLLLLLLLLLD..",
        "..LlLLLLLLLLLD..",
        "..LlLLLLLLLLLD..",
        "..DDDDDDDDDDDD..",
        "................",
    ]
    check("relay_kit", rows)
    pal = {"L": "#8a5a32", "l": "#a8763f", "D": "#5c3a1e", "F": "#6e4724", "s": "#3d2614",
           "g": "#d9a521", "G": "#fff1a8", "A": "#d7b4ff", "a": "#9a5cc6", "v": "#5e3590",
           "e": "#2e7040", "E": "#4a9a5c", "k": "#d9874f"}
    return [outline(grid(rows, pal), "#1f140c")]


def salvaged_circuitry():
    rows = [
        "................",
        "................",
        "..lllllll.......",
        "..lmmmmmmll.....",
        "..lmCccccmml....",
        "..lmwmwmwmcml...",
        "..lmkKKkkmcml...",
        "..lmkKkkkmcmmd..",
        "..lmkkkkkmcmmd..",
        "..lmwmwmwmcmmd..",
        "..lmCcccccCmmd..",
        "..lmmmmmmmmmdd..",
        "..ldmmCmmmdd....",
        "...ddddddd......",
        "................",
        "................",
    ]
    check("salvaged_circuitry", rows)
    pal = {"d": "#1d4a2a", "m": "#2e7040", "l": "#4a9a5c", "c": "#c98a4a", "C": "#f2c94c",
           "k": "#1b1b22", "K": "#4a4a58", "w": "#c9ced6"}
    return [outline(grid(rows, pal), "#0b1a10")]


def rubbing():
    img = sheet(3, 2, 12, 13)
    px = img.load()
    for y in range(3, 13):
        for x in range(4, 12):
            px[x, y] = rgba("#3a3a40" if (x + y) % 3 else "#56565e")
    grid(RUNE, {"k": PARCHMENT["P"]}, img, 6, 5)
    return [outline(img, "#2b2418")]


def torn_page():
    img = sheet(3, 1, 12, 14)
    px = img.load()
    for y, cut in zip(range(1, 15), [12, 12, 11, 12, 11, 10, 11, 12, 12, 11, 10, 11, 12, 12]):
        for x in range(cut + 1, 13):
            px[x, y] = (0, 0, 0, 0)
        px[cut, y] = rgba(PARCHMENT["q"])
    grid(RUNE, {"k": "#4a3520"}, img, 5, 2)
    ink = {"k": "#5a4128"}
    for y, marks in ((9, "kk.k.kk"), (11, "k.kkk.k"), (13, "kkk.k")):
        grid([marks], ink, img, 4, y)
    return [outline(img, "#3a2c18")]


def hearthstone(frames=4):
    out = []
    for f in range(frames):
        img = blank()
        px = img.load()
        for y in range(16):
            for x in range(16):
                dx, dy = (x - 7.5) / 5.6, (y - 8.0) / 6.2
                if dx * dx + dy * dy <= 1:
                    lit = -(dx + dy) * 0.7 + 0.15
                    c = "#b8c1d3" if lit > 0.75 else "#8f99ad" if lit > 0.2 else "#6b7487" if lit > -0.45 else "#4a5263"
                    px[x, y] = rgba(c)
        cells = {(5 + fx, 4 + fy): ch for fy, row in enumerate(FLAME) for fx, ch in enumerate(row) if ch != "."}
        for (x, y) in cells:  # carved groove below-right of the flame
            if (x + 1, y + 1) not in cells and px[x + 1, y + 1][3]:
                px[x + 1, y + 1] = rgba("#3a2a24")
        flicker = [(5, 7), (6, 8), (7, 7), (6, 9)][f]
        for (x, y), ch in cells.items():
            c = "#ffd36b" if ch == "o" else "#ff8c1a"
            if (x, y) == flicker:
                c = "#fff6d0"
            px[x, y] = rgba(c)
        out.append(outline(img, "#1c1f27"))
    return out


def presidential_pants():
    rows = [
        "................",
        "................",
        "...bbbbyybbbb...",
        "...NNnnyGnnnb...",
        "...Nnnnnnnnnb...",
        "...Nnnnnnnnnb...",
        "...Nnnnbbnnnb...",
        "...Ngnn..Nngb...",
        "...Ngnn..Nngb...",
        "...Ngwn..Nngb...",
        "...Ngnn..Nngb...",
        "...Ngnn..Nngb...",
        "...Ngnn..Nngb...",
        "...Ngnb..Nngb...",
        "...yyyy..yyyy...",
        "................",
    ]
    check("presidential_pants", rows)
    pal = {"n": "#24366b", "N": "#3a52a0", "b": "#16224a", "g": "#d9a521", "y": "#f2c94c",
           "G": "#fff1a8", "w": "#ffffff"}
    return [outline(grid(rows, pal), "#0b1022")]


# id -> (display name, what it's for, frames)
ITEMS = [
    ("flint_shard", "Flint Shard", "Age I: knapped from gravel", flint_shard),
    ("flint_hatchet", "Flint Hatchet", "Age I: the first axe", flint_hatchet),
    ("hearthstone", "Hearthstone", "Once-a-day home recall", hearthstone),
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
    # hotbar mock-up at 4x
    sy = h - 120
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
