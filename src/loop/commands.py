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
    plan_balanced_roll,
    grid_to_mcp,
    recalibrate,
)
from src.capture.detect_grid import find_game_window, grid_from_window
from src.bridge.protocol import (
    is_bridge_active, refresh_bridge_state, read_state, BridgeError,
)
from src.bridge.reader import read_bridge_state
from src.bridge.writer import (
    execute_bridge_action, execute_bridge_end_turn,
    deploy_mech, set_bridge_speed,
    move_mech, attack_mech, skip_mech, repair_mech,
)
from src.loop.session import RunSession, SolverAction, DEFAULT_SESSION_FILE
from src.loop.logger import DecisionLog
from src.loop import weapon_penalty_log

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


# Difficulty label map (mirrors GameData.difficulty values)
_DIFFICULTY_LABELS = {0: "Easy", 1: "Normal", 2: "Hard", 3: "Unfair"}


def _read_save_file_difficulty(profile: str = "Alpha") -> int | None:
    """Return the in-game difficulty (0/1/2/3) from the save file, or None.

    Authoritative source for the live difficulty (see CLAUDE.md note on
    Timeline Lost continuations: ``session.difficulty`` is stale Python
    metadata and must be cross-checked against this value at the start
    of each turn).
    """
    try:
        state = load_game_state(profile)
    except Exception:
        return None
    if state is None:
        return None
    diff = getattr(state, "difficulty", None)
    if isinstance(diff, int):
        return diff
    return None


def _visual_to_bridge(pos: str) -> tuple[int, int] | None:
    """Reverse of ``_bv``: 'C5' -> (3, 5). Returns None on malformed input."""
    if not isinstance(pos, str) or len(pos) < 2:
        return None
    col_char = pos[0].upper()
    row_str = pos[1:]
    if not row_str.isdigit():
        return None
    try:
        y = 72 - ord(col_char)
        x = 8 - int(row_str)
    except (TypeError, ValueError):
        return None
    if not (0 <= x < 8 and 0 <= y < 8):
        return None
    return (x, y)


def _read_last_resist_entry(log_path: Path, run_id: str,
                            region: str | None) -> dict | None:
    """Return the most recent probe entry for ``(run_id, region)``.

    Reads the whole JSONL (each run_id has its own directory so files are
    small) and scans bottom-up. Returns ``None`` if no match. Malformed
    lines are ignored — the probe is observational and must not break on
    log corruption.
    """
    if not log_path.exists():
        return None
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("run_id") != run_id:
            continue
        if obj.get("region") != region:
            continue
        return obj
    return None


def _first_grid_power_for_turn(log_path: Path, run_id: str,
                               region: str | None, turn: int) -> int | None:
    """Return the grid_power of the FIRST probe entry for (run_id, region,
    turn). Auto_turn polls the bridge multiple times per player turn; the
    first poll of a given turn sits nearest to the turn boundary and is
    the cleanest anchor for turn-to-turn `grid_power_delta`. Using the
    LAST entry of the previous turn conflates enemy-phase damage with
    whatever intra-turn mech actions happened after the poll fired.
    """
    if not log_path.exists() or turn is None:
        return None
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("run_id") != run_id:
            continue
        if obj.get("region") != region:
            continue
        if obj.get("turn") != turn:
            continue
        gp = obj.get("grid_power")
        if isinstance(gp, int):
            return gp
    return None


def _classify_resist_outcome(
    hp_before: int,
    hp_after: int,
    *,
    attacker_found: bool,
    attacker_pos_changed: bool,
    attacker_webbed: bool,
    target_smoked: bool,
) -> str:
    """Classify one telegraphed-attack outcome post-enemy-phase.

    Outcomes:
      destroyed:          hp_after == 0
      damaged:            hp_before > hp_after > 0
      resisted:           hp unchanged, attacker alive & at same pos,
                          not webbed, target not smoked — the ONLY case
                          where the roll-resist hypothesis is testable.
      attacker_killed:    hp unchanged, specific attacker UID gone —
                          solver preempted; attack never fired.
      attacker_pushed:    hp unchanged, attacker alive but moved —
                          telegraph disrupted; attack may or may not
                          have fired at a different tile.
      attacker_webbed:    hp unchanged, attacker webbed — can't attack.
      target_smoked:      hp unchanged, target tile has smoke — attack
                          blocked by smoke (treated as 0-damage, not a
                          roll resist).
      unknown:            hp_after > hp_before (repair?) or unexpected.

    Priority: destroyed/damaged > disruption flags > resisted. We check
    disruption flags BEFORE calling this "resisted" because disrupted
    attacks look identical to resisted ones via the HP-diff test alone,
    and conflating them is what inflates the apparent resist rate.
    """
    if hp_after == 0:
        return "destroyed"
    if hp_before > hp_after > 0:
        return "damaged"
    if hp_after != hp_before:
        return "unknown"
    # HP unchanged. Determine why.
    if not attacker_found:
        return "attacker_killed"
    if attacker_pos_changed:
        return "attacker_pushed"
    if attacker_webbed:
        return "attacker_webbed"
    if target_smoked:
        return "target_smoked"
    return "resisted"


def _find_enemy_by_uid(board, uid: int):
    """Look up a specific enemy by UID. Returns None if not found."""
    if uid is None or uid < 0:
        return None
    for u in board.units:
        if u.uid == uid and u.is_enemy and u.hp > 0:
            return u
    return None


def _compute_resist_observations(prev_entry: dict, board,
                                 grid_power_now: int,
                                 prev_turn_start_grid_power: int | None = None
                                 ) -> list[dict]:
    """Diff previous-turn telegraphed attacks against current board state.

    Uses attacker UID (captured at telegraph time) to identify the specific
    attacker post-enemy-phase, so we can distinguish a true resist (attack
    fired, rolled 0 damage) from a disrupted attack (solver killed, pushed,
    or webbed the attacker before it could fire). The older implementation
    matched attackers by type name and produced ~70% false-positive resist
    rates when the solver preempted many attacks — see project memory
    `project_grid_defense_probe.md`.

    grid_power_delta compares against ``prev_turn_start_grid_power`` when
    provided (the grid value at the FIRST probe entry of the previous
    turn — i.e. the true turn boundary anchor). Falls back to
    ``prev_entry.grid_power`` which is the LAST entry of the previous
    turn; that fallback is noisy because auto_turn polls multiple times
    per turn and the last poll often lands after our mech actions have
    already destroyed buildings, masking the enemy-phase contribution.
    """
    observations: list[dict] = []
    prev_attacks = prev_entry.get("telegraphed_building_attacks") or []
    anchor_grid_power = (
        prev_turn_start_grid_power
        if isinstance(prev_turn_start_grid_power, int)
        else prev_entry.get("grid_power")
    )
    grid_power_delta = (
        grid_power_now - anchor_grid_power
        if isinstance(anchor_grid_power, int) else None
    )

    for attack in prev_attacks:
        target_pos = attack.get("target_pos")
        attacker_type = attack.get("attacker_type")
        attacker_pos_prev = attack.get("attacker_pos")
        attacker_uid = attack.get("attacker_uid")
        hp_before = attack.get("target_building_hp_before", 0)

        attacker = _find_enemy_by_uid(board, attacker_uid)
        attacker_found = attacker is not None
        attacker_pos_now = _bv(attacker.x, attacker.y) if attacker else None
        attacker_pos_changed = (
            attacker_found and attacker_pos_now != attacker_pos_prev
        )
        attacker_webbed = bool(attacker and attacker.web)

        coords = _visual_to_bridge(target_pos) if target_pos else None
        if coords is None:
            observations.append({
                "target_pos": target_pos,
                "attacker_type": attacker_type,
                "attacker_uid": attacker_uid,
                "attacker_pos_prev": attacker_pos_prev,
                "attacker_pos_now": attacker_pos_now,
                "hp_before": hp_before,
                "hp_after": None,
                "grid_power_delta": grid_power_delta,
                "attacker_found": attacker_found,
                "attacker_pos_changed": attacker_pos_changed,
                "attacker_webbed": attacker_webbed,
                "target_smoked": False,
                "inferred_outcome": "unknown",
            })
            continue
        tx, ty = coords
        tile = board.tiles[tx][ty]
        # If the tile is no longer a building (e.g. now rubble / ground),
        # treat HP as 0 — the building was destroyed.
        if tile.terrain != "building":
            hp_after = 0
        else:
            hp_after = tile.building_hp
        target_smoked = bool(tile.smoke)
        outcome = _classify_resist_outcome(
            hp_before, hp_after,
            attacker_found=attacker_found,
            attacker_pos_changed=attacker_pos_changed,
            attacker_webbed=attacker_webbed,
            target_smoked=target_smoked,
        )
        observations.append({
            "target_pos": target_pos,
            "attacker_type": attacker_type,
            "attacker_uid": attacker_uid,
            "attacker_pos_prev": attacker_pos_prev,
            "attacker_pos_now": attacker_pos_now,
            "hp_before": hp_before,
            "hp_after": hp_after,
            "grid_power_delta": grid_power_delta,
            "attacker_found": attacker_found,
            "attacker_pos_changed": attacker_pos_changed,
            "attacker_webbed": attacker_webbed,
            "target_smoked": target_smoked,
            "inferred_outcome": outcome,
        })
    return observations


