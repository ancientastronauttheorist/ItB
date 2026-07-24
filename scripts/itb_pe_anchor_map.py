#!/usr/bin/env python3
"""Create a build-keyed, read-only named-anchor map for a Windows ITB PE."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "native"
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.pe_anchor_map import (  # noqa: E402
    DEFAULT_ANCHORS,
    PEAnchorError,
    build_pe_anchor_map,
    encode_anchor_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument(
        "--anchor",
        action="append",
        dest="anchors",
        help="ASCII anchor to map; repeatable (defaults to ITB high-value names)",
    )
    parser.add_argument("--output", type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise PEAnchorError(f"invalid inventory JSON constant: {value}")


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    """Write only a direct child of the repository's native-evidence root."""
    output_root = _OUTPUT_ROOT.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if output.parent.resolve() != output_root:
        raise PEAnchorError(
            "output must be a direct child of data/observatory/native"
        )
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise PEAnchorError("refusing to replace non-regular output")
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PEAnchorError(
                "refusing to replace an existing non-anchor artifact"
            ) from exc
        if (
            not isinstance(existing, dict)
            or existing.get("analysis_kind") != "pe_named_anchor_map"
        ):
            raise PEAnchorError(
                "refusing to replace an existing non-anchor artifact"
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
        # Atomic replacement changes only this directory entry. It does not
        # follow an existing hardlink or symlink to a game/session file.
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
        inventory = (
            json.loads(
                args.inventory.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
            if args.inventory is not None
            else None
        )
        result = build_pe_anchor_map(
            args.executable,
            anchors=args.anchors or DEFAULT_ANCHORS,
            inventory=inventory,
        )
        rendered = encode_anchor_map(result)
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            _write_evidence_atomically(args.output, rendered)
        return 0
    except (
        PEAnchorError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
