"""Exact Lua 5.1 conformance tests for the dormant Observatory runtime."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


try:
    from lupa import lua51, lua_type
except ImportError:
    pytest.skip(
        "exact Lua 5.1 Observatory harness requires lupa.lua51",
        allow_module_level=True,
    )

from src.observatory.trace_codec import (
    TraceConfig,
    hook_coverage_sha256,
    trace_config_sha256,
)


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bridge"
    / "observatory_trace.lua"
)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")


PRELUDE = r"""
function sha(character)
    return string.rep(character, 64)
end

function trusted_identity()
    return {
        controller_sha256 = sha("a"),
        installed_modloader_sha256 = sha("b"),
        build_identity_sha256 = sha("c"),
        config_sha256 = CONFIG_DIGEST or sha("d"),
        hook_coverage_sha256 = COVERAGE_DIGEST or sha("e"),
    }
end

function runtime_state(overrides)
    local value = {
        now_epoch = 1001,
        mission_id = "Mission_Test",
        turn = 2,
        phase = "combat_enemy",
        timeline_fingerprint = sha("1"),
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed_fingerprint = sha("2"),
    }
    if overrides then
        for key, child in pairs(overrides) do value[key] = child end
    end
    return value
end

function trace_policy(allowed_kinds, overrides)
    local value = {
        expected_phase = "combat_enemy",
        max_events = 16,
        max_events_per_turn = 16,
        max_event_bytes = 4096,
        max_total_event_bytes = 32768,
        max_attempts = 64,
        max_bundle_bytes = 8 * 1024 * 1024,
        allowed_kinds = allowed_kinds or {"random_int"},
    }
    if overrides then
        for key, child in pairs(overrides) do value[key] = child end
    end
    return value
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

function default_hook_plan(allowed_kinds)
    local allowed = {}
    for _, kind in ipairs(allowed_kinds) do allowed[kind] = true end
    local plan = {}
    for _, kind in ipairs(ALL_KINDS) do
        plan[#plan + 1] = {
            hook_id = kind .. ".default",
            event_kind = kind,
            target = "_G." .. kind,
            target_kind = "lua_global",
            status = allowed[kind] and "installed" or "disabled",
            source_sha256 = sha("3"),
        }
    end
    return plan
end

