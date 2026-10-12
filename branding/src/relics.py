"""The Ascendancy's relic arsenal: 16x16 textures for each relic, sealed and awakened.

Run from the branding/ folder:  python src/relics.py
Writes out/relics/<id>.png (awakened, animated) and <id>_sealed.png, and drafts/relics_preview.png.

Relics are found sealed from the Age of Steam on and awakened at the restored Convergence Spire in the
Age of Reclamation. Sealed, their aether crystal is dead grey; awakened, it glows and pulses.
Built on the renderer in items.py: layers of material/tone pixels, lit from the top left.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from items import FONT, FONT_BOLD, MATS, Mat, from_rows, layer, render, wrap  # noqa: E402

OUT = "out/relics"

MATS["aether"] = Mat(["#3a0f63", "#5a1c99", "#8235d6", "#ad6cff", "#d6b3ff", "#f8efff"], "#1f0838", glow=True)
MATS["aether_dead"] = Mat(["#1d1a23", "#2a2631", "#3a3443", "#4b4456", "#5f576c", "#7a7188"], "#110f15", shiny=True)
MATS["quartz"] = Mat(["#6c6976", "#93909d", "#b9b6c4", "#d8d5e1", "#eeecf3", "#ffffff"], "#3b3942", shiny=True)


# ---------- diagonal weapons: the blade runs from the bottom left to the top right ----------
# Along the weapon, d = x - y grows toward the tip; across it, s = x + y, centred on 15.
def diagonal(spec, ae):
    """spec: list of (d0, d1, half_width, material, tone, aether_core) segments, plus extras."""
    px = {}
    for d0, d1, hw, mat, tone, core in spec:
        for x in range(16):
            for y in range(16):
                d, s = x - y, x + y
                if d0 <= d <= d1 and abs(s - 15) <= hw:
                    on_core = core and s == 15
                    px[(x, y)] = (ae, 3) if on_core else (mat, tone)
    return px


def cross(d, half, mat, tone):
    """A guard across the weapon at position d."""
    return {(x, y): (mat, tone) for x in range(16) for y in range(16) if x - y in (d, d - 1) and abs(x + y - 15) <= half}


def aether_blade(ae):
    blade = diagonal([(-1, 11, 1, "quartz", 3, True), (12, 13, 0, "quartz", 4, False)], ae)
    guard = cross(-2, 3, "iron", 3)
    gem = {(6, 8): (ae, 4)}
    grip = diagonal([(-11, -3, 0, "leather", 3, False)], ae)
    pommel = {(1, 14): (ae, 4), (2, 14): ("iron", 2), (1, 13): ("iron", 2)}
    return [layer(blade), layer(guard), layer(gem, form="none"), layer(grip, form="cylv"), layer(pommel)]


def resonance_tachi(ae):
    # a slim single-edged blade with an aether edge along its lower side, a round copper guard
    blade = {}
    for x in range(16):
        for y in range(16):
            d, s = x - y, x + y
            bend = 1 if d > 6 else 0  # a slight curve toward the tip
            if -2 <= d <= 12 and s - bend in (15, 16):
                blade[(x, y)] = (ae, 3) if s - bend == 16 else ("quartz", 4)
    tsuba = from_rows([".cc.", "cccc", "cccc", ".cc."], {"c": ("copper", 3)}, 4, 8)
    grip = diagonal([(-12, -5, 0, "leather", 2, False)], ae)
    wrap_ = {(x, y): ("twine", 4) for (x, y) in grip if (x + y) % 2 == 0 and (x - y) % 4 == 0}
    return [layer(blade), layer(tsuba, form="round"), layer(grip, form="cylv"), layer(wrap_, form="none", shadow="none")]


def spireguard_greatsword(ae):
    blade = diagonal([(-2, 10, 2, "quartz", 3, True), (11, 13, 1, "quartz", 4, False)], ae)
    for p in list(blade):
        if abs(p[0] + p[1] - 15) == 2:
            blade[p] = ("iron", 3)  # dark iron edges
    guard = cross(-3, 4, "iron", 2)
    guard.update({(x, y): ("copper", 4) for (x, y) in guard if abs(x + y - 15) == 4})
    grip = diagonal([(-11, -5, 0, "leather", 3, False)], ae)
    pommel = {(1, 14): (ae, 4), (2, 13): ("iron", 3)}
    return [layer(blade), layer(guard), layer(grip, form="cylv"), layer(pommel)]


def convergence_glaive(ae):
    shaft = diagonal([(-15, 6, 0, "iron", 3, False)], ae)
    head = from_rows([
        "....qQ",
        "...qQQ",
        "..qQQ.",
        ".qQQ..",
        "qQA...",
        "QA....",
    ], {"q": ("quartz", 2), "Q": ("quartz", 4), "A": (ae, 3)}, 10, 0)
    ring = from_rows([".c.", "c.c", ".c."], {"c": ("copper", 4)}, 8, 5)
    return [layer(shaft, form="cylv"), layer(head), layer(ring, form="none")]


def phase_dagger(ae, f=0):
    blade = diagonal([(2, 9, 1, "quartz", 3, True), (10, 11, 0, "quartz", 4, False)], ae)
    ghost = {(x + 2, y - 2): (ae, 1) for (x, y) in blade if abs(x + y - 15) == 1 and (x - y) % 2 == 0} if ae == "aether" else {}
    guard = cross(1, 2, "iron", 3)
    grip = diagonal([(-6, 0, 0, "leather", 3, False)], ae)
    pommel = {(5, 10): (ae, 4)}
    layers = [layer(blade), layer(guard), layer(grip, form="cylv"), layer(pommel, form="none")]
    if ghost and f % 2 == 1:
        layers.insert(0, layer(ghost, form="none", shadow="none"))
    return layers


def twin_arc_sabres(ae, f=0):
    one = diagonal([(-3, 9, 0, "quartz", 4, False)], ae)
    one.update(diagonal([(-12, -5, 0, "leather", 3, False)], ae))
    one.update(cross(-4, 1, "copper", 3))
    two = {(15 - x, y): v for (x, y), v in one.items()}  # mirrored
    arc = {}
    if ae == "aether":
        pts = [(4, 3), (5, 2), (6, 3), (7, 2), (8, 3), (9, 2), (10, 3), (11, 2)] if f % 2 == 0 else \
              [(4, 2), (5, 3), (6, 2), (7, 3), (8, 2), (9, 3), (10, 2), (11, 3)]
        arc = {p: (ae, 4) for p in pts}
    else:
        arc = {(4, 3): (ae, 2), (11, 3): (ae, 2)}
    return [layer(two), layer(one), layer(arc, form="none", shadow="none")]


def gravity_maul(ae):
    shaft = diagonal([(-15, 2, 0, "iron", 3, False)], ae)
    head = from_rows([
        "..iIIIi.",
        ".iQQQQIi",
        "iQQaaQQi",
        "iQaAAaQi",
        "iQaAAaQi",
        "iQQaaQQi",
        ".iQQQQi.",
        "..iiii..",
    ], {"i": ("iron", 2), "I": ("iron", 4), "Q": ("quartz", 3), "a": (ae, 2), "A": (ae, 4)}, 7, 1)
    return [layer(shaft, form="cylv"), layer(head, form="round", gain=0.9)]


def pulse_gauntlets(ae):
    hand = from_rows([
        "...QqQqQq.......",
        "...QqQqQq.......",
        "..IQqQqQqI......",
        "..IIIIIIII......",
        "..IiiiiiiI......",
        "..IiAAAAiI......",
        "..IiAAAAiII.....",
        "..IiiiiiiIQI....",
        "..IIIIIIIIQI....",
        "...IcccccI......",
        "...IcccccI......",
        "...IIIIIII......",
    ], {"Q": ("quartz", 4), "q": ("quartz", 2), "I": ("iron", 3), "i": ("iron", 2), "A": (ae, 3), "c": ("copper", 3)}, 3, 2)
    return [layer(hand)]


def aegis_plate(ae):
    shield = {}
    for y in range(1, 15):
        for x in range(2, 14):
            w = 6 if y < 9 else 6 - (y - 8)
            if abs(x - 7.5) <= w:
                rim = abs(x - 7.5) > w - 1 or y == 1
                shield[(x, y)] = ("iron", 3) if rim else ("quartz", 3)
    emblem = from_rows([".aa.", "a..a", "a..a", ".aa."], {"a": (ae, 3)}, 6, 5)
    core = {(7, 6): (ae, 5), (8, 7): (ae, 4)}
    return [layer(shield, form="round", gain=0.6), layer(emblem, form="none", shadow="inset"), layer(core, form="none")]


def aether_pistol(ae):
    gun = from_rows([
        "................",
        "................",
        "................",
        "................",
        "..qQQQQQQQQQQQc.",
        "..QQQQQQQQQQQQc.",
        "..iIIaAaIIIIIIi.",
        "..iiIaAaIiiiii..",
        "...iIiiiI.......",
        "....LLLi.I......",
        "....LLL..I......",
        "....LLLiii......",
        "....LLL.........",
        "...iLLL.........",
        "...iiii.........",
    ], {"q": ("quartz", 2), "Q": ("quartz", 4), "I": ("iron", 3), "i": ("iron", 2), "L": ("leather", 3),
        "a": (ae, 2), "A": (ae, 4), "c": ("copper", 4)})
    return [layer(gun)]


def aether_rifle(ae):
    gun = from_rows([
        "................",
        "................",
        "................",
        "................",
        "................",
        "......ii........",
        "qQQQQQQQQQQQQQQc",
        "QQQQaAaAaAQQQQQc",
        "iIIIIIIIIIIIIIi.",
        "LLLLiiIi........",
        "LLLL..I.........",
        "LLL...ii........",
        "LL..............",
    ], {"q": ("quartz", 2), "Q": ("quartz", 4), "I": ("iron", 3), "i": ("iron", 2), "L": ("wood", 3),
        "a": (ae, 2), "A": (ae, 4), "c": ("copper", 4)})
    return [layer(gun)]


def starfall_bow(ae):
    limb = {}
    for y in range(1, 15):
        t = (y - 7.5) / 6.5
        x = round(4 + 6 * t * t)
        limb[(x, y)] = ("quartz", 3)
        if abs(t) > 0.3:
            limb[(x + (1 if t < 0 else 1), y)] = ("quartz", 4)
    grip = {(4, y): ("leather", 3) for y in (6, 7, 8, 9)}
    grip.update({(5, y): ("leather", 2) for y in (7, 8)})
    string = {(10, y): (ae, 3) for y in range(1, 15)}
    tips = {(10, 1): ("copper", 4), (10, 14): ("copper", 4)}
    shard = from_rows(["..A", ".a.", "a.."], {"A": (ae, 5), "a": (ae, 3)}, 11, 5)
    return [layer(string, form="none", shadow="none"), layer(limb), layer(grip, form="cylv"), layer(tips),
            layer(shard, form="none", shadow="none")]


def convergence_lance(ae):
    gun = from_rows([
        "................",
        "................",
        "................",
        "....c..c..c.....",
        "...cQcQQcQQc....",
        "iiiQQQQQQQQQQQAA",
        "IIIQaaAaaAaaQQAA",
        "iiiQQQQQQQQQQQAA",
        "...cQcQQcQQc....",
        "....cIIcI.c.....",
        ".....LLL........",
        ".....LLL........",
        "......LL........",
    ], {"Q": ("quartz", 3), "I": ("iron", 3), "i": ("iron", 2), "L": ("leather", 3), "c": ("copper", 4),
        "a": (ae, 2), "A": (ae, 4)})
    return [layer(gun)]


def menders_censer(ae):
    chain = {(8, y): ("iron", 4 if y % 2 else 2) for y in range(0, 5)}
    body = {}
    for y in range(5, 14):
        for x in range(3, 13):
            if (x - 7.5) ** 2 / 20 + (y - 9.5) ** 2 / 16 <= 1:
                body[(x, y)] = ("brass", 3)
    holes = {(5, 9): (ae, 4), (8, 8): (ae, 5), (10, 10): (ae, 4), (7, 11): (ae, 3), (9, 12): (ae, 3)}
    lid = {(x, 5): ("quartz", 4) for x in range(6, 10)}
    return [layer(chain, form="none"), layer(body, form="round"), layer(lid), layer(holes, form="none", shadow="inset")]


def sentinel_core(ae):
    sphere = {(x, y): ("iron", 3) for x in range(16) for y in range(16) if (x - 7.5) ** 2 + (y - 8) ** 2 <= 26}
    eye = {(x, y): (ae, 4) for x in range(16) for y in range(16) if (x - 7.5) ** 2 + (y - 8) ** 2 <= 4}
    band = {(x, 8): ("quartz", 4) for x in range(2, 14) if (x - 7.5) ** 2 > 4}
    fins = from_rows(["Q..............Q", "QQ............QQ"], {"Q": ("quartz", 3)}, 0, 7)
    return [layer(fins), layer(sphere, form="round", gain=1.1), layer(band, form="none"), layer(eye, form="round", shadow="inset")]


def stasis_pylon(ae):
    base = from_rows(["iIIIIIIi", "iiiiiiii"], {"I": ("iron", 3), "i": ("iron", 2)}, 4, 13)
    column = {(x, y): ("quartz", 3) for x in range(6, 10) for y in range(6, 13)}
    column.update({(x, y): ("quartz", 3) for x in range(7, 9) for y in range(5, 6)})
    seam = {(7, y): (ae, 3) for y in range(7, 13)}
    crystal = from_rows([".A.", "AaA", "aAa", ".a."], {"A": (ae, 5), "a": (ae, 3)}, 6, 1)
    return [layer(base), layer(column, form="cylv"), layer(seam, form="none", shadow="inset"), layer(crystal)]


def aether_cell(ae, f=0):
    """The Aether Cell that awakens a relic: a glass vial in copper caps. Crafted empty, charged in AE2's Charger."""
    glass = {(x, y): ("quartz", 4) for x in (5, 10) for y in range(4, 13)}
    fill = {(x, y): (ae, 3) for x in range(6, 10) for y in range(4, 13)} if ae == "aether" else {}
    if ae == "aether":
        for x in range(6, 10):
            fill[(x, 4 + (f * 2) % 8)] = (ae, 5)  # a bubble rising
    caps = {}
    caps.update({(x, y): ("copper", 3) for x in range(4, 12) for y in (2, 3, 13, 14)})
    caps.update({(x, 1): ("copper", 4) for x in range(6, 10)})
    bands = {(x, 8): ("iron", 3) for x in (5, 10)}
    return [layer(fill, form="cylv", shadow="none"), layer(glass, form="none"), layer(caps, form="cylv"), layer(bands, form="none")]


