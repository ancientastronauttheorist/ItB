// itb_inspect --replay DIR --turns: whole turns against the game.
//
// For every turn whose recorded plan the per-action replay could follow to
// its end (replay.cpp; each step synced to what the game recorded), the
// engine runs the enemy phase (Engine::end_turn) and the result is compared
// with the game's board at the start of the next turn.
//
// When that board was captured. The old bot recorded the next turn's board
// when the next player turn began (src/loop/commands.py: the post-enemy audit
// fires once the bridge reports phase combat_player with active mechs; the
// next m<NN>_turn_<t+1>_solve_input.json is the same board, read before any
// action). Between the end of the enemy's spawns, where Engine::end_turn
// stops, and that capture the game ran AI planning and movement
// (Vek move, queue attacks, place web grapples, new spawn markers) and the
// player's turn start (Zoltan shields, Opener/Closer boosts). So the fields
// compared are the ones those steps cannot change:
//   grid power; every tile's terrain, structure HP, fire, ACID, smoke, pod;
//   mechs and other player units: alive, HP, position, fire/ACID/frozen/shield;
//   enemies by uid: alive, HP, frozen (not position, fire or ACID: the AI
//   moves them, possibly onto fire or ACID);
//   how many enemies emerged.
// The last turn of a mission has no next board; there the post-enemy summary
// (m<NN>_turn_<t>_post_enemy.json, data.actual_outcome) gives grid power,
// buildings and mech HP.

#include <algorithm>
#include <array>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "itb/format.hpp"
#include "itb/game_data.hpp"
#include "replay.hpp"

namespace fs = std::filesystem;
using nlohmann::json;

