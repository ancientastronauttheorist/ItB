#!/usr/bin/env python3
"""
seed_replay.py — Pure-Python replay of Lua 5.1's `math.random` / `math.randomseed`
as they behave in Into the Breach on macOS.

Lua 5.1's math library (lmathlib.c) wraps the C standard library's rand()/srand()
directly:

    static int math_randomseed(lua_State *L) {
      srand(luaL_checkint(L, 1));
      return 0;
    }

    static int math_random(lua_State *L) {
      lua_Number r = (lua_Number)(rand()%RAND_MAX) / (lua_Number)RAND_MAX;
      switch (lua_gettop(L)) {
        case 0: { lua_pushnumber(L, r); break; }
        case 1: {                                 /* random(u) */
          int u = luaL_checkint(L, 1);
          lua_pushnumber(L, floor(r*u)+1);
          break;
        }
        case 2: {                                 /* random(l,u) */
          int l = luaL_checkint(L, 1);
          int u = luaL_checkint(L, 2);
          lua_pushnumber(L, floor(r*(u-l+1))+l);
          break;
        }
        ...
      }
    }

So to reproduce Lua 5.1 `math.random` outcomes we need only reproduce the macOS
libc `rand()` sequence for a given `srand(seed)`.

macOS libc `rand()` (verified empirically against /usr/lib/libSystem on
darwin 25.x; see docs/seed_replay_hypotheses.md) is the classical Park-Miller
"minimal standard" Lehmer LCG:

    state_{n+1} = (state_n * 16807) mod (2**31 - 1)
    rand() returns state_{n+1}
    RAND_MAX = 2**31 - 1 = 2147483647

with one special case: `srand(0)` is treated as `srand(123459876)` (the libc
code reseeds zero to a fixed non-zero state so the stream is never stuck at 0).

Empirical golden values (confirmed via a tiny C probe on this machine):
    srand(1):  rand() -> 16807, 282475249, 1622650073, 984943658, 1144108930, ...
    srand(0):  rand() -> 520932930, 28925691, 822784415, 890459872, 145532761, ...

Usage (module):
    from seed_replay import seed, random, randint, rolls
    seed(560415071)
    random()               # -> float in [0, 1)
    random(100)            # -> int in [1, 100]
    random(1, 6)           # -> int in [1, 6]

Usage (CLI):
    python3 scripts/seed_replay.py SEED [-n N] [--upper U]
        Prints the first N rolls of math.random(U) from seed(SEED).
        Defaults: N=20, U=100.
"""
from __future__ import annotations

import argparse
import math
from typing import Optional


# ---- Park-Miller / macOS libc rand() ------------------------------------

# Lehmer constants
_A = 16807                 # multiplier
_M = 2147483647            # modulus = 2**31 - 1 == RAND_MAX on macOS
RAND_MAX = _M

# Module-global state, mirroring libc's single hidden state.
_state: int = 1


def _normalize_seed(s: int) -> int:
    """Replicate `srand(int s)` cast semantics.

    Lua's `luaL_checkint` casts the Lua number to C `int`, which on all
    platforms ITB runs on is 32-bit signed.  libc's `srand` takes an
    `unsigned int`, so negative seeds wrap mod 2**32.  We model the same by
    first reducing mod 2**32, then applying the Park-Miller domain constraint.
    """
    s = int(s) & 0xFFFFFFFF
    # Park-Miller state must be in [1, _M - 1].  macOS libc reseeds 0 to a
    # hard-coded non-zero state (123459876) so the stream escapes the zero
    # fixed point.  For s > _M we reduce mod (_M - 1) + 1 which keeps the
    # state in the valid range; any standards-compliant LCG srand will also
    # normalize somehow, but since every seed we care about fits in the
    # [1, _M-1] interval we only need the zero special case in practice.
    if s == 0:
        return 123459876
    if s >= _M:
        s = (s % (_M - 1)) + 1
    return s


