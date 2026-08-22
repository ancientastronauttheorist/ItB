#!/usr/bin/env python3
"""Run one same-process RNG-core plus spawn-coordinate capture."""

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
from src.observatory.native_checkpoint import (  # noqa: E402
    NativeCheckpointError,
    build_rng_core_checkpoint,
    validate_native_checkpoint,
)
from src.observatory.spawn_coordinate_hw import (  # noqa: E402
    SpawnCoordinateHwError,
    correlate_spawn_coordinate_snapshot,
)
from src.observatory.spawn_coordinate_rng import (  # noqa: E402
    SpawnCoordinateRngError,
    attribute_spawn_coordinate_rng,
)
from src.observatory.spawn_coordinate_rng_turn import (  # noqa: E402
    SpawnCoordinateRngTurnBoundary,
    SpawnCoordinateRngTurnBoundaryError,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--rng-build-receipt", type=Path, required=True)
    parser.add_argument("--rng-module", type=Path, required=True)
    parser.add_argument("--rng-return-map", type=Path, required=True)
    parser.add_argument("--rng-restore-hashes", type=Path, required=True)
    parser.add_argument("--coordinate-build-receipt", type=Path, required=True)
    parser.add_argument("--coordinate-module", type=Path, required=True)
    parser.add_argument("--trial-output", type=Path, required=True)
    parser.add_argument("--outcome-output", type=Path, required=True)
    parser.add_argument("--rng-checkpoint-output", type=Path, required=True)
    parser.add_argument("--coordinate-snapshot-output", type=Path, required=True)
    parser.add_argument("--coordinate-analysis-output", type=Path, required=True)
    parser.add_argument("--attribution-output", type=Path, required=True)
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
    if resolved == repo or resolved.is_relative_to(repo) or repo.is_relative_to(resolved):
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


def _artifact(path: Path, **fields: object) -> dict:
    return {
        "path": str(path),
        "sha256": stable_file_sha256(path),
        **fields,
    }


def run(args: argparse.Namespace) -> tuple[int, dict]:
    root = _artifact_root()
    session_file = _session_file(root)
    outputs = {
        "trial": _output(args.trial_output, root, "trial output"),
        "outcome": _output(args.outcome_output, root, "outcome output"),
        "rng_checkpoint": _output(
            args.rng_checkpoint_output, root, "RNG checkpoint output"
        ),
        "coordinate_snapshot": _output(
            args.coordinate_snapshot_output, root, "coordinate snapshot output"
        ),
        "coordinate_analysis": _output(
            args.coordinate_analysis_output, root, "coordinate analysis output"
        ),
        "attribution": _output(
            args.attribution_output, root, "attribution output"
        ),
    }
    rng_receipt = load_json_object(args.rng_build_receipt, "RNG build receipt")
    coordinate_receipt = load_json_object(
        args.coordinate_build_receipt, "coordinate build receipt"
    )
    return_map = load_json_object(args.rng_return_map, "RNG return map")
    restore_hashes = load_json_object(
        args.rng_restore_hashes, "RNG restore hashes"
    )
    rng_module_sha256 = stable_file_sha256(args.rng_module)
    coordinate_module_sha256 = stable_file_sha256(args.coordinate_module)
    boundary = SpawnCoordinateRngTurnBoundary(capture_id=args.capture_id)

    result: dict | None = None
    outcome: dict | None = None
    checkpoint: dict | None = None
    coordinate_analysis: dict | None = None
    attribution: dict | None = None
    errors = {"runner": "", "abort": "", "outcome": "", "analysis": ""}
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
        errors["runner"] = str(exc)
    finally:
        try:
            boundary.abort()
        except Exception as exc:
            errors["abort"] = str(exc)

    if not errors["runner"] and not errors["abort"]:
        try:
            if not refresh_bridge_state_fresh(timeout=5.0):
                raise BridgeError("post-trial bridge state did not refresh")
            outcome = read_state()
            if not isinstance(outcome, dict):
                raise BridgeError("post-trial bridge state is unavailable")
            _write(outputs["outcome"], outcome)
        except Exception as exc:
            errors["outcome"] = str(exc)

    if (
        not errors["runner"]
        and not errors["abort"]
        and not errors["outcome"]
        and boundary.rng_snapshot is not None
        and boundary.coordinate_snapshot is not None
        and outcome is not None
    ):
        try:
            checkpoint = build_rng_core_checkpoint(
                boundary.rng_snapshot,
                build_receipt=rng_receipt,
                observed_module_sha256=rng_module_sha256,
            )
            verification = validate_native_checkpoint(
                checkpoint,
                expected_identity=checkpoint["identity"],
                return_map=return_map,
                expected_restore_hashes=restore_hashes,
            )
            if not verification["diagnostic_complete"]:
                raise NativeCheckpointError(
                    "combined RNG checkpoint is not diagnostically complete"
                )
            coordinate_analysis = correlate_spawn_coordinate_snapshot(
                boundary.coordinate_snapshot,
                outcome,
                build_receipt=coordinate_receipt,
                observed_module_sha256=coordinate_module_sha256,
            )
            if coordinate_analysis["status"] != "correlated":
                raise SpawnCoordinateRngError(
                    "coordinate snapshot does not match bridge spawn markers"
                )
            attribution = attribute_spawn_coordinate_rng(
                checkpoint,
                boundary.coordinate_snapshot,
                coordinate_build_receipt=coordinate_receipt,
                coordinate_module_sha256=coordinate_module_sha256,
                return_map=return_map,
                expected_restore_hashes=restore_hashes,
            )
            _write(outputs["rng_checkpoint"], checkpoint)
            _write(outputs["coordinate_snapshot"], boundary.coordinate_snapshot)
            _write(outputs["coordinate_analysis"], coordinate_analysis)
            _write(outputs["attribution"], attribution)
        except Exception as exc:
            errors["analysis"] = str(exc)

    auto = _auto_summary(result)
    valid = bool(
        not any(errors.values())
        and auto.get("status") == "ok"
        and auto.get("post_phase") == "combat_player"
        and auto.get("desyncs_detected") == 0
        and boundary.state == "complete"
        and checkpoint is not None
        and coordinate_analysis is not None
        and attribution is not None
        and attribution.get("status") == "attributed"
    )
    trial = {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_rng_turn_trial",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": "combined_exact_hook_and_coordinate_hw",
        "capture_id": args.capture_id,
        "capture_track": "owner_local_modified",
        "artifact_root": str(root),
        "session_file": str(session_file),
        "status": "complete" if valid else "rejected",
        "valid_trial": valid,
        "modules": {
            "rng_core_sha256": rng_module_sha256,
            "coordinate_sha256": coordinate_module_sha256,
        },
        "build_receipts": {
            "rng_core_sha256": stable_file_sha256(args.rng_build_receipt),
            "coordinate_sha256": stable_file_sha256(
                args.coordinate_build_receipt
            ),
        },
        "boundary": boundary.summary(),
        "auto_turn": auto,
        "artifacts": {
            "outcome": (
                _artifact(outputs["outcome"]) if outcome is not None else None
            ),
            "rng_checkpoint": (
                _artifact(
                    outputs["rng_checkpoint"],
                    record_count=checkpoint["summary"]["record_count"],
                )
                if checkpoint is not None and not errors["analysis"]
                else None
            ),
            "coordinate_snapshot": (
                _artifact(
                    outputs["coordinate_snapshot"],
                    record_count=boundary.coordinate_snapshot["summary"][
                        "record_count"
                    ],
                )
                if boundary.coordinate_snapshot is not None
                and not errors["analysis"]
                else None
            ),
            "coordinate_analysis": (
                _artifact(
                    outputs["coordinate_analysis"],
                    status=coordinate_analysis["status"],
                )
                if coordinate_analysis is not None and not errors["analysis"]
                else None
            ),
            "attribution": (
                _artifact(
                    outputs["attribution"],
                    status=attribution["status"],
                    selector_rng_ordinals=attribution["summary"][
                        "selector_rng_ordinals"
                    ],
                )
                if attribution is not None and not errors["analysis"]
                else None
            ),
        },
        "errors": errors,
    }
    _write(outputs["trial"], trial)
    trial["trial_output"] = _artifact(outputs["trial"])
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
        NativeCheckpointError,
        OSError,
        SpawnCoordinateHwError,
        SpawnCoordinateRngError,
        SpawnCoordinateRngTurnBoundaryError,
        TraceStoreError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
