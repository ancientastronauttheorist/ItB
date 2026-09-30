"""Complete finite native class factory with explicit Lua and heap contracts."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_record_conformance as record
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

factory, parent = record.factory, record.parent
ANALYSIS_KIND = "pe_native_lua_class_factory_conformance"
SEALED_SHA256 = "d8b36d30d732467edb54396ba22a3cd2a167dca15780f3020df18256c617dbcf"
RETURN = 0x0400A000
SOURCE_PINS = {
    **record.SOURCE_PINS,
    "record_conformance": (record.ANALYSIS_KIND, record.SEALED_SHA256),
}
SLOTS = dict(
    lua_createtable=0x3D6518,
    lua_pushvalue=0x3D64E4,
    luaL_ref=0x3D64E8,
    luaL_unref=0x3D64EC,
    lua_settop=0x3D6510,
    lua_gettable=0x3D64BC,
    lua_touserdata=0x3D649C,
    lua_rawgeti=0x3D64C0,
    lua_setmetatable=0x3D6530,
    lua_settable=0x3D6550,
    lua_pushcclosure=0x3D64A0,
)
TARGETS = {
    name: factory.IMPORT + 0x800 + 0x40 * i for i, name in enumerate(sorted(SLOTS))
}
ALL_SLOTS, ALL_TARGETS = {**factory.SLOTS, **SLOTS}, {**factory.TARGETS, **TARGETS}
LITERALS = {
    BASE + 0x43BF18: "__luabind_classes",
    BASE + 0x43BF6C: "__luabind_cast_graph",
    BASE + 0x42A86C: "__luabind_class_id_map",
}
ROLES = {
    "__luabind_classes": "classes",
    "__luabind_cast_graph": "cast_graph",
    "__luabind_class_id_map": "class_id_map",
}
EXCLUDED = (
    (0x2EADD5, 0x2EADE6),
    (0x2EAE19, 0x2EAE2A),
    (0x2EAE6A, 0x2EAE81),
    (0x2EAEAC, 0x2EAEC4),
)
ConformanceError, _require = factory.ConformanceError, factory._require


def vectors():
    return [
        dict(v, registry_profile=profile)
        for v in record.vectors()
        for profile in (0, 1, 2)
    ]


def _record_vector(vector):
    _require(
        type(vector) is dict
        and set(vector)
        == {
            "length",
            "pattern",
            "name_alignment",
            "equal_pointers",
            "profile",
            "record_bias",
            "record_alignment",
            "registry_profile",
        }
        and type(vector["registry_profile"]) is int
        and vector["registry_profile"] in (0, 1, 2),
        "factory full vector differs",
    )
    return {k: v for k, v in vector.items() if k != "registry_profile"}


def _spec(vector):
    profile = vector["registry_profile"]
    return dict(
        context_pointer=0x17000100 + 7 * profile,
        context_word=(0, 0x12345678, 0xFFFFFFFF)[profile],
        context_guard=(0, 1, 0xFFFFFFFF)[profile],
        metatable_reference=31 + 100 * profile,
        graph_pointer=0x18000100 + 7 * profile,
        id_map_pointer=0x19000100 + 31 * profile,
        references=[17 + 100 * profile, 19 + 100 * profile, 23 + 100 * profile],
    )


def _extend_fixture(vector, fixture):
    extended = record._extend_fixture(_record_vector(vector), fixture)
    pages = {p: bytearray(v) for p, v in extended["pages"].items()}
    for page in (0x17000000, 0x18000000, 0x19000000, *{p & ~4095 for p in LITERALS}):
        _require(page not in pages, "factory full mapping overlaps")
        pages[page] = bytearray(bytes([0xE3]) * 4096)
    for name, slot in SLOTS.items():
        factory._put(pages, BASE + slot, TARGETS[name])
    for address, text in LITERALS.items():
        for i, byte in enumerate(text.encode() + b"\0"):
            factory._put(pages, address + i, byte, 1)
    spec = _spec(vector)
    for offset, key in (
        (8, "context_word"),
        (12, "context_guard"),
        (16, "metatable_reference"),
    ):
        factory._put(pages, spec["context_pointer"] + offset, spec[key])
    return dict(extended, pages={p: bytes(v) for p, v in pages.items()}, spec=spec)


def _signed(word):
    return word if word < 0x80000000 else word - 0x100000000


class _Lua:
    """Runtime token controller independent of the native frame oracle."""

    def __init__(self, vector, fixture):
        self.vector, self.fixture, self.spec = vector, fixture, fixture["spec"]
        self.stack, self.registry, self.trace = [("argument", 1)], {}, []
        self.tables, self.strings, self.references = 0, 0, 0
        self.metatables, self.assignments = [], []

    def apply(self, api, args):
        f, s = self.fixture, self.spec
        _require(args[0] == f["state"], "factory Lua state identity differs")
        before = list(self.stack)
        result = 0
        logical_args = list(args)
        if api in ("lua_type", "lua_isnumber", "lua_tolstring", "lua_objlen"):
            _require(
                args[1] == 1 and self.stack[0] == ("argument", 1),
                "factory Lua argument identity differs",
            )
        if api == "lua_gettop":
            result = len(self.stack)
        elif api == "lua_type":
            result = 4
        elif api == "lua_isnumber":
            result = 0
        elif api == "lua_tolstring":
            _require(
                args[2] == 0 and self.strings < 2, "factory Lua string request differs"
            )
            result = f["first_pointer"] if self.strings == 0 else f["second_pointer"]
            self.strings += 1
        elif api == "lua_objlen":
            result = self.vector["length"]
        elif api == "lua_newuserdata":
            _require(args[1] == 72, "factory Lua userdata extent differs")
            result = f["userdata"]
            self.stack.append(("userdata", result))
        elif api == "lua_createtable":
            _require(args[1:] == [0, 0], "factory Lua table request differs")
            self.tables += 1
            self.stack.append(("table", self.tables))
        elif api == "lua_pushvalue":
            index = _signed(args[1])
            logical_args[1] = index
            _require(-len(self.stack) <= index < 0, "factory Lua value index differs")
            self.stack.append(self.stack[index])
        elif api == "luaL_ref":
            _require(
                _signed(args[1]) == -10000 and self.references < 3,
                "factory Lua ref request differs",
            )
            logical_args[1] = -10000
            result = s["references"][self.references]
            self.references += 1
            self.registry[result] = self.stack.pop()
        elif api == "lua_settop":
            index = _signed(args[1])
            logical_args[1] = index
            top = len(self.stack) + index + 1 if index < 0 else index
            _require(0 <= top <= len(self.stack), "factory Lua top request differs")
            self.stack = self.stack[:top]
        elif api == "lua_pushstring":
            pointer = args[1]
            if pointer in LITERALS:
                self.stack.append(("literal", ROLES[LITERALS[pointer]]))
            else:
                _require(
                    pointer == f["second_pointer"], "factory Lua name pointer differs"
                )
                self.stack.append(("name_pointer", pointer))
        elif api == "lua_gettable":
            _require(_signed(args[1]) == -10000, "factory Lua lookup index differs")
            logical_args[1] = -10000
            token = self.stack.pop()
            _require(
                token[0] == "literal" and token[1] in ROLES.values(),
                "factory Lua lookup key differs",
            )
            pointer = {
                "classes": s["context_pointer"],
                "cast_graph": s["graph_pointer"],
                "class_id_map": s["id_map_pointer"],
            }[token[1]]
            self.stack.append(("registry_value", token[1], pointer))
        elif api == "lua_touserdata":
            _require(
                _signed(args[1]) == -1 and self.stack[-1][0] == "registry_value",
                "factory Lua context identity differs",
            )
            logical_args[1] = -1
            result = self.stack[-1][2]
        elif api == "lua_rawgeti":
            _require(
                _signed(args[1]) == -10000 and args[2] == s["metatable_reference"],
                "factory Lua raw lookup differs",
            )
            logical_args[1] = -10000
            self.stack.append(("metatable", args[2]))
        elif api == "lua_setmetatable":
            _require(
                _signed(args[1]) == -2
                and self.stack[-2] == ("userdata", f["userdata"])
                and self.stack[-1] == ("metatable", s["metatable_reference"]),
                "factory Lua metatable identity differs",
            )
            logical_args[1] = -2
            self.metatables.append(
                dict(userdata=f["userdata"], reference=self.stack.pop()[1])
            )
            result = 1
        elif api == "lua_settable":
            _require(
                _signed(args[1]) == -10002
                and self.stack[-2:]
                == [("name_pointer", f["second_pointer"]), ("userdata", f["userdata"])],
                "factory Lua global assignment identity differs",
            )
            logical_args[1] = -10002
            self.stack = self.stack[:-2]
            self.assignments.append(
                dict(name_pointer=f["second_pointer"], userdata=f["userdata"])
            )
        elif api == "lua_pushcclosure":
            _require(
                args[1:] == [BASE + 0x2EC110, 1]
                and self.stack[-1] == ("userdata", f["userdata"]),
                "factory Lua closure identity differs",
            )
            upvalue = self.stack.pop()
            self.stack.append(("closure", BASE + 0x2EC110, upvalue))
        else:
            raise ConformanceError("unexpected factory Lua API")
        self.trace.append(
            dict(
                api=api,
                arguments=logical_args,
                result=result,
                before=before,
                after=list(self.stack),
            )
        )
        return result

    def result(self):
        return json.loads(
            json.dumps(
                dict(
                    calls=self.trace,
                    final_lua_stack=self.stack,
                    registry_bindings=[
                        dict(reference=r, value=v) for r, v in self.registry.items()
                    ],
                    metatable_setting_requests=self.metatables,
                    global_assignment_requests=self.assignments,
                )
            )
        )


def _add_flags(left, right):
    result = (left + right) & 0xFFFFFFFF
    return (
        int(left + right > 0xFFFFFFFF)
        | (4 if (result & 255).bit_count() % 2 == 0 else 0)
        | ((left ^ right ^ result) & 0x10)
        | (0x40 if result == 0 else 0)
        | (0x80 if result & 0x80000000 else 0)
        | (0x800 if (~(left ^ right) & (left ^ result)) & 0x80000000 else 0)
    )


def _extend_expected(vector, fixture, original):
    from src.observatory import native_lua_class_factory_semantics as model

    expected = record._extend_expected(vector, fixture, original)
    spec = fixture["spec"]
    logical = model.apply(
        state=fixture["state"],
        first_pointer=fixture["first_pointer"],
        second_pointer=fixture["second_pointer"],
        userdata=fixture["userdata"],
        name_bytes=factory._name(vector),
        **spec,
    )
    pages = {p: bytearray(v) for p, v in expected["pages"].items()}
    regs = dict(expected["registers"])
    events, calls = list(expected["events"]), list(expected["calls"])
    frame, userdata, state = regs["ebp"], fixture["userdata"], fixture["state"]

    def read(address, width=4):
        value = factory._raw(pages, address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(address, value, width=4):
        value &= (1 << (8 * width)) - 1
        events.append(dict(access="write", address=address, width=width, value=value))
        factory._put(pages, address, value, width)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def pop(register):
        regs[register] = read(regs["esp"])
        regs["esp"] += 4

    def arguments(*args):
        for arg in reversed(args):
            push(arg & 0xFFFFFFFF)

    def api(site, continuation, name, args, result=0, staged=None):
        if staged:
            _require(
                regs[staged] == ALL_TARGETS[name], "factory full staged binding differs"
            )
        else:
            _require(
                read(BASE + ALL_SLOTS[name]) == ALL_TARGETS[name],
                "factory full IAT binding differs",
            )
        push(BASE + continuation)
        response = factory._response(len(calls), result, vector["profile"])
        calls.append(
            dict(
                api=name,
                site_rva=f"0x{site:08x}",
                target=ALL_TARGETS[name],
                arguments=[arg & 0xFFFFFFFF for arg in args],
                continuation=BASE + continuation,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    # The first trailing zero argument was already pushed by the native resume.
    regs["esi"] = read(frame + 8)
    push(0)
    push(state)
    write(userdata + 60, 0)
    api(0x2EADA1, 0x2EADA7, "lua_createtable", [state, 0, 0])
    arguments(state, -1)
    api(0x2EADAA, 0x2EADB0, "lua_pushvalue", [state, -1])
    arguments(state, -10000)
    api(0x2EADB6, 0x2EADBC, "luaL_ref", [state, -10000], spec["references"][0])
    regs["edx"] = read(userdata + 28)
    regs["esp"] += 28
    regs["ebx"] = read(BASE + SLOTS["luaL_unref"])
    write(userdata + 28, state)
    regs["ecx"] = read(userdata + 32)
    write(userdata + 32, regs["eax"])
    _require(regs["edx"] == 0, "factory full first old-context premise differs")
    arguments(state, 0, 0)
    api(0x2EADEB, 0x2EADF1, "lua_createtable", [state, 0, 0])
    arguments(state, -1)
    api(0x2EADF4, 0x2EADFA, "lua_pushvalue", [state, -1])
    arguments(state, -10000)
    api(0x2EAE00, 0x2EAE06, "luaL_ref", [state, -10000], spec["references"][1])
    regs["edx"] = read(userdata + 36)
    regs["esp"] += 28
    write(userdata + 36, state)
    regs["ecx"] = read(userdata + 40)
    write(userdata + 40, regs["eax"])
    _require(regs["edx"] == 0, "factory full second old-context premise differs")
    regs["ebx"] = read(BASE + SLOTS["lua_settop"])
    arguments(state, -3)
    api(0x2EAE33, 0x2EAE35, "lua_settop", [state, -3], staged="ebx")
    arguments(state, BASE + 0x43BF18)
    api(0x2EAE3B, 0x2EAE41, "lua_pushstring", [state, BASE + 0x43BF18])
    arguments(state, -10000)
    api(0x2EAE47, 0x2EAE4D, "lua_gettable", [state, -10000])
    arguments(state, -1)
    api(0x2EAE50, 0x2EAE56, "lua_touserdata", [state, -1], spec["context_pointer"])
    arguments(state, -2)
    write(frame + 12, regs["eax"])
    api(0x2EAE5C, 0x2EAE5E, "lua_settop", [state, -2], staged="ebx")
    regs["eax"] = read(frame + 12)
    regs["esp"] += 40
    _require(
        read(regs["eax"] + 12) != 0xFFFFFFFE,
        "factory full context guard premise differs",
    )
    push(read(regs["eax"] + 16))
    push((-10000) & 0xFFFFFFFF)
    push(state)
    api(0x2EAE8A, 0x2EAE90, "lua_rawgeti", [state, -10000, spec["metatable_reference"]])
    arguments(state, -2)
    api(0x2EAE93, 0x2EAE99, "lua_setmetatable", [state, -2], 1)
    arguments(state, -1)
    api(0x2EAE9C, 0x2EAEA2, "lua_pushvalue", [state, -1])
    regs["ecx"] = read(userdata + 20)
    regs["esp"] += 28
    _require(regs["ecx"] == 0, "factory full third old-context premise differs")
    arguments(state, -10000)
    write(userdata + 24, 0xFFFFFFFE)
    write(userdata + 20, state)
    api(0x2EAED4, 0x2EAEDA, "luaL_ref", [state, -10000], spec["references"][2])
    write(userdata + 24, regs["eax"])
    regs["eax"] = read(frame + 12)
    arguments(state, BASE + 0x43BF6C)
    regs["eax"] = read(regs["eax"] + 8)
    write(userdata + 48, regs["eax"])
    api(0x2EAEEC, 0x2EAEF2, "lua_pushstring", [state, BASE + 0x43BF6C])
    arguments(state, -10000)
    api(0x2EAEF8, 0x2EAEFE, "lua_gettable", [state, -10000])
    arguments(state, -1)
    api(0x2EAF01, 0x2EAF07, "lua_touserdata", [state, -1], spec["graph_pointer"])
    arguments(state, -2)
    write(userdata + 64, regs["eax"])
    api(0x2EAF0D, 0x2EAF0F, "lua_settop", [state, -2], staged="ebx")
    arguments(state, BASE + 0x42A86C)
    api(0x2EAF15, 0x2EAF1B, "lua_pushstring", [state, BASE + 0x42A86C])
    arguments(state, -10000)
    api(0x2EAF21, 0x2EAF27, "lua_gettable", [state, -10000])
    arguments(state, -1)
    api(0x2EAF2A, 0x2EAF30, "lua_touserdata", [state, -1], spec["id_map_pointer"])
    regs["esp"] += 64
    write(userdata + 68, regs["eax"])
    arguments(state, -2)
    api(0x2EAF39, 0x2EAF3B, "lua_settop", [state, -2], staged="ebx")
    regs["esp"] += 8
    regs["eax"] = regs["edi"]
    regs["ecx"] = read(frame - 12)
    write(0, regs["ecx"])
    for r in ("ecx", "edi", "esi", "ebx"):
        pop(r)
    regs["esp"] = regs["ebp"]
    pop("ebp")
    _require(
        read(regs["esp"]) == BASE + 0x2EC307, "factory full initializer return differs"
    )
    regs["esp"] += 12
    outer = regs["ebp"]
    arguments(state, regs["edi"])
    api(
        0x2EC309,
        0x2EC30B,
        "lua_pushstring",
        [state, fixture["second_pointer"]],
        staged="ebx",
    )
    arguments(state, -2)
    api(0x2EC30E, 0x2EC314, "lua_pushvalue", [state, -2])
    arguments(state, -10002)
    api(0x2EC31A, 0x2EC320, "lua_settable", [state, -10002])
    arguments(state, BASE + 0x2EC110, 1)
    api(0x2EC328, 0x2EC32E, "lua_pushcclosure", [state, BASE + 0x2EC110, 1])
    flags = _add_flags(regs["esp"], 36)
    regs["esp"] += 36
    regs["eax"] = 1
    regs["ecx"] = read(outer - 12)
    write(0, regs["ecx"])
    for r in ("ecx", "edi", "esi", "ebx"):
        pop(r)
    regs["esp"] = regs["ebp"]
    pop("ebp")
    _require(read(regs["esp"]) == RETURN, "factory full return address differs")
    regs["esp"] += 4
    _require(
        len(calls) == 34
        and [(c["api"], c["arguments"], c["response"]["eax"]) for c in calls]
        == [
            (c["api"], [a & 0xFFFFFFFF for a in c["arguments"]], c["result"])
            for c in logical["calls"]
        ],
        "factory full logical request sequence differs",
    )
    _require(
        all(
            factory._raw(pages, userdata + offset) == value
            for offset, value in logical["final_fields"].items()
        )
        and factory._raw(pages, userdata + 52) == fixture["record"],
        "factory full logical final fields differ",
    )
    lua_result = dict(
        calls=[
            {k: c[k] for k in ("api", "arguments", "result", "before", "after")}
            for c in logical["calls"]
        ],
        final_lua_stack=logical["final_lua_stack"],
        registry_bindings=logical["registry_bindings"],
        metatable_setting_requests=[
            dict(userdata=userdata, reference=spec["metatable_reference"])
        ],
        global_assignment_requests=[
            dict(name_pointer=fixture["second_pointer"], userdata=userdata)
        ],
    )
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
        flags=flags,
        calls=calls,
        events=events,
        heap_calls=expected["heap_calls"],
        record=fixture["record"],
        lua_result=json.loads(json.dumps(lua_result)),
        logical=dict(factory=logical, record=expected["logical"]["record"]),
    )


def _corruption(fixture, expected):
    outer = fixture["entry"] - 4
    inner = outer - 52
    return dict(
        initializer_name=fixture["userdata"] + 16,
        first_reference=fixture["userdata"] + 32,
        second_reference=fixture["userdata"] + 40,
        third_reference=fixture["userdata"] + 24,
        context_word=fixture["userdata"] + 48,
        graph=fixture["userdata"] + 64,
        id_map=fixture["userdata"] + 68,
        metatable_reference=fixture["spec"]["context_pointer"] + 16,
        outer_fs=outer - 12,
        inner_fs=inner - 12,
        overwritten_argument=inner + 12,
        factory_return=fixture["entry"],
        record_link=fixture["record"],
        record_marker=fixture["record"] + 12,
        record_padding=fixture["record"] + 14,
        record_tail=fixture["record"] + 23,
        heap_global=record.allocation.HEAP_GLOBAL,
        stored_record=fixture["userdata"] + 52,
    )


def _before_instruction(machine, address, negative, fixture, expected):
    if negative == "context_guard" and address == BASE + 0x2EAE64:
        machine.mem_write(
            fixture["spec"]["context_pointer"] + 12, (0xFFFFFFFE).to_bytes(4, "little")
        )


def _endpoint_mutation(machine, negative, fixture, expected, lua, ids):
    if negative == "return_count":
        machine.reg_write(ids["eax"], 2)
    elif negative == "lua_identity":
        lua.registry[fixture["spec"]["references"][0]] = (
            "userdata",
            fixture["userdata"],
        )
    elif negative == "closure_identity":
        lua.stack[-1] = (
            "closure",
            BASE + 0x2EC110,
            ("userdata", fixture["userdata"] ^ 1),
        )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "factory full source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    payload, points, continuation = record._load_code(data, image, sources)
    owner = _decode_body(data, image, sources["program_facts"], factory.START)
    full_factory = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(full_factory) == 296
        and hashlib.sha256(full_factory).hexdigest() == factory.OWNER_SHA256,
        "factory full owner differs",
    )
    initializer = _decode_body(data, image, sources["program_facts"], parent.START)
    full_initializer = b"".join(bytes(r.bytes) for r in initializer)
    _require(
        len(full_initializer) == 612
        and hashlib.sha256(full_initializer).hexdigest() == parent.BODY_SHA256,
        "factory full initializer differs",
    )
    for address, text in LITERALS.items():
        offset = image.rva_to_file_offset(address - BASE)
        expected = text.encode() + b"\0"
        _require(
            data[offset : offset + len(expected)] == expected,
            "factory full literal differs",
        )
    codes = {
        a: b
        for a, b in continuation["codes"].items()
        if not BASE + parent.START <= a < BASE + parent.START + 612
    }
    codes[BASE + parent.START] = full_initializer
    retained = [
        p
        for p in points
        if not factory.START <= int(p["rva"], 16) < factory.START + 296
        and not parent.START <= int(p["rva"], 16) < parent.START + 612
    ]
    points = sorted(
        retained + [_point(r) for r in owner] + [_point(r) for r in initializer],
        key=lambda p: int(p["rva"], 16),
    )
    return (
        full_factory,
        points,
        dict(
            codes=codes,
            endpoint=RETURN,
            instruction_count=231,
            extend_expected=_extend_expected,
            corruption=_corruption,
            heap_target=factory.IMPORT,
            api_targets=TARGETS,
            flag_mask=0xCD5,
            excluded_ranges=EXCLUDED,
            before_instruction=_before_instruction,
            endpoint_mutation=_endpoint_mutation,
        ),
    )


def _run_case(payload, points, continuation, vector, negative=None):
    record_vector = _record_vector(vector)
    base = record._base_vector(record_vector)
    installed = dict(
        continuation,
        extend_fixture=lambda v, f: _extend_fixture(vector, f),
        lua_observer=lambda v, f: _Lua(base, f),
    )
    result = factory._run_case(payload, points, base, negative, continuation=installed)
    result.update(
        vector=vector,
        initializer_instructions=157,
        self_linked_helper_instructions=16,
        allocation_native_instructions=34,
        factory_tail_instructions=24,
    )
    return result


CONTROLS = {
    key: value
    for key, value in record.CONTROLS.items()
    if key
    not in (
        "initializer_sentinel",
        "initializer_unwritten",
        "helper_return",
        "handoff_pointer",
    )
}
CONTROLS.update(
    {
        key: "factory protected memory differs"
        for key in (
            "first_reference",
            "second_reference",
            "third_reference",
            "context_word",
            "graph",
            "id_map",
            "metatable_reference",
            "factory_return",
        )
    }
)
CONTROLS.update(
    second_response="factory Lua response contract differs",
    length_response="factory Lua response contract differs",
    heap_response="factory API request or ABI differs",
    context_guard="factory left normal prefix",
    return_count="factory registers or defined flags differ",
    lua_identity="factory Lua identity trace differs",
    closure_identity="factory Lua identity trace differs",
)


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact factory full executable differs",
    )
    payload, points, continuation = _load_code(data, image, sources)
    observations = [_run_case(payload, points, continuation, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    required = set(sources["record_conformance"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if factory.END <= int(p["rva"], 16) < factory.START + 296
    )
    required.update(
        p["rva"]
        for p in points
        if record.END <= int(p["rva"], 16) < parent.START + 612
        and not any(a <= int(p["rva"], 16) < b for a, b in EXCLUDED)
    )
    _require(
        set(union) == required and len(required) == 302,
        "factory full normal coverage differs",
    )
    sample = next(
        v
        for v in vectors()
        if v["length"] == 16
        and not v["equal_pointers"]
        and v["profile"] == 1
        and v["record_bias"] == 0xFFF
        and v["record_alignment"] == 0
        and v["registry_profile"] == 2
    )
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, continuation, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory full control failed incidentally: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory full control survived: " + kind)
    codes = {BASE + factory.START: payload, **continuation["codes"]}
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a-BASE:08x}",
                    end_rva=f"0x{a-BASE+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=34 * len(observations),
            heap_calls=len(observations),
            controls=len(controls),
            initializer_instructions=157 * len(observations),
            self_linked_helper_instructions=16 * len(observations),
            allocation_native_instructions=34 * len(observations),
            factory_tail_instructions=24 * len(observations),
            result_count=1,
            closure_upvalues=1,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=sorted(ALL_SLOTS.keys() - {"luaL_unref"}) + ["HeapAlloc"],
            checked=[
                "Complete native factory and initializer normal returns with actual allocated record",
                "Native retry, thunk and heap wrapper with one exact successful HeapAlloc contract",
                "Independent full userdata fields, context reads, native memory events and all mapped pages",
                "Both FS registrations restored and original caller ancestors and nonvolatile GPRs preserved",
                "All 34 physical Lua API frames and independent continuous token-stack trace",
                "Three registry identities, metatable and global assignment requests, and one closure upvalue",
                "One native return result, exact continuation, defined ADD flags and clear DF",
            ],
            premises=[
                "All normal sealed factory and record contracts",
                "Three distinct positive registry references and compatible supplied registry and metatable values",
                "Readable disjoint context with guard different from minus two",
                "Normal cdecl Lua responses preserve mapped pages and nonvolatile registers",
            ],
            excluded=[
                "Actual imported DLL or Lua VM behavior and metamethod or host effects",
                "Allocation failure, prior-reference unref arms, assertion, exceptions and cookie verification",
                "Equality or validation of second name pointer contents",
                "Invocation of returned closure, arbitrary memory domains and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory full executable changed",
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
        "sealed factory full conformance differs",
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
        "exact factory full conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
