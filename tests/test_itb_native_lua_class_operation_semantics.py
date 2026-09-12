"""Independent class-operation model and projections from bounded native oracles."""

import copy
import pytest
from src.observatory import native_lua_class_operation_semantics as c
from src.observatory import native_tree_balancing_semantics as balancing


def state(keys, base):
    return dict(
        tree=balancing.from_keys(keys), payloads=[base + i for i in range(len(keys))]
    )


def values(state):
    return {
        n["key"]: state["payloads"][i] for i, n in enumerate(state["tree"]["nodes"])
    }


@pytest.mark.parametrize("index", [None, 0, 1, 2])
@pytest.mark.parametrize("capacity", [3, 4, 9])
def test_selected_record_tree_union_and_detached_results(index, capacity):
    source, dest = state([5, 1, 3], 100), state([4, 3, 2], 200)
    vector = dict(records=[[1, 10], [2, 20], [3, 30]], capacity=capacity)
    selected = [7, 70] if index is None else vector["records"][index]
    before = copy.deepcopy((source, dest, vector, selected))
    options = dict(argument=selected) if index is None else dict(argument_index=index)
    result = c.apply(source, dest, vector, **options)
    assert values(result["destination"]) == {**values(dest), **values(source)}
    assert [row["key"] for row in result["copies"]] == [1, 3, 5]
    assert [row["inserted"] for row in result["copies"]] == [True, False, True]
    assert result["vector"] == dict(
        records=vector["records"] + [selected],
        capacity=4 if capacity == 3 else capacity,
    )
    assert result["grew"] == (capacity == 3) and result["return_word"] == selected[1]
    assert (source, dest, vector, selected) == before
    result["vector"]["records"][0][0] ^= 1
    result["vector"]["records"][-1][1] ^= 1
    result["destination"]["payloads"][0] ^= 1
    assert (source, dest, vector, selected) == before


@pytest.mark.parametrize("size", range(4))
def test_proven_growth_and_spare_capacities(size):
    assert c.next_capacity(size, size) == size + 1
    assert c.next_capacity(size, size + 1) == size + 1
    assert c.next_capacity(size, 9) == 9


@pytest.mark.parametrize(
    "size,capacity",
    [
        (True, 1),
        (0, True),
        (-1, 0),
        (2, 1),
        (4, 4),
        (0, 0x10000000),
        (0x10000000, 0x10000000),
        (c.MAX_CAPACITY, c.MAX_CAPACITY),
    ],
)
def test_unproved_or_malformed_capacity_rejected(size, capacity):
    with pytest.raises(c.OperationError):
        c.next_capacity(size, capacity)


def test_ordinary_signed_span_spare_boundary():
    assert c.next_capacity(c.MAX_CAPACITY - 1, c.MAX_CAPACITY) == c.MAX_CAPACITY


@pytest.mark.parametrize(
    "kind",
    [
        "vector_schema",
        "records_type",
        "short_record",
        "tuple_record",
        "bool_word",
        "negative_word",
        "wide_word",
        "missing_argument",
        "both_arguments",
        "bool_index",
        "negative_index",
        "large_index",
        "zero_source",
        "internal_zero_source",
    ],
)
def test_invalid_input_preserves_all_states(kind):
    source, dest = state([1], 10), state([2], 20)
    vector = dict(records=[[1, 10]], capacity=2)
    options = dict(argument=[7, 70])
    if kind == "vector_schema":
        vector["extra"] = 0
    elif kind == "records_type":
        vector["records"] = ()
    elif kind == "short_record":
        vector["records"] = [[1]]
    elif kind == "tuple_record":
        vector["records"] = [(1, 10)]
    elif kind == "bool_word":
        vector["records"][0][0] = True
    elif kind == "negative_word":
        vector["records"][0][0] = -1
    elif kind == "wide_word":
        vector["records"][0][0] = 2**32
    elif kind == "missing_argument":
        options = {}
    elif kind == "both_arguments":
        options["argument_index"] = 0
    elif kind == "bool_index":
        options = dict(argument_index=True)
    elif kind == "negative_index":
        options = dict(argument_index=-1)
    elif kind == "large_index":
        options = dict(argument_index=1)
    elif kind == "zero_source":
        options = dict(argument=[1, 0])
    else:
        vector["records"][0][1] = 0
        options = dict(argument_index=0)
    before = copy.deepcopy((source, dest, vector, options))
    with pytest.raises(c.OperationError):
        c.apply(source, dest, vector, **options)
    assert (source, dest, vector, options) == before


def read(pages, a, width=4):
    return sum(pages[(a + i) & ~4095][(a + i) & 4095] << (8 * i) for i in range(width))


@pytest.mark.parametrize(
    "name",
    [
        "native_lua_class_spare_return_conformance",
        "native_lua_class_empty_vector_return_conformance",
        "native_lua_class_old_vector_return_conformance",
        "native_lua_class_internal_spare_return_conformance",
        "native_lua_class_internal_growth_return_conformance",
    ],
)
def test_logical_model_matches_native_oracle_projections(name):
    import importlib

    module = importlib.import_module("src.observatory." + name)
    corpus = module.vectors()
    chosen = []
    for profile in ("empty_source", "all_new", "all_existing", "mixed"):
        group = [v for v in corpus if v["profile"] == profile]
        chosen.extend(group[:1] + group[-1:])
    for v in chosen:
        fixture = module._fixture(v)
        expected = module._expected(v, fixture)
        before = fixture["pages"]
        after = expected["pages"]
        receiver = module.RECEIVER
        begin, end, cap = [read(before, receiver + i) for i in (4, 8, 12)]
        records = [[read(before, a), read(before, a + 4)] for a in range(begin, end, 8)]
        vector = dict(records=records, capacity=(cap - begin) // 8)
        argument = module.ARGUMENT
        options = (
            dict(argument_index=(argument - begin) // 8)
            if begin <= argument < end
            else dict(argument=[read(before, argument), read(before, argument + 4)])
        )
        result = c.apply(
            fixture["source_state"], fixture["destination_state"], vector, **options
        )
        final_begin, final_end, final_cap = [
            read(after, receiver + i) for i in (4, 8, 12)
        ]
        actual_records = [
            [read(after, a), read(after, a + 4)]
            for a in range(final_begin, final_end, 8)
        ]
        assert result["vector"] == dict(
            records=actual_records, capacity=(final_cap - final_begin) // 8
        )
        assert result["return_word"] == expected["registers"]["eax"]
        assert result["destination"] == fixture["transfer"]["destination"]
        assert len(result["copies"]) == len(expected["insertions"])
