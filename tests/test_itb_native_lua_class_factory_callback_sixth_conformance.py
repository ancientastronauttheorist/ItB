"""Independent actual-fifth capture, sixth spare transport and retained-page laws."""

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
from src.observatory import native_lua_class_factory_callback_sixth_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE_PATH = PROGRAMS / (
    PREFIX + "native_lua_class_factory_callback_sixth_conformance.json"
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
    chain = c._produce_fifth(payload, fp, continuation, codes, points, vector)
    assert len(chain) == 12
    produced, _, _, _, _, _, _, _, _, _, previous, captured = chain
    return codes, points, vector, produced, previous, captured


def _boundary(registers, xmm, endpoint):
    return dict(
        registers=dict(registers), xmm=dict(xmm), flags=0x246, endpoint=endpoint
    )


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize("value", (0, 1, 2**127, 2**128 - 1))
def test_boundary_uses_exact_expected_full_xmm_not_synthesized_zero(label, value):
    registers = dict.fromkeys(GPR, 0)
    xmm = {name: (value + index) % 2**128 for index, name in enumerate(XMM)}
    row = _boundary(registers, xmm, 0x0400A000)
    before = copy.deepcopy(row)
    assert c._checked_boundary([row], registers, xmm, 0x0400A000, label) == row
    assert row == before


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize("register", GPR + XMM)
def test_each_captured_gpr_and_xmm_is_independently_checked(label, register):
    registers = dict.fromkeys(GPR, 0)
    xmm = {name: 2**96 + index for index, name in enumerate(XMM)}
    row = _boundary(registers, xmm, 0x0400A000)
    row["registers" if register in GPR else "xmm"][register] ^= 1
    with pytest.raises(
        c.ConformanceError, match="fifth producer " + label + " boundary differs"
    ):
        c._checked_boundary([row], registers, xmm, 0x0400A000, label)


@pytest.mark.parametrize("label", ("entry", "return"))
@pytest.mark.parametrize(
    "kind",
    (
        "empty",
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
        "xmm_bool",
        "xmm_negative",
        "xmm_wide",
        "flags_bool",
        "flags_df",
        "flags_wrong",
        "pc_bool",
        "pc_wrong",
    ),
)
def test_fifth_boundary_closed_typed_schemas_pc_flags_and_capture_counts(label, kind):
    registers, xmm = dict.fromkeys(GPR, 0), dict.fromkeys(XMM, 0)
    endpoint = 0x0400A000
    row = _boundary(registers, xmm, endpoint)
    rows = [row]
    if kind == "empty":
        rows = []
    elif kind == "duplicate":
        rows.append(copy.deepcopy(row))
    elif kind == "tuple":
        rows = tuple(rows)
    elif kind == "extra":
        row["ownership"] = True
    elif kind == "missing":
        row.pop("flags")
    elif kind == "gpr_extra":
        row["registers"]["eip"] = endpoint
    elif kind == "gpr_missing":
        row["registers"].pop("eax")
    elif kind.startswith("gpr_"):
        row["registers"]["eax"] = False if kind == "gpr_bool" else 2**32
    elif kind == "xmm_extra":
        row["xmm"]["xmm8"] = 0
    elif kind == "xmm_missing":
        row["xmm"].pop("xmm7")
    elif kind == "xmm_tuple":
        row["xmm"] = tuple(row["xmm"].items())
    elif kind.startswith("xmm_"):
        row["xmm"]["xmm7"] = {
            "xmm_bool": False,
            "xmm_negative": -1,
            "xmm_wide": 2**128,
        }[kind]
    elif kind.startswith("flags_"):
        row["flags"] = {"flags_bool": True, "flags_df": 0x646, "flags_wrong": 0x247}[
            kind
        ]
    else:
        row["endpoint"] = False if kind == "pc_bool" else endpoint ^ 1
    with pytest.raises(c.ConformanceError):
        c._checked_boundary(rows, registers, xmm, endpoint, label)


def _spare_state_fixture():
    xmm = {
        name: (index + 1) * 0x102030405060708090A0B0C0D0
        for index, name in enumerate(XMM)
    }
    return dict(
        simd_state=dict(xmm=xmm, df=0),
        prototype=dict(
            old_size=5,
            vector_begin=0x06002807,
            vector_end=0x0600282F,
            vector_capacity=0x06002837,
            xmm=copy.deepcopy(xmm),
        ),
    )


def test_spare_transport_has_distinct_mode_and_detached_exact_two_key_state():
    assert c.adapter.XMM_SPARE_FACTORY is True
    assert getattr(c.adapter, "SIMD_FACTORY", False) is not True
    assert len(c.adapter.VECTOR_KEYS) == 20 and len(c.adapter.FIXTURE_KEYS) == 25
    fixture = _spare_state_fixture()
    before = copy.deepcopy(fixture)
    result = c.callback._simd_state(fixture, c.adapter)
    assert set(result) == {"xmm", "df"} and result == fixture["simd_state"]
    result["xmm"]["xmm7"] ^= 1
    assert fixture == before
    assert c.callback._simd_state({}, c.fifth.old) is None
    with pytest.raises(c.adapter.ConformanceError, match="actual retained capture"):
        c.adapter._fixture({})


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "default",
        "state_extra",
        "df_bool",
        "df_set",
        "xmm_bool",
        "xmm_wide",
        "xmm_missing",
        "xmm_extra",
        "xmm_tuple",
        "old_size",
        "old_size_bool",
        "begin",
        "end",
        "capacity",
        "mismatch",
        "prototype_xmm_bool",
        "old_begin",
        "old_base",
        "new_base",
        "new_page_count",
    ),
)
def test_spare_transport_rejects_growth_geometry_types_and_undeclared_modes(kind):
    fixture, module = _spare_state_fixture(), c.adapter
    if kind == "missing":
        fixture.pop("simd_state")
    elif kind == "default":
        module = c.fifth.old
    elif kind == "state_extra":
        fixture["simd_state"]["ownership"] = True
    elif kind in ("df_bool", "df_set"):
        fixture["simd_state"]["df"] = False if kind == "df_bool" else 1
    elif kind == "xmm_missing":
        fixture["simd_state"]["xmm"].pop("xmm7")
    elif kind == "xmm_extra":
        fixture["simd_state"]["xmm"]["xmm8"] = 0
    elif kind == "xmm_tuple":
        fixture["simd_state"]["xmm"] = tuple(fixture["simd_state"]["xmm"].items())
    elif kind in ("xmm_bool", "xmm_wide"):
        fixture["simd_state"]["xmm"]["xmm7"] = False if kind == "xmm_bool" else 2**128
    elif kind in ("old_size", "old_size_bool"):
        fixture["prototype"]["old_size"] = 4 if kind == "old_size" else True
    elif kind in ("begin", "end", "capacity"):
        fixture["prototype"]["vector_" + kind] ^= 1
    elif kind == "mismatch":
        fixture["prototype"]["xmm"]["xmm7"] ^= 1
    elif kind == "prototype_xmm_bool":
        fixture["prototype"]["xmm"]["xmm7"] = False
    else:
        fixture["prototype"][kind] = 0x06003000
    with pytest.raises(c.callback.ConformanceError):
        c.callback._simd_state(fixture, module)


