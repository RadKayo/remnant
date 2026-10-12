"""Generate Remnant's ruined city core: the Ascendancy city the group restores at spawn.

python citygen.py --seed 7 --out out/ --jar <client-extra.jar> --jar <create.jar>

Writes core.schem (WorldEdit: //schem load core, then //paste -m !minecraft:structure_void),
structure tiles for /place template (datapack/), plan.png and iso.png previews.
Everything is our own work, so the output can ship with the pack.
"""
import argparse
import json
import math
import os
import types

import numpy as np

from voxel import AIR, VOID, Byte, Grid, List

R = 96  # half width: the grid is 193 x 193 columns, centred on the Hearth
Y = 100
G = 12  # first air layer above the ground; the ground surface is G - 1
WALL_R = 84
FOOT_R = 92

DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
HOUSE_NAMES = ["LAMPWRIGHT", "COPPERSMITH", "SCRIBE", "CHANDLER", "WEAVER", "GLASSWORKS", "BATHS", "AETHER|WORKS",
               "HOUSE|VELL", "HOUSE|ORREN", "HOUSE|MAREK", "COUNTING|HOUSE", "APOTHECARY", "BAKER", "SCHOOL",
               "LODGINGS", "CLOCKMAKER", "CARTOGRAPHER", "TEA HOUSE", "LENSGRINDER"]
# Remnant repairs show the Age they were made in: masonry by Age, metal salvaged and put back
REPAIR = {1: "mud_brick", 2: "cobblestone", 3: "stone_brick", 4: "brick"}
SALVAGED = ("copper", "amethyst", "grate", "bulb", "chain", "lantern", "bars", "door", "campfire", "candle", "skull",
            "bed", "barrel", "pot", "lectern", "composter", "hay", "log", "planks", "wool", "fence", "glass", "sign",
            "banner", "torch", "spruce", "oak", "birch", "crafting", "cauldron")
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def toward(dx, dz):
    """Compass direction of the larger component of (dx, dz)."""
    if abs(dx) >= abs(dz):
        return "east" if dx > 0 else "west"
    return "south" if dz > 0 else "north"


def noise2(shape, cell, rng):
    gx, gz = shape[0] // cell + 2, shape[1] // cell + 2
    g = rng.random((gx, gz))
    fx = np.arange(shape[0]) / cell
    fz = np.arange(shape[1]) / cell
    ix, iz = fx.astype(int), fz.astype(int)
    tx, tz = fx - ix, fz - iz
    tx, tz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    a = g[ix][:, iz] * (1 - tz) + g[ix][:, iz + 1] * tz
    b = g[ix + 1][:, iz] * (1 - tz) + g[ix + 1][:, iz + 1] * tz
    return a * (1 - tx)[:, None] + b * tx[:, None]


def noise3(shape, cell, rng):
    gs = [s // cell + 2 for s in shape]
    g = rng.random(gs).astype(np.float32)
    f = [np.arange(s) / cell for s in shape]
    i = [v.astype(int) for v in f]
    t = [(v - iv) for v, iv in zip(f, i)]
    t = [v * v * (3 - 2 * v) for v in t]
    x, y, z = np.ix_(i[0], i[1], i[2])
    tx, ty, tz = np.ix_(t[0], t[1], t[2])
    out = np.zeros(shape, np.float32)
    for ox in (0, 1):
        wx = tx if ox else 1 - tx
        for oy in (0, 1):
            wy = ty if oy else 1 - ty
            for oz in (0, 1):
                wz = tz if oz else 1 - tz
                out += g[x + ox, y + oy, z + oz] * wx * wy * wz
    return out


def dilate(m, k):
    out = m.copy()
    for _ in range(k):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def box_blur(a, k):
    p = np.pad(a, k).astype(np.float32)
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    n = 2 * k + 1
    s = c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]
    return s / (n * n)


