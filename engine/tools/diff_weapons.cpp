// itb_inspect --diff-weapons: the C++ weapon ports against the Lua scripts
// they mirror (weapon_diff.hpp), on random boards and recorded boards.
//
//   --diff-weapons [DIR] [--random N] [--seed S] [--weapon ID] [--all-tables]
//   --diff-weapons --ports      which weapon methods run natively, and why not
//
// Every ported weapon table (one per distinct behaviour unless --all-tables)
// is fired by every pawn of every board, at every tile; any difference in the
// target area, the SkillEffect (every field of every entry), Lua errors,
// writes, console output or random draws is a mismatch (exit status 1).

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <map>
#include <random>
#include <string>
#include <vector>

#include "itb/engine.hpp"
#include "itb/game_data.hpp"
#include "itb/lua_host.hpp"
#include "itb/recording.hpp"
#include "itb/weapon_diff.hpp"
#include "solve_tool.hpp"

namespace fs = std::filesystem;

namespace itb::tools {

int run_diff_weapons(const DiffWeaponsOptions& opt) {
  std::unique_ptr<Engine> engine;
  try {
    engine = Engine::create(opt.game);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    return 1;
  }
  LuaHost& host = engine->lua();
  if (opt.ports) {
    for (const std::string& id : host.weapon_ids()) {
      for (const char* m : {"GetTargetArea", "GetSkillEffect"}) {
        std::printf("%-32s %-15s %s\n", id.c_str(), m, host.native_port_status(id, m).c_str());
      }
    }
    return 0;
  }
  std::vector<std::string> weapons = ported_weapons(host, opt.all_tables);
  if (!opt.weapon.empty()) {
    weapons.assign(1, opt.weapon);
    if (host.native_binding(opt.weapon).empty()) {
      std::fprintf(stderr, "%s has no port\n", opt.weapon.c_str());
      return 1;
    }
  }
  std::vector<Board> boards;
  std::vector<std::string> names;
  if (!opt.recordings.empty()) {
    std::vector<fs::path> files;
    for (const auto& e : fs::recursive_directory_iterator(opt.recordings)) {
      if (e.is_regular_file() && e.path().filename().string().ends_with("_solve_input.json")) files.push_back(e.path());
    }
    std::sort(files.begin(), files.end());
    for (const fs::path& f : files) {
      std::string error;
      if (auto rec = load_recording(f, &engine->data(), &error)) {
        boards.push_back(rec->board);
        names.push_back(f.parent_path().filename().string() + "/" + f.filename().string());
      }
    }
  }
  const size_t recorded = boards.size();
  std::mt19937 rng(opt.seed);
  const std::vector<std::string> pool = host.weapon_ids();
  for (int i = 0; i < opt.random; ++i) {
    boards.push_back(random_board(engine->data(), pool, rng));
    names.push_back("random #" + std::to_string(i));
  }
  std::printf("%zu ported weapon tables, %zu recorded boards, %d random boards\n", weapons.size(), recorded,
              opt.random);
  WeaponDiffStats total;
  for (const std::string& w : weapons) {
    WeaponDiffStats s;
    for (size_t i = 0; i < boards.size(); ++i) {
      const size_t shown = s.examples.size();
      diff_weapon(host, boards[i], w, s, 3);
      for (size_t k = shown; k < s.examples.size(); ++k) s.examples[k] += "  [" + names[i] + "]";
    }
    std::printf("%-28s area %-30s effect %-34s %9llu areas %10llu effects %5.1f%% native  %s\n", w.c_str(),
                host.native_port(w, "GetTargetArea").c_str(), host.native_port(w, "GetSkillEffect").c_str(),
                static_cast<unsigned long long>(s.areas), static_cast<unsigned long long>(s.effects),
                100.0 * static_cast<double>(s.native) / static_cast<double>(std::max<uint64_t>(1, s.areas + s.effects)),
                s.mismatches ? ("MISMATCHES " + std::to_string(s.mismatches)).c_str() : "identical");
    for (const std::string& e : s.examples) std::printf("    %s\n", e.c_str());
    std::fflush(stdout);
    total.add(s);
  }
  std::printf("\ntotal: %llu target areas, %llu skill effects compared, %llu answered natively, %llu mismatches\n",
              static_cast<unsigned long long>(total.areas), static_cast<unsigned long long>(total.effects),
              static_cast<unsigned long long>(total.native), static_cast<unsigned long long>(total.mismatches));
  return total.mismatches ? 1 : 0;
}

}  // namespace itb::tools
