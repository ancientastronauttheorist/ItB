// Stage 9: the perfect-turn search (solver.hpp).
//
// Values. A node is a board during the player's turn. Its value is the best
// worst-case score the player can guarantee from there:
//   V(B) = max( E(B), max over sub-actions a of C(B, a) )
//   E(B) = min over the enemy phase's chance outcomes of score_turn(root, ..)
//   C(B, a) = min over the chance outcomes o of a of V(B·a·o)
// E(B) is "end the turn now", so every prefix of a plan is a plan. Nodes are
// searched depth-first with alpha-beta: a search returns an Interval [lo, hi]
// that holds V, exact when lo == hi. The global incumbent (the best value
// already guaranteed from the root) raises every alpha.
//
// Soundness. Intervals are only ever built from (a) values the engine
// computed, (b) the min/max rules above and (c) the tier upper bounds of
// `TierBounds` (argued there). A search that runs to the end without being
// cut by the budget therefore proves that no plan beats the incumbent.
#include "itb/solver.hpp"

#include <algorithm>
#include <chrono>
#include <climits>
#include <cstdio>
#include <functional>
#include <unordered_map>
#include <unordered_set>

#include "itb/board_hash.hpp"
#include "itb/core.hpp"
#include "itb/engine.hpp"
#include "itb/lua_host.hpp"
#include "itb/movement.hpp"

namespace itb {
namespace {

using Clock = std::chrono::steady_clock;

// The Lua stream (math.random, random_int) is reseeded before every engine
// run, so a run is a function of the board and the chance choices alone. The
// live stream is hidden; any fixed state is one sample of it.
constexpr uint32_t kLuaSeed = 1;
constexpr int kMaxDepth = 48;

Score filled(int32_t v) {
  Score s;
  s.v.fill(v);
  return s;
}
const Score kLow = filled(INT32_MIN);
const Score kHigh = filled(INT32_MAX);

struct Interval {
  Score lo = kLow;
  Score hi = kHigh;
  bool exact() const { return lo == hi; }
};

double seconds_since(Clock::time_point t) {
  return std::chrono::duration<double>(Clock::now() - t).count();
}

// ---- Chance nodes ---------------------------------------------------------------
//
// Every chance hook the engine calls (TurnContext / ActionOptions) goes through
// the driver, which numbers the calls of one run in order. A run is primed
// with forced choices for its first calls; later calls take their default
// (no Grid Defense resist, branch 0, the pawn's own seed, the first egg tile).
// Since a run is deterministic given its choices, re-running with the first i
// choices of a run plus another option for call i reaches every other outcome
// of the chance tree exactly once (enumerate_chance).

enum class Hook : uint8_t { Resist, Choose, Seed, Egg };

struct ChanceCall {
  Hook hook;
  int options = 1;  // branches of this call (1 = nothing to branch on)
  int chosen = 0;
  uint32_t seed = 0;     // Seed: the seed handed out
  bool matched = false;  // Seed: its death effect drew random numbers
};

class ChanceDriver {
 public:
  ChanceDriver(int grid_defense, int extra_seeds)
      : resist_(grid_defense > 0), seeds_(1 + std::max(0, extra_seeds)) {}

  void begin(const std::vector<int>& forced) {
    forced_ = &forced;
    calls_.clear();
  }
  const std::vector<ChanceCall>& calls() const { return calls_; }
  bool sampled() const { return sampled_; }

  // A death effect drew random numbers (ChanceKind::LuaRandom, amount = the
  // seed): the seed was a sample, so its call branches over the seed sample.
  void mark_random(const std::vector<ChanceRecord>& chances) {
    for (const ChanceRecord& c : chances) {
      if (c.kind != ChanceKind::LuaRandom) continue;
      for (ChanceCall& call : calls_) {
        if (call.hook == Hook::Seed && !call.matched && call.seed == static_cast<uint32_t>(c.amount)) {
          call.matched = true;
          call.options = seeds_;
          sampled_ = true;
          break;
        }
      }
    }
  }

