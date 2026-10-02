"""Finite continuous native returned-class callback with supplied API contracts."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_spare_return_conformance as spare
from src.observatory import native_lua_class_marker_conformance as marker
from src.observatory import native_lua_table_transfer_conformance as table
from src.observatory import native_lua_shared_api_layout as layout
from src.observatory import native_lua_class_callback_semantics as model
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

ANALYSIS_KIND = "pe_native_lua_class_callback_conformance"
SEALED_SHA256 = "e4bc62a4677e0bf190d861cc1749fc0346ee048c8cb39d112ed2c4a36f151cfa"
SOURCE_PINS = {
    "program_facts": spare.SOURCE_PINS["program_facts"],
    "factory_chain": (
        "pe_native_lua_class_factory_chain",
        "824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc",
    ),
    "class_spare": (spare.ANALYSIS_KIND, spare.SEALED_SHA256),
    "marker": (marker.ANALYSIS_KIND, marker.SEALED_SHA256),
    "table": (table.ANALYSIS_KIND, table.SEALED_SHA256),
}
START, END, RETURN = 0x2EC110, 0x2EC21D, 0x0400A000
BODY_SHA256 = "a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3"
CFG_SHA256 = "c1212e08e59965211c3691fc52551f88f3441ba801bcfa7fe599afcb775dd55b"
ConformanceError, _require = spare.ConformanceError, spare._require
STACK = spare.construction.STACK
SOURCE_OBJECT = spare.prefix.SOURCE_OBJECT
RECEIVER = spare.RECEIVER
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
CLASS_ARGUMENT_BELOW_END_SITES = {"0x002eb1c5", "0x002eb1c8", "0x002eb1ca"}
TRANSFER_PAIRS = (
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
)


def vectors():
    result = []
    for i, v in enumerate(spare.prefix.vectors()):
        for j, transfers in enumerate(TRANSFER_PAIRS):
            variant = i + j
            result.append(
                dict(
                    v,
                    buffer_address=(0x13000100, 0x16000100)[variant % 2],
                    old_size=(0, 1, 3)[variant % 3],
                    spare_records=1 + variant % 2,
                    transfers=copy.deepcopy(list(transfers)),
                    marker_words=list(
                        ((0, 0), (0x12345678, 0xFFFFFFFF), (0xFFFFFFFF, 0x12345678))[
                            variant % 3
                        ]
                    ),
                    source_word=(0, 0x12345678, 0xFFFFFFFF)[variant % 3],
                    destination_word=(1, 0x87654321, 0)[variant % 3],
                    destination_refs=[
                        17 + 100 * (variant % 2),
                        19 + 100 * (variant % 2),
                    ],
                    source_refs=[23 + 100 * (variant % 2), 29 + 100 * (variant % 2)],
                )
            )
    return result


def _raw(pages, address, width=4):
    return int.from_bytes(
        bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(width)
        ),
        "little",
    )


def _put(pages, address, value, width=4):
    for i, b in enumerate(value.to_bytes(width, "little")):
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b


def _fixture(vector, *, class_module=spare):
    prototype = class_module._fixture(vector)
    installed = layout.install_layout(prototype, layout.make_layout())
    pages = {p: bytearray(v) for p, v in installed["pages"].items()}
    if "old_begin" in prototype:
        # HeapFree shares the heap dispatch; its native return site distinguishes
        # the exact stdcall request from HeapAlloc without a Lua target collision.
        _put(pages, class_module.growth.FREE_IAT, layout.HEAP_TARGET)
    entry = prototype["stack"] + 48
    _require(
        entry - 20 > prototype["vector_capacity"],
        "callback local record must be above finite vector storage",
    )
    registers = dict(prototype["registers"], esp=entry)
    state = 0x12001000 + 32 * vector["node_alignment"]
    _put(pages, entry, RETURN)
    _put(pages, entry + 4, state)
    for object_address, word, refs in (
        (RECEIVER, vector["destination_word"], vector["destination_refs"]),
        (SOURCE_OBJECT, vector["source_word"], vector["source_refs"]),
    ):
        _put(pages, object_address, word)
        for offset, reference in zip((32, 40), refs):
            _put(pages, object_address + offset, reference)
    frozen = {p: bytes(v) for p, v in pages.items()}
    begin, end, capacity = (_raw(frozen, RECEIVER + offset) for offset in (4, 8, 12))
    live = (end - begin) // 8 if begin else 0
    capacity_count = (capacity - begin) // 8 if begin else 0
    records = [
        [_raw(frozen, begin + 8 * i + 4 * j) for j in range(2)] for i in range(live)
    ]
    logical = model.apply(
        prototype["source_state"],
        prototype["destination_state"],
        dict(records=records, capacity=capacity_count),
        source_pointer=SOURCE_OBJECT,
        source_word=vector["source_word"],
        destination_word=vector["destination_word"],
        destination_refs=vector["destination_refs"],
        source_refs=vector["source_refs"],
        transfers=vector["transfers"],
        allow_growth=class_module is not spare,
    )
    return dict(
        entry=entry,
        registers=registers,
        pages=frozen,
        state=state,
        prototype=prototype,
        logical=logical,
        endpoint=RETURN,
    )


def _direct_response(index, eax):
    return dict(
        eax=eax,
        ecx=0xA1000000 + index,
        edx=0xB1000000 + index,
        eflags=0x202 | ((index * 0x95) & 0x8D5),
    )


def _simd_state(fixture, class_module):
    mode = getattr(class_module, "SIMD_FACTORY", False) is True
    _require(("simd_state" in fixture) == mode, "callback SIMD mode differs")
    if not mode:
        return None
    state = fixture["simd_state"]
    _require(
        type(state) is dict
        and set(state) == {"xmm", "df"}
        and type(state["df"]) is int
        and state["df"] == 0
        and type(state["xmm"]) is dict
        and set(state["xmm"]) == set(XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in state["xmm"].values()),
        "invalid callback SIMD state",
    )
    prototype = fixture["prototype"]
    _require(
        all(
            type(prototype.get(k)) is int
            for k in (
                "old_begin",
                "old_size",
                "vector_begin",
                "vector_end",
                "vector_capacity",
                "old_base",
                "new_base",
                "new_page_count",
            )
        )
        and type(prototype.get("xmm")) is dict
        and set(prototype["xmm"]) == set(XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in prototype["xmm"].values()),
        "callback SIMD geometry differs",
    )
    a = prototype.get("old_begin", 0) - 0x06003800
    _require(
        type(prototype.get("old_size")) is int
        and prototype["old_size"] == 4
        and a in (0, 7, 31)
        and prototype.get("vector_begin") == 0x06002800 + a
        and prototype.get("vector_end") == 0x06002820 + a
        and prototype.get("vector_capacity") == 0x06002830 + a
        and prototype.get("old_base") == 0x06003000
        and prototype.get("new_base") == 0x06002000
        and prototype.get("new_page_count") == 1
        and prototype.get("xmm") == state["xmm"],
        "callback SIMD geometry differs",
    )
    return copy.deepcopy(state)


def _expected(vector, fixture, *, class_module=spare, class_entry_only=False):
    """Closed-form parent frame plus existing independently checked child oracles."""
    regs = dict(fixture["registers"])
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events, calls, children = [], [], []
    direct_count = 0
    simd_state = _simd_state(fixture, class_module)
    frame = fixture["entry"] - 4

    def frozen():
        return {p: bytes(v) for p, v in pages.items()}

    def read(address):
        value = _raw(pages, address)
        events.append(dict(access="read", address=address, width=4, value=value))
        return value

    def write(address, value):
        value &= 0xFFFFFFFF
        events.append(dict(access="write", address=address, width=4, value=value))
        _put(pages, address, value)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def pop(register):
        regs[register] = read(regs["esp"])
        regs["esp"] += 4

    def direct(site, continuation, api, arguments, result, staged):
        nonlocal direct_count
        target = layout.TARGETS[api]
        if staged:
            _require(regs[staged] == target, "callback staged API target differs")
        else:
            _require(read(BASE + layout.SLOTS[api]) == target, "callback IAT differs")
        push(BASE + continuation)
        direct_count += 1
        response = _direct_response(direct_count, result)
        calls.append(
            dict(
                site_rva=f"0x{site:08x}",
                api=api,
                target=target,
                entry_esp=regs["esp"],
                arguments=arguments,
                continuation=BASE + continuation,
                entry_registers=dict(regs),
                response=response,
                group="direct",
            )
        )
        regs.update({k: response[k] for k in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    def child(kind, index, continuation):
        nonlocal regs, pages, simd_state
        push(BASE + continuation)
        if kind == "class":
            child_fixture = dict(
                fixture["prototype"],
                pages=frozen(),
                registers=dict(regs),
                return_address=BASE + continuation,
            )
            result = class_module._expected(vector, child_fixture)
            if simd_state is not None:
                old_begin = child_fixture["old_begin"]
                snapshot = bytes(
                    child_fixture["pages"][(old_begin + i) & ~4095][
                        (old_begin + i) & 4095
                    ]
                    for i in range(32)
                )
                _require(
                    type(result.get("xmm")) is dict
                    and set(result["xmm"]) == set(XMM)
                    and all(
                        type(v) is int and 0 <= v < 2**128
                        for v in result["xmm"].values()
                    )
                    and type(result.get("df")) is int
                    and result["df"] == 0,
                    "callback SIMD child state differs",
                )
                _require(
                    result["xmm"]
                    == dict(
                        simd_state["xmm"],
                        xmm0=int.from_bytes(snapshot[:16], "little"),
                        xmm1=int.from_bytes(snapshot[16:], "little"),
                    ),
                    "callback SIMD child state differs",
                )
                simd_state = dict(xmm=dict(result["xmm"]), df=0)
        else:
            child_vector = (
                dict(
                    alignment=vector["frame_alignment"],
                    prefix_length=1,
                    has_metatable=True,
                    value_kind=("zero", "table")[index],
                    final_void_eax=vector["marker_words"][index],
                )
                if kind == "marker"
                else dict(
                    alignment=vector["frame_alignment"],
                    prefix_length=1 + 2 * index,
                    kinds=vector["transfers"][index],
                )
            )
            module = marker if kind == "marker" else table
            child_fixture = module._fixture(
                child_vector,
                api_layout=layout.make_layout(),
                caller=dict(
                    entry=regs["esp"],
                    return_address=BASE + continuation,
                    registers=dict(regs),
                    stack_pages={p: bytes(pages[p]) for p in (STACK, STACK + 0x1000)},
                ),
            )
            # Generated helper fixture bytes never replace the running parent state.
            child_fixture["pages"] = frozen()
            result = module._expected(child_vector, child_fixture)
            calls.extend(dict(c, group=f"{kind}{index}") for c in result["calls"])
        children.append(
            dict(kind=kind, index=index, fixture=child_fixture, result=result)
        )
        events.extend(result["events"])
        pages = {p: bytearray(v) for p, v in result["pages"].items()}
        regs = dict(result["registers"])

    push(regs["ebp"])
    regs["ebp"] = regs["esp"]
    regs["esp"] -= 24
    regs["eax"] = read(spare.returned.COOKIE) ^ frame
    write(frame - 8, regs["eax"])
    push(regs["ebx"])
    regs["ebx"] = read(frame + 8)
    push(regs["esi"])
    push(regs["edi"])
    regs["edi"] = read(BASE + layout.SLOTS["lua_touserdata"])
    push(0xFFFFD8ED)
    push(regs["ebx"])
    direct(
        0x2EC132,
        0x2EC134,
        "lua_touserdata",
        [fixture["state"], 0xFFFFD8ED],
        fixture.get("receiver", RECEIVER),
        "edi",
    )
    regs["esi"] = regs["eax"]
    regs["esp"] += 8
    write(frame - 20, regs["esi"])
    regs.update(edx=0xFFFFD8ED, ecx=regs["ebx"])
    child("marker", 0, 0x2EC160)
    _require(regs["eax"] & 255 == 1, "callback upvalue marker false")
    regs.update(edx=1, ecx=regs["ebx"])
    child("marker", 1, 0x2EC184)
    _require(regs["eax"] & 255 == 1, "callback argument marker false")
    push(1)
    push(regs["ebx"])
    direct(
        0x2EC1A1,
        0x2EC1A3,
        "lua_touserdata",
        [fixture["state"], 1],
        fixture.get("source_pointer", SOURCE_OBJECT),
        "edi",
    )
    regs["esp"] += 8
    write(frame - 16, 0)
    regs.update(edi=regs["eax"], ecx=regs["esi"], eax=frame - 16)
    write(frame - 12, regs["edi"])
    push(regs["eax"])
    if class_entry_only:
        push(BASE + 0x2EC1BD)
        from src.observatory.native_lua_class_factory_conformance import _add_flags

        result = dict(
            pages=frozen(),
            registers=dict(regs),
            events=events,
            calls=calls,
            children=children,
            flags=_add_flags(frame - 44, 8),
            endpoint=BASE + 0x2EB140,
        )
        if simd_state is not None:
            result.update(xmm=dict(simd_state["xmm"]), df=0)
        return result
    child("class", 0, 0x2EC1BD)
    push(read(regs["esi"] + 32))
    regs["esi"] = read(BASE + layout.SLOTS["lua_rawgeti"])
    push(0xFFFFD8F0)
    push(regs["ebx"])
    direct(
        0x2EC1CC,
        0x2EC1CE,
        "lua_rawgeti",
        [fixture["state"], 0xFFFFD8F0, vector["destination_refs"][0]],
        0x91A2B333,
        "esi",
    )
    push(read(regs["edi"] + 32))
    push(0xFFFFD8F0)
    push(regs["ebx"])
    direct(
        0x2EC1D7,
        0x2EC1D9,
        "lua_rawgeti",
        [fixture["state"], 0xFFFFD8F0, vector["source_refs"][0]],
        0x91A2B344,
        "esi",
    )
    regs["ecx"] = regs["ebx"]
    child("table", 0, 0x2EC1E0)
    regs["eax"] = read(frame - 20)
    push(read(regs["eax"] + 40))
    push(0xFFFFD8F0)
    push(regs["ebx"])
    direct(
        0x2EC1EC,
        0x2EC1EE,
        "lua_rawgeti",
        [fixture["state"], 0xFFFFD8F0, vector["destination_refs"][1]],
        0x91A2B355,
        "esi",
    )
    push(read(regs["edi"] + 40))
    push(0xFFFFD8F0)
    push(regs["ebx"])
    direct(
        0x2EC1F7,
        0x2EC1F9,
        "lua_rawgeti",
        [fixture["state"], 0xFFFFD8F0, vector["source_refs"][1]],
        0x91A2B366,
        "esi",
    )
    regs["esp"] += 48
    regs["ecx"] = regs["ebx"]
    child("table", 1, 0x2EC203)
    regs["ecx"] = read(frame - 20)
    regs["eax"] = read(regs["edi"])
    pop("edi")
    pop("esi")
    write(regs["ecx"], regs["eax"])
    regs["eax"] = 0
    regs["ecx"] = read(frame - 8) ^ regs["ebp"]
    pop("ebx")
    push(BASE + 0x2EC219)
    _require(read(spare.returned.COOKIE) == regs["ecx"], "callback cookie differs")
    _require(
        read(regs["esp"]) == BASE + 0x2EC219, "callback checker continuation differs"
    )
    regs["esp"] += 4
    regs["esp"] = regs["ebp"]
    pop("ebp")
    _require(read(regs["esp"]) == fixture["endpoint"], "callback return word differs")
    regs["esp"] += 4
    result = dict(
        registers=regs,
        pages=frozen(),
        events=events,
        calls=calls,
        children=children,
        flags=0x44,
        endpoint=fixture["endpoint"],
    )
    if simd_state is not None:
        result.update(xmm=dict(simd_state["xmm"]), df=0)
    _require(
        result["pages"]
        == _model_pages(vector, fixture, result, class_module=class_module),
        "independent callback memory differs",
    )
    return result


def _model_pages(vector, fixture, expected, *, class_module=spare):
    child = next(c for c in expected["children"] if c["kind"] == "class")
    logical = fixture["logical"]["class_operation"]
    _require(
        all(
            child["fixture"]["transfer"][k] == logical[k]
            for k in ("destination", "copies")
        ),
        "independent callback class transfer differs",
    )
    pages = {
        p: bytearray(v)
        for p, v in class_module._model_pages(child["fixture"], child["result"]).items()
    }
    # Scratch below the parent's save area is established by the joined child
    # event laws. Independently restore original ancestors and parent-owned cells.
    start = fixture["prototype"]["stack"] + 8
    for p in (STACK, STACK + 0x1000):
        pages[p] = bytearray(expected["pages"][p])
        offset = max(0, min(4096, start - p))
        pages[p][offset:] = fixture["pages"][p][offset:]
    s = fixture["prototype"]["stack"]
    for offset, value in {
        8: fixture["registers"]["edi"],
        12: fixture["registers"]["esi"],
        16: BASE + 0x2EC219,
        24: RECEIVER,
        28: 0,
        32: SOURCE_OBJECT,
        36: vector["cookie"] ^ (fixture["entry"] - 4),
        44: fixture["registers"]["ebp"],
    }.items():
        _put(pages, s + offset, value)
    logical_vector = fixture["logical"]["class_operation"]["vector"]
    begin = fixture["prototype"]["vector_begin"]
    for i, record in enumerate(logical_vector["records"]):
        for j, value in enumerate(record):
            _put(pages, begin + 8 * i + 4 * j, value)
    for offset, value in (
        (4, begin),
        (8, begin + 8 * len(logical_vector["records"])),
        (12, begin + 8 * logical_vector["capacity"]),
    ):
        _put(pages, RECEIVER + offset, value)
    _put(pages, RECEIVER, fixture["logical"]["destination_word"])
    return {p: bytes(v) for p, v in pages.items()}


class _Lua:
    """Supplied API stack contract, replayed independently of the event oracle."""

    def __init__(self, vector):
        self.vector = vector
        self.stack = [("argument", 0)]
        self.trace = []
        self.cursors = [0, 0]
        self.assignments = [[], []]

    def apply(self, call):
        name, group = call["api"], call["group"]
        args = call["arguments"][1:]
        signed = lambda v: v - 2**32 if v >= 2**31 else v
        before = list(self.stack)
        truth = None
        if name == "lua_touserdata":
            return
        if group.startswith("marker"):
            index = int(group[-1])
            if name == "lua_getmetatable":
                self.stack.append(("metatable", index))
            elif name == "lua_pushstring":
                _require(args == [marker.LITERAL], "callback marker literal differs")
                self.stack.append(("marker_key", index))
            elif name == "lua_gettable":
                _require(
                    self.stack[-2:] == [("metatable", index), ("marker_key", index)],
                    "callback marker lookup stack differs",
                )
                self.stack[-1] = ("marker_value", index)
            elif name == "lua_toboolean":
                _require(
                    self.stack[-1] == ("marker_value", index),
                    "callback marker truth stack differs",
                )
            elif name == "lua_settop":
                _require(
                    self.stack[-2:] == [("metatable", index), ("marker_value", index)],
                    "callback marker cleanup stack differs",
                )
                del self.stack[-2:]
            else:
                raise ConformanceError("unknown callback marker API")
            _require(
                len(before) == call["lua_top_before"]
                and len(self.stack) == call["lua_top_after"],
                "callback marker stack depth differs",
            )
            return
        if name == "lua_rawgeti":
            _require(signed(args[0]) == -10000, "callback registry index differs")
            logical_args = [-10000, args[1]]
            self.stack.append(("registry", args[1]))
        else:
            pair = int(group[-1])
            kinds = self.vector["transfers"][pair]
            logical_args = [signed(v) for v in args]
            if name == "lua_pushnil":
                self.stack.append(("nil",))
            elif name == "lua_next":
                _require(
                    self.stack[-2] == ("registry", self.vector["source_refs"][pair]),
                    "callback iterator table differs",
                )
                cursor = self.cursors[pair]
                previous = self.stack.pop()
                _require(
                    previous
                    == (
                        ("nil",)
                        if cursor == 0
                        else ("key", cursor - 1, kinds[cursor - 1])
                    ),
                    "callback iterator key differs",
                )
                truth = int(cursor < len(kinds))
                if truth:
                    self.stack.extend(
                        [("key", cursor, kinds[cursor]), ("value", cursor)]
                    )
                    self.cursors[pair] += 1
            elif name == "lua_pushstring":
                literal = layout.LITERALS[args[0]][:-1].decode()
                logical_args = [literal]
                self.stack.append(("literal", literal))
            elif name == "lua_equal":
                literal, key = self.stack[-1], self.stack[-3]
                _require(
                    literal[0] == "literal" and key[0] == "key",
                    "callback comparison stack differs",
                )
                truth = int(
                    key[2] == {"__init": "init", "__finalize": "finalize"}[literal[1]]
                )
            elif name == "lua_settop":
                del self.stack[len(self.stack) + logical_args[0] + 1 :]
            elif name == "lua_pushvalue":
                self.stack.append(self.stack[logical_args[0]])
            elif name == "lua_insert":
                at = len(self.stack) + logical_args[0]
                self.stack.insert(at, self.stack.pop())
            elif name == "lua_settable":
                _require(
                    self.stack[-5]
                    == ("registry", self.vector["destination_refs"][pair]),
                    "callback assignment table differs",
                )
                key, value = self.stack[-2:]
                _require(
                    key[0] == "key" and value == ("value", key[1]),
                    "callback assignment pair differs",
                )
                self.assignments[pair].append(key[1])
                del self.stack[-2:]
            else:
                raise ConformanceError("unknown callback transfer API")
            _require(
                len(before) == call["lua_top_before"]
                and len(self.stack) == call["lua_top_after"],
                "callback table stack depth differs",
            )
            if truth is not None:
                _require(
                    call["response"]["eax"] == truth,
                    "callback supplied Lua truth differs",
                )
        self.trace.append(
            dict(
                api=name,
                arguments=logical_args,
                before=before,
                after=list(self.stack),
                truth=truth,
            )
        )


def _run_case(
    codes,
    points,
    vector,
    negative=None,
    *,
    class_module=spare,
    fixture=None,
    continuation=None,
):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = (
        _fixture(vector, class_module=class_module) if fixture is None else fixture
    )
    extension = continuation or {}
    expected = _expected(vector, fixture, class_module=class_module)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, payload)
    code_pages = {
        (BASE + a + i) & ~0xFFF for a, b in codes.items() for i in range(len(b))
    }
    for page in code_pages:
        _require(page not in fixture["pages"], "callback code overlaps data")
        machine.mem_map(page, 4096)
        machine.mem_write(page, b"\xcc" * 4096)
    for address, payload in codes.items():
        machine.mem_write(BASE + address, payload)
    for page in (RETURN & ~0xFFF, layout.IMPORT):
        _require(
            page not in code_pages and page not in fixture["pages"],
            "callback endpoint overlaps mapping",
        )
        machine.mem_map(page, 4096)
        machine.mem_write(page, b"\xcc" * 4096)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in REGISTERS}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    simd_state = _simd_state(fixture, class_module)
    xmm_ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in XMM}
    if simd_state is not None:
        for r, value in simd_state["xmm"].items():
            machine.reg_write(xmm_ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, allocations, actual_calls = [], [], [], []
    lua = _Lua(vector)
    class_child = next(c for c in expected["children"] if c["kind"] == "class")
    heap_nodes = class_child["result"]["heap_nodes"]
    tree_heap_count = class_child["result"].get("tree_heap_count", len(heap_nodes))
    frees = []
    resume = None
    simd_copy_done = False

    def xmm_values():
        return {r: machine.reg_read(i) for r, i in xmm_ids.items()}

    def check_simd(expected_xmm):
        _require(xmm_values() == expected_xmm, "callback SIMD XMM differs")
        _require(
            not machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
            "callback SIMD DF differs",
        )

    def registers():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def words(address, count):
        return [
            int.from_bytes(machine.mem_read(address + 4 * i, 4), "little")
            for i in range(count)
        ]

    def on_code(m, address, size, user):
        nonlocal resume, simd_copy_done
        if "before_instruction" in extension:
            extension["before_instruction"](m, address, ids, expected, negative)
        if simd_state is not None:
            pc = address - BASE
            if address == BASE + START or pc == 0x2EB140:
                check_simd(simd_state["xmm"])
            for site, key, control in (
                (0x2EB620, "growth_entry", "simd_growth_entry"),
                (0x2EB680, "resize_entry", "simd_resize_entry"),
                (0x36E580, "copy_entry", "simd_copy_entry"),
            ):
                if pc == site:
                    if negative == control:
                        m.reg_write(ids["edx"], m.reg_read(ids["edx"]) ^ 1)
                    _require(
                        registers() == class_child["result"][key],
                        "callback SIMD boundary differs",
                    )
                    check_simd(simd_state["xmm"])
            if pc == 0x2EB6A6:
                copy_entry = class_child["result"]["copy_entry"]
                if negative == "simd_copy_return":
                    m.reg_write(ids["ecx"], m.reg_read(ids["ecx"]) ^ 1)
                if negative == "simd_copy_flags":
                    m.reg_write(
                        x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1
                    )
                _require(
                    registers()
                    == dict(copy_entry, ecx=0, edx=0, esp=copy_entry["esp"] + 4)
                    and m.reg_read(x.UC_X86_REG_EFLAGS) & 0x8C5 == 0x44,
                    "callback SIMD copy return differs",
                )
                if negative == "simd_copy_xmm":
                    m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
                check_simd(class_child["result"]["xmm"])
                simd_copy_done = True
            if pc == 0x2EC1BD or (negative == "cookie" and pc == 0x3574D5):
                check_simd(class_child["result"]["xmm"])
        if negative == "cookie" and address == BASE + 0x3574D5:
            m.emu_stop()
            return
        if address == layout.HEAP_TARGET:
            if simd_state is not None:
                check_simd(
                    class_child["result"]["xmm"]
                    if simd_copy_done
                    else simd_state["xmm"]
                )
            sp = m.reg_read(ids["esp"])
            actual = words(sp, 4)
            if actual[0] == BASE + 0x389172:
                if negative == "free_request":
                    m.mem_write(
                        sp + 12,
                        (fixture["prototype"]["old_begin"] ^ 1).to_bytes(4, "little"),
                    )
                    actual = words(sp, 4)
                _require(
                    "old_begin" in fixture["prototype"]
                    and not frees
                    and len(allocations) == len(heap_nodes)
                    and sp == fixture["prototype"]["stack"] - 132
                    and actual
                    == [
                        BASE + 0x389172,
                        spare.construction.HEAP,
                        0,
                        fixture["prototype"]["old_begin"],
                    ],
                    "callback free handoff differs",
                )
                for r, v in dict(
                    eax=1, ecx=0xA0000001, edx=0xB0000001, esp=sp + 16
                ).items():
                    m.reg_write(ids[r], v)
                m.reg_write(x.UC_X86_REG_EFLAGS, 0x2D7)
                frees.append(
                    dict(
                        pointer=actual[3],
                        entry_esp=sp,
                        result=1,
                        continuation=actual[0],
                    )
                )
                resume = actual[0]
                m.emu_stop()
                return
            tree_allocation = len(allocations) < tree_heap_count
            request = (
                24
                if tree_allocation
                else 8 * fixture["logical"]["class_operation"]["vector"]["capacity"]
            )
            if negative == "heap_request" and not tree_allocation:
                m.mem_write(sp + 12, (request ^ 1).to_bytes(4, "little"))
                actual = words(sp, 4)
            _require(
                len(allocations) < len(heap_nodes)
                and sp
                == fixture["prototype"]["stack"] - (144 if tree_allocation else 140)
                and actual == [BASE + 0x389463, spare.construction.HEAP, 0, request],
                "callback heap handoff differs",
            )
            node = heap_nodes[len(allocations)]
            for r, v in dict(
                eax=node, ecx=0xA0000001, edx=0xB0000001, esp=sp + 16
            ).items():
                m.reg_write(ids[r], v)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            allocations.append(
                dict(node=node, entry_esp=sp, request=request, continuation=actual[0])
            )
            resume = actual[0]
            m.emu_stop()
            return
        if address in layout.TARGETS.values():
            if simd_state is not None:
                check_simd(
                    class_child["result"]["xmm"]
                    if simd_copy_done
                    else simd_state["xmm"]
                )
            _require(
                len(actual_calls) < len(expected["calls"]), "extra callback API call"
            )
            call = expected["calls"][len(actual_calls)]
            sp = m.reg_read(ids["esp"])
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and words(sp, 1 + len(call["arguments"]))
                == [call["continuation"], *call["arguments"]]
                and registers() == call["entry_registers"],
                "callback API request or ABI differs",
            )
            if (
                negative == "lua_prefix"
                and call["group"] == "table1"
                and call["api"] == "lua_pushnil"
            ):
                lua.stack[1] = ("registry", vector["destination_refs"][0] ^ 1)
            lua.apply(call)
            for r in ("eax", "ecx", "edx"):
                m.reg_write(ids[r], call["response"][r])
            m.reg_write(ids["esp"], sp + 4)
            m.reg_write(x.UC_X86_REG_EFLAGS, call["response"]["eflags"])
            actual_calls.append(call)
            resume = call["continuation"]
            m.emu_stop()
            return
        if address == fixture["endpoint"]:
            if simd_state is not None:
                if negative == "simd_xmm":
                    m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
                if negative == "simd_df":
                    m.reg_write(
                        x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) | 0x400
                    )
                if negative == "simd_spare":
                    at = fixture["prototype"]["vector_begin"] + 40
                    m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
                check_simd(expected["xmm"])
            corrupt = {
                "ancestor": fixture["entry"] + 8,
                "record": fixture["prototype"]["stack"] + 28,
                "word": RECEIVER,
                "reference": SOURCE_OBJECT + 40,
                "literal": marker.LITERAL + len(marker.LITERAL_BYTES) + 3,
                "iat": layout.IAT_PAGE + 0x20,
                "vector": fixture["prototype"]["vector_end"],
                "capacity": RECEIVER + 12,
            }
            if "old_begin" in fixture["prototype"]:
                corrupt["old"] = fixture["prototype"]["old_begin"]
            if negative in corrupt:
                at = corrupt[negative]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "result":
                m.reg_write(ids["eax"], 1)
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "callback escaped selected bodies")
        visited.append(f"0x{pc:08x}")
        if negative == "cookie" and pc == 0x2EC214:
            m.mem_write(
                spare.returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little")
            )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        if width == 8 and simd_state is not None:
            pc = m.reg_read(x.UC_X86_REG_EIP) - BASE
            old_begin, fresh = (
                fixture["prototype"]["old_begin"],
                fixture["prototype"]["vector_begin"],
            )
            allowed_wide = {
                0x36EA60: (False, (old_begin, old_begin + 8)),
                0x36EA64: (False, (old_begin + 16, old_begin + 24)),
                0x36EA69: (True, (fresh, fresh + 8)),
                0x36EA6D: (True, (fresh + 16, fresh + 24)),
            }
            _require(
                pc in allowed_wide
                and writing == allowed_wide[pc][0]
                and address in allowed_wide[pc][1],
                "callback SIMD wide access differs",
            )
        else:
            _require(width in (1, 2, 4), "unexpected callback memory width")
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    (
                        value & ((1 << (8 * width)) - 1)
                        if simd_state is not None
                        else value
                    )
                    if writing
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + START
    expected_frees = int("old_begin" in fixture["prototype"])
    for _ in range(len(expected["calls"]) + len(heap_nodes) + expected_frees + 1):
        resume = None
        machine.emu_start(next_pc, 0, count=100000)
        if resume is None:
            break
        next_pc = resume
    if negative == "cookie":
        frame = fixture["entry"] - 4
        failure_regs = dict(expected["registers"], ebp=frame, esp=frame - 28)
        failure_flags = spare.returned.return_spec(
            frame, vector["cookie"], vector["cookie"] ^ 1
        )["flags"]
        flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
        _require(
            machine.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5
            and registers() == failure_regs
            and flags & 0x8D5 == failure_flags
            and not flags & 0x400,
            "callback cookie failure ABI differs",
        )
        _require(
            events
            == expected["events"][:-4]
            + [
                dict(
                    access="read",
                    address=spare.returned.COOKIE,
                    width=4,
                    value=vector["cookie"] ^ 1,
                )
            ],
            "callback cookie failure prefix differs",
        )
        failure_pages = {p: bytearray(v) for p, v in expected["pages"].items()}
        _put(failure_pages, spare.returned.COOKIE, vector["cookie"] ^ 1)
        _require(
            all(
                bytes(machine.mem_read(p, 4096)) == bytes(v)
                for p, v in failure_pages.items()
            ),
            "callback cookie failure memory differs",
        )
        _require(
            actual_calls == expected["calls"]
            and len(allocations) == len(heap_nodes)
            and len(frees) == expected_frees
            and lua.trace == fixture["logical"]["calls"]
            and lua.stack == fixture["logical"]["final_lua_stack"],
            "callback cookie failure calls differ",
        )
        return dict(kind="cookie", rejected=True, endpoint="0x003574d5")
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "callback endpoint differs",
    )
    _require(
        len(allocations) == len(heap_nodes)
        and actual_calls == expected["calls"]
        and len(frees) == expected_frees,
        "callback call count differs",
    )
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        registers() == expected["registers"]
        and flags & 0x8D5 == expected["flags"]
        and not flags & 0x400,
        "callback registers or flags differ",
    )
    _require(events == expected["events"], "callback ordered events differ")
    _require(
        lua.trace == fixture["logical"]["calls"]
        and lua.stack == fixture["logical"]["final_lua_stack"]
        and lua.assignments == fixture["logical"]["requested_assignments"],
        "callback Lua request trace differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == expected["pages"][p]
            for p in (STACK, STACK + 0x1000)
        ),
        "callback ancestor memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == payload
            for p, payload in expected["pages"].items()
            if p not in (STACK, STACK + 0x1000)
        ),
        "callback protected memory differs",
    )
    if "verify_return" in extension:
        extension["verify_return"](machine, ids, expected, lua)
    observation = json.loads(
        json.dumps(
            dict(
                vector=vector,
                registers=registers(),
                flags=flags & 0x8D5,
                trace_rvas=visited,
                allocations=allocations,
                api_calls=len(actual_calls),
                lua_stack=lua.stack,
                assignments=lua.assignments,
                events_sha256=_canonical_sha256(events),
                lua_trace_sha256=_canonical_sha256(json.loads(json.dumps(lua.trace))),
                memory_sha256=_canonical_sha256(
                    {
                        str(p): hashlib.sha256(v).hexdigest()
                        for p, v in expected["pages"].items()
                    }
                ),
            )
        )
    )
    if class_module is not spare:
        observation["frees"] = frees
    if simd_state is not None:
        observation.update(xmm=xmm_values(), df=0)
    return observation


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "callback source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = _decode_body(data, image, sources["program_facts"], START)
    owner_payload = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(owner_payload) == END - START
        and hashlib.sha256(owner_payload).hexdigest() == BODY_SHA256,
        "callback owner differs",
    )
    codes, witnesses = {START: owner_payload}, {
        _point(r)["rva"]: _point(r) for r in owner
    }
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for key in ("class_spare", "marker", "table"):
        body = sources[key]["body"]
        ranges = body.get(
            "ranges",
            [dict(start_rva=body.get("start_rva"), end_rva=body.get("end_rva"))],
        )
        for point in body["points"]:
            _require(
                point["rva"] not in witnesses or witnesses[point["rva"]] == point,
                "callback witness conflict",
            )
            witnesses[point["rva"]] = point
        for part in ranges:
            a, b = (int(part[k], 16) for k in ("start_rva", "end_rva"))
            offset = image.rva_to_file_offset(a)
            payload = data[offset : offset + b - a]
            decoded = [_point(r) for r in decoder.disasm(payload, BASE + a)]
            _require(
                sum(p["size"] for p in decoded) == b - a
                and all(witnesses.get(p["rva"]) == p for p in decoded),
                "callback selected child code differs",
            )
            codes[a] = payload
    # Overlapping ranges are permitted only when every byte agrees.
    covered = {}
    for a, payload in codes.items():
        for i, byte in enumerate(payload):
            _require(
                a + i not in covered or covered[a + i] == byte,
                "callback code overlap differs",
            )
            covered[a + i] = byte
    return codes, sorted(witnesses.values(), key=lambda p: int(p["rva"], 16))


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact callback executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    excluded = ((0x2EC140, 0x2EC154), (0x2EC164, 0x2EC178), (0x2EC188, 0x2EC19E))
    required = {
        p["rva"]
        for p in points
        if START <= int(p["rva"], 16) < END
        and not any(a <= int(p["rva"], 16) < b for a, b in excluded)
    }
    _require(
        required <= set(union)
        and (
            set(sources["class_spare"]["executed_rvas"])
            - CLASS_ARGUMENT_BELOW_END_SITES
        )
        <= set(union)
        and set(sources["table"]["executed_rvas"]) <= set(union),
        "callback selected normal coverage differs",
    )
    _require(
        not CLASS_ARGUMENT_BELOW_END_SITES.intersection(union),
        "callback local record entered excluded argument range path",
    )
    _require(
        not any(a <= int(pc, 16) < b for pc in union for a, b in excluded),
        "callback excluded error arm executed",
    )
    sample = next(
        v
        for v in vectors()
        if len(v["source_keys"]) == 7
        and v["profile"] == "mixed"
        and len(v["transfers"][0]) == 3
    )
    controls = []
    for kind, message in (
        ("ancestor", "callback ancestor memory differs"),
        ("record", "callback ancestor memory differs"),
        ("word", "callback protected memory differs"),
        ("reference", "callback protected memory differs"),
        ("literal", "callback protected memory differs"),
        ("iat", "callback protected memory differs"),
        ("vector", "callback protected memory differs"),
        ("result", "callback registers or flags differ"),
        ("lua_prefix", "callback Lua request trace differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "callback mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True, reason=message))
        else:
            raise ConformanceError("callback mutation survived")
    controls.append(_run_case(codes, points, sample, "cookie"))
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            start_rva=f"0x{START:08x}",
            end_rva=f"0x{END:08x}",
            sha256=BODY_SHA256,
            cfg_sha256=CFG_SHA256,
            unreachable_class_argument_sites=sorted(CLASS_ARGUMENT_BELOW_END_SITES),
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(b):08x}")
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            callback_bytes=END - START,
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            api_calls=sum(o["api_calls"] for o in observations),
            allocations=sum(len(o["allocations"]) for o in observations),
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in observations
            ),
            retained_lua_values=4,
            result_count=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=list(layout.TARGETS) + ["HeapAlloc"],
            normal_premises=[
                "Non-null valid disjoint source and destination representations",
                "True class markers and valid compatible registry values",
                "Normal cdecl Lua responses preserving mapped pages and nonvolatile registers",
                "Successful bounded stdcall HeapAlloc and nested FS registration contracts",
                "External original two-word local record with spare vector capacity",
                "Stack-local record lies above both finite external vector ranges",
            ],
            checked=[
                "Every callback and selected child instruction executes in one x86 machine",
                "Exact ordered memory events, full mapped pages, registers and defined flags",
                "Actual local record and caller ancestors independently restored",
                "Logical tree transfer, payload overwrite, vector append and source-word copy",
                "One continuous Lua token stack, two filtered assignment request streams",
                "Four retained registry values immediately before returning zero results",
            ],
            excluded=[
                "Assertions, lua_error and false or null marker branches",
                "Real Lua VM, DLL, metamethod or destination-table effects",
                "Heap failure, allocation growth and exception dispatch",
                "Other vector families, arbitrary trees, objects or memory aliases",
                "Host handling of callback results",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "callback executable changed",
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
        "sealed callback conformance differs",
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
        "exact callback conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
