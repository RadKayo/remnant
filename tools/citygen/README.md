# City core generator

`citygen.py` builds Remnant's ruined city core, the Ascendancy city the group restores at spawn, as blocks. It's all our own work, so the output can ship with the pack.

What it builds, centred on the Hearth:

- **The plaza and the Hearth:** ringed paving, a sunken fire pit with an unlit copper brazier for the players to rekindle, benches and copper lamps.
- **The Elder's house:** the one roofed building, patched with Remnant timber. Beside it is the Remnant camp, with shelters, bedrolls, firewood, a lit campfire and a watered garden.
- **Streets:** four avenues to four gates, a ring road and diagonal lanes.
- **The Convergence Spire:** an octagonal tower with an amethyst aether core. The great copper ring is threaded through it, broken away at the upper right, and the missing arc lies in two pieces east of the Spire, still growing aether crystal.
- **The market:** a double colonnade around a fountain on the east avenue, with old stalls.
- **The Grave Warden's mausoleum:** a stair down to a burial crypt with niches and soul lanterns, and a graveyard above.
- **The mooring mast** for the Age of Steam airships.
- **The outer wall:** gatehouses with portcullises, corner towers with copper caps, and three breaches.
- **Lots:** ruined houses (row houses along the avenues and the ring road, more behind), empty district plots for later restoration, gardens and rubble.

The materials are cream limestone (Create), grey tuff, verdigris copper and amethyst. Decay comes from noise: ground floors mostly stand, roofs mostly don't, and landmarks break in big collapses rather than pinholes. Rubble piles up where blocks fell, and anything cut loose from the ground is dropped. Grass, moss, vines, glow lichen and a few trees grow over it.

Inside the ruins:

- **Furnishings:** counters and cauldrons, plus barrels and decorated pots that roll the `remnant:ruins/house` loot table.
- **Rubble:** some of it is suspicious gravel, brushed for `remnant:ruins/rubble`. Both tables hold placeholder vanilla items until the lore items (Torn Pages, Memory Shards) exist.
- **Inscriptions:** waxed signs written in the Runelic font (`runelic:runelic`), so they show as runes. They name shops over doors and mark the Hearth, the Spire, the market, the crypt and each gate.

## Restoration

Every landmark is a site the group restores: `hearth`, `gate_north`, `gate_east`, `gate_south`, `gate_west`, `market`, `crypt` and `mast`. A restored site is built from the same design as the ruin:

- What fell is put back in the materials of the Age that rebuilt it: mud brick in Age I, cobblestone in Age II, stone brick in Age III, brick in Age IV, and the original stone in Age V. Salvaged metal goes back as it was.
- Rubble, vines and moss are cleared. Grass and flowers stay.
- The Age adds its own touches. The Hearth's brazier is lit, with torches on the old lamp posts. A mended gate gets torches beside the arch and banners above it.

Only blocks inside the site change, so anything players built nearby is left alone. Each site is written as structure templates three layers high, plus a function that places them one after another with dust and sound, and then announces the restoration to everyone:

```mcfunction
summon minecraft:marker <Hearth x> <ground y> <Hearth z> {Tags:["remnant_core"]}
function remnant:restore/gate_south
```

The marker goes on the Hearth's ground block once, when the core is pasted; the functions find the site from it. An FTB Quests command reward can call the function when the group completes the site's project.

Keep the seed and the generator version fixed once the core is in a world. The restorations are differences from that exact ruin.

## Running

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/w/.pylib -v "$PWD":/w -v <this folder>:/src:ro \
  -v <dir with the jars>:/jars:ro -w /w python:3.12-alpine \
  python /src/citygen.py --seed 7 --out out --jar /jars/client-1.21.1-extra.jar --jar /jars/create-1.21.1-6.0.10.jar
```

The working folder needs `.pylib` with numpy and Pillow (`pip install --target .pylib numpy pillow`). The jars are only read for block colours and to check that every block exists. A different `--seed` gives a different city with the same landmarks.

Output in `out/`:

| File | What it is |
| --- | --- |
| `core.schem` | WorldEdit schematic, 193 × 100 × 193. Stand where the Hearth goes, with your feet on the ground, and run `//schem load core` then `//paste -m !minecraft:structure_void`. The mask leaves the terrain outside the city untouched. |
| `datapack/` | The same city as four vanilla structure templates, `remnant:core/tile_<x>_<z>`. In a world whose ground is at y = 10, `/place template` them at (-96, -1, -96), (-96, -1, 1), (1, -1, -96) and (1, -1, 1). Forceload the area first. |
| `plan.png`, `iso.png`, `iso_centre.png` | Quick previews without the game |
| `datapack/data/remnant/function/restore/` | The restoration functions, with their templates under `structure/core/site/` |
| `samples.txt` | One position per block state, relative to the Hearth with y = 0 at ground level, for checking a placement with `/execute if block` |

## Checked in game

Placed on a flat NeoForge 1.21.1 test world (vanilla and Create). 161 of 169 sampled block states match exactly. The other 8 are crops that grew between placing and checking, leaf distances, and a few fence and wall joins the game recalculates.
