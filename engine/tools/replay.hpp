// itb_inspect --replay: replays the old bot's recorded player actions through
// the engine and compares the result with what the game really did.
#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "itb/board.hpp"
#include "itb/engine.hpp"
#include "itb/recording.hpp"

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
  // --turns: replay whole turns (player actions, then the enemy phase) and
  // compare with the game's board at the start of the next turn.
  bool turns = false;
};

int run_replay(const ReplayOptions& options);

// A turn whose recorded plan was replayed to its end: the board the enemy
// phase starts from (each step synced to the game's recorded state).
struct TurnStart {
  std::string run;
  std::filesystem::path input;  // m<NN>_turn_<NN>_solve_input.json
  Recording rec;
  Board board;
  bool steps_ok = true;  // every player step matched the game (exact or tolerated)
};

int report_turns(Engine& engine, const std::vector<TurnStart>& turns, const ReplayOptions& options);

}  // namespace itb::tools
