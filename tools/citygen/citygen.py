"""Generate Remainder, Remnant's ruined city core: the Ascendancy city the group restores at spawn.

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
# What each ruined building was, written over its door in runes; restoring it brings the trade back:
# the villager profession that moves in and the workstation they need ("|" breaks the sign line)
TRADES = {"LAMPWRIGHT": ("toolsmith", "smithing_table"), "COPPERSMITH": ("armorer", "blast_furnace"),
          "SCRIBE": ("librarian", "lectern"), "CHANDLER": ("cleric", "brewing_stand"), "WEAVER": ("shepherd", "loom"),
          "GLASSWORKS": ("mason", "stonecutter"), "BATHS": ("leatherworker", "cauldron"),
          "AETHER|WORKS": ("cleric", "brewing_stand"), "HOUSE|VELL": (None, None), "HOUSE|ORREN": (None, None),
          "HOUSE|MAREK": (None, None), "COUNTING|HOUSE": ("librarian", "lectern"), "APOTHECARY": ("cleric", "brewing_stand"),
          "BAKER": ("farmer", "composter"), "SCHOOL": ("librarian", "lectern"), "LODGINGS": (None, None),
          "CLOCKMAKER": ("toolsmith", "smithing_table"), "CARTOGRAPHER": ("cartographer", "cartography_table"),
          "TEA|HOUSE": ("butcher", "smoker"), "LENSGRINDER": ("mason", "stonecutter"),
          "FLETCHER": ("fletcher", "fletching_table"), "FISHMONGER": ("fisherman", "barrel")}
TRADE_NAMES = sorted(TRADES)
JOB_PROPS = {"blast_furnace": {"lit": False}, "lectern": {"has_book": False, "powered": False},
             "brewing_stand": {"has_bottle_0": False, "has_bottle_1": False, "has_bottle_2": False},
             "composter": {"level": 0}, "smoker": {"lit": False}, "barrel": {"open": False}}
FACED = ("blast_furnace", "lectern", "loom", "stonecutter", "smoker")
FREE_PLOTS = 8
# Remnant repairs show the Age they were made in: masonry by Age, metal salvaged and put back
# Repairs match the old stone's tone but not its finish, so you can still see what was mended and when.
# Each entry: (full block, stairs/slab base, wall base)
REPAIR_LIGHT = {1: ("mud_bricks", "mud_brick", "mud_brick"), 2: ("calcite", "diorite", "diorite"),
                3: ("polished_diorite", "polished_diorite", "diorite"), 4: ("quartz_bricks", "quartz", "diorite")}
REPAIR_DARK = {1: ("mud_bricks", "mud_brick", "mud_brick"), 2: ("cobbled_deepslate", "cobbled_deepslate", "cobbled_deepslate"),
               3: ("deepslate_bricks", "deepslate_brick", "deepslate_brick"),
               4: ("polished_deepslate", "polished_deepslate", "polished_deepslate")}
DARK = ("deepslate", "blackstone", "industrial_iron", "weathered_iron", "tuff", "basalt")
FLOOR = {1: "mud_brick", 2: "spruce", 3: "spruce", 4: "stone"}  # floors and roofs (cut limestone) by Age
FULL = {"mud_brick": "mud_bricks", "stone_brick": "stone_bricks", "brick": "bricks", "spruce": "spruce_planks"}
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
        self.sites = {}  # what the group restores: landmarks and houses, each with a footprint
        self.free_plots = 0
        self.trade_deck = []
        self.towers = []
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
            # the Ascendancy's aether-tech: white quartz, dark iron, violet glass, crystal conduits
            "qz": s("smooth_quartz"), "qz_b": s("quartz_bricks"), "qz_p": s("quartz_pillar", axis="y"),
            "qz_ch": s("chiseled_quartz_block"), "calcite": s("calcite"),
            "iron": s("create:industrial_iron_block"), "iron_w": s("create:weathered_iron_block"),
            "aether": s("amethyst_block"), "aether_lit": s("pearlescent_froglight", axis="y"),
            "shingle": s("create:oxidized_copper_shingles"),
            "glass_v": s("purple_stained_glass_pane", north=False, east=False, south=False, west=False, waterlogged=False),
            "glass_w": s("white_stained_glass_pane", north=False, east=False, south=False, west=False, waterlogged=False),
            "glass_vb": s("purple_stained_glass"), "rod": s("end_rod", facing="up"),
            "bars": s("iron_bars", north=False, east=False, south=False, west=False, waterlogged=False),
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

    def site(self, name, label, age, mask, props=None, layer=3, summon=()):
        """age: the earliest Age it can be restored in. Repairs use the Age it's actually finished in."""
        self.sites[name] = {"label": label, "age": age, "mask": mask, "props": props, "layer": layer,
                            "summon": list(summon)}

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
        props = dict(p.split("=", 1) for p in rest.rstrip("]").split(",")) if rest else {}
        full, part, wallb = (REPAIR_DARK if any(w in bare for w in DARK) else REPAIR_LIGHT)[age]
        if name in ("create:cut_limestone", "create:cut_limestone_slab", "create:cut_limestone_stairs"):
            base = FLOOR[age]  # floors and roofs
            full, part = FULL.get(base, base), base
        if bare.endswith("_wall"):
            return self.g.s(wallb + "_wall", **props)
        for kind in ("_stairs", "_slab"):
            if bare.endswith(kind):
                return self.g.s(part + kind, **props)
        return self.g.s(full)

    def restore(self, name, age):
        """The site as the group rebuilds it in a given Age: fallen blocks put back in that Age's materials,
        rubble and weeds cleared, and whatever the site adds."""
        g, site = self.g, self.sites[name]
        mask = np.repeat(site["mask"][:, None, :], g.shape[1], axis=1)
        new = g.a.copy()
        fill = mask & self.removed
        for i in np.unique(self.pre_a[fill]):
            new[fill & (self.pre_a == i)] = self.repair(int(i), age)
        plants = self.g.ids_where(lambda k: any(p in k for p in ("grass[", "short_grass", "tall_grass", "fern",
                                                                    "poppy", "dandelion", "daisy", "cornflower",
                                                                    "bluet")))
        junk = mask & (self.pre_a == AIR) & (g.a > AIR) & ~g.keep & ~np.isin(g.a, plants)
        junk[:, :G, :] = False
        new[junk] = AIR
        deb = mask & self.debris
        new[deb] = self.pre_a[deb]
        if site["props"]:
            site["props"](new, age)
        if age >= 5:  # the aether flows again
            new[mask & (new == self.m["aether"])] = self.m["aether_lit"]
        return new

    def props_hearth(self, new, age):
        """Age I, Rekindle the Hearth: the brazier burns, and torches sit where the lamps no longer work."""
        s = self.g.s
        self.wput(new, 0, G, 0, s("campfire", lit=True, facing="north", signal_fire=False, waterlogged=False))
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.wput(new, 8 * sx, G + 3, 8 * sz, s("torch"))

    def props_market(self, new, age):
        """The market bell: townsfolk gather at it."""
        self.wput(new, 59, G, 6, self.g.s("bell", attachment="floor", facing="north", powered=False))

    # ---------- the Ascendancy's buildings ----------
    def hab_tower(self, cx, cz, rad, floors, door, integrity):
        """A habitation tower: a white quartz shaft that tapers as it rises, thin dark iron ribs, ribbon windows
        of violet or clear glass, white ledges and glass-railed balconies, a dead aether conduit up one rib,
        a flared dark base, and a glass dome ringed by a small copper halo like the Spire's."""
        m, s, rng, g = self.m, self.g.s, self.rng, self.g
        lx, lz = self.dx - cx, self.dz - cz
        d = np.hypot(lx, lz)
        ang = np.degrees(np.arctan2(lz, lx))
        top = G + floors * 4
        glass = m["glass_v"] if rng.random() < 0.6 else m["glass_w"]
        rail = s("white_stained_glass_pane", north=False, east=False, south=False, west=False, waterlogged=False)
        nrib = 8 if rad >= 4.5 else 6
        step = 360 / nrib
        conduit_ang = float(rng.integers(0, nrib)) * step
        g.column_mask((d > rad) & (d <= rad + 2), G, G, self.slab("polished_deepslate"))
        g.column_mask((d > rad) & (d <= rad + 1), G, G, m["ds_pol"])
        base_inside = d <= rad - 1.0
        g.column_mask(base_inside, G - 1, G - 1, m["lime_pol"], built=False)
        r_at = lambda y: max(rad - 0.14 * ((y - G) // 4), rad - 1.2)
        for y in range(G, top + 1):
            ry = r_at(y)
            shell = (d <= ry) & (d > ry - 1.0)
            inside = d <= ry - 1.0
            rib = shell & (np.abs(((ang + step / 2) % step) - step / 2) < math.degrees(0.5 / ry))
            conduit = rib & (np.abs(((ang - conduit_ang + 180) % 360) - 180) < step / 2)
            k, f = divmod(y - G, 4)
            if y == G:
                g.column_mask(shell, y, y, m["ds_pol"])
                continue
            if f == 0:
                g.column_mask(shell, y, y, m["qz"])
                g.column_mask(inside, y, y, m["lime_cut"])
                if k % 2 == 0 and k < floors:  # a glass-railed balcony every other floor
                    g.column_mask((d > ry) & (d <= ry + 1.6), y, y, self.slab("smooth_quartz", "top"))
                    g.column_mask((d > ry + 0.7) & (d <= ry + 1.6), y + 1, y + 1, rail)
                else:
                    g.column_mask((d > ry) & (d <= ry + 1), y, y, self.slab("smooth_quartz", "top"))
            elif f in (1, 2):
                g.column_mask(shell & ~rib, y, y, glass)
                g.column_mask(rib, y, y, m["iron"])
            else:
                g.column_mask(shell & ~rib, y, y, m["qz"])
                g.column_mask(rib, y, y, m["iron"])
            g.column_mask(conduit & (f != 0), y, y, m["aether"])
        # the crown: a violet glass dome on dark ribs, a copper halo held off it on four spokes, an antenna
        rt = r_at(top)
        y = top
        for t in range(1, int(rt) + 2):
            rr = math.sqrt(max(rt * rt - (t - 0.3) ** 2, 0))
            layer = (d <= rr + 0.35) & (d > rr - 1.15)
            if not layer.any():
                break
            y = top + t
            rib = layer & (np.abs(((ang + step / 2) % step) - step / 2) < math.degrees(0.6 / max(rr, 1)))
            g.column_mask(layer & ~rib, y, y, m["glass_vb"])
            g.column_mask(rib, y, y, m["iron"])
        hy = top + 2
        halo = np.abs(d - (rt + 1.6)) < 0.55
        g.column_mask(halo, hy, hy, self.slab("oxidized_cut_copper"))
        for a in (0, 90, 180, 270):
            for t in range(int(rt), int(rt + 2)):
                self.put(cx + int(round(t * math.cos(math.radians(a)))), hy, cz + int(round(t * math.sin(math.radians(a)))),
                         m["iron"])
        self.box(cx, y + 1, cz, cx, y + 3, cz, m["rod"])
        self.put(cx, y + 4, cz, s("lightning_rod", facing="up", powered=False, waterlogged=False))
        # the door, a canopy and two sconces
        shell0 = (d <= rad) & (d > rad - 1.0)
        ddx, ddz = DIRS[door]
        k = 0
        for t in range(int(rad) + 2):
            if shell0[R + cx + ddx * t, R + cz + ddz * t]:
                k = t
        px, pz = cx + ddx * k, cz + ddz * k
        self.box(px, G, pz, px, G + 2, pz, AIR, built=False)
        tx, tz = (1, 0) if ddz else (0, 1)
        for o in (-1, 0, 1):
            self.put(px + ddx + tx * o, G + 3, pz + ddz + tz * o, self.slab("smooth_quartz", "top"))
        for o in (-1, 1):
            self.put(px + ddx + tx * o, G + 2, pz + ddz + tz * o, s("end_rod", facing=door))
        r2 = int(math.ceil(rad)) + 3
        self.towers.append(dict(cx=cx, cz=cz, rad=rad, floors=floors))
        self.claim(cx - r2, cz - r2, cx + r2, cz + r2, integrity, y)
        self.fine[R + cx - r2:R + cx + r2 + 1, R + cz - r2:R + cz + r2 + 1] = 0.12
        cells = [(int(a) - R, int(b) - R) for a, b in zip(*np.nonzero(base_inside))]
        return dict(door=door, px=px, pz=pz, inside=cells, top=top, floors=floors, cx=cx, cz=cz)

    def terrace(self, x0, z0, x1, z1, door, tiers, integrity):
        """A terraced hall: tiers stepping back from the street, each with a full-height glass front in thin
        quartz mullions under a thin roof plate that overhangs it; chamfered corners; ribbon windows down the
        sides; planted terraces on the setbacks and a roof garden on top."""
        m, s, rng = self.m, self.g.s, self.rng
        ddx, ddz = DIRS[door]
        glass = m["glass_v"] if rng.random() < 0.5 else m["glass_w"]
        planters = [s("azalea"), s("flowering_azalea"), s("short_grass")]
        plate = self.slab("smooth_quartz", "top")

        def tier_rect(k):
            a, b, c, e = x0, z0, x1, z1
            if door == "north":
                b += 2 * k
            elif door == "south":
                e -= 2 * k
            elif door == "west":
                a += 2 * k
            else:
                c -= 2 * k
            return a, b, c, e
        self.box(x0 + 1, G - 1, z0 + 1, x1 - 1, G - 1, z1 - 1, m["lime_pol"], built=False)
        for k in range(tiers):
            a, b, c, e = tier_rect(k)
            yb, yt = G + 4 * k, G + 4 * k + 4
            self.box(a, yb, b, c, yt - 1, e, m["qz"])
            self.box(a + 1, yb + (1 if k else 0), b + 1, c - 1, yt - 1, e - 1, AIR, built=False)
            self.box(a, yt, b, c, yt, e, m["lime_cut"])
            if k == 0:
                for (p, q, r_, t_) in ((a, b, c, b), (a, e, c, e), (a, b, a, e), (c, b, c, e)):
                    self.box(p, G, q, r_, G, t_, m["ds_pol"])
            # the roof plate overhangs every side by one
            for (p, q, r_, t_) in ((a - 1, b - 1, c + 1, b - 1), (a - 1, e + 1, c + 1, e + 1),
                                   (a - 1, b, a - 1, e), (c + 1, b, c + 1, e)):
                self.box(p, yt, q, r_, yt, t_, plate)
            for (p, q, r_, t_, side) in ((a, b, c, b, "north"), (a, e, c, e, "south"), (a, b, a, e, "west"),
                                         (c, b, c, e, "east")):
                cells = [(x, z) for x in range(p, r_ + 1) for z in range(q, t_ + 1)]
                for i, (x, z) in enumerate(cells):
                    if (x in (a, c)) and (z in (b, e)):  # chamfered corner
                        self.box(x, yb + (1 if k == 0 else 0), z, x, yt - 1, z, AIR, built=False)
                        continue
                    if i == 1 or i == len(cells) - 2:
                        self.box(x, yb + 1, z, x, yt - 1, z, m["qz_p"])
                    elif side == door:
                        self.box(x, yb + 1, z, x, yt - 1, z, m["qz_p"] if i % 3 == 1 else glass)
                    else:
                        self.box(x, yb + 2, z, x, yb + 3, z, glass)
            if k + 1 < tiers:
                na, nb, nc, ne = tier_rect(k + 1)
                for x in range(a + 1, c):
                    for z in range(b + 1, e):
                        if not (na <= x <= nc and nb <= z <= ne):
                            edge = (door == "north" and z == b + 1) or (door == "south" and z == e - 1) or \
                                   (door == "west" and x == a + 1) or (door == "east" and x == c - 1)
                            if edge:
                                self.put(x, yt + 1, z, m["moss"])
                                self.put(x, yt + 2, z, planters[int(rng.integers(0, 3))], built=False)
        top = G + 4 * tiers
        a, b, c, e = tier_rect(tiers - 1)
        for x in range(a + 2, c - 1):  # a roof garden
            for z in range(b + 2, e - 1):
                if rng.random() < 0.45:
                    self.put(x, top + 1, z, m["moss"])
                    if rng.random() < 0.5:
                        self.put(x, top + 2, z, planters[int(rng.integers(0, 3))], built=False)
        for x, z in ((a + 1, b + 1), (a + 1, e - 1), (c - 1, b + 1), (c - 1, e - 1)):
            self.box(x, top + 1, z, x, top + 2, z, m["rod"])
        # the entrance: a two-wide door under the first roof plate, sconces either side
        mx, mz = (x0 + x1) // 2, (z0 + z1) // 2
        px = x1 if ddx > 0 else x0 if ddx < 0 else mx
        pz = z1 if ddz > 0 else z0 if ddz < 0 else mz
        tx, tz = (1, 0) if ddz else (0, 1)
        for o in (0, 1):
            self.box(px + tx * o, G, pz + tz * o, px + tx * o, G + 2, pz + tz * o, AIR, built=False)
        for o in (-1, 2):
            self.put(px + ddx + tx * o, G + 2, pz + ddz + tz * o, s("end_rod", facing=door))
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, integrity, top + 2)
        self.fine[R + x0 - 1:R + x1 + 2, R + z0 - 1:R + z1 + 2] = 0.15
        cells = [(x, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
        return dict(door=door, px=px, pz=pz, inside=cells, top=G + 4, floors=1, cx=mx, cz=mz)

    def building(self, kind, x0, z0, x1, z1, door, integrity):
        """Build an Ascendancy building on a lot and make it a restoration site with a trade."""
        w, d = x1 - x0 + 1, z1 - z0 + 1
        if kind == "tower":
            rad = min(w, d) / 2 - 0.5
            info = self.hab_tower((x0 + x1) // 2, (z0 + z1) // 2, rad, int(self.rng.integers(4, 9)), door, integrity)
        else:
            deep = d if door in ("north", "south") else w
            info = self.terrace(x0, z0, x1, z1, door, 3 if deep >= 10 else 2 if deep >= 7 else 1, integrity)
        if not self.trade_deck:
            self.trade_deck = [TRADE_NAMES[int(i)] for i in self.rng.permutation(len(TRADE_NAMES))]
        trade = self.trade_deck.pop()
        ddx, ddz = DIRS[door]
        if self.rng.random() < 0.6:
            self.put(info["px"], G + 4, info["pz"], self.m["qz"], keep=True)
            self.sign(info["px"] + ddx, G + 4, info["pz"] + ddz, door, trade.split("|"))
        info["trade"] = trade
        info["kind"] = kind
        info["mask"] = self.rect(x0 - 2, z0 - 2, x1 + 2, z1 + 2)
        label = trade.replace("|", " ").title()
        n = sum(1 for k in self.sites if k.startswith("house_"))
        self.site(f"house_{n}", label if label.startswith("House") else f"The {label}", 2,
                  info["mask"], self.props_building(info), layer=4,
                  summon=[(info["cx"], G, info["cz"], TRADES[trade][0] or "none")])
        self.sites[f"house_{n}"]["kind"] = kind

    def props_building(self, h):
        def props(new, age):
            """A home again: a door, a bed, the trade's workstation, a chest, a ladder through the floors,
            and a lantern under every ceiling so the windows glow at night."""
            s = self.g.s
            door, px, pz = h["door"], h["px"], h["pz"]
            ddx, ddz = DIRS[door]
            back = OPPOSITE[door]
            for half, y in (("lower", G), ("upper", G + 1)):
                self.wput(new, px, y, pz, s("spruce_door", facing=back, half=half, hinge="left", open=False,
                                            powered=False))
            inside = set(h["inside"])
            near_wall = [c for c in inside if any((c[0] + ox, c[1] + oz) not in inside for ox, oz in DIRS.values())]
            near_wall.sort(key=lambda c: (c[0] - px) * ddx + (c[1] - pz) * ddz)  # farthest from the door first
            near_wall = [c for c in near_wall if abs(c[0] - px) + abs(c[1] - pz) > 1]
            used = set()
            for hx, hz in near_wall:
                fx, fz = hx - DIRS[back][0], hz - DIRS[back][1]
                if (fx, fz) in inside and (fx, fz) not in near_wall[:1]:
                    self.wput(new, hx, G, hz, s("red_bed", facing=back, part="head", occupied=False))
                    self.wput(new, fx, G, fz, s("red_bed", facing=back, part="foot", occupied=False))
                    used |= {(hx, hz), (fx, fz)}
                    break
            rest = [c for c in near_wall if c not in used and all(abs(c[0] - u[0]) + abs(c[1] - u[1]) > 1 for u in used)]
            block = TRADES[h["trade"]][1]
            if block and rest:
                props = dict(JOB_PROPS.get(block, {}))
                if block in FACED:
                    props["facing"] = door
                if block == "barrel":
                    props["facing"] = "up"
                self.wput(new, rest[0][0], G, rest[0][1], s(block, **props))
                used.add(rest[0])
            rest = [c for c in rest if c not in used]
            if rest:
                self.wput(new, rest[0][0], G, rest[0][1], s("chest", facing=door, type="single", waterlogged=False))
                used.add(rest[0])
            # a ladder against the wall on the door side
            for lx, lz in sorted(near_wall, key=lambda c: -((c[0] - px) * ddx + (c[1] - pz) * ddz)):
                if (lx, lz) in used or abs(lx - px) + abs(lz - pz) <= 1:
                    continue
                for face, (ox, oz) in DIRS.items():
                    if (lx - ox, lz - oz) not in inside:
                        for y in range(G, h["top"] + 1):
                            self.wput(new, lx, y, lz, s("ladder", facing=face, waterlogged=False))
                        used.add((lx, lz))
                        break
                if (lx, lz) in used:
                    break
            cx, cz = h["cx"], h["cz"]
            for k in range(h["floors"]):
                y = G + 4 * k + 3
                if age == 1:
                    self.wput(new, cx, G + 4 * k + (1 if k else 0), cz, s("candle", candles=3, lit=True,
                                                                              waterlogged=False))
                elif self.wget(new, cx, y + 1, cz) > AIR and (cx, cz) not in used:
                    self.wput(new, cx, y, cz, s("lantern", hanging=True, waterlogged=False))
        return props

    # ---------- megastructures ----------
    def tube(self, a0, a1, c, y, axis):
        """A sky bridge: an iron-floored glass tube three wide with iron frames and a quartz roof,
        running along x (axis "x", c = z) or z (axis "z", c = x) from a0 to a1 at floor height y."""
        m = self.m
        lo, hi = min(a0, a1), max(a0, a1)
        for a in range(lo, hi + 1):
            frame = (a - lo) % 3 == 0
            for o in (-1, 0, 1):
                x, z = (a, c + o) if axis == "x" else (c + o, a)
                self.put(x, y, z, m["iron"])
                self.put(x, y + 4, z, self.slab("smooth_quartz", "top") if not frame else m["iron"])
                for yy in (y + 1, y + 2, y + 3):
                    self.put(x, yy, z, AIR, built=False)
            for o in (-2, 2):
                x, z = (a, c + o) if axis == "x" else (c + o, a)
                self.put(x, y, z, self.slab("smooth_quartz", "top"))
                for yy in (y + 1, y + 2, y + 3):
                    self.put(x, yy, z, m["iron"] if frame else m["glass_w"])
                self.put(x, y + 4, z, m["iron"])

    def arcology(self):
        """The Twin Arcology: two fourteen-storey habitation towers either side of the south-west lane,
        joined by three sky bridges."""
        a, b, z, rad, floors = (-56, -32), None, 44, 6.5, 14
        ia = self.hab_tower(-56, z, rad, floors, "east", 0.8)
        ib = self.hab_tower(-32, z, rad, floors, "west", 0.8)
        for k in (4, 8, 12):
            y = G + 4 * k
            self.tube(-56 + int(rad), -32 - int(rad), z, y, "x")
        self.claim(-66, 34, -22, 54, 0.8, G + 64)
        self.fine[R - 66:R - 21, R + 34:R + 55] = 0.15
        self.site("arcology", "The Twin Arcology", 4, self.rect(-66, 34, -22, 54), self.props_lit([ia, ib]),
                  layer=4, summon=[(-56, G, z, "none"), (-32, G, z, "none"), (-56, G + 17, z, "none"),
                                   (-32, G + 17, z, "none")])

    def archive(self):
        """The Archive: a rotunda ringed by a quartz peristyle under a great violet glass dome, an aether crystal
        at its heart and shelves of the Ascendancy's books around it. Restored, it teaches the runes."""
        m, s = self.m, self.g.s
        cx, cz = 28, 62
        lx, lz = self.dx - cx, self.dz - cz
        d = np.hypot(lx, lz)
        ang = np.degrees(np.arctan2(lz, lx))
        self.g.column_mask(d <= 12.5, G, G, m["ds_pol"])
        self.g.column_mask((d > 12.5) & (d <= 13.5), G, G, self.slab("polished_deepslate"))
        self.g.column_mask(d <= 7.5, G, G, m["qz_b"])
        for a in range(0, 360, 24):
            px, pz = cx + int(round(11 * math.cos(math.radians(a)))), cz + int(round(11 * math.sin(math.radians(a))))
            self.box(px, G + 1, pz, px, G + 8, pz, m["qz_p"])
            self.put(px, G + 9, pz, m["qz_ch"])
        self.g.column_mask((d > 10.3) & (d <= 11.8), G + 10, G + 10, m["iron"])
        self.g.column_mask((d > 10.3) & (d <= 12.2), G + 11, G + 11, self.slab("smooth_quartz"))
        drum = (d > 7.5) & (d <= 8.5)
        slit = drum & (np.abs(((ang + 15) % 30) - 15) < 4)
        self.g.column_mask(drum, G + 1, G + 12, m["qz_b"])
        self.g.column_mask(slit, G + 2, G + 8, m["glass_v"])
        self.g.column_mask(drum & (np.abs(lx) <= 1) & (lz < 0), G + 1, G + 4, AIR, built=False)
        for t in range(0, 10):
            rr = math.sqrt(max(8.5 ** 2 - (t + 0.4) ** 2, 0))
            layer = (d <= rr + 0.4) & (d > rr - 1.2)
            if not layer.any():
                break
            rib = layer & (np.abs(((ang + 22.5) % 45) - 22.5) < math.degrees(0.6 / max(rr, 1)))
            self.g.column_mask(layer & ~rib, G + 13 + t, G + 13 + t, m["glass_vb"])
            self.g.column_mask(rib, G + 13 + t, G + 13 + t, m["iron"])
        self.box(cx, G + 1, cz, cx, G + 2, cz, m["qz_ch"])
        self.box(cx, G + 3, cz, cx, G + 4, cz, m["aether"])
        self.put(cx, G + 5, cz, s("amethyst_cluster", facing="up", waterlogged=False))
        shelves = (d > 5.5) & (d <= 6.5) & (np.abs(((ang + 15) % 30) - 15) > 6)
        self.g.column_mask(shelves, G + 1, G + 3, s("bookshelf"))
        self.claim(cx - 14, cz - 14, cx + 14, cz + 14, 0.7, G + 22)
        self.fine[R + cx - 14:R + cx + 15, R + cz - 14:R + cz + 15] = 0.15
        self.sign(cx, G + 5, cz - 9, "north", ["THE ARCHIVE", "", "WHAT WE KNEW"])
        info = dict(cx=cx, cz=cz, floors=3, top=G + 12)
        self.site("archive", "The Archive", 4, self.rect(cx - 14, cz - 14, cx + 14, cz + 14), self.props_lit([info]),
                  summon=[(cx + 3, G + 1, cz, "librarian"), (cx - 3, G + 1, cz, "librarian")])

    def props_lit(self, infos):
        def props(new, age):
            """Lanterns under every ceiling."""
            for h in infos:
                for k in range(h["floors"]):
                    y = G + 4 * k + 3
                    if self.wget(new, h["cx"], y + 1, h["cz"]) > AIR:
                        self.wput(new, h["cx"], y, h["cz"], self.g.s("lantern", hanging=True, waterlogged=False))
        return props

    def sky_bridges(self):
        """Glass sky bridges between towers that line up along a street, about two thirds of the way up."""
        n = 0
        for i, a in enumerate(self.towers):
            for b in self.towers[i + 1:]:
                for axis, along, across in (("x", 0, 1), ("z", 1, 0)):
                    pa, pb = (a["cx"], a["cz"]), (b["cx"], b["cz"])
                    if abs(pa[across] - pb[across]) > 2 or not 10 <= abs(pa[along] - pb[along]) <= 34:
                        continue
                    k = max(1, min(a["floors"], b["floors"]) * 2 // 3)
                    y = G + 4 * k
                    lo, hi = sorted((pa[along], pb[along]))
                    lo, hi = lo + int(a["rad"]), hi - int(b["rad"])
                    c = (pa[across] + pb[across]) // 2
                    if hi - lo < 4:
                        continue
                    span = self.g.a[R + lo + 3:R + hi - 2, y:y + 5, R + c - 2:R + c + 3] if axis == "x" else \
                        self.g.a[R + c - 2:R + c + 3, y:y + 5, R + lo + 3:R + hi - 2]
                    if (span > AIR).any():
                        self.notes.append(f"bridge {pa}-{pb} blocked")
                        continue
                    self.tube(lo, hi, c, y, axis)
                    n += 1
        self.notes.append(f"{n} sky bridges")

    # ---------- streets of the old city ----------
    def conduits(self):
        """Aether conduits: dashed crystal lines down the middle of every avenue and around the ring road,
        converging on the Hearth. Dark now; they can be made to glow again."""
        m, dx, dz, r, rng = self.m, self.dx, self.dz, self.r, self.rng
        dash = (np.floor(r).astype(int) % 3) != 0
        line = (((dx == 0) | (dz == 0)) & (r >= 7) & (r <= 82) & dash) | ((np.abs(r - 40.25) < 0.5) & dash)
        self.conduit_line = line
        g = self.g.a[:, G - 1, :]
        g[line] = m["aether"]
        grid = dilate(self.roads, 1) | (self.r <= 19.5) | line
        self.site("aether_grid", "The Aether Grid", 5, grid, self.props_grid)

    def props_grid(self, new, age):
        """The streets made whole: paving relaid where the weeds took it, the conduits mended, and the weeds
        on the streets pulled up. (In Age V, restore() also lights every conduit.)"""
        mask = self.sites["aether_grid"]["mask"] & (self.roads | self.conduit_line)
        ground = new[:, G - 1, :]
        ground[mask] = self.pre_a[:, G - 1, :][mask]
        weeds = self.g.ids_where(lambda k: any(p in k for p in ("short_grass", "tall_grass", "fern", "poppy",
                                                                 "dandelion", "daisy", "cornflower", "bluet",
                                                                 "moss_carpet")))
        for y in (G, G + 1):
            layer = new[:, y, :]
            layer[mask & np.isin(layer, weeds)] = AIR

    def pylons(self):
        """Light pylons along the avenues: dark posts with a glowing rod."""
        for a in range(22, 82, 8):
            for side in (-4, 4):
                for x, z in ((side, a), (side, -a), (a, side), (-a, side)):
                    if self.occupied[R + x, R + z]:
                        continue
                    self.box(x, G, z, x, G + 2, z, self.wall("polished_deepslate"))
                    self.put(x, G + 3, z, self.m["iron"])
                    self.put(x, G + 4, z, self.m["rod"])
                    self.integrity[R + x, R + z] = 0.75
                    self.htop[R + x, R + z] = G + 4

    def monorail(self):
        """An elevated monorail on quartz pillars over the ring road."""
        m = self.m
        beam = np.abs(self.r - 40.25) < 0.55
        self.g.column_mask(beam, G + 9, G + 9, m["iron"])
        self.integrity[beam] = 0.9
        self.htop[beam] = G + 40  # decay it as the low part of something tall: whole spans survive or fall
        self.fine[beam] = 0.1
        self.site("monorail", "The Monorail", 3, np.abs(self.r - 40.25) <= 1.6)
        for a in range(0, 360, 9):
            if any(abs(((a - g + 180) % 360) - 180) < 8 for g in (0, 90, 180, 270, 45, 135, 225, 315)):
                continue
            x, z = int(round(40.25 * math.cos(math.radians(a)))), int(round(40.25 * math.sin(math.radians(a))))
            self.box(x, G, z, x, G + 8, z, m["qz_p"])
            self.put(x, G + 8, z, m["qz_ch"])
            self.integrity[R + x, R + z] = 0.95

    def props_house(self, h):
        def props(new, age):
            """A home again: a door, glass, a light, a smoking chimney, a ladder to the roof, a bed,
            and the workstation of the trade written over the door."""
            s = self.g.s
            x0, z0, x1, z1, door, px, pz = (h[k] for k in ("x0", "z0", "x1", "z1", "door", "px", "pz"))
            xi0, xi1, zi0, zi1 = x0 + 1, x1 - 1, z0 + 1, z1 - 1
            ddx, ddz = DIRS[door]
            back = OPPOSITE[door]
            bdx, bdz = DIRS[back]
            for half, y in (("lower", G), ("upper", G + 1)):
                self.wput(new, px, y, pz, s("spruce_door", facing=back, half=half, hinge="left", open=False,
                                            powered=False))
            tx, tz = (1, 0) if ddz else (0, 1)
            self.wput(new, px + ddx + tx, G + 2, pz + ddz + tz, s("wall_torch", facing=door))
            if age >= 2:
                for x, y, z, run in h["windows"]:
                    if self.wget(new, x, y, z) == AIR:
                        self.wput(new, x, y, z, s("glass_pane", waterlogged=False, north=run == "z", south=run == "z",
                                                  east=run == "x", west=run == "x"))
            if door in ("north", "south"):
                bz = zi1 if back == "south" else zi0
                head, foot, job, chest = (xi0, bz), (xi0, bz - bdz), (xi1, bz), ((xi0 + xi1) // 2, bz)
                ladder, lface = (xi1, zi0 if door == "north" else zi1), "west"
            else:
                bx = xi1 if back == "east" else xi0
                head, foot, job, chest = (bx, zi0), (bx - bdx, zi0), (bx, zi1), (bx, (zi0 + zi1) // 2)
                ladder, lface = (xi0 if door == "west" else xi1, zi1), "north"
            ytop = h["top"] if h["roof"] == "flat" else h["top"] - 1
            for y in range(G, ytop + 1):
                self.wput(new, ladder[0], y, ladder[1], s("ladder", facing=lface, waterlogged=False))
            self.wput(new, head[0], G, head[1], s("red_bed", facing=back, part="head", occupied=False))
            self.wput(new, foot[0], G, foot[1], s("red_bed", facing=back, part="foot", occupied=False))
            self.wput(new, chest[0], G, chest[1], s("chest", facing=door, type="single", waterlogged=False))
            block = TRADES[h["trade"]][1]
            if block:
                props = dict(JOB_PROPS.get(block, {}))
                if block in FACED:
                    props["facing"] = door
                if block == "barrel":
                    props["facing"] = "up"
                self.wput(new, job[0], G, job[1], s(block, **props))
            # a light on every floor, so the windows glow at night
            mx, mz = (xi0 + xi1) // 2, (zi0 + zi1) // 2
            for k in range((h["top"] - G) // 4):
                y = G + 4 * k + 3
                if age == 1:
                    self.wput(new, mx, G + 4 * k, mz, s("candle", candles=3, lit=True, waterlogged=False))
                elif self.wget(new, mx, y + 1, mz) > AIR:
                    self.wput(new, mx, y, mz, s("lantern", hanging=True, waterlogged=False))
                elif k == 0:
                    self.wput(new, mx, G, mz, s("lantern", hanging=False, waterlogged=False))
            if h["roof"] == "flat":
                self.wput(new, head[0], h["top"] + 1, head[1], s("bricks"))
                self.wput(new, head[0], h["top"] + 2, head[1], s("bricks"))
                self.wput(new, head[0], h["top"] + 3, head[1], s("campfire", lit=True, facing="north",
                                                                 signal_fire=False, waterlogged=False))
        return props

    def props_gate(self, ang):
        def props(new, age):
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
        lane_mix = np.choose(rng.integers(0, 3, dx.shape), [m["ds_t"], m["ds_cob"], m["ds_pol"]])
        g = self.g.a[:, G - 1, :]
        g[lanes] = lane_mix[lanes]
        self.ground(ring, m["ds_t"])
        self.ground(ns | ew, m["ds_pol"])
        curb = (ns & (np.abs(dx) == 3)) | (ew & (np.abs(dz) == 3))
        self.ground(curb & ~(ns & ew), m["qz"])

    def wear_streets(self):
        """Four centuries of weeds on the streets, and the conduits cracked."""
        m, dx, rng = self.m, self.dx, self.rng
        n = noise2(dx.shape, 9, rng)
        speck = rng.random(dx.shape)
        worn = self.roads & (n > 0.62) & ~self.g.keep[:, G - 1, :]
        self.ground(worn & (speck < 0.7), m["grass"])
        self.ground(worn & (speck >= 0.7), m["coarse"])
        self.ground(self.roads & (n > 0.55) & (n <= 0.62) & (speck < 0.5) & ~self.g.keep[:, G - 1, :], m["gravel"])
        self.ground(self.roads & (speck > 0.985) & ~self.g.keep[:, G - 1, :], m["moss"])
        g = self.g.a[:, G - 1, :]
        broken = self.conduit_line & (rng.random(dx.shape) < 0.25) & ~self.g.keep[:, G - 1, :]
        g[broken] = m["gravel"]

    # ---------- the plaza and the Hearth ----------
    def plaza(self):
        m, dx, dz, r, th = self.m, self.dx, self.dz, self.r, self.th
        pz = r <= 18.5
        rings = (r.astype(int) // 3) % 2 == 0
        spokes = (((th + 180) / 22.5).astype(int) % 2) == 0
        pave = np.where(rings, m["qz_b"], np.where(spokes, m["qz"], m["calcite"]))
        lines = (np.abs(r - 12.5) < 0.5) | (np.abs(r - 18) < 0.5)
        spoke = (r > 7) & ((np.abs(dx) <= 0.5) | (np.abs(dz) <= 0.5) | (np.abs(np.abs(dx) - np.abs(dz)) <= 0.5))
        pave = np.where(lines, m["ds_pol"], np.where(spoke, m["ds_t"], pave))
        g = self.g.a[:, G - 1, :]
        g[pz] = pave[pz]
        self.g.keep[:, G - 1, :] |= pz
        edge = (r > 18.5) & (r <= 19.5)
        gap = (np.abs(dx) <= 3) | (np.abs(dz) <= 3) | (np.abs(np.abs(dx) - np.abs(dz)) <= 2)
        self.g.a[:, G, :][edge & ~gap] = self.slab("smooth_quartz")
        self.g.built[:, G, :][edge & ~gap] = True
        self.g.keep[:, G, :][edge & ~gap] = True
        self.ground(edge, m["ds_pol"])
        self.claim(-22, -22, 22, 22, 1.0)

        # the Hearth: a sunken fire ring with an unlit brazier the Remnant rekindle
        pit = r <= 5.5
        rim = (r > 5.5) & (r <= 7)
        self.g.column_mask(pit, G - 1, G - 1, AIR, built=False)
        self.g.column_mask(pit, G - 2, G - 2, m["ds_pol"], built=False)
        self.ground(rim, m["qz_ch"])
        self.g.keep[:, G - 2:G + 1, :] |= (r <= 7)[:, None, :]
        self.box(-1, G - 2, -1, 1, G - 1, 1, m["ds_ch"], keep=True)
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
                    self.put(x, G, z, self.stairs("smooth_quartz", toward(x, z)), keep=True)
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.box(8 * sx, G, 8 * sz, 8 * sx, G + 2, 8 * sz, self.wall("polished_deepslate"), keep=True)
                self.put(8 * sx, G + 3, 8 * sz, m["bulb"], keep=True)

    # ---------- buildings ----------
    def house(self, x0, z0, x1, z1, floors, door, integrity, roof="flat", wall=None, keep=False):
        """A plain box house. Only the Elder's house and the Storehouse use it now: Ascendancy shells in quartz
        and iron that the Remnant patched with timber."""
        m, s = self.m, self.g.s
        wall = wall or m["qz_b"]
        h = floors * 4
        self.box(x0, G, z0, x1, G + h, z1, wall, keep=keep)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G + h - 1, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G - 1, z0 + 1, x1 - 1, G - 1, z1 - 1, m["lime_pol"], built=False, keep=keep)
        # base course, floor bands, corners
        for y, st in ((G, m["ds_pol"]),) + tuple((G + 4 * k, m["iron"]) for k in range(1, floors + 1)):
            self.box(x0, y, z0, x1, y, z0, st, keep=keep)
            self.box(x0, y, z1, x1, y, z1, st, keep=keep)
            self.box(x0, y, z0, x0, y, z1, st, keep=keep)
            self.box(x1, y, z0, x1, y, z1, st, keep=keep)
        for cx, cz in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
            self.box(cx, G + 1, cz, cx, G + h - 1, cz, m["qz_p"], keep=keep)
        for k in range(1, floors):
            self.box(x0 + 1, G + 4 * k, z0 + 1, x1 - 1, G + 4 * k, z1 - 1, m["lime_cut"], keep=keep)
        # windows on every floor, a door facing the street
        win = m["grate"] if self.rng.random() < 0.4 else AIR
        windows = []
        for k in range(floors):
            yb = G + 4 * k + 1
            for x in range(x0 + 2, x1 - 1, 3):
                for z in (z0, z1):
                    self.box(x, yb, z, x, yb + 1, z, win, built=win != AIR)
                    windows += [(x, yb, z, "x"), (x, yb + 1, z, "x")]
            for z in range(z0 + 2, z1 - 1, 3):
                for x in (x0, x1):
                    self.box(x, yb, z, x, yb + 1, z, win, built=win != AIR)
                    windows += [(x, yb, z, "z"), (x, yb + 1, z, "z")]
        mx, mz = (x0 + x1) // 2, (z0 + z1) // 2
        ddx, ddz = DIRS[door]
        px = x1 if ddx > 0 else x0 if ddx < 0 else mx
        pz = z1 if ddz > 0 else z0 if ddz < 0 else mz
        self.box(px, G, pz, px, G + 2, pz, AIR, built=False)
        self.put(px + ddx, G - 1, pz + ddz, m["lime_pol"], built=False)
        trade = None
        if not keep:
            self.furnish(x0, z0, x1, z1, px, pz)
            if not self.trade_deck:  # deal trades out without repeats until the deck runs out
                self.trade_deck = [TRADE_NAMES[int(i)] for i in self.rng.permutation(len(TRADE_NAMES))]
            trade = self.trade_deck.pop()
            if self.rng.random() < 0.6:
                self.put(px, G + 3, pz, wall, keep=True)  # the lintel holding the name survives
                self.sign(px + ddx, G + 3, pz + ddz, door, trade.split("|"))
        # roof
        top = G + h
        if roof == "flat":
            self.box(x0 + 1, top, z0 + 1, x1 - 1, top, z1 - 1, m["lime_cut"], keep=keep)
            for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
                self.box(ax, top + 1, az, bx, top + 1, bz, self.slab("smooth_quartz"), keep=keep)
        elif roof == "copper":
            self.hip_roof(x0 - 1, z0 - 1, x1 + 1, z1 + 1, top + 1, "oxidized_cut_copper", m["cu"], keep)
            top += min(x1 - x0, z1 - z0) // 2 + 1
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, integrity, top)
        if trade:
            info = dict(x0=x0, z0=z0, x1=x1, z1=z1, door=door, px=px, pz=pz, trade=trade, windows=windows,
                        top=G + h, roof=roof)
            label = trade.replace("|", " ").title()
            n = sum(1 for k in self.sites if k.startswith("house_"))
            prof = TRADES[trade][0] or "none"
            self.site(f"house_{n}", label if label.startswith("House") else f"The {label}", 2,
                      self.rect(x0 - 1, z0 - 1, x1 + 1, z1 + 1), self.props_house(info), layer=4,
                      summon=[((x0 + x1) // 2, G, (z0 + z1) // 2, prof)])
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
                self.put(x, G, z, self.slab("smooth_quartz", "top"), built=False)
            else:
                self.put(x, G, z, s("cauldron"), built=False)

    def loot(self, x, y, z, kind, st, table="remnant:ruins/house"):
        self.put(x, y, z, st, built=False)
        self.g.block_nbt[(R + x, y, R + z)] = {"id": f"minecraft:{kind}", "LootTable": table}

    def sign(self, x, y, z, facing, lines, wood="birch", font="runelic:runelic", standing=False):
        """An inscription. The Ascendancy wrote in runes (the Runelic font); the Remnant write plainly (font=None).
        Placed after decay, where its wall survived."""
        self.signs.append((x, y, z, facing, lines, wood, font, standing))

    def place_signs(self):
        full = self.full_cubes()
        placed = 0
        for x, y, z, facing, lines, wood, font, standing in self.signs:
            ox, oz = DIRS[facing]
            support = self.get(x, y - 1, z) if standing else self.get(x - ox, y, z - oz)
            if self.get(x, y, z) != AIR or support >= len(full) or not full[support]:
                continue
            if standing:
                rot = {"south": 0, "west": 4, "north": 8, "east": 12}[facing]
                st = self.g.s(f"{wood}_sign", rotation=rot, waterlogged=False)
            else:
                st = self.g.s(f"{wood}_wall_sign", facing=facing, waterlogged=False)
            self.put(x, y, z, st, built=False, keep=True)
            text = [json.dumps({"text": t, "font": font} if font else {"text": t})
                    for t in (list(lines) + [""] * 4)[:4]]
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
        self.gable_roof(x0, z0, x1, z1, G + 9)
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

    def gable_roof(self, x0, z0, x1, z1, top):
        """A Remnant timber roof, gabled along x, over walls x0..x1, z0..z1."""
        for i in range(0, (z1 - z0) // 2 + 2):
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
                    self.box(x, top + i, za + 1, x, top + i, zb - 1, self.m["spruce"], keep=True)

    def storehouse(self):
        """The Remnant's storehouse by the plaza. Everything the city's projects need is carried here: each bay
        is a hopper chute feeding that project's Task Screen (FTB Quests, placed on the marked wall once the
        quests exist; a screen only takes items fed into it, so nothing can be handed in from afar)."""
        m, s = self.m, self.g.s
        x0, z0, x1, z1 = 21, -18, 33, -8
        self.house(x0, z0, x1, z1, 1, "south", 1.0, roof=None, keep=True)
        self.box(x0 + 1, G + 1, z0, x1 - 1, G + 2, z0, m["qz_b"], keep=True)  # no windows behind the screens
        self.box(x0 + 3, G, z1, x1 - 3, G + 2, z1, AIR, built=False)  # wide loading front
        self.gable_roof(x0, z0, x1, z1, G + 5)
        for i, bx in enumerate((x0 + 1, x0 + 5, x0 + 9)):
            self.box(bx, G, z0 + 1, bx + 2, G + 2, z0 + 1, AIR, built=False)  # room for a 3x3 screen
            self.put(bx + 1, G, z0 + 2, s("hopper", facing="north", enabled=True), built=False, keep=True)
            self.sign(bx + 1, G + 3, z0 + 1, "south", ["", f"BAY {i + 1}"], font=None)
        for x, z, st in ((x0 + 1, z1 - 1, s("barrel", facing="up", open=False)), (x0 + 2, z1 - 1, s("hay_block", axis="y")),
                         (x1 - 1, z1 - 1, s("oak_log", axis="z")), (x1 - 1, z1 - 2, s("oak_log", axis="z")),
                         (x1 - 2, z1 - 1, s("barrel", facing="up", open=False)), (x0 + 1, z0 + 5, s("barrel", facing="up", open=False))):
            self.put(x, G, z, st, built=False, keep=True)
        self.put(x1 - 1, G + 1, z1 - 1, s("oak_log", axis="z"), built=False, keep=True)
        for x in (x0 + 3, x1 - 3):
            self.put(x, G + 3, z1 + 1, s("wall_torch", facing="south"), built=False, keep=True)
        self.sign((x0 + x1) // 2, G + 3, z1 + 1, "south", ["STOREHOUSE", "", "Deliveries for", "the city"], font=None)
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
        """The Convergence Spire as it stood: an octagonal quartz shaft ribbed in dark iron, violet glass slits,
        a ledge every twelve blocks, tapering into an open lantern of quartz posts around a great aether crystal,
        and a needle above. The ring stands around it whole; the catastrophe breaks both later."""
        m, s, rng = self.m, self.g.s, self.rng
        cx, cz = 0, -58
        self.spire_c = (cx, cz)
        lx, lz = self.dx - cx, self.dz - cz
        lr = np.maximum(np.maximum(np.abs(lx), np.abs(lz)), (np.abs(lx) + np.abs(lz)) / 1.4142)  # octagon
        precinct = (np.hypot(lx, lz) <= 24) & (self.r <= 80)
        ring_pat = (np.hypot(lx, lz).astype(int) % 4 == 0)
        spoke = (np.abs(lx) <= 0.5) | (np.abs(lz) <= 0.5) | (np.abs(np.abs(lx) - np.abs(lz)) <= 0.5)
        g = self.g.a[:, G - 1, :]
        g[precinct] = np.where(spoke, m["aether"], np.where(ring_pat, m["ds_pol"], m["qz_b"]))[precinct]
        for y, rad, st in ((G, 11.5, m["ds_pol"]), (G + 1, 10.8, m["qz"]), (G + 2, 10.2, m["ds_pol"])):
            self.g.column_mask(lr <= rad, y, y, st)
        corner = (np.abs(np.abs(lx) - np.abs(lz)) <= 0.5)
        face = (lx == 0) | (lz == 0) | (np.abs(lx) == np.abs(lz))
        glass = s("purple_stained_glass_pane", north=False, east=False, south=False, west=False, waterlogged=False)
        for y in range(G + 3, G + 71):
            t = max(0, y - (G + 58)) * 0.22
            rad = 8 - t
            shaft = (lr <= rad) & (lr > rad - 2.4)
            k = (y - G) % 12
            self.g.column_mask(shaft, y, y, m["iron"] if k == 0 else m["qz"])
            self.g.column_mask(shaft & corner & (lr > rad - 1) & (k != 0), y, y, m["iron"])
            if k == 0:
                self.g.column_mask((lr <= rad - 2.4) & (lr > 2.5), y, y, m["qz_b"])
                self.g.column_mask((lr > rad) & (lr <= rad + 1.2), y, y, self.slab("smooth_quartz", "top"))
            if k in (4, 5, 6, 7, 8):
                self.g.column_mask(shaft & face & ~corner, y, y, glass)
        # the lantern crown and the needle
        top = G + 71
        posts = [(int(round(4.6 * math.cos(math.radians(a)))), int(round(4.6 * math.sin(math.radians(a)))))
                 for a in range(0, 360, 45)]
        self.g.column_mask(lr <= 5.4, top, top, m["iron"])
        for px, pz in posts:
            self.box(cx + px, top + 1, cz + pz, cx + px, top + 6, cz + pz, m["qz_p"])
        self.g.column_mask(lr <= 5.4, top + 7, top + 7, m["iron"])
        self.g.column_mask(lr <= 3.6, top + 8, top + 8, m["qz"])
        self.box(cx - 1, top + 1, cz - 1, cx + 1, top + 5, cz + 1, m["aether"])
        for o in ((2, 0, "east"), (-2, 0, "west"), (0, 2, "south"), (0, -2, "north")):
            for y in (top + 2, top + 4):
                self.put(cx + o[0], y, cz + o[1], s("amethyst_cluster", facing=o[2], waterlogged=False))
        self.box(cx, top + 9, cz, cx, top + 11, cz, m["qz_p"])
        self.box(cx, top + 12, cz, cx, top + 13, cz, m["iron"])
        self.box(cx, top + 14, cz, cx, top + 15, cz, m["rod"])
        # the aether core: an amethyst column caged in iron up the middle
        for y in range(G, top):
            for x in (-1, 0, 1):
                for z in (-1, 0, 1):
                    st = m["aether"] if (x == 0 and z == 0) else m["iron"] if y % 6 in (0, 1) else m["bars"]
                    if y < G + 3 or (x, z) == (0, 0) or y % 3 == 0:
                        self.put(cx + x, y, cz + z, st)
        # buttresses on the diagonals: quartz fins capped in iron
        for sx in (-1, 1):
            for sz in (-1, 1):
                for k in range(0, 9):
                    hgt = G + 30 - k * 3
                    bx, bz = cx + sx * (6 + k), cz + sz * (6 + k)
                    self.box(bx, G, bz, bx, hgt, bz, m["qz"])
                    self.put(bx, hgt + 1, bz, self.slab("polished_deepslate"))
        door = (np.abs(lx) <= 1) & (lz >= 6) & (lz <= 11)
        self.g.column_mask(door, G, G + 4, AIR, built=False)
        self.sign(cx, G + 5, cz + 9, "south", ["CONVERGENCE", "SPIRE", "", "NO ENTRY"])
        self.ring_whole(cx, cz)
        self.claim(-26, -84, 44, -32, 0.8, G + 86)
        self.fine[R - 26:R + 45, R - 84:R - 31] = 0.12
        self.site("spire", "The Convergence Spire", 5, self.rect(-26, -84, 44, -32), self.props_spire)

    def props_spire(self, new, age):
        """Restored, the Spire's crystal lantern burns."""
        if age >= 5:
            cx, cz = self.spire_c
            for y in range(G + 72, G + 77):
                for x in (-1, 0, 1):
                    for z in (-1, 0, 1):
                        self.wput(new, cx + x, y, cz + z, self.m["aether_lit"])

    def ring_points(self, theta0, theta1, radius, step=0.004):
        th = np.arange(math.radians(theta0), math.radians(theta1), step)
        return th, radius * np.cos(th), radius * np.sin(th)

    RING = (56, 21.0)  # centre height above G, radius

    def ring_cells(self, cx, cz, t0, t1):
        """Every cell of the Convergence ring between two angles: copper, aether crystal on the inner face,
        chiseled nodes every fifteen degrees."""
        m = self.m
        cyo, rad = self.RING
        th, u, v = self.ring_points(t0, t1, rad)
        cells = {}
        for t, a, b in zip(th, u, v):
            for dr in (-1.0, 0.0, 1.0):
                x = int(round(cx + a * (rad + dr) / rad))
                y = int(round(G + cyo + b * (rad + dr) / rad))
                for z in (cz - 1, cz, cz + 1):
                    st = m["aether"] if dr < 0 and z == cz else m["cu"]
                    if int(math.degrees(t)) % 15 == 0:
                        st = m["cu_ch"]
                    cells[(x, y, z)] = st
        return cells

    def ring_whole(self, cx, cz):
        for (x, y, z), st in self.ring_cells(cx, cz, 0, 360).items():
            self.put(x, y, z, st, keep=True)

    def ring_fallen(self, cx, cz):
        """The missing arc, broken in two and lying east of the spire. Debris: cleared when the Spire is restored."""
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
                                self.debris_put(int(x) + ox, int(y) + oy, int(z) + oz, st)
                if deg % 8 < 3:
                    self.debris_put(int(x), int(y) + 2, int(z), m["amethyst"])
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
                    self.debris_put(x, y, z, st)

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
        col = m["qz_p"]
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
                self.put(x, G + 6, z, m["qz_ch"])
            for (ax, az, bx, bz) in ((x0 + inset, z0 + inset, x1 - inset, z0 + inset),
                                     (x0 + inset, z1 - inset, x1 - inset, z1 - inset),
                                     (x0 + inset, z0 + inset, x0 + inset, z1 - inset),
                                     (x1 - inset, z0 + inset, x1 - inset, z1 - inset)):
                self.box(ax, G + 7, az, bx, G + 7, bz, m["iron"])
        for (ax, az, bx, bz) in ((x0, z0, x1, z0 + 3), (x0, z1 - 3, x1, z1), (x0, z0, x0 + 3, z1), (x1 - 3, z0, x1, z1)):
            self.box(ax, G + 8, az, bx, G + 8, bz, m["glass_w"])
        # fountain on the crossing
        fx, fz = 59, 0
        for x in range(fx - 4, fx + 5):
            for z in range(fz - 4, fz + 5):
                d = math.hypot(x - fx, z - fz)
                if d <= 3.2:
                    self.put(x, G - 2, z, m["ds_pol"], built=False)
                    self.put(x, G - 1, z, m["water"] if d > 1 else m["ds_ch"], built=False)
                elif d <= 4.4:
                    self.put(x, G - 1, z, m["ds_pol"], built=False)
                    self.put(x, G, z, m["qz"], keep=True)
        self.box(fx, G, fz, fx, G + 3, fz, m["qz_p"], keep=True)
        self.put(fx, G + 4, fz, m["aether"], keep=True)
        for o in ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")):
            self.put(fx + o[0], G + 4, fz + o[1], self.g.s("amethyst_cluster", facing=o[2], waterlogged=False), keep=True)
        self.sign(fx + 1, G + 1, fz, "east", ["MARKET OF", "SEVEN ROADS"])
        self.sign(fx - 1, G + 1, fz, "west", ["MARKET OF", "SEVEN ROADS"])
        self.put(fx, G + 5, fz, self.g.s("amethyst_cluster", facing="up", waterlogged=False), keep=True)
        # old stalls: tuff posts, a limestone counter and a stone awning
        for sx in (49, 55, 63, 69):
            for sz in (-9, 7):
                for px, pz in ((sx, sz), (sx + 2, sz), (sx, sz + 2), (sx + 2, sz + 2)):
                    self.box(px, G, pz, px, G + 1, pz, self.wall("polished_deepslate"))
                self.box(sx, G + 2, sz, sx + 2, G + 2, sz + 2, self.slab("smooth_quartz"))
                self.box(sx, G, sz + (2 if sz < 0 else 0), sx + 2, G, sz + (2 if sz < 0 else 0),
                         self.slab("smooth_quartz", "top"))
                for _ in range(2):
                    px, pz = sx + int(rng.integers(-1, 4)), sz + int(rng.integers(-1, 4))
                    if self.get(px, G, pz) == AIR:
                        self.put(px, G, pz, s("decorated_pot", facing="north", cracked=bool(rng.random() < .5),
                                              waterlogged=False) if rng.random() < .6 else
                                 s("barrel", facing="up", open=False))
        self.claim(x0 - 2, z0 - 2, x1 + 2, z1 + 2, 0.55, G + 8)
        self.site("market", "The Market", 2, self.rect(x0 - 2, z0 - 2, x1 + 2, z1 + 2), self.props_market)

    # ---------- the Grave Warden's mausoleum, crypt and graveyard ----------
    def crypt(self):
        m, s, rng = self.m, self.g.s, self.rng
        x0, z0, x1, z1 = -66, -24, -52, -12
        self.box(x0, G, z0, x1, G + 7, z1, m["ds_b"], keep=True)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G + 6, z1 - 1, AIR, built=False)
        self.box(x0, G, z0, x1, G, z1, m["ds_pol"], keep=True)
        self.box(x0 + 1, G, z0 + 1, x1 - 1, G, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G - 1, z0 + 1, x1 - 1, G - 1, z1 - 1, m["ds_t"], built=False)
        self.box(x0, G + 4, z0, x1, G + 4, z1, m["qz"], keep=True)
        for x in range(x0 + 2, x1 - 1, 3):
            for z in (z0, z1):
                if not -61 <= x <= -57:
                    self.box(x, G + 1, z, x, G + 3, z, m["glass_v"], keep=True)
        for z in range(z0 + 2, z1 - 1, 3):
            for x in (x0, x1):
                self.box(x, G + 1, z, x, G + 3, z, m["glass_v"], keep=True)
        self.box(x0 + 1, G + 4, z0 + 1, x1 - 1, G + 4, z1 - 1, AIR, built=False)
        self.box(x0 + 1, G + 7, z0 + 1, x1 - 1, G + 7, z1 - 1, m["ds_t"], keep=True)
        self.hip_roof(x0 - 1, z0 - 1, x1 + 1, z1 + 1, G + 8, "deepslate_tile", m["ds_t"], keep=True)
        # portico and steps on the south side, facing the avenue
        for x in (-64, -61, -57, -54):
            self.box(x, G, -10, x, G + 5, -10, m["qz_p"], keep=True)
        self.put(-59, G + 7, -11, m["aether"], keep=True)
        self.put(-59, G + 8, -11, self.g.s("amethyst_cluster", facing="up", waterlogged=False), keep=True)
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
        self.box(cx - 3, G, cz - 3, cx + 3, G + 1, cz + 3, m["ds_pol"])
        self.box(cx - 2, G + 2, cz - 2, cx + 2, G + 2, cz + 2, m["qz"])
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
        arm = G + 6 + 5 * ((top - 4 - (G + 6)) // 5)  # level with a grate ring, so it hangs off the frame
        for x in range(cx + 3, cx + 12):  # the docking arm
            self.put(x, arm, cz, m["cu"], keep=True)
        for y in range(arm - 10, arm):
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
        self.g.column_mask(band, G, top - 1, m["ds_t"])
        self.g.column_mask(outer, G, G + 1, m["ds_pol"])
        self.g.column_mask(outer, G + 5, G + 5, m["aether"])  # the wall's own aether line, dark for now
        self.g.column_mask(outer, G + 4, G + 4, m["qz"])
        self.g.column_mask(outer, G + 6, G + 6, m["qz"])
        self.g.column_mask(band, top, top, m["ds_pol"])
        self.g.column_mask(outer, top, top, m["qz"])
        self.g.column_mask(outer, top + 1, top + 1, self.slab("smooth_quartz"))
        self.g.column_mask(inner, top + 1, top + 1, self.slab("polished_deepslate"))
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
            self.gate_ring(ang)
            near = band & (np.abs(((th - ang + 180) % 360) - 180) < 12)
            self.integrity[near] = 0.97
            gname = {0: "east", 90: "south", 180: "west", -90: "north"}[ang]
            window = (r >= 78.5) & (r <= 91) & (np.abs(((th - ang + 180) % 360) - 180) < 14)
            self.site(f"gate_{gname}", f"The {gname.title()} Gate", 2, window, self.props_gate(ang))
            self.sign(int(round(86 * math.cos(math.radians(ang)))), G + 8, int(round(86 * math.sin(math.radians(ang)))),
                      toward(math.cos(math.radians(ang)), math.sin(math.radians(ang))), ["", f"{gname.upper()} GATE"])
            # the Remnant's own name for the city, on a plain wooden sign just inside the gate
            ix, iz = int(round(78 * math.cos(math.radians(ang)))), int(round(78 * math.sin(math.radians(ang))))
            ox, oz = (0, 5) if axis == "x" else (5, 0)
            self.sign(ix + ox, G, iz + oz, toward(-math.cos(math.radians(ang)), -math.sin(math.radians(ang))),
                      ["", "REMAINDER"], wood="spruce", font=None, standing=True)
            for off in (-1, 1):
                a = math.radians(ang + off * 7)
                self.tower(84 * math.cos(a), 84 * math.sin(a), 4.5, G + 14, cap=False, integrity=0.93)
        for ang in (45, 135, -45, -135):
            a = math.radians(ang)
            self.tower(84 * math.cos(a), 84 * math.sin(a), 6, G + 16, cap=True, integrity=0.75)
        for q, (a0, a1) in {"ne": (-90, 0), "se": (0, 90), "sw": (90, 180), "nw": (-180, -90)}.items():
            ang = (th - a0) % 360
            sector = (r >= 78.5) & (r <= 92) & (ang > 14) & (ang < (a1 - a0) - 14)
            self.site(f"wall_{q}", f"The {q.upper()} Wall", 3, sector, None)

    def gate_ring(self, ang):
        """A Convergence ring set into the gatehouse: copper outside, aether crystal inside, standing in the
        wall's plane around the arch and rising above it."""
        m = self.m
        a = math.radians(ang)
        ux, uz = int(round(math.cos(a))), int(round(math.sin(a)))
        tx, tz = -uz, ux
        cy, rad = G + 6, 10.5
        for t in np.arange(0, 2 * math.pi, 0.01):
            for dr in (-0.5, 0.5):
                o = (rad + dr) * math.cos(t)
                y = int(round(cy + (rad + dr) * math.sin(t)))
                if y < G:
                    continue
                for k in (83, 84, 85):
                    x, z = int(round(tx * o + ux * k)), int(round(tz * o + uz * k))
                    st = m["aether"] if dr < 0 and k == 84 else m["cu"]
                    self.put(x, y, z, st, keep=True)
        # keep the ring's own arch open
        for t in np.arange(math.pi, 2 * math.pi, 0.02):
            pass

    def tower(self, fx, fz, rad, top, cap, integrity=0.7):
        """A wall tower in dark tile with quartz bands; corner towers carry a ward pylon: a quartz obelisk
        with an aether crystal and glowing rods."""
        m, s = self.m, self.g.s
        tx, tz = int(round(fx)), int(round(fz))
        tr = np.hypot(self.dx - tx, self.dz - tz)
        body = tr <= rad
        hollow = tr <= rad - 2
        self.g.column_mask(body, G, top, m["ds_t"])
        self.g.column_mask(body & (tr > rad - 1), G, G + 1, m["ds_pol"])
        self.g.column_mask(hollow, G + 1, top - 1, AIR, built=False)
        for y in range(G + 5, top, 5):
            self.g.column_mask(hollow, y, y, m["ds_pol"])
            self.g.column_mask(body & (tr > rad - 1), y, y, m["qz"])
        self.g.column_mask(body & (tr > rad - 1), top + 1, top + 1, self.slab("smooth_quartz"))
        if cap:
            self.g.column_mask(tr <= 2.2, top + 1, top + 1, m["qz"])
            self.g.column_mask(tr <= 1.6, top + 2, top + 3, m["qz"])
            self.box(tx, top + 4, tz, tx, top + 10, tz, m["qz_p"])
            for o in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                self.box(tx + o[0], top + 4, tz + o[1], tx + o[0], top + 6, tz + o[1], m["qz"])
                self.put(tx + o[0], top + 7, tz + o[1], s("end_rod", facing="up"))
            self.box(tx, top + 11, tz, tx, top + 12, tz, m["aether"])
            for o in ((1, 0, "east"), (-1, 0, "west"), (0, 1, "south"), (0, -1, "north")):
                self.put(tx + o[0], top + 11, tz + o[1], s("amethyst_cluster", facing=o[2], waterlogged=False))
            self.put(tx, top + 13, tz, s("amethyst_cluster", facing="up", waterlogged=False))
        self.integrity[tr <= rad + 1] = integrity
        self.htop[tr <= rad + 1] = top + (13 if cap else 1)
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
        if self.free_plots < 6 and rng.random() < 0.15:  # make sure there are enough free plots
            roll = 0.85
        if roll < 0.8:
            kind = "tower" if min(w, d) >= 7 and rng.random() < 0.6 else "terrace"
            self.building(kind, x0, z0, x1, z1, door, float(rng.uniform(0.5, 0.85)))
        elif roll < 0.9 and self.free_plots < FREE_PLOTS:
            self.plot(x0, z0, x1, z1, door)
            kind = "free plot"
        elif roll < 0.95:
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
        mix = np.choose(rng.integers(0, 5, n.shape), [m["qz_b"], m["calcite"], m["ds_t"], m["ds_pol"],
                                                       m["ds_cob"]])
        g[paved] = mix[paved]
        g[open_ground & (n > 0.42) & (speck >= 0.8) & (speck < 0.9)] = m["coarse"]

    def plot(self, x0, z0, x1, z1, door):
        """A cleared foundation inside the walls, free for anyone to build on."""
        m, rng = self.m, self.rng
        self.free_plots += 1
        ddx, ddz = DIRS[door]
        fx = x1 - 1 if ddx > 0 else x0 + 1 if ddx < 0 else (x0 + x1) // 2
        fz = z1 - 1 if ddz > 0 else z0 + 1 if ddz < 0 else (z0 + z1) // 2
        self.sign(fx, G, fz, door, ["FREE PLOT", "", "Build here if", "you like"], font=None, standing=True)
        self.box(x0, G - 1, z0, x1, G - 1, z1, m["coarse"], built=False)
        for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
            self.box(ax, G - 1, az, bx, G - 1, bz, m["ds_pol"], built=False)
            self.box(ax, G, az, bx, G, bz, m["qz_b"])
        self.claim(x0 - 1, z0 - 1, x1 + 1, z1 + 1, 0.35)

    def garden(self, x0, z0, x1, z1):
        m, rng = self.m, self.rng
        for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0, x0, z1), (x1, z0, x1, z1)):
            self.box(ax, G, az, bx, G, bz, self.slab("smooth_quartz"))
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
                    mix = [m["qz_b"], m["calcite"], m["ds_cob"], m["gravel"], m["ds_t"], m["iron_w"]]
                    for y in range(G, G + h):
                        self.put(x, y, z, mix[int(rng.integers(0, len(mix)))], built=False)
                    if h:
                        self.put(x, G + h - 1, z, m["moss"] if rng.random() < .3 else m["calcite"], built=False)
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

    # ---------- the Sundering, then time ----------
    def snapshot(self):
        """The city as it stood. Restoration rebuilds from this; everything after is damage."""
        self.pre_a = self.g.a.copy()
        self.removed = np.zeros(self.g.shape, bool)
        self.debris = np.zeros(self.g.shape, bool)

    def debris_put(self, x, y, z, st):
        if self.g.inside(R + x, y, R + z):
            self.put(x, y, z, st, built=False, keep=True)
            self.debris[R + x, y, R + z] = True

    def cut(self, mask3d):
        """Remove blocks as damage: restoration puts them back."""
        sel = mask3d & (self.g.a > AIR)
        self.removed |= sel
        self.g.a[sel] = AIR
        self.g.built[sel] = False

    def catastrophe(self):
        """The Sundering: the Spire's crown shatters, its ring snaps and falls, the outer wall is breached."""
        g, rng, m = self.g, self.rng, self.m
        cx, cz = self.spire_c
        lx, lz = self.dx - cx, self.dz - cz
        lr = np.maximum(np.maximum(np.abs(lx), np.abs(lz)), (np.abs(lx) + np.abs(lz)) / 1.4142)
        jag = G + 50 + (noise2(lx.shape, 3, rng) * 24).astype(int)
        core = (np.abs(lx) <= 1) & (np.abs(lz) <= 1)
        ys = np.arange(g.shape[1])[None, :, None]
        crown = ((lr <= 11)[:, None, :] & (ys > jag[:, None, :]) & ~core[:, None, :]) | \
                (core[:, None, :] & (ys > G + 64))
        ring = np.zeros(g.shape, bool)
        for (x, y, z) in self.ring_cells(cx, cz, -30, 100):
            if g.inside(R + x, y, R + z):
                ring[R + x, y, R + z] = True
        self.cut(crown | ring)
        self.ring_fallen(cx, cz)
        # three breaches in the outer wall, with their stone spilled both ways
        dx, dz, r, th = self.dx, self.dz, self.r, self.th
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
            keep_h = G + (hn * 3 * (d / w) * 2).astype(int)
            self.cut(breach[:, None, :] & (ys > keep_h[:, None, :]) & (ys < G + 14))
            spill = (r >= 76) & (r < 92) & (d < w + 2) & ~((r >= 82.5) & (r < 85.5))
            hgt = (np.clip(1 - np.abs(r - 84) / 8, 0, 1) * 4 * hn).astype(int)
            for y in range(G, G + 4):
                fill = spill & (hgt > y - G) & (g.a[:, y, :] == AIR)
                mix = np.choose(rng.integers(0, 4, dx.shape), [m["ds_t"], m["gravel"], m["ds_cob"], m["cobble"]])
                g.a[:, y, :][fill] = mix[fill]
                self.debris[:, y, :] |= fill
            self.notes.append(f"wall breach at {a:.0f} degrees")

    def decay(self):
        g, rng = self.g, self.rng
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
        mix = [m["qz_b"], m["calcite"], m["ds_cob"], m["gravel"], m["ds_t"], m["qz"], m["iron_w"]]
        tops = [self.slab("smooth_quartz"), self.slab("polished_deepslate"), m["moss"], self.slab("cobbled_deepslate")]
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
                            (m["ds_t"], self.g.s("cracked_deepslate_tiles"), .1),
                            (m["qz"], m["calcite"], .07), (m["qz_b"], m["calcite"], .05),
                            (m["iron"], m["iron_w"], .18)):
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
        # only real masonry carries weight: glass panes, bars, rods, leaves and plants hang off it
        from render import shape_of
        bearing = np.array([shape_of(k) in ("cube", "slab", "slab_top") or "_stairs" in k or k.split("[")[0].endswith("_wall")
                            for k in g.pal]) & ~np.array(["pane" in k or "glass" in k for k in g.pal])
        conduct = bearing[g.a]
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
            grow &= conduct | (reach & ~conduct)
            n = int(grow.sum())
            reach = grow
            if n == count:
                break
            count = n
        near = reach.copy()
        near[1:] |= reach[:-1]
        near[:-1] |= reach[1:]
        near[:, 1:] |= reach[:, :-1]
        near[:, :-1] |= reach[:, 1:]
        near[:, :, 1:] |= reach[:, :, :-1]
        near[:, :, :-1] |= reach[:, :, 1:]
        loose = solid & ~reach & ~(near & ~conduct) & g.built & ~g.keep
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
            if kind == "terrace" and rng.random() < 0.18:
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
        self.storehouse()
        self.camp()
        self.spire()
        self.market()
        self.crypt()
        self.mast()
        self.walls()
        self.conduits()
        self.monorail()
        self.pylons()
        self.arcology()
        self.archive()
        self.towers = []  # only street towers get extra bridges
        self.districts()
        self.sky_bridges()
        self.snapshot()
        self.catastrophe()
        self.wear_streets()
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
    """A site's restoration for each Age, as layered structure templates, plus functions that place them a few
    at a time. remnant:restore/<site> picks the variant for the current Age (score #age on objective remnant)."""
    g, site = city.g, city.sites[name]
    cols = site["mask"]
    xs, zs = np.nonzero(cols.any(axis=1))[0], np.nonzero(cols.any(axis=0))[0]
    x0, x1, z0, z1 = int(xs.min()), int(xs.max()) + 1, int(zs.min()), int(zs.max()) + 1
    tdir = os.path.join(out_dir, "data", "remnant", "structure", "core", "site")
    fbase = os.path.join(out_dir, "data", "remnant", "function", "restore")
    os.makedirs(tdir, exist_ok=True)
    at = "execute at @e[type=minecraft:marker,tag=remnant_core,limit=1] run"
    ox, oy, oz = x0 - R, -(G - 1), z0 - R
    cx, cz = int((x0 + x1) / 2) - R, int((z0 + z1) / 2) - R
    changed = 0
    for age in range(1, 6):
        new = city.restore(name, age)
        diff = new != g.a
        if not diff.any():
            continue
        changed = max(changed, int(diff.sum()))
        fdir = os.path.join(fbase, name, f"age{age}")
        os.makedirs(fdir, exist_ok=True)
        ys = np.nonzero(diff.any(axis=(0, 2)))[0]
        levels = list(range(int(ys.min()), int(ys.max()) + 1, site["layer"]))
        for k, y0 in enumerate(levels):
            part = np.full(g.shape, VOID, np.uint16)
            sel = diff.copy()
            sel[:, :y0, :] = False
            sel[:, y0 + site["layer"]:, :] = False
            part[sel] = new[sel]
            ns = types.SimpleNamespace(a=part, pal=g.pal, block_nbt={})
            tname = f"{name}_a{age}_{k}"
            Grid.write_structure(ns, os.path.join(tdir, f"{tname}.nbt"), x0, x1, z0, z1)
            cy = y0 - (G - 1)
            lines = [f"{at} place template remnant:core/site/{tname} ~{ox} ~{oy} ~{oz}",
                     f"{at} playsound minecraft:block.stone.place block @a ~{cx} ~{cy} ~{cz} 4 0.6",
                     f"{at} particle minecraft:poof ~{cx} ~{cy + 1} ~{cz} {(x1 - x0) / 4:.1f} 1 {(z1 - z0) / 4:.1f} 0.02 120"]
            if k + 1 < len(levels):
                lines.append(f"schedule function remnant:restore/{name}/age{age}/{k + 1} 8t")
            else:
                for sx, sy, sz, prof in site["summon"]:
                    lines.append(f'{at} summon minecraft:villager ~{sx} ~{sy - (G - 1)} ~{sz} {{VillagerData:{{profession:'
                                 f'"minecraft:{prof}",level:1,type:"minecraft:plains"}},Offers:{{Recipes:[]}},'
                                 f'PersistenceRequired:1b}}')
                lines += [f'tellraw @a {{"text":"{site["label"]} stands again.","color":"gold"}}',
                          "playsound minecraft:ui.toast.challenge_complete master @a"]
            with open(os.path.join(fdir, f"{k}.mcfunction"), "w") as f:
                f.write("\n".join(lines) + "\n")
    with open(os.path.join(fbase, f"{name}.mcfunction"), "w") as f:
        f.write(f"# Restore {site['label']} (from Age {site['age']}), layer by layer, in the current Age's materials.\n")
        for age in range(1, 6):
            cond = "..1" if age == 1 else "5.." if age == 5 else str(age)
            f.write(f"execute if score #age remnant matches {cond} run function remnant:restore/{name}/age{age}/0\n")
    return changed


def write_core_functions(out_dir):
    fdir = os.path.join(out_dir, "data", "remnant", "function", "core")
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "setup.mcfunction"), "w") as f:
        f.write("# Run once on the Hearth's ground block after pasting the core:\n"
                "#   execute positioned <x> <ground y> <z> run function remnant:core/setup\n"
                "scoreboard objectives add remnant dummy\n"
                "execute unless score #age remnant matches 1.. run scoreboard players set #age remnant 1\n"
                "kill @e[type=minecraft:marker,tag=remnant_core]\n"
                'summon minecraft:marker ~ ~ ~ {Tags:["remnant_core"]}\n')
    for age in range(1, 6):
        with open(os.path.join(fdir, f"age{age}.mcfunction"), "w") as f:
            f.write(f"# Called when Age {age} opens: restorations from now on use its materials.\n"
                    f"scoreboard players set #age remnant {age}\n")


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
    write_core_functions(dp)
    with open(os.path.join(a.out, "sites.txt"), "w") as f:  # for writing the quests: what, where, from which Age
        f.write("# site\tfrom Age\tlabel\tkind\tx0 z0 x1 z1 (relative to the Hearth)\n")
        for name, site in city.sites.items():
            xs, zs = np.nonzero(site["mask"].any(axis=1))[0], np.nonzero(site["mask"].any(axis=0))[0]
            f.write(f"{name}\t{site['age']}\t{site['label']}\t{site.get('kind', 'landmark')}\t"
                    f"{xs.min() - R} {zs.min() - R} {xs.max() - R} {zs.max() - R}\n")
    # the city as it stands at the end of Age V, every site restored: a preview, not shipped
    final = g.a.copy()
    for name in city.sites:
        new = city.restore(name, 5)
        d = new != g.a
        final[d] = new[d]
    fdir = os.path.join(dp, "data", "remnant", "structure", "core_final")
    os.makedirs(fdir, exist_ok=True)
    keep_nbt = {k: v for k, v in g.block_nbt.items() if final[k] == g.a[k]}
    fns = types.SimpleNamespace(a=final, pal=g.pal, block_nbt=keep_nbt)
    for i, x0 in enumerate(range(0, g.shape[0], 97)):
        for j, z0 in enumerate(range(0, g.shape[2], 97)):
            Grid.write_structure(fns, os.path.join(fdir, f"tile_{i}_{j}.nbt"), x0, min(x0 + 97, g.shape[0]),
                                 z0, min(z0 + 97, g.shape[2]))
    if a.jar and not a.no_render:
        iso(types.SimpleNamespace(a=final, pal=g.pal), assets, scale=4).save(os.path.join(a.out, "iso_final.png"))
    houses = 0
    for name in city.sites:
        n = write_site(city, name, dp)
        if name.startswith("house_"):
            houses += 1
        else:
            print(f"site {name}: up to {n} blocks change when restored")
    print(f"{houses} houses restorable, {city.free_plots} free plots")
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
