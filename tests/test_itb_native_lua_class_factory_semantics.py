"""Independent complete normal request/stack laws; no native execution oracle."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_factory_semantics as factory


def inputs():
    return dict(
        state=0x1000,
        first_pointer=0x2000,
        second_pointer=0x3000,
        userdata=0x4000,
        name_bytes=b"name\0",
        context_pointer=0x5000,
        context_word=0x76543210,
        context_guard=0,
        metatable_reference=99,
        graph_pointer=0x6000,
        id_map_pointer=0x7000,
        references=[11, 22, 33],
    )


def test_complete_api_order_arguments_results_and_phase_partition():
    args = inputs()
    result = factory.apply(**args)
    L = args["state"]
    expected = [
        ("lua_gettop", [L], 1),
        ("lua_type", [L, 1], 4),
        ("lua_isnumber", [L, 1], 0),
        ("lua_tolstring", [L, 1, 0], 0x2000),
        ("lua_objlen", [L, 1], 4),
        ("lua_tolstring", [L, 1, 0], 0x3000),
        ("lua_newuserdata", [L, 72], 0x4000),
        ("lua_createtable", [L, 0, 0], 0),
        ("lua_pushvalue", [L, -1], 0),
        ("luaL_ref", [L, -10000], 11),
        ("lua_createtable", [L, 0, 0], 0),
        ("lua_pushvalue", [L, -1], 0),
        ("luaL_ref", [L, -10000], 22),
        ("lua_settop", [L, -3], 0),
        ("lua_pushstring", [L, 0x83BF18], 0),
        ("lua_gettable", [L, -10000], 0),
        ("lua_touserdata", [L, -1], 0x5000),
        ("lua_settop", [L, -2], 0),
        ("lua_rawgeti", [L, -10000, 99], 0),
        ("lua_setmetatable", [L, -2], 1),
        ("lua_pushvalue", [L, -1], 0),
        ("luaL_ref", [L, -10000], 33),
        ("lua_pushstring", [L, 0x83BF6C], 0),
        ("lua_gettable", [L, -10000], 0),
        ("lua_touserdata", [L, -1], 0x6000),
        ("lua_settop", [L, -2], 0),
        ("lua_pushstring", [L, 0x82A86C], 0),
        ("lua_gettable", [L, -10000], 0),
        ("lua_touserdata", [L, -1], 0x7000),
        ("lua_settop", [L, -2], 0),
        ("lua_pushstring", [L, 0x3000], 0),
        ("lua_pushvalue", [L, -2], 0),
        ("lua_settable", [L, -10002], 0),
        ("lua_pushcclosure", [L, 0x6EC110, 1], 0),
    ]
    assert [
        (c["api"], c["arguments"], c["result"]) for c in result["calls"]
    ] == expected
    assert [c["phase"] for c in result["calls"]] == (
        ["factory_prefix"] * 7 + ["initializer"] * 23 + ["factory_tail"] * 4
    )
    assert result["literal_requests"] == [
        dict(role="classes", pointer=0x83BF18),
        dict(role="cast_graph", pointer=0x83BF6C),
        dict(role="class_id_map", pointer=0x82A86C),
    ]
    assert [
        (i, c["literal_role"])
        for i, c in enumerate(result["calls"])
        if c["literal_role"] is not None
    ] == [
        (14, "classes"),
        (22, "cast_graph"),
        (26, "class_id_map"),
        (30, "opaque_name"),
    ]


def test_every_stack_snapshot_follows_an_independent_api_stack_model():
    args = inputs()
    result = factory.apply(**args)
    stack = [("argument", 1)]
    table_count, registry_lookup_count = 0, 0
    registry_values = [
        ("registry_value", "classes", args["context_pointer"]),
        ("registry_value", "cast_graph", args["graph_pointer"]),
        ("registry_value", "class_id_map", args["id_map_pointer"]),
    ]
    for call in result["calls"]:
        assert call["before"] == stack
        api, arguments = call["api"], call["arguments"]
        if api == "lua_newuserdata":
            stack.append(("userdata", args["userdata"]))
        elif api == "lua_createtable":
            table_count += 1
            stack.append(("table", table_count))
        elif api == "lua_pushvalue":
            stack.append(stack[arguments[1]])
        elif api == "luaL_ref":
            stack.pop()
        elif api == "lua_settop":
            # Lua's negative settop sets top = old_top + index + 1.
            stack = stack[: len(stack) + arguments[1] + 1]
        elif api == "lua_pushstring":
            stack.append(
                ("name_pointer", args["second_pointer"])
                if call["phase"] == "factory_tail"
                else ("literal", call["literal_role"])
            )
        elif api == "lua_gettable":
            stack.pop()
            stack.append(registry_values[registry_lookup_count])
            registry_lookup_count += 1
        elif api == "lua_rawgeti":
            stack.append(("metatable", args["metatable_reference"]))
        elif api == "lua_setmetatable":
            assert stack[arguments[1]] == ("userdata", args["userdata"])
            stack.pop()
        elif api == "lua_settable":
            assert arguments[1] == -10002
            value, key = stack.pop(), stack.pop()
            assert value == ("userdata", args["userdata"])
            assert key == ("name_pointer", args["second_pointer"])
        elif api == "lua_pushcclosure":
            upvalue = stack.pop()
            stack.append(("closure", arguments[1], upvalue))
        assert call["after"] == stack
    closure = ("closure", 0x6EC110, ("userdata", args["userdata"]))
    assert result["final_lua_stack"] == [("argument", 1), closure] == stack
    assert result["selected_results"] == [closure]
    assert result["result_count"] == result["lua_stack_delta"] == 1


def test_reference_binding_requests_and_native_fields_remain_offset_only():
    args = inputs()
    result = factory.apply(**args)
    assert result["registry_bindings"] == [
        dict(reference=11, value=("table", 1)),
        dict(reference=22, value=("table", 2)),
        dict(reference=33, value=("userdata", 0x4000)),
    ]
    assert result["metatable_setting_request"] == dict(
        index=-2, userdata=0x4000, reference=99
    )
    assert result["global_assignment_request"] == dict(
        index=-10002, key_pointer=0x3000, userdata=0x4000
    )
    assert result["closure"] == dict(
        target_rva=0x2EC110, target_pointer=0x6EC110, upvalues=[("userdata", 0x4000)]
    )
    assert result["final_fields"] == {
        0: 0x89D1D4,
        4: 0,
        8: 0,
        12: 0,
        16: 0x3000,
        20: 0x1000,
        24: 33,
        28: 0x1000,
        32: 11,
        36: 0x1000,
        40: 22,
        44: 1,
        48: 0x76543210,
        56: 0,
        60: 0,
        64: 0x6000,
        68: 0x7000,
    }
    assert result["unmodeled_fields"] == [52] and 52 not in result["final_fields"]
    assert result["context_reads"] == [
        dict(offset=12, value=0),
        dict(offset=16, value=99),
        dict(offset=8, value=0x76543210),
    ]


def test_exhaustive_small_names_and_independent_second_pointer():
    for size in range(1, 4):
        for values in itertools.product((0, 65, 255), repeat=size):
            if 0 not in values:
                continue
            n = 0
            while values[n] != 0:
                n += 1
            for second_pointer in (1, 0x2000, 0xFFFFFFFF):
                args = inputs()
                args.update(name_bytes=bytes(values), second_pointer=second_pointer)
                result = factory.apply(**args)
                assert result["measured_length"] == n
                assert result["calls"][4]["result"] == n
                assert result["final_fields"][16] == second_pointer
                assert (
                    result["global_assignment_request"]["key_pointer"] == second_pointer
                )


def test_bounded_reference_and_context_contract_combinations():
    for refs in itertools.permutations((1, 2, 0x7FFFFFFF)):
        for guard, word, metaref in itertools.product(
            (0, 1, 0xFFFFFFFF), (0, 0xFFFFFFFF), (0, 0x7FFFFFFF)
        ):
            args = inputs()
            args.update(
                references=list(refs),
                context_guard=guard,
                context_word=word,
                metatable_reference=metaref,
            )
            result = factory.apply(**args)
            assert [
                binding["reference"] for binding in result["registry_bindings"]
            ] == list(refs)
            assert [result["final_fields"][offset] for offset in (32, 40, 24)] == list(
                refs
            )
            assert result["final_fields"][48] == word
            assert result["calls"][18]["arguments"][-1] == metaref


@pytest.mark.parametrize(
    "field",
    [
        "state",
        "first_pointer",
        "second_pointer",
        "userdata",
        "context_pointer",
        "graph_pointer",
        "id_map_pointer",
    ],
)
@pytest.mark.parametrize("value", [False, True, 0, -1, 0x100000000, 1.0, None, "1"])
def test_invalid_pointer_contracts(field, value):
    args = inputs()
    args[field] = value
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)


@pytest.mark.parametrize("field", ["context_word", "context_guard"])
@pytest.mark.parametrize("value", [False, True, -1, 0x100000000, 1.0, None])
def test_invalid_context_words(field, value):
    args = inputs()
    args[field] = value
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)


@pytest.mark.parametrize("value", [False, True, -1, 0x80000000, 1.0, None])
def test_invalid_metatable_reference(value):
    args = inputs()
    args["metatable_reference"] = value
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)


@pytest.mark.parametrize(
    "references",
    [
        None,
        (),
        (1, 2, 3),
        [],
        [1, 2],
        [1, 2, 3, 4],
        [1, 2, 0],
        [1, -1, 3],
        [1, True, 3],
        [1, 0x80000000, 3],
        [1, 2.0, 3],
        [1, 1, 2],
        [1, 2, 1],
        [1, 2, 2],
    ],
)
def test_invalid_reference_lists(references):
    args = inputs()
    args["references"] = references
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)


def test_excluded_assertion_contract():
    args = inputs()
    args["context_guard"] = 0xFFFFFFFE
    with pytest.raises(factory.FactoryError, match="assertion"):
        factory.apply(**args)


def test_pointer_extent_boundaries():
    args = inputs()
    args.update(
        userdata=0xFFFFFFB8,
        context_pointer=0xFFFFFFEC,
        graph_pointer=0xFFFFFFFF,
        id_map_pointer=0xFFFFFFFF,
        first_pointer=0xFFFFFFFE,
        name_bytes=b"\0opaque",
    )
    assert factory.apply(**args)["measured_length"] == 0
    for field in ("userdata", "context_pointer", "first_pointer"):
        invalid = dict(args)
        invalid[field] += 1
        with pytest.raises(factory.FactoryError, match="wraps"):
            factory.apply(**invalid)


@pytest.mark.parametrize("name", [b"", b"abc", "a\0", bytearray(b"a\0"), None])
def test_invalid_name_contract(name):
    args = inputs()
    args["name_bytes"] = name
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)


def test_subclasses_and_output_detachment():
    class Word(int):
        pass

    class Refs(list):
        pass

    for field in ("state", "context_word", "metatable_reference"):
        args = inputs()
        args[field] = Word(args[field])
        with pytest.raises(factory.FactoryError):
            factory.apply(**args)
    args = inputs()
    args["references"] = Refs(args["references"])
    with pytest.raises(factory.FactoryError):
        factory.apply(**args)
    args = inputs()
    before = copy.deepcopy(args)
    first, second = factory.apply(**args), factory.apply(**args)
    expected = copy.deepcopy(second)
    first["calls"][0]["before"].clear()
    first["calls"][0]["arguments"].clear()
    first["calls"][7]["after"].clear()
    first["registry_bindings"][0]["reference"] = 0
    first["closure"]["upvalues"].clear()
    first["final_fields"][16] = 0
    first["context_reads"][0]["value"] = 0xFFFFFFFE
    assert first["calls"][8]["before"] == [
        ("argument", 1),
        ("userdata", 0x4000),
        ("table", 1),
    ]
    assert args == before
    assert second == expected
    assert factory.apply(**args) == expected
