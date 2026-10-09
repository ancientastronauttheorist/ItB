#include <doctest/doctest.h>

#include "itb/core.hpp"
#include "itb/symbols.hpp"

using namespace itb;

TEST_CASE("direction vectors match the game's DIR_VECTORS") {
  CHECK(dir_vector(Dir::Up) == Point{0, -1});
  CHECK(dir_vector(Dir::Right) == Point{1, 0});
  CHECK(dir_vector(Dir::Down) == Point{0, 1});
  CHECK(dir_vector(Dir::Left) == Point{-1, 0});
  CHECK(opposite(Dir::Up) == Dir::Down);
  CHECK(opposite(Dir::Right) == Dir::Left);
  CHECK(opposite(Dir::Left) == Dir::Right);
  CHECK(step(Point{3, 3}, Dir::Left) == Point{2, 3});
}

TEST_CASE("visual notation uses row = 8 - x, column = 'H' - y") {
  CHECK(to_visual(Point{3, 5}) == "C5");
  CHECK(to_visual(Point{0, 7}) == "A8");
  CHECK(to_visual(Point{7, 0}) == "H1");
  CHECK(to_visual(kInvalidPoint) == "--");
  for (int i = 0; i < kTileCount; ++i) {
    const Point p = Point::from_index(i);
    CHECK(from_visual(to_visual(p)) == p);
  }
  CHECK(from_visual("c5") == Point{3, 5});
  CHECK_FALSE(from_visual("I1").has_value());
  CHECK_FALSE(from_visual("A9").has_value());
}

TEST_CASE("points index the native [x][y] grid") {
  CHECK(Point{0, 0}.index() == 0);
  CHECK(Point{0, 1}.index() == 1);
  CHECK(Point{1, 0}.index() == 8);
  CHECK_FALSE(Point{8, 0}.valid());
  CHECK_FALSE(Point{0, -1}.valid());
}

TEST_CASE("symbols intern once") {
  const Symbol a = intern("TestSymbolA");
  CHECK(a != kNoSymbol);
  CHECK(intern("TestSymbolA") == a);
  CHECK(find_symbol("TestSymbolA") == a);
  CHECK(symbol_name(a) == "TestSymbolA");
  CHECK(find_symbol("NeverInterned_xyz") == kNoSymbol);
  CHECK(intern("") == kNoSymbol);
}
