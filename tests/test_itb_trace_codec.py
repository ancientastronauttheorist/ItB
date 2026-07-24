"""Tests for bounded, behavior-neutral Observatory trace evidence."""

from __future__ import annotations

import json

import pytest

from src.observatory.trace_codec import (
    TraceBuffer,
    TraceCodecError,
    TraceConfig,
    encode_trace,
    parse_trace,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _identity() -> dict:
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


def _random_int_payload() -> dict:
    return {"upper_bound": 5, "result": 2}


def _encoded_with_exact_bundle_cap(trace: TraceBuffer) -> str:
    data = trace.to_dict()
    cap = data["config"]["max_bundle_bytes"]
    for _ in range(20):
        data["config"]["max_bundle_bytes"] = cap
        rendered = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        actual = len(rendered.encode("utf-8"))
        if actual == cap:
            return rendered
        cap = actual
    raise AssertionError("bundle-size fixed point did not converge")


def test_disabled_trace_does_not_evaluate_payload():
    called = False

    def payload():
        nonlocal called
        called = True
        return _random_int_payload()

    trace = TraceBuffer(_identity())
    assert not trace.record_lazy(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload_factory=payload,
    )
    assert not called
    assert trace.to_dict()["summary"]["accepted_events"] == 0


def test_phase_filter_and_turn_cap_short_circuit_payload():
    calls = 0

    def payload():
        nonlocal calls
        calls += 1
        return {"upper_bound": 5, "result": calls}

    trace = TraceBuffer(
        _identity(),
        TraceConfig(enabled=True, max_events_per_turn=1),
    )
    assert not trace.record_lazy(
        "random_int",
        phase="combat_player",
        mission_id="Mission_Test",
        turn=1,
        payload_factory=payload,
    )
    assert trace.record_lazy(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload_factory=payload,
    )
    assert not trace.record_lazy(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload_factory=payload,
    )
    assert calls == 1
    summary = trace.to_dict()["summary"]
    assert summary["filtered_events"] == 1
    assert summary["truncation_reasons"] == {
        "max_events_per_turn": 1
    }


def test_invalid_runtime_phase_is_an_error_not_a_filter():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "random_int",
        phase="combat_enmey",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
    )
    summary = trace.to_dict()["summary"]
    assert summary["serialization_errors"] == 1
    assert summary["filtered_events"] == 0


def test_falsy_non_mapping_context_is_not_silently_normalized():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
        context=[],  # type: ignore[arg-type]
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 1


def test_payload_error_is_observational_and_swallowed():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))

    def broken_payload():
        raise RuntimeError("observatory extraction failed")

    assert not trace.record_lazy(
        "get_skill_effect",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=2,
        payload_factory=broken_payload,
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 1


def test_invalid_payload_is_rejected_without_escaping():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={"upper_bound": 5, "result": 5},
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 1


def test_event_byte_cap_is_enforced():
    trace = TraceBuffer(
        _identity(),
        TraceConfig(enabled=True, max_event_bytes=240),
    )
    assert not trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        context={"source": "é" * 200},
        payload=_random_int_payload(),
    )
    assert trace.to_dict()["summary"]["truncation_reasons"] == {
        "max_event_bytes": 1
    }


def test_total_byte_cap_short_circuits_payload_when_full():
    probe = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert probe.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
    )
    event_bytes = probe.to_dict()["summary"]["event_bytes"]

    trace = TraceBuffer(
        _identity(),
        TraceConfig(
            enabled=True,
            max_total_event_bytes=event_bytes,
        ),
    )
    assert trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
    )
    called = False

    def payload():
        nonlocal called
        called = True
        return {"argument": 15, "result": True}

    assert not trace.record_lazy(
        "random_bool",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload_factory=payload,
    )
    assert not called
    assert trace.to_dict()["summary"]["truncation_reasons"] == {
        "max_total_event_bytes": 1
    }


def test_trace_round_trip_is_deterministic():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert trace.record(
        "enemy_target_score",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=3,
        context={"call_site": "Skill:GetTargetScore"},
        payload={
            "pawn_uid": 42,
            "skill_id": "FireflyAtk1",
            "candidate_order": 7,
            "origin": [3, 4],
            "destination": [4, 4],
            "target": [4, 1],
            "target_score": 5,
        },
    )
    first = encode_trace(trace)
    parsed = parse_trace(first)
    second = encode_trace(parsed)
    assert first == second
    assert parsed["events"][0]["seq"] == 0
    assert parsed["summary"]["event_bytes"] > 0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"upper_bound": 0, "result": 0}, "upper_bound"),
        ({"upper_bound": 5, "result": True}, "result"),
        ({"upper_bound": 5, "result": 5}, "below upper_bound"),
        (
            {"upper_bound": 5, "result": 2, "unknown": 1},
            "unknown fields",
        ),
    ],
)
def test_random_int_schema_rejects_malformed_payload(payload, message):
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
    )
    data = trace.to_dict()
    data["events"][0]["payload"] = payload
    with pytest.raises(TraceCodecError, match=message):
        parse_trace(json.dumps(data))


@pytest.mark.parametrize(
    "payload",
    [
        {"argument": 0, "result": True},
        {"argument": 5.0, "result": False},
        {"argument": 5, "result": 1},
    ],
)
def test_random_bool_schema_rejects_malformed_payload(payload):
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    trace.record(
        "random_bool",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={"argument": 15, "result": True},
    )
    data = trace.to_dict()
    data["events"][0]["payload"] = payload
    with pytest.raises(TraceCodecError):
        parse_trace(json.dumps(data))


