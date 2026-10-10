#pragma once

// AE pilot experience and level-ups during a battle.
//
// Kill credit (Pawn::ProcessDeath @00886a80): when a non-mech enemy-team pawn
// (team 6, Vek or bot) dies, the game reads the last shooter
// (EventSystem::GetLastShooter: the owner of the last effect Board::ApplyEffect
// started, cleared at the first frame no effect is active). Every such death
// counts as a kill of that shooter ("any_kill_<id>"). If the victim is not
// Minor, it also gives XP equal to its max HP: to the shooter when its id is
// 0-2 (the mechs; "xp_<id>" and "kill_<id>"), otherwise to the whole squad
// ("env_xp").
//
// Pawn::UpdateKills (@008816c0) runs for every pawn in list order on frames
// with no effect active (Board::OnLoop, before Pawn::DetonateCorpse): XP plus 2
// per kill for an Experienced pilot (Extra_XP), then for a mech with kills:
// Adrenaline counts them, Viscera Nanobots heal, KO_Boost boosts.
// BoardPlayer::UpdateXP (@008a6a90) splits env_xp among the living mechs that
// have a pilot at the start of the next frame: each gets env_xp / n, and the
// remainder goes +1 each to a random subset (C random(), a chance node).
//
// Pawn::IncreasePilotXp (@0087c4b0) -> Pilot::IncreaseXP (@0085c340): XP
// toward the next level; at the threshold (Lua Values xp_level_1 = 25,
// xp_level_2 = 50, Pilot::GetMaxXP) the level rises (at most 2) and the XP
// starts again at 0 (Pilot::ResetLevel: the excess is lost). The new skill
// applies at once: the health total is recomputed (Health / Skilled: +2 max
// HP and +2 HP), Opener on the pawn's first turn and Closer on the last turn
// Boost the mech, Conservative gives limited weapons +1 use. Move bonuses
// are read live by Pawn::GetBaseMove (level_skill_move).

#include "itb/board.hpp"

namespace itb {

inline constexpr int kPilotXpLevel1 = 25;  // game.lua Values["xp_level_1"]
inline constexpr int kPilotXpLevel2 = 50;  // game.lua Values["xp_level_2"]
inline constexpr int kPilotMaxLevel = 2;

// XP that completes the given level (Pilot::GetMaxXP: xp_level_<min(level+1, 2)>).
inline int pilot_xp_required(int level) { return level <= 0 ? kPilotXpLevel1 : kPilotXpLevel2; }

// The pawn has a pilot (Pawn::IsPilot).
inline bool has_pilot_record(const Pawn& p) { return p.pilot_level >= 0; }

// A pilot whose XP the engine follows: below the top level, XP recorded.
inline bool tracks_pilot_xp(const Pawn& p) {
  return p.pilot_level >= 0 && p.pilot_level < kPilotMaxLevel && p.pilot_xp >= 0;
}

// The level `p` would reach with `amount` more XP (one level at most).
bool pilot_levels_up(const Pawn& p, int amount);

// Pawn::IncreasePilotXp: adds `amount` XP and applies a level-up's immediate
// effects. Returns true if the pilot leveled up. A dead pawn gains nothing.
bool increase_pilot_xp(Board& board, Pawn& p, int amount);

// The move the pawn's learned level-up skills give now (Pawn::GetBaseMove @00879600):
// Move and Skilled +1, Opener +2 on the pawn's first turn, Closer +2 on the
// last turn, Pain (Masochist) +2 when not at full HP.
int level_skill_move(const Board& board, const Pawn& p);

// The most HP level-ups can still add to `p` (+2 per Health or Skilled skill
// not learned yet), for the solver's mech HP bound.
int pilot_hp_room(const Pawn& p);

}  // namespace itb
