#!/usr/bin/env python3
"""Snapshot, verify, and restore an exact ITB matched-trial start state."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_KIND = "observatory_rng_trial_start_state"
MANIFEST_NAME = "start_state_manifest.json"
PAYLOAD_NAME = "payload"
TOP_LEVEL_FILES = ("settings.lua", "log.txt", "steam_autocloud.vdf")


class PairStateError(RuntimeError):
    """Raised when a start-state snapshot or restore is unsafe."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--save-root", type=Path, required=True)
    snapshot.add_argument("--output-root", type=Path, required=True)
    snapshot.add_argument("--profile", default="Alpha")
    snapshot.add_argument(
        "--capture-track",
        choices=("owner_local_modified", "pristine_reference"),
        required=True,
    )
    verify = commands.add_parser("verify")
    verify.add_argument("--save-root", type=Path, required=True)
    verify.add_argument("--snapshot-root", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--save-root", type=Path, required=True)
    restore.add_argument("--snapshot-root", type=Path, required=True)
    restore.add_argument("--allow-restore", action="store_true")
    sandbox = commands.add_parser(
        "session-sandbox",
        help="clone a live solver session without reusable execution authority",
    )
    sandbox.add_argument("--source-session", type=Path, required=True)
    sandbox.add_argument("--output-session", type=Path, required=True)
    sandbox.add_argument("--experiment-id", required=True)
    return parser


def _stable_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise PairStateError(f"expected regular file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise PairStateError(f"file changed while being read: {path}")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256((encoded + "\n").encode("utf-8"))


def _resolved_root(path: Path, label: str, *, must_exist: bool = True) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if must_exist and not candidate.is_dir():
        raise PairStateError(f"{label} is not a directory: {candidate}")
    if candidate.parent == candidate:
        raise PairStateError(f"{label} cannot be a filesystem root")
    return candidate.resolve(strict=must_exist)


def _relative_files(save_root: Path, profile: str) -> list[str]:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    if not profile or any(ch not in allowed for ch in profile):
        raise PairStateError("profile must be a simple identifier")
    profile_dir = save_root / f"profile_{profile}"
    if not profile_dir.is_dir() or profile_dir.is_symlink():
        raise PairStateError(f"profile directory is unavailable: {profile_dir}")
    relative = [
        path.relative_to(save_root).as_posix()
        for path in profile_dir.rglob("*")
        if path.is_file()
    ]
    for name in TOP_LEVEL_FILES:
        path = save_root / name
        if not path.is_file() or path.is_symlink():
            raise PairStateError(f"required save file is unavailable: {path}")
        relative.append(name)
    return sorted(relative)


def _safe_member(root: Path, relative: str) -> Path:
    member = PurePosixPath(relative)
    if (
        member.is_absolute()
        or not member.parts
        or any(part in {"", ".", ".."} for part in member.parts)
    ):
        raise PairStateError(f"unsafe manifest path: {relative!r}")
    candidate = root.joinpath(*member.parts)
    resolved_parent = candidate.parent.resolve(strict=False)
    if os.path.commonpath((str(root), str(resolved_parent))) != str(root):
        raise PairStateError(f"manifest path escapes root: {relative!r}")
    return candidate


def _entries_for(root: Path, relative_files: list[str]) -> list[dict[str, Any]]:
    entries = []
    for relative in relative_files:
        path = _safe_member(root, relative)
        data = _stable_bytes(path)
        entries.append(
            {
                "relative_path": relative,
                "size": len(data),
                "sha256": _sha256(data),
            }
        )
    return entries


def _write_create_only_json(path: Path, value: Any) -> None:
    data = (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _load_manifest(snapshot_root: Path) -> dict[str, Any]:
    path = snapshot_root / MANIFEST_NAME
    try:
        value = json.loads(_stable_bytes(path).decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PairStateError(f"invalid start-state manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise PairStateError("start-state manifest must be an object")
    if value.get("schema_version") != SCHEMA_VERSION or value.get("kind") != MANIFEST_KIND:
        raise PairStateError("start-state manifest contract mismatch")
    if value.get("capture_track") not in {"owner_local_modified", "pristine_reference"}:
        raise PairStateError("start-state capture track is invalid")
    entries = value.get("files")
    if not isinstance(entries, list) or not entries:
        raise PairStateError("start-state manifest has no files")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"relative_path", "size", "sha256"}:
            raise PairStateError("start-state file entry is invalid")
        relative = entry["relative_path"]
        if type(relative) is not str or relative in seen:
            raise PairStateError("start-state file path is invalid or duplicated")
        _safe_member(snapshot_root / PAYLOAD_NAME, relative)
        if type(entry["size"]) is not int or entry["size"] < 0:
            raise PairStateError("start-state file size is invalid")
        if type(entry["sha256"]) is not str or len(entry["sha256"]) != 64:
            raise PairStateError("start-state file digest is invalid")
        seen.add(relative)
    if value.get("tree_sha256") != _canonical_sha256(entries):
        raise PairStateError("start-state tree digest mismatch")
    payload_entries = _entries_for(snapshot_root / PAYLOAD_NAME, sorted(seen))
    if payload_entries != entries:
        raise PairStateError("start-state payload does not match its manifest")
    return value


def _game_running() -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Breach.exe", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    for row in csv.reader(result.stdout.splitlines()):
        if row and row[0].casefold() == "breach.exe":
            return True
    return False


def snapshot_state(args: argparse.Namespace) -> int:
    if _game_running():
        raise PairStateError("close Into the Breach before snapshotting")
    save_root = _resolved_root(args.save_root, "save root")
    output_root = _resolved_root(args.output_root, "output root", must_exist=False)
    if output_root.exists():
        raise PairStateError(f"snapshot output already exists: {output_root}")
    output_root.mkdir(parents=True)
    payload_root = output_root / PAYLOAD_NAME
    payload_root.mkdir()
    relative_files = _relative_files(save_root, args.profile)
    try:
        for relative in relative_files:
            source = _safe_member(save_root, relative)
            target = _safe_member(payload_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)
        entries = _entries_for(payload_root, relative_files)
        if entries != _entries_for(save_root, relative_files):
            raise PairStateError("snapshot copy failed byte verification")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "capture_track": args.capture_track,
            "profile": args.profile,
            "file_count": len(entries),
            "total_bytes": sum(entry["size"] for entry in entries),
            "files": entries,
            "tree_sha256": _canonical_sha256(entries),
        }
        _write_create_only_json(output_root / MANIFEST_NAME, manifest)
    except Exception:
        shutil.rmtree(output_root, ignore_errors=True)
        raise
    print(
        f"snapshot={output_root} files={manifest['file_count']} "
        f"bytes={manifest['total_bytes']} tree_sha256={manifest['tree_sha256']}"
    )
    return 0


def verify_state(args: argparse.Namespace) -> int:
    save_root = _resolved_root(args.save_root, "save root")
    snapshot_root = _resolved_root(args.snapshot_root, "snapshot root")
    manifest = _load_manifest(snapshot_root)
    expected_paths = [entry["relative_path"] for entry in manifest["files"]]
    live_paths = _relative_files(save_root, manifest["profile"])
    if live_paths != expected_paths:
        raise PairStateError("live save file set differs from the snapshot")
    live_entries = _entries_for(save_root, live_paths)
    if live_entries != manifest["files"]:
        raise PairStateError("live save bytes differ from the snapshot")
    print(
        f"verified files={manifest['file_count']} bytes={manifest['total_bytes']} "
        f"tree_sha256={manifest['tree_sha256']}"
    )
    return 0


def restore_state(args: argparse.Namespace) -> int:
    if not args.allow_restore:
        raise PairStateError("restore requires --allow-restore")
    if _game_running():
        raise PairStateError("close Into the Breach before restoring")
    save_root = _resolved_root(args.save_root, "save root")
    snapshot_root = _resolved_root(args.snapshot_root, "snapshot root")
    manifest = _load_manifest(snapshot_root)
    expected_paths = {entry["relative_path"] for entry in manifest["files"]}
    profile_prefix = f"profile_{manifest['profile']}/"
    for relative in _relative_files(save_root, manifest["profile"]):
        if relative.startswith(profile_prefix) and relative not in expected_paths:
            extra = _safe_member(save_root, relative)
            if extra.is_symlink():
                raise PairStateError(f"refusing to remove symlink: {extra}")
            extra.unlink()
    payload_root = snapshot_root / PAYLOAD_NAME
    for entry in manifest["files"]:
        relative = entry["relative_path"]
        source = _safe_member(payload_root, relative)
        target = _safe_member(save_root, relative)
        if target.is_symlink():
            raise PairStateError(f"refusing to overwrite symlink: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
    live_paths = _relative_files(save_root, manifest["profile"])
    if live_paths != sorted(expected_paths):
        raise PairStateError("restored save file set failed verification")
    if _entries_for(save_root, live_paths) != manifest["files"]:
        raise PairStateError("restored save bytes failed verification")
    print(
        f"restored files={manifest['file_count']} bytes={manifest['total_bytes']} "
        f"tree_sha256={manifest['tree_sha256']}"
    )
    return 0


def sandbox_session(args: argparse.Namespace) -> int:
    """Create an isolated solver session for a matched runtime experiment.

    Strategy context is preserved so both halves select the same plan.  Runtime
    execution state and all previously consumed dirty-consent tokens are reset,
    and the run id is namespaced so the sandbox cannot reuse authority minted
    for the live achievement session.
    """

    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    experiment_id = str(args.experiment_id)
    if not experiment_id or any(ch not in allowed for ch in experiment_id):
        raise PairStateError("experiment id must be a simple identifier")

    source = Path(os.path.abspath(args.source_session.expanduser()))
    if source.is_symlink() or not source.is_file():
        raise PairStateError(f"source session is not a regular file: {source}")
    output = Path(os.path.abspath(args.output_session.expanduser()))
    if output.parent == output:
        raise PairStateError("output session cannot be a filesystem root")
    if output.exists() or output.is_symlink():
        raise PairStateError(f"output session already exists: {output}")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise PairStateError(f"output session parent is unavailable: {output.parent}")

    try:
        session = json.loads(_stable_bytes(source).decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PairStateError(f"invalid source session: {exc}") from exc
    if not isinstance(session, dict):
        raise PairStateError("source session must be an object")
    mission_index = session.get("mission_index")
    if type(mission_index) is not int or mission_index < 0:
        raise PairStateError("source session mission_index is invalid")

    source_sha256 = _sha256(_stable_bytes(source))
    base_run_id = str(session.get("run_id") or "default")
    session["run_id"] = f"{base_run_id}-observatory-{experiment_id}"
    session["dirty_consent_used"] = []
    session["actions_executed"] = 0
    session["active_solution"] = None
    session["held_end_turn_block"] = None
    session["end_turn_plan_ledger"] = None
    session["post_enemy_block"] = None
    session["recorded_post_enemy_turns"] = []
    _write_create_only_json(output, session)
    print(
        f"session_sandbox={output} source_sha256={source_sha256} "
        f"run_id={session['run_id']} mission_index={mission_index}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            return snapshot_state(args)
        if args.command == "verify":
            return verify_state(args)
        if args.command == "restore":
            return restore_state(args)
        return sandbox_session(args)
    except (PairStateError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
