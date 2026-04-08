# Game Mechanics Reference

Compiled from wiki data and verified game knowledge. Items marked [wiki-gap] were filled from general Into the Breach knowledge because the wiki scrape returned empty data; verify these against authoritative sources.

---

## Turn Structure

Each mission consists of 4-5 turns. Each turn follows this sequence:

1. **Player Phase**: Move and attack with each of 3 mechs (any order). Each mech may move once, then use one weapon. A mech cannot move after attacking. Repair is used in place of attacking.
2. **Attack Order Resolution** (after player ends turn):
   1. Fire damage (burning units take 1 damage -- units at 1 HP die before enemy attacks execute)
   2. Healing effects (Technician pilot passive, Blood Psion regeneration)
   3. Environmental effects and enemy attacks (interleaved in the order displayed in the Attack Order indicator)
   4. Vek spawn (emerge from spawn tiles -- blocked by any unit on the tile, dealing 1 damage to the blocker)
   5. Psion passive effects
3. **Telegraph Phase**: Surviving Vek and newly emerged Vek reposition and telegraph their next-turn attacks.

### Important Timing Rules

- Fire damage happens BEFORE enemy attacks. A burning 1 HP Vek dies before it can attack.
- Environmental effects (air strikes, lightning, conveyor belts, etc.) execute as part of the interleaved Attack Order, typically before most enemy attacks.
- Conveyor belts push during the environment step.
- Smoke cancels attacks for enemies that END their turn on a smoke tile.
- Blocked spawns deal 1 damage to the blocker but do NOT kill the Vek. The Vek tries again next turn.
- The player always acts first with perfect information about all telegraphed attacks.

---

## Terrain Types

| Terrain | Traversable (Ground) | Traversable (Flying) | Blocks Projectiles | Key Effect |
|---------|---------------------|---------------------|-------------------|------------|
| Ground | Yes | Yes | No | Default tile, no special effect |
| Water | No (kills non-massive) | Yes | No | Drowns non-massive non-flying units; submerges massive units |
| Mountain | No | No (can fly over, cannot land) | Yes | 2 HP obstacle; first hit = Damaged Mountain, second hit = Rubble (ground) |
| Building | No | No | Yes | 1 HP; losing buildings reduces Grid Power; Grid Defense % chance to resist |
| Forest | Yes | Yes | No | Catches fire when the tile takes weapon damage |
| Sand | Yes | Yes | No | Creates smoke when hit by weapon damage (not push/fire) |
| Ice | Yes | Yes | No | 2-step destruction: Intact -> Cracked -> Water. Fire skips to Water instantly |
| Lava | No (kills non-massive) | Yes | No | Like water but also sets surviving massive units on fire |
| Chasm | No (kills ALL non-flying) | Yes | No | Instant death for ALL non-flying units, including massive |
| Conveyor Belt | Yes | Yes | No | Pushes any unit 1 tile in belt direction during environment step |
| A.C.I.D. Pool | Yes | Yes | No | Applies A.C.I.D. status to any unit stopping on it; consumed after one use |
| Teleporter Pad | Yes | Yes | No | Teleports unit to paired pad; if destination occupied, units swap |
| Fire Tile | Yes | Yes | No | Sets units on fire that enter or end turn on it |
| Smoke Tile | Yes | Yes | No | Units in smoke cannot attack or repair; cancels enemy attacks |
| Cracked Ground | Yes | Yes | No | Becomes Chasm if damaged again |
| Spawn Tile | Yes | Yes | No | Indicates where Vek will emerge; can be blocked |

### Terrain Details

**Water**
- Non-flying, non-massive ground units pushed or moved into water drown instantly.
- Massive units (all player Mechs, boss Vek) survive but are submerged and cannot attack or repair.
- Flying units hover over water with no effect.
- Extinguishes fire on units that enter.
- Freezing water creates an Ice Tile.
- If a unit with A.C.I.D. drowns in water, the tile becomes an A.C.I.D. Pool.

**Mountain**
- Blocks both movement and projectile line of fire for ground and flying units.
- Flying units can fly OVER mountains but cannot land on them.
- Takes 2 hits to destroy regardless of damage per hit.
- Instant-kill attacks (e.g., lightning, air strikes) destroy even undamaged mountains in one hit.
- Pushing a unit into a mountain deals 1 bump damage to the pushed unit.
- Mountains can be shielded.
- Mountain Rubble functions as normal ground.

