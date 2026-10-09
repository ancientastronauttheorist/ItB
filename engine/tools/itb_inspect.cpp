// itb_inspect: look at what the engine sees.
//
//   itb_inspect [--game DIR] <recording.json>   render a recorded board
//   itb_inspect [--game DIR] --pawns            list pawn definitions
//   itb_inspect [--game DIR] --scripts          report the script load
//   itb_inspect [--game DIR] --corpus DIR       load every *_solve_input.json under DIR

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <map>
#include <string>
#include <vector>

#include "itb/format.hpp"
#include "itb/game_data.hpp"
#include "itb/recording.hpp"

namespace fs = std::filesystem;
using namespace itb;

namespace {

int usage() {
  std::cerr << "usage: itb_inspect [--game DIR] (<recording.json> | --pawns | --scripts | --corpus DIR)\n";
  return 2;
}

// Enemy pawns with a queued attack, in board-list order.
std::vector<int32_t> queued_vek_in_list_order(const Board& b) {
  std::vector<int32_t> out;
  for (const Pawn& p : b.pawns()) {
    if (p.team == Team::Enemy && p.queued.active()) out.push_back(p.uid);
  }
  return out;
}

int run_corpus(const fs::path& dir, const GameData& data) {
  std::vector<fs::path> files;
  for (const auto& e : fs::recursive_directory_iterator(dir)) {
    const std::string name = e.path().filename().string();
    if (e.is_regular_file() && name.ends_with("_solve_input.json")) files.push_back(e.path());
  }
  std::sort(files.begin(), files.end());

  int loaded = 0, failed = 0, with_order = 0, order_match = 0, order_match_by_uid = 0;
  std::map<std::string, int> warning_counts;
  std::vector<std::string> mismatches;
  for (const fs::path& f : files) {
    std::string error;
    auto rec = load_recording(f, &data, &error);
    if (!rec) {
      ++failed;
      std::cerr << "FAIL " << error << "\n";
      continue;
    }
    ++loaded;
    for (const std::string& w : rec->warnings) ++warning_counts[w];

    // attack_order lists Vek uids in the order the game will fire them.
    std::vector<int32_t> expected;
    for (int32_t uid : rec->attack_order) {
      const Pawn* p = rec->board.find_pawn(uid);
      if (p && p->queued.active()) expected.push_back(uid);
    }
    if (expected.size() < 2) continue;
    ++with_order;
    const std::vector<int32_t> actual = queued_vek_in_list_order(rec->board);
    if (actual == expected) {
      ++order_match;
    } else if (mismatches.size() < 8) {
      std::string line = f.parent_path().filename().string() + "/" + f.filename().string() + " expected";
      for (int32_t u : expected) line += " " + std::to_string(u);
      line += " | list order";
      for (int32_t u : actual) line += " " + std::to_string(u);
      mismatches.push_back(line);
    }
    std::vector<int32_t> by_uid = actual;
    std::sort(by_uid.begin(), by_uid.end());
    if (by_uid == expected) ++order_match_by_uid;
  }

  std::printf("recordings: %zu  loaded: %d  failed: %d\n", files.size(), loaded, failed);
  // Bridges before 2026-06-23 wrote attack_order sorted by uid (a bot-side
  // assumption), so only later recordings reflect the game's actual order.
  std::printf("boards with >=2 queued Vek: %d (attack_order before 2026-06-23 is uid-sorted by the bot)\n",
              with_order);
  std::printf("  attack order == board list order: %d\n", order_match);
  std::printf("  attack order == ascending uid:     %d\n", order_match_by_uid);
  for (const std::string& m : mismatches) std::printf("  mismatch: %s\n", m.c_str());
  if (!warning_counts.empty()) {
    std::printf("warnings:\n");
    for (const auto& [w, n] : warning_counts) std::printf("  %5d  %s\n", n, w.c_str());
  }
  return failed == 0 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  fs::path game = GameData::default_game_root();
  std::vector<std::string> args;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--game" && i + 1 < argc) {
      game = argv[++i];
    } else {
      args.push_back(a);
    }
  }
  if (args.empty()) return usage();

  ScriptLoadReport report;
  GameData data;
  try {
    data = GameData::load(game, &report);
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    return 1;
  }

  if (args[0] == "--scripts") {
    std::printf("game root: %s\n", game.string().c_str());
    std::printf("scripts ok: %d  failed: %d  passes: %d  pawns: %zu\n", report.files_ok,
                report.files_failed, report.passes, data.pawns().size());
    std::printf("stubbed native globals (%zu):", report.stubbed_globals.size());
    for (const auto& s : report.stubbed_globals) std::printf(" %s", s.c_str());
    std::printf("\n");
    std::printf("stubs later defined by Lua (%zu):", report.overwritten_stubs.size());
    for (const auto& s : report.overwritten_stubs) std::printf(" %s", s.c_str());
    std::printf("\n");
    for (const auto& e : report.errors) std::printf("  error: %s\n", e.c_str());
    for (const auto& w : report.field_warnings) std::printf("  field: %s\n", w.c_str());
    return 0;
  }
  if (args[0] == "--pawns") {
    for (const PawnDef& d : data.pawns()) {
      std::printf("%-26s hp %2d move %d team %d%s%s%s%s  [", d.name.c_str(), d.health, d.move_speed,
                  static_cast<int>(d.default_team), d.massive ? " massive" : "",
                  d.flying ? " flying" : "", d.armor ? " armor" : "", d.pushable ? "" : " stable");
      for (size_t i = 0; i < d.skills.size(); ++i) {
        std::printf("%s%s", i ? ", " : "", d.skills[i].c_str());
      }
      std::printf("]\n");
    }
    return 0;
  }
  if (args[0] == "--corpus") {
    if (args.size() < 2) return usage();
    return run_corpus(args[1], data);
  }

  std::string error;
  auto rec = load_recording(args[0], &data, &error);
  if (!rec) {
    std::cerr << "error: " << error << "\n";
    return 1;
  }
  std::printf("%s m%02d turn %d %s (%s)\n", rec->run_id.c_str(), rec->mission_index, rec->turn,
              rec->mission_id.c_str(), rec->phase.c_str());
  std::fputs(render_board(rec->board).c_str(), stdout);
  for (const std::string& w : rec->warnings) std::printf("warning: %s\n", w.c_str());
  return 0;
}