def _log_resist_probe(session: RunSession, board, bridge_data: dict) -> None:
    """Log RNG seeds + telegraphed building attacks for the grid-defense probe.

    Writes one JSONL entry per player-turn-start to
    ``recordings/<run_id>/resist_probe.jsonl``. Each entry captures:

    - master_seed, ai_seed (from saveData.lua; ai_seed advances per turn)
    - grid_defense_pct, grid_power
    - telegraphed attacks landing on building tiles (the events whose
      resist outcome we want to predict)
    - ``resist_observations``: per-target outcome diffs against the
      previous entry's ``telegraphed_building_attacks``. Since the enemy
      phase runs between two consecutive player-turn snapshots, comparing
      the two tells us which buildings resisted, were damaged, or were
      destroyed — the ground-truth signal for grid-defense-roll replay.

    Pairing consecutive entries (plus observing final building HPs) lets us
    reconstruct which telegraphed attacks the game pre-rolled as resists,
    then attempt to replay the ``ai_seed`` locally through Lua's math.random
    to find the offset at which resist rolls appear.

    No-ops unless bridge reports a master_seed (i.e. save was readable).
    """
    if bridge_data.get("phase") != "combat_player":
        return
    master_seed = bridge_data.get("master_seed")
    if master_seed is None:
        return
    mission_id = bridge_data.get("mission_id") or ""
    mission_seeds = bridge_data.get("mission_seeds") or {}
    # Pick the active region — the one currently in combat. iState=0 marks
    # the mission that's actively being played; iState=4 is scouted /
    # not yet entered. The bridge's `mission_id` (e.g. "Mission_Survive")
    # is the template name, not the save-file's sMission slot (e.g.
    # "Mission7"), so we match on iState rather than name.
    active_seed = None
    active_region = None
    active_mission_slot = None
    for region_key, info in mission_seeds.items():
        if isinstance(info, dict) and info.get("state") == 0:
            active_seed = info.get("ai_seed")
            active_region = region_key
            active_mission_slot = info.get("mission")
            break
    # Telegraphed building attacks: enemy.target lands on a building tile.
    # Capture attacker UID so the next-turn diff can identify this specific
    # attacker (not just its type) — needed to distinguish a true resist
    # from a solver-preempted attack when multiple enemies of the same type
    # are on the board.
    telegraphed = []
    for e in board.enemies():
        if e.target_x < 0 or e.target_y < 0:
            continue
        tile = board.tiles[e.target_x][e.target_y]
        if tile.terrain != "building" or tile.building_hp <= 0:
            continue
        telegraphed.append({
            "attacker_uid": e.uid,
            "attacker_type": e.type,
            "attacker_pos": _bv(e.x, e.y),
            "target_pos": _bv(e.target_x, e.target_y),
            "target_building_hp_before": tile.building_hp,
        })
    # Outcome diff vs previous turn's telegraphed attacks. First snapshot
    # in a mission (and the first snapshot after a region swap) gets an
    # empty list. ``auto_turn`` may poll the bridge multiple times per
    # player turn; skip observation-recomputation if the last entry is
    # already for the same (region, turn) so we don't clobber the signal
    # with all-zero diffs on re-reads.
    run_id = session.run_id or "default"
    log_path = _recording_dir(session) / "resist_probe.jsonl"
    current_turn = bridge_data.get("turn", 0)
    prev_entry = _read_last_resist_entry(log_path, run_id, active_region)
    if (prev_entry is not None
            and prev_entry.get("turn") == current_turn
            and prev_entry.get("region") == active_region):
        # Reuse the observations we computed on the first read of this
        # (region, turn) so the signal survives intra-turn bridge polls.
        resist_observations = list(prev_entry.get("resist_observations") or [])
    elif prev_entry is None:
        resist_observations = []
    else:
        # Anchor grid_power_delta to the FIRST poll of the previous turn
        # (the true turn boundary) rather than whatever the last entry's
        # grid was. Intra-turn polls drop grid after our mech actions, so
        # the last entry misattributes mech damage to the enemy phase.
        prev_turn = prev_entry.get("turn")
        prev_turn_start_gp = _first_grid_power_for_turn(
            log_path, run_id, active_region, prev_turn,
        )
        resist_observations = _compute_resist_observations(
            prev_entry, board, board.grid_power,
            prev_turn_start_grid_power=prev_turn_start_gp,
        )
    entry = {
        "run_id": run_id,
        "mission_id": mission_id,
        "region": active_region,
        "mission_slot": active_mission_slot,
        "turn": current_turn,
        "master_seed": master_seed,
        "ai_seed": active_seed,
        "grid_defense_pct": getattr(board, "grid_defense_pct", 15),
        "grid_power": board.grid_power,
        "grid_power_max": board.grid_power_max,
        # Per-tile building HP map {"A1": hp, ...} — lets the analyzer tell
        # WHICH building lost HP across turns, not just the total. Needed to
        # disambiguate "one resist + one destroy" vs "two small hits".
        "building_hp_map": {
            f"{chr(72 - y)}{8 - x}": board.tiles[x][y].building_hp
            for x in range(8) for y in range(8)
            if board.tiles[x][y].terrain == "building"
            and board.tiles[x][y].building_hp > 0
        },
        "telegraphed_building_attacks": telegraphed,
        "resist_observations": resist_observations,
        "timestamp": int(bridge_data.get("timestamp", 0)),
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _auto_advance_mission(session: RunSession, bridge_data: dict) -> bool:
    """Detect a mission boundary from the bridge and bump ``mission_index``.

    Without this, every mission in a multi-mission run shares ``mission_index=0``
    and recordings collide on the ``m00_*`` prefix — the second mission's turn-0
    board overwrites the first's, etc. (See run 20260428_165811_685 where
    Mission_FreezeBots clobbered Mission_BotDefense's m00_turn_04_board.json,
    and the volcano final on the R.S.T. island missed its m## prefix entirely
    because Mission_Final / a recurring template id collided with an earlier
    mission of the same name on a previous island.)

    ``cmd_mission_end`` already bumps explicitly when called, but the harness
    doesn't always call it (e.g. on Region Secured detected from a screenshot).
    This auto-detect path is the safety net.

    Bump rules:
      - bridge mission_id empty       → no-op (between missions / loading)
      - session.current_mission empty → first time we see a mission this run
                                        (or post-cmd_mission_end re-entry).
                                        Adopt the name; do NOT bump index —
                                        ``mission_index`` already points at the
                                        correct slot (0 for fresh runs, mi+1
                                        for post-mission_end).
      - same mission_id, turn regressed → SAME TEMPLATE, NEW INSTANCE
                                        (e.g., Mission_Acid recurring across
                                        islands). The bridge only emits
                                        template ids; we proxy "new mission"
                                        with a turn drop below the highest
                                        turn we observed in this slot. Bump
                                        index, reset per-mission state.
      - same mission_id, no turn drop → no-op (every-turn read path).
      - different mission_id          → mission boundary missed by the harness.
                                        Bump index, adopt new name, clear
                                        per-mission soft-disable list (mirrors
                                        ``RunSession.advance_mission``).

    Returns True when an adopt-or-bump fired so the caller can ``session.save()``.
    """
    mission_id = (bridge_data.get("mission_id") or "").strip()
    if not mission_id:
        return False
    bridge_turn = bridge_data.get("turn", 0)
    if not isinstance(bridge_turn, int):
        try:
            bridge_turn = int(bridge_turn)
        except (TypeError, ValueError):
            bridge_turn = 0

    if session.current_mission == mission_id:
        # Same template id. Detect a fresh instance via turn regression — the
        # bridge re-zeroes Game:GetTurnCount() at every mission start, so a
        # drop below ``last_mission_turn`` while the template id matches means
        # the harness missed cmd_mission_end AND the next mission happens to
        # share the template name. Without this branch, the new mission's
        # recordings collide with the prior one's m## prefix.
        if (session.last_mission_turn >= 1
                and bridge_turn < session.last_mission_turn):
            print(
                f"[auto_advance_mission] same-template boundary detected: "
                f"{mission_id!r} turn {session.last_mission_turn} -> "
                f"{bridge_turn} "
                f"(mission_index {session.mission_index} -> "
                f"{session.mission_index + 1})"
            )
            session.mission_index += 1
            session.last_mission_turn = bridge_turn
            session.disabled_actions = []
            return True
        # Track the high-water mark in-place for future regression checks.
        # This is a non-structural side effect and intentionally does NOT
        # signal a save (the field will be persisted by the next genuine
        # session.save() — typically a few seconds later in cmd_read).
        if bridge_turn > session.last_mission_turn:
            session.last_mission_turn = bridge_turn
        return False
    if not session.current_mission:
        # First mission this run, or first read after cmd_mission_end cleared
        # current_mission and pre-bumped mission_index. Just adopt the name.
        session.current_mission = mission_id
        session.last_mission_turn = bridge_turn
        return True
    # Mission boundary the harness missed. Bump and reset per-mission state.
    print(
        f"[auto_advance_mission] mission boundary detected: "
        f"{session.current_mission!r} -> {mission_id!r} "
        f"(mission_index {session.mission_index} -> {session.mission_index + 1})"
    )
    session.current_mission = mission_id
    session.mission_index += 1
    session.last_mission_turn = bridge_turn
    session.disabled_actions = []
    # The post-bump mission has its own terrain anchor; clear the prior
    # fingerprint so the next ``cmd_read`` re-seeds without firing the
    # stage-change detector against a stale (different-mission) reference.
    session.last_terrain_fingerprint = None
    session.terrain_stage_change_pending = False
    return True


def _detect_terrain_stage_change(
    session: RunSession,
    bridge_data: dict,
) -> dict | None:
    """Detect mid-mission terrain stage swaps via structural fingerprinting.

    Returns a dict describing the swap when one fires, or ``None`` on a
    normal turn. Side-effects: always updates
    ``session.last_terrain_fingerprint`` to the current turn; sets
    ``session.terrain_stage_change_pending = True`` and records a
    ``terrain_stage_change`` decision when a swap fires; persists the
    session if either field changed.

    See ``src/bridge/terrain_fingerprint.py`` for the hash + threshold
    rationale. The threshold is intentionally conservative (>= 16 of 64
    tiles changed structural class) so destroyed mountains, melted ice,
    and one-off rubble conversions don't trip it.
    """
    from src.bridge.terrain_fingerprint import (
        DEFAULT_CHANGE_THRESHOLD,
        diff_count,
        fingerprint_from_bridge_tiles,
        fingerprint_from_session_dict,
        fingerprint_to_session_dict,
        is_stage_change,
    )

    tiles = bridge_data.get("tiles") or []
    if not tiles:
        return None

    turn = bridge_data.get("turn", 0)
    mission_index = session.mission_index

    curr = fingerprint_from_bridge_tiles(
        tiles, mission_index=mission_index, turn=turn,
    )
    prev = fingerprint_from_session_dict(session.last_terrain_fingerprint)

    fired = is_stage_change(prev, curr)
    payload: dict | None = None
    if fired:
        changed = diff_count(prev, curr)
        payload = {
            "mission_index": mission_index,
            "mission": session.current_mission,
            "prev_turn": prev.turn if prev else None,
            "curr_turn": turn,
            "prev_hash": prev.hash if prev else None,
            "curr_hash": curr.hash,
            "tiles_changed": changed,
            "threshold": DEFAULT_CHANGE_THRESHOLD,
        }
        session.terrain_stage_change_pending = True
        session.record_decision("terrain_stage_change", payload)
        # Banner mirrors the RESEARCH GATE format so the harness picks
        # it up out of the read output.
        print("\n" + "!" * 60)
        print("! TERRAIN STAGE CHANGE — mid-mission arena swap detected.")
        print(
            f"!   Mission: {session.current_mission} "
            f"(index {mission_index})"
        )
        print(
            f"!   Turn {prev.turn if prev else '?'} -> {turn}: "
            f"{changed}/64 structural tiles changed "
            f"(threshold {DEFAULT_CHANGE_THRESHOLD})."
        )
        print(
            "!   Cached active_solution / predicted_states are stale; "
            "downstream code should re-solve from the new board."
        )
        print("!" * 60)

    session.last_terrain_fingerprint = fingerprint_to_session_dict(curr)
    session.save()
    return payload


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


def _get_simulator_version() -> int:
    """Return the simulator semantic version (bumps when sim behavior changes).

    See src/solver/verify.py:SIMULATOR_VERSION for bump discipline. Stamped
    on solve records and failure_db entries so the tuner can refuse to
    mix pre-bump and post-bump corpora without explicit acknowledgment.
    """
    from src.solver.verify import SIMULATOR_VERSION
    return SIMULATOR_VERSION


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


def _unit_roster_fingerprint(bridge_data: dict | None) -> str:
    """Return a stable string fingerprint of the live unit roster.

    Captures (uid, x, y, hp) for each entry in ``bridge_data["units"]``.
    Used by cmd_auto_turn to detect bridge-state staleness — if cmd_solve
    cached a solution against a roster snapshot that no longer matches the
    current bridge state, the cached predicted_states are unreliable and
    must not be reused for verify_action diffs.

    Returns "" when bridge_data is missing or has no units.
    """
    if not bridge_data:
        return ""
    units = bridge_data.get("units") or []
    if not units:
        return ""
    parts: list[str] = []
    for u in units:
        uid = u.get("uid")
        if uid is None:
            continue
        parts.append(
            f"{uid}:{u.get('x', -1)},{u.get('y', -1)}:{u.get('hp', 0)}"
        )
    parts.sort()
    return "|".join(parts)


def _enqueue_behavior_novelty(
    session: RunSession,
    diff,
    turn: int,
) -> list[str]:
    """Enqueue research on every non-mech unit type present in ``diff``.

    Called from ``cmd_auto_turn`` right after each ``fuzzy_detector.evaluate``
    firing. An alive-field flip is the smoking gun for behavior novelty —
    solver predicted kill/no-kill and reality said otherwise — but magnitude
    diffs (hp off by one, damage_amount mismatches) also belong on the queue
    so ``drain_stale_behavior_novelty`` can distinguish structural surprises
    from benign model drift on a catalogued type.

    Per unit type we pick the worst diff (by severity) and stamp
    ``diff_field``, ``diff_predicted``, ``diff_actual``, ``severity`` onto
    the queue entry. The drain helper uses that metadata to auto-resolve
    catalogued types whose worst desync this turn was low-severity.

    Dedup in ``session.enqueue_research`` (compound key with ``kind``) keeps
    re-seeing the same unit across multiple desyncs from double-queuing;
    the first enqueue wins its severity stamp for the life of the entry.

    Returns the list of unit types newly enqueued.
    """
    from src.research.orchestrator import worst_diff_per_type

    enqueued: list[str] = []
    for unit_type, (field, predicted, actual, severity) in (
        worst_diff_per_type(diff).items()
    ):
        if session.enqueue_research(
            unit_type, None, turn, kind="behavior_novelty",
            diff_field=field,
            diff_predicted=predicted,
            diff_actual=actual,
            severity=severity,
        ):
            enqueued.append(unit_type)
    return enqueued


def _auto_enqueue_mech_weapons(
    session: RunSession,
    board: Board,
    turn_for_queue: int,
) -> list[dict]:
    """Enqueue a mech_weapon probe for each unique live mech × probeable slot.

    Mechs are never flagged as unknown (they're squad-native), but
    each new mech type on the board is worth probing once to populate
    ``data/weapon_def_mismatches.jsonl``. Dedup in
    ``session.enqueue_research`` (compound key with ``kind="mech_weapon"``
    + ``slot``) makes this idempotent across turns — re-reading the
    board never double-enqueues the same probe.

    Only ``capture.PROBEABLE_WEAPON_SLOTS`` get auto-enqueued. Slot 0
    is the Repair icon on the starting squad and its tooltip lives
    outside the calibrated weapon_preview crop; auto-enqueuing it
    just adds noise. Manual probes via ``research_probe_mech`` still
    accept any slot index.

    Returns the list of newly-enqueued entries (empty on re-reads).
    """
    from src.research.capture import PROBEABLE_WEAPON_SLOTS

    enqueued: list[dict] = []
    seen_mech_types: set[str] = set()
    for u in board.units:
        if getattr(u, "hp", 0) <= 0:
            continue
        if not getattr(u, "is_mech", False):
            continue
        mech_type = getattr(u, "type", "") or ""
        if not mech_type or mech_type in seen_mech_types:
            continue
        seen_mech_types.add(mech_type)
        for slot in PROBEABLE_WEAPON_SLOTS:
            added = session.enqueue_research(
                mech_type, None, turn_for_queue,
                kind="mech_weapon", slot=slot,
            )
            if added:
                enqueued.append({"type": mech_type, "slot": slot})
    return enqueued


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
                "simulator_version": _get_simulator_version(),
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

            # Auto-advance ``mission_index`` when we observe a mission boundary
            # the harness didn't fire ``cmd_mission_end`` for. Must run BEFORE
            # ``_record_turn_state`` / ``_log_resist_probe`` so the new mission's
            # writes land under the bumped ``m{NN}_*`` prefix instead of
            # overwriting the prior mission's recordings.
            if _auto_advance_mission(session, bridge_data):
                session.save()

            # Mid-mission terrain stage-change detection. Some final missions
            # swap their arena partway through (volcano → caverns on
            # Mission_Final). Without this, the solver keeps using stage-1
            # terrain after the swap and predicted_states diverge from the
            # actual board. Detection only — corrective action (re-init sim)
            # is left to downstream code that consumes
            # ``terrain_stage_change_pending`` / the result["terrain_stage_change"]
            # signal. Must run AFTER _auto_advance_mission so a real mission
            # boundary doesn't false-positive (the detector's mission_index
            # gate filters cross-mission swaps).
            try:
                stage_change = _detect_terrain_stage_change(
                    session, bridge_data,
                )
                if stage_change:
                    result["terrain_stage_change"] = stage_change
            except Exception as exc:
                # Detector is observational — never break cmd_read on a
                # fingerprint error. Surface in the result for debugging.
                result["terrain_fingerprint_error"] = str(exc)

            # Grid-defense resist probe: log aiSeed + telegraphed building
            # attacks each player-turn-start. No-op if the bridge didn't
            # surface a seed or phase isn't combat_player.
            try:
                _log_resist_probe(session, board, bridge_data)
            except Exception:
                # Probe is observational — never break cmd_read on a log error.
                pass

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

                # Self-healing loop Phase 0: flag any pawn type or terrain
                # id we've never cataloged. Instrumentation only — no
                # behavior change. Regenerate the baseline with
                # scripts/regenerate_known_types.py.
                from src.solver.unknown_detector import detect_unknowns
                unknowns = detect_unknowns(board, phase=phase)
                turn_for_queue = bridge_data.get("turn", 0)
                if (unknowns["types"] or unknowns["terrain_ids"]
                        or unknowns["weapons"] or unknowns["screens"]):
                    result["unknowns"] = unknowns
                    # Protocol gate flag — see CLAUDE.md rule 20. The
                    # harness must run research_next before solving.
                    result["requires_research"] = True
                    # Phase 2 #P2-2: enqueue each novel type / terrain for
                    # the between-turn research processor. Dedup is per
                    # (type, terrain_id, kind, slot), so re-seeing across
                    # turns won't re-enqueue. Enqueuing itself is cheap —
                    # the expensive Vision capture happens in #P2-3+.
                    enqueued = []
                    for t in unknowns["types"]:
                        if session.enqueue_research(t, None, turn_for_queue):
                            enqueued.append({"type": t, "terrain_id": None})
                    for tid in unknowns["terrain_ids"]:
                        if session.enqueue_research("", tid, turn_for_queue):
                            enqueued.append({"type": "", "terrain_id": tid})
                    for w in unknowns["weapons"]:
                        if session.enqueue_research(
                            w, None, turn_for_queue, kind="enemy_weapon",
                        ):
                            enqueued.append({
                                "type": w, "terrain_id": None,
                                "kind": "enemy_weapon",
                            })
                    for s in unknowns["screens"]:
                        if session.enqueue_research(
                            s, None, turn_for_queue, kind="screen",
                        ):
                            enqueued.append({
                                "type": s, "terrain_id": None,
                                "kind": "screen",
                            })
                    if enqueued:
                        result["research_enqueued"] = enqueued
                        session.save()
                    print("\n" + "!" * 60)
                    print("! RESEARCH GATE — novelty on the board.")
                    if unknowns["types"]:
                        print(f"!   Unknown types:   {', '.join(unknowns['types'])}")
                    if unknowns["terrain_ids"]:
                        print(f"!   Unknown terrain: {', '.join(unknowns['terrain_ids'])}")
                    if unknowns["weapons"]:
                        print(f"!   Unknown weapons: {', '.join(unknowns['weapons'])}")
                    if unknowns["screens"]:
                        print(f"!   Unknown screen:  {', '.join(unknowns['screens'])}")
                    print("!   Next: game_loop.py research_next  (CLAUDE.md rule 20)")
                    print("!" * 60)

                # Missing wire #5: gate on queued behavior-novelty entries
                # too. detect_unknowns only catches name-novelty; desyncs
                # enqueued mid-turn by cmd_auto_turn won't re-flag here
                # (the unit is already known), so we need a separate
                # check that walks the queue for actionable entries.
                #
                # Fix #4: drain stale low-severity entries on catalogued
                # types *before* asking the predicate — otherwise the gate
                # fires every turn for off-by-one HP diffs that the tuner
                # corpus already handles. The drain is the only mutator;
                # has_actionable_research stays read-only.
                if not result.get("requires_research"):
                    from src.research.orchestrator import (
                        drain_stale_behavior_novelty,
                        has_actionable_research,
                    )
                    drained = drain_stale_behavior_novelty(session)
                    if drained:
                        result["research_auto_resolved"] = drained
                    if has_actionable_research(session, board):
                        result["requires_research"] = True
                        print("\n" + "!" * 60)
                        print("! RESEARCH GATE — behavior-novelty entry in queue.")
                        print("!   Next: game_loop.py research_next  (CLAUDE.md rule 20)")
                        print("!" * 60)

                # Phase 2 #P2-8 follow-up: auto-enqueue mech-weapon probes.
                # Mechs aren't "unknowns" but their weapons are the
                # comparator's primary regression target — enqueue one
                # entry per (mech_type, slot) per mission so the
                # research_next / research_probe_mech flow can populate
                # weapon_def_mismatches.jsonl across the full squad.
                mech_weapons = _auto_enqueue_mech_weapons(
                    session, board, turn_for_queue,
                )
                if mech_weapons:
                    result["mech_weapons_enqueued"] = mech_weapons
                    session.save()

                # Deployment zone (available on turn 0 during deployment)
                deploy_zone = bridge_data.get("deployment_zone", [])
                if deploy_zone:
                    deploy_tiles = []
                    teleporter_tiles_set = _teleporter_tile_set(board)
                    for tile in deploy_zone:
                        bx, by = tile[0], tile[1]
                        visual_row = 8 - bx
                        visual_col = chr(72 - by)
                        mcp_x, mcp_y = grid_to_mcp(bx, by)
                        hazard = classify_deploy_hazard(
                            board, bx, by, teleporter_tiles_set,
                        )
                        entry = {
                            "bridge": f"({bx},{by})",
                            "visual": f"{visual_col}{visual_row}",
                            "mcp": [mcp_x, mcp_y],
                            "hazard": hazard,
                        }
                        deploy_tiles.append(entry)
                    result["deployment_zone"] = deploy_tiles

                print(f"\n{'='*50}")
                print(f"BOARD STATE (BRIDGE) — Turn {bridge_data.get('turn', '?')} | "
                      f"Grid: {board.grid_power}/{board.grid_power_max} | "
                      f"Phase: {phase}")
                print(f"{'='*50}")
                board.print_board()

                if deploy_zone:
                    # Annotate cracked tiles so the caller sees the hazard.
                    for tile, dt in zip(deploy_zone, deploy_tiles):
                        bx, by = tile[0], tile[1]
                        if board.tiles[bx][by].cracked:
                            dt["cracked"] = True
                    cracked_count = sum(1 for dt in deploy_tiles if dt.get("cracked"))
                    hazard_count = sum(1 for dt in deploy_tiles if dt.get("hazard"))
                    hdr = f"\nDEPLOYMENT ZONE ({len(deploy_tiles)} tiles):"
                    flags: list[str] = []
                    if cracked_count:
                        flags.append(f"⚠ {cracked_count} cracked")
                    if hazard_count:
                        flags.append(f"⚠ {hazard_count} hazard")
                    if flags:
                        hdr += "  [" + " | ".join(flags) + " — avoid]"
                    print(hdr)
                    for dt in deploy_tiles:
                        bits = []
                        if dt.get("cracked"):
                            bits.append("CRACKED")
                        if dt.get("hazard"):
                            bits.append(dt["hazard"].upper())
                        suffix = ("  ⚠ " + ",".join(bits)) if bits else ""
                        print(f"  {dt['visual']} (bridge {dt['bridge']}) -> MCP ({dt['mcp'][0]}, {dt['mcp'][1]}){suffix}")

                    # Show ranked recommendations (hazard-aware)
                    ranked_full = recommend_deploy_tiles(board, deploy_zone)
                    if ranked_full:
                        print(f"\nRECOMMENDED DEPLOY (ranked by enemy proximity + building cover):")
                        for idx, d in enumerate(ranked_full):
                            rx, ry = d["x"], d["y"]
                            vr = 8 - rx
                            vc = chr(72 - ry)
                            mx, my = grid_to_mcp(rx, ry)
                            role = ["FORWARD", "MID", "SUPPORT"][min(idx, 2)]
                            warn = ""
                            if d.get("hazard_warning") and d.get("hazard"):
                                warn = f"  ⚠ FALLBACK: {d['hazard']}"
                            print(f"  {idx+1}. {vc}{vr} ({role}) -> MCP ({mx}, {my}){warn}")
                        result["recommended_deploy"] = [
                            {
                                "visual": f"{chr(72-d['y'])}{8-d['x']}",
                                "mcp": list(grid_to_mcp(d["x"], d["y"])),
                                "hazard": d.get("hazard"),
                                "hazard_warning": bool(d.get("hazard_warning")),
                            }
                            for d in ranked_full
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


def _infer_webb_egg_adjacency(units: list) -> None:
    """Mutate ``units`` to mark WEB on any living unit cardinally adjacent
    to a living WebbEgg1.

    Bridge's ``p:IsGrappled()`` empirically misses Spider-egg webs on
    mechs (confirmed: Cannon Mech shown Webbed in-game but bridge returned
    web=False). Game rule from weapons_enemy.lua SpiderAtk1:
        for dir = DIR_START, DIR_END do
            ret:AddGrapple(p2, p2 + DIR_VECTORS[dir], "hold")
    so infer from adjacency until the bridge probes identify the right
    API. web_source_uid points to the egg so web-break-on-push/kill works.
    """
    eggs = [u for u in units
            if u.get("type") == "WebbEgg1" and u.get("hp", 0) > 0]
    if not eggs:
        return
    by_pos = {(u.get("x"), u.get("y")): u for u in units}
    for egg in eggs:
        ex, ey = egg.get("x"), egg.get("y")
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            neighbor = by_pos.get((ex + dx, ey + dy))
            if neighbor is None or neighbor.get("hp", 0) <= 0:
                continue
            # Adjacent egg is the AUTHORITATIVE webber — override any
            # bridge-reported web_source_uid (Lua GetGrappler returns the
            # wrong unit when a Scorpion is nearby alongside a WebbEgg,
            # which lets the solver "break" the web by pushing the wrong
            # enemy and incorrectly conclude the mech can move).
            neighbor["web"] = True
            neighbor["web_source_uid"] = egg.get("uid", 0)


def _check_wheel_sim_version() -> dict | None:
    """Return an error dict iff the installed Rust wheel's SIMULATOR_VERSION
    disagrees with the Python constant. Returns None when OK or unchecked.

    The Rust wheel exposes ``itb_solver.simulator_version()`` (a u32 const
    baked at build time). A mismatch means the wheel wasn't rebuilt after
    a simulator change — running Python code against stale Rust produces
    silent prediction divergence. Fail loudly at cmd_solve entry.

    If the function is missing on the wheel (older build without the
    export), skip the check — the rebuild itself will add it.
    """
    from src.solver.verify import SIMULATOR_VERSION as PY_SIM_VERSION
    try:
        import itb_solver as _itb
    except ImportError:
        return None
    sim_fn = getattr(_itb, "simulator_version", None)
    if sim_fn is None:
        return None
    try:
        rust_sim = int(sim_fn())
    except Exception:
        return None
    if rust_sim != PY_SIM_VERSION:
        return {
            "error": "wheel_sim_version_mismatch",
            "python_simulator_version": PY_SIM_VERSION,
            "rust_wheel_simulator_version": rust_sim,
            "hint": ("Rust wheel is out of sync with Python. Rebuild: "
                     "cd rust_solver && maturin build --release && "
                     "pip3 install --user --force-reinstall "
                     "target/wheels/itb_solver-*.whl"),
        }
    return None


def cmd_solve(profile: str = "Alpha", time_limit: float = 10.0,
              beam: int = 0) -> dict:
    """Run solver on current board, store solution in session.

    Args:
        beam: 0 (default) uses `itb_solver.solve` — the current top-1 path.
              2 uses `itb_solver.solve_beam(depth=2, k=5)` and picks the plan
              with the highest chain_score (turn-1 score + best turn-2 sub-plan
              score). 1 uses solve_beam(depth=1) which is equivalent to
              solve_top_k with K=5 — takes the top raw-score plan without the
              two-stage clean-plan filter. Other values raise ValueError.

    Returns the chosen solution with actions and score. When beam>=1 the
    recording stamps `beam_mode` and `chain_score` so downstream analysis
    can diff plan quality vs. top-1.
    """
    if beam not in (0, 1, 2):
        return {"error": f"invalid beam value {beam!r}; must be 0, 1, or 2"}
    # Refuse to solve against a stale wheel after a Rust rebuild.
    wheel_err = _check_wheel_sim_version()
    if wheel_err is not None:
        _print_result(wheel_err)
        return wheel_err

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

    # Research gate — refuse to solve when novelty is on the board
    # OR when a queued behavior-novelty entry's target is currently live.
    # Solving past either produces confidently-wrong plays. The harness
    # must run cmd_research_next → dispatch capture → cmd_research_submit
    # before calling solve again. See CLAUDE.md rule 20 and
    # docs/self_healing_loop_design.md.
    from src.research.orchestrator import (
        drain_stale_behavior_novelty,
        has_actionable_research,
    )
    from src.solver.research_gate import research_gate_envelope
    from src.solver.unknown_detector import detect_unknowns
    _solve_phase = bridge_data.get("phase") if bridge_data else None
    gate = research_gate_envelope(
        detect_unknowns(board, phase=_solve_phase)
    )
    # Fix #4: drain stale low-severity entries on catalogued types before
    # checking the predicate. Otherwise auto_turn→solve returns
    # RESEARCH_REQUIRED with unknowns:{} every turn for off-by-one HP
    # mismatches the tuner already learns from via failure_db.
    drain_stale_behavior_novelty(session)
    if gate is None and has_actionable_research(session, board):
        gate = {
            "error": "RESEARCH_REQUIRED",
            "unknowns": {},
            "next": "cmd_research_next",
            "message": (
                "Queued research entry actionable on current board "
                "(behavior novelty from a prior desync). Resolve before "
                "solving. See CLAUDE.md rule 20."
            ),
        }
    if gate is not None:
        _print_result(gate)
        return gate

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

                _infer_webb_egg_adjacency(bridge_data["units"])
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
            # Inject pilot_value per mech unit so the Rust search scores
            # pilot loss correctly. Lua exposes pilot_id; Python computes
            # the multiplier via _compute_pilot_value so Rust doesn't need
            # its own lookup table.
            from src.model.board import _compute_pilot_value as _cpv
            for ud in bridge_data.get("units", []):
                if ud.get("mech"):
                    ud["pilot_value"] = _cpv(
                        ud.get("pilot_id", ""),
                        ud.get("pilot_skills", []),
                        ud.get("max_hp", 0),
                        ud.get("type", ""),
                        ud.get("pilot_level", 0),
                    )
            # Self-healing loop Tier 2: forward the session's current
            # blocklist so the Rust solver biases scoring away from
            # soft-disabled weapons. Expiry was pruned at the start of
            # cmd_auto_turn; Rust just needs the weapon_id strings.
            if session.disabled_actions:
                bridge_data["disabled_actions"] = list(session.disabled_actions)
            # Phase 3: committed weapon-def overrides. Applied before
            # the solve via bridge JSON; Rust reports them back in
            # applied_overrides for audit.
            from src.solver.weapon_overrides import (
                load_base_overrides as _load_base_ovr,
                inject_into_bridge as _inject_ovr,
            )
            _inject_ovr(bridge_data, base=_load_base_ovr())
            # Mission-aware "do not kill X" bonus-objective resolver.
            # Replaces the previous unconditional Volatile-Vek penalty
            # with a per-mission gate (sim v21). Empty list on missions
            # that don't have a "do not kill" bonus → penalty no-ops.
            from src.solver.mission_bonus_objectives import (
                inject_into_bridge as _inject_bonus_obj,
            )
            _inject_bonus_obj(bridge_data)
            rust_start = _time.time()
            beam_chain_score = None  # only set on beam>=1 path
            if beam == 0:
                rust_json = _rust.solve(_json.dumps(bridge_data), time_limit)
                rust_result = _json.loads(rust_json)
            else:
                # solve_beam returns a JSON array of chain objects sorted
                # by chain_score desc; we pick chains[0]. Empty array means
                # no active mechs / no legal plans — normalize to the
                # shape `solve` returns so the downstream code path stays
                # single-branch.
                chains_json = _rust.solve_beam(
                    _json.dumps(bridge_data), beam, 5, time_limit,
                )
                chains = _json.loads(chains_json)
                if not chains:
                    rust_result = {"actions": [], "score": float("-inf"),
                                   "stats": {}, "applied_overrides": []}
                else:
                    top = chains[0]
                    rust_result = top["level_0"]
                    beam_chain_score = top["chain_score"]
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

    # Store solution in session — stamp the fingerprint of the roster
    # we solved against so cmd_auto_turn can detect stale cached
    # solutions if a future call sees a different roster.
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
    input_fp = _unit_roster_fingerprint(bridge_data)
    session.set_solution(solver_actions, solution.score, current_turn,
                         input_fingerprint=input_fp)

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

    # Replay solution for enriched recording data. Pass the active weights
    # so score_breakdown in the recording reflects the values the solver
    # actually searched under (not evaluate.py DEFAULT_WEIGHTS).
    rem_spawns = bridge_data.get("remaining_spawns", 2**31 - 1) if bridge_data else 2**31 - 1
    _breakdown_weights = None
    if eval_weights_dict:
        from src.solver.evaluate import EvalWeights as _EW
        _breakdown_weights = _EW(**{k: v for k, v in eval_weights_dict.items()
                                    if k in _EW.__dataclass_fields__})
    enriched = replay_solution(bridge_data, solution, spawns,
                               current_turn=current_turn,
                               total_turns=board.total_turns if hasattr(board, 'total_turns') else 5,
                               remaining_spawns=rem_spawns,
                               weights=_breakdown_weights)

    # Record solver output for replay/analysis (enriched format).
    # schema_version stamps the shape of this record so future beam
    # output (Task #10) can coexist with the current top-1 flat format.
    # Readers must route through verify.predicted_states_from_solve_record
    # rather than reaching into data.predicted_states directly.
    from src.solver.verify import SOLVE_RECORD_SCHEMA_VERSION
    solve_data = {
        "schema_version": SOLVE_RECORD_SCHEMA_VERSION,
        "simulator_version": _get_simulator_version(),
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
        "beam_mode": beam,
        "beam_chain_score": beam_chain_score,
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


def cmd_verify_action(action_index: int, auto_diagnose: bool = False) -> dict:
    """Per-action verification: diff predicted vs actual board state.

    Reads the per-action snapshot the solver captured during replay_solution,
    refreshes the bridge, and diffs the two. NEVER re-solves, NEVER overrides
    — desyncs are written to the failure database as data for the tuner.

    When ``auto_diagnose`` is True (also enabled by ITB_AUTO_DIAGNOSE=1
    in the environment), desyncs are appended to ``session.diagnosis_queue``
    with status=pending. The harness drains the queue between turns via
    ``cmd_diagnose_next``; nothing about diagnosis runs on the verify_action
    hot path itself (per design doc §13 #17).

    Returns a dict with status PASS/DESYNC/ERROR. The desync record carries
    a top_category and (optionally) a model_gap_known subcategory so Phase 4's
    tuner can filter pre-existing simulation gaps from tunable failures.
    """
    from src.solver.verify import (
        diff_states,
        classify_diff,
        predicted_states_from_solve_record,
    )

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

    predicted_states = predicted_states_from_solve_record(solve_record)
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
            "simulator_version": _get_simulator_version(),
            "tags": list(session.tags),
        },
    )
    # Mirror the ID construction in append_to_failure_db so callers can hand
    # the failure_id straight to `game_loop.py diagnose`.
    failure_id = (
        f"{session.run_id or 'default'}_m{session.mission_index:02d}"
        f"_t{solved_turn:02d}_per_action_desync_a{action_index}"
    )

    # Verbose per-field block (Layer 1 of the diagnosis loop). Replaces the
    # category-only one-liner that used to be the entire desync output.
    action_meta = None
    sol_actions = session.active_solution.actions
    if 0 <= action_index < len(sol_actions):
        a = sol_actions[action_index]
        action_meta = {
            "mech_uid": getattr(a, "mech_uid", None),
            "mech_type": getattr(a, "mech_type", None),
            "weapon": getattr(a, "weapon", None),
            "target": list(a.target) if getattr(a, "target", None) else None,
            "description": getattr(a, "description", None),
        }
    from src.solver.verify import format_diff_for_log
    print(format_diff_for_log(
        diff,
        action_index,
        action=action_meta,
        failure_id=failure_id,
        run_id=session.run_id,
    ))

    enqueued = False
    if auto_diagnose or os.environ.get("ITB_AUTO_DIAGNOSE") == "1":
        enqueued = _enqueue_diagnosis(
            session,
            failure_id=failure_id,
            diff_dict=diff_dict,
            sim_version=_get_simulator_version(),
            classification=classification,
        )
        if enqueued:
            # Pass the session path explicitly so test monkeypatches on
            # DEFAULT_SESSION_FILE flow through (the default-arg form binds
            # at import time and would write to the original location).
            session.save(DEFAULT_SESSION_FILE)
            print(f"  [auto-diagnose] enqueued — drain via "
                  f"`game_loop.py diagnose_next` (queue depth: "
                  f"{sum(1 for e in session.diagnosis_queue if e.get('status') == 'pending')})")

    result = {
        "status": "DESYNC",
        "action_index": action_index,
        "diff_count": diff.total_count(),
        "category": classification["top_category"],
        "categories": classification["categories"],
        "subcategory": classification.get("subcategory"),
        "model_gap": classification.get("model_gap", False),
        "failure_id": failure_id,
        "diagnosis_enqueued": enqueued,
    }
    _print_result(result)
    return result


def _enqueue_diagnosis(session: RunSession, failure_id: str, diff_dict: dict,
                       sim_version: int, classification: dict) -> bool:
    """Append a desync to session.diagnosis_queue.

    Returns True if a new entry was added, False if skipped (only on
    duplicate signature now — see below). The queue dedups on
    (diff_signature, sim_version) against pending+done entries: same
    diff in same sim version diagnoses to the same answer.

    NOTE: an earlier version skipped enqueue when classification.model_gap
    was true (any diff matching a known_gap). That was over-eager —
    classify_diff sets model_gap on a single tile.acid diff, suppressing
    enqueue for 27 unrelated novel diffs in the same record. Layer 2 is
    now smarter about per-diff gap tagging (diagnosis.diff_known_gap
    short-circuits only when ALL diffs are gaps), so we always enqueue
    and let Layer 2 route correctly.
    """
    from datetime import datetime as _dt
    from src.solver.diagnosis import combined_diff_signature

    diff_sig = combined_diff_signature(diff_dict)
    for entry in session.diagnosis_queue:
        if (
            entry.get("diff_signature") == diff_sig
            and entry.get("sim_version") == sim_version
        ):
            return False

    session.diagnosis_queue.append({
        "failure_id": failure_id,
        "diff_signature": diff_sig,
        "sim_version": sim_version,
        "enqueued_at": _dt.utcnow().isoformat() + "Z",
        "status": "pending",
        "diagnose_status": None,
        "rule_id": None,
        "markdown": None,
    })
    return True


def cmd_diagnose_queue(show: str = "pending") -> dict:
    """List diagnosis queue entries.

    ``show`` ∈ {"pending", "done", "failed", "all"}. Default "pending"
    is what the harness wants between turns; "all" gives the full
    audit log.
    """
    session = _load_session()
    entries = session.diagnosis_queue
    if show != "all":
        entries = [e for e in entries if e.get("status") == show]

    print(f"DIAGNOSIS_QUEUE ({show}): {len(entries)} entries")
    for i, e in enumerate(entries):
        st = e.get("status", "?")
        ds = e.get("diagnose_status") or ""
        rid = e.get("rule_id") or ""
        suffix = f" → {ds}" + (f" ({rid})" if rid else "")
        print(f"  {i:>2}. [{st}] {e.get('failure_id', '?')}{suffix}")

    result = {
        "status": "OK",
        "show": show,
        "count": len(entries),
        "entries": entries,
    }
    _print_result(result)
    return result


def cmd_diagnose_next(force: bool = False) -> dict:
    """Drain the next pending entry from session.diagnosis_queue.

    Calls ``diagnose()`` on the entry's failure_id, marks the queue entry
    done (or failed), and returns a result dict. Designed to be called by
    the harness between turns — never on the auto_turn hot path.

    Returns ``{status: "EMPTY"}`` if the queue is drained.
    """
    from src.solver.diagnosis import diagnose

    session = _load_session()
    pending_idx = next(
        (i for i, e in enumerate(session.diagnosis_queue)
         if e.get("status") == "pending"),
        None,
    )
    if pending_idx is None:
        result = {"status": "EMPTY", "message": "no pending diagnoses"}
        print("DIAGNOSE_NEXT: queue empty")
        _print_result(result)
        return result

    entry = session.diagnosis_queue[pending_idx]
    failure_id = entry.get("failure_id", "")

    try:
        diag = diagnose(failure_id, force=force)
    except Exception as e:
        entry["status"] = "failed"
        entry["error"] = str(e)
        session.save(DEFAULT_SESSION_FILE)
        result = {
            "status": "ERROR",
            "failure_id": failure_id,
            "error": str(e),
        }
        print(f"DIAGNOSE_NEXT {failure_id}: ERROR {e}")
        _print_result(result)
        return result

    entry["status"] = "done" if diag.get("status") != "ERROR" else "failed"
    entry["diagnose_status"] = diag.get("status")
    entry["rule_id"] = diag.get("rule_id")
    entry["markdown"] = diag.get("markdown")
    if diag.get("status") == "ERROR":
        entry["error"] = diag.get("error")
    session.save(DEFAULT_SESSION_FILE)

    print(f"DIAGNOSE_NEXT {failure_id}: {diag.get('status')}")
    if diag.get("rule_id"):
        print(f"  rule: {diag['rule_id']} (confidence={diag.get('confidence', '?')})")
    if diag.get("known_gap"):
        print(f"  known_gap: {diag['known_gap']}")
    if diag.get("markdown"):
        print(f"  markdown: {diag['markdown']}")
    pending_remaining = sum(
        1 for e in session.diagnosis_queue if e.get("status") == "pending"
    )
    print(f"  queue remaining: {pending_remaining}")

    result = {
        "status": "OK",
        "failure_id": failure_id,
        "diagnose_status": diag.get("status"),
        "rule_id": diag.get("rule_id"),
        "markdown": diag.get("markdown"),
        "queue_remaining": pending_remaining,
    }
    _print_result(result)
    return result


def cmd_diagnose(failure_id: str, force: bool = False,
                 out_path: str | None = None) -> dict:
    """Layer 2 of the diagnosis loop: rules + agent fallback prompt.

    Resolution order: rejections.jsonl → known_gaps.yaml → rules.yaml →
    needs_agent. ``--force`` skips the rejection + known_gap guards so
    the loop will retry a previously-suppressed diff.

    Status outcomes:
      rule_match           — one rule won; markdown carries hypothesis + fix
      needs_agent          — no rule; markdown embeds the agent prompt block
                             — dispatch via Agent tool and submit response
                             via `diagnose_apply_agent <id> '<json>'`
      insufficient_data    — diff matches a known model gap (--force overrides)
      rejected             — prior rejection on this diff_signature × sim_version

    Spec: docs/diagnosis_loop_design.md §7 + §12.
    """
    from pathlib import Path as _Path
    from src.solver.diagnosis import diagnose

    out_dir = _Path(out_path) if out_path else None
    result = diagnose(failure_id, force=force, out_dir=out_dir)

    if result.get("status") == "ERROR":
        print(f"DIAGNOSE {failure_id}: ERROR {result.get('error')}")
        _print_result(result)
        return result

    status = result.get("status", "?")
    rule_id = result.get("rule_id")
    if status == "rule_match" and rule_id:
        print(f"DIAGNOSE {failure_id}: rule_match → {rule_id} "
              f"(confidence={result.get('confidence', '?')})")
    elif status == "insufficient_data":
        print(f"DIAGNOSE {failure_id}: insufficient_data → "
              f"known_gap={result.get('known_gap')} (use --force to override)")
    elif status == "rejected":
        rec = result.get("rejection") or {}
        print(f"DIAGNOSE {failure_id}: rejected — "
              f"reason={rec.get('reason', '?')!r} "
              f"(use --force to override)")
    elif result.get("ambiguous"):
        cands = ", ".join(result.get("candidates") or [])
        print(f"DIAGNOSE {failure_id}: needs_agent — ambiguous match "
              f"({cands})")
    else:
        print(f"DIAGNOSE {failure_id}: needs_agent — no rule matched")
    print(f"  markdown: {result.get('markdown')}")
    if result.get("next_step"):
        print(f"  next: {result['next_step']}")
    # Don't echo the full prompt through _print_result — the markdown carries
    # it for the harness to copy. Strip from the JSON dump for readability.
    display = {k: v for k, v in result.items() if k != "agent_prompt"}
    if "agent_prompt" in result:
        display["agent_prompt"] = (
            f"<{len(result['agent_prompt'])} chars — see {result['markdown']}>"
        )
    _print_result(display)
    return result


def cmd_diagnose_apply_agent(failure_id: str, payload: str,
                             out_path: str | None = None) -> dict:
    """Validate an Explore-agent JSON response and write agent_proposed markdown.

    `payload` is the agent's JSON response (raw string OR a path to a file
    containing the response). Validation enforces:
      - JSON parses
      - target_language == "rust" (no Python sim fixes)
      - every suspect_files[*].path resolves and the cited lines exist
      - confidence ∈ {high, medium, low}
      - fix_snippet has both before + after non-empty

    On failure, returns status=ERROR with the per-clause error list — fix
    the JSON and resubmit. On success, writes status=agent_proposed
    markdown alongside the previous needs_agent file (overwrites).
    """
    from pathlib import Path as _Path
    from src.solver.diagnosis import apply_agent_response

    payload_text = payload
    p = _Path(payload)
    if p.exists() and p.is_file():
        payload_text = p.read_text()

    out_dir = _Path(out_path) if out_path else None
    result = apply_agent_response(failure_id, payload_text, out_dir=out_dir)

    if result.get("status") == "ERROR":
        print(f"DIAGNOSE_APPLY_AGENT {failure_id}: ERROR")
        for e in result.get("errors") or [result.get("error", "?")]:
            print(f"  - {e}")
        _print_result(result)
        return result

    print(f"DIAGNOSE_APPLY_AGENT {failure_id}: agent_proposed "
          f"(confidence={result.get('confidence', '?')})")
    print(f"  markdown: {result.get('markdown')}")
    print(f"  fix_signature: {result.get('fix_signature')}")
    print(f"  next: review the markdown, then either "
          f"`apply_diagnosis {failure_id} [--dry-run]` or "
          f"`reject_diagnosis {failure_id} --reason '...'`")
    _print_result(result)
    return result


def cmd_apply_diagnosis(failure_id: str,
                        dry_run: bool = False,
                        skip_regression: bool = False,
                        skip_build: bool = False) -> dict:
    """Layer 4: walk an agent_proposed diagnosis through the apply sequence.

    Strict order: parse markdown frontmatter → check git clean → snapshot
    → apply before/after → atomic SIMULATOR_VERSION bump (when sim files
    touched) → archive failure_db → rebuild → regression. On any failure,
    every edit is reverted and the diagnosis status flips to apply_failed.

    --dry-run prints the plan and exits before touching any file.
    --skip-build skips maturin (use for non-Rust edits).
    --skip-regression skips scripts/regression.sh (dangerous; the user
    is responsible for running it manually before commit).

    Spec: docs/diagnosis_loop_design.md §11.
    """
    from src.solver.diagnosis_apply import apply_diagnosis

    outcome = apply_diagnosis(
        failure_id, dry_run=dry_run,
        skip_regression=skip_regression, skip_build=skip_build,
    )

    plan = outcome.plan
    suspect_paths = (
        [sf.get("path") for sf in plan.suspect_files] if plan else []
    )

    if outcome.status in ("refused", "apply_failed"):
        print(f"APPLY_DIAGNOSIS {failure_id}: {outcome.status} "
              f"(stage={outcome.stage})")
        print(f"  error: {outcome.error}")
        result = {
            "status": outcome.status,
            "failure_id": failure_id,
            "stage": outcome.stage,
            "error": outcome.error,
            "suspect_files": suspect_paths,
        }
        _print_result(result)
        return result

    if outcome.status == "dry_run":
        print(f"APPLY_DIAGNOSIS {failure_id}: dry_run plan")
        print(f"  confidence: {plan.confidence}")
        print(f"  suspect files: {suspect_paths}")
        print(f"  needs_sim_bump: {plan.needs_sim_bump}")
        if plan.needs_sim_bump:
            print(f"  sim_version_before: {plan.sim_version_before} "
                  f"→ {plan.sim_version_before + 1 if plan.sim_version_before else '?'}")
        print("  fix_snippet.before:")
        for line in plan.fix_snippet["before"].splitlines():
            print(f"    | {line}")
        print("  fix_snippet.after:")
        for line in plan.fix_snippet["after"].splitlines():
            print(f"    | {line}")
        result = {
            "status": "dry_run",
            "failure_id": failure_id,
            "suspect_files": suspect_paths,
            "needs_sim_bump": plan.needs_sim_bump,
        }
        _print_result(result)
        return result

    # applied / applied_unverified
    print(f"APPLY_DIAGNOSIS {failure_id}: {outcome.status}")
    print(f"  files edited: {len(outcome.edits)}")
    if outcome.sim_bumped:
        print(f"  SIMULATOR_VERSION bumped {plan.sim_version_before} "
              f"→ {plan.sim_version_before + 1}")
    if outcome.archived_failure_db:
        try:
            rel = outcome.archived_failure_db.relative_to(
                Path(__file__).resolve().parent.parent.parent
            )
            print(f"  failure_db archived: {rel}")
        except ValueError:
            print(f"  failure_db archived: {outcome.archived_failure_db}")
    if outcome.status == "applied":
        print("  next: review the diff with `git diff`, then commit + push")
    else:
        print("  next: --skip-regression was set; run "
              "`bash scripts/regression.sh` manually before commit")
    result = {
        "status": outcome.status,
        "failure_id": failure_id,
        "edits": [str(p.relative_to(Path(__file__).resolve().parent.parent.parent))
                  for p in outcome.edits.keys()
                  if str(p).startswith(str(Path(__file__).resolve().parent.parent.parent))]
                 or [str(p) for p in outcome.edits.keys()],
        "sim_bumped": outcome.sim_bumped,
        "archived_failure_db": (
            str(outcome.archived_failure_db)
            if outcome.archived_failure_db else None
        ),
    }
    _print_result(result)
    return result


def cmd_reject_diagnosis(failure_id: str, reason: str,
                         out_path: str | None = None) -> dict:
    """Record a rejection so the same diff_signature × sim_version is suppressed.

    Appends to `diagnoses/rejections.jsonl` and rewrites the diagnosis
    markdown to status=rejected. Future `diagnose` calls on the same
    failure short-circuit unless `--force` is passed.
    """
    from pathlib import Path as _Path
    from src.solver.diagnosis import reject

    out_dir = _Path(out_path) if out_path else None
    result = reject(failure_id, reason, out_dir=out_dir)

    if result.get("status") == "ERROR":
        print(f"REJECT_DIAGNOSIS {failure_id}: ERROR {result.get('error')}")
        _print_result(result)
        return result

    print(f"REJECT_DIAGNOSIS {failure_id}: rejected at {result.get('rejected_at')}")
    print(f"  diff_signature: {result.get('diff_signature')}")
    print(f"  proposed_fix_sig: {result.get('proposed_fix_sig')}")
    print(f"  markdown: {result.get('markdown')}")
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


def cmd_click_balanced_roll() -> dict:
    """Emit a click plan for the Balanced Roll button on squad-select.

    Pure planner. Dispatch the batch via ``computer_batch`` before
    clicking Start, so a Balanced Roll (no duplicate mech classes, max
    4 weapons between them) is seeded instead of whatever squad is
    currently shown.
    """
    recalibrate()
    batch = plan_balanced_roll()
    result = {
        "status": "PLAN",
        "batch": batch,
        "next_step": "dispatch batch, then click Start to begin the run",
    }
    print(f"\n=== CLICK_BALANCED_ROLL ===")
    for i, c in enumerate(batch):
        print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) -- {c['description']}")
    print(f"Next: dispatch batch via computer_batch, then click Start")
    _print_result(result)
    return result


