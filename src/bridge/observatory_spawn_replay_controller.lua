-- Exact, one-family replay-input controller for Spawner:NextPawn.
--
-- Loading and constructing this module are inert. activate() replaces only
-- the build-pinned NextPawn slot. During an active NextPawn call, and only for
-- that synchronous call, it temporarily replaces the build-pinned
-- random_element slot so it can copy the exact candidate array passed by
-- SelectPawn. Both slots are restored before checkpoint() returns.

local M = {}

M.VERSION = "observatory-spawn-replay-controller/1"
M.SPAWNER_SOURCE_SUFFIX = "scripts/spawner_backend.lua"
M.SPAWNER_SOURCE_LINE = 174
M.SPAWNER_SOURCE_SHA256 =
    "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
M.RANDOM_ELEMENT_SOURCE_SUFFIX = "scripts/global.lua"
M.RANDOM_ELEMENT_SOURCE_LINE = 560
M.RANDOM_ELEMENT_SOURCE_SHA256 =
    "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
M.MAX_SPANS = 8
M.MAX_CANDIDATES = 64
M.MAX_NATIVE_RECORDS = 4096

local OPTION_FIELDS = {
    capture_id = true,
    spawner = true,
    observer = true,
    getinfo = true,
    globals = true,
}

local SCALAR_FIELDS = {
    "num_weak",
    "num_upgrades",
    "upgrade_streak",
    "num_spawns",
    "upgrade_max",
    "used_bosses",
    "num_bosses",
}

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

local function bounded_integer(value)
    return integer(value) and value >= -1000000 and value <= 1000000
end

local function valid_capture_id(value)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= 96
        and string.match(value, "^[a-z][a-z0-9._-]*$") ~= nil
end

local function normalized_source(value)
    if type(value) ~= "string" then return nil end
    if string.sub(value, 1, 1) == "@" then value = string.sub(value, 2) end
    return string.gsub(value, "\\", "/")
end

local function source_suffix_matches(value, suffix)
    local source = normalized_source(value)
    if source == nil then return false end
    return string.sub(source, -string.len(suffix)) == suffix
end

local function observer_count(observer)
    local ok, status = pcall(rawget(observer, "status"))
    if not ok or type(status) ~= "table"
        or rawget(status, "state") ~= "capturing"
        or rawget(status, "patch_installed") ~= true
        or not integer(rawget(status, "record_count"))
        or rawget(status, "record_count") < 0
        or rawget(status, "record_count") > M.MAX_NATIVE_RECORDS then
        return nil
    end
    return rawget(status, "record_count")
end

local function snapshot_ratio(value)
    if value == nil then
        return {present = false, numerator = false, denominator = false}, true
    end
    if type(value) ~= "table"
        or not bounded_integer(rawget(value, 1))
        or not bounded_integer(rawget(value, 2)) then
        return {present = true, numerator = false, denominator = false}, false
    end
    return {
        present = true,
        numerator = rawget(value, 1),
        denominator = rawget(value, 2),
    }, true
end

local function snapshot_inputs(spawner)
    local result = {}
    local valid = true
    for _, field in ipairs(SCALAR_FIELDS) do
        -- NextPawn reads these through ordinary table lookup. Active spawner
        -- instances inherit defaults and per-difficulty settings from Spawner,
        -- so rawget would silently record "unavailable" for values the game
        -- actually consumes.
        local value = spawner[field]
        if value == nil then
            result[field] = false
        elseif bounded_integer(value) then
            result[field] = value
        else
            result[field] = false
            valid = false
        end
    end
    local weak, weak_valid = snapshot_ratio(spawner.curr_weakRatio)
    local upgrade, upgrade_valid =
        snapshot_ratio(spawner.curr_upgradeRatio)
    result.curr_weak_ratio = weak
    result.curr_upgrade_ratio = upgrade
    return result, valid and weak_valid and upgrade_valid
end

local function inspect_source(getinfo, fn, suffix, line)
    local ok, info = pcall(getinfo, fn, "S")
    if not ok or type(info) ~= "table"
        or rawget(info, "what") ~= "Lua"
        or not source_suffix_matches(rawget(info, "source"), suffix)
        or rawget(info, "linedefined") ~= line then
        return nil
    end
    return {
        source = normalized_source(rawget(info, "source")),
        linedefined = rawget(info, "linedefined"),
    }
end

local Controller = {}

