// Stage 7: mission environments and mission combat hooks.
//
// In game a mission is a Lua object (GAME.Missions[k]) with a LiveEnvironment
// (Env_Airstrike, Env_Tides, ...). The enemy phase drives both through a few
// Lua calls: IsEnvironmentEffect / ApplyEnvironmentEffect (the environment
// steps), BaseUpdate (every frame: UpdateMission hooks such as the dam flood
// or the acid storm), NextTurn with the enemy team, and IsEndBlocked.
// `Environment` is that interface. The native implementations
// (make_native_environment) rebuild the mission's state from what the bridge
// recorded; a Lua-backed implementation that runs the real mission scripts can
// replace them behind the same interface once the bridge exports the mission
// instance (stage 7 spec section 4).
//
// Where the recorded data does not pin the behaviour down, an environment
// says so (PhaseEventType::EnvInexact / EnvUnsupported) or, for hidden random
// choices, asks the chance-node resolver (EnvHost::choose).
#pragma once

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "itb/board.hpp"
#include "itb/executor.hpp"
#include "itb/space_damage.hpp"
#include "itb/tile_rules.hpp"

namespace itb {

class GameData;

// ---- What the bridge recorded about the mission -----------------------------

// One environment_danger_v2 row: Board:IsEnvironmentDanger(p) with the
// bridge's guesses about it. Only the tile is trusted: damage and kill come
// from bridge heuristics (wind is tagged damage 1, old bridges mislabel
// Mission_Crack and Terratide), so environments dispatch on the mission id.
struct DangerTile {
  Point p = kInvalidPoint;
  int damage = 1;
  bool kill = true;
  int flying_immune = -1;  // -1: not recorded
};

// Env_Volcano / Env_Final instance state (bridge mission_final_volcano /
// mission_final_cave): the ordered Locations the next steps strike.
struct FinalEnvState {
  bool complete = false;
  int mode = 0;   // 1 rocks, 2 lava (tentacles in the cave)
  int phase = 0;  // 1..4
  bool instant = false;
  std::vector<Point> locations;
};

struct MissionData {
  std::string mission_id;  // M.ID: what environments dispatch on
  std::string env_type;    // the bridge's heuristic label (informational only)
  std::vector<DangerTile> danger;  // in the bridge's scan order (y, then x)
  std::vector<Point> freeze;       // Ice Storm tiles (environment_freeze)
  std::optional<int> tides_index;  // Env_Tides / Env_Terratide Index
  std::optional<Dir> wind_dir;     // Env_RandomWind WindDir
  std::optional<FinalEnvState> volcano;     // Mission_Final
  std::optional<FinalEnvState> final_cave;  // Mission_Final_Cave
  // Ordered Env_Attack Locations when known (e.g. a future bridge export of
  // the env instance); empty = only the danger tiles are known.
  std::vector<Point> ordered_locations;
  int32_t hacking_bot = -1;       // Mission_Hacking BotID
  int32_t hacking_building = -1;  // Mission_Hacking HackID
  std::optional<bool> infinite_spawn;
  std::vector<int32_t> launching;  // satellite rockets with a queued launch
  int difficulty = -1;
};

// ---- Events ----------------------------------------------------------------------

enum class PhaseEventType : uint8_t {
  EndTurn,         // player-team pawns ended their turn (Pawn::EndTurn)
  WebsCleared,     // Board::NextTurn(6) released `amount` webbed pawns
  StatusTick,      // pawn `uid` ticked in phase `amount` (detail: what it did)
  EnvStep,         // the environment applied step `amount` (detail: what)
  EnvInexact,      // the recorded data does not pin this down (detail: why)
  EnvUnsupported,  // no native implementation for what was recorded
  MissionHook,     // a mission hook changed the board (detail: which)
  ShotFired,       // pawn `uid` fired its queued attack at `point`
  ShotFizzled,     // pawn `uid`'s queued target left its target area
  ShotCancelled,   // pawn `uid` lost its queued attack before firing
  Burrowed,        // pawn `uid` dove underground (off the board until the AI moves)
  MissionEnd,      // state 2: the mission ended (no spawns, no AI)
  SpawnEmerged,    // a Vek emerged at `point` (uid -1: type unknown, no pawn added)
  SpawnBlocked,    // the spawn at `point` was blocked (by `uid`, -1: terrain)
  SpawnDropped,    // the spawn at `point` was removed (tile became water/chasm)
  Thawed,          // Mission_Reactivation thawed `uid`
};

const char* to_string(PhaseEventType t);

struct PhaseEvent {
  PhaseEventType type;
  Point point = kInvalidPoint;
  int32_t uid = -1;
  int amount = 0;
  std::string detail;
};

// ---- The interface -----------------------------------------------------------------

// What an environment step or mission hook may do. Mirrors the Lua calls
// shipped missions make: Board:AddEffect, direct board edits (SetAcid,
// SetShield, AddPawn, RemovePawn, ...) and random draws.
class EnvHost {
 public:
  virtual ~EnvHost() = default;
  virtual Board& board() = 0;
  virtual const GameData& data() const = 0;
  // Stage 2 context for direct rule edits (set_pawn_acid, set_terrain, ...).
  virtual RulesContext& rules() = 0;
  // Board:AddEffect: append to the stacked effects (FULL_DELAY).
  virtual void add_effect(SkillEffect effect) = 0;
  // A hidden choice (Lua RNG, or state the bridge does not record): returns
  // a branch in [0, options), logged as a chance node. `options` <= 1 -> 0.
  virtual int choose(ChanceKind kind, int options, Point where = kInvalidPoint, int amount = 0) = 0;
  virtual void note(PhaseEventType type, std::string detail, Point where = kInvalidPoint,
                    int32_t uid = -1, int amount = 0) = 0;
  // A uid for a pawn a hook adds (Board:AddPawn).
  virtual int32_t new_uid() = 0;
  // Board:IsBusy() right now (some hooks only run on an idle board).
  virtual bool busy() const = 0;
  // Game:GetTurnCount().
  virtual int turn() const = 0;
};

class Environment {
 public:
  virtual ~Environment() = default;
  // The Lua class (and mission) this implements, e.g. "Env_Tides".
  virtual std::string name() const = 0;
  // Once, at End Turn, before anything resolves: recorded state the bridge
  // leaves implicit (e.g. the train's queued move) is filled in here.
  virtual void begin(EnvHost&) {}
  // Mission:IsEnvironmentEffect(), read once at the start of the enemy phase.
  virtual bool is_effect(EnvHost&) { return false; }
  // Mission:ApplyEnvironmentEffect(): queue this step's effects (add_effect);
  // returns true if another step follows.
  virtual bool apply(EnvHost&) { return false; }
  // Mission:BaseUpdate() (UpdateMission), every simulated frame.
  virtual void update(EnvHost&) {}
  // Mission:BaseNextTurn() with TEAM_ENEMY, in state 2 before the spawns.
  virtual void next_turn(EnvHost&) {}
  // Mission:IsEndBlocked().
  virtual bool end_blocked(EnvHost&) { return false; }
};

// The native implementation for a recorded mission (dispatch on mission_id;
// see the README's environment table for what is exact).
std::unique_ptr<Environment> make_native_environment(const MissionData& mission);

}  // namespace itb
