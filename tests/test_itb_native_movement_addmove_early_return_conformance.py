"""Independent AddMove count-zero/one laws and isolated actual-state checks."""

import copy
import faulthandler
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from collections import UserDict

import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_movement_addmove_early_return_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_movement_addmove_early_return_conformance.json")
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
PAGE_ORDER = (
    0,
    0x30000000,
    0x30001000,
    0x06002000,
    0x06000000,
    0x10000000,
    0x00893000,
    0x008B7000,
    0x007D6000,
)
PARAMETERS = (0xBF800000, 0x7FC01234, 0xFF800000)
PREFIX_TRACE = (
    0x257340,
    0x257341,
    0x257343,
    0x257345,
    0x25734A,
    0x257350,
    0x257351,
    0x257357,
    0x25735C,
    0x25735E,
    0x257361,
    0x257362,
    0x257363,
    0x257364,
    0x257367,
    0x25736D,
    0x25736F,
    0x257376,
    0x257379,
    0x25737C,
    0x25737E,
    0x257381,
    0x257384,
    0x257386,
    0x257388,
    0x2573F0,
    0x2573F2,
)
OWNED_TRACE = (
    0x2573F4,
    0x2573F7,
    0x2573F9,
    0x2573FB,
    0x2573FE,
    0x2573FF,
    0x257400,
    0x7800,
    0x7801,
    0x7803,
    0x7806,
    0x7809,
    0x780B,
    0x780E,
    0x7810,
    0x7816,
    0x781A,
    0x7820,
    0x784D,
    0x7850,
    0x7851,
    0x35785D,
    0x36FB17,
    0x389156,
    0x389158,
    0x389159,
    0x38915B,
    0x38915F,
    0x389161,
    0x389164,
    0x389166,
    0x38916C,
    0x389172,
    0x389174,
    0x38918E,
    0x38918F,
    0x7856,
    0x7859,
    0x785A,
    0x257405,
)
SUFFIX_TRACE = (
    0x257408,
    0x25740A,
    0x25740D,
    0x257414,
    0x257415,
    0x257416,
    0x257417,
    0x25741A,
    0x25741C,
    0x3574CA,
    0x3574D0,
    0x3574D3,
    0x257421,
    0x257423,
    0x257424,
)
BODY_RANGES = (
    (0x7800, 0x785B),
    (0x257340, 0x257427),
    (0x3574CA, 0x3574D5),
    (0x35785D, 0x357862),
    (0x36FB17, 0x36FB1C),
    (0x389156, 0x389190),
)
POINT_SHA = "c9b19a18f0af920b1444c18aa583d6b1d067b164d2cb7d3d068be7dd5760aa3f"
PACKET_KEYS = {
    "path",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "free_entry",
    "free_return",
    "free_packet",
    "imported",
    "cookie_entry",
}
OBSERVATION_KEYS = {
    "vector",
    "registers",
    "xmm",
    "flags",
    "flag_mask",
    "df",
    "trace_rvas",
    "events_sha256",
    "pages_sha256",
    "memory_event_count",
    "boundaries",
    "summaries",
}
SELECTED = (0, 1, 2, 12, 14, 69, 70, 71, 135, 139, 141, 143)
CONTROLS = {
    **{
        stage + "_" + suffix: "movement " + stage.replace("_", " ") + " differs"
        for stage in ("free_entry", "free_return", "cookie_entry")
        for suffix in ("gpr", "xmm", "flags", "df", "page")
    },
    "count": "movement native path differs",
    "capacity": "movement ordered memory events differ",
    "free_request": "movement free handoff differs",
    **{
        name: "movement supplied response preservation differs"
        for name in ("response_gpr", "response_xmm", "response_page", "response_result")
    },
    "cookie": "movement cookie entry differs",
    **{
        name: "movement final pages differ"
        for name in (
            "seh",
            "ancestor",
            "old",
            "receiver",
            "feature_padding",
            "iat_padding",
            "ignored_parameter",
            "caller_header",
        )
    },
    **{
        name: "movement final ABI differs"
        for name in (
            "final_al",
            "final_nonvolatile",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "movement final events differ",
    "restored_write_record": "movement final events differ",
    "trace_record": "movement final native path differs",
}


def strict_equal(a, b):
    assert type(a) is type(b), (type(a), type(b))
    if type(a) is dict:
        assert set(a) == set(b)
        assert all(any(type(k) is type(j) and k == j for j in b) for k in a)
        for k in a:
            strict_equal(a[k], b[k])
    elif type(a) in (list, tuple):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            strict_equal(x, y)
    else:
        assert a == b


def canonical_hash(value):
    raw = (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(v).hexdigest() for p, v in sorted(pages.items())
    }


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def word(pages, address):
    return int.from_bytes(blob(pages, address, 4), "little")


def install(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def all_vectors():
    return [
        dict(alignment=a, profile=p, path_form=f)
        for a in range(16)
        for p in range(3)
        for f in ("null", "empty_owned", "one")
    ]


def independent_fixture(v):
    p, a, form = v["profile"], v["alignment"], v["path_form"]
    pages = {
        address: bytes(
            (index * 37 + offset * 13 + p * 71) & 255 for offset in range(4096)
        )
        for index, address in enumerate(PAGE_ORDER)
    }
    g, o = 0x30001000 + a, 0x06002800 + a
    begin, end, cap = (
        (0, 0, 0) if form == "null" else (o, o + (8 if form == "one" else 0), o + 8)
    )
    for index, value in enumerate((0x04000000, begin, end, cap, PARAMETERS[p])):
        install(pages, g + 4 * index, value)
    for address, value in (
        (0, 0x11112222 ^ p * 0x1020304),
        (0x00893F28, 0x19A51C73 ^ p * 0x2468ACE),
        (0x008B7634, 0x12345678),
        (0x007D621C, 0x05000000),
        (o, 0xD15C0048 ^ p * 0x7654321),
        (o + 4, 0x1122AA48 ^ p * 0x1234567),
    ):
        install(pages, address, value & 0xFFFFFFFF)
    regs = {
        r: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, r in enumerate(GPR)
    }
    regs.update(ecx=0x10000100, esp=g)
    xmms = {
        r: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmms,
        return_address=0x04000000,
        entry_flags=0x246,
    )


def add_flags(a, b):
    result = (a + b) & 0xFFFFFFFF
    return (
        int(a + b > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | ((a ^ b ^ result) & 0x10)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int((~(a ^ b) & (a ^ result) & 0x80000000) != 0) << 11)
    )


def independent(v, fixture):
    initial, pages, events = dict(fixture["registers"]), dict(fixture["pages"]), []
    g, f = initial["esp"], initial["esp"] - 4
    begin, end, capacity = [word(pages, g + k) for k in (4, 8, 12)]
    cookie, seh = word(pages, 0x00893F28), word(pages, 0)
    xmms = dict(fixture["xmm"])

    def emit(access, address, value=None):
        if access == "read":
            actual = word(pages, address)
            if value is not None:
                assert actual == value
            value = actual
        else:
            install(pages, address, value)
        events.append(dict(access=access, address=address, width=4, value=value))

    def boundary(regs, endpoint, flags, mask):
        return dict(
            registers=dict(regs),
            xmm=dict(xmms),
            pages=dict(pages),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    # Exact parent prologue, SEH registration and count inputs, before cleanup.
    prologue = (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CA95E),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("read", 0x00893F28, cookie),
        ("write", g - 20, cookie ^ f),
        ("write", g - 0x280, initial["ebx"]),
        ("write", g - 0x284, initial["esi"]),
        ("write", g - 0x288, cookie ^ f),
        ("write", 0, g - 16),
        ("write", g - 8, 0),
        ("read", g + 8, end),
        ("read", g + 4, begin),
    )
    for row in prologue:
        emit(*row)
    count = 1 if v["path_form"] == "one" else 0
    assert end - begin == count * 8
    regs = dict(
        initial,
        eax=count,
        ebx=initial["ebx"] & 0xFFFFFF00,
        edx=begin,
        esi=0x10000100,
        ebp=f,
        esp=g - 0x288,
    )
    free_entry = free_return = free_packet = imported = None
    if begin:
        emit("read", g + 12, capacity)
        assert capacity - begin == 8
        for address, value in (
            (g - 0x28C, 8),
            (g - 0x290, 1),
            (g - 0x294, begin),
            (g - 0x298, 0x00657405),
        ):
            emit("write", address, value)
        v_sp = g - 0x298
        regs.update(ecx=1, esp=v_sp)
        free_entry = boundary(regs, 0x00407800, 0, 0xC5)
        child_start = len(events)
        # Stride8/count1 selects the ordinary primitive and its DIV remainder7.
        free_rows = (
            ("write", v_sp - 4, f),
            ("read", v_sp + 8, 1),
            ("read", v_sp + 12, 8),
            ("read", v_sp + 12, 8),
            ("read", v_sp + 4, begin),
            ("write", v_sp - 8, begin),
            ("write", v_sp - 12, 0x00407856),
            ("write", v_sp - 16, v_sp - 4),
            ("read", v_sp - 8, begin),
            ("read", v_sp - 8, begin),
            ("write", v_sp - 20, begin),
            ("write", v_sp - 24, 0),
            ("read", 0x008B7634, 0x12345678),
            ("write", v_sp - 28, 0x12345678),
            ("read", 0x007D621C, 0x05000000),
            ("write", v_sp - 32, 0x00789172),
        )
        for row in free_rows:
            emit(*row)
        imported = dict(
            role="free",
            entry_esp=v_sp - 32,
            words=[0x00789172, 0x12345678, 0, begin],
            **boundary(
                dict(
                    regs, eax=0x1FFFFFFF, ecx=begin, edx=7, ebp=v_sp - 16, esp=v_sp - 32
                ),
                0x05000000,
                (4, 0, 0, 4, 0, 4, 4, 0, 0, 4, 4, 0, 4, 0, 0, 4)[v["alignment"]],
                0x8D5,
            ),
        )
        for row in (
            ("read", v_sp - 16, v_sp - 4),
            ("read", v_sp - 12, 0x00407856),
            ("read", v_sp - 4, f),
            ("read", v_sp, 0x00657405),
        ):
            emit(*row)
        regs.update(eax=1, ecx=0xA0000001, edx=0xB0000001, esp=v_sp + 4)
        free_packet = dict(
            registers=dict(regs),
            flags=add_flags(v_sp - 8, 4),
            flag_mask=0x8D5,
            events=copy.deepcopy(events[child_start:]),
            stack=pages[0x30000000] + pages[0x30001000],
            error=pages[0x06000000],
            stop=0x00657405,
            protocol=dict(
                returned=True,
                result=1,
                next_kind=None,
                error_cell=None,
                last_error=None,
            ),
        )
        free_return = boundary(regs, 0x00657405, free_packet["flags"], 0x8D5)
        regs["esp"] += 12
    for row in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ f),
        ("read", g - 0x284, initial["esi"]),
        ("read", g - 0x280, initial["ebx"]),
        ("read", g - 20, cookie ^ f),
        ("write", g - 0x280, 0x00657421),
    ):
        emit(*row)
    final = dict(initial, eax=0, ecx=cookie, edx=0xB0000001 if begin else 0, esp=g + 20)
    cookie_entry = boundary(
        dict(final, ebp=f, esp=g - 0x280), 0x007574CA, (0, 4, 0)[v["profile"]], 0x8C5
    )
    for row in (
        ("read", 0x00893F28, cookie),
        ("read", g - 0x280, 0x00657421),
        ("read", g - 4, initial["ebp"]),
        ("read", g, 0x04000000),
    ):
        emit(*row)
    return dict(
        path=dict(
            begin=begin,
            end=end,
            capacity=capacity,
            count=count,
            parameter_bits=PARAMETERS[v["profile"]],
        ),
        registers=final,
        xmm=xmms,
        pages=pages,
        events=events,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=0x04000000,
        trace_rvas=[
            f"0x{pc:08x}"
            for pc in PREFIX_TRACE + (OWNED_TRACE if begin else ()) + SUFFIX_TRACE
        ],
        free_entry=free_entry,
        free_return=free_return,
        free_packet=free_packet,
        imported=imported,
        cookie_entry=cookie_entry,
    )


def final_pages_by_stores(v, fixture):
    pages, regs = dict(fixture["pages"]), fixture["registers"]
    g, f = regs["esp"], regs["esp"] - 4
    cookie, seh = word(pages, 0x00893F28), word(pages, 0)
    stores = {
        g - 4: regs["ebp"],
        g - 8: 0,
        g - 12: 0x007CA95E,
        g - 16: seh,
        g - 20: cookie ^ f,
        g - 0x280: 0x00657421,
        g - 0x284: regs["esi"],
        g - 0x288: cookie ^ f,
        0: seh,
    }
    if v["path_form"] != "null":
        o, v_sp = 0x06002800 + v["alignment"], g - 0x298
        stores.update(
            {
                g - 0x28C: 8,
                g - 0x290: 1,
                g - 0x294: o,
                g - 0x298: 0x00657405,
                v_sp - 4: f,
                v_sp - 8: o,
                v_sp - 12: 0x00407856,
                v_sp - 16: v_sp - 4,
                v_sp - 20: o,
                v_sp - 24: 0,
                v_sp - 28: 0x12345678,
                v_sp - 32: 0x00789172,
            }
        )
    for address, value in stores.items():
        install(pages, address, value)
    return pages


@pytest.fixture(scope="module")
def cases():
    return [
        (v, f, independent(v, f))
        for v in all_vectors()
        for f in [independent_fixture(v)]
    ]


def test_all144_fixture_recipes_trace_domains_and_full_independent_expected_packets(
    cases,
):
    assert c.vectors() == all_vectors() and len(cases) == 144
    assert len(PREFIX_TRACE + SUFFIX_TRACE) == 42
    assert len(PREFIX_TRACE + OWNED_TRACE + SUFFIX_TRACE) == 82
    assert len(set(PREFIX_TRACE + OWNED_TRACE + SUFFIX_TRACE)) == 82
    for v, f, wanted in cases:
        strict_equal(c._fixture(v), f)
        before = copy.deepcopy(f)
        actual = c._expected(v, f)
        assert set(actual) == PACKET_KEYS and len(actual) == 15
        strict_equal(actual, wanted)
        strict_equal(f, before)
        strict_equal(actual["pages"], final_pages_by_stores(v, f))
        g, o = f["registers"]["esp"], 0x06002800 + v["alignment"]
        assert len(actual["events"]) == (25 if v["path_form"] == "null" else 50)
        assert all(e["width"] == 4 and e["address"] != g + 16 for e in actual["events"])
        assert blob(actual["pages"], g, 20) == blob(f["pages"], g, 20)
        assert blob(actual["pages"], g + 20, 0x30002000 - g - 20) == blob(
            f["pages"], g + 20, 0x30002000 - g - 20
        )
        assert blob(actual["pages"], o, 8) == blob(f["pages"], o, 8)
        assert all(
            actual["pages"][p] == f["pages"][p]
            for p in PAGE_ORDER
            if p not in (0, 0x30000000, 0x30001000)
        )
        if actual["free_packet"] is not None:
            assert (
                len(actual["free_packet"]) == 8
                and len(actual["free_packet"]["events"]) == 20
            )
            assert (
                actual["free_entry"]["flag_mask"],
                actual["cookie_entry"]["flag_mask"],
            ) == (0xC5, 0x8C5)
            assert actual["imported"]["registers"]["edx"] == 7
        actual["pages"].clear()
        actual["xmm"]["xmm7"] = 0
        strict_equal(f, before)


@pytest.mark.parametrize(
    "key,bad",
    (
        ("alignment", False),
        ("alignment", -1),
        ("alignment", 16),
        ("alignment", 2**32),
        ("profile", True),
        ("profile", 3),
        ("profile", 1.0),
        ("path_form", "two"),
        ("path_form", 0),
    ),
)
def test_finite_vector_types_and_bounds_do_not_alias(key, bad):
    v = dict(all_vectors()[0])
    v[key] = bad
    with pytest.raises(c.ConformanceError):
        c._fixture(v)


@pytest.mark.parametrize("kind", ("extra", "missing", "facade", "str_key"))
def test_vector_exact_schema_and_typed_keys(kind):
    v = dict(all_vectors()[0])
    if kind == "extra":
        v["unused"] = 0
    elif kind == "missing":
        v.pop("profile")
    elif kind == "facade":
        v = UserDict(v)
    else:

        class Label(str):
            pass

        v[Label("alignment")] = v.pop("alignment")
    with pytest.raises(c.ConformanceError):
        c._fixture(v)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "page_bool",
        "page_size",
        "mutable_page",
        "extra_page",
        "gpr_bool",
        "gpr_wrap",
        "gpr_extra",
        "gpr_key",
        "xmm_bool",
        "xmm_wrap",
        "xmm_missing",
        "flags",
        "return",
        "caller",
        "capacity",
        "ignored_parameter",
        "ancestor",
        "feature",
        "iat",
        "old",
        "profile_relabel",
    ),
)
def test_fixture_exact_types_geometry_and_recipe_bytes(kind):
    v = all_vectors()[-1]
    f = independent_fixture(v)
    g = f["registers"]["esp"]
    if kind == "extra":
        f["extra"] = 0
    elif kind == "page_bool":
        f["pages"][False] = f["pages"].pop(0)
    elif kind == "page_size":
        f["pages"][0] = bytes(4095)
    elif kind == "mutable_page":
        f["pages"][0] = bytearray(f["pages"][0])
    elif kind == "extra_page":
        f["pages"][0x20000000] = bytes(4096)
    elif kind == "gpr_bool":
        f["registers"]["eax"] = True
    elif kind == "gpr_wrap":
        f["registers"]["eax"] = 2**32
    elif kind == "gpr_extra":
        f["registers"]["other"] = 0
    elif kind == "gpr_key":

        class Label(str):
            pass

        f["registers"][Label("eax")] = f["registers"].pop("eax")
    elif kind == "xmm_bool":
        f["xmm"]["xmm0"] = False
    elif kind == "xmm_wrap":
        f["xmm"]["xmm0"] = 2**128
    elif kind == "xmm_missing":
        f["xmm"].pop("xmm7")
    elif kind == "flags":
        f["entry_flags"] = 0x646
    elif kind == "return":
        f["return_address"] += 1
    elif kind == "profile_relabel":
        f = independent_fixture(dict(v, profile=0))
    else:
        addresses = dict(
            caller=g,
            capacity=g + 12,
            ignored_parameter=g + 16,
            ancestor=g + 20,
            feature=0x00893001,
            iat=0x007D6000,
            old=0x0600280F,
        )
        at = addresses[kind]
        install(f["pages"], at, word(f["pages"], at) ^ 1)
    with pytest.raises(c.ConformanceError, match="fixture recipe"):
        c._expected(v, f)


