from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.observatory.msvc_rng_replay import (
    advance_state,
    result_from_advanced_state,
)
from src.observatory.spawn_coordinate_capsule_campaign import (
    BREAKPOINT_PLAN,
    BUILD_RECEIPT,
    EXPECTED_BUILD_RECEIPT_SHA256,
    EXPECTED_MODULE_SHA256,
    PAIR_SPECS,
    SpawnCoordinateCapsuleCampaignError,
    build_spawn_coordinate_capsule_campaign_receipt,
    publish_spawn_coordinate_capsule_campaign_receipt,
)
from src.observatory.spawn_coordinate_capsule_hw import (
    EXPECTED_BOUNDARY_MAP_SHA256,
    EXPECTED_EXECUTABLE_SHA256,
    EXPECTED_FALLBACK_PREBYTES_SHA256,
    EXPECTED_INVENTORY_SHA256,
    EXPECTED_PLAN_SHA256,
    EXPECTED_POSITION_BOUNDARY_SHA256,
    EXPECTED_RNG_OWNER_SHA256,
    EXPECTED_SCHEDULER_PREBYTES_SHA256,
    EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256,
    EXPECTED_SELECTOR_REGION_SHA256,
    EXPECTED_SPAWN_BOUNDARY_SHA256,
    EXPECTED_STANDARD_PREBYTES_SHA256,
    correlate_spawn_coordinate_capsule_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _draw(kind: str, seq: int, raw_rng: int) -> dict:
    count = 4
    selected_index = raw_rng % count
    candidates = [{"x": index, "y": seq} for index in range(count)]
    return {
        "kind": kind,
        "seq": seq,
        "candidate_count": count,
        "selected_index": selected_index,
        "rng_quotient": raw_rng // count,
        "raw_rng": raw_rng,
        "selected_x": candidates[selected_index]["x"],
        "selected_y": candidates[selected_index]["y"],
        "candidates": candidates,
    }


def _snapshot(capture_id: str) -> dict:
    state_before = 0x12345678
    state_after = advance_state(state_before)
    selector_raw = result_from_advanced_state(state_after)
    draws = [
        _draw("scheduler_draw", 0, 101),
        _draw("selector_standard_draw", 1, selector_raw),
    ]
    tiles = []
    block_spawn = []
    for x in range(8):
        for y in range(8):
            occupant_ids = [17] if [x, y] == [3, 3] else []
            tiles.append(
                {
                    "x": x,
                    "y": y,
                    "terrain": 0,
                    "pod_state": 1 if [x, y] == [7, 7] else 0,
                    "item_present": [x, y] == [4, 4],
                    "acid": [x, y] == [2, 2],
                    "dangerous_flag": [x, y] == [1, 1],
                    "occupancy_count": len(occupant_ids),
                    "occupant_ids": occupant_ids,
                }
            )
            block_spawn.append({"x": x, "y": y, "value": int(y == 0)})
    selector = draws[1]
    return {
        "schema_version": 1,
        "kind": "native_spawn_coordinate_capsule_hw_observer_snapshot",
        "observer_version": "observatory-spawn-coordinate-capsule-hw-observer/2",
        "capture_id": capture_id,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": 5_530_112,
            "inventory_sha256": EXPECTED_INVENTORY_SHA256,
            "boundary_map_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
            "spawn_candidate_boundary_sha256": EXPECTED_SPAWN_BOUNDARY_SHA256,
            "position_observations_boundary_sha256": (
                EXPECTED_POSITION_BOUNDARY_SHA256
            ),
            "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
            "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
            "selector_entry_prebytes_sha256": (
                EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256
            ),
            "scheduler_prebytes_sha256": EXPECTED_SCHEDULER_PREBYTES_SHA256,
            "selector_fallback_prebytes_sha256": (
                EXPECTED_FALLBACK_PREBYTES_SHA256
            ),
            "selector_standard_prebytes_sha256": (
                EXPECTED_STANDARD_PREBYTES_SHA256
            ),
            "rng_state_owner_sha256": EXPECTED_RNG_OWNER_SHA256,
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "overflow_count": 0,
            "candidate_error_count": 0,
            "capsule_error_count": 0,
            "rng_error_count": 0,
            "pairing_error_count": 0,
            "pointer_fault_count": 0,
            "transition_mismatch_count": 0,
            "wrong_thread_count": 0,
            "unexpected_breakpoint_count": 0,
            "torn_record_count": 0,
            "torn_capsule_count": 0,
            "debug_registers_armed": False,
            "debug_registers_cleared": True,
            "veh_installed": False,
            "veh_removed": True,
            "executable_file_released": True,
            "executable_bytes_modified": False,
            "seam_bytes_unchanged": True,
            "addresses_or_pointers_published": False,
        },
        "draw_records": draws,
        "capsules": [
            {
                "seq": 0,
                "draw_seq": 1,
                "selector_kind": "selector_standard_draw",
                "board_width": 8,
                "board_height": 8,
                "board_turn": 1,
                "pawn_id": 9,
                "pawn_team": 1,
                "rng_state_before": f"0x{state_before:08x}",
                "rng_state_after": f"0x{state_after:08x}",
                "raw_rng": selector_raw,
                "selected_index": selector["selected_index"],
                "selected_x": selector["selected_x"],
                "selected_y": selector["selected_y"],
                "block_spawn_values": block_spawn,
                "spawn_markers": [{"x": 0, "y": 0}],
                "dangerous_points_a": [{"x": 5, "y": 5}],
                "dangerous_points_b": [{"x": 6, "y": 6}],
                "tiles": tiles,
            }
        ],
        "summary": {
            "draw_record_count": 2,
            "scheduler_count": 1,
            "selector_fallback_count": 0,
            "selector_standard_count": 1,
            "selector_count": 1,
            "capsule_entry_count": 1,
            "capsule_count": 1,
            "thread_count": 1,
            "last_draw_sequence": 1,
            "last_capsule_sequence": 0,
        },
    }


