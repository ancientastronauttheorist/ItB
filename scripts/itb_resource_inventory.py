#!/usr/bin/env python3
"""Build or verify a metadata-only Into the Breach resource inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "resources"
_MAX_JSON_BYTES = 512 * 1024 * 1024
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.resource_archive import (  # noqa: E402
    ANALYSIS_KIND,
    ResourceArchiveError,
    build_resource_inventory,
    encode_resource_inventory,
    validate_resource_inventory,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="inventory one sealed installation")
    build.add_argument("--install-dir", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify one committed inventory")
    verify.add_argument("--install-dir", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise ResourceArchiveError(f"invalid JSON constant: {value}")


def _read_json_object(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ResourceArchiveError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    if before.st_size > _MAX_JSON_BYTES:
        raise ResourceArchiveError(f"{label} exceeds the JSON size limit")
    payload = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise ResourceArchiveError(f"{label} changed while being read")
    value = json.loads(
        payload.decode("utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(value, dict):
        raise ResourceArchiveError(f"{label} must contain a JSON object")
    return value


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    output_root = _OUTPUT_ROOT.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if output.parent.resolve() != output_root:
        raise ResourceArchiveError(
            "output must be a direct child of data/observatory/resources"
        )
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise ResourceArchiveError("refusing to replace non-regular output")
        try:
            existing = _read_json_object(destination, "existing output")
        except (
            ResourceArchiveError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ResourceArchiveError(
                "refusing to replace an existing non-resource-inventory artifact"
            ) from exc
        if existing.get("analysis_kind") != ANALYSIS_KIND:
            raise ResourceArchiveError(
                "refusing to replace an existing non-resource-inventory artifact"
            )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output_root,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json_object(args.inventory, "inventory")
        if args.command == "build":
            result = build_resource_inventory(
                args.install_dir,
                inventory=inventory,
            )
            rendered = encode_resource_inventory(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered)
        else:
            evidence = _read_json_object(args.evidence, "evidence")
            result = validate_resource_inventory(
                args.install_dir,
                evidence,
                inventory=inventory,
            )
            sys.stdout.write(encode_resource_inventory(result))
        return 0
    except (
        ResourceArchiveError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