@pytest.mark.parametrize(
    "kind",
    (
        "register",
        "flag",
        "stack",
        "error",
        "event",
        "stop",
        "protocol",
        "bool",
        "extra",
        "coordinated",
    ),
)
def test_complete_free_child_packet_rejects_forgeries(monkeypatch, kind):
    v = all_vectors()[-1]
    f = independent_fixture(v)
    original = c.deallocator._expected

    def forged(*args, **kwargs):
        packet = copy.deepcopy(original(*args, **kwargs))
        if kind == "register":
            packet["registers"]["edx"] ^= 1
        elif kind == "flag":
            packet["flags"] ^= 1
        elif kind == "stack":
            packet["stack"] = bytes([packet["stack"][0] ^ 1]) + packet["stack"][1:]
        elif kind == "error":
            packet["error"] = bytes([packet["error"][0] ^ 1]) + packet["error"][1:]
        elif kind == "event":
            packet["events"][0]["value"] ^= 1
        elif kind == "stop":
            packet["stop"] ^= 1
        elif kind == "protocol":
            packet["protocol"]["result"] = 0
        elif kind == "bool":
            packet["registers"]["eax"] = True
        elif kind == "extra":
            packet["extra"] = 0
        else:
            packet["registers"]["eax"] = 0
            packet["protocol"]["result"] = 0
            packet["events"].append(
                dict(access="write", address=0x0600280F, width=4, value=0)
            )
        return packet

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.ConformanceError, match="free primitive"):
        c._expected(v, f)


