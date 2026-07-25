-- ITB Engine Observatory dormant trace runtime.
--
-- This module does not read files, poll bridge commands, or install hooks at
-- load time. A controller must first prepare an exact, short-lived manifest
-- and then activate it with the one-shot nonce as a separate second step.
-- Hook installation is explicit and limited to boundaries independently
-- proven non-yielding under Lua 5.1.

local M = {}

M.VERSION = "observatory-lua/1"
M.MAX_ARM_WINDOW_SECONDS = 15 * 60
M.HARD_MAX_EVENTS = 4096
M.HARD_MAX_EVENTS_PER_TURN = 1024
M.HARD_MAX_EVENT_UNITS = 64 * 1024
M.HARD_MAX_TOTAL_UNITS = 4 * 1024 * 1024
M.HARD_MAX_ATTEMPTS = 16 * 1024
M.HARD_MAX_HOOKS = 256
M.HARD_BUNDLE_RESERVE_BYTES = 2 * 1024 * 1024
M.HARD_MAX_SNAPSHOT_UNITS =
    M.HARD_MAX_TOTAL_UNITS + M.HARD_BUNDLE_RESERVE_BYTES
M.HARD_MAX_BUNDLE_BYTES = 64 * 1024 * 1024

local KNOWN_PHASES = {
    combat_enemy = true,
    combat_player = true,
}

local KNOWN_KINDS = {
    random_int = true,
    random_bool = true,
    enemy_candidate = true,
    enemy_target_score = true,
    score_positioning = true,
    get_target_area = true,
    get_skill_effect = true,
    enemy_action_selected = true,
}

local KNOWN_KIND_ORDER = {
    "enemy_action_selected",
    "enemy_candidate",
    "enemy_target_score",
    "get_skill_effect",
    "get_target_area",
    "random_bool",
    "random_int",
    "score_positioning",
}

local MANIFEST_FIELDS = {
    schema_version = true,
    capture_id = true,
    checkpoint_seq = true,
    arm_nonce = true,
    controller_version = true,
    controller_sha256 = true,
    installed_modloader_sha256 = true,
    build_identity_sha256 = true,
    expected_mission_id = true,
    expected_turn = true,
    expected_phase = true,
    timeline_fingerprint = true,
    master_seed = true,
    region_id = true,
    ai_seed_fingerprint = true,
    config_sha256 = true,
    hook_coverage_sha256 = true,
    activated_epoch = true,
    expires_epoch = true,
    max_events = true,
    max_events_per_turn = true,
    max_event_bytes = true,
    max_total_event_bytes = true,
    max_attempts = true,
    max_bundle_bytes = true,
    allowed_kinds = true,
}

local RUNTIME_FIELDS = {
    now_epoch = true,
    mission_id = true,
    turn = true,
    phase = true,
    timeline_fingerprint = true,
    master_seed = true,
    region_id = true,
    ai_seed_fingerprint = true,
}

local POLICY_FIELDS = {
    expected_phase = true,
    max_events = true,
    max_events_per_turn = true,
    max_event_bytes = true,
    max_total_event_bytes = true,
    max_attempts = true,
    max_bundle_bytes = true,
    allowed_kinds = true,
}

local HOOK_PLAN_FIELDS = {
    hook_id = true,
    event_kind = true,
    target = true,
    target_kind = true,
    status = true,
    source_sha256 = true,
}

local BINDING_FIELDS = {
    holder = true,
    key = true,
}

local EXTRACTION_FIELDS = {
    context = true,
    payload = true,
}

local HOOK_TARGET_KINDS = {
    lua_global = true,
    lua_method = true,
    native_boundary = true,
}

local HOOK_STATUSES = {
    installed = true,
    disabled = true,
}

local TRUSTED_FIELDS = {
    controller_sha256 = true,
    installed_modloader_sha256 = true,
    build_identity_sha256 = true,
    config_sha256 = true,
    hook_coverage_sha256 = true,
}

local CHECKPOINT_REASONS = {
    turn_boundary = true,
    mission_end = true,
    explicit = true,
}

local function pack(...)
    return { n = select("#", ...), ... }
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

local function nonempty_text(value)
    return type(value) == "string" and value ~= ""
end

local function bounded_text(value, limit)
    return nonempty_text(value) and string.len(value) <= limit
end

local function lower_sha256(value)
    return type(value) == "string"
        and string.len(value) == 64
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function arm_nonce(value)
    return type(value) == "string"
        and string.len(value) >= 32
        and string.len(value) <= 64
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function capture_id(value)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= 128
        and string.match(value, "^[a-z0-9][a-z0-9._-]*$") ~= nil