def cmd_recommend_mission(
    profile: str = "Alpha",
    island_map_json: str | None = None,
) -> dict:
    """Recommend a mission from the current island slate.

    Reads the bridge ``island_map`` (or the supplied JSON file when the
    bridge isn't on the island map screen — the Lua hook only emits it
    outside active combat). Derives squad capability tags from the live
    units list, scores each available mission, prints the top 3 with
    rationale lines.

    The ``--island-map-json`` flag points at a file containing a list
    of {region_id, mission_id, bonus_objective_ids, environment, ...}
    objects (same shape Lua emits). Used for offline scoring / tests
    when the bridge is unavailable or the Lua hook hasn't been
    installed yet.
    """
    from src.strategy.mission_picker import score_island_map

    bridge_data: dict = {}
    units: list = []
    grid_power = 7
    island_map: list | None = None

    if island_map_json:
        try:
            with open(island_map_json) as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            result = {"status": "ERROR",
                      "error": f"Failed to load island_map_json: {e}"}
            _print_result(result)
            return result
        if isinstance(payload, dict):
            island_map = payload.get("island_map")
            units = payload.get("units", [])
            grid_power = payload.get("grid_power", 7)
        else:
            island_map = payload  # bare list
    else:
        # Pull live bridge state.
        if not is_bridge_active():
            result = {"status": "NO_BRIDGE",
                      "note": "Bridge not active. Pass --island-map-json "
                              "<path> to score from a saved payload."}
            _print_result(result)
            return result
        try:
            refresh_bridge_state()
        except (BridgeError, Exception):
            pass
        board, bridge_data = read_bridge_state()
        if bridge_data is None:
            result = {"status": "NO_BRIDGE",
                      "note": "Bridge read failed."}
            _print_result(result)
            return result
        island_map = bridge_data.get("island_map")
        units = bridge_data.get("units", [])
        grid_power = bridge_data.get("grid_power", 7)

    if not island_map:
        phase = bridge_data.get("phase", "unknown") if bridge_data else "unknown"
        result = {
            "status": "NO_ISLAND_MAP",
            "phase": phase,
            "note": ("No mission options visible. The Lua hook only emits "
                     "island_map outside active combat. If you're on the "
                     "corp island map and this still fails, the modloader "
                     "may need a rebuild (scripts/install_modloader.sh)."),
        }
        _print_result(result)
        return result

    ranked = score_island_map(island_map, units, grid_power)
    top3 = ranked[:3]

    print(f"\n=== RECOMMEND_MISSION ===")
    print(f"Squad weapons:   "
          f"{[w for u in units if u.get('mech') for w in u.get('weapons', [])]}")
    print(f"Grid power:      {grid_power}")
    print(f"Available:       {len(island_map)} mission(s)")
    print()
    for rank, m in enumerate(top3, start=1):
        print(f"  #{rank}  region={m.get('region_id')}  "
              f"{m.get('mission_id', '?')}  "
              f"score={m['score']}")
        for line in m.get("rationale_lines", []):
            print(f"        {line}")
        print()

    result = {
        "status": "OK",
        "grid_power": grid_power,
        "ranked": ranked,
        "top3": top3,
    }
    _print_result(result)
    return result


