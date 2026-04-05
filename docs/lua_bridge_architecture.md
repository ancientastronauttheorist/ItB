# Lua Bridge Architecture: Into the Breach <-> Python Bot

## Overview

Replace the current two-layer indirection (save-file parsing + MCP mouse clicks) with
a direct Lua<->Python bridge using file-based IPC through `/tmp/`. The game's
`modloader.lua` writes JSON state dumps and reads command files; the Python bot reads
state and writes commands. No mouse clicks, no coordinate calibration, no window focus
issues.

```
Current:   Game -> saveData.lua -> save_parser.py -> solver -> executor.py -> MCP clicks -> Game
Proposed:  Game -> /tmp/itb_state.json -> bridge_reader.py -> solver -> bridge_writer.py -> /tmp/itb_cmd.txt -> Game
```

---

## 1. Communication Protocol

### 1.1 File Locations

| File | Writer | Reader | Format | Purpose |
|------|--------|--------|--------|---------|
| `/tmp/itb_state.json` | Lua | Python | JSON | Full board state dump |
| `/tmp/itb_cmd.txt` | Python | Lua | Line-based text | Bot commands |
| `/tmp/itb_ack.txt` | Lua | Python | Line-based text | Command acknowledgement |
| `/tmp/itb_bridge.log` | Lua | Human | Plain text | Debug log |

### 1.2 Synchronization Protocol

The protocol is request-response with the game polling for commands:

```
GAME (Lua)                              BOT (Python)
    |                                       |
    |-- write state.json ------------------>|
    |                                       |-- read state.json
    |                                       |-- run solver
    |                                       |-- write cmd.txt
    |<-- poll for cmd.txt (every 200ms) ----|
    |-- read cmd.txt                        |
    |-- delete cmd.txt                      |
    |-- execute command                     |
    |-- write ack.txt (result)              |
    |                                       |-- poll for ack.txt (every 100ms)
    |-- write state.json (updated) -------->|-- read ack.txt
    |                                       |-- delete ack.txt
    |                                       |-- (next command or done)
```

**Key design decisions:**

1. **Reader deletes.** The consumer of each file deletes it after reading. This
   prevents stale data and doubles as an implicit "consumed" signal. Lua deletes
   `cmd.txt` after reading; Python deletes `ack.txt` after reading.

2. **Atomic writes.** Both sides write to a `.tmp` suffix first, then rename.
   This prevents the reader from seeing a half-written file. Lua: `os.rename`.
   Python: `os.replace`.

3. **Polling interval.** Lua polls for `cmd.txt` every 200ms (5 checks/second).
   The game runs at 60fps, so a 200ms poll in `Mission:BaseUpdate()` fires every
   ~12 frames -- negligible CPU overhead. Python polls for `ack.txt` every 100ms.

4. **Timeout.** Both sides time out after 30 seconds of no response. On timeout,
   Lua logs an error and resumes normal game operation (player can still click
   manually). Python raises an exception that the session handler catches.

5. **State dumps are unprompted.** The game writes `state.json` whenever a
   significant event occurs (turn start, action complete, deployment start). The
   bot does NOT request state -- it just reads whatever the game last wrote.

### 1.3 Bridge Lifecycle

```
1. Game starts -> modloader.lua loads -> bridge initializes
2. Bridge writes /tmp/itb_bridge_ready (empty file) -> Python detects game is ready
3. Player turn starts -> Lua writes state.json
4. Python reads state, solves, writes first command
5. Lua reads command, executes, writes ack + updated state
6. Python reads ack, writes next command
7. ... repeat until all mechs acted ...
8. Python writes END_TURN command
9. Lua ends turn, waits for next player turn
10. Back to step 3
```

---

## 2. State Serialization (Lua -> JSON)

### 2.1 JSON Structure

The state dump mirrors the existing `Board` + `Unit` + `BoardTile` dataclasses
exactly, so the Python side can construct a `Board` directly from JSON without
translation:

```json
{
  "version": 1,
  "timestamp": 1712345678,
  "phase": "combat_player",
  "turn": 2,
  "grid_power": 5,
  "grid_power_max": 7,
  "mission_name": "Mission4",
  "map_name": "any1",
  "victory_turns": 2,

  "tiles": [
    {"x": 0, "y": 0, "terrain": "mountain", "terrain_id": 3},
    {"x": 0, "y": 2, "terrain": "building", "terrain_id": 1,
     "building_hp": 1, "population": 49, "on_fire": false},
    {"x": 1, "y": 3, "terrain": "forest", "terrain_id": 6},
    ...
  ],

  "units": [
    {
      "uid": 100, "type": "PunchMech", "team": 1, "is_mech": true,
      "x": 3, "y": 2, "hp": 3, "max_hp": 3,
      "move_speed": 3, "flying": false, "massive": true,
      "armor": false, "pushable": true,
      "weapon": "Prime_Punchmech", "weapon2": "",
      "active": true,
      "target_x": -1, "target_y": -1,
      "pilot_name": "Ralph Karlsson", "pilot_id": "Pilot_Original"
    },
    {
      "uid": 200, "type": "Firefly1", "team": 6, "is_mech": false,
      "x": 5, "y": 4, "hp": 3, "max_hp": 3,
      "move_speed": 2, "flying": false, "massive": false,
      "armor": false, "pushable": true,
      "weapon": "FireflyAtk1", "weapon2": "",
      "active": true,
      "target_x": 3, "target_y": 4
    },
    ...
  ],

  "spawn_points": [[7, 4], [5, 5]],
  "spawns": ["Jelly_Armor1", "Firefly1"],

  "objectives": [
    {"text": "Protect the Grid", "category": 0, "value": 0, "potential": 1},
    {"text": "Kill 2 enemies", "category": 1, "value": 1, "potential": 2}
  ],

  "deployment_zones": [[2, 3], [3, 3], [4, 3], [2, 4], [3, 4]],

  "environment": {
    "rain": 3,
    "rain_type": 0,
    "air_strike_tiles": [],
    "conveyor_tiles": [],
    "lightning_tiles": []
  }
}
```

