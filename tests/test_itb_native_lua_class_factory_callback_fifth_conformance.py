"""Independent actual-fourth capture, fifth SIMD transport and retained-page laws."""

import copy
import faulthandler
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
from src.observatory import native_lua_class_factory_callback_fifth_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE_PATH = PROGRAMS / (
    PREFIX + "native_lua_class_factory_callback_fifth_conformance.json"
)
XMM = tuple("xmm" + str(index) for index in range(8))
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")


def blob(pages, address, size):
    return bytes(
        pages[(address + offset) & ~4095][(address + offset) & 4095]
        for offset in range(size)
    )


def word(pages, address, width=4):
    return int.from_bytes(blob(pages, address, width), "little")


def change(pages, address, value, width=1):
    result = dict(pages)
    for index, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + index) & ~4095
        data = bytearray(result[page])
        data[(address + index) & 4095] = byte
        result[page] = bytes(data)
    return result


def source_values(state):
    return {
        node["key"]: state["payloads"][identity]
        for identity, node in enumerate(state["tree"]["nodes"])
    }


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


def _native_inputs(index):
    vector = c.vectors()[index]
    data, image, digest = c.full._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.factory.EXE_SHA256
    sources = _sources()
    c._preflight(sources)
    payload, fp, continuation, codes, points = c._load_code(data, image, sources)
    chain = c._produce_fourth(payload, fp, continuation, codes, points, vector)
    produced, _, _, _, _, _, _, _, previous, captured = chain
    return codes, points, vector, produced, previous, captured, chain


def _boundary(registers, endpoint):
    return dict(
        registers=dict(registers),
        xmm=dict.fromkeys(XMM, 0),
        flags=0x246,
        endpoint=endpoint,
    )


@pytest.mark.parametrize("label", ("entry", "return"))
def test_boundary_accepts_actual_schema_and_zero_machine_state(label):
    registers = {name: index * 0x1234567 for index, name in enumerate(GPR)}
    endpoint = 0x006EC110 if label == "entry" else 0x0400A000
    boundary = _boundary(registers, endpoint)
    before = copy.deepcopy(boundary)
    assert c._checked_boundary([boundary], registers, endpoint, label) == boundary
    assert boundary == before


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize("register", GPR)
def test_each_actual_boundary_gpr_is_independently_checked(label, register):
    registers = dict.fromkeys(GPR, 0)
    boundary = _boundary(registers, 0x0400A000)
    boundary["registers"][register] ^= 1
    with pytest.raises(
        c.ConformanceError, match="fourth producer " + label + " boundary differs"
    ):
        c._checked_boundary([boundary], registers, 0x0400A000, label)


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize("register", XMM)
@pytest.mark.parametrize("value", (1, 2**127, False, -1, 2**128))
def test_each_actual_boundary_xmm_requires_typed_zero(label, register, value):
    registers = dict.fromkeys(GPR, 0)
    boundary = _boundary(registers, 0x0400A000)
    boundary["xmm"][register] = value
    with pytest.raises(
        c.ConformanceError, match="fourth producer " + label + " boundary differs"
    ):
        c._checked_boundary([boundary], registers, 0x0400A000, label)


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize(
    "kind",
    (
        "no_capture",
        "duplicate",
        "tuple",
        "extra",
        "missing",
        "gpr_extra",
        "gpr_missing",
        "gpr_bool",
        "gpr_wide",
        "xmm_extra",
        "xmm_missing",
        "xmm_tuple",
        "flags_bool",
        "flags_df",
        "flags_wrong",
        "pc_wrong",
        "pc_bool",
    ),
)
def test_boundary_count_pc_flags_and_closed_schemas(label, kind):
    registers = dict.fromkeys(GPR, 0)
    endpoint = 0x0400A000
    boundary = _boundary(registers, endpoint)
    rows = [boundary]
    if kind == "no_capture":
        rows = []
    elif kind == "duplicate":
        rows.append(copy.deepcopy(boundary))
    elif kind == "tuple":
        rows = tuple(rows)
    elif kind == "extra":
        boundary["ownership"] = True
    elif kind == "missing":
        boundary.pop("flags")
    elif kind == "gpr_extra":
        boundary["registers"]["eip"] = endpoint
    elif kind == "gpr_missing":
        boundary["registers"].pop("eax")
    elif kind == "gpr_bool":
        boundary["registers"]["eax"] = False
    elif kind == "gpr_wide":
        boundary["registers"]["eax"] = 2**32
    elif kind == "xmm_extra":
        boundary["xmm"]["xmm8"] = 0
    elif kind == "xmm_missing":
        boundary["xmm"].pop("xmm7")
    elif kind == "xmm_tuple":
        boundary["xmm"] = tuple(boundary["xmm"].items())
    elif kind.startswith("flags_"):
        boundary["flags"] = {
            "flags_bool": True,
            "flags_df": 0x646,
            "flags_wrong": 0x247,
        }[kind]
    else:
        boundary["endpoint"] = endpoint ^ 1 if kind == "pc_wrong" else True
    with pytest.raises(
        c.ConformanceError, match="fourth producer " + label + " boundary differs"
    ):
        c._checked_boundary(rows, registers, endpoint, label)


