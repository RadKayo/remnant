// The stone-age start: the Remnant begin with flint and fire.
//
// The first hour goes like this:
//   - Break leaves for sticks (they drop more often than in vanilla).
//   - Dig gravel by hand for flint.
//   - Knap the flint: right-click stone with it to strike off flint shards.
//   - Two shards and a stick make a Flint Hatchet, the only way to fell a tree.
//   - Three shards and two sticks make a stone pickaxe (a flint pick). After that, stone tools as usual.
// Logs can't be broken without an axe, and there are no wooden tools at all.

ServerEvents.tags('item', event => {
  event.add('minecraft:axes', 'remnant:flint_hatchet')
})

const WOODEN_TOOLS = ['wooden_pickaxe', 'wooden_axe', 'wooden_shovel', 'wooden_hoe', 'wooden_sword']

ServerEvents.recipes(event => {
  WOODEN_TOOLS.forEach(t => event.remove({ output: `minecraft:${t}` }))
  event.shapeless('remnant:flint_hatchet', ['2x remnant:flint_shard', 'minecraft:stick']).id('remnant:flint_hatchet')
  event.shaped('minecraft:stone_pickaxe', ['FFF', ' S ', ' S '], { F: 'remnant:flint_shard', S: 'minecraft:stick' })
    .id('remnant:flint_pick')
})

// No punching trees
BlockEvents.broken(event => {
  const { player, block } = event
  if (!player || player.isCreative() || !block.hasTag('minecraft:logs')) return
  if (player.mainHandItem.hasTag('minecraft:axes')) return
  player.statusMessage = Text.of('Too tough to break by hand. You need an axe; flint will do.').gray()
  event.cancel()
})

// Knapping: strike flint against stone for shards
const KNAPPING_STONE = ['minecraft:base_stone_overworld', 'c:cobblestones', 'c:stones']

BlockEvents.rightClicked(event => {
  const { player, block, item, hand, server } = event
  if (String(hand) !== 'MAIN_HAND' || item.id != 'minecraft:flint') return
  if (!KNAPPING_STONE.some(tag => block.hasTag(tag))) return
  item.count--
  const shards = Math.random() < 0.7 ? 2 : 1
  player.give(Item.of('remnant:flint_shard', shards))
  server.runCommandSilent(`execute in ${block.dimension} run playsound minecraft:block.stone.hit block @a ${block.x} ${block.y} ${block.z} 1 ${(0.8 + Math.random() * 0.4).toFixed(2)}`)
  event.cancel()
})

// More sticks from leaves and more flint from gravel, so nobody is stuck at the start
BlockEvents.broken(event => {
  const { player, block } = event
  if (!player || player.isCreative()) return
  if (block.hasTag('minecraft:leaves') && !player.mainHandItem.hasTag('c:tools/shear') && Math.random() < 0.2) {
    block.popItem(Item.of('minecraft:stick'))
  } else if (block.id == 'minecraft:gravel' && Math.random() < 0.15) {
    block.popItem(Item.of('minecraft:flint'))
  }
})
