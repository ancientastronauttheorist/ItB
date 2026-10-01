"""Bounded empty-class continuation of the factory's returned callback.

Source and destination trees are supplied empty. The original callback pair
is appended to a supplied successful first eight-byte heap allocation. No
memory is read, no native instruction or Lua VM executes, and no ownership
or general tree-operation result is established by this logical model.
"""

from __future__ import annotations

from src.observatory import native_lua_class_factory_callback_entry_semantics as entry


class FactoryCallbackEmptyClassError(entry.FactoryCallbackEntryError):
    pass


def _word(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0xFFFFFFFF:
        raise FactoryCallbackEmptyClassError(
            f"{label} must be {'nonzero ' if nonzero else ''}uint32"
        )
    return value


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
    vector_pointer,
    cookie,
):
    """Return the twelve-request prefix and empty-class normal return packet.

    The prefix supplies its original ``[0, source_pointer]`` record at T-20;
    the class helper copies those words to the fresh vector. Only userdata
    offsets 4, 8 and 12 change. All 24 bytes of the factory's allocated record
    are preserved. Heap success and both empty trees are conditional supplied
    premises; the source's bytes, registry state and callback suffix are open.

    The vector's eight bytes cannot overlap the 72-byte userdata, 24-byte
    record or original callback frame [T-48,T+8). Cookie metadata describes
    the reached class cookie cells, rather than the deeper helper stack extent.
    """
    try:
        result = entry.apply(
            state=state,
            userdata=userdata,
            record_pointer=record_pointer,
            source_pointer=source_pointer,
            callback_entry=callback_entry,
            registers=registers,
            closure_target=closure_target,
            closure_upvalues=closure_upvalues,
            upvalue_has_metatable=upvalue_has_metatable,
            argument_has_metatable=argument_has_metatable,
            upvalue_marker_kind=upvalue_marker_kind,
            argument_marker_kind=argument_marker_kind,
        )
    except entry.FactoryCallbackEntryError as exc:
        raise FactoryCallbackEmptyClassError(str(exc)) from exc

    _word(vector_pointer, "vector pointer", nonzero=True)
    _word(cookie, "cookie")
    vector_end = vector_pointer + 8
    if vector_end > 0xFFFFFFFF:
        raise FactoryCallbackEmptyClassError("vector end pointer wraps uint32")
    if callback_entry < 56:
        raise FactoryCallbackEmptyClassError("class cookie address must cover T-56")
    for pointer, size, label in (
        (userdata, 72, "userdata"),
        (record_pointer, 24, "record"),
        (callback_entry - 48, 56, "callback frame"),
    ):
        if vector_pointer < pointer + size and pointer < vector_end:
            raise FactoryCallbackEmptyClassError(f"vector overlaps {label}")

    result.update(
        class_return=dict(
            registers=dict(
                eax=source_pointer,
                ebx=state,
                ecx=cookie,
                edx=0,
                esi=userdata,
                edi=source_pointer,
                ebp=callback_entry - 4,
                esp=callback_entry - 40,
            ),
            flags=0x44,
            flag_mask=0xCD5,
            endpoint=0x006EC1BD,
        ),
        vector=dict(
            records=[[0, source_pointer]],
            capacity=1,
            begin=vector_pointer,
            end=vector_end,
            capacity_pointer=vector_end,
        ),
        field_updates={4: vector_pointer, 8: vector_end, 12: vector_end},
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12)
        ],
        record_preserved_size=24,
        heap_request=dict(continuation=0x00789463, handle=0x12345678, flags=0, bytes=8),
        native_cookie=dict(
            frame=callback_entry - 52,
            protected_address=callback_entry - 56,
            stored_word=cookie ^ (callback_entry - 52),
        ),
    )
    return result
