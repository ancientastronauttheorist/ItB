"""Independent marker truth/stack laws, without executing the native callback."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_callback_error_semantics as errors


def inputs():
    return dict(
        state=0x1000,
        userdata=0x2000,
        upvalue_kind="zero",
        argument_has_metatable=False,
        argument_kind="nil",
    )


def test_nine_compatible_marker_modes_follow_independent_lua_stack_operations():
    concrete = {"zero": 0, "empty_string": "", "table": {}, "nil": None, "false": False}
    for upvalue_kind, argument_mode in itertools.product(
        ("zero", "empty_string", "table"),
        ((False, "nil"), (True, "nil"), (True, "false")),
    ):
        args = inputs()
        args.update(
            upvalue_kind=upvalue_kind,
            argument_has_metatable=argument_mode[0],
            argument_kind=argument_mode[1],
        )
        result = errors.apply(**args)
        assert len(result["calls"]) == (13 if argument_mode[0] else 9)
        stack = [("argument", 1)]
        for call in result["calls"]:
            assert call["before"] == stack
            api, arguments, phase = call["api"], call["arguments"], call["phase"]
            role = "upvalue" if phase == "upvalue_marker" else "argument"
            if api == "lua_getmetatable":
                has_metatable = role == "upvalue" or argument_mode[0]
                assert call["result"] == int(has_metatable)
                if has_metatable:
                    stack.append(("metatable", role))
            elif api == "lua_pushstring":
                if phase == "error":
                    stack.append(("message", "argument_marker_error"))
                else:
                    stack.append(("literal", "marker_key"))
            elif api == "lua_gettable":
                assert stack[arguments[1]] == ("metatable", role)
                stack.pop()
                stack.append(
                    (
                        "marker_value",
                        role,
                        upvalue_kind if role == "upvalue" else argument_mode[1],
                    )
                )
            elif api == "lua_toboolean":
                marker = concrete[stack[-1][2]]
                # Lua's falseness is nil/false only, never Python bool(value).
                truth = marker is not None and marker is not False
                assert call["result"] == int(truth)
            elif api == "lua_settop":
                stack = stack[: len(stack) + arguments[1] + 1]
                assert stack == [("argument", 1)]
            elif api == "lua_touserdata":
                assert call["result"] == args["userdata"]
            elif api == "lua_error":
                assert call["result"] is None
            assert call["after"] == stack
        assert (
            result["error_entry_lua_stack"]
            == stack
            == [("argument", 1), ("message", "argument_marker_error")]
        )
        assert result["marker_results"] == dict(upvalue_al=1, argument_al=0)
        assert result["closure_upvalue"] == ("userdata", args["userdata"])
        assert result["userdata"] == args["userdata"]
        assert result["lua_stack_delta"] == 1


@pytest.mark.parametrize(
    "has_metatable,kind", [(False, "nil"), (True, "nil"), (True, "false")]
)
def test_exact_api_arguments_phase_order_and_import_entry(has_metatable, kind):
    args = inputs()
    args.update(argument_has_metatable=has_metatable, argument_kind=kind)
    result = errors.apply(**args)
    L = args["state"]
    expected = [("lua_touserdata", [L, -10003], L * 2, "direct")]
    for phase, index, present, truth in (
        ("upvalue_marker", -10003, True, 1),
        ("argument_marker", 1, has_metatable, 0),
    ):
        expected.append(("lua_getmetatable", [L, index], int(present), phase))
        if present:
            expected.extend(
                [
                    ("lua_pushstring", [L, 0x83C738], 0, phase),
                    ("lua_gettable", [L, -2], 0, phase),
                    ("lua_toboolean", [L, -1], truth, phase),
                    ("lua_settop", [L, -3], 0, phase),
                ]
            )
    expected += [
        ("lua_pushstring", [L, 0x83C99C], 0, "error"),
        ("lua_error", [L], None, "error"),
    ]
    assert [
        (c["api"], c["arguments"], c["result"], c["phase"]) for c in result["calls"]
    ] == expected
    assert result["marker_literal"] == dict(pointer=0x83C738, text="__luabind_classrep")
    assert result["error_literal"] == dict(
        pointer=0x83C99C, text="expected class to derive from or a newline"
    )
    assert result["endpoint"] == dict(
        api="lua_error",
        iat_rva=0x3D6498,
        call_rva=0x2EC195,
        return_rva=0x2EC19B,
        arguments=[L],
    )
    assert result["native_marker_requests"] == [
        dict(target_rva=0x2EB560, state=L, index=-10003, expected_al=1),
        dict(target_rva=0x2EB560, state=L, index=1, expected_al=0),
    ]
    assert result["frame"] == dict(
        ebp_delta_from_entry_esp=-4,
        idle_esp_delta_from_ebp=-36,
        pushstring_esp_delta_from_idle=-12,
        pushstring_esp_delta_from_ebp=-48,
        pushstring_stack_words=[0x6EC194, L, 0x83C99C],
        error_esp_delta_from_idle=-16,
        error_esp_delta_from_ebp=-52,
        error_stack_words=[0x6EC19B, L, L, 0x83C99C],
    )


@pytest.mark.parametrize("field", ["state", "userdata"])
@pytest.mark.parametrize("value", [False, True, 0, -1, 0x100000000, 1.0, None, "1"])
def test_invalid_pointer_words_rejected(field, value):
    args = inputs()
    args[field] = value
    with pytest.raises(errors.CallbackErrorSemanticsError, match="nonzero uint32"):
        errors.apply(**args)


def test_positive_word_boundaries_are_opaque_not_dereferenced():
    for state, userdata in itertools.product((1, 0xFFFFFFFF), repeat=2):
        args = inputs()
        args.update(state=state, userdata=userdata)
        result = errors.apply(**args)
        assert result["calls"][0]["result"] == userdata
        assert result["frame"]["error_stack_words"][1:3] == [state, state]


@pytest.mark.parametrize(
    "kind", [None, 0, False, "nil", "false", "true", "userdata", ""]
)
def test_upvalue_false_or_unsupported_kinds_rejected(kind):
    args = inputs()
    args["upvalue_kind"] = kind
    with pytest.raises(errors.CallbackErrorSemanticsError, match="upvalue kind"):
        errors.apply(**args)


@pytest.mark.parametrize("value", [None, 0, 1, "false", [], {}])
def test_metatable_presence_requires_exact_bool(value):
    args = inputs()
    args["argument_has_metatable"] = value
    with pytest.raises(errors.CallbackErrorSemanticsError, match="must be bool"):
        errors.apply(**args)


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize(
    "kind", [None, False, 0, "zero", "empty_string", "table", "true", ""]
)
def test_argument_true_or_unsupported_kinds_rejected(present, kind):
    args = inputs()
    args.update(argument_has_metatable=present, argument_kind=kind)
    with pytest.raises(errors.CallbackErrorSemanticsError, match="argument kind"):
        errors.apply(**args)


def test_absent_metatable_requires_nil_kind():
    args = inputs()
    args["argument_kind"] = "false"
    with pytest.raises(errors.CallbackErrorSemanticsError, match="without one"):
        errors.apply(**args)


def test_exact_subclass_guards_and_output_detachment():
    class Word(int):
        pass

    class Kind(str):
        pass

    for field in ("state", "userdata", "upvalue_kind", "argument_kind"):
        args = inputs()
        args[field] = (
            Word(args[field]) if type(args[field]) is int else Kind(args[field])
        )
        with pytest.raises(errors.CallbackErrorSemanticsError):
            errors.apply(**args)
    args = inputs()
    before = copy.deepcopy(args)
    first, second = errors.apply(**args), errors.apply(**args)
    expected = copy.deepcopy(second)
    first["calls"][0]["arguments"].clear()
    first["calls"][1]["after"].clear()
    first["calls"][-2]["after"].clear()
    first["native_marker_requests"][0]["index"] = 0
    first["frame"]["error_stack_words"].clear()
    first["marker_results"]["upvalue_al"] = 0
    assert first["calls"][2]["before"] == [("argument", 1), ("metatable", "upvalue")]
    assert first["calls"][-1]["before"] == [
        ("argument", 1),
        ("message", "argument_marker_error"),
    ]
    assert first["initial_lua_stack"] == [("argument", 1)]
    assert first["closure_upvalue"] == ("userdata", args["userdata"])
    assert args == before
    assert second == expected
    assert errors.apply(**args) == expected