**Building**
- 1 HP -- any damage destroys the building (unless Grid Defense triggers or building is shielded/frozen).
- Grid Defense gives a % chance to resist damage (see Grid Defense section).
- Multiple buildings can exist on one tile (1, 2, or rarely 3 Grid Power per tile). When damaged, ALL buildings on that tile are destroyed at once.
- Buildings block movement for both ground and flying units.
- Buildings block projectile line of fire (like mountains).
- Buildings are immune to fire damage (fire does not destroy them but can set the tile on fire).
- Buildings can be frozen -- frozen buildings are invincible; any damage breaks the ice but not the building.
- Pushing a unit into a building deals bump damage to BOTH the pushed unit AND the building (1 damage each). Building damage costs grid power. (Empirically verified in v1.2.93 — wiki sources claiming buildings are immune are incorrect.)

**Forest**
- Catches fire when the tile itself takes weapon damage (not push/bump damage to a unit standing on it).
- A unit standing on a forest that is simultaneously damaged and pushed off will NOT be set on fire.
- Forest Fire tile sets any unit on fire that ends its turn on it.
- Freezing a Forest Fire tile reverts it to a regular Forest.

**Sand**
- Only WEAPON damage converts sand to smoke. Push damage, collision damage, and fire damage do NOT cause smoke.
- If hit with a fire attack, sand converts to a Fire Tile instead of Smoke.
- Lightning environmental effect also converts sand to smoke.
- Found primarily on R.S.T. Corporation island.

**Ice**
- Two-step destruction: Intact Ice -> Cracked Ice -> Water Tile.
- Fire effects instantly convert Ice to Water, skipping the cracked stage.
- Freezing cracked ice restores it to intact ice.
- Freezing water creates ice.
- Found primarily on Pinnacle Robotics island.

**Lava**
- Behaves like water for drowning purposes -- kills non-flying non-massive ground units instantly.
- NOT simply "traversable with fire damage." It drowns non-massive ground units.
- Surviving units (massive/mechs) are submerged AND set on fire.
- Flying units hover over lava safely.
- Falling Rocks environmental effect converts lava to normal ground.
- Appears on the Volcanic Hive (final mission).

**Chasm**
- Instant kill for ALL non-flying units, INCLUDING massive units and boss Vek. Unlike water/lava, the Massive trait does NOT protect from chasms.
- Shields do NOT protect against chasm death.
- Mechs that fall into chasms are lost entirely (no disabled mech left behind).
- Flying units hover safely over chasms.
- Created by Cracked Ground tiles being damaged, Seismic Activity environmental effect, and Cataclysm mechanic.
- Found commonly on R.S.T. Corporation island.

**Conveyor Belt**
- Pushes any unit (including flying units) one tile in the belt's direction during the environment step of the Attack Order phase.
- Found on Detritus Disposal island.
- Push direction is fixed and visually marked on the tile.

**A.C.I.D. Pool**
- Inflicts A.C.I.D. status on any unit (including flying) that stops on this tile.
- Consumed after one use -- reverts to ground after inflicting A.C.I.D.
- Flying units ARE affected (unlike water/lava).
- Found on Detritus Disposal island.

**Teleporter Pad**
- Come in two pairs (4 pads total -- blue pair and red pair).
- Units voluntarily ending movement on a pad OR pushed onto a pad are teleported to the paired pad.
- If the destination pad is occupied, the two units swap positions.
- Found on Detritus Disposal island (note: NOT Pinnacle despite its tech theme).

---

## Status Effects

### Fire
- **Effect**: Unit takes 1 damage at the START of each turn (during Attack Order, before enemy attacks).
- **Persists** until removed.
- **Applied by**: Fire attacks, fire tiles, burning forests, lava (for surviving massive/mech units).
- **Removed by**: Repairing, entering water (submerging extinguishes fire), entering smoke, being frozen.
- **Key rules**:
  - Applying fire to a frozen unit unfreezes it AND sets it on fire simultaneously.
  - Shield blocks fire application but does not remove existing fire.
  - Fire melts ice tiles instantly (skips damaged stage, goes straight to water).
  - Buildings are immune to fire damage.
  - Burrowers lose fire when they burrow underground.
  - A.C.I.D. does NOT double fire damage (fire is not weapon damage).
  - Setting a unit on fire also sets the tile on fire.

