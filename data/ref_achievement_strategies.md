# Achievement Strategies

Reference for the bot's achievement strategist layer. Each entry describes the exact
unlock condition, the recommended approach, and how to configure the solver's
evaluation weights when targeting that achievement.

---

## Already Completed

- [x] Victory (50.1%) -- Beat the game (any length)
- [x] Watery Grave (68.1%) -- Drown 3 enemies in water in a single battle (Rift Walkers)
- [x] Emerging Technologies (63.6%) -- Unlock a new Mech Squad
- [x] Perfect Island (61.3%) -- Do not fail any objective on a single Corporate Island
- [x] The Defenders (49.8%) -- Finish a Corporate Island without taking Building Damage
- [x] Immovable Objects (41.7%) -- Block 100 Vek across all games (cumulative)
- [x] Sustainable Energy (39.1%) -- Finish 3 Corporate Islands without dropping below 4 Grid Power
- [x] Plus 2 more (likely Island Secure and Field Promotion -- verify with user)

---

## Tier 1: Green Zone (>40% global unlock -- Natural Play)

### Island Secure (75.1%)
- **Requirement:** Complete the first Corporate Island with the Rift Walkers squad.
- **Squad:** Rift Walkers (required)
- **Strategy:** Play normally. Complete any 2 missions on the first island, then beat the island boss. The squad is the starter squad with no unlock needed.
- **Bot approach:** Standard solver play, no special weights needed. Just complete the first island.
- **Key weapons:** Titan Fist, Taurus Cannon, Artemis Artillery (all defaults)
- **Ideal setup:** Normal difficulty, first island, any CEO
- **Estimated difficulty for bot:** Easy

### Field Promotion (73.2%)
- **Requirement:** Have a Pilot reach maximum level.
- **Squad:** Any
- **Strategy:** Pilots gain XP from kills, completing missions, and completing objectives. A pilot reaches max level (experienced -> veteran -> elite) over roughly 2 islands of consistent play. Keep the same pilot alive across missions.
- **Bot approach:** No special solver weights. Just play competently and keep pilots alive. The bot should avoid trading pilots between mechs unnecessarily.
- **Key pilots:** Any starting pilot; time-traveled pilot with existing XP is faster
- **Ideal setup:** Normal difficulty, 3-4 island run for enough missions
- **Estimated difficulty for bot:** Easy

### Friends in High Places (49.8%)
- **Requirement:** Spend 50 Reputation across all games (cumulative).
- **Squad:** Any
- **Strategy:** Reputation is earned from bonus objectives and spent in shops between islands. Simply spend reputation on upgrades, weapons, grid power, etc. Accumulates across all runs.
- **Bot approach:** Always spend reputation in shops rather than hoarding. No solver changes needed.
- **Ideal setup:** Any, just keep playing runs
- **Estimated difficulty for bot:** Easy (cumulative, will happen naturally)

### Come Together (44.7%)
- **Requirement:** Unlock 6 additional Pilots.
- **Squad:** Any
- **Strategy:** Pilots are found in Time Pods during missions. Collect time pods across runs. Each new pilot found counts. Also unlocked by traveling a pilot to a new timeline.
- **Bot approach:** Add moderate weight to collecting time pods during missions. The solver should prioritize picking up pods when safe.
- **Ideal setup:** Any difficulty, multi-run cumulative
- **Estimated difficulty for bot:** Easy (cumulative across runs)

### Best of the Best (43.9%)
- **Requirement:** Have 3 Pilots at maximum level simultaneously.
- **Squad:** Any
- **Strategy:** This requires all 3 mech pilots to reach max level in the same run. Requires a longer run (3-4 islands) and distributing kills so no one pilot hogs all XP. All three must reach elite rank.
- **Bot approach:** Distribute kills across mechs. The solver should slightly prefer kill opportunities for under-leveled pilots. Track pilot XP and balance accordingly.
- **Key pilots:** Start with experienced time-traveler pilot for a head start
- **Ideal setup:** Normal difficulty, 4-island run to guarantee enough XP for all three
- **Estimated difficulty for bot:** Easy-Medium

### Good Samaritan (41.7%)
- **Requirement:** Earn 9 Reputation from missions on a single Corporate Island.
- **Squad:** Any
- **Strategy:** Each mission has a bonus objective worth 1-2 reputation, plus building protection reputation. On a single island with enough missions, complete all bonus objectives. A perfect island with 4+ missions should yield 9+ reputation.
- **Bot approach:** Heavily weight bonus objective completion. The solver should treat bonus objectives almost as importantly as building protection.
- **Ideal setup:** Normal difficulty, pick an island with 4 missions and bonus objectives that are achievable (kill X enemies, protect buildings, etc.)
- **Estimated difficulty for bot:** Easy-Medium

---

## Tier 2: Yellow Zone (20-40% -- Requires Specific Squad Play)

### Perfect Battle (36.4%)
- **Requirement:** Take no Mech or Building Damage in a single battle with the Rusting Hulks squad. Repaired damage still counts.
- **Squad:** Rusting Hulks (required)
- **Strategy:** Smoke cancels Vek attacks entirely. Use Jet Mech to drop smoke on every threatening Vek. Use Pulse Mech to push Vek out of attack range. Choose an easy first-island mission with 2-3 enemies.
- **Bot approach:** Set building_damage and mech_damage weights to maximum (essentially infinite penalty). Heavily reward smoke placement on Vek tiles. Prefer canceling attacks via smoke over killing.
- **Key weapons:** Aerial Bombs (smoke), Rocket Artillery (smoke behind shooter), Repulse (push), Storm Generator (passive -- smoke damages enemies)
- **Key pilots:** Camila Vera (immune to smoke/webbing, best for this squad)
- **Ideal setup:** Normal difficulty, first island, 2-objective mission with fewest enemies
- **Estimated difficulty for bot:** Medium

### Get Over Here (33.9%)
- **Requirement:** Kill an enemy by pulling it into yourself with the Zenith Guard squad.
- **Squad:** Zenith Guard (required)
- **Strategy:** The Defense Mech has Attraction Pulse which pulls a target 1 tile toward itself. Pull a 1-HP enemy into the Defense Mech's tile to kill it via bump damage. Works best against weakened enemies or 1-HP Leapers.
- **Bot approach:** When a 1-HP enemy is adjacent-by-one to the Defense Mech, heavily reward using Attraction Pulse on it. Weaken enemies to 1 HP with Laser Mech or Charge Mech first, then pull.
- **Key weapons:** Attraction Pulse (Defense Mech), Force Amp passive (+1 bump damage makes this easier)
- **Ideal setup:** Normal difficulty, island with Leapers (1 HP naturally). Pick a mission early on first island.
- **Estimated difficulty for bot:** Medium

### Overpowered (30.7%)
- **Requirement:** Overpower your Power Grid twice by earning or buying Power when it is full with the Rusting Hulks squad.
- **Squad:** Rusting Hulks (required)
- **Strategy:** First, fill Grid Power to maximum. Then earn grid power from bonus objectives or buy it in shops when already full. Need to do this twice in the same run. Requires careful grid power management.
- **Bot approach:** Run-level planner must track grid power. Once full, seek missions with grid power rewards or save reputation to buy grid power in shop when full. The solver should complete grid-power bonus objectives when grid is already full.
- **Key weapons:** N/A (squad default)
- **Ideal setup:** Normal difficulty. Do NOT spend grid power on upgrades once full. Play defensively to avoid losing grid power. Choose bonus objectives that reward grid power.
- **Estimated difficulty for bot:** Medium

