// Getting around: the Hearthstone and the old waystone network.
//
// Hearthstone (the item and its channel are in startup_scripts/hearthstone.js)
//   - Everyone gets one on their first login; more are crafted from flint, cobblestone and a campfire.
//   - The hour-long cooldown is real time and survives relogs and deaths.
//   - Taking damage while channelling breaks the channel.
//
// Waystones
//   - No recipes: the only waystones are the ones the old world left behind, in villages and the wild.
//   - They can't be broken, except in creative.
//   - Every one starts dark. A Relay Kit (Age II) wakes it. The noise draws a wave of monsters, larger
//     for every player nearby and every Age past II; when the wave is dead the waystone lights for the
//     whole server, and from then on works as normal (each player still activates it once).
//   - Waystones placed in creative (the one in Remainder, say) start lit.
//   - The inventory warp button is on (config/waystones-common.toml); the mod's own cooldown and XP
//     costs apply.
// Admins: /remnant waystone wake lights the waystone you're looking at; /remnant hearth reset <players>
// clears Hearthstone cooldowns.

const NbtCompound = Java.loadClass('net.minecraft.nbt.CompoundTag')
const BoxClass = Java.loadClass('net.minecraft.world.phys.AABB')

// ---------- Hearthstone ----------
ServerEvents.recipes(event => {
  event.shaped('remnant:hearthstone', ['CFC', 'FHF', 'CFC'], {
    C: '#c:cobblestones', F: 'remnant:flint_shard', H: 'minecraft:campfire',
  }).id('remnant:hearthstone')
})

function restoreHearthCooldown(player) {
  const left = player.persistentData.getLong('remnant_hearth_ready') - Date.now()
  if (left > 0) player.addItemCooldown('remnant:hearthstone', Math.ceil(left / 50))
}

PlayerEvents.loggedIn(event => {
  const { player } = event
  if (!player.persistentData.getBoolean('remnant_hearthstone_given')) {
    player.give('remnant:hearthstone')
    player.persistentData.putBoolean('remnant_hearthstone_given', true)
  }
  restoreHearthCooldown(player)
})
PlayerEvents.respawned(event => restoreHearthCooldown(event.player))

EntityEvents.afterHurt(event => {
  const p = event.entity
  if (!p.isPlayer() || !p.isUsingItem() || p.useItem.id != 'remnant:hearthstone') return
  p.stopUsingItem()
  p.statusMessage = Text.of('The channel breaks.').gray()
})

// ---------- Waystones ----------
const WAYSTONES = 'waystones:waystones'

ServerEvents.recipes(event => {
  event.remove({ mod: 'waystones' })
  event.remove({ output: '@waystones' })
  event.shaped('remnant:relay_kit', ['PAP', 'GCG', 'BAB'], {
    P: 'minecraft:ender_pearl', A: 'minecraft:amethyst_shard', G: '#c:ingots/gold',
    C: 'remnant:salvaged_circuitry', B: 'minecraft:stone_bricks',
  }).id('remnant:relay_kit')
})

// State per waystone, in server.persistentData.remnant_waystones, keyed by dimension and lower-half
// position: { state: 'waking' | 'lit', tag: the wave's entity tag, since: game time the wave began }
function waystoneData(server) {
  const data = server.persistentData
  if (!data.contains('remnant_waystones')) data.put('remnant_waystones', new NbtCompound())
  return data.getCompound('remnant_waystones')
}

function waystoneKey(block) {
  const y = String(block.properties.get('half')) === 'upper' ? block.y - 1 : block.y
  return `${block.dimension}|${block.x},${y},${block.z}`
}

function parseKey(key) {
  const parts = key.split('|')
  const xyz = parts[1].split(',').map(Number)
  return { dim: parts[0], x: xyz[0], y: xyz[1], z: xyz[2] }
}

function waystoneState(server, key) {
  const all = waystoneData(server)
  return all.contains(key) ? String(all.getCompound(key).getString('state')) : 'dark'
}

function playersNear(level, w, radius) {
  let n = 0
  level.players.forEach(p => { if (p.distanceToSqr(w.x + 0.5, w.y, w.z + 0.5) < radius * radius) n++ })
  return n
}

function tellNear(level, w, radius, text) {
  level.players.forEach(p => { if (p.distanceToSqr(w.x + 0.5, w.y, w.z + 0.5) < radius * radius) p.tell(text) })
}

function runAt(server, dim, command) {
  server.runCommandSilent(`execute in ${dim} run ${command}`)
}