def test_sixth_matrix_pins_and_predecessor_seal_are_exact():
    assert c.vectors() == c.fifth.vectors() and len(c.vectors()) == 216
    assert len(c.SOURCE_PINS) == 46
    assert c.SOURCE_PINS["factory_callback_fifth"][1] == c.fifth.SEALED_SHA256
    sources = _sources()
    assert set(c._preflight(sources)) == set(c.SOURCE_PINS)
    assert all(
        c._canonical_sha256(sources[key]) == digest
        for key, (_, digest) in c.SOURCE_PINS.items()
    )


def _check_packet(codes, points, vector, produced, previous, captured):
    before = copy.deepcopy((produced, previous, captured))
    prior, addresses = c._check_fifth(produced, previous, captured)
    snapshot = blob(previous["pages"], previous["fourth_vector_pointer"], 32)
    xmm = dict.fromkeys(XMM, 0)
    xmm.update(
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:], "little"),
    )
    assert captured["entry"][0]["xmm"] == dict.fromkeys(XMM, 0)
    assert captured["returned"][0]["xmm"] == xmm
    assert captured["entry"][0]["flags"] == captured["returned"][0]["flags"] == 0x246
    assert captured["entry"][0]["registers"] == previous["registers"]
    assert captured["returned"][0]["registers"] == prior["full_return"]["registers"]
    fixture = c._resume(produced, previous, captured, vector)
    assert (produced, previous, captured) == before
    c._check_host_patches(captured, fixture)
    allowed = {fixture["entry"] + index for index in range(8)} | {
        address + 20 + index
        for address in previous["prototype"]["source_addresses"]
        for index in range(4)
    }
    assert len(fixture["patches"]) == len(allowed) == 36
    assert {row["address"] for row in fixture["patches"]} == allowed
    assert {
        page + offset
        for page, payload in fixture["pages"].items()
        for offset, byte in enumerate(payload)
        if byte != captured["pages"][page][offset]
    } <= allowed
    source = copy.deepcopy(previous["prototype"]["source_state"])
    source["payloads"] = [
        word_value ^ (0xFFFFFFFF if vector["profile"] == 0 else 0)
        for word_value in source["payloads"]
    ]
    assert fixture["prototype"]["source_state"] == source
    assert (
        fixture["prototype"]["destination_state"]
        == prior["class_transfer"]["destination"]
    )
    assert fixture["prototype"]["destination_addresses"] == addresses
    assert set(fixture["prototype"]).isdisjoint(
        {"old_begin", "old_base", "new_base", "new_page_count"}
    )
    assert fixture["simd_state"] == dict(xmm=xmm, df=0)
    logical = c._logical(fixture)
    expected = c.callback._expected(
        fixture["callback_vector"], fixture, class_module=c.adapter
    )
    child = next(row for row in expected["children"] if row["kind"] == "class")
    assert set(child["fixture"]) == c.adapter.FIXTURE_KEYS
    assert (
        child["result"]["tree_heap_count"] == 0 and child["result"]["heap_nodes"] == []
    )
    assert len(child["result"]["insertions"]) == 7
    assert all(
        row["inserted"] is False and row["heap_node"] is None
        for row in child["result"]["insertions"]
    )
    assert child["result"]["destination_addresses"] == addresses
    assert child["result"]["registers"] == logical["class_return"]["registers"]
    assert child["result"]["registers"]["edx"] == fixture["entry"] - 60
    assert child["result"]["registers"]["esp"] == fixture["entry"] - 40
    assert child["result"]["endpoint"] == 0x006EC1BD
    assert child["result"]["xmm"] == expected["xmm"] == xmm
    assert child["result"]["df"] == expected["df"] == 0
    assert not any(row["width"] == 8 for row in expected["events"])
    begin = fixture["vector_begin"]
    assert begin == previous["vector_begin"] == 0x06002800 + vector["vector_alignment"]
    pair = bytes(4) + fixture["source_pointer"].to_bytes(4, "little")
    assert blob(captured["pages"], begin, 40) == pair * 5
    final = expected["pages"]
    assert blob(final, begin, 48) == pair * 6
    for offset, value in ((4, begin), (8, begin + 48), (12, begin + 48), (56, 8)):
        assert word(final, fixture["receiver"] + offset) == value
    wanted_page = bytearray(captured["pages"][begin & ~4095])
    at = (begin & 4095) + 40
    wanted_page[at : at + 8] = pair
    assert final[begin & ~4095] == bytes(wanted_page)
    for pointer, size in (
        (previous["fourth_vector_pointer"], 32),
        (previous["third_vector_pointer"], 24),
        (previous["second_vector_pointer"], 16),
        (previous["first_arguments"]["vector_pointer"], 8),
    ):
        assert blob(final, pointer, size) == blob(captured["pages"], pointer, size)
    assert blob(final, produced["fixture"]["record"], 24) == blob(
        captured["pages"], produced["fixture"]["record"], 24
    )
    preserved = [offset for offset in range(0, 72, 4) if offset not in (0, 8)]
    assert len(preserved) == 16
    assert all(
        word(final, fixture["receiver"] + offset)
        == word(captured["pages"], fixture["receiver"] + offset)
        for offset in preserved
    )
    assert logical["field_updates"] == {8: begin + 48}
    assert logical["normal_field_updates"] == {
        0: fixture["callback_vector"]["source_word"],
        8: begin + 48,
    }
    retained_values = source_values(prior["class_transfer"]["destination"])
    source_map = source_values(source)
    final_state = logical["class_transfer"]["destination"]
    assert source_values(final_state) == retained_values | source_map
    assert source_values(final_state)[16] == retained_values[16]
    for address, node in zip(addresses, final_state["tree"]["nodes"]):
        assert blob(final, address, 20) == blob(captured["pages"], address, 20)
        assert word(final, address + 20) == source_map.get(
            node["key"], retained_values[node["key"]]
        )
    for pointer, value in fixture["prototype"]["strings"].items():
        assert blob(final, pointer, len(value)) == value
    assert final[0x00893000] == captured["pages"][0x00893000]
    final_capture = {}

    def capture(machine, ids, oracle, lua):
        final_capture["pages"] = {
            page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]
        }

    result = c._run_case(codes, points, fixture, produced, vector, capture=capture)
    assert final_capture["pages"] == final
    assert result["allocations"] == result["frees"] == []
    assert result["payload_updates"] == 7
    assert result["registers"] == logical["full_return"]["registers"]
    assert result["xmm"] == xmm and result["df"] == 0
    assert result["events_sha256"] == c._canonical_sha256(expected["events"])
    assert result["memory_sha256"] == c.fifth.repeat._page_sha(final)
    assert result["captured_pages_sha256"] == c.fifth.repeat._page_sha(
        captured["pages"]
    )
    assert result["captured_simd_sha256"] == c._canonical_sha256(
        dict(entry=captured["entry"], returned=captured["returned"])
    )
    assert not {"0x0036ea60", "0x0036ea64", "0x0036ea69", "0x0036ea6d"} & set(
        result["trace_rvas"]
    )
    original = copy.deepcopy((previous, captured))
    fixture["prototype"]["source_state"]["payloads"][0] ^= 1
    fixture["prototype"]["destination_addresses"].clear()
    fixture["simd_state"]["xmm"]["xmm7"] ^= 1
    fixture["callback_vector"]["source_refs"][0] ^= 1
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
            c.ConformanceError, match="^verified fifth callback capture differs$"
        ):
            c._check_fifth(produced, previous, altered)
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
                match="^fifth producer " + label + " boundary differs$",
            ):
                c._check_fifth(produced, previous, altered)
    for domain in ("capture", "observation"):
        altered = copy.deepcopy(captured)
        target = (
            altered["registers"]
            if domain == "capture"
            else altered["observation"]["registers"]
        )
        target["eax"] = False
        with pytest.raises(c.ConformanceError):
            c._check_fifth(produced, previous, altered)
    for register in GPR:
        altered = copy.deepcopy(captured)
        for target in (
            altered["registers"],
            altered["observation"]["registers"],
            altered["returned"][0]["registers"],
        ):
            target[register] ^= 1
        with pytest.raises(c.ConformanceError):
            c._check_fifth(produced, previous, altered)
    for kind in (
        "xmm_value",
        "xmm_bool",
        "xmm_missing",
        "xmm_extra",
        "df_set",
        "df_bool",
    ):
        altered = copy.deepcopy(captured)
        observation = altered["observation"]
        if kind == "xmm_value":
            observation["xmm"]["xmm0"] ^= 1
        elif kind == "xmm_bool":
            observation["xmm"]["xmm7"] = False
        elif kind == "xmm_missing":
            observation["xmm"].pop("xmm7")
        elif kind == "xmm_extra":
            observation["xmm"]["xmm8"] = 0
        else:
            observation["df"] = 1 if kind == "df_set" else False
        with pytest.raises(c.ConformanceError):
            c._check_fifth(produced, previous, altered)
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
        ("source_head" + str(offset), c.fifth.old.prefix.SOURCE_HEAD + offset)
        for offset in range(24)
    ]
    for pointer, data in previous["prototype"]["strings"].items():
        locations += [
            ("key" + str(pointer) + "_" + str(offset), pointer + offset)
            for offset in (0, len(data) - 1)
        ]
    for name, pointer, size in (
        ("fifth", previous["vector_begin"], 40),
        ("fourth", previous["fourth_vector_pointer"], 32),
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
        ("future_spare", 0x06002800 + vector["vector_alignment"] + 47),
        ("stack_scratch", previous["entry"] - 100),
    ]
    for name, address in locations:
        altered = copy.deepcopy(captured)
        altered["pages"] = change(
            altered["pages"], address, word(altered["pages"], address, 1) ^ 1
        )
        altered["observation"]["memory_sha256"] = c.fifth.repeat._page_sha(
            altered["pages"]
        )
        with pytest.raises(
            c.ConformanceError, match="^retained fifth callback differs$"
        ):
            c._check_fifth(produced, previous, altered)
    for field in ("allocations", "frees"):
        altered = copy.deepcopy(captured)
        altered["observation"][field][0]["entry_esp"] ^= 1
        with pytest.raises(
            c.ConformanceError, match="^retained fifth callback differs$"
        ):
            c._check_fifth(produced, previous, altered)
    altered = copy.deepcopy(captured)
    altered["observation"]["frees"][0]["result"] = True
    with pytest.raises(c.ConformanceError):
        c._check_fifth(produced, previous, altered)
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
            c.ConformanceError, match="^sixth host patch partition differs$"
        ):
            c._check_host_patches(captured, altered)
    assert (fixture, captured) == before


