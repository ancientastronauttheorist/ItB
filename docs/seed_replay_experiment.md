# Seed-replay experiment — can we reproduce ITB spawns offline?

**Status:** experiment ran on two recorded turns. **Result: no match.** The
limitation is documented; offline tools downstream of this insight are
described below.

This document is the writeup for `scripts/seed_replay_experiment.py`. It is
*post-hoc validation only* — never used in any live decision loop.

## TL;DR

We cannot mechanically reproduce ITB spawn outcomes from the captured
`master_seed` + `ai_seed` alone, because `random_int` and `random_bool`
(the two C functions the Lua spawner calls — see `spawner_backend.lua`
lines 209, 222, 245) are defined inside `itb_test.dylib`, the engine's
stripped C++ shared library. We can read their *names* (`strings` on the
main binary surfaces `random_int` / `random_bool` / `aiSeed` / `seed`), but
not their RNG type, their seeding ritual, or whether they share state with
Lua's `math.random` (which IS Park-Miller — see `seed_replay.py`).

That said, the experiment was still worth running:

- **It rules out the easy hypothesis.** No window of the Park-Miller stream
  seeded by `ai_seed` (or `master_seed`, or the post-turn `ai_seed`)
  produces an obvious structural alignment with the observed spawn-type
  sequences across the 30 leading rolls. So `random_int` is not a thin
  passthrough to `math.random` consumed in Lua-level call order.
- **It catalogs what we DO know** (algorithm in Lua, seed sources we
  capture, libc PRNG identity) and what is blocked (the C++ call order /
  RNG instance binding inside `itb_test.dylib`).
- **It justifies why we keep capturing `ai_seed`** in `resist_probe.jsonl`
  and `bridge_state.mission_seeds[<region>].ai_seed` even though it
  cannot be replayed offline. It still functions as a fingerprint for
  run/turn identity in regression analysis.

## What was tested

`scripts/seed_replay_experiment.py` analyzes two recorded turn pairs:

| Case | Run | Mission | Pre-turn → Post-turn | New uids observed |
|------|-----|---------|----------------------|--------------------|
| 1 | `20260425_005049_742` | `Mission_HornetBoss` (m02) | 2 → 3 | Scorpion2 @ E4, Scorpion1 @ B3, Scorpion1 @ C3, Firefly1 @ C2 |
| 2 | `20260425_185532_218` | `Mission_Train` (m05) | 1 → 2 | Firefly1 @ D2, Scorpion2 @ C4, Spiderling1 @ D5, WebbEgg1 @ B5 |

For each case:

