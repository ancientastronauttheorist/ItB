#!/usr/bin/env python3
"""Run one solver-controlled turn with a spawn-coordinate HW boundary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bridge.protocol import (  # noqa: E402
    BridgeError,
    read_state,
    refresh_bridge_state_fresh,
)
from src.loop.commands import cmd_auto_turn  # noqa: E402
from src.observatory.spawn_coordinate_hw import (  # noqa: E402
    SpawnCoordinateHwError,
    correlate_spawn_coordinate_snapshot,
)
from src.observatory.spawn_coordinate_turn import (  # noqa: E402
    SpawnCoordinateTurnBoundary,
    SpawnCoordinateTurnBoundaryError,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
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
    parser.add_argument("--profile", default="Alpha")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-wait", type=float, default=45.0)
    parser.add_argument("--candidate-rank", type=int, default=None)
    parser.add_argument("--allow-dirty-plan", action="store_true")
    parser.add_argument("--dirty-consent-id", default=None)
    parser.add_argument("--allow-protected-objective-loss", action="store_true")
    parser.add_argument("--allow-objective-loss", action="store_true")
    parser.add_argument("--allow-timeline-collapse", action="store_true")
    parser.add_argument("--allow-mech-loss", action="store_true")
    parser.add_argument(
        "--no-frontier-diagnostics",
        dest="frontier_diagnostics",
        action="store_false",
        default=True,
    )
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
    if (
        resolved == repo
        or resolved.is_relative_to(repo)
        or repo.is_relative_to(resolved)
    ):
        raise OSError("ITB_ARTIFACT_ROOT must not overlap the repository")
    return resolved


def _session_file(root: Path) -> Path:
    raw = os.environ.get("ITB_SESSION_FILE")
    if not raw:
        raise OSError("ITB_SESSION_FILE is required")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise OSError("ITB_SESSION_FILE must be absolute")
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise OSError("ITB_SESSION_FILE must be inside ITB_ARTIFACT_ROOT")
    if resolved.exists() or resolved.is_symlink():
        raise OSError(f"ITB_SESSION_FILE must be fresh: {resolved}")
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


def _outcome_reasons(outcome: object) -> list[str]:
    if not isinstance(outcome, dict):
        return ["bridge_outcome_missing"]
    reasons: list[str] = []
    if outcome.get("mission_id") != "Mission_Power":
        reasons.append("bridge_mission_mismatch")
    if outcome.get("phase") != "combat_player":
        reasons.append("bridge_phase_mismatch")
    spawning = outcome.get("spawning_tiles")
    if not isinstance(spawning, list) or not spawning:
        reasons.append("bridge_spawn_activity_missing")
    if outcome.get("environment_danger") not in (None, []):
        reasons.append("bridge_environment_activity")
    if outcome.get("environment_danger_v2") not in (None, []):
        reasons.append("bridge_environment_v2_activity")
    return reasons


def _auto_summary(result: object) -> dict:
    if not isinstance(result, dict):
        return {"status": "invalid_result"}
    return {
        key: result.get(key)
        for key in (
            "status",
            "turn",
            "actions_completed",
            "score",
            "re_solves",
            "desyncs_detected",
            "post_phase",
            "grid_power",
            "observatory_native_rng_boundary",
            "error",
            "blocking",
            "retry_allowed",
        )
        if key in result
    }


def run(args: argparse.Namespace) -> tuple[int, dict]:
    root = _artifact_root()
    session_file = _session_file(root)
    trial_output = _output(args.trial_output, root, "trial output")
    outcome_output = _output(args.outcome_output, root, "outcome output")
    snapshot_output = None
    analysis_output = None
    if args.condition == "armed":
        if args.snapshot_output is None or args.analysis_output is None:
            raise ValueError(
                "armed condition requires snapshot and analysis outputs"
            )
        snapshot_output = _output(
            args.snapshot_output, root, "snapshot output"
        )
        analysis_output = _output(
            args.analysis_output, root, "analysis output"
        )
    elif args.snapshot_output is not None or args.analysis_output is not None:
        raise ValueError("only the armed condition accepts observer outputs")
    receipt = load_json_object(
        args.build_receipt, "spawn-coordinate build receipt"
    )
    module_sha256 = stable_file_sha256(args.module)
    boundary = SpawnCoordinateTurnBoundary(
        condition=args.condition,
        capture_id=args.capture_id,
    )

    result: dict | None = None
    outcome: dict | None = None
    runner_error = ""
    abort_error = ""
    outcome_error = ""
    try:
        result = cmd_auto_turn(
            profile=args.profile,
            time_limit=args.time_limit,
            max_wait=args.max_wait,
            allow_dirty_plan=args.allow_dirty_plan,
            candidate_rank=args.candidate_rank,
            dirty_consent_id=args.dirty_consent_id,
            allow_protected_objective_loss=args.allow_protected_objective_loss,
            allow_objective_loss=args.allow_objective_loss,
            allow_timeline_collapse=args.allow_timeline_collapse,
            allow_mech_loss=args.allow_mech_loss,
            frontier_diagnostics=args.frontier_diagnostics,
            _observatory_native_rng_boundary=boundary,
        )
    except Exception as exc:
        runner_error = str(exc)
    finally:
        try:
            boundary.abort()
        except Exception as exc:
            abort_error = str(exc)

    if not runner_error and not abort_error:
        try:
            if not refresh_bridge_state_fresh(timeout=5.0):
                raise BridgeError("post-trial bridge state did not refresh")
            outcome = read_state()
            if not isinstance(outcome, dict):
                raise BridgeError("post-trial bridge state is unavailable")
            _write(outcome_output, outcome)
        except Exception as exc:
            outcome_error = str(exc)

    outcome_reasons = _outcome_reasons(outcome)
    analysis = None
    analysis_error = ""
    if (
        args.condition == "armed"
        and boundary.snapshot is not None
        and outcome is not None
    ):
        try:
            analysis = correlate_spawn_coordinate_snapshot(
                boundary.snapshot,
                outcome,
                build_receipt=receipt,
                observed_module_sha256=module_sha256,
            )
            assert snapshot_output is not None
            assert analysis_output is not None
            _write(snapshot_output, boundary.snapshot)
            _write(analysis_output, analysis)
        except Exception as exc:
            analysis_error = str(exc)

    auto_summary = _auto_summary(result)
    valid = bool(
        not runner_error
        and not abort_error
        and not outcome_error
        and not outcome_reasons
        and not analysis_error
        and auto_summary.get("status") == "ok"
        and auto_summary.get("post_phase") == "combat_player"
        and auto_summary.get("desyncs_detected") == 0
        and boundary.state == "complete"
        and (
            (args.condition != "armed" and boundary.snapshot is None)
            or (
                boundary.snapshot is not None
                and analysis is not None
                and analysis.get("status") == "correlated"
            )
        )
    )
    trial = {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": args.capture_id,
        "capture_track": "owner_local_modified",
        "artifact_root": str(root),
        "session_file": str(session_file),
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "module_sha256": module_sha256,
        "build_receipt_sha256": stable_file_sha256(args.build_receipt),
        "boundary": boundary.summary(),
        "auto_turn": auto_summary,
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
                "record_count": boundary.snapshot.get("summary", {}).get(
                    "record_count"
                ),
                "complete": boundary.snapshot.get("integrity", {}).get(
                    "complete"
                ),
            }
            if boundary.snapshot is not None and snapshot_output is not None
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
            "runner": runner_error,
            "abort": abort_error,
            "outcome": outcome_error,
            "outcome_validation": outcome_reasons,
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
        OSError,
        SpawnCoordinateHwError,
        SpawnCoordinateTurnBoundaryError,
        TraceStoreError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
