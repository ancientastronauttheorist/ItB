#!/usr/bin/env python3
"""Run one callback family over the fixed Firefly tournament scenario."""

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

from src.bridge.protocol import (  # noqa: E402
    BridgeError,
    read_state,
    refresh_bridge_state_fresh,
)
from src.bridge.writer import bridge_observatory_enemy_callback_trial  # noqa: E402
from src.observatory.callback_trial_result import (  # noqa: E402
    CallbackTrialResultError,
    validate_callback_trial_result,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)


ACK_RE = re.compile(
    r"OK OBS_ENEMY_CALLBACK_TRIAL condition=(control|exact_hook) "
    r"family=(get_target_area|enemy_target_score|get_skill_effect|score_positioning) "
    r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
    r"at=([0-7]),([0-7]) consumed_spawns=(\d+) attempts=(\d+) "
    r"events=(\d+) complete=true\Z"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument(
        "--condition", choices=("control", "exact_hook"), required=True
    )
    parser.add_argument("--pair-plan", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--outcome-output", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--trace-output", type=Path)
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
    repository = ROOT.resolve()
    if (
        resolved == repository
        or resolved.is_relative_to(repository)
        or repository.is_relative_to(resolved)
    ):
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


def _pair_identity(plan: dict, pair_plan: Path) -> dict[str, str]:
    if (
        plan.get("schema_version") != 1
        or plan.get("kind") != "observatory_callback_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("conditions") != ["control", "exact_hook"]
    ):
        raise ValueError("callback pair plan is invalid")
    capture_id = plan.get("capture_id")
    family = plan.get("callback_family")
    nonce = plan.get("activation_nonce")
    artifacts = plan.get("artifacts")
    capsule = artifacts.get("capsule") if isinstance(artifacts, dict) else None
    arm = artifacts.get("arm_packet") if isinstance(artifacts, dict) else None
    if (
        type(capture_id) is not str
        or re.fullmatch(r"[a-z][a-z0-9._-]{0,95}", capture_id) is None
        or family not in {
            "get_target_area",
            "enemy_target_score",
            "get_skill_effect",
            "score_positioning",
        }
        or type(nonce) is not str
        or re.fullmatch(r"[0-9a-f]{32,64}", nonce) is None
        or not isinstance(capsule, dict)
        or not isinstance(arm, dict)
        or re.fullmatch(r"[0-9a-f]{64}", str(capsule.get("sha256") or ""))
        is None
        or re.fullmatch(r"[0-9a-f]{64}", str(arm.get("sha256") or ""))
        is None
    ):
        raise ValueError(f"callback pair identity is invalid: {pair_plan}")
    return {
        "capture_id": capture_id,
        "family": family,
        "activation_nonce": nonce,
        "capsule_sha256": capsule["sha256"],
        "arm_packet_sha256": arm["sha256"],
    }


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
        [
            unit
            for unit in units
            if isinstance(unit, dict) and unit.get("team") == 6
        ]
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
    result_output = _output(args.result_output, root, "result output")
    trace_output = None
    if args.condition == "exact_hook":
        if args.trace_output is None:
            raise ValueError("exact_hook condition requires --trace-output")
        trace_output = _output(args.trace_output, root, "trace output")
    elif args.trace_output is not None:
        raise ValueError("control condition does not accept --trace-output")

    pair_plan = load_json_object(args.pair_plan, "callback pair plan")
    identity = _pair_identity(pair_plan, args.pair_plan)
    ack = ""
    command_error = ""
    validation_error = ""
    result: dict | None = None
    trace: dict | None = None
    outcome: dict | None = None
    try:
        ack, result, trace = bridge_observatory_enemy_callback_trial(
            args.condition,
            identity["family"],
            identity["capture_id"],
            identity["activation_nonce"],
            identity["capsule_sha256"],
            timeout=args.timeout,
        )
        result = validate_callback_trial_result(
            result,
            expected_condition=args.condition,
            expected_capsule_sha256=identity["capsule_sha256"],
            expected_arm_packet_sha256=identity["arm_packet_sha256"],
        )
        if not refresh_bridge_state_fresh(timeout=5.0):
            raise BridgeError("post-trial bridge state did not refresh")
        outcome = read_state()
        if not isinstance(outcome, dict):
            raise BridgeError("post-trial bridge state is unavailable")
    except Exception as exc:
        command_error = str(exc)

    match = ACK_RE.fullmatch(ack)
    pawn_id = int(match.group(4)) if match else -1
    outcome_reasons = _outcome_reasons(outcome, pawn_id)
    if result is not None:
        try:
            if result.get("capture_id") != identity["capture_id"]:
                raise ValueError("validated result capture differs")
            if result.get("callback_family") != identity["family"]:
                raise ValueError("validated result family differs")
            if args.condition == "exact_hook" and trace is None:
                raise ValueError("exact callback trace is missing")
            if args.condition == "control" and trace is not None:
                raise ValueError("control callback trace is present")
        except Exception as exc:
            validation_error = str(exc)

    if outcome is not None:
        _write(outcome_output, outcome)
    if result is not None:
        _write(result_output, result)
    if trace is not None and trace_output is not None:
        _write(trace_output, trace)

    valid = bool(
        not command_error
        and not validation_error
        and match is not None
        and match.group(1) == args.condition
        and match.group(2) == identity["family"]
        and match.group(3) == identity["capture_id"]
        and not outcome_reasons
        and result is not None
        and outcome is not None
        and ((args.condition == "control" and trace is None) or trace is not None)
    )
    trial = {
        "schema_version": 1,
        "kind": "observatory_enemy_callback_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": identity["capture_id"],
        "callback_family": identity["family"],
        "capture_track": "owner_local_modified",
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "command_ack": ack or None,
        "pair_plan_sha256": stable_file_sha256(args.pair_plan),
        "capsule_sha256": identity["capsule_sha256"],
        "arm_packet_sha256": identity["arm_packet_sha256"],
        "scenario": (
            {
                "pawn_id": pawn_id,
                "pawn_type": "Firefly1",
                "start": [int(match.group(5)), int(match.group(6))],
                "consumed_spawn_count": int(match.group(7)),
            }
            if match
            else None
        ),
        "callback_counts": (
            {
                "attempted_calls": int(match.group(8)),
                "event_count": int(match.group(9)),
            }
            if match
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
        "result": (
            {
                "path": str(result_output),
                "sha256": stable_file_sha256(result_output),
            }
            if result is not None
            else None
        ),
        "trace": (
            {
                "path": str(trace_output),
                "sha256": stable_file_sha256(trace_output),
            }
            if trace is not None and trace_output is not None
            else None
        ),
        "errors": {
            "command": command_error,
            "validation": validation_error,
            "outcome": outcome_reasons,
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
        CallbackTrialResultError,
        OSError,
        TraceStoreError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