def cmd_research_next(profile: str = "Alpha") -> dict:
    """Pick the next research queue entry and emit its capture plan.

    Between-turn research flow, Phase 2 wiring. This is the pull-side
    of the orchestrator: picks the head of ``session.research_queue``,
    finds the matching unit on the live board, builds the MCP capture
    plan (mouse_move → click → screenshot), marks the entry
    ``in_progress``, saves the session.

    The caller (Claude) then:

    1. Dispatches ``plan.batch`` via ``computer_batch``.
    2. Zooms each ``plan.crops[i].region``.
    3. Applies the matching ``prompts[crop_name]`` to produce JSON.
    4. Calls ``cmd_research_submit`` with the research_id and
       ``{crop_name: json_string}``.

    Returns ``{"status": "NO_WORK"}`` when the queue is drained or no
    pending entry has a matching unit on the current board.
    """
    from src.research import capture, orchestrator

    session = _load_session()

    if not is_bridge_active():
        result = {"error": "Bridge not active — research requires bridge"}
        _print_result(result)
        return result

    board, _bridge = read_bridge_state()
    if board is None:
        result = {"error": "Failed to read bridge state for research target"}
        _print_result(result)
        return result

    try:
        ui = capture.resolve_ui_regions(capture.load_ui_regions())
    except Exception as e:
        result = {"error": f"UI regions load failed: {e}"}
        _print_result(result)
        return result

    plan = orchestrator.begin_research(session, board, ui=ui)
    if plan is None:
        session.save()
        result = {
            "status": "NO_WORK",
            "queue_len": len(session.research_queue),
            "pending": sum(1 for e in session.research_queue
                           if e.get("status") == "pending"),
        }
        print(f"\n=== RESEARCH_NEXT ===")
        print(f"  No researchable entry on current board "
              f"(queue_len={result['queue_len']}, "
              f"pending={result['pending']})")
        _print_result(result)
        return result

    session.save()
    result = {
        "status": "PLAN",
        **plan,
    }
    target = plan["target"]
    print(f"\n=== RESEARCH_NEXT (research_id={plan['research_id']}) ===")
    print(f"  target: {target['type']} ({target['kind']}) at "
          f"bridge {tuple(target['position_bridge'])} -> "
          f"MCP {tuple(target['target_mcp'])}")
    print(f"  crops: {[c['name'] for c in plan['plan']['crops']]}")
    print(f"  next: dispatch plan.batch → zoom each crop → Vision → "
          f"cmd_research_submit {plan['research_id']}")
    _print_result(result)
    return result


