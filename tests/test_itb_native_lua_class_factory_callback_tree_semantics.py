"""Independent bounded factory-tree laws; no native instruction oracle."""

import copy
import itertools

import pytest

from src.observatory import native_tree_balancing_semantics as balancing
from src.observatory import (
    native_lua_class_factory_callback_tree_semantics as model,
)


def source(keys, variant=0):
    payloads = [
        (
            [0, 0xFFFFFFFF, 0x80000000, 1, 0x12345678, 0xFEDCBA98, 7][index]
            if variant == 0
            else ((key * 0x10101 + variant) & 0xFFFFFFFF)
        )
        for index, key in enumerate(keys)
    ]
    return dict(tree=balancing.from_keys(keys), payloads=payloads)


def arguments(**changes):
    entry = changes.get("callback_entry", 0x30001030)
    userdata = changes.get("userdata", 0x14000087)
    result = dict(
        source_state=source([0xFFFFFFFF, 0, 0x80000000, 7, 0xFFFFFFFE, 1, 99]),
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


def check_tree(tree):
    """Independent parent, membership, ordering and red-black invariants."""
    nodes, seen, ordered = tree["nodes"], set(), []

    def visit(index, parent, low, high):
        if index is None:
            return 1
        assert type(index) is int and 0 <= index < len(nodes) and index not in seen
        seen.add(index)
        node = nodes[index]
        assert node["parent"] == parent and low < node["key"] < high
        assert type(node["color"]) is int and node["color"] in (0, 1)
        if node["color"] == 0:
            assert all(
                child is None or nodes[child]["color"] == 1
                for child in (node["left"], node["right"])
            )
        left = visit(node["left"], index, low, node["key"])
        ordered.append(node["key"])
        right = visit(node["right"], index, node["key"], high)
        assert left == right
        return left + node["color"]

    if tree["root"] is not None:
        assert nodes[tree["root"]]["color"] == 1
    visit(tree["root"], None, -1, 2**32)
    assert len(seen) == len(nodes)
    return ordered


KEYS = [0, 1, 7, 99, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF]


@pytest.mark.parametrize("size", range(8))
@pytest.mark.parametrize("order", ["ascending", "reversed", "alternating"])
@pytest.mark.parametrize("variant", [0, 1, 0xFFFFFFFF])
def test_inorder_copy_payloads_and_canonical_destination_invariants(
    size, order, variant
):
    keys = KEYS[:size]
    if order == "reversed":
        keys = keys[::-1]
    elif order == "alternating":
        keys = keys[::2] + keys[1::2][::-1]
    kwargs = arguments(source_state=source(keys, variant))
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    operation = result["callback_operation"]
    destination = operation["destination"]
    by_key = {
        key: kwargs["source_state"]["payloads"][index] for index, key in enumerate(keys)
    }
    assert check_tree(destination["tree"]) == sorted(keys)
    assert [node["key"] for node in destination["tree"]["nodes"]] == sorted(keys)
    assert destination["payloads"] == [by_key[key] for key in sorted(keys)]
    assert operation["copies"] == [
        dict(
            source=keys.index(key),
            destination=index,
            key=key,
            inserted=True,
            payload=by_key[key],
        )
        for index, key in enumerate(sorted(keys))
    ]
    assert operation["vector"] == dict(
        records=[[0, kwargs["source_pointer"]]], capacity=1
    )
    assert operation["return_word"] == kwargs["source_pointer"]
    assert operation["argument_kind"] == "external" and operation["grew"] is True
    assert result["source_state"] == kwargs["source_state"]
    assert result["tree_count"] == size
    assert result["class_transfer"] == dict(
        destination=destination, copies=operation["copies"]
    )
    assert kwargs == before


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def check_prefix(kwargs, calls):
    state, userdata, argument = (
        kwargs["state"],
        kwargs["userdata"],
        kwargs["source_pointer"],
    )
    expected = [("lua_touserdata", [state, -10003], userdata, "direct")]
    for identity_index, stack_index in ((0, -10003), (1, 1)):
        group = "marker" + str(identity_index)
        expected.extend(
            [
                ("lua_getmetatable", [state, stack_index], 1, group),
                ("lua_pushstring", [state, 0x83C738], 0, group),
                ("lua_gettable", [state, -2], 0, group),
                ("lua_toboolean", [state, -1], 1, group),
                ("lua_settop", [state, -3], 0, group),
            ]
        )
    expected.append(("lua_touserdata", [state, 1], argument, "direct"))
    stack = [("argument", argument)]
    assert len(calls) == 12
    for call, (api, words, response, group) in zip(calls, expected):
        assert call["before"] == stack
        assert (call["api"], call["arguments"], call["result"], call["group"]) == (
            api,
            [signed(word) for word in words],
            response,
            group,
        )
        identity = userdata if group == "marker0" else argument
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
    assert stack == [("argument", argument)]


def check_suffix(kwargs, result):
    """Interpret actual Lua indices and each supplied iterator response."""
    stack = [("argument", kwargs["source_pointer"])]
    registry = [
        kwargs["destination_refs"][0],
        kwargs["source_refs"][0],
        kwargs["destination_refs"][1],
        kwargs["source_refs"][1],
    ]
    registry_cursor, pair, cursor = 0, -1, 0
    assignments = [[], []]
    for call in result["registry_table_calls"]:
        assert call["before"] == stack
        api, args, truth = call["api"], call["arguments"], None
        if api == "lua_rawgeti":
            assert args == [-10000, registry[registry_cursor]]
            stack.append(("registry", registry[registry_cursor]))
            registry_cursor += 1
        elif api == "lua_pushnil":
            assert args == []
            pair += 1
            cursor = 0
            stack.append(("nil",))
        elif api == "lua_next":
            assert args == [-2] and stack[-2] == (
                "registry",
                kwargs["source_refs"][pair],
            )
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
            stack.insert(position, stack.pop())
        elif api == "lua_settable":
            assert args == [-5]
            assert stack[-5] == ("registry", kwargs["destination_refs"][pair])
            key, value = stack[-2:]
            assert key[0] == "key" and key[2] == "other" and value == ("value", key[1])
            assignments[pair].append(key[1])
            del stack[-2:]
        else:
            pytest.fail(f"unexpected API {api}")
        assert call["truth"] == truth and call["after"] == stack
    assert registry_cursor == 4 and pair == 1
    assert assignments == result["requested_assignments"]
    assert stack == result["normal_final_lua_stack"]


@pytest.mark.parametrize(
    "upvalue,argument", itertools.product(("zero", "empty_string", "table"), repeat=2)
)
def test_identity_prefix_normal_requests_and_tree_independent_suffix(upvalue, argument):
    kwargs = arguments(upvalue_marker_kind=upvalue, argument_marker_kind=argument)
    result = model.apply(**kwargs)
    check_prefix(kwargs, result["prefix_calls"])
    check_suffix(kwargs, result)
    assert result["calls"] == result["prefix_calls"]
    assert (
        result["normal_requests"]
        == result["prefix_calls"] + result["registry_table_calls"]
    )
    assert all(
        left["after"] == right["before"]
        for left, right in zip(result["normal_requests"], result["normal_requests"][1:])
    )
    assert len(result["normal_requests"]) == 62
    baseline = model.full_return_model.apply(
        **{key: value for key, value in kwargs.items() if key != "source_state"}
    )
    for field in (
        "class_return",
        "full_return",
        "normal_requests",
        "registry_requests",
        "table_transfers",
        "normal_final_lua_stack",
        "return_count",
    ):
        assert result[field] == baseline[field]


RECIPES = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
]


