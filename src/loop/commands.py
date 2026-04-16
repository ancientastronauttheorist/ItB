"""Game loop subcommand implementations.

Each command is a pure function: load state -> compute -> output -> save state.
Commands are called by the CLI dispatcher (game_loop.py) and by Claude
through the computer-use MCP tool.

The session file persists state between CLI invocations.
The decision log records every action for post-run analysis.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from src.capture.save_parser import (
    load_game_state,
    load_active_mission,
    detect_game_phase,
)
from src.model.board import Board
from src.model.weapons import get_weapon_name
from src.solver.solver import MechAction, replay_solution
from src.solver.evaluate import evaluate_threats
from src.control.executor import (
    plan_single_mech,
    plan_end_turn,
    grid_to_mcp,
    recalibrate,
)
from src.capture.detect_grid import find_game_window, grid_from_window
from src.bridge.protocol import is_bridge_active, refresh_bridge_state, BridgeError
from src.bridge.reader import read_bridge_state
from src.bridge.writer import (
    execute_bridge_action, execute_bridge_end_turn,
    deploy_mech, set_bridge_speed,
    move_mech, attack_mech, skip_mech, repair_mech,
)
from src.loop.session import RunSession, SolverAction, DEFAULT_SESSION_FILE
from src.loop.logger import DecisionLog

SNAPSHOT_DIR = Path(__file__).parent.parent.parent / "snapshots"
SAVE_DIR = Path.home() / "Library" / "Application Support" / "IntoTheBreach"


def _load_session() -> RunSession:
    """Load the active session (creates default if none exists)."""
    return RunSession.load(DEFAULT_SESSION_FILE)


def _get_logger(session: RunSession) -> DecisionLog:
    """Get the decision log for the current run."""
    run_id = session.run_id or "default"
    return DecisionLog(run_id)


RECORDING_DIR = Path(__file__).parent.parent.parent / "recordings"


def _atomic_json_write(filepath: Path, data: dict) -> None:
    """Write JSON atomically: tmp file -> fsync -> os.replace."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(f".tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(filepath))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _recording_dir(session: RunSession) -> Path:
    """Get the recording directory for the current run."""
    run_id = session.run_id or "default"
    run_dir = RECORDING_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _record_turn_state(session: RunSession, label: str, data: dict,
                       turn_override: int = None) -> None:
    """Record full game state to a per-run, per-mission, per-turn JSON file.

    Creates recordings/<run_id>/m<M>_turn_<N>_<label>.json with the complete
    bridge state and/or solver output for later replay and analysis.

    Args:
        turn_override: If set, use this turn number instead of session.current_turn.
            Used for post-enemy recordings that reference the solved turn.
    """
    run_dir = _recording_dir(session)
    turn = turn_override if turn_override is not None else session.current_turn
    mi = session.mission_index

    filename = f"m{mi:02d}_turn_{turn:02d}_{label}.json"
    filepath = run_dir / filename

    record = {
        "timestamp": datetime.now().isoformat(),
        "run_id": session.run_id or "default",
        "mission_index": mi,
        "turn": turn,
        "label": label,
        "data": data,
    }

    _atomic_json_write(filepath, record)


def _get_solver_version() -> str:
    """Get solver version from Cargo.toml + git hash."""
    try:
        cargo_path = Path(__file__).parent.parent.parent / "rust_solver" / "Cargo.toml"
        version = "unknown"
        if cargo_path.exists():
            for line in cargo_path.read_text().splitlines():
                if line.strip().startswith("version"):
                    version = line.split('"')[1]
                    break
        git_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).parent.parent.parent
        ).stdout.strip()
        return f"rust-{version}-{git_hash}" if git_hash else f"rust-{version}"
    except Exception:
        return "unknown"


def _get_weight_version() -> str:
    """Get weight version from active.json."""
    try:
        weights_path = Path(__file__).parent.parent.parent / "weights" / "active.json"
        if weights_path.exists():
            with open(weights_path) as f:
                return json.load(f).get("version", "unknown")
    except Exception:
        pass
    return "default"


def _write_manifest(session: RunSession, extra: dict = None) -> None:
    """Write or update the run manifest file."""
    run_dir = _recording_dir(session)
    filepath = run_dir / "manifest.json"

    # Load existing manifest if present (for updates)
    manifest = {}
    if filepath.exists():
        try:
            with open(filepath) as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Set/update fields
    manifest.update({
        "run_id": session.run_id,
        "squad": session.squad,
        "difficulty": session.difficulty,
        "achievement_targets": session.achievement_targets,
        "tags": session.tags,
        "solver_version": _get_solver_version(),
        "weight_version": _get_weight_version(),
        "updated": datetime.now().isoformat(),
    })
    manifest.setdefault("created", datetime.now().isoformat())
    manifest.setdefault("missions", [])
    manifest.setdefault("outcome", None)

    if extra:
        manifest.update(extra)

    _atomic_json_write(filepath, manifest)


def _capture_action_snapshot() -> dict:
    """Capture lightweight board snapshot for per-action diff recording."""
    refresh_bridge_state()
    board, _ = read_bridge_state()
    if not board:
        return {}
    return {
        "mechs": [{"uid": u.uid, "pos": [u.x, u.y], "hp": u.hp,
                    "active": getattr(u, 'active', True)}
                   for u in board.units if u.is_mech],
        "enemies": [{"uid": u.uid, "pos": [u.x, u.y], "hp": u.hp}
                     for u in board.units if not u.is_mech and u.hp > 0],
    }


def _write_mission_summary(session: RunSession, turns_completed: int,
                           final_grid: str = "") -> None:
    """Aggregate turn data into a mission summary."""
    run_dir = _recording_dir(session)
    mi = session.mission_index

    # Collect trigger data from this mission's turn files
    trigger_files = sorted(run_dir.glob(f"m{mi:02d}_turn_*_triggers.json"))
    total_triggers = 0
    severity_counts = {"critical": 0, "high": 0, "medium": 0}
    for tf in trigger_files:
        try:
            with open(tf) as f:
                td = json.load(f).get("data", {})
            total_triggers += td.get("trigger_count", 0)
            for sev in severity_counts:
                severity_counts[sev] += td.get("severity_counts", {}).get(sev, 0)
        except (json.JSONDecodeError, OSError):
            continue

    summary = {
        "mission_index": mi,
        "mission_name": session.current_mission,
        "turns_completed": turns_completed,
        "final_grid": final_grid,
        "total_triggers": total_triggers,
        "severity_counts": severity_counts,
        "buildings_lost": session.buildings_lost,
        "timestamp": datetime.now().isoformat(),
    }

    filepath = run_dir / f"m{mi:02d}_mission_summary.json"
    _atomic_json_write(filepath, summary)

    # Update manifest with mission result
    _write_manifest(session, {
        "missions": _load_mission_list(run_dir),
    })


def _load_mission_list(run_dir: Path) -> list:
    """Load all mission summaries from a run directory."""
    summaries = []
    for f in sorted(run_dir.glob("m*_mission_summary.json")):
        try:
            with open(f) as fh:
                summaries.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return summaries


def _write_run_summary(session: RunSession, outcome: str) -> None:
    """Write final run summary aggregating all missions."""
    run_dir = _recording_dir(session)
    missions = _load_mission_list(run_dir)

    total_turns = sum(m.get("turns_completed", 0) for m in missions)
    total_triggers = sum(m.get("total_triggers", 0) for m in missions)

    summary = {
        "run_id": session.run_id,
        "squad": session.squad,
        "difficulty": session.difficulty,
        "outcome": outcome,
        "missions_completed": len(missions),
        "total_turns": total_turns,
        "total_triggers": total_triggers,
        "buildings_lost": session.buildings_lost,
        "timestamp": datetime.now().isoformat(),
    }

    filepath = run_dir / "run_summary.json"
    _atomic_json_write(filepath, summary)

    # Finalize manifest
    _write_manifest(session, {"outcome": outcome})


# --- Coordinate Helpers ---


def _bv(x: int, y: int) -> str:
    """Bridge (x,y) to visual notation (e.g. 'C5'). Matches game board labels."""
    return f"{chr(72 - y)}{8 - x}"


# --- Post-Enemy Analysis Helpers ---


def _capture_board_summary(board: Board) -> dict:
    """Extract a summary of the current board state for comparison."""
    buildings_alive = 0
    building_hp_total = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                building_hp_total += t.building_hp

    return {
        "buildings_alive": buildings_alive,
        "building_hp_total": building_hp_total,
        "grid_power": board.grid_power,
        "enemies_alive": len(board.enemies()),
        "enemy_hp_total": sum(e.hp for e in board.enemies()),
        "mechs_alive": len([m for m in board.mechs() if m.hp > 0]),
        "mech_hp": [
            {"uid": m.uid, "type": m.type, "hp": m.hp, "max_hp": m.max_hp}
            for m in board.mechs()
        ],
    }


def _compute_deltas(predicted: dict, actual: dict) -> dict:
    """Compare predicted vs actual board state. Negative diff = worse than predicted."""
    deltas = {
        "buildings_alive_diff": actual["buildings_alive"] - predicted["buildings_alive"],
        "building_hp_diff": actual["building_hp_total"] - predicted["building_hp_total"],
        "grid_power_diff": actual["grid_power"] - predicted["grid_power"],
        # Enemy count diff recorded for info but NOT used for triggers
        # (new spawns inflate actual count — that's expected, not a solver failure)
        "enemies_alive_diff": actual["enemies_alive"] - predicted["enemies_alive"],
    }

    # Per-mech HP comparison — match by UID for precision
    mech_deltas = []
    pred_mechs = {m["uid"]: m for m in predicted.get("mech_hp", [])}
    for am in actual.get("mech_hp", []):
        pm = pred_mechs.get(am["uid"])
        if pm:
            mech_deltas.append({
                "uid": am["uid"],
                "type": am["type"],
                "predicted_hp": pm["hp"],
                "actual_hp": am["hp"],
                "diff": am["hp"] - pm["hp"],
            })
        else:
            # Mech in actual but not predicted (shouldn't happen normally)
            mech_deltas.append({
                "uid": am["uid"],
                "type": am["type"],
                "predicted_hp": 0,
                "actual_hp": am["hp"],
                "diff": am["hp"],
            })
    deltas["mech_hp_diff"] = mech_deltas

    # Human-readable unexpected events
    unexpected = []
    if deltas["buildings_alive_diff"] < 0:
        unexpected.append(
            f"Lost {-deltas['buildings_alive_diff']} unexpected building(s)")
    if deltas["grid_power_diff"] < 0:
        unexpected.append(
            f"Grid power dropped by {-deltas['grid_power_diff']} unexpectedly")
    for md in mech_deltas:
        if md["diff"] < 0:
            unexpected.append(
                f"{md['type']} took {-md['diff']} unexpected damage")
    deltas["unexpected_events"] = unexpected

    return deltas


def _record_post_enemy(session: RunSession, board: Board,
                       solved_turn: int) -> None:
    """Record post-enemy board state and compare with solver predictions.

    Idempotent: if ``(mission_index, solved_turn)`` is already in
    ``session.recorded_post_enemy_turns``, returns early so the same turn
    can't be flushed twice (e.g. once by ``cmd_read``, once by
    ``cmd_auto_mission`` on exit).
    """
    from src.solver.analysis import detect_triggers

    run_dir = _recording_dir(session)
    mi = session.mission_index

    # Dedup guard.
    key = [mi, solved_turn]
    if key in session.recorded_post_enemy_turns:
        return

    # Load the solve recording from the solved turn (try new naming, fallback to old)
    solve_file = run_dir / f"m{mi:02d}_turn_{solved_turn:02d}_solve.json"
    if not solve_file.exists():
        solve_file = run_dir / f"turn_{solved_turn:02d}_solve.json"
    if not solve_file.exists():
        return

    session.recorded_post_enemy_turns.append(key)

    with open(solve_file) as f:
        solve_record = json.load(f)

    solve_data = solve_record.get("data", {})
    predicted = solve_data.get("predicted_outcome")
    if predicted is None:
        # Old-format recording without predictions — skip comparison
        return

    # Capture actual board state
    actual = _capture_board_summary(board)

    # Compute deltas
    deltas = _compute_deltas(predicted, actual)

    # Record post-enemy state
    _record_turn_state(session, "post_enemy", {
        "actual_outcome": actual,
        "predicted_outcome": predicted,
        "deltas": deltas,
    }, turn_override=solved_turn)

    # Detect triggers
    triggers = detect_triggers(actual, predicted, deltas, solve_data, board)
    if triggers:
        _record_turn_state(session, "triggers", {
            "triggers": triggers,
            "trigger_count": len(triggers),
            "severity_counts": {
                "critical": sum(1 for t in triggers if t["severity"] == "critical"),
                "high": sum(1 for t in triggers if t["severity"] == "high"),
                "medium": sum(1 for t in triggers if t["severity"] == "medium"),
            },
        }, turn_override=solved_turn)

        # Append to failure database
        from src.solver.analysis import append_to_failure_db
        append_to_failure_db(
            triggers,
            run_id=session.run_id or "default",
            mission_index=session.mission_index,
            turn=solved_turn,
            context={
                "squad": session.squad,
                "island": session.current_island,
                "grid_power": actual.get("grid_power"),
                "solver_timed_out": solve_data.get("search_stats", {}).get("timed_out", False),
                "weight_version": solve_data.get("weight_version", "unknown"),
                "solver_version": _get_solver_version(),
                "tags": list(session.tags),
            },
        )

        # Print triggers for immediate visibility
        print(f"\n{'='*50}")
        print(f"TRIGGERS DETECTED ({len(triggers)}) — Turn {solved_turn}:")
        for t in triggers:
            print(f"  [T{t['tier']}] {t['severity'].upper()}: "
                  f"{t['trigger']} — {t['details']}")
        print(f"{'='*50}")
    else:
        print(f"\nPost-enemy analysis: no triggers (predictions matched)")


# --- State Reading Commands ---


