# Running the Remnant server

The server installs and updates itself from this repository the same way the game does, with packwiz-installer in server mode.

1. Make a NeoForge **21.1.256** server for Minecraft **1.21.1** on Java 21. On Pelican, use the NeoForge egg.
2. Give it **8 GB**: `-Xms4G -Xmx6G` in `user_jvm_args.txt`, in a container with 8 GB. The pack server sat at 5.5 GB in a 5.7 GB test container while generating terrain.
3. Put `packwiz-installer-bootstrap.jar` in the server folder, and run this before each start (on Pelican, add it to the startup command before `java ...`):

   ```
   java -jar packwiz-installer-bootstrap.jar -g -s server https://raw.githubusercontent.com/RadKayo/remnant/main/pack.toml
   ```

4. **Once, by hand:** download Ember's Ancient Remnants 1.0.2.2 for NeoForge 1.21.1 (`ancient_remnants-1.0.2.2-neoforge.jar`) from its CurseForge page and put it in `mods/`. Its author blocks automatic downloads. The installer recognises the file once it's there. It's server-only, so players never need it.
5. In `server.properties`: `view-distance=10`, `simulation-distance=6`, `spawn-protection=0`, and `allow-flight=true` (aircraft, mounts and bloodline flight would otherwise kick players).
6. Before anyone joins, pre-generate the area around spawn: `/chunky center 0 0`, `/chunky radius 2000`, `/chunky start`. The pack generated 2,601 chunks at 32 per second in testing.

## The city core

Remainder, the ruined city at spawn, is pasted once into a new world. It isn't part of the pack download, because only the server needs it. See `tools/citygen/README.md`:

- Paste `core.schem` with WorldEdit at the chosen spawn.
- Copy the generated `datapack/` into `world/datapacks/`.
- Run `execute positioned <x> <ground y> <z> run function remnant:core/setup` on the Hearth's ground block.

## What the pack already sets

- **Configs:**
  - PneumaticCraft's Cold Sweat integration is off (it crashed).
  - Tough As Nails is thirst only.
  - MineColonies quarters start at a 3-chunk radius and can grow to 8.
  - Distant Horizons' auto-updater is off (3.3.3 crashes on Chunky).
- **Datapacks** (in `kubejs/data`):
  - Ember's ruins become Ascendancy ruins.
  - Every gun's bullets are capped at about 160 blocks, so a shot can't force distant chunks to load (see `datapacks/README.md`).
