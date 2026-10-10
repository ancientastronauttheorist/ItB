#include <doctest/doctest.h>

#include <vector>

#include "itb/board.hpp"

using namespace itb;

namespace {

Pawn make(int32_t uid, Team team, bool neutral = false, Faction faction = Faction::Default,
          const char* type = "Test") {
  Pawn p;
  p.uid = uid;
  p.type = intern(type);
  p.team = team;
  p.neutral = neutral;
  p.faction = faction;
  p.hp = p.max_hp = 1;
  p.pos = Point{uid % kBoardSize, (uid / kBoardSize) % kBoardSize};
  return p;
}

std::vector<int32_t> uids(const Board& b) {
  std::vector<int32_t> out;
  for (const Pawn& p : b.pawns()) out.push_back(p.uid);
  return out;
}

}  // namespace

TEST_CASE("pawn list regroups like Board::AddPawn") {
  Board b;
  b.add_pawn(make(1, Team::Enemy));
  b.add_pawn(make(2, Team::Player));                          // controlled mech
  b.add_pawn(make(3, Team::Enemy));
  b.add_pawn(make(4, Team::Player, /*neutral=*/true));        // e.g. a neutral player unit
  b.add_pawn(make(5, Team::Player, true, Faction::Bots));     // bots faction
  b.add_pawn(make(6, Team::Player));                          // controlled
  b.add_pawn(make(7, Team::None));                            // non-player, insertion order
  b.add_pawn(make(8, Team::Player, true, Faction::Default, "Filler_Pawn"));

  // Pass 0: controlled, bots, Filler_Pawn. Pass 1: non-player. Pass 2: rest.
  CHECK(uids(b) == std::vector<int32_t>{2, 5, 6, 8, 1, 3, 7, 4});
}

TEST_CASE("add_pawn returns the inserted pawn") {
  Board b;
  b.add_pawn(make(1, Team::Enemy));
  Pawn& mech = b.add_pawn(make(2, Team::Player));
  CHECK(mech.uid == 2);
  mech.hp = 3;
  CHECK(b.find_pawn(2)->hp == 3);
}

TEST_CASE("lookup by position and uid") {
  Board b;
  Pawn p = make(9, Team::Enemy);
  p.pos = Point{4, 2};
  b.add_pawn(p);
  REQUIRE(b.pawn_at(Point{4, 2}) != nullptr);
  CHECK(b.pawn_at(Point{4, 2})->uid == 9);
  CHECK(b.pawn_at(Point{2, 4}) == nullptr);
  CHECK(b.find_pawn(9) != nullptr);
  CHECK(b.find_pawn(10) == nullptr);
}

TEST_CASE("a multi-tile pawn is found on its extra tile too") {
  Board b;
  Pawn dam = make(9, Team::None);
  dam.pos = Point{4, 0};
  dam.extra_dx = 1;  // Dam_Pawn ExtraSpaces {Point(1,0)}
  b.add_pawn(dam);
  Pawn v = make(10, Team::Enemy);
  v.pos = Point{4, 1};
  b.add_pawn(v);
  const Pawn& d = *b.find_pawn(9);
  CHECK(d.multi_tile());
  CHECK(d.extra_tile() == Point{5, 0});
  CHECK(d.occupies(Point{4, 0}));
  CHECK(d.occupies(Point{5, 0}));
  CHECK_FALSE(d.occupies(Point{3, 0}));
  REQUIRE(b.pawn_at(Point{5, 0}) != nullptr);
  CHECK(b.pawn_at(Point{5, 0})->uid == 9);
  CHECK(b.pawns_at(Point{5, 0}).size() == 1);
  CHECK(b.pawn_at(Point{5, 1}) == nullptr);
  // One-tile pawns and pawns off the board have no extra tile.
  CHECK_FALSE(b.find_pawn(10)->multi_tile());
  CHECK(b.find_pawn(10)->extra_tile() == kInvalidPoint);
  Pawn off = dam;
  off.pos = kInvalidPoint;
  CHECK(off.extra_tile() == kInvalidPoint);
  CHECK_FALSE(off.occupies(Point{0, -1}));
}

TEST_CASE("tiles default to empty road") {
  Board b;
  const Tile& t = b.tile(Point{0, 0});
  CHECK(t.terrain == Terrain::Road);
  CHECK(t.hp == 0);
  CHECK(t.item == kNoSymbol);
  b.tile(Point{7, 7}).terrain = Terrain::Mountain;
  CHECK(b.tile(Point{7, 7}).is_mountain());
}

TEST_CASE("new pawn uids never reuse a removed pawn's uid") {
  Board b;
  b.add_pawn(make(3, Team::Enemy));
  b.add_pawn(make(7, Team::Enemy));
  CHECK(b.next_uid == 8);
  b.remove_pawn(7);
  CHECK(b.next_uid == 8);  // a later spawn gets 8, not 7 again
  b.add_pawn(make(b.next_uid++, Team::Enemy));
  CHECK(b.next_uid == 9);
}
