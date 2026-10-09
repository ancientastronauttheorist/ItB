// itb_inspect --replay: the engine against what the game really did.
//
// The old bot recorded, per turn, the board it solved
// (m<NN>_turn_<NN>_solve_input.json), the plan it executed and its own
// simulator's prediction after each move and each attack (..._solve.json:
// data.actions, data.predicted_states[i].{post_move, post_attack}). After each
// sub-action it read the live board through the bridge and compared it with
// that prediction on a fixed set of fields; only differences were written
// (failure_db.jsonl and ..._action_<i>_<phase>_verify.json). Nothing is
// written when they agree.
//
// Ground truth after a sub-action is therefore the old prediction with the
// recorded differences applied, on exactly the fields the old verifier
// compared:
//   units  alive, hp, pos, active (mechs), status fire/acid/frozen/shield/web
//          (and boosted when the snapshot has it);
//   tiles  terrain, building_hp, fire, acid, smoke, has_pod (and shield when
//          present), only on the tiles the snapshot lists;
//   grid   grid_power.
// After a desync the bot re-solved, and the re-solved plans were not kept, so
// a turn is replayed up to and including its first desynced action.
//
// How each action reached the game matters. Weapons went through the native
// Pawn:FireWeapon, except a few the bridge emulated (repairs from 2026-05-16,
// Aerial Bombs / Bombing Run transit damage, Quick-Fire, Ricochet, Seismic
// flip); moves were native Pawn:Move until 2026-05-29 and Pawn:SetSpace
// teleports afterwards. Results are split by that path.

#include "replay.hpp"

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <regex>
#include <set>
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

// ---- Snapshots -------------------------------------------------------------------

struct UnitState {
  int32_t uid = -1;
  std::string type;
  bool alive = true;
  bool known = true;  // false: only existence is known (the rest wasn't recorded)
  int hp = 0;
  Point pos;
  bool active = false;
  bool mech = false;
  std::map<std::string, bool> status;
};

struct TileState {
  Point p;
  std::string terrain;
  int building_hp = 0;
  bool fire = false, acid = false, smoke = false, pod = false;
  std::optional<bool> shield;
};

struct State {
  std::vector<UnitState> units;
  std::map<int, TileState> tiles;  // by Point::index
  std::optional<int> grid;

  UnitState* unit(int32_t uid) {
    for (UnitState& u : units) {
      if (u.uid == uid) return &u;
    }
    return nullptr;
  }
  const UnitState* unit(int32_t uid) const { return const_cast<State*>(this)->unit(uid); }
};

Point json_point(const json& j) {
  if (!j.is_array() || j.size() < 2 || !j[0].is_number() || !j[1].is_number()) return kInvalidPoint;
  return {j[0].get<int>(), j[1].get<int>()};
}

bool jbool(const json& j, const char* k) {
  auto it = j.find(k);
  return it != j.end() && it->is_boolean() && it->get<bool>();
}

int jint(const json& j, const char* k, int fallback = 0) {
  auto it = j.find(k);
  return it != j.end() && it->is_number() ? it->get<int>() : fallback;
}

// `lava_is_ice`: the board came from a bridge whose name table called ice
// "lava" (before 2026-05-04); its snapshots inherit the name.
State parse_snapshot(const json& s, bool lava_is_ice) {
  State st;
  for (const json& u : s.value("units", json::array())) {
    UnitState us;
    us.uid = jint(u, "uid", -1);
    us.type = u.value("type", "");
    us.alive = jbool(u, "alive") && jint(u, "hp") > 0;
    us.hp = jint(u, "hp");
    us.pos = json_point(u.value("pos", json()));
    us.active = jbool(u, "active");
    us.mech = jbool(u, "is_mech");
    if (auto it = u.find("status"); it != u.end() && it->is_object()) {
      for (auto& [k, v] : it->items()) {
        if (v.is_boolean() && k != "infected") us.status[k] = v.get<bool>();
      }
    }
    st.units.push_back(std::move(us));
  }
  for (const json& t : s.value("tiles_changed", json::array())) {
    TileState ts;
    ts.p = {jint(t, "x", -1), jint(t, "y", -1)};
    if (!ts.p.valid()) continue;
    ts.terrain = t.value("terrain", "");
    if (lava_is_ice && ts.terrain == "lava") ts.terrain = "ice";
    ts.building_hp = jint(t, "building_hp");
    ts.fire = jbool(t, "fire");
    ts.acid = jbool(t, "acid");
    ts.smoke = jbool(t, "smoke");
    ts.pod = jbool(t, "has_pod");
    if (auto it = t.find("shield"); it != t.end() && it->is_boolean()) ts.shield = it->get<bool>();
    st.tiles[ts.p.index()] = ts;
  }
  if (auto it = s.find("grid_power"); it != s.end() && it->is_number()) st.grid = it->get<int>();
  return st;
}

