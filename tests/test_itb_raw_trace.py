"""Tests for the untrusted-Lua to authoritative-trace boundary."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

import pytest

from scripts.itb_trace import main as trace_cli
from src.observatory.raw_trace import (
    RawTraceError,
    arm_packet_sha256,
    build_arm_packet,
    finalize_raw_checkpoint,
)
from src.observatory.trace_store import (
    read_arm_packet,
    read_raw_checkpoint,
    stable_file_sha256,
    write_arm_packet,
)
from src.observatory.trace_codec import (
    EVENT_KINDS,
    TraceConfig,
    build_identity_sha256,
    encode_trace,
    hook_coverage_sha256,
    trace_config_sha256,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


def _build_identity() -> dict:
    return {
        "platform": "windows",
        "architecture": "x86",
        "architectures": None,
        "executable_sha256": HASH_A,
        "build_id": "13725832",
        "depot_manifest": "8335438558621014449",
        "build_evidence": "local_appmanifest",
        "scripts_revision_sha256": HASH_B,
        "maps_revision_sha256": HASH_C,
    }


def _inventory() -> dict:
    identity = _build_identity()
    return {
        "app_id": "590380",
        "platform": identity["platform"],
        "executable": {
            "architecture": identity["architecture"],
            "sha256": identity["executable_sha256"],
        },
        "steam": {
            "app_id": "590380",
            "build_id": identity["build_id"],
            "evidence": {
                "path": "appmanifest_590380.acf",
                "sha256": HASH_D,
            },
            "installed_depots": [
                {
                    "depot_id": "590381",
                    "manifest": identity["depot_manifest"],
                }
            ],
        },
        "content": {
            "scripts": {
                "revision_sha256": identity["scripts_revision_sha256"]
            },
            "maps": {"revision_sha256": identity["maps_revision_sha256"]},
        },
    }


def _config() -> TraceConfig:
    return TraceConfig(
        enabled=True,
        allowed_phases=("combat_enemy",),
        max_events=32,
        max_events_per_turn=32,
        max_event_bytes=4096,
        max_total_event_bytes=64 * 1024,
        max_bundle_bytes=3 * 1024 * 1024,
    )


def _hook_plan() -> list[dict]:
    return [
        {
            "hook_id": f"hook.{kind}",
            "event_kind": kind,
            "target": f"_G.{kind}",
            "target_kind": "lua_global",
            "status": "installed" if kind == "random_int" else "disabled",
            "source_sha256": HASH_C,
        }
        for kind in sorted(EVENT_KINDS)
    ]


def _coverage() -> list[dict]:
    return [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in _hook_plan()
    ]


def _capture_identity() -> dict:
    config = _config()
    return {
        "capture_id": "experiment-001",
        "arm_nonce": "0123456789abcdef0123456789abcdef",
        "controller_version": "observatory-controller/1",
        "controller_sha256": HASH_D,
        "installed_modloader_sha256": HASH_E,
        "expected_mission_id": "Mission_Test",
        "expected_turn": 2,
        "timeline_fingerprint": HASH_A,
        "master_seed": -12345,
        "region_id": "archive_a",
        "ai_seed_fingerprint": HASH_B,
        "expected_phase": "combat_enemy",
        "config_sha256": trace_config_sha256(config),
        "hook_coverage_sha256": hook_coverage_sha256(_coverage()),
        "activated_at_utc": "2026-07-24T12:00:00Z",
        "expires_at_utc": "2026-07-24T12:05:00Z",
    }


def _epoch(text: str) -> int:
    return int(
        datetime.fromisoformat(text[:-1] + "+00:00")
        .astimezone(timezone.utc)
        .timestamp()
    )


def _event() -> dict:
    return {
        "seq": 0,
        "kind": "random_int",
        "phase": "combat_enemy",
        "mission_id": "Mission_Test",
        "turn": 2,
        "context": {"call_site": "_G.random_int"},
        "payload": {"call_order": 0, "upper_bound": 5, "result": 2},
    }


def _raw(capture: dict | None = None) -> dict:
    capture = capture or _capture_identity()
    event = _event()
    exact_bytes = len(
        json.dumps(
            event,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ) + 1
    attempted = {kind: 0 for kind in EVENT_KINDS}
    attempted["random_int"] = 1
    return {
        "raw_schema_version": 1,
        "runtime_version": "observatory-lua/1",
        "capture_id": capture["capture_id"],
        "checkpoint_seq": 7,
        "arm_nonce": capture["arm_nonce"],
        "controller_version": capture["controller_version"],
        "controller_sha256": capture["controller_sha256"],
        "installed_modloader_sha256": capture[
            "installed_modloader_sha256"
        ],
        "build_identity_sha256": build_identity_sha256(_build_identity()),
        "expected_mission_id": capture["expected_mission_id"],
        "expected_turn": capture["expected_turn"],
        "expected_phase": capture["expected_phase"],
        "timeline_fingerprint": capture["timeline_fingerprint"],
        "master_seed": capture["master_seed"],
        "region_id": capture["region_id"],
        "ai_seed_fingerprint": capture["ai_seed_fingerprint"],
        "config_sha256": capture["config_sha256"],
        "hook_coverage_sha256": capture["hook_coverage_sha256"],
        "config": _config().to_dict(),
        "hook_coverage": _coverage(),
        "activated_epoch": _epoch(capture["activated_at_utc"]),
        "expires_epoch": _epoch(capture["expires_at_utc"]),
        "started_epoch": _epoch("2026-07-24T12:00:01Z"),
        "completed_epoch": _epoch("2026-07-24T12:00:02Z"),
        "checkpoint_reason": "explicit",
        "attempted_calls": attempted,
        "events": [event],
        "summary": {
            "accepted_events": 1,
            "event_byte_upper_bound": exact_bytes + 500,
            "dropped_events": 0,
            "filtered_events": 0,
            "serialization_errors": 0,
            "truncation_reasons": {},
            "stop_reasons": {},
            "restore_conflicts": 0,
        },
    }


def _finalize(raw: dict) -> dict:
    packet = build_arm_packet(
        build_identity=_build_identity(),
        capture_identity=_capture_identity(),
        config=_config().to_dict(),
        hook_plan=_hook_plan(),
        max_attempts=64,
        checkpoint_seq=7,
    )
    return finalize_raw_checkpoint(
        raw,
        build_identity=_build_identity(),
        capture_identity=_capture_identity(),
        arm_packet=packet,
        expected_arm_packet_sha256=arm_packet_sha256(packet),
    )


def test_build_arm_packet_matches_lua_contract_and_is_deterministic():
    packet = build_arm_packet(
        build_identity=_build_identity(),
        capture_identity=_capture_identity(),
        config=_config().to_dict(),
        hook_plan=_hook_plan(),
        max_attempts=64,
        checkpoint_seq=7,
    )

    assert packet["manifest"]["schema_version"] == 1
    assert packet["manifest"]["build_identity_sha256"] == (
        build_identity_sha256(_build_identity())
    )
    assert packet["manifest"]["allowed_kinds"] == ["random_int"]
    assert packet["policy"]["allowed_kinds"] == ["random_int"]
    assert packet["trusted"]["config_sha256"] == (
        _capture_identity()["config_sha256"]
    )
    assert packet["hook_plan"] == _hook_plan()
    assert arm_packet_sha256(packet) == arm_packet_sha256(copy.deepcopy(packet))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda plan, capture, config: plan[0].update(extra=True),
            "unknown fields",
        ),
        (
            lambda plan, capture, config: plan[0].update(
                status="unavailable", source_sha256=None
            ),
            "installed or disabled",
        ),
        (
            lambda plan, capture, config: capture.update(
                config_sha256=HASH_A
            ),
            "config digest mismatch",
        ),
        (
            lambda plan, capture, config: config.update(
                max_bundle_bytes=64 * 1024
            ),
            "checkpoint reserve",
        ),
        (
            lambda plan, capture, config: capture.update(
                activated_at_utc="1969-12-31T23:58:00Z",
                expires_at_utc="1969-12-31T23:59:00Z",
            ),
            "capture window is invalid",
        ),
        (
            lambda plan, capture, config: capture.update(
                controller_version="\u00e9" * 100
            ),
            "controller_version exceeds the Lua runtime byte limit",
        ),
        (
            lambda plan, capture, config: plan[0].update(
                target="\u00e9" * 200
            ),
            "target exceeds the Lua runtime byte limit",
        ),
        (
            lambda plan, capture, config: plan[6].update(
                target="_G.some_other_function"
            ),
            "exact Lua global RNG target",
        ),
        (
            lambda plan, capture, config: capture.update(
                master_seed=(2**53) + 1
            ),
            "master_seed is outside the exact Lua integer range",
        ),
    ],
)
def test_build_arm_packet_rejects_untrusted_or_impossible_inputs(
    mutation,
    message,
):
    plan = _hook_plan()
    capture = _capture_identity()
    config = _config().to_dict()
    mutation(plan, capture, config)
    with pytest.raises(RawTraceError, match=message):
        build_arm_packet(
            build_identity=_build_identity(),
            capture_identity=capture,
            config=config,
            hook_plan=plan,
            max_attempts=64,
            checkpoint_seq=7,
        )


def test_build_arm_packet_rejects_inexact_checkpoint_sequence():
    with pytest.raises(RawTraceError, match="exact Lua integer range"):
        build_arm_packet(
            build_identity=_build_identity(),
            capture_identity=_capture_identity(),
            config=_config().to_dict(),
            hook_plan=_hook_plan(),
            max_attempts=64,
            checkpoint_seq=(2**53) + 1,
        )


def test_finalize_raw_checkpoint_recomputes_canonical_bytes_and_validates():
    raw = _raw()
    trace = _finalize(raw)

    exact_bytes = len(
        json.dumps(
            raw["events"][0],
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ) + 1
    assert trace["schema_version"] == 2
    assert trace["checkpoint"]["seq"] == 7
    assert trace["checkpoint"]["started_at_utc"] == (
        "2026-07-24T12:00:01Z"
    )
    assert trace["checkpoint"]["completed_at_utc"] == (
        "2026-07-24T12:00:02Z"
    )
    assert trace["summary"]["event_bytes"] == exact_bytes
    assert trace["summary"]["event_bytes"] != (
        raw["summary"]["event_byte_upper_bound"]
    )
    assert encode_trace(trace).endswith("\n")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda raw: raw.update(extra=True),
            "unknown fields",
        ),
        (
            lambda raw: raw.update(capture_id="other"),
            "does not match trusted capture",
        ),
        (
            lambda raw: raw.update(build_identity_sha256=HASH_E),
            "build identity digest mismatch",
        ),
        (
            lambda raw: raw["summary"]["stop_reasons"].update(
                capture_expired=1
            ),
            "invalid raw summary.stop_reasons key",
        ),
        (
            lambda raw: raw["summary"].update(restore_conflicts=1),
            "restore conflicts",
        ),
        (
            lambda raw: raw["summary"].update(event_byte_upper_bound=1),
            "below canonical event bytes",
        ),
        (
            lambda raw: raw["attempted_calls"].update(random_int=2),
            "do not reconcile",
        ),
        (
            lambda raw: raw["events"][0]["payload"].update(result=5),
            "cannot be finalized",
        ),
        (
            lambda raw: raw.update(completed_epoch=raw["expires_epoch"] + 1),
            "outside capture window",
        ),
    ],
)
def test_finalize_raw_checkpoint_rejects_unsafe_or_inconsistent_data(
    mutation,
    message,
):
    raw = _raw()
    mutation(raw)
    with pytest.raises(RawTraceError, match=message):
        _finalize(raw)


def test_finalize_rejects_stopped_capture_even_when_counters_reconcile():
    raw = _raw()
    raw["attempted_calls"]["random_int"] = 2
    raw["summary"].update(
        dropped_events=1,
        truncation_reasons={"max_total_event_bytes": 1},
        stop_reasons={"max_total_event_bytes": 1},
    )

    with pytest.raises(RawTraceError, match="stopped Lua captures"):
        _finalize(raw)


def test_finalize_accepts_only_empty_lua_array_for_empty_reason_maps():
    raw = _raw()
    raw["summary"]["truncation_reasons"] = []
    raw["summary"]["stop_reasons"] = []
    assert _finalize(raw)["summary"]["truncation_reasons"] == {}

    raw = _raw()
    raw["summary"]["truncation_reasons"] = ["max_events"]
    with pytest.raises(RawTraceError, match="must be an object"):
        _finalize(raw)


def test_build_identity_digest_is_canonical_and_type_sensitive():
    identity = _build_identity()
    reordered = dict(reversed(list(identity.items())))
    assert build_identity_sha256(identity) == build_identity_sha256(reordered)
    assert build_identity_sha256(identity) == hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def test_arm_and_raw_file_readers_require_exact_names_and_digests(tmp_path):
    packet = build_arm_packet(
        build_identity=_build_identity(),
        capture_identity=_capture_identity(),
        config=_config().to_dict(),
        hook_plan=_hook_plan(),
        max_attempts=64,
        checkpoint_seq=7,
    )
    arm_root = tmp_path / "arms"
    arm_path = write_arm_packet(packet, root=arm_root)
    arm_digest = stable_file_sha256(arm_path)
    assert read_arm_packet(
        arm_path,
        expected_capture_id="experiment-001",
        expected_checkpoint_seq=7,
        expected_arm_sha256=arm_digest,
        root=arm_root,
    ) == packet

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw_path = raw_root / "itb_observatory_trace_experiment-001_7.raw"
    raw_path.write_text(
        json.dumps(_raw(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_digest = stable_file_sha256(raw_path)
    assert read_raw_checkpoint(
        raw_path,
        expected_capture_id="experiment-001",
        expected_checkpoint_seq=7,
        expected_raw_sha256=raw_digest,
        root=raw_root,
        max_bytes=_config().max_bundle_bytes,
    )["capture_id"] == "experiment-001"
    with pytest.raises(Exception, match="content digest mismatch"):
        read_raw_checkpoint(
            raw_path,
            expected_capture_id="experiment-001",
            expected_checkpoint_seq=7,
            expected_raw_sha256=HASH_A,
            root=raw_root,
            max_bytes=_config().max_bundle_bytes,
        )


def test_cli_build_arm_and_finalize_raw_end_to_end(tmp_path, capsys):
    controller = tmp_path / "controller.bundle"
    modloader = tmp_path / "modloader.lua"
    controller.write_bytes(b"controller-runtime-v1\n")
    modloader.write_bytes(b"modloader-v1\n")
    capture = _capture_identity()
    capture["controller_sha256"] = stable_file_sha256(controller)
    capture["installed_modloader_sha256"] = stable_file_sha256(modloader)

    inventory_path = tmp_path / "inventory.json"
    capture_path = tmp_path / "capture.json"
    config_path = tmp_path / "config.json"
    hook_path = tmp_path / "hooks.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    capture_path.write_text(json.dumps(capture), encoding="utf-8")
    config_path.write_text(json.dumps(_config().to_dict()), encoding="utf-8")
    hook_path.write_text(
        json.dumps({"hook_plan": _hook_plan()}), encoding="utf-8"
    )
    arm_root = tmp_path / "arms"
    assert trace_cli(
        [
            "build-arm",
            "--inventory",
            str(inventory_path),
            "--capture-identity",
            str(capture_path),
            "--controller-artifact",
            str(controller),
            "--installed-modloader",
            str(modloader),
            "--config",
            str(config_path),
            "--hook-plan",
            str(hook_path),
            "--max-attempts",
            "64",
            "--checkpoint-seq",
            "7",
            "--output-root",
            str(arm_root),
        ]
    ) == 0
    arm_output = capsys.readouterr().out.strip()
    arm_path = next(arm_root.glob("*.json"))
    arm_digest = stable_file_sha256(arm_path)
    assert f"sha256={arm_digest}" in arm_output

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw_path = raw_root / "itb_observatory_trace_experiment-001_7.raw"
    raw_path.write_text(
        json.dumps(_raw(capture), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_digest = stable_file_sha256(raw_path)
    final_root = tmp_path / "final"
    assert trace_cli(
        [
            "finalize-raw",
            str(raw_path),
            "--inventory",
            str(inventory_path),
            "--capture-identity",
            str(capture_path),
            "--controller-artifact",
            str(controller),
            "--installed-modloader",
            str(modloader),
            "--arm",
            str(arm_path),
            "--arm-root",
            str(arm_root),
            "--arm-sha256",
            arm_digest,
            "--raw-root",
            str(raw_root),
            "--raw-sha256",
            raw_digest,
            "--checkpoint-seq",
            "7",
            "--output-root",
            str(final_root),
        ]
    ) == 0
    final_output = capsys.readouterr().out.strip()
    final_path = next(final_root.glob("*.json"))
    assert f"sha256={stable_file_sha256(final_path)}" in final_output


_CALLBACK_SLOTS = (
    ("slot-0001", "GetTargetArea", "get_target_area", "fn-0001"),
    ("slot-0002", "GetTargetArea", "get_target_area", "fn-0002"),
    ("slot-0003", "GetTargetScore", "enemy_target_score", "fn-0003"),
    ("slot-0004", "GetSkillEffect", "get_skill_effect", "fn-0004"),
    ("slot-0005", "ScorePositioning", "score_positioning", "fn-0005"),
)


def _callback_hook_plan(installed_kind: str) -> list[dict]:
    plan = [
        {
            "hook_id": f"callback.{slot_id}",
            "event_kind": kind,
            "target": f"runtime.callback.{slot_id}.{method}.{function_id}",
            "target_kind": (
                "lua_global" if method == "ScorePositioning" else "lua_method"
            ),
            "status": "installed" if kind == installed_kind else "disabled",
            "source_sha256": HASH_C,
        }
        for slot_id, method, kind, function_id in _CALLBACK_SLOTS
    ]
    covered = {entry["event_kind"] for entry in plan}
    for kind in sorted(EVENT_KINDS - covered):
        plan.append(
            {
                "hook_id": f"disabled.{kind}",
                "event_kind": kind,
                "target": f"disabled.{kind}",
                "target_kind": (
                    "lua_global"
                    if kind in {"random_bool", "random_int"}
                    else "native_boundary"
                ),
                "status": "disabled",
                "source_sha256": HASH_D,
            }
        )
    return sorted(plan, key=lambda item: (item["event_kind"], item["target"]))


def _callback_capture_identity(installed_kind: str) -> dict:
    capture = _capture_identity()
    capture["controller_version"] = "observatory-callback-controller/1"
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in _callback_hook_plan(installed_kind)
    ]
    capture["hook_coverage_sha256"] = hook_coverage_sha256(coverage)
    return capture


def _callback_event(kind: str) -> dict:
    payloads = {
        "score_positioning": {
            "pawn_uid": 42,
            "candidate_order": 0,
            "position": [2, 3],
            "score": 4.5,
        },
        "get_target_area": {
            "payload_version": 1,
            "representation": "coordinate_list",
            "pawn_uid": 42,
            "skill_id": "ScorpionAtk1",
            "origin": [2, 3],
            "target_area": [[2, 4], [2, 5]],
            "call_order": 0,
        },
        "enemy_target_score": {
            "payload_version": 1,
            "representation": "get_target_score_arguments",
            "pawn_uid": 42,
            "skill_id": "ScorpionAtk1",
            "pawn_space": [1, 3],
            "p1": [2, 3],
            "p2": [2, 5],
            "call_order": 0,
            "score": 7.25,
        },
        "get_skill_effect": {
            "payload_version": 1,
            "representation": "raw_opaque_primitives",
            "pawn_uid": 42,
            "skill_id": "ScorpionAtk1",
            "origin": [2, 3],
            "target": [2, 4],
            "call_order": 0,
            "primitive_count": 3,
            "primitive_summary": {
                "effect": [
                    {
                        "index": 0,
                        "fields": [
                            {"name": "iDamage", "value": 2},
                            {"name": "iPush", "value": 1},
                            {"name": "loc", "value": [2, 4]},
                        ],
                    }
                ],
                "q_effect": [],
            },
        },
    }
    return {
        "seq": 0,
        "kind": kind,
        "phase": "combat_enemy",
        "mission_id": "Mission_Test",
        "turn": 2,
        "context": {
            "call_site": "runtime.callback.slot-0001.Test.fn-0001",
            "source": "fn-0001",
        },
        "payload": payloads[kind],
    }


def _callback_raw(installed_kind: str) -> tuple[dict, dict, dict]:
    capture = _callback_capture_identity(installed_kind)
    plan = _callback_hook_plan(installed_kind)
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in plan
    ]
    event = _callback_event(installed_kind)
    raw = _raw(capture)
    raw["hook_coverage"] = coverage
    raw["events"] = [event]
    raw["attempted_calls"] = {kind: 0 for kind in EVENT_KINDS}
    raw["attempted_calls"][installed_kind] = 1
    raw["summary"]["event_byte_upper_bound"] = len(
        json.dumps(
            event,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ) + 501
    packet = build_arm_packet(
        build_identity=_build_identity(),
        capture_identity=capture,
        config=_config().to_dict(),
        hook_plan=plan,
        max_attempts=64,
        checkpoint_seq=7,
    )
    return raw, capture, packet


def _finalize_callback(installed_kind: str) -> dict:
    raw, capture, packet = _callback_raw(installed_kind)
    return finalize_raw_checkpoint(
        raw,
        build_identity=_build_identity(),
        capture_identity=capture,
        arm_packet=packet,
        expected_arm_packet_sha256=arm_packet_sha256(packet),
    )


@pytest.mark.parametrize(
    "kind",
    [
        "score_positioning",
        "get_target_area",
        "enemy_target_score",
        "get_skill_effect",
    ],
)
def test_callback_raw_events_promote_to_schema_v2(kind):
    trace = _finalize_callback(kind)
    event = trace["events"][0]
    assert event["kind"] == kind
    assert trace["checkpoint"]["attempted_calls"][kind] == 1
    if kind == "get_target_area":
        assert "call_order" not in event["payload"]
        assert event["payload"]["target_area"] == [[2, 4], [2, 5]]
    elif kind == "enemy_target_score":
        assert event["payload"]["origin"] == [1, 3]
        assert event["payload"]["destination"] == [2, 3]
        assert event["payload"]["target"] == [2, 5]
        assert event["payload"]["candidate_order"] == 0
    elif kind == "get_skill_effect":
        summary = _callback_event(kind)["payload"]["primitive_summary"]
        expected = hashlib.sha256(
            (
                json.dumps(
                    summary,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()
        assert event["payload"]["summary_sha256"] == expected
        assert event["payload"]["primitive_count"] == 3


def test_callback_arm_packet_rejects_partial_family_or_non_slot_install():
    kind = "get_target_area"
    capture = _callback_capture_identity(kind)
    plan = _callback_hook_plan(kind)
    second = next(entry for entry in plan if entry["hook_id"] == "callback.slot-0002")
    second["status"] = "disabled"
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in plan
    ]
    capture["hook_coverage_sha256"] = hook_coverage_sha256(coverage)
    with pytest.raises(RawTraceError, match="family-complete"):
        build_arm_packet(
            build_identity=_build_identity(),
            capture_identity=capture,
            config=_config().to_dict(),
            hook_plan=plan,
            max_attempts=64,
            checkpoint_seq=7,
        )


def test_callback_finalize_rejects_torn_skill_effect_summary():
    raw, capture, packet = _callback_raw("get_skill_effect")
    raw["events"][0]["payload"]["primitive_count"] = 4
    with pytest.raises(RawTraceError, match="primitive_count mismatch"):
        finalize_raw_checkpoint(
            raw,
            build_identity=_build_identity(),
            capture_identity=capture,
            arm_packet=packet,
            expected_arm_packet_sha256=arm_packet_sha256(packet),
        )
