"""Orchestrator glue tests — begin_research + submit_research.

Simulates the full between-turn flow with a mocked ``grid_to_mcp``
and the existing capture/vision/comparator modules unmocked (we
want end-to-end JSON round-trips). Covers:

1. ``begin_research`` picks the first pending entry whose type is on
   the live board and returns a well-formed plan + prompts.
2. When no pending entry has a live target, returns None and bumps
   ``attempts`` on each skipped entry.
3. ``submit_research`` parses Vision JSONs, stores them under the
   entry's ``result``, and transitions status to done / failed based
   on confidence.
4. End-to-end: queue has one entry → begin → submit clean Vision
   JSON → queue is drained, result is stored.
5. Comparator fires when ``weapon_preview`` is among the responses.
"""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from src.loop.session import RunSession
from src.research import orchestrator, capture


def _fake_board(units):
    return SimpleNamespace(units=units)


def _fake_unit(type_name: str, x: int, y: int, hp: int = 3, is_mech: bool = False):
    return SimpleNamespace(type=type_name, x=x, y=y, hp=hp, is_mech=is_mech)


def _ui_regions():
    raw = {
        "reference_window": {"x": 200, "y": 137, "width": 1280, "height": 748},
        "regions": {
            "name_tag": {"bounds": [178, 558, 410, 603]},
            "unit_status": {"bounds": [178, 618, 442, 728]},
            "weapon_preview": {"bounds": [480, 355, 610, 720]},
            "terrain_tooltip": {"bounds": [980, 635, 1225, 725]},
        },
        "neutral_hover": {"coordinate": [1100, 100]},
    }
    from src.capture.detect_grid import WindowInfo
    return capture.resolve_ui_regions(
        raw,
        current_window=WindowInfo(x=200, y=137, width=1280, height=748),
    )


# ── begin_research ───────────────────────────────────────────────────────────


def test_begin_research_finds_unit_and_builds_plan(monkeypatch):
    monkeypatch.setattr(orchestrator, "grid_to_mcp",
                        lambda x, y: (740, 366))
    s = RunSession()
    s.enqueue_research("FireflyBoss", None, current_turn=1)
    board = _fake_board([_fake_unit("FireflyBoss", 3, 2)])

    out = orchestrator.begin_research(s, board, ui=_ui_regions())
    assert out is not None
    assert out["target"]["type"] == "FireflyBoss"
    assert out["target"]["kind"] == "enemy"
    assert out["target"]["target_mcp"] == [740, 366]
    # Plan carries a computer_batch sequence + crop regions.
    actions = [a["action"] for a in out["plan"]["batch"]]
    assert actions == ["mouse_move", "wait", "left_click", "wait", "screenshot"]
    assert {c["name"] for c in out["plan"]["crops"]} == {"name_tag", "unit_status"}
    # Prompts shipped so the harness doesn't round-trip for them.
    assert "name_tag" in out["prompts"]
    assert "unit_status" in out["prompts"]
    # Entry transitioned to in_progress with a research_id.
    entry = s.research_queue[0]
    assert entry["status"] == "in_progress"
    assert entry["research_id"] == out["research_id"]


def test_begin_research_returns_none_when_no_target_on_board(monkeypatch):
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (0, 0))
    s = RunSession()
    s.enqueue_research("FireflyBoss", None, current_turn=1)
    board = _fake_board([_fake_unit("Hornet1", 3, 2)])  # different type

    out = orchestrator.begin_research(s, board, ui=_ui_regions())
    assert out is None
    # Skipped entries still bump attempts so we can cap retry budget later.
    assert s.research_queue[0]["attempts"] == 1
    assert s.research_queue[0]["status"] == "pending"


def test_begin_research_ignores_dead_units(monkeypatch):
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (0, 0))
    s = RunSession()
    s.enqueue_research("Hornet1", None, current_turn=1)
    board = _fake_board([_fake_unit("Hornet1", 3, 2, hp=0)])  # dead

    assert orchestrator.begin_research(s, board, ui=_ui_regions()) is None


def test_begin_research_marks_kind_mech_for_mech_units(monkeypatch):
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (694, 400))
    s = RunSession()
    # Hypothetical: a mech whose type is unknown (imagine a new squad).
    s.enqueue_research("ExperimentMech", None, current_turn=1)
    board = _fake_board([_fake_unit("ExperimentMech", 3, 3, is_mech=True)])
    out = orchestrator.begin_research(s, board, ui=_ui_regions())
    assert out["target"]["kind"] == "mech"


# ── submit_research ──────────────────────────────────────────────────────────


def _begin_for(session, board, monkeypatch):
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (740, 366))
    return orchestrator.begin_research(session, board, ui=_ui_regions())


