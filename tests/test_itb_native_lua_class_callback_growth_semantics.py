"""Opt-in external small-vector growth leaves callback request laws unchanged."""

import copy

import pytest
from src.observatory import native_lua_class_callback_semantics as callback
from src.observatory import native_tree_balancing_semantics as balancing

TREES = [([], [2]), ([1, 3], [2, 4]), ([3, 1], [1, 3]), ([5, 1, 3], [4, 3, 2])]
TRANSFERS = [
    [[], ["other", "finalize", "init"]],
    [["init", "other", "finalize"], ["other", "other"]],
    [["finalize"], ["init", "finalize"]],
]
SPARE_STATES = [
    (size, capacity) for size in range(4) for capacity in range(size + 1, 6)
]


def state(keys, payload_base):
    return dict(
        tree=balancing.from_keys(keys),
        payloads=[payload_base + i for i in range(len(keys))],
    )


def inputs(size=3, *, capacity=None, keys=TREES[-1], transfers=TRANSFERS[1]):
    return dict(
        source=state(keys[0], 100),
        destination=state(keys[1], 200),
        vector=dict(
            records=[[i + 1, 90 + i] for i in range(size)],
            capacity=size if capacity is None else capacity,
        ),
        source_pointer=0x12345678,
        source_word=0xFEDCBA98,
        destination_word=0x87654321,
        destination_refs=[11, 22],
        source_refs=[33, 44],
        transfers=copy.deepcopy(transfers),
    )


def values(obj):
    return {
        node["key"]: obj["payloads"][i] for i, node in enumerate(obj["tree"]["nodes"])
    }


def assert_lua_contract(result, transfers):
    assert result["initial_lua_stack"] == [("argument", 0)]
    assert result["final_lua_stack"] == [
        ("argument", 0),
        ("registry", 11),
        ("registry", 33),
        ("registry", 22),
        ("registry", 44),
    ]
    assert result["return_count"] == 0 and result["lua_stack_delta"] == 4
    assert result["requested_assignments"] == [
        [i for i, kind in enumerate(kinds) if kind == "other"] for kinds in transfers
    ]
    assert [
        (r["field_offset"], r["role"], r["reference"], r["arguments"])
        for r in result["registry_requests"]
    ] == [
        (32, "destination", 11, [-10000, 11]),
        (32, "source", 33, [-10000, 33]),
        (40, "destination", 22, [-10000, 22]),
        (40, "source", 44, [-10000, 44]),
    ]
    calls = result["calls"]
    assert all(
        left["after"] == right["before"] for left, right in zip(calls, calls[1:])
    )
    assert calls[0]["before"] == result["initial_lua_stack"]
    assert calls[-1]["after"] == result["final_lua_stack"]
    for index, transfer in enumerate(result["table_transfers"]):
        prefix_length = 1 + 2 * index
        assert (
            transfer["initial"]
            == transfer["final"]
            == result["final_lua_stack"][: prefix_length + 2]
        )
        assert transfer["lua_stack_delta"] == 0
        assert transfer["api_count"] == 2 + sum(
            {"init": 4, "finalize": 7, "other": 10}[kind] for kind in transfers[index]
        )
        for call in transfer["calls"]:
            assert (
                call["before"][:prefix_length]
                == call["after"][:prefix_length]
                == result["final_lua_stack"][:prefix_length]
            )


@pytest.mark.parametrize("size", range(4))
@pytest.mark.parametrize("keys", TREES)
@pytest.mark.parametrize("transfers", TRANSFERS)
def test_all_full_sizes_tree_profiles_and_asymmetric_tables(size, keys, transfers):
    args = inputs(size, keys=keys, transfers=transfers)
    before = copy.deepcopy(args)
    result = callback.apply(**args, allow_growth=True)
    operation = result["class_operation"]
    # Independent closed capacities on the bounded full-vector domain.
    assert operation["vector"] == dict(
        records=before["vector"]["records"] + [[0, args["source_pointer"]]],
        capacity=(1, 2, 3, 4)[size],
    )
    assert operation["grew"] is True and operation["argument_kind"] == "external"
    assert operation["return_word"] == args["source_pointer"]
    assert values(operation["destination"]) == {
        **values(args["destination"]),
        **values(args["source"]),
    }
    assert [item["key"] for item in operation["copies"]] == sorted(keys[0])
    assert [item["inserted"] for item in operation["copies"]] == [
        key not in keys[1] for key in sorted(keys[0])
    ]
    assert result["destination_word"] == args["source_word"]
    assert_lua_contract(result, transfers)
    assert args == before
    spare_args = dict(
        args,
        vector=dict(
            records=copy.deepcopy(args["vector"]["records"]), capacity=size + 1
        ),
    )
    spare = callback.apply(**spare_args)
    spare["class_operation"]["grew"] = True
    assert result == spare


