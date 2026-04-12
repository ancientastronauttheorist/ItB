--------------------------------------------------------------------
-- ITB Bot Bridge — Production
-- Runs inside Into the Breach on macOS via modloader.lua injection.
-- Communicates with external Python bot via file-based IPC in /tmp/.
--
-- State dump: /tmp/itb_state.json (Lua writes, Python reads)
-- Commands:   /tmp/itb_cmd.txt    (Python writes, Lua reads)
-- Ack:        /tmp/itb_ack.txt    (Lua writes, Python reads)
--------------------------------------------------------------------

local STATE_FILE = "/tmp/itb_state.json"
local STATE_TMP  = "/tmp/itb_state.json.tmp"
local CMD_FILE   = "/tmp/itb_cmd.txt"
local ACK_FILE   = "/tmp/itb_ack.txt"
local ACK_TMP    = "/tmp/itb_ack.tmp"
local LOG_FILE   = "/tmp/itb_bridge.log"

local TERRAIN_NAMES = {
    [0] = "ground", [1] = "building", [2] = "rubble", [3] = "water",
    [4] = "mountain", [5] = "lava", [6] = "forest", [7] = "sand",
    [8] = "ice", [9] = "chasm",
}

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
        os.rename(tmp_path, path)
    end
end

local function log_bridge(msg)
    local f = io.open(LOG_FILE, "a")
    if f then
        f:write(os.date() .. " | " .. msg .. "\n")
        f:close()
    end
end

--------------------------------------------------------------------
-- Read all save-file-derived data in a single I/O pass:
-- grid power, queued shots, and conveyor belts.
-- Reads saveData.lua (preferred) or undoSave.lua (fallback).
--------------------------------------------------------------------
local function _read_save_data()
    local result = {
        network = nil,
        networkMax = nil,
        queued_shots = {},
        conveyor_belts = {},
    }
    local base = os.getenv("HOME") ..
        "/Library/Application Support/IntoTheBreach/profile_Alpha/"
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

    -- Queued shots: per-enemy piQueuedShot target data
    for block in content:gmatch('%["pawn%d+"%]%s*=%s*(%b{})') do
        local pid = block:match('%["id"%]%s*=%s*(%d+)')
        local qs = block:match('%["piQueuedShot"%]%s*=%s*Point%s*%(([^%)]+)%)')
        if pid and qs then
            local qsx, qsy = qs:match('(%-?%d+)%s*,%s*(%-?%d+)')
            if qsx and qsy then
                result.queued_shots[tonumber(pid)] = {x = tonumber(qsx), y = tonumber(qsy)}
            end
        end
    end

    -- Victory turns (mission length: usually 5, 4 for train/tidal missions)
    local victory = content:match('%["victory"%]%s*=%s*(%d+)')
    if victory then result.victory_turns = tonumber(victory) end

    -- Conveyor belts: direction from custom tile sprites
    for loc_x, loc_y, custom in content:gmatch(
        '%["loc"%]%s*=%s*Point%(%s*(%d+)%s*,%s*(%d+)%s*%).-'
        .. '%["custom"%]%s*=%s*"(conveyor%d+%.png)"'
    ) do
        local dir = custom:match("conveyor(%d+)")
        if dir then
            local key = loc_x .. "," .. loc_y
            result.conveyor_belts[key] = tonumber(dir)
        end
    end

    return result
end

