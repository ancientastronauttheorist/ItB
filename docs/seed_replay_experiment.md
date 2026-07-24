# Seed-replay experiment — can we reproduce ITB spawns offline?

**Status:** candidate streams were printed for two recorded turns. A reviewer
noticed no obvious manual alignment; mechanical matching was not implemented.
The limitation is documented; offline tools downstream of this insight are
described below.

This document is the writeup for `scripts/seed_replay_experiment.py`. It is
*post-hoc validation only* — never used in any live decision loop.

## TL;DR

The two noisy recorded cases showed no obvious alignment under manual
inspection of simple Park-Miller candidate streams. The experiment did not map
the spawn pool or perform a formal call-order/offset fit, so it cannot determine
whether `master_seed` + `ai_seed` are sufficient. The Lua spawner calls
native-visible `random_int` and `random_bool` at known semantic points, but we
have not mapped their implementation, state, seeding ritual, or complete call
order. The recording manifests do not contain platform, executable/native
hashes, depot/build identity, libc identity, or content revisions, so their
engine provenance is unverified. Separately, strings in the inventoried Windows
PE expose `random_int`, `random_bool`, `aiSeed`, and `seed`; that does not prove
which RNG backed these recordings or whether either path shares state with
Lua's `math.random`.

The locally observed `itb_test.dylib` is not a trustworthy origin for these
claims. The official macOS depot does not list it, and the local artifact's
provenance is unresolved. It must not be described as a shipped core engine
library without direct build-keyed evidence.

That said, the experiment was still worth running:

- **It exposed candidate prefixes for inspection.** A reviewer noticed no
  obvious alignment in the displayed Park-Miller prefixes seeded by
  `ai_seed`, `master_seed`, or the post-turn `ai_seed`. No window scan, pool
  mapping, or formal call-order fit was performed. With only two noisy,
  build-unkeyed cases, this does not rule out shared Park-Miller state or
  another offset model.
- **It catalogs what we DO know** (algorithm in Lua, seed sources we
  capture, and one sampled macOS libc PRNG identity) and what is blocked
  (native binding identity, hidden state, and complete consumption order).
- **It justifies why we keep capturing `ai_seed`** in `resist_probe.jsonl`
  and `bridge_state.mission_seeds[<region>].ai_seed` even though it
  has not been validated as an offline replay key. It still functions as a
  fingerprint for run/turn identity in regression analysis.

## What was tested

`scripts/seed_replay_experiment.py` analyzes two recorded turn pairs:

| Case | Run | Mission | Pre-turn → Post-turn | New uids observed |
|------|-----|---------|----------------------|--------------------|
| 1 | `20260425_005049_742` | `Mission_HornetBoss` (m02) | 2 → 3 | Scorpion2 @ E4, Scorpion1 @ B3, Scorpion1 @ C3, Firefly1 @ C2 |
| 2 | `20260425_185532_218` | `Mission_Train` (m05) | 1 → 2 | Firefly1 @ D2, Scorpion2 @ C4, Spiderling1 @ D5, WebbEgg1 @ B5 |

For each case:

