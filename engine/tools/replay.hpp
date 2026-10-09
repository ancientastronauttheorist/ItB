// itb_inspect --replay: replays the old bot's recorded player actions through
// the engine and compares the result with what the game really did.
#pragma once

#include <filesystem>
#include <string>

namespace itb::tools {

struct ReplayOptions {
  std::filesystem::path recordings;  // recordings/ (run directories)
  std::filesystem::path failure_db;  // default: <recordings>/failure_db.jsonl
  std::filesystem::path game;        // game install (scripts/)
  int show = 25;            // mismatches to print in full
  bool sync = true;         // reset compared fields to the ground truth after each step
  std::string only_weapon;  // replay only actions with this weapon id ("" = all)
  std::string trace;        // "<run>/<mission>/<turn>": print boards and effects of that turn
  std::filesystem::path json_out;  // optional: every mismatch as JSON lines
};

int run_replay(const ReplayOptions& options);

}  // namespace itb::tools
