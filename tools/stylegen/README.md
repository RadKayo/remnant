# Bloodline styles (proof of concept)

`restyle.py` recolours a MineColonies blueprint for each of Remnant's nine bloodlines and renders an isometric preview sheet. Only materials change: woods, stones, Domum Ornamentum roof tiles and wall plaster, glass, lighting and bedding. Every building keeps its original design. Each swap is checked against the game's real block list before it's used.

**Licensing:** MineColonies' bundled styles are All Rights Reserved. Nothing this script produces from them is committed here or shipped in the pack. Output stays local until we either have the authors' permission, generate styles on our own server from its own copy of MineColonies, or recolour a base style we built ourselves.

## Running

From a working folder containing:

- `tex/` with `assets/minecraft/textures/block`, `assets/minecraft/blockstates` (from the Minecraft client jar) and `assets/domum_ornamentum/textures/block` (from Domum Ornamentum)
- the blueprint to recolour

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -w /w python:3.12-alpine \
  sh -c 'pip install -q --target /w/.pylib nbtlib==2.0.4 pillow && PYTHONPATH=/w/.pylib python restyle.py some.blueprint preview.png'
```

The bloodline material sets are the `BLOODLINES` table at the top of the script.
