import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    REPO_ROOT
    / "data"
    / "observatory"
    / "captures"
    / "windows_build_13725832_owner_local_modified_20260821_callback_receipt.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_artifact(artifact: dict) -> Path:
    path = REPO_ROOT / artifact["path"]
    payload = path.read_bytes()
    assert len(payload) == artifact["size"]
    assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    return path


def test_owner_callback_capture_receipt_binds_committed_evidence():
    receipt = _load_json(RECEIPT_PATH)

    assert receipt["kind"] == "observatory_callback_manifest_capture_receipt"
    assert receipt["capture_track"] == "owner_local_modified"
    assert receipt["build_identity"] == {
        "architecture": "x86",
        "build_id": "13725832",
        "depot_manifest": "8335438558621014449",
        "executable_sha256": (
            "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        ),
        "maps_revision_sha256": (
            "a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4"
        ),
        "platform": "windows",
        "scripts_revision_sha256": (
            "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
        ),
    }

    complete_attempts = [
        attempt for attempt in receipt["attempts"] if "artifact" in attempt
    ]
    assert len(complete_attempts) == 2
    manifest_paths = [
        _assert_artifact(attempt["artifact"]) for attempt in complete_attempts
    ]
    manifest_payloads = [path.read_bytes() for path in manifest_paths]
    assert manifest_payloads[0] == manifest_payloads[1]
    assert receipt["determinism"] == {
        "byte_identical": True,
        "fresh_process_count": 2,
        "manifest_sha256": hashlib.sha256(manifest_payloads[0]).hexdigest(),
    }

    _assert_artifact(receipt["inventory"])
    _assert_artifact(receipt["lexical_index"]["artifact"])
    _assert_artifact(receipt["restore"]["artifact"])
    _assert_artifact(receipt["whole_install_after_restore"]["artifact"])
    join_path = _assert_artifact(receipt["runtime_join"]["artifact"])

    manifest = json.loads(manifest_payloads[0])
    join = _load_json(join_path)
    assert join["runtime_manifest"] == manifest
    assert manifest["summary"] == receipt["runtime_summary"]
    assert join["summary"] == receipt["runtime_join"]["summary"]
    assert join["summary"]["join_status_counts"] == {
        "ambiguous": 0,
        "c_function": 0,
        "debug_unavailable": 0,
        "matched": 65,
        "truncated_source": 0,
        "unmatched": 0,
        "unresolved_line": 0,
        "unresolved_source": 0,
    }


def test_owner_callback_capture_receipt_preserves_safety_limits():
    receipt = _load_json(RECEIPT_PATH)

    failed = receipt["attempts"][0]
    assert failed["status"] == "failed_closed"
    assert "Garden_Atk" in failed["ack"]
    assert receipt["instrumentation"]["native_hook_installed"] is False
    assert (
        receipt["instrumentation"]["candidate_callback_invoked_or_wrapped"]
        is False
    )
    assert receipt["restore"]["mismatch_count"] == 0
    assert receipt["restore"]["remaining_experimental_file_count"] == 0
    assert receipt["restore"]["extra_profile_file_count"] == 0
    assert receipt["whole_install_after_restore"]["comparison_summary"] == {
        "changed": 0,
        "identical": 689,
        "missing": 0,
        "platform_specific": 0,
    }
    assert "pristine Steam depot neutrality" in receipt["claims"]["not_proven"]
