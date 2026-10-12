# Datapacks

Our own datapacks. `tools/pack/build.py` copies each one's `data/` into `kubejs/data/`, which KubeJS loads as a datapack on every world, so they ship with the pack and apply from world creation.

## remnant_ruins

Rebuilds Ember's Ancient Remnants (giant pillars, a bridge, aqueducts and a stone hand) as ruins of the Ascendancy as they generate. Nothing of Ember's is copied or edited: a Lithostitched worldgen modifier attaches our block-swap processor list to their 42 template pools.

- `worldgen/processor_list/ascendancy_ruins.json`:
  - Stone bricks and stone become white quartz and calcite.
  - The banding stairs and slabs become dark polished deepslate.
  - Cobblestone pieces become white diorite, so the walls stay clean instead of speckled.
  - A few blocks become dead aether veins (amethyst).
  - Stairs and slabs keep their orientation.
- `worldgen/processor_list/ascendancy_ruins_light.json`: the same with no dark trim, for the aqueducts, whose detail was too fine for it.
- `lithostitched/worldgen_modifier/`: attaches each list to its pools.

Needs Lithostitched 1.8+ and Ember's Ancient Remnants 1.0.2.2. Ember's is server-only in the pack: it's pure worldgen, and its author blocks automatic downloads, so the server's copy is placed by hand. Checked in the full pack: a placed large pillar came out as about 9,000 quartz, calcite and smooth quartz blocks, with deepslate bands and amethyst veins, and no stone left.

## remnant_guns

Caps every bullet from Create: Gunsmithing and NTGL at about 160 blocks of travel (speed times lifetime), which stays inside the area loaded around the shooter. Out of the box a gatling round can fly 9,000 blocks. A fast projectile checks every block on its path, so a shot toward the horizon forces chunk loads on the server thread. That is the likely way ewewukek's Musket Mod froze Dragonfyre on Sept 13 2026. Thrown items (grenades) are left alone, since their "life" is the fuse. The files are full copies of the mods' weapon definitions with only `projectile.life` lowered; regenerate them if either mod updates.