def test_submit_research_parses_and_marks_done(monkeypatch):
    s = RunSession()
    s.enqueue_research("FireflyBoss", None, current_turn=1)
    board = _fake_board([_fake_unit("FireflyBoss", 3, 2)])
    plan = _begin_for(s, board, monkeypatch)
    rid = plan["research_id"]

    responses = {
        "name_tag": '{"name": "Firefly Leader", "hp": 6, "move": null, '
                    '"class_icons": ["damages_mountain", "destroys_buildings"]}',
        "unit_status": '{"kind": "enemy", "pilot_name": null, '
                       '"weapon_slot_count": 0}',
    }
    result = orchestrator.submit_research(s, rid, responses)
    assert result["status"] == "done"
    # Parsed crops ended up on the entry's result.
    entry = s.research_queue[0]
    assert entry["status"] == "done"
    assert entry["result"]["parsed"]["name_tag"]["name"] == "Firefly Leader"


def test_submit_research_marks_failed_on_all_low_confidence(monkeypatch):
    s = RunSession()
    s.enqueue_research("Ghost", None, current_turn=1)
    board = _fake_board([_fake_unit("Ghost", 3, 2)])
    plan = _begin_for(s, board, monkeypatch)
    rid = plan["research_id"]

    # Give Vision garbage → every parser returns confidence 0.
    responses = {"name_tag": "garbage", "unit_status": "nope"}
    result = orchestrator.submit_research(s, rid, responses)
    assert result["status"] == "failed"
    assert s.research_queue[0]["status"] == "failed"


def test_submit_research_unknown_id_returns_error():
    s = RunSession()
    out = orchestrator.submit_research(s, "deadbeef", {})
    assert "error" in out


def test_submit_research_runs_comparator_when_weapon_preview_present(monkeypatch, tmp_path: Path):
    s = RunSession()
    s.enqueue_research("TestMech", None, current_turn=1)
    board = _fake_board([_fake_unit("TestMech", 3, 3, is_mech=True)])
    plan = _begin_for(s, board, monkeypatch)
    rid = plan["research_id"]

    mismatches_path = tmp_path / "mm.jsonl"
    # Claim the weapon is Vice Fist but with wrong damage (should flag).
    responses = {
        "name_tag": '{"name": "TestMech", "hp": 3, "move": 5, "class_icons": []}',
        "weapon_preview": (
            '{"name": "Vice Fist", "weapon_class": "Prime Class Weapon", '
            '"description": "Grab and toss.", '
            '"damage": 9, "footprint_tiles": [[1,0]], '
            '"push_directions": ["west"], "upgrades": []}'
        ),
    }
    result = orchestrator.submit_research(
        s, rid, responses,
        run_id="demo", mismatches_path=mismatches_path,
    )
    # Comparator caught the damage=9 vs sim=1 mismatch.
    assert result["mismatches"], result
    assert any(m["field"] == "damage" for m in result["mismatches"])
    # JSONL line written for the run.
    assert mismatches_path.exists()


def test_submit_research_no_comparator_call_without_weapon_preview(monkeypatch, tmp_path: Path):
    s = RunSession()
    s.enqueue_research("FireflyBoss", None, current_turn=1)
    board = _fake_board([_fake_unit("FireflyBoss", 3, 2)])
    plan = _begin_for(s, board, monkeypatch)
    rid = plan["research_id"]

    mm_path = tmp_path / "mm.jsonl"
    responses = {
        "name_tag": '{"name": "Firefly Leader", "hp": 6, "move": null, '
                    '"class_icons": []}',
    }
    result = orchestrator.submit_research(
        s, rid, responses, mismatches_path=mm_path,
    )
    assert result["mismatches"] == []
    assert not mm_path.exists()


# ── end-to-end flow ──────────────────────────────────────────────────────────


def test_queue_drains_on_clean_end_to_end_run(monkeypatch):
    """Simulates the full between-turn flow: enqueue → begin → submit."""
    s = RunSession(current_mission="M1")
    s.enqueue_research("FireflyBoss", None, current_turn=1)
    s.enqueue_research("Hornet1", None, current_turn=1)
    board = _fake_board([
        _fake_unit("FireflyBoss", 3, 2),
        _fake_unit("Hornet1", 4, 4),
    ])
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (0, 0))

    # First pop
    plan1 = orchestrator.begin_research(s, board, ui=_ui_regions())
    assert plan1["target"]["type"] == "FireflyBoss"
    orchestrator.submit_research(s, plan1["research_id"], {
        "name_tag": '{"name": "Firefly Leader", "hp": 6}',
    })

    # Second pop — first entry done so picker skips it.
    plan2 = orchestrator.begin_research(s, board, ui=_ui_regions())
    assert plan2["target"]["type"] == "Hornet1"
    orchestrator.submit_research(s, plan2["research_id"], {
        "name_tag": '{"name": "Hornet", "hp": 2}',
    })

    # Third pop — queue drained.
    assert orchestrator.begin_research(s, board, ui=_ui_regions()) is None

    # Both entries status == done.
    assert all(e["status"] == "done" for e in s.research_queue)
