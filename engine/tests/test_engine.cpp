// Stage 6 integration: shots run end to end, from the game's own weapon Lua
// through the frame-exact executor. Expected boards follow each weapon's Lua
// (file cited per test) and the stage 2-4 rules. Skipped (with a warning)
// without a game install; set ITB_GAME_DIR to point at one.

#include <doctest/doctest.h>

#include <algorithm>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

#include "itb/engine.hpp"
#include "itb/game_data.hpp"
#include "itb/movement.hpp"

using namespace itb;

namespace {

Engine* engine() {
  static Engine* e = [] {
    const auto root = GameData::default_game_root();
    if (root.empty() || !std::filesystem::exists(root / "scripts" / "scripts.lua")) {
      return static_cast<Engine*>(nullptr);
    }
    return Engine::create(root).release();
  }();
  return e;
}

#define NEED_ENGINE()                                                                     \
  if (!engine()) {                                                                        \
    WARN_MESSAGE(false, "no game install found; set ITB_GAME_DIR to run engine tests"); \
    return;                                                                               \
  }                                                                                       \
  Engine& E = *engine()

void set_building(Board& b, Point p, int hp = 1) {
  Tile& t = b.tile(p);
  t.terrain = Terrain::Building;
  t.hp = t.max_hp = static_cast<int8_t>(hp);
  t.populated = true;
}

void set_mountain(Board& b, Point p) {
  Tile& t = b.tile(p);
  t.terrain = Terrain::Mountain;
  t.hp = t.max_hp = 2;
}

// Adds a pawn of this type and returns its uid; squad mechs get the mech flag.
int32_t place(Board& b, const char* type, Point p, bool mech = false) {
  const PawnDef* def = engine()->data().pawn(type);
  REQUIRE_MESSAGE(def != nullptr, type);
  int32_t uid = 0;
  for (const Pawn& q : b.pawns()) uid = std::max(uid, q.uid + 1);
  Pawn pawn = engine()->data().make_pawn(*def, uid, p);
  if (mech) {
    pawn.mech = true;
    pawn.corpse = true;
    pawn.team = Team::Player;
  }
  b.add_pawn(pawn);
  return uid;
}

const Pawn* at(const Board& b, Point p) {
  for (const Pawn& q : b.pawns()) {
    if (q.pos == p && q.alive()) return &q;
  }
  return nullptr;
}

bool gone(const Board& b, int32_t uid) {
  const Pawn* p = b.find_pawn(uid);
  return !p || !p->alive();
}

}  // namespace

