#!/usr/bin/env python3
"""Run one restore-to-close selector-entry Board/RNG capsule condition."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import itb_observatory_pair_state as pair_state  # noqa: E402
from scripts import itb_observatory_spawn_coordinate_capsule_trial as trial_runner  # noqa: E402
from src.bridge import protocol as bridge_protocol  # noqa: E402
from src.loop import session as loop_session  # noqa: E402
from src.observatory.game_process_identity import (  # noqa: E402
    GameProcessIdentityError,
    capture_windows_game_process_identity,
    validate_windows_game_executable,
)
from src.observatory.spawn_coordinate_capsule_hw import (  # noqa: E402
    SpawnCoordinateCapsuleHwError,
    validate_spawn_coordinate_capsule_build_identity,
)
from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    load_json_object,
    stable_file_sha256,
)
from src.observatory.windows_game_lifecycle import (  # noqa: E402
    WindowsGameLifecycleError,
    gracefully_close_exact_windows_game,
    launch_exact_windows_game,
    wait_for_exact_windows_game_process,
)


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_spawn_coordinate_capsule_condition_lifecycle"
NATIVE_CONTINUE_ACK = "OK OBS_NATIVE_CONTINUE_REQUEST invoked=true"
_PAIR_ID_RE = re.compile(r"spawn-capsule-pair(?P<suffix>00[1-3])\Z")


class CapsuleConditionError(RuntimeError):
    """Raised when a condition lifecycle cannot preserve its exact contract."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument(
        "--condition",
        choices=("control", "dormant", "armed"),
        required=True,
    )
    parser.add_argument("--save-root", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--source-session", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--profile", default="Alpha")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-wait", type=float, default=45.0)
    parser.add_argument("--process-wait", type=float, default=30.0)
    parser.add_argument("--bridge-wait", type=float, default=60.0)
    parser.add_argument("--close-wait", type=float, default=30.0)
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


def _absolute_regular(path: Path, label: str) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.is_symlink() or not candidate.is_file():
        raise CapsuleConditionError(f"{label} is not a regular file: {candidate}")
    return candidate.resolve()


def _artifact_root(path: Path) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.parent == candidate or not candidate.is_dir() or candidate.is_symlink():
        raise CapsuleConditionError(f"artifact root is unavailable: {candidate}")
    resolved = candidate.resolve()
    repo = ROOT.resolve()
    if (
        resolved == repo
        or resolved.is_relative_to(repo)
        or repo.is_relative_to(resolved)
    ):
        raise CapsuleConditionError("artifact root must not overlap the repository")
    return resolved


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_create_only_json(path: Path, value: object) -> None:
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


def _ack_fingerprint() -> tuple[int, int, int, str] | None:
    path = bridge_protocol.ACK_FILE
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise CapsuleConditionError("bridge ACK path is not a regular file")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    before_identity = (
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_size,
    )
    after_identity = (
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_size,
    )
    if before_identity != after_identity or len(data) != before.st_size:
        raise CapsuleConditionError("bridge ACK changed while read")
    return (*before_identity, hashlib.sha256(data).hexdigest())