# id, name, how it fights, signature, drawing function (some take a frame for their animation)
RELICS = [
    ("aether_blade", "Aether Blade", "Longsword", "Hits leave aether sparks; a dash strike closes the gap", aether_blade),
    ("resonance_tachi", "Resonance Tachi", "Tachi", "A perfect parry releases a counter-wave", resonance_tachi),
    ("spireguard_greatsword", "Spireguard Greatsword", "Greatsword", "A ground slam sends out a shockwave", spireguard_greatsword),
    ("convergence_glaive", "Convergence Glaive", "Spear", "A charged thrust pierces a whole line", convergence_glaive),
    ("phase_dagger", "Phase Dagger", "Dagger", "Blink behind your target", phase_dagger),
    ("twin_arc_sabres", "Twin Arc Sabres", "Dual swords", "Lightning arcs between everything both blades hit", twin_arc_sabres),
    ("gravity_maul", "Gravity Maul", "Axe moveset", "A slam drags nearby enemies in", gravity_maul),
    ("pulse_gauntlets", "Pulse Gauntlets", "Fists", "Every third hit discharges a pulse", pulse_gauntlets),
    ("aegis_plate", "Aegis Plate", "Shield", "Raise it to throw a barrier over allies behind you", aegis_plate),
    ("aether_pistol", "Aether Pistol", "Gun", "Charged shots that chain to a second target", aether_pistol),
    ("aether_rifle", "Aether Rifle", "Gun", "A piercing beam through every enemy in line", aether_rifle),
    ("convergence_lance", "Convergence Lance", "Heavy gun", "A long charge, then a beam that breaks shields", convergence_lance),
    ("starfall_bow", "Starfall Bow", "Bow", "Arrows split into homing shards", starfall_bow),
    ("menders_censer", "Mender's Censer", "Held", "Swing it to heal allies around you", menders_censer),
    ("sentinel_core", "Sentinel Core", "Held", "Wakes a construct that fights beside you for 30 s", sentinel_core),
    ("stasis_pylon", "Stasis Pylon", "Thrown", "Plants a pylon that slows and weakens enemies near it", stasis_pylon),
]


