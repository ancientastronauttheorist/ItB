"""Handwritten successful resize6->9 page, event and boundary equations.

Source-only test support; it does not import a production oracle or execute code.
"""

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
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_simd_vector_resize6_to9_conformance as c
from tests.test_itb_native_installed_simd_copy48_conformance import TRACE as COPY_TRACE

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
H, HEAP = 0x0FFFFFD0, 0x12345678
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT = 0x008B7634, 0x007D6220, 0x007D621C
ALLOCATION_TRACE = (
    0x8A920,
    0x8A921,
    0x8A923,
    0x8A926,
    0x8A928,
    0x8A932,
    0x8A937,
    0x8A939,
    0x8A93C,
    0x8A941,
    0x8A962,
    0x8A963,
    0x3574DB,
    0x3574DC,
    0x3574DE,
    0x3574FF,
    0x357502,
    0x379F52,
    0x379F54,
    0x379F55,
    0x379F57,
    0x379F58,
    0x38942B,
    0x38942D,
    0x38942E,
    0x389430,
    0x389431,
    0x389434,
    0x389437,
    0x389439,
    0x38943B,
    0x389454,
    0x389455,
    0x389457,
    0x38945D,
    0x389463,
    0x389465,
    0x389467,
    0x389476,
    0x389477,
    0x389478,
    0x357507,
    0x357508,
    0x35750A,
    0x35750C,
    0x35750D,
    0x8A968,
    0x8A96B,
    0x8A96D,
    0x8A96E,
)
FREE_TRACE = (
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
)
TRACE = (
    (
        0x2EB680,
        0x2EB681,
        0x2EB683,
        0x2EB684,
        0x2EB687,
        0x2EB688,
        0x2EB689,
        0x2EB68A,
        0x2EB68B,
        0x2EB68D,
        0x2EB690,
    )
    + ALLOCATION_TRACE
    + (0x2EB695, 0x2EB697, 0x2EB699, 0x2EB69C, 0x2EB69E, 0x2EB69F, 0x2EB6A0, 0x2EB6A1)
    + COPY_TRACE
    + (
        0x2EB6A6,
        0x2EB6A8,
        0x2EB6AB,
        0x2EB6AE,
        0x2EB6B0,
        0x2EB6B3,
        0x2EB6B5,
        0x2EB6B7,
        0x2EB6BA,
        0x2EB6BC,
        0x2EB6BE,
        0x2EB6C1,
        0x2EB6C2,
        0x2EB6C3,
    )
    + FREE_TRACE
    + (
        0x2EB6C8,
        0x2EB6CB,
        0x2EB6CE,
        0x2EB6D1,
        0x2EB6D4,
        0x2EB6D7,
        0x2EB6DA,
        0x2EB6DC,
        0x2EB6DD,
        0x2EB6DE,
        0x2EB6DF,
        0x2EB6E1,
        0x2EB6E2,
    )
)


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def add_flags(left, right):
    total = left + right
    result = total & 0xFFFFFFFF
    return (
        int(total > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int((left & 15) + (right & 15) > 15) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((~(left ^ right) & (left ^ result)) & 0x80000000)) << 11)
    )