def _check_event_corruptions(adapter, vector, fixture, copies, events):
    inherited_events = adapter.prefix._expected(vector, fixture)["events"]

    def check(packet):
        adapter._event_law(
            vector, fixture, copies, packet, inherited_events=inherited_events
        )

    check(events)
    entry = fixture["stack"]
    payload_indices = [
        index
        for index, row in enumerate(events)
        if row["access"] == "write"
        and row["address"]
        in {
            fixture["destination_addresses"][copy_row["destination"]] + 20
            for copy_row in copies
        }
    ]
    assert len(payload_indices) == 7
    omitted_id = next(
        identity
        for identity, node in enumerate(fixture["destination_state"]["tree"]["nodes"])
        if node["key"] == 16
    )
    omitted = fixture["destination_addresses"][omitted_id] + 20
    old_word = adapter._raw(fixture["pages"], omitted)
    forged = dict(access="write", address=omitted, width=4, value=old_word ^ 1)
    restored = dict(forged, value=old_word)
    mutations = []
    mutations.append([])
    altered = copy.deepcopy(events)
    altered[payload_indices[0] : payload_indices[0]] = [forged, restored]
    mutations.append(altered)
    altered = copy.deepcopy(events)
    altered.insert(payload_indices[0], copy.deepcopy(altered[payload_indices[0]]))
    mutations.append(altered)
    altered = copy.deepcopy(events)
    first, second = payload_indices[:2]
    altered[first], altered[second] = altered[second], altered[first]
    mutations.append(altered)
    for field, value in (
        ("value", events[first]["value"] ^ 1),
        ("value", False),
        ("address", omitted),
        ("width", 1),
        ("access", "read"),
    ):
        altered = copy.deepcopy(events)
        altered[first][field] = value
        mutations.append(altered)
    altered = copy.deepcopy(events)
    altered.pop(first)
    mutations.append(altered)
    for altered in mutations:
        with pytest.raises(
            adapter.ConformanceError,
            match="^factory spare ordered nonstack writes differ$",
        ):
            check(altered)

    # Ten scalar append events plus nine independently derived normal-return
    # events. The admitted C+28 argument is above the fixed vector end.
    assert entry + 28 > fixture["vector_end"]
    tail_size = 19
    assert len(events) >= tail_size
    append_start = len(events) - tail_size
    assert events[append_start] == dict(
        access="read", address=entry - 16, width=4, value=adapter.prefix.RECEIVER
    )
    for offset in range(tail_size):
        for field in ("address", "value", "width", "access"):
            altered = copy.deepcopy(events)
            row = altered[append_start + offset]
            if field == "access":
                row[field] = "write" if row[field] == "read" else "read"
            elif field == "width":
                row[field] = 1
            else:
                row[field] ^= 1
            with pytest.raises(adapter.ConformanceError):
                check(altered)
    for kind in ("missing", "duplicate", "reorder", "extra"):
        altered = copy.deepcopy(events)
        if kind == "missing":
            altered.pop(append_start)
        elif kind == "duplicate":
            altered.insert(append_start, copy.deepcopy(altered[append_start]))
        elif kind == "reorder":
            altered[append_start], altered[append_start + 1] = (
                altered[append_start + 1],
                altered[append_start],
            )
        else:
            altered.append(dict(access="read", address=entry, width=4, value=0))
        with pytest.raises(
            adapter.ConformanceError,
            match="^factory spare append and return event tail differs$",
        ):
            check(altered)


