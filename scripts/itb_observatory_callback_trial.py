#!/usr/bin/env python3
"""Prepare, arm, and compare exact one-family callback trials."""

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

from src.observatory.callback_hook_plan import (  # noqa: E402
    CALLBACK_KINDS,
    build_callback_hook_plan,
)
from src.observatory.callback_trial_capsule import (  # noqa: E402
    CallbackTrialCapsuleError,
    arm_callback_trial_request,
    build_callback_trial_capsule,
    callback_trial_capsule_sha256,
    render_callback_trial_capsule,
    render_callback_trial_request,
    write_callback_trial_capsule,
)
from src.observatory.callback_trial_result import (  # noqa: E402
    CallbackTrialResultError,
    compare_callback_trial_results,
)
from src.observatory.raw_trace import arm_packet_sha256, build_arm_packet  # noqa: E402
from src.observatory.trace_codec import (  # noqa: E402
    TraceConfig,
    hook_coverage_sha256,
    trace_config_sha256,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    build_identity_from_inventory,
    load_json_object,
    stable_file_sha256,
    write_arm_packet,
)


_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build-capsule")
    build.add_argument("--arm", type=Path, required=True)
    build.add_argument("--arm-sha256", required=True)
    build.add_argument("--bindings", type=Path, required=True)
    build.add_argument("--callback-join", type=Path, required=True)
    build.add_argument(
        "--capture-track",
        choices=("owner_local_modified", "pristine_reference"),
        required=True,
    )
    build.add_argument("--expected-mission-slot", required=True)
    build.add_argument("--expected-ai-seed", type=int, required=True)
    build.add_argument("--output-root", type=Path, required=True)

    arm = commands.add_parser("arm-request")
    arm.add_argument("--bridge-root", type=Path, required=True)
    arm.add_argument("--condition", choices=("control", "exact_hook"), required=True)
    arm.add_argument("--activation-nonce", required=True)
    arm.add_argument("--capsule-sha256", required=True)

    compare = commands.add_parser("compare-results")
    compare.add_argument("--control", type=Path, required=True)
    compare.add_argument("--exact-hook", type=Path, required=True)
    compare.add_argument("--capsule-sha256", required=True)
    compare.add_argument("--arm-sha256", required=True)
    compare.add_argument("--output", type=Path)

    prepare = commands.add_parser(
        "prepare-pair",
        help="build all immutable inputs for one control/exact-hook callback pair",
    )
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--controller-artifact", type=Path, required=True)
    prepare.add_argument("--installed-modloader", type=Path, required=True)
    prepare.add_argument("--trial-host", type=Path, required=True)
    prepare.add_argument("--bindings", type=Path, required=True)
    prepare.add_argument("--callback-join", type=Path, required=True)
    prepare.add_argument(
        "--capture-track",
        choices=("owner_local_modified", "pristine_reference"),
        required=True,
    )
    prepare.add_argument("--capture-id", required=True)
    prepare.add_argument("--callback-family", choices=sorted(CALLBACK_KINDS), required=True)
    prepare.add_argument("--mission-id", required=True)
    prepare.add_argument("--mission-slot", required=True)
    prepare.add_argument("--turn", type=int, required=True)
    prepare.add_argument("--master-seed", type=int, required=True)
    prepare.add_argument("--region-id", required=True)
    prepare.add_argument("--ai-seed", type=int, required=True)
    prepare.add_argument("--timeline-fingerprint", required=True)
    prepare.add_argument("--window-seconds", type=int, default=10 * 60)
    prepare.add_argument("--output-root", type=Path, required=True)
    return parser


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def _write_create_only_json(path: Path, value: object) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path = Path(os.path.abspath(path.expanduser()))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CallbackTrialCapsuleError(f"immutable output already exists: {path.name}") from exc
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _build_capsule(args: argparse.Namespace) -> int:
    if stable_file_sha256(args.arm) != args.arm_sha256:
        raise CallbackTrialCapsuleError("arm file does not match --arm-sha256")
    packet = load_json_object(args.arm, "arm packet")
    if arm_packet_sha256(packet) != args.arm_sha256:
        raise CallbackTrialCapsuleError("arm packet is not canonical")
    capsule = build_callback_trial_capsule(
        packet,
        load_json_object(args.bindings, "callback bindings"),
        load_json_object(args.callback_join, "callback join"),
        capture_track=args.capture_track,
        expected_mission_slot=args.expected_mission_slot,
        expected_ai_seed=args.expected_ai_seed,
    )
    rendered = render_callback_trial_capsule(capsule)
    path = write_callback_trial_capsule(rendered, root=args.output_root)
    print(f"capsule={path} sha256={callback_trial_capsule_sha256(rendered)}")
    return 0


