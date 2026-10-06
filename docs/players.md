# Installing Remnant

Remnant updates itself: every time you launch, it checks this repository and downloads any changed mods or configs before the game starts.

1. Install [Prism Launcher](https://prismlauncher.org/).
2. Create a new instance: Minecraft **1.21.1**, mod loader **NeoForge** (the version listed in `pack.toml`).
3. Download `packwiz-installer-bootstrap.jar` from the [packwiz-installer-bootstrap releases](https://github.com/packwiz/packwiz-installer-bootstrap/releases) and put it in the instance's `minecraft` folder (Edit instance, then Open .minecraft).
4. In the instance settings, under **Settings → Custom commands**, tick the box and set the pre-launch command to:

   ```
   "$INST_JAVA" -jar packwiz-installer-bootstrap.jar https://raw.githubusercontent.com/RadKayo/remnant/main/pack.toml
   ```

5. Launch. The first start downloads everything; later starts only fetch what changed.

If a mod is CurseForge-only and its author blocks third-party downloads, the installer will ask you to download that one file by hand and tell you where to put it.