function lightWaystone(server, key, quiet) {
  const entry = new NbtCompound()
  entry.putString('state', 'lit')
  waystoneData(server).put(key, entry)
  if (quiet) return
  const w = parseKey(key)
  runAt(server, w.dim, `particle minecraft:end_rod ${w.x + 0.5} ${w.y + 1.5} ${w.z + 0.5} 0.3 1 0.3 0.05 80`)
  runAt(server, w.dim, `playsound minecraft:block.beacon.activate block @a ${w.x} ${w.y} ${w.z} 1.5 1`)
  const level = server.getLevel(w.dim)
  if (level) tellNear(level, w, 64, Text.of('The waystone wakes. It will carry you now.').color(0xe8d9b5))
}

// The wave: what comes, by Age
const HELMET = '{id:"minecraft:leather_helmet",count:1}'
const WAVE = [
  { age: 2, mob: 'zombie', nbt: `ArmorItems:[{},{},{},${HELMET}]` },
  { age: 2, mob: 'husk', nbt: '' },
  { age: 2, mob: 'skeleton', nbt: `HandItems:[{id:"minecraft:bow",count:1},{}],ArmorItems:[{},{},{},${HELMET}]` },
  { age: 3, mob: 'stray', nbt: `HandItems:[{id:"minecraft:bow",count:1},{}],ArmorItems:[{},{},{},${HELMET}]` },
  { age: 3, mob: 'witch', nbt: '' },
  { age: 4, mob: 'vindicator', nbt: 'HandItems:[{id:"minecraft:iron_axe",count:1},{}]' },
  { age: 4, mob: 'pillager', nbt: 'HandItems:[{id:"minecraft:crossbow",count:1},{}]' },
]

function isOpen(level, x, y, z) {
  const block = level.getBlock(x, y, z)
  return block.blockState.getCollisionShape(level, block.pos).isEmpty() && block.blockState.getFluidState().isEmpty()
}

// Solid ground with two blocks of air above, near height y0
function groundNear(level, x, y0, z) {
  for (let dy = 4; dy >= -4; dy--) {
    let y = y0 + dy
    if (!isOpen(level, x, y - 1, z) && isOpen(level, x, y, z) && isOpen(level, x, y + 1, z)) return y
  }
  return null
}

function spawnWave(server, level, w, tag) {
  const age = remnantAge(server)
  const roster = WAVE.filter(m => m.age <= age)
  const count = Math.min(14, 2 + 2 * Math.max(1, playersNear(level, w, 32)) + Math.max(0, age - 2))
  let spawned = 0
  for (let tries = 0; tries < count * 4 && spawned < count; tries++) {
    let angle = Math.random() * Math.PI * 2
    let r = 7 + Math.random() * 6
    let x = Math.floor(w.x + Math.cos(angle) * r)
    let z = Math.floor(w.z + Math.sin(angle) * r)
    let y = groundNear(level, x, w.y, z)
    if (y === null) continue
    let m = roster[Math.floor(Math.random() * roster.length)]
    let nbt = `{Tags:["remnant_wave","${tag}"],PersistenceRequired:1b${m.nbt ? ',' + m.nbt : ''}}`
    runAt(server, w.dim, `summon minecraft:${m.mob} ${x + 0.5} ${y} ${z + 0.5} ${nbt}`)
    spawned++
  }
  return spawned
}

function wakeWaystone(server, level, key, player) {
  const w = parseKey(key)
  const data = server.persistentData
  const id = data.getInt('remnant_wave_next') + 1
  data.putInt('remnant_wave_next', id)
  const tag = `remnant_wave_${id}`
  const entry = new NbtCompound()
  entry.putString('state', 'waking')
  entry.putString('tag', tag)
  entry.putLong('since', level.levelData.gameTime)
  waystoneData(server).put(key, entry)
  level.spawnLightning(w.x + 0.5, w.y + 2, w.z + 0.5, true)
  runAt(server, w.dim, `particle minecraft:electric_spark ${w.x + 0.5} ${w.y + 1.5} ${w.z + 0.5} 0.4 1 0.4 0.2 60`)
  spawnWave(server, level, w, tag)
  tellNear(level, w, 48, Text.of(`${player.username} fits the relay. The waystone hums, and something out there heard it.`).gold())
}

