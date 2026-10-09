// Turn scoring: strict priority tiers, compared lexicographically.
//
// A Score summarizes how a turn went, comparing the board before the player's
// actions with the board after the enemy phase. Higher is better in every
// tier and an earlier tier always dominates a later one, so "optimal" has one
// exact meaning. Tiers (decided with the project owner):
//
//   1. grid and buildings: grid power lost, then building HP lost
//   2. mech survival:      mechs destroyed, then mech HP lost
//   3. mission objectives: objective failures (stage 8)
//   4. kills and damage:   Vek killed, then Vek HP removed
//   5. position:           end-of-turn position quality (stage 8)
//
// Losses are stored negated so that every component is "larger is better".
#pragma once

#include <array>
#include <compare>
#include <cstdint>
#include <string>

#include "itb/board.hpp"

namespace itb {

struct TurnContext;
struct PhaseResult;

enum class ScoreKey : int {
  GridLost = 0,      // -(grid power lost)
  BuildingHpLost,    // -(building HP lost, populated or not)
  MechsLost,         // -(mechs destroyed)
  MechHpLost,        // -(mech HP lost)
  ObjectivesFailed,  // -(mission/bonus objective failures), stage 8
  ObjectiveProgress, // + objective progress, stage 8
  VekKilled,         // + Vek killed
  VekHpRemoved,      // + Vek HP removed
  Position,          // + position quality, stage 8
  Count,
};

inline constexpr int kScoreKeys = static_cast<int>(ScoreKey::Count);

struct Score {
  std::array<int32_t, kScoreKeys> v{};

  int32_t& operator[](ScoreKey k) { return v[static_cast<int>(k)]; }
  int32_t operator[](ScoreKey k) const { return v[static_cast<int>(k)]; }

  // Lexicographic: the first differing component decides.
  auto operator<=>(const Score&) const = default;
  bool operator==(const Score&) const = default;

  std::string describe() const;
};

// Scores the turn from `before` (start of the player's turn) to `after` (end
// of the enemy phase). `phase` and `ctx` may be null; stage 8 uses them for
// mission objectives.
Score score_turn(const Board& before, const Board& after, const TurnContext* ctx = nullptr,
                 const PhaseResult* phase = nullptr);

}  // namespace itb
