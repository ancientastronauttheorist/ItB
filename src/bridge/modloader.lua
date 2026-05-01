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
        difficulty = nil,     -- GameData.difficulty (0=Easy, 1=Normal, 2=Hard, 3=Unfair)
        queued_shots = {},
        queued_targets = {},  -- [pawn_id] = {x, y} from piTarget (leap/melee landing tile)
        queued_skills = {},   -- [pawn_id] = iQueuedSkill (>=0 when an attack is actually queued)
        conveyor_belts = {},
        pilots = {},  -- [pawn_id] = {id=..., level=..., skill1=..., skill2=...}
        master_seed = nil,    -- GameData.seed — run-lifetime master RNG seed
        mission_seeds = {},   -- [region_key] = aiSeed — per-mission per-turn PRNG snapshot
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
            -- Queued shot (projectile/laser/artillery end-tile)
            local qs = block:match('%["piQueuedShot"%]%s*=%s*Point%s*%(([^%)]+)%)')
            if qs then
                local qsx, qsy = qs:match('(%-?%d+)%s*,%s*(%-?%d+)')
                if qsx and qsy then
                    result.queued_shots[pid_n] = {x = tonumber(qsx), y = tonumber(qsy)}
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
local function dump_state()
    if not Board then return end

    local state = {}

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
            elseif terrain_id == 4 then
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
                    base_move = pawn_def and pawn_def.MoveSpeed or p:GetMoveSpeed(),
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

                    -- Per-enemy target: piQueuedShot first (projectile/laser/
                    -- artillery attacks), then piTarget (leap/melee landing
                    -- tile — used by Jumper pawns like Leaper1/Leaper2 where
                    -- piQueuedShot is (-1,-1)), then Lua API probes. We must
                    -- gate the piTarget read on iQueuedSkill >= 0 because the
                    -- save stores piTarget as a stale last-target even on
                    -- pawns that have no queued skill this turn.
                    local qs = save_data.queued_shots[pid]
                    if qs and qs.x >= 0 and qs.y >= 0 then
                        unit.queued_target = {qs.x, qs.y}
                    elseif unit.has_queued_attack then
                        local resolved_via = nil
                        -- (1) Save-file piTarget (works for Leapers, Scorpions,
                        --     any melee/jumper pawn with AddQueuedMelee).
                        local qt = save_data.queued_targets[pid]
                        local qskill = save_data.queued_skills[pid]
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

    -- Attack order: enemies with queued attacks sorted by UID (ascending)
    state.attack_order = {}
    for _, u in ipairs(state.units) do
        if u.team == 6 and u.has_queued_attack then
            state.attack_order[#state.attack_order + 1] = u.uid
        end
    end
    table.sort(state.attack_order)

    -- Webber fallback: for any webbed unit without a known web_source_uid
    -- (Lua API didn't expose it), pick the closest alive enemy whose primary
    -- weapon has Web=true. ITB rule: web breaks when webber is pushed or killed,
    -- so the solver needs to know which enemy unwebs the unit. If no webber is
    -- found (all dead), clear the stale web flag entirely.
    local WEB_WEAPONS = {ScorpionAtk1=true, ScorpionAtk2=true, ScorpionAtkB=true,
                         LeaperAtk1=true, LeaperAtk2=true}
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
    --                     Air Strike / Lightning / Satellite emit
    --                     flying_immune=0 — those hit flyers too.
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

    -- Helper: add a danger tile to both v1 and v2 fields. The optional
    -- `flying_immune_override` controls the 5th field (Satellite Rocket
    -- forces it false — bombs hit flyers).
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
                            -- Always lethal, never flying-immune (rockets
                            -- detonate above ground level — flyers caught).
                            add_danger(nx, ny, true, false)
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
            state.mission_id = mission.ID
        end
    end)

    -- Teleporter pads: populated by the Mission_Teleporter:StartMission
    -- wrap below. Each entry = {x1, y1, x2, y2}. Empty list / absent on
    -- non-teleporter missions; the Rust/Python simulators ignore an empty
    -- list (pre-sim-v8 behavior). The earlier Board.AddTeleport global
    -- override crashed mac OS at file-load with "no static 'AddTeleport'
    -- in class 'Board'" (commit 456ba49 → rolled back in 63e0e18); the
    -- current scope-rebinds AddTeleport only inside StartMission and pcalls
    -- everything so a future API change can't take down mission load.
    if _ITB_TELEPORT_PAIRS and #_ITB_TELEPORT_PAIRS > 0 then
        state.teleporter_pairs = {}
        for _, pair in ipairs(_ITB_TELEPORT_PAIRS) do
            state.teleporter_pairs[#state.teleporter_pairs + 1] = pair
        end
    end

    -- Bonus-objective progress for "Kill N enemies" (BONUS_KILL_FIVE = 6).
    -- Emitted so the Python evaluator can reward plans that reach the
    -- cumulative kill target. Absent / 0 → no kill-N bonus on this mission;
    -- the evaluator's step-function check neutralizes safely. Per
    -- scripts/missions/missions.lua:
    --   BONUS_KILL_FIVE = 6 in the enum
    --   mission.BonusObjs is the chosen bonus list (random from BonusPool)
    --   mission.KilledVek is cumulative this-mission kills
    --   mission:GetKillBonus() is difficulty-scaled (5 easy / 7 normal/hard)
    pcall(function()
        local mission = _ITB_CURRENT_MISSION
        if mission and mission.BonusObjs then
            local has_kill_five = false
            for _, obj in ipairs(mission.BonusObjs) do
                if obj == 6 then has_kill_five = true; break end
            end
            if has_kill_five and mission.GetKillBonus then
                local ok, target = pcall(function() return mission:GetKillBonus() end)
                if ok and type(target) == "number" then
                    state.mission_kill_target = target
                end
            end
            if mission.KilledVek ~= nil then
                state.mission_kills_done = mission.KilledVek
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

-- execute_weapon_by_slot: fire weapon using a 0-based slot index from
-- the Python side (maps to 1-indexed Lua SkillList).
-- This avoids name-matching issues where the solver's weapon ID doesn't
-- match the pawn type's SkillList entry (e.g. purchased / upgraded weapons,
-- or names the Rust solver doesn't recognise → "Unknown").
local function execute_weapon_by_slot(pawn, weapon_slot, tx, ty)
    -- weapon_slot is 0-based from Python; Lua SkillList is 1-indexed
    local slot = weapon_slot + 1
    local ptype = pawn:GetType()
    local pawn_def = _G[ptype]
    local skill_count = 0
    if pawn_def and pawn_def.SkillList then
        skill_count = #pawn_def.SkillList
    end
    if skill_count == 0 or slot > skill_count then
        return false, "weapon slot " .. weapon_slot ..
               " out of range (pawn " .. ptype ..
               " has " .. skill_count .. " skills)"
    end
    local wname = pawn_def.SkillList[slot]
    local source = pawn:GetSpace()
    local ok, err = pcall(function()
        pawn:FireWeapon(Point(tx, ty), slot)
    end)
    if not ok then
        log_bridge("WARN: FireWeapon failed for slot " .. slot ..
                   " (" .. wname .. "): " .. tostring(err))
        return false, "FireWeapon failed: " .. tostring(err)
    end
    log_bridge("FIRE: " .. wname .. " slot=" .. slot .. " " ..
               source.x .. "," .. source.y .. " -> " .. tx .. "," .. ty)

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
    local is_transit_leap =
        string.find(wname, "^Brute_Jetmech") ~= nil or
        string.find(wname, "^Brute_Bombrun") ~= nil
    if is_transit_leap then
        local skill = _G[wname]
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
                for k = 1, dist - 1 do
                    local nx = source.x + sx * k
                    local ny = source.y + sy * k
                    local tp = Point(nx, ny)
                    -- FireWeapon DOES apply transit damage to any unit
                    -- standing on the transit tile (observed 2026-04-24
                    -- turn 1 and turn 2: acid-statused Firefly1 on
                    -- transit died after 1 of our manual + 1 of the
                    -- engine's damage, instead of surviving at HP=1).
                    -- FireWeapon does NOT damage terrain (buildings /
                    -- mountains on transit) and does NOT emit the
                    -- tile's smoke/acid effect — both are still on us.
                    -- So: apply damage ONLY to tiles without a live
                    -- unit (FireWeapon handles those), and always
                    -- apply smoke/acid flags via a damage=0 SpaceDamage.
                    local occupant = Board:GetPawn(tp)
                    local has_live = occupant ~= nil and not occupant:IsDead()
                    local dmg_val = has_live and 0 or skill.Damage
                    local sd = SpaceDamage(tp, dmg_val)
                    if skill.Smoke and skill.Smoke > 0 then
                        sd.iSmoke = skill.Smoke
                    end
                    if skill.Acid and skill.Acid > 0 then
                        sd.iAcid = skill.Acid
                    end
                    local ok_d, err_d = pcall(function()
                        Board:DamageSpace(sd)
                    end)
                    if ok_d then
                        if dmg_val > 0 then dmg_applied = dmg_applied + 1 end
                        if skill.Smoke and skill.Smoke > 0 then
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
        local ok1, err1 = pcall(function() pawn:Move(Point(mx, my)) end)
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

-- BaseUpdate: resume pending command coroutine, poll for new commands,
-- and periodically dump state. Coroutine resume happens FIRST so that
-- wait_for_board_coro yields get unblocked the moment the engine drains
-- its effect queue — without this, poll_commands could race a yielded
-- coroutine and clobber _running_coroutine.
Mission.BaseUpdate = function(self)
    _orig_BaseUpdate(self)
    -- Cache current mission (self is the active mission inside BaseUpdate)
    _ITB_CURRENT_MISSION = self
    -- Heartbeat: write mtime so Python can detect stuck/dead bridge
    pcall(function()
        local f = io.open("/tmp/itb_bridge_heartbeat", "w")
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
    pcall(dump_state)
    log_bridge("MISSION START: " .. tostring(self.ID or self.Name or "unknown"))
end

-- BaseDeployment: capture deployment zone AFTER engine sets it up
Mission.BaseDeployment = function(self)
    _orig_BaseDeployment(self)
    _ITB_CURRENT_MISSION = self
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
