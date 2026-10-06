# Remnant

A story-driven co-op survival adventure for Minecraft 1.21.1 on NeoForge, built for a small friend group.

> Four hundred years ago, a civilisation that ran on magic-fuelled machines tried to open a bridge to other worlds and broke this one instead. You're the Remnant, descendants of the survivors, starting over with flint and fire.
>
> Rebuild through five Ages, from stone tools to steam trains, airships and finally the old world's own reactors, by recovering lost schematics from the ruins. Rifts lead to other realms, including a full Pokémon region with its own story, where you can raise a partner who fights beside you back home.
>
> Your bloodline grows with you: nine lineages that awaken new abilities as the world advances. Combat is skill-based, bosses are about patterns rather than giant health bars, and death stings, but your friends can drag you back.
>
> No grinding for bigger numbers. Just a broken world worth exploring, and a town worth defending.

**Status:** in development. The design is settled and the pack is being built and tested. Nothing here is playable yet.

## Design rules

These decide what goes into the pack and how it's tuned:

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

Players install the pack once in Prism Launcher, and it updates itself on every launch. See [docs/players.md](docs/players.md).

## Repository layout

| Path | What it holds |
| --- | --- |
| `pack.toml`, `index.toml` | packwiz metadata: Minecraft 1.21.1, NeoForge, and the file index |
| `mods/` | One `.pw.toml` per mod, pointing at its Modrinth or CurseForge download |
| `config/`, `defaultconfigs/` | Mod configuration shipped with the pack |
| `kubejs/` | Scripts for the custom systems: the stone-age start, Ages and schematics, waystone rebuilding, Remmings and more |
| `docs/` | Player and maintainer notes (not shipped to clients) |

## Maintaining

The pack is managed with [packwiz](https://packwiz.infra.link/):

```bash
packwiz modrinth add <slug>     # add a mod from Modrinth
packwiz curseforge add <slug>   # add a mod from CurseForge
packwiz update --all            # update everything
packwiz refresh                 # rebuild index.toml after editing files by hand
```

Commit `index.toml` together with whatever changed, or clients will reject the update. Every change is tested on the test server before it reaches players.
