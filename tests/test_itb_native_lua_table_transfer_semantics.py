"""Conditional two-entry Lua transfer request and stack laws."""

import copy
import itertools
import pytest
from src.observatory import native_lua_table_transfer_semantics as c


@pytest.mark.parametrize("prefix", [0, 1, 4])
def test_all_short_key_sequences_filter_and_restore(prefix):
    for length in range(5):
        for sequence in itertools.product(c.KINDS, repeat=length):
            kinds = list(sequence)
            before = list(kinds)
            result = c.transfer_requests(kinds, prefix)
            assert kinds == before
            assert result["assignments"] == [
                i for i, k in enumerate(kinds) if k == "other"
            ]
            assert result["skipped"] == [i for i, k in enumerate(kinds) if k != "other"]
            assert result["final"] == result["initial"]
            assert len(result["final"]) == prefix + 2 and result["lua_stack_delta"] == 0
            assert result["api_count"] == 2 + sum(
                {"init": 4, "finalize": 7, "other": 10}[k] for k in kinds
            )
            calls = result["calls"]
            assert calls[0]["api"] == "lua_pushnil" and calls[-1]["api"] == "lua_next"
            assert calls[-1]["truth"] == 0
            assert sum(row["api"] == "lua_next" for row in calls) == length + 1
            assert sum(row["api"] == "lua_settable" for row in calls) == kinds.count(
                "other"
            )
            for first, second in zip(calls, calls[1:]):
                assert first["after"] == second["before"]
            for row in calls:
                assert row["before"][:prefix] == result["initial"][:prefix]
                assert row["after"][:prefix] == result["initial"][:prefix]
                if row["api"] == "lua_settable":
                    assert row["arguments"] == [-5]
                    assert row["before"][-5] == ("destination",)
                    assert row["before"][-3] == row["before"][-2]
                    assert row["after"] == row["before"][:-2]
                if row["api"] == "lua_next":
                    assert row["arguments"] == [-2] and row["before"][-2] == ("source",)
                if row["api"] == "lua_equal":
                    assert row["arguments"] == [-1, -3]


@pytest.mark.parametrize(
    "kind,api_order",
    [
        (
            "init",
            [
                "lua_pushnil",
                "lua_next",
                "lua_pushstring",
                "lua_equal",
                "lua_settop",
                "lua_next",
            ],
        ),
        (
            "finalize",
            [
                "lua_pushnil",
                "lua_next",
                "lua_pushstring",
                "lua_equal",
                "lua_settop",
                "lua_pushstring",
                "lua_equal",
                "lua_settop",
                "lua_next",
            ],
        ),
        (
            "other",
            [
                "lua_pushnil",
                "lua_next",
                "lua_pushstring",
                "lua_equal",
                "lua_settop",
                "lua_pushstring",
                "lua_equal",
                "lua_settop",
                "lua_pushvalue",
                "lua_insert",
                "lua_settable",
                "lua_next",
            ],
        ),
    ],
)
def test_each_single_entry_request_path(kind, api_order):
    result = c.transfer_requests([kind])
    assert [row["api"] for row in result["calls"]] == api_order
    literals = [
        row["arguments"][0] for row in result["calls"] if row["api"] == "lua_pushstring"
    ]
    assert literals == (["__init"] if kind == "init" else ["__init", "__finalize"])
    cleanup = [
        row["arguments"][0] for row in result["calls"] if row["api"] == "lua_settop"
    ]
    assert cleanup == {"init": [-3], "finalize": [-2, -3], "other": [-2, -2]}[kind]


@pytest.mark.parametrize(
    "kinds,prefix",
    [
        ((), 0),
        (["bad"], 0),
        ([True], 0),
        (["other"] * 9, 0),
        ([], True),
        ([], -1),
        ([], 9),
    ],
)
def test_invalid_finite_domain_rejected(kinds, prefix):
    with pytest.raises(c.TransferError):
        c.transfer_requests(kinds, prefix)


def test_results_do_not_alias_input_or_other_snapshots():
    kinds = ["other", "init", "finalize"]
    before = list(kinds)
    result = c.transfer_requests(kinds, 2)
    final = copy.deepcopy(result["final"])
    next_before = copy.deepcopy(result["calls"][1]["before"])
    result["initial"][0] = ("changed",)
    result["calls"][0]["after"][0] = ("changed",)
    assert (
        result["final"] == final
        and result["calls"][1]["before"] == next_before
        and kinds == before
    )