1. The pre-turn `bridge_state` contributes `master_seed`, `mission_seeds[<active>].ai_seed`, the `spawning_tiles` list (alarmed eggs telegraphing *next* enemy phase's spawns), and `remaining_spawns`.
2. The post-turn `bridge_state` is diffed against pre-turn to extract the ground-truth set of new enemy uids and where they ended up (after their first move).
3. Park-Miller is seeded from each candidate seed (`ai_seed`-pre, `ai_seed`-post, `master_seed`) using the existing `scripts/seed_replay.py` reproducer (verified-correct against macOS libc — see `tests/test_seed_replay.py`).
4. The first 50 outputs of `math.random(5)`, `math.random(7)`, `math.random(8)` are printed. These are reasonable upper-bounds for the spawner's `random_int` calls — `5` matches `curr_weakRatio[2]` and `start_spawns` constants, `7` and `8` match plausible sizes of the per-island `GAME:GetSpawnList()` pool.
5. The script does NOT auto-declare a match. It prints the streams alongside the observed type sequence so a human can confirm or reject visually.

## What was found

For both cases, *no* leading window of any stream aligns with the observed type sequence under any obvious mapping. Examples:

- Case 1: observed `[Scorpion2, Scorpion1, Scorpion1, Firefly1]`. None of the seeded streams produce a 4-tuple where the same index appears at positions 1 and 2 followed by a different index at positions 0 and 3 (the structural shape required if the spawner is picking from a pool list).
- Case 2: observed `[Firefly1, Scorpion2, Spiderling1, WebbEgg1]`. Even more challenging — `Spiderling1` and `WebbEgg1` are spawn-emergent (Spider's lifecycle), not direct `Spawner:NextPawn` outputs. Three of the four observed "spawns" are likely not spawns at all: they're the *result* of a Spider2 already on the board hatching its egg + an Alpha/Vek emerging from a previous turn's eggs. So the case is doubly noisy as a spawn-prediction test.

## Why this is hard (and what we'd need to change)

The blocker is the `random_int` / `random_bool` binding:

- `nm -gU itb_test.dylib` exports only `_luaopen_itb_test`. All other symbols are static.
- `strings .../Into the Breach` confirms the names `random_int` and `random_bool` are resident in the main binary, not `itb_test.dylib` (which contains different code paths). They are likely registered via `lua_register` from the C++ side.
- We do not know whether they:
  - call `rand()` (sharing libc state with Lua's `math.random`),
  - own a private `std::mt19937` seeded from `aiSeed`,
  - or use a third RNG (xorshift, MINSTD, Knuth's TYPE_3, etc.).
- Even if (the most optimistic case) they share libc `rand()` state, the engine consumes RNG between turns for: AI movement planning, attack-target pre-rolls, animation jitter, and other systems. Without instrumentation we cannot count those consumptions.

To get a real prediction match we would need either:

1. **Live-game RNG instrumentation.** Add a Lua hook in `modloader.lua` that wraps `random_int` / `random_bool` and logs every call with its result during an enemy phase. Then we can verify Park-Miller equivalence empirically. **(out of scope for this experiment — would touch live bridge code.)**
2. **Binary diffing of the engine.** Disassemble `itb_test.dylib` / the main binary in Hopper/Ghidra to find the `random_int` body. **(huge time cost; the engine is closed-source.)**
3. **Differential observation.** Capture *thousands* of (ai_seed → first-spawn-type) pairs and treat it as a regression problem: can we learn a function `(ai_seed) → spawn_index_offset` empirically? Plausible but expensive.

## What this enables anyway

Even with prediction blocked, `ai_seed` capture remains valuable for:

- **Run/turn fingerprinting.** Two recordings with the same `(master_seed, ai_seed, mission_id, turn)` are *guaranteed* to be the same engine state. This makes regression bisection deterministic.
- **Post-hoc determinism checks.** If a recorded turn is replayed inside the game (via `recover_state` / `undo`) and produces a different `ai_seed`, that signals a desync we can flag.
- **Detecting silent re-seeds.** The engine occasionally re-seeds (e.g., on save/load). The capture cadence in `resist_probe.jsonl` lets us detect those events.
- **Future grid-defense resist work.** The companion `seed_probe_analyze.py` tool already uses this data for the 15% resist-roll hypothesis; that path is independent of the spawn problem and may yet pay off (resist rolls are simpler — one `random_int(100)` per attack — and the call ordering may be tractable).

## Files

- `scripts/seed_replay_experiment.py` — the experiment runner (this work).
- `scripts/seed_replay.py` — pure-Python Park-Miller / Lua 5.1 `math.random` reproducer (existing).
- `docs/seed_replay_hypotheses.md` — formal H1/H2/H3 hypotheses for the resist-roll problem (existing).
- `tests/test_seed_replay.py` — golden values against macOS libc (existing).

## Honest scorecard

- **Match declared:** 0 / 2 cases.
- **Useful artifacts produced:** documentation of the algorithm flow, a reusable forensic CLI, a clear list of what's blocked.
- **Should we integrate this into a live path?** **No.** The experiment confirms there's nothing to integrate — we cannot predict spawns from seeds alone today, and the user explicitly scoped this to offline post-hoc validation.
