"""Run session state management with file locking.

Each CLI invocation is a short-lived process. The session file persists
state between invocations. File locking (fcntl.flock) prevents corruption
from rapid sequential calls. Atomic writes (tmp + os.replace) prevent
partial writes.

Adapted from the Demon Bluff solver's GameSession pattern.
"""

from __future__ import annotations

import atexit
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

SESSION_DIR = Path(__file__).parent.parent.parent / "sessions"
DEFAULT_SESSION_FILE = SESSION_DIR / "active_session.json"

# Module-level lock state
_lock_handle = None
_lock_path = None


def _acquire_lock(path: str | Path, timeout_s: float = 5.0):
    """Acquire a process-wide file lock.

    Holds the lock from first access until process exit, serializing
    read-modify-write commands and preventing JSON corruption.
    Re-entrant: if this process already holds the lock, returns immediately.
    """
    global _lock_handle, _lock_path
    import fcntl

    # Already locked by this process — re-entrant
    if _lock_handle is not None and _lock_path == str(path):
        return _lock_handle

    lock_path = f"{path}.lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    handle = open(lock_path, "a+b")
    deadline = time.time() + timeout_s

    while True:
        try:
            handle.seek(0)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.time() >= deadline:
                handle.close()
                raise TimeoutError(
                    f"Timed out acquiring session lock after {timeout_s}s. "
                    f"Is another process holding the lock?"
                )
            time.sleep(0.05)

    _lock_handle = handle
    _lock_path = str(path)
    return handle


def _release_lock():
    """Release the session file lock."""
    global _lock_handle, _lock_path
    if _lock_handle is None:
        return
    try:
        import fcntl
        fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        _lock_handle.close()
        _lock_handle = None
        _lock_path = None


atexit.register(_release_lock)


