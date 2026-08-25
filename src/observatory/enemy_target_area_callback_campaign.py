"""Seal the synthetic Firefly ``GetTargetArea`` callback campaign.

The campaign deliberately isolates one Lua callback family.  Three fresh
processes each replay the same fixed Firefly1 decision twice: once with the
controller prepared but inactive and once with only ``GetTargetArea`` active.
This module validates the raw trials, proves paired outcome neutrality and
slot restoration, and correlates the ordered callback payloads with the
separately sealed complete native enemy-record tournament.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.observatory.callback_trial_result import (
    compare_callback_trial_results,
    validate_callback_trial_result,
)
from src.observatory.enemy_tournament_hw_campaign import EXPECTED_CANDIDATES
from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_enemy_target_area_callback_campaign_receipt"
SAVE_TREE_SHA256 = (
    "cfdb040ab907f854595b5760d1da4492886e6f9240c6d6a5a90886e1b6686c11"
)
SEMANTIC_SHA256 = (
    "957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673"
)
BUILD_IDENTITY_SHA256 = (
    "e3e93229f5e216a397088f11051aa6c8e3763b0aa70cd05552c4717e8696dd11"
)
INSTALLED_EXPERIMENT_MODLOADER_SHA256 = (
    "07af106b8cc2abab88fd215ed0ddfe04fc138ba9c4987f2500a445509898071d"
)
BINDING_MANIFEST_SHA256 = (
    "d6b25a368df6cbe9d556f56c7dc0e94531369d0ac2f97ad5ac0d4a169b7d9eb3"
)
CALLBACK_JOIN_DOCUMENT_SHA256 = (
    "018ea315ab5e5324dfc2c8949b693ee49aa76c38a8185360fa92157511fb42fc"
)
HOOK_COVERAGE_SHA256 = (
    "3e4faf92b8f08a4da75a04c3e7490e4731e7ad61d5d5f761c7292781224eeee4"
)
CONTROLLER_SHA256 = (
    "4c30aeb71aa53332f1558133205e716c40230e0db4dbc08f386c23cd2f69fdee"
)
TRIAL_HOST_SHA256 = (
    "6477d7e5d631628b4ba3c1d7a306658702a3e91f3d674aff354e9182483f6925"
)

INVENTORY = Path("data/observatory/inventories") / (
    "windows_build_13725832_31fe35265598_local_modified.json"
)
CALLBACK_BINDINGS = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260822T025049Z_"
    "callback_bindings_live_slot_update.json"
)
CALLBACK_JOIN = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260821T201929Z_"
    "callback_join.json"
)
TOURNAMENT_RECEIPT = Path("data/observatory/captures") / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_tournament_hw_receipt.json"
)
MODLOADER_SOURCE = Path("src/bridge/modloader.lua")
CONTROLLER_SOURCE = Path("src/bridge/observatory_callback_controller.lua")
TRIAL_HOST_SOURCE = Path("src/bridge/observatory_callback_trial_host.lua")

EXPECTED_SCENARIO = {
    "consumed_spawn_count": 0,
    "pawn_id": 1303,
    "pawn_type": "Firefly1",
    "start": [4, 4],
}
SELECTED_INPUT_INDEX = 5
PAIR_SPECS = {
    "pair001": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "d1c0fb4a41856a8ff67b072f2dffa6877f858f3ac934fc2db9d83e1965c7ae84"
        ),
        "arm_packet_sha256": (
            "c1e74755c00a630b9fa106ea1316a41c3d4b0f35162b29985d1ff5a9b06416b4"
        ),
        "capsule_sha256": (
            "c571cbac8c093b88f27563475b63073b88a8f85ec982cb1550883cea57e2b9ab"
        ),
    },
    "pair002": {
        "order": ["exact_hook", "control"],
        "plan_sha256": (
            "33f7358a30e10623a506f37c4fa1e62f0762ea8c26c2e99430c714fda8ef51ea"
        ),
        "arm_packet_sha256": (
            "fb98dd64811a6a3736e17d438f727ef16be17717b4bcc5377b564cab29bab28b"
        ),
        "capsule_sha256": (
            "1d54636dff684585477887ee074c3fd295336c36bf537ca38860b70395387db6"
        ),
    },
    "pair003": {
        "order": ["control", "exact_hook"],
        "plan_sha256": (
            "69d1622bdcd9c7d8819c09c1b2553e78d469a58696a15fe1cb272d384f5fe16e"
        ),
        "arm_packet_sha256": (
            "6732fb3c103c261f6f54b4d72140c2eaef5daeb249f54cad2508844cd8f9e7a7"
        ),
        "capsule_sha256": (
            "79acb588c9fe7174dff8d64df5005e4622e013e77240f6a5c7e77b67c45fe5cd"
        ),
    },
}
PAIR_FILES = frozenset(
    {
        "pair_plan.json",
        "control_trial.json",
        "control_outcome.json",
        "control_result.json",
        "exact_hook_trial.json",
        "exact_hook_outcome.json",
        "exact_hook_result.json",
        "exact_hook_trace.json",
    }
)
ATTEMPTED_FAMILIES = frozenset(
    {
        "enemy_action_selected",
        "enemy_candidate",
        "enemy_target_score",
        "get_skill_effect",
        "get_target_area",
        "random_bool",
        "random_int",
        "score_positioning",
    }
)
_CAPTURE_ID_RE = re.compile(r"^firefly-target-area-pair-00[1-3]$")


def _target_area(origin: list[int]) -> list[list[int]]:
    x, y = origin
    return [[x, y - 1], [x + 1, y], [x, y + 1], [x - 1, y]]


EXPECTED_TARGET_AREA_EVENTS = [
    {
        "call_order": index,
        "origin": [record["destination_x"], record["destination_y"]],
        "pawn_uid": 1303,
        "payload_version": 1,
        "representation": "coordinate_list",
        "skill_id": "FireflyAtk1",
        "target_area": _target_area(
            [record["destination_x"], record["destination_y"]]
        ),
    }
    for index, record in enumerate(EXPECTED_CANDIDATES)
]
EXPECTED_TARGET_AREA_EVENTS.append(
    {
        **EXPECTED_TARGET_AREA_EVENTS[SELECTED_INPUT_INDEX],
        "call_order": len(EXPECTED_CANDIDATES),
    }
)


class EnemyTargetAreaCallbackCampaignError(RuntimeError):
    """Raised when target-area evidence is missing or inconsistent."""


def _stable_bytes(path: Path, label: str) -> bytes:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise EnemyTargetAreaCallbackCampaignError(
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
        raise EnemyTargetAreaCallbackCampaignError(f"{label} changed while read")
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
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    return _sha256(payload)


def _load(path: Path, label: str) -> dict[str, Any]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnemyTargetAreaCallbackCampaignError(
            f"invalid {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise EnemyTargetAreaCallbackCampaignError(f"{label} must be an object")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EnemyTargetAreaCallbackCampaignError(f"{label} must be an object")
    return value


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise EnemyTargetAreaCallbackCampaignError(
            f"artifact is outside the repository: {resolved}"
        ) from exc
    data = _stable_bytes(resolved, relative)
    return {"path": relative, "size": len(data), "sha256": _sha256(data)}


def _created_at(trial: Mapping[str, Any], label: str) -> datetime:
    value = trial.get("created_at")
    if type(value) is not str:
        raise EnemyTargetAreaCallbackCampaignError(f"{label} created_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnemyTargetAreaCallbackCampaignError(
            f"{label} created_at is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise EnemyTargetAreaCallbackCampaignError(
            f"{label} created_at lacks a timezone"
        )
    return parsed


def _metadata_digest(
    value: object,
    path: Path,
    label: str,
) -> Mapping[str, Any]:
    metadata = _mapping(value, f"{label} metadata")
    if metadata.get("sha256") != _sha256(_stable_bytes(path, label)):
        raise EnemyTargetAreaCallbackCampaignError(f"{label} digest differs")
    return metadata


def _validate_plan(
    path: Path,
    *,
    pair_name: str,
    spec: Mapping[str, str | list[str]],
    repository_root: Path,
) -> dict[str, Any]:
    data = _stable_bytes(path, f"{pair_name} pair plan")
    if _sha256(data) != spec["plan_sha256"]:
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} pair-plan digest differs"
        )
    plan = _load(path, f"{pair_name} pair plan")
    capture_id = f"firefly-target-area-pair-{pair_name[-3:]}"
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("kind") != "observatory_callback_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("conditions") != ["control", "exact_hook"]
        or plan.get("callback_family") != "get_target_area"
        or plan.get("capture_id") != capture_id
        or _CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} pair-plan identity differs"
        )
    artifacts = _mapping(plan.get("artifacts"), f"{pair_name} plan artifacts")
    expected_repository_artifacts = {
        "inventory": INVENTORY,
        "bindings": CALLBACK_BINDINGS,
        "callback_join": CALLBACK_JOIN,
        "installed_modloader": MODLOADER_SOURCE,
        "controller": CONTROLLER_SOURCE,
        "trial_host": TRIAL_HOST_SOURCE,
    }
    for key, relative in expected_repository_artifacts.items():
        metadata = _mapping(artifacts.get(key), f"{pair_name} plan {key}")
        actual = _sha256(
            _stable_bytes(repository_root / relative, f"repository {key}")
        )
        if metadata.get("sha256") != actual:
            raise EnemyTargetAreaCallbackCampaignError(
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
        raise EnemyTargetAreaCallbackCampaignError(
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
    capture_id = f"firefly-target-area-pair-{pair_name[-3:]}"
    attempts = 0 if condition == "control" else 9
    ack = (
        "OK OBS_ENEMY_CALLBACK_TRIAL "
        f"condition={condition} family=get_target_area capture={capture_id} "
        "pawn=1303 type=Firefly1 at=4,4 consumed_spawns=0 "
        f"attempts={attempts} events={attempts} complete=true"
    )
    if (
        trial.get("schema_version") != SCHEMA_VERSION
        or trial.get("kind") != "observatory_enemy_callback_turn_trial"
        or trial.get("pair_id") != pair_name
        or trial.get("condition") != condition
        or trial.get("capture_id") != capture_id
        or trial.get("callback_family") != "get_target_area"
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
        raise EnemyTargetAreaCallbackCampaignError(
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
        raise EnemyTargetAreaCallbackCampaignError(
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
        or trace.get("controller_version") != "observatory-callback-controller/1"
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
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} trace identity differs"
        )
    attempted = _mapping(trace.get("attempted_calls"), f"{pair_name} attempts")
    if set(attempted) != ATTEMPTED_FAMILIES or any(
        attempted[key] != (9 if key == "get_target_area" else 0)
        for key in ATTEMPTED_FAMILIES
    ):
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} trace attempted-call vector differs"
        )
    summary = _mapping(trace.get("summary"), f"{pair_name} trace summary")
    if (
        summary.get("accepted_events") != 9
        or summary.get("dropped_events") != 0
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
        or summary.get("stop_reasons") != []
        or summary.get("truncation_reasons") != []
    ):
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} trace integrity differs"
        )
    coverage = trace.get("hook_coverage")
    if not isinstance(coverage, list) or len(coverage) != 69:
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} hook coverage count differs"
        )
    installed = [
        item
        for item in coverage
        if isinstance(item, Mapping) and item.get("status") == "installed"
    ]
    if (
        len(installed) != 11
        or any(item.get("event_kind") != "get_target_area" for item in installed)
        or any(
            not isinstance(item, Mapping)
            or item.get("status") not in {"installed", "disabled"}
            or (
                item.get("status") == "installed"
                and item.get("event_kind") != "get_target_area"
            )
            for item in coverage
        )
    ):
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} activated more than GetTargetArea"
        )

    events = trace.get("events")
    if not isinstance(events, list) or len(events) != 9:
        raise EnemyTargetAreaCallbackCampaignError(
            f"{pair_name} target-area event count differs"
        )
    payloads: list[dict[str, Any]] = []
    for index, (event, expected_payload) in enumerate(
        zip(events, EXPECTED_TARGET_AREA_EVENTS, strict=True)
    ):
        if (
            not isinstance(event, Mapping)
            or set(event)
            != {"context", "kind", "mission_id", "payload", "phase", "seq", "turn"}
            or event.get("seq") != index
            or event.get("kind") != "get_target_area"
            or event.get("mission_id") != "Mission_Power"
            or event.get("phase") != "combat_enemy"
            or event.get("turn") != 1
            or event.get("context")
            != {
                "call_site": "runtime.callback.slot-0001.GetTargetArea.fn-0001",
                "source": "fn-0001",
            }
            or event.get("payload") != expected_payload
        ):
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} target-area event {index} differs"
            )
        payloads.append(dict(expected_payload))
    return {
        "attempted_calls": 9,
        "accepted_events": 9,
        "serialization_errors": 0,
        "restore_conflicts": 0,
        "installed_get_target_area_slots": len(installed),
        "event_payloads": payloads,
        "event_payloads_sha256": _object_sha256(payloads),
    }


def _validate_tournament_receipt(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = repository_root / TOURNAMENT_RECEIPT
    receipt = _load(path, "enemy-tournament receipt")
    results = _mapping(receipt.get("results"), "enemy-tournament results")
    pairs = receipt.get("pairs")
    if (
        receipt.get("kind") != "observatory_enemy_tournament_hw_campaign_receipt"
        or results.get("classification")
        != "complete_enemy_record_tournament_runtime_replay"
        or results.get("selected_input_indices") != [5, 5, 5]
        or results.get("semantic_sha256") != SEMANTIC_SHA256
        or not isinstance(pairs, list)
        or len(pairs) != 3
        or any(
            not isinstance(pair, Mapping)
            or not isinstance(pair.get("observation"), Mapping)
            or pair["observation"].get("candidate_records") != EXPECTED_CANDIDATES
            for pair in pairs
        )
    ):
        raise EnemyTargetAreaCallbackCampaignError(
            "complete enemy-tournament receipt differs"
        )
    return receipt, _artifact(path, repository_root)


def build_enemy_target_area_callback_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate three counterbalanced target-area pairs and return a receipt."""
    root = campaign_root.resolve()
    repo = repository_root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise EnemyTargetAreaCallbackCampaignError(
            f"campaign root is invalid: {root}"
        )
    actual_pairs = {
        item.name for item in root.iterdir() if item.is_dir() and not item.is_symlink()
    }
    other = {
        item.name for item in root.iterdir() if not item.is_dir() or item.is_symlink()
    }
    if actual_pairs != set(PAIR_SPECS) or other:
        raise EnemyTargetAreaCallbackCampaignError("campaign pair set differs")

    tournament, tournament_artifact = _validate_tournament_receipt(repo)
    pairs: list[dict[str, Any]] = []
    event_payloads_sha256: str | None = None
    semantic_sha256: str | None = None
    runtime_identity: dict[str, Any] | None = None
    for pair_name, spec in PAIR_SPECS.items():
        pair_dir = root / pair_name
        actual_files = {
            item.name for item in pair_dir.iterdir() if item.is_file() and not item.is_symlink()
        }
        if actual_files != PAIR_FILES or any(
            item.is_dir() or item.is_symlink() for item in pair_dir.iterdir()
        ):
            raise EnemyTargetAreaCallbackCampaignError(
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
                or result["callback_family"] != "get_target_area"
                or result["binding_manifest_sha256"] != BINDING_MANIFEST_SHA256
                or result["callback_join_sha256"] != CALLBACK_JOIN_DOCUMENT_SHA256
                or result["slot_count"] != 65
                or result["serialization_errors"] != 0
            ):
                raise EnemyTargetAreaCallbackCampaignError(
                    f"{pair_name} {condition} result identity differs"
                )
            trials[condition] = trial
            results[condition] = result
            outcomes[condition] = _load(
                pair_dir / f"{condition}_outcome.json",
                f"{pair_name} {condition} outcome",
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
        if actual_order != spec["order"]:
            raise EnemyTargetAreaCallbackCampaignError(
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
            or direct.get("exact_hook_attempted_calls") != 9
            or direct.get("exact_hook_event_count") != 9
            or direct.get("both_restored") is not True
        ):
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} callback comparison differs"
            )
        outcome = compare_rng_trial_outcomes(
            outcomes["control"],
            outcomes["exact_hook"],
            capture_id=f"enemy-target-area-{pair_name}",
        )
        if outcome.get("status") != "matched" or outcome.get("difference_count") != 0:
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} whole-game outcomes differ"
            )
        if outcome.get("control_semantic_sha256") != SEMANTIC_SHA256:
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} semantic outcome differs"
            )
        if semantic_sha256 is None:
            semantic_sha256 = outcome["control_semantic_sha256"]
        elif semantic_sha256 != outcome["control_semantic_sha256"]:
            raise EnemyTargetAreaCallbackCampaignError(
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
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} target-area event stream differs"
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
            raise EnemyTargetAreaCallbackCampaignError(
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
                    "attempted_calls": 9,
                    "accepted_events": 9,
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
    correlation = []
    for index, (candidate, payload) in enumerate(
        zip(EXPECTED_CANDIDATES, EXPECTED_TARGET_AREA_EVENTS[:8], strict=True)
    ):
        target = [candidate["target_x"], candidate["target_y"]]
        if payload["origin"] != [
            candidate["destination_x"],
            candidate["destination_y"],
        ] or target not in payload["target_area"]:
            raise EnemyTargetAreaCallbackCampaignError(
                f"candidate {index} target-area correlation differs"
            )
        correlation.append(
            {
                "candidate_index": index,
                "call_order": index,
                "origin": payload["origin"],
                "candidate_target": target,
                "candidate_target_area_index": payload["target_area"].index(target),
                "target_area": payload["target_area"],
            }
        )
    selected_repeat = EXPECTED_TARGET_AREA_EVENTS[-1]
    if selected_repeat["origin"] != correlation[SELECTED_INPUT_INDEX]["origin"]:
        raise EnemyTargetAreaCallbackCampaignError(
            "selected-destination repeat differs"
        )

    inventory_path = repo / INVENTORY
    inventory = _load(inventory_path, "owner-local inventory")
    tournament_results = _mapping(tournament["results"], "tournament results")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": {
            "platform": inventory["platform"],
            "architecture": inventory["executable"]["architecture"],
            "build_id": inventory["steam"]["build_id"],
            "depot_manifest": inventory["steam"]["installed_depots"][0]["manifest"],
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
            "callback_family": "get_target_area",
            "condition_orders": [pair["condition_order"] for pair in pairs],
            "fresh_processes": 3,
            "fixed_seed": 324_508_639,
            "save_tree_sha256": SAVE_TREE_SHA256,
            "scenario": EXPECTED_SCENARIO,
        },
        "pairs": pairs,
        "correlation": {
            "native_candidate_source": tournament_artifact,
            "native_candidate_vector_sha256": tournament_results[
                "stable_candidate_vector_sha256"
            ],
            "candidate_count": 8,
            "candidate_calls": correlation,
            "selected_input_index": SELECTED_INPUT_INDEX,
            "selected_destination_repeat": {
                "call_order": 8,
                "origin": selected_repeat["origin"],
                "target_area": selected_repeat["target_area"],
                "matches_candidate_call_order": SELECTED_INPUT_INDEX,
            },
        },
        "results": {
            "classification": (
                "fixed_firefly_get_target_area_runtime_order_correlated_to_"
                "complete_native_tournament"
            ),
            "complete_restored_pairs": len(pairs),
            "control_attempt_counts": [0, 0, 0],
            "exact_attempt_counts": [9, 9, 9],
            "exact_event_counts": [9, 9, 9],
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
                    "processes emitted the same nine ordered GetTargetArea calls "
                    "while every matched control emitted none."
                ),
                (
                    "The first eight call origins equal the complete native "
                    "tournament's eight candidate destinations in order, and "
                    "each native candidate target is coordinate index three of "
                    "the corresponding four-point Lua PointList."
                ),
                (
                    "The ninth call repeats candidate input 5's destination and "
                    "PointList; that input is the record selected by the "
                    "separately sealed native selector replay in this "
                    "deterministic scenario."
                ),
                (
                    "Every control/exact whole-game outcome matched semantically, "
                    "all 65 slots were restored, and all exact calls serialized "
                    "with zero drops, errors, or restore conflicts."
                ),
            ],
            "not_proven": [
                (
                    "A universal GetTargetArea call count, PointList, target choice, "
                    "or selected-destination repeat for other boards, enemies, "
                    "weapons, cancellation, or retarget paths."
                ),
                (
                    "A same-process dual-observer causal ordering between each Lua "
                    "callback and the native record seam; the correlation joins "
                    "separately counterbalanced deterministic campaigns."
                ),
                (
                    "Candidate-time Board predicates, GetSkillEffect values, "
                    "GetTargetScore values, ScorePositioning values, target-tie RNG "
                    "state, or transitive native-helper RNG."
                ),
                (
                    "Prospective enemy forecasting from ordinary solver input or "
                    "pristine-depot behavior."
                ),
            ],
        },
        "solver_conformance": {
            "resolved_rule": (
                "For the fixed Firefly1 payload, preserve the observed ordered "
                "four-point target areas and bind the first eight origins to "
                "the complete native candidate destination order"
            ),
            "capture_backed_test": (
                "test_committed_target_area_campaign_correlates_native_candidates"
            ),
            "rust_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The Rust simulator consumes the authoritative settled queue; "
                "ordinary solver input still lacks prospective Lua PointLists, "
                "candidate-time Board state, and selector-entry RNG state."
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
            "complete_enemy_tournament_receipt": tournament_artifact,
        },
    }


