"""Recover and replay the pinned Windows build's observable MSVC RNG state.

The linked CRT generator keeps a 32-bit state, advances it with the classic
MSVC linear-congruential recurrence, and returns bits 16 through 30.  Its top
state bit is therefore permanently unobservable: two states separated by
``0x80000000`` produce the same result stream forever.  This module preserves
that raw ambiguity while exposing the canonical low-31-bit state that exactly
determines every future observable ``rand()`` result.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


MULTIPLIER = 214013
INCREMENT = 2531011
STATE_MASK = 0xFFFFFFFF
OBSERVABLE_STATE_MASK = 0x7FFFFFFF
RESULT_MASK = 0x7FFF
_MODULUS = 1 << 32
_MULTIPLIER_INVERSE = pow(MULTIPLIER, -1, _MODULUS)


class MsvcRngReplayError(ValueError):
    """Raised when an observed stream cannot produce one exact replay class."""


def _require_state(value: int) -> int:
    if type(value) is not int or not 0 <= value <= STATE_MASK:
        raise MsvcRngReplayError("state must be a 32-bit unsigned integer")
    return value


def _require_count(value: int) -> int:
    if type(value) is not int or value < 0:
        raise MsvcRngReplayError("count must be a non-negative integer")
    return value


def _normalize_results(results: Sequence[int] | Iterable[int]) -> tuple[int, ...]:
    try:
        normalized = tuple(results)
    except TypeError as exc:
        raise MsvcRngReplayError("rand results must be an iterable") from exc
    if len(normalized) < 3:
        raise MsvcRngReplayError(
            "at least three consecutive rand results are required"
        )
    if any(type(value) is not int or not 0 <= value <= RESULT_MASK for value in normalized):
        raise MsvcRngReplayError("rand results must be integers in [0, 32767]")
    return normalized


def advance_state(state: int) -> int:
    """Advance one raw 32-bit CRT state without discarding its hidden bit."""
    return (MULTIPLIER * _require_state(state) + INCREMENT) & STATE_MASK


def previous_state(state: int) -> int:
    """Invert one raw 32-bit CRT state transition."""
    return ((_require_state(state) - INCREMENT) * _MULTIPLIER_INVERSE) & STATE_MASK


def result_from_advanced_state(state: int) -> int:
    """Return the MSVC ``rand()`` value represented by an advanced state."""
    return (_require_state(state) >> 16) & RESULT_MASK


def draw(state: int) -> tuple[int, int]:
    """Return ``(result, next_raw_state)`` for one MSVC ``rand()`` call."""
    next_state = advance_state(state)
    return result_from_advanced_state(next_state), next_state


def replay_results(state: int, count: int) -> tuple[int, ...]:
    """Replay ``count`` results from the raw or canonical pre-call state."""
    current = _require_state(state)
    output: list[int] = []
    for _ in range(_require_count(count)):
        result, current = draw(current)
        output.append(result)
    return tuple(output)


def canonical_observable_state(state: int) -> int:
    """Discard only the permanently masked raw state bit."""
    return _require_state(state) & OBSERVABLE_STATE_MASK


def recover_raw_pre_states(
    results: Sequence[int] | Iterable[int],
) -> tuple[int, ...]:
    """Enumerate raw pre-call states consistent with consecutive results.

    The first result fixes bits 16 through 30 of the first post-call state.
    Enumerating its hidden top bit and low 16 bits is exhaustive; later
    results then filter those 131,072 candidates before the transition is
    inverted.
    """
    observed = _normalize_results(results)
    recovered: list[int] = []
    first = observed[0]
    for hidden_bit in (0, 1):
        fixed_high = (hidden_bit << 31) | (first << 16)
        for low_bits in range(1 << 16):
            first_post_state = fixed_high | low_bits
            current = first_post_state
            matches = True
            for expected in observed[1:]:
                current = advance_state(current)
                if result_from_advanced_state(current) != expected:
                    matches = False
                    break
            if matches:
                recovered.append(previous_state(first_post_state))
    return tuple(sorted(recovered))


def recover_observable_pre_state(
    results: Sequence[int] | Iterable[int],
) -> int:
    """Recover the unique low-31-bit state that determines future results.

    This fails closed unless the observations leave exactly the expected pair
    of raw states and those states differ only by the permanently hidden bit.
    """
    observed = _normalize_results(results)
    raw_states = recover_raw_pre_states(observed)
    if len(raw_states) != 2 or raw_states[0] ^ raw_states[1] != 0x80000000:
        raise MsvcRngReplayError(
            "observations do not resolve to one MSVC observable-state class; "
            f"found {len(raw_states)} raw candidates"
        )
    canonical = canonical_observable_state(raw_states[0])
    if replay_results(canonical, len(observed)) != observed:
        raise MsvcRngReplayError("recovered state does not replay observations")
    return canonical