--------------------------------------------------------------------
-- State serializer: Board → JSON
--------------------------------------------------------------------
local function dump_state()
    if not Board then return end

    local state = {}

    -- Phase detection
    local team_turn = Game and Game:GetTeamTurn() or 0
    if team_turn == 1 then
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

    -- Grid power: prefer save file value (authoritative, updated at turn boundaries).
    -- Falls back to GameData globals which may be stale at run transitions.
    -- Game:GetPower() crashes the Lua runtime so we can't use it.
    state.grid_power = save_data.network or (GameData and GameData.network) or 0
    state.grid_power_max = save_data.networkMax or (GameData and GameData.networkMax) or 7
    if save_data.victory_turns then
        state.total_turns = save_data.victory_turns
    end
    state.timestamp = os.time()

    -- Conveyor belts from consolidated save read
    local conveyor_belts = save_data.conveyor_belts

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

            -- Status effects
            local ok_f, fire = pcall(function() return Board:IsFire(pt) end)
            if ok_f and fire then tile.fire = true end
            local ok_s, smoke = pcall(function() return Board:IsSmoke(pt) end)
            if ok_s and smoke then tile.smoke = true end
            local ok_a, acid = pcall(function() return Board:IsAcid(pt) end)
            if ok_a and acid then tile.acid = true end
            local ok_fr, frozen = pcall(function() return Board:IsFrozen(pt) end)
            if ok_fr and frozen then tile.frozen = true end
            local ok_cr, cracked = pcall(function() return Board:IsCracked(pt) end)
            if ok_cr and cracked then tile.cracked = true end

            -- Conveyor belt direction (from save file)
            local belt_dir = conveyor_belts[x .. "," .. y]
            if belt_dir then tile.conveyor = belt_dir end

            -- Building data
            if terrain_id == 1 then
                local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
                if ok_h then tile.building_hp = hp end
            -- Mountain data (2 = full, 1 = damaged, 0 = rubble)
            elseif terrain_id == 4 then
                local ok_h, hp = pcall(function() return Board:GetHealth(pt) end)
                if ok_h then tile.building_hp = hp else tile.building_hp = 2 end
                tile.population = 1
            end

            -- Pod
            local ok_p, pod = pcall(function() return Board:IsPod(pt) end)
            if ok_p and pod then tile.pod = true end

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

                local unit = {
                    uid = pid,
                    type = ptype,
                    x = sp.x, y = sp.y,
                    hp = p:GetHealth(),
                    max_hp = pawn_def and pawn_def.Health or p:GetHealth(),
                    team = p:GetTeam(),
                    mech = p:IsMech(),
                    active = p:IsActive(),
                    move = p:GetMoveSpeed(),
                }

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
                local ok_w, web = pcall(function() return p:IsGrappled() end)
                if ok_w then unit.web = web end
                local ok_ar, ar = pcall(function() return p:IsArmor() end)
                if ok_ar and ar then unit.armor = true end

                -- Weapons from type definition
                unit.weapons = {}
                if pawn_def and pawn_def.SkillList then
                    for _, wname in ipairs(pawn_def.SkillList) do
                        unit.weapons[#unit.weapons + 1] = wname
                    end
                end

                -- Enemy attack data
                if p:GetTeam() == TEAM_ENEMY then
                    local ok_sw, sw = pcall(function() return p:GetSelectedWeapon() end)
                    if ok_sw and sw and sw > 0 then
                        unit.has_queued_attack = true
                    end

                    -- Per-enemy target from save file piQueuedShot
                    local qs = queued_shots[pid]
                    if qs and qs.x >= 0 and qs.y >= 0 then
                        unit.queued_target = {qs.x, qs.y}
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
            end
        end
    end

    -- Attack order: enemies with queued attacks sorted by UID (ascending)
    state.attack_order = {}
    for _, u in ipairs(state.units) do
        if u.team == 6 and u.has_queued_attack then
            state.attack_order[#state.attack_order + 1] = u.uid
        end
    end
    table.sort(state.attack_order)

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
    -- v2 = list of [x, y, damage, kill_int] where kill_int=1 means Deadly Threat
    -- (instant-kill, bypasses shield/frozen/armor/ACID per ITB spec).
    state.environment_danger = {}
    state.environment_danger_v2 = {}

    -- Default all env_danger tiles to lethal (kill=1). Most hazards ARE
    -- lethal to ground units: Air Strike, Lightning, Cataclysm→chasm,
    -- Seismic→chasm, Tidal Waves→water. Non-lethal hazards (Wind Storm,
    -- Sandstorm, SnowStorm) detected via LiveEnvironment field signatures
    -- and get kill=0.
    local env_damage = 1
    local env_kill_default = true

    -- Detect hazard type via LiveEnvironment field signatures:
    --   WindDir       → Wind Storm (push, non-lethal)
    --   Row           → Sandstorm (smoke, non-lethal)
    --   Indices (only)→ SnowStorm/IceStorm (freeze, non-lethal)
    --   Locations     → Lightning/Air Strike/Seismic (lethal)
    --   Index (only)  → Tidal Wave/Cataclysm (lethal)
    -- Fallback: try matching Lua class globals for Sandstorm edge case.
    local env_type = "unknown"
    pcall(function()
        local mission = GetCurrentMission and GetCurrentMission()
        if mission and mission.LiveEnvironment then
            local le = mission.LiveEnvironment
            if le.WindDir ~= nil then
                env_type = "wind"
                env_kill_default = false
            elseif le.Row ~= nil then
                env_type = "sandstorm"
                env_kill_default = false
            elseif le.Indices ~= nil then
                env_type = "snow"
                env_kill_default = false
            elseif le.Locations ~= nil then
                env_type = "lightning_or_airstrike"
            elseif le.Index ~= nil then
                env_type = "tidal_or_cataclysm"
            elseif le.StartEffect ~= nil then
                env_type = "cataclysm_or_seismic"
            end
            -- Fallback class matching for Sandstorm (Row may be nil initially)
            if env_type == "unknown" then
                local cls = _G and _G["Env_Sandstorm"]
                if cls then
                    local mt = getmetatable(le)
                    if mt and (mt == cls or mt.__index == cls) then
                        env_type = "sandstorm"
                        env_kill_default = false
                    end
                end
            end
        end
    end)
    state.env_type = env_type

    -- Helper: add a danger tile to both v1 and v2 fields.
    local function add_danger(x, y, kill_override)
        state.environment_danger[#state.environment_danger + 1] = {x, y}
        local k = env_kill_default
        if kill_override ~= nil then
            k = kill_override
        end
        state.environment_danger_v2[#state.environment_danger_v2 + 1] = {x, y, env_damage, k and 1 or 0}
    end

    for y = 0, 7 do
        for x = 0, 7 do
            local ok, danger = pcall(function() return Board:IsEnvironmentDanger(Point(x, y)) end)
            if ok and danger then
                add_danger(x, y)
            end
        end
    end

    -- Satellite rocket deadly threat: 4 adjacent tiles kill any unit on launch
    -- Board:IsEnvironmentDanger() does NOT detect these, so we add them manually.
    -- Only flag tiles on the turn the rocket is queued to fire (GetSelectedWeapon > 0).
    -- Satellite rockets are always Deadly Threat regardless of mission environment.
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
                            add_danger(nx, ny, true)  -- always lethal
                        end
                    end
                end
            end
        end
    end

    -- Deployment zone (captured in BaseDeployment hook via Board:GetZone)
    if _ITB_DEPLOY_ZONE and #_ITB_DEPLOY_ZONE > 0 then
        state.deployment_zone = _ITB_DEPLOY_ZONE
    end

    -- Mission metadata for hazard classification
    pcall(function()
        local mission = GetCurrentMission and GetCurrentMission()
        if mission then
            state.mission_id = mission.ID
        end
    end)

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
    return wait_until_coro(function()
        return not Board:IsBusy()
    end, max_wait)
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
local function find_weapon_slot(pawn, weapon_id)
    local ptype = pawn:GetType()
    local pawn_def = _G[ptype]
    if not (pawn_def and pawn_def.SkillList) then return nil end
    for i, wname in ipairs(pawn_def.SkillList) do
        if wname == weapon_id then return i end
    end
    return nil
end

local function execute_weapon_skill(pawn, weapon_id, tx, ty)
    local slot = find_weapon_slot(pawn, weapon_id)
    if not slot then
        return false, "weapon " .. weapon_id .. " not in pawn SkillList"
    end
    local source = pawn:GetSpace()
    local ok, err = pcall(function()
        pawn:FireWeapon(Point(tx, ty), slot)
    end)
    if not ok then
        log_bridge("WARN: FireWeapon failed for " .. weapon_id ..
                   " (slot " .. slot .. "): " .. tostring(err))
        return false, "FireWeapon failed: " .. tostring(err)
    end
    log_bridge("FIRE: " .. weapon_id .. " slot=" .. slot .. " " ..
               source.x .. "," .. source.y .. " -> " .. tx .. "," .. ty)
    return true, "FireWeapon[" .. slot .. "]"
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
        local ok, err = pcall(function() pawn:Move(Point(x, y)) end)
        if not ok then
            write_ack("ERROR: Move failed: " .. tostring(err))
            return
        end
        wait_for_board_coro()
        write_ack("OK MOVE " .. uid .. " to " .. x .. "," .. y)

    elseif cmd == "ATTACK" then
        -- ATTACK uid weapon_id target_x target_y
        local uid = tonumber(parts[2])
        local weapon_id = parts[3]
        local tx, ty = tonumber(parts[4]), tonumber(parts[5])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local ok, method = execute_weapon_skill(pawn, weapon_id, tx, ty)
        if not ok then
            write_ack("ERROR: " .. method)
            return
        end
        wait_for_board_coro()
        pawn:SetActive(false)
        write_ack("OK ATTACK " .. uid .. " " .. weapon_id .. " at " ..
                  tx .. "," .. ty .. " [" .. method .. "]")

    elseif cmd == "MOVE_ATTACK" then
        -- MOVE_ATTACK uid mx my weapon_id tx ty
        local uid = tonumber(parts[2])
        local mx, my = tonumber(parts[3]), tonumber(parts[4])
        local weapon_id = parts[5]
        local tx, ty = tonumber(parts[6]), tonumber(parts[7])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local ok1, err1 = pcall(function() pawn:Move(Point(mx, my)) end)
        if not ok1 then
            write_ack("ERROR: Move failed: " .. tostring(err1))
            return
        end
        wait_for_board_coro()
        local ok2, method = execute_weapon_skill(pawn, weapon_id, tx, ty)
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
            local repair_skill = _G["Skill_Repair"]
            if repair_skill and repair_skill.GetSkillEffect then
                local effect = repair_skill:GetSkillEffect(pos, pos)
                Board:AddEffect(effect)
                method = "skill"
                return
            end
            -- Fallback: SpaceDamage with iRepair
            local sd = SpaceDamage(pos, 0)
            sd.iRepair = 1
            Board:DamageSpace(sd)
            method = "fallback"
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
            -- Game:EndTurn() doesn't exist on this ITB build AND ITB-ModLoader
            -- is not installed, so there's no way to actually advance the turn
            -- from Lua alone — the engine only transitions on a real UI click
            -- on the End Turn button. We still SetActive all player pawns so
            -- the solver sees a consistent "no remaining actions" state, then
            -- hand back a NEEDS_MCP_CLICK sentinel so the Python side routes
            -- through plan_end_turn() and a computer_batch click dispatch.
            log_bridge("WARN: EndTurn() failed (" .. tostring(err) ..
                       "); SetActive only, caller must MCP-click End Turn")
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
            write_ack("NEEDS_MCP_CLICK END_TURN method=SetActive")
            return
        end
        -- Game:EndTurn() branch (reserved for future ITB builds that expose
        -- the method). Wait for the full player→enemy→player cycle.
        local start_count = -1
        pcall(function() start_count = Game:GetTurnCount() end)
        wait_until_coro(function()
            if Board:IsBusy() then return false end
            local cur_count = -1
            pcall(function() cur_count = Game:GetTurnCount() end)
            return cur_count > start_count
        end, 60)
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
        BaseUpdate     = Mission.BaseUpdate,
        NextTurn       = Mission.NextTurn,
        BaseStart      = Mission.BaseStart,
        MissionEnd     = Mission.MissionEnd,
        BaseDeployment = Mission.BaseDeployment,
    }
end

local _orig_BaseUpdate     = _ITB_BRIDGE_ORIGINALS.BaseUpdate
local _orig_NextTurn       = _ITB_BRIDGE_ORIGINALS.NextTurn
local _orig_BaseStart      = _ITB_BRIDGE_ORIGINALS.BaseStart
local _orig_MissionEnd     = _ITB_BRIDGE_ORIGINALS.MissionEnd
local _orig_BaseDeployment = _ITB_BRIDGE_ORIGINALS.BaseDeployment

-- Cached deployment zone (captured in BaseDeployment, cleared on MissionEnd)
_ITB_DEPLOY_ZONE = _ITB_DEPLOY_ZONE or {}

-- State dump interval (separate from command poll)
local _state_dump_interval = 5  -- dump state every 5 seconds
local _last_state_dump = 0

-- BaseUpdate: resume pending command coroutine, poll for new commands,
-- and periodically dump state. Coroutine resume happens FIRST so that
-- wait_for_board_coro yields get unblocked the moment the engine drains
-- its effect queue — without this, poll_commands could race a yielded
-- coroutine and clobber _running_coroutine.
Mission.BaseUpdate = function(self)
    _orig_BaseUpdate(self)
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
        pcall(function()
            local ptList = Board:GetZone("deployment")
            if ptList and ptList.size then
                local n = ptList:size()
                if n > 0 then
                    _ITB_DEPLOY_ZONE = {}
                    for i = 1, n do
                        local p = ptList:index(i)
                        _ITB_DEPLOY_ZONE[#_ITB_DEPLOY_ZONE + 1] = {p.x, p.y}
                    end
                    log_bridge("DEPLOY ZONE captured in BaseUpdate: " .. n .. " tiles")
                end
            end
        end)
    end
    -- Periodically dump state so Python can detect the bridge
    if now - _last_state_dump >= _state_dump_interval then
        _last_state_dump = now
        pcall(dump_state)
    end
end

-- NextTurn: dump state on each turn change
Mission.NextTurn = function(self)
    _orig_NextTurn(self)
    pcall(dump_state)
    log_bridge("TURN " .. (Game and Game:GetTurnCount() or "?") .. " team=" .. (Game and Game:GetTeamTurn() or "?"))
end

-- BaseStart: dump state when mission starts (after deployment)
Mission.BaseStart = function(self)
    _orig_BaseStart(self)
    pcall(dump_state)
    log_bridge("MISSION START: " .. tostring(self.ID or self.Name or "unknown"))
end

-- BaseDeployment: capture deployment zone AFTER engine sets it up
Mission.BaseDeployment = function(self)
    _orig_BaseDeployment(self)
    -- Capture zone AFTER original runs (engine creates the zone in BaseDeployment)
    pcall(function()
        -- Board:GetZone returns a PointList — iterate with :size()/:index()
        local ptList = Board:GetZone("deployment")
        _ITB_DEPLOY_ZONE = {}
        if ptList and ptList.size then
            local n = ptList:size()
            for i = 1, n do
                local p = ptList:index(i)
                _ITB_DEPLOY_ZONE[#_ITB_DEPLOY_ZONE + 1] = {p.x, p.y}
            end
        end
        if #_ITB_DEPLOY_ZONE > 0 then
            log_bridge("DEPLOY ZONE from Board:GetZone: " .. #_ITB_DEPLOY_ZONE .. " tiles")
        else
            log_bridge("DEPLOY ZONE: Board:GetZone returned 0 tiles")
        end
    end)
    -- Dump state so Python can see the deployment zone immediately
    pcall(dump_state)
end

-- MissionEnd: log mission completion, clear deployment zone
Mission.MissionEnd = function(self)
    log_bridge("MISSION END: " .. tostring(self.ID or self.Name or "unknown"))
    _ITB_DEPLOY_ZONE = {}
    _orig_MissionEnd(self)
end

--------------------------------------------------------------------
-- Startup
--------------------------------------------------------------------
-- Clean up stale files from previous session
pcall(function() os.remove(STATE_FILE) end)
pcall(function() os.remove(CMD_FILE) end)
pcall(function() os.remove(ACK_FILE) end)

local _reload_count = (_ITB_BRIDGE_LOAD_COUNT or 0) + 1
_ITB_BRIDGE_LOAD_COUNT = _reload_count

log_bridge("=== ITB Bot Bridge started (load #" .. _reload_count .. ") ===")
if ConsolePrint then
    ConsolePrint("ITB Bot Bridge loaded! IPC via /tmp/itb_*.json")
end
