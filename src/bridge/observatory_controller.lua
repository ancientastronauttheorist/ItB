-- Explicit, source-only controller for disposable Observatory experiments.
--
-- Loading this module performs no I/O, environment lookup, polling, global
-- mutation, hook installation, or runtime construction.  A host must supply
-- the exact arm packet and separately invoke prepare(), activate(nonce), and
-- checkpoint().  The first implementation intentionally supports only the
-- independently tested Lua-visible RNG globals.

local M = {}

M.VERSION = "observatory-controller/1"

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
    hook_bindings = true,
    raw_writer = true,
}

local SUPPORTED_KINDS = {
    random_int = true,
    random_bool = true,
}

local function safe_disarm(runtime)
    pcall(runtime.disarm, runtime)
end

local function exact_fields(value, expected)
    if type(value) ~= "table" then return false end
    for key, _ in pairs(expected) do
        if value[key] == nil then return false end
    end
    for key, _ in pairs(value) do
        if not expected[key] then return false end
    end
    return true
end

local function integer(value)
    return type(value) == "number" and value == math.floor(value)
end

local function rng_observer(plan)
    if plan.event_kind == "random_int" then
        return function(results, arguments, call_order)
            local upper_bound = arguments[1]
            local result = results[1]
            if not integer(upper_bound)
                or upper_bound < 1
                or not integer(result)
                or result < 0
                or result >= upper_bound then
                error("invalid random_int boundary")
            end
            return {
                context = {call_site = plan.target},
                payload = {
                    call_order = call_order,
                    upper_bound = upper_bound,
                    result = result,
                },
            }
        end
    end
    if plan.event_kind == "random_bool" then
        return function(results, arguments, call_order)
            local argument = arguments[1]
            local result = results[1]
            if not integer(argument)
                or argument < 1
                or type(result) ~= "boolean" then
                error("invalid random_bool boundary")
            end
            return {
                context = {call_site = plan.target},
                payload = {
                    call_order = call_order,
                    argument = argument,
                    result = result,
                },
            }
        end
    end
    return nil
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
    local installed_count = 0
    local installed_entry = nil
    for _, entry in ipairs(packet.hook_plan) do
        if type(entry) ~= "table" then
            return false, "invalid hook plan"
        elseif entry.status == "installed" then
            installed_count = installed_count + 1
            installed_entry = entry
            if not SUPPORTED_KINDS[entry.event_kind] then
                return false, "unsupported installed hook"
            end
        end
    end
    if installed_count ~= 1 then
        return false, "controller requires exactly one installed hook"
    end
    local expected_target = "_G." .. installed_entry.event_kind
    local binding = self.hook_bindings[installed_entry.hook_id]
    if installed_entry.target ~= expected_target
        or installed_entry.target_kind ~= "lua_global"
        or type(binding) ~= "table"
        or binding.holder ~= _G
        or binding.key ~= installed_entry.event_kind then
        return false, "installed RNG binding is not exact"
    end
    local ok, runtime_or_error = pcall(function()
        return self.runtime_module.new({
            trusted = packet.trusted,
            policy = packet.policy,
            hook_plan = packet.hook_plan,
            hook_bindings = self.hook_bindings,
            runtime_provider = self.runtime_provider,
        })
    end)
    if not ok then return false, tostring(runtime_or_error) end
    local prepared, prepare_error = runtime_or_error:prepare(
        packet.manifest
    )
    if not prepared then
        safe_disarm(runtime_or_error)
        return false, prepare_error
    end
    self.runtime = runtime_or_error
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
    for _, plan in ipairs(self.runtime.hook_plan) do
        if plan.status == "installed" then
            local observer = rng_observer(plan)
            if not observer then
                safe_disarm(self.runtime)
                return false, "unsupported installed hook"
            end
            local install_ok, installed, install_error = pcall(
                self.runtime.install_proven_non_yielding_hook,
                self.runtime,
                plan.hook_id,
                observer
            )
            if not install_ok then
                safe_disarm(self.runtime)
                return false, "runtime hook installation failed"
            end
            if not installed then
                safe_disarm(self.runtime)
                return false, install_error
            end
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
    local ok, write_result, write_error = pcall(
        self.raw_writer, snapshot
    )
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
            or type(options.hook_bindings) ~= "table"
            or type(options.raw_writer) ~= "function" then
            error("invalid Observatory controller options", 2)
        end
        local self = setmetatable({}, Controller)
        self.runtime_module = runtime_module
        self.runtime_provider = options.runtime_provider
        self.hook_bindings = options.hook_bindings
        self.raw_writer = options.raw_writer
        self.runtime = nil
        self.consumed = false
        self.activated = false
        self.written = false
        return self
    end
    return Bound
end

return M
