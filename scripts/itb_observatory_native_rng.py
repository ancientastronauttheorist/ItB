#!/usr/bin/env python3
"""Operate and seal the fixed build-keyed native RNG-core observer."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bridge.protocol import BridgeError  # noqa: E402
from src.bridge.writer import (  # noqa: E402
    bridge_observatory_native_rng_arm,
    bridge_observatory_native_rng_finish,
    bridge_observatory_native_rng_seed,
    bridge_observatory_native_rng_status,
)
from src.observatory.native_checkpoint import (  # noqa: E402
    NativeCheckpointError,
    build_rng_core_checkpoint,
    validate_native_checkpoint,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    arm = commands.add_parser("arm", help="arm the one-shot observer")
    arm.add_argument("--capture-id", required=True)

    commands.add_parser(
        "seed",
        help="apply the fixed seed after all player actors are spent",
    )

    commands.add_parser("status", help="read the observer status")

    finish = commands.add_parser(
        "finish",
        help="restore the hook and seal one fully bound diagnostic checkpoint",
    )
    finish.add_argument("--capture-id", required=True)
    finish.add_argument("--build-receipt", type=Path, required=True)
    finish.add_argument("--module", type=Path, required=True)
    finish.add_argument("--rng-return-map", type=Path, required=True)
    finish.add_argument("--restore-hashes", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    return parser


def _stable_json(path: Path, label: str) -> dict:
    return load_json_object(Path(path), label)


def _write_create_only(path: Path, value: object) -> None:
    output = Path(os.path.abspath(path.expanduser()))
    if output.parent == output or output.parent.is_symlink():
        raise OSError("checkpoint output parent is unsafe")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    with output.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _arm(args: argparse.Namespace) -> int:
    ack = bridge_observatory_native_rng_arm(args.capture_id)
    print(
        json.dumps(
            {"status": "armed", "capture_id": args.capture_id, "ack": ack},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _status() -> int:
    ack, status = bridge_observatory_native_rng_status()
    print(json.dumps({"ack": ack, "observer": status}, indent=2, sort_keys=True))
    return 0


def _seed() -> int:
    ack = bridge_observatory_native_rng_seed()
    print(json.dumps({"status": "seeded", "ack": ack}, indent=2, sort_keys=True))
    return 0


def _finish(args: argparse.Namespace) -> int:
    # Complete every local trust check that does not require the runtime
    # snapshot before asking the game to remove the hook. This avoids learning
    # after arming that a caller supplied an unusable evidence destination.
    receipt = _stable_json(args.build_receipt, "observer build receipt")
    return_map = _stable_json(args.rng_return_map, "RNG return map")
    restore_hashes = _stable_json(args.restore_hashes, "restore hashes")
    module_sha256 = stable_file_sha256(args.module)
    output = Path(os.path.abspath(args.output.expanduser()))
    if output.exists() or output.is_symlink():
        raise OSError(f"checkpoint output already exists: {output}")

    ack, snapshot = bridge_observatory_native_rng_finish(args.capture_id)
    checkpoint = build_rng_core_checkpoint(
        snapshot,
        build_receipt=receipt,
        observed_module_sha256=module_sha256,
    )
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=checkpoint["identity"],
        return_map=return_map,
        expected_restore_hashes=restore_hashes,
    )
    if not verification["diagnostic_complete"]:
        raise NativeCheckpointError(
            "native RNG checkpoint did not satisfy complete diagnostic proof"
        )
    _write_create_only(output, checkpoint)
    print(
        json.dumps(
            {
                "status": "complete",
                "capture_id": args.capture_id,
                "ack": ack,
                "checkpoint": str(output),
                "checkpoint_sha256": stable_file_sha256(output),
                "record_count": checkpoint["summary"]["record_count"],
                "hook_bytes_restored": checkpoint["integrity"][
                    "hook_bytes_restored"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "arm":
            return _arm(args)
        if args.command == "status":
            return _status()
        if args.command == "seed":
            return _seed()
        return _finish(args)
    except (
        BridgeError,
        NativeCheckpointError,
        TraceStoreError,
        TimeoutError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
