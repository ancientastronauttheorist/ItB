# Seed replay — Grid Defense resist hypotheses

Into the Breach exposes mostly repeatable player-side behavior, but its full
determinism boundary is not established. Enemy tie-breaking, spawn RNG, native
call order, hidden state, and the per-hit Grid Defense "resist" roll (default
15%) remain research targets. To predict resist outcomes, we first need to
identify which RNG boundary—if any of the captured ones—the check uses.

This document records the PRNG model, the candidate hypotheses, and what
decisive evidence would look like for each. The companion code is
`scripts/seed_replay.py` (pure-Python replay of the Lua/libc PRNG) and
`scripts/seed_probe_analyze.py` (the inspection CLI).

## 1. PRNG reference

### 1.1 Lua 5.1 `math.random` / `math.randomseed`

Lua 5.1's `lmathlib.c` wraps the C standard library directly:

```c
static int math_randomseed (lua_State *L) {
  srand(luaL_checkint(L, 1));
  return 0;
}

static int math_random (lua_State *L) {
  lua_Number r = (lua_Number)(rand()%RAND_MAX) / (lua_Number)RAND_MAX;
  switch (lua_gettop(L)) {
    case 0: { lua_pushnumber(L, r); break; }
    case 1: {                        /* math.random(u) */
      int u = luaL_checkint(L, 1);
      luaL_argcheck(L, 1 <= u, 1, "interval is empty");
      lua_pushnumber(L, floor(r * u) + 1);
      break;
    }
    case 2: {                        /* math.random(l, u) */
      int l = luaL_checkint(L, 1);
      int u = luaL_checkint(L, 2);
      luaL_argcheck(L, l <= u, 2, "interval is empty");
      lua_pushnumber(L, floor(r * (u - l + 1)) + l);
      break;
    }
    ...
  }
}
```

Key facts:

* Seeds are cast to C `int` before being passed to `srand`. Signed 32-bit
  is fine for the five example values recorded here: `aiSeed` 560415071 /
  407184687 / 47698094 and `master_seed` 86321070 / 343639449.
* `r = (rand() % RAND_MAX) / RAND_MAX` and `math.random(u) = floor(r*u)+1`.
  The `% RAND_MAX` is a no-op whenever `rand() < RAND_MAX`, which on
  Park-Miller is always. We reproduce it faithfully for clarity.

### 1.2 macOS libc `rand()`

On one sampled macOS environment, a standalone native probe of the host system
libc produced the Park-Miller ("minimal standard" Lehmer) stream below. This is
evidence for that libc-backed Lua `math.random` model, not proof that ITB's
native `random_int`, `random_bool`, spawn, or resist logic uses it:

```
state_{n+1} = (state_n * 16807) mod (2**31 − 1)   # RAND_MAX = 2**31 − 1
rand()     returns state_{n+1}
srand(0)   reseeds state to 123459876             # escapes the zero fixed point
```

Verified on this machine (macOS 26.4, xnu-11417 / libSystem) against a tiny
C program:

| `srand(S)` | first five `rand()` values |
|-----------:|-----------------------------|
| `srand(1)` | 16807, 282475249, 1622650073, 984943658, 1144108930 |
| `srand(0)` | 520932930, 28925691, 822784415, 890459872, 145532761 |
| `srand(560415071)` | 32822555, 1892868253, 613981513, 528365156, 388296547 |
| `srand(407184687)` | 1670135067, 201321132, 1317521499, 879949476, 1738449890 |

`tests/test_seed_replay.py` encodes a subset of those as golden values.

This is the canonical Park-Miller LCG. A Lua build proven to call the system
glibc `rand()` would instead see glibc's TYPE_3 additive generator. We have not
established that the native Linux ITB build uses that path, so platform alone
does not select the generator. **Our implementation models only the sampled
macOS environment and documents that in the module docstring.** Any bundled or
private native PRNG would invalidate this model for the corresponding binding.

### 1.3 `math.random(100)` ∈ [1,100]

Binning: `floor((rand() % RAND_MAX) / RAND_MAX * 100) + 1`.

