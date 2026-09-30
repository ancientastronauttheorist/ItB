"""Standalone callback laws, with no native callback instruction oracle."""

import copy
import itertools

import pytest
from src.observatory import native_lua_class_callback_semantics as callback
from src.observatory import native_tree_balancing_semantics as balancing


def state(keys, payload_base):
    return dict(
        tree=balancing.from_keys(keys),
        payloads=[payload_base + i for i in range(len(keys))],
    )


def values(obj):
    return {node["key"]: obj["payloads"][i] for i, node in enumerate(obj["tree"]["nodes"])}


def inputs():
    return dict(
        source=state([5, 1, 3], 100),
        destination=state([4, 3, 2], 200),
        vector=dict(records=[[9, 90]], capacity=3),
        source_pointer=0x12345678,
        source_word=0xFEDCBA98,
        destination_word=0x87654321,
        destination_refs=[11, 22],
        source_refs=[33, 44],
        transfers=[["init", "other", "finalize"], ["other", "finalize", "other"]],
    )


VECTOR_DOMAINS = [(size, capacity) for size in range(4) for capacity in range(size + 1, 6)]


@pytest.mark.parametrize("size,capacity", VECTOR_DOMAINS)
@pytest.mark.parametrize(
    "source_keys,destination_keys",
    [([], [2]), ([1, 3], [2, 4]), ([3, 1], [1, 3]), ([5, 1, 3], [4, 3, 2])],
)
def test_tree_overwrite_and_original_external_record_append(size, capacity, source_keys, destination_keys):
    args = inputs()
    args["source"] = state(source_keys, 100)
    args["destination"] = state(destination_keys, 200)
    args["vector"] = dict(records=[[i, 10 + i] for i in range(size)], capacity=capacity)
    before = copy.deepcopy(args)
    result = callback.apply(**args)
    operation = result["class_operation"]
    assert values(operation["destination"]) == {
        **values(args["destination"]), **values(args["source"])
    }
    assert [item["key"] for item in operation["copies"]] == sorted(source_keys)
    assert [item["inserted"] for item in operation["copies"]] == [
        key not in destination_keys for key in sorted(source_keys)
    ]
    assert operation["vector"] == dict(
        records=args["vector"]["records"] + [[0, args["source_pointer"]]], capacity=capacity
    )
    assert operation["argument_kind"] == "external" and operation["grew"] is False
    assert operation["return_word"] == args["source_pointer"]
    assert result["destination_word"] == args["source_word"]
    assert result["return_count"] == 0
    assert args == before


def test_all_bounded_transfer_pairs_preserve_prefix_and_filter_assignments():
    sequences = [list(items) for length in range(4)
                 for items in itertools.product(("init", "finalize", "other"), repeat=length)]
    args = inputs()
    args["source"], args["destination"] = state([], 0), state([], 0)
    for first, second in itertools.product(sequences, repeat=2):
        args["transfers"] = [first, second]
        before = copy.deepcopy(args)
        result = callback.apply(**args)
        assert result["initial_lua_stack"] == [("argument", 0)]
        assert result["final_lua_stack"] == [
            ("argument", 0), ("registry", 11), ("registry", 33),
            ("registry", 22), ("registry", 44),
        ]
        assert result["lua_stack_delta"] == 4 and result["return_count"] == 0
        assert result["requested_assignments"] == [
            [i for i, kind in enumerate(sequence) if kind == "other"]
            for sequence in (first, second)
        ]
        for index, transfer in enumerate(result["table_transfers"]):
            prefix_size = 1 + 2 * index
            assert transfer["initial"] == transfer["final"]
            assert transfer["initial"] == result["final_lua_stack"][:prefix_size + 2]
            assert transfer["lua_stack_delta"] == 0
            assert transfer["api_count"] == 2 + sum(
                {"init": 4, "finalize": 7, "other": 10}[kind] for kind in (first, second)[index]
            )
            for call in transfer["calls"]:
                assert call["before"][:prefix_size] == result["final_lua_stack"][:prefix_size]
                assert call["after"][:prefix_size] == result["final_lua_stack"][:prefix_size]
        calls = result["calls"]
        assert calls[0]["before"] == result["initial_lua_stack"]
        assert calls[-1]["after"] == result["final_lua_stack"]
        assert all(left["after"] == right["before"] for left, right in zip(calls, calls[1:]))
        assert args == before


def test_registry_requests_and_transfer_order():
    result = callback.apply(**inputs())
    assert result["registry_requests"] == [
        dict(role=role, field_offset=offset, reference=reference, arguments=[-10000, reference])
        for role, offset, reference in [
            ("destination", 32, 11), ("source", 32, 33),
            ("destination", 40, 22), ("source", 40, 44),
        ]
    ]
    calls = result["calls"]
    raw_indices = [i for i, call in enumerate(calls) if call["api"] == "lua_rawgeti"]
    first_count = result["table_transfers"][0]["api_count"]
    assert raw_indices == [0, 1, first_count + 2, first_count + 3]
    assert calls[2:first_count + 2] == result["table_transfers"][0]["calls"]
    assert calls[first_count + 4:] == result["table_transfers"][1]["calls"]


