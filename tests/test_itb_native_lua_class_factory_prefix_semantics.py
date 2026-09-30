"""Finite byte/name request laws, independent of native instruction execution."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_factory_prefix_semantics as prefix


def inputs():
    return dict(
        state=0x12345678, first_pointer=0x2000, second_pointer=0x3000, userdata=0x4000
    )


def test_exhaustive_small_first_nul_families_and_opaque_suffixes():
    # Every byte string of length <=4 from this alphabet that includes a zero.
    # The oracle counts the nonzero prefix, without using the model's find.
    for size in range(1, 5):
        for values in itertools.product((0, 1, 65, 255), repeat=size):
            if 0 not in values:
                continue
            count = 0
            for value in values:
                if value == 0:
                    break
                count += 1
            result = prefix.apply(bytes(values), **inputs())
            assert result["measured_length"] == count
            assert result["byte_reads"] == count + 1
            assert result["first_terminal_cursor"] == 0x2001 + count
            assert result["prefix_instruction_count"] == 71 + 4 * count
            assert result["calls"][4]["result"] == count
            assert result == prefix.apply(bytes(values[: count + 1]), **inputs())


@pytest.mark.parametrize("length", [0, 1, 2, 15, 16, 31, 255, 256])
def test_seven_normal_contracts_and_initializer_handoff(length):
    args = inputs()
    result = prefix.apply(b"x" * length + b"\0", **args)
    assert [
        (call["api"], call["arguments"], call["result"]) for call in result["calls"]
    ] == [
        ("lua_gettop", [args["state"]], 1),
        ("lua_type", [args["state"], 1], 4),
        ("lua_isnumber", [args["state"], 1], 0),
        ("lua_tolstring", [args["state"], 1, 0], args["first_pointer"]),
        ("lua_objlen", [args["state"], 1], length),
        ("lua_tolstring", [args["state"], 1, 0], args["second_pointer"]),
        ("lua_newuserdata", [args["state"], 72], args["userdata"]),
    ]
    assert result["initializer"] == dict(
        target_rva=0x2EACF0,
        return_rva=0x2EC307,
        arguments=[args["state"], args["second_pointer"]],
        registers=dict(
            eax=args["userdata"],
            ecx=args["userdata"],
            esi=args["state"],
            edi=args["second_pointer"],
        ),
    )
    assert [call["entry_esp_delta_from_idle"] for call in result["calls"]] == [
        -8,
        -12,
        -12,
        -16,
        -12,
        -16,
        -12,
    ]
    assert result["frame"] == dict(
        ebp_delta_from_entry_esp=-4,
        idle_esp_delta_from_ebp=-36,
        initializer_esp_delta_from_ebp=-48,
        initializer_stack_words=[0x6EC307, args["state"], args["second_pointer"]],
        local_stores=[
            dict(ebp_offset=offset, value=value)
            for offset, value in (
                (-16, args["userdata"]),
                (-20, args["userdata"]),
                (-4, 0),
            )
        ],
    )
    initial = [("argument", 1)]
    final = initial + [("userdata", args["userdata"])]
    assert result["initial_lua_stack"] == initial
    assert result["final_lua_stack"] == final
    assert result["lua_stack_delta"] == 1
    assert all(call["before"] == initial for call in result["calls"])
    assert [call["after"] for call in result["calls"]] == [initial] * 6 + [final]


@pytest.mark.parametrize("second_pointer", [1, 0x2000, 0xFFFFFFFF])
@pytest.mark.parametrize("userdata", [1, 0xFFFFFFFF])
def test_handoff_pointers_are_independent_and_not_dereferenced(
    second_pointer, userdata
):
    args = inputs()
    args.update(second_pointer=second_pointer, userdata=userdata)
    result = prefix.apply(b"\0uninspected", **args)
    assert result["measured_length"] == 0
    assert result["initializer"]["arguments"] == [args["state"], second_pointer]
    assert result["initializer"]["registers"]["ecx"] == userdata


def test_terminating_cursor_boundary_and_unread_suffix():
    args = inputs()
    args["first_pointer"] = 0xFFFFFFFE
    assert prefix.apply(b"\0suffix", **args)["first_terminal_cursor"] == 0xFFFFFFFF
    with pytest.raises(prefix.FactoryPrefixError, match="wraps"):
        prefix.apply(b"x\0", **args)
    args["first_pointer"] = 0xFFFFFFFF
    with pytest.raises(prefix.FactoryPrefixError, match="wraps"):
        prefix.apply(b"\0", **args)


@pytest.mark.parametrize(
    "field", ["state", "first_pointer", "second_pointer", "userdata"]
)
@pytest.mark.parametrize("value", [False, True, 0, -1, 0x100000000, 1.0, "1", None])
def test_invalid_words_rejected(field, value):
    args = inputs()
    args[field] = value
    with pytest.raises(prefix.FactoryPrefixError, match="nonzero uint32"):
        prefix.apply(b"x\0", **args)


@pytest.mark.parametrize("name", [None, "x\0", bytearray(b"x\0"), [120, 0]])
def test_invalid_byte_shapes_rejected(name):
    with pytest.raises(prefix.FactoryPrefixError, match="must be bytes"):
        prefix.apply(name, **inputs())


@pytest.mark.parametrize("name", [b"", b"abc", b"\xff"])
def test_missing_terminator_rejected(name):
    with pytest.raises(prefix.FactoryPrefixError, match="NUL terminator"):
        prefix.apply(name, **inputs())


def test_integer_and_bytes_subclasses_rejected():
    class Word(int):
        pass

    class Name(bytes):
        pass

    args = inputs()
    args["state"] = Word(1)
    with pytest.raises(prefix.FactoryPrefixError):
        prefix.apply(b"\0", **args)
    with pytest.raises(prefix.FactoryPrefixError):
        prefix.apply(Name(b"\0"), **inputs())


def test_outputs_detached_from_each_other_and_repeated_calls():
    args = inputs()
    first = prefix.apply(b"hello\0", **args)
    second = prefix.apply(b"hello\0", **args)
    expected = copy.deepcopy(second)
    first["calls"][0]["arguments"][0] = 0
    first["calls"][0]["before"].clear()
    first["calls"][0]["after"].clear()
    first["initializer"]["arguments"].clear()
    first["frame"]["local_stores"][0]["value"] = 0
    assert second == expected
    assert first["calls"][1]["before"] == [("argument", 1)]
    assert first["initial_lua_stack"] == [("argument", 1)]
    assert first["final_lua_stack"] == [("argument", 1), ("userdata", args["userdata"])]
    assert prefix.apply(b"hello\0", **args) == expected
