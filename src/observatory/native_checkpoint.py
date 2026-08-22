"""Strict validation for inert native Observatory diagnostic checkpoints.

This schema is intentionally separate from the authoritative Observatory trace
schema.  A valid checkpoint can support build-specific diagnostic claims, but
it is never promoted to semantic trace evidence by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
CHECKPOINT_KIND = "native_diagnostic_checkpoint"
RNG_CORE_SNAPSHOT_KIND = "native_rng_core_observer_snapshot"
RNG_CORE_OBSERVER_VERSION = "observatory-rng-core-observer/1"
MAX_RECORDS = 4096
MAX_THREADS = 32
MAX_CALLERS = 256
MAX_QUEUE_ITEMS = 64

_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RVA = re.compile(r"0x[0-9a-f]{8}\Z")
_OBSERVER_COMPILE_FLAGS = [
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
]
_OBSERVER_RECEIPT_FIELDS = {
    "architecture",
    "boundary_map_canonical_sha256",
    "boundary_map_file_sha256",
    "build_id",
    "caller_count",
    "compile_flags",
    "compiler",
    "compiler_stdout",
    "executable_sha256",
    "executable_size",
    "export_name",
    "generated_include_sha256",
    "hook_plan_filename",
    "hook_plan_sha256",
    "imports",
    "inventory_canonical_sha256",
    "kind",
    "loaded_or_armed",
    "machine_attestation",
    "module_filename",
    "module_sha256",
    "module_size",
    "observer_version",
    "reproducibility",
    "restore_hashes_filename",
    "restore_manifest_sha256",
    "rng_core_region_sha256",
    "rng_core_rva",
    "rng_return_map_sha256",
    "schema_version",
    "source_attestation",
    "source_path",
    "source_sha256",
}
_RECORD_KINDS = {
    "rng_core",
    "rng_seed",
    "phase_marker",
    "span_marker",
    "selected_record",
    "queue_snapshot",
}
_SPAN_NAMES = {"spawner_next_pawn"}
_SPAN_ACTIONS = {"enter", "exit"}
_SPAN_DETAILS = {"normal", "shortcut_no_draw", "cancelled"}
_QUEUE_STATES = {"queued", "cancelled", "executed", "retargeted"}


class NativeCheckpointError(ValueError):
    """Raised when diagnostic checkpoint evidence is malformed or incomplete."""


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeCheckpointError(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    actual = set(value)
    if actual != fields:
        raise NativeCheckpointError(
            f"{label} fields differ; "
            f"missing={sorted(fields - actual)}, unknown={sorted(actual - fields)}"
        )


def _integer(value: Any, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise NativeCheckpointError(
            f"{label} must be an integer in [{low}, {high}]"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise NativeCheckpointError(f"{label} must be a canonical identifier")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise NativeCheckpointError(f"{label} must be lowercase SHA-256")
    return value


def _rva(value: Any, label: str) -> str:
    if type(value) is not str or _RVA.fullmatch(value) is None:
        raise NativeCheckpointError(f"{label} must be a canonical 32-bit RVA")
    return value


def _text(value: Any, label: str, *, limit: int) -> str:
    if type(value) is not str or not value or len(value) > limit:
        raise NativeCheckpointError(f"{label} must be bounded non-empty text")
    return value


def _nullable_identifier(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, label)


def _point(value: Any, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise NativeCheckpointError(f"{label} must be a two-integer point")
    return [
        _integer(value[0], f"{label}[0]", -1, 7),
        _integer(value[1], f"{label}[1]", -1, 7),
    ]


def _identity(value: Any) -> None:
    item = _object(value, "identity")
    fields = {
        "platform",
        "architecture",
        "executable_sha256",
        "executable_size",
        "build_id",
        "inventory_sha256",
        "boundary_map_sha256",
        "rng_return_map_sha256",
        "helper_sha256",
        "hook_plan_sha256",
        "restore_manifest_sha256",
    }
    _exact(item, fields, "identity")
    if item["platform"] != "windows" or item["architecture"] != "x86":
        raise NativeCheckpointError("identity must name the Windows x86 build")
    for field in (
        "executable_sha256",
        "inventory_sha256",
        "boundary_map_sha256",
        "rng_return_map_sha256",
        "helper_sha256",
        "hook_plan_sha256",
        "restore_manifest_sha256",
    ):
        _digest(item[field], f"identity.{field}")
    _integer(item["executable_size"], "identity.executable_size", 1, 1 << 31)
    build_id = item["build_id"]
    if type(build_id) is not str or not build_id or len(build_id) > 96:
        raise NativeCheckpointError("identity.build_id must be non-empty text")


def validate_return_map_binding(
    checkpoint: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    """Bind an in-memory caller catalog to the checkpoint's exact identity."""
    from src.observatory.rng_return_map import encode_rng_return_map

    if (
        return_map.get("schema_version") != 1
        or return_map.get("analysis_kind") != "native_rng_return_id_map"
    ):
        raise NativeCheckpointError("return map has an unsupported schema")
    actual_digest = hashlib.sha256(
        encode_rng_return_map(return_map).encode("utf-8")
    ).hexdigest()
    if actual_digest != checkpoint["identity"]["rng_return_map_sha256"]:
        raise NativeCheckpointError("return map digest does not match checkpoint")
    identity = return_map.get("identity")
    if not isinstance(identity, Mapping):
        raise NativeCheckpointError("return map identity must be an object")
    for field in (
        "platform",
        "architecture",
        "executable_sha256",
        "executable_size",
        "build_id",
    ):
        if identity.get(field) != checkpoint["identity"][field]:
            raise NativeCheckpointError(
                f"return map identity field does not match checkpoint: {field}"
            )
    callers = return_map.get("callers")
    if not isinstance(callers, list) or len(callers) > MAX_CALLERS - 1:
        raise NativeCheckpointError("return map callers must be a bounded array")
    result: dict[int, Mapping[str, Any]] = {}
    for caller_id, raw in enumerate(callers, start=1):
        if not isinstance(raw, Mapping) or raw.get("caller_id") != caller_id:
            raise NativeCheckpointError("return map caller IDs are not contiguous")
        classification = raw.get("classification")
        if not isinstance(classification, Mapping):
            raise NativeCheckpointError("return map classification must be an object")
        status = classification.get("status")
        source = classification.get("source_region")
        if status == "unclassified_raw_candidate":
            if source is not None:
                raise NativeCheckpointError(
                    "unclassified return-map caller names a source region"
                )
        elif status == "reviewed_direct_call":
            if type(source) is not str or not source:
                raise NativeCheckpointError(
                    "reviewed return-map caller lacks a source region"
                )
        else:
            raise NativeCheckpointError("return map classification is unsupported")
        result[caller_id] = classification
    return result


