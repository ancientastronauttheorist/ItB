"""Independent conditional requests for the normal factory validation prefix.

The seven Lua responses are supplied normal contracts, not computed Lua
behavior. Only the first pointer's synthetic bytes are inspected. The second
pointer is passed to an opaque initializer without inspecting its contents.
This model executes neither native instructions nor Lua, allocation or SEH.
"""

from __future__ import annotations


class FactoryPrefixError(RuntimeError):
    pass


def _word(value, label):
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise FactoryPrefixError(f"{label} must be nonzero uint32")
    return value


def apply(name_bytes, *, state, first_pointer, second_pointer, userdata):
    """Describe one accepted prefix ending at the opaque initializer entry.

    ``name_bytes`` is a readable synthetic byte sequence at ``first_pointer``;
    it must include a NUL. The supplied lua_objlen contract equals the offset
    of its first NUL, irrespective of any later synthetic bytes. No equality
    between first/second pointers or their contents is assumed. The userdata
    contract is nonzero so the initializer call is taken.
    """
    if type(name_bytes) is not bytes:
        raise FactoryPrefixError("name bytes must be bytes")
    for value, label in (
        (state, "state"),
        (first_pointer, "first pointer"),
        (second_pointer, "second pointer"),
        (userdata, "userdata"),
    ):
        _word(value, label)
    length = name_bytes.find(b"\0")
    if length < 0:
        raise FactoryPrefixError("name bytes must include a NUL terminator")
    if first_pointer + length + 1 > 0xFFFFFFFF:
        raise FactoryPrefixError("first pointer's terminating cursor wraps uint32")

    initial = [("argument", 1)]
    final = initial + [("userdata", userdata)]
    responses = (
        ("lua_gettop", [state], 1),
        ("lua_type", [state, 1], 4),
        ("lua_isnumber", [state, 1], 0),
        ("lua_tolstring", [state, 1, 0], first_pointer),
        ("lua_objlen", [state, 1], length),
        ("lua_tolstring", [state, 1, 0], second_pointer),
        ("lua_newuserdata", [state, 72], userdata),
    )
    calls = [
        dict(
            api=api,
            arguments=list(arguments),
            result=result,
            before=list(initial),
            after=list(final if api == "lua_newuserdata" else initial),
            # At each API entry the argument words follow its return address.
            entry_esp_delta_from_idle=-4 * (len(arguments) + 1),
        )
        for api, arguments, result in responses
    ]
    return dict(
        measured_length=length,
        byte_reads=length + 1,
        first_terminal_cursor=first_pointer + length + 1,
        prefix_instruction_count=71 + 4 * length,
        calls=calls,
        initial_lua_stack=list(initial),
        final_lua_stack=list(final),
        lua_stack_delta=1,
        initializer=dict(
            target_rva=0x002EACF0,
            return_rva=0x002EC307,
            arguments=[state, second_pointer],
            registers=dict(eax=userdata, ecx=userdata, esi=state, edi=second_pointer),
        ),
        frame=dict(
            ebp_delta_from_entry_esp=-4,
            idle_esp_delta_from_ebp=-36,
            initializer_esp_delta_from_ebp=-48,
            initializer_stack_words=[0x006EC307, state, second_pointer],
            local_stores=[
                dict(ebp_offset=-16, value=userdata),
                dict(ebp_offset=-20, value=userdata),
                dict(ebp_offset=-4, value=0),
            ],
        ),
    )
