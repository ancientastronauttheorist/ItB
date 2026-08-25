-- One-shot host for natural enemy callback-boundary experiments.
--
-- Loading this module is inert. Construction only enumerates callback table
-- identities; it performs no file I/O, calls no candidate, and installs no
-- wrapper. The Mod Loader explicitly advances the host at the enemy NextTurn
-- boundary and keeps it alive through the enemy phase, the following player
-- transition, and that player's first completed BaseUpdate. This covers the
-- engine's deferred next-action planning while still restoring every slot at
-- one reviewed mission boundary before publishing the small result document.

local M = {}

M.VERSION = "observatory-callback-trial-host/2"

local CAPSULE_FIELDS = {
    schema_version = true,
    kind = true,
    capture_track = true,
    arm_packet_sha256 = true,
    packet = true,
    callback_family = true,
    binding_manifest_sha256 = true,
    binding_manifest = true,
    callback_join_sha256 = true,
    callback_join = true,
    expected_save = true,
}

local EXPECTED_SAVE_FIELDS = {
    mission_id = true,
    mission_slot = true,
    turn = true,
    master_seed = true,
    region_id = true,
    ai_seed = true,
}

local OPTION_FIELDS = {
    condition = true,
    activation_nonce = true,
    capsule_sha256 = true,
    capsule = true,
    controller_module = true,
    callback_manifest_module = true,
    callback_bindings_module = true,
    live_state_provider = true,
    raw_writer = true,
    result_writer = true,
    globals = true,
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

local CALLBACK_FAMILIES = {
    get_target_area = true,
    enemy_target_score = true,
    get_skill_effect = true,
    score_positioning = true,
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

local function bounded_text(value, maximum)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= maximum
end

local function deep_equal(left, right)
    local seen = 0
    local function compare(a, b, depth)
        seen = seen + 1
        if seen > 200000 or depth > 64 or type(a) ~= type(b) then return false end
        if type(a) ~= "table" then return a == b end
        for key, value in pairs(a) do
            if rawget(b, key) == nil or not compare(value, rawget(b, key), depth + 1) then
                return false
            end
        end
        for key, _ in pairs(b) do
            if rawget(a, key) == nil then return false end
        end
        return true
    end
    return compare(left, right, 0)
end

local function copy_runtime(runtime)
    local result = {}
    for key, _ in pairs(RUNTIME_FIELDS) do result[key] = runtime[key] end
    return result
end

local function runtime_stable_identity_matches(runtime, manifest)
    return runtime.mission_id == manifest.expected_mission_id
        and runtime.timeline_fingerprint == manifest.timeline_fingerprint
        and runtime.master_seed == manifest.master_seed
        and runtime.region_id == manifest.region_id
        and runtime.ai_seed_fingerprint == manifest.ai_seed_fingerprint
end

local function runtime_matches_capture_start(runtime, manifest)
    return runtime_stable_identity_matches(runtime, manifest)
        and runtime.turn == manifest.expected_turn
        and runtime.phase == manifest.expected_phase
end

local function runtime_matches_capture_finish(runtime, manifest)
    return runtime_stable_identity_matches(runtime, manifest)
        and runtime.turn == manifest.expected_turn + 1
        and runtime.phase == "combat_player"
end

local function validate_capsule(capsule)
    if not exact_fields(capsule, CAPSULE_FIELDS)
        or capsule.schema_version ~= 1
        or capsule.kind ~= "observatory_callback_trial_capsule"
        or (capsule.capture_track ~= "owner_local_modified"
            and capsule.capture_track ~= "pristine_reference")
        or not lower_sha256(capsule.arm_packet_sha256)
        or not CALLBACK_FAMILIES[capsule.callback_family]
        or not lower_sha256(capsule.binding_manifest_sha256)
        or type(capsule.binding_manifest) ~= "table"
        or not lower_sha256(capsule.callback_join_sha256)
        or type(capsule.callback_join) ~= "table"
        or not exact_fields(capsule.expected_save, EXPECTED_SAVE_FIELDS)
        or not bounded_text(capsule.expected_save.mission_id, 256)
        or not bounded_text(capsule.expected_save.mission_slot, 128)
        or not integer(capsule.expected_save.turn)
        or capsule.expected_save.turn < 0
        or not integer(capsule.expected_save.master_seed)
        or not bounded_text(capsule.expected_save.region_id, 128)
        or not integer(capsule.expected_save.ai_seed) then
        return nil, "invalid callback trial capsule"
    end
    local packet = capsule.packet
    local manifest = type(packet) == "table" and rawget(packet, "manifest")
    local plan = type(packet) == "table" and rawget(packet, "hook_plan")
    if type(manifest) ~= "table"
        or type(plan) ~= "table"
        or manifest.controller_version ~= "observatory-callback-controller/1"
        or manifest.expected_phase ~= "combat_enemy"
        or not bounded_text(manifest.capture_id, 128)
        or not integer(manifest.checkpoint_seq)
        or manifest.checkpoint_seq < 0
        or not activation_nonce(manifest.arm_nonce)
        or manifest.expected_mission_id ~= capsule.expected_save.mission_id
        or manifest.expected_turn ~= capsule.expected_save.turn
        or manifest.master_seed ~= capsule.expected_save.master_seed
        or manifest.region_id ~= capsule.expected_save.region_id then
        return nil, "callback capsule does not match its arm packet"
    end
    local installed_family = nil
    local installed_count = 0
    for _, entry in ipairs(plan) do
        if type(entry) ~= "table" then return nil, "invalid callback hook plan" end
        if entry.status == "installed" then
            installed_count = installed_count + 1
            if installed_family ~= nil and installed_family ~= entry.event_kind then
                return nil, "callback hook plan mixes installed families"
            end
            installed_family = entry.event_kind
        end
    end
    if installed_count < 1 or installed_family ~= capsule.callback_family then
        return nil, "callback family does not match its arm packet"
    end
    return manifest
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

function Host:_all_restored()
    for _, binding in ipairs(self.live_bindings) do
        if binding.holder[binding.key] ~= binding.original then return false end
    end
    return true
end

function Host:_controller_status()
    if not self.controller then
        return {consumed = false, prepared = false, activated = false, written = false}
    end
    local ok, status = pcall(self.controller.status, self.controller)
    if ok and type(status) == "table" then return status end
    return {consumed = true, prepared = false, activated = false, written = false}
end

function Host:_result(status, error_text, before, after)
    return {
        schema_version = 1,
        kind = "observatory_callback_trial_result",
        host_version = M.VERSION,
        capture_track = self.capsule.capture_track,
        condition = self.condition,
        capsule_sha256 = self.capsule_sha256,
        arm_packet_sha256 = self.capsule.arm_packet_sha256,
        binding_manifest_sha256 = self.capsule.binding_manifest_sha256,
        callback_join_sha256 = self.capsule.callback_join_sha256,
        capture_id = self.manifest.capture_id,
        checkpoint_seq = self.manifest.checkpoint_seq,
        callback_family = self.capsule.callback_family,
        status = status,
        error = error_text or "",
        runtime_before = before or {},
        runtime_after = after or {},
        controller_status = self:_controller_status(),
        raw_written = self.raw_written == true,
        raw_event_count = self.raw_event_count,
        attempted_calls = self.attempted_calls,
        serialization_errors = self.serialization_errors,
        slot_count = #self.live_bindings,
        slots_restored = self:_all_restored(),
    }
end

function Host:_publish(status, error_text, before, after)
    if self.result_published then return false, "result already published" end
    local ok, wrote, write_error = pcall(
        self.result_writer,
        self:_result(status, error_text, before, after)
    )
    if not ok or wrote ~= true then
        return false, write_error or "callback result writer failed"
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
    local published, publish_error = self:_publish(
        "failed", tostring(error_text), before, after
    )
    if not published then return "failed", publish_error end
    return "failed", tostring(error_text)
end

function Host:_new_controller()
    local raw_writer = function(snapshot)
        if type(snapshot) ~= "table"
            or type(snapshot.events) ~= "table"
            or type(snapshot.attempted_calls) ~= "table"
            or type(snapshot.summary) ~= "table" then
            return false, "invalid callback raw checkpoint"
        end
        self.raw_event_count = #snapshot.events
        self.attempted_calls = snapshot.attempted_calls[self.capsule.callback_family] or 0
        self.serialization_errors = snapshot.summary.serialization_errors or 0
        local wrote, write_error = self.raw_writer(snapshot)
        if wrote == true then self.raw_written = true end
        return wrote, write_error
    end
    local ok, controller_or_error = pcall(
        self.controller_module.new,
        {
            runtime_provider = function() return self.runtime_snapshot end,
            binding_document = self.binding_document,
            live_bindings = self.live_bindings,
            raw_writer = raw_writer,
            globals = self.globals,
        }
    )
    if not ok or type(controller_or_error) ~= "table" then
        return nil, "callback controller construction failed"
    end
    return controller_or_error
end

function Host:_begin(runtime)
    self.runtime_snapshot = runtime
    local controller, controller_error = self:_new_controller()
    if not controller then return self:_fail(controller_error, runtime, nil) end
    self.controller = controller
    local prepared, prepare_error = controller:prepare(self.capsule.packet)
    if not prepared then return self:_fail(prepare_error, runtime, nil) end
    if self.condition == "exact_hook" then
        local activated, activate_error = controller:activate(self.activation_nonce)
        if not activated then return self:_fail(activate_error, runtime, nil) end
    end
    if self.condition == "control" and not self:_all_restored() then
        return self:_fail("control preparation changed a callback slot", runtime, nil)
    end
    self.runtime_before = runtime
    self.state = "capturing"
    return "capturing"
end

function Host:_finish(runtime)
    if not runtime_matches_capture_finish(runtime, self.manifest) then
        return self:_fail("runtime identity changed during callback window", self.runtime_before, runtime)
    end
    if self.condition == "exact_hook" then
        local checkpointed, checkpoint_error = self.controller:checkpoint("explicit")
        if not checkpointed then
            return self:_fail(checkpoint_error, self.runtime_before, runtime)
        end
    else
        self.controller:disarm()
    end
    -- The controller's attested runtime provider must remain pinned to the
    -- enemy-boundary identity through checkpoint validation. Record the later
    -- player boundary only after the controller is fully disarmed.
    self.runtime_snapshot = runtime
    if not self:_all_restored() then
        return self:_fail("callback slots were not restored", self.runtime_before, runtime)
    end
    self.state = "complete"
    local published, publish_error = self:_publish(
        "complete", "", self.runtime_before, runtime
    )
    if not published then
        self.state = "failed"
        return "failed", publish_error
    end
    return "complete"
end

function Host:step(stage)
    if stage ~= "next_turn" and stage ~= "base_update_after" then
        return self:_fail("invalid callback host stage", nil, nil)
    end
    if self.state == "complete" or self.state == "failed" then
        return self.state, self.last_error
    end
    if self.in_step then return self.state end
    self.in_step = true
    local ok, status, step_error = pcall(function()
        local runtime, runtime_error = self:_provider()
        if not runtime then return self:_fail(runtime_error, nil, nil) end
        if runtime.now_epoch > self.manifest.expires_epoch then
            return self:_fail("callback capture window expired", runtime, nil)
        end
        if runtime.now_epoch < self.manifest.activated_epoch then return self.state end
        if self.state == "waiting" then
            if stage ~= "next_turn" then return "waiting" end
            if runtime.mission_id == "" or runtime.phase == "unknown" then return "waiting" end
            if runtime.mission_id ~= self.manifest.expected_mission_id then
                return self:_fail("unexpected active mission", runtime, nil)
            end
            if runtime.turn < self.manifest.expected_turn then return "waiting" end
            if runtime.turn > self.manifest.expected_turn then
                return self:_fail("expected turn was missed", runtime, nil)
            end
            if runtime.phase ~= self.manifest.expected_phase then return "waiting" end
            if not runtime_matches_capture_start(runtime, self.manifest) then
                return self:_fail("live runtime identity mismatch", runtime, nil)
            end
            return self:_begin(runtime)
        end
        if self.state == "capturing" then
            if stage == "base_update_after"
                and runtime_matches_capture_finish(runtime, self.manifest) then
                return self:_finish(runtime)
            end
            if runtime_matches_capture_start(runtime, self.manifest)
                or runtime_matches_capture_finish(runtime, self.manifest) then
                return "capturing"
            end
            return self:_fail(
                "runtime identity changed during callback window",
                self.runtime_before,
                runtime
            )
        end
        return self.state
    end)
    self.in_step = false
    if not ok then
        status, step_error = self:_fail(
            "callback trial host failed: " .. tostring(status), nil, nil
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
        callback_family = self.capsule.callback_family,
        raw_written = self.raw_written == true,
        raw_event_count = self.raw_event_count,
        attempted_calls = self.attempted_calls,
        serialization_errors = self.serialization_errors,
        result_published = self.result_published == true,
        slots_restored = self:_all_restored(),
        error = self.last_error or "",
    }
end

function Host:abort(reason)
    if self.state == "complete" or self.state == "failed" then
        return self.state, self.last_error
    end
    local status, abort_error = self:_fail(
        reason or "callback trial host aborted", nil, nil
    )
    self.last_error = abort_error
    return status, abort_error
end

function M.new(options)
    if not exact_fields(options, OPTION_FIELDS)
        or (options.condition ~= "control" and options.condition ~= "exact_hook")
        or not activation_nonce(options.activation_nonce)
        or not lower_sha256(options.capsule_sha256)
        or type(options.controller_module) ~= "table"
        or type(options.controller_module.new) ~= "function"
        or type(options.callback_manifest_module) ~= "table"
        or type(options.callback_bindings_module) ~= "table"
        or type(options.callback_bindings_module.enumerate) ~= "function"
        or type(options.live_state_provider) ~= "function"
        or type(options.raw_writer) ~= "function"
        or type(options.result_writer) ~= "function"
        or type(options.globals) ~= "table" then
        error("invalid callback trial host options", 2)
    end
    local manifest, capsule_error = validate_capsule(options.capsule)
    if not manifest then error(capsule_error, 2) end
    if options.activation_nonce ~= manifest.arm_nonce then
        error("activation nonce does not match callback capsule", 2)
    end
    local identity_manifest = rawget(
        options.capsule.binding_manifest,
        "identity_manifest"
    )
    local attested_limits = type(identity_manifest) == "table"
        and rawget(identity_manifest, "limits") or nil
    if type(attested_limits) ~= "table" then
        error("callback capsule binding limits are unavailable", 2)
    end
    local enumeration_limits = {
        max_roots = rawget(attested_limits, "max_roots"),
        max_depth = rawget(attested_limits, "max_depth"),
        max_functions = rawget(attested_limits, "max_functions"),
        max_text_bytes = rawget(attested_limits, "max_text_bytes"),
    }
    local document, live_bindings, binding_error =
        options.callback_bindings_module.enumerate(
            options.globals,
            options.callback_manifest_module,
            enumeration_limits
        )
    if type(document) ~= "table" or type(live_bindings) ~= "table" then
        error(binding_error or "callback binding enumeration failed", 2)
    end
    if not deep_equal(document, options.capsule.binding_manifest) then
        error("live callback bindings do not match capsule", 2)
    end
    local self = setmetatable({}, Host)
    self.condition = options.condition
    self.activation_nonce = options.activation_nonce
    self.capsule_sha256 = options.capsule_sha256
    self.capsule = options.capsule
    self.controller_module = options.controller_module
    self.live_state_provider = options.live_state_provider
    self.raw_writer = options.raw_writer
    self.result_writer = options.result_writer
    self.globals = options.globals
    self.binding_document = document
    self.live_bindings = live_bindings
    self.manifest = manifest
    self.controller = nil
    self.runtime_snapshot = nil
    self.runtime_before = nil
    self.state = "waiting"
    self.last_error = nil
    self.in_step = false
    self.raw_written = false
    self.raw_event_count = 0
    self.attempted_calls = 0
    self.serialization_errors = 0
    self.result_published = false
    self.step = Host.step
    self.status = Host.status
    self.abort = Host.abort
    return self
end

return M