### Frozen
- **Effect**: Unit cannot move, attack, or take actions. ANY damage frees the unit (the damage itself is negated).
- **Applied by**: Cryo-Launcher, ice attacks, Freeze Mines, Ice Storm environmental effect.
- **Removed by**: Taking any damage (damage is negated), repairing (uses action to break free), fire damage (unfreezes AND catches fire).
- **Key rules**:
  - Frozen flying units are GROUNDED -- can fall into water/chasms and die.
  - Frozen enemies cannot attack (cancels their telegraphed attack).
  - Frozen units on spawn points block Vek emergence.
  - Frozen units can still be pushed by weapons.
  - Frozen units are NOT protected from instant-kill effects (chasms, Self-Destruct, environmental kills).
  - Casting shield on a frozen unit makes it both frozen AND shielded (takes 2 hits to free -- first removes shield, second unfreezes).
  - Freezing a unit on water creates an ice tile instead of the unit drowning.

### A.C.I.D. (Corroding A.C.I.D.)
- **Effect**: Doubles all WEAPON damage against the affected unit. All other damage (push, collision, fire, spawn blocking, electric smoke) is NOT doubled. Disables Armor.
- **Persists** until removed.
- **Applied by**: Centipede attacks, A.C.I.D. pool tiles, A.C.I.D. weapons.
- **Removed by**: Repairing (active repair action only -- Technician passive and Blood Psion healing do NOT remove it).
- **Key rules**:
  - Only doubles WEAPON damage. Push, collision, fire, spawn blocking damage are all unaffected.
  - A.C.I.D. DOES apply to self-damage from weapons (e.g., Unstable Cannon).
  - A.C.I.D. DOES double the bonus damage from a Boosted attacker (stacks multiplicatively).
  - Completely disables Armor while active.
  - Kills of A.C.I.D.-affected units leave acid pools on ground tiles.
  - Flying units ARE affected by A.C.I.D. Pool tiles.
  - Shield prevents A.C.I.D. application without consuming the shield.

### Smoke
- **Effect**: Units in smoke cannot attack or repair. Enemy units that END their turn on a Smoke tile have their queued attack cancelled for the entire turn.
- **Duration**: Smoke dissipates after one full turn cycle. [wiki-gap]
- **Applied by**: Smoke attacks, sand tiles hit by weapon damage, Storm Generator, various weapons.
- **Removed by**: Natural dissipation, fire (fire replaces smoke).
- **Key rules**:
  - Attack cancellation triggers for enemies that END their turn on smoke.
  - Smoke extinguishes fire tiles when applied.
  - Smoke extinguishes burning units that enter smoke tiles.
  - Storm Generator (Rusting Hulks passive) deals 1 damage to all enemies in smoke at the start of the enemy attack phase.
  - Camila Vera (pilot) is immune to smoke effects.
  - Smoke prevents satellite launches on Pinnacle.
  - Smoke does NOT prevent: explosions, Vek spawns, death-effects (like Explosive Decay).

### Webbed
- **Effect**: Unit cannot move but CAN still attack and use abilities.
- **Applied by**: Spider and Alpha Spider attacks, Spiderling web attack, Scorpion attacks.
- **Removed by**: Being pushed to an empty tile (even if captor also moves in same direction), dashing away, captor's attack being cancelled, captor dying, repairing.
- **Key rules**:
  - Camila Vera is immune to webbing.
  - Shield prevents web application.
  - Webbed mechs can still attack and use weapons -- only movement is restricted.
  - Webbed Vek can still attack from their current position.
  - Teleporter and similar weapons do NOT remove Webbed status.
  - If a webbed mech uses Teleporter/Swap, the swapped unit becomes webbed instead.

