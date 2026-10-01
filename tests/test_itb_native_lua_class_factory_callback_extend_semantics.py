"""Independent retained-ID, tree-union and callback extension laws."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_factory_callback_extend_semantics as model
from src.observatory import native_tree_balancing_semantics as balancing


def source(keys, seed):
    return dict(
        tree=balancing.from_keys(keys),
        payloads=[
            (seed ^ index * 0x01010101) & 0xFFFFFFFF for index in range(len(keys))
        ],
    )


def arguments(keys=None, **changes):
    entry = changes.get("callback_entry", 0x30001030)
    userdata = changes.get("userdata", 0x14000087)
    result = dict(
        source_state=source([5, 1, 3] if keys is None else keys, 0x75310000),
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


def inputs(first=None, second_keys=None, **changes):
    first = arguments() if first is None else first
    prior = model.tree_model.apply(**first)
    entry = changes.get("second_entry", 0x31001037)
    result = dict(
        first_arguments=first,
        second_source_state=source(
            [6, 0, 3] if second_keys is None else second_keys, 0xFFFFFFFF
        ),
        new_vector_pointer=0x0700301F,
        second_entry=entry,
        second_registers=dict(prior["full_return"]["registers"], esp=entry),
    )
    result.update(changes)
    return result


def values(state):
    return {
        node["key"]: state["payloads"][index]
        for index, node in enumerate(state["tree"]["nodes"])
    }


def check_redblack(tree):
    nodes, visited, inorder = tree["nodes"], set(), []

    def visit(index, parent, low, high):
        if index is None:
            return 1
        assert type(index) is int and 0 <= index < len(nodes) and index not in visited
        visited.add(index)
        node = nodes[index]
        assert node["parent"] == parent and low < node["key"] < high
        assert type(node["color"]) is int and node["color"] in (0, 1)
        if node["color"] == 0:
            assert all(
                child is None or nodes[child]["color"] == 1
                for child in (node["left"], node["right"])
            )
        left = visit(node["left"], index, low, node["key"])
        inorder.append(node["key"])
        right = visit(node["right"], index, node["key"], high)
        assert left == right
        return left + node["color"]

    if tree["root"] is not None:
        assert nodes[tree["root"]]["color"] == 1
    visit(tree["root"], None, -1, 2**32)
    assert len(visited) == len(nodes)
    return inorder


def check_union(kwargs, result):
    first, second = result["first"], result["second"]
    initial = first["callback_operation"]["destination"]
    selected = kwargs["second_source_state"]
    operation = second["callback_operation"]
    destination = operation["destination"]
    old_keys = [node["key"] for node in initial["tree"]["nodes"]]
    source_keys = [node["key"] for node in selected["tree"]["nodes"]]
    new_keys = sorted(set(source_keys) - set(old_keys))
    final_keys = old_keys + new_keys
    assert [node["key"] for node in destination["tree"]["nodes"]] == final_keys
    assert check_redblack(destination["tree"]) == sorted(
        set(old_keys) | set(source_keys)
    )
    assert values(destination) == {**values(initial), **values(selected)}
    for old_id, key in enumerate(old_keys):
        assert destination["tree"]["nodes"][old_id]["key"] == key
        if key not in source_keys:
            assert destination["payloads"][old_id] == initial["payloads"][old_id]
    assert operation["copies"] == [
        dict(
            source=source_keys.index(key),
            destination=final_keys.index(key),
            key=key,
            inserted=key not in old_keys,
            payload=values(selected)[key],
        )
        for key in sorted(source_keys)
    ]
    assert second["class_transfer"] == dict(
        destination=destination, copies=operation["copies"]
    )
    assert second["tree_count"] == len(final_keys) <= 14
    assert (
        second["normal_field_updates"][56]
        == second["field_updates"][56]
        == len(final_keys)
    )
    assert second["tree_heap_requests"] == [
        dict(continuation=0x789463, handle=0x12345678, flags=0, bytes=24)
        for _ in new_keys
    ]
    assert second["sentinel_link_ids"] == dict(
        root=destination["tree"]["root"],
        leftmost=final_keys.index(min(final_keys)) if final_keys else None,
        rightmost=final_keys.index(max(final_keys)) if final_keys else None,
    )
    assert second["sentinel_preserved_offsets"] == list(range(12, 24))
    assert len(second["normal_preserved_userdata_offsets"]) == 13


HIGH = [
    0x80000000,
    0x80000001,
    0x800000FF,
    0xFFFF0000,
    0xFFFFFF00,
    0xFFFFFFFE,
    0xFFFFFFFF,
]
LOW = [0, 1, 16, 255, 1024, 65535, 0x7FFFFFFF]
RECIPES = [
    ([], []),
    ([], [7, 1, 3]),
    ([7, 1, 3], []),
    ([7, 1, 3], [3, 7, 1]),
    ([7, 1, 3], [8, 2, 4]),
    ([10, 30, 50], [20, 40]),
    ([1, 3, 5], [0]),
    ([1, 3, 5], [7, 9]),
    ([1, 3, 5], [0, 3, 6]),
    (HIGH, LOW),
    (LOW, HIGH),
    (HIGH, list(reversed(HIGH))),
]


@pytest.mark.parametrize("first_keys,second_keys", RECIPES)
@pytest.mark.parametrize("order", ["supplied", "reversed", "alternating"])
@pytest.mark.parametrize("seed", [0, 0x80000000, 0xFFFFFFFF])
def test_empty_same_disjoint_minimum_interior_end_mixed_high_keys_and_union14(
    first_keys, second_keys, order, seed
):
    first_keys, second_keys = list(first_keys), list(second_keys)
    if order == "reversed":
        first_keys, second_keys = first_keys[::-1], second_keys[::-1]
    elif order == "alternating":
        first_keys = first_keys[::2] + first_keys[1::2][::-1]
        second_keys = second_keys[::2] + second_keys[1::2][::-1]
    kwargs = inputs(arguments(first_keys), second_keys)
    kwargs["second_source_state"] = source(second_keys, seed)
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    check_union(kwargs, result)
    assert result["first"] == model.tree_model.apply(**kwargs["first_arguments"])
    assert (
        result["second"]["source_state"] == kwargs["second_source_state"]
        and kwargs == before
    )
    if (
        set(first_keys).isdisjoint(second_keys)
        and len(first_keys) == len(second_keys) == 7
    ):
        assert result["second"]["tree_count"] == 14


@pytest.mark.parametrize(
    "first_size,second_size", itertools.product(range(8), repeat=2)
)
def test_all_source_counts_zero_through_seven_and_retained_payloads(
    first_size, second_size
):
    kwargs = inputs(
        arguments([10 * index for index in reversed(range(first_size))]),
        [10 * index + 5 for index in reversed(range(second_size))],
    )
    result = model.apply(**kwargs)
    check_union(kwargs, result)
    assert result["second"]["tree_count"] == first_size + second_size


def test_new_key_rotations_preserve_old_ids_and_unvisited_payloads():
    kwargs = inputs(arguments([10, 30, 50]), [0, 20, 40, 60, 70, 80, 90])
    result = model.apply(**kwargs)
    check_union(kwargs, result)
    old = result["first"]["callback_operation"]["destination"]
    new = result["second"]["callback_operation"]["destination"]
    assert new["payloads"][:3] == old["payloads"]
    assert any(
        new["tree"]["nodes"][index] != old["tree"]["nodes"][index] for index in range(3)
    )


TRANSFER_PAIRS = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
    (["other"] * 3, ["other"] * 3),
]


@pytest.mark.parametrize("first_transfer,second_transfer", TRANSFER_PAIRS)
@pytest.mark.parametrize("word", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_lua_word_refs_and_iterators_are_independent_of_new_tree_keys(
    first_transfer, second_transfer, word
):
    kwargs = inputs(
        arguments(
            source_word=word,
            destination_word=word ^ 0xFFFFFFFF,
            destination_refs=[0, 0xFFFFFFFF],
            source_refs=[0xFFFFFFFF, 0],
            transfers=[first_transfer, second_transfer],
        )
    )
    first, second = model.apply(**kwargs).values()
    for field in (
        "prefix_calls",
        "registry_table_calls",
        "registry_requests",
        "table_transfers",
        "requested_assignments",
        "normal_requests",
        "normal_initial_lua_stack",
        "normal_final_lua_stack",
    ):
        assert second[field] == first[field]
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in (first_transfer, second_transfer)
    ]
    assert len(second["normal_requests"]) == 16 + sum(counts)
    assert second["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert second["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert second["normal_lua_stack_delta"] == 4 and second["return_count"] == 0
    assert second["source_word"] == second["destination_word"] == word


@pytest.mark.parametrize("entry", [56, 57, 0x31001037, 0xFFFFFFF8])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_full_return_all_gprs_and_class_final_free_volatile_law(entry, cookie):
    kwargs = inputs(arguments(cookie=cookie), second_entry=entry)
    result = model.apply(**kwargs)
    incoming = kwargs["second_registers"]
    second = result["second"]
    assert second["full_return"] == dict(
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
    first = kwargs["first_arguments"]
    assert second["class_return"] == dict(
        registers=dict(
            eax=first["source_pointer"],
            ebx=first["state"],
            ecx=cookie,
            edx=0xB0000001,
            esi=first["userdata"],
            edi=first["source_pointer"],
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )


def test_vector_copies_old_pair_appends_same_pair_and_frees_only_old8():
    kwargs = inputs()
    result = model.apply(**kwargs)
    second = result["second"]
    pointer, old, argument = (
        kwargs["new_vector_pointer"],
        kwargs["first_arguments"]["vector_pointer"],
        kwargs["first_arguments"]["source_pointer"],
    )
    assert second["vector"] == dict(
        records=[[0, argument], [0, argument]],
        capacity=2,
        begin=pointer,
        end=pointer + 16,
        capacity_pointer=pointer + 16,
    )
    assert second["callback_operation"]["vector"] == dict(
        records=[[0, argument], [0, argument]], capacity=2
    )
    assert second["vector_heap_request"] == dict(
        continuation=0x789463, handle=0x12345678, flags=0, bytes=16
    )
    assert second["vector_free_request"] == dict(
        continuation=0x789172, handle=0x12345678, flags=0, pointer=old
    )
    assert second["old_vector_pointer"] == old and result["first"]["vector"][
        "records"
    ] == [[0, argument]]
    assert second["normal_field_updates"] == {
        0: kwargs["first_arguments"]["source_word"],
        4: pointer,
        8: pointer + 16,
        12: pointer + 16,
        56: 5,
    }
    assert second["normal_preserved_userdata_offsets"] == [
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
        60,
        64,
        68,
    ]


@pytest.mark.parametrize(
    "kind",
    [
        "first_schema",
        "first_eight",
        "second_eight",
        "second_schema",
        "tree_schema",
        "payload_bool",
        "payload_wide",
        "payload_count",
        "key_bool",
        "key_wide",
        "color_bool",
        "red_root",
        "cycle",
    ],
)
def test_strict_first_second_domains_schema_uint32_redblack_and_seven_node_bounds(kind):
    kwargs = inputs()
    obj = kwargs["second_source_state"]
    if kind == "first_schema":
        kwargs["first_arguments"]["extra"] = 0
    elif kind == "first_eight":
        kwargs["first_arguments"]["source_state"] = source(list(range(8)), 0)
    elif kind == "second_eight":
        kwargs["second_source_state"] = source(list(range(8)), 0)
    elif kind == "second_schema":
        obj["extra"] = 0
    elif kind == "tree_schema":
        obj["tree"]["extra"] = 0
    elif kind == "payload_bool":
        obj["payloads"][0] = True
    elif kind == "payload_wide":
        obj["payloads"][0] = 2**32
    elif kind == "payload_count":
        obj["payloads"].pop()
    elif kind == "key_bool":
        obj["tree"]["nodes"][0]["key"] = True
    elif kind == "key_wide":
        obj["tree"]["nodes"][0]["key"] = 2**32
    elif kind == "color_bool":
        obj["tree"]["nodes"][0]["color"] = False
    elif kind == "red_root":
        obj["tree"]["nodes"][obj["tree"]["root"]]["color"] = 0
    else:
        obj["tree"]["nodes"][0]["left"] = 0
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackExtendError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field",
    ["new_vector_pointer", "second_entry", "source_word", "source_ref", "second_gpr"],
)
@pytest.mark.parametrize("value", [False, True, -1, 2**32, 1.0, "1", None])
def test_inherited_strict_word_pointer_and_register_guards(field, value):
    kwargs = inputs()
    if field == "source_word":
        kwargs["first_arguments"]["source_word"] = value
    elif field == "source_ref":
        kwargs["first_arguments"]["source_refs"][0] = value
    elif field == "second_gpr":
        kwargs["second_registers"]["eax"] = value
    else:
        kwargs[field] = value
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackExtendError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_actual_first_return_is_required_for_every_second_gpr(register):
    kwargs = inputs()
    kwargs["second_registers"][register] ^= 1
    with pytest.raises(model.FactoryCallbackExtendError, match="actual first return"):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "target", ["old_vector", "userdata", "sentinel", "source", "second_frame"]
)
@pytest.mark.parametrize("position", ["before", "first", "last", "after"])
def test_new16_extent_aliases_and_exact_adjacency(target, position):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    base, size = dict(
        old_vector=(first["vector_pointer"], 8),
        userdata=(first["userdata"], 72),
        sentinel=(first["record_pointer"], 24),
        source=(first["source_pointer"], 72),
        second_frame=(kwargs["second_entry"] - 48, 56),
    )[target]
    kwargs["new_vector_pointer"] = {
        "before": base - 16,
        "first": base,
        "last": base + size - 1,
        "after": base + size,
    }[position]
    if position in ("first", "last"):
        with pytest.raises(model.FactoryCallbackExtendError, match="overlaps"):
            model.apply(**kwargs)
    else:
        assert model.apply(**kwargs)["second"]["vector"]["capacity"] == 2


@pytest.mark.parametrize(
    "failure",
    ["tree", "payload", "copy_id", "inserted", "vector", "grew", "return_word"],
)
def test_actual_extension_operation_corruptions_rejected(monkeypatch, failure):
    kwargs = inputs()
    selected_keys = [
        node["key"] for node in kwargs["second_source_state"]["tree"]["nodes"]
    ]
    original = model.callback.apply
    reached = []

    def mismatch(source_state, destination, vector, **call_kwargs):
        result = original(source_state, destination, vector, **call_kwargs)
        if [node["key"] for node in source_state["tree"]["nodes"]] == selected_keys:
            reached.append(True)
            operation = result["class_operation"]
            if failure == "tree":
                operation["destination"]["tree"]["root"] = 0
            elif failure == "payload":
                operation["destination"]["payloads"][0] ^= 1
            elif failure == "copy_id":
                operation["copies"][0]["destination"] = 0
            elif failure == "inserted":
                operation["copies"][0]["inserted"] = False
            elif failure == "vector":
                operation["vector"]["capacity"] = 3
            elif failure == "grew":
                operation["grew"] = False
            else:
                operation["return_word"] = 1
        return result

    monkeypatch.setattr(model.callback, "apply", mismatch)
    with pytest.raises(
        model.FactoryCallbackExtendError,
        match="extension class operation packet disagrees",
    ):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize(
    "failure",
    [
        "count",
        "field_count",
        "normal_count",
        "sentinel",
        "sentinel_preserved",
        "tree_requests",
        "vector",
        "allocation",
        "free",
        "class_edx",
        "full_return",
    ],
)
def test_repeat_baseline_count_sentinel_heap_and_return_metadata_corruptions_rejected(
    monkeypatch, failure
):
    kwargs = inputs()
    original = model.repeat_model.apply

    def mismatch(**call_kwargs):
        result = original(**call_kwargs)
        second = result["second"]
        if failure == "count":
            second["tree_count"] += 1
        elif failure == "field_count":
            second["field_updates"][56] += 1
        elif failure == "normal_count":
            second["normal_field_updates"][56] += 1
        elif failure == "sentinel":
            second["sentinel_link_ids"]["root"] = None
        elif failure == "sentinel_preserved":
            second["sentinel_preserved_offsets"].pop()
        elif failure == "tree_requests":
            second["tree_heap_requests"] = [dict(bytes=24)]
        elif failure == "vector":
            second["vector"]["capacity"] = 3
        elif failure == "allocation":
            second["vector_heap_request"]["bytes"] = 8
        elif failure == "free":
            second["vector_free_request"]["pointer"] ^= 1
        elif failure == "class_edx":
            second["class_return"]["registers"]["edx"] = 0
        else:
            second["full_return"]["registers"]["esp"] ^= 1
        return result

    monkeypatch.setattr(model.repeat_model, "apply", mismatch)
    with pytest.raises(
        model.FactoryCallbackExtendError, match="repeat baseline .*disagree"
    ):
        model.apply(**kwargs)


@pytest.mark.parametrize("failure", ["registry", "call", "table", "count"])
def test_coordinated_baseline_and_actual_extension_suffix_reaches_independent_contract(
    monkeypatch, failure
):
    kwargs = inputs()
    selected_keys = [
        node["key"] for node in kwargs["second_source_state"]["tree"]["nodes"]
    ]
    repeat_apply, callback_apply = model.repeat_model.apply, model.callback.apply
    contract = model.tree_model._suffix_contract
    reached = dict(baseline=0, actual=0, contract=0)

    def corrupt(packet, baseline):
        if failure == "registry":
            packet["registry_requests"][0]["reference"] ^= 1
        elif failure == "call":
            packet["registry_table_calls" if baseline else "calls"][0]["arguments"][
                1
            ] ^= 1
            if baseline:
                packet["normal_requests"][12]["arguments"][1] ^= 1
        elif failure == "table":
            packet["table_transfers"][0]["api_count"] += 1
        else:
            packet["return_count"] = 1

    def baseline_mismatch(**call_kwargs):
        result = repeat_apply(**call_kwargs)
        reached["baseline"] += 1
        corrupt(result["second"], True)
        return result

    def actual_mismatch(source_state, destination, vector, **call_kwargs):
        result = callback_apply(source_state, destination, vector, **call_kwargs)
        if [node["key"] for node in source_state["tree"]["nodes"]] == selected_keys:
            reached["actual"] += 1
            corrupt(result, False)
        return result

    def observed_contract(suffix, **call_kwargs):
        if [entry["key"] for entry in suffix["class_operation"]["copies"]] == sorted(
            selected_keys
        ):
            reached["contract"] += 1
        return contract(suffix, **call_kwargs)

    monkeypatch.setattr(model.repeat_model, "apply", baseline_mismatch)
    monkeypatch.setattr(model.callback, "apply", actual_mismatch)
    monkeypatch.setattr(model.tree_model, "_suffix_contract", observed_contract)
    with pytest.raises(
        model.FactoryCallbackExtendError,
        match="callback suffix requests disagree with table contract",
    ):
        model.apply(**kwargs)
    assert reached == dict(baseline=1, actual=1, contract=1)


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_shared_semantic_inputs_and_all_detached_output_views():
    kwargs = inputs()
    kwargs["second_source_state"] = kwargs["first_arguments"]["source_state"]
    before = copy.deepcopy(kwargs)
    shared_result = model.apply(**kwargs)
    assert kwargs == before and shared_result["second"]["tree_heap_requests"] == []
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    result, again = model.apply(**kwargs), model.apply(**kwargs)
    assert result == again and kwargs == before
    assert containers(result).isdisjoint(containers(kwargs)) and containers(
        result
    ).isdisjoint(containers(again))
    assert containers(result["first"]).isdisjoint(containers(result["second"]))
    second = result["second"]
    assert containers(second["class_transfer"]).isdisjoint(
        containers(second["callback_operation"])
    )
    second["source_state"]["payloads"][0] ^= 1
    second["callback_operation"]["destination"]["payloads"][0] ^= 1
    second["callback_operation"]["copies"][0]["payload"] ^= 1
    second["callback_operation"]["vector"]["records"][0][1] ^= 1
    assert second["class_transfer"] == again["second"]["class_transfer"]
    assert second["vector"] == again["second"]["vector"]
    second["tree_heap_requests"][0]["bytes"] = 0
    assert second["tree_heap_requests"][1:] == again["second"]["tree_heap_requests"][1:]
    second["sentinel_link_ids"]["root"] = None
    second["normal_requests"][12]["after"].clear()
    assert second["registry_table_calls"] == again["second"]["registry_table_calls"]
    assert (
        result["first"] == again["first"]
        and model.apply(**kwargs) == again
        and kwargs == before
    )