def _outcome(timestamp: int, selected: list[int]) -> dict:
    return {
        "timestamp": timestamp,
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "turn": 2,
        "grid_power": 5,
        "units": [],
        "tiles": [],
        "spawning_tiles": [selected],
    }


def _prepare_campaign(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    build_path = repo / BUILD_RECEIPT
    plan_path = repo / BREAKPOINT_PLAN
    build_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / BUILD_RECEIPT, build_path)
    shutil.copy2(ROOT / BREAKPOINT_PLAN, plan_path)
    build = json.loads(build_path.read_text(encoding="utf-8"))
    campaign = repo / "data" / "observatory" / "captures" / "capsule-campaign"
    base_minute = 0
    for pair_index, (pair_name, order) in enumerate(PAIR_SPECS.items()):
        timestamps = {
            condition: base_minute + order.index(condition) for condition in order
        }
        for condition in ("control", "dormant", "armed"):
            condition_dir = campaign / pair_name / condition
            condition_dir.mkdir(parents=True)
            pair_id = f"spawn-capsule-pair{pair_name[-3:]}"
            capture_id = f"{pair_id}-{condition}"
            snapshot = _snapshot(capture_id)
            selected = [
                snapshot["capsules"][0]["selected_x"],
                snapshot["capsules"][0]["selected_y"],
            ]
            outcome = _outcome(pair_index * 10 + timestamps[condition], selected)
            outcome_path = condition_dir / "outcome.json"
            _write(outcome_path, outcome)

            armed = condition == "armed"
            snapshot_path = condition_dir / "snapshot.json"
            analysis_path = condition_dir / "analysis.json"
            analysis = None
            if armed:
                _write(snapshot_path, snapshot)
                analysis = correlate_spawn_coordinate_capsule_snapshot(
                    snapshot,
                    outcome,
                    build_receipt=build,
                    observed_module_sha256=EXPECTED_MODULE_SHA256,
                )
                _write(analysis_path, analysis)

            summary = snapshot["summary"]
            finish_counts = summary if armed else {
                "draw_record_count": 0,
                "scheduler_count": 0,
                "selector_fallback_count": 0,
                "selector_standard_count": 0,
                "selector_count": 0,
                "capsule_count": 0,
            }
            armed_text = "true" if armed else "false"
            boundary = {
                "condition": condition,
                "capture_id": capture_id,
                "state": "complete",
                "prepare_ack": (
                    "OK OBS_SPAWN_CAPSULE_PREPARE "
                    f"condition={condition} capture={capture_id} "
                    f"seed=324508639 armed={armed_text}"
                ),
                "finish_ack": (
                    "OK OBS_SPAWN_CAPSULE_FINISH "
                    f"condition={condition} capture={capture_id} "
                    f"draws={finish_counts['draw_record_count']} "
                    f"scheduler={finish_counts['scheduler_count']} "
                    f"fallback={finish_counts['selector_fallback_count']} "
                    f"standard={finish_counts['selector_standard_count']} "
                    f"selectors={finish_counts['selector_count']} "
                    f"capsules={finish_counts['capsule_count']} complete=true"
                ),
                "abort_ack": None,
            }
            if armed:
                boundary.update(
                    {
                        "snapshot_sha256": _object_sha256(snapshot),
                        "draw_record_count": summary["draw_record_count"],
                        "scheduler_count": summary["scheduler_count"],
                        "selector_count": summary["selector_count"],
                        "capsule_count": summary["capsule_count"],
                        "seam_bytes_unchanged": True,
                        "debug_registers_cleared": True,
                        "addresses_or_pointers_published": False,
                    }
                )
            minute = pair_index * 10 + timestamps[condition]
            trial = {
                "schema_version": 1,
                "kind": "observatory_spawn_coordinate_capsule_turn_trial",
                "created_at": f"2026-08-29T12:{minute:02d}:00+00:00",
                "pair_id": pair_id,
                "condition": condition,
                "capture_id": capture_id,
                "capture_track": "owner_local_modified",
                "artifact_root": str(campaign),
                "session_file": str(campaign / f"session-{capture_id}.json"),
                "status": "complete",
                "valid_trial": True,
                "module_sha256": EXPECTED_MODULE_SHA256,
                "build_receipt_sha256": EXPECTED_BUILD_RECEIPT_SHA256,
                "pre_dispatch_turn": 1,
                "auto_turn": {
                    "status": "PLAN",
                    "turn": 1,
                    "actions_completed": 3,
                    "desyncs_detected": 0,
                    "end_turn_plan_id": f"plan-{capture_id}",
                    "end_turn_plan_source": "lightning_loop",
                    "end_turn_delivery_mode": "local",
                    "local_end_turn_reserved": True,
                },
                "dispatch": {
                    "status": "DISPATCHED",
                    "dispatch": {
                        "delivery_confirmation": "delivered_confirmed"
                    },
                },
                "boundary": boundary,
                "outcome": {
                    "path": str(outcome_path),
                    "sha256": _file_sha256(outcome_path),
                },
                "snapshot": (
                    {
                        "path": str(snapshot_path),
                        "sha256": _file_sha256(snapshot_path),
                        "draw_record_count": summary["draw_record_count"],
                        "capsule_count": summary["capsule_count"],
                        "complete": True,
                    }
                    if armed
                    else None
                ),
                "analysis": (
                    {
                        "path": str(analysis_path),
                        "sha256": _file_sha256(analysis_path),
                        "kind": analysis["kind"],
                        "status": analysis["status"],
                    }
                    if analysis is not None
                    else None
                ),
                "snapshot_consumed_from_bridge": True,
                "pause_guard": {
                    "status": "OK",
                    "pause_verified": True,
                    "safe_to_think": True,
                },
                "errors": {
                    "reservation": "",
                    "pre_dispatch": "",
                    "dispatch": "",
                    "wait": "",
                    "finish": "",
                    "analysis": "",
                    "snapshot_consume": "",
                    "abort": "",
                    "pause": "",
                },
            }
            _write(condition_dir / "trial.json", trial)
        base_minute += 1
    return repo, campaign


