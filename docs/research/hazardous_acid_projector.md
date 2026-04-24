# A.C.I.D. Projector (Nano Mech starter) — Research Report

Internal names: `ScienceMech` / `Nano_Mech` chassis, `Science_AcidShot` weapon. This is the **Nano Mech's starter** from Hazardous Mechs squad. **Distinct from the A.C.I.D. Cannon** (Any-Class weapon on the A.C.I.D. Tank NPC deployable — see `hazardous_acid_cannon.md`).

## 1. Source

**Squad:** **Hazardous Mechs** (base game, unlocked for 4 coins). Science-class slot.

**Squadmates:** Leap Mech (Prime, Hydraulic Legs) + Unstable Mech (Brute, Unstable Cannon) — both self-damage weapons that rely on Nano's A.C.I.D. + Viscera Nanobots to survive. Evaluator weights for `acid_applied` should be high for this squad.

## 2. Nano Mech Base Stats

| Stat | Value |
|---|---|
| Class | Science |
| HP | 2 |
| Move | 4 |
| Mass | Small (Science-class default; pushable) |
| Flying | Yes (move over water/chasm/lava/fire tiles without dying; lava still applies Fire on landing) |
| Armor / Stable | No / No |
| Passive (weapon slot 2) | **Viscera Nanobots** — heal 1 HP on any mech's kill (squad-wide); Upgrade I = +1 Heal (heal 2 HP), 3 power |

## 3. A.C.I.D. Projector — Exact Behavior

| Field | Value |
|---|---|
| Debug name | `Science_AcidShot` |
| Class-locked | Science-only slot (cannot be swapped to Prime/Brute) |
| Power cost | **Free** (no reactor power) |
| Damage | **0** (wiki "Damage: ''" field; dev clarified "zero-damage attacks like the Nano Mech's attack") |
| Weapon type | Projectile (straight line in one of 4 cardinal directions) |
| Range | **Unlimited** — first obstacle / unit / board-edge stops it |
| Push | **1 tile Forward** (away from Nano Mech, in fire direction) |
| Status applied | **A.C.I.D.** on hit target |
| Upgrades | **None.** No Upgrade 1 or 2 — one of the few upgrade-less weapons. |
| Self-damage | None |
| Ally-targetable | Yes (no damage, but target receives ACID) |

### Execution order

