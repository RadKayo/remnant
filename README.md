# Remnant

A story-driven co-op survival adventure for Minecraft 1.21.1 on NeoForge, built for a small friend group.

> Four hundred years ago, a civilisation that ran on magic-fuelled machines tried to open a bridge to other worlds and broke this one instead. You're the Remnant, descendants of the survivors, starting over with flint and fire.
>
> Every expedition is won before it starts. Meals that take days to ferment, brews from herbs that only grow in other realms, oils for the monster you're hunting, rations that keep on the road: preparation is how you get strong.
>
> Rebuild through five Ages, from stone tools to steam trains, airships and finally the old world's own reactors, by recovering lost schematics from the ruins. Rifts lead to other realms, including a full Pokémon region with its own story, where you can raise a partner who fights beside you back home.
>
> Your bloodline grows with you: nine lineages that awaken new abilities as the world advances. Combat is skill-based, bosses are about patterns rather than giant health bars, and death stings, but your friends can drag you back.
>
> No grinding for bigger numbers. Just a broken world worth exploring, and a town worth defending.

**Status:** v0.1.0. All 262 mods install and boot on server and client, with the compatibility fixes, the reskinned ruins and the gun safety caps. The custom systems (the Ages, the stone-age start, the Grave Warden, bloodline powers, relics and quests) are next, so it isn't playable as Remnant yet.

## Design rules

These decide what goes into the pack and how it's tuned:

- **Preparation is the game.** Power comes mostly from what you bring: meals, aged drinks, brews, blade oils and rations made from ingredients you gather across the world and its realms. Bosses and deep realms are tuned for players who arrive prepared.
- **No number race.** Characters grow through new abilities, mobility and utility, not stacked damage percentages. Gear power is gated by the Ages.
- **Earned progress.** Each Age opens when the group recovers a piece of the old world, not by grinding resources.
- **Earned flight.** Mounts and machines come first. Flight is hard to get, and nothing moves faster than 75 blocks per second.
- **Shortcuts only to places you've been.** Waystones are found and rebuilt, roads become fast travel once built, and the frontier stays slow.
- **Bosses are fights, not sponges.** Readable patterns, arenas and phases, with health tuned to the number of players present.
- **One big machine mod per Age,** so systems don't overlap and the server stays fast.

## The five Ages

| Age | Opened by | What it brings |
| --- | --- | --- |
| I. Embers | The start | Flint tools, campfires, thirst and temperature, seasons |
| II. Hearths | Surviving the first winter | Iron, farming, a town with NPC workers, waterwheels and windmills, bronze and steel, horses and carts, roads, rebuilt waystones |
| III. Steam | The Gearwright Schematic | Steam engines, trains, ships and cannons, aircraft and airships, first electricity |
| IV. Industry | The Foundry Codex | Heavy industry, oil and steel, drones, computers |
| V. Reclamation | The Aether Core | The old world's own technology, and the finale |

Alongside the Ages run **the Weave** (magic, including a forbidden path) and **the Rifts** (other realms that open with the story).

## Bloodlines

Bladebound, Stormwalker, Ironsoul, Weave-touched, Riftborn, Deepdelver, Beastbound, Graveborn and Hearthborn. Each has a base kit and three awakenings that unlock with the Ages and a personal trial. Between them they cover tank, healer and support, damage, control and summoner roles.

## Realms

The Twilight Forest, the Aether, the Undergarden, the Otherside, Eternal Starlight and the Bumblezone, plus the Wild Realm (a full Pokémon region), arenas for the old world's fallen titans, an endless rift of dungeons, the ruined capital, and the End.

## Playing

Players install the pack once in Prism Launcher, and it updates itself on every launch. See [docs/players.md](docs/players.md). For the server, see [docs/server.md](docs/server.md).

## Repository layout

| Path | What it holds |
| --- | --- |
| `pack.toml`, `index.toml` | packwiz metadata: Minecraft 1.21.1, NeoForge, and the file index |
| `mods/` | One `.pw.toml` per mod, pointing at its Modrinth or CurseForge download |
| `config/`, `defaultconfigs/` | Mod configuration shipped with the pack |
| `kubejs/` | Scripts for the custom systems (coming), our textures over other mods' (Remming coins) and our datapacks in `kubejs/data` (generated, don't edit) |
| `datapacks/` | Source of our datapacks: Ascendancy ruins, gun range caps (see its README) |
| `tools/pack/` | `build.py` writes `mods/` from the audited list; `cap_guns.py` writes the gun caps |
| `tools/citygen/` | The generator for Remainder, the city core (not shipped; its output goes on the server) |
| `docs/` | Player and maintainer notes (not shipped to clients) |
| `tools/compat/` | The compatibility audit: resolves the mod plan, checks dependencies and mixin overlaps (not shipped) |

## Maintaining

The pack is managed with [packwiz](https://packwiz.infra.link/), but `mods/` is generated from the audited mod list rather than edited by hand:

1. Add or change the mod in the plan in `tools/compat/resolve.py`, then run the audit (resolve, download, analyze, check) in [`tools/compat`](tools/compat/README.md).
2. `python3 tools/pack/build.py <compat>/data/resolved.json <compat>/jars` rewrites `mods/` and copies our datapacks and textures into `kubejs/`.
3. `packwiz refresh` rebuilds `index.toml`. `config/DistantHorizons.toml` is marked `preserve = true` there, so players keep their own video settings, and refresh keeps that flag.
4. Install the result into a scratch server and client with `packwiz serve` plus packwiz-installer, and boot both before pushing.

Commit `index.toml` together with whatever changed, or clients will reject the update. Every change is tested on the test server before it reaches players.

Before adding or updating mods, run the audit in [`tools/compat`](tools/compat/README.md). Two packwiz rules came out of it:

- Sides: everything installs on both sides except mods Modrinth marks server-unsupported (rendering, HUD, tooltips), plus Epic Tweaks, which breaks a dedicated server. Libraries that Modrinth calls server-only still go on both sides (SmartBrainLib, CodxLib, Lithostitched, Structure Pool API). Ember's Ancient Remnants is server-only, because its author blocks automatic downloads and clients don't need it.
- Iris is held at 1.8.14-beta.1, because 1.8.12 refuses Sodium 0.8.13.
- Distant Horizons is pinned to 3.3.2 with its built-in updater turned off, until its Chunky crash is fixed.
