#include "lua_env.hpp"

#include <algorithm>
#include <regex>
#include <stdexcept>

extern "C" {
#include "lauxlib.h"
#include "lua.h"
#include "lualib.h"
}

namespace itb::detail {
namespace {

// Constants the game binds into Lua natively (ActiveLua::BindDefinitions,
// Linux build 21601364), plus the DIR_* values confirmed from DIR_VECTORS.
constexpr const char* kNativeConstants = R"lua(
DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT, DIR_NONE, DIR_FLIP = 0, 1, 2, 3, 4, 6
TEAM_PLAYER, TEAM_NONE, TEAM_ANY, TEAM_MECH, TEAM_ENEMY, TEAM_BOTS, TEAM_ENEMY_MAJOR = 1, 2, 2, 4, 6, 8, -1
FACTION_DEFAULT, FACTION_BOTS, FACTION_TOTAL = 0, 1, 2
TERRAIN_ROAD, TERRAIN_BUILDING, TERRAIN_RUBBLE, TERRAIN_WATER, TERRAIN_MOUNTAIN = 0, 1, 2, 3, 4
TERRAIN_ICE, TERRAIN_FOREST, TERRAIN_SAND, TERRAIN_HOLE = 5, 6, 7, 9
TERRAIN_FIRE, TERRAIN_ACID, TERRAIN_LAVA = 11, 12, 14
PATH_GROUND, PATH_FLYER, PATH_MASSIVE, PATH_PROJECTILE, PATH_ROADRUNNER = 0, 1, 2, 3, 4
PATH_BURROWER, PATH_PHASING = 7, 9
LEADER_NONE, LEADER_HEALTH, LEADER_VINES, LEADER_REGEN, LEADER_ARMOR = 0, 1, 2, 4, 5
LEADER_EXPLODE, LEADER_BOSS, LEADER_TENTACLE, LEADER_SPIDER, LEADER_FIRE = 6, 7, 8, 9, 10
LEADER_BOOSTED, LEADER_NECRO = 11, 12
TIER_NORMAL, TIER_ALPHA, TIER_BOSS = 0, 1, 2
DAMAGE_ZERO, DAMAGE_DEATH = 500, 1000
NO_DELAY, FULL_DELAY, PROJ_DELAY = 0, -1, -2
ENV_EFFECT = -10
EFFECT_NONE, EFFECT_CREATE, EFFECT_REMOVE = 0, 1, 2
IMPACT_NULL, IMPACT_METAL, IMPACT_ROCK, IMPACT_FLESH, IMPACT_INSECT = 0, 1, 2, 3, 4
IMPACT_BLOB, IMPACT_SHIELD, IMPACT_WATER = 5, 6, 7
POPULATED_FALSE, POPULATED_TRUE = 0, 1
ZONE_NONE, ZONE_DIR, ZONE_ALL, ZONE_CUSTOM = 0, 1, 2, 3
BLOCKED_NONE, BLOCKED_TEMP, BLOCKED_PERM = 0, 1, 2
CRACK_LAVA, CRACK_TENTACLE = 0, 1
DIFF_EASY, DIFF_NORMAL, DIFF_HARD, DIFF_UNFAIR = 0, 1, 2, 3
DIFF_MOD_NONE, DIFF_MOD_EASY, DIFF_MOD_HARD = 0, 1, 2
LAYER_SKY, LAYER_FRONT, LAYER_BACK, LAYER_FLOOR, LAYER_LESS_BACK = 0, 1, 2, 3, 4
RAIN_NORMAL, RAIN_ACID, RAIN_SNOW = 0, 1, 2
FADE_OUT, FADE_EXPLODE = 1, 2
QUEST_OBJECTIVES, QUEST_MECH, QUEST_BUILDINGS, QUEST_REPUTATION, QUEST_POWER = 0, 1, 2, 3, 4
NAME_NORMAL, NAME_FIRST, NAME_SECOND, NAME_REVERSE = 0, 2, 3, 4
FONT_MODE_NORMAL, FONT_MODE_LARGE, FONT_MODE_PHONE = 0, 1, 2
PAWN_ID_MECH, PAWN_ID_CEO, PAWN_ID_ARCHIVE, PAWN_ID_RST, PAWN_ID_PINNACLE = 1000, 2000, 2001, 2002, 2003
SQUAD_ARCHIVE_A, SQUAD_RUST_A, SQUAD_PINNACLE_A, SQUAD_DETRITUS_A = 0, 1, 2, 3
SQUAD_ARCHIVE_B, SQUAD_RUST_B, SQUAD_PINNACLE_B, SQUAD_DETRITUS_B = 4, 5, 6, 7
SECRET_SQUAD = 10
ADVANCED_SQUAD_1, ADVANCED_SQUAD_2, ADVANCED_SQUAD_3, ADVANCED_SQUAD_4 = 11, 12, 13, 14
ADVANCED_SQUAD_5, ADVANCED_SQUAD_6, ADVANCED_SQUAD_7 = 15, 16, 17
SEX_MALE, SEX_FEMALE, SEX_NEUTRAL = 0, 1, 2
)lua";

// A working Point (the scripts do arithmetic on points while loading) and an
// inert "sink" that stands in for native objects/functions.
constexpr const char* kPrelude = R"lua(
local PointMT = {}
PointMT.__index = PointMT
function Point(x, y) return setmetatable({x = x or 0, y = y or 0}, PointMT) end
local function both_points(a, b)
  return getmetatable(a) == PointMT and getmetatable(b) == PointMT
end
-- Point +/- non-Point has unknown native semantics; it only occurs in UI
-- layout code, so it yields the inert stub instead of a guess.
PointMT.__add = function(a, b)
  if not both_points(a, b) then return ITB_SINK end
  return Point(a.x + b.x, a.y + b.y)
end
PointMT.__sub = function(a, b)
  if not both_points(a, b) then return ITB_SINK end
  return Point(a.x - b.x, a.y - b.y)
end
PointMT.__unm = function(a) return Point(-a.x, -a.y) end
PointMT.__mul = function(a, b)
  if type(a) == "number" then a, b = b, a end
  return Point(a.x * b, a.y * b)
end
PointMT.__eq = function(a, b) return a.x == b.x and a.y == b.y end
PointMT.__tostring = function(p) return "Point(" .. tostring(p.x) .. ", " .. tostring(p.y) .. ")" end
function PointMT:GetString() return tostring(self) end
function PointMT:Length() return math.sqrt(self.x * self.x + self.y * self.y) end
function PointMT:Manhattan() return math.abs(self.x) + math.abs(self.y) end
VEC_UP, VEC_RIGHT, VEC_DOWN, VEC_LEFT = Point(0, -1), Point(1, 0), Point(0, 1), Point(-1, 0)
VEC_RIGHT_UP, VEC_RIGHT_DOWN = Point(1, -1), Point(1, 1)
VEC_LEFT_DOWN, VEC_LEFT_UP = Point(-1, 1), Point(-1, -1)

ITB_SINK = {}
local SinkMT = {}
local function sink() return ITB_SINK end
SinkMT.__index = sink
SinkMT.__call = sink
SinkMT.__newindex = function() end
for _, m in ipairs({"__add", "__sub", "__mul", "__div", "__mod", "__pow", "__unm", "__concat"}) do
  SinkMT[m] = sink
end
SinkMT.__tostring = function() return "" end
setmetatable(ITB_SINK, SinkMT)

-- Native queries whose results the scripts do arithmetic on while loading.
function ScreenSizeX() return 1280 end
function ScreenSizeY() return 720 end
function GetBoardScale() return 1 end
function GetDefaultScale() return 1 end
function Rect2D(x, y, w, h) return {x = x or 0, y = y or 0, w = w or 0, h = h or 0} end
)lua";