def test_detachment_across_inputs_outputs_and_repeated_calls():
    args = inputs()
    before = copy.deepcopy(args)
    first = callback.apply(**args)
    second = callback.apply(**args)
    assert first == second
    untouched = copy.deepcopy(second)
    first["class_operation"]["destination"]["payloads"][0] = 0
    first["class_operation"]["vector"]["records"][0][0] = 0
    first["class_operation"]["vector"]["records"][-1][1] = 0
    first["registry_requests"][0]["arguments"][0] = 0
    first["requested_assignments"][0].append(99)
    first["initial_lua_stack"][0] = ("changed",)
    first["calls"][2]["after"][0] = ("changed",)
    first["table_transfers"][0]["initial"][0] = ("changed",)
    assert args == before and second == untouched
    assert first["final_lua_stack"] == second["final_lua_stack"]
    assert first["table_transfers"][0]["assignments"] == [1]
    assert first["table_transfers"][0]["calls"][0]["after"][0] == ("argument", 0)
    assert first["calls"][3]["before"][0] == ("argument", 0)


@pytest.mark.parametrize("value", [False, True, -1, 2**32, 1.0, "1", None])
@pytest.mark.parametrize("field", ["source_pointer", "source_word", "destination_word", "destination_ref", "source_ref"])
def test_strict_uint32_guards(field, value):
    args = inputs()
    if field in ("source_ref", "destination_ref"):
        args[field.removesuffix("_ref") + "_refs"][0] = value
    else:
        args[field] = value
    before = copy.deepcopy(args)
    with pytest.raises(callback.CallbackError):
        callback.apply(**args)
    assert args == before


@pytest.mark.parametrize("word", [0, 0xFFFFFFFF])
def test_boundary_words_and_refs_are_permitted(word):
    args = inputs()
    args.update(source_pointer=0xFFFFFFFF, source_word=word, destination_word=word,
                destination_refs=[word, word], source_refs=[word, word])
    result = callback.apply(**args)
    assert result["destination_word"] == word
    assert result["final_lua_stack"][1:] == [("registry", word)] * 4


@pytest.mark.parametrize("kind", [
    "null_source", "short_dest_refs", "tuple_source_refs", "long_source_refs",
    "tuple_transfers", "one_transfer", "three_transfers", "tuple_kinds", "long_kinds",
    "unknown_kind", "bool_kind", "vector_schema", "tuple_records", "too_many_records",
    "no_spare_capacity", "zero_capacity", "wide_capacity", "bool_capacity",
    "short_record", "tuple_record", "bool_record_word", "wide_record_word",
    "same_classes", "shared_tree", "shared_payloads", "shared_vector_payloads",
    "bad_source_schema", "bad_destination_payload", "bad_source_tree",
])
def test_invalid_or_unproved_domain_rejected_without_mutation(kind):
    args = inputs()
    if kind == "null_source": args["source_pointer"] = 0
    elif kind == "short_dest_refs": args["destination_refs"] = [1]
    elif kind == "tuple_source_refs": args["source_refs"] = (1, 2)
    elif kind == "long_source_refs": args["source_refs"] = [1, 2, 3]
    elif kind == "tuple_transfers": args["transfers"] = ([], [])
    elif kind == "one_transfer": args["transfers"] = [[]]
    elif kind == "three_transfers": args["transfers"] = [[], [], []]
    elif kind == "tuple_kinds": args["transfers"][0] = ()
    elif kind == "long_kinds": args["transfers"][0] = ["other"] * 4
    elif kind == "unknown_kind": args["transfers"][0] = ["unknown"]
    elif kind == "bool_kind": args["transfers"][0] = [True]
    elif kind == "vector_schema": args["vector"]["extra"] = 0
    elif kind == "tuple_records": args["vector"]["records"] = ()
    elif kind == "too_many_records": args["vector"].update(records=[[0, 1]] * 4, capacity=5)
    elif kind == "no_spare_capacity": args["vector"]["capacity"] = 1
    elif kind == "zero_capacity": args["vector"]["capacity"] = 0
    elif kind == "wide_capacity": args["vector"]["capacity"] = 6
    elif kind == "bool_capacity": args["vector"]["capacity"] = True
    elif kind == "short_record": args["vector"]["records"] = [[1]]
    elif kind == "tuple_record": args["vector"]["records"] = [(1, 2)]
    elif kind == "bool_record_word": args["vector"]["records"][0][0] = True
    elif kind == "wide_record_word": args["vector"]["records"][0][1] = 2**32
    elif kind == "same_classes": args["destination"] = args["source"]
    elif kind == "shared_tree": args["destination"]["tree"] = args["source"]["tree"]
    elif kind == "shared_payloads": args["destination"]["payloads"] = args["source"]["payloads"]
    elif kind == "shared_vector_payloads": args["vector"]["records"] = args["source"]["payloads"]
    elif kind == "bad_source_schema": args["source"]["extra"] = 0
    elif kind == "bad_destination_payload": args["destination"]["payloads"][0] = True
    else: args["source"]["tree"]["nodes"][0]["color"] = False
    before = copy.deepcopy(args)
    with pytest.raises(callback.CallbackError):
        callback.apply(**args)
    assert args == before
