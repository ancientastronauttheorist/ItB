# Seed replay — Grid Defense resist hypotheses

Into the Breach is deterministic from the player's side except for the per-hit
Grid Defense "resist" roll (default 15%). To predict those outcomes we'd like
to know which RNG stream the resist check is drawn from.

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
  is fine for every seed we've observed (all four of `aiSeed` 560415071 /
  407184687 / 47698094 and `master_seed` 86321070 / 343639449 fit).
* `r = (rand() % RAND_MAX) / RAND_MAX` and `math.random(u) = floor(r*u)+1`.
  The `% RAND_MAX` is a no-op whenever `rand() < RAND_MAX`, which on
  Park-Miller is always. We reproduce it faithfully for clarity.

### 1.2 macOS libc `rand()`

The relevant ITB binary is `/Applications`-bundled and links against the
system libc. Empirically (probe program below), the stream is Park-Miller
aka "minimal standard" Lehmer:

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

This is the canonical Park-Miller LCG. On Linux/glibc it would instead be
TYPE_3 additive Fibonacci, so anyone porting this tool to a Linux build of
ITB would need to swap the generator. **Our implementation is macOS-only
and documents that in the module docstring.** If the game turns out to ship
a bundled PRNG via its own `require('random')` (it does not, based on
grepping `scripts/`; see §5), that would invalidate this section entirely.

### 1.3 `math.random(100)` ∈ [1,100]

Binning: `floor((rand() % RAND_MAX) / RAND_MAX * 100) + 1`.

Because `rand() ∈ [1, 2**31 − 2]` with Park-Miller, the ratio is in
`[1/(2**31 - 1), (2**31 - 2)/(2**31 - 1)]` ≈ `[4.7e-10, 1 − 4.7e-10]`, so
`floor(r*100) ∈ {0, …, 99}` and `math.random(100) ∈ {1, …, 100}` as
expected. 1 is reachable (when `rand()` is tiny) and 100 is reachable (when
`rand() ≈ RAND_MAX`). A "resist" under a 15% Grid Defense is exactly
`math.random(100) <= 15`.

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
  read. Comparing consecutive turns yields "grid damage observed at turn T",
  used to distinguish `all resisted` from `none resisted` from `some resisted`.

## 3. Hypotheses

Let `R(seed, k)` be the k-th (0-indexed) result of `math.random(100)` from
`math.randomseed(seed)`. A resist occurs iff `R ≤ 15`. For a turn with K
building-targeting attacks, let the observed damage be D (number of
buildings that actually took damage). Then exactly `K − D` resists occurred.

### H1 — `ai_seed` is the resist RNG

**Claim.** The game calls `math.randomseed(aiSeed)` at the start of each
enemy phase (or mission start) and draws resist rolls from that stream. The
offset K ≥ 0 is some constant plus a known per-turn prefix consumed by
unrelated AI operations (pathfinding tie-breaks, animation jitter, …).

**Confirmation.** Find a single non-negative integer K such that, for every
probe row where `ai_seed` is non-null:

* at positions `K, K+1, …, K+K_row−1` of `rolls(ai_seed, …)` the count of
  values ≤ 15 equals `K_row − D_row`.

Additionally the *which* attacks resisted should align: attack index `j`
resisted iff roll `K + j ≤ 15`. (If the game shuffles attack order vs. the
telegraph order we capture, this weaker predicate still holds.)

**Rejection.** If exhaustive search over `K ∈ [0, K_max]` (say K_max = 1024)
yields no offset consistent with every observed turn — and the observed
turns are not all degenerate (all K_row = D_row = 0 means no information) —
H1 is rejected.

