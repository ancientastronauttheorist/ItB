"""Independent fixed full4-to-cap6 class SIMD32 and external append laws."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_lua_class_simd_vector_return_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE_PATH = PROGRAMS / (
    PREFIX + "native_lua_class_simd_vector_return_conformance.json"
)
CONTROLS = {
    "ancestor": "class ancestor memory differs",
    "source": "class protected memory differs",
    "payload": "class protected memory differs",
    "vector": "class protected memory differs",
    "iterator": "class ancestor memory differs",
    "heap_request": "class heap handoff differs",
    "heap_response": "class SIMD boundary differs",
    "old": "class protected memory differs",
    "heap_free_request": "class free handoff differs",
    "xmm": "class XMM differs",
    "spare": "class protected memory differs",
}


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def read(pages, address, width=4):
    return int.from_bytes(blob(pages, address, width), "little")


def change(pages, address, value, width=4):
    result = dict(pages)
    for index, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + index) & ~4095
        payload = bytearray(result[page])
        payload[(address + index) & 4095] = byte
        result[page] = bytes(payload)
    return result


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


@pytest.fixture(scope="module")
def cases():
    return [
        (vector, fixture, c._expected(vector, fixture))
        for vector in c.vectors()
        for fixture in [c._fixture(vector)]
    ]


def test_exact_existing_tree_matrix_and_fixed_geometry():
    expected = [
        dict(
            vector,
            vector_alignment=alignment,
            old_size=4,
            old_alignment=alignment,
            xmm_profile=profile,
        )
        for vector in c.prefix.vectors()
        if vector["profile"] == "all_existing"
        for alignment in (0, 7, 31)
        for profile in (0, 1)
    ]
    assert c.vectors() == expected
    assert len(expected) == 288
    assert {len(vector["source_keys"]) for vector in expected} == set(range(8))
    assert all(
        set(vector["source_keys"]) == set(vector["destination_keys"])
        for vector in expected
    )
    assert {vector["vector_alignment"] for vector in expected} == {0, 7, 31}
    assert {vector["xmm_profile"] for vector in expected} == {0, 1}
    assert {vector["frame_alignment"] for vector in expected} == {0, 15}


def test_copy32_append_argument8_old32_preserved_and_new_filler_including_spare8(cases):
    for vector, fixture, result in cases:
        old, new = fixture["old_begin"], fixture["vector_begin"]
        assert old == 0x06003800 + vector["vector_alignment"]
        assert new == 0x06002800 + vector["vector_alignment"]
        snapshot = blob(fixture["pages"], old, 32)
        argument = read(fixture["pages"], fixture["stack"] + 4)
        record = blob(fixture["pages"], argument, 8)
        wanted = bytearray(fixture["pages"][0x06002000])
        offset = new - 0x06002000
        wanted[offset : offset + 32] = snapshot
        wanted[offset + 32 : offset + 40] = record
        assert result["pages"][0x06002000] == bytes(wanted)
        assert blob(result["pages"], new, 40) == snapshot + record
        assert blob(result["pages"], new + 40, 8) == blob(fixture["pages"], new + 40, 8)
        assert result["pages"][0x06003000] == fixture["pages"][0x06003000]
        assert blob(result["pages"], argument, 8) == record
        assert read(result["pages"], c.RECEIVER + 4) == new
        assert read(result["pages"], c.RECEIVER + 8) == new + 40
        assert read(result["pages"], c.RECEIVER + 12) == new + 48
        assert (read(result["pages"], c.RECEIVER + 8) - new) // 8 == 5
        assert (read(result["pages"], c.RECEIVER + 12) - new) // 8 == 6
        header_writes = [
            (item["address"] - c.RECEIVER, item["value"])
            for item in result["events"]
            if item["access"] == "write"
            and item["address"] in (c.RECEIVER + 4, c.RECEIVER + 8, c.RECEIVER + 12)
        ]
        assert header_writes == [(12, new + 48), (8, new + 32), (4, new), (8, new + 40)]
        append = [
            event("read", argument, int.from_bytes(record[:4], "little")),
            event("write", new + 32, int.from_bytes(record[:4], "little")),
            event("read", argument + 4, int.from_bytes(record[4:], "little")),
            event("write", new + 36, int.from_bytes(record[4:], "little")),
        ]
        assert any(
            result["events"][index : index + 4] == append
            for index in range(len(result["events"]) - 3)
        )


def test_all_eight_simd_hooks_are_ordered_exact_halves_and_xmm_df(cases):
    for vector, fixture, result in cases:
        old, new = fixture["old_begin"], fixture["vector_begin"]
        snapshot = blob(fixture["pages"], old, 32)
        wide = [item for item in result["events"] if item["width"] == 8]
        assert wide == [
            event(
                access,
                base + offset,
                int.from_bytes(snapshot[offset : offset + 8], "little"),
                8,
            )
            for access, base in (("read", old), ("write", new))
            for offset in (0, 8, 16, 24)
        ]
        assert len(wide) == 8
        assert result["xmm"] == dict(
            fixture["xmm"],
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:], "little"),
        )
        assert set(result["xmm"]) == {"xmm" + str(index) for index in range(8)}
        assert all(
            result["xmm"]["xmm" + str(index)] == fixture["xmm"]["xmm" + str(index)]
            for index in range(2, 8)
        )
        assert result["df"] == 0
        assert all(item["width"] in (1, 2, 4, 8) for item in result["events"])
        assert all(
            0 <= item["value"] < 1 << (8 * item["width"]) for item in result["events"]
        )


def test_final_abi_cookie_feature_page_seh_and_original_caller_storage(cases):
    for vector, fixture, result in cases:
        entry, frame = fixture["stack"], fixture["stack"] - 4
        incoming = fixture["registers"]
        assert result["registers"] == dict(
            incoming,
            eax=0x14000000,
            ecx=vector["cookie"],
            edx=0xB0000001,
            esp=entry + 8,
        )
        assert result["flags"] == 0x44
        assert result["endpoint"] == fixture["return_address"]
        assert read(result["pages"], frame) == incoming["ebp"]
        for offset, register in ((-28, "esi"), (-32, "edi")):
            assert read(result["pages"], frame + offset) == incoming[register]
        assert read(result["pages"], frame - 4) == vector["cookie"] ^ frame
        assert read(result["pages"], frame - 24) == 0x006EB227
        assert read(result["pages"], entry) == fixture["return_address"]
        assert read(result["pages"], 0) == vector["previous_seh"]
        assert result["pages"][0x00893000] == fixture["pages"][0x00893000]
        assert read(result["pages"], 0x00893F28) == vector["cookie"]
        assert read(result["pages"], 0x00893F30) == 0x93939393
        for page in (0x30000000, 0x30001000):
            start = max(0, entry + 8 - page)
            assert result["pages"][page][start:] == fixture["pages"][page][start:]
        preserved = [
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12, 56)
        ]
        assert len(preserved) == 14
        assert all(
            read(result["pages"], c.RECEIVER + offset)
            == read(fixture["pages"], c.RECEIVER + offset)
            for offset in preserved
        )


def test_exact_growth_resize_copy_boundary_gprs_and_installed_continuations(cases):
    for vector, fixture, result in cases:
        frame = fixture["stack"] - 4
        growth_entry = result["growth_entry"]
        argument = read(fixture["pages"], fixture["stack"] + 4)
        assert growth_entry["eax"] == fixture["old_begin"] + 32
        assert growth_entry["ecx"] == c.RECEIVER + 4 == 0x0FFFFFD0
        assert growth_entry["esi"] == c.RECEIVER
        assert growth_entry["edi"] == argument
        assert growth_entry["esp"] == frame - 40
        assert result["resize_entry"] == dict(
            growth_entry,
            eax=6,
            ebx=0x1FFFFFFD,
            ecx=0x0FFFFFD0,
            edx=6,
            esi=0x0FFFFFD0,
            edi=4,
            esp=frame - 60,
        )
        assert result["copy_entry"] == dict(
            result["resize_entry"],
            eax=fixture["vector_begin"],
            edi=fixture["vector_begin"],
            ecx=32,
            edx=fixture["old_begin"],
            ebp=frame - 64,
            esp=frame - 96,
        )
        for address, continuation in (
            (frame - 40, 0x006EB205),
            (frame - 60, 0x006EB66E),
            (frame - 88, 0x006EB695),
            (frame - 96, 0x006EB6A6),
        ):
            assert event("write", address, continuation) in result["events"]
        assert event("write", frame - 124, 48) in result["events"]
        assert event("write", frame - 136, 0x00789463) in result["events"]
        assert event("write", frame - 116, fixture["old_begin"]) in result["events"]
        assert event("write", frame - 128, 0x00789172) in result["events"]


def test_tree_identity_links_key_pointers_padding_and_all_existing_payloads(cases):
    for vector, fixture, result in cases:
        initial_addresses = fixture["destination_addresses"]
        assert result["destination_addresses"] == initial_addresses
        assert result["tree_heap_count"] == 0
        assert result["heap_nodes"] == [fixture["vector_begin"]]
        source = {
            node["key"]: fixture["source_state"]["payloads"][identity]
            for identity, node in enumerate(fixture["source_state"]["tree"]["nodes"])
        }
        destination_keys = [
            node["key"] for node in fixture["destination_state"]["tree"]["nodes"]
        ]
        assert len(result["insertions"]) == len(source)
        assert [row["key"] for row in result["insertions"]] == sorted(source)
        assert all(not row["inserted"] for row in result["insertions"])
        for address, key in zip(initial_addresses, destination_keys):
            assert blob(result["pages"], address, 20) == blob(
                fixture["pages"], address, 20
            )
            assert read(result["pages"], address + 20) == source[key]
        assert blob(result["pages"], c.prefix.leaf.HEAD, 24) == blob(
            fixture["pages"], c.prefix.leaf.HEAD, 24
        )
        assert read(result["pages"], c.RECEIVER + 56) == len(source)
        for page in (
            c.prefix.SOURCE_OBJECT,
            c.prefix.SOURCE_NODES,
            c.prefix.SOURCE_KEYS,
        ):
            if page in fixture["pages"]:
                assert result["pages"][page] == fixture["pages"][page]
        for row in result["insertions"]:
            source_address = fixture["source_addresses"][row["source"]]
            pair = [
                event("read", source_address + 20, source[row["key"]]),
                event("write", row["destination_address"] + 20, source[row["key"]]),
            ]
            assert any(
                result["events"][index : index + 2] == pair
                for index in range(len(result["events"]) - 1)
            )


def test_snapshots_outputs_and_all_fixture_objects_are_detached(cases):
    vector, fixture, result = cases[-1]
    before = copy.deepcopy((vector, fixture))
    current = c._expected(vector, fixture)
    assert current == result
    current["registers"]["ebx"] ^= 1
    current["xmm"]["xmm7"] ^= 1
    current["growth_entry"]["edx"] ^= 1
    current["events"][0]["value"] ^= 1
    current["destination_addresses"].clear()
    assert (vector, fixture) == before
    assert c._expected(vector, fixture) == result


@pytest.mark.parametrize(
    "kind",
    (
        "old32",
        "copy32",
        "record",
        "spare",
        "begin",
        "end",
        "capacity",
        "payload",
        "iterator",
        "pair",
        "inserted_byte",
        "key_pointer",
        "node_padding",
    ),
)
def test_independent_page_reconstruction_rejects_forged_protected_memory(cases, kind):
    _, fixture, result = next(case for case in reversed(cases) if case[2]["insertions"])
    frame = fixture["stack"] - 4
    node = result["insertions"][-1]["destination_address"]
    address, width = {
        "old32": (fixture["old_begin"], 1),
        "copy32": (fixture["vector_begin"] + 15, 1),
        "record": (fixture["vector_end"], 8),
        "spare": (fixture["vector_end"] + 8, 1),
        "begin": (c.RECEIVER + 4, 4),
        "end": (c.RECEIVER + 8, 4),
        "capacity": (c.RECEIVER + 12, 4),
        "payload": (node + 20, 4),
        "iterator": (frame - 8, 4),
        "pair": (frame - 20, 4),
        "inserted_byte": (frame - 16, 1),
        "key_pointer": (node + 16, 4),
        "node_padding": (node + 14, 1),
    }[kind]
    forged = copy.deepcopy(result)
    forged["pages"] = change(
        result["pages"], address, read(result["pages"], address, width) ^ 1, width
    )
    rebuilt = c._model_pages(fixture, forged)
    assert rebuilt != forged["pages"]
    assert read(rebuilt, address, width) == read(result["pages"], address, width)


@pytest.mark.parametrize(
    "field,value",
    (
        ("old_size", True),
        ("old_size", 3),
        ("old_size", 5),
        ("vector_alignment", True),
        ("vector_alignment", 1),
        ("old_alignment", False),
        ("old_alignment", 1),
        ("xmm_profile", True),
        ("xmm_profile", 2),
    ),
)
def test_malformed_vector_geometry_is_rejected(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize("kind", ("profile", "mismatched_keys", "vector_extra"))
def test_only_declared_existing_key_vector_schema_is_admitted(kind):
    vector = c.vectors()[-1]
    if kind == "profile":
        vector["profile"] = "all_new"
    elif kind == "mismatched_keys":
        vector["destination_keys"] = [0]
    else:
        vector["capacity"] = 5
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "xmm_missing",
        "xmm_extra",
        "xmm_bool",
        "xmm_negative",
        "xmm_wide",
        "old_size",
        "new_base",
        "old_base",
        "page_count",
        "new_begin",
        "new_end",
        "new_capacity",
        "gpr_bool",
        "gpr_extra",
        "page_short",
        "page_mutable",
        "installed_return",
        "installed_argument",
        "installed_source",
        "header_begin",
        "header_end",
        "header_capacity",
        "feature_word",
    ),
)
def test_strict_fixture_xmm_geometry_and_installed_slots(kind):
    vector = c.vectors()[-1]
    fixture = c._fixture(vector)
    if kind == "xmm_missing":
        fixture["xmm"].pop("xmm7")
    elif kind == "xmm_extra":
        fixture["xmm"]["xmm8"] = 0
    elif kind.startswith("xmm_"):
        fixture["xmm"]["xmm7"] = {
            "xmm_bool": False,
            "xmm_negative": -1,
            "xmm_wide": 2**128,
        }[kind]
    elif kind in ("old_size", "new_base", "old_base", "page_count"):
        field = {"page_count": "new_page_count"}.get(kind, kind)
        fixture[field] = {
            "old_size": 3,
            "new_base": 0x06001000,
            "old_base": 0x06004000,
            "page_count": 2,
        }[kind]
    elif kind in ("new_begin", "new_end", "new_capacity"):
        fixture[
            {
                "new_begin": "vector_begin",
                "new_end": "vector_end",
                "new_capacity": "vector_capacity",
            }[kind]
        ] ^= 1
    elif kind == "gpr_bool":
        fixture["registers"]["eax"] = True
    elif kind == "gpr_extra":
        fixture["registers"]["eflags"] = 0x246
    elif kind.startswith("page_"):
        page = fixture["pages"][0x06002000]
        fixture["pages"][0x06002000] = (
            page[:-1] if kind == "page_short" else bytearray(page)
        )
    else:
        address, width = {
            "installed_return": (fixture["stack"], 4),
            "installed_argument": (fixture["stack"] + 4, 4),
            "installed_source": (c.ARGUMENT + 4, 4),
            "header_begin": (c.RECEIVER + 4, 4),
            "header_end": (c.RECEIVER + 8, 4),
            "header_capacity": (c.RECEIVER + 12, 4),
            "feature_word": (0x00893F30, 4),
        }[kind]
        fixture["pages"] = change(
            fixture["pages"], address, read(fixture["pages"], address, width) ^ 1, width
        )
    with pytest.raises((c.ConformanceError, c.growth.ConformanceError)):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "registers",
        "xmm0",
        "xmm7",
        "flags",
        "flag_mask",
        "df",
        "geometry",
        "copy_entry",
        "resize_entry",
        "allocation_request",
        "free_request",
        "events",
        "coordinated_stack_events",
        "endpoint",
        "extra_metadata",
        "stack",
        "new",
        "old",
        "object",
        "error",
        "feature_page",
    ),
)
def test_every_growth_join_component_is_independently_checked(monkeypatch, kind):
    vector = c.vectors()[-1]
    fixture = c._fixture(vector)
    original, calls = c.growth._expected, []

    def changed(*arguments, **keywords):
        result = original(*arguments, **keywords)
        calls.append(True)
        if len(calls) != 1:
            return result
        if kind == "registers":
            result["registers"]["ebx"] ^= 1
        elif kind in ("xmm0", "xmm7"):
            result["xmm"][kind] ^= 1
        elif kind == "geometry":
            result["geometry"]["new_begin"] ^= 1
        elif kind in ("copy_entry", "resize_entry"):
            result[kind]["edx"] ^= 1
        elif kind == "allocation_request":
            result[kind]["bytes"] ^= 1
        elif kind == "free_request":
            result[kind]["pointer"] ^= 1
        elif kind in ("events", "coordinated_stack_events"):
            result["events"][0]["value"] ^= 1
            if kind == "coordinated_stack_events":
                stack = bytearray(result["stack"])
                stack[result["events"][0]["address"] - 0x30000000] ^= 1
                result["stack"] = bytes(stack)
        elif kind == "extra_metadata":
            result["ownership_claim"] = True
        elif kind in ("stack", "new", "old", "object", "error", "feature_page"):
            buffer = bytearray(result[kind])
            buffer[0] ^= 1
            result[kind] = bytes(buffer)
        else:
            result[kind] ^= 1
        return result

    monkeypatch.setattr(c.growth, "_expected", changed)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)
    assert calls


def _source_paths():
    return {
        key: PROGRAMS
        / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }


def _sources():
    return {key: json.loads(path.read_bytes()) for key, path in _source_paths().items()}


@pytest.fixture(scope="module")
def receipts():
    assert (
        c.SEALED_SHA256 != "PENDING"
    ), "class SIMD receipt must be sealed before delivery"
    evidence = json.loads(EVIDENCE_PATH.read_bytes())
    return evidence, _sources()


def test_actual_source_receipt_partition_and_strict_source_identity():
    paths, sources = _source_paths(), _sources()
    assert set(paths) == set(c.SOURCE_PINS)
    identities = c._preflight(sources)
    assert set(identities) == set(c.SOURCE_PINS)
    for key, (_, digest) in c.SOURCE_PINS.items():
        assert c._canonical_sha256(sources[key]) == digest
    assert c.SOURCE_PINS["simd_growth"][1] == c.growth.SEALED_SHA256
    assert c.SOURCE_PINS["old_vector_return"][1] == c.old.SEALED_SHA256
    for kind in ("missing", "extra"):
        altered = copy.deepcopy(sources)
        if kind == "missing":
            altered.pop("simd_growth")
        else:
            altered["unexpected_source"] = copy.deepcopy(sources["simd_growth"])
        with pytest.raises(c.ConformanceError):
            c._preflight(altered)


def test_sealed_encoding_structure_bounded_summary_and_simd_coverage(receipts):
    evidence, sources = receipts
    raw = EVIDENCE_PATH.read_bytes()
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    assert raw == c.encode_conformance(evidence).encode("utf-8") and b"\r\n" not in raw
    verified = c.validate_structure(evidence, sources)
    assert verified["status"] == "structurally_verified"
    assert verified["evidence_sha256"] == c.SEALED_SHA256
    assert evidence["vectors"] == c.vectors()
    assert evidence["source_receipts"] == c._preflight(sources)
    summary = evidence["summary"]
    assert summary["cases"] == len(c.vectors()) == 288
    assert (
        summary["allocation_requests"] == summary["free_requests"] == len(c.vectors())
    )
    assert summary["grown_vector_records"] == 5 * len(c.vectors())
    assert (
        summary["iterations"]
        == summary["existing_insertions"]
        == sum(len(vector["source_keys"]) for vector in c.vectors())
    )
    assert (
        summary["allocated_insertions"]
        == summary["opaque_instructions"]
        == summary["accounting_promotions"]
        == 0
    )
    assert summary["max_iterations"] == 7
    assert summary["static_sites"] == len(evidence["body"]["points"])
    assert summary["executed_sites"] == len(evidence["executed_rvas"])
    assert summary["instruction_bytes"] == sum(
        int(row["end_rva"], 16) - int(row["start_rva"], 16)
        for row in evidence["body"]["ranges"]
    )
    assert set(evidence["executed_rvas"]) <= {
        point["rva"] for point in evidence["body"]["points"]
    }
    assert {
        "0x0036e5b1",
        "0x0036ea60",
        "0x0036ea64",
        "0x0036ea69",
        "0x0036ea6d",
        "0x002eb620",
        "0x002eb680",
        "0x002eb205",
    } <= set(evidence["executed_rvas"])
    assert not any(
        0x2EB15F <= int(point, 16) < 0x2EB179 or 0x2EB1C5 <= int(point, 16) < 0x2EB1F7
        for point in evidence["executed_rvas"]
    )
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == set(CONTROLS) | {"cookie"}
    assert all(row["rejected"] for row in controls.values())
    assert controls["cookie"]["endpoint"] == "0x003574d5"
    assert "factory callback composition" in " ".join(evidence["scope"]["not_claimed"])


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "vector",
        "observation",
        "control",
        "coverage",
        "point",
        "range",
        "pin",
        "scope",
    ),
)
def test_any_sealed_receipt_tampering_is_rejected(receipts, kind):
    original, sources = receipts
    evidence = copy.deepcopy(original)
    if kind == "summary":
        evidence["summary"]["grown_vector_records"] += 1
    elif kind == "vector":
        evidence["vectors"][0]["old_size"] = 3
    elif kind == "observation":
        evidence["observations_sha256"] = "0" * 64
    elif kind == "control":
        evidence["negative_controls"][0]["rejected"] = False
    elif kind == "coverage":
        evidence["executed_rvas"].pop()
    elif kind == "point":
        evidence["body"]["points"][0]["size"] += 1
    elif kind == "range":
        evidence["body"]["ranges"][0]["end_rva"] = "0xffffffff"
    elif kind == "pin":
        evidence["source_receipts"] = {}
    else:
        evidence["scope"]["claim"] += " actual allocation ownership"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize(
    "key",
    (
        "program_facts",
        "old_vector_return",
        "simd_growth",
        "short_simd_conformance",
        "simd_resize",
    ),
)
def test_tampered_ancestor_receipt_is_rejected(receipts, key):
    evidence, original = receipts
    sources = copy.deepcopy(original)
    sources[key]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


def _native_code():
    executable = os.environ["ITB_EXACT_EXE"]
    data, image, digest = c._load_executable(Path(executable))
    assert digest == c.EXE_SHA256
    sources = _sources()
    c._preflight(sources)
    codes, points, _ = c._load_code(data, image, sources)
    return codes, points


def _native_case(index):
    vector = c.vectors()[index]
    fixture = c._fixture(vector)
    before = copy.deepcopy(fixture)
    expected = c._expected(vector, fixture)
    codes, points = _native_code()
    result = c._run_case(codes, points, vector, fixture=fixture)
    assert fixture == before
    assert result["registers"] == expected["registers"]
    assert result["xmm"] == expected["xmm"] and result["df"] == 0
    assert result["flags"] == expected["flags"]
    assert result["events_sha256"] == c._canonical_sha256(expected["events"])
    assert result["memory_sha256"] == c._canonical_sha256(
        {
            str(page): hashlib.sha256(payload).hexdigest()
            for page, payload in expected["pages"].items()
        }
    )
    frame = fixture["stack"] - 4
    assert result["allocations"] == [
        dict(
            node=fixture["vector_begin"],
            entry_esp=frame - 136,
            request=48,
            continuation=0x00789463,
        )
    ]
    assert result["frees"] == [
        dict(
            pointer=fixture["old_begin"],
            entry_esp=frame - 128,
            result=1,
            continuation=0x00789172,
        )
    ]
    assert all(not row["inserted"] for row in result["insertions"])
    assert set(result["trace_rvas"]) <= {point["rva"] for point in points}
    assert {"0x0036ea60", "0x0036ea64", "0x0036ea69", "0x0036ea6d"} <= set(
        result["trace_rvas"]
    )


def _native_control(kind):
    vector = c.vectors()[-1]
    if kind == "cookie":
        assert c._run_case(*_native_code(), vector, kind) == dict(
            kind="cookie", rejected=True, endpoint="0x003574d5"
        )
    else:
        with pytest.raises(c.ConformanceError, match="^" + CONTROLS[kind] + "$"):
            c._run_case(*_native_code(), vector, kind)


def _isolated(action, *arguments):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and the reviewed private native runtime")
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        timeout=600,
        env=environment,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == result.stderr == b""


@pytest.mark.parametrize("index", (0, 1, 4, 5, 282, 283, 286, 287))
def test_isolated_native_corpus_boundaries(index):
    _isolated("corpus", index)


@pytest.mark.parametrize("kind", tuple(CONTROLS) + ("cookie",))
def test_isolated_native_controls_fail_for_their_intended_reasons(kind):
    _isolated("negative", kind)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_and_structure_match_the_receipt(receipts, command):
    _, _ = receipts
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and the reviewed private native runtime")
    arguments = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_simd_vector_return_conformance.py"),
        command,
    ]
    for key, path in _source_paths().items():
        arguments += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        arguments += ["--executable", str(Path(executable))]
    if command != "build":
        arguments += ["--evidence", str(EVIDENCE_PATH)]
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        timeout=600,
        env=environment,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    if command == "build":
        assert result.stdout == EVIDENCE_PATH.read_bytes()
    else:
        verified = json.loads(result.stdout)
        assert verified["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert verified["evidence_sha256"] == c.SEALED_SHA256
        assert result.stdout == c.encode_conformance(verified).encode("utf-8")


if __name__ == "__main__":
    import faulthandler

    faulthandler.disable()
    action, *arguments = sys.argv[1:]
    if action == "corpus":
        _native_case(int(arguments[0]))
    elif action == "negative":
        _native_control(arguments[0])
    else:
        raise ValueError("unknown isolated native action")


@pytest.mark.parametrize(
    "kind",
    (
        "vector_missing",
        "vector_tuple",
        "key_tuple",
        "bool_key",
        "duplicate_key",
        "fixture_extra",
        "fixture_missing",
    ),
)
def test_closed_vector_and_fixture_schema_and_canonical_key_recipes(kind):
    vector = c.vectors()[-1]
    if kind.startswith("fixture_"):
        fixture = c._fixture(vector)
        if kind == "fixture_extra":
            fixture["ownership_claim"] = True
        else:
            fixture.pop("transfer")
        with pytest.raises(c.ConformanceError):
            c._expected(vector, fixture)
        return
    if kind == "vector_missing":
        vector.pop("old_alignment")
    elif kind == "vector_tuple":
        vector = tuple(vector.items())
    elif kind == "key_tuple":
        vector["source_keys"] = tuple(vector["source_keys"])
    elif kind == "bool_key":
        vector["source_keys"][vector["source_keys"].index(1)] = True
    else:
        vector["source_keys"][0] = vector["source_keys"][1]
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind", ("extra", "missing", "old_alignment", "bool_alignment")
)
def test_expected_entry_independently_revalidates_vector_schema_and_geometry(kind):
    vector = c.vectors()[-1]
    fixture = c._fixture(vector)
    if kind == "extra":
        vector["requested_capacity"] = 7
    elif kind == "missing":
        vector.pop("old_alignment")
    elif kind == "old_alignment":
        vector["old_alignment"] = 0
    else:
        vector["old_alignment"] = True
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize("first_word", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_supplied_actual_callback_caller_zero_or_dword_record_and_return_binding(
    first_word,
):
    vector = c.vectors()[-1]
    seed = c._fixture(vector)
    entry = seed["stack"]
    registers = dict(
        seed["registers"],
        eax=0xFFFFFFFF,
        ebx=0x80000000,
        edx=0,
        esi=0xAAAAAAAA,
        edi=0x55555555,
        ebp=0x87654321,
    )
    fixture = c._fixture(
        vector,
        caller=dict(
            argument_address=entry + 28,
            argument_record=[first_word, 0x14000000],
            return_address=0x006EC1BD,
            registers=registers,
        ),
    )
    before = copy.deepcopy(fixture)
    result = c._expected(vector, fixture)
    new = fixture["vector_begin"]
    assert blob(result["pages"], new + 32, 8) == first_word.to_bytes(4, "little") + (
        0x14000000
    ).to_bytes(4, "little")
    assert blob(result["pages"], entry + 28, 8) == blob(fixture["pages"], entry + 28, 8)
    assert result["endpoint"] == 0x006EC1BD
    assert result["registers"] == dict(
        registers, eax=0x14000000, ecx=vector["cookie"], edx=0xB0000001, esp=entry + 8
    )
    assert fixture == before
