# Task #14 scratch — pilot passives

Branch: `solver/pilot-passives`. Baseline regression 277/277 (main @ ddaf68f).

## Why not the other HIGH-tier passives

Several "HIGH" pilots in `data/ref_pilot_abilities.md` are **already** reflected in
bridge state and need no new Rust code for the single-turn solver:

- **Bethany Jones (Pilot_Genius)** — Starting Shield: bridge sets `shield=true`
  at turn 1; `Unit::shield()` already blocks damage. No regen, so nothing to
  model across turns either (unlike Mafan).
- **Abe Isamu (Pilot_Assassin)** — Armored: bridge sets `armor=true`;
  simulator already subtracts 1 from weapon damage.
- **Ariadne +3 HP** (the HP half of Rockman) — `_compute_pilot_value` already
  folds the +3 into `max_hp`; the HP-boost heuristic means the solver sees
  the real HP.
- **Lily Reed (Pilot_Youth)** — +3 Move turn 1: bridge reports the boosted
  `move` field on turn 1 already.

What's left in HIGH that actually needs code: the persistent immunities and
the one action-transforming passive.

## Chosen scope (3 passives, 4 hook points)

All three change simulator predictions on a given board → **SIMULATOR_VERSION bump 2→3**.

### 1. Camila Vera — Pilot_Soldier — Evasion (web + smoke immune)
Wiki-verified 2026-04-23: "Mech unaffected by Webbing and Smoke".
- **Web hook**: `simulate.rs:924` (mech-weapon applies web) and `enemy.rs:443` /
  `enemy.rs:471` (Vek web attacks) — skip `set_web(true)` when target unit has
  the Pilot_Soldier flag.
- **Smoke**: no-op today. `rust_solver/src/simulate.rs` does not currently
  model mech-attack-cancelled-when-on-smoke (see grep of smoke sites — all
  are tile-mutation or enemy-side). The sim treats every mech as
  smoke-immune. Wire the flag anyway so a future fix to the base mechanic
  auto-honors Camila. Mark with `// TODO: honor PilotSoldier when smoke
  cancels mech attacks`.

### 2. Ariadne — Pilot_Rock — Rockman (fire immune, +3 HP already in max_hp)
Wiki-verified: "+3 Health and immune to Fire".
- **Fire-apply hook**: `simulate.rs:571,604,762,911,1459` and `enemy.rs:436,619`
  (and possibly ~1677) — guard each `set_fire(true)` on a player unit by
  checking the target's pilot flag. Cleanest via a `Unit::can_catch_fire()`
  helper that returns `false` when the pilot is Pilot_Rock OR the squad has
  `flame_shielding`.
- **Fire-tick hook**: `enemy.rs:198`. Already has a `flame_shielding` branch
  (squad-wide). Generalize: skip fire tick if `can_catch_fire == false` OR
  the unit already shouldn't be burning (defensive, fire flag shouldn't
  have been set in the first place).
- Do **not** touch max_hp; `_compute_pilot_value`'s HP-boost heuristic is
  sufficient.

### 3. Harold Schmidt — Pilot_Repairman — Frenzied Repair (push adjacent)
Wiki-verified: "pushes adjacent enemies away … also applies to mechs and
obstacles like boulders".
- **Repair-branch hook**: in `simulate.rs` at the `WeaponId::REPAIR` branch,
  after the HP / fire / acid / frozen cleanup, emit an outward push on each
  of the 4 cardinal neighbours of the mech's tile. Use the existing
  `apply_push` helper so bump-into-building, push-chain, and terrain
  interactions are all consistent with other push sources.

## Implementation plan

### Unit struct change
Add `pilot_flags: u8` to `rust_solver/src/board.rs::Unit`:
```rust
bitflags! {
    pub struct PilotFlags: u8 {
        const SOLDIER    = 0b0001;  // Camila Vera — web + smoke immune
        const ROCK       = 0b0010;  // Ariadne — fire immune (+3 HP is in max_hp)
        const REPAIRMAN  = 0b0100;  // Harold Schmidt — repair pushes adj
    }
}
```
(One `u8` keeps `Unit` under its current size bucket; board_size test has
1200-byte headroom so this is fine.)

### JSON/bridge path
1. `rust_solver/src/serde_bridge.rs::JsonUnit` — add `pilot_id: Option<String>`.
2. In `board_from_json`, map string → `PilotFlags` bits when `is_mech`. Enemies
   always 0.
3. Python `src/loop/commands.py::cmd_solve` (and siblings) — inject `pilot_id`
   into each mech's bridge dict alongside `pilot_value`. The Lua bridge already
   exposes `pilot_id` on each unit dict, so this is a pass-through — verify at
   the call site.

### Lookup helper
```rust
fn pilot_flags_from_id(pilot_id: &str) -> PilotFlags {
    match pilot_id {
        "Pilot_Soldier"    => PilotFlags::SOLDIER,
        "Pilot_Rock"       => PilotFlags::ROCK,
        "Pilot_Repairman"  => PilotFlags::REPAIRMAN,
        _ => PilotFlags::empty(),
    }
}
```

### Tests
`#[cfg(test)]` in the relevant modules:
- `simulate.rs::test_pilot_soldier_immune_to_web` — Scorpion webs Camila → no
  WEB flag set, move_speed unchanged.
- `simulate.rs::test_pilot_rock_immune_to_fire_apply` — Flame weapon on
  Ariadne → no FIRE flag.
- `enemy.rs::test_pilot_rock_skips_fire_tick` — FIRE flag pre-set on Ariadne
  (defensive) → no damage on tick.
- `simulate.rs::test_pilot_repairman_pushes_adjacent_enemies` — Harold
  repairs, neighbouring enemies bump into buildings / drown / push.

## Edge cases flagged

- **Camila smoke-immunity latent**: wire flag; actual guard arrives when the
  mech-on-smoke-attack-cancel bug is fixed. Not today's task.
- **Pilot death stops passives**: when `hp <= 0`, the flag is still on the
  Unit struct but every hook already checks `u.alive()` / `u.hp > 0` before
  applying, so there's no regression. Verified by reading each hook site.
- **Action-order dependence**: none of these three passives introduce it.
  Repair-push runs at action execution, not on mech ordering. Fire/web
  immunity are idempotent. No solver.rs rework.

## Rollback anchor
Pre-bump corpus will be archived as
`recordings/failure_db_snapshot_sim_v2.jsonl` before the SIMULATOR_VERSION
bump. If the regression fails post-implementation, the diff is isolated to
the three hook clusters above plus the Unit bitflag.
