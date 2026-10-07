"""Remnant emblem, logo, title/loading backgrounds and window icons.

Run from the branding/ folder:  python src/brand.py
Writes finished assets to out/ and review composites to drafts/.
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

LOGO_FONT = "fonts/CinzelDecorative-Black.ttf"
SUB_FONT = "fonts/Cinzel[wght].ttf"
PIXEL_FONT = "fonts/Silkscreen-Regular.ttf"


def vgrad(size, stops):
    """Vertical gradient image from (position 0..1, hex) stops."""
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    cols = [(p, Image.new("RGBA", (1, 1), c).getpixel((0, 0))) for p, c in stops]
    for y in range(h):
        t = y / max(1, h - 1)
        for (p0, c0), (p1, c1) in zip(cols, cols[1:]):
            if p0 <= t <= p1:
                k = (t - p0) / max(1e-6, p1 - p0)
                c = tuple(int(c0[i] + (c1[i] - c0[i]) * k) for i in range(4))
                d.line([(0, y), (w, y)], fill=c)
                break
    return img


def fill_mask(mask, fill_img):
    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    out.paste(fill_img, (0, 0), mask)
    return out


def flame_mask(size, cx, cy, h, w):
    """A two-tongued hearth flame as an L mask."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    pts = []
    for i in range(121):
        t = i / 120 * 2 * math.pi
        # teardrop body, widest low down
        x = math.sin(t) * w * (0.55 + 0.45 * math.cos(t / 2) ** 2) * (0.5 - 0.5 * math.cos(t)) ** 0.6
        y = -math.cos(t) * h * 0.5
        pts.append((cx + x, cy + y))
    d.polygon(pts, fill=255)
    # side tongue on the left, leaning in
    tongue = [(cx - w * 0.35, cy + h * 0.05), (cx - w * 0.62, cy - h * 0.28), (cx - w * 0.12, cy - h * 0.05)]
    d.polygon(tongue, fill=255)
    return m.filter(ImageFilter.GaussianBlur(h * 0.01))


def emblem(S=1024):
    """Broken gear ring with a hearth flame rising through it, on transparency."""
    c = S / 2
    gear = Image.new("L", (S, S), 0)
    g = ImageDraw.Draw(gear)
    R, r, teeth, th = 0.40 * S, 0.30 * S, 12, 0.055 * S
    poly = []
    for i in range(teeth * 8):
        a = i / (teeth * 8) * 2 * math.pi
        k = (i % 8)
        rad = R + (th if 2 <= k <= 5 else 0)
        poly.append((c + math.cos(a) * rad, c + math.sin(a) * rad))
    g.polygon(poly, fill=255)
    g.ellipse([c - r, c - r, c + r, c + r], fill=0)
    # the break: a wedge knocked out of the upper right, with a jagged edge
    gap = [(c, c)]
    for a in (-75, -62, -55, -40, -30):
        rad = R * 1.4 * (0.9 if a in (-62, -40) else 1.0)
        gap.append((c + math.cos(math.radians(a)) * rad, c + math.sin(math.radians(a)) * rad))
    g.polygon(gap, fill=0)
    brass = vgrad((S, S), [(0, "#fbe3a0"), (0.45, "#c99a3e"), (1, "#5c3a12")])
    outline = gear.filter(ImageFilter.MaxFilter(17))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img = Image.alpha_composite(img, fill_mask(outline, Image.new("RGBA", (S, S), "#160d06")))
    img = Image.alpha_composite(img, fill_mask(gear, brass))
    # flame
    fm = flame_mask((S, S), c, c - 0.02 * S, 0.62 * S, 0.30 * S)
    glow = fill_mask(fm.filter(ImageFilter.GaussianBlur(S * 0.05)), Image.new("RGBA", (S, S), "#ff7a2f"))
    img = Image.alpha_composite(img, glow)
    fo = fm.filter(ImageFilter.MaxFilter(13))
    img = Image.alpha_composite(img, fill_mask(fo, Image.new("RGBA", (S, S), "#3a0d05")))
    fire = vgrad((S, S), [(0, "#ffd36b"), (0.35, "#ff9a3c"), (0.7, "#e2461b"), (1, "#8f1d10")])
    img = Image.alpha_composite(img, fill_mask(fm, fire))
    core = flame_mask((S, S), c, c + 0.08 * S, 0.30 * S, 0.14 * S)
    img = Image.alpha_composite(img, fill_mask(core, vgrad((S, S), [(0, "#fffbe0"), (1, "#ffcf6b")])))
    return img