TEST_CASE("Engine: Titan Fist pushes into an open tile") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 4}, true);
  const int32_t vek = place(b, "Scorpion1", {3, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  CHECK(r.weapon == "Prime_Punchmech");
  CHECK(r.lua_errors.empty());
  // weapons_prime.lua Prime_Punchmech: 2 damage, push away from the mech.
  CHECK(b.find_pawn(vek)->hp == 1);
  CHECK(b.find_pawn(vek)->pos == Point{3, 2});
  CHECK_FALSE(b.find_pawn(mech)->active);
  CHECK(r.resolve.quiescent);
}

TEST_CASE("Engine: Titan Fist pushes into a unit, a mountain, a building and water") {
  NEED_ENGINE();
  SUBCASE("unit: both take a bump, nobody moves") {
    Board b;
    const int32_t mech = place(b, "PunchMech", {3, 4}, true);
    const int32_t a = place(b, "Scorpion1", {3, 3});
    const int32_t c = place(b, "Scorpion1", {3, 2});
    REQUIRE(E.fire_weapon(b, mech, 0, {3, 3}).ok());
    CHECK(gone(b, a));  // 3 HP: 2 weapon + 1 bump
    CHECK(b.find_pawn(c)->hp == 2);
    CHECK(b.find_pawn(c)->pos == Point{3, 2});
  }
  SUBCASE("mountain: the mountain cracks") {
    Board b;
    const int32_t mech = place(b, "PunchMech", {3, 4}, true);
    const int32_t a = place(b, "Firefly1", {3, 3});
    set_mountain(b, {3, 2});
    REQUIRE(E.fire_weapon(b, mech, 0, {3, 3}).ok());
    CHECK(gone(b, a));
    CHECK(b.tile({3, 2}).hp == 1);
    CHECK(b.tile({3, 2}).terrain == Terrain::Mountain);
  }
  SUBCASE("building: the building falls and the grid drops") {
    Board b;
    b.grid_power = 5;
    const int32_t mech = place(b, "PunchMech", {3, 4}, true);
    const int32_t a = place(b, "Scorpion1", {3, 3});
    b.find_pawn(a)->hp = 4;
    b.find_pawn(a)->max_hp = 4;
    set_building(b, {3, 2});
    REQUIRE(E.fire_weapon(b, mech, 0, {3, 3}).ok());
    CHECK(b.find_pawn(a)->hp == 1);
    CHECK(b.find_pawn(a)->pos == Point{3, 3});
    CHECK(b.tile({3, 2}).hp == 0);
    CHECK(b.grid_power == 4);
  }
  SUBCASE("building resists: Grid Defense is a logged chance node") {
    Board b;
    b.grid_power = 5;
    const int32_t mech = place(b, "PunchMech", {3, 4}, true);
    place(b, "Scorpion1", {3, 3});
    set_building(b, {3, 2});
    ActionOptions o;
    o.grid_resist = [](Point, int) { return true; };
    const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3}, std::nullopt, o);
    REQUIRE(r.ok());
    CHECK(b.grid_power == 5);
    REQUIRE(r.resolve.chances.size() == 1);
    CHECK(r.resolve.chances[0].kind == ChanceKind::GridDefense);
    CHECK(r.resolve.chances[0].outcome == 1);
  }
  SUBCASE("water: a ground Vek drowns") {
    Board b;
    const int32_t mech = place(b, "PunchMech", {3, 4}, true);
    const int32_t a = place(b, "Scorpion1", {3, 3});
    b.tile({3, 2}).terrain = Terrain::Water;
    REQUIRE(E.fire_weapon(b, mech, 0, {3, 3}).ok());
    CHECK(gone(b, a));
  }
}