def _simd_fixture():
    xmm = {
        name: (index + 1) * 0x123456789ABCDEF0123456789
        for index, name in enumerate(XMM)
    }
    return dict(
        simd_state=dict(xmm=xmm, df=0),
        prototype=dict(
            old_begin=0x06003807,
            old_size=4,
            vector_begin=0x06002807,
            vector_end=0x06002827,
            vector_capacity=0x06002837,
            old_base=0x06003000,
            new_base=0x06002000,
            new_page_count=1,
            xmm=copy.deepcopy(xmm),
        ),
    )


def test_optional_simd_transport_returns_detached_exact_two_key_state():
    fixture = _simd_fixture()
    before = copy.deepcopy(fixture)
    state = c.callback._simd_state(fixture, c.adapter)
    assert set(state) == {"xmm", "df"} and set(state["xmm"]) == set(XMM)
    assert state == fixture["simd_state"] and state["df"] == 0
    state["xmm"]["xmm7"] ^= 1
    assert fixture == before
    assert c.callback._simd_state({}, c.old) is None


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "default_mode",
        "state_extra",
        "state_tuple",
        "df_bool",
        "df_set",
        "df_negative",
        "xmm_extra",
        "xmm_missing",
        "xmm_bool",
        "xmm_negative",
        "xmm_wide",
        "xmm_tuple",
        "prototype_bool",
        "prototype_xmm_bool",
        "prototype_xmm_mismatch",
        "old_size",
        "old_begin",
        "new_begin",
        "new_end",
        "new_capacity",
        "old_base",
        "new_base",
        "new_pages",
    ),
)
def test_optional_simd_state_rejects_undeclared_modes_types_and_geometry(kind):
    fixture = _simd_fixture()
    module = c.adapter
    if kind == "missing":
        fixture.pop("simd_state")
    elif kind == "default_mode":
        module = c.old
    elif kind == "state_extra":
        fixture["simd_state"]["ownership"] = True
    elif kind == "state_tuple":
        fixture["simd_state"] = tuple(fixture["simd_state"].items())
    elif kind.startswith("df_"):
        fixture["simd_state"]["df"] = {
            "df_bool": False,
            "df_set": 1,
            "df_negative": -1,
        }[kind]
    elif kind == "xmm_extra":
        fixture["simd_state"]["xmm"]["xmm8"] = 0
    elif kind == "xmm_missing":
        fixture["simd_state"]["xmm"].pop("xmm7")
    elif kind == "xmm_tuple":
        fixture["simd_state"]["xmm"] = tuple(fixture["simd_state"]["xmm"].items())
    elif kind.startswith("xmm_"):
        fixture["simd_state"]["xmm"]["xmm7"] = {
            "xmm_bool": False,
            "xmm_negative": -1,
            "xmm_wide": 2**128,
        }[kind]
    elif kind == "prototype_bool":
        fixture["prototype"]["old_size"] = True
    elif kind == "prototype_xmm_bool":
        fixture["prototype"]["xmm"]["xmm7"] = False
    elif kind == "prototype_xmm_mismatch":
        fixture["prototype"]["xmm"]["xmm7"] ^= 1
    else:
        field = {
            "new_begin": "vector_begin",
            "new_end": "vector_end",
            "new_capacity": "vector_capacity",
            "new_pages": "new_page_count",
        }.get(kind, kind)
        fixture["prototype"][field] ^= 1
    before = copy.deepcopy(fixture)
    with pytest.raises(c.callback.ConformanceError):
        c.callback._simd_state(fixture, module)
    assert fixture == before


@pytest.mark.parametrize("value", (0, 1, 2**127, 2**128 - 1))
def test_simd_transport_accepts_full_uint128_range_with_clear_df(value):
    fixture = _simd_fixture()
    fixture["simd_state"]["xmm"]["xmm7"] = value
    fixture["prototype"]["xmm"]["xmm7"] = value
    assert c.callback._simd_state(fixture, c.adapter)["xmm"]["xmm7"] == value


def test_adapter_has_exact_schema_and_never_constructs_a_fixture():
    assert len(c.adapter.VECTOR_KEYS) == 18
    assert len(c.simd_class.FIXTURE_KEYS) == 29
    assert c.adapter.SOURCE_KEYS == {0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF}
    with pytest.raises(c.adapter.ConformanceError, match="actual retained capture"):
        c.adapter._fixture({})


