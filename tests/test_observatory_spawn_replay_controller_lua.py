"""Lua 5.1 conformance tests for the exact spawn-replay controller."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip("exact Lua 5.1 harness requires lupa.lua51", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "src" / "bridge" / "observatory_spawn_replay_controller.lua"
).read_text(encoding="utf-8")


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().MODULE = runtime.execute(SOURCE)
    runtime.execute(
        r"""
        function new_replay_fixture()
            local count = 10
            local random_calls = 0
            local globals = {}
            globals.BossesList = {FireflyBoss = true, ScarabBoss = true}
            local random_original = function(list)
                random_calls = random_calls + 1
                count = count + 1
                return list[(26204 % #list) + 1]
            end
            globals.random_element = random_original
            local spawner = {
                num_weak = 2,
                num_upgrades = 3,
                upgrade_streak = 1,
                num_spawns = 5,
                upgrade_max = 3,
                used_bosses = 0,
                num_bosses = 1,
                curr_weakRatio = {2, 4},
                curr_upgradeRatio = {1, 3},
                max_level = {Mosquito = 2, Scarab = 2, Firefly = 2},
            }
            local next_original = function(self, tables)
                count = count + 1
                local selected = globals.random_element(tables)
                count = count + 1
                self.num_spawns = self.num_spawns + 1
                return selected .. "2"
            end
            spawner.NextPawn = next_original
            local observer = {status = function()
                return {
                    state = "capturing",
                    patch_installed = true,
                    record_count = count,
                }
            end}
            local getinfo = function(fn)
                if fn == next_original then
                    return {
                        what = "Lua",
                        source = "@B:\\SteamLibrary\\steamapps\\common\\Into the Breach\\scripts\\spawner_backend.lua",
                        linedefined = 174,
                    }
                elseif fn == random_original then
                    return {
                        what = "Lua",
                        source = "@B:\\SteamLibrary\\steamapps\\common\\Into the Breach\\scripts\\global.lua",
                        linedefined = 560,
                    }
                end
                return {what = "Lua", source = "@unknown.lua", linedefined = 1}
            end
            return spawner, globals, observer, getinfo,
                next_original, random_original,
                function() return random_calls end
        end
        """
    )
    return runtime


def test_captures_exact_candidate_array_and_restores_both_slots(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo,
            next_original, random_original, random_calls = new_replay_fixture()
        local controller = assert(MODULE.new({
            capture_id = "spawn-replay-001",
            spawner = spawner,
            observer = observer,
            getinfo = getinfo,
            globals = globals,
        }))
        assert(spawner.NextPawn == next_original)
        assert(globals.random_element == random_original)
        assert(controller:activate())
        assert(spawner.NextPawn ~= next_original)
        assert(globals.random_element == random_original)

        local selected = spawner:NextPawn({"Mosquito", "Scarab", "Firefly"})
        assert(selected == "Firefly2")
        assert(random_calls() == 1)
        assert(globals.random_element == random_original)

        local ledger = assert(controller:checkpoint())
        assert(spawner.NextPawn == next_original)
        assert(globals.random_element == random_original)
        assert(ledger.kind == "spawn_rng_replay_ledger")
        assert(ledger.integrity.complete)
        assert(ledger.integrity.next_wrapper_restored)
        assert(ledger.integrity.random_wrapper_restored)
        assert(ledger.summary.span_count == 1)
        assert(ledger.summary.candidate_event_count == 1)
        local span = ledger.spans[1]
        assert(span.entry_count == 10)
        assert(span.exit_count == 13)
        assert(span.selected_pawn == "Firefly2")
        assert(span.selected_max_level == 2)
        assert(span.boss_available)
        assert(span.inputs.num_spawns == 5)
        assert(span.inputs.curr_weak_ratio.numerator == 2)
        assert(span.inputs.curr_upgrade_ratio.denominator == 3)
        local event = span.candidate_events[1]
        assert(event.entry_count == 11)
        assert(event.exit_count == 12)
        assert(event.list_length == 3)
        assert(event.available[1] == "Mosquito")
        assert(event.available[2] == "Scarab")
        assert(event.available[3] == "Firefly")
        assert(event.selected_base == "Firefly")
        """
    )


def test_snapshots_effective_values_inherited_by_active_spawner(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo,
            next_original, random_original = new_replay_fixture()
        local active = setmetatable({
            curr_weakRatio = {1, 4},
            curr_upgradeRatio = {2, 3},
        }, {__index = spawner})
        local controller = assert(MODULE.new({
            capture_id="spawn-replay-inherited", spawner=spawner,
            observer=observer, getinfo=getinfo, globals=globals,
        }))
        assert(controller:activate())
        assert(active:NextPawn({"Mosquito", "Scarab", "Firefly"}) == "Firefly2")
        local ledger = assert(controller:checkpoint())
        assert(ledger.integrity.complete)
        local span = ledger.spans[1]
        assert(span.inputs_valid)
        assert(span.inputs.num_weak == 2)
        assert(span.inputs.num_upgrades == 3)
        assert(span.inputs.num_spawns == 5)
        assert(span.inputs.curr_weak_ratio.numerator == 1)
        assert(span.inputs.curr_upgrade_ratio.numerator == 2)
        assert(span.selected_max_level == 2)
        assert(span.boss_available)
        """
    )


def test_original_nextpawn_error_still_restores_random_element(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo,
            next_original, random_original = new_replay_fixture()
        spawner.NextPawn = function(self)
            globals.random_element({"Scarab"})
            error("next boom")
        end
        next_original = spawner.NextPawn
        getinfo = function(fn)
            if fn == next_original then
                return {what="Lua", source="@scripts/spawner_backend.lua", linedefined=174}
            elseif fn == random_original then
                return {what="Lua", source="@scripts/global.lua", linedefined=560}
            end
        end
        local controller = assert(MODULE.new({
            capture_id="spawn-replay-error", spawner=spawner,
            observer=observer, getinfo=getinfo, globals=globals,
        }))
        assert(controller:activate())
        local ok, err = pcall(function() spawner:NextPawn() end)
        assert(not ok and string.find(err, "next boom", 1, true))
        assert(globals.random_element == random_original)
        local ledger = assert(controller:checkpoint())
        assert(ledger.spans[1].detail == "original_error")
        assert(ledger.integrity.random_wrapper_restored)
        """
    )


def test_source_mismatch_fails_before_mutation(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo,
            next_original, random_original = new_replay_fixture()
        local controller = assert(MODULE.new({
            capture_id="spawn-replay-source", spawner=spawner,
            observer=observer,
            getinfo=function(fn)
                if fn == next_original then
                    return {what="Lua", source="@scripts/spawner_backend.lua", linedefined=174}
                end
                return {what="Lua", source="@wrong.lua", linedefined=560}
            end,
            globals=globals,
        }))
        local ok, err = controller:activate()
        assert(not ok and err == "random_element source identity mismatch")
        assert(spawner.NextPawn == next_original)
        assert(globals.random_element == random_original)
        """
    )


def test_random_element_owner_conflict_is_not_overwritten(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo,
            next_original, random_original = new_replay_fixture()
        local replacement = function() return "owner" end
        spawner.NextPawn = function(self, tables)
            local selected = globals.random_element(tables)
            globals.random_element = replacement
            return selected .. "1"
        end
        next_original = spawner.NextPawn
        getinfo = function(fn)
            if fn == next_original then
                return {what="Lua", source="@scripts/spawner_backend.lua", linedefined=174}
            elseif fn == random_original then
                return {what="Lua", source="@scripts/global.lua", linedefined=560}
            end
        end
        local controller = assert(MODULE.new({
            capture_id="spawn-replay-conflict", spawner=spawner,
            observer=observer, getinfo=getinfo, globals=globals,
        }))
        assert(controller:activate())
        assert(spawner:NextPawn({"Scarab"}) == "Scarab1")
        assert(globals.random_element == replacement)
        local ledger = assert(controller:checkpoint())
        assert(globals.random_element == replacement)
        assert(not ledger.integrity.complete)
        assert(ledger.integrity.restore_conflict)
        assert(not ledger.integrity.random_wrapper_restored)
        """
    )


def test_invalid_candidate_array_and_missing_event_fail_closed(lua):
    lua.execute(
        r"""
        local spawner, globals, observer, getinfo = new_replay_fixture()
        local controller = assert(MODULE.new({
            capture_id="spawn-replay-invalid", spawner=spawner,
            observer=observer, getinfo=getinfo, globals=globals,
        }))
        assert(controller:activate())
        assert(spawner:NextPawn({"Scarab", 7}) == "Scarab2")
        local ledger = assert(controller:checkpoint())
        assert(not ledger.integrity.complete)
        assert(ledger.integrity.invalid_candidate_count == 1)

        local spawner2, globals2, observer2, getinfo2,
            next2, random2 = new_replay_fixture()
        spawner2.NextPawn = function(self) return "Firefly1" end
        next2 = spawner2.NextPawn
        getinfo2 = function(fn)
            if fn == next2 then
                return {what="Lua", source="@scripts/spawner_backend.lua", linedefined=174}
            elseif fn == random2 then
                return {what="Lua", source="@scripts/global.lua", linedefined=560}
            end
        end
        local controller2 = assert(MODULE.new({
            capture_id="spawn-replay-missing", spawner=spawner2,
            observer=observer2, getinfo=getinfo2, globals=globals2,
        }))
        assert(controller2:activate())
        assert(spawner2:NextPawn() == "Firefly1")
        local ledger2 = assert(controller2:checkpoint())
        assert(not ledger2.integrity.complete)
        assert(ledger2.integrity.candidate_count_mismatch_count == 1)
        """
    )
