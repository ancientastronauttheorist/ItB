"""Tests for exact native-function review accounting over a verified atlas."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
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
from src.observatory.program_facts import build_program_facts


@pytest.fixture(autouse=True)
def _install_synthetic_upstream_adapter(monkeypatch):
    def validate_synthetic_upstream(
        document,
        target,
        *,
        entry_rva,
        atlas_record_identity,
        support_class,
        label,
    ):
        expected_fields = {
            "entry_rva",
            "atlas_record_sha256",
            "support_class",
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


def _registry(program_facts: dict, claims: list[dict] | None = None) -> dict:
    from src.observatory.native_function_accounting import _canonical_sha256

    return {
        "schema_version": 1,
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
) -> dict:
    relative = Path("evidence") / name
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_rva = function["entry_rva"]
    record_sha256 = atlas_record_sha256(function)
    review_fields = {
        "boundary_status": "reviewed_exact",
        "ownership": "first_party",
        "subsystem": "player_action",
        "purpose": "Records a reviewed native player action boundary.",
        "inputs_outputs": "Consumes an action request and returns its result.",
        "native_lua_boundary": "registered_lua_callable",
        "reference_status": "reviewed_immediate",
        "exclusion": "none",
        "evidence_class": "fact",
    }
    support_relative = relative.with_name(f"{relative.stem}.support.json")
    support_path = tmp_path / support_relative
    upstream_relative = relative.with_name(f"{relative.stem}.upstream.json")
    upstream_path = tmp_path / upstream_relative
    support_classes = [
        "boundary",
        "immediate_references",
        "native_lua_boundary",
        "ownership",
        "semantic_io",
    ]
    upstream_records = [
        {
            "entry_rva": entry_rva,
            "atlas_record_sha256": record_sha256,
            "support_class": support_class,
            "evidence_class": "fact",
            "statement": f"Synthetic decoded {support_class} observation.",
            "observed": _support_assertion(review_fields, support_class),
        }
        for support_class in support_classes
    ]
    upstream_document = {
        "schema_version": 1,
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
            "assertion_sha256": _canonical_sha256(
                _support_assertion(review_fields, support_class)
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
        for index, support_class in enumerate(support_classes)
    ]
    support_document = {
        "schema_version": 1,
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
            "path": support_relative.as_posix(),
            "sha256": support_sha256,
            "json_pointer": f"/records/{index}",
        }
        for index, support_class in enumerate(support_classes)
    ]
    document = {
        "schema_version": 1,
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


def _l2_claim(program_facts: dict, evidence: dict, *, entry: int = 0) -> dict:
    function = program_facts["functions"][entry]
    return {
        "entry_rva": function["entry_rva"],
        "atlas_record_sha256": atlas_record_sha256(function),
        "claimed_level": "L2",
        "boundary_status": "reviewed_exact",
        "ownership": "first_party",
        "subsystem": "player_action",
        "purpose": "Records a reviewed native player action boundary.",
        "inputs_outputs": "Consumes an action request and returns its result.",
        "native_lua_boundary": "registered_lua_callable",
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
):
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
        "native_lua_boundary_counts": ("native_lua_boundary", "unknown"),
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
    assert result["review_candidates"]["affects_review_or_level"] is False
    assert result["review_candidates"]["ghidra_thunk_flagged_entry_rvas"] == [
        "0x00001020"
    ]


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
    assert review["evidence"] == [reference]
    assert validate_native_function_accounting(
        executable,
        result,
        program_facts,
        registry,
        inventory=inventory,
        repo_root=tmp_path,
    )["status"] == "verified"


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
    claim.update(claimed_level="L1", native_lua_boundary="unknown")
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
    evidence.write_text(capsys.readouterr().out, encoding="utf-8")
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
    destination.write_text(valid_rendered, encoding="utf-8")
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
