#!/usr/bin/env python3
"""Run one guarded selector-entry Board/RNG capsule trial.

This runner deliberately separates the solver's opaque local End Turn
reservation from its actual click.  The capsule is prepared only after every
player actor is spent and the reservation is durable, remains active through
the guarded local dispatcher and enemy transition, then restores before the
game is paused again.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
from src.loop.commands import (  # noqa: E402
    cmd_auto_turn,
    cmd_dispatch_end_turn,
    cmd_lightning_snap_pause,
)
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
            "bridge_ack",
            "end_turn_plan_id",
            "end_turn_plan_source",
            "end_turn_delivery_mode",
            "local_end_turn_reserved",
            "error",
            "blocking",
            "retry_allowed",
        )
        if key in result
    }


def _reservation_valid(result: object) -> bool:
    return bool(
        isinstance(result, dict)
        and result.get("status") == "PLAN"
        and result.get("local_end_turn_reserved") is True
        and result.get("end_turn_plan_source") == "lightning_loop"
        and result.get("end_turn_delivery_mode") == "local"
        and isinstance(result.get("end_turn_plan_id"), str)
        and result.get("end_turn_plan_id")
    )


def _fresh_state(timeout: float = 5.0) -> dict:
    if not refresh_bridge_state_fresh(timeout=timeout):
        raise BridgeError("capsule trial bridge state did not refresh")
    value = read_state()
    if not isinstance(value, dict):
        raise BridgeError("capsule trial bridge state is unavailable")
    return value


def _wait_for_next_player_turn(
    pre_turn: int,
    *,
    max_wait: float,
    wait_poll_interval: float,
) -> dict:
    deadline = time.monotonic() + max(0.1, float(max_wait))
    wait_poll_interval = max(0.05, float(wait_poll_interval))
    last: dict | None = None
    while time.monotonic() < deadline:
        try:
            state = _fresh_state(timeout=min(5.0, max(0.1, deadline - time.monotonic())))
        except BridgeError:
            time.sleep(wait_poll_interval)
            continue
        last = state
        turn = state.get("turn")
        if (
            state.get("mission_id") == "Mission_Power"
            and state.get("phase") == "combat_player"
            and type(turn) is int
            and turn > pre_turn
        ):
            return state
        if state.get("in_active_mission") is False:
            raise BridgeError("capsule trial mission ended before the next player turn")
        time.sleep(wait_poll_interval)
    raise TimeoutError(
        "capsule trial next player turn timeout; last phase="
        f"{last.get('phase') if isinstance(last, dict) else None}"
    )


def _dispatch_confirmation(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    dispatch = result.get("dispatch")
    if not isinstance(dispatch, dict):
        return None
    return dispatch.get("delivery_confirmation")


def _reserve_with_auto_turn(args: argparse.Namespace) -> dict:
    key = "ITB_LIGHTNING_LOCAL_END_TURN"
    prior = os.environ.get(key)
    os.environ[key] = "1"
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
        )
    finally:
        if prior is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prior


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
    dispatch_result: dict | None = None
    outcome: dict | None = None
    analysis: dict | None = None
    pause_result: dict | None = None
    errors = {
        "reservation": "",
        "pre_dispatch": "",
        "dispatch": "",
        "wait": "",
        "finish": "",
        "analysis": "",
        "snapshot_consume": "",
        "abort": "",
        "pause": "",
    }
    pre_turn: int | None = None
    try:
        auto_result = _reserve_with_auto_turn(args)
        if not _reservation_valid(auto_result):
            errors["reservation"] = "auto_turn did not create an opaque local reservation"
        else:
            pre_state = _fresh_state()
            pre_turn_value = pre_state.get("turn")
            if (
                pre_state.get("mission_id") != "Mission_Power"
                or pre_state.get("phase") != "combat_player"
                or type(pre_turn_value) is not int
            ):
                errors["pre_dispatch"] = "fresh pre-dispatch mission state differs"
            else:
                pre_turn = pre_turn_value
                boundary.before_dispatch()
                try:
                    dispatch_result = cmd_dispatch_end_turn(
                        execute=True,
                        _allow_reserved_local_plan=True,
                    )
                except Exception as exc:
                    errors["dispatch"] = str(exc)
                confirmation = _dispatch_confirmation(dispatch_result)
                if not errors["dispatch"] and (
                    not isinstance(dispatch_result, dict)
                    or dispatch_result.get("status") != "DISPATCHED"
                    or confirmation != "delivered_confirmed"
                ):
                    errors["dispatch"] = "guarded local End Turn was not confirmed"
                if not errors["dispatch"]:
                    try:
                        outcome = _wait_for_next_player_turn(
                            pre_turn,
                            max_wait=args.max_wait,
                            wait_poll_interval=args.wait_poll_interval,
                        )
                    except Exception as exc:
                        errors["wait"] = str(exc)
                accepted = not errors["dispatch"] and not errors["wait"]
                try:
                    boundary.after_dispatch(
                        {
                            "status": "OK" if accepted else "STOPPED",
                            "delivery_confirmation": confirmation,
                        }
                    )
                except Exception as exc:
                    errors["finish"] = str(exc)
    except Exception as exc:
        if boundary.state in {"prepare_pending", "prepared"}:
            try:
                boundary.after_dispatch(
                    {
                        "status": "STOPPED",
                        "delivery_confirmation": _dispatch_confirmation(
                            dispatch_result
                        ),
                    }
                )
            except Exception as finish_exc:
                errors["finish"] = str(finish_exc)
        target = "pre_dispatch" if auto_result is not None else "reservation"
        if not errors[target]:
            errors[target] = str(exc)
    finally:
        try:
            boundary.abort()
        except Exception as exc:
            errors["abort"] = str(exc)
        try:
            pause_result = cmd_lightning_snap_pause(
                f"spawn_capsule_{args.capture_id}",
                note="post_spawn_coordinate_capsule_trial_restore_guard",
                run_seconds=0.0,
                include_ocr=True,
            )
        except Exception as exc:
            errors["pause"] = str(exc)

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
    pause_ok = bool(
        isinstance(pause_result, dict)
        and pause_result.get("status") in {"OK", "PAUSED"}
        and pause_result.get("pause_verified") is True
        and pause_result.get("safe_to_think") is True
    )
    valid = bool(
        not any(errors.values())
        and _reservation_valid(auto_result)
        and isinstance(dispatch_result, dict)
        and dispatch_result.get("status") == "DISPATCHED"
        and _dispatch_confirmation(dispatch_result) == "delivered_confirmed"
        and outcome is not None
        and boundary.state == "complete"
        and pause_ok
        and (
            (args.condition != "armed" and boundary.snapshot is None)
            or (analysis is not None and analysis.get("status") == "correlated")
        )
    )
    trial = {
        "schema_version": 2,
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
        "pre_dispatch_turn": pre_turn,
        "auto_turn": auto_summary,
        "dispatch": dispatch_result,
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
        "pause_guard": pause_result,
        "errors": errors,
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