def logo(em):
    W, H = 2400, 1100
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    e = em.resize((520, 520), Image.LANCZOS)
    img.alpha_composite(e, ((W - 520) // 2, 0))
    font = ImageFont.truetype(LOGO_FONT, 300)
    text = "REMNANT"
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    bb = d.textbbox((0, 0), text, font=font)
    tx, ty = (W - (bb[2] - bb[0])) // 2 - bb[0], 520
    d.text((tx, ty), text, font=font, fill=255)
    glow = fill_mask(m.filter(ImageFilter.GaussianBlur(28)), Image.new("RGBA", (W, H), "#ff6a1f"))
    img = Image.alpha_composite(img, glow)
    shadow = fill_mask(m.filter(ImageFilter.MaxFilter(15)), Image.new("RGBA", (W, H), "#120a05"))
    img = Image.alpha_composite(img, shadow)
    brass = vgrad((W, H), [(0, "#fff3c4"), (0.52, "#f3d58c"), (0.62, "#c99a3e"), (0.8, "#8a5a1c"), (1, "#5c3a12")])
    img = Image.alpha_composite(img, fill_mask(m, brass))
    sub = ImageFont.truetype(SUB_FONT, 64)
    subtitle = "A  BROKEN  WORLD  WORTH  REBUILDING"
    d2 = ImageDraw.Draw(img)
    sb = d2.textbbox((0, 0), subtitle, font=sub)
    d2.text(((W - (sb[2] - sb[0])) // 2, ty + 360), subtitle, font=sub, fill="#e8d9b5",
            stroke_width=4, stroke_fill="#120a05")
    return img.crop(img.getbbox())


def scene(seed=7):
    """Low-res 480x270 dusk scene, upscaled 4x with nearest-neighbour for a pixel-art look."""
    random.seed(seed)
    W, H, HOR = 480, 270, 196
    img = vgrad((W, H), [(0, "#07081a"), (0.38, "#1d1233"), (0.62, "#4a1d2e"), (0.73, "#a8461f"), (0.76, "#d8742c"), (1, "#2a0f0c")])
    d = ImageDraw.Draw(img)
    for _ in range(90):  # stars in the upper sky
        x, y = random.randrange(W), random.randrange(int(H * 0.45))
        v = random.randint(90, 200)
        d.point((x, y), fill=(v, v, min(255, v + 30), 255))
    # the rift: a lens-shaped tear onto a dark void, glowing at the edges, with debris drawn toward it
    sx0, sy0, sx1, sy1, maxw = 300, 36, 430, 118, 22
    L = math.hypot(sx1 - sx0, sy1 - sy0)
    ux, uy = (sx1 - sx0) / L, (sy1 - sy0) / L
    nx_, ny_ = -uy, ux
    upper, lower = [], []
    for i in range(41):
        t = i / 40
        jit = random.uniform(-2.5, 2.5) if 0 < i < 40 else 0
        bx, by = sx0 + ux * L * t + nx_ * jit, sy0 + uy * L * t + ny_ * jit
        wv = maxw * math.sin(math.pi * t) ** 0.85 * random.uniform(0.75, 1.0)
        upper.append((bx + nx_ * wv / 2, by + ny_ * wv / 2))
        lower.append((bx - nx_ * wv / 2, by - ny_ * wv / 2))
    tear = upper + lower[::-1]
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.polygon(tear, fill=(130, 80, 255, 230))
    hd.line(tear + [tear[0]], fill=(180, 140, 255, 230), width=12)
    img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(12)))
    rift = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rift)
    rd.polygon(tear, fill="#07020f")
    for _ in range(18):  # glimpses of another sky inside the tear
        t = random.uniform(0.15, 0.85)
        ox = sx0 + ux * L * t + nx_ * random.uniform(-maxw / 4, maxw / 4)
        oy = sy0 + uy * L * t + ny_ * random.uniform(-maxw / 4, maxw / 4)
        rd.point((ox, oy), fill=random.choice(["#5ef0ff", "#b9a2ff", "#ffffff"]))
    rd.line(upper, fill="#e6dcff", width=1)
    rd.line(lower, fill="#b49cff", width=1)
    img = Image.alpha_composite(img, rift)
    d = ImageDraw.Draw(img)
    for _ in range(9):  # rubble pulled up toward the rift
        t = random.uniform(0.0, 1.0)
        cx_ = sx0 + ux * L * t + nx_ * random.choice([-1, 1]) * random.uniform(18, 46)
        cy_ = sy0 + uy * L * t + ny_ * random.uniform(14, 40)
        sz = random.randint(2, 5)
        rock = [(cx_ + random.uniform(-sz, sz), cy_ + random.uniform(-sz, sz)) for _ in range(5)]
        d.polygon(rock, fill="#120c1c")
        d.point((min(p[0] for p in rock), min(p[1] for p in rock)), fill="#8e74d8")
    # the broken Convergence ring on the far horizon
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rg = ImageDraw.Draw(ring)
    cx, cy, R = 150, HOR + 8, 74
    rg.arc([cx - R, cy - R, cx + R, cy + R], start=190, end=300, fill="#1c1430", width=8)
    rg.arc([cx - R, cy - R, cx + R, cy + R], start=318, end=350, fill="#1c1430", width=8)
    rg.arc([cx - R + 2, cy - R + 2, cx + R - 2, cy + R - 2], start=225, end=290, fill="#5a3a8a", width=1)
    img = Image.alpha_composite(img, ring)
    d = ImageDraw.Draw(img)

    def skyline(base_y, hmin, hmax, wmin, wmax, col, rim=None):
        x = -5
        while x < W:
            bw = random.randint(wmin, wmax)
            bh = random.randint(hmin, hmax)
            top = base_y - bh
            d.rectangle([x, top, x + bw, base_y + 40], fill=col)
            for _ in range(random.randint(1, 3)):  # broken, jagged tops
                nx = x + random.randint(0, max(1, bw - 2))
                d.polygon([(nx, top), (nx + random.randint(2, 6), top), (nx + random.randint(0, 3), top + random.randint(3, 10))], fill=img.getpixel((min(W - 1, max(0, nx)), max(0, top - 2))))
            if random.random() < 0.25:  # a spire
                sx = x + bw // 2
                d.polygon([(sx - 2, top), (sx + 2, top), (sx, top - random.randint(8, 22))], fill=col)
            if rim:
                d.line([(x, top), (x + bw, top)], fill=rim)
            x += bw + random.randint(-3, 0)

    skyline(HOR, 14, 48, 6, 18, "#2a1d38", rim="#4b2f4f")
    fog = vgrad((W, 40), [(0, "#00000000"), (1, "#5a2a3acc")])
    img.alpha_composite(fog, (0, HOR - 30))
    d = ImageDraw.Draw(img)
    skyline(HOR + 18, 20, 70, 10, 26, "#140d1c")
    # foreground hill
    hill = [(0, H)]
    for x in range(0, W + 10, 10):
        hill.append((x, 238 + 10 * math.sin(x / 70) + random.randint(-2, 2)))
    hill.append((W, H))
    d.polygon(hill, fill="#09070d")
    # campfire with its glow, two figures, rising embers
    fx, fy = 120, 240
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([fx - 60, fy - 40, fx + 60, fy + 30], fill=(255, 120, 40, 90))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    for dx, dy, col in [(0, 0, "#ffd36b"), (-1, 1, "#ff9a3c"), (1, 1, "#ff9a3c"), (0, -1, "#ffb347"), (0, -2, "#ff7a2f"),
                        (-2, 2, "#e2461b"), (2, 2, "#e2461b"), (-1, -1, "#ff7a2f"), (1, -3, "#e2461b")]:
        d.point((fx + dx, fy + dy), fill=col)
    d.line([(fx - 3, fy + 3), (fx + 3, fy + 3)], fill="#3a2414")
    for px_, sit in ((fx - 12, True), (fx + 10, False)):  # two survivors by the fire
        if sit:
            d.rectangle([px_, fy - 3, px_ + 2, fy + 2], fill="#050307")
            d.rectangle([px_ + 1, fy - 6, px_ + 2, fy - 4], fill="#050307")
        else:
            d.rectangle([px_, fy - 7, px_ + 1, fy + 2], fill="#050307")
            d.rectangle([px_, fy - 9, px_ + 1, fy - 8], fill="#050307")
    for _ in range(40):
        ex = fx + random.randint(-10, 10) + random.randint(0, 40)
        ey = fy - random.randint(4, 110)
        d.point((ex, ey), fill=random.choice(["#ffb347", "#ff7a2f", "#ffd36b"]))
    return img.resize((W * 4, H * 4), Image.NEAREST)


