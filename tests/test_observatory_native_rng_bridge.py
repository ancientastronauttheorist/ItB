from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bridge import protocol


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


def _snapshot(capture_id: str, record_count: int = 1) -> dict:
    return {
        "schema_version": 1,
        "kind": "native_rng_core_observer_snapshot",
        "observer_version": "observatory-rng-core-observer/1",
        "capture_id": capture_id,
        "identity": {},
        "integrity": {
            "complete": True,
            "hook_bytes_restored": True,
            "patch_installed": False,
        },
        "records": [{} for _ in range(record_count)],
        "summary": {"record_count": record_count},
    }


def test_native_rng_arm_is_fixed_and_refuses_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot = tmp_path / "snapshot.json"
    temporary = tmp_path / "snapshot.json.tmp"
    monkeypatch.setattr(protocol, "NATIVE_RNG_SNAPSHOT_FILE", snapshot)
    monkeypatch.setattr(protocol, "NATIVE_RNG_SNAPSHOT_TMP", temporary)
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: "OK OBS_NATIVE_RNG_ARM capture=native-pair-01",
    )

    assert protocol.arm_observatory_native_rng("native-pair-01") == (
        "OK OBS_NATIVE_RNG_ARM capture=native-pair-01"
    )
    assert commands == ["OBS_NATIVE_RNG_ARM native-pair-01"]

    snapshot.write_text("{}", encoding="utf-8")
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.arm_observatory_native_rng("native-pair-02")
    assert commands == ["OBS_NATIVE_RNG_ARM native-pair-01"]


def test_native_rng_seed_command_is_no_argument_and_fixed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: "OK OBS_NATIVE_RNG_SEED seed=324508639",
    )

    assert protocol.seed_observatory_native_rng() == (
        "OK OBS_NATIVE_RNG_SEED seed=324508639"
    )
    assert commands == ["OBS_NATIVE_RNG_SEED"]


def test_native_rng_seed_and_arm_is_one_fixed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        protocol, "NATIVE_RNG_SNAPSHOT_FILE", tmp_path / "snapshot.json"
    )
    monkeypatch.setattr(
        protocol, "NATIVE_RNG_SNAPSHOT_TMP", tmp_path / "snapshot.json.tmp"
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_NATIVE_RNG_SEED_AND_ARM capture=native-pair-01 "
            "seed=324508639"
        ),
    )

    assert protocol.seed_and_arm_observatory_native_rng(
        "native-pair-01"
    ).endswith("seed=324508639")
    assert commands == ["OBS_NATIVE_RNG_SEED_AND_ARM native-pair-01"]


@pytest.mark.parametrize("capture_id", ["", "Upper", "a/b", "a" * 97])
def test_native_rng_arm_rejects_noncanonical_capture_ids(capture_id: str):
    with pytest.raises(protocol.BridgeError, match="capture ID"):
        protocol.arm_observatory_native_rng(capture_id)


def test_native_rng_finish_requires_a_fresh_complete_matching_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(protocol, "NATIVE_RNG_SNAPSHOT_FILE", snapshot_path)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)

    def ack(**_kwargs):
        snapshot_path.write_text(
            json.dumps(_snapshot("native-pair-01")), encoding="utf-8"
        )
        return (
            "OK OBS_NATIVE_RNG_FINISH capture=native-pair-01 "
            "records=1 complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    response, snapshot = protocol.finish_observatory_native_rng(
        "native-pair-01", timeout=0.2
    )
    assert response.endswith("records=1 complete=true")
    assert snapshot["integrity"]["hook_bytes_restored"] is True
    assert commands == ["OBS_NATIVE_RNG_FINISH"]


def test_native_rng_finish_rejects_ack_snapshot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    snapshot_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(protocol, "NATIVE_RNG_SNAPSHOT_FILE", snapshot_path)
    monkeypatch.setattr(protocol, "write_command", lambda _command: None)

    def ack(**_kwargs):
        snapshot_path.write_text(
            json.dumps(_snapshot("different-capture")), encoding="utf-8"
        )
        return (
            "OK OBS_NATIVE_RNG_FINISH capture=native-pair-01 "
            "records=1 complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    with pytest.raises(protocol.BridgeError, match="complete ACK"):
        protocol.finish_observatory_native_rng(
            "native-pair-01", timeout=0.2
        )


def test_modloader_native_rng_path_is_fixed_one_shot_and_restores_before_ack():
    native_sha = (
        "8ef711798bd9d37fbff5e75eaac17c271"
        "89f9c25aa6f11122cb27068b5e2184c"
    )
    assert native_sha in MODLOADER
    seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    seed_and_arm = MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM" then'
    )
    arm = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_ARM" then')
    status = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_STATUS" then')
    finish = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_FINISH" then')
    lua = MODLOADER.index('elseif cmd == "LUA" then')
    assert seed < seed_and_arm < arm < status < finish < lua
    seed_block = MODLOADER[seed:seed_and_arm]
    assert "NATIVE_RNG_FIXED_SEED" in seed_block
    assert "requires spent player actors" in seed_block
    assert "parts[2]" not in seed_block
    atomic_block = MODLOADER[seed_and_arm:arm]
    assert "load_observatory_rng_seed_helper" in atomic_block
    assert "load_observatory_native_rng_module" in atomic_block
    assert atomic_block.index("load_observatory_native_rng_module") < (
        atomic_block.index('rawget(seed_helper, "seed")')
    )
    assert atomic_block.index('rawget(seed_helper, "seed")') < (
        atomic_block.index('rawget(observer, "arm")')
    )
    block = MODLOADER[finish:lua]
    assert 'rawget(_observatory_native_rng_module, "finish")' in block
    assert "validate_observatory_native_rng_snapshot(" in block
    assert "write_observatory_create_only_json(" in block
    assert block.index('rawget(_observatory_native_rng_module, "finish")') < (
        block.index("write_observatory_create_only_json(")
    )
    assert block.index("write_observatory_create_only_json(") < block.index(
        'write_ack(\n            "OK OBS_NATIVE_RNG_FINISH'
    )
    arm_block = MODLOADER[arm:status]
    assert "package.loadlib" not in arm_block
    assert "parts[2]" in arm_block
    assert "parts[3]" not in arm_block
