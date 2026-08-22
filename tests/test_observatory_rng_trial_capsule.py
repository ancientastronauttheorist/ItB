from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.itb_observatory_rng_trial import main as rng_trial_cli
from src.observatory.raw_trace import arm_packet_sha256, build_arm_packet
from src.observatory.rng_trial_capsule import (
    REQUEST_FILENAME,
    RngTrialCapsuleError,
    arm_rng_trial_request,
    build_rng_trial_capsule,
    msvc_random_bool_first,
    msvc_random_int_first,
    render_rng_trial_capsule,
    render_rng_trial_request,
    rng_trial_capsule_sha256,
    write_rng_trial_capsule,
)
from src.observatory.trace_codec import hook_coverage_sha256
from src.observatory.trace_store import write_arm_packet
from tests.test_itb_raw_trace import (
    _build_identity,
    _capture_identity,
    _config,
    _hook_plan,
    _inventory,
)


def _packet(probe_kind: str = "random_int") -> dict:
    plan = _hook_plan()
    for entry in plan:
        entry["status"] = (
            "installed" if entry["event_kind"] == probe_kind else "disabled"
        )
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in plan
    ]
    capture = _capture_identity()
    capture["hook_coverage_sha256"] = hook_coverage_sha256(coverage)
    return build_arm_packet(
        build_identity=_build_identity(),
        capture_identity=capture,
        config=_config().to_dict(),
        hook_plan=plan,
        max_attempts=64,
        checkpoint_seq=7,
    )


HELPER_SHA = "e" * 64
SEED_REGION_SHA = "f" * 64
NATIVE_SEED = 123456789


def _capsule(**overrides) -> dict:
    options = {
        "capture_track": "owner_local_modified",
        "expected_mission_slot": "Mission2",
        "expected_ai_seed": 1,
        "native_seed": NATIVE_SEED,
        "seed_helper_sha256": HELPER_SHA,
        "rng_seed_rva": "0x00387f37",
        "rng_seed_region_sha256": SEED_REGION_SHA,
    }
    options.update(overrides)
    probe_kind = options.get("probe_kind", "random_int")
    return build_rng_trial_capsule(_packet(probe_kind), **options)


def test_capsule_is_deterministic_data_only_lua():
    capsule = _capsule(expected_ai_seed=-991, probe_upper_bound=65521)
    first = render_rng_trial_capsule(capsule)
    second = render_rng_trial_capsule(capsule)

    assert first == second
    assert first.startswith(
        "-- Generated data-only ITB Observatory RNG trial capsule.\nreturn {"
    )
    assert "loadstring" not in first
    assert "dofile" not in first
    assert "io." not in first
    assert "os." not in first
    assert '["architectures"]' not in first
    assert capsule["arm_packet_sha256"] == arm_packet_sha256(_packet())
    assert capsule["expected_save"] == {
        "mission_id": "Mission_Test",
        "mission_slot": "Mission2",
        "turn": 2,
        "master_seed": -12345,
        "region_id": "archive_a",
        "ai_seed": -991,
    }
    assert capsule["rng_control"]["expected_result"] == msvc_random_int_first(
        NATIVE_SEED,
        65521,
    )
    assert capsule["rng_control"]["helper_sha256"] == HELPER_SHA
    assert rng_trial_capsule_sha256(first) == hashlib.sha256(
        first.encode("utf-8")
    ).hexdigest()


def test_random_bool_capsule_binds_exact_hook_and_seeded_boolean():
    capsule = _capsule(
        probe_kind="random_bool",
        probe_argument=2,
        native_seed=0,
    )

    assert capsule["probe"] == {"kind": "random_bool", "argument": 2}
    assert capsule["rng_control"]["expected_result"] is True
    assert msvc_random_bool_first(0, 2) is True
    assert capsule["packet"]["policy"]["allowed_kinds"] == ["random_bool"]
    installed = [
        entry
        for entry in capsule["packet"]["hook_plan"]
        if entry["status"] == "installed"
    ]
    assert [entry["target"] for entry in installed] == ["_G.random_bool"]
    rendered = render_rng_trial_capsule(capsule)
    assert '["kind"] = "random_bool"' in rendered
    assert '["expected_result"] = true' in rendered


