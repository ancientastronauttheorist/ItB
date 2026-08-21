"""Lua 5.1 tests for the inert Observatory callback manifest module."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip(
        "exact callback manifest harness requires lupa.lua51",
        allow_module_level=True,
    )


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "src" / "bridge" / "observatory_callback_manifest.lua"
).read_bytes().decode("utf-8")


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().CALLBACK_MANIFEST = runtime.execute(SOURCE)
    return runtime


def test_module_load_is_inert_and_writes_no_globals():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute(
        r"""
        io.open = function() error("unexpected I/O") end
        os.getenv = function() error("unexpected environment lookup") end
        """
    )
    before = set(runtime.globals().keys())
    module = runtime.execute(SOURCE)
    after = set(runtime.globals().keys())
    assert module.VERSION == "observatory-callback-manifest/1"
    assert before == after


def test_direct_inherited_alias_c_and_replacement_are_explicit(lua):
    lua.execute(
        r"""
        local calls = 0
        local shared = function() calls = calls + 1; return "called" end
        local old = function() calls = calls + 1; return "old" end
        local base = {GetTargetArea = shared}
        local root = {
            GetTargetScore = shared,
            GetSkillEffect = table.insert,
        }
        local root_mt = {__index = base}
        setmetatable(root, root_mt)

        local manifest = assert(CALLBACK_MANIFEST.enumerate({{
            root_id = "enemy.1.skill.1",
            object = root,
            expected = {GetTargetScore = old},
        }}))

        assert(calls == 0)
        assert(getmetatable(root) == root_mt)
        assert(rawget(root, "GetTargetScore") == shared)
        assert(rawget(root, "GetTargetArea") == nil)
        assert(manifest.schema_version == 1)
        assert(manifest.runtime_version == "observatory-callback-manifest/1")
        assert(manifest.summary.root_count == 1)
        assert(manifest.summary.method_count == 4)
        assert(manifest.summary.function_count == 3)
        assert(manifest.summary.replaced_count == 1)

        local area = manifest.roots[1].methods[1]
        local score = manifest.roots[1].methods[2]
        local effect = manifest.roots[1].methods[3]
        local positioning = manifest.roots[1].methods[4]
        assert(area.method == "GetTargetArea")
        assert(area.status == "resolved" and area.resolution_depth == 1)
        assert(score.status == "resolved" and score.resolution_depth == 0)
        assert(area.function_id == score.function_id)
        assert(score.replaced)
        assert(score.expected_function_id ~= score.function_id)
        assert(effect.status == "c_function")
        assert(not effect.replaced)
        assert(manifest.functions[3].what == "C")
        assert(positioning.status == "missing")
        assert(positioning.function_id == "")
        """
    )


def test_dynamic_index_cycles_depth_and_nonfunctions_never_execute(lua):
    lua.execute(
        r"""
        local index_calls = 0
        local dynamic = {}
        setmetatable(dynamic, {
            __index = function()
                index_calls = index_calls + 1
                error("must not run")
            end,
        })

        local cycle_a, cycle_b = {}, {}
        setmetatable(cycle_a, {__index = cycle_b})
        setmetatable(cycle_b, {__index = cycle_a})

        local invalid = {}
        setmetatable(invalid, {__index = 7})

        local protected = {}
        setmetatable(protected, {__index = {}, __metatable = "locked"})

        local nonfunction = {GetTargetArea = 42}
        local deep_root, deep_one, deep_two = {}, {}, {}
        setmetatable(deep_root, {__index = deep_one})
        setmetatable(deep_one, {__index = deep_two})
        deep_two.GetTargetArea = function() error("must not run") end

        local manifest = assert(CALLBACK_MANIFEST.enumerate({
            {root_id = "dynamic", object = dynamic, expected = {}},
            {root_id = "cycle", object = cycle_a, expected = {}},
            {root_id = "invalid", object = invalid, expected = {}},
            {root_id = "protected", object = protected, expected = {}},
            {root_id = "nonfunction", object = nonfunction, expected = {}},
            {root_id = "deep", object = deep_root, expected = {}},
        }, {
            max_roots = 8,
            max_depth = 1,
            max_functions = 8,
            max_text_bytes = 128,
        }))
        assert(index_calls == 0)
        assert(manifest.roots[1].methods[1].status == "function_index")
        assert(manifest.roots[2].methods[1].status == "index_cycle")
        assert(manifest.roots[3].methods[1].status == "invalid_index")
        assert(manifest.roots[4].methods[1].status == "protected_metatable")
        assert(manifest.roots[5].methods[1].status == "non_function")
        assert(manifest.roots[6].methods[1].status == "depth_exceeded")
        assert(manifest.summary.function_count == 0)
        """
    )


def test_function_and_metadata_caps_are_reported_without_calling_targets(lua):
    lua.execute(
        r"""
        local calls = 0
        local chunk = assert(loadstring(
            "return function() return 1 end",
            "@scripts/" .. string.rep("long_name_", 20) .. ".lua"
        ))
        local long_source = chunk()
        local other = function() calls = calls + 1 end
        local root = {
            GetTargetArea = long_source,
            GetTargetScore = other,
        }
        local manifest = assert(CALLBACK_MANIFEST.enumerate({{
            root_id = "capped",
            object = root,
            expected = {},
        }}, {
            max_roots = 1,
            max_depth = 1,
            max_functions = 1,
            max_text_bytes = 32,
        }))
        assert(calls == 0)
        assert(manifest.functions[1].source_truncated)
        assert(string.len(manifest.functions[1].source) == 32)
        assert(manifest.roots[1].methods[1].status == "resolved")
        assert(manifest.roots[1].methods[2].status == "function_cap")
        assert(manifest.summary.status_counts.function_cap == 1)
        """
    )


def test_invalid_inputs_fail_closed(lua):
    lua.execute(
        r"""
        local ok, err = CALLBACK_MANIFEST.enumerate({}, nil)
        assert(ok == nil and err == "invalid roots")
        ok, err = CALLBACK_MANIFEST.enumerate({{
            root_id = "Bad ID",
            object = {},
            expected = {},
        }}, nil)
        assert(ok == nil and err == "invalid root")
        ok, err = CALLBACK_MANIFEST.enumerate({{
            root_id = "valid",
            object = {},
            expected = {GetTargetArea = 4},
        }}, nil)
        assert(ok == nil and err == "invalid expected callback")

        local spec_index_calls = 0
        local incomplete = setmetatable({
            root_id = "valid",
            object = {},
        }, {
            __index = function()
                spec_index_calls = spec_index_calls + 1
                error("spec lookup must remain raw")
            end,
        })
        ok, err = CALLBACK_MANIFEST.enumerate({incomplete}, nil)
        assert(ok == nil and err == "invalid root")
        assert(spec_index_calls == 0)
        """
    )
