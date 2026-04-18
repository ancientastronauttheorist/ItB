"""Phase 4 P4-1c — board extractor & observable-change verifier tests.

Extractor tests are pure file ops: write a fake recording into
tmp_path, run the extractor, assert the fixture exists in the
expected schema. No solver required.

Verifier tests import ``itb_solver`` via pytest.importorskip — CI
runs them against the real wheel; local dev without the wheel still
collects the file cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research import board_extractor, pattern_miner as pm


# ── helpers ─────────────────────────────────────────────────────────────────


def _write_board_recording(
    recordings_root: Path,
    run_id: str,
    mission: int,
    turn: int,
    bridge_state: dict | None = None,
) -> Path:
    d = recordings_root / run_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"m{mission:02d}_turn_{turn:02d}_board.json"
    p.write_text(json.dumps({
        "run_id": run_id,
        "mission_index": mission,
        "turn": turn,
        "data": {
            "bridge_state": bridge_state or {"phase": "combat_player", "tiles": []},
        },
    }))
    return p


def _mk_candidate(
    *,
    weapon_id: str = "Prime_Shift",
    source: str = "failure_db",
    field: str = "damage_amount",
    refs: list[tuple[str, int, int]] | None = None,
) -> pm.MinedCandidate:
    sig = pm.DiffSignature(
        source=source, weapon_id=weapon_id, field=field,
        rust_bucket="predicted", vision_bucket="tile:|unit:hp|scalar:",
    )
    return pm.MinedCandidate(
        signature=sig,
        count=len(refs or []),
        board_refs=refs or [("RUN1", 0, 1)],
        sample_entries=[],
    )


# ── extractor ───────────────────────────────────────────────────────────────


def test_extract_writes_fixture_with_expected_schema(tmp_path: Path):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    bs = {"phase": "combat_player", "tiles": [{"x": 0, "y": 0}], "turn": 1}
    _write_board_recording(rec, "RUN1", 0, 1, bridge_state=bs)

    cand = _mk_candidate(refs=[("RUN1", 0, 1)])
    path = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )
    assert path is not None
    assert path.exists()

    fixture = json.loads(path.read_text())
    assert fixture["weapon_id"] == "Prime_Shift"
    assert fixture["case"] == cand.signature.hash8()
    assert fixture["bridge_state"] == bs
    assert fixture["signature_hash"] == cand.signature.hash8()
    assert fixture["source_board_ref"] == {
        "run_id": "RUN1", "mission": 0, "turn": 1,
    }


def test_extract_filename_uses_weapon_and_hash(tmp_path: Path):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    _write_board_recording(rec, "RUN1", 0, 1)
    cand = _mk_candidate(weapon_id="Brute_Grapple", refs=[("RUN1", 0, 1)])

    path = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )
    assert path.name == f"Brute_Grapple_{cand.signature.hash8()}.json"


def test_extract_skips_vision_only_refs(tmp_path: Path):
    """Vision-source candidates tag board_refs with (run_id, -1, -1)
    because the comparator fires on a weapon preview, not a turn.
    The extractor must return None — the drafter will author a
    fixture by hand instead of copying a nonexistent board."""
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    cand = _mk_candidate(source="vision", refs=[("VR1", -1, -1)])
    assert board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    ) is None
    assert not out.exists()


def test_extract_falls_through_to_next_ref_if_first_missing(tmp_path: Path):
    """When the earliest board_ref has no recording on disk, the
    extractor must try the next one rather than giving up — recordings
    get pruned, miners don't."""
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    _write_board_recording(rec, "RUN2", 0, 3)  # only the second ref exists
    cand = _mk_candidate(refs=[("RUN1_missing", 0, 1), ("RUN2", 0, 3)])

    path = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )
    assert path is not None
    fixture = json.loads(path.read_text())
    assert fixture["source_board_ref"]["run_id"] == "RUN2"


def test_extract_returns_none_when_no_recordings_found(tmp_path: Path):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    cand = _mk_candidate(refs=[("GHOST", 0, 1)])
    assert board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    ) is None


def test_extract_returns_none_for_unknown_weapon(tmp_path: Path):
    """``signature_from_vision`` tags unknown weapons with
    ``weapon_id="?:display_name"``. Those can't be fixture-extracted
    because there's no Rust weapon_id to patch."""
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    _write_board_recording(rec, "RUN1", 0, 1)
    cand = _mk_candidate(weapon_id="?:mystery weapon", refs=[("RUN1", 0, 1)])
    assert board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    ) is None