def test_free_installed_continuation_is_bound_after_canonical_primitive_join():
    v = all_vectors()[-1]
    f = independent_fixture(v)
    wanted = independent(v, f)
    entry = wanted["free_entry"]
    pages = dict(entry["pages"])
    install(pages, entry["registers"]["esp"], 0x00657406)
    with pytest.raises(c.ConformanceError, match="installed continuation"):
        c._free_packet_law(dict(entry["registers"]), pages, wanted["path"]["begin"])


def source_paths():
    names = dict(
        program_facts="program_facts",
        movement_binding="native_movement_effect_binding",
        free_composition="native_vector_deallocation_composition",
        free_conformance="native_vector_deallocation_conformance_joined",
        cookie_return="native_lua_class_vector_return_conformance",
    )
    return {k: PROGRAMS / (PREFIX + name + ".json") for k, name in names.items()}


def sources():
    return {k: json.loads(p.read_bytes()) for k, p in source_paths().items()}


@pytest.mark.parametrize("key", tuple(source_paths()))
def test_all5_source_pin_errors_normalize_to_declared_error(key):
    supplied = sources()
    supplied[key]["analysis_kind"] = "forged"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("key", tuple(source_paths()))
def test_full_source_build_identity_survives_a_faulty_pin_facade(monkeypatch, key):
    supplied = sources()
    identity_key = "identity" if key == "program_facts" else "build_identity"
    supplied[key][identity_key]["executable_sha256"] = "0" * 64
    monkeypatch.setattr(
        c.common,
        "_source_identity",
        lambda value, kind, digest, label: dict(
            analysis_kind=kind, canonical_sha256=digest
        ),
    )
    with pytest.raises(c.ConformanceError, match="source build"):
        c._preflight(supplied)


