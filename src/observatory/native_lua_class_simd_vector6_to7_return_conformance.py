"""Finite continuous existing-key class6 to7 with installed growth capacity9."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_simd_vector_return_conformance as legacy
from src.observatory import native_simd_vector_growth6_to9_conformance as growth
from src.observatory import native_simd_vector_growth6_to9_semantics as model
from src.observatory import native_simd_vector_resize6_to9_conformance as resize
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_vector_return_conformance as returned
from src.observatory import native_assertion_helper_fill_conformance as common

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_lua_class_simd_vector6_to7_return_conformance"
SEALED_SHA256 = "9103e9dd655eaeb9530b0c09f2ea2d050e6e5462c2f796ce3136e63264ff37e6"
SOURCE_PINS = {
    **legacy.SOURCE_PINS,
    **growth.SOURCE_PINS,
    "class_simd_return": (legacy.ANALYSIS_KIND, legacy.SEALED_SHA256),
    "growth6_to9": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
}
START = prefix.START
RECEIVER, ARGUMENT, SOURCE_HEAD = prefix.RECEIVER, prefix.ARGUMENT, prefix.SOURCE_HEAD
construction = prefix.construction
ConformanceError = prefix.ConformanceError
REGISTERS, XMM = model.REGISTERS, model.XMM
allocator, installed_copy = growth.allocator, growth.installed_copy
STACK, ERROR, FEATURE_PAGE = model.STACK, model.ERROR, model.FEATURE_PAGE
HEAP, IMPORT = model.HEAP, model.IMPORT
ALLOC_IAT, FREE_IAT = model.ALLOC_IAT, model.FREE_IAT
VECTOR_KEYS, FIXTURE_KEYS = legacy.VECTOR_KEYS, legacy.FIXTURE_KEYS
_canonical_bytes, _canonical_sha256 = common._canonical_bytes, common._canonical_sha256
_same_packet = legacy._same_packet
_read, _write, _pages, _event_law, _boundary = (
    growth._read,
    growth._write,
    growth._pages,
    growth._event_law,
    growth._boundary,
)
_allocation_packet_law, _copy_packet_law, _free_packet_law = (
    growth._allocation_packet_law,
    growth._copy_packet_law,
    growth._free_packet_law,
)
_add_flags, _sub_flags = growth._add_flags, model._sub_flags
ALLOCATION_TRACE, FREE_TRACE, COPY_TRACE = (
    model.ALLOCATION_TRACE,
    model.FREE_TRACE,
    model.COPY_TRACE,
)
OWNER_TRACE = model.OWNER_TRACE
GROWTH_PREFIX = model.GROWTH_PREFIX
POINTS_SHA256 = "bc43b3482b4a7c8a47f3cd213b2ef76ace1a0599aa06b86cdee4ca99d246e690"
BODIES = (
    (30720, 30811),
    (450352, 450431),
    (464976, 465070),
    (511376, 511417),
    (512096, 512147),
    (512160, 512660),
    (567584, 567675),
    (3045024, 3045097),
    (3047920, 3048068),
    (3048080, 3048177),
    (3048192, 3048488),
    (3048638, 3048670),
    (3060032, 3060172),
    (3060215, 3060269),
    (3061280, 3061374),
    (3061376, 3061477),
    (3503306, 3503317),
    (3503323, 3503374),
    (3504221, 3504226),
    (3597696, 3597759),
    (3598388, 3598403),
    (3598740, 3598795),
    (3598925, 3599031),
    (3603223, 3603228),
    (3645266, 3645277),
    (3707222, 3707280),
    (3707947, 3708025),
)


def _require(condition, message):
    if not condition:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def vectors():
    return [dict(v, old_size=6) for v in legacy.vectors()]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(
            type(vector[k]) is int
            for k in VECTOR_KEYS - {"profile", "source_keys", "destination_keys"}
        )
        and type(vector["profile"]) is str
        and all(
            type(vector[k]) is list and all(type(n) is int for n in vector[k])
            for k in ("source_keys", "destination_keys")
        )
        and vector in vectors(),
        "outside fixed class6 to7 geometry",
    )


def _fixture(vector):
    _checked_vector(vector)
    fixture = copy.deepcopy(
        _normalize(lambda: legacy._fixture(dict(vector, old_size=4)))
    )
    pages = {page: bytearray(data) for page, data in fixture["pages"].items()}
    pages[0x06004000] = bytearray(bytes([0xA5]) * 4096)
    old = 0x06002800 + vector["vector_alignment"]
    fresh = 0x06004800 + vector["vector_alignment"]
    for offset, value in ((4, old), (8, old + 48), (12, old + 48)):
        _write(pages, RECEIVER + offset, value.to_bytes(4, "little"))
    for i in range(12):
        value = (
            0x91827364 ^ i * 0x1234567 ^ vector["xmm_profile"] * 0x7654321
        ) & 0xFFFFFFFF
        _write(pages, old + 4 * i, value.to_bytes(4, "little"))
    fixture.update(
        pages=_pages(pages),
        old_size=6,
        old_begin=old,
        vector_begin=fresh,
        vector_end=fresh + 48,
        vector_capacity=fresh + 72,
        old_base=0x06002000,
        new_base=0x06004000,
        new_page_count=1,
    )
    return fixture


def _resize_packet_law(g, incoming, obj):
    initial, xmm = incoming["registers"], incoming["xmm"]
    s = initial["esp"]
    memory, events, e = _event_law(incoming["pages"])
    w = lambda address, value: e("write", address, value)
    r = lambda address, value: e("read", address, value)
    w(s - 4, initial["ebp"])
    w(s - 8, obj)
    r(s + 4, 9)
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 16, initial["esi"]),
        (s - 20, initial["edi"]),
        (s - 24, 9),
        (s - 8, 9),
        (s - 28, BASE + 0x2EB695),
    ):
        w(address, value)
    regs = dict(initial, ebp=s - 4, esp=s - 28, eax=9, esi=obj)
    allocation_entry = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, incoming["entry_flags"], 0xFFFFFFFF
    )
    allocated = _allocation_packet_law(
        regs, _pages(memory), g["new_begin"], BASE + 0x2EB695
    )
    events.extend(allocated["events"])
    _write(memory, STACK, allocated["stack"])
    regs = dict(allocated["registers"])
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    for address, value in (
        (s - 24, 48),
        (s - 28, g["old_begin"]),
        (s - 32, g["new_begin"]),
        (s - 36, BASE + 0x2EB6A6),
    ):
        w(address, value)
    regs.update(
        eax=g["new_begin"],
        edi=g["new_begin"],
        esi=obj,
        ecx=48,
        edx=g["old_begin"],
        esp=s - 36,
    )
    copy_entry = _boundary(
        regs,
        xmm,
        memory,
        events,
        BASE + 0x36E580,
        _sub_flags(g["old_end"], g["old_begin"]),
        0x8D5,
    )
    copied = _copy_packet_law(regs, xmm, _pages(memory), g["old_begin"], g["new_begin"])
    events.extend(copied["events"])
    memory = {page: bytearray(data) for page, data in copied["pages"].items()}

    # Replace closure targets after child page transport, retaining all prior events.
    def owner_event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))

    w = lambda address, value: owner_event("write", address, value)
    r = lambda address, value: owner_event("read", address, value)
    regs, xmm = dict(copied["registers"]), dict(copied["xmm"])
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    r(obj + 8, g["old_capacity"])
    for address, value in (
        (s - 24, 8),
        (s - 28, 6),
        (s - 32, g["old_begin"]),
        (s - 36, BASE + 0x2EB6C8),
    ):
        w(address, value)
    regs.update(eax=6, ebx=6, ecx=g["old_begin"], esp=s - 36)
    free_entry = _boundary(regs, xmm, memory, events, BASE + 0x7800, 0x4, 0xC5)
    # SAR6-capacity arithmetic leaves PF1 and CF0; AF is undefined.
    freed = _free_packet_law(regs, _pages(memory), g["old_begin"], BASE + 0x2EB6C8)
    events.extend(freed["events"])
    _write(memory, STACK, freed["stack"])
    regs = dict(freed["registers"])
    r(s - 8, 9)
    for address, value in (
        (obj + 8, g["new_capacity"]),
        (obj + 4, g["new_end"]),
        (obj, g["new_begin"]),
    ):
        w(address, value)
    for address, value in (
        (s - 20, initial["edi"]),
        (s - 16, initial["esi"]),
        (s - 12, initial["ebx"]),
        (s - 4, initial["ebp"]),
        (s, incoming["return_address"]),
    ):
        r(address, value)
    regs.update(
        eax=g["new_end"],
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        ebp=initial["ebp"],
        esp=s + 8,
    )
    trace = (
        tuple(pc for pc in OWNER_TRACE if pc <= 0x2EB690)
        + ALLOCATION_TRACE
        + tuple(pc for pc in OWNER_TRACE if 0x2EB695 <= pc <= 0x2EB6A1)
        + COPY_TRACE
        + tuple(pc for pc in OWNER_TRACE if 0x2EB6A6 <= pc <= 0x2EB6C3)
        + FREE_TRACE
        + tuple(pc for pc in OWNER_TRACE if pc >= 0x2EB6C8)
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=xmm,
        flags=_add_flags(s - 32, 12),
        flag_mask=0x8D5,
        df=0,
        events=events,
        pages=_pages(memory),
        endpoint=incoming["return_address"],
        allocation_entry=allocation_entry,
        allocation_packet=allocated,
        copy_entry=copy_entry,
        copy_packet=copied,
        free_entry=free_entry,
        free_packet=freed,
        allocation_request=dict(
            continuation=BASE + 0x389463, handle=HEAP, flags=0, bytes=72
        ),
        free_request=dict(
            continuation=BASE + 0x389172, handle=HEAP, flags=0, pointer=g["old_begin"]
        ),
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
    )


def _growth_packet_law(
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    g = dict(
        old_begin=source,
        old_end=source + 48,
        old_capacity=source + 48,
        new_begin=destination,
        new_end=destination + 48,
        new_capacity=destination + 72,
        copy_bytes=48,
        request=72,
        old_size=6,
        requested=9,
    )
    initial, xmm = dict(registers), dict(xmm)
    entry, obj = initial["esp"], object_address
    memory, prefix, e = _event_law(pages)
    for access, address, value in (
        ("write", entry - 4, initial["esi"]),
        ("write", entry - 8, initial["edi"]),
        ("read", obj + 8, source + 48),
        ("read", obj + 4, source + 48),
        ("read", obj, source),
        ("write", entry - 12, initial["ebx"]),
        ("write", entry - 16, 9),
        ("write", entry - 20, BASE + 0x2EB66E),
    ):
        e(access, address, value)
    regs = dict(
        initial, eax=9, ebx=0x1FFFFFFC, ecx=obj, edx=9, esi=obj, edi=6, esp=entry - 20
    )
    # Selected CMP9vs7 clears arithmetic bits and preserves admitted IF/reservedbit1.
    full_flags = entry_flags & 0x202
    incoming = _boundary(regs, xmm, memory, prefix, BASE + 0x2EB680, 0, 0x8D5)
    actual_pages = _pages(memory)
    supplied = dict(
        pages=actual_pages,
        registers=regs,
        xmm=xmm,
        return_address=BASE + 0x2EB66E,
        entry_flags=full_flags,
    )
    predicted = _resize_packet_law(g, supplied, obj)
    joined = prefix + copy.deepcopy(predicted["events"])
    returned = _boundary(
        predicted["registers"],
        predicted["xmm"],
        predicted["pages"],
        joined,
        BASE + 0x2EB66E,
        predicted["flags"],
        predicted["flag_mask"],
    )
    events = copy.deepcopy(joined)
    events.extend(
        dict(access="read", address=address, width=4, value=value)
        for address, value in (
            (entry - 12, initial["ebx"]),
            (entry - 8, initial["edi"]),
            (entry - 4, initial["esi"]),
            (entry, return_address),
        )
    )
    result = copy.deepcopy(predicted)
    result.update(
        registers=dict(
            predicted["registers"],
            ebx=initial["ebx"],
            edi=initial["edi"],
            esi=initial["esi"],
            esp=entry + 8,
        ),
        events=events,
        endpoint=return_address,
        resize_entry=incoming,
        resize_return=returned,
        resize_packet=copy.deepcopy(predicted),
    )
    for name in ("allocation_entry", "copy_entry", "free_entry"):
        result[name]["events"] = copy.deepcopy(prefix) + result[name]["events"]
    result["trace_rvas"] = (
        [f"0x{pc:08x}" for pc in GROWTH_PREFIX]
        + predicted["trace_rvas"]
        + [f"0x{pc:08x}" for pc in (0x2EB66E, 0x2EB66F, 0x2EB670, 0x2EB671)]
    )
    return result


def _expected(vector, fixture):
    _checked_vector(vector)
    _require(
        type(fixture) is dict
        and set(fixture) == FIXTURE_KEYS
        and _same_packet(fixture, _fixture(vector)),
        "class6 to7 fixture recipe differs",
    )
    return _normalize(lambda: _composed_expected(vector, fixture))


def _composed_expected(vector, fixture):
    """Fixed physical join; callers must separately bind their tree/vector domain."""
    argument = prefix._checked_argument(fixture)
    result = _normalize(lambda: prefix._expected(vector, fixture))
    prefix_result = copy.deepcopy(result)
    pages = {p: bytearray(v) for p, v in result["pages"].items()}
    events = list(result["events"])
    regs = dict(result["registers"])

    def read(a):
        value = int.from_bytes(
            bytes(pages[(a + i) & ~0xFFF][(a + i) & 0xFFF] for i in range(4)), "little"
        )
        events.append(dict(access="read", address=a, width=4, value=value))
        return value

    def write(a, value):
        events.append(dict(access="write", address=a, width=4, value=value))
        for i, b in enumerate(value.to_bytes(4, "little")):
            pages[(a + i) & ~0xFFF][(a + i) & 0xFFF] = b

    frame = fixture["stack"] - 4
    receiver = read(frame - 12)
    _require(
        receiver == RECEIVER and regs["edi"] == argument,
        "external append receiver differs",
    )
    old_end = read(receiver + 8)
    _require(
        old_end == read(receiver + 12) == fixture["old_begin"] + 8 * vector["old_size"]
        and argument >= old_end,
        "old vector is not full and external",
    )
    # PUSH ECX passes an unused dummy; growth and every allocation/copy instruction remain native.
    write(frame - 36, regs["ecx"])
    write(frame - 40, BASE + 0x2EB205)
    regs.update(eax=old_end, esi=receiver, ecx=receiver + 4, esp=frame - 40)
    growth_entry = _boundary(
        regs, fixture["xmm"], pages, events, BASE + 0x2EB620, 0x246, 0xFFFFFFFF
    )
    inputs = dict(
        pages=_pages(pages),
        registers=dict(regs),
        xmm=dict(fixture["xmm"]),
        source=fixture["old_begin"],
        destination=fixture["vector_begin"],
        object_address=receiver + 4,
        return_address=BASE + 0x2EB205,
        entry_flags=0x246,
    )
    predicted_child = _growth_packet_law(**inputs)
    child = _normalize(lambda: model.apply(**inputs))
    _require(_same_packet(child, predicted_child), "class6 to7 growth join differs")
    events.extend(child["events"])
    pages = {page: bytearray(data) for page, data in child["pages"].items()}
    regs = dict(child["registers"])
    _require(
        regs["esp"] == frame - 32 and regs["edi"] == argument,
        "class6 to7 growth ABI differs",
    )
    growth_return = _boundary(
        regs,
        child["xmm"],
        pages,
        events,
        BASE + 0x2EB205,
        child["flags"],
        child["flag_mask"],
    )
    end = read(receiver + 8)
    _require(
        end == fixture["vector_end"] and end != 0, "grown vector allocation differs"
    )
    first = read(argument)
    write(end, first)
    second = read(argument + 4)
    write(end + 4, second)
    write(receiver + 8, read(receiver + 8) + 8)
    regs.update(eax=second, ecx=end, esi=receiver)
    cookie = vector["cookie"]
    suffix = returned._expected(
        dict(
            frame=frame,
            cookie=cookie,
            current=cookie,
            relation=returned.return_spec(
                frame, cookie, cookie, return_address=fixture["return_address"]
            ),
            saved={r: fixture["registers"][r] for r in ("edi", "esi", "ebx", "ebp")},
            registers=regs,
            stack=bytes(pages[construction.STACK] + pages[construction.STACK + 0x1000]),
            stack_base=construction.STACK,
        )
    )
    events.extend(suffix["events"])
    for i, p in enumerate((construction.STACK, construction.STACK + 0x1000)):
        pages[p] = bytearray(suffix["stack"][4096 * i : 4096 * (i + 1)])
    result["tree_heap_count"] = len(result["heap_nodes"])
    result["heap_nodes"] = result["heap_nodes"] + [fixture["vector_begin"]]
    result.update(
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        registers=suffix["registers"],
        flags=suffix["flags"],
        endpoint=fixture["return_address"],
        xmm=dict(child["xmm"]),
        df=0,
        growth_entry=growth_entry,
        growth_return=growth_return,
        growth_packet=copy.deepcopy(child),
        prefix_packet=copy.deepcopy(prefix_result),
    )
    _require(
        result["pages"] == _model_pages(fixture, result),
        "independent class append differs",
    )
    return result


def _model_pages(fixture, expected):
    pages = {p: bytearray(v) for p, v in prefix._model_pages(fixture, expected).items()}
    for i in range(8 * fixture["old_size"]):
        at = fixture["old_begin"] + i
        target = fixture["vector_begin"] + i
        pages[target & ~0xFFF][target & 0xFFF] = fixture["pages"][at & ~0xFFF][
            at & 0xFFF
        ]
    # The vector model appends the unchanged two-word argument as a record.
    argument = prefix._checked_argument(fixture)
    record = bytes(
        fixture["pages"][(argument + i) & ~0xFFF][(argument + i) & 0xFFF]
        for i in range(8)
    )
    for i, b in enumerate(record):
        a = fixture["vector_end"] + i
        pages[a & ~0xFFF][a & 0xFFF] = b
    for offset, value in (
        (4, fixture["vector_begin"]),
        (8, fixture["vector_end"] + 8),
        (12, fixture["vector_capacity"]),
    ):
        for i, b in enumerate(value.to_bytes(4, "little")):
            a = RECEIVER + offset + i
            pages[a & ~0xFFF][a & 0xFFF] = b
    return {p: bytes(v) for p, v in pages.items()}


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "class6 to7 source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        ids = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[key]["build_identity"], identity)
                for key in SOURCE_PINS
                if key != "program_facts"
            ),
            "class6 to7 source build differs",
        )
        old_ids = legacy._preflight({key: sources[key] for key in legacy.SOURCE_PINS})
        new_ids = growth._preflight({key: sources[key] for key in growth.SOURCE_PINS})
        _require(
            _same_packet(sources["class_simd_return"]["source_receipts"], old_ids)
            and _same_packet(sources["growth6_to9"]["source_receipts"], new_ids),
            "class6 to7 source join differs",
        )
        return ids

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        _preflight(sources)
        codes, points, selected = legacy._load_code(
            data, image, {key: sources[key] for key in legacy.SOURCE_PINS}
        )
        children, child_points = growth._load_code(
            data, image, {key: sources[key] for key in growth.SOURCE_PINS}
        )
        bytes_map = {}
        for start, payload in list(codes.items()) + [
            (growth.BODIES[name][0], payload) for name, payload in children.items()
        ]:
            for i, value in enumerate(payload):
                _require(
                    start + i not in bytes_map or bytes_map[start + i] == value,
                    "class6 to7 code byte conflict",
                )
                bytes_map[start + i] = value
        rows = {}
        for point in points + [p for batch in child_points.values() for p in batch]:
            _require(
                point["rva"] not in rows or _same_packet(rows[point["rva"]], point),
                "class6 to7 code point conflict",
            )
            rows[point["rva"]] = point
        merged = {a: bytes(bytes_map[i] for i in range(a, b)) for a, b in BODIES}
        _require(
            set(bytes_map) == {i for a, b in BODIES for i in range(a, b)},
            "class6 to7 selected ranges differ",
        )
        ordered = sorted(rows.values(), key=lambda p: int(p["rva"], 16))
        _checked_code_packet(merged, ordered)
        return merged, ordered, selected

    return _normalize(run)


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and set(codes) == {a for a, b in BODIES}
            and type(points) is list,
            "class6 to7 code packet differs",
        )
        _require(
            _canonical_sha256(points) == POINTS_SHA256,
            "class6 to7 direct point identity differs",
        )
        allowed = {}
        for a, b in BODIES:
            _require(
                type(codes[a]) is bytes and len(codes[a]) == b - a,
                "class6 to7 direct code extent differs",
            )
            cursor = a
            for p in (p for p in points if a <= int(p["rva"], 16) < b):
                _require(
                    type(p) is dict
                    and set(p) == {"rva", "size", "sha256"}
                    and type(p["size"]) is int
                    and p["size"] > 0
                    and type(p["rva"]) is str
                    and type(p["sha256"]) is str,
                    "class6 to7 direct point schema differs",
                )
                pc = int(p["rva"], 16)
                _require(
                    pc == cursor
                    and pc + p["size"] <= b
                    and hashlib.sha256(
                        codes[a][pc - a : pc - a + p["size"]]
                    ).hexdigest()
                    == p["sha256"],
                    "class6 to7 direct instruction bytes differ",
                )
                allowed[pc] = p
                cursor += p["size"]
            _require(cursor == b, "class6 to7 direct point extent differs")
        _require(
            len(allowed) == len(points), "class6 to7 direct point partition differs"
        )
        return allowed

    return _normalize(run)


def _check_boundary(machine, ids, xmm_ids, x, boundary, events, label):
    _require(
        _same_packet(
            {name: machine.reg_read(reg) for name, reg in ids.items()},
            boundary["registers"],
        )
        and _same_packet(
            {name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
            boundary["xmm"],
        )
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & boundary["flag_mask"]
        == boundary["flags"] & boundary["flag_mask"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == boundary["endpoint"]
        and _same_packet(events, boundary["events"])
        and all(
            bytes(machine.mem_read(page, 4096)) == data
            for page, data in boundary["pages"].items()
        ),
        "class6 to7 " + label + " differs",
    )


CONTROLS = {
    **{
        name: "class6 to7 growth entry differs"
        for name in (
            "growth_entry_gpr",
            "growth_entry_xmm",
            "growth_entry_flags",
            "growth_entry_df",
            "growth_entry_page",
        )
    },
    **{
        name: "class6 to7 growth return differs"
        for name in (
            "growth_return_gpr",
            "growth_return_xmm",
            "growth_return_flags",
            "growth_return_df",
            "growth_return_page",
        )
    },
    "heap_response": "class6 to7 supplied response preservation differs",
    "source": "class6 to7 final pages differ",
    "payload": "class6 to7 final pages differ",
    "vector": "class6 to7 final pages differ",
    "iterator": "class6 to7 final pages differ",
    "argument": "class6 to7 final pages differ",
    "cookie": "class6 to7 cookie first failure frontier",
    "resize_request": "class6 to7 resize entry differs",
    "child_tail": "class6 to7 copy return differs",
    "caller_argument": "class6 to7 final pages differ",
    **{
        name: "class6 to7 resize entry differs"
        for name in (
            "resize_entry_gpr",
            "resize_entry_xmm",
            "resize_entry_df",
            "resize_entry_flags",
            "resize_entry_page",
        )
    },
    **{
        name: "class6 to7 resize return differs"
        for name in (
            "resize_return_gpr",
            "resize_return_xmm",
            "resize_return_df",
            "resize_return_flags",
            "resize_return_page",
        )
    },
    **{
        name: "class6 to7 copy entry differs"
        for name in (
            "copy_entry_gpr",
            "copy_entry_xmm",
            "copy_entry_df",
            "copy_entry_flags",
            "copy_entry_page",
        )
    },
    **{
        name: "class6 to7 copy return differs"
        for name in (
            "copy_return_gpr",
            "copy_return_xmm",
            "copy_return_flags",
            "copy_return_df",
            "copy_return_page",
        )
    },
    "allocation_request": "class6 to7 allocation handoff differs",
    "free_request": "class6 to7 free handoff differs",
    "allocation_entry": "class6 to7 allocation entry differs",
    "allocation_return": "class6 to7 allocation return differs",
    "free_entry": "class6 to7 free entry differs",
    **{
        name: "class6 to7 final pages differ"
        for name in (
            "header",
            "spare",
            "old",
            "feature_padding",
            "ancestor",
            "iat_padding",
            "error",
        )
    },
    "final_gpr": "class6 to7 final ABI differs",
    "final_xmm": "class6 to7 final ABI differs",
    "final_df": "class6 to7 final ABI differs",
    "final_flags": "class6 to7 final ABI differs",
    **{
        name: "class6 to7 final events differ"
        for name in (
            "missing_half_record",
            "scalar_order_record",
            "restored_write_record",
        )
    },
    "trace_record": "class6 to7 final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid class6 to7 control",
    )
    fixture = _fixture(vector)
    combined = _expected(vector, fixture)
    expected = copy.deepcopy(combined["growth_packet"])
    before_growth = combined["growth_entry"]["events"]
    for field in (
        "allocation_entry",
        "copy_entry",
        "free_entry",
        "resize_entry",
        "resize_return",
    ):
        expected[field]["events"] = (
            copy.deepcopy(before_growth) + expected[field]["events"]
        )
    expected.update(
        events=combined["events"],
        registers=combined["registers"],
        xmm=combined["xmm"],
        flags=combined["flags"],
        pages=combined["pages"],
        endpoint=combined["endpoint"],
    )
    expected["tail_trace"] = (
        [
            f"0x{pc:08x}"
            for pc in (
                0x2EB1BB,
                0x2EB1BE,
                0x2EB1C1,
                0x2EB1C3,
                0x2EB1F7,
                0x2EB1FA,
                0x2EB1FC,
                0x2EB1FD,
                0x2EB200,
            )
        ]
        + combined["growth_packet"]["trace_rvas"]
        + [
            f"0x{pc:08x}"
            for pc in (
                0x2EB205,
                0x2EB208,
                0x2EB20A,
                0x2EB20C,
                0x2EB20E,
                0x2EB210,
                0x2EB213,
                0x2EB216,
                0x2EB21A,
                0x2EB21D,
                0x2EB21E,
                0x2EB21F,
                0x2EB221,
                0x2EB222,
                0x3574CA,
                0x3574D0,
                0x3574D3,
                0x2EB227,
                0x2EB229,
                0x2EB22A,
            )
        ]
    )
    prefix_boundary = _boundary(
        combined["prefix_packet"]["registers"],
        fixture["xmm"],
        combined["prefix_packet"]["pages"],
        combined["prefix_packet"]["events"],
        BASE + prefix.STOP,
        0x44,
        0xCC5,
    )
    wanted_events = combined["events"]
    if negative == "cookie":
        wanted_events = combined["events"][:-4] + [
            dict(
                access="read",
                address=returned.COOKIE,
                width=4,
                value=vector["cookie"] ^ 1,
            )
        ]
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "class6 to7 reviewed Unicorn required")
    allowed = _checked_code_packet(codes, points)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    code_pages = {
        (BASE + address) & ~4095
        for start, end in BODIES
        for address in range(start, end)
    } | {fixture["return_address"] & ~4095, IMPORT}
    _require(
        not code_pages.intersection(fixture["pages"]),
        "class6 to7 runtime mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, data in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    for start, payload in codes.items():
        machine.mem_write(BASE + start, payload)
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    g, s = expected["geometry"], fixture["stack"] - 64
    events, visited, summaries, boundaries = [], [], [], []
    resume = None
    tail_visited = []

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    def observe_boundary(name, boundary):
        flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
        boundaries.append(
            dict(
                name=name,
                registers={name: machine.reg_read(reg) for name, reg in ids.items()},
                xmm={name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
                eflags=flags,
                flags=flags & boundary["flag_mask"],
                flag_mask=boundary["flag_mask"],
                df=(flags >> 10) & 1,
                endpoint=machine.reg_read(x.UC_X86_REG_EIP),
                pages_sha256=installed_copy._page_hashes(
                    {
                        page: bytes(machine.mem_read(page, 4096))
                        for page in fixture["pages"]
                    }
                ),
                events_sha256=_canonical_sha256(events),
            )
        )

    def mutate_boundary(prefix):
        if negative == prefix + "_gpr":
            machine.reg_write(ids["edx"], machine.reg_read(ids["edx"]) ^ 1)
        if negative == prefix + "_xmm":
            machine.reg_write(xmm_ids["xmm7"], machine.reg_read(xmm_ids["xmm7"]) ^ 1)
        if negative == prefix + "_df":
            machine.reg_write(
                x.UC_X86_REG_EFLAGS, machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x400
            )
        if negative == prefix + "_flags":
            machine.reg_write(
                x.UC_X86_REG_EFLAGS, machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 1
            )
        if negative == prefix + "_page":
            flip(ERROR + 1)

    def allocation_return_boundary():
        pages = {
            page: bytearray(data)
            for page, data in expected["allocation_entry"]["pages"].items()
        }
        _write(pages, STACK, expected["allocation_packet"]["stack"])
        return _boundary(
            expected["allocation_packet"]["registers"],
            fixture["xmm"],
            pages,
            expected["allocation_entry"]["events"]
            + expected["allocation_packet"]["events"],
            BASE + 0x2EB695,
            expected["allocation_packet"]["flags"],
            0x8D5,
        )

    def copy_return_boundary():
        p = expected["copy_packet"]
        return _boundary(
            p["registers"],
            p["xmm"],
            p["pages"],
            expected["copy_entry"]["events"] + p["events"],
            p["endpoint"],
            p["flags"],
            p["flag_mask"],
        )

    def on_code(m, address, size, user):
        nonlocal resume
        if address == BASE + 0x3574D5 and negative == "cookie":
            m.emu_stop()
            return
        if address == BASE + 0x2EB222 and negative == "cookie":
            m.mem_write(returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        if address == expected["endpoint"]:
            m.emu_stop()
            return
        if address == IMPORT:
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            index = len(summaries)
            _require(index < 2, "class6 to7 repeated heap response")
            role = "allocation" if index == 0 else "free"
            wanted = [
                BASE + (0x389463 if index == 0 else 0x389172),
                HEAP,
                0,
                72 if index == 0 else g["old_begin"],
            ]
            if negative == role + "_request":
                flip(sp + 12)
                words[3] ^= 1
            _require(
                sp == s - (76 if index == 0 else 68) and words == wanted,
                "class6 to7 " + role + " handoff differs",
            )
            initial = expected["resize_entry"]["registers"]
            expected_gpr = (
                dict(
                    initial, eax=72, ecx=(RECEIVER + 4), esi=72, ebp=s - 56, esp=s - 76
                )
                if index == 0
                else dict(
                    expected["free_entry"]["registers"],
                    eax=0x1FFFFFFF,
                    edx=7,
                    ebp=s - 52,
                    esp=s - 68,
                )
            )
            _require(
                _same_packet(
                    {name: m.reg_read(reg) for name, reg in ids.items()}, expected_gpr
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                    fixture["xmm"] if index == 0 else expected["xmm"],
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0,
                "class6 to7 " + role + " imported ABI differs",
            )
            flag_mask = 0x8C5 if index == 0 else 0x8D5
            flag_value = (
                4
                if index == 0
                else int((g["old_begin"] & 255).bit_count() % 2 == 0) << 2
            )
            _require(
                m.reg_read(x.UC_X86_REG_EFLAGS) & flag_mask == flag_value,
                "class6 to7 " + role + " imported flags differ",
            )
            before = {page: bytes(m.mem_read(page, 4096)) for page in fixture["pages"]}
            imported = dict(
                role=role,
                entry_esp=sp,
                words=list(words),
                registers={name: m.reg_read(reg) for name, reg in ids.items()},
                xmm={name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                eflags=m.reg_read(x.UC_X86_REG_EFLAGS),
                flags=m.reg_read(x.UC_X86_REG_EFLAGS) & flag_mask,
                flag_mask=flag_mask,
                df=(m.reg_read(x.UC_X86_REG_EFLAGS) >> 10) & 1,
                endpoint=m.reg_read(x.UC_X86_REG_EIP),
                pages_sha256=installed_copy._page_hashes(before),
                events_sha256=_canonical_sha256(events),
            )
            for name, value in (
                (
                    "eax",
                    (
                        (g["new_begin"] ^ int(negative == "heap_response"))
                        if index == 0
                        else 1
                    ),
                ),
                ("ecx", 0xA0000001),
                ("edx", 0xB0000001),
                ("esp", sp + 16),
            ):
                m.reg_write(ids[name], value)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            _require(
                all(
                    bytes(m.mem_read(page, 4096)) == data
                    for page, data in before.items()
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                    fixture["xmm"] if index == 0 else expected["xmm"],
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in ids.items()},
                    dict(
                        expected_gpr,
                        eax=g["new_begin"] if index == 0 else 1,
                        ecx=0xA0000001,
                        edx=0xB0000001,
                        esp=sp + 16,
                    ),
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) == 0x246,
                "class6 to7 supplied response preservation differs",
            )
            summaries.append(imported)
            resume = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "class6 to7 escaped selected code",
        )
        if pc == prefix.STOP:
            _check_boundary(m, ids, xmm_ids, x, prefix_boundary, events, "class prefix")
            observe_boundary("class_prefix", prefix_boundary)
        elif pc == 0x2EB620:
            mutate_boundary("growth_entry")
            _check_boundary(
                m, ids, xmm_ids, x, combined["growth_entry"], events, "growth entry"
            )
            observe_boundary("growth_entry", combined["growth_entry"])
        elif pc == 0x2EB205:
            mutate_boundary("growth_return")
            _check_boundary(
                m, ids, xmm_ids, x, combined["growth_return"], events, "growth return"
            )
            observe_boundary("growth_return", combined["growth_return"])
        elif pc == 0x2EB680:
            mutate_boundary("resize_entry")
            if negative == "resize_request":
                flip(s + 4)
            _require(
                m.reg_read(x.UC_X86_REG_EFLAGS) == 0x202,
                "class6 to7 resize entry differs",
            )
            _check_boundary(
                m, ids, xmm_ids, x, expected["resize_entry"], events, "resize entry"
            )
            observe_boundary("resize_entry", expected["resize_entry"])
        elif pc == 0x2EB66E:
            mutate_boundary("resize_return")
            _check_boundary(
                m, ids, xmm_ids, x, expected["resize_return"], events, "resize return"
            )
            observe_boundary("resize_return", expected["resize_return"])
        elif pc == 0x8A920:
            if negative == "allocation_entry":
                m.reg_write(ids["ecx"], 0)
            _check_boundary(
                m,
                ids,
                xmm_ids,
                x,
                expected["allocation_entry"],
                events,
                "allocation entry",
            )
            observe_boundary("allocation_entry", expected["allocation_entry"])
        elif pc == 0x2EB695:
            if negative == "allocation_return":
                m.reg_write(
                    ids["ecx"],
                    allocator.DATA + 0x800 + (vector["vector_alignment"] & 15),
                )
            state = allocation_return_boundary()
            _check_boundary(m, ids, xmm_ids, x, state, events, "allocation return")
            observe_boundary("allocation_return", state)
        elif pc == 0x36E580:
            mutate_boundary("copy_entry")
            _check_boundary(
                m, ids, xmm_ids, x, expected["copy_entry"], events, "copy entry"
            )
            observe_boundary("copy_entry", expected["copy_entry"])
        elif pc == 0x2EB6A6:
            mutate_boundary("copy_return")
            if negative == "child_tail":
                m.reg_write(
                    ids["edx"],
                    int.from_bytes(
                        _read(fixture["pages"], g["old_begin"] + 32, 4), "little"
                    ),
                )
            state = copy_return_boundary()
            _check_boundary(m, ids, xmm_ids, x, state, events, "copy return")
            observe_boundary("copy_return", state)
        elif pc == 0x7800:
            if negative == "free_entry":
                m.reg_write(ids["eax"], 4)
            _check_boundary(
                m, ids, xmm_ids, x, expected["free_entry"], events, "free entry"
            )
            observe_boundary("free_entry", expected["free_entry"])
        visited.append(f"0x{pc:08x}")
        if tail_visited or pc == prefix.STOP:
            tail_visited.append(f"0x{pc:08x}")
            _require(
                tail_visited == expected["tail_trace"][: len(tail_visited)],
                "class6 to7 native path differs",
            )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        _require(width in (1, 2, 4, 8), "class6 to7 access width differs")
        if width == 8:
            pc = m.reg_read(x.UC_X86_REG_EIP) - BASE
            halves = {
                0x36EA60: (False, g["old_begin"]),
                0x36EA64: (False, g["old_begin"] + 16),
                0x36EA69: (True, g["new_begin"]),
                0x36EA6D: (True, g["new_begin"] + 16),
            }
            _require(
                pc in halves
                and writing == halves[pc][0]
                and address in (halves[pc][1], halves[pc][1] + 8),
                "class6 to7 wide site differs",
            )
        actual = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & ((1 << (8 * width)) - 1)
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < len(wanted_events)
            and _same_packet(actual, wanted_events[len(events)]),
            "class6 to7 ordered memory events differ",
        )
        events.append(actual)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + START
    for _ in range(3):
        resume = None
        machine.emu_start(next_pc, 0, count=50000)
        if resume is None:
            break
        next_pc = resume
    if negative == "cookie":
        frame = fixture["stack"] - 4
        _require(
            machine.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5
            and machine.reg_read(ids["esp"]) == frame - 24,
            "class6 to7 cookie failure frontier differs",
        )
        failure = dict(combined["registers"], ebp=frame, esp=frame - 24)
        ff = returned.return_spec(frame, vector["cookie"], vector["cookie"] ^ 1)[
            "flags"
        ]
        _require(
            _same_packet(
                {name: machine.reg_read(reg) for name, reg in ids.items()}, failure
            )
            and _same_packet(
                {name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
                combined["xmm"],
            )
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x8D5 == ff
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0,
            "class6 to7 cookie failure ABI differs",
        )
        wanted = {page: bytearray(data) for page, data in combined["pages"].items()}
        _write(wanted, returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        _require(
            _same_packet(events, wanted_events)
            and all(
                bytes(machine.mem_read(page, 4096)) == bytes(data)
                for page, data in wanted.items()
            ),
            "class6 to7 cookie failure memory differs",
        )
        return dict(kind="cookie", rejected=True, endpoint="0x003574d5")
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"]
        and [row["role"] for row in summaries] == ["allocation", "free"]
        and [row["name"] for row in boundaries]
        == [
            "class_prefix",
            "growth_entry",
            "resize_entry",
            "allocation_entry",
            "allocation_return",
            "copy_entry",
            "copy_return",
            "free_entry",
            "resize_return",
            "growth_return",
        ],
        "class6 to7 endpoint or boundaries differ",
    )
    corrupt = {
        "header": (RECEIVER + 4),
        "spare": g["new_end"] + 8,
        "old": g["old_begin"] + 44,
        "feature_padding": FEATURE_PAGE + 1,
        "ancestor": fixture["stack"] + 8,
        "source": SOURCE_HEAD + 14,
        "argument": prefix._checked_argument(fixture),
        "iterator": fixture["stack"] - 12,
        "vector": g["new_end"],
        "caller_argument": combined["growth_entry"]["registers"]["esp"] + 4,
        "iat_padding": (ALLOC_IAT & ~4095) + 1,
        "error": ERROR + 1,
    }
    if negative == "payload" and combined["insertions"]:
        flip(combined["insertions"][-1]["destination_address"] + 20)
    if negative in corrupt:
        flip(corrupt[negative])
    if negative == "final_gpr":
        machine.reg_write(ids["edx"], 0)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm2"], machine.reg_read(xmm_ids["xmm2"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "final_flags" else 0x400),
        )
    copy_start = len(expected["copy_entry"]["events"])
    if negative == "missing_half_record":
        del events[copy_start + 6]
    if negative == "scalar_order_record":
        events[copy_start + 14], events[copy_start + 16] = (
            events[copy_start + 16],
            events[copy_start + 14],
        )
    if negative == "restored_write_record":
        original = int.from_bytes(fixture["pages"][ERROR][:4], "little")
        events.extend(
            [
                dict(access="write", address=ERROR, width=4, value=original ^ 1),
                dict(access="write", address=ERROR, width=4, value=original),
            ]
        )
    if negative == "trace_record":
        visited.append("0x0036ea9d")
        tail_visited.append("0x0036ea9d")
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    xmm = {name: machine.reg_read(reg) for name, reg in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    pages = {page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]}
    _require(
        _same_packet(regs, expected["registers"])
        and _same_packet(xmm, expected["xmm"])
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and flags & 0x400 == 0,
        "class6 to7 final ABI differs",
    )
    _require(_same_packet(pages, expected["pages"]), "class6 to7 final pages differ")
    _require(_same_packet(events, expected["events"]), "class6 to7 final events differ")
    _require(
        _same_packet(tail_visited, expected["tail_trace"]),
        "class6 to7 final native path differs",
    )
    result = dict(
        vector=dict(vector),
        registers=regs,
        xmm=xmm,
        flags=flags & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        summaries=summaries,
        boundaries=boundaries,
        pages_sha256=installed_copy._page_hashes(pages),
        memory_event_count=len(events),
        insertions=copy.deepcopy(combined["insertions"]),
        allocations=[
            dict(
                node=next(
                    b["registers"]["eax"]
                    for b in boundaries
                    if b["name"] == "allocation_return"
                ),
                entry_esp=summary["entry_esp"],
                request=summary["words"][3],
                continuation=summary["words"][0],
            )
            for summary in summaries
            if summary["role"] == "allocation"
        ],
        frees=[
            dict(
                pointer=summary["words"][3],
                entry_esp=summary["entry_esp"],
                result=1,
                continuation=summary["words"][0],
            )
            for summary in summaries
            if summary["role"] == "free"
        ],
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(combined), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(Path(executable)))
    codes, points, selected = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    sample = vectors()[-1]
    for name, reason in CONTROLS.items():
        if name == "cookie":
            controls.append(_run_case(codes, points, sample, name))
            continue
        try:
            _run_case(codes, points, sample, name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "class6 to7 incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("class6 to7 control survived: " + name)
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    _require(
        set(union) <= {p["rva"] for p in points}
        and {f"0x{pc:08x}" for pc in model.GROWTH_PREFIX}
        | {
            f"0x{pc:08x}"
            for pc in (
                0x2EB205,
                0x2EB20E,
                0x2EB213,
                0x2EB216,
                0x3574CA,
                0x36EA60,
                0x36EA64,
                0x36EA69,
                0x36EA6D,
                0x36EA80,
                0x36EA87,
                0x36EA89,
                0x36EA94,
            )
        }
        <= set(union),
        "class6 to7 native coverage differs",
    )
    _require(
        not any(
            0x2EB15F <= int(pc, 16) < 0x2EB179 or 0x2EB1C5 <= int(pc, 16) < 0x2EB1F7
            for pc in union
        ),
        "class6 to7 excluded arm executed",
    )
    n = len(observations)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    exclusive_end_rva=f"0x{a+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in codes.items()
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            loaded_bytes=sum(map(len, codes.values())),
            loaded_sites=len(points),
            executed_sites=len(union),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            tree_allocations=0,
            allocation_requests=n,
            free_requests=n,
            existing_insertions=sum(len(o["insertions"]) for o in observations),
            copied_bytes=48 * n,
            preserved_old_bytes=48 * n,
            allocated_bytes=72 * n,
            appended_bytes=8 * n,
            live_vector_bytes=56 * n,
            spare_bytes=16 * n,
            wide_reads=4 * n,
            wide_writes=4 * n,
            scalar_tail_reads=4 * n,
            scalar_tail_writes=4 * n,
            memory_events=sum(o["memory_event_count"] for o in observations),
            controls=len(controls),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Finite native existing-key class transfer full size6 capacity6 growth to capacity9 external record append size7 and normal caller return",
            premises=[
                "Canonical source and destination key sets have zero through seven existing nodes with no tree allocation",
                "Old48 source and fresh72 capacity are disjoint with retained feature selecting SIMD first32 and scalar last16",
                "Successful supplied HeapAlloc and HeapFree preserve full pages nonvolatile GPR and all eight XMM",
                "Independent complete21 growth and18 resize child packet laws bind actual installed frames and ordered events",
                "Tree prefix events full pages eight GPR and XMM are checked at actual join with inherited source routing contract",
            ],
            not_claimed=[
                "New keys assertion internal append arbitrary class fixture metadata allocation failure heap ownership hardware or factory callback7",
                "Injected record mutations do not establish execution of represented extra stores or sites",
                "Cookie mismatch stops before first failure helper instruction with no handler behavior or normal return claim",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class6 to7 executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], identities)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed class6 to7 receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
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
            _canonical_bytes(build_conformance(executable, sources))
            == _canonical_bytes(evidence),
            "exact class6 to7 receipt differs",
        )
        return dict(status="verified", evidence_sha256=SEALED_SHA256)

    return _normalize(run)


encode_conformance = growth.encode_conformance
