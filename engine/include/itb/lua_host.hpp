// Stage 6: a Lua 5.1 host that runs the game's own weapon and death-effect
// scripts against an engine Board.
//
// The host loads every shipped script once (GetScripts() order) into one Lua
// state with faithful native bindings: Point, SpaceDamage, SkillEffect, the
// list types, Board and BoardPawn queries, Game, the team/terrain/... constants
// and the game's glibc-compatible rand() stream. A call then goes through the
// Lua global CallMethod exactly as the game's Skill/Pawn code does, with
// `self` = the weapon's class table (id plus _A/_B/_AB for powered upgrades).
//
// The board is read-only during a call: Board/BoardPawn userdata look the
// engine Board up on every access, so nothing is copied into Lua. Mutating
// bindings (Board:SetTerrain, Pawn:SetFrozen, Game:ModifyPowerGrid, ...) are
// not applied; each call is recorded as a LuaWrite for the caller.
//
// Boundary with the stage 4 executor: results are exactly what Lua returned.
// Skill::PrepareEffect (default sAnimation := the weapon's Explosion, owner
// team, projectile source := origin) and Skill::CheckAlterations (Vek Hormones,
// Boost) are native steps applied after Lua returns; they belong to the
// executor. sScript strings are not run here either: the executor runs them
// with run_script() when the entry is applied.
#pragma once

#include <cstdint>
#include <filesystem>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "itb/board.hpp"
#include "itb/core.hpp"
#include "itb/space_damage.hpp"

namespace itb {

// Point() in Lua: the native "invalid" sentinel (-2147483647, -2147483647).
inline constexpr Point kLuaPointNone{-2147483647, -2147483647};

// Every native SpaceDamage field (0xC8 bytes in game), as Lua sees them.
// Fields without a Lua name are only written by SkillEffect:Add* methods.
struct LuaSpaceDamage {
  Point loc = kInvalidPoint;
  int iDamage = 0;
  int iPush = 4;  // DIR_NONE
  int iShield = 0;
  bool bSimpleMark = false;
  int iFire = 0;
  int iFrozen = 0;
  int iInjure = 0;
  int iSmoke = 0;
  int iAcid = 0;
  int iCrack = 0;
  bool bKO_Effect = false;
  bool boosted = false;  // +0x31, set by SpaceDamage::Boost
  int anim_flags = 2;    // +0x34: ANIM_NO_DELAY 1 / ANIM_DELAY 2 / ANIM_REVERSE 4
  std::string sAnimation;
  std::string sSound;
  std::string projectile_art;  // +0x48
  std::string sImageMark;
  int projectile_kind = 0;  // 1 artillery, 2 projectile, 3 air strike, 4 dropper, 5 laser, 6 reverse air strike
  Point projectile_source = kInvalidPoint;
  std::string sPawn;
  int iPawnTeam = 2;
  int owner_team = 2;  // +0x74, stamped by Skill::PrepareEffect
  bool bHide = false;
  bool bHidePath = false;
  bool bHideIcon = false;
  bool bEvacuate = false;
  float fDelay = 0.0f;
  std::vector<Point> path;  // +0x80 move path
  int move_kind = 0;        // 0 walk, 1 leap, 2 charge, 3 melee, 4 teleport, 5 burrow
  int iTerrain = 10;
  std::string sScript;
  std::string grapple_anim;  // +0xA8
  Point grapple_source = kInvalidPoint;
  std::string sItem;
  int mode_override = 3;  // +0xC0

  // SpaceDamage::IsMovement: a path, not melee, no projectile.
  bool is_movement() const { return !path.empty() && move_kind != 3 && projectile_kind == 0; }
  bool operator==(const LuaSpaceDamage&) const = default;
};

struct LuaSkillEffect {
  std::vector<LuaSpaceDamage> effect;
  std::vector<LuaSpaceDamage> q_effect;
  std::string sound;         // +0x30
  std::string impact_sound;  // +0x38
  Point piOrigin = kLuaPointNone;
  Point target = kLuaPointNone;  // +0x48
  int team = 2;                  // +0x50
  int iOwner = -1;
  std::string str58;
  bool follow_up = false;  // +0x60
  bool flag61 = false;

  bool operator==(const LuaSkillEffect&) const = default;
};

// Converts to the engine types. Fields the engine SpaceDamage does not carry
// yet (animation, sound, art, UI flags) are dropped.
SpaceDamage to_engine(const LuaSpaceDamage& sd);
SkillEffect to_engine(const LuaSkillEffect& se);

// A value passed to a mutating binding, as recorded.
using LuaArg = std::variant<std::monostate, bool, double, std::string, Point>;

// A mutating binding a script called (not applied by the host).
struct LuaWrite {
  std::string object;  // "Board", "Pawn", "Game", "PAWN_FACTORY"
  std::string method;
  int32_t pawn = -1;   // receiver uid for Pawn writes
  std::vector<LuaArg> args;  // Pawn* arguments are recorded as their uid (double)
  // A SkillEffect argument (Board:AddEffect), or a SpaceDamage argument
  // wrapped as its only entry (Board:AddEffect(SD), Board:DamageSpace(SD)).
  std::optional<LuaSkillEffect> effect;

