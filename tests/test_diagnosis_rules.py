"""Diagnosis rules-table fixtures.

Each fixture is a minimal failure_db-shaped record that should resolve to
exactly one of the four sim v10 seed rules in `diagnoses/rules.yaml`.
The shapes were extracted from the pre-fix sim_v9 entries on the
Disposal-Site Blitzkrieg turn (commit f00a394, run
recordings/20260423_131700_144/) — they're the corpus that motivated the
rules in the first place.

Marked @pytest.mark.regression so the canonical
`bash scripts/regression.sh` doesn't pick them up automatically; run via
`pytest tests/test_diagnosis_rules.py -m regression` per session brief.
"""

from __future__ import annotations

import pytest

from src.solver.diagnosis import (
    MatchResult,
    Rule,
    diagnose,
    diff_known_gap,
    load_rules,
    match_rule,
)


# ---------------------------------------------------------------------------
# Static fixtures
# ---------------------------------------------------------------------------


def _wallmech_move_only_failure() -> tuple[dict, dict]:
    """Rule 1 — `move_only_active_guard`.

    WallMech plan: move D6→D7, no weapon. Sim cleared `active=false`,
    actual game left `active=true`.
    """
    failure = {
        "id": "fixture_move_only_a1",
        "run_id": "20260423_131700_144",
        "mission": 0,
        "turn": 1,
        "action_index": 1,
        "simulator_version": 9,
        "category": "click_miss",
        "diff": {
            "unit_diffs": [
                {
                    "uid": 1,
                    "type": "WallMech",
                    "field": "active",
                    "predicted": False,
                    "actual": True,
                }
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 1,
        "mech_type": "WallMech",
        "move_to": [1, 4],
        "weapon": "Unknown",
        "weapon_id": "Unknown",
        "target": [255, 255],
        "description": "WallMech, move D6→D7",
    }
    return failure, action


def _chain_whip_self_damage_failure() -> tuple[dict, dict]:
    """Rule 2 — `chain_shooter_self_damage`.

    ElectricMech (uid 0) fires Chain Whip at Scarab2 (D4). Sim's chain
    BFS wraps back to the shooter tile; predicts ElectricMech HP 3 → 1.
    Actual game leaves ElectricMech at full 3 HP.
    """
    failure = {
        "id": "fixture_chain_self_damage_a2",
        "run_id": "20260423_131700_144",
        "mission": 0,
        "turn": 1,
        "action_index": 2,
        "simulator_version": 9,
        "category": "damage_amount",
        "diff": {
            "unit_diffs": [
                {
                    "uid": 0,
                    "type": "ElectricMech",
                    "field": "hp",
                    "predicted": 1,
                    "actual": 3,
                }
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 0,
        "mech_type": "ElectricMech",
        "move_to": [3, 4],
        "weapon": "Chain Whip",
        "weapon_id": "Prime_Lightning",
        "target": [4, 4],
        "description": "ElectricMech, fire Chain Whip at D4",
    }
    return failure, action


def _artillery_perpendicular_failure() -> tuple[dict, dict]:
    """Rule 3 — `artillery_perpendicular_push_missing`.

    RockartMech fires Rock Launcher at C3 with PushDir::Perpendicular.
    Acid_Tank at the southern flank should be pushed outward (south)
    by 1 tile; sim missed the perpendicular branch and left it in place.
    """
    failure = {
        "id": "fixture_artillery_perp_a3",
        "run_id": "20260423_131700_144",
        "mission": 0,
        "turn": 1,
        "action_index": 3,
        "simulator_version": 9,
        "category": "push_dir",
        "diff": {
            "unit_diffs": [
                {
                    "uid": 118,
                    "type": "Acid_Tank",
                    "field": "pos",
                    "predicted": [5, 6],
                    "actual": [5, 7],
                }
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 2,
        "mech_type": "RockartMech",
        "move_to": [2, 5],
        "weapon": "Rock Launcher",
        "weapon_id": "Ranged_Rockthrow",
        "target": [5, 5],
        "description": "RockartMech, fire Rock Launcher at C3",
    }
    return failure, action


def _acid_tile_load_failure() -> tuple[dict, dict]:
    """Rule 4 — `acid_tile_unit_status_at_load`.

    Acid_Tank fires A.C.I.D. Cannon at C3. Predicted state shows tile
    (5,5) acid=false; actual game has acid=true. Underlying root cause
    is the load-time ACID-status drop that this rule patches in
    serde_bridge.rs (commit f00a394 bug #3).
    """
    failure = {
        "id": "fixture_acid_load_a0",
        "run_id": "20260423_131700_144",
        "mission": 0,
        "turn": 1,
        "action_index": 0,
        "simulator_version": 9,
        "category": "tile_status",
        "diff": {
            "unit_diffs": [],
            "tile_diffs": [
                {
                    "x": 5,
                    "y": 5,
                    "field": "acid",
                    "predicted": False,
                    "actual": True,
                }
            ],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 118,
        "mech_type": "Acid_Tank",
        "move_to": [5, 6],
        "weapon": "A.C.I.D. Cannon",
        "weapon_id": "Acid_Tank_Attack",
        "target": [5, 5],
        "description": "Acid_Tank, move B5→B3, fire A.C.I.D. Cannon at C3",
    }
    return failure, action


# ---------------------------------------------------------------------------
# Sanity: rules.yaml loads at all + the four seed rules are present.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_rules_load_with_four_seed_entries():
    rules = load_rules()
    ids = {r.id for r in rules}
    expected = {
        "move_only_active_guard",
        "chain_shooter_self_damage",
        "artillery_perpendicular_push_missing",
        "acid_tile_unit_status_at_load",
    }
    missing = expected - ids
    assert not missing, f"diagnoses/rules.yaml missing seed rules: {missing}"


@pytest.mark.regression
def test_rules_have_suspect_files_in_rust_only():
    """Authoritative sim is Rust — no rule should target Python sim files."""
    rules = load_rules()
    for r in rules:
        for sf in r.suspect_files:
            path = sf.split(":", 1)[0]
            assert path.startswith("rust_solver/") or path.startswith(
                "src/bridge/"
            ), (
                f"Rule {r.id} suspect_file {sf!r} should target rust_solver/* "
                "(Python sim is test primitives only)"
            )


# ---------------------------------------------------------------------------
# Per-rule: each fixture matches exactly the expected rule.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_move_only_active_guard_matches():
    failure, action = _wallmech_move_only_failure()
    res = match_rule(failure["diff"], action, failure["simulator_version"])
    assert res.winner is not None
    assert res.winner.id == "move_only_active_guard"
    assert res.winner.confidence == "high"
    assert any(
        sf.startswith("rust_solver/src/simulate.rs")
        for sf in res.winner.suspect_files
    )


@pytest.mark.regression
def test_chain_shooter_self_damage_matches():
    failure, action = _chain_whip_self_damage_failure()
    res = match_rule(failure["diff"], action, failure["simulator_version"])
    assert res.winner is not None
    assert res.winner.id == "chain_shooter_self_damage"


@pytest.mark.regression
def test_artillery_perpendicular_push_matches():
    failure, action = _artillery_perpendicular_failure()
    res = match_rule(failure["diff"], action, failure["simulator_version"])
    assert res.winner is not None
    assert res.winner.id == "artillery_perpendicular_push_missing"


@pytest.mark.regression
def test_acid_tile_unit_status_matches():
    failure, action = _acid_tile_load_failure()
    res = match_rule(failure["diff"], action, failure["simulator_version"])
    assert res.winner is not None
    assert res.winner.id == "acid_tile_unit_status_at_load"


# ---------------------------------------------------------------------------
# Discriminator gating: rule must NOT fire when the action context misses.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_move_only_rule_skips_when_action_has_a_weapon():
    """The active-flag diff alone is not enough — rule needs weapon_id_none."""
    failure, _ = _wallmech_move_only_failure()
    action_with_weapon = {
        "mech_uid": 1,
        "mech_type": "WallMech",
        "weapon": "Wall Buster",
        "weapon_id": "Prime_Punchmech",
        "target": [3, 4],
    }
    res = match_rule(
        failure["diff"], action_with_weapon, failure["simulator_version"]
    )
    assert res.winner is None, (
        "move_only_active_guard must require weapon_id_none — "
        "matching on the symptom alone is the foot-gun in §13 #9"
    )


@pytest.mark.regression
def test_chain_shooter_rule_skips_for_non_chain_weapon():
    failure, _ = _chain_whip_self_damage_failure()
    action_non_chain = {
        "mech_uid": 0,
        "mech_type": "ElectricMech",
        "weapon": "Punch",
        "weapon_id": "Prime_Punchmech",
        "target": [4, 4],
    }
    res = match_rule(
        failure["diff"], action_non_chain, failure["simulator_version"]
    )
    assert res.winner is None


@pytest.mark.regression
def test_artillery_perpendicular_rule_skips_for_non_artillery():
    failure, _ = _artillery_perpendicular_failure()
    action_melee = {
        "mech_uid": 2,
        "mech_type": "ElectricMech",
        "weapon": "Chain Whip",
        "weapon_id": "Prime_Lightning",
        "target": [5, 5],
    }
    res = match_rule(
        failure["diff"], action_melee, failure["simulator_version"]
    )
    assert res.winner is None


# ---------------------------------------------------------------------------
# Sim-version gating: retired rules don't fire on post-fix corpus rows.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_retired_rules_skip_post_fix_sim_version():
    """All four sim_v10 fixes are retired_in_sim_version=10.

    A diff that would have matched on sim_version=9 must NOT match
    on sim_version=10 — the rule has shipped, the bug is gone.
    """
    failure, action = _wallmech_move_only_failure()
    res_pre_fix = match_rule(failure["diff"], action, sim_version=9)
    assert res_pre_fix.winner is not None  # sanity

    res_post_fix = match_rule(failure["diff"], action, sim_version=10)
    assert res_post_fix.winner is None, (
        "move_only_active_guard is retired_in_sim_version=10; should not "
        "match on sim_version=10 corpus"
    )


# ---------------------------------------------------------------------------
# Markdown round-trip: diagnose() writes a file we can re-load.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_diagnose_writes_markdown_with_frontmatter(tmp_path):
    failure, action = _wallmech_move_only_failure()
    out_dir = tmp_path / "diag"
    result = diagnose(
        failure["id"],
        force=False,
        out_dir=out_dir,
        failure=failure,
        action=action,
    )
    assert result["status"] == "rule_match"
    assert result["rule_id"] == "move_only_active_guard"

    md_path = out_dir / f"{failure['id']}.md"
    assert md_path.exists()
    text = md_path.read_text()
    assert text.startswith("---\n"), "frontmatter must be first"
    assert "status: rule_match" in text
    assert "move_only_active_guard" in text
    assert "## Symptom" in text
    assert "## Hypothesis" in text
    assert "## Proposed fix" in text


@pytest.mark.regression
def test_diagnose_unmatched_falls_through_to_needs_agent(tmp_path):
    """A diff that matches none of the seed rules should produce
    needs_agent markdown — agent fallback is PR3, not this session."""
    failure = {
        "id": "fixture_unknown",
        "run_id": "test",
        "mission": 0,
        "turn": 1,
        "action_index": 0,
        "simulator_version": 10,
        "diff": {
            "unit_diffs": [
                {
                    "uid": 99,
                    "type": "Hornet1",
                    "field": "status.frozen",
                    "predicted": True,
                    "actual": False,
                }
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 0,
        "mech_type": "PunchMech",
        "weapon": "Titan Fist",
        "weapon_id": "Prime_Punchmech",
        "target": [3, 3],
    }
    out_dir = tmp_path / "diag"
    result = diagnose(
        failure["id"],
        out_dir=out_dir,
        failure=failure,
        action=action,
    )
    assert result["status"] == "needs_agent"
    assert result["rule_id"] is None
    text = (out_dir / f"{failure['id']}.md").read_text()
    assert "status: needs_agent" in text
    assert "Agent fallback" in text or "needs agent" in text.lower()


# ---------------------------------------------------------------------------
# Known-gap suppression: web-clear is on the gaps list and should short-circuit.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_known_gap_short_circuits_diagnose(tmp_path):
    """diff_known_gap should fire on web-clear-on-push (in known_gaps.yaml)."""
    diff = {
        "unit_diffs": [
            {
                "uid": 119,
                "type": "Scarab2",
                "field": "status.web",
                "predicted": True,
                "actual": False,
            }
        ],
        "tile_diffs": [],
        "scalar_diffs": [],
    }
    gap_id = diff_known_gap(diff)
    assert gap_id == "web_clear_on_push"

    failure = {
        "id": "fixture_web_clear",
        "run_id": "test",
        "mission": 0,
        "turn": 1,
        "action_index": 0,
        "simulator_version": 10,
        "diff": diff,
    }
    out_dir = tmp_path / "diag"
    result = diagnose(
        failure["id"], out_dir=out_dir, failure=failure, action=None
    )
    assert result["status"] == "insufficient_data"
    assert result["known_gap"] == "web_clear_on_push"

    # --force should bypass the known_gap check.
    forced = diagnose(
        failure["id"],
        force=True,
        out_dir=out_dir,
        failure=failure,
        action=None,
    )
    # Status depends on whether any rule happens to match this synthetic
    # diff. None of the four seed rules look at status.web, so it should
    # fall through to needs_agent — but the key assertion is the known_gap
    # suppression was bypassed (i.e. status != insufficient_data).
    assert forced["status"] != "insufficient_data"
