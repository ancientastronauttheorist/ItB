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
-- Read piQueuedShot from save file for per-enemy target data
--------------------------------------------------------------------
local function _read_queued_shots()
    local shots = {}
    local base = os.getenv("HOME") ..
        "/Library/Application Support/IntoTheBreach/profile_Alpha/"
    -- Try saveData.lua first, fall back to undoSave.lua
    local sf = io.open(base .. "saveData.lua", "r")
    if not sf then
        sf = io.open(base .. "undoSave.lua", "r")
    end
    if not sf then return shots end
    local content = sf:read("*a")
    sf:close()

    for block in content:gmatch('%["pawn%d+"%]%s*=%s*(%b{})') do
        local pid = block:match('%["id"%]%s*=%s*(%d+)')
        local qs = block:match('%["piQueuedShot"%]%s*=%s*Point%s*%(([^%)]+)%)')
        if pid and qs then
            local qsx, qsy = qs:match('(%-?%d+)%s*,%s*(%-?%d+)')
            if qsx and qsy then
                shots[tonumber(pid)] = {x = tonumber(qsx), y = tonumber(qsy)}
            end
        end
    end
    return shots
end

--------------------------------------------------------------------
-- Read conveyor belt data from save file
-- Returns table: { "x,y" = direction_int } for conveyor tiles
-- Direction: 0=right(+x), 1=down(+y), 2=left(-x), 3=up(-y)
--------------------------------------------------------------------
local function _read_conveyor_belts()
    local belts = {}
    local base = os.getenv("HOME") ..
        "/Library/Application Support/IntoTheBreach/profile_Alpha/"
    local sf = io.open(base .. "saveData.lua", "r")
    if not sf then
        sf = io.open(base .. "undoSave.lua", "r")
    end
    if not sf then return belts end
    local content = sf:read("*a")
    sf:close()

    -- Match: ["loc"] = Point( x, y ), ... ["custom"] = "conveyorN.png"
    -- These appear in the map_data.map array
    for loc_x, loc_y, custom in content:gmatch(
        '%["loc"%]%s*=%s*Point%(%s*(%d+)%s*,%s*(%d+)%s*%).-'
        .. '%["custom"%]%s*=%s*"(conveyor%d+%.png)"'
    ) do
        local dir = custom:match("conveyor(%d+)")
        if dir then
            local key = loc_x .. "," .. loc_y
            belts[key] = tonumber(dir)
        end
    end
    return belts
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
    -- Live grid power from Game API (not stale save file GameData.network)
    local ok_gp, gp = pcall(function() return Game:GetPower() end)
    if ok_gp and gp then
        state.grid_power = gp.iPower or 0
        state.grid_power_max = gp.iMax or 7
    else
        state.grid_power = GameData and GameData.network or 0
        state.grid_power_max = GameData and GameData.networkMax or 7
    end
    state.timestamp = os.time()

    -- Read conveyor belt data from save file
    local conveyor_belts = _read_conveyor_belts()

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
                tile.population = 1
            end

            -- Pod
            local ok_p, pod = pcall(function() return Board:IsPod(pt) end)
            if ok_p and pod then tile.pod = true end

            state.tiles[#state.tiles + 1] = tile
        end
    end

    -- Read queued shots from save file (for per-enemy target data)
    local queued_shots = _read_queued_shots()

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

    -- Environment danger
    state.environment_danger = {}
    for y = 0, 7 do
        for x = 0, 7 do
            local ok, danger = pcall(function() return Board:IsEnvironmentDanger(Point(x, y)) end)
            if ok and danger then
                state.environment_danger[#state.environment_danger + 1] = {x, y}
            end
        end
    end

    -- Deployment zone
    if _ITB_DEPLOY_ZONE and #_ITB_DEPLOY_ZONE > 0 then
        -- Use captured zone from BaseDeployment (final missions / special maps)
        state.deployment_zone = _ITB_DEPLOY_ZONE
    elseif state.phase ~= "combat_player" then
        -- Heuristic fallback: during deployment, scan for open ground tiles
        -- in the left portion of the board (columns 0-3), which matches the
        -- standard deployment zone for regular missions.
        local zone = {}
        for y = 0, 7 do
            for x = 0, 3 do
                local pt = Point(x, y)
                local terrain = Board:GetTerrain(pt)
                if terrain == 0 then  -- ground only
                    local pawn = Board:GetPawn(pt)
                    if not pawn then
                        zone[#zone + 1] = {x, y}
                    end
                end
            end
        end
        if #zone > 0 then
            state.deployment_zone = zone
        end
    end

    write_atomic(STATE_FILE, STATE_TMP, json_encode(state))
end

--------------------------------------------------------------------
-- Command executor
--------------------------------------------------------------------
local function write_ack(msg)
    write_atomic(ACK_FILE, ACK_TMP, msg)
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

    local cmd = parts[1]

    if cmd == "MOVE" then
        -- MOVE uid x y
        local uid = tonumber(parts[2])
        local x, y = tonumber(parts[3]), tonumber(parts[4])
        local pawn = Board:GetPawn(uid)
        if not pawn then
            write_ack("ERROR: pawn " .. uid .. " not found")
            return
        end
        local ok, err = pcall(function() pawn:Move(Point(x, y)) end)
        if ok then
            write_ack("OK MOVE " .. uid .. " to " .. x .. "," .. y)
        else
            write_ack("ERROR: Move failed: " .. tostring(err))
        end

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
        -- Look up weapon definition for damage value
        local wdef = _G[weapon_id]
        if not wdef then
            write_ack("ERROR: weapon " .. weapon_id .. " not found")
            return
        end
        local damage = wdef.Damage or 1
        local ppos = pawn:GetSpace()

        -- Calculate push direction from source -> target
        local dx = tx - ppos.x
        local dy = ty - ppos.y
        local push_dir = DIR_NONE
        if     dx ==  1 and dy ==  0 then push_dir = DIR_RIGHT
        elseif dx == -1 and dy ==  0 then push_dir = DIR_LEFT
        elseif dx ==  0 and dy ==  1 then push_dir = DIR_UP
        elseif dx ==  0 and dy == -1 then push_dir = DIR_DOWN
        end

        -- Check if weapon has push (most Prime/Brute weapons do)
        local has_push = wdef.Push == 1 or wdef.Push == true
        -- Override: known push weapons
        if weapon_id == "Prime_Punchmech" or weapon_id == "Brute_Tankmech" then
            has_push = true
        end

        local ok, err = pcall(function()
            -- Apply damage to target tile
            if has_push and push_dir ~= DIR_NONE then
                -- DamageSpace with push direction
                local sd = SpaceDamage(Point(tx, ty), damage, push_dir)
                Board:DamageSpace(sd)

                -- Check if push actually moved the target
                -- DamageSpace handles push internally when iPush is set
            else
                -- Damage only (ranged/artillery weapons)
                local sd = SpaceDamage(Point(tx, ty), damage)
                Board:DamageSpace(sd)
            end
        end)

        if ok then
            write_ack("OK ATTACK " .. uid .. " " .. weapon_id .. " at " .. tx .. "," .. ty)
        else
            write_ack("ERROR: Attack failed: " .. tostring(err))
        end

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
        -- Move first
        local ok1, err1 = pcall(function() pawn:Move(Point(mx, my)) end)
        if not ok1 then
            write_ack("ERROR: Move failed: " .. tostring(err1))
            return
        end
        -- Then attack using DamageSpace (same logic as ATTACK)
        local wdef = _G[weapon_id]
        if not wdef then
            write_ack("ERROR: weapon " .. weapon_id .. " not found")
            return
        end
        local damage = wdef.Damage or 1
        local dx = tx - mx
        local dy = ty - my
        local push_dir = DIR_NONE
        if     dx ==  1 and dy ==  0 then push_dir = DIR_RIGHT
        elseif dx == -1 and dy ==  0 then push_dir = DIR_LEFT
        elseif dx ==  0 and dy ==  1 then push_dir = DIR_UP
        elseif dx ==  0 and dy == -1 then push_dir = DIR_DOWN
        end
        local has_push = wdef.Push == 1 or wdef.Push == true
        if weapon_id == "Prime_Punchmech" or weapon_id == "Brute_Tankmech" then
            has_push = true
        end

        local ok2, err2 = pcall(function()
            if has_push and push_dir ~= DIR_NONE then
                Board:DamageSpace(SpaceDamage(Point(tx, ty), damage, push_dir))
            else
                Board:DamageSpace(SpaceDamage(Point(tx, ty), damage))
            end
        end)
        if ok2 then
            write_ack("OK MOVE_ATTACK " .. uid)
        else
            write_ack("ERROR: Attack failed: " .. tostring(err2))
        end

    elseif cmd == "END_TURN" then
        -- Mark all player mechs as inactive (done for this turn)
        local ok, err = pcall(function()
            local mech_ids = extract_table(Board:GetPawns(TEAM_PLAYER))
            for _, mid in ipairs(mech_ids) do
                local m = Board:GetPawn(mid)
                if m then m:SetActive(false) end
            end
        end)
        if ok then
            write_ack("OK END_TURN")
        else
            write_ack("ERROR: END_TURN failed: " .. tostring(err))
            log_bridge("END_TURN ERROR: " .. tostring(err))
        end

    elseif cmd == "LUA" then
        -- Raw Lua execution (for debugging)
        local lua_code = cmd_str:sub(5)
        local ok, result = pcall(loadstring(lua_code))
        write_ack(ok and ("OK LUA: " .. tostring(result)) or ("ERROR LUA: " .. tostring(result)))

    else
        write_ack("ERROR: unknown command: " .. cmd)
    end

    -- Dump state after every command
    pcall(dump_state)
end

local function poll_commands()
    local f = io.open(CMD_FILE, "r")
    if f then
        local cmd = f:read("*a")
        f:close()
        os.remove(CMD_FILE)
        if cmd and cmd:match("%S") then
            log_bridge("CMD: " .. cmd:gsub("\n", " "))
            execute_command(cmd:match("^%s*(.-)%s*$"))  -- trim whitespace
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

-- BaseUpdate: poll for commands AND periodically dump state
Mission.BaseUpdate = function(self)
    _orig_BaseUpdate(self)
    local now = os.clock()
    if now - _last_poll >= _poll_interval then
        _last_poll = now
        pcall(poll_commands)
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

-- BaseDeployment: capture deployment zone before engine clears it
Mission.BaseDeployment = function(self)
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
            log_bridge("DEPLOY ZONE: Board:GetZone returned 0 tiles (fallback will be used)")
        end
    end)
    _orig_BaseDeployment(self)
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
