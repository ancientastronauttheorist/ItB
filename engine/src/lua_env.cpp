#include "lua_env.hpp"

#include <algorithm>
#include <regex>
#include <stdexcept>

#include "lua_host_detail.hpp"

extern "C" {
#include "lauxlib.h"
#include "lua.h"
#include "lualib.h"
}

namespace itb::detail {
namespace {

// Native values (constants, Point, SpaceDamage, ...) come from the Lua host's
// value bindings (lua_host_values.cpp); this prelude adds an inert "sink"
// that stands in for the remaining native objects/functions while loading.
constexpr const char* kPrelude = R"lua(
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
  lua::install_value_bindings(L_);
  check(L_, luaL_dostring(L_, kPrelude), "prelude");
  for (const std::string& name : stubs) {
    lua_getglobal(L_, "ITB_SINK");
    lua_setglobal(L_, name.c_str());
  }
}

std::unique_ptr<LuaEnv> LuaEnv::load_game_scripts(const std::filesystem::path& game_root,
                                                  ScriptRun* run, const Binder& bind) {
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
    if (bind) bind(L);
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
