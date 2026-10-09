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

// Releases the webs held by pawns on p (ClearGrapple on the emitting tile).
void release_webs(Board& board, Point p);

}  // namespace itb::detail