def test_runner_exposes_only_postcheck_capture_and_no_fixture_override():
    parameters = inspect.signature(c._run_case).parameters
    assert list(parameters) == ["codes", "points", "vector", "negative", "capture"]
    assert parameters["capture"].kind is inspect.Parameter.KEYWORD_ONLY


def test_source_and_direct_code_packets_have_no_numeric_or_mapping_facades():
    supplied = sources()
    assert len(c.SOURCE_PINS) == 5
    with pytest.raises(c.ConformanceError):
        c._preflight(UserDict(supplied))
    points = c._source_points(supplied)
    assert canonical_hash(points) == POINT_SHA and len(points) == 128
    zero_codes = {a: bytes(b - a) for a, b in BODY_RANGES}
    with pytest.raises(c.ConformanceError, match="instruction bytes"):
        c._checked_code_packet(zero_codes, points)

    class Address(int):
        pass

    invalid = {Address(k): v for k, v in zero_codes.items()}
    with pytest.raises(c.ConformanceError, match="direct code identity"):
        c._checked_code_packet(invalid, points)
    for bad in (points[:-1], points + [points[0]], UserDict({"points": points})):
        with pytest.raises(c.ConformanceError):
            c._checked_code_packet(zero_codes, bad)


def quiet_environment():
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    return environment


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE for reviewed isolated native workers")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=1800,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b"" and result.stderr == b""