### Shield (Energy Shield)
- **Effect**: Blocks the next instance of damage AND prevents application of negative status effects (Fire, Frozen, A.C.I.D., Web). Consumed on first hit of direct damage.
- **Applied by**: Defense Mech shield, Bethany Jones ability, Mafan (Zoltan) ability, Adam pilot ability, some weapon upgrades.
- **Key rules**:
  - Shields do NOT remove existing status effects -- only prevent new ones.
  - Shields prevent fire damage from fire tiles.
  - Shields prevent A.C.I.D. application (without consuming the shield).
  - Shields prevent freezing.
  - Shields on buildings protect them from one attack.
  - Multiple shields do not stack (binary: has shield or does not).
  - CANNOT block instant-kill effects: Self-Destruct, Satellite Rocket, Supply Train ramming, Chasm death, Mosquito Leader attack, Air Bombing, Lightning Strikes.
  - Freeze Mine: shielded unit removes mine without being frozen and without losing shield.

### Armored
- **Effect**: Reduces incoming WEAPON damage by 1. Does NOT reduce push, collision, fire, spawn blocking, or electric smoke damage. Does NOT reduce self-damage.
- **Applied by**: Abe Isamu ability, Shell Psion buff (all Vek), Hook Mech natural armor, Judo Mech natural armor, Bouncer Leader natural armor, Psionic Receiver passive.
- **Key rules**:
  - Only reduces WEAPON damage from other sources.
  - Minimum 1 damage still applies -- armor doesn't negate 1-damage weapon attacks. [wiki-gap]
  - A.C.I.D. completely disables armor.
  - Multiple instances of Armored on the same unit are redundant (do not stack).
  - Also reduces Psion Tyrant's Hive Targeted damage.

### Boosted
- **Effect**: Unit's next attack deals +1 damage. Consumed on any ability use (including non-damaging abilities and repair).
- **Applied by**: Raging Psion (all Vek boosted while alive), Morgan Lejeune kills, Kai Miller full HP, stepping on fire (Heat Sinkers passive), some weapons.
- **Key rules**:
  - Affects ALL targets of an attack, including self-damage.
  - Consumed even by non-damaging abilities like shields or teleports.
  - Boosted repair heals 2 HP instead of 1.
  - A.C.I.D. doubles the Boosted bonus damage (stacks multiplicatively).
  - Deployable and spawned units (Light Tank, Arachnoid) are NOT affected by Boost.

### Stable
- **Effect**: Cannot be moved by any weapon effect (Push, Teleport, etc.).
- **Key rules**:
  - Stable units can't be pushed into other units to cause push damage.
  - Pushing other units INTO a Stable unit works as expected (both take bump damage).

### Deadly Threat
- **Effect**: The weapon or environment effect on this tile will kill any unit. Shields and Ice (Frozen) will NOT block.
- **Applied by**: Certain environmental effects (air strikes, lightning strikes, satellite rockets).

### Vek Mites
- **Effect**: Unit is infected with Vek Mites.
- **Removed by**: Damage, fire, A.C.I.D., freezing, or repairing.
- **Only appears in**: "Knock Mites off the Mechs" mission objectives. Removing all three grants 1 Reputation.

---

## Damage Types

### Weapon Damage
- The primary damage type from mech and Vek attacks.
- Affected by Armor (-1 reduction).
- Affected by A.C.I.D. (x2 multiplied).
- Affected by Boosted (+1 from attacker).
- Affected by Shield (blocked, consumes shield).
- Affected by Frozen (negated, unfreezes target).

### Push/Bump Damage
- 1 damage when a unit is pushed into an occupied tile, obstacle (mountain, building, map edge), or another unit.
- Both units take 1 damage in a collision (the pushed unit AND the obstacle unit).
- NOT affected by Armor.
- NOT affected by A.C.I.D.
- NOT doubled by Boosted.
- Blocked by Shield (consumes shield).
- A unit pushed into empty space takes no bump damage.

### Fire Damage
- 1 damage per turn at the start of Attack Order.
- NOT affected by Armor.
- NOT affected by A.C.I.D.
- Blocked by Shield (prevents fire application).
- Buildings are immune to fire damage.