  void bind(ActionOptions& o) {
    o.grid_resist = [this](Point, int) { return next(Hook::Resist, resist_ ? 2 : 1) == 1; };
    o.death_seed = [this](const Pawn& p) { return seed_for(p); };
    o.spider_egg = [this](Resolver&, const Pawn&, const std::vector<Point>& tiles) {
      return next(Hook::Egg, static_cast<int>(tiles.size()));
    };
  }
  void bind(TurnContext& tc) {
    tc.grid_resist = [this](Point, int) { return next(Hook::Resist, resist_ ? 2 : 1) == 1; };
    tc.choose = [this](const ChanceRecord& node) { return next(Hook::Choose, std::max(1, node.options)); };
    tc.death_seed = [this](const Pawn& p) { return seed_for(p); };
    tc.spider_egg = [this](Resolver&, const Pawn&, const std::vector<Point>& tiles) {
      return next(Hook::Egg, static_cast<int>(tiles.size()));
    };
  }

 private:
  int next(Hook h, int options) {
    const size_t i = calls_.size();
    int c = forced_ && i < forced_->size() ? (*forced_)[i] : 0;
    c = std::clamp(c, 0, std::max(0, options - 1));
    calls_.push_back(ChanceCall{h, std::max(1, options), c, 0, false});
    return c;
  }
  uint32_t seed_for(const Pawn& p) {
    const size_t i = calls_.size();
    const int k = forced_ && i < forced_->size() ? (*forced_)[i] : 0;
    // k = 0: the engine's default seed (uid + 1); others: fixed samples.
    const uint32_t seed = k == 0 ? static_cast<uint32_t>(p.uid + 1)
                                 : static_cast<uint32_t>(p.uid + 1) * 2654435761u + 40503u * static_cast<uint32_t>(k);
    calls_.push_back(ChanceCall{Hook::Seed, 1, k, seed, false});
    return seed;
  }