function arm_manifest(policy, overrides)
    local value = {
        schema_version = 1,
        capture_id = "capture-001",
        checkpoint_seq = 0,
        arm_nonce = string.rep("f", 32),
        controller_version = "test-controller/1",
        controller_sha256 = sha("a"),
        installed_modloader_sha256 = sha("b"),
        build_identity_sha256 = sha("c"),
        expected_mission_id = "Mission_Test",
        expected_turn = 2,
        expected_phase = policy.expected_phase,
        timeline_fingerprint = sha("1"),
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed_fingerprint = sha("2"),
        config_sha256 = CONFIG_DIGEST or sha("d"),
        hook_coverage_sha256 = COVERAGE_DIGEST or sha("e"),
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
    if overrides then
        for key, child in pairs(overrides) do value[key] = child end
    end
    return value
end

function default_extraction(results, arguments, call_order)
    return {
        context = {source = "lua51-test"},
        payload = {
            call_order = call_order,
            result = results[1],
            argument = arguments[1],
        },
    }
end

function new_runtime(spec)
    spec = spec or {}
    local allowed = spec.allowed_kinds or {"random_int"}
    local policy = trace_policy(allowed, spec.policy_overrides)
    local plan = spec.hook_plan or default_hook_plan(allowed)
    local bindings = spec.hook_bindings or {}
    for _, entry in ipairs(plan) do
        if entry.status == "installed"
            and bindings[entry.hook_id] == nil then
            bindings[entry.hook_id] = {
                holder = {f = function(value) return value end},
                key = "f",
            }
        end
    end
    local state = spec.state or runtime_state()
    local provider = spec.runtime_provider or function() return state end
    local runtime = MOD.new({
        trusted = trusted_identity(),
        policy = policy,
        hook_plan = plan,
        hook_bindings = bindings,
        runtime_provider = provider,
    })
    return runtime, bindings, state, policy, plan
end

function activate_runtime(spec, manifest_overrides)
    local runtime, bindings, state, policy, plan = new_runtime(spec)
    local manifest = arm_manifest(policy, manifest_overrides)
    assert(runtime:prepare(manifest))
    assert(runtime:activate(manifest.arm_nonce))
    return runtime, bindings, state, manifest, plan
end

function install_defaults(runtime, plan, observer)
    for _, entry in ipairs(plan) do
        if entry.status == "installed" then
            assert(runtime:install_proven_non_yielding_hook(
                entry.hook_id, observer or default_extraction
            ))
        end
    end
end

function packed(...)
    return {n = select("#", ...), ...}
end
"""


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    module = runtime.execute(MODULE_SOURCE)
    runtime.globals().MOD = module
    runtime.globals().MODULE_SOURCE = MODULE_SOURCE
    runtime.execute(PRELUDE)
    assert runtime.eval("_VERSION") == "Lua 5.1"
    return runtime


def _lua_to_python(value):
    is_table = lua_type(value) == "table" or (
        type(value).__module__ == "lupa.lua51"
        and hasattr(value, "keys")
        and hasattr(value, "items")
    )
    if not is_table:
        return value
    keys = list(value.keys())
    if keys and all(type(key) is int for key in keys):
        ordered = sorted(keys)
        if ordered == list(range(1, len(keys) + 1)):
            return [_lua_to_python(value[index]) for index in ordered]
    return {key: _lua_to_python(child) for key, child in value.items()}


def test_load_and_construction_are_behavior_neutral(lua):
    lua.execute(
        r"""
        local holder = {f = function() return "original" end}
        local original = holder.f
        local runtime = new_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
        })
        assert(not runtime:is_enabled())
        assert(holder.f == original)
        local ok, err = runtime:install_proven_non_yielding_hook(
            "random_int.default", default_extraction
        )
        assert(not ok and err == "trace is disabled")
        assert(holder.f == original)
        """
    )


def test_two_step_activation_is_one_shot_and_nonce_survives_reload(lua):
    lua.execute(
        r"""
        local first, _, _, policy = new_runtime()
        local manifest = arm_manifest(policy)
        assert(first:prepare(manifest))
        local ok, err = first:activate(string.rep("0", 32))
        assert(not ok and err == "activation nonce mismatch")
        ok, err = first:prepare(manifest)
        assert(not ok and err == "runtime already consumed")

        local second = new_runtime()
        assert(second:prepare(manifest))
        assert(second:activate(manifest.arm_nonce))

        MOD = assert(loadstring(MODULE_SOURCE))()
        local reloaded = new_runtime()
        ok, err = reloaded:prepare(manifest)
        assert(not ok and err == "nonce already used")
        """
    )


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ('manifest.capture_id = "UPPER"', "manifest values"),
        ("manifest.extra = true", "manifest fields"),
        ('manifest.controller_sha256 = sha("9")', "trusted identity mismatch"),
        ('manifest.expected_phase = "combat_player"', "manifest values"),
        ("manifest.expires_epoch = 1901", "manifest freshness"),
        (
            'manifest.allowed_kinds = {"random_bool", "random_int"}',
            "trusted policy mismatch",
        ),
        ("manifest.max_events = manifest.max_events + 1", "trusted policy mismatch"),
        ("state.timeline_fingerprint = sha(\"9\")", "runtime identity mismatch"),
        ("state.now_epoch = 999", "manifest freshness"),
    ],
)
def test_prepare_fails_closed(lua, mutation, expected):
    lua.globals().MUTATION = mutation
    lua.globals().EXPECTED = expected
    lua.execute(
        r"""
        local runtime, _, state, policy = new_runtime()
        manifest = arm_manifest(policy)
        _G.state = state
        assert(loadstring(MUTATION))()
        local ok, err = runtime:prepare(manifest)
        assert(not ok and err == EXPECTED, tostring(err))
        assert(not runtime:is_enabled())
        """
    )


def test_policy_and_full_hook_plan_are_trusted_inputs(lua):
    lua.execute(
        r"""
        local ok, err = pcall(function()
            new_runtime({
                allowed_kinds = {"random_int"},
                policy_overrides = {max_events = 0},
            })
        end)
        assert(not ok and string.find(err, "policy values", 1, true))

        ok, err = pcall(function()
            new_runtime({
                policy_overrides = {
                    max_bundle_bytes = 32768 + 2 * 1024 * 1024 - 1,
                },
            })
        end)
        assert(not ok and string.find(err, "policy values", 1, true))

        ok, err = pcall(function()
            local plan = default_hook_plan({"random_int"})
            plan[7].target = ""
            new_runtime({hook_plan = plan})
        end)
        assert(not ok and string.find(err, "hook plan entry", 1, true))

        ok, err = pcall(function()
            local plan = default_hook_plan({"random_int"})
            plan[7].status = "disabled"
            new_runtime({hook_plan = plan})
        end)
        assert(not ok and string.find(err, "hook plan coverage", 1, true))
        """
    )


def test_installation_is_bound_to_exact_planned_target(lua):
    lua.execute(
        r"""
        local planned = {f = function() return 1 end}
        local other = {f = function() return 2 end}
        local planned_original = planned.f
        local other_original = other.f
        local runtime, bindings, _, policy = new_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = planned, key = "f"},
            },
        })
        bindings["random_int.default"].holder = other
        local manifest = arm_manifest(policy)
        assert(runtime:prepare(manifest))
        assert(runtime:activate(manifest.arm_nonce))
        assert(runtime:install_proven_non_yielding_hook(
            "random_int.default", default_extraction
        ))
        assert(planned.f ~= planned_original)
        assert(other.f == other_original)
        local ok, err = runtime:install_proven_non_yielding_hook(
            "random_int.default", default_extraction
        )
        assert(not ok and err == "hook already installed")

        local changed = {f = function() return 3 end}
        local runtime2, _, _, policy2 = new_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = changed, key = "f"},
            },
        })
        changed.f = function() return 4 end
        local manifest2 = arm_manifest(policy2, {
            capture_id = "capture-changed-function",
            arm_nonce = string.rep("e", 32),
        })
        assert(runtime2:prepare(manifest2))
        assert(runtime2:activate(manifest2.arm_nonce))
        ok, err = runtime2:install_proven_non_yielding_hook(
            "random_int.default", default_extraction
        )
        assert(not ok and err == "hook target changed")
        """
    )


def test_wrapper_preserves_returns_and_isolates_observer_copies(lua):
    lua.execute(
        r"""
        local returned = {untouched = true}
        local argument = {untouched = true}
        local holder = {}
        local original_calls = 0
        holder.f = function(value)
            original_calls = original_calls + 1
            return returned, nil, "tail"
        end
        local runtime, _, _, _, plan = activate_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
        })
        install_defaults(runtime, plan, function(results, arguments, order)
            results[1] = "changed"
            results[3] = "changed"
            arguments[1].untouched = false
            return {
                context = {},
                payload = {call_order = order, result = 1, argument = 1},
            }
        end)
        local result = packed(holder.f(argument))
        assert(original_calls == 1)
        assert(result.n == 3)
        assert(result[1] == returned and returned.untouched)
        assert(result[2] == nil and result[3] == "tail")
        assert(argument.untouched)
        """
    )


def test_original_nested_calls_are_observed_but_observer_reentry_is_not(lua):
    lua.execute(
        r"""
        local inner = {}
        local outer = {}
        inner.f = function(value) return value + 1 end
        outer.f = function(value) return inner.f(value) + 1 end
        local plan = default_hook_plan({})
        plan[7] = {
            hook_id = "random_int.inner",
            event_kind = "random_int",
            target = "_G.inner",
            target_kind = "lua_global",
            status = "installed",
            source_sha256 = sha("3"),
        }
        table.insert(plan, 8, {
            hook_id = "random_int.outer",
            event_kind = "random_int",
            target = "_G.outer",
            target_kind = "lua_global",
            status = "installed",
            source_sha256 = sha("3"),
        })
        local bindings = {
            ["random_int.inner"] = {holder = inner, key = "f"},
            ["random_int.outer"] = {holder = outer, key = "f"},
        }
        local runtime, _, _, _, actual_plan = activate_runtime({
            allowed_kinds = {"random_int"},
            hook_plan = plan,
            hook_bindings = bindings,
        })
        local observed = 0
        install_defaults(runtime, actual_plan, function(results, args, order)
            observed = observed + 1
            if observed == 1 then assert(inner.f(20) == 21) end
            return {
                context = {},
                payload = {
                    call_order = order,
                    result = results[1],
                    argument = args[1],
                },
            }
        end)
        assert(outer.f(1) == 3)
        assert(observed == 2)
        assert(runtime.attempted_calls.random_int == 2)
        assert(#runtime.events == 2)
        assert(runtime.events[1].payload.call_order == 0)
        assert(runtime.events[2].payload.call_order == 1)
        """
    )


def test_original_error_propagates_and_does_not_poison_guard(lua):
    lua.execute(
        r"""
        local holder = {}
        local calls = 0
        holder.f = function()
            calls = calls + 1
            error("original boom")
        end
        local runtime, _, _, _, plan = activate_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
        })
        install_defaults(runtime, plan)
        local ok, err = pcall(holder.f)
        assert(not ok and string.find(err, "original boom", 1, true))
        assert(calls == 1)
        assert(runtime.in_trace == false)
        assert(runtime.attempted_calls.random_int == 0)
        """
    )


def test_provider_and_observer_reentry_are_guarded_after_original(lua):
    lua.execute(
        r"""
        local holder = {}
        local original_calls = 0
        holder.f = function(value)
            original_calls = original_calls + 1
            return value
        end
        local state = runtime_state()
        local probe_provider = false
        local runtime, _, _, policy, plan = new_runtime({
            state = state,
            runtime_provider = function()
                if probe_provider then assert(holder.f(99) == 99) end
                return state
            end,
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
        })
        local manifest = arm_manifest(policy, {
            capture_id = "capture-provider-reentry",
            arm_nonce = string.rep("b", 32),
        })
        assert(runtime:prepare(manifest))
        assert(runtime:activate(manifest.arm_nonce))
        local observed = 0
        install_defaults(runtime, plan, function(results, arguments, order)
            observed = observed + 1
            assert(holder.f(100) == 100)
            return default_extraction(results, arguments, order)
        end)
        probe_provider = true
        assert(holder.f(1) == 1)
        assert(original_calls == 3)
        assert(observed == 1)
        assert(runtime.attempted_calls.random_int == 1)
        """
    )


def test_observer_failure_is_one_reconciled_outcome(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime()
        install_defaults(runtime, plan, function() error("trace failure") end)
        assert(bindings["random_int.default"].holder.f(4) == 4)
        assert(runtime.attempted_calls.random_int == 1)
        assert(runtime.serialization_errors == 1)
        assert(#runtime.events == 0)
        """
    )