def independent(*, pages, registers, xmm, source, destination, return_address):
    """Predict all writes/events from an already installed, complete fixture."""
    original, output = copy.deepcopy(pages), copy.deepcopy(pages)
    r, o, d = registers["esp"], source, destination
    snapshot = blob(original, o, 48)
    events, boundaries = [], {}

    def event(access, address, value, width=4):
        row = dict(access=access, address=address, width=width, value=value)
        events.append(row)
        if access == "write":
            for i, byte in enumerate(value.to_bytes(width, "little")):
                page = (address + i) & ~4095
                data = bytearray(output[page])
                data[(address + i) & 4095] = byte
                output[page] = bytes(data)
        else:
            assert int.from_bytes(blob(output, address, width), "little") == value

    w = lambda address, value: event("write", address, value)
    rd = lambda address, value: event("read", address, value)

    def boundary(name, regs, endpoint, flags, mask, xmms):
        boundaries[name] = dict(
            registers=copy.deepcopy(regs),
            xmm=copy.deepcopy(xmms),
            pages=copy.deepcopy(output),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    assert [int.from_bytes(blob(original, H + i, 4), "little") for i in (0, 4, 8)] == [
        o,
        o + 48,
        o + 48,
    ]
    assert [int.from_bytes(blob(original, r + i, 4), "little") for i in (0, 4)] == [
        return_address,
        9,
    ]
    for address, value in ((r - 4, registers["ebp"]), (r - 8, H)):
        w(address, value)
    rd(r + 4, 9)
    for address, value in (
        (r - 12, registers["ebx"]),
        (r - 16, registers["esi"]),
        (r - 20, registers["edi"]),
        (r - 24, 9),
        (r - 8, 9),
        (r - 28, 0x006EB695),
    ):
        w(address, value)
    allocated_entry = dict(registers, eax=9, esi=H, ebp=r - 4, esp=r - 28)
    boundary("allocation_entry", allocated_entry, 0x0048A920, 0x246, 0xFFFFFFFF, xmm)
    a = r - 28
    # Ordinary allocation: requested count9, bytes72, no pointer metadata.
    w(a - 4, r - 4)
    rd(a + 4, 9)
    for address, value in ((a - 8, 72), (a - 12, 0x0048A968), (a - 16, a - 4)):
        w(address, value)
    rd(a - 8, 72)
    for address, value in ((a - 20, 72), (a - 24, 0x00757507), (a - 28, a - 16)):
        w(address, value)
    rd(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, H)
    rd(a - 20, 72)
    w(a - 36, 72)
    w(a - 40, 0)
    rd(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    alloc_target = int.from_bytes(blob(output, ALLOC_IAT, 4), "little")
    rd(ALLOC_IAT, alloc_target)
    w(a - 48, 0x00789463)
    allocation_request = dict(
        entry_esp=r - 76, words=[0x00789463, HEAP, 0, 72], target=alloc_target
    )
    for address, value in (
        (a - 32, H),
        (a - 28, a - 16),
        (a - 24, 0x00757507),
        (a - 20, 72),
        (a - 16, a - 4),
        (a - 12, 0x0048A968),
        (a - 4, r - 4),
        (a, 0x006EB695),
    ):
        rd(address, value)
    allocated_return = dict(allocated_entry, eax=d, ecx=d, edx=0xB0000001, esp=r - 20)
    boundary(
        "allocation_return",
        allocated_return,
        0x006EB695,
        add_flags(a - 8, 4),
        0x8D5,
        xmm,
    )
    rd(H, o)
    rd(H + 4, o + 48)
    for address, value in (
        (r - 24, 48),
        (r - 28, o),
        (r - 32, d),
        (r - 36, 0x006EB6A6),
    ):
        w(address, value)
    copy_entry = dict(allocated_return, eax=d, ecx=48, edx=o, edi=d, esp=r - 36)
    # SUB ECX,EDX gives48; its independently defined result has PF1 only.
    boundary("copy_entry", copy_entry, 0x0076E580, 4, 0x8D5, xmm)
    c = r - 36
    w(c - 4, d)
    w(c - 8, H)
    rd(c + 8, o)
    rd(c + 12, 48)
    rd(c + 4, d)
    rd(0x00893F30, 0x93939393)
    for access, address in (("read", o), ("write", d)):
        for offset in (0, 8, 16, 24):
            event(
                access,
                address + offset,
                int.from_bytes(snapshot[offset : offset + 8], "little"),
                8,
            )
    for offset in (32, 36, 40, 44):
        value = int.from_bytes(snapshot[offset : offset + 4], "little")
        rd(o + offset, value)
        w(d + offset, value)
    for address, value in ((c + 4, d), (c - 8, H), (c - 4, d), (c, 0x006EB6A6)):
        rd(address, value)
    copied_xmm = dict(
        xmm,
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:32], "little"),
    )
    copied_return = dict(
        copy_entry,
        eax=d,
        ecx=0,
        edx=int.from_bytes(snapshot[44:48], "little"),
        esp=r - 32,
    )
    boundary("copy_return", copied_return, 0x006EB6A6, 0x44, 0x8C5, copied_xmm)
    rd(H, o)
    rd(H + 4, o + 48)
    rd(H + 8, o + 48)
    for address, value in ((r - 24, 8), (r - 28, 6), (r - 32, o), (r - 36, 0x006EB6C8)):
        w(address, value)
    free_entry = dict(copied_return, eax=6, ebx=6, ecx=o, esp=r - 36)
    # SAR count3 leaves AF/OF unclaimed; only CF/PF/ZF/SF are defined.
    boundary("free_entry", free_entry, 0x00407800, 4, 0xC5, copied_xmm)
    f = r - 36
    # Successful ordinary guard: two stride reads, no raw-pointer metadata.
    w(f - 4, r - 4)
    rd(f + 8, 6)
    rd(f + 12, 8)
    rd(f + 12, 8)
    rd(f + 4, o)
    w(f - 8, o)
    w(f - 12, 0x00407856)
    inner = f - 12
    w(inner - 4, f - 4)
    rd(inner + 4, o)
    rd(inner + 4, o)
    w(inner - 8, o)
    w(inner - 12, 0)
    rd(HEAP_GLOBAL, HEAP)
    w(inner - 16, HEAP)
    free_target = int.from_bytes(blob(output, FREE_IAT, 4), "little")
    rd(FREE_IAT, free_target)
    w(inner - 20, 0x00789172)
    free_request = dict(
        entry_esp=r - 68, words=[0x00789172, HEAP, 0, o], target=free_target
    )
    for address, value in (
        (inner - 4, f - 4),
        (inner, 0x00407856),
        (f - 4, r - 4),
        (f, 0x006EB6C8),
    ):
        rd(address, value)
    freed_return = dict(free_entry, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=f + 4)
    boundary(
        "free_return", freed_return, 0x006EB6C8, add_flags(f - 8, 4), 0x8D5, copied_xmm
    )
    rd(r - 8, 9)
    for address, value in ((H + 8, d + 72), (H + 4, d + 48), (H, d)):
        w(address, value)
    for address, value in (
        (r - 20, registers["edi"]),
        (r - 16, registers["esi"]),
        (r - 12, registers["ebx"]),
        (r - 4, registers["ebp"]),
        (r, return_address),
    ):
        rd(address, value)
    assert len(events) == 104
    return dict(
        pages=output,
        events=events,
        source_snapshot=snapshot,
        registers=dict(
            registers, eax=d + 48, ecx=0xA0000001, edx=0xB0000001, esp=r + 8
        ),
        xmm=copied_xmm,
        flags=add_flags(r - 32, 12),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        boundaries=boundaries,
        allocation_request=allocation_request,
        free_request=free_request,
        stack_extent=[r - 76, r + 8],
    )