  std::string describe() const;
};

// Result of one native -> Lua call.
struct LuaCall {
  bool ok = true;      // false: Lua error or wrong return type (the game's default was used)
  std::string error;   // the caught message ("Something went wrong in ..." in game)
  std::vector<LuaWrite> writes;
  std::vector<std::string> console;  // LOG/print/ConsolePrint output
};

struct LuaHostOptions {
  int difficulty = 0;          // GetDifficulty()
  bool advanced_content = true;  // IsNewEnemies/IsNewMissions/IsNewEquipment
  int sector = 1;              // Game:GetSector()
  // IsPassiveSkill(name) is true if any of these starts with `name`
  // (SquadControl::sTempPassive plus the Passive strings of powered skills).
  // nullopt: derived on every query from the Lua Passive field of each
  // weapon carried by a mech on the board.
  std::optional<std::vector<std::string>> passives;
  uint32_t seed = 1;           // initial rand() seed (srand)
};

struct LuaHostReport {
  int files_ok = 0;
  int passes = 0;
  std::vector<std::string> errors;
  std::vector<std::string> stubbed_globals;    // names left to inert stubs
  std::vector<std::string> overwritten_stubs;  // must be empty
};

class LuaHost {
 public:
  // Loads the scripts under game_root (see GameData::default_game_root).
  // Throws std::runtime_error if they cannot be found.
  static std::unique_ptr<LuaHost> create(const std::filesystem::path& game_root,
                                         const LuaHostOptions& options = {},
                                         LuaHostReport* report = nullptr);
  ~LuaHost();
  LuaHost(const LuaHost&) = delete;
  LuaHost& operator=(const LuaHost&) = delete;

  // Weapon table name for a base id and its powered upgrades
  // (Skill::UpdateUpgrades): "", "_A", "_B" or "_AB".
  static std::string weapon_name(std::string_view base, bool upgrade_a, bool upgrade_b);

  // Skill::GetTargetArea: Lua GetTargetArea(self, origin), with the points
  // that have x < 0 or y < 0 removed (duplicates and other off-board points
  // are kept, as in game). `shooter` becomes the Lua `Pawn` global (the
  // selected pawn) for the call. Empty on error.
  std::vector<Point> target_area(const Board& board, const Pawn& shooter,
                                 std::string_view weapon, Point origin, LuaCall* call = nullptr);

  // Lua GetSkillEffect(self, origin, target), unprocessed. Unlike
  // Skill::ComputeAffectedPoints this does not check the target against the
  // target area. Empty on error.
  LuaSkillEffect skill_effect_raw(const Board& board, const Pawn& shooter, std::string_view weapon,
                                  Point origin, Point target, LuaCall* call = nullptr);
  SkillEffect skill_effect(const Board& board, const Pawn& shooter, std::string_view weapon,
                           Point origin, Point target, LuaCall* call = nullptr);

  // Skill::FireQueued for a queued Vek attack: recomputes the target area
  // from the shooter's current tile (the game reuses the area cached at
  // planning time when the shooter did not move), fizzles (empty) if the
  // stored target is not in it, else runs GetSkillEffect(current tile, target)
  // and returns the queued list as the list that fires (`effect`; `q_effect`
  // is left empty).
  LuaSkillEffect queued_effect_raw(const Board& board, const Pawn& shooter, std::string_view weapon,
                                   Point target, LuaCall* call = nullptr);
  SkillEffect queued_effect(const Board& board, const Pawn& shooter, std::string_view weapon,
                            Point target, LuaCall* call = nullptr);

  // Two-click weapons (Lua TwoClick).
  bool is_two_click(std::string_view weapon, LuaCall* call = nullptr);
  std::vector<Point> second_target_area(const Board& board, const Pawn& shooter,
                                        std::string_view weapon, Point origin, Point first,
                                        LuaCall* call = nullptr);
  LuaSkillEffect final_effect_raw(const Board& board, const Pawn& shooter, std::string_view weapon,
                                  Point origin, Point first, Point target, LuaCall* call = nullptr);

  // Pawn::TriggerDeathEffect's Lua part: CallMethod(type, "GetDeathEffect",
  // pawn tile). `seed` reseeds rand() first (the pawn's hidden +0x964 seed;
  // live seeds are not visible, so results are one sample of a random
  // outcome). The native ACID-pool / Fast Decay entries are not added here.
  // `selected` is the Lua `Pawn` global (the game leaves it at whichever pawn
  // was selected last); null sets it to nil.
  LuaSkillEffect death_effect_raw(const Board& board, const Pawn& dying,
                                  std::optional<uint32_t> seed = std::nullopt,
                                  const Pawn* selected = nullptr, LuaCall* call = nullptr);
  SkillEffect death_effect(const Board& board, const Pawn& dying,
                           std::optional<uint32_t> seed = std::nullopt,
                           const Pawn* selected = nullptr, LuaCall* call = nullptr);

  // LuaEnv::DirectLua for a SpaceDamage sScript. The board is read-only;
  // mutations come back as LuaCall::writes for the executor to apply.
  LuaCall run_script(const Board& board, std::string_view code, const Pawn* selected = nullptr);

  // The shared rand() stream (glibc TYPE_3).
  void seed(uint32_t s);
  int rand();

  // Every global table derived from the Lua Skill class (all weapons,
  // including upgrade variants), sorted.
  std::vector<std::string> weapon_ids() const;
  // A Lua field of a global table (through its metatable chain), as a
  // string/number/bool; nullopt when absent or of another type.
  std::optional<std::string> lua_string(std::string_view table, std::string_view field) const;
  std::optional<double> lua_number(std::string_view table, std::string_view field) const;
  std::optional<bool> lua_bool(std::string_view table, std::string_view field) const;

  struct Impl;

 private:
  LuaHost();
  std::unique_ptr<Impl> impl_;
};

}  // namespace itb
