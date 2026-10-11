// Differential checks of the C++ weapon ports (weapon_diff.hpp).

#include "itb/weapon_diff.hpp"

#include <algorithm>
#include <cstdlib>
#include <map>
#include <sstream>

#include "itb/game_data.hpp"

namespace itb {

void WeaponDiffStats::add(const WeaponDiffStats& o) {
  areas += o.areas;
  effects += o.effects;
  native += o.native;
  mismatches += o.mismatches;
  for (const std::string& e : o.examples) {
    if (examples.size() < 20) examples.push_back(e);
  }
}

namespace {

std::string pt(Point p) { return "(" + std::to_string(p.x) + "," + std::to_string(p.y) + ")"; }

std::string pts(const std::vector<Point>& v) {
  std::string s = "[";
  for (size_t i = 0; i < v.size(); ++i) s += (i ? " " : "") + pt(v[i]);
  return s + "]";
}

// The first field in which two entries differ, as "name: a vs b".
std::string sd_diff(const LuaSpaceDamage& a, const LuaSpaceDamage& b) {
  std::ostringstream o;
#define ITB_CMP(f, show)                                                    \
  if (!(a.f == b.f)) {                                                      \
    o << #f << ": " << show(a.f) << " vs " << show(b.f);                    \
    return o.str();                                                         \
  }
  auto same = [](const auto& v) { return v; };
  ITB_CMP(loc, pt)
  ITB_CMP(iDamage, same)
  ITB_CMP(iPush, same)
  ITB_CMP(iShield, same)
  ITB_CMP(bSimpleMark, same)
  ITB_CMP(iFire, same)
  ITB_CMP(iFrozen, same)
  ITB_CMP(iInjure, same)
  ITB_CMP(iSmoke, same)
  ITB_CMP(iAcid, same)
  ITB_CMP(iCrack, same)
  ITB_CMP(bKO_Effect, same)
  ITB_CMP(boosted, same)
  ITB_CMP(anim_flags, same)
  ITB_CMP(sAnimation, same)
  ITB_CMP(sSound, same)
  ITB_CMP(projectile_art, same)
  ITB_CMP(sImageMark, same)
  ITB_CMP(projectile_kind, same)
  ITB_CMP(projectile_source, pt)
  ITB_CMP(sPawn, same)
  ITB_CMP(iPawnTeam, same)
  ITB_CMP(owner_team, same)
  ITB_CMP(bHide, same)
  ITB_CMP(bHidePath, same)
  ITB_CMP(bHideIcon, same)
  ITB_CMP(bEvacuate, same)
  ITB_CMP(fDelay, same)
  ITB_CMP(path, pts)
  ITB_CMP(move_kind, same)
  ITB_CMP(iTerrain, same)
  ITB_CMP(sScript, same)
  ITB_CMP(grapple_anim, same)
  ITB_CMP(grapple_source, pt)
  ITB_CMP(sItem, same)
  ITB_CMP(mode_override, same)
#undef ITB_CMP
  return "";
}

std::string effect_diff(const LuaSkillEffect& a, const LuaSkillEffect& b) {
  for (int q = 0; q < 2; ++q) {
    const auto& la = q ? a.q_effect : a.effect;
    const auto& lb = q ? b.q_effect : b.effect;
    const char* name = q ? "q_effect" : "effect";
    for (size_t i = 0; i < std::min(la.size(), lb.size()); ++i) {
      const std::string d = sd_diff(la[i], lb[i]);
      if (!d.empty()) return std::string(name) + "[" + std::to_string(i) + "] " + d;
    }
    if (la.size() != lb.size()) {
      return std::string(name) + " size " + std::to_string(la.size()) + " vs " + std::to_string(lb.size());
    }
  }
  if (!(a == b)) return "SkillEffect header fields";
  return "";
}

std::string call_diff(const LuaCall& a, const LuaCall& b) {
  if (a.ok != b.ok || a.error != b.error) return "error: '" + a.error + "' vs '" + b.error + "'";
  if (a.console != b.console) return "console output";
  if (a.writes.size() != b.writes.size()) return "writes";
  for (size_t i = 0; i < a.writes.size(); ++i) {
    if (a.writes[i].describe() != b.writes[i].describe()) return "write " + a.writes[i].describe();
  }
  return "";
}

constexpr uint32_t kSeed = 12345;

}  // namespace

std::vector<std::string> ported_weapons(LuaHost& host, bool all) {
  std::vector<std::string> ids = host.weapon_ids();
  ids.push_back("Move");
  std::sort(ids.begin(), ids.end());
  ids.erase(std::unique(ids.begin(), ids.end()), ids.end());
  std::vector<std::string> out;
  std::map<std::string, std::string> seen;  // binding -> first table
  for (const std::string& id : ids) {
    const std::string binding = host.native_binding(id);
    if (binding.empty()) continue;
    if (!all && !seen.emplace(binding, id).second) continue;
    out.push_back(id);
  }
  return out;
}

void diff_weapon(LuaHost& host, const Board& b, const std::string& weapon, WeaponDiffStats& stats,
                 size_t max_examples) {
  const bool was_native = host.native_weapons();
  auto mismatch = [&](const std::string& what) {
    ++stats.mismatches;
    if (stats.examples.size() < max_examples) stats.examples.push_back(weapon + ": " + what);
  };
  const bool area_port = !host.native_port(weapon, "GetTargetArea").empty();
  const bool effect_port = !host.native_port(weapon, "GetSkillEffect").empty();
  for (const Pawn& shooter : b.pawns()) {
    if (!shooter.pos.valid()) continue;
    const std::string who = std::string(symbol_name(shooter.type)) + "#" + std::to_string(shooter.uid) + "@" +
                            pt(shooter.pos);
    if (area_port) {
      LuaCall lc, nc;
      host.set_native_weapons(false);
      host.seed(kSeed);
      const uint64_t d0 = host.rand_draws();
      const std::vector<Point> la = host.target_area(b, shooter, weapon, shooter.pos, &lc);
      const uint64_t lua_draws = host.rand_draws() - d0;
      host.set_native_weapons(true);
      host.seed(kSeed);
      const uint64_t d1 = host.rand_draws();
      const uint64_t n0 = host.native_calls();
      const std::vector<Point> na = host.target_area(b, shooter, weapon, shooter.pos, &nc);
      stats.native += host.native_calls() - n0;
      const uint64_t native_draws = host.rand_draws() - d1;
      ++stats.areas;
      if (la != na) {
        mismatch("GetTargetArea by " + who + ": " + pts(la) + " vs " + pts(na));
      } else if (const std::string d = call_diff(lc, nc); !d.empty()) {
        mismatch("GetTargetArea by " + who + ": " + d);
      } else if (lua_draws != native_draws) {
        mismatch("GetTargetArea by " + who + ": random draws");
      }
    }
    if (!effect_port) continue;
    for (int i = 0; i < kTileCount; ++i) {
      const Point target = Point::from_index(i);
      LuaCall lc, nc;
      host.set_native_weapons(false);
      host.seed(kSeed);
      const uint64_t d0 = host.rand_draws();
      const LuaSkillEffect le = host.skill_effect_raw(b, shooter, weapon, shooter.pos, target, &lc);
      const uint64_t lua_draws = host.rand_draws() - d0;
      host.set_native_weapons(true);
      host.seed(kSeed);
      const uint64_t d1 = host.rand_draws();
      const uint64_t n0 = host.native_calls();
      const LuaSkillEffect ne = host.skill_effect_raw(b, shooter, weapon, shooter.pos, target, &nc);
      stats.native += host.native_calls() - n0;
      const uint64_t native_draws = host.rand_draws() - d1;
      ++stats.effects;
      if (const std::string d = effect_diff(le, ne); !d.empty()) {
        mismatch("GetSkillEffect by " + who + " at " + pt(target) + ": " + d);
      } else if (const std::string c = call_diff(lc, nc); !c.empty()) {
        mismatch("GetSkillEffect by " + who + " at " + pt(target) + ": " + c);
      } else if (lua_draws != native_draws) {
        mismatch("GetSkillEffect by " + who + " at " + pt(target) + ": random draws");
      }
    }
  }
  host.set_native_weapons(was_native);
}

Board random_board(const GameData& data, const std::vector<std::string>& weapons, std::mt19937& rng) {
  auto chance = [&](double p) { return std::uniform_real_distribution<double>(0, 1)(rng) < p; };
  auto pick = [&](int n) { return std::uniform_int_distribution<int>(0, n - 1)(rng); };
  Board b;
  static const Terrain kTerrains[] = {Terrain::Road,  Terrain::Road,   Terrain::Road,     Terrain::Road,
                                      Terrain::Rubble, Terrain::Building, Terrain::Building, Terrain::Mountain,
                                      Terrain::Water, Terrain::Ice,    Terrain::Forest,   Terrain::Sand,
                                      Terrain::Hole};
  static const char* kItems[] = {"Item_Mine", "Freeze_Mine", "Item_Mine_Pod"};
  for (int i = 0; i < kTileCount; ++i) {
    Tile& t = b.tile(Point::from_index(i));
    t.terrain = kTerrains[pick(static_cast<int>(std::size(kTerrains)))];
    switch (t.terrain) {
      case Terrain::Building:
        t.max_hp = static_cast<int8_t>(1 + pick(2));
        t.hp = static_cast<int8_t>(chance(0.2) ? 0 : 1 + pick(t.max_hp));
        t.populated = chance(0.7);
        t.shield = chance(0.1);
        t.frozen = chance(0.1);
        if (chance(0.05)) t.unique_building = intern("str_power1");
        break;
      case Terrain::Mountain:
        t.max_hp = 2;
        t.hp = static_cast<int8_t>(1 + pick(2));
        t.shield = chance(0.05);
        t.frozen = chance(0.05);
        break;
      case Terrain::Ice:
        t.max_hp = 2;
        t.hp = static_cast<int8_t>(1 + pick(2));
        break;
      case Terrain::Water:
        t.lava = chance(0.15);
        t.acid = chance(0.15);
        break;
      default:
        t.fire = chance(0.1) ? FireState::Burning : FireState::None;
        t.smoke = chance(0.1);
        t.acid = chance(0.1);
        t.cracked = chance(0.07);
        t.spikes = chance(0.03);
        if (chance(0.04)) t.pod = PodState::Present;
        if (chance(0.05)) t.item = intern(kItems[pick(3)]);
        break;
    }
    if (chance(0.03)) t.walls = static_cast<uint8_t>(1 << pick(4));
  }
  const std::vector<PawnDef>& defs = data.pawns();
  const int count = 2 + pick(11);
  int32_t uid = chance(0.5) ? 0 : 2000 + pick(1000);
  for (int k = 0; k < count && !defs.empty(); ++k) {
    const PawnDef& def = defs[static_cast<size_t>(pick(static_cast<int>(defs.size())))];
    Point pos = Point::from_index(pick(kTileCount));
    Pawn p = data.make_pawn(def, uid++, pos);
    p.mech = def.pawn_class.size() > 0 && chance(0.7);
    if (chance(0.1)) p.team = static_cast<Team>(std::array<int, 4>{1, 2, 6, 6}[static_cast<size_t>(pick(4))]);
    if (p.max_hp > 0) p.hp = static_cast<int8_t>(chance(0.1) ? 0 : 1 + pick(p.max_hp));
    p.fire = chance(0.1);
    p.frozen = chance(0.1);
    p.acid = chance(0.1);
    p.shield = chance(0.1);
    p.boosted = chance(0.1);
    p.infected = chance(0.05);
    p.active = chance(0.7);
    p.moved = chance(0.3);
    p.armor = p.armor || chance(0.05);
    p.flying = p.flying || chance(0.05);
    p.jumper = p.jumper || chance(0.05);
    p.teleporter = p.teleporter || chance(0.03);
    p.pushable = chance(0.9) ? p.pushable : !p.pushable;
    if (chance(0.1)) p.pilot_abilities = 1u << pick(16);
    if (chance(0.1)) p.movement.bonus_shift = static_cast<int8_t>(1 + pick(3));
    if (!weapons.empty()) {
      for (Symbol& w : p.weapons) {
        if (w == kNoSymbol && chance(0.3)) w = intern(weapons[static_cast<size_t>(pick(static_cast<int>(weapons.size())))]);
      }
    }
    if (chance(0.3)) {
      p.queued.weapon = static_cast<int8_t>(pick(2));
      p.queued.origin = pos;
      p.queued.target = Point::from_index(pick(kTileCount));
    }
    b.add_pawn(p);
  }
  // Webs between neighbours, and dead bodies sharing a tile.
  for (Pawn& p : b.pawns()) {
    if (chance(0.05) && b.pawns().size() > 1) {
      const Pawn& src = b.pawns()[static_cast<size_t>(pick(static_cast<int>(b.pawns().size())))];
      if (src.uid != p.uid) {
        p.webbed = true;
        // A neighbour's web is tile state too (Tile::web_out / web_in).
        const Point d = p.pos - src.pos;
        if (src.pos.valid() && p.pos.valid() && std::abs(d.x) + std::abs(d.y) == 1) {
          const int dir = d.y < 0 ? 0 : d.x > 0 ? 1 : d.y > 0 ? 2 : 3;
          Tile& from = b.tile(src.pos);
          if (!(from.web_out >> dir & 1)) {
            from.web_out = static_cast<uint8_t>(from.web_out | (1u << dir));
            ++b.tile(p.pos).web_in;
          }
        }
      }
    }
  }
  b.grid_power = 1 + pick(7);
  b.turn = 1 + pick(5);
  b.player_phase = chance(0.8);
  if (chance(0.2)) b.passives = 1u << pick(18);
  if (chance(0.1)) b.psion = static_cast<Leader>(std::array<int, 6>{1, 4, 5, 6, 9, 11}[static_cast<size_t>(pick(6))]);
  return b;
}

}  // namespace itb
