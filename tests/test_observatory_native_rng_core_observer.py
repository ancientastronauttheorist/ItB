from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_rng_core_observer as observer_build
from src.observatory.native_checkpoint import (
    NativeCheckpointError,
    build_rng_core_checkpoint,
    validate_native_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_rng_core_observer.c"
_DIGEST = "a" * 64
_CORE_DIGEST = observer_build.EXPECTED_RNG_CORE_SHA256


def _receipt() -> dict:
    receipt = {
        "schema_version": 1,
        "kind": "observatory_rng_core_observer_build",
        "observer_version": observer_build.OBSERVER_VERSION,
        "architecture": "x86",
        "export_name": observer_build.EXPORT_NAME,
        "module_sha256": _DIGEST,
        "module_size": 18_944,
        "executable_sha256": observer_build.EXPECTED_EXECUTABLE_SHA256,
        "executable_size": observer_build.EXPECTED_EXECUTABLE_SIZE,
        "build_id": observer_build.EXPECTED_BUILD_ID,
        "inventory_canonical_sha256": "b" * 64,
        "boundary_map_canonical_sha256": "c" * 64,
        "rng_return_map_sha256": "d" * 64,
        "hook_plan_sha256": "e" * 64,
        "restore_manifest_sha256": (
            "d7ad5662a8ba8cdce081f56705ea8302ad425e5f7dbf6830ba4056f99408b73d"
        ),
        "rng_core_region_sha256": _CORE_DIGEST,
        "rng_core_rva": "0x00387f16",
        "caller_count": 118,
        "boundary_map_file_sha256": "f" * 64,
        "generated_include_sha256": "1" * 64,
        "source_sha256": "2" * 64,
        "source_path": "src/native/observatory_rng_core_observer.c",
        "module_filename": f"itb_observatory_rng_core_observer_{_DIGEST}.dll",
        "hook_plan_filename": (
            "windows_build_13725832_rng_core_hook_plan_eeeeeeeeeeee.json"
        ),
        "restore_hashes_filename": (
            "windows_build_13725832_rng_core_restore_hashes_d7ad5662a8ba.json"
        ),
        "loaded_or_armed": False,
        "imports": ["bcrypt.dll", "kernel32.dll"],
        "compiler": "Microsoft (R) C/C++ Optimizing Compiler Version test for x86",
        "compiler_stdout": "observatory_rng_core_observer.c",
        "compile_flags": [
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
        ],
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "source_attestation": {
            "entry_abi_source_sha256": "3" * 64,
            "hot_source_sha256": "4" * 64,
            "post_abi_source_sha256": "5" * 64,
        },
        "machine_attestation": {
            "loader_entry_absent": True,
            "pe_entry_point_rva": "0x00000000",
            "observer_enter": {
                "rva": "0x00001000",
                "size": 100,
                "sha256": "6" * 64,
                "instruction_count": 30,
                "branch_count": 4,
                "return_count": 1,
                "direct_or_indirect_call_count": 0,
            },
            "observer_exit": {
                "rva": "0x00001100",
                "size": 100,
                "sha256": "7" * 64,
                "instruction_count": 30,
                "branch_count": 4,
                "return_count": 1,
                "direct_or_indirect_call_count": 0,
            },
            "entry_stub": {
                "rva": "0x00001200",
                "size": 36,
                "sha256": "8" * 64,
                "enter_target_rva": "0x00001000",
                "gateway_pointer_rva": "0x00005000",
                "post_core_rva": "0x00001300",
                "saved_return_offset": 36,
            },
            "post_core_stub": {
                "rva": "0x00001300",
                "size": 33,
                "sha256": "9" * 64,
                "exit_target_rva": "0x00001100",
                "saved_result_offset": 28,
                "return_scratch_offset": -40,
            },
        },
    }
    return receipt


def _snapshot() -> dict:
    receipt = _receipt()
    return {
        "schema_version": 1,
        "kind": "native_rng_core_observer_snapshot",
        "observer_version": observer_build.OBSERVER_VERSION,
        "capture_id": "pair_009_native_rng_core",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "executable_sha256": receipt["executable_sha256"],
            "executable_size": receipt["executable_size"],
            "build_id": receipt["build_id"],
            "inventory_sha256": receipt["inventory_canonical_sha256"],
            "boundary_map_sha256": receipt["boundary_map_canonical_sha256"],
            "rng_return_map_sha256": receipt["rng_return_map_sha256"],
            "hook_plan_sha256": receipt["hook_plan_sha256"],
            "restore_manifest_sha256": receipt["restore_manifest_sha256"],
        },
        "integrity": {
            "state": "restored",
            "overflow_count": 0,
            "unknown_caller_count": 0,
            "torn_record_count": 0,
            "thread_cap_count": 0,
            "nesting_cap_count": 0,
            "thread_recovery_count": 0,
            "loader_lock_recovery_pending": False,
            "restore_conflict": False,
            "patch_installed": False,
            "active_frames": 0,
            "core_bytes_restored": True,
            "hook_bytes_restored": True,
            "page_protection_restored": True,
            "instruction_cache_flushed": True,
            "executable_file_released": True,
            "post_restore_hashes": {"rng_core": _CORE_DIGEST},
            "stopped_reason": None,
            "complete": True,
        },
        "records": [
            {
                "kind": "rng_core",
                "seq": 0,
                "thread_slot": 0,
                "caller_id": 21,
                "result": 12_345,
            },
            {
                "kind": "rng_core",
                "seq": 1,
                "thread_slot": 0,
                "caller_id": 22,
                "result": 23_456,
            },
        ],
        "summary": {
            "record_count": 2,
            "thread_count": 1,
            "last_sequence": 1,
        },
    }


