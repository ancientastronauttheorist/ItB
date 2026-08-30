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


def test_native_rng_spawn_span_arm_is_one_fixed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    for name in (
        "NATIVE_RNG_SNAPSHOT_FILE",
        "NATIVE_RNG_SNAPSHOT_TMP",
        "SPAWN_SPAN_LEDGER_FILE",
        "SPAWN_SPAN_LEDGER_TMP",
    ):
        monkeypatch.setattr(protocol, name, tmp_path / name.lower())
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN "
            "capture=native-pair-01 seed=324508639"
        ),
    )

    ack = protocol.seed_and_arm_observatory_native_rng_spawn_span(
        "native-pair-01"
    )
    assert ack.endswith("seed=324508639")
    assert commands == [
        "OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN native-pair-01"
    ]


@pytest.mark.parametrize(
    ("function", "ack", "command"),
    [
        (
            protocol.arm_observatory_native_rng_spawn_replay,
            "OK OBS_NATIVE_RNG_ARM_SPAWN_REPLAY capture=native-pair-01",
            "OBS_NATIVE_RNG_ARM_SPAWN_REPLAY native-pair-01",
        ),
        (
            protocol.prepare_observatory_spawn_replay_control,
            "OK OBS_SPAWN_REPLAY_CONTROL capture=native-pair-01 dormant=true",
            "OBS_SPAWN_REPLAY_CONTROL native-pair-01",
        ),
    ],
)
def test_spawn_replay_arm_and_control_are_fixed_unseeded_commands(
    function, ack, command, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    for name in (
        "NATIVE_RNG_SNAPSHOT_FILE",
        "NATIVE_RNG_SNAPSHOT_TMP",
        "SPAWN_REPLAY_LEDGER_FILE",
        "SPAWN_REPLAY_LEDGER_TMP",
    ):
        monkeypatch.setattr(protocol, name, tmp_path / name.lower())
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(protocol, "wait_for_ack", lambda **_kwargs: ack)

    assert function("native-pair-01") == ack
    assert commands == [command]
    assert "SEED" not in command


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


def test_spawn_span_finish_requires_matching_fresh_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ledger_path = tmp_path / "ledger.json"
    monkeypatch.setattr(protocol, "SPAWN_SPAN_LEDGER_FILE", ledger_path)
    snapshot = _snapshot("native-pair-01", record_count=3)

    def finish(capture_id, **_kwargs):
        ledger_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "spawn_rng_span_ledger",
                    "capture_id": capture_id,
                    "write_mode": "create_only",
                    "raw_record_count": 3,
                    "integrity": {"complete": True},
                }
            ),
            encoding="utf-8",
        )
        return "FINISH", snapshot

    monkeypatch.setattr(protocol, "finish_observatory_native_rng", finish)
    ack, observed, ledger = protocol.finish_observatory_native_rng_spawn_span(
        "native-pair-01", timeout=0.2
    )
    assert ack == "FINISH"
    assert observed is snapshot
    assert ledger["raw_record_count"] == 3


def test_spawn_replay_finish_requires_matching_fresh_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ledger_path = tmp_path / "replay.json"
    monkeypatch.setattr(protocol, "SPAWN_REPLAY_LEDGER_FILE", ledger_path)
    snapshot = _snapshot("native-pair-01", record_count=3)

    def finish(capture_id, **_kwargs):
        ledger_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "spawn_rng_replay_ledger",
                    "capture_id": capture_id,
                    "write_mode": "create_only",
                    "raw_record_count": 3,
                    "integrity": {"complete": True},
                }
            ),
            encoding="utf-8",
        )
        return "FINISH", snapshot

    monkeypatch.setattr(protocol, "finish_observatory_native_rng", finish)
    ack, observed, ledger = protocol.finish_observatory_native_rng_spawn_replay(
        "native-pair-01", timeout=0.2
    )
    assert ack == "FINISH"
    assert observed is snapshot
    assert ledger["raw_record_count"] == 3


def test_modloader_native_rng_path_is_fixed_one_shot_and_restores_before_ack():
    native_sha = (
        "8ef711798bd9d37fbff5e75eaac17c271"
        "89f9c25aa6f11122cb27068b5e2184c"
    )
    assert native_sha in MODLOADER
    assert (
        "e0c6766f6d2150616fc10224fa2d1d53"
        "c051a7171fd2e107267f1383a4fcc91a"
    ) in MODLOADER
    seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    seed_and_arm = MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM" then'
    )
    spawn_span = MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN" then'
    )
    arm = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_ARM" then')
    status = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_STATUS" then')
    finish = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_FINISH" then')
    lua = MODLOADER.index('elseif cmd == "LUA" then')
    assert seed < spawn_span < seed_and_arm < arm < status < finish < lua
    spawn_block = MODLOADER[spawn_span:seed_and_arm]
    assert "start_observatory_native_rng_with_spawn_span" in spawn_block
    seed_block = MODLOADER[seed:spawn_span]
    assert "NATIVE_RNG_FIXED_SEED" in seed_block
    assert "requires spent player actors" in seed_block
    assert "parts[2]" not in seed_block
    atomic_block = MODLOADER[seed_and_arm:arm]
    assert "load_observatory_rng_seed_helper" in atomic_block
    assert "load_observatory_native_gameflow_helper" in atomic_block
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