### Environmental Damage
- Varies by source.
- Air strikes, lightning, satellite rockets: instant kill (Deadly Threat).
- Conveyor belt push: follows normal push rules.
- Tidal waves: drowning (follows water tile rules).
- Falling rocks, tentacles: instant kill. [wiki-gap]
- Volcanic projectiles: instant kill + fire on impact tile. [wiki-gap]

### Self-Damage
- Some weapons deal damage to the attacking mech (e.g., Unstable Cannon, Vice Fist).
- A.C.I.D. DOES apply to self-damage from weapons.
- Armor does NOT reduce self-damage.
- Boosted DOES increase self-damage.

### Spawn Blocking Damage
- 1 damage to any unit standing on a Vek spawn tile when the Vek tries to emerge.
- NOT affected by Armor, A.C.I.D., or Boosted.
- The Stabilizers passive (Steel Judoka) negates spawn blocking damage to mechs.
- Prevents the Vek from emerging; Vek tries again next turn.

---

## Push Mechanics

Pushing is one of the most critical mechanics. Many weapons push targets.

### Basic Rules
- Push moves the target 1 tile in the specified direction.
- If the target CANNOT move (wall, mountain, map edge, another unit, building), the target takes 1 bump damage instead of moving.
- If two units collide from a push, BOTH units take 1 bump damage.
- Push damage (bump/collision) is NOT affected by Armor or A.C.I.D.

### Chain Pushing
- Pushing unit A into unit B pushes BOTH units in the push direction if B has an empty tile behind it. [wiki-gap]
- If the chain cannot resolve (e.g., B is against a wall), both A and B take 1 bump damage. [wiki-gap]

### Terrain Interactions
- **Pushing into Water**: Non-massive non-flying units drown instantly. Massive units submerge.
- **Pushing into Lava**: Same as water, but surviving massive units are also set on fire.
- **Pushing into Chasms**: ALL non-flying units die, including massive units. This bypasses Massive trait.
- **Pushing into Fire Tiles**: Unit is set on fire.
- **Pushing onto Conveyor Belts**: Conveyor effect applies during environment step.
- **Pushing frozen flying units into Water/Chasms**: They die (frozen = grounded).
- **Pushing onto Teleporter Pads**: Triggers teleportation to paired pad.
- **Pushing onto A.C.I.D. Pools**: Unit gains A.C.I.D. status.

### Special Push Rules
- Stable units cannot be pushed.
- Push does NOT convert sand tiles to smoke (only weapon damage does).
- Push does NOT ignite forest tiles (only weapon damage does).
- Push damage to a unit on a sand tile does NOT create smoke.

---

## Grid Defense

### How It Works
- Each building has a percentage chance to resist any incoming damage.
- When a building would take damage, the game rolls against the Grid Defense percentage.
- If the roll succeeds, the building survives; if it fails, the building is destroyed.
- The roll uses seeded RNG -- outcomes are predetermined. Reset Turn does NOT change the outcome.

### Grid Defense Values
- **Starting value**: 15% (0% on Unfair difficulty).
- **Overpower bonus**: Each Grid Power gained when already at maximum gives +2% for the first 5 overpowered points, then +1% per point, up to +25% total from overpower.
- **Pilot bonus**: +3% per pilot with the "+3 Grid DEF" skill. Max 3 pilots = +9%.
- **Maximum total**: 49% (15% base + 25% overpower + 9% pilot). 34% on Unfair (0% base + 25% + 9%).

### Solver Guidance
- The solver should assume Grid Defense NEVER triggers (pessimistic). Treat any resist as a bonus.
- Never rely on Grid Defense to save a building.

---

## Grid Power

- Grid Power represents the power grid of civilian buildings. At 0 Grid Power, the game is lost.
- **Maximum**: 7 Grid Power.
- **Starting value**: 5 on all difficulties.
- **Losing power**: Each building destroyed reduces Grid Power by the number of buildings on that tile (1, 2, or rarely 3).
- **Gaining power**:
  - Some missions grant Grid Power as a bonus objective reward.
  - After finishing a Corporate Island, spend 1 Reputation for 1 Grid Power.
  - Perfect Island reward: can choose +2 Grid Power.
  - Grid Charger weapon: restores 1 Grid Power when used successfully.
  - On Unfair difficulty, all grid power earned from the above sources is doubled.
