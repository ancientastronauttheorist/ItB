"""Independent conditional Lua requests for a complete normal factory path.

Lua API responses and readable native context fields are supplied contracts.
The native allocator is outside this model. Pointer fields receive only
offset-level meanings; the second name pointer's bytes remain opaque.
"""

from __future__ import annotations

import copy

from src.observatory import native_lua_class_factory_prefix_semantics as prefix


class FactoryError(RuntimeError):
    pass


def _word(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0xFFFFFFFF:
        raise FactoryError(f"{label} must be {'nonzero ' if nonzero else ''}uint32")
    return value


def _reference(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0x7FFFFFFF:
        raise FactoryError(
            f"{label} must be {'positive' if nonzero else 'nonnegative'} int32"
        )
    return value


def apply(
    *,
    state,
    first_pointer,
    second_pointer,
    userdata,
    name_bytes,
    context_pointer,
    context_word,
    context_guard,
    metatable_reference,
    graph_pointer,
    id_map_pointer,
    references,
):
    """Return 34 normal Lua contracts, stack snapshots, and offset-only fields.

    The three references are supplied positive luaL_ref results. Context reads
    supply its +8 word, +12 guard, and +16 metatable reference. The forbidden
    guard value -2 would enter an assertion arm and is outside this model.
    No native helper, Lua VM, metamethod, registry, or heap mutation executes.
    """
    for value, label in (
        (context_pointer, "context pointer"),
        (graph_pointer, "graph pointer"),
        (id_map_pointer, "id map pointer"),
    ):
        _word(value, label, nonzero=True)
    _word(context_word, "context word")
    _word(context_guard, "context guard")
    if context_guard == 0xFFFFFFFE:
        raise FactoryError("context guard enters the excluded assertion arm")
    _reference(metatable_reference, "metatable reference")
    if type(references) is not list or len(references) != 3:
        raise FactoryError("references must be a list of three positive int32 results")
    refs = [_reference(value, "reference", nonzero=True) for value in references]
    if len(set(refs)) != 3:
        raise FactoryError("fresh registry references must be distinct")
    try:
        first = prefix.apply(
            name_bytes,
            state=state,
            first_pointer=first_pointer,
            second_pointer=second_pointer,
            userdata=userdata,
        )
    except prefix.FactoryPrefixError as exc:
        raise FactoryError(str(exc)) from exc
    if userdata + 71 > 0xFFFFFFFF:
        raise FactoryError("userdata's highest written byte wraps uint32")
    if context_pointer + 19 > 0xFFFFFFFF:
        raise FactoryError("context's highest read byte wraps uint32")

    calls = [
        {
            key: copy.deepcopy(call[key])
            for key in ("api", "arguments", "result", "before", "after")
        }
        | dict(phase="factory_prefix", literal_role=None)
        for call in first["calls"]
    ]
    stack = list(first["final_lua_stack"])
    userdata_value = ("userdata", userdata)
    table1, table2 = ("table", 1), ("table", 2)
    metatable = ("metatable", metatable_reference)
    literal_requests = []

    def request(
        api,
        arguments,
        *,
        result=0,
        remove=0,
        additions=(),
        literal_role=None,
        phase="initializer",
    ):
        before = list(stack)
        if remove:
            del stack[-remove:]
        stack.extend(additions)
        calls.append(
            dict(
                api=api,
                arguments=list(arguments),
                result=result,
                before=before,
                after=list(stack),
                phase=phase,
                literal_role=literal_role,
            )
        )

    for table, reference in ((table1, refs[0]), (table2, refs[1])):
        request("lua_createtable", [state, 0, 0], additions=[table])
        request("lua_pushvalue", [state, -1], additions=[table])
        request("luaL_ref", [state, -10000], result=reference, remove=1)
    request("lua_settop", [state, -3], remove=2)

    def lookup(role, literal_pointer, returned_pointer):
        literal = ("literal", role)
        value = ("registry_value", role, returned_pointer)
        literal_requests.append(dict(role=role, pointer=literal_pointer))
        request(
            "lua_pushstring",
            [state, literal_pointer],
            additions=[literal],
            literal_role=role,
        )
        request("lua_gettable", [state, -10000], remove=1, additions=[value])
        request("lua_touserdata", [state, -1], result=returned_pointer)
        request("lua_settop", [state, -2], remove=1)

    lookup("classes", 0x0083BF18, context_pointer)
    request("lua_rawgeti", [state, -10000, metatable_reference], additions=[metatable])
    request("lua_setmetatable", [state, -2], result=1, remove=1)
    request("lua_pushvalue", [state, -1], additions=[userdata_value])
    request("luaL_ref", [state, -10000], result=refs[2], remove=1)
    lookup("cast_graph", 0x0083BF6C, graph_pointer)
    lookup("class_id_map", 0x0082A86C, id_map_pointer)

    name_value = ("name_pointer", second_pointer)
    callback_pointer = 0x006EC110
    closure_value = ("closure", callback_pointer, userdata_value)
    request(
        "lua_pushstring",
        [state, second_pointer],
        additions=[name_value],
        literal_role="opaque_name",
        phase="factory_tail",
    )
    request(
        "lua_pushvalue", [state, -2], additions=[userdata_value], phase="factory_tail"
    )
    request("lua_settable", [state, -10002], remove=2, phase="factory_tail")
    request(
        "lua_pushcclosure",
        [state, callback_pointer, 1],
        remove=1,
        additions=[closure_value],
        phase="factory_tail",
    )

    final_fields = {
        0: 0x0089D1D4,
        4: 0,
        8: 0,
        12: 0,
        16: second_pointer,
        20: state,
        24: refs[2],
        28: state,
        32: refs[0],
        36: state,
        40: refs[1],
        44: 1,
        48: context_word,
        56: 0,
        60: 0,
        64: graph_pointer,
        68: id_map_pointer,
    }
    return dict(
        calls=calls,
        measured_length=first["measured_length"],
        initial_lua_stack=list(first["initial_lua_stack"]),
        final_lua_stack=list(stack),
        lua_stack_delta=1,
        result_count=1,
        selected_results=[closure_value],
        closure=dict(
            target_rva=0x002EC110,
            target_pointer=callback_pointer,
            upvalues=[userdata_value],
        ),
        registry_bindings=[
            dict(reference=reference, value=value)
            for reference, value in (
                (refs[0], table1),
                (refs[1], table2),
                (refs[2], userdata_value),
            )
        ],
        metatable_setting_request=dict(
            index=-2, userdata=userdata, reference=metatable_reference
        ),
        global_assignment_request=dict(
            index=-10002, key_pointer=second_pointer, userdata=userdata
        ),
        literal_requests=literal_requests,
        final_fields=final_fields,
        unmodeled_fields=[52],
        context_reads=[
            dict(offset=offset, value=value)
            for offset, value in (
                (12, context_guard),
                (16, metatable_reference),
                (8, context_word),
            )
        ],
    )
