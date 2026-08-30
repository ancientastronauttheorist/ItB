from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.observatory.msvc_rng_replay import (
    advance_state,
    result_from_advanced_state,
)
from src.observatory.game_process_identity import (
    EXPECTED_EXECUTABLE_SIZE as EXPECTED_PROCESS_EXECUTABLE_SIZE,
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
from src.observatory.start_state_proof import (
    MANIFEST_KIND,
    MANIFEST_SCHEMA_VERSION,
    PROOF_KIND,
    SCHEMA_VERSION as START_STATE_SCHEMA_VERSION,
    start_state_manifest_sha256,
    start_state_tree_sha256,
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


def _process_identity(repo: Path, *, pid: int, created_at: str) -> dict:
    parsed = datetime.fromisoformat(created_at)
    creation_filetime = (
        int(parsed.timestamp()) * 10_000_000 + 116_444_736_000_000_000
    )
    return {
        "schema_version": 1,
        "kind": "observatory_windows_game_process_identity",
        "pid": pid,
        "creation_filetime": creation_filetime,
        "created_at": datetime.fromtimestamp(
            (creation_filetime - 116_444_736_000_000_000) / 10_000_000.0,
            tz=timezone.utc,
        ).isoformat(),
        "executable_path": str((repo / "Breach.exe").resolve()),
        "executable_size": EXPECTED_PROCESS_EXECUTABLE_SIZE,
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
    }


def _start_state_proof(repo: Path, *, verified_at: str) -> dict:
    files = [
        {"relative_path": "log.txt", "size": 3, "sha256": "1" * 64},
        {
            "relative_path": "profile_Alpha/saveData.lua",
            "size": 4,
            "sha256": "2" * 64,
        },
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "capture_track": "owner_local_modified",
        "profile": "Alpha",
        "file_count": len(files),
        "total_bytes": 7,
        "files": files,
        "tree_sha256": start_state_tree_sha256(files),
    }
    return {
        "schema_version": START_STATE_SCHEMA_VERSION,
        "kind": PROOF_KIND,
        "verified_at": verified_at,
        "game_stopped": True,
        "save_root": str((repo / "live-save").resolve()),
        "snapshot_root": str((repo / "sealed-start-state").resolve()),
        "manifest_sha256": start_state_manifest_sha256(manifest),
        "manifest": manifest,
    }


def _lifecycle(
    repo: Path,
    campaign: Path,
    condition_dir: Path,
    *,
    pair_id: str,
    condition: str,
    capture_id: str,
    minute: int,
    process_identity: dict,
    start_state_proof: dict,
    session_path: Path,
    trial_path: Path,
) -> dict:
    bridge_start = {
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "turn": 1,
        "active_mechs": 3,
        "master_seed": 324508639,
        "region_id": "synthetic-region",
        "timeline_fingerprint": "3" * 64,
        "ai_seed_fingerprint": "4" * 64,
    }
    manifest = start_state_proof["manifest"]
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_capsule_condition_lifecycle",
        "created_at": f"2026-08-29T12:{minute:02d}:42+00:00",
        "pair_id": pair_id,
        "condition": condition,
        "capture_id": capture_id,
        "capture_track": "owner_local_modified",
        "status": "complete",
        "valid_lifecycle": True,
        "artifact_root": str(campaign),
        "condition_root": str(condition_dir),
        "build_identity": {
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_PROCESS_EXECUTABLE_SIZE,
            "module_sha256": EXPECTED_MODULE_SHA256,
            "build_receipt_sha256": EXPECTED_BUILD_RECEIPT_SHA256,
        },
        "restore": {
            "manifest_sha256": start_state_proof["manifest_sha256"],
            "tree_sha256": manifest["tree_sha256"],
            "file_count": manifest["file_count"],
            "total_bytes": manifest["total_bytes"],
        },
        "start_state": {
            "path": str(condition_dir / "start_state_proof.json"),
            "sha256": _file_sha256(condition_dir / "start_state_proof.json"),
            "verified_at": start_state_proof["verified_at"],
            "manifest_sha256": start_state_proof["manifest_sha256"],
            "tree_sha256": manifest["tree_sha256"],
            "game_stopped": True,
        },
        "session": {
            "path": str(session_path),
            "sha256": _file_sha256(session_path),
            "source_path": str((repo / "source-session.json").resolve()),
            "source_sha256": "5" * 64,
        },
        "native_continue": {
            "request_path": str((repo / "native-continue.request").resolve()),
            "armed": True,
            "consumed": True,
            "ack": "OK OBS_NATIVE_CONTINUE_REQUEST invoked=true",
            "cleaned_after_failure": False,
        },
        "launch": {
            "requested_at": f"2026-08-29T12:{minute:02d}:05+00:00",
            "launcher_pid": process_identity["pid"],
            "executable_path": process_identity["executable_path"],
            "executable_size": EXPECTED_PROCESS_EXECUTABLE_SIZE,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        },
        "process_identity": process_identity,
        "bridge_start": bridge_start,
        "bridge_start_sha256": _object_sha256(bridge_start),
        "trial": {
            "path": str(trial_path),
            "sha256": _file_sha256(trial_path),
            "status": "complete",
            "valid_trial": True,
        },
        "close": {
            "method": "WM_CLOSE",
            "requested_at": f"2026-08-29T12:{minute:02d}:40+00:00",
            "closed_at": f"2026-08-29T12:{minute:02d}:41+00:00",
            "pid": process_identity["pid"],
            "creation_filetime": process_identity["creation_filetime"],
            "window_handles": [20_000 + process_identity["pid"]],
            "exited": True,
            "forced_termination": False,
        },
        "errors": {
            "restore": "",
            "start_state": "",
            "session": "",
            "session_cleanup": "",
            "continue_arm": "",
            "launch": "",
            "process": "",
            "bridge_start": "",
            "trial": "",
            "close": "",
            "continue_cleanup": "",
        },
    }


def _campaign_lifecycle(repo: Path, campaign: Path) -> dict:
    order = [
        f"{pair_name}/{condition}"
        for pair_name, conditions in PAIR_SPECS.items()
        for condition in conditions
    ]
    condition_receipts = []
    for key in order:
        pair_name, condition = key.split("/", 1)
        path = campaign / pair_name / condition / "lifecycle.json"
        condition_receipts.append(
            {
                "pair": pair_name,
                "condition": condition,
                "lifecycle_sha256": _file_sha256(path),
            }
        )
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_capsule_campaign_lifecycle",
        "created_at": "2026-08-29T13:00:01+00:00",
        "capture_track": "owner_local_modified",
        "status": "complete",
        "valid_campaign": True,
        "artifact_root": str(campaign),
        "condition_order": order,
        "conditions": condition_receipts,
        "final_restore": _start_state_proof(
            repo,
            verified_at="2026-08-29T13:00:00+00:00",
        ),
        "errors": {
            "conditions": "",
            "final_restore": "",
        },
    }


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
            start_state_path = condition_dir / "start_state_proof.json"
            start_state_proof = _start_state_proof(
                repo,
                verified_at=f"2026-08-29T12:{minute:02d}:00+00:00",
            )
            _write(start_state_path, start_state_proof)
            trial_created_at = f"2026-08-29T12:{minute:02d}:30+00:00"
            process_identity = _process_identity(
                repo,
                pid=10_000
                + pair_index * 3
                + ("control", "dormant", "armed").index(condition),
                created_at=f"2026-08-29T12:{minute:02d}:10+00:00",
            )
            session_path = condition_dir / "session.json"
            trial = {
                "schema_version": 2,
                "kind": "observatory_spawn_coordinate_capsule_turn_trial",
                "created_at": trial_created_at,
                "pair_id": pair_id,
                "condition": condition,
                "capture_id": capture_id,
                "capture_track": "owner_local_modified",
                "artifact_root": str(campaign),
                "session_file": str(session_path),
                "process_identity": process_identity,
                "start_state": {
                    "path": str(start_state_path),
                    "sha256": _file_sha256(start_state_path),
                    "verified_at": start_state_proof["verified_at"],
                    "manifest_sha256": start_state_proof["manifest_sha256"],
                    "tree_sha256": start_state_proof["manifest"]["tree_sha256"],
                },
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
            trial_path = condition_dir / "trial.json"
            _write(trial_path, trial)
            _write(
                session_path,
                {"run_id": f"synthetic-{capture_id}", "mission_index": 0},
            )
            _write(
                condition_dir / "lifecycle.json",
                _lifecycle(
                    repo,
                    campaign,
                    condition_dir,
                    pair_id=pair_id,
                    condition=condition,
                    capture_id=capture_id,
                    minute=minute,
                    process_identity=process_identity,
                    start_state_proof=start_state_proof,
                    session_path=session_path,
                    trial_path=trial_path,
                ),
            )
        base_minute += 1
    _write(
        campaign / "campaign_lifecycle.json",
        _campaign_lifecycle(repo, campaign),
    )
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
    assert receipt["campaign"]["fresh_process_count"] == 9
    assert receipt["campaign"]["all_start_states_match"] is True
    assert receipt["campaign"]["all_lifecycles_complete"] is True
    assert receipt["campaign"]["all_processes_gracefully_closed"] is True
    assert receipt["restore"]["save_restoration_pending"] is False
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
    lifecycle_path = condition_dir / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["trial"]["sha256"] = _file_sha256(trial_path)
    _write(lifecycle_path, lifecycle)

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
    trial_path = campaign / "pair003" / "dormant" / "trial.json"
    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    trial["created_at"] = "2026-08-29T12:25:30+00:00"
    _write(trial_path, trial)
    lifecycle_path = trial_path.parent / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["trial"]["sha256"] = _file_sha256(trial_path)
    lifecycle["close"]["requested_at"] = "2026-08-29T12:25:40+00:00"
    lifecycle["close"]["closed_at"] = "2026-08-29T12:25:41+00:00"
    lifecycle["created_at"] = "2026-08-29T12:25:42+00:00"
    _write(lifecycle_path, lifecycle)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="condition order differs",
    ):
        build_spawn_coordinate_capsule_campaign_receipt(
            campaign,
            repository_root=repo,
        )


