"""Seal the atomic native-RNG Observatory campaign.

This receipt is intentionally narrower than a simulator specification.  It
binds two counterbalanced live trials to the pinned Windows build, validates
the observer's independent build and restore identities, and describes the
recorded caller/result streams.  It does not infer spawn-selection semantics
without an explicit ``Spawner:NextPawn`` span boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.callback_trial_result import validate_callback_trial_result
from src.observatory.native_checkpoint import validate_native_checkpoint
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


RECEIPT_SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_native_rng_atomic_campaign_receipt"
FIXED_SEED = 324508639
FIRST_SEEDED_RESULT = 24356
PAIR_SPECS = {
    "pair003": "exact_then_control",
    "pair004": "control_then_exact",
}
PAIR_FILES = frozenset(
    {
        "control_gameflow_result.json",
        "control_outcome.json",
        "control_trial.json",
        "exact_hook_checkpoint.json",
        "exact_hook_gameflow_result.json",
        "exact_hook_outcome.json",
        "exact_hook_trial.json",
        "outcome_comparison.json",
    }
)
REVIEWED_CALLERS = {
    19: "ai_seed_advance",
    21: "random_int_1",
    25: "random_bool_1",
    29: "candidate_loop",
    30: "record_selector",
    31: "record_selector",
}
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


class NativeRngCampaignError(RuntimeError):
    """Raised when archived native campaign evidence cannot support a claim."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeRngCampaignError(f"invalid JSON artifact {path}: {exc}") from exc


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
        raise NativeRngCampaignError(f"value is not canonical JSON: {exc}") from exc
    return (encoded + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise NativeRngCampaignError(
            f"artifact is outside the repository: {path}"
        ) from exc
    payload = path.read_bytes()
    return {
        "path": relative,
        "size": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeRngCampaignError(f"{label} must be an object")
    return value


def _expected_identity(build: Mapping[str, Any]) -> dict[str, Any]:
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


def _validate_trial(
    value: Any,
    *,
    pair_id: str,
    condition: str,
) -> dict[str, Any]:
    trial = _mapping(value, f"{pair_id} {condition} trial")
    required = {
        "schema_version",
        "kind",
        "created_at",
        "pair_id",
        "condition",
        "capture_id",
        "artifact_root",
        "session_file",
        "status",
        "valid_trial",
        "boundary",
        "auto_turn",
        "checkpoint",
        "errors",
    }
    if set(trial) != required:
        raise NativeRngCampaignError(f"{pair_id} {condition} trial fields differ")
    capture_id = f"{pair_id}-{condition.removesuffix('_hook')}"
    if (
        trial["schema_version"] != 1
        or trial["kind"] != "observatory_native_rng_turn_trial"
        or trial["pair_id"] != pair_id
        or trial["condition"] != condition
        or trial["capture_id"] != capture_id
        or trial["status"] != "complete"
        or trial["valid_trial"] is not True
    ):
        raise NativeRngCampaignError(f"{pair_id} {condition} trial is not valid")
    errors = _mapping(trial["errors"], f"{pair_id} {condition} errors")
    if set(errors) != {"runner", "abort", "checkpoint"} or any(errors.values()):
        raise NativeRngCampaignError(f"{pair_id} {condition} trial has errors")

    boundary = _mapping(trial["boundary"], f"{pair_id} {condition} boundary")
    if (
        boundary.get("condition") != condition
        or boundary.get("capture_id") != capture_id
        or boundary.get("state") != "complete"
    ):
        raise NativeRngCampaignError(f"{pair_id} {condition} boundary is incomplete")
    if condition == "control":
        if (
            boundary.get("seed_ack")
            != f"OK OBS_NATIVE_RNG_SEED seed={FIXED_SEED}"
            or boundary.get("seed_and_arm_ack") is not None
            or boundary.get("finish_ack") is not None
            or trial["checkpoint"] is not None
        ):
            raise NativeRngCampaignError(
                f"{pair_id} control did not remain an unarmed seeded run"
            )
    else:
        expected_ack = (
            f"OK OBS_NATIVE_RNG_SEED_AND_ARM capture={capture_id} seed={FIXED_SEED}"
        )
        checkpoint = _mapping(trial["checkpoint"], f"{pair_id} checkpoint summary")
        if (
            boundary.get("seed_ack") is not None
            or boundary.get("seed_and_arm_ack") != expected_ack
            or boundary.get("hook_bytes_restored") is not True
            or boundary.get("record_count") != checkpoint.get("record_count")
            or checkpoint.get("diagnostic_complete") is not True
            or checkpoint.get("hook_bytes_restored") is not True
        ):
            raise NativeRngCampaignError(
                f"{pair_id} exact boundary was not atomically armed and restored"
            )
        finish = boundary.get("finish_ack")
        expected_finish = (
            f"OK OBS_NATIVE_RNG_FINISH capture={capture_id} "
            f"records={checkpoint['record_count']} complete=true"
        )
        if finish != expected_finish:
            raise NativeRngCampaignError(f"{pair_id} exact finish ACK differs")

    auto_turn = _mapping(trial["auto_turn"], f"{pair_id} {condition} auto turn")
    if (
        auto_turn.get("status") != "ok"
        or auto_turn.get("post_phase") != "combat_player"
        or auto_turn.get("desyncs_detected") != 0
        or auto_turn.get("actions_completed") != 3
    ):
        raise NativeRngCampaignError(f"{pair_id} {condition} turn was not clean")
    auto_boundary = _mapping(
        auto_turn.get("observatory_native_rng_boundary"),
        f"{pair_id} {condition} auto boundary",
    )
    if (
        auto_boundary.get("condition") != condition
        or auto_boundary.get("capture_id") != capture_id
        or auto_boundary.get("state") != "complete"
        or auto_boundary.get("end_turn_status") != "OK"
    ):
        raise NativeRngCampaignError(
            f"{pair_id} {condition} auto-turn boundary differs"
        )
    return json.loads(json.dumps(trial))


def _runtime_identity(result: Mapping[str, Any]) -> dict[str, Any]:
    runtime = result["runtime_before"]
    return {
        field: runtime[field]
        for field in (
            "timeline_fingerprint",
            "mission_id",
            "turn",
            "master_seed",
            "region_id",
            "ai_seed_fingerprint",
        )
    }


def _condition_order(
    control: Mapping[str, Any], exact: Mapping[str, Any]
) -> str:
    control_epoch = control["runtime_before"]["now_epoch"]
    exact_epoch = exact["runtime_before"]["now_epoch"]
    if control_epoch == exact_epoch:
        raise NativeRngCampaignError("condition start epochs are identical")
    return "control_then_exact" if control_epoch < exact_epoch else "exact_then_control"


def _semantic_state(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "timestamp"}


def _difference_paths(comparison: Mapping[str, Any]) -> list[str]:
    return [item["path"] for item in comparison["differences"]]


def _longest_common_prefix(left: Sequence[Any], right: Sequence[Any]) -> int:
    count = 0
    for left_item, right_item in zip(left, right):
        if left_item != right_item:
            break
        count += 1
    return count


def _validate_pair(
    pair_dir: Path,
    *,
    repository_root: Path,
    build: Mapping[str, Any],
    return_map: Mapping[str, Any],
    restore_hashes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_order = PAIR_SPECS.get(pair_dir.name)
    if expected_order is None:
        raise NativeRngCampaignError(f"unexpected native pair {pair_dir.name}")
    actual_files = frozenset(child.name for child in pair_dir.iterdir() if child.is_file())
    if actual_files != PAIR_FILES:
        raise NativeRngCampaignError(
            f"{pair_dir.name} artifact set mismatch; "
            f"missing={sorted(PAIR_FILES - actual_files)}, "
            f"extra={sorted(actual_files - PAIR_FILES)}"
        )

    pair_id = f"owner-native-rng-atomic-{pair_dir.name.replace('pair', 'pair-')}"
    control_trial = _validate_trial(
        _load_json(pair_dir / "control_trial.json"),
        pair_id=pair_id,
        condition="control",
    )
    exact_trial = _validate_trial(
        _load_json(pair_dir / "exact_hook_trial.json"),
        pair_id=pair_id,
        condition="exact_hook",
    )
    control_gameflow = validate_callback_trial_result(
        _load_json(pair_dir / "control_gameflow_result.json"),
        expected_condition="control",
    )
    exact_gameflow = validate_callback_trial_result(
        _load_json(pair_dir / "exact_hook_gameflow_result.json"),
        expected_condition="control",
    )
    control_runtime = _runtime_identity(control_gameflow)
    exact_runtime = _runtime_identity(exact_gameflow)
    if control_runtime != exact_runtime:
        raise NativeRngCampaignError(f"{pair_dir.name} runtime identity drift")
    order = _condition_order(control_gameflow, exact_gameflow)
    if order != expected_order:
        raise NativeRngCampaignError(f"{pair_dir.name} condition order drift")

    control_outcome = _mapping(
        _load_json(pair_dir / "control_outcome.json"), "control outcome"
    )
    exact_outcome = _mapping(
        _load_json(pair_dir / "exact_hook_outcome.json"), "exact outcome"
    )
    outcome = compare_rng_trial_outcomes(
        control_outcome,
        exact_outcome,
        capture_id=pair_id,
    )
    if outcome != _load_json(pair_dir / "outcome_comparison.json"):
        raise NativeRngCampaignError(f"{pair_dir.name} outcome comparison drift")
    if (
        outcome["status"] != "mismatched"
        or outcome["difference_count"] != 2
        or _difference_paths(outcome)
        != ["/spawning_tiles/0/0", "/spawning_tiles/0/1"]
    ):
        raise NativeRngCampaignError(
            f"{pair_dir.name} has an unclassified semantic difference"
        )

    checkpoint = _mapping(
        _load_json(pair_dir / "exact_hook_checkpoint.json"), "native checkpoint"
    )
    expected_identity = _expected_identity(build)
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=restore_hashes,
    )
    if (
        verification["diagnostic_complete"] is not True
        or checkpoint["capture_id"] != exact_trial["capture_id"]
        or checkpoint["summary"]["thread_count"] != 1
        or checkpoint["summary"]["record_count"]
        != exact_trial["checkpoint"]["record_count"]
        or checkpoint["records"][0]["result"] != FIRST_SEEDED_RESULT
    ):
        raise NativeRngCampaignError(f"{pair_dir.name} checkpoint is incomplete")
    checkpoint_digest = _sha256_bytes(
        (pair_dir / "exact_hook_checkpoint.json").read_bytes()
    )
    if checkpoint_digest != exact_trial["checkpoint"]["sha256"]:
        raise NativeRngCampaignError(f"{pair_dir.name} checkpoint digest drift")

    caller_counts = Counter(record["caller_id"] for record in checkpoint["records"])
    if not set(REVIEWED_CALLERS) <= set(caller_counts):
        raise NativeRngCampaignError(f"{pair_dir.name} lacks reviewed native callers")
    artifacts = {
        name.removesuffix(".json"): _artifact(pair_dir / name, repository_root)
        for name in sorted(PAIR_FILES)
    }
    pair_receipt = {
        "pair": pair_dir.name,
        "pair_id": pair_id,
        "condition_order": order,
        "runtime_identity": control_runtime,
        "turn_execution": {
            "control_actions": control_trial["auto_turn"]["actions_completed"],
            "exact_actions": exact_trial["auto_turn"]["actions_completed"],
            "desyncs": 0,
        },
        "atomic_boundary": {
            "fixed_seed": FIXED_SEED,
            "seed_and_arm_ack": exact_trial["boundary"]["seed_and_arm_ack"],
            "first_recorded_result": checkpoint["records"][0]["result"],
            "record_count": checkpoint["summary"]["record_count"],
            "thread_count": checkpoint["summary"]["thread_count"],
            "diagnostic_complete": True,
            "hook_bytes_restored": True,
            "unknown_caller_count": checkpoint["integrity"][
                "unknown_caller_count"
            ],
            "restore_conflict": checkpoint["integrity"]["restore_conflict"],
        },
        "reviewed_caller_counts": {
            str(caller_id): caller_counts[caller_id]
            for caller_id in sorted(REVIEWED_CALLERS)
        },
        "whole_game_outcome": {
            "status": outcome["status"],
            "differences": outcome["differences"],
            "control_semantic_sha256": outcome["control_semantic_sha256"],
            "exact_semantic_sha256": outcome["exact_hook_semantic_sha256"],
        },
        "artifacts": artifacts,
    }
    analysis_inputs = {
        "checkpoint": checkpoint,
        "control_outcome": dict(control_outcome),
        "exact_outcome": dict(exact_outcome),
    }
    return pair_receipt, analysis_inputs


def _caller_analysis(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for caller_id, source_region in REVIEWED_CALLERS.items():
        left_records = [
            item for item in left["records"] if item["caller_id"] == caller_id
        ]
        right_records = [
            item for item in right["records"] if item["caller_id"] == caller_id
        ]
        left_values = [item["result"] for item in left_records]
        right_values = [item["result"] for item in right_records]
        result.append(
            {
                "caller_id": caller_id,
                "source_region": source_region,
                "pair003_count": len(left_records),
                "pair004_count": len(right_records),
                "pair003_first_sequence": left_records[0]["seq"],
                "pair004_first_sequence": right_records[0]["seq"],
                "result_sequences_equal": left_values == right_values,
                "pair003_results_sha256": _canonical_sha256(left_values),
                "pair004_results_sha256": _canonical_sha256(right_values),
            }
        )
    return result


def build_native_rng_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate both archived atomic pairs and return a deterministic receipt."""
    campaign_root = Path(campaign_root)
    repository_root = Path(repository_root)
    actual_dirs = tuple(
        sorted(child.name for child in campaign_root.iterdir() if child.is_dir())
    )
    if actual_dirs != tuple(PAIR_SPECS):
        raise NativeRngCampaignError(
            f"native pair set mismatch: expected {tuple(PAIR_SPECS)}, found {actual_dirs}"
        )

    build_path = repository_root / OBSERVER_RECEIPT
    return_map_path = repository_root / RETURN_MAP
    restore_path = repository_root / RESTORE_HASHES
    build = _mapping(_load_json(build_path), "observer build receipt")
    return_map = _mapping(_load_json(return_map_path), "RNG return map")
    restore_hashes = _mapping(_load_json(restore_path), "restore hashes")
    expected_sources = {
        caller["caller_id"]: caller["classification"].get("source_region")
        for caller in return_map["callers"]
        if caller["caller_id"] in REVIEWED_CALLERS
    }
    if expected_sources != REVIEWED_CALLERS:
        raise NativeRngCampaignError("reviewed caller catalog drift")

    pairs: list[dict[str, Any]] = []
    inputs: dict[str, dict[str, Any]] = {}
    runtime_identity: dict[str, Any] | None = None
    for pair_name in PAIR_SPECS:
        pair, current_inputs = _validate_pair(
            campaign_root / pair_name,
            repository_root=repository_root,
            build=build,
            return_map=return_map,
            restore_hashes=restore_hashes,
        )
        if runtime_identity is None:
            runtime_identity = pair["runtime_identity"]
        elif runtime_identity != pair["runtime_identity"]:
            raise NativeRngCampaignError("campaign runtime identity drift")
        pairs.append(pair)
        inputs[pair_name] = current_inputs
    assert runtime_identity is not None

    left = inputs["pair003"]["checkpoint"]
    right = inputs["pair004"]["checkpoint"]
    left_results = [record["result"] for record in left["records"]]
    right_results = [record["result"] for record in right["records"]]
    left_tuples = [
        (record["caller_id"], record["result"]) for record in left["records"]
    ]
    right_tuples = [
        (record["caller_id"], record["result"]) for record in right["records"]
    ]
    result_prefix = _longest_common_prefix(left_results, right_results)
    tuple_prefix = _longest_common_prefix(left_tuples, right_tuples)

    exact_repeat = compare_rng_trial_outcomes(
        inputs["pair003"]["exact_outcome"],
        inputs["pair004"]["exact_outcome"],
        capture_id="native-rng-atomic-exact-repeat",
    )
    control_repeat = compare_rng_trial_outcomes(
        inputs["pair003"]["control_outcome"],
        inputs["pair004"]["control_outcome"],
        capture_id="native-rng-atomic-control-repeat",
    )
    if exact_repeat["status"] != "matched":
        raise NativeRngCampaignError("exact atomic outcomes do not repeat")
    if (
        control_repeat["status"] != "mismatched"
        or _difference_paths(control_repeat)
        != ["/spawning_tiles/0/1"]
    ):
        raise NativeRngCampaignError("control outcome difference is unclassified")
    if result_prefix != 104 or tuple_prefix != 0:
        raise NativeRngCampaignError("atomic repeat stream boundary drift")

    caller_analysis = _caller_analysis(left, right)
    stable_reviewed = [
        item["caller_id"]
        for item in caller_analysis
        if item["result_sequences_equal"]
    ]
    if stable_reviewed != [19, 29, 30, 31]:
        raise NativeRngCampaignError("reviewed caller repeat classification drift")

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": _expected_identity(build),
        "runtime_identity": runtime_identity,
        "campaign": {
            "pair_count": 2,
            "condition_orders": {
                "control_then_exact": 1,
                "exact_then_control": 1,
            },
            "fixed_seed": FIXED_SEED,
            "atomic_command": "OBS_NATIVE_RNG_SEED_AND_ARM",
            "observer_version": build["observer_version"],
        },
        "results": {
            "complete_restored_checkpoints": 2,
            "first_seeded_result": FIRST_SEEDED_RESULT,
            "exact_record_counts": [
                left["summary"]["record_count"],
                right["summary"]["record_count"],
            ],
            "exact_result_stream_common_prefix": result_prefix,
            "exact_caller_result_common_prefix": tuple_prefix,
            "exact_outcomes_repeat": True,
            "control_outcomes_repeat": False,
            "within_pair_mismatch_scope": [
                "/spawning_tiles/0/0",
                "/spawning_tiles/0/1",
            ],
            "control_repeat_mismatch_scope": _difference_paths(control_repeat),
            "reviewed_callers": caller_analysis,
            "stable_reviewed_result_sequences": stable_reviewed,
            "classification": "restored_native_stream_observation_not_spawn_semantics",
        },
        "claims": {
            "proven": [
                "Atomic seed-and-arm captured the fixed seed's first native RNG result in both exact runs.",
                "Both native checkpoints are build-bound, complete, single-threaded, free of unknown callers, and report byte-exact RNG-core restoration without conflict.",
                "Reviewed direct callers for random_int, random_bool, candidate tie-breaking, record selection, and AI seed advance executed in both captures.",
                "The candidate-loop, record-selector, and AI-seed-advance caller result subsequences repeated across the two exact captures.",
                "The two exact observed outcomes repeated, while the two unobserved controls from the same save and fixed seed selected different spawn coordinates.",
            ],
            "not_proven": [
                "Whole-game neutrality of the native observer.",
                "A deterministic linear native RNG call order from save state and fixed seed alone.",
                "Which RNG draws belong to Spawner:NextPawn; no native span markers were installed.",
                "Native spawn-selection, final enemy-action selection, or candidate tournament semantics.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "solver_safeguard": {
            "rule": "consume observed spawn markers but never fabricate an unknown pawn identity or replacement spawn coordinate",
            "rust_test": "test_projection_never_fabricates_unresolved_native_spawn_selection",
        },
        "supporting_artifacts": {
            "observer_build_receipt": _artifact(build_path, repository_root),
            "rng_return_map": _artifact(return_map_path, repository_root),
            "restore_hashes": _artifact(restore_path, repository_root),
        },
        "pairs": pairs,
        "restore": {
            "save_tree_sha256": runtime_identity["timeline_fingerprint"],
            "save_restoration_pending": True,
            "install_restoration_pending": True,
        },
    }


def publish_native_rng_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
    output: Path,
) -> tuple[Path, str]:
    """Create one immutable native campaign receipt."""
    receipt = build_native_rng_campaign_receipt(
        campaign_root,
        repository_root=repository_root,
    )
    payload = _canonical_bytes(receipt)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise NativeRngCampaignError(f"receipt already exists: {output}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return output, _sha256_bytes(payload)
