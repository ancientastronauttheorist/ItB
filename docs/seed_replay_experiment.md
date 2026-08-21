# Seed-replay experiment — can we reproduce ITB spawns offline?

**Status:** candidate streams were printed for two recorded turns. A reviewer
noticed no obvious manual alignment; mechanical matching was not implemented.
The limitation is documented. A later exact-build Windows boundary pass mapped
the native RNG but cannot retroactively identify these recordings or recover
their missing call order.

This document is the writeup for `scripts/seed_replay_experiment.py`. It is
*post-hoc validation only* — never used in any live decision loop.

## TL;DR

The two noisy recorded cases showed no obvious alignment under manual
inspection of simple Park-Miller candidate streams. The experiment did not map
the spawn pool or perform a formal call-order/offset fit, so it cannot determine
whether `master_seed` + `ai_seed` are sufficient. The Lua spawner calls
native-visible `random_int` and `random_bool` at known semantic points, but the
recording manifests do not contain platform, executable/native hashes,
depot/build identity, libc identity, or content revisions. Their engine
provenance is therefore unverified. A later pass proved that the pinned Windows
PE uses an MSVC-style shared RNG and mapped its seeding ritual, but that does not
identify which RNG backed these recordings or recover their complete call
order.

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
- **It catalogs what we DO know** (algorithm in Lua, seed sources we capture,
  one sampled macOS libc PRNG identity, and the later pinned Windows native
  map) and what is blocked (recording identity, hidden state, and complete
  consumption order).
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

For these two historical recordings, the blockers are missing build identity,
hidden state, and complete call order:

- The pinned Windows executable's registration mechanism, four binding bodies,
  shared RNG core, seed setter, and enemy-planning seed ritual are now mapped.
  See `docs/itb_native_anchor_research.md`. Those facts apply only to that
  exact executable hash.
- `nm -gU` on the unrelated-provenance local `itb_test.dylib` exports only
  `_luaopen_itb_test`; this does not locate the game's RNG bindings.
- The recordings do not say whether they came from that Windows PE or the
  sampled macOS environment, so choosing either generator would invent
  provenance.
- Other engine systems consume the shared Windows RNG between semantic Lua
  decisions. Static analysis proves native AI calls, including tie-breaking,
  but runtime attribution is still required to identify and count the exact
  sequence that led to each spawn.

To get a real prediction match we would need a combination of:

1. **Live-game RNG instrumentation.** On a disposable non-achievement install,
   activate one dormant `_G.random_int` / `_G.random_bool` wrapper at a time,
   then compare it with bounded native caller evidence. **(Out of scope for this
   historical experiment; it would touch installed runtime code.)**
2. **Targeted native boundary research — completed for the pinned Windows
   build.** The remaining requirement is controlled dynamic validation; do not
   transfer the result to a different binary or assume a local dylib contains
   the body.
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
- `docs/itb_native_anchor_research.md` — exact Windows boundary follow-up.

## Honest scorecard

- **Mechanical matcher:** not implemented.
- **Manual observation:** no obvious alignment noticed in two displayed,
  noisy prefixes; this is not a rejection test.
- **Useful artifacts produced:** documentation of the algorithm flow, a reusable forensic CLI, a clear list of what's blocked.
- **Should we integrate this into a live path?** **No.** The experiment produced
  no validated spawn predictor. Keep it offline until build-keyed traces support
  a behavioral model.