def wanted_fixture(vector, fixture):
    a = vector["alignment"]
    return independent(
        pages=fixture["pages"],
        registers=fixture["registers"],
        xmm=fixture["xmm"],
        source=0x06002800 + a,
        destination=0x06004800 + a,
        return_address=fixture["return_address"],
    )


def canonical_hash(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
    ).hexdigest()


def page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def check_expected(vector, fixture, result, wanted):
    assert set(result) == {
        "geometry",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "events",
        "pages",
        "endpoint",
        "allocation_entry",
        "allocation_packet",
        "copy_entry",
        "copy_packet",
        "free_entry",
        "free_packet",
        "allocation_request",
        "free_request",
        "trace_rvas",
    }
    for key in (
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "events",
        "pages",
        "endpoint",
    ):
        assert result[key] == wanted[key], key
    assert result["allocation_entry"] == wanted["boundaries"]["allocation_entry"]
    assert result["copy_entry"] == wanted["boundaries"]["copy_entry"]
    assert result["free_entry"] == wanted["boundaries"]["free_entry"]
    a = vector["alignment"]
    o, d = 0x06002800 + a, 0x06004800 + a
    assert result["geometry"] == dict(
        old_begin=o,
        old_end=o + 48,
        old_capacity=o + 48,
        new_begin=d,
        new_end=d + 48,
        new_capacity=d + 72,
        copy_bytes=48,
        request=72,
        old_size=6,
        requested=9,
    )
    allocated = wanted["boundaries"]["allocation_return"]
    assert result["allocation_packet"] == dict(
        relation=dict(result=d, request=72, metadata=None),
        registers=allocated["registers"],
        flags=allocated["flags"],
        flag_mask=0x8D5,
        stack=blob(allocated["pages"], 0x30000000, 8192),
        payload=fixture["pages"][0x06004000],
        events=wanted["events"][9:36],
    )
    copied = wanted["boundaries"]["copy_return"]
    assert set(result["copy_packet"]) == {
        "pages",
        "source_snapshot",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "endpoint",
        "trace_rvas",
        "events",
    }
    for key in ("pages", "registers", "xmm", "flags", "flag_mask", "df", "endpoint"):
        assert result["copy_packet"][key] == copied[key], key
    assert result["copy_packet"]["source_snapshot"] == wanted["source_snapshot"]
    assert result["copy_packet"]["events"] == wanted["events"][42:68]
    freed = wanted["boundaries"]["free_return"]
    assert result["free_packet"] == dict(
        registers=freed["registers"],
        flags=freed["flags"],
        flag_mask=0x8D5,
        events=wanted["events"][75:95],
        stack=blob(freed["pages"], 0x30000000, 8192),
        error=fixture["pages"][0x06000000],
        stop=0x006EB6C8,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    assert result["allocation_request"] == dict(
        continuation=0x00789463, handle=HEAP, flags=0, bytes=72
    )
    assert result["free_request"] == dict(
        continuation=0x00789172, handle=HEAP, flags=0, pointer=o
    )
    assert [
        row
        for row in result["events"]
        if row["access"] == "write" and H <= row["address"] < H + 12
    ] == [
        dict(access="write", address=H + 8, width=4, value=d + 72),
        dict(access="write", address=H + 4, width=4, value=d + 48),
        dict(access="write", address=H, width=4, value=d),
    ]
    assert blob(result["pages"], d + 48, 24) == blob(fixture["pages"], d + 48, 24)
    assert blob(result["pages"], o, 48) == wanted["source_snapshot"]
    assert len(result["events"]) == 104
    assert result["trace_rvas"] == [f"0x{pc:08x}" for pc in TRACE]
    assert result["copy_packet"]["trace_rvas"] == [f"0x{pc:08x}" for pc in COPY_TRACE]


def test_exact_coupled_matrix_and_frame_geometry():
    assert c.vectors() == [
        dict(alignment=a, profile=p) for a in range(16) for p in range(3)
    ]
    for vector in c.vectors():
        fixture = c._fixture(vector)
        assert set(fixture) == {
            "pages",
            "registers",
            "xmm",
            "return_address",
            "entry_flags",
        }
        assert set(fixture["pages"]) == {
            0x06000000,
            0x06002000,
            0x06003000,
            0x06004000,
            0x0FFFF000,
            0x30000000,
            0x30001000,
            0x00893000,
            0x008B7000,
            0x007D6000,
        }
        a, r = vector["alignment"], fixture["registers"]["esp"]
        assert r == 0x30001000 + a and fixture["registers"]["ecx"] == H
        assert (
            fixture["return_address"] == 0x04000000 and fixture["entry_flags"] == 0x246
        )
        assert c.frame_join(r) == dict(
            protected_start=r - 76,
            protected_end=r + 8,
            allocation=r - 28,
            heap_allocate=r - 76,
            copy=r - 36,
            deallocation=r - 36,
            heap_free=r - 68,
            returned=r + 8,
        )


@pytest.mark.parametrize("alignment", range(16))
def test_all_profiles_full_independent_resize_law(alignment):
    for profile in range(3):
        vector = dict(alignment=alignment, profile=profile)
        fixture = c._fixture(vector)
        before = copy.deepcopy(fixture)
        wanted = wanted_fixture(vector, fixture)
        result = c._expected(vector, fixture)
        check_expected(vector, fixture, result, wanted)
        assert fixture == before
        result["registers"]["eax"] ^= 1
        result["xmm"]["xmm7"] ^= 1
        result["events"][0]["value"] ^= 1
        assert fixture == before


@pytest.mark.parametrize("field", ("alignment", "profile"))
@pytest.mark.parametrize("value", (False, True, -1, 16, 2**32, 1.0, None))
def test_vector_words_are_strict(field, value):
    vector = dict(alignment=7, profile=2)
    vector[field] = value
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "bool_gpr",
        "bool_xmm",
        "mutable_page",
        "missing_page",
        "old_header",
        "source",
        "spare",
        "ancestor",
        "feature",
        "iat",
        "heap",
        "return",
        "request",
        "entry_flags",
    ),
)
def test_finite_fixture_rejects_typed_relabeling(kind):
    vector = dict(alignment=15, profile=2)
    fixture = c._fixture(vector)
    if kind == "extra":
        fixture["unused"] = 0
    elif kind == "missing":
        fixture.pop("xmm")
    elif kind == "bool_gpr":
        fixture["registers"]["eax"] = False
    elif kind == "bool_xmm":
        fixture["xmm"]["xmm0"] = False
    elif kind == "mutable_page":
        fixture["pages"][0x06004000] = bytearray(fixture["pages"][0x06004000])
    elif kind == "missing_page":
        fixture["pages"].pop(0x06003000)
    elif kind == "entry_flags":
        fixture["entry_flags"] ^= 0x10
    else:
        addresses = dict(
            old_header=H + 4,
            source=0x0600280F,
            spare=0x0600480F + 48,
            ancestor=0x3000100F + 8,
            feature=0x00893001,
            iat=ALLOC_IAT,
            heap=HEAP_GLOBAL,
            return_=0x3000100F,
            request=0x3000100F + 4,
        )
        at = addresses["return_" if kind == "return" else kind]
        page = at & ~4095
        data = bytearray(fixture["pages"][page])
        data[at & 4095] ^= 1
        fixture["pages"][page] = bytes(data)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "result_bool",
        "metadata_bool",
        "register_bool",
        "flags_bool",
        "payload",
        "event_bool",
        "event_extra",
        "canonical_actual",
    ),
)
def test_allocation_relocation_checks_all_seven_canonical_fields(monkeypatch, kind):
    vector = dict(alignment=15, profile=2)
    fixture = c._fixture(vector)
    original = c.allocator._expected
    observed = []

    def corrupted(v, *args, **kwargs):
        observed.append(copy.deepcopy(v))
        packet = original(v, *args, **kwargs)
        if kind == "extra":
            packet["unused"] = 0
        elif kind == "missing":
            packet.pop("flag_mask")
        elif kind == "result_bool":
            packet["relation"]["result"] = False
        elif kind == "metadata_bool":
            packet["relation"]["metadata"] = False
        elif kind == "register_bool":
            packet["registers"]["eax"] = False
        elif kind == "flags_bool":
            packet["flags"] = False
        elif kind == "payload":
            packet["payload"] = (
                bytes([packet["payload"][0] ^ 1]) + packet["payload"][1:]
            )
        elif kind == "event_bool":
            packet["events"][0]["width"] = True
        elif kind == "event_extra":
            packet["events"].append(copy.deepcopy(packet["events"][-1]))
        else:
            packet["relation"]["result"] = 0x0600480F
            packet["registers"].update(eax=0x0600480F, ecx=0x0600480F)
        return packet

    monkeypatch.setattr(c.allocator, "_expected", corrupted)
    with pytest.raises(c.ConformanceError, match="allocation primitive"):
        c._expected(vector, fixture)
    assert observed == [dict(count=9, pointer=0x0600080F)]


