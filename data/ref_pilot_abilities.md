# Pilot Abilities Audit Reference

Comprehensive inventory of all pilots and their passive abilities for Into the Breach solver implementation. This audit identifies which abilities should be modeled in the depth-5 beam search, bridge exposure gaps, and implementation priority.

---

## Pilot Abilities Table

| pilot_id | in-game name | ability | type | trigger | simulator_priority | bridge_exposed | current_solver_treatment | notes |
|----------|------------|---------|------|---------|-------------------|-----------------|--------------------------|-------|
| Pilot_Original | Ralph Karlsson | +2 XP per Vek kill | passive | on_kill | FLAVOR | yes (id only) | pilot_value_only | Leveling speed boost; no turn-level impact |
| Pilot_Youth | Lily Reed | +3 Move on first turn of every mission | passive | on_mission_start + on_turn_start | HIGH | yes (id only) | unmodeled | Turn 1 mobility directly enables/blocks tactics |
| Pilot_Genius | Bethany Jones | Mech starts every mission with Shield | passive | on_mission_start | HIGH | yes (id only) | unmodeled | Blocks first hit, prevents status effects (fire, freeze, smoke) |
| Pilot_Assassin | Abe Isamu | Mech gains Armored (reduce damage by 1, min 1) | passive | on_incoming_damage | HIGH | yes (id only) | unmodeled | Cumulative 25% reduction over 4 turns = game changer |
| Pilot_Miner | Silica | Mech can act twice if it does not move (costs 2 reactor power) | active | on_player_phase_conditional | HIGH | yes (id only) | unmodeled | Double damage output per turn; major power curve swing |
| Pilot_Recycler | Prospero | Mech gains Flying (costs 1 reactor power) | active | on_deploy_conditional | MED | yes (id only) | unmodeled | Avoids water/lava/chasm; enables new positioning |
| Pilot_Repairman | Harold Schmidt | Repair action pushes adjacent tiles | passive | on_repair | MED | yes (id only) | unmodeled | Turns heal into offensive positioning tool |
| Pilot_Medic | Isaac Jones | Gain 1 extra "Reset Turn" per battle (2 instead of 1) | passive | on_reset_trigger | HIGH | yes (id only) | unmodeled | Undo availability directly impacts plan depth |
| Pilot_Leader | Chen Rong | After attacking, gain 1 free tile movement | passive | on_attack_end | MED | yes (id only) | unmodeled | Repositioning after attack enables follow-up tactics |
| Pilot_Soldier | Camila Vera | Mech unaffected by Webbing and Smoke | passive | on_web_attempt + on_smoke_tile | HIGH | yes (id only) | unmodeled | Negates status effects that disable movement/attack |
| Pilot_Hotshot | Henry Kwan | Mech can move through enemy units | passive | on_move | MED | yes (id only) | unmodeled | Enables melee positioning from unexpected angles |
| Pilot_Warrior | Gana | Deploy anywhere on map, damaging adjacent enemies (costs 1 reactor power) | active | on_deployment | MED | yes (id only) | unmodeled | Map control on turn 1; 0-3 damage AoE |
| Pilot_Aquatic | Archimedes | Move again after shooting (costs 1 reactor power) | active | on_attack_end_conditional | MED | yes (id only) | unmodeled | Hit-and-run repositioning; costs reactor |
| Pilot_Mantis | Kazaaakpleth | 2 damage melee attack replaces Repair | passive | on_repair_attempt | MED | yes (id only) | unmodeled | Cannot heal; must damage instead; high risk/reward |
| Pilot_Zoltan | Mafan | +1 Reactor Core. Mech HP becomes 1. Gain Shield every turn. | passive | on_mission_start + on_turn_start | HIGH | yes (id only) | unmodeled | Shield regen negates incoming 1-3 damage; extra core enables double-power abilities |
| Pilot_Rock | Ariadne | +3 Health and immune to Fire | passive | on_mission_start + on_fire_attempt | HIGH | yes (id only) | unmodeled | Extra HP compounded with shield stacking; fire immunity is rare |
| Pilot_Arrogant | Kai Miller | Mech is Boosted if full health, otherwise -1 Move | passive | on_turn_start | MED | yes (id only) | unmodeled | Incentivizes aggressive play; movement penalty when hurt |
| Pilot_Caretaker | Rosie Rivets | After Move, Repair adjacent Mechs | passive | on_move_end | MED | yes (id only) | unmodeled | Mobile healing; can heal 2 allies per turn |
| Pilot_Chemical | Morgan Lejeune | Mech gains Boosted on kill | passive | on_kill | MED | yes (id only) | unmodeled | Snowball ability; +1 damage after first kill |
| Pilot_Delusional | Adam | On Reset Turn, gain Shield and +2 Move | passive | on_reset_turn | LOW | yes (id only) | unmodeled | Undo synergy; pairs with Isaac Jones for 3 resets |
| ? | Bethany Pike | (no data) | ? | ? | ? | ? | ? | Referenced in ref_pilots.md but no ability defined; possible legacy/placeholder |
| Pilot_Cyborg | Cyborg Pilot | Loses 25 XP when mech is disabled (cannot equip normal pilots) | passive | on_disable | FLAVOR | yes (id only) | pilot_value_only | Secret Squad exclusive; no damage passives |
| (none) | Corporate Timeline Pilot 1 | No special skill (equivalent to Artificial Pilot) | passive | (always active) | FLAVOR | yes (id only) | pilot_value_only | Does gain XP; no ability modifiers |
| (none) | Corporate Timeline Pilot 2 | No special skill (equivalent to Artificial Pilot) | passive | (always active) | FLAVOR | yes (id only) | pilot_value_only | Does gain XP; no ability modifiers |

