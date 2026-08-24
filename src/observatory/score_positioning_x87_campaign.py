"""Seal the counterbalanced ScorePositioning x87 runtime campaign."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.score_positioning_x87 import (
    ANALYSIS_KIND,
    EXPECTED_MODULE_SHA256,
    analyze_score_positioning_x87_snapshot,
)


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_score_positioning_x87_campaign_receipt"
BUILD_RECEIPT = Path("data/observatory/native") / (
    "itb_observatory_score_positioning_x87_observer_"
    f"{EXPECTED_MODULE_SHA256}.dll.receipt.json"
)
SAVE_TREE_SHA256 = (
    "ca305830ca471c3d5f1501bb8750a7d076283752bde39a66f637717e7f04eae5"
)
EXPECTED_SCENARIO = {
    "consumed_spawn_count": 0,
    "pawn_id": 1303,
    "pawn_type": "Firefly1",
    "start": [4, 4],
}
EXPECTED_ROUNDING_MODE = "nearest_even"
EXPECTED_CONTROL_WORD = 0x027F
PAIR_SPECS = {
    "pair001": ["control", "dormant", "armed"],
    "pair002": ["armed", "control", "dormant"],
    "pair003": ["dormant", "armed", "control"],
}


class ScorePositioningX87CampaignError(RuntimeError):
    """Raised when runtime campaign evidence is missing or inconsistent."""


def _stable_bytes(path: Path, label: str) -> bytes:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise ScorePositioningX87CampaignError(
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
        raise ScorePositioningX87CampaignError(f"{label} changed while read")
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


def _load(path: Path, label: str) -> dict[str, Any]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScorePositioningX87CampaignError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ScorePositioningX87CampaignError(f"{label} must be an object")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ScorePositioningX87CampaignError(f"{label} must be an object")
    return value


def _exact_children(root: Path, expected: set[str], *, directories: bool) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ScorePositioningX87CampaignError(f"campaign path is invalid: {root}")
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
        raise ScorePositioningX87CampaignError(
            f"campaign children differ at {root}"
        )


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    repo = repository_root.resolve()
    try:
        relative = resolved.relative_to(repo).as_posix()
    except ValueError as exc:
        raise ScorePositioningX87CampaignError(
            f"campaign artifact is outside the repository: {resolved}"
        ) from exc
    data = _stable_bytes(resolved, relative)
    return {"path": relative, "sha256": _sha256(data), "size": len(data)}


def _created_at(trial: Mapping[str, Any], label: str) -> datetime:
    value = trial.get("created_at")
    if type(value) is not str:
        raise ScorePositioningX87CampaignError(f"{label} created_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScorePositioningX87CampaignError(
            f"{label} created_at is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise ScorePositioningX87CampaignError(
            f"{label} created_at has no timezone"
        )
    return parsed


def _validate_trial(
    trial: Mapping[str, Any],
    *,
    pair_name: str,
    condition: str,
    outcome_path: Path,
    receipt_sha256: str,
) -> None:
    suffix = pair_name[-3:]
    capture_id = f"score-x87-pair-{suffix}-{condition}"
    expected_boundary = (
        {
            "record_count": 1,
            "rounding_mode": EXPECTED_ROUNDING_MODE,
            "control_word": EXPECTED_CONTROL_WORD,
        }
        if condition == "armed"
        else {
            "record_count": 0,
            "rounding_mode": "unobserved",
            "control_word": 0,
        }
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind")
        != "observatory_score_positioning_x87_turn_trial"
        or trial.get("pair_id") != f"score-x87-pair-{suffix}"
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("capture_track") != "owner_local_modified"
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
        or trial.get("module_sha256") != EXPECTED_MODULE_SHA256
        or trial.get("build_receipt_sha256") != receipt_sha256
        or trial.get("scenario") != EXPECTED_SCENARIO
        or trial.get("boundary") != expected_boundary
    ):
        raise ScorePositioningX87CampaignError(
            f"{pair_name} {condition} trial differs"
        )
    errors = _mapping(trial.get("errors"), f"{pair_name} {condition} errors")
    if errors.get("command") or errors.get("analysis") or errors.get("outcome"):
        raise ScorePositioningX87CampaignError(
            f"{pair_name} {condition} trial has errors"
        )
    outcome = _mapping(
        trial.get("outcome"), f"{pair_name} {condition} outcome metadata"
    )
    if outcome.get("sha256") != _sha256(
        _stable_bytes(outcome_path, f"{pair_name} {condition} outcome")
    ):
        raise ScorePositioningX87CampaignError(
            f"{pair_name} {condition} outcome digest differs"
        )
    if condition == "armed":
        snapshot = _mapping(
            trial.get("snapshot"), f"{pair_name} snapshot metadata"
        )
        analysis = _mapping(
            trial.get("analysis"), f"{pair_name} analysis metadata"
        )
        if (
            snapshot.get("record_count") != 1
            or snapshot.get("complete") is not True
            or analysis.get("kind") != ANALYSIS_KIND
            or analysis.get("rounding_mode") != EXPECTED_ROUNDING_MODE
        ):
            raise ScorePositioningX87CampaignError(
                f"{pair_name} armed evidence is incomplete"
            )
    elif trial.get("snapshot") is not None or trial.get("analysis") is not None:
        raise ScorePositioningX87CampaignError(
            f"{pair_name} {condition} published observer output"
        )


def build_score_positioning_x87_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate three counterbalanced triplets and return their receipt."""
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    _exact_children(root, set(PAIR_SPECS), directories=True)
    build_path = repo / BUILD_RECEIPT
    build = _load(build_path, "x87 build receipt")
    receipt_sha256 = _sha256(_stable_bytes(build_path, "x87 build receipt"))
    if build.get("module_sha256") != EXPECTED_MODULE_SHA256:
        raise ScorePositioningX87CampaignError("x87 build receipt module differs")

    pairs: list[dict[str, Any]] = []
    semantic_sha256: str | None = None
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
                outcome_path=condition_dir / "outcome.json",
                receipt_sha256=receipt_sha256,
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
            raise ScorePositioningX87CampaignError(
                f"{pair_name} condition order differs"
            )

        armed_dir = pair_dir / "armed"
        snapshot = _load(armed_dir / "snapshot.json", f"{pair_name} snapshot")
        analysis = analyze_score_positioning_x87_snapshot(
            snapshot,
            build_receipt=build,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )
        committed_analysis = _load(
            armed_dir / "analysis.json", f"{pair_name} analysis"
        )
        if analysis != committed_analysis:
            raise ScorePositioningX87CampaignError(
                f"{pair_name} x87 analysis drift"
            )
        observation = _mapping(
            analysis.get("observation"), f"{pair_name} observation"
        )
        if (
            observation.get("rounding_mode") != EXPECTED_ROUNDING_MODE
            or observation.get("control_word") != EXPECTED_CONTROL_WORD
        ):
            raise ScorePositioningX87CampaignError(
                f"{pair_name} x87 mode or control word differs"
            )
        artifacts["armed_snapshot"] = _artifact(
            armed_dir / "snapshot.json", repo
        )
        artifacts["armed_analysis"] = _artifact(
            armed_dir / "analysis.json", repo
        )

        comparisons = {
            "control_dormant": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["dormant"],
                capture_id=f"score-x87-{pair_name}-dormant",
            ),
            "control_armed": compare_rng_trial_outcomes(
                outcomes["control"],
                outcomes["armed"],
                capture_id=f"score-x87-{pair_name}-armed",
            ),
        }
        if any(item["status"] != "matched" for item in comparisons.values()):
            raise ScorePositioningX87CampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        pair_semantic = comparisons["control_armed"]["control_semantic_sha256"]
        if semantic_sha256 is None:
            semantic_sha256 = pair_semantic
        elif pair_semantic != semantic_sha256:
            raise ScorePositioningX87CampaignError(
                f"{pair_name} fixed scenario outcome differs"
            )
        integrity = _mapping(snapshot.get("integrity"), f"{pair_name} integrity")
        pairs.append(
            {
                "pair": pair_name,
                "pair_id": f"score-x87-pair-{pair_name[-3:]}",
                "condition_order": actual_order,
                "scenario": EXPECTED_SCENARIO,
                "observation": {
                    "control_word": observation["control_word"],
                    "rounding_control_bits": observation[
                        "rounding_control_bits"
                    ],
                    "rounding_mode": observation["rounding_mode"],
                    "boundary": observation["boundary"],
                    "frame_chain": observation["frame_chain"],
                },
                "observer_integrity": {
                    field: integrity[field]
                    for field in (
                        "state",
                        "complete",
                        "debug_registers_cleared",
                        "veh_removed",
                        "executable_file_released",
                        "lua_file_released",
                        "executable_bytes_modified",
                        "seams_unchanged",
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
                "lua_dll_sha256",
                "lua_dll_size",
                "inventory_canonical_sha256",
                "boundary_map_canonical_sha256",
                "hardware_breakpoint_plan_sha256",
                "module_sha256",
            )
        },
        "campaign": {
            "pair_count": len(pairs),
            "conditions": ["control", "dormant", "armed"],
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fixed_seed": 324508639,
            "save_tree_sha256": SAVE_TREE_SHA256,
            "scenario": EXPECTED_SCENARIO,
        },
        "pairs": pairs,
        "results": {
            "classification": "score_positioning_x87_rounding_mode_resolved",
            "complete_restored_snapshots": len(pairs),
            "records_per_armed_snapshot": [1, 1, 1],
            "control_words": [EXPECTED_CONTROL_WORD] * len(pairs),
            "rounding_modes": [EXPECTED_ROUNDING_MODE] * len(pairs),
            "stable_control_word": EXPECTED_CONTROL_WORD,
            "stable_rounding_mode": EXPECTED_ROUNDING_MODE,
            "all_semantic_outcomes_match": True,
            "semantic_sha256": semantic_sha256,
        },
        "claims": {
            "proven": [
                "All three exact ScorePositioning lua_tointeger conversions used x87 control word 0x027F, whose rounding-control bits select round-to-nearest-even.",
                "Control, dormant-loaded, and armed whole-game outcomes were semantically identical in all three counterbalanced triplets.",
                "Every one-shot observer cleared its debug register, removed its vectored exception handler, released both pinned files, retained both image seams, and modified no executable bytes.",
            ],
            "not_proven": [
                "That every future process or non-ScorePositioning Lua integer conversion uses the same x87 control word.",
                "A complete native enemy tournament replay; this campaign resolves only ScorePositioning's native integer-conversion mode.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "Convert half-integer ScorePositioning results with signed "
                "round-to-nearest-even for this exact Windows build"
            ),
            "offline_model": (
                "src.observatory.enemy_score_positioning_semantics."
                "replay_score_positioning_native_integer"
            ),
            "capture_backed_test": (
                "test_committed_x87_campaign_selects_nearest_even_replay"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator does not fabricate the unresolved native "
                "candidate tournament or execute ScorePositioning; the "
                "authoritative settled enemy queue remains its input."
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(build_path, repo),
        },
    }


def publish_score_positioning_x87_campaign_receipt(
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
        raise ScorePositioningX87CampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
