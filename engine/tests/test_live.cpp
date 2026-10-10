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