@pytest.mark.parametrize(
    "kind",
    ("edx32", "df_bool", "mask_bool", "xmm", "snapshot", "spare_page", "extra_event"),
)
def test_copy_join_rejects_stale32_and_coordinated_spare_corruption(monkeypatch, kind):
    vector = dict(alignment=7, profile=2)
    fixture = c._fixture(vector)
    original = c.copy_model.apply

    def corrupted(**kwargs):
        packet = original(**kwargs)
        if kind == "edx32":
            packet["registers"]["edx"] = 0
        elif kind == "df_bool":
            packet["df"] = False
        elif kind == "mask_bool":
            packet["flag_mask"] = True
        elif kind == "xmm":
            packet["xmm"]["xmm7"] ^= 1
        elif kind == "snapshot":
            packet["source_snapshot"] = (
                bytes([packet["source_snapshot"][0] ^ 1])
                + packet["source_snapshot"][1:]
            )
        elif kind == "spare_page":
            at = 0x06004807 + 48
            data = bytearray(packet["pages"][0x06004000])
            data[at & 4095] ^= 1
            packet["pages"][0x06004000] = bytes(data)
            packet["events"].append(
                dict(
                    access="write",
                    address=at,
                    width=4,
                    value=int.from_bytes(blob(packet["pages"], at, 4), "little"),
                )
            )
        else:
            packet["events"].append(copy.deepcopy(packet["events"][-1]))
        return packet

    monkeypatch.setattr(c.copy_model, "apply", corrupted)
    with pytest.raises(c.ConformanceError, match="copy primitive"):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    ("returned_int", "result_bool", "eax_bool", "error", "stack", "stop", "extra"),
)
def test_free_packet_checks_typed_protocol_and_all_eight_fields(monkeypatch, kind):
    vector = dict(alignment=7, profile=2)
    fixture = c._fixture(vector)
    original = c.deallocator._expected

    def corrupted(*args, **kwargs):
        packet = original(*args, **kwargs)
        if kind == "returned_int":
            packet["protocol"]["returned"] = 1
        elif kind == "result_bool":
            packet["protocol"]["result"] = True
        elif kind == "eax_bool":
            packet["registers"]["eax"] = True
        elif kind in ("error", "stack"):
            packet[kind] = bytes([packet[kind][0] ^ 1]) + packet[kind][1:]
        elif kind == "stop":
            packet["stop"] ^= 1
        else:
            packet["unused"] = 0
        return packet

    monkeypatch.setattr(c.deallocator, "_expected", corrupted)
    with pytest.raises(c.ConformanceError, match="free primitive"):
        c._expected(vector, fixture)


