-- Explicit one-family controller for Lua callback-boundary experiments.
--
-- Loading and constructing this module perform no I/O and install no hook.
-- The caller supplies the inert callback-slot document and its live-only
-- bindings, then separately invokes prepare(), activate(nonce), and
-- checkpoint().  Every resolved slot for exactly one callback family is
-- wrapped together so inherited implementations are neither missed nor
-- stacked.  Adapters run only after the original callback returns.

local M = {}

M.VERSION = "observatory-callback-controller/1"
M.MAX_TARGET_AREA = 64
M.MAX_EFFECT_RECORDS_PER_LIST = 128

local PACKET_FIELDS = {
    arm_packet_schema_version = true,
    build_identity = true,
    manifest = true,
    trusted = true,
    policy = true,
    hook_plan = true,
}

local OPTION_FIELDS = {
    runtime_provider = true,
    binding_document = true,
    live_bindings = true,
    raw_writer = true,
    globals = true,
}

local SLOT_FIELDS = {
    slot_id = true,
    method = true,
    function_id = true,
    root_ids = true,
}

local LIVE_FIELDS = {
    slot_id = true,
    holder = true,
    key = true,
    original = true,
    function_id = true,
    method = true,
    root_ids = true,
    root_objects = true,
}

local METHOD_TO_KIND = {
    GetTargetArea = "get_target_area",
    GetTargetScore = "enemy_target_score",
    GetSkillEffect = "get_skill_effect",
    ScorePositioning = "score_positioning",
}

local KIND_TO_METHOD = {
    get_target_area = "GetTargetArea",
    enemy_target_score = "GetTargetScore",
    get_skill_effect = "GetSkillEffect",
    score_positioning = "ScorePositioning",
}

local EFFECT_FIELDS = {
    "bEvacuate",
    "bHide",
    "bHideIcon",
    "bHidePath",
    "bKO_Effect",
    "bSimpleMark",
    "fDelay",
    "iAcid",
    "iCrack",
    "iDamage",
    "iFire",
    "iFrozen",
    "iInjure",
    "iPawnTeam",
    "iPush",
    "iShield",
    "iSmoke",
    "iTerrain",
    "sAnimation",
    "sImageMark",
    "sItem",
    "sPawn",
    "sScript",
    "sSound",
}

local EFFECT_POINT_FIELDS = {
    "loc",
    "piOrigin",
    "piTarget",
}

local function safe_disarm(runtime)
    pcall(runtime.disarm, runtime)
end

local function exact_fields(value, expected)
    if type(value) ~= "table" then return false end
    for key, _ in pairs(expected) do
        if rawget(value, key) == nil then return false end
    end
    for key, _ in pairs(value) do
        if not expected[key] then return false end
    end
    return true
end

local function integer(value)
    return type(value) == "number" and value == math.floor(value)
end

