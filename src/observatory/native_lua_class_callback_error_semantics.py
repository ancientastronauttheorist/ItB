"""Conditional returned-callback argument-marker rejection requests.

The upvalue marker is truthy; the argument marker is absent or Lua-false.
The endpoint is lua_error import entry, without executing it or supplying a
result. This standalone model gives no full-EAX, VM, unwind or assertion law.
"""

from __future__ import annotations


class CallbackErrorSemanticsError(RuntimeError):
    pass


def _pointer(value, label):
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise CallbackErrorSemanticsError(f"{label} must be nonzero uint32")


def apply(*, state, userdata, upvalue_kind, argument_has_metatable, argument_kind):
    """Describe compatible supplied responses up to argument rejection.

    Lua zero, empty string and table values are truthy independently of Python
    truth. With a metatable, nil/false argument markers are false. Without a
    metatable the marker kind must be nil and is never looked up.
    """
    _pointer(state, "state")
    _pointer(userdata, "userdata")
    if type(upvalue_kind) is not str or upvalue_kind not in (
        "zero",
        "empty_string",
        "table",
    ):
        raise CallbackErrorSemanticsError(
            "upvalue kind must be zero, empty_string or table"
        )
    if type(argument_has_metatable) is not bool:
        raise CallbackErrorSemanticsError("argument_has_metatable must be bool")
    if (
        type(argument_kind) is not str
        or argument_kind not in ("nil", "false")
        or (not argument_has_metatable and argument_kind != "nil")
    ):
        raise CallbackErrorSemanticsError(
            "argument kind must be nil/false with a metatable, or nil without one"
        )

    initial = [("argument", 1)]
    stack = list(initial)
    upvalue = ("userdata", userdata)
    calls = []

    def request(
        api, arguments, *, phase, result=0, remove=0, additions=(), literal_role=None
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

    request("lua_touserdata", [state, -10003], phase="direct", result=userdata)

    def marker(role, index, *, has_metatable, kind, truth):
        phase = role + "_marker"
        request(
            "lua_getmetatable",
            [state, index],
            phase=phase,
            result=int(has_metatable),
            additions=[("metatable", role)] if has_metatable else [],
        )
        if has_metatable:
            request(
                "lua_pushstring",
                [state, 0x0083C738],
                phase=phase,
                additions=[("literal", "marker_key")],
                literal_role="marker_key",
            )
            request(
                "lua_gettable",
                [state, -2],
                phase=phase,
                remove=1,
                additions=[("marker_value", role, kind)],
            )
            request("lua_toboolean", [state, -1], phase=phase, result=int(truth))
            request("lua_settop", [state, -3], phase=phase, remove=2)

    marker("upvalue", -10003, has_metatable=True, kind=upvalue_kind, truth=True)
    marker(
        "argument",
        1,
        has_metatable=argument_has_metatable,
        kind=argument_kind,
        truth=False,
    )
    request(
        "lua_pushstring",
        [state, 0x0083C99C],
        phase="error",
        additions=[("message", "argument_marker_error")],
        literal_role="argument_marker_error",
    )
    request(
        "lua_error",
        [state],
        phase="error",
        result=None,
        literal_role="argument_marker_error",
    )
    return dict(
        calls=calls,
        userdata=userdata,
        closure_upvalue=upvalue,
        initial_lua_stack=list(initial),
        error_entry_lua_stack=list(stack),
        lua_stack_delta=1,
        marker_results=dict(upvalue_al=1, argument_al=0),
        native_marker_requests=[
            dict(target_rva=0x002EB560, state=state, index=-10003, expected_al=1),
            dict(target_rva=0x002EB560, state=state, index=1, expected_al=0),
        ],
        marker_literal=dict(pointer=0x0083C738, text="__luabind_classrep"),
        error_literal=dict(
            pointer=0x0083C99C, text="expected class to derive from or a newline"
        ),
        endpoint=dict(
            api="lua_error",
            iat_rva=0x003D6498,
            call_rva=0x002EC195,
            return_rva=0x002EC19B,
            arguments=[state],
        ),
        frame=dict(
            ebp_delta_from_entry_esp=-4,
            idle_esp_delta_from_ebp=-36,
            pushstring_esp_delta_from_idle=-12,
            pushstring_esp_delta_from_ebp=-48,
            pushstring_stack_words=[0x006EC194, state, 0x0083C99C],
            error_esp_delta_from_idle=-16,
            error_esp_delta_from_ebp=-52,
            error_stack_words=[0x006EC19B, state, state, 0x0083C99C],
        ),
    )
