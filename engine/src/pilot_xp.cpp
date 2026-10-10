// Pilot experience and level-ups (itb/pilot_xp.hpp).

#include "itb/pilot_xp.hpp"

#include <algorithm>

namespace itb {

namespace {

bool gives_health(int id) {
  return id == static_cast<int>(LevelSkill::Health) || id == static_cast<int>(LevelSkill::Skilled);
}

}  // namespace

bool pilot_levels_up(const Pawn& p, int amount) {
  if (!tracks_pilot_xp(p) || amount <= 0 || !p.alive()) return false;
  return p.pilot_xp + amount >= pilot_xp_required(p.pilot_level);
}

bool increase_pilot_xp(Board& board, Pawn& p, int amount) {
  if (!tracks_pilot_xp(p) || amount <= 0 || !p.alive()) return false;
  const int required = pilot_xp_required(p.pilot_level);
  // ValueBar::Modify keeps the value within [0, max].
  p.pilot_xp = static_cast<int16_t>(std::min(required, p.pilot_xp + amount));
  if (p.pilot_xp < required) return false;

  // Pilot::IncreaseXP: next level, XP back to 0 (Pilot::ResetLevel).
  ++p.pilot_level;
  p.pilot_xp = 0;
  const int skill = p.pilot_level == 1 ? p.pilot_skill1 : p.pilot_skill2;

  // Pawn::ComputeHealthTotal: the learned Health / Skilled bonus raises the
  // maximum, and current HP moves by the same amount (ValueBar::SetMax, then
  // Modify). A Zoltan pilot's mech always has 1.
  if (gives_health(skill) && !p.has_pilot(kPilotZoltan)) {
    p.max_hp = static_cast<int8_t>(p.max_hp + 2);
    p.hp = static_cast<int8_t>(std::min<int>(p.max_hp, p.hp + 2));
  }
  switch (static_cast<LevelSkill>(skill)) {
    case LevelSkill::Opener:
      // Pawn turn count (+0x9ec) 1: the mission's first turn.
      if (p.movement.turn_count == 1) p.boosted = true;
      break;
    case LevelSkill::Closer:
      // Turns remaining (+0x9f0) 1: the last turn.
      if (board.turn == board.total_turns) p.boosted = true;
      break;
    case LevelSkill::Conservative:
      // Skill::ModifyUses(1) on every limited weapon. Pawn::uses cannot tell
      // a used-up limited weapon from an unpowered one (both 0), so only
      // weapons with uses left are raised.
      for (int8_t& u : p.uses) {
        if (u > 0) u = static_cast<int8_t>(std::min(u + 1, 100));
      }
      break;
    case LevelSkill::Thick:
      p.pilot_abilities |= kPilotThick;
      break;
    case LevelSkill::Regen:
      p.pilot_abilities |= kPilotRegen;
      break;
    default:
      // Move / Skilled / Pain move: level_skill_move. Grid (+3 Grid Defense:
      // the odds of a chance the solver takes at its worst), Reactor, Popular,
      // Invulnerable: nothing on the board. Adrenaline counts kills from
      // here on (the battle's earlier kills are not recorded).
      break;
  }
  return true;
}

int level_skill_move(const Board& board, const Pawn& p) {
  if (p.pilot_level < 1) return 0;
  int move = 0;
  if (p.has_level_skill(LevelSkill::Move)) move += 1;
  if (p.has_level_skill(LevelSkill::Skilled)) move += 1;
  if (p.has_level_skill(LevelSkill::Opener) && p.movement.turn_count <= 1) move += 2;
  if (p.has_level_skill(LevelSkill::Closer) && board.turn == board.total_turns) move += 2;
  if (p.has_level_skill(LevelSkill::Pain) && p.hp < p.max_hp) move += 2;
  return move;
}

int pilot_hp_room(const Pawn& p) {
  if (!tracks_pilot_xp(p) || p.has_pilot(kPilotZoltan)) return 0;
  int room = 0;
  if (p.pilot_level < 1 && gives_health(p.pilot_skill1)) room += 2;
  if (p.pilot_level < 2 && gives_health(p.pilot_skill2)) room += 2;
  return room;
}

}  // namespace itb
