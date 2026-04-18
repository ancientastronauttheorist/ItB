"""Phase 4 P4-1d — pr_drafter tests.

The drafter stacks pattern_miner + board_extractor + stage_candidates.
Tests stub the moving parts (verifier in particular — it imports the
Rust solver) so they're fast and wheel-independent.

Coverage:

- Vision candidates with stageable fields → staged (or reported as
  would-stage in dry-run).
- failure_db candidates → skipped with "manual override required"
  since the drafter can't guess which Rust field to patch.
- No recording on disk → skipped with extractor-returned-None reason.
- Verifier says "no observable change" → skipped; nothing staged.
- max_stage cap applies absolutely (not per-weapon).
- dry_run=True leaves disk untouched but populates the report.
- execute=True writes fixture and appends to the staged file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research import pr_drafter
from src.research import pattern_miner as pm
from src.research import board_extractor


# ── helpers ─────────────────────────────────────────────────────────────────


def _vision_candidate(
    *,
    weapon_id: str = "Prime_Shift",
    field_name: str = "damage",
    rust_value: Any = 1,
    vision_value: Any = 5,
    refs: list[tuple[str, int, int]] | None = None,
    count: int | None = None,
) -> pm.MinedCandidate:
    from typing import Any
    sample = {
        "weapon_id": weapon_id,
        "field": field_name,
        "rust_value": rust_value,
        "vision_value": vision_value,
        "severity": "high",
        "confidence": 1.0,
        "display_name": weapon_id,
        "run_id": (refs or [("R1", -1, -1)])[0][0],
    }
    sig = pm.DiffSignature(
        source="vision", weapon_id=weapon_id, field=field_name,
        rust_bucket=str(rust_value), vision_bucket=str(vision_value),
    )
    refs = refs or [("R1", -1, -1)]
    return pm.MinedCandidate(
        signature=sig,
        count=count if count is not None else len(refs),
        board_refs=refs,
        sample_entries=[sample],
    )


def _failure_candidate(
    *,
    weapon_id: str = "Prime_Shift",
    refs: list[tuple[str, int, int]] | None = None,
) -> pm.MinedCandidate:
    sig = pm.DiffSignature(
        source="failure_db", weapon_id=weapon_id, field="damage_amount",
        rust_bucket="predicted", vision_bucket="tile:|unit:hp|scalar:",
    )
    refs = refs or [("R1", 0, 1)]
    return pm.MinedCandidate(
        signature=sig, count=len(refs), board_refs=refs, sample_entries=[],
    )


from typing import Any


def _write_board(root: Path, run_id: str, m: int, t: int, bs: dict | None = None) -> Path:
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"m{m:02d}_turn_{t:02d}_board.json"
    p.write_text(json.dumps({
        "data": {"bridge_state": bs or {"phase": "combat_player", "tiles": []}},
    }))
    return p


def _stub_verify(observable: bool, *, reason: str = "", plan_changed: bool = False,
                 score_delta: float = 0.0):
    """Factory: returns a ``verify_observable_change`` replacement that
    reports a fixed verdict. Lets tests dodge the real solver import."""
    def _fn(*args, **kwargs):
        return board_extractor.VerificationResult(
            observable_change=observable,
            reason=reason or ("moved" if observable else "did not move"),
            plan_changed=plan_changed,
            score_delta=score_delta,
            stock_score=0.0,
            patched_score=score_delta,
            applied_overrides=[{"weapon_id": args[1]["weapon_id"]}],
        )
    return _fn


# ── dry-run behaviour ───────────────────────────────────────────────────────


def test_dry_run_leaves_disk_untouched(tmp_path: Path, monkeypatch):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    staged = tmp_path / "staged.jsonl"
    _write_board(rec, "R1", 0, 1)
    cand = _vision_candidate(refs=[("R1", 0, 1)])

    monkeypatch.setattr(board_extractor, "verify_observable_change",
                        _stub_verify(True, plan_changed=True))

    report = pr_drafter.draft_from_candidates(
        [cand], dry_run=True, recordings_root=rec,
        output_dir=out, staged_path=staged,
    )
    # Dry-run: no files on disk, but the outcome says "would stage".
    assert not out.exists() or not list(out.iterdir())
    assert not staged.exists()
    assert report.staged_count == 1
    assert report.outcomes[0].status == "staged"
    assert "dry-run" in report.outcomes[0].reason


def test_execute_writes_fixture_and_stages(tmp_path: Path, monkeypatch):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    staged = tmp_path / "staged.jsonl"
    _write_board(rec, "R1", 0, 1)
    cand = _vision_candidate(refs=[("R1", 0, 1)])

    monkeypatch.setattr(board_extractor, "verify_observable_change",
                        _stub_verify(True, plan_changed=True))

    report = pr_drafter.draft_from_candidates(
        [cand], dry_run=False, recordings_root=rec,
        output_dir=out, staged_path=staged,
    )
    # Fixture written with the P4-1c schema.
    fixtures = list(out.glob("*.json"))
    assert len(fixtures) == 1
    fx = json.loads(fixtures[0].read_text())
    assert fx["weapon_id"] == "Prime_Shift"
    assert fx["signature_hash"] == cand.signature.hash8()

    # Staged entry written with P3-5 schema — source_mismatch survives
    # so review_overrides reject can later derive its deny-list hash.
    assert staged.exists()
    rows = [json.loads(l) for l in staged.read_text().strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["weapon_id"] == "Prime_Shift"
    assert "source_mismatch" in rows[0]
    assert rows[0]["source_mismatch"]["field"] == "damage"


# ── skip paths ──────────────────────────────────────────────────────────────


def test_failure_db_candidates_skipped(tmp_path: Path, monkeypatch):
    rec = tmp_path / "rec"
    _write_board(rec, "R1", 0, 1)
    cand = _failure_candidate(refs=[("R1", 0, 1)])

    report = pr_drafter.draft_from_candidates(
        [cand], dry_run=True, recordings_root=rec,
        output_dir=tmp_path / "boards", staged_path=tmp_path / "staged.jsonl",
        verify=False,
    )
    assert report.staged_count == 0
    assert report.outcomes[0].status == "skipped"
    assert "hand-authored" in report.outcomes[0].reason


def test_no_recording_skipped(tmp_path: Path, monkeypatch):
    """Vision candidates sometimes tag board_refs with (run_id, -1, -1)
    — no recording path to resolve. Drafter skips rather than crash."""
    rec = tmp_path / "rec"
    cand = _vision_candidate(refs=[("R1", -1, -1)])
    report = pr_drafter.draft_from_candidates(
        [cand], dry_run=True, recordings_root=rec,
        output_dir=tmp_path / "boards", staged_path=tmp_path / "staged.jsonl",
        verify=False,
    )
    assert report.outcomes[0].status == "skipped"
    assert "no recording" in report.outcomes[0].reason


def test_verify_no_observable_change_skips(tmp_path: Path, monkeypatch):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    staged = tmp_path / "staged.jsonl"
    _write_board(rec, "R1", 0, 1)
    cand = _vision_candidate(refs=[("R1", 0, 1)])

    # Verifier stubbed to say "nope, no change".
    monkeypatch.setattr(board_extractor, "verify_observable_change",
                        _stub_verify(False, reason="override is a no-op"))

    report = pr_drafter.draft_from_candidates(
        [cand], dry_run=False, recordings_root=rec,
        output_dir=out, staged_path=staged,
    )
    assert report.staged_count == 0
    assert report.outcomes[0].status == "skipped"
    # Fixture was extracted (we need it to run the verifier), but the
    # staged file stays empty.
    assert not staged.exists()


# ── max_stage cap ───────────────────────────────────────────────────────────


def test_max_stage_caps_absolute_not_per_weapon(tmp_path: Path, monkeypatch):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    staged = tmp_path / "staged.jsonl"
    for i in range(4):
        _write_board(rec, f"R{i}", 0, 1)
    cands = [
        _vision_candidate(weapon_id=f"W_{i}", refs=[(f"R{i}", 0, 1)])
        for i in range(4)
    ]
    monkeypatch.setattr(board_extractor, "verify_observable_change",
                        _stub_verify(True, plan_changed=True))

    report = pr_drafter.draft_from_candidates(
        cands, dry_run=False, recordings_root=rec,
        output_dir=out, staged_path=staged, max_stage=2,
    )
    assert report.staged_count == 2
    assert sum(1 for o in report.outcomes if o.status == "skipped"
               and "max_stage" in o.reason) == 2