namespace itb::tools {
namespace {

struct Diff {
  std::string field;
  std::string where;
  std::string engine;
  std::string actual;
  Point tile = kInvalidPoint;
  std::string why;  // known cause outside the engine ("" = unexplained)
};

std::string terrain_kind(const Tile& t) {
  switch (t.terrain) {
    case Terrain::Road: return "ground";
    case Terrain::Building: return t.hp > 0 ? "building" : "rubble";
    case Terrain::Rubble: return "rubble";
    case Terrain::Water: return t.lava ? "lava" : "water";
    case Terrain::Mountain: return "mountain";
    case Terrain::Ice: return "ice";
    case Terrain::Forest: return "forest";
    case Terrain::Sand: return "sand";
    case Terrain::Hole: return "chasm";
    default: return "terrain" + std::to_string(static_cast<int>(t.terrain));
  }
}

std::string s(bool b) { return b ? "true" : "false"; }
std::string s(int v) { return std::to_string(v); }
std::string s(Point p) { return p.valid() ? to_visual(p) : "-"; }

std::string name(const Pawn& p) { return std::string(symbol_name(p.type)) + "#" + std::to_string(p.uid); }

bool on_board(const Pawn& p) { return p.alive() && !p.fallen && p.pos.valid(); }

bool detail_contains(const Pawn& p, std::string_view part) {
  return symbol_name(p.type).find(part) != std::string_view::npos;
}

// A multi-tile pawn may be reported by its other tile.
bool extra_tile(const GameData& data, const Pawn& p, Point reported) {
  const PawnDef* def = data.pawn(p.type);
  if (!def) return false;
  for (Point e : def->extra_spaces) {
    if (p.pos + e == reported || reported + e == p.pos) return true;
  }
  return false;
}

// Pawns created by AI planning's instant effects (Digger rock walls, spider
// eggs hatching into spiderlings), between the two boards.
bool ai_planning_type(std::string_view t) {
  return t == "Wall" || t == "Spiderling1" || t == "WebbEgg1" || t == "Blob1" || t == "Blob2" ||
         t.starts_with("Totem") || t == "BombRock";
}

// Pawns whose planned attack creates pawns at once (Spider eggs, Blobber
// blobs, Digger walls, Shaman totems, egg hatching).
bool ai_planning_spawner(const Pawn& p) {
  const std::string_view t = symbol_name(p.type);
  return t.starts_with("Spider") || t.starts_with("Blobber") || t.starts_with("Digger") ||
         t.starts_with("Shaman") || t == "SpiderlingEgg1" || t == "WebbEgg1" || t.starts_with("Bomber");
}
bool ai_planning_pawn(const Pawn& p) { return ai_planning_type(symbol_name(p.type)); }

// The next board was read after the next turn had begun: a mech already
// acted (inactive at the start of its turn), or moved further than any
// enemy-phase push could take it.
std::string stale_reason(const Board& e, const Board& next) {
  for (const Pawn& q : next.pawns()) {
    if (!q.mech || q.team != Team::Player || !q.alive()) continue;
    if (!q.active && !q.frozen) return "a mech had already acted";
    const Pawn* p = e.find_pawn(q.uid);
    if (p && p->pos.valid() && q.pos.valid() && e.teleporters.empty() &&
        std::abs(p->pos.x - q.pos.x) + std::abs(p->pos.y - q.pos.y) > 2) {
      return "a mech had already moved";
    }
  }
  return "";
}

std::vector<Diff> compare_next(const Board& e, const PhaseResult& pr, const Board& start, const Board& next,
                               const GameData& data, const std::string& mission) {
  std::vector<Diff> out;
  auto add = [&](std::string field, std::string where, std::string engine, std::string actual,
                 Point tile = kInvalidPoint, std::string why = "") {
    out.push_back(Diff{std::move(field), std::move(where), std::move(engine), std::move(actual), tile, std::move(why)});
  };
  if (e.grid_power != next.grid_power) add("grid_power", "grid", s(e.grid_power), s(next.grid_power));
  // What AI planning leaves behind: instant smoke on a queued target
  // (Mosquitoes), ACID pools picked up by a Vek stopping on them.
  auto queued_on = [&](Point p) {
    return std::any_of(next.pawns().begin(), next.pawns().end(),
                       [&](const Pawn& q) { return q.alive() && q.queued.active() && q.queued.target == p; });
  };
  for (int i = 0; i < kTileCount; ++i) {
    const Point p = Point::from_index(i);
    const Tile& a = e.tile(p);
    const Tile& b = next.tile(p);
    const std::string where = to_visual(p);
    if (terrain_kind(a) != terrain_kind(b)) {
      add("tile.terrain", where, terrain_kind(a), terrain_kind(b), p,
          terrain_kind(a) == "lava" && terrain_kind(b) == "water" ? "bridge: lava reported as water (no lava flag)"
                                                                  : "");
    }
    const bool structure = (a.is_building() || a.is_mountain()) && (b.is_building() || b.is_mountain());
    if (structure && a.hp != b.hp) add("tile.hp", where, s(a.hp), s(b.hp), p);
    if (a.on_fire() != b.on_fire()) add("tile.fire", where, s(a.on_fire()), s(b.on_fire()), p);
    if (a.acid != b.acid) {
      const Pawn* q = next.pawn_at(p);
      add("tile.acid", where, s(a.acid), s(b.acid), p,
          a.acid && q && q->alive() && q->acid ? "ACID pool picked up by an AI move" : "");
    }
    if (a.smoke != b.smoke) {
      add("tile.smoke", where, s(a.smoke), s(b.smoke), p,
          b.smoke && queued_on(p) ? "AI planning: instant smoke on a queued target" : "");
    }
    const bool pa = a.pod == PodState::Present, pb = b.pod == PodState::Present;
    if (pa != pb) add("tile.pod", where, s(pa), s(pb), p);
  }

  // Pair units: by uid for pawns of the start board; spawned pawns get uids
  // the game picks, so those pair by type and tile. (Pawns the player's
  // weapons created carry the engine's uid, which the game may have given to
  // another pawn: same uid and type, or it is not the same pawn.)
  auto in_start = [&](const Pawn& q) {
    const Pawn* p = start.find_pawn(q.uid);
    return p && p->type == q.type;
  };
  std::map<int32_t, int32_t> pair;  // game uid -> engine uid
  std::set<int32_t> used;
  for (const Pawn& q : next.pawns()) {
    const Pawn* p = e.find_pawn(q.uid);
    if (p && in_start(q) && p->type == q.type) {
      pair[q.uid] = p->uid;
      used.insert(p->uid);
    }
  }
  for (const Pawn& q : next.pawns()) {
    if (pair.count(q.uid) || q.team == Team::Enemy) continue;
    for (const Pawn& p : e.pawns()) {
      if (!used.count(p.uid) && p.type == q.type && p.pos == q.pos && p.alive() == q.alive()) {
        pair[q.uid] = p.uid;
        used.insert(p.uid);
        break;
      }
    }
  }
  std::multiset<std::string> new_engine, new_game;
  const int unknown = static_cast<int>(pr.emerged_unknown.size());
  for (const Pawn& q : next.pawns()) {
    const std::string where = name(q);
    auto it = pair.find(q.uid);
    if (it == pair.end()) {
      if (!q.alive()) continue;
      if (q.team == Team::Enemy && !in_start(q)) {
        new_game.insert(std::string(symbol_name(q.type)));
      } else if (ai_planning_pawn(q)) {
        add("unit.extra", where, "absent", "alive", q.pos, "created during AI planning");
      } else {
        add("unit.alive", where, "absent", "true", q.pos);
      }
      continue;
    }
    const Pawn* p = e.find_pawn(it->second);
    const bool ea = p->alive() && !p->fallen;
    if (ea != q.alive()) {
      add("unit.alive", where, s(ea), s(q.alive()), q.pos);
      continue;
    }
    if (!ea) continue;
    if (p->hp != q.hp) {
      std::string why;
      if (p->mech && q.hp > p->hp && q.max_hp > p->max_hp) why = "pilot level-up (no pilot XP in the bridge)";
      if (!p->mech && q.pos != p->pos && q.pos.valid() && e.tile(q.pos).item != kNoSymbol &&
          next.tile(q.pos).item == kNoSymbol) {
        why = "stepped on an item in AI movement";
      }
      add("unit.hp", where, s(p->hp), s(q.hp), q.pos, why);
    }
    if (q.team == Team::Player) {
      // Mechs and stationary units: nothing moves them in AI planning.
      const bool still = p->mech || detail_contains(*p, "Train") || (p->move == 0 && p->weapons[0] == kNoSymbol);
      if (p->pos != q.pos && !extra_tile(data, *p, q.pos) && still) {
        add("unit.pos", where, s(p->pos), s(q.pos), q.pos);
      }
      if (p->fire != q.fire) {
        add("unit.fire", where, s(p->fire), s(q.fire), q.pos,
            p->mech && p->fire && p->pos.valid() && e.tile(p->pos).on_fire()
                ? "open question: mechs standing in fire (README)"
                : "");
      }
      if (p->acid != q.acid) add("unit.acid", where, s(p->acid), s(q.acid), q.pos);
      if (p->shield != q.shield) {
        add("unit.shield", where, s(p->shield), s(q.shield), q.pos,
            q.shield && p->has_pilot(kPilotZoltan) ? "Zoltan shield at turn start" : "");
      }
    }
    if (p->frozen != q.frozen) add("unit.frozen", where, s(p->frozen), s(q.frozen), q.pos);
  }
  for (const Pawn& p : e.pawns()) {
    if (used.count(p.uid) || !on_board(p)) {
      if (!used.count(p.uid) && p.alive() && !p.fallen && !p.pos.valid()) {
        // Burrowed pawns are underground (not in the bridge's unit list).
        add("unit.alive", name(p), "true", "absent", p.pos, "underground (burrowed): resurfaces in AI movement");
      }
      continue;
    }
    if (!in_start(p) && p.team == Team::Enemy) {
      new_engine.insert(std::string(symbol_name(p.type)));
      continue;
    }
    add("unit.alive", name(p), "true", "absent", p.pos,
        symbol_name(p.type) == "SpiderlingEgg1" ? "hatched during AI planning" : "");
  }
  // New enemies: pair equal types, set aside what AI planning creates, then
  // the engine's unknown-type spawns stand for any of the rest.
  for (auto it = new_engine.begin(); it != new_engine.end();) {
    auto g = new_game.find(*it);
    if (g != new_game.end()) {
      new_game.erase(g);
      it = new_engine.erase(it);
    } else {
      ++it;
    }
  }
  int planned = 0;
  for (auto it = new_game.begin(); it != new_game.end();) {
    if (ai_planning_type(*it)) {
      ++planned;
      it = new_game.erase(it);
    } else {
      ++it;
    }
  }
  if (planned > 0) add("enemies.new", "AI planning", "0", s(planned), kInvalidPoint, "created during AI planning");
  // An unknown spawn on a mine dies there (ground Vek; flyers are not known).
  int mined = 0;
  for (Point p : pr.emerged_unknown) mined += e.tile(p).item != kNoSymbol ? 1 : 0;
  const int ne = static_cast<int>(new_engine.size()) + unknown;
  const int ng = static_cast<int>(new_game.size());
  if (ne != ng) {
    std::string why;
    bool mines = false;
    for (int i = 0; i < kTileCount; ++i) mines = mines || e.tile(Point::from_index(i)).item != kNoSymbol;
    if (ng > ne && (mission == "Mission_Factory" || mission == "Mission_SpiderBoss" ||
                    mission == "Mission_BlobBoss" || mission == "Mission_Holes" || mission == "Mission_Acid")) {
      why = "the mission adds pawns in UpdateSpawning (after AI planning)";
    } else if (ne - ng == mined && mined > 0) {
      why = "a spawn of unknown type emerged on a mine";
    } else if (ne > ng && mines) {
      why = "a new Vek may have stepped on a mine in AI movement";
    }
    add("enemies.new", "spawns", s(ne), s(ng), kInvalidPoint, why);
  } else if (unknown == 0 && !new_engine.empty()) {
    add("enemies.type", "spawns", std::to_string(new_engine.size()) + " known", "other types");
  }
  return out;
}

int jint(const json& j, const char* k, int fallback = -1) {
  auto it = j.find(k);
  return it != j.end() && it->is_number() ? it->get<int>() : fallback;
}

// The post-enemy summary (src/loop/commands.py _capture_board_summary) of
// the engine's board; enemies count team-6 pawns with HP (spawns of unknown
// type count as one each, their HP is unknown).
std::vector<Diff> compare_post(const Board& e, const PhaseResult& pr, const json& actual) {
  std::vector<Diff> out;
  auto add = [&](std::string field, std::string where, int engine, int got) {
    if (engine != got) out.push_back(Diff{std::move(field), std::move(where), s(engine), s(got), kInvalidPoint, ""});
  };
  int buildings = 0, building_hp = 0, mechs = 0, enemies = 0, enemy_hp = 0;
  for (int i = 0; i < kTileCount; ++i) {
    const Tile& t = e.tile(Point::from_index(i));
    if (t.is_building() && t.hp > 0) {
      ++buildings;
      building_hp += t.hp;
    }
  }
  for (const Pawn& p : e.pawns()) {
    mechs += p.mech && p.team == Team::Player && p.alive() ? 1 : 0;
    if (p.team == Team::Enemy && p.alive() && !p.fallen) {
      ++enemies;
      enemy_hp += p.hp;
    }
  }
  const int unknown = static_cast<int>(pr.emerged_unknown.size());
  if (jint(actual, "enemies_alive") >= 0) {
    add("enemies_alive", "board", enemies + unknown, jint(actual, "enemies_alive"));
    const bool spawner = std::any_of(e.pawns().begin(), e.pawns().end(),
                                     [](const Pawn& p) { return p.alive() && ai_planning_spawner(p); });
    if (!out.empty() && out.back().field == "enemies_alive" && (spawner || unknown > 0) &&
        jint(actual, "enemies_alive") > enemies + unknown) {
      out.back().why = spawner ? "AI planning adds pawns (summary only: types unknown)"
                               : "a spawn of unknown type may add pawns in AI planning (summary only)";
    }
  }
  if (unknown == 0 && jint(actual, "enemy_hp_total") >= 0) {
    add("enemy_hp_total", "board", enemy_hp, jint(actual, "enemy_hp_total"));
  }
  if (jint(actual, "grid_power") >= 0) add("grid_power", "grid", e.grid_power, jint(actual, "grid_power"));
  if (jint(actual, "buildings_alive") >= 0) add("buildings_alive", "board", buildings, jint(actual, "buildings_alive"));
  if (jint(actual, "building_hp_total") >= 0) {
    add("building_hp_total", "board", building_hp, jint(actual, "building_hp_total"));
  }
  if (jint(actual, "mechs_alive") >= 0) add("mechs_alive", "board", mechs, jint(actual, "mechs_alive"));
  if (auto it = actual.find("mech_hp"); it != actual.end() && it->is_array()) {
    for (const json& m : *it) {
      const Pawn* p = e.find_pawn(jint(m, "uid"));
      if (p) add("unit.hp", name(*p), std::max<int>(0, p->hp), jint(m, "hp", 0));
    }
  }
  return out;
}

json load_json(const fs::path& p) {
  std::ifstream in(p);
  json j;
  in >> j;
  return j;
}

bool real(const std::vector<Diff>& d) {
  return std::any_of(d.begin(), d.end(), [](const Diff& x) { return x.why.empty(); });
}
int real_count(const std::vector<Diff>& d) {
  return static_cast<int>(std::count_if(d.begin(), d.end(), [](const Diff& x) { return x.why.empty(); }));
}

// Stage 8: an objective quantity the engine derived, checked against what the
// game recorded.
struct Check {
  int compared = 0, agree = 0;
  std::vector<std::string> examples;
  void add(bool ok, const std::string& label, int engine, int game) {
    ++compared;
    agree += ok ? 1 : 0;
    if (!ok && examples.size() < 6) {
      examples.push_back(label + ": engine " + std::to_string(engine) + ", game " + std::to_string(game));
    }
  }
};

struct Tally {
  int turns = 0, exact = 0, explained = 0, resist = 0, branch = 0, upgrade = 0, inexact = 0;
  std::map<std::string, int> fields;
  int ok() const { return exact + explained; }
};

std::string pct(int a, int b) {
  char buf[32];
  std::snprintf(buf, sizeof buf, "%5.1f%%", b ? 100.0 * a / b : 0.0);
  return buf;
}

}  // namespace

int report_turns(Engine& engine, const std::vector<TurnStart>& turns, const ReplayOptions& opt) {
  const GameData& data = engine.data();
  std::map<std::string, Tally> by_mission;  // "<set> <mission>"
  Tally all[2];
  std::map<std::string, int> no_truth, truth_kind;
  int spawn_typed = 0;  // turns whose emerged spawn types came from the next board
  std::map<std::string, int> why_count[2];  // explained differences by cause
  std::map<std::string, std::map<std::string, int>> chance_use;
  std::map<std::string, int> events, inexact_why;
  std::vector<std::pair<std::string, std::vector<Diff>>> shown;
  std::map<std::string, Check> checks;  // stage 8 objective checks
  std::map<std::string, std::array<int, 4>> obj_lines;  // id -> lines, failed, progress>0, inexact
  std::vector<std::string> obj_failures;                // every scored failure, for review
  std::ofstream jout;
  if (!opt.json_out.empty()) jout.open(opt.json_out);

  for (const TurnStart& t : turns) {
    const std::string fname = t.input.filename().string();
    if (fname.size() < 12 || fname[0] != 'm') {
      ++no_truth["old file naming"];
      continue;
    }
    const std::string prefix = fname.substr(0, 9);  // m<NN>_turn_
    const int turn_no = std::stoi(fname.substr(9, 2));
    char nb[64], pe[64];
    std::snprintf(nb, sizeof nb, "%s%02d_solve_input.json", prefix.c_str(), turn_no + 1);
    std::snprintf(pe, sizeof pe, "%s%02d_post_enemy.json", prefix.c_str(), turn_no);
    const fs::path next_path = t.input.parent_path() / nb;
    const fs::path post_path = t.input.parent_path() / pe;
    std::optional<Recording> next;
    if (fs::exists(next_path)) {
      std::string err;
      next = load_recording(next_path, &data, &err);
    }
    std::optional<json> post;
    if (fs::exists(post_path)) {
      try {
        const json j = load_json(post_path);
        if (j.contains("data") && j["data"].contains("actual_outcome")) post = j["data"]["actual_outcome"];
      } catch (const std::exception&) {
      }
    }
    if (!next && !post) {
      ++no_truth[t.rec.board.turn == t.rec.board.total_turns ? "final turn without post_enemy" : "no next board"];
      continue;
    }
    const std::string mission = t.rec.mission_id.empty() ? "?" : t.rec.mission_id;
    const std::string key = t.run + "/" + std::to_string(t.rec.mission_index) + "/" + std::to_string(t.rec.turn);
    const bool trace = key == opt.trace;

    // Runs the enemy phase with these chance-node picks / resisted buildings.
    std::vector<std::string> spawn_types;
    auto run = [&](const std::vector<int>& picks, const std::set<int>& resist, PhaseResult& pr,
                   uint32_t passives = 0) {
      Board b = t.board;
      b.passives |= passives;
      TurnContext ctx;
      ctx.mission = t.rec.mission;
      ctx.spawn_types = spawn_types;
      size_t n = 0;
      ctx.choose = [&picks, &n](const ChanceRecord& c) {
        const int v = n < picks.size() ? picks[n] : 0;
        ++n;
        return std::min(v, c.options - 1);
      };
      ctx.grid_resist = [&resist](Point p, int) { return resist.count(p.index()) > 0; };
      pr = engine.end_turn(b, ctx);
      return b;
    };
    PhaseResult pr;
    Board end = run({}, {}, pr);
    // The next board is only the game's post-enemy board if nothing of the
    // next turn happened before it was read.
    const std::string stale = next ? stale_reason(end, next->board) : "";
    const bool use_next = next && stale.empty();
    if (!use_next && !post) {
      ++no_truth["next board read after the next turn began (" + stale + "), no post_enemy"];
      continue;
    }
    // Both captures are of the same moment; when they disagree (one was
    // read minutes later, after something else happened) neither is trusted.
    if (use_next && post) {
      PhaseResult none;
      std::vector<Diff> agree = compare_post(next->board, none, *post);
      std::erase_if(agree, [](const Diff& x) {
        return x.field == "enemies_alive" || x.field == "enemy_hp_total" || x.field == "unit.hp";
      });
      if (!agree.empty()) {
        ++no_truth["next board and post_enemy disagree (" + agree.front().field + ")"];
        continue;
      }
    }
    ++truth_kind[use_next ? "the next turn's board"
                 : next   ? "post_enemy summary (next board stale: " + stale + ")"
                          : "post_enemy summary (no next board)"];
    auto diff = [&](const Board& b, const PhaseResult& p) {
      std::vector<Diff> out;
      // The next board when usable (post_enemy summaries sometimes carry the
      // save file's grid, which lags), else the post-enemy summary.
      if (!use_next) out = compare_post(b, p, *post);
      if (use_next) {
        std::vector<Diff> n = compare_next(b, p, t.board, next->board, data, mission);
        out.insert(out.end(), n.begin(), n.end());
      }
      return out;
    };
    // Spawn types are hidden (decided when queued, not shown). The next board
    // shows what emerged: give those types to the spawns that emerged, in
    // uid order (= queue order) over the spawns in the bridge's scan order,
    // so global effects (a new psion) are modelled. Which tile got which type
    // stays a guess.
    if (use_next && !pr.emerged_unknown.empty()) {
      std::vector<std::pair<int32_t, std::string>> fresh;
      for (const Pawn& q : next->board.pawns()) {
        const Pawn* s0 = t.board.find_pawn(q.uid);
        if (q.team != Team::Enemy || !q.alive() || (s0 && s0->type == q.type) || ai_planning_pawn(q)) continue;
        fresh.emplace_back(q.uid, std::string(symbol_name(q.type)));
      }
      std::sort(fresh.begin(), fresh.end());
      if (fresh.size() == pr.emerged_unknown.size()) {
        spawn_types.assign(t.board.spawn_points.size(), "");
        size_t k = 0;
        for (size_t i = 0; i < t.board.spawn_points.size() && k < fresh.size(); ++i) {
          if (std::find(pr.emerged_unknown.begin(), pr.emerged_unknown.end(), t.board.spawn_points[i]) !=
              pr.emerged_unknown.end()) {
            spawn_types[i] = fresh[k++].second;
          }
        }
        ++spawn_typed;
        end = run({}, {}, pr);
      }
    }
    std::vector<Diff> d = diff(end, pr);
    bool used_branch = false, used_resist = false, used_upgrade = false;
    std::vector<int> best_picks;
    // Hidden choices: try the other branches (up to 64 runs).
    std::vector<int> options;
    for (const ChanceRecord& c : pr.chances) {
      if (c.kind == ChanceKind::EnvOrder || c.kind == ChanceKind::EnvChoice || c.kind == ChanceKind::MissionRandom) {
        options.push_back(c.options);
        ++chance_use[mission][c.kind == ChanceKind::EnvOrder    ? "env order"
                              : c.kind == ChanceKind::EnvChoice ? "env choice"
                                                                : "mission random"];
      }
    }
    if (real(d) && !options.empty()) {
      std::vector<int> picks(options.size(), 0);
      int runs = 0;
      for (;;) {
        size_t k = 0;
        while (k < picks.size() && ++picks[k] >= options[k]) picks[k++] = 0;
        if (k == picks.size() || ++runs > 64) break;
        PhaseResult p2;
        Board b2 = run(picks, {}, p2);
        std::vector<Diff> d2 = diff(b2, p2);
        if (real_count(d2) < real_count(d)) {
          end = b2;
          pr = p2;
          d = d2;
          used_branch = true;
          best_picks = picks;
          if (!real(d)) break;
        }
      }
    }
    // Grid Defense: buildings the engine destroyed that stood in game.
    std::set<int> resist;
    for (const ChanceRecord& c : pr.chances) {
      if (c.kind != ChanceKind::GridDefense) continue;
      for (const Diff& x : d) {
        if ((x.field == "tile.hp" || x.field == "tile.terrain") && x.tile == c.point) resist.insert(c.point.index());
      }
      if (std::any_of(d.begin(), d.end(), [](const Diff& x) { return x.field == "grid_power"; })) {
        resist.insert(c.point.index());
      }
    }
    if (!resist.empty()) {
      PhaseResult p2;
      Board b2 = run(best_picks, resist, p2);
      std::vector<Diff> d2 = diff(b2, p2);
      if (real_count(d2) < real_count(d)) {
        end = b2;
        pr = p2;
        d = d2;
        used_resist = true;
      }
    }
    // Upgrades the bridge did not record: the Storm Generator's +1.
    if (real(d) && t.board.has_passive(kPassiveElectricSmoke) && !t.board.has_passive(kPassiveElectricSmokeA)) {
      PhaseResult p2;
      Board b2 = run(best_picks, resist, p2, kPassiveElectricSmokeA);
      std::vector<Diff> d2 = diff(b2, p2);
      if (!real(d2)) {
        end = b2;
        pr = p2;
        d = d2;
        used_upgrade = true;
      }
    }

    // Multi-tile pawns (trains, dams) occupy only their main tile in the
    // engine: a shot at the other tile misses there.
    bool extra_hit = false;
    for (const Pawn& m : t.board.pawns()) {
      const PawnDef* def = data.pawn(m.type);
      if (!def || def->extra_spaces.empty() || !m.alive()) continue;
      for (Point x : def->extra_spaces) {
        for (const Pawn& q : t.board.pawns()) {
          extra_hit = extra_hit || (q.queued.active() && q.queued.target == m.pos + x);
        }
      }
    }
    if (extra_hit) {
      for (Diff& x : d) {
        if (x.why.empty()) x.why = "a shot at a multi-tile pawn's second tile (engine: main tile only)";
      }
    }
    for (const PhaseEvent& ev : pr.events) {
      ++events[to_string(ev.type)];
      if (ev.type == PhaseEventType::EnvInexact || ev.type == PhaseEventType::EnvUnsupported) {
        ++inexact_why[mission + ": " + ev.detail];
      }
    }
    const int set = t.steps_ok ? 0 : 1;
    for (const Diff& x : d) {
      if (!x.why.empty()) ++why_count[set][x.why];
    }
    for (Tally* tl : {&all[set], &by_mission[(set ? "synced  " : "matched ") + mission]}) {
      ++tl->turns;
      if (d.empty() && !used_upgrade) {
        ++tl->exact;
      } else if (!real(d)) {
        ++tl->explained;
      }
      tl->resist += used_resist && !real(d) ? 1 : 0;
      tl->branch += used_branch && !real(d) ? 1 : 0;
      tl->upgrade += used_upgrade ? 1 : 0;
      tl->inexact += pr.exact ? 0 : 1;
      std::set<std::string> f;
      for (const Diff& x : d) {
        if (x.why.empty()) f.insert(x.field);
      }
      for (const std::string& x : f) ++tl->fields[x];
    }
    const std::string label = key + " " + mission + (next ? "" : " [post_enemy]") + (t.steps_ok ? "" : " [synced]");
    if (jout.is_open()) {
      for (const Diff& x : d) {
        jout << json{{"turn", key}, {"mission", mission}, {"steps_ok", t.steps_ok}, {"field", x.field},
                     {"where", x.where}, {"engine", x.engine}, {"actual", x.actual}, {"why", x.why}}
                    .dump()
             << "\n";
      }
    }
    if (real(d) && static_cast<int>(shown.size()) < opt.show) shown.emplace_back(label, d);
    {
      // Stage 8: score the turn from its start and check the objective
      // counters against the game's records.
      TurnContext sctx;
      sctx.mission = t.rec.mission;
      const ObjectiveReport obj = evaluate_objectives(t.rec.board, end, &sctx, &pr);
      for (const ObjectiveLine& l : obj.lines) {
        auto& c = obj_lines[l.id.substr(0, l.id.find(' '))];
        ++c[0];
        c[1] += l.failed;
        if (l.failed > 0) {
          obj_failures.push_back(label + ": " + l.id + " failed " + std::to_string(l.failed) + " (" + l.detail +
                                 (t.steps_ok ? "" : ", player steps synced") + ")");
        }
        c[2] += l.progress > 0 ? 1 : 0;
        c[3] += l.exact ? 0 : 1;
      }
      const ObjectiveData& o0 = t.rec.mission.objectives;
      if (use_next) {
        const ObjectiveData& o1 = next->mission.objectives;
        // Mission.KilledVek only counts while BONUS_KILL_FIVE or
        // BONUS_PACIFIST is active (Mission:BaseUpdate); AcidKills always.
        const std::vector<BonusId> bonus = active_bonuses(t.rec.board, t.rec.mission);
        const bool counted = mission == "Mission_AcidTank" ||
                             std::find(bonus.begin(), bonus.end(), BonusId::KillFive) != bonus.end() ||
                             std::find(bonus.begin(), bonus.end(), BonusId::Pacifist) != bonus.end();
        if (counted && o0.kills_done >= 0 && o1.kills_done >= 0) {
          const bool acid = mission == "Mission_AcidTank";
          const int engine_kills = o0.kills_done + (acid ? obj.acid_kills : obj.enemy_kills);
          checks[acid ? "acid kills (next mission_kills_done)" : "kills (next mission_kills_done)"].add(
              engine_kills == o1.kills_done, label, engine_kills, o1.kills_done);
        }
        if (o0.repairs_done >= 0 && o1.repairs_done >= 0) {
          checks["repair platforms (next repair_platforms_used)"].add(
              o0.repairs_done + obj.repairs_used == o1.repairs_done, label, o0.repairs_done + obj.repairs_used,
              o1.repairs_done);
        }
        if (o0.mountains_done >= 0 && o1.mountains_done >= 0) {
          checks["mountains (next mission_mountains_destroyed)"].add(
              o0.mountains_done + obj.mountains_destroyed == o1.mountains_done, label,
              o0.mountains_done + obj.mountains_destroyed, o1.mountains_done);
        }
        const ObjectiveTally e = objective_counts(end), g = objective_counts(next->board);
        checks["objective buildings (next board)"].add(e.objective_buildings == g.objective_buildings, label,
                                                         e.objective_buildings, g.objective_buildings);
        checks["pods (next board)"].add(e.pods == g.pods, label, e.pods, g.pods);
        checks["infected mechs (next board)"].add(e.mites == g.mites, label, e.mites, g.mites);
      } else if (post) {
        const ObjectiveTally e = objective_counts(end);
        if (jint(*post, "objective_buildings_alive") >= 0) {
          checks["objective buildings (post_enemy)"].add(e.objective_buildings == jint(*post, "objective_buildings_alive"),
                                                         label, e.objective_buildings,
                                                         jint(*post, "objective_buildings_alive"));
        }
        if (jint(*post, "pods_present") >= 0) {
          checks["pods (post_enemy)"].add(e.pods == jint(*post, "pods_present"), label, e.pods,
                                          jint(*post, "pods_present"));
        }
      }
    }
    if (trace) {
      std::printf("==== %s\n---- enemy phase starts from:\n%s", label.c_str(), render_board(t.board).c_str());
      for (const PhaseEvent& ev : pr.events) {
        std::printf("  %-22s %-4s uid %4d amount %d %s\n", to_string(ev.type), s(ev.point).c_str(), ev.uid, ev.amount,
                    ev.detail.c_str());
      }
      for (const ChanceRecord& c : pr.chances) {
        std::printf("  chance kind %d at %s options %d outcome %d\n", static_cast<int>(c.kind), s(c.point).c_str(),
                    c.options, c.outcome);
      }
      std::printf("---- engine after:\n%s", render_board(end).c_str());
      if (next) std::printf("---- game, next turn start:\n%s", render_board(next->board).c_str());
      for (const Diff& x : d) {
        std::printf("  DIFF %-16s %-22s engine %-8s game %-8s %s\n", x.field.c_str(), x.where.c_str(), x.engine.c_str(),
                    x.actual.c_str(), x.why.c_str());
      }
    }
  }

  std::printf("enemy phase: whole recorded turns replayed (player actions, then Engine::end_turn)\n");
  std::printf("turns whose recorded plan was replayed to its end: %zu\n", turns.size());
  for (const auto& [k, n] : no_truth) std::printf("  no ground truth: %4d  %s\n", n, k.c_str());
  for (const auto& [k, n] : truth_kind) std::printf("  compared with:   %4d  %s\n", n, k.c_str());
  std::printf("  spawn types taken from the next board: %d turns\n", spawn_typed);
  const char* set_names[2] = {"player steps all matched", "player steps synced after a mismatch"};
  for (int i = 0; i < 2; ++i) {
    const Tally& a = all[i];
    std::printf(
        "\n%s: %d turns  exact %d (%s)  +explained %d -> %s  [grid-resist %d, chance branch %d, unrecorded "
        "upgrade %d, inexact env %d]\n",
        set_names[i], a.turns, a.exact, pct(a.exact, a.turns).c_str(), a.explained, pct(a.ok(), a.turns).c_str(),
        a.resist, a.branch, a.upgrade, a.inexact);
    for (const auto& [f, n] : a.fields) std::printf("    %-18s %d turns\n", f.c_str(), n);
    for (const auto& [w, n] : why_count[i]) std::printf("    explained %4d  %s\n", n, w.c_str());
  }
  std::printf("\nper mission (set, mission: turns, exact+explained, mismatching fields):\n");
  for (const auto& [m, a] : by_mission) {
    std::printf("  %-36s %3d  ok %3d (%s)", m.c_str(), a.turns, a.ok(), pct(a.ok(), a.turns).c_str());
    for (const auto& [f, n] : a.fields) std::printf("  %s:%d", f.c_str(), n);
    if (a.inexact) std::printf("  [inexact env %d]", a.inexact);
    std::printf("\n");
  }
  std::printf("\nchance nodes branched (hidden choices):\n");
  for (const auto& [m, c] : chance_use) {
    for (const auto& [k, n] : c) std::printf("  %-28s %-16s %d\n", m.c_str(), k.c_str(), n);
  }
  std::printf("\nevents:\n");
  for (const auto& [k, n] : events) std::printf("  %-24s %d\n", k.c_str(), n);
  for (const auto& [k, n] : inexact_why) std::printf("  inexact/unsupported %4d  %s\n", n, k.c_str());
  std::printf("\nobjectives (stage 8), engine counters vs the game's records:\n");
  for (const auto& [k, c] : checks) {
    std::printf("  %-48s %4d compared, %4d agree (%s)\n", k.c_str(), c.compared, c.agree,
                pct(c.agree, c.compared).c_str());
    for (const std::string& x : c.examples) std::printf("      %s\n", x.c_str());
  }
  std::printf("objective lines scored (id: turns, stars failed, turns with progress, approximate):\n");
  for (const auto& [k, c] : obj_lines) {
    std::printf("  %-32s %4d  failed %3d  progress %3d  approx %3d\n", k.c_str(), c[0], c[1], c[2], c[3]);
  }
  std::printf("objective failures scored:\n");
  for (const std::string& f : obj_failures) std::printf("  %s\n", f.c_str());
  std::printf("\nfirst mismatching turns:\n");
  for (const auto& [label, d] : shown) {
    std::printf("  %s\n", label.c_str());
    for (const Diff& x : d) {
      std::printf("      %-16s %-22s engine %-8s game %-8s %s\n", x.field.c_str(), x.where.c_str(), x.engine.c_str(),
                  x.actual.c_str(), x.why.empty() ? "" : ("(" + x.why + ")").c_str());
    }
  }
  return 0;
}

}  // namespace itb::tools
