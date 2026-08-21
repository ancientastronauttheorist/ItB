-- Inert runtime callback-identity enumerator for Observatory experiments.
--
-- Loading this module performs no I/O, global mutation, target lookup, or
-- callback invocation.  enumerate() inspects only the exact roots supplied by
-- its caller.  Resolution uses rawget plus a bounded table-valued __index
-- chain; function-valued or otherwise dynamic lookup is reported unresolved
-- and is never invoked.

local M = {}

M.VERSION = "observatory-callback-manifest/1"
M.SCHEMA_VERSION = 1

local METHODS = {
    "GetTargetArea",
    "GetTargetScore",
    "GetSkillEffect",
    "ScorePositioning",
}

local METHOD_SET = {}
for _, method in ipairs(METHODS) do METHOD_SET[method] = true end

local STATUSES = {
    "resolved",
    "c_function",
    "debug_unavailable",
    "missing",
    "function_index",
    "index_cycle",
    "depth_exceeded",
    "invalid_index",
    "protected_metatable",
    "non_function",
    "function_cap",
}

local DEFAULT_LIMITS = {
    max_roots = 64,
    max_depth = 16,
    max_functions = 256,
    max_text_bytes = 512,
}

local HARD_LIMITS = {
    max_roots = 256,
    max_depth = 32,
    max_functions = 1024,
    max_text_bytes = 1024,
}

local DISCOVERY_LIMITS = {
    max_pawns = 512,
    max_skill_slots = 16,
    max_skills = 255,
    max_depth = 16,
    max_symbol_bytes = 96,
}

local ROOT_FIELDS = {
    root_id = true,
    object = true,
    expected = true,
}

local LIMIT_FIELDS = {
    max_roots = true,
    max_depth = true,
    max_functions = true,
    max_text_bytes = true,
}

local debug_getinfo =
    type(debug) == "table" and type(debug.getinfo) == "function"
        and debug.getinfo or nil

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

local function nonnegative_integer(value)
    return type(value) == "number"
        and value >= 0
        and value == math.floor(value)
end

local function positive_integer(value)
    return nonnegative_integer(value) and value > 0
end

local function array_shape(value, length)
    if type(value) ~= "table" then return false end
    for index = 1, length do
        if rawget(value, index) == nil then return false end
    end
    for key, _ in pairs(value) do
        if not nonnegative_integer(key)
            or key < 1
            or key > length then
            return false
        end
    end
    return true
end

local function valid_root_id(value)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= 128
        and string.match(value, "^[A-Za-z0-9][A-Za-z0-9._:-]*$") ~= nil
end

local function valid_symbol(value)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= DISCOVERY_LIMITS.max_symbol_bytes
        and string.match(value, "^[A-Za-z][A-Za-z0-9_]*$") ~= nil
end

local function validate_limits(options)
    if options == nil then
        return {
            max_roots = DEFAULT_LIMITS.max_roots,
            max_depth = DEFAULT_LIMITS.max_depth,
            max_functions = DEFAULT_LIMITS.max_functions,
            max_text_bytes = DEFAULT_LIMITS.max_text_bytes,
        }
    end
    if not exact_fields(options, LIMIT_FIELDS) then
        return nil, "invalid limits"
    end
    local copied = {}
    for field, maximum in pairs(HARD_LIMITS) do
        local value = options[field]
        if not positive_integer(value) or value > maximum then
            return nil, "invalid limit " .. field
        end
        copied[field] = value
    end
    return copied
end

local function validate_roots(roots, limits)
    if type(roots) ~= "table" then return nil, "invalid roots" end
    local count = #roots
    if count < 1 or count > limits.max_roots
        or not array_shape(roots, count) then
        return nil, "invalid roots"
    end
    local seen_ids = {}
    local copied = {}
    for index = 1, count do
        local entry = rawget(roots, index)
        if not exact_fields(entry, ROOT_FIELDS)
            or not valid_root_id(entry.root_id)
            or seen_ids[entry.root_id]
            or type(entry.object) ~= "table"
            or type(entry.expected) ~= "table" then
            return nil, "invalid root"
        end
        for key, value in pairs(entry.expected) do
            if not METHOD_SET[key] or type(value) ~= "function" then
                return nil, "invalid expected callback"
            end
        end
        seen_ids[entry.root_id] = true
        copied[index] = entry
    end
    return copied
end

local function bounded_text(value, limit)
    if type(value) ~= "string" then value = "" end
    if string.len(value) <= limit then return value, false end
    return string.sub(value, 1, limit), true
end

local function safe_line(value)
    if type(value) ~= "number"
        or value ~= math.floor(value)
        or value < -1 then
        return -1
    end
    return value
end

