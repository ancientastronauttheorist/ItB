"""Independent conditional factory rejection requests ending at lua_error entry.

Only responses reached by short-circuit control flow are inspected. Earlier
APIs have supplied normal-return contracts. lua_error itself is not executed;
its import-entry boundary supplies no result, return, or unwind behavior.
"""

from __future__ import annotations


class FactoryErrorSemanticsError(RuntimeError):
    pass


def _word(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0xFFFFFFFF:
        raise FactoryErrorSemanticsError(
            f"{label} must be {'nonzero ' if nonzero else ''}uint32"
        )
    return value


def apply(
    *,
    state,
    argument_count,
    type_result,
    number_result,
    first_pointer,
    name_bytes,
    object_length,
):
    """Describe one rejected request sequence, without a lua_error response.

    Counts up to three use individual argument tokens. Larger counts use one
    compact argument-prefix token, avoiding allocation proportional to a
    supplied uint32 count. Later unused response contracts remain opaque.
    """
    _word(state, "state", nonzero=True)
    _word(argument_count, "argument count")
    initial = (
        [("argument", i + 1) for i in range(argument_count)]
        if argument_count <= 3
        else [("arguments", argument_count)]
    )
    calls = []

    def supplied(api, arguments, result):
        calls.append(
            dict(
                api=api,
                arguments=list(arguments),
                result=result,
                before=list(initial),
                after=list(initial),
                literal_role=None,
            )
        )

    supplied("lua_gettop", [state], argument_count)
    measured_length = None
    byte_reads = 0
    if argument_count != 1:
        reason = "argument_count"
    else:
        _word(type_result, "type result")
        supplied("lua_type", [state, 1], type_result)
        if type_result != 4:
            reason = "type"
        else:
            _word(number_result, "number result")
            supplied("lua_isnumber", [state, 1], number_result)
            if number_result != 0:
                reason = "numeric"
            else:
                _word(first_pointer, "first pointer", nonzero=True)
                if type(name_bytes) is not bytes:
                    raise FactoryErrorSemanticsError("name bytes must be bytes")
                measured_length = name_bytes.find(b"\0")
                if measured_length < 0:
                    raise FactoryErrorSemanticsError(
                        "name bytes must include a NUL terminator"
                    )
                if first_pointer + measured_length + 1 > 0xFFFFFFFF:
                    raise FactoryErrorSemanticsError(
                        "first pointer's terminating cursor wraps uint32"
                    )
                byte_reads = measured_length + 1
                supplied("lua_tolstring", [state, 1, 0], first_pointer)
                _word(object_length, "object length")
                supplied("lua_objlen", [state, 1], object_length)
                if object_length == measured_length:
                    raise FactoryErrorSemanticsError(
                        "accepted normal prefix is outside the error model"
                    )
                reason = "name_length"

    mismatch = reason == "name_length"
    role = "extra_nulls" if mismatch else "invalid_construct"
    literal = 0x0083CA88 if mismatch else 0x0083CA60
    text = (
        "luabind does not support class names with extra nulls"
        if mismatch
        else "invalid construct, expected class name"
    )
    final = initial + [("message", role)]
    calls.append(
        dict(
            api="lua_pushstring",
            arguments=[state, literal],
            result=0,
            before=list(initial),
            after=list(final),
            literal_role=role,
        )
    )
    calls.append(
        dict(
            api="lua_error",
            arguments=[state],
            result=None,
            before=list(final),
            after=list(final),
            literal_role=role,
        )
    )
    return dict(
        calls=calls,
        reason=reason,
        error_literal=dict(role=role, pointer=literal, text=text),
        argument_count=argument_count,
        argument_prefix_is_compact=argument_count > 3,
        initial_lua_stack=list(initial),
        error_entry_lua_stack=list(final),
        lua_stack_delta=1,
        measured_length=measured_length,
        byte_reads=byte_reads,
        endpoint=dict(
            api="lua_error",
            iat_rva=0x003D6498,
            call_rva=0x002EC2C8 if mismatch else 0x002EC28A,
            return_rva=0x002EC2CE if mismatch else 0x002EC290,
            arguments=[state],
        ),
        frame=dict(
            ebp_delta_from_entry_esp=-4,
            idle_esp_delta_from_ebp=-36,
            pushstring_esp_delta_from_idle=-12,
            pushstring_esp_delta_from_ebp=-48,
            pushstring_stack_words=[
                0x006EC2C7 if mismatch else 0x006EC289,
                state,
                literal,
            ],
            error_esp_delta_from_idle=-16,
            error_esp_delta_from_ebp=-52,
            error_stack_words=[
                0x006EC2CE if mismatch else 0x006EC290,
                state,
                state,
                literal,
            ],
        ),
    )