  bool resist_;
  int seeds_;
  const std::vector<int>* forced_ = nullptr;
  std::vector<ChanceCall> calls_;
  bool sampled_ = false;
};

enum class EnumEnd { Complete, Stopped, Truncated };

// Runs `run` once per leaf of the chance tree (the default outcome first).
// `run` returns false to stop. `extra` counts the runs after the first.
template <class Run>
EnumEnd enumerate_chance(ChanceDriver& d, int max_leaves, uint64_t& extra, Run&& run) {
  std::vector<std::vector<int>> todo(1);
  int leaves = 0;
  while (!todo.empty()) {
    const std::vector<int> prefix = std::move(todo.back());
    todo.pop_back();
    d.begin(prefix);
    if (leaves++ > 0) ++extra;
    if (!run()) return EnumEnd::Stopped;
    const std::vector<ChanceCall>& calls = d.calls();
    for (size_t i = prefix.size(); i < calls.size(); ++i) {
      for (int j = 0; j < calls[i].options; ++j) {
        if (j == calls[i].chosen) continue;
        std::vector<int> p;
        p.reserve(i + 1);
        for (size_t k = 0; k < i; ++k) p.push_back(calls[k].chosen);
        p.push_back(j);
        todo.push_back(std::move(p));
      }
    }
    if (leaves >= max_leaves && !todo.empty()) return EnumEnd::Truncated;
  }
  return EnumEnd::Complete;
}

// ---- Sub-actions -----------------------------------------------------------------

struct SubAction {
  enum Kind : uint8_t { Move, Weapon, Repair };
  int32_t uid = -1;
  Kind kind = Move;
  int8_t slot = -1;
  bool chance = false;  // more than one chance outcome
  Symbol skill = kNoSymbol;  // weapon or repair skill
  Point target = kInvalidPoint;
  Point target2 = kInvalidPoint;
};

ActionResult run_sub(Engine& e, Board& b, const SubAction& a, const ActionOptions& o) {
  switch (a.kind) {
    case SubAction::Move:
      return e.move(b, a.uid, a.target, o);
    case SubAction::Weapon:
      return e.fire_weapon(b, a.uid, a.slot, a.target,
                           a.target2.valid() ? std::optional<Point>(a.target2) : std::nullopt, o);
    case SubAction::Repair:
      return e.repair(b, a.uid, a.target, symbol_name(a.skill), o);
  }
  return {};
}

// Consecutive move + action of one unit become one PlayerAction.
std::vector<PlayerAction> to_player_actions(const std::vector<SubAction>& line) {
  std::vector<PlayerAction> out;
  for (const SubAction& a : line) {
    if (a.kind != SubAction::Move && !out.empty()) {
      PlayerAction& last = out.back();
      if (last.uid == a.uid && last.kind == PlayerAction::Kind::None && last.move.valid()) {
        last.kind = a.kind == SubAction::Weapon ? PlayerAction::Kind::Weapon : PlayerAction::Kind::Repair;
        last.weapon = std::string(symbol_name(a.skill));
        last.target = a.target;
        if (a.target2.valid()) last.target2 = a.target2;
        continue;
      }
    }
    PlayerAction p;
    p.uid = a.uid;
    if (a.kind == SubAction::Move) {
      p.move = a.target;
    } else {
      p.kind = a.kind == SubAction::Weapon ? PlayerAction::Kind::Weapon : PlayerAction::Kind::Repair;
      p.weapon = std::string(symbol_name(a.skill));
      p.target = a.target;
      if (a.target2.valid()) p.target2 = a.target2;
    }
    out.push_back(std::move(p));
  }
  return out;
}

// As score.cpp counts them.
int building_hp(const Board& b) {
  int total = 0;
  for (int i = 0; i < kTileCount; ++i) {
    const Tile& t = b.tile(Point::from_index(i));
    if (t.is_building()) total += std::max<int>(0, t.hp);
  }
  return total;
}

bool scored_enemy(const Pawn& p) { return p.team == Team::Enemy && !p.neutral && !p.mech; }

// ---- Tier upper bounds ------------------------------------------------------------
//
// ub(B) is a Score that no plan continuing from board B can beat: it is
// componentwise >= the score of every such plan, hence lexicographically >=.
// Per component of score_turn (score.cpp):
//   GridLost       = after.grid - root.grid. The engine raises grid power only
//                    through Lua Game:ModifyPowerGrid (Engine::apply_writes),
//                    which no shipped script calls with a gain except
//                    Support_KO_GridCharger's kill script. Without such a
//                    weapon on the board grid power never rises, so after.grid
//                    <= B.grid. With one, after.grid <= grid_power_max.
//   BuildingHpLost = building HP after - at the root. Building HP only rises
//                    in add_building (SpaceDamage iTerrain = TERRAIN_BUILDING),
//                    which no weapon, pawn or death script produces and the
//                    native environments never request (only mission_final's
//                    setup scripts do, which the engine does not run). So the
//                    total never rises: <= hp(B) - hp(root).
//   MechsLost      = sum over the root's mechs of alive_after - alive_before:
//                    <= the number of mechs dead at the root (revived corpses).
//   MechHpLost     = sum of hp_after - hp_before: a pawn's HP never exceeds
//                    its max HP (every heal clamps), and a mech's max HP only
//                    rises by the Soldier psion's +1, which reaches mechs only
//                    with Psion Leech. So <= sum of (max_hp [+1] - hp_before).
//   ObjectivesFailed = -(stars lost) <= 0.
//   VekKilled      <= enemies alive at the root (only those are counted).
//   VekHpRemoved   <= their total HP (hp_before - hp_after, hp_after >= 0).
//   ObjectiveProgress, Position: unbounded (INT32_MAX) unless the caller
//                    gives SolveOptions::tier_caps.
// tier_caps lowers any component further (the caller vouches for them).
class TierBounds {
 public:
  TierBounds(const Board& root, const std::optional<Score>& caps) {
    root_grid_ = root.grid_power;
    root_building_ = building_hp(root);
    for (const Pawn& p : root.pawns()) {
      for (Symbol w : p.weapons) {
        if (w != kNoSymbol && symbol_name(w).starts_with("Support_KO_GridCharger")) grid_monotone_ = false;
      }
    }
    caps_ = kHigh;
    caps_[ScoreKey::GridLost] = std::max(root.grid_power_max, root.grid_power) - root.grid_power;
    caps_[ScoreKey::BuildingHpLost] = 0;
    const int leech = root.has_passive(kPassivePsionLeech) ? 1 : 0;
    int dead_mechs = 0, mech_room = 0, enemies = 0, enemy_hp = 0;
    for (const Pawn& p : root.pawns()) {
      const int hp0 = p.alive() && !p.fallen && p.pos.valid() ? p.hp : 0;
      if (p.mech && p.team == Team::Player) {
        if (hp0 <= 0) ++dead_mechs;
        mech_room += std::max(0, p.max_hp + leech - hp0);
      } else if (scored_enemy(p) && hp0 > 0) {
        ++enemies;
        enemy_hp += hp0;
      }
    }
    caps_[ScoreKey::MechsLost] = dead_mechs;
    caps_[ScoreKey::MechHpLost] = mech_room;
    caps_[ScoreKey::ObjectivesFailed] = 0;
    caps_[ScoreKey::VekKilled] = enemies;
    caps_[ScoreKey::VekHpRemoved] = enemy_hp;
    if (caps) {
      for (size_t i = 0; i < caps_.v.size(); ++i) caps_.v[i] = std::min(caps_.v[i], caps->v[i]);
    }
  }

