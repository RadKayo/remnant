# Compatibility audit

Scripts that check the planned mod list against NeoForge 1.21.1 before anything goes into the pack. Run them from an empty working folder (they create `data/` and `jars/` next to where you run them):

```bash
python -I path/to/tools/compat/resolve.py    # find each mod's newest NeoForge 1.21.1 build, follow dependencies
python -I path/to/tools/compat/download.py   # download the jars into jars/
python -I path/to/tools/compat/analyze.py    # read every jar's metadata and mixins
python -I path/to/tools/compat/check.py      # report missing dependencies, version clashes and mixin overlaps
```

| Script | What it does |
| --- | --- |
| `resolve.py` | Holds the planned mod list (`PLAN`). Resolves each mod on Modrinth, falling back to CurseForge, and follows required dependencies |
| `download.py` | Downloads every resolved jar, checking Modrinth's SHA-1 |
| `analyze.py` | Reads each jar's `neoforge.mods.toml` and its bundled (jar-in-jar) libraries, and parses the bytecode of every mixin to record which game methods it changes and how |
| `check.py` | Checks dependencies and version ranges with the same rules NeoForge uses (Maven `ComparableVersion`), lists declared incompatibilities, and ranks mixin overlaps: `high` when one mod rewrites a method another mod hooks inside, `low` when the other hooks only its start or end |
| `rcon.py` | A tiny RCON client for driving the test server (forcing chunk generation in each dimension, for example) |

The static checks catch metadata problems; the test server catches everything else. Results and the fixes we chose are recorded in the design doc's Compatibility tab.