def _arm(args: argparse.Namespace) -> int:
    payload = render_callback_trial_request(
        condition=args.condition,
        activation_nonce=args.activation_nonce,
        capsule_sha256=args.capsule_sha256,
    )
    path = arm_callback_trial_request(
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


def _compare(args: argparse.Namespace) -> int:
    comparison = compare_callback_trial_results(
        load_json_object(args.control, "control callback result"),
        load_json_object(args.exact_hook, "exact-hook callback result"),
        expected_capsule_sha256=args.capsule_sha256,
        expected_arm_packet_sha256=args.arm_sha256,
    )
    if args.output is None:
        print(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _write_create_only_json(args.output, comparison)
        print(
            f"comparison={args.output} sha256={stable_file_sha256(args.output)} "
            "status=matched"
        )
    return 0


def _prepare(args: argparse.Namespace) -> int:
    if _CAPTURE_ID_RE.fullmatch(args.capture_id or "") is None:
        raise CallbackTrialCapsuleError("capture ID is invalid")
    if _SHA256_RE.fullmatch(args.timeline_fingerprint or "") is None:
        raise CallbackTrialCapsuleError("timeline fingerprint must be lowercase SHA-256")
    if not 1 <= args.window_seconds <= 15 * 60:
        raise CallbackTrialCapsuleError("capture window must be 1 to 900 seconds")

    inventory = load_json_object(args.inventory, "inventory")
    build_identity = build_identity_from_inventory(inventory)
    bindings = load_json_object(args.bindings, "callback bindings")
    callback_join = load_json_object(args.callback_join, "callback join")
    hook_plan = build_callback_hook_plan(
        bindings,
        callback_join,
        installed_kind=args.callback_family,
    )
    coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in hook_plan
    ]
    config = TraceConfig(
        enabled=True,
        allowed_phases=("combat_enemy",),
        max_events=1024,
        max_events_per_turn=1024,
        max_event_bytes=64 * 1024,
        max_total_event_bytes=4 * 1024 * 1024,
        max_bundle_bytes=8 * 1024 * 1024,
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
    controller_sha = stable_file_sha256(args.controller_artifact)
    modloader_sha = stable_file_sha256(args.installed_modloader)
    capture_identity = {
        "capture_id": args.capture_id,
        "arm_nonce": secrets.token_hex(16),
        "controller_version": "observatory-callback-controller/1",
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
        max_attempts=4096,
        checkpoint_seq=0,
    )
    root = Path(os.path.abspath(args.output_root.expanduser()))
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"itb_observatory_callback_{args.capture_id}"
    config_path = root / f"{prefix}_config.json"
    hook_path = root / f"{prefix}_hook_plan.json"
    capture_path = root / f"{prefix}_capture_identity.json"
    _write_create_only_json(config_path, config.to_dict())
    _write_create_only_json(hook_path, {"hook_plan": hook_plan})
    _write_create_only_json(capture_path, capture_identity)
    arm_path = write_arm_packet(packet, root=root)
    capsule = build_callback_trial_capsule(
        packet,
        bindings,
        callback_join,
        capture_track=args.capture_track,
        expected_mission_slot=args.mission_slot,
        expected_ai_seed=args.ai_seed,
    )
    rendered = render_callback_trial_capsule(capsule)
    capsule_path = write_callback_trial_capsule(rendered, root=root)
    pair_plan = {
        "schema_version": 1,
        "kind": "observatory_callback_trial_pair_plan",
        "capture_track": args.capture_track,
        "capture_id": args.capture_id,
        "callback_family": args.callback_family,
        "activation_nonce": capture_identity["arm_nonce"],
        "conditions": ["control", "exact_hook"],
        "artifacts": {
            "inventory": {"path": str(args.inventory.resolve()), "sha256": stable_file_sha256(args.inventory)},
            "controller": {"path": str(args.controller_artifact.resolve()), "sha256": controller_sha},
            "installed_modloader": {"path": str(args.installed_modloader.resolve()), "sha256": modloader_sha},
            "trial_host": {"path": str(args.trial_host.resolve()), "sha256": stable_file_sha256(args.trial_host)},
            "bindings": {"path": str(args.bindings.resolve()), "sha256": stable_file_sha256(args.bindings)},
            "callback_join": {"path": str(args.callback_join.resolve()), "sha256": stable_file_sha256(args.callback_join)},
            "callback_join_document_sha256": _canonical_sha256(callback_join),
            "config": {"path": str(config_path), "sha256": stable_file_sha256(config_path)},
            "hook_plan": {"path": str(hook_path), "sha256": stable_file_sha256(hook_path)},
            "capture_identity": {"path": str(capture_path), "sha256": stable_file_sha256(capture_path)},
            "arm_packet": {"path": str(arm_path), "sha256": arm_packet_sha256(packet)},
            "capsule": {"path": str(capsule_path), "sha256": callback_trial_capsule_sha256(rendered)},
        },
    }
    plan_path = root / f"{prefix}_pair_plan.json"
    _write_create_only_json(plan_path, pair_plan)
    print(
        f"plan={plan_path} arm_sha256={arm_packet_sha256(packet)} "
        f"capsule_sha256={callback_trial_capsule_sha256(rendered)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build-capsule":
            return _build_capsule(args)
        if args.command == "arm-request":
            return _arm(args)
        if args.command == "compare-results":
            return _compare(args)
        return _prepare(args)
    except (
        CallbackTrialCapsuleError,
        CallbackTrialResultError,
        TraceStoreError,
        KeyError,
        TypeError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