def _check_adapter_controls(vector, produced, previous, captured):
    fixture = c._resume(produced, previous, captured, vector)
    cv = fixture["callback_vector"]
    expected = c.callback._expected(cv, fixture, class_module=c.adapter)
    child = next(row for row in expected["children"] if row["kind"] == "class")
    _, _, copies = c.adapter._checked(cv, child["fixture"])
    _check_event_corruptions(
        c.adapter, cv, child["fixture"], copies, child["result"]["events"]
    )
    for kind in (
        "vector_extra",
        "vector_missing",
        "fixture_extra",
        "fixture_missing",
        "old_size",
        "spare",
        "buffer",
        "nil_bool",
        "profile",
        "source_key",
        "destination_key",
        "marker_bool",
        "source_word_bool",
        "word_mismatch",
        "transfer",
        "xmm_bool",
        "gpr_bool",
        "growth_key",
        "begin",
        "end",
        "capacity",
    ):
        v, child_fixture = copy.deepcopy(cv), copy.deepcopy(child["fixture"])
        if kind == "vector_extra":
            v["ownership"] = True
        elif kind == "vector_missing":
            v.pop("buffer_address")
        elif kind == "fixture_extra":
            child_fixture["ownership"] = True
        elif kind == "fixture_missing":
            child_fixture.pop("xmm")
        elif kind == "old_size":
            v["old_size"] = 4
        elif kind == "spare":
            v["spare_records"] = 2
        elif kind == "buffer":
            v["buffer_address"] ^= 1
        elif kind == "nil_bool":
            v["nil_flag"] = True
        elif kind == "profile":
            v["profile"] = "all_new"
        elif kind == "source_key":
            v["source_keys"][0] ^= 1
        elif kind == "destination_key":
            v["destination_keys"][0] ^= 1
        elif kind == "marker_bool":
            v["marker_words"][0] = False
        elif kind == "source_word_bool":
            v["source_word"] = False
        elif kind == "word_mismatch":
            v["destination_word"] ^= 1
        elif kind == "transfer":
            v["transfers"][0] = ["invalid"]
        elif kind == "xmm_bool":
            child_fixture["xmm"]["xmm7"] = False
        elif kind == "gpr_bool":
            child_fixture["registers"]["eax"] = False
        elif kind == "growth_key":
            child_fixture["old_begin"] = previous["fourth_vector_pointer"]
        else:
            child_fixture["vector_" + kind] ^= 1
        with pytest.raises(c.adapter.ConformanceError):
            c.adapter._expected(v, child_fixture)
    original_fixture = c.adapter._fixture

    def forbidden(*arguments, **keywords):
        raise AssertionError("sixth retained path constructed a replacement fixture")

    c.adapter._fixture = forbidden
    try:
        assert c.callback._expected(cv, fixture, class_module=c.adapter) == expected
    finally:
        c.adapter._fixture = original_fixture
    original_expected = c.adapter._expected
    try:
        for kind in XMM + ("missing", "bool", "df_bool", "df_set"):
            child_result = copy.deepcopy(child["result"])
            if kind in XMM:
                child_result["xmm"][kind] ^= 1
            elif kind == "missing":
                child_result["xmm"].pop("xmm7")
            elif kind == "bool":
                child_result["xmm"]["xmm7"] = False
            else:
                child_result["df"] = False if kind == "df_bool" else 1
            c.adapter._expected = lambda vector, fixture: copy.deepcopy(child_result)
            with pytest.raises(
                c.callback.ConformanceError, match="callback SIMD child state differs"
            ):
                c.callback._expected(cv, fixture, class_module=c.adapter)
    finally:
        c.adapter._expected = original_expected