Firing pattern on target tile T (first occupied/blocking tile in projectile line):
1. **Resolve projectile line.** First unit, mountain, or board edge on the line is the target tile T. Ice tiles don't block; units/mountains/buildings/edge do.
2. **If T has a unit:** apply A.C.I.D. to that unit, then push 1 tile Forward. Damage = 0, so armor/ACID damage math is moot.
3. **If push resolves into a blocker:** pushed unit takes 1 bump damage (standard push rules — ignores armor/ACID).
4. **If T has no unit (mountain/building at first obstacle):** mountain takes 0 weapon damage (no effect). A.C.I.D. is **deposited on the ground tile** immediately in front of the mountain (per dev clarification: "A.C.I.D. falls to their feet" when target can't receive it). **Verify in-game.**

## 4. Upgrades

**None.** A.C.I.D. Projector has no Upgrade 1 or Upgrade 2. No power investment possible. Nano Mech's only upgrade investment is into Viscera Nanobots' `+1 Heal` (3 power). Codebase already correctly omits upgrade options.

## 5. Edge Cases / Interactions

- **Shield:** 0 damage, so shield is NEVER consumed by this weapon. Shields block new negative status effects → unit does NOT get A.C.I.D. Instead, per dev clarification, A.C.I.D. "falls to their feet" — **tile under the shielded unit becomes an A.C.I.D. Tile**. When shield is later broken, unit picks up ACID from standing on the tile (if still there).
- **Frozen:** Same fall-to-feet mechanic. 0 damage does not unfreeze. ACID falls to tile under frozen unit → becomes A.C.I.D. Tile (or **Frozen A.C.I.D. Tile** if tile is also ice).
- **Push still applies to shielded/frozen targets** — shield doesn't block push; frozen does. For frozen, push is nullified; only ACID-to-tile effect remains. **Verify.**
- **Armor:** Irrelevant — 0 damage means armor's −1 never triggers. ACID applied as-is.
- **ACID (already on target):** No-op stacking — ACID is boolean.
- **Water tile target:** Projectile hits first blocker along the line; water doesn't block projectiles. If pushed unit ends up pushed INTO water → drowns (non-flying) + water tile becomes **A.C.I.D. Water Tile**. Flying units pushed into water: entering water removes ACID from unit, so flying Vek pushed into water by this weapon loses ACID immediately.
- **Fire tile / lava tile target:** ACID extinguishes burning tile (wiki: "Acid extinguishes burning tiles but not burning units"). Firing at a unit on a fire tile leaves target with ACID + Fire, but tile becomes ACID (not burning).
- **Emerging Vek tile:** Firing at a spawn tile in enemy's emergence phase → ACID deposited on tile → Vek that emerges next turn walks onto ACID and becomes ACID-ed.
- **Smoke tile:** Firing FROM smoke is blocked. Firing INTO smoke is allowed — projectile passes through; ACID applies normally.
- **Building target:** 0 damage → building unharmed. ACID deposited on building's tile (same fall-to-feet logic). If unit later steps on that tile after building destruction → picks up ACID.
- **Psion interaction:** "Acid-based attacks nullify armor buffs from Psion Vek" (Gameranx) — ACID on Shield-Psion-buffed unit removes the armor buff.
- **Friendly-fire ACID:** CAN target a friendly mech (e.g., to double a scripted hit that will kill both). Rarely useful; expose as legal action in solver, low priority.

## 6. Open Questions (verify in-game, then bump SIMULATOR_VERSION)

1. **Projectile hitting mountain/building (no unit at target):** does ACID deposit on the obstacle tile, the tile before it, or nowhere? Wiki silent.
2. **Projectile with no target (edge of board):** does ACID deposit on edge tile, or is shot wasted? Probably wasted (matches Taurus Cannon).
3. **Push of Frozen unit:** frozen units are immobilized — does Projector's push move them? If not, does ACID still transfer to tile they stand on?
4. **Acid on sand tile:** sand→smoke conversion triggers on "weapon damage" — 0 damage probably does not convert sand. Verify.
5. **Projector fired at an A.C.I.D.-Frozen ice tile:** it's already an ACID tile under ice. No-op? Verify.

## 7. Existing Codebase State

Already partially implemented:
- `src/model/weapons.py` → `Science_AcidShot`: `WeaponDef(name="Acid Projector", weapon_type="projectile", damage=0, push="forward", acid=True, range_max=0)` ✓
- `rust_solver/src/weapons.rs` → `w[44]`: `WeaponType::Projectile, damage: 0, push: PushDir::Forward, range_max: 0, flags: ACID` ✓

**Gaps to close (each bumps SIMULATOR_VERSION):**
- Does Rust simulator's `apply_acid` route ACID to the tile under a shielded/frozen target (fall-to-feet)? If it applies to the unit directly, this is a bug.
- Does the simulator model ACID on emerge-tiles pre-applying ACID to the next spawn? Important for Hazardous squad scoring.
- Does water-on-ACID-unit → A.C.I.D. Water Tile conversion apply when unit drowns from this weapon's push? Check `apply_push` → water drown handler.

## Sources

- [Nano Mech - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Nano_Mech) (cache: `data/wiki_raw/Nano_Mech.json`)
- [Hazardous Mechs - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Hazardous_Mechs) (cache: `data/wiki_raw/Hazardous_Mechs.json`)
- [Weapons table - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Weapons) (cache: `data/wiki_raw/Weapons.json` tables[3] rows[4])
- [BUG - A.C.I.D. vs Shields and Ice - Steam Discussions (dev clarification)](https://steamcommunity.com/app/590380/discussions/0/1694914736004808550/)
- [Into The Breach: All The Weird Things The Game Doesn't Tell You - Gameranx](https://gameranx.com/features/id/142114/article/into-the-breach-all-the-weird-things-the-game-doesnt-tell-you/)
- [Abilities and status effects - Wiki](https://intothebreach.fandom.com/wiki/Abilities_and_status_effects)
- [A.C.I.D. Tile - Wiki](https://intothebreach.fandom.com/wiki/A.C.I.D._Tile)
- [Corroding A.C.I.D. - Wiki](https://intothebreach.fandom.com/wiki/Corroding_A.C.I.D.)
- [Shield - Wiki](https://intothebreach.fandom.com/wiki/Shield)