end

local function nonnegative_integer(value)
    return type(value) == "number"
        and value >= 0
        and value == math.floor(value)
end

local function signed_integer(value)
    return type(value) == "number" and value == math.floor(value)
end

local function valid_utf8(value)
    local index = 1
    local length = string.len(value)
    while index <= length do
        local first = string.byte(value, index)
        if first <= 0x7f then
            index = index + 1
        else
            local second = string.byte(value, index + 1)
            if first >= 0xc2 and first <= 0xdf
                and second and second >= 0x80 and second <= 0xbf then
                index = index + 2
            else
                local third = string.byte(value, index + 2)
                if first >= 0xe0 and first <= 0xef
                    and second and third
                    and second >= 0x80 and second <= 0xbf
                    and third >= 0x80 and third <= 0xbf
                    and not (first == 0xe0 and second < 0xa0)
                    and not (first == 0xed and second >= 0xa0) then
                    index = index + 3
                else
                    local fourth = string.byte(value, index + 3)
                    if first >= 0xf0 and first <= 0xf4
                        and second and third and fourth
                        and second >= 0x80 and second <= 0xbf
                        and third >= 0x80 and third <= 0xbf
                        and fourth >= 0x80 and fourth <= 0xbf
                        and not (first == 0xf0 and second < 0x90)
                        and not (first == 0xf4 and second >= 0x90) then
                        index = index + 4
                    else
                        return false
                    end
                end
            end
        end
    end
    return true
end

local function copy_primitive(value, depth, seen, budget)
    local value_type = type(value)
    if value == nil or value_type == "boolean" or value_type == "string" then
        if value_type == "string" then
            if not valid_utf8(value) then
                return nil, "invalid UTF-8 string"
            end
            -- Six bytes per input byte safely bounds JSON escaping, including
            -- control characters rendered as \u00XX. Quotes add two more.
            budget.units = budget.units + string.len(value) * 6 + 2
        elseif value_type == "boolean" then
            budget.units = budget.units + 5
        else
            budget.units = budget.units + 4
        end
        if budget.units > budget.limit then
            return nil, "primitive budget exceeded"
        end
        return value
    end
    if value_type == "number" then
        if value ~= value or value == math.huge or value == -math.huge then
            return nil, "non-finite number"
        end
        -- A finite IEEE-754 value has a much shorter canonical JSON spelling.
        budget.units = budget.units + 32
        if budget.units > budget.limit then
            return nil, "primitive budget exceeded"
        end
        return value
    end
    if value_type ~= "table" then
        return nil, "non-primitive value"
    end
    if depth >= budget.max_depth then
        return nil, "primitive depth exceeded"
    end
    if seen[value] then return nil, "primitive cycle" end
    seen[value] = true
    budget.units = budget.units + 2
    if budget.units > budget.limit then
        seen[value] = nil
        return nil, "primitive budget exceeded"
    end
    local result = {}
    local count = 0
    for key, child in pairs(value) do
        count = count + 1
        if count > 4096 then
            seen[value] = nil
            return nil, "table entry limit exceeded"
        end
        if type(key) ~= "string"
            and not nonnegative_integer(key) then
            seen[value] = nil
            return nil, "non-primitive table key"
        end
        -- Conservatively covers a comma, colon, newline, and indentation at
        -- the maximum supported nesting depth in pretty JSON.
        budget.units = budget.units + 64
        if budget.units > budget.limit then
            seen[value] = nil
            return nil, "primitive budget exceeded"
        end
        local copied_key, key_error = copy_primitive(
            key, depth + 1, seen, budget
        )
        if key_error then
            seen[value] = nil
            return nil, key_error
        end
        local copied_child, child_error = copy_primitive(
            child, depth + 1, seen, budget
        )
        if child_error then
            seen[value] = nil
            return nil, child_error
        end
        result[copied_key] = copied_child
    end
    seen[value] = nil
    return result
end

local function bounded_copy(value, limit, max_depth)
    local budget = {
        units = 0,
        limit = limit,
        max_depth = max_depth or 8,
    }
    local copied, err = copy_primitive(value, 0, {}, budget)
    return copied, err, budget.units
end

local function sorted_allowed_kinds(value)
    if type(value) ~= "table" or #value == 0 then return nil end
    local seen = {}
    local previous = nil
    local result = {}
    for index, kind in ipairs(value) do
        if not nonempty_text(kind)
            or not KNOWN_KINDS[kind]
            or seen[kind]
            or (previous ~= nil and previous >= kind) then
            return nil
        end
        seen[kind] = true
        previous = kind
        result[index] = kind
    end
    for key, _ in pairs(value) do
        if not nonnegative_integer(key)
            or key < 1
            or key > #value then
            return nil
        end
    end
    return result, seen