def cmd_research_submit(
    research_id: str,
    vision_responses: dict | str,
    profile: str = "Alpha",
    wiki_fallback: bool = True,
) -> dict:
    """Receive Vision JSON for a ``cmd_research_next`` plan and finalize.

    ``vision_responses`` is a dict keyed by crop name (``name_tag``,
    ``unit_status``, ``weapon_preview``, ``terrain_tooltip``) whose
    values are either raw JSON strings or already-parsed dicts. CLI
    callers pass a JSON string; programmatic callers pass a dict.

    Side effects: runs the weapon-def comparator if ``weapon_preview``
    is among the responses (appends to
    ``data/weapon_def_mismatches.jsonl``), stores the parsed result on
    the queue entry, transitions status to ``done`` or ``failed``,
    saves the session.

    When ``wiki_fallback`` is True (default), an all-low-confidence
    submission retries via the Fandom wiki client before marking the
    entry failed. Disable with ``--no-wiki`` for fully offline runs.
    """
    import json as _json
    from src.research import orchestrator

    session = _load_session()

    if isinstance(vision_responses, str):
        try:
            vision_responses = _json.loads(vision_responses)
        except _json.JSONDecodeError as e:
            result = {"error": f"vision_responses not valid JSON: {e}"}
            _print_result(result)
            return result

    out = orchestrator.submit_research(
        session,
        research_id,
        vision_responses or {},
        run_id=session.run_id,
        wiki_fallback=wiki_fallback,
    )
    session.save()

    if "error" in out:
        print(f"\n=== RESEARCH_SUBMIT FAILED ===")
        print(f"  {out['error']}")
    else:
        print(f"\n=== RESEARCH_SUBMIT {research_id} ===")
        src = out.get("source", "vision")
        print(f"  status: {out['status']} (source={src})")
        for crop, parsed in out.get("parsed", {}).items():
            conf = parsed.get("confidence", 0.0)
            # Pick a single headline field per crop type for the log line.
            head = (
                parsed.get("name")
                or parsed.get("kind")
                or parsed.get("terrain")
                or "?"
            )
            print(f"  {crop}: {head} (confidence={conf:.2f})")
        if out.get("mismatches"):
            print(f"  mismatches: {len(out['mismatches'])}")
            for m in out["mismatches"]:
                print(f"    - {m['field']}: rust={m['rust_value']} "
                      f"vision={m['vision_value']} [{m['severity']}]")
        else:
            print(f"  mismatches: none")
        if out.get("staged_candidates"):
            print(f"  staged override candidates: {len(out['staged_candidates'])}")
            for c in out["staged_candidates"]:
                patch_fields = [k for k in c if k not in
                                ("weapon_id", "note", "source_run_id",
                                 "source_mismatch")]
                print(f"    - {c['weapon_id']}: {patch_fields}  "
                      f"(review via game_loop.py review_overrides)")
        if out.get("wiki_fallback"):
            wf = out["wiki_fallback"]
            print(f"  wiki_fallback: {wf.get('title', '?')} "
                  f"(section={wf.get('used_section', '?')})")
    _print_result(out)
    return out


def _parse_visual_tile(tile: str) -> tuple[int, int] | None:
    """Parse an A1-H8 visual tile into bridge ``(x, y)``.

    Column letters A-H map to bridge ``y = 72 - ord(col)`` (so H=0, A=7).
    Row digits 1-8 map to bridge ``x = 8 - row`` (so 1=7, 8=0).

    Returns None on malformed input. The two-character shape is the
    canonical form; spaces and lower-case are tolerated.
    """
    t = tile.strip().upper()
    if len(t) != 2:
        return None
    col, row_s = t[0], t[1]
    if col < "A" or col > "H" or not row_s.isdigit():
        return None
    row = int(row_s)
    if row < 1 or row > 8:
        return None
    return (8 - row, 72 - ord(col))


def cmd_research_probe_mech(
    tile: str,
    slot: int = 0,
    profile: str = "Alpha",
) -> dict:
    """Probe a single weapon slot on the mech at ``tile``.

    One-shot counterpart to ``cmd_research_next``. Builds a capture
    plan that selects the mech, hovers the weapon icon for the given
    slot, and captures the ``weapon_preview`` panel for Vision. The
    resulting JSON is submitted via ``cmd_research_submit`` exactly
    like a queue-driven entry — the comparator fires on submit and
    writes mismatches to ``data/weapon_def_mismatches.jsonl``.

    ``tile`` accepts A1-H8 visual notation (preferred) or a bridge
    ``"x,y"`` pair. ``slot`` is 0-indexed into the mech's weapon-icon
    rail (0 = secondary/repair, 1 = prime; see
    ``capture.weapon_icon_positions``). The caller loops slots
    externally — one probe, one submit, one comparator run.
    """
    from src.research import capture, orchestrator

    session = _load_session()

    if not is_bridge_active():
        result = {"error": "Bridge not active — research_probe_mech requires bridge"}
        _print_result(result)
        return result

    parsed = _parse_visual_tile(tile)
    if parsed is None:
        # Fallback: accept "x,y" bridge form for automation scripts.
        try:
            bx, by = (int(p) for p in tile.split(","))
            parsed = (bx, by)
        except (ValueError, AttributeError):
            result = {"error": f"Unparseable tile '{tile}' — expected A1-H8 or 'x,y'"}
            _print_result(result)
            return result
    bridge_x, bridge_y = parsed

    board, _bridge = read_bridge_state()
    if board is None:
        result = {"error": "Failed to read bridge state for probe target"}
        _print_result(result)
        return result

    try:
        ui = capture.resolve_ui_regions(capture.load_ui_regions())
    except Exception as e:
        result = {"error": f"UI regions load failed: {e}"}
        _print_result(result)
        return result

    out = orchestrator.begin_weapon_probe(
        session, board, bridge_x, bridge_y, slot, ui=ui,
    )
    if "error" in out:
        session.save()
        print(f"\n=== RESEARCH_PROBE_MECH FAILED ===")
        print(f"  {out['error']}")
        _print_result(out)
        return out

    session.save()
    result = {"status": "PLAN", **out}
    target = out["target"]
    print(f"\n=== RESEARCH_PROBE_MECH (research_id={out['research_id']}) ===")
    print(f"  target: {target['type']} slot {target['slot']} at "
          f"{_bv(target['position_bridge'][0], target['position_bridge'][1])} "
          f"-> icon MCP {tuple(target['weapon_icon_mcp'])}")
    print(f"  next: dispatch plan.batch → zoom weapon_preview → Vision → "
          f"cmd_research_submit {out['research_id']}")
    _print_result(result)
    return result