**Design note on tiles array:** Only non-default tiles are included (same as save file).
Any tile not listed is assumed to be plain ground with no occupant or status. This keeps
the JSON compact (~2-4KB per dump instead of 64 entries).

### 2.2 JSON Builder in Lua (No Library Required)

Lua has no built-in JSON encoder. Rather than depending on a third-party library
(which would require additional files in the game directory), we build a minimal
JSON encoder in ~60 lines of Lua:

```lua
-- Minimal JSON encoder (handles string, number, boolean, nil, table)
local function json_encode(val, indent, depth)
    indent = indent or "  "
    depth = depth or 0
    local pad = string.rep(indent, depth)
    local pad1 = string.rep(indent, depth + 1)

    if val == nil then
        return "null"
    elseif type(val) == "boolean" then
        return val and "true" or "false"
    elseif type(val) == "number" then
        return tostring(val)
    elseif type(val) == "string" then
        -- Escape special chars
        local escaped = val:gsub('\\', '\\\\'):gsub('"', '\\"')
            :gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
        return '"' .. escaped .. '"'
    elseif type(val) == "table" then
        -- Detect array vs object: array if sequential integer keys from 1
        local is_array = true
        local max_i = 0
        for k, _ in pairs(val) do
            if type(k) ~= "number" or k ~= math.floor(k) or k < 1 then
                is_array = false
                break
            end
            if k > max_i then max_i = k end
        end
        if max_i == 0 and next(val) ~= nil then is_array = false end

        local parts = {}
        if is_array then
            for i = 1, max_i do
                parts[#parts + 1] = pad1 .. json_encode(val[i], indent, depth + 1)
            end
            return "[\n" .. table.concat(parts, ",\n") .. "\n" .. pad .. "]"
        else
            for k, v in pairs(val) do
                local key = type(k) == "string" and k or tostring(k)
                parts[#parts + 1] = pad1 .. '"' .. key .. '": '
                    .. json_encode(v, indent, depth + 1)
            end
            return "{\n" .. table.concat(parts, ",\n") .. "\n" .. pad .. "}"
        end
    end
    return "null"
end
```

This is embedded directly in `modloader.lua`. No external dependencies.

### 2.3 When State is Dumped

| Event | Trigger | Phase Value |
|-------|---------|-------------|
| Player turn starts | `NextTurn()` hook fires with `team == 1` | `"combat_player"` |
| After each mech action completes | Command ACK | `"combat_player"` |
| Deployment phase starts | Mission load hook | `"deployment"` |
| After deployment confirms | Deployment complete | `"combat_player"` |
| Mission ends | `iState` changes from 0 | `"mission_ending"` |
| Between missions | Map screen detected | `"between_missions"` |

### 2.4 State Extraction from Lua API

The game's Lua API provides direct access to everything the save parser currently
extracts (and more). Here is the mapping:

```lua
-- Board object (global during combat)
Board                           -- the 8x8 game board
Board:GetSize()                 -- returns Point(8, 8)
Board:GetTerrain(Point(x,y))    -- returns terrain int (0-9)
Board:IsFire(Point(x,y))        -- returns bool
Board:IsSmoke(Point(x,y))       -- returns bool
Board:IsAcid(Point(x,y))        -- returns bool
Board:IsFrozen(Point(x,y))      -- returns bool
Board:IsPod(Point(x,y))         -- returns bool
Board:GetHealth(Point(x,y))     -- building/mountain HP
Board:IsDangerous(Point(x,y))   -- danger tile for spawns
Board:IsBlocked(Point(x,y), PATH_GROUND) -- movement query

-- Pawn access
Board:GetPawn(Point(x,y))       -- returns pawn at tile, or nil
GetPawn(id)                     -- returns pawn by numeric ID

-- Pawn properties (given a pawn object p)
p:GetId()                       -- numeric ID
p:GetType()                     -- string type name
p:GetSpace()                    -- returns Point(x, y)
p:GetHealth()                   -- current HP
p:GetMaxHealth()                -- max HP
p:GetTeam()                     -- 1=player, 6=enemy
p:IsMech()                      -- bool
p:IsFlying()                    -- bool
p:IsFrozen()                    -- bool
p:IsShield()                    -- bool
p:IsAcid()                      -- bool
p:IsFire()                      -- bool
p:GetWeaponCount()              -- number of weapons
p:GetPoweredWeaponCount()       -- powered weapons
p:GetMoveSpeed()                -- movement range

-- Game-level
GetGame()                       -- game state object
GetGame():GetTurnCount()        -- current turn number
GetGame():GetTeamTurn()         -- whose turn (1=player, 6=enemy)
Game:GetPower()                 -- current grid power  (via GetGame())
-- NOTE: grid_power_max not directly queryable; read from save once

-- Pawn iteration (no GetAllPawns, so iterate the board)
-- Loop over all 64 tiles and check Board:GetPawn(Point(x,y))
-- Also iterate through known pawn IDs (0-999) via GetPawn(id)
```

**Important API gaps the Lua bridge must handle:**

- **No `GetAllPawns()`.** Must iterate board tiles or known IDs. Tile iteration
  is reliable and only 64 checks.
- **No direct attack intent query.** Enemy targets (`piQueuedShot`) are stored in
  save data but NOT exposed through the Lua pawn API. Two options:
  1. Read `piQueuedShot` from the save file (hybrid approach -- save parser for
     intents only, Lua for everything else).
  2. Parse the pawn's internal table via `_G` table traversal (fragile).
  3. Read the queued attack from the save file at turn start and include it in
     the state dump. The save file is always up-to-date at turn boundaries.
  **Decision: Option 3.** At the start of each player turn, the save file has just
  been written with current enemy intents. We read `piQueuedShot` from the save
  for enemy target data, and use the Lua API for everything else. This is the same
  hybrid the current system uses (save_parser), but with Lua for the reliable parts.

### 2.5 Complete State Dump Function