local function finite_number(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

local function exact_array(value, length)
    if type(value) ~= "table" or #value ~= length then return false end
    for index = 1, length do
        if rawget(value, index) == nil then return false end
    end
    for key, _ in pairs(value) do
        if not integer(key) or key < 1 or key > length then return false end
    end
    return true
end

local function same_array(left, right)
    if type(left) ~= "table" or type(right) ~= "table" then return false end
    if not exact_array(left, #left) or not exact_array(right, #right)
        or #left ~= #right then
        return false
    end
    for index = 1, #left do
        if left[index] ~= right[index] then return false end
    end
    return true
end

local function slot_target(slot)
    return "runtime.callback."
        .. slot.slot_id .. "."
        .. slot.method .. "."
        .. slot.function_id
end

local function slot_hook_id(slot)
    return "callback." .. slot.slot_id
end

local function slot_target_kind(slot)
    if slot.method == "ScorePositioning"
        and #slot.root_ids == 1
        and slot.root_ids[1] == "global.ScorePositioning" then
        return "lua_global"
    end
    return "lua_method"
end

local function call_method(object, name, ...)
    local arguments = {...}
    local ok, result = pcall(function()
        local method = object[name]
        if type(method) ~= "function" then error("missing method") end
        return method(object, unpack(arguments))
    end)
    if not ok then error("callback adapter " .. name .. " failed") end
    return result
end

local function coordinate(value)
    local ok, x, y = pcall(function() return value.x, value.y end)
    if not ok
        or not integer(x)
        or not integer(y)
        or x < 0 or x > 7
        or y < 0 or y > 7 then
        error("callback adapter received an invalid board point")
    end
    return {x, y}
end

local function pawn_uid(pawn)
    local uid = call_method(pawn, "GetId")
    if not integer(uid) or uid < 0 then
        error("callback adapter received an invalid pawn ID")
    end
    return uid
end

local function pawn_space(pawn)
    return coordinate(call_method(pawn, "GetSpace"))
end

local function skill_id(root_id)
    local prefix = "enemy.skill."
    if string.sub(root_id, 1, string.len(prefix)) == prefix then
        local result = string.sub(root_id, string.len(prefix) + 1)
        if result ~= "" then return result end
    end
    return root_id
end

local function binding_root_id(binding, object)
    for index = 1, #binding.root_objects do
        if binding.root_objects[index] == object then
            return binding.root_ids[index]
        end
    end
    error("callback receiver is outside the armed root set")
end

local function target_area(value)
    local size = call_method(value, "size")
    if not integer(size) or size < 0 or size > M.MAX_TARGET_AREA then
        error("callback target area exceeds its cap")
    end
    local result = {}
    for index = 1, size do
        result[index] = coordinate(call_method(value, "index", index))
    end
    return result
end

local function optional_primitive(value, name)
    local ok, property = pcall(function() return value[name] end)
    if not ok then return nil end
    local kind = type(property)
    if kind == "boolean" or kind == "string" then return property end
    if kind == "number" and finite_number(property) then return property end
    return nil
end

local function optional_point(value, name)
    local ok, property = pcall(function() return value[name] end)
    if not ok or property == nil then return nil end
    local converted_ok, converted = pcall(coordinate, property)
    if converted_ok then return converted end
    return nil
end

local function effect_list(value)
    local size = call_method(value, "size")
    if not integer(size)
        or size < 0
        or size > M.MAX_EFFECT_RECORDS_PER_LIST then
        error("callback skill effect list exceeds its cap")
    end
    local result = {}
    local primitive_count = 0
    for index = 1, size do
        local item = call_method(value, "index", index)
        local fields = {}
        for _, name in ipairs(EFFECT_FIELDS) do
            local primitive = optional_primitive(item, name)
            if primitive ~= nil then
                fields[#fields + 1] = {name = name, value = primitive}
                primitive_count = primitive_count + 1
            end
        end
        for _, name in ipairs(EFFECT_POINT_FIELDS) do
            local point = optional_point(item, name)
            if point ~= nil then
                fields[#fields + 1] = {name = name, value = point}
                primitive_count = primitive_count + 1
            end
        end
        result[index] = {
            index = index - 1,
            fields = fields,
        }
    end
    return result, primitive_count
end

local function skill_effect_summary(value)
    local ok, effect, queued = pcall(function()
        return value.effect, value.q_effect
    end)
    if not ok or effect == nil or queued == nil then
        error("callback adapter received an invalid SkillEffect")
    end
    local instant, instant_count = effect_list(effect)
    local delayed, delayed_count = effect_list(queued)
    return {
        effect = instant,
        q_effect = delayed,
    }, instant_count + delayed_count
end

local function current_pawn(globals)
    local pawn = rawget(globals, "Pawn")
    if pawn == nil then error("callback adapter has no current Pawn") end
    return pawn
end

local function callback_adapter(plan, binding, globals)
    if plan.event_kind == "score_positioning" then
        return function(results, arguments, call_order)
            if results.n < 1 or arguments.n < 2
                or not finite_number(results[1]) then
                error("invalid ScorePositioning boundary")
            end
            return {
                context = {
                    call_site = plan.target,
                    source = binding.function_id,
                },
                payload = {
                    pawn_uid = pawn_uid(arguments[2]),
                    candidate_order = call_order,
                    position = coordinate(arguments[1]),
                    score = results[1],
                },
            }
        end
    end
    if plan.event_kind == "get_target_area" then
        return function(results, arguments, call_order)
            if results.n < 1 or arguments.n < 2 then
                error("invalid GetTargetArea boundary")
            end
            local root_id = binding_root_id(binding, arguments[1])
            local pawn = current_pawn(globals)
            return {
                context = {
                    call_site = plan.target,
                    source = binding.function_id,
                },
                payload = {
                    payload_version = 1,
                    representation = "coordinate_list",
                    pawn_uid = pawn_uid(pawn),
                    skill_id = skill_id(root_id),
                    origin = coordinate(arguments[2]),
                    target_area = target_area(results[1]),
                    call_order = call_order,
                },
            }
        end
    end
    if plan.event_kind == "enemy_target_score" then
        return function(results, arguments, call_order)
            if results.n < 1 or arguments.n < 3
                or not finite_number(results[1]) then
                error("invalid GetTargetScore boundary")
            end
            local root_id = binding_root_id(binding, arguments[1])
            local pawn = current_pawn(globals)
            return {
                context = {
                    call_site = plan.target,
                    source = binding.function_id,
                },
                payload = {
                    payload_version = 1,
                    representation = "get_target_score_arguments",
                    pawn_uid = pawn_uid(pawn),
                    skill_id = skill_id(root_id),
                    pawn_space = pawn_space(pawn),
                    p1 = coordinate(arguments[2]),
                    p2 = coordinate(arguments[3]),
                    call_order = call_order,
                    score = results[1],
                },
            }
        end
    end
    if plan.event_kind == "get_skill_effect" then
        return function(results, arguments, call_order)
            if results.n < 1 or arguments.n < 3 then
                error("invalid GetSkillEffect boundary")
            end
            local root_id = binding_root_id(binding, arguments[1])
            local pawn = current_pawn(globals)
            local summary, primitive_count = skill_effect_summary(results[1])
            return {
                context = {
                    call_site = plan.target,
                    source = binding.function_id,
                },
                payload = {
                    payload_version = 1,
                    representation = "raw_opaque_primitives",
                    pawn_uid = pawn_uid(pawn),
                    skill_id = skill_id(root_id),
                    origin = coordinate(arguments[2]),
                    target = coordinate(arguments[3]),
                    call_order = call_order,
                    primitive_count = primitive_count,
                    primitive_summary = summary,
                },
            }
        end
    end
    return nil
end

local function validate_bindings(document, live_bindings)
    if type(document) ~= "table"
        or document.schema_version ~= 1
        or document.runtime_version ~= "observatory-callback-bindings/1"
        or type(document.slots) ~= "table"
        or type(live_bindings) ~= "table"
        or #document.slots < 1
        or #document.slots ~= #live_bindings then
        return nil, "invalid callback binding manifest"
    end
    local slots = {}
    for index, slot in ipairs(document.slots) do
        local live = live_bindings[index]
        local expected_id = string.format("slot-%04d", index)
        if not exact_fields(slot, SLOT_FIELDS)
            or slot.slot_id ~= expected_id
            or not METHOD_TO_KIND[slot.method]
            or type(slot.function_id) ~= "string"
            or slot.function_id == ""
            or type(slot.root_ids) ~= "table"
            or #slot.root_ids < 1
            or not exact_fields(live, LIVE_FIELDS)
            or live.slot_id ~= slot.slot_id
            or live.method ~= slot.method
            or live.function_id ~= slot.function_id
            or live.key ~= slot.method
            or type(live.holder) ~= "table"
            or type(live.original) ~= "function"
            or live.holder[live.key] ~= live.original
            or not same_array(live.root_ids, slot.root_ids)
            or not exact_array(live.root_objects, #slot.root_ids) then
            return nil, "callback live binding mismatch"
        end
        for root_index, root_id in ipairs(slot.root_ids) do
            if type(root_id) ~= "string" or root_id == ""
                or type(live.root_objects[root_index]) ~= "table" then
                return nil, "invalid callback root binding"
            end
        end
        slots[slot.slot_id] = {
            document = slot,
            live = live,
        }
    end
    return slots
end

local Controller = {}
Controller.__index = Controller

function Controller:prepare(packet)
    if self.runtime ~= nil or self.consumed then
        return false, "controller already consumed"
    end
    self.consumed = true
    if not exact_fields(packet, PACKET_FIELDS)
        or packet.arm_packet_schema_version ~= 1
        or type(packet.build_identity) ~= "table"
        or type(packet.hook_plan) ~= "table" then
        return false, "invalid arm packet"
    end
    local installed_kind = nil
    local installed = {}
    local callback_coverage = {}
    for _, entry in ipairs(packet.hook_plan) do
        if type(entry) ~= "table" then return false, "invalid hook plan" end
        local slot_id = string.match(
            tostring(entry.hook_id or ""), "^callback%.(slot%-%d%d%d%d)$"
        )
        if slot_id ~= nil then
            local bound = self.slots[slot_id]
            if not bound
                or entry.hook_id ~= slot_hook_id(bound.document)
                or entry.event_kind ~= METHOD_TO_KIND[bound.document.method]
                or entry.target ~= slot_target(bound.document)
                or entry.target_kind ~= slot_target_kind(bound.document)
                or callback_coverage[slot_id] then
                return false, "callback hook plan does not match slot manifest"
            end
            callback_coverage[slot_id] = true
            if entry.status == "installed" then
                if installed_kind ~= nil
                    and installed_kind ~= entry.event_kind then
                    return false, "controller requires one callback family"
                end
                installed_kind = entry.event_kind
                installed[#installed + 1] = {
                    plan = entry,
                    binding = bound.live,
                }
            elseif entry.status ~= "disabled" then
                return false, "callback hook status is invalid"
            end
        elseif entry.status == "installed" then
            return false, "controller accepts only callback-slot hooks"
        end
    end
    if installed_kind == nil or #installed == 0 then
        return false, "controller requires one installed callback family"
    end
    local expected_method = KIND_TO_METHOD[installed_kind]
    local expected_count = 0
    for slot_id, bound in pairs(self.slots) do
        if not callback_coverage[slot_id] then
            return false, "callback hook plan omits a resolved slot"
        end
        if bound.document.method == expected_method then
            expected_count = expected_count + 1
        end
    end
    if #installed ~= expected_count then
        return false, "installed callback family coverage is incomplete"
    end
    local hook_bindings = {}
    for _, item in ipairs(installed) do
        hook_bindings[item.plan.hook_id] = {
            holder = item.binding.holder,
            key = item.binding.key,
        }
    end
    local ok, runtime_or_error = pcall(function()
        return self.runtime_module.new({
            trusted = packet.trusted,
            policy = packet.policy,
            hook_plan = packet.hook_plan,
            hook_bindings = hook_bindings,
            runtime_provider = self.runtime_provider,
        })
    end)
    if not ok then return false, tostring(runtime_or_error) end
    local prepared, prepare_error = runtime_or_error:prepare(packet.manifest)
    if not prepared then
        safe_disarm(runtime_or_error)
        return false, prepare_error
    end
    self.runtime = runtime_or_error
    self.installed = installed
    return true
end

function Controller:activate(nonce)
    if self.activated then return false, "controller already activated" end
    if not self.runtime then return false, "controller is not prepared" end
    local call_ok, activated, activate_error = pcall(
        self.runtime.activate, self.runtime, nonce
    )
    if not call_ok then
        safe_disarm(self.runtime)
        return false, "runtime activation failed"
    end
    if not activated then
        safe_disarm(self.runtime)
        return false, activate_error
    end
    for _, item in ipairs(self.installed) do
        local adapter = callback_adapter(
            item.plan, item.binding, self.globals
        )
        local install_ok, installed, install_error = pcall(
            self.runtime.install_proven_non_yielding_adapter_hook,
            self.runtime,
            item.plan.hook_id,
            adapter
        )
        if not install_ok or not installed then
            safe_disarm(self.runtime)
            return false, install_error or "runtime hook installation failed"
        end
    end
    self.activated = true
    return true
end

function Controller:checkpoint(reason)
    if not self.activated or not self.runtime then
        return false, "controller is not active"
    end
    local call_ok, snapshot, checkpoint_error = pcall(
        self.runtime.checkpoint, self.runtime, reason
    )
    self.activated = false
    if not call_ok then
        safe_disarm(self.runtime)
        return false, "runtime checkpoint failed"
    end
    if not snapshot then
        safe_disarm(self.runtime)
        return false, checkpoint_error
    end
    local ok, write_result, write_error = pcall(self.raw_writer, snapshot)
    if not ok then return false, "raw writer failed" end
    if write_result ~= true then
        return false, write_error or "raw writer rejected checkpoint"
    end
    self.written = true
    return true
end

function Controller:disarm()
    if self.runtime then safe_disarm(self.runtime) end
    self.activated = false
end

function Controller:status()
    return {
        consumed = self.consumed == true,
        prepared = self.runtime ~= nil,
        activated = self.activated == true,
        written = self.written == true,
    }
end

function M.bind_runtime(runtime_module)
    if type(runtime_module) ~= "table"
        or type(runtime_module.new) ~= "function" then
        error("invalid Observatory runtime module", 2)
    end
    local Bound = {VERSION = M.VERSION}
    function Bound.new(options)
        if not exact_fields(options, OPTION_FIELDS)
            or type(options.runtime_provider) ~= "function"
            or type(options.binding_document) ~= "table"
            or type(options.live_bindings) ~= "table"
            or type(options.raw_writer) ~= "function"
            or type(options.globals) ~= "table" then
            error("invalid Observatory callback controller options", 2)
        end
        local slots, binding_error = validate_bindings(
            options.binding_document, options.live_bindings
        )
        if not slots then error(binding_error, 2) end
        local self = setmetatable({}, Controller)
        self.runtime_module = runtime_module
        self.runtime_provider = options.runtime_provider
        self.binding_document = options.binding_document
        self.live_bindings = options.live_bindings
        self.raw_writer = options.raw_writer
        self.globals = options.globals
        self.slots = slots
        self.runtime = nil
        self.installed = nil
        self.consumed = false
        self.activated = false
        self.written = false
        return self
    end
    return Bound
end

return M
