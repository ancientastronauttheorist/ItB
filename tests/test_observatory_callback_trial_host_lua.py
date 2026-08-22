"""Lua 5.1 lifecycle tests for the natural callback trial host."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip("exact Lua 5.1 harness requires lupa.lua51", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = (ROOT / "src" / "bridge" / "observatory_trace.lua").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (
    ROOT / "src" / "bridge" / "observatory_callback_controller.lua"
).read_text(encoding="utf-8")
HOST_SOURCE = (
    ROOT / "src" / "bridge" / "observatory_callback_trial_host.lua"
).read_text(encoding="utf-8")


PRELUDE = r"""
function sha(value) return string.rep(value, 64) end
function point(x, y) return {x = x, y = y} end

Pawn = {GetId = function() return 17 end}
local original_positioning = function(position, pawn)
    return position.x * 10 + position.y + pawn:GetId() / 100
end
ScorePositioning = original_positioning
ORIGINAL_POSITIONING = original_positioning

BINDING_DOCUMENT = {
    schema_version = 1,
    runtime_version = "observatory-callback-bindings/1",
    method_order = {"GetTargetArea", "GetTargetScore", "GetSkillEffect", "ScorePositioning"},
    identity_manifest = {},
    roots = {},
    slots = {{
        slot_id = "slot-0001",
        method = "ScorePositioning",
        function_id = "fn-0001",
        root_ids = {"global.ScorePositioning"},
    }},
    summary = {root_count = 1, method_count = 4, function_count = 1, slot_count = 1},
}

LIVE_BINDINGS = {{
    slot_id = "slot-0001",
    holder = _G,
    key = "ScorePositioning",
    original = original_positioning,
    function_id = "fn-0001",
    method = "ScorePositioning",
    root_ids = {"global.ScorePositioning"},
    root_objects = {_G},
}}

MANIFEST_MODULE = {}
BINDINGS_MODULE = {
    enumerate = function()
        return BINDING_DOCUMENT, LIVE_BINDINGS
    end,
}

function deep_copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, child in pairs(value) do result[deep_copy(key)] = deep_copy(child) end
    return result
end

local plan = {}
for _, kind in ipairs({
    "enemy_action_selected",
    "enemy_candidate",
    "enemy_target_score",
    "get_skill_effect",
    "get_target_area",
    "random_bool",
    "random_int",
}) do
    plan[#plan + 1] = {
        hook_id = "disabled." .. kind,
        event_kind = kind,
        target = "disabled." .. kind,
        target_kind = (kind == "random_bool" or kind == "random_int")
            and "lua_global" or "native_boundary",
        status = "disabled",
        source_sha256 = sha("a"),
    }
end
plan[#plan + 1] = {
    hook_id = "callback.slot-0001",
    event_kind = "score_positioning",
    target = "runtime.callback.slot-0001.ScorePositioning.fn-0001",
    target_kind = "lua_global",
    status = "installed",
    source_sha256 = sha("b"),
}

