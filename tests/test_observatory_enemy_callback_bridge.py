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
    ("condition", "attempts"),
    [("control", 0), ("exact_hook", 9)],
)
def test_enemy_callback_trial_requires_fresh_restored_family_output(
    condition: str,
    attempts: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(protocol, "BRIDGE_DIR", tmp_path)
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    family = "get_target_area"
    capture_id = f"firefly-area-{condition}"
    nonce = "a" * 32
    capsule_sha256 = "b" * 64

    def ack(**_kwargs):
        result_path = (
            tmp_path
            / f"itb_observatory_callback_trial_{capture_id}_{condition}.json"
        )
        result_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "observatory_callback_trial_result",
                    "status": "complete",
                    "condition": condition,
                    "capture_id": capture_id,
                    "callback_family": family,
                    "attempted_calls": attempts,
                    "raw_event_count": attempts,
                    "serialization_errors": 0,
                    "slots_restored": True,
                }
            ),
            encoding="utf-8",
        )
        if condition == "exact_hook":
            events = [
                {
                    "seq": index,
                    "kind": family,
                    "mission_id": "Mission_Power",
                    "phase": "combat_enemy",
                    "context": {},
                    "payload": {},
                }
                for index in range(attempts)
            ]
            (tmp_path / f"itb_observatory_trace_{capture_id}_0.raw").write_text(
                json.dumps(
                    {
                        "raw_schema_version": 1,
                        "controller_version": "observatory-callback-controller/1",
                        "capture_id": capture_id,
                        "checkpoint_seq": 0,
                        "attempted_calls": {family: attempts},
                        "events": events,
                        "summary": {
                            "accepted_events": attempts,
                            "dropped_events": 0,
                            "filtered_events": 0,
                            "serialization_errors": 0,
                            "restore_conflicts": 0,
                            "stop_reasons": [],
                            "truncation_reasons": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
        return (
            f"OK OBS_ENEMY_CALLBACK_TRIAL condition={condition} family={family} "
            f"capture={capture_id} pawn=1303 type=Firefly1 at=4,4 "
            f"consumed_spawns=1 attempts={attempts} events={attempts} "
            "complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    observed_ack, result, trace = protocol.run_observatory_enemy_callback_trial(
        condition,
        family,
        capture_id,
        nonce,
        capsule_sha256,
        timeout=0.2,
    )

    assert observed_ack.endswith(
        f"attempts={attempts} events={attempts} complete=true"
    )
    assert result["slots_restored"] is True
    assert (trace is not None) is (condition == "exact_hook")
    assert commands == [
        f"OBS_ENEMY_CALLBACK_TRIAL {condition} {family} {capture_id} "
        f"{nonce} {capsule_sha256}"
    ]


def test_enemy_callback_trial_rejects_existing_or_incomplete_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(protocol, "BRIDGE_DIR", tmp_path)
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    monkeypatch.setattr(protocol, "write_command", lambda _value: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_ENEMY_CALLBACK_TRIAL condition=exact_hook "
            "family=get_target_area capture=firefly-area-exact pawn=1303 "
            "type=Firefly1 at=4,4 consumed_spawns=1 attempts=9 events=8 "
            "complete=true"
        ),
    )

    with pytest.raises(protocol.BridgeError, match="incomplete"):
        protocol.run_observatory_enemy_callback_trial(
            "exact_hook",
            "get_target_area",
            "firefly-area-exact",
            "a" * 32,
            "b" * 64,
            timeout=0.2,
        )

    existing = (
        tmp_path
        / "itb_observatory_callback_trial_firefly-area-control_control.json"
    )
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.run_observatory_enemy_callback_trial(
            "control",
            "get_target_area",
            "firefly-area-control",
            "a" * 32,
            "b" * 64,
            timeout=0.2,
        )


def test_enemy_callback_modloader_reuses_attested_host_and_firefly_setup():
    function = MODLOADER.index(
        "function ENEMY_TOURNAMENT.callback_trial("
    )
    command = MODLOADER.index('elseif cmd == "OBS_ENEMY_CALLBACK_TRIAL" then')
    native_seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    function_block = MODLOADER[function:command]
    command_block = MODLOADER[command:native_seed]

    assert "ENEMY_TOURNAMENT.callback_families" in function_block
    assert "initialize_observatory_callback_trial({" in function_block
    assert "observatory_selected_queue_scenario()" in function_block
    assert 'rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED' in function_block
    assert 'rawget(gameflow, "end_player_turn")' in function_block
    assert 'rawget(status, "slots_restored") ~= true' in function_block
    assert 'rawget(status, "serialization_errors") ~= 0' in function_block
    assert "attempts < 1 or events ~= attempts" in function_block
    assert "ENEMY_TOURNAMENT.callback_trial(" in command_block


def test_enemy_callback_python_bridge_rejects_invalid_inputs(monkeypatch):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    valid = {
        "condition": "control",
        "family": "get_target_area",
        "capture_id": "valid-01",
        "activation_nonce": "a" * 32,
        "capsule_sha256": "b" * 64,
    }

    for field, value, message in (
        ("condition", "other", "condition is invalid"),
        ("family", "other", "family is invalid"),
        ("capture_id", "../escape", "capture ID is invalid"),
        ("activation_nonce", "no", "activation nonce is invalid"),
        ("capsule_sha256", "no", "capsule SHA-256 is invalid"),
    ):
        arguments = dict(valid)
        arguments[field] = value
        with pytest.raises(protocol.BridgeError, match=message):
            protocol.run_observatory_enemy_callback_trial(**arguments)
