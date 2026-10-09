// Shared state between the Lua host's Board/Pawn bindings
// (lua_host_board.cpp) and its call layer (lua_host.cpp).
#pragma once

#include <cstdint>
#include <string>

#include "itb/board.hpp"
#include "itb/lua_host.hpp"
#include "lua_host_detail.hpp"

namespace itb::lua {

// Per-state host context, reachable from every binding.
struct HostContext {
  const Board* board = nullptr;  // the board of the call in progress
  LuaCall* call = nullptr;       // where writes and console output go
  int32_t selected = -1;         // uid of the Lua `Pawn` global (-1: nil)
  int depth = 0;                 // nested native -> Lua calls in progress
  LuaHostOptions options;
  LuaHost::Impl* impl = nullptr;
};

HostContext& host_context(lua_State* L);

// Installs Board, BoardPawn, GameMap, ValueBar, PawnFactory, PAWN_FACTORY and
// the settings/console globals.
void install_host_bindings(lua_State* L, HostContext* ctx);

// A fresh, non-owning BoardPawn userdata (nil for null), as luabind pushes
// every Pawn* result.
void push_pawn(lua_State* L, const Pawn* p);
void host_push_board(lua_State* L);
void host_push_game(lua_State* L);

// Implemented by the call layer (they re-enter Lua).
bool host_is_targeted(lua_State* L, Point p);
int host_deploy_score(lua_State* L, Point p);
int host_position_score(lua_State* L, const Pawn& pawn, Point p);
bool host_is_passive(lua_State* L, const std::string& name);
void host_console(lua_State* L, const std::string& line);

}  // namespace itb::lua