def draw(fn, ae, f=0):
    try:
        layers = fn(ae, f)
    except TypeError:
        layers = fn(ae)
    if ae == "aether":  # a slow pulse in the crystal
        for L in layers:
            for p, (m, t) in L["px"].items():
                if m == "aether":
                    L["px"][p] = (m, min(5, t + (1 if f in (1, 2) else 0)))
    return render(layers)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs("drafts", exist_ok=True)
    cards = []
    for rid, name, kind, sig, fn in RELICS:
        sealed = draw(fn, "aether_dead")
        sealed.save(f"{OUT}/{rid}_sealed.png")
        frames = [draw(fn, "aether", f) for f in range(4)]
        strip = Image.new("RGBA", (16, 64))
        for i, fr in enumerate(frames):
            strip.paste(fr, (0, 16 * i))
        strip.save(f"{OUT}/{rid}.png")
        with open(f"{OUT}/{rid}.png.mcmeta", "w") as fh:
            fh.write('{"animation": {"frametime": 5, "interpolate": false}}\n')
        cards.append((name, kind, sig, sealed, frames[1]))
    empty = render(aether_cell("aether_dead"))
    empty.save(f"{OUT}/aether_cell_empty.png")
    cell_frames = [draw(aether_cell, "aether", f) for f in range(4)]
    strip = Image.new("RGBA", (16, 64))
    for i, fr in enumerate(cell_frames):
        strip.paste(fr, (0, 16 * i))
    strip.save(f"{OUT}/aether_cell.png")
    with open(f"{OUT}/aether_cell.png.mcmeta", "w") as fh:
        fh.write('{"animation": {"frametime": 5, "interpolate": false}}\n')
    cards.append(("Aether Cell", "Awakens a relic", "Crafted empty from amethyst, quartz and copper; charged in an AE2 Charger",
                  empty, cell_frames[1]))

    cols, scale, pad = 4, 7, 30
    tile = 16 * scale
    cw = tile * 2 + 40
    ch = tile + 120
    rows = (len(cards) + cols - 1) // cols
    w, h = pad + cols * (cw + pad), 110 + rows * (ch + pad)
    img = Image.new("RGBA", (w, h), "#14121a")
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT_BOLD, 30)
    label = ImageFont.truetype(FONT, 16)
    small = ImageFont.truetype(FONT, 13)
    d.text((pad, 22), "THE ASCENDANCY'S RELICS", font=title, fill="#e8d9b5")
    d.text((pad, 62), "Sealed (left) and awakened (right), 16x16 at 7x. Found sealed from the Age of Steam; awakened at the restored Spire.", font=small, fill="#9c8f78")
    for i, (name, kind, sig, sealed, awake) in enumerate(cards):
        x = pad + (i % cols) * (cw + pad)
        y = 100 + (i // cols) * (ch + pad)
        d.rectangle([x - 8, y - 8, x + cw - 8, y + ch - 8], fill="#1c1924")
        img.alpha_composite(sealed.resize((tile, tile), Image.NEAREST), (x, y))
        img.alpha_composite(awake.resize((tile, tile), Image.NEAREST), (x + tile + 24, y))
        ly = y + tile + 8
        d.text((x, ly), name.upper(), font=label, fill="#e8d9b5")
        d.text((x, ly + 21), kind, font=small, fill="#b99bee")
        ly += 40
        for line in wrap(d, sig, small, cw - 16):
            d.text((x, ly), line, font=small, fill="#9c8f78")
            ly += 17
    img.save("drafts/relics_preview.png")
    print("wrote", OUT, "and drafts/relics_preview.png")


if __name__ == "__main__":
    main()