  Score global() const { return caps_; }

  Score of(const Board& b) const {
    Score s = caps_;
    if (grid_monotone_) {
      s[ScoreKey::GridLost] = std::min(s[ScoreKey::GridLost], b.grid_power - root_grid_);
    }
    s[ScoreKey::BuildingHpLost] = std::min(s[ScoreKey::BuildingHpLost], building_hp(b) - root_building_);
    return s;
  }

 private:
  int root_grid_ = 0;
  int root_building_ = 0;
  bool grid_monotone_ = true;
  Score caps_;
};

// ---- The search -------------------------------------------------------------------

struct Outcome {
  Board board;
  BoardHash hash;
};

struct Child {
  SubAction act;
  std::vector<Outcome> outcomes;  // the default outcome first
  Score order;                    // best case of ending the turn right after
};

struct TTEntry {
  Interval v;
  SubAction best;
  bool has_best = false;
};

class Searcher {
 public:
  Searcher(Engine& engine, const Board& root, const TurnContext& ctx, const SolveOptions& o)
      : e_(engine),
        root_(root),
        o_(o),
        bounds_(root, o.tier_caps),
        driver_(root.grid_defense, o.extra_death_seeds) {
    tc_ = ctx;
    tc_.events = nullptr;
    tc_.log = nullptr;
    driver_.bind(tc_);
    driver_.bind(aopts_);
    aopts_.check_legal = true;
    for (const auto& [uid, skill] : o.repair_skills) repair_[uid] = intern(skill);
    move_skill_ = intern("Move");
    default_repair_ = intern("Skill_Repair");
  }

  SolveResult run() {
    start_ = Clock::now();
    const BoardHash h = hash_board(root_, HashMode::Search);
    std::vector<SubAction> pv;
    const Interval r = search(root_, h, kLow, kHigh, true, &pv, 0);

    SolveResult out;
    out.stats = stats_;
    out.stats.time_s = seconds_since(start_);
    out.timed_out = aborted_;
    out.chance_exact = chance_exact_ && !driver_.sampled();
    if (!has_incumbent_) return out;
    out.best.actions = to_player_actions(best_line_);
    out.best.worst_case = incumbent_;
    out.best.contingent = std::any_of(best_line_.begin(), best_line_.end(),
                                      [](const SubAction& a) { return a.chance; });
    out.proven_optimal = !aborted_ && out.chance_exact;
    Score upper = std::max(r.hi, incumbent_);
    if (!aborted_ && r.hi > incumbent_) {
      warnings_.push_back("search completed with a root bound above the plan: " + r.hi.describe());
    }
    if (out.proven_optimal) upper = incumbent_;
    out.upper_bound = upper;
    int k = 0;
    while (k < kScoreKeys && upper.v[k] == incumbent_.v[k]) ++k;
    out.proven_components = upper == incumbent_ ? kScoreKeys : k;
    if (!out.chance_exact) out.warnings.push_back("chance not enumerated exactly (sampled death-effect seed or chance tree over the cap)");
    for (const std::string& w : warnings_) out.warnings.push_back(w);
    return out;
  }

 private:
  bool budget_exceeded() {
    if (aborted_) return true;
    if (o_.node_limit && stats_.nodes >= o_.node_limit) aborted_ = true;
    if (o_.time_limit_s > 0 && seconds_since(start_) >= o_.time_limit_s) aborted_ = true;
    return aborted_;
  }

  void note(const std::string& w) {
    if (std::find(warnings_.begin(), warnings_.end(), w) == warnings_.end()) warnings_.push_back(w);
  }

  void improve(const Score& v, const std::vector<SubAction>& tail) {
    if (has_incumbent_ && v <= incumbent_) return;
    if (!has_incumbent_) stats_.first_plan_s = seconds_since(start_);
    has_incumbent_ = true;
    incumbent_ = v;
    best_line_ = path_;
    best_line_.insert(best_line_.end(), tail.begin(), tail.end());
    stats_.best_plan_s = seconds_since(start_);
  }

