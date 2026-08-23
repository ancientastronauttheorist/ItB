--------------------------------------------------------------------
-- ITB Bot Bridge — Production
-- Runs inside Into the Breach via modloader.lua injection.
-- Communicates with external Python bot via file-based IPC.
--
-- macOS default: /tmp/itb_*
-- Windows default: Documents/My Games/Into The Breach/itb_bridge/itb_*
--------------------------------------------------------------------

local function normalize_path(path)
    return (path:gsub("\\", "/"))
end

local function is_windows()
    return package.config:sub(1, 1) == "\\"
end

local function default_save_root()
    local override = os.getenv("ITB_SAVE_DIR")
    if override and override ~= "" then return normalize_path(override) end
    if is_windows() then
        local user = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
        return normalize_path(user) .. "/Documents/My Games/Into The Breach"
    end
    local home = os.getenv("HOME") or "."
    return normalize_path(home) .. "/Library/Application Support/IntoTheBreach"
end

local function default_bridge_dir()
    local override = os.getenv("ITB_BRIDGE_DIR")
    if override and override ~= "" then return normalize_path(override) end
    if is_windows() then
        return default_save_root() .. "/itb_bridge"
    end
    return "/tmp"
end

local BRIDGE_DIR = default_bridge_dir()
local SAVE_ROOT = default_save_root()

local STATE_FILE = BRIDGE_DIR .. "/itb_state.json"
local STATE_TMP  = BRIDGE_DIR .. "/itb_state.json.tmp"
local CMD_FILE   = BRIDGE_DIR .. "/itb_cmd.txt"
local ACK_FILE   = BRIDGE_DIR .. "/itb_ack.txt"
local ACK_TMP    = BRIDGE_DIR .. "/itb_ack.tmp"
local LOG_FILE   = BRIDGE_DIR .. "/itb_bridge.log"
local HEARTBEAT_FILE = BRIDGE_DIR .. "/itb_bridge_heartbeat"
local CALLBACK_MANIFEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_callback_manifest.json"
local CALLBACK_MANIFEST_TMP =
    BRIDGE_DIR .. "/itb_observatory_callback_manifest.json.tmp"
local CALLBACK_MANIFEST_REQUEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_callback_manifest.request"
local CALLBACK_MANIFEST_REQUEST_TOKEN =
    "observatory-callback-manifest-request/1"
local CALLBACK_BINDINGS_FILE =
    BRIDGE_DIR .. "/itb_observatory_callback_bindings.json"
local CALLBACK_BINDINGS_TMP =
    BRIDGE_DIR .. "/itb_observatory_callback_bindings.json.tmp"
local CALLBACK_BINDINGS_REQUEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_callback_bindings.request"
local CALLBACK_BINDINGS_REQUEST_TOKEN =
    "observatory-callback-bindings-request/1"
local RNG_TRIAL_REQUEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_rng_trial.request"
local RNG_TRIAL_REQUEST_TOKEN =
    "observatory-rng-trial-request/1"
local CALLBACK_TRIAL_REQUEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_callback_trial.request"
local CALLBACK_TRIAL_REQUEST_TOKEN =
    "observatory-callback-trial-request/1"
local NATIVE_CONTINUE_REQUEST_FILE =
    BRIDGE_DIR .. "/itb_observatory_native_continue.request"
local NATIVE_CONTINUE_REQUEST_TOKEN =
    "observatory-native-continue-request/1"
local NATIVE_RNG_SNAPSHOT_FILE =
    BRIDGE_DIR .. "/itb_observatory_native_rng_snapshot.json"
local NATIVE_RNG_SNAPSHOT_TMP =
    BRIDGE_DIR .. "/itb_observatory_native_rng_snapshot.json.tmp"
local SPAWN_SPAN_LEDGER_FILE =
    BRIDGE_DIR .. "/itb_observatory_spawn_span_ledger.json"
local SPAWN_SPAN_LEDGER_TMP =
    BRIDGE_DIR .. "/itb_observatory_spawn_span_ledger.json.tmp"
local SPAWN_SPAN_CONTROLLER_SHA256 =
    "4923ee3b08c802824f17963dc625015d2c91e6e467149b72bba218c49830935d"
local SPAWN_REPLAY_LEDGER_FILE =
    BRIDGE_DIR .. "/itb_observatory_spawn_replay_ledger.json"
local SPAWN_REPLAY_LEDGER_TMP =
    BRIDGE_DIR .. "/itb_observatory_spawn_replay_ledger.json.tmp"
local SPAWN_REPLAY_CONTROLLER_SHA256 =
    "c411c5e1d84cfae079b6b5f6b69b9bc022d0f0a9a87af5bf877ca1c1badb699f"
local SELECTED_QUEUE_SNAPSHOT_FILE =
    BRIDGE_DIR .. "/itb_observatory_selected_queue_snapshot.json"
local SELECTED_QUEUE_SNAPSHOT_TMP =
    BRIDGE_DIR .. "/itb_observatory_selected_queue_snapshot.json.tmp"
local SELECTED_QUEUE_OBSERVER_SHA256 =
    "2cf202cc2e58c33651864ed8939b8491cc082048c300d82b63ff3cfbd76a5676"
local SELECTED_QUEUE_OBSERVER_EXPORT =
    "luaopen_itb_observatory_selected_queue_hw_observer"
local SELECTED_QUEUE_HW_PLAN_SHA256 =
    "f99e1ba7b130799f27f6cc4e7a12aa4198bccb624ce994ae6a3fc063c30511b6"
local SPAWN_COORDINATE_SNAPSHOT_FILE =
    BRIDGE_DIR .. "/itb_observatory_spawn_coordinate_snapshot.json"
local SPAWN_COORDINATE_SNAPSHOT_TMP =
    BRIDGE_DIR .. "/itb_observatory_spawn_coordinate_snapshot.json.tmp"
local SPAWN_COORDINATE_OBSERVER_SHA256 =
    "e9f7392eb6d529be306c085271414d9e1fe17c2de03cf4266a692af6d1af11a1"
local SPAWN_COORDINATE_OBSERVER_EXPORT =
    "luaopen_itb_observatory_spawn_coordinate_hw_observer"
local SPAWN_COORDINATE_HW_PLAN_SHA256 =
    "6c22aa5cb62552afd7f08d9e942a82cbceb620aab3b1853f004c98534ea74e09"
local NATIVE_RNG_OBSERVER_SHA256 =
    "8ef711798bd9d37fbff5e75eaac17c27189f9c25aa6f11122cb27068b5e2184c"
local NATIVE_RNG_OBSERVER_EXPORT =
    "luaopen_itb_observatory_rng_core_observer"
local NATIVE_RNG_OBSERVER_BUILD_ID = "13725832"
local NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256 =
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
local NATIVE_RNG_OBSERVER_CORE_RVA = "0x00387f16"
local NATIVE_RNG_OBSERVER_CORE_SHA256 =
    "3d7a67186e320b23a31d2ca6f9281211b373b60d44f35531cf4369da45cf0179"
local NATIVE_RNG_OBSERVER_RETURN_MAP_SHA256 =
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
local NATIVE_RNG_OBSERVER_HOOK_PLAN_SHA256 =
    "a3d09bbc95ed32c1d8fc4c4155f6b09cabea69a90c361bbb966e2de69023f378"
local NATIVE_RNG_OBSERVER_RESTORE_SHA256 =
    "d7ad5662a8ba8cdce081f56705ea8302ad425e5f7dbf6830ba4056f99408b73d"
local NATIVE_RNG_FIXED_SEED = 324508639
local NATIVE_RNG_SEED_HELPER_SHA256 =
    "bd6501c701b8c5f21dbaec309573ab654c7cf01a5705423e2c0ee554dd0e2787"
local NATIVE_RNG_SEED_REGION_SHA256 =
    "67b19fe39627674ef04d07bd86e989a39ce744be2e93f9265c16e2aeb928cf9d"
local NATIVE_GAMEFLOW_HELPER_SHA256 =
    "e0c6766f6d2150616fc10224fa2d1d53c051a7171fd2e107267f1383a4fcc91a"

local _observatory_native_rng_module = nil
local _observatory_native_rng_capture_id = nil
local _observatory_spawn_span_controller = nil
local _observatory_spawn_replay_controller = nil
local _observatory_native_gameflow = nil
local _observatory_selected_queue_module = nil
local _observatory_spawn_coordinate_module = nil
local _observatory_spawn_coordinate_condition = nil
local _observatory_spawn_coordinate_capture_id = nil
local _observatory_spawn_coordinate_restored = false

if is_windows() then
    os.execute('mkdir "' .. BRIDGE_DIR .. '" >NUL 2>NUL')
else
    os.execute('mkdir -p "' .. BRIDGE_DIR .. '"')
end

local TERRAIN_NAMES = {}

local function add_terrain_name(global_name, fallback_id, name)
    local id = _G[global_name]
    if type(id) ~= "number" then id = fallback_id end
    if type(id) == "number" then TERRAIN_NAMES[id] = name end
end

add_terrain_name("TERRAIN_ROAD", 0, "ground")
add_terrain_name("TERRAIN_BUILDING", 1, "building")
add_terrain_name("TERRAIN_RUBBLE", 2, "rubble")
add_terrain_name("TERRAIN_WATER", 3, "water")
add_terrain_name("TERRAIN_MOUNTAIN", 4, "mountain")
add_terrain_name("TERRAIN_ICE", 5, "ice")
add_terrain_name("TERRAIN_FOREST", 6, "forest")
add_terrain_name("TERRAIN_SAND", 7, "sand")
add_terrain_name("TERRAIN_HOLE", 9, "chasm")
add_terrain_name("TERRAIN_ACID", 10, "acid")
add_terrain_name("TERRAIN_LAVA", nil, "lava")

local _poll_interval = 0.2  -- seconds between command polls
local _last_poll = 0

