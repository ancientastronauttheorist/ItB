from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bridge import protocol
from src.bridge.protocol import BridgeError


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


def test_arm_is_exact_build_keyed_and_requires_fresh_output(monkeypatch, tmp_path):
    commands: list[str] = []
    snapshot = tmp_path / "score_x87.json"
    temporary = tmp_path / "score_x87.json.tmp"
    monkeypatch.setattr(protocol, "SCORE_POSITIONING_X87_SNAPSHOT_FILE", snapshot)
    monkeypatch.setattr(protocol, "SCORE_POSITIONING_X87_SNAPSHOT_TMP", temporary)
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **kwargs: True)
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **kwargs: (
            "OK OBS_SCORE_POSITIONING_X87_ARM capture=score-x87-001 "
            "state=capturing records=0"
        ),
    )

    ack = protocol.arm_observatory_score_positioning_x87("score-x87-001")

    assert commands == ["OBS_SCORE_POSITIONING_X87_ARM score-x87-001"]
    assert ack.endswith("state=capturing records=0")

    snapshot.write_text("{}", encoding="utf-8")
    with pytest.raises(BridgeError, match="already exists"):
        protocol.arm_observatory_score_positioning_x87("score-x87-002")


@pytest.mark.parametrize(
    ("state", "records", "mode"),
    [
        ("capturing", 0, "pending"),
        ("draining", 1, "nearest_even"),
        ("draining", 1, "down"),
        ("draining", 1, "up"),
        ("draining", 1, "toward_zero"),
    ],
)
def test_status_accepts_only_consistent_pending_or_observed_ack(
    monkeypatch, state, records, mode
):
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **kwargs: (
            "OK OBS_SCORE_POSITIONING_X87_STATUS capture=score-x87-001 "
            f"state={state} records={records} mode={mode}"
        ),
    )

    _, status = protocol.status_observatory_score_positioning_x87(
        "score-x87-001"
    )

    assert commands == ["OBS_SCORE_POSITIONING_X87_STATUS score-x87-001"]
    assert status == {
        "state": state,
        "record_count": records,
        "rounding_mode": mode,
    }


def test_status_rejects_inconsistent_ack(monkeypatch):
    monkeypatch.setattr(protocol, "write_command", lambda command: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **kwargs: (
            "OK OBS_SCORE_POSITIONING_X87_STATUS capture=score-x87-001 "
            "state=capturing records=1 mode=nearest_even"
        ),
    )

    with pytest.raises(BridgeError, match="inconsistent"):
        protocol.status_observatory_score_positioning_x87("score-x87-001")