- **Game over**: If Grid Power reaches 0, the timeline is lost. One surviving pilot can be sent back to try again.

---

## Repair Mechanic

- Any mech can use the Repair action instead of attacking.
- Repair heals 1 HP (2 HP if Boosted).
- Repair removes Fire and A.C.I.D. status effects from the mech.
- Repair removes Webbed status.
- Repair removes Vek Mites.
- Repair can be used while Frozen (uses the action to break free). [wiki-gap]
- A mech must choose: attack OR repair. Cannot do both in the same turn.
- Smoke prevents repair (unit in smoke cannot repair).
- Mechs fully repair between missions (free, automatic).

---

## Reactor Cores

- Used for upgrading mechs. Each installed core provides 1 energy for stats, weapons, upgrades, passives, or pilot abilities.
- **Maximum per mech**: 9 reactor cores.
- **Sources**:
  - Recovering a Time Pod during a mission.
  - Completing certain bonus objectives.
  - Spending 3 Reputation after protecting a Corporate HQ.

---

## Reputation and Shop

### Earning Reputation [wiki-gap]
- Reputation is earned by completing bonus objectives during missions.
- Each island has multiple missions with optional objectives worth 1-2 Reputation each.
- Maximum earnable Reputation per island depends on which missions are chosen (typically 7-9 possible). [wiki-gap]
- Reputation is spent between islands at the shop.
- The "Good Samaritan" achievement requires earning 9 Reputation from missions on a single island.

### The Shop (Between Islands)
| Item | Cost | Description |
|------|------|-------------|
| Weapon | 1-3 Reputation | Random weapon to equip on a mech |
| Pilot | 1 Reputation | Random pilot to recruit |
| Grid Power | 1 Reputation per point | Restore 1 Grid Power |
| Reactor Core | 3 Reputation | Add reactor core to a mech (available after boss missions) |

### Shop Strategy
- Prioritize Grid Power if low.
- Reactor Cores are expensive (3 Rep) but valuable for key weapon upgrades.
- Shop inventory is random each visit.
- The "Lucky Start" achievement requires beating the game without spending any Reputation.

---

## Islands

### General Structure
- A game run consists of selecting a squad, choosing 2-4 corporate islands to liberate, then fighting the final battle on the Volcanic Hive.
- Each island has 8 regions: 1 Corporate HQ, 7 available for missions.
- Completing 4 missions triggers an attack on the Corporate HQ and locks out the remaining 3 regions.
- After liberating 2+ islands, the Volcanic Hive becomes accessible for the final battle.

### Archive, Inc. (Museum Island)
- **CEO**: Dewey Alms
- **Environment**: Temperate -- natural terrain with forests, mountains, water.
- **Unique terrain**: Abundant water, forests, mountains.
- **Environmental conditions**: Air Support (bombing runs), Tidal Waves (edge becomes water), Mines (instant kill on contact), Bad Repairs (AE -- all mechs start at 1 HP).
- **Common Vek**: Firefly, Beetle, Hornet, Leaper, Scarab.
- **Notes**: Good starting island. Tidal waves and water provide easy environmental kills. Always available at the start.

### R.S.T. Corporation (Desert Island)
- **CEO**: Jessica Kern
- **Environment**: Desert -- sand, chasms, extreme weather.
- **Unique terrain**: Sand tiles, chasms, lightning rods.
- **Environmental conditions**: Lightning Strikes (4 random tiles, instant kill), Sandstorm (AE -- row of smoke from edge), Cataclysm (row of chasms from edge), Seismic Activity (3 tiles become chasms), Erosion Points (chasms with Hornets), Windstorm (AE -- rows pushed), Evacuated Buildings (AE -- trap buildings).
- **Common Vek**: Firefly, Scorpion, Centipede, Blobber, Digger.
- **Notes**: Chasms provide instant kills. Lightning strikes are instant kills. Sand/storms add tactical options.

### Pinnacle Robotics (Ice Island)
- **CEO**: Zenith
- **Environment**: Frozen -- ice terrain, high-tech hazards.
- **Unique terrain**: Ice tiles, satellite launch pads.
- **Environmental conditions**: Ice Storm (3x3 freeze patches), Cryo-Mines (freeze on contact), Thawing Enemies (enemies start frozen, thaw over turns), Rogue Bots (1 HP AI enemies with fire attacks).
- **Common Vek**: Hornet, Beetle, Bot, Spider, Burrower.
- **Notes**: Bots add complexity. Ice tiles can be cracked into water for kills. Features Bot Leader unique boss.

