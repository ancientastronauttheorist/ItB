"""P3-3: schema + round-trip tests for the Python override loader.

The loader is the last thing between a curated ``data/weapon_overrides.json``
and the Rust solve. Its job is (a) fail loudly on malformed entries, (b)
strip free-form metadata before it crosses the FFI boundary, and (c) put
base/runtime entries in the right bridge-JSON keys.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.solver.weapon_overrides import (
    OverrideSchemaError,
    apply_runtime,
    clear_runtime,
    inject_into_bridge,
    load_base_overrides,
    stage_candidates,
)


def test_load_missing_file_returns_empty(tmp_path):
    assert load_base_overrides(tmp_path / "nope.json") == []


def test_load_strips_free_form_metadata(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([
        {
            "weapon_id": "Ranged_Defensestrike",
            "damage": 1,
            "note": "Vision disagreed — see mismatches log 2026-04-18",
            "source_mismatch_ts": "2026-04-18T00:46:22+00:00",
            "reviewer": "aircow",
        }
    ]))
    loaded = load_base_overrides(p)
    assert loaded == [{"weapon_id": "Ranged_Defensestrike", "damage": 1}]


def test_load_rejects_unknown_flag_name(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([
        {"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE", "NOT_A_FLAG"]}
    ]))
    with pytest.raises(OverrideSchemaError, match="unknown flag names"):
        load_base_overrides(p)


def test_load_rejects_entry_with_no_patch(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([{"weapon_id": "Prime_Punchmech", "note": "x"}]))
    with pytest.raises(OverrideSchemaError, match="no patchable fields"):
        load_base_overrides(p)


def test_load_rejects_non_array_top_level(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps({"weapon_id": "Prime_Punchmech", "damage": 1}))
    with pytest.raises(OverrideSchemaError, match="top-level must be a JSON array"):
        load_base_overrides(p)


def test_inject_splits_base_and_runtime():
    bd: dict = {}
    base = [{"weapon_id": "Prime_Punchmech", "damage": 3}]
    runtime = [{"weapon_id": "Prime_Punchmech", "damage": 99}]
    inject_into_bridge(bd, base=base, runtime=runtime)
    assert bd["weapon_overrides"] == base
    assert bd["weapon_overrides_runtime"] == runtime


def test_inject_empty_leaves_bridge_untouched():
    bd: dict = {}
    inject_into_bridge(bd)
    assert "weapon_overrides" not in bd
    assert "weapon_overrides_runtime" not in bd


def test_python_runtime_overlay_patches_get_weapon_def():
    from src.model.weapons import get_weapon_def
    try:
        stock = get_weapon_def("Prime_Punchmech")
        assert stock.damage == 2 and not stock.fire
        bd = {
            "weapon_overrides": [{"weapon_id": "Prime_Punchmech", "damage": 7}],
            "weapon_overrides_runtime": [
                {"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE"]},
                # Runtime wins the damage field on conflict.
                {"weapon_id": "Prime_Punchmech", "damage": 99},
            ],
        }
        apply_runtime(bd)
        patched = get_weapon_def("Prime_Punchmech")
        assert patched.damage == 99, "runtime layer should win damage"
        assert patched.fire is True, "flag from runtime layer applied"
        # Unrelated weapon untouched.
        assert get_weapon_def("Brute_Tankmech").damage == 1
    finally:
        clear_runtime()
    # Overlay reverts after clear.
    assert get_weapon_def("Prime_Punchmech").damage == 2


def test_python_runtime_overlay_affects_simulate_weapon():
    """End-to-end parity: Python simulate_weapon damage reflects overlay."""
    from src.model.board import Board
    from src.solver.simulate import simulate_weapon

    def _board_with_mech_and_enemy(dmg: int):
        # Build a minimal bridge dict then construct a Board from it.
        bridge = {
            "grid_power": 7, "turn": 0, "total_turns": 5,
            "tiles": [{"x": x, "y": y, "terrain": "ground"}
                      for x in range(8) for y in range(8)],
            "units": [
                {"uid": 1, "type": "PunchMech", "x": 3, "y": 3,
                 "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                 "weapons": ["Prime_Punchmech"], "move": 3, "active": True},
                {"uid": 2, "type": "Firefly1", "x": 4, "y": 3,
                 "hp": 5, "max_hp": 5, "team": 6,
                 "weapons": ["FireflyAtk1"]},
            ],
            "spawning_tiles": [],
        }
        return Board.from_bridge_data(bridge)

    # Stock: Titan Fist does 2 damage → enemy drops from 5 to 3.
    clear_runtime()
    board = _board_with_mech_and_enemy(2)
    mech = next(u for u in board.units if u.uid == 1)
    simulate_weapon(board, mech, "Prime_Punchmech", 4, 3)
    enemy = next(u for u in board.units if u.uid == 2)
    assert enemy.hp == 3, "stock damage baseline"

    # Override damage to 4 → enemy should drop to 1.
    try:
        apply_runtime({"weapon_overrides": [
            {"weapon_id": "Prime_Punchmech", "damage": 4},
        ]})
        board2 = _board_with_mech_and_enemy(4)
        mech2 = next(u for u in board2.units if u.uid == 1)
        simulate_weapon(board2, mech2, "Prime_Punchmech", 4, 3)
        enemy2 = next(u for u in board2.units if u.uid == 2)
        assert enemy2.hp == 1, "overlay damage took effect"
    finally:
        clear_runtime()


def test_stage_skips_non_stageable_fields(tmp_path):
    # push_arrows / footprint_size have no deterministic Rust patch.
    p = tmp_path / "staged.jsonl"
    mismatches = [
        {"weapon_id": "Science_Gravwell", "display_name": "Grav Well",
         "field": "push_arrows", "rust_value": {}, "vision_value": 0,
         "severity": "low", "confidence": 0.9},
        {"weapon_id": "Prime_Punchmech", "display_name": "Titan Fist",
         "field": "footprint_size", "rust_value": "[1,1]", "vision_value": 4,
         "severity": "medium", "confidence": 0.9},
    ]
    staged = stage_candidates(mismatches, run_id="r1", path=p)
    assert staged == []
    assert not p.exists()


def test_stage_damage_mismatch_writes_candidate(tmp_path):
    p = tmp_path / "staged.jsonl"
    mismatches = [
        # Live-smoke-test finding that already sits in
        # data/weapon_def_mismatches.jsonl.
        {"weapon_id": "Ranged_Defensestrike",
         "display_name": "Cluster Artillery", "field": "damage",
         "rust_value": 0, "vision_value": 1,
         "severity": "high", "confidence": 1.0},
    ]
    staged = stage_candidates(mismatches, run_id="r1", path=p)
    assert len(staged) == 1
    cand = staged[0]
    assert cand["weapon_id"] == "Ranged_Defensestrike"
    assert cand["damage"] == 1
    assert cand["source_run_id"] == "r1"
    # File appended with one JSON line.
    lines = p.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["damage"] == 1


def test_stage_respects_severity_threshold(tmp_path):
    # A medium-severity damage mismatch is ignored under the default
    # "high" threshold but accepted if the caller lowers the bar.
    p = tmp_path / "staged.jsonl"
    mm = [{"weapon_id": "Prime_Punchmech", "display_name": "Titan Fist",
           "field": "damage", "rust_value": 2, "vision_value": 3,
           "severity": "medium", "confidence": 1.0}]
    assert stage_candidates(mm, run_id="r1", path=p) == []
    staged = stage_candidates(mm, run_id="r1", path=p,
                              severity_threshold="medium")
    assert len(staged) == 1


def _prime_cli_env(monkeypatch, tmp_path, *, with_board_for: str | None = None):
    """Redirect the CLI's file paths into tmp_path so tests don't
    mutate data/ or tests/ on disk.

    When ``with_board_for`` is set, the board-lookup helper returns a
    stub path for that weapon_id and None for everything else.
    """
    from src.solver import weapon_overrides as wo
    from src.loop import commands as cmds

    staged = tmp_path / "staged.jsonl"
    overrides = tmp_path / "weapon_overrides.json"

    monkeypatch.setattr(wo, "DEFAULT_STAGED_PATH", staged)
    monkeypatch.setattr(wo, "DEFAULT_OVERRIDES_PATH", overrides)

    stub_board = tmp_path / f"{with_board_for or 'none'}_stub.json"
    if with_board_for:
        stub_board.write_text("{}")

    def _lookup(wid: str):
        if with_board_for and wid == with_board_for:
            return stub_board
        return None

    monkeypatch.setattr(cmds, "_regression_board_for_weapon", _lookup)
    return staged, overrides


def test_review_list_empty(monkeypatch, tmp_path):
    from src.loop.commands import cmd_review_overrides
    _prime_cli_env(monkeypatch, tmp_path)
    result = cmd_review_overrides("list")
    assert result["staged"] == []


def test_review_accept_refuses_without_regression_board(monkeypatch, tmp_path):
    from src.loop.commands import cmd_review_overrides
    staged, overrides = _prime_cli_env(monkeypatch, tmp_path)
    staged.write_text(json.dumps({
        "weapon_id": "Ranged_Defensestrike", "damage": 1,
        "note": "test", "source_run_id": "r1",
    }) + "\n")
    result = cmd_review_overrides("accept", 0)
    assert "error" in result
    assert "regression board" in result["error"]
    # Nothing promoted; staged still present.
    assert staged.exists()
    assert not overrides.exists()


def test_review_accept_with_regression_board_promotes(monkeypatch, tmp_path):
    from src.loop.commands import cmd_review_overrides
    staged, overrides = _prime_cli_env(
        monkeypatch, tmp_path, with_board_for="Ranged_Defensestrike"
    )
    staged.write_text(json.dumps({
        "weapon_id": "Ranged_Defensestrike", "damage": 1,
        "note": "test", "source_run_id": "r1",
        "source_mismatch": {"field": "damage", "rust_value": 0},
    }) + "\n")
    result = cmd_review_overrides("accept", 0)
    assert result.get("action") == "accepted"
    loaded = json.loads(overrides.read_text())
    assert loaded[0]["weapon_id"] == "Ranged_Defensestrike"
    assert loaded[0]["damage"] == 1
    # Staged entry consumed.
    assert not staged.exists() or staged.read_text().strip() == ""


def test_review_accept_force_bypasses_regression_board(monkeypatch, tmp_path):
    from src.loop.commands import cmd_review_overrides
    staged, overrides = _prime_cli_env(monkeypatch, tmp_path)
    staged.write_text(json.dumps({
        "weapon_id": "Prime_Punchmech", "damage": 3,
        "note": "force path", "source_run_id": "r1",
    }) + "\n")
    result = cmd_review_overrides("accept", 0, force=True)
    assert result["action"] == "accepted"
    assert result["forced"] is True
    assert overrides.exists()


def test_review_reject_drops_entry(monkeypatch, tmp_path):
    from src.loop.commands import cmd_review_overrides
    staged, _ = _prime_cli_env(monkeypatch, tmp_path)
    staged.write_text("\n".join([
        json.dumps({"weapon_id": "A", "damage": 1,
                    "note": "x", "source_run_id": "r1"}),
        json.dumps({"weapon_id": "B", "damage": 2,
                    "note": "y", "source_run_id": "r1"}),
    ]) + "\n")
    result = cmd_review_overrides("reject", 0)
    assert result["action"] == "rejected"
    assert result["weapon_id"] == "A"
    remaining = [json.loads(l) for l in staged.read_text().splitlines() if l]
    assert len(remaining) == 1
    assert remaining[0]["weapon_id"] == "B"


def test_submit_research_stages_candidate_from_high_mismatch(tmp_path,
                                                             monkeypatch):
    """End-to-end: orchestrator.submit_research → stage_candidates."""
    from src.loop.session import RunSession
    from src.research import orchestrator
    from src.solver import weapon_overrides as wo

    staged_path = tmp_path / "staged.jsonl"
    mismatches_path = tmp_path / "mismatches.jsonl"
    monkeypatch.setattr(wo, "DEFAULT_STAGED_PATH", staged_path)

    session = RunSession(run_id="r-stage-1", squad="rift_walkers")
    session.enqueue_research("Cluster_Artillery", None, current_turn=0,
                             kind="mech_weapon", slot=1)
    entry = session.research_queue[0]
    entry["research_id"] = "rsid-1"

    # Vision payload that will trip the damage comparator against
    # Ranged_Defensestrike (rust damage=0, vision reports damage=1).
    weapon_preview = {
        "name": "Cluster Artillery",
        "description": "",
        "damage": 1,
        "footprint_tiles": [[0, 0]],
        "push_directions": [],
        "confidence": 1.0,
    }
    out = orchestrator.submit_research(
        session, "rsid-1",
        {"weapon_preview": weapon_preview},
        run_id="r-stage-1",
        mismatches_path=mismatches_path,
        wiki_fallback=False,
    )
    assert out["mismatches"], "comparator should have emitted the damage mismatch"
    assert out["staged_candidates"], "high-severity damage mismatch should stage"
    cand = out["staged_candidates"][0]
    assert cand["weapon_id"] == "Ranged_Defensestrike"
    assert cand["damage"] == 1
    # File hit.
    lines = staged_path.read_text().splitlines()
    assert any('"Ranged_Defensestrike"' in line for line in lines)


def test_inject_round_trip_through_rust_applies_and_audits():
    """End-to-end: loader → inject → itb_solver.solve → applied_overrides."""
    itb_solver = pytest.importorskip("itb_solver")
    bd = {
        "grid_power": 7, "turn": 0, "total_turns": 5,
        "tiles": [{"x": x, "y": y, "terrain": "ground"}
                  for x in range(8) for y in range(8)],
        "units": [
            {"uid": 1, "type": "PunchMech", "x": 3, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "weapons": ["Prime_Punchmech"], "move": 3, "active": True},
            {"uid": 2, "type": "Firefly1", "x": 5, "y": 3,
             "hp": 2, "max_hp": 2, "team": 6,
             "weapons": ["FireflyAtk1"], "queued_target": [3, 3]},
        ],
        "spawning_tiles": [],
    }
    inject_into_bridge(
        bd,
        base=[{"weapon_id": "Prime_Punchmech", "damage": 5, "note": "dropped"}],
        runtime=[{"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE"]}],
    )
    out = json.loads(itb_solver.solve(json.dumps(bd), 2.0))
    applied = out.get("applied_overrides", [])
    sources = [(e["weapon_id"], e["source"], tuple(e["fields"])) for e in applied]
    assert ("Prime_Punchmech", "base", ("damage",)) in sources
    assert ("Prime_Punchmech", "runtime", ("flags_set",)) in sources
