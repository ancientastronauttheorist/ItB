// itb_inspect --predict: the engine's prediction for one bridge state.
#pragma once

#include <filesystem>
#include <string>

namespace itb::tools {

struct PredictOptions {
  std::filesystem::path state;  // a bridge state (bare or a recording wrapper)
  std::filesystem::path game;
  std::string actions;          // JSON array, or @FILE
  bool enemy = true;            // run the enemy phase after the actions
  bool branches = false;        // enumerate the enemy phase's hidden choices
  int max_branches = 64;
  std::filesystem::path json_out;
};

int run_predict(const PredictOptions& options);

}  // namespace itb::tools
