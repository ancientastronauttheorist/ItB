// Interned identifiers for the game's string ids (pawn types, weapon names,
// item names, ...). Keeps Board/Pawn trivially copyable for search.
#pragma once

#include <cstdint>
#include <string_view>

namespace itb {

// 0 is reserved for "none". Interning is process-wide and append-only; it is
// not synchronized, so intern everything before searching on multiple threads.
using Symbol = uint16_t;
inline constexpr Symbol kNoSymbol = 0;

Symbol intern(std::string_view name);
// Returns kNoSymbol when the name has never been interned.
Symbol find_symbol(std::string_view name);
std::string_view symbol_name(Symbol s);

}  // namespace itb
