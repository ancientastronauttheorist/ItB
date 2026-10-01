"""Independent bounded data, frame and ABI checks for the empty continuation."""

import copy
import itertools

import pytest
from src.observatory import (
    native_lua_class_factory_callback_empty_class_semantics as model,
)


def arguments(**changes):
    entry = changes.get("callback_entry", 0x30001030)
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
        closure_target=0x006EC110,
        closure_upvalues=[userdata],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
        vector_pointer=0x06002007,
        cookie=0xD43782A1,
    )
    result.update(changes)
    return result


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


@pytest.mark.parametrize(
    "upvalue,argument",
    list(itertools.product(("zero", "empty_string", "table"), repeat=2)),
)
def test_twelve_lua_requests_restore_prefix_before_empty_class(upvalue, argument):
    kwargs = arguments(upvalue_marker_kind=upvalue, argument_marker_kind=argument)
    result = model.apply(**kwargs)
    state, userdata, source = (
        kwargs["state"],
        kwargs["userdata"],
        kwargs["source_pointer"],
    )
    expected = [
        ("lua_touserdata", [state, -10003], userdata, "direct"),
        ("lua_getmetatable", [state, -10003], 1, "marker0"),
        ("lua_pushstring", [state, 0x83C738], 0, "marker0"),
        ("lua_gettable", [state, -2], 0, "marker0"),
        ("lua_toboolean", [state, -1], 1, "marker0"),
        ("lua_settop", [state, -3], 0, "marker0"),
        ("lua_getmetatable", [state, 1], 1, "marker1"),
        ("lua_pushstring", [state, 0x83C738], 0, "marker1"),
        ("lua_gettable", [state, -2], 0, "marker1"),
        ("lua_toboolean", [state, -1], 1, "marker1"),
        ("lua_settop", [state, -3], 0, "marker1"),
        ("lua_touserdata", [state, 1], source, "direct"),
    ]
    assert len(result["calls"]) == len(expected)
    stack = [("argument", source)]
    for call, (api, words, response, group) in zip(result["calls"], expected):
        assert call["before"] == stack
        assert (call["api"], call["arguments"], call["result"], call["group"]) == (
            api,
            [signed(word) for word in words],
            response,
            group,
        )
        identity = userdata if group == "marker0" else source
        kind = upvalue if group == "marker0" else argument
        if api == "lua_getmetatable":
            stack.append(("metatable", identity))
        elif api == "lua_pushstring":
            stack.append(("marker_key", identity))
        elif api == "lua_gettable":
            stack[-1] = ("marker_value", identity, kind)
        elif api == "lua_settop":
            del stack[-2:]
        assert call["after"] == stack
    assert (
        result["initial_lua_stack"]
        == result["boundary_lua_stack"]
        == [("argument", source)]
    )
    assert result["closure_target"] == 0x006EC110
    assert result["closure_upvalues"] == [userdata]
    assert result["userdata_extent"] == dict(pointer=userdata, size=72)
    assert result["record_extent"] == dict(pointer=kwargs["record_pointer"], size=24)


