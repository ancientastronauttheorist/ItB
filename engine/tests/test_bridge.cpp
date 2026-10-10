// The Lua bridge (src/bridge/modloader.lua) checked outside the game, in the
// game's Lua version: it must compile, and tests/bridge/bridge_harness.lua
// runs it against a strict mock of the game API (see that file).
#include <doctest/doctest.h>

#include "itb/game_data.hpp"

#include <unistd.h>

#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "itb/recording.hpp"

extern "C" {
#include <lauxlib.h>
#include <lua.h>
#include <lualib.h>
}

namespace fs = std::filesystem;

namespace {

const fs::path kRepo = ITB_REPO_ROOT;
const fs::path kModloader = kRepo / "src" / "bridge" / "modloader.lua";
const fs::path kHarness = kRepo / "engine" / "tests" / "bridge" / "bridge_harness.lua";
const fs::path kMock = kRepo / "engine" / "tests" / "bridge" / "game_mock.lua";

struct LuaState {
  lua_State* L = luaL_newstate();
  LuaState() { luaL_openlibs(L); }
  ~LuaState() { lua_close(L); }
  std::string error() const {
    const char* msg = lua_tostring(L, -1);
    return msg ? msg : "(no message)";
  }
};

void set_global(lua_State* L, const char* name, const std::string& value) {
  lua_pushstring(L, value.c_str());
  lua_setglobal(L, name);
}

}  // namespace

TEST_CASE("bridge: modloader.lua compiles in Lua 5.1") {
  LuaState lua;
  const int rc = luaL_loadfile(lua.L, kModloader.string().c_str());
  INFO(lua.error());
  CHECK(rc == 0);
}

TEST_CASE("bridge: harness against the mocked game API") {
  const fs::path dir = fs::temp_directory_path() / ("itb_bridge_harness_" + std::to_string(getpid()));
  fs::remove_all(dir);
  fs::create_directories(dir / "profile_Alpha");
  LuaState lua;
  set_global(lua.L, "HARNESS_MODLOADER", kModloader.string());
  set_global(lua.L, "HARNESS_MOCK", kMock.string());
  set_global(lua.L, "HARNESS_DIR", dir.string());
  // With the game's scripts the harness also runs the final-mission
  // (Env_Volcano, pylon drop) and Env_Lightning enemy phases.
  const std::string game_dir = itb::GameData::default_game_root().string();
  const bool with_game = !game_dir.empty() && fs::exists(fs::path(game_dir) / "scripts" / "scripts.lua");
  if (with_game) set_global(lua.L, "HARNESS_GAME_DIR", game_dir);
  const int rc = luaL_dofile(lua.L, kHarness.string().c_str());
  INFO(lua.error());
  REQUIRE(rc == 0);
  if (with_game) {
    lua_getglobal(lua.L, "HARNESS_REAL_SCRIPTS_RAN");
    CHECK(lua_toboolean(lua.L, -1) == 1);
    lua_pop(lua.L, 1);
  }

  // The dump the SCENARIO left is the engine's input: it loads with the
  // extension fields.
  std::string error;
  auto rec = itb::load_recording(dir / "itb_snapshot_scenario_vek_order.json", nullptr, &error);
  REQUIRE_MESSAGE(rec.has_value(), error);
  CHECK(rec->bridge_ext_version == 1);
  CHECK(rec->bridge_errors.empty());
  CHECK(rec->mission.mission_key == 3);
  CHECK(rec->mission.env_classes.front() == "Env_Lightning");
  CHECK(rec->spawn_order_known);
  CHECK(rec->spawn_types == std::vector<std::string>{"Scorpion1"});
  CHECK(rec->board.spawn_points == std::vector<itb::Point>{{6, 6}});
  REQUIRE(rec->attack_order.size() == 2);
  CHECK(rec->attack_order_all == rec->attack_order);
  const itb::Pawn* first = rec->board.find_pawn(rec->attack_order[0]);
  REQUIRE(first != nullptr);
  CHECK(first->pos == itb::Point{4, 5});
  CHECK(first->fire);
  CHECK(first->queued.target == itb::Point{4, 4});
  const itb::Pawn* mech = rec->board.find_pawn(0);
  REQUIRE(mech != nullptr);
  CHECK(itb::symbol_name(mech->weapons[0]) == "Prime_Punchmech_B");
  CHECK(mech->shield);
  CHECK(rec->board.tile({2, 6}).fire == itb::FireState::Burning);
  CHECK(rec->board.tile({5, 6}).hp == 1);
  fs::remove_all(dir);
}
