"""Independent identity, suffix-stack and complete-return laws; no native oracle."""

import copy
import itertools

import pytest

from src.observatory import (
    native_lua_class_factory_callback_return_semantics as model,
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
        source_word=0xFEDCBA98,
        destination_word=0x87654321,
        destination_refs=[11, 22],
        source_refs=[33, 44],
        transfers=[["init", "other", "finalize"], ["other", "finalize", "init"]],
    )
    result.update(changes)
    return result


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def check_prefix(kwargs, calls):
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
    assert len(calls) == 12
    stack = [("argument", source)]
    for call, (api, words, response, group) in zip(calls, expected):
        assert set(call) == {"api", "arguments", "result", "before", "after", "group"}
        assert call["before"] == stack
        assert (call["api"], call["arguments"], call["result"], call["group"]) == (
            api,
            [signed(word) for word in words],
            response,
            group,
        )
        identity = userdata if group == "marker0" else source
        kind = kwargs[
            "upvalue_marker_kind" if group == "marker0" else "argument_marker_kind"
        ]
        if api == "lua_getmetatable":
            stack.append(("metatable", identity))
        elif api == "lua_pushstring":
            stack.append(("marker_key", identity))
        elif api == "lua_gettable":
            stack[-1] = ("marker_value", identity, kind)
        elif api == "lua_settop":
            del stack[-2:]
        assert call["after"] == stack
    assert stack == [("argument", source)]


def check_suffix(kwargs, result):
    """Interpret each recorded API using Lua stack indices and supplied values."""
    stack = [("argument", kwargs["source_pointer"])]
    registry_order = [
        kwargs["destination_refs"][0],
        kwargs["source_refs"][0],
        kwargs["destination_refs"][1],
        kwargs["source_refs"][1],
    ]
    registry_cursor = 0
    pair, cursor = -1, 0
    assignments = [[], []]
    for call in result["registry_table_calls"]:
        assert set(call) == {"api", "arguments", "before", "after", "truth"}
        assert call["before"] == stack
        api, args, truth = call["api"], call["arguments"], None
        if api == "lua_rawgeti":
            reference = registry_order[registry_cursor]
            assert args == [-10000, reference]
            stack.append(("registry", reference))
            registry_cursor += 1
        elif api == "lua_pushnil":
            assert args == [] and registry_cursor in (2, 4)
            pair += 1
            cursor = 0
            stack.append(("nil",))
        elif api == "lua_next":
            assert args == [-2]
            assert stack[-2] == ("registry", kwargs["source_refs"][pair])
            kinds = kwargs["transfers"][pair]
            assert stack.pop() == (
                ("nil",) if cursor == 0 else ("key", cursor - 1, kinds[cursor - 1])
            )
            truth = int(cursor < len(kinds))
            if truth:
                stack.extend([("key", cursor, kinds[cursor]), ("value", cursor)])
                cursor += 1
        elif api == "lua_pushstring":
            assert args in (["__init"], ["__finalize"])
            stack.append(("literal", args[0]))
        elif api == "lua_equal":
            assert args == [-1, -3]
            assert stack[-1][0] == "literal" and stack[-3][0] == "key"
            truth = int("__" + stack[-3][2] == stack[-1][1])
        elif api == "lua_settop":
            assert args in ([-2], [-3])
            del stack[len(stack) + args[0] + 1 :]
        elif api == "lua_pushvalue":
            assert args == [-2]
            stack.append(stack[-2])
        elif api == "lua_insert":
            assert args == [-2]
            position = len(stack) - 2
            value = stack.pop()
            stack.insert(position, value)
        elif api == "lua_settable":
            assert args == [-5]
            assert stack[-5] == ("registry", kwargs["destination_refs"][pair])
            key, value = stack[-2:]
            assert key[0] == "key" and key[2] == "other"
            assert value == ("value", key[1])
            assignments[pair].append(key[1])
            del stack[-2:]
        else:
            pytest.fail(f"unexpected suffix API {api}")
        assert call["truth"] == truth
        assert call["after"] == stack
    assert registry_cursor == 4 and pair == 1
    assert assignments == result["requested_assignments"]
    assert stack == result["normal_final_lua_stack"]


