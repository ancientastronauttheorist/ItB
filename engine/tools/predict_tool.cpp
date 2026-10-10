// itb_inspect --predict: the engine's prediction for one bridge state, for
// comparing with the live game (engine/LIVE_TEST_PLAN.md).
//
//   itb_inspect --predict <state.json> [--actions JSON|@FILE] [--no-enemy]
//               [--branches [N]] [--json FILE]
//
// Runs the player's actions, then (unless --no-enemy) Engine::end_turn up to
// the end of the spawns, with the recording's full information (spawn types
// and queue order, Visibility::Full). Prints, per outcome, the chance
// choices taken, the phase events in order and every change against the
// input board. --branches enumerates the hidden choices of the enemy phase
// (Lightning order, ...; at most N outcomes, default 64); without it only
// the first branch runs. Grid Defense never resists here: a resisted hit
// shows up as a building that kept its HP. --json writes the outcomes'
// boards in the bridge's field names for scripts/live_validate.py.
//
// Actions: [{"uid": 0, "move": [x, y], "weapon": "Prime_Punchmech_B" or
// "slot": 0, "target": [x, y], "target2": [x, y]}, {"uid": 1, "repair": true}]
// (bridge coordinates).

#include "predict_tool.hpp"

#include <cstdio>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "itb/engine.hpp"
#include "itb/format.hpp"
#include "itb/game_data.hpp"
#include "itb/recording.hpp"

namespace fs = std::filesystem;
using nlohmann::json;

