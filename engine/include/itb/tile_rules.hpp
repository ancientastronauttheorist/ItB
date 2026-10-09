// Stage 2: what one SpaceDamage does to one tile.
//
// Covers the per-tile damage pipeline (Board::DamageSpace and
// BoardSpace::DamageSpace), pawn damage and healing, terrain transitions,
// buildings and grid damage, tile and pawn status setters, terrain dangers and
// the continuous "settle" rules the game runs every frame.
//
// The game is real-time; this engine is turn-step. Things the game finishes in
// later frames are either recorded for a later stage (pushes, spawn requests,
// burrow dives) or completed by `settle` (deferred chasms, drowning, falling,
// acid/fire pickup). Every pawn is treated as not busy. Deaths only set
// `Pawn::dying` (and HP 0); dead pawns stay on the board for stage 3.
//
// Grid Defense is the one random branch here. It is a chance node: each hit on
// a populated building asks `RulesContext::grid_resist`, and every such call is
// logged as a GridDamaged or GridResisted event.
#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "itb/board.hpp"
#include "itb/core.hpp"
#include "itb/space_damage.hpp"
#include "itb/symbols.hpp"

namespace itb {

class GameData;

enum class RulesEventType : uint8_t {
  GridDamaged,        // populated building hit, not resisted: grid -amount
  GridResisted,       // populated building hit resisted (amount = the loss avoided)
  BuildingDamaged,    // building lost `amount` HP (populated or not)
  BuildingDestroyed,  // building reached 0 HP
  TerrainDamaged,     // mountain or ice lost 1 HP
  TerrainChanged,     // amount = new Terrain id
  PawnDamaged,        // pawn `uid` lost `amount` HP
  PawnHealed,         // pawn `uid` gained `amount` HP
  PawnKilled,         // pawn `uid` died (death pending)
  PawnRevived,        // a mech corpse was healed back to life
  PawnFell,           // pawn `uid` fell into a chasm
  PawnBurrowed,       // burrower dove underground (stage 3/7 removes it)
  PawnSpawned,        // sPawn created pawn `uid`
  ItemTriggered,      // `symbol` = the item that went off
  PodDestroyed,
  PodCollected,
};

struct RulesEvent {
  RulesEventType type;
  Point point = kInvalidPoint;
  int32_t uid = -1;
  int amount = 0;
  Symbol symbol = kNoSymbol;
};

// A push started by a SpaceDamage (Pawn::Push). Resolution is stage 3.
// `dir` may be Dir::Flip (reverses the pawn's queued attack).
struct PendingPush {
  int32_t uid = -1;
  Point from = kInvalidPoint;
  Dir dir = Dir::None;
};

// An sPawn that could not be created here (no GameData, or unknown type).
struct SpawnRequest {
  Symbol type = kNoSymbol;
  Point loc = kInvalidPoint;
  Team team = Team::None;  // Team::None = the type's default team
};

struct RulesContext {
  // Pawn definitions for sPawn. Without it, spawns become SpawnRequests.
  const GameData* data = nullptr;

  // Chance node for Grid Defense: called once per hit on a populated building
  // with the grid power at stake; return true if the building resists. Empty =
  // never resists.
  std::function<bool(Point building, int amount)> grid_resist;

  // Optional event log (scoring, chance-node bookkeeping).
  std::vector<RulesEvent>* events = nullptr;

  // Lua sScript hook, called before the hit. Without it, scripts are recorded.
  std::function<void(Board&, const std::string& script, Point loc)> run_script;

  // Name of the shot being resolved (EventSystem::GetLastShot). Train shots
  // ("Train_Move", "Armored_Train_Move") do not collapse cracked tiles.
  Symbol current_shot = kNoSymbol;

  // Preview / event-freeze mode: populated buildings lose HP but no grid.
  bool freeze_events = false;

  // Uid for the next spawned pawn; -1 = one more than the largest uid on board.
  int32_t next_uid = -1;