void check(lua_State* L, int status, const char* what) {
  if (status != 0) {
    std::string msg = lua_tostring(L, -1) ? lua_tostring(L, -1) : "unknown error";
    lua_pop(L, 1);
    throw std::runtime_error(std::string(what) + ": " + msg);
  }
}

// The list of script paths from scripts/scripts.lua's GetScripts().
std::vector<std::string> script_list(const std::filesystem::path& game_root) {
  lua_State* L = luaL_newstate();
  luaL_openlibs(L);
  const auto path = (game_root / "scripts" / "scripts.lua").string();
  std::vector<std::string> files;
  try {
    check(L, luaL_dofile(L, path.c_str()), "loading scripts.lua");
    lua_getglobal(L, "GetScripts");
    check(L, lua_pcall(L, 0, 1, 0), "calling GetScripts");
    const int n = static_cast<int>(lua_objlen(L, -1));
    for (int i = 1; i <= n; ++i) {
      lua_rawgeti(L, -1, i);
      if (const char* s = lua_tostring(L, -1)) files.emplace_back(s);
      lua_pop(L, 1);
    }
  } catch (...) {
    lua_close(L);
    throw;
  }
  lua_close(L);
  // Player save data and the mod loader are not part of the game's rules.
  std::erase_if(files, [](const std::string& f) {
    return f.rfind("user/", 0) == 0 || f.find("modloader.lua") != std::string::npos;
  });
  return files;
}

}  // namespace

