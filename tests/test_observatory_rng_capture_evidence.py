from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.trace_codec import parse_trace


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data" / "observatory" / "captures"
NATIVE = ROOT / "data" / "observatory" / "native"
RECEIPT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260821_"
    "rng_pair004_rejected_receipt.json"
)
HELPER_RECEIPT = (
    NATIVE
    / "windows_build_13725832_31fe35265598_rng_seed_helper_receipt.json"
)
OBSERVER_RECEIPT = (
    NATIVE
    / "windows_build_13725832_31fe35265598_rng_core_observer_receipt.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(item: dict) -> Path:
    path = ROOT / item["path"]
    payload = path.read_bytes()
    assert len(payload) == item["size"]
    assert hashlib.sha256(payload).hexdigest() == item["sha256"]
    return path


def test_rejected_pair4_receipt_binds_the_negative_runtime_evidence():
    receipt = _load(RECEIPT)
    assert receipt["kind"] == "observatory_rng_trial_rejected_pair_receipt"
    assert receipt["capture_track"] == "owner_local_modified"
    assert receipt["rejection"]["status"] == "rejected_for_matched_neutrality"
    assert receipt["rejection"]["classification"] == (
        "uncontrolled_process_local_native_rng_state"
    )
    assert receipt["probe"] == {
        "control_result": 4678,
        "exact_hook_result": 337,
        "kind": "random_int",
        "matched": False,
        "upper_bound": 65521,
    }
    assert receipt["restore"]["save_restored_to_sealed_baseline"] is True
    assert receipt["restore"]["install_restoration_pending"] is True

    paths = {
        name: _artifact(item)
        for name, item in receipt["artifacts"].items()
    }
    control = _load(paths["control_result"])
    exact = _load(paths["exact_hook_result"])
    assert control["condition"] == "control"
    assert exact["condition"] == "exact_hook"
    assert control["capture_id"] == exact["capture_id"] == receipt["capture_id"]
    assert control["capsule_sha256"] == exact["capsule_sha256"]
    assert control["arm_packet_sha256"] == exact["arm_packet_sha256"]
    assert control["runtime_before"] | {"now_epoch": 0} == (
        exact["runtime_before"] | {"now_epoch": 0}
    )
    assert control["target_restored"] is exact["target_restored"] is True
    assert control["raw_written"] is False
    assert exact["raw_written"] is True
    assert control["probe"]["result"] != exact["probe"]["result"]

    comparison = _load(paths["outcome_comparison"])
    assert comparison["status"] == "mismatched"
    assert comparison["differences"] == receipt["outcome"]["differences"]
    assert comparison["difference_count"] == 1

    trace = parse_trace(paths["finalized_trace"].read_text(encoding="utf-8"))
    assert trace["build_identity"] == receipt["build_identity"] | {
        "architectures": None,
        "build_evidence": "local_appmanifest",
    }
    assert trace["capture_identity"]["capture_id"] == receipt["capture_id"]
    assert trace["summary"]["accepted_events"] == 1
    assert trace["events"] == [
        {
            "context": {"call_site": "_G.random_int"},
            "kind": "random_int",
            "mission_id": "Mission_Power",
            "payload": {
                "call_order": 0,
                "result": exact["probe"]["result"],
                "upper_bound": exact["probe"]["upper_bound"],
            },
            "phase": "combat_enemy",
            "seq": 0,
            "turn": 1,
        }
    ]


def test_build_keyed_rng_seed_helper_receipt_binds_reproducible_inputs():
    receipt = _load(HELPER_RECEIPT)
    source = ROOT / receipt["source_path"]
    boundaries = (
        ROOT
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_pe_boundaries.json"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt["source_sha256"]
    assert hashlib.sha256(boundaries.read_bytes()).hexdigest() == (
        receipt["native_boundaries_sha256"]
    )
    assert receipt["module_sha256"] in receipt["module_filename"]
    assert receipt["module_size"] == 73728
    assert receipt["architecture"] == "x86"
    assert receipt["export_name"] == "luaopen_itb_observatory_rng_seed"
    assert "<temporary-build>" in receipt["compiler_stdout"]
    assert "AppData" not in receipt["compiler_stdout"]
    assert not any((ROOT / "data" / "observatory").rglob("*.dll"))


def test_build_keyed_rng_core_observer_receipt_binds_reproducible_inputs():
    receipt = _load(OBSERVER_RECEIPT)
    source = ROOT / receipt["source_path"]
    boundaries = NATIVE / "windows_build_13725832_31fe35265598_pe_boundaries.json"
    hook_plan = (
        NATIVE
        / "windows_build_13725832_31fe35265598_rng_core_hook_plan.json"
    )
    restore_hashes = (
        NATIVE
        / "windows_build_13725832_31fe35265598_rng_core_restore_hashes.json"
    )

    assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt["source_sha256"]
    assert hashlib.sha256(boundaries.read_bytes()).hexdigest() == receipt[
        "boundary_map_file_sha256"
    ]
    assert hashlib.sha256(hook_plan.read_bytes()).hexdigest() == receipt[
        "hook_plan_sha256"
    ]
    assert hashlib.sha256(restore_hashes.read_bytes()).hexdigest() == receipt[
        "restore_manifest_sha256"
    ]
    assert receipt["reproducibility"] == {
        "attestations_identical": True,
        "independent_build_count": 2,
        "module_bytes_identical": True,
    }
    assert receipt["module_sha256"] in receipt["module_filename"]
    assert receipt["hook_plan_sha256"][:12] in receipt["hook_plan_filename"]
    assert receipt["restore_manifest_sha256"][:12] in receipt[
        "restore_hashes_filename"
    ]
    assert receipt["module_size"] == 19968
    assert receipt["architecture"] == "x86"
    assert receipt["export_name"] == "luaopen_itb_observatory_rng_core_observer"
    assert receipt["loaded_or_armed"] is False
    assert "<temporary-build>" in receipt["compiler_stdout"]
    assert "AppData" not in receipt["compiler_stdout"]
    assert not any((ROOT / "data" / "observatory").rglob("*.dll"))
