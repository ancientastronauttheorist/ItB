"""Append-only markdown decision log.

Every solver output, mech action, verification result, and phase
transition is timestamped and appended to a per-run log file.
This enables post-run analysis, regression debugging, and the
self-improvement feedback loop (CLAUDE.md Rule 9).

Adapted from the Demon Bluff solver's DecisionLog pattern.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class DecisionLog:
    """Append-only markdown log for a single game run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.log_file = LOG_DIR / f"{run_id}_log.md"
        os.makedirs(LOG_DIR, exist_ok=True)

        # Write header if new file
        if not self.log_file.exists():
            self._write(f"# Decision Log: {run_id}\n")
            self._write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def _write(self, text: str):
        with open(self.log_file, "a") as f:
            f.write(text)

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def log_turn_start(self, turn: int, board_summary: str):
        """Log the start of a new player turn."""
        self._write(f"\n---\n\n## Turn {turn} [{self._ts()}]\n\n")
        self._write(f"{board_summary}\n\n")

    def log_solver_output(self, score: float, actions: list[str],
                          threats: int = 0):
        """Log the solver's recommended solution."""
        self._write(f"### Solver Output [{self._ts()}]\n\n")
        self._write(f"Score: {score:.0f} | Threats: {threats}\n\n")
        for i, desc in enumerate(actions):
            self._write(f"{i+1}. {desc}\n")
        self._write("\n")

    def log_mech_action(self, action_index: int, description: str,
                        click_count: int):
        """Log a mech action being executed."""
        self._write(
            f"#### Action {action_index} [{self._ts()}]\n\n"
            f"{description} ({click_count} clicks)\n\n"
        )

    def log_verification(self, action_index: int, success: bool,
                         details: str = ""):
        """Log a verification result after mech execution."""
        status = "PASS" if success else "FAIL"
        self._write(f"Verify action {action_index}: **{status}**")
        if details:
            self._write(f" — {details}")
        self._write("\n\n")

    def log_phase_transition(self, old_phase: str, new_phase: str):
        """Log a game phase change."""
        self._write(
            f"Phase: {old_phase} → **{new_phase}** [{self._ts()}]\n\n"
        )

    def log_end_turn(self):
        """Log end of player turn."""
        self._write(f"End Turn [{self._ts()}]\n\n")

    def log_error(self, error_type: str, details: str,
                  recovery: str = ""):
        """Log an error with recovery action."""
        self._write(f"### ERROR: {error_type} [{self._ts()}]\n\n")
        self._write(f"{details}\n")
        if recovery:
            self._write(f"\nRecovery: {recovery}\n")
        self._write("\n")

    def log_custom(self, label: str, text: str):
        """Log Claude's own reasoning or notes."""
        self._write(f"#### {label} [{self._ts()}]\n\n")
        self._write(f"{text}\n\n")

    def log_run_end(self, outcome: str, stats: dict = None):
        """Log the end of a run."""
        self._write(f"\n---\n\n## Run End: {outcome} [{self._ts()}]\n\n")
        if stats:
            for k, v in stats.items():
                self._write(f"- {k}: {v}\n")
            self._write("\n")
