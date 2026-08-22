"""Seal the matched natural callback Observatory campaign.

The archived pairs exercise one callback family at a time through a complete
enemy decision cycle.  The receipt proves invocation, bounded serialization,
and slot restoration.  Whole-game outcome equality remains a separate claim,
especially for the repeated ``GetSkillEffect`` pair whose only observed
difference was the following spawn marker.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.callback_trial_result import (
    compare_callback_trial_results,
    validate_callback_trial_result,
)
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


RECEIPT_SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_natural_callback_campaign_receipt"
PAIR_SPECS = {
    "score_positioning_pair002": {
        "family": "score_positioning",
        "order": "control_then_exact",
        "attempted": 100,
        "accepted": 100,
        "outcome": "matched",
    },
    "get_target_area_pair001": {
        "family": "get_target_area",
        "order": "control_then_exact",
        "attempted": 47,
        "accepted": 47,
        "outcome": "matched",
    },
    "enemy_target_score_pair001": {
        "family": "enemy_target_score",
        "order": "control_then_exact",
        "attempted": 181,
        "accepted": 181,
        "outcome": "matched",
    },
    "get_skill_effect_pair002": {
        "family": "get_skill_effect",
        "order": "control_then_exact",
        "attempted": 147,
        "accepted": 146,
        "outcome": "mismatched",
    },
    "get_skill_effect_pair003": {
        "family": "get_skill_effect",
        "order": "exact_then_control",
        "attempted": 147,
        "accepted": 146,
        "outcome": "mismatched",
    },
}
PAIR_FILES = frozenset(
    {
        "capture_identity.json",
        "control_outcome.json",
        "control_result.json",
        "exact_hook_outcome.json",
        "exact_hook_result.json",
        "exact_hook_trace.json",
        "outcome_comparison.json",
        "pair_plan.json",
        "result_comparison.json",
    }
)
INVENTORY = Path(
    "data/observatory/inventories/"
    "windows_build_13725832_31fe35265598_local_modified.json"
)
CALLBACK_BINDINGS = Path(
    "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822T025049Z_"
    "callback_bindings_live_slot_update.json"
)
CALLBACK_JOIN = Path(
    "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260821T201929Z_callback_join.json"
)


class CallbackCampaignReceiptError(RuntimeError):
    """Raised when natural callback evidence is incomplete or inconsistent."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CallbackCampaignReceiptError(f"invalid JSON artifact {path}: {exc}") from exc


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
        raise CallbackCampaignReceiptError(
            f"receipt is not canonical JSON: {exc}"
        ) from exc
    return (encoded + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise CallbackCampaignReceiptError(
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
        raise CallbackCampaignReceiptError(f"{label} must be an object")
    return value


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


def _condition_order(control: Mapping[str, Any], exact: Mapping[str, Any]) -> str:
    left = control["runtime_before"]["now_epoch"]
    right = exact["runtime_before"]["now_epoch"]
    if left == right:
        raise CallbackCampaignReceiptError("paired condition epochs are identical")
    return "control_then_exact" if left < right else "exact_then_control"


def _difference_paths(comparison: Mapping[str, Any]) -> list[str]:
    return [item["path"] for item in comparison["differences"]]


def _validate_capture_identity(
    identity: Mapping[str, Any],
    *,
    capture_id: str,
    runtime_identity: Mapping[str, Any],
) -> None:
    required = {
        "activated_at_utc",
        "ai_seed_fingerprint",
        "arm_nonce",
        "capture_id",
        "config_sha256",
        "controller_sha256",
        "controller_version",
        "expected_mission_id",
        "expected_phase",
        "expected_turn",
        "expires_at_utc",
        "hook_coverage_sha256",
        "installed_modloader_sha256",
        "master_seed",
        "region_id",
        "timeline_fingerprint",
    }
    if set(identity) != required:
        raise CallbackCampaignReceiptError("capture identity fields differ")
    expected = {
        "capture_id": capture_id,
        "expected_mission_id": runtime_identity["mission_id"],
        "expected_phase": "combat_enemy",
        "expected_turn": runtime_identity["turn"],
        "master_seed": runtime_identity["master_seed"],
        "region_id": runtime_identity["region_id"],
        "timeline_fingerprint": runtime_identity["timeline_fingerprint"],
        "ai_seed_fingerprint": runtime_identity["ai_seed_fingerprint"],
    }
    if any(identity.get(field) != value for field, value in expected.items()):
        raise CallbackCampaignReceiptError("capture identity does not bind runtime")
    if identity["controller_version"] != "observatory-callback-controller/1":
        raise CallbackCampaignReceiptError("callback controller version differs")


def _validate_raw_trace(
    raw: Mapping[str, Any],
    *,
    family: str,
    exact: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        raw.get("capture_id") != exact["capture_id"]
        or raw.get("timeline_fingerprint")
        != exact["runtime_before"]["timeline_fingerprint"]
        or raw.get("master_seed") != exact["runtime_before"]["master_seed"]
        or raw.get("ai_seed_fingerprint")
        != exact["runtime_before"]["ai_seed_fingerprint"]
        or raw.get("expected_mission_id") != exact["runtime_before"]["mission_id"]
        or raw.get("expected_turn") != exact["runtime_before"]["turn"]
        or raw.get("checkpoint_seq") != exact["checkpoint_seq"]
    ):
        raise CallbackCampaignReceiptError("raw callback identity drift")
    events = raw.get("events")
    if not isinstance(events, list) or len(events) != exact["raw_event_count"]:
        raise CallbackCampaignReceiptError("raw callback event count differs")
    for index, event in enumerate(events):
        if (
            not isinstance(event, Mapping)
            or event.get("seq") != index
            or event.get("kind") != family
            or event.get("mission_id") != exact["runtime_before"]["mission_id"]
            or event.get("turn") != exact["runtime_before"]["turn"]
            or event.get("phase") != "combat_enemy"
            or not isinstance(event.get("context"), Mapping)
            or not isinstance(event.get("payload"), Mapping)
        ):
            raise CallbackCampaignReceiptError("raw callback event stream differs")
    attempted = _mapping(raw.get("attempted_calls"), "raw attempted calls")
    if (
        attempted.get(family) != exact["attempted_calls"]
        or any(value != (exact["attempted_calls"] if key == family else 0)
               for key, value in attempted.items())
    ):
        raise CallbackCampaignReceiptError("raw callback attempted calls differ")
    summary = _mapping(raw.get("summary"), "raw callback summary")
    dropped = exact["attempted_calls"] - exact["raw_event_count"]
    if (
        summary.get("accepted_events") != exact["raw_event_count"]
        or summary.get("dropped_events") != dropped
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
    ):
        raise CallbackCampaignReceiptError("raw callback summary differs")
    if dropped == 0:
        if summary.get("stop_reasons") != [] or summary.get("truncation_reasons") != []:
            raise CallbackCampaignReceiptError("complete raw callback reports truncation")
    elif dropped == 1:
        reason = {"max_total_event_bytes": 1}
        if (
            summary.get("stop_reasons") != reason
            or summary.get("truncation_reasons") != reason
        ):
            raise CallbackCampaignReceiptError("bounded trace truncation differs")
    else:
        raise CallbackCampaignReceiptError("unexpected callback drop count")
    return {
        "attempted_calls": exact["attempted_calls"],
        "accepted_events": exact["raw_event_count"],
        "dropped_events": dropped,
        "events_sha256": _canonical_sha256(events),
        "build_identity_sha256": raw.get("build_identity_sha256"),
        "installed_modloader_sha256": raw.get("installed_modloader_sha256"),
    }


def _validate_pair(
    pair_dir: Path,
    *,
    repository_root: Path,
    spec: Mapping[str, Any],
    inventory_sha256: str,
    bindings_sha256: str,
    callback_join_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    actual_files = frozenset(child.name for child in pair_dir.iterdir() if child.is_file())
    if actual_files != PAIR_FILES:
        raise CallbackCampaignReceiptError(
            f"{pair_dir.name} artifact set mismatch; "
            f"missing={sorted(PAIR_FILES - actual_files)}, "
            f"extra={sorted(actual_files - PAIR_FILES)}"
        )
    plan = _mapping(_load_json(pair_dir / "pair_plan.json"), "pair plan")
    capture_id = plan.get("capture_id")
    family = spec["family"]
    if (
        plan.get("schema_version") != 1
        or plan.get("kind") != "observatory_callback_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("callback_family") != family
        or plan.get("conditions") != ["control", "exact_hook"]
        or not isinstance(capture_id, str)
    ):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} plan identity differs")
    plan_artifacts = _mapping(plan.get("artifacts"), "pair plan artifacts")
    if (
        plan_artifacts["inventory"]["sha256"] != inventory_sha256
        or plan_artifacts["bindings"]["sha256"] != bindings_sha256
        or plan_artifacts["callback_join"]["sha256"] != callback_join_sha256
    ):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} build binding differs")

    control = validate_callback_trial_result(
        _load_json(pair_dir / "control_result.json"),
        expected_condition="control",
    )
    exact = validate_callback_trial_result(
        _load_json(pair_dir / "exact_hook_result.json"),
        expected_condition="exact_hook",
    )
    if (
        control["capture_id"] != capture_id
        or exact["capture_id"] != capture_id
        or control["callback_family"] != family
        or exact["callback_family"] != family
    ):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} result identity differs")
    direct = compare_callback_trial_results(
        control,
        exact,
        expected_capsule_sha256=exact["capsule_sha256"],
        expected_arm_packet_sha256=exact["arm_packet_sha256"],
    )
    if direct != _load_json(pair_dir / "result_comparison.json"):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} result comparison drift")
    if (
        exact["attempted_calls"] != spec["attempted"]
        or exact["raw_event_count"] != spec["accepted"]
    ):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} callback count drift")
    order = _condition_order(control, exact)
    if order != spec["order"]:
        raise CallbackCampaignReceiptError(f"{pair_dir.name} condition order drift")

    runtime_identity = _runtime_identity(control)
    identity = _mapping(
        _load_json(pair_dir / "capture_identity.json"), "capture identity"
    )
    _validate_capture_identity(
        identity,
        capture_id=capture_id,
        runtime_identity=runtime_identity,
    )
    if (
        _sha256_bytes((pair_dir / "capture_identity.json").read_bytes())
        != plan_artifacts["capture_identity"]["sha256"]
        or exact["capsule_sha256"] != plan_artifacts["capsule"]["sha256"]
        or exact["arm_packet_sha256"] != plan_artifacts["arm_packet"]["sha256"]
    ):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} artifact binding drift")

    raw = _mapping(_load_json(pair_dir / "exact_hook_trace.json"), "raw trace")
    raw_summary = _validate_raw_trace(raw, family=family, exact=exact)
    if raw_summary["installed_modloader_sha256"] != identity[
        "installed_modloader_sha256"
    ]:
        raise CallbackCampaignReceiptError(f"{pair_dir.name} loader identity drift")

    control_outcome = _mapping(
        _load_json(pair_dir / "control_outcome.json"), "control outcome"
    )
    exact_outcome = _mapping(
        _load_json(pair_dir / "exact_hook_outcome.json"), "exact outcome"
    )
    outcome = compare_rng_trial_outcomes(
        control_outcome,
        exact_outcome,
        capture_id=capture_id,
    )
    if outcome != _load_json(pair_dir / "outcome_comparison.json"):
        raise CallbackCampaignReceiptError(f"{pair_dir.name} outcome comparison drift")
    if outcome["status"] != spec["outcome"]:
        raise CallbackCampaignReceiptError(f"{pair_dir.name} outcome status drift")
    if outcome["status"] == "mismatched" and _difference_paths(outcome) != [
        "/spawning_tiles/0/0",
        "/spawning_tiles/0/1",
    ]:
        raise CallbackCampaignReceiptError(
            f"{pair_dir.name} has an unclassified outcome difference"
        )

    artifacts = {
        name.removesuffix(".json"): _artifact(pair_dir / name, repository_root)
        for name in sorted(PAIR_FILES)
    }
    pair_receipt = {
        "pair": pair_dir.name,
        "capture_id": capture_id,
        "callback_family": family,
        "condition_order": order,
        "runtime_identity": runtime_identity,
        "slot_count": exact["slot_count"],
        "both_restored": direct["both_restored"],
        "trace": raw_summary,
        "whole_game_outcome": {
            "status": outcome["status"],
            "difference_count": outcome["difference_count"],
            "differences": outcome["differences"],
            "control_semantic_sha256": outcome["control_semantic_sha256"],
            "exact_semantic_sha256": outcome["exact_hook_semantic_sha256"],
        },
        "artifacts": artifacts,
    }
    inputs = {
        "control_outcome": dict(control_outcome),
        "exact_outcome": dict(exact_outcome),
        "events": raw["events"],
    }
    return pair_receipt, inputs


