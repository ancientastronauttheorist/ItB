"""Focused tests for strict Lua 5.1 bytecode metadata parsing."""

from __future__ import annotations

import pytest

from src.observatory.lua51_bytecode import (
    Lua51BytecodeError,
    flatten_prototypes,
    parse_lua51_chunk,
)


try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional exact-version harness
    lua51 = None


pytestmark = pytest.mark.skipif(lua51 is None, reason="requires lupa.lua51")


def _compile(source: bytes) -> bytes:
    runtime = lua51.LuaRuntime(encoding=None)
    function = runtime.compile(source, name=b"@scripts/test.lua")
    return runtime.eval(b"string.dump")(function)


def test_parses_nested_prototypes_and_debug_metadata():
    chunk = parse_lua51_chunk(
        _compile(
            b"""
local captured = 3
function Outer(value, ...)
    local function Inner(argument)
        return argument + captured
    end
    print(math.abs(value))
    return Inner(value)
end
"""
        )
    )

    prototypes = flatten_prototypes(chunk.root)
    assert chunk.header.normalized()["version"] == "5.1"
    assert [prototype.prototype_path for prototype in prototypes] == [
        "0",
        "0/0",
        "0/0/0",
    ]
    assert prototypes[1].parameter_count == 1
    assert prototypes[1].vararg_flags != 0
    assert prototypes[2].parameter_count == 1
    assert prototypes[2].upvalue_count == 1
    assert prototypes[2].upvalue_names == (b"captured",)
    assert all(len(prototype.serialized_sha256) == 64 for prototype in prototypes)


def test_parser_is_deterministic_and_rejects_trailing_or_wrong_version():
    dumped = _compile(b"return function(a) return a end")
    first = parse_lua51_chunk(dumped)
    second = parse_lua51_chunk(dumped)
    assert first == second

    with pytest.raises(Lua51BytecodeError, match="trailing bytes"):
        parse_lua51_chunk(dumped + b"x")

    wrong_version = bytearray(dumped)
    wrong_version[4] = 0x54
    with pytest.raises(Lua51BytecodeError, match="not Lua 5.1"):
        parse_lua51_chunk(bytes(wrong_version))


def test_parser_rejects_truncated_chunks():
    dumped = _compile(b"return 1")
    with pytest.raises(Lua51BytecodeError, match="truncated"):
        parse_lua51_chunk(dumped[:-1])