def test_observer_source_has_one_inert_build_keyed_surface():
    source = SOURCE.read_bytes()
    attestation = observer_build._attest_source(source)

    assert set(attestation) == {
        "hot_source_sha256",
        "entry_abi_source_sha256",
        "post_abi_source_sha256",
    }
    text = source.decode("ascii")
    assert text.count("__declspec(dllexport)") == 1
    assert observer_build.EXPORT_NAME in text
    assert "LdrLockLoaderLock" in text
    assert "g_recovery_handles" in text
    assert text.index("restore_entry_patch()") < text.index("push_snapshot(state)")
    for forbidden in (
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "WinHttp",
        "socket(",
    ):
        assert forbidden not in text


def test_builder_requires_no_loader_entry_and_two_reproducible_builds():
    source = (ROOT / "scripts" / "build_itb_observatory_rng_core_observer.py").read_text(
        encoding="utf-8"
    )
    assert '"/NOENTRY"' in source
    assert '"/NODEFAULTLIB"' in source
    assert source.count("_compile_observer_once(environment, include_data)") == 2
    assert '"independent_build_count": 2' in source


def test_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"not the pinned executable")
    boundaries = tmp_path / "boundaries.json"
    boundaries.write_text(json.dumps({}), encoding="utf-8")
    return_map = tmp_path / "return_map.json"
    return_map.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(observer_build.ObserverBuildError, match="pinned observer"):
        observer_build._validate_inputs(executable, boundaries, return_map)


def test_complete_raw_snapshot_finalizes_to_native_checkpoint():
    raw = _snapshot()
    receipt = _receipt()

    checkpoint = build_rng_core_checkpoint(
        raw,
        build_receipt=receipt,
        observed_module_sha256=receipt["module_sha256"],
    )
    result = validate_native_checkpoint(
        checkpoint,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        expected_restore_hashes={"rng_core": _CORE_DIGEST},
    )

    assert checkpoint["kind"] == "native_diagnostic_checkpoint"
    assert checkpoint["identity"]["helper_sha256"] == receipt["module_sha256"]
    assert checkpoint["summary"]["rng_core_count"] == 2
    assert result["reported_complete"] is True
    assert result["identity_verified"] is True
    assert result["restore_hashes_verified"] is True
    assert result["caller_catalog_verified"] is False


def test_raw_snapshot_requires_independently_observed_module_hash():
    with pytest.raises(NativeCheckpointError, match="observed observer module"):
        build_rng_core_checkpoint(
            _snapshot(),
            build_receipt=_receipt(),
            observed_module_sha256="0" * 64,
        )


def test_raw_snapshot_complete_flag_cannot_hide_recovery_handle():
    raw = _snapshot()
    raw["integrity"]["thread_recovery_count"] = 1

    with pytest.raises(NativeCheckpointError, match="complete"):
        build_rng_core_checkpoint(
            raw,
            build_receipt=_receipt(),
            observed_module_sha256=_DIGEST,
        )


def test_raw_snapshot_rejects_caller_outside_build_catalog():
    raw = _snapshot()
    raw["records"][0]["caller_id"] = _receipt()["caller_count"] + 1

    with pytest.raises(NativeCheckpointError, match="caller ID exceeds"):
        build_rng_core_checkpoint(
            raw,
            build_receipt=_receipt(),
            observed_module_sha256=_DIGEST,
        )


def test_raw_snapshot_requires_full_reproducible_build_attestation():
    raw = _snapshot()
    receipt = _receipt()
    del receipt["machine_attestation"]

    with pytest.raises(NativeCheckpointError, match="receipt fields differ"):
        build_rng_core_checkpoint(
            raw,
            build_receipt=receipt,
            observed_module_sha256=_DIGEST,
        )


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("entry_stub", "enter_target_rva"),
        ("entry_stub", "post_core_rva"),
        ("post_core_stub", "exit_target_rva"),
    ],
)
def test_raw_snapshot_rejects_unlinked_machine_attestation(section, field):
    receipt = _receipt()
    receipt["machine_attestation"][section][field] = "0x00002000"

    with pytest.raises(NativeCheckpointError, match="control-flow link differs"):
        build_rng_core_checkpoint(
            _snapshot(),
            build_receipt=receipt,
            observed_module_sha256=_DIGEST,
        )


def test_raw_snapshot_complete_flag_cannot_hide_loader_lock_recovery():
    raw = _snapshot()
    raw["integrity"]["loader_lock_recovery_pending"] = True

    with pytest.raises(NativeCheckpointError, match="complete"):
        build_rng_core_checkpoint(
            raw,
            build_receipt=_receipt(),
            observed_module_sha256=_DIGEST,
        )


def test_restored_but_stopped_snapshot_remains_diagnostic_incomplete():
    raw = _snapshot()
    raw["integrity"].update(stopped_reason="overflow", complete=False)
    raw["integrity"]["overflow_count"] = 1

    checkpoint = build_rng_core_checkpoint(
        raw,
        build_receipt=_receipt(),
        observed_module_sha256=_DIGEST,
    )
    result = validate_native_checkpoint(
        checkpoint,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        expected_restore_hashes={"rng_core": _CORE_DIGEST},
    )

    assert checkpoint["integrity"]["complete"] is False
    assert result["reported_complete"] is False


def test_restore_manifest_digest_matches_observer_builder_bytes():
    encoded = json.dumps(
        {"rng_core": _CORE_DIGEST},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    assert hashlib.sha256(encoded.encode("utf-8")).hexdigest() == (
        "d7ad5662a8ba8cdce081f56705ea8302ad425e5f7dbf6830ba4056f99408b73d"
    )