def cmd_read(profile: str = "Alpha") -> dict:
    """Parse save file, detect game phase, dump board state.

    Returns a dict with phase, board info, and mech status.
    """
    # Invalidate cached window position so next click uses fresh detection
    recalibrate()

    session = _load_session()

    # Try bridge first (direct Lua API access)
    if is_bridge_active():
        # Request fresh state dump from game
        refresh_bridge_state()
        board, bridge_data = read_bridge_state()
        if board is not None and bridge_data is not None:
            phase = bridge_data.get("phase", "unknown")
            old_phase = session.phase
            session.phase = phase

            result = {
                "phase": phase,
                "source": "bridge",
                "turn": bridge_data.get("turn", 0),
                "grid_power": f"{board.grid_power}/{board.grid_power_max}",
            }

            session.current_turn = bridge_data.get("turn", 0)

            if phase in ("combat_player", "combat_enemy"):
                mechs = board.mechs()
                active_mechs = [m for m in mechs if m.active and m.hp > 0]
                result["mechs"] = [
                    {"type": m.type, "pos": _bv(m.x, m.y),
                     "hp": f"{m.hp}/{m.max_hp}",
                     "weapon": get_weapon_name(m.weapon),
                     "status": "READY" if m.active else "DONE"}
                    for m in mechs
                ]
                result["active_mechs"] = len(active_mechs)

                enemies = board.enemies()
                result["enemies"] = [
                    {"type": e.type, "pos": _bv(e.x, e.y),
                     "hp": f"{e.hp}/{e.max_hp}",
                     "target": f" \u2192 {_bv(e.target_x, e.target_y)}" if e.target_x >= 0 else ""}
                    for e in enemies
                ]

                threats = board.get_threatened_buildings()
                result["threatened_buildings"] = len(threats)
                if threats:
                    result["threats"] = [
                        f"Building {_bv(x, y)} by {u.type} at {_bv(u.x, u.y)}"
                        for x, y, u in threats
                    ]

                targeted = bridge_data.get("targeted_tiles", [])
                result["targeted_tiles"] = len(targeted)
                spawning = bridge_data.get("spawning_tiles", [])
                result["spawn_points"] = len(spawning)

                # Deployment zone (available on turn 0 during deployment)
                deploy_zone = bridge_data.get("deployment_zone", [])
                if deploy_zone:
                    deploy_tiles = []
                    for tile in deploy_zone:
                        bx, by = tile[0], tile[1]
                        visual_row = 8 - bx
                        visual_col = chr(72 - by)
                        mcp_x, mcp_y = grid_to_mcp(bx, by)
                        deploy_tiles.append({
                            "bridge": f"({bx},{by})",
                            "visual": f"{visual_col}{visual_row}",
                            "mcp": [mcp_x, mcp_y],
                        })
                    result["deployment_zone"] = deploy_tiles

                print(f"\n{'='*50}")
                print(f"BOARD STATE (BRIDGE) — Turn {bridge_data.get('turn', '?')} | "
                      f"Grid: {board.grid_power}/{board.grid_power_max} | "
                      f"Phase: {phase}")
                print(f"{'='*50}")
                board.print_board()

                if deploy_zone:
                    print(f"\nDEPLOYMENT ZONE ({len(deploy_tiles)} tiles):")
                    for dt in deploy_tiles:
                        print(f"  {dt['visual']} (bridge {dt['bridge']}) -> MCP ({dt['mcp'][0]}, {dt['mcp'][1]})")

                    # Show ranked recommendations
                    ranked = rank_deploy_tiles(board, deploy_zone)
                    if ranked:
                        print(f"\nRECOMMENDED DEPLOY (ranked by enemy proximity + building cover):")
                        for idx, (rx, ry) in enumerate(ranked):
                            vr = 8 - rx
                            vc = chr(72 - ry)
                            mx, my = grid_to_mcp(rx, ry)
                            role = ["FORWARD", "MID", "SUPPORT"][min(idx, 2)]
                            print(f"  {idx+1}. {vc}{vr} ({role}) -> MCP ({mx}, {my})")
                        result["recommended_deploy"] = [
                            {"visual": f"{chr(72-ry)}{8-rx}", "mcp": list(grid_to_mcp(rx, ry))}
                            for rx, ry in ranked
                        ]

                # Environment danger tiles
                env_danger = bridge_data.get("environment_danger", [])
                env_type = bridge_data.get("env_type", "unknown")
                if env_danger:
                    danger_tiles = []
                    for tile in env_danger:
                        if isinstance(tile, (list, tuple)) and len(tile) >= 2:
                            bx, by = tile[0], tile[1]
                            visual_row = 8 - bx
                            visual_col = chr(72 - by)
                            danger_tiles.append({
                                "bridge": f"({bx},{by})",
                                "visual": f"{visual_col}{visual_row}",
                            })
                    result["environment_danger"] = danger_tiles
                    result["env_type"] = env_type
                    _ENV_LABELS = {
                        "wind": "PUSH (non-lethal)",
                        "sandstorm": "SMOKE (non-lethal)",
                        "snow": "FREEZE (non-lethal)",
                        "lightning_or_airstrike": "LETHAL (instant-kill)",
                        "tidal_or_cataclysm": "LETHAL (terrain conversion)",
                        "cataclysm_or_seismic": "LETHAL (terrain→chasm)",
                        "unknown": "LETHAL (default)",
                    }
                    # Override label from v2 kill_int if available
                    env_v2 = bridge_data.get("environment_danger_v2", [])
                    if env_type == "unknown" and env_v2:
                        all_non_lethal = all(
                            isinstance(t, (list, tuple)) and len(t) >= 4 and t[3] == 0
                            for t in env_v2
                        )
                        if all_non_lethal:
                            label = "NON-LETHAL (kill_int=0, env_type unknown)"
                        else:
                            label = _ENV_LABELS.get(env_type, "LETHAL (default)")
                    else:
                        label = _ENV_LABELS.get(env_type, "LETHAL (default)")
                    print(f"\nENVIRONMENT DANGER ({len(danger_tiles)} tiles) — {label}:")
                    for dt in danger_tiles:
                        print(f"  {dt['visual']} (bridge {dt['bridge']})")

            if old_phase != phase and old_phase != "unknown":
                logger = _get_logger(session)
                logger.log_phase_transition(old_phase, phase)

            # Record full state for replay/analysis
            _record_turn_state(session, "board", {
                "bridge_state": bridge_data,
                "result_summary": result,
            })

            # Post-enemy detection: if turn advanced past the solved turn,
            # this board is the actual outcome of the previous turn's solution.
            # NOTE: Cannot rely on actions_executed (MCP flow uses cmd_read
            # to verify, not cmd_verify, so the counter stays at 0).
            if (session.active_solution is not None
                    and bridge_data.get("turn", 0) > session.active_solution.turn
                    and phase == "combat_player"):
                _record_post_enemy(session, board, session.active_solution.turn)
                session.active_solution = None  # consumed — prevents re-trigger
            elif (session.active_solution is not None
                    and phase in ("between_missions", "mission_ending")):
                # Mission ended — clear stale solution (no comparison possible)
                session.active_solution = None

            session.save()
            _print_result(result)
            return result

    # Fallback: detect phase from saveData.lua ONLY (no undoSave fallback)
    phase = detect_game_phase(profile)

    old_phase = session.phase
    session.phase = phase

    result = {"phase": phase}

    if phase in ("combat_player", "combat_enemy"):
        state = load_game_state(profile)
        if state is None or state.active_mission is None:
            result["error"] = "Phase is combat but no mission data loaded"
            session.save()
            _print_result(result)
            return result

        m = state.active_mission
        board = Board.from_mission(m, state.grid_power, state.grid_power_max)

        # Update session
        session.current_turn = m.current_turn

        # Board summary
        result["turn"] = m.current_turn
        result["grid_power"] = f"{board.grid_power}/{board.grid_power_max}"

        # Mechs
        mechs = board.mechs()
        active_mechs = [mech for mech in mechs if mech.active and mech.hp > 0]
        result["mechs"] = []
        for mech in mechs:
            status = "READY" if mech.active else "DONE"
            if mech.hp <= 0:
                status = "DEAD"
            weapon_name = get_weapon_name(mech.weapon)
            result["mechs"].append({
                "type": mech.type,
                "pos": _bv(mech.x, mech.y),
                "hp": f"{mech.hp}/{mech.max_hp}",
                "weapon": weapon_name,
                "status": status,
            })
        result["active_mechs"] = len(active_mechs)

        # Enemies
        enemies = board.enemies()
        result["enemies"] = []
        for e in enemies:
            target = f" \u2192 {_bv(e.target_x, e.target_y)}" if e.target_x >= 0 else ""
            result["enemies"].append({
                "type": e.type,
                "pos": _bv(e.x, e.y),
                "hp": f"{e.hp}/{e.max_hp}",
                "target": target,
            })

        # Threats
        threats = board.get_threatened_buildings()
        result["threatened_buildings"] = len(threats)
        if threats:
            result["threats"] = [
                f"Building {_bv(x, y)} by {u.type} at {_bv(u.x, u.y)}"
                for x, y, u in threats
            ]

        # Spawn points
        spawns = [(p.x, p.y) for p in m.spawn_points]
        result["spawn_points"] = len(spawns)

        # Print ASCII board
        print("\n" + "=" * 50)
        print(f"BOARD STATE — Turn {m.current_turn} | "
              f"Grid: {board.grid_power}/{board.grid_power_max} | "
              f"Phase: {phase}")
        print("=" * 50)
        board.print_board()

    elif phase == "between_missions":
        state = load_game_state(profile)
        if state:
            result["grid_power"] = f"{state.grid_power}/{state.grid_power_max}"
        result["note"] = "Between missions (map/shop/island select). Use screenshot to determine exact screen."

    elif phase == "mission_ending":
        result["note"] = "Mission is ending. Wait for reward screen."

    elif phase == "no_save":
        result["note"] = "No save file found. Game may be on main menu or not running."

    # Log phase transition if it changed
    if old_phase != phase and old_phase != "unknown":
        logger = _get_logger(session)
        logger.log_phase_transition(old_phase, phase)

    session.save()
    _print_result(result)
    return result