def _wait_for_native_continue_ack(
    previous: tuple[int, int, int, str] | None,
    *,
    max_wait: float,
    poll_interval: float,
) -> str:
    deadline = time.monotonic() + max(0.1, float(max_wait))
    interval = max(0.02, float(poll_interval))
    while time.monotonic() < deadline:
        observed = _ack_fingerprint()
        if observed is None or observed == previous:
            time.sleep(interval)
            continue
        path = bridge_protocol.ACK_FILE
        content = path.read_text(encoding="utf-8", errors="strict").strip()
        if _ack_fingerprint() != observed:
            time.sleep(interval)
            continue
        path.unlink()
        if content != NATIVE_CONTINUE_ACK:
            raise CapsuleConditionError(
                f"native Continue startup ACK differs: {content!r}"
            )
        return content
    raise CapsuleConditionError("native Continue startup ACK did not arrive")


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = _artifact_root(args.artifact_root)
    match = _PAIR_ID_RE.fullmatch(str(args.pair_id))
    if match is None:
        raise CapsuleConditionError("pair id must be spawn-capsule-pair001..003")
    pair_name = f"pair{match.group('suffix')}"
    condition_root = root / pair_name / args.condition
    if condition_root.exists() or condition_root.is_symlink():
        raise CapsuleConditionError(
            f"condition artifact directory already exists: {condition_root}"
        )
    source_session = _absolute_regular(args.source_session, "source session")
    module = _absolute_regular(args.module, "capsule module")
    build_receipt = _absolute_regular(args.build_receipt, "capsule build receipt")
    executable_identity = validate_windows_game_executable(args.executable)
    build = load_json_object(build_receipt, "capsule build receipt")
    module_sha256 = stable_file_sha256(module)
    build_receipt_sha256 = stable_file_sha256(build_receipt)
    validate_spawn_coordinate_capsule_build_identity(
        build,
        observed_module_sha256=module_sha256,
        observed_build_receipt_sha256=build_receipt_sha256,
    )
    if bridge_protocol.NATIVE_CONTINUE_REQUEST_FILE.exists():
        raise CapsuleConditionError("native Continue startup request is already armed")
    return {
        "artifact_root": root,
        "pair_name": pair_name,
        "condition_root": condition_root,
        "source_session": source_session,
        "source_session_sha256": stable_file_sha256(source_session),
        "module": module,
        "module_sha256": module_sha256,
        "build_receipt": build_receipt,
        "build_receipt_sha256": build_receipt_sha256,
        "executable": Path(executable_identity["path"]),
        "executable_identity": executable_identity,
    }


def _wait_for_bridge_start(
    process_identity: dict[str, Any],
    *,
    max_wait: float,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.1, float(max_wait))
    interval = max(0.05, float(poll_interval))
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        current_identity = capture_windows_game_process_identity(
            Path(str(process_identity["executable_path"]))
        )
        if (
            current_identity.get("pid"),
            current_identity.get("creation_filetime"),
        ) != (
            process_identity.get("pid"),
            process_identity.get("creation_filetime"),
        ):
            raise CapsuleConditionError(
                "Breach.exe process identity changed before bridge readiness"
            )
        try:
            refreshed = bridge_protocol.refresh_bridge_state_fresh(
                timeout=min(5.0, max(0.1, deadline - time.monotonic()))
            )
        except (bridge_protocol.BridgeError, TimeoutError):
            refreshed = False
        if not refreshed:
            time.sleep(interval)
            continue
        state = bridge_protocol.read_state()
        if not isinstance(state, dict):
            time.sleep(interval)
            continue
        last = state
        if (
            state.get("mission_id") == "Mission_Power"
            and state.get("phase") == "combat_player"
            and type(state.get("turn")) is int
            and type(state.get("active_mechs")) is int
            and state.get("active_mechs") > 0
        ):
            if bridge_protocol.NATIVE_CONTINUE_REQUEST_FILE.exists():
                raise CapsuleConditionError(
                    "native Continue request remains after Mission_Power loaded"
                )
            return state
        if state.get("in_active_mission") is False and state.get("phase") not in {
            "main_menu",
            "loading",
        }:
            raise CapsuleConditionError(
                f"native Continue reached unexpected phase {state.get('phase')!r}"
            )
        time.sleep(interval)
    raise CapsuleConditionError(
        "native Continue did not reach a ready Mission_Power player turn; "
        f"last phase={last.get('phase') if isinstance(last, dict) else None!r}"
    )


def _bridge_summary(state: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "mission_id",
        "phase",
        "turn",
        "active_mechs",
        "master_seed",
        "region_id",
        "timeline_fingerprint",
        "ai_seed_fingerprint",
    )
    return {field: state.get(field) for field in fields}


