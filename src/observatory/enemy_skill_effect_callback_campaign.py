"""Seal the synthetic Firefly ``GetSkillEffect`` callback campaign.

The campaign isolates one callback family in three fresh-process,
counterbalanced control/exact pairs.  It validates every raw SkillEffect,
proves whole-game outcome neutrality and callback-slot restoration, then joins
the ordered calls to the separately sealed target-area, target-score, source-
ancestry, and complete native-tournament evidence for the same fixed Firefly1
scenario.
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
from src.observatory.enemy_target_score_callback_campaign import (
    TARGET_AREA_RECEIPT as SCORE_BOUND_TARGET_AREA_RECEIPT,
    build_enemy_target_score_callback_campaign_receipt,
    EXPECTED_TARGET_SCORE_EVENTS,
)
from src.observatory.enemy_tournament_hw_campaign import EXPECTED_CANDIDATES
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


RECEIPT_KIND = "observatory_enemy_skill_effect_callback_campaign_receipt"
HOOK_COVERAGE_SHA256 = (
    "5373e93367f93c12325b11fa42e8ac15f41eaee2a1827921d9ad08084d2e22b1"
)
TARGET_AREA_CAPTURE_ROOT = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_area_callback"
)
TARGET_AREA_RECEIPT = TARGET_AREA_CAPTURE_ROOT.with_name(
    TARGET_AREA_CAPTURE_ROOT.name + "_receipt.json"
)
TARGET_SCORE_CAPTURE_ROOT = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_score_callback"
)
TARGET_SCORE_RECEIPT = TARGET_SCORE_CAPTURE_ROOT.with_name(
    TARGET_SCORE_CAPTURE_ROOT.name + "_receipt.json"
)
SCORE_EFFECT_ANCESTRY = Path("data/observatory/callbacks") / (
    "windows_build_13725832_31fe35265598_enemy_score_effect_ancestry.json"
)

PAIR_SPECS = {
    "pair001": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "de8277d7f8c1898ac0b99e5ff95791d6adfce16d7442ebe702d30f488e69df7e"
        ),
        "arm_packet_sha256": (
            "82c374a009024e4a274c4d44b8738c0d4015428fd0e04155357f9360f53d06f8"
        ),
        "capsule_sha256": (
            "185e19b4ebf53b27f4198e19323cc743d56be16ced421773452d721b4eed87cb"
        ),
    },
    "pair002": {
        "order": ["exact_hook", "control"],
        "plan_sha256": (
            "5d242af89b6e05127e95b9e91a31145a8f6a7e84645256442cfb9d8bef42c8cf"
        ),
        "arm_packet_sha256": (
            "1ec849f4410ba649f3f808b47ac2167072c6b2dc397903661262bf5ff3b40d3a"
        ),
        "capsule_sha256": (
            "b25266e16579572dc5875e289c68f5101a08c0215ccfcefd794c4b0c529622fe"
        ),
    },
    "pair003": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "2bca575dd60a4185dc93a2ceca94d614955009c80335a4d91ad13c5f0a885fe1"
        ),
        "arm_packet_sha256": (
            "48f73c1490be9548bd0b1445302227be8056444e51987834206cfe0becd0a022"
        ),
        "capsule_sha256": (
            "655f5b76fb1bd0df701043062e210c28f24db9080e3e904a88302d2ca9bd2fc1"
        ),
    },
}
_CAPTURE_ID_RE = re.compile(r"^firefly-skill-effect-pair-00[1-3]$")


_IMPACT_TILES = [
    [4, 0], [7, 2], [4, 7], [3, 2],
    [4, 0], [6, 3], [4, 7], [3, 3],
    [4, 0], [7, 5], [4, 7], [3, 5],
    [4, 0], [7, 6], [4, 7], [2, 6],
    [5, 0], [6, 3], [5, 7], [3, 3],
    [5, 0], [6, 4], [5, 7], [3, 4],
    [5, 0], [7, 5], [5, 7], [3, 5],
    [4, 0], [6, 4], [4, 7], [3, 4],
    [3, 4],
]


def _effect_fields(impact: list[int]) -> list[dict[str, Any]]:
    return [
        {"name": "bEvacuate", "value": False},
        {"name": "bHide", "value": False},
        {"name": "bHideIcon", "value": False},
        {"name": "bHidePath", "value": False},
        {"name": "bKO_Effect", "value": False},
        {"name": "bSimpleMark", "value": False},
        {"name": "fDelay", "value": -2},
        {"name": "iAcid", "value": 0},
        {"name": "iCrack", "value": 0},
        {"name": "iDamage", "value": 1},
        {"name": "iFire", "value": 0},
        {"name": "iFrozen", "value": 0},
        {"name": "iInjure", "value": 0},
        {"name": "iPawnTeam", "value": 2},
        {"name": "iPush", "value": 4},
        {"name": "iShield", "value": 0},
        {"name": "iSmoke", "value": 0},
        {"name": "iTerrain", "value": 10},
        {"name": "sAnimation", "value": ""},
        {"name": "sImageMark", "value": ""},
        {"name": "sItem", "value": ""},
        {"name": "sPawn", "value": ""},
        {"name": "sScript", "value": ""},
        {"name": "sSound", "value": ""},
        {"name": "loc", "value": impact},
    ]


def _effect_event(
    call_order: int,
    origin: list[int],
    target: list[int],
    impact: list[int],
) -> dict[str, Any]:
    return {
        "call_order": call_order,
        "origin": origin,
        "pawn_uid": 1303,
        "payload_version": 1,
        "primitive_count": 25,
        "primitive_summary": {
            "effect": [],
            "q_effect": [{"fields": _effect_fields(impact), "index": 0}],
        },
        "representation": "raw_opaque_primitives",
        "skill_id": "FireflyAtk1",
        "target": target,
    }


EXPECTED_SKILL_EFFECT_EVENTS = [
    _effect_event(
        call_order,
        area_event["origin"],
        target,
        _IMPACT_TILES[call_order],
    )
    for call_order, (area_event, target) in enumerate(
        (area_event, target)
        for area_event in EXPECTED_TARGET_AREA_EVENTS[:8]
        for target in area_event["target_area"]
    )
]
EXPECTED_SKILL_EFFECT_EVENTS.append(
    _effect_event(32, [5, 4], [4, 4], _IMPACT_TILES[32])
)


def _effect_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    queued = payload["primitive_summary"]["q_effect"][0]
    fields = {item["name"]: item["value"] for item in queued["fields"]}
    return {
        "call_order": payload["call_order"],
        "origin": payload["origin"],
        "target": payload["target"],
        "impact_tile": fields["loc"],
        "damage": fields["iDamage"],
        "push": fields["iPush"],
        "fire": fields["iFire"],
        "acid": fields["iAcid"],
        "frozen": fields["iFrozen"],
        "instant_primitive_count": len(payload["primitive_summary"]["effect"]),
        "queued_primitive_count": len(payload["primitive_summary"]["q_effect"]),
    }


class EnemySkillEffectCallbackCampaignError(
    EnemyTargetAreaCallbackCampaignError
):
    """Raised when skill-effect evidence is missing or inconsistent."""


def _validate_plan(
    path: Path,
    *,
    pair_name: str,
    spec: Mapping[str, str | list[str]],
    repository_root: Path,
) -> dict[str, Any]:
    data = _stable_bytes(path, f"{pair_name} pair plan")
    if _sha256(data) != spec["plan_sha256"]:
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} pair-plan digest differs"
        )
    plan = _load(path, f"{pair_name} pair plan")
    capture_id = f"firefly-skill-effect-pair-{pair_name[-3:]}"
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("kind") != "observatory_callback_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("conditions") != ["control", "exact_hook"]
        or plan.get("callback_family") != "get_skill_effect"
        or plan.get("capture_id") != capture_id
        or _CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise EnemySkillEffectCallbackCampaignError(
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
            raise EnemySkillEffectCallbackCampaignError(
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
        raise EnemySkillEffectCallbackCampaignError(
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
    capture_id = f"firefly-skill-effect-pair-{pair_name[-3:]}"
    attempts = 0 if condition == "control" else 33
    ack = (
        "OK OBS_ENEMY_CALLBACK_TRIAL "
        f"condition={condition} family=get_skill_effect capture={capture_id} "
        "pawn=1303 type=Firefly1 at=4,4 consumed_spawns=0 "
        f"attempts={attempts} events={attempts} complete=true"
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind") != "observatory_enemy_callback_turn_trial"
        or trial.get("pair_id") != pair_name
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("callback_family") != "get_skill_effect"
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
        raise EnemySkillEffectCallbackCampaignError(
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
        raise EnemySkillEffectCallbackCampaignError(
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
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} trace identity differs"
        )
    attempted = _mapping(trace.get("attempted_calls"), f"{pair_name} attempts")
    if set(attempted) != ATTEMPTED_FAMILIES or any(
        attempted[key] != (33 if key == "get_skill_effect" else 0)
        for key in ATTEMPTED_FAMILIES
    ):
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} trace attempted-call vector differs"
        )
    summary = _mapping(trace.get("summary"), f"{pair_name} trace summary")
    if (
        summary.get("accepted_events") != 33
        or summary.get("dropped_events") != 0
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
        or summary.get("stop_reasons") != []
        or summary.get("truncation_reasons") != []
    ):
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} trace integrity differs"
        )
    coverage = trace.get("hook_coverage")
    if not isinstance(coverage, list) or len(coverage) != 69:
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} hook coverage count differs"
        )
    installed = [
        item
        for item in coverage
        if isinstance(item, Mapping) and item.get("status") == "installed"
    ]
    if (
        len(installed) != 38
        or any(
            item.get("event_kind") != "get_skill_effect" for item in installed
        )
        or any(
            not isinstance(item, Mapping)
            or item.get("status") not in {"installed", "disabled"}
            or (
                item.get("status") == "installed"
                and item.get("event_kind") != "get_skill_effect"
            )
            for item in coverage
        )
    ):
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} activated more than GetSkillEffect"
        )

    events = trace.get("events")
    if not isinstance(events, list) or len(events) != 33:
        raise EnemySkillEffectCallbackCampaignError(
            f"{pair_name} skill-effect event count differs"
        )
    payloads: list[dict[str, Any]] = []
    for index, (event, expected_payload) in enumerate(
        zip(events, EXPECTED_SKILL_EFFECT_EVENTS, strict=True)
    ):
        if (
            not isinstance(event, Mapping)
            or set(event)
            != {"context", "kind", "mission_id", "payload", "phase", "seq", "turn"}
            or event.get("seq") != index
            or event.get("kind") != "get_skill_effect"
            or event.get("mission_id") != "Mission_Power"
            or event.get("phase") != "combat_enemy"
            or event.get("turn") != 1
            or event.get("context")
            != {
                "call_site": (
                    "runtime.callback.slot-0032.GetSkillEffect.fn-0032"
                ),
                "source": "fn-0032",
            }
            or event.get("payload") != expected_payload
        ):
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} skill-effect event {index} differs"
            )
        payloads.append(dict(expected_payload))
    return {
        "attempted_calls": 33,
        "accepted_events": 33,
        "serialization_errors": 0,
        "restore_conflicts": 0,
        "installed_get_skill_effect_slots": len(installed),
        "event_projections": [_effect_projection(payload) for payload in payloads],
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
        raise EnemySkillEffectCallbackCampaignError(
            "target-area campaign receipt differs"
        )
    return receipt, _artifact(path, repository_root)


def _validate_target_score_receipt(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repository_root / TARGET_SCORE_RECEIPT
    receipt = _load(path, "target-score campaign receipt")
    rebuilt = build_enemy_target_score_callback_campaign_receipt(
        repository_root / TARGET_SCORE_CAPTURE_ROOT,
        repository_root=repository_root,
    )
    results = _mapping(receipt.get("results"), "target-score results")
    correlation = _mapping(
        receipt.get("correlation"), "target-score correlation"
    )
    groups = correlation.get("score_groups")
    if (
        SCORE_BOUND_TARGET_AREA_RECEIPT != TARGET_AREA_RECEIPT
        or receipt != rebuilt
        or receipt.get("kind")
        != "observatory_enemy_target_score_callback_campaign_receipt"
        or results.get("classification")
        != (
            "fixed_firefly_get_target_score_runtime_matrix_correlated_to_"
            "target_areas_and_complete_native_tournament"
        )
        or results.get("exact_event_counts") != [32, 32, 32]
        or results.get("semantic_sha256") != SEMANTIC_SHA256
        or results.get("all_event_streams_match") is not True
        or not isinstance(groups, list)
        or len(groups) != 8
    ):
        raise EnemySkillEffectCallbackCampaignError(
            "target-score campaign receipt differs"
        )
    return receipt, _artifact(path, repository_root)


def _validate_score_effect_ancestry(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repository_root / SCORE_EFFECT_ANCESTRY
    value = _load(path, "score/effect ancestry")
    contracts = _mapping(value.get("contracts"), "ancestry contracts")
    closure = _mapping(value.get("closure"), "ancestry closure")
    callbacks = value.get("target_score_callbacks")
    skill = [] if not isinstance(callbacks, list) else [
        item
        for item in callbacks
        if isinstance(item, Mapping) and item.get("symbol") == "Skill:GetTargetScore"
    ]
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != "lua_enemy_score_effect_ancestry"
        or contracts.get("base_lua_route")
        != "Skill:GetTargetScore -> self:GetSkillEffect -> ScoreList"
        or contracts.get("score_route_uses_native_cache_materializer") is not False
        or contracts.get("score_route_uses_final_effect") is not False
        or closure.get("score_side_effect_ancestry_complete") is not True
        or closure.get("prospective_callback_inputs_complete") is not False
        or len(skill) != 1
        or skill[0].get("payload_route") != "direct_actual_effect"
        or skill[0].get("self_effect_calls") != 1
        or skill[0].get("score_list_calls") != 2
        or skill[0].get("get_final_effect_calls") != 0
    ):
        raise EnemySkillEffectCallbackCampaignError(
            "score/effect ancestry differs"
        )
    return value, _artifact(path, repository_root)


def _settled_action(
    outcome: Mapping[str, Any], label: str
) -> dict[str, Any]:
    units = outcome.get("units")
    fireflies = [] if not isinstance(units, list) else [
        unit
        for unit in units
        if isinstance(unit, Mapping) and unit.get("uid") == 1303
    ]
    if (
        outcome.get("mission_id") != "Mission_Power"
        or outcome.get("phase") != "combat_player"
        or outcome.get("turn") != 2
        or outcome.get("attack_order") != [1303]
        or outcome.get("targeted_tiles") != [[3, 4]]
        or len(fireflies) != 1
        or fireflies[0].get("type") != "Firefly1"
        or [fireflies[0].get("x"), fireflies[0].get("y")] != [5, 4]
        or fireflies[0].get("has_queued_attack") is not True
        or fireflies[0].get("weapons") != ["FireflyAtk1"]
    ):
        raise EnemySkillEffectCallbackCampaignError(
            f"{label} settled action differs"
        )
    return {
        "pawn_uid": 1303,
        "pawn_type": "Firefly1",
        "origin": [5, 4],
        "skill_id": "FireflyAtk1",
        "impact_tile": [3, 4],
        "has_queued_attack": True,
        "attack_order": [1303],
    }


def build_enemy_skill_effect_callback_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate three counterbalanced skill-effect pairs and return a receipt."""
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise EnemySkillEffectCallbackCampaignError(
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
        raise EnemySkillEffectCallbackCampaignError("campaign pair set differs")

    tournament, tournament_artifact = _validate_tournament_receipt(repo)
    target_area, target_area_artifact = _validate_target_area_receipt(repo)
    target_score, target_score_artifact = _validate_target_score_receipt(repo)
    ancestry, ancestry_artifact = _validate_score_effect_ancestry(repo)
    pairs: list[dict[str, Any]] = []
    event_payloads_sha256: str | None = None
    semantic_sha256: str | None = None
    runtime_identity: dict[str, Any] | None = None
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
            raise EnemySkillEffectCallbackCampaignError(
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
                or result["callback_family"] != "get_skill_effect"
                or result["binding_manifest_sha256"]
                != BINDING_MANIFEST_SHA256
                or result["callback_join_sha256"]
                != CALLBACK_JOIN_DOCUMENT_SHA256
                or result["slot_count"] != 65
                or result["serialization_errors"] != 0
            ):
                raise EnemySkillEffectCallbackCampaignError(
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
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} condition order differs"
            )
        direct = compare_callback_trial_results(
            results["control"],
            results["exact_hook"],
            expected_capsule_sha256=str(spec["capsule_sha256"]),
            expected_arm_packet_sha256=str(spec["arm_packet_sha256"]),
        )
        if (
            direct.get("status") != "matched"
            or direct.get("exact_hook_attempted_calls") != 33
            or direct.get("exact_hook_event_count") != 33
            or direct.get("both_restored") is not True
        ):
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} callback comparison differs"
            )
        outcome = compare_rng_trial_outcomes(
            outcomes["control"],
            outcomes["exact_hook"],
            capture_id=f"enemy-skill-effect-{pair_name}",
        )
        if outcome.get("status") != "matched" or outcome.get(
            "difference_count"
        ) != 0:
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        if outcome.get("control_semantic_sha256") != SEMANTIC_SHA256:
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} semantic outcome differs"
            )
        if semantic_sha256 is None:
            semantic_sha256 = outcome["control_semantic_sha256"]
        elif semantic_sha256 != outcome["control_semantic_sha256"]:
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} semantic outcome repeat differs"
            )
        settled_control = _settled_action(
            outcomes["control"], f"{pair_name} control"
        )
        settled_exact = _settled_action(
            outcomes["exact_hook"], f"{pair_name} exact"
        )
        if settled_control != settled_exact:
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} settled action comparison differs"
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
            raise EnemySkillEffectCallbackCampaignError(
                f"{pair_name} skill-effect event stream differs"
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
            raise EnemySkillEffectCallbackCampaignError(
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
                    "attempted_calls": 33,
                    "accepted_events": 33,
                    "serialization_errors": 0,
                    "both_restored": True,
                },
                "whole_game_outcome": {
                    "status": "matched",
                    "difference_count": 0,
                    "semantic_sha256": outcome["control_semantic_sha256"],
                },
                "settled_action": settled_exact,
                "trace": trace_summary,
                "artifacts": artifacts,
            }
        )

    assert runtime_identity is not None
    assert event_payloads_sha256 is not None
    assert semantic_sha256 is not None
    target_area_correlation = _mapping(
        target_area["correlation"], "target-area correlation"
    )
    area_calls = target_area_correlation.get("candidate_calls")
    if not isinstance(area_calls, list) or len(area_calls) != 8:
        raise EnemySkillEffectCallbackCampaignError(
            "target-area candidate-call vector differs"
        )
    target_score_correlation = _mapping(
        target_score["correlation"], "target-score correlation"
    )
    raw_score_groups = target_score_correlation.get("score_groups")
    if not isinstance(raw_score_groups, list) or len(raw_score_groups) != 8:
        raise EnemySkillEffectCallbackCampaignError(
            "target-score group vector differs"
        )
    effect_groups = []
    for candidate_index, (candidate, area_call, raw_score_group) in enumerate(
        zip(EXPECTED_CANDIDATES, area_calls, raw_score_groups, strict=True)
    ):
        effects = EXPECTED_SKILL_EFFECT_EVENTS[
            candidate_index * 4 : candidate_index * 4 + 4
        ]
        scores = EXPECTED_TARGET_SCORE_EVENTS[
            candidate_index * 4 : candidate_index * 4 + 4
        ]
        origin = [candidate["destination_x"], candidate["destination_y"]]
        targets = [payload["target"] for payload in effects]
        impacts = [_effect_projection(payload)["impact_tile"] for payload in effects]
        raw_scores = [payload["score"] for payload in scores]
        native_target = [candidate["target_x"], candidate["target_y"]]
        if (
            not isinstance(area_call, Mapping)
            or not isinstance(raw_score_group, Mapping)
            or area_call.get("candidate_index") != candidate_index
            or area_call.get("origin") != origin
            or area_call.get("target_area") != targets
            or raw_score_group.get("candidate_index") != candidate_index
            or raw_score_group.get("origin") != origin
            or raw_score_group.get("target_area") != targets
            or raw_score_group.get("raw_callback_scores") != raw_scores
            or any(payload["origin"] != origin for payload in effects)
            or any(payload["p1"] != origin for payload in scores)
            or [payload["p2"] for payload in scores] != targets
            or raw_scores != [0, 0, 0, 5]
            or native_target != targets[3]
            or candidate["target_score"] != raw_scores[3]
        ):
            raise EnemySkillEffectCallbackCampaignError(
                f"candidate {candidate_index} effect correlation differs"
            )
        effect_groups.append(
            {
                "candidate_index": candidate_index,
                "get_target_area_call_order": candidate_index,
                "get_target_score_call_orders": [
                    payload["call_order"] for payload in scores
                ],
                "score_side_get_skill_effect_call_orders": [
                    payload["call_order"] for payload in effects
                ],
                "origin": origin,
                "target_area": targets,
                "impact_tiles": impacts,
                "raw_callback_scores": raw_scores,
                "raw_unique_best_index": 3,
                "raw_unique_best_target": targets[3],
                "native_candidate_target": native_target,
                "native_candidate_target_score": candidate["target_score"],
                "native_candidate_positioning_score": candidate[
                    "positioning_score"
                ],
                "raw_effect_contract": {
                    "instant_primitives": 0,
                    "queued_primitives": 1,
                    "damage": 1,
                    "push": 4,
                    "fire": 0,
                    "acid": 0,
                    "frozen": 0,
                },
                "effect_arguments_match_score_arguments": True,
            }
        )

    selected_input_index = 5
    selected_score_effect = EXPECTED_SKILL_EFFECT_EVENTS[
        selected_input_index * 4 + 3
    ]
    selected_final_effect = EXPECTED_SKILL_EFFECT_EVENTS[32]
    selected_score_projection = _effect_projection(selected_score_effect)
    selected_final_projection = _effect_projection(selected_final_effect)
    if (
        selected_final_effect["origin"] != selected_score_effect["origin"]
        or selected_final_effect["target"] != selected_score_effect["target"]
        or selected_final_effect["primitive_summary"]
        != selected_score_effect["primitive_summary"]
        or selected_final_projection["impact_tile"] != [3, 4]
        or any(pair["settled_action"]["origin"] != [5, 4] for pair in pairs)
        or any(pair["settled_action"]["impact_tile"] != [3, 4] for pair in pairs)
    ):
        raise EnemySkillEffectCallbackCampaignError(
            "selected effect repeat differs"
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
            "callback_family": "get_skill_effect",
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fresh_processes": 3,
            "fixed_seed": 324_508_639,
            "save_tree_sha256": SAVE_TREE_SHA256,
            "scenario": EXPECTED_SCENARIO,
            "accepted_trial_count": 6,
        },
        "pairs": pairs,
        "correlation": {
            "target_area_source": target_area_artifact,
            "target_area_event_payloads_sha256": target_area["results"][
                "event_payloads_sha256"
            ],
            "target_score_source": target_score_artifact,
            "target_score_event_payloads_sha256": target_score["results"][
                "event_payloads_sha256"
            ],
            "score_effect_ancestry_source": ancestry_artifact,
            "score_effect_route": ancestry["contracts"]["base_lua_route"],
            "native_candidate_source": tournament_artifact,
            "native_candidate_vector_sha256": tournament_results[
                "stable_candidate_vector_sha256"
            ],
            "candidate_count": 8,
            "effect_groups": effect_groups,
            "selected_effect_repeat": {
                "target_area_call_order": selected_repeat["call_order"],
                "native_selected_input_index": selected_input_index,
                "score_side_call_order": selected_score_effect["call_order"],
                "final_call_order": selected_final_effect["call_order"],
                "origin": selected_final_effect["origin"],
                "target": selected_final_effect["target"],
                "impact_tile": selected_final_projection["impact_tile"],
                "raw_effect_matches_score_side_call": True,
                "score_side_projection": selected_score_projection,
                "final_projection": selected_final_projection,
                "settled_action_matches_all_pairs": True,
                "scope": (
                    "the 33-call order and settled action are same-process; "
                    "the native-record and target/score joins are separate "
                    "deterministic campaigns"
                ),
            },
        },
        "results": {
            "classification": (
                "fixed_firefly_get_skill_effect_runtime_sequence_correlated_"
                "to_scoring_native_selection_and_settled_action"
            ),
            "complete_restored_pairs": len(pairs),
            "control_attempt_counts": [0, 0, 0],
            "exact_attempt_counts": [33, 33, 33],
            "exact_event_counts": [33, 33, 33],
            "all_event_streams_match": True,
            "event_payloads_sha256": event_payloads_sha256,
            "all_semantic_outcomes_match": True,
            "semantic_sha256": semantic_sha256,
            "all_slots_restored": True,
            "serialization_error_count": 0,
            "restore_conflict_count": 0,
        },
        "claims": {
            "proven": [
                (
                    "In the fixed Firefly1 scenario, all three exact-hook fresh "
                    "processes emitted the same 33 ordered GetSkillEffect calls "
                    "while every matched control emitted none."
                ),
                (
                    "Calls 0 through 31 form eight consecutive four-call groups. "
                    "Their origins and target order equal the first eight sealed "
                    "GetTargetArea calls and the 32 raw GetTargetScore argument "
                    "pairs. Each raw effect has no instant primitive and exactly "
                    "one queued one-damage, no-push projectile primitive."
                ),
                (
                    "Source-exact ancestry proves inherited Skill:GetTargetScore "
                    "dynamically calls self:GetSkillEffect once, so the first 32 "
                    "effects are the score-side materializations for those "
                    "candidate/target arguments in this fixed scenario."
                ),
                (
                    "Call 32 repeats score-side call 23 byte-for-byte apart from "
                    "call order: origin [5,4], selected target [4,4], and impact "
                    "tile [3,4]. That is native selected input 5, and the same "
                    "process settles Firefly1 at [5,4] with a queued attack on "
                    "[3,4]."
                ),
                (
                    "Every control/exact whole-game outcome matched semantically, "
                    "all 65 slots were restored, and all exact calls serialized "
                    "with zero drops, errors, or restore conflicts."
                ),
            ],
            "not_proven": [
                (
                    "A universal GetSkillEffect call count, primitive payload, "
                    "or repeat path for other boards, enemies, weapons, TwoClick, "
                    "cancellation, or retarget flows."
                ),
                (
                    "A same-process dual-observer causal ordering between the Lua "
                    "target/score callbacks and native records; those joins use "
                    "separate deterministic campaigns."
                ),
                (
                    "Native cache annotation/postprocessing of the raw final "
                    "SkillEffect, post-wrapper losing-target scores, the native "
                    "equal-best set, or caller-29 RNG state."
                ),
                (
                    "Candidate-time Board snapshots, direct dangerous carriers, "
                    "runtime-mutated Pawn helper values, transitive native-helper "
                    "RNG, or prospective enemy forecasting from ordinary solver "
                    "input."
                ),
                "Pristine-depot behavior.",
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "For the fixed Firefly1 payload, preserve the observed 32 "
                "score-side raw SkillEffects and the final selected-effect repeat "
                "that matches the settled queued action"
            ),
            "capture_backed_test": (
                "test_committed_skill_effect_campaign_correlates_scoring_and_"
                "settled_action"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator consumes the authoritative settled queue; "
                "ordinary solver input still lacks future callback Board state, "
                "native cache postprocessing, wrapper modifiers, and selector-"
                "entry RNG state."
            ),
        },
        "restore": {
            "install_restoration_pending": True,
            "save_restoration_pending": True,
            "save_tree_sha256": SAVE_TREE_SHA256,
        },
        "supporting_artifacts": {
            "inventory": _artifact(inventory_path, repo),
            "runtime_callback_bindings": _artifact(repo / CALLBACK_BINDINGS, repo),
            "callback_join": _artifact(repo / CALLBACK_JOIN, repo),
            "target_area_campaign_receipt": target_area_artifact,
            "target_score_campaign_receipt": target_score_artifact,
            "score_effect_ancestry": ancestry_artifact,
            "complete_enemy_tournament_receipt": tournament_artifact,
        },
    }


def archive_enemy_skill_effect_callback_campaign(
    source_root: Path,
    output_root: Path,
) -> Path:
    """Copy only immutable pair plans and accepted outputs into the repo."""
    source = source_root.resolve()
    output = Path(os.path.abspath(output_root))
    if output.exists() or output.is_symlink():
        raise EnemySkillEffectCallbackCampaignError(
            f"campaign archive already exists: {output}"
        )
    if source.is_symlink() or not source.is_dir():
        raise EnemySkillEffectCallbackCampaignError(
            f"campaign source is invalid: {source}"
        )
    output.mkdir(parents=True)
    for pair_name in PAIR_SPECS:
        source_pair = source / pair_name
        destination_pair = output / pair_name
        destination_pair.mkdir()
        plans = list(source_pair.glob("*_pair_plan.json"))
        if len(plans) != 1:
            raise EnemySkillEffectCallbackCampaignError(
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
    return output


def publish_enemy_skill_effect_callback_campaign_receipt(
    value: Mapping[str, Any],
    output: Path,
) -> tuple[Path, str]:
    """Create one immutable canonical skill-effect campaign receipt."""
    path = output.resolve()
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise EnemySkillEffectCallbackCampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
