#include "itb/format.hpp"

#include <sstream>

namespace itb {
namespace {

char terrain_glyph(const Tile& t) {
  switch (t.terrain) {
    case Terrain::Road: return '.';
    case Terrain::Building: return 'B';
    case Terrain::Rubble: return ',';
    case Terrain::Water: return t.lava ? 'L' : '~';
    case Terrain::Mountain: return 'M';
    case Terrain::Ice: return '_';
    case Terrain::Forest: return 'f';
    case Terrain::Sand: return 's';
    case Terrain::Hole: return 'O';
    default: return '?';
  }
}

char pawn_label(size_t index) {
  constexpr const char* kLabels = "0123456789abcdefghijklmnopqrstuvwxyz";
  return index < 36 ? kLabels[index] : '#';
}

const char* team_name(Team t) {
  switch (t) {
    case Team::Player: return "player";
    case Team::Enemy: return "enemy";
    case Team::None: return "none";
    default: return "other";
  }
}

}  // namespace

std::string terrain_name(Terrain t) {
  switch (t) {
    case Terrain::Road: return "road";
    case Terrain::Building: return "building";
    case Terrain::Rubble: return "rubble";
    case Terrain::Water: return "water";
    case Terrain::Mountain: return "mountain";
    case Terrain::Ice: return "ice";
    case Terrain::Forest: return "forest";
    case Terrain::Sand: return "sand";
    case Terrain::Hole: return "chasm";
    case Terrain::Fire: return "fire";
    case Terrain::Acid: return "acid";
    case Terrain::Lava: return "lava";
  }
  return "unknown";
}

std::string describe_pawn(const Pawn& p) {
  std::ostringstream out;
  out << symbol_name(p.type) << " #" << p.uid << " @" << to_visual(p.pos) << " hp " << int(p.hp)
      << "/" << int(p.max_hp) << " " << team_name(p.team);
  if (p.mech) out << " mech";
  if (p.flying) out << " flying";
  if (p.massive) out << " massive";
  if (p.armor) out << " armor";
  if (!p.pushable) out << " stable";
  if (p.fire) out << " FIRE";
  if (p.frozen) out << " FROZEN";
  if (p.acid) out << " ACID";
  if (p.shield) out << " SHIELD";
  if (p.webbed) out << " WEB";
  if (p.boosted) out << " BOOST";
  if (p.queued.active()) {
    out << " -> " << symbol_name(p.weapons[p.queued.weapon]) << " at " << to_visual(p.queued.target);
  }
  return out.str();
}

std::string render_board(const Board& b) {
  std::ostringstream out;
  out << "     A  B  C  D  E  F  G  H\n";
  for (int row = kBoardSize; row >= 1; --row) {
    out << "  " << row << " ";
    for (int col = 0; col < kBoardSize; ++col) {
      const Point p{kBoardSize - row, kBoardSize - 1 - col};
      const Tile& t = b.tile(p);
      char mark = ' ';
      for (size_t i = 0; i < b.pawns().size(); ++i) {
        if (b.pawns()[i].pos == p) mark = pawn_label(i);
      }
      char status = ' ';
      if (t.on_fire()) status = '^';
      else if (t.smoke) status = '%';
      else if (t.acid) status = 'a';
      out << terrain_glyph(t) << mark << status;
    }
    out << "\n";
  }
  out << "grid " << b.grid_power << "/" << b.grid_power_max << "  turn " << b.turn << "/"
      << b.total_turns << "\n";
  for (size_t i = 0; i < b.pawns().size(); ++i) {
    out << "  [" << pawn_label(i) << "] " << describe_pawn(b.pawns()[i]) << "\n";
  }
  return out.str();
}

}  // namespace itb
