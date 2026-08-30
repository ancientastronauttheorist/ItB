#!/usr/bin/env python3
"""Run one fresh-process selector-entry Board/RNG capsule trial.

The capsule is prepared only after every player actor is spent.  The already
validated exact-build game-flow helper then performs one synchronous native
End Turn, after which the observer is restored before the post-turn state is
captured.  The enclosing condition runner gracefully closes the process.
"""

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
    consume_observatory_spawn_coordinate_capsule_snapshot,
    read_state,
    refresh_bridge_state_fresh,
)
from src.loop.commands import cmd_auto_turn  # noqa: E402
from src.observatory.game_process_identity import (  # noqa: E402
    GameProcessIdentityError,
    capture_windows_game_process_identity,
)
from src.observatory.spawn_coordinate_capsule_hw import (  # noqa: E402
    SpawnCoordinateCapsuleHwError,
    correlate_spawn_coordinate_capsule_snapshot,
    validate_spawn_coordinate_capsule_build_identity,
)
from src.observatory.spawn_coordinate_capsule_turn import (  # noqa: E402
    SpawnCoordinateCapsuleTurnBoundary,
    SpawnCoordinateCapsuleTurnError,
)
from src.observatory.start_state_proof import (  # noqa: E402
    StartStateProofError,
    validate_start_state_verification_proof,
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
        "--condition",
        choices=("control", "dormant", "armed"),
        required=True,
    )
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--start-state-proof", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--outcome-output", type=Path, required=True)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--analysis-output", type=Path)
    parser.add_argument("--profile", default="Alpha")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-wait", type=float, default=45.0)
    parser.add_argument("--wait-poll-interval", type=float, default=0.20)
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
    if resolved.is_symlink() or not resolved.is_file():
        raise OSError(
            f"ITB_SESSION_FILE must be an existing isolated session: {resolved}"
        )
    return resolved


def _output(path: Path, root: Path, label: str) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.parent == candidate or not candidate.is_relative_to(root):
        raise OSError(f"{label} must be inside ITB_ARTIFACT_ROOT")
    if candidate.exists() or candidate.is_symlink():
        raise OSError(f"{label} already exists: {candidate}")
    return candidate


def _input(path: Path, root: Path, label: str) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if (
        candidate.is_symlink()
        or not candidate.is_file()
        or not candidate.is_relative_to(root)
    ):
        raise OSError(f"{label} must be a regular file inside ITB_ARTIFACT_ROOT")
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


def _fresh_state(timeout: float = 5.0) -> dict:
    if not refresh_bridge_state_fresh(timeout=timeout):
        raise BridgeError("capsule trial bridge state did not refresh")
    value = read_state()
    if not isinstance(value, dict):
        raise BridgeError("capsule trial bridge state is unavailable")
    return value


