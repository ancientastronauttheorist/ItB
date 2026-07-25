#!/usr/bin/env python3
"""Build, finalize, validate, and summarize Observatory evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.raw_trace import (  # noqa: E402
    RawTraceError,
    arm_packet_sha256,
    build_arm_packet,
    finalize_raw_checkpoint,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    build_identity_from_inventory,
    load_json_object,
    read_arm_packet,
    read_final_trace,
    read_raw_checkpoint,
    stable_file_sha256,
    summarize_trace,
    write_arm_packet,
    write_final_trace,
)


def _trusted_inputs(child: argparse.ArgumentParser) -> None:
    child.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="trusted content-inventory JSON",
    )
    child.add_argument(
        "--capture-identity",
        type=Path,
        required=True,
        help="trusted capture_identity JSON object",
    )


def _artifact_inputs(child: argparse.ArgumentParser) -> None:
    child.add_argument(
        "--controller-artifact",
        type=Path,
        required=True,
        help="exact controller/runtime bundle named by controller_sha256",
    )
    child.add_argument(
        "--installed-modloader",
        type=Path,
        required=True,
        help="exact deployed Mod Loader file named by its capture hash",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Operate the fail-closed Engine Observatory evidence boundary."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "summary"):
        child = subparsers.add_parser(command)
        child.add_argument("trace", type=Path)
        _trusted_inputs(child)
        child.add_argument(
            "--trace-sha256",
            required=True,
            help="trusted SHA-256 of the finalized trace bytes",
        )

    build = subparsers.add_parser(
        "build-arm",
        help="build and immutably publish an inert arm packet",
    )
    _trusted_inputs(build)
    _artifact_inputs(build)
    build.add_argument("--config", type=Path, required=True)
    build.add_argument(
        "--hook-plan",
        type=Path,
        required=True,
        help='strict JSON object containing only {"hook_plan": [...]}',
    )
    build.add_argument("--max-attempts", type=int, required=True)
    build.add_argument("--checkpoint-seq", type=int, required=True)
    build.add_argument("--output-root", type=Path, required=True)

    finalize = subparsers.add_parser(
        "finalize-raw",
        help="validate one exact raw checkpoint and publish schema-v2 evidence",
    )
    finalize.add_argument("raw", type=Path)
    _trusted_inputs(finalize)
    _artifact_inputs(finalize)
    finalize.add_argument("--arm", type=Path, required=True)
    finalize.add_argument("--arm-root", type=Path, required=True)
    finalize.add_argument("--arm-sha256", required=True)
    finalize.add_argument("--raw-root", type=Path, required=True)
    finalize.add_argument("--raw-sha256", required=True)
    finalize.add_argument("--checkpoint-seq", type=int, required=True)
    finalize.add_argument("--output-root", type=Path, required=True)
    return parser


def _load_trusted(args: argparse.Namespace) -> tuple[dict, dict]:
    inventory = load_json_object(args.inventory, "inventory")
    return (
        build_identity_from_inventory(inventory),
        load_json_object(args.capture_identity, "capture identity"),
    )


def _verify_artifacts(
    args: argparse.Namespace,
    capture: dict,
) -> None:
    controller_sha = stable_file_sha256(args.controller_artifact)
    if controller_sha != capture.get("controller_sha256"):
        raise TraceStoreError(
            "controller artifact does not match capture identity"
        )
    modloader_sha = stable_file_sha256(args.installed_modloader)
    if modloader_sha != capture.get("installed_modloader_sha256"):
        raise TraceStoreError(
            "installed Mod Loader does not match capture identity"
        )


def _validate_or_summarize(args: argparse.Namespace) -> int:
    expected_build, expected_capture = _load_trusted(args)
    trace_path = Path(os.path.abspath(args.trace.expanduser()))
    trace = read_final_trace(
        trace_path,
        expected_build_identity=expected_build,
        expected_capture_identity=expected_capture,
        expected_trace_sha256=args.trace_sha256,
        root=trace_path.parent,
    )
    if args.command == "validate":
        print(
            "valid "
            f"capture={trace['capture_identity']['capture_id']} "
            f"checkpoint={trace['checkpoint']['seq']} "
            f"events={len(trace['events'])}"
        )
    else:
        print(
            json.dumps(
                summarize_trace(trace),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return 0


def _build_arm(args: argparse.Namespace) -> int:
    build, capture = _load_trusted(args)
    _verify_artifacts(args, capture)
    config = load_json_object(args.config, "trace config")
    hook_wrapper = load_json_object(args.hook_plan, "hook plan")
    if set(hook_wrapper) != {"hook_plan"}:
        raise TraceStoreError(
            "hook plan file must contain exactly the hook_plan field"
        )
    packet = build_arm_packet(
        build_identity=build,
        capture_identity=capture,
        config=config,
        hook_plan=hook_wrapper["hook_plan"],
        max_attempts=args.max_attempts,
        checkpoint_seq=args.checkpoint_seq,
    )
    path = write_arm_packet(packet, root=args.output_root)
    print(f"arm={path} sha256={arm_packet_sha256(packet)}")
    return 0


def _finalize_raw(args: argparse.Namespace) -> int:
    build, capture = _load_trusted(args)
    _verify_artifacts(args, capture)
    packet = read_arm_packet(
        args.arm,
        expected_capture_id=capture["capture_id"],
        expected_checkpoint_seq=args.checkpoint_seq,
        expected_arm_sha256=args.arm_sha256,
        root=args.arm_root,
    )
    raw = read_raw_checkpoint(
        args.raw,
        expected_capture_id=capture["capture_id"],
        expected_checkpoint_seq=args.checkpoint_seq,
        expected_raw_sha256=args.raw_sha256,
        root=args.raw_root,
        max_bytes=min(
            packet["policy"]["max_bundle_bytes"],
            64 * 1024 * 1024,
        ),
    )
    trace = finalize_raw_checkpoint(
        raw,
        build_identity=build,
        capture_identity=capture,
        arm_packet=packet,
        expected_arm_packet_sha256=args.arm_sha256,
    )
    path = write_final_trace(trace, root=args.output_root)
    digest = stable_file_sha256(path)
    print(
        f"final={path} sha256={digest} "
        f"events={len(trace['events'])}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in {"validate", "summary"}:
            return _validate_or_summarize(args)
        if args.command == "build-arm":
            return _build_arm(args)
        return _finalize_raw(args)
    except (TraceStoreError, RawTraceError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