end

local function same_array(left, right)
    if #left ~= #right then return false end
    for index = 1, #left do
        if left[index] ~= right[index] then return false end
    end
    return true
end

local function validate_policy(policy)
    if not exact_fields(policy, POLICY_FIELDS) then
        return nil, "policy fields"
    end
    local allowed, allowed_set = sorted_allowed_kinds(
        policy.allowed_kinds
    )
    if not allowed then return nil, "policy allowed kinds" end
    if policy.expected_phase ~= "combat_enemy"
        or not nonnegative_integer(policy.max_events)
        or policy.max_events < 1
        or policy.max_events > M.HARD_MAX_EVENTS
        or not nonnegative_integer(policy.max_events_per_turn)
        or policy.max_events_per_turn < 1
        or policy.max_events_per_turn > M.HARD_MAX_EVENTS_PER_TURN
        or not nonnegative_integer(policy.max_event_bytes)
        or policy.max_event_bytes < 1
        or policy.max_event_bytes > M.HARD_MAX_EVENT_UNITS
        or not nonnegative_integer(policy.max_total_event_bytes)
        or policy.max_total_event_bytes < 1
        or policy.max_total_event_bytes > M.HARD_MAX_TOTAL_UNITS
        or not nonnegative_integer(policy.max_attempts)
        or policy.max_attempts < 1
        or policy.max_attempts > M.HARD_MAX_ATTEMPTS
        or not nonnegative_integer(policy.max_bundle_bytes)
        or policy.max_bundle_bytes < 1
        or policy.max_bundle_bytes > M.HARD_MAX_BUNDLE_BYTES
        or policy.max_events_per_turn > policy.max_events
        or policy.max_event_bytes > policy.max_total_event_bytes
        or policy.max_bundle_bytes
            < policy.max_total_event_bytes
                + M.HARD_BUNDLE_RESERVE_BYTES then
        return nil, "policy values"
    end
    local copied, copy_error = bounded_copy(policy, 64 * 1024)
    if copy_error then return nil, copy_error end
    return copied, allowed_set
end

local function validate_hook_plan(plan, allowed_set, bindings)
    if type(plan) ~= "table"
        or type(bindings) ~= "table"
        or #plan == 0
        or #plan > M.HARD_MAX_HOOKS then
        return nil, "hook plan"
    end
    local copied = {}
    local by_id = {}
    local seen_kinds = {}
    local seen_ids = {}
    local seen_targets = {}
    local installed_kinds = {}
    local previous_kind = nil
    local previous_target = nil
    local coverage = {}
    for index, entry in ipairs(plan) do
        if not exact_fields(entry, HOOK_PLAN_FIELDS)
            or not bounded_text(entry.hook_id, 128)
            or string.match(
                entry.hook_id, "^[a-z0-9][a-z0-9._:-]*$"
            ) == nil
            or seen_ids[entry.hook_id]
            or not KNOWN_KINDS[entry.event_kind]
            or not bounded_text(entry.target, 256)
            or not HOOK_TARGET_KINDS[entry.target_kind]
            or not HOOK_STATUSES[entry.status]
            or not lower_sha256(entry.source_sha256) then
            return nil, "hook plan entry"
        end
        if previous_kind ~= nil
            and (
                previous_kind > entry.event_kind
                or (
                    previous_kind == entry.event_kind
                    and previous_target >= entry.target
                )
            ) then
            return nil, "hook plan order"
        end
        local target_key = entry.event_kind .. "\0" .. entry.target
        if seen_targets[target_key] then
            return nil, "duplicate hook target"
        end
        previous_kind = entry.event_kind
        previous_target = entry.target
        seen_ids[entry.hook_id] = true
        seen_targets[target_key] = true
        seen_kinds[entry.event_kind] = true
        if entry.status == "installed" then
            installed_kinds[entry.event_kind] = true
            local binding = bindings[entry.hook_id]
            if not exact_fields(binding, BINDING_FIELDS)
                or type(binding.holder) ~= "table"
                or (type(binding.key) ~= "string"
                    and type(binding.key) ~= "number")
                or type(binding.holder[binding.key]) ~= "function" then
                return nil, "hook binding"
            end
        elseif bindings[entry.hook_id] ~= nil then
            return nil, "unexpected hook binding"
        end
        local entry_copy, copy_error = bounded_copy(entry, 8192)
        if copy_error then return nil, copy_error end
        copied[index] = entry_copy
        by_id[entry.hook_id] = entry_copy
        coverage[index] = {
            event_kind = entry.event_kind,
            target = entry.target,
            target_kind = entry.target_kind,
            status = entry.status,
            source_sha256 = entry.source_sha256,
        }
    end
    for key, _ in pairs(plan) do
        if not nonnegative_integer(key)
            or key < 1
            or key > #plan then
            return nil, "hook plan shape"
        end
    end
    for key, _ in pairs(bindings) do
        local entry = by_id[key]
        if not entry or entry.status ~= "installed" then
            return nil, "unknown hook binding"
        end
    end
    for _, kind in ipairs(KNOWN_KIND_ORDER) do
        if not seen_kinds[kind]
            or (installed_kinds[kind] == true)
                ~= (allowed_set[kind] == true) then
            return nil, "hook plan coverage"
        end
    end
    return copied, by_id, coverage