def cmd_research_attach_community(
    research_id: str,
    notes_json: str | dict,
    profile: str = "Alpha",
) -> dict:
    """Attach harness-supplied community notes to a research record.

    Missing wire #4 — Steam forum + Reddit fetch. Called after the
    harness WebFetches the URLs emitted by ``cmd_research_submit``'s
    ``community_queries`` field. See CLAUDE.md rule 20.

    Args:
        research_id: ID returned by a prior ``research_next`` /
            ``research_probe_mech`` + ``research_submit`` cycle.
        notes_json: Either a dict or a JSON string with shape
            ``{source: {url, excerpt, confidence}}``. Normalized by
            ``community_fetch.normalize_notes``; sub-threshold entries
            are dropped before persistence.

    Persists normalized notes to ``data/wiki_raw/<encoded_name>.json``
    under a ``community_notes`` field, merging with any existing content
    (wiki fetch output is preserved). Returns a confidence-band
    classification per ``community_fetch.classify_confidence``.
    """
    from src.research import community_fetch, wiki_client

    session = _load_session()

    # Resolve the entry by research_id.
    entry = None
    for e in session.research_queue:
        if e.get("research_id") == research_id:
            entry = e
            break
    if entry is None:
        result = {"error": f"unknown research_id: {research_id}"}
        _print_result(result)
        return result

    # Prefer the target_name we stashed on submit; fall back to entry type.
    stored = entry.get("result") or {}
    cq = stored.get("community_queries") or {}
    target_name = ""
    if isinstance(cq, dict):
        target_name = str(cq.get("target_name", "") or "")
    if not target_name:
        target_name = str(entry.get("type", "") or "")
    if not target_name:
        result = {"error": "no target name available to key community_notes"}
        _print_result(result)
        return result

    # Parse input.
    if isinstance(notes_json, str):
        try:
            raw = json.loads(notes_json)
        except json.JSONDecodeError as exc:
            result = {"error": f"invalid JSON for notes: {exc}"}
            _print_result(result)
            return result
    else:
        raw = notes_json

    normalized = community_fetch.normalize_notes(raw)
    kept = community_fetch.drop_low_confidence(normalized)

    # Merge into data/wiki_raw/<encoded_name>.json. Create if missing.
    cache_path = wiki_client._cache_path(target_name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if cache_path.exists():
        try:
            with open(cache_path) as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing["community_notes"] = kept
    with open(cache_path, "w") as f:
        json.dump(existing, f, indent=2)

    # Confidence band. tooltip_ok = any Vision parse cleared 0.5;
    # wiki_ok = submit produced a wiki_fallback payload.
    parsed = stored.get("parsed") or {}
    tooltip_ok = False
    for p in parsed.values():
        if isinstance(p, dict) and float(p.get("confidence", 0.0)) > 0.5:
            tooltip_ok = True
            break
    wiki_ok = bool(stored.get("wiki_fallback"))
    band = community_fetch.classify_confidence(tooltip_ok, wiki_ok, len(kept))

    result = {
        "research_id": research_id,
        "target_name": target_name,
        "attached_count": len(kept),
        "dropped_count": len(normalized) - len(kept),
        "wiki_raw_path": str(cache_path),
        "confidence_band": band,
    }
    print(f"\n=== RESEARCH_ATTACH_COMMUNITY (research_id={research_id}) ===")
    print(f"  target: {target_name}")
    print(f"  attached: {len(kept)}  dropped: {len(normalized) - len(kept)}")
    print(f"  confidence_band: {band}")
    _print_result(result)
    return result


def _regression_board_for_weapon(weapon_id: str) -> Path | None:
    """Return the first tests/weapon_overrides/<weapon_id>_*.json board
    file, or None when no board has been authored. Module-level so tests
    can monkeypatch it without relying on the real tests/ directory."""
    d = Path(__file__).resolve().parents[2] / "tests" / "weapon_overrides"
    if not d.exists():
        return None
    matches = sorted(d.glob(f"{weapon_id}_*.json"))
    return matches[0] if matches else None


def cmd_review_overrides(
    action: str = "list",
    index: int | None = None,
    *,
    force: bool = False,
) -> dict:
    """Inspect / promote weapon override candidates staged by P3-5.

    ``action``:
      - ``list`` (default): print every staged candidate with its index.
      - ``accept <index>``: promote into ``data/weapon_overrides.json``
        (no auto-commit). Refuses unless a regression board exists at
        ``tests/weapon_overrides/<weapon_id>_<case>.json`` — bypass with
        ``--force`` only when bootstrapping P3-7.
      - ``reject <index>``: drop the candidate from the staged file.

    Returns a dict describing the outcome. Never writes to the live
    session; overrides take effect at the next solve.
    """
    from src.solver.weapon_overrides import (
        DEFAULT_OVERRIDES_PATH, DEFAULT_STAGED_PATH,
        OverrideSchemaError, load_base_overrides,
    )

    def _read_staged() -> list[dict]:
        if not DEFAULT_STAGED_PATH.exists():
            return []
        out: list[dict] = []
        for line in DEFAULT_STAGED_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _write_staged(entries: list[dict]) -> None:
        if not entries:
            if DEFAULT_STAGED_PATH.exists():
                DEFAULT_STAGED_PATH.unlink()
            return
        DEFAULT_STAGED_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_STAGED_PATH.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    staged = _read_staged()

    if action == "list":
        result = {
            "staged_path": str(DEFAULT_STAGED_PATH),
            "overrides_path": str(DEFAULT_OVERRIDES_PATH),
            "staged": [
                {"index": i, **entry} for i, entry in enumerate(staged)
            ],
        }
        print(f"\n=== REVIEW_OVERRIDES ({len(staged)} staged) ===")
        if not staged:
            print("  (none staged — data/weapon_overrides_staged.jsonl "
                  "is empty)")
        else:
            for i, entry in enumerate(staged):
                wid = entry.get("weapon_id", "?")
                patch = {k: v for k, v in entry.items()
                         if k not in ("weapon_id", "note",
                                      "source_run_id", "source_mismatch")}
                print(f"  [{i}] {wid}: {patch}")
                note = entry.get("note")
                if note:
                    print(f"      note: {note}")
        _print_result(result)
        return result

    if index is None:
        err = {"error": f"review_overrides {action} requires <index>"}
        _print_result(err)
        return err
    if index < 0 or index >= len(staged):
        err = {"error": f"index {index} out of range (0..{len(staged) - 1})"}
        _print_result(err)
        return err

    entry = staged[index]
    wid = entry.get("weapon_id", "")

    if action == "reject":
        # Write to the deny list BEFORE dropping the staged entry — if
        # the reject fails mid-write, the candidate stays visible in
        # `review_overrides list` rather than vanishing silently.
        from src.research.pattern_miner import (
            append_to_deny_list,
            signature_from_staged_entry,
        )

        deny_record = None
        sig = signature_from_staged_entry(entry)
        if sig is not None:
            deny_record = append_to_deny_list(sig, reason="review_overrides reject")

        staged.pop(index)
        _write_staged(staged)
        result = {
            "action": "rejected",
            "index": index,
            "weapon_id": wid,
            "remaining_staged": len(staged),
            "deny_list_entry": deny_record,
        }
        print(f"\n=== REVIEW_OVERRIDES reject [{index}] {wid} ===")
        print(f"  removed from {DEFAULT_STAGED_PATH.name}")
        if deny_record:
            print(f"  deny-list: signature_hash={deny_record['signature_hash']} "
                  f"(P4 miner will skip this pattern)")
        else:
            print("  deny-list: skipped (no source_mismatch — miner won't "
                  "auto-skip this signature next run)")
        print(f"  remaining staged: {len(staged)}")
        _print_result(result)
        return result

    if action != "accept":
        err = {"error": f"unknown action: {action!r} "
                        "(expected list | accept | reject)"}
        _print_result(err)
        return err

    # accept path — gated on regression board presence.
    board_path = _regression_board_for_weapon(wid)
    if board_path is None and not force:
        err = {
            "error": (
                f"no regression board for {wid} at "
                f"tests/weapon_overrides/{wid}_<case>.json — add one that "
                f"fails without the override and passes with it, or rerun "
                f"with --force to bypass (not recommended)."
            ),
        }
        _print_result(err)
        return err

    # Build the promoted entry: strip staging-only metadata but keep a
    # shortened "note" so future reviewers can trace the origin.
    promoted = {"weapon_id": wid}
    for field in ("weapon_type", "damage", "damage_outer", "push",
                  "self_damage", "range_min", "range_max", "limited",
                  "path_size", "flags_set", "flags_clear"):
        if field in entry:
            promoted[field] = entry[field]
    origin = entry.get("source_mismatch") or {}
    promoted["note"] = (
        entry.get("note")
        or f"promoted from staged (run={entry.get('source_run_id', '?')})"
    )
    promoted["source_run_id"] = entry.get("source_run_id", "")
    if origin:
        promoted["source_mismatch"] = origin

    # Load the existing base file and append (after sanity-validating
    # the merged result — catches schema errors before we touch disk).
    DEFAULT_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if DEFAULT_OVERRIDES_PATH.exists():
        try:
            existing = json.loads(DEFAULT_OVERRIDES_PATH.read_text())
            if not isinstance(existing, list):
                raise OverrideSchemaError(
                    f"{DEFAULT_OVERRIDES_PATH}: top-level must be an array"
                )
        except (OverrideSchemaError, json.JSONDecodeError) as e:
            err = {"error": f"failed to read existing overrides: {e}"}
            _print_result(err)
            return err
    existing.append(promoted)

    # Round-trip through load_base_overrides with a tempfile so the
    # committed file is always valid — schema errors mean we don't
    # commit the promotion.
    from tempfile import NamedTemporaryFile
    tmp = NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        tmp.write(json.dumps(existing, indent=2))
        tmp.close()
        try:
            load_base_overrides(tmp.name)
        except OverrideSchemaError as e:
            err = {"error": f"promoted entry fails schema validation: {e}"}
            _print_result(err)
            return err
        # Validated — swap into place.
        Path(tmp.name).replace(DEFAULT_OVERRIDES_PATH)
    finally:
        if Path(tmp.name).exists():
            Path(tmp.name).unlink(missing_ok=True)

    staged.pop(index)
    _write_staged(staged)
    result = {
        "action": "accepted",
        "index": index,
        "weapon_id": wid,
        "overrides_path": str(DEFAULT_OVERRIDES_PATH),
        "regression_board": str(board_path) if board_path else None,
        "forced": force and board_path is None,
        "remaining_staged": len(staged),
    }
    print(f"\n=== REVIEW_OVERRIDES accept [{index}] {wid} ===")
    if board_path:
        print(f"  regression board: {board_path}")
    elif force:
        print("  WARNING: --force used without a regression board")
    print(f"  appended to {DEFAULT_OVERRIDES_PATH}")
    print("  next solve will apply it automatically (no rebuild needed)")
    print("  remember to git commit data/weapon_overrides.json when ready")
    _print_result(result)
    return result


def cmd_mine_overrides(
    *,
    execute: bool = False,
    max_stage: int = 3,
    time_limit: float = 2.0,
    verify: bool = True,
    since: str | None = None,
    no_cutoff: bool = False,
) -> dict:
    """P4-1d — mine the jsonl corpora for override candidates and stage them.

    ``execute=False`` (default) is a report-only pass: the miner runs,
    the drafter picks auto-generatable Vision candidates, but nothing
    hits disk. ``execute=True`` writes fixtures to
    ``tests/weapon_overrides/`` and appends staged entries to
    ``data/weapon_overrides_staged.jsonl`` — after which the existing
    ``review_overrides list / accept`` flow (P3-6) takes over.

    Never creates branches or PRs. Human is expected to run
    ``git status`` → review the extracted fixture + staged entry →
    ``review_overrides accept <idx>`` → commit + PR via the usual path.
    """
    from src.research.pattern_miner import mine, load_min_timestamp
    from src.research.pr_drafter import draft_from_candidates

    if no_cutoff:
        effective_cutoff: str | None = None
        candidates = mine(min_timestamp=None)
    elif since is not None:
        effective_cutoff = since
        candidates = mine(min_timestamp=since)
    else:
        effective_cutoff = load_min_timestamp()
        candidates = mine()
    report = draft_from_candidates(
        candidates,
        dry_run=not execute,
        verify=verify,
        max_stage=max_stage,
        time_limit=time_limit,
    )

    print("\n=== MINE_OVERRIDES ===")
    if effective_cutoff:
        print(f"  cutoff (failure_db): {effective_cutoff}")
    else:
        print(f"  cutoff (failure_db): disabled")
    print(f"  mined candidates: {len(candidates)}")
    print(f"  draft outcomes:   staged={report.staged_count} "
          f"skipped={report.skipped_count} (dry_run={report.dry_run})")
    print()
    for i, o in enumerate(report.outcomes):
        sig = o.candidate.signature
        print(f"  [{i}] {sig.source}/{sig.weapon_id}/{sig.field} "
              f"({o.candidate.count}× boards) → {o.status}")
        print(f"       {o.reason}")
        if o.fixture_path:
            print(f"       fixture: {o.fixture_path}")
        if o.verification and not o.verification.get("skipped"):
            vr = o.verification
            print(f"       verify:  observable={vr.get('observable_change')} "
                  f"plan_changed={vr.get('plan_changed')} "
                  f"score_Δ={vr.get('score_delta', 0.0):+.3f}")

    if not execute:
        print("\n  (dry-run; no files written. re-run with --execute to stage.)")
    else:
        print("\n  next: game_loop.py review_overrides list")

    result = {
        "mined": len(candidates),
        "staged": report.staged_count,
        "skipped": report.skipped_count,
        "dry_run": report.dry_run,
        "cutoff": effective_cutoff,
        "outcomes": [
            {
                "weapon_id": o.candidate.signature.weapon_id,
                "source": o.candidate.signature.source,
                "field": o.candidate.signature.field,
                "signature_hash": o.candidate.signature.hash8(),
                "status": o.status,
                "reason": o.reason,
                "fixture_path": str(o.fixture_path) if o.fixture_path else None,
                "verification": o.verification,
            }
            for o in report.outcomes
        ],
    }
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
    # Sync difficulty from save file when available — the --difficulty CLI
    # flag is a default for the metadata, but the save file is authoritative
    # once the game has written one (matches the cross-check in
    # cmd_auto_turn). Falls through silently if the save file isn't readable
    # (fresh install, no profile yet).
    _live_diff = _read_save_file_difficulty()
    if _live_diff is not None and _live_diff != session.difficulty:
        _ses_label = _DIFFICULTY_LABELS.get(
            session.difficulty, str(session.difficulty)
        )
        _save_label = _DIFFICULTY_LABELS.get(_live_diff, str(_live_diff))
        print(
            f"[new_run] difficulty synced from save file: "
            f"{session.difficulty} ({_ses_label}) -> "
            f"{_live_diff} ({_save_label})"
        )
        session.difficulty = _live_diff
    # Fix B 2026-04-28 — explicit wipe of run-scoped soft-disable state.
    # ``new_run`` already produces a fresh session via the dataclass default
    # (disabled_actions=[]), but a future refactor that inherits prior
    # session fields would silently carry stale disables across runs. The
    # 2026-04-28 Run-2 defeat showed that's a -40k-score-floor bug in
    # waiting; making the wipe explicit (and logged) is cheap insurance.
    if session.disabled_actions:
        for entry in list(session.disabled_actions):
            print(
                f"[new_run] dropping stale disable: "
                f"weapon={entry.get('weapon_id', '?')} "
                f"confidence={entry.get('confidence', 'unset')} "
                f"reason=\"new_run_squad_change\""
            )
    session.disabled_actions = []
    session.save()

    # Write run manifest
    _write_manifest(session)

    logger = DecisionLog(session.run_id)
    logger.log_custom("New Run", (
        f"Squad: {squad}\n"
        f"Achievements: {achievements or 'none'}\n"
        f"Difficulty: {session.difficulty}\n"
        f"Tags: {tags or 'none'}"
    ))

    result = {
        "run_id": session.run_id,
        "squad": squad,
        "difficulty": session.difficulty,
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
        _infer_webb_egg_adjacency(bd["units"])

    # Inject weights
    if weights:
        bd["eval_weights"] = weights

    # Inject mine data from save file ONLY on turn 0. After turn 0 the Lua
    # bridge is authoritative — stale save-file mines produce phantom kills
    # (see reader.py for the same gate and the m02 t01 a2 incident).
    if "tiles" in bd and bd.get("turn", -1) <= 0:
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

    from src.model.board import _compute_pilot_value as _cpv
    for ud in bd.get("units", []):
        if ud.get("mech"):
            ud["pilot_value"] = _cpv(
                ud.get("pilot_id", ""), ud.get("pilot_skills", []),
                ud.get("max_hp", 0), ud.get("type", ""),
                ud.get("pilot_level", 0),
            )

    # Phase 3: committed weapon-def overrides. _solve_with_rust is the
    # replay/tuner path; base overrides stay active so replayed scores
    # agree with live solves.
    from src.solver.weapon_overrides import (
        load_base_overrides as _load_base_ovr,
        inject_into_bridge as _inject_ovr,
    )
    _inject_ovr(bd, base=_load_base_ovr())
    # Mission-aware "do not kill X" bonus-objective resolver — replay
    # parity with live solves. Same precedence rules: pre-populated
    # bridge entry wins, else data/mission_bonus_objectives.json,
    # else empty (penalty no-ops).
    from src.solver.mission_bonus_objectives import (
        inject_into_bridge as _inject_bonus_obj,
    )
    _inject_bonus_obj(bd)

    # Sim v28: stamp `is_infinite_spawn` on replayed/tuned bridge_data so
    # the Rust solver's future_factor floor (0.5) kicks in on boss /
    # Mission_Infinite missions. Live bridge reads route this through
    # `src/bridge/reader.py`, but replays load straight from recordings
    # (bridge_state was captured before the field existed) and the tuner
    # corpus pre-dates the field too. Idempotent: only sets when missing.
    if "is_infinite_spawn" not in bd:
        from src.bridge.reader import _is_infinite_spawn_mission
        bd["is_infinite_spawn"] = _is_infinite_spawn_mission(
            bd.get("mission_id") or ""
        )

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
    # Load active.json weights so replay reflects the current weight bundle
    # rather than Rust's compiled defaults (caller can still pass --no-rust
    # to use the Python solver, which already loads active.json elsewhere).
    eval_weights_dict = None
    weights_path = Path(__file__).parent.parent.parent / "weights" / "active.json"
    if weights_path.exists():
        try:
            with open(weights_path) as wf:
                weight_data = json.load(wf)
            eval_weights_dict = weight_data.get("weights")
        except (json.JSONDecodeError, IOError):
            pass

    if use_rust:
        try:
            solution = _solve_with_rust(bridge_data, time_limit, weights=eval_weights_dict)
        except Exception as e:
            print(f"  Rust solver error: {e}")

    if solution is None:
        from src.solver.solver import Solution
        print("  ERROR: Rust solver failed — no solution available")
        solution = Solution()

    # Replay for enriched data
    enriched = None
    if solution.actions:
        enriched = replay_solution(bridge_data, solution, spawns)

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
        _infer_webb_egg_adjacency(bridge_data["units"])

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

    from src.model.board import _compute_pilot_value as _cpv
    for ud in bridge_data.get("units", []):
        if ud.get("mech"):
            ud["pilot_value"] = _cpv(
                ud.get("pilot_id", ""), ud.get("pilot_skills", []),
                ud.get("max_hp", 0), ud.get("type", ""),
                ud.get("pilot_level", 0),
            )

    # Forward the soft-disable blocklist on re-solves too, otherwise the
    # Rust solver could pick the disabled weapon again on the same turn
    # the detector just flagged it.
    if session.disabled_actions:
        bridge_data["disabled_actions"] = list(session.disabled_actions)
    # Phase 3: committed weapon-def overrides (same as cmd_solve).
    from src.solver.weapon_overrides import (
        load_base_overrides as _load_base_ovr,
        inject_into_bridge as _inject_ovr,
    )
    _inject_ovr(bridge_data, base=_load_base_ovr())
    # Mission-aware "do not kill X" bonus-objective resolver (same as
    # cmd_solve, sim v21). Empty list on missions without a "do not
    # kill" bonus → penalty no-ops.
    from src.solver.mission_bonus_objectives import (
        inject_into_bridge as _inject_bonus_obj,
    )
    _inject_bonus_obj(bridge_data)

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
            enriched = _replay(bridge_data, solution, spawns,
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


def _research_peek(session: RunSession, limit: int = 3) -> list[dict]:
    """Return the first ``limit`` non-``done`` entries from the research queue.

    Used by ``cmd_auto_turn`` to surface an "INVESTIGATING" status line
    (#P2-7) so the user sees the between-turn research pipeline has
    a backlog, not a stall.

    We include both ``pending`` and ``in_progress`` entries — a caller
    that actually runs the research will flip entries to
    ``in_progress`` as it works them, and the line should still show
    that work is happening.
    """
    out: list[dict] = []
    for entry in session.research_queue:
        if entry.get("status") in (None, "pending", "in_progress"):
            out.append({
                "type": entry.get("type", ""),
                "terrain_id": entry.get("terrain_id"),
                "status": entry.get("status", "pending"),
                "attempts": entry.get("attempts", 0),
                "first_seen_turn": entry.get("first_seen_turn", 0),
            })
            if len(out) >= limit:
                break
    return out


def _narrate_fuzzy(
    detections: list[dict],
    soft_disables: list[dict],
    unknowns: dict,
    research_peek: list[dict] | None = None,
) -> None:
    """Print one-line human-readable summaries of self-healing events.

    Called once per turn from ``cmd_auto_turn``. Kept separate from the
    structured return dict so the operator can follow along without
    parsing JSON, while automated callers still get the full data.

    ``research_peek`` (#P2-7) is the head of ``session.research_queue``.
    Surfacing it tells the user the game didn't freeze — the between-turn
    processor is either about to look into a novel pawn/terrain or is
    mid-research on one.
    """
    research_peek = research_peek or []
    has_research = bool(research_peek)
    if (
        not detections
        and not soft_disables
        and not (unknowns.get("types") or unknowns.get("terrain_ids"))
        and not has_research
    ):
        return

    print()
    if unknowns.get("types") or unknowns.get("terrain_ids"):
        bits = []
        if unknowns.get("types"):
            bits.append(f"types={','.join(unknowns['types'])}")
        if unknowns.get("terrain_ids"):
            bits.append(f"terrain={','.join(unknowns['terrain_ids'])}")
        print(f"  UNKNOWNS flagged: {' '.join(bits)}")

    for det in detections:
        ctx = det.get("context") or {}
        weapon = ctx.get("weapon") or "?"
        tier = det.get("proposed_tier")
        conf = det.get("confidence")
        freq = det.get("frequency")
        asym = det.get("asymmetry") or []
        asym_str = f" [{','.join(asym)}]" if asym else ""
        gap_str = " model_gap" if det.get("model_gap") else ""
        print(
            f"  FUZZY: {det.get('top_category')} on {weapon} "
            f"(mech {ctx.get('mech_uid')} {ctx.get('sub_action')}#"
            f"{ctx.get('action_index')}) "
            f"freq={freq} tier={tier} conf={conf:.2f}{asym_str}{gap_str}"
        )

    for sd in soft_disables:
        new_marker = "new" if sd.get("new_entry") else "extended"
        print(
            f"  SOFT-DISABLE ({new_marker}): {sd['weapon_id']} until turn "
            f"{sd['expires_turn']} (cause={sd['cause']}, "
            f"freq={sd.get('frequency')})"
        )

    for entry in research_peek:
        # Compact "investigating: <Type> / <terrain_id>" line. One or
        # the other is always "" — we show whichever is set.
        t = entry.get("type") or ""
        tid = entry.get("terrain_id")
        label = " / ".join(x for x in (t, tid) if x) or "?"
        status = entry.get("status", "pending")
        attempts = entry.get("attempts", 0)
        tail = (f" (attempt {attempts})" if attempts else
                " (not yet researched)")
        print(f"  INVESTIGATING [{status}]: {label}{tail}")


# Cap on how many distinct weapons may be soft-disabled simultaneously
# for the active squad. Sets a ceiling on auto-tuner blast radius — the
# 2026-04-28 run caged 3/3 squad weapons in a single mission when the
# threshold was 2; even with the new threshold of 3, a wave of upstream
# sim drift could theoretically still reach 3+ weapons. This cap keeps
# the squad playable: at most 2 simultaneously caged, the rest narrate.
# Existing entries (already over the cap when this code first runs) are
# left in place — the cap is prospective only.
_SOFT_DISABLE_PER_RUN_CAP = 2


def _maybe_soft_disable(
    session: RunSession,
    signal: dict,
    turn: int,
    fired: list[dict],
    window: int = 3,
    run_id: str | None = None,
) -> None:
    """Apply the Tier 2 response if the signal proposes it.

    Writes to ``session.disabled_actions`` and appends a narrator-friendly
    summary to ``fired`` so ``cmd_auto_turn`` can surface the action in
    its return dict + terminal output.

    Expiry is ``turn + window`` so the block lives through the next
    ``window`` turns (inclusive). Phase 1 uses a fixed window; Phase 2
    will gate expiry on topology change (new Vek spawn, building lost).
    """
    if signal.get("proposed_tier") != 2:
        return
    weapon = (signal.get("context") or {}).get("weapon")
    if not weapon:
        return
    cause = signal.get("signature", "unknown")
    expires = turn + window

    # Per-run cap (Fix #4 2026-04-28): if we already have N distinct
    # weapons disabled and this would add a new one, log+skip rather
    # than cage the rest of the squad. Re-flagging an already-disabled
    # weapon (extending expiry / appending cause) bypasses the cap by
    # definition — it doesn't grow the disabled set.
    already = {e.get("weapon_id") for e in session.disabled_actions}
    if weapon not in already and len(already) >= _SOFT_DISABLE_PER_RUN_CAP:
        print(
            f"  SOFT-DISABLE CAP: would have disabled {weapon} "
            f"(cause={cause}, freq={signal.get('frequency')}, "
            f"conf={signal.get('confidence')}) but {len(already)} weapons "
            f"already caged ({sorted(already)}); narrating instead."
        )
        fired.append({
            "weapon_id": weapon,
            "cause": cause,
            "expires_turn": expires,
            "confidence": signal.get("confidence"),
            "frequency": signal.get("frequency"),
            "new_entry": False,
            "skipped_by_cap": True,
        })
        return

    added = session.add_disabled_action(
        weapon_id=weapon, cause=cause, expires_turn=expires,
    )
    fired.append({
        "weapon_id": weapon,
        "cause": cause,
        "expires_turn": expires,
        "confidence": signal.get("confidence"),
        "frequency": signal.get("frequency"),
        "new_entry": added,
    })
    # Persist cross-run: only on first firing in this session so one bad run
    # doesn't multi-count the same signature.
    if added:
        weapon_penalty_log.record_soft_disable(
            signature=cause, weapon_id=weapon, run_id=run_id or "",
        )


def _maybe_flag_grid_drop(
    investigations: list,
    diff,
    classification: dict,
    predicted: dict,
    actual_board,
    context: dict,
    run_id: str,
    turn: int,
    failure_db_id: str,
) -> None:
    """Snapshot + queue an investigation when grid_power dropped unexpectedly.

    Fired from the per-sub-action desync hook. Caller decides what to do with
    the queued investigations at end-of-turn (see cmd_auto_turn's INVESTIGATE
    path). We don't halt execution mid-turn — the rest of the solver plan
    still runs, the game still reaches "waiting on End Turn click" — but the
    End Turn click is withheld until the investigation is resolved.
    """
    if "grid_power" not in classification.get("categories", ()):
        return

    # Extract the specific grid-power diff so the agent has a concrete figure.
    grid_scalar = None
    for sd in getattr(diff, "scalar_diffs", []) or []:
        if sd.get("field") == "grid_power":
            grid_scalar = sd
            break
    building_tile_diffs = [
        td for td in getattr(diff, "tile_diffs", []) or []
        if td.get("field") == "building_hp"
    ]

    # Write a minimal snapshot: predicted state + actual state + context.
    snap_label = f"grid_drop_{run_id}_t{turn:02d}_a{context.get('action_index', '?')}"
    snap_dir = SNAPSHOT_DIR / snap_label
    snap_dir.mkdir(parents=True, exist_ok=True)
    try:
        with (snap_dir / "predicted.json").open("w") as f:
            json.dump(predicted, f, indent=2, default=str)
        with (snap_dir / "actual_board.json").open("w") as f:
            json.dump(
                {
                    "grid_power": actual_board.grid_power,
                    "grid_power_max": actual_board.grid_power_max,
                    "units": [
                        {
                            "uid": u.uid, "type": u.type,
                            "x": u.x, "y": u.y,
                            "hp": u.hp, "max_hp": u.max_hp,
                            "team": u.team, "is_mech": u.is_mech,
                        }
                        for u in actual_board.units
                    ],
                    "tiles": [
                        [
                            {
                                "terrain": t.terrain,
                                "building_hp": getattr(t, "building_hp", 0),
                            }
                            for t in row
                        ]
                        for row in actual_board.tiles
                    ],
                },
                f, indent=2, default=str,
            )
        with (snap_dir / "context.json").open("w") as f:
            json.dump({
                "run_id": run_id,
                "turn": turn,
                "sub_action": context.get("sub_action"),
                "action_index": context.get("action_index"),
                "mech_uid": context.get("mech_uid"),
                "weapon": context.get("weapon"),
                "target": context.get("target"),
                "grid_power_diff": grid_scalar,
                "building_hp_diffs": building_tile_diffs,
                "failure_db_id": failure_db_id,
                "classification": classification,
            }, f, indent=2, default=str)
    except OSError as e:
        print(f"  [grid-drop] snapshot write failed: {e}")

    reason_parts: list[str] = []
    if grid_scalar:
        reason_parts.append(
            f"grid predicted {grid_scalar.get('predicted')}, actual "
            f"{grid_scalar.get('actual')} "
            f"({int(grid_scalar.get('actual') or 0) - int(grid_scalar.get('predicted') or 0):+d})"
        )
    if building_tile_diffs:
        reason_parts.append(f"{len(building_tile_diffs)} building hp diff(s)")
    reason = "; ".join(reason_parts) or "unexpected grid_power drop"

    investigations.append({
        "reason": reason,
        "snapshot_path": str(snap_dir),
        "failure_db_id": failure_db_id,
        "turn": turn,
        "action_index": context.get("action_index"),
        "weapon": context.get("weapon"),
        "mech_uid": context.get("mech_uid"),
    })
    print(f"  [grid-drop] flagged for investigation → {snap_label}")


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
    fuzzy_signal: dict | None = None,
) -> None:
    """Record a sub-action desync to the failure database.

    ``fuzzy_signal`` is the self-healing loop Phase 0 payload from
    ``src.solver.fuzzy_detector.evaluate`` — passed through unchanged
    into both the per-action recording and the failure_db record so
    the Phase 1 detector work has a training corpus to mine.
    """
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
    if fuzzy_signal is not None:
        verify_record["fuzzy_signal"] = fuzzy_signal
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
    if fuzzy_signal is not None:
        desync_trigger["fuzzy_signal"] = fuzzy_signal

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
            "simulator_version": _get_simulator_version(),
            "tags": list(session.tags),
        },
    )
    # Persist session so failure_events_this_run (appended at the hook
    # site just before this call) survives across CLI invocations.
    session.save()
    print(f"  DESYNC action {action_index} {phase}: "
          f"{diff.total_count()} diffs [{cat_label}]")