def test_native_rng_conditions_use_the_pinned_synchronous_end_turn_helper():
    end_turn = MODLOADER.index('elseif cmd == "END_TURN" then')
    seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    end_turn_block = MODLOADER[end_turn:seed]
    assert "_observatory_native_gameflow" in end_turn_block
    assert "native_diagnostic" in end_turn_block
    assert 'rawget(gameflow, "end_player_turn")' in end_turn_block

    spawn_start = MODLOADER.index(
        "local function start_observatory_native_rng_with_spawn_span"
    )
    trial_state = MODLOADER.index(
        "local function observatory_trial_live_state", spawn_start
    )
    spawn_start_block = MODLOADER[spawn_start:trial_state]
    assert "load_observatory_native_gameflow_helper" in spawn_start_block
    assert "_observatory_native_gameflow = gameflow" in spawn_start_block

    spawn_command = MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN" then'
    )
    exact_command = MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM" then'
    )
    seed_block = MODLOADER[seed:spawn_command]
    exact_block = MODLOADER[exact_command:MODLOADER.index(
        'elseif cmd == "OBS_NATIVE_RNG_ARM" then'
    )]
    assert "load_observatory_native_gameflow_helper" in seed_block
    assert "_observatory_native_gameflow = gameflow" in seed_block
    assert "load_observatory_native_gameflow_helper" in exact_block
    assert "_observatory_native_gameflow = gameflow" in exact_block


def test_native_continue_startup_request_is_fixed_and_one_shot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    request = tmp_path / "native_continue.request"
    monkeypatch.setattr(protocol, "BRIDGE_DIR", tmp_path)
    monkeypatch.setattr(protocol, "NATIVE_CONTINUE_REQUEST_FILE", request)

    assert protocol.arm_observatory_native_continue_startup() == request
    assert request.read_bytes() == b"observatory-native-continue-request/1\n"
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.arm_observatory_native_continue_startup()

    assert "NATIVE_CONTINUE_REQUEST_TOKEN" in MODLOADER
    assert "consume_observatory_native_continue_startup_request" in MODLOADER
    assert 'rawget(gameflow, "continue_saved_timeline")' in MODLOADER
    assert "_native_continue_startup_requested" in MODLOADER
    startup = MODLOADER.index(
        "local function consume_observatory_native_continue_startup_request"
    )
    cleanup = MODLOADER.index("-- Clean up stale files from previous session", startup)
    startup_block = MODLOADER[startup:cleanup]
    assert startup_block.index('rawget(gameflow, "continue_saved_timeline")') < (
        startup_block.index("_observatory_native_gameflow = gameflow")
    )

    end_turn = MODLOADER.index('elseif cmd == "END_TURN" then')
    native_rng_seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    end_turn_block = MODLOADER[end_turn:native_rng_seed]
    assert end_turn_block.index('rawget(gameflow, "end_player_turn")') < (
        end_turn_block.index("_observatory_native_gameflow = nil")
    )


@pytest.mark.parametrize(
    ("condition", "record_count"),
    [("control", 0), ("dormant", 0), ("armed", 2)],
)
def test_selected_queue_trial_is_fixed_and_requires_fresh_armed_output(
    condition: str,
    record_count: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "selected.json"
    monkeypatch.setattr(protocol, "SELECTED_QUEUE_SNAPSHOT_FILE", snapshot_path)
    monkeypatch.setattr(
        protocol, "SELECTED_QUEUE_SNAPSHOT_TMP", tmp_path / "selected.json.tmp"
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    capture_id = f"selected-{condition}-01"

    def ack(**_kwargs):
        if condition == "armed":
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "native_selected_queue_hw_observer_snapshot",
                        "capture_id": capture_id,
                        "integrity": {"complete": True},
                        "summary": {"record_count": 2},
                    }
                ),
                encoding="utf-8",
            )
        return (
            f"OK OBS_SELECTED_QUEUE_TRIAL condition={condition} "
            f"capture={capture_id} pawn=1300 type=Firefly1 at=4,4 "
            f"consumed_spawns=1 records={record_count} complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    observed_ack, snapshot = protocol.run_observatory_selected_queue_trial(
        condition, capture_id, timeout=0.2
    )
    assert observed_ack.endswith(f"records={record_count} complete=true")
    assert (snapshot is not None) is (condition == "armed")
    assert commands == [f"OBS_SELECTED_QUEUE_TRIAL {condition} {capture_id}"]


