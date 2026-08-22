"""Lua 5.1 tests for inert callback-slot enumeration."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip("exact Lua 5.1 harness requires lupa.lua51", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SOURCE = (ROOT / "src" / "bridge" / "observatory_callback_manifest.lua").read_text(
    encoding="utf-8"
)
BINDINGS_SOURCE = (ROOT / "src" / "bridge" / "observatory_callback_bindings.lua").read_text(
    encoding="utf-8"
)


def test_shared_inherited_slots_are_deduplicated_without_calls_or_mutation():
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.globals().MANIFEST = lua.execute(MANIFEST_SOURCE)
    lua.globals().BINDINGS = lua.execute(BINDINGS_SOURCE)
    lua.execute(
        r"""
        local calls = 0
        TEAM_ENEMY = 6
        local Base = {}
        Base.GetTargetArea = function() calls = calls + 1 end
        Base.GetTargetScore = function() calls = calls + 1 end
        Base.GetSkillEffect = function() calls = calls + 1 end
        SkillA = setmetatable({}, {__index = Base})
        SkillB = setmetatable({
            GetSkillEffect = function() calls = calls + 1 end,
        }, {__index = Base})
        PawnA = {DefaultTeam = TEAM_ENEMY, SkillList = {"SkillA"}}
        PawnB = {DefaultTeam = TEAM_ENEMY, SkillList = {"SkillB"}}
        PawnList = {"PawnA", "PawnB"}
        ScorePositioning = function() calls = calls + 1 end
        local base_area = Base.GetTargetArea
        local base_score = Base.GetTargetScore
        local base_effect = Base.GetSkillEffect
        local override_effect = SkillB.GetSkillEffect
        local global_score = ScorePositioning

        local document, live, err = BINDINGS.enumerate(_G, MANIFEST, {
            max_roots = 16,
            max_depth = 8,
            max_functions = 32,
            max_text_bytes = 256,
        })
        assert(document and live and err == nil)
        assert(calls == 0)
        assert(document.summary.root_count == 3)
        assert(document.summary.method_count == 12)
        assert(document.summary.function_count == 5)
        assert(document.summary.slot_count == 5)
        assert(#live == 5)

        assert(document.roots[1].root_id == "enemy.skill.SkillA")
        assert(document.roots[2].root_id == "enemy.skill.SkillB")
        assert(document.roots[3].root_id == "global.ScorePositioning")
        assert(document.roots[1].methods[1].slot_id == "slot-0001")
        assert(document.roots[2].methods[1].slot_id == "slot-0001")
        assert(document.slots[1].root_ids[1] == "enemy.skill.SkillA")
        assert(document.slots[1].root_ids[2] == "enemy.skill.SkillB")
        assert(document.slots[1].method == "GetTargetArea")
        assert(live[1].holder == Base and live[1].key == "GetTargetArea")
        assert(live[1].original == base_area)
        assert(live[1].root_ids[1] == "enemy.skill.SkillA")
        assert(live[1].root_ids[2] == "enemy.skill.SkillB")
        assert(live[1].root_objects[1] == SkillA)
        assert(live[1].root_objects[2] == SkillB)
        assert(live[5].holder == _G)
        assert(live[5].key == "ScorePositioning")
        assert(live[5].original == global_score)

        assert(Base.GetTargetArea == base_area)
        assert(Base.GetTargetScore == base_score)
        assert(Base.GetSkillEffect == base_effect)
        assert(SkillB.GetSkillEffect == override_effect)
        assert(ScorePositioning == global_score)
        """
    )


def test_dynamic_index_fails_closed_without_invoking_it():
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    lua.globals().MANIFEST = lua.execute(MANIFEST_SOURCE)
    lua.globals().BINDINGS = lua.execute(BINDINGS_SOURCE)
    lua.execute(
        r"""
        local index_calls = 0
        TEAM_ENEMY = 6
        SkillA = setmetatable({}, {__index = function()
            index_calls = index_calls + 1
            return function() end
        end})
        PawnA = {DefaultTeam = TEAM_ENEMY, SkillList = {"SkillA"}}
        PawnList = {"PawnA"}
        ScorePositioning = function() return 0 end
        local document, live, err = BINDINGS.enumerate(_G, MANIFEST, nil)
        assert(document and live and err == nil)
        assert(index_calls == 0)
        assert(document.roots[1].methods[1].status == "function_index")
        assert(document.roots[1].methods[1].slot_id == "")
        """
    )
