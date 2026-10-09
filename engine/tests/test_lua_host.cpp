// Runs the game's own weapon and death-effect scripts through the Lua host
// (stage 6). Expected values are read off each weapon's Lua (file/function
// cited per test). Skipped (with a warning) when no game install is
// configured; set ITB_GAME_DIR to point at one.

#include <doctest/doctest.h>

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

#include "itb/game_data.hpp"
#include "itb/lua_host.hpp"
#include "itb/movement.hpp"

using namespace itb;

namespace {

struct Game {
  const GameData* data = nullptr;
  LuaHost* host = nullptr;
  LuaHostReport report;
};

Game& game() {
  static Game g = [] {
    Game out;
    const auto root = GameData::default_game_root();
    if (root.empty() || !std::filesystem::exists(root / "scripts" / "scripts.lua")) return out;
    out.data = new GameData(GameData::load(root));
    out.host = LuaHost::create(root, {}, &out.report).release();
    return out;
  }();
  return g;
}

#define NEED_GAME()                                                                        \
  Game& G = game();                                                                        \
  if (!G.host) {                                                                           \
    WARN_MESSAGE(false, "no game install found; set ITB_GAME_DIR to run Lua host tests"); \
    return;                                                                                \
  }                                                                                        \
  LuaHost& H = *G.host

Board empty_board() {
  Board b;
  b.turn = 1;
  return b;
}

void set_building(Board& b, Point p) {
  Tile& t = b.tile(p);
  t.terrain = Terrain::Building;
  t.hp = t.max_hp = 1;
  t.populated = true;
}

void set_mountain(Board& b, Point p) {
  Tile& t = b.tile(p);
  t.terrain = Terrain::Mountain;
  t.hp = t.max_hp = 2;
}

// Adds a pawn of this type; returns its uid (Board references move when the
// pawn list grows).
int32_t place(Board& b, const char* type, Point p, bool mech = false) {
  const PawnDef* def = game().data->pawn(type);
  REQUIRE_MESSAGE(def != nullptr, type);
  int32_t uid = 0;
  for (const Pawn& q : b.pawns()) uid = std::max(uid, q.uid + 1);
  Pawn pawn = game().data->make_pawn(*def, uid, p);
  if (mech) {
    pawn.mech = true;
    pawn.team = Team::Player;
  }
  b.add_pawn(pawn);
  return uid;
}

const Pawn& pawn(const Board& b, int32_t uid) { return *b.find_pawn(uid); }

std::vector<Point> pts(std::initializer_list<Point> l) { return l; }

// Runs a Lua chunk; the chunk signals failure with error()/assert().
void lua_ok(LuaHost& h, const Board& b, const char* code) {
  const LuaCall c = h.run_script(b, code);
  INFO(code);
  CHECK_MESSAGE(c.ok, c.error);
}

// Runs a Lua chunk that must raise; returns the message.
std::string lua_error(LuaHost& h, const Board& b, const char* code) {
  const LuaCall c = h.run_script(b, code);
  INFO(code);
  CHECK_FALSE(c.ok);
  return c.error;
}

// A board with a Punch mech at (3,4), a Firefly at (3,1) and some terrain.
struct Scene {
  Board b = empty_board();
  int32_t mech = -1;
  int32_t vek = -1;
};

Scene punch_scene(const char* mech_type = "PunchMech") {
  Scene s;
  s.mech = place(s.b, mech_type, {3, 4}, true);
  s.vek = place(s.b, "Firefly1", {3, 1});
  return s;
}

}  // namespace

// ---- runtime rules ---------------------------------------------------------------

TEST_CASE("Lua host: scripts load with every native bound") {
  NEED_GAME();
  for (const auto& e : G.report.errors) MESSAGE(e);
  CHECK(G.report.errors.empty());
  CHECK(G.report.files_ok > 100);
  CHECK(G.report.overwritten_stubs.empty());
  // Only UI/campaign classes are left to inert stubs.
  for (const std::string& name : G.report.stubbed_globals) {
    CHECK_MESSAGE((name == "TipData" || name == "PilotSkill" || name == "GetMechColorsInTexture" ||
                   name == "Button" || name == "Text" || name == "StyleInfo" || name == "JoyRumble" ||
                   name == "RegionInfo"),
                  name);
  }
}

TEST_CASE("Lua host: rand() is glibc's TYPE_3 stream") {
  NEED_GAME();
  H.seed(1);
  CHECK(H.rand() == 1804289383);
  CHECK(H.rand() == 846930886);
  CHECK(H.rand() == 1681692777);
  H.seed(0);  // glibc treats seed 0 as 1
  CHECK(H.rand() == 1804289383);
  H.seed(42);
  const int first = H.rand();
  H.seed(42);
  CHECK(H.rand() == first);
  // random_int(n) = rand() % n; random_int(a, b) = a + rand() % (b - a).
  const Board b = empty_board();
  H.seed(1);
  lua_ok(H, b, "assert(random_int(10) == 1804289383 % 10)");
  lua_ok(H, b, "assert(random_int(5, 9) == 5 + 846930886 % 4)");
  lua_ok(H, b, "assert(random_int(0) == 0 and random_int(7, 7) == 7)");
  lua_error(H, b, "random_bool(0)");
}

TEST_CASE("Lua host: Point follows the native bindings") {
  NEED_GAME();
  const Board b = empty_board();
  lua_ok(H, b, "local p = Point() assert(p.x == -2147483647 and p.y == -2147483647)");
  lua_ok(H, b, "assert(Point(3, 4):GetString() == 'Point( 3, 4 )')");
  lua_ok(H, b, "assert(Point(-1, 2):GetLuaString() == 'Point( -1, 2 )')");
  lua_ok(H, b, "assert(Point(2.9, -1.5) == Point(2, -1))");  // lua_tointeger truncation
  lua_ok(H, b, "assert(Point(1, 2) + Point(3, 4) == Point(4, 6) and Point(1, 2) - Point(3, 4) == Point(-2, -2))");
  lua_ok(H, b, "assert(Point(1, -2) * 3 == Point(3, -6))");
  lua_ok(H, b, "assert(Point(1, 2):Manhattan(Point(4, 0)) == 5)");
  lua_ok(H, b, "assert(Point(1, 2) ~= Point(2, 1) and Point(1, 2) ~= nil and Point(1, 2) ~= 5)");
  lua_ok(H, b, "local q = Point(Point(5, 6)) assert(q.x == 5 and q.y == 6)");
  lua_ok(H, b, "assert(VEC_UP == Point(0, -1) and VEC_RIGHT == Point(1, 0) and VEC_DOWN == Point(0, 1))");
  lua_ok(H, b, "assert(VEC_LEFT == Point(-1, 0) and VEC_RIGHT_UP == nil and VEC_LEFT_DOWN == nil)");
  // Not registered natively.
  CHECK(lua_error(H, b, "local x = Point(1, 1) + 5").find("No matching overload") != std::string::npos);
  CHECK(lua_error(H, b, "local x = 2 * Point(1, 1)").find("No matching overload") != std::string::npos);
  CHECK(lua_error(H, b, "local x = -Point(1, 1)").find("No such operator") != std::string::npos);
  CHECK(lua_error(H, b, "local x = tostring(Point(1, 1))").find("No such operator") != std::string::npos);
  lua_error(H, b, "local x = Point(1, 1):Length()");
  lua_error(H, b, "local x = Point('1', 2)");  // numeric strings are rejected
  // Unknown fields live on the Lua side of the instance only.
  lua_ok(H, b, "local p = Point(1, 1) p.foo = 3 assert(p.foo == 3 and Point(1, 1).foo == nil)");
  // Points are not interned: table keys go by identity.
  lua_ok(H, b, "local t = {} t[Point(1, 2)] = 1 assert(t[Point(1, 2)] == nil)");
}