  Score alpha_of(const Score& alpha) const {
    return has_incumbent_ ? std::max(alpha, incumbent_) : alpha;
  }

  // E(B): the worst case of ending the turn on B.
  Interval leaf(const Board& b, const Score& alpha) {
    BoardHash key{};
    if (o_.use_tt) {
      key = hash_board(b, HashMode::EndTurn);
      if (auto it = leaf_memo_.find(key); it != leaf_memo_.end()) {
        if (it->second.exact() || it->second.hi <= alpha) {
          ++stats_.leaf_hits;
          return it->second;
        }
      }
    }
    Score worst = kHigh;
    bool cut = false;
    const EnumEnd end = enumerate_chance(driver_, o_.max_chance_leaves, stats_.chance_branches, [&] {
      Board after = b;
      const Clock::time_point t0 = Clock::now();
      e_.lua().seed(kLuaSeed);
      const PhaseResult pr = e_.end_turn(after, tc_);
      stats_.enemy_phase_s += seconds_since(t0);
      ++stats_.enemy_phases;
      driver_.mark_random(pr.chances);
      if (!pr.exact) note("enemy phase: the recorded data does not pin every step down (EnvInexact)");
      if (!pr.emerged_unknown.empty()) note("enemy phase: spawns of unknown type emerge without a pawn");
      worst = std::min(worst, score_turn(root_, after, &tc_, &pr));
      if (worst <= alpha) {
        cut = true;
        return false;
      }
      return true;
    });
    if (end == EnumEnd::Truncated) chance_exact_ = false;
    if (cut) ++stats_.chance_cutoffs;
    const Interval r = cut ? Interval{kLow, worst} : Interval{worst, worst};
    if (o_.use_tt && leaf_memo_.size() < o_.tt_max_entries) leaf_memo_[key] = r;
    return r;
  }

  bool passive(Symbol w) {
    auto it = passive_.find(w);
    if (it != passive_.end()) return it->second;
    const std::string name(symbol_name(w));
    const std::optional<std::string> p = e_.lua().lua_string(name, "Passive");
    const bool is = (p && !p->empty()) || !e_.lua().lua_string(name, "Name");
    passive_[w] = is;
    return is;
  }

  bool two_click(Symbol w) {
    auto it = two_click_.find(w);
    if (it != two_click_.end()) return it->second;
    const bool is = e_.lua().is_two_click(symbol_name(w));
    two_click_[w] = is;
    return is;
  }

  static void valid_unique(std::vector<Point>& pts) {
    std::vector<Point> out;
    for (Point p : pts) {
      if (p.valid() && std::find(out.begin(), out.end(), p) == out.end()) out.push_back(p);
    }
    pts = std::move(out);
  }

  // Runs one sub-action from b through every chance outcome. False if the
  // engine refuses it or nothing happens.
  bool execute(const Board& b, SubAction& act, std::vector<Outcome>& outs) {
    outs.clear();
    bool refused = false;
    const EnumEnd end = enumerate_chance(driver_, o_.max_chance_leaves, stats_.chance_branches, [&] {
      Board next = b;
      const Clock::time_point t0 = Clock::now();
      e_.lua().seed(kLuaSeed);
      const ActionResult r = run_sub(e_, next, act, aopts_);
      stats_.sub_action_s += seconds_since(t0);
      ++stats_.sub_actions;
      if (!r.ok()) {
        refused = true;
        return false;
      }
      driver_.mark_random(r.resolve.chances);
      const BoardHash h = hash_board(next, HashMode::Search);
      for (const Outcome& o : outs) {
        if (o.hash == h) return true;
      }
      outs.push_back(Outcome{std::move(next), h});
      return true;
    });
    if (refused) return false;
    if (end == EnumEnd::Truncated) chance_exact_ = false;
    act.chance = outs.size() > 1;
    return true;
  }