end

local function same_runtime(manifest, runtime)
    return runtime.mission_id == manifest.expected_mission_id
        and runtime.turn == manifest.expected_turn
        and runtime.phase == manifest.expected_phase
        and runtime.timeline_fingerprint == manifest.timeline_fingerprint
        and runtime.master_seed == manifest.master_seed
        and runtime.region_id == manifest.region_id
        and runtime.ai_seed_fingerprint == manifest.ai_seed_fingerprint
end

local function validate_runtime(runtime)
    if not exact_fields(runtime, RUNTIME_FIELDS) then
        return false, "runtime fields"
    end
    if not nonnegative_integer(runtime.now_epoch)
        or not bounded_text(runtime.mission_id, 256)
        or not nonnegative_integer(runtime.turn)
        or not KNOWN_PHASES[runtime.phase]
        or not lower_sha256(runtime.timeline_fingerprint)
        or not signed_integer(runtime.master_seed)
        or not bounded_text(runtime.region_id, 128)
        or not lower_sha256(runtime.ai_seed_fingerprint) then
        return false, "runtime values"
    end
    return true
end

local function validate_manifest(manifest, trusted, policy, runtime)
    if not exact_fields(manifest, MANIFEST_FIELDS) then
        return false, "manifest fields"
    end
    if not exact_fields(trusted, TRUSTED_FIELDS) then
        return false, "trusted fields"
    end
    local runtime_ok, runtime_error = validate_runtime(runtime)
    if not runtime_ok then return false, runtime_error end
    if manifest.schema_version ~= 1
        or not capture_id(manifest.capture_id)
        or not nonnegative_integer(manifest.checkpoint_seq)
        or not arm_nonce(manifest.arm_nonce)
        or not bounded_text(manifest.controller_version, 128)
        or not lower_sha256(manifest.controller_sha256)
        or not lower_sha256(manifest.installed_modloader_sha256)
        or not lower_sha256(manifest.build_identity_sha256)
        or not bounded_text(manifest.expected_mission_id, 256)
        or not nonnegative_integer(manifest.expected_turn)
        or manifest.expected_phase ~= "combat_enemy"
        or not lower_sha256(manifest.timeline_fingerprint)
        or not signed_integer(manifest.master_seed)
        or not bounded_text(manifest.region_id, 128)
        or not lower_sha256(manifest.ai_seed_fingerprint)
        or not lower_sha256(manifest.config_sha256)
        or not lower_sha256(manifest.hook_coverage_sha256)
        or not nonnegative_integer(manifest.activated_epoch)
        or not nonnegative_integer(manifest.expires_epoch)
        or not nonnegative_integer(manifest.max_events)
        or manifest.max_events < 1
        or manifest.max_events > M.HARD_MAX_EVENTS
        or not nonnegative_integer(manifest.max_events_per_turn)
        or manifest.max_events_per_turn < 1
        or manifest.max_events_per_turn > M.HARD_MAX_EVENTS_PER_TURN
        or not nonnegative_integer(manifest.max_event_bytes)
        or manifest.max_event_bytes < 1
        or manifest.max_event_bytes > M.HARD_MAX_EVENT_UNITS
        or not nonnegative_integer(manifest.max_total_event_bytes)
        or manifest.max_total_event_bytes < 1
        or manifest.max_total_event_bytes > M.HARD_MAX_TOTAL_UNITS
        or not nonnegative_integer(manifest.max_attempts)
        or manifest.max_attempts < 1
        or manifest.max_attempts > M.HARD_MAX_ATTEMPTS
        or not nonnegative_integer(manifest.max_bundle_bytes)
        or manifest.max_bundle_bytes < 1
        or manifest.max_bundle_bytes > M.HARD_MAX_BUNDLE_BYTES then
        return false, "manifest values"
    end
    if manifest.max_events_per_turn > manifest.max_events
        or manifest.max_event_bytes > manifest.max_total_event_bytes then
        return false, "manifest cap relationship"
    end
    if manifest.expected_phase ~= policy.expected_phase
        or manifest.max_events ~= policy.max_events
        or manifest.max_events_per_turn ~= policy.max_events_per_turn
        or manifest.max_event_bytes ~= policy.max_event_bytes
        or manifest.max_total_event_bytes
            ~= policy.max_total_event_bytes
        or manifest.max_attempts ~= policy.max_attempts
        or manifest.max_bundle_bytes ~= policy.max_bundle_bytes
        or not same_array(
            manifest.allowed_kinds, policy.allowed_kinds
        ) then
        return false, "trusted policy mismatch"
    end
    if manifest.expires_epoch <= manifest.activated_epoch
        or manifest.expires_epoch - manifest.activated_epoch
            > M.MAX_ARM_WINDOW_SECONDS
        or runtime.now_epoch < manifest.activated_epoch
        or runtime.now_epoch > manifest.expires_epoch then
        return false, "manifest freshness"
    end
    local allowed, allowed_set = sorted_allowed_kinds(
        manifest.allowed_kinds
    )
    if not allowed then return false, "allowed kinds" end
    if manifest.controller_sha256 ~= trusted.controller_sha256
        or manifest.installed_modloader_sha256
            ~= trusted.installed_modloader_sha256
        or manifest.build_identity_sha256
            ~= trusted.build_identity_sha256
        or manifest.config_sha256 ~= trusted.config_sha256
        or manifest.hook_coverage_sha256
            ~= trusted.hook_coverage_sha256 then
        return false, "trusted identity mismatch"
    end
    if not same_runtime(manifest, runtime) then
        return false, "runtime identity mismatch"
    end
    local copied, copy_error = bounded_copy(manifest, 64 * 1024)
    if copy_error then return false, copy_error end
    return true, copied, allowed_set
