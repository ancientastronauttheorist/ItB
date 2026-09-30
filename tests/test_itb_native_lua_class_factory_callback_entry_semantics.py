"""Independent Lua identity and caller-frame checks for the callback entry map."""

import copy
import itertools

import pytest
from src.observatory import native_lua_class_factory_callback_entry_semantics as model


def arguments(**changes):
    entry = changes.get("callback_entry", 0x30000FFF)
    userdata = changes.get("userdata", 0x14000087)
    result = dict(
        state=0x12001000,
        userdata=userdata,
        record_pointer=0x16000FFF,
        source_pointer=0x1A000100,
        callback_entry=entry,
        registers=dict(
            eax=0xFFFFFFFF,
            ebx=0x80000000,
            ecx=0x12345678,
            edx=0,
            esi=0xAAAAAAAA,
            edi=0x55555555,
            ebp=0x87654321,
            esp=entry,
        ),
        closure_target=0x6EC110,
        closure_upvalues=[userdata],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
    )
    result.update(changes)
    return result


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def interpret(kwargs, result):
    """Independent stack interpreter, with each marker bound to its object."""
    state, userdata, source = (
        kwargs["state"],
        kwargs["userdata"],
        kwargs["source_pointer"],
    )
    stack = [("argument", source)]
    names, marker = [], -1
    for number, call in enumerate(result["calls"]):
        assert set(call) == {"api", "arguments", "result", "before", "after", "group"}
        assert call["before"] == stack
        api, args = call["api"], call["arguments"]
        names.append(api)
        assert args[0] == signed(state)
        if api == "lua_touserdata":
            assert call["group"] == "direct"
            assert args == [signed(state), -10003 if number == 0 else 1]
            assert call["result"] == (userdata if number == 0 else source)
        else:
            if api == "lua_getmetatable":
                marker += 1
            assert call["group"] == ("marker0", "marker1")[marker]
            identity = userdata if marker == 0 else source
            kind = (
                kwargs["upvalue_marker_kind"]
                if marker == 0
                else kwargs["argument_marker_kind"]
            )
            if api == "lua_getmetatable":
                assert args == [signed(state), -10003 if marker == 0 else 1]
                stack.append(("metatable", identity))
                assert call["result"] == 1
            elif api == "lua_pushstring":
                assert args == [signed(state), 0x83C738]
                stack.append(("marker_key", identity))
                assert call["result"] == 0
            elif api == "lua_gettable":
                assert args == [signed(state), -2]
                assert stack[-2:] == [("metatable", identity), ("marker_key", identity)]
                stack[-1] = ("marker_value", identity, kind)
                assert call["result"] == 0
            elif api == "lua_toboolean":
                assert args == [signed(state), -1]
                assert stack[-1] == ("marker_value", identity, kind)
                assert call["result"] == 1
            else:
                assert api == "lua_settop" and args == [signed(state), -3]
                assert stack[-2:] == [
                    ("metatable", identity),
                    ("marker_value", identity, kind),
                ]
                del stack[-2:]
                assert call["result"] == 0
        assert call["after"] == stack
    assert names == ["lua_touserdata"] + [
        "lua_getmetatable",
        "lua_pushstring",
        "lua_gettable",
        "lua_toboolean",
        "lua_settop",
    ] * 2 + ["lua_touserdata"]
    assert marker == 1 and stack == result["boundary_lua_stack"] == result[
        "initial_lua_stack"
    ] == [("argument", source)]


@pytest.mark.parametrize(
    "upvalue,argument",
    list(itertools.product(("zero", "empty_string", "table"), repeat=2)),
)
@pytest.mark.parametrize("alias", [False, True])
def test_all_truthy_marker_pairs_independent_twelve_call_interpreter_and_alias_identity(
    upvalue, argument, alias
):
    kwargs = arguments(upvalue_marker_kind=upvalue, argument_marker_kind=argument)
    if alias:
        kwargs["source_pointer"] = kwargs["userdata"]
    result = model.apply(**kwargs)
    assert len(result["calls"]) == 12
    interpret(kwargs, result)
    assert result["calls"][5]["after"] == [("argument", kwargs["source_pointer"])]
    assert result["calls"][10]["after"] == [("argument", kwargs["source_pointer"])]


@pytest.mark.parametrize(
    "entry", [48, 49, 0x30000FFF, 0x30001000, 0x3000100F, 0xFFFFFFF8]
)
def test_class_caller_physical_record_and_all_eight_gprs(entry):
    kwargs = arguments(callback_entry=entry)
    result = model.apply(**kwargs)
    assert result["class_entry_rva"] == 0x2EB140
    assert result["class_caller"] == dict(
        return_address=0x6EC1BD,
        argaddress=entry - 20,
        argument_record=[0, kwargs["source_pointer"]],
        registers=dict(
            eax=entry - 20,
            ebx=kwargs["state"],
            ecx=kwargs["userdata"],
            edx=0xB1000002,
            esi=kwargs["userdata"],
            edi=kwargs["source_pointer"],
            ebp=entry - 4,
            esp=entry - 48,
        ),
    )
    assert (
        result["class_caller"]["argaddress"]
        == result["class_caller"]["registers"]["esp"] + 28
    )
    assert not {
        "flags",
        "eflags",
        "pages",
        "record_bytes",
        "userdata_bytes",
    }.intersection(result)


