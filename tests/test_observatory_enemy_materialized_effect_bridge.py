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
        ("control", (0, 0, 0, 0)),
        ("dormant", (0, 0, 0, 0)),
        ("armed", (7, 1, 1, 1)),
    ],
)
def test_materialized_effect_trial_requires_fresh_condition_specific_output(
    condition: str,
    counts: tuple[int, int, int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "materialized.json"
    monkeypatch.setattr(
        protocol, "ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_TMP",
        tmp_path / "materialized.json.tmp",
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_FILE",
        tmp_path / "materialized.rejected.json",
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_TMP",
        tmp_path / "materialized.rejected.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    capture_id = f"materialized-{condition}-01"

    def ack(**_kwargs):
        if condition == "armed":
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "native_enemy_materialized_effect_hw_snapshot",
                        "capture_id": capture_id,
                        "integrity": {"complete": True},
                        "summary": {
                            "candidate_count": counts[0],
                            "selected_count": counts[1],
                            "materialized_effect_count": counts[2],
                            "queue_count": counts[3],
                        },
                    }
                ),
                encoding="utf-8",
            )
        return (
            "OK OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL "
            f"condition={condition} capture={capture_id} "
            "pawn=1300 type=Firefly1 at=4,4 consumed_spawns=1 "
            f"candidates={counts[0]} selected={counts[1]} "
            f"materialized={counts[2]} queue={counts[3]} complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    observed_ack, snapshot = (
        protocol.run_observatory_enemy_materialized_effect_trial(
            condition, capture_id, timeout=0.2
        )
    )

    assert observed_ack.endswith(
        f"candidates={counts[0]} selected={counts[1]} "
        f"materialized={counts[2]} queue={counts[3]} complete=true"
    )
    assert (snapshot is not None) is (condition == "armed")
    assert commands == [
        f"OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL {condition} {capture_id}"
    ]


def test_materialized_effect_trial_rejects_bad_counts_and_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "materialized.json"
    monkeypatch.setattr(
        protocol, "ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_TMP",
        tmp_path / "materialized.json.tmp",
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_FILE",
        tmp_path / "materialized.rejected.json",
    )
    monkeypatch.setattr(
        protocol,
        "ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_TMP",
        tmp_path / "materialized.rejected.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    monkeypatch.setattr(protocol, "write_command", lambda _value: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL condition=armed "
            "capture=materialized-armed-01 pawn=1300 type=Firefly1 at=4,4 "
            "consumed_spawns=0 candidates=7 selected=1 materialized=0 "
            "queue=1 complete=true"
        ),
    )

    with pytest.raises(protocol.BridgeError, match="one exact capture"):
        protocol.run_observatory_enemy_materialized_effect_trial(
            "armed", "materialized-armed-01", timeout=0.2
        )

    snapshot_path.write_text("{}", encoding="utf-8")
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.run_observatory_enemy_materialized_effect_trial(
            "control", "materialized-control-01", timeout=0.2
        )


def test_materialized_effect_modloader_path_is_build_keyed_and_four_stage():
    command = MODLOADER.index(
        'elseif cmd == "OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL" then'
    )
    callbacks = MODLOADER.index('elseif cmd == "OBS_ENEMY_CALLBACK_TRIAL" then')
    block = MODLOADER[command:callbacks]

    assert "ENEMY_TOURNAMENT.materialized_effect.trial" in block
    assert (
        "cf686bb2c48b56f1314d996ad53236b7"
        "6a03eb679d9893d2878929724adde328"
    ) in MODLOADER
    assert "function ENEMY_TOURNAMENT.materialized_effect.load" in MODLOADER
    assert "function ENEMY_TOURNAMENT.materialized_effect.validate_snapshot" in MODLOADER
    assert "function ENEMY_TOURNAMENT.materialized_effect.snapshot_complete" in MODLOADER
    assert "function ENEMY_TOURNAMENT.materialized_effect.trial" in MODLOADER
    assert 'rawget(observer, "MATERIALIZED_RVA") ~= "0x00268323"' in MODLOADER
    assert "materialized_effect_count" in MODLOADER
    assert "torn_materialized_count" in MODLOADER
    assert "queued_animation_length" in MODLOADER
    assert "skill_key_length" in MODLOADER
    assert "rejected_snapshot_file" in MODLOADER
    assert "rejected snapshot captured" in MODLOADER


def test_materialized_effect_python_bridge_rejects_invalid_inputs(monkeypatch):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)

    with pytest.raises(protocol.BridgeError, match="condition is invalid"):
        protocol.run_observatory_enemy_materialized_effect_trial(
            "other", "valid-01"
        )
    with pytest.raises(protocol.BridgeError, match="capture ID is invalid"):
        protocol.run_observatory_enemy_materialized_effect_trial(
            "control", "../escape"
        )
