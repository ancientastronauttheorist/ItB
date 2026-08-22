"""Seal the final build-keyed spawn-span and selected-queue campaigns."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.observatory.msvc_rng_replay import (
    recover_observable_pre_state,
    recover_raw_pre_states,
    replay_results,
)
from src.observatory.native_checkpoint import (
    validate_native_checkpoint,
    validate_return_map_binding,
)
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.selected_queue_hw import correlate_selected_queue_snapshot
from src.observatory.spawn_rng_attribution import analyze_spawn_rng


SCHEMA_VERSION = 1
SPAWN_RECEIPT_KIND = "observatory_spawn_span_campaign_receipt"
SPAWN_REPLAY_RECEIPT_KIND = "observatory_spawn_replay_campaign_receipt"
SELECTED_RECEIPT_KIND = "observatory_selected_queue_campaign_receipt"
FIXED_SEED = 324_508_639
CONTROLLER_SHA256 = "4923ee3b08c802824f17963dc625015d2c91e6e467149b72bba218c49830935d"
SPAWN_REPLAY_CONTROLLER_SHA256 = (
    "c411c5e1d84cfae079b6b5f6b69b9bc022d0f0a9a87af5bf877ca1c1badb699f"
)
SELECTED_MODULE_SHA256 = "2cf202cc2e58c33651864ed8939b8491cc082048c300d82b63ff3cfbd76a5676"
SAVE_TREE_SHA256 = "ca305830ca471c3d5f1501bb8750a7d076283752bde39a66f637717e7f04eae5"

OBSERVER_RECEIPT = Path(
    "data/observatory/native/"
    "windows_build_13725832_31fe35265598_rng_core_observer_receipt.json"
)
RETURN_MAP = Path(
    "data/observatory/native/"
    "windows_build_13725832_31fe35265598_rng_return_ids.json"
)
RESTORE_HASHES = Path(
    "data/observatory/native/"
    "windows_build_13725832_31fe35265598_rng_core_restore_hashes.json"
)
SELECTED_RECEIPT = Path(
    "data/observatory/native/"
    "windows_build_13725832_31fe35265598_selected_queue_hw_observer_receipt.json"
)
SPAWNER_SOURCE_SHA256 = "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
RANDOM_ELEMENT_SOURCE_SHA256 = (
    "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
)
SPAWN_REPLAY_CONTROLLER_RECEIPT = Path(
    "data/observatory/native/"
    "windows_build_13725832_31fe35265598_spawn_replay_controller_receipt.json"
)

SPAWN_PAIR_SPECS = {
    "pair001": {
        "order": "exact_hook_then_spawn_span",
        "capture_ids": ("spawn-p001-exact", "spawn-p001-span-final"),
        "selected_pawn": "Firefly2",
        "draw_results": [24976, 26204, 24669],
        "difference_paths": ["/spawning_tiles/0/0", "/spawning_tiles/0/1"],
    },
    "pair002": {
        "order": "spawn_span_then_exact_hook",
        "capture_ids": ("spawn-p002-exact", "spawn-p002-span"),
        "selected_pawn": "Scarab2",
        "draw_results": [757, 11839, 17554],
        "difference_paths": ["/spawning_tiles/0/1"],
    },
    "pair003": {
        "order": "exact_hook_then_spawn_span",
        "capture_ids": ("spawn-p003-exact", "spawn-p003-span"),
        "selected_pawn": "Scarab2",
        "draw_results": [6793, 13804, 4449],
        "difference_paths": [],
    },
}

SPAWN_REPLAY_PAIR_SPECS = {
    "pair001": {
        "order": "control_then_spawn_replay",
        "capture_ids": (
            "spawn-replay-p001-control-r3",
            "spawn-replay-p001-replay-r3",
        ),
        "selected_pawn": "Firefly2",
        "selected_base": "Firefly",
        "draw_results": [6988, 26456, 12828],
        "observable_pre_state_hex": "0x14c88732",
        "difference_paths": [],
    },
    "pair002": {
        "order": "spawn_replay_then_control",
        "capture_ids": (
            "spawn-replay-p002-control",
            "spawn-replay-p002-replay",
        ),
        "selected_pawn": "Scarab2",
        "selected_base": "Scarab",
        "draw_results": [14826, 21631, 24783],
        "observable_pre_state_hex": "0x14ca8e21",
        "difference_paths": ["/spawning_tiles/0/0", "/spawning_tiles/0/1"],
    },
    "pair003": {
        "order": "control_then_spawn_replay",
        "capture_ids": (
            "spawn-replay-p003-control",
            "spawn-replay-p003-replay",
        ),
        "selected_pawn": "Firefly2",
        "selected_base": "Firefly",
        "draw_results": [2424, 29057, 30541],
        "observable_pre_state_hex": "0x14cf8cc9",
        "difference_paths": ["/spawning_tiles/0/0", "/spawning_tiles/0/1"],
    },
}

SELECTED_PAIR_SPECS = {
    "pair001": {
        "order": ["control", "dormant", "armed"],
        "capture_ids": {
            "control": "selected-pair-001-control",
            "dormant": "selected-pair-001-dormant",
            "armed": "selected-pair-001-armed-r2",
        },
    },
    "pair002": {
        "order": ["armed", "dormant", "control"],
        "capture_ids": {
            "control": "selected-pair-002-control",
            "dormant": "selected-pair-002-dormant",
            "armed": "selected-pair-002-armed",
        },
    },
    "pair003": {
        "order": ["dormant", "control", "armed"],
        "capture_ids": {
            "control": "selected-pair-003-control-r2",
            "dormant": "selected-pair-003-dormant",
            "armed": "selected-pair-003-armed",
        },
    },
}

SELECTED_NATIVE_EXPECTED = {
    "pawn_id": 1303,
    "ai_destination": [5, 4],
    "ai_target": [4, 4],
    "queue_origin": [5, 4],
    "queue_target": [4, 4],
    "queued_shot": [4, 4],
    "current_weapon_raw": 1,
    "queued_skill_raw": 1,
    "selected_rank_fields_raw": [5, 5],
    "base_current_weapon_raw": -1,
}


class NativeBoundaryCampaignError(RuntimeError):
    """Raised when campaign artifacts cannot support the bounded claims."""


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeBoundaryCampaignError(f"invalid JSON artifact {path}: {exc}") from exc


def _canonical_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise NativeBoundaryCampaignError(f"value is not canonical JSON: {exc}") from exc
    return (encoded + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeBoundaryCampaignError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], names: set[str], label: str
) -> None:
    actual = set(value)
    if actual != names:
        raise NativeBoundaryCampaignError(
            f"{label} fields differ; missing={sorted(names - actual)}, "
            f"unknown={sorted(actual - names)}"
        )


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise NativeBoundaryCampaignError(f"artifact is outside repository: {path}") from exc
    payload = path.read_bytes()
    return {"path": relative, "size": len(payload), "sha256": _sha256(payload)}


def _exact_children(path: Path, names: set[str], *, directories: bool) -> None:
    if not path.is_dir():
        raise NativeBoundaryCampaignError(f"campaign directory is missing: {path}")
    actual = {
        child.name
        for child in path.iterdir()
        if (child.is_dir() if directories else child.is_file())
    }
    if actual != names:
        raise NativeBoundaryCampaignError(
            f"artifact set differs at {path}; missing={sorted(names - actual)}, "
            f"extra={sorted(actual - names)}"
        )


def _created_at(value: Mapping[str, Any], label: str) -> datetime:
    raw = value.get("created_at")
    if type(raw) is not str:
        raise NativeBoundaryCampaignError(f"{label}.created_at is invalid")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise NativeBoundaryCampaignError(f"{label}.created_at is invalid") from exc
    if parsed.tzinfo is None:
        raise NativeBoundaryCampaignError(f"{label}.created_at lacks a timezone")
    return parsed


def _expected_rng_identity(build: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "platform": "windows",
        "architecture": build["architecture"],
        "executable_sha256": build["executable_sha256"],
        "executable_size": build["executable_size"],
        "build_id": build["build_id"],
        "inventory_sha256": build["inventory_canonical_sha256"],
        "boundary_map_sha256": build["boundary_map_canonical_sha256"],
        "rng_return_map_sha256": build["rng_return_map_sha256"],
        "helper_sha256": build["module_sha256"],
        "hook_plan_sha256": build["hook_plan_sha256"],
        "restore_manifest_sha256": build["restore_manifest_sha256"],
    }


def _validate_native_turn_trial(
    trial: Mapping[str, Any],
    *,
    pair_id: str,
    condition: str,
    capture_id: str,
    checkpoint_path: Path,
    outcome_path: Path,
) -> None:
    if (
        trial.get("schema_version") != 1
        or trial.get("kind") != "observatory_native_rng_turn_trial"
        or trial.get("pair_id") != pair_id
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial is not complete")
    errors = _mapping(trial.get("errors"), f"{pair_id} {condition} errors")
    if any(errors.values()):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial has errors")
    auto = _mapping(trial.get("auto_turn"), f"{pair_id} {condition} auto turn")
    if (
        auto.get("status") != "ok"
        or auto.get("actions_completed") != 3
        or auto.get("desyncs_detected") != 0
        or auto.get("post_phase") != "combat_player"
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} turn was not clean")
    boundary = _mapping(trial.get("boundary"), f"{pair_id} {condition} boundary")
    if (
        boundary.get("condition") != condition
        or boundary.get("capture_id") != capture_id
        or boundary.get("state") != "complete"
        or boundary.get("hook_bytes_restored") is not True
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} boundary was not restored")
    if condition == "spawn_span" and (
        boundary.get("spawn_span_count") != 1
        or boundary.get("spawn_wrapper_restored") is not True
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} spawn wrapper was not restored")
    checkpoint = _mapping(trial.get("checkpoint"), f"{pair_id} {condition} checkpoint")
    outcome = _mapping(trial.get("outcome"), f"{pair_id} {condition} outcome")
    if (
        checkpoint.get("sha256") != _file_sha256(checkpoint_path)
        or outcome.get("sha256") != _file_sha256(outcome_path)
        or checkpoint.get("diagnostic_complete") is not True
        or checkpoint.get("hook_bytes_restored") is not True
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} artifact hash differs")


def build_spawn_span_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    _exact_children(root, set(SPAWN_PAIR_SPECS), directories=True)
    build = _mapping(_load(repo / OBSERVER_RECEIPT), "RNG observer receipt")
    return_map = _mapping(_load(repo / RETURN_MAP), "RNG return map")
    restore_hashes = _mapping(_load(repo / RESTORE_HASHES), "restore hashes")
    expected_identity = _expected_rng_identity(build)
    pairs: list[dict[str, Any]] = []

    for pair_name, spec in SPAWN_PAIR_SPECS.items():
        pair_dir = root / pair_name
        _exact_children(pair_dir, {"exact_hook", "spawn_span"}, directories=True)
        exact_dir = pair_dir / "exact_hook"
        span_dir = pair_dir / "spawn_span"
        _exact_children(
            exact_dir,
            {"trial.json", "outcome.json", "checkpoint.json"},
            directories=False,
        )
        _exact_children(
            span_dir,
            {
                "trial.json",
                "outcome.json",
                "checkpoint.json",
                "span_ledger.json",
                "spawn_analysis.json",
            },
            directories=False,
        )
        exact_trial = _mapping(_load(exact_dir / "trial.json"), "exact trial")
        span_trial = _mapping(_load(span_dir / "trial.json"), "span trial")
        exact_capture, span_capture = spec["capture_ids"]
        pair_id = f"spawn-pair-{pair_name[-3:]}"
        _validate_native_turn_trial(
            exact_trial,
            pair_id=pair_id,
            condition="exact_hook",
            capture_id=exact_capture,
            checkpoint_path=exact_dir / "checkpoint.json",
            outcome_path=exact_dir / "outcome.json",
        )
        _validate_native_turn_trial(
            span_trial,
            pair_id=pair_id,
            condition="spawn_span",
            capture_id=span_capture,
            checkpoint_path=span_dir / "checkpoint.json",
            outcome_path=span_dir / "outcome.json",
        )
        order = (
            "exact_hook_then_spawn_span"
            if _created_at(exact_trial, "exact trial")
            < _created_at(span_trial, "span trial")
            else "spawn_span_then_exact_hook"
        )
        if order != spec["order"]:
            raise NativeBoundaryCampaignError(f"{pair_name} condition order differs")

        exact_checkpoint = _mapping(_load(exact_dir / "checkpoint.json"), "exact checkpoint")
        span_checkpoint = _mapping(_load(span_dir / "checkpoint.json"), "span checkpoint")
        exact_verification = validate_native_checkpoint(
            exact_checkpoint,
            expected_identity=expected_identity,
            return_map=return_map,
            expected_restore_hashes=restore_hashes,
        )
        if not exact_verification["diagnostic_complete"]:
            raise NativeBoundaryCampaignError(f"{pair_name} exact checkpoint is incomplete")
        ledger = _mapping(_load(span_dir / "span_ledger.json"), "spawn span ledger")
        analysis = analyze_spawn_rng(
            span_checkpoint,
            span_ledger=ledger,
            expected_controller_sha256=CONTROLLER_SHA256,
            return_map=return_map,
            expected_identity=expected_identity,
            expected_restore_hashes=restore_hashes,
        )
        if analysis != _load(span_dir / "spawn_analysis.json"):
            raise NativeBoundaryCampaignError(f"{pair_name} spawn analysis drift")
        span = analysis["spans"][0] if analysis.get("summary", {}).get("span_count") == 1 else None
        if (
            not isinstance(span, Mapping)
            or span.get("status") != "resolved_with_draws"
            or span.get("selected_pawn") != spec["selected_pawn"]
            or span.get("caller_ids") != [21, 21, 21]
            or span.get("caller_origins") != [
                "lua_random_leaf",
                "lua_random_leaf",
                "lua_random_leaf",
            ]
        ):
            raise NativeBoundaryCampaignError(f"{pair_name} spawn span transcript differs")
        by_sequence = {record["seq"]: record for record in span_checkpoint["records"]}
        draw_results = [by_sequence[seq]["result"] for seq in span["draw_sequences"]]
        if draw_results != spec["draw_results"]:
            raise NativeBoundaryCampaignError(f"{pair_name} spawn draw results differ")

        comparison = compare_rng_trial_outcomes(
            _mapping(_load(exact_dir / "outcome.json"), "exact outcome"),
            _mapping(_load(span_dir / "outcome.json"), "span outcome"),
            capture_id=f"spawn-span-{pair_name}",
        )
        paths = [item["path"] for item in comparison["differences"]]
        if paths != spec["difference_paths"]:
            raise NativeBoundaryCampaignError(f"{pair_name} outcome difference scope differs")

        pairs.append(
            {
                "pair": pair_name,
                "pair_id": pair_id,
                "condition_order": order,
                "selected_pawn": span["selected_pawn"],
                "native_draws": [
                    {
                        "sequence": sequence,
                        "caller_id": by_sequence[sequence]["caller_id"],
                        "result": by_sequence[sequence]["result"],
                    }
                    for sequence in span["draw_sequences"]
                ],
                "restoration": {
                    "native_hook_bytes": True,
                    "spawn_wrapper": True,
                    "restore_conflict": False,
                },
                "whole_game_outcome": {
                    "status": comparison["status"],
                    "difference_paths": paths,
                    "exact_semantic_sha256": comparison["control_semantic_sha256"],
                    "span_semantic_sha256": comparison["exact_hook_semantic_sha256"],
                },
                "artifacts": {
                    "exact_trial": _artifact(exact_dir / "trial.json", repo),
                    "exact_outcome": _artifact(exact_dir / "outcome.json", repo),
                    "exact_checkpoint": _artifact(exact_dir / "checkpoint.json", repo),
                    "span_trial": _artifact(span_dir / "trial.json", repo),
                    "span_outcome": _artifact(span_dir / "outcome.json", repo),
                    "span_checkpoint": _artifact(span_dir / "checkpoint.json", repo),
                    "span_ledger": _artifact(span_dir / "span_ledger.json", repo),
                    "spawn_analysis": _artifact(span_dir / "spawn_analysis.json", repo),
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": SPAWN_RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": expected_identity,
        "campaign": {
            "pair_count": len(pairs),
            "fixed_seed": FIXED_SEED,
            "condition_orders": dict(Counter(item["condition_order"] for item in pairs)),
            "controller_sha256": CONTROLLER_SHA256,
            "spawner_source_sha256": SPAWNER_SOURCE_SHA256,
        },
        "pairs": pairs,
        "results": {
            "classification": "spawn_call_order_resolved_solver_replay_inputs_unavailable",
            "complete_restored_spans": len(pairs),
            "draw_count_per_span": [len(item["native_draws"]) for item in pairs],
            "selected_pawns": [item["selected_pawn"] for item in pairs],
            "call_order": [
                {
                    "position": 1,
                    "lua_source": "random_int(curr_weakRatio[2])",
                    "meaning": "weak-versus-nonweak branch",
                },
                {
                    "position": 2,
                    "lua_source": "random_element(available)",
                    "meaning": "available pawn identity",
                },
                {
                    "position": 3,
                    "lua_source": "random_int(curr_upgradeRatio[2])",
                    "meaning": "upgrade branch",
                },
            ],
            "conditional_fourth_call": (
                "random_bool(chance) occurs only for an eligible unused boss; "
                "none of the three bounded spans took that branch"
            ),
        },
        "claims": {
            "proven": [
                "Each of three source-verified Spawner:NextPawn calls enclosed exactly three native RNG draws, all through the reviewed random_int(max) leaf.",
                "The three enclosed draws align in source order with weak-class choice, available-pawn choice, and upgrade choice; no boss random_bool branch executed.",
                "Every native hook and Lua NextPawn wrapper restored without conflict before evidence publication.",
            ],
            "not_proven": [
                "Replay of future pawn identity from the ordinary solver input; pre-span CRT state and the exact runtime available-array order are not exported.",
                "Whole-game neutrality of spawn instrumentation; two paired outcomes differ only in the following spawn coordinate and one pair matches.",
                "Future spawn-coordinate selection, which occurs outside Spawner:NextPawn.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "rule": (
                "preserve observed spawn markers but do not fabricate a future pawn identity "
                "until the solver receives the missing replay inputs"
            ),
            "rust_test": "test_projection_never_fabricates_unresolved_native_spawn_selection",
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(repo / OBSERVER_RECEIPT, repo),
            "return_map": _artifact(repo / RETURN_MAP, repo),
            "restore_hashes": _artifact(repo / RESTORE_HASHES, repo),
        },
    }


def _validate_spawn_replay_trial(
    trial: Mapping[str, Any],
    *,
    pair_id: str,
    condition: str,
    capture_id: str,
    outcome_path: Path,
    checkpoint_path: Path | None = None,
    replay_path: Path | None = None,
) -> None:
    if (
        trial.get("schema_version") != 1
        or trial.get("kind") != "observatory_native_rng_turn_trial"
        or trial.get("pair_id") != pair_id
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial differs")
    errors = _mapping(trial.get("errors"), f"{pair_id} {condition} errors")
    if any(errors.values()):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial has errors")
    auto = _mapping(trial.get("auto_turn"), f"{pair_id} {condition} auto turn")
    if (
        auto.get("status") != "ok"
        or auto.get("actions_completed") != 3
        or auto.get("desyncs_detected") != 0
        or auto.get("re_solves") != 0
        or auto.get("post_phase") != "combat_player"
        or auto.get("grid_power") != "4/7"
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} turn was not clean")
    outcome = _mapping(trial.get("outcome"), f"{pair_id} {condition} outcome")
    if outcome.get("sha256") != _file_sha256(outcome_path):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} outcome hash differs")
    boundary = _mapping(trial.get("boundary"), f"{pair_id} {condition} boundary")
    if (
        boundary.get("condition") != condition
        or boundary.get("capture_id") != capture_id
        or boundary.get("state") != "complete"
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} boundary differs")

    if condition == "spawn_replay_control":
        if (
            trial.get("checkpoint") is not None
            or "spawn_replay" in trial
            or boundary.get("finish_ack") is not None
            or boundary.get("arm_ack")
            != f"OK OBS_SPAWN_REPLAY_CONTROL capture={capture_id} dormant=true"
        ):
            raise NativeBoundaryCampaignError(
                f"{pair_id} control published diagnostic evidence"
            )
        return

    if checkpoint_path is None or replay_path is None:
        raise NativeBoundaryCampaignError(f"{pair_id} replay paths are missing")
    if (
        boundary.get("hook_bytes_restored") is not True
        or boundary.get("spawn_replay_span_count") != 1
        or boundary.get("spawn_replay_wrappers_restored") is not True
        or type(boundary.get("record_count")) is not int
        or boundary["record_count"] <= 0
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} replay boundary was not restored")
    checkpoint = _mapping(trial.get("checkpoint"), f"{pair_id} checkpoint")
    replay = _mapping(trial.get("spawn_replay"), f"{pair_id} replay capsule")
    if (
        checkpoint.get("sha256") != _file_sha256(checkpoint_path)
        or checkpoint.get("diagnostic_complete") is not True
        or checkpoint.get("hook_bytes_restored") is not True
        or checkpoint.get("record_count") != boundary["record_count"]
        or replay.get("sha256") != _file_sha256(replay_path)
        or replay.get("replay_verified") is not True
        or replay.get("span_count") != 1
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} replay artifact hash differs")


def _validate_spawn_replay_capsule(
    capsule: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    *,
    capture_id: str,
    expected_identity: Mapping[str, Any],
    return_map: Mapping[str, Any],
    expected_restore_hashes: Mapping[str, Any],
) -> dict[str, Any]:
    _exact_fields(
        capsule,
        {
            "schema_version",
            "analysis_kind",
            "capture_id",
            "build_identity",
            "source_identity",
            "controller_sha256",
            "span_id",
            "thread_slot",
            "raw_record_range",
            "native_results",
            "raw_pre_state_candidates",
            "observable_pre_state",
            "observable_pre_state_hex",
            "raw_state_hidden_bit_ambiguous",
            "future_observable_stream_exact",
            "weak_branch",
            "candidate_choice",
            "upgrade_branch",
            "boss_branch",
            "selected_pawn",
            "replay_verified",
        },
        f"{capture_id} replay capsule",
    )
    if (
        capsule.get("schema_version") != 1
        or capsule.get("analysis_kind") != "spawn_rng_replay_capsule"
        or capsule.get("capture_id") != capture_id
        or capsule.get("build_identity") != expected_identity
        or capsule.get("controller_sha256") != SPAWN_REPLAY_CONTROLLER_SHA256
        or capsule.get("span_id") != 1
        or capsule.get("raw_state_hidden_bit_ambiguous") is not True
        or capsule.get("future_observable_stream_exact") is not True
        or capsule.get("replay_verified") is not True
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} replay capsule identity differs")
    source = _mapping(capsule.get("source_identity"), f"{capture_id} source identity")
    expected_source = {
        "spawner_expected_sha256": SPAWNER_SOURCE_SHA256,
        "spawner_expected_source_suffix": "scripts/spawner_backend.lua",
        "spawner_expected_linedefined": 174,
        "random_element_expected_sha256": RANDOM_ELEMENT_SOURCE_SHA256,
        "random_element_expected_source_suffix": "scripts/global.lua",
        "random_element_expected_linedefined": 560,
        "source_locations_verified": True,
    }
    if any(source.get(field) != value for field, value in expected_source.items()):
        raise NativeBoundaryCampaignError(f"{capture_id} replay source differs")
    for prefix, suffix, line in (
        ("spawner", "scripts/spawner_backend.lua", 174),
        ("random_element", "scripts/global.lua", 560),
    ):
        runtime_source = source.get(f"{prefix}_runtime_source")
        if (
            type(runtime_source) is not str
            or "\\" in runtime_source
            or not runtime_source.endswith(suffix)
            or source.get(f"{prefix}_runtime_linedefined") != line
        ):
            raise NativeBoundaryCampaignError(
                f"{capture_id} runtime source differs for {prefix}"
            )

    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    if not verification["diagnostic_complete"]:
        raise NativeBoundaryCampaignError(f"{capture_id} checkpoint is incomplete")
    callers = validate_return_map_binding(checkpoint, return_map)
    random_int = callers.get(21)
    if (
        not isinstance(random_int, Mapping)
        or random_int.get("status") != "reviewed_direct_call"
        or random_int.get("source_region") != "random_int_1"
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} random_int caller is unbound")
    records = checkpoint["records"]
    raw_range = capsule.get("raw_record_range")
    if (
        not isinstance(raw_range, list)
        or len(raw_range) != 2
        or any(type(value) is not int for value in raw_range)
        or not 0 <= raw_range[0] < raw_range[1] <= len(records)
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} raw record range is invalid")
    enclosed = records[raw_range[0] : raw_range[1]]
    if (
        len(enclosed) not in {3, 4}
        or [record["caller_id"] for record in enclosed]
        != [21, 21, 21] + ([25] if len(enclosed) == 4 else [])
        or any(record["kind"] != "rng_core" for record in enclosed)
        or any(record["thread_slot"] != capsule.get("thread_slot") for record in enclosed)
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} enclosed RNG records differ")
    observed = [record["result"] for record in enclosed]
    if capsule.get("native_results") != observed:
        raise NativeBoundaryCampaignError(f"{capture_id} native result join differs")
    raw_states = recover_raw_pre_states(observed)
    observable_state = recover_observable_pre_state(observed)
    if (
        capsule.get("raw_pre_state_candidates")
        != [f"0x{state:08x}" for state in raw_states]
        or capsule.get("observable_pre_state") != observable_state
        or capsule.get("observable_pre_state_hex") != f"0x{observable_state:08x}"
        or list(replay_results(observable_state, len(observed))) != observed
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} recovered RNG state differs")

    weak = _mapping(capsule.get("weak_branch"), f"{capture_id} weak branch")
    candidate = _mapping(
        capsule.get("candidate_choice"), f"{capture_id} candidate choice"
    )
    upgrade = _mapping(capsule.get("upgrade_branch"), f"{capture_id} upgrade branch")
    boss = _mapping(capsule.get("boss_branch"), f"{capture_id} boss branch")
    for branch, result, label in (
        (weak, observed[0], "weak"),
        (candidate, observed[1], "candidate"),
        (upgrade, observed[2], "upgrade"),
    ):
        if branch.get("raw_result") != result:
            raise NativeBoundaryCampaignError(
                f"{capture_id} {label} branch result differs"
            )
    weak_denominator = weak.get("denominator")
    weak_numerator = weak.get("numerator")
    if (
        type(weak_denominator) is not int
        or weak_denominator <= 0
        or type(weak_numerator) is not int
        or weak.get("modulo_result") != observed[0] % weak_denominator
        or weak.get("selected_weak")
        is not (observed[0] % weak_denominator < weak_numerator)
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} weak replay differs")
    available = candidate.get("available")
    if (
        not isinstance(available, list)
        or not available
        or any(type(value) is not str or not value for value in available)
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} candidate array is invalid")
    candidate_index = observed[1] % len(available)
    if (
        candidate.get("selected_index_zero_based") != candidate_index
        or candidate.get("selected_base") != available[candidate_index]
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} candidate replay differs")
    upgrade_denominator = upgrade.get("denominator")
    upgrade_numerator = upgrade.get("numerator")
    if (
        type(upgrade_denominator) is not int
        or upgrade_denominator <= 0
        or type(upgrade_numerator) is not int
        or upgrade.get("modulo_result") != observed[2] % upgrade_denominator
        or type(upgrade.get("break_streak")) is not bool
        or type(upgrade.get("selected_max_level")) is not int
        or upgrade.get("selected_upgrade")
        is not (
            observed[2] % upgrade_denominator < upgrade_numerator
            and upgrade["selected_max_level"] != 1
            and not upgrade["break_streak"]
        )
        or type(upgrade.get("living_upgrade_cap_forced_downgrade")) is not bool
    ):
        raise NativeBoundaryCampaignError(f"{capture_id} upgrade replay differs")
    if len(observed) == 3:
        if boss != {
            "guard_reached": False,
            "boss_available": True,
            "chance": None,
            "raw_result": None,
            "selected_boss": False,
        }:
            raise NativeBoundaryCampaignError(f"{capture_id} boss guard differs")
    else:
        chance = boss.get("chance")
        if (
            boss.get("guard_reached") is not True
            or type(chance) is not int
            or chance <= 0
            or boss.get("raw_result") != observed[3]
            or boss.get("selected_boss") is not (observed[3] % chance == 0)
        ):
            raise NativeBoundaryCampaignError(f"{capture_id} boss replay differs")
    selected_base = candidate["selected_base"]
    selected_pawn = capsule.get("selected_pawn")
    if type(selected_pawn) is not str or not selected_pawn.startswith(selected_base):
        raise NativeBoundaryCampaignError(f"{capture_id} selected pawn differs")
    expected_suffix = (
        "Boss"
        if boss["selected_boss"]
        else "1"
        if not upgrade["selected_upgrade"]
        or upgrade["living_upgrade_cap_forced_downgrade"]
        else "2"
    )
    if selected_pawn != selected_base + expected_suffix:
        raise NativeBoundaryCampaignError(f"{capture_id} final pawn replay differs")
    return {
        "selected_pawn": selected_pawn,
        "selected_base": selected_base,
        "native_results": observed,
        "observable_pre_state_hex": capsule["observable_pre_state_hex"],
        "raw_record_range": raw_range,
        "thread_slot": capsule["thread_slot"],
    }


def build_spawn_replay_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    _exact_children(root, set(SPAWN_REPLAY_PAIR_SPECS), directories=True)
    build = _mapping(_load(repo / OBSERVER_RECEIPT), "RNG observer receipt")
    return_map = _mapping(_load(repo / RETURN_MAP), "RNG return map")
    restore_hashes = _mapping(_load(repo / RESTORE_HASHES), "restore hashes")
    controller_build = _mapping(
        _load(repo / SPAWN_REPLAY_CONTROLLER_RECEIPT),
        "spawn replay controller receipt",
    )
    controller_source = repo / "src/bridge/observatory_spawn_replay_controller.lua"
    if (
        controller_build.get("schema_version") != 1
        or controller_build.get("kind")
        != "observatory_spawn_replay_controller_build"
        or controller_build.get("controller_version")
        != "observatory-spawn-replay-controller/1"
        or controller_build.get("controller_sha256")
        != SPAWN_REPLAY_CONTROLLER_SHA256
        or controller_build.get("module_sha256")
        != SPAWN_REPLAY_CONTROLLER_SHA256
        or _file_sha256(controller_source) != SPAWN_REPLAY_CONTROLLER_SHA256
        or controller_build.get("spawner_source_sha256")
        != SPAWNER_SOURCE_SHA256
        or controller_build.get("global_source_sha256")
        != RANDOM_ELEMENT_SOURCE_SHA256
        or controller_build.get("loading_is_inert") is not True
        or controller_build.get("write_mode") != "create_only"
    ):
        raise NativeBoundaryCampaignError("spawn replay controller receipt differs")
    expected_identity = _expected_rng_identity(build)
    pairs: list[dict[str, Any]] = []

    for pair_name, spec in SPAWN_REPLAY_PAIR_SPECS.items():
        pair_dir = root / pair_name
        _exact_children(pair_dir, {"control", "replay"}, directories=True)
        control_dir = pair_dir / "control"
        replay_dir = pair_dir / "replay"
        _exact_children(control_dir, {"trial.json", "outcome.json"}, directories=False)
        _exact_children(
            replay_dir,
            {"trial.json", "outcome.json", "checkpoint.json", "spawn_replay.json"},
            directories=False,
        )
        control_trial = _mapping(_load(control_dir / "trial.json"), "control trial")
        replay_trial = _mapping(_load(replay_dir / "trial.json"), "replay trial")
        control_capture, replay_capture = spec["capture_ids"]
        pair_id = f"spawn-replay-pair-{pair_name[-3:]}"
        _validate_spawn_replay_trial(
            control_trial,
            pair_id=pair_id,
            condition="spawn_replay_control",
            capture_id=control_capture,
            outcome_path=control_dir / "outcome.json",
        )
        _validate_spawn_replay_trial(
            replay_trial,
            pair_id=pair_id,
            condition="spawn_replay",
            capture_id=replay_capture,
            outcome_path=replay_dir / "outcome.json",
            checkpoint_path=replay_dir / "checkpoint.json",
            replay_path=replay_dir / "spawn_replay.json",
        )
        order = (
            "control_then_spawn_replay"
            if _created_at(control_trial, "control trial")
            < _created_at(replay_trial, "replay trial")
            else "spawn_replay_then_control"
        )
        if order != spec["order"]:
            raise NativeBoundaryCampaignError(f"{pair_name} condition order differs")

        checkpoint = _mapping(_load(replay_dir / "checkpoint.json"), "checkpoint")
        capsule = _mapping(_load(replay_dir / "spawn_replay.json"), "replay capsule")
        replay = _validate_spawn_replay_capsule(
            capsule,
            checkpoint,
            capture_id=replay_capture,
            expected_identity=expected_identity,
            return_map=return_map,
            expected_restore_hashes=restore_hashes,
        )
        if (
            replay["selected_pawn"] != spec["selected_pawn"]
            or replay["selected_base"] != spec["selected_base"]
            or replay["native_results"] != spec["draw_results"]
            or replay["observable_pre_state_hex"]
            != spec["observable_pre_state_hex"]
        ):
            raise NativeBoundaryCampaignError(f"{pair_name} replay transcript differs")

        comparison = compare_rng_trial_outcomes(
            _mapping(_load(control_dir / "outcome.json"), "control outcome"),
            _mapping(_load(replay_dir / "outcome.json"), "replay outcome"),
            capture_id=f"spawn-replay-{pair_name}",
        )
        difference_paths = [item["path"] for item in comparison["differences"]]
        if difference_paths != spec["difference_paths"]:
            raise NativeBoundaryCampaignError(f"{pair_name} outcome scope differs")
        pairs.append(
            {
                "pair": pair_name,
                "pair_id": pair_id,
                "condition_order": order,
                "replay": replay,
                "restoration": {
                    "native_hook_bytes": True,
                    "nextpawn_wrapper": True,
                    "random_element_wrapper": True,
                    "restore_conflict": False,
                },
                "whole_game_outcome": {
                    "status": comparison["status"],
                    "difference_paths": difference_paths,
                    "control_semantic_sha256": comparison["control_semantic_sha256"],
                    "replay_semantic_sha256": comparison[
                        "exact_hook_semantic_sha256"
                    ],
                },
                "artifacts": {
                    "control_trial": _artifact(control_dir / "trial.json", repo),
                    "control_outcome": _artifact(control_dir / "outcome.json", repo),
                    "replay_trial": _artifact(replay_dir / "trial.json", repo),
                    "replay_outcome": _artifact(replay_dir / "outcome.json", repo),
                    "replay_checkpoint": _artifact(
                        replay_dir / "checkpoint.json", repo
                    ),
                    "replay_capsule": _artifact(
                        replay_dir / "spawn_replay.json", repo
                    ),
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": SPAWN_REPLAY_RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": expected_identity,
        "campaign": {
            "pair_count": len(pairs),
            "conditions": ["spawn_replay_control", "spawn_replay"],
            "condition_orders": dict(
                Counter(pair["condition_order"] for pair in pairs)
            ),
            "controller_sha256": SPAWN_REPLAY_CONTROLLER_SHA256,
            "spawner_source_sha256": SPAWNER_SOURCE_SHA256,
            "random_element_source_sha256": RANDOM_ELEMENT_SOURCE_SHA256,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "pairs": pairs,
        "results": {
            "classification": (
                "spawn_identity_replay_inputs_resolved_coordinate_rng_still_unresolved"
            ),
            "complete_verified_replays": len(pairs),
            "draw_count_per_replay": [len(pair["replay"]["native_results"]) for pair in pairs],
            "selected_pawns": [pair["replay"]["selected_pawn"] for pair in pairs],
            "observable_pre_states": [
                pair["replay"]["observable_pre_state_hex"] for pair in pairs
            ],
            "whole_game_outcomes": [
                pair["whole_game_outcome"]["status"] for pair in pairs
            ],
        },
        "claims": {
            "proven": [
                "Each of three source-verified NextPawn calls exported the exact ordered candidate array, effective weak and upgrade ratios, selected base, selected final pawn, and its enclosed native RNG results.",
                "Three consecutive MSVC rand results recover one exact observable pre-call state class; the two raw candidates differ only in permanently hidden bit 31 and produce the same future observable stream.",
                "Replaying each recovered state through weak choice, candidate modulo choice, and upgrade choice reproduces Firefly2, Scarab2, and Firefly2 exactly.",
                "Every native hook, NextPawn wrapper, and in-span random_element wrapper restored without conflict before evidence publication.",
            ],
            "not_proven": [
                "Advance prediction from ordinary solver input; the current bridge does not export this native pre-call state and candidate capsule before selection executes.",
                "Future spawn-coordinate selection, which occurs after NextPawn and produced the only paired outcome differences.",
                "Whole-game observer neutrality; fresh processes used naturally different native RNG states, so the counterbalanced controls are not RNG-state matched.",
                "The conditional boss branch in a natural live capture; it is modeled and unit-tested but none of these three calls reached its guard.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "resolved_model": (
                "MSVC observable state plus the effective NextPawn ratios and ordered "
                "candidate array are sufficient to replay ordinary pawn identity exactly"
            ),
            "runtime_rule": (
                "do not materialize a future pawn until the exact pre-call replay capsule "
                "and the still-unresolved spawn coordinate are available"
            ),
            "rust_safeguard_test": (
                "test_projection_never_fabricates_unresolved_native_spawn_selection"
            ),
            "capture_backed_test": (
                "test_committed_spawn_replay_campaign_recovers_exact_native_choices"
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(repo / OBSERVER_RECEIPT, repo),
            "controller_build_receipt": _artifact(
                repo / SPAWN_REPLAY_CONTROLLER_RECEIPT, repo
            ),
            "return_map": _artifact(repo / RETURN_MAP, repo),
            "restore_hashes": _artifact(repo / RESTORE_HASHES, repo),
        },
    }


def _validate_selected_trial(
    trial: Mapping[str, Any],
    *,
    pair_id: str,
    condition: str,
    capture_id: str,
    outcome_path: Path,
    receipt_sha256: str,
) -> None:
    if (
        trial.get("schema_version") != 1
        or trial.get("kind") != "observatory_selected_queue_turn_trial"
        or trial.get("pair_id") != pair_id
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("capture_track") != "owner_local_modified"
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
        or trial.get("module_sha256") != SELECTED_MODULE_SHA256
        or trial.get("build_receipt_sha256") != receipt_sha256
        or trial.get("scenario")
        != {
            "consumed_spawn_count": 0,
            "pawn_id": 1303,
            "pawn_type": "Firefly1",
            "start": [4, 4],
        }
    ):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial differs")
    errors = _mapping(trial.get("errors"), f"{pair_id} {condition} errors")
    if errors.get("command") or errors.get("analysis") or errors.get("outcome"):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} trial has errors")
    outcome = _mapping(trial.get("outcome"), f"{pair_id} {condition} outcome")
    if outcome.get("sha256") != _file_sha256(outcome_path):
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} outcome hash differs")
    if condition == "armed":
        if trial.get("snapshot") is None or trial.get("analysis") is None:
            raise NativeBoundaryCampaignError(f"{pair_id} armed evidence is missing")
    elif trial.get("snapshot") is not None or trial.get("analysis") is not None:
        raise NativeBoundaryCampaignError(f"{pair_id} {condition} published observer output")


def build_selected_queue_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    _exact_children(root, set(SELECTED_PAIR_SPECS), directories=True)
    build = _mapping(_load(repo / SELECTED_RECEIPT), "selected/queue build receipt")
    receipt_sha = _file_sha256(repo / SELECTED_RECEIPT)
    pairs: list[dict[str, Any]] = []

    for pair_name, spec in SELECTED_PAIR_SPECS.items():
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
            trial = _mapping(_load(condition_dir / "trial.json"), f"{pair_name} {condition} trial")
            _validate_selected_trial(
                trial,
                pair_id=f"selected-pair-{pair_name[-3:]}",
                condition=condition,
                capture_id=spec["capture_ids"][condition],
                outcome_path=condition_dir / "outcome.json",
                receipt_sha256=receipt_sha,
            )
            trials[condition] = trial
            outcomes[condition] = _mapping(
                _load(condition_dir / "outcome.json"), f"{pair_name} {condition} outcome"
            )
            artifacts[f"{condition}_trial"] = _artifact(condition_dir / "trial.json", repo)
            artifacts[f"{condition}_outcome"] = _artifact(condition_dir / "outcome.json", repo)

        actual_order = [
            condition
            for condition, _ in sorted(
                ((_condition, _created_at(trials[_condition], f"{pair_name} {_condition}"))
                 for _condition in trials),
                key=lambda item: item[1],
            )
        ]
        if actual_order != spec["order"]:
            raise NativeBoundaryCampaignError(f"{pair_name} condition order differs")

        armed_dir = pair_dir / "armed"
        snapshot = _mapping(_load(armed_dir / "snapshot.json"), f"{pair_name} snapshot")
        analysis = correlate_selected_queue_snapshot(
            snapshot,
            outcomes["armed"],
            build_receipt=build,
            observed_module_sha256=SELECTED_MODULE_SHA256,
        )
        if analysis != _load(armed_dir / "analysis.json"):
            raise NativeBoundaryCampaignError(f"{pair_name} selected/queue analysis drift")
        if analysis.get("status") != "correlated" or analysis.get("native") != SELECTED_NATIVE_EXPECTED:
            raise NativeBoundaryCampaignError(f"{pair_name} native selected/queue fields differ")
        artifacts["armed_snapshot"] = _artifact(armed_dir / "snapshot.json", repo)
        artifacts["armed_analysis"] = _artifact(armed_dir / "analysis.json", repo)

        control_dormant = compare_rng_trial_outcomes(
            outcomes["control"], outcomes["dormant"], capture_id=f"selected-{pair_name}-dormant"
        )
        control_armed = compare_rng_trial_outcomes(
            outcomes["control"], outcomes["armed"], capture_id=f"selected-{pair_name}-armed"
        )
        if control_dormant["status"] != "matched" or control_armed["status"] != "matched":
            raise NativeBoundaryCampaignError(f"{pair_name} whole-game outcomes differ")

        pairs.append(
            {
                "pair": pair_name,
                "pair_id": f"selected-pair-{pair_name[-3:]}",
                "condition_order": actual_order,
                "scenario": trials["armed"]["scenario"],
                "native": analysis["native"],
                "bridge": analysis["bridge"],
                "observer_integrity": snapshot["integrity"],
                "event_order": [record["kind"] for record in snapshot["records"]],
                "whole_game_outcome": {
                    "control_dormant": control_dormant["status"],
                    "control_armed": control_armed["status"],
                    "semantic_sha256": control_armed["control_semantic_sha256"],
                },
                "artifacts": artifacts,
            }
        )

    first_native = pairs[0]["native"]
    if any(pair["native"] != first_native for pair in pairs[1:]):
        raise NativeBoundaryCampaignError("selected/queue native transcripts do not repeat")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": SELECTED_RECEIPT_KIND,
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
                "hardware_breakpoint_plan_sha256",
                "selected_prebytes_sha256",
                "queue_prebytes_sha256",
                "module_sha256",
            )
        },
        "campaign": {
            "pair_count": len(pairs),
            "condition_order_count": len({tuple(pair["condition_order"]) for pair in pairs}),
            "conditions": ["control", "dormant", "armed"],
            "module_sha256": SELECTED_MODULE_SHA256,
        },
        "pairs": pairs,
        "results": {
            "classification": "final_selected_record_correlated_to_immediate_queue_commit",
            "complete_restored_snapshots": len(pairs),
            "records_per_armed_snapshot": [2, 2, 2],
            "event_order": ["selected_record", "queued_action"],
            "stable_native_fields": first_native,
            "all_semantic_outcomes_match": True,
        },
        "claims": {
            "proven": [
                "The reviewed final 24-byte selected-record boundary was followed immediately by one queued-action commit for the same pawn on the same thread in all three armed runs.",
                "aiDest equals queue origin, aiTarget equals both the queue target and queued shot, and current weapon equals queued skill in all three captures.",
                "Control, dormant-loaded, and armed outcomes are semantically identical in all three counterbalanced triplets.",
                "Every hardware breakpoint was cleared, the VEH was removed, the executable seam bytes were unchanged, and no executable file bytes were modified.",
            ],
            "not_proven": [
                "Universal behavior across other pawn types, multi-weapon enemies, cancellation, or retarget paths.",
                "The full native candidate tournament payload; static ordering and Lua callback streams remain the evidence for that wider boundary.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "rule": (
                "consume the bridge queue as the authoritative selected action; aiDest maps to "
                "queued origin and aiTarget maps to queued target"
            ),
            "rust_test": "test_observatory_selected_record_drives_firefly_queue_direction",
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(repo / SELECTED_RECEIPT, repo),
        },
    }


def publish_campaign_receipt(value: Mapping[str, Any], output: Path) -> tuple[Path, str]:
    path = output.resolve()
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise NativeBoundaryCampaignError(f"receipt already exists: {path}") from exc
    return path, _sha256(payload)
