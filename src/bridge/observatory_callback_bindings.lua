-- Inert callback-slot enumerator for Observatory experiments.
--
-- This module never calls or wraps a candidate callback.  enumerate() first
-- asks the separately reviewed identity-manifest module for the exact enemy
-- roots and function IDs, then resolves the raw table slot that supplies each
-- method.  Shared inherited slots receive one deterministic slot ID so a later
-- controller can install exactly one reversible wrapper per live table field.

local M = {}

M.VERSION = "observatory-callback-bindings/1"
M.SCHEMA_VERSION = 1
M.MAX_SLOTS = 512

local METHODS = {
    "GetTargetArea",
    "GetTargetScore",
    "GetSkillEffect",
    "ScorePositioning",
}

local function nonnegative_integer(value)
    return type(value) == "number"
        and value >= 0
        and value == math.floor(value)
end

local function exact_array(value, length)
    if type(value) ~= "table" or #value ~= length then return false end
    for index = 1, length do
        if rawget(value, index) == nil then return false end
    end
    for key, _ in pairs(value) do
        if not nonnegative_integer(key) or key < 1 or key > length then
            return false
        end
    end
    return true
end

local function resolve_slot(object, method, max_depth)
    local current = object
    local seen = {}
    local depth = 0
    while true do
        if seen[current] then return nil, nil, "index_cycle", depth end
        seen[current] = true
        local value = rawget(current, method)
        if value ~= nil then
            if type(value) == "function" then
                return current, value, "function", depth
            end
            return nil, nil, "non_function", depth
        end
        local metatable = getmetatable(current)
        if metatable == nil then return nil, nil, "missing", depth end
        if type(metatable) ~= "table" then
            return nil, nil, "protected_metatable", depth
        end
        local index = rawget(metatable, "__index")
        if index == nil then return nil, nil, "missing", depth end
        if type(index) == "function" then
            return nil, nil, "function_index", depth
        end
        if type(index) ~= "table" then
            return nil, nil, "invalid_index", depth
        end
        if seen[index] then return nil, nil, "index_cycle", depth end
        if depth >= max_depth then
            return nil, nil, "depth_exceeded", depth
        end
        current = index
        depth = depth + 1
    end
end

local function method_by_name(root)
    local result = {}
    if type(root) ~= "table" or not exact_array(root.methods, #METHODS) then
        return nil
    end
    for index, expected_method in ipairs(METHODS) do
        local method = root.methods[index]
        if type(method) ~= "table" or method.method ~= expected_method then
            return nil
        end
        result[expected_method] = method
    end
    return result
end

function M.enumerate(globals, manifest_module, options)
    if type(globals) ~= "table"
        or type(manifest_module) ~= "table"
        or type(manifest_module.discover_enemy_skill_roots) ~= "function"
        or type(manifest_module.enumerate) ~= "function" then
        return nil, nil, "invalid callback binding inputs"
    end
    local roots, discovery_error =
        manifest_module.discover_enemy_skill_roots(globals)
    if not roots then return nil, nil, discovery_error end
    local identity, identity_error = manifest_module.enumerate(roots, options)
    if not identity then return nil, nil, identity_error end
    if type(identity.limits) ~= "table"
        or not nonnegative_integer(identity.limits.max_depth)
        or not exact_array(identity.roots, #roots)
        or #identity.roots ~= #roots then
        return nil, nil, "invalid identity manifest"
    end

    local slot_ids = {}
    local slot_entries = {}
    local live_bindings = {}
    local output_roots = {}

    for root_index, root in ipairs(roots) do
        local identity_root = identity.roots[root_index]
        if type(identity_root) ~= "table"
            or identity_root.root_id ~= root.root_id then
            return nil, nil, "identity root order mismatch"
        end
        local identity_methods = method_by_name(identity_root)
        if not identity_methods then
            return nil, nil, "invalid identity methods"
        end
        local output_methods = {}
        for method_index, method in ipairs(METHODS) do
            local identity_method = identity_methods[method]
            local holder, callback, resolution, depth = resolve_slot(
                root.object, method, identity.limits.max_depth
            )
            local slot_id = ""
            if identity_method.function_id ~= "" then
                if resolution ~= "function"
                    or type(holder) ~= "table"
                    or type(callback) ~= "function"
                    or depth ~= identity_method.resolution_depth then
                    return nil, nil, "identity slot resolution mismatch"
                end
                local by_method = slot_ids[holder]
                if by_method == nil then
                    by_method = {}
                    slot_ids[holder] = by_method
                end
                local slot_index = by_method[method]
                if slot_index == nil then
                    if #slot_entries >= M.MAX_SLOTS then
                        return nil, nil, "callback slot cap exceeded"
                    end
                    slot_index = #slot_entries + 1
                    by_method[method] = slot_index
                    slot_id = string.format("slot-%04d", slot_index)
                    slot_entries[slot_index] = {
                        slot_id = slot_id,
                        method = method,
                        function_id = identity_method.function_id,
                        root_ids = {},
                    }
                    live_bindings[slot_index] = {
                        slot_id = slot_id,
                        holder = holder,
                        key = method,
                        original = callback,
                        function_id = identity_method.function_id,
                        method = method,
                        -- Live-only identity used by the later callback
                        -- controller.  These tables are deliberately absent
                        -- from the serialized document: they let a wrapper
                        -- distinguish which concrete skill object inherited a
                        -- shared defining slot without scanning _G or calling
                        -- any candidate callback.
                        root_ids = {},
                        root_objects = {},
                    }
                else
                    local slot = slot_entries[slot_index]
                    local live = live_bindings[slot_index]
                    slot_id = slot.slot_id
                    if slot.function_id ~= identity_method.function_id
                        or live.original ~= callback then
                        return nil, nil, "shared callback slot identity mismatch"
                    end
                end
                local slot = slot_entries[slot_index]
                local live = live_bindings[slot_index]
                slot.root_ids[#slot.root_ids + 1] = root.root_id
                live.root_ids[#live.root_ids + 1] = root.root_id
                live.root_objects[#live.root_objects + 1] = root.object
            else
                if resolution == "function" then
                    return nil, nil, "unpublished callback function"
                end
                if depth ~= identity_method.resolution_depth then
                    return nil, nil, "unresolved callback depth mismatch"
                end
            end
            output_methods[method_index] = {
                method = method,
                status = identity_method.status,
                resolution_depth = identity_method.resolution_depth,
                function_id = identity_method.function_id,
                slot_id = slot_id,
            }
        end
        output_roots[root_index] = {
            root_id = root.root_id,
            methods = output_methods,
        }
    end

    return {
        schema_version = M.SCHEMA_VERSION,
        runtime_version = M.VERSION,
        method_order = {
            METHODS[1], METHODS[2], METHODS[3], METHODS[4],
        },
        identity_manifest = identity,
        roots = output_roots,
        slots = slot_entries,
        summary = {
            root_count = #output_roots,
            method_count = #output_roots * #METHODS,
            function_count = identity.summary.function_count,
            slot_count = #slot_entries,
        },
    }, live_bindings
end

return M