@pytest.mark.parametrize("entry", [56, 57, 0x30001030, 0x3000103F, 0xFFFFFFF8])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_original_class_packet_return_gprs_cookie_cells_and_endpoint(entry, cookie):
    kwargs = arguments(callback_entry=entry, cookie=cookie)
    result = model.apply(**kwargs)
    source, userdata, state = (
        kwargs["source_pointer"],
        kwargs["userdata"],
        kwargs["state"],
    )
    assert result["class_entry_rva"] == 0x002EB140
    assert result["class_caller"] == dict(
        return_address=0x006EC1BD,
        argaddress=entry - 20,
        argument_record=[0, source],
        registers=dict(
            eax=entry - 20,
            ebx=state,
            ecx=userdata,
            edx=0xB1000002,
            esi=userdata,
            edi=source,
            ebp=entry - 4,
            esp=entry - 48,
        ),
    )
    assert result["class_return"] == dict(
        registers=dict(
            eax=source,
            ebx=state,
            ecx=cookie,
            edx=0,
            esi=userdata,
            edi=source,
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    assert result["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert (
        result["native_cookie"]["stored_word"] ^ result["native_cookie"]["frame"]
    ) == cookie
    assert result["class_caller"]["argaddress"] == entry - 48 + 28
    assert result["class_return"]["registers"]["esp"] == entry - 48 + 8


@pytest.mark.parametrize("vector", [1, 0x06002000, 0x06002007, 0x0600201F, 0xFFFFFFF7])
def test_first_allocation_original_pair_field_updates_and_preservation_bytes(vector):
    kwargs = arguments(vector_pointer=vector)
    result = model.apply(**kwargs)
    source = kwargs["source_pointer"]
    assert result["heap_request"] == dict(
        continuation=0x00789463, handle=0x12345678, flags=0, bytes=8
    )
    assert result["vector"] == dict(
        records=[[0, source]],
        capacity=1,
        begin=vector,
        end=vector + 8,
        capacity_pointer=vector + 8,
    )
    assert result["field_updates"] == {4: vector, 8: vector + 8, 12: vector + 8}
    assert result["preserved_userdata_offsets"] == [
        0,
        16,
        20,
        24,
        28,
        32,
        36,
        40,
        44,
        48,
        52,
        56,
        60,
        64,
        68,
    ]
    original_userdata = bytes((index * 71 + 13) % 256 for index in range(72))
    expected_userdata = bytearray(original_userdata)
    expected_userdata[4:8] = vector.to_bytes(4, "little")
    expected_userdata[8:12] = (vector + 8).to_bytes(4, "little")
    expected_userdata[12:16] = (vector + 8).to_bytes(4, "little")
    modeled_userdata = bytearray(original_userdata)
    for offset, word in result["field_updates"].items():
        modeled_userdata[offset : offset + 4] = word.to_bytes(4, "little")
    assert modeled_userdata == expected_userdata
    for offset in result["preserved_userdata_offsets"]:
        assert (
            modeled_userdata[offset : offset + 4]
            == original_userdata[offset : offset + 4]
        )
    assert result["record_preserved_size"] == 24
    pair = b"\0" * 4 + source.to_bytes(4, "little")
    assert (
        b"".join(word.to_bytes(4, "little") for word in result["vector"]["records"][0])
        == pair
    )
    assert result["vector"]["records"][0] == result["class_caller"]["argument_record"]
    assert (
        result["vector"]["records"][0] is not result["class_caller"]["argument_record"]
    )


@pytest.mark.parametrize("domain", ["userdata", "record_pointer", "callback_entry"])
@pytest.mark.parametrize("position", ["before", "inside", "last", "after"])
def test_vector_span_aliases_reject_overlap_and_allow_exact_adjacent_spans(
    domain, position
):
    kwargs = arguments()
    start = kwargs[domain] - (48 if domain == "callback_entry" else 0)
    size = {"userdata": 72, "record_pointer": 24, "callback_entry": 56}[domain]
    kwargs["vector_pointer"] = {
        "before": start - 8,
        "inside": start - 7,
        "last": start + size - 1,
        "after": start + size,
    }[position]
    if position in ("inside", "last"):
        with pytest.raises(
            model.FactoryCallbackEmptyClassError, match="vector overlaps"
        ):
            model.apply(**kwargs)
    else:
        assert model.apply(**kwargs)["vector"]["begin"] == kwargs["vector_pointer"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("vector_pointer", 0),
        ("vector_pointer", True),
        ("vector_pointer", False),
        ("vector_pointer", -1),
        ("vector_pointer", 1.0),
        ("vector_pointer", None),
        ("vector_pointer", 0xFFFFFFF8),
        ("vector_pointer", 0xFFFFFFFF),
        ("vector_pointer", 0x100000000),
        ("cookie", True),
        ("cookie", False),
        ("cookie", -1),
        ("cookie", 0.0),
        ("cookie", None),
        ("cookie", 0x100000000),
        ("callback_entry", 48),
        ("callback_entry", 55),
        ("callback_entry", False),
        ("callback_entry", 0xFFFFFFF9),
        ("source_pointer", True),
        ("userdata", 0xFFFFFFB9),
        ("record_pointer", 0xFFFFFFE9),
        ("closure_upvalues", [False]),
        ("upvalue_marker_kind", "nil"),
        ("argument_marker_kind", "false"),
        ("upvalue_has_metatable", 1),
        ("argument_has_metatable", False),
    ],
)
def test_strict_new_words_cookie_cells_and_inherited_prefix_validation(key, value):
    with pytest.raises(model.FactoryCallbackEmptyClassError):
        model.apply(**arguments(**{key: value}))


def test_prefix_allowed_identity_alias_and_high_unsigned_words_are_retained():
    kwargs = arguments(
        state=0xFFFFFFFF,
        userdata=0xFFFFFFB8,
        record_pointer=0xFFFFFFE8,
        source_pointer=0xFFFFFFB8,
        callback_entry=0xFFFFFFF8,
    )
    result = model.apply(**kwargs)
    assert all(call["arguments"][0] == -1 for call in result["calls"])
    assert result["vector"]["records"] == [[0, 0xFFFFFFB8]]
    assert result["class_return"]["registers"]["eax"] == 0xFFFFFFB8
    assert result["record_preserved_size"] == 24


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_immutable_inputs_detached_prefix_and_independent_new_containers():
    kwargs = arguments()
    original = copy.deepcopy(kwargs)
    first, second = model.apply(**kwargs), model.apply(**kwargs)
    assert kwargs == original and first == second
    assert containers(first).isdisjoint(containers(second))
    assert containers(first).isdisjoint(containers(kwargs))
    first["vector"]["records"][0][1] = 0
    assert first["class_caller"]["argument_record"] == [0, kwargs["source_pointer"]]
    first["calls"][1]["after"].clear()
    assert first["calls"][2]["before"] == [
        ("argument", kwargs["source_pointer"]),
        ("metatable", kwargs["userdata"]),
    ]
    first["class_return"]["registers"]["eax"] = 0
    first["field_updates"].clear()
    first["preserved_userdata_offsets"].clear()
    first["heap_request"]["bytes"] = 0
    first["native_cookie"]["stored_word"] = 0
    first["closure_upvalues"].clear()
    assert model.apply(**kwargs) == second and kwargs == original
