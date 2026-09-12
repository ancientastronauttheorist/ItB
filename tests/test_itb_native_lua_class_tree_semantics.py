"""Independent key union and unconditional source-payload replacement."""

import copy
import pytest
from src.observatory import native_lua_class_tree_semantics as c


def state(keys, seed=0):
    return dict(
        tree=c.balancing.from_keys(keys),
        payloads=[(seed + 13 * i) & 0xFFFFFFFF for i in range(len(keys))],
    )


def mapping(s):
    return {n["key"]: s["payloads"][i] for i, n in enumerate(s["tree"]["nodes"])}


@pytest.mark.parametrize(
    "source_keys,dest_keys",
    [
        ([], []),
        ([], [3, 1, 5]),
        ([3, 1, 5], []),
        ([3, 1, 5], [5, 3, 1]),
        ([7, 1, 5, 3], [2, 3, 6, 5]),
        ([0xFFFFFFFF, 0, 0x80000000], [0, 1]),
        (list(reversed(range(31))), list(range(15, 48))),
    ],
)
def test_key_union_payload_precedence_and_immutable_inputs(source_keys, dest_keys):
    source = state(source_keys, 0xF0000000)
    dest = state(dest_keys, 0x10000000)
    before = copy.deepcopy((source, dest))
    result = c.transfer(source, dest)
    assert (source, dest) == before
    expected = dict(mapping(dest))
    expected.update(mapping(source))
    assert mapping(result["destination"]) == expected
    assert [row["key"] for row in result["copies"]] == sorted(source_keys)
    assert sum(row["inserted"] for row in result["copies"]) == len(
        set(source_keys) - set(dest_keys)
    )
    for row in result["copies"]:
        assert row["payload"] == mapping(source)[row["key"]]
        assert (
            result["destination"]["tree"]["nodes"][row["destination"]]["key"]
            == row["key"]
        )
    c.validate_state(result["destination"])


def test_existing_keys_preserve_topology_and_ids_but_replace_every_payload():
    source = state([1, 5, 3], 100)
    dest = state([5, 3, 1], 200)
    result = c.transfer(source, dest)
    assert result["destination"]["tree"] == dest["tree"]
    assert all(not row["inserted"] for row in result["copies"])
    assert mapping(result["destination"]) == mapping(source)


def test_returned_state_does_not_alias_inputs():
    source = state([1, 3], 100)
    dest = state([2], 200)
    before = copy.deepcopy((source, dest))
    result = c.transfer(source, dest)
    result["destination"]["payloads"][0] = 0
    result["destination"]["tree"]["nodes"][0]["key"] = 999
    assert (source, dest) == before


@pytest.mark.parametrize("payloads", [[], [True], [-1], [2**32], (1,)])
def test_invalid_payload_domain(payloads):
    source = state([1])
    source["payloads"] = payloads
    with pytest.raises(RuntimeError):
        c.transfer(source, state([]))


def test_union_bound_rejected_before_any_mutation():
    source = state(list(range(128, 257)))
    dest = state(list(range(128)))
    before = copy.deepcopy((source, dest))
    with pytest.raises(c.TransferError, match="union"):
        c.transfer(source, dest)
    assert (source, dest) == before


def test_duplicate_transfer_is_idempotent():
    source = state([4, 2, 6, 1, 3, 5, 7], 100)
    dest = state([0, 2, 8], 200)
    once = c.transfer(source, dest)["destination"]
    twice = c.transfer(source, once)
    assert twice["destination"] == once
    assert all(not row["inserted"] for row in twice["copies"])