// The old verifier's differences, applied to its prediction.
void apply_diff(State& st, const json& diff, bool lava_is_ice) {
  for (const json& d : diff.value("unit_diffs", json::array())) {
    const int32_t uid = jint(d, "uid", -1);
    const std::string field = d.value("field", "");
    const json& actual = d.contains("actual") ? d["actual"] : json();
    UnitState* u = st.unit(uid);
    if (field == "missing_in_predicted") {
      if (!u) {
        UnitState n;
        n.uid = uid;
        n.type = d.value("type", "");
        n.known = false;
        st.units.push_back(n);
      }
      continue;
    }
    if (!u) continue;
    if (field == "missing_in_actual") {
      u->alive = false;
    } else if (field == "alive") {
      u->alive = actual.is_boolean() && actual.get<bool>();
      if (u->alive) u->known = false;  // predicted dead: its fields were not compared
    } else if (field == "hp" && actual.is_number()) {
      u->hp = actual.get<int>();
    } else if (field == "pos") {
      u->pos = json_point(actual);
    } else if (field == "active" && actual.is_boolean()) {
      u->active = actual.get<bool>();
    } else if (field.starts_with("status.") && actual.is_boolean()) {
      u->status[field.substr(7)] = actual.get<bool>();
    }
  }
  for (const json& d : diff.value("tile_diffs", json::array())) {
    const Point p{jint(d, "x", -1), jint(d, "y", -1)};
    if (!p.valid()) continue;
    auto it = st.tiles.find(p.index());
    if (it == st.tiles.end()) continue;
    TileState& t = it->second;
    const std::string field = d.value("field", "");
    const json& actual = d.contains("actual") ? d["actual"] : json();
    if (field == "terrain" && actual.is_string()) {
      t.terrain = actual.get<std::string>();
      if (lava_is_ice && t.terrain == "lava") t.terrain = "ice";
    } else if (field == "building_hp" && actual.is_number()) {
      t.building_hp = actual.get<int>();
      if (d.contains("actual_terrain") && d["actual_terrain"].is_string()) {
        t.terrain = d["actual_terrain"].get<std::string>();
        if (lava_is_ice && t.terrain == "lava") t.terrain = "ice";
      }
    } else if (actual.is_boolean()) {
      const bool v = actual.get<bool>();
      if (field == "fire") t.fire = v;
      else if (field == "acid") t.acid = v;
      else if (field == "smoke") t.smoke = v;
      else if (field == "has_pod") t.pod = v;
      else if (field == "shield") t.shield = v;
    }
  }
  for (const json& d : diff.value("scalar_diffs", json::array())) {
    if (d.value("field", "") == "grid_power" && d["actual"].is_number()) st.grid = d["actual"].get<int>();
  }
}

// ---- The engine's side ------------------------------------------------------------