def test_capsule_rendering_is_type_sensitive_for_seeded_results():
    bool_capsule = _capsule(
        probe_kind="random_bool",
        probe_argument=2,
        native_seed=0,
    )
    bool_capsule["rng_control"]["expected_result"] = 1
    with pytest.raises(RngTrialCapsuleError, match="validated inputs"):
        render_rng_trial_capsule(bool_capsule)

    int_capsule = _capsule(native_seed=0, probe_upper_bound=2)
    assert int_capsule["rng_control"]["expected_result"] == 0
    int_capsule["rng_control"]["expected_result"] = False
    with pytest.raises(RngTrialCapsuleError, match="validated inputs"):
        render_rng_trial_capsule(int_capsule)


def test_capsule_rejects_non_exact_hook_and_transport_nulls():
    packet = _packet()
    packet["hook_plan"][5]["status"] = "installed"
    with pytest.raises(RngTrialCapsuleError, match="exactly one"):
        build_rng_trial_capsule(
            packet,
            capture_track="owner_local_modified",
            expected_mission_slot="Mission2",
            expected_ai_seed=1,
            native_seed=NATIVE_SEED,
            seed_helper_sha256=HELPER_SHA,
            rng_seed_rva="0x00387f37",
            rng_seed_region_sha256=SEED_REGION_SHA,
        )

    capsule = _capsule()
    capsule["packet"]["manifest"]["unexpected_null"] = None
    with pytest.raises(RngTrialCapsuleError):
        render_rng_trial_capsule(capsule)

    capsule = _capsule()
    capsule["probe"]["kind"] = []
    with pytest.raises(RngTrialCapsuleError, match="probe_kind"):
        render_rng_trial_capsule(capsule)


def test_capsule_publication_is_create_only(tmp_path):
    rendered = render_rng_trial_capsule(
        _capsule(expected_ai_seed=7)
    )
    path = write_rng_trial_capsule(rendered, root=tmp_path)
    assert path.read_text(encoding="utf-8") == rendered
    assert path.name.endswith(f"{rng_trial_capsule_sha256(rendered)}.lua")
    with pytest.raises(RngTrialCapsuleError, match="already exists"):
        write_rng_trial_capsule(rendered, root=tmp_path)


def test_request_is_exact_bounded_and_create_only(tmp_path):
    nonce = "f" * 32
    digest = "a" * 64
    payload = render_rng_trial_request(
        condition="exact_hook",
        activation_nonce=nonce,
        capsule_sha256=digest,
    )
    assert payload == (
        "observatory-rng-trial-request/1\n"
        "condition=exact_hook\n"
        f"activation_nonce={nonce}\n"
        f"capsule_sha256={digest}\n"
    ).encode("ascii")
    path = arm_rng_trial_request(
        bridge_root=tmp_path,
        condition="exact_hook",
        activation_nonce=nonce,
        capsule_sha256=digest,
    )
    assert path.name == REQUEST_FILENAME
    assert path.read_bytes() == payload
    with pytest.raises(RngTrialCapsuleError, match="already exists"):
        arm_rng_trial_request(
            bridge_root=tmp_path,
            condition="exact_hook",
            activation_nonce=nonce,
            capsule_sha256=digest,
        )


def test_rng_trial_cli_builds_capsule_and_request(tmp_path, capsys):
    arm_root = tmp_path / "arms"
    arm = write_arm_packet(_packet(), root=arm_root)
    arm_digest = arm_packet_sha256(_packet())
    capsule_root = tmp_path / "capsules"
    seed_helper = tmp_path / "seed_helper.dll"
    seed_helper.write_bytes(b"seed helper")
    assert rng_trial_cli(
        [
            "build-capsule",
            "--arm",
            str(arm),
            "--arm-sha256",
            arm_digest,
            "--capture-track",
            "owner_local_modified",
            "--expected-mission-slot",
            "Mission2",
            "--expected-ai-seed",
            "77",
            "--native-seed",
            str(NATIVE_SEED),
            "--seed-helper",
            str(seed_helper),
            "--rng-seed-rva",
            "0x00387f37",
            "--rng-seed-region-sha256",
            SEED_REGION_SHA,
            "--output-root",
            str(capsule_root),
        ]
    ) == 0
    output = capsys.readouterr().out
    capsule_path = next(capsule_root.glob("itb_observatory_rng_capsule_*.lua"))
    capsule_digest = rng_trial_capsule_sha256(
        capsule_path.read_text(encoding="utf-8")
    )
    assert capsule_digest in output

    bridge_root = tmp_path / "bridge"
    assert rng_trial_cli(
        [
            "arm-request",
            "--bridge-root",
            str(bridge_root),
            "--condition",
            "control",
            "--activation-nonce",
            "f" * 32,
            "--capsule-sha256",
            capsule_digest,
        ]
    ) == 0
    assert (bridge_root / REQUEST_FILENAME).is_file()


