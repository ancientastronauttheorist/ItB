-- Offline checks of the Lua bridge (src/bridge/modloader.lua) in the game's
-- Lua version (5.1), against game_mock.lua. Run by itb_tests
-- (test_bridge.cpp) or by hand:
--
--   engine/build/itb_lua51 engine/tests/bridge/bridge_harness.lua \
--       src/bridge/modloader.lua engine/tests/bridge/game_mock.lua <empty dir>
--
-- It loads the real bridge with the game API mocked strictly (luabind
-- arity and types), then checks the pure helpers, a full state dump (old
-- fields still there, new fields right), the hooks the bridge installs, and
-- the commands, including the SCENARIO coroutine with a board that stays
-- busy across frames. Raises with every failed check.

local MODLOADER = HARNESS_MODLOADER or arg[1]
local MOCK_FILE = HARNESS_MOCK or arg[2]
local DIR = HARNESS_DIR or arg[3]
assert(MODLOADER and MOCK_FILE and DIR, "usage: bridge_harness.lua <modloader.lua> <game_mock.lua> <dir>")

local failures = {}
local checks = 0
local function check(cond, msg)
    checks = checks + 1
    if not cond then failures[#failures + 1] = msg end
end
local function eq(a, b, msg)
    check(a == b, msg .. ": expected " .. tostring(b) .. ", got " .. tostring(a))
end

---------------------------------------------------------------- sandbox
-- The bridge reads its directories from the environment and writes
-- /tmp files by default: point everything at DIR. No shell commands.
local real_getenv = os.getenv
os.getenv = function(name)
    if name == "ITB_BRIDGE_DIR" or name == "ITB_SAVE_DIR" then return DIR end
    return real_getenv(name)
end
local real_execute = os.execute
os.execute = function() return 0 end
local CLOCK = 1000
os.clock = function() return CLOCK end

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local s = f:read("*a")
    f:close()
    return s
end
local function write_file(path, text)
    local f = assert(io.open(path, "w"))
    f:write(text)
    f:close()
end

---------------------------------------------------------------- game data
local MOCK = dofile(MOCK_FILE)

-- Pawn and weapon tables (plain Lua, like the game's scripts).
PunchMech = {Health = 3, MoveSpeed = 3, SkillList = {"Prime_Punchmech"}, Massive = true,
             Corpse = true, DefaultTeam = 1}
LimitMech = {Health = 3, MoveSpeed = 3, SkillList = {"Ranged_Limited"}, Corpse = true}
Firefly1 = {Health = 3, MoveSpeed = 2, SkillList = {"FireflyAtk1"}}
Scorpion1 = {Health = 3, MoveSpeed = 3, SkillList = {"ScorpionAtk1"}}
Jelly_Health1 = {Health = 2, MoveSpeed = 2, SkillList = {}, Leader = 1, Flying = true}
Train_Pawn = {Health = 1, MoveSpeed = 0, SkillList = {"Train_Move"}, DefaultTeam = 1,
              ExtraSpaces = {Point(0, 1)}, Pushable = false}
Prime_Punchmech = {Damage = 2}
Prime_Punchmech_B = {Damage = 3}
Ranged_Limited = {Damage = 2, Limited = 2}
Passive_Electric = {Passive = "Electric_Smoke"}
Passive_Electric_A = {Passive = "Electric_Smoke_A"}
FireflyAtk1 = {Damage = 1}
ScorpionAtk1 = {Damage = 1}
Train_Move = {Damage = 0}

-- Board: mechs 0 and 1, a train (main tile (4,4), extra (4,5)), two Vek, a
-- psion; buildings, ice, lava, a custom tile; a lightning mission.
local mech0 = MOCK.add_pawn{id = 0, type = "PunchMech", x = 2, y = 2, team = 1, mech = true, shots = 1}
local mech1 = MOCK.add_pawn{id = 1, type = "LimitMech", x = 3, y = 3, team = 1, mech = true, shots = 2}
local vek_a = MOCK.add_pawn{id = 50, type = "Firefly1", x = 5, y = 5, team = 6, selected_weapon = 1}
local vek_b = MOCK.add_pawn{id = 51, type = "Scorpion1", x = 6, y = 2, team = 6, selected_weapon = 1}
local psion = MOCK.add_pawn{id = 52, type = "Jelly_Health1", x = 7, y = 7, team = 6}
local train = MOCK.add_pawn{id = 60, type = "Train_Pawn", x = 4, y = 4, team = 1}
MOCK.tiles[0][0].terrain = TERRAIN_BUILDING
MOCK.tiles[0][0].hp, MOCK.tiles[0][0].max, MOCK.tiles[0][0].populated = 1, 1, true
MOCK.tiles[1][0].terrain = TERRAIN_BUILDING
MOCK.tiles[1][0].hp, MOCK.tiles[1][0].max, MOCK.tiles[1][0].populated = 2, 2, false
MOCK.tiles[6][6].terrain = TERRAIN_ICE
MOCK.tiles[6][6].hp, MOCK.tiles[6][6].max = 1, 2
MOCK.tiles[7][0].terrain, MOCK.tiles[7][0].lava = TERRAIN_WATER, true
MOCK.tiles[0][7].custom = "conveyor1.png"
MOCK.tiles[1][1].env, MOCK.tiles[5][2].env = true, true
MOCK.tiles[1][5].targeted = true
MOCK.zones.enemy = {{6, 0}, {6, 1}, {7, 1}}
MOCK.zones.deployment = {{1, 3}, {2, 3}}
MOCK.spawns = {{type = "Firefly1", x = 6, y = 3, id = 70}, {type = "Scorpion1", x = 5, y = 1, id = 71}}

local M = Mission_Lightning:new()
M.ID = "Mission_Lightning"
M.TurnLimit = 5
M.BonusObjs = {5, 6}
M.PowerStart = 6
M.BlockedSpawns = 1
M.KilledVek = 2
M.Spawner = {num_spawns = 5, pawn_counts = {Firefly = 2}}
M.LiveEnvironment = Env_Lightning:new({Locations = {Point(1, 1), Point(5, 2)}, Planned = {Point(1, 1), Point(5, 2)}})
GAME = {Missions = {[0] = Mission:new{ID = "Mission_Final"}, [3] = M}}

-- Save: the active region is 3; region 1 is a decoy whose pawn 0 has
-- other weapons.
local function pawn_block(n, body) return '["pawn' .. n .. '"] = {' .. body .. '},\n' end
local region3 = '["region3"] = {["mission"] = "Mission3", ["player"] = {["iCurrentTurn"] = 1, '
    .. '["iTeamTurn"] = 1, ["map_data"] = {\n'
    .. pawn_block(1, '["type"] = "PunchMech", ["id"] = 0, ["mech"] = true, '
        .. '["primary"] = "Prime_Punchmech", ["primary_power"] = {}, ["primary_mod1"] = {0, 0, }, '
        .. '["primary_mod2"] = {1, 1, 1, }, ["primary_uses"] = 1, ["secondary"] = "Passive_Electric", '
        .. '["secondary_power"] = {1, }, ["secondary_mod1"] = {1, }, ["secondary_mod2"] = {}, '
        .. '["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["exp"] = 17, ["level"] = 1, '
        .. '["skill1"] = 7, ["skill2"] = 12, }, ["iMutation"] = 0, ["iQueuedSkill"] = -1')
    .. pawn_block(2, '["type"] = "LimitMech", ["id"] = 1, ["mech"] = true, '
        .. '["primary"] = "Ranged_Limited", ["primary_mod1"] = {0, }, ["primary_mod2"] = {0, }, '
        .. '["primary_uses"] = 2, ["primary_damaged"] = false, '
        .. '["pilot"] = {["id"] = "Pilot_Rock", ["exp"] = 3, ["level"] = 0, ["skill1"] = 1, ["skill2"] = 2, }, '
        .. '["iQueuedSkill"] = -1')
    .. pawn_block(3, '["type"] = "Firefly1", ["id"] = 50, ["mech"] = false, ["iMutation"] = 1, '
        .. '["piTarget"] = Point(5,4), ["piOrigin"] = Point(5,5), ["piQueuedShot"] = Point(5,4), ["iQueuedSkill"] = 1')
    .. pawn_block(4, '["type"] = "Scorpion1", ["id"] = 51, ["mech"] = false, ["iMutation"] = 1, '
        .. '["piTarget"] = Point(6,3), ["piOrigin"] = Point(6,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = 1')
    .. pawn_block(5, '["type"] = "Train_Pawn", ["id"] = 60, ["mech"] = false, '
        .. '["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(4,3), ["iQueuedSkill"] = 1')
    .. '["pawn_count"] = 5, ["blocked_points"] = {Point(1,1), Point(5,2), },\n'
    .. '["blocked_type"] = {1, 1, },\n'
    .. '["spawns"] = {"Firefly1", "Scorpion1", },\n'
    .. '["spawn_ids"] = {70, 71, },\n'
    .. '["spawn_points"] = {Point(6,3), Point(5,1), },\n'
    .. '}, }, }, \n'
local region1 = '["region1"] = {["mission"] = "Mission1", ["player"] = {["iCurrentTurn"] = 3, ["map_data"] = {\n'
    .. pawn_block(1, '["type"] = "PunchMech", ["id"] = 0, ["primary"] = "Decoy_Gun", ["primary_uses"] = 1')
    .. '["spawns"] = {"Decoy1", },\n["spawn_ids"] = {9, },\n["spawn_points"] = {Point(0,0), },\n'
    .. '}, }, }, \n'
local save_dir = DIR .. "/profile_Alpha"
if not io.open(save_dir .. "/.probe", "w") then
    real_execute('mkdir -p "' .. save_dir .. '"')
end
write_file(save_dir .. "/saveData.lua",
    'GameData = {["network"] = 5, ["networkMax"] = 7, ["difficulty"] = 1, ["seed"] = 42, '
    .. '["weapons"] = {"Prime_Punchmech_B", "Passive_Electric_A", "Ranged_Limited", "", "", "", }, }\n'
    .. 'RegionData = {\n' .. region1 .. region3 .. '["iBattleRegion"] = 3, }\n')

---------------------------------------------------------------- load
local chunk, load_err = loadfile(MODLOADER)
assert(chunk, "modloader.lua does not compile: " .. tostring(load_err))
chunk()
local X = _ITB_BRIDGE_EXT
assert(type(X) == "table", "bridge extension table missing")

eq(#MOCK.mismatches, 0, "strict-call mismatches while loading")
check(Mission.BaseUpdate ~= nil and Mission.BaseNextTurn ~= nil, "Mission hooks present")
check(_ITB_BRIDGE_ORIGINALS.BaseNextTurn ~= Mission.BaseNextTurn, "BaseNextTurn wrapped")
check(_ITB_BRIDGE_ORIGINALS.ApplyEnvironmentEffect ~= Mission.ApplyEnvironmentEffect, "ApplyEnvironmentEffect wrapped")
check(_ITB_BRIDGE_ORIGINALS.PlanEnvironment ~= Mission.PlanEnvironment, "PlanEnvironment wrapped")

---------------------------------------------------------------- helpers
do
    local v = X.json_decode('{"a": [1, 2.5, -3e2, true, false, null, "x\\"y\\n\\u0041"], "b": {}, "c": {"d": null}}')
    eq(v.a[1], 1, "json int")
    eq(v.a[2], 2.5, "json float")
    eq(v.a[3], -300, "json exponent")
    eq(v.a[4], true, "json true")
    eq(v.a[5], false, "json false")
    check(rawequal(v.a[6], X.JSON_NULL), "json null kept in arrays")
    eq(v.a[7], 'x"y\nA', "json escapes")
    eq(next(v.b), nil, "json empty object")
    eq(v.c.d, nil, "json null dropped from objects")
    for _, bad in ipairs({'{"a": }', '[1, 2', '{"a" 1}', '"abc', '{} x'}) do
        check(not pcall(X.json_decode, bad), "json rejects " .. bad)
    end

    local cyc = {name = "c"}
    cyc.self = cyc
    local ctx = X.new_dump_ctx()
    local d = X.dump_value({p = Point(3, 4), list = {Point(1, 2), Point(3, 4)}, f = function() end,
                           nan = 0 / 0, inf = math.huge, cyc = cyc, deep = {{{{{1}}}}},
                           mixed = {1, 2, x = 3}, [7] = "seven"}, 0, ctx)
    eq(d.p.x, 3, "dump Point x")
    eq(d.list[2].y, 4, "dump Point array")
    eq(d.f, nil, "dump skips functions")
    eq(d.nan, "nan", "dump NaN as string")
    eq(d.inf, "inf", "dump inf as string")
    eq(d.cyc.self, "<cycle>", "dump cycle")
    eq(d.deep[1][1][1], "<depth>", "dump depth limit")
    eq(d.mixed.x, 3, "mixed table becomes object")
    eq(d.mixed["1"], 1, "mixed table keeps array part")
    eq(d["7"], "seven", "numeric key as string")
    check(ctx.truncated, "depth limit flagged")

    local save = X.parse_save(read_file(save_dir .. "/saveData.lua"))
    eq(save.battle_region, 3, "save battle region")
    eq(save.mission, "Mission3", "save region mission")
    eq(save.turn, 1, "save region turn")
    eq(#save.spawns, 2, "save spawn count")
    eq(save.spawns[1].type, "Firefly1", "save spawn 1 type")
    eq(save.spawns[2].x, 5, "save spawn 2 x")
    eq(save.spawns[2].uid, 71, "save spawn 2 uid")
    eq(save.pawns[0].weapons[1].base, "Prime_Punchmech", "save uses the active region's pawn 0")
    eq(save.pawns[0].pilot.xp, 17, "save pilot xp")
    eq(save.pawns[51].queued_target[1], 6, "save piTarget")
    eq(save.spawn_blocks[2][3], 1, "save blocked spawn type")

    eq(X.exact_weapon_id({base = "Prime_Punchmech", mod1 = {0, 0}, mod2 = {1, 1, 1}}), "Prime_Punchmech_B", "exact id _B")
    eq(X.exact_weapon_id({base = "Passive_Electric", mod1 = {1}, mod2 = {}}), "Passive_Electric_A", "exact id passive _A")
    eq(X.exact_weapon_id({base = "Prime_Punchmech", mod1 = {}, mod2 = {}}), "Prime_Punchmech", "exact id base")

    -- One limited weapon (2 saved) + one passive: 2 shots left reads as
    -- 2 (passive not a skill) or 1 (passive a skill): ambiguous until
    -- calibrated.
    local ws = {{slot = 0, base = "Ranged_Limited", mod1 = {}, mod2 = {}, uses = 2},
                {slot = 1, base = "Passive_Electric", mod1 = {}, mod2 = {}, uses = 1}}
    local slots = X.weapon_slots(ws, 2)
    check(slots[1].uses_ambiguous, "limited + passive uncalibrated is ambiguous")
    slots = X.weapon_slots(ws, 2, 1)
    eq(slots[1].uses, 1, "calibrated limited uses")
    eq(slots[1].uses_basis, "calibrated", "calibrated basis")
    slots = X.weapon_slots({ws[1]}, 1)
    eq(slots[1].uses, 1, "single limited weapon")
    eq(slots[1].limited, 2, "limited count from the weapon table")
end

---------------------------------------------------------------- dump
local function load_state(path)
    local text = read_file(path or (DIR .. "/itb_state.json"))
    assert(text, "no state file at " .. tostring(path))
    local ok, st = pcall(X.json_decode, text)
    assert(ok, "state is not valid JSON: " .. tostring(st))
    return st
end
local function unit(st, uid, extra)
    for _, u in ipairs(st.units) do
        if u.uid == uid and (u.is_extra_tile == true) == (extra == true) then return u end
    end
    return nil
end

_ITB_CURRENT_MISSION = M
X._dump_state()
eq(#MOCK.mismatches, 0, "strict-call mismatches during the dump")
local st = load_state()
do
    -- Old fields.
    eq(#st.tiles, 64, "64 tiles")
    eq(st.phase, "combat_player", "phase")
    eq(st.grid_power, 5, "grid from the save")
    eq(st.mission_id, "Mission_Lightning", "mission id")
    eq(st.total_turns, 5, "TurnLimit")
    check(unit(st, 60, true) ~= nil, "train extra tile still emitted")
    eq(#st.attack_order, 2, "attack_order: two Vek")
    eq(#st.environment_danger_v2, 2, "env danger")
    eq(#st.spawning_tiles, 2, "spawning tiles")
    -- New fields.
    eq(#st.bridge_errors, 0, "bridge_errors empty (" .. (st.bridge_errors[1] and st.bridge_errors[1].where .. ": " .. st.bridge_errors[1].error or "") .. ")")
    eq(st.bridge_ext_version, 1, "ext version")
    eq(st.bridge_debug, false, "debug off")
    local ms = st.mission_state
    check(ms ~= nil, "mission_state present")
    if ms then
        eq(ms.key, 3, "mission key")
        eq(ms.native_key, "Mission3", "native key")
        eq(ms.class_chain[1], "Mission_Lightning", "mission class")
        eq(ms.class_chain[2], "Mission", "mission base class")
        eq(ms.env_class_chain[1], "Env_Lightning", "env class")
        eq(ms.env_class_chain[2], "Env_Attack", "env base class")
        eq(ms.turn_limit, 5, "turn limit")
        eq(ms.instance.BlockedSpawns, 1, "instance field")
        eq(ms.instance.LiveEnvironment, nil, "LiveEnvironment not inside the mission dump")
        eq(ms.instance.Spawner.num_spawns, 5, "nested instance table")
        eq(ms.env_instance.Locations[2].x, 5, "env Locations as points")
        eq(ms.sector, 2, "sector")
    end
    eq(#st.spawn_queue, 2, "spawn queue")
    eq(st.spawn_queue[1].type, "Firefly1", "spawn queue order")
    eq(st.spawn_queue_source, "save", "spawn queue source")
    eq(st.spawn_queue_matches_markers, true, "queue matches markers")
    eq(st.mission_power_start, 6, "PowerStart")
    eq(st.mission_blocked_spawns, 1, "BlockedSpawns with BONUS_BLOCK")
    eq(st.bonus_objective_ids[2], 6, "bonus ids")
    eq(st.zones.enemy[3][1], 7, "zone points")
    local m0 = unit(st, 0)
    eq(m0.weapons_exact[1], "Prime_Punchmech_B", "mech 0 exact primary")
    eq(m0.weapons_exact[2], "Passive_Electric_A", "mech 0 exact passive")
    eq(m0.weapons[1], "Prime_Punchmech", "old weapons field untouched")
    eq(m0.pilot.xp, 17, "pilot xp")
    eq(m0.pilot.skill2, 12, "pilot skill2")
    eq(m0.pilot_skills[1], "skill1=7", "old pilot_skills untouched")
    local m1 = unit(st, 1)
    eq(m1.shots_remaining, 2, "shots remaining")
    eq(m1.weapon_slots[1].uses, 2, "limited uses (calibrated at turn start)")
    eq(m1.weapon_slots[1].uses_basis, "calibrated", "uses basis")
    local t = unit(st, 60)
    eq(t.queued_any.target[2], 3, "train queued shot")
    eq(t.extra_spaces[1][2], 1, "train extra space")
    eq(t.has_queued_attack, nil, "train has no old-style queued fields")
    local p = unit(st, 52)
    eq(p.traits.leader, 1, "psion Leader trait")
    eq(p.traits.flying, true, "flying trait")
    eq(unit(st, 50).mutation, 1, "mutation from the save")
    eq(st.attack_order_all[1], 50, "attack_order_all: Vek first")
    eq(st.attack_order_all[3], 60, "attack_order_all: train last")
    local by = {}
    for _, tl in ipairs(st.tiles) do by[tl.x .. "," .. tl.y] = tl end
    eq(by["6,6"].ice_hp, 1, "cracked ice hp")
    eq(by["0,7"].custom_tile, "conveyor1.png", "custom tile")
    eq(by["0,0"].populated, true, "populated building")
    eq(by["1,0"].populated, false, "unpopulated building")
    eq(by["7,0"].terrain, "lava", "lava tile")
end

-- The second mech fires its limited weapon: the save stays, live uses drop.
MOCK.data(mech1).shots = 1
MOCK.data(mech1).active = false
X._dump_state()
st = load_state()
eq(unit(st, 1).weapon_slots[1].uses, 1, "limited uses after a shot")

---------------------------------------------------------------- hooks
do
    MOCK.hook_calls = {}
    local r1 = Mission.ApplyEnvironmentEffect(M)
    local r2 = Mission.ApplyEnvironmentEffect(M)
    eq(r1, true, "env step 1 result passed through")
    eq(r2, false, "env step 2 result passed through")
    eq(#MOCK.hook_calls, 2, "original ApplyEnvironmentEffect called once per step")
    X._dump_state()
    st = load_state()
    eq(#st.env_strike_log, 2, "two env steps logged")
    eq(st.env_strike_log[1].current_attack.x, 5, "first strike (5,2)")
    eq(st.env_strike_log[2].current_attack.x, 1, "second strike (1,1)")
    eq(st.env_strike_log[1].returned, true, "step 1 returned true")

    -- Debug captures around the enemy phase.
    write_file(X.DEBUG_FLAG_FILE, "1")
    X._debug_at = nil
    MOCK.team = 6
    MOCK.hook_calls = {}
    Mission.BaseNextTurn(M)
    eq(MOCK.hook_calls[1], "BaseNextTurn", "original BaseNextTurn ran")
    check(read_file(X.PRE_SPAWN_FILE) ~= nil, "pre-spawn capture written")
    local ret = Mission.PlanEnvironment(M)
    eq(ret, "plan-result", "PlanEnvironment result passed through")
    check(read_file(X.POST_SPAWN_FILE) ~= nil, "post-spawn capture written")
    local pre = load_state(X.PRE_SPAWN_FILE)
    eq(pre.phase, "combat_enemy", "pre-spawn capture in the enemy phase")
    os.remove(X.POST_SPAWN_FILE)
    Mission.PlanEnvironment(M)
    eq(read_file(X.POST_SPAWN_FILE), nil, "only the first PlanEnvironment is captured")
    MOCK.team = 1

    -- Per-frame log: HP change and a selected shooter.
    _ITB_BRIDGE_PHASE_LOG = nil
    Mission.BaseUpdate(M)
    MOCK.data(vek_a).hp = 2
    MOCK.data(vek_b).selected = true
    Mission.BaseUpdate(M)
    local log = _ITB_BRIDGE_PHASE_LOG
    local kinds = {}
    for _, e in ipairs(log.entries) do kinds[e.kind] = (kinds[e.kind] or 0) + 1 end
    eq(kinds.hp, 1, "hp change logged")
    eq(kinds.selected, 1, "shooter selection logged")
    MOCK.data(vek_b).selected = false
    os.remove(X.DEBUG_FLAG_FILE)
    X._debug_at = nil
end

---------------------------------------------------------------- commands
local function run_command(cmd, max_frames)
    os.remove(DIR .. "/itb_ack.txt")
    write_file(DIR .. "/itb_cmd.txt", "#7 " .. cmd)
    for _ = 1, (max_frames or 200) do
        CLOCK = CLOCK + 1
        Mission.BaseUpdate(M)
        local ack = read_file(DIR .. "/itb_ack.txt")
        if ack and read_file(DIR .. "/itb_cmd.txt") == nil then
            -- The coroutine may still be running if the ack came early;
            -- run frames until it is done.
            for _ = 1, 20 do
                CLOCK = CLOCK + 1
                Mission.BaseUpdate(M)
            end
            return ack
        end
    end
    return nil
end

do
    local ack = run_command("SNAPSHOT probe one")
    eq(ack, "#7 OK SNAPSHOT " .. X.SNAPSHOT_PREFIX .. "probe.json", "SNAPSHOT ack")
    check(read_file(X.SNAPSHOT_PREFIX .. "probe.json") ~= nil, "snapshot file")

    ack = run_command("SCENARIO {\"name\": \"x\"}")
    check(ack and string.find(ack, "ERROR: SCENARIO disabled", 1, true) ~= nil, "SCENARIO needs the debug flag")

    -- Old command path unchanged.
    MOCK.data(mech0).active = true
    ack = run_command("SKIP 0")
    eq(ack, "#7 OK SKIP 0", "SKIP ack")
    eq(MOCK.data(mech0).active, false, "SKIP deactivates")
    MOCK.data(mech0).active = true

    write_file(X.DEBUG_FLAG_FILE, "1")
    X._debug_at = nil
    ack = run_command("DEBUG_STATUS")
    check(ack and string.find(ack, '"debug":true', 1, true) ~= nil, "DEBUG_STATUS")

    local scenario = [[{
      "name": "vek order",
      "clear_pawns": "all",
      "clear_spawns": true,
      "tiles": [
        {"x": 4, "y": 1, "terrain": "building", "hp": 1, "populated": true},
        {"x": 2, "y": 6, "fire": true},
        {"x": 3, "y": 6, "smoke": true, "acid": true},
        {"x": 0, "y": 4, "terrain": "water"},
        {"x": 5, "y": 6, "terrain": "ice", "hp": 1}
      ],
      "pawns": [
        {"uid": 0, "x": 4, "y": 2, "hp": 2, "shield": true},
        {"type": "Firefly1", "team": 6, "x": 4, "y": 5, "fire": true, "queue": {"x": 4, "y": 4}},
        {"type": "Scorpion1", "team": 6, "x": 5, "y": 2, "acid": true, "queue": {"x": 4, "y": 2}},
        {"type": "Firefly1", "team": 6, "x": 1, "y": 2, "frozen": true}
      ],
      "spawns": [{"type": "Scorpion1", "x": 6, "y": 6}]
    }]]
    write_file(DIR .. "/scenario.json", scenario)
    MOCK.calls = {}
    MOCK.busy_after_mutation = 3
    ack = run_command("SCENARIO @" .. DIR .. "/scenario.json", 400)
    check(ack ~= nil, "SCENARIO acked")
    ack = ack or ""
    check(string.find(ack, "#7 OK SCENARIO ", 1, true) == 1, "SCENARIO ok: " .. ack)
    local report = X.json_decode(string.sub(ack, string.len("#7 OK SCENARIO ") + 1))
    eq(#report.errors, 0, "SCENARIO errors (" .. tostring(report.errors[1]) .. ")")
    eq(#report.created, 3, "three pawns created")
    eq(#MOCK.mismatches, 0, "strict-call mismatches during SCENARIO (" .. tostring(MOCK.mismatches[1]) .. ")")

    -- The board.
    eq(MOCK.find_pawn(50), nil, "old Vek removed")
    eq(MOCK.find_pawn(60), nil, "train removed (clear_pawns all)")
    check(MOCK.find_pawn(1) ~= nil, "mechs kept")
    local d0 = MOCK.data(mech0)
    eq(d0.x * 10 + d0.y, 42, "mech moved to (4,2)")
    eq(d0.hp, 2, "mech hp")
    eq(d0.shield, true, "mech shield")
    eq(MOCK.tiles[4][1].terrain, TERRAIN_BUILDING, "building placed")
    eq(MOCK.tiles[2][6].fire, true, "tile fire")
    eq(MOCK.tiles[0][4].terrain, TERRAIN_WATER, "water")
    eq(MOCK.tiles[5][6].hp, 1, "cracked ice")
    local ff = MOCK.pawn_at(Point(4, 5))
    check(ff ~= nil and MOCK.data(ff).fire == true, "burning Firefly")
    eq(MOCK.tiles[4][5].fire, false, "its tile does not burn")
    local fz = MOCK.pawn_at(Point(1, 2))
    check(fz ~= nil and MOCK.data(fz).frozen == true, "frozen Firefly")
    eq(#MOCK.spawns, 1, "old spawns cleared, one queued")
    eq(MOCK.spawns[1].x, 6, "queued spawn")

    -- The dump that follows is the engine's input.
    st = load_state()
    eq(#st.bridge_errors, 0, "bridge_errors after SCENARIO")
    local created = report.created
    local u1 = unit(st, created[1].uid)
    eq(u1.has_queued_attack, true, "scenario queue overlay")
    eq(u1.queued_target[2], 4, "scenario queued target")
    eq(u1.queued_source, "scenario", "queued source")
    eq(st.attack_order[1], created[1].uid, "attack order = creation order (1)")
    eq(st.attack_order[2], created[2].uid, "attack order = creation order (2)")
    eq(#st.attack_order, 2, "frozen pawn has no queued attack")
    eq(st.spawn_queue_source, "scenario", "spawn queue from the scenario")
    eq(#st.spawn_queue, 1, "spawn queue length")
    eq(st.spawn_queue[1].type, "Scorpion1", "spawn type")
    eq(st.spawn_queue_matches_markers, true, "scenario queue matches markers")
    eq(st.scenario.name, "vek order", "scenario echo")
    check(st.phase_log ~= nil, "phase log exported with the debug flag")
    check(read_file(X.SNAPSHOT_PREFIX .. "scenario_vek_order.json") ~= nil, "scenario snapshot file")

    ack = run_command("PHASE_LOG")
    check(ack and string.find(ack, "OK PHASE_LOG", 1, true) ~= nil, "PHASE_LOG ack")
    check(read_file(X.PHASE_LOG_FILE) ~= nil, "phase log file")
    ack = run_command("SCENARIO_RESET")
    eq(ack, "#7 OK SCENARIO_RESET", "SCENARIO_RESET")
    eq(_ITB_BRIDGE_SCENARIO, nil, "scenario ledger cleared")

    ack = run_command("SCENARIO {\"pawns\": [{\"type\": \"Firefly1\", \"x\": 4, \"y\": 2}]}")
    check(ack and string.find(ack, "OK SCENARIO", 1, true) ~= nil, "SCENARIO inline JSON")
    report = X.json_decode(string.sub(ack or "", string.len("#7 OK SCENARIO ") + 1))
    check(report.errors and string.find(report.errors[1] or "", "occupied", 1, true) ~= nil,
          "placing on an occupied tile is reported")
    ack = run_command("SCENARIO {bad json")
    check(ack and string.find(ack, "ERROR: SCENARIO payload", 1, true) ~= nil, "bad JSON rejected")
    MOCK.team = 6
    ack = run_command("SCENARIO {}")
    check(ack and string.find(ack, "not the player turn", 1, true) ~= nil, "SCENARIO only in the player turn")
    MOCK.team = 1
    os.remove(X.DEBUG_FLAG_FILE)
end

---------------------------------------------------------------- live findings
-- moved flag, MOVE_NATIVE, FIRE, re-added pawns, weapons_add, injured,
-- tiles_after, the drop zone, saveData vs undoSave, powered weapons, tile
-- changes in the phase log.
do
    write_file(X.DEBUG_FLAG_FILE, "1")
    X._debug_at = nil
    MOCK.team = 1
    MOCK.data(mech0).active = true
    MOCK.data(mech1).active = true
    Mission.BaseNextTurn(M)  -- the player's turn begins: positions recorded
    local ack = run_command("MOVE_NATIVE 0 4 3")
    check(ack and string.find(ack, "[FireWeapon[0]] at 4,3", 1, true) ~= nil, "MOVE_NATIVE through the Move skill: " .. tostring(ack))
    eq(MOCK.fired[#MOCK.fired].slot, 0, "MOVE_NATIVE fires slot 0")
    MOCK.data(mech1).active = false
    ack = run_command("MOVE_NATIVE 1 3 4")
    check(ack and string.find(ack, "[Move] at 3,4", 1, true) ~= nil, "MOVE_NATIVE falls back to Pawn:Move: " .. tostring(ack))
    st = load_state()
    eq(unit(st, 0).moved, true, "moved after MOVE_NATIVE")
    eq(unit(st, 0).moved_source, "turn_start", "moved from the turn-start positions")
    eq(unit(st, 1).moved, true, "moved by position")
    MOCK.data(mech1).x, MOCK.data(mech1).y = 3, 3
    st = load_state((function() X._dump_state() return nil end)())
    eq(unit(st, 1).moved, false, "back on its turn-start tile and no undo: not moved")

    ack = run_command("FIRE 1 1 3 5")
    check(ack and string.find(ack, "OK FIRE 1 slot=1 at 3,5 ret=1", 1, true) ~= nil, "FIRE: " .. tostring(ack))

    local spec = [[{"name": "readd", "clear_pawns": "all",
      "pawns": [
        {"type": "Firefly1", "team": 6, "x": 6, "y": 1, "queue": {"x": 6, "y": 2}},
        {"type": "Scorpion1", "team": 6, "x": 6, "y": 4, "queue": {"x": 6, "y": 5}},
        {"ref": 1, "readd": true},
        {"type": "PunchMech", "team": 1, "x": 0, "y": 5, "weapons_add": ["Ranged_Limited"], "injured": true}],
      "tiles_after": [{"x": 0, "y": 5, "fire": true}]}]]
    ack = run_command("SCENARIO " .. spec, 400) or ""
    check(string.find(ack, "OK SCENARIO", 1, true) ~= nil, "SCENARIO readd: " .. ack)
    local report = X.json_decode(string.sub(ack, string.len("#7 OK SCENARIO ") + 1))
    eq(#report.errors, 0, "readd scenario errors (" .. tostring(report.errors[1]) .. ")")
    st = load_state()
    eq(st.attack_order[1], report.created[2].uid, "re-added pawn attacks last (1)")
    eq(st.attack_order[2], report.created[1].uid, "re-added pawn attacks last (2)")
    local helper = MOCK.find_pawn(report.created[3].uid)
    eq(MOCK.data(helper).added[1], "Ranged_Limited", "weapons_add")
    eq(MOCK.data(helper).injured, true, "injured via iInjure")
    eq(MOCK.tiles[0][5].fire, true, "tiles_after")

    -- Drop zone during deployment (turn 0).
    MOCK.turn = 0
    X._dump_state()
    st = load_state()
    eq(st.deploying, true, "deploying at turn 0")
    eq(st.drop_zone_source, "zone+columns", "two zone tiles: whole columns added")
    check(#st.drop_zone > 3, "drop zone has more than 3 tiles")
    MOCK.zones.deployment = {}
    X._dump_state()
    st = load_state()
    eq(st.drop_zone_source, "default", "no zone: default columns 1-3")
    check(st.deployment_zone ~= nil and #st.deployment_zone > 0, "deployment_zone filled from the drop zone")
    for _, p in ipairs(st.drop_zone) do
        check(p[1] >= 1 and p[1] <= 3 and p[2] >= 1 and p[2] <= 6, "default drop zone tile in x 1-3, y 1-6")
    end
    MOCK.turn = 1

    -- undoSave.lua holding a later turn wins; powered weapons.
    Prime_Punchmech_A = {Damage = 2}
    Passive_Electric.PowerCost = 1
    Ranged_Limited.PowerCost = 1
    local undo = read_file(save_dir .. "/saveData.lua")
    undo = string.gsub(undo, '%["iCurrentTurn"%] = 1', '["iCurrentTurn"] = 2', 1)
    undo = string.gsub(undo, '%["primary_mod1"%] = {0, 0, }, %["primary_mod2"%] = {1, 1, 1, }',
                       '["primary_mod1"] = {1, 1, }, ["primary_mod2"] = {0, 0, 0, }', 1)
    write_file(save_dir .. "/undoSave.lua", undo)
    X._dump_state()
    st = load_state()
    eq(st.save_source, "undoSave.lua", "the later save is used")
    eq(unit(st, 0).weapons_exact[1], "Prime_Punchmech_A", "upgrade from undoSave")
    eq(unit(st, 0).weapon_slots[2].powered, true, "powered passive (1 core, cost 1)")
    eq(unit(st, 1).weapon_slots[1].powered, false, "unpowered weapon (0 cores, cost 1)")
    os.remove(save_dir .. "/undoSave.lua")

    -- Tile changes in the phase log.
    Mission.BaseUpdate(M)
    MOCK.tiles[0][0].hp = 0
    MOCK.tiles[0][0].terrain = TERRAIN_RUBBLE
    Mission.BaseUpdate(M)
    local found = false
    for _, e in ipairs(_ITB_BRIDGE_PHASE_LOG.entries) do
        if e.kind == "tile" and e.x == 0 and e.y == 0 then found = true end
    end
    check(found, "building damage logged per frame")
    os.remove(X.DEBUG_FLAG_FILE)
    X._debug_at = nil
end

eq(#MOCK.mismatches, 0, "strict-call mismatches overall")

if #failures > 0 then
    error(#failures .. " of " .. checks .. " bridge checks failed:\n  " .. table.concat(failures, "\n  "), 0)
end
print("bridge harness: " .. checks .. " checks passed")
return checks