end

local PROCESS_STATE_KEY = "__ITB_OBSERVATORY_TRACE_PROCESS_V1"

local function process_state()
    local state = rawget(_G, PROCESS_STATE_KEY)
    if state == nil then
        state = {used_nonces = {}, hook_registry = {}}
        rawset(_G, PROCESS_STATE_KEY, state)
    end
    if type(state) ~= "table"
        or type(state.used_nonces) ~= "table"
        or type(state.hook_registry) ~= "table" then
        return nil
    end
    return state
end

local Runtime = {}
Runtime.__index = Runtime

function M.new(options)
    if type(options) ~= "table"
        or not exact_fields(options, {
            trusted = true,
            policy = true,
            hook_plan = true,
            hook_bindings = true,
            runtime_provider = true,
        })
        or type(options.runtime_provider) ~= "function" then
        error("invalid Observatory runtime options", 2)
    end
    if not exact_fields(options.trusted, TRUSTED_FIELDS) then
        error("invalid Observatory trusted identity", 2)
    end
    for key, value in pairs(options.trusted) do
        if not lower_sha256(value) then
            error("invalid Observatory trusted hash: " .. tostring(key), 2)
        end
    end
    local trusted_copy, trusted_error = bounded_copy(
        options.trusted, 16 * 1024
    )
    if trusted_error then
        error("invalid Observatory trusted identity", 2)
    end
    local policy, allowed_or_error = validate_policy(options.policy)
    if not policy then
        error("invalid Observatory " .. tostring(allowed_or_error), 2)
    end
    local allowed = allowed_or_error
    local hook_plan, hooks_or_error, hook_coverage = validate_hook_plan(
        options.hook_plan, allowed, options.hook_bindings
    )
    if not hook_plan then
        error("invalid Observatory " .. tostring(hooks_or_error), 2)
    end
    local shared = process_state()
    if not shared then
        error("invalid Observatory process state", 2)
    end
    local self = setmetatable({}, Runtime)
    self.trusted = trusted_copy
    self.policy = policy
    self.allowed = allowed
    self.hook_plan = hook_plan
    self.hook_plan_by_id = hooks_or_error
    self.hook_coverage = hook_coverage
    self.hook_bindings = {}
    for _, entry in ipairs(hook_plan) do
        if entry.status == "installed" then
            local binding = options.hook_bindings[entry.hook_id]
            local occupied = shared.hook_registry[binding.holder]
            if type(occupied) == "table"
                and occupied[binding.key] ~= nil then
                error("Observatory hook target already registered", 2)
            end
            self.hook_bindings[entry.hook_id] = {
                holder = binding.holder,
                key = binding.key,
                original = binding.holder[binding.key],
            }
        end
    end
    self.runtime_provider = options.runtime_provider
    self.used_nonces = shared.used_nonces
    self.hook_registry = shared.hook_registry
    self.pending = nil
    self.prepare_consumed = false
    self.checkpointed = false
    self.manifest = nil
    self.started_epoch = nil
    self.enabled = false
    self.in_trace = false
    self.events = {}
    self.hooks = {}
    self.installed_hook_ids = {}
    self.event_byte_upper_bound = 0
    self.attempted_calls = {}
    for _, kind in ipairs(KNOWN_KIND_ORDER) do
        self.attempted_calls[kind] = 0
    end
    self.accepted_by_turn = {}
    self.dropped_events = 0
    self.filtered_events = 0
    self.serialization_errors = 0
    self.truncation_reasons = {}
    self.stop_reasons = {}
    self.restore_conflicts = 0
    self.total_attempts = 0
    return self