def _hash_map(value: Any, label: str, *, allow_empty: bool = False) -> dict[str, str]:
    item = _object(value, label)
    if (not allow_empty and not item) or len(item) > 64:
        raise NativeCheckpointError(f"{label} must contain 1..64 hooks")
    result: dict[str, str] = {}
    for hook_id, digest in item.items():
        key = _identifier(hook_id, f"{label} hook id")
        result[key] = _digest(digest, f"{label}.{key}")
    return result


def restore_hash_manifest_sha256(value: Mapping[str, Any]) -> str:
    """Hash the canonical externally trusted hook restore manifest."""
    hashes = _hash_map(value, "restore_hash_manifest")
    encoded = json.dumps(
        hashes,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _queue_item(value: Any, label: str) -> None:
    item = _object(value, label)
    _exact(
        item,
        {
            "enemy_id",
            "position",
            "destination",
            "target",
            "skill_id",
            "state",
        },
        label,
    )
    _identifier(item["enemy_id"], f"{label}.enemy_id")
    _point(item["position"], f"{label}.position")
    _point(item["destination"], f"{label}.destination")
    _point(item["target"], f"{label}.target")
    _nullable_identifier(item["skill_id"], f"{label}.skill_id")
    if item["state"] not in _QUEUE_STATES:
        raise NativeCheckpointError(f"{label}.state is unsupported")


def _record(value: Any, index: int) -> tuple[str, int]:
    label = f"records[{index}]"
    item = _object(value, label)
    common = {"kind", "seq", "thread_slot"}
    kind = item.get("kind")
    if kind not in _RECORD_KINDS:
        raise NativeCheckpointError(f"{label}.kind is unsupported")
    seq = _integer(item.get("seq"), f"{label}.seq", 0, MAX_RECORDS - 1)
    thread = _integer(
        item.get("thread_slot"),
        f"{label}.thread_slot",
        0,
        MAX_THREADS - 1,
    )

    if kind == "rng_core":
        _exact(item, common | {"caller_id", "result"}, label)
        _integer(item["caller_id"], f"{label}.caller_id", 0, MAX_CALLERS - 1)
        _integer(item["result"], f"{label}.result", 0, 32767)
    elif kind == "rng_seed":
        _exact(item, common | {"seed"}, label)
        _integer(item["seed"], f"{label}.seed", 0, 0xFFFFFFFF)
    elif kind == "phase_marker":
        _exact(item, common | {"phase", "action"}, label)
        _identifier(item["phase"], f"{label}.phase")
        if item["action"] not in _SPAN_ACTIONS:
            raise NativeCheckpointError(f"{label}.action is unsupported")
    elif kind == "span_marker":
        _exact(item, common | {"span_id", "name", "action", "detail"}, label)
        _integer(item["span_id"], f"{label}.span_id", 1, 0x7FFFFFFF)
        if item["name"] not in _SPAN_NAMES:
            raise NativeCheckpointError(f"{label}.name is unsupported")
        if item["action"] not in _SPAN_ACTIONS:
            raise NativeCheckpointError(f"{label}.action is unsupported")
        if item["detail"] not in _SPAN_DETAILS:
            raise NativeCheckpointError(f"{label}.detail is unsupported")
    elif kind == "selected_record":
        _exact(
            item,
            common | {"turn", "enemy_id", "ai_dest", "ai_target", "skill_id"},
            label,
        )
        _integer(item["turn"], f"{label}.turn", 0, 999)
        _identifier(item["enemy_id"], f"{label}.enemy_id")
        _point(item["ai_dest"], f"{label}.ai_dest")
        _point(item["ai_target"], f"{label}.ai_target")
        _nullable_identifier(item["skill_id"], f"{label}.skill_id")
    else:
        _exact(item, common | {"turn", "phase", "queue"}, label)
        _integer(item["turn"], f"{label}.turn", 0, 999)
        _identifier(item["phase"], f"{label}.phase")
        queue = item["queue"]
        if not isinstance(queue, list) or len(queue) > MAX_QUEUE_ITEMS:
            raise NativeCheckpointError(
                f"{label}.queue must contain at most {MAX_QUEUE_ITEMS} entries"
            )
        for queue_index, entry in enumerate(queue):
            _queue_item(entry, f"{label}.queue[{queue_index}]")
    return str(kind), thread


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise NativeCheckpointError(f"{label} must be boolean")
    return value


def _validate_hot_attestation(value: Any, label: str) -> None:
    item = _object(value, label)
    _exact(
        item,
        {
            "branch_count",
            "direct_or_indirect_call_count",
            "instruction_count",
            "return_count",
            "rva",
            "sha256",
            "size",
        },
        label,
    )
    _rva(item["rva"], f"{label}.rva")
    _digest(item["sha256"], f"{label}.sha256")
    _integer(item["size"], f"{label}.size", 1, 4096)
    _integer(item["instruction_count"], f"{label}.instruction_count", 1, 4096)
    _integer(item["branch_count"], f"{label}.branch_count", 0, 4096)
    _integer(item["return_count"], f"{label}.return_count", 1, 64)
    _integer(
        item["direct_or_indirect_call_count"],
        f"{label}.direct_or_indirect_call_count",
        0,
        0,
    )


def _validate_machine_attestation(value: Any) -> None:
    item = _object(value, "observer build receipt.machine_attestation")
    _exact(
        item,
        {
            "entry_stub",
            "loader_entry_absent",
            "observer_enter",
            "observer_exit",
            "pe_entry_point_rva",
            "post_core_stub",
        },
        "observer build receipt.machine_attestation",
    )
    if item["loader_entry_absent"] is not True:
        raise NativeCheckpointError("observer build receipt has a loader entry")
    if item["pe_entry_point_rva"] != "0x00000000":
        raise NativeCheckpointError("observer build receipt PE entry point differs")
    observer_enter = _object(
        item["observer_enter"],
        "observer build receipt.machine_attestation.observer_enter",
    )
    observer_exit = _object(
        item["observer_exit"],
        "observer build receipt.machine_attestation.observer_exit",
    )
    _validate_hot_attestation(
        observer_enter,
        "observer build receipt.machine_attestation.observer_enter",
    )
    _validate_hot_attestation(
        observer_exit,
        "observer build receipt.machine_attestation.observer_exit",
    )

    entry = _object(
        item["entry_stub"],
        "observer build receipt.machine_attestation.entry_stub",
    )
    _exact(
        entry,
        {
            "enter_target_rva",
            "gateway_pointer_rva",
            "post_core_rva",
            "rva",
            "saved_return_offset",
            "sha256",
            "size",
        },
        "observer build receipt.machine_attestation.entry_stub",
    )
    for field in ("enter_target_rva", "gateway_pointer_rva", "post_core_rva", "rva"):
        _rva(entry[field], f"observer build receipt.entry_stub.{field}")
    _digest(entry["sha256"], "observer build receipt.entry_stub.sha256")
    _integer(entry["size"], "observer build receipt.entry_stub.size", 1, 256)
    if entry["saved_return_offset"] != 36:
        raise NativeCheckpointError("observer entry stub return offset differs")

    post = _object(
        item["post_core_stub"],
        "observer build receipt.machine_attestation.post_core_stub",
    )
    _exact(
        post,
        {
            "exit_target_rva",
            "return_scratch_offset",
            "rva",
            "saved_result_offset",
            "sha256",
            "size",
        },
        "observer build receipt.machine_attestation.post_core_stub",
    )
    for field in ("exit_target_rva", "rva"):
        _rva(post[field], f"observer build receipt.post_core_stub.{field}")
    _digest(post["sha256"], "observer build receipt.post_core_stub.sha256")
    _integer(post["size"], "observer build receipt.post_core_stub.size", 1, 256)
    if post["saved_result_offset"] != 28 or post["return_scratch_offset"] != -40:
        raise NativeCheckpointError("observer post-core ABI offsets differ")
    if (
        entry["enter_target_rva"] != observer_enter["rva"]
        or entry["post_core_rva"] != post["rva"]
        or post["exit_target_rva"] != observer_exit["rva"]
    ):
        raise NativeCheckpointError(
            "observer machine attestation control-flow link differs"
        )


def _rng_core_build_binding(
    receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    build = _object(receipt, "observer build receipt")
    _exact(build, _OBSERVER_RECEIPT_FIELDS, "observer build receipt")
    _integer(build.get("schema_version"), "observer build receipt.schema_version", 1, 1)
    required = {
        "kind": "observatory_rng_core_observer_build",
        "observer_version": RNG_CORE_OBSERVER_VERSION,
        "architecture": "x86",
        "export_name": "luaopen_itb_observatory_rng_core_observer",
    }
    for field, expected in required.items():
        if build.get(field) != expected:
            raise NativeCheckpointError(
                f"observer build receipt field differs: {field}"
            )
    for field in (
        "module_sha256",
        "executable_sha256",
        "inventory_canonical_sha256",
        "boundary_map_canonical_sha256",
        "boundary_map_file_sha256",
        "rng_return_map_sha256",
        "hook_plan_sha256",
        "restore_manifest_sha256",
        "rng_core_region_sha256",
        "source_sha256",
        "generated_include_sha256",
    ):
        _digest(build.get(field), f"observer build receipt.{field}")
    observed = _digest(observed_module_sha256, "observed module SHA-256")
    if observed != build["module_sha256"]:
        raise NativeCheckpointError(
            "observed observer module does not match the build receipt"
        )
    _integer(
        build.get("module_size"),
        "observer build receipt.module_size",
        1,
        1 << 30,
    )
    _integer(
        build.get("executable_size"),
        "observer build receipt.executable_size",
        1,
        1 << 31,
    )
    caller_count = _integer(
        build.get("caller_count"),
        "observer build receipt.caller_count",
        1,
        MAX_CALLERS - 1,
    )
    build_id = build.get("build_id")
    if type(build_id) is not str or not build_id or len(build_id) > 96:
        raise NativeCheckpointError("observer build receipt.build_id is invalid")
    if build.get("rng_core_rva") != "0x00387f16":
        raise NativeCheckpointError("observer build receipt RNG-core RVA differs")
    if build["loaded_or_armed"] is not False:
        raise NativeCheckpointError("observer build receipt is not dormant")
    if build["compile_flags"] != _OBSERVER_COMPILE_FLAGS:
        raise NativeCheckpointError("observer build receipt compile flags differ")
    if build["imports"] != ["bcrypt.dll", "kernel32.dll"]:
        raise NativeCheckpointError("observer build receipt imports differ")
    _text(build["compiler"], "observer build receipt.compiler", limit=512)
    _text(
        build["compiler_stdout"],
        "observer build receipt.compiler_stdout",
        limit=8192,
    )
    if build["source_path"] != "src/native/observatory_rng_core_observer.c":
        raise NativeCheckpointError("observer build receipt source path differs")
    expected_module = (
        "itb_observatory_rng_core_observer_"
        f"{build['module_sha256']}.dll"
    )
    if build["module_filename"] != expected_module:
        raise NativeCheckpointError("observer build receipt module filename differs")
    expected_plan = (
        f"windows_build_{build_id}_rng_core_hook_plan_"
        f"{build['hook_plan_sha256'][:12]}.json"
    )
    if build["hook_plan_filename"] != expected_plan:
        raise NativeCheckpointError("observer build receipt hook-plan filename differs")
    expected_restore = (
        f"windows_build_{build_id}_rng_core_restore_hashes_"
        f"{build['restore_manifest_sha256'][:12]}.json"
    )
    if build["restore_hashes_filename"] != expected_restore:
        raise NativeCheckpointError(
            "observer build receipt restore-manifest filename differs"
        )

    reproducibility = _object(
        build["reproducibility"],
        "observer build receipt.reproducibility",
    )
    _exact(
        reproducibility,
        {
            "attestations_identical",
            "independent_build_count",
            "module_bytes_identical",
        },
        "observer build receipt.reproducibility",
    )
    _integer(
        reproducibility["independent_build_count"],
        "observer build receipt.reproducibility.independent_build_count",
        2,
        2,
    )
    if (
        _boolean(
            reproducibility["module_bytes_identical"],
            "observer build receipt.reproducibility.module_bytes_identical",
        )
        is not True
        or _boolean(
            reproducibility["attestations_identical"],
            "observer build receipt.reproducibility.attestations_identical",
        )
        is not True
    ):
        raise NativeCheckpointError("observer build is not reproducible")

    source_attestation = _object(
        build["source_attestation"],
        "observer build receipt.source_attestation",
    )
    _exact(
        source_attestation,
        {
            "entry_abi_source_sha256",
            "hot_source_sha256",
            "post_abi_source_sha256",
        },
        "observer build receipt.source_attestation",
    )
    for field, digest in source_attestation.items():
        _digest(digest, f"observer build receipt.source_attestation.{field}")
    _validate_machine_attestation(build["machine_attestation"])
    return {
        "platform": "windows",
        "architecture": "x86",
        "executable_sha256": build["executable_sha256"],
        "executable_size": build["executable_size"],
        "build_id": build_id,
        "inventory_sha256": build["inventory_canonical_sha256"],
        "boundary_map_sha256": build["boundary_map_canonical_sha256"],
        "rng_return_map_sha256": build["rng_return_map_sha256"],
        "helper_sha256": observed,
        "hook_plan_sha256": build["hook_plan_sha256"],
        "restore_manifest_sha256": build["restore_manifest_sha256"],
        "rng_core_region_sha256": build["rng_core_region_sha256"],
        "caller_count": caller_count,
    }


def build_rng_core_checkpoint(
    value: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Bind one raw observer snapshot to its independently hashed build."""
    snapshot = _object(value, "RNG-core observer snapshot")
    _exact(
        snapshot,
        {
            "schema_version",
            "kind",
            "observer_version",
            "capture_id",
            "identity",
            "integrity",
            "records",
            "summary",
        },
        "RNG-core observer snapshot",
    )
    if snapshot["schema_version"] != 1:
        raise NativeCheckpointError("unsupported RNG-core snapshot schema")
    if snapshot["kind"] != RNG_CORE_SNAPSHOT_KIND:
        raise NativeCheckpointError("unexpected RNG-core snapshot kind")
    if snapshot["observer_version"] != RNG_CORE_OBSERVER_VERSION:
        raise NativeCheckpointError("RNG-core observer version differs")
    _identifier(snapshot["capture_id"], "capture_id")

    binding = _rng_core_build_binding(build_receipt, observed_module_sha256)
    identity = _object(snapshot["identity"], "snapshot.identity")
    expected_raw_identity = {
        field: binding[field]
        for field in (
            "platform",
            "architecture",
            "executable_sha256",
            "executable_size",
            "build_id",
            "inventory_sha256",
            "boundary_map_sha256",
            "rng_return_map_sha256",
            "hook_plan_sha256",
            "restore_manifest_sha256",
        )
    }
    _exact(identity, set(expected_raw_identity), "snapshot.identity")
    if dict(identity) != expected_raw_identity:
        raise NativeCheckpointError(
            "snapshot identity does not match the observer build receipt"
        )

    records = snapshot["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise NativeCheckpointError(
            f"snapshot records must contain at most {MAX_RECORDS} entries"
        )
    threads: set[int] = set()
    unknown_callers = 0
    for index, raw in enumerate(records):
        kind, thread = _record(raw, index)
        if kind != "rng_core" or raw["seq"] != index:
            raise NativeCheckpointError(
                "RNG-core snapshot records must be contiguous RNG-core entries"
            )
        if raw["caller_id"] > binding["caller_count"]:
            raise NativeCheckpointError(
                "RNG-core snapshot caller ID exceeds the build receipt"
            )
        threads.add(thread)
        if raw["caller_id"] == 0:
            unknown_callers += 1

    summary = _object(snapshot["summary"], "snapshot.summary")
    _exact(
        summary,
        {"record_count", "thread_count", "last_sequence"},
        "snapshot.summary",
    )
    record_count = _integer(
        summary["record_count"], "snapshot.summary.record_count", 0, MAX_RECORDS
    )
    thread_count = _integer(
        summary["thread_count"], "snapshot.summary.thread_count", 0, MAX_THREADS
    )
    if (
        record_count != len(records)
        or summary["last_sequence"] != len(records) - 1
        or thread_count < len(threads)
    ):
        raise NativeCheckpointError("RNG-core snapshot summary is inconsistent")

    raw_integrity = _object(snapshot["integrity"], "snapshot.integrity")
    # Lua table fields assigned nil do not survive JSON serialization.  The
    # native observer emits a nil stopped_reason on a normal complete capture,
    # so canonicalize that one optional wire field back to explicit None while
    # retaining exact-field validation for every other integrity claim.
    integrity = dict(raw_integrity)
    integrity.setdefault("stopped_reason", None)
    _exact(
        integrity,
        {
            "state",
            "overflow_count",
            "unknown_caller_count",
            "torn_record_count",
            "thread_cap_count",
            "nesting_cap_count",
            "thread_recovery_count",
            "loader_lock_recovery_pending",
            "restore_conflict",
            "patch_installed",
            "active_frames",
            "core_bytes_restored",
            "hook_bytes_restored",
            "page_protection_restored",
            "instruction_cache_flushed",
            "executable_file_released",
            "post_restore_hashes",
            "stopped_reason",
            "complete",
        },
        "snapshot.integrity",
    )
    state = integrity["state"]
    if state not in {
        "dormant",
        "verified",
        "capturing",
        "draining",
        "restored",
        "failed_clean",
        "failed_patched",
    }:
        raise NativeCheckpointError("snapshot.integrity.state is unsupported")
    overflow = _integer(
        integrity["overflow_count"],
        "snapshot.integrity.overflow_count",
        0,
        1 << 31,
    )
    unknown = _integer(
        integrity["unknown_caller_count"],
        "snapshot.integrity.unknown_caller_count",
        0,
        MAX_RECORDS,
    )
    torn = _integer(
        integrity["torn_record_count"],
        "snapshot.integrity.torn_record_count",
        0,
        MAX_RECORDS,
    )
    thread_cap = _integer(
        integrity["thread_cap_count"],
        "snapshot.integrity.thread_cap_count",
        0,
        1 << 31,
    )
    nesting_cap = _integer(
        integrity["nesting_cap_count"],
        "snapshot.integrity.nesting_cap_count",
        0,
        1 << 31,
    )
    thread_recovery = _integer(
        integrity["thread_recovery_count"],
        "snapshot.integrity.thread_recovery_count",
        0,
        MAX_THREADS * 6,
    )
    active = _integer(
        integrity["active_frames"],
        "snapshot.integrity.active_frames",
        0,
        MAX_THREADS * 8,
    )
    if unknown != unknown_callers:
        raise NativeCheckpointError(
            "snapshot unknown caller count does not match records"
        )
    boolean_fields = (
        "restore_conflict",
        "patch_installed",
        "core_bytes_restored",
        "hook_bytes_restored",
        "page_protection_restored",
        "instruction_cache_flushed",
        "executable_file_released",
        "loader_lock_recovery_pending",
        "complete",
    )
    for field in boolean_fields:
        _boolean(integrity[field], f"snapshot.integrity.{field}")
    stopped = integrity["stopped_reason"]
    if stopped is not None:
        _identifier(stopped, "snapshot.integrity.stopped_reason")
    hashes = _hash_map(
        integrity["post_restore_hashes"],
        "snapshot.integrity.post_restore_hashes",
        allow_empty=not integrity["core_bytes_restored"],
    )
    expected_hashes = (
        {"rng_core": binding["rng_core_region_sha256"]}
        if integrity["core_bytes_restored"]
        else {}
    )
    if hashes != expected_hashes:
        raise NativeCheckpointError(
            "snapshot post-restore hashes differ from restored core state"
        )
    if integrity["hook_bytes_restored"] != integrity["core_bytes_restored"]:
        raise NativeCheckpointError(
            "snapshot core and hook restoration claims differ"
        )
    reported_complete = (
        state == "restored"
        and overflow == 0
        and unknown == 0
        and torn == 0
        and thread_cap == 0
        and nesting_cap == 0
        and thread_recovery == 0
        and not integrity["loader_lock_recovery_pending"]
        and not integrity["restore_conflict"]
        and not integrity["patch_installed"]
        and active == 0
        and integrity["core_bytes_restored"]
        and integrity["hook_bytes_restored"]
        and integrity["page_protection_restored"]
        and integrity["instruction_cache_flushed"]
        and integrity["executable_file_released"]
        and stopped is None
    )
    if integrity["complete"] is not reported_complete:
        raise NativeCheckpointError(
            "snapshot integrity.complete does not match diagnostics"
        )
    if state == "failed_clean" and integrity["patch_installed"]:
        raise NativeCheckpointError("failed_clean snapshot still has a patch")
    if state == "failed_patched" and not integrity["patch_installed"]:
        raise NativeCheckpointError("failed_patched snapshot has no patch")

    standard_reason = stopped
    if not reported_complete and standard_reason is None:
        standard_reason = "observer_integrity_incomplete"
    standard_identity = {
        field: binding[field]
        for field in (
            "platform",
            "architecture",
            "executable_sha256",
            "executable_size",
            "build_id",
            "inventory_sha256",
            "boundary_map_sha256",
            "rng_return_map_sha256",
            "helper_sha256",
            "hook_plan_sha256",
            "restore_manifest_sha256",
        )
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": CHECKPOINT_KIND,
        "identity": standard_identity,
        "capture_id": snapshot["capture_id"],
        "integrity": {
            "overflow_count": overflow,
            "unknown_caller_count": unknown,
            "torn_record_count": torn,
            "restore_conflict": integrity["restore_conflict"],
            "hook_bytes_restored": integrity["hook_bytes_restored"],
            "post_restore_hashes": hashes,
            "stopped_reason": standard_reason,
            "complete": reported_complete,
        },
        "records": [dict(item) for item in records],
        "summary": {
            "record_count": len(records),
            "rng_core_count": len(records),
            "rng_seed_count": 0,
            "phase_marker_count": 0,
            "span_marker_count": 0,
            "selected_record_count": 0,
            "queue_snapshot_count": 0,
            "thread_count": len(threads),
            "last_sequence": len(records) - 1,
            "capture_complete": reported_complete,
        },
    }


def validate_native_checkpoint(
    value: Mapping[str, Any],
    *,
    expected_identity: Mapping[str, Any] | None = None,
    return_map: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one diagnostic checkpoint and return a compact verification."""
    checkpoint = _object(value, "checkpoint")
    _exact(
        checkpoint,
        {
            "schema_version",
            "kind",
            "identity",
            "capture_id",
            "integrity",
            "records",
            "summary",
        },
        "checkpoint",
    )
    if checkpoint["schema_version"] != SCHEMA_VERSION:
        raise NativeCheckpointError("unsupported native checkpoint schema version")
    if checkpoint["kind"] != CHECKPOINT_KIND:
        raise NativeCheckpointError("unexpected native checkpoint kind")
    _identity(checkpoint["identity"])
    identity_verified = expected_identity is not None
    if identity_verified and checkpoint["identity"] != expected_identity:
        raise NativeCheckpointError("checkpoint identity does not match expectation")
    _identifier(checkpoint["capture_id"], "capture_id")

    records = checkpoint["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise NativeCheckpointError(
            f"records must contain at most {MAX_RECORDS} entries"
        )
    kinds: Counter[str] = Counter()
    threads: set[int] = set()
    unknown_callers = 0
    for index, raw in enumerate(records):
        kind, thread = _record(raw, index)
        if raw["seq"] != index:
            raise NativeCheckpointError("record sequences must be contiguous from zero")
        kinds[kind] += 1
        threads.add(thread)
        if kind == "rng_core" and raw["caller_id"] == 0:
            unknown_callers += 1

    integrity = _object(checkpoint["integrity"], "integrity")
    _exact(
        integrity,
        {
            "overflow_count",
            "unknown_caller_count",
            "torn_record_count",
            "restore_conflict",
            "hook_bytes_restored",
            "post_restore_hashes",
            "stopped_reason",
            "complete",
        },
        "integrity",
    )
    overflow = _integer(integrity["overflow_count"], "integrity.overflow_count", 0, 1 << 31)
    unknown = _integer(
        integrity["unknown_caller_count"],
        "integrity.unknown_caller_count",
        0,
        MAX_RECORDS,
    )
    torn = _integer(integrity["torn_record_count"], "integrity.torn_record_count", 0, MAX_RECORDS)
    if unknown != unknown_callers:
        raise NativeCheckpointError("unknown caller count does not match records")
    for field in ("restore_conflict", "hook_bytes_restored", "complete"):
        if type(integrity[field]) is not bool:
            raise NativeCheckpointError(f"integrity.{field} must be boolean")
    hashes = _hash_map(
        integrity["post_restore_hashes"],
        "integrity.post_restore_hashes",
        allow_empty=not integrity["hook_bytes_restored"],
    )
    stopped = integrity["stopped_reason"]
    if stopped is not None:
        _identifier(stopped, "integrity.stopped_reason")
    reported_complete = (
        overflow == 0
        and unknown == 0
        and torn == 0
        and not integrity["restore_conflict"]
        and integrity["hook_bytes_restored"]
        and stopped is None
    )
    if integrity["complete"] is not reported_complete:
        raise NativeCheckpointError("integrity.complete does not match diagnostics")

    caller_catalog = (
        validate_return_map_binding(checkpoint, return_map)
        if return_map is not None
        else None
    )
    observed_caller_ids = {
        record["caller_id"]
        for record in records
        if record["kind"] == "rng_core" and record["caller_id"] != 0
    }
    caller_catalog_verified = (
        not observed_caller_ids
        or (
            caller_catalog is not None
            and observed_caller_ids <= set(caller_catalog)
        )
    )
    restore_hashes_verified = False
    if expected_restore_hashes is not None:
        expected_hashes = _hash_map(
            expected_restore_hashes,
            "expected_restore_hashes",
        )
        if restore_hash_manifest_sha256(expected_hashes) != checkpoint[
            "identity"
        ]["restore_manifest_sha256"]:
            raise NativeCheckpointError(
                "expected restore hashes do not match the trusted identity"
            )
        restore_hashes_verified = hashes == expected_hashes
    diagnostic_complete = (
        reported_complete
        and identity_verified
        and caller_catalog_verified
        and restore_hashes_verified
    )

    expected_summary = {
        "record_count": len(records),
        "rng_core_count": kinds["rng_core"],
        "rng_seed_count": kinds["rng_seed"],
        "phase_marker_count": kinds["phase_marker"],
        "span_marker_count": kinds["span_marker"],
        "selected_record_count": kinds["selected_record"],
        "queue_snapshot_count": kinds["queue_snapshot"],
        "thread_count": len(threads),
        "last_sequence": len(records) - 1,
        "capture_complete": reported_complete,
    }
    summary = _object(checkpoint["summary"], "summary")
    _exact(summary, set(expected_summary), "summary")
    if dict(summary) != expected_summary:
        raise NativeCheckpointError("checkpoint summary is inconsistent")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": CHECKPOINT_KIND,
        "status": "verified",
        "capture_id": checkpoint["capture_id"],
        "identity_verified": identity_verified,
        "caller_catalog_verified": caller_catalog_verified,
        "restore_hashes_verified": restore_hashes_verified,
        "reported_complete": reported_complete,
        "diagnostic_complete": diagnostic_complete,
        "summary": expected_summary,
        "authority": "build_specific_diagnostic_only",
    }


def encode_native_checkpoint(value: Mapping[str, Any]) -> str:
    """Encode a checkpoint or verification deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
