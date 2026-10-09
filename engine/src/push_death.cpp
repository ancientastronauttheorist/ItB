// Stage 3: pushes (Pawn::Push, FinishPush, Board::IsPushBlocked, PushDamage)
// and the death pipeline (ProcessDeath, TriggerDeathEffect, DetonateCorpse,
// psion leaders, removal of bodies).

#include <algorithm>
#include <string>

#include "itb/game_data.hpp"
#include "itb/movement.hpp"
#include "rules_detail.hpp"
#include "simulation.hpp"

namespace itb::detail {
namespace {

// The tile's occupant list as the push obstacle test sees it: every pawn
// there (dying and fallen bodies included), in arrival order.
const Pawn* first_listed(const Board& board, Point p) {
  const Pawn* first = nullptr;
  for (const Pawn& pawn : board.pawns()) {
    if (pawn.pos == p && (!first || pawn.arrival < first->arrival)) first = &pawn;
  }
  return first;
}

// Pawn::FlipQueued: the attack is mirrored through its origin.
void flip_queued(Pawn& pawn) {
  if (!pawn.queued.active()) return;
  const Point origin = pawn.queued.origin.valid() ? pawn.queued.origin : pawn.pos;
  pawn.queued.target = origin * 2 - pawn.queued.target;
}

SpaceDamage explosion_hit(Point p, std::string_view anim) {
  SpaceDamage sd = space_damage(p, 1);
  sd.animation = intern(anim);
  sd.mode_override = kModeExplosion;
  return sd;
}

}  // namespace

// ---- Pushes ---------------------------------------------------------------------

// Pawn::Push.
void Simulation::start_push(int32_t uid, Dir dir, int cause) {
  Pawn* pawn = board_.find_pawn(uid);
  if (!pawn) return;
  if (dir == Dir::Flip) {
    // DIR_FLIP only mirrors the queued attack of a living, flippable pawn.
    if (!pawn->ignore_flip && pawn->alive()) {
      flip_queued(*pawn);
      changed_ = true;
    }
    return;
  }
  if (!pawn->pushable || !is_cardinal(dir)) return;
  // A push towards the edge does nothing at all (it is never "blocked").
  if (!step(pawn->pos, dir).valid()) return;
  // Dead, frozen and massive pawns are pushed too. A running push or lunge
  // is restarted with the new direction.
  PawnSim& ps = state(uid);
  ps.tracker.running = true;
  ps.tracker.dir = dir;
  ps.tracker.from = pawn->pos;
  ps.tracker.cause = cause;
  ps.tracker.end_frame = first_pawn_update(uid) + clock_.tracker_updates(dur_.push) - 1;
  changed_ = true;
  log(ResolveEventType::PushStarted, pawn->pos, uid, static_cast<int>(dir));
}

// Board::IsPushBlocked(p, d): terrain, the tile's first occupant, then the
// wall on the edge the pawn would enter through.
bool Simulation::push_blocked(Point p, Dir dir, int32_t pusher) {
  if (!p.valid()) return false;
  const Tile& t = board_.tile(p);
  if (t.is_building() || t.is_mountain()) return true;
  if (const Pawn* first = first_listed(board_, p)) {
    if (first->alive() || is_corpse(board_, *first)) return true;
    // A dying body blocks while its death animation is under half done
    // (frozen where KillInstant stopped it).
    const PawnSim& ps = state(first->uid);
    if (ps.death_anim) {
      const int n = death_updates(ps);
      const bool blocked = ps.death_anim->progress(n) < 0.5f;
      if (ps.frozen_updates < 0 && death_anim_playing(ps)) {
        const bool earlier = n > 0 && ps.death_anim->progress(n - 1) < 0.5f;
        const bool later = ps.death_anim->progress(n + 1) < 0.5f;
        if (earlier != blocked || later != blocked) flag(TimingKind::DyingBlocker, p, pusher);
      }
      if (blocked) return true;
    }
  }
  return t.has_wall(opposite(dir));
}

// BoardSpace::PushDamage: the obstacle tile takes a 1-damage bump (pawns,
// buildings with their grid roll, mountains), then the wall between the two
// tiles is knocked down.
void Simulation::push_damage(Point target, Point from, Dir dir) {
  rules_.pushes.clear();
  damage_tile(board_, target, 1, DamageMode::Push, rules_);
  rules_.pushes.clear();
  note_deaths();
  register_holes();
  Tile& a = board_.tile(from);
  Tile& b = board_.tile(target);
  if (a.has_wall(dir) || b.has_wall(opposite(dir))) {
    a.walls = static_cast<uint8_t>(a.walls & ~(1u << static_cast<int>(dir)));
    b.walls = static_cast<uint8_t>(b.walls & ~(1u << static_cast<int>(opposite(dir))));
  }
}

// Pawn::FinishPush, on the frame the tracker passes its length.
void Simulation::finish_push(Pawn& pawn, PawnSim& ps) {
  const int32_t uid = pawn.uid;
  const Dir dir = ps.tracker.dir;
  const Point from = pawn.pos;
  const Point target = step(from, dir);
  Action rec{ActionKind::PushEnd, frame_, {from, target}, new_cause(), ps.tracker.cause, false};
  if (push_blocked(target, dir, uid)) {
    log(ResolveEventType::PushBlocked, target, uid);
    // The pushed pawn takes its bump first (dead non-mechs ignore it), then
    // the obstacle.
    damage_pawn(board_, pawn, 1, DamageMode::Push, rules_);
    note_deaths();
    push_damage(target, from, dir);
  } else {
    // Pawn::MoveDir: relocate (Injured applies: the push no longer makes it
    // busy), carry the queued attack along, then the new tile's dangers at once.
    set_space(board_, pawn, target, pawn_busy(pawn, false), &rules_);
    if (Pawn* p = board_.find_pawn(uid)) shift_queued_shot(*p, dir_vector(dir));
    note_deaths();
    check_terrain_dangers(board_, target, rules_);
    note_deaths();
    log(ResolveEventType::PushMoved, target, uid);
    if (const Pawn* p = board_.find_pawn(uid)) {
      const Tile& t = board_.tile(target);
      rec.hazard = t.on_fire() || t.acid || t.lava || t.spikes || t.smoke ||
                   (p->fire && t.terrain == Terrain::Water);
    }
  }
  actions_.push_back(std::move(rec));
  changed_ = true;
}

// ---- Deaths ---------------------------------------------------------------------------

void Simulation::note_deaths() {
  for (const Pawn& p : board_.pawns()) {
    PawnSim& ps = state(p.uid);
    if (!ps.dead && !p.alive()) {
      note_death(p, ps);
    } else if (ps.dead && p.alive()) {
      // A mech corpse healed back to life.
      ps.dead = ps.death_pending = ps.death_fx_pending = ps.detonate_pending = false;
      ps.frozen_updates = -1;
      ps.death_anim = nullptr;
      ps.xp_gone = -1;
      changed_ = true;
    }
  }
}

void Simulation::note_death(const Pawn& pawn, PawnSim& ps) {
  ps.dead = true;
  ps.death_pending = true;
  // The death animation advances in render passes from this frame on.
  ps.death_frame = frame_;
  ps.frozen_updates = -1;
  ps.death_anim = death_timeline(pawn);
  changed_ = true;
}

void Simulation::instant_kill(const Pawn& pawn) {
  PawnSim& ps = state(pawn.uid);
  if (!ps.dead && !pawn.alive()) note_death(pawn, ps);
  if (ps.dead && ps.death_anim && ps.frozen_updates < 0) {
    ps.frozen_updates = death_updates(ps);
    changed_ = true;
  }
}

bool Simulation::start_fall(Pawn& pawn) {
  PawnSim& ps = state(pawn.uid);
  // Pawn::Fall waits for a running push (it is asked again later); a fall
  // already under way is not restarted.
  if (ps.falling || (ps.tracker.running && !ps.tracker.has_melee)) return true;
  ps.falling = true;
  ps.fall_end = first_pawn_update(pawn.uid) + clock_.tracker_updates(dur_.fall) - 1;
  changed_ = true;
  return true;
}

// Pawn::ProcessDeath, once no push or lunge is running on the pawn.
void Simulation::process_death(Pawn& pawn, PawnSim& ps) {
  ps.death_pending = false;
  ps.death_fx_pending = true;
  if (pawn.team == Team::Player) set_pawn_fire(board_, pawn, false);
  // The XP popup over a dead enemy keeps the body on the board.
  if (pawn.team == Team::Enemy && !pawn.mech && !pawn.retreating) {
    ps.xp_gone = frame_ + clock_.tracker_updates(dur_.xp_popup);
  }
  changed_ = true;
  log(ResolveEventType::DeathProcessed, pawn.pos, pawn.uid);
}

// Pawn::IsExploding: Explodes / Burns, or the Blast, boss, spider or fire
// psion's mutation.
bool Simulation::is_exploding(const Pawn& pawn) const {
  return pawn.explodes || pawn.burns || mutation_affects(board_, pawn, Leader::Explode) ||
         mutation_affects(board_, pawn, Leader::Boss) ||
         mutation_affects(board_, pawn, Leader::Spider) ||
         mutation_affects(board_, pawn, Leader::Fire);
}

// Pawn::TriggerDeathEffect: [ACID pool, Fast Decay forest, Lua entries],
// appended to the stack as a FULL_DELAY follow-up effect.
void Simulation::trigger_death_effect(Pawn& pawn, PawnSim& ps) {
  ps.death_fx_pending = false;
  const int32_t uid = pawn.uid;
  const Point tile = pawn.pos;
  SkillEffect fx;
  if (ctx_.death_effect) fx = ctx_.death_effect(owner_, pawn, tile);
  const Pawn* p = board_.find_pawn(uid);
  if (!p) return;
  std::vector<SpaceDamage> front;
  if (p->acid && !is_corpse(board_, *p)) {
    SpaceDamage acid = space_damage(tile);
    acid.acid = StatusChange::Apply;
    front.push_back(acid);
  }
  if (board_.has_passive(kPassiveFastDecay) && is_vek(*p) && tile.valid() &&
      board_.tile(tile).terrain != Terrain::Water && board_.tile(tile).terrain != Terrain::Hole) {
    SpaceDamage decay = space_damage(tile);
    decay.fire = StatusChange::Remove;
    decay.terrain = static_cast<int>(Terrain::Forest);
    front.push_back(decay);
  }
  fx.effect.insert(fx.effect.begin(), front.begin(), front.end());
  if (is_exploding(*p)) ps.detonate_pending = true;
  prepare_effect(fx, tile, tile, p->team, kNoSymbol);
  fx.owner = last_owner_ >= 0 ? last_owner_ : uid;
  fx.follow_up = true;
  push_back(std::move(fx), kFullDelay, last_shot_, new_cause());
  changed_ = true;
  log(ResolveEventType::DeathEffect, tile, uid);
}

// Pawn::DetonateCorpse (P5, no effect active): only if the explosion's source
// still holds. Otherwise the request stays pending, and the body with it.
void Simulation::detonate_corpse(Pawn& pawn, PawnSim& ps) {
  if (!ps.detonate_pending || !is_exploding(pawn)) return;
  const Point pos = pawn.pos;
  SkillEffect fx;
  const bool blast = pawn.explodes || mutation_affects(board_, pawn, Leader::Explode) ||
                     mutation_affects(board_, pawn, Leader::Boss);
  if (blast) {
    // Explosion mode (no armor/ACID, not a bump), the neighbours then the
    // pawn's own tile: left, down, right, up, self.
    fx.effect.push_back(explosion_hit(pos, "explo_fire1"));
    for (int d = 0; d < 4; ++d) {
      const Point q = step(pos, static_cast<Dir>(d));
      fx.effect.insert(fx.effect.begin(), explosion_hit(q, "exploout1_" + std::to_string(d)));
    }
  }
  if (mutation_affects(board_, pawn, Leader::Spider)) {
    // An egg on its own tile, or lobbed onto a free neighbour.
    static const Symbol egg = intern("SpiderlingEgg1");
    SpaceDamage spawn = space_damage(pos);
    spawn.spawn_pawn = egg;
    if (!is_blocked(board_, pos, Pathing::lua(PathProfile::Ground))) {
      fx.effect.push_back(spawn);
    } else {
      std::vector<Point> free;
      for (int dx = -1; dx <= 1; ++dx) {
        for (int dy = -1; dy <= 1; ++dy) {
          const Point q = pos + Point{dx, dy};
          if ((dx || dy) && q.valid() && !is_blocked(board_, q, Pathing::lua(PathProfile::Ground)) &&
              board_.tile(q).pod == PodState::None) {
            free.push_back(q);
          }
        }
      }
      if (!free.empty()) {
        int pick = ctx_.spider_egg ? ctx_.spider_egg(owner_, pawn, free) : 0;
        pick = std::clamp(pick, 0, static_cast<int>(free.size()) - 1);
        if (result_) {
          result_->chances.push_back(ChanceRecord{ChanceKind::SpiderEgg, frame_, free[static_cast<size_t>(pick)],
                                                  0, pick, static_cast<int>(free.size())});
        }
        spawn.loc = free[static_cast<size_t>(pick)];
        spawn.projectile = ProjectileKind::Artillery;
        spawn.art = intern("effects/shotup_spider.png");
        spawn.projectile_source = pos;
        spawn.delay = kFullDelay;
        fx.effect.push_back(spawn);
      }
    }
  }
  if ((mutation_affects(board_, pawn, Leader::Fire) || pawn.burns) && pos.valid() &&
      board_.tile(pos).terrain != Terrain::Water) {
    SpaceDamage burn = space_damage(pos);
    burn.fire = StatusChange::Apply;
    burn.animation = intern("explo_fire1");
    fx.effect.push_back(burn);
  }
  prepare_effect(fx, pos, pos, last_team_ != Team::None ? last_team_ : pawn.team, kNoSymbol);
  fx.owner = last_owner_ >= 0 ? last_owner_ : pawn.uid;
  fx.follow_up = true;
  push_back(std::move(fx), kFullDelay, last_shot_, new_cause());
  ps.detonate_pending = false;
  changed_ = true;
  log(ResolveEventType::CorpseExploded, pos, pawn.uid);
}

// Board::UpdateLeaders: the board psion comes from living leaders only.
void Simulation::update_leaders() {
  if (!track_leaders_) return;
  Leader leader = Leader::None;
  for (const Pawn& p : board_.pawns()) {
    if (p.alive() && p.leader != Leader::None) {
      leader = p.leader;
      break;
    }
  }
  if (board_.psion != leader) {
    board_.psion = leader;
    changed_ = true;
  }
}

// Board::OnLoop's removal test, before the pawn's own update.
bool Simulation::removable(const Pawn& pawn, const PawnSim& ps) const {
  if (pawn.mech || pawn.alive() || !ps.dead) return false;
  if (death_anim_playing(ps)) return false;
  if (ps.xp_gone >= 0 && frame_ < ps.xp_gone) return false;
  if (ps.tracker.running || ps.death_pending || ps.death_fx_pending || ps.detonate_pending) return false;
  return !is_corpse(board_, pawn);
}

void Simulation::remove(int32_t uid) {
  const Pawn* p = board_.find_pawn(uid);
  log(ResolveEventType::PawnRemoved, p ? p->pos : kInvalidPoint, uid);
  board_.remove_pawn(uid);
  pawns_.erase(uid);
  changed_ = true;
}

}  // namespace itb::detail
