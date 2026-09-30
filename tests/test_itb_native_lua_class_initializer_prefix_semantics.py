"""Independent finite fixed-offset laws, with no native instruction oracle."""

import copy
import itertools
import struct

import pytest

from src.observatory import native_lua_class_initializer_prefix_semantics as prefix


def expected_fields(name_pointer):
    # Specify the field partition independently from the ordered request list.
    zeros = {offset: 0 for offset in (4, 8, 12, 20, 28, 36, 52, 56)}
    negative_twos = {offset: 0xFFFFFFFE for offset in (24, 32, 40)}
    return {0: 0x0089D1D4, 16: name_pointer, 44: 1, **zeros, **negative_twos}


def test_bounded_pointer_cross_product_and_complete_field_partition():
    userdatas = list(range(1, 17)) + [0x1000, 0x12345678, 0xFFFFFFC4]
    names = list(range(1, 17)) + [0x1000, 0xABCDEF01, 0xFFFFFFFE, 0xFFFFFFFF]
    for userdata, name_pointer in itertools.product(userdatas, names):
        result = prefix.apply(userdata=userdata, name_pointer=name_pointer)
        expected = expected_fields(name_pointer)
        assert result["final_fields"] == expected
        assert result["ordered_offset_writes"] == [
            dict(offset=offset, size=4, value=expected[offset])
            for offset in range(0, 60, 4)
            if offset != 48
        ]
        assert result["untouched_offsets"] == [48, 60, 64, 68]
        assert not set(result["untouched_offsets"]) & set(result["final_fields"])
        assert len(result["final_fields"]) == 14
        assert result["instruction_count"] == 37
        assert result["native_handoff"] == dict(
            target_rva=0x7C600,
            return_rva=0x2EAD90,
            arguments=[],
            registers=dict(
                eax=name_pointer, ecx=userdata, esi=userdata + 52, edi=userdata
            ),
        )


def test_requests_leave_every_unspecified_byte_untouched():
    # Apply requests to distinctive initial bytes. The model does not receive
    # this arena; preservation is a consequence of its exact write footprint.
    original = bytes(range(72))
    arena = bytearray(original)
    result = prefix.apply(userdata=0x1000, name_pointer=0x12345678)
    changed_domain = set()
    for write in result["ordered_offset_writes"]:
        offset = write["offset"]
        arena[offset : offset + 4] = struct.pack("<I", write["value"])
        changed_domain.update(range(offset, offset + 4))
    assert changed_domain == set(range(48)) | set(range(52, 60))
    assert bytes(arena[48:52]) == original[48:52]
    assert bytes(arena[60:72]) == original[60:72]
    for index in set(range(72)) - changed_domain:
        assert arena[index] == original[index]


def test_nested_frame_and_argument_slot_overwrite():
    result = prefix.apply(userdata=0x2000, name_pointer=0xFFFFFFFE)
    assert result["frame"] == dict(
        ebp_delta_from_entry_esp=-4,
        pre_call_esp_delta_from_ebp=-32,
        handoff_esp_delta_from_ebp=-36,
        helper_return_address=0x006EAD90,
        saved_parent_fs_ebp_offset=-12,
        active_fs_ebp_delta=-12,
        cookie_ebp_offset=-32,
        second_argument_ebp_offset=12,
        second_argument_read=0xFFFFFFFE,
        second_argument_final=0x2034,
        local_words=[dict(ebp_offset=-16, value=0x2000), dict(ebp_offset=-4, value=3)],
    )
    assert result["native_handoff"]["registers"]["eax"] == 0xFFFFFFFE
    assert result["final_fields"][16] == 0xFFFFFFFE


def test_last_written_byte_boundary_and_pointer_without_extent():
    # U+59 may equal UINT32_MAX; U+60 is untouched and need not be representable.
    result = prefix.apply(userdata=0xFFFFFFC4, name_pointer=0xFFFFFFFF)
    assert result["native_handoff"]["registers"]["esi"] == 0xFFFFFFF8
    assert result["final_fields"][16] == 0xFFFFFFFF
    for userdata in (0xFFFFFFC5, 0xFFFFFFFE, 0xFFFFFFFF):
        with pytest.raises(prefix.InitializerPrefixError, match="wraps"):
            prefix.apply(userdata=userdata, name_pointer=1)


@pytest.mark.parametrize("field", ["userdata", "name_pointer"])
@pytest.mark.parametrize("value", [False, True, 0, -1, 0x100000000, 1.0, "1", None])
def test_invalid_words_rejected(field, value):
    args = dict(userdata=0x1000, name_pointer=0x2000)
    args[field] = value
    with pytest.raises(prefix.InitializerPrefixError, match="nonzero uint32"):
        prefix.apply(**args)


def test_integer_subclasses_rejected():
    class Word(int):
        pass

    for field in ("userdata", "name_pointer"):
        args = dict(userdata=0x1000, name_pointer=0x2000)
        args[field] = Word(args[field])
        with pytest.raises(prefix.InitializerPrefixError, match="nonzero uint32"):
            prefix.apply(**args)


def test_outputs_detached_from_each_other_and_repeated_calls():
    args = dict(userdata=0x1000, name_pointer=0x2000)
    first = prefix.apply(**args)
    second = prefix.apply(**args)
    expected = copy.deepcopy(second)
    first["ordered_offset_writes"][0]["value"] = 0
    first["untouched_offsets"].clear()
    first["native_handoff"]["registers"]["eax"] = 0
    first["frame"]["local_words"][0]["value"] = 0
    assert first["final_fields"][0] == 0x0089D1D4
    assert first["frame"]["second_argument_read"] == 0x2000
    assert second == expected
    assert prefix.apply(**args) == expected