def seed(s: int) -> None:
    """Equivalent to Lua's `math.randomseed(s)` / C's `srand(s)` on macOS."""
    global _state
    _state = _normalize_seed(s)


def _rand_raw() -> int:
    """One step of the Park-Miller LCG.  Equivalent to macOS libc `rand()`."""
    global _state
    _state = (_state * _A) % _M
    return _state


def random(a: Optional[int] = None, b: Optional[int] = None):
    """Replicate Lua 5.1 `math.random`.

    - `random()`       -> float in [0, 1)
    - `random(u)`      -> int in [1, u]
    - `random(l, u)`   -> int in [l, u]
    """
    raw = _rand_raw()
    # Lua computes: r = (lua_Number)(rand() % RAND_MAX) / (lua_Number)RAND_MAX
    # `raw % RAND_MAX` is a no-op when raw < RAND_MAX (which is always true
    # for Park-Miller since state in [1, M-1] and RAND_MAX = M), but we
    # reproduce it faithfully for bitwise-identical semantics.
    r = (raw % RAND_MAX) / RAND_MAX
    if a is None:
        return r
    if b is None:
        u = int(a)
        if u < 1:
            raise ValueError("interval is empty")
        return int(math.floor(r * u)) + 1
    l = int(a)
    u = int(b)
    if l > u:
        raise ValueError("interval is empty")
    return int(math.floor(r * (u - l + 1))) + l


def randint(a: int, b: int) -> int:
    """Convenience alias for `random(a, b)`."""
    return random(a, b)


def rolls(s: int, n: int, upper: int = 100) -> list[int]:
    """Return the first `n` results of `math.random(upper)` from `seed(s)`.

    Pure (does not touch module state of the *caller*'s previous seed):
    we save & restore `_state` around the call.
    """
    global _state
    saved = _state
    try:
        seed(s)
        return [random(upper) for _ in range(n)]
    finally:
        _state = saved


def floats(s: int, n: int) -> list[float]:
    """Return the first `n` results of `math.random()` from `seed(s)`."""
    global _state
    saved = _state
    try:
        seed(s)
        return [random() for _ in range(n)]
    finally:
        _state = saved


def raw_sequence(s: int, n: int) -> list[int]:
    """Return the first `n` raw `rand()` outputs from `srand(s)`.

    Useful for unit tests and cross-checking against a C program.
    """
    global _state
    saved = _state
    try:
        seed(s)
        return [_rand_raw() for _ in range(n)]
    finally:
        _state = saved


# ---- CLI ----------------------------------------------------------------


def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="Replay Lua 5.1 math.random(upper) rolls from a seed "
                    "(macOS libc Park-Miller).")
    ap.add_argument("seed", type=int, help="integer seed (as passed to math.randomseed)")
    ap.add_argument("-n", "--count", type=int, default=20,
                    help="number of rolls to print (default: 20)")
    ap.add_argument("-u", "--upper", type=int, default=100,
                    help="upper bound for math.random(u) (default: 100)")
    ap.add_argument("--raw", action="store_true",
                    help="also print raw rand() state values")
    ap.add_argument("--float", dest="as_float", action="store_true",
                    help="print floats from math.random() instead of math.random(u)")
    args = ap.parse_args()

    seed(args.seed)
    header = ["i", "rand()"] if args.raw else ["i"]
    header.append("random(float)" if args.as_float else f"random({args.upper})")
    print("\t".join(header))
    for i in range(args.count):
        if args.raw:
            raw = _rand_raw()
            r = (raw % RAND_MAX) / RAND_MAX
            if args.as_float:
                print(f"{i}\t{raw}\t{r:.10f}")
            else:
                val = int(math.floor(r * args.upper)) + 1
                print(f"{i}\t{raw}\t{val}")
        else:
            if args.as_float:
                print(f"{i}\t{random():.10f}")
            else:
                print(f"{i}\t{random(args.upper)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
