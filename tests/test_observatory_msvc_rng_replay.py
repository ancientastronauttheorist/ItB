"""Tests for exact observable replay of the native Windows CRT RNG."""

from __future__ import annotations

import pytest

from src.observatory.msvc_rng_replay import (
    MsvcRngReplayError,
    advance_state,
    canonical_observable_state,
    draw,
    previous_state,
    recover_observable_pre_state,
    recover_raw_pre_states,
    replay_results,
)


LIVE_SPAWN_SPANS = (
    ((24976, 26204, 24669), 0x143E0BAE),
    ((757, 11839, 17554), 0x2A2385E3),
    ((6793, 13804, 4449), 0x1444D9C8),
)


@pytest.mark.parametrize(("results", "canonical"), LIVE_SPAWN_SPANS)
def test_recovers_exact_observable_state_from_live_spawn_spans(results, canonical):
    raw_states = recover_raw_pre_states(results)

    assert len(raw_states) == 2
    assert raw_states[0] ^ raw_states[1] == 0x80000000
    assert {canonical_observable_state(state) for state in raw_states} == {canonical}
    assert recover_observable_pre_state(results) == canonical
    assert replay_results(canonical, len(results)) == results


def test_hidden_state_bit_never_changes_future_results():
    state = 0x143E0BAE

    assert replay_results(state, 10_000) == replay_results(state ^ 0x80000000, 10_000)


def test_transition_is_invertible_and_draw_advances_before_returning():
    seed = 0x12345678
    result, post_state = draw(seed)

    assert post_state == advance_state(seed)
    assert previous_state(post_state) == seed
    assert result == 13289


@pytest.mark.parametrize(
    "results",
    [None, 3, (), (1,), (1, 2), (0, 1, 32768), (0, True, 2)],
)
def test_recovery_rejects_invalid_or_insufficient_results(results):
    with pytest.raises(MsvcRngReplayError):
        recover_observable_pre_state(results)


@pytest.mark.parametrize("state", [-1, 1 << 32, True, 1.5])
def test_state_operations_reject_non_u32_values(state):
    with pytest.raises(MsvcRngReplayError):
        advance_state(state)


def test_replay_rejects_negative_or_non_integer_counts():
    with pytest.raises(MsvcRngReplayError):
        replay_results(0, -1)
    with pytest.raises(MsvcRngReplayError):
        replay_results(0, True)
