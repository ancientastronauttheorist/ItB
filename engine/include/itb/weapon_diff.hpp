// Differential checks of the C++ weapon ports against the Lua scripts they
// mirror (LuaHost::set_native_weapons). Used by the tests (a fast subset) and
// by `itb_inspect --diff-weapons` (the full sweep).
#pragma once

#include <cstdint>
#include <random>
#include <string>
#include <vector>

#include "itb/board.hpp"
#include "itb/lua_host.hpp"

namespace itb {

class GameData;

struct WeaponDiffStats {
  uint64_t areas = 0;       // GetTargetArea calls compared
  uint64_t effects = 0;     // GetSkillEffect calls compared
  uint64_t native = 0;      // of those, answered by a port (the rest fell back to Lua)
  uint64_t mismatches = 0;  // calls whose results differ
  std::vector<std::string> examples;  // the first mismatches, described

  void add(const WeaponDiffStats& o);
};

// Every weapon table with a port for GetTargetArea or GetSkillEffect, one
// per distinct behaviour: tables whose ported methods and field values are
// the same (e.g. a weapon and an upgrade that changes nothing the port
// reads) behave identically in Lua and natively, so one stands for all.
// `all` returns every such table instead.
std::vector<std::string> ported_weapons(LuaHost& host, bool all = false);

// Compares Lua and the port for `weapon` on board `b`: for every pawn on the
// board as the shooter (selected, firing from its tile), the target area, and
// the skill effect at every tile of the board. Both runs start from the same
// random stream; the host's native setting is restored afterwards.
void diff_weapon(LuaHost& host, const Board& b, const std::string& weapon, WeaponDiffStats& stats,
                 size_t max_examples = 5);

// A random board for the differential tests: every terrain, tile status and
// pawn type (from `data`), random statuses, teams, stacked bodies, webs,
// queued shots, passives and pilots; weapons from `weapons`.
Board random_board(const GameData& data, const std::vector<std::string>& weapons, std::mt19937& rng);

}  // namespace itb
