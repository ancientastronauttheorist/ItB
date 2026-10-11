// itb_live (tools/live_tool.hpp): the live driver's JSON requests, and the
// archived live-session bridge states under recordings/live/.

#include <doctest/doctest.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <memory>
#include <set>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "itb/engine.hpp"
#include "itb/game_data.hpp"
#include "itb/recording.hpp"
#include "itb/tile_rules.hpp"
#include "live_tool.hpp"

namespace fs = std::filesystem;
using nlohmann::json;
using namespace itb;

namespace {

const fs::path kLiveDir = fs::path(ITB_REPO_ROOT) / "recordings" / "live";
const fs::path kCaveT2 = kLiveDir / "2026-10-09" / "Mission_Final_Cave_t2_start_1791602065398.json";

bool have_game() {
  const auto root = GameData::default_game_root();
  return !root.empty() && fs::exists(root / "scripts" / "scripts.lua");
}

tools::LiveSession* session() {
  static std::unique_ptr<tools::LiveSession> s = [] {
    return have_game() ? std::make_unique<tools::LiveSession>(GameData::default_game_root(), 1) : nullptr;
  }();
  return s.get();
}

#define NEED_SESSION()                                                                    \
  if (!session()) {                                                                       \
    WARN_MESSAGE(false, "no game install found; set ITB_GAME_DIR to run engine tests"); \
    return;                                                                               \
  }                                                                                       \
  tools::LiveSession& S = *session()

// Files scripts/live_play.py writes next to the bridge states.
bool is_state_file(const fs::path& p) {
  const std::string n = p.filename().string();
  if (p.extension() != ".json") return false;
  for (const char* suffix : {"_prediction.json", "_solve.json", "manifest.json", "_last_prediction.json"}) {
    if (n.ends_with(suffix)) return false;
  }
  return true;
}

// A dump taken after a mission ended (live_play records the state it sees
// once the enemy phase finishes the mission): no combat board to check.
bool mission_over_dump(const fs::path& p) {
  const json j = json::parse(std::ifstream(p), nullptr, false);
  if (j.is_discarded()) return false;
  const json* s = &j;
  if (s->contains("data")) s = &(*s)["data"];
  if (s->contains("bridge_state")) s = &(*s)["bridge_state"];
  return s->value("in_active_mission", true) == false;
}

std::set<int> uids(const json& board) {
  std::set<int> out;
  for (const json& u : board["units"]) out.insert(u["uid"].get<int>());
  return out;
}

fs::path temp_file(const std::string& name, const json& content) {
  const fs::path p = fs::temp_directory_path() / name;
  std::ofstream(p) << content.dump();
  return p;
}

}  // namespace

TEST_CASE("live: every archived live-session bridge state loads") {
  REQUIRE(fs::is_directory(kLiveDir));
  std::unique_ptr<GameData> data;
  if (have_game()) data = std::make_unique<GameData>(GameData::load(GameData::default_game_root()));
  int loaded = 0, session_2026_10_09 = 0;
  for (const auto& e : fs::recursive_directory_iterator(kLiveDir)) {
    if (!e.is_regular_file() || !is_state_file(e.path())) continue;
    if (mission_over_dump(e.path())) continue;
    std::string error;
    const auto rec = load_recording(e.path(), data.get(), &error);
    CHECK_MESSAGE(rec.has_value(), e.path().string() << ": " << error);
    if (!rec) continue;
    ++loaded;
    CHECK_MESSAGE(!rec->mission_id.empty(), e.path().string());
    CHECK_MESSAGE(!rec->board.pawns().empty(), e.path().string());
    if (e.path().parent_path().filename() == "2026-10-09") ++session_2026_10_09;
  }
  CHECK(session_2026_10_09 == 78);
  MESSAGE("live states loaded: " << loaded);
}

