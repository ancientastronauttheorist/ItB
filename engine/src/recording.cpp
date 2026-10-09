#include "itb/recording.hpp"

#include <algorithm>
#include <fstream>

#include <nlohmann/json.hpp>

#include "itb/game_data.hpp"

namespace itb {
namespace {

using nlohmann::json;

template <typename T>
T get_or(const json& j, const char* key, T fallback) {
  auto it = j.find(key);
  if (it == j.end() || it->is_null()) return fallback;
  try {
    return it->get<T>();
  } catch (const json::exception&) {
    return fallback;
  }
}

Point get_point(const json& j, const char* key) {
  auto it = j.find(key);
  if (it == j.end() || !it->is_array() || it->size() < 2) return kInvalidPoint;
  return {(*it)[0].get<int>(), (*it)[1].get<int>()};
}

Terrain terrain_from(const json& t, Tile& tile, std::vector<std::string>& warnings) {
  // The bridge's terrain name is authoritative: lava arrives with id 5.
  const std::string name = get_or<std::string>(t, "terrain", "");
  if (name == "ground") return Terrain::Road;
  if (name == "building") return Terrain::Building;
  if (name == "rubble") return Terrain::Rubble;
  if (name == "water") return Terrain::Water;
  if (name == "mountain") return Terrain::Mountain;
  if (name == "ice") return Terrain::Ice;
  if (name == "forest") return Terrain::Forest;
  if (name == "sand") return Terrain::Sand;
  if (name == "chasm") return Terrain::Hole;
  if (name == "lava") {
    tile.lava = true;
    return Terrain::Water;
  }
  warnings.push_back("unknown terrain '" + name + "'");
  return static_cast<Terrain>(get_or<int>(t, "terrain_id", 0));
}

void load_tile(const json& t, Board& board, std::vector<std::string>& warnings) {
  const Point p{get_or<int>(t, "x", -1), get_or<int>(t, "y", -1)};
  if (!p.valid()) {
    warnings.push_back("tile with invalid position");
    return;
  }
  Tile& tile = board.tile(p);
  tile = Tile{};
  tile.terrain = terrain_from(t, tile, warnings);
  if (tile.is_building() || tile.is_mountain()) {
    tile.hp = static_cast<int8_t>(get_or<int>(t, "building_hp", tile.is_mountain() ? 2 : 1));
    tile.max_hp = static_cast<int8_t>(tile.is_mountain() ? 2 : std::max<int>(tile.hp, 1));
    // The bridge reports "frozen" for anything frozen on the tile; only
    // structures carry their own frozen state.
    tile.frozen = get_or<bool>(t, "frozen", false);
  }
  // The bridge only reports population on mountains, where it is
  // meaningless; recorded buildings are populated unless proven otherwise.
  if (tile.is_building()) tile.populated = true;
  if (tile.terrain == Terrain::Ice) tile.hp = tile.max_hp = 2;
  if (get_or<bool>(t, "fire", false)) tile.fire = FireState::Burning;
  tile.smoke = get_or<bool>(t, "smoke", false);
  tile.acid = get_or<bool>(t, "acid", false);
  tile.cracked = get_or<bool>(t, "cracked", false);
  if (get_or<bool>(t, "pod", false)) tile.pod = PodState::Present;
  tile.conveyor = static_cast<int8_t>(get_or<int>(t, "conveyor", -1));
  if (auto item = get_or<std::string>(t, "item", ""); !item.empty()) tile.item = intern(item);
  if (auto obj = get_or<std::string>(t, "objective_name", ""); !obj.empty()) {
    tile.unique_building = intern(obj);
  } else if (get_or<bool>(t, "unique_building", false)) {
    tile.unique_building = intern("unique_building");
  }
}

Pawn load_unit(const json& u, const GameData* data, std::vector<std::string>& warnings) {
  const std::string type = get_or<std::string>(u, "type", "");
  const int32_t uid = get_or<int>(u, "uid", -1);
  const Point pos{get_or<int>(u, "x", -1), get_or<int>(u, "y", -1)};

  Pawn p;
  const PawnDef* def = data ? data->pawn(type) : nullptr;
  if (def) {
    p = data->make_pawn(*def, uid, pos);
  } else {
    if (data) warnings.push_back("unknown pawn type '" + type + "'");
    p.uid = uid;
    p.type = intern(type);
    p.pos = pos;
  }
  // Recorded values win over definition defaults (pilots, upgrades, statuses).
  p.hp = static_cast<int8_t>(get_or<int>(u, "hp", p.hp));
  p.max_hp = static_cast<int8_t>(get_or<int>(u, "max_hp", p.max_hp));
  // The bridge reports the Lua MoveSpeed (base_move) and the current
  // effective speed (move). Pilots and upgrades aren't recorded separately, so
  // the whole difference is kept as a standing bonus.
  const int effective_move = get_or<int>(u, "move", p.move);
  p.move = static_cast<int8_t>(get_or<int>(u, "base_move", effective_move));
  p.movement.pilot_bonus = static_cast<int8_t>(effective_move - p.move);
  p.team = static_cast<Team>(get_or<int>(u, "team", static_cast<int>(p.team)));
  p.mech = get_or<bool>(u, "mech", p.mech);
  p.flying = get_or<bool>(u, "flying", p.flying);
  p.massive = get_or<bool>(u, "massive", p.massive);
  p.pushable = get_or<bool>(u, "pushable", p.pushable);
  p.armor = get_or<bool>(u, "armor", p.armor);
  p.minor = get_or<bool>(u, "minor", p.minor);
  p.active = get_or<bool>(u, "active", false);
  p.fire = get_or<bool>(u, "fire", false);
  p.frozen = get_or<bool>(u, "frozen", false);
  p.acid = get_or<bool>(u, "acid", false);
  p.shield = get_or<bool>(u, "shield", false);
  p.boosted = get_or<bool>(u, "boosted", false);
  p.webbed = get_or<bool>(u, "web", false);
  p.infected = get_or<bool>(u, "infected", false);
  p.web_source = get_or<int>(u, "web_source_uid", -1);

  p.weapons = {};
  if (auto it = u.find("weapons"); it != u.end() && it->is_array()) {
    size_t i = 0;
    for (const json& w : *it) {
      if (i >= p.weapons.size()) {
        warnings.push_back(type + " has more than " + std::to_string(kMaxWeapons) + " weapons");
        break;
      }
      if (w.is_string()) p.weapons[i++] = intern(w.get<std::string>());
    }
  }

  if (get_or<bool>(u, "has_queued_attack", false)) {
    // The bridge does not report which weapon is queued; Vek carry one.
    p.queued.weapon = 0;
    p.queued.origin = get_point(u, "queued_origin");
    p.queued.target = get_point(u, "queued_target");
  }
  return p;
}

}  // namespace

std::optional<Recording> load_recording(const std::filesystem::path& path,
                                        const GameData* data, std::string* error) {
  auto fail = [&](const std::string& msg) -> std::optional<Recording> {
    if (error) *error = path.string() + ": " + msg;
    return std::nullopt;
  };

  std::ifstream in(path);
  if (!in) return fail("cannot open");
  json root;
  try {
    in >> root;
  } catch (const json::exception& e) {
    return fail(std::string("bad JSON: ") + e.what());
  }

  Recording rec;
  const json* state = &root;
  if (root.contains("data")) {
    rec.run_id = get_or<std::string>(root, "run_id", "");
    rec.mission_index = get_or<int>(root, "mission_index", 0);
    rec.turn = get_or<int>(root, "turn", 0);
    rec.label = get_or<std::string>(root, "label", "");
    const json& d = root["data"];
    if (!d.is_object() || !d.contains("bridge_state")) return fail("no data.bridge_state");
    state = &d["bridge_state"];
  }
  const json& s = *state;
  if (!s.contains("tiles") || !s.contains("units")) return fail("not a bridge board");

  rec.mission_id = get_or<std::string>(s, "mission_id", "");
  rec.phase = get_or<std::string>(s, "phase", "");
  Board& b = rec.board;
  b.grid_power = get_or<int>(s, "grid_power", b.grid_power);
  b.grid_power_max = get_or<int>(s, "grid_power_max", b.grid_power_max);
  b.turn = get_or<int>(s, "turn", b.turn);
  b.total_turns = get_or<int>(s, "total_turns", b.total_turns);

  for (const json& t : s["tiles"]) load_tile(t, b, rec.warnings);
  for (const json& u : s["units"]) {
    // Multi-tile pawns are reported once per extra tile; keep the main entry.
    if (get_or<bool>(u, "is_extra_tile", false)) continue;
    b.add_pawn(load_unit(u, data, rec.warnings));
  }
  if (auto it = s.find("spawning_tiles"); it != s.end() && it->is_array()) {
    for (const json& p : *it) {
      if (p.is_array() && p.size() >= 2) b.spawn_points.emplace_back(p[0].get<int>(), p[1].get<int>());
    }
  }
  if (auto it = s.find("attack_order"); it != s.end() && it->is_array()) {
    for (const json& uid : *it) {
      if (uid.is_number_integer()) rec.attack_order.push_back(uid.get<int32_t>());
    }
  }
  return rec;
}

}  // namespace itb