def test_coordinates_scores_and_selected_action_are_validated():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "score_positioning",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "pawn_uid": 1,
            "candidate_order": 0,
            "position": [8, 0],
            "score": 1,
        },
    )
    assert not trace.record(
        "enemy_action_selected",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "pawn_uid": 1,
            "skill_id": "",
            "origin": [0, 0],
            "destination": [1, 0],
            "target": [2, 0],
        },
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 2


def test_target_area_and_effect_payloads_are_explicitly_versioned():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert trace.record(
        "get_target_area",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "payload_version": 1,
            "representation": "coordinate_list",
            "pawn_uid": 1,
            "skill_id": "FireflyAtk1",
            "origin": [1, 1],
            "target_area": [[1, 2], [1, 3]],
        },
    )
    assert trace.record(
        "get_skill_effect",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "payload_version": 1,
            "representation": "opaque_primitive_summary",
            "pawn_uid": 1,
            "skill_id": "FireflyAtk1",
            "origin": [1, 1],
            "target": [1, 2],
            "primitive_count": 2,
            "summary_sha256": HASH_A,
        },
    )
    parse_trace(encode_trace(trace))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data.update(schema_version=99),
            "unsupported trace schema",
        ),
        (
            lambda data: data.update(schema_version=True),
            "unsupported trace schema",
        ),
        (
            lambda data: data["events"][0].update(seq=5),
            "non-contiguous event sequence",
        ),
        (
            lambda data: data["events"][0].update(kind="unknown"),
            "unknown event kind",
        ),
        (
            lambda data: data["events"][0].update(kind=[]),
            "unknown event kind",
        ),
        (
            lambda data: data["build_identity"].update(platform=[]),
            "platform",
        ),
        (
            lambda data: data["summary"].update(accepted_events=0),
            "accepted_events mismatch",
        ),
        (
            lambda data: data["build_identity"].update(
                executable_sha256="31fe"
            ),
            "lowercase SHA-256",
        ),
        (
            lambda data: data.update(unexpected=True),
            "unknown fields",
        ),
    ],
)
def test_malformed_trace_fails_closed(mutation, message: str):
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    trace.record(
        "random_bool",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={"argument": 15, "result": True},
    )
    data = trace.to_dict()
    mutation(data)
    with pytest.raises(TraceCodecError, match=message):
        parse_trace(json.dumps(data))


@pytest.mark.parametrize("field", ["accepted_events", "event_bytes"])
def test_empty_trace_summary_counts_require_exact_integers(field: str):
    data = TraceBuffer(_identity(), TraceConfig(enabled=True)).to_dict()
    data["summary"][field] = False
    with pytest.raises(TraceCodecError, match=field):
        parse_trace(json.dumps(data))


def test_build_identity_is_validated_at_buffer_construction():
    identity = _identity()
    identity["platform"] = "solaris"
    with pytest.raises(TraceCodecError, match="platform"):
        TraceBuffer(identity)

    identity = _identity()
    identity["build_id"] = None
    with pytest.raises(TraceCodecError, match="numeric"):
        TraceBuffer(identity)

    identity = _identity()
    identity.update(
        build_id=None,
        depot_manifest=None,
        build_evidence="unavailable",
    )
    TraceBuffer(identity)


def test_payload_versions_require_exact_integers():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "get_target_area",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "payload_version": True,
            "representation": "coordinate_list",
            "pawn_uid": 1,
            "skill_id": "FireflyAtk1",
            "origin": [1, 1],
            "target_area": [[1, 2]],
        },
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 1


def test_inventory_architecture_vocabulary_round_trips():
    armv7 = _identity()
    armv7.update(platform="linux", architecture="armv7")
    TraceBuffer(armv7)

    universal = _identity()
    universal.update(
        platform="macos",
        architecture="universal",
        architectures=["arm64", "x86_64"],
    )
    parsed = parse_trace(encode_trace(TraceBuffer(universal)))
    assert parsed["build_identity"]["architectures"] == ["arm64", "x86_64"]

    universal["architectures"] = ["x86_64", "arm64"]
    with pytest.raises(TraceCodecError, match="sorted unique"):
        TraceBuffer(universal)


@pytest.mark.parametrize(
    "phases",
    [
        "combat_enemy",
        ("combat_enemy", "combat_enemy"),
        ("unknown",),
        (),
    ],
)
def test_phase_configuration_rejects_ambiguous_values(phases):
    with pytest.raises(ValueError, match="allowed_phases"):
        TraceConfig(allowed_phases=phases)


def test_disabled_bundle_with_events_is_rejected():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload=_random_int_payload(),
    )
    data = trace.to_dict()
    data["config"]["enabled"] = False
    with pytest.raises(TraceCodecError, match="disabled trace"):
        parse_trace(json.dumps(data))


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(TraceCodecError, match="duplicate JSON key"):
        parse_trace('{"schema_version":1,"schema_version":1}')


def test_nonfinite_numbers_are_rejected_without_escaping():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert not trace.record(
        "score_positioning",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=1,
        payload={
            "pawn_uid": 1,
            "candidate_order": 0,
            "position": [1, 1],
            "score": float("nan"),
        },
    )
    assert trace.to_dict()["summary"]["serialization_errors"] == 1


def test_bundle_cap_counts_actual_utf8_bytes_at_exact_boundary():
    trace = TraceBuffer(_identity(), TraceConfig(enabled=True))
    assert trace.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Misión_é",
        turn=1,
        context={"source": "native_é"},
        payload=_random_int_payload(),
    )
    exact = _encoded_with_exact_bundle_cap(trace)
    assert parse_trace(exact)["events"][0]["mission_id"] == "Misión_é"

    data = json.loads(exact)
    data["config"]["max_bundle_bytes"] -= 1
    too_small = json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    assert len(too_small.encode("utf-8")) == len(exact.encode("utf-8"))
    with pytest.raises(TraceCodecError, match="max_bundle_bytes"):
        parse_trace(too_small)