TEST_CASE("live: board, solve and predict on a live state") {
  NEED_SESSION();
  const json board = S.handle({{"cmd", "board"}, {"state", kCaveT2.string()}});
  REQUIRE_MESSAGE(board["ok"].get<bool>(), board.dump());
  CHECK(board["mission_id"] == "Mission_Final_Cave");
  CHECK(board["turn"] == 2);
  CHECK(board["active_units"] == 3);
  const json& units = board["board"]["units"];
  REQUIRE(units.size() >= 3);
  CHECK(std::is_sorted(units.begin(), units.end(),
                       [](const json& a, const json& b) { return a["uid"].get<int>() < b["uid"].get<int>(); }));
  for (const char* key : {"uid", "type", "x", "y", "hp", "team", "mech", "fire", "acid", "frozen", "shield", "web"}) {
    CHECK(units[0].contains(key));
  }

  const json solved = S.handle({{"cmd", "solve"}, {"state", kCaveT2.string()}, {"time_limit", 3.0}});
  REQUIRE_MESSAGE(solved["ok"].get<bool>(), solved.dump());
  CHECK(solved["format"] == tools::kLiveFormat);
  CHECK(solved["searched"] == true);
  for (const char* key : {"worst_case", "upper_bound", "proven_optimal", "proven_components", "chance_exact",
                          "timed_out", "contingent", "stats", "warnings", "plan", "steps", "start", "after_player",
                          "after_enemy", "enemy_phase", "predicted_score"}) {
    CHECK_MESSAGE(solved.contains(key), key);
  }
  CHECK(solved["refused"] == -1);
  CHECK(solved["worst_case"].contains("grid"));
  const json& plan = solved["plan"];
  REQUIRE_FALSE(plan.empty());
  // One step per move that changes tile and per weapon or repair, in order,
  // each with the predicted board after it.
  size_t expected = 0;
  for (const json& a : plan) {
    if (a["kind"] != "none") ++expected;
  }
  const json& steps = solved["steps"];
  CHECK(steps.size() >= expected);
  CHECK(steps.size() <= expected + plan.size());
  for (size_t i = 0; i < steps.size(); ++i) {
    const json& s = steps[i];
    CHECK(s["index"] == i);
    CHECK(s["status"] == "ok");
    CHECK(s["board"].contains("units"));
    const std::string sub = s["sub"];
    CHECK((sub == "move" || sub == "weapon" || sub == "repair"));
    if (sub == "weapon") CHECK(s["weapon_index"].get<int>() >= 0);
  }

  // The same plan through `predict` gives the same boards.
  const json predicted = S.handle({{"cmd", "predict"}, {"state", kCaveT2.string()}, {"plan", plan}});
  REQUIRE_MESSAGE(predicted["ok"].get<bool>(), predicted.dump());
  CHECK(predicted["steps"].size() == steps.size());
  CHECK(predicted["after_enemy"] == solved["after_enemy"]);
  CHECK(predicted["after_player"] == solved["after_player"]);
  CHECK_FALSE(predicted.contains("worst_case"));
}

