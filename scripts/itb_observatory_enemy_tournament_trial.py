#!/usr/bin/env python3
"""Run one fixed complete enemy-record tournament Observatory trial."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bridge.protocol import BridgeError, read_state, refresh_bridge_state_fresh  # noqa: E402
from src.bridge.writer import bridge_observatory_enemy_tournament_trial  # noqa: E402
from src.observatory.enemy_tournament_hw import (  # noqa: E402
    EnemyTournamentHwError,
    correlate_enemy_tournament_snapshot,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)


ACK_RE = re.compile(
    r"OK OBS_ENEMY_TOURNAMENT_TRIAL condition=(control|dormant|armed) "
    r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
    r"at=([0-7]),([0-7]) consumed_spawns=(\d+) candidates=(\d+) "
    r"selected=(\d+) queue=(\d+) complete=true\Z"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument(
        "--condition", choices=("control", "dormant", "armed"), required=True
    )
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--outcome-output", type=Path, required=True)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--analysis-output", type=Path)
    parser.add_argument("--timeout", type=float, default=75.0)
    return parser


def _artifact_root() -> Path:
    raw = os.environ.get("ITB_ARTIFACT_ROOT")
    if not raw:
        raise OSError("ITB_ARTIFACT_ROOT is required")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise OSError("ITB_ARTIFACT_ROOT must be absolute")
    resolved = root.resolve()
    repo = ROOT.resolve()
    if resolved == repo or resolved.is_relative_to(repo) or repo.is_relative_to(resolved):
        raise OSError("ITB_ARTIFACT_ROOT must not overlap the repository")
    return resolved


def _output(path: Path, root: Path, label: str) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.parent == candidate or not candidate.is_relative_to(root):
        raise OSError(f"{label} must be inside ITB_ARTIFACT_ROOT")
    if candidate.exists() or candidate.is_symlink():
        raise OSError(f"{label} already exists: {candidate}")
    return candidate


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _outcome_reasons(outcome: object, pawn_id: int) -> list[str]:
    if not isinstance(outcome, dict):
        return ["bridge_outcome_missing"]
    reasons: list[str] = []
    if outcome.get("mission_id") != "Mission_Power":
        reasons.append("bridge_mission_mismatch")
    if outcome.get("phase") != "combat_player":
        reasons.append("bridge_phase_mismatch")
    if outcome.get("spawning_tiles") != []:
        reasons.append("bridge_spawn_activity")
    if outcome.get("environment_danger") not in (None, []):
        reasons.append("bridge_environment_activity")
    if outcome.get("environment_danger_v2") not in (None, []):
        reasons.append("bridge_environment_v2_activity")
    units = outcome.get("units")
    enemies = (
        [unit for unit in units if isinstance(unit, dict) and unit.get("team") == 6]
        if isinstance(units, list)
        else []
    )
    if len(enemies) != 1:
        reasons.append("bridge_enemy_count_mismatch")
    elif enemies[0].get("uid") != pawn_id:
        reasons.append("bridge_enemy_id_mismatch")
    elif enemies[0].get("type") != "Firefly1":
        reasons.append("bridge_enemy_type_mismatch")
    elif enemies[0].get("has_queued_attack") is not True:
        reasons.append("bridge_queue_missing")
    return reasons


def run(args: argparse.Namespace) -> tuple[int, dict]:
    root = _artifact_root()
    trial_output = _output(args.trial_output, root, "trial output")
    outcome_output = _output(args.outcome_output, root, "outcome output")
    snapshot_output = None
    analysis_output = None
    if args.condition == "armed":
        if args.snapshot_output is None or args.analysis_output is None:
            raise ValueError("armed condition requires snapshot and analysis outputs")
        snapshot_output = _output(args.snapshot_output, root, "snapshot output")
        analysis_output = _output(args.analysis_output, root, "analysis output")
    elif args.snapshot_output is not None or args.analysis_output is not None:
        raise ValueError("only the armed condition accepts observer outputs")
    receipt = load_json_object(args.build_receipt, "enemy-tournament build receipt")
    module_sha256 = stable_file_sha256(args.module)

    ack = ""
    command_error = ""
    snapshot: dict | None = None
    outcome: dict | None = None
    try:
        ack, snapshot = bridge_observatory_enemy_tournament_trial(
            args.condition, args.capture_id, timeout=args.timeout
        )
        if not refresh_bridge_state_fresh(timeout=5.0):
            raise BridgeError("post-trial bridge state did not refresh")
        outcome = read_state()
        if not isinstance(outcome, dict):
            raise BridgeError("post-trial bridge state is unavailable")
    except Exception as exc:
        command_error = str(exc)

    ack_match = ACK_RE.fullmatch(ack)
    pawn_id = int(ack_match.group(3)) if ack_match else -1
    outcome_reasons = _outcome_reasons(outcome, pawn_id)
    analysis = None
    analysis_error = ""
    if args.condition == "armed" and snapshot is not None and outcome is not None:
        try:
            analysis = correlate_enemy_tournament_snapshot(
                snapshot,
                outcome,
                build_receipt=receipt,
                observed_module_sha256=module_sha256,
            )
        except Exception as exc:
            analysis_error = str(exc)

    if outcome is not None:
        _write(outcome_output, outcome)
    if snapshot is not None and snapshot_output is not None:
        _write(snapshot_output, snapshot)
    if analysis is not None and analysis_output is not None:
        _write(analysis_output, analysis)

    valid = bool(
        not command_error
        and not analysis_error
        and ack_match is not None
        and ack_match.group(1) == args.condition
        and ack_match.group(2) == args.capture_id
        and not outcome_reasons
        and outcome is not None
        and (
            (args.condition != "armed" and snapshot is None)
            or (
                snapshot is not None
                and analysis is not None
                and analysis.get("status") == "correlated"
            )
        )
    )
    trial = {
        "schema_version": 1,
        "kind": "observatory_enemy_tournament_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": args.capture_id,
        "capture_track": "owner_local_modified",
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "command_ack": ack or None,
        "module_sha256": module_sha256,
        "build_receipt_sha256": stable_file_sha256(args.build_receipt),
        "scenario": (
            {
                "pawn_id": pawn_id,
                "pawn_type": "Firefly1",
                "start": [int(ack_match.group(4)), int(ack_match.group(5))],
                "consumed_spawn_count": int(ack_match.group(6)),
            }
            if ack_match
            else None
        ),
        "native_counts": (
            {
                "candidate_count": int(ack_match.group(7)),
                "selected_count": int(ack_match.group(8)),
                "queue_count": int(ack_match.group(9)),
            }
            if ack_match
            else None
        ),
        "outcome": (
            {
                "path": str(outcome_output),
                "sha256": stable_file_sha256(outcome_output),
            }
            if outcome is not None
            else None
        ),
        "snapshot": (
            {
                "path": str(snapshot_output),
                "sha256": stable_file_sha256(snapshot_output),
                "candidate_count": snapshot.get("summary", {}).get(
                    "candidate_count"
                ),
                "complete": snapshot.get("integrity", {}).get("complete"),
            }
            if snapshot is not None and snapshot_output is not None
            else None
        ),
        "analysis": (
            {
                "path": str(analysis_output),
                "sha256": stable_file_sha256(analysis_output),
                "status": analysis.get("status"),
            }
            if analysis is not None and analysis_output is not None
            else None
        ),
        "errors": {
            "command": command_error,
            "outcome": outcome_reasons,
            "analysis": analysis_error,
        },
    }
    _write(trial_output, trial)
    trial["trial_output"] = {
        "path": str(trial_output),
        "sha256": stable_file_sha256(trial_output),
    }
    return (0 if valid else 2), trial


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    try:
        code, trial = run(args)
        print(json.dumps(trial, indent=2, sort_keys=True))
        return code
    except (
        BridgeError,
        EnemyTournamentHwError,
        OSError,
        TraceStoreError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