def test_declared_fifth_matrix_and_source_pins_are_finite():
    assert c.vectors() == c.fourth.vectors()
    assert len(c.vectors()) == 216
    assert len(c.SOURCE_PINS) == 45
    assert {vector["first_key_profile"] for vector in c.vectors()} == {0, 1}
    assert {vector["vector_alignment"] for vector in c.vectors()} == {0, 7, 31}
    assert {vector["profile"] for vector in c.vectors()} == {0, 1}
    assert all(vector["source_profile"] == 3 for vector in c.vectors())
    sources = _sources()
    assert set(_source_paths()) == set(c.SOURCE_PINS)
    identities = c._preflight(sources)
    assert set(identities) == set(c.SOURCE_PINS)
    for key, (_, digest) in c.SOURCE_PINS.items():
        assert c._canonical_sha256(sources[key]) == digest
    assert c.SOURCE_PINS["factory_callback_fourth"][1] == c.fourth.SEALED_SHA256
    assert c.SOURCE_PINS["class_simd"][1] == c.simd_class.SEALED_SHA256


def _check_packet(codes, points, vector, produced, previous, captured, chain):
    baseline = copy.deepcopy((produced, previous, captured))
    prior, addresses = c._check_fourth(produced, previous, captured)
    assert len(captured["entry"]) == len(captured["returned"]) == 1
    assert (
        captured["entry"][0]["xmm"]
        == captured["returned"][0]["xmm"]
        == dict.fromkeys(XMM, 0)
    )
    assert captured["entry"][0]["flags"] == captured["returned"][0]["flags"] == 0x246
    assert captured["entry"][0]["registers"] == previous["registers"]
    assert (
        captured["returned"][0]["registers"]
        == captured["observation"]["registers"]
        == prior["full_return"]["registers"]
    )
    assert set(captured["observation"]).isdisjoint({"xmm", "df"})
    assert captured["pages"][0x06002000] == previous["pages"][0x06002000]
    assert captured["pages"][0x00893000] == previous["pages"][0x00893000]
    fixture = c._resume(produced, previous, captured, vector)
    assert (produced, previous, captured) == baseline
    c._check_host_patches(captured, fixture)
    allowed = {fixture["entry"] + offset for offset in range(8)} | {
        address + 20 + offset
        for address in previous["prototype"]["source_addresses"]
        for offset in range(4)
    }
    assert len(fixture["patches"]) == len(allowed) == 36
    assert {patch["address"] for patch in fixture["patches"]} == allowed
    changed = {
        page + offset
        for page, data in fixture["pages"].items()
        for offset, byte in enumerate(data)
        if byte != captured["pages"][page][offset]
    }
    assert changed <= allowed
    expected_source = copy.deepcopy(previous["prototype"]["source_state"])
    expected_source["payloads"] = [
        value ^ (0xFFFFFFFF if vector["profile"] else 0)
        for value in expected_source["payloads"]
    ]
    assert fixture["prototype"]["source_state"] == expected_source
    assert (
        fixture["prototype"]["source_state"]["tree"]
        == previous["prototype"]["source_state"]["tree"]
    )
    assert (
        fixture["prototype"]["destination_state"]
        == prior["class_transfer"]["destination"]
    )
    assert fixture["prototype"]["destination_addresses"] == addresses
    assert fixture["pages"][0x06002000] == captured["pages"][0x06002000]
    assert fixture["pages"][0x00893000] == captured["pages"][0x00893000]
    logical = c._logical(fixture)
    expected = c.callback._expected(
        fixture["callback_vector"], fixture, class_module=c.adapter
    )
    child = next(row for row in expected["children"] if row["kind"] == "class")
    assert set(child["fixture"]) == c.simd_class.FIXTURE_KEYS
    assert child["result"]["tree_heap_count"] == 0
    assert len(child["result"]["insertions"]) == 7
    assert child["result"]["destination_addresses"] == addresses
    assert all(
        not row["inserted"] and row["heap_node"] is None
        for row in child["result"]["insertions"]
    )
    assert child["result"]["registers"] == logical["class_return"]["registers"]
    assert child["result"]["endpoint"] == 0x006EC1BD
    final = expected["pages"]
    new, old, source = (
        fixture["vector_begin"],
        fixture["fourth_vector_pointer"],
        fixture["source_pointer"],
    )
    assert new == 0x06002800 + vector["vector_alignment"]
    snapshot = blob(captured["pages"], old, 32)
    pair = bytes(4) + source.to_bytes(4, "little")
    assert snapshot == pair * 4
    assert blob(final, new, 40) == pair * 5
    assert word(final, fixture["receiver"] + 4) == new
    assert word(final, fixture["receiver"] + 8) == new + 40
    assert word(final, fixture["receiver"] + 12) == new + 48
    wanted_page = bytearray(captured["pages"][0x06002000])
    offset = new - 0x06002000
    wanted_page[offset : offset + 40] = pair * 5
    assert final[0x06002000] == bytes(wanted_page)
    assert blob(final, new + 40, 8) == blob(captured["pages"], new + 40, 8)
    for pointer, size in (
        (old, 32),
        (fixture["third_vector_pointer"], 24),
        (fixture["second_vector_pointer"], 16),
        (fixture["first_arguments"]["vector_pointer"], 8),
    ):
        assert blob(final, pointer, size) == blob(captured["pages"], pointer, size)
    sentinel = produced["fixture"]["record"]
    assert blob(final, sentinel, 24) == blob(captured["pages"], sentinel, 24)
    assert word(final, fixture["receiver"] + 56) == 8
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert len(preserved) == 13
    assert all(
        word(final, fixture["receiver"] + offset)
        == word(captured["pages"], fixture["receiver"] + offset)
        for offset in preserved
    )
    source_values_final = source_values(expected_source)
    retained_values = source_values(prior["class_transfer"]["destination"])
    assert source_values_final.keys() == c.adapter.SOURCE_KEYS
    final_tree = logical["class_transfer"]["destination"]
    assert source_values(final_tree) == retained_values | source_values_final
    assert source_values(final_tree)[16] == retained_values[16]
    destination_keys = [node["key"] for node in final_tree["tree"]["nodes"]]
    for address, key in zip(addresses, destination_keys):
        assert blob(final, address, 20) == blob(captured["pages"], address, 20)
        assert word(final, address + 20) == source_values_final.get(
            key, retained_values[key]
        )
    for pointer, data in fixture["prototype"]["strings"].items():
        assert blob(final, pointer, len(data)) == data
    assert final[0x00893000] == captured["pages"][0x00893000]
    xmm = dict.fromkeys(XMM, 0)
    xmm.update(
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:], "little"),
    )
    assert expected["xmm"] == child["result"]["xmm"] == xmm
    assert expected["df"] == child["result"]["df"] == 0
    wide = [row for row in expected["events"] if row["width"] == 8]
    assert wide == [
        dict(
            access=access,
            address=base + offset,
            width=8,
            value=int.from_bytes(snapshot[offset : offset + 8], "little"),
        )
        for access, base in (("read", old), ("write", new))
        for offset in (0, 8, 16, 24)
    ]
    final_capture = {}

    def capture(machine, ids, oracle, lua):
        final_capture["pages"] = {
            page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]
        }

    result = c._run_case(codes, points, fixture, produced, vector, capture=capture)
    assert final_capture["pages"] == final
    assert result["registers"] == logical["full_return"]["registers"]
    assert result["xmm"] == xmm and result["df"] == 0
    assert result["memory_sha256"] == c.repeat._page_sha(final)
    assert result["events_sha256"] == c._canonical_sha256(expected["events"])
    assert result["payload_updates"] == 7
    assert result["allocations"] == [
        dict(
            node=new,
            entry_esp=fixture["entry"] - 188,
            request=48,
            continuation=0x00789463,
        )
    ]
    assert result["frees"] == [
        dict(
            pointer=old,
            entry_esp=fixture["entry"] - 180,
            result=1,
            continuation=0x00789172,
        )
    ]
    assert result["captured_pages_sha256"] == c.repeat._page_sha(captured["pages"])
    assert result["captured_simd_sha256"] == c._canonical_sha256(
        dict(entry=captured["entry"], returned=captured["returned"])
    )
    assert {
        "0x0036e5b1",
        "0x0036ea60",
        "0x0036ea64",
        "0x0036ea69",
        "0x0036ea6d",
    } <= set(result["trace_rvas"])
    original = copy.deepcopy((previous, captured))
    fixture["prototype"]["source_state"]["payloads"][0] ^= 1
    fixture["prototype"]["destination_state"]["tree"]["nodes"][0]["key"] ^= 1
    fixture["prototype"]["destination_addresses"].clear()
    fixture["callback_vector"]["source_refs"][0] ^= 1
    fixture["callback_vector"]["transfers"][0].append("other")
    fixture["prototype"]["strings"].clear()
    fixture["simd_state"]["xmm"]["xmm7"] ^= 1
    assert (previous, captured) == original


