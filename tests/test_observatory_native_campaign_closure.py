from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from src.observatory.content_inventory import compare_inventories
from src.observatory.runtime_callback_bindings import (
    callback_binding_manifest_sha256,
    validate_runtime_callback_bindings,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = REPO_ROOT / "data" / "observatory" / "captures"
CALLBACK_RECEIPT = (
    CAPTURE_ROOT
    / "windows_build_13725832_owner_local_modified_20260822_callback_bindings_receipt.json"
)
CLEANUP_RECEIPT = (
    CAPTURE_ROOT
    / "windows_build_13725832_owner_local_modified_20260822_native_campaign_cleanup_receipt.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(value: dict) -> Path:
    path = REPO_ROOT / value["path"]
    payload = path.read_bytes()
    assert len(payload) == value["size"]
    assert hashlib.sha256(payload).hexdigest() == value["sha256"]
    return path


def _source_artifact(value: dict) -> Path:
    path = REPO_ROOT / value["path"]
    payload = path.read_bytes()
    if value.get("line_endings") == "lf":
        payload = payload.replace(b"\r\n", b"\n")
    assert len(payload) == value["size"]
    assert hashlib.sha256(payload).hexdigest() == value["sha256"]
    return path


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def test_callback_binding_receipt_binds_two_inert_fresh_process_captures():
    receipt = _load(CALLBACK_RECEIPT)
    assert receipt["kind"] == "observatory_callback_binding_capture_receipt"
    assert receipt["capture_track"] == "owner_local_modified"

    captures = [_artifact(attempt["artifact"]) for attempt in receipt["attempts"]]
    assert len(captures) == 2
    assert captures[0].read_bytes() == captures[1].read_bytes()
    raw_sha256 = hashlib.sha256(captures[0].read_bytes()).hexdigest()
    assert receipt["determinism"] == {
        "fresh_process_count": 2,
        "byte_identical": True,
        "raw_sha256": raw_sha256,
        "canonical_sha256": "d6b25a368df6cbe9d556f56c7dc0e94531369d0ac2f97ad5ac0d4a169b7d9eb3",
    }

    bindings = validate_runtime_callback_bindings(_load(captures[0]))
    assert callback_binding_manifest_sha256(bindings) == receipt["determinism"][
        "canonical_sha256"
    ]
    assert bindings["summary"] == receipt["document"]["summary"]
    assert dict(Counter(slot["method"] for slot in bindings["slots"])) == receipt[
        "document"
    ]["slot_family_counts"]
    assert receipt["instrumentation"]["candidate_callback_invoked_or_wrapped"] is False
    assert receipt["instrumentation"]["native_hook_installed"] is False
    _artifact(receipt["instrumentation"]["deployed_modloader"])
    for source in receipt["instrumentation"]["collector_sources"]:
        _source_artifact(source)


def test_cleanup_receipt_closes_pending_restore_with_exact_inventory_and_save():
    receipt = _load(CLEANUP_RECEIPT)
    assert receipt["kind"] == "observatory_native_campaign_cleanup_receipt"
    assert receipt["capture_track"] == "owner_local_modified"

    campaign_path = _artifact(receipt["campaign_evidence"]["seeded_rng_campaign"])
    callback_path = _artifact(receipt["campaign_evidence"]["callback_bindings"])
    assert callback_path == CALLBACK_RECEIPT
    campaign = _load(campaign_path)
    assert campaign["restore"]["install_restoration_pending"] is True
    assert receipt["supersedes_pending_state"]["resolved"] is True
    assert receipt["supersedes_pending_state"]["receipt"] == str(
        campaign_path.relative_to(REPO_ROOT)
    ).replace("\\", "/")

    accepted_path = _artifact(receipt["install_restore"]["accepted_inventory"])
    restored_path = _artifact(receipt["install_restore"]["post_cleanup_inventory"])
    comparison = compare_inventories(_load(accepted_path), _load(restored_path))
    assert comparison["summary"] == receipt["install_restore"]["comparison_summary"]
    assert comparison["summary"] == {
        "identical": 689,
        "changed": 0,
        "missing": 0,
        "platform_specific": 0,
    }
    accepted = _load(accepted_path)
    accepted_loader = next(
        entry
        for entry in accepted["content"]["scripts"]["files"]
        if entry["path"] == "scripts/modloader.lua"
    )
    assert accepted_loader["sha256"] == receipt["install_restore"][
        "installed_modloader_sha256"
    ]
    assert receipt["install_restore"]["remaining_experimental_file_count"] == 0

    save_manifest = _load(_artifact(receipt["save_restore"]["baseline_manifest"]))
    assert save_manifest["file_count"] == receipt["save_restore"]["verified_file_count"]
    assert save_manifest["total_bytes"] == receipt["save_restore"]["verified_byte_count"]
    assert save_manifest["tree_sha256"] == receipt["save_restore"]["tree_sha256"]
    assert _canonical_sha256(save_manifest["files"]) == save_manifest["tree_sha256"]
    assert receipt["save_restore"]["file_set_and_bytes_match"] is True

    assert receipt["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert receipt["terminal_state"] == {
        "game_process_running": False,
        "native_observer_installed": False,
        "native_seed_helper_installed": False,
        "callback_trial_installed": False,
    }
