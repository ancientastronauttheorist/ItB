"""Independent fixed-offset requests before an initializer's first helper.

The input words describe an opaque writable userdata base and a name pointer.
This model never reads name bytes, executes native code, or gives the written
fields source-level meanings. The helper entry is the endpoint, not executed.
"""

from __future__ import annotations


class InitializerPrefixError(RuntimeError):
    pass


def _word(value, label):
    if type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
        raise InitializerPrefixError(f"{label} must be nonzero uint32")
    return value


def apply(*, userdata, name_pointer):
    """Return the 37-instruction prefix's conditional writes and handoff.

    Writable storage through userdata+59 is a premise, not validated memory.
    The greatest actual written byte must not wrap uint32. The name pointer
    is copied as an opaque word, so it needs no readable extent or terminator.
    """
    _word(userdata, "userdata")
    _word(name_pointer, "name pointer")
    if userdata + 59 > 0xFFFFFFFF:
        raise InitializerPrefixError("userdata's highest written byte wraps uint32")
    fields = (
        (0, 0x0089D1D4),
        (4, 0),
        (8, 0),
        (12, 0),
        (16, name_pointer),
        (20, 0),
        (24, 0xFFFFFFFE),
        (28, 0),
        (32, 0xFFFFFFFE),
        (36, 0),
        (40, 0xFFFFFFFE),
        (44, 1),
        (52, 0),
        (56, 0),
    )
    return dict(
        ordered_offset_writes=[
            dict(offset=offset, size=4, value=value) for offset, value in fields
        ],
        final_fields=dict(fields),
        untouched_offsets=[48, 60, 64, 68],
        instruction_count=37,
        native_handoff=dict(
            target_rva=0x0007C600,
            return_rva=0x002EAD90,
            arguments=[],
            registers=dict(
                eax=name_pointer, ecx=userdata, esi=userdata + 52, edi=userdata
            ),
        ),
        frame=dict(
            ebp_delta_from_entry_esp=-4,
            pre_call_esp_delta_from_ebp=-32,
            handoff_esp_delta_from_ebp=-36,
            helper_return_address=0x006EAD90,
            saved_parent_fs_ebp_offset=-12,
            active_fs_ebp_delta=-12,
            cookie_ebp_offset=-32,
            second_argument_ebp_offset=12,
            second_argument_read=name_pointer,
            second_argument_final=userdata + 52,
            local_words=[
                dict(ebp_offset=-16, value=userdata),
                dict(ebp_offset=-4, value=3),
            ],
        ),
    )