### Shield Mastery (28.5%)
- **Requirement:** Block damage with a Shield 4 times in a single battle with the Zenith Guard squad.
- **Squad:** Zenith Guard (required)
- **Strategy:** The Defense Mech has Shield Projector (2-3 uses per battle). Shield buildings or mechs that will be hit. The Charge Mech with Gain Shield upgrade also contributes. Need 4 instances of a shield absorbing damage in one battle.
- **Bot approach:** Place shields on tiles that will definitely take damage. The solver should predict which buildings/mechs will be hit and preemptively shield them. Weight shield usage that will absorb damage very highly.
- **Key weapons:** Shield Projector (Defense Mech, 2 uses base, 3 with upgrade), Spartan Shield with Gain Shield upgrade (Aegis Mech)
- **Ideal setup:** Normal difficulty, later island with more enemies attacking. Upgrade Shield Projector to +1 Use.
- **Estimated difficulty for bot:** Medium

### Ramming Speed (28.4%)
- **Requirement:** Kill an enemy 5 or more tiles away with a Dash Punch with the Rift Walkers squad.
- **Squad:** Rift Walkers (required)
- **Strategy:** The Combat Mech's Titan Fist has a Dash upgrade that lets it charge any distance before punching. The mech must start 5+ tiles away from the target and dash to kill it. Target must die from the punch (2 base damage).
- **Bot approach:** Requires Dash upgrade on Titan Fist (1 reactor core). The solver should look for enemies with 2 HP or less that are 5+ tiles in a straight line from the Combat Mech. Heavily reward this scenario.
- **Key weapons:** Titan Fist with Dash upgrade (Upgrade I)
- **Ideal setup:** Normal difficulty, first island. Get Dash upgrade ASAP. Look for long open rows/columns.
- **Estimated difficulty for bot:** Medium

### Humanity's Savior (27.8%)
- **Requirement:** Rescue 100,000 civilians across all games (cumulative).
- **Squad:** Any
- **Strategy:** Civilians are saved by protecting buildings. Each building has a population count. Play normally across many runs and this accumulates. Higher population islands yield more.
- **Bot approach:** No special solver changes. Just protect buildings. The bot prioritizing building protection (which it should always do) will naturally accumulate this.
- **Ideal setup:** Any, play many runs
- **Estimated difficulty for bot:** Easy (cumulative, long-term)

### Chain Attack (24.8%)
- **Requirement:** Have the Electric Whip attack chain through 10 tiles with the Blitzkrieg squad.
- **Squad:** Blitzkrieg (required)
- **Strategy:** The Lightning Mech's Electric Whip chains through adjacent targets. To hit 10 tiles, you need a long chain of adjacent enemies, mechs, boulders, and buildings. Place boulders from the Boulder Mech adjacent to enemy clusters. Use the Hook Mech's Grappling Hook to pull enemies into the chain. The Building Chain upgrade lets the whip pass through buildings without damage.
- **Bot approach:** Requires a later mission with many enemies (4+). The solver should set up chains by positioning boulders and mechs adjacent to enemy clusters. Heavily reward chain length. Prioritize Building Chain upgrade.
- **Key weapons:** Electric Whip with Building Chain upgrade, Rock Accelerator (place boulders as chain links), Grappling Hook (pull enemies into position)
- **Key pilots:** Silica (double shot lets Lightning Mech fire twice)
- **Ideal setup:** Normal difficulty, later island (3rd+) with many enemies. 4+ enemies plus 3 mechs plus boulders plus buildings forms the chain.
- **Estimated difficulty for bot:** Hard (requires complex positioning across multiple turns)

### Perfect Strategy (23.3%)
- **Requirement:** Collect 10 Perfect Island rewards across all games (cumulative).
- **Squad:** Any
- **Strategy:** A Perfect Island reward is given when no objectives are failed on an entire island. Play clean islands across runs.
- **Bot approach:** Weight bonus objectives highly. The bot's standard play should aim for perfect islands.
- **Ideal setup:** Normal difficulty, first island is easiest to perfect
- **Estimated difficulty for bot:** Medium (cumulative, will accumulate over runs)

### Mass Displacement (23.0%)
- **Requirement:** Push 3 enemies with a single attack with the Steel Judoka squad.
- **Squad:** Steel Judoka (required)
- **Strategy:** Cluster Artillery (Siege Mech) pushes all 4 adjacent tiles of its target. If 3+ enemies are adjacent to the target tile, they all get pushed. Need to find or create a cluster of enemies around a single tile.
- **Bot approach:** The solver should look for 3+ enemies adjacent to a single empty tile. Heavily reward firing Cluster Artillery at that tile. Use Vice Fist (Judo Mech) and Grav Well (Gravity Mech) to group enemies first.
- **Key weapons:** Cluster Artillery (Siege Mech), Vice Fist and Grav Well for positioning
- **Ideal setup:** Normal difficulty, later island with 4+ enemies. Wait for a turn where enemies cluster naturally or group them over multiple turns.
- **Estimated difficulty for bot:** Medium-Hard (requires specific enemy clustering)

### Backup Batteries (20.7%)
- **Requirement:** Earn or buy 10 Grid Power on a single Corporate Island.
- **Squad:** Any
- **Strategy:** Grid power is earned from building protection and bonus objectives, plus bought in shops. On a single island with 4 missions and a shop visit, accumulate 10 total grid power gained (even if some was lost to damage). Take bonus objectives that award grid power. Buy grid power in the island shop.
- **Bot approach:** Run-level planner should track grid power earned per island. Prioritize bonus objectives that grant grid power. Always buy grid power in shops when available on the target island.
- **Ideal setup:** Normal difficulty, 4-mission island. Take grid power rewards.
- **Estimated difficulty for bot:** Medium

### Scorched Earth (20.5%)
- **Requirement:** End a battle with 12 tiles on Fire with the Flame Behemoths squad.
- **Squad:** Flame Behemoths (required)
- **Strategy:** Use Flame Thrower (with range upgrades) and Vulcan Artillery to set tiles on fire aggressively. Fire persists for the entire battle. By the final turn, spread fire across the map. Fire does not damage buildings, so firing near buildings is safe.
- **Bot approach:** In the last 1-2 turns of a battle, the solver should maximize fire tile count. Add a large reward for tiles on fire. Both the Flame Thrower (up to 3-tile range with upgrades) and Vulcan Artillery create fire.
- **Key weapons:** Flame Thrower (range upgrades are priority), Vulcan Artillery, Teleporter (reposition to spread fire further)
- **Ideal setup:** Normal difficulty, any island. Upgrade Flame Thrower range first. In the last 2 turns of battle, focus on fire spread over kills.
- **Estimated difficulty for bot:** Medium

### I'm getting too old for this... (20.3%)
- **Requirement:** Have an individual Pilot fight the final battle 3 times across multiple games (cumulative).
- **Squad:** Any
- **Strategy:** Travel the same pilot to new timelines after beating the final battle. That pilot keeps accumulating final battle count. Requires 3 full game victories with the same pilot surviving to the end.
- **Bot approach:** Run-level planner must always time-travel the same pilot. Track which pilot has the most final battle completions. Protect that pilot above all others.
- **Ideal setup:** Normal difficulty, 2-island runs for fastest completion. Keep the designated pilot alive through the final battle.
- **Estimated difficulty for bot:** Medium (requires 3 full victories, cumulative)