def _check_capture_controls(vector, produced, previous, captured):
    before = copy.deepcopy((produced, previous, captured))
    for kind in (
        "stale_pages",
        "stale_registers",
        "extra_capture",
        "missing_capture",
        "extra_page",
        "short_page",
        "mutable_page",
    ):
        altered = copy.deepcopy(captured)
        if kind == "stale_pages":
            address = previous["vector_begin"]
            altered["pages"] = change(
                altered["pages"], address, word(altered["pages"], address, 1) ^ 1
            )
        elif kind == "stale_registers":
            altered["registers"]["eax"] ^= 1
        elif kind == "extra_capture":
            altered["ownership"] = True
        elif kind == "missing_capture":
            altered.pop("returned")
        elif kind == "extra_page":
            altered["pages"][0xDEAD0000] = bytes(4096)
        elif kind == "short_page":
            altered["pages"][0x06002000] = altered["pages"][0x06002000][:-1]
        else:
            altered["pages"][0x06002000] = bytearray(altered["pages"][0x06002000])
        with pytest.raises(
            c.ConformanceError, match="^verified fourth callback capture differs$"
        ):
            c._check_fourth(produced, previous, altered)
    for label, key in (("entry", "entry"), ("return", "returned")):
        for kind in ("count", "pc", "flags", "df", "gpr", "xmm", "xmm_bool"):
            altered = copy.deepcopy(captured)
            rows = altered[key]
            if kind == "count":
                rows.append(copy.deepcopy(rows[0]))
            elif kind == "pc":
                rows[0]["endpoint"] ^= 1
            elif kind in ("flags", "df"):
                rows[0]["flags"] ^= 1 if kind == "flags" else 0x400
            elif kind == "gpr":
                rows[0]["registers"]["eax"] ^= 1
            elif kind == "xmm":
                rows[0]["xmm"]["xmm7"] = 1
            else:
                rows[0]["xmm"]["xmm7"] = False
            with pytest.raises(
                c.ConformanceError,
                match="^fourth producer " + label + " boundary differs$",
            ):
                c._check_fourth(produced, previous, altered)
    for domain in ("capture", "observation"):
        altered = copy.deepcopy(captured)
        target = (
            altered["registers"]
            if domain == "capture"
            else altered["observation"]["registers"]
        )
        target["eax"] = False
        with pytest.raises(c.ConformanceError):
            c._check_fourth(produced, previous, altered)
    locations = []
    locations += [
        ("u" + str(offset), previous["receiver"] + offset) for offset in range(0, 72, 4)
    ]
    locations += [
        ("p" + str(offset), produced["fixture"]["record"] + offset)
        for offset in range(24)
    ]
    for identity, address in enumerate(previous["prototype"]["destination_addresses"]):
        locations += [
            ("destination" + str(identity) + "_" + str(offset), address + offset)
            for offset in (0, 4, 8, 12, 13, 14, 15, 16, 20)
        ]
    for identity, address in enumerate(previous["prototype"]["source_addresses"]):
        locations += [
            ("source" + str(identity) + "_" + str(offset), address + offset)
            for offset in (0, 4, 8, 12, 13, 14, 15, 16, 20)
        ]
    locations += [
        ("source_object" + str(offset), previous["source_pointer"] + offset)
        for offset in range(0, 72, 4)
    ]
    locations += [
        ("source_head" + str(offset), c.old.prefix.SOURCE_HEAD + offset)
        for offset in range(24)
    ]
    for pointer, data in previous["prototype"]["strings"].items():
        locations += [
            ("key" + str(pointer) + "_" + str(offset), pointer + offset)
            for offset in (0, len(data) - 1)
        ]
    for name, pointer, size in (
        ("fourth", previous["vector_begin"], 32),
        ("third", previous["third_vector_pointer"], 24),
        ("second", previous["second_vector_pointer"], 16),
        ("first", previous["first_arguments"]["vector_pointer"], 8),
    ):
        locations += [(name + str(offset), pointer + offset) for offset in range(size)]
    locations += [
        ("fs", 0),
        ("cookie", 0x00893F28),
        ("feature_word", 0x00893F30),
        ("feature_other", 0x00893037),
        ("page2_first", previous["first_arguments"]["vector_pointer"]),
        ("page2_filler", 0x06002700),
        ("future_spare", 0x06002800 + vector["vector_alignment"] + 40),
        ("stack_scratch", previous["entry"] - 100),
    ]
    for name, address in locations:
        altered = copy.deepcopy(captured)
        altered["pages"] = change(
            altered["pages"], address, word(altered["pages"], address, 1) ^ 1
        )
        altered["observation"]["memory_sha256"] = c.repeat._page_sha(altered["pages"])
        with pytest.raises(
            c.ConformanceError, match="^retained fourth callback differs$"
        ):
            c._check_fourth(produced, previous, altered)
    for field in ("allocations", "frees"):
        altered = copy.deepcopy(captured)
        altered["observation"][field][0]["entry_esp"] ^= 1
        with pytest.raises(
            c.ConformanceError, match="^retained fourth callback differs$"
        ):
            c._check_fourth(produced, previous, altered)
    altered = copy.deepcopy(captured)
    altered["observation"]["frees"][0]["result"] = True
    with pytest.raises(c.ConformanceError):
        c._check_fourth(produced, previous, altered)
    assert (produced, previous, captured) == before