// Checked every two seconds while anyone is near: the waystone lights once its wave is dead, or after
// ten minutes if something wandered off for good.
const WAVE_TIMEOUT = 12000
ServerEvents.tick(event => {
  const server = event.server
  if (server.tickCount % 40 !== 0) return
  const all = waystoneData(server)
  const keys = []
  all.getAllKeys().forEach(k => keys.push(String(k)))
  keys.forEach(key => {
    const entry = all.getCompound(key)
    if (String(entry.getString('state')) !== 'waking') return
    const w = parseKey(key)
    const level = server.getLevel(w.dim)
    if (!level || playersNear(level, w, 48) === 0) return
    const tag = String(entry.getString('tag'))
    let left = 0
    level.getEntitiesWithin(new BoxClass(w.x - 64, w.y - 32, w.z - 64, w.x + 64, w.y + 32, w.z + 64))
      .forEach(e => { if (e.isAlive() && e.tags.contains(tag)) left++ })
    if (left === 0 || level.levelData.gameTime - entry.getLong('since') > WAVE_TIMEOUT) lightWaystone(server, key, false)
  })
})

// Right-clicking a waystone. This listens to NeoForge's event directly: KubeJS's BlockEvents.rightClicked
// is skipped while the held item is on cooldown, which would let a recharging Hearthstone or a
// just-thrown ender pearl walk straight into a dark waystone's menu.
const RightClickBlock = Java.loadClass('net.neoforged.neoforge.event.entity.player.PlayerInteractEvent$RightClickBlock')
const InteractionResult = Java.loadClass('net.minecraft.world.InteractionResult')

function refuse(event) {
  event.setCancellationResult(InteractionResult.FAIL)
  event.setCanceled(true)
}

function onWaystoneClick(event) {
  const level = event.level
  if (level.isClientSide()) return
  const block = level.getBlock(event.pos)
  if (!block.hasTag(WAYSTONES)) return
  const player = event.entity
  const server = level.server
  const key = waystoneKey(block)
  const state = waystoneState(server, key)
  if (state === 'lit' || player.isCreative()) return
  refuse(event)
  if (String(event.hand) !== 'MAIN_HAND') return
  const item = event.itemStack
  if (state === 'waking') {
    player.statusMessage = Text.of('The waystone is still waking. Something is still out there.').gray()
  } else if (item.id != 'remnant:relay_kit') {
    player.statusMessage = Text.of('This waystone is dark. A Relay Kit could wake it.').gray()
  } else if (remnantAge(server) < 2) {
    player.statusMessage = Text.of(`Age II: ${AGES[2].name}. Not yet.`).gray()
  } else {
    wakeWaystone(server, level, key, player)
    item.count--
  }
}

// (Rhino rejects const declarations inside a try block, hence the separate function.)
NativeEvents.onEvent(RightClickBlock, event => {
  try {
    onWaystoneClick(event)
  } catch (e) {
    console.error(`Waystone click: ${e}`)
  }
})

BlockEvents.broken(event => {
  const { player, block, server } = event
  if (!block.hasTag(WAYSTONES)) return
  if (player && player.isCreative()) {
    waystoneData(server).remove(waystoneKey(block))
    return
  }
  if (player) player.statusMessage = Text.of('It won\'t budge.').gray()
  event.cancel()
})

BlockEvents.placed(event => {
  const { player, block, server } = event
  if (player && player.isCreative() && block.hasTag(WAYSTONES)) lightWaystone(server, waystoneKey(block), true)
})

ServerEvents.commandRegistry(event => {
  const { commands: Commands, arguments: Arguments } = event
  event.register(Commands.literal('remnant')
    .then(Commands.literal('hearth').requires(s => s.hasPermission(2))
      .then(Commands.literal('reset').then(Commands.argument('players', Arguments.PLAYERS.create(event)).executes(ctx => {
        const players = Arguments.PLAYERS.getResult(ctx, 'players')
        players.forEach(p => {
          p.persistentData.remove('remnant_hearth_ready')
          p.cooldowns.removeCooldown(Item.of('remnant:hearthstone').item)
        })
        return players.size()
      }))))
    .then(Commands.literal('waystone').requires(s => s.hasPermission(2))
      .then(Commands.literal('wake').executes(ctx => {
        const player = ctx.source.playerOrException
        const hit = player.pick(8, 0, false)
        if (String(hit.type) !== 'BLOCK') return 0
        const block = player.level.getBlock(hit.blockPos)
        if (!block.hasTag(WAYSTONES)) {
          ctx.source.sendFailure(Text.of('Look at a waystone.'))
          return 0
        }
        lightWaystone(ctx.source.server, waystoneKey(block), false)
        return 1
      }))))
})
