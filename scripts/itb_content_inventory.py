#!/usr/bin/env python3
"""Create and compare deterministic read-only ITB installation inventories."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.content_inventory import (  # noqa: E402
    InventoryError,
    compare_inventories,
    create_inventory,
    detect_installations,
    write_json,
)


def _is_within(path: Path, directory: Path) -> bool:
    return path.expanduser().resolve().is_relative_to(directory.expanduser().resolve())


def _windows_registry_steam_roots() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
        return [Path(value)]
    except (ImportError, OSError, TypeError):
        return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="hash one installation")
    inventory.add_argument("--install-dir", type=Path)
    inventory.add_argument("--platform", choices=("windows", "macos", "linux"))
    inventory.add_argument("--label")
    inventory.add_argument("--output", type=Path)

    locate = subparsers.add_parser("locate", help="find installed Steam copies")
    locate.add_argument("--platform", choices=("windows", "macos", "linux"))

    compare = subparsers.add_parser("compare", help="compare two inventory JSON files")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "locate":
            installs = detect_installations(
                platform_name=args.platform,
                extra_steam_roots=_windows_registry_steam_roots(),
            )
            print(json.dumps([str(path) for path in installs], indent=2))
            return 0 if installs else 1

        if args.command == "inventory":
            install_dir = args.install_dir or (
                Path(os.environ["ITB_INSTALL_DIR"])
                if os.environ.get("ITB_INSTALL_DIR")
                else None
            )
            if install_dir is None:
                installs = detect_installations(
                    platform_name=args.platform,
                    extra_steam_roots=_windows_registry_steam_roots(),
                )
                if len(installs) != 1:
                    raise InventoryError(
                        "automatic discovery requires exactly one installation; "
                        f"found {len(installs)}"
                    )
                install_dir = installs[0]
            result = create_inventory(
                install_dir,
                platform_name=args.platform,
                label=args.label,
            )
            if args.output is not None and _is_within(args.output, install_dir):
                raise InventoryError(
                    "refusing to write inventory output inside the installed game"
                )
        else:
            left = json.loads(args.left.read_text(encoding="utf-8"))
            right = json.loads(args.right.read_text(encoding="utf-8"))
            result = compare_inventories(left, right)

        rendered = write_json(result, args.output)
        if args.output is None:
            sys.stdout.write(rendered)
        return 0
    except (InventoryError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