def _check_native_controls(codes, points, vector, produced, previous, captured):
    fixture = c._resume(produced, previous, captured, vector)
    assert c.CONTROLS
    assert not {
        "heap_request",
        "heap_register",
        "heap_flags",
        "heap_identity",
        "heap_response",
        "tree_request",
        "free_request",
        "free_register",
        "free_flags",
        "simd_growth_entry",
        "simd_resize_entry",
        "simd_copy_entry",
        "simd_copy_return",
        "simd_copy_flags",
        "simd_copy_xmm",
    } & set(c.CONTROLS)
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
        timeout=2400,
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
def test_actual_sixth_both_first_profiles_alignments_and_opposite_payload_mask(index):
    _isolated("packet", index)


def test_actual_fifth_capture_full_boundaries_and_refreshed_sha_corruptions():
    _isolated("captures", len(c.vectors()) - 1)


def test_actual_sixth_host_patch_partition_and_coordinated_after_mutation():
    _isolated("host", len(c.vectors()) - 1)


def test_actual_spare_adapter_closed_schema_no_constructor_and_scalar_event_guards():
    _isolated("adapter", len(c.vectors()) - 1)


def test_actual_sixth_controls_exclude_heap_and_reject_for_declared_reasons():
    _isolated("controls", len(c.vectors()) - 1)


