#!/usr/bin/env python3
"""Build and arm the fixed one-shot Observatory RNG trial capsule."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.raw_trace import (  # noqa: E402
    arm_packet_sha256,
    build_arm_packet,
)
from src.observatory.rng_trial_capsule import (  # noqa: E402
    RNG_SEED_HELPER_VERSION,
    RngTrialCapsuleError,
    arm_rng_trial_request,
    build_rng_trial_capsule,
    render_rng_trial_capsule,
    render_rng_trial_request,
    rng_trial_capsule_sha256,
    write_rng_trial_capsule,
)
from src.observatory.rng_trial_result import (  # noqa: E402
    RngTrialResultError,
    compare_rng_trial_results,
)
from src.observatory.rng_trial_outcome import (  # noqa: E402
    RngTrialOutcomeError,
    compare_rng_trial_outcomes,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    build_identity_from_inventory,
    load_json_object,
    stable_file_sha256,
    write_arm_packet,
)
from src.observatory.trace_codec import (  # noqa: E402
    EVENT_KINDS,
    TraceConfig,
    hook_coverage_sha256,
    trace_config_sha256,
)


_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser(
        "build-capsule",
        help="render and immutably publish a data-only trial capsule",
    )
    build.add_argument("--arm", type=Path, required=True)
    build.add_argument("--arm-sha256", required=True)
    build.add_argument(
        "--capture-track",
        choices=("owner_local_modified", "pristine_reference"),
        required=True,
    )
    build.add_argument("--expected-mission-slot", required=True)
    build.add_argument("--expected-ai-seed", type=int, required=True)
    build.add_argument("--native-seed", type=int, required=True)
    build.add_argument("--seed-helper", type=Path, required=True)
    build.add_argument("--rng-seed-rva", required=True)
    build.add_argument("--rng-seed-region-sha256", required=True)
    build.add_argument(
        "--probe-kind",
        choices=("random_int", "random_bool"),
        default="random_int",
    )
    build.add_argument("--probe-upper-bound", type=int, default=65521)
    build.add_argument("--probe-argument", type=int, default=2)
    build.add_argument("--output-root", type=Path, required=True)

    arm = commands.add_parser(
        "arm-request",
        help="create the fixed startup request in one explicit bridge root",
    )
    arm.add_argument("--bridge-root", type=Path, required=True)
    arm.add_argument(
        "--condition",
        choices=("control", "exact_hook"),
        required=True,
    )
    arm.add_argument("--activation-nonce", required=True)
    arm.add_argument("--capsule-sha256", required=True)

    compare = commands.add_parser(
        "compare-results",
        help="strictly compare one control/exact-hook result pair",
    )
    compare.add_argument("--control", type=Path, required=True)
    compare.add_argument("--exact-hook", type=Path, required=True)
    compare.add_argument("--capsule-sha256", required=True)
    compare.add_argument("--arm-sha256", required=True)
    compare.add_argument("--output", type=Path)

    outcomes = commands.add_parser(
        "compare-outcomes",
        help="compare post-trial bridge states, ignoring only their timestamps",
    )
    outcomes.add_argument("--control", type=Path, required=True)
    outcomes.add_argument("--exact-hook", type=Path, required=True)
    outcomes.add_argument("--capture-id", required=True)
    outcomes.add_argument("--output", type=Path, required=True)

    prepare = commands.add_parser(
        "prepare-pair",
        help="build all immutable inputs for one control/exact-hook pair",
    )
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--controller-artifact", type=Path, required=True)
    prepare.add_argument("--installed-modloader", type=Path, required=True)
    prepare.add_argument("--trial-host", type=Path, required=True)
    prepare.add_argument("--seed-helper", type=Path, required=True)
    prepare.add_argument("--native-boundaries", type=Path, required=True)
    prepare.add_argument("--callback-join", type=Path, required=True)
    prepare.add_argument(
        "--capture-track",
        choices=("owner_local_modified", "pristine_reference"),
        required=True,
    )
    prepare.add_argument("--capture-id", required=True)
    prepare.add_argument("--mission-id", required=True)
    prepare.add_argument("--mission-slot", required=True)
    prepare.add_argument("--turn", type=int, required=True)
    prepare.add_argument("--master-seed", type=int, required=True)
    prepare.add_argument("--region-id", required=True)
    prepare.add_argument("--ai-seed", type=int, required=True)
    prepare.add_argument("--native-seed", type=int, required=True)
    prepare.add_argument("--timeline-fingerprint", required=True)
    prepare.add_argument(
        "--probe-kind",
        choices=("random_int", "random_bool"),
        default="random_int",
    )
    prepare.add_argument("--probe-upper-bound", type=int, default=65521)
    prepare.add_argument("--probe-argument", type=int, default=2)
    prepare.add_argument("--window-seconds", type=int, default=10 * 60)
    prepare.add_argument("--output-root", type=Path, required=True)
    return parser


def _build_capsule(args: argparse.Namespace) -> int:
    if stable_file_sha256(args.arm) != args.arm_sha256:
        raise RngTrialCapsuleError("arm file does not match --arm-sha256")
    packet = load_json_object(args.arm, "arm packet")
    if arm_packet_sha256(packet) != args.arm_sha256:
        raise RngTrialCapsuleError("arm packet is not canonical")
    capsule = build_rng_trial_capsule(
        packet,
        capture_track=args.capture_track,
        expected_mission_slot=args.expected_mission_slot,
        expected_ai_seed=args.expected_ai_seed,
        native_seed=args.native_seed,
        seed_helper_sha256=stable_file_sha256(args.seed_helper),
        rng_seed_rva=args.rng_seed_rva,
        rng_seed_region_sha256=args.rng_seed_region_sha256,
        probe_kind=args.probe_kind,
        probe_upper_bound=args.probe_upper_bound,
        probe_argument=args.probe_argument,
    )
    rendered = render_rng_trial_capsule(capsule)
    path = write_rng_trial_capsule(rendered, root=args.output_root)
    print(f"capsule={path} sha256={rng_trial_capsule_sha256(rendered)}")
    return 0


def _arm_request(args: argparse.Namespace) -> int:
    payload = render_rng_trial_request(
        condition=args.condition,
        activation_nonce=args.activation_nonce,
        capsule_sha256=args.capsule_sha256,
    )
    path = arm_rng_trial_request(
        bridge_root=args.bridge_root,
        condition=args.condition,
        activation_nonce=args.activation_nonce,
        capsule_sha256=args.capsule_sha256,
    )
    print(
        f"request={path} sha256={hashlib.sha256(payload).hexdigest()} "
        f"condition={args.condition}"
    )
    return 0


def _compare_results(args: argparse.Namespace) -> int:
    comparison = compare_rng_trial_results(
        load_json_object(args.control, "control result"),
        load_json_object(args.exact_hook, "exact-hook result"),
        expected_capsule_sha256=args.capsule_sha256,
        expected_arm_packet_sha256=args.arm_sha256,
    )
    if args.output is None:
        print(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _write_create_only_json(args.output, comparison)
        print(
            f"comparison={args.output} "
            f"sha256={stable_file_sha256(args.output)} status=matched"
        )
    return 0


def _compare_outcomes(args: argparse.Namespace) -> int:
    comparison = compare_rng_trial_outcomes(
        load_json_object(args.control, "control bridge outcome"),
        load_json_object(args.exact_hook, "exact-hook bridge outcome"),
        capture_id=args.capture_id,
    )
    _write_create_only_json(args.output, comparison)
    print(
        f"outcome_comparison={args.output} "
        f"sha256={stable_file_sha256(args.output)} "
        f"status={comparison['status']}"
    )
    return 0 if comparison["status"] == "matched" else 3


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write_create_only_json(path: Path, value: object) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RngTrialCapsuleError(f"immutable output already exists: {path.name}") from exc
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _region_sha256(boundaries: dict, region_id: str) -> str:
    matches = [
        entry
        for entry in boundaries.get("regions", [])
        if isinstance(entry, dict) and entry.get("id") == region_id
    ]
    if len(matches) != 1:
        raise RngTrialCapsuleError(f"boundary region {region_id} is not unique")
    digest = matches[0].get("sha256")
    if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
        raise RngTrialCapsuleError(f"boundary region {region_id} lacks SHA-256")
    return digest


def _region(boundaries: dict, region_id: str) -> dict:
    matches = [
        entry
        for entry in boundaries.get("regions", [])
        if isinstance(entry, dict) and entry.get("id") == region_id
    ]
    if len(matches) != 1:
        raise RngTrialCapsuleError(f"boundary region {region_id} is not unique")
    return matches[0]


def _require_callback_join(callback_join: dict, build_identity: dict) -> None:
    if (
        callback_join.get("schema_version") != 1
        or callback_join.get("analysis_kind") != "runtime_callback_identity_join"
    ):
        raise RngTrialCapsuleError("callback join contract is invalid")
    join_identity = callback_join.get("build_identity")
    if not isinstance(join_identity, dict) or any(
        join_identity.get(field) != build_identity.get(field)
        for field in (
            "platform",
            "architecture",
            "executable_sha256",
            "build_id",
            "depot_manifest",
            "scripts_revision_sha256",
            "maps_revision_sha256",
        )
    ):
        raise RngTrialCapsuleError("callback join does not match the inventory")
    summary = callback_join.get("summary")
    counts = summary.get("join_status_counts") if isinstance(summary, dict) else None
    function_count = summary.get("function_count") if isinstance(summary, dict) else None
    if (
        type(function_count) is not int
        or function_count < 1
        or not isinstance(counts, dict)
        or counts.get("matched") != function_count
        or any(value != 0 for key, value in counts.items() if key != "matched")
    ):
        raise RngTrialCapsuleError("callback join is not complete and exact")


def _hook_plan(
    *,
    boundaries: dict,
    boundaries_sha256: str,
    callback_join_sha256: str,
    probe_kind: str,
) -> list[dict]:
    random_int_sha = _region_sha256(boundaries, "random_int_1")
    random_bool_sha = _region_sha256(boundaries, "random_bool_1")
    callback_kinds = {
        "enemy_target_score",
        "get_skill_effect",
        "get_target_area",
        "score_positioning",
    }
    native_kinds = {"enemy_action_selected", "enemy_candidate"}
    plan = []
    for kind in sorted(EVENT_KINDS):
        if kind == "random_int":
            target = "_G.random_int"
            target_kind = "lua_global"
            source_sha = random_int_sha
            status = "installed" if probe_kind == kind else "disabled"
        elif kind == "random_bool":
            target = "_G.random_bool"
            target_kind = "lua_global"
            source_sha = random_bool_sha
            status = "installed" if probe_kind == kind else "disabled"
        elif kind in callback_kinds:
            target = f"catalog.callback.{kind}"
            target_kind = "lua_method"
            source_sha = callback_join_sha256
            status = "disabled"
        elif kind in native_kinds:
            target = f"catalog.native.{kind}"
            target_kind = "native_boundary"
            source_sha = boundaries_sha256
            status = "disabled"
        else:
            raise RngTrialCapsuleError(f"unclassified event family: {kind}")
        plan.append(
            {
                "hook_id": f"rng_trial.{kind}",
                "event_kind": kind,
                "target": target,
                "target_kind": target_kind,
                "status": status,
                "source_sha256": source_sha,
            }
        )
    return plan


def _prepare_pair(args: argparse.Namespace) -> int:
    if _CAPTURE_ID_RE.fullmatch(args.capture_id) is None:
        raise RngTrialCapsuleError("capture ID is invalid")
    if _SHA256_RE.fullmatch(args.timeline_fingerprint or "") is None:
        raise RngTrialCapsuleError("timeline fingerprint must be lowercase SHA-256")
    if not 1 <= args.window_seconds <= 15 * 60:
        raise RngTrialCapsuleError("capture window must be 1 to 900 seconds")
    inventory = load_json_object(args.inventory, "inventory")
    build_identity = build_identity_from_inventory(inventory)
    boundaries = load_json_object(args.native_boundaries, "native boundaries")
    if (
        boundaries.get("schema_version") != 1
        or boundaries.get("analysis_kind") != "pe_reviewed_boundary_map"
    ):
        raise RngTrialCapsuleError("native boundary contract is invalid")
    boundary_identity = boundaries.get("identity")
    if not isinstance(boundary_identity, dict) or any(
        boundary_identity.get(field) != build_identity.get(field)
        for field in (
            "platform",
            "architecture",
            "executable_sha256",
            "build_id",
            "scripts_revision_sha256",
            "maps_revision_sha256",
        )
    ):
        raise RngTrialCapsuleError("native boundaries do not match the inventory")
    controller_sha = stable_file_sha256(args.controller_artifact)
    modloader_sha = stable_file_sha256(args.installed_modloader)
    host_sha = stable_file_sha256(args.trial_host)
    seed_helper_sha = stable_file_sha256(args.seed_helper)
    boundaries_sha = stable_file_sha256(args.native_boundaries)
    callback_join = load_json_object(args.callback_join, "callback join")
    _require_callback_join(callback_join, build_identity)
    callback_join_sha = stable_file_sha256(args.callback_join)
    seed_region = _region(boundaries, "rng_seed")
    if (
        seed_region.get("start_rva") != "0x00387f37"
        or seed_region.get("sha256") != _region_sha256(boundaries, "rng_seed")
    ):
        raise RngTrialCapsuleError("native seed boundary is invalid")
    hook_plan = _hook_plan(
        boundaries=boundaries,
        boundaries_sha256=boundaries_sha,
        callback_join_sha256=callback_join_sha,
        probe_kind=args.probe_kind,
    )
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in hook_plan
    ]
    config = TraceConfig(
        enabled=True,
        allowed_phases=("combat_enemy",),
        max_events=8,
        max_events_per_turn=8,
        max_event_bytes=4096,
        max_total_event_bytes=64 * 1024,
        max_bundle_bytes=3 * 1024 * 1024,
    )
    activated = datetime.now(timezone.utc).replace(microsecond=0)
    expires = activated + timedelta(seconds=args.window_seconds)
    ai_seed_fingerprint = _canonical_sha256(
        {
            "ai_seed": args.ai_seed,
            "mission_id": args.mission_id,
            "region_id": args.region_id,
            "turn": args.turn,
        }
    )
    capture_identity = {
        "capture_id": args.capture_id,
        "arm_nonce": secrets.token_hex(16),
        "controller_version": "observatory-controller/1",
        "controller_sha256": controller_sha,
        "installed_modloader_sha256": modloader_sha,
        "expected_mission_id": args.mission_id,
        "expected_turn": args.turn,
        "timeline_fingerprint": args.timeline_fingerprint,
        "master_seed": args.master_seed,
        "region_id": args.region_id,
        "ai_seed_fingerprint": ai_seed_fingerprint,
        "expected_phase": "combat_enemy",
        "config_sha256": trace_config_sha256(config),
        "hook_coverage_sha256": hook_coverage_sha256(coverage),
        "activated_at_utc": activated.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": expires.isoformat().replace("+00:00", "Z"),
    }
    packet = build_arm_packet(
        build_identity=build_identity,
        capture_identity=capture_identity,
        config=config.to_dict(),
        hook_plan=hook_plan,
        max_attempts=8,
        checkpoint_seq=0,
    )
    root = Path(os.path.abspath(args.output_root.expanduser()))
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"itb_observatory_rng_{args.capture_id}"
    config_path = root / f"{prefix}_config.json"
    hook_plan_path = root / f"{prefix}_hook_plan.json"
    capture_path = root / f"{prefix}_capture_identity.json"
    _write_create_only_json(config_path, config.to_dict())
    _write_create_only_json(hook_plan_path, {"hook_plan": hook_plan})
    _write_create_only_json(capture_path, capture_identity)
    arm_path = write_arm_packet(packet, root=root)
    capsule = build_rng_trial_capsule(
        packet,
        capture_track=args.capture_track,
        expected_mission_slot=args.mission_slot,
        expected_ai_seed=args.ai_seed,
        native_seed=args.native_seed,
        seed_helper_sha256=seed_helper_sha,
        rng_seed_rva=seed_region["start_rva"],
        rng_seed_region_sha256=seed_region["sha256"],
        probe_kind=args.probe_kind,
        probe_upper_bound=args.probe_upper_bound,
        probe_argument=args.probe_argument,
    )
    rendered_capsule = render_rng_trial_capsule(capsule)
    capsule_path = write_rng_trial_capsule(rendered_capsule, root=root)
    plan = {
        "schema_version": 1,
        "kind": "observatory_rng_trial_pair_plan",
        "capture_track": args.capture_track,
        "capture_id": args.capture_id,
        "probe_kind": args.probe_kind,
        "activation_nonce": capture_identity["arm_nonce"],
        "artifacts": {
            "inventory": {
                "path": str(args.inventory.resolve()),
                "sha256": stable_file_sha256(args.inventory),
            },
            "controller": {
                "path": str(args.controller_artifact.resolve()),
                "sha256": controller_sha,
            },
            "installed_modloader": {
                "path": str(args.installed_modloader.resolve()),
                "sha256": modloader_sha,
            },
            "trial_host": {
                "path": str(args.trial_host.resolve()),
                "sha256": host_sha,
            },
            "seed_helper": {
                "path": str(args.seed_helper.resolve()),
                "sha256": seed_helper_sha,
                "version": RNG_SEED_HELPER_VERSION,
            },
            "native_boundaries": {
                "path": str(args.native_boundaries.resolve()),
                "sha256": boundaries_sha,
            },
            "callback_join": {
                "path": str(args.callback_join.resolve()),
                "sha256": callback_join_sha,
            },
            "config": {
                "path": str(config_path),
                "sha256": stable_file_sha256(config_path),
            },
            "hook_plan": {
                "path": str(hook_plan_path),
                "sha256": stable_file_sha256(hook_plan_path),
            },
            "capture_identity": {
                "path": str(capture_path),
                "sha256": stable_file_sha256(capture_path),
            },
            "arm_packet": {
                "path": str(arm_path),
                "sha256": arm_packet_sha256(packet),
            },
            "capsule": {
                "path": str(capsule_path),
                "sha256": rng_trial_capsule_sha256(rendered_capsule),
            },
        },
    }
    plan_path = root / f"{prefix}_pair_plan.json"
    _write_create_only_json(plan_path, plan)
    print(
        f"plan={plan_path} capture={args.capture_id} "
        f"arm_sha256={arm_packet_sha256(packet)} "
        f"capsule_sha256={rng_trial_capsule_sha256(rendered_capsule)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build-capsule":
            return _build_capsule(args)
        if args.command == "arm-request":
            return _arm_request(args)
        if args.command == "compare-results":
            return _compare_results(args)
        if args.command == "compare-outcomes":
            return _compare_outcomes(args)
        return _prepare_pair(args)
    except (
        RngTrialCapsuleError,
        RngTrialResultError,
        RngTrialOutcomeError,
        TraceStoreError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