def test_synthetic_capsule_campaign_seals_board_rng_and_neutrality(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)

    receipt = build_spawn_coordinate_capsule_campaign_receipt(
        campaign,
        repository_root=repo,
    )

    assert receipt["results"]["classification"] == (
        "selector_entry_board_rng_capsule_captured"
    )
    assert receipt["results"]["complete_restored_snapshots"] == 3
    assert receipt["results"]["capsule_counts"] == [1, 1, 1]
    assert receipt["results"]["draw_counts"] == [2, 2, 2]
    assert receipt["results"]["all_armed_observations_match"] is True
    assert receipt["results"]["all_semantic_outcomes_match"] is True
    assert receipt["campaign"]["condition_orders"] == list(PAIR_SPECS.values())
    assert receipt["restore"]["cleanup_receipt_pending"] is True
    assert any(
        "complete future spawn forecast" in claim.lower()
        for claim in receipt["claims"]["not_proven"]
    )


def test_capsule_campaign_rejects_semantic_outcome_drift(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    condition_dir = campaign / "pair002" / "armed"
    outcome_path = condition_dir / "outcome.json"
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    outcome["grid_power"] = 4
    _write(outcome_path, outcome)
    trial_path = condition_dir / "trial.json"
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    trial["outcome"]["sha256"] = _file_sha256(outcome_path)
    _write(trial_path, trial)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="whole-game outcomes differ",
    ):
        build_spawn_coordinate_capsule_campaign_receipt(
            campaign,
            repository_root=repo,
        )


def test_capsule_campaign_rejects_counterbalance_order_drift(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    trial_path = campaign / "pair003" / "control" / "trial.json"
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    trial["created_at"] = "2026-08-29T12:20:00+00:00"
    _write(trial_path, trial)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="condition order differs",
    ):
        build_spawn_coordinate_capsule_campaign_receipt(
            campaign,
            repository_root=repo,
        )


def test_capsule_campaign_receipt_publish_is_immutable(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    receipt = build_spawn_coordinate_capsule_campaign_receipt(
        campaign,
        repository_root=repo,
    )
    output = repo / "capsule-receipt.json"

    path, digest = publish_spawn_coordinate_capsule_campaign_receipt(
        receipt,
        output,
    )

    assert path == output.resolve()
    assert digest == _file_sha256(output)
    with pytest.raises(SpawnCoordinateCapsuleCampaignError, match="already exists"):
        publish_spawn_coordinate_capsule_campaign_receipt(receipt, output)