LuaEnv::LuaEnv() : L_(luaL_newstate()) {
  if (!L_) throw std::runtime_error("luaL_newstate failed");
  luaL_openlibs(L_);
}

LuaEnv::~LuaEnv() {
  if (L_) lua_close(L_);
}

void LuaEnv::install_prelude(const std::vector<std::string>& stubs) {
  check(L_, luaL_dostring(L_, kNativeConstants), "native constants");
  check(L_, luaL_dostring(L_, kPrelude), "prelude");
  for (const std::string& name : stubs) {
    lua_getglobal(L_, "ITB_SINK");
    lua_setglobal(L_, name.c_str());
  }
}

std::unique_ptr<LuaEnv> LuaEnv::load_game_scripts(const std::filesystem::path& game_root,
                                                  ScriptRun* run) {
  const std::vector<std::string> files = script_list(game_root);
  static const std::regex missing_global(R"(attempt to (?:call|index) global '([A-Za-z_][A-Za-z_0-9]*)')");

  std::vector<std::string> stubs;
  ScriptRun result;
  std::unique_ptr<LuaEnv> env;
  constexpr int kMaxPasses = 300;
  for (int pass = 1; pass <= kMaxPasses; ++pass) {
    env = std::make_unique<LuaEnv>();
    env->install_prelude(stubs);
    lua_State* L = env->L();
    // Scripts locate their own files with dofile(GetWorkingDir() .. path).
    const std::string root = game_root.string() + "/";
    lua_pushstring(L, root.c_str());
    lua_pushcclosure(L, [](lua_State* S) {
      lua_pushvalue(S, lua_upvalueindex(1));
      return 1;
    }, 1);
    lua_setglobal(L, "GetWorkingDir");

    result = ScriptRun{};
    result.passes = pass;
    bool added = false;
    for (const std::string& file : files) {
      const std::string full = root + file;
      if (luaL_loadfile(L, full.c_str()) != 0 || lua_pcall(L, 0, 0, 0) != 0) {
        std::string msg = lua_tostring(L, -1) ? lua_tostring(L, -1) : "unknown error";
        lua_pop(L, 1);
        // Learn one stub per pass, from the first missing-name failure: later
        // files may fail on names an earlier missing-name abort would have
        // defined. Stubs the scripts later overwrite are reported, since those
        // names were not native after all.
        std::smatch m;
        if (!added && std::regex_search(msg, m, missing_global) &&
            std::find(stubs.begin(), stubs.end(), m[1].str()) == stubs.end()) {
          stubs.push_back(m[1].str());
          added = true;
        }
        result.errors.push_back(file + ": " + msg);
      } else {
        ++result.files_ok;
      }
    }
    if (!added) break;
  }
  result.stubbed_globals = stubs;
  lua_State* L = env->L();
  lua_getglobal(L, "ITB_SINK");
  for (const std::string& name : stubs) {
    lua_getglobal(L, name.c_str());
    if (!lua_rawequal(L, -1, -2)) result.overwritten_stubs.push_back(name);
    lua_pop(L, 1);
  }
  lua_pop(L, 1);
  if (run) *run = result;
  return env;
}

}  // namespace itb::detail