TEST_CASE("Lua host: constants match the binary's registrations") {
  NEED_GAME();
  const Board b = empty_board();
  lua_ok(H, b, "assert(UNPOPULATED == 0 and POPULATED == 1 and TOTAL == 2)");
  lua_ok(H, b, "assert(POPULATED_TRUE == nil and POPULATED_FALSE == nil and SECRET_SQUAD == nil)");
  lua_ok(H, b, "assert(SQUAD_SECRET == 10 and DIR_START == 0 and DIR_END == 3 and DIR_TOTAL == 4 and DIR_ANY == 4)");
  lua_ok(H, b, "assert(TEAM_ANY == 2 and TEAM_NONE == 2 and TEAM_ENEMY_MAJOR == -1 and TEAM_BOTS == 8)");
  lua_ok(H, b, "assert(SERIOUSLY_JUST_ONE == 3626 and INT_MAX == 2147483647 and INVALID_NODE == 4294967295)");
  lua_ok(H, b, "assert(EFFECT_DEADLY == true and EFFECT_WARNING == false and NULL == 0)");
  lua_ok(H, b, "assert(ANIM_NO_DELAY == 1 and ANIM_DELAY == 2 and ANIM_REVERSE == 4 and FADE_IN == 0)");
  lua_ok(H, b, "assert(REWARD_TECH == 2 and OBJ_COMPLETE == 2 and EVENT_REPAIR_UNDO == 73 and SEX_AI == 4)");
  lua_ok(H, b, "assert(PAWN_FACTORY ~= nil and COLOR_WHITE ~= nil and ALIGN_CENTER_ALL == 3)");
}

TEST_CASE("Lua host: SpaceDamage constructors, fields and strict conversions") {
  NEED_GAME();
  const Board b = empty_board();
  lua_ok(H, b,
         "local d = SpaceDamage() assert(d.loc == Point(-1, -1) and d.iDamage == 0 and d.iPush == 4)"
         " assert(d.iTerrain == 10 and d.iPawnTeam == 2 and d.fDelay == 0 and d.sAnimation == '')");
  lua_ok(H, b, "local d = SpaceDamage(3) assert(d.iDamage == 3 and d.loc == Point(-1, -1))");
  lua_ok(H, b, "local d = SpaceDamage(Point(1, 2)) assert(d.loc == Point(1, 2) and d.iDamage == 0)");
  lua_ok(H, b, "local d = SpaceDamage(Point(1, 2), 2) assert(d.iDamage == 2 and d.iPush == 4)");
  lua_ok(H, b, "local d = SpaceDamage(Point(1, 2), 2, 3) assert(d.iDamage == 2 and d.iPush == 3)");
  lua_ok(H, b, "local d = SoundEffect(Point(1, 2), 'boom') assert(d.loc == Point(1, 2) and d.sSound == 'boom')");
  lua_error(H, b, "local d = SpaceDamage(Point(1, 2), true)");
  lua_error(H, b, "local d = SpaceDamage() d.iDamage = '3'");
  lua_error(H, b, "local d = SpaceDamage() d.sAnimation = 5");
  lua_error(H, b, "local d = SpaceDamage() d.bHide = 1");
  // loc is a reference into the SpaceDamage; the setter copies.
  lua_ok(H, b, "local d = SpaceDamage(Point(1, 1)) d.loc.x = 5 assert(d.loc == Point(5, 1))");
  lua_ok(H, b, "local d = SpaceDamage(Point(1, 1)) local l = d.loc d.loc = Point(4, 4) assert(l == Point(4, 4))");
  lua_ok(H, b, "local p = Point(1, 1) local d = SpaceDamage(p) p.x = 7 assert(d.loc == Point(1, 1))");
  lua_ok(H, b,
         "local d = SpaceDamage() assert(not d:IsMovement() and d:MoveStart() == Point(-1, 1))");
}

TEST_CASE("Lua host: SkillEffect references alias the stored entries") {
  NEED_GAME();
  const Board b = empty_board();
  lua_ok(H, b,
         "local se = SkillEffect() local d = SpaceDamage(Point(1, 1), 1) se:AddDamage(d)"
         " d.iDamage = 9 assert(se:GetDamage(1).iDamage == 1)"  // AddDamage copies
         " se:GetDamage(1).iDamage = 3 assert(se.effect:index(1).iDamage == 3)"
         " se.effect:index(1).loc.y = 6 assert(se:GetDamage(1).loc == Point(1, 6))"
         " assert(se:GetDamageCount() == 1 and se.effect:size() == 1 and se.q_effect:empty())"
         " se.effect:push_back(SpaceDamage(2)) assert(se:GetDamageCount() == 2)"
         " assert(se.effect:back().iDamage == 2)"
         " se.piOrigin.x = 4 assert(se.piOrigin.x == 4 and se.iOwner == -1)");
  lua_ok(H, b,
         "local l = PointList() l:push_back(Point(1, 1)) l:push_back(Point(2, 2)) l:push_back(Point(3, 3))"
         " assert(l:size() == 3 and l:index(1) == Point(1, 1) and l:back() == Point(3, 3))"
         " l:erase(2) assert(l:size() == 2 and l:index(2) == Point(3, 3))"
         " local i = IntList() i:push_back(4) assert(i:index(1) == 4 and not i:empty())");
  lua_error(H, b, "local l = PointList() l:index(1)");  // undefined in game
  lua_error(H, b, "local se = SkillEffect() se:AddLeap(Point(1, 1), Point(2, 2), FULL_DELAY)");
}

