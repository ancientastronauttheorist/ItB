# A.C.I.D. Tank & A.C.I.D. Cannon — Research Report

Internal names: `Acid_Tank` (pawn), `Acid_Tank_Attack` (weapon). Confirmed in-game 2026-04-23 via live hover (pilot "Isla Patel" — a randomly-generated generic Corporate Pilot name, not a canonical character).

**Not to be confused with** the Nano Mech's A.C.I.D. Projector (`Science_AcidShot`) — see `hazardous_acid_projector.md`.

## 1. What it is

The **A.C.I.D. Tank** is a **single-use deployable equipment pickup** — one of four Tank deployables (Light, Pull, Shield, A.C.I.D.). When activated, it spawns an extra friendly unit on the board — a **fourth player-controlled combatant** alongside the three mechs. Same UI as a mech: click-select → move → attack. Persists until killed or mission ends; the item slot is consumed on deploy.

**Obtained via:** Time Pod drop, or purchased as a Reputation-shop reward. Not pilot-specific.

**"Isla Patel":** randomly-generated generic Corporate Pilot name auto-assigned to the tank (generic pilots have random names and no innate skill). No canonical pilot tie to the tank.

**In-game tooltip tag:** "Any Class Weapon" — the A.C.I.D. Cannon could theoretically be transferred between units if removed from the Tank, but in practice the Tank is the only carrier.

## 2. Tank unit stats

| Stat | Value | Source |
|---|---|---|
| HP | **1** (3 with +2 HP upgrade) | Fandom / bridge confirms `1/1` |
| Move | **3** | Fandom |
| Mass | Normal (pushable) | inferred from Allied Units class |
| Armor | none | |
| Flying | no | |
| Stable | no | |
| Passives | none | |

## 3. A.C.I.D. Cannon (`Acid_Tank_Attack`)

**In-game tooltip (verbatim):** "Shoot a projectile that inflicts A.C.I.D."

- **Damage:** **0** — no HP damage, only A.C.I.D. status. (Tank cannon family is consistently 0-damage — compare Light Tank: "shoots a projectile that does no damage and pushes the target.")
- **Targeting:** Projectile line, identical family to Light/Pull/Shield tank cannons — fires in one of four cardinal directions and hits the first valid target in that line. Range limited by board edge / line-of-sight.
- **Push:** **None by default.** The **Push upgrade (1 Core)** adds a 1-tile push away from the tank on hit.
- **ACID application:** applies A.C.I.D. to struck unit. If target has a **Shield**, ACID is blocked and **"falls to the feet"** — tile beneath becomes an A.C.I.D. Tile instead.
- **Power cost:** 0 grid power (tank deployables don't consume grid power). The "1" visible on the weapon icon is the Reactor-Core cost of an upgrade pip, not a power cost.

## 4. Upgrades

| Upgrade | Cost | Effect |
|---|---|---|
| **+2 HP** | 1 Core | Tank max HP becomes 3 |
| **Push** | 1 Core | Attack also pushes target 1 tile away from tank |

Total upgrade cost = 2 cores. Cheap relative to mech weapons.

## 5. Differences from A.C.I.D. Projector (Nano Mech)

| Attribute | A.C.I.D. Tank Cannon | A.C.I.D. Projector (Nano Mech) |
|---|---|---|
| Wielder | 4th deployable NPC (1 HP, 3 move, single-use) | Nano Mech (Science, 2 HP, 4 move, permanent) |
| Damage | 0 | 0 |
| Range | Projectile line (cardinal) | Projectile line (cardinal) |
| Push | **Upgrade only** (1 Core) | **Built-in 1-tile Forward** |
| Upgrades | +2 HP, Push | None |
| Persistence | Single-use per run | Permanent on mech |
| Bridge id | `Acid_Tank_Attack` | `Science_AcidShot` |
| Internal display name | "A.C.I.D. Cannon" | "Acid Projector" |

Both share:
- "Falls-to-feet" rule for shielded targets (ACID deposits on tile under the shield instead of on unit).
- Cannot apply ACID through Frozen (status blocked until thaw).

## 6. Edge cases

- **Shielded target:** ACID cannot apply; drops on target's tile per "falls to feet" rule.
- **Frozen target:** ACID cannot apply while frozen. Needs prior thaw.
- **Empty line of fire:** shot fizzles; **does not** target empty tiles to pre-seed an ACID tile (cannon targets units, not tiles).
- **Tank self-ACID:** the Tank can be ACID'd (by enemy ACID attacks), doubling incoming weapon damage — at 1 HP this one-shots it.
- **End of mission:** Tank is lost permanently; single-use per campaign run.
- **Chain push (with Push upgrade):** standard push rules — blocked push deals 1 bump to target + whatever it's shoved into.
- **Emerging Vek tile:** tank cannon targets units, not tiles. To pre-apply ACID to a spawn, you need a tile-targetable weapon (not this one). **Verify in-game** — the Projector can; Cannon may not.

## 7. Open questions (in-game verification)

1. **Projectile range cap** — full-board like other tank cannons, or capped? (Screenshot didn't show targeting reticle.)
2. **Empty-tile targeting** — truly unit-only, or can it fire at any cardinal tile? (Critical for solver legal-move generation.)
3. **Push-upgrade push direction** — strictly away-from-tank, or along projectile direction? (Universal tank behavior says away-from-tank; verify.)
4. **Mass** — is it Normal (1-tile pushable) or Small?
5. **Deterministic "Isla Patel"** — is there a pilot event that rolls this specific name, or purely random?
6. **Tank firing through buildings / mountains** — line-of-sight blockers stop the projectile; target is the blocker itself (0 damage, no effect). Verify what happens to ACID deposit.

## 8. Bridge / solver implementation

**Pawn `Acid_Tank`:**
- `hp: 1`, `move_speed: 3`, `class_type: "Allied"` (new category), `mass: Normal`, `flying: false`, `stable: false`
- Player-controlled (same action economy as mechs)
- Consumable slot (single-use per run) — not a permanent squad member

**Weapon `Acid_Tank_Attack`:**
- `weapon_type: "projectile"`, `damage: 0`, `range_max: 0` (infinite), `push: "none"` (upgrade-dependent), `acid: true`, `power_cost: 0`
- Targeting: cardinal line, first unit blocks
- Upgrade flags: `+2HP` (mutates pawn hp to 3), `+Push` (push: "forward", 1 tile away from tank)

**Bridge exposure:** currently the `Acid_Tank` pawn type is in `data/known_types.json`. Weapon display name `A.C.I.D. Cannon` may need to be added to weapon_defs so the bridge reports it correctly. Currently bridge emits `Acid_Tank_Attack` as the weapon field.

## Sources

- [A.C.I.D. Tank - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/A.C.I.D._Tank)
- [Light Tank - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Light_Tank) (0-damage projectile+push family)
- [Allied Units - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Allied_Units)
- [A.C.I.D. Tile - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/A.C.I.D._Tile) (falls-to-feet rule)
- [Shield - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Shield) (ACID+shield interaction)
- [Best Equipment - Geek Generation](https://g33kgeneration.wordpress.com/2018/05/14/into-the-breach-best-equipment/)
- [Favorite pickups - Steam Discussions](https://steamcommunity.com/app/590380/discussions/0/1696043263498127483/)
- Live in-game hover test 2026-04-23 (Isla Patel / Acid_Tank)
- Local: `data/known_types.json`
