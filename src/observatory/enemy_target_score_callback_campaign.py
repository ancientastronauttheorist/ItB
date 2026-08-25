"""Seal the synthetic Firefly ``GetTargetScore`` callback campaign.

The campaign isolates the score callback family in three fresh-process,
counterbalanced control/exact pairs.  It validates every raw call, proves
whole-game outcome neutrality and callback-slot restoration, then joins the
ordered 8-by-4 score matrix to the separately sealed target-area and complete
native-tournament campaigns for the same fixed Firefly1 scenario.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.callback_trial_result import (
    compare_callback_trial_results,
    validate_callback_trial_result,
)
from src.observatory.enemy_target_area_callback_campaign import (
    ATTEMPTED_FAMILIES,
    BINDING_MANIFEST_SHA256,
    BUILD_IDENTITY_SHA256,
    CALLBACK_BINDINGS,
    CALLBACK_JOIN,
    CALLBACK_JOIN_DOCUMENT_SHA256,
    CONTROLLER_SHA256,
    CONTROLLER_SOURCE,
    EXPECTED_SCENARIO,
    EXPECTED_TARGET_AREA_EVENTS,
    INSTALLED_EXPERIMENT_MODLOADER_SHA256,
    INVENTORY,
    MODLOADER_SOURCE,
    PAIR_FILES,
    SAVE_TREE_SHA256,
    SCHEMA_VERSION,
    SEMANTIC_SHA256,
    TRIAL_HOST_SHA256,
    TRIAL_HOST_SOURCE,
    EnemyTargetAreaCallbackCampaignError,
    _artifact,
    _canonical_bytes,
    _created_at,
    _load,
    _mapping,
    _metadata_digest,
    _object_sha256,
    _sha256,
    _stable_bytes,
    _validate_tournament_receipt,
    build_enemy_target_area_callback_campaign_receipt,
)
from src.observatory.enemy_tournament_hw_campaign import EXPECTED_CANDIDATES
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


RECEIPT_KIND = "observatory_enemy_target_score_callback_campaign_receipt"
HOOK_COVERAGE_SHA256 = (
    "5562a0e2d5c571538468a2e2b94aa4b40d0f5171ba6d42b2b8ba9282a54b6b1c"
)
TARGET_AREA_CAPTURE_ROOT = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_area_callback"
)
TARGET_AREA_RECEIPT = TARGET_AREA_CAPTURE_ROOT.with_name(
    TARGET_AREA_CAPTURE_ROOT.name + "_receipt.json"
)
REJECTED_DIAGNOSTIC = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_score_callback_pair002_precommand_rejection.json"
)
REJECTED_DIAGNOSTIC_SHA256 = (
    "b27c437384af10ca5d7f709bbfcf80bbebaa8bcd92bc759391f8392eb419e33d"
)

PAIR_SPECS = {
    "pair001": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "e2ca071de438ce79c3a0449ba3d69c443651f2d3f7616cfc833b4ae7183c7eba"
        ),
        "arm_packet_sha256": (
            "143fa790d91d927599d385909917d049193eeca26033f7e74dae194ca2c79721"
        ),
        "capsule_sha256": (
            "7e22b844ad33a7069c1479e65311b3cba2e318189e0f9ffa0e6e7704af4226eb"
        ),
    },
    "pair002": {
        "order": ["exact_hook", "control"],
        "plan_sha256": (
            "78bd8a76aadfb7ebc97ac40d634dd0fb72f3bb4d41728cc0c7f846a57100a0a4"
        ),
        "arm_packet_sha256": (
            "4ba09455184c70bede926448e77fe50e29dd0c7d1354be51e5d20d4c6d41fbdf"
        ),
        "capsule_sha256": (
            "64a3c8af6f4b3b2a74339480a26c14034180f9c42ee44df1c4a90e480bb1c4e0"
        ),
    },
    "pair003": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "8dd1fa12eb4e388d8fcb5b528fb7aa218f6c10d1274cd536b45f5fb7ee641c8e"
        ),
        "arm_packet_sha256": (
            "842766ab86509f8715cf1af8e595495ad3837e2de6dcad4e93630f346b97d791"
        ),
        "capsule_sha256": (
            "aa970ddf2ed41a69bcd282d3bcf531eaa1520c02a969027744e83588125e5504"
        ),
    },
}
_CAPTURE_ID_RE = re.compile(r"^firefly-target-score-pair-00[1-3]$")


def _score_event(
    call_order: int,
    origin: list[int],
    target: list[int],
    target_index: int,
) -> dict[str, Any]:
    return {
        "call_order": call_order,
        "p1": origin,
        "p2": target,
        "pawn_space": origin,
        "pawn_uid": 1303,
        "payload_version": 1,
        "representation": "get_target_score_arguments",
        "score": 5 if target_index == 3 else 0,
        "skill_id": "FireflyAtk1",
    }


EXPECTED_TARGET_SCORE_EVENTS = [
    _score_event(
        candidate_index * 4 + target_index,
        area_event["origin"],
        target,
        target_index,
    )
    for candidate_index, area_event in enumerate(EXPECTED_TARGET_AREA_EVENTS[:8])
    for target_index, target in enumerate(area_event["target_area"])
]


class EnemyTargetScoreCallbackCampaignError(
    EnemyTargetAreaCallbackCampaignError
):
    """Raised when target-score evidence is missing or inconsistent."""


def _validate_plan(
    path: Path,
    *,
    pair_name: str,
    spec: Mapping[str, str | list[str]],
    repository_root: Path,
) -> dict[str, Any]:
    data = _stable_bytes(path, f"{pair_name} pair plan")
    if _sha256(data) != spec["plan_sha256"]:
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} pair-plan digest differs"
        )
    plan = _load(path, f"{pair_name} pair plan")
    capture_id = f"firefly-target-score-pair-{pair_name[-3:]}"
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("kind") != "observatory_callback_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("conditions") != ["control", "exact_hook"]
        or plan.get("callback_family") != "enemy_target_score"
        or plan.get("capture_id") != capture_id
        or _CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} pair-plan identity differs"
        )
    artifacts = _mapping(plan.get("artifacts"), f"{pair_name} plan artifacts")
    repository_artifacts = {
        "inventory": INVENTORY,
        "bindings": CALLBACK_BINDINGS,
        "callback_join": CALLBACK_JOIN,
        "installed_modloader": MODLOADER_SOURCE,
        "controller": CONTROLLER_SOURCE,
        "trial_host": TRIAL_HOST_SOURCE,
    }
    for key, relative in repository_artifacts.items():
        metadata = _mapping(artifacts.get(key), f"{pair_name} plan {key}")
        actual = _sha256(
            _stable_bytes(repository_root / relative, f"repository {key}")
        )
        if metadata.get("sha256") != actual:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} plan {key} binding differs"
            )
    capsule = _mapping(artifacts.get("capsule"), f"{pair_name} capsule")
    arm = _mapping(artifacts.get("arm_packet"), f"{pair_name} arm packet")
    if (
        capsule.get("sha256") != spec["capsule_sha256"]
        or arm.get("sha256") != spec["arm_packet_sha256"]
        or artifacts.get("callback_join_document_sha256")
        != CALLBACK_JOIN_DOCUMENT_SHA256
        or artifacts["installed_modloader"].get("sha256")
        != INSTALLED_EXPERIMENT_MODLOADER_SHA256
        or artifacts["controller"].get("sha256") != CONTROLLER_SHA256
        or artifacts["trial_host"].get("sha256") != TRIAL_HOST_SHA256
        or type(plan.get("activation_nonce")) is not str
        or re.fullmatch(r"[0-9a-f]{32,64}", plan["activation_nonce"]) is None
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} generated-artifact binding differs"
        )
    return plan


def _validate_trial(
    trial: Mapping[str, Any],
    *,
    pair_name: str,
    condition: str,
    pair_dir: Path,
    spec: Mapping[str, str | list[str]],
) -> None:
    capture_id = f"firefly-target-score-pair-{pair_name[-3:]}"
    attempts = 0 if condition == "control" else 32
    ack = (
        "OK OBS_ENEMY_CALLBACK_TRIAL "
        f"condition={condition} family=enemy_target_score capture={capture_id} "
        "pawn=1303 type=Firefly1 at=4,4 consumed_spawns=0 "
        f"attempts={attempts} events={attempts} complete=true"
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind") != "observatory_enemy_callback_turn_trial"
        or trial.get("pair_id") != pair_name
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("callback_family") != "enemy_target_score"
        or trial.get("capture_track") != "owner_local_modified"
        or trial.get("status") != "complete"
        or trial.get("valid_trial") is not True
        or trial.get("command_ack") != ack
        or trial.get("pair_plan_sha256") != spec["plan_sha256"]
        or trial.get("capsule_sha256") != spec["capsule_sha256"]
        or trial.get("arm_packet_sha256") != spec["arm_packet_sha256"]
        or trial.get("scenario") != EXPECTED_SCENARIO
        or trial.get("callback_counts")
        != {"attempted_calls": attempts, "event_count": attempts}
        or trial.get("errors")
        != {"command": "", "outcome": [], "validation": ""}
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} {condition} trial differs"
        )
    _metadata_digest(
        trial.get("outcome"),
        pair_dir / f"{condition}_outcome.json",
        f"{pair_name} {condition} outcome",
    )
    _metadata_digest(
        trial.get("result"),
        pair_dir / f"{condition}_result.json",
        f"{pair_name} {condition} result",
    )
    if condition == "exact_hook":
        _metadata_digest(
            trial.get("trace"),
            pair_dir / "exact_hook_trace.json",
            f"{pair_name} exact trace",
        )
    elif trial.get("trace") is not None:
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} control unexpectedly published a trace"
        )


def _validate_trace(
    trace: Mapping[str, Any],
    *,
    pair_name: str,
    plan: Mapping[str, Any],
    exact: Mapping[str, Any],
) -> dict[str, Any]:
    runtime = exact["runtime_before"]
    if (
        trace.get("raw_schema_version") != SCHEMA_VERSION
        or trace.get("runtime_version") != "observatory-lua/1"
        or trace.get("controller_version")
        != "observatory-callback-controller/1"
        or trace.get("capture_id") != exact["capture_id"]
        or trace.get("checkpoint_seq") != exact["checkpoint_seq"]
        or trace.get("checkpoint_reason") != "explicit"
        or trace.get("expected_mission_id") != runtime["mission_id"]
        or trace.get("expected_phase") != "combat_enemy"
        or trace.get("expected_turn") != runtime["turn"]
        or trace.get("timeline_fingerprint") != runtime["timeline_fingerprint"]
        or trace.get("master_seed") != runtime["master_seed"]
        or trace.get("region_id") != runtime["region_id"]
        or trace.get("ai_seed_fingerprint") != runtime["ai_seed_fingerprint"]
        or trace.get("build_identity_sha256") != BUILD_IDENTITY_SHA256
        or trace.get("installed_modloader_sha256")
        != INSTALLED_EXPERIMENT_MODLOADER_SHA256
        or trace.get("controller_sha256") != CONTROLLER_SHA256
        or trace.get("hook_coverage_sha256") != HOOK_COVERAGE_SHA256
        or trace.get("arm_nonce") != plan["activation_nonce"]
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} trace identity differs"
        )
    attempted = _mapping(trace.get("attempted_calls"), f"{pair_name} attempts")
    if set(attempted) != ATTEMPTED_FAMILIES or any(
        attempted[key] != (32 if key == "enemy_target_score" else 0)
        for key in ATTEMPTED_FAMILIES
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} trace attempted-call vector differs"
        )
    summary = _mapping(trace.get("summary"), f"{pair_name} trace summary")
    if (
        summary.get("accepted_events") != 32
        or summary.get("dropped_events") != 0
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
        or summary.get("stop_reasons") != []
        or summary.get("truncation_reasons") != []
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} trace integrity differs"
        )
    coverage = trace.get("hook_coverage")
    if not isinstance(coverage, list) or len(coverage) != 69:
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} hook coverage count differs"
        )
    installed = [
        item
        for item in coverage
        if isinstance(item, Mapping) and item.get("status") == "installed"
    ]
    if (
        len(installed) != 15
        or any(
            item.get("event_kind") != "enemy_target_score" for item in installed
        )
        or any(
            not isinstance(item, Mapping)
            or item.get("status") not in {"installed", "disabled"}
            or (
                item.get("status") == "installed"
                and item.get("event_kind") != "enemy_target_score"
            )
            for item in coverage
        )
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} activated more than GetTargetScore"
        )

    events = trace.get("events")
    if not isinstance(events, list) or len(events) != 32:
        raise EnemyTargetScoreCallbackCampaignError(
            f"{pair_name} target-score event count differs"
        )
    payloads: list[dict[str, Any]] = []
    for index, (event, expected_payload) in enumerate(
        zip(events, EXPECTED_TARGET_SCORE_EVENTS, strict=True)
    ):
        if (
            not isinstance(event, Mapping)
            or set(event)
            != {"context", "kind", "mission_id", "payload", "phase", "seq", "turn"}
            or event.get("seq") != index
            or event.get("kind") != "enemy_target_score"
            or event.get("mission_id") != "Mission_Power"
            or event.get("phase") != "combat_enemy"
            or event.get("turn") != 1
            or event.get("context")
            != {
                "call_site": (
                    "runtime.callback.slot-0002.GetTargetScore.fn-0002"
                ),
                "source": "fn-0002",
            }
            or event.get("payload") != expected_payload
        ):
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} target-score event {index} differs"
            )
        payloads.append(dict(expected_payload))
    return {
        "attempted_calls": 32,
        "accepted_events": 32,
        "serialization_errors": 0,
        "restore_conflicts": 0,
        "installed_get_target_score_slots": len(installed),
        "event_payloads": payloads,
        "event_payloads_sha256": _object_sha256(payloads),
    }


def _validate_target_area_receipt(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repository_root / TARGET_AREA_RECEIPT
    receipt = _load(path, "target-area campaign receipt")
    rebuilt = build_enemy_target_area_callback_campaign_receipt(
        repository_root / TARGET_AREA_CAPTURE_ROOT,
        repository_root=repository_root,
    )
    results = _mapping(receipt.get("results"), "target-area results")
    correlation = _mapping(
        receipt.get("correlation"), "target-area correlation"
    )
    if (
        receipt != rebuilt
        or receipt.get("kind")
        != "observatory_enemy_target_area_callback_campaign_receipt"
        or results.get("classification")
        != (
            "fixed_firefly_get_target_area_runtime_order_correlated_to_"
            "complete_native_tournament"
        )
        or results.get("exact_event_counts") != [9, 9, 9]
        or results.get("semantic_sha256") != SEMANTIC_SHA256
        or results.get("all_event_streams_match") is not True
        or correlation.get("candidate_count") != 8
        or correlation.get("selected_input_index") != 5
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            "target-area campaign receipt differs"
        )
    return receipt, _artifact(path, repository_root)


def _validate_rejected_diagnostic(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repository_root / REJECTED_DIAGNOSTIC
    data = _stable_bytes(path, "pair002 rejected pre-command diagnostic")
    if _sha256(data) != REJECTED_DIAGNOSTIC_SHA256:
        raise EnemyTargetScoreCallbackCampaignError(
            "pair002 rejected diagnostic digest differs"
        )
    value = _load(path, "pair002 rejected pre-command diagnostic")
    spec = PAIR_SPECS["pair002"]
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("kind") != "observatory_enemy_callback_turn_trial"
        or value.get("pair_id") != "pair002"
        or value.get("condition") != "control"
        or value.get("capture_id") != "firefly-target-score-pair-002"
        or value.get("capture_track") != "owner_local_modified"
        or value.get("callback_family") != "enemy_target_score"
        or value.get("pair_plan_sha256") != spec["plan_sha256"]
        or value.get("capsule_sha256") != spec["capsule_sha256"]
        or value.get("arm_packet_sha256") != spec["arm_packet_sha256"]
        or value.get("status") != "rejected"
        or value.get("valid_trial") is not False
        or value.get("command_ack") is not None
        or value.get("callback_counts") is not None
        or value.get("scenario") is not None
        or value.get("outcome") is not None
        or value.get("result") is not None
        or value.get("trace") is not None
        or value.get("errors")
        != {
            "command": "enemy callback trial output already exists",
            "outcome": ["bridge_outcome_missing"],
            "validation": "",
        }
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            "pair002 rejected diagnostic identity differs"
        )
    return value, _artifact(path, repository_root)


def build_enemy_target_score_callback_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate three counterbalanced target-score pairs and return a receipt."""
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise EnemyTargetScoreCallbackCampaignError(
            f"campaign root is invalid: {root}"
        )
    actual_pairs = {
        item.name
        for item in root.iterdir()
        if item.is_dir() and not item.is_symlink()
    }
    other = {
        item.name
        for item in root.iterdir()
        if not item.is_dir() or item.is_symlink()
    }
    if actual_pairs != set(PAIR_SPECS) or other:
        raise EnemyTargetScoreCallbackCampaignError("campaign pair set differs")

    tournament, tournament_artifact = _validate_tournament_receipt(repo)
    target_area, target_area_artifact = _validate_target_area_receipt(repo)
    rejected, rejected_artifact = _validate_rejected_diagnostic(repo)
    pairs: list[dict[str, Any]] = []
    event_payloads_sha256: str | None = None
    semantic_sha256: str | None = None
    runtime_identity: dict[str, Any] | None = None
    pair002_times: dict[str, Any] = {}
    for pair_name, spec in PAIR_SPECS.items():
        pair_dir = root / pair_name
        actual_files = {
            item.name
            for item in pair_dir.iterdir()
            if item.is_file() and not item.is_symlink()
        }
        if actual_files != PAIR_FILES or any(
            item.is_dir() or item.is_symlink() for item in pair_dir.iterdir()
        ):
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} artifact set differs"
            )
        plan = _validate_plan(
            pair_dir / "pair_plan.json",
            pair_name=pair_name,
            spec=spec,
            repository_root=repo,
        )
        trials: dict[str, dict[str, Any]] = {}
        results: dict[str, dict[str, Any]] = {}
        outcomes: dict[str, dict[str, Any]] = {}
        for condition in ("control", "exact_hook"):
            trial = _load(
                pair_dir / f"{condition}_trial.json",
                f"{pair_name} {condition} trial",
            )
            _validate_trial(
                trial,
                pair_name=pair_name,
                condition=condition,
                pair_dir=pair_dir,
                spec=spec,
            )
            result = validate_callback_trial_result(
                _load(
                    pair_dir / f"{condition}_result.json",
                    f"{pair_name} {condition} result",
                ),
                expected_condition=condition,
                expected_capsule_sha256=str(spec["capsule_sha256"]),
                expected_arm_packet_sha256=str(spec["arm_packet_sha256"]),
            )
            if (
                result["capture_id"] != plan["capture_id"]
                or result["callback_family"] != "enemy_target_score"
                or result["binding_manifest_sha256"]
                != BINDING_MANIFEST_SHA256
                or result["callback_join_sha256"]
                != CALLBACK_JOIN_DOCUMENT_SHA256
                or result["slot_count"] != 65
                or result["serialization_errors"] != 0
            ):
                raise EnemyTargetScoreCallbackCampaignError(
                    f"{pair_name} {condition} result identity differs"
                )
            trials[condition] = trial
            results[condition] = result
            outcomes[condition] = _load(
                pair_dir / f"{condition}_outcome.json",
                f"{pair_name} {condition} outcome",
            )

        trial_times = {
            condition: _created_at(trials[condition], pair_name)
            for condition in trials
        }
        actual_order = [
            condition
            for condition, _ in sorted(
                trial_times.items(), key=lambda item: item[1]
            )
        ]
        if actual_order != spec["order"]:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} condition order differs"
            )
        if pair_name == "pair002":
            pair002_times = trial_times
        direct = compare_callback_trial_results(
            results["control"],
            results["exact_hook"],
            expected_capsule_sha256=str(spec["capsule_sha256"]),
            expected_arm_packet_sha256=str(spec["arm_packet_sha256"]),
        )
        if (
            direct.get("status") != "matched"
            or direct.get("exact_hook_attempted_calls") != 32
            or direct.get("exact_hook_event_count") != 32
            or direct.get("both_restored") is not True
        ):
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} callback comparison differs"
            )
        outcome = compare_rng_trial_outcomes(
            outcomes["control"],
            outcomes["exact_hook"],
            capture_id=f"enemy-target-score-{pair_name}",
        )
        if outcome.get("status") != "matched" or outcome.get(
            "difference_count"
        ) != 0:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        if outcome.get("control_semantic_sha256") != SEMANTIC_SHA256:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} semantic outcome differs"
            )
        if semantic_sha256 is None:
            semantic_sha256 = outcome["control_semantic_sha256"]
        elif semantic_sha256 != outcome["control_semantic_sha256"]:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} semantic outcome repeat differs"
            )

        trace = _load(pair_dir / "exact_hook_trace.json", f"{pair_name} trace")
        trace_summary = _validate_trace(
            trace,
            pair_name=pair_name,
            plan=plan,
            exact=results["exact_hook"],
        )
        current_payload_sha256 = trace_summary["event_payloads_sha256"]
        if event_payloads_sha256 is None:
            event_payloads_sha256 = current_payload_sha256
        elif event_payloads_sha256 != current_payload_sha256:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} target-score event stream differs"
            )
        current_runtime = {
            field: results["exact_hook"]["runtime_before"][field]
            for field in (
                "timeline_fingerprint",
                "mission_id",
                "turn",
                "master_seed",
                "region_id",
                "ai_seed_fingerprint",
            )
        }
        if runtime_identity is None:
            runtime_identity = current_runtime
        elif runtime_identity != current_runtime:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} runtime identity differs"
            )
        artifacts = {
            name.removesuffix(".json"): _artifact(pair_dir / name, repo)
            for name in sorted(PAIR_FILES)
        }
        pairs.append(
            {
                "pair": pair_name,
                "capture_id": plan["capture_id"],
                "condition_order": actual_order,
                "scenario": EXPECTED_SCENARIO,
                "callback_comparison": {
                    "status": "matched",
                    "attempted_calls": 32,
                    "accepted_events": 32,
                    "serialization_errors": 0,
                    "both_restored": True,
                },
                "whole_game_outcome": {
                    "status": "matched",
                    "difference_count": 0,
                    "semantic_sha256": outcome["control_semantic_sha256"],
                },
                "trace": trace_summary,
                "artifacts": artifacts,
            }
        )

    assert runtime_identity is not None
    assert event_payloads_sha256 is not None
    assert semantic_sha256 is not None
    rejected_time = _created_at(rejected, "pair002 rejected diagnostic")
    if not (
        pair002_times["exact_hook"]
        < rejected_time
        < pair002_times["control"]
    ):
        raise EnemyTargetScoreCallbackCampaignError(
            "pair002 rejected diagnostic chronology differs"
        )

    target_area_correlation = _mapping(
        target_area["correlation"], "target-area correlation"
    )
    area_calls = target_area_correlation.get("candidate_calls")
    if not isinstance(area_calls, list) or len(area_calls) != 8:
        raise EnemyTargetScoreCallbackCampaignError(
            "target-area candidate-call vector differs"
        )
    score_groups = []
    for candidate_index, (candidate, area_call) in enumerate(
        zip(EXPECTED_CANDIDATES, area_calls, strict=True)
    ):
        group = EXPECTED_TARGET_SCORE_EVENTS[
            candidate_index * 4 : candidate_index * 4 + 4
        ]
        origin = [candidate["destination_x"], candidate["destination_y"]]
        targets = [payload["p2"] for payload in group]
        raw_scores = [payload["score"] for payload in group]
        native_target = [candidate["target_x"], candidate["target_y"]]
        if (
            not isinstance(area_call, Mapping)
            or area_call.get("candidate_index") != candidate_index
            or area_call.get("origin") != origin
            or area_call.get("target_area") != targets
            or any(payload["p1"] != origin for payload in group)
            or any(payload["pawn_space"] != origin for payload in group)
            or raw_scores != [0, 0, 0, 5]
            or native_target != targets[3]
            or candidate["target_score"] != raw_scores[3]
        ):
            raise EnemyTargetScoreCallbackCampaignError(
                f"candidate {candidate_index} score correlation differs"
            )
        score_groups.append(
            {
                "candidate_index": candidate_index,
                "get_target_area_call_order": candidate_index,
                "get_target_score_call_orders": [
                    payload["call_order"] for payload in group
                ],
                "origin": origin,
                "target_area": targets,
                "raw_callback_scores": raw_scores,
                "raw_unique_best_index": 3,
                "raw_unique_best_target": targets[3],
                "native_candidate_target": native_target,
                "native_candidate_target_score": candidate["target_score"],
                "native_candidate_positioning_score": candidate[
                    "positioning_score"
                ],
                "raw_best_matches_native_candidate": True,
            }
        )

    inventory_path = repo / INVENTORY
    inventory = _load(inventory_path, "owner-local inventory")
    tournament_results = _mapping(tournament["results"], "tournament results")
    selected_repeat = _mapping(
        target_area_correlation["selected_destination_repeat"],
        "selected target-area repeat",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": {
            "platform": inventory["platform"],
            "architecture": inventory["executable"]["architecture"],
            "build_id": inventory["steam"]["build_id"],
            "depot_manifest": inventory["steam"]["installed_depots"][0][
                "manifest"
            ],
            "executable_sha256": inventory["executable"]["sha256"],
            "lua_dll_sha256": next(
                item["sha256"]
                for item in inventory["native_libraries"]
                if item["path"] == "lua5.1.dll"
            ),
            "callback_build_identity_sha256": BUILD_IDENTITY_SHA256,
            "installed_experiment_modloader_sha256": (
                INSTALLED_EXPERIMENT_MODLOADER_SHA256
            ),
        },
        "runtime_identity": runtime_identity,
        "campaign": {
            "pair_count": len(pairs),
            "conditions": ["control", "exact_hook"],
            "callback_family": "enemy_target_score",
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fresh_processes": 3,
            "fixed_seed": 324_508_639,
            "save_tree_sha256": SAVE_TREE_SHA256,
            "scenario": EXPECTED_SCENARIO,
            "accepted_trial_count": 6,
            "rejected_pre_command_trial_count": 1,
        },
        "pairs": pairs,
        "correlation": {
            "target_area_source": target_area_artifact,
            "target_area_event_payloads_sha256": target_area["results"][
                "event_payloads_sha256"
            ],
            "native_candidate_source": tournament_artifact,
            "native_candidate_vector_sha256": tournament_results[
                "stable_candidate_vector_sha256"
            ],
            "candidate_count": 8,
            "score_groups": score_groups,
            "selected_destination_repeat": {
                "target_area_call_order": selected_repeat["call_order"],
                "matches_candidate_index": selected_repeat[
                    "matches_candidate_call_order"
                ],
                "origin": selected_repeat["origin"],
                "target_area": selected_repeat["target_area"],
                "additional_score_group_observed": False,
                "scope": (
                    "separate deterministic campaigns; not a same-process "
                    "causal ordering claim"
                ),
            },
        },
        "results": {
            "classification": (
                "fixed_firefly_get_target_score_runtime_matrix_correlated_to_"
                "target_areas_and_complete_native_tournament"
            ),
            "complete_restored_pairs": len(pairs),
            "control_attempt_counts": [0, 0, 0],
            "exact_attempt_counts": [32, 32, 32],
            "exact_event_counts": [32, 32, 32],
            "all_event_streams_match": True,
            "event_payloads_sha256": event_payloads_sha256,
            "all_semantic_outcomes_match": True,
            "semantic_sha256": semantic_sha256,
            "all_slots_restored": True,
            "serialization_error_count": 0,
            "restore_conflict_count": 0,
            "rejected_pre_command_trials": 1,
        },
        "claims": {
            "proven": [
                (
                    "In the fixed Firefly1 scenario, all three exact-hook fresh "
                    "processes emitted the same 32 ordered GetTargetScore calls "
                    "while every matched control emitted none."
                ),
                (
                    "The calls form eight consecutive four-call groups whose "
                    "origins and target order equal the first eight sealed "
                    "GetTargetArea calls: every raw score vector is [0,0,0,5]."
                ),
                (
                    "For each group, the raw unique-best tile at index three "
                    "equals the separately captured native candidate target, "
                    "and raw score five equals that record's target score."
                ),
                (
                    "Every control/exact whole-game outcome matched semantically, "
                    "all 65 slots were restored, and all exact calls serialized "
                    "with zero drops, errors, or restore conflicts."
                ),
                (
                    "One pair002 control attempt was rejected before issuing a "
                    "game command because retained exact-hook output existed; "
                    "the later accepted control is the only control evidence."
                ),
            ],
            "not_proven": [
                (
                    "A universal GetTargetScore call count, value, or target "
                    "choice for other boards, enemies, weapons, cancellation, "
                    "or retarget paths."
                ),
                (
                    "A same-process dual-observer causal ordering between the "
                    "Lua score calls, target-area calls, and native records; the "
                    "correlation joins separate deterministic campaigns."
                ),
                (
                    "Post-wrapper scores for the three losing targets, the "
                    "native equal-best set, or caller-29 RNG state and values."
                ),
                (
                    "Candidate-time Board predicates, ScorePositioning inputs, "
                    "concrete SkillEffect payloads, transitive native-helper RNG, "
                    "or prospective enemy forecasting from ordinary solver input."
                ),
                "Pristine-depot behavior.",
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "For the fixed Firefly1 payload, preserve the observed eight "
                "ordered four-target raw score groups and bind each unique raw "
                "best to its complete native candidate record"
            ),
            "capture_backed_test": (
                "test_committed_target_score_campaign_correlates_areas_and_"
                "native_candidates"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator consumes the authoritative settled queue; "
                "ordinary solver input still lacks future callback Board state, "
                "SkillEffects, wrapper modifiers, and selector-entry RNG state."
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "diagnostics": {
            "pair002_precommand_rejection": {
                "classification": "safely_rejected_before_game_command",
                "reason": "enemy callback trial output already exists",
                "chronology": "after_exact_hook_before_accepted_control",
                "accepted_as_campaign_evidence": False,
                "artifact": rejected_artifact,
            }
        },
        "supporting_artifacts": {
            "inventory": _artifact(inventory_path, repo),
            "runtime_callback_bindings": _artifact(repo / CALLBACK_BINDINGS, repo),
            "callback_join": _artifact(repo / CALLBACK_JOIN, repo),
            "target_area_campaign_receipt": target_area_artifact,
            "complete_enemy_tournament_receipt": tournament_artifact,
        },
    }


def archive_enemy_target_score_callback_campaign(
    source_root: Path,
    output_root: Path,
) -> Path:
    """Copy immutable accepted pairs and the rejected diagnostic into the repo."""
    source = source_root.resolve()
    output = Path(os.path.abspath(output_root))
    diagnostic_output = output.with_name(
        output.name + "_pair002_precommand_rejection.json"
    )
    if output.exists() or output.is_symlink():
        raise EnemyTargetScoreCallbackCampaignError(
            f"campaign archive already exists: {output}"
        )
    if diagnostic_output.exists() or diagnostic_output.is_symlink():
        raise EnemyTargetScoreCallbackCampaignError(
            f"diagnostic archive already exists: {diagnostic_output}"
        )
    if source.is_symlink() or not source.is_dir():
        raise EnemyTargetScoreCallbackCampaignError(
            f"campaign source is invalid: {source}"
        )
    diagnostic_source = (
        source
        / "diagnostics"
        / "pair002_control_retained_raw_rejection_trial.json"
    )
    diagnostic = _stable_bytes(
        diagnostic_source, "pair002 source rejected diagnostic"
    )
    if _sha256(diagnostic) != REJECTED_DIAGNOSTIC_SHA256:
        raise EnemyTargetScoreCallbackCampaignError(
            "pair002 source rejected diagnostic digest differs"
        )
    output.mkdir(parents=True)
    for pair_name in PAIR_SPECS:
        source_pair = source / pair_name
        destination_pair = output / pair_name
        destination_pair.mkdir()
        plans = list(source_pair.glob("*_pair_plan.json"))
        if len(plans) != 1:
            raise EnemyTargetScoreCallbackCampaignError(
                f"{pair_name} source pair plan is ambiguous"
            )
        sources = {"pair_plan.json": plans[0]}
        for condition in ("control", "exact_hook"):
            sources[f"{condition}_trial.json"] = (
                source_pair / condition / "trial.json"
            )
            sources[f"{condition}_outcome.json"] = (
                source_pair / condition / "outcome.json"
            )
            sources[f"{condition}_result.json"] = (
                source_pair / condition / "result.json"
            )
        sources["exact_hook_trace.json"] = (
            source_pair / "exact_hook" / "trace.json"
        )
        for name, source_path in sources.items():
            payload = _stable_bytes(source_path, f"{pair_name} source {name}")
            destination = destination_pair / name
            with destination.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
    with diagnostic_output.open("xb") as handle:
        handle.write(diagnostic)
        handle.flush()
        os.fsync(handle.fileno())
    return output


def publish_enemy_target_score_callback_campaign_receipt(
    value: Mapping[str, Any],
    output: Path,
) -> tuple[Path, str]:
    """Create one immutable canonical target-score campaign receipt."""
    path = output.resolve()
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise EnemyTargetScoreCallbackCampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
