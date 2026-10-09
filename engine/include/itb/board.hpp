// Board state: 8x8 tiles plus the ordered pawn list.
//
// Everything here is plain data so a Board can be copied cheaply during
// search. Rules live elsewhere; this layer only stores state and preserves the
// orderings the native game relies on.
#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include "itb/core.hpp"
#include "itb/symbols.hpp"

namespace itb {

struct Tile {
  Terrain terrain = Terrain::Road;
  // Structure HP shared by buildings, mountains (2 = intact) and ice
  // (2 = intact, 1 = cracked ice).
  int8_t hp = 0;
  int8_t max_hp = 0;
  // Grid power lost when this building takes damage; 0 = unpopulated.
  int8_t population = 0;
  int8_t shield = 0;        // structure shield count (buildings/mountains)
  bool lava = false;        // natively a flag on a water tile
  bool fire = false;
  bool smoke = false;
  bool acid = false;        // acid pool on the ground (or acid water)
  bool frozen = false;      // frozen structure
  bool cracked = false;     // cracked ground: next weapon hit opens a chasm
  bool vines = false;
  bool pod = false;         // time pod
  int8_t conveyor = -1;     // conveyor direction, -1 = none
  uint8_t walls = 0;        // bit d set = wall on the Dir(d) edge
  Symbol item = kNoSymbol;  // mine / item name
  Symbol unique_building = kNoSymbol;
  Symbol custom_tile = kNoSymbol;

  bool is_building() const { return terrain == Terrain::Building; }
  bool is_mountain() const { return terrain == Terrain::Mountain; }
  bool is_chasm() const { return terrain == Terrain::Hole; }
  bool is_liquid() const { return terrain == Terrain::Water; }  // includes lava
};

struct QueuedShot {
  int8_t weapon = -1;  // index into Pawn::weapons, -1 = no queued attack
  Point origin = kInvalidPoint;
  Point target = kInvalidPoint;

  bool active() const { return weapon >= 0 && target.valid(); }
};

inline constexpr int kMaxWeapons = 4;

struct Pawn {
  int32_t uid = -1;
  Symbol type = kNoSymbol;
  Point pos = kInvalidPoint;
  int8_t hp = 0;
  int8_t max_hp = 0;
  int8_t move = 0;
  Team team = Team::None;
  Faction faction = Faction::Default;
  std::array<Symbol, kMaxWeapons> weapons{};

  // Static traits (copied from the pawn definition, overridable per board).
  bool mech = false;
  bool massive = false;
  bool flying = false;
  bool pushable = true;
  bool armor = false;
  bool ignore_smoke = false;
  bool ignore_fire = false;
  bool minor = false;
  bool corpse = false;  // leaves a corpse (mechs)
  bool burrows = false;
  bool jumper = false;
  bool teleporter = false;
  bool explodes = false;
  bool neutral = false;
  bool mission_critical = false;

  // Status.
  bool active = false;  // can still act this turn
  bool fire = false;
  bool frozen = false;
  bool acid = false;
  bool shield = false;
  bool boosted = false;
  bool webbed = false;
  bool infected = false;
  int32_t web_source = -1;  // uid of the webbing pawn
  QueuedShot queued;

  bool alive() const { return hp > 0; }
  bool controlled() const { return team == Team::Player && !neutral; }
};

class Board {
 public:
  Tile& tile(Point p) { return tiles_[p.index()]; }
  const Tile& tile(Point p) const { return tiles_[p.index()]; }

  // Pawns in the game's board-list order. That order drives Vek attack order,
  // status ticks and same-frame push resolution.
  const std::vector<Pawn>& pawns() const { return pawns_; }
  std::vector<Pawn>& pawns() { return pawns_; }

  // Appends a pawn and regroups the list the way Board::AddPawn does.
  Pawn& add_pawn(const Pawn& pawn);

  Pawn* pawn_at(Point p);
  const Pawn* pawn_at(Point p) const;
  Pawn* find_pawn(int32_t uid);
  const Pawn* find_pawn(int32_t uid) const;

  int grid_power = 7;
  int grid_power_max = 7;
  int grid_defense = 15;  // percent chance a building resists a hit
  int turn = 1;
  int total_turns = 5;
  Leader psion = Leader::None;  // active Vek psion mutation
  std::vector<Point> spawn_points;  // emerging Vek locations

 private:
  std::array<Tile, kTileCount> tiles_{};
  std::vector<Pawn> pawns_;
};

}  // namespace itb
