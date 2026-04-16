# Enemy Data Audit — 2026-04-15

Audited 4 enemies currently on the board by clicking each tile and hovering
their name in the bottom-left Unit Status panel. Compared observed tooltip
data against the solver's model (`src/model/weapons.py`, `src/model/pawn_stats.py`,
`src/solver/solver.py::_simulate_enemy_attacks`).

## Observed vs. Solver

### 1. Alpha Hornet (E5) — bridge type `Hornet2`, weapon `HornetAtk2`
| Field        | Game tooltip                      | Solver data                               | Match |
|--------------|-----------------------------------|-------------------------------------------|-------|
| Move         | 5                                 | `pawn_stats.py: move_speed=5`             | ✓     |
| Flying       | yes                               | `pawn_stats.py: flying=True`              | ✓     |
| Weapon name  | Launching Stinger                 | `weapons.py: "Alpha Hornet Sting"`        | cosmetic only |
| Damage       | 2                                 | `weapons.py: damage=2`                    | ✓     |
| Effect       | Stab 2 tiles in front of the unit | `weapons.py: aoe_behind=True`, melee branch applies TargetBehind hit | ✓ |
| Passive      | Explosive Decay (inherited)       | `board.blast_psion_active` flag applied at Vek death | ✓ |

### 2. Alpha Centipede (C5) — bridge type `Centipede2`, weapon `CentipedeAtk2`
| Field        | Game tooltip                                          | Solver data                                           | Match |
|--------------|-------------------------------------------------------|-------------------------------------------------------|-------|
| Move         | 2                                                     | `pawn_stats.py: move_speed=2`                         | ✓     |
| Weapon name  | Corrosive Vomit                                       | `weapons.py: "Alpha Centipede Spit"`                  | cosmetic only |
| Damage       | 2                                                     | `weapons.py: damage=2`                                | ✓     |
| Acid effect  | Applies A.C.I.D. on nearby units                      | `weapons.py: acid=True`                               | **GAP in simulation** |
| AOE shape    | Target + 2 perpendicular tiles (splash)               | `weapons.py: aoe_perpendicular=True`                  | **GAP in simulation** |
| Passive      | Explosive Decay (inherited)                           | inherited via Blast Psion flag                        | ✓     |

**Gap:** `solver.py::_simulate_enemy_attacks` projectile branch (lines 218–227)
only applies base damage to the primary target. It does **not** apply the
`acid` status flag, and it does **not** splash the `aoe_perpendicular` tiles.
The weapon def has the flags (`acid=True, aoe_perpendicular=True`), but the
enemy attack simulator ignores them. Mech weapon simulation (`simulate.py`)
handles `wdef.acid` correctly — the gap is on the enemy-attack side only.

### 3. Blast Psion (D5) — bridge type `Jelly_Explode1`, no weapon
| Field        | Game tooltip                                                         | Solver data                                           | Match |
|--------------|----------------------------------------------------------------------|-------------------------------------------------------|-------|
| Move         | 2                                                                    | `pawn_stats.py: move_speed=2`                         | ✓     |
| Flying       | yes                                                                  | `pawn_stats.py: flying=True`                          | ✓     |
| Attack       | none (passive unit)                                                  | no queued_target, no weapon                           | ✓     |
| Passive      | Explosive Decay — all *other* Vek explode on death for 1 adj damage  | `simulate.py::apply_blast_psion_explosion`, triggers on Vek death, excludes the Psion itself | ✓ |

**Note:** the bridge type string `"Jelly_Explode1"` is the game's internal ID
for the Blast Psion (historical naming — unrelated to the Blobber). Solver uses
this type string to set `board.blast_psion_active`. **No gap** — the code is
correct but the name is misleading for anyone reading it.

### 4. Alpha Scorpion (D3) — bridge type `Scorpion2`, weapon `ScorpionAtk2`
| Field        | Game tooltip                               | Solver data                                    | Match |
|--------------|--------------------------------------------|------------------------------------------------|-------|
| Move         | 3                                          | `pawn_stats.py: move_speed=3`                  | ✓     |
| Weapon name  | Goring Spinneret                           | `weapons.py: "Alpha Scorpion Strike"`          | cosmetic only |
| Damage       | 3                                          | `weapons.py: damage=3`                         | ✓     |
| Web effect   | Web the target, preparing to stab it       | `weapons.py: web=True`                         | **GAP in simulation** |
| Passive      | Explosive Decay (inherited)                | inherited via Blast Psion flag                 | ✓     |

**Gap:** `solver.py::_simulate_enemy_attacks` melee branch (lines 229–252)
applies damage + optional `aoe_behind`, but does **not** set `web=True` on the
target when the enemy weapon has the web flag. The web flag is only applied
in the `self_aoe` branch (Scorpion Leader's Massive Spinneret). Alpha
Scorpion's normal melee web hit does not web its victim in simulation.

## Summary of Gaps to Fix

All three gaps are in `src/solver/solver.py::_simulate_enemy_attacks`:

1. **Enemy projectile ACID** — when `wdef.acid`, set `unit.acid = True` on the
   hit target (and spawn an acid pool if the tile has water/ground).
2. **Enemy projectile `aoe_perpendicular`** — when `wdef.aoe_perpendicular`,
   also hit the two tiles perpendicular to the projectile direction at the
   impact point (Centipede's forward-T splash).
3. **Enemy melee `web`** — when `wdef.web` and weapon type is melee, set
   `unit.web = True` (and track `web_source_uid = enemy.uid`) on the hit target.

Nothing else differs between tooltip and solver. Stats (HP/Move/Flying) and
damage numbers all match. The Explosive Decay global buff from the Blast
Psion is modeled correctly.

## Fix Status — 2026-04-15

All three gaps fixed in both Python (`src/solver/solver.py`) and Rust
(`rust_solver/src/enemy.rs`):

- `_apply_enemy_weapon_status` helper added in Python, applied after each
  enemy hit in the projectile and melee branches.
- `apply_weapon_status` now called after each enemy hit in the Rust
  `Projectile` and `Melee` branches (+ 2-tile `weapon_behind` variant).
- Web writes the attacker's UID into `web_source_uid` so the existing
  web-break-on-push/kill logic continues to work.
- `aoe_perpendicular` branch hits the two tiles perpendicular to the
  projectile direction with full damage + status.

Rust test coverage (all pass):
- `test_alpha_centipede_applies_acid_to_target`
- `test_alpha_centipede_aoe_perpendicular_splashes`
- `test_alpha_scorpion_webs_target`
- `test_alpha_hornet_line_still_hits_both_tiles` (regression)

Full Rust suite: 64/64 passing. Extension rebuilt and reinstalled; live
`game_loop.py solve` runs cleanly against the current board.
