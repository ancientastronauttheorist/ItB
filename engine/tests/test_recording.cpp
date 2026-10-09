#include <doctest/doctest.h>

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "itb/recording.hpp"

using namespace itb;

namespace {
const std::string kFixture = std::string(ITB_FIXTURE_DIR) + "/board_m07_turn01.json";
}

TEST_CASE("loads a recorded bridge board") {
  std::string error;
  auto rec = load_recording(kFixture, nullptr, &error);
  REQUIRE_MESSAGE(rec.has_value(), error);

  CHECK(rec->run_id == "20260713_052159_731");
  CHECK(rec->mission_index == 7);
  CHECK(rec->turn == 1);
  CHECK(rec->mission_id == "Mission_Survive");
  CHECK(rec->phase == "combat_player");

  const Board& b = rec->board;
  CHECK(b.grid_power == 7);
  CHECK(b.grid_power_max == 7);
  CHECK(b.total_turns == 4);
  CHECK(b.pawns().size() == 11);
  REQUIRE(b.spawn_points.size() == 1);
  CHECK(b.spawn_points[0] == Point{6, 4});
  CHECK(rec->attack_order == std::vector<int32_t>{969, 970, 972, 973});

  const Tile& mountain = b.tile(Point{6, 0});
  CHECK(mountain.terrain == Terrain::Mountain);
  CHECK(mountain.hp == 2);
}

TEST_CASE("recorded units keep their live stats and queued attacks") {
  std::string error;
  auto rec = load_recording(kFixture, nullptr, &error);
  REQUIRE(rec.has_value());
  const Board& b = rec->board;

  const Pawn* punch = b.find_pawn(0);
  REQUIRE(punch != nullptr);
  CHECK(symbol_name(punch->type) == "PunchMech");
  CHECK(punch->pos == Point{3, 5});
  CHECK(punch->hp == 6);
  CHECK(punch->max_hp == 6);
  CHECK(punch->mech);
  CHECK(punch->massive);
  CHECK(punch->team == Team::Player);
  // Recorded base move 3, effective move 5.
  CHECK(punch->move == 3);
  CHECK(punch->movement.pilot_bonus == 2);

  const Pawn* digger = b.find_pawn(969);
  REQUIRE(digger != nullptr);
  CHECK(symbol_name(digger->type) == "Digger2");
  CHECK(digger->team == Team::Enemy);
  CHECK(digger->queued.active());
  CHECK(digger->queued.target == Point{4, 3});
  CHECK(symbol_name(digger->weapons[0]) == "DiggerAtk2");

  // Player units come first in the board list.
  CHECK(b.pawns().front().team == Team::Player);
}

TEST_CASE("bridge quirks are corrected on load") {
  const auto path = std::filesystem::temp_directory_path() / "itb_recording_quirks.json";
  {
    std::ofstream out(path);
    out << R"({"tiles": [
        {"x": 1, "y": 1, "terrain": "lava", "terrain_id": 5},
        {"x": 2, "y": 2, "terrain": "lava", "terrain_id": 3, "lava": true},
        {"x": 3, "y": 3, "terrain": "ground", "terrain_id": 0}],
      "units": [
        {"uid": 0, "type": "PunchMech", "x": 3, "y": 3, "hp": 5, "max_hp": 3, "team": 1, "mech": true,
         "move": 0, "base_move": 3, "web": true, "web_source_uid": 9,
         "weapons": ["Prime_Punchmech", "Passive_ForceAmp"], "pilot_id": "Pilot_Rock"},
        {"uid": 9, "type": "Scorpion1", "x": 3, "y": 4, "hp": 3, "max_hp": 3, "team": 6}],
      "teleporter_pairs": [[0, 0, 7, 7]]})";
  }
  std::string error;
  auto rec = load_recording(path, nullptr, &error);
  std::filesystem::remove(path);
  REQUIRE_MESSAGE(rec.has_value(), error);
  const Board& b = rec->board;
  // Bridges before 2026-05-04 named ice (id 5) "lava"; real lava is water + flag.
  CHECK(b.tile({1, 1}).terrain == Terrain::Ice);
  CHECK_FALSE(b.tile({1, 1}).lava);
  CHECK(b.tile({2, 2}).terrain == Terrain::Water);
  CHECK(b.tile({2, 2}).lava);
  const Pawn& mech = *b.find_pawn(0);
  CHECK(mech.max_hp == 5);                   // base Health was reported as max_hp
  CHECK(mech.movement.pilot_bonus == 0);     // GetMoveSpeed() read 0 while webbed
  CHECK(mech.web_tile == Point{3, 4});       // the web comes from the source's tile
  CHECK(b.has_passive(kPassiveForceAmp));    // squad passives from the mechs' weapons
  REQUIRE(rec->pilots.size() == 1);
  CHECK(rec->pilots[0].second == "Pilot_Rock");
  REQUIRE(b.teleporters.size() == 2);
  CHECK(b.teleporters[1] == Point{7, 7});
  CHECK(b.tile({0, 0}).teleporter);
  CHECK(b.teleporter_occupants == std::vector<int32_t>{-1, -1});
}

TEST_CASE("rejects files that are not boards") {
  std::string error;
  auto rec = load_recording(std::string(ITB_FIXTURE_DIR) + "/does_not_exist.json", nullptr, &error);
  CHECK_FALSE(rec.has_value());
  CHECK(error.find("cannot open") != std::string::npos);
}
