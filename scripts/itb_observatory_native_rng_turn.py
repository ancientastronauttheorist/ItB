#!/usr/bin/env python3
"""Run one solver-controlled turn with a build-keyed native RNG boundary."""

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

from src.loop.commands import cmd_auto_turn  # noqa: E402
from src.observatory.native_checkpoint import (  # noqa: E402
    NativeCheckpointError,
    build_rng_core_checkpoint,
    validate_native_checkpoint,
)
from src.observatory.native_rng_turn import (  # noqa: E402
    NativeRngTurnBoundary,
    NativeRngTurnBoundaryError,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--condition", choices=["control", "exact_hook"], required=True)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
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
        help="Skip expensive dirty-frontier previews; safety gates remain active.",
    )
    parser.add_argument("--build-receipt", type=Path)
    parser.add_argument("--module", type=Path)
    parser.add_argument("--rng-return-map", type=Path)
    parser.add_argument("--restore-hashes", type=Path)
    parser.add_argument("--checkpoint-output", type=Path)
    return parser


def _absolute_output(path: Path, label: str) -> Path:
    output = Path(os.path.abspath(path.expanduser()))
    if output.parent == output or output.parent.is_symlink():
        raise OSError(f"{label} parent is unsafe")
    if output.exists() or output.is_symlink():
        raise OSError(f"{label} already exists: {output}")
    return output


def _runtime_artifact_root() -> Path:
    raw = os.environ.get("ITB_ARTIFACT_ROOT")
    if not raw:
        raise OSError(
            "ITB_ARTIFACT_ROOT must be set before process start so the "
            "diagnostic uses an isolated one-shot session ledger"
        )
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise OSError("ITB_ARTIFACT_ROOT must be absolute")
    resolved = root.resolve()
    repo = ROOT.resolve()
    if resolved == repo or resolved.is_relative_to(repo) or repo.is_relative_to(resolved):
        raise OSError("ITB_ARTIFACT_ROOT must not overlap the repository")
    return resolved


def _runtime_session_file(artifact_root: Path) -> Path:
    raw = os.environ.get("ITB_SESSION_FILE")
    if not raw:
        raise OSError(
            "ITB_SESSION_FILE must be set before process start so native "
            "trials cannot reuse a consumed dirty-consent ledger"
        )
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise OSError("ITB_SESSION_FILE must be absolute")
    resolved = path.resolve()
    if not resolved.is_relative_to(artifact_root):
        raise OSError("ITB_SESSION_FILE must be inside ITB_ARTIFACT_ROOT")
    if resolved.exists() or resolved.is_symlink():
        raise OSError(f"ITB_SESSION_FILE must be fresh: {resolved}")
    return resolved


def _write_create_only(path: Path, value: object) -> None:
    output = _absolute_output(path, "output")
    output.parent.mkdir(parents=True, exist_ok=True)
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
    with output.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _exact_inputs(args: argparse.Namespace) -> tuple[dict, dict, dict, str, Path]:
    named = {
        "build receipt": args.build_receipt,
        "observer module": args.module,
        "RNG return map": args.rng_return_map,
        "restore hashes": args.restore_hashes,
        "checkpoint output": args.checkpoint_output,
    }
    missing = [label for label, value in named.items() if value is None]
    if missing:
        raise ValueError(
            "exact_hook requires " + ", ".join(missing)
        )
    checkpoint_output = _absolute_output(
        args.checkpoint_output, "checkpoint output"
    )
    receipt = load_json_object(args.build_receipt, "observer build receipt")
    return_map = load_json_object(args.rng_return_map, "RNG return map")
    restore_hashes = load_json_object(args.restore_hashes, "restore hashes")
    module_sha256 = stable_file_sha256(args.module)
    return receipt, return_map, restore_hashes, module_sha256, checkpoint_output


def _auto_turn_summary(result: object) -> dict:
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
    artifact_root = _runtime_artifact_root()
    session_file = _runtime_session_file(artifact_root)
    trial_output = _absolute_output(args.trial_output, "trial output")
    exact_inputs = _exact_inputs(args) if args.condition == "exact_hook" else None
    boundary = NativeRngTurnBoundary(
        condition=args.condition,
        capture_id=args.capture_id,
    )
    result: dict | None = None
    runner_error = ""
    abort_error = ""
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
    except Exception as exc:  # cmd_auto_turn normally returns structured blocks
        runner_error = str(exc)
    finally:
        try:
            boundary.abort()
        except Exception as exc:
            abort_error = str(exc)

    checkpoint = None
    checkpoint_summary = None
    checkpoint_error = ""
    if args.condition == "exact_hook" and boundary.snapshot is not None:
        assert exact_inputs is not None
        receipt, return_map, restore_hashes, module_sha256, checkpoint_output = (
            exact_inputs
        )
        try:
            checkpoint = build_rng_core_checkpoint(
                boundary.snapshot,
                build_receipt=receipt,
                observed_module_sha256=module_sha256,
            )
            verification = validate_native_checkpoint(
                checkpoint,
                expected_identity=checkpoint["identity"],
                return_map=return_map,
                expected_restore_hashes=restore_hashes,
            )
            if not verification["diagnostic_complete"]:
                raise NativeCheckpointError(
                    "native RNG checkpoint is not diagnostically complete"
                )
            _write_create_only(checkpoint_output, checkpoint)
            checkpoint_summary = {
                "path": str(checkpoint_output),
                "sha256": stable_file_sha256(checkpoint_output),
                "record_count": checkpoint["summary"]["record_count"],
                "hook_bytes_restored": checkpoint["integrity"][
                    "hook_bytes_restored"
                ],
                "diagnostic_complete": True,
            }
        except Exception as exc:
            checkpoint_error = str(exc)

    auto_summary = _auto_turn_summary(result)
    valid = bool(
        not runner_error
        and not abort_error
        and not checkpoint_error
        and auto_summary.get("status") == "ok"
        and auto_summary.get("post_phase") == "combat_player"
        and auto_summary.get("desyncs_detected") == 0
        and boundary.state == "complete"
        and (
            args.condition == "control"
            or (
                checkpoint_summary is not None
                and checkpoint_summary["hook_bytes_restored"] is True
            )
        )
    )
    trial = {
        "schema_version": 1,
        "kind": "observatory_native_rng_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": args.capture_id,
        "artifact_root": str(artifact_root),
        "session_file": str(session_file),
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "boundary": boundary.summary(),
        "auto_turn": auto_summary,
        "checkpoint": checkpoint_summary,
        "errors": {
            "runner": runner_error,
            "abort": abort_error,
            "checkpoint": checkpoint_error,
        },
    }
    _write_create_only(trial_output, trial)
    trial["trial_output"] = {
        "path": str(trial_output),
        "sha256": stable_file_sha256(trial_output),
    }
    return (0 if valid else 2), trial


def main(argv: list[str] | None = None) -> int:
    # The live solver narrates visual tiles with Unicode arrows.  Windows can
    # otherwise inherit a legacy console code page and raise mid-turn while
    # printing a fully valid plan.  Configure the diagnostic process before
    # any session-touching work so console rendering cannot alter trial flow.
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
        NativeCheckpointError,
        NativeRngTurnBoundaryError,
        TraceStoreError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
