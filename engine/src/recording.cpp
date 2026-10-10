#include "itb/recording.hpp"

#include <algorithm>
#include <fstream>

#include <nlohmann/json.hpp>

#include "itb/game_data.hpp"
#include "itb/tile_rules.hpp"

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
  const std::string name = get_or<std::string>(t, "terrain", "");
  const int id = get_or<int>(t, "terrain_id", -1);
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
    // Bridges before 2026-05-04 named terrain id 5 (ice) "lava" by mistake.
    // Real lava is water (id 3) with the lava flag (IsTerrain(TERRAIN_LAVA)).
    if (id == static_cast<int>(Terrain::Ice) && !get_or<bool>(t, "lava", false)) {
      warnings.push_back(kIceNamedLava);
      return Terrain::Ice;
    }
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
  if (p.hp > p.max_hp) {
    // Older bridges reported the type's base Health as max_hp, without the
    // pilot and upgrade bonuses that the live HP includes.
    warnings.push_back("hp above the recorded max_hp (max_hp raised)");
    p.max_hp = p.hp;
  }
  // The bridge reports the Lua MoveSpeed (base_move) and the current
  // effective speed (move). Pilots and upgrades aren't recorded separately, so
  // the whole difference is kept as a standing bonus.
  const int effective_move = get_or<int>(u, "move", p.move);
  p.move = static_cast<int8_t>(get_or<int>(u, "base_move", effective_move));
  // A speed below the base is Pawn:GetMoveSpeed() reading 0 for a webbed (or
  // otherwise held) pawn at that moment, not a lasting penalty.
  if (effective_move < p.move) warnings.push_back("effective move below base move (ignored)");
  p.movement.pilot_bonus = static_cast<int8_t>(std::max(0, effective_move - p.move));
  p.team = static_cast<Team>(get_or<int>(u, "team", static_cast<int>(p.team)));
  p.mech = get_or<bool>(u, "mech", p.mech);
  p.flying = get_or<bool>(u, "flying", p.flying);
  p.massive = get_or<bool>(u, "massive", p.massive);
  p.pushable = get_or<bool>(u, "pushable", p.pushable);
  p.armor = get_or<bool>(u, "armor", p.armor);
  p.minor = get_or<bool>(u, "minor", p.minor);
  p.active = get_or<bool>(u, "active", false);
  // A unit that already used its move this turn (not exported by older bridges).
  p.moved = get_or<bool>(u, "moved", false);
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

  // AE pilot level-up skills (Pilot::GetAllPilotSkills order: Health, Move,
  // Grid, Reactor, Opener, Closer, Popular, Thick, Skilled, Invulnerable,
  // Adrenaline, Pain, Regen, Conservative), active from levels 1 and 2. Only
  // the ones that change rules map to abilities: Thick Skin (no fire, no
  // ACID) and Technician (Regen).
  if (auto it = u.find("pilot_skills"); it != u.end() && it->is_array()) {
    const int level = get_or<int>(u, "pilot_level", 0);
    for (const json& sk : *it) {
      if (!sk.is_string()) continue;
      const std::string text = sk.get<std::string>();
      const size_t eq = text.find('=');
      if (eq == std::string::npos) continue;
      const int slot = text.rfind("skill2", 0) == 0 ? 2 : 1;
      if (level < slot) continue;
      int id = -1;
      try {
        id = std::stoi(text.substr(eq + 1));
      } catch (const std::exception&) {
        continue;
      }
      if (id == 7) p.pilot_abilities |= kPilotThick;
      if (id == 12) p.pilot_abilities |= kPilotRegen;
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

// Squad passives (board.hpp Passive) by Lua weapon name; upgraded variants
// carry a suffix. Order matters: longer names first.
uint32_t passive_of(std::string_view weapon) {
  static const std::pair<const char*, uint32_t> kNames[] = {
      {"Passive_FriendlyFire_AB", kPassiveFriendlyFireAB | kPassiveFriendlyFire},
      {"Passive_FriendlyFire_A", kPassiveFriendlyFireA | kPassiveFriendlyFire},
      {"Passive_FriendlyFire_B", kPassiveFriendlyFireB | kPassiveFriendlyFire},
      {"Passive_FriendlyFire", kPassiveFriendlyFire},
      {"Passive_Boosters_A", kPassiveKickoff | kPassiveKickoffUpgraded},
      {"Passive_Boosters_AB", kPassiveKickoff | kPassiveKickoffUpgraded},
      {"Passive_Boosters", kPassiveKickoff},
      {"Passive_ForceAmp", kPassiveForceAmp},
      {"Passive_AutoShields", kPassiveAutoShield},
      {"Passive_FlameImmune", kPassiveFlameImmune},
      {"Passive_FireBoost", kPassiveFireBoost},
      {"Passive_HealingSmoke", kPassiveHealingSmoke},
      {"Passive_PlayerTurnShield", kPassivePlayerTurnShield},
      {"Passive_Leech", kPassivePsionLeech},
      {"Passive_Electric_A", kPassiveElectricSmoke | kPassiveElectricSmokeA},
      {"Passive_Electric", kPassiveElectricSmoke},
      {"Passive_Burrows", kPassiveBurrows},
      {"Passive_FastDecay", kPassiveFastDecay},
      {"Passive_VoidShock", kPassiveVoidShock},
  };
  for (const auto& [name, bits] : kNames) {
    if (weapon.starts_with(name)) return bits;
  }
  return kPassiveNone;
}

std::vector<Point> point_list(const json& j) {
  std::vector<Point> out;
  if (!j.is_array()) return out;
  for (const json& p : j) {
    if (p.is_array() && p.size() >= 2 && p[0].is_number() && p[1].is_number()) {
      out.emplace_back(p[0].get<int>(), p[1].get<int>());
    }
  }
  return out;
}

std::optional<FinalEnvState> final_env(const json& s, const char* key) {
  auto it = s.find(key);
  if (it == s.end() || !it->is_object()) return std::nullopt;
  FinalEnvState f;
  f.complete = get_or<bool>(*it, "complete", false);
  f.mode = get_or<int>(*it, "mode", 0);
  f.phase = get_or<int>(*it, "phase", 0);
  f.instant = get_or<bool>(*it, "instant", false);
  if (auto l = it->find("locations"); l != it->end()) f.locations = point_list(*l);
  return f;
}

void load_objectives(const json& s, Recording& rec);

// Stage 7 mission data: environment marks and the env/mission fields newer
// bridges export (stage 7 spec section 2.4).
void load_mission(const json& s, Recording& rec) {
  MissionData& m = rec.mission;
  m.mission_id = rec.mission_id;
  m.env_type = get_or<std::string>(s, "env_type", "");
  m.difficulty = get_or<int>(s, "difficulty", -1);
  if (auto it = s.find("environment_danger_v2"); it != s.end() && it->is_array()) {
    for (const json& d : *it) {
      if (!d.is_array() || d.size() < 2 || !d[0].is_number() || !d[1].is_number()) continue;
      DangerTile t;
      t.p = {d[0].get<int>(), d[1].get<int>()};
      if (d.size() > 2 && d[2].is_number()) t.damage = d[2].get<int>();
      if (d.size() > 3 && d[3].is_number()) t.kill = d[3].get<int>() != 0;
      if (d.size() > 4 && d[4].is_number()) t.flying_immune = d[4].get<int>();
      m.danger.push_back(t);
    }
  } else if (auto v1 = s.find("environment_danger"); v1 != s.end()) {
    for (Point p : point_list(*v1)) m.danger.push_back(DangerTile{p, 1, true, -1});
  }
  if (auto it = s.find("environment_freeze"); it != s.end()) m.freeze = point_list(*it);
  if (auto it = s.find("environment_tides_index"); it != s.end() && it->is_number()) m.tides_index = it->get<int>();
  if (auto it = s.find("environment_wind_dir"); it != s.end() && it->is_number()) {
    const int d = it->get<int>();
    if (d >= 0 && d < 4) m.wind_dir = static_cast<Dir>(d);
  }
  m.volcano = final_env(s, "mission_final_volcano");
  m.final_cave = final_env(s, "mission_final_cave");
  m.hacking_bot = get_or<int>(s, "mission_hacking_bot_id", -1);
  m.hacking_building = get_or<int>(s, "mission_hacking_hack_id", -1);
  if (auto it = s.find("is_infinite_spawn"); it != s.end() && it->is_boolean()) m.infinite_spawn = it->get<bool>();
  for (const json& u : s["units"]) {
    if (get_or<bool>(u, "queued_launch", false) && !get_or<bool>(u, "is_extra_tile", false)) {
      m.launching.push_back(get_or<int>(u, "uid", -1));
    }
  }
  load_objectives(s, rec);
}

// Stage 8: the mission's objective bookkeeping (environment.hpp ObjectiveData).
void load_objectives(const json& s, Recording& rec) {
  ObjectiveData& o = rec.mission.objectives;
  if (auto it = s.find("bonus_objective_ids"); it != s.end() && it->is_array()) {
    o.bonus_known = true;
    for (const json& b : *it) {
      if (b.is_number_integer()) o.bonus.push_back(b.get<int>());
    }
  }
  o.kills_done = get_or<int>(s, "mission_kills_done", -1);
  o.kill_target = get_or<int>(s, "mission_kill_target", -1);
  o.kill_limit = get_or<int>(s, "mission_kill_limit", -1);
  o.blocked_spawns = get_or<int>(s, "mission_blocked_spawns", -1);
  o.power_start = get_or<int>(s, "mission_power_start", -1);
  // PowerStart is the grid at deployment; nothing can damage the grid before
  // the first player turn.
  if (o.power_start < 0 && rec.board.turn == 1 && s.contains("grid_power")) o.power_start = rec.board.grid_power;
  o.repair_target = get_or<int>(s, "repair_platform_target", -1);
  o.repairs_done = get_or<int>(s, "repair_platforms_used", -1);
  o.mountain_target = get_or<int>(s, "mission_mountain_target", -1);
  o.mountains_done = get_or<int>(s, "mission_mountains_destroyed", -1);
  o.freeze_target = get_or<int>(s, "freeze_building_target", -1);
  if (auto it = s.find("freeze_building_tiles"); it != s.end()) o.freeze_buildings = point_list(*it);
  if (auto it = s.find("terraform_grass_tiles"); it != s.end() && it->is_array()) {
    o.grass = point_list(*it);
    o.grass_known = true;
  }
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
    const Pawn& p = b.add_pawn(load_unit(u, data, rec.warnings));
    if (auto pilot = get_or<std::string>(u, "pilot_id", ""); !pilot.empty()) {
      rec.pilots.emplace_back(p.uid, pilot);
    }
  }
  // Webs come from the tile their source stands on.
  for (Pawn& p : b.pawns()) {
    if (!p.webbed) continue;
    if (const Pawn* src = b.find_pawn(p.web_source)) p.web_tile = src->pos;
  }
  for (const Pawn& p : b.pawns()) {
    if (p.mech && p.team == Team::Player) {
      for (Symbol w : p.weapons) {
        if (w != kNoSymbol) b.passives |= passive_of(symbol_name(w));
      }
    }
  }
  // Board::UpdateLeaders: the last living leader in list order.
  for (const Pawn& p : b.pawns()) {
    if (p.alive() && p.leader != Leader::None) b.psion = p.leader;
  }
  // Recorded HP already includes the Soldier psion's +1.
  for (Pawn& p : b.pawns()) {
    if (p.alive() && mutation_affects(b, p, Leader::Health)) p.health_bonus = true;
  }
  // The bridge's `boosted` is Pawn:IsBoosted(), which includes the Boost
  // psion: only a boost the psion does not explain is the pawn's status.
  for (Pawn& p : b.pawns()) {
    if (p.boosted && mutation_affects(b, p, Leader::Boosted)) p.boosted = false;
  }
  rec.difficulty = get_or<int>(s, "difficulty", -1);
  if (auto it = s.find("spawning_tiles"); it != s.end() && it->is_array()) {
    for (const json& p : *it) {
      if (p.is_array() && p.size() >= 2) b.spawn_points.emplace_back(p[0].get<int>(), p[1].get<int>());
    }
  }
  // Teleporter pads: [x1, y1, x2, y2] per pair. Whoever stands on a pad
  // now has already arrived there.
  if (auto it = s.find("teleporter_pairs"); it != s.end() && it->is_array()) {
    for (const json& pair : *it) {
      if (!pair.is_array() || pair.size() < 4) continue;
      for (int k = 0; k < 2; ++k) {
        const Point p{pair[2 * k].get<int>(), pair[2 * k + 1].get<int>()};
        if (!p.valid()) continue;
        b.teleporters.push_back(p);
        b.tile(p).teleporter = true;
        const Pawn* on = b.pawn_at(p);
        b.teleporter_occupants.push_back(on && on->alive() ? on->uid : -1);
      }
    }
  }
  load_mission(s, rec);
  if (auto it = s.find("attack_order"); it != s.end() && it->is_array()) {
    for (const json& uid : *it) {
      if (uid.is_number_integer()) rec.attack_order.push_back(uid.get<int32_t>());
    }
  }
  return rec;
}

}  // namespace itb
