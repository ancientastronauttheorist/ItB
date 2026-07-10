"""CLI parity regressions for exact dirty-plan consent flags."""

from __future__ import annotations

import sys

import game_loop


def test_auto_turn_cli_forwards_mech_loss_consent(monkeypatch):
    calls = []

    monkeypatch.setattr(
        game_loop,
        "cmd_auto_turn",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "game_loop.py",
            "auto_turn",
            "--allow-dirty-plan",
            "--candidate-rank",
            "3",
            "--dirty-consent-id",
            "exact-token",
            "--allow-mech-loss",
        ],
    )

    game_loop.main()

    assert len(calls) == 1
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 3
    assert calls[0]["dirty_consent_id"] == "exact-token"
    assert calls[0]["allow_mech_loss"] is True
