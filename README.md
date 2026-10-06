# Remnant

A NeoForge 1.21.1 adventure modpack for a small friend group.

Four hundred years ago the Ascendancy tried to bridge to other worlds and tore the world open instead. You play the Remnant: descendants of the survivors, starting over with flint and fire, rebuilding through five Ages while rifts pull you into other realms.

**Status:** in development. Nothing here is playable yet.

## Playing

Players install the pack once in Prism Launcher, and it updates itself on every launch. See [docs/players.md](docs/players.md).

## Layout

| Path | What it holds |
| --- | --- |
| `pack.toml`, `index.toml` | packwiz metadata: Minecraft 1.21.1, NeoForge, and the file index |
| `mods/` | One `.pw.toml` per mod, pointing at its Modrinth or CurseForge download |
| `config/`, `kubejs/`, `defaultconfigs/` | Pack configuration and scripts (added as the pack grows) |
| `docs/` | Player and maintainer notes (not shipped to clients) |

## Maintaining

The pack is managed with [packwiz](https://packwiz.infra.link/):

```bash
packwiz modrinth add <slug>     # add a mod from Modrinth
packwiz curseforge add <slug>   # add a mod from CurseForge
packwiz update --all            # update everything
packwiz refresh                 # rebuild index.toml after editing files by hand
```

Commit `index.toml` together with whatever changed, or clients will reject the update.