namespace itb::tools {
namespace {

Point jpoint(const json& j) {
  if (!j.is_array() || j.size() < 2 || !j[0].is_number() || !j[1].is_number()) return kInvalidPoint;
  return {j[0].get<int>(), j[1].get<int>()};
}

const char* chance_name(ChanceKind k) {
  switch (k) {
    case ChanceKind::GridDefense: return "GridDefense";
    case ChanceKind::SpiderEgg: return "SpiderEgg";
    case ChanceKind::LuaRandom: return "LuaRandom";
    case ChanceKind::EnvOrder: return "EnvOrder";
    case ChanceKind::EnvChoice: return "EnvChoice";
    case ChanceKind::MissionRandom: return "MissionRandom";
  }
  return "?";
}

// The bridge's terrain names.
std::string bridge_terrain(const Tile& t) {
  if (t.lava && t.terrain == Terrain::Water) return "lava";
  switch (t.terrain) {
    case Terrain::Road: return "ground";
    case Terrain::Building: return "building";
    case Terrain::Rubble: return "rubble";
    case Terrain::Water: return "water";
    case Terrain::Mountain: return "mountain";
    case Terrain::Ice: return "ice";
    case Terrain::Forest: return "forest";
    case Terrain::Sand: return "sand";
    case Terrain::Hole: return "chasm";
    default: return "terrain" + std::to_string(static_cast<int>(t.terrain));
  }
}

struct Action {
  int32_t uid = -1;
  Point move = kInvalidPoint;
  bool repair = false;
  std::string weapon;  // empty: move only
  int slot = -1;
  Point target = kInvalidPoint;
  std::optional<Point> target2;
};

bool parse_actions(const std::string& text, std::vector<Action>& out, std::string* error) {
  std::string body = text;
  if (!body.empty() && body[0] == '@') {
    std::ifstream in(body.substr(1));
    if (!in) {
      *error = "cannot open " + body.substr(1);
      return false;
    }
    std::stringstream ss;
    ss << in.rdbuf();
    body = ss.str();
  }
  json j;
  try {
    j = json::parse(body);
  } catch (const json::exception& e) {
    *error = std::string("bad actions JSON: ") + e.what();
    return false;
  }
  if (!j.is_array()) {
    *error = "actions must be a JSON array";
    return false;
  }
  for (const json& a : j) {
    Action act;
    act.uid = a.value("uid", -1);
    if (auto it = a.find("move"); it != a.end()) act.move = jpoint(*it);
    act.repair = a.value("repair", false);
    act.weapon = a.value("weapon", "");
    act.slot = a.value("slot", -1);
    if (auto it = a.find("target"); it != a.end()) act.target = jpoint(*it);
    if (auto it = a.find("target2"); it != a.end()) act.target2 = jpoint(*it);
    out.push_back(act);
  }
  return true;
}

json board_json(const Board& b) {
  json units = json::array();
  for (const Pawn& p : b.pawns()) {
    units.push_back({{"uid", p.uid},
                     {"type", std::string(symbol_name(p.type))},
                     {"x", p.pos.x},
                     {"y", p.pos.y},
                     {"hp", p.hp},
                     {"max_hp", p.max_hp},
                     {"team", static_cast<int>(p.team)},
                     {"alive", p.alive() && !p.fallen},
                     {"fire", p.fire},
                     {"acid", p.acid},
                     {"shield", p.shield},
                     {"frozen", p.frozen},
                     {"web", p.webbed}});
  }
  json tiles = json::array();
  for (int i = 0; i < kTileCount; ++i) {
    const Point p = Point::from_index(i);
    const Tile& t = b.tile(p);
    json tj = {{"x", p.x},
               {"y", p.y},
               {"terrain", bridge_terrain(t)},
               {"fire", t.on_fire()},
               {"smoke", t.smoke},
               {"acid", t.acid},
               {"cracked", t.cracked},
               {"frozen", t.frozen},
               {"shield", t.shield}};
    if (t.is_building() || t.is_mountain()) tj["building_hp"] = t.hp;
    if (t.terrain == Terrain::Ice) tj["ice_hp"] = t.hp;
    if (t.item != kNoSymbol) tj["item"] = std::string(symbol_name(t.item));
    tiles.push_back(tj);
  }
  return {{"grid_power", b.grid_power}, {"units", units}, {"tiles", tiles}};
}

std::string pawn_label(const Pawn& p) {
  return std::string(symbol_name(p.type)) + "#" + std::to_string(p.uid);
}

std::string where(Point p) { return p.valid() ? to_visual(p) : "off-board"; }

// Every change from `before` to `after`, one line each.
std::vector<std::string> board_changes(const Board& before, const Board& after) {
  std::vector<std::string> out;
  auto flag = [&](const std::string& who, const char* name, bool a, bool b) {
    if (a != b) out.push_back(who + " " + name + " " + (a ? "on" : "off") + " -> " + (b ? "on" : "off"));
  };
  for (const Pawn& p : before.pawns()) {
    const std::string who = pawn_label(p);
    const Pawn* q = after.find_pawn(p.uid);
    if (q && q->type != p.type) q = nullptr;
    if (!q) {
      out.push_back(who + " " + where(p.pos) + ": removed");
      continue;
    }
    if (p.alive() && !(q->alive() && !q->fallen)) {
      out.push_back(who + " " + where(p.pos) + ": died" + (q->fallen ? " (fell)" : "") + " at " +
                    where(q->pos));
      continue;
    }
    if (p.pos != q->pos) out.push_back(who + " moved " + where(p.pos) + " -> " + where(q->pos));
    if (p.hp != q->hp) {
      out.push_back(who + " " + where(q->pos) + " hp " + std::to_string(p.hp) + " -> " + std::to_string(q->hp));
    }
    flag(who, "fire", p.fire, q->fire);
    flag(who, "acid", p.acid, q->acid);
    flag(who, "shield", p.shield, q->shield);
    flag(who, "frozen", p.frozen, q->frozen);
    flag(who, "webbed", p.webbed, q->webbed);
    if (p.queued.active() && !q->queued.active()) out.push_back(who + " queued shot gone");
  }
  for (const Pawn& q : after.pawns()) {
    const Pawn* p = before.find_pawn(q.uid);
    if (p && p->type == q.type) continue;
    out.push_back("new " + pawn_label(q) + " at " + where(q.pos) + " hp " + std::to_string(q.hp) +
                  (q.alive() ? "" : " (dead)"));
  }
  for (int i = 0; i < kTileCount; ++i) {
    const Point pt = Point::from_index(i);
    const Tile& a = before.tile(pt);
    const Tile& b = after.tile(pt);
    if (a == b) continue;
    const std::string who = "tile " + to_visual(pt);
    if (bridge_terrain(a) != bridge_terrain(b)) {
      out.push_back(who + " " + bridge_terrain(a) + " -> " + bridge_terrain(b));
    }
    if (a.hp != b.hp) out.push_back(who + " hp " + std::to_string(a.hp) + " -> " + std::to_string(b.hp));
    flag(who, "fire", a.on_fire(), b.on_fire());
    flag(who, "smoke", a.smoke, b.smoke);
    flag(who, "acid", a.acid, b.acid);
    flag(who, "cracked", a.cracked, b.cracked);
    flag(who, "frozen", a.frozen, b.frozen);
    flag(who, "shield", a.shield, b.shield);
    if (a.item != b.item) out.push_back(who + " item changed");
  }
  if (before.grid_power != after.grid_power) {
    out.push_back("grid " + std::to_string(before.grid_power) + " -> " + std::to_string(after.grid_power));
  }
  return out;
}

struct Outcome {
  std::vector<std::pair<ChanceKind, std::pair<int, int>>> choices;  // kind, (pick, options)
  std::vector<std::string> action_status;
  PhaseResult phase;
  bool ran_enemy = false;
  Board board;
};

}  // namespace

int run_predict(const PredictOptions& opt) {
  std::unique_ptr<Engine> engine;
  try {
    engine = Engine::create(opt.game);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    return 1;
  }
  std::string error;
  auto rec = load_recording(opt.state, &engine->data(), &error);
  if (!rec) {
    std::fprintf(stderr, "error: %s\n", error.c_str());
    return 1;
  }
  std::vector<Action> actions;
  if (!opt.actions.empty() && !parse_actions(opt.actions, actions, &error)) {
    std::fprintf(stderr, "error: %s\n", error.c_str());
    return 1;
  }
  Board start = rec->board;
  std::map<int32_t, std::string> repair_skill;
  for (const auto& [uid, pilot] : rec->pilots) {
    if (Pawn* p = start.find_pawn(uid)) {
      p->pilot_abilities |= engine->pilot_ability(pilot);
      repair_skill[uid] = engine->repair_skill(pilot);
    }
  }
  TurnContext ctx = turn_context(*rec, Visibility::Full);

  std::vector<Outcome> outcomes;
  std::vector<std::vector<int>> todo{{}};
  const int max_outcomes = opt.branches ? opt.max_branches : 1;
  while (!todo.empty() && static_cast<int>(outcomes.size()) < max_outcomes) {
    const std::vector<int> prefix = todo.back();
    todo.pop_back();
    Outcome out;
    out.board = start;
    size_t call = 0;
    ctx.choose = [&](const ChanceRecord& node) {
      const int pick = call < prefix.size() ? prefix[call] : 0;
      ++call;
      out.choices.push_back({node.kind, {pick, node.options}});
      return pick;
    };
    bool refused = false;
    const ActionOptions ao = action_options(ctx);  // the mission's per-frame hooks, ctx.choose
    for (const Action& a : actions) {
      if (a.move.valid()) {
        const ActionResult r = engine->move(out.board, a.uid, a.move, ao);
        out.action_status.push_back("#" + std::to_string(a.uid) + " move " + where(a.move) + ": " +
                                    to_string(r.status));
        if (!r.ok()) refused = true;
      }
      if (a.repair) {
        auto it = repair_skill.find(a.uid);
        const ActionResult r =
            engine->repair(out.board, a.uid, kInvalidPoint, it != repair_skill.end() ? it->second : "Skill_Repair", ao);
        out.action_status.push_back("#" + std::to_string(a.uid) + " repair: " + std::string(to_string(r.status)));
        if (!r.ok()) refused = true;
      } else if (!a.weapon.empty() || a.slot >= 0) {
        ActionResult r = !a.weapon.empty()
                             ? engine->fire_weapon(out.board, a.uid, a.weapon, a.target, a.target2, ao)
                             : engine->fire_weapon(out.board, a.uid, a.slot, a.target, a.target2, ao);
        out.action_status.push_back("#" + std::to_string(a.uid) + " " + r.weapon + " at " + where(a.target) +
                                    (a.target2 ? " then " + where(*a.target2) : "") + ": " +
                                    to_string(r.status) +
                                    (r.resolve.timing_sensitive() ? " (timing-sensitive)" : ""));
        if (!r.ok()) refused = true;
      }
    }
    if (opt.enemy && !refused) {
      out.phase = engine->end_turn(out.board, ctx);
      out.ran_enemy = true;
    }
    // Branch on every choice made beyond the forced prefix.
    for (size_t j = out.choices.size(); j-- > prefix.size();) {
      for (int b = 1; b < out.choices[j].second.second; ++b) {
        std::vector<int> next = prefix;
        next.resize(j, 0);
        next.push_back(b);
        todo.push_back(next);
      }
    }
    outcomes.push_back(std::move(out));
  }

  std::printf("%s: %s turn %d, %zu action(s)%s, %zu outcome(s)%s\n", opt.state.filename().string().c_str(),
              rec->mission_id.c_str(), rec->board.turn, actions.size(), opt.enemy ? " + enemy phase" : "",
              outcomes.size(), todo.empty() ? "" : " (more branches not run)");
  if (!rec->spawn_types.empty()) {
    std::printf("spawn queue (%s):", rec->spawn_order_known ? "queue order" : "scan order");
    for (size_t i = 0; i < rec->board.spawn_points.size(); ++i) {
      std::printf(" %s %s", where(rec->board.spawn_points[i]).c_str(),
                  i < rec->spawn_types.size() && !rec->spawn_types[i].empty() ? rec->spawn_types[i].c_str() : "?");
    }
    std::printf("\n");
  }
  for (const std::string& w : rec->warnings) std::printf("warning: %s\n", w.c_str());
  json jout = json::array();
  for (size_t k = 0; k < outcomes.size(); ++k) {
    const Outcome& o = outcomes[k];
    std::printf("\n== outcome %zu", k + 1);
    for (const auto& [kind, pick] : o.choices) {
      std::printf(" [%s %d/%d]", chance_name(kind), pick.first + 1, pick.second);
    }
    std::printf("\n");
    for (const std::string& s : o.action_status) std::printf("  action %s\n", s.c_str());
    json events = json::array();
    if (o.ran_enemy) {
      if (!o.phase.exact) std::printf("  (engine says inexact for this mission)\n");
      if (o.phase.timing_sensitive()) std::printf("  (timing-sensitive outcome)\n");
      for (const PhaseEvent& e : o.phase.events) {
        if (e.type == PhaseEventType::StatusTick && e.detail.empty()) continue;
        std::string line = std::string(to_string(e.type));
        if (e.uid >= 0) {
          const Pawn* p = start.find_pawn(e.uid);
          if (!p) p = o.board.find_pawn(e.uid);
          line += " " + (p ? pawn_label(*p) : "#" + std::to_string(e.uid));
        }
        if (e.point.valid()) line += " " + to_visual(e.point);
        if (e.amount) line += " (" + std::to_string(e.amount) + ")";
        if (!e.detail.empty()) line += ": " + e.detail;
        std::printf("  event %s\n", line.c_str());
        events.push_back({{"type", to_string(e.type)},
                          {"uid", e.uid},
                          {"x", e.point.x},
                          {"y", e.point.y},
                          {"amount", e.amount},
                          {"detail", e.detail}});
      }
      for (const std::string& err : o.phase.lua_errors) std::printf("  lua error: %s\n", err.c_str());
    }
    for (const std::string& c : board_changes(start, o.board)) std::printf("  %s\n", c.c_str());
    json choices = json::array();
    for (const auto& [kind, pick] : o.choices) {
      choices.push_back({{"kind", chance_name(kind)}, {"pick", pick.first}, {"options", pick.second}});
    }
    jout.push_back({{"choices", choices},
                    {"actions", o.action_status},
                    {"enemy_phase", o.ran_enemy},
                    {"exact", o.phase.exact},
                    {"timing_sensitive", o.phase.timing_sensitive()},
                    {"events", events},
                    {"board", board_json(o.board)}});
  }
  if (!opt.json_out.empty()) {
    std::ofstream f(opt.json_out);
    f << json{{"state", opt.state.string()}, {"start", board_json(start)}, {"outcomes", jout}}.dump(1) << "\n";
  }
  return 0;
}

}  // namespace itb::tools
