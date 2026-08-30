"""Tests for exact native-function review accounting over a verified atlas."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_REGISTRY_RAW_SHA256 = (
    "910320d150e7aa6977ce08fcaa9a71823f82f181624efd7a59932a5e7d55910d"
)
_COMMITTED_REGISTRY_CANONICAL_SHA256 = (
    "1f3226a6939b21126bc7e3514b4ef9784590935c5ef6017b7e025c83b994f3c4"
)
_COMMITTED_ACCOUNTING_RAW_SHA256 = (
    "147feaba792a06da19fa12876d0b58be4633f5ae917f243e447868d6fbbf80f1"
)
_COMMITTED_ACCOUNTING_CANONICAL_SHA256 = (
    "9f8739fe4a5c3bcfb9f10aeda9faf3333c96b3ea9ee130a00538aef87ce6dee5"
)
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_native_function_accounting  # noqa: E402
import src.observatory.native_function_accounting as native_accounting  # noqa: E402

from src.observatory.native_function_accounting import (
    ANALYSIS_KIND,
    NativeFunctionAccountingError,
    REVIEW_EVIDENCE_KIND,
    SUPPORT_EVIDENCE_KIND,
    _canonical_sha256,
    _read_repo_json,
    _safe_repo_path,
    _support_assertion,
    atlas_record_sha256,
    build_native_function_accounting,
    encode_native_function_accounting,
    validate_native_function_accounting,
)
from src.observatory.native_lua_direct_calls import (
    build_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_lua_cclosure_callbacks import (
    build_native_lua_cclosure_callback_census,
    validate_native_lua_cclosure_callback_structure,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    build_native_lua_cclosure_setfield_publication_census,
    validate_native_lua_cclosure_setfield_publication_structure,
)
from src.observatory.program_facts import build_program_facts


_IMAGE_BASE = 0x00400000
_LUA_IAT_RVA = 0x00001190
_CALLBACK_RVA = 0x00001040
_PUSHCLOSURE_IAT_RVA = 0x000011C0
_SETFIELD_IAT_RVA = 0x000011C4
_SETFIELD_KEY_RVA = 0x00001200


@pytest.fixture(autouse=True)
def _install_synthetic_upstream_adapter(monkeypatch):
    def validate_synthetic_upstream(
        document,
        *,
        executable,
        inventory,
        program_facts,
        source_sha256,
        verification_cache,
        json_pointer,
        entry_rva,
        atlas_record_identity,
        support_class,
        role,
        label,
    ):
        if not executable.is_file() or inventory["executable"]["path"] != "Breach.exe":
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream build context differs"
            )
        if source_sha256 != hashlib.sha256(
            json.dumps(document, sort_keys=True).encode("utf-8")
        ).hexdigest():
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream source identity differs"
            )
        if not isinstance(verification_cache, dict):
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream cache differs"
            )
        native_accounting._direct_record_pointer(
            json_pointer,
            f"{label}.json_pointer",
        )
        target = native_accounting._mapping(
            native_accounting._json_pointer(
                document,
                json_pointer,
                f"{label}.json_pointer",
            ),
            f"{label} synthetic upstream target",
        )
        if (
            set(document)
            != {"schema_version", "analysis_kind", "build_identity", "records"}
            or document["schema_version"] != 2
            or document["analysis_kind"] != "synthetic_native_function_analysis"
        ):
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream document differs"
            )
        native_accounting._identity_matches(
            document,
            program_facts["identity"],
            label,
        )
        if not isinstance(document["records"], list) or not document["records"]:
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream records must be non-empty"
            )
        expected_fields = {
            "entry_rva",
            "atlas_record_sha256",
            "support_class",
            "role",
            "evidence_class",
            "statement",
            "observed",
        }
        if set(target) != expected_fields:
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream fields differ"
            )
        if (
            target["entry_rva"] != entry_rva
            or target["atlas_record_sha256"] != atlas_record_identity
            or target["support_class"] != support_class
            or target["role"] != role
        ):
            raise NativeFunctionAccountingError(
                f"{label} synthetic upstream identity differs"
            )
        return {
            "assertion": target["observed"],
            "evidence_class": target["evidence_class"],
            "statement": target["statement"],
        }

    monkeypatch.setitem(
        native_accounting._UPSTREAM_ADAPTERS,
        "synthetic_native_function_analysis",
        validate_synthetic_upstream,
    )


def _synthetic_pe() -> bytes:
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<I", data, optional + 28, 0x400000)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x400, 0x1000, 0x400, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x220:0x224] = b"\xe8\x0b\x00\x00"
    data[0x230:0x232] = b"\x90\xc3"
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic native accounting test",
        "executable": {
            "path": "Breach.exe",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "format": "pe",
            "architecture": "x86",
        },
        "steam": {
            "build_id": "123",
            "installed_depots": [{"depot_id": "590381", "manifest": "456"}],
            "evidence": {"sha256": "d" * 64},
        },
        "content": {
            "scripts": {"revision_sha256": "a" * 64},
            "maps": {"revision_sha256": "b" * 64},
        },
        "native_libraries": [
            {
                "path": "synthetic.dll",
                "size": 7,
                "sha256": "c" * 64,
                "format": "pe",
                "architecture": "x86",
            }
        ],
    }


def _facts(data: bytes, *, first_thunk: int = 0) -> str:
    first = hashlib.sha256(data[0x220:0x224]).hexdigest()
    second = hashlib.sha256(data[0x230:0x232]).hexdigest()
    return "\n".join(
        [
            "meta\tformat_version\t1",
            "meta\tghidra_version\t12.1.3",
            "meta\tprogram_name\tBreach.exe",
            "meta\tlanguage_id\tx86:LE:32:default",
            "meta\tcompiler_spec_id\twindows",
            "meta\timage_base\t0x00400000",
            "meta\tfunction_count\t2",
            "meta\trange_count\t2",
            "meta\tdirect_internal_call_count\t1",
            "meta\tomitted_call_target_count\t3",
            f"function\t0x00001020\tFUN_00401020\tGlobal\tDEFAULT\t{first_thunk}\t4\t{first}",
            f"function\t0x00001030\tnamed_target\tGlobal\tUSER_DEFINED\t0\t2\t{second}",
            "range\t0x00001020\t0x00001020\t4",
            "range\t0x00001030\t0x00001030\t2",
            "call\t0x00001020\t0x00001020\t0x00001030\t0x00001030\tGlobal::named_target",
            "",
        ]
    )


def _write_inputs(tmp_path: Path, *, first_thunk: int = 0) -> tuple[Path, dict, dict]:
    data = _synthetic_pe()
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    facts = tmp_path / "program.tsv"
    facts.write_text(_facts(data, first_thunk=first_thunk), encoding="utf-8", newline="\n")
    return executable, inventory, build_program_facts(executable, facts, inventory=inventory)


def _write_direct_lua_inputs(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    data = bytearray(0xA00)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1020)
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 104, 0x1100, 40)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    code = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _LUA_IAT_RVA) + b"\xc3"
    data[0x220:0x227] = code
    data[0x240:0x242] = b"\x90\xc3"
    struct.pack_into("<IIIII", data, 0x300, 0x1180, 0, 0, 0x1140, _LUA_IAT_RVA)
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x36D] = b"lua_gettop\0"
    struct.pack_into("<II", data, 0x380, 0x1160, 0)
    struct.pack_into("<II", data, 0x390, 0x1160, 0)
    raw = bytes(data)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(raw)
    inventory = _inventory(raw)
    inventory["label"] = "synthetic direct Lua accounting adapter test"
    inventory["native_libraries"] = [
        {
            "path": "lua5.1.dll",
            "size": 7,
            "sha256": "c" * 64,
            "format": "pe",
            "architecture": "x86",
        }
    ]
    facts = tmp_path / "program.tsv"
    first = hashlib.sha256(code).hexdigest()
    second = hashlib.sha256(raw[0x240:0x242]).hexdigest()
    facts.write_text(
        "\n".join(
            [
                "meta\tformat_version\t1",
                "meta\tghidra_version\t12.1.3",
                "meta\tprogram_name\tBreach.exe",
                "meta\tlanguage_id\tx86:LE:32:default",
                "meta\tcompiler_spec_id\twindows",
                "meta\timage_base\t0x00400000",
                "meta\tfunction_count\t2",
                "meta\trange_count\t2",
                "meta\tdirect_internal_call_count\t0",
                "meta\tomitted_call_target_count\t1",
                f"function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t7\t{first}",
                f"function\t0x00001040\tother\tGlobal\tUSER_DEFINED\t0\t2\t{second}",
                "range\t0x00001020\t0x00001020\t7",
                "range\t0x00001040\t0x00001040\t2",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    program_facts = build_program_facts(executable, facts, inventory=inventory)
    census = build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )
    return executable, inventory, program_facts, census


def _write_callback_inputs(
    tmp_path: Path,
) -> tuple[Path, dict, dict, dict, dict]:
    code = (
        b"\x6a\x02"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + b"\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _LUA_IAT_RVA)
        + b"\xc3"
    )
    data = bytearray(0xA00)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1020)
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 104, 0x1100, 40)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x220 : 0x220 + len(code)] = code
    data[0x240:0x243] = b"\x31\xc0\xc3"
    struct.pack_into("<IIIII", data, 0x300, 0x1180, 0, 0, 0x1140, _LUA_IAT_RVA)
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x373] = b"lua_pushcclosure\0"
    struct.pack_into("<II", data, 0x380, 0x1160, 0)
    struct.pack_into("<II", data, 0x390, 0x1160, 0)
    raw = bytes(data)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(raw)
    inventory = _inventory(raw)
    inventory["label"] = "synthetic callback accounting adapter test"
    inventory["native_libraries"] = [
        {
            "path": "lua5.1.dll",
            "size": 7,
            "sha256": "c" * 64,
            "format": "pe",
            "architecture": "x86",
        }
    ]
    facts = tmp_path / "program.tsv"
    caller_hash = hashlib.sha256(code).hexdigest()
    callback_hash = hashlib.sha256(raw[0x240:0x243]).hexdigest()
    facts.write_text(
        "\n".join(
            [
                "meta\tformat_version\t1",
                "meta\tghidra_version\t12.1.3",
                "meta\tprogram_name\tBreach.exe",
                "meta\tlanguage_id\tx86:LE:32:default",
                "meta\tcompiler_spec_id\twindows",
                "meta\timage_base\t0x00400000",
                "meta\tfunction_count\t2",
                "meta\trange_count\t2",
                "meta\tdirect_internal_call_count\t0",
                "meta\tomitted_call_target_count\t1",
                (
                    "function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t"
                    f"{len(code)}\t{caller_hash}"
                ),
                (
                    "function\t0x00001040\tcallback\tGlobal\tUSER_DEFINED\t0\t"
                    f"3\t{callback_hash}"
                ),
                f"range\t0x00001020\t0x00001020\t{len(code)}",
                "range\t0x00001040\t0x00001040\t3",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    program_facts = build_program_facts(executable, facts, inventory=inventory)
    direct_calls = build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )
    callbacks = build_native_lua_cclosure_callback_census(
        executable,
        direct_calls,
        program_facts,
        inventory=inventory,
    )
    return executable, inventory, program_facts, direct_calls, callbacks


def _write_setfield_publication_inputs(
    tmp_path: Path,
) -> tuple[Path, dict, dict, dict, dict, dict]:
    code = (
        b"\x6a\x00"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + b"\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _PUSHCLOSURE_IAT_RVA)
        + b"\x83\xc4\x0c"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _SETFIELD_KEY_RVA)
        + b"\x6a\xfe\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _SETFIELD_IAT_RVA)
        + b"\xc3"
    )
    data = bytearray(0xC00)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1020)
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 104, 0x1100, 40)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0xA00, 0x1000, 0xA00, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x220 : 0x220 + len(code)] = code
    data[0x240:0x243] = b"\x31\xc0\xc3"
    data[0x400:0x405] = b"__gc\0"
    struct.pack_into(
        "<IIIII", data, 0x300, 0x11B0, 0, 0, 0x1140, _PUSHCLOSURE_IAT_RVA
    )
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x373] = b"lua_pushcclosure\0"
    struct.pack_into("<H", data, 0x378, 8)
    data[0x37A:0x387] = b"lua_setfield\0"
    struct.pack_into("<III", data, 0x3B0, 0x1160, 0x1178, 0)
    struct.pack_into("<III", data, 0x3C0, 0x1160, 0x1178, 0)
    raw = bytes(data)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(raw)
    inventory = _inventory(raw)
    inventory["label"] = "synthetic setfield publication accounting adapter test"
    inventory["native_libraries"] = [
        {
            "path": "lua5.1.dll",
            "size": 7,
            "sha256": "c" * 64,
            "format": "pe",
            "architecture": "x86",
        }
    ]
    facts = tmp_path / "program.tsv"
    caller_hash = hashlib.sha256(code).hexdigest()
    callback_hash = hashlib.sha256(raw[0x240:0x243]).hexdigest()
    facts.write_text(
        "\n".join(
            [
                "meta\tformat_version\t1",
                "meta\tghidra_version\t12.1.3",
                "meta\tprogram_name\tBreach.exe",
                "meta\tlanguage_id\tx86:LE:32:default",
                "meta\tcompiler_spec_id\twindows",
                "meta\timage_base\t0x00400000",
                "meta\tfunction_count\t2",
                "meta\trange_count\t2",
                "meta\tdirect_internal_call_count\t0",
                "meta\tomitted_call_target_count\t2",
                (
                    "function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t"
                    f"{len(code)}\t{caller_hash}"
                ),
                (
                    "function\t0x00001040\tcallback\tGlobal\tUSER_DEFINED\t0\t"
                    f"3\t{callback_hash}"
                ),
                f"range\t0x00001020\t0x00001020\t{len(code)}",
                "range\t0x00001040\t0x00001040\t3",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    program_facts = build_program_facts(executable, facts, inventory=inventory)
    direct_calls = build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )
    callbacks = build_native_lua_cclosure_callback_census(
        executable,
        direct_calls,
        program_facts,
        inventory=inventory,
    )
    publications = build_native_lua_cclosure_setfield_publication_census(
        executable,
        direct_calls,
        callbacks,
        program_facts,
        inventory=inventory,
    )
    return executable, inventory, program_facts, direct_calls, callbacks, publications


def _registry(program_facts: dict, claims: list[dict] | None = None) -> dict:
    from src.observatory.native_function_accounting import _canonical_sha256

    return {
        "schema_version": 2,
        "analysis_kind": "pe_native_function_review_registry",
        "atlas_canonical_sha256": _canonical_sha256(program_facts),
        "claims": [] if claims is None else claims,
    }


def _write_evidence(
    tmp_path: Path,
    identity: dict,
    function: dict,
    *,
    name: str = "review.json",
    native_lua_boundary: dict | None = None,
) -> dict:
    relative = Path("evidence") / name
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_rva = function["entry_rva"]
    record_sha256 = atlas_record_sha256(function)
    if native_lua_boundary is None:
        native_lua_boundary = {
            "state": "roles",
            "roles": ["lua_api_consumer", "registered_lua_callable"],
        }
    review_fields = {
        "boundary_status": "reviewed_exact",
        "ownership": "first_party",
        "subsystem": "player_action",
        "purpose": "Records a reviewed native player action boundary.",
        "inputs_outputs": "Consumes an action request and returns its result.",
        "native_lua_boundary": native_lua_boundary,
        "reference_status": "reviewed_immediate",
        "exclusion": "none",
        "evidence_class": "fact",
    }
    support_relative = relative.with_name(f"{relative.stem}.support.json")
    support_path = tmp_path / support_relative
    upstream_relative = relative.with_name(f"{relative.stem}.upstream.json")
    upstream_path = tmp_path / upstream_relative
    support_specs = [
        ("boundary", None),
        ("immediate_references", None),
        ("ownership", None),
        ("semantic_io", None),
    ]
    if native_lua_boundary["state"] == "none":
        support_specs.append(("native_lua_boundary", None))
    else:
        support_specs.extend(
            ("native_lua_role", role)
            for role in native_lua_boundary["roles"]
        )
    support_specs.sort(key=lambda item: (item[0], "" if item[1] is None else item[1]))
    upstream_records = [
        {
            "entry_rva": entry_rva,
            "atlas_record_sha256": record_sha256,
            "support_class": support_class,
            "role": role,
            "evidence_class": "fact",
            "statement": f"Synthetic decoded {support_class} observation.",
            "observed": _support_assertion(review_fields, support_class, role=role),
        }
        for support_class, role in support_specs
    ]
    upstream_document = {
        "schema_version": 2,
        "analysis_kind": "synthetic_native_function_analysis",
        "build_identity": identity,
        "records": upstream_records,
    }
    upstream_payload = json.dumps(upstream_document, sort_keys=True).encode(
        "utf-8"
    )
    upstream_path.write_bytes(upstream_payload)
    upstream_sha256 = hashlib.sha256(upstream_payload).hexdigest()
    support_records = [
        {
            "entry_rva": entry_rva,
            "atlas_record_sha256": record_sha256,
            "support_class": support_class,
            "role": role,
            "assertion_sha256": _canonical_sha256(
                _support_assertion(review_fields, support_class, role=role)
            ),
            "evidence_class": "fact",
            "statement": f"Synthetic reviewed {support_class} support.",
            "sources": [
                {
                    "path": upstream_relative.as_posix(),
                    "sha256": upstream_sha256,
                    "json_pointer": f"/records/{index}",
                }
            ],
        }
        for index, (support_class, role) in enumerate(support_specs)
    ]
    support_document = {
        "schema_version": 2,
        "analysis_kind": SUPPORT_EVIDENCE_KIND,
        "build_identity": identity,
        "records": support_records,
    }
    support_payload = json.dumps(support_document, sort_keys=True).encode("utf-8")
    support_path.write_bytes(support_payload)
    support_sha256 = hashlib.sha256(support_payload).hexdigest()
    support = [
        {
            "support_class": support_class,
            "role": role,
            "path": support_relative.as_posix(),
            "sha256": support_sha256,
            "json_pointer": f"/records/{index}",
        }
        for index, (support_class, role) in enumerate(support_specs)
    ]
    document = {
        "schema_version": 2,
        "analysis_kind": REVIEW_EVIDENCE_KIND,
        "build_identity": identity,
        "records": [
            {
                "entry_rva": entry_rva,
                "atlas_record_sha256": record_sha256,
                **review_fields,
                "rationale": "Synthetic exact L2 review for validator tests.",
                "support": support,
            }
        ],
    }
    payload = json.dumps(document, sort_keys=True).encode("utf-8")
    path.write_bytes(payload)
    return {
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "json_pointer": "/records/0",
    }


def _rewrite_evidence_chain(tmp_path: Path, reference: dict, mutate) -> None:
    review_path = tmp_path / reference["path"]
    review_document = json.loads(review_path.read_text(encoding="utf-8"))
    support_reference = review_document["records"][0]["support"][0]
    support_path = tmp_path / support_reference["path"]
    support_document = json.loads(support_path.read_text(encoding="utf-8"))
    upstream_reference = support_document["records"][0]["sources"][0]
    upstream_path = tmp_path / upstream_reference["path"]
    upstream_document = json.loads(upstream_path.read_text(encoding="utf-8"))

    mutate(review_document, support_document, upstream_document)

    upstream_payload = json.dumps(upstream_document, sort_keys=True).encode("utf-8")
    upstream_path.write_bytes(upstream_payload)
    upstream_sha256 = hashlib.sha256(upstream_payload).hexdigest()
    for record in support_document["records"]:
        for source in record["sources"]:
            if source["path"] == upstream_reference["path"]:
                source["sha256"] = upstream_sha256

    support_payload = json.dumps(support_document, sort_keys=True).encode("utf-8")
    support_path.write_bytes(support_payload)
    support_sha256 = hashlib.sha256(support_payload).hexdigest()
    for record in review_document["records"]:
        for support in record["support"]:
            if support["path"] == support_reference["path"]:
                support["sha256"] = support_sha256

    review_payload = json.dumps(review_document, sort_keys=True).encode("utf-8")
    review_path.write_bytes(review_payload)
    reference["sha256"] = hashlib.sha256(review_payload).hexdigest()


def _bind_upstream_artifact_source(
    tmp_path: Path,
    reference: dict,
    artifact: dict,
    *,
    filename: str,
    json_pointer: str,
    support_class: str = "native_lua_role",
    role: str | None = "lua_api_consumer",
) -> None:
    artifact_relative = Path("evidence") / filename
    artifact_payload = json.dumps(artifact, sort_keys=True).encode("utf-8")
    (tmp_path / artifact_relative).write_bytes(artifact_payload)
    artifact_sha256 = hashlib.sha256(artifact_payload).hexdigest()

    def bind(_review, support, _upstream):
        record = next(
            item
            for item in support["records"]
            if item["support_class"] == support_class and item["role"] == role
        )
        record["sources"] = [
            {
                "path": artifact_relative.as_posix(),
                "sha256": artifact_sha256,
                "json_pointer": json_pointer,
            }
        ]

    _rewrite_evidence_chain(tmp_path, reference, bind)

    # If the replaced source happened to be the helper's first source, its
    # generic repinning step used the synthetic document hash. Restore the
    # independently hash-pinned artifact and propagate the support hash.
    review_path = tmp_path / reference["path"]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    support_relative = Path(review["records"][0]["support"][0]["path"])
    support_path = tmp_path / support_relative
    support = json.loads(support_path.read_text(encoding="utf-8"))
    record = next(
        item
        for item in support["records"]
        if item["support_class"] == support_class and item["role"] == role
    )
    record["sources"][0]["sha256"] = artifact_sha256
    support_payload = json.dumps(support, sort_keys=True).encode("utf-8")
    support_path.write_bytes(support_payload)
    support_sha256 = hashlib.sha256(support_payload).hexdigest()
    for item in review["records"][0]["support"]:
        if item["path"] == support_relative.as_posix():
            item["sha256"] = support_sha256
    review_payload = json.dumps(review, sort_keys=True).encode("utf-8")
    review_path.write_bytes(review_payload)
    reference["sha256"] = hashlib.sha256(review_payload).hexdigest()


def _bind_direct_census_source(
    tmp_path: Path,
    reference: dict,
    census: dict,
    *,
    support_class: str = "native_lua_role",
    role: str | None = "lua_api_consumer",
) -> None:
    _bind_upstream_artifact_source(
        tmp_path,
        reference,
        census,
        filename="direct-lua-census.json",
        json_pointer="/records/0",
        support_class=support_class,
        role=role,
    )


def _bind_callback_census_source(
    tmp_path: Path,
    reference: dict,
    census: dict,
    *,
    json_pointer: str = "/callback_targets/0",
    support_class: str = "native_lua_role",
    role: str | None = "cclosure_callback_target",
) -> None:
    _bind_upstream_artifact_source(
        tmp_path,
        reference,
        census,
        filename="callback-census.json",
        json_pointer=json_pointer,
        support_class=support_class,
        role=role,
    )


def _bind_setfield_publication_census_source(
    tmp_path: Path,
    reference: dict,
    census: dict,
    *,
    json_pointer: str = "/registered_targets/0",
    support_class: str = "native_lua_role",
    role: str | None = "registered_lua_callable",
) -> None:
    _bind_upstream_artifact_source(
        tmp_path,
        reference,
        census,
        filename="setfield-publication-census.json",
        json_pointer=json_pointer,
        support_class=support_class,
        role=role,
    )


def _l2_claim(
    program_facts: dict,
    evidence: dict,
    *,
    entry: int = 0,
    native_lua_boundary: dict | None = None,
) -> dict:
    function = program_facts["functions"][entry]
    if native_lua_boundary is None:
        native_lua_boundary = {
            "state": "roles",
            "roles": ["lua_api_consumer", "registered_lua_callable"],
        }
    return {
        "entry_rva": function["entry_rva"],
        "atlas_record_sha256": atlas_record_sha256(function),
        "claimed_level": "L2",
        "boundary_status": "reviewed_exact",
        "ownership": "first_party",
        "subsystem": "player_action",
        "purpose": "Records a reviewed native player action boundary.",
        "inputs_outputs": "Consumes an action request and returns its result.",
        "native_lua_boundary": native_lua_boundary,
        "reference_status": "reviewed_immediate",
        "exclusion": "none",
        "evidence_class": "fact",
        "evidence": [evidence],
    }


def _build(
    tmp_path: Path,
    program_facts: dict,
    registry: dict,
    executable: Path,
    inventory: dict,
) -> dict:
    return build_native_function_accounting(
        executable, program_facts, registry, inventory=inventory, repo_root=tmp_path
    )


def test_empty_registry_is_deterministic_exact_and_never_heuristically_promotes(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.delitem(
        native_accounting._UPSTREAM_ADAPTERS,
        "synthetic_native_function_analysis",
    )
    executable, inventory, program_facts = _write_inputs(tmp_path, first_thunk=1)
    registry = _registry(program_facts)

    result = _build(tmp_path, program_facts, registry, executable, inventory)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert encode_native_function_accounting(
        result
    ) == encode_native_function_accounting(
        _build(tmp_path, program_facts, registry, executable, inventory)
    )
    assert [
        item["review"]["achieved_level"] for item in result["functions"]
    ] == ["L0", "L0"]
    assert [item["review"]["ownership"] for item in result["functions"]] == [
        "unknown",
        "unknown",
    ]
    assert result["method"]["registered_upstream_analysis_adapters"] == [
        "pe_native_lua_direct_import_call_census",
        "pe_native_lua_immediate_cclosure_callback_census",
        "pe_native_lua_immediate_cclosure_setfield_publication_census",
    ]
    summary = result["summary"]
    assert summary["atlas_functions"] == 2
    assert summary["reviewed_functions"] == 0
    assert summary["unreviewed_functions"] == 2
    assert summary["level_L0"] == 2
    assert summary["level_L1"] == 0
    assert summary["level_L2"] == 0
    assert summary["reviewed_exclusions"] == 0
    assert summary["ownership_unknown"] == 2
    assert summary["subsystem_unknown"] == 2
    assert summary["ghidra_thunk_flagged"] == 1
    assert summary["repeated_body_groups"] == 0
    assert summary["functions_in_repeated_body_groups"] == 0
    assert summary["name_source_counts"] == [
        {"name_source": "DEFAULT", "functions": 1},
        {"name_source": "USER_DEFINED", "functions": 1},
    ]
    assert summary["ghidra_declared_call_records"] == 1
    assert summary["declared_calls_without_target_entry"] == 0
    assert summary["omitted_call_targets"] == 3
    assert summary["schema_violations"] == 0
    defaults = {
        "level_counts": ("level", "L0"),
        "boundary_status_counts": ("boundary_status", "atlas_analysis_only"),
        "ownership_counts": ("ownership", "unknown"),
        "subsystem_counts": ("subsystem", "unknown"),
        "native_lua_boundary_state_counts": (
            "native_lua_boundary_state",
            "unknown",
        ),
        "reference_status_counts": (
            "reference_status",
            "atlas_declared_direct_only",
        ),
        "exclusion_counts": ("exclusion", "none"),
        "evidence_class_counts": ("evidence_class", "unresolved"),
    }
    for partition_name, (category_field, expected_category) in defaults.items():
        partition = {
            item[category_field]: item["functions"]
            for item in summary[partition_name]
        }
        assert sum(partition.values()) == 2
        assert partition[expected_category] == 2
        assert all(
            count == 0
            for category, count in partition.items()
            if category != expected_category
        )
    assert summary["native_lua_roles_are_nonexclusive"] is True
    assert summary["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 0},
        {"native_lua_role": "lua_api_consumer", "functions": 0},
        {"native_lua_role": "registered_lua_callable", "functions": 0},
        {"native_lua_role": "registration_builder", "functions": 0},
    ]
    assert result["review_candidates"]["affects_review_or_level"] is False
    assert result["review_candidates"]["ghidra_thunk_flagged_entry_rvas"] == [
        "0x00001020"
    ]


def test_committed_schema_v2_registry_and_accounting_identity():
    programs = _REPO_ROOT / "data" / "observatory" / "programs"
    registry_path = programs / (
        "windows_build_13725832_31fe35265598_"
        "native_function_review_registry.json"
    )
    accounting_path = programs / (
        "windows_build_13725832_31fe35265598_native_function_accounting.json"
    )

    def read_and_hash(path: Path) -> tuple[bytes, dict, str]:
        payload = path.read_bytes()
        value = json.loads(payload)
        canonical = (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        return payload, value, hashlib.sha256(canonical).hexdigest()

    registry_payload, registry, registry_canonical = read_and_hash(registry_path)
    accounting_payload, accounting, accounting_canonical = read_and_hash(
        accounting_path
    )
    assert hashlib.sha256(registry_payload).hexdigest() == (
        _COMMITTED_REGISTRY_RAW_SHA256
    )
    assert registry_canonical == _COMMITTED_REGISTRY_CANONICAL_SHA256
    assert hashlib.sha256(accounting_payload).hexdigest() == (
        _COMMITTED_ACCOUNTING_RAW_SHA256
    )
    assert accounting_canonical == _COMMITTED_ACCOUNTING_CANONICAL_SHA256
    assert registry["schema_version"] == accounting["schema_version"] == 2
    assert registry["claims"] == []
    assert len(accounting["functions"]) == 25312
    assert accounting["summary"]["level_L0"] == 25312
    assert accounting["summary"]["level_L1"] == 0
    assert accounting["summary"]["level_L2"] == 0
    assert accounting["method"]["registered_upstream_analysis_adapters"] == [
        "pe_native_lua_direct_import_call_census",
        "pe_native_lua_immediate_cclosure_callback_census",
        "pe_native_lua_immediate_cclosure_setfield_publication_census",
    ]
    assert accounting["summary"]["native_lua_boundary_state_counts"] == [
        {"functions": 0, "native_lua_boundary_state": "none"},
        {"functions": 0, "native_lua_boundary_state": "roles"},
        {"functions": 25312, "native_lua_boundary_state": "unknown"},
    ]
    assert accounting["summary"]["native_lua_role_counts"] == [
        {"functions": 0, "native_lua_role": "cclosure_callback_target"},
        {"functions": 0, "native_lua_role": "lua_api_consumer"},
        {"functions": 0, "native_lua_role": "registered_lua_callable"},
        {"functions": 0, "native_lua_role": "registration_builder"},
    ]
    assert all(
        item["review"]["native_lua_boundary"]
        == {"state": "unknown", "roles": []}
        for item in accounting["functions"]
    )


def test_reviewed_l2_claim_requires_exact_pins_and_repo_local_identity_evidence(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    result = _build(tmp_path, program_facts, registry, executable, inventory)

    assert result["summary"]["level_L2"] == 1
    assert result["summary"]["level_L0"] == 1
    review = result["functions"][0]["review"]
    assert review["achieved_level"] == "L2"
    assert review["native_lua_boundary"] == {
        "state": "roles",
        "roles": ["lua_api_consumer", "registered_lua_callable"],
    }
    assert result["summary"]["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 0},
        {"native_lua_role": "lua_api_consumer", "functions": 1},
        {"native_lua_role": "registered_lua_callable", "functions": 1},
        {"native_lua_role": "registration_builder", "functions": 0},
    ]
    assert review["evidence"] == [reference]
    assert validate_native_function_accounting(
        executable,
        result,
        program_facts,
        registry,
        inventory=inventory,
        repo_root=tmp_path,
    )["status"] == "verified"


def test_reviewed_none_boundary_uses_whole_field_support(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    native_lua_boundary = {"state": "none", "roles": []}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=native_lua_boundary,
    )
    result = _build(
        tmp_path,
        program_facts,
        _registry(
            program_facts,
            [
                _l2_claim(
                    program_facts,
                    reference,
                    native_lua_boundary=native_lua_boundary,
                )
            ],
        ),
        executable,
        inventory,
    )

    assert result["functions"][0]["review"]["native_lua_boundary"] == native_lua_boundary
    assert result["summary"]["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 0},
        {"native_lua_role": "lua_api_consumer", "functions": 0},
        {"native_lua_role": "registered_lua_callable", "functions": 0},
        {"native_lua_role": "registration_builder", "functions": 0},
    ]


@pytest.mark.parametrize(
    "native_lua_boundary, message",
    [
        ("registered_lua_callable", "must be an object"),
        ({"state": "unknown", "roles": ["lua_api_consumer"]}, "cannot publish"),
        ({"state": "none", "roles": ["lua_api_consumer"]}, "cannot publish"),
        ({"state": "roles", "roles": []}, "requires at least one"),
        (
            {
                "state": "roles",
                "roles": ["registered_lua_callable", "lua_api_consumer"],
            },
            "unique and canonically sorted",
        ),
        ({"state": "roles", "roles": ["not_a_role"]}, "unsupported role"),
    ],
)
def test_native_lua_boundary_v2_is_strict(
    tmp_path: Path,
    native_lua_boundary,
    message: str,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    claim = _l2_claim(program_facts, reference)
    claim["native_lua_boundary"] = native_lua_boundary

    with pytest.raises(NativeFunctionAccountingError, match=message):
        _build(
            tmp_path,
            program_facts,
            _registry(program_facts, [claim]),
            executable,
            inventory,
        )


def test_native_lua_role_atoms_must_equal_the_reviewed_role_set(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def remove_registered_callable(review, _support, _upstream):
        review["records"][0]["support"] = [
            item
            for item in review["records"][0]["support"]
            if item["role"] != "registered_lua_callable"
        ]

    _rewrite_evidence_chain(tmp_path, reference, remove_registered_callable)
    with pytest.raises(NativeFunctionAccountingError, match="native Lua roles differ"):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_native_lua_role_atoms_reject_duplicate_source_reference(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def duplicate_role(review, _support, _upstream):
        role_support = next(
            item
            for item in review["records"][0]["support"]
            if item["role"] == "lua_api_consumer"
        )
        review["records"][0]["support"].append(copy.deepcopy(role_support))

    _rewrite_evidence_chain(tmp_path, reference, duplicate_role)
    with pytest.raises(
        NativeFunctionAccountingError,
        match="duplicate support evidence reference",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_native_lua_role_allows_distinct_corroborating_sources(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def add_corroboration(review, support, upstream):
        role = "lua_api_consumer"
        support_index = next(
            index
            for index, item in enumerate(support["records"])
            if item["role"] == role
        )
        upstream_index = len(upstream["records"])
        corroborating_upstream = copy.deepcopy(
            upstream["records"][support_index]
        )
        corroborating_upstream["statement"] = (
            "Independent synthetic Lua API consumer observation."
        )
        upstream["records"].append(corroborating_upstream)

        new_support_index = len(support["records"])
        corroborating_support = copy.deepcopy(support["records"][support_index])
        corroborating_support["statement"] = (
            "Independent reviewed Lua API consumer support."
        )
        corroborating_support["sources"][0]["json_pointer"] = (
            f"/records/{upstream_index}"
        )
        support["records"].append(corroborating_support)

        original_reference = next(
            item
            for item in review["records"][0]["support"]
            if item["role"] == role
        )
        corroborating_reference = copy.deepcopy(original_reference)
        corroborating_reference["json_pointer"] = f"/records/{new_support_index}"
        review["records"][0]["support"].append(corroborating_reference)
        review["records"][0]["support"].sort(
            key=lambda item: (
                item["support_class"],
                "" if item["role"] is None else item["role"],
                item["path"],
                item["json_pointer"],
            )
        )

    _rewrite_evidence_chain(tmp_path, reference, add_corroboration)
    result = _build(tmp_path, program_facts, registry, executable, inventory)

    assert result["functions"][0]["review"]["achieved_level"] == "L2"


def test_accounting_schema_v2_rejects_legacy_registry(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    registry = _registry(program_facts)
    registry["schema_version"] = 1

    with pytest.raises(NativeFunctionAccountingError, match="unsupported review registry schema"):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_review_evidence_requires_dedicated_kind_and_matching_dimensions(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda review, _support, _upstream: review.update(
            analysis_kind=ANALYSIS_KIND
        ),
    )
    with pytest.raises(NativeFunctionAccountingError, match="is not.*review"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        name="dimension.json",
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda review, _support, _upstream: review["records"][0].update(
            ownership="third_party"
        ),
    )
    with pytest.raises(
        NativeFunctionAccountingError,
        match="review dimension differs at ownership",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_review_support_requires_complete_bound_and_strong_classes(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    function = program_facts["functions"][0]

    reference = _write_evidence(tmp_path, program_facts["identity"], function)
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda review, _support, _upstream: review["records"][0]["support"].pop(),
    )
    with pytest.raises(NativeFunctionAccountingError, match="classes differ"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path, program_facts["identity"], function, name="weak.json"
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda _review, support, _upstream: support["records"][0].update(
            evidence_class="inference"
        ),
    )
    with pytest.raises(NativeFunctionAccountingError, match="weaker than"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path, program_facts["identity"], function, name="empty-source.json"
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda _review, support, _upstream: support["records"][0][
            "sources"
        ].clear(),
    )
    with pytest.raises(NativeFunctionAccountingError, match="must be non-empty"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path, program_facts["identity"], function, name="self-source.json"
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def make_support_self_cite(_review, support, _upstream):
        support["records"][0]["sources"][0]["path"] = (
            "evidence/self-source.support.json"
        )

    _rewrite_evidence_chain(tmp_path, reference, make_support_self_cite)
    with pytest.raises(NativeFunctionAccountingError, match="cannot self-cite"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path, program_facts["identity"], function, name="assertion.json"
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def change_support_assertion(_review, support, _upstream):
        next(
            record
            for record in support["records"]
            if record["support_class"] == "ownership"
        )["assertion_sha256"] = "0" * 64

    _rewrite_evidence_chain(tmp_path, reference, change_support_assertion)
    with pytest.raises(
        NativeFunctionAccountingError,
        match="supports a different structured assertion",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_upstream_analysis_is_allowlisted_and_derives_the_assertion(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    function = program_facts["functions"][0]
    reference = _write_evidence(tmp_path, program_facts["identity"], function)
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    _rewrite_evidence_chain(
        tmp_path,
        reference,
        lambda _review, _support, upstream: upstream.update(
            analysis_kind="unregistered_analysis"
        ),
    )
    with pytest.raises(NativeFunctionAccountingError, match="unsupported upstream"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    reference = _write_evidence(
        tmp_path, program_facts["identity"], function, name="upstream-value.json"
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    def change_upstream_value(_review, _support, upstream):
        next(
            record
            for record in upstream["records"]
            if record["support_class"] == "ownership"
        )["observed"] = {"ownership": "third_party"}

    _rewrite_evidence_chain(tmp_path, reference, change_upstream_value)
    with pytest.raises(
        NativeFunctionAccountingError,
        match="different structured assertion",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_direct_lua_census_derives_only_positive_consumer_role_end_to_end(
    tmp_path: Path,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    boundary = {"state": "roles", "roles": ["lua_api_consumer"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=boundary,
    )
    _bind_direct_census_source(tmp_path, reference, census)

    result = _build(
        tmp_path,
        program_facts,
        _registry(
            program_facts,
            [
                _l2_claim(
                    program_facts,
                    reference,
                    native_lua_boundary=boundary,
                )
            ],
        ),
        executable,
        inventory,
    )

    assert result["functions"][0]["review"]["native_lua_boundary"] == boundary
    assert result["summary"]["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 0},
        {"native_lua_role": "lua_api_consumer", "functions": 1},
        {"native_lua_role": "registered_lua_callable", "functions": 0},
        {"native_lua_role": "registration_builder", "functions": 0},
    ]
    assert "pe_native_lua_direct_import_call_census" in result["method"][
        "registered_upstream_analysis_adapters"
    ]


@pytest.mark.parametrize(
    "overclaimed_role",
    [
        "cclosure_callback_target",
        "registered_lua_callable",
        "registration_builder",
    ],
)
def test_direct_lua_census_rejects_other_role_overclaim_end_to_end(
    tmp_path: Path,
    overclaimed_role: str,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    boundary = {"state": "roles", "roles": [overclaimed_role]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=boundary,
    )
    _bind_direct_census_source(
        tmp_path,
        reference,
        census,
        role=overclaimed_role,
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the lua_api_consumer role",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "support_class,native_lua_boundary",
    [
        ("boundary", {"state": "roles", "roles": ["lua_api_consumer"]}),
        ("ownership", {"state": "roles", "roles": ["lua_api_consumer"]}),
        (
            "immediate_references",
            {"state": "roles", "roles": ["lua_api_consumer"]},
        ),
        ("semantic_io", {"state": "roles", "roles": ["lua_api_consumer"]}),
        ("native_lua_boundary", {"state": "none", "roles": []}),
    ],
)
def test_direct_lua_census_rejects_non_role_support_end_to_end(
    tmp_path: Path,
    support_class: str,
    native_lua_boundary: dict,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=native_lua_boundary,
    )
    _bind_direct_census_source(
        tmp_path,
        reference,
        census,
        support_class=support_class,
        role=None,
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the lua_api_consumer role",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        native_lua_boundary=native_lua_boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "tamper",
    ["whole_atlas", "unrelated_record", "zero_call_selected_record"],
)
def test_direct_lua_adapter_validates_the_whole_census_before_deriving(
    tmp_path: Path,
    tamper: str,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    if tamper == "whole_atlas":
        census["atlas"]["canonical_sha256"] = "0" * 64
    elif tamper == "unrelated_record":
        unrelated = copy.deepcopy(census["records"][0])
        unrelated["entry_rva"] = program_facts["functions"][1]["entry_rva"]
        unrelated["atlas_record_sha256"] = atlas_record_sha256(
            program_facts["functions"][1]
        )
        unrelated["direct_lua_import_calls"][0]["call_rva"] = (
            program_facts["functions"][1]["entry_rva"]
        )
        census["records"].append(unrelated)
    else:
        census["records"][0]["direct_lua_import_calls"] = []
        census["records"][0]["direct_call_count"] = 0
        census["records"][0]["import_names"] = []

    boundary = {"state": "roles", "roles": ["lua_api_consumer"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=boundary,
    )
    _bind_direct_census_source(tmp_path, reference, census)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="failed exact binary verification",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_structurally_consistent_fabricated_census_cannot_support_a_fact(
    tmp_path: Path,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    census["records"][0]["direct_lua_import_calls"][0]["call_rva"] = (
        "0x00001021"
    )
    assert validate_native_lua_direct_call_structure(
        census,
        program_facts,
    )["status"] == "structurally_verified"

    boundary = {"state": "roles", "roles": ["lua_api_consumer"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=boundary,
    )
    _bind_direct_census_source(tmp_path, reference, census)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="failed exact binary verification",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_direct_lua_exact_binary_verification_is_cached_per_source(
    monkeypatch,
    tmp_path: Path,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    from src.observatory import native_lua_direct_calls as direct_calls

    calls = 0
    original = direct_calls.validate_native_lua_direct_call_census

    def counting_validator(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        direct_calls,
        "validate_native_lua_direct_call_census",
        counting_validator,
    )
    source_sha256 = hashlib.sha256(
        json.dumps(census, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache: dict = {}
    kwargs = {
        "executable": executable,
        "inventory": inventory,
        "program_facts": program_facts,
        "source_sha256": source_sha256,
        "verification_cache": cache,
        "entry_rva": program_facts["functions"][0]["entry_rva"],
        "atlas_record_identity": atlas_record_sha256(
            program_facts["functions"][0]
        ),
        "support_class": "native_lua_role",
        "role": "lua_api_consumer",
        "label": "cached direct census",
    }

    first = native_accounting._adapt_native_lua_direct_call_census(
        census,
        json_pointer="/records/0",
        **kwargs,
    )
    second = native_accounting._adapt_native_lua_direct_call_census(
        census,
        json_pointer="/records/0",
        **kwargs,
    )

    assert first == second
    assert calls == 1
    assert list(cache) == [
        ("pe_native_lua_direct_import_call_census", source_sha256)
    ]


def test_direct_lua_adapter_rejects_a_pointed_record_for_another_function(
    tmp_path: Path,
):
    executable, inventory, program_facts, census = _write_direct_lua_inputs(
        tmp_path
    )
    boundary = {"state": "roles", "roles": ["lua_api_consumer"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_direct_census_source(tmp_path, reference, census)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="does not describe the exact atlas record",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_direct_lua_adapter_rejects_exclusion_support_without_interpretation():
    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the lua_api_consumer role",
    ):
        native_accounting._adapt_native_lua_direct_call_census(
            {},
            executable=Path("missing.exe"),
            inventory={},
            program_facts={},
            source_sha256="0" * 64,
            verification_cache={},
            json_pointer="/records/0",
            entry_rva="0x00001020",
            atlas_record_identity="0" * 64,
            support_class="exclusion",
            role=None,
            label="exclusion source",
        )


def test_direct_lua_adapter_keeps_records_only_pointer_contract():
    with pytest.raises(
        NativeFunctionAccountingError,
        match="must point directly to one records entry",
    ):
        native_accounting._adapt_native_lua_direct_call_census(
            {},
            executable=Path("missing.exe"),
            inventory={},
            program_facts={},
            source_sha256="0" * 64,
            verification_cache={},
            json_pointer="/callback_targets/0",
            entry_rva="0x00001020",
            atlas_record_identity="0" * 64,
            support_class="native_lua_role",
            role="lua_api_consumer",
            label="wrong direct pointer",
        )


def test_callback_adapter_rejects_exclusion_support_without_interpretation():
    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the cclosure_callback_target role",
    ):
        native_accounting._adapt_native_lua_cclosure_callback_census(
            {},
            executable=Path("missing.exe"),
            inventory={},
            program_facts={},
            source_sha256="0" * 64,
            verification_cache={},
            json_pointer="/callback_targets/0",
            entry_rva="0x00001020",
            atlas_record_identity="0" * 64,
            support_class="exclusion",
            role=None,
            label="callback exclusion source",
        )


def test_callback_census_derives_only_cclosure_target_end_to_end(
    tmp_path: Path,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": ["cclosure_callback_target"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(tmp_path, reference, callbacks)

    result = _build(
        tmp_path,
        program_facts,
        _registry(
            program_facts,
            [
                _l2_claim(
                    program_facts,
                    reference,
                    entry=1,
                    native_lua_boundary=boundary,
                )
            ],
        ),
        executable,
        inventory,
    )

    assert result["functions"][1]["review"]["native_lua_boundary"] == boundary
    assert result["summary"]["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 1},
        {"native_lua_role": "lua_api_consumer", "functions": 0},
        {"native_lua_role": "registered_lua_callable", "functions": 0},
        {"native_lua_role": "registration_builder", "functions": 0},
    ]


@pytest.mark.parametrize(
    "overclaimed_role",
    ["lua_api_consumer", "registered_lua_callable", "registration_builder"],
)
def test_callback_census_rejects_other_role_overclaims_end_to_end(
    tmp_path: Path,
    overclaimed_role: str,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": [overclaimed_role]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(
        tmp_path,
        reference,
        callbacks,
        role=overclaimed_role,
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the cclosure_callback_target role",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "support_class,native_lua_boundary",
    [
        ("boundary", {"state": "roles", "roles": ["cclosure_callback_target"]}),
        ("ownership", {"state": "roles", "roles": ["cclosure_callback_target"]}),
        (
            "immediate_references",
            {"state": "roles", "roles": ["cclosure_callback_target"]},
        ),
        (
            "semantic_io",
            {"state": "roles", "roles": ["cclosure_callback_target"]},
        ),
        ("native_lua_boundary", {"state": "none", "roles": []}),
    ],
)
def test_callback_census_rejects_non_role_support_end_to_end(
    tmp_path: Path,
    support_class: str,
    native_lua_boundary: dict,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=native_lua_boundary,
    )
    _bind_callback_census_source(
        tmp_path,
        reference,
        callbacks,
        support_class=support_class,
        role=None,
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="prove only the cclosure_callback_target role",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=native_lua_boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "json_pointer",
    [
        "/resolved_sites/0",
        "/unresolved_sites/0",
        "/callback_targets/0/callback_entry_rva",
        "/callback_targets",
    ],
)
def test_callback_census_rejects_non_target_and_nested_pointers(
    tmp_path: Path,
    json_pointer: str,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": ["cclosure_callback_target"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(
        tmp_path,
        reference,
        callbacks,
        json_pointer=json_pointer,
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="must point directly to one callback target",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_callback_census_rejects_a_target_for_another_function(
    tmp_path: Path,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": ["cclosure_callback_target"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(tmp_path, reference, callbacks)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="does not describe the exact atlas record",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=0,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize("tamper", ["zero", "stale", "unrelated"])
def test_callback_adapter_rejects_tampered_whole_census(
    tmp_path: Path,
    tamper: str,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    if tamper == "zero":
        callbacks["callback_targets"][0]["resolved_site_count"] = 0
    elif tamper == "stale":
        callbacks["direct_call_census"]["canonical_sha256"] = "0" * 64
    else:
        callbacks["unresolved_sites"].append(
            {
                "caller_entry_rva": "0x00001020",
                "resolution": "unresolved_non_immediate_callback",
            }
        )
    boundary = {"state": "roles", "roles": ["cclosure_callback_target"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(tmp_path, reference, callbacks)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="failed exact binary verification",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_structurally_plausible_callback_forgery_cannot_support_a_fact(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    callbacks["resolved_sites"][0]["literal_upvalue_count"] = 3
    callbacks["resolved_sites"][0]["upvalue_push"]["sha256"] = hashlib.sha256(
        b"\x6a\x03"
    ).hexdigest()
    assert validate_native_lua_cclosure_callback_structure(
        callbacks,
        direct_calls,
        program_facts,
    )["status"] == "structurally_verified"
    boundary = {"state": "roles", "roles": ["cclosure_callback_target"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_callback_census_source(tmp_path, reference, callbacks)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="failed exact binary verification",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_callback_exact_binary_verification_is_cached_per_source(
    monkeypatch,
    tmp_path: Path,
):
    executable, inventory, program_facts, _direct, callbacks = (
        _write_callback_inputs(tmp_path)
    )
    from src.observatory import native_lua_cclosure_callbacks as callback_module

    calls = 0
    original = callback_module.validate_native_lua_cclosure_callback_census

    def counting_validator(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        callback_module,
        "validate_native_lua_cclosure_callback_census",
        counting_validator,
    )
    source_sha256 = hashlib.sha256(
        json.dumps(callbacks, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache: dict = {}
    kwargs = {
        "executable": executable,
        "inventory": inventory,
        "program_facts": program_facts,
        "source_sha256": source_sha256,
        "verification_cache": cache,
        "json_pointer": "/callback_targets/0",
        "entry_rva": program_facts["functions"][1]["entry_rva"],
        "atlas_record_identity": atlas_record_sha256(
            program_facts["functions"][1]
        ),
        "support_class": "native_lua_role",
        "role": "cclosure_callback_target",
        "label": "cached callback census",
    }

    first = native_accounting._adapt_native_lua_cclosure_callback_census(
        callbacks,
        **kwargs,
    )
    second = native_accounting._adapt_native_lua_cclosure_callback_census(
        callbacks,
        **kwargs,
    )

    assert first == second
    assert calls == 1
    assert list(cache) == [
        ("pe_native_lua_immediate_cclosure_callback_census", source_sha256)
    ]


def test_setfield_publication_census_derives_registered_target_and_builder(
    tmp_path: Path,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    target_boundary = {"state": "roles", "roles": ["registered_lua_callable"]}
    builder_boundary = {"state": "roles", "roles": ["registration_builder"]}
    target_reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        name="registered-target.json",
        native_lua_boundary=target_boundary,
    )
    builder_reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        name="registration-builder.json",
        native_lua_boundary=builder_boundary,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        target_reference,
        publications,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        builder_reference,
        publications,
        json_pointer="/builders/0",
        role="registration_builder",
    )

    result = _build(
        tmp_path,
        program_facts,
        _registry(
            program_facts,
            [
                _l2_claim(
                    program_facts,
                    builder_reference,
                    entry=0,
                    native_lua_boundary=builder_boundary,
                ),
                _l2_claim(
                    program_facts,
                    target_reference,
                    entry=1,
                    native_lua_boundary=target_boundary,
                ),
            ],
        ),
        executable,
        inventory,
    )

    assert result["functions"][1]["review"]["native_lua_boundary"] == (
        target_boundary
    )
    assert result["functions"][0]["review"]["native_lua_boundary"] == (
        builder_boundary
    )
    assert result["summary"]["native_lua_role_counts"] == [
        {"native_lua_role": "cclosure_callback_target", "functions": 0},
        {"native_lua_role": "lua_api_consumer", "functions": 0},
        {"native_lua_role": "registered_lua_callable", "functions": 1},
        {"native_lua_role": "registration_builder", "functions": 1},
    ]


@pytest.mark.parametrize(
    ("entry", "role", "json_pointer", "message"),
    [
        (1, "registration_builder", "/registered_targets/0", "registration builder"),
        (0, "registered_lua_callable", "/builders/0", "registered callback target"),
        (
            1,
            "cclosure_callback_target",
            "/registered_targets/0",
            "registered_lua_callable or registration_builder",
        ),
        (
            1,
            "lua_api_consumer",
            "/registered_targets/0",
            "registered_lua_callable or registration_builder",
        ),
    ],
)
def test_setfield_publication_census_rejects_cross_and_other_roles(
    tmp_path: Path,
    entry: int,
    role: str,
    json_pointer: str,
    message: str,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": [role]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][entry],
        native_lua_boundary=boundary,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        reference,
        publications,
        json_pointer=json_pointer,
        role=role,
    )

    with pytest.raises(NativeFunctionAccountingError, match=message):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=entry,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "support_class,native_lua_boundary",
    [
        ("boundary", {"state": "roles", "roles": ["registered_lua_callable"]}),
        ("ownership", {"state": "roles", "roles": ["registered_lua_callable"]}),
        (
            "immediate_references",
            {"state": "roles", "roles": ["registered_lua_callable"]},
        ),
        (
            "semantic_io",
            {"state": "roles", "roles": ["registered_lua_callable"]},
        ),
        ("native_lua_boundary", {"state": "none", "roles": []}),
    ],
)
def test_setfield_publication_census_rejects_non_role_support(
    tmp_path: Path,
    support_class: str,
    native_lua_boundary: dict,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=native_lua_boundary,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        reference,
        publications,
        support_class=support_class,
        role=None,
    )

    with pytest.raises(
        NativeFunctionAccountingError, match="prove only native Lua roles"
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=native_lua_boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    ("entry", "role", "json_pointer", "message"),
    [
        (
            1,
            "registered_lua_callable",
            "/registered_targets/0/callback_entry_rva",
            "registered callback target",
        ),
        (1, "registered_lua_callable", "/registered_targets", "registered callback target"),
        (1, "registered_lua_callable", "/registered_targets/00", "registered callback target"),
        (1, "registered_lua_callable", "/builders/0", "registered callback target"),
        (1, "registered_lua_callable", "/publications/0", "registered callback target"),
        (
            0,
            "registration_builder",
            "/builders/0/builder_entry_rva",
            "registration builder",
        ),
        (0, "registration_builder", "/builders", "registration builder"),
        (0, "registration_builder", "/builders/00", "registration builder"),
        (0, "registration_builder", "/registered_targets/0", "registration builder"),
    ],
)
def test_setfield_publication_census_requires_direct_role_specific_pointers(
    tmp_path: Path,
    entry: int,
    role: str,
    json_pointer: str,
    message: str,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": [role]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][entry],
        native_lua_boundary=boundary,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        reference,
        publications,
        json_pointer=json_pointer,
        role=role,
    )

    with pytest.raises(NativeFunctionAccountingError, match=message):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=entry,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    ("entry", "role", "json_pointer"),
    [
        (0, "registered_lua_callable", "/registered_targets/0"),
        (1, "registration_builder", "/builders/0"),
    ],
)
def test_setfield_publication_census_rejects_wrong_atlas_record(
    tmp_path: Path,
    entry: int,
    role: str,
    json_pointer: str,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    boundary = {"state": "roles", "roles": [role]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][entry],
        native_lua_boundary=boundary,
    )
    _bind_setfield_publication_census_source(
        tmp_path,
        reference,
        publications,
        json_pointer=json_pointer,
        role=role,
    )

    with pytest.raises(
        NativeFunctionAccountingError, match="does not describe the exact atlas record"
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=entry,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


@pytest.mark.parametrize("tamper", ["zero_publication_count", "whole_artifact"])
def test_setfield_publication_adapter_rejects_tampered_whole_census(
    tmp_path: Path,
    tamper: str,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    if tamper == "zero_publication_count":
        publications["registered_targets"][0]["publication_site_count"] = 0
    else:
        publications["builders"][0]["key_texts"] = ["unexpected"]
    boundary = {"state": "roles", "roles": ["registered_lua_callable"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_setfield_publication_census_source(tmp_path, reference, publications)

    with pytest.raises(
        NativeFunctionAccountingError, match="failed exact binary verification"
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_structurally_plausible_setfield_publication_forgery_cannot_support_fact(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls, callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    publication = publications["publications"][0]
    forged_key_rva = 0x00001300
    publication["key_rva"] = f"0x{forged_key_rva:08x}"
    publication["key_push"]["sha256"] = hashlib.sha256(
        b"\x68" + (_IMAGE_BASE + forged_key_rva).to_bytes(4, "little")
    ).hexdigest()
    assert validate_native_lua_cclosure_setfield_publication_structure(
        publications,
        direct_calls,
        callbacks,
        program_facts,
    )["status"] == "structurally_verified"
    boundary = {"state": "roles", "roles": ["registered_lua_callable"]}
    reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        native_lua_boundary=boundary,
    )
    _bind_setfield_publication_census_source(tmp_path, reference, publications)

    with pytest.raises(
        NativeFunctionAccountingError, match="failed exact binary verification"
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(
                program_facts,
                [
                    _l2_claim(
                        program_facts,
                        reference,
                        entry=1,
                        native_lua_boundary=boundary,
                    )
                ],
            ),
            executable,
            inventory,
        )


def test_setfield_publication_exact_binary_verification_is_cached_per_source(
    monkeypatch,
    tmp_path: Path,
):
    executable, inventory, program_facts, _direct, _callbacks, publications = (
        _write_setfield_publication_inputs(tmp_path)
    )
    from src.observatory import (
        native_lua_cclosure_setfield_publications as publication_module,
    )

    calls = 0
    original = publication_module.validate_native_lua_cclosure_setfield_publication_census

    def counting_validator(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        publication_module,
        "validate_native_lua_cclosure_setfield_publication_census",
        counting_validator,
    )
    source_sha256 = hashlib.sha256(
        json.dumps(publications, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache: dict = {}
    common = {
        "executable": executable,
        "inventory": inventory,
        "program_facts": program_facts,
        "source_sha256": source_sha256,
        "verification_cache": cache,
        "support_class": "native_lua_role",
        "label": "cached setfield publication census",
    }
    target = native_accounting._adapt_native_lua_cclosure_setfield_publication_census(
        publications,
        json_pointer="/registered_targets/0",
        entry_rva=program_facts["functions"][1]["entry_rva"],
        atlas_record_identity=atlas_record_sha256(program_facts["functions"][1]),
        role="registered_lua_callable",
        **common,
    )
    builder = native_accounting._adapt_native_lua_cclosure_setfield_publication_census(
        publications,
        json_pointer="/builders/0",
        entry_rva=program_facts["functions"][0]["entry_rva"],
        atlas_record_identity=atlas_record_sha256(program_facts["functions"][0]),
        role="registration_builder",
        **common,
    )

    assert target["assertion"] == {"native_lua_role": "registered_lua_callable"}
    assert builder["assertion"] == {"native_lua_role": "registration_builder"}
    assert calls == 1
    assert list(cache) == [
        (
            "pe_native_lua_immediate_cclosure_setfield_publication_census",
            source_sha256,
        )
    ]


def test_l0_cannot_publish_resolved_higher_level_dimensions(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    claim = _l2_claim(program_facts, reference)
    claim.update(
        claimed_level="L0",
        evidence_class="hypothesis",
        reference_status="atlas_declared_direct_only",
    )
    with pytest.raises(NativeFunctionAccountingError, match="L0 cannot publish"):
        _build(
            tmp_path,
            program_facts,
            _registry(program_facts, [claim]),
            executable,
            inventory,
        )

    claim = _l2_claim(program_facts, reference)
    claim.update(
        claimed_level="L1",
        native_lua_boundary={"state": "unknown", "roles": []},
    )
    with pytest.raises(NativeFunctionAccountingError, match="L1 cannot publish"):
        _build(
            tmp_path,
            program_facts,
            _registry(program_facts, [claim]),
            executable,
            inventory,
        )


@pytest.mark.parametrize("exclusion", ["unreachable", "duplicate_thunk", "data_only"])
def test_type_specific_exclusions_fail_closed(
    tmp_path: Path,
    exclusion: str,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    claim = _l2_claim(program_facts, reference)
    claim.update(exclusion=exclusion, claimed_level="EXCLUDED")
    with pytest.raises(NativeFunctionAccountingError, match="unsupported until"):
        _build(
            tmp_path,
            program_facts,
            _registry(program_facts, [claim]),
            executable,
            inventory,
        )


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda registry: registry.update(atlas_canonical_sha256="0" * 64),
            "different atlas",
        ),
        (
            lambda registry: registry["claims"][0].update(
                atlas_record_sha256="0" * 64
            ),
            "stale atlas record",
        ),
        (
            lambda registry: registry["claims"].append(
                copy.deepcopy(registry["claims"][0])
            ),
            "unique increasing",
        ),
        (
            lambda registry: registry["claims"][0].update(
                entry_rva="0x00001999"
            ),
            "unknown atlas entry",
        ),
        (
            lambda registry: registry["claims"][0].update(
                unexpected_field=True
            ),
            "fields differ",
        ),
        (lambda registry: registry["claims"][0].update(purpose=None), "derives L1"),
        (
            lambda registry: registry["claims"][0].update(
                exclusion="third_party", claimed_level="EXCLUDED"
            ),
            "third-party exclusions",
        ),
    ],
)
def test_rejects_stale_malformed_unknown_and_overclaimed_registry_claims(
    tmp_path: Path,
    mutate,
    message: str,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    mutate(registry)

    with pytest.raises(NativeFunctionAccountingError, match=message):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_rejects_claims_out_of_canonical_entry_order(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    second_reference = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][1],
        name="second-review.json",
    )
    first = _l2_claim(program_facts, reference, entry=0)
    second = _l2_claim(program_facts, second_reference, entry=1)
    registry = _registry(program_facts, [second, first])

    with pytest.raises(NativeFunctionAccountingError, match="unique increasing"):
        _build(tmp_path, program_facts, registry, executable, inventory)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("sha256", "0" * 64, "SHA-256 differs"),
        ("json_pointer", "/records/99", "does not resolve"),
    ],
)
def test_rejects_bad_repository_evidence_sha_and_pointer(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][0]
    )
    reference[field] = value
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    with pytest.raises(NativeFunctionAccountingError, match=message):
        _build(tmp_path, program_facts, registry, executable, inventory)


@pytest.mark.parametrize(
    "field, replacement",
    [
        ("build_id", "other-build"),
        ("scripts_revision_sha256", "1" * 64),
        ("maps_revision_sha256", "2" * 64),
        ("appmanifest_sha256", "3" * 64),
        (
            "native_libraries",
            [
                {
                    "architecture": "x86",
                    "format": "pe",
                    "path": "changed.dll",
                    "sha256": "4" * 64,
                    "size": 1,
                }
            ],
        ),
    ],
)
def test_rejects_evidence_from_a_different_build_identity(
    tmp_path: Path,
    field: str,
    replacement,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    wrong_identity = copy.deepcopy(program_facts["identity"])
    wrong_identity[field] = replacement
    reference = _write_evidence(
        tmp_path, wrong_identity, program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    with pytest.raises(
        NativeFunctionAccountingError,
        match=f"identity differs at {field}",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_rejects_evidence_with_partial_or_extended_identity(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    partial_identity = copy.deepcopy(program_facts["identity"])
    partial_identity.pop("maps_revision_sha256")
    reference = _write_evidence(
        tmp_path, partial_identity, program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    with pytest.raises(NativeFunctionAccountingError, match="identity fields differ"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    extended_identity = copy.deepcopy(program_facts["identity"])
    extended_identity["unexpected"] = "field"
    reference = _write_evidence(
        tmp_path,
        extended_identity,
        program_facts["functions"][0],
        name="extended.json",
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])
    with pytest.raises(NativeFunctionAccountingError, match="identity fields differ"):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_rejects_nested_boolean_integer_identity_alias(tmp_path: Path):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    wrong_identity = copy.deepcopy(program_facts["identity"])
    wrong_identity["native_libraries"][0]["size"] = True
    reference = _write_evidence(
        tmp_path, wrong_identity, program_facts["functions"][0]
    )
    registry = _registry(program_facts, [_l2_claim(program_facts, reference)])

    with pytest.raises(
        NativeFunctionAccountingError,
        match="identity differs at native_libraries",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


@pytest.mark.parametrize(
    "candidate",
    [
        "evidence/review.json:claim",
        "C:data/review.json",
        "evidence/CON.json",
        "evidence/CON .json",
        "evidence/COM¹.json",
        "evidence/trailing.",
        "evidence\\review.json",
        "../review.json",
        "/absolute/review.json",
    ],
)
def test_repository_evidence_paths_reject_windows_aliases(candidate: str):
    with pytest.raises(NativeFunctionAccountingError, match="normalized"):
        _safe_repo_path(candidate, "test path")


def test_repository_evidence_rejects_linked_parent_directory(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    payload = b'{"value":"outside"}'
    (external / "review.json").write_bytes(payload)
    linked_parent = repo_root / "evidence"
    try:
        linked_parent.symlink_to(external, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("test host does not permit directory symlinks")

    with pytest.raises(
        NativeFunctionAccountingError,
        match="parent is not a contained real directory",
    ):
        _read_repo_json(
            repo_root,
            _safe_repo_path("evidence/review.json", "test path"),
            hashlib.sha256(payload).hexdigest(),
        )


def test_rejects_evidence_record_joined_to_a_different_atlas_function(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    reference = _write_evidence(
        tmp_path, program_facts["identity"], program_facts["functions"][1]
    )
    registry = _registry(
        program_facts,
        [_l2_claim(program_facts, reference, entry=0)],
    )

    with pytest.raises(
        NativeFunctionAccountingError,
        match="review dimension differs at atlas_record_sha256",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def test_rejects_unsorted_evidence_and_invalid_exclusion_requirements(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    first = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        name="z.json",
    )
    second = _write_evidence(
        tmp_path,
        program_facts["identity"],
        program_facts["functions"][0],
        name="a.json",
    )
    claim = _l2_claim(program_facts, first)
    claim["evidence"] = [first, second]
    registry = _registry(program_facts, [claim])
    with pytest.raises(NativeFunctionAccountingError, match="canonically sorted"):
        _build(tmp_path, program_facts, registry, executable, inventory)

    claim = _l2_claim(program_facts, second)
    claim.update(
        exclusion="third_party",
        claimed_level="EXCLUDED",
        boundary_status="reviewed_conflict",
        evidence_class="inference",
    )
    with pytest.raises(
        NativeFunctionAccountingError,
        match="exclusions require exact boundaries and fact evidence",
    ):
        _build(
            tmp_path,
            program_facts,
            _registry(program_facts, [claim]),
            executable,
            inventory,
        )


def test_verifier_is_exact_and_distinguishes_boolean_from_integer_tampering(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    result = _build(
        tmp_path,
        program_facts,
        _registry(program_facts),
        executable,
        inventory,
    )

    tampered = copy.deepcopy(result)
    tampered["summary"]["atlas_functions"] = True
    with pytest.raises(
        NativeFunctionAccountingError,
        match="exact rebuilt accounting overlay",
    ):
        validate_native_function_accounting(
            executable,
            tampered,
            program_facts,
            _registry(program_facts),
            inventory=inventory,
            repo_root=tmp_path,
        )
    with pytest.raises(NativeFunctionAccountingError, match="floating-point"):
        encode_native_function_accounting({"value": 1.0})


def test_builder_rejects_boolean_program_facts_schema_even_if_registry_is_repinned(
    tmp_path: Path,
):
    executable, inventory, program_facts = _write_inputs(tmp_path)
    program_facts["schema_version"] = True
    registry = _registry(program_facts)

    with pytest.raises(
        NativeFunctionAccountingError,
        match="program-facts prerequisite failed.*schema version",
    ):
        _build(tmp_path, program_facts, registry, executable, inventory)


def _write_cli_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    executable, inventory, program_facts = _write_inputs(tmp_path)
    inventory_path = tmp_path / "inventory.json"
    facts_path = tmp_path / "program-facts.json"
    registry_path = tmp_path / "registry.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    facts_path.write_text(json.dumps(program_facts), encoding="utf-8")
    registry_path.write_text(json.dumps(_registry(program_facts)), encoding="utf-8")
    return executable, inventory_path, facts_path, registry_path


def _cli_build_args(
    executable: Path,
    inventory: Path,
    facts: Path,
    registry: Path,
) -> list[str]:
    return [
        "build",
        "--executable",
        str(executable),
        "--inventory",
        str(inventory),
        "--program-facts",
        str(facts),
        "--registry",
        str(registry),
    ]


def test_cli_build_and_verify_round_trip(tmp_path: Path, capsys):
    executable, inventory, facts, registry = _write_cli_inputs(tmp_path)
    build_args = _cli_build_args(executable, inventory, facts, registry)

    assert itb_native_function_accounting.main(build_args) == 0
    evidence = tmp_path / "accounting.json"
    evidence.write_bytes(capsys.readouterr().out.encode("utf-8"))
    assert itb_native_function_accounting.main(
        [
            "verify",
            "--executable",
            str(executable),
            "--inventory",
            str(inventory),
            "--program-facts",
            str(facts),
            "--registry",
            str(registry),
            "--evidence",
            str(evidence),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


@pytest.mark.parametrize(
    "payload, message",
    [
        ('{"platform":"windows","platform":"windows"}', "duplicate JSON object key"),
        ('{"value":1.5}', "floating-point JSON values are unsupported"),
        ('{"value":NaN}', "invalid JSON constant"),
    ],
)
def test_cli_rejects_duplicate_float_and_nonfinite_json(
    tmp_path: Path,
    capsys,
    payload: str,
    message: str,
):
    executable, inventory, facts, registry = _write_cli_inputs(tmp_path)
    inventory.write_text(payload, encoding="utf-8")

    assert itb_native_function_accounting.main(
        _cli_build_args(executable, inventory, facts, registry)
    ) == 2
    assert message in capsys.readouterr().err


def test_cli_json_reader_rechecks_parent_identity(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "input.json"
    source.write_text('{"value":1}', encoding="utf-8")
    parent = source.parent
    observed = parent.lstat()

    def stale_parent_chain(_path, _label):
        return [
            (
                parent,
                SimpleNamespace(
                    st_mode=observed.st_mode,
                    st_dev=observed.st_dev,
                    st_ino=observed.st_ino + 1,
                ),
            )
        ]

    monkeypatch.setattr(
        itb_native_function_accounting,
        "_require_real_parent_chain",
        stale_parent_chain,
    )

    with pytest.raises(NativeFunctionAccountingError, match="changed while"):
        itb_native_function_accounting._read_json_object(source, "input")


def test_cli_output_is_confined_and_only_replaces_native_accounting(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    executable, inventory, facts, registry = _write_cli_inputs(tmp_path)
    output_root = tmp_path / "data" / "observatory" / "programs"
    monkeypatch.setattr(itb_native_function_accounting, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(itb_native_function_accounting, "_OUTPUT_ROOT", output_root)
    build_args = _cli_build_args(executable, inventory, facts, registry)

    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(tmp_path / "outside.json")]
        )
        == 2
    )
    assert "output must be a direct child" in capsys.readouterr().err

    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / "accounting.json"
    destination.write_text('{"analysis_kind":"other"}', encoding="utf-8")
    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(destination)]
        )
        == 2
    )
    assert (
        "refusing to replace an existing non-native-accounting artifact"
        in capsys.readouterr().err
    )

    assert itb_native_function_accounting.main(build_args) == 0
    valid_rendered = capsys.readouterr().out
    destination.write_bytes(valid_rendered.encode("utf-8"))
    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(destination)]
        )
        == 0
    )
    assert (
        json.loads(destination.read_text(encoding="utf-8"))["analysis_kind"]
        == ANALYSIS_KIND
    )

    deterministic = destination.read_bytes()
    destination.write_text(
        json.dumps(json.loads(deterministic)),
        encoding="utf-8",
    )
    reformatted = destination.read_bytes()
    assert reformatted != deterministic
    assert (
        itb_native_function_accounting.main(
            [
                "verify",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--program-facts",
                str(facts),
                "--registry",
                str(registry),
                "--evidence",
                str(destination),
            ]
        )
        == 2
    )
    assert "deterministically encoded" in capsys.readouterr().err
    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(destination)]
        )
        == 2
    )
    assert "deterministically encoded" in capsys.readouterr().err
    assert destination.read_bytes() == reformatted
    destination.write_bytes(deterministic)

    differing_evidence = json.loads(valid_rendered)
    differing_evidence["summary"]["schema_violations"] = 1
    destination.write_text(json.dumps(differing_evidence), encoding="utf-8")
    preserved = destination.read_bytes()
    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(destination)]
        )
        == 2
    )
    assert "overwrite differing" in capsys.readouterr().err
    assert destination.read_bytes() == preserved

    different_identity = json.loads(valid_rendered)
    different_identity["build_identity"]["build_id"] = "different"
    destination.write_text(json.dumps(different_identity), encoding="utf-8")
    assert (
        itb_native_function_accounting.main(
            build_args + ["--output", str(destination)]
        )
        == 2
    )
    assert "different native-accounting identity" in capsys.readouterr().err


def test_cli_writer_preserves_concurrently_created_destination(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    executable, inventory, facts, registry = _write_cli_inputs(tmp_path)
    repo_root = tmp_path / "repo"
    output_root = repo_root / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    destination = output_root / "accounting.json"
    monkeypatch.setattr(itb_native_function_accounting, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(
        itb_native_function_accounting, "_OUTPUT_ROOT", output_root
    )
    original_link = itb_native_function_accounting.os.link
    foreign = b"foreign concurrent output\n"

    def race_link(source, target):
        Path(target).write_bytes(foreign)
        return original_link(source, target)

    monkeypatch.setattr(itb_native_function_accounting.os, "link", race_link)

    assert (
        itb_native_function_accounting.main(
            _cli_build_args(executable, inventory, facts, registry)
            + ["--output", str(destination)]
        )
        == 2
    )
    assert "appeared concurrently" in capsys.readouterr().err
    assert destination.read_bytes() == foreign


def test_cli_atomic_writer_rejects_linked_output_root(
    tmp_path: Path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    output_parent = repo_root / "data" / "observatory"
    output_parent.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    output_root = output_parent / "programs"
    try:
        output_root.symlink_to(external, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("test host does not permit directory symlinks")
    monkeypatch.setattr(itb_native_function_accounting, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(
        itb_native_function_accounting,
        "_OUTPUT_ROOT",
        output_root,
    )

    with pytest.raises(NativeFunctionAccountingError, match="link/reparse"):
        itb_native_function_accounting._write_evidence_atomically(
            output_root / "accounting.json",
            '{"analysis_kind":"pe_native_function_accounting"}\n',
        )
    assert not (external / "accounting.json").exists()
