"""Continuous native callback assertion prefix and mode-three getter dispatch."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.observatory import (
    native_lua_class_callback_assertion_prefix_conformance as prefix,
)
from src.observatory import (
    native_assertion_helper_parent_dispatch_conformance as dispatch,
)

common, marker, layout = prefix.common, prefix.marker, prefix.layout
model = dispatch.model
BASE, ConformanceError, _require = prefix.BASE, prefix.ConformanceError, prefix._require
_canonical_sha256, _canonical_bytes = prefix._canonical_sha256, prefix._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_callback_assertion_dispatch_conformance"
SEALED_SHA256 = "f6693e3b32ec3776e6b1193e582af68f4df77d6178a864e5cffb545eeaff11ce"
START, BOUNDARY, GLOBAL_PAGE = prefix.START, prefix.BOUNDARY, dispatch.GLOBAL_PAGE
DISPATCH_PROFILES = ((1, 0xFFFFFFFF), (0, 1), (0, 2), (2, 0xFFFFFFFF))
SOURCE_PINS = dict(prefix.SOURCE_PINS)
for _key, _pin in dispatch.SOURCE_PINS.items():
    _require(
        _key not in SOURCE_PINS or SOURCE_PINS[_key] == _pin,
        "callback assertion dispatch source pin conflict",
    )
    SOURCE_PINS[_key] = _pin
SOURCE_PINS["callback_assertion_prefix"] = (prefix.ANALYSIS_KIND, prefix.SEALED_SHA256)
CONTROLS = {
    **prefix.CONTROLS,
    **{"dispatch_" + key: reason for key, reason in dispatch.CONTROLS.items()},
    "join_register": "callback assertion dispatch join differs",
    "join_page_refresh": "callback assertion dispatch join differs",
    "join_global_refresh": "callback assertion dispatch join differs",
    "prefix_missing_read": "callback assertion prefix memory events differ",
    "prefix_trace_record": "callback assertion prefix native path differs",
}


def vectors():
    return [dict(v, dispatch_profile=p) for v in prefix.vectors() for p in range(4)]


def _prefix_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"alignment", "profile", "family", "dispatch_profile"}
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["family"]) is str
        and type(vector["dispatch_profile"]) is int
        and 0 <= vector["dispatch_profile"] < len(DISPATCH_PROFILES),
        "callback assertion dispatch vector differs",
    )
    previous = {k: vector[k] for k in ("alignment", "profile", "family")}
    _require(previous in prefix.vectors(), "callback assertion dispatch vector differs")
    return previous


def _global_page(vector):
    _prefix_vector(vector)
    first, second = DISPATCH_PROFILES[vector["dispatch_profile"]]
    result = bytearray(((i * 17) ^ (i >> 4) ^ 0xA9) & 255 for i in range(4096))
    for address, value in ((model.FIRST_GLOBAL, first), (model.SECOND_GLOBAL, second)):
        at = address - GLOBAL_PAGE
        result[at : at + 4] = value.to_bytes(4, "little")
    return bytes(result)


def _fixture(vector):
    previous = prefix._fixture(_prefix_vector(vector))
    _require(
        GLOBAL_PAGE not in previous["pages"],
        "callback assertion dispatch global page overlaps",
    )
    return dict(prefix_fixture=previous, global_page=_global_page(vector))


def _expected(vector, fixture):
    previous = _prefix_vector(vector)
    _require(
        type(fixture) is dict
        and set(fixture) == {"prefix_fixture", "global_page"}
        and type(fixture["prefix_fixture"]) is dict
        and type(fixture["global_page"]) is bytes
        and len(fixture["global_page"]) == 4096
        and fixture["global_page"] == _global_page(vector),
        "callback assertion dispatch fixture differs",
    )
    old = fixture["prefix_fixture"]
    _require(
        set(old) == {"entry", "state", "userdata", "registers", "pages"}
        and all(
            type(old[key]) is int and 0 <= old[key] <= 0xFFFFFFFF
            for key in ("entry", "state", "userdata")
        )
        and type(old["registers"]) is dict
        and set(old["registers"]) == set(common.REGISTERS)
        and all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF for v in old["registers"].values()
        )
        and type(old["pages"]) is dict
        and all(
            type(p) is int
            and p % 4096 == 0
            and 0 <= p <= 0xFFFFF000
            and type(data) is bytes
            and len(data) == 4096
            for p, data in old["pages"].items()
        )
        and _same_packet(old, prefix._fixture(previous)),
        "callback assertion dispatch fixture differs",
    )
    pe = prefix._expected(previous, fixture["prefix_fixture"])
    _require(
        GLOBAL_PAGE not in pe["pages"],
        "callback assertion dispatch global page overlaps",
    )
    try:
        predicted = model.apply_to_pages(
            registers=pe["registers"],
            pages=dict(pe["pages"]) | {GLOBAL_PAGE: fixture["global_page"]},
            entry_flags=pe["flags"],
        )
    except model.AssertionParentDispatchError as exc:
        raise ConformanceError(str(exc)) from exc
    return dict(prefix=pe, dispatch=predicted)


def _same_packet(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _same_packet(actual[k], value) for k, value in expected.items()
        )
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same_packet(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


def _page_hashes(pages):
    return {f"0x{p:08x}": hashlib.sha256(data).hexdigest() for p, data in pages.items()}


def _normalize(operation):
    # The prefix's common facade does not expose the fill normalizer. Keep its
    # declared error class while normalizing errors from both source families.
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _prefix_projection(vector, expected):
    return dict(
        vector=_prefix_vector(vector),
        trace_rvas=copy.deepcopy(expected["trace_rvas"]),
        api_calls=[
            dict(
                api=c["api"],
                arguments=copy.deepcopy(c["arguments"]),
                response=copy.deepcopy(c["response"]),
            )
            for c in expected["calls"]
        ],
        boundary_request=copy.deepcopy(expected["boundary_request"]),
        registers=dict(expected["registers"]),
        flags=expected["flags"],
        logical=copy.deepcopy(expected["logical"]),
        lua_calls=copy.deepcopy(expected["logical"]["calls"]),
        memory_events_sha256=_canonical_sha256(expected["events"]),
        pages_sha256=_page_hashes(expected["pages"]),
    )


def _check_join(actual, vector, fixture, expected):
    reason = "callback assertion dispatch join differs"
    pe = expected["prefix"]
    pages = dict(pe["pages"]) | {GLOBAL_PAGE: fixture["global_page"]}
    _require(
        type(actual) is dict
        and set(actual)
        == {
            "registers",
            "flags",
            "endpoint",
            "pages",
            "pages_sha256",
            "prefix_observation",
        }
        and type(actual["registers"]) is dict
        and set(actual["registers"]) == set(common.REGISTERS)
        and all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in actual["registers"].values()
        )
        and _same_packet(actual["registers"], pe["registers"])
        and type(actual["flags"]) is int
        and 0 <= actual["flags"] <= 0xFFFFFFFF
        and actual["flags"] & 0xCC5 == pe["flags"]
        and type(actual["endpoint"]) is int
        and actual["endpoint"] == BOUNDARY
        and type(actual["pages"]) is dict
        and set(actual["pages"]) == set(pages)
        and all(
            type(p) is int and type(data) is bytes and len(data) == 4096
            for p, data in actual["pages"].items()
        )
        and actual["pages"] == pages
        and _same_packet(actual["pages_sha256"], _page_hashes(actual["pages"]))
        and _same_packet(actual["prefix_observation"], _prefix_projection(vector, pe)),
        reason,
    )
    return copy.deepcopy(actual)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict
            and set(sources) == set(SOURCE_PINS)
            and all(type(value) is dict for value in sources.values()),
            "callback assertion dispatch source partition differs",
        )
        prefix._preflight({key: sources[key] for key in prefix.SOURCE_PINS})
        dispatch._preflight({key: sources[key] for key in dispatch.SOURCE_PINS})
        result = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            sources["callback_assertion_prefix"]["build_identity"] == identity,
            "callback assertion dispatch prefix build differs",
        )
        return result

    return _normalize(run)


def _load_code_impl(data, image, sources):
    _preflight(sources)
    pc, pp = prefix._load_code(
        data, image, {key: sources[key] for key in prefix.SOURCE_PINS}
    )
    dc, dp = dispatch._load_code(
        data, image, {key: sources[key] for key in dispatch.SOURCE_PINS}
    )
    byte_map, point_map = {}, {}
    for codes in (pc, dc):
        for start, body in codes.items():
            for index, byte in enumerate(body):
                address = start + index
                _require(
                    address not in byte_map or byte_map[address] == byte,
                    "callback assertion dispatch code conflict",
                )
                byte_map[address] = byte
    for point in pp + dp:
        _require(
            point["rva"] not in point_map
            or _same_packet(point_map[point["rva"]], point),
            "callback assertion dispatch point conflict",
        )
        point_map[point["rva"]] = point
    merged = {}
    start = None
    for address in sorted(byte_map):
        if start is None or start + len(merged[start]) != address:
            start = address
            merged[start] = bytearray()
        merged[start].append(byte_map[address])
    return {p: bytes(data) for p, data in merged.items()}, [
        point_map[key] for key in sorted(point_map)
    ]


def _load_code(data, image, sources):
    return _normalize(lambda: _load_code_impl(data, image, sources))


def _run_case(codes, points, vector, negative=None, *, capture=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "callback assertion dispatch control differs",
    )
    fixture = _fixture(vector)
    previous = _prefix_vector(vector)
    old_fixture = fixture["prefix_fixture"]
    oracle = _expected(vector, fixture)
    pe, expected = oracle["prefix"], oracle["dispatch"]
    lua = prefix._Lua(previous, old_fixture)
    initial_pages = dict(old_fixture["pages"]) | {GLOBAL_PAGE: fixture["global_page"]}
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, data in initial_pages.items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    code_pages = {
        (address + i) & ~4095
        for address, data in codes.items()
        for i in range(len(data))
    }
    code_pages |= {layout.IMPORT, BOUNDARY & ~4095, expected["endpoint"] & ~4095}
    _require(
        not code_pages & set(initial_pages),
        "callback assertion dispatch mapping overlaps",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for address, data in codes.items():
        machine.mem_write(address, data)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in common.REGISTERS}
    for name, value in old_fixture["registers"].items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    visited, events, calls = [], [], []
    dispatch_visited, dispatch_events = [], []
    counts = dict(first_entry=0, first_return=0, second_entry=0, second_return=0)
    resume, finished, actual_join, prefix_observation = None, False, None, None
    phase, entry = "prefix", None
    allowed = {point["rva"] for point in points}
    dispatch_allowed = {int(point["rva"], 16) for point in points}
    dispatch_negative = (
        negative[len("dispatch_") :]
        if type(negative) is str and negative.startswith("dispatch_")
        else None
    )

    def regs():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def word(address):
        return int.from_bytes(machine.mem_read(address, 4), "little")

    def words(address, count):
        return [word(address + 4 * i) for i in range(count)]

    def flip_register(name):
        machine.reg_write(ids[name], machine.reg_read(ids[name]) ^ 1)

    def flip_word(address):
        machine.mem_write(address, (word(address) ^ 1).to_bytes(4, "little"))

    def verify_prefix():
        _require(
            len(calls) == len(pe["calls"]),
            "callback assertion prefix boundary absent",
        )
        _require(
            regs() == pe["registers"]
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xCC5 == pe["flags"],
            "callback assertion prefix registers or flags differ",
        )
        _require(
            all(
                bytes(machine.mem_read(p, 4096)) == data
                for p, data in pe["pages"].items()
            ),
            "callback assertion prefix protected memory differs",
        )
        _require(
            events == pe["events"], "callback assertion prefix memory events differ"
        )
        _require(
            visited == pe["trace_rvas"], "callback assertion prefix native path differs"
        )
        _require(
            json.loads(json.dumps(lua.calls)) == pe["logical"]["calls"],
            "callback assertion prefix Lua trace differs",
        )
        _require(
            json.loads(json.dumps(lua.stack)) == pe["logical"]["final_lua_stack"],
            "callback assertion prefix Lua identity differs",
        )
        result = dict(
            vector=previous,
            trace_rvas=copy.deepcopy(visited),
            api_calls=copy.deepcopy(calls),
            boundary_request=copy.deepcopy(pe["boundary_request"]),
            registers=regs(),
            flags=pe["flags"],
            logical=copy.deepcopy(pe["logical"]),
            lua_calls=json.loads(json.dumps(lua.calls)),
            memory_events_sha256=_canonical_sha256(events),
            pages_sha256=_page_hashes(
                {p: bytes(machine.mem_read(p, 4096)) for p in pe["pages"]}
            ),
        )
        _require(
            _same_packet(result, _prefix_projection(vector, pe)),
            "callback assertion dispatch prefix projection differs",
        )
        return result

    def dispatch_code(m, address, size, user):
        nonlocal finished
        pc = address - BASE
        if pc == model.PARENT:
            if dispatch_negative == "df":
                m.reg_write(
                    x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) | 0x400
                )
            _require(
                not m.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
                "assertion dispatch initial DF differs",
            )
        if pc == model.FIRST:
            counts["first_entry"] += 1
            if dispatch_negative == "mode":
                flip_word(entry - 12)
            if dispatch_negative == "first_register":
                flip_register("edx")
            _require(
                regs() == expected["first_getter"]["entry_registers"]
                and words(entry - 16, 2) == [BASE + 0x379CD2, 3],
                "assertion dispatch first handoff differs",
            )
        if pc == 0x379CD2:
            counts["first_return"] += 1
            if dispatch_negative == "first_return":
                flip_register("eax")
            packet = expected["first_getter"]
            _require(
                regs() == packet["return_registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & packet["flag_mask"]
                == packet["flags"],
                "assertion dispatch first return differs",
            )
        if pc == model.SECOND:
            counts["second_entry"] += 1
            if dispatch_negative == "second_register":
                flip_register("edx")
            packet = expected["second_getter"]
            _require(
                packet is not None
                and regs() == packet["entry_registers"]
                and words(entry - 12, 1) == [BASE + 0x379CE1],
                "assertion dispatch second handoff differs",
            )
        if pc == 0x379CE1:
            counts["second_return"] += 1
            if dispatch_negative == "second_return":
                flip_register("eax")
            packet = expected["second_getter"]
            _require(
                packet is not None
                and regs() == packet["return_registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & packet["flag_mask"]
                == packet["flags"],
                "assertion dispatch second return differs",
            )
        if address in (BASE + model.THIRD, BASE + model.FOURTH):
            _require(
                address == expected["endpoint"],
                "assertion dispatch selected child differs",
            )
            call = expected["call"]
            if dispatch_negative == "argument":
                flip_word(call["entry_esp"] + 4)
            if dispatch_negative == "caller_return":
                flip_word(call["entry_esp"] + 16)
            if dispatch_negative == "call_return":
                flip_word(call["entry_esp"])
            _require(
                words(call["entry_esp"], len(call["arguments"]) + 1)
                == [call["return_address"], *call["arguments"]],
                "assertion dispatch callee frame differs",
            )
            if dispatch_negative == "result":
                flip_register("eax")
            if dispatch_negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            corrupt = {
                "ancestor": entry + 16,
                "saved_ebp": entry - 4,
                "global": model.FIRST_GLOBAL,
                "global_padding": GLOBAL_PAGE + 0x777,
            }
            if dispatch_negative in corrupt:
                flip_word(corrupt[dispatch_negative])
            if dispatch_negative == "missing_read":
                dispatch_events.pop(
                    next(
                        i
                        for i, e in enumerate(dispatch_events)
                        if e["address"] == model.FIRST_GLOBAL
                    )
                )
            if dispatch_negative == "extra_read":
                dispatch_events.append(
                    dict(
                        access="read",
                        address=model.SECOND_GLOBAL,
                        width=4,
                        value=DISPATCH_PROFILES[vector["dispatch_profile"]][1],
                        rva=model.SECOND,
                    )
                )
            if dispatch_negative == "restored_global_write":
                value = DISPATCH_PROFILES[vector["dispatch_profile"]][0]
                dispatch_events.extend(
                    [
                        dict(
                            access="write",
                            address=model.FIRST_GLOBAL,
                            width=4,
                            value=value ^ 1,
                            rva=model.FIRST,
                        ),
                        dict(
                            access="write",
                            address=model.FIRST_GLOBAL,
                            width=4,
                            value=value,
                            rva=model.FIRST,
                        ),
                    ]
                )
            if dispatch_negative == "trace":
                dispatch_visited.append(model.THIRD)
            finished = True
            m.emu_stop()
            return
        _require(
            pc in dispatch_allowed
            and len(dispatch_visited) < len(expected["trace_rvas"])
            and pc == expected["trace_rvas"][len(dispatch_visited)],
            "assertion dispatch instruction path differs",
        )
        dispatch_visited.append(pc)

    def on_code(m, address, size, user):
        nonlocal resume, finished, phase, entry, actual_join, prefix_observation, expected
        if phase == "dispatch":
            dispatch_code(m, address, size, user)
            return
        if address == BOUNDARY:
            req = pe["boundary_request"]
            sp = m.reg_read(ids["esp"])
            if negative == "boundary_argument":
                flip_word(sp + 4)
            _require(
                sp == req["entry_esp"]
                and words(sp, 4) == req["retained_stack_words"]
                and regs() == req["entry_registers"],
                "callback assertion prefix boundary request or ABI differs",
            )
            if negative == "lua_identity":
                lua.stack[-1] = ("message", "wrong")
            frame = old_fixture["entry"] - 4
            corruption = dict(
                ancestor=old_fixture["entry"] + 8,
                userdata=old_fixture["userdata"],
                expression_page=pe["logical"]["native_boundary"]["arguments"][0],
                cookie=common.COOKIE,
                saved_register=frame - 28,
                local_userdata=frame - 20,
                boundary_return=sp,
                boundary_word=sp + 12,
                iat_padding=layout.IAT_PAGE,
            )
            if negative in corruption:
                at = corruption[negative]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "result":
                m.reg_write(ids["eax"], 1)
            if negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            if negative == "prefix_missing_read":
                events.pop(0)
            if negative == "prefix_trace_record":
                visited.append(f"0x{START:08x}")
            prefix_observation = verify_prefix()
            if negative == "join_register":
                flip_register("edx")
            if negative == "join_page_refresh":
                flip_word(common.COOKIE)
            if negative == "join_global_refresh":
                flip_word(model.FIRST_GLOBAL)
            captured_pages = {p: bytes(m.mem_read(p, 4096)) for p in initial_pages}
            actual_join = _check_join(
                dict(
                    registers=regs(),
                    flags=m.reg_read(x.UC_X86_REG_EFLAGS),
                    endpoint=m.reg_read(x.UC_X86_REG_EIP),
                    pages=captured_pages,
                    pages_sha256=_page_hashes(captured_pages),
                    prefix_observation=prefix_observation,
                ),
                vector,
                fixture,
                oracle,
            )
            # This computes a pure law over already validated captured pages.
            # It neither writes the machine nor runs another native engine.
            try:
                actual_prediction = model.apply_to_pages(
                    registers=actual_join["registers"],
                    pages=actual_join["pages"],
                    entry_flags=actual_join["flags"],
                )
            except model.AssertionParentDispatchError as exc:
                raise ConformanceError(str(exc)) from exc
            _require(
                _same_packet(actual_prediction, expected),
                "callback assertion dispatch join prediction differs",
            )
            entry = sp
            phase = "dispatch"
            # No emu_stop, reseed, page patch or GPR rewrite at this join.
            dispatch_code(m, address, size, user)
            return
        if address in layout.TARGETS.values():
            _require(
                len(calls) < len(pe["calls"]),
                "extra callback assertion prefix API call",
            )
            call = pe["calls"][len(calls)]
            sp = m.reg_read(ids["esp"])
            if negative == "api_argument" and not calls:
                m.mem_write(sp + 4, (old_fixture["state"] ^ 1).to_bytes(4, "little"))
            args = words(sp + 4, len(call["arguments"]))
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and [word(sp), *args] == [call["continuation"], *call["arguments"]]
                and regs() == call["entry_registers"],
                "callback assertion prefix API request or ABI differs",
            )
            result = lua.apply(call["api"], args)
            if call["api"] in ("lua_touserdata", "lua_getmetatable", "lua_toboolean"):
                _require(
                    result == call["response"]["eax"],
                    "callback assertion prefix Lua response differs",
                )
            response = dict(call["response"])
            if negative == "api_response" and len(calls) == len(pe["calls"]) - 1:
                response["eax"] = 1
            for name in ("eax", "ecx", "edx"):
                m.reg_write(ids[name], response[name])
            m.reg_write(x.UC_X86_REG_EFLAGS, response["eflags"])
            m.reg_write(ids["esp"], sp + 4)
            calls.append(dict(api=call["api"], arguments=args, response=response))
            resume = call["continuation"]
            m.emu_stop()
            return
        if negative == "upvalue_guard" and address == BASE + 0x2EC160:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) | 1)
        rva = f"0x{address-BASE:08x}"
        _require(
            rva in allowed
            and len(visited) < len(pe["trace_rvas"])
            and rva == pe["trace_rvas"][len(visited)],
            "callback assertion prefix native path differs",
        )
        visited.append(rva)

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        record = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                (value & ((1 << (8 * width)) - 1))
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        if phase == "prefix":
            events.append(record)
        else:
            _require(width == 4, "assertion dispatch unexpected memory width")
            _require(
                not writing or not GLOBAL_PAGE <= address < GLOBAL_PAGE + 4096,
                "assertion dispatch global write",
            )
            record["rva"] = m.reg_read(x.UC_X86_REG_EIP) - BASE
            dispatch_events.append(record)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    pc = BASE + START
    for _ in range(len(pe["calls"]) + 1):
        resume = None
        machine.emu_start(pc, 0, count=1400)
        if finished:
            break
        _require(resume is not None, "callback assertion prefix missing continuation")
        pc = resume
    _require(
        finished
        and phase == "dispatch"
        and actual_join is not None
        and machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "callback assertion dispatch frontier absent",
    )
    _require(
        counts
        == dict(
            first_entry=1,
            first_return=1,
            second_entry=int(expected["second_getter"] is not None),
            second_return=int(expected["second_getter"] is not None),
        ),
        "assertion dispatch getter counts differ",
    )
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        regs() == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"],
        "assertion dispatch final ABI differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == data
            for p, data in expected["pages"].items()
        ),
        "assertion dispatch protected pages differ",
    )
    _require(
        dispatch_events == expected["events"],
        "assertion dispatch ordered events differ",
    )
    _require(
        dispatch_visited == expected["trace_rvas"],
        "assertion dispatch instruction path differs",
    )
    _require(
        events == pe["events"]
        and visited == pe["trace_rvas"]
        and len(calls) == len(pe["calls"]),
        "callback assertion dispatch prefix phase differs",
    )
    result = dict(
        branch=expected["branch"],
        registers=regs(),
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        endpoint=f"0x{expected['endpoint']-BASE:08x}",
        trace_rvas=[f"0x{rva:08x}" for rva in dispatch_visited],
        events_sha256=_canonical_sha256(dispatch_events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(data).hexdigest()
                for p, data in expected["pages"].items()
            }
        ),
        second_getter=expected["second_getter"] is not None,
        arguments=copy.deepcopy(expected["call"]["arguments"]),
        opaque_child_executed=False,
    )
    join_projection = dict(
        registers=copy.deepcopy(actual_join["registers"]),
        flags=actual_join["flags"],
        endpoint=f"0x{actual_join['endpoint']-BASE:08x}",
        pages_sha256=copy.deepcopy(actual_join["pages_sha256"]),
    )
    observation = dict(
        vector=copy.deepcopy(vector),
        prefix_observation=prefix_observation,
        dispatch=result,
        join=join_projection,
        trace_rvas=visited + result["trace_rvas"],
        opaque_child_executed=False,
    )
    if capture is not None:
        capture(machine, ids, copy.deepcopy(oracle), copy.deepcopy(actual_join))
    return observation


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = common._load_executable(Path(executable))
    _require(
        digest == common.EXE_SHA256 and image.image_base == BASE,
        "exact callback assertion dispatch executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations, prefixes = [], {}
    for vector in vectors():
        observation = _run_case(codes, points, vector)
        previous = observation["prefix_observation"]
        key = tuple(vector[k] for k in ("alignment", "profile", "family"))
        _require(
            key not in prefixes or _same_packet(prefixes[key], previous),
            "callback assertion dispatch prefix recipe differs",
        )
        prefixes[key] = previous
        observations.append(observation)
    ordered_prefix = [
        prefixes[tuple(v[k] for k in ("alignment", "profile", "family"))]
        for v in prefix.vectors()
    ]
    previous = sources["callback_assertion_prefix"]
    prefix_hash = _canonical_sha256(ordered_prefix)
    prefix_sites = sorted(
        {pc for observation in ordered_prefix for pc in observation["trace_rvas"]}
    )
    _require(
        previous["vectors"] == prefix.vectors()
        and prefix_hash == previous["observations_sha256"]
        and prefix_sites == previous["executed_rvas"],
        "callback assertion dispatch sealed prefix differs",
    )
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    dispatch_sites = sorted(
        {
            pc
            for observation in observations
            for pc in observation["dispatch"]["trace_rvas"]
        }
    )
    _require(
        set(union) <= {point["rva"] for point in points},
        "callback assertion dispatch selected union differs",
    )
    controls = []
    sample = dict(alignment=15, profile=2, family="false", dispatch_profile=2)
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "callback assertion dispatch incidental control: "
                + kind
                + ": "
                + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError(
                "callback assertion dispatch control survived: " + kind
            )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{p-BASE:08x}",
                    end_rva=f"0x{p-BASE+len(body):08x}",
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                for p, body in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        prefix_executed_rvas=prefix_sites,
        dispatch_executed_rvas=dispatch_sites,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        prefix_observations_sha256=prefix_hash,
        join_observations_sha256=_canonical_sha256(
            [observation["join"] for observation in observations]
        ),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            unique_prefixes=len(ordered_prefix),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            prefix_native_instructions=sum(
                len(o["prefix_observation"]["trace_rvas"]) for o in observations
            ),
            dispatch_native_instructions=sum(
                len(o["dispatch"]["trace_rvas"]) for o in observations
            ),
            supplied_api_calls=sum(
                len(o["prefix_observation"]["api_calls"]) for o in observations
            ),
            assertion_joins=len(observations),
            first_getters=len(observations),
            second_getters=sum(o["dispatch"]["second_getter"] for o in observations),
            normal=sum(o["dispatch"]["branch"] == "normal" for o in observations),
            alternate=sum(o["dispatch"]["branch"] == "alternate" for o in observations),
            marker_calls=sum(v["family"] != "null" for v in vectors()),
            families={
                family: sum(v["family"] == family for v in vectors())
                for family in ("null", "absent", "nil", "false")
            },
            controls=len(controls),
            global_writes=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "One native callback prefix marker parent mode-three first getter and conditional second getter machine",
                "All old prefix pages data events instruction sites Lua calls stack identities GPRs and defined flags match before immediate fall-through",
                "The original prefix observation projection excludes the added getter global page and matches the pinned predecessor aggregate exactly",
                "Actual full boundary state is captured without a join stop reseed host patch or register rewrite",
                "Actual caller words form the exact normal four-argument or alternate three-argument frame",
                "Ordered dispatch reads writes all final pages full GPRs and independently defined flags agree before the opaque child executes",
            ],
            premises=[
                "Supplied normal cdecl Lua responses and the original four validation-failure families",
                "Four finite synthetic getter global recipes are installed before the callback starts; no bootstrap value is inferred",
                "Entry DF is clear and CMP TEST preserve it; AF is unclaimed after TEST",
            ],
            excluded=[
                "Opaque child instructions callback return imported DLL behavior CRT identity dialog abort trap unwind and ownership",
                "First-getter setter and invalid-mode descendants runtime global-value inference and whole-program accounting",
                "Injected event and path corruption records do not establish execution of their represented instructions",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "callback assertion dispatch executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    common._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed callback assertion dispatch receipt differs",
    )
    common._assert_publication_safe(evidence)
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
        "exact callback assertion dispatch receipt differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = prefix.encode_conformance