TEST_CASE("Engine: Artemis Artillery hits the center and pushes the sides") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "ArtiMech", {6, 3}, true);
  const int32_t center = place(b, "Scorpion1", {3, 3});
  const int32_t left = place(b, "Scorpion1", {3, 2});
  const int32_t right = place(b, "Hornet1", {3, 4});
  set_building(b, {2, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  // weapons_base.lua ArtilleryDefault: 1 damage in the center, the four
  // neighbours pushed outwards with DamageOuter 0; buildings take 0.
  CHECK(b.find_pawn(center)->hp == 2);
  CHECK(b.find_pawn(center)->pos == Point{3, 3});
  CHECK(b.find_pawn(left)->pos == Point{3, 1});
  CHECK(b.find_pawn(left)->hp == 3);
  CHECK(b.find_pawn(right)->pos == Point{3, 5});
  CHECK(b.tile({2, 3}).hp == 1);  // the building only gets an air push
  // The flight takes time: the center hit lands after the side pushes start.
  CHECK(r.resolve.end_frame > 10);
}

TEST_CASE("Engine: Tri-Rocket pushes three tiles in a line") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {6, 3}, true);
  b.find_pawn(mech)->weapons[0] = intern("Ranged_Crack");
  const int32_t near = place(b, "Scorpion1", {4, 3});
  const int32_t mid = place(b, "Scorpion1", {3, 3});
  const int32_t far = place(b, "Firefly1", {2, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  // ae_weapons.lua Ranged_Crack: the far tile first, then the target, then
  // the near tile, each 1 damage and a push away from the shooter (left).
  // The far Vek moves first, so the chain shifts one tile with no bumps.
  CHECK(b.find_pawn(far)->pos == Point{1, 3});
  CHECK(b.find_pawn(mid)->pos == Point{2, 3});
  CHECK(b.find_pawn(near)->pos == Point{3, 3});
  CHECK(b.find_pawn(far)->hp == 2);
  CHECK(b.find_pawn(mid)->hp == 2);
  CHECK(b.find_pawn(near)->hp == 2);
}

TEST_CASE("Engine: Grav Well pulls the target towards the mech") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "GravMech", {6, 3}, true);
  const int32_t vek = place(b, "Scorpion1", {2, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {2, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  CHECK(b.find_pawn(vek)->pos == Point{3, 3});
  CHECK(b.find_pawn(vek)->hp == 3);
}

TEST_CASE("Engine: Aerial Bombs leap and bomb the tile flown over") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "JetMech", {5, 3}, true);
  const int32_t vek = place(b, "Scorpion1", {4, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  // weapons_brute.lua Brute_Jetmech: leap to the target, 1 damage and smoke
  // on the tile in between.
  CHECK(b.find_pawn(mech)->pos == Point{3, 3});
  CHECK(r.end == Point{3, 3});
  CHECK(b.find_pawn(vek)->hp == 2);
  CHECK(b.tile({4, 3}).smoke);
  CHECK_FALSE(b.tile({5, 3}).smoke);
}

TEST_CASE("Engine: Rocket Artillery smokes the tile behind the mech") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "RocketMech", {6, 3}, true);
  const int32_t vek = place(b, "Scorpion1", {3, 3});
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  // weapons_ranged.lua Ranged_Rocket: smoke behind, 2 damage and a push.
  CHECK(b.tile({7, 3}).smoke);
  CHECK(b.find_pawn(vek)->hp == 1);
  CHECK(b.find_pawn(vek)->pos == Point{2, 3});
}

TEST_CASE("Engine: Shield Projector shields the target and the tile beyond") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "ScienceMech", {6, 3}, true);
  set_building(b, {3, 3});
  const int32_t ally = place(b, "PunchMech", {2, 3}, true);
  const ActionResult r = E.fire_weapon(b, mech, 1, {3, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  CHECK(r.weapon == "Science_Shield");
  CHECK(b.tile({3, 3}).shield);
  CHECK(b.find_pawn(ally)->shield);
  CHECK_FALSE(b.tile({4, 3}).shield);
}

TEST_CASE("Engine: Repair heals 1 and clears fire and ACID") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 3}, true);
  Pawn& m = *b.find_pawn(mech);
  m.hp = 1;
  m.fire = true;
  m.acid = true;
  const ActionResult r = E.repair(b, mech);
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  const Pawn& after = *b.find_pawn(mech);
  CHECK(after.hp == 2);
  CHECK_FALSE(after.fire);
  CHECK_FALSE(after.acid);
  CHECK_FALSE(after.active);
  // Repair is a self-target skill: other tiles are not in its area.
  Board b2;
  const int32_t m2 = place(b2, "PunchMech", {3, 3}, true);
  CHECK(E.repair(b2, m2, {3, 4}).status == ActionStatus::NotInArea);
}

TEST_CASE("Engine: moves run the Lua Move skill and are checked against its area") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 3}, true);
  b.tile({3, 1}).terrain = Terrain::Water;
  const ActionResult r = E.move(b, mech, {3, 5});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  CHECK(r.weapon == "Move");
  CHECK(b.find_pawn(mech)->pos == Point{3, 5});
  CHECK(b.find_pawn(mech)->moved);
  CHECK(b.find_pawn(mech)->active);
  // A second move is refused, as is a tile out of range.
  CHECK(E.move(b, mech, {3, 4}).status == ActionStatus::CannotAct);
  Board b2;
  const int32_t m2 = place(b2, "PunchMech", {0, 0}, true);
  CHECK(E.move(b2, m2, {7, 7}).status == ActionStatus::NotInArea);
  // A mech (massive) may stop in water.
  Board b3;
  const int32_t m3 = place(b3, "PunchMech", {3, 3}, true);
  b3.tile({3, 2}).terrain = Terrain::Water;
  REQUIRE(E.move(b3, m3, {3, 2}).ok());
  CHECK(b3.find_pawn(m3)->alive());
}

