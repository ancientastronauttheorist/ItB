"""Finite native AddMove count-zero/one cleanup and normal caller return.

The selected path never constructs or appends an effect record. Successful
HeapFree is a supplied response premise, not an ownership or unmapping proof.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_effect_binding as binding
from src.observatory import native_vector_deallocation_composition as free_contract
from src.observatory import native_vector_deallocation_conformance_joined as deallocator
from src.observatory import native_lua_class_vector_return_conformance as cookie_witness
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_addmove_early_return_conformance"
SEALED_SHA256 = "c2448f75dc5c50f3e4de7f6bc0f412016cdb07bbe7becc491d5bd1b31f840079"
SOURCE_PINS = {
    "program_facts": binding.SOURCE_PINS["program_facts"],
    "movement_binding": (
        binding.ANALYSIS_KIND,
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
    "free_composition": (free_contract.ANALYSIS_KIND, free_contract.SEALED_SHA256),
    "free_conformance": (deallocator.ANALYSIS_KIND, deallocator.SEALED_SHA256),
    "cookie_return": (cookie_witness.ANALYSIS_KIND, cookie_witness.SEALED_SHA256),
}
STACK, ERROR, OLD_PAGE, RECEIVER_PAGE = 0x30000000, 0x06000000, 0x06002000, 0x10000000
RECEIVER, COOKIE, FEATURE_PAGE = 0x10000100, 0x00893F28, 0x00893000
HEAP_GLOBAL, FREE_IAT, HEAP = 0x008B7634, 0x007D621C, 0x12345678
IMPORT, RETURN = 0x05000000, 0x04000000
CPU_MODEL = 19  # UC_CPU_X86_HASWELL, matching the reviewed early-path probes.
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
BODIES = (
    (0x7800, 0x785B),
    (0x257340, 0x257427),
    (0x3574CA, 0x3574D5),
    (0x35785D, 0x357862),
    (0x36FB17, 0x36FB1C),
    (0x389156, 0x389190),
)
POINTS_SHA256 = "c9b19a18f0af920b1444c18aa583d6b1d067b164d2cb7d3d068be7dd5760aa3f"
VECTOR_KEYS = {"alignment", "profile", "path_form"}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
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
FREE_CALL_TRACE = (0x2573F4, 0x2573F7, 0x2573F9, 0x2573FB, 0x2573FE, 0x2573FF, 0x257400)
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
_canonical_bytes, _canonical_sha256 = common._canonical_bytes, common._canonical_sha256


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _same_packet(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return (
            set(a) == set(b)
            and all(any(type(k) is type(j) and k == j for j in b) for k in a)
            and all(_same_packet(a[k], b[k]) for k in a)
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same_packet(x, y) for x, y in zip(a, b))
    return a == b


def _read(pages, address, size=4):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _pages(pages):
    return {p: bytes(v) for p, v in pages.items()}


def _stack(pages):
    return _read(pages, STACK, 8192)


def _page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(data).hexdigest()
        for p, data in sorted(pages.items())
    }


def vectors():
    return [
        dict(alignment=a, profile=p, path_form=f)
        for a in range(16)
        for p in range(3)
        for f in ("null", "empty_owned", "one")
    ]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(type(k) is str for k in vector)
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["path_form"]) is str
        and vector in vectors(),
        "outside fixed movement early return geometry",
    )


def _fixture(vector):
    _checked_vector(vector)
    a, p, form = vector["alignment"], vector["profile"], vector["path_form"]
    pages = {
        page: bytearray(bytes([(i * 37 + j * 13 + p * 71) & 255 for j in range(4096)]))
        for i, page in enumerate(
            (
                0,
                STACK,
                STACK + 4096,
                OLD_PAGE,
                ERROR,
                RECEIVER_PAGE,
                FEATURE_PAGE,
                HEAP_GLOBAL & ~4095,
                FREE_IAT & ~4095,
            )
        )
    }
    g, o = STACK + 4096 + a, OLD_PAGE + 0x800 + a
    begin = 0 if form == "null" else o
    end = begin + (8 if form == "one" else 0)
    capacity = 0 if form == "null" else o + 8
    cookie = (0x19A51C73 ^ (p * 0x2468ACE)) & 0xFFFFFFFF
    seh = (0x11112222 ^ (p * 0x1020304)) & 0xFFFFFFFF
    values = (RETURN, begin, end, capacity, (0xBF800000, 0x7FC01234, 0xFF800000)[p])
    for offset, value in enumerate(values):
        _write(pages, g + offset * 4, value.to_bytes(4, "little"))
    for address, value in (
        (0, seh),
        (COOKIE, cookie),
        (HEAP_GLOBAL, HEAP),
        (FREE_IAT, IMPORT),
    ):
        _write(pages, address, value.to_bytes(4, "little"))
    _write(
        pages,
        o,
        ((0xD15C0048 ^ (p * 0x7654321)) & 0xFFFFFFFF).to_bytes(4, "little")
        + ((0x1122AA48 ^ (p * 0x1234567)) & 0xFFFFFFFF).to_bytes(4, "little"),
    )
    regs = {
        r: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, r in enumerate(REGISTERS)
    }
    regs.update(ecx=RECEIVER, esp=g)
    xmms = {
        r: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=_pages(pages),
        registers=regs,
        xmm=xmms,
        return_address=RETURN,
        entry_flags=0x246,
    )


def _event_law(original):
    memory = {p: bytearray(v) for p, v in original.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address), "little") == value,
                "movement expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    return memory, events, event


def _boundary(regs, xmm, pages, events, endpoint, flags, mask):
    return dict(
        registers=dict(regs),
        xmm=dict(xmm),
        pages=_pages(pages),
        events=copy.deepcopy(events),
        endpoint=endpoint,
        flags=flags,
        flag_mask=mask,
        df=0,
    )


def _free_packet_law(regs, pages, pointer):
    """Ordinary count1/stride8; exact8 fields against the unchanged generic law."""
    v = regs["esp"]
    memory, events, e = _event_law(pages)
    for access, address, value in (
        ("write", v - 4, regs["ebp"]),
        ("read", v + 8, 1),
        ("read", v + 12, 8),
        ("read", v + 12, 8),
        ("read", v + 4, pointer),
        ("write", v - 8, pointer),
        ("write", v - 12, BASE + 0x7856),
        ("write", v - 16, v - 4),
        ("read", v - 8, pointer),
        ("read", v - 8, pointer),
        ("write", v - 20, pointer),
        ("write", v - 24, 0),
        ("read", HEAP_GLOBAL, HEAP),
        ("write", v - 28, HEAP),
        ("read", FREE_IAT, IMPORT),
        ("write", v - 32, BASE + 0x389172),
        ("read", v - 16, v - 4),
        ("read", v - 12, BASE + 0x7856),
        ("read", v - 4, regs["ebp"]),
        ("read", v, deallocator.RETURN),
    ):
        # The primitive's canonical outer RET word is rebound only after the
        # complete source model comparison. All stack/page bytes are actual.
        if address == v and access == "read":
            events.append(dict(access=access, address=address, width=4, value=value))
        else:
            e(access, address, value)
    wanted = dict(
        registers=dict(regs, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=v + 4),
        flags=_add_flags(v - 8, 4),
        flag_mask=0x8D5,
        events=events,
        stack=_stack(memory),
        error=pages[ERROR],
        stop=deallocator.RETURN,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    child = _normalize(
        lambda: deallocator._expected(
            dict(
                pointer=pointer,
                count=1,
                stride=8,
                metadata=None,
                responses=[dict(kind="heap_free", eax=1)],
                heap=HEAP,
            ),
            dict(regs),
            _stack(pages),
            pages[ERROR],
            stack_base=STACK,
        )
    )
    _require(_same_packet(child, wanted), "movement free primitive differs")
    _require(
        int.from_bytes(_read(pages, v), "little") == BASE + 0x257405,
        "movement free installed continuation differs",
    )
    wanted["events"][-1]["value"] = BASE + 0x257405
    wanted["stop"] = BASE + 0x257405
    return wanted


def _expected(vector, fixture):
    _checked_vector(vector)
    _require(
        type(fixture) is dict
        and set(fixture) == FIXTURE_KEYS
        and type(fixture["pages"]) is dict
        and set(fixture["pages"])
        == {
            0,
            STACK,
            STACK + 4096,
            OLD_PAGE,
            ERROR,
            RECEIVER_PAGE,
            FEATURE_PAGE,
            HEAP_GLOBAL & ~4095,
            FREE_IAT & ~4095,
        }
        and all(
            type(p) is int and type(v) is bytes and len(v) == 4096
            for p, v in fixture["pages"].items()
        )
        and type(fixture["registers"]) is dict
        and set(fixture["registers"]) == set(REGISTERS)
        and all(
            type(v) is int and 0 <= v < 2**32 for v in fixture["registers"].values()
        )
        and fixture["registers"]["esp"] == STACK + 4096 + vector["alignment"]
        and fixture["registers"]["ecx"] == RECEIVER
        and type(fixture["xmm"]) is dict
        and set(fixture["xmm"]) == set(XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in fixture["xmm"].values())
        and type(fixture["entry_flags"]) is int
        and fixture["entry_flags"] == 0x246
        and type(fixture["return_address"]) is int
        and fixture["return_address"] == RETURN
        and _same_packet(fixture, _fixture(vector)),
        "movement fixture recipe differs",
    )
    return _normalize(lambda: _composed_expected(vector, fixture))


def _composed_expected(vector, fixture):
    regs = dict(fixture["registers"])
    initial = dict(regs)
    xmm = dict(fixture["xmm"])
    g, f = regs["esp"], regs["esp"] - 4
    begin = int.from_bytes(_read(fixture["pages"], g + 4), "little")
    end = int.from_bytes(_read(fixture["pages"], g + 8), "little")
    capacity = int.from_bytes(_read(fixture["pages"], g + 12), "little")
    cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
    seh = int.from_bytes(_read(fixture["pages"], 0), "little")
    memory, events, e = _event_law(fixture["pages"])
    for access, address, value in (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CA95E),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("read", COOKIE, cookie),
        ("write", g - 20, cookie ^ f),
        ("write", g - 0x280, initial["ebx"]),
        ("write", g - 0x284, initial["esi"]),
        ("write", g - 0x288, cookie ^ f),
        ("write", 0, g - 16),
        ("write", g - 8, 0),
        ("read", g + 8, end),
        ("read", g + 4, begin),
    ):
        e(access, address, value)
    count = (end - begin) // 8
    regs.update(
        eax=count,
        ebx=initial["ebx"] & 0xFFFFFF00,
        edx=begin,
        esi=RECEIVER,
        ebp=f,
        esp=g - 0x288,
    )
    free_entry, free_return, free_packet, imported = None, None, None, None
    trace = PREFIX_TRACE
    if begin:
        for access, address, value in (
            ("read", g + 12, capacity),
            ("write", g - 0x28C, 8),
            ("write", g - 0x290, 1),
            ("write", g - 0x294, begin),
            ("write", g - 0x298, BASE + 0x257405),
        ):
            e(access, address, value)
        regs.update(ecx=1, esp=g - 0x298)
        free_entry = _boundary(regs, xmm, memory, events, BASE + 0x7800, 0, 0xC5)
        before = copy.deepcopy(events)
        free_packet = _free_packet_law(regs, _pages(memory), begin)
        events.extend(copy.deepcopy(free_packet["events"]))
        _write(memory, STACK, free_packet["stack"])
        regs = dict(free_packet["registers"])
        free_return = _boundary(
            regs, xmm, memory, events, BASE + 0x257405, free_packet["flags"], 0x8D5
        )
        import_pages = {p: bytearray(v) for p, v in free_entry["pages"].items()}
        for row in free_packet["events"][:16]:
            if row["access"] == "write":
                _write(import_pages, row["address"], row["value"].to_bytes(4, "little"))
        v = g - 0x298
        imported = dict(
            role="free",
            entry_esp=v - 32,
            words=[BASE + 0x389172, HEAP, 0, begin],
            **_boundary(
                dict(
                    free_entry["registers"],
                    eax=0x1FFFFFFF,
                    ecx=begin,
                    edx=7,
                    ebp=v - 16,
                    esp=v - 32,
                ),
                xmm,
                import_pages,
                before + free_packet["events"][:16],
                IMPORT,
                int((begin & 255).bit_count() % 2 == 0) << 2,
                0x8D5,
            ),
        )
        regs["esp"] += 12
        trace = trace + FREE_CALL_TRACE + FREE_TRACE + (0x257405,)
    suffix_rows = (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ f),
        ("read", g - 0x284, initial["esi"]),
        ("read", g - 0x280, initial["ebx"]),
        ("read", g - 20, cookie ^ f),
        ("write", g - 0x280, BASE + 0x257421),
        ("read", COOKIE, cookie),
        ("read", g - 0x280, BASE + 0x257421),
        ("read", g - 4, initial["ebp"]),
        ("read", g, RETURN),
    )
    for access, address, value in suffix_rows[:7]:
        e(access, address, value)
    final = dict(
        initial, eax=0, ecx=cookie, edx=(0xB0000001 if begin else 0), esp=g + 20
    )
    checker_flags = (int((cookie & 255).bit_count() % 2 == 0) << 2) | (
        (cookie >> 31) << 7
    )
    cookie_entry = _boundary(
        dict(final, ebp=f, esp=g - 0x280),
        xmm,
        memory,
        events,
        BASE + 0x3574CA,
        checker_flags,
        0x8C5,
    )
    for access, address, value in suffix_rows[7:]:
        e(access, address, value)
    pages = _pages(memory)
    # Reconstruct complete pages independently, using only source-derived frame
    # stores plus the primitive's checked stack transport for the owned path.
    _require(
        all(row["address"] != g + 16 for row in events),
        "movement ignored parameter was read",
    )
    result = dict(
        path=dict(
            begin=begin,
            end=end,
            capacity=capacity,
            count=count,
            parameter_bits=int.from_bytes(_read(fixture["pages"], g + 16), "little"),
        ),
        registers=final,
        xmm=xmm,
        pages=pages,
        events=events,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=RETURN,
        trace_rvas=[f"0x{pc:08x}" for pc in trace + SUFFIX_TRACE],
        free_entry=free_entry,
        free_return=free_return,
        free_packet=free_packet,
        imported=imported,
        cookie_entry=cookie_entry,
    )
    _require(
        _same_packet(pages, _model_pages(fixture, result)),
        "movement independent final pages differ",
    )
    return result


def _model_pages(fixture, expected):
    memory = {p: bytearray(v) for p, v in fixture["pages"].items()}
    g = fixture["registers"]["esp"]
    f = g - 4
    cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
    seh = int.from_bytes(_read(fixture["pages"], 0), "little")
    for address, value in (
        (g - 4, fixture["registers"]["ebp"]),
        (g - 8, 0),
        (g - 12, 0x007CA95E),
        (g - 16, seh),
        (g - 20, cookie ^ f),
        (g - 0x280, fixture["registers"]["ebx"]),
        (g - 0x284, fixture["registers"]["esi"]),
        (g - 0x288, cookie ^ f),
    ):
        _write(memory, address, value.to_bytes(4, "little"))
    if expected["free_packet"] is not None:
        _write(memory, STACK, expected["free_packet"]["stack"])
    _write(memory, 0, seh.to_bytes(4, "little"))
    _write(memory, g - 0x280, (BASE + 0x257421).to_bytes(4, "little"))
    return _pages(memory)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "movement source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        ids = {
            k: common._source_identity(sources[k], *pin, k)
            for k, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[k]["build_identity"], identity)
                for k in SOURCE_PINS
                if k != "program_facts"
            ),
            "movement source build differs",
        )
        return ids

    return _normalize(run)


def _source_points(sources):
    main = sources["movement_binding"]["bodies"]["move_parent"]
    _require(
        main["entry_rva"] == "0x00257340" and main["size"] == 231,
        "movement parent extent differs",
    )
    points = [
        {k: p[k] for k in ("rva", "size", "sha256")} for p in main["graph"]["nodes"]
    ]
    free = sources["free_composition"]
    points.extend(free["guard_body"]["points"])
    for row in free["free_bodies"]:
        if row["entry_rva"] in ("0x0035785d", "0x0036fb17", "0x00389156"):
            points.extend(row["points"])
    points.extend(sources["cookie_return"]["bodies"]["checker_normal"]["points"])
    points = sorted(points, key=lambda p: int(p["rva"], 16))
    _require(
        _canonical_sha256(points) == POINTS_SHA256,
        "movement source point identity differs",
    )
    return points


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and all(type(k) is int for k in codes)
            and set(codes) == {a for a, b in BODIES}
            and type(points) is list
            and _canonical_sha256(points) == POINTS_SHA256,
            "movement direct code identity differs",
        )
        allowed = {}
        for a, b in BODIES:
            _require(
                type(codes[a]) is bytes and len(codes[a]) == b - a,
                "movement direct code extent differs",
            )
            cursor = a
            for p in (p for p in points if a <= int(p["rva"], 16) < b):
                _require(
                    type(p) is dict
                    and set(p) == {"rva", "size", "sha256"}
                    and type(p["size"]) is int
                    and p["size"] > 0,
                    "movement direct point schema differs",
                )
                pc = int(p["rva"], 16)
                _require(
                    pc == cursor
                    and pc + p["size"] <= b
                    and hashlib.sha256(
                        codes[a][pc - a : pc - a + p["size"]]
                    ).hexdigest()
                    == p["sha256"],
                    "movement direct instruction bytes differ",
                )
                allowed[pc] = p
                cursor += p["size"]
            _require(cursor == b, "movement direct point extent differs")
        _require(len(allowed) == len(points), "movement direct point partition differs")
        return allowed

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        _preflight(sources)
        _require(
            hashlib.sha256(data).hexdigest() == EXE_SHA256 and image.image_base == BASE,
            "movement executable differs",
        )
        points = _source_points(sources)
        codes = {}
        for a, b in BODIES:
            offset = image.rva_span_to_file_offset(a, b - a)
            _require(offset is not None, "movement selected body unmapped")
            codes[a] = data[offset : offset + b - a]
        _checked_code_packet(codes, points)
        return codes, points

    return _normalize(run)


def _check_boundary(machine, ids, xmm_ids, x, wanted, events, label):
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        _same_packet(
            {r: machine.reg_read(i) for r, i in ids.items()}, wanted["registers"]
        )
        and _same_packet(
            {r: machine.reg_read(i) for r, i in xmm_ids.items()}, wanted["xmm"]
        )
        and flags & wanted["flag_mask"] == wanted["flags"]
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == wanted["endpoint"]
        and _same_packet(events, wanted["events"])
        and all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in wanted["pages"].items()
        ),
        "movement " + label + " differs",
    )


CONTROLS = {
    **{
        name: "movement " + stage.replace("_", " ") + " differs"
        for stage in ("free_entry", "free_return", "cookie_entry")
        for name in (
            stage + "_gpr",
            stage + "_xmm",
            stage + "_flags",
            stage + "_df",
            stage + "_page",
        )
    },
    "count": "movement native path differs",
    "capacity": "movement ordered memory events differ",
    "free_request": "movement free handoff differs",
    "response_gpr": "movement supplied response preservation differs",
    "response_xmm": "movement supplied response preservation differs",
    "response_page": "movement supplied response preservation differs",
    "response_result": "movement supplied response preservation differs",
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
    **{
        name: "movement final events differ"
        for name in ("missing_read_record", "restored_write_record")
    },
    "trace_record": "movement final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid movement control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "movement reviewed Unicorn required")
    allowed = _checked_code_packet(codes, points)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(CPU_MODEL)
    _require(machine.ctl_get_cpu_model() == CPU_MODEL, "movement CPU model differs")
    code_pages = {
        (BASE + address) & ~4095 for a, b in BODIES for address in range(a, b)
    } | {IMPORT, RETURN}
    _require(
        not code_pages.intersection(fixture["pages"]),
        "movement runtime mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, payload)
    for a, payload in codes.items():
        machine.mem_write(BASE + a, payload)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in REGISTERS}
    xmm_ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in XMM}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    for r, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    events, trace, boundaries, summaries = [], [], [], []
    resume = None
    g = fixture["registers"]["esp"]

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    if negative == "capacity":
        flip(g + 12)

    def observe_boundary(name, expected):
        flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
        boundaries.append(
            dict(
                name=name,
                registers={r: machine.reg_read(i) for r, i in ids.items()},
                xmm={r: machine.reg_read(i) for r, i in xmm_ids.items()},
                eflags=flags,
                flags=flags & expected["flag_mask"],
                flag_mask=expected["flag_mask"],
                df=(flags >> 10) & 1,
                endpoint=machine.reg_read(x.UC_X86_REG_EIP),
                pages_sha256=_page_hashes(
                    {p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]}
                ),
                events_sha256=_canonical_sha256(events),
            )
        )

    def mutate_boundary(name):
        if negative == name + "_gpr":
            machine.reg_write(ids["edx"], machine.reg_read(ids["edx"]) ^ 1)
        if negative == name + "_xmm":
            machine.reg_write(xmm_ids["xmm7"], machine.reg_read(xmm_ids["xmm7"]) ^ 1)
        if negative in (name + "_flags", name + "_df"):
            machine.reg_write(
                x.UC_X86_REG_EFLAGS,
                machine.reg_read(x.UC_X86_REG_EFLAGS)
                ^ (1 if negative == name + "_flags" else 0x400),
            )
        if negative == name + "_page":
            flip(ERROR + 1)

    def on_code(m, address, size, user):
        nonlocal resume
        if address == RETURN:
            m.emu_stop()
            return
        if address == IMPORT:
            imported = wanted["imported"]
            _require(
                imported is not None and not summaries, "movement repeated or null free"
            )
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            if negative == "free_request":
                words[3] ^= 1
                flip(sp + 12)
            _require(
                sp == imported["entry_esp"] and words == imported["words"],
                "movement free handoff differs",
            )
            _check_boundary(m, ids, xmm_ids, x, imported, events, "free imported ABI")
            flags = m.reg_read(x.UC_X86_REG_EFLAGS)
            pages = {p: bytes(m.mem_read(p, 4096)) for p in fixture["pages"]}
            summaries.append(
                dict(
                    role="free",
                    entry_esp=sp,
                    words=words,
                    registers={r: m.reg_read(i) for r, i in ids.items()},
                    xmm={r: m.reg_read(i) for r, i in xmm_ids.items()},
                    eflags=flags,
                    flags=flags & imported["flag_mask"],
                    flag_mask=imported["flag_mask"],
                    df=(flags >> 10) & 1,
                    endpoint=address,
                    pages_sha256=_page_hashes(pages),
                    events_sha256=_canonical_sha256(events),
                )
            )
            response = dict(
                imported["registers"],
                eax=1,
                ecx=0xA0000001,
                edx=0xB0000001,
                esp=sp + 16,
            )
            for r in ("eax", "ecx", "edx", "esp"):
                m.reg_write(ids[r], response[r])
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            if negative == "response_gpr":
                m.reg_write(ids["ebx"], m.reg_read(ids["ebx"]) ^ 1)
            if negative == "response_xmm":
                m.reg_write(xmm_ids["xmm6"], m.reg_read(xmm_ids["xmm6"]) ^ 1)
            if negative == "response_page":
                flip(ERROR + 1)
            if negative == "response_result":
                m.reg_write(ids["eax"], 0)
            _require(
                _same_packet({r: m.reg_read(i) for r, i in ids.items()}, response)
                and _same_packet(
                    {r: m.reg_read(i) for r, i in xmm_ids.items()}, fixture["xmm"]
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) == 0x246
                and all(
                    bytes(m.mem_read(p, 4096)) == payload
                    for p, payload in pages.items()
                ),
                "movement supplied response preservation differs",
            )
            resume = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "movement escaped selected code",
        )
        if negative == "count" and pc == 0x257381:
            m.reg_write(ids["eax"], 2)
        for name, endpoint in (
            ("free_entry", BASE + 0x7800),
            ("free_return", BASE + 0x257405),
            ("cookie_entry", BASE + 0x3574CA),
        ):
            if address == endpoint:
                state = wanted[name]
                _require(state is not None, "movement unadmitted free boundary")
                mutate_boundary(name)
                if negative == "cookie" and name == "cookie_entry":
                    flip(COOKIE)
                _check_boundary(
                    m, ids, xmm_ids, x, state, events, name.replace("_", " ")
                )
                observe_boundary(name, state)
        trace.append(f"0x{pc:08x}")
        _require(
            trace == wanted["trace_rvas"][: len(trace)], "movement native path differs"
        )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        _require(width == 4, "movement access width differs")
        row = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & 0xFFFFFFFF
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < len(wanted["events"])
            and _same_packet(row, wanted["events"][len(events)]),
            "movement ordered memory events differ",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + 0x257340
    for _ in range(2):
        resume = None
        machine.emu_start(next_pc, 0, count=10000)
        if resume is None:
            break
        next_pc = resume
    corrupt = {
        "seh": 0,
        "ancestor": g + 20,
        "old": OLD_PAGE + 0x800 + vector["alignment"],
        "receiver": RECEIVER + 4,
        "feature_padding": FEATURE_PAGE + 1,
        "iat_padding": FREE_IAT & ~4095,
        "ignored_parameter": g + 16,
        "caller_header": g + 12,
    }
    if negative in corrupt:
        flip(corrupt[negative])
    if negative == "final_al":
        machine.reg_write(ids["eax"], machine.reg_read(ids["eax"]) ^ 1)
    if negative == "final_nonvolatile":
        machine.reg_write(ids["ebx"], machine.reg_read(ids["ebx"]) ^ 1)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm0"], machine.reg_read(xmm_ids["xmm0"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "final_flags" else 0x400),
        )
    if negative == "final_endpoint":
        machine.reg_write(x.UC_X86_REG_EIP, RETURN + 1)
    if negative == "missing_read_record":
        events.pop()
    if negative == "restored_write_record":
        events.extend(
            [
                dict(access="write", address=RECEIVER, width=4, value=1),
                dict(
                    access="write",
                    address=RECEIVER,
                    width=4,
                    value=int.from_bytes(_read(fixture["pages"], RECEIVER), "little"),
                ),
            ]
        )
    if negative == "trace_record":
        trace.append("0x0025738a")
    regs = {r: machine.reg_read(i) for r, i in ids.items()}
    xmms = {r: machine.reg_read(i) for r, i in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    pages = {p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]}
    _require(
        _same_packet(regs, wanted["registers"])
        and _same_packet(xmms, wanted["xmm"])
        and flags & 0x8D5 == 0x44
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == RETURN,
        "movement final ABI differs",
    )
    _require(_same_packet(pages, wanted["pages"]), "movement final pages differ")
    _require(_same_packet(events, wanted["events"]), "movement final events differ")
    _require(
        _same_packet(trace, wanted["trace_rvas"]), "movement final native path differs"
    )
    names = (
        ["free_entry", "free_return", "cookie_entry"]
        if wanted["path"]["begin"]
        else ["cookie_entry"]
    )
    _require(
        [b["name"] for b in boundaries] == names
        and len(summaries) == int(bool(wanted["path"]["begin"])),
        "movement boundaries or free count differs",
    )
    result = dict(
        vector=dict(vector),
        registers=regs,
        xmm=xmms,
        flags=flags & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        trace_rvas=trace,
        events_sha256=_canonical_sha256(events),
        pages_sha256=_page_hashes(pages),
        memory_event_count=len(events),
        boundaries=boundaries,
        summaries=summaries,
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(wanted), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(Path(executable)))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "movement incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("movement control survived: " + name)
    executed = sorted({pc for o in observations for pc in o["trace_rvas"]})
    trace_union = {
        f"0x{pc:08x}"
        for pc in PREFIX_TRACE
        + FREE_CALL_TRACE
        + FREE_TRACE
        + (0x257405,)
        + SUFFIX_TRACE
    }
    _require(set(executed) == trace_union, "movement native coverage differs")
    n = len(observations)
    owned = sum(bool(o["summaries"]) for o in observations)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    exclusive_end_rva=f"0x{a+len(v):08x}",
                    sha256=hashlib.sha256(v).hexdigest(),
                )
                for a, v in codes.items()
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            cpu_model=dict(id=CPU_MODEL, name="UC_CPU_X86_HASWELL"),
        ),
        executed_rvas=executed,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            null_cases=n - owned,
            owned_cases=owned,
            loaded_sites=len(points),
            loaded_bytes=sum(map(len, codes.values())),
            executed_sites=len(executed),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            memory_events=sum(o["memory_event_count"] for o in observations),
            free_requests=sum(len(o["summaries"]) for o in observations),
            allocation_requests=0,
            old_bytes_preserved=8 * n,
            xmm_preserved_cases=n,
            parameter_word_reads=0,
            effect_record_sites=0,
            controls=len(controls),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Finite native AddMove path count zero or one early AL-zero return with original by-value path cleanup",
            premises=[
                "Exact144 synthetic recipes with null or one-capacity path storage and ignored arbitrary parameter bits",
                "One Unicorn state executes parent ordinary count1 stride8 free guard and cookie return continuously",
                "Supplied successful HeapFree preserves full pages nonvolatile GPR all8XMM and DF0",
                "Architecturally defined flags checked separately from captured finite VM rawEFLAGS",
                "Full8 primitive packet checked against unchanged generic free law with installed continuation binding",
            ],
            not_claimed=[
                "Count greater than one effect record construction copy append destruction AddCharge gameplay reachability or pawn movement",
                "Allocator ownership unmapping failure unwinding exception handler real process or hardware execution",
                "Injected event and path record mutations do not prove represented stores or instructions executed",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "movement executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], ids)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed movement receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def build_conformance(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _same_packet(_build_unsealed(executable, sources), evidence),
            "movement native rebuild differs",
        )
        return dict(
            status="verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def encode_conformance(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
