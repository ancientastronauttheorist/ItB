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

// Tile fire state. A forest that catches fire becomes road and keeps burning
// (BurningForest); natively the state values are 0/1/2.
enum class FireState : int8_t { None = 0, Burning = 1, BurningForest = 2 };

enum class PodState : int8_t { None = 0, Present = 1, Destroyed = 2, Collected = 3 };

struct Tile {
  Terrain terrain = Terrain::Road;
  // Structure HP shared by buildings, mountains (2 = intact) and ice
  // (2 = intact, 1 = cracked ice).
  int8_t hp = 0;
  int8_t max_hp = 0;
  bool populated = false;  // plain building costs grid when hit
  bool shield = false;     // structure shield (buildings/mountains)
  bool frozen = false;     // frozen structure (buildings/mountains)
  bool lava = false;       // natively a flag on a water (or ice) tile
  FireState fire = FireState::None;
  bool smoke = false;
  bool acid = false;       // acid pool on the ground (or acid water)
  bool cracked = false;    // cracked ground: next weapon hit opens a chasm
  bool pending_hole = false;  // iTerrain = HOLE applied; becomes a chasm shortly after
  bool vines = false;
  bool spikes = false;     // injures pawns that end on it
  bool building_on_water = false;  // destroyed building leaves water, not rubble
  bool teleporter = false;         // teleporter pad (blocks cracking)
  PodState pod = PodState::None;
  int8_t conveyor = -1;     // conveyor direction, -1 = none
  uint8_t walls = 0;        // bit d set = wall on the Dir(d) edge
  Symbol item = kNoSymbol;  // mine / item name
  Symbol unique_building = kNoSymbol;  // objective building id
  Symbol custom_tile = kNoSymbol;
  Symbol special_tag = kNoSymbol;      // e.g. "supervolcano"

  bool is_building() const { return terrain == Terrain::Building; }
  bool is_mountain() const { return terrain == Terrain::Mountain; }
  bool is_chasm() const { return terrain == Terrain::Hole; }
  bool is_liquid() const { return terrain == Terrain::Water; }  // includes lava
  bool on_fire() const { return fire != FireState::None; }
  bool has_wall(Dir d) const { return (walls >> static_cast<int>(d)) & 1; }

  bool operator==(const Tile&) const = default;
};

struct QueuedShot {
  int8_t weapon = -1;  // index into Pawn::weapons, -1 = no queued attack
  Point origin = kInvalidPoint;
  Point target = kInvalidPoint;

  bool active() const { return weapon >= 0 && target.valid(); }

  bool operator==(const QueuedShot&) const = default;
};

// Pilot abilities that change rules (pilots.lua Skill names in comments).
enum PilotAbility : uint32_t {
  kPilotNone = 0,
  kPilotArmored = 1u << 0,          // Armored
  kPilotThick = 1u << 1,            // Thick: immune to fire and ACID
  kPilotRockSkill = 1u << 2,        // Rock_Skill
  kPilotRetaliation = 1u << 3,      // Retaliation
  kPilotFlying = 1u << 4,           // Flying
  kPilotDisableImmunity = 1u << 5,  // Disable_Immunity
  kPilotFreezeWalk = 1u << 6,       // Freeze_Walk
  kPilotPainImmunity = 1u << 7,     // Pain_Immunity
  kPilotRoadRunner = 1u << 8,       // Road_Runner
  kPilotShifty = 1u << 9,           // Shifty
  kPilotPostMove = 1u << 10,        // Post_Move
  kPilotDoubleShot = 1u << 11,      // Double_Shot
  kPilotYouthMove = 1u << 12,       // Youth_Move
  kPilotArrogantBoost = 1u << 13,   // Arrogant_Boost
};

// Squad passives that change rules. Comments give the Lua weapon name and,
// where it differs, the name the binary checks.
enum Passive : uint32_t {
  kPassiveNone = 0,
  kPassiveForceAmp = 1u << 0,          // Passive_ForceAmp
  kPassiveAutoShield = 1u << 1,        // Passive_AutoShields / "Auto_Shield"
  kPassiveFlameImmune = 1u << 2,       // Passive_FlameImmune / "Flame_Immune"
  kPassiveFireBoost = 1u << 3,         // Passive_FireBoost
  kPassiveHealingSmoke = 1u << 4,      // Passive_HealingSmoke
  kPassivePlayerTurnShield = 1u << 5,  // Passive_PlayerTurnShield
  kPassivePsionLeech = 1u << 6,        // Passive_Leech / "Psion_Leech"
  kPassiveElectricSmoke = 1u << 7,     // Passive_Electric
  kPassiveBurrows = 1u << 8,           // Passive_Burrows
  kPassiveKickoff = 1u << 9,           // Passive_Boosters (Kickoff Boosters)
  kPassiveKickoffUpgraded = 1u << 10,  // Passive_Boosters_A / "Kickoff_Booster_A" (+2 move)
  // Vek Hormones: enemy shots hitting Vek get +1, +2 with either upgrade, +3
  // with both.
  kPassiveFriendlyFire = 1u << 11,     // Passive_FriendlyFire
  kPassiveFriendlyFireA = 1u << 12,    // Passive_FriendlyFire_A
  kPassiveFriendlyFireB = 1u << 13,    // Passive_FriendlyFire_B
  kPassiveFriendlyFireAB = 1u << 14,   // Passive_FriendlyFire_AB
  kPassiveFastDecay = 1u << 15,        // Passive_FastDecay: dead Vek leave forest
  kPassiveVoidShock = 1u << 16,        // Passive_VoidShock (AE)
};

