// Core value types and game constants.
//
// Numeric values are the ones the game binds into Lua (ActiveLua::BindDefinitions
// in the Linux build 21601364) so that data read from the game's own scripts
// and from bridge recordings can be used without translation.
#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace itb {

inline constexpr int kBoardSize = 8;
inline constexpr int kTileCount = kBoardSize * kBoardSize;

// Board coordinate in the game's native convention (the bridge uses the same
// one). The native grid is indexed [x][y].
struct Point {
  int x = -1;
  int y = -1;

  constexpr Point() = default;
  constexpr Point(int x_, int y_) : x(x_), y(y_) {}

  constexpr bool valid() const {
    return x >= 0 && x < kBoardSize && y >= 0 && y < kBoardSize;
  }
  constexpr int index() const { return x * kBoardSize + y; }
  static constexpr Point from_index(int i) { return {i / kBoardSize, i % kBoardSize}; }

  constexpr Point operator+(Point o) const { return {x + o.x, y + o.y}; }
  constexpr Point operator-(Point o) const { return {x - o.x, y - o.y}; }
  constexpr Point operator*(int k) const { return {x * k, y * k}; }
  constexpr bool operator==(const Point&) const = default;
};

inline constexpr Point kInvalidPoint{-1, -1};

// Directions. UP..LEFT = 0..3 index DIR_VECTORS (confirmed from the static
// initializer that fills DIR_VECTORS from VEC_UP/RIGHT/DOWN/LEFT); NONE = 4 is
// the SpaceDamage iPush default; FLIP = 6 reverses a queued attack.
enum class Dir : int8_t { Up = 0, Right = 1, Down = 2, Left = 3, None = 4, Flip = 6 };

inline constexpr std::array<Point, 4> kDirVectors{{{0, -1}, {1, 0}, {0, 1}, {-1, 0}}};

constexpr bool is_cardinal(Dir d) { return static_cast<int>(d) >= 0 && static_cast<int>(d) < 4; }
constexpr Point dir_vector(Dir d) { return kDirVectors[static_cast<int>(d)]; }
// The native code computes the opposite direction as (d + 2) % 4.
constexpr Dir opposite(Dir d) { return static_cast<Dir>((static_cast<int>(d) + 2) % 4); }
constexpr Point step(Point p, Dir d) { return p + dir_vector(d); }

enum class Terrain : int8_t {
  Road = 0,
  Building = 1,
  Rubble = 2,
  Water = 3,
  Mountain = 4,
  Ice = 5,
  Forest = 6,
  Sand = 7,
  Hole = 9,  // chasm
  // Only meaningful as SpaceDamage::iTerrain requests; tiles store fire/acid
  // as statuses and lava as a flag on water.
  Fire = 11,
  Acid = 12,
  Lava = 14,
};

// Team ids as stored on a pawn (Pawn+0xD0) and used by Pawn::IsTeam queries.
// Mech (4), Bots (8), Any (2, same value as None) and EnemyMajor (-1) are
// query categories rather than stored teams.
enum class Team : int8_t {
  EnemyMajor = -1,
  Player = 1,
  None = 2,
  Mech = 4,
  Enemy = 6,
  Bots = 8,
};

enum class Faction : int8_t { Default = 0, Bots = 1 };  // Default = Vek

// Psion / boss "leader" mutations.
enum class Leader : int8_t {
  None = 0,
  Health = 1,
  Vines = 2,
  Regen = 4,
  Armor = 5,
  Explode = 6,
  Boss = 7,
  Tentacle = 8,
  Spider = 9,
  Fire = 10,
  Boosted = 11,
  Necro = 12,
};

enum class Tier : int8_t { Normal = 0, Alpha = 1, Boss = 2 };

enum class PathProfile : int8_t {
  Ground = 0,
  Flyer = 1,
  Massive = 2,
  Projectile = 3,
  RoadRunner = 4,
  Teleporter = 5,
  Jumper = 6,
  Burrower = 7,
  FinalStep = 8,  // internal: re-checks the last tile of a walk (never a pawn's own profile)
  Phasing = 9,
};

// Special SpaceDamage::iDamage values.
inline constexpr int kDamageZero = 500;    // shows as a hit but deals 0
inline constexpr int kDamageDeath = 1000;  // ignores shields/frozen, kills

// SpaceDamage::fDelay sentinels; positive values are seconds.
inline constexpr float kNoDelay = 0.0f;
inline constexpr float kFullDelay = -1.0f;  // wait until nothing is busy
inline constexpr float kProjDelay = -2.0f;  // wait only for projectiles

// Visual tile names as shown in game and used in project communication:
// row = 8 - x, column letter = 'H' - y. Bridge (3, 5) is "C5".
std::string to_visual(Point p);
std::optional<Point> from_visual(std::string_view name);

}  // namespace itb
