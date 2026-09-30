"""Independent finite rejection/short-circuit laws, without native execution."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_factory_error_semantics as errors


def inputs():
    return dict(
        state=0x1000,
        argument_count=1,
        type_result=4,
        number_result=0,
        first_pointer=0x2000,
        name_bytes=b"abc\0",
        object_length=4,
    )


class Unused:
    """Irrelevant contracts should remain wholly uninterpreted."""

    def __eq__(self, other):
        raise AssertionError("unused response compared")

    def __int__(self):
        raise AssertionError("unused response converted")


@pytest.mark.parametrize("count", [0, 2, 3, 4, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF])
def test_count_short_circuit_ignores_every_later_contract(count):
    args = dict(
        state=0x1000,
        argument_count=count,
        **{
            key: Unused()
            for key in (
                "type_result",
                "number_result",
                "first_pointer",
                "name_bytes",
                "object_length",
            )
        }
    )
    result = errors.apply(**args)
    assert result["reason"] == "argument_count"
    assert [call["api"] for call in result["calls"]] == [
        "lua_gettop",
        "lua_pushstring",
        "lua_error",
    ]
    assert result["calls"][0]["result"] == count
    assert result["argument_prefix_is_compact"] is (count > 3)
    expected = (
        [("argument", i + 1) for i in range(count)]
        if count <= 3
        else [("arguments", count)]
    )
    assert result["initial_lua_stack"] == expected
    assert result["error_entry_lua_stack"] == expected + [
        ("message", "invalid_construct")
    ]
    assert result["measured_length"] is None and result["byte_reads"] == 0


@pytest.mark.parametrize(
    "type_result", [0, 1, 2, 3, 5, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
)
def test_type_short_circuit_ignores_number_pointer_bytes_and_length(type_result):
    args = inputs()
    args.update(
        type_result=type_result,
        number_result=Unused(),
        first_pointer=Unused(),
        name_bytes=Unused(),
        object_length=Unused(),
    )
    result = errors.apply(**args)
    assert result["reason"] == "type"
    assert [call["api"] for call in result["calls"]] == [
        "lua_gettop",
        "lua_type",
        "lua_pushstring",
        "lua_error",
    ]
    assert result["calls"][1]["result"] == type_result


@pytest.mark.parametrize("number_result", [1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF])
def test_numeric_short_circuit_ignores_pointer_bytes_and_length(number_result):
    args = inputs()
    args.update(
        number_result=number_result,
        first_pointer=Unused(),
        name_bytes=Unused(),
        object_length=Unused(),
    )
    result = errors.apply(**args)
    assert result["reason"] == "numeric"
    assert [call["api"] for call in result["calls"]] == [
        "lua_gettop",
        "lua_type",
        "lua_isnumber",
        "lua_pushstring",
        "lua_error",
    ]
    assert result["calls"][2]["result"] == number_result


def test_exhaustive_small_first_nul_families_and_length_rejections():
    for size in range(1, 5):
        for values in itertools.product((0, 65, 255), repeat=size):
            if 0 not in values:
                continue
            length = 0
            for value in values:
                if value == 0:
                    break
                length += 1
            for object_length in (0, length + 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
                if object_length == length:
                    continue
                args = inputs()
                args.update(name_bytes=bytes(values), object_length=object_length)
                result = errors.apply(**args)
                assert result["reason"] == "name_length"
                assert result["measured_length"] == length
                assert result["byte_reads"] == length + 1
                assert [call["api"] for call in result["calls"]] == [
                    "lua_gettop",
                    "lua_type",
                    "lua_isnumber",
                    "lua_tolstring",
                    "lua_objlen",
                    "lua_pushstring",
                    "lua_error",
                ]
                assert result["calls"][3]["arguments"] == [0x1000, 1, 0]
                assert result["calls"][4]["arguments"] == [0x1000, 1]
                assert result["calls"][4]["result"] == object_length
                args["name_bytes"] = bytes(values[: length + 1])
                assert errors.apply(**args) == result


@pytest.mark.parametrize("family", ["argument_count", "type", "numeric", "name_length"])
def test_exact_literal_and_import_entry_frames(family):
    args = inputs()
    if family == "argument_count":
        args["argument_count"] = 0
    elif family == "type":
        args["type_result"] = 0
    elif family == "numeric":
        args["number_result"] = 1
    result = errors.apply(**args)
    mismatch = family == "name_length"
    role, literal = (
        ("extra_nulls", 0x83CA88) if mismatch else ("invalid_construct", 0x83CA60)
    )
    assert result["error_literal"] == dict(
        role=role,
        pointer=literal,
        text=(
            "luabind does not support class names with extra nulls"
            if mismatch
            else "invalid construct, expected class name"
        ),
    )
    assert result["calls"][-2]["arguments"] == [0x1000, literal]
    assert result["calls"][-2]["result"] == 0
    assert result["calls"][-1]["arguments"] == [0x1000]
    assert result["calls"][-1]["result"] is None
    assert result["calls"][-1]["before"] == result["calls"][-1]["after"]
    assert result["calls"][-1]["after"] == result["error_entry_lua_stack"]
    assert result["endpoint"] == dict(
        api="lua_error",
        iat_rva=0x3D6498,
        call_rva=0x2EC2C8 if mismatch else 0x2EC28A,
        return_rva=0x2EC2CE if mismatch else 0x2EC290,
        arguments=[0x1000],
    )
    assert result["frame"] == dict(
        ebp_delta_from_entry_esp=-4,
        idle_esp_delta_from_ebp=-36,
        pushstring_esp_delta_from_idle=-12,
        pushstring_esp_delta_from_ebp=-48,
        pushstring_stack_words=[0x6EC2C7 if mismatch else 0x6EC289, 0x1000, literal],
        error_esp_delta_from_idle=-16,
        error_esp_delta_from_ebp=-52,
        error_stack_words=[0x6EC2CE if mismatch else 0x6EC290, 0x1000, 0x1000, literal],
    )
    assert result["lua_stack_delta"] == 1
    assert all(
        left["after"] == right["before"]
        for left, right in zip(result["calls"], result["calls"][1:])
    )


@pytest.mark.parametrize(
    "field",
    [
        "state",
        "argument_count",
        "type_result",
        "number_result",
        "first_pointer",
        "object_length",
    ],
)
@pytest.mark.parametrize("invalid", [False, True, -1, 0x100000000, 1.0, None, "1"])
def test_reached_word_types_are_strict(field, invalid):
    args = inputs()
    args[field] = invalid
    with pytest.raises(errors.FactoryErrorSemanticsError, match="uint32"):
        errors.apply(**args)


@pytest.mark.parametrize("field", ["state", "first_pointer"])
def test_relevant_pointer_zero_rejected(field):
    args = inputs()
    args[field] = 0
    with pytest.raises(errors.FactoryErrorSemanticsError, match="nonzero"):
        errors.apply(**args)


def test_cursor_page_and_address_boundaries():
    args = inputs()
    args.update(first_pointer=0x2FFE, name_bytes=b"x\0suffix", object_length=3)
    assert errors.apply(**args)["measured_length"] == 1  # Cursor crosses a page.
    args.update(first_pointer=0xFFFFFFFE, name_bytes=b"\0suffix", object_length=1)
    assert errors.apply(**args)["measured_length"] == 0
    args["name_bytes"] = b"x\0"
    with pytest.raises(errors.FactoryErrorSemanticsError, match="wraps"):
        errors.apply(**args)
    args.update(first_pointer=0xFFFFFFFF, name_bytes=b"\0")
    with pytest.raises(errors.FactoryErrorSemanticsError, match="wraps"):
        errors.apply(**args)


@pytest.mark.parametrize("name", [b"", b"abc", "x\0", bytearray(b"x\0"), [120, 0]])
def test_reached_bytes_shape_and_missing_terminator_rejected(name):
    args = inputs()
    args["name_bytes"] = name
    with pytest.raises(errors.FactoryErrorSemanticsError):
        errors.apply(**args)


@pytest.mark.parametrize("name", [b"\0", b"x\0", b"xy\0suffix"])
def test_accepted_normal_prefix_excluded(name):
    args = inputs()
    args.update(name_bytes=name, object_length=name.index(b"\0"))
    with pytest.raises(errors.FactoryErrorSemanticsError, match="accepted normal"):
        errors.apply(**args)


def test_subclasses_rejected_only_when_reached_and_outputs_detached():
    class Word(int):
        pass

    class Name(bytes):
        pass

    for field in (
        "state",
        "argument_count",
        "type_result",
        "number_result",
        "first_pointer",
        "object_length",
    ):
        args = inputs()
        args[field] = Word(args[field])
        with pytest.raises(errors.FactoryErrorSemanticsError):
            errors.apply(**args)
    args = inputs()
    args["name_bytes"] = Name(args["name_bytes"])
    with pytest.raises(errors.FactoryErrorSemanticsError):
        errors.apply(**args)
    args["argument_count"] = 0
    assert errors.apply(**args)["reason"] == "argument_count"
    args = inputs()
    before = copy.deepcopy(args)
    first, second = errors.apply(**args), errors.apply(**args)
    expected = copy.deepcopy(second)
    first["calls"][0]["arguments"].clear()
    first["calls"][0]["before"].clear()
    first["calls"][-2]["after"].clear()
    first["error_literal"]["text"] = "changed"
    first["endpoint"]["arguments"].clear()
    first["frame"]["error_stack_words"].clear()
    assert first["calls"][-1]["before"] == [("argument", 1), ("message", "extra_nulls")]
    assert first["initial_lua_stack"] == [("argument", 1)]
    assert args == before
    assert second == expected
    assert errors.apply(**args) == expected