```lua
function dump_game_state()
    local state = {}
    state.version = 1
    state.timestamp = os.time()
    state.turn = GetGame():GetTurnCount()
    state.phase = get_current_phase()  -- see section 4
    state.grid_power = Game:GetPower()
    state.grid_power_max = GRID_POWER_MAX  -- cached from save at run start

    -- Tiles (only non-default)
    state.tiles = {}
    for x = 0, 7 do
        for y = 0, 7 do
            local p = Point(x, y)
            local terrain = Board:GetTerrain(p)
            if terrain ~= 0  -- not plain ground
               or Board:IsFire(p) or Board:IsSmoke(p)
               or Board:IsAcid(p) or Board:IsFrozen(p)
               or Board:IsPod(p)
            then
                local tile = {x = x, y = y, terrain_id = terrain}
                tile.terrain = TERRAIN_NAMES[terrain]  -- lookup table
                if terrain == 1 then  -- building
                    tile.building_hp = Board:GetHealth(p)
                    -- Population: not queryable via API, set to 1 if populated
                    tile.population = (Board:GetHealth(p) > 0) and 1 or 0
                end
                if terrain == 3 then  -- mountain
                    tile.building_hp = Board:GetHealth(p)
                end
                tile.on_fire = Board:IsFire(p) or false
                tile.smoke = Board:IsSmoke(p) or false
                tile.acid = Board:IsAcid(p) or false
                tile.frozen = Board:IsFrozen(p) or false
                tile.has_pod = Board:IsPod(p) or false
                state.tiles[#state.tiles + 1] = tile
            end
        end
    end

    -- Units (iterate board + check for off-board pawns via known IDs)
    state.units = {}
    local seen = {}
    for x = 0, 7 do
        for y = 0, 7 do
            local pawn = Board:GetPawn(Point(x, y))
            if pawn and not seen[pawn:GetId()] then
                seen[pawn:GetId()] = true
                state.units[#state.units + 1] = serialize_pawn(pawn)
            end
        end
    end

    -- Spawn points (from save data, cached at turn start)
    state.spawn_points = CACHED_SPAWN_POINTS
    state.spawns = CACHED_SPAWN_TYPES

    -- Objectives (from save data, cached)
    state.objectives = CACHED_OBJECTIVES

    -- Write to file
    write_json("/tmp/itb_state.json", state)
end

function serialize_pawn(pawn)
    local pos = pawn:GetSpace()
    local u = {
        uid = pawn:GetId(),
        type = pawn:GetType(),
        team = pawn:GetTeam(),
        is_mech = pawn:IsMech(),
        x = pos.x,
        y = pos.y,
        hp = pawn:GetHealth(),
        max_hp = pawn:GetMaxHealth(),
        move_speed = pawn:GetMoveSpeed(),
        flying = pawn:IsFlying(),
        massive = pawn:IsMech(),  -- all player mechs are massive
        armor = false,  -- not directly queryable; use type lookup
        pushable = true,
        weapon = "",
        weapon2 = "",
        active = true,  -- updated from save data / tracking
    }

    -- Weapon names from save data (not queryable via pawn API)
    -- Cached at turn start from save parser
    local pawn_cache = PAWN_EXTRA[pawn:GetId()]
    if pawn_cache then
        u.weapon = pawn_cache.primary or ""
        u.weapon2 = pawn_cache.secondary or ""
        u.active = pawn_cache.active
        u.target_x = pawn_cache.target_x or -1
        u.target_y = pawn_cache.target_y or -1
        u.armor = pawn_cache.armor or false
    end

    return u
end
```

### 2.6 Hybrid Data Source Strategy

Not everything is available from the Lua API. Here is the authoritative source
for each data element:

| Data | Source | Reason |
|------|--------|--------|
| Tile terrain | Lua API `Board:GetTerrain()` | Real-time, always current |
| Tile fire/smoke/acid/frozen | Lua API `Board:IsFire()` etc. | Real-time |
| Tile building HP | Lua API `Board:GetHealth()` | Real-time |
| Unit position | Lua API `pawn:GetSpace()` | Real-time |
| Unit HP | Lua API `pawn:GetHealth()` | Real-time |
| Unit team | Lua API `pawn:GetTeam()` | Real-time |
| Unit move speed | Lua API `pawn:GetMoveSpeed()` | Real-time |
| Unit flying | Lua API `pawn:IsFlying()` | Real-time |
| Unit weapon names | **Save file** | Not in pawn API |
| Unit active (bActive) | **Save file** | Not in pawn API |
| Enemy attack targets | **Save file** (piQueuedShot) | Not in pawn API |
| Spawn points | **Save file** (spawn_points) | Not in pawn API |
| Objectives | **Save file** | Not in pawn API |
| Grid power max | **Save file** (once at run start) | Not in game API |
| Unit armor/pushable | **Type lookup table** | Static per type |

**Implementation:** At the start of each player turn, the bridge reads both the Lua
API (for real-time tile/unit data) AND the save file (for weapon names, intents,
active status, spawns). The save file read uses the same `io.open` + pattern matching
that we already confirmed works from `modloader.lua`.

---

## 3. Command Execution (Python -> Lua)

### 3.1 Command File Format

One command per file. Plain text, one line:

```
MOVE 100 3 4
ATTACK 100 1 5 4
END_TURN
DEPLOY 100 3 3
UNDO
REPAIR 100
WAIT
```

Format: `COMMAND_TYPE [pawn_id] [arg1] [arg2] [arg3]`

### 3.2 Command Definitions

| Command | Args | Description |
|---------|------|-------------|
| `MOVE <uid> <x> <y>` | pawn_id, dest_x, dest_y | Move pawn to tile |
| `ATTACK <uid> <weapon_idx> <x> <y>` | pawn_id, 1 or 2, target_x, target_y | Fire weapon at target |
| `MOVE_ATTACK <uid> <mx> <my> <widx> <tx> <ty>` | Combined move+attack | Atomic move-then-attack |
| `END_TURN` | (none) | End the player turn |
| `DEPLOY <uid> <x> <y>` | pawn_id, tile_x, tile_y | Place mech during deployment |
| `UNDO` | (none) | Undo last action |
| `REPAIR <uid>` | pawn_id | Repair instead of attacking |
| `WAIT` | (none) | No-op, used for synchronization |

### 3.3 Execution via Lua API

Each command maps to specific Lua API calls:

```lua
-- Command dispatch table
local COMMANDS = {}

COMMANDS.MOVE = function(args)
    local uid, x, y = args[1], args[2], args[3]
    local pawn = GetPawn(uid)
    if not pawn then return false, "pawn not found: " .. uid end

    local dest = Point(x, y)

    -- Validate: is the tile reachable?
    -- The game tracks valid moves internally; we trust the solver
    -- but wrap in pcall for safety
    local ok, err = pcall(function()
        pawn:Move(dest)
    end)
    if not ok then return false, "move failed: " .. tostring(err) end
    return true, "moved " .. uid .. " to " .. x .. "," .. y
end

COMMANDS.ATTACK = function(args)
    local uid, weapon_idx, tx, ty = args[1], args[2], args[3], args[4]
    local pawn = GetPawn(uid)
    if not pawn then return false, "pawn not found: " .. uid end

    -- FireWeapon triggers the weapon effect including damage, push, status
    local ok, err = pcall(function()
        pawn:FireWeapon(Point(tx, ty), weapon_idx)
    end)
    if not ok then return false, "attack failed: " .. tostring(err) end
    return true, "fired weapon " .. weapon_idx .. " at " .. tx .. "," .. ty
end

COMMANDS.MOVE_ATTACK = function(args)
    local uid, mx, my, widx, tx, ty = args[1], args[2], args[3],
                                       args[4], args[5], args[6]
    local pawn = GetPawn(uid)
    if not pawn then return false, "pawn not found: " .. uid end

    -- Move first, then attack
    local ok, err = pcall(function()
        pawn:Move(Point(mx, my))
    end)
    if not ok then return false, "move failed: " .. tostring(err) end

    -- Small delay for animation (game needs a frame to update)
    -- The polling loop handles this naturally

    ok, err = pcall(function()
        pawn:FireWeapon(Point(tx, ty), widx)
    end)
    if not ok then return false, "attack failed: " .. tostring(err) end
    return true, "moved+attacked"
end

COMMANDS.END_TURN = function(args)
    -- Trigger end turn through the game's internal function
    local ok, err = pcall(function()
        -- The game's internal end-turn call
        GetGame():EndTurn()
    end)
    if not ok then return false, "end_turn failed: " .. tostring(err) end
    return true, "turn ended"
end

COMMANDS.REPAIR = function(args)
    local uid = args[1]
    local pawn = GetPawn(uid)
    if not pawn then return false, "pawn not found: " .. uid end
    local ok, err = pcall(function()
        pawn:Repair()  -- heals 1 HP, removes fire and acid
    end)
    if not ok then return false, "repair failed: " .. tostring(err) end
    return true, "repaired " .. uid
end

COMMANDS.UNDO = function(args)
    local ok, err = pcall(function()
        -- Undo last mech action
        Board:UndoMove()
    end)
    if not ok then return false, "undo failed: " .. tostring(err) end
    return true, "undone"
end
```

### 3.4 Acknowledgement Format

After executing a command, Lua writes `/tmp/itb_ack.txt`:

```
OK moved 100 to 3,4
```
or
```
ERROR pawn not found: 999
```

Format: `STATUS message`

Where STATUS is `OK` or `ERROR`. The Python side reads this, then deletes the file.

### 3.5 Animation Handling

When the Lua API executes a move or attack, the game plays animations. The bridge
must wait for animations to complete before the bot can issue the next command.
Strategy:

1. After `pawn:Move()`, the game animates the movement over ~0.5-1.0 seconds.
2. After `pawn:FireWeapon()`, attack animations take ~1.0-2.0 seconds.
3. The bridge does NOT write the next state dump until animations complete.
4. Detection: poll `Board:IsBusy()` (if available) or use a fixed delay based on
   action type.
5. Fallback: if no busy-check API exists, use conservative delays:
   - MOVE: wait 1.0 second after execution
   - ATTACK: wait 2.0 seconds after execution
   - END_TURN: wait 6.0 seconds (enemy phase animations)

The delay happens in the Lua polling loop AFTER writing the ACK, BEFORE writing
the next state dump. This ensures the Python side doesn't try to read stale
positions during animation.

---

## 4. Game Event Hooks

### 4.1 Hook Strategy

Without the mod loader's event registration system, we use function overrides.
The approach: save original functions, replace with wrappers that call our code
then call the original.

**Primary hook: `Mission.BaseUpdate()`**

This function is called every frame during a mission. We add a polling check:

```lua
-- Save the original
local _original_BaseUpdate = Mission.BaseUpdate

function Mission:BaseUpdate()
    -- Call original game logic first
    _original_BaseUpdate(self)

    -- Bridge polling (every N frames to avoid performance hit)
    bridge_frame_counter = (bridge_frame_counter or 0) + 1
    if bridge_frame_counter >= 12 then  -- ~200ms at 60fps
        bridge_frame_counter = 0
        bridge_poll()
    end
end
```

**Secondary hook: `Mission.NextTurn()`**

Fires when a new turn starts (after enemy phase resolves):

```lua
local _original_NextTurn = Mission.NextTurn

function Mission:NextTurn()
    _original_NextTurn(self)

    -- Detect player turn start
    if GetGame():GetTeamTurn() == TEAM_PLAYER then
        bridge_on_player_turn()
    end
end
```

### 4.2 Turn Transition Detection

```lua
local TEAM_PLAYER = 1
local TEAM_ENEMY = 6
local bridge_active = false
local bridge_waiting_for_command = false

function bridge_on_player_turn()
    -- Read save file for data not in Lua API (intents, weapons, spawns)
    cache_save_data()

    -- Dump full state
    dump_game_state()

    -- Enter command-waiting mode
    bridge_waiting_for_command = true
    bridge_active = true
end

function bridge_poll()
    if not bridge_active then return end
    if not bridge_waiting_for_command then return end

    -- Check for command file
    local f = io.open("/tmp/itb_cmd.txt", "r")
    if f then
        local line = f:read("*line")
        f:close()
        os.remove("/tmp/itb_cmd.txt")

        if line then
            local ok, msg = execute_command(line)
            write_ack(ok, msg)

            -- If the command was END_TURN, stop polling until next player turn
            if line:match("^END_TURN") then
                bridge_waiting_for_command = false
            else
                -- Wait for animation, then dump updated state
                bridge_schedule_state_dump()
            end
        end
    end
end
```

