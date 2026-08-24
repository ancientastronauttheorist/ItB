#!/usr/bin/env python3
"""Arm, finish, validate, and archive ScorePositioning x87 observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bridge.protocol import (
    BridgeError,
    arm_observatory_score_positioning_x87,
    finish_observatory_score_positioning_x87,
    status_observatory_score_positioning_x87,
)
from src.observatory.score_positioning_x87 import (
    EXPECTED_MODULE_SHA256,
    ScorePositioningX87Error,
    analyze_score_positioning_x87_snapshot,
)


MODULE_PATH = ROOT / "data" / "observatory" / "native" / (
    "itb_observatory_score_positioning_x87_observer_"
    f"{EXPECTED_MODULE_SHA256}.dll"
)
RECEIPT_PATH = MODULE_PATH.with_suffix(".dll.receipt.json")


class ScorePositioningX87CliError(RuntimeError):
    """Raised when local evidence publication cannot be trusted."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("arm", "status"):
        child = subparsers.add_parser(command)
        child.add_argument("--capture-id", required=True)
    finish = subparsers.add_parser("finish")
    finish.add_argument("--capture-id", required=True)
    finish.add_argument("--output-root", type=Path)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--snapshot", type=Path, required=True)
    analyze.add_argument("--output", type=Path)
    parser.add_argument("--module", type=Path, default=MODULE_PATH)
    parser.add_argument("--receipt", type=Path, default=RECEIPT_PATH)
    return parser


def _stable_bytes(path: Path, label: str) -> bytes:
    path = Path(os.path.abspath(path.expanduser()))
    if path.is_symlink() or not path.is_file():
        raise ScorePositioningX87CliError(f"{label} is not a regular file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise ScorePositioningX87CliError(f"{label} changed while being read")
    return data


def _load_json(path: Path, label: str) -> dict[str, Any]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScorePositioningX87CliError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ScorePositioningX87CliError(f"{label} must be an object")
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _write_create_only(path: Path, data: bytes) -> None:
    path = Path(os.path.abspath(path.expanduser()))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ScorePositioningX87CliError(
            f"immutable evidence output already exists: {path}"
        ) from exc


def _validate_and_analyze(
    snapshot: dict[str, Any], module_path: Path, receipt_path: Path
) -> dict[str, Any]:
    module = _stable_bytes(module_path, "observer module")
    module_sha = hashlib.sha256(module).hexdigest()
    if module_sha != EXPECTED_MODULE_SHA256:
        raise ScorePositioningX87CliError("observer module digest differs")
    receipt = _load_json(receipt_path, "observer build receipt")
    return analyze_score_positioning_x87_snapshot(
        snapshot,
        build_receipt=receipt,
        observed_module_sha256=module_sha,
    )


def _archive(
    output_root: Path,
    capture_id: str,
    snapshot: dict[str, Any],
    analysis: dict[str, Any],
) -> tuple[Path, Path]:
    output_root = Path(os.path.abspath(output_root.expanduser()))
    snapshot_path = output_root / f"{capture_id}_snapshot.json"
    analysis_path = output_root / f"{capture_id}_analysis.json"
    _write_create_only(snapshot_path, _canonical_json(snapshot))
    _write_create_only(analysis_path, _canonical_json(analysis))
    return snapshot_path, analysis_path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "arm":
            print(arm_observatory_score_positioning_x87(args.capture_id))
            return 0
        if args.command == "status":
            ack, status = status_observatory_score_positioning_x87(
                args.capture_id
            )
            print(ack)
            print(_canonical_json(status).decode("utf-8"), end="")
            return 0
        if args.command == "finish":
            ack, snapshot = finish_observatory_score_positioning_x87(
                args.capture_id
            )
            analysis = _validate_and_analyze(snapshot, args.module, args.receipt)
            print(ack)
            if args.output_root is not None:
                snapshot_path, analysis_path = _archive(
                    args.output_root, args.capture_id, snapshot, analysis
                )
                print(f"snapshot={snapshot_path}")
                print(f"analysis={analysis_path}")
            else:
                print(_canonical_json(analysis).decode("utf-8"), end="")
            return 0
        snapshot = _load_json(args.snapshot, "x87 snapshot")
        analysis = _validate_and_analyze(snapshot, args.module, args.receipt)
        data = _canonical_json(analysis)
        if args.output is None:
            print(data.decode("utf-8"), end="")
        else:
            _write_create_only(args.output, data)
            print(f"analysis={args.output}")
        return 0
    except (
        BridgeError,
        ScorePositioningX87Error,
        ScorePositioningX87CliError,
        OSError,
        TimeoutError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