TEST_CASE("Engine: a queued Vek attack fires from the current tile") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 6}, true);
  const int32_t vek = place(b, "Firefly1", {3, 1});
  b.find_pawn(vek)->queued = QueuedShot{0, {3, 1}, {3, 2}};
  const ActionResult r = E.fire_queued(b, vek);
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  CHECK(r.weapon == "FireflyAtk1");
  CHECK_FALSE(b.find_pawn(vek)->queued.active());
  // weapons_enemy.lua FireflyAtk1: a 1-damage projectile down the column.
  CHECK(b.find_pawn(mech)->hp == 2);
  // A stored target that left the area fizzles (and is used up).
  Board b2;
  const int32_t v2 = place(b2, "Firefly1", {3, 1});
  b2.find_pawn(v2)->queued = QueuedShot{0, {3, 1}, {5, 5}};
  CHECK(E.fire_queued(b2, v2).status == ActionStatus::NoEffect);
  CHECK_FALSE(b2.find_pawn(v2)->queued.active());
}

TEST_CASE("Engine: scripts and their writes run against the board mid-resolution") {
  NEED_ENGINE();
  Board b;
  const int32_t vek = place(b, "Scorpion1", {2, 2});
  SkillEffect se;
  se.origin = {0, 0};
  // The first entry moves the Vek; the script then reads where it stands
  // now and writes there.
  se.add_damage(space_damage({2, 2}, 0, Dir::Right));
  SpaceDamage script = space_damage({-1, -1});
  script.delay = kNoDelay;
  script.script =
      "local p = Board:GetPawn(0):GetSpace() "
      "Board:SetTerrain(p + Point(0, 1), TERRAIN_WATER) "
      "Board:GetPawn(0):SetFrozen(true) "
      "Game:ModifyPowerGrid(SERIOUSLY_JUST_ONE)";
  se.add_delay(1.0f);
  se.add_damage(script);
  b.grid_power = 4;
  ActionResult diag;
  E.resolve(b, se, WeaponInfo{}, {}, &diag);
  CHECK(diag.lua_errors.empty());
  CHECK(diag.unapplied.empty());
  CHECK(b.find_pawn(vek)->pos == Point{3, 2});
  CHECK(b.tile({3, 3}).terrain == Terrain::Water);
  CHECK(b.find_pawn(vek)->frozen);
  CHECK(b.grid_power == 5);
}

TEST_CASE("Engine: death effects run through Lua and see the current board") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 4}, true);
  const int32_t vat = place(b, "AcidVat", {3, 3});
  REQUIRE(E.fire_weapon(b, mech, 0, {3, 3}).ok());
  // mission_barrels.lua AcidVat:GetDeathEffect: acid water where it died.
  // The punch kills it and pushes the body; its death is processed once the
  // push ends, so the water appears on the tile it was pushed to.
  CHECK(gone(b, vat));
  CHECK(b.tile({3, 3}).terrain == Terrain::Road);
  CHECK(b.tile({3, 2}).terrain == Terrain::Water);
  CHECK(b.tile({3, 2}).acid);
}

TEST_CASE("Engine: the effect carries the weapon's animations and art") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "ArtiMech", {6, 3}, true);
  const ActionResult r = E.fire_weapon(b, mech, 0, {3, 3});
  REQUIRE(r.ok());
  const auto shot = std::find_if(r.effect.effect.begin(), r.effect.effect.end(), [](const SpaceDamage& sd) {
    return sd.projectile == ProjectileKind::Artillery;
  });
  REQUIRE(shot != r.effect.effect.end());
  CHECK(symbol_name(shot->animation) == "ExploArt1");
  CHECK(symbol_name(shot->art) == "effects/shotup_tribomb_missile.png");
  CHECK(shot->projectile_source == Point{6, 3});
  CHECK(shot->owner_team == Team::Player);
  CHECK(r.effect.owner == mech);
}