def _trial_args(
    args: argparse.Namespace,
    preflight: dict[str, Any],
    *,
    start_state_proof: Path,
) -> argparse.Namespace:
    condition_root = preflight["condition_root"]
    armed = args.condition == "armed"
    return argparse.Namespace(
        pair_id=args.pair_id,
        condition=args.condition,
        capture_id=f"{args.pair_id}-{args.condition}",
        build_receipt=preflight["build_receipt"],
        module=preflight["module"],
        executable=preflight["executable"],
        start_state_proof=start_state_proof,
        trial_output=condition_root / "trial.json",
        outcome_output=condition_root / "outcome.json",
        snapshot_output=(condition_root / "snapshot.json" if armed else None),
        analysis_output=(condition_root / "analysis.json" if armed else None),
        profile=args.profile,
        time_limit=args.time_limit,
        max_wait=args.max_wait,
        wait_poll_interval=args.wait_poll_interval,
        candidate_rank=args.candidate_rank,
        allow_dirty_plan=args.allow_dirty_plan,
        dirty_consent_id=args.dirty_consent_id,
        allow_protected_objective_loss=args.allow_protected_objective_loss,
        allow_objective_loss=args.allow_objective_loss,
        allow_timeline_collapse=args.allow_timeline_collapse,
        allow_mech_loss=args.allow_mech_loss,
        frontier_diagnostics=args.frontier_diagnostics,
    )


def _remove_owned_continue_request() -> bool:
    path = bridge_protocol.NATIVE_CONTINUE_REQUEST_FILE
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_file():
        raise CapsuleConditionError(
            "refusing to remove a non-regular native Continue request"
        )
    if path.read_bytes() != bridge_protocol.NATIVE_CONTINUE_REQUEST_BYTES:
        raise CapsuleConditionError(
            "refusing to remove an unrecognized native Continue request"
        )
    path.unlink()
    return True