### There is No Try (20.2%)
- **Requirement:** Finish 3 Corporate Islands without failing an objective.
- **Squad:** Any
- **Strategy:** Complete 3 islands in a single run without failing any bonus or main objective. This is like getting 3 Perfect Islands in one run. Requires consistently clean play.
- **Bot approach:** Weight bonus objectives very highly -- treat them almost like building protection. The solver must never sacrifice an objective.
- **Ideal setup:** Normal difficulty, pick easier bonus objectives (kill X enemies, protect buildings)
- **Estimated difficulty for bot:** Medium-Hard

---

## Tier 3: Orange Zone (10-20% -- Deliberate Setup Needed)

### Squads Victory (19.0%)
- **Requirement:** Beat the game with 4 different Squads (cumulative).
- **Squad:** Any 4 different squads
- **Strategy:** Simply beat the game 4 times, each with a different squad. The bot should cycle through squads.
- **Bot approach:** Run-level planner tracks which squads have completed victories. Select the next unfinished squad.
- **Ideal setup:** Normal difficulty, 2-island runs for fastest completion per squad
- **Estimated difficulty for bot:** Medium (requires 4 victories)

### Adaptable Victory (18.8%)
- **Requirement:** Beat the game at least once at each length: 2, 3, and 4 islands secured (cumulative).
- **Squad:** Any
- **Strategy:** Complete one run at each length. 2-island is the shortest/easiest. 4-island is the longest but gives more upgrades.
- **Bot approach:** Run-level planner tracks which lengths have been completed. Select the next unfinished length.
- **Ideal setup:** Normal difficulty. Do 2-island first (easiest), then 3, then 4.
- **Estimated difficulty for bot:** Medium (requires 3 victories)

### Cryo Expert (16.9%)
- **Requirement:** Shoot the Cryo-Launcher 4 times in a single battle with the Frozen Titans squad.
- **Squad:** Frozen Titans (required)
- **Strategy:** The Ice Mech's Cryo-Launcher freezes both itself and the target. Normally it can only fire once every other turn (because it freezes itself). To fire 4 times, the Ice Mech needs to be unfrozen each turn. Use the Mirror Mech's Janus Cannon to hit and unfreeze the Ice Mech. Or use Mafan pilot (shield prevents freeze). A 5-turn battle gives exactly enough turns if unfreezing works every turn.
- **Bot approach:** Each turn: unfreeze Ice Mech (hit with Janus Cannon or have shield), then fire Cryo-Launcher. The solver should prioritize unfreezing the Ice Mech and then using Cryo-Launcher, even if suboptimal for the board.
- **Key weapons:** Cryo-Launcher (Ice Mech), Janus Cannon (Mirror Mech, used to unfreeze)
- **Key pilots:** Mafan (Zoltan Shield prevents freeze -- best choice), Bethany Jones (shield pilot alternative)
- **Ideal setup:** Normal difficulty, first island. Mafan on Ice Mech lets it fire every turn without needing to unfreeze. 5-turn battle = 5 potential shots.
- **Estimated difficulty for bot:** Medium

### Quantum Entanglement (16.6%)
- **Requirement:** Teleport a unit 4 tiles away with the Flame Behemoths squad.
- **Squad:** Flame Behemoths (required)
- **Strategy:** The Swap Mech's Teleporter swaps its position with a target. Base range is adjacent only. Upgrade I adds +1 range (2 tiles), Upgrade II adds +2 more (4 tiles total). With both upgrades, swap with a unit 4 tiles away.
- **Bot approach:** Requires both Teleporter range upgrades (3 reactor cores for science weapon). Once upgraded, find any unit 4 tiles away and swap. The solver should heavily reward using Teleporter at max range.
- **Key weapons:** Teleporter with both range upgrades (+1 Range, +2 Range)
- **Ideal setup:** Normal difficulty, second island (need time to get 3 reactor cores for upgrades). Any mission once fully upgraded.
- **Estimated difficulty for bot:** Medium

### Pacifist (16.6%)
- **Requirement:** Kill fewer than 3 enemies in a single battle with the Frozen Titans squad.
- **Squad:** Frozen Titans (required)
- **Strategy:** Freeze enemies with Cryo-Launcher instead of killing them. Use Spartan Shield to flip attack directions rather than kill. Only kill 0-2 enemies total in the battle. Frozen enemies cannot attack, so use freezing as the primary defense.
- **Bot approach:** Heavily penalize killing enemies (invert normal kill reward). Reward freezing and pushing over killing. The solver should only kill if absolutely necessary to prevent grid damage.
- **Key weapons:** Cryo-Launcher (freeze instead of kill), Spartan Shield (flip attacks), Janus Cannon (push away)
- **Ideal setup:** Normal difficulty, first island, pick a mission with fewer spawns. Avoid "kill X enemies" bonus objectives.
- **Estimated difficulty for bot:** Medium

### This is Fine (15.7%)
- **Requirement:** Have 5 enemies on Fire simultaneously with the Flame Behemoths squad.
- **Squad:** Flame Behemoths (required)
- **Strategy:** Set enemies on fire using Flame Thrower and Vulcan Artillery. Need 5+ enemies alive and on fire at the same time. Do not kill burning enemies. Later missions with more enemies (4-5 at once) plus emerging Vek make this possible. Ignite tiles where Vek are emerging so they spawn on fire.
- **Bot approach:** In later missions, prioritize setting enemies on fire over killing them. The solver should penalize killing burning enemies and reward igniting new ones. Track simultaneous burning enemy count.
- **Key weapons:** Flame Thrower (range upgrades), Vulcan Artillery, Flame Shielding (passive -- mechs immune to fire)
- **Ideal setup:** Normal difficulty, 3rd or 4th island where 5+ enemies can be present. Ignite emerging Vek tiles pre-emptively.
- **Estimated difficulty for bot:** Medium-Hard

### Stormy Weather (15.4%)
- **Requirement:** Deal 12 damage with Electric Smoke in a single battle with the Rusting Hulks squad.
- **Squad:** Rusting Hulks (required)
- **Strategy:** The Storm Generator passive makes smoke deal 1 damage (2 with upgrade) to enemies each turn. Spread smoke aggressively over multiple turns. Each enemy standing in smoke takes damage at the start of their turn. Need to accumulate 12 total smoke damage in one 5-turn battle.
- **Bot approach:** Maximize smoke coverage on enemy tiles. The solver should prioritize placing smoke on enemies even over killing them. Track total smoke damage. Upgrade Storm Generator (+1 damage) to need fewer instances.
- **Key weapons:** Storm Generator (passive, upgraded to +1 damage), Aerial Bombs (Jet Mech, creates smoke), Rocket Artillery (creates smoke behind shooter)
- **Ideal setup:** Normal difficulty, second or third island with more enemies. Upgrade Storm Generator first. +1 Range on Jet Mech helps cover more enemies.
- **Estimated difficulty for bot:** Medium

### Healing (15.1%)
- **Requirement:** Heal 10 Mech Health in a single battle with the Hazardous Mechs squad.
- **Squad:** Hazardous Mechs (required)
- **Strategy:** Viscera Nanobots heals mechs 1 (or 2 with upgrade) HP per killing blow. The Leap Mech and Unstable Mech both deal self-damage every attack. Intentionally take self-damage, then heal by getting kills. Need 10 total healing in one battle. With +1 Heal upgrade, need 5 kills that heal. Without upgrade, need 10 kill-heals.
- **Bot approach:** Encourage self-damage attacks and then killing blows. The solver should track total healing in the battle and prioritize getting kills with damaged mechs. Upgrade +1 Heal on Viscera Nanobots first.
- **Key weapons:** Hydraulic Legs (self-damage + area damage), Unstable Cannon (self-damage + target damage), Viscera Nanobots (passive, upgrade +1 Heal)
- **Ideal setup:** Normal difficulty, second island with enough enemies. Keep attacking even when taking self-damage to maximize heal cycles.
- **Estimated difficulty for bot:** Medium

