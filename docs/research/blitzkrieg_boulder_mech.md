# Boulder Mech & Rock Accelerator — Research Report

Internal names: `RockartMech` chassis, `Ranged_Rockthrow` weapon. Bridge currently mislabels weapon as `Rock Launcher` — **bug to fix**. In-game display confirmed as **Rock Accelerator** via live hover test 2026-04-23 (pilot Philip Ferry).

## 1. Squad & mech stats

**Squad:** Blitzkrieg (base game). Ranged class.

**Boulder Mech base stats** (empirically confirmed 2026-04-23; wiki base HP may differ):

| Field | Value | Notes |
|---|---|---|
| Class | Ranged | |
| HP | **3 (in live game)** — wiki caches list base 2, so this may be a pilot/core bonus or Advanced Edition buff | **Verify base HP** in a fresh squad-pick |
| Move | 3 | Standard for Ranged |
| Mass | **Massive** (mountain icon confirmed on-screen) | |
| Flying | No | |
| Stable | No | |
| Armor | No | |
| Innate passives | None | |

## 2. Rock Accelerator — Execution Order

**In-game tooltip (verbatim):** "Launch a rock at a tile, pushing adjacent tiles."

**Base stats (confirmed in-game):**
- **Damage:** 2
- **Power cost:** 1 (single pip)
- **Range:** any tile in the targeted cardinal line (not artillery arc — **straight-line projectile** shot from the mech's tile in N/E/S/W, player picks the destination tile within the line)
- **Targeting:** cardinal line, any distance to board edge; tile is individually selectable

**Push visualization (empirically confirmed in preview animation):** when firing north, the two pushed tiles are **east and west of the destination tile** (perpendicular to firing axis). Forward/backward tiles NOT pushed. This is the key distinction vs. Artemis.

**Step-by-step resolution:**

1. **Projectile flies** from Boulder Mech along its facing cardinal axis to the selected destination tile. The rock is a distinct object in-flight (matters for Smoke-on-self: Smoke prevents firing at start, not mid-flight).
2. **On impact with the destination tile:**
   - **If tile contains a unit (enemy, mech, building, Vek, boulder, mountain):** rock is destroyed, target takes **2 damage** (weapon damage — obeys Armor -1, ACID ×2, Shield blocks). No rock remains.
   - **If tile is empty walkable ground (incl. sand, forest):** rock persists as a **1-HP pushable obstacle** ("Rock" pawn) occupying the tile.
   - **If tile is a mountain:** mountain takes 1 damage (cracked → rubble). Rock consumed.
   - **If tile is water / chasm / lava:** rock falls in, destroyed; no obstacle created.
   - **If tile is ice:** ice cracks. No obstacle on top.
3. **Push adjacent tiles perpendicular to the projectile path** (the two "side" tiles — left and right of the destination tile relative to firing axis). Forward/backward NOT pushed.
   - Perpendicular push direction is outward from the destination tile on both sides simultaneously.
   - Standard push rules apply: blocked → bump for 1 dmg (ignores armor/ACID); chain push moves only the first unit.
4. **If the target itself was pushable and the rock hit it**, the 2 damage resolves first (killing if ≤2 HP), then side-pushes trigger on the two perpendicular tiles. The center tile does NOT also receive a push.

**Key behavioral notes:**
- Rocks left on empty tiles are **pushable** by any push effect, are **targetable** as obstacles, do **not** attack enemies, **block projectiles** (Firefly shots, etc.), and **block spawn tiles** (Vek dies via blocking damage on the rock; rock takes 1 dmg = destroyed).
- Rocks **conduct Electric Whip** (count as chain-able units) — core Blitzkrieg synergy.
- Enemies do **not** target rocks voluntarily. Tactical Compendium notes **Tumblebugs do not target previously-placed boulders**.
- Destroying a rock counts as a kill but grants **no XP/pilot rep**.
- Rocks are destroyed by fire (damage over time), water/chasm/lava on push, or any 1+ damage instance.
- Rock mass: **Normal** (pushable by standard pushes; not Massive).

## 3. Upgrade Paths

**Only ONE upgrade** (empirically confirmed — no second upgrade slot in tooltip):

| Upgrade | Cost | Effect |
|---|---|---|
| +1 Damage | **2 power** (2 pips) | base 2 → 3 damage |

No Power +1 or Range upgrade.

## 4. Edge Cases / Interactions

- **Perpendicular-only push:** Rock Accelerator pushes exactly the two tiles adjacent to the destination tile that are perpendicular to the firing axis. Forward/backward NOT pushed. This is the single most important mechanical difference from Artemis — common solver bug source.
- **Ally-targetable:** Yes — can fire at a friendly mech tile; mech takes 2 dmg (Armor/ACID-modified) and the two sides get pushed. Useful for repositioning pushes, but no "friendly fire prevention."
- **Self-targeting:** Cannot fire at own tile (standard weapon rule).
- **Mountain at destination:** 1 damage to mountain (cracked/destroyed), rock consumed, side pushes still trigger.
- **Empty destination + no ground (water/chasm/lava):** rock destroyed, no obstacle, side pushes still trigger. Useful to push enemies into water without leaving a blocker.
- **Smoke tile at destination:** Smoke on firing mech prevents firing. Smoke on destination tile — **unconfirmed**; ITB-wide rule is smoke does not block *arriving* weapons, only *firing*, so the rock should land normally.
- **Shield on target:** Shield absorbs 2 damage (no damage, no death). Rock still consumed. Side pushes still trigger.
- **Frozen target:** Any damage unfreezes; target takes 0 damage, unfreezes. Side pushes still trigger and break frozen neighbors.
- **ACID target:** 2 × 2 = 4 damage. Side pushes unaffected by ACID.
- **Armor target:** 2 − 1 = 1 damage.
- **Projectile path blocked mid-flight:** The player *cannot select* a tile behind a blocker — the targeting indicator stops at the first blocker. This is a UI constraint, so "blocked mid-flight" doesn't occur at resolution time.
- **Rock blocking Vek emergence:** emerging Vek deals blocking damage (1) to rock, rock dies (1 HP), Vek is cancelled.
- **Rocks destroying Time Pods:** flagged as "likely but unconfirmed" in Tactical Compendium.
- **Psion auras:** rock is not a Vek, so Psion Tyrant buffs don't apply to it. Shield Psion's shield on enemy target blocks the 2 damage but not the side pushes.
- **Objective buildings at destination:** rock deals 2 damage → objective building (2 HP) reduced to 1 HP. Side pushes still trigger.
- **Fire on rock:** rock takes 1 damage/turn → destroyed next turn.
- **Boulder Mech in Lightning Mech chain:** at 2 HP base (wiki) or 3 HP (live), Boulder Mech dies to its own squad's Electric Whip — community consensus is to upgrade HP first.

## 5. Open Questions (verify in-game)

1. **Base HP** — wiki caches say 2, live game shows 3. Verify in a fresh Blitzkrieg pick (no pilot, no upgrades).
2. **Rock pawn type name** in game data — Lua files call it `Rock` / `RockLight` / similar; confirm from ITB-ModLoader `/scripts/` dump.
3. **Rock interacts with conveyor tiles** — does a placed rock get conveyed? Likely yes.
4. **Smoke at destination tile** — does arriving rock still deal damage and push? Rule-consistent answer is yes, but no explicit source.
5. **Rock mass for push** — Normal (standard) vs. Massive. Assume Normal unless in-game test shows otherwise.
6. **Rock blocking push chains** — when an enemy is pushed into a rock tile, does it bump-damage the rock (1 dmg, destroys it), bump-damage itself (1 dmg), or both?
7. **Time Pod destruction** by rock.
8. **Interaction with Storm Generator / other Advanced Edition weapons** — none documented; assume no special case.

## 6. Solver/bridge implementation notes

- Bridge bug: `RockartMech` currently reports weapon display name `Rock Launcher`. In-game name is **Rock Accelerator**. Internal `Ranged_Rockthrow` id is fine; fix the display mapping.
- Perpendicular push direction must be hard-coded as "axis perpendicular to firing direction." Do NOT reuse Artemis push logic.
- Rock spawning on empty tile = new `Rock` pawn, 1 HP, Normal mass, passive (no attack), counts as conductor for Electric Whip.
- Mountain hit: 1 damage to mountain, rock consumed.
- Water/chasm/lava hit: rock destroyed, no persisting pawn.

## Sources

- [Rock Accelerator - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Rock_Accelerator)
- [Boulder Mech - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Boulder_Mech)
- [Blitzkrieg squad - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Blitzkrieg)
- [Rock Launcher (distinct weapon) - Wiki](https://intothebreach.fandom.com/wiki/Rock_Launcher)
- [Subset Games forum: Artemis Artillery and Rock Accelerator descriptions are confusing](https://subsetgames.com/forum/viewtopic.php?t=32946)
- [Steam: Tactical Compendium](https://steamcommunity.com/app/590380/discussions/0/3461597549837414830/)
- [Steam: How to use Blitzkrieg?](https://steamcommunity.com/app/590380/discussions/0/1694917906649168346/)
- [Steam: Know your Breach](https://steamcommunity.com/sharedfiles/filedetails/?id=1615974379)
- [GameFAQs: Blitzkrieg walkthrough](https://gamefaqs.gamespot.com/pc/205477-into-the-breach/faqs/76363/blitzkrieg)
- [Reactor Core - Wiki](https://intothebreach.fandom.com/wiki/Reactor_Core)
- Live in-game hover test 2026-04-23 (pilot Philip Ferry; preview animation confirms perpendicular push)
- Local: `data/wiki_raw/Blitzkrieg.json`