def _check_host_controls(vector, produced, previous, captured):
    fixture = c._resume(produced, previous, captured, vector)
    before = copy.deepcopy((fixture, captured))
    for kind in (
        "extra",
        "missing",
        "duplicate",
        "outside",
        "before",
        "after",
        "coordinated_after",
        "address_bool",
        "byte_bool",
        "byte_wide",
        "schema_extra",
        "tuple",
        "pages_other",
        "pages_missing",
        "pages_extra",
    ):
        altered = copy.deepcopy(fixture)
        if kind == "extra":
            altered["patches"].append(copy.deepcopy(altered["patches"][0]))
        elif kind == "missing":
            altered["patches"].pop()
        elif kind == "duplicate":
            altered["patches"][-1] = copy.deepcopy(altered["patches"][0])
        elif kind == "outside":
            altered["patches"][0]["address"] = 0x06002700
        elif kind in ("before", "after"):
            altered["patches"][0][kind] ^= 1
        elif kind == "coordinated_after":
            patch = altered["patches"][0]
            patch["after"] ^= 1
            altered["pages"] = change(
                altered["pages"], patch["address"], patch["after"]
            )
        elif kind == "address_bool":
            altered["patches"][0]["address"] = True
        elif kind == "byte_bool":
            altered["patches"][0]["before"] = False
        elif kind == "byte_wide":
            altered["patches"][0]["after"] = 256
        elif kind == "schema_extra":
            altered["patches"][0]["width"] = 1
        elif kind == "tuple":
            altered["patches"] = tuple(altered["patches"])
        elif kind == "pages_other":
            altered["pages"] = change(
                altered["pages"], 0x06002700, word(altered["pages"], 0x06002700, 1) ^ 1
            )
        elif kind == "pages_missing":
            altered["pages"].pop(0x06002000)
        else:
            altered["pages"][0xDEAD0000] = bytes(4096)
        with pytest.raises(
            c.ConformanceError, match="^fifth host patch partition differs$"
        ):
            c._check_host_patches(captured, altered)
    assert (fixture, captured) == before