function M.new(options)
    if not exact_fields(options, OPTION_FIELDS)
        or not valid_capture_id(rawget(options, "capture_id"))
        or type(rawget(options, "spawner")) ~= "table"
        or type(rawget(options.spawner, "NextPawn")) ~= "function"
        or type(rawget(options, "observer")) ~= "table"
        or type(rawget(options.observer, "status")) ~= "function"
        or type(rawget(options, "getinfo")) ~= "function"
        or type(rawget(options, "globals")) ~= "table"
        or type(rawget(options.globals, "random_element")) ~= "function" then
        return nil, "spawn replay controller options are invalid"
    end
    return {
        capture_id = options.capture_id,
        spawner = options.spawner,
        observer = options.observer,
        getinfo = options.getinfo,
        globals = options.globals,
        original_next_pawn = options.spawner.NextPawn,
        original_random_element = options.globals.random_element,
        next_wrapper = nil,
        random_wrapper = nil,
        spans = {},
        current_span = nil,
        active_depth = 0,
        activated = false,
        consumed = false,
        next_wrapper_restored = false,
        random_wrapper_restored = true,
        restore_conflict = false,
        nested_next_count = 0,
        nested_random_count = 0,
        observer_status_error_count = 0,
        span_overflow_count = 0,
        candidate_overflow_count = 0,
        invalid_candidate_count = 0,
        input_snapshot_error_count = 0,
        random_install_error_count = 0,
        candidate_count_mismatch_count = 0,
        next_source = nil,
        next_linedefined = nil,
        random_source = nil,
        random_linedefined = nil,
        source_locations_verified = false,
        activate = Controller.activate,
        checkpoint = Controller.checkpoint,
        abort = Controller.abort,
    }
end

function Controller:_call_random_element(list)
    if self.current_span == nil then
        return self.original_random_element(list)
    end
    if self.current_span.random_active then
        self.nested_random_count = self.nested_random_count + 1
        return self.original_random_element(list)
    end
    self.current_span.random_active = true
    local entry_count = observer_count(self.observer)
    if entry_count == nil then
        self.observer_status_error_count = self.observer_status_error_count + 1
    end
    local available = {}
    local list_length = type(list) == "table" and #list or -1
    local candidates_valid = type(list) == "table"
        and list_length >= 1 and list_length <= M.MAX_CANDIDATES
    if candidates_valid then
        for index = 1, list_length do
            local candidate = rawget(list, index)
            if type(candidate) ~= "string"
                or string.len(candidate) < 1
                or string.len(candidate) > 96 then
                candidates_valid = false
                break
            end
            available[index] = candidate
        end
    end
    if not candidates_valid then
        self.invalid_candidate_count = self.invalid_candidate_count + 1
        available = {}
    end
    local call_ok, result = pcall(self.original_random_element, list)
    local exit_count = observer_count(self.observer)
    if exit_count == nil then
        self.observer_status_error_count = self.observer_status_error_count + 1
    end
    local events = self.current_span.candidate_events
    if #events >= M.MAX_SPANS then
        self.candidate_overflow_count = self.candidate_overflow_count + 1
    else
        events[#events + 1] = {
            event_id = #events + 1,
            entry_count = entry_count,
            exit_count = exit_count,
            detail = call_ok and "normal" or "original_error",
            list_length = list_length,
            candidates_valid = candidates_valid,
            available = available,
            selected_base = call_ok and result or false,
        }
    end
    self.current_span.random_active = false
    if not call_ok then error(result, 0) end
    return result
end

