"""Game loop subcommand implementations.

Each command is a pure function: load state -> compute -> output -> save state.
Commands are called by the CLI dispatcher (game_loop.py) and by Claude
through the computer-use MCP tool.

The session file persists state between CLI invocations.
The decision log records every action for post-run analysis.
"""

from __future__ import annotations

import json
import shutil
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
from src.solver.solver import solve_turn, MechAction
from src.solver.evaluate import evaluate_threats
from src.control.executor import (
    plan_single_mech,
    plan_end_turn,
    get_mech_portraits,
    grid_to_mcp,
    recalibrate,
)
from src.capture.detect_grid import find_game_window, grid_from_window
from src.bridge.protocol import is_bridge_active
from src.bridge.reader import read_bridge_state
from src.bridge.writer import execute_bridge_action, execute_bridge_end_turn
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
                    {"type": m.type, "pos": f"({m.x},{m.y})",
                     "hp": f"{m.hp}/{m.max_hp}",
                     "weapon": get_weapon_name(m.weapon),
                     "status": "READY" if m.active else "DONE"}
                    for m in mechs
                ]
                result["active_mechs"] = len(active_mechs)

                enemies = board.enemies()
                result["enemies"] = [
                    {"type": e.type, "pos": f"({e.x},{e.y})",
                     "hp": f"{e.hp}/{e.max_hp}",
                     "target": f" -> ({e.target_x},{e.target_y})" if e.target_x >= 0 else ""}
                    for e in enemies
                ]

                threats = board.get_threatened_buildings()
                result["threatened_buildings"] = len(threats)
                if threats:
                    result["threats"] = [
                        f"Building ({x},{y}) by {u.type} at ({u.x},{u.y})"
                        for x, y, u in threats
                    ]

                targeted = bridge_data.get("targeted_tiles", [])
                result["targeted_tiles"] = len(targeted)
                spawning = bridge_data.get("spawning_tiles", [])
                result["spawn_points"] = len(spawning)

                print(f"\n{'='*50}")
                print(f"BOARD STATE (BRIDGE) — Turn {bridge_data.get('turn', '?')} | "
                      f"Grid: {board.grid_power}/{board.grid_power_max} | "
                      f"Phase: {phase}")
                print(f"{'='*50}")
                board.print_board()

            if old_phase != phase and old_phase != "unknown":
                logger = _get_logger(session)
                logger.log_phase_transition(old_phase, phase)

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
                "pos": f"({mech.x},{mech.y})",
                "hp": f"{mech.hp}/{mech.max_hp}",
                "weapon": weapon_name,
                "status": status,
            })
        result["active_mechs"] = len(active_mechs)

        # Enemies
        enemies = board.enemies()
        result["enemies"] = []
        for e in enemies:
            target = f" -> ({e.target_x},{e.target_y})" if e.target_x >= 0 else ""
            result["enemies"].append({
                "type": e.type,
                "pos": f"({e.x},{e.y})",
                "hp": f"{e.hp}/{e.max_hp}",
                "target": target,
            })

        # Threats
        threats = board.get_threatened_buildings()
        result["threatened_buildings"] = len(threats)
        if threats:
            result["threats"] = [
                f"Building ({x},{y}) by {u.type} at ({u.x},{u.y})"
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

    state = load_game_state(profile)
    if state is None or state.active_mission is None:
        result = {"error": "No active mission to solve"}
        _print_result(result)
        return result

    m = state.active_mission
    board = Board.from_mission(m, state.grid_power, state.grid_power_max)
    spawns = [(p.x, p.y) for p in m.spawn_points]

    # Check for active mechs
    active_mechs = [mech for mech in board.mechs() if mech.active and mech.hp > 0]
    if not active_mechs:
        result = {"error": "No active mechs — all have acted this turn"}
        _print_result(result)
        return result

    # Run solver
    print(f"\nSolving ({len(active_mechs)} active mechs, {time_limit}s limit)...")
    solution = solve_turn(board, spawn_points=spawns, time_limit=time_limit)

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
    session.set_solution(solver_actions, solution.score, m.current_turn)

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
        except TimeoutError as e:
            result = {"error": str(e), "bridge": True}
            print(f"  ERROR: {e}")

        session.save()
        _print_result(result)
        return result

    # MCP mode: return click plan
    state = load_game_state(profile)
    board = None
    portraits = {}
    if state and state.active_mission:
        board = Board.from_mission(
            state.active_mission, state.grid_power, state.grid_power_max
        )
        portraits = get_mech_portraits(board)

    portrait_idx = portraits.get(action.mech_type, action_index)
    clicks = plan_single_mech(mech_action, portrait_idx, board)

    logger.log_mech_action(action_index, action.description, len(clicks))

    result = {
        "action_index": action_index,
        "mech_type": action.mech_type,
        "description": action.description,
        "clicks": clicks,
    }

    print(f"\n=== EXECUTE Action {action_index}: {action.description} ===")
    for i, c in enumerate(clicks):
        if c["type"] == "click":
            print(f"  {i+1}. CLICK ({c['x']}, {c['y']}) -- {c['description']}")
        elif c["type"] == "key":
            print(f"  {i+1}. KEY '{c['text']}' -- {c['description']}")
        elif c["type"] == "wait":
            print(f"  {i+1}. WAIT {c['duration']}s -- {c['description']}")

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


def cmd_end_turn() -> dict:
    """End the current turn.

    In bridge mode: sends END_TURN command directly.
    In MCP mode: returns click plan for End Turn button.
    """
    session = _load_session()
    logger = _get_logger(session)
    logger.log_end_turn()

    # Bridge mode
    if is_bridge_active():
        print("\n=== BRIDGE END TURN ===")
        try:
            ack = execute_bridge_end_turn()
            print(f"  ACK: {ack}")
            result = {"bridge": True, "ack": ack}
        except TimeoutError as e:
            result = {"error": str(e), "bridge": True}
            print(f"  ERROR: {e}")

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
                difficulty: int = 0) -> dict:
    """Initialize a new run session."""
    session = RunSession.new_run(squad, achievements, difficulty)
    session.save()

    logger = DecisionLog(session.run_id)
    logger.log_custom("New Run", (
        f"Squad: {squad}\n"
        f"Achievements: {achievements or 'none'}\n"
        f"Difficulty: {difficulty}"
    ))

    result = {
        "run_id": session.run_id,
        "squad": squad,
        "achievements": achievements or [],
    }
    print(f"\nNew run initialized: {session.run_id}")
    print(f"  Squad: {squad}")
    if achievements:
        print(f"  Targeting: {', '.join(achievements)}")

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
