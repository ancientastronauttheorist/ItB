"""Conditional callback requests before either native assertion-helper entry."""

from __future__ import annotations


class AssertionPrefixError(RuntimeError):
    pass


def apply(*, state, userdata, has_metatable, value_kind):
    if type(state) is not int or not 1 <= state <= 0xFFFFFFFF:
        raise AssertionPrefixError("state must be nonzero uint32")
    if type(userdata) is not int or not 0 <= userdata <= 0xFFFFFFFF:
        raise AssertionPrefixError("userdata must be uint32")
    stack = [("argument", 1)]
    initial = list(stack)
    calls = []

    def request(
        name, args, result=0, phase="direct", role=None, remove=0, additions=()
    ):
        before = list(stack)
        if remove:
            del stack[-remove:]
        stack.extend(additions)
        calls.append(
            dict(
                api=name,
                arguments=list(args),
                result=result,
                before=before,
                after=list(stack),
                phase=phase,
                literal_role=role,
            )
        )

    request("lua_touserdata", [state, -10003], userdata)
    if userdata == 0:
        reason = "null_upvalue"
        words = [0x83CA00, 0x83C9C8, 69]
        continuation = 0x6EC151
        call = 0x2EC14C
    else:
        if type(has_metatable) is not bool:
            raise AssertionPrefixError("has_metatable must be bool")
        if (
            type(value_kind) is not str
            or value_kind not in ("nil", "false")
            or (not has_metatable and value_kind != "nil")
        ):
            raise AssertionPrefixError(
                "false marker requires nil or false, or nil without a metatable"
            )
        phase = "upvalue_marker"
        request(
            "lua_getmetatable",
            [state, -10003],
            int(has_metatable),
            phase,
            additions=[("metatable", "upvalue")] if has_metatable else [],
        )
        if has_metatable:
            request(
                "lua_pushstring",
                [state, 0x83C738],
                phase=phase,
                role="marker_key",
                additions=[("literal", "marker_key")],
            )
            request(
                "lua_gettable",
                [state, -2],
                phase=phase,
                remove=1,
                additions=[("marker_value", "upvalue", value_kind)],
            )
            request("lua_toboolean", [state, -1], 0, phase)
            request("lua_settop", [state, -3], phase=phase, remove=2)
        reason = "false_upvalue_marker"
        words = [0x83C908, 0x83C9C8, 70]
        continuation = 0x6EC175
        call = 0x2EC170
    return dict(
        calls=calls,
        reason=reason,
        userdata=userdata,
        initial_lua_stack=initial,
        final_lua_stack=list(stack),
        lua_stack_delta=0,
        marker_al=None if userdata == 0 else 0,
        native_boundary=dict(
            target_rva=0x379CC2,
            call_rva=call,
            continuation=continuation,
            arguments=words,
        ),
        frame=dict(
            ebp_delta_from_entry_esp=-4,
            idle_esp_delta_from_ebp=-36,
            boundary_esp_delta_from_ebp=-52,
            stack_words=[continuation, *words],
        ),
    )
