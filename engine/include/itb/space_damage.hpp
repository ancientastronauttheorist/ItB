// SpaceDamage and SkillEffect: what a weapon, environment or death effect
// asks the board to do. Mirrors the fields the game exposes to Lua
// (SpaceDamage is 0xC8 bytes natively; SkillEffect holds an instant list and a
// queued list).
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "itb/core.hpp"
#include "itb/symbols.hpp"

namespace itb {

// How a hit is applied. Weapon hits respect armor/ACID and affect terrain;
// push-mode hits (bumps, blocked spawns) ignore armor/ACID and only damage
// pawns, buildings and mountains.
enum class DamageMode : int8_t { Weapon = 0, Push = 1 };

// SpaceDamage status fields use 0 = untouched, 1 = apply, 2 = remove.
enum class StatusChange : int8_t { None = 0, Apply = 1, Remove = 2 };

enum class ProjectileKind : int8_t { None = 0, Artillery = 1, Projectile = 2, Laser = 5 };

enum class MoveKind : int8_t { Walk = 0, Leap = 1, Charge = 2, Melee = 3, Teleport = 4, Burrow = 5 };

// iTerrain sentinel meaning "leave the terrain alone".
inline constexpr int kNoTerrainChange = 10;

struct SpaceDamage {
  Point loc = kInvalidPoint;
  int damage = 0;  // may be kDamageZero / kDamageDeath; negative heals
  Dir push = Dir::None;
  int shield = 0;  // >0 adds a shield, <0 removes one
  StatusChange fire = StatusChange::None;
  StatusChange frozen = StatusChange::None;
  StatusChange injure = StatusChange::None;
  StatusChange smoke = StatusChange::None;
  StatusChange acid = StatusChange::None;
  bool crack = false;
  bool ko_effect = false;
  bool boosted = false;  // set when Boost already added +1
  int terrain = kNoTerrainChange;
  Symbol spawn_pawn = kNoSymbol;  // sPawn: create this pawn on the tile
  Team spawn_team = Team::None;
  Team owner_team = Team::None;   // stamped by the firing skill
  bool evacuate = false;
  float delay = kNoDelay;
  ProjectileKind projectile = ProjectileKind::None;
  Point projectile_source = kInvalidPoint;
  MoveKind move_kind = MoveKind::Walk;
  std::vector<Point> path;  // movement entries only
  Point grapple_source = kInvalidPoint;
  Symbol item = kNoSymbol;  // sItem: place an item
  std::string script;       // sScript: Lua run before the hit

  bool is_movement() const { return !path.empty(); }
};

struct SkillEffect {
  std::vector<SpaceDamage> effect;    // applied when fired
  std::vector<SpaceDamage> q_effect;  // telegraphed part, applied in the enemy phase
  Point origin = kInvalidPoint;
  Point target = kInvalidPoint;
  int32_t owner = -1;  // firing pawn uid, -1 = none
};

}  // namespace itb