local function inspect_function(callback, limit)
    if debug_getinfo == nil then
        return {
            debug_status = "unavailable",
            source = "",
            source_truncated = false,
            short_src = "",
            short_src_truncated = false,
            linedefined = -1,
            lastlinedefined = -1,
            what = "",
            what_truncated = false,
            name = "",
            name_truncated = false,
            namewhat = "",
            namewhat_truncated = false,
        }
    end
    local ok, info = pcall(debug_getinfo, callback, "nS")
    if not ok or type(info) ~= "table" then
        return {
            debug_status = "unavailable",
            source = "",
            source_truncated = false,
            short_src = "",
            short_src_truncated = false,
            linedefined = -1,
            lastlinedefined = -1,
            what = "",
            what_truncated = false,
            name = "",
            name_truncated = false,
            namewhat = "",
            namewhat_truncated = false,
        }
    end
    local source, source_truncated = bounded_text(info.source, limit)
    local short_src, short_src_truncated = bounded_text(info.short_src, limit)
    local what, what_truncated = bounded_text(info.what, limit)
    local name, name_truncated = bounded_text(info.name, limit)
    local namewhat, namewhat_truncated = bounded_text(info.namewhat, limit)
    return {
        debug_status = "available",
        source = source,
        source_truncated = source_truncated,
        short_src = short_src,
        short_src_truncated = short_src_truncated,
        linedefined = safe_line(info.linedefined),
        lastlinedefined = safe_line(info.lastlinedefined),
        what = what,
        what_truncated = what_truncated,
        name = name,
        name_truncated = name_truncated,
        namewhat = namewhat,
        namewhat_truncated = namewhat_truncated,
    }
end

local function resolve_raw_value(object, field, max_depth)
    local current = object
    local seen = {}
    local depth = 0
    while true do
        if seen[current] then
            return nil, "index_cycle", depth
        end
        seen[current] = true
        local value = rawget(current, field)
        if value ~= nil then
            return value, "value", depth
        end
        local metatable = getmetatable(current)
        if metatable == nil then return nil, "missing", depth end
        if type(metatable) ~= "table" then
            return nil, "protected_metatable", depth
        end
        local index = rawget(metatable, "__index")
        if index == nil then return nil, "missing", depth end
        if type(index) == "function" then
            return nil, "function_index", depth
        end
        if type(index) ~= "table" then
            return nil, "invalid_index", depth
        end
        if seen[index] then
            return nil, "index_cycle", depth
        end
        if depth >= max_depth then
            return nil, "depth_exceeded", depth
        end
        current = index
        depth = depth + 1
    end
end


local function resolve_raw(object, method, max_depth)
    local value, resolution, depth = resolve_raw_value(
        object, method, max_depth
    )
    if resolution ~= "value" then return nil, resolution, depth end
    if type(value) == "function" then return value, "function", depth end
    return nil, "non_function", depth
end


local function discovery_value(object, field, label)
    local value, status = resolve_raw_value(
        object, field, DISCOVERY_LIMITS.max_depth
    )
    if status ~= "value" then
        return nil, label .. " " .. field .. " is " .. status
    end
    return value
end


