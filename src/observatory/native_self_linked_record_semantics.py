"""Conditional fixed-offset laws for a small native helper's normal return.

A positive pointer to a writable 24-byte allocation is supplied as a premise.
The allocation call and its callees are not executed or simulated. Field
contents and helper spelling imply no source-level type or ownership policy.
"""

from __future__ import annotations


class SelfLinkedRecordError(RuntimeError):
    pass


def apply(*, pointer):
    """Describe helper-only stores after its allocation call returns pointer.

    The full supplied 24-byte extent must fit uint32 without wrapping. This
    normal domain excludes zero and wrapping EAX-plus-four/eight guard cases.
    Returned flags contain only the defined bits of the final TEST(pointer+8).
    """
    if type(pointer) is not int or not 1 <= pointer <= 0xFFFFFFFF:
        raise SelfLinkedRecordError("pointer must be nonzero uint32")
    if pointer + 23 > 0xFFFFFFFF:
        raise SelfLinkedRecordError("supplied 24-byte extent wraps uint32")
    final_ecx = pointer + 8
    flags = dict(
        cf=0,
        pf=int((final_ecx & 0xFF).bit_count() % 2 == 0),
        zf=int(final_ecx == 0),
        sf=(final_ecx >> 31) & 1,
        of=0,
    )
    return dict(
        requested_size=24,
        returned_pointer=pointer,
        ordered_writes=[
            dict(offset=0, size=4, value=pointer),
            dict(offset=4, size=4, value=pointer),
            dict(offset=8, size=4, value=pointer),
            dict(offset=12, size=2, value=0x0101),
        ],
        untouched_offsets=list(range(14, 24)),
        final_ecx=final_ecx,
        instruction_count=16,
        native_allocation_call=dict(
            target_rva=0x003574DB,
            return_rva=0x0007C607,
            arguments=[24],
        ),
        flags_mask=0x8C5,
        flags_value=(flags["pf"] << 2) | (flags["zf"] << 6) | (flags["sf"] << 7),
        flags=flags,
    )
