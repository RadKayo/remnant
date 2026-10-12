// The Hearthstone: a way home, once an hour.
//
// Sneak and right-click a lit campfire or a Cold Sweat hearth with it to bind it there (a plain
// right-click works on a campfire too). Then hold right-click anywhere for ten seconds to return,
// from any dimension. Each player gets one on their first login, and more can be crafted.
// The hour is real time: server_scripts/travel.js keeps it across relogs and deaths, gives the first
// stone, and breaks the channel when the player takes damage. The binding lives on the stone itself,
// so a stone handed to a friend takes them to your fire.

const HearthPos = Java.loadClass('net.minecraft.core.BlockPos')
const CampfireBlock = Java.loadClass('net.minecraft.world.level.block.CampfireBlock')

const HEARTH_CHANNEL = 200 // ticks: ten seconds
const HEARTH_COOLDOWN = 72000 // ticks: one hour
const HEARTH_BLOCKS = ['cold_sweat:hearth_bottom', 'cold_sweat:hearth_top']
const STAND_OFFSETS = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1], [2, 0], [-2, 0], [0, 2], [0, -2]]

function isHearth(level, pos) {
  const state = level.getBlockState(pos)
  return CampfireBlock.isLitCampfire(state) || HEARTH_BLOCKS.indexOf(String(state.block.id)) >= 0
}

// The hearth the player is looking at, if any
function targetedHearth(level, player) {
  const hit = player.pick(5, 0, false)
  if (String(hit.type) !== 'BLOCK') return null
  return isHearth(level, hit.blockPos) ? hit.blockPos : null
}

function boundHearth(stack) {
  const data = stack.customData
  if (!data || !data.contains('hearth_dim')) return null
  return { dim: data.getString('hearth_dim'), x: data.getInt('hearth_x'), y: data.getInt('hearth_y'), z: data.getInt('hearth_z') }
}

function dimensionId(level) {
  return String(level.dimension) // KubeJS's getter: the dimension's id
}

// Run a command in a level's dimension (server.runCommandSilent always runs in the overworld)
function runIn(level, command) {
  level.server.runCommandSilent(`execute in ${dimensionId(level)} run ${command}`)
}

function bindHearth(stack, level, pos, player) {
  const data = stack.customData
  data.putString('hearth_dim', dimensionId(level))
  data.putInt('hearth_x', pos.x)
  data.putInt('hearth_y', pos.y)
  data.putInt('hearth_z', pos.z)
  stack.setCustomData(data)
  const where = dimensionId(level) === 'minecraft:overworld' ? '' : ` (${dimensionId(level).split(':')[1].replace(/_/g, ' ')})`
  stack.setLore([Text.of(`Bound to a hearth at ${pos.x}, ${pos.y}, ${pos.z}${where}`).gray().italic(false)])
  player.statusMessage = Text.of('The stone warms. It will bring you back here.').color(0xe8d9b5)
  runIn(level, `playsound minecraft:block.respawn_anchor.charge player @a ${pos.x} ${pos.y} ${pos.z} 0.6 1.4`)
}

function isOpen(level, pos) {
  const state = level.getBlockState(pos)
  return state.getCollisionShape(level, pos).isEmpty() && state.getFluidState().isEmpty()
}

// Somewhere to stand beside the hearth (on top of a campfire would burn)
function standingSpot(level, hearth) {
  for (let i = 0; i < STAND_OFFSETS.length; i++) {
    for (let dy = 0; dy <= 2; dy++) {
      let feet = hearth.offset(STAND_OFFSETS[i][0], dy === 2 ? -1 : dy, STAND_OFFSETS[i][1])
      let floor = feet.below()
      if (isOpen(level, feet) && isOpen(level, feet.above()) && !level.getBlockState(floor).getCollisionShape(level, floor).isEmpty()) {
        return feet
      }
    }
  }
  return hearth.above()
}

function recall(stack, level, player) {
  const bound = boundHearth(stack)
  if (!bound) return
  const dest = level.server.getLevel(bound.dim)
  const hearth = new HearthPos(bound.x, bound.y, bound.z)
  if (!dest || !isHearth(dest, hearth)) {
    player.statusMessage = Text.of('Your hearth has gone cold. Relight it, or bind the stone somewhere else.').gray()
    return
  }
  const spot = standingSpot(dest, hearth)
  runIn(level, `particle minecraft:reverse_portal ${player.x} ${player.y + 1} ${player.z} 0.4 0.8 0.4 0.05 60`)
  runIn(level, `playsound minecraft:block.beacon.deactivate player @a ${player.x} ${player.y} ${player.z} 0.8 1.2`)
  level.server.runCommandSilent(`execute in ${bound.dim} run tp ${player.username} ${spot.x + 0.5} ${spot.y} ${spot.z + 0.5}`)
  runIn(dest, `particle minecraft:flame ${spot.x + 0.5} ${spot.y + 1} ${spot.z + 0.5} 0.4 0.8 0.4 0.02 30`)
  runIn(dest, `playsound minecraft:block.respawn_anchor.set_spawn player @a ${spot.x} ${spot.y} ${spot.z} 0.8 1.2`)
  player.addItemCooldown(stack.item, HEARTH_COOLDOWN)
  player.persistentData.putLong('remnant_hearth_ready', Date.now() + HEARTH_COOLDOWN * 50)
}

// Right-click: bind if aimed at a hearth, otherwise start the channel if the stone is bound
function startUse(level, player, stack) {
  const hearth = targetedHearth(level, player)
  if (hearth) {
    if (!level.isClientSide()) bindHearth(stack, level, hearth, player)
    return false
  }
  if (!boundHearth(stack)) {
    if (!level.isClientSide()) player.statusMessage = Text.of('It has no hearth yet. Sneak and right-click a lit campfire or a hearth with it.').gray()
    return false
  }
  if (!level.isClientSide()) runIn(level, `playsound minecraft:block.beacon.ambient player @a ${player.x} ${player.y} ${player.z} 1 1.6`)
  return true
}

// An error inside an item callback kicks the player, so log it instead
function safely(fallback, fn) {
  try {
    return fn()
  } catch (e) {
    console.error(`Hearthstone: ${e}`)
    return fallback
  }
}

StartupEvents.registry('item', event => {
  event.create('remnant:hearthstone').maxStackSize(1).rarity('uncommon')
    .tooltip(Text.of('Bind it at a lit campfire or a hearth. Hold use to return there, once an hour.').gray())
    .useAnimation('bow')
    .useDuration(() => HEARTH_CHANNEL)
    .use((level, player, hand) => safely(false, () => startUse(level, player, player.getItemInHand(hand))))
    .finishUsing((stack, level, entity) => {
      if (!level.isClientSide() && entity.isPlayer()) safely(null, () => recall(stack, level, entity))
      return stack
    })
})
