#include "itb/board.hpp"

#include <algorithm>

namespace itb {
namespace {

// Board::AddPawn rebuilds the list in three passes, each keeping the previous
// relative order:
//   0: controlled player units, bots-faction player units, and Filler_Pawn
//   1: every non-player-team pawn (Vek, neutrals, structures)
//   2: the remaining (neutral) player-team units
int list_pass(const Pawn& p) {
  if (p.team != Team::Player) return 1;
  static const Symbol filler = intern("Filler_Pawn");
  if (!p.neutral || p.faction == Faction::Bots || p.type == filler) return 0;
  return 2;
}

}  // namespace

Pawn& Board::add_pawn(const Pawn& pawn) {
  pawns_.push_back(pawn);
  const int32_t uid = pawn.uid;
  std::stable_sort(pawns_.begin(), pawns_.end(), [](const Pawn& a, const Pawn& b) {
    return list_pass(a) < list_pass(b);
  });
  // The appended pawn is the last one in its pass.
  for (auto it = pawns_.rbegin(); it != pawns_.rend(); ++it) {
    if (it->uid == uid && list_pass(*it) == list_pass(pawn)) return *it;
  }
  return pawns_.back();  // unreachable
}

void Board::remove_pawn(int32_t uid) {
  std::erase_if(pawns_, [uid](const Pawn& p) { return p.uid == uid; });
}

std::vector<Pawn*> Board::pawns_at(Point p) {
  std::vector<Pawn*> out;
  for (Pawn& pawn : pawns_) {
    if (pawn.pos == p) out.push_back(&pawn);
  }
  return out;
}

Pawn* Board::pawn_at(Point p) {
  for (Pawn& pawn : pawns_) {
    if (pawn.pos == p) return &pawn;
  }
  return nullptr;
}

const Pawn* Board::pawn_at(Point p) const {
  return const_cast<Board*>(this)->pawn_at(p);
}

Pawn* Board::find_pawn(int32_t uid) {
  for (Pawn& pawn : pawns_) {
    if (pawn.uid == uid) return &pawn;
  }
  return nullptr;
}

const Pawn* Board::find_pawn(int32_t uid) const {
  return const_cast<Board*>(this)->find_pawn(uid);
}

}  // namespace itb