@pytest.mark.parametrize("index", SELECTED)
def test_actual_single_uc_trace_events_full_pages_boundaries_and_abi(index):
    isolated("packet", index)


def test_all40_native_controls_reject_with_their_intended_reason():
    isolated("controls")


def test_direct_runner_rejects_changed_code_and_metadata_before_machine_creation():
    isolated("code")


def native_code():
    data, image, sha = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert sha == "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    return c._load_code(data, image, sources())


def validate_actual_boundary(row, name, wanted):
    assert set(row) == {
        "name",
        "registers",
        "xmm",
        "eflags",
        "flags",
        "flag_mask",
        "df",
        "endpoint",
        "pages_sha256",
        "events_sha256",
    }
    assert row["name"] == name
    for key in ("registers", "xmm", "flags", "flag_mask", "df", "endpoint"):
        strict_equal(row[key], wanted[key])
    assert type(row["eflags"]) is int and 0 <= row["eflags"] < 2**32
    assert (
        row["eflags"] & wanted["flag_mask"] == wanted["flags"]
        and row["eflags"] & 0x400 == 0
    )
    assert row["eflags"] & 2 and not row["eflags"] & ~0xAD7
    assert row["pages_sha256"] == page_hashes(wanted["pages"])
    assert row["events_sha256"] == canonical_hash(wanted["events"])


