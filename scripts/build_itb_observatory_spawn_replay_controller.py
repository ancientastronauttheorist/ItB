#!/usr/bin/env python3
"""Package and attest the inert, content-addressed spawn replay controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "bridge" / "observatory_spawn_replay_controller.lua"
VERSION = "observatory-spawn-replay-controller/1"
SPAWNER_SHA256 = "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
SPAWNER_SOURCE_SUFFIX = "scripts/spawner_backend.lua"
SPAWNER_SOURCE_LINE = 174
RANDOM_ELEMENT_SHA256 = "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
RANDOM_ELEMENT_SOURCE_SUFFIX = "scripts/global.lua"
RANDOM_ELEMENT_SOURCE_LINE = 560


class SpawnReplayBuildError(RuntimeError):
    """Raised when the fixed replay controller cannot be packaged safely."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spawner-source", type=Path, required=True)
    parser.add_argument("--global-source", type=Path, required=True)
    parser.add_argument("--modloader", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _stable_bytes(path: Path, label: str) -> bytes:
    path = Path(os.path.abspath(path.expanduser()))
    if path.is_symlink() or not path.is_file():
        raise SpawnReplayBuildError(f"{label} must be a regular file: {path}")
    before = path.stat()
    payload = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise SpawnReplayBuildError(f"{label} changed while being read")
    return payload


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def build(
    *,
    spawner_source: Path,
    global_source: Path,
    modloader: Path,
    output_root: Path,
) -> dict[str, object]:
    controller = _stable_bytes(SOURCE, "controller source")
    spawner = _stable_bytes(spawner_source, "Spawner source")
    global_lua = _stable_bytes(global_source, "global Lua source")
    loader = _stable_bytes(modloader, "modloader")
    try:
        controller_text = controller.decode("utf-8", errors="strict")
        loader_text = loader.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SpawnReplayBuildError(f"Lua source is not UTF-8: {exc}") from exc
    controller_sha = _sha256(controller)
    if _sha256(spawner) != SPAWNER_SHA256:
        raise SpawnReplayBuildError("Spawner source SHA-256 differs from pinned build")
    if _sha256(global_lua) != RANDOM_ELEMENT_SHA256:
        raise SpawnReplayBuildError("global Lua SHA-256 differs from pinned build")
    required_fragments = (
        f'M.VERSION = "{VERSION}"',
        f'M.SPAWNER_SOURCE_SUFFIX = "{SPAWNER_SOURCE_SUFFIX}"',
        f"M.SPAWNER_SOURCE_LINE = {SPAWNER_SOURCE_LINE}",
        SPAWNER_SHA256,
        f'M.RANDOM_ELEMENT_SOURCE_SUFFIX = "{RANDOM_ELEMENT_SOURCE_SUFFIX}"',
        f"M.RANDOM_ELEMENT_SOURCE_LINE = {RANDOM_ELEMENT_SOURCE_LINE}",
        RANDOM_ELEMENT_SHA256,
        "function Controller:activate()",
        "function Controller:checkpoint()",
        "function Controller:abort()",
        "return M",
    )
    if any(fragment not in controller_text for fragment in required_fragments):
        raise SpawnReplayBuildError("controller source contract differs")
    if any(
        re.search(pattern, controller_text)
        for pattern in (
            r"\bio\s*\.",
            r"\bos\s*\.",
            r"\bloadfile\s*\(",
            r"\bdofile\s*\(",
            r"\bpackage\s*\.",
        )
    ):
        raise SpawnReplayBuildError("controller source contains an unreviewed I/O API")
    if controller_sha not in loader_text:
        raise SpawnReplayBuildError("modloader does not pin the controller SHA-256")
    if loader_text.count(controller_sha) != 1:
        raise SpawnReplayBuildError("modloader controller SHA-256 pin is ambiguous")

    output_root = Path(os.path.abspath(output_root.expanduser()))
    if output_root.is_symlink():
        raise SpawnReplayBuildError("output root must not be a symlink")
    output_root.mkdir(parents=True, exist_ok=True)
    module_name = f"itb_observatory_spawn_replay_controller_{controller_sha}.lua"
    module_path = output_root / module_name
    receipt_path = output_root / f"{module_name.removesuffix('.lua')}_receipt.json"
    if module_path.exists() or module_path.is_symlink() or receipt_path.exists():
        raise SpawnReplayBuildError("create-only controller output already exists")
    with module_path.open("xb") as handle:
        handle.write(controller)
        handle.flush()
        os.fsync(handle.fileno())
    receipt = {
        "schema_version": 1,
        "kind": "observatory_spawn_replay_controller_build",
        "controller_version": VERSION,
        "controller_source": str(SOURCE.resolve()),
        "controller_sha256": controller_sha,
        "module_filename": module_name,
        "module_sha256": _sha256(module_path.read_bytes()),
        "spawner_source": str(Path(spawner_source).resolve()),
        "spawner_source_sha256": SPAWNER_SHA256,
        "spawner_source_suffix": SPAWNER_SOURCE_SUFFIX,
        "spawner_source_linedefined": SPAWNER_SOURCE_LINE,
        "global_source": str(Path(global_source).resolve()),
        "global_source_sha256": RANDOM_ELEMENT_SHA256,
        "random_element_source_suffix": RANDOM_ELEMENT_SOURCE_SUFFIX,
        "random_element_source_linedefined": RANDOM_ELEMENT_SOURCE_LINE,
        "modloader_sha256": _sha256(loader),
        "loading_is_inert": True,
        "runtime_mutation": (
            "exact_Spawner.NextPawn_slot_and_in_span_random_element_slot"
        ),
        "write_mode": "create_only",
    }
    payload = _canonical(receipt)
    with receipt_path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return {
        "module": str(module_path),
        "receipt": str(receipt_path),
        "controller_sha256": controller_sha,
        "receipt_sha256": _sha256(payload),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build(
            spawner_source=args.spawner_source,
            global_source=args.global_source,
            modloader=args.modloader,
            output_root=args.output_root,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, SpawnReplayBuildError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