  void generate(const Board& b, const BoardHash& h, std::vector<Child>& out) {
    out.clear();
    std::unordered_set<BoardHash, BoardHashOf> seen;
    seen.insert(h);
    auto add = [&](SubAction act) {
      Child c;
      if (!execute(b, act, c.outcomes)) return;
      if (c.outcomes.size() == 1 && !seen.insert(c.outcomes[0].hash).second) {
        ++stats_.duplicate_children;
        return;
      }
      c.act = act;
      out.push_back(std::move(c));
    };
    LuaHost& lua = e_.lua();
    for (const Pawn& p : b.pawns()) {
      if (!p.controlled() || !p.alive() || !p.pos.valid()) continue;
      const int32_t uid = p.uid;
      const Point at = p.pos;
      if (p.active && p.movement.powered && !p.frozen) {
        for (int slot = 0; slot < kMaxWeapons; ++slot) {
          const Symbol w = p.weapons[static_cast<size_t>(slot)];
          if (w == kNoSymbol || passive(w)) continue;
          const std::string name(symbol_name(w));
          std::vector<Point> targets = lua.target_area(b, p, name, at);
          valid_unique(targets);
          const bool two = two_click(w);
          for (Point t : targets) {
            SubAction a;
            a.uid = uid;
            a.kind = SubAction::Weapon;
            a.slot = static_cast<int8_t>(slot);
            a.skill = w;
            a.target = t;
            if (two && !lua.two_click_exception(b, p, name, at, t)) {
              const Point first = lua.translate_first_click(b, p, name, at, t);
              std::vector<Point> second = lua.second_target_area(b, p, name, at, first);
              valid_unique(second);
              for (Point t2 : second) {
                a.target2 = t2;
                add(a);
              }
            } else {
              add(a);
            }
          }
        }
        if (p.mech) {
          auto it = repair_.find(uid);
          const Symbol skill = it != repair_.end() ? it->second : default_repair_;
          std::vector<Point> targets = lua.target_area(b, p, symbol_name(skill), at);
          valid_unique(targets);
          if (targets.empty()) targets.push_back(at);
          for (Point t : targets) {
            SubAction a;
            a.uid = uid;
            a.kind = SubAction::Repair;
            a.skill = skill;
            a.target = t;
            add(a);
          }
        }
      }
      if (can_move(p)) {
        std::vector<Point> dests = lua.target_area(b, p, "Move", at);
        valid_unique(dests);
        for (Point d : dests) {
          if (d == at) continue;
          SubAction a;
          a.uid = uid;
          a.kind = SubAction::Move;
          a.skill = move_skill_;
          a.target = d;
          add(a);
        }
      }
    }
  }

  // The best line from b along the table's best sub-actions (default
  // outcomes), for a table hit that improves the incumbent.
  std::vector<SubAction> table_line(const Board& start) {
    std::vector<SubAction> line;
    Board cur = start;
    std::vector<Outcome> outs;
    for (int guard = 0; guard < kMaxDepth; ++guard) {
      auto it = tt_.find(hash_board(cur, HashMode::Search));
      if (it == tt_.end() || !it->second.has_best) break;
      SubAction act = it->second.best;
      if (!execute(cur, act, outs) || outs.empty()) break;
      line.push_back(act);
      cur = std::move(outs[0].board);
    }
    return line;
  }

  // V over the chance outcomes of one child: the minimum.
  Interval chance_node(Child& c, Score alpha, const Score& beta, std::vector<SubAction>* pv, int depth) {
    Score lo = kHigh, hi = kHigh;
    for (size_t k = 0; k < c.outcomes.size(); ++k) {
      std::vector<SubAction> sub;
      const Interval r = search(c.outcomes[k].board, c.outcomes[k].hash, alpha, std::min(beta, hi), false,
                                k == 0 ? &sub : nullptr, depth + 1);
      if (k == 0 && pv) *pv = std::move(sub);
      lo = std::min(lo, r.lo);
      hi = std::min(hi, r.hi);
      if (hi <= alpha_of(alpha) && k + 1 < c.outcomes.size()) {
        ++stats_.chance_cutoffs;
        return Interval{kLow, hi};  // the outcomes left can only lower it
      }
      if (aborted_ && k + 1 < c.outcomes.size()) return Interval{kLow, hi};
    }
    return Interval{lo, hi};
  }