**Notes on table:**
- **Bethany Pike**: Mentioned in user's initial list but no ability found in any source file. May be a typo for "Bethany Jones" or a removed/unreleased pilot.
- **Corporate Timeline Pilots**: Functionally identical to Artificial Pilots (no abilities, do gain XP). Not critical for solver since they appear only outside time-travel runs.

---

## Ability Type Breakdown

### Passive (Always-On)
Base game: Abe Isamu, Bethany Jones, Harold Schmidt, Kazaaakpleth, Mafan, Ariadne, Camila Vera, Henry Kwan, Chen Rong, Ralph Karlsson, Isaac Jones, Lily Reed.
Advanced: Kai Miller, Rosie Rivets, Morgan Lejeune, Adam.
Secret: Cyborg Pilot.

### Active (Player-Triggered, Cost 1-2 Reactor Core)
- Silica: Double Shot (2 core) — conditional on not moving
- Prospero: Flying (1 core)
- Gana: Preemptive Strike (1 core)
- Archimedes: Fire-and-Forget (1 core)

### Conditional (Fires on Specific Event)
- Lily Reed: Impulsive (mission start)
- Chen Rong: Sidestep (after attack)
- Rosie Rivets: Reassuring Hand (after move)
- Morgan Lejeune: Field Research (on kill)
- Adam: Chosen One (on reset turn)

---

## Ability Priority Ranking

### HIGH (Directly Changes Kill/Survival Calculus Every Turn)

1. **Bethany Jones (Starting Shield)** — Blocks first hit + prevents status effects. Essential for turns with fire/freeze threats.
2. **Abe Isamu (Armored)** — Cumulative 25% reduction over 4 hits; compounds with shields.
3. **Mafan (Zoltan)** — Regenerating shield every turn + extra reactor = 2-ability runs.
4. **Silica (Double Shot)** — 2x damage per turn without movement; fundamentally changes weapon priority.
5. **Ariadne (Rockman)** — +3 HP + fire immunity; survives self-damage mechs (Leap, Unstable, Electric Whip).
6. **Isaac Jones (Temporal Reset)** — Extra undo = depth-5 solver gains more look-ahead value.
7. **Camila Vera (Evasion)** — Ignores web/smoke = always moves/attacks; counters Scorpion/Spider threat.
8. **Lily Reed (Impulsive)** — +3 Move on turn 1 = 60% more mobility; enables turn-1 aggressive plays.

### MED (Specific Weapon/Terrain Interactions)