def cmd_solve(profile: str = "Alpha", time_limit: float = 10.0) -> dict:
    """Run solver on current board, store solution in session.

    Returns the solution with actions and score.
    """
    session = _load_session()
    logger = _get_logger(session)

    # Try bridge first (richer data: status effects, per-enemy targets)
    board = None
    spawns = []
    bridge_data = None
    current_turn = 0
    environment_danger = set()
    if is_bridge_active():
        refresh_bridge_state()
        board, bridge_data = read_bridge_state()
        if board is not None and bridge_data is not None:
            spawns = [tuple(s) for s in bridge_data.get("spawning_tiles", [])]
            current_turn = bridge_data.get("turn", 0)
            # Extract environment danger tiles (tidal waves, air strikes, etc.)
            for dt in bridge_data.get("environment_danger", []):
                if isinstance(dt, (list, tuple)) and len(dt) >= 2:
                    environment_danger.add((dt[0], dt[1]))

    # Fallback to save parser
    if board is None:
        state = load_game_state(profile)
        if state is None or state.active_mission is None:
            result = {"error": "No active mission to solve"}
            _print_result(result)
            return result
        m = state.active_mission
        board = Board.from_mission(m, state.grid_power, state.grid_power_max)
        spawns = [(p.x, p.y) for p in m.spawn_points]
        current_turn = m.current_turn

    # Check for active mechs (includes friendly controllable units like ArchiveArtillery)
    active_mechs = [mech for mech in board.mechs()
                    if mech.active and mech.hp > 0 and (mech.is_mech or mech.weapon)]
    if not active_mechs:
        result = {"error": "No active mechs — all have acted this turn"}
        _print_result(result)
        return result

    # Run solver — try Rust (fast) first, fall back to Python
    print(f"\nSolving ({len(active_mechs)} active mechs, {time_limit}s limit)...")
    if environment_danger:
        print(f"  Environment danger: {len(environment_danger)} tiles")

    solution = None

    # Load evaluation weights from active weight file
    weight_version = "default"
    weights_path = Path(__file__).parent.parent.parent / "weights" / "active.json"
    eval_weights_dict = None
    if weights_path.exists():
        try:
            with open(weights_path) as wf:
                weight_data = json.load(wf)
            eval_weights_dict = weight_data.get("weights")
            weight_version = weight_data.get("version", "unknown")
        except (json.JSONDecodeError, IOError):
            pass

    # Try Rust solver if bridge data available
    if bridge_data is not None:
        try:
            import itb_solver as _rust
            import json as _json
            import time as _time
            # Augment unit data with pawn_stats info (ranged flag) for Rust solver
            from src.model.pawn_stats import get_pawn_stats
            if "units" in bridge_data:
                for u in bridge_data["units"]:
                    stats = get_pawn_stats(u.get("type", ""))
                    u["ranged"] = stats.ranged
                    if not stats.pushable:
                        u["pushable"] = False
                    # Clamp u8 fields to prevent Rust deserializer overflow
                    for k in ("weapon_damage", "weapon_push", "hp", "max_hp"):
                        if k in u and isinstance(u[k], int) and u[k] > 255:
                            u[k] = 255
            # Inject custom weights into bridge data for Rust solver
            if eval_weights_dict:
                bridge_data["eval_weights"] = eval_weights_dict
            # Inject mine data from board into bridge data
            # (save-file fallback until modloader reports items natively)
            if board is not None and "tiles" in bridge_data:
                for td in bridge_data["tiles"]:
                    bx, by = td.get("x", -1), td.get("y", -1)
                    if 0 <= bx < 8 and 0 <= by < 8:
                        if board.tile(bx, by).freeze_mine:
                            td["freeze_mine"] = True
                        if board.tile(bx, by).old_earth_mine:
                            td["old_earth_mine"] = True
            rust_start = _time.time()
            rust_json = _rust.solve(_json.dumps(bridge_data), time_limit)
            rust_result = _json.loads(rust_json)
            rust_elapsed = _time.time() - rust_start

            if rust_result.get("actions"):
                # Convert Rust result to Python Solution/MechAction objects
                from src.solver.solver import Solution, MechAction
                rust_actions = []
                for ra in rust_result["actions"]:
                    # Use weapon_id (internal ID like "Prime_Punchmech") for simulation,
                    # not weapon (display name like "Titan Fist").
                    # Fall back to display-name-to-ID lookup if weapon_id not present.
                    w_id = ra.get("weapon_id", "")
                    if not w_id:
                        from src.model.weapons import weapon_name_to_id
                        w_id = weapon_name_to_id(ra.get("weapon", ""))
                    rust_actions.append(MechAction(
                        mech_uid=ra["mech_uid"],
                        mech_type=ra["mech_type"],
                        move_to=tuple(ra["move_to"]),
                        weapon=w_id,
                        target=tuple(ra["target"]),
                        description=ra["description"],
                    ))
                solution = Solution(
                    actions=rust_actions,
                    score=rust_result["score"],
                    elapsed_seconds=rust_elapsed,
                    timed_out=rust_result["stats"].get("timed_out", False),
                    permutations_tried=rust_result["stats"].get("permutations_tried", 0),
                    total_permutations=rust_result["stats"].get("total_permutations", 0),
                    active_mech_count=len(active_mechs),
                )
                print(f"  Rust solver: {rust_elapsed:.2f}s, score={solution.score:.0f}, "
                      f"{solution.permutations_tried}/{solution.total_permutations} permutations"
                      f"{' (some timed out)' if solution.timed_out else ' (all complete)'}")
        except ImportError:
            print("  ERROR: Rust solver not available (itb_solver module not found)")
            print("  Build with: cd rust_solver && maturin develop --release")
        except Exception as e:
            print(f"  Rust solver error: {e}")

    # Rust solver is the only solver. If it failed, return empty solution.
    if solution is None:
        from src.solver.solver import Solution
        print("  ERROR: Rust solver failed — no solution available")
        solution = Solution()

    if not solution.actions:
        result = {
            "warning": "Solver returned empty solution (timeout or no valid actions)",
            "actions": [],
            "score": float('-inf'),
        }
        logger.log_error(
            "empty_solution",
            "Solver returned no actions. Consider manual play.",
            "Take screenshot and play manually, or increase time limit."
        )
        _print_result(result)
        session.save()
        return result

    # Store solution in session
    solver_actions = []
    for a in solution.actions:
        solver_actions.append(SolverAction(
            mech_uid=a.mech_uid,
            mech_type=a.mech_type,
            move_to=a.move_to,
            weapon=a.weapon,
            target=a.target,
            description=a.description,
        ))
    session.set_solution(solver_actions, solution.score, current_turn)

    # Build result
    result = {
        "score": solution.score,
        "num_actions": len(solution.actions),
        "actions": [],
    }
    for i, a in enumerate(solution.actions):
        result["actions"].append({
            "index": i,
            "mech_type": a.mech_type,
            "description": a.description,
        })

    # Log
    threats = board.get_threatened_buildings()
    logger.log_solver_output(
        solution.score,
        [a.description for a in solution.actions],
        threats=len(threats),
    )

    session.record_decision("solve", {
        "score": solution.score,
        "actions": [a.description for a in solution.actions],
    })

    # Replay solution for enriched recording data
    rem_spawns = bridge_data.get("remaining_spawns", 2**31 - 1) if bridge_data else 2**31 - 1
    enriched = replay_solution(board, solution, spawns,
                               current_turn=current_turn,
                               total_turns=board.total_turns if hasattr(board, 'total_turns') else 5,
                               remaining_spawns=rem_spawns)

    # Record solver output for replay/analysis (enriched format)
    solve_data = {
        "score": solution.score,
        "actions": [{
            "mech_uid": a.mech_uid,
            "mech_type": a.mech_type,
            "move_to": list(a.move_to) if a.move_to else None,
            "weapon": get_weapon_name(a.weapon) if a.weapon and a.weapon != "_REPAIR" else a.weapon,
            "weapon_id": a.weapon,
            "target": list(a.target),
            "description": a.description,
        } for a in solution.actions],
        "threats": len(threats),
        "active_mechs": len(active_mechs),
        "spawn_points": spawns,
        "search_stats": {
            "elapsed_seconds": solution.elapsed_seconds,
            "timed_out": solution.timed_out,
            "permutations_tried": solution.permutations_tried,
            "total_permutations": solution.total_permutations,
            "active_mech_count": solution.active_mech_count,
        },
        "weight_version": weight_version,
        "action_results": enriched["action_results"],
        "predicted_states": enriched.get("predicted_states", []),
        "predicted_outcome": enriched["predicted_outcome"],
        "score_breakdown": enriched["score_breakdown"],
    }
    _record_turn_state(session, "solve", solve_data)

    # Print
    print(f"\n=== SOLUTION (score: {solution.score:.0f}) ===")
    for i, a in enumerate(solution.actions):
        print(f"  Action {i}: {a.description}")
    print(f"\n{len(solution.actions)} actions to execute. "
          f"Use 'execute <index>' for each.")

    session.save()
    _print_result(result)
    return result


def cmd_execute(action_index: int, profile: str = "Alpha") -> dict:
    """Execute ONE mech action.

    In bridge mode: sends command directly to the game via Lua bridge.
    In MCP mode: returns click plan for Claude to execute manually.
    """
    session = _load_session()
    logger = _get_logger(session)

    # Get action from stored solution
    action = session.get_action(action_index)
    if action is None:
        total = 0
        if session.active_solution:
            total = len(session.active_solution.actions)
        result = {"error": f"No action at index {action_index} "
                  f"(solution has {total} actions)"}
        _print_result(result)
        return result

    # Convert SolverAction to MechAction
    mech_action = MechAction(
        mech_uid=action.mech_uid,
        mech_type=action.mech_type,
        move_to=action.move_to,
        weapon=action.weapon,
        target=action.target,
        description=action.description,
    )

    # Bridge mode: execute directly via Lua
    if is_bridge_active():
        logger.log_mech_action(action_index, action.description, 0)

        # Load board for move detection
        board_data, _ = read_bridge_state()
        board = board_data

        print(f"\n=== BRIDGE EXECUTE Action {action_index}: {action.description} ===")
        try:
            ack = execute_bridge_action(mech_action, board)
            print(f"  ACK: {ack}")
            session.mark_action_executed()
            result = {
                "action_index": action_index,
                "mech_type": action.mech_type,
                "description": action.description,
                "bridge": True,
                "ack": ack,
            }
        except (TimeoutError, BridgeError) as e:
            result = {"error": str(e), "bridge": True}
            print(f"  ERROR: {e}")

        session.save()
        _print_result(result)
        return result

    # MCP mode: return click plan. Prefer the bridge for live mech positions
    # so the click planner can resolve the mech tile correctly even when the
    # save file is stale; fall back to the save parser for offline replays.
    board = None
    if is_bridge_active():
        try:
            refresh_bridge_state()
            board, _ = read_bridge_state()
        except Exception:
            board = None
    if board is None:
        state = load_game_state(profile)
        if state and state.active_mission:
            board = Board.from_mission(
                state.active_mission, state.grid_power, state.grid_power_max
            )

    clicks = plan_single_mech(mech_action, board)

    logger.log_mech_action(action_index, action.description, len(clicks))

    result = {
        "action_index": action_index,
        "mech_type": action.mech_type,
        "description": action.description,
        "clicks": clicks,
    }

    print(f"\n=== EXECUTE Action {action_index}: {action.description} ===")
    for i, c in enumerate(clicks):
        print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) -- {c['description']}")

    session.save()
    return result


def cmd_verify(action_index: int = -1, profile: str = "Alpha",
               max_retries: int = 5, retry_delay: float = 1.5) -> dict:
    """Verify that the last mech action was executed correctly.

    Re-parses the save file and checks that the expected mech has
    acted (bActive = False). Retries to handle save file write delay.

    After end_turn, pass action_index=-1 to do a lenient check
    (only verifies turn advanced, not detailed board state).
    """
    session = _load_session()
    logger = _get_logger(session)

    if action_index >= 0 and session.active_solution:
        action = session.get_action(action_index)
        if action is None:
            result = {"error": f"No action at index {action_index}"}
            _print_result(result)
            return result
        expected_mech_type = action.mech_type
        expected_move_to = action.move_to
    else:
        expected_mech_type = None
        expected_move_to = None

    # Retry loop for save file staleness
    for attempt in range(max_retries):
        state = load_game_state(profile)
        if state is None or state.active_mission is None:
            # Mission may have ended — this is valid after end_turn
            if action_index < 0:
                result = {
                    "status": "PASS",
                    "note": "No active mission — mission may have ended",
                }
                logger.log_verification(-1, True, "Mission ended")
                session.save()
                _print_result(result)
                return result
            # During mech execution, no mission = unexpected
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            result = {
                "status": "FAIL",
                "error": "No active mission found during mech verification",
            }
            logger.log_verification(action_index, False, "No mission data")
            session.save()
            _print_result(result)
            return result

        m = state.active_mission
        board = Board.from_mission(m, state.grid_power, state.grid_power_max)

        # If verifying a specific mech action
        if expected_mech_type:
            # Find the mech and check if it has acted
            target_mech = None
            for u in board.units:
                if u.is_mech and u.type == expected_mech_type:
                    target_mech = u
                    break

            if target_mech is None:
                # Mech not found — may have been destroyed
                result = {
                    "status": "PASS",
                    "note": f"{expected_mech_type} not found (may be destroyed)",
                }
                logger.log_verification(action_index, True,
                                        f"{expected_mech_type} not found")
                session.mark_action_executed()
                session.save()
                _print_result(result)
                return result

            if not target_mech.active:
                # Mech has acted — success!
                pos_match = ""
                if expected_move_to:
                    actual = (target_mech.x, target_mech.y)
                    if actual == tuple(expected_move_to):
                        pos_match = f", position correct at {actual}"
                    else:
                        pos_match = (f", position MISMATCH: "
                                     f"expected {expected_move_to}, "
                                     f"actual {actual}")

                result = {
                    "status": "PASS",
                    "mech": expected_mech_type,
                    "acted": True,
                    "note": f"{expected_mech_type} has acted{pos_match}",
                }
                logger.log_verification(action_index, True,
                                        result["note"])
                session.mark_action_executed()
                session.save()
                _print_result(result)
                return result

            # Mech still active — save may not have updated yet
            if attempt < max_retries - 1:
                print(f"  Verify attempt {attempt+1}/{max_retries}: "
                      f"{expected_mech_type} still active, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue

            # All retries exhausted
            result = {
                "status": "FAIL",
                "mech": expected_mech_type,
                "acted": False,
                "note": (f"{expected_mech_type} still shows as active after "
                         f"{max_retries} retries. Click may have missed."),
            }
            logger.log_verification(action_index, False, result["note"])
            logger.log_error("verify_fail", result["note"],
                             f"Retry: game_loop.py execute {action_index}")
            session.save()
            _print_result(result)
            return result

        # Verifying after end_turn — lenient check
        else:
            # Check if turn has advanced or mission ended
            current_turn = m.current_turn
            if current_turn > session.current_turn:
                result = {
                    "status": "PASS",
                    "note": f"Turn advanced to {current_turn}",
                    "turn": current_turn,
                }
                session.current_turn = current_turn
                logger.log_verification(-1, True, result["note"])
                session.save()
                _print_result(result)
                return result

            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue

            result = {
                "status": "FAIL",
                "note": f"Turn still at {current_turn} after {max_retries} retries",
            }
            logger.log_verification(-1, False, result["note"])
            session.save()
            _print_result(result)
            return result

    # Should not reach here
    result = {"status": "FAIL", "error": "Verify exhausted all retries"}
    _print_result(result)
    return result


def cmd_verify_action(action_index: int) -> dict:
    """Per-action verification: diff predicted vs actual board state.

    Reads the per-action snapshot the solver captured during replay_solution,
    refreshes the bridge, and diffs the two. NEVER re-solves, NEVER overrides
    — desyncs are written to the failure database as data for the tuner.

    Returns a dict with status PASS/DESYNC/ERROR. The desync record carries
    a top_category and (optionally) a model_gap_known subcategory so Phase 4's
    tuner can filter pre-existing simulation gaps from tunable failures.
    """
    from src.solver.verify import diff_states, classify_diff

    session = _load_session()

    if not session.active_solution:
        result = {"status": "ERROR", "error": "No active solution to verify against"}
        _print_result(result)
        return result

    actions = session.active_solution.actions
    if not actions:
        result = {"status": "PASS", "note": "no actions to verify (empty solution)"}
        _print_result(result)
        return result

    if action_index < 0 or action_index >= len(actions):
        result = {
            "status": "ERROR",
            "error": f"action_index {action_index} out of range (have {len(actions)})",
        }
        _print_result(result)
        return result

    if not is_bridge_active():
        result = {"status": "ERROR", "error": "bridge not active — verify_action requires bridge"}
        _print_result(result)
        return result

    # Load the solve recording for the solved turn to get predicted_states.
    run_dir = _recording_dir(session)
    mi = session.mission_index
    solved_turn = session.active_solution.turn
    solve_file = run_dir / f"m{mi:02d}_turn_{solved_turn:02d}_solve.json"
    if not solve_file.exists():
        result = {
            "status": "ERROR",
            "error": f"solve recording missing: {solve_file.name}",
        }
        _print_result(result)
        return result

    try:
        with open(solve_file) as f:
            solve_record = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        result = {"status": "ERROR", "error": f"failed to read solve recording: {e}"}
        _print_result(result)
        return result

    predicted_states = solve_record.get("data", {}).get("predicted_states") or []
    if action_index >= len(predicted_states):
        result = {
            "status": "ERROR",
            "error": (f"no predicted_state at index {action_index} "
                      f"(recording has {len(predicted_states)})"),
        }
        _print_result(result)
        return result

    predicted_entry = predicted_states[action_index]

    # Support both old format (flat snapshot) and new format (post_move/post_attack).
    if "post_attack" in predicted_entry:
        predicted = predicted_entry["post_attack"]
    else:
        predicted = predicted_entry

    # Refresh bridge and read the actual current state.
    try:
        refresh_bridge_state()
    except (TimeoutError, BridgeError) as e:
        result = {"status": "ERROR", "error": f"bridge refresh failed: {e}"}
        _print_result(result)
        return result

    actual_board, _ = read_bridge_state()
    if actual_board is None:
        result = {"status": "ERROR", "error": "failed to read bridge state"}
        _print_result(result)
        return result

    diff = diff_states(predicted, actual_board)

    if diff.is_empty():
        result = {"status": "PASS", "action_index": action_index}
        print(f"VERIFY {action_index}: PASS")
        _print_result(result)
        return result

    classification = classify_diff(diff, mech_uid=predicted.get("mech_uid"))
    diff_dict = diff.to_dict()

    verify_record = {
        "action_index": action_index,
        "mech_uid": predicted.get("mech_uid"),
        "predicted": predicted,
        "diff": diff_dict,
        "classification": classification,
    }
    _record_turn_state(session, f"action_{action_index}_verify", verify_record,
                       turn_override=solved_turn)

    severity = "high" if classification["top_category"] in ("click_miss", "death") else "medium"
    cat_label = classification["top_category"]
    if classification.get("subcategory"):
        cat_label += f" [{classification['subcategory']}]"

    desync_trigger = {
        "trigger": "per_action_desync",
        "tier": 2,
        "severity": severity,
        "details": (
            f"Action {action_index} desync: {diff.total_count()} diffs, "
            f"top={cat_label}"
        ),
        "action_index": action_index,
        "mech_uid": predicted.get("mech_uid"),
        "category": classification["top_category"],
        "subcategory": classification.get("subcategory"),
        "diff": diff_dict,
    }

    from src.solver.analysis import append_to_failure_db
    append_to_failure_db(
        [desync_trigger],
        run_id=session.run_id or "default",
        mission_index=session.mission_index,
        turn=solved_turn,
        context={
            "squad": session.squad,
            "island": session.current_island,
            "model_gap": classification.get("model_gap", False),
            "weight_version": _get_weight_version(),
            "solver_version": _get_solver_version(),
            "tags": list(session.tags),
        },
    )

    result = {
        "status": "DESYNC",
        "action_index": action_index,
        "diff_count": diff.total_count(),
        "category": classification["top_category"],
        "categories": classification["categories"],
        "subcategory": classification.get("subcategory"),
        "model_gap": classification.get("model_gap", False),
    }
    print(f"VERIFY {action_index}: DESYNC ({diff.total_count()} diffs) [{cat_label}]")
    _print_result(result)
    return result


def cmd_click_action(action_index: int) -> dict:
    """Plan clicks for ONE mech action and emit a computer_batch-ready batch.

    Pure planner — does not execute any clicks itself. Claude (the parent
    process) reads the JSON output, dispatches the batch via
    ``mcp__computer-use__computer_batch``, waits for animations, then
    calls ``verify_action`` to confirm the predicted state landed.

    The planner reads the LIVE bridge state to resolve the mech's current
    tile, so it stays correct even if the solver's planned move_to differs
    from where the mech actually ended up.
    """
    session = _load_session()

    if not session.active_solution:
        result = {"status": "ERROR", "error": "No active solution"}
        _print_result(result)
        return result

    actions = session.active_solution.actions
    if action_index < 0 or action_index >= len(actions):
        result = {
            "status": "ERROR",
            "error": f"action_index {action_index} out of range (have {len(actions)})",
        }
        _print_result(result)
        return result

    action = actions[action_index]

    if not is_bridge_active():
        result = {"status": "ERROR", "error": "bridge not active — click_action requires bridge"}
        _print_result(result)
        return result

    # Defend against window movement between actions.
    recalibrate()

    try:
        refresh_bridge_state()
    except (TimeoutError, BridgeError) as e:
        result = {"status": "ERROR", "error": f"bridge refresh failed: {e}"}
        _print_result(result)
        return result

    board, _ = read_bridge_state()
    if board is None:
        result = {"status": "ERROR", "error": "failed to read bridge state"}
        _print_result(result)
        return result

    mech_action = MechAction(
        mech_uid=action.mech_uid,
        mech_type=action.mech_type,
        move_to=action.move_to,
        weapon=action.weapon,
        target=action.target,
        description=action.description,
    )
    batch = plan_single_mech(mech_action, board)

    if not batch:
        result = {
            "status": "ERROR",
            "error": (f"plan_single_mech returned empty batch — mech UID "
                      f"{action.mech_uid} not on the live board"),
        }
        _print_result(result)
        return result

    result = {
        "status": "PLAN",
        "action_index": action_index,
        "mech_type": action.mech_type,
        "description": action.description,
        "batch": batch,
        "next_step": f"verify_action {action_index}",
    }

    print(f"\n=== CLICK_ACTION {action_index}: {action.description} ===")
    for i, c in enumerate(batch):
        if c.get("type") == "wait":
            print(f"  {i+1}. wait {c.get('duration', 0)}s -- {c.get('description', '')}")
        else:
            print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) -- {c['description']}")
    print(f"Next: dispatch batch via computer_batch, then run "
          f"`verify_action {action_index}`")

    session.save()
    _print_result(result)
    return result