### Glittering C-Beam (14.8%)
- **Requirement:** Hit 4 enemies with a single laser with the Zenith Guard squad.
- **Squad:** Zenith Guard (required)
- **Strategy:** The Laser Mech's Burst Beam fires in a straight line, hitting multiple tiles. Need 4 enemies lined up in a row or column. Use Charge Mech and Defense Mech to push/pull enemies into line. Later missions with more enemies (4+) provide the raw material.
- **Bot approach:** The solver should look for opportunities to line up 4 enemies. Use Charge Mech (Ramming Engines pushes on hit) and Defense Mech (Attraction Pulse pulls) to position enemies in a line. Then fire Burst Beam through all 4. Requires multi-mech coordination.
- **Key weapons:** Burst Beam (Laser Mech), Ramming Engines (positioning), Attraction Pulse (positioning)
- **Ideal setup:** Normal difficulty, 3rd or 4th island with 5+ enemies. Wait for turns with many enemies on the field.
- **Estimated difficulty for bot:** Hard (requires 4 enemies in a line)

### Untouchable (14.5%)
- **Requirement:** Finish a Corporate Island without taking Mech Damage. Repaired damage still counts.
- **Squad:** Any (Rusting Hulks recommended -- smoke prevents attacks)
- **Strategy:** No mech can take any damage across an entire island (3-4 missions). Use smoke, shields, and pushing to prevent all damage to mechs. Avoid using self-damage weapons.
- **Bot approach:** Set mech_damage weight to maximum. The solver should never allow mech damage, treating it as almost as bad as building damage. Prefer smoke/shield/push over direct combat.
- **Key weapons:** Smoke weapons (Rusting Hulks), Shield Projector (Zenith Guard)
- **Key pilots:** Mafan (Zoltan Shield absorbs 1 hit per turn)
- **Ideal setup:** Normal difficulty, first island (fewer enemies). Rusting Hulks with smoke on every enemy every turn.
- **Estimated difficulty for bot:** Medium-Hard

### Unwitting Allies (14.2%)
- **Requirement:** Have 4 enemies die from enemy fire in a single battle with the Steel Judoka squad.
- **Squad:** Steel Judoka (required)
- **Strategy:** The Vek Hormones passive makes enemies deal +1 damage to each other. Push/throw enemies into each other's attack lines. Fireflies and Gastropods with ranged attacks are ideal -- redirect their fire to hit other Vek. Need 4 total enemy-on-enemy kills.
- **Bot approach:** The solver should prioritize pushing enemies into other enemies' attack paths over direct kills. Reward enemy-kills-enemy events very highly. Use Vice Fist (throw behind), Grav Well (pull into attack lines), and Cluster Artillery (push into attack lines). Penalize direct mech kills when an enemy-fire-kill is possible.
- **Key weapons:** Vice Fist (Judo Mech), Grav Well (Gravity Mech), Cluster Artillery (Siege Mech), Vek Hormones (passive +1 enemy damage)
- **Ideal setup:** Normal difficulty, later island with 4+ enemies and ranged attackers (Fireflies, Gastropods). Check attack order to plan redirections.
- **Estimated difficulty for bot:** Hard (requires complex positioning across turns)

### Hold the Line (14.0%)
- **Requirement:** Block 4 emerging Vek in a single turn with the Blitzkrieg squad.
- **Squad:** Blitzkrieg (required)
- **Strategy:** When Vek are about to emerge (ground cracks), place units on those tiles to block them. Need 4 emerging Vek blocked in one turn. Place mechs and boulders on crack tiles. The Boulder Mech's Rock Accelerator places a boulder on a tile, blocking spawns.
- **Bot approach:** Wait for a turn with 4+ emerging Vek. The solver should place all 3 mechs on crack tiles and launch a boulder onto the 4th. Heavily reward blocking emerging Vek. This requires 4 cracks in a single turn.
- **Key weapons:** Rock Accelerator (Boulder Mech, places boulder to block), Grappling Hook (Hook Mech, repositioning), all 3 mechs as blockers
- **Ideal setup:** Normal difficulty, later mission (turn 3-5 when many Vek try to emerge). Later islands have more spawns per turn.
- **Estimated difficulty for bot:** Hard (requires 4 simultaneous spawns, which is situational)

### Overkill (12.6%)
- **Requirement:** Deal 8 damage to a unit with a single attack with the Hazardous Mechs squad.
- **Squad:** Hazardous Mechs (required)
- **Strategy:** The Unstable Cannon deals 2 base + upgrades. With both damage upgrades (+1 each to self and target, +1 to target) it reaches 4 damage. Apply A.C.I.D. (doubles damage) with Nano Mech first, then shoot with Unstable Cannon for 8 damage. Alternatively, the Leap Mech can also reach high damage with A.C.I.D.
- **Bot approach:** Apply A.C.I.D. to target first (Nano Mech), then shoot with fully upgraded Unstable Cannon. The solver should identify A.C.I.D. targets and heavily reward the overkill combo. Needs Unstable Cannon fully upgraded (4 damage base) + A.C.I.D. (doubles to 8).
- **Key weapons:** A.C.I.D. Projector (Nano Mech), Unstable Cannon fully upgraded (4 damage), Viscera Nanobots (offset self-damage)
- **Key pilots:** Morgan Lejeune or Kai Miller on Unstable Mech for +1 damage (reaches 5 base, 10 with A.C.I.D.) [needs-verification on whether boost applies before A.C.I.D. doubling]
- **Ideal setup:** Normal difficulty, second or third island. Need both Unstable Cannon upgrades + A.C.I.D. combo.
- **Estimated difficulty for bot:** Medium

### Distant Friends (11.3%)
- **Requirement:** Encounter a familiar face (find an FTL pilot in a time pod).
- **Squad:** Any
- **Strategy:** FTL pilots (Kazaaakpleth, Ariadne, Mafan) appear randomly in Time Pods. The FTL game must be owned on Steam. Keep opening time pods across runs and eventually an FTL pilot appears.
- **Bot approach:** Prioritize collecting time pods in every mission. This is RNG-dependent. No special solver changes beyond time pod collection priority.
- **Ideal setup:** Any, collect time pods every run. Requires FTL to be owned on the same Steam account. [needs-verification: confirm FTL ownership]
- **Estimated difficulty for bot:** Medium (RNG-dependent)

### Mech Specialist (11.1%)
- **Requirement:** Beat the game with 3 of the same Mech in a Custom squad.
- **Squad:** Custom (required -- 3x same mech)
- **Strategy:** Choose 3 copies of the same mech. The easiest choice is 3x Combat Mech (Titan Fist is versatile), 3x Judo Mech (armor + throw), or 3x Leap Mech (high damage + movement). Having 3 identical weapons simplifies the solver.
- **Bot approach:** Build a custom squad of 3x the same mech. The solver only needs to handle one weapon type. Recommended: 3x Combat Mech (good damage, Dash upgrade gives mobility) or 3x Judo Mech (armor, repositioning).
- **Ideal setup:** Normal difficulty, 2-island run. 3x Combat Mech recommended for simplicity.
- **Estimated difficulty for bot:** Medium-Hard