TEST_CASE("Lua host: SkillEffect adders build the native entries") {
  NEED_GAME();
  const Board b = empty_board();
  // A throwaway weapon whose GetSkillEffect exercises the adders.
  lua_ok(H, b, R"lua(
    HostProbe = Skill:new{}
    function HostProbe:GetSkillEffect(p1, p2)
      local ret = SkillEffect()
      ret:AddProjectile(SpaceDamage(p2, 1), "effects/laser1", 0.5)       -- 1
      ret:AddProjectile(p1, SpaceDamage(p2, 1), "effects/shot", 0.5)     -- 2
      ret:AddArtillery(SpaceDamage(p2, 2), "effects/up")                 -- 3
      ret:AddQueuedProjectile(SpaceDamage(p2, 1), "effects/laser2", 0.5) -- q1
      ret:AddQueuedArtillery(SpaceDamage(p2, 1), "effects/upq")          -- q2
      ret:AddMelee(p1, SpaceDamage(p2, 3))                               -- 4
      local path = PointList() path:push_back(p1) path:push_back(p2)
      assert(ret:AddMove(path, NO_DELAY))                                 -- 5
      assert(not ret:AddMove(PointList(), NO_DELAY))
      ret:AddLeap(path, 0.25)                                            -- 6, 7
      ret:AddTeleport(p1, p2, FULL_DELAY)                                -- 8, 9, 10
      ret:AddAirstrike(Point(4, 2), "effects/plane")                     -- 11, 12
      ret:AddBounce(p1, 3)                                               -- 13
      ret:AddDelay(0.3)                                                  -- 14
      ret:AddGrapple(p1, p2, "hold")                                     -- 15
      ret:AddAnimation(p2, "ExploAir1", ANIM_NO_DELAY)                   -- 16
      ret:AddCharge(path, FULL_DELAY)                                    -- 17
      ret:AddBurrow(path, FULL_DELAY)                                    -- 18
      ret:AddDropper(SpaceDamage(p2, 1), "dropper")                      -- 19
      ret:AddVoice("Mission_X", -1)                                      -- 20
      return ret
    end
  )lua");
  Board board = empty_board();
  const int32_t uid = place(board, "PunchMech", {1, 1}, true);
  LuaCall call;
  const LuaSkillEffect se = H.skill_effect_raw(board, pawn(board, uid), "HostProbe", {1, 1}, {1, 3}, &call);
  REQUIRE_MESSAGE(call.ok, call.error);
  REQUIRE(se.effect.size() == 20);
  REQUIRE(se.q_effect.size() == 2);
  const auto& e = se.effect;
  // AddProjectile: "laser" in the art name forces kind 5 and delay 0.
  CHECK(e[0].projectile_kind == 5);
  CHECK(e[0].fDelay == 0.0f);
  CHECK(e[0].projectile_source == Point{-1, -1});
  CHECK(e[1].projectile_kind == 2);
  CHECK(e[1].fDelay == 0.5f);
  CHECK(e[1].projectile_source == Point{1, 1});
  CHECK(e[2].projectile_kind == 1);
  CHECK(e[2].fDelay == -2.0f);
  CHECK(e[2].projectile_art == "effects/up");
  // Queued laser keeps its delay.
  CHECK(se.q_effect[0].projectile_kind == 5);
  CHECK(se.q_effect[0].fDelay == 0.5f);
  CHECK(se.q_effect[1].projectile_kind == 1);
  CHECK(se.q_effect[1].fDelay == -2.0f);
  // AddMelee: the attacker tile is the path, FULL_DELAY by default.
  CHECK(e[3].move_kind == 3);
  CHECK(e[3].path == pts({{1, 1}}));
  CHECK(e[3].loc == Point{1, 3});
  CHECK(e[3].fDelay == -1.0f);
  CHECK_FALSE(e[3].is_movement());
  CHECK(e[4].is_movement());
  CHECK(e[4].loc == Point{-1, -1});
  CHECK(e[4].path == pts({{1, 1}, {1, 3}}));
  // AddLeap: a throw marker on the start tile, then a leap entry.
  CHECK(e[5].loc == Point{1, 1});
  CHECK(e[5].sImageMark == "advanced/combat/throw_2.png");
  CHECK(e[6].move_kind == 1);
  CHECK(e[6].fDelay == 0.25f);
  // AddTeleport: the move entry, then glow markers on both ends.
  CHECK(e[7].move_kind == 4);
  CHECK(e[8].loc == Point{1, 1});
  CHECK(e[9].loc == Point{1, 3});
  CHECK(e[9].sImageMark == "advanced/combat/icons/icon_teleport_glow");
  // AddAirstrike: a plane entry on (0, y), then a delay from x.
  CHECK(e[10].loc == Point{0, 2});
  CHECK(e[10].projectile_kind == 3);
  CHECK(e[11].bHide);
  CHECK(e[11].fDelay == 4 * 0.125f + 0.375f);
  CHECK(e[12].sScript == "Board:Bounce(Point( 1, 1 ),3)");
  CHECK(e[13].bHide);
  CHECK(e[13].fDelay == 0.3f);
  CHECK(e[14].loc == Point{1, 1});
  CHECK(e[14].grapple_source == Point{1, 3});
  CHECK(e[14].sAnimation == "dummy");
  CHECK(e[14].grapple_anim == "hold");
  CHECK(e[15].anim_flags == 1);
  CHECK(e[16].move_kind == 2);
  CHECK(e[17].move_kind == 5);
  CHECK(e[18].projectile_kind == 4);
  CHECK(e[19].sScript == "PrepareVoiceEvent(\"Mission_X\",-1)");
  // Engine conversion keeps the rules-relevant fields.
  const SkillEffect eng = to_engine(se);
  CHECK(eng.effect[3].move_kind == MoveKind::Melee);
  CHECK(eng.effect[2].projectile == ProjectileKind::Artillery);
  CHECK(eng.effect[2].damage == 2);
}

// ---- player weapons ---------------------------------------------------------------

// weapons_prime.lua Prime_Punchmech:GetSkillEffect; default Skill:GetTargetArea
// (global.lua) = Board:GetSimpleReachable(p, PathSize 1, false).
TEST_CASE("Lua host: Prime_Punchmech") {
  NEED_GAME();
  Scene s = punch_scene();
  place(s.b, "Firefly1", {3, 3});
  const Pawn& m = pawn(s.b, s.mech);
  CHECK(H.target_area(s.b, m, "Prime_Punchmech", m.pos) == pts({{3, 3}, {4, 4}, {3, 5}, {2, 4}}));
  LuaCall call;
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Prime_Punchmech", m.pos, {3, 3}, &call);
  REQUIRE(call.ok);
  REQUIRE(se.effect.size() == 1);
  const LuaSpaceDamage& d = se.effect[0];
  CHECK(d.loc == Point{3, 3});
  CHECK(d.iDamage == 2);
  CHECK(d.iPush == 0);  // DIR_UP
  CHECK(d.sAnimation == "explopunch1_0");
  CHECK(d.move_kind == 3);
  CHECK(d.path == pts({{3, 4}}));
  CHECK(d.fDelay == -1.0f);
  CHECK(se.q_effect.empty());

  // _B: Damage 4.
  CHECK(H.skill_effect_raw(s.b, m, "Prime_Punchmech_B", m.pos, {3, 3}).effect.at(0).iDamage == 4);
}

