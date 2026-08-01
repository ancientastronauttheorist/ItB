"""Lua 5.1 tests for the explicit Observatory experiment controller."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip(
        "exact Lua 5.1 Observatory harness requires lupa.lua51",
        allow_module_level=True,
    )

from src.observatory.controller_bundle import (
    controller_bundle_sha256,
    render_controller_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = (
    ROOT / "src" / "bridge" / "observatory_trace.lua"
).read_bytes().decode("utf-8")
CONTROLLER_SOURCE = (
    ROOT / "src" / "bridge" / "observatory_controller.lua"
).read_bytes().decode("utf-8")

PRELUDE = r"""
function sha(character)
    return string.rep(character, 64)
end

local ALL_KINDS = {
    "enemy_action_selected",
    "enemy_candidate",
    "enemy_target_score",
    "get_skill_effect",
    "get_target_area",
    "random_bool",
    "random_int",
    "score_positioning",
}

function packet_for(installed_kind)
    local plan = {}
    for _, kind in ipairs(ALL_KINDS) do
        plan[#plan + 1] = {
            hook_id = kind .. ".default",
            event_kind = kind,
            target = "_G." .. kind,
            target_kind = "lua_global",
            status = kind == installed_kind and "installed" or "disabled",
            source_sha256 = sha("3"),
        }
    end
    local policy = {
        expected_phase = "combat_enemy",
        max_events = 16,
        max_events_per_turn = 16,
        max_event_bytes = 4096,
        max_total_event_bytes = 32768,
        max_attempts = 64,
        max_bundle_bytes = 8 * 1024 * 1024,
        allowed_kinds = {installed_kind},
    }
    local trusted = {
        controller_sha256 = sha("a"),
        installed_modloader_sha256 = sha("b"),
        build_identity_sha256 = sha("c"),
        config_sha256 = sha("d"),
        hook_coverage_sha256 = sha("e"),
    }
    local manifest = {
        schema_version = 1,
        capture_id = "capture-001",
        checkpoint_seq = 4,
        arm_nonce = string.rep("f", 32),
        controller_version = "observatory-controller/1",
        controller_sha256 = sha("a"),
        installed_modloader_sha256 = sha("b"),
        build_identity_sha256 = sha("c"),
        expected_mission_id = "Mission_Test",
        expected_turn = 2,
        expected_phase = "combat_enemy",
        timeline_fingerprint = sha("1"),
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed_fingerprint = sha("2"),
        config_sha256 = sha("d"),
        hook_coverage_sha256 = sha("e"),
        activated_epoch = 1000,
        expires_epoch = 1100,
        max_events = policy.max_events,
        max_events_per_turn = policy.max_events_per_turn,
        max_event_bytes = policy.max_event_bytes,
        max_total_event_bytes = policy.max_total_event_bytes,
        max_attempts = policy.max_attempts,
        max_bundle_bytes = policy.max_bundle_bytes,
        allowed_kinds = policy.allowed_kinds,
    }
    return {
        arm_packet_schema_version = 1,
        build_identity = {platform = "windows"},
        manifest = manifest,
        trusted = trusted,
        policy = policy,
        hook_plan = plan,
    }
end

function runtime_state()
    return {
        now_epoch = 1001,
        mission_id = "Mission_Test",
        turn = 2,
        phase = "combat_enemy",
        timeline_fingerprint = sha("1"),
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed_fingerprint = sha("2"),
    }