@dataclass
class SolverAction:
    """A single mech action from the solver."""
    mech_uid: int
    mech_type: str
    move_to: tuple[int, int] | None  # (x, y) or None if no move
    weapon: str                       # weapon ID or "" if no attack
    target: tuple[int, int]           # (x, y) or (-1, -1) if no attack
    description: str

    def to_dict(self) -> dict:
        return {
            "mech_uid": self.mech_uid,
            "mech_type": self.mech_type,
            "move_to": list(self.move_to) if self.move_to else None,
            "weapon": self.weapon,
            "target": list(self.target),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SolverAction:
        return cls(
            mech_uid=d["mech_uid"],
            mech_type=d["mech_type"],
            move_to=tuple(d["move_to"]) if d.get("move_to") else None,
            weapon=d.get("weapon", ""),
            target=tuple(d.get("target", (-1, -1))),
            description=d.get("description", ""),
        )


@dataclass
class ActiveSolution:
    """The current solver solution being executed."""
    actions: list[SolverAction]
    score: float
    turn: int  # which turn this solution is for
    # Fingerprint of the unit roster (uid,x,y,hp tuples) the solver
    # consumed when producing this plan. Used by cmd_auto_turn to
    # detect stale-state reuse when bridge animations had not yet
    # propagated unit deaths at solve time. Empty string for legacy
    # / synthetic solutions where no fingerprint is available.
    input_fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "score": self.score,
            "turn": self.turn,
            "input_fingerprint": self.input_fingerprint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ActiveSolution:
        return cls(
            actions=[SolverAction.from_dict(a) for a in d["actions"]],
            score=d["score"],
            turn=d["turn"],
            input_fingerprint=d.get("input_fingerprint", ""),
        )


@dataclass
class RunSession:
    """Persistent state for a single game run.

    Tracks run-level decisions, mission state, and the active solver
    solution so cmd_execute can index into it between CLI invocations.
    """

    # Run-level state
    run_id: str = ""
    squad: str = ""
    achievement_targets: list[str] = field(default_factory=list)
    difficulty: int = 0
    current_island: str = ""
    current_mission: str = ""
    islands_completed: list[str] = field(default_factory=list)
    mission_index: int = 0  # incremented when current_mission changes

    # Free-form tags for run classification (e.g. ["audit"] for env audit
    # playthroughs that should be filtered out of the tuner training corpus).
    tags: list[str] = field(default_factory=list)

    # Mission-level state
    current_turn: int = 0
    phase: str = "unknown"  # last detected phase

    # Active solution (stored so cmd_execute can index into it)
    active_solution: ActiveSolution | None = None
    actions_executed: int = 0  # how many actions from active_solution done

    # Cumulative stats
    buildings_lost: int = 0
    mechs_destroyed: int = 0
    enemies_killed: int = 0
    turns_played: int = 0

    # Decision history (append-only within a run)
    decisions: list[dict] = field(default_factory=list)

    # Per-mission post-enemy recording dedup set. Each int is the
    # ``solved_turn`` that already had ``_record_post_enemy`` fire, scoped
    # by the current ``mission_index``. Stored as a flat ``[mi, turn]``
    # list in JSON to round-trip cleanly through to_dict / from_dict.
    recorded_post_enemy_turns: list[list[int]] = field(default_factory=list)

    # Self-healing loop Phase 0 instrumentation. Each desync fired by
    # ``cmd_auto_turn`` appends the ``fuzzy_detector.evaluate`` output here,
    # producing an in-memory frequency window the Phase 1 detector can
    # consume without re-reading ``failure_db.jsonl``.
    failure_events_this_run: list[dict] = field(default_factory=list)

    # Phase 1 Tier 2 soft-disable blocklist. Each entry tells the solver
    # to apply a score bias on actions using ``weapon_id`` until
    # ``expires_turn`` (inclusive). Reset at mission boundaries.
    # Rust enforcement lands in #P1-3; the field exists now so the
    # detector can write entries and downstream Python can read them.
    disabled_actions: list[dict] = field(default_factory=list)

    # Phase 2 research queue. Populated when ``cmd_read`` sees a pawn
    # type or terrain id outside ``data/known_types.json``. The
    # between-turn processor pops one pending entry at a time, runs the
    # tooltip-capture + Vision pipeline, and marks status. Entries
    # persist across turns AND missions — the queue is a run-level TODO
    # list; it only resets when a new run starts.
    # Entry shape:
    #   {
    #     "type": str,           # unit type, "" if terrain-only
    #     "terrain_id": str|None, # terrain id, None if unit-only
    #     "mission_id": str,      # current_mission when first queued
    #     "first_seen_turn": int,
    #     "attempts": int,
    #     "status": "pending"|"in_progress"|"done"|"failed",
    #     "result": dict|None,    # extraction output once done
    #   }
    # Dedup key: ``(type, terrain_id)`` — the same unit type re-seen
    # later in the run extends ``attempts`` / updates metadata but does
    # not produce a second entry.
    research_queue: list[dict] = field(default_factory=list)

    # Layer 3 of the diagnosis loop. Populated by `verify_action --diagnose`
    # (or with ITB_AUTO_DIAGNOSE=1). Pending entries are drained by the
    # harness via `game_loop.py diagnose_next` between turns — NEVER on the
    # auto_turn hot path (45s enemy-animation budget). Spec: docs/
    # diagnosis_loop_design.md §8.
    # Entry shape:
    #   {
    #     "failure_id": str,
    #     "diff_signature": str,         # combined sha; for dedup
    #     "sim_version": int,
    #     "enqueued_at": str,            # ISO timestamp
    #     "status": "pending"|"done"|"failed",
    #     "diagnose_status": str|None,   # set after drain: rule_match / needs_agent / ...
    #     "rule_id": str|None,
    #     "markdown": str|None,
    #   }
    # Dedup key: (diff_signature, sim_version) — same diff in same sim
    # diagnoses to the same answer; no point re-enqueueing.
    diagnosis_queue: list[dict] = field(default_factory=list)

    # --- Solution management ---

    def set_solution(self, actions: list[SolverAction], score: float,
                     turn: int, input_fingerprint: str = ""):
        """Store a new solver solution. Resets execution counter."""
        self.active_solution = ActiveSolution(
            actions=actions, score=score, turn=turn,
            input_fingerprint=input_fingerprint,
        )
        self.actions_executed = 0

    def get_next_action(self) -> SolverAction | None:
        """Return the next unexecuted action, or None if all done."""
        if self.active_solution is None:
            return None
        if self.actions_executed >= len(self.active_solution.actions):
            return None
        return self.active_solution.actions[self.actions_executed]

    def get_action(self, index: int) -> SolverAction | None:
        """Return a specific action by index, or None if out of range."""
        if self.active_solution is None:
            return None
        if index >= len(self.active_solution.actions):
            return None
        return self.active_solution.actions[index]

    def mark_action_executed(self):
        """Increment the executed action counter."""
        self.actions_executed += 1

    def actions_remaining(self) -> int:
        """How many actions are left to execute."""
        if self.active_solution is None:
            return 0
        return len(self.active_solution.actions) - self.actions_executed

    # --- Mission tracking ---

    def advance_mission(self, mission_name: str):
        """Update mission and increment index if mission changed.

        Also clears the Tier 2 blocklist — a terrain-specific pattern
        in mission A (Volatile Vek, acid pools) shouldn't carry into
        mission B. ``failure_events_this_run`` intentionally persists
        across missions: if weapon X's push direction is wrong, that's
        a sim bug not an environment artifact, and the evidence stays
        valid the whole run.
        """
        if mission_name and mission_name != self.current_mission:
            self.current_mission = mission_name
            self.mission_index += 1
            self.disabled_actions = []

    # --- Decision tracking ---

    def record_decision(self, label: str, data: dict):
        """Append a decision to the history."""
        self.decisions.append({
            "timestamp": datetime.now().isoformat(),
            "turn": self.current_turn,
            "label": label,
            **data,
        })

    # --- Soft-disable blocklist (Phase 1 Tier 2) ---

    def add_disabled_action(
        self,
        weapon_id: str,
        cause: str,
        expires_turn: int,
        strategic_override: bool = False,
    ) -> bool:
        """Add a blocklist entry. Returns True if new, False if already present.

        Dedup key is ``weapon_id`` alone — a weapon is either disabled or
        not. If the same weapon is re-flagged, extend its expiry to the
        later of the two rather than stacking entries.
        """
        for entry in self.disabled_actions:
            if entry.get("weapon_id") == weapon_id:
                entry["expires_turn"] = max(entry.get("expires_turn", 0),
                                            expires_turn)
                if cause and cause not in entry.get("cause_pattern", ""):
                    # Preserve causal history as an "x|y" chain.
                    existing = entry.get("cause_pattern", "")
                    entry["cause_pattern"] = (
                        f"{existing}|{cause}" if existing else cause
                    )
                return False
        self.disabled_actions.append({
            "weapon_id": weapon_id,
            "cause_pattern": cause,
            "expires_turn": expires_turn,
            "strategic_override": strategic_override,
        })
        return True

    # --- Research queue (Phase 2) ---

    def enqueue_research(
        self,
        type_name: str,
        terrain_id: str | None,
        current_turn: int,
        *,
        kind: str | None = None,
        slot: int | None = None,
        diff_field: str | None = None,
        diff_predicted: object = None,
        diff_actual: object = None,
        severity: str | None = None,
    ) -> bool:
        """Add a research entry for a novel unit type or terrain id.

        Deduped by ``(type, terrain_id, kind, slot)``. If the tuple
        already exists, the function is idempotent — it does NOT
        increment ``attempts`` (that's the processor's job after it
        actually tries research).

        ``kind`` + ``slot`` disambiguate probes for the same unit type
        (e.g. ``kind="mech_weapon", slot=0`` vs ``slot=1``). Legacy
        callers pass neither and get the original
        ``(type, terrain_id)`` dedup behaviour — an entry without kind
        stores ``kind=None, slot=None``, which still compares equal
        across the compound key.

        Pass ``type_name=""`` for terrain-only entries and
        ``terrain_id=None`` for unit-only entries.

        ``diff_field`` / ``diff_predicted`` / ``diff_actual`` /
        ``severity`` attach the triggering desync metadata to the entry
        so ``drain_stale_behavior_novelty`` can auto-resolve catalogued
        types whose diff looks like benign model drift. Defaults leave
        the fields off the entry entirely so legacy callers stay
        schema-compatible.

        Returns True if a new entry was added, False if it was a dupe.
        """
        key = (type_name or "", terrain_id, kind, slot)
        for e in self.research_queue:
            existing = (
                e.get("type", ""),
                e.get("terrain_id"),
                e.get("kind"),
                e.get("slot"),
            )
            if existing == key:
                return False
        entry: dict = {
            "type": type_name or "",
            "terrain_id": terrain_id,
            "kind": kind,
            "slot": slot,
            "mission_id": self.current_mission,
            "first_seen_turn": current_turn,
            "attempts": 0,
            "status": "pending",
            "result": None,
        }
        if diff_field is not None:
            entry["diff_field"] = diff_field
            entry["diff_predicted"] = diff_predicted
            entry["diff_actual"] = diff_actual
        if severity is not None:
            entry["severity"] = severity
        self.research_queue.append(entry)
        return True

    def next_research_entry(self) -> dict | None:
        """Return the first pending entry, or None if the queue is drained.

        ``in_progress`` entries are skipped — the processor should finish
        (or fail) them before picking the next one. That keeps any recursive
        discovery from fanning out and tying up the research tier.
        """
        for e in self.research_queue:
            if e.get("status", "pending") == "pending":
                return e
        return None

    def mark_research(
        self,
        type_name: str,
        terrain_id: str | None,
        status: str,
        result: dict | None = None,
        *,
        kind: str | None = None,
        slot: int | None = None,
    ) -> bool:
        """Update status / bump attempts on the matching entry.

        ``status`` transitions:
          pending → in_progress   (processor picks it up)
          in_progress → done      (success; result captured)
          in_progress → failed    (extraction gave up after retries)
          in_progress → pending   (deferred — try again later)

        Each transition through ``in_progress`` increments ``attempts``
        so the processor can cap retry budget.

        ``kind`` + ``slot`` match the same compound key used by
        ``enqueue_research``; unset defaults preserve legacy
        ``(type, terrain_id)`` behaviour.

        Returns True if the entry was found and updated.
        """
        key = (type_name or "", terrain_id, kind, slot)
        for e in self.research_queue:
            existing = (
                e.get("type", ""),
                e.get("terrain_id"),
                e.get("kind"),
                e.get("slot"),
            )
            if existing == key:
                if status == "in_progress":
                    e["attempts"] = e.get("attempts", 0) + 1
                e["status"] = status
                if result is not None:
                    e["result"] = result
                return True
        return False

    def prune_disabled_actions(self, current_turn: int) -> int:
        """Drop entries whose ``expires_turn`` has passed. Returns drop count.

        Call at the start of each turn. Expiry is inclusive: an entry with
        ``expires_turn == current_turn`` is still active for this turn and
        drops next turn.
        """
        before = len(self.disabled_actions)
        self.disabled_actions = [
            e for e in self.disabled_actions
            if e.get("expires_turn", 0) >= current_turn
        ]
        return before - len(self.disabled_actions)

    # --- Serialization ---

    def to_dict(self) -> dict:
        d = {
            "run_id": self.run_id,
            "squad": self.squad,
            "achievement_targets": self.achievement_targets,
            "difficulty": self.difficulty,
            "current_island": self.current_island,
            "current_mission": self.current_mission,
            "islands_completed": self.islands_completed,
            "mission_index": self.mission_index,
            "current_turn": self.current_turn,
            "phase": self.phase,
            "active_solution": (
                self.active_solution.to_dict()
                if self.active_solution else None
            ),
            "actions_executed": self.actions_executed,
            "buildings_lost": self.buildings_lost,
            "mechs_destroyed": self.mechs_destroyed,
            "enemies_killed": self.enemies_killed,
            "turns_played": self.turns_played,
            "decisions": self.decisions,
            "recorded_post_enemy_turns": self.recorded_post_enemy_turns,
            "tags": self.tags,
            "failure_events_this_run": self.failure_events_this_run,
            "disabled_actions": self.disabled_actions,
            "research_queue": self.research_queue,
            "diagnosis_queue": self.diagnosis_queue,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> RunSession:
        sol_data = d.get("active_solution")
        return cls(
            run_id=d.get("run_id", ""),
            squad=d.get("squad", ""),
            achievement_targets=d.get("achievement_targets", []),
            difficulty=d.get("difficulty", 0),
            current_island=d.get("current_island", ""),
            current_mission=d.get("current_mission", ""),
            islands_completed=d.get("islands_completed", []),
            mission_index=d.get("mission_index", 0),
            current_turn=d.get("current_turn", 0),
            phase=d.get("phase", "unknown"),
            active_solution=(
                ActiveSolution.from_dict(sol_data)
                if sol_data else None
            ),
            actions_executed=d.get("actions_executed", 0),
            buildings_lost=d.get("buildings_lost", 0),
            mechs_destroyed=d.get("mechs_destroyed", 0),
            enemies_killed=d.get("enemies_killed", 0),
            turns_played=d.get("turns_played", 0),
            decisions=d.get("decisions", []),
            recorded_post_enemy_turns=d.get("recorded_post_enemy_turns", []),
            tags=d.get("tags", []),
            failure_events_this_run=d.get("failure_events_this_run") or [],
            disabled_actions=d.get("disabled_actions") or [],
            research_queue=d.get("research_queue") or [],
            diagnosis_queue=d.get("diagnosis_queue") or [],
        )

    # --- Persistence with file locking ---

    def save(self, path: str | Path = DEFAULT_SESSION_FILE):
        """Save session to JSON with file locking and atomic write."""
        path = Path(path)
        _acquire_lock(path)

        tmp_path = path.parent / f".tmp.{os.getpid()}.{path.name}"
        try:
            with open(tmp_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(path))
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    @classmethod
    def load(cls, path: str | Path = DEFAULT_SESSION_FILE) -> RunSession:
        """Load session from JSON with file locking."""
        path = Path(path)
        _acquire_lock(path)

        if not path.exists():
            return cls()

        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def new_run(cls, squad: str, achievements: list[str] = None,
                difficulty: int = 0,
                tags: list[str] = None) -> RunSession:
        """Create a fresh session for a new game run."""
        now = datetime.now()
        run_id = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"
        return cls(
            run_id=run_id,
            squad=squad,
            achievement_targets=achievements or [],
            difficulty=difficulty,
            tags=tags or [],
        )
