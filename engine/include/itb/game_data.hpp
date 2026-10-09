// Static game definitions read from the game's own Lua scripts at runtime.
//
// The scripts are loaded from a local game install (never committed). Field
// names and defaults come from the Pawn base table in scripts/global.lua.
#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "itb/board.hpp"
#include "itb/core.hpp"
#include "itb/symbols.hpp"

namespace itb {

struct PawnDef {
  std::string name;
  Symbol symbol = kNoSymbol;
  std::string pawn_class;  // "Prime", "Brute", ... for mechs
  int health = 3;
  int move_speed = 0;
  std::vector<std::string> skills;
  Team default_team = Team::None;
  Faction default_faction = Faction::Default;
  Leader leader = Leader::None;
  Tier tier = Tier::Normal;
  int ranged = 0;
  bool massive = false;
  bool flying = false;
  bool pushable = true;
  bool armor = false;
  bool ignore_smoke = false;
  bool ignore_fire = false;
  bool ignore_flip = false;
  bool minor = false;
  bool corpse = false;
  bool burrows = false;
  bool jumper = false;
  bool teleporter = false;
  bool explodes = false;
  bool neutral = false;
  bool non_grid = false;
  bool large_shield = false;
  bool temp_unit = false;
  bool mission = false;
  bool spawn_limit = true;
  bool void_shock_immune = false;
  bool avoiding_mines = false;
  bool is_death_effect = false;
  std::vector<Point> extra_spaces;
};

struct ScriptLoadReport {
  int files_ok = 0;
  int files_failed = 0;
  int passes = 0;
  std::vector<std::string> errors;
  std::vector<std::string> stubbed_globals;
  std::vector<std::string> overwritten_stubs;  // stubbed, then defined by Lua
  std::vector<std::string> field_warnings;     // fields that weren't plain data
};

class GameData {
 public:
  // ITB_GAME_DIR if set, else the build-configured default.
  static std::filesystem::path default_game_root();

  // Throws std::runtime_error if the scripts cannot be found or loaded.
  static GameData load(const std::filesystem::path& game_root,
                       ScriptLoadReport* report = nullptr);

  const std::vector<PawnDef>& pawns() const { return pawns_; }
  const PawnDef* pawn(std::string_view name) const;
  const PawnDef* pawn(Symbol symbol) const;

  // A fresh pawn of this type with its definition's traits and full health.
  Pawn make_pawn(const PawnDef& def, int32_t uid, Point pos) const;

 private:
  std::vector<PawnDef> pawns_;
  std::unordered_map<Symbol, size_t> by_symbol_;
};

}  // namespace itb