@pytest.mark.parametrize("first,second", RECIPES + [(["other"] * 3, ["other"] * 3)])
@pytest.mark.parametrize("word", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_table_recipes_registry_words_final_five_values_and_edx_count(
    first, second, word
):
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
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in (first, second)
    ]
    assert len(result["normal_requests"]) == 16 + sum(counts)
    assert result["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert result["source_word"] == result["destination_word"] == word
    assert result["normal_final_lua_stack"] == [
        ("argument", 0xFFFFFFB8),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert result["normal_lua_stack_delta"] == 4 and result["return_count"] == 0
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
    assert [table["api_count"] for table in result["table_transfers"]] == counts
    if first == second == ["other"] * 3:
        assert len(result["normal_requests"]) == 80


@pytest.mark.parametrize("entry", [56, 57, 0x30001030, 0xFFFFFFF8])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_all_eight_gprs_class_first_null_copy_cookie_flags_and_endpoint(entry, cookie):
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
    assert result["class_return"] == dict(
        registers=dict(
            eax=kwargs["source_pointer"],
            ebx=kwargs["state"],
            ecx=cookie,
            edx=0,
            esi=kwargs["userdata"],
            edi=kwargs["source_pointer"],
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


@pytest.mark.parametrize("size", range(8))
def test_five_normal_updates_thirteen_preserved_words_and_sentinel_links(size):
    kwargs = arguments(source_state=source(KEYS[:size]))
    result = model.apply(**kwargs)
    pointer = kwargs["vector_pointer"]
    assert result["normal_field_updates"] == {
        0: kwargs["source_word"],
        4: pointer,
        8: pointer + 8,
        12: pointer + 8,
        56: size,
    }
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert (
        result["normal_preserved_userdata_offsets"] == preserved
        and len(preserved) == 13
    )
    assert result["field_updates"] == {
        4: pointer,
        8: pointer + 8,
        12: pointer + 8,
        56: size,
    }
    assert result["preserved_userdata_offsets"] == [0] + preserved
    original = bytes((index * 71 + 13) % 256 for index in range(72))
    changed = bytearray(original)
    for offset, value in result["normal_field_updates"].items():
        changed[offset : offset + 4] = value.to_bytes(4, "little")
    for offset in preserved:
        assert changed[offset : offset + 4] == original[offset : offset + 4]
    assert result["sentinel_preserved_offsets"] == list(range(12, 24))
    assert "record_preserved_size" not in result and "heap_request" not in result
    tree = result["callback_operation"]["destination"]["tree"]
    assert result["sentinel_link_ids"] == dict(
        root=tree["root"],
        leftmost=0 if size else None,
        rightmost=size - 1 if size else None,
    )
    assert result["vector_heap_request"] == dict(
        continuation=0x00789463, handle=0x12345678, flags=0, bytes=8
    )
    assert result["tree_heap_requests"] == [
        dict(continuation=0x00789463, handle=0x12345678, flags=0, bytes=24)
        for _ in range(size)
    ]
    assert (
        all(
            type(value) is int and 0 <= value < size
            for value in result["sentinel_link_ids"].values()
        )
        if size
        else (set(result["sentinel_link_ids"].values()) == {None})
    )


@pytest.mark.parametrize(
    "kind",
    [
        "state_schema",
        "tree_schema",
        "tuple_nodes",
        "payload_count",
        "tuple_payloads",
        "bool_payload",
        "wide_payload",
        "negative_payload",
        "bool_key",
        "wide_key",
        "negative_key",
        "duplicate_key",
        "bool_root",
        "bool_color",
        "red_root",
        "bad_parent",
        "cycle",
        "unreachable",
        "black_height",
        "eight_nodes",
    ],
)
def test_strict_source_schema_uint32_redblack_membership_and_bound(kind):
    obj = source([2, 1, 3])
    if kind == "state_schema":
        obj["extra"] = 0
    elif kind == "tree_schema":
        obj["tree"]["extra"] = 0
    elif kind == "tuple_nodes":
        obj["tree"]["nodes"] = tuple(obj["tree"]["nodes"])
    elif kind == "payload_count":
        obj["payloads"].pop()
    elif kind == "tuple_payloads":
        obj["payloads"] = tuple(obj["payloads"])
    elif kind == "bool_payload":
        obj["payloads"][0] = True
    elif kind == "wide_payload":
        obj["payloads"][0] = 2**32
    elif kind == "negative_payload":
        obj["payloads"][0] = -1
    elif kind == "bool_key":
        obj["tree"]["nodes"][0]["key"] = True
    elif kind == "wide_key":
        obj["tree"]["nodes"][0]["key"] = 2**32
    elif kind == "negative_key":
        obj["tree"]["nodes"][0]["key"] = -1
    elif kind == "duplicate_key":
        obj["tree"]["nodes"][1]["key"] = 2
    elif kind == "bool_root":
        obj["tree"]["root"] = False
    elif kind == "bool_color":
        obj["tree"]["nodes"][0]["color"] = True
    elif kind == "red_root":
        obj["tree"]["nodes"][0]["color"] = 0
    elif kind == "bad_parent":
        obj["tree"]["nodes"][1]["parent"] = None
    elif kind == "cycle":
        obj["tree"]["nodes"][0]["left"] = 0
    elif kind == "unreachable":
        obj["tree"]["root"] = None
    elif kind == "black_height":
        obj["tree"]["nodes"][1]["color"] = 1
    else:
        obj = dict(tree=balancing.from_keys(list(range(8))), payloads=list(range(8)))
    kwargs = arguments(source_state=obj)
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackTreeError):
        model.apply(**kwargs)
    assert kwargs == before
    assert issubclass(
        model.FactoryCallbackTreeError,
        model.full_return_model.FactoryCallbackReturnError,
    )


@pytest.mark.parametrize("value", [False, True, -1, 2**32, 1.0, "1", None])
@pytest.mark.parametrize(
    "field", ["source_word", "destination_word", "destination_ref", "source_ref"]
)
def test_inherited_strict_words_and_refs(field, value):
    kwargs = arguments()
    if field.endswith("_ref"):
        kwargs[field + "s"][0] = value
    else:
        kwargs[field] = value
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackTreeError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_pointer", 0),
        ("source_pointer", 0xFFFFFFB9),
        ("source_pointer", True),
        ("cookie", False),
        ("cookie", 2**32),
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
def test_inherited_identity_closure_marker_extent_and_transfer_guards(field, value):
    kwargs = arguments(**{field: value})
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackTreeError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "first,second",
    itertools.combinations(
        (
            "userdata",
            "record_pointer",
            "source_pointer",
            "vector_pointer",
            "callback_entry",
        ),
        2,
    ),
)
@pytest.mark.parametrize("position", ["before", "first", "last", "after"])
def test_all_extent_aliases_and_exact_adjacency(first, second, position):
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
        with pytest.raises(model.FactoryCallbackTreeError, match="overlaps"):
            model.apply(**kwargs)
    else:
        assert model.apply(**kwargs)["tree_count"] == 7


@pytest.mark.parametrize(
    "failure", ["vector", "copies", "payloads", "tree", "kind", "return_word"]
)
def test_generic_tree_operation_packet_disagreement_rejected(monkeypatch, failure):
    original = model.callback.apply

    def mismatch(source_state, *args, **kwargs):
        result = original(source_state, *args, **kwargs)
        if source_state["tree"]["nodes"]:
            operation = result["class_operation"]
            if failure == "vector":
                operation["vector"]["capacity"] = 2
            elif failure == "copies":
                operation["copies"].reverse()
            elif failure == "payloads":
                operation["destination"]["payloads"][0] ^= 1
            elif failure == "tree":
                operation["destination"]["tree"]["root"] = 0
            elif failure == "kind":
                operation["argument_kind"] = "internal"
            else:
                operation["return_word"] = 7
        return result

    monkeypatch.setattr(model.callback, "apply", mismatch)
    with pytest.raises(model.FactoryCallbackTreeError, match="disagree"):
        model.apply(**arguments())


@pytest.mark.parametrize(
    "failure", ["call", "registry", "table", "assignments", "stack", "count"]
)
def test_coordinated_baseline_and_generic_suffix_corruption_rejected(
    monkeypatch, failure
):
    original = model.callback.apply

    def mismatch(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure == "call":
            result["calls"][0]["arguments"][1] = 7
        elif failure == "registry":
            result["registry_requests"][0]["reference"] = 7
        elif failure == "table":
            result["table_transfers"][0]["api_count"] += 1
        elif failure == "assignments":
            result["requested_assignments"][0] = []
        elif failure == "stack":
            result["final_lua_stack"][1] = ("registry", 7)
        else:
            result["return_count"] = 1
        return result

    monkeypatch.setattr(model.callback, "apply", mismatch)
    with pytest.raises(model.FactoryCallbackTreeError, match="disagree"):
        model.apply(**arguments())


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_inputs_outputs_repeated_results_and_parallel_views_are_detached():
    kwargs = arguments()
    before = copy.deepcopy(kwargs)
    first, second = model.apply(**kwargs), model.apply(**kwargs)
    assert first == second and kwargs == before
    assert containers(first).isdisjoint(containers(kwargs))
    assert containers(first).isdisjoint(containers(second))
    for left, right in (
        ("callback_operation", "class_transfer"),
        ("source_state", "class_transfer"),
        ("normal_requests", "registry_table_calls"),
        ("prefix_calls", "calls"),
        ("tree_heap_requests", "vector_heap_request"),
    ):
        assert containers(first[left]).isdisjoint(containers(first[right]))
    first["source_state"]["payloads"][0] ^= 1
    first["callback_operation"]["destination"]["payloads"][0] ^= 1
    first["callback_operation"]["copies"][0]["payload"] ^= 1
    first["callback_operation"]["vector"]["records"][0][1] = 0
    assert first["class_transfer"] == second["class_transfer"]
    assert first["vector"] == second["vector"]
    first["normal_requests"][12]["after"].clear()
    assert first["registry_table_calls"] == second["registry_table_calls"]
    first["tree_heap_requests"][0]["bytes"] = 0
    assert first["tree_heap_requests"][1:] == second["tree_heap_requests"][1:]
    first["sentinel_link_ids"]["root"] = None
    first["sentinel_preserved_offsets"].clear()
    assert model.apply(**kwargs) == second and kwargs == before