def _check_adapter_controls(vector, produced, previous, captured):
    fixture = c._resume(produced, previous, captured, vector)
    expected = c.callback._expected(
        fixture["callback_vector"], fixture, class_module=c.adapter
    )
    child = next(row for row in expected["children"] if row["kind"] == "class")
    cv = fixture["callback_vector"]
    for kind in (
        "vector_extra",
        "vector_missing",
        "fixture_extra",
        "fixture_missing",
        "old_size",
        "old_alignment",
        "nil_bool",
        "nil_wrong",
        "frame",
        "profile",
        "source_key",
        "destination_key",
        "marker_bool",
        "source_ref_bool",
        "source_word_bool",
        "destination_word",
        "transfer_bad",
        "transfer_bound",
    ):
        vector_copy, child_fixture = copy.deepcopy(cv), copy.deepcopy(child["fixture"])
        if kind == "vector_extra":
            vector_copy["ownership"] = True
        elif kind == "vector_missing":
            vector_copy.pop("old_alignment")
        elif kind == "fixture_extra":
            child_fixture["ownership"] = True
        elif kind == "fixture_missing":
            child_fixture.pop("xmm")
        elif kind == "old_size":
            vector_copy["old_size"] = 3
        elif kind == "old_alignment":
            vector_copy["old_alignment"] = (vector_copy["old_alignment"] + 1) % 32
        elif kind == "nil_bool":
            vector_copy["nil_flag"] = True
        elif kind == "nil_wrong":
            vector_copy["nil_flag"] = 255
        elif kind == "frame":
            vector_copy["frame_alignment"] = 7
        elif kind == "profile":
            vector_copy["profile"] = "all_new"
        elif kind == "source_key":
            vector_copy["source_keys"][0] ^= 1
        elif kind == "destination_key":
            vector_copy["destination_keys"][0] ^= 1
        elif kind == "marker_bool":
            vector_copy["marker_words"][0] = False
        elif kind == "source_ref_bool":
            vector_copy["source_refs"][0] = False
        elif kind == "source_word_bool":
            vector_copy["source_word"] = False
        elif kind == "destination_word":
            vector_copy["destination_word"] ^= 1
        elif kind == "transfer_bad":
            vector_copy["transfers"][0] = ["invalid"]
        else:
            vector_copy["transfers"][0] = ["other"] * 4
        with pytest.raises(c.adapter.ConformanceError):
            c.adapter._expected(vector_copy, child_fixture)
    originals = (c.adapter._fixture, c.simd_class._fixture)

    def forbidden(*arguments, **keywords):
        raise AssertionError(
            "retained factory path constructed a replacement class fixture"
        )

    c.adapter._fixture = c.simd_class._fixture = forbidden
    try:
        assert c.callback._expected(cv, fixture, class_module=c.adapter) == expected
    finally:
        c.adapter._fixture, c.simd_class._fixture = originals
    original_expected = c.adapter._expected
    try:
        for kind in XMM + (
            "xmm_missing",
            "xmm_extra",
            "xmm_bool",
            "xmm_negative",
            "xmm_wide",
            "df_missing",
            "df_bool",
            "df_set",
        ):
            result = copy.deepcopy(child["result"])
            if kind in XMM:
                result["xmm"][kind] ^= 1
            elif kind == "xmm_missing":
                result["xmm"].pop("xmm7")
            elif kind == "xmm_extra":
                result["xmm"]["xmm8"] = 0
            elif kind in ("xmm_bool", "xmm_negative", "xmm_wide"):
                result["xmm"]["xmm7"] = {
                    "xmm_bool": False,
                    "xmm_negative": -1,
                    "xmm_wide": 2**128,
                }[kind]
            elif kind == "df_missing":
                result.pop("df")
            else:
                result["df"] = False if kind == "df_bool" else 1
            c.adapter._expected = lambda vector, child_fixture: copy.deepcopy(result)
            with pytest.raises(
                c.callback.ConformanceError, match="^callback SIMD child state differs$"
            ):
                c.callback._expected(cv, fixture, class_module=c.adapter)
    finally:
        c.adapter._expected = original_expected