### Lightning War (10.5%)
- **Requirement:** Finish the first 2 Corporate Islands in under 30 minutes with the Blitzkrieg squad.
- **Squad:** Blitzkrieg (required)
- **Strategy:** Speed run the first 2 islands. Take only required missions (2 per island + boss fight). Make decisions fast, skip animations, and play aggressively. The Electric Whip can clear enemies quickly.
- **Bot approach:** The bot must minimize think time. Use shorter search depths. Skip non-essential missions. End turns immediately after making moves. The 30-minute timer is real-time, so solver speed matters.
- **Key weapons:** Electric Whip (fast area damage), Rock Accelerator, Grappling Hook
- **Ideal setup:** Normal difficulty, 2-island run. Take the 2 easiest missions per island. Skip shop/upgrade screens quickly.
- **Estimated difficulty for bot:** Hard (real-time constraint, bot must be fast)

### Change the Odds (10.4%)
- **Requirement:** Raise Grid Defense to 30% or more with a Random squad.
- **Squad:** Random (required)
- **Strategy:** Grid Defense starts at 15% and increases by spending reputation on Grid Defense upgrades in shops. Each upgrade adds 5% or so. Need to accumulate enough upgrades across an island to reach 30%.
- **Bot approach:** Run-level planner should always buy Grid Defense upgrades in shops when using Random squad. Track Grid Defense percentage and prioritize reaching 30%.
- **Ideal setup:** Normal difficulty, 3-4 island run with Random squad to have enough shop visits.
- **Estimated difficulty for bot:** Medium

### Unbreakable (10.2%)
- **Requirement:** Have Mech Armor absorb 5 damage in a single battle with the Steel Judoka squad.
- **Squad:** Steel Judoka (required)
- **Strategy:** The Judo Mech and Hook Mech have Natural Armor (weapon damage reduced by 1). Each time armor absorbs damage, it counts. Need 5 instances of armor absorbing 1 damage each. Intentionally position armored mechs in enemy attack lines where they will be hit.
- **Bot approach:** The solver should intentionally place the Judo Mech and Hook Mech in enemy attack paths (as long as they survive). Reward absorbing damage on armored mechs. Each hit that does reduced damage counts toward the achievement.
- **Key weapons:** N/A (Natural Armor is inherent to Judo Mech and Hook Mech)
- **Ideal setup:** Normal difficulty, later island with many attacking enemies. Let armored mechs take hits intentionally.
- **Estimated difficulty for bot:** Medium-Hard (requires deliberately taking hits)

---

## Tier 4: Red Zone (<10% -- Hardest Achievements)

### Class Specialist (9.8%)
- **Requirement:** Beat the game with 3 different Mechs from the same class in a Custom squad.
- **Squad:** Custom (required -- 3 mechs of one class: Prime, Brute, Ranged, or Science)
- **Strategy:** Choose 3 different mechs of the same class. Recommended: 3 Brute mechs (varied push/damage options) or 3 Ranged mechs (artillery coverage). The challenge is that no Science class provides direct damage, and 3 Primes may lack range.
- **Bot approach:** Build custom squad with 3 mechs from the same class. Recommended: 3 Brute mechs (Cannon Mech + Hook Mech + Mirror Mech or Unstable Mech for damage variety and push options). [needs-verification: which specific combination is strongest]
- **Ideal setup:** Normal difficulty, 2-island run.
- **Estimated difficulty for bot:** Hard

### Trusted Equipment (9.7%)
- **Requirement:** Finish 3 Corporate Islands without equipping any new Pilots or weapons.
- **Squad:** Any (strong default squad recommended)
- **Strategy:** Never equip any new pilots or weapons found in time pods or shops for 3 islands. You can still buy reactor cores and grid power. Stick with starting pilots and default weapons the entire run.
- **Bot approach:** Run-level planner must never equip new pilots or weapons. Only buy reactor cores and grid power in shops. Skip weapon pickups.
- **Ideal setup:** Normal difficulty, use a squad with strong defaults (Rusting Hulks or Steel Judoka). Upgrade existing weapons only.
- **Estimated difficulty for bot:** Medium

### Immortal (9.6%)
- **Requirement:** Finish 4 Corporate Islands without a Mech being destroyed at the end of a battle with the Hazardous Mechs squad.
- **Squad:** Hazardous Mechs (required)
- **Strategy:** Despite self-damage weapons, no mech can be destroyed (0 HP at battle end) across 4 islands. Keep Nano Mech alive for Viscera Nanobots healing. Manage self-damage carefully. Avoid suicide plays.
- **Bot approach:** The solver must heavily penalize any action sequence that could result in mech death. Track mech HP carefully and never attack if it would kill a mech without a kill-heal. Keep Nano Mech alive at all costs.
- **Key weapons:** Viscera Nanobots (heal on kill), A.C.I.D. Projector (Nano Mech must survive)
- **Key pilots:** Mafan (Zoltan Shield absorbs self-damage), Abe Isamu (prevents 1 self-damage)
- **Ideal setup:** Normal difficulty, 4-island run. Get +1 Heal upgrade on Viscera Nanobots immediately. Play cautiously.
- **Estimated difficulty for bot:** Hard

### Loot Boxes! (9.4%)
- **Requirement:** Open 5 Time Pods in a single game with a Random squad.
- **Squad:** Random (required)
- **Strategy:** Time Pods appear in missions occasionally. Prioritize collecting every time pod across a 4-island run. Some missions have time pods as bonus objectives.
- **Bot approach:** Heavily weight time pod collection. The solver should always move a mech to collect time pods even at some risk. Run-level planner should pick missions that display time pods. Play a 4-island run to maximize pod opportunities.
- **Ideal setup:** Normal difficulty, 4-island run with Random squad. Collect every pod.
- **Estimated difficulty for bot:** Medium (RNG-dependent on pod spawns)

### Engineering Dropout (9.3%)
- **Requirement:** Finish 3 Corporate Islands without powering a Weapon Modification.
- **Squad:** Any
- **Strategy:** Never spend reactor cores on weapon upgrades for 3 islands. You can still power HP and movement upgrades for mechs. Use only base-level weapons.
- **Bot approach:** Run-level planner must never allocate reactor cores to weapon modifications. Only use cores for mech HP and move speed. The solver works with unmodified weapons only.
- **Ideal setup:** Normal difficulty, squad with strong base weapons (Rusting Hulks -- Storm Generator is a passive that works without powering; Aerial Bombs are effective unpowered). [needs-verification: does passive Storm Generator count as a weapon modification?]
- **Estimated difficulty for bot:** Medium-Hard

### Trick Shot (9.2%)
- **Requirement:** Kill 3 enemies with a single attack of the Janus Cannon with the Frozen Titans squad.
- **Squad:** Frozen Titans (required)
- **Strategy:** The Janus Cannon fires two projectiles in opposite directions, pushing targets. To kill 3 enemies: have enemies on both sides of the Mirror Mech (1 in each direction), plus bump kills (pushed into water, buildings, or other enemies). Need enemies at low HP or push-into-hazard setups.
- **Bot approach:** The solver should set up 3 enemies in a line (or 2 lines from Mirror Mech). Weaken them first with Aegis Mech (Spartan Shield, 2 damage) and Ice Mech (unfreeze damage). Then fire Janus Cannon to kill 3. Can also get kills from bumping into hazards. Heavily reward 3-kill Janus setups.
- **Key weapons:** Janus Cannon with +1 damage upgrades (up to 3 damage), Spartan Shield (weaken enemies), Cryo-Launcher (freeze then bump damage on unfreeze)
- **Ideal setup:** Normal difficulty, later island with many enemies. Fully upgrade Janus Cannon damage. Look for enemies near water/chasms for push-kills.
- **Estimated difficulty for bot:** Hard

