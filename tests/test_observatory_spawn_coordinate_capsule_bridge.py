from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bridge import protocol


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


def test_capsule_load_check_requires_exact_dormant_unconsumed_ack(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_SPAWN_CAPSULE_LOAD_CHECK "
            "state=dormant consumed=false armed=false"
        ),
    )

    ack = protocol.check_observatory_spawn_coordinate_capsule_load(timeout=0.2)

    assert ack.endswith("state=dormant consumed=false armed=false")
    assert commands == ["OBS_SPAWN_CAPSULE_LOAD_CHECK"]


@pytest.mark.parametrize(
    ("condition", "counts"),
    [
        ("control", (0, 0, 0, 0, 0, 0)),
        ("dormant", (0, 0, 0, 0, 0, 0)),
        ("armed", (2, 1, 0, 1, 1, 1)),
    ],
)
def test_capsule_boundary_requires_fresh_armed_output(
    condition: str,
    counts: tuple[int, int, int, int, int, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    snapshot_path = tmp_path / "spawn-coordinate-capsule.json"
    monkeypatch.setattr(
        protocol, "SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE", snapshot_path
    )
    monkeypatch.setattr(
        protocol,
        "SPAWN_COORDINATE_CAPSULE_SNAPSHOT_TMP",
        tmp_path / "spawn-coordinate-capsule.json.tmp",
    )
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda **_kwargs: True)
    commands: list[str] = []
    monkeypatch.setattr(protocol, "write_command", commands.append)
    capture_id = f"spawn-capsule-{condition}-01"
    draws, scheduler, fallback, standard, selectors, capsules = counts

    def ack(**_kwargs):
        command = commands[-1]
        if command.startswith("OBS_SPAWN_CAPSULE_PREPARE"):
            armed = "true" if condition == "armed" else "false"
            return (
                f"OK OBS_SPAWN_CAPSULE_PREPARE condition={condition} "
                f"capture={capture_id} seed=324508639 armed={armed}"
            )
        if condition == "armed":
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": (
                            "native_spawn_coordinate_capsule_hw_observer_snapshot"
                        ),
                        "capture_id": capture_id,
                        "integrity": {"complete": True},
                        "summary": {
                            "draw_record_count": draws,
                            "scheduler_count": scheduler,
                            "selector_fallback_count": fallback,
                            "selector_standard_count": standard,
                            "selector_count": selectors,
                            "capsule_count": capsules,
                        },
                    }
                ),
                encoding="utf-8",
            )
        return (
            f"OK OBS_SPAWN_CAPSULE_FINISH condition={condition} "
            f"capture={capture_id} draws={draws} scheduler={scheduler} "
            f"fallback={fallback} standard={standard} selectors={selectors} "
            f"capsules={capsules} complete=true"
        )

    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    prepare_ack = protocol.prepare_observatory_spawn_coordinate_capsule(
        condition, capture_id, timeout=0.2
    )
    finish_ack, snapshot = protocol.finish_observatory_spawn_coordinate_capsule(
        condition, capture_id, timeout=0.2
    )

    assert prepare_ack.endswith(
        f"armed={'true' if condition == 'armed' else 'false'}"
    )
    assert finish_ack.endswith(f"capsules={capsules} complete=true")
    assert (snapshot is not None) is (condition == "armed")
    assert commands == [
        f"OBS_SPAWN_CAPSULE_PREPARE {condition} {capture_id}",
        f"OBS_SPAWN_CAPSULE_FINISH {capture_id}",
    ]


def test_capsule_abort_requires_a_clean_restore_ack(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(protocol, "write_command", lambda _command: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda **_kwargs: (
            "OK OBS_SPAWN_CAPSULE_ABORT condition=armed "
            "capture=spawn-capsule-armed-01 restored=true"
        ),
    )

    assert protocol.abort_observatory_spawn_coordinate_capsule(
        "spawn-capsule-armed-01"
    ).endswith("restored=true")


def test_capsule_modloader_path_is_separate_build_keyed_and_non_advancing():
    assert 'elseif cmd == "OBS_SPAWN_CAPSULE_LOAD_CHECK" then' in MODLOADER
    assert 'elseif cmd == "OBS_SPAWN_CAPSULE_PREPARE" then' in MODLOADER
    assert 'elseif cmd == "OBS_SPAWN_CAPSULE_FINISH" then' in MODLOADER
    assert 'elseif cmd == "OBS_SPAWN_CAPSULE_ABORT" then' in MODLOADER
    assert "SPAWN_COORDINATE_CAPSULE.load_check()" in MODLOADER
    assert "SPAWN_COORDINATE_CAPSULE.prepare(parts[2], parts[3])" in MODLOADER
    assert "SPAWN_COORDINATE_CAPSULE.finish(parts[2])" in MODLOADER
    assert "SPAWN_COORDINATE_CAPSULE.abort(parts[2])" in MODLOADER
    assert (
        "bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9"
    ) in MODLOADER
    assert (
        "e79fb1f734f06dee9862b15f29e0bbccfa82e34b3fe2506565ab56ad45d39ca1"
    ) in MODLOADER
    assert "SPAWN_COORDINATE_SNAPSHOT_FILE" in MODLOADER
    assert "SPAWN_COORDINATE_CAPSULE.snapshot_file" in MODLOADER
    prepare_start = MODLOADER.index("function SPAWN_COORDINATE_CAPSULE.prepare")
    finish_start = MODLOADER.index("function SPAWN_COORDINATE_CAPSULE.finish")
    prepare_block = MODLOADER[prepare_start:finish_start]
    assert 'rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED' in prepare_block
    assert 'rawget(observer, "arm")' in prepare_block
    assert "end_player_turn" not in prepare_block
    assert "Board:SpawnQueued()" not in prepare_block
    assert "write_observatory_create_only_json(" in MODLOADER
