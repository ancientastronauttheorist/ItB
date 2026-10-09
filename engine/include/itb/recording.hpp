// Loading boards from the Lua bridge's recordings (recordings/<run>/m*_solve_input.json).
#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

#include "itb/board.hpp"

namespace itb {

class GameData;

struct Recording {
  std::string run_id;
  int mission_index = 0;
  int turn = 0;
  std::string label;
  std::string mission_id;
  std::string phase;
  Board board;
  std::vector<int32_t> attack_order;  // Vek uids in the order the game reported
  std::vector<std::string> warnings;  // fields the loader could not map
};

// Parses a recording file (the wrapper with a "data.bridge_state" object, or a
// bare bridge_state). Unit types missing from `data` are kept with their
// recorded stats and reported in `warnings`. Returns nullopt and sets `error`
// if the file is not a bridge board.
std::optional<Recording> load_recording(const std::filesystem::path& path,
                                        const GameData* data, std::string* error);

}  // namespace itb
