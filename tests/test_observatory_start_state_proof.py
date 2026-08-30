from __future__ import annotations

import copy

import pytest

from src.observatory.start_state_proof import (
    MANIFEST_KIND,
    MANIFEST_SCHEMA_VERSION,
    PROOF_KIND,
    SCHEMA_VERSION,
    StartStateProofError,
    start_state_manifest_sha256,
    start_state_tree_sha256,
    validate_start_state_verification_proof,
)


def _proof(tmp_path) -> dict:
    files = [
        {"relative_path": "log.txt", "size": 3, "sha256": "1" * 64},
        {
            "relative_path": "profile_Alpha/saveData.lua",
            "size": 4,
            "sha256": "2" * 64,
        },
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "capture_track": "owner_local_modified",
        "profile": "Alpha",
        "file_count": len(files),
        "total_bytes": 7,
        "files": files,
        "tree_sha256": start_state_tree_sha256(files),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": PROOF_KIND,
        "verified_at": "2026-08-29T12:00:00+00:00",
        "game_stopped": True,
        "save_root": str((tmp_path / "save").resolve()),
        "snapshot_root": str((tmp_path / "snapshot").resolve()),
        "manifest_sha256": start_state_manifest_sha256(manifest),
        "manifest": manifest,
    }


def test_start_state_proof_binds_exact_tree_before_process_start(tmp_path):
    proof = _proof(tmp_path)
    result = validate_start_state_verification_proof(
        proof,
        process_identity={"created_at": "2026-08-29T12:00:01+00:00"},
    )

    assert result == proof
    assert result is not proof


@pytest.mark.parametrize(
    "mutate,match",
    (
        (lambda proof: proof.update(game_stopped=False), "contract differs"),
        (
            lambda proof: proof["manifest"]["files"][0].update(size=8),
            "contract differs",
        ),
        (
            lambda proof: proof["manifest"]["files"][0].update(
                relative_path="../escape"
            ),
            "file entry is invalid",
        ),
    ),
)
def test_start_state_proof_rejects_tampering(tmp_path, mutate, match):
    proof = copy.deepcopy(_proof(tmp_path))
    mutate(proof)

    with pytest.raises(StartStateProofError, match=match):
        validate_start_state_verification_proof(proof)


def test_start_state_proof_rejects_verification_after_process_start(tmp_path):
    proof = _proof(tmp_path)

    with pytest.raises(StartStateProofError, match="did not precede"):
        validate_start_state_verification_proof(
            proof,
            process_identity={"created_at": "2026-08-29T11:59:59+00:00"},
        )