def build_callback_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate all archived natural callback pairs."""
    campaign_root = Path(campaign_root)
    repository_root = Path(repository_root)
    actual_dirs = {child.name for child in campaign_root.iterdir() if child.is_dir()}
    if actual_dirs != set(PAIR_SPECS):
        raise CallbackCampaignReceiptError(
            f"callback pair set mismatch; missing={sorted(set(PAIR_SPECS)-actual_dirs)}, "
            f"extra={sorted(actual_dirs-set(PAIR_SPECS))}"
        )

    inventory_path = repository_root / INVENTORY
    bindings_path = repository_root / CALLBACK_BINDINGS
    callback_join_path = repository_root / CALLBACK_JOIN
    inventory_sha256 = _sha256_bytes(inventory_path.read_bytes())
    bindings_sha256 = _sha256_bytes(bindings_path.read_bytes())
    callback_join_sha256 = _sha256_bytes(callback_join_path.read_bytes())

    pairs: list[dict[str, Any]] = []
    inputs: dict[str, dict[str, Any]] = {}
    runtime_identity: dict[str, Any] | None = None
    build_identity_sha256: str | None = None
    installed_modloader_sha256: str | None = None
    for name, spec in PAIR_SPECS.items():
        pair, current_inputs = _validate_pair(
            campaign_root / name,
            repository_root=repository_root,
            spec=spec,
            inventory_sha256=inventory_sha256,
            bindings_sha256=bindings_sha256,
            callback_join_sha256=callback_join_sha256,
        )
        if runtime_identity is None:
            runtime_identity = pair["runtime_identity"]
            build_identity_sha256 = pair["trace"]["build_identity_sha256"]
            installed_modloader_sha256 = pair["trace"][
                "installed_modloader_sha256"
            ]
        elif (
            pair["runtime_identity"] != runtime_identity
            or pair["trace"]["build_identity_sha256"] != build_identity_sha256
            or pair["trace"]["installed_modloader_sha256"]
            != installed_modloader_sha256
        ):
            raise CallbackCampaignReceiptError("callback campaign identity drift")
        pairs.append(pair)
        inputs[name] = current_inputs
    assert runtime_identity is not None
    assert build_identity_sha256 is not None
    assert installed_modloader_sha256 is not None

    effect_left = inputs["get_skill_effect_pair002"]
    effect_right = inputs["get_skill_effect_pair003"]
    effect_control_repeat = compare_rng_trial_outcomes(
        effect_left["control_outcome"],
        effect_right["control_outcome"],
        capture_id="callback-get-skill-effect-control-repeat",
    )
    effect_exact_repeat = compare_rng_trial_outcomes(
        effect_left["exact_outcome"],
        effect_right["exact_outcome"],
        capture_id="callback-get-skill-effect-exact-repeat",
    )
    effect_events_repeat = _canonical_sha256(effect_left["events"]) == _canonical_sha256(
        effect_right["events"]
    )
    if (
        effect_control_repeat["status"] != "matched"
        or effect_exact_repeat["status"] != "matched"
        or not effect_events_repeat
    ):
        raise CallbackCampaignReceiptError("GetSkillEffect repeat drift")

    matched = sum(pair["whole_game_outcome"]["status"] == "matched" for pair in pairs)
    total_attempted = sum(pair["trace"]["attempted_calls"] for pair in pairs)
    total_accepted = sum(pair["trace"]["accepted_events"] for pair in pairs)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_binding": {
            "build_identity_sha256": build_identity_sha256,
            "installed_modloader_sha256": installed_modloader_sha256,
            "inventory": _artifact(inventory_path, repository_root),
            "runtime_callback_bindings": _artifact(bindings_path, repository_root),
            "callback_join": _artifact(callback_join_path, repository_root),
        },
        "runtime_identity": runtime_identity,
        "campaign": {
            "pair_count": len(pairs),
            "callback_families": {
                "score_positioning": 1,
                "get_target_area": 1,
                "enemy_target_score": 1,
                "get_skill_effect": 2,
            },
            "condition_orders": {
                "control_then_exact": 4,
                "exact_then_control": 1,
            },
        },
        "results": {
            "complete_restored_pairs": len(pairs),
            "attempted_calls": total_attempted,
            "accepted_events": total_accepted,
            "bounded_dropped_events": total_attempted - total_accepted,
            "whole_game_matches": matched,
            "whole_game_mismatches": len(pairs) - matched,
            "mismatch_scope": [
                "/spawning_tiles/0/0",
                "/spawning_tiles/0/1",
            ],
            "get_skill_effect_repeat": {
                "counterbalanced": True,
                "control_outcomes_repeat": True,
                "exact_outcomes_repeat": True,
                "event_streams_repeat": True,
            },
            "classification": "live_callback_invocation_and_restoration_with_bounded_outcomes",
        },
        "claims": {
            "proven": [
                "ScorePositioning, GetTargetArea, GetTargetScore, and GetSkillEffect wrappers executed during complete natural enemy decision cycles and restored every installed slot.",
                "The campaign observed 622 callback attempts, serialized 620 events, and reported no serialization errors or restore conflicts.",
                "ScorePositioning, GetTargetArea, and GetTargetScore matched their paired whole-game bridge outcomes.",
                "Two counterbalanced GetSkillEffect pairs repeated the same event stream and condition-specific outcomes; their control/exact difference was limited to the following spawn coordinate.",
            ],
            "not_proven": [
                "Whole-game neutrality of GetSkillEffect instrumentation.",
                "Native enemy-candidate enumeration, native final-action selection, or their exact tournament ordering.",
                "That every possible callback implementation or mission path was exercised.",
                "Automatic Rust conformance for opaque callback payloads without a mechanic-specific oracle.",
                "Pristine-depot behavior; this is the attested owner-local-modified Windows build.",
            ],
        },
        "pairs": pairs,
        "restore": {
            "save_tree_sha256": runtime_identity["timeline_fingerprint"],
            "save_restoration_pending": True,
            "install_restoration_pending": True,
        },
    }


def publish_callback_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
    output: Path,
) -> tuple[Path, str]:
    """Create one immutable natural callback campaign receipt."""
    receipt = build_callback_campaign_receipt(
        campaign_root,
        repository_root=repository_root,
    )
    payload = _canonical_bytes(receipt)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CallbackCampaignReceiptError(f"receipt already exists: {output}") from exc
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