def _check_native_controls(codes, points, vector, produced, previous, captured):
    fixture = c._resume(produced, previous, captured, vector)
    required = {
        "simd_growth_entry",
        "simd_resize_entry",
        "simd_copy_entry",
        "simd_copy_xmm",
        "simd_copy_return",
        "simd_copy_flags",
        "simd_xmm",
        "simd_df",
        "simd_spare",
    }
    assert required <= set(c.CONTROLS)
    assert set(c.normal.CONTROLS) <= set(c.CONTROLS)
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError, match="^" + reason + "$"):
            c._run_case(codes, points, fixture, produced, vector, kind)
    assert c._run_case(codes, points, fixture, produced, vector, "cookie") == dict(
        kind="cookie", rejected=True, endpoint="0x003574d5"
    )


def _isolated(action, index):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and the reviewed private native runtime")
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        capture_output=True,
        timeout=900,
        env=environment,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == result.stderr == b""


SELECTED = [
    next(
        index
        for index, vector in enumerate(c.vectors())
        if vector["profile"] == profile
        and vector["first_key_profile"] == first
        and vector["vector_alignment"] == alignment
    )
    for profile in (0, 1)
    for first in (0, 1)
    for alignment in (0, 7, 31)
]


@pytest.mark.parametrize("index", SELECTED)
def test_actual_fifth_both_first_profiles_alignments_and_unchanged_or_flipped_payloads(
    index,
):
    _isolated("packet", index)


def test_actual_capture_stale_metadata_full_boundaries_and_refreshed_digest_corruptions():
    _isolated("captures", len(c.vectors()) - 1)


def test_actual_host_patch_partition_rejects_undeclared_or_coordinated_changes():
    _isolated("host", len(c.vectors()) - 1)


def test_actual_adapter_schema_existing_tree_domain_and_no_replacement_constructor():
    _isolated("adapter", len(c.vectors()) - 1)


def test_actual_native_controls_reject_for_their_declared_reasons_and_cookie_frontier():
    _isolated("controls", len(c.vectors()) - 1)


@pytest.fixture(scope="module")
def receipts():
    assert (
        c.SEALED_SHA256 != "PENDING"
    ), "fifth receipt must be sealed before final delivery"
    return json.loads(EVIDENCE_PATH.read_bytes()), _sources()


