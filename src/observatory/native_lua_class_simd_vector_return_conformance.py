"""Fixed four-record native class transfer, SIMD growth, external append and return."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_empty_vector_return_conformance as empty
from src.observatory import native_lua_class_spare_return_conformance as spare
from src.observatory import native_simd_vector_growth_conformance as growth
from src.observatory import native_lua_class_old_vector_return_conformance as old
from src.observatory import native_lua_class_vector_return_conformance as returned
from src.observatory import native_lua_class_vector_append_semantics as append
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
)
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _decode_body,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_simd_vector_return_conformance"
SEALED_SHA256 = "f0ffcae4eec8beab14a2a24a6b6ecdd736ed523c39ea681ead624e4a7b98008f"
SOURCE_PINS = {
    **old.SOURCE_PINS,
    **growth.SOURCE_PINS,
    "old_vector_return": (old.ANALYSIS_KIND, old.SEALED_SHA256),
    "simd_growth": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
}

START = prefix.START
RECEIVER, ARGUMENT, SOURCE_HEAD = prefix.RECEIVER, prefix.ARGUMENT, prefix.SOURCE_HEAD
construction = prefix.construction
ConformanceError, _require = prefix.ConformanceError, prefix._require
SPARE_RANGES = ((0x2EB1BB, 0x2EB1CC), (0x2EB1F7, 0x2EB1FC), (0x2EB205, 0x2EB22D))
VECTOR_KEYS = {
    "profile",
    "source_keys",
    "destination_keys",
    "node_alignment",
    "frame_alignment",
    "nil_flag",
    "previous_seh",
    "cookie",
    "payload_seed",
    "vector_alignment",
    "old_size",
    "old_alignment",
    "xmm_profile",
}
FIXTURE_KEYS = {
    "addresses",
    "construction_vector",
    "destination_addresses",
    "destination_state",
    "memory",
    "new_base",
    "new_page_count",
    "node",
    "old_base",
    "old_begin",
    "old_size",
    "pages",
    "parent",
    "query_argument",
    "registers",
    "relation",
    "result",
    "return_address",
    "selector",
    "source_addresses",
    "source_state",
    "stack",
    "strings",
    "transfer",
    "tree",
    "vector_begin",
    "vector_capacity",
    "vector_end",
    "xmm",
}


def vectors():
    return [
        dict(v, vector_alignment=a, old_size=4, old_alignment=a, xmm_profile=p)
        for v in prefix.vectors()
        if v["profile"] == "all_existing"
        for a in (0, 7, 31)
        for p in (0, 1)
    ]


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
            type(vector[k]) is list and all(type(v) is int for v in vector[k])
            for k in ("source_keys", "destination_keys")
        )
        and vector in vectors()
        and vector["old_size"] == 4
        and type(vector["old_size"]) is int
        and type(vector["vector_alignment"]) is int
        and vector["vector_alignment"] in (0, 7, 31)
        and vector["old_alignment"] == vector["vector_alignment"]
        and type(vector["xmm_profile"]) is int
        and vector["xmm_profile"] in (0, 1),
        "outside fixed SIMD class geometry",
    )


def _fixture(vector, *, caller=None):
    _checked_vector(vector)
    fixture = prefix._fixture(vector, caller=caller)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    a = vector["vector_alignment"]
    old_begin, fresh = growth.OLD + 0x800 + a, growth.NEW + 0x800 + a

    def put(address, value, width=4):
        for i, b in enumerate(value.to_bytes(width, "little")):
            _require((address + i) & ~4095 in pages, "SIMD class fixture word unmapped")
            pages[(address + i) & ~4095][(address + i) & 4095] = b

    for offset, value in ((4, old_begin), (8, old_begin + 32), (12, old_begin + 32)):
        put(RECEIVER + offset, value)
    for i in range(8):
        put(
            old_begin + 4 * i,
            (0x91827364 ^ i * 0x1234567 ^ vector["xmm_profile"] * 0x7654321)
            & 0xFFFFFFFF,
        )
    put(growth.FREE_IAT, construction.IMPORT)
    feature = bytearray(b"\x93" * 4096)
    feature[0xF28:0xF2C] = vector["cookie"].to_bytes(4, "little")
    pages[growth.FEATURE_PAGE] = feature
    xmm = {
        f"xmm{i}": int.from_bytes(
            bytes(
                (i * 19 + j * 41 + vector["xmm_profile"] * 73) & 255 for j in range(16)
            ),
            "little",
        )
        for i in range(8)
    }
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        old_size=4,
        old_begin=old_begin,
        vector_begin=fresh,
        vector_end=fresh + 32,
        vector_capacity=fresh + 48,
        old_base=growth.OLD,
        new_base=growth.NEW,
        new_page_count=1,
        xmm=xmm,
    )
    return fixture


def _same_packet(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _same_packet(actual[k], v) for k, v in expected.items()
        )
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same_packet(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


def _growth_packet_law(
    vector, initial, xmm, stack, new, old_bytes, objects, error, feature
):
    """Class-side equations for every growth boundary, buffer and access."""
    s, obj = initial["esp"], RECEIVER + 4
    g = growth.geometry(vector)
    parent_stack = bytearray(stack)
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            at = address - construction.STACK
            parent_stack[at : at + 4] = value.to_bytes(4, "little")

    for address, value in ((s - 4, initial["esi"]), (s - 8, initial["edi"])):
        event("write", address, value)
    for address, value in (
        (obj + 8, g["old_capacity"]),
        (obj + 4, g["old_end"]),
        (obj, g["old_begin"]),
    ):
        event("read", address, value)
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 16, 6),
        (s - 20, BASE + 0x2EB66E),
    ):
        event("write", address, value)
    incoming = dict(
        initial, eax=6, ebx=0x1FFFFFFD, ecx=obj, edx=6, esi=obj, edi=4, esp=s - 20
    )
    predicted_stack, resize_events = growth._resize_memory_law(
        vector,
        incoming,
        xmm,
        bytes(parent_stack),
        new,
        old_bytes,
        objects,
        error,
        feature,
    )
    events.extend(resize_events)
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 8, initial["edi"]),
        (s - 4, initial["esi"]),
        (s, BASE + 0x2EB205),
    ):
        event("read", address, value)
    at = 0x800 + vector["vector_alignment"]
    snapshot = old_bytes[at : at + 32]
    predicted_new = bytearray(new)
    predicted_new[at : at + 32] = snapshot
    predicted_object = bytearray(objects)
    for offset, value in (
        (0, g["new_begin"]),
        (4, g["new_end"]),
        (8, g["new_capacity"]),
    ):
        at = obj - (RECEIVER & ~4095) + offset
        predicted_object[at : at + 4] = value.to_bytes(4, "little")
    return dict(
        geometry=g,
        registers=dict(
            initial, eax=g["new_end"], ecx=0xA0000001, edx=0xB0000001, esp=s + 8
        ),
        xmm=dict(
            xmm,
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:], "little"),
        ),
        flags=growth._add_flags(s - 52, 12),
        flag_mask=0x8D5,
        df=0,
        events=events,
        stack=predicted_stack,
        new=bytes(predicted_new),
        old=old_bytes,
        object=bytes(predicted_object),
        error=error,
        feature_page=feature,
        endpoint=BASE + 0x2EB205,
        resize_entry=incoming,
        copy_entry=dict(
            incoming,
            eax=g["new_begin"],
            ecx=32,
            edx=g["old_begin"],
            esi=obj,
            edi=g["new_begin"],
            ebp=s - 24,
            esp=s - 56,
        ),
        allocation_request=dict(
            continuation=BASE + 0x389463, handle=growth.HEAP, flags=0, bytes=48
        ),
        free_request=dict(
            continuation=BASE + 0x389172,
            handle=growth.HEAP,
            flags=0,
            pointer=g["old_begin"],
        ),
    )


def _expected(vector, fixture):
    _checked_vector(vector)
    _require(
        type(fixture) is dict and set(fixture) == FIXTURE_KEYS,
        "invalid SIMD class fixture schema",
    )
    _require(
        type(fixture.get("xmm")) is dict
        and set(fixture["xmm"]) == set(growth.XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in fixture["xmm"].values()),
        "invalid SIMD class XMM state",
    )
    _require(
        type(fixture.get("old_size")) is int
        and fixture["old_size"] == 4
        and type(vector["old_size"]) is int
        and vector["old_size"] == 4
        and fixture.get("new_base") == growth.NEW
        and fixture.get("old_base") == growth.OLD
        and fixture.get("new_page_count") == 1,
        "outside fixed SIMD class geometry",
    )
    new_page_count = fixture.get("new_page_count", 4)
    old_base = fixture.get("old_base", growth.OLD)
    new_base = fixture.get("new_base", construction.DATA)
    _require(
        type(new_page_count) is int
        and new_page_count in (1, 2, 4)
        and type(old_base) is int
        and old_base & 0xFFF == 0
        and old_base in fixture["pages"]
        and type(new_base) is int
        and 0 <= new_base <= 2**32 - 4096 * new_page_count
        and new_base & 0xFFF == 0
        and all(new_base + i * 4096 in fixture["pages"] for i in range(new_page_count))
        and new_base
        <= fixture["vector_begin"]
        <= fixture["vector_end"]
        <= fixture["vector_capacity"]
        <= new_base + 4096 * new_page_count,
        "invalid class old vector mapping",
    )
    argument = prefix._checked_argument(fixture)
    result = prefix._expected(vector, fixture)
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
    a = vector["vector_alignment"]
    child_vector = dict(
        profile=vector["xmm_profile"],
        vector_alignment=a,
        stack_alignment=vector["frame_alignment"],
    )
    _require(
        fixture["old_begin"] == growth.OLD + 0x800 + a
        and fixture["vector_begin"] == growth.NEW + 0x800 + a
        and fixture["vector_end"] == fixture["vector_begin"] + 32
        and fixture["vector_capacity"] == fixture["vector_begin"] + 48,
        "SIMD class pointer geometry differs",
    )
    growth_entry = dict(regs)
    child = growth._expected(
        child_vector,
        regs,
        fixture["xmm"],
        bytes(pages[construction.STACK] + pages[construction.STACK + 4096]),
        bytes(pages[new_base]),
        bytes(pages[old_base]),
        bytes(pages[RECEIVER & ~4095]),
        bytes(pages[growth.ERROR]),
        bytes(pages[growth.FEATURE_PAGE]),
        return_address=BASE + 0x2EB205,
    )
    predicted_child = _growth_packet_law(
        child_vector,
        regs,
        fixture["xmm"],
        bytes(pages[construction.STACK] + pages[construction.STACK + 4096]),
        bytes(pages[new_base]),
        bytes(pages[old_base]),
        bytes(pages[RECEIVER & ~4095]),
        bytes(pages[growth.ERROR]),
        bytes(pages[growth.FEATURE_PAGE]),
    )
    _require(
        _same_packet(child, predicted_child),
        "class SIMD growth join differs",
    )
    events.extend(child["events"])
    for i in range(2):
        pages[construction.STACK + i * 4096] = bytearray(
            child["stack"][4096 * i : 4096 * (i + 1)]
        )
    for i in range(new_page_count):
        pages[new_base + i * 4096] = bytearray(child["new"][4096 * i : 4096 * (i + 1)])
    pages[RECEIVER & ~0xFFF] = bytearray(child["object"])
    regs = dict(child["registers"])
    _require(
        regs["esp"] == frame - 32 and regs["edi"] == argument,
        "class growth ABI differs",
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
        resize_entry=dict(child["resize_entry"]),
        copy_entry=dict(child["copy_entry"]),
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


def _run_case(codes, points, vector, negative=None, *, fixture=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector) if fixture is None else fixture
    expected = _expected(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, payload)
    code_pages = {
        (BASE + a + i) & ~0xFFF
        for a, payload in codes.items()
        for i in range(len(payload))
    }
    for page in sorted(code_pages):
        _require(page not in fixture["pages"], "class code overlaps data")
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    for address, payload in codes.items():
        machine.mem_write(BASE + address, payload)
    endpoint_page = expected["endpoint"] & ~0xFFF
    _require(
        endpoint_page not in code_pages and endpoint_page not in fixture["pages"],
        "return endpoint overlaps mapping",
    )
    machine.mem_map(endpoint_page, 0x1000)
    machine.mem_write(endpoint_page, b"\xcc" * 0x1000)
    machine.mem_map(construction.IMPORT, 0x1000)
    machine.mem_write(construction.IMPORT, b"\xcc")
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for register, value in fixture["registers"].items():
        machine.reg_write(ids[register], value)
    xmm_ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in growth.XMM}
    for r, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, allocations, frees = [], [], [], []
    frame = fixture["stack"] - 4
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == construction.IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            api_return = int.from_bytes(m.mem_read(sp, 4), "little")
            if api_return == BASE + 0x389172:
                if negative == "heap_free_request":
                    m.mem_write(
                        sp + 12, (fixture["old_begin"] ^ 1).to_bytes(4, "little")
                    )
                words = [
                    int.from_bytes(m.mem_read(sp + i * 4, 4), "little")
                    for i in range(4)
                ]
                _require(
                    len(frees) == 0
                    and len(allocations) == len(expected["heap_nodes"])
                    and sp == frame - 128
                    and words
                    == [BASE + 0x389172, construction.HEAP, 0, fixture["old_begin"]],
                    "class free handoff differs",
                )
                for register, value in (
                    (x.UC_X86_REG_EAX, 1),
                    (x.UC_X86_REG_ECX, 0xA0000001),
                    (x.UC_X86_REG_EDX, 0xB0000001),
                    (x.UC_X86_REG_EFLAGS, 0x246),
                    (x.UC_X86_REG_ESP, sp + 16),
                ):
                    m.reg_write(register, value)
                frees.append(
                    dict(
                        pointer=words[3], entry_esp=sp, result=1, continuation=words[0]
                    )
                )
                resume = words[0]
                m.emu_stop()
                return
            if (
                negative == "heap_request"
                and len(allocations) == expected["tree_heap_count"]
            ):
                m.mem_write(sp + 12, (9).to_bytes(4, "little"))
            words = [
                int.from_bytes(m.mem_read(sp + i * 4, 4), "little") for i in range(4)
            ]
            tree_allocation = len(allocations) < expected["tree_heap_count"]
            request = 24 if tree_allocation else 48
            _require(
                len(allocations) < len(expected["heap_nodes"])
                and sp == frame - (140 if tree_allocation else 136)
                and words == [BASE + 0x389463, construction.HEAP, 0, request],
                "class heap handoff differs",
            )
            node = expected["heap_nodes"][len(allocations)]
            if negative == "heap_response" and not tree_allocation:
                node ^= 1
            for register, value in (
                (x.UC_X86_REG_EAX, node),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                m.reg_write(register, value)
            allocations.append(
                dict(node=node, entry_esp=sp, request=request, continuation=words[0])
            )
            resume = words[0]
            m.emu_stop()
            return
        if address == BASE + 0x3574D5 and negative == "cookie":
            m.emu_stop()
            return
        if address == BASE + 0x2EB222 and negative == "cookie":
            m.mem_write(returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        if address == expected["endpoint"]:
            if negative == "argument":
                at = prefix._checked_argument(fixture)
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "iterator":
                m.mem_write(frame - 8, (SOURCE_HEAD ^ 1).to_bytes(4, "little"))
            if negative == "payload":
                last = expected["insertions"][-1]
                m.mem_write(
                    last["destination_address"] + 20,
                    (last["payload"] ^ 1).to_bytes(4, "little"),
                )
            if negative == "xmm":
                m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
            if negative == "spare":
                at = fixture["vector_end"] + 8
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "old":
                at = fixture["old_begin"]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "vector":
                at = fixture["vector_end"]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            m.emu_stop()
            return
        pc = address - BASE
        for boundary, field in (
            (0x2EB620, "growth_entry"),
            (0x2EB680, "resize_entry"),
            (growth.simd.START, "copy_entry"),
        ):
            if pc == boundary:
                _require(
                    {r: m.reg_read(i) for r, i in ids.items()} == expected[field],
                    "class SIMD boundary differs",
                )
        _require(pc in allowed, "class prefix escaped selected bodies")
        visited.append(f"0x{pc:08x}")
        if pc == START and negative in ("ancestor", "source"):
            at = fixture["stack"] + 8 if negative == "ancestor" else SOURCE_HEAD + 14
            m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 2, 4, 8), "unexpected class memory width")
        if width == 8:
            pc = m.reg_read(x.UC_X86_REG_EIP) - BASE
            writing = access == uc.UC_MEM_WRITE
            half = {
                0x36EA60: (False, fixture["old_begin"]),
                0x36EA64: (False, fixture["old_begin"] + 16),
                0x36EA69: (True, fixture["vector_begin"]),
                0x36EA6D: (True, fixture["vector_begin"] + 16),
            }
            _require(
                pc in half
                and writing == half[pc][0]
                and address in (half[pc][1], half[pc][1] + 8),
                "class SIMD access differs",
            )
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value & ((1 << (8 * width)) - 1)
                    if writing
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + START
    for _ in range(len(expected["heap_nodes"]) + 2):
        resume = None
        machine.emu_start(next_pc, 0, count=50000)
        if resume is None:
            break
        next_pc = resume
    if negative == "cookie":
        _require(
            machine.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5
            and machine.reg_read(x.UC_X86_REG_ESP) == frame - 24,
            "class cookie failure frontier differs",
        )
        _require(
            events
            == expected["events"][: -3 - 1]
            + [
                dict(
                    access="read",
                    address=returned.COOKIE,
                    width=4,
                    value=vector["cookie"] ^ 1,
                )
            ],
            "class cookie prefix events differ",
        )
        failure_regs = dict(expected["registers"], ebp=frame, esp=frame - 24)
        failure_flags = returned.return_spec(
            frame, vector["cookie"], vector["cookie"] ^ 1
        )["flags"]
        _require(
            {r: machine.reg_read(i) for r, i in ids.items()} == failure_regs
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x8D5 == failure_flags
            and not machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
            "class cookie failure ABI differs",
        )
        failure_pages = {p: bytearray(v) for p, v in expected["pages"].items()}
        for i, b in enumerate((vector["cookie"] ^ 1).to_bytes(4, "little")):
            at = returned.COOKIE + i
            failure_pages[at & ~0xFFF][at & 0xFFF] = b
        _require(
            all(
                bytes(machine.mem_read(p, 4096)) == bytes(v)
                for p, v in failure_pages.items()
            ),
            "class cookie failure memory differs",
        )
        return dict(kind="cookie", rejected=True, endpoint="0x003574d5")
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "class prefix endpoint differs",
    )
    _require(
        len(allocations) == len(expected["heap_nodes"]) and len(frees) == 1,
        "class allocation count differs",
    )
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"]
        and not flags & 0x400,
        "class registers or flags differ",
    )
    _require(
        {r: machine.reg_read(i) for r, i in xmm_ids.items()} == expected["xmm"],
        "class XMM differs",
    )
    _require(events == expected["events"], "class ordered events differ")
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class ancestor memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class protected memory differs",
    )
    return dict(
        vector=dict(vector),
        xmm={r: machine.reg_read(i) for r, i in xmm_ids.items()},
        df=(flags >> 10) & 1,
        registers=actual,
        flags=flags & 0x8D5,
        trace_rvas=visited,
        insertions=expected["insertions"],
        allocations=allocations,
        frees=frees,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "class SIMD source partition differs",
    )
    try:
        return {
            key: _source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
    except NativeLuaClassReturnHelperChainError as exc:
        raise ConformanceError(str(exc)) from exc


def _load_code(data, image, sources):
    codes, points, selected = old._load_code(
        data, image, {k: sources[k] for k in old.SOURCE_PINS}
    )
    simd_codes, simd_points = growth._load_code(
        data, image, {k: sources[k] for k in growth.SOURCE_PINS}
    )
    byte_map, point_map = {}, {}
    for batches in (
        [(a, b) for a, b in codes.items()],
        [(growth.BODIES[n][0], b) for n, b in simd_codes.items()],
    ):
        for a, b in batches:
            for i, value in enumerate(b):
                _require(
                    a + i not in byte_map or byte_map[a + i] == value,
                    "class SIMD byte conflict",
                )
                byte_map[a + i] = value
    for batch in (points, [p for rows in simd_points.values() for p in rows]):
        for p in batch:
            _require(
                p["rva"] not in point_map or point_map[p["rva"]] == p,
                "class SIMD point conflict",
            )
            point_map[p["rva"]] = p
    merged = {}
    for address in sorted(byte_map):
        if not merged or address != begin + len(merged[begin]):
            begin = address
            merged[begin] = bytearray()
        merged[begin].append(byte_map[address])
    return (
        {a: bytes(b) for a, b in merged.items()},
        sorted(point_map.values(), key=lambda p: int(p["rva"], 16)),
        selected,
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact class spare executable differs",
    )
    codes, points, selected = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    # Fixed four-record vectors use retained-feature SIMD32 and one successful free.
    required = {
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
            0x2EB205,
            0x2EB208,
            0x2EB20A,
            0x2EB20C,
            0x2EB20E,
            0x2EB210,
            0x2EB213,
            0x2EB216,
            0x2EB21A,
            0x2EB222,
            0x2EB22A,
            0x2EB620,
            0x2EB669,
            0x2EB680,
            0x2EB6A6,
            0x3574CA,
        )
    }
    required |= {"0x0036e5b1", "0x0036ea60", "0x0036ea64", "0x0036ea69", "0x0036ea6d"}
    required |= {
        p["rva"] for p in selected if not 0x2EB1C5 <= int(p["rva"], 16) < 0x2EB1CC
    }
    required |= {
        p["rva"]
        for p in points
        if START <= int(p["rva"], 16) < prefix.STOP
        and not 0x2EB15F <= int(p["rva"], 16) < 0x2EB179
    }
    required |= {
        f"0x{pc:08x}"
        for pc in (0x7800, 0x7851, 0x35785D, 0x36FB17, 0x389156, 0x38916C, 0x389172)
    }
    _require(required <= set(union), "class old vector normal coverage differs")
    _require(
        not any(
            0x2EB15F <= int(pc, 16) < 0x2EB179 or 0x2EB1C5 <= int(pc, 16) < 0x2EB1F7
            for pc in union
        ),
        "excluded class arm executed",
    )
    sample = next(
        v
        for v in vectors()
        if v["source_keys"]
        and v["profile"] == "all_existing"
        and v["vector_alignment"] == 31
        and v["old_size"] == 4
    )
    controls = []
    for kind, message in (
        ("ancestor", "class ancestor memory differs"),
        ("source", "class protected memory differs"),
        ("payload", "class protected memory differs"),
        ("vector", "class protected memory differs"),
        ("iterator", "class ancestor memory differs"),
        ("heap_request", "class heap handoff differs"),
        ("heap_response", "class SIMD boundary differs"),
        ("old", "class protected memory differs"),
        ("heap_free_request", "class free handoff differs"),
        ("xmm", "class XMM differs"),
        ("spare", "class protected memory differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "class spare mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("class spare mutation survived")
    controls.append(_run_case(codes, points, sample, "cookie"))
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(b):08x}")
                for a, b in codes.items()
            ],
            points=points,
            old_vector_return_points=selected,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=sum(map(len, codes.values())),
            static_sites=len(points),
            executed_sites=len(union),
            allocation_requests=len(observations),
            grown_vector_records=sum(v["old_size"] + 1 for v in vectors()),
            free_requests=sum(len(o["frees"]) for o in observations),
            iterations=sum(len(o["insertions"]) for o in observations),
            allocated_insertions=sum(len(o["allocations"]) - 1 for o in observations),
            existing_insertions=sum(
                sum(not i["inserted"] for i in o["insertions"]) for o in observations
            ),
            max_iterations=max(len(o["insertions"]) for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native existing-key class transfer full four-record SIMD vector growth external append and normal caller return on a finite canonical corpus",
            premises=[
                "Source and destination initially have equal sets of at most seven canonical nodes with fixed hexadecimal keys and stable DWORD payloads; every transfer updates an existing destination",
                "Vector initially contains four old records with size equal to capacity; one fresh48 block retains32 bytes and appends the external eight-byte argument",
                "Independent tree transfer and record append models check all final protected pages; ordered reads and writes and final ABI are exact",
                "Every descendant instruction is native except supplied successful HeapAlloc and HeapFree responses; old storage is preserved and DF clear with final cookie equal",
                "Supplied heap responses preserve all eight XMM registers; the selected SIMD copy defines XMM0 and XMM1 and preserves XMM2 through XMM7",
            ],
            not_claimed=[
                "Assertion internal argument new-key tree insertion other old record counts allocator metadata failed allocation or deallocation exceptions arbitrary strings aliased trees hardware execution or factory callback composition",
                "Cookie mismatch is checked only through the exact first failure frontier, not failure handler behavior or a normal return",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class spare executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed class spare return differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_conformance(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_conformance(executable, sources))
        == _canonical_bytes(evidence),
        "exact class spare return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
