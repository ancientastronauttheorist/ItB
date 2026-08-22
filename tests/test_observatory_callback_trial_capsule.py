from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.callback_hook_plan import build_callback_hook_plan
from src.observatory.callback_trial_capsule import (
    CallbackTrialCapsuleError,
    arm_callback_trial_request,
    build_callback_trial_capsule,
    callback_trial_capsule_sha256,
    render_callback_trial_capsule,
    render_callback_trial_request,
    write_callback_trial_capsule,
)
from src.observatory.raw_trace import build_arm_packet
from src.observatory.trace_codec import (
    TraceConfig,
    hook_coverage_sha256,
    trace_config_sha256,
)
from src.observatory.trace_store import build_identity_from_inventory


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_local_modified.json"
)
BINDINGS = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260822T021034Z_callback_bindings.json"
)
JOIN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260821T201929Z_callback_join.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs(family: str = "get_target_area") -> tuple[dict, dict, dict]:
    bindings = _load(BINDINGS)
    join = _load(JOIN)
    plan = build_callback_hook_plan(bindings, join, installed_kind=family)
    coverage = [{key: value for key, value in item.items() if key != "hook_id"} for item in plan]
    config = TraceConfig(
        enabled=True,
        allowed_phases=("combat_enemy",),
        max_events=128,
        max_events_per_turn=128,
        max_event_bytes=32 * 1024,
        max_total_event_bytes=2 * 1024 * 1024,
        max_bundle_bytes=4 * 1024 * 1024,
    )
    capture = {
        "capture_id": f"callback-{family}-001",
        "arm_nonce": "0123456789abcdef0123456789abcdef",
        "controller_version": "observatory-callback-controller/1",
        "controller_sha256": "a" * 64,
        "installed_modloader_sha256": "b" * 64,
        "expected_mission_id": "Mission_Test",
        "expected_turn": 2,
        "timeline_fingerprint": "c" * 64,
        "master_seed": -1234,
        "region_id": "archive_a",
        "ai_seed_fingerprint": "d" * 64,
        "expected_phase": "combat_enemy",
        "config_sha256": trace_config_sha256(config),
        "hook_coverage_sha256": hook_coverage_sha256(coverage),
        "activated_at_utc": "2026-08-21T12:00:00Z",
        "expires_at_utc": "2026-08-21T12:10:00Z",
    }
    packet = build_arm_packet(
        build_identity=build_identity_from_inventory(_load(INVENTORY)),
        capture_identity=capture,
        config=config.to_dict(),
        hook_plan=plan,
        max_attempts=512,
        checkpoint_seq=0,
    )
    return packet, bindings, join


@pytest.mark.parametrize(
    "family",
    ["get_target_area", "enemy_target_score", "get_skill_effect", "score_positioning"],
)
def test_real_callback_capsule_is_deterministic_data_only(family):
    packet, bindings, join = _inputs(family)
    capsule = build_callback_trial_capsule(
        packet,
        bindings,
        join,
        capture_track="owner_local_modified",
        expected_mission_slot="island0_mission1",
        expected_ai_seed=991,
    )
    first = render_callback_trial_capsule(capsule)
    second = render_callback_trial_capsule(copy.deepcopy(capsule))

    assert first == second
    assert first.startswith("-- Generated data-only")
    assert "loadstring" not in first and "require(" not in first
    assert capsule["callback_family"] == family
    assert len(first.encode("utf-8")) < 4 * 1024 * 1024
    assert len(callback_trial_capsule_sha256(first)) == 64


def test_capsule_rejects_binding_join_and_packet_drift():
    packet, bindings, join = _inputs()
    drifted_join = copy.deepcopy(join)
    drifted_join["function_joins"][0]["source_sha256"] = "0" * 64
    with pytest.raises(CallbackTrialCapsuleError, match="hook plan is not exact"):
        build_callback_trial_capsule(
            packet,
            bindings,
            drifted_join,
            capture_track="owner_local_modified",
            expected_mission_slot="slot",
            expected_ai_seed=1,
        )

    capsule = build_callback_trial_capsule(
        packet,
        bindings,
        join,
        capture_track="owner_local_modified",
        expected_mission_slot="slot",
        expected_ai_seed=1,
    )
    capsule["binding_manifest"]["summary"]["slot_count"] += 1
    with pytest.raises(Exception):
        render_callback_trial_capsule(capsule)


def test_capsule_and_request_are_create_only(tmp_path):
    packet, bindings, join = _inputs("score_positioning")
    capsule = build_callback_trial_capsule(
        packet,
        bindings,
        join,
        capture_track="owner_local_modified",
        expected_mission_slot="slot",
        expected_ai_seed=8,
    )
    rendered = render_callback_trial_capsule(capsule)
    path = write_callback_trial_capsule(rendered, root=tmp_path)
    assert path.read_text(encoding="utf-8") == rendered
    with pytest.raises(CallbackTrialCapsuleError, match="already exists"):
        write_callback_trial_capsule(rendered, root=tmp_path)

    payload = render_callback_trial_request(
        condition="exact_hook",
        activation_nonce=packet["manifest"]["arm_nonce"],
        capsule_sha256=callback_trial_capsule_sha256(rendered),
    )
    request = arm_callback_trial_request(
        bridge_root=tmp_path,
        condition="exact_hook",
        activation_nonce=packet["manifest"]["arm_nonce"],
        capsule_sha256=callback_trial_capsule_sha256(rendered),
    )
    assert request.read_bytes() == payload
    with pytest.raises(CallbackTrialCapsuleError, match="already armed"):
        arm_callback_trial_request(
            bridge_root=tmp_path,
            condition="control",
            activation_nonce=packet["manifest"]["arm_nonce"],
            capsule_sha256=callback_trial_capsule_sha256(rendered),
        )


def test_request_can_bind_the_one_purpose_continue_helper():
    payload = render_callback_trial_request(
        condition="control",
        activation_nonce="a" * 32,
        capsule_sha256="b" * 64,
        continue_helper_sha256="c" * 64,
    )
    assert payload == (
        b"observatory-callback-trial-request/2\n"
        b"condition=control\n"
        b"activation_nonce=" + b"a" * 32 + b"\n"
        b"capsule_sha256=" + b"b" * 64 + b"\n"
        b"continue_helper_sha256=" + b"c" * 64 + b"\n"
    )