def worker_packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_code()
    vector = all_vectors()[index]
    fixture = independent_fixture(vector)
    wanted = independent(vector, fixture)
    observed_trace, observed_events, instances, captured = [], [], [], []
    original_uc = uc.Uc

    def tracked_uc(*args, **kwargs):
        machine = original_uc(*args, **kwargs)
        instances.append(machine)

        def trace_hook(m, address, size, user):
            if address not in (0x04000000, 0x05000000):
                observed_trace.append(f"0x{address-0x00400000:08x}")

        def memory_hook(m, access, address, width, value, user):
            writing = access == uc.UC_MEM_WRITE
            observed_events.append(
                dict(
                    access="write" if writing else "read",
                    address=address,
                    width=width,
                    value=(
                        value & 0xFFFFFFFF
                        if writing
                        else int.from_bytes(m.mem_read(address, width), "little")
                    ),
                )
            )

        original_set_cpu = machine.ctl_set_cpu_model

        def set_cpu_and_observe(cpu_model):
            assert cpu_model == 19
            original_set_cpu(cpu_model)
            machine.hook_add(uc.UC_HOOK_CODE, trace_hook)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory_hook)

        # Installing hooks initializes Unicorn's CPU and locks its model.
        # Observe after selection, before mapping or executing selected code.
        machine.ctl_set_cpu_model = set_cpu_and_observe
        return machine

    uc.Uc = tracked_uc

    def capture(machine, ids, expected, supplied):
        strict_equal(expected, wanted)
        strict_equal(supplied, fixture)
        assert machine is instances[0]
        assert {r: machine.reg_read(ids[r]) for r in GPR} == wanted["registers"]
        assert {
            r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper())) for r in XMM
        } == wanted["xmm"]
        assert machine.reg_read(x.UC_X86_REG_EFLAGS) == 0x246
        assert machine.reg_read(x.UC_X86_REG_EIP) == 0x04000000
        actual_pages = {p: bytes(machine.mem_read(p, 4096)) for p in PAGE_ORDER}
        strict_equal(actual_pages, wanted["pages"])
        strict_equal(observed_trace, wanted["trace_rvas"])
        strict_equal(observed_events, wanted["events"])
        expected["events"].clear()
        supplied["pages"].clear()
        captured.append(True)

    observation = c._run_case(codes, points, vector, capture=capture)
    assert len(instances) == 1 and captured == [True]
    assert set(observation) == OBSERVATION_KEYS and len(observation) == 12
    for key in ("registers", "xmm", "flags", "flag_mask", "df", "trace_rvas"):
        strict_equal(observation[key], wanted[key])
    assert observation["vector"] == vector
    assert observation["events_sha256"] == canonical_hash(wanted["events"])
    assert observation["pages_sha256"] == page_hashes(wanted["pages"])
    assert observation["memory_event_count"] == len(wanted["events"])
    names = (
        ["cookie_entry"]
        if vector["path_form"] == "null"
        else ["free_entry", "free_return", "cookie_entry"]
    )
    assert [b["name"] for b in observation["boundaries"]] == names
    for row, name in zip(observation["boundaries"], names):
        validate_actual_boundary(row, name, wanted[name])
    assert len(observation["summaries"]) == int(vector["path_form"] != "null")
    if wanted["imported"] is not None:
        row = observation["summaries"][0]
        expected = wanted["imported"]
        assert set(row) == {
            "role",
            "entry_esp",
            "words",
            "registers",
            "xmm",
            "eflags",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
            "pages_sha256",
            "events_sha256",
        }
        assert (
            row["role"] == "free"
            and row["entry_esp"] == expected["entry_esp"]
            and row["words"] == expected["words"]
        )
        adapted = {k: row[k] for k in row if k not in ("role", "entry_esp", "words")}
        adapted["name"] = "imported"
        validate_actual_boundary(adapted, "imported", expected)
        assert row["eflags"] == 0x202 | expected["flags"]