def test_malicious_extraction_metatable_cannot_replace_game_return(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime()
        install_defaults(runtime, plan, function()
            return setmetatable({}, {
                __index = function() error("metatable trap") end,
            })
        end)
        assert(bindings["random_int.default"].holder.f(7) == 7)
        assert(not runtime:is_enabled())
        assert(runtime.attempted_calls.random_int == 1)
        assert(runtime.serialization_errors == 1)
        assert(runtime.stop_reasons.observation_runtime_failed == 1)
        """
    )


def test_state_corrupting_observer_cannot_replace_game_return(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime()
        local holder = bindings["random_int.default"].holder
        local original = holder.f
        install_defaults(runtime, plan, function()
            runtime.events = nil
            error("corrupted trace state")
        end)
        assert(holder.f(11) == 11)
        assert(runtime.in_trace == false)
        assert(not runtime:is_enabled())
        assert(holder.f == original)
        """
    )


def test_cap_stops_after_exact_limit_without_phantom_drop(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime({
            policy_overrides = {max_attempts = 1},
        })
        local holder = bindings["random_int.default"].holder
        local original = holder.f
        local observed = 0
        install_defaults(runtime, plan, function(results, arguments, order)
            observed = observed + 1
            return default_extraction(results, arguments, order)
        end)
        assert(holder.f(1) == 1)
        assert(not runtime:is_enabled())
        assert(holder.f == original)
        assert(holder.f(2) == 2)
        assert(observed == 1)
        assert(runtime.attempted_calls.random_int == 1)
        assert(#runtime.events == 1)
        assert(runtime.dropped_events == 0)
        assert(runtime.stop_reasons.max_attempts == 1)
        """
    )


def test_expiry_and_identity_change_stop_before_extraction(lua):
    lua.execute(
        r"""
        local runtime, bindings, state, _, plan = activate_runtime()
        local holder = bindings["random_int.default"].holder
        local original = holder.f
        local observed = 0
        install_defaults(runtime, plan, function()
            observed = observed + 1
            return {context = {}, payload = {}}
        end)
        state.now_epoch = 1101
        assert(holder.f(1) == 1)
        assert(observed == 0)
        assert(runtime.attempted_calls.random_int == 0)
        assert(runtime.stop_reasons.capture_expired == 1)
        assert(holder.f == original)

        local runtime2, bindings2, state2, _, plan2 = activate_runtime(
            nil,
            {
                capture_id = "capture-identity-change",
                arm_nonce = string.rep("8", 32),
            }
        )
        install_defaults(runtime2, plan2, function()
            observed = observed + 1
            return {context = {}, payload = {}}
        end)
        state2.phase = "combat_player"
        assert(bindings2["random_int.default"].holder.f(2) == 2)
        assert(runtime2.attempted_calls.random_int == 1)
        assert(runtime2.filtered_events == 1)
        assert(runtime2.stop_reasons.runtime_identity_changed == 1)
        assert(observed == 0)
        """
    )


def test_provider_and_nonprimitive_failures_are_reconciled(lua):
    lua.execute(
        r"""
        local fail = false
        local state = runtime_state()
        local runtime, bindings, _, policy, plan = new_runtime({
            state = state,
            runtime_provider = function()
                if fail then error("provider failed") end
                return state
            end,
        })
        local manifest = arm_manifest(policy, {
            capture_id = "capture-provider",
            arm_nonce = string.rep("7", 32),
        })
        assert(runtime:prepare(manifest))
        assert(runtime:activate(manifest.arm_nonce))
        install_defaults(runtime, plan)
        fail = true
        assert(bindings["random_int.default"].holder.f(1) == 1)
        assert(runtime.attempted_calls.random_int == 1)
        assert(runtime.serialization_errors == 1)
        assert(runtime.stop_reasons["runtime provider failed"] == 1)

        local bad_holder = {f = function() return function() end end}
        local runtime2, _, _, _, plan2 = activate_runtime({
            hook_bindings = {
                ["random_int.default"] = {holder = bad_holder, key = "f"},
            },
        }, {
            capture_id = "capture-nonprimitive",
            arm_nonce = string.rep("6", 32),
        })
        install_defaults(runtime2, plan2)
        assert(type(bad_holder.f()) == "function")
        assert(runtime2.attempted_calls.random_int == 1)
        assert(runtime2.serialization_errors == 1)
        """
    )


def test_registry_prevents_stacking_across_real_module_reload(lua):
    lua.execute(
        r"""
        local holder = {f = function(value) return value end}
        local spec = {
            hook_bindings = {
                ["random_int.default"] = {holder = holder, key = "f"},
            },
        }
        local first, _, _, _, plan = activate_runtime(spec, {
            capture_id = "capture-first-reload",
            arm_nonce = string.rep("5", 32),
        })
        install_defaults(first, plan)
        local first_wrapper = holder.f

        MOD = assert(loadstring(MODULE_SOURCE))()
        local ok, err = pcall(function() new_runtime(spec) end)
        assert(not ok)
        assert(string.find(err, "target already registered", 1, true))
        assert(holder.f == first_wrapper)
        first:disarm()

        local third, _, _, policy3 = new_runtime(spec)
        local manifest3 = arm_manifest(policy3, {
            capture_id = "capture-third-reload",
            arm_nonce = string.rep("3", 32),
        })
        assert(third:prepare(manifest3))
        assert(third:activate(manifest3.arm_nonce))
        assert(third:install_proven_non_yielding_hook(
            "random_int.default", default_extraction
        ))
        """
    )


def test_checkpoint_requires_actual_coverage_and_expiry_disarms(lua):
    lua.execute(
        r"""
        local runtime, bindings = activate_runtime()
        local holder = bindings["random_int.default"].holder
        local original = holder.f
        local snapshot, err = runtime:checkpoint("explicit")
        assert(snapshot == nil)
        assert(err == "planned hook coverage was not installed")
        assert(not runtime:is_enabled())
        assert(holder.f == original)

        local runtime2, bindings2, state2, _, plan2 = activate_runtime(nil, {
            capture_id = "capture-expired-checkpoint",
            arm_nonce = string.rep("9", 32),
        })
        local holder2 = bindings2["random_int.default"].holder
        local original2 = holder2.f
        install_defaults(runtime2, plan2)
        state2.now_epoch = 1101
        snapshot, err = runtime2:checkpoint("explicit")
        assert(snapshot == nil and err == "checkpoint outside capture window")
        assert(not runtime2:is_enabled())
        assert(holder2.f == original2)
        """
    )


def test_checkpoint_rejects_detached_planned_wrapper(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime(nil, {
            capture_id = "capture-detached-hook",
            arm_nonce = string.rep("c", 32),
        })
        install_defaults(runtime, plan)
        local holder = bindings["random_int.default"].holder
        local replacement = function(value) return value end
        holder.f = replacement
        local snapshot, err = runtime:checkpoint("explicit")
        assert(snapshot == nil)
        assert(err == "planned hook coverage was not installed")
        assert(holder.f == replacement)
        assert(runtime.restore_conflicts == 1)
        """
    )


def test_checkpoint_contains_bound_policy_coverage_and_reconciles(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, manifest, plan = activate_runtime()
        install_defaults(runtime, plan)
        assert(bindings["random_int.default"].holder.f(3) == 3)
        local snapshot = assert(runtime:checkpoint("explicit"))
        assert(snapshot.capture_id == manifest.capture_id)
        assert(snapshot.checkpoint_seq == manifest.checkpoint_seq)
        assert(snapshot.started_epoch == 1001)
        assert(snapshot.master_seed == -17)
        assert(snapshot.config.max_events == manifest.max_events)
        assert(snapshot.hook_coverage[7].target == "_G.random_int")
        assert(snapshot.hook_coverage[7].hook_id == nil)
        assert(snapshot.hook_coverage[7].status == "installed")
        assert(snapshot.summary.accepted_events == 1)
        assert(snapshot.attempted_calls.random_int == 1)
        local outcomes = snapshot.summary.accepted_events
            + snapshot.summary.dropped_events
            + snapshot.summary.filtered_events
            + snapshot.summary.serialization_errors
        assert(outcomes == snapshot.attempted_calls.random_int)
        local repeated, err = runtime:checkpoint("explicit")
        assert(repeated == nil and err == "capture already checkpointed")
        """
    )


def test_checkpoint_preimages_match_python_digest_contract(lua):
    coverage = [
        {
            "event_kind": kind,
            "target": f"_G.{kind}",
            "target_kind": "lua_global",
            "status": "installed" if kind == "random_int" else "disabled",
            "source_sha256": "3" * 64,
        }
        for kind in (
            "enemy_action_selected",
            "enemy_candidate",
            "enemy_target_score",
            "get_skill_effect",
            "get_target_area",
            "random_bool",
            "random_int",
            "score_positioning",
        )
    ]
    config = TraceConfig(
        enabled=True,
        allowed_phases=("combat_enemy",),
        max_events=16,
        max_events_per_turn=16,
        max_event_bytes=4096,
        max_total_event_bytes=32768,
        max_bundle_bytes=8 * 1024 * 1024,
    )
    lua.globals().CONFIG_DIGEST = trace_config_sha256(config)
    lua.globals().COVERAGE_DIGEST = hook_coverage_sha256(coverage)
    snapshot = lua.execute(
        r"""
        local runtime, _, _, _, plan = activate_runtime(nil, {
            capture_id = "capture-python-preimage",
            arm_nonce = string.rep("d", 32),
        })
        install_defaults(runtime, plan)
        return assert(runtime:checkpoint("explicit"))
        """
    )
    converted = _lua_to_python(snapshot)
    assert converted["config"] == config.to_dict()
    assert converted["hook_coverage"] == coverage
    assert trace_config_sha256(config) == converted["config_sha256"]
    assert (
        hook_coverage_sha256(converted["hook_coverage"])
        == converted["hook_coverage_sha256"]
    )


def test_json_escape_upper_bound_is_conservative(lua):
    snapshot = lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime(nil, {
            capture_id = "capture-json-escaping",
            arm_nonce = string.rep("1", 32),
        })
        local adversarial = string.rep(string.char(34, 92, 10), 20)
        install_defaults(runtime, plan, function(results, arguments, order)
            return {
                context = {},
                payload = {
                    call_order = order,
                    blob = adversarial,
                },
            }
        end)
        bindings["random_int.default"].holder.f(1)
        return assert(runtime:checkpoint("explicit"))
        """
    )
    converted = _lua_to_python(snapshot)
    event = converted["events"][0]
    canonical_bytes = len(
        json.dumps(
            event,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ) + 1
    assert canonical_bytes <= converted["config"]["max_event_bytes"]
    assert canonical_bytes <= converted["summary"]["event_byte_upper_bound"]


def test_full_event_accounting_keeps_near_hard_cap_checkpointable(lua):
    lua.execute(
        r"""
        local runtime, bindings, _, _, plan = activate_runtime({
            policy_overrides = {
                max_events = 4096,
                max_events_per_turn = 1024,
                max_event_bytes = 65536,
                max_total_event_bytes = 4 * 1024 * 1024,
                max_attempts = 16384,
            },
        }, {
            capture_id = "capture-max-envelope",
            arm_nonce = string.rep("a", 32),
        })
        install_defaults(runtime, plan, function(results, arguments, order)
            return {
                context = {},
                payload = {
                    call_order = order,
                    blob = string.rep("x", 3900),
                },
            }
        end)
        local holder = bindings["random_int.default"].holder
            for index = 1, 1024 do
            holder.f(index)
            if not runtime:is_enabled() then break end
        end
        assert(runtime.event_byte_upper_bound > 3 * 1024 * 1024)
        local snapshot, err = runtime:checkpoint("explicit")
        assert(snapshot ~= nil, tostring(err))
        local attempts = snapshot.attempted_calls.random_int
        local outcomes = snapshot.summary.accepted_events
            + snapshot.summary.dropped_events
            + snapshot.summary.filtered_events
            + snapshot.summary.serialization_errors
        assert(attempts == outcomes)
        """
    )
