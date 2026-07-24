#!/usr/bin/env python3
"""Audit exact player-weapon Lua IDs against Rust wid_from_str mappings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.provenance import (  # noqa: E402
    ProvenanceError,
    load_json_object,
)
from src.observatory.weapon_coverage import (  # noqa: E402
    WeaponCoverageError,
    analyze_player_weapon_ids,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("content_root", type=Path)
    parser.add_argument(
        "--rust-source",
        type=Path,
        default=_REPO_ROOT / "rust_solver/src/weapons.rs",
    )
    args = parser.parse_args(argv)
    try:
        try:
            rust_label = (
                args.rust_source.resolve()
                .relative_to(_REPO_ROOT.resolve())
                .as_posix()
            )
        except ValueError:
            rust_label = args.rust_source.name
        result = analyze_player_weapon_ids(
            load_json_object(args.inventory),
            content_root=args.content_root,
            rust_source=args.rust_source,
            rust_source_label=rust_label,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ProvenanceError,
        WeaponCoverageError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