end

function Runtime:is_enabled()
    return self.enabled == true
end

function Runtime:_runtime_state()
    local ok, runtime, runtime_error = pcall(function()
        local provided = self.runtime_provider()
        local valid, validation_error = validate_runtime(provided)
        if not valid then return nil, validation_error end
        local copied, copy_error = bounded_copy(provided, 8192)
        if copy_error then return nil, copy_error end
        return copied
    end)
    if not ok then return nil, "runtime provider failed" end
    return runtime, runtime_error
end

function Runtime:prepare(manifest)
    if self.enabled then return false, "already active" end
    if self.prepare_consumed or self.manifest then
        return false, "runtime already consumed"
    end
    local runtime, runtime_error = self:_runtime_state()
    if not runtime then return false, runtime_error end
    local valid, copied_or_error = validate_manifest(
        manifest, self.trusted, self.policy, runtime
    )
    if not valid then
        self.pending = nil
        return false, copied_or_error
    end
    if self.used_nonces[copied_or_error.arm_nonce] then
        self.pending = nil
        return false, "nonce already used"
    end
    self.prepare_consumed = true
    self.pending = copied_or_error
    return true
end

function Runtime:activate(nonce)
    if self.enabled then return false, "already active" end
    if not self.pending then return false, "no prepared manifest" end
    local pending = self.pending
    self.pending = nil
    if nonce ~= pending.arm_nonce then
        return false, "activation nonce mismatch"
    end
    local runtime, runtime_error = self:_runtime_state()
    if not runtime then return false, runtime_error end
    local valid, copied_or_error = validate_manifest(
        pending, self.trusted, self.policy, runtime
    )
    if not valid then return false, copied_or_error end
    if self.used_nonces[nonce] then
        return false, "nonce already used"
    end
    self.used_nonces[nonce] = true
    self.manifest = copied_or_error
    self.started_epoch = runtime.now_epoch
    self.enabled = true
    return true
end

function Runtime:_count_attempt(kind)
    self.total_attempts = self.total_attempts + 1
    self.attempted_calls[kind] = self.attempted_calls[kind] + 1
    if kind == "random_int" or kind == "random_bool" then
        return self.attempted_calls.random_int
            + self.attempted_calls.random_bool - 1
    end
    return self.attempted_calls[kind] - 1
end

function Runtime:_stop(reason)
    self.stop_reasons[reason] = (self.stop_reasons[reason] or 0) + 1
    self:restore_hooks()
    self.enabled = false
end

function Runtime:_drop(reason)
    self.dropped_events = self.dropped_events + 1
    self.truncation_reasons[reason] =
        (self.truncation_reasons[reason] or 0) + 1
end

function Runtime:_outcome_count()
    return #self.events
        + self.dropped_events
        + self.filtered_events
        + self.serialization_errors
end

function Runtime:_finish_outcome()
    if self.total_attempts >= self.policy.max_attempts then
        self:_stop("max_attempts")
    elseif #self.events >= self.policy.max_events then
        self:_stop("max_events")
    elseif self.event_byte_upper_bound
        >= self.policy.max_total_event_bytes then
        self:_stop("max_total_event_bytes")
    end
end