_WINNABILITY_SCORE_THRESHOLD = -100_000
_WINNABILITY_GRID_DROP = 2


def _check_winnability(turn: int, score: float,
                       grid_power_str: str | None,
                       predicted_outcome: dict) -> dict | None:
    """Return a warning dict if turn-1 solve looks catastrophically lost.

    Fires only on turn 1 (freshly post-deployment). Triggers when the
    solver score is below ``_WINNABILITY_SCORE_THRESHOLD`` AND the
    predicted post-enemy grid_power drops by ``_WINNABILITY_GRID_DROP`` or
    more vs. the current grid. Observational — never aborts.
    """
    if turn != 1:
        return None
    if not isinstance(grid_power_str, str) or "/" not in grid_power_str:
        return None
    try:
        current_grid = int(grid_power_str.split("/", 1)[0])
    except (ValueError, TypeError):
        return None
    predicted_grid = predicted_outcome.get("grid_power")
    if not isinstance(predicted_grid, int):
        return None
    if score >= _WINNABILITY_SCORE_THRESHOLD:
        return None
    if predicted_grid > current_grid - _WINNABILITY_GRID_DROP:
        return None
    bar = "=" * 60
    print(bar)
    print(f"! ABORT WARNING — solver score {score:.0f} on turn 1")
    print(f"! Predicted grid: {current_grid} -> {predicted_grid}")
    print("! Position is likely unwinnable. Recommend: forfeit and")
    print("! pick a different mission. Continue at your own risk.")
    print(bar)
    return {
        "score": float(score),
        "predicted_grid": predicted_grid,
        "current_grid": current_grid,
    }


def cmd_auto_turn(profile: str = "Alpha", time_limit: float = 10.0,
                  wait_for_turn: bool = True, max_wait: float = 45.0) -> dict:
    """Execute a combat turn via bridge with per-sub-action verification.

    For each mech action, executes MOVE and ATTACK as separate sub-actions,
    reads actual board state after each, and diffs against the solver's
    predicted state. On desync, re-solves from the actual board for the
    remaining mechs.

    Flow per mech:
      MOVE → read → diff post_move → (re-solve on desync)
      ATTACK → read → diff post_attack → (re-solve on desync)

    When wait_for_turn=True (default), polls the bridge at entry until phase
    becomes combat_player or max_wait seconds elapse. This folds the enemy-
    phase wait inside one Python call so Claude doesn't burn LLM round-trips
    on polling after each End Turn click.

    Returns dict with turn results or error.
    """
    from src.solver.verify import diff_states, classify_diff
    from src.solver import fuzzy_detector
    from src.bridge.writer import _resolve_weapon_slot

    if not is_bridge_active():
        result = {"error": "Bridge not active — auto_turn requires bridge"}
        _print_result(result)
        return result

    # 1. Read state — with optional phase polling. If enemy phase is still
    #    animating from the previous End Turn click, block here instead of
    #    bouncing back to Claude with "Not in combat_player phase".
    #
    # Two signals must both clear before we solve:
    #   (a) phase == combat_player
    #   (b) active_mechs > 0 (or no mechs left alive — a terminal state)
    # The bridge flips (a) as soon as the logical turn starts, but (b) only
    # resets once enemy animations finish playing — that gap is 10–30s on
    # Hard difficulty. Solving inside the gap produces "No active mechs —
    # all have acted this turn" and does nothing. See
    # `feedback_enemy_turn_animation_window.md`.
    def _ready(rr: dict) -> bool:
        if rr.get("phase") != "combat_player":
            return False
        # If no mechs alive, caller needs to handle (mission will end) —
        # treat as ready so we exit the poll and report accurately.
        if "active_mechs" not in rr:
            return True
        return rr["active_mechs"] > 0

    if wait_for_turn:
        import time as _t
        poll_start = _t.time()
        read_result = cmd_read(profile=profile)
        prev_fp: str | None = None
        while _t.time() - poll_start < max_wait:
            phase = read_result.get("phase")
            # Terminal states — don't keep polling.
            if read_result.get("game_over") or phase in ("mission_end", "unknown"):
                break
            if _ready(read_result):
                # State-stability check: bridge may report
                # phase=combat_player + active_mechs>0 while still listing
                # units that died during the just-finished enemy phase
                # (animations propagate to the JSON dump on a separate
                # tick). Require two consecutive reads with matching unit
                # rosters before exiting. See feedback_enemy_turn_
                # animation_window.md and m13 t03 phantom-uid retrospective.
                _peek_data = (
                    read_state() if is_bridge_active() else None
                )
                cur_fp = _unit_roster_fingerprint(_peek_data)
                if prev_fp is not None and cur_fp == prev_fp:
                    break
                prev_fp = cur_fp
            else:
                prev_fp = None
            _t.sleep(1.5)
            read_result = cmd_read(profile=profile)
    else:
        read_result = cmd_read(profile=profile)

    phase = read_result.get("phase")
    if phase != "combat_player":
        result = {"error": f"Not in combat_player phase: {phase}", "phase": phase}
        _print_result(result)
        return result
    if read_result.get("active_mechs", 1) == 0:
        result = {
            "error": "No active mechs after polling — animations still playing "
                     f"or all mechs dead. Waited {max_wait}s.",
            "phase": phase,
            "active_mechs": 0,
        }
        _print_result(result)
        return result

    # Stale active_solution guard: if a previous auto_turn invocation
    # cached a solution against a now-stale roster (the m13 t03 phantom-
    # uid bug), drop it before we solve fresh. Any verify_action against
    # the stale predicted_states would fire false-positive desyncs.
    _stale_session = _load_session()
    if _stale_session.active_solution is not None:
        cached_fp = _stale_session.active_solution.input_fingerprint
        cached_turn = _stale_session.active_solution.turn
        cur_turn = read_result.get("turn", 0)
        cur_data = read_state() if is_bridge_active() else None
        cur_fp = _unit_roster_fingerprint(cur_data)
        # Different turn → the next solve will overwrite it anyway;
        # mismatched fingerprint on the same turn → stale cache.
        if (cached_turn != cur_turn
                or (cached_fp and cur_fp and cached_fp != cur_fp)):
            _stale_session.active_solution = None
            _stale_session.actions_executed = 0
            _stale_session.save()

    # Research gate — pick up the flag cmd_read already set when
    # either (a) unknown_detector flagged name novelty or (b)
    # has_actionable_research found a queued behavior-novelty entry
    # whose target is on the board. Both cases must block the solver;
    # in case (b) the ``unknowns`` field is empty, so we fall back to
    # a zero-unknowns envelope that still points at research_next.
    # See CLAUDE.md rule 20.
    if read_result.get("requires_research"):
        from src.solver.research_gate import research_gate_envelope
        gate = research_gate_envelope(read_result.get("unknowns"))
        if gate is None:
            gate = {
                "error": "RESEARCH_REQUIRED",
                "unknowns": read_result.get("unknowns") or {},
                "next": "cmd_research_next",
                "message": (
                    "Queued research entry actionable on current board "
                    "(behavior novelty from a prior desync). Resolve "
                    "before solving. See CLAUDE.md rule 20."
                ),
            }
        _print_result(gate)
        return gate

    turn = read_result.get("turn", 0)
    print(f"\n{'='*50}")
    print(f"AUTO TURN {turn} (verify-after-every-sub-action)")
    print(f"{'='*50}")

    # Difficulty cross-check — fires once per auto_turn call. Catches the
    # Timeline-Lost-continuation case where session.difficulty is stale
    # Python metadata that no longer matches the in-game UI. Save file is
    # authoritative; we update session metadata in-memory so downstream
    # writers (manifests, run summaries) record the correct value. See
    # CLAUDE.md note on stale session.difficulty.
    import sys as _sys
    _live_diff = _read_save_file_difficulty(profile)
    _diff_session = _load_session()
    if (_live_diff is not None
            and _diff_session.difficulty != _live_diff):
        _ses_label = _DIFFICULTY_LABELS.get(
            _diff_session.difficulty, str(_diff_session.difficulty)
        )
        _save_label = _DIFFICULTY_LABELS.get(_live_diff, str(_live_diff))
        print(
            f"[DIFFICULTY_MISMATCH] session={_diff_session.difficulty} "
            f"({_ses_label}), save_file={_live_diff} ({_save_label}). "
            f"Trusting save file.",
            file=_sys.stderr,
        )
        _diff_session.difficulty = _live_diff
        _diff_session.save()

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

    # Self-healing loop Phase 1: prune expired blocklist entries and
    # snapshot the evidence window so we can report what fired THIS turn
    # (the suffix of failure_events_this_run after processing) instead
    # of dumping the whole run's history.
    session.prune_disabled_actions(turn)
    pre_turn_event_count = len(session.failure_events_this_run)
    soft_disables_fired_this_turn: list[dict] = []
    grid_drop_investigations: list[dict] = []
    unknowns_flagged = read_result.get("unknowns") or {}

    # Load predicted_states from the solve recording via the schema-aware
    # helper so future beam-format records (Task #10) route correctly.
    from src.solver.verify import predicted_states_from_solve_record
    run_dir = _recording_dir(session)
    mi = session.mission_index
    solve_file = run_dir / f"m{mi:02d}_turn_{turn:02d}_solve.json"
    predicted_states = []
    predicted_outcome: dict = {}
    if solve_file.exists():
        try:
            with open(solve_file) as f:
                solve_record = json.load(f)
            predicted_states = predicted_states_from_solve_record(solve_record)
            predicted_outcome = (solve_record.get("data") or {}).get("predicted_outcome") or {}
        except (json.JSONDecodeError, OSError):
            pass

    # Pre-turn-1 winnability check — if the solver scored catastrophically low
    # AND grid power is forecast to drop ≥2 on turn 1, the position is most
    # likely unwinnable. Surface a loud banner so the operator can forfeit
    # before sinking more turns into a lost mission. Observational only —
    # never auto-aborts (CLAUDE.md "Executing actions with care").
    winnability_warning: dict | None = _check_winnability(
        turn, score, read_result.get("grid_power"), predicted_outcome
    )

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
                    fuzzy_signal = fuzzy_detector.evaluate(
                        diff, classification,
                        context={
                            "mech_uid": mech_uid,
                            "phase": "move",
                            "sub_action": "move",
                            "action_index": actions_completed,
                            "turn": turn,
                            "weapon": action.weapon,
                            "target": list(action.target),
                        },
                        prior_events=(
                            weapon_penalty_log.synthetic_prior_events()
                            + session.failure_events_this_run
                        ),
                    )
                    session.failure_events_this_run.append(fuzzy_signal)
                    _maybe_soft_disable(session, fuzzy_signal, turn,
                                        fired=soft_disables_fired_this_turn,
                                        run_id=session.run_id)
                    _enqueue_behavior_novelty(session, diff, turn)
                    _log_sub_action_desync(
                        session, "move", actions_completed, mech_uid,
                        pred_post_move, actual_board, diff, classification, turn,
                        fuzzy_signal=fuzzy_signal,
                    )
                    _maybe_flag_grid_drop(
                        grid_drop_investigations, diff, classification,
                        pred_post_move, actual_board,
                        context={
                            "mech_uid": mech_uid, "sub_action": "move",
                            "action_index": actions_completed,
                            "weapon": action.weapon,
                            "target": list(action.target),
                        },
                        run_id=session.run_id or "default",
                        turn=turn,
                        failure_db_id=(
                            f"{session.run_id or 'default'}_"
                            f"m{session.mission_index:02d}_t{turn:02d}_"
                            f"per_sub_action_desync_move_a{actions_completed}"
                        ),
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
                fuzzy_signal = fuzzy_detector.evaluate(
                    diff, classification,
                    context={
                        "mech_uid": mech_uid,
                        "phase": "attack",
                        "sub_action": "attack",
                        "action_index": actions_completed,
                        "turn": turn,
                        "weapon": action.weapon,
                        "target": list(action.target),
                    },
                    prior_events=session.failure_events_this_run,
                )
                session.failure_events_this_run.append(fuzzy_signal)
                _maybe_soft_disable(session, fuzzy_signal, turn,
                                    fired=soft_disables_fired_this_turn,
                                    run_id=session.run_id)
                _enqueue_behavior_novelty(session, diff, turn)
                _log_sub_action_desync(
                    session, "attack", actions_completed, mech_uid,
                    pred_post_attack, actual_board, diff, classification, turn,
                    fuzzy_signal=fuzzy_signal,
                )
                _maybe_flag_grid_drop(
                    grid_drop_investigations, diff, classification,
                    pred_post_attack, actual_board,
                    context={
                        "mech_uid": mech_uid, "sub_action": "attack",
                        "action_index": actions_completed,
                        "weapon": action.weapon,
                        "target": list(action.target),
                    },
                    run_id=session.run_id or "default",
                    turn=turn,
                    failure_db_id=(
                        f"{session.run_id or 'default'}_"
                        f"m{session.mission_index:02d}_t{turn:02d}_"
                        f"per_sub_action_desync_attack_a{actions_completed}"
                    ),
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

    fuzzy_detections = session.failure_events_this_run[pre_turn_event_count:]
    solver_gap_events = sum(1 for s in fuzzy_detections if s.get("model_gap"))

    if end_result.get("status") == "PLAN":
        # Grid-drop investigation gate — fire-now per CLAUDE.md rule 22. The
        # bridge has already deactivated mechs via SetActive, but the MCP
        # End Turn click is withheld: the caller must resolve every queued
        # investigation (or choose to skip) before sending the batch.
        if grid_drop_investigations:
            result = {
                "status": "INVESTIGATE",
                "turn": turn,
                "actions_completed": actions_completed,
                "score": score,
                "re_solves": re_solve_count,
                "investigations": grid_drop_investigations,
                "pending_end_turn_batch": end_result["batch"],
                "bridge_ack": end_result.get("bridge_ack"),
                "next_step": (
                    "Resolve each investigation (see CLAUDE.md rule 22) "
                    "before dispatching pending_end_turn_batch."
                ),
                "fuzzy_detections": fuzzy_detections,
                "soft_disabled": list(session.disabled_actions),
                "soft_disables_fired_this_turn": soft_disables_fired_this_turn,
                "unknowns_flagged": unknowns_flagged,
                "solver_gap_events": solver_gap_events,
                "research_queue_peek": _research_peek(session),
            }
            if winnability_warning:
                result["winnability_warning"] = winnability_warning
            _narrate_fuzzy(fuzzy_detections, soft_disables_fired_this_turn,
                           unknowns_flagged,
                           research_peek=result["research_queue_peek"])
            _print_result(result)
            return result

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
            "fuzzy_detections": fuzzy_detections,
            "soft_disabled": list(session.disabled_actions),
            "soft_disables_fired_this_turn": soft_disables_fired_this_turn,
            "unknowns_flagged": unknowns_flagged,
            "solver_gap_events": solver_gap_events,
            "research_queue_peek": _research_peek(session),
        }
        if winnability_warning:
            result["winnability_warning"] = winnability_warning
        _narrate_fuzzy(fuzzy_detections, soft_disables_fired_this_turn,
                       unknowns_flagged,
                       research_peek=result["research_queue_peek"])
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
        "fuzzy_detections": fuzzy_detections,
        "soft_disabled": list(session.disabled_actions),
        "soft_disables_fired_this_turn": soft_disables_fired_this_turn,
        "unknowns_flagged": unknowns_flagged,
        "solver_gap_events": solver_gap_events,
        "research_queue_peek": _research_peek(session),
    }
    if winnability_warning:
        result["winnability_warning"] = winnability_warning
    _narrate_fuzzy(fuzzy_detections, soft_disables_fired_this_turn,
                   unknowns_flagged,
                   research_peek=result["research_queue_peek"])

    if post_board and post_board.grid_power <= 0:
        result["game_over"] = True
        print(f"  GAME OVER — grid power dropped to 0")

    print(f"  Turn {turn} complete: {actions_completed} actions, "
          f"score={score:.0f}, grid={post_grid}/{post_grid_max}, "
          f"re-solves={re_solve_count}, next={post_phase}")

    _print_result(result)
    return result


