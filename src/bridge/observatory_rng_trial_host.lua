-- One-shot host for a matched Observatory RNG wrapper experiment.
--
-- Loading this module is inert. A caller must provide one validated capsule,
-- the separately supplied activation nonce and condition, an exact controller
-- module, a live-state provider, and create-only writers. The host waits for
-- the capsule's exact enemy-phase identity, makes one synthetic one-argument
-- RNG-global call in both conditions, and restores the original target before
-- publishing either the raw trace or the trial result.

local M = {}

M.VERSION = "observatory-rng-trial-host/2"

local CAPSULE_FIELDS = {
    schema_version = true,
    kind = true,
    capture_track = true,
    arm_packet_sha256 = true,
    packet = true,
    probe = true,
    rng_control = true,
    expected_save = true,
}

local RANDOM_INT_PROBE_FIELDS = {
    kind = true,
    upper_bound = true,
}

local RANDOM_BOOL_PROBE_FIELDS = {
    kind = true,
    argument = true,
}

local EXPECTED_SAVE_FIELDS = {
    mission_id = true,
    mission_slot = true,
    turn = true,
    master_seed = true,
    region_id = true,
    ai_seed = true,
}

local RNG_CONTROL_FIELDS = {
    kind = true,
    seed = true,
    expected_result = true,
    helper_version = true,
    helper_sha256 = true,
    executable_sha256 = true,
    build_id = true,
    architecture = true,
    rng_seed_rva = true,
    rng_seed_region_sha256 = true,
}

