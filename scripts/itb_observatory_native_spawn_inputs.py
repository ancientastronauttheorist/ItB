#!/usr/bin/env python3
"""Capture exact native-only enemy-spawn inputs from a live Windows Board."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.native_spawn_input_reader import (  # noqa: E402
    NativeSpawnInputReaderError,
    capture_live_native_spawn_inputs,
    combine_current_bridge_native_capture,
    validate_current_bridge_native_capture_artifact,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read the pinned Windows build's BlockSpawn map and direct "
            "spawn-marker vector without modifying the game process."
        )
    )
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--verify",
        type=Path,
        help="verify one saved combined capture without touching the game",
    )
    parser.add_argument(
        "--with-bridge-replay",
        action="store_true",
        help=(
            "sandwich the native read between two fresh bridge snapshots "
            "and emit the exact current candidate-pool replay"
        ),
    )
    return parser


def _write_create_only(path: Path, encoded: str) -> None:
    resolved = path.resolve()
    recordings = (ROOT / "recordings").resolve()
    if os.path.commonpath((str(resolved), str(recordings))) != str(recordings):
        raise NativeSpawnInputReaderError("output must be below recordings/")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        with resolved.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    except FileExistsError as exc:
        raise NativeSpawnInputReaderError("output already exists") from exc


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.verify is not None:
            if args.pid is not None or args.output is not None or args.with_bridge_replay:
                raise NativeSpawnInputReaderError(
                    "--verify cannot be combined with live-capture options"
                )
            verify_path = args.verify.resolve()
            if verify_path.is_symlink() or not verify_path.is_file():
                raise NativeSpawnInputReaderError(
                    "combined capture is not a regular file"
                )
            try:
                raw = verify_path.read_bytes()
                artifact = json.loads(raw)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise NativeSpawnInputReaderError(
                    f"could not read combined capture: {exc}"
                ) from exc
            validated = validate_current_bridge_native_capture_artifact(artifact)
            sys.stdout.write(
                json.dumps(
                    {
                        "status": "verified",
                        "analysis_kind": validated["analysis_kind"],
                        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                        "candidate_count": validated["candidate_replay"][
                            "candidate_count"
                        ],
                        "future_forecast": validated["future_forecast"],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            return 0
        if args.with_bridge_replay:
            from src.bridge.protocol import (
                is_bridge_alive,
                read_state,
                refresh_bridge_state_fresh,
            )

            if not is_bridge_alive(max_stale_sec=5.0):
                raise NativeSpawnInputReaderError(
                    "bridge replay requires an unpaused active mission heartbeat"
                )
            if refresh_bridge_state_fresh() is not True:
                raise NativeSpawnInputReaderError(
                    "could not refresh bridge state before native capture"
                )
            bridge_before = read_state()
            if bridge_before is None:
                raise NativeSpawnInputReaderError(
                    "bridge state is unavailable before native capture"
                )
            native_capture = capture_live_native_spawn_inputs(args.pid)
            if refresh_bridge_state_fresh() is not True:
                raise NativeSpawnInputReaderError(
                    "could not refresh bridge state after native capture"
                )
            bridge_after = read_state()
            if bridge_after is None:
                raise NativeSpawnInputReaderError(
                    "bridge state is unavailable after native capture"
                )
            result = combine_current_bridge_native_capture(
                bridge_before,
                native_capture,
                bridge_after,
            )
        else:
            result = capture_live_native_spawn_inputs(args.pid)
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            sys.stdout.write(encoded)
        else:
            _write_create_only(args.output, encoded)
            native_result = result.get("native_input_capture", result)
            replay = result.get("candidate_replay")
            sys.stdout.write(
                json.dumps(
                    {
                        "status": "captured",
                        "analysis_kind": result["analysis_kind"],
                        "output": str(args.output.resolve()),
                        "nonzero_block_spawn_count": len(
                            native_result["nonzero_block_spawn_values"]
                        ),
                        "spawn_marker_count": len(
                            native_result["existing_spawn_marker_vector"]
                        ),
                        "candidate_count": (
                            replay.get("candidate_count")
                            if isinstance(replay, dict)
                            else None
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        return 0
    except NativeSpawnInputReaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
