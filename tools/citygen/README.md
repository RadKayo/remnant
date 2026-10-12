# City core generator: Remainder

`citygen.py` builds Remainder, the ruined Ascendancy city at spawn that the group restores. "Remainder" is the Remnant's own name for it, on plain wooden signs inside each gate. as blocks. It's all our own work, so the output can ship with the pack.

What it builds, centred on the Hearth. The Ascendancy was a high-tech aether civilisation, and its city looks it: white quartz, dark iron, violet glass, verdigris copper, and aether-crystal conduits that are dark now and can be made to glow again.

- **The plaza and the Hearth:** ringed paving with aether lines converging on a sunken fire ring, and an unlit copper brazier for the players to rekindle. Beside it are the Elder's house and the Storehouse, both patched with Remnant timber, and the Remnant camp of tents, fire and garden.
- **Streets:** four avenues to four gates, a ring road and diagonal lanes, with violet conduit lines down their middles, light pylons along the avenues, and an elevated monorail on quartz pillars over the ring road, partly fallen.
- **Habitation towers:** round quartz shafts that taper as they rise, with thin iron ribs, ribbon windows of violet or clear glass, white ledges, glass-railed balconies, a conduit seam, a glass dome with a copper halo, and an antenna.
- **Terraced halls:** tiers stepping back from the street, each with a full-height glass front under a thin overhanging roof plate, chamfered corners, ribbon windows, planted terraces and a roof garden.
- **The Convergence Spire:** an octagonal quartz shaft ribbed in iron, tapering into an open crystal lantern and a needle, with an aether core up its middle. The great copper ring stands around it.
- **The Twin Arcology:** two fourteen-storey towers joined by three glass sky bridges. Sky bridges also link street towers that line up.
- **The Archive:** a rotunda in a quartz colonnade under a violet glass dome, with shelves around an aether crystal. Restored, it teaches the runes.
- **The market:** a quartz colonnade with an iron architrave under a glass canopy, around a fountain.
- **The Grave Warden's mausoleum:** a crypt below it, and a graveyard above.
- **The mooring mast** for the Age of Steam airships.
- **The outer wall:** dark tile with quartz bands and its own aether line. A great copper ring is set into each gatehouse, and the corner towers carry ward pylons, quartz obelisks crowned with aether crystal.
- **Free plots** for anyone to build on.

The generator builds the city whole first, then breaks it. **The Sundering** shatters the Spire's crown, snaps its ring (the missing arc falls in two pieces east of it) and breaches the outer wall. Then **time** does the rest.

Decay comes from noise. Ground floors mostly stand while roofs and upper floors mostly don't. Landmarks and towers break in large clean collapses, and houses take smaller holes. Rubble piles up where blocks fell, and anything cut loose from the ground is dropped. Quartz weathers to calcite and iron rusts. Grass, moss, vines, glow lichen and a few trees grow over it.

Inside the ruins:

- **Furnishings:** counters and cauldrons, plus barrels and decorated pots that roll the `remnant:ruins/house` loot table.
- **Rubble:** some of it is suspicious gravel, brushed for `remnant:ruins/rubble`. Both tables hold placeholder vanilla items until the lore items (Torn Pages, Memory Shards) exist.
- **Inscriptions:** waxed signs written in the Runelic font (`runelic:runelic`), so they show as runes. They name shops over doors and mark the Hearth, the Spire, the market, the crypt and each gate.

## Restoration

The group restores the city in front of everyone. There are two kinds of site:

- **Landmarks:** `hearth`, `gate_north`, `gate_east`, `gate_south`, `gate_west`, `market`, `crypt` and `mast` (the Spire comes later). Each has an earliest Age.
- **Houses:** `house_0` and up, one for every ruined house. The rune sign over each door names what it was: a baker, scribe, apothecary, coppersmith and so on. Restoring it brings that trade back:
  - a door, glass in the windows, a torch by the door, a lamp on every floor and a smoking chimney
  - a ladder up through the floors to the roof
  - a bed, a chest, and the trade's workstation
  - a villager of that profession, who moves in, sleeps there and works there. They come with no trades, so they're townsfolk rather than shops.

Every site is built from the same design as the ruin:

- What fell is put back in the materials of the Age the group is in when they finish it. Repairs match the old stone's tone but not its finish, so you can see what was mended.
  - Pale stone is patched with mud brick in Age I, calcite in Age II, polished diorite in Age III and quartz bricks in Age IV.
  - Dark stone and metal are patched with cobbled deepslate, then deepslate bricks, then polished deepslate.
  - Floors and roofs are mud brick, then spruce, then stone.
  - Age V restores the original, and the dead aether conduits glow again (pearlescent froglight).
  - Salvaged metal and glass go back as they were.
- Rubble, vines and moss are cleared, while grass and flowers stay.
- Debris left by the Sundering (the fallen ring pieces, rubble from the breaches) is cleared from a site when it's restored.
- Beyond the landmarks and houses, the streets (`aether_grid`, Age V), the four wall sectors (`wall_ne` and so on, Age III), the `monorail` (Age III), the `arcology` (Age IV), the `archive` (Age IV) and the `spire` (Age V, the finale) are sites too. Restored in Age V, every conduit in a site glows (pearlescent froglight).
- `datapack/data/remnant/structure/core_final/` holds the whole city as it stands with every site restored in Age V. It's a preview for us, not for the pack.
- Landmarks add their own touches: the Hearth's brazier is lit, the gates get torches and banners, and the market gets a bell for the townsfolk to gather at.

Only blocks inside the site change. Each restoration is written for all five Ages as structure templates, three layers high for landmarks and four for houses. A function places them one after another with dust and sound, summons any residents, and announces it to everyone.

Commands (all in the generated datapack):

```mcfunction
# once, standing on the Hearth's ground block after pasting the core
execute positioned <x> <ground y> <z> run function remnant:core/setup
# when an Age opens (from the Ages system)
function remnant:core/age3
# when a project is finished (an FTB Quests command reward)
function remnant:restore/house_12
```

`sites.txt` lists every site with its label, earliest Age and footprint, for writing the quests.

**Deliveries** go to the **Storehouse** by the plaza. It has three bays, each a hopper chute in front of a space on the wall for that project's Task Screen (FTB Quests). A Task Screen only accepts items fed into it, and with the task set to "Task screen only" the quest book can't take them either. So everything has to be carried back to the city. The screens are placed and bound by hand once the quests exist.

**Free plots:** about seven cleared foundations inside the walls, each with a plain sign saying anyone can build there. Everyone's own base is outside the core, in the colony quarters.

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
| `datapack/data/remnant/function/` | `core/setup`, `core/age1`..`age5`, `restore/<site>` and the steps for each Age, with templates under `structure/core/site/` |
| `sites.txt` | Every restoration site: earliest Age, label, footprint |
| `samples.txt` | One position per block state, relative to the Hearth with y = 0 at ground level, for checking a placement with `/execute if block` |

## Checked in game

Placed on a flat NeoForge 1.21.1 test world (vanilla and Create). 161 of 169 sampled block states match exactly. The other 8 are crops that grew between placing and checking, leaf distances, and a few fence and wall joins the game recalculates.