def _release_owned_session_lock(session_path: Path, condition_root: Path) -> None:
    loop_session._release_lock()  # noqa: SLF001
    lock_path = Path(f"{session_path}.lock")
    if not lock_path.exists() and not lock_path.is_symlink():
        return
    if (
        lock_path.is_symlink()
        or not lock_path.is_file()
        or lock_path.parent.resolve() != condition_root.resolve()
    ):
        raise CapsuleConditionError("refusing to remove an unsafe session lock")
    lock_path.unlink()


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    preflight = _preflight(args)
    condition_root: Path = preflight["condition_root"]
    condition_root.parent.mkdir(parents=True, exist_ok=True)
    condition_root.mkdir()
    lifecycle_output = condition_root / "lifecycle.json"
    start_state_path = condition_root / "start_state_proof.json"
    session_path = condition_root / "session.json"
    trial_path = condition_root / "trial.json"
    errors = {
        "restore": "",
        "start_state": "",
        "session": "",
        "session_cleanup": "",
        "continue_arm": "",
        "launch": "",
        "process": "",
        "bridge_start": "",
        "trial": "",
        "close": "",
        "continue_cleanup": "",
    }
    restored_manifest: dict[str, Any] | None = None
    start_state: dict[str, Any] | None = None
    launch: dict[str, Any] | None = None
    process_identity: dict[str, Any] | None = None
    bridge_start: dict[str, Any] | None = None
    trial_result: dict[str, Any] | None = None
    trial_code: int | None = None
    close: dict[str, Any] | None = None
    continue_armed = False
    continue_request_consumed = False
    continue_request_cleaned = False
    continue_ack_before: tuple[int, int, int, str] | None = None
    continue_ack: str | None = None

    try:
        try:
            result = pair_state.restore_state(
                argparse.Namespace(
                    save_root=args.save_root,
                    snapshot_root=args.snapshot_root,
                    allow_restore=True,
                )
            )
            if result != 0:
                raise CapsuleConditionError("start-state restore returned nonzero")
            restored_manifest = pair_state._load_manifest(  # noqa: SLF001
                Path(os.path.abspath(args.snapshot_root)).resolve()
            )
        except Exception as exc:
            errors["restore"] = str(exc)
            raise

        try:
            start_state = pair_state.build_start_state_verification_proof(
                args.save_root,
                args.snapshot_root,
            )
            _write_create_only_json(start_state_path, start_state)
        except Exception as exc:
            errors["start_state"] = str(exc)
            raise

        try:
            result = pair_state.sandbox_session(
                argparse.Namespace(
                    source_session=preflight["source_session"],
                    output_session=session_path,
                    experiment_id=f"{preflight['pair_name']}_{args.condition}",
                )
            )
            if result != 0:
                raise CapsuleConditionError("session sandbox returned nonzero")
        except Exception as exc:
            errors["session"] = str(exc)
            raise

        try:
            continue_ack_before = _ack_fingerprint()
            bridge_protocol.arm_observatory_native_continue_startup()
            continue_armed = True
        except Exception as exc:
            errors["continue_arm"] = str(exc)
            raise

        try:
            launch = launch_exact_windows_game(preflight["executable"])
        except Exception as exc:
            errors["launch"] = str(exc)
            raise

        try:
            process_identity = wait_for_exact_windows_game_process(
                preflight["executable"],
                expected_pid=int(launch["launcher_pid"]),
                timeout=args.process_wait,
                poll_interval=args.wait_poll_interval,
            )
        except Exception as exc:
            errors["process"] = str(exc)
            raise

        try:
            continue_ack = _wait_for_native_continue_ack(
                continue_ack_before,
                max_wait=args.bridge_wait,
                poll_interval=args.wait_poll_interval,
            )
        except Exception as exc:
            errors["bridge_start"] = str(exc)
            raise

        try:
            state = _wait_for_bridge_start(
                process_identity,
                max_wait=args.bridge_wait,
                poll_interval=args.wait_poll_interval,
            )
            bridge_start = _bridge_summary(state)
            continue_request_consumed = True
        except Exception as exc:
            errors["bridge_start"] = str(exc)
            raise

        prior_artifact_root = os.environ.get("ITB_ARTIFACT_ROOT")
        prior_session_file = os.environ.get("ITB_SESSION_FILE")
        os.environ["ITB_ARTIFACT_ROOT"] = str(preflight["artifact_root"])
        os.environ["ITB_SESSION_FILE"] = str(session_path)
        try:
            trial_code, trial_result = trial_runner.run(
                _trial_args(
                    args,
                    preflight,
                    start_state_proof=start_state_path,
                )
            )
            if trial_code != 0 or trial_result.get("valid_trial") is not True:
                raise CapsuleConditionError("capsule trial was rejected")
        except Exception as exc:
            errors["trial"] = str(exc)
        finally:
            try:
                _release_owned_session_lock(session_path, condition_root)
            except Exception as exc:
                errors["session_cleanup"] = str(exc)
            if prior_artifact_root is None:
                os.environ.pop("ITB_ARTIFACT_ROOT", None)
            else:
                os.environ["ITB_ARTIFACT_ROOT"] = prior_artifact_root
            if prior_session_file is None:
                os.environ.pop("ITB_SESSION_FILE", None)
            else:
                os.environ["ITB_SESSION_FILE"] = prior_session_file
    except Exception:
        pass
    finally:
        if process_identity is None and launch is not None:
            try:
                recovered_identity = capture_windows_game_process_identity(
                    preflight["executable"]
                )
                if recovered_identity.get("pid") != launch.get("launcher_pid"):
                    raise CapsuleConditionError(
                        "running Breach.exe PID differs from the launched PID"
                    )
                process_identity = recovered_identity
            except Exception as exc:
                errors["close"] = (
                    "could not recover the launched Breach.exe identity for close: "
                    f"{exc}"
                )
        if process_identity is not None:
            try:
                close = gracefully_close_exact_windows_game(
                    preflight["executable"],
                    process_identity,
                    timeout=args.close_wait,
                    poll_interval=args.wait_poll_interval,
                )
            except Exception as exc:
                errors["close"] = str(exc)
        if continue_armed and bridge_protocol.NATIVE_CONTINUE_REQUEST_FILE.exists():
            try:
                continue_request_cleaned = _remove_owned_continue_request()
            except Exception as exc:
                errors["continue_cleanup"] = str(exc)

    valid = bool(
        not any(errors.values())
        and restored_manifest is not None
        and start_state is not None
        and session_path.is_file()
        and launch is not None
        and process_identity is not None
        and bridge_start is not None
        and continue_request_consumed
        and trial_code == 0
        and trial_result is not None
        and trial_result.get("valid_trial") is True
        and close is not None
        and close.get("exited") is True
        and close.get("forced_termination") is False
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pair_id": args.pair_id,
        "condition": args.condition,
        "capture_id": f"{args.pair_id}-{args.condition}",
        "capture_track": "owner_local_modified",
        "status": "complete" if valid else "rejected",
        "valid_lifecycle": valid,
        "artifact_root": str(preflight["artifact_root"]),
        "condition_root": str(condition_root),
        "build_identity": {
            "executable_sha256": preflight["executable_identity"]["sha256"],
            "executable_size": preflight["executable_identity"]["size"],
            "module_sha256": preflight["module_sha256"],
            "build_receipt_sha256": preflight["build_receipt_sha256"],
        },
        "restore": (
            {
                "manifest_sha256": start_state["manifest_sha256"],
                "tree_sha256": restored_manifest["tree_sha256"],
                "file_count": restored_manifest["file_count"],
                "total_bytes": restored_manifest["total_bytes"],
            }
            if restored_manifest is not None and start_state is not None
            else None
        ),
        "start_state": (
            {
                "path": str(start_state_path),
                "sha256": stable_file_sha256(start_state_path),
                "verified_at": start_state["verified_at"],
                "manifest_sha256": start_state["manifest_sha256"],
                "tree_sha256": start_state["manifest"]["tree_sha256"],
                "game_stopped": start_state["game_stopped"],
            }
            if start_state_path.is_file() and start_state is not None
            else None
        ),
        "session": (
            {
                "path": str(session_path),
                "sha256": stable_file_sha256(session_path),
                "source_path": str(preflight["source_session"]),
                "source_sha256": preflight["source_session_sha256"],
            }
            if session_path.is_file()
            else None
        ),
        "native_continue": {
            "request_path": str(bridge_protocol.NATIVE_CONTINUE_REQUEST_FILE),
            "armed": continue_armed,
            "consumed": continue_request_consumed,
            "ack": continue_ack,
            "cleaned_after_failure": continue_request_cleaned,
        },
        "launch": launch,
        "process_identity": process_identity,
        "bridge_start": bridge_start,
        "bridge_start_sha256": (
            _canonical_sha256(bridge_start) if bridge_start is not None else None
        ),
        "trial": (
            {
                "path": str(trial_path),
                "sha256": stable_file_sha256(trial_path),
                "status": trial_result.get("status"),
                "valid_trial": trial_result.get("valid_trial"),
            }
            if trial_path.is_file() and trial_result is not None
            else None
        ),
        "close": close,
        "errors": errors,
    }
    _write_create_only_json(lifecycle_output, receipt)
    receipt["lifecycle_output"] = {
        "path": str(lifecycle_output),
        "sha256": stable_file_sha256(lifecycle_output),
    }
    return (0 if valid else 2), receipt


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        code, receipt = run(args)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return code
    except (
        bridge_protocol.BridgeError,
        CapsuleConditionError,
        GameProcessIdentityError,
        OSError,
        pair_state.PairStateError,
        SpawnCoordinateCapsuleHwError,
        TraceStoreError,
        ValueError,
        WindowsGameLifecycleError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
