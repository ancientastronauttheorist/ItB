#include "itb/score.hpp"

#include <algorithm>
#include <sstream>

#include "itb/objectives.hpp"

namespace itb {
namespace {

// Structure HP over building tiles. A destroyed building (rubble, or water
// for a building on water) has left the sum with all its HP.
int building_hp(const Board& b) {
  int total = 0;
  for (int i = 0; i < kTileCount; ++i) {
    const Tile& t = b.tile(Point::from_index(i));
    if (t.is_building()) total += std::max<int>(0, t.hp);
  }
  return total;
}

bool on_board_alive(const Pawn* p) { return p && p->alive() && !p->fallen; }

// Tier 4's "Vek": every team-6 pawn that is not neutral, Vek and enemy bots
// alike. Neutral team-6 pawns are mission props (the hacked building, storm
// and shield generators, acid vats, minefield bots) scored as objectives.
bool is_enemy_unit(const Pawn& p) { return p.team == Team::Enemy && !p.neutral && !p.mech; }

// A pawn that retreated (tile_rules retreat: the minor flag set, HP 0) left
// without dying.
bool retreated(const Pawn& p, const Pawn* q) { return q && !p.minor && q->minor && q->hp <= 0 && !q->fallen; }

}  // namespace

std::string Score::describe() const {
  static constexpr const char* kNames[kScoreKeys] = {
      "grid", "bldg_hp", "mechs", "mech_hp", "obj_fail", "obj", "kills", "vek_hp", "position"};
  std::ostringstream out;
  for (int i = 0; i < kScoreKeys; ++i) out << (i ? " " : "") << kNames[i] << "=" << v[i];
  return out.str();
}

// Tier rules (README "Turn score"):
//  1. grid power and building HP: net change, so a gain (none happens mid-turn
//     in shipped missions) counts in the player's favour.
//  2. mechs alive and mech HP over the mechs on the board at the start: net,
//     so a repair or a revived corpse offsets damage (Board:GetMechDamage,
//     which BONUS_MECHS reads, is max HP minus current HP).
//  3. objectives (objectives.hpp).
//  4. enemies killed and enemy HP removed over the enemies alive at the
//     start (spawns of this turn are not scored); net HP, so psion
//     regeneration counts against the player. Retreats are not kills.
//  5. position (objectives.hpp position_terms).
Score score_turn(const Board& before, const Board& after, const TurnContext* ctx, const PhaseResult* phase) {
  Score s;
  s[ScoreKey::GridLost] = after.grid_power - before.grid_power;
  s[ScoreKey::BuildingHpLost] = building_hp(after) - building_hp(before);

  for (const Pawn& p : before.pawns()) {
    const Pawn* q = same_pawn(p, after, phase);
    const int hp0 = on_board_alive(&p) ? p.hp : 0;
    const int hp1 = on_board_alive(q) ? q->hp : 0;
    if (p.mech && p.team == Team::Player) {
      s[ScoreKey::MechsLost] += (hp1 > 0 ? 1 : 0) - (hp0 > 0 ? 1 : 0);
      s[ScoreKey::MechHpLost] += hp1 - hp0;
    } else if (is_enemy_unit(p) && hp0 > 0 && !retreated(p, q)) {
      s[ScoreKey::VekKilled] += hp1 > 0 ? 0 : 1;
      s[ScoreKey::VekHpRemoved] += hp0 - hp1;
    }
  }

  const ObjectiveReport obj = evaluate_objectives(before, after, ctx, phase);
  s[ScoreKey::ObjectivesFailed] = -obj.failed();
  s[ScoreKey::ObjectiveProgress] = obj.progress();
  s[ScoreKey::Position] = position_terms(after).total();
  return s;
}

}  // namespace itb
