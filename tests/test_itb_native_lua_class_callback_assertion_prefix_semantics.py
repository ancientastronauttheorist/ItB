import copy
import pytest
from src.observatory import (
    native_lua_class_callback_assertion_prefix_semantics as model,
)


def test_null_upvalue_short_circuits_opaque_marker_contracts():
    r = model.apply(state=1, userdata=0, has_metatable=object(), value_kind=object())
    assert r["calls"] == [
        dict(
            api="lua_touserdata",
            arguments=[1, -10003],
            result=0,
            before=[("argument", 1)],
            after=[("argument", 1)],
            phase="direct",
            literal_role=None,
        )
    ]
    assert r["reason"] == "null_upvalue" and r["marker_al"] is None
    assert r["native_boundary"] == dict(
        target_rva=0x379CC2,
        call_rva=0x2EC14C,
        continuation=0x6EC151,
        arguments=[0x83CA00, 0x83C9C8, 69],
    )


@pytest.mark.parametrize(
    "present,kind", [(False, "nil"), (True, "nil"), (True, "false")]
)
@pytest.mark.parametrize(
    "state,userdata", [(1, 1), (0xFFFFFFFF, 0xFFFFFFFF), (0x12001000, 0x11000FFF)]
)
def test_independent_false_marker_stack_interpreter(present, kind, state, userdata):
    r = model.apply(
        state=state, userdata=userdata, has_metatable=present, value_kind=kind
    )
    stack = [("argument", 1)]
    names = []
    for call in r["calls"]:
        assert call["before"] == stack
        name = call["api"]
        names.append(name)
        assert call["arguments"][0] == state
        if name == "lua_getmetatable":
            assert call["arguments"][1:] == [-10003] and call["result"] == int(present)
            if present:
                stack.append(("metatable", "upvalue"))
        elif name == "lua_pushstring":
            stack.append(("literal", "marker_key"))
        elif name == "lua_gettable":
            stack[-1] = ("marker_value", "upvalue", kind)
        elif name == "lua_settop":
            del stack[-2:]
        elif name == "lua_toboolean":
            assert call["result"] == 0
        else:
            assert name == "lua_touserdata" and call["result"] == userdata
        assert call["after"] == stack
    assert names == ["lua_touserdata", "lua_getmetatable"] + (
        ["lua_pushstring", "lua_gettable", "lua_toboolean", "lua_settop"]
        if present
        else []
    )
    assert stack == r["final_lua_stack"] == [("argument", 1)]
    assert r["marker_al"] == 0 and r["lua_stack_delta"] == 0
    assert r["native_boundary"] == dict(
        target_rva=0x379CC2,
        call_rva=0x2EC170,
        continuation=0x6EC175,
        arguments=[0x83C908, 0x83C9C8, 70],
    )
    assert r["frame"]["stack_words"] == [0x6EC175, 0x83C908, 0x83C9C8, 70]
    assert r["frame"]["boundary_esp_delta_from_ebp"] == -52


@pytest.mark.parametrize(
    "key,value",
    [
        ("state", 0),
        ("state", True),
        ("state", -1),
        ("state", 0x100000000),
        ("state", 1.0),
        ("userdata", True),
        ("userdata", -1),
        ("userdata", 0x100000000),
        ("userdata", None),
        ("has_metatable", 0),
        ("has_metatable", 1),
        ("value_kind", "zero"),
        ("value_kind", "table"),
        ("value_kind", False),
    ],
)
def test_reached_strict_domains(key, value):
    kwargs = dict(state=1, userdata=1, has_metatable=True, value_kind="nil")
    kwargs[key] = value
    with pytest.raises(model.AssertionPrefixError):
        model.apply(**kwargs)


def test_absent_metatable_requires_nil():
    with pytest.raises(model.AssertionPrefixError):
        model.apply(state=1, userdata=1, has_metatable=False, value_kind="false")


def test_outputs_detached():
    kwargs = dict(state=1, userdata=1, has_metatable=True, value_kind="false")
    baseline = model.apply(**kwargs)
    modified = model.apply(**kwargs)
    modified["calls"][0]["after"].append(("wrong", 1))
    modified["calls"][1]["arguments"][0] = 2
    modified["native_boundary"]["arguments"][0] = 0
    modified["final_lua_stack"].clear()
    assert model.apply(**kwargs) == baseline
    assert modified["calls"][1]["before"] == [("argument", 1)]