Because `rand() ∈ [1, 2**31 − 2]` with Park-Miller, the ratio is in
`[1/(2**31 - 1), (2**31 - 2)/(2**31 - 1)]` ≈ `[4.7e-10, 1 − 4.7e-10]`, so
`floor(r*100) ∈ {0, …, 99}` and `math.random(100) ∈ {1, …, 100}` as
expected. 1 is reachable (when `rand()` is tiny) and 100 is reachable (when
`rand() ≈ RAND_MAX`). **If** a 15% Grid Defense check uses this exact
`math.random(100)` path, its threshold would be `<= 15`. Whether it does so is
the hypothesis under test, not an established mechanic.

## 2. Probe log format

`recordings/<run_id>/resist_probe.jsonl` — one JSON object per line. Fields
relevant here:

* `turn` — 1-indexed mission turn; harness re-reads state multiple times per
  turn, so duplicates exist. The analyzer dedupes by keeping the last.
* `ai_seed` — Lua's `Game.region.player.map_data.aiSeed`, which the engine
  updates between (some) turns.
* `master_seed` — `GameData.seed`, per-run.
* `telegraphed_building_attacks` — the Vek attacks queued this turn whose
  target is a building tile. These are the candidate resist-check events.
* `grid_power`, `grid_power_max` — observed grid power at the moment of the
  read. Consecutive values are only a contaminated proxy: environment, pushes,
  non-telegraphed damage, shields, and snapshot timing prevent them from
  distinguishing resist outcomes in the current data.

## 3. Hypotheses

For the simplified H1/H2 model only, let `R(seed, k)` be the k-th (0-indexed)
result of `math.random(100)` from `math.randomseed(seed)`, and model a resist as
`R ≤ 15`. Inferring a resist count from damage requires direct per-attack
observations: each eligible attack must be known to target an unshielded grid
building, repeated hits and push/environment effects must be separated, and
the building's damage result must be observed. Only under those controls would
`K − D` represent the resist count.

### H1 — `ai_seed` is the resist RNG

**Model.** The game calls `math.randomseed(aiSeed)` at the start of each
enemy phase (or mission start) and draws resist rolls from that stream. The
offset K ≥ 0 is some constant plus a possible per-turn prefix. Pathfinding
tie-breaks, animation, and other operations are candidate consumers, not
established consumers of this stream.

**Support for a preregistered bounded model.** Before inspecting outcomes, fix
the seed source, offset range, eligibility rules, and attack ordering. Find a
single non-negative integer K such that, for every training probe row where
`ai_seed` is non-null:

* at positions `K, K+1, …, K+K_row−1` of `rolls(ai_seed, …)` the count of
  values ≤ 15 equals `K_row − D_row`.

Additionally the *which* attacks resisted should align: attack index `j`
resisted iff roll `K + j ≤ 15`. (If the game shuffles attack order vs. the
telegraph order we capture, this weaker predicate still holds.)

Then require the same parameters to predict a separate build-keyed holdout and
confirm the relevant calls with a trace. A fit on the discovery rows alone is
support, not confirmation.

**Bounded-model rejection.** If exhaustive search over the preregistered
`K ∈ [0, K_max]` yields no offset consistent with informative, directly
observed turns, only that bounded constant-offset model is rejected. Larger or
variable offsets and different call ordering remain unresolved.

**Potential diagnostic.** Turns 2, 3, and 4 in the current log have `ai_seed`
set, and turns 2 and 3 share `ai_seed = 560415071`. If future direct
per-attack evidence shows different resist outcomes on those same-seed turns
under otherwise identical modeled calls, a constant per-turn reseed-and-offset
model would be contradicted. The current log cannot recover those outcomes, so
it neither confirms per-turn reseeding nor confirms a continuously advancing
mission stream.

### H2 — `master_seed` drives resists, `ai_seed` is AI-only

**Model.** `ai_seed` is a separate stream reserved for AI decisions (path
choice, target choice, ability order). Grid Defense resists use the run-
level `GameData.seed` directly or a derived per-turn seed like
`master_seed + turn_number` / `master_seed xor turn_hash`.

**Support for a preregistered bounded model.** Predeclare a small finite set of
derivations such as `seed(master_seed)`, `seed(master_seed + turn)`, and
`seed(master_seed xor turn)`, plus the offset range. A derivation that fits
training rows and independently predicts a build-keyed holdout supports H2
over the tested H1 variants; it does not prove causality without a boundary
trace.

