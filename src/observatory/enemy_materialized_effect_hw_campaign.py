"""Seal the counterbalanced complete enemy materialized-effect runtime campaign."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.observatory.enemy_materialized_effect_hw import (
    ANALYSIS_KIND,
    EXPECTED_PLAN_SHA256,
    correlate_enemy_materialized_effect_snapshot,
)
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_enemy_materialized_effect_hw_campaign_receipt"
EXPECTED_MODULE_SHA256 = (
    "cf686bb2c48b56f1314d996ad53236b76a03eb679d9893d2878929724adde328"
)
EXPECTED_BUILD_RECEIPT_SHA256 = (
    "0c7de96bf9fcde3fa07c109eb4c3d0b295fc7db707c19e74f61af7236f8da3a2"
)
BUILD_RECEIPT = Path("data/observatory/native") / (
    "itb_observatory_enemy_materialized_effect_hw_observer_"
    f"{EXPECTED_MODULE_SHA256}.dll.receipt.json"
)
BREAKPOINT_PLAN = Path("data/observatory/native") / (
    "windows_build_13725832_enemy_materialized_effect_hw_plan_"
    f"{EXPECTED_PLAN_SHA256}.json"
)
SAVE_TREE_SHA256 = (
    "cfdb040ab907f854595b5760d1da4492886e6f9240c6d6a5a90886e1b6686c11"
)
FIXED_SEED = 324_508_639
EXPECTED_SCENARIO = {
    "consumed_spawn_count": 0,
    "pawn_id": 1303,
    "pawn_type": "Firefly1",
    "start": [4, 4],
}
EXPECTED_CANDIDATES = [
    {
        "destination_x": 4,
        "destination_y": 2,
        "target_x": 3,
        "target_y": 2,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 4,
        "destination_y": 3,
        "target_x": 3,
        "target_y": 3,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 4,
        "destination_y": 5,
        "target_x": 3,
        "target_y": 5,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 4,
        "destination_y": 6,
        "target_x": 3,
        "target_y": 6,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 5,
        "destination_y": 3,
        "target_x": 4,
        "target_y": 3,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 5,
        "destination_y": 4,
        "target_x": 4,
        "target_y": 4,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 5,
        "destination_y": 5,
        "target_x": 4,
        "target_y": 5,
        "target_score": 5,
        "positioning_score": 5,
    },
    {
        "destination_x": 4,
        "destination_y": 4,
        "target_x": 3,
        "target_y": 4,
        "target_score": 5,
        "positioning_score": 5,
    },
]
EXPECTED_SELECTOR_CONTEXT = {
    "pawn_id": 1303,
    "current_weapon_raw": 1,
    "base_current_weapon_raw": -1,
    "board_width": 8,
    "board_height": 8,
    "interior_favorable": True,
    "selector_rng_state_before": "0xd6ac62fb",
    "selector_rng_state_after": "0x6f5d21d2",
}
EXPECTED_MATERIALIZED_EFFECT = {
    "effect_count": 0,
    "queued_count": 1,
    "owner_id": 1303,
    "skill_owner_id": 1303,
    "skill_source_tag": 6,
    "origin_x": 5,
    "origin_y": 4,
    "selected_target_x": 4,
    "selected_target_y": 4,
    "queued_loc_x": 3,
    "queued_loc_y": 4,
    "queued_damage": 1,
    "queued_private_origin_x": 5,
    "queued_private_origin_y": 4,
    "queued_private_source_tag": 6,
    "queued_boost_marker": False,
    "queued_animation_length": 13,
    "queued_animation": "ExploFirefly1",
    "skill_key_length": 11,
    "skill_key": "FireflyAtk1",
}
PAIR_SPECS = {
    "pair001": ["control", "dormant", "armed"],
    "pair002": ["armed", "dormant", "control"],
    "pair003": ["dormant", "control", "armed"],
}


class EnemyMaterializedEffectHwCampaignError(RuntimeError):
    """Raised when committed materialized evidence is missing or inconsistent."""


def _stable_bytes(path: Path, label: str) -> bytes:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise EnemyMaterializedEffectHwCampaignError(
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
        raise EnemyMaterializedEffectHwCampaignError(f"{label} changed while read")
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
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return _sha256(payload)


def _load(path: Path, label: str) -> dict[str, Any]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnemyMaterializedEffectHwCampaignError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise EnemyMaterializedEffectHwCampaignError(f"{label} must be an object")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EnemyMaterializedEffectHwCampaignError(f"{label} must be an object")
    return value


def _exact_children(root: Path, expected: set[str], *, directories: bool) -> None:
    if root.is_symlink() or not root.is_dir():
        raise EnemyMaterializedEffectHwCampaignError(f"campaign path is invalid: {root}")
    matching = {
        item.name
        for item in root.iterdir()
        if item.is_dir() == directories and not item.is_symlink()
    }
    other = {
        item.name
        for item in root.iterdir()
        if item.is_dir() != directories or item.is_symlink()
    }
    if matching != expected or other:
        raise EnemyMaterializedEffectHwCampaignError(
            f"campaign children differ at {root}"
        )


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    repo = repository_root.resolve()
    try:
        relative = resolved.relative_to(repo).as_posix()
    except ValueError as exc:
        raise EnemyMaterializedEffectHwCampaignError(
            f"campaign artifact is outside the repository: {resolved}"
        ) from exc
    data = _stable_bytes(resolved, relative)
    return {"path": relative, "sha256": _sha256(data), "size": len(data)}


def _created_at(trial: Mapping[str, Any], label: str) -> datetime:
    value = trial.get("created_at")
    if type(value) is not str:
        raise EnemyMaterializedEffectHwCampaignError(f"{label} created_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnemyMaterializedEffectHwCampaignError(
            f"{label} created_at is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise EnemyMaterializedEffectHwCampaignError(
            f"{label} created_at has no timezone"
        )
    return parsed


def _metadata_digest(
    metadata: object,
    artifact_path: Path,
    label: str,
) -> Mapping[str, Any]:
    value = _mapping(metadata, f"{label} metadata")
    digest = _sha256(_stable_bytes(artifact_path, label))
    if value.get("sha256") != digest:
        raise EnemyMaterializedEffectHwCampaignError(f"{label} digest differs")
    return value


def _validate_trial(
    trial: Mapping[str, Any],
    *,
    pair_name: str,
    condition: str,
    condition_dir: Path,
) -> None:
    suffix = pair_name[-3:]
    capture_id = f"materialized-pair-{suffix}-{condition}"
    expected_counts = (
        {
            "candidate_count": 8,
            "materialized_effect_count": 1,
            "queue_count": 1,
            "selected_count": 1,
        }
        if condition == "armed"
        else {
            "candidate_count": 0,
            "materialized_effect_count": 0,
            "queue_count": 0,
            "selected_count": 0,
        }
    )
    expected_ack = (
        "OK OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL "
        f"condition={condition} capture={capture_id} "
        "pawn=1303 type=Firefly1 at=4,4 consumed_spawns=0 "
        f"candidates={expected_counts['candidate_count']} "
        f"selected={expected_counts['selected_count']} "
        f"materialized={expected_counts['materialized_effect_count']} "
        f"queue={expected_counts['queue_count']} complete=true"
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind") != "observatory_enemy_materialized_effect_turn_trial"
        or trial.get("pair_id") != f"materialized-pair-{suffix}"
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("capture_track") != "owner_local_modified"
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
        or trial.get("module_sha256") != EXPECTED_MODULE_SHA256
        or trial.get("build_receipt_sha256")
        != EXPECTED_BUILD_RECEIPT_SHA256
        or trial.get("scenario") != EXPECTED_SCENARIO
        or trial.get("native_counts") != expected_counts
        or trial.get("command_ack") != expected_ack
    ):
        raise EnemyMaterializedEffectHwCampaignError(
            f"{pair_name} {condition} trial differs"
        )
    errors = _mapping(trial.get("errors"), f"{pair_name} {condition} errors")
    if errors.get("command") or errors.get("analysis") or errors.get("outcome"):
        raise EnemyMaterializedEffectHwCampaignError(
            f"{pair_name} {condition} trial has errors"
        )
    _metadata_digest(
        trial.get("outcome"),
        condition_dir / "outcome.json",
        f"{pair_name} {condition} outcome",
    )
    if condition == "armed":
        snapshot = _metadata_digest(
            trial.get("snapshot"),
            condition_dir / "snapshot.json",
            f"{pair_name} snapshot",
        )
        analysis = _metadata_digest(
            trial.get("analysis"),
            condition_dir / "analysis.json",
            f"{pair_name} analysis",
        )
        if (
            snapshot.get("candidate_count") != 8
            or snapshot.get("materialized_effect_count") != 1
            or snapshot.get("complete") is not True
            or analysis.get("status") != "correlated"
        ):
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} armed evidence is incomplete"
            )
    elif trial.get("snapshot") is not None or trial.get("analysis") is not None:
        raise EnemyMaterializedEffectHwCampaignError(
            f"{pair_name} {condition} published observer output"
        )


def build_enemy_materialized_effect_hw_campaign_receipt(
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
    build = _load(build_path, "enemy materialized-effect build receipt")
    plan = _load(plan_path, "enemy materialized-effect breakpoint plan")
    if (
        _sha256(_stable_bytes(build_path, "enemy materialized-effect build receipt"))
        != EXPECTED_BUILD_RECEIPT_SHA256
        or build.get("module_sha256") != EXPECTED_MODULE_SHA256
        or build.get("hardware_breakpoint_plan_sha256")
        != EXPECTED_PLAN_SHA256
        or _sha256(_stable_bytes(plan_path, "enemy materialized-effect breakpoint plan"))
        != EXPECTED_PLAN_SHA256
        or plan.get("kind")
        != "observatory_enemy_materialized_effect_hardware_breakpoint_plan"
    ):
        raise EnemyMaterializedEffectHwCampaignError(
            "enemy materialized-effect build identity differs"
        )

    pairs: list[dict[str, Any]] = []
    semantic_sha256: str | None = None
    native_fingerprint: str | None = None
    for pair_name, expected_order in PAIR_SPECS.items():
        pair_dir = root / pair_name
        _exact_children(
            pair_dir, {"control", "dormant", "armed"}, directories=True
        )
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
            trials[condition] = trial
            outcomes[condition] = _load(
                condition_dir / "outcome.json",
                f"{pair_name} {condition} outcome",
            )
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
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} condition order differs"
            )

        armed_dir = pair_dir / "armed"
        snapshot = _load(armed_dir / "snapshot.json", f"{pair_name} snapshot")
        analysis = correlate_enemy_materialized_effect_snapshot(
            snapshot,
            outcomes["armed"],
            build_receipt=build,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )
        committed_analysis = _load(
            armed_dir / "analysis.json", f"{pair_name} analysis"
        )
        if analysis != committed_analysis or analysis.get("kind") != ANALYSIS_KIND:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} enemy materialized-effect analysis drift"
            )
        replay = _mapping(analysis.get("replay"), f"{pair_name} replay")
        native = _mapping(analysis.get("native"), f"{pair_name} native")
        if (
            snapshot.get("candidate_records") is None
            or analysis.get("status") != "correlated"
            or native.get("candidate_count") != 8
            or native.get("selected_input_index") != 5
            or native.get("selected_source") != "primary"
            or native.get("draw_count") != 1
            or native.get("rng_state_before") != "0xd6ac62fb"
            or native.get("rng_state_after") != "0x6f5d21d2"
            or native.get("queue_origin") != [5, 4]
            or native.get("queued_shot") != [4, 4]
            or native.get("materialized_queued_loc") != [3, 4]
            or native.get("materialized_damage") != 1
            or native.get("materialized_animation") != "ExploFirefly1"
            or native.get("native_skill_key") != "FireflyAtk1"
            or native.get("current_weapon_raw") != 1
            or native.get("base_current_weapon_before_queue_raw") != -1
            or native.get("base_current_weapon_at_queue_raw") != 1
            or replay.get("selected_record") != EXPECTED_CANDIDATES[5]
            or replay.get("rng_transcript")
            != [
                {
                    "bound": 8,
                    "call_rva": "0x000f7f6a",
                    "caller_id": 30,
                    "canonical_observable_post_call_state": "0x6f5d21d2",
                    "canonical_observable_pre_call_state": "0x56ac62fb",
                    "draw_index": 1,
                    "modulo_result": 5,
                    "raw_result": 28509,
                    "source": "primary_record_group",
                }
            ]
        ):
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} replay facts differ"
            )
        validated_candidates = [
            {key: record[key] for key in EXPECTED_CANDIDATES[index]}
            for index, record in enumerate(snapshot["candidate_records"])
        ]
        if validated_candidates != EXPECTED_CANDIDATES:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} ordered candidate vector differs"
            )
        if snapshot.get("selector_context") != EXPECTED_SELECTOR_CONTEXT:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} selector context differs"
            )
        if snapshot.get("materialized_effect") != EXPECTED_MATERIALIZED_EFFECT:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} materialized SkillEffect differs"
            )

        comparisons = {
            "control_dormant": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["dormant"],
                capture_id=f"enemy-materialized-effect-{pair_name}-dormant",
            ),
            "control_armed": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["armed"],
                capture_id=f"enemy-materialized-effect-{pair_name}-armed",
            ),
        }
        if any(item["status"] != "matched" for item in comparisons.values()):
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        pair_semantic = comparisons["control_armed"]["control_semantic_sha256"]
        if semantic_sha256 is None:
            semantic_sha256 = pair_semantic
        elif pair_semantic != semantic_sha256:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} fixed scenario outcome differs"
            )

        fingerprint_value = {
            "candidate_records": EXPECTED_CANDIDATES,
            "selector_context": EXPECTED_SELECTOR_CONTEXT,
            "selected_record": replay["selected_record"],
            "rng_transcript": replay["rng_transcript"],
            "materialized_effect": EXPECTED_MATERIALIZED_EFFECT,
            "queue_origin": native["queue_origin"],
            "queued_shot": native["queued_shot"],
            "current_weapon_raw": native["current_weapon_raw"],
            "base_current_weapon_before_queue_raw": native[
                "base_current_weapon_before_queue_raw"
            ],
            "base_current_weapon_at_queue_raw": native[
                "base_current_weapon_at_queue_raw"
            ],
        }
        pair_fingerprint = _object_sha256(fingerprint_value)
        if native_fingerprint is None:
            native_fingerprint = pair_fingerprint
        elif pair_fingerprint != native_fingerprint:
            raise EnemyMaterializedEffectHwCampaignError(
                f"{pair_name} native observation differs"
            )

        integrity = _mapping(snapshot.get("integrity"), f"{pair_name} integrity")
        artifacts["armed_snapshot"] = _artifact(
            armed_dir / "snapshot.json", repo
        )
        artifacts["armed_analysis"] = _artifact(
            armed_dir / "analysis.json", repo
        )
        pairs.append(
            {
                "pair": pair_name,
                "pair_id": f"materialized-pair-{pair_name[-3:]}",
                "condition_order": actual_order,
                "scenario": EXPECTED_SCENARIO,
                "observation": fingerprint_value,
                "observation_sha256": pair_fingerprint,
                "observer_integrity": {
                    field: integrity[field]
                    for field in (
                        "state",
                        "complete",
                        "ordering_error_count",
                        "overflow_count",
                        "pointer_fault_count",
                        "torn_candidate_count",
                        "torn_materialized_count",
                        "torn_record_count",
                        "transition_mismatch_count",
                        "unexpected_breakpoint_count",
                        "wrong_thread_count",
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
                "record_selector_boundary_canonical_sha256",
                "rng_state_owner_sha256",
                "skill_effect_boundary_canonical_sha256",
                "materialized_prebytes_sha256",
                "hardware_breakpoint_plan_sha256",
                "module_sha256",
            )
        },
        "campaign": {
            "pair_count": len(pairs),
            "conditions": ["control", "dormant", "armed"],
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fixed_seed": FIXED_SEED,
            "save_tree_sha256": SAVE_TREE_SHA256,
            "scenario": EXPECTED_SCENARIO,
        },
        "pairs": pairs,
        "results": {
            "classification": (
                "selected_firefly_skill_effect_materialization_runtime_proven"
            ),
            "complete_restored_snapshots": len(pairs),
            "candidate_counts": [8] * len(pairs),
            "stable_candidate_vector_sha256": _object_sha256(
                EXPECTED_CANDIDATES
            ),
            "stable_native_observation_sha256": native_fingerprint,
            "stable_selector_rng_state_before": "0xd6ac62fb",
            "stable_selector_rng_state_after": "0x6f5d21d2",
            "draw_counts": [1] * len(pairs),
            "caller_ids": [30] * len(pairs),
            "selected_input_indices": [5] * len(pairs),
            "queue_origins": [[5, 4]] * len(pairs),
            "queued_shots": [[4, 4]] * len(pairs),
            "materialized_effects": [EXPECTED_MATERIALIZED_EFFECT] * len(pairs),
            "materialized_locations": [[3, 4]] * len(pairs),
            "materialized_damages": [1] * len(pairs),
            "materialized_animations": ["ExploFirefly1"] * len(pairs),
            "native_skill_keys": ["FireflyAtk1"] * len(pairs),
            "all_armed_observations_match": True,
            "all_semantic_outcomes_match": True,
            "semantic_sha256": semantic_sha256,
        },
        "claims": {
            "proven": [
                "The fixed Firefly1 scenario produced the same complete ordered vector of eight 24-byte enemy candidate records in all three armed fresh processes.",
                "Starting from selector state 0xd6ac62fb, the exact record-selector replay consumed one caller-30 draw, selected input index 5, reached state 0x6f5d21d2, and bound that record to the immediate same-pawn queue commit.",
                "At the native SkillEffect postprocess seam in each armed process, the selected FireflyAtk1 materialized with owner and source ancestry 1303/6, origin [5,4], selected target [4,4], and one queued one-damage ExploFirefly1 SpaceDamage at [3,4]; that exact object then bound to the settled attack ray.",
                "Control, dormant-loaded, and armed whole-game outcomes were semantically identical in all three counterbalanced triplets.",
                "Every one-shot observer cleared all private debug state, removed its vectored exception handler, released its pinned executable, preserved every seam, published no pointer, and modified no executable bytes.",
            ],
            "not_proven": [
                "A universal candidate vector or selected action for other boards, enemy types, multiple weapons, cancellation, or retarget paths.",
                "Universal SkillEffect materialization, TwoClick/final-effect routes, or callback-time Board observations outside this fixed selected FireflyAtk1 path.",
                "Prospective enemy-phase forecasting from ordinary solver input, which still lacks the complete candidate vector and selector-entry RNG state.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "Given every complete ordered native record and selector-entry "
                "state, replay the exact record selector and require the "
                "selected record to bind through its native materialized "
                "SkillEffect to the settled queue"
            ),
            "offline_model": (
                "src.observatory.enemy_record_selector_boundary."
                "replay_enemy_record_selector"
            ),
            "capture_backed_test": (
                "test_committed_enemy_materialized_effect_binds_raw_selected_and_settled_queue"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator consumes the authoritative settled enemy "
                "queue and does not receive the complete prospective record "
                "vector or selector-entry RNG state."
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(build_path, repo),
            "hardware_breakpoint_plan": _artifact(plan_path, repo),
        },
    }


def publish_enemy_materialized_effect_hw_campaign_receipt(
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
        raise EnemyMaterializedEffectHwCampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
