# Datapacks

Our own datapacks. They ship with the pack.

## remnant_ruins

Rebuilds Ember's Ancient Remnants (giant pillars, a bridge, aqueducts and a stone hand) as ruins of the Ascendancy, as they generate. Nothing of Ember's is copied or edited: a Lithostitched worldgen modifier attaches our block-swap processor list to their 42 template pools.

- `worldgen/processor_list/ascendancy_ruins.json`:
  - Stone bricks and stone become white quartz and calcite.
  - The banding stairs and slabs become dark polished deepslate.
  - Cobblestone pieces become white diorite, so the walls stay clean instead of speckled.
  - A few blocks become dead aether veins (amethyst).
  - Stairs and slabs keep their orientation.
- `worldgen/processor_list/ascendancy_ruins_light.json`: the same with no dark trim, for the aqueducts, whose detail was too fine for it.
- `lithostitched/worldgen_modifier/`: attaches each list to its pools.

Needs Lithostitched 1.8+ and Ember's Ancient Remnants 1.0.2.2. Tested by placing every structure with `/place structure` on a NeoForge 1.21.1 test world.