def test_extract_is_idempotent_by_default(tmp_path: Path):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    _write_board_recording(rec, "RUN1", 0, 1, bridge_state={"tag": "v1"})
    cand = _mk_candidate(refs=[("RUN1", 0, 1)])
    first = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )

    # Replace the underlying recording; default call should NOT rewrite.
    _write_board_recording(rec, "RUN1", 0, 1, bridge_state={"tag": "v2"})
    second = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )
    assert first == second
    assert json.loads(first.read_text())["bridge_state"]["tag"] == "v1"


def test_extract_overwrite_flag_re_extracts(tmp_path: Path):
    rec = tmp_path / "rec"
    out = tmp_path / "boards"
    _write_board_recording(rec, "RUN1", 0, 1, bridge_state={"tag": "v1"})
    cand = _mk_candidate(refs=[("RUN1", 0, 1)])
    board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out,
    )
    _write_board_recording(rec, "RUN1", 0, 1, bridge_state={"tag": "v2"})
    p = board_extractor.extract_regression_board(
        cand, recordings_root=rec, output_dir=out, overwrite=True,
    )
    assert json.loads(p.read_text())["bridge_state"]["tag"] == "v2"


# ── verifier (itb_solver required) ──────────────────────────────────────────


def _pick_live_board_with_nontrivial_score(recordings_root: Path) -> Path | None:
    """Walk recordings in time order; return the first board whose
    stock solve has a non-None score and at least one action. Some
    recorded boards capture post-turn state (everything ``active=False``,
    score=None) and can't be used for verifier round-trip tests."""
    import itb_solver
    if not recordings_root.exists():
        return None
    for run_dir in sorted(recordings_root.iterdir()):
        if not run_dir.is_dir():
            continue
        for board in sorted(run_dir.glob("m*_turn_*_board.json")):
            try:
                bs = json.loads(board.read_text())["data"]["bridge_state"]
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                continue
            try:
                out = json.loads(itb_solver.solve(json.dumps(bs), 2.0))
            except Exception:
                continue
            if out.get("score") is not None and out.get("actions"):
                return board
    return None


def test_verify_flags_observable_change_when_override_moves_plan(tmp_path: Path):
    """A damage bump on a weapon that's actually fired should move
    either the plan or the score — the solver picks differently when
    Vice Fist suddenly deals 99 damage."""
    pytest.importorskip("itb_solver")
    repo_recordings = Path(__file__).resolve().parents[1] / "recordings"
    source = _pick_live_board_with_nontrivial_score(repo_recordings)
    if source is None:
        pytest.skip("no live recording produces a solvable board")

    bridge_state = json.loads(source.read_text())["data"]["bridge_state"]
    # Pick a weapon the stock solve actually fires on this board.
    import itb_solver
    stock = json.loads(itb_solver.solve(json.dumps(bridge_state), 2.0))
    fired = next((a for a in (stock.get("actions") or [])
                  if a.get("weapon_id")), None)
    if fired is None:
        pytest.skip("solver produced no actions on picked board")
    weapon_id = fired["weapon_id"]

    fixture = tmp_path / f"{weapon_id}_bump.json"
    fixture.write_text(json.dumps({
        "weapon_id": weapon_id,
        "case": "bump",
        "bridge_state": bridge_state,
    }))

    override = {"weapon_id": weapon_id, "damage": 99}
    result = board_extractor.verify_observable_change(fixture, override)
    assert result.applied_overrides, (
        f"override didn't reach solver: {result.reason}"
    )
    assert result.observable_change, result.reason


def test_verify_flags_no_observable_change_when_override_is_noop(tmp_path: Path):
    """Setting a field to its current value should surface as
    ``observable_change=False`` — the drafter will skip publishing a
    PR that would trip the P3-7 regression gate."""
    pytest.importorskip("itb_solver")
    from src.model.weapons import WEAPON_DEFS
    repo_recordings = Path(__file__).resolve().parents[1] / "recordings"
    source = _pick_live_board_with_nontrivial_score(repo_recordings)
    if source is None:
        pytest.skip("no live recording produces a solvable board")

    bridge_state = json.loads(source.read_text())["data"]["bridge_state"]
    import itb_solver
    stock = json.loads(itb_solver.solve(json.dumps(bridge_state), 2.0))
    fired = next((a for a in (stock.get("actions") or [])
                  if a.get("weapon_id")), None)
    if fired is None:
        pytest.skip("solver produced no actions on picked board")
    weapon_id = fired["weapon_id"]
    current = int(WEAPON_DEFS[weapon_id].damage)

    fixture = tmp_path / f"{weapon_id}_noop.json"
    fixture.write_text(json.dumps({
        "weapon_id": weapon_id,
        "case": "noop",
        "bridge_state": bridge_state,
    }))

    # damage = current value → override is semantically a no-op.
    result = board_extractor.verify_observable_change(
        fixture, {"weapon_id": weapon_id, "damage": current},
    )
    assert result.observable_change is False, result.reason
