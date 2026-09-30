"""Independent Lua token interpreter for the reached factory assertion prefix."""

import copy

import pytest
from src.observatory import native_lua_class_factory_assertion_prefix_semantics as model


def arguments(**changes):
    result = dict(
        state=0x12001000,
        first_pointer=0x13000FFF,
        second_pointer=0x15000007,
        userdata=0x14000087,
        name_bytes=b"Class\0opaque\xff\0",
        context_pointer=0x17000107,
        context_guard=0xFFFFFFFE,
        references=[17, 19],
    )
    result.update(changes)
    return result


def interpret(kwargs, result):
    """Interpret only the selected requests, independently of model helpers."""
    state = kwargs["state"]
    stack, registry, tables = [("argument", 1)], {}, 0
    names, string_reads, references = [], 0, 0
    for call in result["calls"]:
        assert call["before"] == stack and call["arguments"][0] == state
        api, args = call["api"], call["arguments"]
        names.append(api)
        expected_result = 0
        if api == "lua_gettop":
            assert args == [state]
            expected_result = 1
        elif api == "lua_type":
            assert args == [state, 1]
            expected_result = 4
        elif api == "lua_isnumber":
            assert args == [state, 1]
        elif api == "lua_tolstring":
            assert args == [state, 1, 0]
            expected_result = (
                kwargs["first_pointer"]
                if string_reads == 0
                else kwargs["second_pointer"]
            )
            string_reads += 1
        elif api == "lua_objlen":
            assert args == [state, 1]
            expected_result = kwargs["name_bytes"].index(0)
        elif api == "lua_newuserdata":
            assert args == [state, 72]
            expected_result = kwargs["userdata"]
            stack.append(("userdata", expected_result))
        elif api == "lua_createtable":
            assert args == [state, 0, 0]
            tables += 1
            stack.append(("table", tables))
        elif api == "lua_pushvalue":
            assert args == [state, -1] and stack[-1] == ("table", tables)
            stack.append(stack[-1])
        elif api == "luaL_ref":
            assert args == [state, -10000]
            expected_result = kwargs["references"][references]
            references += 1
            registry[expected_result] = stack.pop()
        elif api == "lua_settop":
            assert args[1] == (-3 if len(stack) == 4 else -2)
            stack = stack[: len(stack) + args[1] + 1]
        elif api == "lua_pushstring":
            assert args == [state, 0x83BF18] and call["literal_role"] == "classes"
            stack.append(("literal", "classes"))
        elif api == "lua_gettable":
            assert args == [state, -10000] and stack[-1] == ("literal", "classes")
            stack[-1] = ("registry_value", "classes", kwargs["context_pointer"])
        elif api == "lua_touserdata":
            assert args == [state, -1]
            assert stack[-1] == ("registry_value", "classes", kwargs["context_pointer"])
            expected_result = kwargs["context_pointer"]
        else:
            pytest.fail("unreached Lua request: " + api)
        assert call["result"] == expected_result and call["after"] == stack
        assert call["phase"] == ("factory_prefix" if len(names) <= 7 else "initializer")
        assert call["literal_role"] == ("classes" if api == "lua_pushstring" else None)
    assert names == [
        "lua_gettop",
        "lua_type",
        "lua_isnumber",
        "lua_tolstring",
        "lua_objlen",
        "lua_tolstring",
        "lua_newuserdata",
    ] + ["lua_createtable", "lua_pushvalue", "luaL_ref"] * 2 + [
        "lua_settop",
        "lua_pushstring",
        "lua_gettable",
        "lua_touserdata",
        "lua_settop",
    ]
    assert tables == references == string_reads == 2
    assert (
        stack
        == result["boundary_lua_stack"]
        == [("argument", 1), ("userdata", kwargs["userdata"])]
    )
    assert result["registry_bindings"] == [
        dict(reference=ref, value=value) for ref, value in registry.items()
    ]


@pytest.mark.parametrize(
    "name",
    [b"\0opaque", b"A\0\xfftail\0", b"\x01\x02\x80\xff\0", b"Class" * 51 + b"\0"],
)
@pytest.mark.parametrize("refs", [[1, 2], [17, 19], [0x7FFFFFFE, 0x7FFFFFFF]])
def test_eighteen_reached_calls_independent_stack_registry_and_first_nul(name, refs):
    kwargs = arguments(name_bytes=name, references=refs)
    result = model.apply(**kwargs)
    assert len(result["calls"]) == 18
    interpret(kwargs, result)
    assert result["initial_lua_stack"] == [("argument", 1)]
    assert result["context_reads"] == [dict(offset=12, value=0xFFFFFFFE)]
    assert result["native_boundary"] == dict(
        target_rva=0x379CC2,
        call_rva=0x2EAE76,
        continuation=0x6EAE7B,
        arguments=[0x83C6B0, 0x83C680, 96],
    )
    assert result["frame"] == dict(
        boundary_esp_delta_from_initializer_ebp=-48,
        stack_words=[0x6EAE7B, 0x83C6B0, 0x83C680, 96],
    )