  Interval search(const Board& b, const BoardHash& h, Score alpha, const Score& beta, bool chance_free,
                  std::vector<SubAction>* pv, int depth) {
    if (pv) pv->clear();
    if (budget_exceeded()) return Interval{kLow, bounds_.of(b)};
    alpha = alpha_of(alpha);
    if (o_.use_tt) {
      auto it = tt_.find(h);
      if (it != tt_.end()) {
        const Interval& v = it->second.v;
        if (v.exact() || v.hi <= alpha || v.lo >= beta) {
          ++stats_.tt_hits;
          if (chance_free && v.lo > kLow && (!has_incumbent_ || v.lo > incumbent_)) {
            const std::vector<SubAction> line = table_line(b);
            improve(v.lo, line);
            if (pv) *pv = line;
          } else if (pv && v.exact()) {
            *pv = table_line(b);
          }
          return v;
        }
      }
    }
    ++stats_.nodes;

    // End the turn here.
    const Interval end = leaf(b, alpha);
    Score lo = end.lo, hi = end.hi;
    std::vector<SubAction> best_pv;
    SubAction best_act;
    bool has_best = false;
    if (chance_free && end.exact()) improve(end.lo, {});
    alpha = std::max(alpha_of(alpha), lo);

    const Score ub = bounds_.of(b);
    auto finish = [&](Interval r) {
      if (o_.use_tt && !aborted_ && tt_.size() < o_.tt_max_entries) {
        tt_[h] = TTEntry{r, best_act, has_best};
      }
      if (chance_free && r.lo > kLow) improve(r.lo, best_pv);
      if (pv) *pv = best_pv;
      return r;
    };
    if (lo >= beta) return finish(Interval{lo, std::max(hi, ub)});
    if (o_.use_bounds && ub <= alpha) {
      ++stats_.bound_prunes;
      return finish(Interval{lo, std::max(hi, ub)});
    }
    if (depth >= kMaxDepth) {
      note("search depth limit reached");
      chance_exact_ = false;
      return finish(Interval{lo, std::max(hi, ub)});
    }

    std::vector<Child> children;
    generate(b, h, children);
    if (o_.order_children) {
      for (Child& c : children) {
        if (budget_exceeded()) break;
        Score key = kHigh;
        for (const Outcome& oc : c.outcomes) key = std::min(key, leaf(oc.board, alpha_of(alpha)).hi);
        c.order = key;
      }
      std::stable_sort(children.begin(), children.end(),
                       [](const Child& x, const Child& y) { return x.order > y.order; });
    }

    for (size_t i = 0; i < children.size(); ++i) {
      Child& c = children[i];
      if (budget_exceeded()) {
        hi = std::max(hi, ub);
        break;
      }
      alpha = std::max(alpha_of(alpha), lo);
      if (o_.use_bounds) {
        Score cub = kLow;
        for (const Outcome& oc : c.outcomes) cub = std::max(cub, bounds_.of(oc.board));
        if (cub <= alpha) {
          ++stats_.bound_prunes;
          hi = std::max(hi, cub);
          continue;
        }
      }
      std::vector<SubAction> sub;
      path_.push_back(c.act);
      Interval r;
      if (c.outcomes.size() == 1) {
        r = search(c.outcomes[0].board, c.outcomes[0].hash, alpha, beta, chance_free, &sub, depth + 1);
      } else {
        r = chance_node(c, alpha, beta, &sub, depth);
        if (chance_free && r.lo > kLow && (!has_incumbent_ || r.lo > incumbent_)) improve(r.lo, sub);
      }
      path_.pop_back();
      hi = std::max(hi, r.hi);
      if (r.lo > lo) {
        lo = r.lo;
        best_act = c.act;
        has_best = true;
        best_pv.clear();
        best_pv.push_back(c.act);
        best_pv.insert(best_pv.end(), sub.begin(), sub.end());
      }
      if (lo >= beta) {
        hi = std::max(hi, ub);  // the children left are not searched
        break;
      }
    }
    return finish(Interval{lo, hi});
  }

  Engine& e_;
  const Board& root_;
  const SolveOptions& o_;
  TierBounds bounds_;
  ChanceDriver driver_;
  TurnContext tc_;
  ActionOptions aopts_;
  std::unordered_map<int32_t, Symbol> repair_;
  std::unordered_map<Symbol, bool> passive_, two_click_;
  Symbol move_skill_ = kNoSymbol;
  Symbol default_repair_ = kNoSymbol;

  std::unordered_map<BoardHash, TTEntry, BoardHashOf> tt_;
  std::unordered_map<BoardHash, Interval, BoardHashOf> leaf_memo_;