### Detritus Disposal (Factory Island)
- **CEO**: Vikram Singh
- **Environment**: Industrial -- factories, recycling, A.C.I.D.
- **Unique terrain**: A.C.I.D. pools, conveyor belts, teleporter pads.
- **Environmental conditions**: Conveyor Belts (push units each turn), Teleporters (paired pads), A.C.I.D. Lakes (Vek spawn from acid, come out acidified).
- **Common Vek**: Centipede, Blobber, Moth, Beetle, Digger.
- **Notes**: A.C.I.D. pools enable massive damage combos. Conveyor belts add positioning complexity. Teleporters enable creative plays. Good for "Overkill" achievement.

### Volcanic Hive (Final Mission)
- **Accessible**: After liberating 2+ islands.
- **Unique terrain**: Lava tiles, mountains/stalagmites, Power Pylons.
- **Two phases**:
  - **Phase 1 (Surface)**: 5 turns. Power Pylons act as buildings. Super Volcano alternates between Lava Flow and Volcanic Projectiles (instant kill).
  - **Phase 2 (Underground)**: 5 turns. Protect the Renfield Bomb (4 HP) until it detonates. Caverns alternate between Falling Rocks (lava to ground) and Tentacles (ground to lava). Both deal instant-kill damage.
- **Between phases**: Disabled mechs restored. Dead pilots stay dead (replaced with AI). Limited-use items restored.
- **Renfield Bomb**: 4 HP, does NOT explode if destroyed. If destroyed, replacement deploys and timer extends by 2 turns.
- **Allowed Vek**: Firefly, Hornet, Scarab, Scorpion, Crab, Beetle, Digger, Blobber. No Advanced Edition Vek spawn here.

---

## Pilot Experience [wiki-gap]

- Pilots gain XP from kills during missions.
- XP thresholds for leveling: approximately 25 XP for Level 1, 50 XP for Level 2 (max). [wiki-gap]
- Level 1 grants a skill choice (one of two options, varies per pilot class). [wiki-gap]
- Level 2 grants a second skill choice. [wiki-gap]
- Common skills include: +1 Move, +1 HP, +2 HP, +1 Reactor, +3 Grid DEF, +1 XP per kill. [wiki-gap]
- Max level is Level 2. Three max-level pilots simultaneously earns "Best of the Best" achievement.
- The "Field Promotion" achievement requires one pilot to reach maximum level.

### XP Allocation [wiki-gap]
- Direct kill: the pilot of the attacking mech gets full XP.
- Indirect kill (drowning, chasm, environmental): XP is split among all squad pilots. [wiki-gap]

---

## Difficulty Levels

| Feature | Easy | Normal | Hard | Unfair |
|---------|------|--------|------|--------|
| Starting Grid Power | 5 | 5 | 5 | 5 |
| Grid Defense Start | 15% | 15% | 15% | 0% |
| Grid Defense Max | 49% | 49% | 49% | 34% |
| Alpha Vek | Rare | From Island 2 | From Island 1 | More frequent |
| Bot Leader | No | Yes | Yes | Yes |
| Vek Spawns | Fewer | Normal | More | Even more |
| Rare Vek | Max 1 type | 2 types on Island 4 | 2 types on Islands 3-4 | More |
| Civilians/Region | 500 | 1,000 | 1,500 | 2,000 |
| Grid Power Earned | Normal | Normal | Normal | Doubled |
| Volcanic Hive Bosses | None | None | 1 in Phase 1 | 2 per phase (3-4 islands) |

- All achievements except "Hard Victory" can be earned on Easy.
- Unfair is Advanced Edition only. Grid Defense starts at 0% but grid power earned is doubled.

---

## Psions [wiki-gap]

Psions are special Vek that provide passive buffs to all other Vek while alive. Only one Psion spawns per island. Killing the Psion removes its buff.