def test_unsigned_high_word_pointers_signed_lua_arguments_and_reached_extents():
    kwargs = arguments(
        state=0xFFFFFFFF,
        userdata=0xFFFFFFB8,
        record_pointer=0xFFFFFFE8,
        source_pointer=0xFFFFFFFF,
        callback_entry=0xFFFFFFF8,
    )
    result = model.apply(**kwargs)
    interpret(kwargs, result)
    assert result["userdata_extent"] == dict(pointer=0xFFFFFFB8, size=72)
    assert result["record_extent"] == dict(pointer=0xFFFFFFE8, size=24)
    assert all(call["arguments"][0] == -1 for call in result["calls"])
    assert result["closure_target"] == 0x6EC110 and result["closure_upvalues"] == [
        0xFFFFFFB8
    ]
    assert result["class_caller"]["registers"]["edi"] == 0xFFFFFFFF


@pytest.mark.parametrize("register", ["eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"])
def test_original_entry_gpr_high_words_are_accepted_and_caller_map_overwrites_them(
    register,
):
    kwargs = arguments()
    baseline = model.apply(**kwargs)
    kwargs["registers"][register] = 0xFFFFFFFF
    assert model.apply(**kwargs) == baseline


def test_record_and_source_pointer_contents_are_opaque_and_no_record_allocation_claim():
    first = arguments(record_pointer=1, source_pointer=1)
    second = arguments(record_pointer=0xFFFFFFE8, source_pointer=1)
    a, b = model.apply(**first), model.apply(**second)
    assert a["calls"] == b["calls"] and a["class_caller"] == b["class_caller"]
    assert a["record_extent"] != b["record_extent"]
    assert not any(
        call["api"]
        in ("HeapAlloc", "HeapFree", "lua_newuserdata", "lua_rawgeti", "lua_settable")
        for call in a["calls"]
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("state", 0),
        ("state", True),
        ("state", -1),
        ("state", 0x100000000),
        ("state", 1.0),
        ("userdata", 0),
        ("userdata", True),
        ("userdata", -1),
        ("userdata", 0xFFFFFFB9),
        ("record_pointer", 0),
        ("record_pointer", False),
        ("record_pointer", -1),
        ("record_pointer", 0xFFFFFFE9),
        ("source_pointer", 0),
        ("source_pointer", True),
        ("source_pointer", -1),
        ("source_pointer", 0x100000000),
        ("callback_entry", 0),
        ("callback_entry", False),
        ("callback_entry", 47),
        ("callback_entry", 0xFFFFFFF9),
        ("callback_entry", 48.0),
        ("closure_target", 0),
        ("closure_target", True),
        ("closure_target", 0x6EC111),
        ("upvalue_has_metatable", False),
        ("upvalue_has_metatable", 1),
        ("upvalue_has_metatable", None),
        ("argument_has_metatable", False),
        ("argument_has_metatable", 1),
        ("argument_has_metatable", None),
        ("upvalue_marker_kind", "nil"),
        ("upvalue_marker_kind", "false"),
        ("upvalue_marker_kind", 0),
        ("argument_marker_kind", "nil"),
        ("argument_marker_kind", "false"),
        ("argument_marker_kind", "other"),
    ],
)
def test_strict_reached_words_extents_closure_truth_and_frame_domains(key, value):
    with pytest.raises(model.FactoryCallbackEntryError):
        model.apply(**arguments(**{key: value}))


@pytest.mark.parametrize(
    "value",
    [[], [0x14000087, 0x14000087], (0x14000087,), [0], [False], [0x14000088], None],
)
def test_closure_exact_single_upvalue_list(value):
    with pytest.raises(model.FactoryCallbackEntryError):
        model.apply(**arguments(closure_upvalues=value))


def test_bool_upvalue_cannot_alias_integer_one_userdata():
    with pytest.raises(model.FactoryCallbackEntryError):
        model.apply(**arguments(userdata=1, closure_upvalues=[True]))


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "list",
        "none",
        "bool",
        "float",
        "negative",
        "overflow",
        "esp",
    ],
)
def test_exact_entry_gpr_dictionary_schema_types_and_esp(mutation):
    kwargs = arguments()
    if mutation == "missing":
        del kwargs["registers"]["eax"]
    elif mutation == "extra":
        kwargs["registers"]["eflags"] = 0x246
    elif mutation == "list":
        kwargs["registers"] = list(kwargs["registers"].items())
    elif mutation == "none":
        kwargs["registers"] = None
    else:
        register = "esp" if mutation == "esp" else "eax"
        kwargs["registers"][register] = {
            "bool": True,
            "float": 0.0,
            "negative": -1,
            "overflow": 0x100000000,
            "esp": kwargs["callback_entry"] + 1,
        }[mutation]
    with pytest.raises(model.FactoryCallbackEntryError):
        model.apply(**kwargs)


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_inputs_immutable_results_detached_and_call_snapshots_independent():
    kwargs = arguments()
    original = copy.deepcopy(kwargs)
    first, second = model.apply(**kwargs), model.apply(**kwargs)
    assert kwargs == original and first == second
    assert containers(first).isdisjoint(containers(second))
    assert containers(first).isdisjoint(containers(kwargs))
    first["calls"][1]["arguments"][0] = 0
    first["calls"][1]["after"].clear()
    assert first["calls"][2]["before"] == [
        ("argument", kwargs["source_pointer"]),
        ("metatable", kwargs["userdata"]),
    ]
    first["class_caller"]["argument_record"][1] = 0
    first["class_caller"]["registers"]["ecx"] = 0
    first["closure_upvalues"].clear()
    first["userdata_extent"]["size"] = 0
    first["record_extent"]["pointer"] = 0
    assert model.apply(**kwargs) == second and kwargs == original
