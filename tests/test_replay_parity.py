"""PR-A parity test: Rust replay_solution shape vs Python's recorded output.

Goal: confirm the new Rust pyo3 `replay_solution` produces JSON that
deserializes to the same dict shape Python consumers
(`cmd_verify_action`, `cmd_auto_turn`, `verify.py::diff_states`)
already understand. Two failure buckets:

  - SHAPE divergence (missing keys, wrong types, wrong nesting):
    blocks PR-A merge. Rust must match Python's exact contract.
  - VALUE divergence (same shape, different values): expected. These
    are the Python-vs-Rust sim bugs the diagnose loop was blind to.
    Documented in the artifact, NOT failed.

Walks a small curated subset of recordings to keep CI fast.
Marked @pytest.mark.regression to run with the rest of the corpus suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RECORDINGS = REPO / "recordings"


# ── Test fixtures ──────────────────────────────────────────────────────────


def _candidate_runs() -> list[Path]:
    """Recordings to exercise. Curated for CI speed.

    Picks the most recently-modified `m00_turn_*_solve.json` from the
    newest 3 run directories that have BOTH a solve recording AND a
    matching board recording. Keeps the test under a few seconds even
    as the recordings/ dir grows.
    """
    if not RECORDINGS.exists():
        return []
    runs = sorted(
        [p for p in RECORDINGS.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[Path] = []
    for run in runs:
        if len(out) >= 3:
            break
        for solve in sorted(run.glob("m*_turn_*_solve.json")):
            board = solve.with_name(solve.name.replace("_solve.json", "_board.json"))
            if board.exists():
                out.append(solve)
                break
    return out


def _load_bridge_and_plan(solve_path: Path) -> tuple[dict, list[dict]] | None:
    """Reconstruct bridge JSON + plan from a solve recording."""
    board_path = solve_path.with_name(solve_path.name.replace("_solve.json", "_board.json"))
    try:
        solve_rec = json.loads(solve_path.read_text())
        board_rec = json.loads(board_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    bridge = (board_rec.get("data") or {}).get("bridge_state")
    if not bridge:
        return None
    actions = (solve_rec.get("data") or {}).get("actions") or []
    if not actions:
        return None
    # Normalize actions to the plan_json shape Rust expects.
    plan = []
    for a in actions:
        wid = a.get("weapon_id") or a.get("weapon") or "None"
        target = a.get("target") or [255, 255]
        move_to = a.get("move_to") or [
            # Fallback: if no move_to recorded, the mech stayed put — find
            # its current position from bridge.
            255, 255,
        ]
        plan.append({
            "mech_uid": int(a["mech_uid"]),
            "move_to": [int(move_to[0]), int(move_to[1])],
            "weapon_id": wid,
            "target": [int(target[0]), int(target[1])],
        })
    return bridge, plan


# ── Shape contract ─────────────────────────────────────────────────────────

# Required top-level keys in Rust replay_solution output.
EXPECTED_TOP_KEYS = {"action_results", "predicted_states", "predicted_outcome", "final_board"}

# Required keys in each action_results[i].
EXPECTED_AR_KEYS = {
    "enemies_killed", "enemy_damage_dealt", "buildings_lost",
    "buildings_damaged", "grid_damage", "mech_damage_taken",
    "mechs_killed", "pods_collected", "spawns_blocked", "events",
}

# Required keys in each snapshot (post_move / post_attack).
EXPECTED_SNAP_KEYS = {
    "action_index", "mech_uid", "snapshot_phase",
    "units", "tiles_changed", "grid_power",
}

EXPECTED_UNIT_KEYS = {
    "uid", "type", "pos", "hp", "max_hp", "alive", "active",
    "is_mech", "team", "status",
}
EXPECTED_STATUS_KEYS = {"fire", "acid", "frozen", "shield", "web"}

EXPECTED_TILE_KEYS = {
    "x", "y", "terrain", "building_hp", "fire", "acid", "smoke", "has_pod",
}

EXPECTED_OUTCOME_KEYS = {
    "buildings_alive", "building_hp_total", "grid_power",
    "enemies_alive", "enemy_hp_total", "mechs_alive",
    "mech_hp", "buildings_destroyed_by_enemies",
}


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.regression
def test_replay_module_loaded():
    """itb_solver.replay_solution must be exposed by the wheel."""
    import itb_solver
    assert hasattr(itb_solver, "replay_solution"), (
        "Rust wheel doesn't expose replay_solution — rebuild via "
        "`maturin build --release && pip3 install --user --force-reinstall "
        "rust_solver/target/wheels/itb_solver-*.whl`"
    )


@pytest.mark.regression
def test_replay_solution_empty_plan_returns_baseline():
    """Empty plan → empty action lists, baseline outcome."""
    import itb_solver
    bridge = json.dumps({
        "tiles": [],
        "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "move": 4, "active": True, "weapons": ["Prime_Punchmech"]},
        ],
        "grid_power": 7, "grid_power_max": 7,
        "spawning_tiles": [], "environment_danger": [],
        "remaining_spawns": 0, "turn": 1, "total_turns": 5,
    })
    raw = itb_solver.replay_solution(bridge, "[]")
    data = json.loads(raw)
    assert set(data.keys()) >= EXPECTED_TOP_KEYS
    assert data["action_results"] == []
    assert data["predicted_states"] == []
    assert data["predicted_outcome"]["mechs_alive"] == 1
    assert data["predicted_outcome"]["enemies_alive"] == 0


@pytest.mark.regression
@pytest.mark.parametrize("solve_path", _candidate_runs(),
                         ids=lambda p: p.parent.name + "/" + p.name)
def test_replay_shape_against_recording(solve_path):
    """For each curated recording, Rust replay output must satisfy the
    shape contract that Python consumers depend on."""
    import itb_solver

    pair = _load_bridge_and_plan(solve_path)
    if pair is None:
        pytest.skip(f"recording {solve_path.name} missing bridge_state or actions")
    bridge, plan = pair

    raw = itb_solver.replay_solution(json.dumps(bridge), json.dumps(plan))
    data = json.loads(raw)

    # Top-level keys
    missing = EXPECTED_TOP_KEYS - set(data.keys())
    assert not missing, f"missing top-level keys: {missing}"

    # Per-action shape
    assert len(data["action_results"]) == len(plan), (
        f"action_results count {len(data['action_results'])} != plan {len(plan)}"
    )
    assert len(data["predicted_states"]) == len(plan), (
        f"predicted_states count {len(data['predicted_states'])} != plan {len(plan)}"
    )

    for i, ar in enumerate(data["action_results"]):
        ar_keys = set(ar.keys())
        # Allow extra keys (forward-compat) but require the documented set.
        miss = EXPECTED_AR_KEYS - ar_keys
        assert not miss, f"action_results[{i}] missing keys: {miss}"

    for i, state in enumerate(data["predicted_states"]):
        assert "post_move" in state and "post_attack" in state, (
            f"predicted_states[{i}] missing post_move/post_attack"
        )
        for phase in ("post_move", "post_attack"):
            snap = state[phase]
            # mech_not_found sentinel path skips the full shape — only
            # require error key + units/tiles_changed/grid_power.
            if "error" in snap:
                assert snap["units"] == [] and snap["tiles_changed"] == []
                continue
            miss = EXPECTED_SNAP_KEYS - set(snap.keys())
            assert not miss, f"state[{i}][{phase}] missing keys: {miss}"
            for j, u in enumerate(snap["units"]):
                umiss = EXPECTED_UNIT_KEYS - set(u.keys())
                assert not umiss, f"state[{i}][{phase}].units[{j}] missing: {umiss}"
                smiss = EXPECTED_STATUS_KEYS - set(u["status"].keys())
                assert not smiss, f"state[{i}][{phase}].units[{j}].status missing: {smiss}"
                assert isinstance(u["pos"], list) and len(u["pos"]) == 2
                assert isinstance(u["alive"], bool)
                assert isinstance(u["is_mech"], bool)
            for k, t in enumerate(snap["tiles_changed"]):
                tmiss = EXPECTED_TILE_KEYS - set(t.keys())
                assert not tmiss, f"state[{i}][{phase}].tiles_changed[{k}] missing: {tmiss}"
                assert isinstance(t["terrain"], str)

    # predicted_outcome shape
    miss = EXPECTED_OUTCOME_KEYS - set(data["predicted_outcome"].keys())
    assert not miss, f"predicted_outcome missing keys: {miss}"

    # final_board must be a dict (bridge JSON) for the post-PR-B
    # round-trip to evaluate_breakdown.
    assert isinstance(data["final_board"], dict)
    assert "tiles" in data["final_board"] or "units" in data["final_board"]


@pytest.mark.regression
def test_replay_value_divergences_documented(tmp_path, capsys):
    """Surface (don't fail on) Python-vs-Rust value divergences from the
    recorded predictions. These are the sim bugs the diagnose loop was
    blind to; the test serializes them as a documentation artifact.

    Runs against the same curated recordings used by the shape test.
    Failure here means there are no recordings at all — that's a setup
    problem, not a sim regression.
    """
    import itb_solver

    candidates = _candidate_runs()
    if not candidates:
        pytest.skip("no recordings available — run an auto_turn first")

    divergences: list[dict] = []
    for solve_path in candidates:
        pair = _load_bridge_and_plan(solve_path)
        if pair is None:
            continue
        bridge, plan = pair
        try:
            raw = itb_solver.replay_solution(json.dumps(bridge), json.dumps(plan))
        except Exception as e:
            divergences.append({"recording": str(solve_path),
                                "error": f"replay failed: {e}"})
            continue
        rust_data = json.loads(raw)
        try:
            recorded = json.loads(solve_path.read_text())
            recorded_states = (recorded.get("data") or {}).get("predicted_states") or []
        except (OSError, json.JSONDecodeError):
            continue
        # Quick spot-check: do the Rust and Python predicted_states
        # agree on per-snapshot grid_power? (One scalar — easy to diff.)
        for i, (rust_state, py_state) in enumerate(
            zip(rust_data["predicted_states"], recorded_states)
        ):
            for phase in ("post_move", "post_attack"):
                rs = rust_state.get(phase) or {}
                ps = py_state.get(phase) or {}
                rg = rs.get("grid_power")
                pg = ps.get("grid_power")
                if rg is not None and pg is not None and rg != pg:
                    divergences.append({
                        "recording": solve_path.name,
                        "action_index": i,
                        "phase": phase,
                        "field": "grid_power",
                        "python_pred": pg,
                        "rust_pred": rg,
                    })

    # Always pass — this test documents, doesn't gate. Print report.
    print(f"\n=== Rust-vs-Python prediction divergences ({len(divergences)} found) ===")
    for d in divergences[:20]:
        print(f"  {d}")
    if len(divergences) > 20:
        print(f"  ... +{len(divergences) - 20} more")
    # Sanity: at least some recordings were exercised.
    assert candidates, "no recordings exercised"
