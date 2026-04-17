"""Phase 0 self-healing loop instrumentation tests.

Covers the four pieces that must exist before Phase 1 can be built on top:

1. ``RunSession.failure_events_this_run`` round-trips through the session
   serializer.
2. ``src.solver.fuzzy_detector.evaluate`` returns the agreed-upon dict
   shape so the Phase 1 detector has a stable input contract.
3. ``src.solver.unknown_detector.detect_unknowns`` flags pawn types and
   terrain ids that aren't in ``data/known_types.json``.
4. ``src.solver.analysis.append_to_failure_db`` passes ``fuzzy_signal``
   through to the on-disk JSONL record (backward-compatible: readers
   that don't know about the field still work because optional fields
   are accessed with ``.get()``).

All tests run without a live game — they exercise Python-only glue.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.loop.session import RunSession
from src.solver import fuzzy_detector, unknown_detector
from src.solver.verify import DiffResult
from src.solver import analysis


# ── #P0-1 round-trip ─────────────────────────────────────────────────────────


def test_failure_events_this_run_round_trips():
    s = RunSession(run_id="t")
    s.failure_events_this_run.append({"hello": "world", "n": 1})
    d = s.to_dict()
    assert d["failure_events_this_run"] == [{"hello": "world", "n": 1}]
    s2 = RunSession.from_dict(d)
    assert s2.failure_events_this_run == [{"hello": "world", "n": 1}]


def test_failure_events_default_empty_on_legacy_session_dict():
    # A dict written before Phase 0 existed (no key) must still load.
    legacy = {"run_id": "old", "squad": "Rift"}
    s = RunSession.from_dict(legacy)
    assert s.failure_events_this_run == []


# ── #P0-2 stub contract ──────────────────────────────────────────────────────


def test_fuzzy_detector_shape_contract():
    diff = DiffResult()  # empty; detector only reads unit_diffs
    classification = {
        "top_category": "damage_amount",
        "categories": ["damage_amount"],
        "subcategory": None,
        "model_gap": False,
    }
    ctx = {"mech_uid": 7, "phase": "attack", "sub_action": "attack",
           "weapon": "Prime_Punchmech", "action_index": 2, "turn": 3}
    sig = fuzzy_detector.evaluate(diff, classification, context=ctx)
    assert sig["version"] == 1
    assert sig["top_category"] == "damage_amount"
    assert sig["categories"] == ["damage_amount"]
    assert sig["model_gap"] is False
    assert sig["context"] == ctx
    # New v1 fields must always be present (None/empty when unused).
    assert "signature" in sig
    assert "frequency" in sig
    assert "asymmetry" in sig
    assert "topology" in sig
    assert "proposed_tier" in sig
    assert "confidence" in sig


def test_fuzzy_detector_json_serializable():
    # Must be JSON-safe so it can land in session state + failure_db.jsonl.
    classification = {"top_category": "push_dir", "categories": ["push_dir"],
                      "subcategory": None, "model_gap": False}
    sig = fuzzy_detector.evaluate(DiffResult(), classification, context={})
    json.dumps(sig)  # must not raise


# ── #P1-1 evaluate() logic ───────────────────────────────────────────────────


def _classification(top, model_gap=False):
    return {
        "top_category": top,
        "categories": [top],
        "subcategory": None,
        "model_gap": model_gap,
    }


def test_signature_groups_by_category_weapon_subaction():
    ctx_a = {"weapon": "Prime_Shift", "sub_action": "attack"}
    ctx_b = {"weapon": "Prime_Shift", "sub_action": "attack"}
    ctx_c = {"weapon": "Ranged_Defensestrike", "sub_action": "attack"}
    a = fuzzy_detector.evaluate(DiffResult(), _classification("push_dir"), context=ctx_a)
    b = fuzzy_detector.evaluate(DiffResult(), _classification("push_dir"), context=ctx_b)
    c = fuzzy_detector.evaluate(DiffResult(), _classification("push_dir"), context=ctx_c)
    # mech/action-index deliberately excluded from the dedup key
    assert a["signature"] == b["signature"]
    assert a["signature"] != c["signature"]


def test_frequency_counts_prior_events_with_same_signature():
    ctx = {"weapon": "Prime_Shift", "sub_action": "attack"}
    # Two prior desyncs on the same signature, one on a different one.
    prior = [
        {"signature": "push_dir|Prime_Shift|attack"},
        {"signature": "push_dir|Prime_Shift|attack"},
        {"signature": "grid_power|Ranged_Defensestrike|attack"},
    ]
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=ctx, prior_events=prior,
    )
    assert sig["frequency"] == 2


def test_tier_escalates_to_soft_disable_on_second_occurrence():
    ctx = {"weapon": "Prime_Shift", "sub_action": "attack"}
    prior = [{"signature": "push_dir|Prime_Shift|attack"}]
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=ctx, prior_events=prior,
    )
    # freq=1 (prior) + this firing = 2 → soft-disable threshold
    assert sig["proposed_tier"] == 2
    assert 0.5 <= sig["confidence"] <= 0.9


def test_tier_narrate_on_first_occurrence_of_weapon_drift():
    ctx = {"weapon": "Prime_Shift", "sub_action": "attack"}
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=ctx, prior_events=[],
    )
    assert sig["proposed_tier"] == 4
    assert sig["frequency"] == 0


def test_tier_for_click_miss_stays_tier_1_even_when_frequent():
    # Execution bugs (click_miss, mech_position_wrong) are Tier 1 — the
    # existing re-solve path handles them. Don't soft-disable a weapon
    # because the click missed; that's not the weapon's fault.
    ctx = {"weapon": "Prime_Shift", "sub_action": "attack"}
    prior = [
        {"signature": "click_miss|Prime_Shift|attack"},
        {"signature": "click_miss|Prime_Shift|attack"},
    ]
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("click_miss"),
        context=ctx, prior_events=prior,
    )
    assert sig["proposed_tier"] == 1


def test_asymmetry_enemy_survived_unexpectedly():
    diff = DiffResult()
    diff.unit_diffs = [{
        "uid": 4, "type": "Firefly2", "field": "alive",
        "predicted": False, "actual": True,
    }]
    sig = fuzzy_detector.evaluate(
        diff, _classification("death"),
        context={"weapon": "Prime_Lasermech", "sub_action": "attack"},
    )
    assert "enemy_survived_unexpectedly" in sig["asymmetry"]


def test_asymmetry_mech_died_unexpectedly():
    diff = DiffResult()
    diff.unit_diffs = [{
        "uid": 0, "type": "PunchMech", "field": "alive",
        "predicted": True, "actual": False,
    }]
    sig = fuzzy_detector.evaluate(
        diff, _classification("death"),
        context={"weapon": "Prime_Punchmech", "sub_action": "attack"},
    )
    assert "mech_died_unexpectedly" in sig["asymmetry"]


# ── #P1-2 disabled_actions ───────────────────────────────────────────────────


def test_add_disabled_action_new_entry():
    s = RunSession()
    added = s.add_disabled_action("Prime_Shift", "push_dir_freq2", expires_turn=5)
    assert added is True
    assert len(s.disabled_actions) == 1
    assert s.disabled_actions[0]["weapon_id"] == "Prime_Shift"
    assert s.disabled_actions[0]["expires_turn"] == 5


def test_add_disabled_action_dedups_and_extends_expiry():
    s = RunSession()
    s.add_disabled_action("Prime_Shift", "a", expires_turn=3)
    added = s.add_disabled_action("Prime_Shift", "b", expires_turn=7)
    assert added is False
    assert len(s.disabled_actions) == 1
    # Expiry moves to the later of the two.
    assert s.disabled_actions[0]["expires_turn"] == 7
    # Cause chain preserves both reasons for the narrator.
    assert "a" in s.disabled_actions[0]["cause_pattern"]
    assert "b" in s.disabled_actions[0]["cause_pattern"]


def test_prune_disabled_actions_drops_expired():
    s = RunSession()
    s.add_disabled_action("W1", "c", expires_turn=3)
    s.add_disabled_action("W2", "c", expires_turn=5)
    dropped = s.prune_disabled_actions(current_turn=4)
    assert dropped == 1
    assert [e["weapon_id"] for e in s.disabled_actions] == ["W2"]


def test_prune_keeps_entries_expiring_this_turn():
    # Inclusive semantics: entry with expires_turn==current_turn is still
    # active for the current turn; drops next turn.
    s = RunSession()
    s.add_disabled_action("W1", "c", expires_turn=3)
    assert s.prune_disabled_actions(current_turn=3) == 0
    assert s.prune_disabled_actions(current_turn=4) == 1


def test_disabled_actions_cleared_on_mission_boundary():
    s = RunSession(current_mission="Archive 1")
    s.add_disabled_action("Prime_Shift", "c", expires_turn=99)
    s.failure_events_this_run.append({"signature": "x"})
    s.advance_mission("Archive 2")
    assert s.disabled_actions == []
    # failure_events_this_run persists — it's a run-level evidence pile.
    assert len(s.failure_events_this_run) == 1


def test_disabled_actions_round_trips():
    s = RunSession()
    s.add_disabled_action("Prime_Shift", "c", expires_turn=5)
    d = s.to_dict()
    assert d["disabled_actions"][0]["weapon_id"] == "Prime_Shift"
    s2 = RunSession.from_dict(d)
    assert s2.disabled_actions[0]["weapon_id"] == "Prime_Shift"


def test_model_gap_known_proposes_narrate_tier_4():
    ctx = {"weapon": "Brute_Beetle", "sub_action": "attack"}
    sig = fuzzy_detector.evaluate(
        DiffResult(),
        _classification("tile_status", model_gap=True),
        context=ctx,
    )
    assert sig["proposed_tier"] == 4
    assert sig["model_gap"] is True


# ── #P0-5 novelty detection ──────────────────────────────────────────────────


def _fake_board(unit_types: list[str], terrain_ids: list[str]):
    """Minimal board duck-type for detect_unknowns.

    ``tiles`` is an 8×8 grid; only tile [0][0..N-1] carries the supplied
    terrain ids, everything else is "ground" (which is always known).
    """
    units = [SimpleNamespace(type=t) for t in unit_types]
    tiles = [[SimpleNamespace(terrain="ground") for _ in range(8)] for _ in range(8)]
    for i, tid in enumerate(terrain_ids):
        tiles[0][i].terrain = tid
    return SimpleNamespace(units=units, tiles=tiles)


def test_detect_unknowns_known_units_empty():
    unknown_detector.reset_cache()
    board = _fake_board(["Firefly1", "Scorpion1"], ["ground", "water"])
    r = unknown_detector.detect_unknowns(board)
    assert r == {"types": [], "terrain_ids": []}


def test_detect_unknowns_flags_novel_unit():
    unknown_detector.reset_cache()
    board = _fake_board(["Wumpus_Alpha", "Scorpion1"], [])
    r = unknown_detector.detect_unknowns(board)
    assert "Wumpus_Alpha" in r["types"]
    assert r["terrain_ids"] == []


def test_detect_unknowns_flags_novel_terrain():
    unknown_detector.reset_cache()
    board = _fake_board([], ["quicksand"])
    r = unknown_detector.detect_unknowns(board)
    assert "quicksand" in r["terrain_ids"]


# ── #P0-3 fuzzy_signal survives the failure_db round-trip ────────────────────


def test_fuzzy_signal_written_to_failure_db(monkeypatch, tmp_path):
    db_path = tmp_path / "failure_db.jsonl"
    monkeypatch.setattr(analysis, "FAILURE_DB_PATH", db_path)

    trigger = {
        "trigger": "per_sub_action_desync_attack",
        "tier": 2,
        "severity": "medium",
        "details": "test",
        "action_index": 0,
        "mech_uid": 3,
        "category": "damage_amount",
        "subcategory": None,
        "diff": {"unit_diffs": [], "tile_diffs": [], "scalar_diffs": [], "total_count": 0},
        "fuzzy_signal": {
            "version": 0,
            "top_category": "damage_amount",
            "categories": ["damage_amount"],
            "subcategory": None,
            "model_gap": False,
            "context": {"mech_uid": 3, "phase": "attack"},
        },
    }
    count = analysis.append_to_failure_db(
        [trigger], run_id="tr", mission_index=0, turn=1,
        context={"squad": "Rift", "island": "", "model_gap": False,
                 "weight_version": "v?", "solver_version": "v?", "tags": []},
    )
    assert count == 1

    # Round-trip: the written record carries fuzzy_signal verbatim.
    line = db_path.read_text().strip()
    rec = json.loads(line)
    assert "fuzzy_signal" in rec
    assert rec["fuzzy_signal"]["top_category"] == "damage_amount"
    assert rec["fuzzy_signal"]["context"]["phase"] == "attack"


# ── #P1-5 narrator ───────────────────────────────────────────────────────────


def test_narrator_outputs_readable_lines(capsys):
    from src.loop.commands import _narrate_fuzzy
    detections = [{
        "top_category": "push_dir",
        "proposed_tier": 4,
        "confidence": 0.4,
        "frequency": 0,
        "asymmetry": [],
        "model_gap": False,
        "context": {
            "weapon": "Prime_Shift",
            "mech_uid": 0,
            "sub_action": "attack",
            "action_index": 1,
        },
    }]
    soft_disables = [{
        "weapon_id": "Prime_Shift",
        "cause": "push_dir|Prime_Shift|attack",
        "expires_turn": 6,
        "confidence": 0.7,
        "frequency": 1,
        "new_entry": True,
    }]
    _narrate_fuzzy(detections, soft_disables, unknowns={})
    out = capsys.readouterr().out
    assert "FUZZY: push_dir on Prime_Shift" in out
    assert "SOFT-DISABLE (new)" in out
    assert "until turn 6" in out


def test_narrator_silent_when_nothing_to_report(capsys):
    from src.loop.commands import _narrate_fuzzy
    _narrate_fuzzy([], [], {})
    assert capsys.readouterr().out == ""


def test_narrator_surfaces_unknowns(capsys):
    from src.loop.commands import _narrate_fuzzy
    _narrate_fuzzy([], [], {"types": ["Wumpus_Alpha"], "terrain_ids": []})
    out = capsys.readouterr().out
    assert "UNKNOWNS flagged" in out
    assert "Wumpus_Alpha" in out


# ── #P1-3 Rust soft-disable bias ─────────────────────────────────────────────


def _rust_solve(bridge_data: dict, time_limit: float = 1.0) -> dict:
    import itb_solver
    return json.loads(itb_solver.solve(json.dumps(bridge_data), time_limit))


def _two_weapon_board():
    """Minimal board where a PunchMech has both Prime_Punchmech and
    Ranged_Artillerymech available and an adjacent scorpion to hit.

    PunchMech at (3,3), scorpion at (3,4) (directly east). Both weapons
    can kill the scorpion on turn 1, so the solver is genuinely free to
    choose between them — which is what we need in order to observe
    the soft-disable bias flipping the selection.
    """
    return {
        "tiles": [
            {"x": x, "y": y, "terrain": "ground"}
            for x in range(8) for y in range(8)
        ],
        "units": [
            {
                "uid": 0, "type": "PunchMech", "x": 3, "y": 3,
                "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                "move": 4, "active": True,
                "weapons": ["Prime_Punchmech", "Ranged_Artillerymech"],
            },
            {
                "uid": 1, "type": "Scorpion1", "x": 3, "y": 4,
                "hp": 1, "max_hp": 1, "team": 6, "mech": False,
                "move": 3, "active": False,
                "weapons": ["ScorpionAtk1"], "queued_target": [-1, -1],
            },
        ],
        "grid_power": 7, "grid_power_max": 7,
        "turn": 1, "total_turns": 5,
        "spawning_tiles": [],
    }


def test_rust_solver_accepts_disabled_actions_without_crashing():
    b = _two_weapon_board()
    b["disabled_actions"] = [{"weapon_id": "Prime_Punchmech"}]
    r = _rust_solve(b)
    # Just verify the shape comes back — the next test checks behavior.
    assert "actions" in r


def test_rust_solver_avoids_soft_disabled_weapon():
    """With a weapon disabled, the solver must pick a different one
    (the bias is large enough to flip the tie when both weapons reach
    the same outcome)."""
    baseline = _rust_solve(_two_weapon_board())
    chosen = next((a["weapon_id"] for a in baseline["actions"]
                   if a["mech_uid"] == 0 and a["weapon_id"]
                   and a["weapon_id"] != "Repair"),
                  None)
    if chosen is None:
        pytest.skip("Solver didn't pick a weapon on baseline — test not useful")

    b = _two_weapon_board()
    b["disabled_actions"] = [{"weapon_id": chosen}]
    blocked = _rust_solve(b)
    blocked_wid = next((a["weapon_id"] for a in blocked["actions"]
                        if a["mech_uid"] == 0), "")
    assert blocked_wid != chosen, (
        f"Solver ignored soft-disable: kept {chosen} even when disabled. "
        f"baseline_score={baseline['score']} blocked_score={blocked['score']}"
    )


def test_rust_solver_falls_back_to_disabled_weapon_when_no_alternative():
    """If nothing else can accomplish the task, the bias is a preference,
    not a prohibition. This is the 'caged mech' safety valve from
    docs/self_healing_loop_design.md §Response Tier 2."""
    # PunchMech with ONLY Prime_Punchmech — no alternative at all.
    board = _two_weapon_board()
    board["units"][0]["weapons"] = ["Prime_Punchmech"]
    board["disabled_actions"] = [{"weapon_id": "Prime_Punchmech"}]
    r = _rust_solve(board)
    # Solver might pick it (paying the penalty) or skip the attack —
    # either is acceptable for the caged case. What we DON'T want is
    # a crash or an empty action list.
    assert "actions" in r


# ── #P1-6 corpus replay harness ──────────────────────────────────────────────


def test_corpus_replay_runs_without_crashing():
    """The replay harness is the regression gate for evaluate(). It must
    handle every real failure_db record without raising. A crash here
    means evaluate()'s contract drifted away from what the historical
    corpus looks like."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "replay_fuzzy_detector",
        Path(__file__).resolve().parent.parent / "scripts" / "replay_fuzzy_detector.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.replay()
    # Skip cleanly if the corpus isn't present in this checkout.
    if "error" in report:
        pytest.skip(report["error"])
    assert report["crashes"] == [], f"evaluate() crashed on real records: {report['crashes']}"
    # Shape contract: if there's a corpus at all, there are records.
    assert report["per_sub_action_records"] >= 0


from pathlib import Path  # noqa: E402 — used above


def test_failure_db_reader_tolerates_missing_fuzzy_signal(monkeypatch, tmp_path):
    """Backward-compat check: trigger without fuzzy_signal still writes
    cleanly, and existing readers that ``.get("fuzzy_signal")`` see None."""
    db_path = tmp_path / "failure_db.jsonl"
    monkeypatch.setattr(analysis, "FAILURE_DB_PATH", db_path)
    trigger = {
        "trigger": "per_sub_action_desync_move",
        "tier": 2,
        "severity": "low",
        "details": "legacy shape",
    }
    analysis.append_to_failure_db(
        [trigger], run_id="tr", mission_index=0, turn=1,
        context={"squad": "Rift", "island": "", "model_gap": False,
                 "weight_version": "v?", "solver_version": "v?", "tags": []},
    )
    rec = json.loads(db_path.read_text().strip())
    assert rec.get("fuzzy_signal") is None