function Controller:activate()
    if self.consumed or self.activated then
        return nil, "spawn replay controller is already consumed or active"
    end
    if self.spawner.NextPawn ~= self.original_next_pawn
        or self.globals.random_element ~= self.original_random_element then
        return nil, "spawn replay boundary changed before activation"
    end
    local next_identity = inspect_source(
        self.getinfo,
        self.original_next_pawn,
        M.SPAWNER_SOURCE_SUFFIX,
        M.SPAWNER_SOURCE_LINE
    )
    local random_identity = inspect_source(
        self.getinfo,
        self.original_random_element,
        M.RANDOM_ELEMENT_SOURCE_SUFFIX,
        M.RANDOM_ELEMENT_SOURCE_LINE
    )
    if next_identity == nil then
        return nil, "Spawner.NextPawn source identity mismatch"
    end
    if random_identity == nil then
        return nil, "random_element source identity mismatch"
    end
    self.next_source = next_identity.source
    self.next_linedefined = next_identity.linedefined
    self.random_source = random_identity.source
    self.random_linedefined = random_identity.linedefined
    self.source_locations_verified = true

    local controller = self
    self.random_wrapper = function(list)
        return Controller._call_random_element(controller, list)
    end
    self.next_wrapper = function(spawner_self, pawn_tables)
        if controller.active_depth ~= 0 then
            controller.nested_next_count = controller.nested_next_count + 1
            controller.active_depth = controller.active_depth + 1
            local nested_ok, nested_result = pcall(
                controller.original_next_pawn, spawner_self, pawn_tables
            )
            controller.active_depth = controller.active_depth - 1
            if not nested_ok then error(nested_result, 0) end
            return nested_result
        end
        if #controller.spans >= M.MAX_SPANS then
            controller.span_overflow_count = controller.span_overflow_count + 1
            return controller.original_next_pawn(spawner_self, pawn_tables)
        end

        controller.active_depth = 1
        local inputs, inputs_valid = snapshot_inputs(spawner_self)
        if not inputs_valid then
            controller.input_snapshot_error_count =
                controller.input_snapshot_error_count + 1
        end
        local span = {
            span_id = #controller.spans + 1,
            name = "spawner_next_pawn",
            detail = "pending",
            inputs = inputs,
            inputs_valid = inputs_valid,
            candidate_events = {},
            selected_pawn = false,
            selected_max_level = false,
            boss_available = false,
            random_active = false,
            random_wrapper_restored = false,
        }
        controller.current_span = span
        local entry_count = observer_count(controller.observer)
        if entry_count == nil then
            controller.observer_status_error_count =
                controller.observer_status_error_count + 1
        end
        span.entry_count = entry_count

        local installed = false
        if controller.globals.random_element == controller.original_random_element then
            controller.globals.random_element = controller.random_wrapper
            installed = controller.globals.random_element == controller.random_wrapper
        end
        if not installed then
            controller.random_install_error_count =
                controller.random_install_error_count + 1
        end
        local call_ok, result = pcall(
            controller.original_next_pawn, spawner_self, pawn_tables
        )
        if installed and controller.globals.random_element == controller.random_wrapper then
            controller.globals.random_element = controller.original_random_element
            span.random_wrapper_restored =
                controller.globals.random_element == controller.original_random_element
        else
            controller.restore_conflict = true
        end
        controller.random_wrapper_restored =
            controller.random_wrapper_restored and span.random_wrapper_restored

        local exit_count = observer_count(controller.observer)
        if exit_count == nil then
            controller.observer_status_error_count =
                controller.observer_status_error_count + 1
        end
        span.exit_count = exit_count
        span.detail = call_ok and "normal" or "original_error"
        span.selected_pawn = call_ok and result or false
        local event = span.candidate_events[1]
        if call_ok and type(event) == "table"
            and type(rawget(event, "selected_base")) == "string" then
            local max_levels = spawner_self.max_level
            local bosses = rawget(controller.globals, "BossesList")
            if type(max_levels) == "table" and type(bosses) == "table" then
                local selected_max = rawget(max_levels, event.selected_base)
                if selected_max == nil then selected_max = 2 end
                if bounded_integer(selected_max)
                    and selected_max >= 1 and selected_max <= 2 then
                    span.selected_max_level = selected_max
                    span.boss_available =
                        rawget(bosses, event.selected_base .. "Boss") ~= nil
                else
                    controller.input_snapshot_error_count =
                        controller.input_snapshot_error_count + 1
                end
            else
                controller.input_snapshot_error_count =
                    controller.input_snapshot_error_count + 1
            end
        else
            controller.input_snapshot_error_count =
                controller.input_snapshot_error_count + 1
        end
        span.random_active = nil
        if #span.candidate_events ~= 1 then
            controller.candidate_count_mismatch_count =
                controller.candidate_count_mismatch_count + 1
        end
        controller.spans[#controller.spans + 1] = span
        controller.current_span = nil
        controller.active_depth = 0
        if not call_ok then error(result, 0) end
        return result
    end

    self.spawner.NextPawn = self.next_wrapper
    if self.spawner.NextPawn ~= self.next_wrapper then
        self.next_wrapper = nil
        self.random_wrapper = nil
        return nil, "Spawner.NextPawn wrapper installation failed"
    end
    self.activated = true
    return true
end

function Controller:checkpoint()
    if self.consumed then
        return nil, "spawn replay controller is already consumed"
    end
    if not self.activated then
        return nil, "spawn replay controller is not active"
    end
    if self.active_depth ~= 0 or self.current_span ~= nil then
        return nil, "Spawner.NextPawn is active during checkpoint"
    end
    local raw_record_count = observer_count(self.observer)
    if raw_record_count == nil then
        self.observer_status_error_count =
            self.observer_status_error_count + 1
    end
    if self.globals.random_element ~= self.original_random_element then
        self.restore_conflict = true
        if self.globals.random_element == self.random_wrapper then
            self.globals.random_element = self.original_random_element
        end
    end
    self.random_wrapper_restored =
        self.globals.random_element == self.original_random_element
    if self.spawner.NextPawn ~= self.next_wrapper then
        self.restore_conflict = true
    else
        self.spawner.NextPawn = self.original_next_pawn
        self.next_wrapper_restored =
            self.spawner.NextPawn == self.original_next_pawn
    end
    self.activated = false
    self.consumed = true

    local complete = self.next_wrapper_restored
        and self.random_wrapper_restored
        and not self.restore_conflict
        and self.nested_next_count == 0
        and self.nested_random_count == 0
        and self.observer_status_error_count == 0
        and self.span_overflow_count == 0
        and self.candidate_overflow_count == 0
        and self.invalid_candidate_count == 0
        and self.input_snapshot_error_count == 0
        and self.random_install_error_count == 0
        and self.candidate_count_mismatch_count == 0
        and self.source_locations_verified
    return {
        schema_version = 1,
        kind = "spawn_rng_replay_ledger",
        controller_version = M.VERSION,
        capture_id = self.capture_id,
        write_mode = "create_only",
        raw_record_count = raw_record_count,
        source_identity = {
            spawner_expected_sha256 = M.SPAWNER_SOURCE_SHA256,
            spawner_expected_source_suffix = M.SPAWNER_SOURCE_SUFFIX,
            spawner_expected_linedefined = M.SPAWNER_SOURCE_LINE,
            spawner_runtime_source = self.next_source,
            spawner_runtime_linedefined = self.next_linedefined,
            random_element_expected_sha256 = M.RANDOM_ELEMENT_SOURCE_SHA256,
            random_element_expected_source_suffix =
                M.RANDOM_ELEMENT_SOURCE_SUFFIX,
            random_element_expected_linedefined = M.RANDOM_ELEMENT_SOURCE_LINE,
            random_element_runtime_source = self.random_source,
            random_element_runtime_linedefined = self.random_linedefined,
            source_locations_verified = self.source_locations_verified,
        },
        integrity = {
            complete = complete,
            next_wrapper_restored = self.next_wrapper_restored,
            random_wrapper_restored = self.random_wrapper_restored,
            restore_conflict = self.restore_conflict,
            nested_next_count = self.nested_next_count,
            nested_random_count = self.nested_random_count,
            observer_status_error_count = self.observer_status_error_count,
            span_overflow_count = self.span_overflow_count,
            candidate_overflow_count = self.candidate_overflow_count,
            invalid_candidate_count = self.invalid_candidate_count,
            input_snapshot_error_count = self.input_snapshot_error_count,
            random_install_error_count = self.random_install_error_count,
            candidate_count_mismatch_count = self.candidate_count_mismatch_count,
            active_depth = self.active_depth,
        },
        spans = self.spans,
        summary = {
            span_count = #self.spans,
            candidate_event_count = (function()
                local count = 0
                for _, span in ipairs(self.spans) do
                    count = count + #span.candidate_events
                end
                return count
            end)(),
            complete = complete,
        },
    }
end

function Controller:abort()
    if self.consumed then
        return self.next_wrapper_restored and self.random_wrapper_restored
    end
    if self.globals.random_element == self.random_wrapper then
        self.globals.random_element = self.original_random_element
    elseif self.globals.random_element ~= self.original_random_element then
        self.restore_conflict = true
    end
    self.random_wrapper_restored =
        self.globals.random_element == self.original_random_element
    if self.activated and self.spawner.NextPawn == self.next_wrapper then
        self.spawner.NextPawn = self.original_next_pawn
        self.next_wrapper_restored =
            self.spawner.NextPawn == self.original_next_pawn
    elseif self.activated then
        self.restore_conflict = true
    end
    self.activated = false
    self.consumed = true
    return self.next_wrapper_restored
        and self.random_wrapper_restored
        and not self.restore_conflict
end

return M