def archive_enemy_target_area_callback_campaign(
    source_root: Path,
    output_root: Path,
) -> Path:
    """Copy only immutable pair plans and accepted raw outputs into the repo."""
    source = source_root.resolve()
    output = Path(os.path.abspath(output_root))
    if output.exists() or output.is_symlink():
        raise EnemyTargetAreaCallbackCampaignError(
            f"campaign archive already exists: {output}"
        )
    if source.is_symlink() or not source.is_dir():
        raise EnemyTargetAreaCallbackCampaignError(
            f"campaign source is invalid: {source}"
        )
    output.mkdir(parents=True)
    for pair_name in PAIR_SPECS:
        source_pair = source / pair_name
        destination_pair = output / pair_name
        destination_pair.mkdir()
        plans = list(source_pair.glob("*_pair_plan.json"))
        if len(plans) != 1:
            raise EnemyTargetAreaCallbackCampaignError(
                f"{pair_name} source pair plan is ambiguous"
            )
        sources = {"pair_plan.json": plans[0]}
        for condition in ("control", "exact_hook"):
            sources[f"{condition}_trial.json"] = source_pair / condition / "trial.json"
            sources[f"{condition}_outcome.json"] = source_pair / condition / "outcome.json"
            sources[f"{condition}_result.json"] = source_pair / condition / "result.json"
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


def publish_enemy_target_area_callback_campaign_receipt(
    value: Mapping[str, Any],
    output: Path,
) -> tuple[Path, str]:
    """Create one immutable canonical target-area campaign receipt."""
    path = output.resolve()
    payload = _canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise EnemyTargetAreaCallbackCampaignError(
            f"campaign receipt already exists: {path}"
        ) from exc
    return path, _sha256(payload)