@pytest.mark.parametrize(
    ("probe_kind", "expected_source_sha"),
    [("random_int", "1" * 64), ("random_bool", "2" * 64)],
)
def test_prepare_pair_builds_complete_build_keyed_artifact_set(
    tmp_path,
    capsys,
    probe_kind,
    expected_source_sha,
):
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    identity = _build_identity()
    boundaries_path = tmp_path / "boundaries.json"
    boundaries_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "analysis_kind": "pe_reviewed_boundary_map",
                "identity": {
                    key: identity[key]
                    for key in (
                        "platform",
                        "architecture",
                        "executable_sha256",
                        "build_id",
                        "scripts_revision_sha256",
                        "maps_revision_sha256",
                    )
                },
                "regions": [
                    {"id": "random_int_1", "sha256": "1" * 64},
                    {"id": "random_bool_1", "sha256": "2" * 64},
                    {
                        "id": "rng_seed",
                        "start_rva": "0x00387f37",
                        "sha256": SEED_REGION_SHA,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    controller = tmp_path / "controller.lua"
    modloader = tmp_path / "modloader.lua"
    host = tmp_path / "host.lua"
    seed_helper = tmp_path / "seed_helper.dll"
    callback_join = tmp_path / "callback_join.json"
    for path, text in (
        (controller, "return {}\n"),
        (modloader, "return true\n"),
        (host, "return {}\n"),
        (seed_helper, "native helper\n"),
    ):
        path.write_text(text, encoding="utf-8")
    callback_join.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "analysis_kind": "runtime_callback_identity_join",
                "build_identity": {
                    key: identity[key]
                    for key in (
                        "platform",
                        "architecture",
                        "executable_sha256",
                        "build_id",
                        "depot_manifest",
                        "scripts_revision_sha256",
                        "maps_revision_sha256",
                    )
                },
                "summary": {
                    "function_count": 1,
                    "join_status_counts": {"matched": 1, "unmatched": 0},
                },
            }
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "pair"
    assert rng_trial_cli(
        [
            "prepare-pair",
            "--inventory",
            str(inventory_path),
            "--controller-artifact",
            str(controller),
            "--installed-modloader",
            str(modloader),
            "--trial-host",
            str(host),
            "--seed-helper",
            str(seed_helper),
            "--native-boundaries",
            str(boundaries_path),
            "--callback-join",
            str(callback_join),
            "--capture-track",
            "owner_local_modified",
            "--capture-id",
            "pair-001",
            "--mission-id",
            "Mission_Test",
            "--mission-slot",
            "Mission2",
            "--turn",
            "2",
            "--master-seed",
            "-17",
            "--region-id",
            "archive_a",
            "--ai-seed",
            "991",
            "--native-seed",
            str(NATIVE_SEED),
            "--timeline-fingerprint",
            "3" * 64,
            "--probe-kind",
            probe_kind,
            "--output-root",
            str(output_root),
        ]
    ) == 0
    output = capsys.readouterr().out
    plan_path = next(output_root.glob("*_pair_plan.json"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["kind"] == "observatory_rng_trial_pair_plan"
    assert plan["capture_track"] == "owner_local_modified"
    assert plan["capture_id"] == "pair-001"
    assert plan["probe_kind"] == probe_kind
    assert len(plan["activation_nonce"]) == 32
    assert plan["artifacts"]["arm_packet"]["sha256"] in output
    assert plan["artifacts"]["capsule"]["sha256"] in output
    assert plan["artifacts"]["seed_helper"]["sha256"] == hashlib.sha256(
        seed_helper.read_bytes()
    ).hexdigest()
    hook_plan_path = Path(plan["artifacts"]["hook_plan"]["path"])
    hook_plan = json.loads(hook_plan_path.read_text(encoding="utf-8"))["hook_plan"]
    installed = [entry for entry in hook_plan if entry["status"] == "installed"]
    assert [entry["event_kind"] for entry in installed] == [probe_kind]
    assert installed[0]["source_sha256"] == expected_source_sha