def worker_controls():
    codes, points = native_code()
    assert c.CONTROLS == CONTROLS and len(CONTROLS) == 40
    for name, reason in CONTROLS.items():
        try:
            c._run_case(codes, points, all_vectors()[-1], name)
        except c.ConformanceError as exc:
            assert str(exc) == reason, (name, str(exc), reason)
        else:
            raise AssertionError("control survived: " + name)


def worker_code():
    import unicorn as uc

    codes, points = native_code()
    original_uc = uc.Uc
    instances = []

    def counted(*args, **kwargs):
        instances.append(True)
        return original_uc(*args, **kwargs)

    uc.Uc = counted
    for kind in ("bytes", "refreshed_point", "key", "extra", "size", "negative"):
        changed, packet = dict(codes), copy.deepcopy(points)
        control = None
        if kind in ("bytes", "refreshed_point"):
            first = min(changed)
            b = bytearray(changed[first])
            b[0] ^= 1
            changed[first] = bytes(b)
            if kind == "refreshed_point":
                packet[0]["sha256"] = hashlib.sha256(
                    changed[first][: packet[0]["size"]]
                ).hexdigest()
        elif kind == "key":

            class Address(int):
                pass

            changed = {Address(k): v for k, v in changed.items()}
        elif kind == "extra":
            changed[0x257427] = bytes([0x90])
        elif kind == "size":
            changed[0x7800] = changed[0x7800][:-1]
        else:
            control = False
        try:
            c._run_case(changed, packet, all_vectors()[0], control)
        except c.ConformanceError:
            pass
        else:
            raise AssertionError("direct code forgery survived: " + kind)
    assert instances == []


@pytest.fixture
def receipt():
    return json.loads(EVIDENCE.read_bytes())