### Hard Victory (9.0%)
- **Requirement:** Beat the game on Hard difficulty (any length).
- **Squad:** Any (strong squad recommended)
- **Strategy:** Hard mode has more enemies, higher HP enemies, and tougher conditions. Play a strong squad (Rusting Hulks or Steel Judoka) and use the bot's optimal play.
- **Bot approach:** Standard solver play but on Hard. May need stronger evaluation weights and deeper search. The solver should be more conservative with building protection.
- **Ideal setup:** Hard difficulty, 2-island run for shortest path to victory. Rusting Hulks recommended (smoke negates enemy strength).
- **Estimated difficulty for bot:** Hard

### Powered Blast (8.8%)
- **Requirement:** Pierce a Walking Bomb with the AP Cannon to kill an Enemy with the Bombermechs squad.
- **Squad:** Bombermechs (required)
- **Strategy:** The Pierce Mech's AP Cannon pierces the first target and damages the second. Place a Walking Bomb (from Bombling Mech) in front of an enemy, then fire AP Cannon. The shot pierces through the bomb (pushing it) and damages the enemy behind it. The enemy must die from this shot.
- **Bot approach:** The solver should set up a Walking Bomb adjacent to an enemy in a straight line from the Pierce Mech. Fire AP Cannon to pierce bomb and kill the enemy. The enemy needs low enough HP to die from 2 base damage (or more with upgrades).
- **Key weapons:** AP Cannon (Pierce Mech), Bomb Dispenser (Bombling Mech -- places Walking Bomb), Force Swap (Exchange Mech -- positioning)
- **Ideal setup:** Normal difficulty, first or second island. Weaken an enemy to 2 HP or less, place bomb in front, fire AP Cannon.
- **Estimated difficulty for bot:** Medium

### On the Backburner (8.2%)
- **Requirement:** Do 4 damage with the Reverse Thrusters with the Mist Eaters squad.
- **Squad:** Mist Eaters (required)
- **Strategy:** The Thruster Mech's Reverse Thrusters deal damage that increases with dash distance. Base: 1-2 damage (2-tile range). Upgrade I: 1-3 damage (3-tile range). Upgrade II: 1-4 damage (4-tile range). Need both range upgrades to reach 4 damage, which requires dashing the maximum 4 tiles away from the target.
- **Bot approach:** Requires both Reverse Thruster range upgrades. The solver should find targets with the Thruster Mech positioned exactly 4 tiles of open space behind it to dash to max range. Heavily reward 4-damage Reverse Thruster hits.
- **Key weapons:** Reverse Thrusters with both range upgrades (+1 Range each)
- **Ideal setup:** Normal difficulty, second or third island (need cores for both upgrades). Look for long open rows/columns.
- **Estimated difficulty for bot:** Medium

### Unstable Ground (7.9%)
- **Requirement:** Crack 10 tiles in one mission with the Cataclysm squad.
- **Squad:** Cataclysm (required)
- **Strategy:** The Cataclysm squad specializes in cracking ground tiles. The Tectonic Mech's Seismic Slam cracks tiles, the Shrapnel Mech's Cluster Bombs crack tiles, and the Prospector Mech helps with positioning. Cracking 10 tiles in one 5-turn mission requires aggressive ground-cracking every turn.
- **Bot approach:** The solver should maximize tiles cracked per turn. Weight cracked tiles heavily. Use all weapon actions to crack tiles even when not directly needed for Vek defense. [needs-verification: exact weapon mechanics for Cataclysm squad]
- **Key weapons:** Seismic Slam (Tectonic Mech), Cluster Bombs (Shrapnel Mech), Prospector tools
- **Ideal setup:** Normal difficulty, pick missions with lots of normal ground tiles (avoid water/chasm heavy maps).
- **Estimated difficulty for bot:** Medium-Hard

### Flight Specialist (7.8%)
- **Requirement:** Beat the game with 3 flying Mechs in a Custom squad.
- **Squad:** Custom (required -- 3 flying mechs)
- **Strategy:** Flying mechs include: Jet Mech (Rusting Hulks), Defense Mech (Zenith Guard), Swap Mech (Flame Behemoths), Ice Mech (Frozen Titans), Nano Mech (Hazardous Mechs), Thruster Mech (Mist Eaters), Control Mech (Mist Eaters), Napalm Mech (Heat Sinkers). Choose 3 that have complementary abilities.
- **Bot approach:** Recommended: Jet Mech (damage + smoke) + Swap Mech (repositioning) + Nano Mech (A.C.I.D. + healing passive). Or Control Mech + Ice Mech + Jet Mech for crowd control. [needs-verification: confirm all flying mechs available]
- **Ideal setup:** Normal difficulty, 2-island run with Custom squad of 3 flyers.
- **Estimated difficulty for bot:** Hard

### Lucky Start (7.3%)
- **Requirement:** Beat the game (any length) without spending any Reputation with a Random squad.
- **Squad:** Random (required)
- **Strategy:** Never spend reputation in shops. No buying weapons, pilots, grid power, or reactor cores from shops. Only use what you find in time pods and mission rewards. Hoard all reputation.
- **Bot approach:** Run-level planner must never spend reputation. Skip all shop purchases. The solver must work with default/found equipment only.
- **Ideal setup:** Normal difficulty, 2-island run for shortest path. Random squad gives unpredictable mechs.
- **Estimated difficulty for bot:** Hard (no upgrades from shops + random squad)

### Complete Victory (7.2%)
- **Requirement:** Beat the game with all 10 primary Squads (cumulative).
- **Squad:** All 10 primary squads (Rift Walkers through Hazardous Mechs), one run each
- **Strategy:** Beat the game once with each of the 10 primary squads. Cumulative across all runs.
- **Bot approach:** Run-level planner tracks which squads have completed victories. Cycle through all 10.
- **Ideal setup:** Normal difficulty, 2-island runs for fastest completion per squad.
- **Estimated difficulty for bot:** Medium-Hard (requires 10 victories total)

### Stay With Me! (7.2%)
- **Requirement:** Heal 12 damage over the course of a single Island with the Mist Eaters squad.
- **Squad:** Mist Eaters (required)
- **Strategy:** Nanofilter Mending heals mechs that stand on smoke tiles. Spread smoke aggressively and position damaged mechs on smoke. Intentionally take damage (let mechs get hit) then heal on smoke. Need 12 total HP healed across all missions on one island.
- **Bot approach:** The solver should allow some mech damage when smoke healing is available. Track total healing per island. Position damaged mechs on smoke tiles even at some tactical cost. Use Reverse Thrusters (self-damage + creates smoke) and Smoldering Shells (creates smoke) to create healing opportunities.
- **Key weapons:** Nanofilter Mending (passive), Reverse Thrusters (self-damage + smoke), Smoldering Shells (creates smoke)
- **Ideal setup:** Normal difficulty, an island with 3-4 missions. Let mechs take incidental damage and heal frequently.
- **Estimated difficulty for bot:** Medium-Hard

### Chronophobia (6.7%)
- **Requirement:** Finish 3 Corporate Islands and destroy every Time Pod discovered.
- **Squad:** Any
- **Strategy:** When a Time Pod appears in a mission, it must be destroyed (let enemies or your attacks hit it) rather than collected. This means intentionally ignoring or destroying pods for 3 full islands.
- **Bot approach:** The solver should target time pods for destruction. When a pod appears, fire a weapon at it or allow enemy attacks to destroy it. Penalize collecting pods. Do NOT walk mechs onto pod tiles.
- **Ideal setup:** Normal difficulty, any squad. 3-island run.
- **Estimated difficulty for bot:** Medium (counterintuitive for the bot which normally collects pods)

