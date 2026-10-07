"""Remming coin textures: one 16x16 item texture per Create: Numismatics denomination.

Run from the branding/ folder:  python src/coins.py
Writes textures to out/coins/ and a preview sheet to drafts/remmings_preview.png.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = "out/coins"
FONT = "fonts/Silkscreen-Regular.ttf"
FONT_BOLD = "fonts/Silkscreen-Bold.ttf"

# outline, shadow, base, light, highlight, engrave
PALETTES = {
    "copper": ["#3b1d10", "#7a3b1f", "#b8653a", "#d9874f", "#f2b880", "#6b3219"],
    "bronze": ["#3a2a12", "#7a5a26", "#a8823f", "#c9a35a", "#ead08c", "#5e4520"],
    "iron":   ["#222428", "#5a5e63", "#8b9197", "#b4bac0", "#e3e8ec", "#4a4e53"],
    "silver": ["#2b3038", "#6f7a88", "#aab6c4", "#cfd9e4", "#ffffff", "#5a6573"],
    "gold":   ["#3d2a05", "#9a6b0e", "#d9a521", "#f2c94c", "#fff1a8", "#8a5a08"],
    "aether": ["#0b1220", "#1f2b4a", "#2e3d66", "#45598f", "#7d93c9", "#14203a"],
}

# Numismatics item id -> (Remming name, value in spurs, metal, radius, edge)
COINS = [
    ("spur",     "Copper Remming", 1,    "copper", 6.1, "smooth"),
    ("bevel",    "Bronze Remming", 8,    "bronze", 6.4, "smooth"),
    ("sprocket", "Iron Remming",   16,   "iron",   6.3, "cog"),
    ("cog",      "Silver Remming", 64,   "silver", 6.7, "reeded"),
    ("crown",    "Gold Remming",   512,  "gold",   6.9, "cog"),
    ("sun",      "Aether Remming", 4096, "aether", 6.9, "cog"),
]

# The Remnant stamp: a raised hearth flame, 5 wide x 7 tall ('#' body, 'o' inner core).
FLAME = [
    "..#..",
    ".##..",
    ".###.",
    "##o##",
    "#ooo#",
    "#ooo#",
    ".###.",
]

C = 7.5  # centre of a 16x16 canvas


def inside(x, y, r, edge):
    dx, dy = x - C, y - C
    d = math.hypot(dx, dy)
    if edge == "cog":
        a = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
        tooth = (a * 10) % 1.0 < 0.5
        return d <= (r + 0.9 if tooth else r)
    return d <= r


def rgba(c):
    return Image.new("RGBA", (1, 1), c).getpixel((0, 0))


def coin(metal, r, edge, frame=0, frames=1):
    pal = [rgba(c) for c in PALETTES[metal]]
    out, shadow, base, light, high, eng = pal
    glow = metal == "aether"
    cyan = [rgba("#5ef0ff"), rgba("#d8fdff"), rgba("#1f8fb0")]
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    mask = [[inside(x, y, r, edge) for x in range(16)] for y in range(16)]
    for y in range(16):
        for x in range(16):
            if not mask[y][x]:
                continue
            dx, dy = x - C, y - C
            d = math.hypot(dx, dy)
            lit = 0.5 - 0.5 * (dx / r * 0.707 + dy / r * 0.707)  # light from the top left
            if d > r - 1.2:  # outer rim, bevelled
                col = high if lit > 0.7 else light if lit > 0.48 else shadow
                if edge == "reeded" and (x + y) % 2 == 0:
                    col = shadow if lit <= 0.48 else base
            elif r - 2.6 < d <= r - 1.6:  # inner groove: dark on the lit side, bright on the shaded side
                col = shadow if lit > 0.5 else high
                if glow:
                    a = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                    col = cyan[0] if abs((a * frames - frame) % frames) < 0.7 else cyan[2]
            else:
                col = light if lit > 0.82 else base if lit > 0.22 else shadow
            px[x, y] = col
    for y in range(16):  # dark outline around the whole coin
        for x in range(16):
            if mask[y][x]:
                continue
            if any(0 <= x + a < 16 and 0 <= y + b < 16 and mask[y + b][x + a]
                   for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = out
    ox, oy = 6, 4  # raised flame with a drop shadow below-right
    cells = {(ox + fx, oy + fy): ch for fy, row in enumerate(FLAME) for fx, ch in enumerate(row) if ch != "."}
    for (x, y) in cells:
        sx, sy = x + 1, y + 1
        if (sx, sy) not in cells and mask[sy][sx]:
            px[sx, sy] = cyan[2] if glow else eng
    for (x, y), ch in cells.items():
        if glow:
            band = (y - oy + frame * 2) % 7 in (0, 1)
            px[x, y] = cyan[1] if (ch == "o" or band) else cyan[0]
        else:
            edge_lit = (x - 1, y) not in cells or (x, y - 1) not in cells
            px[x, y] = high if (ch == "o" or edge_lit) else light
    if metal == "gold":  # a red inlay at the flame's heart
        px[8, 8] = (192, 57, 43, 255)
        px[8, 9] = (150, 35, 28, 255)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs("drafts", exist_ok=True)
    tiles = []
    for cid, name, value, metal, r, edge in COINS:
        if metal == "aether":
            frames = 4
            strip = Image.new("RGBA", (16, 16 * frames))
            for f in range(frames):
                strip.paste(coin(metal, r, edge, f, frames), (0, 16 * f))
            strip.save(f"{OUT}/{cid}.png")
            with open(f"{OUT}/{cid}.png.mcmeta", "w") as fh:
                fh.write('{"animation": {"frametime": 5, "interpolate": false}}\n')
            tiles.append((name, value, coin(metal, r, edge, 0, frames)))
        else:
            img = coin(metal, r, edge)
            img.save(f"{OUT}/{cid}.png")
            tiles.append((name, value, img))

    # preview sheet: each coin at 16x, plus a row of inventory slots at 4x
    scale = 16
    cell = 16 * scale
    pad = 40
    w = pad + len(tiles) * (cell + pad)
    h = 640
    sheet = Image.new("RGBA", (w, h), "#14121a")
    d = ImageDraw.Draw(sheet)
    title = ImageFont.truetype(FONT_BOLD, 34)
    label = ImageFont.truetype(FONT, 22)
    small = ImageFont.truetype(FONT, 18)
    d.text((pad, 18), "REMMINGS - draft coin textures (16x16, shown at 16x)", font=title, fill="#e8d9b5")
    for i, (name, value, img) in enumerate(tiles):
        x = pad + i * (cell + pad)
        sheet.alpha_composite(img.resize((cell, cell), Image.NEAREST), (x, 80))
        d.text((x, 80 + cell + 12), name.upper(), font=label, fill="#e8d9b5")
        d.text((x, 80 + cell + 42), f"= {value} copper", font=small, fill="#9c8f78")
    # inventory slot mock-up at 4x
    sy = 80 + cell + 100
    d.text((pad, sy), "In an inventory (4x):", font=small, fill="#9c8f78")
    sx = pad
    for i, (_, _, img) in enumerate(tiles):
        x = sx + i * 76
        y = sy + 30
        d.rectangle([x, y, x + 71, y + 71], fill="#8b8b8b")
        d.line([x, y, x + 71, y], fill="#373737", width=4)
        d.line([x, y, x, y + 71], fill="#373737", width=4)
        d.line([x, y + 71, x + 71, y + 71], fill="#ffffff", width=4)
        d.line([x + 71, y, x + 71, y + 71], fill="#ffffff", width=4)
        sheet.alpha_composite(img.resize((64, 64), Image.NEAREST), (x + 4, y + 4))
        count = ["64", "12", "7", "3", "2", "1"][i]
        if count != "1":
            d.text((x + 70 - 14 * len(count), y + 44), count, font=label, fill="#3f3f3f")
            d.text((x + 68 - 14 * len(count), y + 42), count, font=label, fill="#ffffff")
    sheet.save("drafts/remmings_preview.png")
    print("wrote", OUT, "and drafts/remmings_preview.png")


if __name__ == "__main__":
    main()
