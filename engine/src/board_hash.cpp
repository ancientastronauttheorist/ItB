#include "itb/board_hash.hpp"

#include <array>

namespace itb {
namespace {

// Every Tile and Pawn field is hashed below. If one of these fails, a field
// was added: hash it, then update the size.
static_assert(sizeof(Tile) == 28, "Tile changed: update hash_board");
static_assert(sizeof(Pawn) == 124, "Pawn changed: update hash_board");
static_assert(sizeof(MoveState) == 16, "MoveState changed: update hash_board");
static_assert(sizeof(QueuedShot) == 20, "QueuedShot changed: update hash_board");

inline uint64_t mix64(uint64_t x) {
  // splitmix64 finalizer
  x ^= x >> 30;
  x *= 0xBF58476D1CE4E5B9ull;
  x ^= x >> 27;
  x *= 0x94D049BB133111EBull;
  x ^= x >> 31;
  return x;
}

// Two independent 64-bit lanes over a stream of 64-bit words.
struct Hasher {
  uint64_t a = 0x243F6A8885A308D3ull;
  uint64_t b = 0x13198A2E03707344ull;
  uint64_t n = 0;

  void word(uint64_t w) {
    ++n;
    a = mix64(a ^ (w + 0x9E3779B97F4A7C15ull * n));
    b = mix64(b + (w ^ 0xC2B2AE3D27D4EB4Full) * (2 * n + 1));
  }
  // Packs small values 8 bits at a time.
  struct Packer {
    Hasher& h;
    uint64_t acc = 0;
    int used = 0;
    void put(uint64_t v, int bits) {
      if (used + bits > 64) flush();
      acc |= (v & ((bits == 64) ? ~0ull : ((1ull << bits) - 1))) << used;
      used += bits;
    }
    void flush() {
      if (used) h.word(acc);
      acc = 0;
      used = 0;
    }
    ~Packer() { flush(); }
  };
  BoardHash done() const { return BoardHash{mix64(a ^ n), mix64(b ^ (n << 1))}; }
};

inline uint64_t u8(int v) { return static_cast<uint8_t>(v); }
inline uint64_t pt(Point p) { return (static_cast<uint64_t>(static_cast<uint32_t>(p.x)) << 32) | static_cast<uint32_t>(p.y); }

void hash_tile(Hasher& h, const Tile& t) {
  Hasher::Packer k{h};
  k.put(u8(static_cast<int>(t.terrain)), 8);
  k.put(u8(t.hp), 8);
  k.put(u8(t.max_hp), 8);
  k.put(u8(static_cast<int>(t.fire)), 8);
  k.put(u8(static_cast<int>(t.pod)), 8);
  k.put(u8(t.conveyor), 8);
  k.put(t.walls, 8);
  k.put(t.populated, 1);
  k.put(t.shield, 1);
  k.put(t.frozen, 1);
  k.put(t.lava, 1);
  k.put(t.smoke, 1);
  k.put(t.acid, 1);
  k.put(t.cracked, 1);
  k.put(t.pending_hole, 1);
  k.put(t.vines, 1);
  k.put(t.spikes, 1);
  k.put(t.building_on_water, 1);
  k.put(t.teleporter, 1);
  k.put(t.item, 16);
  k.put(t.unique_building, 16);
  k.put(t.custom_tile, 16);
  k.put(t.special_tag, 16);
}

void hash_pawn(Hasher& h, const Pawn& p, uint32_t tile_rank, HashMode mode) {
  const bool end_turn = mode == HashMode::EndTurn;
  const bool player = p.team == Team::Player;
  h.word(static_cast<uint32_t>(p.uid));
  h.word(pt(p.pos));
  h.word(pt(p.web_tile));
  h.word(pt(p.queued.origin));
  h.word(pt(p.queued.target));
  h.word(pt(p.movement.prev_pos));
  Hasher::Packer k{h};
  k.put(p.type, 16);
  for (Symbol w : p.weapons) k.put(w, 16);
  for (int8_t u : p.uses) k.put(u8(u), 8);
  k.put(p.pilot_abilities, 32);
  k.put(static_cast<uint32_t>(p.web_source), 32);
  k.put(tile_rank, 16);
  k.put(u8(p.hp), 8);
  k.put(u8(p.max_hp), 8);
  k.put(u8(p.move), 8);
  k.put(u8(static_cast<int>(p.team)), 8);
  k.put(u8(static_cast<int>(p.faction)), 8);
  k.put(u8(static_cast<int>(p.leader)), 8);
  k.put(u8(p.queued.weapon), 8);
  const MoveState& m = p.movement;
  k.put(u8(end_turn && player ? 0 : m.bonus_shift), 8);
  k.put(u8(end_turn && player ? 0 : m.kickoff_bonus), 8);
  k.put(u8(m.pilot_bonus), 8);
  k.put(u8(m.turn_count), 8);
  k.put(m.move_upgrade, 1);
  k.put(m.reset_bonus, 1);
  k.put(m.powered, 1);
  k.put(mode == HashMode::Exact ? m.undo_ready : false, 1);
  k.put(p.mech, 1);
  k.put(p.massive, 1);
  k.put(p.flying, 1);
  k.put(p.pushable, 1);
  k.put(p.armor, 1);
  k.put(p.ignore_smoke, 1);
  k.put(p.ignore_fire, 1);
  k.put(p.minor, 1);
  k.put(p.corpse, 1);
  k.put(p.burrows, 1);
  k.put(p.jumper, 1);
  k.put(p.teleporter, 1);
  k.put(p.explodes, 1);
  k.put(p.burns, 1);
  k.put(p.ignore_flip, 1);
  k.put(p.neutral, 1);
  k.put(p.non_grid, 1);
  k.put(p.mission_critical, 1);
  k.put(end_turn && player ? false : p.active, 1);
  k.put(p.moved, 1);
  k.put(p.fire, 1);
  k.put(p.frozen, 1);
  k.put(p.acid, 1);
  k.put(p.shield, 1);
  k.put(p.boosted, 1);
  k.put(p.webbed, 1);
  k.put(p.infected, 1);
  k.put(p.injured, 1);
  k.put(p.dying, 1);
  k.put(p.health_bonus, 1);
  k.put(p.fallen, 1);
}

}  // namespace

BoardHash hash_board(const Board& b, HashMode mode) {
  Hasher h;
  for (int i = 0; i < kTileCount; ++i) hash_tile(h, b.tile(Point::from_index(i)));
  {
    Hasher::Packer k{h};
    k.put(static_cast<uint32_t>(b.grid_power), 32);
    k.put(static_cast<uint32_t>(b.grid_power_max), 32);
    k.put(static_cast<uint32_t>(b.grid_defense), 32);
    k.put(static_cast<uint32_t>(b.turn), 32);
    k.put(static_cast<uint32_t>(b.total_turns), 32);
    k.put(b.passives, 32);
    // next_uid only labels pawns created later; kept so that equal hashes
    // mean equal futures, uids included.
    k.put(static_cast<uint32_t>(b.next_uid), 32);
    k.put(b.player_phase, 1);
    k.put(u8(static_cast<int>(b.psion)), 8);
    k.put(b.spawn_points.size(), 16);
    k.put(b.teleporters.size(), 16);
    k.put(b.teleporter_occupants.size(), 16);
  }
  for (Point p : b.spawn_points) h.word(pt(p));
  for (Point p : b.teleporters) h.word(pt(p));
  for (int32_t u : b.teleporter_occupants) h.word(static_cast<uint32_t>(u));

  // Arrival stamps as ranks among the pawns sharing a tile (stable on list
  // order, as Board::pawns_at sorts them).
  const std::vector<Pawn>& pawns = b.pawns();
  h.word(pawns.size());
  for (size_t i = 0; i < pawns.size(); ++i) {
    const Pawn& p = pawns[i];
    uint32_t rank = 0;
    for (size_t j = 0; j < pawns.size(); ++j) {
      if (j == i || !(pawns[j].pos == p.pos)) continue;
      const Pawn& q = pawns[j];
      if (q.arrival < p.arrival || (q.arrival == p.arrival && j < i)) ++rank;
    }
    hash_pawn(h, p, rank, mode);
  }
  return h.done();
}

}  // namespace itb
