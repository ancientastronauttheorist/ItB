"""Seal a counterbalanced selector-entry Board/RNG capsule campaign."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.spawn_coordinate_capsule_hw import (
    CORRELATION_KIND,
    EXPECTED_BUILD_RECEIPT_SHA256,
    EXPECTED_MODULE_SHA256,
    EXPECTED_PLAN_SHA256,
    correlate_spawn_coordinate_capsule_snapshot,
    validate_spawn_coordinate_capsule_build_identity,
    validate_spawn_coordinate_capsule_snapshot,
)


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_spawn_coordinate_capsule_hw_campaign_receipt"
TRIAL_KIND = "observatory_spawn_coordinate_capsule_turn_trial"
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


def _created_at(trial: Mapping[str, Any], label: str) -> datetime:
    value = trial.get("created_at")
    if type(value) is not str:
        raise SpawnCoordinateCapsuleCampaignError(f"{label} created_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} created_at is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise SpawnCoordinateCapsuleCampaignError(
            f"{label} created_at has no timezone"
        )
    return parsed


def _metadata_digest(
    metadata: object,
    artifact_path: Path,
    label: str,
) -> Mapping[str, Any]:
    value = _mapping(metadata, f"{label} metadata")
    if value.get("sha256") != _sha256(_stable_bytes(artifact_path, label)):
        raise SpawnCoordinateCapsuleCampaignError(f"{label} digest differs")
    return value


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
) -> None:
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
    _created_at(trial, f"{pair_name} {condition}")
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
    _exact_children(root, set(PAIR_SPECS), directories=True)
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
    for pair_name, expected_order in PAIR_SPECS.items():
        pair_dir = root / pair_name
        _exact_children(pair_dir, {"control", "dormant", "armed"}, directories=True)
        trials: dict[str, Mapping[str, Any]] = {}
        outcomes: dict[str, Mapping[str, Any]] = {}
        artifacts: dict[str, dict[str, Any]] = {}
        for condition in ("control", "dormant", "armed"):
            condition_dir = pair_dir / condition
            expected_files = {"trial.json", "outcome.json"}
            if condition == "armed":
                expected_files |= {"snapshot.json", "analysis.json"}
            _exact_children(condition_dir, expected_files, directories=False)
            trial = _load(
                condition_dir / "trial.json", f"{pair_name} {condition} trial"
            )
            _validate_trial(
                trial,
                pair_name=pair_name,
                condition=condition,
                condition_dir=condition_dir,
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
            "save_restoration_pending": True,
            "cleanup_receipt_pending": True,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(build_path, repo),
            "hardware_breakpoint_plan": _artifact(plan_path, repo),
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