| Psion | Effect |
|-------|--------|
| Soldier Psion | All Vek regenerate 1 HP per turn |
| Blood Psion | All Vek heal to full HP per turn [wiki-gap] |
| Shell Psion | All Vek gain Armored status |
| Blast Psion | All Vek explode on death (Explosive Decay), dealing 1 damage to adjacent tiles |
| Smoldering Psion (AE) | All Vek gain fire immunity |
| Arachnid Psion (AE) | When any Vek dies, a Spiderling Egg spawns on the death tile |
| Raging Psion (AE) | All Vek are Boosted (+1 damage) |
| Psion Tyrant | Final boss Psion in Volcanic Hive. Uses Hive Targeted -- targets 2-3 tiles for 2 damage each turn. [wiki-gap] |

---

## Combat Edge Cases for the Solver

### Order of Operations
- Player mech actions resolve one at a time in the order the player executes them. Order matters.
- Push resolves simultaneously with the weapon attack.
- Kill effects (drowning, chasm) resolve immediately when the push happens.
- A unit killed by push/drowning before its attack phase does not attack.

### Key Solver Priorities (in order)
1. **Protect buildings** -- existential priority. No building should take damage if avoidable.
2. **Preserve Grid Power** -- each building lost drains Grid Power toward game over.
3. **Kill Vek** -- dead Vek cannot threaten next turn.
4. **Block spawns** -- prevent new Vek from entering the board.
5. **Complete bonus objectives** -- earn Reputation for shop purchases.
6. **Minimize mech damage** -- mechs repair between missions but HP matters during the mission.
7. **Position mechs well** -- central positions with good coverage for next turn.

### Threat Neutralization Options
For each building threat, the solver should consider:
1. **Kill the threatening Vek** -- removes the threat entirely.
2. **Push the Vek** -- redirect its attack to miss the building (push perpendicular to attack direction, or push to face a non-building tile).
3. **Block with mech body** -- place a mech on the threatened tile to absorb the hit instead of the building.
4. **Shield the building** -- if a shield weapon is available.
5. **Freeze the Vek** -- frozen Vek cannot attack.
6. **Smoke the Vek** -- Vek ending turn on smoke have attack cancelled.
7. **Drown/chasm the Vek** -- push into water, lava, or chasm for instant kill.

### Common Mistakes to Avoid
- Forgetting that push damage is NOT affected by Armor or A.C.I.D.
- Assuming Massive units die in water (they submerge, only chasms kill them).
- Forgetting frozen flying units are grounded and can drown/fall.
- Not accounting for chain push collisions.
- Forgetting that smoke only cancels attacks if the enemy ENDS its turn on smoke (not just passes through).
- Assuming Grid Defense will save a building (always plan as if it will fail).
- Forgetting forest/sand tile conversion rules with push vs. weapon damage.
- Not considering environmental effects in the Attack Order interleave.

---

## Mission Structure

### Turn Count
- Standard missions: 4-5 turns. [wiki-gap]
- Train missions: Always 4 turns.
- Tidal Wave missions: Always 4 turns.
- Sandstorm/Cataclysm missions (AE): Always 4 turns.
- Volcanic Hive phases: 5 turns each.

### Time Pods
- Time Pods appear during missions, dropping onto random tiles.
- Islands 1-2: Always 1 Time Pod per island.
- Islands 3-4: Always 2 Time Pods per island.
- Strange Pod: 15% chance of replacing a Time Pod on islands 2, 3, or 4.
- Reward: Always grants a Reactor Core. May also contain a Pilot, Weapon, or Passive equipment.
- Must collect with a mech or protect until end of mission. Allied units pushed onto it can also collect.
- Cannot appear in missions with "Protect the Corporate Tower" objective.
- Destroyed by: Vek ending turn on it, Vek dying on it, direct attacks, fire on tile, tile becoming chasm/water.
- NOT destroyed by: Smoke, Ice Storm, Vek running over without stopping, projectiles passing over.

### Perfect Island
- Complete an island with ALL bonus objectives fulfilled and no objectives failed.
- Time Pod objectives count -- a destroyed pod counts as failed.
- Reward choices: New pilot, new weapon/passive, or +2 Grid Power.
- Required for "Perfect Strategy" achievement (10 perfect islands cumulative).