local OPTION_FIELDS = {
    condition = true,
    activation_nonce = true,
    capsule_sha256 = true,
    capsule = true,
    controller_module = true,
    rng_seed_helper = true,
    hook_holder = true,
    live_state_provider = true,
    raw_writer = true,
    result_writer = true,
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

local function lower_sha256(value)
    return type(value) == "string"
        and string.len(value) == 64
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function activation_nonce(value)
    return type(value) == "string"
        and string.len(value) >= 32
        and string.len(value) <= 64
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function copy_runtime(runtime)
    local result = {}
    for key, _ in pairs(RUNTIME_FIELDS) do result[key] = runtime[key] end
    return result
end

local function runtime_matches_manifest(runtime, manifest)
    return runtime.mission_id == manifest.expected_mission_id
        and runtime.turn == manifest.expected_turn
        and runtime.phase == manifest.expected_phase
        and runtime.timeline_fingerprint == manifest.timeline_fingerprint
        and runtime.master_seed == manifest.master_seed
        and runtime.region_id == manifest.region_id
        and runtime.ai_seed_fingerprint == manifest.ai_seed_fingerprint
end

local function validate_capsule(capsule)
    local rng = type(capsule) == "table" and rawget(capsule, "rng_control")
    local probe = type(capsule) == "table" and rawget(capsule, "probe")
    if not exact_fields(capsule, CAPSULE_FIELDS)
        or capsule.schema_version ~= 2
        or capsule.kind ~= "observatory_rng_trial_capsule"
        or (capsule.capture_track ~= "owner_local_modified"
            and capsule.capture_track ~= "pristine_reference")
        or not lower_sha256(capsule.arm_packet_sha256)
        or type(capsule.packet) ~= "table"
        or type(probe) ~= "table"
        or not exact_fields(rng, RNG_CONTROL_FIELDS)
        or rng.kind ~= "build_keyed_seed"
        or not integer(rng.seed)
        or rng.seed < 0
        or rng.seed > 2147483647
        or rng.helper_version ~= "observatory-rng-seed-helper/1"
        or not lower_sha256(rng.helper_sha256)
        or not lower_sha256(rng.executable_sha256)
        or type(rng.build_id) ~= "string"
        or rng.build_id == ""
        or rng.architecture ~= "x86"
        or type(rng.rng_seed_rva) ~= "string"
        or string.match(rng.rng_seed_rva, "^0x[0-9a-f]+$") == nil
        or string.len(rng.rng_seed_rva) ~= 10
        or not lower_sha256(rng.rng_seed_region_sha256)
        or not exact_fields(capsule.expected_save, EXPECTED_SAVE_FIELDS)
        or type(capsule.expected_save.mission_id) ~= "string"
        or capsule.expected_save.mission_id == ""
        or type(capsule.expected_save.mission_slot) ~= "string"
        or capsule.expected_save.mission_slot == ""
        or not integer(capsule.expected_save.turn)
        or capsule.expected_save.turn < 0
        or not integer(capsule.expected_save.master_seed)
        or type(capsule.expected_save.region_id) ~= "string"
        or capsule.expected_save.region_id == ""
        or not integer(capsule.expected_save.ai_seed) then
        return nil, "invalid trial capsule"
    end
    local probe_value = nil
    if probe.kind == "random_int" then
        if not exact_fields(probe, RANDOM_INT_PROBE_FIELDS)
            or not integer(probe.upper_bound)
            or probe.upper_bound < 2
            or probe.upper_bound > 2147483647
            or not integer(rng.expected_result)
            or rng.expected_result < 0
            or rng.expected_result >= probe.upper_bound then
            return nil, "invalid random_int trial capsule"
        end
        probe_value = probe.upper_bound
    elseif probe.kind == "random_bool" then
        if not exact_fields(probe, RANDOM_BOOL_PROBE_FIELDS)
            or not integer(probe.argument)
            or probe.argument < 1
            or probe.argument > 2147483647
            or type(rng.expected_result) ~= "boolean" then
            return nil, "invalid random_bool trial capsule"
        end
        probe_value = probe.argument
    else
        return nil, "unsupported trial probe"
    end
    local state = (rng.seed * 0x343fd + 0x269ec3) % 4294967296
    local draw = math.floor(state / 65536) % 32768
    local expected = draw % probe_value
    if probe.kind == "random_bool" then expected = expected == 0 end
    if rng.expected_result ~= expected then
        return nil, "trial capsule RNG expectation is invalid"
    end
    local packet = capsule.packet
    local manifest = rawget(packet, "manifest")
    local plan = rawget(packet, "hook_plan")
    local build = rawget(packet, "build_identity")
    if rawget(packet, "arm_packet_schema_version") ~= 1
        or type(manifest) ~= "table"
        or type(plan) ~= "table"
        or type(build) ~= "table"
        or rawget(build, "platform") ~= "windows"
        or rawget(build, "architecture") ~= rng.architecture
        or rawget(build, "build_id") ~= rng.build_id
        or rawget(build, "executable_sha256") ~= rng.executable_sha256
        or manifest.capture_id == nil
        or manifest.checkpoint_seq == nil
        or manifest.expected_phase ~= "combat_enemy"
        or manifest.arm_nonce == nil
        or not activation_nonce(manifest.arm_nonce)
        or manifest.expected_mission_id ~= capsule.expected_save.mission_id
        or manifest.expected_turn ~= capsule.expected_save.turn
        or manifest.master_seed ~= capsule.expected_save.master_seed
        or manifest.region_id ~= capsule.expected_save.region_id then
        return nil, "trial capsule does not match its arm packet"
    end
    local installed = nil
    local installed_count = 0
    for _, entry in ipairs(plan) do
        if type(entry) ~= "table" then return nil, "invalid hook plan" end
        if entry.status == "installed" then
            installed_count = installed_count + 1
            installed = entry
        end
    end
    if installed_count ~= 1
        or installed.event_kind ~= probe.kind
        or installed.target ~= "_G." .. probe.kind
        or installed.target_kind ~= "lua_global"
        or type(installed.hook_id) ~= "string"
        or installed.hook_id == "" then
        return nil, "trial capsule requires one exact RNG-global hook"
    end
    return installed
end

local Host = {}
Host.__index = Host

function Host:_provider()
    local ok, runtime, runtime_error = pcall(self.live_state_provider)
    if not ok then return nil, "live state provider failed" end
    if not exact_fields(runtime, RUNTIME_FIELDS)
        or not integer(runtime.now_epoch)
        or type(runtime.mission_id) ~= "string"
        or not integer(runtime.turn)
        or type(runtime.phase) ~= "string"
        or not lower_sha256(runtime.timeline_fingerprint)
        or not integer(runtime.master_seed)
        or type(runtime.region_id) ~= "string"
        or not lower_sha256(runtime.ai_seed_fingerprint) then
        return nil, runtime_error or "invalid live state"
    end
    return copy_runtime(runtime)
end

function Host:_controller_status()
    if not self.controller then
        return {
            consumed = false,
            prepared = false,
            activated = false,
            written = false,
        }
    end
    local ok, status = pcall(self.controller.status, self.controller)
    if ok and type(status) == "table" then return status end
    return {
        consumed = true,
        prepared = false,
        activated = false,
        written = self.raw_written == true,
    }
end

function Host:_result(status, error_text, result, before, after)
    local probe = {
        kind = self.probe_kind,
        result = result,
    }
    if self.probe_kind == "random_int" then
        probe.upper_bound = self.probe_argument
        if result == nil then probe.result = -1 end
    else
        probe.argument = self.probe_argument
        if result == nil then probe.result = false end
    end
    return {
        schema_version = 2,
        kind = "observatory_rng_trial_result",
        host_version = M.VERSION,
        capture_track = self.capsule.capture_track,
        condition = self.condition,
        capsule_sha256 = self.capsule_sha256,
        arm_packet_sha256 = self.capsule.arm_packet_sha256,
        capture_id = self.manifest.capture_id,
        checkpoint_seq = self.manifest.checkpoint_seq,
        status = status,
        error = error_text or "",
        probe = probe,
        rng_control = {
            kind = self.capsule.rng_control.kind,
            seed = self.capsule.rng_control.seed,
            expected_result = self.capsule.rng_control.expected_result,
            helper_version = self.capsule.rng_control.helper_version,
            helper_sha256 = self.capsule.rng_control.helper_sha256,
            seed_applied = self.seed_applied == true,
        },
        runtime_before = before or {},
        runtime_after = after or {},
        controller_status = self:_controller_status(),
        raw_written = self.raw_written == true,
        target_restored = self.hook_holder[self.probe_kind] == self.original,
    }
end

function Host:_publish_result(status, error_text, result, before, after)
    if self.result_published then return false, "result already published" end
    local document = self:_result(status, error_text, result, before, after)
    local ok, wrote, write_error = pcall(self.result_writer, document)
    if not ok or wrote ~= true then
        return false, write_error or "trial result writer failed"
    end
    self.result_published = true
    return true
end

function Host:_disarm()
    if self.controller then pcall(self.controller.disarm, self.controller) end
end

function Host:_fail(error_text, before, after)
    self:_disarm()
    self.state = "failed"
    local published, publish_error = self:_publish_result(
        "failed", tostring(error_text), nil, before, after
    )
    if not published then return "failed", publish_error end
    return "failed", tostring(error_text)
end

function Host:_new_controller()
    local raw_writer = function(snapshot)
        local wrote, write_error = self.raw_writer(snapshot)
        if wrote == true then self.raw_written = true end
        return wrote, write_error
    end
    local ok, controller_or_error = pcall(
        self.controller_module.new,
        {
            runtime_provider = function() return self.runtime_snapshot end,
            hook_bindings = {
                [self.installed.hook_id] = {
                    holder = self.hook_holder,
                    key = self.probe_kind,
                },
            },
            raw_writer = raw_writer,
        }
    )
    if not ok or type(controller_or_error) ~= "table" then
        return nil, "controller construction failed"
    end
    return controller_or_error
end

function Host:_run(before)
    self.runtime_snapshot = before
    local seeded_ok, seeded = pcall(
        self.rng_seed_helper.seed,
        self.capsule.rng_control.seed
    )
    if not seeded_ok or seeded ~= true then
        return self:_fail("native RNG seed helper failed", before, nil)
    end
    self.seed_applied = true
    local controller, controller_error = self:_new_controller()
    if not controller then return self:_fail(controller_error, before, nil) end
    self.controller = controller
    local prepared, prepare_error = controller:prepare(self.capsule.packet)
    if not prepared then return self:_fail(prepare_error, before, nil) end
    if self.condition == "exact_hook" then
        local activated, activate_error = controller:activate(
            self.activation_nonce
        )
        if not activated then return self:_fail(activate_error, before, nil) end
    end

    local call = {pcall(
        self.hook_holder[self.probe_kind],
        self.probe_argument
    )}
    if not call[1] then return self:_fail(call[2], before, nil) end
    local result = call[2]
    if (self.probe_kind == "random_int"
            and (not integer(result)
                or result < 0
                or result >= self.probe_argument))
        or (self.probe_kind == "random_bool" and type(result) ~= "boolean") then
        return self:_fail("probe returned an invalid result", before, nil)
    end
    if result ~= self.capsule.rng_control.expected_result then
        return self:_fail("probe did not consume the seeded RNG state", before, nil)
    end

    local after, after_error = self:_provider()
    if not after then return self:_fail(after_error, before, nil) end
    self.runtime_snapshot = after
    if not runtime_matches_manifest(after, self.manifest) then
        return self:_fail("runtime identity changed during probe", before, after)
    end
    if self.condition == "exact_hook" then
        local checkpointed, checkpoint_error = controller:checkpoint("explicit")
        if not checkpointed then
            return self:_fail(checkpoint_error, before, after)
        end
    else
        controller:disarm()
    end
    if self.hook_holder[self.probe_kind] ~= self.original then
        return self:_fail("RNG target was not restored", before, after)
    end
    self.state = "complete"
    local published, publish_error = self:_publish_result(
        "complete", "", result, before, after
    )
    if not published then
        self.state = "failed"
        return "failed", publish_error
    end
    return "complete"
end

function Host:step()
    if self.state ~= "waiting" then return self.state, self.last_error end
    if self.in_step then return "waiting" end
    self.in_step = true
    local ok, status, step_error = pcall(function()
        local runtime, runtime_error = self:_provider()
        if not runtime then return self:_fail(runtime_error, nil, nil) end
        if runtime.now_epoch > self.manifest.expires_epoch then
            return self:_fail("trial capture window expired", runtime, nil)
        end
        if runtime.now_epoch < self.manifest.activated_epoch then
            return "waiting"
        end
        if runtime.mission_id == "" or runtime.phase == "unknown" then
            return "waiting"
        end
        if runtime.mission_id ~= self.manifest.expected_mission_id then
            return self:_fail("unexpected active mission", runtime, nil)
        end
        if runtime.turn < self.manifest.expected_turn then return "waiting" end
        if runtime.turn > self.manifest.expected_turn then
            return self:_fail("expected turn was missed", runtime, nil)
        end
        if runtime.phase ~= self.manifest.expected_phase then return "waiting" end
        if not runtime_matches_manifest(runtime, self.manifest) then
            return self:_fail("live runtime identity mismatch", runtime, nil)
        end
        return self:_run(runtime)
    end)
    self.in_step = false
    if not ok then
        status, step_error = self:_fail(
            "trial host failed: " .. tostring(status), nil, nil
        )
    end
    self.last_error = step_error
    return status, step_error
end

function Host:status()
    return {
        state = self.state,
        condition = self.condition,
        capture_id = self.manifest.capture_id,
        checkpoint_seq = self.manifest.checkpoint_seq,
        raw_written = self.raw_written == true,
        seed_applied = self.seed_applied == true,
        result_published = self.result_published == true,
        target_restored = self.hook_holder[self.probe_kind] == self.original,
        error = self.last_error or "",
    }
end

function Host:abort(reason)
    if self.state ~= "waiting" then return self.state, self.last_error end
    local status, abort_error = self:_fail(
        reason or "trial host aborted", nil, nil
    )
    self.last_error = abort_error
    return status, abort_error
end

function M.new(options)
    if not exact_fields(options, OPTION_FIELDS)
        or (options.condition ~= "control"
            and options.condition ~= "exact_hook")
        or not activation_nonce(options.activation_nonce)
        or not lower_sha256(options.capsule_sha256)
        or type(options.controller_module) ~= "table"
        or type(options.controller_module.new) ~= "function"
        or type(options.rng_seed_helper) ~= "table"
        or type(rawget(options.rng_seed_helper, "seed")) ~= "function"
        or type(options.hook_holder) ~= "table"
        or type(options.live_state_provider) ~= "function"
        or type(options.raw_writer) ~= "function"
        or type(options.result_writer) ~= "function" then
        error("invalid RNG trial host options", 2)
    end
    local installed, capsule_error = validate_capsule(options.capsule)
    if not installed then error(capsule_error, 2) end
    local probe_kind = options.capsule.probe.kind
    if type(rawget(options.hook_holder, probe_kind)) ~= "function" then
        error("RNG trial target is not a function", 2)
    end
    local manifest = options.capsule.packet.manifest
    if options.activation_nonce ~= manifest.arm_nonce then
        error("activation nonce does not match capsule", 2)
    end
    local rng = options.capsule.rng_control
    local helper = options.rng_seed_helper
    if rawget(helper, "VERSION") ~= rng.helper_version
        or rawget(helper, "BUILD_ID") ~= rng.build_id
        or rawget(helper, "EXECUTABLE_SHA256") ~= rng.executable_sha256
        or rawget(helper, "ARCHITECTURE") ~= rng.architecture
        or rawget(helper, "RNG_SEED_RVA") ~= rng.rng_seed_rva
        or rawget(helper, "RNG_SEED_REGION_SHA256")
            ~= rng.rng_seed_region_sha256 then
        error("native RNG seed helper identity mismatch", 2)
    end
    local self = setmetatable({}, Host)
    self.condition = options.condition
    self.activation_nonce = options.activation_nonce
    self.capsule_sha256 = options.capsule_sha256
    self.capsule = options.capsule
    self.controller_module = options.controller_module
    self.rng_seed_helper = options.rng_seed_helper
    self.hook_holder = options.hook_holder
    self.live_state_provider = options.live_state_provider
    self.raw_writer = options.raw_writer
    self.result_writer = options.result_writer
    self.installed = installed
    self.manifest = manifest
    self.probe_kind = probe_kind
    self.probe_argument = options.capsule.probe.upper_bound
        or options.capsule.probe.argument
    self.original = options.hook_holder[probe_kind]
    self.controller = nil
    self.runtime_snapshot = nil
    self.state = "waiting"
    self.last_error = nil
    self.in_step = false
    self.raw_written = false
    self.seed_applied = false
    self.result_published = false
    -- Publish only the three host entry points Mod Loader is allowed to call
    -- as own fields. Internal helpers remain on the private metatable.
    self.step = Host.step
    self.status = Host.status
    self.abort = Host.abort
    return self
end

return M
