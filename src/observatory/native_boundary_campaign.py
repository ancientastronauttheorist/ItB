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

from src.observatory.native_checkpoint import validate_native_checkpoint
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.selected_queue_hw import correlate_selected_queue_snapshot
from src.observatory.spawn_rng_attribution import analyze_spawn_rng


SCHEMA_VERSION = 1
SPAWN_RECEIPT_KIND = "observatory_spawn_span_campaign_receipt"
SELECTED_RECEIPT_KIND = "observatory_selected_queue_campaign_receipt"
FIXED_SEED = 324_508_639
CONTROLLER_SHA256 = "4923ee3b08c802824f17963dc625015d2c91e6e467149b72bba218c49830935d"
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