1. The pre-turn `bridge_state` contributes `master_seed`, `mission_seeds[<active>].ai_seed`, the `spawning_tiles` list (alarmed eggs telegraphing *next* enemy phase's spawns), and `remaining_spawns`.
2. The post-turn `bridge_state` is diffed against pre-turn to identify new enemy uids and where they ended up (after their first move). This is a new-unit diff, not a ground-truth direct-spawn set.
3. New Spiderling and WebbEgg uids are conservatively labeled as lifecycle candidates when the pre/post evidence supports a hatch or Spider-created egg.
4. Park-Miller is seeded from each candidate seed (`ai_seed`-pre, `ai_seed`-post, `master_seed`) using the existing `scripts/seed_replay.py` reproducer, which was checked against one sampled macOS libc environment (see `tests/test_seed_replay.py`).
5. The number requested by `--rolls` of `math.random(5)`, `math.random(7)`, and `math.random(8)` outputs is printed. These are candidate pool sizes, not a recovered engine pool.
6. The script performs no pool mapping or formal call-order/offset fit and does not auto-declare a match. It prints streams for manual inspection.

The two recording manifests predate Observatory build identity and do not pin
their platform, executable, native libraries, depot/build, libc, or content
revisions. They are useful exploratory artifacts, not build-keyed RNG evidence.

## What was found

For both cases, no obvious alignment was noticed in the displayed candidate
prefixes. This is a manual observation from two noisy cases, not a mechanical
negative result:

- Case 1's new-UID sequence is `[Scorpion2, Scorpion1, Scorpion1, Firefly1]`.
  `Scorpion2` and `Scorpion1` can share one base-pawn choice followed by an
  independent upgrade decision, so raw type equality does not imply repeated
  pool indices. The exact pool, its order, branch draws, and upgrade draws were
  not recovered.
- Case 2's new-UID sequence is
  `[Firefly1, Scorpion2, Spiderling1, WebbEgg1]`. The pre/post snapshots support
  two lifecycle-created units: pre-existing `WebbEgg1` uid 500 is replaced by
  `Spiderling1` uid 542, and a pre-existing `Spider2` can explain new
  `WebbEgg1` uid 571. `Firefly1` uid 501 and `Scorpion2` uid 502 are the two
  plausible direct-spawn candidates corresponding to the two alarmed tiles.

## Why this is hard (and what we'd need to change)

The blocker is the `random_int` / `random_bool` boundary and the hidden engine
state around it:

- `strings` on the sampled main executable confirms the binding names are
  resident there. Their registration mechanism and function bodies remain
  unmapped.
- `nm -gU` on the unrelated-provenance local `itb_test.dylib` exports only
  `_luaopen_itb_test`; this does not locate the game's RNG bindings.
- We do not know whether they:
  - call `rand()` (sharing libc state with Lua's `math.random`),
  - own a private `std::mt19937` seeded from `aiSeed`,
  - or use a third RNG (xorshift, MINSTD, Knuth's TYPE_3, etc.).
- Even if they share libc `rand()` state, other engine systems may consume RNG
  between turns. AI planning, target choice, and animation are candidates, not
  established consumers of the same stream. Without instrumentation we cannot
  identify or count those calls.

To get a real prediction match we would need either:

1. **Live-game RNG instrumentation.** Add a Lua hook in `modloader.lua` that wraps `random_int` / `random_bool` and logs every call with its result during an enemy phase. Then we can verify Park-Miller equivalence empirically. **(out of scope for this experiment — would touch live bridge code.)**
2. **Targeted native boundary research.** On an exact platform/build/hash,
   anchor the Lua registration strings in the main executable and validate the
   mapped behavior empirically. Do not assume a local dylib contains the body.
3. **Differential observation.** Capture *thousands* of (ai_seed → first-spawn-type) pairs and treat it as a regression problem: can we learn a function `(ai_seed) → spawn_index_offset` empirically? Plausible but expensive.

## What this enables anyway

Even with prediction blocked, `ai_seed` capture remains valuable for:

- **Run/turn fingerprinting.** `(master_seed, ai_seed, mission_id, turn)` is a
  useful grouping key, but it is not proof of identical full engine state.
  Hidden RNG position, queue state, or other native fields may differ.
- **Post-hoc determinism checks.** A changed `ai_seed` after a controlled replay
  is evidence of divergence worth investigating, not sufficient proof of the
  cause.
- **Detecting possible re-seeds.** Seed transitions can identify candidates for
  tracing; without observing the RNG boundary, they do not prove a reseed event.
- **Future Grid Defense work.** `seed_probe_analyze.py` can compare candidate
  streams with resist evidence, but the RNG function, number of draws, and call
  ordering remain hypotheses.

## Files

- `scripts/seed_replay_experiment.py` — the experiment runner (this work).
- `scripts/seed_replay.py` — pure-Python Park-Miller / Lua 5.1 `math.random` reproducer (existing).
- `docs/seed_replay_hypotheses.md` — formal H1/H2/H3 hypotheses for the resist-roll problem (existing).
- `tests/test_seed_replay.py` — golden values against macOS libc (existing).

## Honest scorecard

- **Mechanical matcher:** not implemented.
- **Manual observation:** no obvious alignment noticed in two displayed,
  noisy prefixes; this is not a rejection test.
- **Useful artifacts produced:** documentation of the algorithm flow, a reusable forensic CLI, a clear list of what's blocked.
- **Should we integrate this into a live path?** **No.** The experiment produced
  no validated spawn predictor. Keep it offline until build-keyed traces support
  a behavioral model.
