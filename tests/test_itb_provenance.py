"""Tests for build-keyed mechanics provenance validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.observatory.provenance import ProvenanceError, validate_provenance


def _inventory() -> dict:
    return {
        "platform": "windows",
        "executable": {"architecture": "x86", "sha256": "exe"},
        "steam": {
            "build_id": "1",
            "installed_depots": [{"manifest": "depot"}],
        },
        "content": {
            "scripts": {
                "revision_sha256": "scripts",
                "files": [{"path": "scripts/global.lua", "sha256": "global"}],
            },
            "maps": {"revision_sha256": "maps"},
        },
    }


def _provenance() -> dict:
    return {
        "schema_version": 1,
        "build_identity": {
            "platform": "windows",
            "architecture": "x86",
            "executable_sha256": "exe",
            "build_id": "1",
            "depot_manifest": "depot",
            "scripts_revision_sha256": "scripts",
            "maps_revision_sha256": "maps",
        },
        "records": [
            {
                "id": "enemy-scoring",
                "coverage": "partial",
                "sources": [
                    {
                        "path": "scripts/global.lua",
                        "sha256": "global",
                        "symbols": ["ScorePositioning"],
                    }
                ],
                "implementations": [{"path": "rust_solver/src/turn_projection.rs"}],
                "tests": [{"path": "rust_solver/src/turn_projection.rs"}],
                "evidence": [
                    {
                        "classification": "fact",
                        "statement": "The Lua symbol is present.",
                    }
                ],
                "known_gaps": ["Native candidate enumeration is unresolved."],
            }
        ],
    }


def test_valid_provenance_is_counted(tmp_path: Path):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text("// test")
    counts = validate_provenance(_provenance(), _inventory(), repo_root=tmp_path)
    assert counts == {
        "gap": 0,
        "native_dependency": 0,
        "partial": 1,
        "verified": 0,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["build_identity"].update(build_id="2"), "build_identity.build_id"),
        (
            lambda data: data["records"][0]["sources"][0].update(sha256="stale"),
            "stale source hash",
        ),
        (
            lambda data: data["records"][0].update(coverage="partial", known_gaps=[]),
            "requires known_gaps",
        ),
        (
            lambda data: data["records"].append(deepcopy(data["records"][0])),
            "duplicate provenance id",
        ),
        (
            lambda data: data["records"][0].update(
                coverage="verified",
                implementations=[],
                tests=[],
                known_gaps=[],
            ),
            "verified coverage requires implementations and tests",
        ),
        (
            lambda data: data["records"][0].update(
                coverage="verified",
                known_gaps=[],
                evidence=[
                    {
                        "classification": "hypothesis",
                        "statement": "Maybe correct.",
                    }
                ],
            ),
            "verified coverage requires fact-classified evidence",
        ),
    ],
)
def test_invalid_provenance_fails_closed(mutation, message: str):
    provenance = _provenance()
    mutation(provenance)
    with pytest.raises(ProvenanceError, match=message):
        validate_provenance(provenance, _inventory())