### Spider Breeding (6.7%)
- **Requirement:** Spawn 15 Arachnoids in one Island with the Arachnophiles squad.
- **Squad:** Arachnophiles (required)
- **Strategy:** The Arachnoid Mech creates an Arachnoid on each kill. Need 15 kills with the Arachnoid Injector across one island (3-4 missions). Average 4-5 Arachnoid kills per mission. Use Ricochet Rocket and Arachnoids themselves to weaken enemies, then finish with Arachnoid Injector.
- **Bot approach:** The solver should give kill priority to the Arachnoid Mech. Weaken enemies with Ricochet Rocket (Bulk Mech) and Arachnoid damage, then finish with Arachnoid Injector. Track total Arachnoids spawned per island. Upgrade Arachnoid Injector damage to make kills easier.
- **Key weapons:** Arachnoid Injector (must get killing blow), Ricochet Rocket (weaken targets)
- **Key pilots:** Kai Miller or Morgan Lejeune on Arachnoid Mech (+1 damage for easier kills), Silica (double shot for 2 kills per turn)
- **Ideal setup:** Normal difficulty, pick an island with Leapers (1 HP, easy Arachnoid kills) or Pinnacle Robotics (robots to destroy). 4-mission island.
- **Estimated difficulty for bot:** Medium-Hard

### Let's Walk (5.8%)
- **Requirement:** Move Enemies with Control Shot 120 spaces in one game with the Mist Eaters squad.
- **Squad:** Mist Eaters (required)
- **Strategy:** Control Shot moves an enemy a short distance (base 2 tiles, up to 4 with upgrades). Need to accumulate 120 total tiles of enemy movement across an entire game. With 4-tile movement per use and ~20 missions, need about 6 uses per mission at max range.
- **Bot approach:** The solver should use Control Shot every turn at maximum range on enemies. Upgrade Control Shot movement (+1 Move twice) to reach 4-tile moves. Track cumulative enemy movement. Reward longer Control Shot moves.
- **Key weapons:** Control Shot with both movement upgrades (4 tiles per use)
- **Ideal setup:** Normal difficulty, 4-island run for maximum missions. Upgrade Control Shot range ASAP.
- **Estimated difficulty for bot:** Medium-Hard (requires consistent use across many missions)

### Hold the Door (5.4%)
- **Requirement:** Block 30 Emerging Vek by the end of Island 2 with the Bombermechs squad.
- **Squad:** Bombermechs (required)
- **Strategy:** Walking Bombs from the Bombling Mech can block spawns. With 2 Bombs upgrade and Silica pilot, place bombs on spawn tiles every turn. Across 2 islands of missions, need 30 blocks. Approximately 3-4 blocks per mission across 6-8 missions.
- **Bot approach:** The solver should prioritize placing Walking Bombs and mechs on emerging Vek tiles. Track total blocks across the run. The Bombling Mech with Two Bombs upgrade + Silica can place 4 bombs per turn.
- **Key weapons:** Bomb Dispenser with 2 Bombs upgrade, AP Cannon (Pierce Mech as blocker), Force Swap (repositioning)
- **Key pilots:** Silica on Bombling Mech (double shot = 4 bombs per turn)
- **Ideal setup:** Normal difficulty, 2-island run. Get 2 Bombs upgrade and Silica ASAP. Block every spawn possible.
- **Estimated difficulty for bot:** Hard (requires very aggressive spawn blocking over many missions)

### Core of the Earth (5.2%)
- **Requirement:** Drop 10 Enemies into pits on one Island with the Cataclysm squad.
- **Squad:** Cataclysm (required)
- **Strategy:** The Cataclysm squad cracks tiles; cracked tiles become chasms. Push enemies into chasms to kill them. Need 10 pit-kills across one island (3-4 missions). Crack tiles near enemies, then push them in.
- **Bot approach:** The solver should create chasms near enemy positions and push enemies into them. Track pit kills per island. Crack tiles preemptively where enemies are likely to stand. [needs-verification: exact cracking mechanics]
- **Key weapons:** Seismic Slam (crack tiles), Cluster Bombs (crack tiles), push weapons to knock enemies into pits
- **Ideal setup:** Normal difficulty, 4-mission island for maximum opportunities. Crack aggressively and push enemies into pits.
- **Estimated difficulty for bot:** Hard

### No Survivors (5.1%)
- **Requirement:** Have 7 units (any team) die in a single turn with the Bombermechs squad.
- **Squad:** Bombermechs (required)
- **Strategy:** Any units count -- enemies, mechs, Walking Bombs, Arachnoids, etc. A "turn" includes player actions and enemy actions. In a single turn: kill multiple enemies, let enemies kill your bombs, and possibly sacrifice a mech. With 4+ enemies + 3 Walking Bombs + possible Arachnoids, reaching 7 deaths is achievable.
- **Bot approach:** Set up a massive kill turn. Place bombs near enemies, position mechs to kill, and let enemy attacks destroy bombs. The solver needs to find turns where 7+ units can die simultaneously. This likely requires a later-game mission with many enemies.
- **Key weapons:** Bomb Dispenser (Walking Bombs die easily and count), AP Cannon (multi-target), Force Swap (positioning)
- **Ideal setup:** Normal difficulty, 3rd or 4th island with 5+ enemies. Set up bombs + enemy cluster for a mass kill turn.
- **Estimated difficulty for bot:** Hard

### Working Together (5.0%)
- **Requirement:** Area Shift 4 units at once with the Arachnophiles squad.
- **Squad:** Arachnophiles (required)
- **Strategy:** The Slide Mech's Area Shift pushes all adjacent tiles (including the mech itself). Need 4 units adjacent to the Slide Mech when activated. Position mechs, enemies, and Arachnoids around the Slide Mech.
- **Bot approach:** The solver should position the Slide Mech with 4 adjacent units (any combination of allies, enemies, and Arachnoids). Use other mechs to push or position units adjacent to the Slide Mech, then activate Area Shift.
- **Key weapons:** Area Shift (Slide Mech), Arachnoid Injector (spawn Arachnoids as additional units), Ricochet Rocket (push enemies into position)
- **Ideal setup:** Normal difficulty, a mission with spawned Arachnoids already on the field. Position 4 units around the Slide Mech.
- **Estimated difficulty for bot:** Medium-Hard

### Efficient Explosives (4.8%)
- **Requirement:** Kill 3 Enemies with 1 shot of the Ricochet Rocket with the Arachnophiles squad.
- **Squad:** Arachnophiles (required)
- **Strategy:** The Ricochet Rocket bounces off one target to hit another, pushing both. To kill 3: need the direct hit to kill target 1, the ricochet to kill target 2, and the bump damage from pushing to kill target 3. Enemies need to be at low HP.
- **Bot approach:** Weaken 3 enemies to 1-2 HP using Arachnoid Injector and Arachnoids. Then fire Ricochet Rocket to kill 2 directly and push-kill a third. Upgrade Ricochet Rocket +1 damage for 2 damage to both targets. Heavily reward 3-kill Ricochet setups.
- **Key weapons:** Ricochet Rocket with +1 damage upgrade, Arachnoid Injector (weaken enemies), spawned Arachnoids (weaken enemies)
- **Ideal setup:** Normal difficulty, later island with many enemies. Weaken a cluster of enemies over previous turns, then finish with Ricochet.
- **Estimated difficulty for bot:** Hard