def test_receipt_exact_seal_source_ranges_native_totals_and_exclusions(receipt, cases):
    assert c.SEALED_SHA256 != "PENDING" and canonical_hash(receipt) == c.SEALED_SHA256
    assert (
        EVIDENCE.read_bytes() == c.encode_conformance(receipt).encode("utf-8")
        and b"\r" not in EVIDENCE.read_bytes()
    )
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == all_vectors()
    assert canonical_hash(receipt["body"]["points"]) == POINT_SHA
    assert len(receipt["body"]["points"]) == 128
    assert [
        (int(r["start_rva"], 16), int(r["exclusive_end_rva"], 16))
        for r in receipt["body"]["ranges"]
    ] == list(BODY_RANGES)
    executed = sorted({r for v, f, w in cases for r in w["trace_rvas"]})
    assert receipt["executed_rvas"] == executed and len(executed) == 82
    assert {r["name"]: r["reason"] for r in receipt["negative_controls"]} == CONTROLS
    assert all(r["rejected"] is True for r in receipt["negative_controls"])
    counts = dict(
        cases=144,
        null_cases=48,
        owned_cases=96,
        loaded_sites=128,
        loaded_bytes=401,
        executed_sites=82,
        native_instructions=48 * 42 + 96 * 82,
        memory_events=48 * 25 + 96 * 50,
        free_requests=96,
        allocation_requests=0,
        old_bytes_preserved=144 * 8,
        xmm_preserved_cases=144,
        parameter_word_reads=0,
        effect_record_sites=0,
        controls=40,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    strict_equal(receipt["summary"], counts)
    assert receipt["engine"] == dict(
        name="Unicorn",
        version="2.1.4",
        architecture="x86_32",
        cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
    )
    assert set(receipt["source_receipts"]) == set(source_paths()) == set(c.SOURCE_PINS)
    assert all(not (0x25738A <= int(pc, 16) < 0x2573F0) for pc in executed)
    assert len(receipt["observations_sha256"]) == 64
    before = copy.deepcopy(receipt)
    checked = c.validate_structure(receipt, sources())
    checked["summary"].clear()
    strict_equal(receipt, before)


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool",
        "vector",
        "point",
        "range",
        "control",
        "observations",
        "pins",
        "scope",
    ),
)
def test_forged_receipt_is_not_resealed_by_refreshed_encoding(receipt, kind):
    forged = copy.deepcopy(receipt)
    if kind == "summary":
        forged["summary"]["free_requests"] += 1
    elif kind == "bool":
        forged["summary"]["allocation_requests"] = False
    elif kind == "vector":
        forged["vectors"][0]["path_form"] = "one"
    elif kind == "point":
        forged["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        forged["body"]["ranges"][0]["exclusive_end_rva"] = "0xffffffff"
    elif kind == "control":
        forged["negative_controls"][0]["rejected"] = False
    elif kind == "observations":
        forged["observations_sha256"] = "0" * 64
    elif kind == "pins":
        forged["source_receipts"].clear()
    else:
        forged["scope"]["claim"] = "pawn movement proved"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(forged, sources())


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_structure(receipt, command):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE for exact native CLI")
    arguments = [
        sys.executable,
        str(ROOT / "scripts/itb_native_movement_addmove_early_return_conformance.py"),
        command,
    ]
    for key, path in source_paths().items():
        arguments += ["--" + key.replace("_", "-"), str(path)]
    if command != "build":
        arguments += ["--evidence", str(EVIDENCE)]
    if command != "verify-structure":
        arguments += ["--executable", str(Path(executable))]
    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, env=quiet_environment(), timeout=1800
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    if command == "build":
        assert result.stdout == EVIDENCE.read_bytes()
    else:
        parsed = json.loads(result.stdout)
        assert parsed["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert parsed["evidence_sha256"] == c.SEALED_SHA256
        strict_equal(parsed["summary"], receipt["summary"])
        assert result.stdout == c.encode_conformance(parsed).encode("utf-8")


@pytest.mark.parametrize("kind", ("crlf", "duplicate_key", "changed_source"))
def test_structure_cli_rejects_encoding_and_source_changes(receipt, tmp_path, kind):
    raw = c.encode_conformance(receipt).encode("utf-8")
    if kind == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif kind == "duplicate_key":
        raw = raw.replace(b"{\n", b'{\n  "schema_version": 1,\n', 1)
    evidence_path = tmp_path / "receipt.json"
    evidence_path.write_bytes(raw)
    paths = source_paths()
    if kind == "changed_source":
        supplied = sources()["movement_binding"]
        supplied["scope"]["runtime_registration"] = True
        changed = tmp_path / "source.json"
        changed.write_text(json.dumps(supplied), encoding="utf-8")
        paths["movement_binding"] = changed
    arguments = [
        sys.executable,
        str(ROOT / "scripts/itb_native_movement_addmove_early_return_conformance.py"),
        "verify-structure",
        "--evidence",
        str(evidence_path),
    ]
    for key, path in paths.items():
        arguments += ["--" + key.replace("_", "-"), str(path)]
    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, env=quiet_environment(), timeout=1800
    )
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr.startswith(b"error:")


if __name__ == "__main__":
    faulthandler.disable()
    action, index = sys.argv[1], int(sys.argv[2])
    if action == "packet":
        worker_packet(index)
    elif action == "controls":
        worker_controls()
    elif action == "code":
        worker_code()
    else:
        raise SystemExit("unknown worker")
