"""Bounded logical mapping from a factory closure to callback class entry.

Both marker lookups supply truthy normal contracts. The twelve Lua requests
restore the original argument prefix before the native class operation entry.
Extents describe the supplied userdata and record addresses; this model reads
no memory, establishes no ownership, and executes no VM or native instruction.
"""

from __future__ import annotations


class FactoryCallbackEntryError(RuntimeError):
    pass


def _word(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0xFFFFFFFF:
        raise FactoryCallbackEntryError(
            f"{label} must be {'nonzero ' if nonzero else ''}uint32"
        )
    return value


def _extent(pointer, size, label):
    _word(pointer, label, nonzero=True)
    if pointer + size - 1 > 0xFFFFFFFF:
        raise FactoryCallbackEntryError(f"{label} extent wraps uint32")
    return dict(pointer=pointer, size=size)


def _signed(word):
    return word if word < 0x80000000 else word - 0x100000000


def apply(
    *,
    state,
    userdata,
    record_pointer,
    source_pointer,
    callback_entry,
    registers,
    closure_target,
    closure_upvalues,
    upvalue_has_metatable,
    argument_has_metatable,
    upvalue_marker_kind,
    argument_marker_kind,
):
    """Return detached requests and the class caller packet at T minus 48.

    ``registers`` supplies eight uint32 entry GPRs with ESP equal to T. The
    returned closure must target 0x006ec110 and retain exactly the userdata
    upvalue. Lua zero, empty string and table marker values are all truthy.
    Source and userdata identities may coincide. No pointee bytes, flags,
    class-operation results or callback-return behavior are modeled.
    """
    _word(state, "state", nonzero=True)
    userdata_extent = _extent(userdata, 72, "userdata")
    record_extent = _extent(record_pointer, 24, "record pointer")
    _word(source_pointer, "source pointer", nonzero=True)
    if type(callback_entry) is not int or not 48 <= callback_entry <= 0xFFFFFFF8:
        raise FactoryCallbackEntryError("callback entry must cover T-48 through T+7")
    if (
        type(registers) is not dict
        or set(registers) != {"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"}
        or any(
            type(word) is not int or not 0 <= word <= 0xFFFFFFFF
            for word in registers.values()
        )
        or registers["esp"] != callback_entry
    ):
        raise FactoryCallbackEntryError(
            "callback registers must be eight uint32 GPRs with ESP=T"
        )
    if type(closure_target) is not int or closure_target != 0x006EC110:
        raise FactoryCallbackEntryError("closure target must be 0x006ec110")
    if (
        type(closure_upvalues) is not list
        or len(closure_upvalues) != 1
        or type(closure_upvalues[0]) is not int
        or closure_upvalues[0] != userdata
    ):
        raise FactoryCallbackEntryError(
            "closure must retain exactly the userdata upvalue"
        )
    if type(upvalue_has_metatable) is not bool or not upvalue_has_metatable:
        raise FactoryCallbackEntryError("upvalue must have a metatable")
    if type(argument_has_metatable) is not bool or not argument_has_metatable:
        raise FactoryCallbackEntryError("argument must have a metatable")
    for kind, label in (
        (upvalue_marker_kind, "upvalue"),
        (argument_marker_kind, "argument"),
    ):
        if type(kind) is not str or kind not in ("zero", "empty_string", "table"):
            raise FactoryCallbackEntryError(
                f"{label} marker must be zero, empty_string or table"
            )

    initial = [("argument", source_pointer)]
    stack, calls = list(initial), []

    def request(api, args, *, result=0, group="direct", remove=0, additions=()):
        before = list(stack)
        if remove:
            del stack[-remove:]
        stack.extend(additions)
        calls.append(
            dict(
                api=api,
                arguments=[_signed(word) for word in args],
                result=result,
                before=before,
                after=list(stack),
                group=group,
            )
        )

    request("lua_touserdata", [state, -10003], result=userdata)

    def marker(identity, index, kind, group):
        request(
            "lua_getmetatable",
            [state, index],
            result=1,
            group=group,
            additions=[("metatable", identity)],
        )
        request(
            "lua_pushstring",
            [state, 0x0083C738],
            group=group,
            additions=[("marker_key", identity)],
        )
        request(
            "lua_gettable",
            [state, -2],
            group=group,
            remove=1,
            additions=[("marker_value", identity, kind)],
        )
        request("lua_toboolean", [state, -1], result=1, group=group)
        request("lua_settop", [state, -3], group=group, remove=2)

    marker(userdata, -10003, upvalue_marker_kind, "marker0")
    marker(source_pointer, 1, argument_marker_kind, "marker1")
    request("lua_touserdata", [state, 1], result=source_pointer)
    address = callback_entry - 20
    return dict(
        calls=calls,
        initial_lua_stack=list(initial),
        boundary_lua_stack=list(stack),
        closure_target=closure_target,
        closure_upvalues=list(closure_upvalues),
        userdata_extent=userdata_extent,
        record_extent=record_extent,
        class_entry_rva=0x002EB140,
        class_caller=dict(
            return_address=0x006EC1BD,
            argaddress=address,
            argument_record=[0, source_pointer],
            registers=dict(
                eax=address,
                ebx=state,
                ecx=userdata,
                edx=0xB1000002,
                esi=userdata,
                edi=source_pointer,
                ebp=callback_entry - 4,
                esp=callback_entry - 48,
            ),
        ),
    )