### 4.3 Phase Detection in Lua

```lua
function get_current_phase()
    -- Check if we're in a mission
    if not Board then return "no_mission" end

    local game = GetGame()
    if not game then return "no_game" end

    -- Check battle state (mirrors save_parser logic)
    -- iState is not directly queryable, but we can infer from context
    local team = game:GetTeamTurn()
    if team == TEAM_PLAYER then
        return "combat_player"
    elseif team == TEAM_ENEMY then
        return "combat_enemy"
    end

    return "unknown"
end
```

---

## 5. Deployment Phase

### 5.1 Reading Deployment Zones

During the deployment phase (before the first turn of each mission), the game
shows valid placement zones. These are available through:

```lua
-- Deployment zone tiles (green highlighted area)
-- Not directly queryable via API; must be read from save file
-- save_parser already extracts these from map_data.zones
-- For the bridge: read from save file's "zones" field at mission start

function get_deployment_zones()
    -- Read from save file (zones field in map_data)
    -- The save file is written before deployment starts
    local zones = read_save_zones()
    return zones
end
```

### 5.2 Programmatic Mech Placement

```lua
COMMANDS.DEPLOY = function(args)
    local uid, x, y = args[1], args[2], args[3]
    local pawn = GetPawn(uid)
    if not pawn then return false, "pawn not found: " .. uid end

    local ok, err = pcall(function()
        -- SetSpace teleports the pawn to the tile (works during deployment)
        pawn:SetSpace(Point(x, y))
    end)
    if not ok then return false, "deploy failed: " .. tostring(err) end
    return true, "deployed " .. uid .. " to " .. x .. "," .. y
end
```

### 5.3 Deployment Protocol

```
1. Mission loads -> Lua detects deployment phase
2. Lua dumps state with phase="deployment" and deployment_zones=[...]
3. Python reads zones, chooses positions, writes DEPLOY commands (one per mech)
4. Lua executes each DEPLOY, ACKs
5. After all 3 mechs deployed, Python writes CONFIRM_DEPLOY
6. Lua triggers deployment confirmation (clicks Start or calls internal function)
7. Turn 1 begins normally
```

---

## 6. Integration with Existing Python Code

### 6.1 New Module: `src/bridge/`

```
src/bridge/
    __init__.py
    reader.py       # Read /tmp/itb_state.json -> Board
    writer.py       # Write /tmp/itb_cmd.txt from solver actions
    protocol.py     # Sync protocol (wait for ack, timeout handling)
    bridge_board.py # Board.from_bridge_json() constructor
```

### 6.2 Bridge Reader (`reader.py`)

Replaces `save_parser.py` when in bridge mode:

```python
"""Read game state from Lua bridge JSON file."""

import json
import time
from pathlib import Path
from src.model.board import Board, Unit, BoardTile

BRIDGE_STATE = Path("/tmp/itb_state.json")
BRIDGE_ACK = Path("/tmp/itb_ack.txt")
BRIDGE_READY = Path("/tmp/itb_bridge_ready")

TERRAIN_NAMES = {
    0: "ground", 1: "building", 2: "rubble", 3: "mountain",
    4: "water", 5: "lava", 6: "forest", 7: "sand", 8: "ice", 9: "chasm",
}


def is_bridge_available() -> bool:
    """Check if the Lua bridge is active."""
    return BRIDGE_READY.exists()


def read_bridge_state() -> dict | None:
    """Read the latest state dump from the bridge.

    Returns parsed JSON dict, or None if no state available.
    """
    if not BRIDGE_STATE.exists():
        return None
    try:
        data = json.loads(BRIDGE_STATE.read_text())
        return data
    except (json.JSONDecodeError, OSError):
        return None


def board_from_bridge(data: dict) -> Board:
    """Construct a Board from bridge JSON data.

    Mirrors Board.from_mission() but reads from JSON dict
    instead of MissionState dataclass.
    """
    board = Board()
    board.grid_power = data.get("grid_power", 0)
    board.grid_power_max = data.get("grid_power_max", 7)

    # Tiles
    for td in data.get("tiles", []):
        x, y = td["x"], td["y"]
        if 0 <= x < 8 and 0 <= y < 8:
            bt = board.tile(x, y)
            bt.terrain = td.get("terrain", "ground")
            bt.on_fire = td.get("on_fire", False)
            bt.smoke = td.get("smoke", False)
            bt.acid = td.get("acid", False)
            bt.frozen = td.get("frozen", False)
            bt.has_pod = td.get("has_pod", False)
            if bt.terrain == "building":
                bt.building_hp = td.get("building_hp", 1)
                bt.population = td.get("population", 0)

    # Units
    for ud in data.get("units", []):
        u = Unit(
            uid=ud["uid"],
            type=ud["type"],
            x=ud["x"],
            y=ud["y"],
            hp=ud["hp"],
            max_hp=ud["max_hp"],
            team=ud["team"],
            is_mech=ud["is_mech"],
            move_speed=ud.get("move_speed", 3),
            flying=ud.get("flying", False),
            massive=ud.get("massive", False),
            armor=ud.get("armor", False),
            pushable=ud.get("pushable", True),
            weapon=ud.get("weapon", ""),
            weapon2=ud.get("weapon2", ""),
            active=ud.get("active", True),
            target_x=ud.get("target_x", -1),
            target_y=ud.get("target_y", -1),
        )
        board.units.append(u)

    return board
```

### 6.3 Bridge Writer (`writer.py`)

Replaces `executor.py` when in bridge mode:

```python
"""Write commands to the Lua bridge."""

import os
import time
from pathlib import Path
from src.solver.solver import MechAction

BRIDGE_CMD = Path("/tmp/itb_cmd.txt")
BRIDGE_ACK = Path("/tmp/itb_ack.txt")
BRIDGE_CMD_TMP = Path("/tmp/itb_cmd.txt.tmp")

ACK_POLL_INTERVAL = 0.1  # seconds
ACK_TIMEOUT = 30.0       # seconds


def send_command(cmd: str) -> tuple[bool, str]:
    """Write a command and wait for acknowledgement.

    Returns (success, message).
    """
    # Atomic write
    BRIDGE_CMD_TMP.write_text(cmd + "\n")
    os.replace(str(BRIDGE_CMD_TMP), str(BRIDGE_CMD))

    # Wait for ACK
    deadline = time.time() + ACK_TIMEOUT
    while time.time() < deadline:
        if BRIDGE_ACK.exists():
            try:
                ack = BRIDGE_ACK.read_text().strip()
                os.remove(str(BRIDGE_ACK))
                if ack.startswith("OK"):
                    return True, ack[3:]
                else:
                    return False, ack[6:] if ack.startswith("ERROR") else ack
            except OSError:
                pass
        time.sleep(ACK_POLL_INTERVAL)

    return False, "timeout waiting for ACK"


def execute_mech_action(action: MechAction) -> tuple[bool, str]:
    """Convert a solver MechAction to a bridge command and execute it."""
    has_move = action.move_to and action.move_to != (-1, -1)
    has_attack = action.weapon and action.target[0] >= 0

    if has_move and has_attack:
        # Combined move + attack
        cmd = (f"MOVE_ATTACK {action.mech_uid} "
               f"{action.move_to[0]} {action.move_to[1]} "
               f"1 "  # weapon index (1=primary, 2=secondary)
               f"{action.target[0]} {action.target[1]}")
        return send_command(cmd)

    if has_move:
        cmd = f"MOVE {action.mech_uid} {action.move_to[0]} {action.move_to[1]}"
        return send_command(cmd)

    if has_attack:
        cmd = (f"ATTACK {action.mech_uid} 1 "
               f"{action.target[0]} {action.target[1]}")
        return send_command(cmd)

    return True, "no action needed"


def end_turn() -> tuple[bool, str]:
    """Send END_TURN command."""
    return send_command("END_TURN")
```

### 6.4 Updated `game_loop.py` Commands

The CLI gains a `--bridge` flag (or auto-detects bridge availability):

```python
def cmd_read(profile="Alpha"):
    """Parse state -- uses bridge if available, falls back to save file."""
    if is_bridge_available():
        data = read_bridge_state()
        if data:
            board = board_from_bridge(data)
            phase = data["phase"]
            # ... same display logic as current cmd_read ...
            return {"phase": phase, "source": "bridge", ...}

    # Fall back to save file parsing
    return _cmd_read_save(profile)
```

The `cmd_execute` path changes most dramatically. Instead of returning a click
plan for Claude to execute via MCP, it directly sends the command through the
bridge:

```python
def cmd_execute(action_index, profile="Alpha"):
    """Execute a mech action through the bridge (or plan clicks if no bridge)."""
    session = _load_session()
    action = session.get_action(action_index)

    if is_bridge_available():
        ok, msg = execute_mech_action(action)
        if ok:
            session.mark_action_executed()
            session.save()
            return {"status": "OK", "message": msg, "source": "bridge"}
        else:
            return {"status": "ERROR", "message": msg, "source": "bridge"}

    # Fall back to MCP click planning
    return _cmd_execute_clicks(action_index, profile)
```

### 6.5 What Stays the Same

These components are completely unchanged:

- **`src/solver/`** -- The solver operates on `Board` objects regardless of how
  they were constructed (save parser or bridge JSON).
- **`src/model/board.py`** -- Board dataclass is the same.
- **`src/model/weapons.py`** -- Weapon definitions are static.
- **`src/loop/session.py`** -- Session management is transport-agnostic.
- **`src/solver/evaluate.py`** -- Evaluation function unchanged.
- **`src/solver/simulate.py`** -- Simulation unchanged.

### 6.6 What Gets Replaced

| Component | Current (MCP) | Bridge Mode |
|-----------|---------------|-------------|
| State reading | `save_parser.py` | `bridge/reader.py` |
| Action execution | `executor.py` -> MCP clicks | `bridge/writer.py` -> file IPC |
| Verification | `cmd_verify` (re-parse save) | Read ACK + fresh state dump |
| Coordinate system | `grid_to_mcp()`, `detect_grid` | Not needed |
| Window detection | `capture/window.py`, `detect_grid.py` | Not needed |
| MCP tool calls | Claude computer-use | Not needed |

---

## 7. Error Recovery

### 7.1 Lua-Side Error Handling

Every game API call is wrapped in `pcall()`:

```lua
function safe_execute(func, ...)
    local ok, result = pcall(func, ...)
    if not ok then
        bridge_log("ERROR: " .. tostring(result))
        return false, tostring(result)
    end
    return true, result
end
```

### 7.2 Bridge Health Check

The Python side can detect bridge problems:

| Symptom | Cause | Recovery |
|---------|-------|----------|
| No `bridge_ready` file | Game not running or mod not loaded | Wait or start game |
| `state.json` not updating | Lua bridge crashed or hook detached | Restart game |
| ACK timeout (30s) | Command execution hung | Send UNDO, re-read state, retry |
| ACK = ERROR | Invalid command | Log error, re-solve, try different action |
| State shows unexpected phase | Turn changed unexpectedly | Re-read, detect new phase |

### 7.3 Graceful Degradation

If the bridge fails mid-turn, the bot can fall back to MCP mode for that turn:

```python
def cmd_execute(action_index, profile="Alpha"):
    if is_bridge_available():
        ok, msg = execute_mech_action(action)
        if ok:
            return {"status": "OK", "source": "bridge"}
        else:
            print(f"Bridge failed: {msg}. Falling back to MCP clicks.")
            # Fall through to MCP click planning

    return _cmd_execute_clicks(action_index, profile)
```

### 7.4 Mod File Safety

The bridge modifies only one file in the game directory: `modloader.lua` in the
game's `scripts/` folder. To ensure safe recovery:

1. **Backup before patching:** Copy original `modloader.lua` to `modloader.lua.bak`
   before writing bridge code.
2. **Restore script:** A `restore_modloader.sh` script replaces `modloader.lua`
   with the backup. Run this if the game crashes on load.
