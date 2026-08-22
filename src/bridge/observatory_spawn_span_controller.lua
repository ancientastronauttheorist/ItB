-- Exact, one-family boundary controller for Spawner:NextPawn.
--
-- Loading and constructing this module are inert.  activate() temporarily
-- replaces exactly one build-pinned Lua method.  The wrapper samples only the
-- already-loaded native RNG observer's bounded status table immediately before
-- and after the original call.  checkpoint() restores the original function
-- before returning a bounded, I/O-free span ledger.

local M = {}

M.VERSION = "observatory-spawn-span-controller/1"
M.SPAWNER_SOURCE_SUFFIX = "scripts/spawner_backend.lua"
M.SPAWNER_SOURCE_LINE = 174
M.SPAWNER_SOURCE_SHA256 =
    "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
M.MAX_SPANS = 64
M.MAX_NATIVE_RECORDS = 4096

local OPTION_FIELDS = {
    capture_id = true,
    spawner = true,
    observer = true,
    getinfo = true,
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

local function source_suffix_matches(value)
    local source = normalized_source(value)
    if source == nil then return false end
    local suffix = M.SPAWNER_SOURCE_SUFFIX
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

local Controller = {}

function M.new(options)
    if not exact_fields(options, OPTION_FIELDS)
        or not valid_capture_id(rawget(options, "capture_id"))
        or type(rawget(options, "spawner")) ~= "table"
        or type(rawget(options.spawner, "NextPawn")) ~= "function"
        or type(rawget(options, "observer")) ~= "table"
        or type(rawget(options.observer, "status")) ~= "function"
        or type(rawget(options, "getinfo")) ~= "function" then
        return nil, "spawn span controller options are invalid"
    end
    -- The hardened loader validates the one-shot instance with rawget so a
    -- metatable cannot swap methods after construction.  Keep the callable
    -- surface directly on the instance for that exact contract.
    return {
        capture_id = options.capture_id,
        spawner = options.spawner,
        observer = options.observer,
        getinfo = options.getinfo,
        original = options.spawner.NextPawn,
        wrapper = nil,
        spans = {},
        active_depth = 0,
        activated = false,
        consumed = false,
        restore_conflict = false,
        wrapper_restored = false,
        nested_call_count = 0,
        observer_status_error_count = 0,
        span_overflow_count = 0,
        count_regression_count = 0,
        source = nil,
        linedefined = nil,
        source_location_verified = false,
        activate = Controller.activate,
        checkpoint = Controller.checkpoint,
        abort = Controller.abort,
    }
end

function Controller:activate()
    if self.consumed or self.activated then
        return nil, "spawn span controller is already consumed or active"
    end
    if self.spawner.NextPawn ~= self.original then
        return nil, "Spawner.NextPawn changed before activation"
    end
    local ok, info = pcall(self.getinfo, self.original, "S")
    if not ok or type(info) ~= "table"
        or rawget(info, "what") ~= "Lua"
        or not source_suffix_matches(rawget(info, "source"))
        or rawget(info, "linedefined") ~= M.SPAWNER_SOURCE_LINE then
        return nil, "Spawner.NextPawn source identity mismatch"
    end
    self.source = normalized_source(rawget(info, "source"))
    self.linedefined = rawget(info, "linedefined")
    self.source_location_verified = true

    local controller = self
    self.wrapper = function(spawner_self, pawn_tables)
        if controller.active_depth ~= 0 then
            controller.nested_call_count = controller.nested_call_count + 1
            controller.active_depth = controller.active_depth + 1
            local ok_nested, nested_result = pcall(
                controller.original, spawner_self, pawn_tables
            )
            controller.active_depth = controller.active_depth - 1
            if not ok_nested then error(nested_result, 0) end
            return nested_result
        end

        controller.active_depth = 1
        local entry_count = observer_count(controller.observer)
        if entry_count == nil then
            controller.observer_status_error_count =
                controller.observer_status_error_count + 1
        end
        local call_ok, result = pcall(
            controller.original, spawner_self, pawn_tables
        )
        local exit_count = observer_count(controller.observer)
        if exit_count == nil then
            controller.observer_status_error_count =
                controller.observer_status_error_count + 1
        end
        if entry_count ~= nil and exit_count ~= nil
            and exit_count < entry_count then
            controller.count_regression_count =
                controller.count_regression_count + 1
        end

        if #controller.spans >= M.MAX_SPANS then
            controller.span_overflow_count =
                controller.span_overflow_count + 1
        else
            controller.spans[#controller.spans + 1] = {
                span_id = #controller.spans + 1,
                name = "spawner_next_pawn",
                entry_count = entry_count,
                exit_count = exit_count,
                detail = call_ok and "normal" or "original_error",
                selected_pawn = call_ok and result or false,
            }
        end
        controller.active_depth = 0
        if not call_ok then error(result, 0) end
        return result
    end
    self.spawner.NextPawn = self.wrapper
    if self.spawner.NextPawn ~= self.wrapper then
        self.wrapper = nil
        return nil, "Spawner.NextPawn wrapper installation failed"
    end
    self.activated = true
    return true
end

function Controller:checkpoint()
    if self.consumed then
        return nil, "spawn span controller is already consumed"
    end
    if not self.activated then
        return nil, "spawn span controller is not active"
    end
    if self.active_depth ~= 0 then
        return nil, "Spawner.NextPawn is active during checkpoint"
    end
    local raw_record_count = observer_count(self.observer)
    if raw_record_count == nil then
        self.observer_status_error_count =
            self.observer_status_error_count + 1
    end
    if self.spawner.NextPawn ~= self.wrapper then
        self.restore_conflict = true
    else
        self.spawner.NextPawn = self.original
        self.wrapper_restored = self.spawner.NextPawn == self.original
    end
    self.activated = false
    self.consumed = true

    local complete = self.wrapper_restored
        and not self.restore_conflict
        and self.nested_call_count == 0
        and self.observer_status_error_count == 0
        and self.span_overflow_count == 0
        and self.count_regression_count == 0
        and self.source_location_verified
    return {
        schema_version = 1,
        kind = "spawn_rng_span_ledger",
        controller_version = M.VERSION,
        capture_id = self.capture_id,
        write_mode = "create_only",
        raw_record_count = raw_record_count,
        source_identity = {
            expected_sha256 = M.SPAWNER_SOURCE_SHA256,
            expected_source_suffix = M.SPAWNER_SOURCE_SUFFIX,
            expected_linedefined = M.SPAWNER_SOURCE_LINE,
            runtime_source = self.source,
            runtime_linedefined = self.linedefined,
            source_location_verified = self.source_location_verified,
        },
        integrity = {
            complete = complete,
            wrapper_restored = self.wrapper_restored,
            restore_conflict = self.restore_conflict,
            nested_call_count = self.nested_call_count,
            observer_status_error_count = self.observer_status_error_count,
            span_overflow_count = self.span_overflow_count,
            count_regression_count = self.count_regression_count,
            active_depth = self.active_depth,
        },
        spans = self.spans,
        summary = {
            span_count = #self.spans,
            complete = complete,
        },
    }
end

function Controller:abort()
    if self.consumed then return self.wrapper_restored end
    if self.activated and self.spawner.NextPawn == self.wrapper then
        self.spawner.NextPawn = self.original
        self.wrapper_restored = self.spawner.NextPawn == self.original
    elseif self.activated then
        self.restore_conflict = true
    end
    self.activated = false
    self.consumed = true
    return self.wrapper_restored and not self.restore_conflict
end

return M
