// itb_inspect --replay: replays the old bot's recorded player actions through
// the engine and compares the result with what the game really did.
#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "itb/board.hpp"
#include "itb/engine.hpp"
#include "itb/objectives.hpp"
#include "itb/recording.hpp"
#include "itb/score.hpp"

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

// itb_inspect --score <recording>: replays the recorded plan (no syncing),
// runs the enemy phase and prints the turn score breakdown.
int run_score(const std::filesystem::path& input, const std::filesystem::path& game);

// Objective state the old bot's post-enemy summary also records.
struct ObjectiveTally {
  int objective_buildings = 0;  // unique buildings standing
  int pods = 0;                 // pods still on the board
  int mites = 0;                // infected mechs
};
ObjectiveTally objective_counts(const Board& board);
void print_score(const Score& score, const ObjectiveReport& objectives, const PositionTerms& position);

}  // namespace itb::tools