def test_capsule_campaign_rejects_reused_process_identity(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    source_path = campaign / "pair001" / "control" / "trial.json"
    target_path = campaign / "pair002" / "control" / "trial.json"
    source_proof_path = source_path.parent / "start_state_proof.json"
    target_proof_path = target_path.parent / "start_state_proof.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    target = json.loads(target_path.read_text(encoding="utf-8"))
    source_proof = json.loads(source_proof_path.read_text(encoding="utf-8"))
    _write(target_proof_path, source_proof)
    target["process_identity"] = source["process_identity"]
    target["start_state"].update(
        {
            "sha256": _file_sha256(target_proof_path),
            "verified_at": source_proof["verified_at"],
            "manifest_sha256": source_proof["manifest_sha256"],
            "tree_sha256": source_proof["manifest"]["tree_sha256"],
        }
    )
    _write(target_path, target)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="process identity was reused",
    ):
        build_spawn_coordinate_capsule_campaign_receipt(
            campaign,
            repository_root=repo,
        )


def test_capsule_campaign_rejects_forced_process_termination(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    lifecycle_path = campaign / "pair001" / "control" / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["close"]["forced_termination"] = True
    _write(lifecycle_path, lifecycle)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="close differs",
    ):
        build_spawn_coordinate_capsule_campaign_receipt(
            campaign,
            repository_root=repo,
        )


def test_capsule_campaign_rejects_native_continue_ack_drift(tmp_path):
    repo, campaign = _prepare_campaign(tmp_path)
    lifecycle_path = campaign / "pair001" / "control" / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    lifecycle["native_continue"]["ack"] = "ERROR: Continue failed"
    _write(lifecycle_path, lifecycle)

    with pytest.raises(
        SpawnCoordinateCapsuleCampaignError,
        match="native Continue differs",
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