def cmd_click_end_turn() -> dict:
    """Emit a click plan for the End Turn button.

    Pure planner. Claude dispatches the batch via computer_batch, waits
    for the enemy phase to finish (~6s), then calls ``read`` to detect
    the new phase.
    """
    recalibrate()
    batch = plan_end_turn()
    result = {
        "status": "PLAN",
        "batch": batch,
        "next_step": "wait ~6s for enemy phase, then `read`",
    }
    print(f"\n=== CLICK_END_TURN ===")
    for i, c in enumerate(batch):
        print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) -- {c['description']}")
    print(f"Next: dispatch batch via computer_batch, wait ~6s, then `read`")
    _print_result(result)
    return result


def cmd_end_turn() -> dict:
    """End the current turn.

    In bridge mode: sends END_TURN command directly.
    In MCP mode: returns click plan for End Turn button.
    """
    session = _load_session()
    logger = _get_logger(session)
    logger.log_end_turn()

    # Bridge mode: the Lua END_TURN handler SetActives all player pawns for
    # solver-state consistency but cannot actually advance the turn without
    # ITB-ModLoader installed (no modApi, no Mission:EndTurn). It ACKs with
    # NEEDS_MCP_CLICK and we fall through to plan_end_turn so Claude can
    # dispatch the click via computer_batch.
    if is_bridge_active():
        print("\n=== BRIDGE END TURN ===")
        try:
            ack = execute_bridge_end_turn()
            print(f"  ACK: {ack}")
        except (TimeoutError, BridgeError) as e:
            result = {"error": str(e), "bridge": True}
            print(f"  ERROR: {e}")
            session.save()
            _print_result(result)
            return result

        if ack.startswith("NEEDS_MCP_CLICK"):
            recalibrate()
            batch = plan_end_turn()
            result = {
                "status": "PLAN",
                "bridge_ack": ack,
                "batch": batch,
                "next_step": "dispatch batch via computer_batch, "
                             "wait ~6s, then `read`",
            }
            print("  -> bridge SetActive done; emitting MCP click plan")
            for i, c in enumerate(batch):
                print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) "
                      f"-- {c['description']}")
        else:
            result = {"bridge": True, "ack": ack}

        session.save()
        _print_result(result)
        return result

    # MCP mode
    clicks = plan_end_turn()

    result = {
        "clicks": clicks,
        "note": "After executing, wait for enemy phase animations (6+ seconds), "
                "then run: game_loop.py verify",
    }

    print("\n=== END TURN ===")
    for i, c in enumerate(clicks):
        if c["type"] == "click":
            print(f"  {i+1}. CLICK ({c['x']}, {c['y']}) -- {c['description']}")
        elif c["type"] == "wait":
            print(f"  {i+1}. WAIT {c['duration']}s")

    session.save()
    _print_result(result)
    return result


def cmd_status(profile: str = "Alpha") -> dict:
    """Quick summary of current game state."""
    session = _load_session()

    result = {
        "run_id": session.run_id,
        "phase": session.phase,
        "turn": session.current_turn,
        "squad": session.squad,
        "actions_executed": session.actions_executed,
        "actions_remaining": session.actions_remaining(),
    }

    state = load_game_state(profile)
    if state:
        result["grid_power"] = f"{state.grid_power}/{state.grid_power_max}"
        if state.active_mission:
            board = Board.from_mission(
                state.active_mission, state.grid_power, state.grid_power_max
            )
            mechs = board.mechs()
            result["mechs"] = [
                {"type": m.type, "hp": f"{m.hp}/{m.max_hp}",
                 "active": m.active}
                for m in mechs
            ]
            result["enemies_alive"] = len(board.enemies())
            threats = board.get_threatened_buildings()
            result["threatened_buildings"] = len(threats)

    _print_result(result)
    return result


def cmd_new_run(squad: str, achievements: list[str] = None,
                difficulty: int = 0, tags: list[str] = None) -> dict:
    """Initialize a new run session.

    ``tags`` flags the run for downstream filtering. Use ``["audit"]`` for
    environment-audit playthroughs so the failures generated during the
    audit don't pollute the tuner training corpus.
    """
    session = RunSession.new_run(squad, achievements, difficulty, tags=tags)
    session.save()

    # Write run manifest
    _write_manifest(session)

    logger = DecisionLog(session.run_id)
    logger.log_custom("New Run", (
        f"Squad: {squad}\n"
        f"Achievements: {achievements or 'none'}\n"
        f"Difficulty: {difficulty}\n"
        f"Tags: {tags or 'none'}"
    ))

    result = {
        "run_id": session.run_id,
        "squad": squad,
        "achievements": achievements or [],
        "tags": tags or [],
    }
    print(f"\nNew run initialized: {session.run_id}")
    print(f"  Squad: {squad}")
    if achievements:
        print(f"  Targeting: {', '.join(achievements)}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")

    _print_result(result)
    return result