**Observed-support check.** Turns 2, 3, 4 in our log have `ai_seed` set.
Turns 2 and 3 share `ai_seed = 560415071`; if H1 holds with a constant K
per turn, the rolls at that K must predict two DIFFERENT building-attack
outcomes from the same seed — which is only possible if the offset itself
varies per turn (e.g. K advances with each AI operation performed within a
mission). This is the key diagnostic: **same-seed back-to-back turns with
different resist outcomes ⇒ the RNG state is not reset to seed each turn**,
so H1 in its simple form ("reseed per turn") is false. A weaker form —
"reseed per mission, K advances" — is still viable.

### H2 — `master_seed` drives resists, `ai_seed` is AI-only

**Claim.** `ai_seed` is a separate stream reserved for AI decisions (path
choice, target choice, ability order). Grid Defense resists use the run-
level `GameData.seed` directly or a derived per-turn seed like
`master_seed + turn_number` / `master_seed xor turn_hash`.

**Confirmation.** Same offset search as H1 but starting from
`seed(master_seed)`, or from a derivation `seed(master_seed + turn)`,
`seed(master_seed xor turn)`, etc. If any such derivation yields a
self-consistent offset across the probe log and no derivation of
`ai_seed` does, H2 wins.

**Rejection.** No derivation works; or the offset that works happens to
also work for `ai_seed` (coincidence — more probe data required).

### H3 — resists use a separate non-Lua RNG

**Claim.** The resist check is in engine C++ and uses its own RNG, seeded
independently (e.g. from `std::random_device`, `time()`, or the platform
RNG). Lua seeds are irrelevant.

**Confirmation.** Neither H1 nor H2 yields a consistent offset for any
reasonable derivation, AND replaying the same save-file mission (via save
restore from `profile_Alpha/saveData.lua`) produces *different* resist
outcomes across runs despite identical Lua seeds. The latter is the
decisive test; it requires new probe data.

**Rejection.** H1 or H2 confirmed, OR save-restore replays produce
identical outcomes (which would rule out `std::random_device` but leave
`time()` still possible — time-seeded RNGs replay identically only if
seeded before the save is loaded).

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
* Same-seed turns 2/3 confirm the RNG state is not re-seeded each turn,
  so offset K must be turn-varying — but we have no model yet for "how
  many AI RNG draws occur between turn 2 and turn 3".

What the analyzer DOES show:

* Both candidate streams side-by-side for manual eyeball pattern-matching.
* Resist-threshold indices so you can quickly spot if, e.g., ai_seed
  stream has a resist at index 0 when turn 2 observed exactly one resist
  and one non-resist in-game.
* Attack order and targets for each turn (to align with stream positions
  if a per-attack offset-increment hypothesis is under test).

## 5. Known unknowns

* **Whether ITB uses `math.random` at all for resists.** A grep of the
  shipped Lua (`Into the Breach.app/Contents/Resources/scripts/`) for
  "resist" / "Grid Defense" would either point us at the implementation
  or confirm the check is engine-side. Not yet done here.
* **Whether the game uses `math.randomseed` per-mission.** If it only
  seeds once per save load, every mission shares state and the offset is
  essentially "total RNG draws since save load", which is effectively
  unknowable from our probe alone.
* **Number of non-resist RNG events per enemy phase.** Each AI decision
  (Spider spawn direction, Scarab move tie-break, Hornet target when
  multiple equally-good tiles exist, etc.) could consume 1–dozens of
  `math.random` calls. Without instrumentation of those call sites we
  cannot predict the offset K for a given turn.
* **Attack ordering.** The probe captures telegraphed attacks in bridge
  order. Engine execution order (and therefore which resist roll binds
  to which building) may differ. If H1 or H2 is confirmed by count but
  not by per-attack identity, attack-order reshuffling is the likely
  culprit.
* **`RAND_MAX` on the actual ITB binary.** We verified macOS libc uses
  `RAND_MAX = 2**31 − 1`, but ITB could statically link a different libc
  or bundle `lua_stdlib` with an override. Neither is standard on macOS
  Steam builds; we assume it does not.

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

If that table differs on another machine, the libc PRNG is different
(glibc/musl/BSD disagree here); update `seed_replay.py` before trusting
the analyzer.
