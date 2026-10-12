// The Ages: technology returns in five eras, opened for the whole server at once.
//
// Each Age is an AStages server-scope stage (age_2 .. age_5); Age I is the start and needs no stage.
// Opening an Age also raises every player's Apotheosis World Tier, sets the #age score the city's
// restoration functions read, and runs remnant:core/age<n> if the city datapack is installed.
//
// How each Age opens:
//   II   Hearths      the first winter ends (Serene Seasons)
//   III  Steam        someone uses a Gearwright Schematic, found in ruins
//   IV   Industry     someone uses a Foundry Codex
//   V    Reclamation  someone uses an Aether Core
// Admins: /remnant age, /remnant age open <n>, /remnant age reset <n> (testing only).

const AGES = [
  null,
  { name: 'Embers', tier: 'haven' },
  { name: 'Hearths', tier: 'frontier' },
  { name: 'Steam', tier: 'ascent' },
  { name: 'Industry', tier: 'summit' },
  { name: 'Reclamation', tier: 'pinnacle' },
]
const NUMERALS = ['', 'I', 'II', 'III', 'IV', 'V']

// What each Age unlocks. Everything listed is locked until the server reaches that Age: it can't be
// used, placed, mined, equipped or crafted, and it's hidden in EMI. It can still be picked up and
// stored, so a find from a ruin isn't lost.
const LOCKS = {
  2: {
    mods: ['create', 'alloyed', 'brewinandchewin', 'vinery', 'brewery', 'herbalbrews', 'bakery', 'farm_and_charm',
      'farmersrespite', 'cookingforblockheads', 'cuisinedelight', 'astikorcartsredux', 'trotting_wagons', 'via_romana'],
    items: [
      'minecraft:iron_pickaxe', 'minecraft:iron_axe', 'minecraft:iron_shovel', 'minecraft:iron_hoe', 'minecraft:iron_sword',
      'minecraft:iron_helmet', 'minecraft:iron_chestplate', 'minecraft:iron_leggings', 'minecraft:iron_boots',
      'minecraft:brewing_stand',
      'farmersdelight:cooking_pot', 'farmersdelight:skillet', 'farmersdelight:stove', 'farmersdelight:cutting_board',
      'cgs:revolver', 'cgs:shotgun', 'cgs:round_revolver', 'cgs:round_revolver_blank', 'cgs:round_shotgun',
      'cgs:round_shotgun_blank', 'cgs:round_shotgun_flechette', 'cgs:flintlock_long_barrel', 'cgs:flintlock_chambers',
      'cgs:blunderbuss_barrel', 'cgs:blunderbuss_barrel_long', 'cgs:scope',
      'remnant:relay_kit',
    ],
  },
  3: {
    mods: ['railways', 'aeronautics', 'offroad', 'simulated', 'createpropulsion', 'createbigcannons', 'createaddition', 'create_enchantment_industry',
      'immersive_aircraft', 'smallships', 'simpleradio', 'explorerscompass', 'toxony', 'rationcraft', 'sliceanddice',
      'create_central_kitchen'],
    items: [
      'minecraft:diamond_pickaxe', 'minecraft:diamond_axe', 'minecraft:diamond_shovel', 'minecraft:diamond_hoe',
      'minecraft:diamond_sword', 'minecraft:diamond_helmet', 'minecraft:diamond_chestplate', 'minecraft:diamond_leggings',
      'minecraft:diamond_boots',
      'create:steam_engine', 'create:steam_whistle', 'create:blaze_burner', 'create:track', 'create:track_station',
      'create:track_signal', 'create:track_observer', 'create:controls', 'create:schedule', 'create:railway_casing',
      'cgs:gatling', 'cgs:nailgun', 'cgs:launcher', 'cgs:blazegun', 'cgs:hammer', 'cgs:frag_grenade',
      'cgs:round_gatling', 'cgs:round_gatling_blank', 'cgs:round_gatling_piercing', 'cgs:round_revolver_piercing',
      'cgs:round_shotgun_incendiary', 'cgs:round_shotgun_flechette_steel', 'cgs:rocket', 'cgs:rocket_small',
    ],
  },
  4: {
    mods: ['immersiveengineering', 'tfmg', 'pneumaticcraft', 'computercraft', 'immersivecooking', 'reactive'],
    items: [
      'minecraft:netherite_pickaxe', 'minecraft:netherite_axe', 'minecraft:netherite_shovel', 'minecraft:netherite_hoe',
      'minecraft:netherite_sword', 'minecraft:netherite_helmet', 'minecraft:netherite_chestplate',
      'minecraft:netherite_leggings', 'minecraft:netherite_boots',
    ],
  },
  5: {
    mods: ['ae2', 'mekanism', 'mekanismgenerators', 'createnuclear', 'appliedcooking', 'potion_blending'],
    items: [],
  },
}

function itemExists(id) {
  try { return !Item.of(id).isEmpty() } catch (e) { return false }
}

const lockMessage = age => () => Text.of(`Age ${NUMERALS[age]}: ${AGES[age].name}. Not yet.`).gray()

function keep(restriction, age) {
  // Finds can be carried and stored; nothing else
  return restriction.allowPickup().allowInventoryStorage().allowContainerStorage()
    .useMessage(lockMessage(age)).placeMessage(lockMessage(age))
}

