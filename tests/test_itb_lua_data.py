"""Focused proofs for the strict non-executing Lua data parser."""

from __future__ import annotations

import pytest

from src.observatory.lua_data import LuaDataError, LuaPoint, parse_lua_data_chunk


def test_parser_accepts_only_the_declarative_map_subset():
    chunk = parse_lua_data_chunk(
        """
sample = {
    ["version"] = 7,
    ["enabled"] = true,
    ["origin"] = Point(1,2),
    ["items"] = {"tag", false, 3},
}
"""
    )

    assert chunk.global_name == "sample"
    root = chunk.value.require_pure_keyed("root")
    assert root["version"] == 7
    assert root["enabled"] is True
    assert root["origin"] == LuaPoint(1, 2)
    assert root["items"].require_pure_array("items") == ("tag", False, 3)


@pytest.mark.parametrize(
    "source, message",
    [
        ("sample = function() end", "expected"),
        ("sample = { os.execute('bad') }", "unsupported Lua data token"),
        ("sample = { [\"x\"] = -1 }", "unsupported Lua data token"),
        (r'sample = { ["x"] = "escaped\\n" }', "escapes are outside"),
        ("end = {}", "invalid Lua data chunk global name"),
        ("sample = {}\nother = {}", "expected EOF"),
        ("sample = { [\"x\"] = 12345678901 }", "exceeds 10 digits"),
    ],
)
def test_parser_rejects_code_and_out_of_grammar_values(source: str, message: str):
    with pytest.raises(LuaDataError, match=message):
        parse_lua_data_chunk(source)


def test_table_accessors_reject_duplicate_keys_and_mixed_shapes():
    duplicate = parse_lua_data_chunk('sample = {["x"]=1,["x"]=2}').value
    with pytest.raises(LuaDataError, match="duplicate Lua table key"):
        duplicate.require_pure_keyed("root")

    mixed = parse_lua_data_chunk('sample = {["x"]=1,2}').value
    with pytest.raises(LuaDataError, match="array entries"):
        mixed.require_pure_keyed("root")
    with pytest.raises(LuaDataError, match="keyed entries"):
        mixed.require_pure_array("root")


def test_parser_bounds_table_nesting():
    source = "sample = " + "{" * 33 + "1" + "}" * 33
    with pytest.raises(LuaDataError, match="nesting exceeds 32"):
        parse_lua_data_chunk(source)


def test_parser_bounds_wide_tables_and_strings():
    wide = "sample = {" + ",".join("1" for _ in range(10_001)) + "}"
    with pytest.raises(LuaDataError, match="10000-table-entry limit"):
        parse_lua_data_chunk(wide)

    long_string = 'sample = {"' + "x" * 4_097 + '"}'
    with pytest.raises(LuaDataError, match="4096-character limit"):
        parse_lua_data_chunk(long_string)