def test_selected_queue_modloader_path_is_build_keyed_and_synthetic():
    command = MODLOADER.index('elseif cmd == "OBS_SELECTED_QUEUE_TRIAL" then')
    seed = MODLOADER.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then')
    block = MODLOADER[command:seed]
    assert "run_observatory_selected_queue_trial(parts[2], parts[3])" in block
    assert (
        "2cf202cc2e58c33651864ed8939b8491"
        "cc082048c300d82b63ff3cfbd76a5676"
    ) in MODLOADER
    assert "load_observatory_selected_queue_module" in MODLOADER
    assert 'Board:AddPawn("Firefly1", selected)' in MODLOADER
    assert 'rawset(mission, "InfiniteSpawn", false)' in MODLOADER
    assert "Board:SpawnQueued()" in MODLOADER
    assert "Board:RemovePawn(pawn)" in MODLOADER
    assert 'rawget(observer, "arm")' in MODLOADER
    assert 'rawget(observer, "finish")' in MODLOADER
    assert "write_observatory_create_only_json(" in MODLOADER


@pytest.mark.parametrize(
    ("condition", "counts"),
    [
        ("control", (0, 0, 0, 0, 0)),
        ("dormant", (0, 0, 0, 0, 0)),
        ("armed", (2, 1, 0, 1, 1)),
    ],
)
def test_spawn_coordinate_boundary_is_fixed_and_requires_fresh_armed_output(
    condition: str,
    counts: tuple[int, int, int, int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "spawn-coordinate.json"
    monkeypatch.setattr(protocol, "SPAWN_COORDINATE_SNAPSHOT_FILE", snapshot_path)
    monkeypatch.setattr(
        protocol,
        "SPAWN_COORDINATE_SNAPSHOT_TMP",
        tmp_path / "spawn-coordinate.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    capture_id = f"spawn-coordinate-{condition}-01"
    record_count, scheduler, fallback, standard, selectors = counts

    def ack(**_kwargs):
        command = commands[-1]
        if command.startswith("OBS_SPAWN_COORDINATE_PREPARE"):
            armed = "true" if condition == "armed" else "false"
            return (
                f"OK OBS_SPAWN_COORDINATE_PREPARE condition={condition} "
                f"capture={capture_id} seed=324508639 armed={armed}"
            )
        if condition == "armed":
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "native_spawn_coordinate_hw_observer_snapshot",
                        "capture_id": capture_id,
                        "integrity": {"complete": True},
                        "summary": {
                            "record_count": record_count,
                            "scheduler_count": scheduler,
                            "selector_fallback_count": fallback,
                            "selector_standard_count": standard,
                            "selector_count": selectors,
                        },
                    }
                ),
                encoding="utf-8",
            )
        return (
            f"OK OBS_SPAWN_COORDINATE_FINISH condition={condition} "
            f"capture={capture_id} records={record_count} "
            f"scheduler={scheduler} fallback={fallback} standard={standard} "
            f"selectors={selectors} complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    prepare_ack = protocol.prepare_observatory_spawn_coordinate(
        condition, capture_id, timeout=0.2
    )
    finish_ack, snapshot = protocol.finish_observatory_spawn_coordinate(
        condition, capture_id, timeout=0.2
    )
    assert prepare_ack.endswith(
        f"armed={'true' if condition == 'armed' else 'false'}"
    )
    assert finish_ack.endswith(f"selectors={selectors} complete=true")
    assert (snapshot is not None) is (condition == "armed")
    assert commands == [
        f"OBS_SPAWN_COORDINATE_PREPARE {condition} {capture_id}",
        f"OBS_SPAWN_COORDINATE_FINISH {capture_id}",
    ]


def test_spawn_coordinate_abort_requires_a_clean_restore_ack(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(protocol, "write_command", lambda _command: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_SPAWN_COORDINATE_ABORT condition=armed "
            "capture=spawn-coordinate-armed-01 restored=true"
        ),
    )
    assert protocol.abort_observatory_spawn_coordinate(
        "spawn-coordinate-armed-01"
    ).endswith("restored=true")


def test_spawn_coordinate_modloader_path_is_build_keyed_and_read_only():
    assert 'elseif cmd == "OBS_SPAWN_COORDINATE_PREPARE" then' in MODLOADER
    assert 'elseif cmd == "OBS_SPAWN_COORDINATE_FINISH" then' in MODLOADER
    assert 'elseif cmd == "OBS_SPAWN_COORDINATE_ABORT" then' in MODLOADER
    assert "prepare_observatory_spawn_coordinate_trial(parts[2], parts[3])" in MODLOADER
    assert "finish_observatory_spawn_coordinate_trial(parts[2])" in MODLOADER
    assert "abort_observatory_spawn_coordinate_trial(parts[2])" in MODLOADER
    assert (
        "e9f7392eb6d529be306c085271414d9e1fe17c2de03cf4266a692af6d1af11a1"
    ) in MODLOADER
    assert "load_observatory_spawn_coordinate_module" in MODLOADER
    prepare_start = MODLOADER.index(
        "local function prepare_observatory_spawn_coordinate_trial"
    )
    finish_start = MODLOADER.index(
        "local function finish_observatory_spawn_coordinate_trial"
    )
    prepare_block = MODLOADER[prepare_start:finish_start]
    assert 'rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED' in prepare_block
    assert 'rawget(observer, "arm")' in prepare_block
    assert "end_player_turn" not in prepare_block
    assert 'rawget(observer, "finish")' in MODLOADER
    assert "SPAWN_COORDINATE_SNAPSHOT_FILE" in MODLOADER