### Boosted (4.6%)
- **Requirement:** Boost 8 Mechs in one mission with the Heat Sinkers squad.
- **Squad:** Heat Sinkers (required)
- **Strategy:** Heat Engines passive lets mechs standing on fire consume the fire and gain Boost. Need 8 boost events (same mech can be boosted multiple times). With 3 mechs over 5 turns, need to average 1.6 boosts per turn. The Napalm Mech's Firestorm Generator creates fire tiles along its path. The Dispersal Mech with Add Fire upgrade also creates fire. Each mech consuming a fire tile = 1 boost.
- **Bot approach:** The solver should maximize boost count. Every turn, try to position mechs on fire tiles before attacking. The Napalm Mech fires first to create fire, then other mechs walk through fire to get boosted. Track total boosts per mission.
- **Key weapons:** Firestorm Generator (creates fire trail), Thermal Discharger with Add Fire upgrade, Heat Engines (passive -- standing on fire = boost)
- **Key pilots:** Chen Rong or Archimedes on Quick-Fire Mech (move after attack to pick up fire for boost)
- **Ideal setup:** Normal difficulty, Archive island first (forests provide initial fire). Upgrade Napalm Mech range and Dispersal Mech Add Fire for more fire coverage.
- **Estimated difficulty for bot:** Hard

### Feed the Flame (4.5%)
- **Requirement:** Light 3 Enemies on fire with a single attack with the Heat Sinkers squad.
- **Squad:** Heat Sinkers (required)
- **Strategy:** The Thermal Discharger (Dispersal Mech) hits tiles in a line and with Add Fire upgrade sets them all on fire. With range upgrades, it can hit 4 tiles in a line. Need 3 enemies in a line to set all 3 on fire in one attack. Alternatively, the Firestorm Generator sets the target on fire and drops fire on tiles along its path.
- **Bot approach:** The solver should look for 3 enemies in a line and fire Thermal Discharger (with Add Fire upgrade) through all 3. Or use Firestorm Generator on a tile where 3 enemies are adjacent to the fire trail. Heavily reward 3-enemy fire setups.
- **Key weapons:** Thermal Discharger with Add Fire upgrade and range upgrades (up to 4-tile line), Firestorm Generator
- **Ideal setup:** Normal difficulty, later island with many enemies. Fully upgrade Thermal Discharger (Add Fire + both range upgrades). Wait for enemies to line up.
- **Estimated difficulty for bot:** Hard

### Maximum Firepower (4.5%)
- **Requirement:** Deal 8 damage with a single activation of the Quick-Fire Rockets with the Heat Sinkers squad.
- **Squad:** Heat Sinkers (required)
- **Strategy:** Quick-Fire Rockets fire two projectiles in different directions, each doing 1 base damage (2 with +1 Damage upgrade). With Push upgrade, targets are pushed and can take bump damage. With Boost, damage increases by 1. Using A.C.I.D. (from shop weapon or Detritus island) doubles damage. The wiki notes this can be done with just Push upgrade + Boost by bumping 2 Vek into 2 more Vek, or with full upgrades + A.C.I.D.
- **Bot approach:** Setup: upgrade Quick-Fire Rockets (Push + Damage), get Boosted, apply A.C.I.D. to targets if possible. The solver should look for bump chains (target pushed into another enemy). Direct damage (2) + bump damage (2) + direct damage (2) + bump damage (2) = 8 with full upgrades and boost.
- **Key weapons:** Quick-Fire Rockets (Push upgrade + Damage upgrade), Heat Engines (Boost), A.C.I.D. if available
- **Ideal setup:** Normal difficulty, Detritus island for A.C.I.D. access. Fully upgrade Quick-Fire Rockets. Get boosted. Fire at targets that will bump into other enemies.
- **Estimated difficulty for bot:** Hard

### Miner Inconvenience (4.0%)
- **Requirement:** Destroy 20 mountains in one game with the Cataclysm squad.
- **Squad:** Cataclysm (required)
- **Strategy:** The Cataclysm squad's attacks can destroy mountains (mountains become rubble when hit). Need to target mountains specifically across all missions in a game. Some islands have more mountains than others.
- **Bot approach:** The solver should target mountains when safe to do so. Track total mountains destroyed. Weight attacking mountain tiles moderately even when no enemy is on them. [needs-verification: which specific weapons destroy mountains most efficiently]
- **Ideal setup:** Normal difficulty, 4-island run. Pick islands with mountain-heavy maps (RST Corp or Archive Inc may have more). Target mountains aggressively.
- **Estimated difficulty for bot:** Hard

---

## Achievement Synergies and Run Planning

Some achievements can be combined in a single run:

### Natural combinations:
- **Island Secure** + **Field Promotion** + **Good Samaritan** (all in one Rift Walkers run)
- **Perfect Battle** + **Overpowered** + **Stormy Weather** (all Rusting Hulks, same run)
- **Get Over Here** + **Shield Mastery** + **Glittering C-Beam** (all Zenith Guard, same run)
- **Chain Attack** + **Hold the Line** + **Lightning War** (all Blitzkrieg, same run -- though Lightning War's time pressure conflicts with setup)
- **Unbreakable** + **Unwitting Allies** + **Mass Displacement** (all Steel Judoka, same run)
- **Quantum Entanglement** + **Scorched Earth** + **This is Fine** (all Flame Behemoths, same run)
- **Cryo Expert** + **Pacifist** + **Trick Shot** (all Frozen Titans, same run -- Pacifist conflicts somewhat with Trick Shot)
- **Healing** + **Immortal** + **Overkill** (all Hazardous Mechs, same run -- Immortal conflicts with aggressive Healing/Overkill play)

### Cross-run cumulative achievements (progress alongside any targeted run):
- Friends in High Places, Humanity's Savior, Perfect Strategy, Come Together
- I'm getting too old for this... (needs same pilot across 3 winning runs)
- Squads Victory, Adaptable Victory, Complete Victory

### Challenge run combinations:
- **Trusted Equipment** + **Engineering Dropout** (overlap: both avoid equipping new stuff)
- **There is No Try** + **Sustainable Energy** (already completed) can share a run if targeting both

---

## Solver Weight Overrides by Achievement

Quick reference for the bot's evaluation function weight modifications:

| Achievement | building_saved | vek_killed | mech_damage | special_weight |
|---|---|---|---|---|
| Perfect Battle | 100000 | 100 | -100000 | smoke_on_vek: +5000 |
| Stormy Weather | 10000 | 0 | -500 | smoke_damage_dealt: +2000 |
| Scorched Earth | 10000 | -200 | -100 | fire_tiles: +1000 |
| This is Fine | 10000 | -500 | -100 | burning_enemies: +3000 |
| Pacifist | 10000 | -5000 | -100 | freeze_over_kill: +2000 |
| Unwitting Allies | 10000 | -200 | -100 | enemy_kills_enemy: +5000 |
| Unbreakable | 10000 | 500 | +200 (on armored) | armor_absorb: +2000 |
| Healing | 10000 | 1000 | +100 (on healable) | heal_events: +1500 |
| Overkill | 10000 | 500 | -100 | single_hit_damage: +3000 (if >=8) |
| Chain Attack | 10000 | 200 | -100 | chain_length: +500 per tile |
| Hold the Line | 10000 | 500 | -100 | spawns_blocked: +2000 |
| Glittering C-Beam | 10000 | 500 | -100 | laser_targets: +2000 per enemy |
| Mass Displacement | 10000 | 500 | -100 | enemies_pushed_single: +3000 |
| Boosted | 10000 | 500 | -100 | boost_count: +1500 |

These weights are injected into the solver's evaluation function by the achievement strategist layer. The base evaluation function weights (from CLAUDE.md) remain in effect; these overrides add or modify specific terms.