# Hazard severity classification used by deploy filtering.
#
#   0  none        — plain ground / forest / sand / road / building rubble.
#   1  conveyor    — pad/belt slides the mech off the deploy tile silently.
#   1  teleporter  — pad teleports the mech to the paired endpoint.
#   2  freeze_mine — freezes the mech (invincible+immobilized for several
#                    turns, wastes the unit but doesn't kill it).
#   3  old_earth_mine — KILLS any unit that stops on it. Bypasses shield.
#
# The recommender filters out severity ≥ 1 by default and only falls back
# to higher-severity tiles when the deploy zone has fewer than 3 safe ones.
_HAZARD_SEVERITY: dict[str, int] = {
    "conveyor": 1,
    "teleporter": 1,
    "freeze_mine": 2,
    "old_earth_mine": 3,
}


def _teleporter_tile_set(board) -> set[tuple[int, int]]:
    """Collect every (x, y) that appears as a teleporter-pair endpoint."""
    tiles: set[tuple[int, int]] = set()
    for pair in getattr(board, "teleporter_pairs", []) or []:
        if len(pair) >= 4:
            tiles.add((pair[0], pair[1]))
            tiles.add((pair[2], pair[3]))
    return tiles


def classify_deploy_hazard(board, x: int, y: int,
                           teleporter_tiles: set[tuple[int, int]] | None = None
                           ) -> str | None:
    """Return the hazard name for a deploy tile, or None if safe.

    The classification is the WORST hazard on the tile (highest severity).
    Forest is intentionally NOT a hazard — it only burns when damaged, so
    a mech that stops there pre-attack is unharmed.

    Cracked ground is rated separately by the ranker (cracked tiles get a
    score penalty rather than a hazard label) because a cracked tile is
    only dangerous if the mech is later attacked while standing on it,
    which is a positional concern rather than a "stops here = bad" hazard.
    """
    if teleporter_tiles is None:
        teleporter_tiles = _teleporter_tile_set(board)
    tile = board.tiles[x][y]
    # Severity-ordered checks so the most dangerous wins on overlapping items.
    if getattr(tile, "old_earth_mine", False):
        return "old_earth_mine"
    if getattr(tile, "freeze_mine", False):
        return "freeze_mine"
    if (x, y) in teleporter_tiles:
        return "teleporter"
    if getattr(tile, "conveyor", -1) >= 0:
        return "conveyor"
    return None


def recommend_deploy_tiles(board, deploy_zone: list) -> list[dict]:
    """Rank deployment tiles strategically and annotate hazard fallbacks.

    Returns a list of dicts (best first), each:
        {"x": int, "y": int, "hazard": str | None, "hazard_warning": bool}

    Strategy:
      * Score every non-occupied tile (proximity to enemies, building cover,
        forward-row bonus, cracked-ground penalty).
      * Pick up to 3 SAFE (hazard=None) tiles first, with spatial diversity
        and a forward-row guarantee.
      * If fewer than 3 safe tiles exist, fall back to hazard tiles in
        ASCENDING severity (conveyor/teleporter < freeze_mine < old_earth_mine).
        Each fallback pick is flagged with `hazard_warning=True` so the caller
        can surface a "reluctant" notice to the user.

    Severity order is documented at `_HAZARD_SEVERITY`.
    """
    enemies = [u for u in board.units if u.is_enemy and u.hp > 0]
    buildings = []
    for x in range(8):
        for y in range(8):
            t = board.tiles[x][y]
            if t.terrain == "building" and t.building_hp > 0:
                buildings.append((x, y))

    teleporter_tiles = _teleporter_tile_set(board)

    def dist(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)

    # Score every candidate tile. We DON'T drop hazardous tiles here — they
    # stay in the candidate pool with their hazard label so the fallback
    # logic can pick them when the safe pool is exhausted.
    scored: list[tuple[float, int, int, str | None]] = []
    for tile in deploy_zone:
        tx, ty = tile[0], tile[1]
        # Skip tiles already occupied
        if any(u.x == tx and u.y == ty for u in board.units):
            continue

        hazard = classify_deploy_hazard(board, tx, ty, teleporter_tiles)

        if enemies:
            min_e = min(dist(tx, ty, e.x, e.y) for e in enemies)
            avg_e = sum(dist(tx, ty, e.x, e.y) for e in enemies) / len(enemies)
        else:
            min_e, avg_e = 8.0, 8.0

        near_bldg = sum(1 for bx, by in buildings if dist(tx, ty, bx, by) <= 2)
        visual_row = 8 - tx
        forward = 1.0 if 4 <= visual_row <= 6 else 0.0

        # Cracked ground: any damage on this tile converts it to a Chasm and
        # the mech falls in. Massive does NOT save from Chasm. Deploying here
        # means a single adjacent enemy attack (incl. Volatile-Vek death
        # explosion from 1 tile away) can kill the mech before it ever acts.
        # Huge penalty so cracked tiles are only picked when no other option
        # exists (cf. R.S.T. Weather Watch, sim v15 investigation).
        cracked_penalty = -1000.0 if board.tiles[tx][ty].cracked else 0.0

        score = (-min_e * 3.0       # get within striking range
                 + near_bldg * 2.0   # protect nearby buildings
                 + forward * 5.0     # reward forward positioning
                 - avg_e * 1.0       # prefer overall closer to enemies
                 + cracked_penalty)  # almost-always exclude cracked ground
        scored.append((score, tx, ty, hazard))

    scored.sort(key=lambda s: s[0], reverse=True)

    safe_pool = [(s, x, y) for (s, x, y, h) in scored if h is None]
    hazard_pool_by_sev: dict[int, list[tuple[float, int, int, str]]] = {}
    for s, x, y, h in scored:
        if h is None:
            continue
        sev = _HAZARD_SEVERITY[h]
        hazard_pool_by_sev.setdefault(sev, []).append((s, x, y, h))

    # Greedy pick with diversity: avoid clustering within 1 tile.
    selected: list[dict] = []

    def _try_add(tx: int, ty: int, hazard: str | None, warning: bool) -> bool:
        if any(d["x"] == tx and d["y"] == ty for d in selected):
            return False
        selected.append({
            "x": tx,
            "y": ty,
            "hazard": hazard,
            "hazard_warning": warning,
        })
        return True

    # Pass 1: safe tiles, with diversity.
    for score, tx, ty in safe_pool:
        if len(selected) >= 3:
            break
        too_close = any(
            dist(tx, ty, d["x"], d["y"]) <= 1 for d in selected
        )
        if too_close and len(safe_pool) > len(selected) + 3:
            continue
        _try_add(tx, ty, None, False)

    # Ensure at least one safe tile is "forward" (rows 4-6 = bridge x 2-4),
    # mirroring the legacy guarantee.
    has_forward = any(2 <= d["x"] <= 4 and d["hazard"] is None for d in selected)
    if not has_forward and len(selected) == 3 and all(d["hazard"] is None for d in selected):
        for score, tx, ty in safe_pool:
            if 2 <= tx <= 4 and not any(d["x"] == tx and d["y"] == ty for d in selected):
                # Replace the LAST safe pick with a forward one.
                selected[-1] = {
                    "x": tx,
                    "y": ty,
                    "hazard": None,
                    "hazard_warning": False,
                }
                break

    # Pass 2: reluctant fallback in ascending severity. We only enter this
    # branch when fewer than 3 safe tiles exist on the deploy zone.
    if len(selected) < 3:
        for sev in sorted(hazard_pool_by_sev.keys()):
            for score, tx, ty, hazard in hazard_pool_by_sev[sev]:
                if len(selected) >= 3:
                    break
                _try_add(tx, ty, hazard, True)
            if len(selected) >= 3:
                break

    return selected


def rank_deploy_tiles(board, deploy_zone: list) -> list[tuple[int, int]]:
    """Backwards-compatible wrapper around `recommend_deploy_tiles`.

    Returns just `[(x, y), ...]` for callers that don't care about the
    hazard annotations. The richer `recommend_deploy_tiles()` output is
    used by `cmd_read` to print hazard warnings.
    """
    return [(d["x"], d["y"]) for d in recommend_deploy_tiles(board, deploy_zone)]


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
            enriched_old = replay_solution(bridge_data, sol_old, spawns)
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
            enriched_new = replay_solution(bridge_data, sol_new, spawns)
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
            enriched = replay_solution(bridge_data, sol_old, spawns)
            if enriched:
                outcome_old = enriched.get("predicted_outcome", outcome_old)
        if sol_new.actions:
            enriched = replay_solution(bridge_data, sol_new, spawns)
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
             time_limit: float = 5.0,
             since: str | None = None,
             no_cutoff: bool = False,
             accept_version_change: bool = False) -> dict:
    """Auto-tune solver weights by replaying recorded boards.

    Uses random search + coordinate refinement to find weight values
    that maximize the fixed (weight-independent) score across all
    recorded board states. Saves the best weights to a new version file
    and validates against the current weights.

    Data gate: refuses to run with fewer than min_boards recordings.

    Version gate: refuses to run if the failure corpus spans multiple
    simulator_version values (pre-bump rows describe sim output the
    current build no longer produces — tuning on them optimizes for a
    ghost). Pass ``accept_version_change=True`` to override after
    manually archiving the pre-bump corpus. See CLAUDE.md §Operational
    Rules for the archival procedure.

    The failure corpus used for the penalty term honors the shared
    mining cutoff (``data/mining_cutoff.json``): pre-cutoff rows
    describe sim output the current build no longer produces and
    would waste penalty budget if counted. ``since`` overrides the
    config for bisects; ``no_cutoff=True`` disables the filter for
    historical audits.
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
    from src.solver.analysis import (
        load_failure_db, is_auto_fixable_by_tuning,
        filter_by_timestamp, load_failure_cutoff,
    )

    # Version gate: tuning on a corpus that mixes pre-bump and post-bump
    # simulator output produces weights optimized for a ghost build.
    # Entries missing simulator_version are legacy rows from before the
    # field existed; treat them as v1 (the first stamped version) — the
    # gate fires naturally when SIMULATOR_VERSION bumps to 2+ without
    # archival.
    current_sim = _get_simulator_version()
    all_rows_unfiltered = load_failure_db()
    versions_in_corpus = {r.get("simulator_version", 1) for r in all_rows_unfiltered}
    mixed = versions_in_corpus and versions_in_corpus != {current_sim}
    if mixed and not accept_version_change:
        result = {
            "error": "corpus_version_mismatch",
            "current_simulator_version": current_sim,
            "corpus_versions": sorted(versions_in_corpus),
            "hint": ("failure_db contains rows from a prior simulator "
                     "version. Archive the old corpus "
                     "(cp recordings/failure_db.jsonl "
                     "recordings/failure_db_snapshot_sim_v<N>.jsonl) and "
                     "start fresh, or rerun with "
                     "--accept-version-change if mixing is intentional."),
        }
        print(f"\n  VERSION GATE: corpus spans simulator versions "
              f"{sorted(versions_in_corpus)}, current is v{current_sim}. "
              f"Refusing to tune without --accept-version-change.")
        _print_result(result)
        return result
    if no_cutoff:
        cutoff_applied: str | None = None
        all_rows = load_failure_db()
    elif since is not None:
        cutoff_applied = since
        all_rows = filter_by_timestamp(load_failure_db(), since)
    else:
        cutoff_applied = load_failure_cutoff()
        all_rows = filter_by_timestamp(load_failure_db())
    raw_corpus = [r for r in all_rows if is_auto_fixable_by_tuning(r)]
    seen = set()
    deduped = []
    for r in raw_corpus:
        key = (r.get("run_id"), r.get("mission"), r.get("trigger"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    failure_corpus = deduped[:20]
    if cutoff_applied:
        print(f"  Failure cutoff: {cutoff_applied}")
    else:
        print(f"  Failure cutoff: disabled")
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


def _mission_end_auto_commit(
    session: RunSession, outcome: str, mission_index: int,
    *,
    repo_root: "Path | None" = None,
) -> dict:
    """Stage mission artifacts, commit, push. Gracefully reports failures.

    Only stages mission-level artifacts (the run's recordings, active
    session file, the run's decision log, staged override candidates).
    Never ``git add -A`` — uncommitted code edits from the session
    stay out of the auto-commit, which matches the principle that
    mission_end records gameplay state, not code changes.

    ``repo_root`` overrides the default (inferred from ``__file__``)
    so tests can point the helper at a tmp-path checkout.

    Returns a small status dict the caller embeds in the mission_end
    result so the operator sees whether the commit landed and was
    pushed. Failures here never propagate — mission_end's primary job
    is recording the outcome, and git issues shouldn't mask that.
    """
    import subprocess

    repo = repo_root or Path(__file__).parent.parent.parent
    run_id = session.run_id
    mi = mission_index
    mission_name = session.current_mission or "mission"

    candidate_paths = [
        f"recordings/{run_id}",
        "sessions/active_session.json",
        f"logs/{run_id}_log.md",
        "data/weapon_overrides_staged.jsonl",
    ]
    existing = [p for p in candidate_paths if (repo / p).exists()]
    if not existing:
        return {"status": "skipped", "reason": "no stageable artifacts"}

    try:
        subprocess.run(
            ["git", "-C", str(repo), "add"] + existing,
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "status": "failed",
            "stage": "add",
            "error": (exc.stderr or str(exc)).strip(),
        }

    # Nothing actually staged (files unchanged) — skip the commit.
    diff_check = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if diff_check.returncode == 0:
        return {"status": "skipped", "reason": "no changes to commit"}

    commit_msg = (
        f"Mission end: {mission_name} — {outcome} "
        f"({run_id} m{mi:02d})\n\n"
        "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )
    try:
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", commit_msg],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "status": "failed",
            "stage": "commit",
            "error": (exc.stderr or str(exc)).strip(),
        }

    commit_hash = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    # Push is best-effort — commit locally even if push fails.
    push_result = subprocess.run(
        ["git", "-C", str(repo), "push", "origin", "main"],
        capture_output=True, text=True,
    )
    pushed = push_result.returncode == 0

    return {
        "status": "committed",
        "commit": commit_hash,
        "pushed": pushed,
        "push_error": (push_result.stderr or "").strip() if not pushed else None,
    }


def cmd_mission_end(
    outcome: str,
    notes: str = None,
    *,
    no_commit: bool = False,
) -> dict:
    """Record mission outcome on the active run.

    outcome: "win" or "loss"
    notes: optional free-text context
    no_commit: skip the default auto-commit + push of mission artifacts.

    Writes outcome to the run manifest.json and drops a small
    m{NN}_outcome.json pointer file in the run directory, then
    auto-commits + pushes the run's recordings, session state,
    decision log, and any staged override candidates. Pass
    ``--no-commit`` to skip the git step (e.g. mid-development
    runs where you don't want every mission cluttering main).
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

    _repo_root = Path(__file__).parent.parent.parent
    try:
        outcome_file_str = str(outcome_path.relative_to(_repo_root))
    except ValueError:
        outcome_file_str = str(outcome_path)
    result = {
        "run_id": session.run_id,
        "mission": mi,
        "outcome": outcome,
        "outcome_file": outcome_file_str,
        "manifest_updated": True,
    }

    if not no_commit:
        git_result = _mission_end_auto_commit(session, outcome, mi)
        result["git"] = git_result
        print(f"\n[mission_end git] {git_result}")

    # Advance the mission counter AFTER auto-commit (so the just-finished
    # mission's artifacts were staged under their own ``mi`` prefix), so
    # the NEXT mission's recordings land under ``m{mi+1:02d}_...``. Without
    # this bump every mission in a multi-mission run collides on m00_*
    # (see run 20260421_135801_843 where 5 missions all wrote m00_*).
    # Also reset per-mission blocklist state, mirroring ``advance_mission``.
    session.mission_index = mi + 1
    session.current_mission = ""
    session.last_mission_turn = -1
    session.disabled_actions = []
    session.save()
    result["next_mission_index"] = session.mission_index

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
