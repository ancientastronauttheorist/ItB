"""Seal a counterbalanced selector-entry Board/RNG capsule campaign."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.capsule_runtime_modules import EXPECTED_RUNTIME_MODULES
from src.observatory.game_process_identity import (
    EXPECTED_EXECUTABLE_SHA256 as EXPECTED_PROCESS_EXECUTABLE_SHA256,
    EXPECTED_EXECUTABLE_SIZE as EXPECTED_PROCESS_EXECUTABLE_SIZE,
    IDENTITY_KIND as PROCESS_IDENTITY_KIND,
    SCHEMA_VERSION as PROCESS_IDENTITY_SCHEMA_VERSION,
)
from src.observatory.spawn_coordinate_capsule_hw import (
    CORRELATION_KIND,
    EXPECTED_BUILD_RECEIPT_SHA256,
    EXPECTED_MODULE_SHA256,
    EXPECTED_PLAN_SHA256,
    correlate_spawn_coordinate_capsule_snapshot,
    validate_spawn_coordinate_capsule_build_identity,
    validate_spawn_coordinate_capsule_snapshot,
)
from src.observatory.start_state_proof import (
    StartStateProofError,
    validate_start_state_verification_proof,
)


SCHEMA_VERSION = 2
RECEIPT_KIND = "observatory_spawn_coordinate_capsule_hw_campaign_receipt"
TRIAL_KIND = "observatory_spawn_coordinate_capsule_turn_trial"
LIFECYCLE_KIND = "observatory_spawn_coordinate_capsule_condition_lifecycle"
CAMPAIGN_LIFECYCLE_KIND = (
    "observatory_spawn_coordinate_capsule_campaign_lifecycle"
)
BUILD_RECEIPT = Path("data/observatory/native") / (
    "itb_observatory_spawn_coordinate_capsule_hw_observer_"
    f"{EXPECTED_MODULE_SHA256}.dll.receipt.json"
)
BREAKPOINT_PLAN = Path("data/observatory/native") / (
    "windows_build_13725832_spawn_coordinate_capsule_hw_plan_"
    f"{EXPECTED_PLAN_SHA256}.json"
)
PAIR_SPECS = {
    "pair001": ["control", "dormant", "armed"],
    "pair002": ["armed", "control", "dormant"],
    "pair003": ["dormant", "armed", "control"],
}
EXPECTED_CLAIMS = {
    "selector_entry_board_carriers_captured": True,
    "shared_rng_state_exact": True,
    "candidate_vector_pairing_exact": True,
    "transient_dead_noncorpse_occupancy_resolved": False,
    "pawn_path_profile_at_entry_resolved": False,
    "complete_future_forecast": False,
}
ERROR_FIELDS = {
    "reservation",
    "pre_dispatch",
    "dispatch",
    "wait",
    "finish",
    "analysis",
    "snapshot_consume",
    "abort",
    "pause",
}
LIFECYCLE_ERROR_FIELDS = {
    "restore",
    "start_state",
    "session",
    "session_cleanup",
    "continue_arm",
    "launch",
    "process",
    "bridge_start",
    "trial",
    "close",
    "continue_cleanup",
}
_WINDOWS_EPOCH_FILETIME = 116_444_736_000_000_000


class SpawnCoordinateCapsuleCampaignError(RuntimeError):
    """Raised when capsule campaign evidence is incomplete or inconsistent."""


def _stable_bytes(path: Path, label: str) -> bytes:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} is not a regular file: {candidate}"
        )
    before = candidate.stat()
    data = candidate.read_bytes()
    after = candidate.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} changed while read")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _object_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def _load(path: Path, label: str) -> dict[str, Any]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpawnCoordinateCapsuleCampaignError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} must be an object")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SpawnCoordinateCapsuleCampaignError(f"{label} fields differ")


def _exact_children(root: Path, expected: set[str], *, directories: bool) -> None:
    if root.is_symlink() or not root.is_dir():
        raise SpawnCoordinateCapsuleCampaignError(f"campaign path is invalid: {root}")
    children = {
        item.name
        for item in root.iterdir()
        if item.is_dir() == directories and not item.is_symlink()
    }
    opposite = {
        item.name
        for item in root.iterdir()
        if item.is_dir() != directories or item.is_symlink()
    }
    if children != expected or opposite:
        raise SpawnCoordinateCapsuleCampaignError(
            f"campaign children differ at {root}"
        )


def _exact_campaign_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise SpawnCoordinateCapsuleCampaignError(f"campaign path is invalid: {root}")
    directories = {
        item.name for item in root.iterdir() if item.is_dir() and not item.is_symlink()
    }
    files = {
        item.name for item in root.iterdir() if item.is_file() and not item.is_symlink()
    }
    symlinks_or_other = {
        item.name
        for item in root.iterdir()
        if item.is_symlink() or (not item.is_dir() and not item.is_file())
    }
    if (
        directories != set(PAIR_SPECS)
        or files != {"campaign_lifecycle.json"}
        or symlinks_or_other
    ):
        raise SpawnCoordinateCapsuleCampaignError("campaign root children differ")


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    repo = repository_root.resolve()
    try:
        relative = resolved.relative_to(repo).as_posix()
    except ValueError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"campaign artifact is outside the repository: {resolved}"
        ) from exc
    data = _stable_bytes(resolved, relative)
    return {"path": relative, "sha256": _sha256(data), "size": len(data)}


def _timestamp(value: object, label: str) -> datetime:
    if type(value) is not str:
        raise SpawnCoordinateCapsuleCampaignError(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} timestamp has no timezone"
        )
    return parsed


def _created_at(trial: Mapping[str, Any], label: str) -> datetime:
    return _timestamp(trial.get("created_at"), f"{label} created_at")


def _validate_process_identity(
    value: object,
    *,
    trial_created_at: datetime,
    label: str,
) -> Mapping[str, Any]:
    identity = _mapping(value, f"{label} process identity")
    _exact_keys(
        identity,
        {
            "schema_version",
            "kind",
            "pid",
            "creation_filetime",
            "created_at",
            "executable_path",
            "executable_size",
            "executable_sha256",
        },
        f"{label} process identity",
    )
    pid = identity.get("pid")
    creation_filetime = identity.get("creation_filetime")
    executable_path = Path(str(identity.get("executable_path")))
    process_created_at = _timestamp(
        identity.get("created_at"), f"{label} process created_at"
    )
    expected_created_at = datetime.fromtimestamp(
        (int(creation_filetime) - _WINDOWS_EPOCH_FILETIME) / 10_000_000.0,
        tz=timezone.utc,
    ) if type(creation_filetime) is int else None
    if (
        identity.get("schema_version") != PROCESS_IDENTITY_SCHEMA_VERSION
        or identity.get("kind") != PROCESS_IDENTITY_KIND
        or type(pid) is not int
        or pid <= 0
        or type(creation_filetime) is not int
        or creation_filetime <= _WINDOWS_EPOCH_FILETIME
        or process_created_at != expected_created_at
        or process_created_at > trial_created_at
        or not executable_path.is_absolute()
        or executable_path.name.casefold() != "breach.exe"
        or identity.get("executable_size") != EXPECTED_PROCESS_EXECUTABLE_SIZE
        or identity.get("executable_sha256")
        != EXPECTED_PROCESS_EXECUTABLE_SHA256
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} process identity differs"
        )
    return identity


def _metadata_digest(
    metadata: object,
    artifact_path: Path,
    label: str,
) -> Mapping[str, Any]:
    value = _mapping(metadata, f"{label} metadata")
    if value.get("sha256") != _sha256(_stable_bytes(artifact_path, label)):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} digest differs")
    return value


def _lower_sha256(value: object) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and value.lower() == value
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_build_identity(
    build_path: Path,
    plan_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    build_bytes = _stable_bytes(build_path, "capsule build receipt")
    plan_bytes = _stable_bytes(plan_path, "capsule breakpoint plan")
    build = _load(build_path, "capsule build receipt")
    plan = _load(plan_path, "capsule breakpoint plan")
    if (
        _sha256(build_bytes) != EXPECTED_BUILD_RECEIPT_SHA256
        or _sha256(plan_bytes) != EXPECTED_PLAN_SHA256
        or build.get("kind")
        != "observatory_spawn_coordinate_capsule_hw_observer_build"
        or build.get("module_sha256") != EXPECTED_MODULE_SHA256
        or build.get("hardware_breakpoint_plan_sha256") != EXPECTED_PLAN_SHA256
        or plan.get("kind")
        != "observatory_spawn_coordinate_capsule_hardware_breakpoint_plan"
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            "capsule build identity differs"
        )
    validate_spawn_coordinate_capsule_build_identity(
        build,
        observed_module_sha256=EXPECTED_MODULE_SHA256,
        observed_build_receipt_sha256=EXPECTED_BUILD_RECEIPT_SHA256,
    )
    return build, plan


def _validate_trial(
    trial: Mapping[str, Any],
    *,
    pair_name: str,
    condition: str,
    condition_dir: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    suffix = pair_name[-3:]
    pair_id = f"spawn-capsule-pair{suffix}"
    capture_id = f"{pair_id}-{condition}"
    _exact_keys(
        trial,
        {
            "schema_version",
            "kind",
            "created_at",
            "pair_id",
            "condition",
            "capture_id",
            "capture_track",
            "artifact_root",
            "session_file",
            "process_identity",
            "start_state",
            "status",
            "valid_trial",
            "module_sha256",
            "build_receipt_sha256",
            "pre_dispatch_turn",
            "auto_turn",
            "dispatch",
            "boundary",
            "outcome",
            "snapshot",
            "analysis",
            "snapshot_consumed_from_bridge",
            "pause_guard",
            "errors",
        },
        f"{pair_name} {condition} trial",
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind") != TRIAL_KIND
        or trial.get("pair_id") != pair_id
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("capture_track") != "owner_local_modified"
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
        or trial.get("module_sha256") != EXPECTED_MODULE_SHA256
        or trial.get("build_receipt_sha256")
        != EXPECTED_BUILD_RECEIPT_SHA256
        or type(trial.get("pre_dispatch_turn")) is not int
        or trial.get("snapshot_consumed_from_bridge") is not True
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} trial identity differs"
        )
    trial_created_at = _created_at(trial, f"{pair_name} {condition}")
    process_identity = _validate_process_identity(
        trial.get("process_identity"),
        trial_created_at=trial_created_at,
        label=f"{pair_name} {condition}",
    )
    start_state_path = condition_dir / "start_state_proof.json"
    start_state_proof = _load(
        start_state_path,
        f"{pair_name} {condition} start-state proof",
    )
    try:
        start_state_proof = validate_start_state_verification_proof(
            start_state_proof,
            process_identity=process_identity,
        )
    except StartStateProofError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} start-state proof differs: {exc}"
        ) from exc
    start_state_metadata = _metadata_digest(
        trial.get("start_state"),
        start_state_path,
        f"{pair_name} {condition} start-state proof",
    )
    _exact_keys(
        start_state_metadata,
        {"path", "sha256", "verified_at", "manifest_sha256", "tree_sha256"},
        f"{pair_name} {condition} start-state metadata",
    )
    if (
        not Path(str(start_state_metadata.get("path"))).is_absolute()
        or start_state_metadata.get("verified_at")
        != start_state_proof.get("verified_at")
        or start_state_metadata.get("manifest_sha256")
        != start_state_proof.get("manifest_sha256")
        or start_state_metadata.get("tree_sha256")
        != _mapping(
            start_state_proof.get("manifest"),
            f"{pair_name} {condition} start-state manifest",
        ).get("tree_sha256")
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} start-state metadata differs"
        )
    artifact_root = Path(str(trial.get("artifact_root")))
    session_file = Path(str(trial.get("session_file")))
    if (
        not artifact_root.is_absolute()
        or not session_file.is_absolute()
        or not session_file.is_relative_to(artifact_root)
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} external artifact paths differ"
        )

    auto = _mapping(trial.get("auto_turn"), f"{pair_name} {condition} auto_turn")
    if (
        auto.get("status") != "PLAN"
        or auto.get("local_end_turn_reserved") is not True
        or auto.get("end_turn_plan_source") != "lightning_loop"
        or auto.get("end_turn_delivery_mode") != "local"
        or type(auto.get("end_turn_plan_id")) is not str
        or not auto.get("end_turn_plan_id")
        or auto.get("turn") != trial.get("pre_dispatch_turn")
        or auto.get("desyncs_detected") != 0
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} End Turn reservation differs"
        )
    dispatch = _mapping(
        trial.get("dispatch"), f"{pair_name} {condition} dispatch"
    )
    delivery = _mapping(
        dispatch.get("dispatch"), f"{pair_name} {condition} delivery"
    )
    if (
        dispatch.get("status") != "DISPATCHED"
        or delivery.get("delivery_confirmation") != "delivered_confirmed"
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} End Turn delivery differs"
        )
    errors = _mapping(trial.get("errors"), f"{pair_name} {condition} errors")
    _exact_keys(errors, ERROR_FIELDS, f"{pair_name} {condition} errors")
    if any(errors.values()):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} trial has errors"
        )
    pause = _mapping(
        trial.get("pause_guard"), f"{pair_name} {condition} pause guard"
    )
    if (
        pause.get("status") not in {"OK", "PAUSED"}
        or pause.get("pause_verified") is not True
        or pause.get("safe_to_think") is not True
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} pause guard differs"
        )
    _metadata_digest(
        trial.get("outcome"),
        condition_dir / "outcome.json",
        f"{pair_name} {condition} outcome",
    )

    boundary = _mapping(
        trial.get("boundary"), f"{pair_name} {condition} boundary"
    )
    common_boundary = {
        "condition",
        "capture_id",
        "state",
        "prepare_ack",
        "finish_ack",
        "abort_ack",
    }
    armed_boundary = {
        "snapshot_sha256",
        "draw_record_count",
        "scheduler_count",
        "selector_count",
        "capsule_count",
        "seam_bytes_unchanged",
        "debug_registers_cleared",
        "addresses_or_pointers_published",
    }
    _exact_keys(
        boundary,
        common_boundary | (armed_boundary if condition == "armed" else set()),
        f"{pair_name} {condition} boundary",
    )
    armed = "true" if condition == "armed" else "false"
    expected_prepare = (
        "OK OBS_SPAWN_CAPSULE_PREPARE "
        f"condition={condition} capture={capture_id} seed=324508639 armed={armed}"
    )
    if (
        boundary.get("condition") != condition
        or boundary.get("capture_id") != capture_id
        or boundary.get("state") != "complete"
        or boundary.get("prepare_ack") != expected_prepare
        or boundary.get("abort_ack") is not None
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            f"{pair_name} {condition} boundary differs"
        )

    if condition == "armed":
        snapshot = _load(
            condition_dir / "snapshot.json", f"{pair_name} armed snapshot"
        )
        summary = _mapping(snapshot.get("summary"), f"{pair_name} snapshot summary")
        integrity = _mapping(
            snapshot.get("integrity"), f"{pair_name} snapshot integrity"
        )
        expected_finish = (
            "OK OBS_SPAWN_CAPSULE_FINISH "
            f"condition=armed capture={capture_id} "
            f"draws={summary.get('draw_record_count')} "
            f"scheduler={summary.get('scheduler_count')} "
            f"fallback={summary.get('selector_fallback_count')} "
            f"standard={summary.get('selector_standard_count')} "
            f"selectors={summary.get('selector_count')} "
            f"capsules={summary.get('capsule_count')} complete=true"
        )
        snapshot_metadata = _metadata_digest(
            trial.get("snapshot"),
            condition_dir / "snapshot.json",
            f"{pair_name} armed snapshot",
        )
        analysis_metadata = _metadata_digest(
            trial.get("analysis"),
            condition_dir / "analysis.json",
            f"{pair_name} armed analysis",
        )
        if (
            boundary.get("finish_ack") != expected_finish
            or boundary.get("snapshot_sha256") != _object_sha256(snapshot)
            or boundary.get("draw_record_count")
            != summary.get("draw_record_count")
            or boundary.get("scheduler_count") != summary.get("scheduler_count")
            or boundary.get("selector_count") != summary.get("selector_count")
            or boundary.get("capsule_count") != summary.get("capsule_count")
            or boundary.get("seam_bytes_unchanged") is not True
            or boundary.get("debug_registers_cleared") is not True
            or boundary.get("addresses_or_pointers_published") is not False
            or snapshot_metadata.get("draw_record_count")
            != summary.get("draw_record_count")
            or snapshot_metadata.get("capsule_count") != summary.get("capsule_count")
            or snapshot_metadata.get("complete") is not True
            or analysis_metadata.get("kind") != CORRELATION_KIND
            or analysis_metadata.get("status") != "correlated"
            or integrity.get("state") != "restored"
            or integrity.get("complete") is not True
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} armed evidence metadata differs"
            )
    else:
        expected_finish = (
            "OK OBS_SPAWN_CAPSULE_FINISH "
            f"condition={condition} capture={capture_id} draws=0 scheduler=0 "
            "fallback=0 standard=0 selectors=0 capsules=0 complete=true"
        )
        if (
            boundary.get("finish_ack") != expected_finish
            or trial.get("snapshot") is not None
            or trial.get("analysis") is not None
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} {condition} published observer output"
            )
    return process_identity, start_state_proof


def _validate_lifecycle(
    lifecycle: Mapping[str, Any],
    *,
    trial: Mapping[str, Any],
    process_identity: Mapping[str, Any],
    start_state_proof: Mapping[str, Any],
    pair_name: str,
    condition: str,
    condition_dir: Path,
) -> tuple[str, str]:
    label = f"{pair_name} {condition} lifecycle"
    pair_id = f"spawn-capsule-pair{pair_name[-3:]}"
    capture_id = f"{pair_id}-{condition}"
    _exact_keys(
        lifecycle,
        {
            "schema_version",
            "kind",
            "created_at",
            "pair_id",
            "condition",
            "capture_id",
            "capture_track",
            "status",
            "valid_lifecycle",
            "artifact_root",
            "condition_root",
            "build_identity",
            "runtime_modules",
            "restore",
            "start_state",
            "session",
            "native_continue",
            "launch",
            "process_identity",
            "bridge_start",
            "bridge_start_sha256",
            "trial",
            "close",
            "errors",
        },
        label,
    )
    lifecycle_created_at = _timestamp(
        lifecycle.get("created_at"), f"{label} created_at"
    )
    artifact_root = Path(str(lifecycle.get("artifact_root")))
    external_condition_root = Path(str(lifecycle.get("condition_root")))
    try:
        external_relative = external_condition_root.relative_to(artifact_root)
    except ValueError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} external roots differ"
        ) from exc
    if (
        lifecycle.get("schema_version") != 1
        or lifecycle.get("kind") != LIFECYCLE_KIND
        or lifecycle.get("pair_id") != pair_id
        or lifecycle.get("condition") != condition
        or lifecycle.get("capture_id") != capture_id
        or lifecycle.get("capture_track") != "owner_local_modified"
        or lifecycle.get("status") != "complete"
        or lifecycle.get("valid_lifecycle") is not True
        or not artifact_root.is_absolute()
        or not external_condition_root.is_absolute()
        or external_relative.as_posix() != f"{pair_name}/{condition}"
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} identity differs")

    build = _mapping(lifecycle.get("build_identity"), f"{label} build identity")
    _exact_keys(
        build,
        {
            "executable_sha256",
            "executable_size",
            "module_sha256",
            "build_receipt_sha256",
        },
        f"{label} build identity",
    )
    if (
        build.get("executable_sha256") != EXPECTED_PROCESS_EXECUTABLE_SHA256
        or build.get("executable_size") != EXPECTED_PROCESS_EXECUTABLE_SIZE
        or build.get("module_sha256") != EXPECTED_MODULE_SHA256
        or build.get("build_receipt_sha256") != EXPECTED_BUILD_RECEIPT_SHA256
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} build identity differs")

    runtime_modules = _mapping(
        lifecycle.get("runtime_modules"), f"{label} runtime modules"
    )
    _exact_keys(
        runtime_modules,
        set(EXPECTED_RUNTIME_MODULES),
        f"{label} runtime modules",
    )
    scripts_dir = Path(str(process_identity.get("executable_path"))).parent / "scripts"
    for role, expected in EXPECTED_RUNTIME_MODULES.items():
        identity = _mapping(runtime_modules.get(role), f"{label} {role}")
        _exact_keys(identity, {"path", "size", "sha256"}, f"{label} {role}")
        expected_path = scripts_dir / str(expected["filename"])
        if (
            not Path(str(identity.get("path"))).is_absolute()
            or os.path.normcase(str(identity.get("path")))
            != os.path.normcase(str(expected_path))
            or identity.get("size") != expected["size"]
            or identity.get("sha256") != expected["sha256"]
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{label} {role} identity differs"
            )

    manifest = _mapping(
        start_state_proof.get("manifest"), f"{label} start-state manifest"
    )
    restore = _mapping(lifecycle.get("restore"), f"{label} restore")
    _exact_keys(
        restore,
        {"manifest_sha256", "tree_sha256", "file_count", "total_bytes"},
        f"{label} restore",
    )
    if (
        restore.get("manifest_sha256") != start_state_proof.get("manifest_sha256")
        or restore.get("tree_sha256") != manifest.get("tree_sha256")
        or restore.get("file_count") != manifest.get("file_count")
        or restore.get("total_bytes") != manifest.get("total_bytes")
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} restore differs")

    start_state = _metadata_digest(
        lifecycle.get("start_state"),
        condition_dir / "start_state_proof.json",
        f"{label} start-state proof",
    )
    _exact_keys(
        start_state,
        {
            "path",
            "sha256",
            "verified_at",
            "manifest_sha256",
            "tree_sha256",
            "game_stopped",
        },
        f"{label} start state",
    )
    if (
        not Path(str(start_state.get("path"))).is_absolute()
        or start_state.get("verified_at") != start_state_proof.get("verified_at")
        or start_state.get("manifest_sha256")
        != start_state_proof.get("manifest_sha256")
        or start_state.get("tree_sha256") != manifest.get("tree_sha256")
        or start_state.get("game_stopped") is not True
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} start state differs")

    session = _metadata_digest(
        lifecycle.get("session"),
        condition_dir / "session.json",
        f"{label} session",
    )
    _exact_keys(
        session,
        {"path", "sha256", "source_path", "source_sha256"},
        f"{label} session",
    )
    if (
        trial.get("session_file") != session.get("path")
        or not Path(str(session.get("path"))).is_absolute()
        or not Path(str(session.get("source_path"))).is_absolute()
        or not _lower_sha256(session.get("source_sha256"))
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} session differs")

    native_continue = _mapping(
        lifecycle.get("native_continue"), f"{label} native Continue"
    )
    _exact_keys(
        native_continue,
        {"request_path", "armed", "consumed", "ack", "cleaned_after_failure"},
        f"{label} native Continue",
    )
    if (
        not Path(str(native_continue.get("request_path"))).is_absolute()
        or native_continue.get("armed") is not True
        or native_continue.get("consumed") is not True
        or native_continue.get("ack")
        != "OK OBS_NATIVE_CONTINUE_REQUEST invoked=true"
        or native_continue.get("cleaned_after_failure") is not False
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} native Continue differs")

    launch = _mapping(lifecycle.get("launch"), f"{label} launch")
    _exact_keys(
        launch,
        {
            "requested_at",
            "launcher_pid",
            "executable_path",
            "executable_size",
            "executable_sha256",
        },
        f"{label} launch",
    )
    launch_requested_at = _timestamp(
        launch.get("requested_at"), f"{label} launch requested_at"
    )
    process_created_at = _timestamp(
        process_identity.get("created_at"), f"{label} process created_at"
    )
    if (
        launch.get("launcher_pid") != process_identity.get("pid")
        or os.path.normcase(str(launch.get("executable_path")))
        != os.path.normcase(str(process_identity.get("executable_path")))
        or launch.get("executable_size") != EXPECTED_PROCESS_EXECUTABLE_SIZE
        or launch.get("executable_sha256") != EXPECTED_PROCESS_EXECUTABLE_SHA256
        or launch_requested_at > process_created_at
        or lifecycle.get("process_identity") != process_identity
        or trial.get("process_identity") != process_identity
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} process binding differs")

    bridge_start = _mapping(lifecycle.get("bridge_start"), f"{label} bridge start")
    _exact_keys(
        bridge_start,
        {
            "mission_id",
            "phase",
            "turn",
            "active_mechs",
            "master_seed",
            "region_id",
            "timeline_fingerprint",
            "ai_seed_fingerprint",
        },
        f"{label} bridge start",
    )
    bridge_start_sha256 = _object_sha256(bridge_start)
    if (
        bridge_start.get("mission_id") != "Mission_Power"
        or bridge_start.get("phase") != "combat_player"
        or type(bridge_start.get("turn")) is not int
        or bridge_start.get("turn") != trial.get("pre_dispatch_turn")
        or type(bridge_start.get("active_mechs")) is not int
        or bridge_start.get("active_mechs") <= 0
        or lifecycle.get("bridge_start_sha256") != bridge_start_sha256
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} bridge start differs")

    trial_metadata = _metadata_digest(
        lifecycle.get("trial"),
        condition_dir / "trial.json",
        f"{label} trial",
    )
    _exact_keys(
        trial_metadata,
        {"path", "sha256", "status", "valid_trial"},
        f"{label} trial",
    )
    if (
        not Path(str(trial_metadata.get("path"))).is_absolute()
        or trial_metadata.get("status") != "complete"
        or trial_metadata.get("valid_trial") is not True
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} trial differs")

    close = _mapping(lifecycle.get("close"), f"{label} close")
    _exact_keys(
        close,
        {
            "method",
            "requested_at",
            "closed_at",
            "pid",
            "creation_filetime",
            "window_handles",
            "exited",
            "forced_termination",
        },
        f"{label} close",
    )
    close_requested_at = _timestamp(
        close.get("requested_at"), f"{label} close requested_at"
    )
    closed_at = _timestamp(close.get("closed_at"), f"{label} closed_at")
    handles = close.get("window_handles")
    if (
        close.get("method") != "WM_CLOSE"
        or close.get("pid") != process_identity.get("pid")
        or close.get("creation_filetime")
        != process_identity.get("creation_filetime")
        or not isinstance(handles, list)
        or not handles
        or any(type(hwnd) is not int or hwnd <= 0 for hwnd in handles)
        or len(handles) != len(set(handles))
        or close.get("exited") is not True
        or close.get("forced_termination") is not False
        or close_requested_at < _created_at(trial, f"{label} trial")
        or closed_at < close_requested_at
        or lifecycle_created_at < closed_at
    ):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} close differs")

    errors = _mapping(lifecycle.get("errors"), f"{label} errors")
    _exact_keys(errors, LIFECYCLE_ERROR_FIELDS, f"{label} errors")
    if any(errors.values()):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} has errors")
    return str(session["source_sha256"]), bridge_start_sha256


def _validate_campaign_lifecycle(
    value: Mapping[str, Any],
    *,
    campaign_root: Path,
    condition_lifecycles: Mapping[str, Mapping[str, Any]],
    start_state_tree_sha256: str,
    start_state_manifest_sha256: str,
) -> Mapping[str, Any]:
    _exact_keys(
        value,
        {
            "schema_version",
            "kind",
            "created_at",
            "capture_track",
            "status",
            "valid_campaign",
            "artifact_root",
            "condition_order",
            "conditions",
            "final_restore",
            "errors",
        },
        "campaign lifecycle",
    )
    created_at = _timestamp(value.get("created_at"), "campaign lifecycle created_at")
    artifact_root = Path(str(value.get("artifact_root")))
    expected_order = [
        f"{pair_name}/{condition}"
        for pair_name, order in PAIR_SPECS.items()
        for condition in order
    ]
    if (
        value.get("schema_version") != 1
        or value.get("kind") != CAMPAIGN_LIFECYCLE_KIND
        or value.get("capture_track") != "owner_local_modified"
        or value.get("status") != "complete"
        or value.get("valid_campaign") is not True
        or not artifact_root.is_absolute()
        or value.get("condition_order") != expected_order
    ):
        raise SpawnCoordinateCapsuleCampaignError("campaign lifecycle identity differs")
    conditions = value.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != len(expected_order):
        raise SpawnCoordinateCapsuleCampaignError(
            "campaign lifecycle condition count differs"
        )
    latest_condition_at: datetime | None = None
    for expected_key, condition_value in zip(expected_order, conditions, strict=True):
        condition = _mapping(condition_value, "campaign lifecycle condition")
        _exact_keys(
            condition,
            {"pair", "condition", "lifecycle_sha256"},
            "campaign lifecycle condition",
        )
        pair_name, condition_name = expected_key.split("/", 1)
        lifecycle = condition_lifecycles.get(expected_key)
        if lifecycle is None:
            raise SpawnCoordinateCapsuleCampaignError(
                "campaign lifecycle condition is unavailable"
            )
        lifecycle_path = campaign_root / pair_name / condition_name / "lifecycle.json"
        if (
            condition.get("pair") != pair_name
            or condition.get("condition") != condition_name
            or condition.get("lifecycle_sha256")
            != _sha256(_stable_bytes(lifecycle_path, expected_key))
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"campaign lifecycle condition differs: {expected_key}"
            )
        condition_created_at = _timestamp(
            lifecycle.get("created_at"), f"{expected_key} lifecycle created_at"
        )
        if latest_condition_at is None or condition_created_at > latest_condition_at:
            latest_condition_at = condition_created_at

    try:
        final_restore = validate_start_state_verification_proof(
            value.get("final_restore")
        )
    except StartStateProofError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"campaign final restore differs: {exc}"
        ) from exc
    final_verified_at = _timestamp(
        final_restore.get("verified_at"), "campaign final restore verified_at"
    )
    final_manifest = _mapping(
        final_restore.get("manifest"), "campaign final restore manifest"
    )
    if (
        final_restore.get("manifest_sha256") != start_state_manifest_sha256
        or final_manifest.get("tree_sha256") != start_state_tree_sha256
        or latest_condition_at is None
        or final_verified_at <= latest_condition_at
        or created_at < final_verified_at
    ):
        raise SpawnCoordinateCapsuleCampaignError(
            "campaign final restore ordering or tree differs"
        )
    errors = _mapping(value.get("errors"), "campaign lifecycle errors")
    _exact_keys(
        errors,
        {"conditions", "final_restore"},
        "campaign lifecycle errors",
    )
    if any(errors.values()):
        raise SpawnCoordinateCapsuleCampaignError("campaign lifecycle has errors")
    return final_restore


def _capsule_observation(analysis: Mapping[str, Any]) -> dict[str, Any]:
    capsules = analysis.get("capsules")
    if not isinstance(capsules, list) or not capsules:
        raise SpawnCoordinateCapsuleCampaignError("capsule analysis has no capsules")
    observations: list[dict[str, Any]] = []
    for index, capsule_value in enumerate(capsules):
        capsule = _mapping(capsule_value, f"capsule analysis[{index}]")
        board = _mapping(capsule.get("board"), f"capsule analysis[{index}].board")
        rng = _mapping(capsule.get("rng"), f"capsule analysis[{index}].rng")
        observations.append(
            {
                "selector_kind": capsule.get("selector_kind"),
                "board_turn": board.get("turn"),
                "pawn_id": board.get("pawn_id"),
                "pawn_team": board.get("pawn_team"),
                "board_carriers_sha256": _object_sha256(board),
                "rng_state_before": rng.get("state_before"),
                "rng_state_after": rng.get("state_after"),
                "raw_rng": rng.get("raw_rng"),
                "selected_index": capsule.get("selected_index"),
                "selected": capsule.get("selected"),
                "candidate_vector_sha256": _object_sha256(capsule.get("candidates")),
            }
        )
    return {
        "capsule_count": len(observations),
        "capsules": observations,
        "observation_sha256": _object_sha256(observations),
    }


def build_spawn_coordinate_capsule_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate three counterbalanced triplets and return their receipt."""
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    _exact_campaign_root(root)
    build_path = repo / BUILD_RECEIPT
    plan_path = repo / BREAKPOINT_PLAN
    build, _plan = _validate_build_identity(build_path, plan_path)

    pairs: list[dict[str, Any]] = []
    semantic_sha256: str | None = None
    observation_sha256: str | None = None
    capsule_counts: list[int] = []
    draw_counts: list[int] = []
    session_files: set[str] = set()
    plan_ids: set[str] = set()
    created_times: set[datetime] = set()
    process_identities: set[tuple[int, int]] = set()
    process_executable_paths: set[str] = set()
    start_state_tree_sha256: str | None = None
    start_state_manifest_sha256: str | None = None
    source_session_sha256: str | None = None
    bridge_start_sha256: str | None = None
    condition_lifecycles: dict[str, Mapping[str, Any]] = {}
    for pair_name, expected_order in PAIR_SPECS.items():
        pair_dir = root / pair_name
        _exact_children(pair_dir, {"control", "dormant", "armed"}, directories=True)
        trials: dict[str, Mapping[str, Any]] = {}
        outcomes: dict[str, Mapping[str, Any]] = {}
        artifacts: dict[str, dict[str, Any]] = {}
        for condition in ("control", "dormant", "armed"):
            condition_dir = pair_dir / condition
            expected_files = {
                "trial.json",
                "outcome.json",
                "start_state_proof.json",
                "session.json",
                "lifecycle.json",
            }
            if condition == "armed":
                expected_files |= {"snapshot.json", "analysis.json"}
            _exact_children(condition_dir, expected_files, directories=False)
            trial = _load(
                condition_dir / "trial.json", f"{pair_name} {condition} trial"
            )
            process_identity, start_state_proof = _validate_trial(
                trial,
                pair_name=pair_name,
                condition=condition,
                condition_dir=condition_dir,
            )
            process_key = (
                int(process_identity["pid"]),
                int(process_identity["creation_filetime"]),
            )
            if process_key in process_identities:
                raise SpawnCoordinateCapsuleCampaignError(
                    f"{pair_name} {condition} process identity was reused"
                )
            process_identities.add(process_key)
            process_executable_paths.add(
                os.path.normcase(str(process_identity["executable_path"]))
            )
            start_manifest = _mapping(
                start_state_proof["manifest"],
                f"{pair_name} {condition} start-state manifest",
            )
            observed_tree_sha256 = str(start_manifest["tree_sha256"])
            observed_manifest_sha256 = str(start_state_proof["manifest_sha256"])
            if start_state_tree_sha256 is None:
                start_state_tree_sha256 = observed_tree_sha256
                start_state_manifest_sha256 = observed_manifest_sha256
            elif (
                observed_tree_sha256 != start_state_tree_sha256
                or observed_manifest_sha256 != start_state_manifest_sha256
            ):
                raise SpawnCoordinateCapsuleCampaignError(
                    f"{pair_name} {condition} start-state tree differs"
                )
            lifecycle = _load(
                condition_dir / "lifecycle.json",
                f"{pair_name} {condition} lifecycle",
            )
            condition_lifecycles[f"{pair_name}/{condition}"] = lifecycle
            observed_source_session_sha256, observed_bridge_start_sha256 = (
                _validate_lifecycle(
                    lifecycle,
                    trial=trial,
                    process_identity=process_identity,
                    start_state_proof=start_state_proof,
                    pair_name=pair_name,
                    condition=condition,
                    condition_dir=condition_dir,
                )
            )
            if source_session_sha256 is None:
                source_session_sha256 = observed_source_session_sha256
                bridge_start_sha256 = observed_bridge_start_sha256
            elif (
                observed_source_session_sha256 != source_session_sha256
                or observed_bridge_start_sha256 != bridge_start_sha256
            ):
                raise SpawnCoordinateCapsuleCampaignError(
                    f"{pair_name} {condition} lifecycle baseline differs"
                )
            session_file = str(trial["session_file"])
            plan_id = str(_mapping(trial["auto_turn"], "auto_turn")["end_turn_plan_id"])
            created = _created_at(trial, f"{pair_name} {condition}")
            if (
                session_file in session_files
                or plan_id in plan_ids
                or created in created_times
            ):
                raise SpawnCoordinateCapsuleCampaignError(
                    f"{pair_name} {condition} trial identity was reused"
                )
            session_files.add(session_file)
            plan_ids.add(plan_id)
            created_times.add(created)
            outcome = _load(
                condition_dir / "outcome.json", f"{pair_name} {condition} outcome"
            )
            trials[condition] = trial
            outcomes[condition] = outcome
            artifacts[f"{condition}_trial"] = _artifact(
                condition_dir / "trial.json", repo
            )
            artifacts[f"{condition}_outcome"] = _artifact(
                condition_dir / "outcome.json", repo
            )
            artifacts[f"{condition}_start_state_proof"] = _artifact(
                condition_dir / "start_state_proof.json", repo
            )
            artifacts[f"{condition}_session"] = _artifact(
                condition_dir / "session.json", repo
            )
            artifacts[f"{condition}_lifecycle"] = _artifact(
                condition_dir / "lifecycle.json", repo
            )

        actual_order = [
            condition
            for condition, _ in sorted(
                (
                    (condition, _created_at(trials[condition], pair_name))
                    for condition in trials
                ),
                key=lambda item: item[1],
            )
        ]
        if actual_order != expected_order:
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} condition order differs"
            )

        armed_dir = pair_dir / "armed"
        snapshot = _load(armed_dir / "snapshot.json", f"{pair_name} snapshot")
        analysis = correlate_spawn_coordinate_capsule_snapshot(
            snapshot,
            outcomes["armed"],
            build_receipt=build,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )
        validation = validate_spawn_coordinate_capsule_snapshot(
            snapshot,
            build_receipt=build,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )
        committed_analysis = _load(
            armed_dir / "analysis.json", f"{pair_name} analysis"
        )
        if (
            analysis != committed_analysis
            or analysis.get("kind") != CORRELATION_KIND
            or analysis.get("status") != "correlated"
            or analysis.get("claims") != EXPECTED_CLAIMS
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} capsule correlation drift"
            )
        integrity = _mapping(analysis.get("integrity"), f"{pair_name} integrity")
        if (
            integrity.get("state") != "restored"
            or integrity.get("complete") is not True
            or integrity.get("debug_registers_cleared") is not True
            or integrity.get("veh_removed") is not True
            or integrity.get("executable_file_released") is not True
            or integrity.get("executable_bytes_modified") is not False
            or integrity.get("seam_bytes_unchanged") is not True
            or integrity.get("addresses_or_pointers_published") is not False
        ):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} observer restoration differs"
            )

        observation = _capsule_observation(validation)
        if observation_sha256 is None:
            observation_sha256 = observation["observation_sha256"]
        elif observation["observation_sha256"] != observation_sha256:
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} armed capsule observation differs"
            )
        capsule_counts.append(observation["capsule_count"])
        draw_counts.append(len(snapshot["draw_records"]))

        comparisons = {
            "control_dormant": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["dormant"],
                capture_id=f"spawn-capsule-{pair_name}-dormant",
            ),
            "control_armed": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["armed"],
                capture_id=f"spawn-capsule-{pair_name}-armed",
            ),
        }
        if any(item["status"] != "matched" for item in comparisons.values()):
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        pair_semantic = comparisons["control_armed"]["control_semantic_sha256"]
        if semantic_sha256 is None:
            semantic_sha256 = pair_semantic
        elif pair_semantic != semantic_sha256:
            raise SpawnCoordinateCapsuleCampaignError(
                f"{pair_name} fixed scenario outcome differs"
            )

        artifacts["armed_snapshot"] = _artifact(
            armed_dir / "snapshot.json", repo
        )
        artifacts["armed_analysis"] = _artifact(
            armed_dir / "analysis.json", repo
        )
        pairs.append(
            {
                "pair": pair_name,
                "pair_id": f"spawn-capsule-pair{pair_name[-3:]}",
                "condition_order": actual_order,
                "observation": observation,
                "observer_integrity": {
                    field: integrity[field]
                    for field in (
                        "state",
                        "complete",
                        "debug_registers_cleared",
                        "veh_removed",
                        "executable_file_released",
                        "executable_bytes_modified",
                        "seam_bytes_unchanged",
                        "addresses_or_pointers_published",
                    )
                },
                "whole_game_outcome": {
                    "control_dormant": "matched",
                    "control_armed": "matched",
                    "difference_count": 0,
                    "semantic_sha256": pair_semantic,
                },
                "artifacts": artifacts,
            }
        )

    if len(process_executable_paths) != 1:
        raise SpawnCoordinateCapsuleCampaignError(
            "campaign process executable paths differ"
        )
    assert start_state_tree_sha256 is not None
    assert start_state_manifest_sha256 is not None
    campaign_lifecycle = _load(
        root / "campaign_lifecycle.json",
        "campaign lifecycle",
    )
    final_restore = _validate_campaign_lifecycle(
        campaign_lifecycle,
        campaign_root=root,
        condition_lifecycles=condition_lifecycles,
        start_state_tree_sha256=start_state_tree_sha256,
        start_state_manifest_sha256=start_state_manifest_sha256,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": {
            field: build[field]
            for field in (
                "build_id",
                "architecture",
                "executable_sha256",
                "executable_size",
                "inventory_canonical_sha256",
                "boundary_map_canonical_sha256",
                "rng_return_map_sha256",
                "spawn_candidate_boundary_sha256",
                "position_observations_boundary_sha256",
                "rng_state_owner_sha256",
                "hardware_breakpoint_plan_sha256",
                "module_sha256",
            )
        },
        "campaign": {
            "pair_count": len(pairs),
            "conditions": ["control", "dormant", "armed"],
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fixed_seed": 324508639,
            "mission_id": "Mission_Power",
            "dispatch_boundary": "reserved_local_end_turn_through_next_player_turn",
            "fresh_process_count": len(process_identities),
            "all_process_identities_distinct": len(process_identities) == 9,
            "process_executable_sha256": EXPECTED_PROCESS_EXECUTABLE_SHA256,
            "start_state_tree_sha256": start_state_tree_sha256,
            "start_state_manifest_sha256": start_state_manifest_sha256,
            "all_start_states_match": True,
            "source_session_sha256": source_session_sha256,
            "bridge_start_sha256": bridge_start_sha256,
            "all_lifecycles_complete": True,
            "all_processes_gracefully_closed": True,
            "all_runtime_modules_exact": True,
        },
        "pairs": pairs,
        "results": {
            "classification": "selector_entry_board_rng_capsule_captured",
            "complete_restored_snapshots": len(pairs),
            "capsule_counts": capsule_counts,
            "draw_counts": draw_counts,
            "stable_armed_observation_sha256": observation_sha256,
            "all_armed_observations_match": True,
            "all_semantic_outcomes_match": True,
            "semantic_sha256": semantic_sha256,
        },
        "claims": {
            "proven": [
                "Every armed trial paired each selector-entry Board carrier capsule with the exact shared native RNG transition, candidate vector, selected index, and selected coordinate.",
                "Each native selected coordinate matched the ordered spawning markers exposed by the fresh bridge state on the following player turn.",
                "Control, dormant-loaded, and armed whole-game outcomes were semantically identical in all three counterbalanced triplets.",
                "Every one-shot observer cleared its debug registers, removed its vectored exception handler, released the pinned executable, preserved every seam, published no pointer, and modified no executable bytes.",
                "All nine trials used distinct Windows process identities bound to the exact attested Breach.exe path, size, and SHA-256.",
                "Before each fresh process started, the game was stopped and the live save file set and bytes exactly matched the same sealed start-state manifest.",
                "Each trial used the exact installed capsule observer, Continue helper, and RNG-seed helper; consumed the one-shot native Continue request; began from the same fresh bridge state and isolated source session; and ended by gracefully closing that exact process without forced termination.",
            ],
            "not_proven": [
                "Transient dead non-corpse occupancy at selector entry.",
                "The selected pawn's complete native path profile at selector entry.",
                "A complete future spawn forecast from ordinary solver input; these captures expose native selector-time state, not all prior scheduling inputs.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "At each observed spawn selector, pair the exact selector-entry "
                "Board carriers and shared MSVC RNG transition with the ordered "
                "candidate vector and chosen coordinate"
            ),
            "offline_model": (
                "src.observatory.spawn_coordinate_capsule_hw."
                "validate_spawn_coordinate_capsule_snapshot"
            ),
            "capture_backed_test": (
                "test_committed_spawn_coordinate_capsule_campaign_rebuilds_exactly"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator consumes authoritative settled spawn markers; "
                "the capsule does not yet expose every earlier native scheduling "
                "input needed for prospective forecasting."
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": False,
            "cleanup_receipt_pending": True,
            "final_restore_verified_at": final_restore["verified_at"],
            "final_restore_manifest_sha256": final_restore["manifest_sha256"],
            "final_restore_tree_sha256": final_restore["manifest"]["tree_sha256"],
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(build_path, repo),
            "hardware_breakpoint_plan": _artifact(plan_path, repo),
            "campaign_lifecycle": _artifact(
                root / "campaign_lifecycle.json",
                repo,
            ),
        },
    }


def publish_spawn_coordinate_capsule_campaign_receipt(
    value: Mapping[str, Any], output: Path
) -> tuple[Path, str]:
    """Create one immutable canonical campaign receipt."""
    path = output.resolve()
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