3. **Empty modloader is safe:** The vanilla `modloader.lua` is an empty file. If
   anything goes wrong, replacing it with an empty file restores the game to
   vanilla behavior.
4. **Bridge code is self-contained:** All bridge logic lives in `modloader.lua`.
   No other game files are modified.

```bash
#!/bin/bash
# restore_modloader.sh -- Reset modloader.lua to vanilla (empty)
GAME_DIR="$HOME/Library/Application Support/Steam/steamapps/common/Into the Breach/Into the Breach.app/Contents/Resources/scripts"
echo "" > "$GAME_DIR/modloader.lua"
echo "modloader.lua restored to empty (vanilla)"
```

---

## 8. Phased Implementation Plan

### Phase 1: State Dump Only (Read-Only Bridge)

**Goal:** Verify that Lua can dump state and Python can read it. No commands.
Compare bridge state against save parser output to validate correctness.

**Deliverables:**
1. `modloader.lua` with:
   - JSON encoder
   - `dump_game_state()` function
   - `Mission.NextTurn()` hook that dumps state at player turn start
   - Save file reader for supplemental data (weapons, intents, spawns)
2. `src/bridge/reader.py` with:
   - `read_bridge_state()` -> dict
   - `board_from_bridge()` -> Board
3. Validation script that runs both paths and diffs the Board objects
4. `restore_modloader.sh` backup script

**Validation criteria:**
- Bridge Board matches save-parser Board on all fields for 10+ turns
- Tile terrain matches 100%
- Unit positions, HP, team match 100%
- Enemy intents match 100%
- Performance: state dump completes in <50ms

**Estimated effort:** 2-3 sessions

### Phase 2: Command Execution (Move + Attack + End Turn)

**Goal:** Execute solver solutions through the bridge instead of MCP clicks.

**Deliverables:**
1. `modloader.lua` additions:
   - Command parser and dispatch table
   - `Mission.BaseUpdate()` polling hook
   - ACK writer
   - Animation delay handling
2. `src/bridge/writer.py` with:
   - `send_command()` with ACK polling
   - `execute_mech_action()` converting MechAction to command strings
   - `end_turn()`
3. `src/bridge/protocol.py` with timeout/retry logic
4. Updated `cmd_execute` and `cmd_end_turn` to use bridge when available

**Validation criteria:**
- Complete a full turn (3 mech actions + end turn) through bridge
- Verify each action produces correct board state (compare against simulation)
- Handle animation delays correctly (no stale state reads)
- Measure latency: target <500ms per action (vs ~5s per action with MCP)

**Estimated effort:** 2-3 sessions

### Phase 3: Deployment Phase + Full Mission Cycle

**Goal:** Handle deployment, mission transitions, and between-mission navigation.

**Deliverables:**
1. Deployment zone reading and mech placement commands
2. Mission start/end detection hooks
3. Map navigation commands (or detection that map navigation still needs MCP)
4. Updated `game_loop.py` for full bridge-mode game loop

**Validation criteria:**
- Complete a full mission (deployment + 4-5 combat turns + mission end)
- Handle mission transitions cleanly
- No manual intervention needed during combat

**Estimated effort:** 1-2 sessions

### Phase 4: Remove MCP Dependency

**Goal:** The bot plays entirely through the Lua bridge. MCP is not needed.

**Deliverables:**
1. Map/shop/island navigation through bridge (or minimal MCP fallback)
2. Full achievement run test (one complete game from menu to victory/defeat)
3. Performance optimization (batch state dumps, minimize file I/O)
4. Updated CLAUDE.md with bridge-mode protocols

**What still needs MCP (probably):**
- Main menu navigation (start new run, select squad)
- Shop interactions (buy weapons/cores)
- Map navigation (select next mission)
- Reward selection screens

These screens have no in-game Lua hooks and no save-file representation during
the transition. The bot may need a hybrid approach: bridge for combat, MCP for
menu/shop/map navigation.

**Estimated effort:** 2-3 sessions

---

## 9. Performance Comparison

| Metric | Current (MCP) | Bridge Mode | Improvement |
|--------|---------------|-------------|-------------|
| State read latency | ~500ms (parse save file) | ~50ms (read JSON) | 10x |
| Action execution | ~5s (click + animation + verify) | ~2s (command + animation) | 2.5x |
| Full turn (3 mechs) | ~20s | ~8s | 2.5x |
| Verification | ~3s (retry polling) | ~100ms (ACK) | 30x |
| Failure rate | ~10% (missed clicks, focus loss) | ~0% (direct API) | Eliminated |
| Coordinate calibration | Required every session | Not needed | Eliminated |
| Window focus management | Required (game must be frontmost) | Not needed | Eliminated |

---

## 10. Complete `modloader.lua` Skeleton