1. **Prospero (Flying)** — Avoids water/lava/chasm; enables unexpected positioning on island-specific maps.
2. **Harold Schmidt (Frenzied Repair)** — Repair becomes a push; pairs with tanky mechs that self-heal.
3. **Chen Rong (Sidestep)** — +1 repositioning after each attack; enables escape from danger zones.
4. **Gana (Preemptive Strike)** — Deploy anywhere + 0-3 AoE damage on turn 1; counters grouped spawn.
5. **Henry Kwan (Maneuverable)** — Move through enemies; melee positioning from unexpected angles.
6. **Archimedes (Fire-and-Forget)** — Shoot + move; hit-and-run tactics.
7. **Kazaaakpleth (Mantis)** — 2 damage melee vs. heal; enables front-line damage on Judo Mech.
8. **Kai Miller (Arrogant Boost)** — +1 damage at full health; -1 move when hurt.
9. **Rosie Rivets (Reassuring Hand)** — Mobile healing; 2 healing targets per turn.
10. **Morgan Lejeune (Field Research)** — +1 damage snowball on kill; strong on Arachnoid/Nano Mechs.

### LOW (Rare Triggers or Non-Damage Interactions)

1. **Ralph Karlsson (Experienced)** — +2 XP per kill; no turn-level impact, only leveling speed.
2. **Adam (Chosen One)** — Shield + move on reset; only triggers 1-2 times per mission.

---

## Bridge Exposure Analysis

**Current State (modloader.lua:140-154):**
```lua
local pilot_block = block:match('%["pilot"%]%s*=%s*(%b{})')
if pilot_block then
    local pilot_id = pilot_block:match('%["id"%]%s*=%s*"([^"]+)"')
    if pilot_id then
        local pd = {id = pilot_id}
        local lvl = pilot_block:match('%["level"%]%s*=%s*(%-?%d+)')
        if lvl then pd.level = tonumber(lvl) end
        local s1 = pilot_block:match('%["skill1"%]%s*=%s*(%-?%d+)')
        if s1 then pd.skill1 = tonumber(s1) end
        local s2 = pilot_block:match('%["skill2"%]%s*=%s*(%-?%d+)')
        if s2 then pd.skill2 = tonumber(s2) end
        result.pilots[pid_n] = pd
    end
end
```

**Exported Fields:**
- `pilot_id`: string (e.g., "Pilot_Zoltan") ✓
- `pilot_level`: 0-2 ✓
- `skill1`, `skill2`: numeric indices (unclear what they index)

**NOT Exported:**
- Pilot ability names or IDs
- XP values (can be inferred from level; 0=recruit, 1=25+XP, 2=75+XP)
- Unlock state per ability (level 2 abilities locked until level ≥ 2)

**Gap Impact:** To use pilot passives in the solver, one of these must happen:
1. **Bridge Extension** (preferred): Add to JSON state a `pilot_ability` field mapping `pilot_id` → {ability_name, trigger, priority}.
2. **Static Lookup Table** (pragmatic): Embed the pilot_id → ability mapping in `reference_pilot_value.md` or `known_types.json`, then solver reads it at startup.

---

## Stacking & Edge Cases

### Armor Stacking (Abe Isamu + Ariadne + Bethany Jones + Mafan)
- **Abe Isamu** (Armored): -1 damage per hit (min 1)
- **Ariadne** (Rockman): +3 HP
- **Bethany Jones** (Shield): Blocks first hit + prevents status
- **Mafan** (Zoltan Shield): Absorbs 1 damage per turn, regen every turn

These do NOT stack multiplicatively. They interact in priority order:
1. Shield blocks hit entirely (Bethany or Mafan)
2. Armor reduces by 1 (Abe)
3. Extra HP absorbs overflow (Ariadne)

Example: Abe takes 3 damage → 1 armor reduction → 2 damage to HP. If Bethany's shield is active, shield absorbs all 3 before armor applies. **Solver impact:** high. Defensive passives compound and must be modeled together.

### Double-Damage Passives (Silica + Morgan Lejeune)
- **Silica** (Double Shot): 2 attacks per turn without moving
- **Morgan Lejeune** (Field Research): +1 damage (Boost) after kill

These stack: A Silica pilot on a high-damage ranged mech can attack, kill, then attack again boosted. **Solver impact:** extremely high on kill-focused strategies.

### Movement Bonuses (Lily Reed + Chen Rong + Kai Miller + Henry Kwan)
- **Lily Reed** (Impulsive): +3 move on turn 1
- **Chen Rong** (Sidestep): +1 move after attack
- **Kai Miller** (Arrogant Boost): -1 move if hurt
- **Henry Kwan** (Maneuverable): move through units (qualitative, not quantitative)