def _configure_utf8_stdio(streams: tuple[object, ...] | None = None) -> None:
    """Keep imported Windows trials able to print Unicode board summaries."""
    selected = (sys.stdout, sys.stderr) if streams is None else streams
    for stream in selected:
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _run_with_native_boundary(
    args: argparse.Namespace,
    boundary: SpawnCoordinateCapsuleTurnBoundary,
) -> dict:
    _configure_utf8_stdio()
    # An inherited Lightning environment would turn the direct native result
    # into an opaque local reservation.  Isolate this scientific runner from
    # that unrelated UI-delivery mode and restore the caller's environment.
    key = "ITB_LIGHTNING_LOCAL_END_TURN"
    prior = os.environ.pop(key, None)
    try:
        return cmd_auto_turn(
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
    finally:
        if prior is not None:
            os.environ[key] = prior


def _outcome_valid(outcome: object, pre_turn: object) -> bool:
    return bool(
        isinstance(outcome, dict)
        and outcome.get("mission_id") == "Mission_Power"
        and outcome.get("phase") == "combat_player"
        and outcome.get("in_active_mission") is True
        and type(pre_turn) is int
        and type(outcome.get("turn")) is int
        and outcome.get("turn") > pre_turn
    )


def run(args: argparse.Namespace) -> tuple[int, dict]:
    root = _artifact_root()
    session_file = _session_file(root)
    start_state_proof_path = _input(
        args.start_state_proof,
        root,
        "start-state proof",
    )
    trial_output = _output(args.trial_output, root, "trial output")
    outcome_output = _output(args.outcome_output, root, "outcome output")
    snapshot_output = None
    analysis_output = None
    if args.condition == "armed":
        if args.snapshot_output is None or args.analysis_output is None:
            raise ValueError("armed condition requires snapshot and analysis outputs")
        snapshot_output = _output(
            args.snapshot_output,
            root,
            "snapshot output",
        )
        analysis_output = _output(
            args.analysis_output,
            root,
            "analysis output",
        )
    elif args.snapshot_output is not None or args.analysis_output is not None:
        raise ValueError("only the armed condition accepts observer outputs")

    receipt = load_json_object(args.build_receipt, "capsule build receipt")
    module_sha256 = stable_file_sha256(args.module)
    build_receipt_sha256 = stable_file_sha256(args.build_receipt)
    validate_spawn_coordinate_capsule_build_identity(
        receipt,
        observed_module_sha256=module_sha256,
        observed_build_receipt_sha256=build_receipt_sha256,
    )
    process_identity = capture_windows_game_process_identity(args.executable)
    start_state_proof = validate_start_state_verification_proof(
        load_json_object(start_state_proof_path, "start-state proof"),
        process_identity=process_identity,
    )
    start_state_proof_sha256 = stable_file_sha256(start_state_proof_path)
    boundary = SpawnCoordinateCapsuleTurnBoundary(
        condition=args.condition,
        capture_id=args.capture_id,
    )

    auto_result: dict | None = None
    outcome: dict | None = None
    analysis: dict | None = None
    errors = {
        "runner": "",
        "outcome": "",
        "analysis": "",
        "snapshot_consume": "",
        "abort": "",
    }
    pre_turn: int | None = None
    try:
        auto_result = _run_with_native_boundary(args, boundary)
        if isinstance(auto_result, dict) and type(auto_result.get("turn")) is int:
            pre_turn = auto_result["turn"]
        if (
            not isinstance(auto_result, dict)
            or auto_result.get("status") != "ok"
            or auto_result.get("desyncs_detected") != 0
            or auto_result.get("post_phase") != "combat_player"
            or boundary.state != "complete"
            or auto_result.get("observatory_native_rng_boundary")
            != boundary.summary()
        ):
            errors["runner"] = (
                "auto_turn did not complete one exact native capsule boundary"
            )
        else:
            try:
                outcome = _fresh_state()
                if not _outcome_valid(outcome, pre_turn):
                    raise BridgeError(
                        "post-trial state is not the next Mission_Power player turn"
                    )
            except Exception as exc:
                errors["outcome"] = str(exc)
                outcome = None
    except Exception as exc:
        errors["runner"] = str(exc)
    finally:
        try:
            boundary.abort()
        except Exception as exc:
            errors["abort"] = str(exc)

    if outcome is not None:
        _write(outcome_output, outcome)
    if args.condition == "armed" and boundary.snapshot is not None and outcome is not None:
        try:
            analysis = correlate_spawn_coordinate_capsule_snapshot(
                boundary.snapshot,
                outcome,
                build_receipt=receipt,
                observed_module_sha256=module_sha256,
            )
            if analysis.get("status") != "correlated":
                errors["analysis"] = "capsule snapshot did not correlate"
            else:
                assert snapshot_output is not None
                assert analysis_output is not None
                _write(snapshot_output, boundary.snapshot)
                _write(analysis_output, analysis)
        except Exception as exc:
            if not errors["analysis"]:
                errors["analysis"] = str(exc)
        if not errors["analysis"] and analysis is not None:
            try:
                consume_observatory_spawn_coordinate_capsule_snapshot(
                    boundary.snapshot
                )
            except Exception as exc:
                errors["snapshot_consume"] = str(exc)

    auto_summary = _auto_summary(auto_result)
    valid = bool(
        not any(errors.values())
        and isinstance(auto_result, dict)
        and auto_result.get("status") == "ok"
        and auto_result.get("desyncs_detected") == 0
        and auto_result.get("post_phase") == "combat_player"
        and auto_result.get("observatory_native_rng_boundary")
        == boundary.summary()
        and _outcome_valid(outcome, pre_turn)
        and boundary.state == "complete"
        and (
            (args.condition != "armed" and boundary.snapshot is None)
            or (analysis is not None and analysis.get("status") == "correlated")
        )
    )
    trial = {
        "schema_version": 3,
        "kind": "observatory_spawn_coordinate_capsule_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": args.capture_id,
        "capture_track": "owner_local_modified",
        "artifact_root": str(root),
        "session_file": str(session_file),
        "process_identity": process_identity,
        "start_state": {
            "path": str(start_state_proof_path),
            "sha256": start_state_proof_sha256,
            "verified_at": start_state_proof["verified_at"],
            "manifest_sha256": start_state_proof["manifest_sha256"],
            "tree_sha256": start_state_proof["manifest"]["tree_sha256"],
        },
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "module_sha256": module_sha256,
        "build_receipt_sha256": build_receipt_sha256,
        "pre_end_turn_turn": pre_turn,
        "auto_turn": auto_summary,
        "boundary": boundary.summary(),
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
                "draw_record_count": boundary.snapshot.get("summary", {}).get(
                    "draw_record_count"
                ),
                "capsule_count": boundary.snapshot.get("summary", {}).get(
                    "capsule_count"
                ),
                "complete": boundary.snapshot.get("integrity", {}).get("complete"),
            }
            if boundary.snapshot is not None and snapshot_output is not None
            else None
        ),
        "analysis": (
            {
                "path": str(analysis_output),
                "sha256": stable_file_sha256(analysis_output),
                "kind": analysis.get("kind"),
                "status": analysis.get("status"),
            }
            if analysis is not None and analysis_output is not None
            else None
        ),
        "snapshot_consumed_from_bridge": bool(
            args.condition != "armed"
            or (
                analysis is not None
                and analysis.get("status") == "correlated"
                and not errors["snapshot_consume"]
            )
        ),
        "errors": errors,
    }
    _write(trial_output, trial)
    trial["trial_output"] = {
        "path": str(trial_output),
        "sha256": stable_file_sha256(trial_output),
    }
    return (0 if valid else 2), trial


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    args = _parser().parse_args(argv)
    try:
        code, trial = run(args)
        print(json.dumps(trial, indent=2, sort_keys=True))
        return code
    except (
        BridgeError,
        GameProcessIdentityError,
        OSError,
        SpawnCoordinateCapsuleHwError,
        SpawnCoordinateCapsuleTurnError,
        StartStateProofError,
        TraceStoreError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