TEST_CASE("Engine: refuses what the game refuses") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {3, 4}, true);
  place(b, "Scorpion1", {3, 3});
  CHECK(E.fire_weapon(b, 99, 0, {3, 3}).status == ActionStatus::NoPawn);
  CHECK(E.fire_weapon(b, mech, 2, {3, 3}).status == ActionStatus::NoWeapon);
  CHECK(E.fire_weapon(b, mech, 0, {1, 1}).status == ActionStatus::NotInArea);
  b.find_pawn(mech)->frozen = true;
  CHECK(E.fire_weapon(b, mech, 0, {3, 3}).status == ActionStatus::CannotAct);
  // Without the checks the shot fires anyway (frozen pawns only lose the UI).
  ActionOptions o;
  o.check_legal = false;
  CHECK(E.fire_weapon(b, mech, 0, {3, 3}, std::nullopt, o).ok());
}

TEST_CASE("Engine: a limited weapon fires while it has uses left") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "PunchMech", {2, 2}, true);
  const int32_t vek = place(b, "Scorpion1", {2, 5});
  Pawn& m = *b.find_pawn(mech);
  m.weapons[0] = intern("Brute_Heavyrocket");
  m.uses[0] = 1;
  m.active = true;
  REQUIRE(E.fire_weapon(b, mech, 0, {2, 5}).ok());
  CHECK(b.find_pawn(mech)->uses[0] == 0);
  CHECK(gone(b, vek));  // 3 damage
  b.find_pawn(mech)->active = true;
  CHECK(E.fire_weapon(b, mech, 0, {2, 5}).status == ActionStatus::NoUses);
  // Unlimited (-1) weapons are never counted down.
  b.find_pawn(mech)->uses[0] = -1;
  REQUIRE(E.fire_weapon(b, mech, 0, {2, 5}).ok());
  CHECK(b.find_pawn(mech)->uses[0] == -1);
}

TEST_CASE("Engine: a Burrower hurt by the Laser Mech is underground once the shot settles") {
  // Live 2026-10-10 (m20 Mission_Reactivation, turn 2): Prime_Lasermech from
  // F7 at E7, the beam hits the Burrower at D7 for 2 (3 -> 1). It dives
  // (stage 2 H4) and is off the board in the next snapshot; it stays alive
  // (no kill) and resurfaces in the AI's move.
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "LaserMech", {1, 2}, true);
  const int32_t bur = place(b, "Burrower1", {1, 4});
  const ActionResult r = E.fire_weapon(b, mech, 0, {1, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  const Pawn* p = b.find_pawn(bur);
  REQUIRE(p != nullptr);
  CHECK(p->hp == 1);
  CHECK(p->alive());
  CHECK_FALSE(p->pos.valid());
  CHECK(p->movement.prev_pos == Point{1, 4});
  CHECK(at(b, {1, 4}) == nullptr);
  CHECK(r.resolve.quiescent);
}

TEST_CASE("Engine: a Burrower on a cracked tile takes the laser without diving") {
  NEED_ENGINE();
  Board b;
  const int32_t mech = place(b, "LaserMech", {1, 2}, true);
  const int32_t bur = place(b, "Burrower1", {1, 4});
  b.tile({1, 4}).cracked = true;
  const ActionResult r = E.fire_weapon(b, mech, 0, {1, 3});
  REQUIRE_MESSAGE(r.ok(), to_string(r.status));
  // The tile collapses and the Burrower falls in: no dive.
  CHECK(b.tile({1, 4}).is_chasm());
  CHECK(gone(b, bur));
}
