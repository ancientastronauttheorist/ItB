// Runs the game's own scripts from the local install. Skipped (with a
// warning) when no install is configured; set ITB_GAME_DIR to point at one.

#include <doctest/doctest.h>

#include <filesystem>

#include "itb/game_data.hpp"

using namespace itb;

namespace {

const GameData* game_data(ScriptLoadReport* report_out = nullptr) {
  static ScriptLoadReport report;
  static const GameData* data = [] {
    const auto root = GameData::default_game_root();
    if (root.empty() || !std::filesystem::exists(root / "scripts" / "scripts.lua")) {
      return static_cast<GameData*>(nullptr);
    }
    return new GameData(GameData::load(root, &report));
  }();
  if (report_out) *report_out = report;
  return data;
}

}  // namespace

TEST_CASE("game scripts load and register pawns") {
  ScriptLoadReport report;
  const GameData* data = game_data(&report);
  if (!data) {
    WARN_MESSAGE(false, "no game install found; set ITB_GAME_DIR to run game-data tests");
    return;
  }
  INFO("scripts ok " << report.files_ok << ", failed " << report.files_failed);
  for (const auto& e : report.errors) MESSAGE(e);
  CHECK(report.files_failed == 0);
  CHECK(report.files_ok > 100);
  // Build 21601364 registers 145 pawns (every live AddPawn in the script list;
  // four more sit inside comment blocks).
  CHECK(data->pawns().size() >= 145);
  // Stubs must only ever replace native bindings, never Lua definitions.
  CHECK(report.overwritten_stubs.empty());
}

TEST_CASE("mech definitions") {
  const GameData* data = game_data();
  if (!data) return;
  const PawnDef* punch = data->pawn("PunchMech");
  REQUIRE(punch != nullptr);
  CHECK(punch->pawn_class == "Prime");
  CHECK(punch->health == 3);
  CHECK(punch->move_speed == 3);
  CHECK(punch->massive);
  CHECK(punch->default_team == Team::Player);
  REQUIRE(punch->skills.size() == 1);
  CHECK(punch->skills[0] == "Prime_Punchmech");
}

TEST_CASE("Vek definitions inherit Pawn defaults") {
  const GameData* data = game_data();
  if (!data) return;
  const PawnDef* firefly = data->pawn("Firefly1");
  REQUIRE(firefly != nullptr);
  CHECK(firefly->health == 3);
  CHECK(firefly->move_speed == 2);
  CHECK(firefly->ranged == 1);
  CHECK(firefly->default_team == Team::Enemy);
  CHECK(firefly->pushable);       // inherited default
  CHECK_FALSE(firefly->flying);   // inherited default
  CHECK_FALSE(firefly->massive);

  const PawnDef* hornet = data->pawn("Hornet1");
  REQUIRE(hornet != nullptr);
  CHECK(hornet->flying);
  CHECK(hornet->large_shield);
  CHECK(hornet->move_speed == 5);
}

TEST_CASE("Advanced Edition and mission-file pawns are present") {
  const GameData* data = game_data();
  if (!data) return;
  const PawnDef* mosquito = data->pawn("Mosquito1");
  REQUIRE(mosquito != nullptr);
  CHECK(mosquito->health == 2);
  CHECK(mosquito->move_speed == 4);
  CHECK(mosquito->flying);
  CHECK(mosquito->default_team == Team::Enemy);
  // Defined in scripts/missions/sand/mission_filler.lua.
  CHECK(data->pawn("Filler_Pawn") != nullptr);
}

TEST_CASE("pawns declared with Pawn:new and derived pawns are discovered") {
  const GameData* data = game_data();
  if (!data) return;
  // `GuardMech = Pawn:new{...}` never calls AddPawn.
  const PawnDef* guard = data->pawn("GuardMech");
  REQUIRE(guard != nullptr);
  CHECK(guard->health == 3);
  CHECK(guard->move_speed == 4);
  CHECK(guard->massive);
  REQUIRE(guard->skills.size() == 1);
  CHECK(guard->skills[0] == "Prime_ShieldBash");

  // Jelly_Explode1 derives from Jelly_Health1, which derives from Pawn.
  const PawnDef* psion = data->pawn("Jelly_Explode1");
  REQUIRE(psion != nullptr);
  CHECK(psion->leader == Leader::Explode);
  CHECK(psion->flying);  // inherited from Jelly_Health1
  CHECK(psion->default_team == Team::Enemy);
}

TEST_CASE("make_pawn copies the definition") {
  const GameData* data = game_data();
  if (!data) return;
  const PawnDef* hornet = data->pawn("Hornet1");
  REQUIRE(hornet != nullptr);
  const Pawn p = data->make_pawn(*hornet, 42, Point{2, 3});
  CHECK(p.uid == 42);
  CHECK(p.pos == Point{2, 3});
  CHECK(p.hp == 2);
  CHECK(p.max_hp == 2);
  CHECK(p.flying);
  CHECK(p.team == Team::Enemy);
  CHECK(symbol_name(p.weapons[0]) == "HornetAtk1");
}