TEST_CASE("live: the solver never sees the hidden spawn types") {
  NEED_SESSION();
  std::ifstream in(kCaveT2);
  json state = json::parse(in);
  // A bridge that exports the spawn queue: types for every marker.
  json queue = json::array();
  for (const json& p : state["spawning_tiles"]) queue.push_back({{"type", "Scorpion1"}, {"x", p[0]}, {"y", p[1]}});
  REQUIRE(queue.size() == 3);
  state["spawn_queue"] = queue;
  state["spawn_queue_matches_markers"] = true;
  const fs::path path = temp_file("itb_live_test_spawn_queue.json", state);

  const json r = S.handle({{"cmd", "predict"}, {"state", path.string()}, {"plan", json::array()}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  const std::set<int> before = uids(r["start"]);
  for (const json& u : r["after_enemy"]["units"]) {
    CHECK_MESSAGE(!(before.count(u["uid"].get<int>()) == 0 && u["type"] == "Scorpion1"), u.dump());
  }
  CHECK_FALSE(r["enemy_phase"]["emerged_unknown"].empty());

  // With full information the same board would get the Scorpions: the test
  // above is meaningful.
  const std::unique_ptr<Engine> owned = Engine::create(GameData::default_game_root());
  Engine& engine = *owned;
  std::string error;
  auto rec = load_recording(path, &engine.data(), &error);
  REQUIRE_MESSAGE(rec, error);
  Board b = rec->board;
  engine.end_turn(b, turn_context(*rec, Visibility::Full));
  int scorpions = 0;
  for (const Pawn& p : b.pawns()) {
    if (p.alive() && symbol_name(p.type) == "Scorpion1") ++scorpions;
  }
  CHECK(scorpions > 0);
  fs::remove(path);
}

TEST_CASE("live: a moved flag in the state keeps the unit from moving again") {
  NEED_SESSION();
  std::ifstream in(kCaveT2);
  json state = json::parse(in);
  int mech = -1;
  for (json& u : state["units"]) {
    if (u["team"] == 1 && u.value("mech", false) && u.value("active", false)) {
      u["moved"] = true;
      mech = u["uid"];
      break;
    }
  }
  REQUIRE(mech >= 0);
  const fs::path path = temp_file("itb_live_test_moved.json", state);
  const json r = S.handle({{"cmd", "solve"}, {"state", path.string()}, {"time_limit", 2.0}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  for (const json& s : r["steps"]) CHECK_FALSE((s["sub"] == "move" && s["uid"] == mech));
  fs::remove(path);
}

namespace {

const json* board_unit(const json& board, int uid) {
  for (const json& u : board["units"]) {
    if (u["uid"] == uid) return &u;
  }
  return nullptr;
}

}  // namespace

TEST_CASE("live: boards carry each unit's queued shot; smoke clears it (live 2026-10-10 m36 turn 2)") {
  NEED_SESSION();
  // Mission_Filler turn 2. DStrikeMech's Defensestrike pushes Firefly2#941
  // into smoke; JetMech's Aerial Bombs smoke F3 under Beetle2#943; GravMech
  // then pulls the Beetle out to E3. Both shots are gone for good (Pawn::OnLoop
  // clears a smoked Vek's queued shot); Scarab2#942's only moves with it.
  const std::string start = std::string(ITB_FIXTURE_DIR) + "/live_filler_t2_solve_input.json";
  const json plan = json::array({
      {{"uid", 1}, {"move", {1, 4}}, {"kind", "weapon"}, {"weapon", "Ranged_Defensestrike_A"}, {"target", {4, 4}}},
      {{"uid", 0}, {"move", {5, 3}}, {"kind", "weapon"}, {"weapon", "Brute_Jetmech_A"}, {"target", {5, 1}}},
      {{"uid", 2}, {"move", {5, 4}}, {"kind", "weapon"}, {"weapon", "Science_Gravwell"}, {"target", {5, 2}}},
  });
  const json r = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", plan}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  REQUIRE(r["refused"] == -1);
  const json* beetle = board_unit(r["start"], 943);
  REQUIRE(beetle);
  CHECK((*beetle)["queued"]["target"] == json::array({4, 2}));
  CHECK((*beetle)["queued"]["weapon"] == 0);
  const json* mech = board_unit(r["start"], 0);
  REQUIRE(mech);
  CHECK((*mech)["queued"].is_null());

  const json& steps = r["steps"];
  REQUIRE(steps.size() == 6);
  // Step 1: the Defensestrike; step 3: the Aerial Bombs; step 5: the Gravwell.
  CHECK((*board_unit(steps[1]["board"], 941))["queued"].is_null());
  CHECK_FALSE((*board_unit(steps[1]["board"], 943))["queued"].is_null());
  CHECK((*board_unit(steps[3]["board"], 943))["queued"].is_null());
  const json* pulled = board_unit(steps[5]["board"], 943);
  REQUIRE(pulled);
  CHECK(((*pulled)["x"] == 5 && (*pulled)["y"] == 3));
  CHECK((*pulled)["queued"].is_null());
  const json* scarab = board_unit(steps[5]["board"], 942);
  REQUIRE(scarab);
  CHECK((*scarab)["queued"]["target"] == json::array({4, 3}));

  // The bridge's snapshot before End Turn still has the Beetle's shot (read
  // from the save). As exported, the engine charges the Beetle into the
  // Earth Mover; with the shot dropped (what scripts/live_play.py now gives
  // it) the Beetle blocks the E3 spawn and dies, and the Filler_Pawn lives,
  // as in the game.
  std::ifstream in(std::string(ITB_FIXTURE_DIR) + "/live_filler_t2_end_turn.json");
  json wrapped = json::parse(in);
  const fs::path stale = temp_file("itb_live_test_filler_stale.json", wrapped);
  const json before = S.handle({{"cmd", "predict"}, {"state", stale.string()}, {"plan", json::array()}});
  REQUIRE_MESSAGE(before["ok"].get<bool>(), before.dump());
  CHECK(board_unit(before["after_enemy"], 943) != nullptr);
  CHECK(board_unit(before["after_enemy"], 938) == nullptr);
  for (json& u : wrapped["data"]["bridge_state"]["units"]) {
    if (u["uid"] == 943 || u["uid"] == 941) {
      u["has_queued_attack"] = false;
      u.erase("queued_target");
      u.erase("queued_origin");
    }
  }
  const fs::path fixed = temp_file("itb_live_test_filler_fixed.json", wrapped);
  const json after = S.handle({{"cmd", "predict"}, {"state", fixed.string()}, {"plan", json::array()}});
  REQUIRE_MESSAGE(after["ok"].get<bool>(), after.dump());
  CHECK(board_unit(after["after_enemy"], 943) == nullptr);
  CHECK(board_unit(after["after_enemy"], 938) != nullptr);
  fs::remove(stale);
  fs::remove(fixed);
}

TEST_CASE("live: the dam's second tile is occupied (live 2026-10-10 m46 turn 1)") {
  NEED_SESSION();
  // Mission_Dam: Dam_Pawn#2335 at H4 (4,0) with ExtraSpaces {(1,0)} also
  // stands on H3 (5,0); the bridge lists that tile as a second entry with
  // "is_extra_tile". The solver planned InfernoMech#0 onto H3 and the game
  // refused the move.
  const std::string start = std::string(ITB_FIXTURE_DIR) + "/live_dam_t1_solve_input.json";
  const GameData data = GameData::load(GameData::default_game_root());
  std::string error;
  auto rec = load_recording(start, &data, &error);
  REQUIRE_MESSAGE(rec.has_value(), error);
  const Pawn* dam = rec->board.find_pawn(2335);
  REQUIRE(dam);
  CHECK(dam->extra_tile() == Point{5, 0});
  CHECK(rec->board.pawn_at({5, 0}) == dam);
  for (const std::string& w : rec->warnings) CHECK_MESSAGE(w.find("extra") == std::string::npos, w);
  int dams = 0;
  for (const Pawn& p : rec->board.pawns()) dams += p.uid == 2335 ? 1 : 0;
  CHECK(dams == 1);

  const json bad = json::array({{{"uid", 0}, {"move", {5, 0}}}});
  const json r = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", bad}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  CHECK(r["refused"] == 0);
  // The board export lists the dam once.
  int listed = 0;
  for (const json& u : r["start"]["units"]) listed += u["uid"] == 2335 ? 1 : 0;
  CHECK(listed == 1);

  // The plan the engine now finds: from G3 (5,1), flame H3 (5,0), which
  // hits the dam.
  const json good = json::array({
      {{"uid", 0}, {"move", {5, 1}}, {"kind", "weapon"}, {"weapon", "Prime_Flamespreader"}, {"target", {5, 0}}},
  });
  const json r2 = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", good}});
  REQUIRE_MESSAGE(r2["ok"].get<bool>(), r2.dump());
  CHECK(r2["refused"] == -1);
  int hp = -1;
  for (const json& u : r2["after_player"]["units"]) {
    if (u["uid"] == 2335) hp = u["hp"].get<int>();
  }
  CHECK(hp < 2);
}

namespace {

bool unit_webbed(const json& board, int uid) {
  for (const json& u : board["units"]) {
    if (u["uid"] == uid) return u.value("web", false);
  }
  FAIL("unit " << uid << " not on the board");
  return false;
}

constexpr uint8_t dir_bit(Dir d) { return static_cast<uint8_t>(1u << static_cast<int>(d)); }

}  // namespace

TEST_CASE("live: a mech webbed by two Scorpions stays webbed when one is swapped away (live 2026-10-10 m10 t2)") {
  NEED_SESSION();
  // Mission_Train turn 2: InfernoMech#0 at F3 (5,2) is webbed by
  // Scorpion1#2391 at G3 (5,1) and Scorpion2#2392 at E3 (5,3), both queued
  // on F3. The bridge names one source (2391). TeleMech#2 moves to H3 (5,0)
  // and swaps with the Scorpion at G3: that web breaks, the other holds; the
  // game kept the mech webbed.
  const std::string start = std::string(ITB_FIXTURE_DIR) + "/live_train_t2_solve_input.json";
  const GameData data = GameData::load(GameData::default_game_root());
  std::string error;
  auto rec = load_recording(start, &data, &error);
  REQUIRE_MESSAGE(rec.has_value(), error);
  const Board& b = rec->board;
  REQUIRE(b.find_pawn(0)->webbed);
  CHECK(b.tile({5, 2}).web_in == 2);
  CHECK(b.tile({5, 1}).web_out == dir_bit(Dir::Down));
  CHECK(b.tile({5, 3}).web_out == dir_bit(Dir::Up));
  CHECK(web_sources(b, {5, 2}) == (dir_bit(Dir::Up) | dir_bit(Dir::Down)));

  const json plan = json::array(
      {{{"uid", 2}, {"move", {5, 0}}, {"kind", "weapon"}, {"weapon", "Science_Swap"}, {"target", {5, 1}}}});
  const json r = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", plan}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  CHECK(r["refused"] == -1);
  CHECK(unit_webbed(r["after_player"], 0));
  CHECK_FALSE(unit_webbed(r["after_player"], 2));
}

TEST_CASE("live: the train is webbed through its second tile (live 2026-10-10 m10 t3)") {
  NEED_SESSION();
  // Mission_Train turn 3: Train_Pawn#2390 at F4 (4,2) also stands on F5
  // (4,3). Scorpion2#2392 at F6 (4,4) is queued on F5 and webs the train
  // through that tile; the bridge guessed Scorpion1#2391 at F3 (4,1), which
  // is queued elsewhere. IgniteMech#1 fires Ranged_Ignite at F4, pushing the
  // Scorpion at F3 away: the game kept the train webbed.
  const std::string start = std::string(ITB_FIXTURE_DIR) + "/live_train_t3_solve_input.json";
  const GameData data = GameData::load(GameData::default_game_root());
  std::string error;
  auto rec = load_recording(start, &data, &error);
  REQUIRE_MESSAGE(rec.has_value(), error);
  const Board& b = rec->board;
  REQUIRE(b.find_pawn(2390)->webbed);
  CHECK(b.tile({4, 3}).web_in == 1);
  CHECK(b.tile({4, 4}).web_out == dir_bit(Dir::Up));
  CHECK(b.tile({4, 1}).web_out == 0);
  CHECK(b.tile({4, 2}).web_in == 0);
  // TeleMech#2 at G4 (5,2) is webbed by Scorpion1#2405 at G5 (5,3).
  CHECK(b.tile({5, 3}).web_out == dir_bit(Dir::Up));

  const json plan = json::array(
      {{{"uid", 1}, {"move", {2, 2}}, {"kind", "weapon"}, {"weapon", "Ranged_Ignite"}, {"target", {4, 2}}}});
  const json r = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", plan}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  CHECK(r["refused"] == -1);
  CHECK(unit_webbed(r["after_player"], 2390));
  CHECK_FALSE(unit_webbed(r["after_player"], 2));  // pushed off its tile
}

TEST_CASE("live: bad requests answer ok=false") {
  NEED_SESSION();
  CHECK(S.handle({{"cmd", "ping"}})["ok"] == true);
  CHECK(S.handle({{"cmd", "dance"}})["ok"] == false);
  CHECK(S.handle({{"cmd", "board"}})["ok"] == false);
  CHECK(S.handle({{"cmd", "board"}, {"state", "/nonexistent/state.json"}})["ok"] == false);
  CHECK(S.handle(json::array())["ok"] == false);
  const json no_target = S.handle({{"cmd", "predict"},
                                   {"state", kCaveT2.string()},
                                   {"plan", json::array({{{"uid", 0}, {"kind", "weapon"}, {"weapon", "Prime_Punchmech"}}})}});
  CHECK(no_target["ok"] == false);
  // A plan the engine refuses is reported, not executed past.
  const json refused = S.handle({{"cmd", "predict"},
                                 {"state", kCaveT2.string()},
                                 {"plan", json::array({{{"uid", 0}, {"move", {0, 0}}, {"kind", "none"}}})}});
  REQUIRE(refused["ok"] == true);
  CHECK(refused["refused"] == 0);
  CHECK_FALSE(refused.contains("after_enemy"));
}

namespace {

const json* underground_unit(const json& board, int uid) {
  if (!board.contains("underground")) return nullptr;
  for (const json& u : board["underground"]) {
    if (u["uid"] == uid) return &u;
  }
  return nullptr;
}

}  // namespace

TEST_CASE("live: a hurt Burrower leaves the board and is exported underground (live 2026-10-10 m20 turn 2)") {
  NEED_SESSION();
  // Mission_Reactivation turn 2: LaserMech at F7 fires at E7; the beam hits
  // Burrower1#1683 at D7 for 2 (3 -> 1). It dives and the bridge's next
  // snapshot no longer lists it.
  const std::string start = std::string(ITB_FIXTURE_DIR) + "/live_reactivation_t2_step2.json";
  const json plan = json::array(
      {{{"uid", 0}, {"kind", "weapon"}, {"weapon", "Prime_Lasermech_A"}, {"target", {1, 3}}}});
  const json r = S.handle({{"cmd", "predict"}, {"state", start}, {"plan", plan}});
  REQUIRE_MESSAGE(r["ok"].get<bool>(), r.dump());
  REQUIRE(r["refused"] == -1);
  REQUIRE(board_unit(r["start"], 1683) != nullptr);
  CHECK(r["start"]["underground"].empty());
  const json& after = r["steps"].back()["board"];
  CHECK(board_unit(after, 1683) == nullptr);
  const json* dove = underground_unit(after, 1683);
  REQUIRE(dove);
  CHECK((*dove)["hp"] == 1);
  CHECK(((*dove)["x"] == 1 && (*dove)["y"] == 4));

  // The end-turn board as the bridge has it (no Burrower) plus the Burrower
  // as live_play carries it over: it loads underground, stays alive and
  // underground through the enemy phase (it resurfaces in the AI's move).
  std::ifstream in(std::string(ITB_FIXTURE_DIR) + "/live_reactivation_t2_end_turn.json");
  json wrapped = json::parse(in);
  json unit = *dove;
  wrapped["data"]["bridge_state"]["units"].push_back(unit);
  const fs::path carried = temp_file("itb_live_test_reactivation_underground.json", wrapped);
  const json e = S.handle({{"cmd", "predict"}, {"state", carried.string()}, {"plan", json::array()}});
  REQUIRE_MESSAGE(e["ok"].get<bool>(), e.dump());
  CHECK(board_unit(e["start"], 1683) == nullptr);
  REQUIRE(underground_unit(e["start"], 1683) != nullptr);
  CHECK(board_unit(e["after_enemy"], 1683) == nullptr);
  const json* still = underground_unit(e["after_enemy"], 1683);
  REQUIRE(still);
  CHECK((*still)["hp"] == 1);
  fs::remove(carried);
}
