// Guns from the first day: the Create: Gunsmithing flintlock is made by hand in Age I, from iron
// ingots instead of Create's plates and alloy (its own recipe still works once Create opens in Age II).
// Its paper cartridges need lead, gunpowder and paper, all within reach of a stone-age camp.
// Later guns are locked by Age in ages.js; every projectile's range is capped in datapacks/remnant_guns.

ServerEvents.recipes(event => {
  event.shaped('cgs:flintlock', ['IIF', '  L'], {
    I: '#c:ingots/iron', F: 'minecraft:flint_and_steel', L: '#c:stripped_logs',
  }).id('remnant:flintlock_by_hand')
})
