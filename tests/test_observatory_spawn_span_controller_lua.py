"""Lua 5.1 conformance tests for the exact NextPawn span controller."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip("exact Lua 5.1 harness requires lupa.lua51", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "src" / "bridge" / "observatory_spawn_span_controller.lua"
).read_text(encoding="utf-8")


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().MODULE = runtime.execute(SOURCE)
    runtime.execute(
        r"""
        function trusted_getinfo()
            return {
                what = "Lua",
                source = "@B:\\SteamLibrary\\steamapps\\common\\Into the Breach\\scripts\\spawner_backend.lua",
                linedefined = 174,
            }
        end
        function new_fixture()
            local calls = 0
            local count = 10
            local spawner = {}
            spawner.NextPawn = function(self, tables)
                calls = calls + 1
                count = count + 3
                return tables and tables.choice or "Firefly1"
            end
            local observer = {
                status = function()
                    return {
                        state = "capturing",
                        patch_installed = true,
                        record_count = count,
                    }
                end,
            }
            return spawner, observer, function() return calls end
        end
        """
    )
    return runtime


def test_load_and_construction_are_inert_then_restore_exactly(lua):
    lua.execute(
        r"""
        local spawner, observer, calls = new_fixture()
        local original = spawner.NextPawn
        local controller = assert(MODULE.new({
            capture_id = "spawn-span-001",
            spawner = spawner,
            observer = observer,
            getinfo = trusted_getinfo,
        }))
        assert(type(rawget(controller, "activate")) == "function")
        assert(type(rawget(controller, "checkpoint")) == "function")
        assert(type(rawget(controller, "abort")) == "function")
        assert(getmetatable(controller) == nil)
        assert(spawner.NextPawn == original)
        assert(controller:activate())
        assert(spawner.NextPawn ~= original)
        assert(spawner:NextPawn({choice = "Hornet2"}) == "Hornet2")
        local ledger = assert(controller:checkpoint())
        assert(spawner.NextPawn == original)
        assert(calls() == 1)
        assert(ledger.integrity.complete)
        assert(ledger.integrity.wrapper_restored)
        assert(ledger.kind == "spawn_rng_span_ledger")
        assert(ledger.write_mode == "create_only")
        assert(ledger.raw_record_count == 13)
        assert(ledger.spans[1].entry_count == 10)
        assert(ledger.spans[1].exit_count == 13)
        assert(ledger.spans[1].selected_pawn == "Hornet2")
        assert(ledger.source_identity.source_location_verified)
        """
    )


def test_original_error_is_preserved_and_capture_is_not_claimed_normal(lua):
    lua.execute(
        r"""
        local count = 0
        local spawner = {NextPawn = function() count = count + 1; error("boom") end}
        local observer = {status = function()
            return {state = "capturing", patch_installed = true, record_count = count}
        end}
        local original = spawner.NextPawn
        local controller = assert(MODULE.new({
            capture_id = "spawn-span-error",
            spawner = spawner,
            observer = observer,
            getinfo = trusted_getinfo,
        }))
        assert(controller:activate())
        local ok, err = pcall(function() spawner:NextPawn() end)
        assert(not ok and string.find(err, "boom", 1, true))
        local ledger = assert(controller:checkpoint())
        assert(spawner.NextPawn == original)
        assert(ledger.spans[1].detail == "original_error")
        """
    )


def test_source_mismatch_and_restore_conflict_fail_closed(lua):
    lua.execute(
        r"""
        local spawner, observer = new_fixture()
        local controller = assert(MODULE.new({
            capture_id = "spawn-span-source",
            spawner = spawner,
            observer = observer,
            getinfo = function()
                return {what = "Lua", source = "@wrong.lua", linedefined = 174}
            end,
        }))
        local ok, err = controller:activate()
        assert(not ok and err == "Spawner.NextPawn source identity mismatch")

        local controller2 = assert(MODULE.new({
            capture_id = "spawn-span-conflict",
            spawner = spawner,
            observer = observer,
            getinfo = trusted_getinfo,
        }))
        assert(controller2:activate())
        local replacement = function() return "owner" end
        spawner.NextPawn = replacement
        local ledger = assert(controller2:checkpoint())
        assert(spawner.NextPawn == replacement)
        assert(not ledger.integrity.complete)
        assert(ledger.integrity.restore_conflict)
        assert(not ledger.integrity.wrapper_restored)
        """
    )


def test_bad_observer_status_marks_ledger_incomplete(lua):
    lua.execute(
        r"""
        local spawner = {NextPawn = function() return "Scarab1" end}
        local observer = {status = function()
            return {state = "restored", patch_installed = false, record_count = 0}
        end}
        local controller = assert(MODULE.new({
            capture_id = "spawn-span-status",
            spawner = spawner,
            observer = observer,
            getinfo = trusted_getinfo,
        }))
        assert(controller:activate())
        assert(spawner:NextPawn() == "Scarab1")
        local ledger = assert(controller:checkpoint())
        assert(not ledger.integrity.complete)
        assert(ledger.integrity.observer_status_error_count == 3)
        """
    )
