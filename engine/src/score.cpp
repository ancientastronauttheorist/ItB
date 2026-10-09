#include "itb/score.hpp"

#include <algorithm>
#include <sstream>

namespace itb {
namespace {

int building_hp(const Board& b) {
  int total = 0;
  for (int i = 0; i < kTileCount; ++i) {
    const Tile& t = b.tile(Point::from_index(i));
    if (t.is_building()) total += t.hp;
  }
  return total;
}

bool is_vek(const Pawn& p) { return p.team == Team::Enemy && p.faction == Faction::Default; }

}  // namespace

std::string Score::describe() const {
  static constexpr const char* kNames[kScoreKeys] = {
      "grid", "bldg_hp", "mechs", "mech_hp", "obj_fail", "obj", "kills", "vek_hp", "position"};
  std::ostringstream out;
  for (int i = 0; i < kScoreKeys; ++i) out << (i ? " " : "") << kNames[i] << "=" << v[i];
  return out.str();
}

// Minimal tiers 1, 2 and 4; stage 8 adds objectives and position.
Score score_turn(const Board& before, const Board& after, const TurnContext*, const PhaseResult*) {
  Score s;
  s[ScoreKey::GridLost] = -(before.grid_power - after.grid_power);
  s[ScoreKey::BuildingHpLost] = -(building_hp(before) - building_hp(after));

  for (const Pawn& p : before.pawns()) {
    const Pawn* q = after.find_pawn(p.uid);
    const int hp_after = q ? q->hp : 0;
    if (p.mech && p.alive()) {
      if (hp_after <= 0) s[ScoreKey::MechsLost] -= 1;
      s[ScoreKey::MechHpLost] -= std::max(0, p.hp - hp_after);
    } else if (is_vek(p) && p.alive()) {
      if (hp_after <= 0) s[ScoreKey::VekKilled] += 1;
      s[ScoreKey::VekHpRemoved] += std::max(0, p.hp - std::max(hp_after, 0));
    }
  }
  return s;
}

}  // namespace itb