inline constexpr int kMaxWeapons = 4;

// Movement bookkeeping beyond Pawn::move / Pawn::moved (stage 5). Natively
// these are separate pawn fields; the defaults describe a plain pawn.
struct MoveState {
  int8_t bonus_shift = 0;     // >0: replaces the move speed (Shifty 1, Post_Move full move)
  int8_t kickoff_bonus = 0;   // Kickoff Boosters bonus, assigned at turn start
  int8_t pilot_bonus = 0;     // move from the pilot's learned level-up skills
  int8_t turn_count = 0;      // turn starts so far; Youth_Move applies while <= 1
  bool move_upgrade = false;  // powered +1 move upgrade
  bool reset_bonus = false;   // Reset_Bonus pilot after Reset Turn: +2 until next turn start
  bool powered = true;        // unpowered pawns can neither act nor move
  bool undo_ready = false;    // the last player move can still be undone
  Point prev_pos = kInvalidPoint;  // last tile left; an underground burrower resurfaces near it

  bool operator==(const MoveState&) const = default;
};

struct Pawn {
  int32_t uid = -1;
  Symbol type = kNoSymbol;
  Point pos = kInvalidPoint;
  int8_t hp = 0;
  int8_t max_hp = 0;
  int8_t move = 0;  // base move speed (Lua MoveSpeed); bonuses live in `movement`
  Team team = Team::None;
  Faction faction = Faction::Default;
  Leader leader = Leader::None;  // own psion/boss leader type
  std::array<Symbol, kMaxWeapons> weapons{};
  uint32_t pilot_abilities = kPilotNone;

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
  bool burns = false;        // Lua Burns (AE): leaves fire when it dies
  bool ignore_flip = false;  // Lua IgnoreFlip: DIR_FLIP leaves its attack alone
  bool neutral = false;
  bool non_grid = false;
  bool mission_critical = false;

  // Status.
  bool active = false;  // can still act this turn
  bool moved = false;   // has used its move this turn
  bool fire = false;
  bool frozen = false;
  bool acid = false;
  bool shield = false;
  bool boosted = false;
  bool webbed = false;
  bool infected = false;
  bool injured = false;  // loses 1 HP whenever it changes tile
  bool dying = false;    // HP reached 0; death not processed yet
  bool fallen = false;   // fell into a chasm: off the board, never a corpse
  bool retreating = false;  // end-of-mission retreat started (bEvacuate)
  int32_t web_source = -1;  // uid of the webbing pawn
  // When the pawn entered its tile (Board::stamp_arrival). Natively each tile
  // keeps its occupants in arrival order; pawns that share a stamp (0 for
  // boards loaded without that history) fall back to board-list order.
  uint32_t arrival = 0;
  QueuedShot queued;
  MoveState movement;

  bool alive() const { return hp > 0; }
  bool controlled() const { return team == Team::Player && !neutral; }
  bool has_pilot(PilotAbility a) const { return (pilot_abilities & a) != 0; }

  bool operator==(const Pawn&) const = default;
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
  void remove_pawn(int32_t uid);

  // The first pawn standing on p, in tile order (arrival, then list order;
  // a tile rarely holds more than one pawn).
  Pawn* pawn_at(Point p);
  const Pawn* pawn_at(Point p) const;
  // Every pawn standing on p in tile order (corpses and dying pawns can share
  // a tile).
  std::vector<Pawn*> pawns_at(Point p);
  // Records that `pawn` just entered its tile: it goes last in the tile's
  // occupant order.
  void stamp_arrival(Pawn& pawn) { pawn.arrival = ++arrival_clock_; }
  Pawn* find_pawn(int32_t uid);
  const Pawn* find_pawn(int32_t uid) const;

  bool has_passive(Passive p) const { return (passives & p) != 0; }

  bool operator==(const Board&) const = default;

  int grid_power = 7;
  int grid_power_max = 7;
  int grid_defense = 15;  // percent chance a populated building resists a hit
  int turn = 1;
  int total_turns = 5;
  bool player_phase = true;  // false during the enemy phase
  uint32_t passives = kPassiveNone;  // active squad passives
  Leader psion = Leader::None;       // active Vek psion mutation
  std::vector<Point> spawn_points;   // emerging Vek locations

 private:
  std::array<Tile, kTileCount> tiles_{};
  std::vector<Pawn> pawns_;
  uint32_t arrival_clock_ = 0;
};

}  // namespace itb
