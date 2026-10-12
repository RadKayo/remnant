// Remnant's own items. Textures: kubejs/assets/remnant/textures/item (drawn by branding/src/items.py).
// Names: kubejs/assets/remnant/lang/en_us.json. Behaviour lives in server_scripts.

StartupEvents.registry('item', event => {
  // The stone-age start
  event.create('remnant:flint_shard')
  event.create('remnant:flint_hatchet', 'axe').tier('stone')

  // The Age keys: found in ruins, used to open the next Age for everyone
  event.create('remnant:gearwright_schematic').maxStackSize(1).rarity('rare')
  event.create('remnant:foundry_codex').maxStackSize(1).rarity('rare')
  event.create('remnant:aether_core').maxStackSize(1).rarity('epic')

  // Salvage from the old world
  event.create('remnant:salvaged_circuitry')
})