function M.discover_enemy_skill_roots(globals)
    if type(globals) ~= "table" then
        return nil, "invalid globals"
    end
    local team_enemy = rawget(globals, "TEAM_ENEMY")
    local pawn_list = rawget(globals, "PawnList")
    local score_positioning = rawget(globals, "ScorePositioning")
    if not nonnegative_integer(team_enemy) then
        return nil, "TEAM_ENEMY is unavailable"
    end
    if type(pawn_list) ~= "table" then
        return nil, "PawnList is unavailable"
    end
    if type(score_positioning) ~= "function" then
        return nil, "ScorePositioning is unavailable"
    end

    local pawn_count = #pawn_list
    if pawn_count < 1
        or pawn_count > DISCOVERY_LIMITS.max_pawns
        or not array_shape(pawn_list, pawn_count) then
        return nil, "PawnList violates its cap or shape"
    end

    local skills = {}
    for pawn_index = 1, pawn_count do
        local pawn_name = rawget(pawn_list, pawn_index)
        if not valid_symbol(pawn_name) then
            return nil, "invalid PawnList symbol"
        end
        local pawn = rawget(globals, pawn_name)
        if type(pawn) ~= "table" then
            return nil, "pawn global is not a table: " .. pawn_name
        end
        local default_team, team_error = discovery_value(
            pawn, "DefaultTeam", "pawn " .. pawn_name
        )
        if team_error then return nil, team_error end
        if not nonnegative_integer(default_team) then
            return nil, "pawn DefaultTeam is invalid: " .. pawn_name
        end
        if default_team == team_enemy then
            local skill_list, skills_error = discovery_value(
                pawn, "SkillList", "pawn " .. pawn_name
            )
            if skills_error then return nil, skills_error end
            if type(skill_list) ~= "table" then
                return nil, "pawn SkillList is not a table: " .. pawn_name
            end
            local skill_count = #skill_list
            if skill_count > DISCOVERY_LIMITS.max_skill_slots
                or not array_shape(skill_list, skill_count) then
                return nil, "pawn SkillList violates its cap or shape: "
                    .. pawn_name
            end
            for skill_index = 1, skill_count do
                local skill_id = rawget(skill_list, skill_index)
                if not valid_symbol(skill_id) then
                    return nil, "invalid enemy skill symbol"
                end
                local skill = rawget(globals, skill_id)
                if skill == nil then
                    -- PawnList contains at least one shipped enemy whose
                    -- SkillList names a commented-out/missing global
                    -- (Garden_Atk in build 13725832). Preserve that exact
                    -- symbolic root as an empty callback surface so every
                    -- method is reported `missing`; never silently omit it or
                    -- invent/call a replacement.
                    skill = {}
                elseif type(skill) ~= "table" then
                    return nil, "enemy skill global is not a table: "
                        .. skill_id
                end
                skills[skill_id] = skill
            end
        end
    end

    local skill_ids = {}
    for skill_id, _ in pairs(skills) do
        skill_ids[#skill_ids + 1] = skill_id
    end
    table.sort(skill_ids)
    if #skill_ids > DISCOVERY_LIMITS.max_skills then
        return nil, "enemy skill roots exceed their cap"
    end

    local roots = {}
    for index, skill_id in ipairs(skill_ids) do
        roots[index] = {
            root_id = "enemy.skill." .. skill_id,
            object = skills[skill_id],
            expected = {},
        }
    end
    roots[#roots + 1] = {
        root_id = "global.ScorePositioning",
        object = {ScorePositioning = score_positioning},
        expected = {},
    }
    return roots
end

local function new_catalog(limits)
    local state = {
        ids = {},
        entries = {},
        limits = limits,
    }
    function state:register(callback)
        local existing = self.ids[callback]
        if existing ~= nil then return existing, false end
        if #self.entries >= self.limits.max_functions then
            return nil, true
        end
        local function_id = string.format("fn-%04d", #self.entries + 1)
        self.ids[callback] = function_id
        local metadata = inspect_function(
            callback, self.limits.max_text_bytes
        )
        metadata.function_id = function_id
        self.entries[#self.entries + 1] = metadata
        return function_id, false
    end
    return state
end

function M.enumerate(roots, options)
    local limits, limits_error = validate_limits(options)
    if not limits then return nil, limits_error end
    local supplied, roots_error = validate_roots(roots, limits)
    if not supplied then return nil, roots_error end

    local catalog = new_catalog(limits)
    local status_counts = {}
    for _, status in ipairs(STATUSES) do status_counts[status] = 0 end
    local output_roots = {}
    local replaced_count = 0

    for root_index, root in ipairs(supplied) do
        local methods = {}
        for method_index, method in ipairs(METHODS) do
            local callback, resolution, depth = resolve_raw(
                root.object, method, limits.max_depth
            )
            local function_id = ""
            local status = resolution
            if callback ~= nil then
                local truncated
                function_id, truncated = catalog:register(callback)
                if truncated then
                    function_id = ""
                    status = "function_cap"
                else
                    local metadata = catalog.entries[
                        tonumber(string.sub(function_id, 4))
                    ]
                    if metadata.debug_status == "unavailable" then
                        status = "debug_unavailable"
                    elseif metadata.what == "C" then
                        status = "c_function"
                    else
                        status = "resolved"
                    end
                end
            end

            local expected = rawget(root.expected, method)
            local expected_function_id = ""
            local expected_truncated = false
            local replaced = false
            if expected ~= nil then
                expected_function_id, expected_truncated =
                    catalog:register(expected)
                if expected_function_id == nil then
                    expected_function_id = ""
                end
                replaced = callback ~= expected
            end
            if replaced then replaced_count = replaced_count + 1 end
            status_counts[status] = status_counts[status] + 1
            methods[method_index] = {
                method = method,
                status = status,
                replaced = replaced,
                resolution_depth = depth,
                function_id = function_id,
                expected_function_id = expected_function_id,
                expected_truncated = expected_truncated,
            }
        end
        output_roots[root_index] = {
            root_id = root.root_id,
            methods = methods,
        }
    end

    return {
        schema_version = M.SCHEMA_VERSION,
        runtime_version = M.VERSION,
        method_order = {
            METHODS[1], METHODS[2], METHODS[3], METHODS[4],
        },
        limits = limits,
        roots = output_roots,
        functions = catalog.entries,
        summary = {
            root_count = #output_roots,
            method_count = #output_roots * #METHODS,
            function_count = #catalog.entries,
            replaced_count = replaced_count,
            status_counts = status_counts,
        },
    }
end

return M
