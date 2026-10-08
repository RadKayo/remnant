"""Resolve Remnant's planned mods to NeoForge 1.21.1 builds (Modrinth first, CurseForge via cfwidget),
follow required dependencies, and write data/resolved.json.

Usage: python -I tools/resolve.py   (run from compat/)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "RadKayo/remnant-compat-audit (github.com/RadKayo/remnant)"}
LOADER, MC = "neoforge", "1.21.1"

# (group, display name, candidate Modrinth slugs, CurseForge slug or None, note)
# A note of "alt:<key>" marks one side of an undecided either/or.
PLAN = [
    ("framework", "FTB Quests", [], "289412", ""),
    ("framework", "FTB Library", [], "404465", "library"),
    ("framework", "FTB Teams", [], "404468", "library"),
    ("framework", "Easy NPC", ["easy-npc"], "easy-npc", ""),
    ("framework", "Patchouli", ["patchouli"], "patchouli", ""),
    ("framework", "Bountiful", ["bountiful"], "bountiful", ""),
    ("framework", "AStages", ["astages"], "astages", ""),
    ("framework", "KubeJS", ["kubejs"], "kubejs", ""),
    ("framework", "CC: Tweaked", ["cc-tweaked"], "cc-tweaked", ""),
    ("survival", "Tough As Nails", ["tough-as-nails"], "tough-as-nails", "thirst only"),
    ("survival", "Cold Sweat", ["cold-sweat"], "cold-sweat", "temperature"),
    ("survival", "Serene Seasons", ["serene-seasons"], "serene-seasons", ""),
    ("survival", "Comforts", ["comforts"], "comforts", ""),
    ("prep", "Farmer's Delight", ["farmers-delight"], "farmers-delight", ""),
    ("prep", "Meal Mastery", ["farmers-delight-meal-mastery"], None, ""),
    ("prep", "Cuisine Delight", ["cuisine-delight"], None, "alt:kitchen"),
    ("prep", "Cooking for Blockheads", ["cooking-for-blockheads"], "cooking-for-blockheads", "alt:kitchen"),
    ("prep", "Brewin' and Chewin'", ["brewin-and-chewin"], "brewin-and-chewin", ""),
    ("prep", "Let's Do Vinery", ["lets-do-vinery"], None, ""),
    ("prep", "Let's Do Brewery", ["lets-do-brewery-farmcharm-compat", "lets-do-brewery"], None, ""),
    ("prep", "Let's Do HerbalBrews", ["lets-do-herbalbrews"], None, ""),
    ("prep", "Let's Do Farm & Charm", ["lets-do-farm-charm"], None, ""),
    ("prep", "Let's Do Bakery", ["lets-do-bakery-farmcharm-compat", "lets-do-bakery"], None, ""),
    ("prep", "Let's Do WilderNature", ["lets-do-wildernature"], None, ""),
    ("prep", "Farmer's Respite", ["farmers-respite"], "farmers-respite", ""),
    ("prep", "Spice of Life: Onion", ["spice-of-life-onion"], None, ""),
    ("prep", "Hexalia", ["hexalia"], "hexalia", ""),
    ("prep", "Easy Brewing", ["easy-brewing"], None, "alt:alchemy"),
    ("prep", "Reactive Alchemy", ["reactive"], None, "alt:alchemy"),
    ("prep", "Potion Combiner", ["potion-combiner"], None, ""),
    ("prep", "Toxony", ["toxony"], "toxony", ""),
    ("prep", "Rationcraft", ["rationcraft"], None, ""),
    ("prep", "Salt: Renewed", ["salt-renewed"], None, ""),
    ("prep", "Butchery", ["butchery"], "butchery", ""),
    ("prep", "Tide 2", ["tide"], "tide", ""),
    ("prep", "Campfire Creations", ["campfire-creations"], None, ""),
    ("prep", "Create Slice & Dice", ["slice-and-dice"], "create-slice-dice", ""),
    ("prep", "Create: Central Kitchen", ["create-central-kitchen"], "create-central-kitchen", ""),
    ("prep", "Immersive Cooking & Farming", ["immersive-cooking-adoon"], None, ""),
    ("prep", "Applied Cooking", ["applied-cooking"], None, ""),
    ("death", "Hardcore Revival", ["hardcore-revival"], "hardcore-revival", ""),
    ("death", "Corpse", ["corpse"], "corpse", ""),
    ("death", "Reliable Requiem", ["reliable-requiem"], None, ""),
    ("world", "Terralith", ["terralith"], "terralith", ""),
    ("world", "Tectonic", ["tectonic"], "tectonic", ""),
    ("world", "Alex's Caves Continued", ["alexs-caves-continued", "alexs-caves"], None, ""),
    ("world", "The Lost Cities", ["the-lost-cities", "lostcities"], "the-lost-cities", ""),
    ("ruins", "YUNG's Better Dungeons", ["yungs-better-dungeons"], None, ""),
    ("ruins", "YUNG's Better Mineshafts", ["yungs-better-mineshafts"], None, ""),
    ("ruins", "YUNG's Better Strongholds", ["yungs-better-strongholds"], None, ""),
    ("ruins", "YUNG's Better Desert Temples", ["yungs-better-desert-temples"], None, ""),
    ("ruins", "YUNG's Better Jungle Temples", ["yungs-better-jungle-temples"], None, ""),
    ("ruins", "YUNG's Better Ocean Monuments", ["yungs-better-ocean-monuments"], None, ""),
    ("ruins", "YUNG's Better Witch Huts", ["yungs-better-witch-huts"], None, ""),
    ("ruins", "YUNG's Better Nether Fortresses", ["yungs-better-nether-fortresses"], None, ""),
    ("ruins", "YUNG's Better End Island", ["yungs-better-end-island"], None, ""),
    ("ruins", "YUNG's Bridges", ["yungs-bridges"], None, ""),
    ("ruins", "YUNG's Extras", ["yungs-extras"], None, ""),
    ("ruins", "When Dungeons Arise", ["when-dungeons-arise"], "when-dungeons-arise", ""),
    ("ruins", "Dungeons and Taverns", ["dungeons-and-taverns"], None, ""),
    ("ruins", "Towns and Towers", ["towns-and-towers"], None, ""),
    ("ruins", "Explorify", ["explorify"], None, ""),
    ("ruins", "Lootr", ["lootr"], "lootr", ""),
    ("ruins", "End Remastered", ["end-remastered", "endrem"], "endrem", ""),
    ("ruins", "Explorer's Compass", ["explorers-compass"], "explorers-compass", ""),
    ("ruins", "Xaero's Minimap", ["xaeros-minimap"], "xaeros-minimap", ""),
    ("ruins", "Xaero's World Map", ["xaeros-world-map"], "xaeros-world-map", ""),
    ("settlement", "MineColonies", [], "245506", "open:town; NeoForge 1.21.1 builds are CurseForge-only"),
    ("library", "Structurize", [], "298744", "for MineColonies"),
    ("library", "BlockUI", [], "522992", "for MineColonies"),
    ("library", "Domum Ornamentum", [], "527361", "for MineColonies"),
    ("library", "Multi-Piston", [], "303278", "for MineColonies"),
    ("settlement", "Supplementaries", ["supplementaries"], "supplementaries", ""),
    ("settlement", "Waystones", ["waystones"], "waystones", ""),
    ("settlement", "Traveler's Backpack", ["travelersbackpack"], "travelers-backpack", ""),
    ("settlement", "Sophisticated Storage", ["sophisticated-storage"], "sophisticated-storage", ""),
    ("settlement", "Carry On", ["carry-on"], "carry-on", ""),
    ("travel", "Horseman", ["horseman"], None, ""),
    ("travel", "Horse Combat Controls", ["horse-combat-controls"], None, ""),
    ("travel", "AstikorCarts Redux", ["astikorcarts-redux", "astikor-carts-redux"], "astikorcarts-redux", ""),
    ("travel", "Trotting Wagons", ["trotting-wagons"], None, ""),
    ("travel", "Via Romana", ["via-romana"], None, ""),
    ("travel", "Faster Paths", ["faster-paths", "fasterpaths"], None, ""),
    ("travel", "Small Ships", ["small-ships"], "small-ships", ""),
    ("travel", "Immersive Aircraft", ["immersive-aircraft"], "immersive-aircraft", ""),
    ("travel", "Elytra Tuning", ["elytra-tuning"], None, ""),
    ("tech", "Create", ["create"], "create", ""),
    ("tech", "Alloyed", ["alloyed"], None, ""),
    ("tech", "Steam 'n' Rails", ["create-steam-n-rails"], "create-steam-n-rails", ""),
    ("tech", "Create Aeronautics", ["create-aeronautics"], None, ""),
    ("tech", "Create Propulsion", ["create-propulsion"], None, ""),
    ("tech", "Create Big Cannons", ["create-big-cannons"], "create-big-cannons", ""),
    ("tech", "Create Crafts & Additions", ["createaddition"], "createaddition", ""),
    ("tech", "Create Enchantment Industry", ["create-enchantment-industry"], None, ""),
    ("tech", "Create: Numismatics", ["numismatics", "create-numismatics"], None, ""),
    ("tech", "Simple Radio", ["simple-radio"], None, ""),
    ("tech", "Immersive Engineering", ["immersiveengineering", "immersive-engineering"], "immersive-engineering", ""),
    ("tech", "Create: The Factory Must Grow", ["create-tfmg", "tfmg"], None, ""),
    ("tech", "PneumaticCraft: Repressurized", ["pneumaticcraft-repressurized"], "pneumaticcraft-repressurized", ""),
    ("tech", "Applied Energistics 2", ["ae2"], "applied-energistics-2", ""),
    ("tech", "Mekanism", ["mekanism"], "mekanism", ""),
    ("tech", "Mekanism Generators", ["mekanism-generators"], "mekanism-generators", ""),
    ("tech", "Create Nuclear", ["create-nuclear"], None, ""),
    ("weave", "Ars Nouveau", ["ars-nouveau"], "ars-nouveau", ""),
    ("weave", "Iron's Spells 'n Spellbooks", ["irons-spells-n-spellbooks"], "irons-spells-n-spellbooks", ""),
    ("weave", "Occultism", ["occultism"], "occultism", ""),
    ("weave", "Goety", ["goety"], "goety", ""),
    ("realms", "The Twilight Forest", ["the-twilight-forest"], "the-twilight-forest", ""),
    ("realms", "The Aether", ["aether"], "aether", ""),
    ("realms", "The Undergarden", ["the-undergarden"], "the-undergarden", ""),
    ("realms", "Deeper and Darker", ["deeperdarker"], "deeperdarker", ""),
    ("realms", "Eternal Starlight", ["eternal-starlight"], "eternal-starlight", ""),
    ("realms", "The Bumblezone", ["the-bumblezone"], "the-bumblezone-forge", ""),
    ("realms", "L_Ender's Cataclysm", ["l_enders-cataclysm", "lenders-cataclysm"], "l_enders-cataclysm", ""),
    ("realms", "Cataclysm Dimension", ["cataclysm-dimension"], None, ""),
    ("realms", "Dimensional Dungeons", ["dimensional-dungeons"], "dimensional-dungeons", ""),
    ("realms", "Gateways to Eternity", ["gateways-to-eternity"], "gateways-to-eternity", ""),
    ("wild", "Cobblemon", ["cobblemon"], "cobblemon", ""),
    ("wild", "Cobblemon Fight or Flight Reborn", ["cobblemon-fight-or-flight-reborn"], None, ""),
    ("wild", "Cobblemon Mount Mastery", ["cobblemon-mount-mastery", "mount-mastery"], None, ""),
    ("combat", "Epic Fight", ["epic-fight"], "epic-fight-mod", ""),
    ("combat", "Better Combat", ["better-combat"], "better-combat-by-daedelus", ""),
    ("combat", "Combat Roll", ["combat-roll"], "combat-roll", ""),
    ("combat", "Shield Expansion", ["shield-expansion"], None, ""),
    ("combat", "Simply Swords", ["simply-swords"], "simply-swords", ""),
    ("combat", "Apotheosis", ["apotheosis"], "apotheosis", ""),
    ("combat", "Apothic Enchanting", ["apothic-enchanting"], "apothic-enchanting", ""),
    ("combat", "Artifacts", ["artifacts"], "artifacts", ""),
    ("combat", "Relics", ["relics-mod", "relics"], "relics-mod", ""),
    ("combat", "Bosses of Mass Destruction", ["bosses-of-mass-destruction"], None, ""),
    ("combat", "Bosses'Rise", ["bosses-rise", "bossesrise"], None, ""),
    ("combat", "Multiplayer Bosses", ["multiplayer-bosses"], None, ""),
    ("combat", "Dungeon Difficulty", ["dungeon-difficulty"], None, ""),
    ("combat", "Paladins & Priests", ["paladins-and-priests"], None, ""),
    ("character", "Neo Origins", ["neo-origins", "neoorigins"], None, ""),
    ("creatures", "Alex's Mobs Continued", ["alexs-mobs-continued", "alexs-mobs"], None, ""),
    ("creatures", "Naturalist", ["naturalist"], "naturalist", ""),
    ("creatures", "Friends & Foes", ["friends-and-foes"], "friends-and-foes-forge", ""),
    ("creatures", "Mowzie's Mobs", ["mowzies-mobs"], "mowzies-mobs", ""),
    ("creatures", "Illager Invasion", ["illager-invasion"], "illager-invasion", ""),
    ("creatures", "Enderman Overhaul", ["enderman-overhaul"], None, ""),
    ("creatures", "Ice and Fire CE", ["ice-and-fire-ce", "iceandfire-ce"], None, ""),
    ("havoc", "The Hordes", ["the-hordes", "hordes"], "the-hordes", ""),
    ("havoc", "Enhanced Celestials", ["enhanced-celestials"], "enhanced-celestials", ""),
    ("havoc", "Weather, Storms & Tornadoes", ["weather-storms-tornadoes"], "weather-storms-tornadoes", ""),
    ("perf", "Lithium", ["lithium"], None, ""),
    ("perf", "ModernFix", ["modernfix"], "modernfix", ""),
    ("perf", "FerriteCore", ["ferrite-core"], "ferritecore", ""),
    ("perf", "ServerCore", ["servercore"], None, ""),
    ("perf", "Noisium", ["noisium"], None, ""),
    ("perf", "Structure Layout Optimizer", ["structure-layout-optimizer"], None, ""),
    ("perf", "spark", ["spark"], "spark", ""),
    ("perf", "Chunky", ["chunky"], "chunky-pregenerator-forge", ""),
    ("client", "Sodium", ["sodium"], None, ""),
    ("client", "Iris", ["iris"], None, ""),
    ("client", "Distant Horizons", ["distanthorizons"], "distant-horizons", ""),
    ("client", "Entity Culling", ["entityculling"], "entityculling", ""),
    ("client", "ImmediatelyFast", ["immediatelyfast"], "immediatelyfast", ""),
    ("client", "EMI", ["emi"], "emi", ""),
    ("client", "Jade", ["jade"], "jade", ""),
    ("client", "AppleSkin", ["appleskin"], "appleskin", ""),
    ("client", "Mouse Tweaks", ["mouse-tweaks"], "mouse-tweaks", ""),
    ("ui", "FancyMenu", ["fancymenu"], "fancymenu", ""),
    ("ui", "Drippy Loading Screen", ["drippy-loading-screen"], "drippy-loading-screen", ""),
    ("ui", "Modpack Core Essentials", ["modpack-core-essentials"], None, ""),
    ("ui", "Tips", ["tips"], "tips", ""),
    ("ui", "Legendary Tooltips", ["legendary-tooltips"], "legendary-tooltips", "alt:tooltips"),
    ("ui", "Obscure Tooltips", ["obscure-tooltips"], "obscure-tooltips", "alt:tooltips"),
    ("ui", "Food Effect Tooltips", ["food-effect-tooltips-forge", "food-effect-tooltips"], None, ""),
    ("ui", "Item Borders", ["item-borders"], "item-borders", ""),
    ("ui", "Classic and Simple Status Bars", ["cssb"], None, "alt:hud"),
    ("ui", "RPG-HUD", ["rpg-hud"], "rpg-hud", "alt:hud"),
    ("ui", "Auto HUD", ["autohud"], None, ""),
    ("ui", "Overflowing Bars", ["overflowing-bars"], "overflowing-bars", ""),
    ("ui", "Souls Message Banners", ["souls-message-banners"], None, ""),
    ("ui", "Enhanced Boss Bars", ["enhanced-boss-bars-mod", "enhanced-boss-bars"], None, ""),
    ("ui", "Loot Journal", ["loot-journal"], None, ""),
    ("ui", "Toast Control", ["toast-control"], "toast-control", ""),
    ("ui", "Better Advancements", ["better-advancements"], "better-advancements", ""),
    ("ui", "Runelic", ["runelic"], None, ""),
    # compatibility glue, from the Oct 8 audit
    ("glue", "Polymorph", ["polymorph"], None, ""),
    ("glue", "Almost Unified", [], "almost-unified", ""),
    ("glue", "Colorwheel", ["colorwheel"], None, "Iris shaders with Create's Flywheel"),
    ("glue", "Accessories Compatibility Layer", ["accessories-compat-layer"], None, "one accessory screen"),
    ("glue", "CombatEventFix", ["combateventfix"], None, "Epic Fight + Better Combat events"),
    ("glue", "Epic Fight Mod Compat", ["epic-fight-mod-compat"], None, ""),
    ("glue", "Epic Fight Weapons Compat", ["epic-fight-weapons-compat"], None, ""),
    # Epic Fight: Curios Compat Extended needs Epic Fight x Curios Compat, which is CurseForge-only; left out for now
    ("glue", "Sable: Physics Compat", ["sablecompat"], None, ""),
    ("glue", "Create Aeronautics: Compatibility", ["create-aeronautics-compatability"], None, ""),
    ("glue", "Carry On + Create Aeronautics Compat", ["carryon-aeronautics-compat"], None, ""),
    ("glue", "Jade Sable Compat", ["jade-sable-compat"], None, ""),
    # libraries that mods require but don't list on Modrinth
    ("library", "Kambrik", ["kambrik"], None, "for Bountiful"),
    ("library", "Iron's Lib", ["irons-lib"], None, "for Iron's Spells"),
    ("library", "Voidless Framework", ["voidless-framework"], None, "for Rationcraft"),
    ("library", "OctoLib", ["shatterbyte-lib"], None, "for Relics"),
    ("library", "CoroUtil", ["coroutil"], None, "for Weather, Storms & Tornadoes"),
    ("library", "YetAnotherConfigLib", ["yacl"], None, "Reliable Requiem needs 3.8.1+"),
]

CACHE = "data/cache"


def http_json(url, retries=4):
    key = os.path.join(CACHE, urllib.parse.quote(url, safe="")[:200] + ".json")
    if os.path.exists(key):
        return json.load(open(key))
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = json.load(r)
            os.makedirs(CACHE, exist_ok=True)
            json.dump(data, open(key, "w"))
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (202, 429, 500, 502, 503):
                time.sleep(6 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(3)
    return None


def mr_versions(pid):
    q = urllib.parse.urlencode({"loaders": json.dumps([LOADER]), "game_versions": json.dumps([MC])})
    vs = http_json(f"https://api.modrinth.com/v2/project/{pid}/version?{q}") or []
    vs.sort(key=lambda v: (v["version_type"] == "release", v["date_published"]), reverse=True)
    return vs


def mr_project(slug):
    return http_json(f"https://api.modrinth.com/v2/project/{slug}")


def mr_search(name):
    q = urllib.parse.urlencode({"query": name, "limit": 5,
                                "facets": json.dumps([[f"categories:{LOADER}"], [f"versions:{MC}"]])})
    d = http_json(f"https://api.modrinth.com/v2/search?{q}") or {"hits": []}
    return d["hits"]


def cf_lookup(slug):
    path = slug if slug.isdigit() else f"minecraft/mc-mods/{slug}"
    d = http_json(f"https://api.cfwidget.com/{path}")
    if not d or "files" not in d:
        return None
    files = [f for f in d["files"] if "NeoForge" in f["versions"] and MC in f["versions"]]
    files.sort(key=lambda f: (f.get("type") == "release", f["uploaded_at"]), reverse=True)
    if not files:
        return {"title": d.get("title"), "source": "curseforge", "slug": slug, "version": None}
    f = files[0]
    fid = str(f["id"])
    return {"title": d.get("title"), "source": "curseforge", "slug": slug, "version": f["display"],
            "filename": f["name"], "date": f["uploaded_at"][:10], "type": f.get("type"),
            "url": f"https://mediafilez.forgecdn.net/files/{fid[:4]}/{int(fid[4:])}/{urllib.parse.quote(f['name'])}",
            "deps": []}


def mr_entry(proj, vs):
    v = vs[0]
    f = next((f for f in v["files"] if f["primary"]), v["files"][0])
    return {"title": proj["title"], "source": "modrinth", "slug": proj["slug"], "id": proj["id"],
            "version": v["version_number"], "date": v["date_published"][:10], "type": v["version_type"],
            "filename": f["filename"], "url": f["url"], "sha1": f["hashes"].get("sha1"),
            "client_side": proj.get("client_side"), "server_side": proj.get("server_side"),
            "deps": [{"project_id": d.get("project_id"), "version_id": d.get("version_id"),
                      "type": d["dependency_type"]} for d in v.get("dependencies", [])]}


def resolve(name, slugs, cf_slug):
    for s in slugs:
        p = mr_project(s)
        if p:
            vs = mr_versions(p["id"])
            if vs:
                return mr_entry(p, vs)
    for hit in (mr_search(name) if slugs else []):
        if hit["title"].lower().replace("'", "") .startswith(name.lower().replace("'", "")[:8]):
            p = mr_project(hit["project_id"])
            vs = mr_versions(p["id"]) if p else []
            if vs:
                # found by search, not by its own slug: often a port or an add-on, so a person checks it
                return {**mr_entry(p, vs), "via": "search"}
    if cf_slug:
        c = cf_lookup(cf_slug)
        if c:
            return c
    return None


def main():
    out, seen_ids = [], {}
    for group, name, slugs, cf_slug, note in PLAN:
        r = resolve(name, slugs, cf_slug)
        row = {"group": group, "name": name, "note": note, "planned": True, **(r or {"version": None})}
        out.append(row)
        if r and r.get("id"):
            seen_ids[r["id"]] = row
        flag = "  <- found by search, check it: " + r["title"] if r and r.get("via") == "search" else ""
        print(f"{group:10} {name[:34]:34} {(r or {}).get('source', '-'):10} {(r or {}).get('version')}{flag}", flush=True)
    # required dependencies (Modrinth metadata), followed transitively
    queue = [d for row in out for d in row.get("deps", []) if d["type"] == "required"]
    while queue:
        d = queue.pop()
        pid = d.get("project_id")
        if not pid or pid in seen_ids:
            continue
        p = mr_project(pid)
        vs = mr_versions(pid) if p else []
        if not p:
            continue
        row = {"group": "dependency", "name": p["title"], "note": "", "planned": False,
               **(mr_entry(p, vs) if vs else {"title": p["title"], "slug": p["slug"], "version": None})}
        seen_ids[pid] = row
        out.append(row)
        print(f"{'dep':10} {p['title'][:34]:34} {'modrinth':10} {row.get('version')}", flush=True)
        queue += [x for x in row.get("deps", []) if x["type"] == "required"]
    json.dump(out, open("data/resolved.json", "w"), indent=1)
    missing = [r["name"] for r in out if not r.get("version")]
    print("\nresolved", sum(1 for r in out if r.get("version")), "of", len(out), "| missing:", missing)


if __name__ == "__main__":
    sys.exit(main())
