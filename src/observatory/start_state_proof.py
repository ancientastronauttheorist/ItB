"""Strict proof that a matched trial began from one sealed save tree."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
PROOF_KIND = "observatory_rng_trial_start_state_verification"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_KIND = "observatory_rng_trial_start_state"


class StartStateProofError(RuntimeError):
    """Raised when a start-state verification proof is malformed or stale."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StartStateProofError(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise StartStateProofError(f"{label} fields differ")


def _timestamp(value: object, label: str) -> datetime:
    if type(value) is not str:
        raise StartStateProofError(f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StartStateProofError(f"{label} is invalid") from exc
    if parsed.tzinfo is None:
        raise StartStateProofError(f"{label} has no timezone")
    return parsed


def _sha256_text(value: object, *, pretty: bool) -> str:
    if pretty:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    else:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def start_state_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Return the digest of the canonical on-disk manifest encoding."""
    return _sha256_text(manifest, pretty=True)


def start_state_tree_sha256(entries: list[Mapping[str, Any]]) -> str:
    """Return the canonical digest of an ordered start-state file list."""
    return _sha256_text(entries, pretty=False)


def validate_start_state_verification_proof(
    value: object,
    *,
    process_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a detached exact proof, optionally bound before one process start."""
    proof = _mapping(value, "start-state proof")
    _exact(
        proof,
        {
            "schema_version",
            "kind",
            "verified_at",
            "game_stopped",
            "save_root",
            "snapshot_root",
            "manifest_sha256",
            "manifest",
        },
        "start-state proof",
    )
    verified_at = _timestamp(proof.get("verified_at"), "start-state verified_at")
    save_root = Path(str(proof.get("save_root")))
    snapshot_root = Path(str(proof.get("snapshot_root")))
    manifest = _mapping(proof.get("manifest"), "start-state manifest")
    _exact(
        manifest,
        {
            "schema_version",
            "kind",
            "capture_track",
            "profile",
            "file_count",
            "total_bytes",
            "files",
            "tree_sha256",
        },
        "start-state manifest",
    )
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise StartStateProofError("start-state manifest has no files")
    normalized_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry_value in files:
        entry = _mapping(entry_value, "start-state file")
        _exact(entry, {"relative_path", "size", "sha256"}, "start-state file")
        relative = entry.get("relative_path")
        member = PurePosixPath(str(relative))
        digest = entry.get("sha256")
        if (
            type(relative) is not str
            or relative in seen
            or member.is_absolute()
            or not member.parts
            or any(part in {"", ".", ".."} for part in member.parts)
            or type(entry.get("size")) is not int
            or entry.get("size") < 0
            or type(digest) is not str
            or len(digest) != 64
            or digest.lower() != digest
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise StartStateProofError("start-state file entry is invalid")
        seen.add(relative)
        normalized_files.append(dict(entry))
    manifest_digest = start_state_manifest_sha256(manifest)
    if (
        proof.get("schema_version") != SCHEMA_VERSION
        or proof.get("kind") != PROOF_KIND
        or proof.get("game_stopped") is not True
        or not save_root.is_absolute()
        or not snapshot_root.is_absolute()
        or save_root == snapshot_root
        or os.path.normcase(str(save_root)) == os.path.normcase(str(snapshot_root))
        or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("kind") != MANIFEST_KIND
        or manifest.get("capture_track")
        not in {"owner_local_modified", "pristine_reference"}
        or type(manifest.get("profile")) is not str
        or not manifest.get("profile")
        or manifest.get("file_count") != len(normalized_files)
        or manifest.get("total_bytes")
        != sum(entry["size"] for entry in normalized_files)
        or normalized_files != sorted(
            normalized_files, key=lambda item: item["relative_path"]
        )
        or manifest.get("tree_sha256")
        != start_state_tree_sha256(normalized_files)
        or proof.get("manifest_sha256") != manifest_digest
    ):
        raise StartStateProofError("start-state proof contract differs")
    if process_identity is not None:
        process_created_at = _timestamp(
            process_identity.get("created_at"), "process created_at"
        )
        if verified_at >= process_created_at:
            raise StartStateProofError(
                "start-state verification did not precede process creation"
            )
    return json.loads(json.dumps(proof, allow_nan=False))
