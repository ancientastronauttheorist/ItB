// Loading boards from the Lua bridge's recordings (recordings/<run>/m*_solve_input.json).
#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "itb/board.hpp"

namespace itb {

class GameData;

// Warning for boards from bridges whose terrain-name table called ice "lava"
// (before 2026-05-04): those tiles load as ice, and the same run's other files
// (predictions, verify diffs) say "lava" for ice too.
inline constexpr const char* kIceNamedLava = "terrain id 5 named 'lava' (old bridge name table): loaded as ice";

struct Recording {
  std::string run_id;
  int mission_index = 0;
  int turn = 0;
  std::string label;
  std::string mission_id;
  std::string phase;
  Board board;
  std::vector<int32_t> attack_order;  // Vek uids in the order the game reported
  // Pilot table name per unit uid (e.g. "Pilot_Rock"); the pilot's Lua Skill
  // gives its ability (Engine::pilot_ability).
  std::vector<std::pair<int32_t, std::string>> pilots;
  int difficulty = -1;  // the bridge's GetDifficulty(), -1 if not recorded
  std::vector<std::string> warnings;  // fields the loader could not map
};

// Parses a recording file (the wrapper with a "data.bridge_state" object, or a
// bare bridge_state). Unit types missing from `data` are kept with their
// recorded stats and reported in `warnings`. Squad passives come from the
// mechs' Passive_* weapons and the board psion from the living leaders.
// Returns nullopt and sets `error` if the file is not a bridge board.
std::optional<Recording> load_recording(const std::filesystem::path& path,
                                        const GameData* data, std::string* error);

}  // namespace itb