**Bounded-model rejection.** Failure of every preregistered derivation and
offset rejects only that finite family. Searching open-ended derivations until
one fits is overfitting, not evidence. A derivation that also fits `ai_seed`
remains ambiguous.

### H3 — resists use separate native RNG state

**Claim.** The resist check uses native RNG state not reconstructible from the
captured Lua seeds alone. That state could still be deterministic and derived
from save or engine state; "native" does not imply `random_device` or time.

**Supporting evidence.** Neither H1 nor H2 yields a consistent offset for
reasonable derivations, especially after build-keyed traces establish that the
tested Lua stream and call order are complete. Different outcomes after
restoring apparently identical saves would prove that the capture omitted
state or inputs, not which native generator supplied them.

**Rejection.** A build-keyed trace confirms H1 or H2 and reproduces resist
outcomes across an independent holdout. Identical save restores alone do not
reject H3 because a private native RNG may be deterministic and serialized.

## 4. What the analyzer can and cannot decide today

`seed_probe_analyze.py` prints the first N rolls from each candidate seed
and the "resist" indices (where roll ≤ 15). It does NOT auto-search for K
because:

* For a clean decision we need the *observed* per-turn resist outcomes,
  i.e. "of the K_row building attacks, M actually hit and K_row − M were
  resisted." Our probe log captures `grid_power` before the enemy phase
  but not `grid_power` after; the next turn's `grid_power` is a proxy that
  also includes environmental damage, push-into-building damage, and
  damage to non-telegraphed tiles. In the current log, `grid_Δ` across
  turns is 0 every time (probe snapshotted after the damage already
  applied), so we can't tell resist from no-resist from pure-damage.
* Same-seed turns 2/3 could become a useful reseed diagnostic after direct
  per-attack outcomes are captured. The current rows do not reveal whether
  offset K is constant, turn-varying, or applicable at all.

What the analyzer DOES show:

* Both candidate streams side-by-side for manual eyeball pattern-matching.
* Resist-threshold indices for comparison once a future probe records direct,
  eligible per-attack resist/non-resist outcomes.
* Attack order and targets for each turn (to align with stream positions
  if a per-attack offset-increment hypothesis is under test).

## 5. Known unknowns

* **Whether ITB uses `math.random` at all for resists.** A grep of the
  shipped Lua (`Into the Breach.app/Contents/Resources/scripts/`) for
  "resist" / "Grid Defense" may point at an implementation. Absence only
  narrows the search; generic bindings, dynamically selected code, and other
  Lua/native paths remain possible.
* **Whether the game uses `math.randomseed` per-mission.** If it only
  seeds once per save load, every mission shares state and the offset is
  essentially "total RNG draws since save load", which is effectively
  unknowable from our probe alone.
* **Number of non-resist RNG events per enemy phase.** Each AI decision
  (Spider spawn direction, Scarab move tie-break, Hornet target when
  multiple equally-good tiles exist, etc.) may consume zero or more calls from
  this stream. Without instrumentation we cannot identify the consumers or
  predict offset K.
* **Attack ordering.** The probe captures telegraphed attacks in bridge
  order. Engine execution order (and therefore which resist roll binds
  to which building) may differ. If H1 or H2 is confirmed by count but
  not by per-attack identity, attack-order reshuffling is one candidate
  alongside intervening draws, chance fits, and eligibility/modeling errors.
* **The sampled binary/dependency identity.** The standalone probe verified one
  macOS libc uses `RAND_MAX = 2**31 − 1`; it did not prove which dependency or
  RNG the sampled ITB binding calls. Future conclusions must record the exact
  platform, architecture, executable/native hashes, depot/build, and content
  revisions instead of relying on a static-link assumption.

## 6. Reproducing the reference stream (sanity check)

```bash
python3 scripts/seed_replay.py 560415071 -n 10 --raw
# expected (verified against a native C program on this machine):
# i  rand()      random(100)
# 0  32822555    2
# 1  1892868253  89
# 2  613981513   29
# 3  528365156   25
# 4  388296547   19
# ...
```

The Python table is deterministic on every host because the tool does not call
the host libc. To characterize another libc, compile and run the native C probe
there and compare its output with this fixed table. Do not infer host behavior
by merely rerunning the Python model.
