"""Independent finite-repeat laws, without native callback execution."""

import copy
import itertools

import pytest

from src.observatory import native_lua_class_factory_callback_repeat_semantics as model
from src.observatory import native_tree_balancing_semantics as balancing

KEYS = [0, 1, 7, 99, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF]


def source(keys):
    return dict(
        tree=balancing.from_keys(keys),
        payloads=[
            (0x75310000 ^ index * 0x01010101) & 0xFFFFFFFF for index in range(len(keys))
        ],
    )


def arguments(**changes):
    entry = changes.get("callback_entry", 0x30001030)
    userdata = changes.get("userdata", 0x14000087)
    result = dict(
        source_state=source(KEYS[::-1]),
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


def inputs(first=None, **changes):
    first = arguments() if first is None else first
    first_result = model.tree_model.apply(**first)
    second_entry = changes.get("second_entry", 0x31001037)
    second_source = copy.deepcopy(first["source_state"])
    second_source["payloads"] = [
        payload ^ 0xFFFFFFFF for payload in second_source["payloads"]
    ]
    result = dict(
        first_arguments=first,
        second_source_state=second_source,
        new_vector_pointer=0x0700301F,
        second_entry=second_entry,
        second_registers=dict(
            first_result["full_return"]["registers"], esp=second_entry
        ),
    )
    result.update(changes)
    return result


def check_redblack(tree):
    nodes, visited, inorder = tree["nodes"], set(), []

    def visit(index, parent, low, high):
        if index is None:
            return 1
        assert index not in visited and type(index) is int and 0 <= index < len(nodes)
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


@pytest.mark.parametrize("size", range(8))
@pytest.mark.parametrize("order", ["ascending", "reversed", "alternating"])
@pytest.mark.parametrize("payload_profile", ["same", "zero", "varied"])
def test_existing_key_updates_route_inorder_without_tree_allocations(
    size, order, payload_profile
):
    keys = KEYS[:size]
    if order == "reversed":
        keys = keys[::-1]
    elif order == "alternating":
        keys = keys[::2] + keys[1::2][::-1]
    kwargs = inputs(arguments(source_state=source(keys)))
    second_source = kwargs["second_source_state"]
    if payload_profile == "same":
        second_source["payloads"] = list(
            kwargs["first_arguments"]["source_state"]["payloads"]
        )
    elif payload_profile == "zero":
        second_source["payloads"] = [0] * size
    else:
        second_source["payloads"] = [
            ((index * 0xABCDEF01) ^ 0xFFFFFFFF) & 0xFFFFFFFF for index in range(size)
        ]
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    first, second = result["first"], result["second"]
    assert first == model.tree_model.apply(**kwargs["first_arguments"])
    operation = second["callback_operation"]
    destination = operation["destination"]
    assert destination["tree"] == first["callback_operation"]["destination"]["tree"]
    assert check_redblack(destination["tree"]) == sorted(keys)
    by_key = {key: second_source["payloads"][index] for index, key in enumerate(keys)}
    assert destination["payloads"] == [by_key[key] for key in sorted(keys)]
    assert operation["copies"] == [
        dict(
            source=keys.index(key),
            destination=index,
            key=key,
            inserted=False,
            payload=by_key[key],
        )
        for index, key in enumerate(sorted(keys))
    ]
    assert second["class_transfer"] == dict(
        destination=destination, copies=operation["copies"]
    )
    assert second["tree_count"] == first["tree_count"] == size
    assert second["tree_heap_requests"] == []
    assert second["sentinel_link_ids"] == first["sentinel_link_ids"]
    assert second["sentinel_preserved_offsets"] == list(range(24))
    assert second["source_state"] == second_source and kwargs == before


def test_full_vector_moves_original_record_appends_identical_pair_and_requests_one_free():
    kwargs = inputs()
    result = model.apply(**kwargs)
    first, second = result["first"], result["second"]
    pointer, old, argument = (
        kwargs["new_vector_pointer"],
        kwargs["first_arguments"]["vector_pointer"],
        kwargs["first_arguments"]["source_pointer"],
    )
    assert (
        first["vector"]["records"] == [[0, argument]]
        and first["vector"]["capacity"] == 1
    )
    assert second["callback_operation"]["vector"] == dict(
        records=[[0, argument], [0, argument]], capacity=2
    )
    assert second["callback_operation"]["return_word"] == argument
    assert (
        second["callback_operation"]["argument_kind"] == "external"
        and second["callback_operation"]["grew"] is True
    )
    assert second["vector"] == dict(
        records=[[0, argument], [0, argument]],
        capacity=2,
        begin=pointer,
        end=pointer + 16,
        capacity_pointer=pointer + 16,
    )
    assert second["old_vector_pointer"] == old
    assert second["vector_heap_request"] == dict(
        continuation=0x789463, handle=0x12345678, flags=0, bytes=16
    )
    assert second["vector_free_request"] == dict(
        continuation=0x789172, handle=0x12345678, flags=0, pointer=old
    )
    assert first["vector_heap_request"]["bytes"] == 8
    assert "heap_request" not in second and "record_preserved_size" not in second
    original_record = b"\0" * 4 + argument.to_bytes(4, "little")
    assert (
        b"".join(
            word.to_bytes(4, "little")
            for record in second["vector"]["records"]
            for word in record
        )
        == original_record * 2
    )


@pytest.mark.parametrize("entry", [56, 57, 0x31001037, 0xFFFFFFF8])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_actual_first_return_gprs_second_class_free_volatile_and_full_return(
    entry, cookie
):
    kwargs = inputs(arguments(cookie=cookie), second_entry=entry)
    result = model.apply(**kwargs)
    first, second = result["first"], result["second"]
    assert kwargs["second_registers"] == dict(
        first["full_return"]["registers"], esp=entry
    )
    incoming = kwargs["second_registers"]
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
    original = kwargs["first_arguments"]
    assert second["class_return"] == dict(
        registers=dict(
            eax=original["source_pointer"],
            ebx=original["state"],
            ecx=cookie,
            edx=0xB0000001,
            esi=original["userdata"],
            edi=original["source_pointer"],
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    assert second["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert second["class_caller"]["argument_record"] == [0, original["source_pointer"]]


RECIPES = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
    (["other"] * 3, ["other"] * 3),
]


@pytest.mark.parametrize("first_transfer,second_transfer", RECIPES)
@pytest.mark.parametrize("word", [0, 1, 0x80000000, 0xFFFFFFFF])
def test_word_reference_iterator_premises_requests_and_final_five_values_reused(
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
    result = model.apply(**kwargs)
    first, second = result["first"], result["second"]
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
    assert second["requested_assignments"] == [
        [index for index, kind in enumerate(recipe) if kind == "other"]
        for recipe in (first_transfer, second_transfer)
    ]
    assert second["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert second["source_word"] == second["destination_word"] == word
    assert second["normal_lua_stack_delta"] == 4 and second["return_count"] == 0
    assert all(
        left["after"] == right["before"]
        for left, right in zip(second["normal_requests"], second["normal_requests"][1:])
    )


def test_second_field_updates_preserve_thirteen_words_and_all_sentinel_bytes():
    kwargs = inputs()
    second = model.apply(**kwargs)["second"]
    new, word = kwargs["new_vector_pointer"], kwargs["first_arguments"]["source_word"]
    assert second["normal_field_updates"] == {
        0: word,
        4: new,
        8: new + 16,
        12: new + 16,
        56: 7,
    }
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert (
        second["normal_preserved_userdata_offsets"] == preserved
        and len(preserved) == 13
    )
    assert second["preserved_userdata_offsets"] == [0] + preserved
    assert second["field_updates"] == {4: new, 8: new + 16, 12: new + 16, 56: 7}
    original = bytes((index * 71 + 13) % 256 for index in range(72))
    changed = bytearray(original)
    for offset, value in second["normal_field_updates"].items():
        changed[offset : offset + 4] = value.to_bytes(4, "little")
    assert all(
        changed[offset : offset + 4] == original[offset : offset + 4]
        for offset in preserved
    )
    assert second["sentinel_preserved_offsets"] == list(range(24))


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_every_incoming_second_gpr_must_match_actual_prior_return(register):
    kwargs = inputs()
    kwargs["second_registers"][register] ^= 1
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackRepeatError, match="actual first return"):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field", ["new_vector_pointer", "second_entry", "second_register_word"]
)
@pytest.mark.parametrize("value", [False, True, -1, 2**32, 1.0, "1", None])
def test_strict_new_pointer_entry_and_register_words(field, value):
    kwargs = inputs()
    if field == "second_register_word":
        kwargs["second_registers"]["eax"] = value
    else:
        kwargs[field] = value
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackRepeatError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "kind",
    [
        "first_missing",
        "first_extra",
        "first_tuple",
        "first_eight",
        "register_missing",
        "register_extra",
        "register_tuple",
        "source_schema",
        "payload_bool",
        "payload_wide",
        "payload_count",
        "source_keys",
        "source_order",
        "source_color",
        "source_eight",
        "entry_below_cookie",
        "entry_wrap",
        "new_zero",
        "new_wrap",
    ],
)
def test_strict_first_second_state_topology_schema_and_extents(kind):
    kwargs = inputs()
    if kind == "first_missing":
        kwargs["first_arguments"].pop("state")
    elif kind == "first_extra":
        kwargs["first_arguments"]["extra"] = 0
    elif kind == "first_tuple":
        kwargs["first_arguments"] = tuple(kwargs["first_arguments"].items())
    elif kind == "first_eight":
        kwargs["first_arguments"]["source_state"] = source(list(range(8)))
    elif kind == "register_missing":
        kwargs["second_registers"].pop("eax")
    elif kind == "register_extra":
        kwargs["second_registers"]["extra"] = 0
    elif kind == "register_tuple":
        kwargs["second_registers"] = tuple(kwargs["second_registers"].items())
    elif kind == "source_schema":
        kwargs["second_source_state"]["extra"] = 0
    elif kind == "payload_bool":
        kwargs["second_source_state"]["payloads"][0] = True
    elif kind == "payload_wide":
        kwargs["second_source_state"]["payloads"][0] = 2**32
    elif kind == "payload_count":
        kwargs["second_source_state"]["payloads"].pop()
    elif kind == "source_keys":
        kwargs["second_source_state"] = source([0, 1, 2, 3, 4, 5, 6])
    elif kind == "source_order":
        kwargs["second_source_state"] = source(KEYS)
    elif kind == "source_color":
        kwargs["second_source_state"]["tree"]["nodes"][0]["color"] = False
    elif kind == "source_eight":
        kwargs["second_source_state"] = source(list(range(8)))
    elif kind == "entry_below_cookie":
        kwargs["second_entry"] = kwargs["second_registers"]["esp"] = 55
    elif kind == "entry_wrap":
        kwargs["second_entry"] = kwargs["second_registers"]["esp"] = 0xFFFFFFF9
    elif kind == "new_zero":
        kwargs["new_vector_pointer"] = 0
    else:
        kwargs["new_vector_pointer"] = 0xFFFFFFF0
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackRepeatError):
        model.apply(**kwargs)
    assert kwargs == before
    assert issubclass(
        model.FactoryCallbackRepeatError, model.tree_model.FactoryCallbackTreeError
    )


@pytest.mark.parametrize(
    "target", ["old_vector", "userdata", "sentinel", "source", "second_frame"]
)
@pytest.mark.parametrize("position", ["before", "first", "last", "after"])
def test_new_sixteen_bytes_disjoint_from_every_live_extent_and_exact_adjacency(
    target, position
):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    spans = dict(
        old_vector=(first["vector_pointer"], 8),
        userdata=(first["userdata"], 72),
        sentinel=(first["record_pointer"], 24),
        source=(first["source_pointer"], 72),
        second_frame=(kwargs["second_entry"] - 48, 56),
    )
    base, size = spans[target]
    kwargs["new_vector_pointer"] = {
        "before": base - 16,
        "first": base,
        "last": base + size - 1,
        "after": base + size,
    }[position]
    if position in ("first", "last"):
        with pytest.raises(model.FactoryCallbackRepeatError, match="overlaps"):
            model.apply(**kwargs)
    else:
        assert model.apply(**kwargs)["second"]["vector"]["capacity"] == 2


@pytest.mark.parametrize("offset", [-48, -47, -41])
def test_old_vector_cannot_overlap_second_callback_frame(offset):
    kwargs = inputs()
    kwargs["second_entry"] = kwargs["first_arguments"]["vector_pointer"] - offset
    kwargs["second_registers"]["esp"] = kwargs["second_entry"]
    with pytest.raises(model.FactoryCallbackRepeatError, match="old vector overlaps"):
        model.apply(**kwargs)


@pytest.mark.parametrize("new", [1, 0xFFFFFFEF])
def test_new_vector_nonwrapping_boundary_values_admitted(new):
    kwargs = inputs(new_vector_pointer=new)
    assert model.apply(**kwargs)["second"]["vector"]["capacity_pointer"] == new + 16


def test_host_can_reuse_first_entry_frame_and_shared_python_source_objects():
    kwargs = inputs()
    first = kwargs["first_arguments"]
    kwargs["second_entry"] = first["callback_entry"]
    kwargs["second_registers"]["esp"] = first["callback_entry"]
    kwargs["second_source_state"] = first["source_state"]
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    assert result["second"]["source_state"] == result["first"]["source_state"]
    assert kwargs == before
    kwargs["second_source_state"] = dict(
        tree=first["source_state"]["tree"], payloads=[0] * 7
    )
    assert (
        model.apply(**kwargs)["second"]["callback_operation"]["destination"]["payloads"]
        == [0] * 7
    )


@pytest.mark.parametrize(
    "failure",
    [
        "vector",
        "grew",
        "copy_inserted",
        "copy_source",
        "payload",
        "tree",
        "return_word",
        "suffix",
    ],
)
def test_inconsistent_second_operation_and_coordinated_suffix_rejected(
    monkeypatch, failure
):
    kwargs = inputs()
    original = model.callback.apply

    def mismatch(source_state, destination, vector, **call_kwargs):
        result = original(source_state, destination, vector, **call_kwargs)
        if failure == "suffix" and len(vector["records"]) == 1:
            result["registry_requests"][0]["reference"] ^= 1
        elif len(vector["records"]) == 1:
            operation = result["class_operation"]
            if failure == "vector":
                operation["vector"]["capacity"] = 3
            elif failure == "grew":
                operation["grew"] = False
            elif failure == "copy_inserted":
                operation["copies"][0]["inserted"] = True
            elif failure == "copy_source":
                operation["copies"][0]["source"] = 0
            elif failure == "payload":
                operation["destination"]["payloads"][0] ^= 1
            elif failure == "tree":
                operation["destination"]["tree"]["root"] = 0
            else:
                operation["return_word"] = 1
        return result

    monkeypatch.setattr(model.callback, "apply", mismatch)
    with pytest.raises(model.FactoryCallbackRepeatError, match="disagree"):
        model.apply(**kwargs)


@pytest.mark.parametrize("failure", ["registry", "call", "table", "count"])
def test_coordinated_second_baseline_and_callback_suffix_reach_contract_rejection(
    monkeypatch, failure
):
    kwargs = inputs()
    baseline_apply = model.tree_model.full_return_model.apply
    callback_apply = model.callback.apply
    suffix_contract = model.tree_model._suffix_contract
    reached = dict(baseline=0, callback=0, contract=0)

    def corrupt(result, *, baseline):
        if failure == "registry":
            result["registry_requests"][0]["reference"] ^= 1
        elif failure == "call":
            result["registry_table_calls" if baseline else "calls"][0]["arguments"][
                1
            ] ^= 1
            if baseline:
                result["normal_requests"][12]["arguments"][1] ^= 1
        elif failure == "table":
            result["table_transfers"][0]["api_count"] += 1
        else:
            result["return_count"] = 1

    def baseline_mismatch(**call_kwargs):
        result = baseline_apply(**call_kwargs)
        if call_kwargs["callback_entry"] == kwargs["second_entry"]:
            reached["baseline"] += 1
            corrupt(result, baseline=True)
        return result

    def callback_mismatch(source_state, destination, vector, **call_kwargs):
        result = callback_apply(source_state, destination, vector, **call_kwargs)
        if len(vector["records"]) == 1:
            reached["callback"] += 1
            corrupt(result, baseline=False)
        return result

    def observed_contract(suffix, **call_kwargs):
        if len(suffix["class_operation"]["vector"]["records"]) == 2:
            reached["contract"] += 1
        return suffix_contract(suffix, **call_kwargs)

    monkeypatch.setattr(model.tree_model.full_return_model, "apply", baseline_mismatch)
    monkeypatch.setattr(model.callback, "apply", callback_mismatch)
    monkeypatch.setattr(model.tree_model, "_suffix_contract", observed_contract)
    with pytest.raises(
        model.FactoryCallbackRepeatError,
        match="callback suffix requests disagree with table contract",
    ):
        model.apply(**kwargs)
    assert reached == dict(baseline=1, callback=1, contract=1)


def containers(value):
    result = set()
    if type(value) in (dict, list):
        result.add(id(value))
        for child in value.values() if type(value) is dict else value:
            result.update(containers(child))
    return result


def test_all_input_output_repeated_results_and_parallel_packet_views_detached():
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    first, again = model.apply(**kwargs), model.apply(**kwargs)
    assert first == again and kwargs == before
    assert containers(first).isdisjoint(containers(kwargs))
    assert containers(first).isdisjoint(containers(again))
    assert containers(first["first"]).isdisjoint(containers(first["second"]))
    second = first["second"]
    assert containers(second["class_transfer"]).isdisjoint(
        containers(second["callback_operation"])
    )
    second["source_state"]["payloads"][0] ^= 1
    second["callback_operation"]["destination"]["payloads"][0] ^= 1
    second["callback_operation"]["vector"]["records"][0][1] ^= 1
    assert second["vector"] == again["second"]["vector"]
    assert second["class_transfer"] == again["second"]["class_transfer"]
    second["normal_requests"][12]["after"].clear()
    assert second["registry_table_calls"] == again["second"]["registry_table_calls"]
    second["vector_free_request"]["pointer"] ^= 1
    second["sentinel_link_ids"]["root"] = None
    second["sentinel_preserved_offsets"].clear()
    assert first["first"] == again["first"]
    assert model.apply(**kwargs) == again and kwargs == before