end
"""


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime_module = runtime.execute(RUNTIME_SOURCE)
    controller_module = runtime.execute(CONTROLLER_SOURCE)
    runtime.globals().BOUND = controller_module.bind_runtime(runtime_module)
    runtime.execute(PRELUDE)
    return runtime


def test_module_load_and_controller_construction_are_inert(lua):
    lua.execute(
        r"""
        local holder = {f = function(value) return value + 1 end}
        local original = holder.f
        local writes = 0
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
            raw_writer = function() writes = writes + 1; return true end,
        })
        assert(holder.f == original)
        assert(writes == 0)
        local status = controller:status()
        assert(not status.consumed and not status.activated)
        """
    )


def test_random_int_prepare_activate_checkpoint_is_explicit_and_exact(lua):
    lua.execute(
        r"""
        _G.random_int = function(upper) return upper - 1, nil, "tail" end
        local original = _G.random_int
        local written = nil
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function(snapshot)
                written = snapshot
                return true
            end,
        })
        local packet = packet_for("random_int")
        local configured_hook_target = packet.hook_plan[7].target
        assert(controller:prepare(packet))
        assert(_G.random_int == original)
        -- Mutating caller-owned input cannot alter the frozen runtime plan.
        packet.hook_plan[7].target = "mutated"
        assert(controller:activate(string.rep("f", 32)))
        assert(_G.random_int ~= original)
        local function higher_level_caller()
            return _G.random_int(5)
        end
        local first, middle, tail = higher_level_caller()
        assert(first == 4 and middle == nil and tail == "tail")
        assert(controller:checkpoint("explicit"))
        assert(_G.random_int == original)
        assert(written.checkpoint_seq == 4)
        assert(written.started_epoch == 1001)
        assert(written.events[1].kind == "random_int")
        -- v1's compatibility-named call_site is the immutable hook target,
        -- not the higher-level Lua caller or a call-stack reconstruction.
        assert(written.events[1].context.call_site == configured_hook_target)
        assert(written.events[1].context.call_site == "_G.random_int")
        assert(written.events[1].payload.upper_bound == 5)
        assert(written.events[1].payload.result == 4)
        assert(written.summary.stop_reasons.max_attempts == nil)
        """
    )


def test_random_bool_records_raw_argument_without_probability_claim(lua):
    lua.execute(
        r"""
        _G.random_bool = function(argument) return argument == 5 end
        local written = nil
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_bool.default"] = {
                    holder = _G, key = "random_bool"
                },
            },
            raw_writer = function(snapshot)
                written = snapshot
                return true
            end,
        })
        local packet = packet_for("random_bool")
        assert(controller:prepare(packet))
        assert(controller:activate(string.rep("f", 32)))
        assert(_G.random_bool(5) == true)
        assert(controller:checkpoint("explicit"))
        assert(written.events[1].context.call_site == "_G.random_bool")
        assert(written.events[1].payload.argument == 5)
        assert(written.events[1].payload.result == true)
        """
    )


def test_bad_nonce_and_hook_install_failure_restore_original(lua):
    lua.execute(
        r"""
        _G.random_int = function(upper) return upper - 1 end
        local original = _G.random_int
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function() return true end,
        })
        assert(controller:prepare(packet_for("random_int")))
        local ok, err = controller:activate(string.rep("0", 32))
        assert(not ok and err == "activation nonce mismatch")
        assert(_G.random_int == original)

        _G.random_int = function(upper) return upper - 1 end
        local original2 = _G.random_int
        local controller2 = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function() return true end,
        })
        assert(controller2:prepare(packet_for("random_int")))
        _G.random_int = function() return 0 end
        ok, err = controller2:activate(string.rep("f", 32))
        assert(not ok and err == "hook target changed")
        assert(_G.random_int ~= original2)
        """
    )


def test_unsupported_installed_hook_fails_before_runtime_construction(lua):
    lua.execute(
        r"""
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {},
            raw_writer = function() return true end,
        })
        local ok, err = controller:prepare(packet_for("enemy_candidate"))
        assert(not ok and err == "unsupported installed hook")
        local status = controller:status()
        assert(status.consumed and not status.prepared)
        """
    )


def test_controller_v1_rejects_combined_rng_hook_plan(lua):
    lua.execute(
        r"""
        local packet = packet_for("random_int")
        packet.hook_plan[6].status = "installed"
        packet.policy.allowed_kinds = {"random_bool", "random_int"}
        packet.manifest.allowed_kinds = {"random_bool", "random_int"}
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {},
            raw_writer = function() return true end,
        })
        local ok, err = controller:prepare(packet)
        assert(not ok
            and err == "controller requires exactly one installed hook")
        """
    )


def test_malformed_hook_plan_fails_closed_without_throwing(lua):
    lua.execute(
        r"""
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {},
            raw_writer = function() return true end,
        })
        local packet = packet_for("random_int")
        packet.hook_plan = "not-a-table"
        local call_ok, ok, err = pcall(
            controller.prepare, controller, packet
        )
        assert(call_ok and not ok and err == "invalid arm packet")
        """
    )


def test_controller_rejects_mislabeled_or_indirect_rng_binding(lua):
    lua.execute(
        r"""
        local holder = {random_int = function(upper) return upper - 1 end}
        local packet = packet_for("random_int")
        packet.hook_plan[7].target = "_G.some_other_function"
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = holder, key = "random_int"
                },
            },
            raw_writer = function() return true end,
        })
        local ok, err = controller:prepare(packet)
        assert(not ok and err == "installed RNG binding is not exact")
        assert(holder.random_int(4) == 3)
        """
    )


def test_checkpoint_rejection_always_restores_live_hook(lua):
    lua.execute(
        r"""
        _G.random_int = function(upper) return upper - 1 end
        local original = _G.random_int
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function() return true end,
        })
        assert(controller:prepare(packet_for("random_int")))
        assert(controller:activate(string.rep("f", 32)))
        assert(_G.random_int ~= original)
        local ok, err = controller:checkpoint("invalid")
        assert(not ok and err == "invalid checkpoint")
        assert(_G.random_int == original)
        assert(not controller:status().activated)
        """
    )


def test_original_error_object_identity_is_preserved(lua):
    lua.execute(
        r"""
        local sentinel = {}
        _G.random_int = function() error(sentinel) end
        local original = _G.random_int
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function() return true end,
        })
        assert(controller:prepare(packet_for("random_int")))
        assert(controller:activate(string.rep("f", 32)))
        local ok, caught = pcall(_G.random_int, 5)
        assert(not ok and caught == sentinel)
        controller:disarm()
        assert(_G.random_int == original)
        """
    )


def test_raw_writer_failure_occurs_after_hooks_are_restored(lua):
    lua.execute(
        r"""
        _G.random_int = function(upper) return upper - 1 end
        local original = _G.random_int
        local saw_original = false
        local controller = BOUND.new({
            runtime_provider = runtime_state,
            hook_bindings = {
                ["random_int.default"] = {
                    holder = _G, key = "random_int"
                },
            },
            raw_writer = function()
                saw_original = _G.random_int == original
                return false, "create-only collision"
            end,
        })
        assert(controller:prepare(packet_for("random_int")))
        assert(controller:activate(string.rep("f", 32)))
        assert(_G.random_int(3) == 2)
        local ok, err = controller:checkpoint("explicit")
        assert(not ok and err == "create-only collision")
        assert(saw_original and _G.random_int == original)
        """
    )


def test_generated_bundle_loads_without_io_or_global_mutation():
    bundle = render_controller_bundle(RUNTIME_SOURCE, CONTROLLER_SOURCE)
    assert controller_bundle_sha256(bundle) == controller_bundle_sha256(bundle)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute(
        r"""
        io.open = function() error("unexpected I/O") end
        os.getenv = function() error("unexpected environment lookup") end
        """
    )
    before = set(runtime.globals().keys())
    bound = runtime.execute(bundle)
    after = set(runtime.globals().keys())
    assert bound.VERSION == "observatory-controller/1"
    assert before == after