  // Outputs, in the order they happened.
  std::vector<PendingPush> pushes;
  std::vector<SpawnRequest> spawns;
  std::vector<std::string> scripts;   // sScripts seen while run_script was empty
  std::vector<int32_t> burrow_dives;  // uids that dove (Pawn::Burrow)
};

// ---- Damage pipeline -------------------------------------------------------

// GetDamage: DAMAGE_ZERO reads as 0.
int effective_damage(const SpaceDamage& sd);

// Board::DamageSpace(SD): script, the tile pipeline in weapon mode, then sPawn.
void apply_space_damage(Board& board, const SpaceDamage& sd, RulesContext& ctx);

// BoardSpace::DamageSpace(SD, mode): the ordered per-tile steps.
void damage_tile(Board& board, Point p, SpaceDamage sd, DamageMode mode, RulesContext& ctx);
// Same with an SD whose only field is iDamage = damage (BoardSpace::DamageSpace(int, int)
// and, in weapon mode, Board::DamageSpace(Point, int)).
void damage_tile(Board& board, Point p, int damage, DamageMode mode, RulesContext& ctx);

// Pawn::Damage(SD, mode) and Pawn::Damage(int, mode).
void damage_pawn(Board& board, Pawn& pawn, SpaceDamage sd, DamageMode mode, RulesContext& ctx);
void damage_pawn(Board& board, Pawn& pawn, int damage, DamageMode mode, RulesContext& ctx);

// Pawn::ModifyHealth: raw HP change (negative = damage) with turn shield,
// burrow dive and Retaliation.
void modify_health(Board& board, Pawn& pawn, int delta, DamageMode mode, RulesContext& ctx);

// Pawn::Kill / KillInstant: death pending, HP 0, queued shot cleared. No-op on
// a dead pawn.
void kill_pawn(Board& board, Pawn& pawn, RulesContext& ctx);

// Pawn::Fall: a non-flying (or frozen) pawn drops into the chasm and dies.
void fall_pawn(Board& board, Pawn& pawn, RulesContext& ctx);

// ---- Terrain ----------------------------------------------------------------

// SetTerrain, including the pseudo-ids Fire (11), Acid (12), Lava (14),
// spikes (15) and crack (16).
void set_terrain(Board& board, Point p, int terrain, RulesContext& ctx);
inline void set_terrain(Board& board, Point p, Terrain t, RulesContext& ctx) {
  set_terrain(board, p, static_cast<int>(t), ctx);
}
void damage_terrain(Board& board, Point p, int damage, RulesContext& ctx);  // ice, mountains
void add_building(Board& board, Point p, RulesContext& ctx);  // iTerrain = BUILDING
bool is_populated(const Tile& tile);
bool is_crackable(const Board& board, Point p);
void set_cracked(Board& board, Point p, bool on, RulesContext& ctx);

// ---- Tile statuses ----------------------------------------------------------

void set_tile_fire(Board& board, Point p, bool on, RulesContext& ctx);
void set_tile_smoke(Board& board, Point p, bool on, RulesContext& ctx);
void set_tile_acid(Board& board, Point p, bool on, RulesContext& ctx);
void set_tile_frozen(Board& board, Point p, bool on, RulesContext& ctx);
// SetForceField / RemoveForceField: structure shield, else the first pawn's.
void set_tile_shield(Board& board, Point p, bool on, RulesContext& ctx);
// Tile IsForceField / IsFrozen: the structure's, or the first pawn's.
bool tile_shielded(const Board& board, Point p);
bool tile_frozen(const Board& board, Point p);

// Items (items.lua). The SpaceDamage an item applies when it goes off; unknown
// names give an empty SpaceDamage.
SpaceDamage item_damage(Symbol item);
// ClearItem: remove the tile's item and apply its damage to the tile.
void trigger_item(Board& board, Point p, RulesContext& ctx);

// ---- Pawn statuses ----------------------------------------------------------

void set_pawn_fire(Board& board, Pawn& pawn, bool on);
void set_pawn_frozen(Board& board, Pawn& pawn, bool on);
void set_pawn_acid(Board& board, Pawn& pawn, bool on);
void set_pawn_shield(Board& board, Pawn& pawn, bool on);
void set_pawn_injured(Pawn& pawn, bool on);

// ---- Pawn predicates ---------------------------------------------------------

bool is_vek(const Pawn& pawn);  // IsTeam(7): enemy team, Vek faction
bool mutation_affects(const Board& board, const Pawn& pawn, Leader mutation);
bool is_corpse(const Board& board, const Pawn& pawn);  // leaves / is a corpse
bool counts_as_pawn(const Board& board, const Pawn& pawn);  // alive or corpse
bool is_flying(const Pawn& pawn);   // flying (trait or pilot) and alive
bool is_massive(const Board& board, const Pawn& pawn);
bool is_armored(const Board& board, const Pawn& pawn);
bool is_fire_immune(const Board& board, const Pawn& pawn);
bool is_turn_shielded(const Board& board, const Pawn& pawn);  // Networked Shielding

// ---- Occupants ----------------------------------------------------------------

// The pawns on p (excluding fallen ones), in board-list order.
std::vector<Pawn*> occupants(Board& board, Point p);
// BoardSpace::IsPawnSpace(true): some occupant is alive or a corpse.
bool has_pawn(const Board& board, Point p);
// occ[0]: the first occupant (alive or not), or null.
Pawn* first_occupant(Board& board, Point p);

// ---- Continuous rules ----------------------------------------------------------

// CheckAcidFire: healing smoke, then tile fire/lava, acid pool, spikes.
void check_acid_fire(Board& board, Point p, Pawn& pawn, RulesContext& ctx);
// CheckTerrainDangers: drowning, falling, Fire Boost, item pickup.
void check_terrain_dangers(Board& board, Point p, RulesContext& ctx);

// Runs the per-frame tile and pawn rules (BoardSpace::OnLoop, Pawn::OnLoop)
// over the whole board until nothing changes. Returns the passes used.
int settle(Board& board, RulesContext& ctx);

}  // namespace itb
