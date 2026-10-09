#include "itb/core.hpp"

#include <cctype>

namespace itb {

std::string to_visual(Point p) {
  if (!p.valid()) return "--";
  std::string out;
  out += static_cast<char>('H' - p.y);
  out += static_cast<char>('0' + (kBoardSize - p.x));
  return out;
}

std::optional<Point> from_visual(std::string_view name) {
  if (name.size() != 2) return std::nullopt;
  const int col = std::toupper(static_cast<unsigned char>(name[0]));
  const int row = name[1] - '0';
  const Point p{kBoardSize - row, 'H' - col};
  if (!p.valid()) return std::nullopt;
  return p;
}

}  // namespace itb