@pytest.fixture(scope="module")
def receipts():
    assert (
        c.SEALED_SHA256 != "PENDING"
    ), "sixth receipt must be sealed before final delivery"
    return json.loads(EVIDENCE_PATH.read_bytes()), _sources()


def test_sixth_sealed_receipt_exact_predecessor_hashes_coverage_and_finite_counts(
    receipts,
):
    evidence, sources = receipts
    raw = EVIDENCE_PATH.read_bytes()
    assert raw == c.encode_conformance(evidence).encode("utf-8") and b"\r\n" not in raw
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    verified = c.validate_structure(evidence, sources)
    assert verified["status"] == "structurally_verified"
    assert verified["evidence_sha256"] == c.SEALED_SHA256
    assert evidence["vectors"] == c.vectors()
    assert evidence["source_receipts"] == c._preflight(sources)
    count, summary = len(c.vectors()), evidence["summary"]
    expected = dict(
        cases=count,
        callback_invocations=6 * count,
        sixth_class_heap_calls=0,
        sixth_payload_updates=7 * count,
        sixth_tree_allocations=0,
        sixth_copied_old_vector_bytes=0,
        sixth_vector_bytes=48 * count,
        sixth_capacity_bytes=48 * count,
        sixth_preserved_old_vector_bytes=40 * count,
        sixth_free_calls=0,
        fifth_xmm_entry_captures=count,
        fifth_xmm_return_captures=count,
        sixth_wide_reads=0,
        sixth_wide_writes=0,
        sixth_xmm_preservations=count,
        marker_calls=12 * count,
        table_calls=12 * count,
        accounting_promotions=0,
    )
    assert {key: summary[key] for key in expected} == expected
    predecessor = sources["factory_callback_fifth"]
    for key in ("simd_wide_reads", "simd_wide_writes", "free_calls"):
        assert summary[key] == predecessor["summary"][key]
    assert summary["controls"] == len(evidence["negative_controls"])
    assert summary["static_sites"] == len(evidence["body"]["points"])
    assert summary["executed_sites"] == len(evidence["executed_rvas"])
    assert set(evidence["executed_rvas"]) <= {
        point["rva"] for point in evidence["body"]["points"]
    }
    for ordinal in ("first", "second", "third", "fourth", "fifth"):
        for suffix in ("_executed_rvas", "_observations_sha256"):
            assert evidence[ordinal + suffix] == predecessor[ordinal + suffix]
    assert (
        evidence["producer_observations_sha256"]
        == predecessor["producer_observations_sha256"]
    )
    assert (
        evidence["fourth_simd_boundary_observations_sha256"]
        == predecessor["fourth_simd_boundary_observations_sha256"]
    )
    assert len(evidence["fifth_xmm_boundary_observations_sha256"]) == 64
    assert all(row["rejected"] for row in evidence["negative_controls"])


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
def test_sixth_sealed_receipt_tampering_is_rejected(receipts, kind):
    original, sources = receipts
    evidence = copy.deepcopy(original)
    if kind == "summary":
        evidence["summary"]["cases"] += 1
    elif kind == "vector":
        evidence["vectors"][0]["source_profile"] = 2
    elif kind == "observation":
        evidence["fifth_xmm_boundary_observations_sha256"] = "0" * 64
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
        evidence["scope"]["checked"][0] += " actual heap ownership"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize(
    "key",
    ("factory_callback_fifth", "factory_callback_fourth", "class_simd", "simd_growth"),
)
def test_sixth_pinned_source_tampering_rejects_even_unchanged_evidence(receipts, key):
    evidence, original = receipts
    sources = copy.deepcopy(original)
    sources[key]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_sixth_exact_cli_build_verify_and_structure(receipts, command):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and the reviewed private native runtime")
    arguments = [
        sys.executable,
        str(
            ROOT / "scripts/itb_native_lua_class_factory_callback_sixth_conformance.py"
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
    codes, points, vector, produced, previous, captured = _native_inputs(index)
    if action == "packet":
        _check_packet(codes, points, vector, produced, previous, captured)
    elif action == "captures":
        _check_capture_controls(vector, produced, previous, captured)
    elif action == "host":
        _check_host_controls(vector, produced, previous, captured)
    elif action == "adapter":
        _check_adapter_controls(vector, produced, previous, captured)
    elif action == "controls":
        _check_native_controls(codes, points, vector, produced, previous, captured)
    else:
        raise ValueError("unknown isolated sixth action")