--------------------------------------------------------------------
-- Minimal JSON encoder (no external deps)
--------------------------------------------------------------------
local function json_encode(val)
    if val == nil then return "null" end
    local t = type(val)
    if t == "boolean" then return val and "true" or "false" end
    if t == "number" then return tostring(val) end
    if t == "string" then
        return '"' .. val:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n') .. '"'
    end
    if t == "table" then
        -- Check if array (sequential integer keys starting at 1)
        if #val > 0 or next(val) == nil then
            local parts = {}
            for i, v in ipairs(val) do
                parts[i] = json_encode(v)
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, v in pairs(val) do
                parts[#parts+1] = json_encode(tostring(k)) .. ":" .. json_encode(v)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return '"<' .. t .. '>"'
end

--------------------------------------------------------------------
-- File helpers
--------------------------------------------------------------------
local function write_atomic(path, tmp_path, content)
    local f = io.open(tmp_path, "w")
    if f then
        f:write(content)
        f:close()
        local ok, _err = os.rename(tmp_path, path)
        if not ok and is_windows() then
            os.remove(path)
            os.rename(tmp_path, path)
        end
    end
end

local function log_bridge(msg)
    local f = io.open(LOG_FILE, "a")
    if f then
        f:write(os.date() .. " | " .. msg .. "\n")
        f:close()
    end
end

-- Read all save-file-derived data in a single I/O pass:
-- grid power, queued shots, and conveyor belts.
-- Reads saveData.lua (preferred) or undoSave.lua (fallback).
--------------------------------------------------------------------
local function strip_upgrade_suffix_lua(weapon_id)
    if type(weapon_id) ~= "string" then return "", "" end
    for _, suffix in ipairs({"_AB", "_A", "_B"}) do
        local n = string.len(suffix)
        if string.sub(weapon_id, -n) == suffix then
            return string.sub(weapon_id, 1, string.len(weapon_id) - n), suffix
        end
    end
    return weapon_id, ""
end

local function save_mod_group_fully_powered(block, key)
    local blob = block:match('%["' .. key .. '"%]%s*=%s*{(.-)}')
    if not blob then return false end
    local saw_value = false
    for value in blob:gmatch("%-?%d+") do
        saw_value = true
        if (tonumber(value) or 0) <= 0 then
            return false
        end
    end
    return saw_value
end

local function overlay_current_weapon_from_pawn_mods(result, uid, slot, base_weapon, mod1_key, mod2_key, block)
    if type(uid) ~= "number" or uid < 0 or uid > 2 then return end
    if type(base_weapon) ~= "string" or base_weapon == "" then return end

    local powered_a = save_mod_group_fully_powered(block, mod1_key)
    local powered_b = save_mod_group_fully_powered(block, mod2_key)
    local candidates = {}
    if powered_a and powered_b then candidates[#candidates + 1] = base_weapon .. "_AB" end
    if powered_a then candidates[#candidates + 1] = base_weapon .. "_A" end
    if powered_b then candidates[#candidates + 1] = base_weapon .. "_B" end

    local idx = uid * 2 + slot + 1
    local current = result.current_weapons[idx] or ""
    local current_base = strip_upgrade_suffix_lua(current)
    for _, upgraded in ipairs(candidates) do
        if _G[upgraded] ~= nil then
            local expected_base = strip_upgrade_suffix_lua(upgraded)
            if current == "" or current == expected_base or current == upgraded or current_base == expected_base then
                result.current_weapons[idx] = upgraded
                return
            end
        end
    end
end

local function _read_save_data()
    local result = {
        network = nil,
        networkMax = nil,
        difficulty = nil,     -- GameData.difficulty (0=Easy, 1=Normal, 2=Hard, 3=Unfair)
        queued_shots = {},
        queued_origins = {},  -- [pawn_id] = {x, y} from piOrigin (attack queue source)
        queued_targets = {},  -- [pawn_id] = {x, y} from piTarget (leap/melee landing tile)
        queued_skills = {},   -- [pawn_id] = iQueuedSkill (>=0 when an attack is actually queued)
        conveyor_belts = {},
        pilots = {},  -- [pawn_id] = {id=..., level=..., skill1=..., skill2=...}
        pawn_max_health = {},  -- [pawn_id] = max_health
        infected = {},  -- [pawn_id] = bInfected (Vek Mites objective state)
        master_seed = nil,    -- GameData.seed — run-lifetime master RNG seed
        mission_seeds = {},   -- [region_key] = aiSeed — per-mission per-turn PRNG snapshot
        current_weapons = {}, -- GameData.current.weapons, 1-indexed loadout slots
        pawn_offsets = {},    -- [pawn_id] = raw save offset (diagnostic only)
    }
    local base = SAVE_ROOT .. "/profile_Alpha/"
    local sf = io.open(base .. "saveData.lua", "r")
    if not sf then
        sf = io.open(base .. "undoSave.lua", "r")
    end
    if not sf then return result end
    local content = sf:read("*a")
    sf:close()

    -- Grid power (in first line of file, very cheap pattern match)
    local net = content:match('%["network"%]%s*=%s*(%d+)')
    if net then result.network = tonumber(net) end
    local netMax = content:match('%["networkMax"%]%s*=%s*(%d+)')
    if netMax then result.networkMax = tonumber(netMax) end

    -- In-game difficulty: 0=Easy, 1=Normal, 2=Hard, 3=Unfair. Authoritative
    -- live value (the Python session.difficulty drifts after Timeline Lost
    -- continuations). Allow negative just in case the game ever stores it
    -- as -1 for "uninitialized".
    local diff = content:match('%["difficulty"%]%s*=%s*(%-?%d+)')
    if diff then result.difficulty = tonumber(diff) end

    -- RNG seeds — for grid-defense resist prediction probe.
    -- `seed` is the run-lifetime master seed (appears once, top-level GameData).
    -- `aiSeed` is per-mission and advances each turn — it's the PRNG state
    -- snapshot the game uses for AI / resist rolls starting from the next
    -- enemy phase. Recording it per turn lets us replay forward locally and
    -- fish which telegraphed attacks the game has pre-rolled as resists.
    local ms = content:match('%["seed"%]%s*=%s*(%-?%d+)')
    if ms then result.master_seed = tonumber(ms) end
    local weapons_blob = content:match('%["weapons"%]%s*=%s*{(.-)}')
    if weapons_blob then
        for w in weapons_blob:gmatch('"([^"]*)"') do
            result.current_weapons[#result.current_weapons + 1] = w
        end
    end
    for region_key, region_block in content:gmatch('%["(region%d+)"%]%s*=%s*(%b{})') do
        local ais = region_block:match('%["aiSeed"%]%s*=%s*(%-?%d+)')
        if ais then
            local sMission = region_block:match('%["sMission"%]%s*=%s*"([^"]+)"')
            local iTurn = region_block:match('%["iCurrentTurn"%]%s*=%s*(%-?%d+)')
            local iState = region_block:match('%["iState"%]%s*=%s*(%-?%d+)')
            result.mission_seeds[region_key] = {
                ai_seed = tonumber(ais),
                mission = sMission,
                turn = tonumber(iTurn),
                state = tonumber(iState),
            }
        end
    end

    -- Queued shots + pilot data: per-pawn, in a single pass.
    -- Save has blocks like `["pawn3"] = { ["id"] = 3, ["piQueuedShot"] =
    -- Point(5,0), ["pilot"] = { ["id"] = "Pilot_Original", ["level"] = 2,
    -- ["skill1"] = 0, ["skill2"] = 2, ... }, ... }`.
    for block in content:gmatch('%["pawn%d+"%]%s*=%s*(%b{})') do
        local pid = block:match('%["id"%]%s*=%s*(%d+)')
        if pid then
            local pid_n = tonumber(pid)
            if pid_n and pid_n >= 0 and pid_n <= 2 then
                local primary = block:match('%["primary"%]%s*=%s*"([^"]+)"')
                if primary then
                    overlay_current_weapon_from_pawn_mods(
                        result, pid_n, 0, primary,
                        "primary_mod1", "primary_mod2", block)
                end
                local secondary = block:match('%["secondary"%]%s*=%s*"([^"]+)"')
                if secondary then
                    overlay_current_weapon_from_pawn_mods(
                        result, pid_n, 1, secondary,
                        "secondary_mod1", "secondary_mod2", block)
                end
            end
            local off = block:match('%["offset"%]%s*=%s*(%d+)')
            if off then
                result.pawn_offsets[pid_n] = tonumber(off)
            end
            -- Queued shot (projectile/laser/artillery end-tile)
            local qs = block:match('%["piQueuedShot"%]%s*=%s*Point%s*%(([^%)]+)%)')
            if qs then
                local qsx, qsy = qs:match('(%-?%d+)%s*,%s*(%-?%d+)')
                if qsx and qsy then
                    result.queued_shots[pid_n] = {x = tonumber(qsx), y = tonumber(qsy)}
                end
            end
            -- Origin of the queued attack. piQueuedShot is stored relative
            -- to this point; if a Vek is pushed mid-turn, the live target
            -- shifts by current_position + (piQueuedShot - piOrigin).
            local qo = block:match('%["piOrigin"%]%s*=%s*Point%s*%(([^%)]+)%)')
            if qo then
                local qox, qoy = qo:match('(%-?%d+)%s*,%s*(%-?%d+)')
                if qox and qoy then
                    result.queued_origins[pid_n] = {x = tonumber(qox), y = tonumber(qoy)}
                end
            end
            -- piTarget (leap landing tile, melee target, move-style queued attacks).
            -- Populated for Leapers and other Jumper pawns when piQueuedShot is
            -- (-1,-1). Also populated for non-queued pawns (stale last-target),
            -- so the consumer must gate on iQueuedSkill >= 0.
            local pt = block:match('%["piTarget"%]%s*=%s*Point%s*%(([^%)]+)%)')
            if pt then
                local ptx, pty = pt:match('(%-?%d+)%s*,%s*(%-?%d+)')
                if ptx and pty then
                    result.queued_targets[pid_n] = {x = tonumber(ptx), y = tonumber(pty)}
                end
            end
            -- iQueuedSkill: -1 when no skill is queued, >=0 when queued.
            local qsk = block:match('%["iQueuedSkill"%]%s*=%s*(%-?%d+)')
            if qsk then
                result.queued_skills[pid_n] = tonumber(qsk)
            end
            local mh = block:match('%["max_health"%]%s*=%s*(%d+)')
            if mh then
                result.pawn_max_health[pid_n] = tonumber(mh)
            end
            local infected = block:match('%["bInfected"%]%s*=%s*(true|false)')
            if infected then
                result.infected[pid_n] = infected == "true"
            end
            -- Pilot: nested table inside the pawn block
            local pilot_block = block:match('%["pilot"%]%s*=%s*(%b{})')
            if pilot_block then
                local pilot_id = pilot_block:match('%["id"%]%s*=%s*"([^"]+)"')
                if pilot_id then
                    local pd = {id = pilot_id}
                    local lvl = pilot_block:match('%["level"%]%s*=%s*(%-?%d+)')
                    if lvl then pd.level = tonumber(lvl) end
                    local s1 = pilot_block:match('%["skill1"%]%s*=%s*(%-?%d+)')
                    if s1 then pd.skill1 = tonumber(s1) end
                    local s2 = pilot_block:match('%["skill2"%]%s*=%s*(%-?%d+)')
                    if s2 then pd.skill2 = tonumber(s2) end
                    result.pilots[pid_n] = pd
                end
            end
        end
    end

    -- Conveyor belts: direction from custom tile sprites. Keep loc/custom on
    -- the same serialized tile row; a cross-entry pattern can pair a plain
    -- building loc with the next conveyor custom and create phantom belts.
    for line in content:gmatch("[^\r\n]+") do
        local loc_x, loc_y = line:match('%["loc"%]%s*=%s*Point%(%s*(%d+)%s*,%s*(%d+)%s*%)')
        local dir = line:match('%["custom"%]%s*=%s*"conveyor(%d+)%.png"')
        if loc_x and loc_y and dir then
            local key = loc_x .. "," .. loc_y
            result.conveyor_belts[key] = tonumber(dir)
        end
    end

    return result
end

local function get_pawn_max_health(pawn, uid, save_data)
    local pawn_def = _G[pawn:GetType()]
    local base = (pawn_def and pawn_def.Health) or pawn:GetHealth()
    local max_hp = base

    local fn = pawn.GetMaxHealth
    if type(fn) == "function" then
        local ok, mh = pcall(function() return fn(pawn) end)
        if ok and type(mh) == "number" and mh > 0 then
            max_hp = math.max(max_hp, mh)
        end
    end

    local saved = save_data and save_data.pawn_max_health and save_data.pawn_max_health[uid]
    if type(saved) == "number" and saved > 0 then
        max_hp = math.max(max_hp, saved)
    end

    local bonus = 0
    local pilot = save_data and save_data.pilots and save_data.pilots[uid]
    if pilot then
        local level = pilot.level or 0
        -- Pilot perk ID 0 is a real active skill (+2 HP) once the slot is
        -- unlocked, so gate by level instead of treating zero as empty.
        local active_skills = {}
        if level >= 1 then active_skills[#active_skills + 1] = pilot.skill1 end
        if level >= 2 then active_skills[#active_skills + 1] = pilot.skill2 end
        for _, skill in ipairs(active_skills) do
            if skill == 0 or skill == 8 then
                bonus = bonus + 2
            end
        end
    end
    if bonus > 0 and max_hp < base + bonus then
        return max_hp + bonus
    end
    return max_hp
end

local function normalize_queued_target(raw, origin, current_x, current_y)
    if not raw then return nil, false end
    if not origin then return {raw.x, raw.y}, false end
    local nx = current_x + (raw.x - origin.x)
    local ny = current_y + (raw.y - origin.y)
    if nx < 0 or nx > 7 or ny < 0 or ny > 7 then
        return nil, true
    end
    return {nx, ny}, true
end

--------------------------------------------------------------------
-- Deployment zone capture
--------------------------------------------------------------------
-- Read the live deploy zone from Board:GetZone("deployment") and filter
-- to tiles that are CURRENTLY valid for placement:
--   (a) no pawn already on the tile (Coal Plant, just-deployed mech, etc.)
--   (b) terrain is deployable (excludes building/water/mountain/lava/chasm)
-- Without this filter the bridge reports tiles that aren't yellow on screen
-- and clicks silently fail. Returns a list of {x, y} pairs (possibly empty).
local function capture_deploy_zone()
    if not (Board and Board.GetZone) then return {} end
    local ok, ptList = pcall(function() return Board:GetZone("deployment") end)
    if not ok or not ptList or not ptList.size then return {} end
    local n = ptList:size()
    if n == 0 then return {} end
    local zone = {}
    for i = 1, n do
        local p = ptList:index(i)
        local pawn_ok, pawn = pcall(function() return Board:GetPawn(p) end)
        local terr_ok, terrain = pcall(function() return Board:GetTerrain(p) end)
        local has_pawn = pawn_ok and pawn ~= nil
        -- Deployable: 0=ground, 2=rubble, 6=forest, 7=sand, 8=ice
        local terrain_ok = terr_ok and terrain ~= nil and (
            terrain == 0 or terrain == 2 or terrain == 6
            or terrain == 7 or terrain == 8
        )
        if not has_pawn and terrain_ok then
            zone[#zone + 1] = {p.x, p.y}
        end
    end
    return zone
end

--------------------------------------------------------------------
-- State serializer: Board → JSON
--------------------------------------------------------------------
-- Vanilla Into the Breach does not expose a reliable Board:IsShield(Point)
-- query for terrain. memedit adds that method, but an unextended game raises
-- when it is called. RegionData contains the mission's static map baseline;
-- native damage does not clear consumed shields there (it can even retain a
-- shield after the tile becomes rubble). Export it only as a turn-1 seed and
-- never claim it is live. Python refreshes later turns from saveData at the
-- all-actors-active boundary and carries a verified replay-backed ledger.
local function get_runtime_region_tile_shields()
    local region_data = _G.RegionData
    if type(region_data) ~= "table" then return nil end

    local battle_region = region_data.iBattleRegion
    if type(battle_region) ~= "number" then return nil end

    local region
    if battle_region == 20 then
        region = region_data.final_region
    else
        region = region_data["region" .. tostring(battle_region)]
    end
    if type(region) ~= "table"
            or type(region.player) ~= "table"
            or type(region.player.map_data) ~= "table"
            or type(region.player.map_data.map) ~= "table" then
        return nil
    end

    local shields = {}
    for _, entry in pairs(region.player.map_data.map) do
        if type(entry) == "table" and entry.loc ~= nil then
            local ok_xy, x, y = pcall(function()
                return entry.loc.x, entry.loc.y
            end)
            if ok_xy and type(x) == "number" and type(y) == "number" then
                shields[x .. "," .. y] = entry.shield == true
            end
        end
    end
    return shields
end

local function get_live_tile_shield(pt, runtime_region_shields)
    -- memedit's Board:IsShield is the strongest source when installed: both
    -- true and false are authoritative and must beat all fallbacks.
    local ok, shield = pcall(function() return Board:IsShield(pt) end)
    if ok and type(shield) == "boolean" then return shield end

    -- RegionData is a static positive baseline supplied only on turn 1 by the
    -- caller. It is intentionally absent on later turns.
    if runtime_region_shields ~= nil then
        shield = runtime_region_shields[pt.x .. "," .. pt.y]
        if shield ~= nil then return shield end
    end

    -- Compatibility with any external extension that supplies this spelling.
    ok, shield = pcall(function() return Board:IsShielded(pt) end)
    if ok and type(shield) == "boolean" then return shield end
    return false
end

local function point_list_contains(pt_list, point)
    if pt_list == nil or point == nil then return false end
    local ok_size, size = pcall(function() return pt_list:size() end)
    if not ok_size or type(size) ~= "number" then return false end
    for i = 1, size do
        local ok_point, candidate = pcall(function() return pt_list:index(i) end)
        if ok_point and candidate ~= nil
            and candidate.x == point.x and candidate.y == point.y then
            return true
        end
    end
    return false
end

-- Env_Tides source metadata that Board:IsEnvironmentDanger cannot express.
-- Mission_Terratide inherits the same Index and reverses its row mapping.
-- Keep this helper pure so the mission-scoped scalar is independently
-- testable without loading the game or installing this bridge.
local function mission_tides_index(mission_id, live_environment)
    if mission_id ~= "Mission_Tides"
            and mission_id ~= "Mission_Terratide" then
        return nil
    end
    if type(live_environment) ~= "table"
            or type(live_environment.Index) ~= "number" then
        return nil
    end

    local index = live_environment.Index
    if index ~= index or index == math.huge or index == -math.huge
            or index < 1 or index > 8 or index ~= math.floor(index) then
        return nil
    end
    return index
end

-- Planned distinguishes a pending Env_Tides/Terratide wave from the brief
-- post-ApplyEffect state where Index persists but MarkBoard is inactive.
local function mission_tides_planned(mission_id, live_environment)
    if mission_id ~= "Mission_Tides"
            and mission_id ~= "Mission_Terratide" then
        return nil
    end
    if type(live_environment) ~= "table"
            or type(live_environment.Planned) ~= "boolean" then
        return nil
    end
    return live_environment.Planned
end

-- Mission_Final's Env_Volcano consumes native RNG while Plan builds its
-- ordered Locations list. Export that already-selected list plus the compact
-- phase/mode state instead of guessing random_removal in the solver.
local function mission_final_volcano_points(points, maximum)
    if type(points) ~= "table" or #points > maximum then return nil end
    local result = {}
    local seen = {}
    for i = 1, #points do
        local point = points[i]
        local x = point and point.x
        local y = point and point.y
        if type(x) ~= "number" or x ~= math.floor(x) or x < 0 or x > 7
                or type(y) ~= "number" or y ~= math.floor(y) or y < 0 or y > 7 then
            return nil
        end
        local key = x .. "," .. y
        if seen[key] then return nil end
        seen[key] = true
        result[#result + 1] = {x, y}
    end
    return result
end

local function mission_final_volcano(mission_id, live_environment)
    if mission_id ~= "Mission_Final" then return nil end
    local incomplete = {
        complete = false,
        mode = 0,
        phase = 0,
        lava_start = {},
        locations = {},
        planned = {},
    }
    if type(live_environment) ~= "table" then return incomplete end

    local mode = live_environment.Mode
    local phase = live_environment.Phase
    if type(mode) ~= "number" or mode ~= math.floor(mode)
            or (mode ~= 1 and mode ~= 2)
            or type(phase) ~= "number" or phase ~= math.floor(phase)
            or phase < 0 or phase > 4 then
        return incomplete
    end
    if (phase == 0 and mode ~= 1)
            or ((phase == 1 or phase == 3) and mode ~= 2)
            or ((phase == 2 or phase == 4) and mode ~= 1) then
        return incomplete
    end

    local lava_start = mission_final_volcano_points(
        live_environment.LavaStart,
        2
    )
    local locations = mission_final_volcano_points(
        live_environment.Locations,
        4
    )
    local planned = mission_final_volcano_points(
        live_environment.Planned,
        4
    )
    if lava_start == nil or locations == nil or planned == nil
            or #locations ~= #planned
            or (phase > 0 and #locations == 0) then
        return incomplete
    end
    for i = 1, #locations do
        if locations[i][1] ~= planned[i][1]
                or locations[i][2] ~= planned[i][2] then
            return incomplete
        end
    end

    local start_seen = {}
    for _, point in ipairs(lava_start) do
        if not ((point[1] == 2 and point[2] == 1)
                or (point[1] == 1 and point[2] == 2)) then
            return incomplete
        end
        start_seen[point[1] .. "," .. point[2]] = true
    end
    local expected_start_count = phase == 0 and 2
        or ((phase == 1 or phase == 2) and 1 or 0)
    if #lava_start ~= expected_start_count then return incomplete end

    if mode == 2 then
        local first = locations[1]
        if first == nil or not ((first[1] == 2 and first[2] == 1)
                or (first[1] == 1 and first[2] == 2)) then
            return incomplete
        end
        if phase == 1 and start_seen[first[1] .. "," .. first[2]] then
            return incomplete
        end
        for i = 2, #locations do
            local dx = locations[i][1] - locations[i - 1][1]
            local dy = locations[i][2] - locations[i - 1][2]
            if not ((dx == 1 and dy == 0) or (dx == 0 and dy == 1)) then
                return incomplete
            end
        end
    elseif phase > 0 then
        local last_quarter = -1
        for _, point in ipairs(locations) do
            local x, y = point[1], point[2]
            if x < 1 or x > 6 or y < 1 or y > 6
                    or (x == 1 and y == 1) then
                return incomplete
            end
            local quarter = (x >= 4 and 2 or 0) + (y >= 4 and 1 or 0)
            if quarter <= last_quarter then return incomplete end
            last_quarter = quarter
        end
    end

    return {
        complete = true,
        mode = mode,
        phase = phase,
        lava_start = lava_start,
        locations = locations,
        planned = planned,
    }
end

-- Mission_Terraform completes only when no point in Board:GetZone("grass")
-- retains the exact custom grass sprite. Save map_data also contains
-- decorative ground_grass.png markers outside that objective zone, so export
-- the live, zone-filtered remainder rather than making Python guess from the
-- static map. nil means unavailable/malformed; an empty table is an
-- authoritative completed objective.
local function mission_terraform_grass_tiles(mission_id, board)
    if mission_id ~= "Mission_Terraform" then return nil end

    local ok_zone, zone = pcall(function() return board:GetZone("grass") end)
    if not ok_zone or zone == nil then return nil end

    local ok_size, size = pcall(function() return zone:size() end)
    if not ok_size or type(size) ~= "number"
            or size ~= math.floor(size) or size < 0 or size > 64 then
        return nil
    end

    local result = {}
    local seen = {}
    for i = 1, size do
        local ok_point, point = pcall(function() return zone:index(i) end)
        if not ok_point or point == nil then return nil end
        local ok_xy, x, y = pcall(function() return point.x, point.y end)
        if not ok_xy or type(x) ~= "number" or type(y) ~= "number"
                or x ~= math.floor(x) or y ~= math.floor(y)
                or x < 0 or x > 7 or y < 0 or y > 7 then
            return nil
        end

        local ok_custom, custom = pcall(function()
            return board:GetCustomTile(point)
        end)
        if not ok_custom then return nil end
        if custom == "ground_grass.png" then
            local key = x .. "," .. y
            if not seen[key] then
                seen[key] = true
                result[#result + 1] = {x, y}
            end
        end
    end
    table.sort(result, function(a, b)
        return a[1] < b[1] or (a[1] == b[1] and a[2] < b[2])
    end)
    return result
end

-- Exact identity for Mission_Hacking's stored Cannon Bot and facility. Return
-- the pair together or nothing: partial/malformed identity must never make the
-- simulator guess from another Snowtank1 of the same type.
local function mission_hacking_ids(mission_id, mission)
    if mission_id ~= "Mission_Hacking" or type(mission) ~= "table" then
        return nil, nil
    end
    local bot_id = mission.BotID
    local hack_id = mission.HackID
    local function valid_pawn_id(value)
        return type(value) == "number"
            and value == value
            and value ~= math.huge
            and value ~= -math.huge
            and value >= 0
            and value <= 65535
            and value == math.floor(value)
    end
    if not valid_pawn_id(bot_id) or not valid_pawn_id(hack_id)
            or bot_id == hack_id then
        return nil, nil
    end
    return bot_id, hack_id
end

-- Mission_Piston creates up to four neutral Trash Compactors whose exact pawn
-- type fixes the tile they push. Export the entire live action set atomically:
-- complete=true with an empty list is distinct from an older/malformed bridge
-- that could not inspect the mission. The simulator intentionally does not
-- guess the native Mission_Auto scheduling slot from this state alone.
local function mission_pistons(mission_id, units)
    if mission_id ~= "Mission_Piston" or type(units) ~= "table" then
        return nil
    end
    local offsets = {
        Pawn_Piston_U = {0, -1},
        Pawn_Piston_R = {1, 0},
        Pawn_Piston_D = {0, 1},
        Pawn_Piston_L = {-1, 0},
    }
    local actions = {}
    local seen = {}
    local piston_count = 0
    for _, unit in ipairs(units) do
        local offset = type(unit) == "table" and offsets[unit.type] or nil
        if offset ~= nil and not unit.is_extra_tile then
            piston_count = piston_count + 1
            local uid = unit.uid
            local x = unit.x
            local y = unit.y
            local hp = unit.hp
            local valid = type(uid) == "number"
                and uid == math.floor(uid) and uid >= 0 and uid <= 65535
                and not seen[uid]
                and type(x) == "number" and x == math.floor(x) and x >= 0 and x < 8
                and type(y) == "number" and y == math.floor(y) and y >= 0 and y < 8
                and type(hp) == "number" and hp == math.floor(hp)
                and unit.team == 2
            if not valid or piston_count > 4 then
                return { complete = false, actions = {} }
            end
            seen[uid] = true
            if hp > 0 then
                local front_x = x + offset[1]
                local front_y = y + offset[2]
                if front_x < 0 or front_x >= 8 or front_y < 0 or front_y >= 8 then
                    return { complete = false, actions = {} }
                end
                actions[#actions + 1] = {
                    uid = uid,
                    front = {front_x, front_y},
                }
            end
        end
    end
    table.sort(actions, function(a, b) return a.uid < b.uid end)
    return { complete = true, actions = actions }
end

-- CreateTutorial constructs Mission_Tutorial without assigning the ID field
-- used by ordinary CreateMission.  Preserve every explicit mission ID and
-- synthesize only this source-defined tutorial identity so safety gates do not
-- mistake its scripted native lifecycle for an ordinary combat mission.
local function mission_bridge_id(mission)
    if mission == nil then return nil end
    local mission_id = mission.ID
    if (mission_id == nil or mission_id == "")
            and mission.Name == "Tutorial" then
        return "Mission_Tutorial"
    end
    return mission_id
end

local function dump_state()
    if not Board then return end

    local state = {}

    local mission_id = mission_bridge_id(_ITB_CURRENT_MISSION)

    local terraform_grass_lookup = {}
    local terraform_grass_tiles = mission_terraform_grass_tiles(
        mission_id,
        Board
    )
    if terraform_grass_tiles ~= nil then
        state.terraform_grass_live = true
        state.terraform_grass_tiles = terraform_grass_tiles
        for _, grass in ipairs(terraform_grass_tiles) do
            terraform_grass_lookup[grass[1] .. "," .. grass[2]] = true
        end
    end

    -- Phase detection. Game:GetTeamTurn() can keep returning the last combat
    -- team after MissionEnd, so require the active-mission cache too.
    local in_active_mission = (_ITB_CURRENT_MISSION ~= nil)
    state.in_active_mission = in_active_mission
    local team_turn = Game and Game:GetTeamTurn() or 0
    if not in_active_mission then
        state.phase = "unknown"
    elseif team_turn == 1 then
        state.phase = "combat_player"
    elseif team_turn == 6 then
        state.phase = "combat_enemy"
    else
        state.phase = "unknown"
    end

    state.turn = Game and Game:GetTurnCount() or 0
    state.total_turns = 5  -- Default; overridden from save file below if available

    -- Read all save-file-derived data in one I/O pass (grid power, queued shots, conveyors)
    local save_data = _read_save_data()

    -- Only extension APIs are live. RegionData is a turn-1 static baseline;
    -- the Python reader must replace it from the boundary save/ledger.
    local runtime_region_tile_shields = get_runtime_region_tile_shields()
    local ok_shield_api, shield_probe = pcall(function()
        return Board:IsShield(Point(0, 0))
    end)
    local ok_shielded_api, shielded_probe = pcall(function()
        return Board:IsShielded(Point(0, 0))
    end)
    local has_shield_api = ok_shield_api and type(shield_probe) == "boolean"
    local has_shielded_api = ok_shielded_api and type(shielded_probe) == "boolean"
    local use_runtime_region_baseline = state.turn <= 1
        and runtime_region_tile_shields ~= nil
    local runtime_region_shields_for_export = nil
    if use_runtime_region_baseline then
        runtime_region_shields_for_export = runtime_region_tile_shields
    end
    state.tile_shields_live = has_shield_api or has_shielded_api
    state.tile_shields_static_baseline = use_runtime_region_baseline
    if has_shield_api then
        state.tile_shield_source = "board_api"
    elseif has_shielded_api then
        state.tile_shield_source = "board_is_shielded"
    elseif use_runtime_region_baseline then
        state.tile_shield_source = "runtime_region_turn1_baseline"
    end

    -- Grid power: prefer save file value (authoritative, updated at turn boundaries).
    -- Falls back to GameData globals which may be stale at run transitions.
    -- Game:GetPower() crashes the Lua runtime so we can't use it.
    state.grid_power = save_data.network or (GameData and GameData.network) or 0
    state.grid_power_max = save_data.networkMax or (GameData and GameData.networkMax) or 7
    state.timestamp = os.time()

    -- In-game difficulty (0=Easy, 1=Normal, 2=Hard, 3=Unfair). Mirrors the
    -- save-file source-of-truth so Python can cross-check session metadata
    -- without parsing Lua. See cmd_auto_turn difficulty cross-check.
    state.difficulty = save_data.difficulty
        or (GameData and GameData.difficulty) or 0

    -- RNG seeds for grid-defense resist prediction probe. master_seed is the
    -- run-lifetime constant; mission_seeds is a {region_key -> aiSeed} map
    -- that updates each turn. Python side decides which region is "active".
    if save_data.master_seed ~= nil then
        state.master_seed = save_data.master_seed
    end
    if next(save_data.mission_seeds) ~= nil then
        state.mission_seeds = save_data.mission_seeds
    end

    -- Conveyor belts from consolidated save read
    local conveyor_belts = save_data.conveyor_belts

    -- Objective building lookup:
    --   * Single-objective missions set self.AssetLoc (Coal Plant / Power
    --     Generator / Emergency Batteries). AssetId names the asset.
    --   * Mission_Critical and its subclasses (Solar / Wind / Power) set
    --     self.Criticals = {Point, Point} — two Solar Farms / Wind Farms /
    --     Power Plants. FlavorBase names the asset ("Mission_Solar" etc.).
    -- Both populate the same `objective_keys` map; the solver scores each
    -- tagged tile independently via building_objective_bonus.
    local objective_keys = {}
    if _ITB_CURRENT_MISSION then
        -- Single AssetLoc path
        local ok_loc, loc = pcall(function() return _ITB_CURRENT_MISSION.AssetLoc end)
        local ok_id, aid = pcall(function() return _ITB_CURRENT_MISSION.AssetId end)
        if ok_loc and loc and type(loc) == "userdata" then
            local ok_xy, ox, oy = pcall(function() return loc.x, loc.y end)
            if ok_xy and ox and oy then
                objective_keys[ox .. "," .. oy] = (ok_id and aid) or true
            end
        end
        -- Mission_Critical Criticals path (2 buildings)
        local ok_c, criticals = pcall(function() return _ITB_CURRENT_MISSION.Criticals end)
        local ok_fb, flavor = pcall(function() return _ITB_CURRENT_MISSION.FlavorBase end)
        if ok_c and type(criticals) == "table" then
            for _, cpt in ipairs(criticals) do
                if type(cpt) == "userdata" then
                    local ok_xy, cx, cy = pcall(function() return cpt.x, cpt.y end)
                    if ok_xy and cx and cy then
                        objective_keys[cx .. "," .. cy] = (ok_fb and flavor) or true
                    end
                end
            end
        end
    end

    -- Tiles (all 64)
    state.tiles = {}
    for y = 0, 7 do
        for x = 0, 7 do
            local pt = Point(x, y)
            local terrain_id = Board:GetTerrain(pt)
            local tile = {
                x = x, y = y,
                terrain = TERRAIN_NAMES[terrain_id] or "ground",
                terrain_id = terrain_id,
            }
            if terraform_grass_lookup[x .. "," .. y] then
                tile.grass = true
            end

            -- Status effects
            local ok_f, fire = pcall(function() return Board:IsFire(pt) end)
            if ok_f and fire then tile.fire = true end
            local ok_s, smoke = pcall(function() return Board:IsSmoke(pt) end)
            if ok_s and smoke then tile.smoke = true end
            local ok_a, acid = pcall(function() return Board:IsAcid(pt) end)
            if ok_a and acid then tile.acid = true end
            if get_live_tile_shield(pt, runtime_region_shields_for_export) then
                tile.shield = true
            end
            local ok_fr, frozen = pcall(function() return Board:IsFrozen(pt) end)
            if ok_fr and frozen then tile.frozen = true end
            local ok_cr, cracked = pcall(function() return Board:IsCracked(pt) end)
            if ok_cr and cracked then tile.cracked = true end

            -- Conveyor belt direction (from save file)
            local belt_dir = conveyor_belts[x .. "," .. y]
            if belt_dir then tile.conveyor = belt_dir end

            -- Building data
            if terrain_id == (_G.TERRAIN_BUILDING or 1) then
                local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
                if ok_h then tile.building_hp = hp end
                -- Objective building (Coal Plant / Power Generator /
                -- Batteries via AssetLoc, or Solar Farms / Wind Farms /
                -- Power Plants via Mission_Critical.Criticals).
                local obj_tag = objective_keys[x .. "," .. y]
                if obj_tag then
                    tile.unique_building = true
                    if type(obj_tag) == "string" then
                        tile.objective_name = obj_tag
                    end
                end
            -- Mountain data (2 = full, 1 = damaged, 0 = rubble)
            elseif terrain_id == (_G.TERRAIN_MOUNTAIN or 4) then
                local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
                if ok_h then tile.building_hp = hp else tile.building_hp = 2 end
                tile.population = 1
            end

            -- Pod
            local ok_p, pod = pcall(function() return Board:IsPod(pt) end)
            if ok_p and pod then tile.pod = true end

            -- Tile items (freeze mines, old earth mines, etc.)
            local ok_i, item = pcall(function() return Board:GetItem(pt) end)
            if ok_i and item and item ~= "" then
                tile.item = item
                if item == "Freeze_Mine" or item == "Freeze_Mine_Vek" then
                    tile.freeze_mine = true
                elseif item == "Item_Mine" then
                    tile.old_earth_mine = true
                elseif item == "Item_Repair_Mine" then
                    tile.repair_platform = true
                end
            end

            state.tiles[#state.tiles + 1] = tile
        end
    end

    -- Queued shots from consolidated save read
    local queued_shots = save_data.queued_shots

    -- Units (all teams)
    state.units = {}
    local all_ids = extract_table(Board:GetPawns(TEAM_ANY))
    for _, pid in ipairs(all_ids) do
        local ok, p = pcall(function() return Board:GetPawn(pid) end)
        if ok and p then
            local sp = p:GetSpace()
            if sp.x >= 0 then  -- skip off-board pawns
                local ptype = p:GetType()
                local pawn_def = _G[ptype]

                -- max_hp: prefer pawn's live GetMaxHealth() over pawn_def.Health
                -- because pilots can buff mech HP (e.g. +2 from a passive) and
                -- the live value reflects that. Fall back to def base if API
                -- unavailable. Previous code reported base HP, which was
                -- strictly less than current HP for pilot-boosted mechs.
                local live_max_hp = nil
                local ok_mh, mh = pcall(function() return p:GetMaxHealth() end)
                if ok_mh and type(mh) == "number" and mh > 0 then
                    live_max_hp = mh
                end
                local base_move = pawn_def and pawn_def.MoveSpeed or p:GetMoveSpeed()
                local ok_bm, live_base_move = pcall(function() return p:GetBaseMove() end)
                if ok_bm and type(live_base_move) == "number" then
                    base_move = live_base_move
                end
                -- Native mode-1 path occupancy counts a dead pawn only while
                -- Pawn:IsCorpse() is true. Export both the live predicate and
                -- source/static Corpse property so projected deaths retain
                -- the right blocker identity without installing any hook.
                local current_corpse = false
                local ok_co, is_corpse = pcall(function() return p:IsCorpse() end)
                if ok_co and is_corpse == true then
                    current_corpse = true
                end
                local corpse_on_death =
                    pawn_def and pawn_def.Corpse == true or false
                local unit = {
                    uid = pid,
                    type = ptype,
                    x = sp.x, y = sp.y,
                    hp = p:GetHealth(),
                    max_hp = live_max_hp or (pawn_def and pawn_def.Health) or p:GetHealth(),
                    team = p:GetTeam(),
                    mech = p:IsMech(),
                    active = p:IsActive(),
                    move = p:GetMoveSpeed(),
                    base_move = base_move,
                    minor = pawn_def and pawn_def.Minor or false,
                    corpse = current_corpse,
                    corpse_on_death = corpse_on_death,
                    void_shock_immune = pawn_def and pawn_def.VoidShockImmune or false,
                }

                -- Pilot info (mechs only). Save-file-derived is the most
                -- reliable source; Lua-API probes are a fallback. Save
                -- structure is `pawnN.pilot.{id,level,skill1,skill2}` per
                -- entry, keyed by pawn id (matches `pid` here).
                if p:IsMech() then
                    local pilot_id = nil
                    local pilot_level = nil
                    local pilot_skills = {}
                    local save_pilot = save_data.pilots[pid]
                    if save_pilot then
                        pilot_id = save_pilot.id
                        pilot_level = save_pilot.level
                        if save_pilot.skill1 and save_pilot.skill1 ~= 0 then
                            pilot_skills[#pilot_skills + 1] = "skill1=" .. save_pilot.skill1
                        end
                        if save_pilot.skill2 and save_pilot.skill2 ~= 0 then
                            pilot_skills[#pilot_skills + 1] = "skill2=" .. save_pilot.skill2
                        end
                    end
                    -- Lua API probe fallback (if save had no match)
                    if not pilot_id then
                        for _, mname in ipairs({"GetPilotId", "GetPilot"}) do
                            local ok_pm, pv = pcall(function() return p[mname](p) end)
                            if ok_pm and pv then
                                if type(pv) == "string" and pv ~= "" then
                                    pilot_id = pv; break
                                elseif type(pv) == "table" and pv.id then
                                    pilot_id = pv.id
                                    if pv.level then pilot_level = pv.level end
                                    break
                                end
                            end
                        end
                    end
                    if pilot_id then unit.pilot_id = pilot_id end
                    if pilot_level then unit.pilot_level = pilot_level end
                    if #pilot_skills > 0 then unit.pilot_skills = pilot_skills end
                end

                -- Massive trait (walks in water, immune to drowning)
                -- Read from pawn_def since there's no direct IsMassive() API
                if pawn_def and pawn_def.Massive then
                    unit.massive = true
                end

                -- Stable / guarding units cannot be moved by push/teleport
                -- effects even when their static pawn type is normally
                -- pushable. Bridge this as live pushability because bosses and
                -- mission units can gain the status dynamically.
                local pushable = nil
                if pawn_def and pawn_def.Pushable == false then
                    pushable = false
                end
                local ok_g, guarding = pcall(function() return p:IsGuarding() end)
                if ok_g then
                    unit.guarding = guarding
                    unit.stable = guarding
                    if guarding then
                        pushable = false
                    elseif pushable == nil and pawn_def and pawn_def.Pushable ~= nil then
                        pushable = pawn_def.Pushable ~= false
                    end
                end
                if pushable ~= nil then
                    unit.pushable = pushable
                end
                local ok_pw, powered = pcall(function() return p:IsPowered() end)
                if ok_pw and type(powered) == "boolean" then unit.powered = powered end
                local ok_bu, burrower = pcall(function() return p:IsBurrower() end)
                if ok_bu and type(burrower) == "boolean" then unit.burrower = burrower end
                local ok_ju, jumper = pcall(function() return p:IsJumper() end)
                if ok_ju and type(jumper) == "boolean" then unit.jumper = jumper end

                -- Status effects
                local ok_f, fly = pcall(function() return p:IsFlying() end)
                if ok_f then unit.flying = fly end
                local ok_s, sh = pcall(function() return p:IsShield() end)
                if ok_s then unit.shield = sh end
                local ok_a, ac = pcall(function() return p:IsAcid() end)
                if ok_a then unit.acid = ac end
                local ok_fi, fi = pcall(function() return p:IsFire() end)
                if ok_fi then unit.fire = fi end
                local ok_fr, fr = pcall(function() return p:IsFrozen() end)
                if ok_fr then unit.frozen = fr end
                local infected = nil
                for _, mname in ipairs({"IsInfected", "IsInfested", "IsMiteInfected"}) do
                    local ok_m, v = pcall(function() return p[mname](p) end)
                    if ok_m and type(v) == "boolean" then
                        infected = v
                        break
                    end
                end
                if infected == nil and save_data.infected[pid] ~= nil then
                    infected = save_data.infected[pid]
                end
                if infected ~= nil then unit.infected = infected end
                local ok_bo, boosted = pcall(function() return p:IsBoosted() end)
                if ok_bo and boosted then unit.boosted = true end
                -- Web/grapple detection: try multiple API method names.
                -- IsGrappled() alone misses Spider-egg webs on mechs; probe
                -- alternatives so either the Scorpion-grapple or the Spider-
                -- egg web lands in unit.web.
                local web = false
                local web_probes = {}
                for _, mname in ipairs({
                    "IsGrappled", "IsWebbed", "IsWeb", "IsPinned",
                    "IsHeld", "IsHold",
                }) do
                    local ok_m, v = pcall(function() return p[mname](p) end)
                    if ok_m then
                        web_probes[mname] = v
                        if v == true then web = true end
                    end
                end
                unit.web = web
                if type(web_probes.IsGrappled) == "boolean" then
                    unit.grappled = web_probes.IsGrappled
                end
                unit.web_probes = web_probes  -- diagnostic; remove when verified
                -- Webber identification: try API methods first, fall back later (post-loop)
                if web then
                    for _, mname in ipairs({"GetGrappler", "GetGrappledBy", "GetGrapplerPawn", "GetPinnedBy"}) do
                        local ok_m, src = pcall(function() return p[mname](p) end)
                        if ok_m and src then
                            local ok_id, sid = pcall(function() return src:GetId() end)
                            if ok_id and sid then unit.web_source_uid = sid; break end
                        end
                    end
                end
                local ok_ar, ar = pcall(function() return p:IsArmor() end)
                if ok_ar and ar then unit.armor = true end

                -- Weapons from type definition. Python applies the narrow
                -- modeled save overlay before solving and action execution;
                -- exporting every purchased passive here could bypass the
                -- solver's known-type/research gate.
                unit.weapons = {}
                if pawn_def and pawn_def.SkillList then
                    for _, wname in ipairs(pawn_def.SkillList) do
                        unit.weapons[#unit.weapons + 1] = wname
                    end
                end

                -- Enemy attack data
                if p:GetTeam() == TEAM_ENEMY then
                    local qskill = save_data.queued_skills[pid]
                    local ok_sw, sw = pcall(function() return p:GetSelectedWeapon() end)
                    if qskill ~= nil then
                        unit.has_queued_attack = qskill >= 0
                        if ok_sw and sw and sw > 0 and not unit.has_queued_attack then
                            log_bridge(string.format(
                                "selected_weapon ignored for non-attacking %s/%d: GetSelectedWeapon=%s iQueuedSkill=%s",
                                ptype or "?", pid, tostring(sw), tostring(qskill)))
                        end
                    elseif ok_sw and sw and sw > 0 then
                        unit.has_queued_attack = true
                    end

                    -- Per-enemy target: piQueuedShot first (projectile/laser/
                    -- artillery attacks), then piTarget (leap/melee landing
                    -- tile — used by Jumper pawns like Leaper1/Leaper2 where
                    -- piQueuedShot is (-1,-1)), then Lua API probes. We must
                    -- gate the piTarget read on iQueuedSkill >= 0 because the
                    -- save stores piTarget as a stale last-target even on
                    -- pawns that have no queued skill this turn.
                    local qorigin = save_data.queued_origins[pid]
                    if qorigin then
                        unit.queued_origin = {qorigin.x, qorigin.y}
                    end
                    local qs = save_data.queued_shots[pid]
                    if qs and qs.x >= 0 and qs.y >= 0 then
                        unit.queued_target_raw = {qs.x, qs.y}
                        local normalized, did_normalize =
                            normalize_queued_target(qs, qorigin, unit.x, unit.y)
                        unit.queued_target = normalized
                        if did_normalize then
                            unit.queued_target_normalized = true
                        end
                        -- Save-file piQueuedShot can remain stale after live
                        -- attack retarget effects such as DIR_FLIP. Prefer
                        -- the C++ pawn's current queued shot when it returns a
                        -- valid board tile; it already reflects the current
                        -- position/target and must not be normalized again by
                        -- the Python reader.
                        if unit.has_queued_attack then
                            local ok_gqs, gqs = pcall(function() return p:GetQueuedShot() end)
                            if ok_gqs and gqs and (type(gqs) == "userdata" or type(gqs) == "table") then
                                local gx, gy = gqs.x, gqs.y
                                if type(gx) == "number" and type(gy) == "number"
                                        and gx >= 0 and gy >= 0
                                        and gx <= 7 and gy <= 7
                                        and (not unit.queued_target
                                             or unit.queued_target[1] ~= gx
                                             or unit.queued_target[2] ~= gy) then
                                    log_bridge(string.format(
                                        "queued_target live override for %s/%d: save=(%d,%d) normalized=%s GetQueuedShot=(%d,%d)",
                                        ptype or "?", pid, qs.x, qs.y,
                                        unit.queued_target and string.format("(%d,%d)", unit.queued_target[1], unit.queued_target[2]) or "nil",
                                        gx, gy))
                                    unit.queued_target = {gx, gy}
                                    unit.queued_target_normalized = true
                                end
                            end
                        end
                    elseif unit.has_queued_attack then
                        local resolved_via = nil
                        -- (1) Save-file piTarget (works for Leapers, Scorpions,
                        --     any melee/jumper pawn with AddQueuedMelee).
                        local qt = save_data.queued_targets[pid]
                        if qt and qskill and qskill >= 0
                                and qt.x >= 0 and qt.y >= 0
                                and qt.x <= 7 and qt.y <= 7 then
                            unit.queued_target = {qt.x, qt.y}
                            resolved_via = "save_piTarget"
                        end
                        -- (2) Live Lua API: GetQueuedShot() — works for
                        --     HornetBoss and similar shots that don't land
                        --     in piQueuedShot. Try even if (1) succeeded so
                        --     we can log a mismatch for calibration.
                        local ok_gqs, gqs = pcall(function() return p:GetQueuedShot() end)
                        local gqs_desc = "nil"
                        if ok_gqs and gqs and (type(gqs) == "userdata" or type(gqs) == "table") then
                            local gx, gy = gqs.x, gqs.y
                            if type(gx) == "number" and type(gy) == "number" then
                                gqs_desc = string.format("(%d,%d)", gx, gy)
                                if not unit.queued_target
                                        and gx >= 0 and gy >= 0
                                        and gx <= 7 and gy <= 7 then
                                    unit.queued_target = {gx, gy}
                                    resolved_via = "GetQueuedShot"
                                end
                            else
                                gqs_desc = "non_numeric"
                            end
                        elseif not ok_gqs then
                            gqs_desc = "pcall_err"
                        end
                        -- (3) Additional Lua API probes as last resort —
                        --     these may or may not exist on the C++ Pawn
                        --     binding; pcall swallows missing-method errors.
                        --     Logged so the next run tells us which (if any)
                        --     succeeded for stubborn pawn types.
                        if not unit.queued_target then
                            for _, mname in ipairs({
                                "GetQueuedTarget", "GetTarget",
                                "GetQueuedMove", "GetQueuedLocation",
                            }) do
                                local ok_m, v = pcall(function() return p[mname](p) end)
                                if ok_m and v and (type(v) == "userdata" or type(v) == "table") then
                                    local vx, vy = v.x, v.y
                                    if type(vx) == "number" and type(vy) == "number"
                                            and vx >= 0 and vy >= 0
                                            and vx <= 7 and vy <= 7 then
                                        unit.queued_target = {vx, vy}
                                        resolved_via = mname
                                        break
                                    end
                                end
                            end
                        end
                        log_bridge(string.format(
                            "queued_target fallback for %s/%d: via=%s piTarget=%s iQueuedSkill=%s GetQueuedShot=%s result=%s",
                            ptype or "?", pid,
                            resolved_via or "none",
                            qt and string.format("(%d,%d)", qt.x, qt.y) or "nil",
                            tostring(qskill),
                            gqs_desc,
                            unit.queued_target and string.format("(%d,%d)", unit.queued_target[1], unit.queued_target[2]) or "UNRESOLVED"))
                    end

                    -- Weapon properties from game globals
                    local weapon_name = unit.weapons[1]
                    if weapon_name then
                        local wdef = _G[weapon_name]
                        if wdef then
                            unit.weapon_damage = wdef.Damage or 0
                            unit.weapon_target_behind = wdef.TargetBehind or false
                            unit.weapon_push = wdef.Push or 0
                        end
                    end
                end

                state.units[#state.units + 1] = unit

                -- Multi-tile pawns (Dam_Pawn ExtraSpaces): emit a separate
                -- unit entry per extra tile. Downstream solver mirrors HP
                -- across all entries with matching uid at damage time.
                if pawn_def and pawn_def.ExtraSpaces then
                    for _, offset in ipairs(pawn_def.ExtraSpaces) do
                        local ex = sp.x + offset.x
                        local ey = sp.y + offset.y
                        if ex >= 0 and ex < 8 and ey >= 0 and ey < 8 then
                            local extra = {}
                            for k, v in pairs(unit) do extra[k] = v end
                            extra.x = ex
                            extra.y = ey
                            extra.is_extra_tile = true
                            extra.weapons = {}  -- don't double-emit attacks
                            state.units[#state.units + 1] = extra
                        end
                    end
                end
            end
        end
    end

    -- Attack order: enemies with queued attacks in live unit-list order.
    -- Do not sort by UID; Mission_Factory captures showed Pinnacle bots can
    -- resolve Snowlaser before a lower-UID Burnbug kills it.
    state.attack_order = {}
    for _, u in ipairs(state.units) do
        if u.team == 6 and u.has_queued_attack then
            state.attack_order[#state.attack_order + 1] = u.uid
        end
    end

    -- Webber fallback: for any webbed unit without a known web_source_uid
    -- (Lua API didn't expose it), pick the closest alive enemy whose primary
    -- weapon has Web=true. ITB rule: web breaks when webber is pushed or killed,
    -- so the solver needs to know which enemy unwebs the unit. If no webber is
    -- found (all dead), clear the stale web flag entirely.
    local WEB_WEAPONS = {ScorpionAtk1=true, ScorpionAtk2=true, ScorpionAtkB=true,
                         LeaperAtk1=true, LeaperAtk2=true, MosquitoAtkB=true}
    for _, u in ipairs(state.units) do
        if u.web and not u.web_source_uid then
            local best_uid, best_dist = nil, 999
            for _, e in ipairs(state.units) do
                if e.team == 6 and e.hp > 0 and e.weapons and e.weapons[1]
                        and WEB_WEAPONS[e.weapons[1]] then
                    local d = math.abs(e.x - u.x) + math.abs(e.y - u.y)
                    if d < best_dist then best_uid, best_dist = e.uid, d end
                end
            end
            if best_uid then
                u.web_source_uid = best_uid
            else
                -- No webber alive: stale web. Clear it and restore base move.
                u.web = false
                u.move = u.base_move
            end
        end
    end

    -- Targeted tiles (enemy attack indicators)
    state.targeted_tiles = {}
    for y = 0, 7 do
        for x = 0, 7 do
            if Board:IsTargeted(Point(x, y)) then
                state.targeted_tiles[#state.targeted_tiles + 1] = {x, y}
            end
        end
    end

    -- Spawning tiles
    state.spawning_tiles = {}
    for y = 0, 7 do
        for x = 0, 7 do
            if Board:IsSpawning(Point(x, y)) then
                state.spawning_tiles[#state.spawning_tiles + 1] = {x, y}
            end
        end
    end

    -- Environment danger (v1 + v2). v1 = flat list of [x,y] tiles.
    -- v2 = list of [x, y, damage, kill_int, flying_immune] where:
    --   kill_int=1      → Deadly Threat (instant-kill, bypasses shield/
    --                     frozen/armor/ACID per ITB spec)
    --   flying_immune=1 → terrain-conversion lethal (Tidal Wave, Cataclysm,
    --                     Seismic). Effectively-flying units survive
    --                     because water/chasm rules let them hover.
    --                     Air Strike / Lightning / Final Cave falling rocks
    --                     emit flying_immune=0 — those hit flyers too.
    --                     Satellite launch exhaust emits flying_immune=1:
    --                     ground units die, flyers survive.
    -- The 5th field landed at SIMULATOR_VERSION 19 (2026-04-25) closing the
    -- "Hornet on Tidal tile" silent kill desync. Older bridges emit only 4
    -- fields; the Rust deserializer falls back to env_type when the 5th is
    -- missing.
    --
    -- environment_freeze (sim v25): list of [x,y] for Ice Storm tiles (vanilla
    -- Env_SnowStorm, Acid=false). Applies Frozen=true to units at start of
    -- enemy turn — non-lethal status, separate channel from env_danger so the
    -- evaluator scores "lose a turn" rather than "die". NanoStorm
    -- (Env_NanoStorm = Env_SnowStorm:new{Acid=true}) routes into env_danger
    -- with kill=0, damage=1 (the existing non-lethal path handles 1 damage).
    state.environment_danger = {}
    state.environment_danger_v2 = {}
    state.environment_freeze = {}

    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if not mission or not mission.LiveEnvironment then return end
        local volcano = mission_final_volcano(
            mission_id,
            mission.LiveEnvironment
        )
        if volcano ~= nil then
            state.mission_final_volcano = volcano
        end
    end)

    -- Default all env_danger tiles to lethal (kill=1). Most hazards ARE
    -- lethal to ground units: Air Strike, Lightning, Cataclysm→chasm,
    -- Seismic→chasm, Tidal Waves→water. Non-lethal hazards (Wind Storm,
    -- Sandstorm, NanoStorm) detected via class match / field signatures
    -- and get kill=0. Vanilla Ice Storm bypasses env_danger entirely and
    -- routes through env_freeze instead.
    local env_damage = 1
    local env_kill_default = true
    -- Default flying_immune is false. Set true for terrain-conversion
    -- env types when env_type detection lands on tidal/cataclysm/seismic.
    local env_flying_immune_default = false
    -- When the env class is Env_SnowStorm with Acid=false, route IsEnvironmentDanger
    -- tiles into environment_freeze instead of environment_danger. NanoStorm (Acid=true)
    -- uses env_danger with non-lethal damage. Set during class-metatable detection below.
    local route_to_freeze = false

    -- Class-metatable detection FIRES BEFORE field signatures: Env_SnowStorm
    -- shares the `Locations` field with Lightning/Air Strike/Seismic, so the
    -- old field-first heuristic flagged Ice Storm as kill=1 lethal. Walk the
    -- metatable chain so subclasses (Env_NanoStorm extends Env_SnowStorm)
    -- match too. Field signatures stay as a fallback for envs we don't
    -- explicitly recognize.
    local env_type = "unknown"
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if not mission or not mission.LiveEnvironment then return end
        local le = mission.LiveEnvironment
        local mission_id = mission.ID or ""

        -- Mission_Final_Cave uses Env_Final, whose marked tiles are falling
        -- rock / tentacle death effects (SpaceDamage(..., DAMAGE_DEATH)),
        -- not ordinary chasm conversion. Prospero/flying mechs die here.
        if mission_id == "Mission_Final_Cave" then
            env_type = "final_cave"
            env_kill_default = true
            env_flying_immune_default = false
            return
        end

        -- Surface Volcanic Hive alternates source-defined ordered Rocks and
        -- Lava modes. Lava carries zero direct damage on the wire because its
        -- lethality comes from the permanent TERRAIN_LAVA conversion; Rust
        -- consumes the ordered mission_final_volcano payload for exact unit
        -- and terrain semantics.
        if mission_id == "Mission_Final" then
            env_type = "volcano"
            env_flying_immune_default = false
            local volcano = state.mission_final_volcano
            if volcano and volcano.complete and volcano.mode == 2 then
                env_damage = 0
                env_kill_default = false
            else
                env_damage = 1
                env_kill_default = true
            end
            return
        end

        -- Mission_Terratide subclasses Env_Tides but replaces the lethal
        -- water wave with a smoke wave (NewTerrain=TERRAIN_SAND).  Its live
        -- environment still exposes `Index`, so without this authoritative
        -- mission override it falls through as lethal tidal/cataclysm danger.
        -- Keep the warned row on the v2 channel with kill=0; the Rust bridge
        -- decoder routes this mission's row to pending smoke rather than the
        -- generic non-lethal 1-damage path.
        if mission_id == "Mission_Terratide" then
            env_type = "sandstorm"
            env_kill_default = false
            env_flying_immune_default = false
            return
        end

        -- Walk metatable chain. For each link, check membership in our
        -- known-env table. Stops at first match. `_G` lookup is safe — class
        -- globals are always set before any LiveEnvironment instance exists.
        local mt = getmetatable(le)
        while mt do
            local cls_table = mt.__index or mt
            -- Env_SnowStorm: vanilla Ice Storm (Acid=false, freeze) OR Env_NanoStorm
            -- which inherits from it (Acid=true, 1 acid damage). Distinguish by the
            -- live instance's Acid flag — covers both directly-instantiated SnowStorms
            -- and the Nano subclass without a separate metatable check.
            if _G["Env_SnowStorm"] and cls_table == _G["Env_SnowStorm"] then
                if le.Acid then
                    -- NanoStorm: 1 damage + ACID, non-lethal, no freeze.
                    -- ACID application itself is a separate gap — bridge
                    -- doesn't carry per-tile-acid yet — but the 1-damage
                    -- non-lethal path is correct for now.
                    env_type = "nanostorm"
                    env_kill_default = false
                else
                    -- Vanilla Ice Storm: 0 damage, Frozen=true.
                    env_type = "snow"
                    env_kill_default = false
                    route_to_freeze = true
                end
                return
            end
            if _G["Env_Sandstorm"] and cls_table == _G["Env_Sandstorm"] then
                env_type = "sandstorm"
                env_kill_default = false
                return
            end
            mt = getmetatable(cls_table)
        end

        -- Mission IDs are authoritative when class/field signatures collide.
        -- Archive Airstrike exposes StartEffect like Seismic/Cataclysm on some
        -- bridge builds, but bombs still kill flying units. Terrain-conversion
        -- missions are the ones where flyers hover over the new water/chasm.
        if mission_id == "Mission_Airstrike"
                or mission_id == "Mission_Lightning"
                or mission_id == "Mission_LightningStorm" then
            env_type = "lightning_or_airstrike"
            env_kill_default = true
            env_flying_immune_default = false
            return
        elseif mission_id == "Mission_Tides" then
            env_type = "tidal"
            env_kill_default = true
            env_flying_immune_default = true
            return
        elseif mission_id == "Mission_Cataclysm"
                or mission_id == "Mission_Crack" then
            env_type = "cataclysm_or_seismic"
            env_kill_default = true
            env_flying_immune_default = true
            return
        end

        -- Field-signature fallback for envs without an explicit class match
        -- (mods, edge-case classes). Order tightened: WindDir/Row/Index/StartEffect
        -- are unique enough; Locations is checked LAST since SnowStorm shares it.
        if le.WindDir ~= nil then
            env_type = "wind"
            env_kill_default = false
        elseif le.Row ~= nil then
            env_type = "sandstorm"
            env_kill_default = false
        elseif le.Indices ~= nil then
            -- No known vanilla env uses bare Indices — kept for mod compat.
            env_type = "snow"
            env_kill_default = false
        elseif le.Index ~= nil then
            env_type = "tidal_or_cataclysm"
            env_flying_immune_default = true
        elseif le.StartEffect ~= nil then
            env_type = "cataclysm_or_seismic"
            env_flying_immune_default = true
        elseif le.Locations ~= nil then
            -- After the Env_SnowStorm metatable check above, Locations now
            -- means Lightning / Air Strike / Seismic.
            env_type = "lightning_or_airstrike"
            env_flying_immune_default = false
        else
            local fields = {}
            pcall(function()
                for k, _ in pairs(le) do fields[#fields+1] = tostring(k) end
            end)
            log_bridge("[env] WARNING: unknown env_type. Fields: " .. table.concat(fields, ", "))
        end
    end)
    state.env_type = env_type

    -- The visible warning mask can be empty when every column is hidden by a
    -- building shadow or already has the target terrain. Export the live
    -- Index so Rust can still advance Env_Tides::Plan exactly. For Tides, Rust
    -- derives the full-row permanent spawn-block boundary from the inventoried
    -- source; Terratide does not execute that water-only BlockSpawn branch.
    -- No native blocked-cell getter has been identified for this build.
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if not mission or not mission.LiveEnvironment then return end
        local index = mission_tides_index(
            mission.ID or "",
            mission.LiveEnvironment
        )
        if index ~= nil then
            state.environment_tides_index = index
        end
        local planned = mission_tides_planned(
            mission.ID or "",
            mission.LiveEnvironment
        )
        if planned ~= nil then
            state.environment_tides_planned = planned
        end
    end)

    if env_type == "wind" then
        pcall(function()
            local mission = _ITB_CURRENT_MISSION
            if mission and mission.LiveEnvironment
                    and mission.LiveEnvironment.WindDir ~= nil then
                state.environment_wind_dir = mission.LiveEnvironment.WindDir
            end
        end)
    end

    -- Helper: add a danger tile to both v1 and v2 fields. The optional
    -- `flying_immune_override` controls the 5th field.
    local function add_danger(x, y, kill_override, flying_immune_override)
        state.environment_danger[#state.environment_danger + 1] = {x, y}
        local k = env_kill_default
        if kill_override ~= nil then
            k = kill_override
        end
        local fi = env_flying_immune_default
        if flying_immune_override ~= nil then
            fi = flying_immune_override
        end
        -- flying_immune is meaningless on non-lethal tiles (1 dmg already
        -- skips flying via the bump path); zero it out to keep the wire
        -- representation tidy.
        if not k then fi = false end
        state.environment_danger_v2[#state.environment_danger_v2 + 1] =
            {x, y, env_damage, k and 1 or 0, fi and 1 or 0}
    end

    for y = 0, 7 do
        for x = 0, 7 do
            local ok, danger = pcall(function() return Board:IsEnvironmentDanger(Point(x, y)) end)
            if ok and danger then
                if route_to_freeze then
                    -- Vanilla Ice Storm: tiles freeze at start of enemy turn.
                    -- Non-lethal status effect; bypasses env_danger entirely.
                    state.environment_freeze[#state.environment_freeze + 1] = {x, y}
                else
                    add_danger(x, y)
                end
            end
        end
    end

    -- Satellite rocket deadly threat: 4 adjacent tiles kill grounded units on
    -- launch. Board:IsEnvironmentDanger() does NOT detect these, so we add
    -- them manually.
    -- Only flag tiles on the turn the rocket is queued to fire (GetSelectedWeapon > 0).
    -- Satellite rockets are always lethal regardless of mission environment,
    -- but live launch exhaust spares flying pawns.
    for _, u in ipairs(state.units) do
        if u.type and string.find(u.type, "Satellite") then
            local ok, p = pcall(function() return Board:GetPawn(u.uid) end)
            if ok and p then
                local ok_sw, sw = pcall(function() return p:GetSelectedWeapon() end)
                local queued = ok_sw and sw and sw > 0
                if queued then
                    u.queued_launch = true
                    local dirs = {{-1,0},{1,0},{0,-1},{0,1}}
                    for _, d in ipairs(dirs) do
                        local nx, ny = u.x + d[1], u.y + d[2]
                        if nx >= 0 and nx <= 7 and ny >= 0 and ny <= 7 then
                            add_danger(nx, ny, true, true)
                        end
                    end
                end
            end
        end
    end

    -- Deployment zone: prefer a live Board:GetZone("deployment") read on every
    -- dump so the zone is correct even when BaseDeployment hasn't fired yet
    -- (e.g. between missions) or has been cleared by MissionEnd. Falls back to
    -- the cached BaseDeployment capture if the live read returns nothing.
    pcall(function()
        local zone = capture_deploy_zone()
        if zone and #zone > 0 then
            state.deployment_zone = zone
            _ITB_DEPLOY_ZONE = zone  -- refresh cache for consistency
        end
    end)
    if not state.deployment_zone and _ITB_DEPLOY_ZONE and #_ITB_DEPLOY_ZONE > 0 then
        state.deployment_zone = _ITB_DEPLOY_ZONE
    end

    -- Mission metadata for hazard classification
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if mission then
            state.mission_id = mission_id
            -- Mission_Hacking converts one specific stored Cannon Bot after
            -- one specific stored facility dies. Export both live pawn IDs so
            -- the simulator never guesses from type alone when other
            -- Snowtank1 enemies are present. Missing/invalid IDs are omitted;
            -- old bridge payloads therefore fail closed in Rust.
            local bot_id, hack_id = mission_hacking_ids(mission.ID, mission)
            if bot_id ~= nil then
                state.mission_hacking_bot_id = bot_id
                state.mission_hacking_hack_id = hack_id
            end
            local pistons = mission_pistons(mission.ID, state.units)
            if pistons ~= nil then
                state.mission_pistons = pistons
            end
        end
    end)

    -- Teleporter pads: populated by the Mission_Teleporter:StartMission
    -- wrap below. Each entry = {x1, y1, x2, y2}. Empty list / absent on
    -- non-teleporter missions; stale pairs must not leak into other
    -- missions. The earlier Board.AddTeleport global
    -- override crashed mac OS at file-load with "no static 'AddTeleport'
    -- in class 'Board'" (commit 456ba49 → rolled back in 63e0e18); the
    -- current scope-rebinds AddTeleport only inside StartMission and pcalls
    -- everything so a future API change can't take down mission load.
    if state.mission_id == "Mission_Teleporter"
       and _ITB_TELEPORT_PAIRS and #_ITB_TELEPORT_PAIRS > 0 then
        state.teleporter_pairs = {}
        for _, pair in ipairs(_ITB_TELEPORT_PAIRS) do
            state.teleporter_pairs[#state.teleporter_pairs + 1] = pair
        end
    end

    -- Bonus-objective progress for enemy kill-count objectives.
    -- BONUS_KILL_FIVE is "kill at least N"; BONUS_PACIFIST is
    -- "kill N or fewer". Emit separate fields because the former rewards
    -- extra kills while the latter fails immediately when exceeded. Per
    -- scripts/missions/missions.lua:
    --   BONUS_KILL_FIVE = 6 in the enum
    --   BONUS_PACIFIST = 9 in the enum
    --   mission.BonusObjs is the chosen bonus list (random from BonusPool)
    --   mission.KilledVek is cumulative generic kill-count progress
    --   mission:GetKillBonus() is difficulty-scaled (5 easy / 7 normal/hard)
    --   mission:GetPacifistCount() is difficulty-scaled (4 easy / 5 normal/hard / 6 unfair)
    -- Mission_AcidTank is a built-in Detritus objective rather than a
    -- BONUS_KILL_FIVE entry: kill 4 acid-inflicted Vek. It tracks mission.AcidKills,
    -- so expose that through the same solver fields.
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        local is_acid_tank = mission and mission.ID == "Mission_AcidTank"
        if is_acid_tank then
            state.mission_kill_target = 4
        end
        if mission and mission.BonusObjs then
            local has_kill_five = false
            local has_pacifist = false
            for _, obj in ipairs(mission.BonusObjs) do
                if obj == 6 then has_kill_five = true end
                if obj == 9 then has_pacifist = true end
            end
            if has_kill_five and mission.GetKillBonus then
                local ok, target = pcall(function() return mission:GetKillBonus() end)
                if ok and type(target) == "number" then
                    state.mission_kill_target = target
                end
            end
            if has_pacifist and mission.GetPacifistCount then
                local ok, limit = pcall(function() return mission:GetPacifistCount() end)
                if ok and type(limit) == "number" then
                    state.mission_kill_limit = limit
                end
            end
        end
        if is_acid_tank and mission.AcidKills ~= nil then
            state.mission_kills_done = mission.AcidKills
        elseif mission and mission.KilledVek ~= nil then
            state.mission_kills_done = mission.KilledVek
        end
    end)

    -- Mission_Repair objective progress ("Use 3 Repair Platforms"). The
    -- game increments RepairPickups from EVENT_REPAIR_PICKUP; any unit that
    -- triggers Item_Repair_Mine counts. Expose both target and cumulative
    -- progress so the solver can value using the remaining platforms.
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if mission and mission.ID == "Mission_Repair" then
            state.repair_platform_target = 3
            if mission.RepairPickups ~= nil then
                state.repair_platforms_used = mission.RepairPickups
            end
        end
    end)

    -- Mission_Force objective progress ("Destroy 2 mountains"). The game
    -- increments mission.Mountains from EVENT_MOUNTAIN_DESTROYED and gates
    -- mission end on mission.MountainsGoal.
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if mission and mission.ID == "Mission_Force" then
            if mission.MountainsGoal ~= nil then
                state.mission_mountain_target = mission.MountainsGoal
            else
                state.mission_mountain_target = 2
            end
            if mission.Mountains ~= nil then
                state.mission_mountains_destroyed = mission.Mountains
            end
        end
    end)

    -- TODO(sim_v21): emit `state.bonus_objective_unit_types` — the list of
    -- pawn-type strings the active mission's BonusObjs flag as "do not
    -- kill X" (e.g. BONUS_PROTECT_VOLATILE → {"GlowingScorpion"}). The
    -- Rust side already reads `JsonInput::bonus_objective_unit_types`
    -- and gates `volatile_enemy_killed` on it; while this Lua hook is
    -- unimplemented, Python falls back to `data/mission_bonus_objectives.json`
    -- keyed by mission_id (see src/solver/mission_bonus_objectives.py).
    -- Implementing this in Lua requires inspecting mission.BonusObjs for
    -- the protect-X enum values + walking the mission's Pawn list to map
    -- enum→type-name; safe to do but needs in-game testing to validate
    -- the enum values, hence deferred. The Python fallback covers all
    -- catalogued protect-X missions today.

    -- Victory signal: when mission:IsFinalTurn() is true, no more Vek will
    -- emerge after this turn's enemy phase. Solver treats this as the final
    -- turn (future_factor = 0). Also expose mission.TurnLimit as authoritative
    -- total_turns — this matches "Hold out for N turns" better than the
    -- hardcoded 5 when the mission actually runs for a different length.
    -- API reference: scripts/missions/missions.lua
    --   Mission:IsFinalTurn() → Game:GetTurnCount() == self.TurnLimit - 1
    --   Mission:GetSpawnCount() returns 0 on final turn (no reinforcements)
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if mission then
            if mission.TurnLimit ~= nil then
                state.total_turns = mission.TurnLimit
            end
            if mission.IsFinalTurn and mission:IsFinalTurn() then
                state.remaining_spawns = 0
            else
                -- Not final: set a positive sentinel so future_factor uses
                -- the normal turn-based decay instead of collapsing to 0.
                state.remaining_spawns = 1
            end
        end
    end)

    -- Island map: per-region mission preview for the squad-aware mission
    -- picker. The currently-selected island's mission slate lives at the
    -- global `GAME.Missions` (see scripts/islands.lua createIncidents:319 —
    -- "GAME.Missions = incidents"). Each entry is a Mission object with:
    --   .ID         -- "Mission_Train", "Mission_Volatile", etc.
    --   .BonusObjs  -- list of int enums (1-9). See missions.lua:32-40 —
    --                 BONUS_ASSET=1 BONUS_KILL=2 BONUS_GRID=3 BONUS_MECHS=4
    --                 BONUS_BLOCK=5 BONUS_KILL_FIVE=6 BONUS_DEBRIS=7
    --                 BONUS_SELFDAMAGE=8 BONUS_PACIFIST=9
    --   .Environment -- "Env_Lava", "Env_TidalWaves", "Env_Conveyor",
    --                   "Env_Null", etc.
    --   .DiffMod    -- DIFF_MOD_EASY=-1, DIFF_MOD_NONE=0, DIFF_MOD_HARD=1
    --   .AssetId    -- e.g. "Mission_Mech_Boss" — only set for some missions
    -- GAME.Island holds the 1-based corp slot for the current island (set
    -- in createIncidents:191). Defensive: GAME and GAME.Missions may be
    -- nil during boot or non-island screens; pcall guards every read.
    --
    -- Emit only when we are NOT in an active mission (combat/deployment) —
    -- in combat, _ITB_CURRENT_MISSION is set and the slate is irrelevant.
    -- Outside combat the player is on the corp island map, between-mission
    -- transition, or shop; the bridge phase will read "unknown" and the
    -- picker can score the available missions.
    state.island_map = nil
    state.island_map_debug = nil
    -- Unconditional reachability probe: if state.island_map_probe shows up
    -- in the JSON but state.island_map does not, we know the pcall block is
    -- the failure point (not the surrounding scope or write_atomic).
    state.island_map_probe = "scope_alive"
    -- Resolve GAME via _G first, fall back to bare global. Both should work
    -- given Lua's scoping rules, but we record which path succeeded so a
    -- failed lookup can be told apart from a missing-Missions case.
    local _game_ref = rawget(_G, "GAME")
    if _game_ref == nil then
        _game_ref = GAME  -- bare-global fallback (ITB's own scope convention)
    end
    state.island_map_game_seen = (_game_ref ~= nil) and type(_game_ref) or "nil"
    local ok_island_map, err_island_map = pcall(function()
        if _ITB_CURRENT_MISSION ~= nil then
            state.island_map_debug = "skipped: in active mission"
            return  -- in active mission; slate is not the right answer
        end
        if not _game_ref or type(_game_ref) ~= "table" then
            state.island_map_debug = "GAME is " .. tostring(_game_ref)
            return
        end
        local missions = _game_ref.Missions
        if type(missions) ~= "table" then
            state.island_map_debug = "GAME.Missions is " .. type(missions) ..
                " (value=" .. tostring(missions) .. ")"
            return
        end
        local out = {}
        -- GAME.Missions is 1-indexed for regular missions; key 0 is the
        -- boss/final mission when present. Walk both 0 and 1..N.
        local indices = {}
        local n_keys = 0
        for k, _ in pairs(missions) do
            n_keys = n_keys + 1
            if type(k) == "number" then
                indices[#indices + 1] = k
            end
        end
        table.sort(indices)
        for _, k in ipairs(indices) do
            local m = missions[k]
            if type(m) == "table" then
                local entry = {
                    region_id = k,
                    mission_id = m.ID or "",
                }
                local bonus_ids = {}
                if type(m.BonusObjs) == "table" then
                    for _, b in ipairs(m.BonusObjs) do
                        if type(b) == "number" then
                            bonus_ids[#bonus_ids + 1] = b
                        end
                    end
                end
                entry.bonus_objective_ids = bonus_ids
                if type(m.Environment) == "string" and m.Environment ~= "" then
                    entry.environment = m.Environment
                else
                    entry.environment = nil
                end
                if type(m.DiffMod) == "number" then
                    entry.diff_mod = m.DiffMod
                end
                if type(m.AssetId) == "string" and m.AssetId ~= "" then
                    entry.asset_id = m.AssetId
                end
                if type(m.BossMission) == "boolean" then
                    entry.boss = m.BossMission
                end
                out[#out + 1] = entry
            end
        end
        state.island_map = out
        state.island_map_debug = "ok: " .. tostring(#out) .. " entries from " ..
            tostring(n_keys) .. " keys"
        if type(_game_ref.Island) == "number" then
            state.island_index = _game_ref.Island
        end
    end)
    if not ok_island_map then
        state.island_map_debug = "pcall error: " .. tostring(err_island_map)
    end

    write_atomic(STATE_FILE, STATE_TMP, json_encode(state))
end

--------------------------------------------------------------------
-- Bridge configuration
--------------------------------------------------------------------
local _bridge_speed = "fast"  -- "fast" or "visual"

--------------------------------------------------------------------
-- Animation/effect handling
--------------------------------------------------------------------
-- Commands run inside a coroutine created by poll_commands() so that
-- wait_for_board_coro / wait_until_coro can yield control back to the
-- engine while the effect queue drains. The OLD wait_for_board() was a
-- tight os.clock() spin inside the same Lua thread as Mission:BaseUpdate
-- — the engine could never advance the animation queue while Lua was
-- spinning, so Board:IsBusy() stayed true until the 15 s timeout fired.
-- Yielding lets BaseUpdate return, the engine advance, and the next
-- BaseUpdate tick resume the coroutine with a fresh Board state.

local _running_coroutine = nil

local function bridge_fast_mode()
    return _bridge_speed == "fast"
end

-- NOTE: os.time() (wall clock, second precision) rather than os.clock()
-- (process CPU time). When the coroutine yields back to the engine, CPU
-- time barely advances relative to wall time, so an os.clock()-based
-- deadline stretches out to ~3x its nominal wall-clock length. Python's
-- wait_for_ack uses wall clock, so the two must agree.
local function wait_until_coro(predicate, max_wait)
    max_wait = max_wait or 15
    local start = os.time()
    while os.time() - start < max_wait do
        local ok, ready = pcall(predicate)
        if not ok or ready then return true end
        coroutine.yield()
    end
    log_bridge("WARN: wait_until_coro timed out after " .. max_wait .. "s (wall)")
    return false
end

local function wait_for_board_coro(max_wait)
    if bridge_fast_mode() then
        max_wait = math.min(max_wait or 15, 2)
    end
    return wait_until_coro(function()
        return not Board:IsBusy()
    end, max_wait)
end

local function move_pawn_for_bridge(pawn, point)
    if bridge_fast_mode() then
        local ok, err = pcall(function() pawn:SetSpace(point) end)
        if ok then return true, "SetSpace" end
        return false, err
    end
    local ok, err = pcall(function() pawn:Move(point) end)
    if ok then return true, "Move" end
    return false, err
end

--------------------------------------------------------------------
-- Weapon skill execution
--------------------------------------------------------------------
-- Previous versions of this helper called
--   Board:AddEffect(skill:GetSkillEffect(source, target))
-- which fires the SkillEffect outside any pawn ownership context and
-- leaves the engine's effect queue in a permanently-busy state
-- (Board:IsBusy() stays true forever). Vanilla ITB — including the
-- game's own trailer script — exclusively uses `pawn:FireWeapon(target,
-- slot)` to invoke a weapon: that C-side method handles ownership,
-- animation scheduling and queue drain the way the engine expects.
-- Slot is 1-indexed into the pawn type's SkillList; see the weapon
-- extraction loop in dump_state() where SkillList is read in the same
-- order.
-- find_weapon_slot: name-based lookup kept for backward compat / diagnostics
local function find_weapon_slot(pawn, weapon_id)
    local ptype = pawn:GetType()
    local pawn_def = _G[ptype]
    if not (pawn_def and pawn_def.SkillList) then return nil end
    for i, wname in ipairs(pawn_def.SkillList) do
        if wname == weapon_id then return i end
    end
    return nil
end

local function effective_weapon_from_save(save_data, uid, weapon_slot, fallback)
    if not save_data then return fallback, "static" end
    local weapons = save_data.current_weapons or {}
    local idx = nil
    -- GameData.current.weapons stores two loadout slots per player mech, keyed
    -- by the stable player mech ids 0,1,2. Do not use pawn["offset"] here:
    -- live combat saves can stamp every squad mech with the same value (for
    -- example 5), which is a board/undo offset rather than a loadout offset.
    if type(uid) == "number" and uid >= 0 and uid <= 2 then
        idx = uid * 2 + weapon_slot + 1
    end
    local wname = idx and weapons[idx] or nil
    if type(wname) == "string" and wname ~= "" then
        if _G[wname] ~= nil then
            return wname, "save"
        end
        log_bridge("WARN: save weapon " .. wname ..
                   " for uid=" .. tostring(uid) ..
                   " slot=" .. tostring(weapon_slot) ..
                   " has no Lua skill; falling back to " .. tostring(fallback))
    end
    return fallback, "static"
end

local function tile_damage_snapshot(pt)
    local snap = {}
    local ok_t, terrain_id = pcall(function() return Board:GetTerrain(pt) end)
    if ok_t then snap.terrain_id = terrain_id end
    local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
    if ok_h then snap.health = hp end
    local ok_cr, cracked = pcall(function() return Board:IsCracked(pt) end)
    if ok_cr then snap.cracked = cracked and true or false end
    return snap
end

local function tile_damage_changed(before, pt)
    if before == nil then return false end
    local ok_t, terrain_id = pcall(function() return Board:GetTerrain(pt) end)
    if ok_t and before.terrain_id ~= nil and terrain_id ~= before.terrain_id then
        return true
    end
    local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
    if ok_h and before.health ~= nil and hp ~= before.health then
        return true
    end
    local ok_cr, cracked = pcall(function() return Board:IsCracked(pt) end)
    if ok_cr and before.cracked ~= nil and (cracked and true or false) ~= before.cracked then
        return true
    end
    return false
end

local function path_profile_for_target_area(point, fallback)
    if Pawn ~= nil then
        local ok, prof = pcall(function() return Pawn:GetPathProf() end)
        if ok and prof ~= nil then return prof end
    end
    if Board ~= nil and point ~= nil then
        local ok_pawn, source_pawn = pcall(function()
            return Board:GetPawn(point)
        end)
        if ok_pawn and source_pawn ~= nil then
            local ok_prof, prof = pcall(function()
                return source_pawn:GetPathProf()
            end)
            if ok_prof and prof ~= nil then return prof end
        end
    end
    return fallback or PATH_FLYER or PATH_PROJECTILE
end

local function bridge_safe_jet_target_area(self, point)
    local ret = PointList()
    local path_prof = path_profile_for_target_area(point, PATH_FLYER)
    for i = DIR_START, DIR_END do
        for k = self.MinMove, self.Range do
            local curr = DIR_VECTORS[i] * k + point
            if not Board:IsBlocked(curr, path_prof) then
                ret:push_back(curr)
            end
        end
    end
    return ret
end

local function bridge_safe_leap_target_area(self, point)
    local ret = PointList()
    local path_prof = path_profile_for_target_area(point, PATH_FLYER)
    local range = self.Range or 1
    for i = DIR_START, DIR_END do
        for k = 1, range do
            local curr = DIR_VECTORS[i] * k + point
            if Board:IsValid(curr) and not Board:IsBlocked(curr, path_prof) then
                ret:push_back(curr)
            end
        end
    end
    return ret
end

local function install_safe_jet_target_area()
    if _ITB_BRIDGE_SAFE_JET_TARGET_AREA then return end
    local names = {
        "Brute_Jetmech",
        "Brute_Jetmech_A",
        "Brute_Jetmech_B",
        "Brute_Jetmech_AB",
        "Brute_Bombrun",
        "Brute_Bombrun_A",
        "Brute_Bombrun_B",
        "Brute_Bombrun_AB",
        "Support_Smoke",
        "Support_Smoke_A",
        "Support_Smoke_B",
        "Support_Smoke_AB",
    }
    local installed = 0
    for _, name in ipairs(names) do
        local skill = _G[name]
        if skill ~= nil then
            skill.GetTargetArea = bridge_safe_jet_target_area
            installed = installed + 1
        end
    end
    _ITB_BRIDGE_SAFE_JET_TARGET_AREA = true
    log_bridge("SAFE TARGET AREA: patched Aerial Bombs family entries=" ..
               installed)
end

local function install_safe_leap_target_area()
    if _ITB_BRIDGE_SAFE_LEAP_TARGET_AREA then return end
    local names = {
        "Prime_Leap",
        "Prime_Leap_A",
        "Prime_Leap_B",
        "Prime_Leap_AB",
        "Support_Boosters",
        "Support_Boosters_A",
        "Support_Boosters_B",
        "Support_Boosters_AB",
        "Prime_SpikeLeap",
        "Prime_SpikeLeap_A",
        "Prime_SpikeLeap_B",
        "Prime_SpikeLeap_AB",
    }
    local installed = 0
    for _, name in ipairs(names) do
        local skill = _G[name]
        if skill ~= nil then
            skill.GetTargetArea = bridge_safe_leap_target_area
            installed = installed + 1
        end
    end
    _ITB_BRIDGE_SAFE_LEAP_TARGET_AREA = true
    log_bridge("SAFE TARGET AREA: patched Leap_Attack family entries=" ..
               installed)
end

local function execute_prime_tc_punt(pawn, wname, tx, ty)
    local skill = _G[wname]
    if not skill then
        return false, "Prime_TC_Punt skill missing: " .. tostring(wname)
    end

    local source = pawn:GetSpace()
    local dx = tx - source.x
    local dy = ty - source.y
    local dist = math.abs(dx) + math.abs(dy)
    if dist < 2 or (dx ~= 0 and dy ~= 0) then
        return false, "invalid Prime_TC_Punt landing " .. tx .. "," .. ty ..
               " from " .. source.x .. "," .. source.y
    end

    local sx = dx == 0 and 0 or (dx / math.abs(dx))
    local sy = dy == 0 and 0 or (dy / math.abs(dy))
    local first = Point(source.x + sx, source.y + sy)
    local landing = Point(tx, ty)

    if not Board:IsValid(landing) then
        return false, "Prime_TC_Punt landing off-board " .. tx .. "," .. ty
    end
    if Board:IsBlocked(landing, PATH_FLYER) then
        return false, "Prime_TC_Punt landing blocked " .. tx .. "," .. ty
    end

    local target = Board:GetPawn(first)
    if not target then
        return false, "Prime_TC_Punt first click has no pawn at " ..
               first.x .. "," .. first.y
    end
    local guarding = false
    local ok_guard, guard_val = pcall(function() return target:IsGuarding() end)
    if ok_guard and guard_val then guarding = true end
    if guarding then
        return false, "Prime_TC_Punt target is guarding at " ..
               first.x .. "," .. first.y
    end

    local uid = nil
    local ok_uid, uid_val = pcall(function() return pawn:GetId() end)
    if ok_uid then uid = uid_val end
    local save_data = _read_save_data()
    local save_pilot = uid and save_data.pilots[uid] or nil
    local boosted = false
    local ok_bo, bo = pcall(function() return pawn:IsBoosted() end)
    if ok_bo and bo then boosted = true end
    local target_was_enemy = false
    local ok_team, target_team = pcall(function() return target:GetTeam() end)
    if ok_team and target_team == (_G.TEAM_ENEMY or 6) then
        target_was_enemy = true
    end

    -- Board:AddEffect(GetFinalEffect(...)) bypasses the engine ability-use
    -- wrapper that normally applies and consumes Boost. Mirror that wrapper
    -- here so the bridge execution matches the solver's weapon semantics.
    local old_damage = nil
    if boosted and type(skill.Damage) == "number" and skill.Damage > 0 then
        old_damage = skill.Damage
        skill.Damage = old_damage + 1
    end
    local ok, err = pcall(function()
        Board:AddEffect(skill:GetFinalEffect(source, first, landing))
    end)
    if old_damage ~= nil then
        pcall(function() skill.Damage = old_damage end)
    end
    if not ok then
        return false, "Prime_TC_Punt GetFinalEffect failed: " .. tostring(err)
    end

    local desired_boosted = false
    if save_pilot and save_pilot.id == "Pilot_Arrogant" then
        local hp = pawn:GetHealth()
        local max_hp = get_pawn_max_health(pawn, uid, save_data)
        desired_boosted = hp >= max_hp
    elseif save_pilot and save_pilot.id == "Pilot_Chemical" and target_was_enemy then
        local dead = false
        local ok_dead, is_dead = pcall(function() return target:IsDead() end)
        if ok_dead and is_dead then dead = true end
        local ok_hp, hp = pcall(function() return target:GetHealth() end)
        if ok_hp and hp <= 0 then dead = true end
        desired_boosted = dead
    end
    if boosted or desired_boosted then
        for _, mname in ipairs({"SetBoosted", "SetBoost"}) do
            local ok_set, did_set = pcall(function()
                local fn = pawn[mname]
                if type(fn) == "function" then
                    fn(pawn, desired_boosted)
                    return true
                end
                return false
            end)
            if ok_set and did_set then break end
        end
    end
    log_bridge("FIRE: " .. wname .. " two_click " ..
               source.x .. "," .. source.y .. " -> " ..
               first.x .. "," .. first.y .. " -> " .. tx .. "," .. ty)
    return true, "GetFinalEffect(" .. wname .. ") first=" ..
           first.x .. "," .. first.y .. " landing=" .. tx .. "," .. ty
end

local function effective_weapon_name_by_slot(pawn, weapon_slot)
    local slot = weapon_slot + 1
    local ptype = pawn:GetType()
    local pawn_def = _G[ptype]
    if not (pawn_def and pawn_def.SkillList) then
        return nil, nil, nil, "weapon slot " .. weapon_slot ..
               " unavailable (pawn " .. ptype .. " has no SkillList)"
    end

    local uid = nil
    local ok_uid, uid_val = pcall(function() return pawn:GetId() end)
    if ok_uid then uid = uid_val end
    local base_wname = pawn_def.SkillList[slot]
    local save_data = _read_save_data()
    local wname, wsource =
        effective_weapon_from_save(save_data, uid, weapon_slot, base_wname)
    if wname == nil then
        return nil, nil, nil, "weapon slot " .. weapon_slot ..
               " out of range (pawn " .. ptype .. " has " ..
               tostring(#pawn_def.SkillList) ..
               " static skills and no save-backed weapon)"
    end
    return wname, base_wname, slot, nil, wsource, pawn_def, uid
end

local function pawn_is_guarding(pawn)
    local ok_guard, guard_val = pcall(function() return pawn:IsGuarding() end)
    return ok_guard and guard_val
end

local function pawn_is_boosted(pawn)
    local ok_bo, boosted = pcall(function() return pawn:IsBoosted() end)
    return ok_bo and boosted
end

local function set_pawn_boosted(pawn, desired)
    for _, mname in ipairs({"SetBoosted", "SetBoost"}) do
        local ok_set, did_set = pcall(function()
            local fn = pawn[mname]
            if type(fn) == "function" then
                fn(pawn, desired)
                return true
            end
            return false
        end)
        if ok_set and did_set then return true end
    end
    return false
end

local function pawn_is_enemy(pawn)
    if pawn == nil then return false end
    local ok_team, team = pcall(function() return pawn:GetTeam() end)
    return ok_team and team == (_G.TEAM_ENEMY or 6)
end

local function pawn_is_dead_or_zero(pawn)
    if pawn == nil then return false end
    local ok_dead, dead = pcall(function() return pawn:IsDead() end)
    if ok_dead and dead then return true end
    local ok_hp, hp = pcall(function() return pawn:GetHealth() end)
    return ok_hp and hp <= 0
end

local function get_projectile_end_safe(source, target)
    local ok, final = pcall(function()
        return GetProjectileEnd(source, target, PATH_PROJECTILE)
    end)
    if ok and final ~= nil then return final end
    return target
end

local function execute_ricochet_native(pawn, wname, skill, first, second)
    local source = pawn:GetSpace()
    local first_dir = GetDirection(first - source)
    local first_tar = get_projectile_end_safe(source, first)
    local second_dir = GetDirection(second - first)
    local second_tar = get_projectile_end_safe(first, second)
    local damage = tonumber(skill.Damage) or 1
    local boosted = pawn_is_boosted(pawn)
    if boosted and damage > 0 then
        damage = damage + 1
    end

    local uid = nil
    local ok_uid, uid_val = pcall(function() return pawn:GetId() end)
    if ok_uid then uid = uid_val end
    local save_data = _read_save_data()
    local save_pilot = uid and save_data.pilots[uid] or nil

    local targets = {
        {point = second_tar, dir = second_dir},
        {point = first_tar, dir = first_dir},
    }
    local killed_enemy = false
    for _, entry in ipairs(targets) do
        local pt = entry.point
        if Board:IsValid(pt) then
            local target_pawn = Board:GetPawn(pt)
            local target_was_enemy = pawn_is_enemy(target_pawn)
            local dmg = damage
            if not skill.AllyDamage and Board:IsPawnTeam(pt, TEAM_PLAYER) then
                dmg = DAMAGE_ZERO
            end
            local sd = SpaceDamage(pt, dmg, entry.dir)
            local ok_dmg, err_dmg = pcall(function() Board:DamageSpace(sd) end)
            if not ok_dmg then
                return false, "Ricochet DamageSpace failed at " ..
                       pt.x .. "," .. pt.y .. ": " .. tostring(err_dmg)
            end
            if target_was_enemy and pawn_is_dead_or_zero(target_pawn) then
                killed_enemy = true
            end
        end
    end

    if boosted or killed_enemy then
        local desired_boosted = false
        if save_pilot and save_pilot.id == "Pilot_Arrogant" then
            local hp = pawn:GetHealth()
            local max_hp = get_pawn_max_health(pawn, uid, save_data)
            desired_boosted = hp >= max_hp
        elseif save_pilot and save_pilot.id == "Pilot_Chemical" and killed_enemy then
            desired_boosted = true
        end
        set_pawn_boosted(pawn, desired_boosted)
    end

    log_bridge("FIRE: " .. wname .. " direct_ricochet " ..
               source.x .. "," .. source.y .. " -> " ..
               first.x .. "," .. first.y .. " -> " ..
               second.x .. "," .. second.y)
    return true, "DamageSpace(" .. wname .. ") first=" ..
           first_tar.x .. "," .. first_tar.y .. " second=" ..
           second_tar.x .. "," .. second_tar.y
end

local function execute_quick_fire_native(pawn, wname, skill, first, second)
    local source = pawn:GetSpace()
    local first_dir = GetDirection(first - source)
    local second_dir = GetDirection(second - source)
    local first_tar = get_projectile_end_safe(source, first)
    local second_tar = get_projectile_end_safe(source, second)
    local damage = tonumber(skill.Damage) or 1
    local boosted = pawn_is_boosted(pawn)
    if boosted and damage > 0 then
        damage = damage + 1
    end

    local uid = nil
    local ok_uid, uid_val = pcall(function() return pawn:GetId() end)
    if ok_uid then uid = uid_val end
    local save_data = _read_save_data()
    local save_pilot = uid and save_data.pilots[uid] or nil

    local killed_enemy = false
    local targets = {
        {point = first_tar, dir = first_dir},
        {point = second_tar, dir = second_dir},
    }
    for _, entry in ipairs(targets) do
        local pt = entry.point
        if Board:IsValid(pt) then
            local target_pawn = Board:GetPawn(pt)
            local target_was_enemy = pawn_is_enemy(target_pawn)
            local sd = SpaceDamage(pt, damage)
            if tonumber(skill.Push) == 1 then
                sd.iPush = entry.dir
            end
            local ok_dmg, err_dmg = pcall(function() Board:DamageSpace(sd) end)
            if not ok_dmg then
                return false, "Quick-Fire DamageSpace failed at " ..
                       pt.x .. "," .. pt.y .. ": " .. tostring(err_dmg)
            end
            if target_was_enemy and pawn_is_dead_or_zero(target_pawn) then
                killed_enemy = true
            end
        end
    end

    if boosted or killed_enemy then
        local desired_boosted = false
        if save_pilot and save_pilot.id == "Pilot_Arrogant" then
            local hp = pawn:GetHealth()
            local max_hp = get_pawn_max_health(pawn, uid, save_data)
            desired_boosted = hp >= max_hp
        elseif save_pilot and save_pilot.id == "Pilot_Chemical" and killed_enemy then
            desired_boosted = true
        end
        set_pawn_boosted(pawn, desired_boosted)
    end

    log_bridge("FIRE: " .. wname .. " direct_quick_fire " ..
               source.x .. "," .. source.y .. " -> " ..
               first.x .. "," .. first.y .. " -> " ..
               second.x .. "," .. second.y)
    return true, "DamageSpace(" .. wname .. ") first=" ..
           first_tar.x .. "," .. first_tar.y .. " second=" ..
           second_tar.x .. "," .. second_tar.y
end

local function execute_two_click_by_slot(pawn, weapon_slot, tx1, ty1, tx2, ty2)
    local wname, _base_wname, slot, err =
        effective_weapon_name_by_slot(pawn, weapon_slot)
    if err ~= nil then
        return false, err
    end
    local skill = _G[wname]
    if not skill then
        return false, "two-click skill missing: " .. tostring(wname)
    end

    local source = pawn:GetSpace()
    local first = Point(tx1, ty1)
    local second = Point(tx2, ty2)
    if not Board:IsValid(first) or not Board:IsValid(second) then
        return false, "two-click target off-board"
    end

    if string.find(wname, "^Brute_TC_DoubleShot") ~= nil then
        local function shot_dir(point)
            local dx = point.x - source.x
            local dy = point.y - source.y
            if dx == 0 and dy > 0 then return 0 end
            if dx > 0 and dy == 0 then return 1 end
            if dx == 0 and dy < 0 then return 2 end
            if dx < 0 and dy == 0 then return 3 end
            return nil
        end
        local first_dir = shot_dir(first)
        local second_dir = shot_dir(second)
        if first_dir == nil then
            return false, "Quick-Fire first target not cardinal " ..
                   first.x .. "," .. first.y .. " from " ..
                   source.x .. "," .. source.y
        end
        if second_dir == nil then
            return false, "Quick-Fire second target not cardinal " ..
                   second.x .. "," .. second.y .. " from " ..
                   source.x .. "," .. source.y
        end
        if first_dir == second_dir then
            return false, "Quick-Fire targets must be in different directions"
        end
        return execute_quick_fire_native(pawn, wname, skill, first, second)
    end

    if string.find(wname, "^Brute_TC_Ricochet") ~= nil then
        if first.x == source.x and first.y == source.y then
            return false, "Ricochet first target is source"
        end
        if first.x ~= source.x and first.y ~= source.y then
            return false, "Ricochet first target not cardinal " ..
                   first.x .. "," .. first.y .. " from " ..
                   source.x .. "," .. source.y
        end
        local first_effect = first
        local ok_translate, translated = pcall(function()
            if type(skill.TranslateFirstClick) == "function" then
                return skill:TranslateFirstClick(source, first)
            end
            return nil
        end)
        if ok_translate and translated ~= nil then
            first_effect = translated
        end
        if second.x ~= first_effect.x and second.y ~= first_effect.y then
            return false, "Ricochet second target not cardinal " ..
                   second.x .. "," .. second.y .. " from " ..
                   first_effect.x .. "," .. first_effect.y
        end
        return execute_ricochet_native(pawn, wname, skill, first, second)
    end

    if string.find(wname, "^Science_TC_Control") ~= nil then
        local target_pawn = Board:GetPawn(first)
        if not target_pawn then
            return false, "Control Shot first click has no pawn at " ..
                   first.x .. "," .. first.y
        end
        local ok_first, first_targets = pcall(function()
            return skill:GetTargetArea(source)
        end)
        if not ok_first then
            return false, "Control Shot GetTargetArea failed: " .. tostring(first_targets)
        end
        if not point_list_contains(first_targets, first) then
            return false, "Control Shot first click is not natively eligible at " ..
                   first.x .. "," .. first.y
        end
        local ok_second, second_targets = pcall(function()
            return skill:GetSecondTargetArea(source, first)
        end)
        if not ok_second then
            return false, "Control Shot GetSecondTargetArea failed: " .. tostring(second_targets)
        end
        if not point_list_contains(second_targets, second) then
            return false, "Control Shot second click is not natively reachable at " ..
                   second.x .. "," .. second.y
        end
        local ok, ctrl_err = pcall(function()
            Board:AddEffect(skill:GetFinalEffect(source, first, second))
        end)
        if not ok then
            return false, "Control Shot GetFinalEffect failed: " .. tostring(ctrl_err)
        end
        log_bridge("FIRE: " .. wname .. " control_shot slot=" .. slot .. " " ..
                   source.x .. "," .. source.y .. " -> " ..
                   first.x .. "," .. first.y .. " -> " ..
                   second.x .. "," .. second.y)
        return true, "GetFinalEffect(" .. wname .. ") first=" ..
               first.x .. "," .. first.y .. " second=" ..
               second.x .. "," .. second.y
    end

    if wname == "Ranged_DeployBomb_A" then
        local function deploy_dir(point)
            local dx = point.x - source.x
            local dy = point.y - source.y
            if dx == 0 and dy > 0 then return 0 end
            if dx > 0 and dy == 0 then return 1 end
            if dx == 0 and dy < 0 then return 2 end
            if dx < 0 and dy == 0 then return 3 end
            return nil
        end
        local function deploy_dist(point)
            return math.abs(point.x - source.x) + math.abs(point.y - source.y)
        end

        local first_dir = deploy_dir(first)
        local second_dir = deploy_dir(second)
        if first_dir == nil then
            return false, "2 Bombs first target not cardinal " ..
                   first.x .. "," .. first.y .. " from " ..
                   source.x .. "," .. source.y
        end
        if second_dir == nil then
            return false, "2 Bombs second target not cardinal " ..
                   second.x .. "," .. second.y .. " from " ..
                   source.x .. "," .. source.y
        end
        if deploy_dist(first) < 2 then
            return false, "2 Bombs first target below min range " ..
                   first.x .. "," .. first.y
        end
        if deploy_dist(second) < 2 then
            return false, "2 Bombs second target below min range " ..
                   second.x .. "," .. second.y
        end
        if first_dir == second_dir then
            return false, "2 Bombs targets must be in different directions"
        end
        if Board:IsBlocked(first, PATH_GROUND) then
            return false, "2 Bombs first target blocked " ..
                   first.x .. "," .. first.y
        end
        if Board:IsBlocked(second, PATH_GROUND) then
            return false, "2 Bombs second target blocked " ..
                   second.x .. "," .. second.y
        end

        local ok, bomb_err = pcall(function()
            Board:AddEffect(skill:GetFinalEffect(source, first, second))
        end)
        if not ok then
            return false, "2 Bombs GetFinalEffect failed: " .. tostring(bomb_err)
        end
        log_bridge("FIRE: " .. wname .. " two_bombs slot=" .. slot .. " " ..
                   source.x .. "," .. source.y .. " -> " ..
                   first.x .. "," .. first.y .. " -> " ..
                   second.x .. "," .. second.y)
        return true, "GetFinalEffect(" .. wname .. ") first=" ..
               first.x .. "," .. first.y .. " second=" ..
               second.x .. "," .. second.y
    end

    if string.find(wname, "^Science_TC_SwapOther") == nil then
        return false, "unsupported two-click weapon " .. tostring(wname)
    end
    local dist = math.abs(first.x - source.x) + math.abs(first.y - source.y)
    if dist ~= 1 then
        return false, "Force Swap first target not adjacent " ..
               first.x .. "," .. first.y .. " from " ..
               source.x .. "," .. source.y
    end
    local first_pawn = Board:GetPawn(first)
    local second_pawn = Board:GetPawn(second)
    if not first_pawn then
        return false, "Force Swap first click has no pawn at " ..
               first.x .. "," .. first.y
    end
    if not second_pawn then
        return false, "Force Swap second click has no pawn at " ..
               second.x .. "," .. second.y
    end
    if first.x == second.x and first.y == second.y then
        return false, "Force Swap targets must be different"
    end
    if pawn_is_guarding(first_pawn) or pawn_is_guarding(second_pawn) then
        return false, "Force Swap target is guarding/stable"
    end

    local ok, fx_err = pcall(function()
        Board:AddEffect(skill:GetFinalEffect(source, first, second))
    end)
    if not ok then
        return false, "Force Swap GetFinalEffect failed: " .. tostring(fx_err)
    end
    log_bridge("FIRE: " .. wname .. " two_click slot=" .. slot .. " " ..
               source.x .. "," .. source.y .. " -> " ..
               first.x .. "," .. first.y .. " -> " ..
               second.x .. "," .. second.y)
    return true, "GetFinalEffect(" .. wname .. ") first=" ..
           first.x .. "," .. first.y .. " second=" ..
           second.x .. "," .. second.y
end

-- execute_weapon_by_slot: fire weapon using a 0-based slot index from
-- the Python side (maps to 1-indexed Lua SkillList).
-- This avoids name-matching issues where the solver's weapon ID doesn't
-- match the pawn type's SkillList entry (e.g. purchased / upgraded weapons,
-- or names the Rust solver doesn't recognise → "Unknown").
local function execute_weapon_by_slot(pawn, weapon_slot, tx, ty)
    -- weapon_slot is 0-based from Python; Lua SkillList is 1-indexed
    local wname, base_wname, slot, err, wsource, pawn_def, uid =
        effective_weapon_name_by_slot(pawn, weapon_slot)
    if err ~= nil then
        return false, err
    end
    local restore_skill_list = false
    if wname ~= base_wname then
        restore_skill_list = true
        pawn_def.SkillList[slot] = wname
        log_bridge("EFFECTIVE_WEAPON: uid=" .. tostring(uid) ..
                   " slot=" .. slot .. " " .. tostring(base_wname) ..
                   " -> " .. tostring(wname) .. " source=" .. tostring(wsource))
    end
    local source = pawn:GetSpace()
    -- pawn:FireWeapon() applies Seismic Capacitor's damage through the file
    -- bridge, but some engine builds omit its DIR_FLIP retarget side effect.
    -- Snapshot a live queued enemy now so we can add only the missing flip
    -- after FireWeapon returns.  GetQueuedShot is the same C++ live probe used
    -- by state extraction to override save-stale piQueuedShot values.
    local seismic_flip_before = nil
    if string.find(wname, "^Science_KO_Crack") ~= nil then
        local target = Board:GetPawn(Point(tx, ty))
        if target ~= nil and not target:IsDead() and target:GetTeam() == TEAM_ENEMY then
            local ok_id, target_id = pcall(function() return target:GetId() end)
            local ok_qs, queued = pcall(function() return target:GetQueuedShot() end)
            if ok_id and ok_qs and queued ~= nil
                    and type(queued.x) == "number" and type(queued.y) == "number"
                    and queued.x >= 0 and queued.y >= 0
                    and queued.x <= 7 and queued.y <= 7 then
                seismic_flip_before = {
                    id = target_id,
                    x = queued.x,
                    y = queued.y,
                }
            end
        end
    end
    if string.find(wname, "^Prime_TC_Punt") ~= nil then
        local ok_punt, method = execute_prime_tc_punt(pawn, wname, tx, ty)
        if restore_skill_list then
            pawn_def.SkillList[slot] = base_wname
        end
        if not ok_punt then
            log_bridge("WARN: Prime_TC_Punt failed for slot " .. slot ..
                       " (" .. tostring(wname) .. "): " .. tostring(method))
            return false, method
        end
        return true, method
    end

    local is_transit_leap =
        string.find(wname, "^Brute_Jetmech") ~= nil or
        string.find(wname, "^Brute_Bombrun") ~= nil
    local skill = is_transit_leap and _G[wname] or nil
    local transit_before = nil
    if skill and skill.Damage and skill.Damage > 0 then
        local dx = tx - source.x
        local dy = ty - source.y
        local dist = math.abs(dx) + math.abs(dy)
        if dist >= 2 and (dx == 0 or dy == 0) then
            local sx = dx == 0 and 0 or (dx / math.abs(dx))
            local sy = dy == 0 and 0 or (dy / math.abs(dy))
            transit_before = {sx = sx, sy = sy, dist = dist, tiles = {}}
            for k = 1, dist - 1 do
                local tp = Point(source.x + sx * k, source.y + sy * k)
                transit_before.tiles[k] = tile_damage_snapshot(tp)
            end
        end
    end
    local ok, fired_or_err = pcall(function()
        return pawn:FireWeapon(Point(tx, ty), slot)
    end)
    if restore_skill_list then
        pawn_def.SkillList[slot] = base_wname
    end
    if not ok then
        log_bridge("WARN: FireWeapon failed for slot " .. slot ..
                   " (" .. wname .. "): " .. tostring(fired_or_err))
        return false, "FireWeapon failed: " .. tostring(fired_or_err)
    end
    if fired_or_err == false then
        log_bridge("WARN: FireWeapon returned false for slot " .. slot ..
                   " (" .. wname .. ")")
        return false, "FireWeapon returned false for slot " .. tostring(slot) ..
               " (" .. tostring(wname) .. ")"
    end
    log_bridge("FIRE: " .. wname .. " slot=" .. slot .. " " ..
               source.x .. "," .. source.y .. " -> " .. tx .. "," .. ty)

    if seismic_flip_before ~= nil then
        local target = Board:GetPawn(Point(tx, ty))
        local same_target = false
        if target ~= nil and not target:IsDead() and target:GetTeam() == TEAM_ENEMY then
            local ok_id, target_id = pcall(function() return target:GetId() end)
            same_target = ok_id and target_id == seismic_flip_before.id
        end
        if same_target then
            local ok_qs, queued = pcall(function() return target:GetQueuedShot() end)
            local unchanged = ok_qs and queued ~= nil
                and queued.x == seismic_flip_before.x
                and queued.y == seismic_flip_before.y
            if unchanged then
                local flip = SpaceDamage(Point(tx, ty), 0)
                flip.iPush = DIR_FLIP
                local ok_flip, flip_err = pcall(function()
                    Board:DamageSpace(flip)
                end)
                if ok_flip then
                    log_bridge(string.format(
                        "SEISMIC_FLIP_FALLBACK: uid=%s queued=(%d,%d)",
                        tostring(seismic_flip_before.id),
                        seismic_flip_before.x, seismic_flip_before.y))
                else
                    log_bridge("WARN: Seismic DIR_FLIP fallback failed for uid=" ..
                               tostring(seismic_flip_before.id) .. ": " ..
                               tostring(flip_err))
                end
            else
                log_bridge("SEISMIC_FLIP_ENGINE: uid=" ..
                           tostring(seismic_flip_before.id))
            end
        end
    end

    -- Transit-damage workaround for Brute_Jetmech (Aerial Bombs) and
    -- Brute_Bombrun (Bombing Run). The game's weapons_brute.lua
    -- Brute_Jetmech:GetSkillEffect (and Brute_Bombrun which inherits
    -- from it) loops k=1..Range-1 and calls Board:DamageSpace with
    -- damage + iSmoke on each transit tile. pawn:FireWeapon() dispatches
    -- the leap movement but does NOT execute that Lua script —
    -- 5/5 snapshots (grid_drop_20260421_211617_239_t02_a0,
    -- _20260421_215501_106_t02_a0, _20260423_131700_144_t01_a0,
    -- _20260424_144237_364_t01_a1, plus t03_a0 in the 211617 run) show
    -- transit tiles at predicted HP-1 vs actual HP unchanged, and zero
    -- smoke tiles in all five actual boards. Replicate the game's own
    -- GetSkillEffect loop here, pulling skill.Damage / skill.Smoke off
    -- the live Lua skill so weapon upgrades (Jetmech_A Damage=2,
    -- Bombrun_B Damage=3) flow through automatically.
    --
    -- NOT using skill:GetSkillEffect + Board:AddEffect: the comment at
    -- the top of this section records that path leaves Board:IsBusy()
    -- stuck true and broke the engine queue.
    if is_transit_leap then
        skill = skill or _G[wname]
        if skill and skill.Damage and skill.Damage > 0 then
            local dx = tx - source.x
            local dy = ty - source.y
            local dist = math.abs(dx) + math.abs(dy)
            -- Cardinal-only (leap enumerator already guarantees this,
            -- but guard defensively).
            if dist >= 2 and (dx == 0 or dy == 0) then
                local sx = dx == 0 and 0 or (dx / math.abs(dx))
                local sy = dy == 0 and 0 or (dy / math.abs(dy))
                local dmg_applied = 0
                local smoke_applied = 0
                local engine_tile_damage_seen = 0
                for k = 1, dist - 1 do
                    local nx = source.x + sx * k
                    local ny = source.y + sy * k
                    local tp = Point(nx, ny)
                    -- FireWeapon DOES apply transit damage to any unit
                    -- standing on the transit tile (observed 2026-04-24
                    -- turn 1 and turn 2: acid-statused Firefly1 on
                    -- transit died after 1 of our manual + 1 of the
                    -- engine's damage, instead of surviving at HP=1).
                    -- Some engine paths do apply transit terrain damage
                    -- during FireWeapon, while older captures showed no
                    -- terrain damage. Snapshot-before / compare-after keeps
                    -- the workaround adaptive: apply synthetic damage only
                    -- when FireWeapon left the tile's terrain state unchanged,
                    -- and always apply smoke/acid via SpaceDamage.
                    local occupant = Board:GetPawn(tp)
                    local has_live = occupant ~= nil and not occupant:IsDead()
                    local before = nil
                    if transit_before and transit_before.tiles then
                        before = transit_before.tiles[k]
                    end
                    local engine_changed_tile = tile_damage_changed(before, tp)
                    if engine_changed_tile then
                        engine_tile_damage_seen = engine_tile_damage_seen + 1
                    end
                    local dmg_val = (has_live or engine_changed_tile) and 0 or skill.Damage
                    local smoke_val = skill.Smoke or 0
                    local acid_val = skill.Acid or 0
                    local used_direct_status = false
                    local ok_d = false
                    local err_d = nil
                    if dmg_val == 0 and has_live and smoke_val > 0 and acid_val == 0 then
                        -- Use a real SpaceDamage payload even for occupied
                        -- transit tiles. Direct Board:SetSmoke paints the
                        -- tile but can leave already-queued Vek attacks live;
                        -- DamageSpace(iSmoke) follows the weapon/status path
                        -- that attack cancellation code observes.
                        local sd = SpaceDamage(tp, 0)
                        sd.iSmoke = smoke_val
                        ok_d, err_d = pcall(function()
                            Board:DamageSpace(sd)
                        end)
                        used_direct_status = ok_d
                    end
                    if not used_direct_status then
                        local sd = SpaceDamage(tp, dmg_val)
                        if smoke_val > 0 then
                            sd.iSmoke = smoke_val
                        end
                        if acid_val > 0 then
                            sd.iAcid = acid_val
                        end
                        ok_d, err_d = pcall(function()
                            Board:DamageSpace(sd)
                        end)
                    end
                    if ok_d then
                        if dmg_val > 0 then dmg_applied = dmg_applied + 1 end
                        if smoke_val > 0 then
                            smoke_applied = smoke_applied + 1
                        end
                    else
                        log_bridge("WARN: transit DamageSpace failed at (" ..
                                   nx .. "," .. ny .. ") for " .. wname ..
                                   ": " .. tostring(err_d))
                    end
                end
                log_bridge("TRANSIT: " .. wname ..
                           " dmg_applied=" .. dmg_applied ..
                           " smoke_applied=" .. smoke_applied ..
                           " engine_tile_damage_seen=" .. engine_tile_damage_seen ..
                           " damage=" .. skill.Damage ..
                           " smoke=" .. tostring(skill.Smoke or 0))
            end
        end
    end

    return true, "FireWeapon[" .. slot .. "](" .. wname .. ")"
end

--------------------------------------------------------------------
-- Command executor
--------------------------------------------------------------------
local _cmd_seq = nil

local function write_ack(msg)
    local ack = msg
    if _cmd_seq then
        ack = "#" .. _cmd_seq .. " " .. msg
    end
    write_atomic(ACK_FILE, ACK_TMP, ack)
end

local function ui_probe_value(label, fn)
    local ok, value = pcall(fn)
    local out = {label = label, ok = ok and true or false}
    if ok then
        local vt = type(value)
        out.type = vt
        if vt == "boolean" or vt == "number" or vt == "string" then
            out.value = value
        elseif value == nil then
            out.value = nil
        else
            out.value = tostring(value)
        end
    else
        out.error = tostring(value)
    end
    return out
end

local function ui_probe_has_callable(obj, name)
    if obj == nil then return false end
    local ok, value = pcall(function() return obj[name] end)
    return ok and type(value) == "function"
end

local function ui_probe_methods(label, obj, names)
    local out = {}
    for _, name in ipairs(names) do
        out[#out + 1] = ui_probe_value(label .. "." .. name, function()
            if obj == nil then error(label .. " unavailable") end
            local fn = obj[name]
            if type(fn) ~= "function" then error(name .. " not callable") end
            return fn(obj)
        end)
    end
    return out
end

local function ui_probe_globals()
    local out = {}
    local global_names = {
        "Game", "Board", "Mission", "GameData", "sdlext", "modApi",
        "UiRoot", "Ui", "UI", "PauseMenu", "Pause_Menu", "Menu",
        "Screen", "ScreenManager", "GetGame", "GetCurrentMission",
    }
    for _, name in ipairs(global_names) do
        out[#out + 1] = ui_probe_value("_G." .. name, function()
            return _G[name]
        end)
    end
    return out
end

local function ui_probe_menu_state()
    local probes = {
        bridge_speed = _bridge_speed,
        timestamp = os.time(),
        globals = ui_probe_globals(),
        values = {},
        callable = {},
    }

    local method_names = {
        "IsPaused", "IsPause", "IsPauseMenu", "IsMenuOpen", "IsGamePaused",
        "IsCombatPaused", "IsRunning", "IsBusy", "GetState", "GetCurrentState",
        "GetTeamTurn", "GetTurnCount",
    }
    local objects = {
        {"Game", Game},
        {"Board", Board},
        {"Mission", Mission},
    }
    if GetGame ~= nil then
        local ok_game, game_ref = pcall(function() return GetGame() end)
        probes.values[#probes.values + 1] = {
            label = "GetGame()",
            ok = ok_game and true or false,
            type = ok_game and type(game_ref) or nil,
            value = ok_game and tostring(game_ref) or nil,
            error = ok_game and nil or tostring(game_ref),
        }
        if ok_game then
            objects[#objects + 1] = {"GetGame()", game_ref}
        end
    end

    for _, pair in ipairs(objects) do
        local label = pair[1]
        local obj = pair[2]
        local callable = {}
        for _, name in ipairs(method_names) do
            if ui_probe_has_callable(obj, name) then
                callable[#callable + 1] = name
            end
        end
        probes.callable[label] = callable
        local method_values = ui_probe_methods(label, obj, method_names)
        for _, entry in ipairs(method_values) do
            probes.values[#probes.values + 1] = entry
        end
    end

    local globals_as_functions = {
        "IsPaused", "IsPauseMenu", "IsMenuOpen", "IsGamePaused",
        "GetCurrentScreen", "GetCurrentMenu", "GetUiState",
    }
    for _, name in ipairs(globals_as_functions) do
        probes.values[#probes.values + 1] = ui_probe_value(name .. "()", function()
            local fn = _G[name]
            if type(fn) ~= "function" then error(name .. " not callable") end
            return fn()
        end)
    end

    return probes
end

-- Apply the bridge's direct Repair mutation to one pawn. The command-context
-- Skill_Repair effect can ACK without changing live state, so Repair Field
-- must reuse this exact path for every TEAM_MECH pawn instead of delegating
-- the group effect back to the unreliable native call.
local function direct_repair_pawn(target, target_uid, heal, save_data, effect_remove)
    local target_pos = target:GetSpace()
    local hp = target:GetHealth()
    local max_hp = get_pawn_max_health(target, target_uid, save_data)
    local new_hp = math.min(hp, max_hp - heal) + heal

    local hp_set = false
    local ok_set_health, did_set_health = pcall(function()
        local fn = target.SetHealth
        if type(fn) == "function" then
            fn(target, new_hp)
            return true
        end
        return false
    end)
    hp_set = ok_set_health and did_set_health

    local sd = SpaceDamage(target_pos, hp_set and 0 or -heal)
    sd.iFire = effect_remove
    sd.iAcid = effect_remove
    sd.iFrozen = effect_remove
    sd.iInjure = effect_remove
    Board:DamageSpace(sd)
    pcall(function()
        local fn = target.SetInfected
        if type(fn) == "function" then
            fn(target, false)
        end
    end)

    return new_hp
end

local function modloader_script_directory()
    local debug_table = rawget(_G, "debug")
    if type(debug_table) ~= "table"
        or type(rawget(debug_table, "getinfo")) ~= "function" then
        return nil, "debug.getinfo is unavailable"
    end
    local ok, info = pcall(
        rawget(debug_table, "getinfo"),
        modloader_script_directory,
        "S"
    )
    if not ok or type(info) ~= "table"
        or type(info.source) ~= "string"
        or string.sub(info.source, 1, 1) ~= "@" then
        return nil, "modloader source path is unavailable"
    end
    local source = normalize_path(string.sub(info.source, 2))
    local directory = string.match(source, "^(.*)/[^/]+$")
    if type(directory) ~= "string" or directory == "" then
        return nil, "modloader source directory is unavailable"
    end
    return directory
end

local function observatory_callback_module_path()
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    return directory .. "/observatory_callback_manifest.lua"
end

local function observatory_callback_bindings_module_path()
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    return directory .. "/observatory_callback_bindings.lua"
end

local function load_observatory_callback_module()
    local path, path_error = observatory_callback_module_path()
    if not path then return nil, path_error end
    local chunk, load_error = loadfile(path)
    if type(chunk) ~= "function" then
        return nil, "cannot load sibling callback module: "
            .. tostring(load_error)
    end
    local ok, module = pcall(chunk)
    if not ok or type(module) ~= "table" then
        return nil, "callback module failed to load: " .. tostring(module)
    end
    if rawget(module, "VERSION") ~= "observatory-callback-manifest/1"
        or type(rawget(module, "discover_enemy_skill_roots")) ~= "function"
        or type(rawget(module, "enumerate")) ~= "function" then
        return nil, "callback module contract mismatch"
    end
    return module
end

local function load_observatory_callback_bindings_module()
    local path, path_error = observatory_callback_bindings_module_path()
    if not path then return nil, path_error end
    local chunk, load_error = loadfile(path)
    if type(chunk) ~= "function" then
        return nil, "cannot load sibling callback bindings module: "
            .. tostring(load_error)
    end
    local ok, module = pcall(chunk)
    if not ok or type(module) ~= "table" then
        return nil, "callback bindings module failed to load: "
            .. tostring(module)
    end
    if rawget(module, "VERSION") ~= "observatory-callback-bindings/1"
        or type(rawget(module, "enumerate")) ~= "function" then
        return nil, "callback bindings module contract mismatch"
    end
    return module
end

local function write_observatory_callback_manifest(content)
    if type(content) ~= "string" or string.len(content) > 4 * 1024 * 1024 then
        return false, "callback manifest exceeds its output cap"
    end
    local file, open_error = io.open(CALLBACK_MANIFEST_TMP, "w")
    if not file then return false, tostring(open_error) end
    local write_ok, write_error = pcall(function()
        file:write(content)
        file:flush()
    end)
    file:close()
    if not write_ok then
        os.remove(CALLBACK_MANIFEST_TMP)
        return false, tostring(write_error)
    end
    local renamed, rename_error = os.rename(
        CALLBACK_MANIFEST_TMP, CALLBACK_MANIFEST_FILE
    )
    if not renamed and is_windows() then
        os.remove(CALLBACK_MANIFEST_FILE)
        renamed, rename_error = os.rename(
            CALLBACK_MANIFEST_TMP, CALLBACK_MANIFEST_FILE
        )
    end
    if not renamed then
        os.remove(CALLBACK_MANIFEST_TMP)
        return false, tostring(rename_error)
    end
    return true
end

local function write_observatory_callback_bindings(content)
    if type(content) ~= "string" or string.len(content) > 8 * 1024 * 1024 then
        return false, "callback bindings manifest exceeds its output cap"
    end
    local file, open_error = io.open(CALLBACK_BINDINGS_TMP, "w")
    if not file then return false, tostring(open_error) end
    local write_ok, write_error = pcall(function()
        file:write(content)
        file:flush()
    end)
    file:close()
    if not write_ok then
        os.remove(CALLBACK_BINDINGS_TMP)
        return false, tostring(write_error)
    end
    local renamed, rename_error = os.rename(
        CALLBACK_BINDINGS_TMP, CALLBACK_BINDINGS_FILE
    )
    if not renamed and is_windows() then
        os.remove(CALLBACK_BINDINGS_FILE)
        renamed, rename_error = os.rename(
            CALLBACK_BINDINGS_TMP, CALLBACK_BINDINGS_FILE
        )
    end
    if not renamed then
        os.remove(CALLBACK_BINDINGS_TMP)
        return false, tostring(rename_error)
    end
    return true
end

local function valid_lower_sha256(value)
    return type(value) == "string"
        and string.len(value) == 64
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function valid_observatory_capture_id(value)
    return type(value) == "string"
        and string.len(value) >= 1
        and string.len(value) <= 128
        and string.match(value, "^[a-z0-9][a-z0-9._-]*$") ~= nil
end

local function load_observatory_trial_artifact(directory, filename, label)
    if type(directory) ~= "string"
        or type(filename) ~= "string"
        or string.len(filename) < 1
        or string.len(filename) > 192
        or string.match(filename, "^[A-Za-z0-9_.-]+$") == nil then
        return nil, "invalid " .. label .. " filename"
    end
    local chunk, load_error = loadfile(directory .. "/" .. filename)
    if type(chunk) ~= "function" then
        return nil, "cannot load " .. label .. ": " .. tostring(load_error)
    end
    local ok, artifact = pcall(chunk)
    if not ok or type(artifact) ~= "table" then
        return nil, label .. " failed to load: " .. tostring(artifact)
    end
    return artifact
end

local function load_observatory_rng_seed_helper(directory, rng_control)
    if not is_windows() then
        return nil, "native RNG seed helper requires Windows"
    end
    if type(rng_control) ~= "table"
        or rawget(rng_control, "helper_version")
            ~= "observatory-rng-seed-helper/1"
        or not valid_lower_sha256(rawget(rng_control, "helper_sha256"))
        or not valid_lower_sha256(rawget(rng_control, "executable_sha256"))
        or rawget(rng_control, "architecture") ~= "x86"
        or type(rawget(rng_control, "build_id")) ~= "string"
        or type(rawget(rng_control, "rng_seed_rva")) ~= "string"
        or not valid_lower_sha256(
            rawget(rng_control, "rng_seed_region_sha256")
        ) then
        return nil, "native RNG seed helper identity is invalid"
    end
    local package_table = rawget(_G, "package")
    local loadlib = type(package_table) == "table"
        and rawget(package_table, "loadlib") or nil
    if type(loadlib) ~= "function" then
        return nil, "package.loadlib is unavailable"
    end
    local filename = "itb_observatory_rng_seed_"
        .. rawget(rng_control, "helper_sha256") .. ".dll"
    local ok, loader, load_error = pcall(
        loadlib,
        directory .. "/" .. filename,
        "luaopen_itb_observatory_rng_seed"
    )
    if not ok or type(loader) ~= "function" then
        return nil, "cannot load native RNG seed helper: "
            .. tostring(load_error or loader)
    end
    local opened, helper = pcall(loader)
    if not opened or type(helper) ~= "table" then
        return nil, "native RNG seed helper failed to open: "
            .. tostring(helper)
    end
    if rawget(helper, "VERSION") ~= rawget(rng_control, "helper_version")
        or rawget(helper, "BUILD_ID") ~= rawget(rng_control, "build_id")
        or rawget(helper, "EXECUTABLE_SHA256")
            ~= rawget(rng_control, "executable_sha256")
        or rawget(helper, "ARCHITECTURE")
            ~= rawget(rng_control, "architecture")
        or rawget(helper, "RNG_SEED_RVA")
            ~= rawget(rng_control, "rng_seed_rva")
        or rawget(helper, "RNG_SEED_REGION_SHA256")
            ~= rawget(rng_control, "rng_seed_region_sha256")
        or type(rawget(helper, "seed")) ~= "function" then
        return nil, "native RNG seed helper contract mismatch"
    end
    return helper
end

local function load_observatory_callback_gameflow_helper(
    directory, helper_sha256
)
    if not is_windows() then
        return nil, "callback game-flow helper requires Windows"
    end
    if type(directory) ~= "string"
        or not valid_lower_sha256(helper_sha256) then
        return nil, "callback game-flow helper identity is invalid"
    end
    local package_table = rawget(_G, "package")
    local loadlib = type(package_table) == "table"
        and rawget(package_table, "loadlib") or nil
    if type(loadlib) ~= "function" then
        return nil, "package.loadlib is unavailable"
    end
    local filename = "itb_observatory_continue_"
        .. helper_sha256 .. ".dll"
    local ok, loader, load_error = pcall(
        loadlib,
        directory .. "/" .. filename,
        "luaopen_itb_observatory_continue"
    )
    if not ok or type(loader) ~= "function" then
        return nil, "cannot load callback game-flow helper: "
            .. tostring(load_error or loader)
    end
    local opened, helper = pcall(loader)
    if not opened or type(helper) ~= "table" then
        return nil, "callback game-flow helper failed to open: "
            .. tostring(helper)
    end
    if rawget(helper, "VERSION")
            ~= "observatory-callback-gameflow-helper/6"
        or rawget(helper, "BUILD_ID") ~= "13725832"
        or rawget(helper, "EXECUTABLE_SHA256")
            ~= "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        or rawget(helper, "ARCHITECTURE") ~= "x86"
        or rawget(helper, "HOST_GLOBAL_RVA") ~= "0x004b9cf8"
        or rawget(helper, "GAME_APP_VTABLE_RVA") ~= "0x00435014"
        or rawget(helper, "MENU_VTABLE_RVA") ~= "0x0043597c"
        or rawget(helper, "MENU_BUTTON_VTABLE_RVA") ~= "0x004358f4"
        or rawget(helper, "TITLE_KEY_ACTION_RVA") ~= "0x0021c650"
        or rawget(helper, "TITLE_KEY_ACTION_REGION_SHA256")
            ~= "981a2a39bfcc7ae40d5aa7e4c049b3ad97877404807b979a938a0bf10bd0f481"
        or rawget(helper, "NEW_GAME_ACTION_RVA") ~= "0x00217900"
        or rawget(helper, "NEW_GAME_ACTION_REGION_SHA256")
            ~= "4ae664238c4b6678a7c0c769c72d5850014e4cd5b8fdb2c6d034a16d2ee3eceb"
        or rawget(helper, "SCREEN_ROOT_VTABLE_RVA") ~= "0x0043544c"
        or rawget(helper, "BATTLE_UI_VTABLE_RVA") ~= "0x00430148"
        or rawget(helper, "END_TURN_ACTION_RVA") ~= "0x00186b40"
        or rawget(helper, "END_TURN_ACTION_REGION_SHA256")
            ~= "3eff056cdd650e48c1c508f48da151d39bcd987afc1043257acc4d33bf1ea756"
        or rawget(helper, "SDL2_SHA256")
            ~= "cb7161fff576ab9a0288c14029bc98d138c3f660e764860dbd37640f06cb7f10"
        or rawget(helper, "RENDER_PRESENT_IAT_RVA") ~= "0x003d6384"
        or rawget(helper, "GL_SWAP_IAT_RVA") ~= "0x003d63b4"
        or type(rawget(helper, "continue_saved_timeline")) ~= "function"
        or type(rawget(helper, "continue_status")) ~= "function"
        or type(rawget(helper, "end_player_turn")) ~= "function" then
        return nil, "callback game-flow helper contract mismatch"
    end
    return helper
end

local function load_observatory_native_gameflow_helper(directory)
    return load_observatory_callback_gameflow_helper(
        directory, NATIVE_GAMEFLOW_HELPER_SHA256
    )
end

local function load_observatory_selected_queue_module(directory)
    if not is_windows() then
        return nil, "selected/queue observer requires Windows"
    end
    if type(directory) ~= "string" then
        return nil, "selected/queue observer directory is invalid"
    end
    local package_table = rawget(_G, "package")
    local loadlib = type(package_table) == "table"
        and rawget(package_table, "loadlib") or nil
    if type(loadlib) ~= "function" then
        return nil, "package.loadlib is unavailable"
    end
    local filename = "itb_observatory_selected_queue_hw_observer_"
        .. SELECTED_QUEUE_OBSERVER_SHA256 .. ".dll"
    local ok, loader, load_error = pcall(
        loadlib,
        directory .. "/" .. filename,
        SELECTED_QUEUE_OBSERVER_EXPORT
    )
    if not ok or type(loader) ~= "function" then
        return nil, "cannot load selected/queue observer: "
            .. tostring(load_error or loader)
    end
    local opened, observer = pcall(loader)
    if not opened or type(observer) ~= "table" then
        return nil, "selected/queue observer failed to open: "
            .. tostring(observer)
    end
    if rawget(observer, "VERSION")
            ~= "observatory-selected-queue-hw-observer/1"
        or rawget(observer, "BUILD_ID") ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(observer, "EXECUTABLE_SHA256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(observer, "ARCHITECTURE") ~= "x86"
        or rawget(observer, "SELECTED_RVA") ~= "0x000f6854"
        or rawget(observer, "QUEUE_RVA") ~= "0x00227d20"
        or rawget(observer, "HARDWARE_BREAKPOINT_PLAN_SHA256")
            ~= SELECTED_QUEUE_HW_PLAN_SHA256
        or type(rawget(observer, "arm")) ~= "function"
        or type(rawget(observer, "finish")) ~= "function"
        or type(rawget(observer, "status")) ~= "function" then
        return nil, "selected/queue observer contract mismatch"
    end
    return observer
end

local function load_observatory_spawn_coordinate_module(directory)
    if not is_windows() then
        return nil, "spawn-coordinate observer requires Windows"
    end
    if type(directory) ~= "string" then
        return nil, "spawn-coordinate observer directory is invalid"
    end
    local package_table = rawget(_G, "package")
    local loadlib = type(package_table) == "table"
        and rawget(package_table, "loadlib") or nil
    if type(loadlib) ~= "function" then
        return nil, "package.loadlib is unavailable"
    end
    local filename = "itb_observatory_spawn_coordinate_hw_observer_"
        .. SPAWN_COORDINATE_OBSERVER_SHA256 .. ".dll"
    local ok, loader, load_error = pcall(
        loadlib,
        directory .. "/" .. filename,
        SPAWN_COORDINATE_OBSERVER_EXPORT
    )
    if not ok or type(loader) ~= "function" then
        return nil, "cannot load spawn-coordinate observer: "
            .. tostring(load_error or loader)
    end
    local opened, observer = pcall(loader)
    if not opened or type(observer) ~= "table" then
        return nil, "spawn-coordinate observer failed to open: "
            .. tostring(observer)
    end
    if rawget(observer, "VERSION")
            ~= "observatory-spawn-coordinate-hw-observer/1"
        or rawget(observer, "BUILD_ID") ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(observer, "EXECUTABLE_SHA256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(observer, "ARCHITECTURE") ~= "x86"
        or rawget(observer, "SCHEDULER_RVA") ~= "0x001751ae"
        or rawget(observer, "SELECTOR_FALLBACK_RVA") ~= "0x00172e1e"
        or rawget(observer, "SELECTOR_STANDARD_RVA") ~= "0x00172e7b"
        or rawget(observer, "HARDWARE_BREAKPOINT_PLAN_SHA256")
            ~= SPAWN_COORDINATE_HW_PLAN_SHA256
        or type(rawget(observer, "arm")) ~= "function"
        or type(rawget(observer, "finish")) ~= "function"
        or type(rawget(observer, "status")) ~= "function" then
        return nil, "spawn-coordinate observer contract mismatch"
    end
    return observer
end

local function observatory_path_exists(path)
    local file = io.open(path, "r")
    if not file then return false end
    file:close()
    return true
end

local function write_observatory_create_only_json(
    final_path, temp_path, value, max_bytes
)
    if type(final_path) ~= "string"
        or type(temp_path) ~= "string"
        or type(value) ~= "table"
        or type(max_bytes) ~= "number"
        or max_bytes < 1
        or max_bytes > 64 * 1024 * 1024 then
        return false, "invalid create-only output"
    end
    if observatory_path_exists(final_path)
        or observatory_path_exists(temp_path) then
        return false, "create-only output already exists"
    end
    local content = json_encode(value)
    if type(content) ~= "string" or string.len(content) > max_bytes then
        return false, "create-only output exceeds its cap"
    end
    local file, open_error = io.open(temp_path, "w")
    if not file then return false, tostring(open_error) end
    local write_ok, write_error = pcall(function()
        file:write(content)
        file:flush()
    end)
    file:close()
    if not write_ok then
        os.remove(temp_path)
        return false, tostring(write_error)
    end
    if observatory_path_exists(final_path) then
        os.remove(temp_path)
        return false, "create-only output appeared during publication"
    end
    local renamed, rename_error = os.rename(temp_path, final_path)
    if not renamed then
        os.remove(temp_path)
        return false, tostring(rename_error)
    end
    return true
end

local function load_observatory_native_rng_module()
    if not is_windows() then
        return nil, "native RNG observer requires Windows"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local package_table = rawget(_G, "package")
    local loadlib = type(package_table) == "table"
        and rawget(package_table, "loadlib") or nil
    if type(loadlib) ~= "function" then
        return nil, "package.loadlib is unavailable"
    end
    local filename = "itb_observatory_rng_core_observer_"
        .. NATIVE_RNG_OBSERVER_SHA256 .. ".dll"
    local ok, loader, load_error = pcall(
        loadlib,
        directory .. "/" .. filename,
        NATIVE_RNG_OBSERVER_EXPORT
    )
    if not ok or type(loader) ~= "function" then
        return nil, "cannot load native RNG observer: "
            .. tostring(load_error or loader)
    end
    local opened, observer = pcall(loader)
    if not opened or type(observer) ~= "table" then
        return nil, "native RNG observer failed to open: "
            .. tostring(observer)
    end
    if rawget(observer, "VERSION")
            ~= "observatory-rng-core-observer/1"
        or rawget(observer, "BUILD_ID")
            ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(observer, "EXECUTABLE_SHA256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(observer, "ARCHITECTURE") ~= "x86"
        or rawget(observer, "RNG_CORE_RVA")
            ~= NATIVE_RNG_OBSERVER_CORE_RVA
        or rawget(observer, "RNG_CORE_REGION_SHA256")
            ~= NATIVE_RNG_OBSERVER_CORE_SHA256
        or rawget(observer, "RNG_RETURN_MAP_SHA256")
            ~= NATIVE_RNG_OBSERVER_RETURN_MAP_SHA256
        or rawget(observer, "HOOK_PLAN_SHA256")
            ~= NATIVE_RNG_OBSERVER_HOOK_PLAN_SHA256
        or rawget(observer, "RESTORE_MANIFEST_SHA256")
            ~= NATIVE_RNG_OBSERVER_RESTORE_SHA256
        or type(rawget(observer, "arm")) ~= "function"
        or type(rawget(observer, "finish")) ~= "function"
        or type(rawget(observer, "status")) ~= "function" then
        return nil, "native RNG observer contract mismatch"
    end
    return observer
end

local function load_observatory_spawn_span_controller(observer, capture_id)
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local filename = "itb_observatory_spawn_span_controller_"
        .. SPAWN_SPAN_CONTROLLER_SHA256 .. ".lua"
    local module, module_error = load_observatory_trial_artifact(
        directory, filename, "spawn span controller"
    )
    if not module then return nil, module_error end
    if rawget(module, "VERSION")
            ~= "observatory-spawn-span-controller/1"
        or rawget(module, "SPAWNER_SOURCE_SUFFIX")
            ~= "scripts/spawner_backend.lua"
        or rawget(module, "SPAWNER_SOURCE_LINE") ~= 174
        or rawget(module, "SPAWNER_SOURCE_SHA256")
            ~= "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
        or rawget(module, "MAX_SPANS") ~= 64
        or rawget(module, "MAX_NATIVE_RECORDS") ~= 4096
        or type(rawget(module, "new")) ~= "function" then
        return nil, "spawn span controller contract mismatch"
    end
    local spawner = rawget(_G, "Spawner")
    local debug_table = rawget(_G, "debug")
    local getinfo = type(debug_table) == "table"
        and rawget(debug_table, "getinfo") or nil
    if type(spawner) ~= "table" or type(rawget(spawner, "NextPawn")) ~= "function"
        or type(getinfo) ~= "function" then
        return nil, "Spawner.NextPawn runtime boundary is unavailable"
    end
    local opened, controller, controller_error = pcall(
        rawget(module, "new"),
        {
            capture_id = capture_id,
            spawner = spawner,
            observer = observer,
            getinfo = getinfo,
        }
    )
    if not opened or type(controller) ~= "table" then
        return nil, "spawn span controller construction failed: "
            .. tostring(controller_error or controller)
    end
    if type(rawget(controller, "activate")) ~= "function"
        or type(rawget(controller, "checkpoint")) ~= "function"
        or type(rawget(controller, "abort")) ~= "function" then
        return nil, "spawn span controller instance contract mismatch"
    end
    return controller
end

local function load_observatory_spawn_replay_controller(observer, capture_id)
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local filename = "itb_observatory_spawn_replay_controller_"
        .. SPAWN_REPLAY_CONTROLLER_SHA256 .. ".lua"
    local module, module_error = load_observatory_trial_artifact(
        directory, filename, "spawn replay controller"
    )
    if not module then return nil, module_error end
    if rawget(module, "VERSION")
            ~= "observatory-spawn-replay-controller/1"
        or rawget(module, "SPAWNER_SOURCE_SUFFIX")
            ~= "scripts/spawner_backend.lua"
        or rawget(module, "SPAWNER_SOURCE_LINE") ~= 174
        or rawget(module, "SPAWNER_SOURCE_SHA256")
            ~= "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
        or rawget(module, "RANDOM_ELEMENT_SOURCE_SUFFIX")
            ~= "scripts/global.lua"
        or rawget(module, "RANDOM_ELEMENT_SOURCE_LINE") ~= 560
        or rawget(module, "RANDOM_ELEMENT_SOURCE_SHA256")
            ~= "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        or rawget(module, "MAX_SPANS") ~= 8
        or rawget(module, "MAX_CANDIDATES") ~= 64
        or rawget(module, "MAX_NATIVE_RECORDS") ~= 4096
        or type(rawget(module, "new")) ~= "function" then
        return nil, "spawn replay controller contract mismatch"
    end
    local spawner = rawget(_G, "Spawner")
    local random_element_fn = rawget(_G, "random_element")
    local debug_table = rawget(_G, "debug")
    local getinfo = type(debug_table) == "table"
        and rawget(debug_table, "getinfo") or nil
    if type(spawner) ~= "table"
        or type(rawget(spawner, "NextPawn")) ~= "function"
        or type(random_element_fn) ~= "function"
        or type(getinfo) ~= "function" then
        return nil, "spawn replay runtime boundaries are unavailable"
    end
    local opened, controller, controller_error = pcall(
        rawget(module, "new"),
        {
            capture_id = capture_id,
            spawner = spawner,
            observer = observer,
            getinfo = getinfo,
            globals = _G,
        }
    )
    if not opened or type(controller) ~= "table" then
        return nil, "spawn replay controller construction failed: "
            .. tostring(controller_error or controller)
    end
    if type(rawget(controller, "activate")) ~= "function"
        or type(rawget(controller, "checkpoint")) ~= "function"
        or type(rawget(controller, "abort")) ~= "function" then
        return nil, "spawn replay controller instance contract mismatch"
    end
    return controller
end

local function validate_observatory_native_rng_snapshot(snapshot, capture_id)
    if type(snapshot) ~= "table"
        or rawget(snapshot, "schema_version") ~= 1
        or rawget(snapshot, "kind")
            ~= "native_rng_core_observer_snapshot"
        or rawget(snapshot, "observer_version")
            ~= "observatory-rng-core-observer/1"
        or rawget(snapshot, "capture_id") ~= capture_id
        or type(rawget(snapshot, "identity")) ~= "table"
        or type(rawget(snapshot, "integrity")) ~= "table"
        or type(rawget(snapshot, "records")) ~= "table"
        or type(rawget(snapshot, "summary")) ~= "table" then
        return nil, "native RNG snapshot contract mismatch"
    end
    local identity = rawget(snapshot, "identity")
    local integrity = rawget(snapshot, "integrity")
    local summary = rawget(snapshot, "summary")
    if rawget(identity, "build_id") ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(identity, "executable_sha256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(identity, "rng_return_map_sha256")
            ~= NATIVE_RNG_OBSERVER_RETURN_MAP_SHA256
        or rawget(identity, "hook_plan_sha256")
            ~= NATIVE_RNG_OBSERVER_HOOK_PLAN_SHA256
        or rawget(identity, "restore_manifest_sha256")
            ~= NATIVE_RNG_OBSERVER_RESTORE_SHA256
        or rawget(integrity, "complete") ~= true
        or rawget(integrity, "state") ~= "restored"
        or rawget(integrity, "patch_installed") ~= false
        or rawget(integrity, "hook_bytes_restored") ~= true
        or type(rawget(summary, "record_count")) ~= "number"
        or rawget(summary, "record_count") ~= #snapshot.records then
        return nil, "native RNG snapshot is incomplete or inconsistent"
    end
    return true
end

local function validate_observatory_spawn_span_ledger(
    ledger, capture_id, raw_record_count
)
    if type(ledger) ~= "table"
        or rawget(ledger, "schema_version") ~= 1
        or rawget(ledger, "kind") ~= "spawn_rng_span_ledger"
        or rawget(ledger, "controller_version")
            ~= "observatory-spawn-span-controller/1"
        or rawget(ledger, "controller_sha256")
            ~= SPAWN_SPAN_CONTROLLER_SHA256
        or rawget(ledger, "capture_id") ~= capture_id
        or rawget(ledger, "write_mode") ~= "create_only"
        or rawget(ledger, "raw_record_count") ~= raw_record_count
        or type(rawget(ledger, "source_identity")) ~= "table"
        or type(rawget(ledger, "integrity")) ~= "table"
        or type(rawget(ledger, "spans")) ~= "table"
        or type(rawget(ledger, "summary")) ~= "table" then
        return nil, "spawn span ledger contract mismatch"
    end
    local source = rawget(ledger, "source_identity")
    local integrity = rawget(ledger, "integrity")
    local summary = rawget(ledger, "summary")
    if rawget(source, "expected_sha256")
            ~= "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
        or rawget(source, "expected_source_suffix")
            ~= "scripts/spawner_backend.lua"
        or rawget(source, "expected_linedefined") ~= 174
        or rawget(source, "runtime_linedefined") ~= 174
        or rawget(source, "source_location_verified") ~= true
        or rawget(integrity, "complete") ~= true
        or rawget(integrity, "wrapper_restored") ~= true
        or rawget(integrity, "restore_conflict") ~= false
        or rawget(integrity, "nested_call_count") ~= 0
        or rawget(integrity, "observer_status_error_count") ~= 0
        or rawget(integrity, "span_overflow_count") ~= 0
        or rawget(integrity, "count_regression_count") ~= 0
        or rawget(integrity, "active_depth") ~= 0
        or rawget(summary, "span_count") ~= #ledger.spans
        or rawget(summary, "complete") ~= true then
        return nil, "spawn span ledger is incomplete"
    end
    local previous_exit = 0
    for index, span in ipairs(ledger.spans) do
        if type(span) ~= "table"
            or rawget(span, "span_id") ~= index
            or rawget(span, "name") ~= "spawner_next_pawn"
            or rawget(span, "detail") ~= "normal"
            or type(rawget(span, "entry_count")) ~= "number"
            or span.entry_count ~= math.floor(span.entry_count)
            or type(rawget(span, "exit_count")) ~= "number"
            or span.exit_count ~= math.floor(span.exit_count)
            or span.entry_count < previous_exit
            or span.entry_count < 0
            or span.entry_count > span.exit_count
            or span.exit_count > raw_record_count
            or type(rawget(span, "selected_pawn")) ~= "string"
            or string.len(span.selected_pawn) < 1
            or string.len(span.selected_pawn) > 96 then
            return nil, "spawn span ledger contains an invalid span"
        end
        previous_exit = span.exit_count
    end
    return true
end

local function validate_observatory_spawn_replay_ledger(
    ledger, capture_id, raw_record_count
)
    if type(ledger) ~= "table"
        or rawget(ledger, "schema_version") ~= 1
        or rawget(ledger, "kind") ~= "spawn_rng_replay_ledger"
        or rawget(ledger, "controller_version")
            ~= "observatory-spawn-replay-controller/1"
        or rawget(ledger, "controller_sha256")
            ~= SPAWN_REPLAY_CONTROLLER_SHA256
        or rawget(ledger, "capture_id") ~= capture_id
        or rawget(ledger, "write_mode") ~= "create_only"
        or rawget(ledger, "raw_record_count") ~= raw_record_count
        or type(rawget(ledger, "source_identity")) ~= "table"
        or type(rawget(ledger, "integrity")) ~= "table"
        or type(rawget(ledger, "spans")) ~= "table"
        or type(rawget(ledger, "summary")) ~= "table" then
        return nil, "spawn replay ledger contract mismatch"
    end
    local source = rawget(ledger, "source_identity")
    local integrity = rawget(ledger, "integrity")
    local summary = rawget(ledger, "summary")
    if rawget(source, "spawner_expected_sha256")
            ~= "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
        or rawget(source, "spawner_expected_source_suffix")
            ~= "scripts/spawner_backend.lua"
        or rawget(source, "spawner_expected_linedefined") ~= 174
        or rawget(source, "spawner_runtime_linedefined") ~= 174
        or rawget(source, "random_element_expected_sha256")
            ~= "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        or rawget(source, "random_element_expected_source_suffix")
            ~= "scripts/global.lua"
        or rawget(source, "random_element_expected_linedefined") ~= 560
        or rawget(source, "random_element_runtime_linedefined") ~= 560
        or rawget(source, "source_locations_verified") ~= true
        or rawget(integrity, "complete") ~= true
        or rawget(integrity, "next_wrapper_restored") ~= true
        or rawget(integrity, "random_wrapper_restored") ~= true
        or rawget(integrity, "restore_conflict") ~= false
        or rawget(integrity, "nested_next_count") ~= 0
        or rawget(integrity, "nested_random_count") ~= 0
        or rawget(integrity, "observer_status_error_count") ~= 0
        or rawget(integrity, "span_overflow_count") ~= 0
        or rawget(integrity, "candidate_overflow_count") ~= 0
        or rawget(integrity, "invalid_candidate_count") ~= 0
        or rawget(integrity, "input_snapshot_error_count") ~= 0
        or rawget(integrity, "random_install_error_count") ~= 0
        or rawget(integrity, "candidate_count_mismatch_count") ~= 0
        or rawget(integrity, "active_depth") ~= 0
        or rawget(summary, "span_count") ~= #ledger.spans
        or rawget(summary, "candidate_event_count") ~= #ledger.spans
        or rawget(summary, "complete") ~= true then
        return nil, "spawn replay ledger is incomplete: spans="
            .. tostring(rawget(summary, "span_count"))
            .. " events=" .. tostring(rawget(summary, "candidate_event_count"))
            .. " next_restored="
            .. tostring(rawget(integrity, "next_wrapper_restored"))
            .. " random_restored="
            .. tostring(rawget(integrity, "random_wrapper_restored"))
            .. " conflict=" .. tostring(rawget(integrity, "restore_conflict"))
            .. " nested_next="
            .. tostring(rawget(integrity, "nested_next_count"))
            .. " nested_random="
            .. tostring(rawget(integrity, "nested_random_count"))
            .. " observer_status="
            .. tostring(rawget(integrity, "observer_status_error_count"))
            .. " span_overflow="
            .. tostring(rawget(integrity, "span_overflow_count"))
            .. " candidate_overflow="
            .. tostring(rawget(integrity, "candidate_overflow_count"))
            .. " invalid_candidate="
            .. tostring(rawget(integrity, "invalid_candidate_count"))
            .. " input_snapshot="
            .. tostring(rawget(integrity, "input_snapshot_error_count"))
            .. " random_install="
            .. tostring(rawget(integrity, "random_install_error_count"))
            .. " candidate_mismatch="
            .. tostring(rawget(integrity, "candidate_count_mismatch_count"))
            .. " active_depth=" .. tostring(rawget(integrity, "active_depth"))
    end
    local scalar_fields = {
        "num_weak", "num_upgrades", "upgrade_streak", "num_spawns",
        "upgrade_max", "used_bosses", "num_bosses",
    }
    local previous_exit = 0
    for index, span in ipairs(ledger.spans) do
        if type(span) ~= "table"
            or rawget(span, "span_id") ~= index
            or rawget(span, "name") ~= "spawner_next_pawn"
            or rawget(span, "detail") ~= "normal"
            or rawget(span, "inputs_valid") ~= true
            or type(rawget(span, "inputs")) ~= "table"
            or type(rawget(span, "candidate_events")) ~= "table"
            or #span.candidate_events ~= 1
            or type(rawget(span, "entry_count")) ~= "number"
            or span.entry_count ~= math.floor(span.entry_count)
            or type(rawget(span, "exit_count")) ~= "number"
            or span.exit_count ~= math.floor(span.exit_count)
            or span.entry_count < previous_exit
            or span.entry_count < 0
            or span.exit_count - span.entry_count < 3
            or span.exit_count - span.entry_count > 4
            or span.exit_count > raw_record_count
            or type(rawget(span, "selected_pawn")) ~= "string"
            or string.len(span.selected_pawn) < 2
            or string.len(span.selected_pawn) > 100
            or type(rawget(span, "selected_max_level")) ~= "number"
            or span.selected_max_level ~= math.floor(span.selected_max_level)
            or span.selected_max_level < 1 or span.selected_max_level > 2
            or type(rawget(span, "boss_available")) ~= "boolean"
            or rawget(span, "random_wrapper_restored") ~= true then
            return nil, "spawn replay ledger contains an invalid span"
        end
        for _, field in ipairs(scalar_fields) do
            local value = rawget(span.inputs, field)
            if value ~= false and (type(value) ~= "number"
                or value ~= math.floor(value)) then
                return nil, "spawn replay ledger contains invalid scalar inputs"
            end
        end
        for _, field in ipairs({"curr_weak_ratio", "curr_upgrade_ratio"}) do
            local ratio = rawget(span.inputs, field)
            if type(ratio) ~= "table"
                or type(rawget(ratio, "present")) ~= "boolean"
                or (rawget(ratio, "numerator") ~= false
                    and (type(rawget(ratio, "numerator")) ~= "number"
                        or ratio.numerator ~= math.floor(ratio.numerator)))
                or (rawget(ratio, "denominator") ~= false
                    and (type(rawget(ratio, "denominator")) ~= "number"
                        or ratio.denominator ~= math.floor(ratio.denominator))) then
                return nil, "spawn replay ledger contains invalid ratio inputs"
            end
        end
        local event = span.candidate_events[1]
        if type(event) ~= "table"
            or rawget(event, "event_id") ~= 1
            or rawget(event, "detail") ~= "normal"
            or rawget(event, "candidates_valid") ~= true
            or type(rawget(event, "entry_count")) ~= "number"
            or event.entry_count ~= math.floor(event.entry_count)
            or type(rawget(event, "exit_count")) ~= "number"
            or event.exit_count ~= event.entry_count + 1
            or event.entry_count < span.entry_count
            or event.exit_count > span.exit_count
            or type(rawget(event, "list_length")) ~= "number"
            or event.list_length ~= math.floor(event.list_length)
            or event.list_length < 1 or event.list_length > 64
            or type(rawget(event, "available")) ~= "table"
            or #event.available ~= event.list_length
            or type(rawget(event, "selected_base")) ~= "string"
            or string.sub(span.selected_pawn, 1, string.len(event.selected_base))
                ~= event.selected_base then
            return nil, "spawn replay ledger contains an invalid candidate event"
        end
        local selected_found = false
        for candidate_index, candidate in ipairs(event.available) do
            if candidate_index > event.list_length
                or type(candidate) ~= "string"
                or string.len(candidate) < 1
                or string.len(candidate) > 96 then
                return nil, "spawn replay ledger contains an invalid candidate"
            end
            if candidate == event.selected_base then selected_found = true end
        end
        if not selected_found then
            return nil, "spawn replay selected base is absent from candidates"
        end
        previous_exit = span.exit_count
    end
    return true
end

local function start_observatory_native_rng_with_spawn_span(capture_id)
    local command_name = "OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN"
    if not valid_observatory_capture_id(capture_id)
        or string.len(capture_id) > 96 then
        return nil, command_name .. " requires one capture ID"
    end
    if not Board or not Game then
        return nil, command_name .. " requires an active mission"
    end
    local team_ok, team_turn = pcall(function() return Game:GetTeamTurn() end)
    if not team_ok or team_turn ~= TEAM_PLAYER then
        return nil, command_name .. " requires combat_player"
    end
    local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
    for _, actor_id in ipairs(actor_ids) do
        local actor = Board:GetPawn(actor_id)
        local active_ok, active = pcall(function()
            return actor and actor:IsActive()
        end)
        if active_ok and active then
            return nil, command_name .. " requires spent player actors"
        end
    end
    if _observatory_native_rng_module ~= nil
        or _observatory_spawn_span_controller ~= nil then
        return nil, "native RNG spawn-span observer is already consumed"
    end
    if observatory_path_exists(NATIVE_RNG_SNAPSHOT_FILE)
        or observatory_path_exists(NATIVE_RNG_SNAPSHOT_TMP)
        or observatory_path_exists(SPAWN_SPAN_LEDGER_FILE)
        or observatory_path_exists(SPAWN_SPAN_LEDGER_TMP) then
        return nil, "native RNG spawn-span output already exists"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local seed_helper, seed_helper_error = load_observatory_rng_seed_helper(
        directory,
        {
            helper_version = "observatory-rng-seed-helper/1",
            helper_sha256 = NATIVE_RNG_SEED_HELPER_SHA256,
            executable_sha256 = NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256,
            architecture = "x86",
            build_id = NATIVE_RNG_OBSERVER_BUILD_ID,
            rng_seed_rva = "0x00387f37",
            rng_seed_region_sha256 = NATIVE_RNG_SEED_REGION_SHA256,
        }
    )
    if not seed_helper then return nil, tostring(seed_helper_error) end
    local gameflow, gameflow_error =
        load_observatory_native_gameflow_helper(directory)
    if not gameflow then return nil, tostring(gameflow_error) end
    local observer, observer_error = load_observatory_native_rng_module()
    if not observer then return nil, tostring(observer_error) end
    local controller, controller_error =
        load_observatory_spawn_span_controller(observer, capture_id)
    if not controller then return nil, tostring(controller_error) end

    local seed_ok, seeded = pcall(
        rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED
    )
    if not seed_ok or seeded ~= true then
        return nil, "seed failed: " .. tostring(seeded)
    end
    _observatory_native_rng_module = observer
    _observatory_native_rng_capture_id = capture_id
    local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
    if not arm_ok or armed ~= true then
        pcall(rawget(observer, "finish"))
        return nil, "native observer arm failed: " .. tostring(armed)
    end
    local activate_ok, activated = pcall(
        rawget(controller, "activate"), controller
    )
    if not activate_ok or activated ~= true then
        pcall(rawget(controller, "abort"), controller)
        pcall(rawget(observer, "finish"))
        return nil, "spawn span activation failed: " .. tostring(activated)
    end
    local status_ok, status = pcall(rawget(observer, "status"))
    if not status_ok or type(status) ~= "table"
        or rawget(status, "state") ~= "capturing"
        or rawget(status, "patch_installed") ~= true then
        pcall(rawget(controller, "abort"), controller)
        pcall(rawget(observer, "finish"))
        return nil, "post-activation observer status mismatch"
    end
    _observatory_spawn_span_controller = controller
    _observatory_native_gameflow = gameflow
    return command_name .. " capture=" .. capture_id
        .. " seed=" .. tostring(NATIVE_RNG_FIXED_SEED)
end

local function start_observatory_native_rng_with_spawn_replay(capture_id)
    local command_name = "OBS_NATIVE_RNG_ARM_SPAWN_REPLAY"
    if not valid_observatory_capture_id(capture_id)
        or string.len(capture_id) > 96 then
        return nil, command_name .. " requires one capture ID"
    end
    if not Board or not Game then
        return nil, command_name .. " requires an active mission"
    end
    local team_ok, team_turn = pcall(function() return Game:GetTeamTurn() end)
    if not team_ok or team_turn ~= TEAM_PLAYER then
        return nil, command_name .. " requires combat_player"
    end
    local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
    for _, actor_id in ipairs(actor_ids) do
        local actor = Board:GetPawn(actor_id)
        local active_ok, active = pcall(function()
            return actor and actor:IsActive()
        end)
        if active_ok and active then
            return nil, command_name .. " requires spent player actors"
        end
    end
    if _observatory_native_rng_module ~= nil
        or _observatory_spawn_span_controller ~= nil
        or _observatory_spawn_replay_controller ~= nil then
        return nil, "native RNG spawn-replay observer is already consumed"
    end
    if observatory_path_exists(NATIVE_RNG_SNAPSHOT_FILE)
        or observatory_path_exists(NATIVE_RNG_SNAPSHOT_TMP)
        or observatory_path_exists(SPAWN_REPLAY_LEDGER_FILE)
        or observatory_path_exists(SPAWN_REPLAY_LEDGER_TMP) then
        return nil, "native RNG spawn-replay output already exists"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local gameflow, gameflow_error =
        load_observatory_native_gameflow_helper(directory)
    if not gameflow then return nil, tostring(gameflow_error) end
    local observer, observer_error = load_observatory_native_rng_module()
    if not observer then return nil, tostring(observer_error) end
    local controller, controller_error =
        load_observatory_spawn_replay_controller(observer, capture_id)
    if not controller then return nil, tostring(controller_error) end

    _observatory_native_rng_module = observer
    _observatory_native_rng_capture_id = capture_id
    local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
    if not arm_ok or armed ~= true then
        pcall(rawget(observer, "finish"))
        return nil, "native observer arm failed: " .. tostring(armed)
    end
    local activate_ok, activated = pcall(
        rawget(controller, "activate"), controller
    )
    if not activate_ok or activated ~= true then
        pcall(rawget(controller, "abort"), controller)
        pcall(rawget(observer, "finish"))
        return nil, "spawn replay activation failed: " .. tostring(activated)
    end
    local status_ok, status = pcall(rawget(observer, "status"))
    if not status_ok or type(status) ~= "table"
        or rawget(status, "state") ~= "capturing"
        or rawget(status, "patch_installed") ~= true then
        pcall(rawget(controller, "abort"), controller)
        pcall(rawget(observer, "finish"))
        return nil, "post-activation observer status mismatch"
    end
    _observatory_spawn_replay_controller = controller
    _observatory_native_gameflow = gameflow
    return command_name .. " capture=" .. capture_id
end

local function prepare_observatory_spawn_replay_control(capture_id)
    local command_name = "OBS_SPAWN_REPLAY_CONTROL"
    if not valid_observatory_capture_id(capture_id)
        or string.len(capture_id) > 96 then
        return nil, command_name .. " requires one capture ID"
    end
    if not Board or not Game then
        return nil, command_name .. " requires an active mission"
    end
    local team_ok, team_turn = pcall(function() return Game:GetTeamTurn() end)
    if not team_ok or team_turn ~= TEAM_PLAYER then
        return nil, command_name .. " requires combat_player"
    end
    local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
    for _, actor_id in ipairs(actor_ids) do
        local actor = Board:GetPawn(actor_id)
        local active_ok, active = pcall(function()
            return actor and actor:IsActive()
        end)
        if active_ok and active then
            return nil, command_name .. " requires spent player actors"
        end
    end
    if _observatory_native_rng_module ~= nil
        or _observatory_spawn_span_controller ~= nil
        or _observatory_spawn_replay_controller ~= nil then
        return nil, "native RNG observer is already consumed"
    end
    if observatory_path_exists(NATIVE_RNG_SNAPSHOT_FILE)
        or observatory_path_exists(NATIVE_RNG_SNAPSHOT_TMP)
        or observatory_path_exists(SPAWN_REPLAY_LEDGER_FILE)
        or observatory_path_exists(SPAWN_REPLAY_LEDGER_TMP) then
        return nil, "spawn replay control output already exists"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local gameflow, gameflow_error =
        load_observatory_native_gameflow_helper(directory)
    if not gameflow then return nil, tostring(gameflow_error) end
    local observer, observer_error = load_observatory_native_rng_module()
    if not observer then return nil, tostring(observer_error) end
    local controller, controller_error =
        load_observatory_spawn_replay_controller(observer, capture_id)
    if not controller then return nil, tostring(controller_error) end
    -- Loading and constructing both content-addressed modules is the dormant
    -- control. Neither arm() nor activate() is called, and no output is made.
    _observatory_native_gameflow = gameflow
    return command_name .. " capture=" .. capture_id .. " dormant=true"
end

local function validate_observatory_selected_queue_snapshot(snapshot, capture_id)
    if type(snapshot) ~= "table"
        or rawget(snapshot, "schema_version") ~= 1
        or rawget(snapshot, "kind")
            ~= "native_selected_queue_hw_observer_snapshot"
        or rawget(snapshot, "observer_version")
            ~= "observatory-selected-queue-hw-observer/1"
        or rawget(snapshot, "capture_id") ~= capture_id
        or type(rawget(snapshot, "identity")) ~= "table"
        or type(rawget(snapshot, "integrity")) ~= "table"
        or type(rawget(snapshot, "records")) ~= "table"
        or type(rawget(snapshot, "summary")) ~= "table" then
        return nil, "selected/queue snapshot contract mismatch"
    end
    local identity = rawget(snapshot, "identity")
    local integrity = rawget(snapshot, "integrity")
    local summary = rawget(snapshot, "summary")
    if rawget(identity, "platform") ~= "windows"
        or rawget(identity, "architecture") ~= "x86"
        or rawget(identity, "build_id") ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(identity, "executable_sha256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(identity, "boundary_map_sha256")
            ~= "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        or rawget(identity, "hardware_breakpoint_plan_sha256")
            ~= SELECTED_QUEUE_HW_PLAN_SHA256
        or rawget(identity, "selected_prebytes_sha256")
            ~= "8e2e44aae1e456d15513da12e097135d095ae740d579715d19e83cb65c35650b"
        or rawget(identity, "queue_prebytes_sha256")
            ~= "f63c44a5d0405f6e008755d711095ec30ac330c6b1bfcfbb43340ca8b0ed84b3"
        or type(rawget(summary, "record_count")) ~= "number"
        or rawget(summary, "record_count") ~= #snapshot.records
        or type(rawget(summary, "selected_count")) ~= "number"
        or type(rawget(summary, "queue_count")) ~= "number"
        or type(rawget(summary, "pair_count")) ~= "number"
        or type(rawget(integrity, "complete")) ~= "boolean" then
        return nil, "selected/queue snapshot identity or counts mismatch"
    end
    for index, record in ipairs(snapshot.records) do
        if type(record) ~= "table"
            or rawget(record, "seq") ~= index - 1
            or (rawget(record, "kind") ~= "selected_record"
                and rawget(record, "kind") ~= "queued_action")
            or type(rawget(record, "pair_index")) ~= "number"
            or type(rawget(record, "pawn_id")) ~= "number"
            or type(rawget(record, "current_weapon_raw")) ~= "number"
            or type(rawget(record, "base_current_weapon_raw")) ~= "number" then
            return nil, "selected/queue snapshot contains an invalid record"
        end
    end
    return true
end

local function observatory_selected_queue_snapshot_complete(snapshot)
    local integrity = rawget(snapshot, "integrity") or {}
    local summary = rawget(snapshot, "summary") or {}
    if rawget(integrity, "state") ~= "restored"
        or rawget(integrity, "complete") ~= true
        or rawget(integrity, "stopped_reason") ~= nil
        or rawget(integrity, "overflow_count") ~= 0
        or rawget(integrity, "ordering_error_count") ~= 0
        or rawget(integrity, "pointer_fault_count") ~= 0
        or rawget(integrity, "transition_mismatch_count") ~= 0
        or rawget(integrity, "wrong_thread_count") ~= 0
        or rawget(integrity, "unexpected_breakpoint_count") ~= 0
        or rawget(integrity, "torn_record_count") ~= 0
        or rawget(integrity, "debug_registers_armed") ~= false
        or rawget(integrity, "debug_registers_cleared") ~= true
        or rawget(integrity, "veh_installed") ~= false
        or rawget(integrity, "veh_removed") ~= true
        or rawget(integrity, "executable_file_released") ~= true
        or rawget(integrity, "executable_bytes_modified") ~= false
        or rawget(integrity, "seam_bytes_unchanged") ~= true
        or rawget(summary, "record_count") ~= 2
        or rawget(summary, "selected_count") ~= 1
        or rawget(summary, "queue_count") ~= 1
        or rawget(summary, "pair_count") ~= 1
        or rawget(summary, "thread_count") ~= 1
        or rawget(summary, "pending_selection") ~= false then
        return nil, "selected/queue snapshot is incomplete"
    end
    return true
end

local function validate_observatory_spawn_coordinate_snapshot(
    snapshot, capture_id
)
    if type(snapshot) ~= "table"
        or rawget(snapshot, "schema_version") ~= 1
        or rawget(snapshot, "kind")
            ~= "native_spawn_coordinate_hw_observer_snapshot"
        or rawget(snapshot, "observer_version")
            ~= "observatory-spawn-coordinate-hw-observer/1"
        or rawget(snapshot, "capture_id") ~= capture_id
        or type(rawget(snapshot, "identity")) ~= "table"
        or type(rawget(snapshot, "integrity")) ~= "table"
        or type(rawget(snapshot, "records")) ~= "table"
        or type(rawget(snapshot, "summary")) ~= "table" then
        return nil, "spawn-coordinate snapshot contract mismatch"
    end
    local identity = rawget(snapshot, "identity")
    local integrity = rawget(snapshot, "integrity")
    local summary = rawget(snapshot, "summary")
    if rawget(identity, "platform") ~= "windows"
        or rawget(identity, "architecture") ~= "x86"
        or rawget(identity, "build_id") ~= NATIVE_RNG_OBSERVER_BUILD_ID
        or rawget(identity, "executable_sha256")
            ~= NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256
        or rawget(identity, "boundary_map_sha256")
            ~= "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        or rawget(identity, "hardware_breakpoint_plan_sha256")
            ~= SPAWN_COORDINATE_HW_PLAN_SHA256
        or rawget(identity, "selector_region_sha256")
            ~= "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
        or rawget(identity, "scheduler_region_sha256")
            ~= "639ea27e48757d5c7f08499522d7f8933dc874957f4d00a74bbeec4a6750bd89"
        or rawget(identity, "scheduler_prebytes_sha256")
            ~= "419b08b2e5f923a50b9c561f72289c66c4582a38f35816d8727787cdae8f9ea7"
        or rawget(identity, "selector_fallback_prebytes_sha256")
            ~= "fd2f466614b6c81c7e73fcdb8b000dd72200a8143400bd9528bedc1d69ffd4e6"
        or rawget(identity, "selector_standard_prebytes_sha256")
            ~= "c582fb84bc51ea60cbda9c2b62bbd3a9ef4103d42654486a3569da5f8997f011"
        or type(rawget(summary, "record_count")) ~= "number"
        or rawget(summary, "record_count") ~= #snapshot.records
        or type(rawget(summary, "scheduler_count")) ~= "number"
        or type(rawget(summary, "selector_fallback_count")) ~= "number"
        or type(rawget(summary, "selector_standard_count")) ~= "number"
        or type(rawget(summary, "selector_count")) ~= "number"
        or type(rawget(integrity, "complete")) ~= "boolean" then
        return nil, "spawn-coordinate snapshot identity or counts mismatch"
    end
    if summary.record_count ~= summary.scheduler_count
            + summary.selector_fallback_count
            + summary.selector_standard_count
        or summary.selector_count ~= summary.selector_fallback_count
            + summary.selector_standard_count then
        return nil, "spawn-coordinate summary arithmetic mismatch"
    end
    local kind_counts = {
        scheduler_draw = 0,
        selector_fallback_draw = 0,
        selector_standard_draw = 0,
    }
    for index, record in ipairs(snapshot.records) do
        local kind = type(record) == "table" and rawget(record, "kind") or nil
        local candidates = type(record) == "table"
            and rawget(record, "candidates") or nil
        local candidate_count = type(record) == "table"
            and rawget(record, "candidate_count") or nil
        local selected_index = type(record) == "table"
            and rawget(record, "selected_index") or nil
        local quotient = type(record) == "table"
            and rawget(record, "rng_quotient") or nil
        local raw_rng = type(record) == "table"
            and rawget(record, "raw_rng") or nil
        if kind_counts[kind] == nil
            or rawget(record, "seq") ~= index - 1
            or type(candidate_count) ~= "number"
            or candidate_count ~= math.floor(candidate_count)
            or candidate_count < 1 or candidate_count > 64
            or type(selected_index) ~= "number"
            or selected_index ~= math.floor(selected_index)
            or selected_index < 0 or selected_index >= candidate_count
            or type(quotient) ~= "number"
            or quotient ~= math.floor(quotient)
            or quotient < 0 or quotient > 32767
            or type(raw_rng) ~= "number"
            or raw_rng ~= quotient * candidate_count + selected_index
            or type(candidates) ~= "table"
            or #candidates ~= candidate_count then
            return nil, "spawn-coordinate snapshot contains an invalid record"
        end
        local selected = candidates[selected_index + 1]
        if type(selected) ~= "table"
            or rawget(selected, "x") ~= rawget(record, "selected_x")
            or rawget(selected, "y") ~= rawget(record, "selected_y") then
            return nil, "spawn-coordinate selected candidate mismatch"
        end
        for _, candidate in ipairs(candidates) do
            if type(candidate) ~= "table"
                or type(rawget(candidate, "x")) ~= "number"
                or type(rawget(candidate, "y")) ~= "number" then
                return nil, "spawn-coordinate candidate is invalid"
            end
        end
        kind_counts[kind] = kind_counts[kind] + 1
    end
    if kind_counts.scheduler_draw ~= summary.scheduler_count
        or kind_counts.selector_fallback_draw
            ~= summary.selector_fallback_count
        or kind_counts.selector_standard_draw
            ~= summary.selector_standard_count then
        return nil, "spawn-coordinate record-kind counts mismatch"
    end
    return true
end

local function observatory_spawn_coordinate_snapshot_complete(snapshot)
    local integrity = rawget(snapshot, "integrity") or {}
    local summary = rawget(snapshot, "summary") or {}
    if rawget(integrity, "state") ~= "restored"
        or rawget(integrity, "complete") ~= true
        or rawget(integrity, "stopped_reason") ~= nil
        or rawget(integrity, "overflow_count") ~= 0
        or rawget(integrity, "candidate_error_count") ~= 0
        or rawget(integrity, "pointer_fault_count") ~= 0
        or rawget(integrity, "transition_mismatch_count") ~= 0
        or rawget(integrity, "wrong_thread_count") ~= 0
        or rawget(integrity, "unexpected_breakpoint_count") ~= 0
        or rawget(integrity, "torn_record_count") ~= 0
        or rawget(integrity, "debug_registers_armed") ~= false
        or rawget(integrity, "debug_registers_cleared") ~= true
        or rawget(integrity, "veh_installed") ~= false
        or rawget(integrity, "veh_removed") ~= true
        or rawget(integrity, "executable_file_released") ~= true
        or rawget(integrity, "executable_bytes_modified") ~= false
        or rawget(integrity, "seam_bytes_unchanged") ~= true
        or type(rawget(summary, "record_count")) ~= "number"
        or rawget(summary, "record_count") < 1
        or rawget(summary, "record_count") > 256
        or type(rawget(summary, "selector_count")) ~= "number"
        or rawget(summary, "selector_count") < 1
        or rawget(summary, "thread_count") ~= 1 then
        return nil, "spawn-coordinate snapshot is incomplete"
    end
    return true
end

local function observatory_selected_queue_scenario()
    local mission = _ITB_CURRENT_MISSION
    if not mission and GetCurrentMission then
        local mission_ok, current = pcall(GetCurrentMission)
        if mission_ok then mission = current end
    end
    if mission_bridge_id(mission) ~= "Mission_Power" then
        return nil, "selected/queue scenario requires Mission_Power"
    end
    for x = 0, 7 do
        for y = 0, 7 do
            local point = Point(x, y)
            local danger_ok, danger = pcall(function()
                return Board:IsEnvironmentDanger(point)
            end)
            if danger_ok and danger then
                return nil, "selected/queue scenario requires no environment danger"
            end
        end
    end
    rawset(mission, "InfiniteSpawn", false)
    local spawning_before = 0
    for x = 0, 7 do
        for y = 0, 7 do
            local spawn_ok, spawning = pcall(function()
                return Board:IsSpawning(Point(x, y))
            end)
            if spawn_ok and spawning then spawning_before = spawning_before + 1 end
        end
    end
    if spawning_before > 0 then
        local spawn_ok, spawn_error = pcall(function() Board:SpawnQueued() end)
        if not spawn_ok then
            return nil, "cannot consume queued spawns: " .. tostring(spawn_error)
        end
    end
    for x = 0, 7 do
        for y = 0, 7 do
            local spawn_ok, spawning = pcall(function()
                return Board:IsSpawning(Point(x, y))
            end)
            if spawn_ok and spawning then
                return nil, "queued spawn marker remained after scenario reset"
            end
        end
    end
    local enemy_ids = extract_table(Board:GetPawns(TEAM_ENEMY))
    table.sort(enemy_ids)
    for _, enemy_id in ipairs(enemy_ids) do
        local pawn = Board:GetPawn(enemy_id)
        if pawn then
            local removed, remove_error = pcall(function()
                Board:RemovePawn(pawn)
            end)
            if not removed then
                return nil, "cannot remove scenario enemy: "
                    .. tostring(remove_error)
            end
        end
    end
    if #extract_table(Board:GetPawns(TEAM_ENEMY)) ~= 0 then
        return nil, "scenario enemy reset was incomplete"
    end
    local candidates = {
        Point(4, 4), Point(4, 5), Point(5, 4), Point(3, 4),
        Point(4, 3), Point(5, 3), Point(3, 5), Point(5, 5),
    }
    local selected = nil
    for _, point in ipairs(candidates) do
        local safe_ok, safe = pcall(function()
            return Board:IsValid(point)
                and Board:GetTerrain(point) == TERRAIN_ROAD
                and not Board:IsPawnSpace(point)
                and not Board:IsItem(point)
                and not Board:IsPod(point)
                and not Board:IsFire(point)
                and not Board:IsAcid(point)
                and not Board:IsSmoke(point)
                and not Board:IsSpawning(point)
                and not Board:IsEnvironmentDanger(point)
        end)
        if safe_ok and safe then selected = point break end
    end
    if selected == nil then
        return nil, "no safe deterministic Firefly scenario tile is available"
    end
    local added_ok, added_error = pcall(function()
        Board:AddPawn("Firefly1", selected)
    end)
    if not added_ok then
        return nil, "cannot add deterministic Firefly: " .. tostring(added_error)
    end
    local pawn = Board:GetPawn(selected)
    if not pawn or pawn:GetTeam() ~= TEAM_ENEMY
        or pawn:GetType() ~= "Firefly1" then
        return nil, "deterministic Firefly identity mismatch"
    end
    local clear_ok, clear_error = pcall(function() pawn:ClearQueued() end)
    if not clear_ok then
        return nil, "cannot clear deterministic Firefly queue: "
            .. tostring(clear_error)
    end
    local final_ids = extract_table(Board:GetPawns(TEAM_ENEMY))
    if #final_ids ~= 1 or final_ids[1] ~= pawn:GetId() then
        return nil, "selected/queue scenario is not one-enemy exact"
    end
    return {
        pawn_id = pawn:GetId(),
        pawn_type = pawn:GetType(),
        x = selected.x,
        y = selected.y,
        consumed_spawn_count = spawning_before,
    }
end

local function run_observatory_selected_queue_trial(condition, capture_id)
    local command_name = "OBS_SELECTED_QUEUE_TRIAL"
    if condition ~= "control" and condition ~= "dormant"
        and condition ~= "armed" then
        return nil, command_name .. " condition is invalid"
    end
    if not valid_observatory_capture_id(capture_id)
        or string.len(capture_id) > 96 then
        return nil, command_name .. " capture ID is invalid"
    end
    if not Board or not Game then
        return nil, command_name .. " requires an active mission"
    end
    local team_ok, team_turn = pcall(function() return Game:GetTeamTurn() end)
    if not team_ok or team_turn ~= TEAM_PLAYER then
        return nil, command_name .. " requires combat_player"
    end
    if _observatory_selected_queue_module ~= nil then
        return nil, "selected/queue observer is already consumed"
    end
    if observatory_path_exists(SELECTED_QUEUE_SNAPSHOT_FILE)
        or observatory_path_exists(SELECTED_QUEUE_SNAPSHOT_TMP) then
        return nil, "selected/queue snapshot output already exists"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local seed_helper, seed_helper_error = load_observatory_rng_seed_helper(
        directory,
        {
            helper_version = "observatory-rng-seed-helper/1",
            helper_sha256 = NATIVE_RNG_SEED_HELPER_SHA256,
            executable_sha256 = NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256,
            architecture = "x86",
            build_id = NATIVE_RNG_OBSERVER_BUILD_ID,
            rng_seed_rva = "0x00387f37",
            rng_seed_region_sha256 = NATIVE_RNG_SEED_REGION_SHA256,
        }
    )
    if not seed_helper then return nil, tostring(seed_helper_error) end
    local gameflow, gameflow_error =
        load_observatory_native_gameflow_helper(directory)
    if not gameflow then return nil, tostring(gameflow_error) end
    local observer = nil
    if condition ~= "control" then
        local observer_error = nil
        observer, observer_error =
            load_observatory_selected_queue_module(directory)
        if not observer then return nil, tostring(observer_error) end
    end
    local scenario, scenario_error = observatory_selected_queue_scenario()
    if not scenario then return nil, tostring(scenario_error) end
    local mech_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
    for _, mech_id in ipairs(mech_ids) do
        local mech = Board:GetPawn(mech_id)
        if mech and not mech:IsDead() then mech:SetActive(false) end
    end
    local seed_ok, seeded = pcall(
        rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED
    )
    if not seed_ok or seeded ~= true then
        return nil, "selected/queue seed failed: " .. tostring(seeded)
    end
    if condition == "armed" then
        _observatory_selected_queue_module = observer
        local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
        if not arm_ok or armed ~= true then
            pcall(rawget(observer, "finish"))
            return nil, "selected/queue arm failed: " .. tostring(armed)
        end
        local status_ok, status = pcall(rawget(observer, "status"))
        if not status_ok or type(status) ~= "table"
            or rawget(status, "state") ~= "capturing"
            or rawget(status, "debug_registers_armed") ~= true then
            pcall(rawget(observer, "finish"))
            return nil, "selected/queue arm status mismatch"
        end
    end
    local start_count = -1
    pcall(function() start_count = Game:GetTurnCount() end)
    local end_ok, invoked = pcall(rawget(gameflow, "end_player_turn"))
    if not end_ok or invoked ~= true then
        if condition == "armed" then pcall(rawget(observer, "finish")) end
        return nil, "selected/queue native End Turn failed: "
            .. tostring(invoked)
    end
    local advanced = wait_until_coro(function()
        if Board:IsBusy() then return false end
        local current_count = -1
        local current_team = -1
        pcall(function() current_count = Game:GetTurnCount() end)
        pcall(function() current_team = Game:GetTeamTurn() end)
        return current_count > start_count and current_team == TEAM_PLAYER
    end, 60)
    if not advanced then
        if condition == "armed" then pcall(rawget(observer, "finish")) end
        return nil, "selected/queue turn transition timed out"
    end
    local record_count = 0
    if condition == "armed" then
        local finish_ok, snapshot = pcall(rawget(observer, "finish"))
        if not finish_ok or type(snapshot) ~= "table" then
            return nil, "selected/queue finish failed: " .. tostring(snapshot)
        end
        local valid, validation_error =
            validate_observatory_selected_queue_snapshot(snapshot, capture_id)
        if not valid then return nil, tostring(validation_error) end
        local wrote, write_error = write_observatory_create_only_json(
            SELECTED_QUEUE_SNAPSHOT_FILE,
            SELECTED_QUEUE_SNAPSHOT_TMP,
            snapshot,
            256 * 1024
        )
        if not wrote then
            return nil, "selected/queue snapshot output failed: "
                .. tostring(write_error)
        end
        record_count = rawget(snapshot.summary, "record_count") or 0
        local complete, complete_error =
            observatory_selected_queue_snapshot_complete(snapshot)
        if not complete then return nil, tostring(complete_error) end
    end
    return command_name .. " condition=" .. condition
        .. " capture=" .. capture_id
        .. " pawn=" .. tostring(scenario.pawn_id)
        .. " type=" .. tostring(scenario.pawn_type)
        .. " at=" .. tostring(scenario.x) .. "," .. tostring(scenario.y)
        .. " consumed_spawns=" .. tostring(scenario.consumed_spawn_count)
        .. " records=" .. tostring(record_count)
        .. " complete=true"
end

local function prepare_observatory_spawn_coordinate_trial(
    condition, capture_id
)
    local command_name = "OBS_SPAWN_COORDINATE_PREPARE"
    if condition ~= "control" and condition ~= "dormant"
        and condition ~= "armed" then
        return nil, command_name .. " condition is invalid"
    end
    if not valid_observatory_capture_id(capture_id)
        or string.len(capture_id) > 96 then
        return nil, command_name .. " capture ID is invalid"
    end
    if not Board or not Game then
        return nil, command_name .. " requires an active mission"
    end
    local mission = _ITB_CURRENT_MISSION
    if not mission and GetCurrentMission then
        local mission_ok, current = pcall(GetCurrentMission)
        if mission_ok then mission = current end
    end
    if mission_bridge_id(mission) ~= "Mission_Power" then
        return nil, command_name .. " requires Mission_Power"
    end
    local team_ok, team_turn = pcall(function() return Game:GetTeamTurn() end)
    if not team_ok or team_turn ~= TEAM_PLAYER then
        return nil, command_name .. " requires combat_player"
    end
    local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
    for _, actor_id in ipairs(actor_ids) do
        local actor = Board:GetPawn(actor_id)
        local active_ok, active = pcall(function()
            return actor and actor:IsActive()
        end)
        if active_ok and active then
            return nil, command_name .. " requires spent player actors"
        end
    end
    if _observatory_spawn_coordinate_condition ~= nil
        or _observatory_spawn_coordinate_module ~= nil then
        return nil, "spawn-coordinate boundary is already consumed"
    end
    if observatory_path_exists(SPAWN_COORDINATE_SNAPSHOT_FILE)
        or observatory_path_exists(SPAWN_COORDINATE_SNAPSHOT_TMP) then
        return nil, "spawn-coordinate snapshot output already exists"
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local seed_helper, seed_helper_error = load_observatory_rng_seed_helper(
        directory,
        {
            helper_version = "observatory-rng-seed-helper/1",
            helper_sha256 = NATIVE_RNG_SEED_HELPER_SHA256,
            executable_sha256 = NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256,
            architecture = "x86",
            build_id = NATIVE_RNG_OBSERVER_BUILD_ID,
            rng_seed_rva = "0x00387f37",
            rng_seed_region_sha256 = NATIVE_RNG_SEED_REGION_SHA256,
        }
    )
    if not seed_helper then return nil, tostring(seed_helper_error) end
    local observer = nil
    if condition ~= "control" then
        local observer_error = nil
        observer, observer_error =
            load_observatory_spawn_coordinate_module(directory)
        if not observer then return nil, tostring(observer_error) end
    end
    local seed_ok, seeded = pcall(
        rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED
    )
    if not seed_ok or seeded ~= true then
        return nil, "spawn-coordinate seed failed: " .. tostring(seeded)
    end
    if condition == "armed" then
        local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
        if not arm_ok or armed ~= true then
            pcall(rawget(observer, "finish"))
            return nil, "spawn-coordinate arm failed: " .. tostring(armed)
        end
        local status_ok, status = pcall(rawget(observer, "status"))
        if not status_ok or type(status) ~= "table"
            or rawget(status, "state") ~= "capturing"
            or rawget(status, "debug_registers_armed") ~= true then
            pcall(rawget(observer, "finish"))
            return nil, "spawn-coordinate arm status mismatch"
        end
    end
    _observatory_spawn_coordinate_module = observer or false
    _observatory_spawn_coordinate_condition = condition
    _observatory_spawn_coordinate_capture_id = capture_id
    _observatory_spawn_coordinate_restored = false
    return command_name .. " condition=" .. condition
        .. " capture=" .. capture_id
        .. " seed=" .. tostring(NATIVE_RNG_FIXED_SEED)
        .. " armed=" .. tostring(condition == "armed")
end

local function finish_observatory_spawn_coordinate_trial(capture_id)
    local command_name = "OBS_SPAWN_COORDINATE_FINISH"
    if capture_id ~= _observatory_spawn_coordinate_capture_id
        or _observatory_spawn_coordinate_condition == nil then
        return nil, command_name .. " capture does not match prepared boundary"
    end
    local condition = _observatory_spawn_coordinate_condition
    local summary = {
        record_count = 0,
        scheduler_count = 0,
        selector_fallback_count = 0,
        selector_standard_count = 0,
        selector_count = 0,
    }
    if condition == "armed" then
        local observer = _observatory_spawn_coordinate_module
        local finish_ok, snapshot = pcall(rawget(observer, "finish"))
        if not finish_ok or type(snapshot) ~= "table" then
            return nil, "spawn-coordinate finish failed: " .. tostring(snapshot)
        end
        local integrity = rawget(snapshot, "integrity") or {}
        _observatory_spawn_coordinate_restored =
            rawget(integrity, "state") == "restored"
            and rawget(integrity, "debug_registers_armed") == false
            and rawget(integrity, "debug_registers_cleared") == true
            and rawget(integrity, "veh_installed") == false
            and rawget(integrity, "veh_removed") == true
            and rawget(integrity, "executable_file_released") == true
            and rawget(integrity, "executable_bytes_modified") == false
            and rawget(integrity, "seam_bytes_unchanged") == true
        _observatory_spawn_coordinate_module = false
        if not _observatory_spawn_coordinate_restored then
            return nil, "spawn-coordinate finish could not prove clean restore"
        end
        local valid, validation_error =
            validate_observatory_spawn_coordinate_snapshot(snapshot, capture_id)
        if not valid then return nil, tostring(validation_error) end
        local complete, complete_error =
            observatory_spawn_coordinate_snapshot_complete(snapshot)
        if not complete then return nil, tostring(complete_error) end
        local wrote, write_error = write_observatory_create_only_json(
            SPAWN_COORDINATE_SNAPSHOT_FILE,
            SPAWN_COORDINATE_SNAPSHOT_TMP,
            snapshot,
            2 * 1024 * 1024
        )
        if not wrote then
            return nil, "spawn-coordinate snapshot output failed: "
                .. tostring(write_error)
        end
        summary = rawget(snapshot, "summary") or summary
    end
    _observatory_spawn_coordinate_condition = "finished"
    return command_name .. " condition=" .. condition
        .. " capture=" .. capture_id
        .. " records=" .. tostring(summary.record_count or 0)
        .. " scheduler=" .. tostring(summary.scheduler_count or 0)
        .. " fallback=" .. tostring(summary.selector_fallback_count or 0)
        .. " standard=" .. tostring(summary.selector_standard_count or 0)
        .. " selectors=" .. tostring(summary.selector_count or 0)
        .. " complete=true"
end

local function abort_observatory_spawn_coordinate_trial(capture_id)
    local command_name = "OBS_SPAWN_COORDINATE_ABORT"
    if capture_id ~= _observatory_spawn_coordinate_capture_id
        or _observatory_spawn_coordinate_condition == nil then
        return nil, command_name .. " capture does not match prepared boundary"
    end
    local condition = _observatory_spawn_coordinate_condition
    local clean = true
    if condition == "armed" then
        local observer = _observatory_spawn_coordinate_module
        if observer == false and _observatory_spawn_coordinate_restored then
            clean = true
        elseif type(observer) ~= "table" then
            clean = false
        else
            local finish_ok, snapshot = pcall(rawget(observer, "finish"))
            local integrity = finish_ok and type(snapshot) == "table"
                and rawget(snapshot, "integrity") or {}
            clean = finish_ok
                and rawget(integrity, "state") == "restored"
                and rawget(integrity, "debug_registers_armed") == false
                and rawget(integrity, "debug_registers_cleared") == true
                and rawget(integrity, "veh_installed") == false
                and rawget(integrity, "veh_removed") == true
                and rawget(integrity, "executable_file_released") == true
                and rawget(integrity, "executable_bytes_modified") == false
                and rawget(integrity, "seam_bytes_unchanged") == true
            if clean then
                _observatory_spawn_coordinate_restored = true
                _observatory_spawn_coordinate_module = false
            end
        end
        if not clean then
            return nil, "spawn-coordinate abort could not prove clean restore"
        end
    end
    _observatory_spawn_coordinate_condition = "aborted"
    return command_name .. " condition=" .. condition
        .. " capture=" .. capture_id .. " restored=" .. tostring(clean)
end

local function observatory_trial_live_state(capsule, cached_save)
    local packet = rawget(capsule, "packet") or {}
    local manifest = rawget(packet, "manifest") or {}
    local mission_id = mission_bridge_id(_ITB_CURRENT_MISSION) or ""
    local turn = 0
    local team_turn = 0
    if Game then
        pcall(function() turn = Game:GetTurnCount() end)
        pcall(function() team_turn = Game:GetTeamTurn() end)
    end
    local phase = "unknown"
    if mission_id ~= "" and team_turn == TEAM_PLAYER then
        phase = "combat_player"
    elseif mission_id ~= "" and team_turn == TEAM_ENEMY then
        phase = "combat_enemy"
    end
    return {
        now_epoch = os.time(),
        mission_id = mission_id,
        turn = turn,
        phase = phase,
        timeline_fingerprint = manifest.timeline_fingerprint or "",
        master_seed = cached_save.master_seed,
        region_id = cached_save.region_id,
        ai_seed_fingerprint = manifest.ai_seed_fingerprint or "",
    }
end

local function initialize_observatory_rng_trial(request)
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local capsule_filename = "itb_observatory_rng_capsule_"
        .. request.capsule_sha256 .. ".lua"
    local capsule, capsule_error = load_observatory_trial_artifact(
        directory, capsule_filename, "RNG trial capsule"
    )
    if not capsule then return nil, capsule_error end
    if rawget(capsule, "schema_version") ~= 2
        or rawget(capsule, "kind") ~= "observatory_rng_trial_capsule"
        or (rawget(capsule, "capture_track") ~= "owner_local_modified"
            and rawget(capsule, "capture_track") ~= "pristine_reference")
        or type(rawget(capsule, "packet")) ~= "table"
        or type(rawget(capsule, "rng_control")) ~= "table"
        or type(rawget(capsule, "expected_save")) ~= "table" then
        return nil, "RNG trial capsule contract mismatch"
    end
    local packet = rawget(capsule, "packet")
    local trusted = rawget(packet, "trusted")
    local manifest = rawget(packet, "manifest")
    local policy = rawget(packet, "policy")
    local expected_save = rawget(capsule, "expected_save")
    if type(trusted) ~= "table"
        or type(manifest) ~= "table"
        or type(policy) ~= "table"
        or not valid_lower_sha256(rawget(trusted, "controller_sha256"))
        or not valid_observatory_capture_id(rawget(manifest, "capture_id"))
        or type(rawget(manifest, "checkpoint_seq")) ~= "number"
        or rawget(manifest, "checkpoint_seq") < 0
        or rawget(manifest, "checkpoint_seq")
            ~= math.floor(rawget(manifest, "checkpoint_seq"))
        or type(rawget(policy, "max_bundle_bytes")) ~= "number"
        or rawget(policy, "max_bundle_bytes") < 1
        or rawget(policy, "max_bundle_bytes") > 64 * 1024 * 1024 then
        return nil, "RNG trial capsule identity is invalid"
    end
    local host, host_error = load_observatory_trial_artifact(
        directory,
        "observatory_rng_trial_host.lua",
        "RNG trial host"
    )
    if not host then return nil, host_error end
    if rawget(host, "VERSION") ~= "observatory-rng-trial-host/2"
        or type(rawget(host, "new")) ~= "function" then
        return nil, "RNG trial host contract mismatch"
    end
    local controller_filename = "itb_observatory_controller_"
        .. rawget(trusted, "controller_sha256") .. ".lua"
    local controller, controller_error = load_observatory_trial_artifact(
        directory, controller_filename, "RNG trial controller"
    )
    if not controller then return nil, controller_error end
    if rawget(controller, "VERSION") ~= "observatory-controller/1"
        or type(rawget(controller, "new")) ~= "function" then
        return nil, "RNG trial controller contract mismatch"
    end
    local rng_seed_helper, rng_seed_helper_error =
        load_observatory_rng_seed_helper(
            directory,
            rawget(capsule, "rng_control")
        )
    if not rng_seed_helper then return nil, rng_seed_helper_error end

    -- Read and freeze save-derived identity before any wrapper can exist.
    -- The runtime provider below performs no file I/O; it combines these exact
    -- cached values with the live mission/turn/team sampled outside extraction.
    local save_data = _read_save_data()
    local expected_region = rawget(expected_save, "region_id")
    local region = type(save_data.mission_seeds) == "table"
        and save_data.mission_seeds[expected_region] or nil
    if save_data.master_seed ~= rawget(expected_save, "master_seed")
        or type(region) ~= "table"
        or region.ai_seed ~= rawget(expected_save, "ai_seed")
        or region.mission ~= rawget(expected_save, "mission_slot")
        or region.turn ~= rawget(expected_save, "turn") then
        return nil, "RNG trial save identity mismatch"
    end
    local cached_save = {
        master_seed = save_data.master_seed,
        region_id = expected_region,
        ai_seed = region.ai_seed,
    }
    local capture_id = rawget(manifest, "capture_id")
    local checkpoint_seq = rawget(manifest, "checkpoint_seq")
    local condition = request.condition
    local raw_path = BRIDGE_DIR .. "/itb_observatory_trace_"
        .. capture_id .. "_" .. tostring(checkpoint_seq) .. ".raw"
    local result_path = BRIDGE_DIR .. "/itb_observatory_rng_trial_"
        .. capture_id .. "_" .. condition .. ".json"
    local live_state_provider = function()
        return observatory_trial_live_state(capsule, cached_save)
    end
    local raw_writer = function(snapshot)
        return write_observatory_create_only_json(
            raw_path,
            raw_path .. ".tmp",
            snapshot,
            rawget(policy, "max_bundle_bytes")
        )
    end
    local result_writer = function(result)
        return write_observatory_create_only_json(
            result_path,
            result_path .. ".tmp",
            result,
            256 * 1024
        )
    end
    local ok, trial_or_error = pcall(
        rawget(host, "new"),
        {
            condition = condition,
            activation_nonce = request.activation_nonce,
            capsule_sha256 = request.capsule_sha256,
            capsule = capsule,
            controller_module = controller,
            rng_seed_helper = rng_seed_helper,
            hook_holder = _G,
            live_state_provider = live_state_provider,
            raw_writer = raw_writer,
            result_writer = result_writer,
        }
    )
    if not ok or type(trial_or_error) ~= "table"
        or type(rawget(trial_or_error, "step")) ~= "function" then
        return nil, "RNG trial initialization failed: "
            .. tostring(trial_or_error)
    end
    return trial_or_error
end

local function consume_observatory_rng_trial_startup_request()
    local file = io.open(RNG_TRIAL_REQUEST_FILE, "r")
    if not file then return false end
    local content = file:read(512)
    local extra = file:read(1)
    file:close()
    pcall(function() os.remove(RNG_TRIAL_REQUEST_FILE) end)
    if extra ~= nil or type(content) ~= "string" then
        return nil, "RNG trial startup request exceeds its cap"
    end
    local condition, nonce, capsule_sha256 = string.match(
        content,
        "^observatory%-rng%-trial%-request/1"
            .. "\ncondition=([a-z_]+)"
            .. "\nactivation_nonce=([0-9a-f]+)"
            .. "\ncapsule_sha256=([0-9a-f]+)\n$"
    )
    if (condition ~= "control" and condition ~= "exact_hook")
        or type(nonce) ~= "string"
        or string.len(nonce) < 32
        or string.len(nonce) > 64
        or not valid_lower_sha256(capsule_sha256) then
        return nil, "invalid RNG trial startup request"
    end
    local trial, trial_error = initialize_observatory_rng_trial({
        condition = condition,
        activation_nonce = nonce,
        capsule_sha256 = capsule_sha256,
    })
    if not trial then return nil, trial_error end
    _ITB_OBSERVATORY_RNG_TRIAL = trial
    log_bridge("OBS RNG TRIAL armed condition=" .. condition)
    return true
end

local function initialize_observatory_callback_trial(request)
    local directory, directory_error = modloader_script_directory()
    if not directory then return nil, directory_error end
    local capsule_filename = "itb_observatory_callback_capsule_"
        .. request.capsule_sha256 .. ".lua"
    local capsule, capsule_error = load_observatory_trial_artifact(
        directory, capsule_filename, "callback trial capsule"
    )
    if not capsule then return nil, capsule_error end
    if rawget(capsule, "schema_version") ~= 1
        or rawget(capsule, "kind")
            ~= "observatory_callback_trial_capsule"
        or (rawget(capsule, "capture_track") ~= "owner_local_modified"
            and rawget(capsule, "capture_track") ~= "pristine_reference")
        or type(rawget(capsule, "packet")) ~= "table"
        or type(rawget(capsule, "binding_manifest")) ~= "table"
        or type(rawget(capsule, "callback_join")) ~= "table"
        or type(rawget(capsule, "expected_save")) ~= "table"
        or not valid_lower_sha256(
            rawget(capsule, "binding_manifest_sha256")
        )
        or not valid_lower_sha256(rawget(capsule, "callback_join_sha256")) then
        return nil, "callback trial capsule contract mismatch"
    end
    local packet = rawget(capsule, "packet")
    local trusted = rawget(packet, "trusted")
    local manifest = rawget(packet, "manifest")
    local policy = rawget(packet, "policy")
    local expected_save = rawget(capsule, "expected_save")
    if type(trusted) ~= "table"
        or type(manifest) ~= "table"
        or type(policy) ~= "table"
        or rawget(manifest, "controller_version")
            ~= "observatory-callback-controller/1"
        or not valid_lower_sha256(rawget(trusted, "controller_sha256"))
        or not valid_observatory_capture_id(rawget(manifest, "capture_id"))
        or type(rawget(manifest, "checkpoint_seq")) ~= "number"
        or rawget(manifest, "checkpoint_seq") < 0
        or rawget(manifest, "checkpoint_seq")
            ~= math.floor(rawget(manifest, "checkpoint_seq"))
        or type(rawget(policy, "max_bundle_bytes")) ~= "number"
        or rawget(policy, "max_bundle_bytes") < 1
        or rawget(policy, "max_bundle_bytes") > 64 * 1024 * 1024 then
        return nil, "callback trial capsule identity is invalid"
    end
    local host, host_error = load_observatory_trial_artifact(
        directory,
        "observatory_callback_trial_host.lua",
        "callback trial host"
    )
    if not host then return nil, host_error end
    if rawget(host, "VERSION") ~= "observatory-callback-trial-host/2"
        or type(rawget(host, "new")) ~= "function" then
        return nil, "callback trial host contract mismatch"
    end
    local controller_filename = "itb_observatory_controller_"
        .. rawget(trusted, "controller_sha256") .. ".lua"
    local controller_source, controller_error = load_observatory_trial_artifact(
        directory, controller_filename, "callback trial controller"
    )
    if not controller_source then return nil, controller_error end
    if rawget(controller_source, "VERSION")
            ~= "observatory-callback-controller/1"
        or type(rawget(controller_source, "bind_runtime")) ~= "function" then
        return nil, "callback trial controller contract mismatch"
    end
    local trace_runtime, trace_error = load_observatory_trial_artifact(
        directory,
        "observatory_trace.lua",
        "callback trial trace runtime"
    )
    if not trace_runtime then return nil, trace_error end
    if rawget(trace_runtime, "VERSION") ~= "observatory-lua/1" then
        return nil, "callback trial trace runtime contract mismatch"
    end
    local bound_ok, controller = pcall(
        rawget(controller_source, "bind_runtime"), trace_runtime
    )
    if not bound_ok or type(controller) ~= "table"
        or rawget(controller, "VERSION")
            ~= "observatory-callback-controller/1"
        or type(rawget(controller, "new")) ~= "function" then
        return nil, "callback trial controller binding failed"
    end
    local callback_manifest, callback_manifest_error =
        load_observatory_callback_module()
    if not callback_manifest then return nil, callback_manifest_error end
    local callback_bindings, callback_bindings_error =
        load_observatory_callback_bindings_module()
    if not callback_bindings then return nil, callback_bindings_error end

    -- Freeze save-derived identity before the host may prepare a callback
    -- controller. The live provider below performs no file I/O while wrappers
    -- exist; it combines these cached values with the current mission boundary.
    local save_data = _read_save_data()
    local expected_region = rawget(expected_save, "region_id")
    local region = type(save_data.mission_seeds) == "table"
        and save_data.mission_seeds[expected_region] or nil
    if save_data.master_seed ~= rawget(expected_save, "master_seed")
        or type(region) ~= "table"
        or region.ai_seed ~= rawget(expected_save, "ai_seed")
        or region.mission ~= rawget(expected_save, "mission_slot")
        or region.turn ~= rawget(expected_save, "turn") then
        return nil, "callback trial save identity mismatch"
    end
    local cached_save = {
        master_seed = save_data.master_seed,
        region_id = expected_region,
        ai_seed = region.ai_seed,
    }
    local capture_id = rawget(manifest, "capture_id")
    local checkpoint_seq = rawget(manifest, "checkpoint_seq")
    local condition = request.condition
    local raw_path = BRIDGE_DIR .. "/itb_observatory_trace_"
        .. capture_id .. "_" .. tostring(checkpoint_seq) .. ".raw"
    local result_path = BRIDGE_DIR .. "/itb_observatory_callback_trial_"
        .. capture_id .. "_" .. condition .. ".json"
    local live_state_provider = function()
        return observatory_trial_live_state(capsule, cached_save)
    end
    local raw_writer = function(snapshot)
        return write_observatory_create_only_json(
            raw_path,
            raw_path .. ".tmp",
            snapshot,
            rawget(policy, "max_bundle_bytes")
        )
    end
    local result_writer = function(result)
        return write_observatory_create_only_json(
            result_path,
            result_path .. ".tmp",
            result,
            256 * 1024
        )
    end
    local ok, trial_or_error = pcall(
        rawget(host, "new"),
        {
            condition = condition,
            activation_nonce = request.activation_nonce,
            capsule_sha256 = request.capsule_sha256,
            capsule = capsule,
            controller_module = controller,
            callback_manifest_module = callback_manifest,
            callback_bindings_module = callback_bindings,
            live_state_provider = live_state_provider,
            raw_writer = raw_writer,
            result_writer = result_writer,
            globals = _G,
        }
    )
    if not ok or type(trial_or_error) ~= "table"
        or type(rawget(trial_or_error, "step")) ~= "function" then
        return nil, "callback trial initialization failed: "
            .. tostring(trial_or_error)
    end
    return trial_or_error
end

local function consume_observatory_callback_trial_startup_request()
    local file = io.open(CALLBACK_TRIAL_REQUEST_FILE, "r")
    if not file then return false end
    local content = file:read(512)
    local extra = file:read(1)
    file:close()
    pcall(function() os.remove(CALLBACK_TRIAL_REQUEST_FILE) end)
    if extra ~= nil or type(content) ~= "string" then
        return nil, "callback trial startup request exceeds its cap"
    end
    local condition, nonce, capsule_sha256, continue_helper_sha256
    condition, nonce, capsule_sha256 = string.match(
        content,
        "^observatory%-callback%-trial%-request/1"
            .. "\ncondition=([a-z_]+)"
            .. "\nactivation_nonce=([0-9a-f]+)"
            .. "\ncapsule_sha256=([0-9a-f]+)\n$"
    )
    if condition == nil then
        condition, nonce, capsule_sha256, continue_helper_sha256 = string.match(
            content,
            "^observatory%-callback%-trial%-request/2"
                .. "\ncondition=([a-z_]+)"
                .. "\nactivation_nonce=([0-9a-f]+)"
                .. "\ncapsule_sha256=([0-9a-f]+)"
                .. "\ncontinue_helper_sha256=([0-9a-f]+)\n$"
        )
    end
    if (condition ~= "control" and condition ~= "exact_hook")
        or type(nonce) ~= "string"
        or string.len(nonce) < 32
        or string.len(nonce) > 64
        or not valid_lower_sha256(capsule_sha256)
        or (continue_helper_sha256 ~= nil
            and not valid_lower_sha256(continue_helper_sha256)) then
        return nil, "invalid callback trial startup request"
    end
    local request = {
        condition = condition,
        activation_nonce = nonce,
        capsule_sha256 = capsule_sha256,
    }
    local gameflow = nil
    if continue_helper_sha256 ~= nil then
        local directory, directory_error = modloader_script_directory()
        if not directory then
            return nil, directory_error
        end
        local helper, helper_error =
            load_observatory_callback_gameflow_helper(
                directory, continue_helper_sha256
            )
        if not helper then
            return nil, helper_error
        end
        gameflow = helper
    end
    local trial, trial_error = initialize_observatory_callback_trial(request)
    local roots_not_loaded = type(trial_error) == "string"
        and string.find(
            trial_error,
            "callback trial initialization failed: invalid roots",
            1,
            true
        ) ~= nil
    if not trial and not (gameflow ~= nil and roots_not_loaded) then
        return nil, trial_error
    end
    if trial then _ITB_OBSERVATORY_CALLBACK_TRIAL = trial end
    if gameflow ~= nil then
        local invoked_ok, invoked = pcall(
            rawget(gameflow, "continue_saved_timeline")
        )
        if not invoked_ok or invoked ~= true then
            local invoke_error = "title Continue helper invocation failed: "
                .. tostring(invoked)
            if trial then
                pcall(rawget(trial, "abort"), trial, invoke_error)
            end
            _ITB_OBSERVATORY_CALLBACK_TRIAL = nil
            return nil, invoke_error
        end
        _ITB_OBSERVATORY_CALLBACK_GAMEFLOW = gameflow
        local status_ok, continue_status = pcall(
            rawget(gameflow, "continue_status")
        )
        if not status_ok
            or (continue_status ~= "pending"
                and continue_status ~= "invoked") then
            _ITB_OBSERVATORY_CALLBACK_TRIAL = nil
            _ITB_OBSERVATORY_CALLBACK_GAMEFLOW = nil
            return nil, "title Continue bootstrap status is invalid"
        end
        log_bridge(
            "OBS CALLBACK TRIAL title Continue bootstrap accepted status="
            .. continue_status
        )
    end
    if trial then
        log_bridge("OBS CALLBACK TRIAL armed condition=" .. condition)
    else
        _ITB_OBSERVATORY_CALLBACK_PENDING = {
            request = request,
            attempts = 0,
        }
        log_bridge(
            "OBS CALLBACK TRIAL pending mission callback roots condition="
            .. condition
        )
    end
    return true
end

local function execute_command(cmd_str)
    local parts = {}
    for word in cmd_str:gmatch("%S+") do
        parts[#parts + 1] = word
    end

    if #parts == 0 then
        write_ack("ERROR: empty command")
        return
    end

    -- Parse optional sequence ID prefix: #NNN
    _cmd_seq = nil
    if parts[1]:sub(1,1) == "#" then
        _cmd_seq = parts[1]:sub(2)
        table.remove(parts, 1)
        if #parts == 0 then
            write_ack("ERROR: empty command after sequence ID")
            return
        end
    end

    local cmd = parts[1]

    if cmd == "MOVE" then
        -- MOVE uid x y (does NOT deactivate — follow with ATTACK/REPAIR/SKIP)
        local uid = tonumber(parts[2])
        local x, y = tonumber(parts[3]), tonumber(parts[4])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local ok, err = move_pawn_for_bridge(pawn, Point(x, y))
        if not ok then
            write_ack("ERROR: Move failed: " .. tostring(err))
            return
        end
        wait_for_board_coro()
        write_ack("OK MOVE " .. uid .. " to " .. x .. "," .. y .. " [" .. err .. "]")

    elseif cmd == "ATTACK" then
        -- ATTACK uid weapon_slot target_x target_y
        -- weapon_slot is 0-based index (0=primary, 1=secondary)
        local uid = tonumber(parts[2])
        local weapon_slot = tonumber(parts[3])
        local tx, ty = tonumber(parts[4]), tonumber(parts[5])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        if weapon_slot == nil then
            write_ack("ERROR: invalid weapon slot '" .. tostring(parts[3]) .. "'")
            return
        end
        local ok, method = execute_weapon_by_slot(pawn, weapon_slot, tx, ty)
        if not ok then
            write_ack("ERROR: " .. method)
            return
        end
        wait_for_board_coro()
        pawn:SetActive(false)
        write_ack("OK ATTACK " .. uid .. " slot=" .. weapon_slot .. " at " ..
                  tx .. "," .. ty .. " [" .. method .. "]")

    elseif cmd == "TWO_CLICK_ATTACK" then
        -- TWO_CLICK_ATTACK uid weapon_slot target1_x target1_y target2_x target2_y
        -- weapon_slot is 0-based index (0=primary, 1=secondary)
        local uid = tonumber(parts[2])
        local weapon_slot = tonumber(parts[3])
        local tx1, ty1 = tonumber(parts[4]), tonumber(parts[5])
        local tx2, ty2 = tonumber(parts[6]), tonumber(parts[7])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        if weapon_slot == nil then
            write_ack("ERROR: invalid weapon slot '" .. tostring(parts[3]) .. "'")
            return
        end
        local ok, method = execute_two_click_by_slot(
            pawn, weapon_slot, tx1, ty1, tx2, ty2
        )
        if not ok then
            write_ack("ERROR: " .. method)
            return
        end
        wait_for_board_coro()
        pawn:SetActive(false)
        write_ack("OK TWO_CLICK_ATTACK " .. uid .. " slot=" .. weapon_slot ..
                  " at " .. tx1 .. "," .. ty1 .. " and " ..
                  tx2 .. "," .. ty2 .. " [" .. method .. "]")

    elseif cmd == "MOVE_ATTACK" then
        -- MOVE_ATTACK uid mx my weapon_slot tx ty
        -- weapon_slot is 0-based index (0=primary, 1=secondary)
        local uid = tonumber(parts[2])
        local mx, my = tonumber(parts[3]), tonumber(parts[4])
        local weapon_slot = tonumber(parts[5])
        local tx, ty = tonumber(parts[6]), tonumber(parts[7])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        if weapon_slot == nil then
            write_ack("ERROR: invalid weapon slot '" .. tostring(parts[5]) .. "'")
            return
        end
        local ok1, err1 = move_pawn_for_bridge(pawn, Point(mx, my))
        if not ok1 then
            write_ack("ERROR: Move failed: " .. tostring(err1))
            return
        end
        wait_for_board_coro()
        local ok2, method = execute_weapon_by_slot(pawn, weapon_slot, tx, ty)
        if not ok2 then
            write_ack("ERROR: " .. method)
            return
        end
        wait_for_board_coro()
        pawn:SetActive(false)
        write_ack("OK MOVE_ATTACK " .. uid .. " [" .. method .. "]")

    elseif cmd == "SKIP" then
        -- SKIP uid — mech takes no action this turn
        local uid = tonumber(parts[2])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        pawn:SetActive(false)
        write_ack("OK SKIP " .. uid)

    elseif cmd == "REPAIR" then
        -- REPAIR uid — mech repairs at current position
        local uid = tonumber(parts[2])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local pos = pawn:GetSpace()
        local method = "unknown"
        local ok, err = pcall(function()
            local effect_remove = _G["EFFECT_REMOVE"] or 2
            local boosted = false
            local ok_bo, bo = pcall(function() return pawn:IsBoosted() end)
            if ok_bo and bo then boosted = true end
            local save_data = _read_save_data()
            local max_hp = get_pawn_max_health(pawn, uid, save_data)
            local heal = boosted and 2 or 1

            -- Board:AddEffect(Skill_Repair:GetSkillEffect(...)) can ACK while
            -- doing nothing from the bridge command context. Mutate HP/status
            -- directly so verify sees the live board update.
            local new_hp = direct_repair_pawn(
                pawn, uid, heal, save_data, effect_remove)

            local mass_repair = false
            local ok_mass, has_mass = pcall(function()
                local fn = _G["IsPassiveSkill"]
                return type(fn) == "function" and fn("Mass_Repair")
            end)
            mass_repair = ok_mass and has_mass and true or false
            if mass_repair then
                local mech_team = _G["TEAM_MECH"] or TEAM_PLAYER
                local mech_ids = extract_table(Board:GetPawns(mech_team))
                for _, mid in ipairs(mech_ids) do
                    if mid ~= uid then
                        local target = Board:GetPawn(mid)
                        if target then
                            direct_repair_pawn(
                                target, mid, heal, save_data, effect_remove)
                        end
                    end
                end
            end

            -- Direct SpaceDamage is not a normal ability use, so consume Boost
            -- manually. Kai's Arrogant Boost is state-based and returns if the
            -- repair leaves the mech at full HP.
            local save_pilot = save_data.pilots[uid]
            local is_kai = save_pilot and save_pilot.id == "Pilot_Arrogant"
            local desired_boosted = is_kai and new_hp >= max_hp
            if boosted or desired_boosted then
                for _, mname in ipairs({"SetBoosted", "SetBoost"}) do
                    local ok_set, did_set = pcall(function()
                        local fn = pawn[mname]
                        if type(fn) == "function" then
                            fn(pawn, desired_boosted)
                            return true
                        end
                        return false
                    end)
                    if ok_set and did_set then break end
                end
            end

            local is_repairman = save_pilot and save_pilot.id == "Pilot_Repairman"
            local ok_power, has_power = pcall(function()
                return pawn:IsAbility("Power_Repair")
            end)
            if ok_power and has_power then is_repairman = true end
            if is_repairman then
                for i = DIR_START, DIR_END do
                    local adj = pos + DIR_VECTORS[i]
                    Board:DamageSpace(SpaceDamage(adj, 0, i))
                end
            end
            method = boosted and "direct_repair_boosted" or "direct_repair"
            if mass_repair then method = method .. "_mass" end
        end)
        if not ok then
            write_ack("ERROR: Repair failed: " .. tostring(err))
            return
        end
        wait_for_board_coro()
        pawn:SetActive(false)
        write_ack("OK REPAIR " .. uid .. " [" .. method .. "]")

    elseif cmd == "DEPLOY" then
        -- DEPLOY uid x y — place mech at tile during deployment
        local uid = tonumber(parts[2])
        local x, y = tonumber(parts[3]), tonumber(parts[4])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local ok, err = pcall(function() pawn:SetSpace(Point(x, y)) end)
        if not ok then
            write_ack("ERROR: Deploy failed: " .. tostring(err))
            return
        end
        write_ack("OK DEPLOY " .. uid .. " at " .. x .. "," .. y)

    elseif cmd == "END_TURN" then
        local method = "unknown"
        local start_count = -1
        pcall(function() start_count = Game:GetTurnCount() end)
        local ok, err = pcall(function()
            if Game and Game.EndTurn then
                Game:EndTurn()
                method = "EndTurn"
            elseif GetGame then
                local g = GetGame()
                if g and g.EndTurn then
                    g:EndTurn()
                    method = "GetGame"
                else
                    error("no EndTurn method available")
                end
            else
                error("no Game/GetGame available")
            end
        end)
        if not ok then
            -- Game:EndTurn() does not exist on this ITB build. Keep the normal
            -- bridge contract click-only, but an armed Observatory callback
            -- trial may use its exact-build, one-shot native UI action. The
            -- helper is loaded only by the content-addressed startup request.
            log_bridge("WARN: EndTurn() failed (" .. tostring(err) ..
                       "); trying reviewed fallback")
            method = "SetActive"
            local ok2, err2 = pcall(function()
                local mech_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
                for _, mid in ipairs(mech_ids) do
                    local m = Board:GetPawn(mid)
                    if m then m:SetActive(false) end
                end
            end)
            if not ok2 then
                write_ack("ERROR: END_TURN failed: " .. tostring(err2))
                log_bridge("END_TURN ERROR: " .. tostring(err2))
                return
            end
            local gameflow = rawget(
                _G, "_ITB_OBSERVATORY_CALLBACK_GAMEFLOW"
            )
            local trial = rawget(_G, "_ITB_OBSERVATORY_CALLBACK_TRIAL")
            local native_diagnostic = false
            if type(trial) ~= "table"
                and type(_observatory_native_gameflow) == "table" then
                gameflow = _observatory_native_gameflow
                native_diagnostic = true
            end
            if (type(trial) == "table" or native_diagnostic)
                and type(gameflow) == "table"
                and rawget(gameflow, "VERSION")
                    == "observatory-callback-gameflow-helper/6"
                and type(rawget(gameflow, "end_player_turn"))
                    == "function" then
                local native_ok, invoked = pcall(
                    rawget(gameflow, "end_player_turn")
                )
                if native_diagnostic then
                    _observatory_native_gameflow = nil
                end
                if not native_ok or invoked ~= true then
                    write_ack(
                        "ERROR: Observatory native End Turn failed: "
                        .. tostring(invoked)
                    )
                    log_bridge(
                        "END_TURN OBSERVATORY ERROR: " .. tostring(invoked)
                    )
                    return
                end
                method = "observatory_native"
                if native_diagnostic then
                    log_bridge("OBS NATIVE DIAGNOSTIC End Turn invoked")
                else
                    log_bridge("OBS CALLBACK TRIAL native End Turn invoked")
                end
            else
                write_ack("NEEDS_MCP_CLICK END_TURN method=SetActive")
                return
            end
        end
        -- Wait for the full player→enemy→player cycle.
        local advanced = wait_until_coro(function()
            if Board:IsBusy() then return false end
            local cur_count = -1
            pcall(function() cur_count = Game:GetTurnCount() end)
            return cur_count > start_count
        end, 60)
        if not advanced then
            write_ack(
                "ERROR: END_TURN transition timed out method=" .. method
            )
            return
        end
        local phase = "unknown"
        if Game then
            local ok_tt, tt = pcall(function() return Game:GetTeamTurn() end)
            if ok_tt then
                if tt == 1 then phase = "combat_player"
                elseif tt == 6 then phase = "combat_enemy"
                end
            end
        end
        write_ack("OK END_TURN phase=" .. phase .. " method=" .. method)

    elseif cmd == "SET_SPEED" then
        -- SET_SPEED fast|visual
        local mode = parts[2] or "fast"
        if mode == "fast" or mode == "visual" then
            _bridge_speed = mode
            write_ack("OK SET_SPEED " .. mode)
            return
        else
            write_ack("ERROR: invalid speed: " .. mode .. " (use fast or visual)")
            return
        end

    elseif cmd == "UI_PROBE" then
        -- Read-only probe for pause/menu/UI state candidates. Intended for
        -- before/after Esc comparisons; every candidate is protected by pcall.
        local ok, result = pcall(ui_probe_menu_state)
        if ok then
            write_ack("OK UI_PROBE " .. json_encode(result))
        else
            write_ack("ERROR: UI_PROBE failed: " .. tostring(result))
        end
        return

    elseif cmd == "OBS_CALLBACK_MANIFEST" then
        -- Explicit, read-only Observatory operation. The sibling module is
        -- loaded only for this command; it resolves exact enemy Skill roots
        -- with raw table access and never invokes a candidate callback.
        if #parts ~= 1 then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST accepts no arguments")
            return
        end
        local module, module_error = load_observatory_callback_module()
        if not module then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST " .. module_error)
            return
        end
        local roots_ok, roots, roots_error = pcall(
            rawget(module, "discover_enemy_skill_roots"), _G
        )
        if not roots_ok then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST root discovery failed: "
                .. tostring(roots))
            return
        end
        if type(roots) ~= "table" then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST root discovery failed: "
                .. tostring(roots_error))
            return
        end
        local manifest_ok, manifest, manifest_error = pcall(
            rawget(module, "enumerate"),
            roots,
            {
                max_roots = 256,
                max_depth = 16,
                max_functions = 1024,
                max_text_bytes = 512,
            }
        )
        if not manifest_ok then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST enumeration failed: "
                .. tostring(manifest))
            return
        end
        if type(manifest) ~= "table" then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST enumeration failed: "
                .. tostring(manifest_error))
            return
        end
        local wrote, write_error = write_observatory_callback_manifest(
            json_encode(manifest)
        )
        if not wrote then
            write_ack("ERROR: OBS_CALLBACK_MANIFEST output failed: "
                .. tostring(write_error))
            return
        end
        local summary = rawget(manifest, "summary") or {}
        write_ack(
            "OK OBS_CALLBACK_MANIFEST roots="
            .. tostring(rawget(summary, "root_count") or -1)
            .. " functions="
            .. tostring(rawget(summary, "function_count") or -1)
        )
        return

    elseif cmd == "OBS_CALLBACK_BINDINGS" then
        -- Explicit, inert slot enumeration. This command calls no candidate
        -- callback and installs no wrapper; it only groups the exact raw table
        -- fields that supply the already-enumerated callback identities.
        if #parts ~= 1 then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS accepts no arguments")
            return
        end
        local manifest_module, manifest_error =
            load_observatory_callback_module()
        if not manifest_module then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS " .. manifest_error)
            return
        end
        local bindings_module, bindings_error =
            load_observatory_callback_bindings_module()
        if not bindings_module then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS " .. bindings_error)
            return
        end
        local enumerate_ok, document, _live_bindings, enumerate_error = pcall(
            rawget(bindings_module, "enumerate"),
            _G,
            manifest_module,
            {
                max_roots = 256,
                max_depth = 16,
                max_functions = 1024,
                max_text_bytes = 512,
            }
        )
        if not enumerate_ok then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS enumeration failed: "
                .. tostring(document))
            return
        end
        if type(document) ~= "table" then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS enumeration failed: "
                .. tostring(enumerate_error))
            return
        end
        local wrote, write_error = write_observatory_callback_bindings(
            json_encode(document)
        )
        if not wrote then
            write_ack("ERROR: OBS_CALLBACK_BINDINGS output failed: "
                .. tostring(write_error))
            return
        end
        local summary = rawget(document, "summary") or {}
        write_ack(
            "OK OBS_CALLBACK_BINDINGS roots="
            .. tostring(rawget(summary, "root_count") or -1)
            .. " functions="
            .. tostring(rawget(summary, "function_count") or -1)
            .. " slots="
            .. tostring(rawget(summary, "slot_count") or -1)
        )
        return

    elseif cmd == "OBS_SPAWN_COORDINATE_PREPARE" then
        if #parts ~= 3 then
            write_ack(
                "ERROR: OBS_SPAWN_COORDINATE_PREPARE requires condition and capture ID"
            )
            return
        end
        local completed, trial_error =
            prepare_observatory_spawn_coordinate_trial(parts[2], parts[3])
        if not completed then
            write_ack("ERROR: OBS_SPAWN_COORDINATE_PREPARE "
                .. tostring(trial_error))
            return
        end
        write_ack("OK " .. completed)
        return

    elseif cmd == "OBS_SPAWN_COORDINATE_FINISH" then
        if #parts ~= 2 then
            write_ack(
                "ERROR: OBS_SPAWN_COORDINATE_FINISH requires capture ID"
            )
            return
        end
        local completed, trial_error =
            finish_observatory_spawn_coordinate_trial(parts[2])
        if not completed then
            write_ack("ERROR: OBS_SPAWN_COORDINATE_FINISH "
                .. tostring(trial_error))
            return
        end
        write_ack("OK " .. completed)
        return

    elseif cmd == "OBS_SPAWN_COORDINATE_ABORT" then
        if #parts ~= 2 then
            write_ack(
                "ERROR: OBS_SPAWN_COORDINATE_ABORT requires capture ID"
            )
            return
        end
        local completed, trial_error =
            abort_observatory_spawn_coordinate_trial(parts[2])
        if not completed then
            write_ack("ERROR: OBS_SPAWN_COORDINATE_ABORT "
                .. tostring(trial_error))
            return
        end
        write_ack("OK " .. completed)
        return

    elseif cmd == "OBS_SELECTED_QUEUE_TRIAL" then
        if #parts ~= 3 then
            write_ack(
                "ERROR: OBS_SELECTED_QUEUE_TRIAL requires condition and capture ID"
            )
            return
        end
        local completed, trial_error =
            run_observatory_selected_queue_trial(parts[2], parts[3])
        if not completed then
            write_ack("ERROR: OBS_SELECTED_QUEUE_TRIAL "
                .. tostring(trial_error))
            return
        end
        write_ack("OK " .. completed)
        return

    elseif cmd == "OBS_NATIVE_RNG_SEED" then
        -- Fixed build-keyed seed control for matched native-observer trials.
        -- The command accepts no seed input and is permitted only after all
        -- player actors are spent, immediately before the End Turn click.
        if #parts ~= 1 or not Board or not Game then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED requires an active mission")
            return
        end
        local team_ok, team_turn = pcall(function()
            return Game:GetTeamTurn()
        end)
        if not team_ok or team_turn ~= TEAM_PLAYER then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED requires combat_player")
            return
        end
        local actors_spent = true
        local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
        for _, actor_id in ipairs(actor_ids) do
            local actor = Board:GetPawn(actor_id)
            local active_ok, active = pcall(function()
                return actor and actor:IsActive()
            end)
            if active_ok and active then actors_spent = false break end
        end
        if not actors_spent then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED requires spent player actors")
            return
        end
        local directory, directory_error = modloader_script_directory()
        if not directory then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED "
                .. tostring(directory_error))
            return
        end
        local helper, helper_error = load_observatory_rng_seed_helper(
            directory,
            {
                helper_version = "observatory-rng-seed-helper/1",
                helper_sha256 = NATIVE_RNG_SEED_HELPER_SHA256,
                executable_sha256 = NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256,
                architecture = "x86",
                build_id = NATIVE_RNG_OBSERVER_BUILD_ID,
                rng_seed_rva = "0x00387f37",
                rng_seed_region_sha256 = NATIVE_RNG_SEED_REGION_SHA256,
            }
        )
        if not helper then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED "
                .. tostring(helper_error))
            return
        end
        local gameflow, gameflow_error =
            load_observatory_native_gameflow_helper(directory)
        if not gameflow then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED "
                .. tostring(gameflow_error))
            return
        end
        local seed_ok, seeded = pcall(
            rawget(helper, "seed"), NATIVE_RNG_FIXED_SEED
        )
        if not seed_ok or seeded ~= true then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED failed: "
                .. tostring(seeded))
            return
        end
        _observatory_native_gameflow = gameflow
        write_ack("OK OBS_NATIVE_RNG_SEED seed="
            .. tostring(NATIVE_RNG_FIXED_SEED))
        return

    elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN" then
        if #parts ~= 2 then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN requires one capture ID"
            )
            return
        end
        local started, start_error =
            start_observatory_native_rng_with_spawn_span(parts[2])
        if not started then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN "
                .. tostring(start_error))
            return
        end
        write_ack("OK " .. started)
        return

    elseif cmd == "OBS_SPAWN_REPLAY_CONTROL" then
        if #parts ~= 2 then
            write_ack(
                "ERROR: OBS_SPAWN_REPLAY_CONTROL requires one capture ID"
            )
            return
        end
        local prepared, prepare_error =
            prepare_observatory_spawn_replay_control(parts[2])
        if not prepared then
            write_ack("ERROR: OBS_SPAWN_REPLAY_CONTROL "
                .. tostring(prepare_error))
            return
        end
        write_ack("OK " .. prepared)
        return

    elseif cmd == "OBS_NATIVE_RNG_ARM_SPAWN_REPLAY" then
        if #parts ~= 2 then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_ARM_SPAWN_REPLAY requires one capture ID"
            )
            return
        end
        local started, start_error =
            start_observatory_native_rng_with_spawn_replay(parts[2])
        if not started then
            write_ack("ERROR: OBS_NATIVE_RNG_ARM_SPAWN_REPLAY "
                .. tostring(start_error))
            return
        end
        write_ack("OK " .. started)
        return

    elseif cmd == "OBS_NATIVE_RNG_SEED_AND_ARM" then
        -- Exact-hook trials must not yield a BaseUpdate between fixing the
        -- native seed and installing the observer. Load and validate both
        -- content-addressed modules first, then seed and arm in this single
        -- command dispatch. The only caller-controlled value is a bounded
        -- evidence label; no address, path, seed, or hook shape is accepted.
        local capture_id = parts[2]
        if #parts ~= 2
            or not valid_observatory_capture_id(capture_id)
            or string.len(capture_id) > 96 then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_SEED_AND_ARM requires one capture ID"
            )
            return
        end
        if not Board or not Game then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_SEED_AND_ARM requires an active mission"
            )
            return
        end
        local team_ok, team_turn = pcall(function()
            return Game:GetTeamTurn()
        end)
        if not team_ok or team_turn ~= TEAM_PLAYER then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_SEED_AND_ARM requires combat_player"
            )
            return
        end
        local actors_spent = true
        local actor_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
        for _, actor_id in ipairs(actor_ids) do
            local actor = Board:GetPawn(actor_id)
            local active_ok, active = pcall(function()
                return actor and actor:IsActive()
            end)
            if active_ok and active then actors_spent = false break end
        end
        if not actors_spent then
            write_ack(
                "ERROR: OBS_NATIVE_RNG_SEED_AND_ARM requires spent player actors"
            )
            return
        end
        if _observatory_native_rng_module ~= nil then
            write_ack("ERROR: native RNG observer is already consumed")
            return
        end
        if observatory_path_exists(NATIVE_RNG_SNAPSHOT_FILE)
            or observatory_path_exists(NATIVE_RNG_SNAPSHOT_TMP) then
            write_ack("ERROR: native RNG snapshot output already exists")
            return
        end
        local directory, directory_error = modloader_script_directory()
        if not directory then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM "
                .. tostring(directory_error))
            return
        end
        local seed_helper, seed_helper_error =
            load_observatory_rng_seed_helper(
                directory,
                {
                    helper_version = "observatory-rng-seed-helper/1",
                    helper_sha256 = NATIVE_RNG_SEED_HELPER_SHA256,
                    executable_sha256 =
                        NATIVE_RNG_OBSERVER_EXECUTABLE_SHA256,
                    architecture = "x86",
                    build_id = NATIVE_RNG_OBSERVER_BUILD_ID,
                    rng_seed_rva = "0x00387f37",
                    rng_seed_region_sha256 = NATIVE_RNG_SEED_REGION_SHA256,
                }
            )
        if not seed_helper then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM "
                .. tostring(seed_helper_error))
            return
        end
        local gameflow, gameflow_error =
            load_observatory_native_gameflow_helper(directory)
        if not gameflow then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM "
                .. tostring(gameflow_error))
            return
        end
        -- Loading validates the observer contract but installs no patch;
        -- observer.arm below is the sole mutation point.
        local observer, observer_error =
            load_observatory_native_rng_module()
        if not observer then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM "
                .. tostring(observer_error))
            return
        end
        local seed_ok, seeded = pcall(
            rawget(seed_helper, "seed"), NATIVE_RNG_FIXED_SEED
        )
        if not seed_ok or seeded ~= true then
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM seed failed: "
                .. tostring(seeded))
            return
        end
        _observatory_native_rng_module = observer
        _observatory_native_rng_capture_id = capture_id
        local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
        if not arm_ok or armed ~= true then
            pcall(rawget(observer, "finish"))
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM arm failed: "
                .. tostring(armed))
            return
        end
        local status_ok, status = pcall(rawget(observer, "status"))
        if not status_ok or type(status) ~= "table"
            or rawget(status, "state") ~= "capturing"
            or rawget(status, "patch_installed") ~= true then
            pcall(rawget(observer, "finish"))
            write_ack("ERROR: OBS_NATIVE_RNG_SEED_AND_ARM status mismatch")
            return
        end
        _observatory_native_gameflow = gameflow
        write_ack(
            "OK OBS_NATIVE_RNG_SEED_AND_ARM capture=" .. capture_id
            .. " seed=" .. tostring(NATIVE_RNG_FIXED_SEED)
        )
        return

    elseif cmd == "OBS_NATIVE_RNG_ARM" then
        -- Explicit one-shot native diagnostic. The fixed module name and all
        -- exported build identities are pinned above; command input supplies
        -- only a bounded capture label, never a path, RVA, or address.
        local capture_id = parts[2]
        if #parts ~= 2
            or not valid_observatory_capture_id(capture_id)
            or string.len(capture_id) > 96 then
            write_ack("ERROR: OBS_NATIVE_RNG_ARM requires one capture ID")
            return
        end
        if _observatory_native_rng_module ~= nil then
            write_ack("ERROR: native RNG observer is already consumed")
            return
        end
        if observatory_path_exists(NATIVE_RNG_SNAPSHOT_FILE)
            or observatory_path_exists(NATIVE_RNG_SNAPSHOT_TMP) then
            write_ack("ERROR: native RNG snapshot output already exists")
            return
        end
        local observer, observer_error =
            load_observatory_native_rng_module()
        if not observer then
            write_ack("ERROR: OBS_NATIVE_RNG_ARM "
                .. tostring(observer_error))
            return
        end
        _observatory_native_rng_module = observer
        _observatory_native_rng_capture_id = capture_id
        local arm_ok, armed = pcall(rawget(observer, "arm"), capture_id)
        if not arm_ok or armed ~= true then
            pcall(rawget(observer, "finish"))
            write_ack("ERROR: OBS_NATIVE_RNG_ARM failed: "
                .. tostring(armed))
            return
        end
        local status_ok, status = pcall(rawget(observer, "status"))
        if not status_ok or type(status) ~= "table"
            or rawget(status, "state") ~= "capturing"
            or rawget(status, "patch_installed") ~= true then
            pcall(rawget(observer, "finish"))
            write_ack("ERROR: OBS_NATIVE_RNG_ARM status mismatch")
            return
        end
        write_ack("OK OBS_NATIVE_RNG_ARM capture=" .. capture_id)
        return

    elseif cmd == "OBS_NATIVE_RNG_STATUS" then
        if #parts ~= 1 or _observatory_native_rng_module == nil then
            write_ack("ERROR: native RNG observer is not loaded")
            return
        end
        local status_ok, status = pcall(
            rawget(_observatory_native_rng_module, "status")
        )
        if not status_ok or type(status) ~= "table" then
            write_ack("ERROR: OBS_NATIVE_RNG_STATUS failed: "
                .. tostring(status))
            return
        end
        write_ack("OK OBS_NATIVE_RNG_STATUS " .. json_encode(status))
        return

    elseif cmd == "OBS_NATIVE_RNG_FINISH" then
        if #parts ~= 1 or _observatory_native_rng_module == nil
            or _observatory_native_rng_capture_id == nil then
            write_ack("ERROR: native RNG observer is not loaded")
            return
        end
        local span_ledger = nil
        local replay_ledger = nil
        if _observatory_spawn_span_controller ~= nil then
            local checkpoint_ok, checkpoint_value = pcall(
                rawget(_observatory_spawn_span_controller, "checkpoint"),
                _observatory_spawn_span_controller
            )
            if checkpoint_ok and type(checkpoint_value) == "table" then
                span_ledger = checkpoint_value
                rawset(
                    span_ledger,
                    "controller_sha256",
                    SPAWN_SPAN_CONTROLLER_SHA256
                )
            else
                pcall(
                    rawget(_observatory_spawn_span_controller, "abort"),
                    _observatory_spawn_span_controller
                )
            end
        end
        if _observatory_spawn_replay_controller ~= nil then
            local checkpoint_ok, checkpoint_value = pcall(
                rawget(_observatory_spawn_replay_controller, "checkpoint"),
                _observatory_spawn_replay_controller
            )
            if checkpoint_ok and type(checkpoint_value) == "table" then
                replay_ledger = checkpoint_value
                rawset(
                    replay_ledger,
                    "controller_sha256",
                    SPAWN_REPLAY_CONTROLLER_SHA256
                )
            else
                pcall(
                    rawget(_observatory_spawn_replay_controller, "abort"),
                    _observatory_spawn_replay_controller
                )
            end
        end
        local finish_ok, snapshot = pcall(
            rawget(_observatory_native_rng_module, "finish")
        )
        if not finish_ok or type(snapshot) ~= "table" then
            write_ack("ERROR: OBS_NATIVE_RNG_FINISH failed: "
                .. tostring(snapshot))
            return
        end
        local valid, validation_error =
            validate_observatory_native_rng_snapshot(
                snapshot, _observatory_native_rng_capture_id
            )
        if not valid then
            write_ack("ERROR: OBS_NATIVE_RNG_FINISH "
                .. tostring(validation_error))
            return
        end
        if _observatory_spawn_span_controller ~= nil then
            local ledger_valid, ledger_error =
                validate_observatory_spawn_span_ledger(
                    span_ledger,
                    _observatory_native_rng_capture_id,
                    rawget(snapshot.summary, "record_count")
                )
            if not ledger_valid then
                write_ack("ERROR: OBS_NATIVE_RNG_FINISH "
                    .. tostring(ledger_error))
                return
            end
        end
        if _observatory_spawn_replay_controller ~= nil then
            local ledger_valid, ledger_error =
                validate_observatory_spawn_replay_ledger(
                    replay_ledger,
                    _observatory_native_rng_capture_id,
                    rawget(snapshot.summary, "record_count")
                )
            if not ledger_valid then
                write_ack("ERROR: OBS_NATIVE_RNG_FINISH "
                    .. tostring(ledger_error))
                return
            end
        end
        local wrote, write_error = write_observatory_create_only_json(
            NATIVE_RNG_SNAPSHOT_FILE,
            NATIVE_RNG_SNAPSHOT_TMP,
            snapshot,
            1024 * 1024
        )
        if not wrote then
            write_ack("ERROR: OBS_NATIVE_RNG_FINISH output failed: "
                .. tostring(write_error))
            return
        end
        if span_ledger ~= nil then
            local ledger_wrote, ledger_write_error =
                write_observatory_create_only_json(
                    SPAWN_SPAN_LEDGER_FILE,
                    SPAWN_SPAN_LEDGER_TMP,
                    span_ledger,
                    256 * 1024
                )
            if not ledger_wrote then
                write_ack("ERROR: OBS_NATIVE_RNG_FINISH span ledger output failed: "
                    .. tostring(ledger_write_error))
                return
            end
        end
        if replay_ledger ~= nil then
            local ledger_wrote, ledger_write_error =
                write_observatory_create_only_json(
                    SPAWN_REPLAY_LEDGER_FILE,
                    SPAWN_REPLAY_LEDGER_TMP,
                    replay_ledger,
                    256 * 1024
                )
            if not ledger_wrote then
                write_ack("ERROR: OBS_NATIVE_RNG_FINISH replay ledger output failed: "
                    .. tostring(ledger_write_error))
                return
            end
        end
        write_ack(
            "OK OBS_NATIVE_RNG_FINISH capture="
            .. _observatory_native_rng_capture_id
            .. " records="
            .. tostring(rawget(snapshot.summary, "record_count"))
            .. " complete=true"
        )
        return

    elseif cmd == "LUA" then
        -- Raw Lua execution (for debugging)
        local lua_code = cmd_str:match("LUA%s+(.*)")
        if not lua_code or lua_code == "" then
            write_ack("ERROR: empty LUA command")
            return
        end
        local ok, result = pcall(loadstring(lua_code))
        write_ack(ok and ("OK LUA: " .. tostring(result))
                      or ("ERROR LUA: " .. tostring(result)))

    else
        write_ack("ERROR: unknown command: " .. cmd)
    end

    -- Dump state after every command
    pcall(dump_state)
end

local function poll_commands()
    -- If a prior command's coroutine is still running (yielded on
    -- wait_for_board_coro), leave the cmd file alone until it completes.
    if _running_coroutine then return end

    local f = io.open(CMD_FILE, "r")
    if f then
        local cmd = f:read("*a")
        f:close()
        os.remove(CMD_FILE)
        if cmd and cmd:match("%S") then
            log_bridge("CMD: " .. cmd:gsub("\n", " "))
            local trimmed = cmd:match("^%s*(.-)%s*$")
            -- Wrap execute_command in a coroutine so wait_for_board_coro
            -- can yield control back to the engine between polls.
            _running_coroutine = coroutine.create(function()
                execute_command(trimmed)
            end)
            local ok, err = coroutine.resume(_running_coroutine)
            if not ok then
                log_bridge("CMD CORO ERROR: " .. tostring(err))
                write_atomic(ACK_FILE, ACK_TMP,
                             "ERROR: coroutine failed: " .. tostring(err))
                _running_coroutine = nil
            elseif coroutine.status(_running_coroutine) == "dead" then
                _running_coroutine = nil
            end
        end
    end
end

--------------------------------------------------------------------
-- Game hooks (with re-execution guard)
--------------------------------------------------------------------
-- Guard: store originals in a global so reloads don't compound hooks.
-- On first load, _ITB_BRIDGE_ORIGINALS is nil so we capture the real
-- game functions. On subsequent loads we reuse those same originals,
-- preventing the wrap-on-wrap stack that kills frame rate.
if not _ITB_BRIDGE_ORIGINALS then
    _ITB_BRIDGE_ORIGINALS = {
        BaseUpdate       = Mission.BaseUpdate,
        NextTurn         = Mission.NextTurn,
        BaseStart        = Mission.BaseStart,
        MissionEnd       = Mission.MissionEnd,
        BaseDeployment   = Mission.BaseDeployment,
        -- Mission_Teleporter is loaded earlier (scripts.lua line 65 vs
        -- modloader.lua at 160) but guard regardless — any plugin can
        -- redefine it before our hook installs.
        TeleporterStartMission = (Mission_Teleporter
            and Mission_Teleporter.StartMission) or nil,
    }
end

local _orig_BaseUpdate              = _ITB_BRIDGE_ORIGINALS.BaseUpdate
local _orig_NextTurn                = _ITB_BRIDGE_ORIGINALS.NextTurn
local _orig_BaseStart               = _ITB_BRIDGE_ORIGINALS.BaseStart
local _orig_MissionEnd              = _ITB_BRIDGE_ORIGINALS.MissionEnd
local _orig_BaseDeployment          = _ITB_BRIDGE_ORIGINALS.BaseDeployment
local _orig_TeleporterStartMission  = _ITB_BRIDGE_ORIGINALS.TeleporterStartMission

-- Teleporter pads for the CURRENT mission. Each entry = {x1, y1, x2, y2}.
-- Populated by the Mission_Teleporter:StartMission wrap further down: that
-- wrap scope-rebinds Board.AddTeleport in a pcall so the C++ class system
-- can reject the assignment (commit 456ba49 hit "no static 'AddTeleport'
-- in class 'Board'" with a permanent global rebind at file-load) without
-- taking down mission load. On rejection the list stays empty and the
-- solver falls back to pre-sim-v8 behavior for that mission.
_ITB_TELEPORT_PAIRS = _ITB_TELEPORT_PAIRS or {}

-- Cached deployment zone (captured in BaseDeployment, cleared on MissionEnd)
_ITB_DEPLOY_ZONE = _ITB_DEPLOY_ZONE or {}

-- Cached current mission reference. Populated via Mission:BaseStart,
-- BaseUpdate, NextTurn, and BaseDeployment hooks since the game does not
-- expose a top-level GetCurrentMission() global. Cleared in MissionEnd.
_ITB_CURRENT_MISSION = _ITB_CURRENT_MISSION or nil

-- State dump interval (separate from command poll)
local _state_dump_interval = 5  -- dump state every 5 seconds
local _last_state_dump = 0

local function clear_stale_teleporter_pairs_for(mission)
    if mission and mission.ID and mission.ID ~= "Mission_Teleporter"
       and _ITB_TELEPORT_PAIRS and #_ITB_TELEPORT_PAIRS > 0 then
        log_bridge("TELEPORT PAD: clearing stale pairs for "
            .. tostring(mission.ID))
        _ITB_TELEPORT_PAIRS = {}
    end
end

local function step_observatory_rng_trial()
    local observatory_trial = rawget(_G, "_ITB_OBSERVATORY_RNG_TRIAL")
    if type(observatory_trial) == "table"
        and type(rawget(observatory_trial, "step")) == "function" then
        local step_ok, trial_status, trial_error = pcall(
            rawget(observatory_trial, "step"), observatory_trial
        )
        if not step_ok then
            local abort = rawget(observatory_trial, "abort")
            if type(abort) == "function" then
                pcall(abort, observatory_trial, "Mod Loader step failed")
            end
            log_bridge("OBS RNG TRIAL host error: " .. tostring(trial_status))
            _ITB_OBSERVATORY_RNG_TRIAL = nil
        elseif trial_status == "complete" or trial_status == "failed" then
            log_bridge(
                "OBS RNG TRIAL " .. tostring(trial_status)
                .. (trial_error and (": " .. tostring(trial_error)) or "")
            )
            _ITB_OBSERVATORY_RNG_TRIAL = nil
        end
    end
end

local function activate_pending_observatory_callback_trial()
    local pending = rawget(_G, "_ITB_OBSERVATORY_CALLBACK_PENDING")
    if type(pending) ~= "table" then return end
    local request = rawget(pending, "request")
    local attempts = rawget(pending, "attempts")
    if type(request) ~= "table" or type(attempts) ~= "number" then
        _ITB_OBSERVATORY_CALLBACK_PENDING = nil
        _ITB_OBSERVATORY_CALLBACK_GAMEFLOW = nil
        log_bridge("OBS CALLBACK TRIAL pending state is invalid")
        return
    end
    attempts = attempts + 1
    rawset(pending, "attempts", attempts)
    local gameflow = rawget(_G, "_ITB_OBSERVATORY_CALLBACK_GAMEFLOW")
    local continue_status = nil
    if type(gameflow) == "table"
        and type(rawget(gameflow, "continue_status")) == "function" then
        local status_ok, status = pcall(rawget(gameflow, "continue_status"))
        if status_ok then continue_status = status end
    end
    if continue_status ~= "invoked" then
        if continue_status == "pending" and attempts < 120 then return end
        _ITB_OBSERVATORY_CALLBACK_PENDING = nil
        _ITB_OBSERVATORY_CALLBACK_GAMEFLOW = nil
        write_ack("ERROR: Observatory title Continue bootstrap failed")
        log_bridge(
            "OBS CALLBACK TRIAL title Continue bootstrap failed status="
            .. tostring(continue_status)
        )
        return
    end
    local trial, trial_error = initialize_observatory_callback_trial(request)
    if trial then
        _ITB_OBSERVATORY_CALLBACK_TRIAL = trial
        _ITB_OBSERVATORY_CALLBACK_PENDING = nil
        log_bridge(
            "OBS CALLBACK TRIAL armed condition="
            .. tostring(rawget(request, "condition"))
            .. " after mission load"
        )
        return
    end
    local roots_not_loaded = type(trial_error) == "string"
        and string.find(
            trial_error,
            "callback trial initialization failed: invalid roots",
            1,
            true
        ) ~= nil
    if roots_not_loaded and attempts < 120 then return end
    _ITB_OBSERVATORY_CALLBACK_PENDING = nil
    _ITB_OBSERVATORY_CALLBACK_GAMEFLOW = nil
    write_ack("ERROR: Observatory callback trial deferred startup failed")
    log_bridge(
        "OBS CALLBACK TRIAL deferred startup failed: "
        .. tostring(trial_error)
    )
end

local function step_observatory_callback_trial(stage)
    local observatory_trial = rawget(
        _G, "_ITB_OBSERVATORY_CALLBACK_TRIAL"
    )
    if type(observatory_trial) == "table"
        and type(rawget(observatory_trial, "step")) == "function" then
        local step_ok, trial_status, trial_error = pcall(
            rawget(observatory_trial, "step"), observatory_trial, stage
        )
        if not step_ok then
            local abort = rawget(observatory_trial, "abort")
            if type(abort) == "function" then
                pcall(abort, observatory_trial, "Mod Loader callback step failed")
            end
            log_bridge(
                "OBS CALLBACK TRIAL host error: " .. tostring(trial_status)
            )
            _ITB_OBSERVATORY_CALLBACK_TRIAL = nil
        elseif trial_status == "complete" or trial_status == "failed" then
            log_bridge(
                "OBS CALLBACK TRIAL " .. tostring(trial_status)
                .. (trial_error and (": " .. tostring(trial_error)) or "")
            )
            _ITB_OBSERVATORY_CALLBACK_TRIAL = nil
        end
    end
end

-- BaseUpdate: resume pending command coroutine, poll for new commands,
-- and periodically dump state. The one-shot Observatory trial samples the
-- already-selected team before the original frame update is allowed to drain
-- enemy effects; otherwise a fast loss/transition can make the enemy boundary
-- unobservable. With no explicitly armed trial this helper is inert.
-- Coroutine resume still happens before command polling so that
-- wait_for_board_coro yields get unblocked the moment the engine drains
-- its effect queue — without this, poll_commands could race a yielded
-- coroutine and clobber _running_coroutine.
Mission.BaseUpdate = function(self)
    -- Cache current mission first: the trial's live-state provider must use
    -- this exact BaseUpdate receiver even on the first frame after a reload.
    _ITB_CURRENT_MISSION = self
    clear_stale_teleporter_pairs_for(self)
    step_observatory_rng_trial()
    _orig_BaseUpdate(self)
    _ITB_CURRENT_MISSION = self
    clear_stale_teleporter_pairs_for(self)
    -- A title-screen bootstrap cannot enumerate enemy Skill globals yet.
    -- Construct the inert callback host only after the continued mission has
    -- loaded those roots, before any player command can end the turn.
    activate_pending_observatory_callback_trial()
    -- An explicitly armed callback controller remains active across the enemy
    -- phase and the following player transition. The host checkpoints here
    -- only on that player's first completed BaseUpdate, restoring every slot
    -- before any bridge polling or state I/O.
    step_observatory_callback_trial("base_update_after")
    -- Heartbeat: write mtime so Python can detect stuck/dead bridge
    pcall(function()
        local f = io.open(HEARTBEAT_FILE, "w")
        if f then f:write(tostring(os.clock())); f:close() end
    end)
    if _running_coroutine then
        local ok, err = coroutine.resume(_running_coroutine)
        if not ok then
            log_bridge("CORO RESUME ERROR: " .. tostring(err))
            write_atomic(ACK_FILE, ACK_TMP,
                         "ERROR: coroutine failed: " .. tostring(err))
            _running_coroutine = nil
        elseif coroutine.status(_running_coroutine) == "dead" then
            _running_coroutine = nil
        end
    end
    local now = os.clock()
    if now - _last_poll >= _poll_interval then
        _last_poll = now
        pcall(poll_commands)
    end
    -- If deploy zone is empty on turn 0, retry capture each update
    if #_ITB_DEPLOY_ZONE == 0 and Game and Game:GetTurnCount() == 0 then
        local zone = capture_deploy_zone()
        if #zone > 0 then
            _ITB_DEPLOY_ZONE = zone
            log_bridge("DEPLOY ZONE captured in BaseUpdate: " .. #zone .. " tiles")
        end
    end
    -- Periodically dump state so Python can detect the bridge
    if now - _last_state_dump >= _state_dump_interval then
        _last_state_dump = now
        pcall(dump_state)
    end
end

-- NextTurn: dump state on each turn change.
--
-- Defensive re-activation: when our bridge END_TURN took the SetActive(false)
-- fallback path (Game:EndTurn() unavailable), the engine's turn-start lifecycle
-- may not re-activate pawns on the next player phase because our manual
-- SetActive(false) was out of band. Without this, auto_turn's poller sees
-- phase=combat_player + active_mechs=0 forever and the whole player turn is
-- skipped, bleeding grid power.
Mission.NextTurn = function(self)
    _orig_NextTurn(self)
    _ITB_CURRENT_MISSION = self
    clear_stale_teleporter_pairs_for(self)
    -- Explicit callback trials arm only after the original transition has
    -- selected TEAM_ENEMY. On the next player transition they deliberately
    -- remain armed until the following completed BaseUpdate so deferred enemy
    -- planning after NextTurn is still inside the bounded window.
    step_observatory_callback_trial("next_turn")
    pcall(function()
        if Game and Game:GetTeamTurn() == TEAM_PLAYER then
            local mech_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
            for _, mid in ipairs(mech_ids) do
                local m = Board:GetPawn(mid)
                if m and not m:IsDead() then m:SetActive(true) end
            end
        end
    end)
    pcall(dump_state)
    log_bridge("TURN " .. (Game and Game:GetTurnCount() or "?") .. " team=" .. (Game and Game:GetTeamTurn() or "?"))
end

-- BaseStart: dump state when mission starts (after deployment)
Mission.BaseStart = function(self)
    _orig_BaseStart(self)
    _ITB_CURRENT_MISSION = self
    clear_stale_teleporter_pairs_for(self)
    pcall(dump_state)
    log_bridge("MISSION START: " .. tostring(self.ID or self.Name or "unknown"))
end

-- BaseDeployment: capture deployment zone AFTER engine sets it up
Mission.BaseDeployment = function(self)
    _orig_BaseDeployment(self)
    _ITB_CURRENT_MISSION = self
    clear_stale_teleporter_pairs_for(self)
    -- Capture zone AFTER original runs (engine creates the zone in BaseDeployment)
    _ITB_DEPLOY_ZONE = capture_deploy_zone()
    if #_ITB_DEPLOY_ZONE > 0 then
        log_bridge("DEPLOY ZONE from Board:GetZone: " .. #_ITB_DEPLOY_ZONE .. " tiles")
    else
        log_bridge("DEPLOY ZONE: Board:GetZone returned 0 tiles")
    end
    -- Dump state so Python can see the deployment zone immediately
    pcall(dump_state)
end

-- MissionEnd: log mission completion, clear deployment zone + teleport pads
Mission.MissionEnd = function(self)
    log_bridge("MISSION END: " .. tostring(self.ID or self.Name or "unknown"))
    _ITB_DEPLOY_ZONE = {}
    _ITB_CURRENT_MISSION = nil
    _ITB_TELEPORT_PAIRS = {}
    _orig_MissionEnd(self)
    pcall(dump_state)
end

-- Mission_Teleporter:StartMission — capture pad pairs.
--
-- Why this wrap exists: Mission_Teleporter calls Board:AddTeleport(p1,p2)
-- twice during StartMission to register two pad pairs, and the C++ side
-- never re-exposes those pairs through a documented Lua getter. The Rust
-- sim's apply_teleport_on_land needs them to score post-move positions
-- correctly on Detritus disposal missions (commit 456ba49 added the sim
-- side; the bridge has been emitting an empty list since 63e0e18 rolled
-- back the global Board.AddTeleport hook that crashed macOS).
--
-- Why this is safer than the prior global hook:
--   * Wrap target is Mission_Teleporter, a pure-Lua subclass of
--     Mission_Auto. Method dispatch on Mission goes through plain Lua
--     metatables (the existing Mission.BaseStart wrap proves that works
--     on macOS); Board lives in the C++ class proxy that rejected the
--     earlier rawset.
--   * The Board.AddTeleport scope-rebind is wrapped in pcall. If the
--     proxy still refuses the assignment we just log + skip capture; the
--     original StartMission still runs, _ITB_TELEPORT_PAIRS stays empty,
--     and the simulator falls back to pre-v8 behavior — same outcome
--     we have today, no crash.
--   * No other mission ever touches Board.AddTeleport in our wrap, so
--     Vice Fist throw and Science_Swap (the other AddTeleport callers)
--     never see our shadow function.
--   * Every step is pcall-guarded. The worst case is that the next
--     teleporter mission solves on stale (empty) pad data; combat still
--     proceeds.
if Mission_Teleporter and _orig_TeleporterStartMission then
    Mission_Teleporter.StartMission = function(self)
        _ITB_TELEPORT_PAIRS = {}
        local original_AddTeleport = nil
        local rebound = false
        local capture_fn = function(board_self, p1, p2)
            -- Record the pair, then defer to the original engine method
            -- so the actual pad placement / animation still happens.
            local ok = pcall(function()
                if p1 and p2
                   and type(p1.x) == "number" and type(p1.y) == "number"
                   and type(p2.x) == "number" and type(p2.y) == "number" then
                    _ITB_TELEPORT_PAIRS[#_ITB_TELEPORT_PAIRS + 1] =
                        {p1.x, p1.y, p2.x, p2.y}
                    log_bridge(
                        "TELEPORT PAD pair captured: ("
                        .. p1.x .. "," .. p1.y .. ") <-> ("
                        .. p2.x .. "," .. p2.y .. ")")
                end
            end)
            if not ok then
                log_bridge("TELEPORT PAD capture: pair record failed (non-fatal)")
            end
            -- Always invoke the original — never swallow the pad placement.
            -- C++ binding signature is `void AddTeleport(Board&, Point, Point)`
            -- — exactly 3 args. Forwarding a 4th `delay` arg (even nil) tripped
            -- C++ overload resolution with "No matching overload found" and
            -- crashed ITB on the next mission load (observed on Detritus
            -- 2026-04-29: Mission_Disposal ended, next Mission_Teleporter
            -- mission's StartMission errored mid-AddTeleport and the game
            -- terminated). Dropping the trailing arg matches the engine
            -- signature exactly.
            return original_AddTeleport(board_self, p1, p2)
        end

        -- Try to install the capture. If the C++ proxy rejects the
        -- assignment (the failure mode that bit commit 456ba49) the
        -- pcall returns false and we proceed without recording — the
        -- original StartMission still runs through the unmodified
        -- engine method, mission load succeeds.
        local install_ok = pcall(function()
            original_AddTeleport = Board and Board.AddTeleport or nil
            if original_AddTeleport then
                Board.AddTeleport = capture_fn
                rebound = true
            end
        end)

        if not install_ok then
            log_bridge("TELEPORT PAD: Board.AddTeleport rebind rejected — "
                .. "running StartMission with empty pad list (sim falls back "
                .. "to pre-v8 behavior on this mission)")
            rebound = false
        end

        -- Run the original mission setup. This is the call that
        -- triggers Board:AddTeleport(start, finish) twice.
        local run_ok, run_err = pcall(function()
            _orig_TeleporterStartMission(self)
        end)

        -- ALWAYS restore, regardless of whether StartMission errored.
        -- Leaving our shadow function on Board would break Vice Fist /
        -- Science_Swap on subsequent turns.
        if rebound then
            pcall(function()
                Board.AddTeleport = original_AddTeleport
            end)
        end

        if not run_ok then
            log_bridge("TELEPORT PAD: original StartMission errored: "
                .. tostring(run_err))
            -- Re-raise so the engine sees the same error it would have
            -- without our wrap. Game-side error recovery owns this path.
            error(run_err)
        end

        log_bridge("TELEPORT PAD: StartMission complete, "
            .. #_ITB_TELEPORT_PAIRS .. " pair(s) captured")
    end
end

--------------------------------------------------------------------
-- Startup
--------------------------------------------------------------------
-- A fixed-token, one-shot request can capture the inert callback manifest at
-- script-load time, before a Mission exists.  scripts.lua loads modloader.lua
-- after the shipped pawn/skill registries, so discovery needs no Board.  This
-- path never dispatches file contents as a command: it accepts only the exact
-- versioned token, removes the request before execution, and invokes the same
-- no-argument read-only command with a literal string.
local function consume_observatory_callback_manifest_startup_request()
    local file = io.open(CALLBACK_MANIFEST_REQUEST_FILE, "r")
    if not file then return false end
    local content = file:read(128)
    local extra = file:read(1)
    file:close()
    pcall(function() os.remove(CALLBACK_MANIFEST_REQUEST_FILE) end)
    if extra ~= nil
        or (content ~= CALLBACK_MANIFEST_REQUEST_TOKEN
            and content ~= CALLBACK_MANIFEST_REQUEST_TOKEN .. "\n"
            and content ~= CALLBACK_MANIFEST_REQUEST_TOKEN .. "\r\n") then
        write_ack("ERROR: invalid Observatory callback startup request")
        log_bridge("OBS CALLBACK MANIFEST startup request rejected")
        return true
    end
    log_bridge("OBS CALLBACK MANIFEST startup request accepted")
    execute_command("OBS_CALLBACK_MANIFEST")
    return true
end

local function consume_observatory_callback_bindings_startup_request()
    local file = io.open(CALLBACK_BINDINGS_REQUEST_FILE, "r")
    if not file then return false end
    local content = file:read(128)
    local extra = file:read(1)
    file:close()
    pcall(function() os.remove(CALLBACK_BINDINGS_REQUEST_FILE) end)
    if extra ~= nil
        or (content ~= CALLBACK_BINDINGS_REQUEST_TOKEN
            and content ~= CALLBACK_BINDINGS_REQUEST_TOKEN .. "\n"
            and content ~= CALLBACK_BINDINGS_REQUEST_TOKEN .. "\r\n") then
        write_ack("ERROR: invalid Observatory callback bindings startup request")
        log_bridge("OBS CALLBACK BINDINGS startup request rejected")
        return true
    end
    log_bridge("OBS CALLBACK BINDINGS startup request accepted")
    execute_command("OBS_CALLBACK_BINDINGS")
    return true
end

local function consume_observatory_native_continue_startup_request()
    local file = io.open(NATIVE_CONTINUE_REQUEST_FILE, "r")
    if not file then return false end
    local content = file:read(128)
    local extra = file:read(1)
    file:close()
    pcall(function() os.remove(NATIVE_CONTINUE_REQUEST_FILE) end)
    if extra ~= nil
        or (content ~= NATIVE_CONTINUE_REQUEST_TOKEN
            and content ~= NATIVE_CONTINUE_REQUEST_TOKEN .. "\n"
            and content ~= NATIVE_CONTINUE_REQUEST_TOKEN .. "\r\n") then
        write_ack("ERROR: invalid Observatory native Continue request")
        log_bridge("OBS NATIVE CONTINUE startup request rejected")
        return true
    end
    local directory, directory_error = modloader_script_directory()
    if not directory then
        write_ack("ERROR: Observatory native Continue "
            .. tostring(directory_error))
        return true
    end
    local gameflow, gameflow_error =
        load_observatory_native_gameflow_helper(directory)
    if not gameflow then
        write_ack("ERROR: Observatory native Continue "
            .. tostring(gameflow_error))
        return true
    end
    local continue_ok, invoked = pcall(
        rawget(gameflow, "continue_saved_timeline")
    )
    if not continue_ok or invoked ~= true then
        write_ack("ERROR: Observatory native Continue failed: "
            .. tostring(invoked))
        return true
    end
    _observatory_native_gameflow = gameflow
    write_ack("OK OBS_NATIVE_CONTINUE_REQUEST invoked=true")
    log_bridge("OBS NATIVE CONTINUE startup request invoked")
    return true
end

-- Clean up stale files from previous session
pcall(function() os.remove(STATE_FILE) end)
pcall(function() os.remove(CMD_FILE) end)
pcall(function() os.remove(ACK_FILE) end)
install_safe_jet_target_area()
install_safe_leap_target_area()

local _reload_count = (_ITB_BRIDGE_LOAD_COUNT or 0) + 1
_ITB_BRIDGE_LOAD_COUNT = _reload_count

log_bridge("=== ITB Bot Bridge started (load #" .. _reload_count .. ") ===")
if ConsolePrint then
    ConsolePrint("ITB Bot Bridge loaded! IPC via " .. BRIDGE_DIR)
end

local _callback_startup_requested = observatory_path_exists(
    CALLBACK_MANIFEST_REQUEST_FILE
)
local _callback_bindings_startup_requested = observatory_path_exists(
    CALLBACK_BINDINGS_REQUEST_FILE
)
local _rng_trial_startup_requested = observatory_path_exists(
    RNG_TRIAL_REQUEST_FILE
)
local _callback_trial_startup_requested = observatory_path_exists(
    CALLBACK_TRIAL_REQUEST_FILE
)
local _native_continue_startup_requested = observatory_path_exists(
    NATIVE_CONTINUE_REQUEST_FILE
)
local _observatory_startup_request_count =
    (_callback_startup_requested and 1 or 0)
    + (_callback_bindings_startup_requested and 1 or 0)
    + (_rng_trial_startup_requested and 1 or 0)
    + (_callback_trial_startup_requested and 1 or 0)
    + (_native_continue_startup_requested and 1 or 0)
if _observatory_startup_request_count > 1 then
    write_ack("ERROR: multiple Observatory startup requests are armed")
    log_bridge("OBS startup rejected: multiple requests are armed")
elseif _callback_startup_requested then
    local _startup_request_ok, _startup_request_error = pcall(
        consume_observatory_callback_manifest_startup_request
    )
    if not _startup_request_ok then
        log_bridge("OBS CALLBACK MANIFEST startup request failed: "
            .. tostring(_startup_request_error))
    end
elseif _callback_bindings_startup_requested then
    local _startup_request_ok, _startup_request_error = pcall(
        consume_observatory_callback_bindings_startup_request
    )
    if not _startup_request_ok then
        log_bridge("OBS CALLBACK BINDINGS startup request failed: "
            .. tostring(_startup_request_error))
    end
elseif _native_continue_startup_requested then
    local _startup_request_ok, _startup_request_error = pcall(
        consume_observatory_native_continue_startup_request
    )
    if not _startup_request_ok then
        write_ack("ERROR: Observatory native Continue startup failed")
        log_bridge("OBS NATIVE CONTINUE startup failed: "
            .. tostring(_startup_request_error))
    end
elseif _rng_trial_startup_requested then
    if rawget(_G, "_ITB_OBSERVATORY_RNG_TRIAL") ~= nil then
        write_ack("ERROR: an Observatory RNG trial is already active")
        log_bridge("OBS RNG TRIAL startup rejected: trial already active")
    else
        local _trial_request_ok, _trial_consumed, _trial_error = pcall(
            consume_observatory_rng_trial_startup_request
        )
        if not _trial_request_ok then
            write_ack("ERROR: Observatory RNG trial startup failed")
            log_bridge("OBS RNG TRIAL startup failed: "
                .. tostring(_trial_consumed))
        elseif _trial_consumed == nil then
            write_ack("ERROR: Observatory RNG trial startup rejected")
            log_bridge("OBS RNG TRIAL startup rejected: "
                .. tostring(_trial_error))
        elseif _trial_consumed then
            write_ack("OK OBS RNG TRIAL ARMED")
        end
    end
elseif _callback_trial_startup_requested then
    if rawget(_G, "_ITB_OBSERVATORY_CALLBACK_TRIAL") ~= nil
        or rawget(_G, "_ITB_OBSERVATORY_CALLBACK_PENDING") ~= nil then
        write_ack("ERROR: an Observatory callback trial is already active")
        log_bridge(
            "OBS CALLBACK TRIAL startup rejected: trial already active"
        )
    else
        local _trial_request_ok, _trial_consumed, _trial_error = pcall(
            consume_observatory_callback_trial_startup_request
        )
        if not _trial_request_ok then
            write_ack("ERROR: Observatory callback trial startup failed")
            log_bridge("OBS CALLBACK TRIAL startup failed: "
                .. tostring(_trial_consumed))
        elseif _trial_consumed == nil then
            write_ack("ERROR: Observatory callback trial startup rejected")
            log_bridge("OBS CALLBACK TRIAL startup rejected: "
                .. tostring(_trial_error))
        elseif _trial_consumed then
            write_ack("OK OBS CALLBACK TRIAL ARMED")
        end
    end
end