def test_finish_requires_fresh_snapshot_matching_ack(monkeypatch, tmp_path):
    commands: list[str] = []
    snapshot_path = tmp_path / "score_x87.json"
    temporary = tmp_path / "score_x87.json.tmp"
    capture_id = "score-x87-001"
    snapshot = {
        "schema_version": 1,
        "kind": "native_score_positioning_x87_snapshot",
        "capture_id": capture_id,
        "integrity": {"complete": True},
        "summary": {"record_count": 1},
        "observation": {
            "rounding_mode": "nearest_even",
            "control_word": 639,
        },
    }
    monkeypatch.setattr(
        protocol, "SCORE_POSITIONING_X87_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(protocol, "SCORE_POSITIONING_X87_SNAPSHOT_TMP", temporary)
    monkeypatch.setattr(protocol, "write_command", commands.append)

    def acknowledge(**kwargs):
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        return (
            "OK OBS_SCORE_POSITIONING_X87_FINISH capture=score-x87-001 "
            "records=1 mode=nearest_even control_word=639 complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", acknowledge)

    ack, observed = protocol.finish_observatory_score_positioning_x87(capture_id)

    assert commands == ["OBS_SCORE_POSITIONING_X87_FINISH score-x87-001"]
    assert ack.endswith("control_word=639 complete=true")
    assert observed == snapshot


@pytest.mark.parametrize("condition", ["control", "dormant", "armed"])
def test_fixed_trial_requires_matching_fresh_output(
    monkeypatch, tmp_path, condition
):
    commands: list[str] = []
    capture_id = f"score-x87-001-{condition}"
    snapshot_path = tmp_path / "score_x87.json"
    temporary = tmp_path / "score_x87.json.tmp"
    snapshot = {
        "schema_version": 1,
        "kind": "native_score_positioning_x87_snapshot",
        "capture_id": capture_id,
        "integrity": {"complete": True},
        "summary": {"record_count": 1},
        "observation": {
            "rounding_mode": "nearest_even",
            "control_word": 639,
        },
    }
    monkeypatch.setattr(
        protocol, "SCORE_POSITIONING_X87_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(protocol, "SCORE_POSITIONING_X87_SNAPSHOT_TMP", temporary)
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **kwargs: True)
    monkeypatch.setattr(protocol, "write_command", commands.append)

    def acknowledge(**kwargs):
        if condition == "armed":
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        records = 1 if condition == "armed" else 0
        mode = "nearest_even" if condition == "armed" else "unobserved"
        control_word = 639 if condition == "armed" else 0
        return (
            "OK OBS_SCORE_POSITIONING_X87_TRIAL "
            f"condition={condition} capture={capture_id} "
            "pawn=1303 type=Firefly1 at=4,4 consumed_spawns=0 "
            f"records={records} mode={mode} control_word={control_word} "
            "complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", acknowledge)

    ack, observed = protocol.run_observatory_score_positioning_x87_trial(
        condition, capture_id
    )

    assert commands == [
        f"OBS_SCORE_POSITIONING_X87_TRIAL {condition} {capture_id}"
    ]
    assert f"condition={condition}" in ack
    assert observed == (snapshot if condition == "armed" else None)


def test_modloader_surface_is_one_shot_strict_and_create_only():
    assert (
        '"515376611fb75ff58ed5323b654eb8dd2402996e5e4dbc237d870d3c5fbab504"'
        in MODLOADER
    )
    assert (
        '"5a104c63de813099febaabe692e2e89e313459d6579dd8808e4c4bb2516013b0"'
        in MODLOADER
    )
    assert "function SCORE_POSITIONING_X87.load" in MODLOADER
    assert "function SCORE_POSITIONING_X87.validate_snapshot" in MODLOADER
    assert "function SCORE_POSITIONING_X87.snapshot_complete" in MODLOADER
    assert "SCORE_POSITIONING_X87.snapshot_file" in MODLOADER
    assert "write_observatory_create_only_json(" in MODLOADER
    assert 'elseif cmd == "OBS_SCORE_POSITIONING_X87_ARM" then' in MODLOADER
    assert 'elseif cmd == "OBS_SCORE_POSITIONING_X87_STATUS" then' in MODLOADER
    assert 'elseif cmd == "OBS_SCORE_POSITIONING_X87_FINISH" then' in MODLOADER
    assert 'elseif cmd == "OBS_SCORE_POSITIONING_X87_TRIAL" then' in MODLOADER
    assert "function SCORE_POSITIONING_X87.trial" in MODLOADER
    assert "observatory_selected_queue_scenario()" in MODLOADER
    assert 'rawget(gameflow, "end_player_turn")' in MODLOADER
    assert "requires spent player actors" in MODLOADER
    assert "debug_registers_armed" in MODLOADER
    assert "seams_unchanged" in MODLOADER


@pytest.mark.parametrize("capture_id", ["", "Bad", "x 1", "a" * 97])
def test_protocol_rejects_invalid_capture_ids(capture_id):
    with pytest.raises(BridgeError, match="capture ID"):
        protocol.arm_observatory_score_positioning_x87(capture_id)
    with pytest.raises(BridgeError, match="capture ID"):
        protocol.status_observatory_score_positioning_x87(capture_id)
    with pytest.raises(BridgeError, match="capture ID"):
        protocol.finish_observatory_score_positioning_x87(capture_id)
    with pytest.raises(BridgeError, match="capture ID"):
        protocol.run_observatory_score_positioning_x87_trial(
            "armed", capture_id
        )