// (A function, not a bare loop: Rhino rejects const declarations inside top-level loops.)
function lockAge(age) {
  const stage = `age_${age}`
  LOCKS[age].mods.forEach(mod => {
    if (Platform.isLoaded(mod)) keep(AStages.addRestrictionForMod(`remnant/age${age}/${mod}`, stage, mod), age)
  })
  const items = LOCKS[age].items.filter(itemExists)
  if (items.length) keep(AStages.addRestrictionForItem(`remnant/age${age}/items`, stage, items), age)
}
;[2, 3, 4, 5].forEach(lockAge)

// ---------- state ----------
function remnantAge(server) {
  let age = 1
  for (let n = 2; n <= 5; n++) if (AStages.serverHasStage(`age_${n}`, server)) age = n
  return age
}

function syncPlayer(server, player) {
  const age = remnantAge(server)
  server.runCommandSilent(`apoth set_world_tier ${player.username} ${AGES[age].tier}`)
}

function syncScore(server) {
  server.runCommandSilent('scoreboard objectives add remnant dummy')
  server.runCommandSilent(`scoreboard players set #age remnant ${remnantAge(server)}`)
}

// Open the next Age for everyone. Returns false if it isn't next.
function remnantOpenAge(server, age, opener) {
  if (age !== remnantAge(server) + 1) return false
  AStages.addStageToServer(`age_${age}`, false, false, false)
  syncScore(server)
  server.runCommandSilent(`function remnant:core/age${age}`)
  server.players.forEach(p => syncPlayer(server, p))
  server.runCommandSilent('title @a times 20 100 30')
  server.runCommandSilent(`title @a subtitle {"text":"${AGES[age].name.toUpperCase()}","color":"gold"}`)
  server.runCommandSilent(`title @a title {"text":"AGE ${NUMERALS[age]}","color":"#e8d9b5","bold":true}`)
  server.runCommandSilent('playsound minecraft:ui.toast.challenge_complete master @a')
  server.tell(Text.of(opener ? `${opener} has opened Age ${NUMERALS[age]}: ${AGES[age].name}.`
    : `Age ${NUMERALS[age]}: ${AGES[age].name} has begun.`).gold())
  return true
}

ServerEvents.loaded(event => syncScore(event.server))
PlayerEvents.loggedIn(event => syncPlayer(event.server, event.player))

// ---------- Age II: the first winter ends ----------
const SeasonHelper = Java.loadClass('sereneseasons.api.season.SeasonHelper')

ServerEvents.tick(event => {
  const server = event.server
  if (server.tickCount % 1200 !== 0 || remnantAge(server) >= 2) return
  const season = String(SeasonHelper.getSeasonState(server.overworld()).getSeason())
  const data = server.persistentData
  if (season === 'WINTER') data.putBoolean('remnant_winter_seen', true)
  else if (data.getBoolean('remnant_winter_seen') && season === 'SPRING') remnantOpenAge(server, 2, null)
})

// ---------- Ages III to V: keys found in ruins ----------
const KEYS = {
  'remnant:gearwright_schematic': 3,
  'remnant:foundry_codex': 4,
  'remnant:aether_core': 5,
}

Object.keys(KEYS).forEach(id => {
  ItemEvents.rightClicked(id, event => {
    const { server, player, item } = event
    const age = KEYS[id]
    const now = remnantAge(server)
    if (now >= age) {
      player.statusMessage = Text.of(`Age ${NUMERALS[age]} is already open.`).gray()
    } else if (now < age - 1) {
      player.statusMessage = Text.of('The pages make no sense yet. Something has to come before this.').gray()
    } else if (remnantOpenAge(server, age, player.username)) {
      item.count--
    }
    event.cancel()
  })
})

// ---------- admin ----------
ServerEvents.commandRegistry(event => {
  const { commands: Commands } = event
  const IntegerArgumentType = Java.loadClass('com.mojang.brigadier.arguments.IntegerArgumentType')
  event.register(Commands.literal('remnant')
    .then(Commands.literal('age')
      .executes(ctx => {
        const age = remnantAge(ctx.source.server)
        ctx.source.sendSystemMessage(Text.of(`Age ${NUMERALS[age]}: ${AGES[age].name}`))
        return age
      })
      .then(Commands.literal('open').requires(s => s.hasPermission(2))
        .then(Commands.argument('age', IntegerArgumentType.integer(2, 5)).executes(ctx => {
          const age = IntegerArgumentType.getInteger(ctx, 'age')
          return remnantOpenAge(ctx.source.server, age, null) ? 1 : 0
        })))
      .then(Commands.literal('reset').requires(s => s.hasPermission(2))
        .then(Commands.argument('age', IntegerArgumentType.integer(1, 5)).executes(ctx => {
          const server = ctx.source.server
          const age = IntegerArgumentType.getInteger(ctx, 'age')
          for (let n = 2; n <= 5; n++) {
            if (n <= age) AStages.addStageToServer(`age_${n}`, false, false, false)
            else AStages.removeStageFromServer(`age_${n}`, false, false, false)
          }
          syncScore(server)
          server.players.forEach(p => syncPlayer(server, p))
          return age
        })))))
})