@pytest.mark.parametrize(
    "upvalue,argument",
    list(itertools.product(("zero", "empty_string", "table"), repeat=2)),
)
def test_identity_bound_prefix_and_independent_normal_suffix(upvalue, argument):
    kwargs = arguments(upvalue_marker_kind=upvalue, argument_marker_kind=argument)
    result = model.apply(**kwargs)
    check_prefix(kwargs, result["prefix_calls"])
    check_suffix(kwargs, result)
    assert result["calls"] == result["prefix_calls"]
    assert result["normal_requests"] == (
        result["prefix_calls"] + result["registry_table_calls"]
    )
    assert all(
        left["after"] == right["before"]
        for left, right in zip(result["normal_requests"], result["normal_requests"][1:])
    )
    assert len(result["normal_requests"]) == 62


TRANSFER_PAIRS = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
]


@pytest.mark.parametrize("first,second", TRANSFER_PAIRS)
@pytest.mark.parametrize("word", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_transfer_recipes_words_refs_final_stack_and_count_law(first, second, word):
    kwargs = arguments(
        source_pointer=0xFFFFFFB8,
        source_word=word,
        destination_word=word ^ 0xFFFFFFFF,
        destination_refs=[0, 0xFFFFFFFF],
        source_refs=[0xFFFFFFFF, 0],
        transfers=[first, second],
    )
    result = model.apply(**kwargs)
    check_suffix(kwargs, result)
    assert result["source_word"] == result["destination_word"] == word
    assert result["normal_initial_lua_stack"] == [("argument", 0xFFFFFFB8)]
    assert result["normal_final_lua_stack"] == [
        ("argument", 0xFFFFFFB8),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert result["normal_lua_stack_delta"] == 4 and result["return_count"] == 0
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in (first, second)
    ]
    assert len(result["normal_requests"]) == 16 + sum(counts)
    assert result["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert result["requested_assignments"] == [
        [index for index, kind in enumerate(recipe) if kind == "other"]
        for recipe in (first, second)
    ]
    assert result["registry_requests"] == [
        dict(
            role=role,
            field_offset=offset,
            reference=reference,
            arguments=[-10000, reference],
        )
        for role, offset, reference in (
            ("destination", 32, 0),
            ("source", 32, 0xFFFFFFFF),
            ("destination", 40, 0xFFFFFFFF),
            ("source", 40, 0),
        )
    ]
    for pair, transfer in enumerate(result["table_transfers"]):
        prefix_size = 1 + pair * 2
        assert transfer["initial"] == transfer["final"]
        assert (
            transfer["initial"] == result["normal_final_lua_stack"][: prefix_size + 2]
        )
        assert transfer["api_count"] == counts[pair]
        assert transfer["lua_stack_delta"] == 0
        assert all(
            call["before"][:prefix_size] == transfer["initial"][:prefix_size]
            and call["after"][:prefix_size] == transfer["initial"][:prefix_size]
            for call in transfer["calls"]
        )


@pytest.mark.parametrize("entry", [56, 57, 0x30001030, 0xFFFFFFF8])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_complete_normal_gprs_cookie_flags_endpoint_and_23_call_response(entry, cookie):
    kwargs = arguments(callback_entry=entry, cookie=cookie)
    result = model.apply(**kwargs)
    incoming = kwargs["registers"]
    assert result["full_return"] == dict(
        registers=dict(
            eax=0,
            ebx=incoming["ebx"],
            ecx=cookie,
            edx=0xB0000317,
            esi=incoming["esi"],
            edi=incoming["edi"],
            ebp=incoming["ebp"],
            esp=entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    assert result["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert result["class_return"]["registers"]["esp"] == entry - 40
    assert result["class_caller"]["registers"]["esp"] == entry - 48


def test_original_pair_empty_class_growth_and_four_updates_preserve_14_dwords():
    kwargs = arguments()
    result = model.apply(**kwargs)
    pointer, source, word = (
        kwargs["vector_pointer"],
        kwargs["source_pointer"],
        kwargs["source_word"],
    )
    assert result["callback_operation"] == dict(
        destination={"tree": {"root": None, "nodes": []}, "payloads": []},
        copies=[],
        vector={"records": [[0, source]], "capacity": 1},
        return_word=source,
        argument_kind="external",
        grew=True,
    )
    assert result["vector"] == dict(
        records=[[0, source]],
        capacity=1,
        begin=pointer,
        end=pointer + 8,
        capacity_pointer=pointer + 8,
    )
    assert result["class_caller"]["argument_record"] == [0, source]
    assert result["normal_field_updates"] == {
        0: word,
        4: pointer,
        8: pointer + 8,
        12: pointer + 8,
    }
    assert result["field_updates"] == {4: pointer, 8: pointer + 8, 12: pointer + 8}
    assert result["normal_preserved_userdata_offsets"] == list(range(16, 72, 4))
    assert len(result["normal_preserved_userdata_offsets"]) == 14
    original = bytes((index * 71 + 13) % 256 for index in range(72))
    changed = bytearray(original)
    for offset, value in result["normal_field_updates"].items():
        changed[offset : offset + 4] = value.to_bytes(4, "little")
    assert changed[:16] == b"".join(
        value.to_bytes(4, "little")
        for value in (word, pointer, pointer + 8, pointer + 8)
    )
    assert changed[16:] == original[16:]
    assert result["record_preserved_size"] == 24
    original_record = bytes(range(24))
    assert original_record[: result["record_preserved_size"]] == original_record


@pytest.mark.parametrize("value", [False, True, -1, 0x100000000, 1.0, "1", None])
@pytest.mark.parametrize(
    "field", ["source_word", "destination_word", "destination_ref", "source_ref"]
)
def test_strict_words_and_refs_translate_to_empty_class_subclass(field, value):
    kwargs = arguments()
    if field.endswith("_ref"):
        kwargs[field + "s"][0] = value
    else:
        kwargs[field] = value
    original = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackReturnError):
        model.apply(**kwargs)
    assert kwargs == original
    assert issubclass(
        model.FactoryCallbackReturnError,
        model.empty_class.FactoryCallbackEmptyClassError,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_pointer", 0),
        ("source_pointer", True),
        ("cookie", False),
        ("cookie", 0x100000000),
        ("vector_pointer", 0),
        ("vector_pointer", 0xFFFFFFF8),
        ("callback_entry", 55),
        ("callback_entry", 0xFFFFFFF9),
        ("closure_target", 0x6EC111),
        ("closure_target", False),
        ("closure_upvalues", []),
        ("closure_upvalues", [False]),
        ("closure_upvalues", [0x14000087, 0x14000087]),
        ("upvalue_has_metatable", 1),
        ("argument_has_metatable", False),
        ("upvalue_marker_kind", "nil"),
        ("argument_marker_kind", "false"),
        ("destination_refs", [1]),
        ("destination_refs", (1, 2)),
        ("source_refs", [1, 2, 3]),
        ("transfers", ([], [])),
        ("transfers", [[]]),
        ("transfers", [[], [], []]),
        ("transfers", [(), []]),
        ("transfers", [["other"] * 4, []]),
        ("transfers", [["unknown"], []]),
        ("transfers", [[True], []]),
    ],
)
def test_invalid_or_unproved_inputs_rejected_without_mutation(field, value):
    kwargs = arguments(**{field: value})
    original = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackReturnError):
        model.apply(**kwargs)
    assert kwargs == original


@pytest.mark.parametrize("domain", ["userdata", "record_pointer", "callback_entry"])
def test_inherited_overlap_guards(domain):
    kwargs = arguments()
    kwargs["vector_pointer"] = kwargs[domain] - (
        48 if domain == "callback_entry" else 0
    )
    with pytest.raises(model.FactoryCallbackReturnError, match="vector overlaps"):
        model.apply(**kwargs)


@pytest.mark.parametrize("source", [0xFFFFFFB9, 0xFFFFFFFF])
def test_source_full_72_byte_extent_wraps_rejected(source):
    with pytest.raises(
        model.FactoryCallbackReturnError, match="source pointer extent wraps"
    ):
        model.apply(**arguments(source_pointer=source))


@pytest.mark.parametrize(
    "first,second",
    list(
        itertools.combinations(
            (
                "userdata",
                "record_pointer",
                "source_pointer",
                "vector_pointer",
                "callback_entry",
            ),
            2,
        )
    ),
)
@pytest.mark.parametrize("position", ["before", "first", "last", "after"])
def test_all_modeled_span_pairs_overlap_and_exact_adjacency(first, second, position):
    kwargs = arguments()
    sizes = dict(
        userdata=72,
        record_pointer=24,
        source_pointer=72,
        vector_pointer=8,
        callback_entry=56,
    )
    base = 0x22002000
    kwargs[first] = base + (48 if first == "callback_entry" else 0)
    second_start = {
        "before": base - sizes[second],
        "first": base,
        "last": base + sizes[first] - 1,
        "after": base + sizes[first],
    }[position]
    kwargs[second] = second_start + (48 if second == "callback_entry" else 0)
    kwargs["registers"]["esp"] = kwargs["callback_entry"]
    kwargs["closure_upvalues"] = [kwargs["userdata"]]
    if position in ("first", "last"):
        with pytest.raises(model.FactoryCallbackReturnError, match="overlaps"):
            model.apply(**kwargs)
    else:
        assert model.apply(**kwargs)["normal_field_updates"][0] == kwargs["source_word"]


def test_all_other_triples_are_admitted_beyond_frozen_six_recipe_matrix():
    kwargs = arguments(transfers=[["other"] * 3, ["other"] * 3])
    result = model.apply(**kwargs)
    check_suffix(kwargs, result)
    assert len(result["normal_requests"]) == 80
    assert result["full_return"]["registers"]["edx"] == 0xB0000320


@pytest.mark.parametrize(
    "failure", ["vector", "return_word", "destination", "boundary"]
)
def test_disagreeing_composed_packets_rejected(monkeypatch, failure):
    if failure == "boundary":
        original = model.empty_class.apply

        def mismatch(**kwargs):
            result = original(**kwargs)
            result["boundary_lua_stack"] = [("argument", 7)]
            return result

        monkeypatch.setattr(model.empty_class, "apply", mismatch)
    else:
        original = model.callback.apply

        def mismatch(*args, **kwargs):
            result = original(*args, **kwargs)
            operation = result["class_operation"]
            if failure == "vector":
                operation["vector"]["capacity"] = 2
            elif failure == "return_word":
                operation["return_word"] = 7
            else:
                operation["destination"]["payloads"] = [7]
            return result

        monkeypatch.setattr(model.callback, "apply", mismatch)
    with pytest.raises(model.FactoryCallbackReturnError, match="disagree"):
        model.apply(**arguments())


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_inputs_repeated_outputs_and_request_views_are_detached():
    kwargs = arguments()
    original = copy.deepcopy(kwargs)
    first, second = model.apply(**kwargs), model.apply(**kwargs)
    assert kwargs == original and first == second
    assert containers(first).isdisjoint(containers(kwargs))
    assert containers(first).isdisjoint(containers(second))
    first["normal_requests"][12]["after"].clear()
    assert (
        first["registry_table_calls"][0]["after"]
        == second["registry_table_calls"][0]["after"]
    )
    first["prefix_calls"][1]["after"].clear()
    assert first["calls"] == second["calls"]
    first["registry_table_calls"][2]["after"].clear()
    assert first["table_transfers"] == second["table_transfers"]
    first["callback_operation"]["vector"]["records"][0][1] = 0
    assert first["vector"]["records"] == second["vector"]["records"]
    first["registry_requests"][0]["arguments"].clear()
    first["requested_assignments"][0].clear()
    assert first["table_transfers"] == second["table_transfers"]
    first["normal_final_lua_stack"].clear()
    first["full_return"]["registers"]["ebx"] = 0
    first["normal_field_updates"].clear()
    first["normal_preserved_userdata_offsets"].clear()
    assert model.apply(**kwargs) == second and kwargs == original