```lua
--[[
    Into the Breach Lua Bridge
    Loaded by scripts.lua as the last file in the game's Lua environment.
    Communicates with external Python bot via /tmp/ file IPC.
]]

-- ============================================================
-- Configuration
-- ============================================================
local BRIDGE_DIR = "/tmp"
local STATE_FILE = BRIDGE_DIR .. "/itb_state.json"
local CMD_FILE   = BRIDGE_DIR .. "/itb_cmd.txt"
local ACK_FILE   = BRIDGE_DIR .. "/itb_ack.txt"
local READY_FILE = BRIDGE_DIR .. "/itb_bridge_ready"
local LOG_FILE   = BRIDGE_DIR .. "/itb_bridge.log"
local POLL_FRAMES = 12  -- poll every 12 frames (~200ms at 60fps)

local TEAM_PLAYER = 1
local TEAM_ENEMY  = 6

local TERRAIN_NAMES = {
    [0] = "ground", [1] = "building", [2] = "rubble", [3] = "mountain",
    [4] = "water", [5] = "lava", [6] = "forest", [7] = "sand",
    [8] = "ice", [9] = "chasm",
}

-- ============================================================
-- State
-- ============================================================
local bridge_active = false
local bridge_waiting = false
local frame_counter = 0
local CACHED_SPAWN_POINTS = {}
local CACHED_SPAWN_TYPES = {}
local CACHED_OBJECTIVES = {}
local PAWN_EXTRA = {}  -- supplemental data from save file
local GRID_POWER_MAX = 7

-- ============================================================
-- JSON Encoder (embedded, no dependencies)
-- ============================================================
-- [json_encode function as shown in section 2.2]

-- ============================================================
-- File I/O Helpers
-- ============================================================
local function write_file(path, content)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "w")
    if not f then return false end
    f:write(content)
    f:close()
    os.rename(tmp, path)
    return true
end

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local content = f:read("*all")
    f:close()
    return content
end

local function file_exists(path)
    local f = io.open(path, "r")
    if f then f:close() return true end
    return false
end

local function bridge_log(msg)
    local f = io.open(LOG_FILE, "a")
    if f then
        f:write(os.date("[%H:%M:%S] ") .. msg .. "\n")
        f:close()
    end
end

-- ============================================================
-- Save File Reader (for supplemental data)
-- ============================================================
local function cache_save_data()
    -- Read the save file for data not in Lua API
    -- (weapons, active status, enemy intents, spawns)
    -- This is a simplified pattern-matching reader, not a full parser
    -- [Implementation reads specific fields via string patterns]
    bridge_log("Cached supplemental data from save file")
end

-- ============================================================
-- State Serialization
-- ============================================================
-- [dump_game_state() and serialize_pawn() as shown in section 2.5]

-- ============================================================
-- Command Execution
-- ============================================================
-- [COMMANDS table and dispatch as shown in section 3.3]

local function execute_command(line)
    local parts = {}
    for word in line:gmatch("%S+") do
        parts[#parts + 1] = word
    end
    local cmd_name = parts[1]
    local args = {}
    for i = 2, #parts do
        args[#args + 1] = tonumber(parts[i]) or parts[i]
    end

    local handler = COMMANDS[cmd_name]
    if not handler then
        return false, "unknown command: " .. cmd_name
    end
    return handler(args)
end

local function write_ack(ok, msg)
    local status = ok and "OK" or "ERROR"
    write_file(ACK_FILE, status .. " " .. (msg or "") .. "\n")
end

-- ============================================================
-- Polling Loop
-- ============================================================
local function bridge_poll()
    if not bridge_active or not bridge_waiting then return end

    if file_exists(CMD_FILE) then
        local content = read_file(CMD_FILE)
        os.remove(CMD_FILE)

        if content then
            local line = content:match("([^\n]+)")
            if line then
                bridge_log("CMD: " .. line)
                local ok, msg = execute_command(line)
                write_ack(ok, msg)
                bridge_log("ACK: " .. (ok and "OK" or "ERROR") .. " " .. (msg or ""))

                if line:match("^END_TURN") then
                    bridge_waiting = false
                else
                    -- Dump updated state after short delay for animation
                    -- (handled by next poll cycle naturally)
                    dump_game_state()
                end
            end
        end
    end
end

-- ============================================================
-- Game Hooks
-- ============================================================
local function bridge_on_player_turn()
    cache_save_data()
    dump_game_state()
    bridge_waiting = true
    bridge_log("Player turn " .. GetGame():GetTurnCount() .. " -- waiting for commands")
end

-- Hook Mission.BaseUpdate for frame-based polling
if Mission and Mission.BaseUpdate then
    local _orig_BaseUpdate = Mission.BaseUpdate
    function Mission:BaseUpdate()
        _orig_BaseUpdate(self)
        frame_counter = frame_counter + 1
        if frame_counter >= POLL_FRAMES then
            frame_counter = 0
            bridge_poll()
        end
    end
end

-- Hook NextTurn for turn transition detection
if Mission and Mission.NextTurn then
    local _orig_NextTurn = Mission.NextTurn
    function Mission:NextTurn()
        _orig_NextTurn(self)
        if GetGame():GetTeamTurn() == TEAM_PLAYER then
            bridge_on_player_turn()
        end
    end
end

-- ============================================================
-- Initialization
-- ============================================================
local function bridge_init()
    -- Clean up stale files from previous session
    os.remove(STATE_FILE)
    os.remove(CMD_FILE)
    os.remove(ACK_FILE)

    -- Signal that bridge is ready
    write_file(READY_FILE, "ready\n")
    bridge_active = true
    bridge_log("Bridge initialized")
end

bridge_init()
```

---

## 11. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `pawn:Move()` or `pawn:FireWeapon()` don't exist or behave differently | Medium | High | Test each API call in isolation first. Have MCP fallback. |
| Save file not written at hook time (race condition) | Low | Medium | Add 200ms delay before reading save in `cache_save_data()`. |
| `Mission.BaseUpdate` hook causes frame drops | Low | Low | 200ms poll interval = 5 file checks/second, negligible. |
| Game update breaks Lua API | Low | High | Pin game version. `modloader.lua.bak` for instant rollback. |
| `os.execute` / `io.open` permissions blocked on macOS | Very Low | High | Already confirmed working. Gatekeeper does not block these. |
| JSON encoding bugs (special chars, nested tables) | Medium | Low | Extensive test with complex board states. |
| Animation timing too short (stale state read) | Medium | Medium | Conservative delays + verify state changed before proceeding. |
| `piQueuedShot` not in save at expected time | Low | High | Validate at phase 1. Fall back to save-parser-only if needed. |

---

## 12. Open Questions (Resolve During Phase 1)

1. **Does `pawn:FireWeapon(target, index)` exist?** The API surface needs
   verification. Alternative: `Board:AddEffect(SpaceDamage(...))` to simulate
   weapon effects manually.

2. **Does `GetGame():EndTurn()` exist?** If not, we may need to simulate an
   end-turn click or find the internal function name.

3. **Is `Mission.BaseUpdate` the right hook point?** It might be `Mission:BaseUpdate`
   (method vs function). Test both syntaxes.

4. **Does the save file update immediately on `pawn:Move()`?** If yes, we can
   read supplemental data after each command instead of only at turn start.

5. **Can we read the deployment zone from Lua?** If `Board:IsDeploymentZone(p)`
   or similar exists, we don't need the save file for this.

6. **What happens if we call `pawn:Move()` to an invalid tile?** Does it silently
   fail, throw an error, or crash? Must test in pcall.
