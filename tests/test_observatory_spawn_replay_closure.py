from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.content_inventory import compare_inventories


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data" / "observatory" / "captures"
CLEANUP_RECEIPT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_"
    "spawn_replay_cleanup_receipt.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(value: dict) -> Path:
    path = ROOT / value["path"]
    payload = path.read_bytes()
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


def test_cleanup_receipt_closes_spawn_replay_campaign_and_owner_state():
    receipt = _load(CLEANUP_RECEIPT)
    assert receipt["kind"] == "observatory_spawn_replay_cleanup_receipt"
    assert receipt["capture_track"] == "owner_local_modified"

    campaign_path = _artifact(receipt["campaign_evidence"])
    campaign = _load(campaign_path)
    assert campaign["kind"] == "observatory_spawn_replay_campaign_receipt"
    assert campaign["restore"] == {
        "install_restoration_pending": True,
        "save_restoration_pending": True,
        "save_tree_sha256": receipt["save_restore"]["tree_sha256"],
    }
    pending = receipt["supersedes_pending_state"]
    assert pending["receipt"] == campaign_path.relative_to(ROOT).as_posix()
    assert pending["prior_value"] is True
    assert pending["resolved"] is True

    accepted_path = _artifact(receipt["install_restore"]["accepted_inventory"])
    restored_path = _artifact(receipt["install_restore"]["post_cleanup_inventory"])
    comparison = compare_inventories(_load(accepted_path), _load(restored_path))
    assert comparison["summary"] == receipt["install_restore"][
        "comparison_summary"
    ]
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
    assert save_manifest["file_count"] == receipt["save_restore"][
        "verified_file_count"
    ]
    assert save_manifest["total_bytes"] == receipt["save_restore"][
        "verified_byte_count"
    ]
    assert save_manifest["tree_sha256"] == receipt["save_restore"]["tree_sha256"]
    assert _canonical_sha256(save_manifest["files"]) == save_manifest["tree_sha256"]
    assert receipt["save_restore"]["file_set_and_bytes_match"] is True

    assert receipt["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert all(value is False for value in receipt["terminal_state"].values())
    assert (ROOT / receipt["install_restore"]["cleanup_operation"]["tool"]).is_file()