std::string terrain_name(const Tile& t) {
  switch (t.terrain) {
    case Terrain::Road: return "ground";
    case Terrain::Building: return "building";
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

bool engine_alive(const Pawn& p) { return p.hp > 0 && !p.fallen && p.pos.valid(); }

bool pawn_status(const Board& b, const Pawn& p, const std::string& k) {
  if (k == "fire") return p.fire;
  if (k == "acid") return p.acid;
  if (k == "frozen") return p.frozen;
  if (k == "shield") return p.shield;
  if (k == "web") return p.webbed;
  // The bridge reads Pawn:IsBoosted(): the status, the Boost psion or an
  // Arrogant pilot at full health.
  if (k == "boosted") return is_boosted(b, p);
  return false;
}

std::string str(bool b) { return b ? "true" : "false"; }
std::string str(int v) { return std::to_string(v); }
std::string str(Point p) { return p.valid() ? to_visual(p) : "-"; }

struct Mismatch {
  std::string field;  // unit.hp, tile.smoke, grid_power, ...
  std::string where;  // unit uid/type or tile
  std::string engine, actual, predicted;
  Point tile = kInvalidPoint;
  bool mech = false;
  std::string artefact;  // known verifier tolerance that makes the truth unreliable
};

// Pairs ground-truth units with engine pawns: by uid, then (type, tile) for
// spawns whose uid the game picks.
std::map<int32_t, int32_t> match_units(const Board& b, const State& gt) {
  std::map<int32_t, int32_t> m;  // gt uid -> engine uid
  std::set<int32_t> used;
  // Same uid and type. (Spawns can get another uid in the engine: the game
  // hands uids to emerging Vek before they surface.)
  for (const UnitState& u : gt.units) {
    const Pawn* p = b.find_pawn(u.uid);
    if (p && (u.type.empty() || symbol_name(p->type) == u.type)) {
      m[u.uid] = u.uid;
      used.insert(u.uid);
    }
  }
  for (const UnitState& u : gt.units) {
    if (m.count(u.uid) || !u.alive || !u.known) continue;
    for (const Pawn& p : b.pawns()) {
      if (used.count(p.uid) || !engine_alive(p)) continue;
      if (symbol_name(p.type) == u.type && p.pos == u.pos) {
        m[u.uid] = p.uid;
        used.insert(p.uid);
        break;
      }
    }
  }
  // Unknown-detail units (present in game, not predicted): any unmatched
  // living pawn of that type.
  for (const UnitState& u : gt.units) {
    if (m.count(u.uid) || u.known) continue;
    for (const Pawn& p : b.pawns()) {
      if (used.count(p.uid) || !engine_alive(p)) continue;
      if (symbol_name(p.type) == u.type) {
        m[u.uid] = p.uid;
        used.insert(p.uid);
        break;
      }
    }
  }
  return m;
}

// A multi-tile pawn (trains, dams) is listed once per tile by the bridge,
// all with the same uid; the old verifier kept whichever came last, so its
// position may be any of the pawn's tiles.
bool on_extra_tile(const GameData& data, const Pawn& p, Point reported) {
  const PawnDef* def = data.pawn(p.type);
  if (!def) return false;
  for (Point e : def->extra_spaces) {
    if (p.pos + e == reported || reported + e == p.pos) return true;
  }
  return false;
}

std::vector<Mismatch> compare(const Board& b, const State& gt, const State& pred, const GameData& data) {
  std::vector<Mismatch> out;
  const auto match = match_units(b, gt);
  std::set<int32_t> matched;
  for (const auto& [g, e] : match) matched.insert(e);
  auto add = [&](std::string field, std::string where, std::string engine, std::string actual,
                 std::string predicted, bool mech = false, Point tile = kInvalidPoint) {
    out.push_back(Mismatch{std::move(field), std::move(where), std::move(engine), std::move(actual),
                           std::move(predicted), tile, mech, ""});
  };
  for (const UnitState& u : gt.units) {
    const std::string where = u.type + "#" + std::to_string(u.uid);
    const UnitState* pu = pred.unit(u.uid);
    auto it = match.find(u.uid);
    const Pawn* p = it == match.end() ? nullptr : b.find_pawn(it->second);
    const bool e_alive = p && engine_alive(*p);
    if (!u.alive) {
      if (e_alive) add("unit.alive", where, "true", "false", pu ? str(pu->alive) : "-", u.mech);
      continue;
    }
    if (!e_alive) {
      add("unit.alive", where, p ? "false" : "absent", "true", pu ? str(pu->alive) : "absent", u.mech);
      continue;
    }
    if (!u.known) continue;
    if (p->hp != u.hp) add("unit.hp", where, str(p->hp), str(u.hp), pu ? str(pu->hp) : "-", u.mech);
    if (p->pos != u.pos) {
      add("unit.pos", where, str(p->pos), str(u.pos), pu ? str(pu->pos) : "-", u.mech);
      if (on_extra_tile(data, *p, u.pos)) out.back().artefact = "bridge: multi-tile pawn reported by another tile";
    }
    if (u.mech && p->active != u.active) {
      add("unit.active", where, str(p->active), str(u.active), pu ? str(pu->active) : "-", u.mech);
    }
    for (const auto& [k, v] : u.status) {
      const bool e = pawn_status(b, *p, k);
      if (e != v) {
        std::string pv = "-";
        if (pu) {
          auto s = pu->status.find(k);
          if (s != pu->status.end()) pv = str(s->second);
        }
        add("unit.status." + k, where, str(e), str(v), pv, u.mech);
      }
    }
  }
  // Living pawns the game did not have. Burrowed units are never captured.
  for (const Pawn& p : b.pawns()) {
    if (!engine_alive(p) || matched.count(p.uid) || p.burrows) continue;
    if (const UnitState* g = gt.unit(p.uid); g && symbol_name(p.type) == g->type) continue;
    add("unit.extra", std::string(symbol_name(p.type)) + "#" + std::to_string(p.uid), "alive at " + str(p.pos),
        "absent", "-", p.mech);
  }
  for (const auto& [idx, t] : gt.tiles) {
    const Tile& et = b.tile(t.p);
    const std::string where = to_visual(t.p);
    auto pt = pred.tiles.find(idx);
    const TileState* pr = pt == pred.tiles.end() ? nullptr : &pt->second;
    const std::string terr = terrain_name(et);
    if (terr != t.terrain) add("tile.terrain", where, terr, t.terrain, pr ? pr->terrain : "-", false, t.p);
    const int bhp = et.is_building() || et.is_mountain() ? et.hp : 0;
    if (bhp != t.building_hp) {
      add("tile.building_hp", where, str(bhp), str(t.building_hp), pr ? str(pr->building_hp) : "-", false, t.p);
    }
    if (et.on_fire() != t.fire) add("tile.fire", where, str(et.on_fire()), str(t.fire), pr ? str(pr->fire) : "-", false, t.p);
    if (et.acid != t.acid) add("tile.acid", where, str(et.acid), str(t.acid), pr ? str(pr->acid) : "-", false, t.p);
    if (et.smoke != t.smoke) add("tile.smoke", where, str(et.smoke), str(t.smoke), pr ? str(pr->smoke) : "-", false, t.p);
    const bool pod = et.pod == PodState::Present;
    if (pod != t.pod) add("tile.has_pod", where, str(pod), str(t.pod), pr ? str(pr->pod) : "-", false, t.p);
    if (t.shield && et.shield != *t.shield) {
      add("tile.shield", where, str(et.shield), str(*t.shield), pr && pr->shield ? str(*pr->shield) : "-", false, t.p);
    }
  }
  if (gt.grid && b.grid_power != *gt.grid) {
    add("grid_power", "grid", str(b.grid_power), str(*gt.grid), pred.grid ? str(*pred.grid) : "-");
  }
  return out;
}

// Resets the compared fields to the ground truth, so the next step starts
// from the game's board as far as it is known.
void sync(Board& b, const State& gt, const GameData& data) {
  const auto match = match_units(b, gt);
  std::set<int32_t> matched;
  for (const auto& [g, e] : match) matched.insert(e);
  for (const UnitState& u : gt.units) {
    auto it = match.find(u.uid);
    Pawn* p = it == match.end() ? nullptr : b.find_pawn(it->second);
    if (!u.alive) {
      if (p && engine_alive(*p)) {
        if (p->mech) {
          p->hp = 0;
        } else {
          b.remove_pawn(p->uid);
        }
      }
      continue;
    }
    if (!p) {
      if (!u.known) continue;
      const PawnDef* def = data.pawn(u.type);
      if (!def || !u.pos.valid()) continue;
      Pawn n = data.make_pawn(*def, u.uid, u.pos);
      n.team = u.mech ? Team::Player : n.team;
      n.mech = u.mech;
      p = &b.add_pawn(n);
    }
    if (!u.known) continue;
    if (p->uid != u.uid && !b.find_pawn(u.uid)) p->uid = u.uid;
    p->hp = static_cast<int8_t>(u.hp);
    p->max_hp = std::max(p->max_hp, p->hp);
    p->fallen = false;
    p->dying = false;
    if (!on_extra_tile(data, *p, u.pos)) p->pos = u.pos;
    // `active` stays the engine's own bookkeeping: the old prediction never
    // cleared it, so it is only trustworthy where a desync record set it.
    if (u.mech && !u.active) p->active = false;
    for (const auto& [k, v] : u.status) {
      if (k == "fire") p->fire = v;
      else if (k == "acid") p->acid = v;
      else if (k == "frozen") p->frozen = v;
      else if (k == "shield") p->shield = v;
      else if (k == "web") p->webbed = v;
      else if (k == "boosted") p->boosted = v;
    }
  }
  std::vector<int32_t> extra;
  for (const Pawn& p : b.pawns()) {
    const UnitState* g = gt.unit(p.uid);
    if (engine_alive(p) && !matched.count(p.uid) && !(g && symbol_name(p.type) == g->type) && !p.burrows) {
      extra.push_back(p.uid);
    }
  }
  for (int32_t uid : extra) b.remove_pawn(uid);
  // Dead non-mech bodies the engine still carries are gone in game.
  std::vector<int32_t> bodies;
  for (const Pawn& p : b.pawns()) {
    if (!engine_alive(p) && !p.mech) bodies.push_back(p.uid);
  }
  for (int32_t uid : bodies) b.remove_pawn(uid);

  for (const auto& [idx, t] : gt.tiles) {
    Tile& et = b.tile(t.p);
    static const std::map<std::string, Terrain> kTerrain = {
        {"ground", Terrain::Road},   {"building", Terrain::Building}, {"rubble", Terrain::Rubble},
        {"water", Terrain::Water},   {"lava", Terrain::Water},        {"mountain", Terrain::Mountain},
        {"ice", Terrain::Ice},       {"forest", Terrain::Forest},     {"sand", Terrain::Sand},
        {"chasm", Terrain::Hole}};
    if (auto it = kTerrain.find(t.terrain); it != kTerrain.end() && terrain_name(et) != t.terrain) {
      et.terrain = it->second;
      et.lava = t.terrain == "lava";
      et.pending_hole = false;
      if (et.terrain == Terrain::Ice) et.hp = et.max_hp = 2;
    }
    if (et.is_building() || et.is_mountain()) et.hp = static_cast<int8_t>(t.building_hp);
    if (et.on_fire() != t.fire) et.fire = t.fire ? FireState::Burning : FireState::None;
    et.acid = t.acid;
    et.smoke = t.smoke;
    if ((et.pod == PodState::Present) != t.pod) et.pod = t.pod ? PodState::Present : PodState::None;
    if (t.shield) et.shield = *t.shield;
  }
  if (gt.grid) b.grid_power = *gt.grid;
}

// ---- Recorded desyncs -----------------------------------------------------------

struct Desync {
  int action = -1;
  std::string phase;  // move / attack / repair / skip
  int32_t mech = -1;
  std::string timestamp;
  json diff;
  std::optional<json> predicted;  // from the verify file
};

std::string phase_slot(const std::string& phase) { return phase == "move" ? "post_move" : "post_attack"; }

json load_json(const fs::path& p) {
  std::ifstream in(p);
  json j;
  in >> j;
  return j;
}

// ---- Execution paths -----------------------------------------------------------------

enum class Path { Native, AddEffect, Augmented, Synthetic };

const char* path_name(Path p) {
  switch (p) {
    case Path::Native: return "native";
    case Path::AddEffect: return "AddEffect";
    case Path::Augmented: return "native+synthetic";
    case Path::Synthetic: return "synthetic";
  }
  return "?";
}

// How the bridge applied an attack (src/bridge/modloader.lua history).
Path attack_path(const std::string& weapon, const std::string& date) {
  auto starts = [&](const char* s) { return weapon.rfind(s, 0) == 0; };
  if (weapon == "_REPAIR") return date >= "2026-05-16" ? Path::Synthetic : Path::AddEffect;
  if (starts("Brute_Jetmech") || starts("Brute_Bombrun")) {
    return date >= "2026-04-24" ? Path::Augmented : Path::Native;
  }
  if (starts("Science_KO_Crack") && date >= "2026-07-09") return Path::Augmented;
  if (starts("Brute_TC_DoubleShot") || starts("Brute_TC_Ricochet")) return Path::Synthetic;
  if (starts("Prime_TC_Punt") && date >= "2026-05-21") return Path::AddEffect;
  if (date < "2026-04-11") return Path::AddEffect;
  return Path::Native;
}

Path move_path(const std::string& date) { return date >= "2026-05-29" ? Path::Synthetic : Path::Native; }

// ---- Statistics ----------------------------------------------------------------------

struct Tally {
  int steps = 0;
  int exact = 0;      // no mismatch at all
  int tolerated = 0;  // only mismatches the old verifier would not have logged
  int resist = 0;     // matched once a Grid Defense resist was taken
  std::map<std::string, int> fields;  // steps with a mismatch of this field (non-artefact)

  void add(const std::vector<Mismatch>& mm, bool resisted) {
    ++steps;
    bool real = false;
    std::set<std::string> seen;
    for (const Mismatch& m : mm) {
      if (!m.artefact.empty()) continue;
      real = true;
      seen.insert(m.field);
    }
    for (const std::string& f : seen) ++fields[f];
    if (mm.empty()) {
      ++exact;
      if (resisted) ++resist;
    } else if (!real) {
      ++tolerated;
    }
  }
  int ok() const { return exact + tolerated; }
};

std::string pct(int a, int b) {
  char buf[32];
  std::snprintf(buf, sizeof buf, "%5.1f%%", b ? 100.0 * a / b : 0.0);
  return buf;
}

void print_tally(const char* label, const Tally& t) {
  std::printf("  %-34s %5d steps  exact %5d (%s)  +tolerated %4d -> %s  [resist-explained %d]\n", label, t.steps,
              t.exact, pct(t.exact, t.steps).c_str(), t.tolerated, pct(t.ok(), t.steps).c_str(), t.resist);
}

struct Shown {
  std::string head;
  std::vector<Mismatch> mm;
};

}  // namespace

int run_replay(const ReplayOptions& opt) {
  std::unique_ptr<Engine> engine;
  try {
    engine = Engine::create(opt.game);
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << "\n";
    return 1;
  }
  const GameData& data = engine->data();

  // failure_db rows by (run, mission, turn).
  std::map<std::string, std::vector<Desync>> fdb;
  {
    const fs::path path = opt.failure_db.empty() ? opt.recordings / "failure_db.jsonl" : opt.failure_db;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
      json r;
      try {
        r = json::parse(line);
      } catch (const std::exception&) {
        continue;
      }
      const std::string trig = r.value("trigger", "");
      static const std::string kPrefix = "per_sub_action_desync_";
      if (trig.rfind(kPrefix, 0) != 0 || !r.contains("diff") || !r["action_index"].is_number()) continue;
      Desync d;
      d.action = r["action_index"].get<int>();
      d.phase = trig.substr(kPrefix.size());
      d.mech = jint(r, "mech_uid", -1);
      d.timestamp = r.value("timestamp", "");
      d.diff = r["diff"];
      const std::string key = r.value("run_id", "") + "/" + std::to_string(jint(r, "mission", -1)) + "/" +
                              std::to_string(jint(r, "turn", -1));
      fdb[key].push_back(std::move(d));
    }
  }

  std::vector<fs::path> inputs;
  for (const auto& e : fs::recursive_directory_iterator(opt.recordings)) {
    const std::string name = e.path().filename().string();
    if (e.is_regular_file() && name.ends_with("_solve_input.json")) inputs.push_back(e.path());
  }
  std::sort(inputs.begin(), inputs.end());

  std::ofstream jout;
  if (!opt.json_out.empty()) jout.open(opt.json_out);

  std::map<std::string, int> skips;  // reason -> actions (or turns) skipped
  std::map<std::string, int> refusals;
  int turns = 0, turns_used = 0;
  // Attack steps: [bucket][path]; bucket 0 = old sim right, 1 = old sim desync.
  std::map<std::string, Tally> attack, moves;
  std::map<std::string, Tally> per_weapon;  // native attacks only
  std::map<std::string, std::map<std::string, int>> weapon_fields;
  std::vector<Shown> shown[2];
  std::map<std::string, int> lua_errors;
  std::map<std::string, int> unapplied;
  std::map<std::string, int> upgrade_explained;
  std::vector<std::string> refusal_examples;
  int timing_sensitive = 0, chance_lua = 0;

  const std::regex verify_re(R"(_action_(\d+)_(move|attack|repair|skip)_verify\.json$)");

  for (const fs::path& input : inputs) {
    const std::string name = input.filename().string();
    const fs::path solve_path =
        input.parent_path() / (name.substr(0, name.size() - std::string("_input.json").size()) + ".json");
    if (!fs::exists(solve_path)) continue;
    ++turns;
    json solve;
    try {
      solve = load_json(solve_path);
    } catch (const std::exception&) {
      ++skips["turn: unreadable solve.json"];
      continue;
    }
    const json& sd = solve["data"];
    const json& actions = sd["actions"];
    const json& states = sd["predicted_states"];
    if (!actions.is_array() || actions.empty()) {
      ++skips["turn: no actions"];
      continue;
    }
    if (sd.contains("partial_re_solve")) {
      ++skips["turn: partial re-solve plan"];
      continue;
    }
    if (!states.is_array() || states.size() != actions.size() || !states[0].contains("post_attack")) {
      ++skips["turn: no per-sub-action predictions"];
      continue;
    }
    std::string error;
    auto rec = load_recording(input, &data, &error);
    if (!rec) {
      ++skips["turn: board did not load"];
      continue;
    }
    const std::string date = solve.value("timestamp", "");
    const bool lava_is_ice =
        std::find(rec->warnings.begin(), rec->warnings.end(), kIceNamedLava) != rec->warnings.end();
    const std::string run = input.parent_path().filename().string();

    // This turn's recorded desyncs: verify files first, failure_db rows for
    // the rest (same action and phase are the same desync).
    std::vector<Desync> desyncs;
    const std::string prefix = name.substr(0, name.size() - std::string("_solve_input.json").size());
    for (const auto& e : fs::directory_iterator(input.parent_path())) {
      const std::string vn = e.path().filename().string();
      std::smatch m;
      if (vn.rfind(prefix + "_action_", 0) != 0 || !std::regex_search(vn, m, verify_re)) continue;
      json v;
      try {
        v = load_json(e.path());
      } catch (const std::exception&) {
        continue;
      }
      const json& vd = v.contains("data") ? v["data"] : v;
      Desync d;
      d.action = std::stoi(m[1].str());
      d.phase = m[2].str();
      d.mech = jint(vd, "mech_uid", -1);
      d.timestamp = v.value("timestamp", "");
      d.diff = vd.value("diff", json::object());
      if (vd.contains("predicted")) d.predicted = vd["predicted"];
      desyncs.push_back(std::move(d));
    }
    const std::string key = run + "/" + std::to_string(rec->mission_index) + "/" + std::to_string(rec->turn);
    const bool trace = key == opt.trace;
    if (auto it = fdb.find(key); it != fdb.end()) {
      for (const Desync& d : it->second) {
        const bool have = std::any_of(desyncs.begin(), desyncs.end(), [&](const Desync& x) {
          return x.action == d.action && x.phase == d.phase;
        });
        if (!have) desyncs.push_back(d);
      }
    }
    // The first desync (moves before attacks), checked against this plan.
    std::sort(desyncs.begin(), desyncs.end(), [](const Desync& a, const Desync& b) {
      if (a.action != b.action) return a.action < b.action;
      return (a.phase == "move") > (b.phase == "move");
    });
    const Desync* first = desyncs.empty() ? nullptr : &desyncs.front();
    if (first) {
      const bool in_plan = first->action >= 0 && first->action < static_cast<int>(actions.size());
      bool consistent = in_plan && first->mech == actions[static_cast<size_t>(first->action)].value("mech_uid", -2) &&
                        first->timestamp >= date;
      if (consistent && first->predicted) {
        consistent = *first->predicted == states[static_cast<size_t>(first->action)][phase_slot(first->phase)];
      }
      if (!consistent) {
        ++skips["turn: desync record from another plan or attempt"];
        continue;
      }
    }
    ++turns_used;

    Board board = rec->board;
    for (const auto& [uid, pilot] : rec->pilots) {
      if (Pawn* p = board.find_pawn(uid)) p->pilot_abilities |= engine->pilot_ability(pilot);
    }
    const int last = first ? first->action : static_cast<int>(actions.size()) - 1;
    std::set<std::string> skipped;  // "#uid" of mechs whose step was move-only
    if (last + 1 < static_cast<int>(actions.size())) {
      skips["action: after the turn's first desync (re-solved plan not recorded)"] +=
          static_cast<int>(actions.size()) - last - 1;
    }

    for (int i = 0; i <= last; ++i) {
      const json& a = actions[static_cast<size_t>(i)];
      const int32_t uid = a.value("mech_uid", -1);
      const std::string weapon = a.value("weapon_id", "");
      const Point move_to = json_point(a.value("move_to", json()));
      const Point target = json_point(a.value("target", json()));
      const bool desync_here = first && first->action == i;
      const int bucket = desync_here ? 1 : 0;
      const char* bucket_name = bucket ? "old-sim desync" : "old-sim right";
      if (!opt.only_weapon.empty() && weapon != opt.only_weapon) {
        ++skips["action: filtered by --weapon"];
        break;
      }
      Pawn* mech = board.find_pawn(uid);
      if (!mech) {
        ++skips["action: mech not on the board"];
        break;
      }
      std::string head = run + " m" + std::to_string(rec->mission_index) + " t" + std::to_string(rec->turn) +
                         " a" + std::to_string(i) + " " + symbol_name(mech->type).data() + "#" + std::to_string(uid);

      auto note = [&](const ActionResult& r) {
        for (const std::string& e : r.lua_errors) ++lua_errors[weapon + ": " + e.substr(0, 120)];
        for (const LuaWrite& w : r.unapplied) ++unapplied[w.object + ":" + w.method];
        if (r.resolve.timing_sensitive()) ++timing_sensitive;
        for (const ChanceRecord& c : r.resolve.chances) {
          if (c.kind == ChanceKind::LuaRandom) ++chance_lua;
        }
      };
      auto record = [&](const std::string& label, int b, std::vector<Mismatch>& mm) {
        for (Mismatch& m : mm) {
          if (jout.is_open()) {
            jout << json{{"step", label}, {"bucket", b}, {"field", m.field}, {"where", m.where},
                         {"engine", m.engine}, {"actual", m.actual}, {"predicted", m.predicted},
                         {"artefact", m.artefact}}
                        .dump()
                 << "\n";
          }
        }
        bool real = std::any_of(mm.begin(), mm.end(), [](const Mismatch& m) { return m.artefact.empty(); });
        if (real && static_cast<int>(shown[b].size()) < opt.show) shown[b].push_back(Shown{label, mm});
      };
      // Mismatches the old verifier tolerated without logging, when this
      // step has no desync record: the ground truth itself is unsure there.
      auto tag_tolerances = [&](std::vector<Mismatch>& mm, bool has_record) {
        for (Mismatch& m : mm) {
          const size_t hash = m.where.rfind('#');
          if (m.field == "unit.active" && hash != std::string::npos && skipped.count(m.where.substr(hash))) {
            m.artefact = "bridge: SKIP deactivation varies by version";
          }
        }
        if (has_record) return;
        const bool only_active = std::all_of(mm.begin(), mm.end(), [](const Mismatch& m) {
          return m.field == "unit.active";
        });
        const bool only_mech_hp = std::all_of(mm.begin(), mm.end(), [](const Mismatch& m) {
          return m.field == "unit.hp" && m.mech && std::stoi(m.engine) > std::stoi(m.actual);
        });
        const bool only_grid_up = std::all_of(mm.begin(), mm.end(), [](const Mismatch& m) {
          return m.field == "grid_power" && std::stoi(m.engine) > std::stoi(m.actual);
        });
        for (Mismatch& m : mm) {
          // The old simulator never cleared `active` and the verifier
          // forgave predicted-active / actually-inactive: without a desync
          // record, a predicted `active = true` says nothing.
          if (m.field == "unit.active" && m.engine == "false") {
            m.artefact = "verifier: active not tracked by the old simulator";
          }
          if (only_active && m.engine == "false") m.artefact = "verifier: active-only diff on a finished mech";
          if (only_mech_hp) m.artefact = "verifier: mech hp above prediction";
          if (only_grid_up) m.artefact = "verifier: grid settlement";
        }
      };
      auto phase_state = [&](const std::string& slot, const std::string& phase_a, const std::string& phase_b,
                             bool& has_record) {
        const json& snap = states[static_cast<size_t>(i)][slot];
        State pred = parse_snapshot(snap, lava_is_ice);
        State gt = pred;
        has_record = false;
        for (const Desync& d : desyncs) {
          if (d.action == i && (d.phase == phase_a || d.phase == phase_b)) {
            apply_diff(gt, d.diff, lava_is_ice);
            has_record = true;
            break;
          }
        }
        return std::make_pair(pred, gt);
      };
      // Runs `act` on a copy; if a building the engine damaged was intact in
      // game and rolled Grid Defense, runs it again with those rolls resisted.
      auto run_step = [&](auto act, const State& gt, const State& pred, bool& resisted) {
        resisted = false;
        if (trace) std::printf("==== %s\n---- before:\n%s", head.c_str(), render_board(board).c_str());
        Board trial = board;
        ActionResult r = act(trial, ActionOptions{});
        std::vector<Mismatch> mm = compare(trial, gt, pred, data);
        std::set<int> resist;
        for (const ChanceRecord& c : r.resolve.chances) {
          if (c.kind != ChanceKind::GridDefense) continue;
          for (const Mismatch& m : mm) {
            if (m.field == "tile.building_hp" && m.tile == c.point && std::stoi(m.engine) < std::stoi(m.actual)) {
              resist.insert(c.point.index());
            }
          }
        }
        if (!resist.empty()) {
          Board again = board;
          ActionOptions o;
          o.grid_resist = [&](Point p, int) { return resist.count(p.index()) > 0; };
          ActionResult r2 = act(again, o);
          std::vector<Mismatch> mm2 = compare(again, gt, pred, data);
          if (mm2.size() < mm.size()) {
            trial = std::move(again);
            r = std::move(r2);
            mm = std::move(mm2);
            resisted = true;
          }
        }
        if (trace) {
          std::printf("---- effect (%s, %s):\n", r.weapon.c_str(), to_string(r.status));
          for (const SpaceDamage& e : r.effect.effect) {
            std::printf("  %s dmg %d push %d proj %d delay %.2f%s%s%s\n", str(e.loc).c_str(), e.damage,
                        static_cast<int>(e.push), static_cast<int>(e.projectile), static_cast<double>(e.delay),
                        e.spawn_pawn != kNoSymbol ? (" spawn " + std::string(symbol_name(e.spawn_pawn))).c_str() : "",
                        e.path.empty() ? "" : " path", e.script.empty() ? "" : " script");
          }
          std::printf("---- after:\n%s", render_board(trial).c_str());
          for (const Mismatch& m : mm) {
            std::printf("  MISMATCH %s %s engine %s actual %s old %s %s\n", m.field.c_str(), m.where.c_str(),
                        m.engine.c_str(), m.actual.c_str(), m.predicted.c_str(), m.artefact.c_str());
          }
        }
        board = std::move(trial);
        note(r);
        return std::make_pair(r, mm);
      };

      // ---- the move
      bool move_record = false;
      if (move_to.valid() && move_to != mech->pos) {
        auto [pred, gt] = phase_state("post_move", "move", "move", move_record);
        bool resisted = false;
        auto [r, mm] = run_step(
            [&](Board& b, ActionOptions o) {
              ActionResult res = engine->move(b, uid, move_to, o);
              if (!res.ok() && res.status != ActionStatus::NoEffect) {
                ++refusals[std::string("move: ") + to_string(res.status)];
                if (refusal_examples.size() < 12) refusal_examples.push_back(head + " move " + str(move_to));
                o.check_legal = false;
                res = engine->move(b, uid, move_to, o);
              }
              return res;
            },
            gt, pred, resisted);
        tag_tolerances(mm, move_record);
        const std::string label = head + " move " + str(move_to) + " [" + path_name(move_path(date)) + "]";
        const int mb = move_record ? 1 : 0;
        moves[std::string(mb ? "old-sim desync" : "old-sim right") + " / " + path_name(move_path(date))].add(mm,
                                                                                                    resisted);
        record(label, mb, mm);
        if (opt.sync) sync(board, gt, data);
        if (move_record) {
          ++skips["action: attack after a move desync (re-solved mid-action)"];
          break;
        }
      }

      // ---- the attack (or repair / skip)
      bool attack_record = false;
      auto [pred, gt] = phase_state("post_attack", "attack", weapon == "_REPAIR" ? "repair" : "skip", attack_record);
      // Any phase of the final sub-action counts (repair / skip records).
      for (const Desync& d : desyncs) {
        if (d.action == i && d.phase != "move" && !attack_record) {
          apply_diff(gt, d.diff, lava_is_ice);
          attack_record = true;
        }
      }
      const bool skip = weapon.empty() || weapon == "Unknown" || !target.valid();
      if (!skip && weapon != "_REPAIR" && !engine->lua().lua_string(weapon, "Name")) {
        ++skips["action: weapon unknown to the scripts (" + weapon + ")"];
        break;
      }
      if (!skip && weapon != "_REPAIR") {
        LuaCall c;
        const bool two = engine->lua().is_two_click(weapon, &c) &&
                         !engine->lua().two_click_exception(board, *board.find_pawn(uid), weapon,
                                                            board.find_pawn(uid)->pos, target, &c);
        if (two) {
          ++skips["action: two-click weapon without a recorded second target"];
          break;
        }
      }
      std::string repair_skill = "Skill_Repair";
      for (const auto& [pu, pilot] : rec->pilots) {
        if (pu == uid) repair_skill = engine->repair_skill(pilot);
      }
      bool resisted = false;
      const Board before_attack = board;
      auto [r, mm] = run_step(
          [&](Board& b, ActionOptions o) {
            ActionResult res;
            // A move-only plan step: the recorded game state keeps the mech
            // active (the verifier compared `active` and agreed).
            if (skip) return res;
            auto fire = [&](const ActionOptions& oo) {
              return weapon == "_REPAIR" ? engine->repair(b, uid, kInvalidPoint, repair_skill, oo)
                                         : engine->fire_weapon(b, uid, weapon, target, std::nullopt, oo);
            };
            res = fire(o);
            if (!res.ok() && res.status != ActionStatus::NoEffect) {
              ++refusals[std::string(weapon == "_REPAIR" ? "repair: " : "weapon: ") + to_string(res.status)];
              if (refusal_examples.size() < 12) refusal_examples.push_back(head + " " + weapon + " -> " + str(target));
              o.check_legal = false;
              res = fire(o);
            }
            // The bridge ends the mech's turn after every attack.
            if (Pawn* p = b.find_pawn(uid)) p->active = false;
            return res;
          },
          gt, pred, resisted);
      tag_tolerances(mm, attack_record);
      // Older bridges reported base weapon ids even when an upgrade was
      // powered (no save overlay yet): if a powered variant reproduces the
      // game exactly, the recorded id is the culprit, not the engine.
      const bool real_left = std::any_of(mm.begin(), mm.end(), [](const Mismatch& m) { return m.artefact.empty(); });
      if (real_left && !skip && weapon != "_REPAIR" && !weapon.ends_with("_A") && !weapon.ends_with("_B") &&
          !weapon.ends_with("_AB")) {
        for (const char* suffix : {"_A", "_B", "_AB"}) {
          const std::string variant = weapon + suffix;
          if (!engine->lua().lua_string(variant, "Name")) continue;
          Board vb = before_attack;
          ActionOptions o;
          o.check_legal = false;
          engine->fire_weapon(vb, uid, variant, target, std::nullopt, o);
          if (Pawn* p = vb.find_pawn(uid)) p->active = false;
          std::vector<Mismatch> vm = compare(vb, gt, pred, data);
          tag_tolerances(vm, attack_record);
          if (std::any_of(vm.begin(), vm.end(), [](const Mismatch& m) { return m.artefact.empty(); })) continue;
          for (Mismatch& m : mm) {
            if (m.artefact.empty()) m.artefact = "recording: weapon id lacks its powered upgrade (" + variant + ")";
          }
          ++upgrade_explained[variant];
          board = std::move(vb);
          break;
        }
      }
      if (skip) {
        // Move-only steps: whether the bridge also ended the mech's turn
        // (SKIP -> SetActive(false)) changed between bot versions.
        skipped.insert("#" + std::to_string(uid));
        for (Mismatch& m : mm) {
          if (m.field == "unit.active" && m.where.ends_with("#" + std::to_string(uid)) && m.artefact.empty()) {
            m.artefact = "bridge: SKIP deactivation varies by version";
          }
        }
      }
      const Path path = skip ? Path::Native : attack_path(weapon, date);
      const std::string wname = skip ? "(no attack)" : weapon;
      const std::string label = head + " " + wname + " -> " + str(target) + " [" + path_name(path) + "]";
      const int ab = attack_record ? 1 : 0;
      attack[std::string(ab ? "old-sim desync" : "old-sim right") + " / " + path_name(path)].add(mm, resisted);
      if (path == Path::Native) {
        per_weapon[wname].add(mm, resisted);
        for (const Mismatch& m : mm) {
          if (m.artefact.empty()) ++weapon_fields[wname][m.field];
        }
      }
      record(label, ab, mm);
      (void)bucket_name;
      (void)bucket;
      if (opt.sync) sync(board, gt, data);
    }
  }

  std::printf("turns with a solve input and plan: %d  replayed: %d\n", turns, turns_used);
  std::printf("\nattack steps (board after the move + attack vs the game):\n");
  Tally all_attack;
  for (const auto& [k, t] : attack) {
    print_tally(k.c_str(), t);
    all_attack.steps += t.steps;
    all_attack.exact += t.exact;
    all_attack.tolerated += t.tolerated;
    all_attack.resist += t.resist;
  }
  print_tally("all", all_attack);
  std::printf("\nmove steps (board after the move vs the game):\n");
  for (const auto& [k, t] : moves) print_tally(k.c_str(), t);

  std::printf("\nmismatching fields (steps with that field wrong, tolerated artefacts excluded):\n");
  std::map<std::string, std::map<std::string, int>> by_field;
  for (const auto& [k, t] : attack) {
    for (const auto& [f, n] : t.fields) by_field[f]["attack " + k] += n;
  }
  for (const auto& [k, t] : moves) {
    for (const auto& [f, n] : t.fields) by_field[f]["move " + k] += n;
  }
  for (const auto& [f, m] : by_field) {
    std::printf("  %-22s", f.c_str());
    for (const auto& [k, n] : m) std::printf("  %s: %d", k.c_str(), n);
    std::printf("\n");
  }

  std::printf("\nnative attacks per weapon (steps, exact+tolerated, wrong fields):\n");
  std::vector<std::pair<std::string, Tally>> pw(per_weapon.begin(), per_weapon.end());
  std::sort(pw.begin(), pw.end(), [](const auto& a, const auto& b) { return a.second.steps > b.second.steps; });
  for (const auto& [w, t] : pw) {
    std::printf("  %-26s %4d  ok %4d (%s)", w.c_str(), t.steps, t.ok(), pct(t.ok(), t.steps).c_str());
    for (const auto& [f, n] : weapon_fields[w]) std::printf("  %s:%d", f.c_str(), n);
    std::printf("\n");
  }

  std::printf("\nskipped:\n");
  for (const auto& [k, n] : skips) std::printf("  %5d  %s\n", n, k.c_str());
  std::printf("engine refused (then forced):\n");
  for (const auto& [k, n] : refusals) std::printf("  %5d  %s\n", n, k.c_str());
  for (const std::string& e : refusal_examples) std::printf("      e.g. %s\n", e.c_str());
  std::printf("timing-sensitive resolutions: %d  Lua random death effects: %d\n", timing_sensitive, chance_lua);
  for (const auto& [k, n] : lua_errors) std::printf("  lua error %4d  %s\n", n, k.c_str());
  for (const auto& [k, n] : unapplied) std::printf("  unapplied write %4d  %s\n", n, k.c_str());
  for (const auto& [k, n] : upgrade_explained) {
    std::printf("  explained by an unrecorded upgrade %4d  %s\n", n, k.c_str());
  }

  for (int b = 0; b < 2; ++b) {
    std::printf("\nfirst mismatches (%s):\n", b ? "old-sim desync" : "old-sim right");
    for (const Shown& s : shown[b]) {
      std::printf("  %s\n", s.head.c_str());
      for (const Mismatch& m : s.mm) {
        std::printf("      %-18s %-18s engine %-12s actual %-12s old-sim %s%s\n", m.field.c_str(), m.where.c_str(),
                    m.engine.c_str(), m.actual.c_str(), m.predicted.c_str(),
                    m.artefact.empty() ? "" : ("  (" + m.artefact + ")").c_str());
      }
    }
  }
  return 0;
}

}  // namespace itb::tools
