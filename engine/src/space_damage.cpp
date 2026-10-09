#include "itb/space_damage.hpp"

#include <utility>

namespace itb {
namespace {

SpaceDamage path_entry(std::vector<Point> path, MoveKind kind, float delay) {
  SpaceDamage sd;
  sd.path = std::move(path);
  sd.move_kind = kind;
  sd.delay = delay;
  return sd;
}

SpaceDamage projectile_entry(Point source, SpaceDamage sd, std::string_view art, float delay) {
  sd.projectile_source = source;
  sd.art = intern(art);
  sd.delay = delay;
  if (art.find("laser") != std::string_view::npos) {
    sd.projectile = ProjectileKind::Laser;
    sd.delay = kNoDelay;
  } else {
    sd.projectile = ProjectileKind::Projectile;
  }
  return sd;
}

SpaceDamage artillery_entry(SpaceDamage sd, std::string_view art, float delay) {
  sd.projectile = ProjectileKind::Artillery;
  sd.art = intern(art);
  sd.delay = delay;
  return sd;
}

SpaceDamage melee_entry(Point origin, SpaceDamage sd, float delay) {
  sd.move_kind = MoveKind::Melee;
  sd.path = {origin, sd.loc};
  sd.delay = delay;
  return sd;
}

}  // namespace

SpaceDamage space_damage(Point loc, int damage, Dir push) {
  SpaceDamage sd;
  sd.loc = loc;
  sd.damage = damage;
  sd.push = push;
  return sd;
}

void boost_damage(SpaceDamage& sd) {
  if (sd.damage > 0 && sd.damage != kDamageDeath && sd.damage != kDamageZero) {
    ++sd.damage;
  } else if (sd.damage < 0 && sd.damage > -10) {
    --sd.damage;
  }
  sd.boosted = true;
}

void SkillEffect::add_delay(float seconds) {
  SpaceDamage sd;
  sd.delay = seconds;
  effect.push_back(sd);
}

void SkillEffect::add_projectile(Point source, SpaceDamage sd, std::string_view art, float delay) {
  effect.push_back(projectile_entry(source, std::move(sd), art, delay));
}

void SkillEffect::add_queued_projectile(SpaceDamage sd, std::string_view art, float delay) {
  q_effect.push_back(projectile_entry(kInvalidPoint, std::move(sd), art, delay));
}

void SkillEffect::add_artillery(SpaceDamage sd, std::string_view art, float delay) {
  effect.push_back(artillery_entry(std::move(sd), art, delay));
}

void SkillEffect::add_queued_artillery(SpaceDamage sd, std::string_view art, float delay) {
  q_effect.push_back(artillery_entry(std::move(sd), art, delay));
}

void SkillEffect::add_melee(Point origin, SpaceDamage sd, float delay) {
  effect.push_back(melee_entry(origin, std::move(sd), delay));
}

void SkillEffect::add_queued_melee(Point origin, SpaceDamage sd, float delay) {
  q_effect.push_back(melee_entry(origin, std::move(sd), delay));
}

void SkillEffect::add_move(std::vector<Point> path, float delay) {
  effect.push_back(path_entry(std::move(path), MoveKind::Walk, delay));
}

void SkillEffect::add_leap(std::vector<Point> path, float delay) {
  effect.push_back(path_entry(std::move(path), MoveKind::Leap, delay));
}

void SkillEffect::add_charge(std::vector<Point> path, float delay) {
  effect.push_back(path_entry(std::move(path), MoveKind::Charge, delay));
}

void SkillEffect::add_burrow(std::vector<Point> path, float delay) {
  effect.push_back(path_entry(std::move(path), MoveKind::Burrow, delay));
}

void SkillEffect::add_teleport(Point from, Point to, float delay) {
  effect.push_back(path_entry({from, to}, MoveKind::Teleport, delay));
}

void SkillEffect::add_script(std::string script) {
  SpaceDamage sd;
  sd.script = std::move(script);
  effect.push_back(sd);
}

void SkillEffect::add_air_strike(Point loc, std::string_view art) {
  SpaceDamage sd;
  sd.loc = loc;
  sd.projectile = ProjectileKind::AirStrike;
  sd.art = intern(art);
  sd.delay = kProjDelay;
  effect.push_back(sd);
}

void SkillEffect::add_dropper(SpaceDamage sd, std::string_view art) {
  sd.projectile = ProjectileKind::Pylon;
  sd.art = intern(art);
  sd.delay = kNoDelay;
  effect.push_back(sd);
}

}  // namespace itb
