"""
Golden-value tests for scripts/seed_replay.py.

The goldens were hand-derived by running a tiny C program that calls
srand(SEED) then rand() repeatedly, on the same macOS libc that Into
the Breach links against.  See docs/seed_replay_hypotheses.md §1.2.

If any assertion here fails on another machine, the host libc is NOT
macOS Park-Miller and the PRNG module will need to be adapted.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable (mirrors how the CLI does it).
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import seed_replay  # noqa: E402


def test_rand_max_is_park_miller():
    # RAND_MAX on macOS libc is 2**31 - 1, Park-Miller modulus.
    assert seed_replay.RAND_MAX == 2147483647


def test_raw_sequence_seed_one():
    # srand(1); rand() -> 16807, 282475249, 1622650073, 984943658, 1144108930
    # This is the canonical Park-Miller start.
    got = seed_replay.raw_sequence(1, 5)
    assert got == [16807, 282475249, 1622650073, 984943658, 1144108930]


def test_raw_sequence_seed_zero_special_case():
    # srand(0) on macOS libc reseeds to state 123459876.
    # 123459876 * 16807 mod (2**31 - 1) == 520932930.
    got = seed_replay.raw_sequence(0, 5)
    assert got == [520932930, 28925691, 822784415, 890459872, 145532761]


def test_raw_sequence_observed_aiseed():
    # Matches the C-probe output for seed=560415071 (one of the aiSeeds in our probe log).
    got = seed_replay.raw_sequence(560415071, 5)
    assert got == [32822555, 1892868253, 613981513, 528365156, 388296547]


def test_random_float_first_value_seed_one():
    # r = 16807 / 2147483647  =>  ~7.826369e-6
    seed_replay.seed(1)
    r = seed_replay.random()
    assert r == 16807 / 2147483647
    assert 0.0 <= r < 1.0


def test_random_bounded_upper_seed_one():
    # floor(16807/2147483647 * 100) + 1  =>  floor(7.8e-4) + 1 = 1
    seed_replay.seed(1)
    assert seed_replay.random(100) == 1


def test_random_bounded_seed_observed():
    # Matches C-probe rolls for seed=560415071:
    #   2, 89, 29, 25, 19, 96, 94, 51, 51, 65
    seed_replay.seed(560415071)
    got = [seed_replay.random(100) for _ in range(10)]
    assert got == [2, 89, 29, 25, 19, 96, 94, 51, 51, 65]


def test_random_two_arg_form():
    # math.random(l, u) = floor(r*(u-l+1)) + l
    # seed 1, first r = 16807/2147483647 ~ 7.8e-6
    # floor(7.8e-6 * 6) + 1 = 1
    seed_replay.seed(1)
    got = [seed_replay.random(1, 6) for _ in range(3)]
    # For seed=1, r_i = [16807, 282475249, 1622650073] / RAND_MAX
    # floor(r*6)+1  = [1, 1, 5]
    assert got == [1, 1, 5]


def test_rolls_is_pure():
    # rolls() must not advance the module's RNG state for the caller.
    seed_replay.seed(42)
    before = seed_replay.random()
    seed_replay.seed(42)  # reset for comparison
    _ = seed_replay.rolls(560415071, 5, upper=100)
    after = seed_replay.random()
    assert before == after


def test_rolls_matches_observed_aiseed():
    # Same golden, via the convenience rolls() entry point.
    got = seed_replay.rolls(560415071, 10, upper=100)
    assert got == [2, 89, 29, 25, 19, 96, 94, 51, 51, 65]


def test_rolls_matches_407184687():
    # The other aiSeed in our probe log (turn 4).
    got = seed_replay.rolls(407184687, 10, upper=100)
    assert got == [78, 10, 62, 41, 81, 76, 33, 26, 40, 28]