local policy = {
    expected_phase = "combat_enemy",
    max_events = 32,
    max_events_per_turn = 32,
    max_event_bytes = 16384,
    max_total_event_bytes = 262144,
    max_attempts = 64,
    max_bundle_bytes = 4 * 1024 * 1024,
    allowed_kinds = {"score_positioning"},
}
local manifest = {
    schema_version = 1,
    capture_id = "callback-host-001",
    checkpoint_seq = 0,
    arm_nonce = string.rep("f", 32),
    controller_version = "observatory-callback-controller/1",
    controller_sha256 = sha("1"),
    installed_modloader_sha256 = sha("2"),
    build_identity_sha256 = sha("3"),
    expected_mission_id = "Mission_Test",
    expected_turn = 2,
    expected_phase = "combat_enemy",
    timeline_fingerprint = sha("4"),
    master_seed = -17,
    region_id = "Archive_A",
    ai_seed_fingerprint = sha("5"),
    config_sha256 = sha("6"),
    hook_coverage_sha256 = sha("7"),
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
PACKET = {
    arm_packet_schema_version = 1,
    build_identity = {platform = "windows"},
    manifest = manifest,
    trusted = {
        controller_sha256 = sha("1"),
        installed_modloader_sha256 = sha("2"),
        build_identity_sha256 = sha("3"),
        config_sha256 = sha("6"),
        hook_coverage_sha256 = sha("7"),
    },
    policy = policy,
    hook_plan = plan,
}
CAPSULE = {
    schema_version = 1,
    kind = "observatory_callback_trial_capsule",
    capture_track = "owner_local_modified",
    arm_packet_sha256 = sha("8"),
    packet = PACKET,
    callback_family = "score_positioning",
    binding_manifest_sha256 = sha("9"),
    binding_manifest = deep_copy(BINDING_DOCUMENT),
    callback_join_sha256 = sha("a"),
    callback_join = {},
    expected_save = {
        mission_id = "Mission_Test",
        mission_slot = "island0_mission1",
        turn = 2,
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed = 81,
    },
}

function runtime_state()
    return {
        now_epoch = 1001,
        mission_id = "Mission_Test",
        turn = 2,
        phase = "combat_enemy",
        timeline_fingerprint = sha("4"),
        master_seed = -17,
        region_id = "Archive_A",
        ai_seed_fingerprint = sha("5"),
    }
end

function new_host(condition, raw_writer, result_writer)
    return HOST.new({
        condition = condition,
        activation_nonce = string.rep("f", 32),
        capsule_sha256 = sha("b"),
        capsule = CAPSULE,
        controller_module = CONTROLLER,
        callback_manifest_module = MANIFEST_MODULE,
        callback_bindings_module = BINDINGS_MODULE,
        live_state_provider = runtime_state,
        raw_writer = raw_writer or function() return true end,
        result_writer = result_writer or function() return true end,
        globals = _G,
    })
end
"""


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime_module = runtime.execute(RUNTIME_SOURCE)
    controller_module = runtime.execute(CONTROLLER_SOURCE).bind_runtime(runtime_module)
    host_module = runtime.execute(HOST_SOURCE)
    runtime.globals().CONTROLLER = controller_module
    runtime.globals().HOST = host_module
    runtime.execute(PRELUDE)
    return runtime


def test_exact_hook_captures_natural_call_and_restores(lua):
    lua.execute(
        r"""
        local raw = nil
        local result = nil
        local host = new_host(
            "exact_hook",
            function(snapshot) raw = snapshot; return true end,
            function(document) result = document; return true end
        )
        assert(ScorePositioning == ORIGINAL_POSITIONING)
        assert(host:step("next_turn") == "capturing")
        assert(ScorePositioning ~= ORIGINAL_POSITIONING)
        local score = ScorePositioning(point(3, 4), Pawn)
        assert(score == 34.17)
        assert(host:step("base_update_after") == "complete")
        assert(ScorePositioning == ORIGINAL_POSITIONING)
        assert(raw ~= nil and #raw.events == 1)
        assert(raw.events[1].payload.position[1] == 3)
        assert(result.status == "complete")
        assert(result.raw_written and result.raw_event_count == 1)
        assert(result.attempted_calls == 1)
        assert(result.slots_restored)
        assert(result.controller_status.written)
        """
    )


def test_control_uses_same_boundary_without_installing_or_writing(lua):
    lua.execute(
        r"""
        local wrote_raw = false
        local result = nil
        local host = new_host(
            "control",
            function() wrote_raw = true; return true end,
            function(document) result = document; return true end
        )
        assert(host:step("next_turn") == "capturing")
        assert(ScorePositioning == ORIGINAL_POSITIONING)
        assert(ScorePositioning(point(2, 1), Pawn) == 21.17)
        assert(host:step("base_update_after") == "complete")
        assert(not wrote_raw and not result.raw_written)
        assert(result.raw_event_count == 0 and result.attempted_calls == 0)
        assert(result.slots_restored)
        """
    )


def test_live_binding_drift_fails_before_any_hook(lua):
    lua.execute(
        r"""
        local old = BINDING_DOCUMENT.slots[1].function_id
        BINDING_DOCUMENT.slots[1].function_id = "fn-9999"
        local ok, err = pcall(new_host, "exact_hook")
        assert(not ok)
        assert(string.find(tostring(err), "live callback bindings do not match capsule", 1, true))
        assert(ScorePositioning == ORIGINAL_POSITIONING)
        BINDING_DOCUMENT.slots[1].function_id = old
        """
    )


def test_writer_failure_still_restores_all_slots(lua):
    lua.execute(
        r"""
        local result = nil
        local host = new_host(
            "exact_hook",
            function() return false, "disk rejected" end,
            function(document) result = document; return true end
        )
        assert(host:step("next_turn") == "capturing")
        ScorePositioning(point(1, 1), Pawn)
        local status, err = host:step("base_update_after")
        assert(status == "failed")
        assert(ScorePositioning == ORIGINAL_POSITIONING)
        assert(result.status == "failed" and result.slots_restored)
        assert(string.find(result.error, "disk rejected", 1, true))
        """
    )
