// Human-readable board rendering (A1-H8 notation, as used in project
// communication).
#pragma once

#include <string>

#include "itb/board.hpp"

namespace itb {

std::string terrain_name(Terrain t);
// Grid with rows 8..1 and columns A..H, then the pawn list in board order.
std::string render_board(const Board& board);
std::string describe_pawn(const Pawn& pawn);

}  // namespace itb