class City:
    def __init__(self, seed):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.g = Grid(2 * R + 1, Y, 2 * R + 1)
        d = np.arange(2 * R + 1) - R
        self.dx, self.dz = np.meshgrid(d, d, indexing="ij")
        self.r = np.hypot(self.dx, self.dz)
        self.th = np.degrees(np.arctan2(self.dz, self.dx))  # 0 east, 90 south, 180 west, -90 north
        self.integrity = np.full(self.dx.shape, 0.6, np.float32)
        self.htop = np.full(self.dx.shape, G + 12, np.int32)  # roof line of whatever stands on a column
        self.fine = np.full(self.dx.shape, 0.55, np.float32)  # small holes (houses) vs big collapses (landmarks)
        self.occupied = np.zeros(self.dx.shape, bool)
        self.roads = np.zeros(self.dx.shape, bool)
        self.lots = []
        self.notes = []
        self.signs = []
        self.sites = {}  # landmarks the group restores, each with a footprint and the Age of its repairs
        s = self.g.s
        self.m = {
            # the Ascendancy's city: cream limestone, grey tuff, verdigris copper, aether crystal
            "lime": s("create:cut_limestone_bricks"), "lime_small": s("create:small_limestone_bricks"),
            "lime_cut": s("create:cut_limestone"), "lime_pol": s("create:polished_cut_limestone"),
            "lime_raw": s("create:limestone"), "lime_layer": s("create:layered_limestone"),
            "lime_pillar": s("create:limestone_pillar", axis="y"),
            "tuff_b": s("tuff_bricks"), "tuff_pol": s("polished_tuff"), "tuff_ch": s("chiseled_tuff_bricks"),
            "tuff_chis": s("chiseled_tuff"), "tuff": s("tuff"),
            "cu": s("oxidized_cut_copper"), "cu_block": s("oxidized_copper"), "cu_ch": s("oxidized_chiseled_copper"),
            "grate": s("oxidized_copper_grate", waterlogged=False),
            "bulb": s("oxidized_copper_bulb", lit=False, powered=False),
            "amethyst": s("amethyst_block"),
            "ds_b": s("deepslate_bricks"), "ds_t": s("deepslate_tiles"), "ds_pol": s("polished_deepslate"),
            "ds_ch": s("chiseled_deepslate"), "ds_cob": s("cobbled_deepslate"),
            "stone": s("stone"), "dirt": s("dirt"), "grass": s("grass_block", snowy=False),
            "coarse": s("coarse_dirt"), "gravel": s("gravel"), "cobble": s("cobblestone"),
            "moss": s("moss_block"), "podzol": s("podzol", snowy=False), "andesite": s("andesite"),
            "mossy_cobble": s("mossy_cobblestone"),
            "spruce": s("spruce_planks"), "spruce_log": s("spruce_log", axis="y"),
            "water": s("water", level=0),
        }

    # ---------- small helpers ----------
    def X(self, dx):
        return R + dx

    def put(self, dx, y, dz, st, built=True, keep=False):
        self.g.put(R + dx, y, R + dz, st, built, keep)

    def box(self, x0, y0, z0, x1, y1, z1, st, built=True, keep=False):
        self.g.box(R + x0, y0, R + z0, R + x1, y1, R + z1, st, built, keep)

    def get(self, dx, y, dz):
        return self.g.get(R + dx, y, R + dz)

    def stairs(self, base, facing, half="bottom"):
        return self.g.s(f"{base}_stairs", facing=facing, half=half, shape="straight", waterlogged=False)

    def slab(self, base, kind="bottom"):
        return self.g.s(f"{base}_slab", type=kind, waterlogged=False)

    def wall(self, base):
        return self.g.s(f"{base}_wall", up=True, north="none", east="none", south="none", west="none",
                        waterlogged=False)

    def ground(self, mask, st):
        self.g.column_mask(mask, G - 1, G - 1, st, built=False)

    def claim(self, x0, z0, x1, z1, integrity=None, top=None):
        sl = (slice(R + x0, R + x1 + 1), slice(R + z0, R + z1 + 1))
        self.occupied[sl] = True
        if integrity is not None:
            self.integrity[sl] = integrity
        if top is not None:
            self.htop[sl] = top

    # ---------- restoration sites ----------
    def rect(self, x0, z0, x1, z1):
        return (self.dx >= x0) & (self.dx <= x1) & (self.dz >= z0) & (self.dz <= z1)

    def site(self, name, label, age, mask, props=None):
        self.sites[name] = {"label": label, "age": age, "mask": mask, "props": props}

    def wput(self, arr, dx, y, dz, st):
        if self.g.inside(R + dx, y, R + dz):
            arr[R + dx, y, R + dz] = st

    def wget(self, arr, dx, y, dz):
        return int(arr[R + dx, y, R + dz]) if self.g.inside(R + dx, y, R + dz) else VOID

    def repair(self, i, age):
        """The block the Remnant put back where an Ascendancy block fell, in the Age they did it."""
        key = self.g.pal[i]
        name, _, rest = key.partition("[")
        bare = name.split(":")[1]
        if age >= 5 or any(w in bare for w in SALVAGED):
            return i
        base = REPAIR[age]
        props = dict(p.split("=", 1) for p in rest.rstrip("]").split(",")) if rest else {}
        for kind in ("_stairs", "_slab", "_wall"):
            if bare.endswith(kind):
                return self.g.s(base + kind, **props)
        return self.g.s({"mud_brick": "mud_bricks", "stone_brick": "stone_bricks", "brick": "bricks"}.get(base, base))

    def restore(self, name):
        """The site as the group rebuilds it: fallen blocks put back in the Age's own materials,
        rubble and weeds cleared, and whatever the Age adds."""
        g, site = self.g, self.sites[name]
        mask = np.repeat(site["mask"][:, None, :], g.shape[1], axis=1)
        new = g.a.copy()
        fill = mask & self.removed
        for i in np.unique(self.pre_a[fill]):
            new[fill & (self.pre_a == i)] = self.repair(int(i), site["age"])
        plants = self.g.ids_where(lambda k: any(p in k for p in ("grass[", "short_grass", "tall_grass", "fern",
                                                                    "poppy", "dandelion", "daisy", "cornflower",
                                                                    "bluet")))
        junk = mask & (self.pre_a == AIR) & (g.a > AIR) & ~g.keep & ~np.isin(g.a, plants)
        junk[:, :G, :] = False
        new[junk] = AIR
        if site["props"]:
            site["props"](new)
        return new

    def props_hearth(self, new):
        """Age I, Rekindle the Hearth: the brazier burns, and torches sit where the lamps no longer work."""
        s = self.g.s
        self.wput(new, 0, G, 0, s("campfire", lit=True, facing="north", signal_fire=False, waterlogged=False))
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.wput(new, 8 * sx, G + 3, 8 * sz, s("torch"))

    def props_gate(self, ang):
        def props(new):
            """Age II, Mend the Gate: torches either side of the arch, the Remnant's banners above it."""
            s = self.g.s
            a = math.radians(ang)
            ux, uz = int(round(math.cos(a))), int(round(math.sin(a)))
            tx, tz = -uz, ux
            facing = toward(ux, uz)
            torch, banner = s("wall_torch", facing=facing), s("red_wall_banner", facing=facing)
            for off, y, st in ((-4, G + 3, torch), (4, G + 3, torch), (-2, G + 7, banner), (2, G + 7, banner)):
                seen = False
                for k in range(78, 93):
                    x, z = tx * off + ux * k, tz * off + uz * k
                    if self.wget(new, x, y, z) > AIR:
                        seen = True
                    elif seen:
                        self.wput(new, x, y, z, st)
                        break
        return props

    # ---------- terrain and streets ----------
    def terrain(self):
        m = self.m
        foot = self.r <= FOOT_R
        self.g.column_mask(foot, 0, G - 6, m["stone"], built=False)
        self.g.column_mask(foot, G - 5, G - 2, m["dirt"], built=False)
        self.ground(foot, m["grass"])
        self.g.column_mask(foot, G, G + 30, AIR, built=False)

    def streets(self):
        m, dx, dz, r, rng = self.m, self.dx, self.dz, self.r, self.rng
        ns = (np.abs(dx) <= 3) & (r >= 16) & (r <= FOOT_R)
        ew = (np.abs(dz) <= 3) & (r >= 16) & (r <= FOOT_R)
        ring = (r >= 38) & (r <= 42.5)
        lanes = (np.abs(np.abs(dx) - np.abs(dz)) <= 1) & (r >= 18) & (r <= 76)
        self.roads = ns | ew | ring | lanes
        n = noise2(dx.shape, 9, rng)
        speck = rng.random(dx.shape)
        lane_mix = np.choose(rng.integers(0, 3, dx.shape), [m["cobble"], m["tuff"], m["gravel"]])
        g = self.g.a[:, G - 1, :]
        g[lanes] = lane_mix[lanes]
        self.ground(ring, m["tuff_b"])
        self.ground(ns | ew, m["tuff_pol"])
        curb = (ns & (np.abs(dx) == 3)) | (ew & (np.abs(dz) == 3))
        self.ground(curb & ~(ns & ew), m["tuff_b"])
        # four centuries of weeds
        worn = self.roads & (n > 0.62)
        self.ground(worn & (speck < 0.7), m["grass"])
        self.ground(worn & (speck >= 0.7), m["coarse"])
        self.ground(self.roads & (n > 0.55) & (n <= 0.62) & (speck < 0.5), m["gravel"])
        self.ground(self.roads & (speck > 0.985), m["moss"])

    # ---------- the plaza and the Hearth ----------
    def plaza(self):
        m, dx, dz, r, th = self.m, self.dx, self.dz, self.r, self.th
        pz = r <= 18.5
        rings = (r.astype(int) // 3) % 2 == 0
        spokes = (((th + 180) / 22.5).astype(int) % 2) == 0
        pave = np.where(rings, m["lime_pol"], np.where(spokes, m["lime_cut"], m["lime_small"]))
        lines = (np.abs(r - 12.5) < 0.5) | (np.abs(r - 18) < 0.5)
        spoke = (r > 7) & ((np.abs(dx) <= 0.5) | (np.abs(dz) <= 0.5) | (np.abs(np.abs(dx) - np.abs(dz)) <= 0.5))
        pave = np.where(lines, m["tuff_b"], np.where(spoke, m["tuff_pol"], pave))
        g = self.g.a[:, G - 1, :]
        g[pz] = pave[pz]
        self.g.keep[:, G - 1, :] |= pz
        edge = (r > 18.5) & (r <= 19.5)
        gap = (np.abs(dx) <= 3) | (np.abs(dz) <= 3) | (np.abs(np.abs(dx) - np.abs(dz)) <= 2)
        self.g.a[:, G, :][edge & ~gap] = self.slab("create:cut_limestone")
        self.g.built[:, G, :][edge & ~gap] = True
        self.g.keep[:, G, :][edge & ~gap] = True
        self.ground(edge, m["lime_pol"])
        self.claim(-22, -22, 22, 22, 1.0)

        # the Hearth: a sunken fire ring with an unlit brazier the Remnant rekindle
        pit = r <= 5.5
        rim = (r > 5.5) & (r <= 7)
        self.g.column_mask(pit, G - 1, G - 1, AIR, built=False)
        self.g.column_mask(pit, G - 2, G - 2, m["tuff_pol"], built=False)
        self.ground(rim, m["tuff_ch"])
        self.g.keep[:, G - 2:G + 1, :] |= (r <= 7)[:, None, :]
        self.box(-1, G - 2, -1, 1, G - 1, 1, m["tuff_chis"], keep=True)
        for d, (ox, oz) in DIRS.items():
            self.put(ox, G, oz, self.stairs("oxidized_cut_copper", d), keep=True)
        for ox in (-1, 1):
            for oz in (-1, 1):
                self.put(ox, G, oz, self.slab("oxidized_cut_copper"), keep=True)
        self.put(0, G, 0, self.g.s("campfire", lit=False, facing="north", signal_fire=False, waterlogged=False),
                 keep=True)
        self.sign(0, G - 1, 2, "south", ["HERE BURNS", "THE FIRST", "FLAME"])
        self.site("hearth", "The Hearth", 1, r <= 20, self.props_hearth)
        self.sign(0, G - 1, -2, "north", ["OF THE", "CONVERGENCE"])
        # benches facing the fire, lamp posts on the diagonals
        for x in range(-10, 11):
            for z in range(-10, 11):
                rr = math.hypot(x, z)
                if 8.5 <= rr < 9.5 and abs(x) > 3 and abs(z) > 3:
                    self.put(x, G, z, self.stairs("create:cut_limestone", toward(x, z)), keep=True)
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.box(8 * sx, G, 8 * sz, 8 * sx, G + 2, 8 * sz, self.wall("polished_tuff"), keep=True)
                self.put(8 * sx, G + 3, 8 * sz, m["bulb"], keep=True)

    # ---------- buildings ----------
    def house(self, x0, z0, x1, z1, floors, door, integrity, roof="flat", wall=None, keep=False):
        m, s = self.m, self.g.s
        wall = wall or m["lime"]
        h = floors * 4
        self.box(x0, G, z0, x1, G + h, z1, wall, keep=keep)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G + h - 1, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G - 1, z0 + 1, x1 - 1, G - 1, z1 - 1, m["lime_pol"], built=False)
        # base course, floor bands, corners
        for y, st in ((G, m["tuff_pol"]),) + tuple((G + 4 * k, m["cu"]) for k in range(1, floors + 1)):
            self.box(x0, y, z0, x1, y, z0, st, keep=keep)
            self.box(x0, y, z1, x1, y, z1, st, keep=keep)
            self.box(x0, y, z0, x0, y, z1, st, keep=keep)
            self.box(x1, y, z0, x1, y, z1, st, keep=keep)
        for cx, cz in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
            self.box(cx, G + 1, cz, cx, G + h - 1, cz, m["lime_pol"], keep=keep)
        for k in range(1, floors):
            self.box(x0 + 1, G + 4 * k, z0 + 1, x1 - 1, G + 4 * k, z1 - 1, m["lime_pol"], keep=keep)
        # windows on every floor, a door facing the street
        win = m["grate"] if self.rng.random() < 0.4 else AIR
        for k in range(floors):
            yb = G + 4 * k + 1
            for x in range(x0 + 2, x1 - 1, 3):
                for z in (z0, z1):
                    self.box(x, yb, z, x, yb + 1, z, win, built=win != AIR)
            for z in range(z0 + 2, z1 - 1, 3):
                for x in (x0, x1):
                    self.box(x, yb, z, x, yb + 1, z, win, built=win != AIR)
        mx, mz = (x0 + x1) // 2, (z0 + z1) // 2
        ddx, ddz = DIRS[door]
        px = x1 if ddx > 0 else x0 if ddx < 0 else mx
        pz = z1 if ddz > 0 else z0 if ddz < 0 else mz
        self.box(px, G, pz, px, G + 2, pz, AIR, built=False)
        self.put(px + ddx, G - 1, pz + ddz, m["lime_pol"], built=False)
        if not keep:
            self.furnish(x0, z0, x1, z1, px, pz)
            if self.rng.random() < 0.45:
                name = HOUSE_NAMES[int(self.rng.integers(0, len(HOUSE_NAMES)))]
                self.put(px, G + 3, pz, wall, keep=True)  # the lintel holding the name survives
                self.sign(px + ddx, G + 3, pz + ddz, door, name.split("|"))
        # roof
        top = G + h
        if roof == "flat":
            self.box(x0 + 1, top, z0 + 1, x1 - 1, top, z1 - 1, m["lime_pol"], keep=keep)
            for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
                self.box(ax, top + 1, az, bx, top + 1, bz, self.wall("create:cut_limestone"), keep=keep)
        elif roof == "copper":
            self.hip_roof(x0 - 1, z0 - 1, x1 + 1, z1 + 1, top + 1, "oxidized_cut_copper", m["cu"], keep)
            top += min(x1 - x0, z1 - z0) // 2 + 1
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, integrity, top)
        return top

    def furnish(self, x0, z0, x1, z1, px, pz):
        """What the Ascendancy left behind: counters, cauldrons, and barrels and pots worth searching."""
        rng, s = self.rng, self.g.s
        spots = [(x, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)
                 if (x in (x0 + 1, x1 - 1) or z in (z0 + 1, z1 - 1)) and abs(x - px) + abs(z - pz) > 2]
        for k in rng.permutation(len(spots))[:int(rng.integers(1, 4))]:
            x, z = spots[int(k)]
            roll = rng.random()
            if roll < 0.35:
                self.loot(x, G, z, "barrel", s("barrel", facing="up", open=False))
            elif roll < 0.6:
                self.loot(x, G, z, "decorated_pot", s("decorated_pot", facing="north", cracked=bool(rng.random() < .5),
                                                     waterlogged=False))
            elif roll < 0.82:
                self.put(x, G, z, self.slab("create:polished_cut_limestone", "top"), built=False)
            else:
                self.put(x, G, z, s("cauldron"), built=False)

    def loot(self, x, y, z, kind, st, table="remnant:ruins/house"):
        self.put(x, y, z, st, built=False)
        self.g.block_nbt[(R + x, y, R + z)] = {"id": f"minecraft:{kind}", "LootTable": table}

    def sign(self, x, y, z, facing, lines, wood="birch"):
        """An inscription in the Ascendancy's runes (the Runelic font). Placed after decay, where its wall survived."""
        self.signs.append((x, y, z, facing, lines, wood))

    def place_signs(self):
        full = self.full_cubes()
        placed = 0
        for x, y, z, facing, lines, wood in self.signs:
            ox, oz = DIRS[facing]
            support = self.get(x - ox, y, z - oz)
            if self.get(x, y, z) != AIR or support >= len(full) or not full[support]:
                continue
            self.put(x, y, z, self.g.s(f"{wood}_wall_sign", facing=facing, waterlogged=False), built=False, keep=True)
            text = [json.dumps({"text": t, "font": "runelic:runelic"}) for t in (list(lines) + [""] * 4)[:4]]
            blank = [json.dumps({"text": ""})] * 4
            self.g.block_nbt[(R + x, y, R + z)] = {
                "id": "minecraft:sign", "is_waxed": Byte(1),
                "front_text": {"messages": List(8, text), "color": "black", "has_glowing_text": Byte(0)},
                "back_text": {"messages": List(8, blank), "color": "black", "has_glowing_text": Byte(0)}}
            placed += 1
        self.notes.append(f"{placed} of {len(self.signs)} inscriptions placed")

    def hip_roof(self, x0, z0, x1, z1, y, base, fill, keep=False):
        while x0 <= x1 and z0 <= z1:
            if x1 - x0 < 2 or z1 - z0 < 2:
                self.box(x0, y, z0, x1, y, z1, self.slab(base), keep=keep)
                return
            for x in range(x0, x1 + 1):
                self.put(x, y, z0, self.stairs(base, "south"), keep=keep)
                self.put(x, y, z1, self.stairs(base, "north"), keep=keep)
            for z in range(z0 + 1, z1):
                self.put(x0, y, z, self.stairs(base, "east"), keep=keep)
                self.put(x1, y, z, self.stairs(base, "west"), keep=keep)
            self.box(x0 + 1, y, z0 + 1, x1 - 1, y, z1 - 1, fill, keep=keep)
            x0, z0, x1, z1, y = x0 + 1, z0 + 1, x1 - 1, z1 - 1, y + 1

    def elder_house(self):
        """The one roofed building: the Elder's, patched with Remnant timber."""
        m, s = self.m, self.g.s
        x0, z0, x1, z1 = -16, 21, -6, 31
        self.house(x0, z0, x1, z1, 2, "north", 1.0, roof=None, keep=True)
        # the upper floor's east corner fell; the Remnant filled it with spruce
        self.box(x1, G + 5, z0 + 5, x1, G + 8, z1 - 1, m["spruce"], keep=True)
        self.box(x0 + 6, G + 7, z1, x1, G + 8, z1, m["spruce"], keep=True)
        # gabled spruce roof along x
        top = G + 9
        for i in range(0, 7):
            za, zb = z0 - 1 + i, z1 + 1 - i
            if za > zb:
                break
            for x in range(x0 - 1, x1 + 2):
                if za == zb:
                    self.put(x, top + i, za, self.slab("spruce"), keep=True)
                else:
                    self.put(x, top + i, za, self.stairs("spruce", "south"), keep=True)
                    self.put(x, top + i, zb, self.stairs("spruce", "north"), keep=True)
            for x in (x0, x1):
                if zb - za > 1:
                    self.box(x, top + i, za + 1, x, top + i, zb - 1, m["spruce"], keep=True)
        # shutters, a lit window, and the Elder's things
        for x in (x0 + 2, x1 - 3):
            self.put(x, G + 2, z0 - 1, s("spruce_trapdoor", facing="north", half="top", open=True,
                                         powered=False, waterlogged=False), keep=True)
        self.put(-9, G, 29, s("lectern", facing="north", has_book=False, powered=False), keep=True)
        self.put(-14, G, 29, s("barrel", facing="up", open=False), keep=True)
        self.put(-15, G, 29, s("crafting_table"), keep=True)
        self.put(-15, G, 23, s("red_bed", facing="south", part="head", occupied=False), keep=True)
        self.put(-15, G, 22, s("red_bed", facing="south", part="foot", occupied=False), keep=True)
        self.put(-7, G, 23, s("candle", candles=3, lit=False, waterlogged=False), keep=True)
        self.claim(x0 - 2, z0 - 2, x1 + 2, z1 + 2, 1.0)

    def camp(self):
        """Where the Remnant actually live, for now: tents, firewood, a fire and a garden by the plaza."""
        m, s, rng = self.m, self.g.s, self.rng
        x0, z0, x1, z1 = -33, -16, -20, -6
        self.box(x0, G - 1, z0, x1, G - 1, z1, m["coarse"], built=False)
        self.tent(x0, z0, "smooth_sandstone", "brown", 2)
        self.tent(x0 + 6, z0, "smooth_quartz", "green", 1)
        self.box(x1 - 1, G, z0, x1, G + 1, z0 + 3, s("oak_log", axis="z"), built=False, keep=True)
        self.put(-26, G, -10, s("campfire", lit=True, facing="north", signal_fire=False, waterlogged=False),
                 built=False, keep=True)
        for x in (-28, -24):
            self.put(x, G, -10, s("stripped_spruce_log", axis="z"), built=False, keep=True)
        self.put(-23, G, -7, s("crafting_table"), built=False, keep=True)
        self.put(-22, G, -7, s("barrel", facing="up", open=False), built=False, keep=True)
        self.box(-21, G, -7, -21, G + 1, -7, s("hay_block", axis="y"), built=False, keep=True)
        self.put(-20, G, -7, s("composter", level=3), built=False, keep=True)
        # a watered garden: wheat, carrots, potatoes
        for x in range(-33, -27):
            for z in (-8, -7):
                self.put(x, G - 1, z, s("farmland", moisture=7), built=False, keep=True)
                crop = ("wheat", "carrots", "potatoes")[(x + 33) // 2]
                self.put(x, G, z, s(crop, age=int(rng.integers(2, 8))), built=False, keep=True)
        self.put(-31, G - 1, -9, m["water"], built=False, keep=True)
        self.claim(x0 - 2, z0 - 2, x1 + 2, z1 + 2, 1.0)

    def tent(self, x0, z0, canvas, bed, beds):
        """A canvas A-frame, five wide and four deep, open to the south, with bedrolls inside.
        Stairs make the sloped canvas; a slab is the ridge."""
        s = self.g.s
        back = s({"smooth_sandstone": "white_wool", "smooth_quartz": "white_wool"}[canvas])
        for z in range(z0, z0 + 4):
            self.put(x0, G, z, self.stairs(canvas, "east"), built=False, keep=True)
            self.put(x0 + 4, G, z, self.stairs(canvas, "west"), built=False, keep=True)
            self.put(x0 + 1, G + 1, z, self.stairs(canvas, "east"), built=False, keep=True)
            self.put(x0 + 3, G + 1, z, self.stairs(canvas, "west"), built=False, keep=True)
            self.put(x0 + 2, G + 2, z, self.slab(canvas), built=False, keep=True)
        self.box(x0 + 1, G, z0, x0 + 3, G, z0, back, built=False, keep=True)
        self.put(x0 + 2, G + 1, z0, back, built=False, keep=True)
        pole = s("birch_fence", north=False, east=False, south=False, west=False, waterlogged=False)
        self.box(x0 + 2, G, z0 + 4, x0 + 2, G + 1, z0 + 4, pole, built=False, keep=True)
        self.put(x0 + 2, G + 2, z0 + 4, self.slab(canvas), built=False, keep=True)
        for bx in ((x0 + 1, x0 + 3) if beds == 2 else (x0 + 2,)):
            self.put(bx, G, z0 + 1, s(f"{bed}_bed", facing="north", part="head", occupied=False), built=False, keep=True)
            self.put(bx, G, z0 + 2, s(f"{bed}_bed", facing="north", part="foot", occupied=False), built=False, keep=True)

    # ---------- the Convergence Spire and its broken ring ----------
    def spire(self):
        m, s, rng = self.m, self.g.s, self.rng
        cx, cz = 0, -58
        lx, lz = self.dx - cx, self.dz - cz
        lr = np.maximum(np.maximum(np.abs(lx), np.abs(lz)), (np.abs(lx) + np.abs(lz)) / 1.4142)  # octagon
        precinct = (np.hypot(lx, lz) <= 24) & (self.r <= 80)
        n = noise2(lx.shape, 5, rng)
        g = self.g.a[:, G - 1, :]
        g[precinct] = np.where(n > 0.55, m["tuff_b"], np.where(n > 0.4, m["lime_pol"], m["lime_cut"]))[precinct]
        # stepped plinth, then the octagonal shaft
        for y, rad in ((G, 11), (G + 1, 10.4), (G + 2, 10)):
            ring = lr <= rad
            self.g.column_mask(ring, y, y, m["tuff_pol"] if y < G + 2 else m["tuff_b"])
        shaft = lr <= 8
        hollow = lr <= 5.6
        top = G + 54 + (noise2(lx.shape, 3, rng) * 22).astype(int)  # jagged broken crown
        for y in range(G + 3, G + 77):
            layer = shaft & ~hollow & (top >= y)
            if not layer.any():
                continue
            st = m["cu"] if (y - G) % 12 == 0 else m["lime"]
            self.g.a[:, y, :][layer] = st
            self.g.built[:, y, :][layer] = True
            corner = layer & (np.abs(np.abs(lx) - np.abs(lz)) <= 0.5) & (lr > 7)
            self.g.a[:, y, :][corner & ((y - G) % 12 != 0)] = m["lime_pol"]
            if (y - G) % 12 == 0:
                floor = hollow & (top >= y) & (lr > 2.5)
                self.g.a[:, y, :][floor] = m["lime_pol"]
                self.g.built[:, y, :][floor] = True
            if (y - G) % 12 in (5, 6, 7, 8):  # tall slits on the eight faces
                face = layer & ((np.abs(lx) == 0) | (np.abs(lz) == 0) | (np.abs(lx) == np.abs(lz)))
                self.g.a[:, y, :][face] = AIR
        # the aether core: an amethyst column caged in copper up the middle
        for y in range(G, G + 70):
            for x in (-1, 0, 1):
                for z in (-1, 0, 1):
                    st = m["amethyst"] if (x == 0 and z == 0) or (y % 6 in (0, 1)) else m["grate"]
                    if y < G + 3 or (x, z) == (0, 0) or y % 3 == 0:
                        self.put(cx + x, y, cz + z, st)
        # buttresses on the diagonals
        for sx in (-1, 1):
            for sz in (-1, 1):
                for k in range(0, 9):
                    hgt = G + 30 - k * 3
                    bx, bz = cx + sx * (6 + k), cz + sz * (6 + k)
                    self.box(bx, G, bz, bx, hgt, bz, m["lime"])
                    self.put(bx, hgt + 1, bz, self.slab("create:cut_limestone_brick"))
        door = (np.abs(lx) <= 1) & (lz >= 6) & (lz <= 11)
        self.g.column_mask(door, G, G + 4, AIR, built=False)
        self.sign(cx, G + 5, cz + 9, "south", ["CONVERGENCE", "SPIRE", "", "NO ENTRY"])
        self.ring_standing(cx, cz)
        self.ring_fallen(cx, cz)
        self.claim(-26, -84, 44, -32, 0.8, G + 76)
        self.fine[R - 26:R + 45, R - 84:R - 31] = 0.12

    def ring_points(self, theta0, theta1, radius, step=0.004):
        th = np.arange(math.radians(theta0), math.radians(theta1), step)
        return th, radius * np.cos(th), radius * np.sin(th)

    def ring_standing(self, cx, cz):
        """The Convergence ring, threaded through the spire, broken away at the upper right."""
        m = self.m
        cy, rad = G + 56, 21.0
        th, u, v = self.ring_points(100, 330, rad)
        for t, a, b in zip(th, u, v):
            for dr in (-1.0, 0.0, 1.0):
                x = cx + a * (rad + dr) / rad
                y = cy + b * (rad + dr) / rad
                for z in (cz - 1, cz, cz + 1):
                    st = m["amethyst"] if dr < 0 and z == cz else m["cu"]
                    if int(math.degrees(t)) % 15 == 0:
                        st = m["cu_ch"]
                    self.put(int(round(x)), int(round(y)), z, st, keep=True)
        # jagged ends
        for t in (100, 330):
            a, b = rad * math.cos(math.radians(t)), rad * math.sin(math.radians(t))
            for _ in range(6):
                self.put(int(round(cx + a + self.rng.integers(-2, 3))), int(round(cy + b + self.rng.integers(-2, 3))),
                         cz + int(self.rng.integers(-1, 2)), m["cu_block"], keep=True)

    def ring_fallen(self, cx, cz):
        """The missing arc, broken in two and lying east of the spire."""
        m, rng = self.m, self.rng
        rad = 21.0
        pieces = ((-30, 22, (14, -46), 25, 3), (24, 95, (30, -68), 115, 1))
        for t0, t1, (tx, tz), rot, lift in pieces:
            th, u, v = self.ring_points(t0, t1, rad)
            mid = math.radians((t0 + t1) / 2)
            u, v = u - rad * math.cos(mid), v - rad * math.sin(mid)
            c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            wx, wz = tx + u * c - v * s_, tz + u * s_ + v * c
            frac = np.linspace(-1, 1, len(th))
            wy = G - 1 + lift * np.clip(frac, 0, None) ** 2 * 1.5
            for x, y, z, t in zip(wx, wy, wz, th):
                deg = int(math.degrees(t))
                for ox in (-1, 0, 1):
                    for oz in (-1, 0, 1):
                        for oy in (0, 1, 2):
                            if abs(ox) + abs(oz) + (oy == 2) * 2 + (oy == 0) <= 2:
                                st = m["cu_ch"] if deg % 15 == 0 else m["cu"]
                                self.put(int(x) + ox, int(y) + oy, int(z) + oz, st, keep=True)
                if deg % 8 < 3:
                    self.put(int(x), int(y) + 2, int(z), m["amethyst"], keep=True)
            # aether crystals still growing out of the wreck
            for _ in range(40):
                k = rng.integers(0, len(th))
                x, z = int(wx[k]) + rng.integers(-3, 4), int(wz[k]) + rng.integers(-3, 4)
                y = G
                while self.get(x, y, z) not in (AIR, VOID) and y < G + 6:
                    y += 1
                if self.get(x, y, z) == AIR:
                    st = self.g.s("amethyst_cluster", facing="up", waterlogged=False) if rng.random() < 0.6 \
                        else m["amethyst"]
                    self.put(x, y, z, st)

    # ---------- the market ----------
    def market(self):
        m, s, rng = self.m, self.g.s, self.rng
        x0, z0, x1, z1 = 44, -14, 74, 14
        sq = (self.dx >= x0) & (self.dx <= x1) & (self.dz >= z0) & (self.dz <= z1)
        n = noise2(self.dx.shape, 4, rng)
        g = self.g.a[:, G - 1, :]
        g[sq] = np.where(n > 0.5, m["lime_cut"], m["lime_small"])[sq]
        g[sq & (n > 0.66)] = m["grass"]
        # double colonnade around the square, open where the avenue runs through
        col = self.g.s("create:limestone_pillar", axis="y")
        for inset in (0, 3):
            pts = []
            for x in range(x0 + inset, x1 - inset + 1, 3):
                pts += [(x, z0 + inset), (x, z1 - inset)]
            for z in range(z0 + inset, z1 - inset + 1, 3):
                pts += [(x0 + inset, z), (x1 - inset, z)]
            for x, z in pts:
                if abs(z) <= 3 and x in (x0 + inset, x1 - inset):
                    continue
                self.box(x, G, z, x, G + 5, z, col)
                self.put(x, G + 6, z, m["lime_pol"])
            for (ax, az, bx, bz) in ((x0 + inset, z0 + inset, x1 - inset, z0 + inset),
                                     (x0 + inset, z1 - inset, x1 - inset, z1 - inset),
                                     (x0 + inset, z0 + inset, x0 + inset, z1 - inset),
                                     (x1 - inset, z0 + inset, x1 - inset, z1 - inset)):
                self.box(ax, G + 7, az, bx, G + 7, bz, m["lime"])
        for (ax, az, bx, bz) in ((x0, z0, x1, z0 + 3), (x0, z1 - 3, x1, z1), (x0, z0, x0 + 3, z1), (x1 - 3, z0, x1, z1)):
            self.box(ax, G + 8, az, bx, G + 8, bz, self.slab("create:polished_cut_limestone"))
        # fountain on the crossing
        fx, fz = 59, 0
        for x in range(fx - 4, fx + 5):
            for z in range(fz - 4, fz + 5):
                d = math.hypot(x - fx, z - fz)
                if d <= 3.2:
                    self.put(x, G - 2, z, m["tuff_pol"], built=False)
                    self.put(x, G - 1, z, m["water"] if d > 1 else m["tuff_ch"], built=False)
                elif d <= 4.4:
                    self.put(x, G - 1, z, m["lime_pol"], built=False)
                    self.put(x, G, z, m["lime_pol"], keep=True)
        self.box(fx, G, fz, fx, G + 2, fz, m["cu_ch"], keep=True)
        self.sign(fx + 1, G + 1, fz, "east", ["MARKET OF", "SEVEN ROADS"])
        self.sign(fx - 1, G + 1, fz, "west", ["MARKET OF", "SEVEN ROADS"])
        self.put(fx, G + 3, fz, m["cu_block"], keep=True)
        # old stalls: tuff posts, a limestone counter and a stone awning
        for sx in (49, 55, 63, 69):
            for sz in (-9, 7):
                for px, pz in ((sx, sz), (sx + 2, sz), (sx, sz + 2), (sx + 2, sz + 2)):
                    self.box(px, G, pz, px, G + 1, pz, self.wall("polished_tuff"))
                self.box(sx, G + 2, sz, sx + 2, G + 2, sz + 2, self.slab("create:cut_limestone"))
                self.box(sx, G, sz + (2 if sz < 0 else 0), sx + 2, G, sz + (2 if sz < 0 else 0),
                         self.slab("create:polished_cut_limestone", "top"))
                for _ in range(2):
                    px, pz = sx + int(rng.integers(-1, 4)), sz + int(rng.integers(-1, 4))
                    if self.get(px, G, pz) == AIR:
                        self.put(px, G, pz, s("decorated_pot", facing="north", cracked=bool(rng.random() < .5),
                                              waterlogged=False) if rng.random() < .6 else
                                 s("barrel", facing="up", open=False))
        self.claim(x0 - 2, z0 - 2, x1 + 2, z1 + 2, 0.55, G + 8)
        self.site("market", "The Market", 2, self.rect(x0 - 2, z0 - 2, x1 + 2, z1 + 2))

    # ---------- the Grave Warden's mausoleum, crypt and graveyard ----------
    def crypt(self):
        m, s, rng = self.m, self.g.s, self.rng
        x0, z0, x1, z1 = -66, -24, -52, -12
        self.box(x0, G, z0, x1, G + 7, z1, m["ds_b"], keep=True)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G + 6, z1 - 1, AIR, built=False)
        self.box(x0, G, z0, x1, G, z1, m["ds_pol"], keep=True)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G - 1, z0 + 1, x1 - 1, G - 1, z1 - 1, m["ds_t"], built=False)
        self.box(x0, G + 4, z0, x1, G + 4, z1, m["ds_ch"], keep=True)
        self.box(x0 + 1, G + 4, z0 + 1, x1 - 1, G + 4, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G + 7, z0 + 1, x1 - 1, G + 7, z1 - 1, m["ds_t"], keep=True)
        self.hip_roof(x0 - 1, z0 - 1, x1 + 1, z1 + 1, G + 8, "deepslate_tile", m["ds_t"], keep=True)
        # portico and steps on the south side, facing the avenue
        for x in (-64, -61, -57, -54):
            self.box(x, G, -10, x, G + 5, -10, m["ds_pol"], keep=True)
        self.box(x0, G + 6, -11, x1, G + 6, -9, self.slab("deepslate_tile"), keep=True)
        self.box(-61, G - 1, -9, -57, G - 1, -8, m["ds_pol"], built=False)
        self.box(-60, G, z1, -58, G + 3, z1, AIR, built=False)
        self.sign(-59, G + 4, z1 + 1, "south", ["HERE THEY", "WAIT"], "dark_oak")
        # stair down to the crypt, running north
        for k in range(7):
            z = -14 - k
            self.box(-60, G - 2 - k, z, -58, G - 2 - k, z, self.stairs("deepslate_brick", "south"), keep=True)
            self.box(-60, G - 1 - k, z, -58, G + 2, z, AIR, built=False)
            self.box(-61, G - 3 - k, z, -61, G - 1, z, m["ds_b"], keep=True)
            self.box(-57, G - 3 - k, z, -57, G - 1, z, m["ds_b"], keep=True)
        cx0, cz0, cx1, cz1, fy = -65, -35, -53, -21, G - 9
        self.box(cx0 - 1, fy, cz0 - 1, cx1 + 1, G - 3, cz1, m["ds_b"], keep=True)
        self.box(cx0, fy + 1, cz0, cx1, G - 4, cz1 - 1, AIR, built=False)
        self.box(cx0, fy, cz0, cx1, fy, cz1 - 1, m["ds_t"], keep=True)
        self.box(-60, fy + 1, cz1 - 1, -58, G - 4, cz1, AIR, built=False)
        for z in range(cz0 + 1, cz1 - 1, 3):  # burial niches with the old dead
            for x, face in ((cx0 - 1, "east"), (cx1 + 1, "west")):
                self.box(x, fy + 2, z, x, fy + 3, z, AIR, built=False)
                if rng.random() < 0.7:
                    rot = 12 if face == "east" else 4
                    self.put(x, fy + 2, z, s("skeleton_skull", rotation=rot, powered=False), keep=True)
                else:
                    self.put(x, fy + 2, z, s("candle", candles=int(rng.integers(2, 5)), lit=True,
                                             waterlogged=False), keep=True)
        for x in (cx0 + 3, cx1 - 3):
            for z in (cz0 + 3, cz1 - 4):
                self.box(x, fy + 1, z, x, G - 4, z, m["ds_pol"], keep=True)
        self.box(-60, fy + 1, -30, -58, fy + 1, -27, m["ds_pol"], keep=True)  # the sarcophagus
        self.box(-60, fy + 2, -30, -58, fy + 2, -27, self.slab("polished_deepslate"), keep=True)
        for x, z in ((-63, -23), (-55, -23), (-63, -27), (-55, -27), (-63, -31), (-55, -31), (-59, -34)):
            self.put(x, G - 4, z, s("chain", axis="y", waterlogged=False), keep=True)
            self.put(x, G - 5, z, s("soul_lantern", hanging=True, waterlogged=False), keep=True)
        # graveyard on the ground above the crypt
        yard = (self.dx >= -80) & (self.dx <= -46) & (self.dz >= -40) & (self.dz <= -27)
        self.ground(yard, m["grass"])
        for x in range(-78, -47, 3):
            for z in range(-38, -28, 3):
                if rng.random() < 0.75:
                    self.put(x, G - 1, z, m["podzol"] if rng.random() < .5 else m["coarse"], built=False)
                    self.put(x, G - 1, z + 1, m["podzol"] if rng.random() < .5 else m["coarse"], built=False)
                    self.put(x, G, z - 1, self.wall("cobbled_deepslate") if rng.random() < .6 else m["ds_ch"])
        edge = yard & dilate(~yard, 1)
        gate = edge & (self.dz >= -28) & (self.dx >= -63) & (self.dx <= -61)
        self.g.a[:, G, :][edge & ~gate] = s("iron_bars", north=False, east=False, south=False, west=False,
                                            waterlogged=False)
        self.g.built[:, G, :][edge & ~gate] = True
        self.claim(-82, -42, -44, -6, 0.75)
        self.site("crypt", "The Grave Warden's Crypt", 3, self.rect(-82, -42, -44, -6))

    # ---------- the airship mooring mast ----------
    def mast(self):
        m, s = self.m, self.g.s
        cx, cz = 60, 40
        self.box(cx - 3, G, cz - 3, cx + 3, G + 1, cz + 3, m["tuff_pol"])
        self.box(cx - 2, G + 2, cz - 2, cx + 2, G + 2, cz + 2, m["tuff_ch"])
        top = G + 40
        for x, z in ((cx - 2, cz - 2), (cx + 2, cz - 2), (cx - 2, cz + 2), (cx + 2, cz + 2)):
            self.box(x, G + 3, z, x, top, z, m["cu"], keep=True)
        for y in range(G + 6, top, 5):
            for (ax, az, bx, bz) in ((cx - 2, cz - 2, cx + 2, cz - 2), (cx - 2, cz + 2, cx + 2, cz + 2),
                                     (cx - 2, cz - 2, cx - 2, cz + 2), (cx + 2, cz - 2, cx + 2, cz + 2)):
                self.box(ax, y, az, bx, y, bz, m["grate"])
        self.box(cx - 4, top + 1, cz - 4, cx + 4, top + 1, cz + 4, self.slab("oxidized_cut_copper"), keep=True)
        self.box(cx - 1, top + 2, cz - 1, cx + 1, top + 4, cz + 1, m["cu"], keep=True)
        self.put(cx, top + 5, cz, m["bulb"], keep=True)
        for x in range(cx + 3, cx + 12):  # the docking arm
            self.put(x, top - 2, cz, m["cu"], keep=True)
        for y in range(top - 12, top - 2):
            self.put(cx + 11, y, cz, s("chain", axis="y", waterlogged=False), keep=True)
        self.claim(cx - 6, cz - 6, cx + 13, cz + 6, 0.85, G + 45)
        self.site("mast", "The Mooring Mast", 3, self.rect(cx - 6, cz - 6, cx + 13, cz + 6))

    # ---------- the outer wall ----------
    def walls(self):
        m, dx, dz, r, th, rng = self.m, self.dx, self.dz, self.r, self.th, self.rng
        band = (r >= 82.5) & (r < 85.5)
        outer = band & (r >= 84.5)
        inner = band & (r < 83.5)
        top = G + 9
        self.g.column_mask(band, G, top - 1, m["tuff_b"])
        self.g.column_mask(outer, G, G + 1, m["tuff_pol"])
        self.g.column_mask(outer, G + 5, G + 5, m["tuff_ch"])
        self.g.column_mask(band, top, top, m["tuff_pol"])
        merlon = outer & ((((th + 180) * 84 * math.pi / 180) // 2).astype(int) % 2 == 0)
        self.g.column_mask(merlon, top + 1, top + 1, self.wall("tuff_brick"))
        self.g.column_mask(inner, top + 1, top + 1, self.slab("tuff_brick"))
        self.integrity[band] = (0.68 + 0.3 * noise2(dx.shape, 18, rng))[band]
        self.htop[band] = top + 1
        self.fine[band] = 0.25
        # gates where the avenues leave, with a half-raised portcullis
        for ang, axis in ((0, "x"), (90, "z"), (180, "x"), (-90, "z")):
            side = np.abs(dz) if axis == "x" else np.abs(dx)
            along = dx if axis == "x" else dz
            sign = 1 if ang in (0, 90) else -1
            gate = band & (side <= 3) & (along * sign > 0)
            for y in range(G, top + 2):
                arch = (y <= G + 4) | (((y - (G + 4)) / 3.2) ** 2 + (side / 3.6) ** 2 <= 1)
                cut = gate & arch
                self.g.a[:, y, :][cut] = AIR
                self.g.built[:, y, :][cut] = False
            port = gate & (np.abs(r - 84) < 0.5)
            self.g.column_mask(port & (side <= 2), G + 4, G + 6, m["grate"])
            near = band & (np.abs(((th - ang + 180) % 360) - 180) < 12)
            self.integrity[near] = 0.97
            gname = {0: "east", 90: "south", 180: "west", -90: "north"}[ang]
            window = (r >= 78.5) & (r <= 91) & (np.abs(((th - ang + 180) % 360) - 180) < 14)
            self.site(f"gate_{gname}", f"The {gname.title()} Gate", 2, window, self.props_gate(ang))
            self.sign(int(round(86 * math.cos(math.radians(ang)))), G + 8, int(round(86 * math.sin(math.radians(ang)))),
                      toward(math.cos(math.radians(ang)), math.sin(math.radians(ang))), ["", f"{gname.upper()} GATE"])
            for off in (-1, 1):
                a = math.radians(ang + off * 7)
                self.tower(84 * math.cos(a), 84 * math.sin(a), 4.5, G + 14, cap=False, integrity=0.93)
        for ang in (45, 135, -45, -135):
            a = math.radians(ang)
            self.tower(84 * math.cos(a), 84 * math.sin(a), 6, G + 16, cap=True, integrity=0.75)
        # three breaches where the wall came down
        picks = []
        while len(picks) < 3:
            a = float(rng.uniform(-180, 180))
            near = min(abs(((a - b + 180) % 360) - 180) for b in (0, 90, 180, -90, 45, 135, -45, -135))
            if near > 16 and all(abs(((a - p + 180) % 360) - 180) > 40 for p in picks):
                picks.append(a)
        hn = noise2(dx.shape, 3, rng)
        for a in picks:
            w = rng.uniform(5, 9)
            d = np.abs(((th - a + 180) % 360) - 180)
            breach = (r >= 81) & (r < 87) & (d < w)
            for y in range(G, top + 3):
                keep_h = G + (hn * 3 * (d / w) * 2).astype(int)
                cut = breach & (y > keep_h)
                self.g.a[:, y, :][cut & (self.g.a[:, y, :] != VOID)] = AIR
                self.g.built[:, y, :][cut] = False
            spill = (r >= 76) & (r < 92) & (d < w + 2) & ~band
            hgt = (np.clip(1 - np.abs(r - 84) / 8, 0, 1) * 4 * hn).astype(int)
            for y in range(G, G + 4):
                fill = spill & (hgt > y - G)
                mix = np.choose(rng.integers(0, 4, dx.shape), [m["tuff_b"], m["gravel"], m["tuff"], m["cobble"]])
                self.g.a[:, y, :][fill] = mix[fill]
                self.g.built[:, y, :][fill] = False
            self.notes.append(f"wall breach at {a:.0f} degrees")

    def tower(self, fx, fz, rad, top, cap, integrity=0.7):
        m = self.m
        tx, tz = int(round(fx)), int(round(fz))
        tr = np.hypot(self.dx - tx, self.dz - tz)
        body = tr <= rad
        hollow = tr <= rad - 2
        self.g.column_mask(body, G, top, m["tuff_b"])
        self.g.column_mask(body & (tr > rad - 1), G, G + 1, m["tuff_pol"])
        self.g.column_mask(hollow, G + 1, top - 1, AIR, built=False)
        for y in range(G + 5, top, 5):
            self.g.column_mask(hollow, y, y, m["tuff_pol"])
        self.g.column_mask(body & (tr > rad - 1) & ((((np.degrees(np.arctan2(self.dz - tz, self.dx - tx)) + 180)
                                                      // 30).astype(int)) % 2 == 0), top + 1, top + 1,
                           self.wall("tuff_brick"))
        if cap:
            for j in range(0, 9):
                rr = rad + 1 - j * (rad + 1) / 8.5
                ring = (tr <= rr) & (tr > rr - 1.4)
                self.g.column_mask(ring, top + 1 + j, top + 1 + j, m["cu"])
            self.g.column_mask(tr <= 0.5, top + 9, top + 10, m["cu_block"])
        self.integrity[tr <= rad + 1] = integrity
        self.htop[tr <= rad + 1] = top + (10 if cap else 1)
        self.fine[tr <= rad + 1] = 0.25

    # ---------- the lots between the streets ----------
    def districts(self):
        """Fill the space between the streets: row houses along the avenues and the ring road first,
        then lots behind them with narrow alleys. Ruined houses, empty district plots, gardens, rubble."""
        rng = self.rng
        blocked = dilate(self.roads, 1) | self.occupied
        self.free = ~blocked & (self.r >= 23) & (self.r <= 77)
        # frontage on both sides of each avenue, doors on the avenue
        for axis in ("ns", "ew"):
            for side in (-1, 1):
                along = int(rng.integers(-77, -70))
                while along < 77:
                    w, d = int(rng.integers(6, 11)), int(rng.integers(8, 13))
                    near = 5 if side > 0 else -5 - d + 1
                    if axis == "ns":
                        x0, z0, door = near, along, "west" if side > 0 else "east"
                        x1, z1 = x0 + d - 1, z0 + w - 1
                    else:
                        x0, z0, door = along, near, "north" if side > 0 else "south"
                        x1, z1 = x0 + w - 1, z0 + d - 1
                    if self.try_lot(x0, z0, x1, z1, door, margin=0):
                        along += w + int(rng.integers(1, 3))
                    else:
                        along += 2
        # frontage outside and inside the ring road, facing it
        for rad, out in ((47, 1), (33, -1)):
            ang = float(rng.uniform(0, 360))
            stop = ang + 360
            while ang < stop:
                w, d = int(rng.integers(6, 10)), int(rng.integers(7, 11))
                a = math.radians(ang)
                cr = rad + out * d / 2
                cx, cz = int(round(cr * math.cos(a))), int(round(cr * math.sin(a)))
                x0, z0 = cx - w // 2, cz - d // 2
                door = toward(-out * cx, -out * cz)
                if door in ("east", "west"):
                    x0, z0 = cx - d // 2, cz - w // 2
                    x1, z1 = x0 + d - 1, z0 + w - 1
                else:
                    x1, z1 = x0 + w - 1, z0 + d - 1
                ok = self.try_lot(x0, z0, x1, z1, door, margin=0)
                ang += math.degrees((w + (2 if ok else 1)) / rad)
        # whatever room is left
        for _ in range(8000):
            w, d = int(rng.integers(6, 12)), int(rng.integers(6, 12))
            x0, z0 = int(rng.integers(-78, 78)), int(rng.integers(-78, 78))
            cx, cz = x0 + w / 2, z0 + d / 2
            if abs(cx) < abs(cz):
                door = "west" if cx > 0 else "east"
            else:
                door = "north" if cz > 0 else "south"
            self.try_lot(x0, z0, x0 + w - 1, z0 + d - 1, door, margin=1)
        self.old_paving()

    def try_lot(self, x0, z0, x1, z1, door, margin):
        rng, free = self.rng, self.free
        if x0 - margin < -R or z0 - margin < -R or x1 + margin > R or z1 + margin > R:
            return False
        if not free[R + x0 - margin:R + x1 + margin + 1, R + z0 - margin:R + z1 + margin + 1].all():
            return False
        w, d = x1 - x0 + 1, z1 - z0 + 1
        roll = rng.random()
        if roll < 0.6:
            floors = int(rng.choice([1, 2, 2, 3, 3]))
            wall = self.m["lime"] if rng.random() < 0.7 else self.m["lime_small"]
            roof = "copper" if rng.random() < 0.35 else "flat"
            self.house(x0, z0, x1, z1, floors, door, float(rng.uniform(0.45, 0.9)), roof, wall)
            kind = "house"
        elif roll < 0.68 and w >= 7 and d >= 7:
            x1, z1 = x0 + 6, z0 + 6
            self.house(x0, z0, x1, z1, 4, door, float(rng.uniform(0.5, 0.8)), "copper")
            kind = "tower house"
        elif roll < 0.82:
            self.plot(x0, z0, x1, z1)
            kind = "district plot"
        elif roll < 0.91:
            self.garden(x0, z0, x1, z1)
            kind = "garden"
        else:
            self.mound(x0, z0, x1, z1)
            kind = "rubble"
        self.lots.append((kind, x0, z0, x1, z1))
        free[R + x0 - 1:R + x1 + 2, R + z0 - 1:R + z1 + 2] = False
        return True

    def old_paving(self):
        """What's left of the city's paving between buildings, under four centuries of grass."""
        m, rng = self.m, self.rng
        n = noise2(self.dx.shape, 6, rng)
        speck = rng.random(n.shape)
        g = self.g.a[:, G - 1, :]
        open_ground = (g == m["grass"]) & (self.r >= 20) & (self.r <= 80) & ~self.occupied
        paved = open_ground & (n > 0.42) & (speck < 0.8)
        mix = np.choose(rng.integers(0, 5, n.shape), [m["lime_cut"], m["lime_small"], m["tuff_b"], m["tuff"],
                                                       m["cobble"]])
        g[paved] = mix[paved]
        g[open_ground & (n > 0.42) & (speck >= 0.8) & (speck < 0.9)] = m["coarse"]

    def plot(self, x0, z0, x1, z1):
        """An empty foundation: where a restored district goes up later."""
        m, rng = self.m, self.rng
        self.box(x0, G - 1, z0, x1, G - 1, z1, m["coarse"], built=False)
        for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
            self.box(ax, G - 1, az, bx, G - 1, bz, m["tuff_pol"], built=False)
            self.box(ax, G, az, bx, G, bz, m["lime"])
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, 0.35)

    def garden(self, x0, z0, x1, z1):
        m, rng = self.m, self.rng
        for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
            self.box(ax, G, az, bx, G, bz, self.wall("create:cut_limestone"))
        self.tree((x0 + x1) // 2, (z0 + z1) // 2, "birch" if rng.random() < .4 else "oak")
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, 0.5)

    def mound(self, x0, z0, x1, z1):
        m, rng = self.m, self.rng
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        rx, rz = (x1 - x0) / 2 + .5, (z1 - z0) / 2 + .5
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                d = ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2
                if d <= 1:
                    h = int((1 - d) * 4 + rng.random())
                    mix = [m["lime"], m["lime_raw"], m["cobble"], m["gravel"], m["tuff"], m["lime_layer"]]
                    for y in range(G, G + h):
                        self.put(x, y, z, mix[int(rng.integers(0, len(mix)))], built=False)
                    if h:
                        self.put(x, G + h - 1, z, m["moss"] if rng.random() < .3 else m["lime_raw"], built=False)
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, 0.4)

    def tree(self, x, z, kind="oak", height=None):
        rng, s = self.rng, self.g.s
        h = height or int(rng.integers(5, 8))
        log, leaves = s(f"{kind}_log", axis="y"), s(f"{kind}_leaves", distance=1, persistent=True,
                                                  waterlogged=False)
        y0 = G
        while self.get(x, y0, z) not in (AIR,) and y0 < G + 20:
            y0 += 1
        self.box(x, G - 1, z, x, G - 1, z, self.m["dirt"], built=False)
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                for dy in range(-2, 3):
                    if dx * dx + dz * dz + (dy * 1.4) ** 2 <= 7.5 + rng.random() * 2:
                        if self.get(x + dx, y0 + h + dy, z + dz) == AIR:
                            self.put(x + dx, y0 + h + dy, z + dz, leaves, built=False)
        self.box(x, y0, z, x, y0 + h, z, log, built=False)

    # ---------- time ----------
    def decay(self):
        g, rng = self.g, self.rng
        self.pre_a = g.a.copy()  # the city as designed, before time: restoration rebuilds from this
        self.removed = np.zeros(g.shape, bool)
        before = g.built & (g.a > AIR)
        cand = before & ~g.keep
        cand[:, :G, :] = False
        f = self.fine[:, None, :]
        n = noise3(g.shape, 7, rng) * (1 - f) + (noise3(g.shape, 2, rng) * 0.65 + rng.random(g.shape, np.float32) * 0.35) * f
        vals = n[cand]
        rank = np.empty(len(vals), np.float32)
        rank[np.argsort(vals)] = np.linspace(0, 1, len(vals), dtype=np.float32)
        q = np.zeros(g.shape, np.float32)
        q[cand] = rank
        ys = np.arange(g.shape[1], dtype=np.float32)[None, :, None]
        integ = self.integrity[:, None, :]
        # ground floors mostly stand; roofs and upper floors mostly don't
        hf = np.clip((ys - G) / np.maximum(self.htop[:, None, :] - G, 4), 0, 1)
        p_remove = np.clip((1 - integ) * 0.5 - 0.05 + 0.62 * hf ** 1.2, 0, 0.95)
        gone = cand & (q < p_remove)
        self.removed |= gone
        g.a[gone] = AIR
        g.built[gone] = False
        removed = (gone.sum(axis=1)).astype(np.float32)
        self.rubble(removed)
        self.weather()
        for _ in range(3):
            self.unfloat()
        self.anchor()

    def rubble(self, removed):
        m, g, rng = self.m, self.g, self.rng
        spread = box_blur(removed, 2)
        height = spread * 0.45 + rng.random(spread.shape) * 0.6
        mix = [m["lime"], m["lime_raw"], m["cobble"], m["gravel"], m["tuff"], m["lime_layer"], m["andesite"]]
        tops = [self.slab("create:cut_limestone"), self.slab("tuff_brick"), m["moss"], self.slab("cobblestone")]
        sus = self.g.s("suspicious_gravel", dusted=0)
        xs, zs = np.nonzero(height >= 1)
        for x, z in zip(xs.tolist(), zs.tolist()):
            h = min(int(height[x, z]), 3)
            if g.a[x, G - 1, z] in (AIR, VOID) or self.roads[x, z] and rng.random() < 0.6:
                continue
            for k in range(h):
                if g.a[x, G + k, z] != AIR:
                    break
                st = tops[int(rng.integers(0, 4))] if k == h - 1 else mix[int(rng.integers(0, 7))]
                if st == m["gravel"] and rng.random() < 0.15:  # brush it for what's buried
                    st = sus
                    g.block_nbt[(x, G + k, z)] = {"id": "minecraft:brushable_block", "LootTable": "remnant:ruins/rubble"}
                g.a[x, G + k, z] = st

    def weather(self):
        m, g, rng = self.m, self.g, self.rng
        roll = rng.random(g.shape)
        for src, dst, p in ((m["lime"], m["lime_raw"], .07), (m["lime"], m["lime_layer"], .04),
                            (m["lime_small"], m["lime_raw"], .06), (m["tuff_b"], m["tuff"], .08),
                            (m["ds_b"], self.g.s("cracked_deepslate_bricks"), .12),
                            (m["ds_t"], self.g.s("cracked_deepslate_tiles"), .1)):
            sel = (g.a == src) & ~g.keep & (roll < p)
            g.a[sel] = dst
            roll = rng.random(g.shape)

    def unfloat(self):
        g = self.g
        b = g.built & (g.a > AIR) & ~g.keep
        below_air = np.zeros_like(b)
        below_air[:, 1:, :] = g.a[:, :-1, :] <= AIR
        solid = g.a > AIR
        nb = np.zeros(g.shape, np.int8)
        nb[1:] += solid[:-1]
        nb[:-1] += solid[1:]
        nb[:, :, 1:] += solid[:, :, :-1]
        nb[:, :, :-1] += solid[:, :, 1:]
        drop = b & below_air & (nb < 2)
        self.removed |= drop
        g.a[drop] = AIR
        g.built[drop] = False

    def anchor(self):
        """Drop anything the decay cut loose from the ground: no floating floors or platforms."""
        g = self.g
        solid = g.a > AIR
        reach = np.zeros(g.shape, bool)
        reach[:, :G, :] = solid[:, :G, :]
        count = int(reach.sum())
        for _ in range(800):
            grow = reach.copy()
            grow[1:] |= reach[:-1]
            grow[:-1] |= reach[1:]
            grow[:, 1:] |= reach[:, :-1]
            grow[:, :-1] |= reach[:, 1:]
            grow[:, :, 1:] |= reach[:, :, :-1]
            grow[:, :, :-1] |= reach[:, :, 1:]
            grow &= solid
            n = int(grow.sum())
            reach = grow
            if n == count:
                break
            count = n
        loose = solid & ~reach & g.built & ~g.keep
        self.removed |= loose
        g.a[loose] = AIR
        g.built[loose] = False
        self.notes.append(f"{int(loose.sum())} loose blocks dropped")

    def full_cubes(self):
        from render import shape_of
        return np.array([shape_of(k) == "cube" and "_stairs" not in k for k in self.g.pal])

    def overgrowth(self):
        m, g, rng, s = self.m, self.g, self.rng, self.g.s
        grass_top = (g.a[:, G - 1, :] == m["grass"]) & (g.a[:, G, :] == AIR)
        roll = rng.random(grass_top.shape)
        flowers = ["poppy", "dandelion", "oxeye_daisy", "cornflower", "azure_bluet"]
        g.a[:, G, :][grass_top & (roll < 0.3)] = s("short_grass")
        g.a[:, G, :][grass_top & (roll >= 0.3) & (roll < 0.36)] = s("fern")
        fl = grass_top & (roll >= 0.36) & (roll < 0.385)
        g.a[:, G, :][fl] = np.array([s(f) for f in flowers], np.uint16)[rng.integers(0, 5, fl.shape)][fl]
        tall = grass_top & (roll >= 0.385) & (roll < 0.4) & (g.a[:, G + 1, :] == AIR)
        g.a[:, G, :][tall] = s("tall_grass", half="lower")
        g.a[:, G + 1, :][tall] = s("tall_grass", half="upper")
        # moss creeping over paving and up the rubble
        n = noise2(grass_top.shape, 7, rng)
        paved = (g.a[:, G - 1, :] > AIR) & (g.a[:, G, :] == AIR) & ~grass_top & ~g.keep[:, G - 1, :]
        carpet = paved & (n > 0.6) & (rng.random(n.shape) < 0.6)
        g.a[:, G, :][carpet] = s("moss_carpet")
        # vines down exposed walls
        solid = (g.a > AIR) & g.built
        count = 0
        for face, (ox, oz) in DIRS.items():
            prop = OPPOSITE[face]
            vine = s("vine", **{"up": False, "north": prop == "north", "south": prop == "south",
                                "east": prop == "east", "west": prop == "west"})
            xs, ys, zs = np.nonzero(solid[max(0, -ox):g.shape[0] - max(0, ox), G + 2:, max(0, -oz):g.shape[2] - max(0, oz)])
            pick = rng.random(len(xs)) < 0.012
            for x, y, z in zip(xs[pick].tolist(), ys[pick].tolist(), zs[pick].tolist()):
                x, y, z = x + max(0, -ox), y + G + 2, z + max(0, -oz)
                vx, vz = x + ox, z + oz
                for k in range(int(rng.integers(2, 9))):
                    if g.a[vx, y - k, vz] != AIR or not solid[x, y - k, z]:
                        break
                    g.a[vx, y - k, vz] = vine
                    count += 1
        # glow lichen in the crypt and the spire
        lichen = {}
        for face, (ox, oz) in DIRS.items():
            lichen[face] = s("glow_lichen", **{"down": False, "up": False, "north": face == "north",
                                               "south": face == "south", "east": face == "east",
                                               "west": face == "west", "waterlogged": False})
        full = self.full_cubes()
        for _ in range(500):
            x = int(rng.integers(R - 70, R - 46))
            z = int(rng.integers(R - 36, R - 18))
            y = int(rng.integers(G - 8, G - 3))
            if g.a[x, y, z] == AIR:
                for face, (ox, oz) in DIRS.items():
                    if full[g.a[x + ox, y, z + oz]] and g.built[x + ox, y, z + oz]:
                        g.a[x, y, z] = lichen[face]
                        break
        # a few trees that grew up through the ruins
        for kind, x0, z0, x1, z1 in self.lots:
            if kind == "house" and rng.random() < 0.18:
                self.tree((x0 + x1) // 2, (z0 + z1) // 2, "oak" if rng.random() < .6 else "birch")
        self.notes.append(f"{count} vine blocks")

    def connect(self):
        """Set wall, bar and pane connections so WorldEdit pastes them joined up."""
        g = self.g
        from render import shape_of
        kinds = {}
        for i, k in enumerate(g.pal):
            name = k.split("[")[0]
            if name.endswith("_wall"):
                kinds[i] = "wall"
            elif name.endswith("iron_bars") or name.endswith("_pane") or name.endswith("_fence"):
                kinds[i] = "bars"
        joinable = [shape_of(k) == "cube" or i in kinds for i, k in enumerate(g.pal)]
        full = self.full_cubes()
        targets = np.array(list(kinds), np.uint16)
        xs, ys, zs = np.nonzero(np.isin(g.a, targets))
        sx, sy, sz = g.shape
        for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
            joinable += [True] * (len(g.pal) - len(joinable))  # new connection states are walls and bars too
            i = int(g.a[x, y, z])
            if i not in kinds:
                kinds[i] = "wall" if g.pal[i].split("[")[0].endswith("_wall") else "bars"
            name = g.pal[i].split("[")[0]
            side = {}
            for face, (ox, oz) in DIRS.items():
                nx, nz = x + ox, z + oz
                side[face] = 0 <= nx < sx and 0 <= nz < sz and bool(joinable[g.a[nx, y, nz]])
            if kinds[i] == "wall":
                above = y + 1 < sy and bool(full[min(int(g.a[x, y + 1, z]), len(full) - 1)]) and \
                    int(g.a[x, y + 1, z]) < len(full)
                straight = (side["north"] and side["south"] and not side["east"] and not side["west"]) or \
                           (side["east"] and side["west"] and not side["north"] and not side["south"])
                props = {f: ("tall" if above else "low") if side[f] else "none" for f in DIRS}
                g.a[x, y, z] = g.s(name, up=not straight or above, waterlogged=False, **props)
            else:
                g.a[x, y, z] = g.s(name, waterlogged=False, **{f: side[f] for f in DIRS})

    # ---------- all together ----------
    def build(self):
        self.terrain()
        self.streets()
        self.plaza()
        self.elder_house()
        self.camp()
        self.spire()
        self.market()
        self.crypt()
        self.mast()
        self.walls()
        self.districts()
        self.decay()
        self.place_signs()
        self.overgrowth()
        self.connect()


BE_BLOCKS = {"minecraft:sign": "_sign", "minecraft:brushable_block": "suspicious_", "minecraft:barrel": "barrel",
             "minecraft:decorated_pot": "decorated_pot"}


def prune_block_nbt(g):
    """Drop block-entity data whose block was later replaced by something else."""
    for (x, y, z), be in list(g.block_nbt.items()):
        if BE_BLOCKS.get(be["id"], "~") not in g.pal[int(g.a[x, y, z])]:
            del g.block_nbt[(x, y, z)]


def write_site(city, name, out_dir):
    """A site's restoration as layered structure templates plus functions that place them a few at a time."""
    g, site = city.g, city.sites[name]
    new = city.restore(name)
    diff = new != g.a
    if not diff.any():
        return 0
    cols = site["mask"]
    xs, zs = np.nonzero(cols.any(axis=1))[0], np.nonzero(cols.any(axis=0))[0]
    x0, x1, z0, z1 = int(xs.min()), int(xs.max()) + 1, int(zs.min()), int(zs.max()) + 1
    ys = np.nonzero(diff.any(axis=(0, 2)))[0]
    tdir = os.path.join(out_dir, "data", "remnant", "structure", "core", "site")
    fdir = os.path.join(out_dir, "data", "remnant", "function", "restore", name)
    os.makedirs(tdir, exist_ok=True)
    os.makedirs(fdir, exist_ok=True)
    at = "execute at @e[type=minecraft:marker,tag=remnant_core,limit=1] run"
    ox, oy, oz = x0 - R, -(G - 1), z0 - R
    cx, cz = int((x0 + x1) / 2) - R, int((z0 + z1) / 2) - R
    levels = list(range(int(ys.min()), int(ys.max()) + 1, 3))
    for k, y0 in enumerate(levels):
        part = np.full(g.shape, VOID, np.uint16)
        sel = diff.copy()
        sel[:, :y0, :] = False
        sel[:, y0 + 3:, :] = False
        part[sel] = new[sel]
        ns = types.SimpleNamespace(a=part, pal=g.pal, block_nbt={})
        Grid.write_structure(ns, os.path.join(tdir, f"{name}_{k}.nbt"), x0, x1, z0, z1)
        cy = y0 - (G - 1)
        lines = [f"{at} place template remnant:core/site/{name}_{k} ~{ox} ~{oy} ~{oz}",
                 f"{at} playsound minecraft:block.stone.place block @a ~{cx} ~{cy} ~{cz} 4 0.6",
                 f"{at} particle minecraft:poof ~{cx} ~{cy + 1} ~{cz} {(x1 - x0) / 4:.1f} 1 {(z1 - z0) / 4:.1f} 0.02 120"]
        if k + 1 < len(levels):
            lines.append(f"schedule function remnant:restore/{name}/{k + 1} 8t")
        else:
            lines += [f'tellraw @a {{"text":"{site["label"]} stands again.","color":"gold"}}',
                      "playsound minecraft:ui.toast.challenge_complete master @a"]
        with open(os.path.join(fdir, f"{k}.mcfunction"), "w") as f:
            f.write("\n".join(lines) + "\n")
    with open(os.path.join(fdir, "..", f"{name}.mcfunction"), "w") as f:
        f.write(f"# Restore {site['label']} (Age {site['age']}), layer by layer over a few seconds.\n"
                f"# Needs the core's marker: summon minecraft:marker on the Hearth's ground block, tagged remnant_core.\n"
                f"function remnant:restore/{name}/0\n")
    return int(diff.sum())


LOOT = {
    "house": {"type": "minecraft:chest", "pools": [{"rolls": {"min": 1, "max": 4}, "entries": [
        {"type": "minecraft:item", "name": n, "weight": w,
         "functions": [{"function": "minecraft:set_count", "count": {"min": 1, "max": c}}]}
        for n, w, c in (("minecraft:bone", 10, 3), ("minecraft:string", 8, 3), ("minecraft:paper", 8, 3),
                        ("minecraft:flint", 8, 2), ("minecraft:iron_nugget", 6, 4), ("minecraft:copper_ingot", 4, 2),
                        ("minecraft:candle", 4, 2), ("minecraft:amethyst_shard", 3, 2), ("minecraft:book", 1, 1))]}]},
    "rubble": {"type": "minecraft:archaeology", "pools": [{"rolls": 1, "entries": [
        {"type": "minecraft:item", "name": n, "weight": w}
        for n, w in (("minecraft:flint", 6), ("minecraft:bone", 4), ("minecraft:iron_nugget", 4),
                     ("minecraft:paper", 3), ("minecraft:amethyst_shard", 3), ("minecraft:copper_ingot", 2),
                     ("minecraft:brewer_pottery_sherd", 1), ("minecraft:archer_pottery_sherd", 1))]}]},
}


class View:
    """A rectangular window onto a Grid, for close-up renders."""
    def __init__(self, g, x0, x1, z0, z1):
        self.a, self.pal = g.a[x0:x1, :, z0:z1], g.pal


def validate(grid, assets):
    """Every block must exist in the jars, and every property must be one the block has."""
    problems = []
    for key in grid.pal:
        name, _, rest = key.partition("[")
        ns, _, bare = name.partition(":")
        bs = assets.json(f"assets/{ns}/blockstates/{bare}.json")
        if bs is None:
            problems.append(f"unknown block {name}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out")
    ap.add_argument("--jar", action="append", default=[])
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    city = City(a.seed)
    city.build()
    g = city.g
    counts = np.bincount(g.a.ravel(), minlength=len(g.pal))
    print(f"palette {len(g.pal)} states, {int((g.a > AIR).sum())} blocks, {int((g.a == AIR).sum())} air")
    kinds = {}
    for k, *_ in city.lots:
        kinds[k] = kinds.get(k, 0) + 1
    print("lots:", kinds)
    for n in city.notes:
        print(n)
    if a.jar:
        from render import Assets, iso, plan
        assets = Assets(a.jar)
        probs = validate(g, assets)
        print("validation:", "ok" if not probs else probs)
        if not a.no_render:
            plan(g, assets, G).save(os.path.join(a.out, "plan.png"))
            iso(g, assets, scale=4).save(os.path.join(a.out, "iso.png"))
            iso(View(g, R - 46, R + 46, R - 46, R + 40), assets, scale=9).save(os.path.join(a.out, "iso_centre.png"))
    prune_block_nbt(g)
    g.write_schem(os.path.join(a.out, "core.schem"), offset=(-R, -G, -R))
    tiles = os.path.join(a.out, "datapack", "data", "remnant", "structure", "core")
    os.makedirs(tiles, exist_ok=True)
    dp = os.path.join(a.out, "datapack")
    for table, body in LOOT.items():  # placeholders until the lore items (Torn Pages, Memory Shards) exist
        ldir = os.path.join(dp, "data", "remnant", "loot_table", "ruins")
        os.makedirs(ldir, exist_ok=True)
        with open(os.path.join(ldir, f"{table}.json"), "w") as f:
            json.dump(body, f, indent=1)
    for name in city.sites:
        print(f"site {name}: {write_site(city, name, dp)} blocks change when restored")
    with open(os.path.join(a.out, "datapack", "pack.mcmeta"), "w") as f:
        f.write('{"pack": {"pack_format": 48, "description": "Remnant city core (generated)"}}\n')
    step = 97
    for i, x0 in enumerate(range(0, g.shape[0], step)):
        for j, z0 in enumerate(range(0, g.shape[2], step)):
            g.write_structure(os.path.join(tiles, f"tile_{i}_{j}.nbt"), x0, min(x0 + step, g.shape[0]),
                              z0, min(z0 + step, g.shape[2]))
    with open(os.path.join(a.out, "samples.txt"), "w") as f:  # one position per state, in /place coordinates
        flat = g.a.ravel()
        for i in range(2, len(g.pal)):
            hit = np.flatnonzero(flat == i)
            if len(hit):
                x, y, z = np.unravel_index(hit[len(hit) // 2], g.shape)
                f.write(f"{x - R} {y - (G - 1)} {z - R} {g.pal[i]}\n")
    print("used:", ", ".join(f"{g.pal[i]}={c}" for i, c in sorted(enumerate(counts), key=lambda t: -t[1])[:12]))


if __name__ == "__main__":
    main()