@pytest.mark.parametrize("size,capacity", SPARE_STATES)
@pytest.mark.parametrize("keys", TREES)
@pytest.mark.parametrize("transfers", TRANSFERS)
def test_every_normal_spare_state_opt_in_matches_default(
    size, capacity, keys, transfers
):
    args = inputs(size, capacity=capacity, keys=keys, transfers=transfers)
    before = copy.deepcopy(args)
    result = callback.apply(**args, allow_growth=True)
    assert (
        result == callback.apply(**args) == callback.apply(**args, allow_growth=False)
    )
    assert result["class_operation"]["grew"] is False
    assert result["class_operation"]["vector"]["capacity"] == capacity
    assert args == before


@pytest.mark.parametrize("size", range(4))
@pytest.mark.parametrize("explicit", [False, True])
def test_default_rejects_full_vectors_with_existing_error(size, explicit):
    args = inputs(size)
    before = copy.deepcopy(args)
    keywords = {"allow_growth": False} if explicit else {}
    with pytest.raises(
        callback.CallbackError,
        match="external vector must have at most three live records and spare capacity <=5",
    ):
        callback.apply(**args, **keywords)
    assert args == before


@pytest.mark.parametrize(
    "value", [None, 0, 1, -1, 2, 0.0, 1.0, "true", "false", [], {}, ()]
)
def test_allow_growth_requires_strict_boolean(value):
    args = inputs()
    before = copy.deepcopy(args)
    with pytest.raises(callback.CallbackError, match="allow_growth must be bool"):
        callback.apply(**args, allow_growth=value)
    assert args == before


@pytest.mark.parametrize("size", range(4))
def test_growth_results_detached_from_inputs_and_other_calls(size):
    args = inputs(size)
    before = copy.deepcopy(args)
    first = callback.apply(**args, allow_growth=True)
    second = callback.apply(**args, allow_growth=True)
    untouched = copy.deepcopy(second)
    first["class_operation"]["vector"]["records"][-1][0] = 99
    if size:
        first["class_operation"]["vector"]["records"][0][0] = 99
    first["class_operation"]["destination"]["payloads"][0] = 0
    first["class_operation"]["copies"][0]["payload"] = 0
    first["registry_requests"][0]["arguments"][0] = 0
    first["calls"][2]["after"][0] = ("changed",)
    first["table_transfers"][0]["initial"][0] = ("changed",)
    first["requested_assignments"][0].append(99)
    assert args == before and second == untouched
    assert first["final_lua_stack"] == second["final_lua_stack"]
    assert first["table_transfers"][0]["assignments"] == [1]
    assert first["table_transfers"][0]["calls"][0]["after"][0] == ("argument", 0)


@pytest.mark.parametrize(
    "mutation",
    [
        "same_classes",
        "shared_tree",
        "shared_node",
        "shared_payloads",
        "shared_vector_payloads",
    ],
)
def test_growth_keeps_mutable_domains_disjoint(mutation):
    args = inputs()
    if mutation == "same_classes":
        args["destination"] = args["source"]
    elif mutation == "shared_tree":
        args["destination"]["tree"] = args["source"]["tree"]
    elif mutation == "shared_node":
        args["destination"]["tree"]["nodes"][0] = args["source"]["tree"]["nodes"][0]
    elif mutation == "shared_payloads":
        args["destination"]["payloads"] = args["source"]["payloads"]
    else:
        args["vector"]["records"] = args["source"]["payloads"]
    before = copy.deepcopy(args)
    with pytest.raises(
        callback.CallbackError,
        match="class and vector representations must be disjoint",
    ):
        callback.apply(**args, allow_growth=True)
    assert args == before


@pytest.mark.parametrize(
    "mutation",
    [
        "negative_capacity",
        "bool_capacity",
        "under_capacity",
        "wide_capacity",
        "too_many_records",
        "extra_vector_field",
        "tuple_records",
        "tuple_record",
        "short_record",
        "bool_record",
        "wide_record",
        "null_pointer",
        "internal_index",
        "unknown_transfer",
    ],
)
def test_growth_does_not_expand_other_input_contracts(mutation):
    args = inputs()
    vector = args["vector"]
    if mutation == "negative_capacity":
        vector["capacity"] = -1
    elif mutation == "bool_capacity":
        vector["capacity"] = True
    elif mutation == "under_capacity":
        vector["capacity"] = 2
    elif mutation == "wide_capacity":
        vector["capacity"] = 6
    elif mutation == "too_many_records":
        vector.update(records=[[0, 1]] * 4, capacity=4)
    elif mutation == "extra_vector_field":
        vector["extra"] = 0
    elif mutation == "tuple_records":
        vector["records"] = tuple(vector["records"])
    elif mutation == "tuple_record":
        vector["records"][0] = (1, 2)
    elif mutation == "short_record":
        vector["records"][0] = [1]
    elif mutation == "bool_record":
        vector["records"][0][0] = True
    elif mutation == "wide_record":
        vector["records"][0][1] = 2**32
    elif mutation == "null_pointer":
        args["source_pointer"] = 0
    elif mutation == "internal_index":
        vector["argument_index"] = 0
    else:
        args["transfers"][0][0] = "unknown"
    before = copy.deepcopy(args)
    with pytest.raises(callback.CallbackError):
        callback.apply(**args, allow_growth=True)
    assert args == before
