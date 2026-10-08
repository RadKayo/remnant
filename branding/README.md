# Branding

Scripts that draw Remnant's art, plus review drafts. Nothing in this folder ships to players until a finished asset is copied into the pack (for example under `kubejs/assets/`).

| Script | Draws |
| --- | --- |
| `src/coins.py` | The six Remming coin textures (16x16, reskinning Create: Numismatics' denominations) and a preview sheet |
| `src/brand.py` | The emblem, window icons, logo, title and loading backgrounds, and mock-ups |
| `src/items.py` | Textures for our own (KubeJS) items: flint tools, Hearthstone, Relay Kit, the Age keys, rune items, and a preview sheet |

Outputs land in `out/` (finished assets) and `drafts/` (review images).

## Running

The scripts need Pillow and four open-licence fonts from Google Fonts (SIL OFL): Cinzel Decorative Black, Cinzel, Silkscreen and Pixelify Sans. Download them into `fonts/`, then:

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -w /w python:3.12-alpine \
  sh -c 'pip install -q --target /w/.pylib pillow && PYTHONPATH=/w/.pylib python src/coins.py && PYTHONPATH=/w/.pylib python src/brand.py && PYTHONPATH=/w/.pylib python src/items.py'
```
