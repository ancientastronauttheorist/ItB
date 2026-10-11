// Helpers shared by the tile-rules sources.
#pragma once

#include <string_view>

#include "itb/symbols.hpp"
#include "itb/tile_rules.hpp"

namespace itb::detail {

inline void emit(RulesContext& ctx, RulesEventType type, Point p, int32_t uid = -1,
                 int amount = 0, Symbol symbol = kNoSymbol) {
  if (ctx.events) ctx.events->push_back(RulesEvent{type, p, uid, amount, symbol});
}

inline bool type_is(const Pawn& pawn, std::string_view name) {
  return symbol_name(pawn.type) == name;
}

inline bool type_contains(const Pawn& pawn, std::string_view part) {
  return symbol_name(pawn.type).find(part) != std::string_view::npos;
}

// Lava as BoardSpace::IsTerrain(LAVA) sees it: water with the lava flag. Most
// rules read the raw flag instead (Tile::lava), which also survives on ice.
inline bool is_lava(const Tile& t) { return t.terrain == Terrain::Water && t.lava; }

// BoardSpace::ClearGrapple(1) on p (@0091b770): releases every web the tile
// emits (each held neighbour lets go of one web, SetGrappled(4)).
void release_webs(Board& board, Point p);

// The tile-state half of settle_tile_frame's early return: with no pawn on
// the tile (fallen ones included), a tile in this state is left exactly as
// it is.
bool inert_tile_state(const Tile& t);
// settle_tile_frame(board, p) would change nothing at all.
bool settle_tile_noop(const Board& board, Point p);
// The tile-state half of settle_tile_noop for an occupied tile: with no
// occupant (not fallen) that is a mech or on fire, a tile in this state is
// left exactly as it is.
bool quiet_occupied_tile_state(const Tile& t);

}  // namespace itb::detail