def cmd_snapshot(label: str, profile: str = "Alpha") -> dict:
    """Save current state for regression testing.

    Copies save file + session + board state to snapshots/<label>/.
    """
    snap_dir = SNAPSHOT_DIR / label
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Copy save file
    profile_dir = SAVE_DIR / f"profile_{profile}"
    for fname in ['saveData.lua', 'undoSave.lua']:
        src = profile_dir / fname
        if src.exists():
            shutil.copy2(str(src), str(snap_dir / fname))

    # Copy session
    if DEFAULT_SESSION_FILE.exists():
        shutil.copy2(str(DEFAULT_SESSION_FILE), str(snap_dir / "session.json"))

    # Save board state as JSON
    state = load_game_state(profile)
    if state and state.active_mission:
        board = Board.from_mission(
            state.active_mission, state.grid_power, state.grid_power_max
        )
        # Save a summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "label": label,
            "turn": state.active_mission.current_turn,
            "grid_power": state.grid_power,
            "mechs": [
                {"type": m.type, "pos": (m.x, m.y), "hp": m.hp}
                for m in board.mechs()
            ],
            "enemies": [
                {"type": e.type, "pos": (e.x, e.y), "hp": e.hp}
                for e in board.enemies()
            ],
        }
        with open(snap_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

    result = {"snapshot": label, "path": str(snap_dir)}
    print(f"\nSnapshot saved to: {snap_dir}")
    _print_result(result)
    return result


def cmd_log(message: str) -> dict:
    """Append Claude's reasoning to the decision log."""
    session = _load_session()
    logger = _get_logger(session)

    logger.log_custom("Claude Note", message)
    session.record_decision("note", {"message": message})
    session.save()

    result = {"logged": message}
    print(f"Logged: {message}")
    return result


# --- Helpers ---


def cmd_achievements() -> dict:
    """Query Steam for current Into the Breach achievement status."""
    import urllib.request
    from pathlib import Path

    # Load API key and Steam ID from .env
    env_path = Path(__file__).parent.parent.parent / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    api_key = env_vars.get("STEAM_API_KEY")
    steam_id = env_vars.get("STEAM_ID")

    if not api_key or not steam_id:
        result = {"error": "Missing STEAM_API_KEY or STEAM_ID in .env file"}
        _print_result(result)
        return result

    app_id = "590380"  # Into the Breach
    url = (f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
           f"?key={api_key}&steamid={steam_id}&appid={app_id}&l=en")

    try:
        resp = urllib.request.urlopen(url)
        data = json.loads(resp.read())
    except Exception as e:
        result = {"error": f"Steam API request failed: {e}"}
        _print_result(result)
        return result

    achievements = data.get("playerstats", {}).get("achievements", [])
    unlocked = [a for a in achievements if a.get("achieved") == 1]
    locked = [a for a in achievements if a.get("achieved") == 0]

    result = {
        "total": len(achievements),
        "unlocked": len(unlocked),
        "locked": len(locked),
        "unlocked_list": [a.get("name", a["apiname"]) for a in unlocked],
    }

    print(f"\n=== STEAM ACHIEVEMENTS: {len(unlocked)}/{len(achievements)} ===\n")
    for a in sorted(unlocked, key=lambda x: x.get("unlocktime", 0)):
        print(f"  ✅ {a.get('name', a['apiname'])}")
    print(f"\n  ❌ {len(locked)} remaining\n")

    _print_result(result)
    return result


def cmd_calibrate() -> dict:
    """Print detected window position, grid config, and sample tile positions.

    Diagnostic command to verify the coordinate system is correct.
    """
    recalibrate()

    win = find_game_window()
    if win is None:
        result = {"error": "Game window not found. Is Into the Breach running?"}
        _print_result(result)
        return result

    grid = grid_from_window(win)

    result = {
        "window": {
            "x": win.x, "y": win.y,
            "width": win.width, "height": win.height,
        },
        "grid_origin": {
            "x": round(grid.origin_x, 1),
            "y": round(grid.origin_y, 1),
        },
        "row_step": [round(grid.row_dx, 2), round(grid.row_dy, 2)],
        "col_step": [round(grid.col_dx, 2), round(grid.col_dy, 2)],
    }

    print(f"\n=== CALIBRATION ===")
    print(f"Window: x={win.x} y={win.y} w={win.width} h={win.height}")
    print(f"Grid origin (tile 1,1): ({grid.origin_x:.1f}, {grid.origin_y:.1f})")
    print(f"Row step (save_x): ({grid.row_dx:.2f}, {grid.row_dy:.2f})")
    print(f"Col step (save_y): ({grid.col_dx:.2f}, {grid.col_dy:.2f})")

    print(f"\nSample tile positions (MCP coords):")
    for sx, sy in [(0,0), (3,1), (4,2), (4,3), (7,7)]:
        px, py = grid.tile_to_pixel(sx + 1, sy + 1)
        print(f"  save({sx},{sy}) -> MCP ({px:.0f}, {py:.0f})")

    print(f"\nUI positions:")
    print(f"  End Turn: ({win.x + 95}, {win.y + 78})")
    print(f"  Portrait 0: ({win.x + 50}, {win.y + 135})")
    print(f"  Portrait 1: ({win.x + 50}, {win.y + 195})")
    print(f"  Portrait 2: ({win.x + 50}, {win.y + 245})")

    _print_result(result)
    return result


def _find_board_file(run_dir: Path, turn: int, mission: int = None) -> Path | None:
    """Find a board recording file, trying new naming then old naming."""
    if mission is not None:
        f = run_dir / f"m{mission:02d}_turn_{turn:02d}_board.json"
        if f.exists():
            return f
    candidates = sorted(run_dir.glob(f"m*_turn_{turn:02d}_board.json"))
    if candidates:
        return candidates[0]
    f = run_dir / f"turn_{turn:02d}_board.json"
    return f if f.exists() else None


def _load_board_from_recording(board_file: Path) -> tuple:
    """Load bridge_data, Board, spawns, and env_danger from a board recording.

    Returns (bridge_data, board, spawns, environment_danger) or raises ValueError.
    """
    with open(board_file) as f:
        board_record = json.load(f)

    bridge_data = board_record.get("data", {}).get("bridge_state")
    if bridge_data is None:
        raise ValueError("Recording has no bridge_state")

    board = Board.from_bridge_data(bridge_data)
    spawns = [tuple(s) for s in bridge_data.get("spawning_tiles", [])]
    environment_danger = set()
    for dt in bridge_data.get("environment_danger", []):
        if isinstance(dt, (list, tuple)) and len(dt) >= 2:
            environment_danger.add((dt[0], dt[1]))

    return bridge_data, board, spawns, environment_danger


def _solve_with_rust(bridge_data: dict, time_limit: float,
                     weights: dict = None) -> "Solution":
    """Run the Rust solver on bridge_data with optional custom weights.

    Returns a Solution object or None if Rust solver unavailable.
    """
    import copy
    from src.solver.solver import Solution, MechAction
    from src.model.pawn_stats import get_pawn_stats

    bd = copy.deepcopy(bridge_data)

    # Augment unit data with ranged/pushable flags
    if "units" in bd:
        for u in bd["units"]:
            stats = get_pawn_stats(u.get("type", ""))
            u["ranged"] = stats.ranged
            if not stats.pushable:
                u["pushable"] = False

    # Inject weights
    if weights:
        bd["eval_weights"] = weights

    # Inject mine data from save file fallback
    if "tiles" in bd:
        has_freeze = any(t.get("freeze_mine") for t in bd["tiles"])
        if not has_freeze:
            from src.bridge.reader import _read_freeze_mines_from_save
            mines = _read_freeze_mines_from_save()
            if mines:
                for td in bd["tiles"]:
                    if (td.get("x", -1), td.get("y", -1)) in mines:
                        td["freeze_mine"] = True
        has_oe = any(t.get("old_earth_mine") for t in bd["tiles"])
        if not has_oe:
            from src.bridge.reader import _read_old_earth_mines_from_save
            oe_mines = _read_old_earth_mines_from_save()
            if oe_mines:
                for td in bd["tiles"]:
                    if (td.get("x", -1), td.get("y", -1)) in oe_mines:
                        td["old_earth_mine"] = True

    import itb_solver as _rust
    rust_start = time.time()
    rust_json = _rust.solve(json.dumps(bd), time_limit)
    rust_result = json.loads(rust_json)
    rust_elapsed = time.time() - rust_start

    if not rust_result.get("actions"):
        return Solution()

    rust_actions = []
    for ra in rust_result["actions"]:
        w_id = ra.get("weapon_id", "")
        if not w_id:
            from src.model.weapons import weapon_name_to_id
            w_id = weapon_name_to_id(ra.get("weapon", ""))
        rust_actions.append(MechAction(
            mech_uid=ra["mech_uid"],
            mech_type=ra["mech_type"],
            move_to=tuple(ra["move_to"]),
            weapon=w_id,
            target=tuple(ra["target"]),
            description=ra["description"],
        ))

    return Solution(
        actions=rust_actions,
        score=rust_result["score"],
        elapsed_seconds=rust_elapsed,
        timed_out=rust_result["stats"].get("timed_out", False),
        permutations_tried=rust_result["stats"].get("permutations_tried", 0),
        total_permutations=rust_result["stats"].get("total_permutations", 0),
        active_mech_count=rust_result["stats"].get("active_mech_count", 0),
    )


def _fixed_score(outcome: dict) -> float:
    """Weight-independent scorer for fair comparison between weight versions.

    Uses only objective game metrics, not tunable weights.
    """
    return (
        outcome.get("buildings_alive", 0) * 100
        + outcome.get("grid_power", 0) * 50
        - outcome.get("buildings_destroyed_by_enemies", 0) * 200
        + outcome.get("mechs_alive", 0) * 30
    )


def cmd_replay(run_id: str, turn: int, time_limit: float = 30.0,
               mission: int = None, use_rust: bool = True) -> dict:
    """Load a recorded board state and re-run the solver.

    Reconstructs a Board from a recorded board JSON and re-runs the solver.
    Uses Rust solver by default (--no-rust for Python fallback).
    Supports both new (m00_turn_01_board.json) and old (turn_01_board.json) naming.
    """
    run_dir = RECORDING_DIR / run_id

    board_file = _find_board_file(run_dir, turn, mission)
    if board_file is None:
        result = {"error": f"No board recording for turn {turn} in {run_id}"}
        _print_result(result)
        return result

    try:
        bridge_data, board, spawns, environment_danger = _load_board_from_recording(board_file)
    except (ValueError, json.JSONDecodeError) as e:
        result = {"error": str(e)}
        _print_result(result)
        return result

    print(f"\nReplaying turn {turn} from run {run_id} "
          f"(time limit: {time_limit}s, solver: {'rust' if use_rust else 'python'})...")

    solution = None
    if use_rust:
        try:
            solution = _solve_with_rust(bridge_data, time_limit)
        except Exception as e:
            print(f"  Rust solver error: {e}")

    if solution is None:
        from src.solver.solver import Solution
        print("  ERROR: Rust solver failed — no solution available")
        solution = Solution()

    # Replay for enriched data
    enriched = None
    if solution.actions:
        enriched = replay_solution(board, solution, spawns)

    # Load original solve recording for comparison
    solve_file = run_dir / f"turn_{turn:02d}_solve.json"
    original_solve = None
    if solve_file.exists():
        with open(solve_file) as f:
            original_solve = json.load(f).get("data", {})

    # Build comparison result
    result = {
        "run_id": run_id,
        "turn": turn,
        "new_score": solution.score,
        "new_actions": [a.description for a in solution.actions],
        "search_stats": {
            "elapsed_seconds": solution.elapsed_seconds,
            "timed_out": solution.timed_out,
            "permutations_tried": solution.permutations_tried,
            "total_permutations": solution.total_permutations,
        },
    }

    if enriched:
        result["new_predicted_outcome"] = enriched["predicted_outcome"]
        result["new_score_breakdown"] = enriched["score_breakdown"]

    if original_solve:
        orig_score = original_solve.get("score", 0)
        result["original_score"] = orig_score
        result["original_actions"] = [
            a["description"] if isinstance(a, dict) else a
            for a in original_solve.get("actions", [])
        ]
        result["score_diff"] = solution.score - orig_score

        # Load triggers from original run
        trigger_file = run_dir / f"turn_{turn:02d}_triggers.json"
        if trigger_file.exists():
            with open(trigger_file) as f:
                orig_triggers = json.load(f).get("data", {}).get("triggers", [])
            result["original_triggers"] = len(orig_triggers)

    # Print comparison
    print(f"\n{'='*50}")
    print(f"REPLAY: Run {run_id}, Turn {turn}")
    print(f"{'='*50}")

    if original_solve:
        print(f"Original score: {original_solve.get('score', '?'):.0f}")
    print(f"New score:      {solution.score:.0f}")
    if "score_diff" in result:
        diff = result["score_diff"]
        sign = "+" if diff >= 0 else ""
        label = " (BETTER)" if diff > 0 else (" (SAME)" if diff == 0 else " (WORSE)")
        print(f"Difference:     {sign}{diff:.0f}{label}")

    print(f"\nNew actions:")
    for i, a in enumerate(solution.actions):
        print(f"  {i}: {a.description}")

    if original_solve:
        print(f"\nOriginal actions:")
        for i, a in enumerate(result.get("original_actions", [])):
            print(f"  {i}: {a}")

    if result.get("original_triggers"):
        print(f"\nOriginal run had {result['original_triggers']} trigger(s)")

    _print_result(result)
    return result


def _re_solve_partial(
    board: Board,
    bridge_data: dict,
    done_uids: set[int],
    mid_action_uid: int | None,
    time_limit: float,
    session: RunSession,
) -> tuple[list, list, float]:
    """Re-solve from actual board state with partial mech states.

    Args:
        board: The actual board from the bridge.
        bridge_data: Raw bridge data dict (for Rust solver input).
        done_uids: UIDs of mechs that have already completed their action.
        mid_action_uid: UID of a mech that has moved but not attacked (or None).
        time_limit: Solver time limit.
        session: Session for weight loading.

    Returns:
        (actions, predicted_states, score) from the new solve.
        actions is a list of MechAction. predicted_states is the dual-snapshot
        list from replay_solution.
    """
    import json as _json
    import time as _time
    from src.solver.solver import Solution, MechAction as _MA, replay_solution as _replay
    from src.model.pawn_stats import get_pawn_stats

    # Mark mech states in bridge data for the Rust solver
    if "units" in bridge_data:
        for u in bridge_data["units"]:
            uid = u.get("uid")
            stats = get_pawn_stats(u.get("type", ""))
            u["ranged"] = stats.ranged
            if not stats.pushable:
                u["pushable"] = False
            # Clamp u8 fields to prevent Rust deserializer overflow
            for k in ("weapon_damage", "weapon_push", "hp", "max_hp"):
                if k in u and isinstance(u[k], int) and u[k] > 255:
                    u[k] = 255
            if uid in done_uids:
                u["active"] = False
            elif uid == mid_action_uid:
                u["active"] = True
                u["can_move"] = False
            # All others keep their current active/can_move state

    # Load weights
    weights_path = Path(__file__).parent.parent.parent / "weights" / "active.json"
    if weights_path.exists():
        try:
            with open(weights_path) as wf:
                weight_data = _json.load(wf)
            bridge_data["eval_weights"] = weight_data.get("weights")
        except (ValueError, OSError):
            pass

    # Inject mine data from board into bridge data
    if board is not None and "tiles" in bridge_data:
        for td in bridge_data["tiles"]:
            bx, by = td.get("x", -1), td.get("y", -1)
            if 0 <= bx < 8 and 0 <= by < 8:
                if board.tile(bx, by).freeze_mine:
                    td["freeze_mine"] = True
                if board.tile(bx, by).old_earth_mine:
                    td["old_earth_mine"] = True

    try:
        import itb_solver as _rust
        t0 = _time.time()
        rust_json = _rust.solve(_json.dumps(bridge_data), time_limit)
        rust_result = _json.loads(rust_json)
        elapsed = _time.time() - t0

        if rust_result.get("actions"):
            from src.model.weapons import weapon_name_to_id
            actions = []
            for ra in rust_result["actions"]:
                w_id = ra.get("weapon_id", "")
                if not w_id:
                    w_id = weapon_name_to_id(ra.get("weapon", ""))
                actions.append(_MA(
                    mech_uid=ra["mech_uid"],
                    mech_type=ra["mech_type"],
                    move_to=tuple(ra["move_to"]),
                    weapon=w_id,
                    target=tuple(ra["target"]),
                    description=ra["description"],
                ))
            score = rust_result["score"]

            solution = Solution(
                actions=actions,
                score=score,
                elapsed_seconds=elapsed,
                timed_out=rust_result["stats"].get("timed_out", False),
                permutations_tried=rust_result["stats"].get("permutations_tried", 0),
                total_permutations=rust_result["stats"].get("total_permutations", 0),
                active_mech_count=len(actions),
            )

            spawns = [tuple(s) for s in bridge_data.get("spawning_tiles", [])]
            current_turn = bridge_data.get("turn", 0)
            enriched = _replay(board, solution, spawns,
                               current_turn=current_turn,
                               total_turns=bridge_data.get("total_turns", 5))
            return actions, enriched.get("predicted_states", []), score
    except Exception as e:
        print(f"  Re-solve error: {e}")

    return [], [], float('-inf')


def _resolve_weapon_slot_from_board(mech_uid: int, weapon_id: str, board: Board) -> int:
    """Resolve weapon_id to 0-based slot by matching against the mech's weapons."""
    mech = next((u for u in board.units if u.uid == mech_uid), None)
    if mech is None:
        return 0
    if weapon_id == mech.weapon:
        return 0
    if weapon_id == mech.weapon2:
        return 1
    return 0


def _log_sub_action_desync(
    session: RunSession,
    phase: str,
    action_index: int,
    mech_uid: int,
    predicted: dict,
    actual_board: Board,
    diff,
    classification: dict,
    solved_turn: int,
) -> None:
    """Record a sub-action desync to the failure database."""
    from src.solver.analysis import append_to_failure_db

    diff_dict = diff.to_dict()
    severity = "high" if classification["top_category"] in (
        "click_miss", "mech_position_wrong", "death"
    ) else "medium"
    cat_label = classification["top_category"]
    if classification.get("subcategory"):
        cat_label += f" [{classification['subcategory']}]"

    verify_record = {
        "action_index": action_index,
        "sub_action": phase,
        "mech_uid": mech_uid,
        "predicted": predicted,
        "diff": diff_dict,
        "classification": classification,
    }
    _record_turn_state(session, f"action_{action_index}_{phase}_verify",
                       verify_record, turn_override=solved_turn)

    desync_trigger = {
        "trigger": f"per_sub_action_desync_{phase}",
        "tier": 2,
        "severity": severity,
        "details": (
            f"Action {action_index} {phase} desync: {diff.total_count()} diffs, "
            f"top={cat_label}"
        ),
        "action_index": action_index,
        "sub_action": phase,
        "mech_uid": mech_uid,
        "category": classification["top_category"],
        "subcategory": classification.get("subcategory"),
        "diff": diff_dict,
    }

    append_to_failure_db(
        [desync_trigger],
        run_id=session.run_id or "default",
        mission_index=session.mission_index,
        turn=solved_turn,
        context={
            "squad": session.squad,
            "island": session.current_island,
            "model_gap": classification.get("model_gap", False),
            "weight_version": _get_weight_version(),
            "solver_version": _get_solver_version(),
            "tags": list(session.tags),
        },
    )
    print(f"  DESYNC action {action_index} {phase}: "
          f"{diff.total_count()} diffs [{cat_label}]")


def cmd_auto_turn(profile: str = "Alpha", time_limit: float = 10.0) -> dict:
    """Execute a combat turn via bridge with per-sub-action verification.

    For each mech action, executes MOVE and ATTACK as separate sub-actions,
    reads actual board state after each, and diffs against the solver's
    predicted state. On desync, re-solves from the actual board for the
    remaining mechs.

    Flow per mech:
      MOVE → read → diff post_move → (re-solve on desync)
      ATTACK → read → diff post_attack → (re-solve on desync)

    Returns dict with turn results or error.
    """
    from src.solver.verify import diff_states, classify_diff
    from src.bridge.writer import _resolve_weapon_slot

    if not is_bridge_active():
        result = {"error": "Bridge not active — auto_turn requires bridge"}
        _print_result(result)
        return result

    # 1. Read state
    read_result = cmd_read(profile=profile)
    phase = read_result.get("phase")
    if phase != "combat_player":
        result = {"error": f"Not in combat_player phase: {phase}", "phase": phase}
        _print_result(result)
        return result

    turn = read_result.get("turn", 0)
    print(f"\n{'='*50}")
    print(f"AUTO TURN {turn} (verify-after-every-sub-action)")
    print(f"{'='*50}")

    # 2. Solve
    solve_result = cmd_solve(profile=profile, time_limit=time_limit)
    if "error" in solve_result:
        result = {"error": f"Solve: {solve_result['error']}", "turn": turn}
        _print_result(result)
        return result
    if "warning" in solve_result:
        result = {"error": "Empty solution — manual play needed", "turn": turn}
        _print_result(result)
        return result

    score = solve_result.get("score", 0)
    session = _load_session()

    # Load predicted_states from the solve recording
    run_dir = _recording_dir(session)
    mi = session.mission_index
    solve_file = run_dir / f"m{mi:02d}_turn_{turn:02d}_solve.json"
    predicted_states = []
    if solve_file.exists():
        try:
            with open(solve_file) as f:
                solve_record = json.load(f)
            predicted_states = solve_record.get("data", {}).get("predicted_states", [])
        except (json.JSONDecodeError, OSError):
            pass

    # Build action list from session solution
    actions = session.active_solution.actions if session.active_solution else []
    done_uids: set[int] = set()
    re_solve_count = 0
    actions_completed = 0

    # 3. Execute each action with per-sub-action verification
    action_idx = 0
    while action_idx < len(actions):
        action = actions[action_idx]
        mech_uid = action.mech_uid
        mech_action = MechAction(
            mech_uid=action.mech_uid,
            mech_type=action.mech_type,
            move_to=action.move_to,
            weapon=action.weapon,
            target=action.target,
            description=action.description,
        )

        print(f"\n--- Action {actions_completed}: {action.description} ---")

        # Determine sub-action breakdown
        has_move = (action.move_to and action.move_to != (-1, -1))
        is_repair = (action.weapon == "_REPAIR")
        has_attack = (action.weapon and action.target[0] >= 0 and not is_repair)

        # Check if mech is actually moving (not staying in place)
        if has_move:
            refresh_bridge_state()
            current_board, current_data = read_bridge_state()
            if current_board:
                mech = next((u for u in current_board.units if u.uid == mech_uid), None)
                if mech and action.move_to == (mech.x, mech.y):
                    has_move = False

        # Get predicted states for this action
        pred_entry = predicted_states[action_idx] if action_idx < len(predicted_states) else {}
        pred_post_move = pred_entry.get("post_move") if isinstance(pred_entry, dict) else None
        pred_post_attack = pred_entry.get("post_attack") if isinstance(pred_entry, dict) else pred_entry

        # --- MOVE PHASE ---
        if has_move:
            try:
                ack = move_mech(mech_uid, action.move_to[0], action.move_to[1])
                print(f"  MOVE: {ack}")
            except (TimeoutError, BridgeError) as e:
                print(f"  MOVE ERROR: {e}")
                result = {"error": f"Move {actions_completed}: {e}",
                          "turn": turn, "actions_completed": actions_completed}
                _print_result(result)
                return result

            # Read actual state after move
            refresh_bridge_state()
            actual_board, actual_data = read_bridge_state()

            if actual_board and pred_post_move:
                diff = diff_states(pred_post_move, actual_board)
                if not diff.is_empty():
                    classification = classify_diff(diff, mech_uid=mech_uid, phase="move")
                    _log_sub_action_desync(
                        session, "move", actions_completed, mech_uid,
                        pred_post_move, actual_board, diff, classification, turn,
                    )
                    re_solve_count += 1
                    # Re-solve: this mech has moved but not attacked
                    if actual_data:
                        new_actions, new_preds, new_score = _re_solve_partial(
                            actual_board, actual_data, done_uids,
                            mid_action_uid=mech_uid,
                            time_limit=time_limit, session=session,
                        )
                        if new_actions:
                            print(f"  RE-SOLVED: {len(new_actions)} actions, score={new_score:.0f}")
                            # First action should be attack-only for mid_action mech
                            solver_actions = []
                            for a in new_actions:
                                solver_actions.append(SolverAction(
                                    mech_uid=a.mech_uid,
                                    mech_type=a.mech_type,
                                    move_to=a.move_to,
                                    weapon=a.weapon,
                                    target=a.target,
                                    description=a.description,
                                ))
                            actions = solver_actions
                            predicted_states = new_preds
                            score = new_score
                            action_idx = 0
                            continue  # restart loop with new solution
                else:
                    print(f"  MOVE VERIFIED: PASS")

        # --- ATTACK PHASE ---
        if has_attack:
            refresh_bridge_state()
            current_board, _ = read_bridge_state()
            weapon_slot = _resolve_weapon_slot(mech_action, current_board) if current_board else 0

            try:
                ack = attack_mech(mech_uid, weapon_slot, action.target[0], action.target[1])
                print(f"  ATTACK: {ack}")
            except (TimeoutError, BridgeError) as e:
                print(f"  ATTACK ERROR: {e}")
                result = {"error": f"Attack {actions_completed}: {e}",
                          "turn": turn, "actions_completed": actions_completed}
                _print_result(result)
                return result
        elif is_repair:
            if has_move:
                pass  # move already done above
            try:
                ack = repair_mech(mech_uid)
                print(f"  REPAIR: {ack}")
            except (TimeoutError, BridgeError) as e:
                print(f"  REPAIR ERROR: {e}")
                result = {"error": f"Repair {actions_completed}: {e}",
                          "turn": turn, "actions_completed": actions_completed}
                _print_result(result)
                return result
        elif not has_move:
            try:
                ack = skip_mech(mech_uid)
                print(f"  SKIP: {ack}")
            except (TimeoutError, BridgeError) as e:
                print(f"  SKIP ERROR: {e}")
        else:
            # Move-only: need to deactivate via SKIP
            try:
                ack = skip_mech(mech_uid)
                print(f"  SKIP (move-only): {ack}")
            except (TimeoutError, BridgeError) as e:
                print(f"  SKIP ERROR: {e}")

        # Read actual state after attack/repair/skip
        refresh_bridge_state()
        actual_board, actual_data = read_bridge_state()

        if actual_board and pred_post_attack:
            diff = diff_states(pred_post_attack, actual_board)
            if not diff.is_empty():
                classification = classify_diff(diff, mech_uid=mech_uid, phase="attack")
                _log_sub_action_desync(
                    session, "attack", actions_completed, mech_uid,
                    pred_post_attack, actual_board, diff, classification, turn,
                )
                # Skip re-solve if spawn-only on last action (new Vek emerged)
                is_last_action = (action_idx >= len(actions) - 1)
                spawn_new_only = (
                    diff.unit_diffs
                    and all(ud.get("field") == "missing_in_predicted"
                            for ud in diff.unit_diffs)
                    and not diff.tile_diffs
                    and not diff.scalar_diffs
                )
                if spawn_new_only and is_last_action:
                    print(f"  DESYNC action {actions_completed} attack: "
                          f"{diff.total_count()} diffs [spawn-only on last action, skipping re-solve]")
                    done_uids.add(mech_uid)
                    actions_completed += 1
                    action_idx += 1
                    continue

                re_solve_count += 1
                # Re-solve for remaining mechs
                done_uids.add(mech_uid)
                remaining = len(actions) - action_idx - 1
                if remaining > 0 and actual_data:
                    new_actions, new_preds, new_score = _re_solve_partial(
                        actual_board, actual_data, done_uids,
                        mid_action_uid=None,
                        time_limit=time_limit, session=session,
                    )
                    if new_actions:
                        print(f"  RE-SOLVED: {len(new_actions)} actions, score={new_score:.0f}")
                        solver_actions = []
                        for a in new_actions:
                            solver_actions.append(SolverAction(
                                mech_uid=a.mech_uid,
                                mech_type=a.mech_type,
                                move_to=a.move_to,
                                weapon=a.weapon,
                                target=a.target,
                                description=a.description,
                            ))
                        actions = solver_actions
                        predicted_states = new_preds
                        score = new_score
                        action_idx = 0
                        actions_completed += 1
                        continue  # restart loop with new solution
            else:
                print(f"  ATTACK VERIFIED: PASS")

        done_uids.add(mech_uid)
        actions_completed += 1
        action_idx += 1

    # 4. End turn
    end_result = cmd_end_turn()
    if "error" in end_result:
        result = {"error": f"END_TURN: {end_result['error']}",
                  "turn": turn, "actions_completed": actions_completed}
        _print_result(result)
        return result

    if end_result.get("status") == "PLAN":
        result = {
            "status": "PLAN",
            "turn": turn,
            "actions_completed": actions_completed,
            "score": score,
            "re_solves": re_solve_count,
            "bridge_ack": end_result.get("bridge_ack"),
            "batch": end_result["batch"],
            "next_step": "dispatch batch via computer_batch, wait ~6s, "
                         "then `read`",
        }
        _print_result(result)
        return result

    # 5. Post-turn state check
    time.sleep(1)
    refresh_bridge_state()
    post_board, post_data = read_bridge_state()
    post_phase = post_data.get("phase", "unknown") if post_data else "unknown"
    post_grid = post_board.grid_power if post_board else 0
    post_grid_max = post_board.grid_power_max if post_board else 0

    result = {
        "status": "ok",
        "turn": turn,
        "actions_completed": actions_completed,
        "score": score,
        "re_solves": re_solve_count,
        "post_phase": post_phase,
        "grid_power": f"{post_grid}/{post_grid_max}",
    }

    if post_board and post_board.grid_power <= 0:
        result["game_over"] = True
        print(f"  GAME OVER — grid power dropped to 0")

    print(f"  Turn {turn} complete: {actions_completed} actions, "
          f"score={score:.0f}, grid={post_grid}/{post_grid_max}, "
          f"re-solves={re_solve_count}, next={post_phase}")

    _print_result(result)
    return result


def rank_deploy_tiles(board, deploy_zone: list) -> list[tuple[int, int]]:
    """Rank deployment tiles by strategic value.

    Scores each tile based on:
    - Proximity to enemies (closer = better for interception on Turn 1)
    - Proximity to buildings (adjacent = better for protection)
    - Forward positioning (rows 4-6 bonus — at least one mech in strike range)

    Returns list of (x, y) bridge coordinates, best first.
    Picks 3 tiles with spatial diversity (not all clustered together).
    """
    enemies = [u for u in board.units if u.is_enemy and u.hp > 0]
    buildings = []
    for x in range(8):
        for y in range(8):
            t = board.tiles[x][y]
            if t.terrain == "building" and t.building_hp > 0:
                buildings.append((x, y))

    def dist(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)

    # Score every candidate tile
    scored = []
    for tile in deploy_zone:
        tx, ty = tile[0], tile[1]
        # Skip tiles already occupied
        if any(u.x == tx and u.y == ty for u in board.units):
            continue

        if enemies:
            min_e = min(dist(tx, ty, e.x, e.y) for e in enemies)
            avg_e = sum(dist(tx, ty, e.x, e.y) for e in enemies) / len(enemies)
        else:
            min_e, avg_e = 8.0, 8.0

        near_bldg = sum(1 for bx, by in buildings if dist(tx, ty, bx, by) <= 2)
        visual_row = 8 - tx
        forward = 1.0 if 4 <= visual_row <= 6 else 0.0

        score = (-min_e * 3.0       # get within striking range
                 + near_bldg * 2.0   # protect nearby buildings
                 + forward * 5.0     # reward forward positioning
                 - avg_e * 1.0)      # prefer overall closer to enemies
        scored.append((score, tx, ty))

    scored.sort(key=lambda s: s[0], reverse=True)

    # Greedy pick with diversity: avoid clustering within 1 tile
    selected = []
    for score, tx, ty in scored:
        if len(selected) >= 3:
            break
        too_close = any(dist(tx, ty, sx, sy) <= 1 for sx, sy in selected)
        if too_close and len(scored) > len(selected) + 3:
            continue
        selected.append((tx, ty))

    # Ensure at least one tile is "forward" (rows 4-6 = bridge x 2-4)
    has_forward = any(2 <= tx <= 4 for tx, ty in selected)
    if not has_forward and len(selected) == 3:
        for score, tx, ty in scored:
            if 2 <= tx <= 4 and (tx, ty) not in selected:
                selected[-1] = (tx, ty)
                break

    return selected


def cmd_auto_mission(profile: str = "Alpha", time_limit: float = 10.0,
                     max_turns: int = 20) -> dict:
    """Execute a complete mission via bridge: deploy -> combat turns -> mission end.

    Handles deployment automatically. Loops auto_turn until mission ends
    or game over. Falls back to Claude for reward selection, shop, etc.

    Returns dict with mission results or error.
    """
    if not is_bridge_active():
        result = {"error": "Bridge not active — auto_mission requires bridge"}
        _print_result(result)
        return result

    print(f"\n{'='*50}")
    print(f"AUTO MISSION START")
    print(f"{'='*50}")

    # Read initial state
    refresh_bridge_state()
    board, bridge_data = read_bridge_state()
    if board is None or bridge_data is None:
        result = {"error": "Failed to read bridge state"}
        _print_result(result)
        return result

    phase = bridge_data.get("phase", "unknown")
    turn = bridge_data.get("turn", 0)

    # Handle deployment (turn 0 with deployment zone)
    deploy_zone = bridge_data.get("deployment_zone", [])
    if turn == 0 and deploy_zone:
        print(f"\n--- DEPLOYMENT ({len(deploy_zone)} tiles available) ---")
        mechs = [u for u in board.units if u.is_mech and u.hp > 0]
        if mechs:
            # Rank tiles strategically: proximity to enemies + buildings
            ranked = rank_deploy_tiles(board, deploy_zone)
            if not ranked:
                ranked = [(t[0], t[1]) for t in deploy_zone[:3]]

            # Assign mechs: melee (Prime) gets forward tile, artillery gets back
            melee_types = {"PunchMech", "JudoMech", "ChargeMech",
                           "NanoMech", "LeapMech", "GravMech",
                           "TeleMech", "ExchangeMech"}
            melee = [m for m in mechs if m.type in melee_types]
            others = [m for m in mechs if m.type not in melee_types]
            # Melee mechs first (get forward tiles), then others
            ordered_mechs = melee + others

            for i, mech in enumerate(ordered_mechs):
                if i >= len(ranked):
                    print(f"  WARN: not enough ranked tiles for {mech.uid}")
                    break
                dx, dy = ranked[i]
                visual_row = 8 - dx
                visual_col = chr(72 - dy)
                print(f"  Deploying {mech.type} (uid={mech.uid}) "
                      f"to {visual_col}{visual_row} ({dx},{dy})")
                try:
                    ack = deploy_mech(mech.uid, dx, dy)
                    print(f"    ACK: {ack}")
                except (TimeoutError, BridgeError) as e:
                    result = {"error": f"Deploy failed for {mech.type}: {e}"}
                    _print_result(result)
                    return result
            print(f"  All {len(ordered_mechs)} mechs deployed")
        # Re-read state after deployment
        import time as _time
        _time.sleep(1)
        refresh_bridge_state()
        board, bridge_data = read_bridge_state()
        if board is None:
            result = {"error": "Failed to read state after deployment"}
            _print_result(result)
            return result

    # Combat loop
    turns_completed = 0
    mission_result = {"status": "unknown"}

    for t in range(max_turns):
        # Check phase
        refresh_bridge_state()
        board, bridge_data = read_bridge_state()
        if board is None:
            result = {"error": f"Bridge read failed at turn loop {t}",
                      "turns_completed": turns_completed}
            _print_result(result)
            return result

        phase = bridge_data.get("phase", "unknown")

        if phase == "combat_player":
            turn_result = cmd_auto_turn(profile=profile, time_limit=time_limit)

            if "error" in turn_result:
                result = {"error": turn_result["error"],
                          "turns_completed": turns_completed}
                _print_result(result)
                return result

            turns_completed += 1

            if turn_result.get("game_over"):
                mission_result = {
                    "status": "game_over",
                    "turns_completed": turns_completed,
                    "last_grid": turn_result.get("grid_power"),
                }
                break

            post_phase = turn_result.get("post_phase", "unknown")
            if post_phase in ("mission_ending", "between_missions",
                              "unknown"):
                # Mission may have ended — check more carefully
                import time as _time
                _time.sleep(2)
                refresh_bridge_state()
                check_board, check_data = read_bridge_state()
                if check_data:
                    check_phase = check_data.get("phase", "unknown")
                    if check_phase != "combat_player":
                        mission_result = {
                            "status": "mission_complete",
                            "turns_completed": turns_completed,
                            "final_grid": turn_result.get("grid_power"),
                        }
                        break

        elif phase == "combat_enemy":
            # Still in enemy phase, wait
            import time as _time
            _time.sleep(3)
            continue

        else:
            # Unknown phase — mission may have ended
            mission_result = {
                "status": "phase_exit",
                "phase": phase,
                "turns_completed": turns_completed,
            }
            break
    else:
        mission_result = {
            "status": "max_turns_reached",
            "turns_completed": turns_completed,
        }

    # Write mission summary
    session = _load_session()

    # Force-flush the final turn's post_enemy record. cmd_read normally
    # triggers _record_post_enemy when it sees the turn advance, but on
    # mission_ending / game_over the loop exits before that read fires
    # for the last solved turn. The dedup guard inside _record_post_enemy
    # makes the call a no-op if cmd_read already did the work.
    if session.active_solution is not None:
        try:
            refresh_bridge_state()
            final_board, _ = read_bridge_state()
            if final_board is not None:
                _record_post_enemy(session, final_board,
                                   session.active_solution.turn)
                session.active_solution = None
                session.save()
        except Exception as e:
            print(f"  WARN: post-enemy flush failed: {e}")

    final_grid = mission_result.get("final_grid", mission_result.get("last_grid", ""))
    _write_mission_summary(session, turns_completed, str(final_grid))

    print(f"\n{'='*50}")
    print(f"AUTO MISSION COMPLETE: {mission_result['status']}")
    print(f"  Turns: {turns_completed}")
    print(f"{'='*50}")

    _print_result(mission_result)
    return mission_result


def _cmd_validate_failures_only(old_version, new_version, old_weights,
                                new_weights, board_files, record_for_file,
                                time_limit):
    """Tuner-targeted validation: only the failure-corpus boards.

    Per-board outcome rules:
      Fixed     — original trigger no longer fires AND new fixed_score >= old
      Regressed — new fixed_score < old, OR new triggers a stricter
                  prediction failure that the old run did not
      Neutral   — everything else
    """
    from src.solver.analysis import detect_triggers
    from src.solver.solver import replay_solution

    print(f"\n{'='*50}")
    print(f"VALIDATE --failures-only: {old_version} vs {new_version}")
    print(f"  Failure boards: {len(board_files)}")
    print(f"{'='*50}")

    fixed = 0
    regressed = 0
    neutral = 0
    errors = 0
    detail_rows: list[dict] = []

    for i, bf in enumerate(board_files):
        rec = record_for_file[str(bf)]
        original_trigger = rec.get("trigger", "")

        try:
            bridge_data, board, spawns, _ = _load_board_from_recording(bf)
        except Exception:
            errors += 1
            continue

        try:
            sol_old = _solve_with_rust(bridge_data, time_limit, weights=old_weights)
            sol_new = _solve_with_rust(bridge_data, time_limit, weights=new_weights)
        except Exception as e:
            errors += 1
            if i == 0:
                print(f"  Rust solver error: {e}")
            continue

        # Replay both solutions and grab the score breakdown.
        outcome_old = {"buildings_alive": 0, "grid_power": 0, "mechs_alive": 0}
        outcome_new = {"buildings_alive": 0, "grid_power": 0, "mechs_alive": 0}
        old_solve_data = {}
        new_solve_data = {}
        if sol_old.actions:
            enriched_old = replay_solution(board.copy(), sol_old, spawns)
            outcome_old = enriched_old.get("predicted_outcome", outcome_old)
            old_solve_data = {
                "actions": [{
                    "mech_uid": a.mech_uid, "mech_type": a.mech_type,
                    "move_to": list(a.move_to) if a.move_to else None,
                    "weapon": a.weapon, "target": list(a.target),
                    "description": a.description,
                } for a in sol_old.actions],
                "action_results": enriched_old.get("action_results", []),
                "search_stats": {"timed_out": sol_old.timed_out},
            }
        if sol_new.actions:
            enriched_new = replay_solution(board.copy(), sol_new, spawns)
            outcome_new = enriched_new.get("predicted_outcome", outcome_new)
            new_solve_data = {
                "actions": [{
                    "mech_uid": a.mech_uid, "mech_type": a.mech_type,
                    "move_to": list(a.move_to) if a.move_to else None,
                    "weapon": a.weapon, "target": list(a.target),
                    "description": a.description,
                } for a in sol_new.actions],
                "action_results": enriched_new.get("action_results", []),
                "search_stats": {"timed_out": sol_new.timed_out},
            }

        score_old = _fixed_score(outcome_old)
        score_new = _fixed_score(outcome_new)

        # Re-detect the trigger using the offline-replay shortcut: feed
        # predicted = actual so only tier-3/4 triggers can fire (search /
        # rule-violation triggers — exactly what tuning can move).
        empty_deltas = {
            "buildings_alive_diff": 0,
            "grid_power_diff": 0,
            "mech_hp_diff": [],
        }
        new_triggers = detect_triggers(
            actual=outcome_new, predicted=outcome_new,
            deltas=empty_deltas, solve_data=new_solve_data, board=board,
        )
        new_trigger_names = {t["trigger"] for t in new_triggers}

        still_fires = original_trigger in new_trigger_names

        if not still_fires and score_new >= score_old:
            outcome_label = "fixed"
            fixed += 1
        elif score_new < score_old:
            outcome_label = "regressed"
            regressed += 1
        else:
            outcome_label = "neutral"
            neutral += 1

        detail_rows.append({
            "board": str(bf.relative_to(RECORDING_DIR)),
            "trigger": original_trigger,
            "old_score": score_old,
            "new_score": score_new,
            "outcome": outcome_label,
        })

    tested = fixed + regressed + neutral
    verdict = "PASS" if regressed == 0 and fixed > 0 else (
        "PASS" if regressed == 0 else "FAIL"
    )

    result = {
        "mode": "failures_only",
        "old_version": old_version,
        "new_version": new_version,
        "boards_tested": tested,
        "boards_skipped": errors,
        "fixed": fixed,
        "regressed": regressed,
        "neutral": neutral,
        "verdict": verdict,
        "details": detail_rows[:25],  # cap printout
    }

    print(f"\n{'='*50}")
    print(f"FAILURES-ONLY RESULTS: {old_version} vs {new_version}")
    print(f"  Boards tested: {tested} (skipped: {errors})")
    print(f"  Fixed:     {fixed}")
    print(f"  Regressed: {regressed}")
    print(f"  Neutral:   {neutral}")
    print(f"  VERDICT:   {verdict}")
    print(f"{'='*50}")

    _print_result(result)
    return result


def cmd_validate(old_weights_path: str, new_weights_path: str,
                 time_limit: float = 10.0, solver_version: str = None,
                 failures_only: bool = False) -> dict:
    """Compare two weight versions across recorded boards.

    Default mode: runs both weight sets on every recorded board and
    reports which version is better via the fixed (weight-independent)
    scorer plus regression gates.

    ``--failures-only``: restricts the corpus to boards referenced by
    the failure database, deduped by ``(run_id, mission, trigger)``.
    Reports per-failure outcomes (Fixed / Regressed / Neutral) under
    a stricter success metric — a failure is "fixed" only if the same
    trigger no longer fires AND the new fixed_score is >= old fixed_score
    (so the tuner can't game it by sidestepping the situation).
    """
    from src.solver.solver import Solution
    from src.solver.analysis import detect_triggers, load_failure_db

    # Load weight files
    old_path, new_path = Path(old_weights_path), Path(new_weights_path)
    if not old_path.exists():
        result = {"error": f"Old weights not found: {old_path}"}
        _print_result(result)
        return result
    if not new_path.exists():
        result = {"error": f"New weights not found: {new_path}"}
        _print_result(result)
        return result

    with open(old_path) as f:
        old_data = json.load(f)
    with open(new_path) as f:
        new_data = json.load(f)

    old_weights = old_data.get("weights", {})
    new_weights = new_data.get("weights", {})
    old_version = old_data.get("version", "old")
    new_version = new_data.get("version", "new")

    # Failures-only mode: build the corpus from the failure database,
    # deduped by (run_id, mission, trigger). Each unique key resolves
    # to the replay_file recorded on the trigger.
    if failures_only:
        records = load_failure_db()
        seen_keys: set = set()
        failure_records: list = []
        for r in records:
            # Skip audit-mode runs — same rationale as the tuner filter.
            if "audit" in r.get("context", {}).get("tags", []):
                continue
            key = (r.get("run_id"), r.get("mission"), r.get("trigger"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            failure_records.append(r)

        repo_root = Path(__file__).resolve().parent.parent.parent
        board_files = []
        record_for_file = {}
        for rec in failure_records:
            replay_rel = rec.get("replay_file", "")
            if not replay_rel:
                continue
            replay_path = repo_root / replay_rel
            if not replay_path.exists():
                continue
            board_files.append(replay_path)
            record_for_file[str(replay_path)] = rec

        if not board_files:
            result = {
                "error": "No failure records resolve to existing replay files",
                "failure_records_total": len(failure_records),
            }
            _print_result(result)
            return result

        return _cmd_validate_failures_only(
            old_version, new_version, old_weights, new_weights,
            board_files, record_for_file, time_limit,
        )

    # Find all board recordings
    board_files = []
    for run_dir in sorted(RECORDING_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        # Check solver version filter
        if solver_version:
            manifest = run_dir / "manifest.json"
            if manifest.exists():
                try:
                    with open(manifest) as f:
                        m = json.load(f)
                    if m.get("solver_version", "") != solver_version:
                        continue
                except (json.JSONDecodeError, OSError):
                    pass
        # Collect board files (new + old naming)
        board_files.extend(sorted(run_dir.glob("m*_turn_*_board.json")))
        board_files.extend(sorted(run_dir.glob("turn_*_board.json")))

    if not board_files:
        result = {"error": "No board recordings found"}
        _print_result(result)
        return result

    print(f"\n{'='*50}")
    print(f"VALIDATE: {old_version} vs {new_version}")
    print(f"  Boards: {len(board_files)}")
    print(f"{'='*50}")

    # Test each board
    new_better = 0
    old_better = 0
    ties = 0
    errors = 0
    critical_regressions = []

    for i, bf in enumerate(board_files):
        try:
            bridge_data, board, spawns, _ = _load_board_from_recording(bf)
        except Exception:
            errors += 1
            continue

        try:
            sol_old = _solve_with_rust(bridge_data, time_limit, weights=old_weights)
            sol_new = _solve_with_rust(bridge_data, time_limit, weights=new_weights)
        except Exception as e:
            errors += 1
            if i == 0:
                print(f"  Rust solver error: {e}")
            continue

        # Simulate both solutions
        outcome_old = {"buildings_alive": 0, "grid_power": 0, "mechs_alive": 0}
        outcome_new = {"buildings_alive": 0, "grid_power": 0, "mechs_alive": 0}
        if sol_old.actions:
            enriched = replay_solution(board, sol_old, spawns)
            if enriched:
                outcome_old = enriched.get("predicted_outcome", outcome_old)
        if sol_new.actions:
            enriched = replay_solution(board.copy(), sol_new, spawns)
            if enriched:
                outcome_new = enriched.get("predicted_outcome", outcome_new)

        score_old = _fixed_score(outcome_old)
        score_new = _fixed_score(outcome_new)

        if score_new > score_old:
            new_better += 1
        elif score_old > score_new:
            old_better += 1
            # Check if new version loses buildings that old saved
            bld_old = outcome_old.get("buildings_alive", 0)
            bld_new = outcome_new.get("buildings_alive", 0)
            if bld_new < bld_old:
                critical_regressions.append(str(bf.relative_to(RECORDING_DIR)))
        else:
            ties += 1

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(board_files)} boards tested")

    tested = new_better + old_better + ties
    regression_rate = old_better / tested * 100 if tested > 0 else 0
    verdict = "PASS" if (regression_rate <= 20 and len(critical_regressions) == 0) else "FAIL"

    result = {
        "old_version": old_version,
        "new_version": new_version,
        "boards_tested": tested,
        "boards_skipped": errors,
        "new_better": new_better,
        "old_better": old_better,
        "ties": ties,
        "regression_rate": round(regression_rate, 1),
        "critical_regressions": len(critical_regressions),
        "regression_boards": critical_regressions[:10],
        "verdict": verdict,
    }

    print(f"\n{'='*50}")
    print(f"RESULTS: {old_version} vs {new_version}")
    print(f"  Boards tested: {tested} (skipped: {errors})")
    print(f"  New better: {new_better} ({new_better*100/tested:.0f}%)" if tested else "")
    print(f"  Old better: {old_better} ({regression_rate:.0f}%)" if tested else "")
    print(f"  Ties:       {ties}")
    print(f"  Critical regressions: {len(critical_regressions)}")
    print(f"  VERDICT: {verdict}")
    print(f"{'='*50}")

    _print_result(result)
    return result


def cmd_tune(iterations: int = 100, min_boards: int = 50,
             time_limit: float = 5.0) -> dict:
    """Auto-tune solver weights by replaying recorded boards.

    Uses random search + coordinate refinement to find weight values
    that maximize the fixed (weight-independent) score across all
    recorded board states. Saves the best weights to a new version file
    and validates against the current weights.

    Data gate: refuses to run with fewer than min_boards recordings.
    """
    from src.solver.tuner import tune_weights

    # Collect all board files
    board_files = []
    for run_dir in sorted(RECORDING_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        board_files.extend(sorted(run_dir.glob("m*_turn_*_board.json")))
        board_files.extend(sorted(run_dir.glob("turn_*_board.json")))

    # Data gate
    if len(board_files) < min_boards:
        result = {
            "error": f"Not enough data: {len(board_files)} boards "
                     f"(need {min_boards}). Collect more games first.",
            "boards_found": len(board_files),
            "min_boards": min_boards,
        }
        print(f"\n  DATA GATE: {len(board_files)}/{min_boards} boards. "
              f"Need {min_boards - len(board_files)} more.")
        _print_result(result)
        return result

    print(f"\n{'='*50}")
    print(f"WEIGHT AUTO-TUNING")
    print(f"  Boards: {len(board_files)}")
    print(f"  Iterations: {iterations}")
    print(f"  Time limit per board: {time_limit}s")
    print(f"{'='*50}")

    # Load failure corpus for tuner penalty term
    from src.solver.analysis import load_failure_db, is_auto_fixable_by_tuning
    raw_corpus = [r for r in load_failure_db() if is_auto_fixable_by_tuning(r)]
    seen = set()
    deduped = []
    for r in raw_corpus:
        key = (r.get("run_id"), r.get("mission"), r.get("trigger"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    failure_corpus = deduped[:20]
    if failure_corpus:
        print(f"  Failure corpus: {len(failure_corpus)} records "
              f"(from {len(raw_corpus)} total)")

    # Run tuning
    t0 = time.time()
    tune_result = tune_weights(board_files, iterations=iterations,
                               time_limit=time_limit,
                               failure_corpus=failure_corpus)
    elapsed = time.time() - t0

    improvement = tune_result["improvement"]
    improvement_pct = tune_result["improvement_pct"]

    print(f"\n{'='*50}")
    print(f"TUNING COMPLETE ({elapsed:.0f}s)")
    print(f"  Baseline: {tune_result['baseline_score']:.1f}")
    print(f"  Best:     {tune_result['best_score']:.1f} "
          f"({'+' if improvement >= 0 else ''}{improvement:.1f}, "
          f"{improvement_pct:+.1f}%)")
    print(f"  Tuned weights:")
    for k, v in tune_result["tuned_params"].items():
        print(f"    {k:20s} = {v:.1f}")
    print(f"{'='*50}")

    # Save new weights if improved
    if improvement > 0:
        weights_dir = Path(__file__).parent.parent.parent / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)

        # Find next version number
        existing = sorted(weights_dir.glob("v*_*.json"))
        next_num = 2
        for ef in existing:
            try:
                num = int(ef.stem.split("_")[0][1:])
                next_num = max(next_num, num + 1)
            except (ValueError, IndexError):
                pass

        version = f"v{next_num:03d}"
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d")
        new_path = weights_dir / f"{version}_{timestamp}.json"

        new_weight_data = {
            "version": version,
            "parent": _get_weight_version(),
            "description": f"Auto-tuned from {_get_weight_version()} "
                           f"({improvement_pct:+.1f}% on {len(board_files)} boards)",
            "created": datetime.now().isoformat(),
            "weights": tune_result["best_weights"],
            "stats": {
                "boards_tested": len(board_files),
                "iterations": tune_result["iterations_used"],
                "baseline_score": tune_result["baseline_score"],
                "tuned_score": tune_result["best_score"],
                "improvement_pct": round(improvement_pct, 2),
            },
        }

        _atomic_json_write(new_path, new_weight_data)
        print(f"\n  Saved: {new_path}")

        # Validate against current weights
        old_path = weights_dir / "active.json"
        print(f"\n  Validating {_get_weight_version()} vs {version}...")
        val_result = cmd_validate(str(old_path), str(new_path),
                                  time_limit=time_limit)

        if val_result.get("verdict") == "PASS":
            # Deploy as active
            import shutil
            shutil.copy2(new_path, old_path)
            print(f"\n  DEPLOYED: {version} is now active!")
        else:
            print(f"\n  NOT DEPLOYED: validation failed "
                  f"(regression rate {val_result.get('regression_rate', '?')}%)")

        tune_result["weight_file"] = str(new_path)
        tune_result["validation"] = val_result.get("verdict", "unknown")
    else:
        print(f"\n  No improvement found. Current weights are optimal "
              f"for this data set.")

    tune_result["elapsed_seconds"] = round(elapsed, 1)
    _print_result(tune_result)
    return tune_result


def cmd_analyze(min_samples: int = 30) -> dict:
    """Analyze the failure database for patterns and trends.

    Reads recordings/failure_db.jsonl and reports trigger frequencies,
    root-cause breakdowns, and gated pattern analysis.
    """
    from src.solver.analysis import analyze_failures

    report = analyze_failures(min_samples=min_samples)
    total = report.get("total_records", 0)

    print(f"\n{'='*50}")
    print(f"FAILURE ANALYSIS — {total} records")
    print(f"{'='*50}")

    if total == 0:
        print("  No failure records found. Run some games first!")
        _print_result(report)
        return report

    # By root cause
    print(f"\nRoot Causes:")
    for rc, count in report.get("by_root_cause", {}).items():
        pct = count * 100 / total
        print(f"  {rc:25s} {count:4d} ({pct:5.1f}%)")

    # By severity
    print(f"\nSeverity:")
    for sev in ["critical", "high", "medium"]:
        count = report.get("by_severity", {}).get(sev, 0)
        pct = count * 100 / total
        print(f"  {sev:25s} {count:4d} ({pct:5.1f}%)")

    # By trigger type
    print(f"\nTrigger Types:")
    for trigger, count in report.get("by_trigger", {}).items():
        pct = count * 100 / total
        print(f"  {trigger:35s} {count:4d} ({pct:5.1f}%)")

    # By tier
    print(f"\nTiers:")
    for tier, count in report.get("by_tier", {}).items():
        pct = count * 100 / total
        print(f"  Tier {tier:2d}                       {count:4d} ({pct:5.1f}%)")

    # Gated breakdowns
    if "by_squad" in report:
        print(f"\nBy Squad:")
        for squad, count in report["by_squad"].items():
            print(f"  {squad:25s} {count:4d}")
    elif "by_squad_note" in report:
        print(f"\n  {report['by_squad_note']}")

    if "by_turn" in report:
        print(f"\nBy Turn:")
        for turn, count in report["by_turn"].items():
            print(f"  Turn {turn:2d}                       {count:4d}")
    elif "by_turn_note" in report:
        print(f"\n  {report['by_turn_note']}")

    _print_result(report)
    return report


def cmd_mission_end(outcome: str, notes: str = None) -> dict:
    """Record mission outcome on the active run.

    outcome: "win" or "loss"
    notes: optional free-text context

    Writes outcome to the run manifest.json and drops a small
    m{NN}_outcome.json pointer file in the run directory.
    """
    if outcome not in ("win", "loss"):
        return {"error": f"outcome must be 'win' or 'loss', got {outcome!r}"}

    session = RunSession.load()
    if not session.run_id:
        return {"error": "No active run. Start one with `new_run`."}

    run_dir = _recording_dir(session)
    mi = session.mission_index

    # Write mission-level outcome pointer
    outcome_data = {
        "mission_index": mi,
        "mission_name": session.current_mission,
        "result": outcome,
        "notes": notes,
        "recorded_at": datetime.now().isoformat(),
    }
    outcome_path = run_dir / f"m{mi:02d}_outcome.json"
    _atomic_json_write(outcome_path, outcome_data)

    # Update manifest with run-level outcome (the LATEST mission wins in the
    # manifest field; historical outcomes live in the per-mission files).
    _write_manifest(session, {
        "outcome": outcome,
        "outcome_mission": mi,
        "outcome_recorded_at": datetime.now().isoformat(),
        "outcome_notes": notes,
    })

    result = {
        "run_id": session.run_id,
        "mission": mi,
        "outcome": outcome,
        "outcome_file": str(outcome_path.relative_to(
            Path(__file__).parent.parent.parent)),
        "manifest_updated": True,
    }
    _print_result(result)
    print(
        "\n[reminder] If you changed solver code this session, "
        "run `bash scripts/regression.sh` before committing. "
        "(The pre-commit hook will also auto-run it — install via "
        "`bash scripts/install-hooks.sh` on a fresh checkout.)"
    )
    return result


def cmd_annotate(run_id: str, turn: int, notes: str,
                 mission: int = 0) -> dict:
    """Add a notes field to a recorded board JSON.

    Useful for tagging "this turn exercises X bug" so future regression
    triage has context. Edits the board recording in-place (top-level
    `notes` key only — bridge data is left immutable).
    """
    board_file = (
        RECORDING_DIR / run_id / f"m{mission:02d}_turn_{turn:02d}_board.json"
    )
    if not board_file.exists():
        return {"error": f"Recording not found: {board_file}"}

    with open(board_file) as f:
        record = json.load(f)

    record["notes"] = notes
    record["annotated_at"] = datetime.now().isoformat()

    _atomic_json_write(board_file, record)

    result = {
        "file": str(board_file.relative_to(Path(__file__).parent.parent.parent)),
        "notes": notes,
    }
    _print_result(result)
    return result


def _print_result(result: dict):
    """Print result as formatted JSON to stdout."""
    # Filter out click lists for cleaner output
    display = {}
    for k, v in result.items():
        if k == "clicks":
            display[k] = f"[{len(v)} steps]"
        else:
            display[k] = v

    print(f"\n--- Result ---")
    print(json.dumps(display, indent=2, default=str))
