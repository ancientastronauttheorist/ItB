// Stage 6 integration: player and Vek actions end to end.
//
// An Engine owns the game data and one Lua host. Each action runs the way the
// game runs it:
//
//   target area (Lua GetTargetArea, from the shooter's tile)
//   -> GetSkillEffect (two-click weapons: TranslateFirstClick,
//      GetSecondTargetArea, GetFinalEffect)
//   -> Skill::PrepareEffect and CheckAlterations (Boost, Vek Hormones)
//   -> the frame-exact executor, with every sScript and Pawn:GetDeathEffect
//      run by the same Lua host against the board as it is at that frame
//   -> the Pawn::FireWeapon bookkeeping (moved/active, pilot bonuses).
//
// Moves are the Lua `Move` skill (walk, leap or teleport, plus the Web_Vek and
// Adjacent_Heal abilities). Repairs are the pawn's repair skill
// (`Skill_Repair` unless the caller names a pilot variant). Queued Vek
// attacks recompute their effect from the shooter's current tile and fizzle
// when the stored target left the target area (Skill::FireQueued).
//
// Lua writes made by scripts and death effects (Board:AddEffect,
// Board:SetTerrain, Pawn:SetFrozen, Game:ModifyPowerGrid, ...) are applied to
// the board when the script returns; writes the engine does not model are
// reported in ActionResult::unapplied.
#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "itb/board.hpp"
#include "itb/executor.hpp"
#include "itb/lua_host.hpp"
#include "itb/space_damage.hpp"
#include "itb/tile_rules.hpp"

namespace itb {

class GameData;

struct EngineOptions {
  LuaHostOptions lua;
  ResolveConfig config;
  std::optional<Durations> durations;
};

// Per-action hooks and outputs. Everything is optional.
struct ActionOptions {
  // Refuse actions the game would not allow (dead, unpowered or frozen
  // shooter, a pawn that already acted or moved, a target outside the target
  // area). Off: fire whatever was asked, like a script would.
  bool check_legal = true;
  // Grid Defense: return true if the populated building at p resists. Empty =
  // never resists. Every roll is a ChanceRecord in ActionResult::resolve.
  std::function<bool(Point building, int amount)> grid_resist;
  // Seed for a Lua death effect (the pawn's hidden seed in game). Empty =
  // the pawn's uid + 1. Death effects that draw numbers are logged as
  // ChanceKind::LuaRandom.
  std::function<uint32_t(const Pawn& dying)> death_seed;
  // A spider psion egg landing (see ResolveContext::spider_egg).
  std::function<int(Resolver&, const Pawn& pawn, const std::vector<Point>& tiles)> spider_egg;
  std::vector<RulesEvent>* events = nullptr;
  std::vector<ResolveEvent>* log = nullptr;
};

enum class ActionStatus : uint8_t {
  Ok,
  NoPawn,           // no such pawn on the board
  NoWeapon,         // empty slot or unknown weapon table
  CannotAct,        // dead, unpowered, frozen, already acted / moved
  NotInArea,        // the target is not in the (second) target area
  NeedsSecondClick, // a two-click weapon fired without its second target
  NoEffect,         // the skill produced nothing to apply (nothing happened)
};

const char* to_string(ActionStatus s);

struct ActionResult {
  ActionStatus status = ActionStatus::Ok;
  std::string weapon;  // the Lua table that fired ("Move", "Prime_Punchmech_A", ...)
  SkillEffect effect;  // the effect as fired: prepared, alterations applied
  ResolveResult resolve;
  Point end = kInvalidPoint;  // where the actor stands afterwards (kInvalidPoint: gone)
  // Errors the game would swallow: the weapon's own Lua calls, scripts and
  // death effects (the game falls back to its defaults, as here).
  std::vector<std::string> lua_errors;
  // Lua writes from scripts and death effects the engine does not model.
  std::vector<LuaWrite> unapplied;

  bool ok() const { return status == ActionStatus::Ok; }
};

class Engine {
 public:
  // Loads the game data and the Lua host from a game install
  // (GameData::default_game_root() for the configured one). Throws
  // std::runtime_error if the scripts cannot be found.
  static std::unique_ptr<Engine> create(const std::filesystem::path& game_root,
                                        const EngineOptions& options = {});
  ~Engine();
  Engine(const Engine&) = delete;
  Engine& operator=(const Engine&) = delete;

  const GameData& data() const;
  LuaHost& lua();
  const EngineOptions& options() const;

  // The Move skill to `dest` (Pawn::FireWeapon slot 0).
  ActionResult move(Board& board, int32_t uid, Point dest, const ActionOptions& opts = {});

  // Fires the weapon in Pawn::weapons[slot] (the Lua table name, upgrade
  // suffix included) at `target`; `target2` is the second click of a
  // two-click weapon.
  ActionResult fire_weapon(Board& board, int32_t uid, int slot, Point target,
                           std::optional<Point> target2 = std::nullopt,
                           const ActionOptions& opts = {});
  // The same with a weapon named directly (need not be carried).
  ActionResult fire_weapon(Board& board, int32_t uid, std::string_view weapon, Point target,
                           std::optional<Point> target2 = std::nullopt,
                           const ActionOptions& opts = {});

  // Repair: the repair skill (Skill_Repair, or a pilot's variant such as
  // Skill_Repair_A / Skill_Repair_Power / Skill_Repair_Punch) at `target`
  // (default: the pawn's own tile). Same rules as a weapon.
  ActionResult repair(Board& board, int32_t uid, Point target = kInvalidPoint,
                      std::string_view skill = "Skill_Repair", const ActionOptions& opts = {});

  // A Vek's telegraphed attack (SkillManager::FireQueued): the stored target
  // with the effect recomputed from the shooter's current tile. The stored
  // shot is used up whether or not it fizzles.
  ActionResult fire_queued(Board& board, int32_t uid, const ActionOptions& opts = {});

  // A pilot's rule-changing ability (board.hpp PilotAbility) from its Lua
  // table's Skill, e.g. "Pilot_Rock" -> Rock_Skill. kPilotNone if none.
  uint32_t pilot_ability(std::string_view pilot_id);
  // The repair skill a pilot brings: Skill_Repair unless the pilot's Skill
  // replaces it (Power_Repair -> Skill_Repair_Power, Mantis_Skill ->
  // Skill_Repair_Punch; the mapping is inferred from the names).
  std::string repair_skill(std::string_view pilot_id);

  // Resolves a ready effect with the Lua hooks wired (scripts, death
  // effects), e.g. an environment effect. `out` collects Lua diagnostics.
  ResolveResult resolve(Board& board, const SkillEffect& effect, const WeaponInfo& weapon,
                        const ActionOptions& opts = {}, ActionResult* out = nullptr);

  // Applies Lua writes reported by a script or death effect to the board
  // under resolution. Writes the engine does not model are appended to
  // `unapplied`.
  void apply_writes(Resolver& r, RulesContext& rules, const std::vector<LuaWrite>& writes,
                    std::vector<LuaWrite>& unapplied);

  struct Impl;

 private:
  Engine();
  std::unique_ptr<Impl> impl_;
};

}  // namespace itb