// Prime_Punchmech_A: Dash, PathSize INT_MAX: charge to the tile before the
// target, then the melee hit.
TEST_CASE("Lua host: Prime_Punchmech_A dashes") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& m = pawn(s.b, s.mech);
  const std::vector<Point> area = H.target_area(s.b, m, "Prime_Punchmech_A", m.pos);
  CHECK(area == pts({{3, 3}, {3, 2}, {3, 1}, {4, 4}, {5, 4}, {6, 4}, {7, 4}, {3, 5}, {3, 6}, {3, 7},
                     {2, 4}, {1, 4}, {0, 4}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Prime_Punchmech_A", m.pos, {3, 1});
  REQUIRE(se.effect.size() == 2);
  CHECK(se.effect[0].move_kind == 2);
  CHECK(se.effect[0].path == pts({{3, 4}, {3, 3}, {3, 2}}));
  CHECK(se.effect[0].fDelay == -1.0f);
  CHECK(se.effect[1].loc == Point{3, 1});
  CHECK(se.effect[1].path == pts({{3, 2}}));
  CHECK(se.effect[1].iDamage == 2);
}

// weapons_prime.lua Prime_ShieldBash (Flip, _A adds Shield): a self-shield
// entry, then a melee hit that flips (DIR_FLIP) instead of pushing.
TEST_CASE("Lua host: Prime_ShieldBash_A") {
  NEED_GAME();
  Scene s = punch_scene("GuardMech");
  place(s.b, "Firefly1", {4, 4});
  const Pawn& m = pawn(s.b, s.mech);
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Prime_ShieldBash_A", m.pos, {4, 4});
  REQUIRE(se.effect.size() == 2);
  CHECK(se.effect[0].loc == Point{3, 4});
  CHECK(se.effect[0].iShield == 1);
  CHECK(se.effect[0].iDamage == 0);
  CHECK(se.effect[1].loc == Point{4, 4});
  CHECK(se.effect[1].iPush == 6);
  CHECK(se.effect[1].sAnimation == "SwipeClaw2");
  CHECK(se.effect[1].iDamage == 2);
  CHECK(H.skill_effect_raw(s.b, m, "Prime_ShieldBash", m.pos, {4, 4}).effect.size() == 1);
}

// weapons_base.lua TankDefault (Brute_Tankmech in weapons_brute.lua): a
// projectile to the first blocked tile, pushing in the shot direction.
TEST_CASE("Lua host: Brute_Tankmech") {
  NEED_GAME();
  Scene s = punch_scene("TankMech");
  const Pawn& m = pawn(s.b, s.mech);
  const std::vector<Point> area = H.target_area(s.b, m, "Brute_Tankmech", m.pos);
  CHECK(std::find(area.begin(), area.end(), Point{3, 1}) != area.end());
  CHECK(std::find(area.begin(), area.end(), Point{3, 0}) == area.end());
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Brute_Tankmech", m.pos, {3, 3});
  REQUIRE(se.effect.size() == 1);
  const LuaSpaceDamage& d = se.effect[0];
  CHECK(d.loc == Point{3, 1});
  CHECK(d.iDamage == 1);
  CHECK(d.iPush == 0);
  CHECK(d.projectile_kind == 2);
  CHECK(d.projectile_art == "effects/shot_mechtank");
  CHECK(d.fDelay == 0.0f);
  CHECK(d.sAnimation == "explopush1_0");
  const LuaSkillEffect ab = H.skill_effect_raw(s.b, m, "Brute_Tankmech_AB", m.pos, {3, 3});
  CHECK(ab.effect.at(0).iDamage == 3);
  CHECK(ab.effect.at(0).sAnimation == "explopush2_0");
}

// weapons_base.lua ArtilleryDefault / LineArtillery (Ranged_Artillerymech):
// bounce, the shell, bounce, then four outer pushes.
TEST_CASE("Lua host: Ranged_Artillerymech") {
  NEED_GAME();
  Scene s = punch_scene("ArtiMech");
  const Pawn& m = pawn(s.b, s.mech);
  CHECK(H.target_area(s.b, m, "Ranged_Artillerymech", m.pos) ==
        pts({{3, 2}, {3, 1}, {3, 0}, {5, 4}, {6, 4}, {7, 4}, {3, 6}, {3, 7}, {1, 4}, {0, 4}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Ranged_Artillerymech", m.pos, {3, 1});
  REQUIRE(se.effect.size() == 7);
  CHECK(se.effect[0].sScript == "Board:Bounce(Point( 3, 4 ),1)");
  CHECK(se.effect[1].loc == Point{3, 1});
  CHECK(se.effect[1].iDamage == 1);
  CHECK(se.effect[1].iPush == 4);
  CHECK(se.effect[1].projectile_kind == 1);
  CHECK(se.effect[1].fDelay == -2.0f);
  CHECK(se.effect[1].sAnimation == "ExploArt1");
  CHECK(se.effect[1].projectile_art == "effects/shotup_tribomb_missile.png");
  CHECK(se.effect[2].sScript == "Board:Bounce(Point( 3, 1 ),1)");
  for (int d = 0; d < 4; ++d) {
    const LuaSpaceDamage& o = se.effect[static_cast<size_t>(3 + d)];
    CHECK(o.loc == Point{3, 1} + kDirVectors[static_cast<size_t>(d)]);
    CHECK(o.iDamage == 0);
    CHECK(o.iPush == d);
    CHECK(o.sAnimation == "airpush_" + std::to_string(d));
  }
  // _A: no building damage (DAMAGE_ZERO on the centre), bounce 2.5 -> 2.
  set_building(s.b, {3, 2});
  const LuaSkillEffect a = H.skill_effect_raw(s.b, pawn(s.b, s.mech), "Ranged_Artillerymech_A", {3, 4}, {3, 2});
  REQUIRE(a.effect.size() == 7);
  CHECK(a.effect[1].iDamage == 500);
  CHECK(a.effect[2].sScript == "Board:Bounce(Point( 3, 2 ),2)");
  CHECK(H.skill_effect_raw(s.b, pawn(s.b, s.mech), "Ranged_Artillerymech_B", {3, 4}, {3, 1}).effect.at(1).iDamage == 3);
}

// weapons_ranged.lua Ranged_Rocket: bounce, smoke behind the shooter, the
// pushing rocket, bounce.
TEST_CASE("Lua host: Ranged_Rocket") {
  NEED_GAME();
  Scene s = punch_scene("RocketMech");
  const Pawn& m = pawn(s.b, s.mech);
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Ranged_Rocket", m.pos, {3, 1});
  REQUIRE(se.effect.size() == 4);
  CHECK(se.effect[1].loc == Point{3, 5});
  CHECK(se.effect[1].iSmoke == 1);
  CHECK(se.effect[1].sAnimation == "exploout0_2");
  CHECK(se.effect[2].loc == Point{3, 1});
  CHECK(se.effect[2].iDamage == 2);
  CHECK(se.effect[2].iPush == 0);
  CHECK(se.effect[2].projectile_kind == 1);
  CHECK(se.effect[2].sAnimation == "explopush2_0");
  CHECK(se.effect[3].sScript == "Board:Bounce(Point( 3, 1 ),2)");
  CHECK(H.skill_effect_raw(s.b, m, "Ranged_Rocket_AB", m.pos, {3, 1}).effect.at(2).iDamage == 4);
}

// weapons_science.lua Science_Pullmech: a pulling projectile, then a delay and
// a bounce per tile between shooter and target.
TEST_CASE("Lua host: Science_Pullmech") {
  NEED_GAME();
  Scene s = punch_scene("PulseMech");
  const Pawn& m = pawn(s.b, s.mech);
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Science_Pullmech", m.pos, {3, 2});
  REQUIRE(se.effect.size() == 7);
  CHECK(se.effect[0].loc == Point{3, 1});
  CHECK(se.effect[0].iDamage == 0);
  CHECK(se.effect[0].iPush == 2);  // toward the shooter
  CHECK(se.effect[0].projectile_art == "effects/shot_pull");
  CHECK(se.effect[1].fDelay == 0.05f);
  CHECK(se.effect[2].sScript == "Board:Bounce(Point( 3, 4 ),-1)");
  CHECK(se.effect[6].sScript == "Board:Bounce(Point( 3, 2 ),-1)");
}

// weapons_brute.lua Brute_Jetmech: target area 2..Range tiles away that the
// shooter's own profile may land on; leap, then the bombs on the tiles
// flown over.
TEST_CASE("Lua host: Brute_Jetmech") {
  NEED_GAME();
  Scene s = punch_scene("JetMech");
  set_mountain(s.b, {5, 4});
  const Pawn& m = pawn(s.b, s.mech);
  CHECK(H.target_area(s.b, m, "Brute_Jetmech", m.pos) == pts({{3, 2}, {3, 6}, {1, 4}}));
  CHECK(H.target_area(s.b, m, "Brute_Jetmech_B", m.pos) ==
        pts({{3, 2}, {6, 4}, {3, 6}, {3, 7}, {1, 4}, {0, 4}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Brute_Jetmech", m.pos, {3, 2});
  REQUIRE(se.effect.size() == 5);
  CHECK(se.effect[0].sScript == "Board:Bounce(Point( 3, 4 ),2)");
  CHECK(se.effect[1].sImageMark == "advanced/combat/throw_0.png");
  CHECK(se.effect[2].move_kind == 1);
  CHECK(se.effect[2].path == pts({{3, 4}, {3, 2}}));
  CHECK(se.effect[2].fDelay == 0.25f);
  CHECK(se.effect[3].loc == Point{3, 3});
  CHECK(se.effect[3].iDamage == 1);
  CHECK(se.effect[3].iSmoke == 1);
  CHECK(se.effect[3].sAnimation == "ExploRaining1");
  CHECK(se.effect[4].sScript == "Board:Bounce(Point( 3, 3 ),3)");
  const LuaSkillEffect b = H.skill_effect_raw(s.b, m, "Brute_Jetmech_AB", m.pos, {3, 7});
  // Range 3: two bombs with a delay between them.
  REQUIRE(b.effect.size() == 8);
  CHECK(b.effect[3].iDamage == 2);
  CHECK(b.effect[5].fDelay == 0.2f);
  CHECK(b.effect[6].loc == Point{3, 6});
}

// advanced/ae_weapons.lua Ranged_Crack: three pushing shells along the line.
TEST_CASE("Lua host: Ranged_Crack") {
  NEED_GAME();
  Scene s = punch_scene("ArtiMech");
  set_building(s.b, {3, 0});
  const Pawn& m = pawn(s.b, s.mech);
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Ranged_Crack_B", m.pos, {3, 1});
  REQUIRE(se.effect.size() == 10);
  CHECK(se.effect[1].loc == Point{3, 0});
  CHECK(se.effect[1].iDamage == 500);  // _B spares buildings
  CHECK(se.effect[1].bHidePath);
  CHECK(se.effect[1].fDelay == 0.0f);
  CHECK(se.effect[2].fDelay == 0.15f);
  CHECK(se.effect[3].loc == Point{3, 1});
  CHECK(se.effect[3].iDamage == 1);
  CHECK(se.effect[5].loc == Point{3, 2});
  CHECK(se.effect[6].fDelay == 0.5f);
}

// weapons_support.lua Support_Boosters (Leap_Attack in weapons_base.lua, Range
// 7): any free tile in a straight line (hopping over the Firefly), then a leap
// that pushes the landing spot's neighbours (not back toward the start when
// the leap is a single tile).
TEST_CASE("Lua host: Support_Boosters") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& m = pawn(s.b, s.mech);
  const std::vector<Point> area = H.target_area(s.b, m, "Support_Boosters", m.pos);
  CHECK(area == pts({{3, 3}, {3, 2}, {3, 0}, {4, 4}, {5, 4}, {6, 4}, {7, 4}, {3, 5}, {3, 6}, {3, 7},
                     {2, 4}, {1, 4}, {0, 4}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, m, "Support_Boosters", m.pos, {3, 3});
  // burst, leap (2), burst, 3 pushes, bounce
  REQUIRE(se.effect.size() == 8);
  CHECK(se.effect[0].sScript == "Board:AddBurst(Point( 3, 4 ),\"Emitter_Burst_$tile\",4)");
  CHECK(se.effect[2].move_kind == 1);
  for (size_t i = 4; i < 7; ++i) CHECK(se.effect[i].iPush != 2);  // nothing pushed back down
}

// advanced/ae_weapons.lua Science_TC_Control: a two-click weapon. First click
// on a controllable pawn, second click inside its GetReachable area, final
// effect moves it along Board:GetPath.
TEST_CASE("Lua host: Science_TC_Control two-click flow") {
  NEED_GAME();
  Scene s = punch_scene("PulseMech");
  const int32_t target = place(s.b, "Firefly1", {3, 3});
  const Pawn& m = pawn(s.b, s.mech);
  CHECK(H.is_two_click("Science_TC_Control"));
  CHECK_FALSE(H.is_two_click("Prime_Punchmech"));
  CHECK(H.target_area(s.b, m, "Science_TC_Control", m.pos) == pts({{3, 3}}));
  const LuaSkillEffect first = H.skill_effect_raw(s.b, m, "Science_TC_Control", m.pos, {3, 3});
  REQUIRE(first.effect.size() == 1);
  CHECK(first.effect[0].sImageMark == "combat/icons/icon_mind_glow.png");
  const Pathing prof = path_profile(s.b, pawn(s.b, target));
  CHECK(H.second_target_area(s.b, m, "Science_TC_Control", m.pos, {3, 3}) ==
        mask_points(reachable_list(s.b, {3, 3}, 2, prof)));
  const LuaSkillEffect fin = H.final_effect_raw(s.b, m, "Science_TC_Control", m.pos, {3, 3}, {5, 3});
  REQUIRE(fin.effect.size() == 1);
  CHECK(fin.effect[0].path == find_path(s.b, {3, 3}, {5, 3}, prof));
  CHECK(fin.effect[0].fDelay == -1.0f);
}

// ---- enemy weapons -------------------------------------------------------------------

// weapons_enemy.lua FireflyAtk1: a queued projectile to the first blocked tile.
TEST_CASE("Lua host: FireflyAtk1 queued shot") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& v = pawn(s.b, s.vek);
  CHECK(H.target_area(s.b, v, "FireflyAtk1", v.pos) == pts({{3, 0}, {4, 1}, {3, 2}, {2, 1}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, v, "FireflyAtk1", v.pos, {3, 2});
  CHECK(se.effect.empty());
  REQUIRE(se.q_effect.size() == 1);
  const LuaSpaceDamage& d = se.q_effect[0];
  CHECK(d.loc == Point{3, 4});
  CHECK(d.iDamage == 1);
  CHECK(d.projectile_kind == 2);
  CHECK(d.fDelay == -2.0f);
  CHECK(d.projectile_art == "effects/shot_firefly");
  CHECK(d.projectile_source == Point{-1, -1});
  // Fired from the current tile: the queued list is what runs.
  const LuaSkillEffect fired = H.queued_effect_raw(s.b, v, "FireflyAtk1", {3, 2});
  REQUIRE(fired.effect.size() == 1);
  CHECK(fired.effect[0].loc == Point{3, 4});
  CHECK(fired.q_effect.empty());
  // A stored target outside the area recomputed from the current tile fizzles.
  CHECK(H.queued_effect_raw(s.b, v, "FireflyAtk1", {3, 3}).effect.empty());
  const SkillEffect eng = H.queued_effect(s.b, v, "FireflyAtk1", {3, 2});
  REQUIRE(eng.effect.size() == 1);
  CHECK(eng.effect[0].projectile == ProjectileKind::Projectile);
}

// weapons_enemy.lua HornetAtk1: a queued melee with a 0.25 s delay.
TEST_CASE("Lua host: HornetAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const int32_t h = place(s.b, "Hornet1", {3, 3});
  const LuaSkillEffect se = H.skill_effect_raw(s.b, pawn(s.b, h), "HornetAtk1", {3, 3}, {3, 4});
  REQUIRE(se.q_effect.size() == 1);
  CHECK(se.q_effect[0].move_kind == 3);
  CHECK(se.q_effect[0].path == pts({{3, 3}}));
  CHECK(se.q_effect[0].fDelay == 0.25f);
  CHECK(se.q_effect[0].sAnimation == "explohornet_2");
}

// weapons_enemy.lua ScorpionAtk1 (and LeaperAtk1, which derives from it): web
// sound, a grapple, then the queued melee.
TEST_CASE("Lua host: ScorpionAtk1 and LeaperAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const int32_t sc = place(s.b, "Scorpion1", {3, 3});
  for (const auto& [weapon, damage, sound] :
       {std::tuple{"ScorpionAtk1", 1, "/enemy/scorpion_soldier_1"}, std::tuple{"LeaperAtk1", 3, "/enemy/leaper_1"}}) {
    const LuaSkillEffect se = H.skill_effect_raw(s.b, pawn(s.b, sc), weapon, {3, 3}, {3, 4});
    REQUIRE(se.effect.size() == 2);
    CHECK(se.effect[0].sSound == std::string(sound) + "/attack_web");
    CHECK(se.effect[1].loc == Point{3, 3});
    CHECK(se.effect[1].grapple_source == Point{3, 4});
    REQUIRE(se.q_effect.size() == 1);
    CHECK(se.q_effect[0].iDamage == damage);
    CHECK(se.q_effect[0].iPush == 4);
    CHECK(se.q_effect[0].fDelay == -1.0f);
    CHECK(se.q_effect[0].sSound == std::string(sound) + "/attack");
  }
}

// weapons_enemy.lua CentipedeAtk1: queued acid projectile plus the two side
// tiles of the impact ((dir - 1) % 4 is Lua's modulo).
TEST_CASE("Lua host: CentipedeAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const int32_t c = place(s.b, "Centipede1", {3, 0});
  const LuaSkillEffect se = H.skill_effect_raw(s.b, pawn(s.b, c), "CentipedeAtk1", {3, 0}, {4, 0});
  REQUIRE(se.q_effect.size() == 3);
  CHECK(se.q_effect[0].loc == Point{7, 0});
  CHECK(se.q_effect[0].iAcid == 1);
  CHECK(se.q_effect[1].loc == Point{7, 1});
  CHECK(se.q_effect[2].loc == Point{7, -1});
}

// advanced/ae_weapons_enemy.lua BurnbugAtk1: grapple shot, damage, and a
// queued charge pulling the hit pawn back toward the bug.
TEST_CASE("Lua host: BurnbugAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& v = pawn(s.b, s.vek);
  const LuaSkillEffect se = H.skill_effect_raw(s.b, v, "BurnbugAtk1", {3, 1}, {3, 2});
  REQUIRE(se.q_effect.size() == 3);
  CHECK(se.q_effect[0].loc == Point{3, 4});
  CHECK(se.q_effect[0].bHidePath);
  CHECK(se.q_effect[0].projectile_art == "effects/shot_grapple");
  CHECK(se.q_effect[1].iDamage == 1);
  CHECK(se.q_effect[2].move_kind == 2);
  CHECK(se.q_effect[2].path == pts({{3, 4}, {3, 3}, {3, 2}}));
}

// weapons_enemy.lua SpiderAtk1 / BlobberAtk1: an egg/blob artillery shell
// (sPawn) plus grapples / empty hits around it; targets must be empty.
TEST_CASE("Lua host: Spider and Blobber egg weapons") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& v = pawn(s.b, s.vek);
  const std::vector<Point> area = H.target_area(s.b, v, "SpiderAtk1", v.pos);
  CHECK(std::find(area.begin(), area.end(), Point{3, 4}) == area.end());  // occupied
  CHECK(std::find(area.begin(), area.end(), Point{3, 3}) != area.end());
  const LuaSkillEffect spider = H.skill_effect_raw(s.b, v, "SpiderAtk1", v.pos, {3, 3});
  REQUIRE(spider.effect.size() == 5);
  CHECK(spider.effect[0].sPawn == "WebbEgg1");
  CHECK(spider.effect[0].projectile_kind == 1);
  CHECK(spider.effect[1].grapple_source == Point{3, 2});
  const LuaSkillEffect blob = H.skill_effect_raw(s.b, v, "BlobberAtk1", v.pos, {3, 3});
  REQUIRE(blob.effect.size() == 5);
  CHECK(blob.effect[0].sPawn == "Blob1");
  CHECK(blob.effect[0].projectile_art == "effects/shotup_blobber1.png");
  const SkillEffect eng = to_engine(blob);
  CHECK(symbol_name(eng.effect[0].spawn_pawn) == "Blob1");
}

// weapons_enemy.lua DiggerAtk1: self-targeted; rock walls (sPawn "Wall") on
// free neighbours now, queued hits on all four.
TEST_CASE("Lua host: DiggerAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const int32_t d = place(s.b, "Digger1", {3, 3});
  s.b.tile({2, 3}).terrain = Terrain::Water;
  CHECK(H.target_area(s.b, pawn(s.b, d), "DiggerAtk1", {3, 3}) == pts({{3, 3}}));
  const LuaSkillEffect se = H.skill_effect_raw(s.b, pawn(s.b, d), "DiggerAtk1", {3, 3}, {3, 3});
  REQUIRE(se.effect.size() == 2);  // up and right; down is the mech, left is water
  CHECK(se.effect[0].loc == Point{3, 2});
  CHECK(se.effect[0].sPawn == "Wall");
  CHECK(se.effect[1].loc == Point{4, 3});
  REQUIRE(se.q_effect.size() == 4);
  CHECK(se.q_effect[2].loc == Point{3, 4});
  CHECK(se.q_effect[2].iDamage == 1);
  CHECK(se.q_effect[2].sAnimation == "explorocker_2");
}

// advanced/ae_weapons_enemy.lua MosquitoAtk1 and BouncerAtk1.
TEST_CASE("Lua host: MosquitoAtk1 and BouncerAtk1") {
  NEED_GAME();
  Scene s = punch_scene();
  const int32_t mq = place(s.b, "Mosquito1", {3, 3});
  const LuaSkillEffect m = H.skill_effect_raw(s.b, pawn(s.b, mq), "MosquitoAtk1", {3, 3}, {3, 4});
  REQUIRE(m.effect.size() == 2);
  CHECK(m.effect[1].iSmoke == 1);
  CHECK(m.effect[1].loc == Point{3, 4});
  REQUIRE(m.q_effect.size() == 1);
  CHECK(m.q_effect[0].move_kind == 3);
  CHECK(m.q_effect[0].sAnimation == "explomosquito_2");
  const LuaSkillEffect b = H.skill_effect_raw(s.b, pawn(s.b, mq), "BouncerAtk1", {3, 3}, {3, 4});
  REQUIRE(b.q_effect.size() == 2);
  CHECK(b.q_effect[0].loc == Point{3, 3});
  CHECK(b.q_effect[0].iPush == 0);
  CHECK(b.q_effect[1].iPush == 2);
  CHECK(b.q_effect[1].iDamage == 1);
}

// ---- death effects ---------------------------------------------------------------------

// missions/acid/mission_barrels.lua AcidVat:GetDeathEffect.
TEST_CASE("Lua host: AcidVat death effect") {
  NEED_GAME();
  Board b = empty_board();
  const int32_t vat = place(b, "AcidVat", {4, 4});
  LuaCall call;
  const LuaSkillEffect se = H.death_effect_raw(b, pawn(b, vat), std::nullopt, nullptr, &call);
  REQUIRE_MESSAGE(call.ok, call.error);
  REQUIRE(se.effect.size() == 1);
  CHECK(se.effect[0].loc == Point{4, 4});
  CHECK(se.effect[0].iTerrain == 3);
  CHECK(se.effect[0].iAcid == 1);
  CHECK(se.effect[0].sAnimation == "splash");
  // global.lua Pawn:GetDeathEffect: empty.
  const int32_t ff = place(b, "Firefly1", {1, 1});
  CHECK(H.death_effect_raw(b, pawn(b, ff)).effect.empty());
}

// missions/bosses/goo.lua BlobBoss:GetDeathEffect: two random tiles within 2
// (random_removal over general_DiamondTarget order), from the pawn's seed.
TEST_CASE("Lua host: BlobBoss split is seeded") {
  NEED_GAME();
  Board b = empty_board();
  const int32_t boss = place(b, "BlobBoss", {4, 4});
  set_mountain(b, {4, 3});
  const uint32_t seed = 12345;
  const LuaSkillEffect se = H.death_effect_raw(b, pawn(b, boss), seed);
  REQUIRE(se.effect.size() == 3);
  CHECK(se.effect[0].sSound == "/enemy/goo_boss/split");
  // Expected: candidates in general_DiamondTarget order (y-major rows, x
  // ascending), within Manhattan 2, not blocked for ground, not the centre.
  std::vector<Point> cand;
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 8; ++x) {
      const Point p{x, y};
      const int dist = std::abs(x - 4) + std::abs(y - 4);
      if (dist == 0 || dist > 2 || p == Point{4, 3}) continue;
      cand.push_back(p);
    }
  }
  H.seed(seed);
  std::vector<Point> expect;
  for (int i = 0; i < 2; ++i) {
    const size_t k = static_cast<size_t>(H.rand() % static_cast<int>(cand.size()));
    expect.push_back(cand[k]);
    cand.erase(cand.begin() + static_cast<long>(k));
  }
  CHECK(se.effect[1].loc == expect[0]);
  CHECK(se.effect[2].loc == expect[1]);
  CHECK(se.effect[1].sPawn == "BlobBossMed");
  CHECK(se.effect[1].projectile_kind == 1);
  CHECK(se.effect[1].fDelay == 0.0f);
  // Same seed, same split.
  CHECK(H.death_effect_raw(b, pawn(b, boss), seed) == se);
}

// ---- board queries and globals ------------------------------------------------------

TEST_CASE("Lua host: Board and Pawn queries") {
  NEED_GAME();
  Scene s = punch_scene();
  set_building(s.b, {5, 5});
  s.b.tile({6, 6}).terrain = Terrain::Water;
  s.b.tile({6, 6}).lava = true;
  s.b.tile({0, 0}).fire = FireState::Burning;
  const int32_t corpse = place(s.b, "JetMech", {1, 1}, true);
  s.b.find_pawn(corpse)->hp = 0;
  lua_ok(H, s.b, "assert(Board:IsValid(Point(0, 0)) and not Board:IsValid(Point(8, 0)) and Board:IsValid(7, 7))");
  lua_ok(H, s.b, "assert(Board:GetSize() == Point(8, 8))");
  lua_ok(H, s.b, "assert(Board:IsBuilding(Point(5, 5)) and Board:IsPowered(Point(5, 5)))");
  lua_ok(H, s.b, "assert(Board:GetTerrain(Point(6, 6)) == TERRAIN_WATER and Board:IsTerrain(Point(6, 6), TERRAIN_LAVA))");
  lua_ok(H, s.b, "assert(Board:GetTerrain(Point(-1, 3)) == TERRAIN_ROAD and Board:IsTerrain(Point(9, 9), 0))");
  lua_ok(H, s.b, "assert(Board:IsFire(Point(0, 0)) and not Board:IsTerrain(Point(0, 0), TERRAIN_FIRE))");
  lua_ok(H, s.b, "assert(Board:IsEdge(Point(0, -5)) and not Board:IsEdge(Point(-1, 3)))");
  // Teams: TEAM_ANY matches empty tiles too; TEAM_MECH matches the wreck.
  lua_ok(H, s.b, "assert(Board:IsPawnTeam(Point(4, 4), TEAM_ANY) and not Board:IsPawnTeam(Point(4, 4), TEAM_ENEMY))");
  lua_ok(H, s.b, "assert(Board:IsPawnTeam(Point(3, 1), TEAM_ENEMY) and Board:IsPawnTeam(Point(3, 1), TEAM_ENEMY_MAJOR))");
  lua_ok(H, s.b, "assert(Board:GetPawnTeam(Point(3, 4)) == TEAM_PLAYER and Board:GetPawnTeam(Point(4, 4)) == TEAM_NONE)");
  lua_ok(H, s.b, "assert(Board:IsPawnTeam(Point(1, 1), TEAM_MECH) and Board:IsPawnSpace(Point(1, 1)))");
  lua_ok(H, s.b, "assert(Board:GetPawn(Point(4, 4)) == nil and Board:GetPawn(Point(3, 1)):GetType() == 'Firefly1')");
  lua_ok(H, s.b, "assert(Board:GetPawn(1):GetSpace() == Point(3, 1) and Board:GetPawnSpace(99) == Point(-1, -1))");
  lua_ok(H, s.b, "assert(Board:IsPawnAlive(1) and not Board:IsPawnAlive(2))");
  lua_ok(H, s.b, "local ids = Board:GetPawns(TEAM_MECH) assert(ids:size() == 2)");
  lua_ok(H, s.b, "assert(Board:GetPawnCount('Firefly') == 1 and Board:GetEnemyCount() == 1)");
  lua_ok(H, s.b, "assert(Board:IsBlocked(Point(3, 1), PATH_GROUND) and not Board:IsBlocked(Point(6, 6), PATH_FLYER))");
  lua_ok(H, s.b, "local p = Board:GetPath(Point(3, 4), Point(5, 4), PATH_GROUND) assert(p:size() == 3)");
  lua_ok(H, s.b, "assert(Board:GetSimplePath(Point(3, 4), Point(3, 1)):size() == 4)");
  lua_ok(H, s.b, "assert(Board:IsDeadly(SpaceDamage(Point(3, 1), 3), nil) and not Board:IsDeadly(SpaceDamage(Point(3, 1), 2), nil))");
  lua_ok(H, s.b, "assert(Pawn == nil or Pawn:GetId() >= 0)");
  // Pawn userdata have no __eq: two fetches of one pawn cannot be compared.
  CHECK(lua_error(H, s.b, "local x = Board:GetPawn(1) == Board:GetPawn(1)").find("No such operator") !=
        std::string::npos);
  lua_ok(H, s.b, "local p = Board:GetPawn(1) assert(p == p)");
  // Pawn methods.
  lua_ok(H, s.b, "local p = Board:GetPawn(0) assert(p:IsMech() and p:GetTeam() == TEAM_PLAYER and p:GetPathProf() == 16 + PATH_MASSIVE)");
  lua_ok(H, s.b, "local p = Board:GetPawn(1) assert(p:GetMoveSpeed() == 2 and not p:IsGuarding() and p:IsRanged())");
  lua_ok(H, s.b, "local p = Board:GetPawn(2) assert(p:IsDead() and p:IsCorpse() and p:GetHealth() == 0)");
  lua_ok(H, s.b, "assert(Game:GetTurnCount() == 1 and Game:GetTeamTurn() == TEAM_PLAYER and Game:GetPower():GetValue() == 7)");
}

TEST_CASE("Lua host: mutating bindings are reported, not applied") {
  NEED_GAME();
  Scene s = punch_scene();
  const LuaCall c = H.run_script(
      s.b,
      "Game:ModifyPowerGrid(SERIOUSLY_JUST_ONE) Board:SetTerrain(Point(2, 2), TERRAIN_WATER)"
      " Board:GetPawn(1):SetFrozen(true) Board:AddAlert(Point(1, 1), 'x')"
      " assert(Board:GetTerrain(Point(2, 2)) == TERRAIN_ROAD)");
  REQUIRE_MESSAGE(c.ok, c.error);
  REQUIRE(c.writes.size() == 3);
  CHECK(c.writes[0].describe() == "Game:ModifyPowerGrid(3626)");
  CHECK(c.writes[1].describe() == "Board:SetTerrain(Point( 2, 2 ), 3)");
  CHECK(c.writes[2].describe() == "Pawn:SetFrozen(true) [pawn 1]");
  // Strict types still apply to mutators.
  CHECK_FALSE(H.run_script(s.b, "Board:SetTerrain(Point(2, 2), 'x')").ok);
  // LOG/print output is captured.
  const LuaCall p = H.run_script(s.b, "LOG('hello', 3)");
  REQUIRE(p.ok);
  CHECK(p.console.size() == 2);  // ConsolePrint + print
}

TEST_CASE("Lua host: Board:IsTargeted re-runs queued attacks") {
  NEED_GAME();
  Scene s = punch_scene();
  Pawn* v = s.b.find_pawn(s.vek);
  v->queued = {0, {3, 1}, {3, 2}};  // FireflyAtk1 down the column: hits the mech at (3,4)
  lua_ok(H, s.b, "assert(Board:IsTargeted(Point(3, 4)) and not Board:IsTargeted(Point(3, 2)))");
  CHECK(H.target_area(s.b, pawn(s.b, s.vek), "FireflyAtk1", {3, 1}).size() == 4);
}

TEST_CASE("Lua host: IsPassiveSkill matches the squad's passive prefixes") {
  NEED_GAME();
  Scene s = punch_scene();
  s.b.find_pawn(s.mech)->weapons[1] = intern("Passive_Electric_A");  // Passive = "Electric_Smoke_A"
  lua_ok(H, s.b, "assert(IsPassiveSkill('Electric_Smoke') and IsPassiveSkill('Electric_Smoke_A'))");
  lua_ok(H, s.b, "assert(not IsPassiveSkill('Mass_Repair'))");
}

TEST_CASE("Lua host: errors fall back to the game's defaults") {
  NEED_GAME();
  Scene s = punch_scene();
  const Pawn& m = pawn(s.b, s.mech);
  LuaCall call;
  CHECK(H.target_area(s.b, m, "No_Such_Weapon", m.pos, &call).empty());
  CHECK_FALSE(call.ok);
  CHECK(call.error.find("cast_failed") != std::string::npos);  // CallMethod returned 0
  // Lua's Move:GetSkillEffect calls AddLeap(p1, p2, FULL_DELAY) for jumpers,
  // which has no matching overload: the game gets an empty effect too.
  Board b = empty_board();
  const int32_t leaper = place(b, "Leaper1", {2, 2});
  LuaCall mv;
  CHECK(H.skill_effect_raw(b, pawn(b, leaper), "Move", {2, 2}, {2, 4}, &mv).effect.empty());
  CHECK_FALSE(mv.ok);
  CHECK(mv.error.find("No matching overload") != std::string::npos);
  // A plain walker gets the A* path.
  const LuaSkillEffect walk = H.skill_effect_raw(s.b, m, "Move", m.pos, {5, 4});
  REQUIRE(walk.effect.size() == 1);
  CHECK(walk.effect[0].path == find_path(s.b, m.pos, {5, 4}, path_profile(s.b, m)));
}

// ---- coverage --------------------------------------------------------------------------

namespace {

// A few varied boards for the sweep.
std::vector<Board> sweep_boards(int32_t* shooter_uids) {
  std::vector<Board> boards;
  {
    Board b = empty_board();
    set_mountain(b, {2, 2});
    set_building(b, {5, 5});
    b.tile({1, 6}).terrain = Terrain::Water;
    shooter_uids[0] = place(b, "PunchMech", {3, 4}, true);
    place(b, "Firefly1", {3, 1});
    place(b, "Scorpion1", {6, 4});
    place(b, "Hornet1", {3, 6});
    place(b, "JetMech", {1, 4}, true);
    boards.push_back(b);
  }
  {
    Board b = empty_board();
    for (int x = 0; x < 8; ++x) set_building(b, {x, 0});
    b.tile({4, 4}).terrain = Terrain::Hole;
    b.tile({2, 5}).terrain = Terrain::Ice;
    b.tile({2, 5}).hp = b.tile({2, 5}).max_hp = 2;
    b.tile({6, 2}).acid = true;
    b.tile({6, 3}).smoke = true;
    shooter_uids[1] = place(b, "Leaper1", {0, 7});
    place(b, "TankMech", {1, 7}, true);
    place(b, "Digger1", {0, 6});
    place(b, "Spider1", {6, 6});
    place(b, "BlobBoss", {5, 2});
    boards.push_back(b);
  }
  {
    Board b = empty_board();
    for (int y = 0; y < 8; ++y) b.tile({7, y}).terrain = Terrain::Water;
    set_mountain(b, {4, 3});
    shooter_uids[2] = place(b, "ScienceMech", {4, 4}, true);
    place(b, "Burnbug1", {4, 6});
    place(b, "Mosquito1", {2, 4});
    place(b, "Bouncer1", {4, 2});
    place(b, "GuardMech", {5, 4}, true);
    Pawn* q = b.find_pawn(3);
    q->queued = {0, {4, 2}, {4, 3}};
    boards.push_back(b);
  }
  return boards;
}

}  // namespace

TEST_CASE("Lua host: every weapon runs on every sweep board without Lua errors") {
  NEED_GAME();
  const std::vector<std::string> weapons = H.weapon_ids();
  MESSAGE("weapon ids: " << weapons.size());
  CHECK(weapons.size() > 500);
  int32_t shooters[3];
  const std::vector<Board> boards = sweep_boards(shooters);
  // Known faithful failures: the game's own script is broken for this
  // shooter (see the test above for Move on jumpers).
  const auto expected_failure = [&](const std::string& w, size_t board) {
    return w == "Move" && board == 1;
  };
  std::map<std::string, std::string> failures;
  int calls = 0, two_click = 0;
  for (const std::string& w : weapons) {
    const bool tc = H.is_two_click(w);
    two_click += tc ? 1 : 0;
    for (size_t bi = 0; bi < boards.size(); ++bi) {
      const Board& b = boards[bi];
      const Pawn& s = *b.find_pawn(shooters[bi]);
      LuaCall call;
      const std::vector<Point> area = H.target_area(b, s, w, s.pos, &call);
      ++calls;
      std::string err = call.ok ? "" : "area: " + call.error;
      for (Point t : area) {
        if (!err.empty()) break;
        LuaCall c2;
        H.skill_effect_raw(b, s, w, s.pos, t, &c2);
        ++calls;
        if (!c2.ok) err = "effect -> " + to_visual(t) + ": " + c2.error;
        if (tc && err.empty()) {
          const std::vector<Point> second = H.second_target_area(b, s, w, s.pos, t, &c2);
          ++calls;
          for (Point t2 : second) {
            if (!c2.ok) break;
            H.final_effect_raw(b, s, w, s.pos, t, t2, &c2);
            ++calls;
          }
          if (!c2.ok) err = "two-click -> " + to_visual(t) + ": " + c2.error;
        }
      }
      if (!err.empty() && !expected_failure(w, bi)) {
        failures[w + " (board " + std::to_string(bi) + ")"] = err;
      }
    }
  }
  MESSAGE("Lua calls: " << calls << ", two-click weapons: " << two_click);
  for (const auto& [w, e] : failures) MESSAGE(w << ": " << e);
  CHECK(failures.empty());
}

TEST_CASE("Lua host: per-call cost") {
  NEED_GAME();
  Scene s = punch_scene();
  place(s.b, "Firefly1", {3, 3});
  const Pawn m = pawn(s.b, s.mech);
  constexpr int kIters = 2000;
  const auto t0 = std::chrono::steady_clock::now();
  LuaCall check;
  CHECK(H.skill_effect_raw(s.b, m, "Prime_Punchmech", m.pos, {3, 3}, &check).effect.size() == 1);
  CHECK(H.target_area(s.b, m, "Prime_Punchmech_A", m.pos, &check).size() > 5);
  CHECK_MESSAGE(check.ok, check.error);
  for (int i = 0; i < kIters; ++i) H.skill_effect_raw(s.b, m, "Prime_Punchmech", m.pos, {3, 3});
  const auto t1 = std::chrono::steady_clock::now();
  for (int i = 0; i < kIters; ++i) H.skill_effect_raw(s.b, m, "Ranged_Artillerymech", m.pos, {3, 1});
  const auto t2 = std::chrono::steady_clock::now();
  for (int i = 0; i < kIters; ++i) H.target_area(s.b, m, "Prime_Punchmech_A", m.pos);
  const auto t3 = std::chrono::steady_clock::now();
  const auto us = [](auto a, auto b) {
    return std::chrono::duration<double, std::micro>(b - a).count() / kIters;
  };
  MESSAGE("GetSkillEffect Prime_Punchmech: " << us(t0, t1) << " us; Ranged_Artillerymech: " << us(t1, t2)
                                             << " us; GetTargetArea Prime_Punchmech_A: " << us(t2, t3) << " us");
  CHECK(us(t0, t1) < 1000.0);
}
