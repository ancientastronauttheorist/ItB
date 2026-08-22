"""Lua 5.1 conformance tests for the one-family callback controller."""

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

PRELUDE = r"""
function sha(character) return string.rep(character, 64) end
function point(x, y) return {x = x, y = y} end
function point_list(values)
    return {
        size = function() return #values end,
        index = function(_, index) return values[index] end,
    }
end
function effect_list(values)
    return {
        size = function() return #values end,
        index = function(_, index) return values[index] end,
    }
end

local root_a = {}
local root_b = {}
local root_c = {}
local base = {}
local override = {}
base.GetTargetArea = function(_, origin)
    return point_list({origin, point(7, 6)}), nil, "area-tail"
end
override.GetTargetArea = function(_, origin)
    return point_list({point(origin.x + 1, origin.y)}), nil, "override-tail"
end
base.GetTargetScore = function() return 7.5, nil, "score-tail" end
base.GetSkillEffect = function()
    return {
        effect = effect_list({{
            iDamage = 2,
            iPush = 1,
            sPawn = "Spiderling1",
            loc = point(4, 5),
        }}),
        q_effect = effect_list({{
            iSmoke = 1,
            bHide = false,
            piTarget = point(6, 6),
        }}),
    }, nil, "effect-tail"
end
setmetatable(root_a, {__index = base})
setmetatable(root_b, {__index = base})
setmetatable(root_c, {__index = override})

local positioning = function(position, pawn)
    return position.x + position.y + pawn:GetId() / 1000
end
ScorePositioning = positioning
Pawn = {
    GetId = function() return 42 end,
    GetSpace = function() return point(1, 2) end,
}

BINDING_DOCUMENT = {
    schema_version = 1,
    runtime_version = "observatory-callback-bindings/1",
    slots = {
        {slot_id = "slot-0001", method = "GetTargetArea", function_id = "fn-0001", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}},
        {slot_id = "slot-0002", method = "GetTargetArea", function_id = "fn-0002", root_ids = {"enemy.skill.SkillC"}},
        {slot_id = "slot-0003", method = "GetTargetScore", function_id = "fn-0003", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}},
        {slot_id = "slot-0004", method = "GetSkillEffect", function_id = "fn-0004", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}},
        {slot_id = "slot-0005", method = "ScorePositioning", function_id = "fn-0005", root_ids = {"global.ScorePositioning"}},
    },
}

LIVE_BINDINGS = {
    {slot_id = "slot-0001", holder = base, key = "GetTargetArea", original = base.GetTargetArea, function_id = "fn-0001", method = "GetTargetArea", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}, root_objects = {root_a, root_b}},
    {slot_id = "slot-0002", holder = override, key = "GetTargetArea", original = override.GetTargetArea, function_id = "fn-0002", method = "GetTargetArea", root_ids = {"enemy.skill.SkillC"}, root_objects = {root_c}},
    {slot_id = "slot-0003", holder = base, key = "GetTargetScore", original = base.GetTargetScore, function_id = "fn-0003", method = "GetTargetScore", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}, root_objects = {root_a, root_b}},
    {slot_id = "slot-0004", holder = base, key = "GetSkillEffect", original = base.GetSkillEffect, function_id = "fn-0004", method = "GetSkillEffect", root_ids = {"enemy.skill.SkillA", "enemy.skill.SkillB"}, root_objects = {root_a, root_b}},
    {slot_id = "slot-0005", holder = _G, key = "ScorePositioning", original = positioning, function_id = "fn-0005", method = "ScorePositioning", root_ids = {"global.ScorePositioning"}, root_objects = {_G}},
}

ROOT_A = root_a
ROOT_B = root_b
ROOT_C = root_c
BASE = base
OVERRIDE = override

local METHOD_KIND = {
    GetTargetArea = "get_target_area",
    GetTargetScore = "enemy_target_score",
    GetSkillEffect = "get_skill_effect",
    ScorePositioning = "score_positioning",
}

function target_for(slot)
    return "runtime.callback." .. slot.slot_id .. "." .. slot.method .. "." .. slot.function_id
end

function packet_for(installed_kind)
    local plan = {}
    local covered = {}
    for index, slot in ipairs(BINDING_DOCUMENT.slots) do
        local kind = METHOD_KIND[slot.method]
        covered[kind] = true
        plan[#plan + 1] = {
            hook_id = "callback." .. slot.slot_id,
            event_kind = kind,
            target = target_for(slot),
            target_kind = slot.method == "ScorePositioning" and "lua_global" or "lua_method",
            status = kind == installed_kind and "installed" or "disabled",
            source_sha256 = sha(tostring(index)),
        }
    end
    for _, kind in ipairs({"enemy_action_selected", "enemy_candidate", "random_bool", "random_int"}) do
        plan[#plan + 1] = {
            hook_id = "disabled." .. kind,
            event_kind = kind,
            target = "disabled." .. kind,
            target_kind = (kind == "random_bool" or kind == "random_int") and "lua_global" or "native_boundary",
            status = "disabled",
            source_sha256 = sha("a"),
        }
    end
    table.sort(plan, function(left, right)
        if left.event_kind == right.event_kind then return left.target < right.target end
        return left.event_kind < right.event_kind
    end)
    local policy = {
        expected_phase = "combat_enemy",
        max_events = 32,
        max_events_per_turn = 32,
        max_event_bytes = 16384,
        max_total_event_bytes = 262144,
        max_attempts = 128,
        max_bundle_bytes = 8 * 1024 * 1024,
        allowed_kinds = {installed_kind},
    }
    local manifest = {
        schema_version = 1,
        capture_id = "callback-capture-001",
        checkpoint_seq = 2,
        arm_nonce = string.rep("f", 32),
        controller_version = "observatory-callback-controller/1",
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
        trusted = {
            controller_sha256 = sha("a"),
            installed_modloader_sha256 = sha("b"),
            build_identity_sha256 = sha("c"),
            config_sha256 = sha("d"),
            hook_coverage_sha256 = sha("e"),
        },
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

function new_controller(writer)
    return BOUND.new({
        runtime_provider = runtime_state,
        binding_document = BINDING_DOCUMENT,
        live_bindings = LIVE_BINDINGS,
        raw_writer = writer or function() return true end,
        globals = _G,
    })
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


def test_construction_and_prepare_are_inert(lua):
    lua.execute(
        r"""
        local originals = {}
        for index, binding in ipairs(LIVE_BINDINGS) do originals[index] = binding.original end
        local controller = new_controller()
        for index, binding in ipairs(LIVE_BINDINGS) do assert(binding.holder[binding.key] == originals[index]) end
        assert(controller:prepare(packet_for("get_target_area")))
        for index, binding in ipairs(LIVE_BINDINGS) do assert(binding.holder[binding.key] == originals[index]) end
        """
    )

def test_get_target_area_wraps_every_defining_slot_and_restores_exactly(lua):
    lua.execute(
        r"""
        local written = nil
        local controller = new_controller(function(snapshot) written = snapshot; return true end)
        local first_original = BASE.GetTargetArea
        local second_original = OVERRIDE.GetTargetArea
        local packet = packet_for("get_target_area")
        assert(controller:prepare(packet))
        assert(controller:activate(string.rep("f", 32)))
        assert(BASE.GetTargetArea ~= first_original)
        assert(OVERRIDE.GetTargetArea ~= second_original)

        local area, middle, tail = ROOT_A:GetTargetArea(point(2, 3))
        assert(area:size() == 2 and middle == nil and tail == "area-tail")
        local area2, middle2, tail2 = ROOT_C:GetTargetArea(point(3, 4))
        assert(area2:size() == 1 and middle2 == nil and tail2 == "override-tail")
        assert(controller:checkpoint("explicit"))
        assert(BASE.GetTargetArea == first_original)
        assert(OVERRIDE.GetTargetArea == second_original)
        assert(#written.events == 2)
        assert(written.events[1].payload.skill_id == "SkillA")
        assert(written.events[1].payload.call_order == 0)
        assert(written.events[1].payload.target_area[2][1] == 7)
        assert(written.events[2].payload.skill_id == "SkillC")
        assert(written.events[2].payload.call_order == 1)
        """
    )


def test_score_positioning_and_target_score_preserve_signature_fields(lua):
    lua.execute(
        r"""
        local written = nil
        local original = ScorePositioning
        local controller = new_controller(function(snapshot) written = snapshot; return true end)
        assert(controller:prepare(packet_for("score_positioning")))
        assert(controller:activate(string.rep("f", 32)))
        local score = ScorePositioning(point(3, 4), Pawn)
        assert(score == 7.042)
        assert(controller:checkpoint("explicit"))
        assert(ScorePositioning == original)
        assert(written.events[1].payload.pawn_uid == 42)
        assert(written.events[1].payload.position[1] == 3)
        assert(written.events[1].payload.candidate_order == 0)

        written = nil
        local target_controller = new_controller(function(snapshot) written = snapshot; return true end)
        local packet = packet_for("enemy_target_score")
        packet.manifest.capture_id = "callback-capture-score"
        packet.manifest.arm_nonce = string.rep("e", 32)
        assert(target_controller:prepare(packet))
        assert(target_controller:activate(string.rep("e", 32)))
        local result, middle, tail = ROOT_B:GetTargetScore(point(5, 4), point(5, 1))
        assert(result == 7.5 and middle == nil and tail == "score-tail")
        assert(target_controller:checkpoint("explicit"))
        local payload = written.events[1].payload
        assert(payload.representation == "get_target_score_arguments")
        assert(payload.pawn_space[1] == 1 and payload.pawn_space[2] == 2)
        assert(payload.p1[1] == 5 and payload.p2[2] == 1)
        assert(payload.score == 7.5 and payload.call_order == 0)
        """
    )


def test_get_skill_effect_extracts_only_bounded_primitives(lua):
    lua.execute(
        r"""
        local written = nil
        local original = BASE.GetSkillEffect
        local controller = new_controller(function(snapshot) written = snapshot; return true end)
        assert(controller:prepare(packet_for("get_skill_effect")))
        assert(controller:activate(string.rep("f", 32)))
        local effect, middle, tail = ROOT_A:GetSkillEffect(point(2, 2), point(4, 5))
        assert(effect.effect:size() == 1 and middle == nil and tail == "effect-tail")
        assert(controller:checkpoint("explicit"))
        assert(BASE.GetSkillEffect == original)
        local payload = written.events[1].payload
        assert(payload.representation == "raw_opaque_primitives")
        assert(payload.primitive_count == 7)
        assert(payload.primitive_summary.effect[1].index == 0)
        assert(payload.primitive_summary.effect[1].fields[1].name == "iDamage")
        assert(payload.primitive_summary.effect[1].fields[4].name == "loc")
        assert(payload.primitive_summary.q_effect[1].fields[1].name == "bHide")
        assert(payload.primitive_summary.q_effect[1].fields[3].name == "piTarget")
        """
    )


def test_adapter_failure_is_swallowed_without_changing_game_return(lua):
    lua.execute(
        r"""
        local original = BASE.GetTargetArea
        BASE.GetTargetArea = function() return {not_a_point_list = true}, nil, "tail" end
        LIVE_BINDINGS[1].original = BASE.GetTargetArea
        local controller = new_controller()
        assert(controller:prepare(packet_for("get_target_area")))
        assert(controller:activate(string.rep("f", 32)))
        local value, middle, tail = ROOT_A:GetTargetArea(point(1, 1))
        assert(value.not_a_point_list and middle == nil and tail == "tail")
        local snapshot = assert(controller.runtime:checkpoint("explicit"))
        assert(snapshot.attempted_calls.get_target_area == 1)
        assert(snapshot.summary.serialization_errors == 1)
        assert(#snapshot.events == 0)
        BASE.GetTargetArea = original
        LIVE_BINDINGS[1].original = original
        """
    )


def test_original_error_object_identity_and_partial_plan_failure(lua):
    lua.execute(
        r"""
        local sentinel = {}
        local original = BASE.GetTargetScore
        BASE.GetTargetScore = function() error(sentinel) end
        LIVE_BINDINGS[3].original = BASE.GetTargetScore
        local controller = new_controller()
        assert(controller:prepare(packet_for("enemy_target_score")))
        assert(controller:activate(string.rep("f", 32)))
        local ok, caught = pcall(ROOT_A.GetTargetScore, ROOT_A, point(1, 1), point(2, 2))
        assert(not ok and caught == sentinel)
        controller:disarm()
        assert(BASE.GetTargetScore == LIVE_BINDINGS[3].original)
        BASE.GetTargetScore = original
        LIVE_BINDINGS[3].original = original

        local partial = packet_for("get_target_area")
        for _, entry in ipairs(partial.hook_plan) do
            if entry.hook_id == "callback.slot-0002" then entry.status = "disabled" end
        end
        partial.policy.allowed_kinds = {"get_target_area"}
        partial.manifest.allowed_kinds = {"get_target_area"}
        local controller2 = new_controller()
        local prepared, err = controller2:prepare(partial)
        assert(not prepared and err == "installed callback family coverage is incomplete")
        assert(BASE.GetTargetArea == LIVE_BINDINGS[1].original)
        assert(OVERRIDE.GetTargetArea == LIVE_BINDINGS[2].original)
        """
    )