function Runtime:_observe(event_kind, observer, results, arguments)
    if not self.enabled then return end
    local runtime, runtime_error = self:_runtime_state()
    if not runtime then
        self:_count_attempt(event_kind)
        self.serialization_errors = self.serialization_errors + 1
        self:_stop(runtime_error)
        return
    end
    if runtime.now_epoch < self.manifest.activated_epoch
        or runtime.now_epoch > self.manifest.expires_epoch then
        self:_stop("capture_expired")
        return
    end
    local call_order = self:_count_attempt(event_kind)
    if not same_runtime(self.manifest, runtime) then
        self.filtered_events = self.filtered_events + 1
        self:_stop("runtime_identity_changed")
        return
    end
    local turn_key = runtime.mission_id .. ":" .. tostring(runtime.turn)
    local turn_count = self.accepted_by_turn[turn_key] or 0
    if turn_count >= self.policy.max_events_per_turn then
        self:_drop("max_events_per_turn")
        self:_stop("max_events_per_turn")
        return
    end
    local copied_results, results_error = bounded_copy(
        results, self.policy.max_event_bytes
    )
    local copied_arguments, arguments_error = bounded_copy(
        arguments, self.policy.max_event_bytes
    )
    if results_error or arguments_error then
        self.serialization_errors = self.serialization_errors + 1
        self:_finish_outcome()
        return
    end
    local ok, extraction = pcall(
        observer,
        copied_results,
        copied_arguments,
        call_order,
        runtime
    )
    if not ok
        or not exact_fields(extraction, EXTRACTION_FIELDS)
        or type(extraction.context) ~= "table"
        or type(extraction.payload) ~= "table" then
        self.serialization_errors = self.serialization_errors + 1
        self:_finish_outcome()
        return
    end
    local event = {
        seq = #self.events,
        kind = event_kind,
        phase = runtime.phase,
        mission_id = runtime.mission_id,
        turn = runtime.turn,
        context = extraction.context,
        payload = extraction.payload,
    }
    local copied_event, event_error, event_byte_upper_bound = bounded_copy(
        event, self.policy.max_event_bytes - 1
    )
    if event_error then
        if event_error == "primitive budget exceeded" then
            self:_drop("max_event_bytes")
        else
            self.serialization_errors = self.serialization_errors + 1
        end
        self:_finish_outcome()
        return
    end
    event_byte_upper_bound = event_byte_upper_bound + 1
    if self.event_byte_upper_bound + event_byte_upper_bound
        > self.policy.max_total_event_bytes then
        self:_drop("max_total_event_bytes")
        self:_stop("max_total_event_bytes")
        return
    end
    self.events[#self.events + 1] = copied_event
    self.event_byte_upper_bound =
        self.event_byte_upper_bound + event_byte_upper_bound
    self.accepted_by_turn[turn_key] = turn_count + 1
    self:_finish_outcome()
end

function Runtime:install_proven_non_yielding_hook(hook_id, observer)
    if not self.enabled then return false, "trace is disabled" end
    local plan = self.hook_plan_by_id[hook_id]
    local binding = self.hook_bindings[hook_id]
    if not plan
        or plan.status ~= "installed"
        or not binding
        or type(observer) ~= "function" then
        return false, "invalid hook"
    end
    if self.installed_hook_ids[hook_id] then
        return false, "hook already installed"
    end
    local holder = binding.holder
    local key = binding.key
    if holder[key] ~= binding.original then
        return false, "hook target changed"
    end
    local holder_registry = self.hook_registry[holder]
    if holder_registry == nil then
        holder_registry = {}
        self.hook_registry[holder] = holder_registry
    elseif type(holder_registry) ~= "table" then
        return false, "invalid global hook registry"
    end
    if holder_registry[key] ~= nil then
        return false, "hook already registered"
    end
    local original = holder[key]
    local runtime = self
    local wrapper
    wrapper = function(...)
        if not runtime.enabled or runtime.in_trace then
            return original(...)
        end
        -- Deliberately outside pcall: original errors propagate unchanged.
        local results = pack(original(...))
        local arguments = pack(...)
        runtime.in_trace = true
        local trace_ok = pcall(function()
            local attempts_before = runtime.total_attempts
            local outcomes_before = runtime:_outcome_count()
            local observe_ok = pcall(
                runtime._observe,
                runtime,
                plan.event_kind,
                observer,
                results,
                arguments
            )
            if not observe_ok then
                if runtime.total_attempts == attempts_before then
                    runtime:_count_attempt(plan.event_kind)
                end
                if runtime:_outcome_count() == outcomes_before then
                    runtime.serialization_errors =
                        runtime.serialization_errors + 1
                end
                pcall(
                    runtime._stop,
                    runtime,
                    "observation_runtime_failed"
                )
            end
        end)
        runtime.in_trace = false
        if not trace_ok then
            runtime.enabled = false
            pcall(runtime.restore_hooks, runtime)
        end
        return unpack(results, 1, results.n)
    end
    local hook = {
        hook_id = hook_id,
        holder = holder,
        key = key,
        original = original,
        wrapper = wrapper,
        registry = holder_registry,
    }
    self.hooks[#self.hooks + 1] = hook
    self.installed_hook_ids[hook_id] = true
    holder_registry[key] = hook
    holder[key] = wrapper
    return true
end

function Runtime:restore_hooks()
    for index = #self.hooks, 1, -1 do
        local hook = self.hooks[index]
        if hook.holder[hook.key] == hook.wrapper then
            hook.holder[hook.key] = hook.original
        else
            self.restore_conflicts = self.restore_conflicts + 1
        end
        if hook.registry[hook.key] == hook then
            hook.registry[hook.key] = nil
        end
        if next(hook.registry) == nil
            and self.hook_registry[hook.holder] == hook.registry then
            self.hook_registry[hook.holder] = nil
        end
    end
    self.hooks = {}
end

function Runtime:disarm()
    self:restore_hooks()
    self.enabled = false
    self.pending = nil
end

function Runtime:_coverage_complete()
    if self.restore_conflicts > 0 then return false end
    local active = {}
    for _, hook in ipairs(self.hooks) do
        if hook.holder[hook.key] == hook.wrapper
            and hook.registry[hook.key] == hook then
            active[hook.hook_id] = true
        elseif self.enabled then
            return false
        end
    end
    for _, entry in ipairs(self.hook_plan) do
        if entry.status == "installed"
            and (
                not self.installed_hook_ids[entry.hook_id]
                or (self.enabled and not active[entry.hook_id])
            ) then
            return false
        end
    end
    return true
end

function Runtime:checkpoint(reason)
    if not CHECKPOINT_REASONS[reason] then
        return nil, "invalid checkpoint"
    end
    local manifest = self.manifest
    if not manifest then return nil, "capture was never activated" end
    if self.checkpointed then return nil, "capture already checkpointed" end
    if not self:_coverage_complete() then
        self:disarm()
        return nil, "planned hook coverage was not installed"
    end
    self:disarm()
    local runtime, runtime_error = self:_runtime_state()
    if not runtime then
        return nil, runtime_error
    end
    if runtime.now_epoch < manifest.activated_epoch
        or runtime.now_epoch > manifest.expires_epoch then
        return nil, "checkpoint outside capture window"
    end
    if not same_runtime(manifest, runtime) then
        return nil, "checkpoint runtime identity mismatch"
    end
    local snapshot = {
        raw_schema_version = 1,
        runtime_version = M.VERSION,
        capture_id = manifest.capture_id,
        checkpoint_seq = manifest.checkpoint_seq,
        arm_nonce = manifest.arm_nonce,
        controller_version = manifest.controller_version,
        controller_sha256 = manifest.controller_sha256,
        installed_modloader_sha256 =
            manifest.installed_modloader_sha256,
        build_identity_sha256 = manifest.build_identity_sha256,
        expected_mission_id = manifest.expected_mission_id,
        expected_turn = manifest.expected_turn,
        expected_phase = manifest.expected_phase,
        timeline_fingerprint = manifest.timeline_fingerprint,
        master_seed = manifest.master_seed,
        region_id = manifest.region_id,
        ai_seed_fingerprint = manifest.ai_seed_fingerprint,
        config_sha256 = manifest.config_sha256,
        hook_coverage_sha256 = manifest.hook_coverage_sha256,
        config = {
            enabled = true,
            allowed_phases = {self.policy.expected_phase},
            max_events = self.policy.max_events,
            max_events_per_turn = self.policy.max_events_per_turn,
            max_event_bytes = self.policy.max_event_bytes,
            max_total_event_bytes = self.policy.max_total_event_bytes,
            max_bundle_bytes = self.policy.max_bundle_bytes,
        },
        hook_coverage = self.hook_coverage,
        activated_epoch = manifest.activated_epoch,
        expires_epoch = manifest.expires_epoch,
        started_epoch = self.started_epoch,
        completed_epoch = runtime.now_epoch,
        checkpoint_reason = reason,
        attempted_calls = self.attempted_calls,
        events = self.events,
        summary = {
            accepted_events = #self.events,
            event_byte_upper_bound = self.event_byte_upper_bound,
            dropped_events = self.dropped_events,
            filtered_events = self.filtered_events,
            serialization_errors = self.serialization_errors,
            truncation_reasons = self.truncation_reasons,
            stop_reasons = self.stop_reasons,
            restore_conflicts = self.restore_conflicts,
        },
    }
    local snapshot_limit = math.min(
        self.policy.max_bundle_bytes,
        M.HARD_MAX_SNAPSHOT_UNITS
    )
    local copied, copy_error = bounded_copy(snapshot, snapshot_limit, 12)
    if copy_error then return nil, copy_error end
    self.checkpointed = true
    return copied
end

return M