  Clock::time_point start_;
  bool aborted_ = false;
  bool chance_exact_ = true;
  bool has_incumbent_ = false;
  Score incumbent_ = kLow;
  std::vector<SubAction> path_;
  std::vector<SubAction> best_line_;
  std::vector<std::string> warnings_;
  SolveStats stats_;
};

}  // namespace

SolveResult solve_turn(Engine& engine, const Board& board, const TurnContext& ctx, const SolveOptions& options) {
  Searcher s(engine, board, ctx, options);
  SolveResult r = s.run();
  // The returned plan, re-run open-loop: the same value unless it branches
  // on a chance node (then the plan is a policy, see Plan::contingent).
  if (!r.best.contingent && !r.best.actions.empty()) {
    const std::optional<Score> again = evaluate_plan(engine, board, ctx, r.best.actions, options);
    if (!again || *again != r.best.worst_case) {
      r.warnings.push_back("re-running the plan gives " + (again ? again->describe() : std::string("a refusal")));
    }
  }
  return r;
}

std::optional<Score> evaluate_plan(Engine& engine, const Board& board, const TurnContext& ctx,
                                   const std::vector<PlayerAction>& plan, const SolveOptions& options,
                                   std::string* refused) {
  ChanceDriver d(board.grid_defense, options.extra_death_seeds);
  TurnContext tc = ctx;
  tc.events = nullptr;
  tc.log = nullptr;
  d.bind(tc);
  ActionOptions ao;
  d.bind(ao);
  Score worst = kHigh;
  bool bad = false;
  uint64_t extra = 0;
  auto ok = [](const ActionResult& r) { return r.ok() || r.status == ActionStatus::NoEffect; };
  enumerate_chance(d, options.max_chance_leaves, extra, [&] {
    Board b = board;
    for (size_t i = 0; i < plan.size(); ++i) {
      const PlayerAction& a = plan[i];
      const Pawn* p = b.find_pawn(a.uid);
      if (a.move.valid() && p && a.move != p->pos) {
        engine.lua().seed(kLuaSeed);
        const ActionResult r = engine.move(b, a.uid, a.move, ao);
        if (!ok(r)) {
          if (refused) *refused = "action " + std::to_string(i) + " move: " + to_string(r.status);
          bad = true;
          return false;
        }
        d.mark_random(r.resolve.chances);
      }
      if (a.kind == PlayerAction::Kind::None) continue;
      engine.lua().seed(kLuaSeed);
      const ActionResult r =
          a.kind == PlayerAction::Kind::Weapon
              ? engine.fire_weapon(b, a.uid, a.weapon, a.target, a.target2, ao)
              : engine.repair(b, a.uid, a.target, a.weapon.empty() ? "Skill_Repair" : a.weapon, ao);
      if (!ok(r)) {
        if (refused) *refused = "action " + std::to_string(i) + " " + a.weapon + ": " + to_string(r.status);
        bad = true;
        return false;
      }
      d.mark_random(r.resolve.chances);
    }
    engine.lua().seed(kLuaSeed);
    const PhaseResult pr = engine.end_turn(b, tc);
    d.mark_random(pr.chances);
    worst = std::min(worst, score_turn(board, b, &tc, &pr));
    return true;
  });
  if (bad) return std::nullopt;
  return worst;
}

std::string describe_action(const Board& board, const PlayerAction& a) {
  const Pawn* p = board.find_pawn(a.uid);
  std::string s = p ? std::string(symbol_name(p->type)) : std::string("unit");
  s += "#" + std::to_string(a.uid);
  if (a.move.valid()) s += " move " + to_visual(a.move);
  if (a.kind == PlayerAction::Kind::Weapon) {
    s += (a.move.valid() ? ", " : " ") + std::string("fire ") + a.weapon + " at " + to_visual(a.target);
    if (a.target2) s += " then " + to_visual(*a.target2);
  } else if (a.kind == PlayerAction::Kind::Repair) {
    s += (a.move.valid() ? ", " : " ") + std::string("repair") +
         (a.weapon.empty() || a.weapon == "Skill_Repair" ? std::string() : " (" + a.weapon + ")");
    if (a.target.valid() && p && a.target != (a.move.valid() ? a.move : p->pos)) s += " at " + to_visual(a.target);
  } else if (!a.move.valid()) {
    s += " (no action)";
  }
  return s;
}

}  // namespace itb
