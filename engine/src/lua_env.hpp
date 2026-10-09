// Embedded Lua 5.1 environment that runs the game's shipped scripts the way
// the game does at startup (GetScripts() order), standing in for the native
// bindings the scripts touch while loading.
#pragma once

#include <filesystem>
#include <functional>
#include <memory>
#include <string>
#include <vector>

struct lua_State;

namespace itb::detail {

struct ScriptRun {
  int files_ok = 0;
  std::vector<std::string> errors;           // "<file>: <message>"
  std::vector<std::string> stubbed_globals;  // native names replaced by stubs
  std::vector<std::string> overwritten_stubs;  // stubs the scripts redefined
  int passes = 0;
};

class LuaEnv {
 public:
  LuaEnv();
  ~LuaEnv();
  LuaEnv(const LuaEnv&) = delete;
  LuaEnv& operator=(const LuaEnv&) = delete;

  lua_State* L() const { return L_; }

  // Runs every script listed by scripts/scripts.lua under `game_root`. Native
  // functions the scripts need at load time are discovered from "attempt to
  // call/index global" errors and stubbed, then the whole load is repeated in
  // a fresh state until no new stubs are needed.
  // `bind` (optional) installs extra native bindings before the scripts run
  // (the Lua host's Board/Pawn/Game classes); names it defines are never
  // stubbed.
  using Binder = std::function<void(lua_State*)>;
  static std::unique_ptr<LuaEnv> load_game_scripts(const std::filesystem::path& game_root,
                                                   ScriptRun* run, const Binder& bind = {});

 private:
  void install_prelude(const std::vector<std::string>& stubs);
  lua_State* L_ = nullptr;
};

}  // namespace itb::detail