def main():
    os.makedirs("out", exist_ok=True)
    os.makedirs("drafts", exist_ok=True)
    em = emblem()
    em.resize((512, 512), Image.LANCZOS).save("out/emblem_512.png")
    for s in (256, 128, 64, 32, 16):
        em.resize((s, s), Image.LANCZOS).save(f"out/icon_{s}.png")
    lg = logo(em)
    lg.save("out/logo.png")
    bg = scene()
    bg.save("out/background.png")

    # title-screen composite
    title = bg.copy()
    L = lg.resize((int(lg.width * 0.42), int(lg.height * 0.42)), Image.LANCZOS)
    title.alpha_composite(L, ((title.width - L.width) // 2, 70))
    d = ImageDraw.Draw(title)
    bf = ImageFont.truetype(PIXEL_FONT, 30)
    for i, label in enumerate(["Singleplayer", "Multiplayer", "Options", "Quit"]):
        y = 640 + i * 78
        d.rectangle([760, y, 1160, y + 58], fill="#1a1310cc", outline="#c99a3e", width=3)
        tb = d.textbbox((0, 0), label, font=bf)
        d.text((960 - (tb[2] - tb[0]) // 2, y + 13), label, font=bf, fill="#e8d9b5")
    title.convert("RGB").save("drafts/title_screen_mockup.png")

    # loading-screen composite
    load = Image.alpha_composite(bg, Image.new("RGBA", bg.size, (0, 0, 0, 110)))
    L2 = lg.resize((int(lg.width * 0.32), int(lg.height * 0.32)), Image.LANCZOS)
    load.alpha_composite(L2, ((load.width - L2.width) // 2, 230))
    d = ImageDraw.Draw(load)
    d.rectangle([460, 880, 1460, 904], outline="#c99a3e", width=3)
    d.rectangle([466, 886, 466 + int(988 * 0.62), 898], fill="#ff9a3c")
    tip = "Salted meat keeps far longer on the road. Pack accordingly."
    tf = ImageFont.truetype(PIXEL_FONT, 28)
    tb = d.textbbox((0, 0), tip, font=tf)
    d.text((960 - (tb[2] - tb[0]) // 2, 940), tip, font=tf, fill="#e8d9b5")
    d.text((470, 840), "Rekindling the Hearth...", font=tf, fill="#9c8f78")
    load.convert("RGB").save("drafts/loading_screen_mockup.png")

    # emblem and icon sheet
    sheet = Image.new("RGBA", (1400, 620), "#14121a")
    sheet.alpha_composite(em.resize((512, 512), Image.LANCZOS), (40, 54))
    x = 600
    for s in (256, 128, 64, 32, 16):
        ic = Image.open(f"out/icon_{s}.png")
        sheet.alpha_composite(ic, (x, 310 - s // 2))
        x += s + 40
    d = ImageDraw.Draw(sheet)
    d.text((40, 14), "REMNANT EMBLEM + WINDOW ICONS (256/128/64/32/16)", font=ImageFont.truetype(PIXEL_FONT, 26), fill="#e8d9b5")
    sheet.convert("RGB").save("drafts/emblem_and_icons.png")
    print("done")


if __name__ == "__main__":
    main()