def sources():
    base = ROOT / "data/observatory/programs"
    return {
        key: json.loads(
            (
                base
                / (
                    "windows_build_13725832_31fe35265598_"
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ).read_text()
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.common.EXE_SHA256
    return c._load_code(data, image, sources())


def packet(alignment):
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = dict(alignment=alignment, profile=alignment % 3)
    fixture = c._fixture(vector)
    wanted = wanted_fixture(vector, fixture)
    captured = {}

    def capture(machine, ids, expected, installed):
        captured.update(
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            xmm={
                r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper())) for r in XMM
            },
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    observed = c._run_case(codes, points, vector, capture=capture)
    for key in ("registers", "xmm", "pages", "endpoint"):
        assert captured[key] == wanted[key], key
    assert (
        captured["flags"] & 0x8D5 == wanted["flags"] and captured["flags"] & 0x400 == 0
    )
    assert set(observed) == {
        "vector",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "trace_rvas",
        "events_sha256",
        "summaries",
        "boundaries",
        "pages_sha256",
        "memory_event_count",
    }
    for key in ("registers", "xmm", "flags", "flag_mask", "df"):
        assert observed[key] == wanted[key], key
    assert observed["vector"] == vector and observed["memory_event_count"] == 104
    assert observed["trace_rvas"] == [f"0x{pc:08x}" for pc in TRACE]
    assert observed["events_sha256"] == canonical_hash(wanted["events"])
    assert observed["pages_sha256"] == page_hashes(wanted["pages"])
    assert observed["summaries"] == [
        dict(
            role="allocation",
            entry_esp=wanted["allocation_request"]["entry_esp"],
            words=wanted["allocation_request"]["words"],
        ),
        dict(
            role="free",
            entry_esp=wanted["free_request"]["entry_esp"],
            words=wanted["free_request"]["words"],
        ),
    ]
    names = (
        "allocation_entry",
        "allocation_return",
        "copy_entry",
        "copy_return",
        "free_entry",
    )
    assert [b["name"] for b in observed["boundaries"]] == list(names)
    for actual, name in zip(observed["boundaries"], names):
        expected = wanted["boundaries"][name]
        assert set(actual) == {
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
        for key in ("registers", "xmm", "endpoint", "flags", "flag_mask", "df"):
            assert actual[key] == expected[key], (name, key)
        assert (
            type(actual["eflags"]) is int
            and actual["eflags"] & expected["flag_mask"] == expected["flags"]
            and actual["eflags"] & 0x400 == 0
        )
        assert actual["pages_sha256"] == page_hashes(expected["pages"])
        assert actual["events_sha256"] == canonical_hash(expected["events"])
    assert observed["boundaries"][3]["registers"]["edx"] == int.from_bytes(
        wanted["source_snapshot"][44:48], "little"
    )


def controls():
    codes, points = native_inputs()
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, dict(alignment=15, profile=2), kind)
        assert str(caught.value) == reason, kind


def code_tamper():
    codes, points = native_inputs()
    for kind in (
        "missing_body",
        "extra_body",
        "short_body",
        "point_bool",
        "point_extra",
        "point_missing",
        "coordinated_bytes",
    ):
        cc, pp = copy.deepcopy(codes), copy.deepcopy(points)
        name = next(iter(cc))
        point = pp[name][0]
        start = c.BODIES[name][0]
        if kind == "missing_body":
            cc.pop(name)
        elif kind == "extra_body":
            cc["unused"] = b"x"
        elif kind == "short_body":
            cc[name] = cc[name][:-1]
        elif kind == "point_bool":
            point["size"] = True
        elif kind == "point_extra":
            point["unused"] = 0
        elif kind == "point_missing":
            pp[name].pop()
        else:
            offset = int(point["rva"], 16) - start
            body = bytearray(cc[name])
            body[offset] ^= 1
            cc[name] = bytes(body)
            point["sha256"] = hashlib.sha256(
                cc[name][offset : offset + point["size"]]
            ).hexdigest()
        with pytest.raises(c.ConformanceError):
            c._checked_code_packet(cc, pp)


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed resize runtime")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    run = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=2400,
    )
    assert run.returncode == 0, (run.stdout + run.stderr).decode(
        "utf-8", errors="replace"
    )[-4000:]


@pytest.mark.parametrize("alignment", range(16))
def test_actual_boundaries_and_final_full_machine(alignment):
    isolated("packet", alignment)


def test_all_intended_native_controls():
    isolated("controls")


def test_direct_code_packet_schema_and_refreshed_byte_identity():
    isolated("code_tamper")


@pytest.mark.parametrize(
    "shape", ("missing", "extra", "list", "bool_document", "non_json")
)
def test_preflight_rejects_malformed_source_partition(shape):
    supplied = sources()
    if shape == "missing":
        supplied.pop("owner")
    elif shape == "extra":
        supplied["unused"] = {}
    elif shape == "list":
        supplied = list(supplied.items())
    elif shape == "bool_document":
        supplied["owner"] = False
    else:
        supplied["owner"]["unused"] = b"not JSON"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_preflight_checks_exact_all_source_identities():
    identities = c._preflight(sources())
    assert set(identities) == set(c.SOURCE_PINS)
    for key, (kind, digest) in c.SOURCE_PINS.items():
        assert identities[key] == dict(analysis_kind=kind, canonical_sha256=digest)
        supplied = sources()
        supplied[key]["analysis_kind"] = "forged"
        with pytest.raises(c.ConformanceError):
            c._preflight(supplied)


@pytest.mark.parametrize(
    "key",
    (
        "program_facts",
        "owner",
        "allocation_conformance",
        "deallocation_conformance",
        "installed_copy48",
    ),
)
def test_independent_build_check_rejects_disagreement_after_identity_facade(
    monkeypatch, key
):
    supplied = sources()
    identity = supplied[key]["identity" if key == "program_facts" else "build_identity"]
    identity["executable_sha256"] = "0" * 64
    # Exercise the independent build join even if a source-identity facade is faulty.
    monkeypatch.setattr(
        c.common,
        "_source_identity",
        lambda value, kind, digest, label: dict(
            analysis_kind=kind, canonical_sha256=digest
        ),
    )
    with pytest.raises(c.ConformanceError, match="source build"):
        c._preflight(supplied)


PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_simd_vector_resize6_to9_conformance.json")


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("primary has not published the resize6-to9 receipt")
    return json.loads(EVIDENCE.read_text())


def test_receipt_exact_encoding_source_anchor_and_independent_equations(receipt):
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert canonical_hash(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == [
        dict(alignment=a, profile=p) for a in range(16) for p in range(3)
    ]
    assert receipt["executed_rvas"] == [f"0x{pc:08x}" for pc in sorted(set(TRACE))]
    assert (
        canonical_hash(receipt["body"]["points"])
        == "3cdbf66fbd4a4624d94cfba3f07d625732512a97e8689b0e15ee30c410bc4660"
    )
    assert len(receipt["body"]["points"]) == 249
    assert {
        row["name"]: row["reason"] for row in receipt["negative_controls"]
    } == c.CONTROLS
    assert len(receipt["negative_controls"]) == len(c.CONTROLS)
    assert all(row["rejected"] is True for row in receipt["negative_controls"])
    assert set(receipt["source_receipts"]) == set(c.SOURCE_PINS)
    for key, value in dict(
        cases=48,
        loaded_sites=249,
        loaded_bytes=660,
        executed_sites=len(set(TRACE)),
        native_instructions=48 * len(TRACE),
        allocation_api_summaries=48,
        free_api_summaries=48,
        copied_bytes=48 * 48,
        allocated_bytes=72 * 48,
        spare_bytes=24 * 48,
        wide_reads=4 * 48,
        wide_writes=4 * 48,
        scalar_tail_reads=4 * 48,
        scalar_tail_writes=4 * 48,
        preserved_old_bytes=48 * 48,
        memory_events=104 * 48,
        controls=len(c.CONTROLS),
        accounting_promotions=0,
    ).items():
        assert (
            type(receipt["summary"][key]) is int and receipt["summary"][key] == value
        ), key
    assert all(
        pc not in receipt["executed_rvas"]
        for pc in (
            "0x0036ea9d",
            "0x0036ea9f",
            "0x0036eaa1",
            "0x0036eaa2",
            "0x0036eaa3",
            "0x0036eaa4",
        )
    )


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool_summary",
        "vector",
        "controls",
        "point",
        "range",
        "observation",
        "pin",
        "scope",
        "bytes_json",
    ),
)
def test_sealed_receipt_tampering_and_typed_json_reject(kind, receipt):
    value = copy.deepcopy(receipt)
    if kind == "summary":
        value["summary"]["copied_bytes"] += 1
    elif kind == "bool_summary":
        value["summary"]["accounting_promotions"] = False
    elif kind == "vector":
        value["vectors"][0]["alignment"] = True
    elif kind == "controls":
        value["negative_controls"][0]["rejected"] = 1
    elif kind == "point":
        value["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        value["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observation":
        value["observations_sha256"] = "0" * 64
    elif kind == "pin":
        value["source_receipts"]["owner"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        value["scope"]["checked"].append("forged ownership claim")
    else:
        value["unused"] = b"not JSON"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(value, sources())


def builder():
    actual = c.build_conformance(Path(os.environ["ITB_EXACT_EXE"]), sources())
    assert c.encode_conformance(actual).encode("utf-8") == EVIDENCE.read_bytes()


def cli(command):
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_simd_vector_resize6_to9_conformance.py"),
        command,
    ]
    for key, (kind, _) in c.SOURCE_PINS.items():
        path = PROGRAMS / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        args += ["--executable", os.environ["ITB_EXACT_EXE"]]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    run = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=2400)
    assert run.returncode == 0, run.stderr.decode("utf-8", errors="replace")[-4000:]
    assert run.stderr == b""
    if command == "build":
        assert run.stdout == EVIDENCE.read_bytes()
    else:
        value = json.loads(run.stdout)
        assert value["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert value["evidence_sha256"] == c.SEALED_SHA256
        assert run.stdout == c.encode_conformance(value).encode("utf-8")


def test_exact_native_builder_reproduces_receipt(receipt):
    isolated("builder")


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_serial_cli_commands(command, receipt):
    if command == "verify-structure":
        cli(command)
    else:
        isolated("cli", command)


if __name__ == "__main__":
    faulthandler.disable()
    if sys.argv[1] == "packet":
        packet(int(sys.argv[2]))
    elif sys.argv[1] == "code_tamper":
        code_tamper()
    elif sys.argv[1] == "builder":
        builder()
    elif sys.argv[1] == "cli":
        cli(sys.argv[2])
    else:
        controls()