def test_fifth_receipt_encoding_source_partition_coverage_and_finite_counts(receipts):
    evidence, sources = receipts
    raw = EVIDENCE_PATH.read_bytes()
    assert raw == c.encode_conformance(evidence).encode("utf-8") and b"\r\n" not in raw
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    verified = c.validate_structure(evidence, sources)
    assert (
        verified["status"] == "structurally_verified"
        and verified["evidence_sha256"] == c.SEALED_SHA256
    )
    assert evidence["vectors"] == c.vectors()
    assert evidence["source_receipts"] == c._preflight(sources)
    count = len(c.vectors())
    summary = evidence["summary"]
    assert {
        key: summary[key]
        for key in (
            "cases",
            "callback_invocations",
            "fifth_class_heap_calls",
            "fifth_payload_updates",
            "fifth_tree_allocations",
            "fifth_copied_old_vector_bytes",
            "fifth_vector_bytes",
            "fifth_capacity_bytes",
            "fifth_preserved_spare_bytes",
            "fourth_simd_entry_captures",
            "fourth_simd_return_captures",
            "simd_wide_reads",
            "simd_wide_writes",
            "free_calls",
            "marker_calls",
            "table_calls",
            "controls",
            "accounting_promotions",
        )
    } == dict(
        cases=count,
        callback_invocations=5 * count,
        fifth_class_heap_calls=count,
        fifth_payload_updates=7 * count,
        fifth_tree_allocations=0,
        fifth_copied_old_vector_bytes=32 * count,
        fifth_vector_bytes=40 * count,
        fifth_capacity_bytes=48 * count,
        fifth_preserved_spare_bytes=8 * count,
        fourth_simd_entry_captures=count,
        fourth_simd_return_captures=count,
        simd_wide_reads=4 * count,
        simd_wide_writes=4 * count,
        free_calls=4 * count,
        marker_calls=10 * count,
        table_calls=10 * count,
        controls=len(evidence["negative_controls"]),
        accounting_promotions=0,
    )
    assert summary["static_sites"] == len(evidence["body"]["points"])
    assert summary["executed_sites"] == len(evidence["executed_rvas"])
    assert set(evidence["executed_rvas"]) <= {
        point["rva"] for point in evidence["body"]["points"]
    }
    assert {
        "0x0036e5b1",
        "0x0036ea60",
        "0x0036ea64",
        "0x0036ea69",
        "0x0036ea6d",
    } <= set(evidence["executed_rvas"])
    predecessor = sources["factory_callback_fourth"]
    for ordinal in ("first", "second", "third", "fourth"):
        assert (
            evidence[ordinal + "_executed_rvas"]
            == predecessor[ordinal + "_executed_rvas"]
        )
        assert (
            evidence[ordinal + "_observations_sha256"]
            == predecessor[ordinal + "_observations_sha256"]
        )
    assert (
        evidence["producer_observations_sha256"]
        == predecessor["producer_observations_sha256"]
    )
    assert evidence["scope"]["continuous_each_callback"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    assert all(control["rejected"] for control in evidence["negative_controls"])


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
        "pins",
        "scope",
    ),
)
def test_fifth_sealed_receipt_tampering_is_rejected(receipts, kind):
    original, sources = receipts
    evidence = copy.deepcopy(original)
    if kind == "summary":
        evidence["summary"]["cases"] += 1
    elif kind == "vector":
        evidence["vectors"][0]["source_profile"] = 2
    elif kind == "observation":
        field = next(key for key in evidence if key.endswith("observations_sha256"))
        evidence[field] = "0" * 64
    elif kind == "control":
        evidence["negative_controls"][0]["rejected"] = False
    elif kind == "coverage":
        evidence["executed_rvas"].pop()
    elif kind == "point":
        evidence["body"]["points"][0]["size"] += 1
    elif kind == "range":
        evidence["body"]["ranges"][0]["end_rva"] = "0xffffffff"
    elif kind == "pins":
        evidence["source_receipts"] = {}
    else:
        evidence["scope"]["checked"][0] += " hardware allocation ownership"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize(
    "key",
    (
        "factory_callback_fourth",
        "class_simd",
        "simd_growth",
        "simd_resize",
        "short_simd_conformance",
    ),
)
def test_fifth_source_receipt_tampering_is_rejected(receipts, key):
    evidence, original = receipts
    sources = copy.deepcopy(original)
    sources[key]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_fifth_exact_cli_build_verify_and_structure(receipts, command):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and the reviewed private native runtime")
    arguments = [
        sys.executable,
        str(
            ROOT / "scripts/itb_native_lua_class_factory_callback_fifth_conformance.py"
        ),
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
        arguments, cwd=ROOT, capture_output=True, timeout=2400, env=environment
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
    faulthandler.disable()
    action, index = sys.argv[1], int(sys.argv[2])
    codes, points, vector, produced, previous, captured, chain = _native_inputs(index)
    if action == "packet":
        _check_packet(codes, points, vector, produced, previous, captured, chain)
    elif action == "captures":
        _check_capture_controls(vector, produced, previous, captured)
    elif action == "host":
        _check_host_controls(vector, produced, previous, captured)
    elif action == "adapter":
        _check_adapter_controls(vector, produced, previous, captured)
    elif action == "controls":
        _check_native_controls(codes, points, vector, produced, previous, captured)
    else:
        raise ValueError("unknown isolated fifth action")