Only Lily + Chen truly stack numerically. **Solver impact:** medium. Movement enables threat avoidance but doesn't directly damage.

### XP-Gated Abilities (All Leveled Pilots)
All 25 pilots with abilities gain XP:
- **Level 1** (25 XP): Unlock 1 of 2 offered perks from standard pool (+2 HP, +1 Move, +3 Grid DEF, +1 Reactor)
- **Level 2** (75 XP total): Unlock 1 of 2 offered perks from standard pool

Perks are permanent per mission once chosen. Pilot base ability (e.g., Abe's Armor) is ALWAYS active and NOT a perk.

**Key distinction:** Pilot base passive ≠ leveled perks. Solver must model:
- Base passive: always on
- Leveled perks: transient within mission, state-dependent (what the pilot actually learned this run)

**Current solver treatment:** Pilot level is exported but perks are not. Solver only sees pilot_level and cannot distinguish "Abe at level 1 with +2 HP perk" from "Abe at level 2 with +1 Reactor perk."

### "No Pilot" Default
Mechs without assigned pilots (empty slot or Artificial Pilot) have:
- No passive ability
- No XP gain (Artificial Pilots + Corporate Pilots are exceptions; Corporate Pilots DO gain XP)
- Base mech stats unmodified

**Solver implication:** Unmodeled. A mech "without pilot" should be treated as a baseline against which pilot passives are scored.

---

## Implementation Verdict (250 words)

### Bridge Sufficiency

The current bridge is **insufficient for passive pilot modeling**. Exporting pilot_id without ability metadata means the solver has 100% pilot_id coverage but 0% ability coverage. Options:

1. **Bridge Extension (Preferred)**: Modify `modloader.lua:90-91` to add a `pilot_ability` field capturing the ability name alongside pilot_id. Cost: ~20 lines of Lua pattern-matching. Benefit: one-stop truth source; no duplication.

2. **Static Lookup Table (Pragmatic)**: Embed this audit into `known_types.json` or a new `data/pilot_ability_map.json`. Solver loads at startup. Cost: maintain two sources (bridge exports id, table provides ability). Benefit: zero bridge changes; quick to test.

**Recommendation**: Build a static lookup first for rapid iteration, then extend bridge if the static map becomes a maintenance burden.

### Top 8 Pilots (by Solver Impact & Frequency)

1. **Bethany Jones** (Starting Shield) — HIGH priority. Blocks first hit + status. Every island.
2. **Abe Isamu** (Armored) — HIGH priority. Cumulative reduction. Frontline standard.
3. **Silica** (Double Shot) — HIGH priority. 2x damage per turn. Highest raw power.
4. **Mafan** (Zoltan) — HIGH priority. Regen shield + extra core. Self-damage squad enabler.
5. **Lily Reed** (Impulsive) — HIGH priority. +3 move turn 1. Positioning baseline.
6. **Isaac Jones** (Temporal Reset) — HIGH priority. Extra undo. Depth-5 solver gains major advantage.
7. **Ariadne** (Rockman) — HIGH priority. +3 HP + fire immunity. Self-damage mitigation.
8. **Camila Vera** (Evasion) — HIGH priority. Web/smoke immunity. Specific threat negation.

**Ralph Karlsson**: Implement last. XP gain is FLAVOR; no turn-level impact.

### Key Unknown Blocking Full Implementation

**How do leveled perks interact with pilot base passives in the solver state?** The save file exports `skill1`, `skill2` as numeric indices (0=unlearned, 1+=learned), but the indices don't map to ability names anywhere. Clarify:
- Are skill1/skill2 player choices persisted per-pilot per-mission, or per-run?
- Which perk pool do they sample from (restricted by pilot, e.g., Mafan cannot learn +2 HP)?
- If a mission fails, do perks reset, or do they carry to retry?

Without this, the solver cannot score "Abe with +2 HP perk" vs. "Abe with +1 Move perk" separately.

---

## Files Consulted

- `src/bridge/modloader.lua:140-154` — Pilot data extraction
- `data/ref_pilots.md` — Pilot ability descriptions
- `data/pilots.json` — Structured pilot definitions
- `data/ref_squads_and_mechs.md` — Pilot synergies per squad
- `data/known_types.json` — Observed pilot IDs
- `data/ref_game_mechanics.md` — Timing and stacking rules