@pytest.mark.parametrize("second", [0x13000FFF, 0x15000007, 0xFFFFFFFF])
def test_exact_fourteen_fields_original_second_pointer_two_refs_and_unmodeled_record(
    second,
):
    kwargs = arguments(second_pointer=second)
    result = model.apply(**kwargs)
    assert result["final_fields"] == {
        0: 0x89D1D4,
        4: 0,
        8: 0,
        12: 0,
        16: second,
        20: 0,
        24: 0xFFFFFFFE,
        28: kwargs["state"],
        32: 17,
        36: kwargs["state"],
        40: 19,
        44: 1,
        56: 0,
        60: 0,
    }
    assert result["unmodeled_fields"] == [48, 52, 64, 68]
    assert set(result["final_fields"]) | set(result["unmodeled_fields"]) == set(
        range(0, 72, 4)
    )
    assert result["calls"][3]["result"] == kwargs["first_pointer"]
    assert result["calls"][5]["result"] == second


def test_reached_extent_boundaries_and_no_later_metatable_closure_or_context_fields():
    kwargs = arguments(
        state=0xFFFFFFFF,
        first_pointer=0xFFFFFFFE,
        name_bytes=b"\0tail",
        second_pointer=0xFFFFFFFF,
        userdata=0xFFFFFFC0,
        context_pointer=0xFFFFFFF0,
    )
    result = model.apply(**kwargs)
    interpret(kwargs, result)
    assert max(result["final_fields"]) == 60 and result["context_reads"] == [
        dict(offset=12, value=0xFFFFFFFE)
    ]
    assert not {
        "lua_rawgeti",
        "lua_setmetatable",
        "lua_settable",
        "lua_pushcclosure",
        "luaL_unref",
    }.intersection(call["api"] for call in result["calls"])
    assert len(result["registry_bindings"]) == 2


@pytest.mark.parametrize(
    "key,value",
    [
        ("state", 0),
        ("state", True),
        ("state", -1),
        ("state", 0x100000000),
        ("state", 1.0),
        ("first_pointer", 0),
        ("first_pointer", False),
        ("first_pointer", 0xFFFFFFFF),
        ("second_pointer", 0),
        ("second_pointer", True),
        ("second_pointer", -1),
        ("second_pointer", 0x100000000),
        ("userdata", 0),
        ("userdata", False),
        ("userdata", 0xFFFFFFC1),
        ("userdata", 0x100000000),
        ("context_pointer", 0),
        ("context_pointer", True),
        ("context_pointer", -1),
        ("context_pointer", 0xFFFFFFF1),
        ("context_guard", -2),
        ("context_guard", False),
        ("context_guard", 0),
        ("context_guard", 0xFFFFFFFF),
        ("context_guard", float(0xFFFFFFFE)),
        ("name_bytes", b"unterminated"),
        ("name_bytes", "Class\0"),
        ("name_bytes", bytearray(b"Class\0")),
        ("references", (17, 19)),
        ("references", [17]),
        ("references", [17, 19, 23]),
        ("references", [17, 17]),
        ("references", [0, 19]),
        ("references", [-1, 19]),
        ("references", [True, 19]),
        ("references", [17.0, 19]),
        ("references", [0x80000000, 19]),
        ("references", None),
    ],
)
def test_strict_reached_pointer_guard_name_and_reference_contracts(key, value):
    kwargs = arguments(**{key: value})
    with pytest.raises(model.FactoryAssertionPrefixError):
        model.apply(**kwargs)


def test_input_references_immutable_and_each_mutable_output_detached():
    kwargs = arguments()
    original = copy.deepcopy(kwargs)
    baseline = model.apply(**kwargs)
    changed = model.apply(**kwargs)
    changed["calls"][0]["arguments"][0] ^= 1
    changed["calls"][7]["after"].clear()
    changed["registry_bindings"][0]["reference"] = 2
    changed["final_fields"][32] = 0
    changed["context_reads"][0]["value"] = 0
    changed["native_boundary"]["arguments"][0] ^= 1
    changed["frame"]["stack_words"][0] ^= 1
    changed["unmodeled_fields"].clear()
    assert kwargs == original and model.apply(**kwargs) == baseline
    kwargs["references"][0] = 117
    assert baseline["registry_bindings"][0]["reference"] == 17
