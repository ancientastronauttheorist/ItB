from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bridge import protocol


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


@pytest.mark.parametrize(
    ("condition", "counts"),
    [
        ("control", (0, 0, 0)),
        ("dormant", (0, 0, 0)),
        ("armed", (7, 1, 1)),
    ],
)
def test_enemy_tournament_trial_requires_fresh_condition_specific_output(
    condition: str,
    counts: tuple[int, int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "tournament.json"
    monkeypatch.setattr(
        protocol, "ENEMY_TOURNAMENT_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_TOURNAMENT_SNAPSHOT_TMP",
        tmp_path / "tournament.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    capture_id = f"tournament-{condition}-01"

    def ack(**_kwargs):
        if condition == "armed":
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "native_enemy_tournament_hw_snapshot",
                        "capture_id": capture_id,
                        "integrity": {"complete": True},
                        "summary": {
                            "candidate_count": counts[0],
                            "selected_count": counts[1],
                            "queue_count": counts[2],
                        },
                    }
                ),
                encoding="utf-8",
            )
        return (
            f"OK OBS_ENEMY_TOURNAMENT_TRIAL condition={condition} "
            f"capture={capture_id} pawn=1300 type=Firefly1 at=4,4 "
            f"consumed_spawns=1 candidates={counts[0]} selected={counts[1]} "
            f"queue={counts[2]} complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    observed_ack, snapshot = protocol.run_observatory_enemy_tournament_trial(
        condition, capture_id, timeout=0.2
    )

    assert observed_ack.endswith(
        f"candidates={counts[0]} selected={counts[1]} queue={counts[2]} complete=true"
    )
    assert (snapshot is not None) is (condition == "armed")
    assert commands == [
        f"OBS_ENEMY_TOURNAMENT_TRIAL {condition} {capture_id}"
    ]


def test_enemy_tournament_trial_rejects_bad_ack_counts_and_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot_path = tmp_path / "tournament.json"
    monkeypatch.setattr(
        protocol, "ENEMY_TOURNAMENT_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_TOURNAMENT_SNAPSHOT_TMP",
        tmp_path / "tournament.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    monkeypatch.setattr(protocol, "write_command", lambda _value: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_ENEMY_TOURNAMENT_TRIAL condition=armed "
            "capture=tournament-armed-01 pawn=1300 type=Firefly1 at=4,4 "
            "consumed_spawns=0 candidates=0 selected=1 queue=1 complete=true"
        ),
    )

    with pytest.raises(protocol.BridgeError, match="one exact capture"):
        protocol.run_observatory_enemy_tournament_trial(
            "armed", "tournament-armed-01", timeout=0.2
        )

    snapshot_path.write_text("{}", encoding="utf-8")
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.run_observatory_enemy_tournament_trial(
            "control", "tournament-control-01", timeout=0.2
        )


def test_enemy_tournament_modloader_path_is_build_keyed_and_three_stage():
    command = MODLOADER.index('elseif cmd == "OBS_ENEMY_TOURNAMENT_TRIAL" then')
    seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    block = MODLOADER[command:seed]

    assert "ENEMY_TOURNAMENT.trial(parts[2], parts[3])" in block
    assert (
        "d5c173e53182534fb9eb038008bfee9c"
        "34b44b77a15bbe4fc5db0c55a7008dfa"
    ) in MODLOADER
    assert "function ENEMY_TOURNAMENT.load(directory)" in MODLOADER
    assert "function ENEMY_TOURNAMENT.validate_snapshot" in MODLOADER
    assert "function ENEMY_TOURNAMENT.snapshot_complete" in MODLOADER
    assert "function ENEMY_TOURNAMENT.trial" in MODLOADER
    assert 'Board:AddPawn("Firefly1", selected)' in MODLOADER
    assert 'rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED' in MODLOADER
    assert 'rawget(observer, "arm")' in MODLOADER
    assert 'rawget(observer, "finish")' in MODLOADER
    assert "candidate_count" in MODLOADER
    assert "selector_rng_state_before" in MODLOADER
    assert "selector_rng_state_after" in MODLOADER
    assert "addresses_or_pointers_published" in MODLOADER


def test_enemy_tournament_python_bridge_rejects_invalid_inputs(monkeypatch):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)

    with pytest.raises(protocol.BridgeError, match="condition is invalid"):
        protocol.run_observatory_enemy_tournament_trial("other", "valid-01")
    with pytest.raises(protocol.BridgeError, match="capture ID is invalid"):
        protocol.run_observatory_enemy_tournament_trial("control", "../escape")
