# Installing Remnant

Remnant updates itself: every time you launch, it checks this repository and downloads any changed mods or configs before the game starts.

1. Install [Prism Launcher](https://prismlauncher.org/).
2. Create a new instance: Minecraft **1.21.1**, mod loader **NeoForge** (the version listed in `pack.toml`).
3. Download `packwiz-installer-bootstrap.jar` from the [packwiz-installer-bootstrap releases](https://github.com/packwiz/packwiz-installer-bootstrap/releases) and put it in the instance's `minecraft` folder (Edit instance, then Open .minecraft).
4. In the instance settings, under **Settings → Custom commands**, tick the box and set the pre-launch command to:

   ```
   "$INST_JAVA" -jar packwiz-installer-bootstrap.jar https://raw.githubusercontent.com/RadKayo/remnant/main/pack.toml
   ```

5. In the instance settings, under **Settings → Java**, set **Maximum memory** to **6144 MB** (8192 MB if you have it). With about 260 mods, the game runs out of memory below 4 GB.
6. Launch. The first start downloads about 1.5 GB of mods; later starts only fetch what changed. The first load takes a few minutes.

Nothing needs downloading by hand. One mod's author blocks automatic downloads, but it only builds ruins in the world, so it lives on the server alone.
