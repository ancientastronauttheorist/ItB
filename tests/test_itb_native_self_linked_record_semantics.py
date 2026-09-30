"""Independent finite byte-store and TEST-flag laws, without native execution."""

import copy
import struct

import pytest

from src.observatory import native_self_linked_record_semantics as record


def test_bounded_pointer_family_and_little_endian_store_footprint():
    pointers = list(range(1, 513)) + [
        0x12345678,
        0x7FFFFFF7,
        0x7FFFFFF8,
        0x80000000,
        0xFFFFFFE8,
    ]
    for pointer in pointers:
        result = record.apply(pointer=pointer)
        assert result["requested_size"] == 24
        assert result["returned_pointer"] == pointer
        assert result["ordered_writes"] == [
            dict(offset=offset, size=4, value=pointer) for offset in (0, 4, 8)
        ] + [dict(offset=12, size=2, value=0x0101)]
        original = bytes(range(24))
        arena = bytearray(original)
        written = set()
        for write in result["ordered_writes"]:
            offset, size = write["offset"], write["size"]
            arena[offset : offset + size] = write["value"].to_bytes(size, "little")
            written.update(range(offset, offset + size))
        assert arena[:14] == struct.pack("<IIIH", pointer, pointer, pointer, 0x0101)
        assert bytes(arena[14:]) == original[14:]
        assert written == set(range(14))
        assert result["untouched_offsets"] == list(range(14, 24))
        assert not written & set(result["untouched_offsets"])
        assert result["final_ecx"] == pointer + 8
        assert result["instruction_count"] == 16
        assert result["native_allocation_call"] == dict(
            target_rva=0x3574DB,
            return_rva=0x7C607,
            arguments=[24],
        )


def test_low_byte_parity_exhaustively_and_sign_transition():
    # Independently derive parity by summing individual low-byte bits.
    # Bases exercise a low-byte carry and both sides of the sign boundary.
    for base in (0, 0x7FFFFF00, 0x80000000, 0xFFFFFF00):
        for low in range(256):
            pointer = base + low
            if not 1 <= pointer <= 0xFFFFFFE8:
                continue
            tested = pointer + 8
            even = int(sum((tested >> bit) & 1 for bit in range(8)) % 2 == 0)
            sign = int(tested >= 0x80000000)
            result = record.apply(pointer=pointer)
            assert result["flags"] == dict(cf=0, pf=even, zf=0, sf=sign, of=0)
            assert "af" not in result["flags"]
            assert result["flags_mask"] == 0x8C5
            assert result["flags_value"] == even * 4 + sign * 128
            assert not result["flags_value"] & ~result["flags_mask"]


def test_full_24_byte_extent_boundary():
    # The highest byte of the supplied extent can equal UINT32_MAX.
    accepted = record.apply(pointer=0xFFFFFFE8)
    assert accepted["final_ecx"] == 0xFFFFFFF0
    for pointer in (0xFFFFFFE9, 0xFFFFFFF2, 0xFFFFFFFC, 0xFFFFFFFF):
        with pytest.raises(record.SelfLinkedRecordError, match="24-byte extent wraps"):
            record.apply(pointer=pointer)


@pytest.mark.parametrize("pointer", [False, True, 0, -1, 0x100000000, 1.0, "1", None])
def test_invalid_word_rejected(pointer):
    with pytest.raises(record.SelfLinkedRecordError, match="nonzero uint32"):
        record.apply(pointer=pointer)


def test_integer_subclass_rejected():
    class Pointer(int):
        pass

    with pytest.raises(record.SelfLinkedRecordError, match="nonzero uint32"):
        record.apply(pointer=Pointer(1))


def test_output_containers_detached_and_repeatable():
    first = record.apply(pointer=0x1000)
    second = record.apply(pointer=0x1000)
    expected = copy.deepcopy(second)
    first["ordered_writes"][0]["value"] = 0
    first["untouched_offsets"].clear()
    first["native_allocation_call"]["arguments"].clear()
    first["flags"]["pf"] = 99
    assert first["ordered_writes"][1]["value"] == 0x1000
    assert first["returned_pointer"] == 0x1000
    assert second == expected
    assert record.apply(pointer=0x1000) == expected
