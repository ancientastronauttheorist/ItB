"""Grid coordinate mapping for Into the Breach's isometric board.

The game displays an 8x8 grid in isometric (diamond) projection.
Rows are numbered 1-8 (bottom to upper-left).
Columns are lettered A-H (bottom to upper-right).

Tile (1, A) is at the bottom tip of the diamond.
Tile (8, H) is at the top tip.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class GridConfig:
    """Isometric grid configuration for pixel <-> tile coordinate conversion."""

    # Screen pixel position of tile (1, 1) center (i.e., tile 1,A)
    origin_x: float = 690.0
    origin_y: float = 660.0

    # Pixel step per row increment (goes upper-left)
    row_dx: float = -50.0
    row_dy: float = -27.5

    # Pixel step per column increment (goes upper-right)
    col_dx: float = 50.0
    col_dy: float = -27.5

    # Tile diamond dimensions
    tile_half_width: float = 50.0
    tile_half_height: float = 27.5

    # Grid size
    rows: int = 8
    cols: int = 8

    def tile_to_pixel(self, row: int, col: int) -> tuple[float, float]:
        """Convert grid coordinates (row 1-8, col 1-8) to screen pixel center.

        Args:
            row: Row number, 1 (bottom) to 8 (top-left).
            col: Column number, 1/A (bottom) to 8/H (top-right).

        Returns:
            (x, y) pixel coordinates of the tile center.
        """
        x = self.origin_x + (col - 1) * self.col_dx + (row - 1) * self.row_dx
        y = self.origin_y + (col - 1) * self.col_dy + (row - 1) * self.row_dy
        return (x, y)

    def pixel_to_tile(self, px: float, py: float) -> tuple[int, int] | None:
        """Convert screen pixel to grid coordinates.

        Uses the inverse of the isometric transformation.

        Returns:
            (row, col) if the pixel is within the grid, else None.
        """
        # Translate relative to origin
        dx = px - self.origin_x
        dy = py - self.origin_y

        # Inverse of the 2x2 matrix [[col_dx, row_dx], [col_dy, row_dy]]
        # [dx] = [col_dx  row_dx] [col-1]
        # [dy]   [col_dy  row_dy] [row-1]
        det = self.col_dx * self.row_dy - self.row_dx * self.col_dy
        if abs(det) < 1e-6:
            return None

        col_f = (dx * self.row_dy - dy * self.row_dx) / det + 1
        row_f = (dy * self.col_dx - dx * self.col_dy) / det + 1

        row = round(row_f)
        col = round(col_f)

        if 1 <= row <= self.rows and 1 <= col <= self.cols:
            return (row, col)
        return None

    @staticmethod
    def col_to_letter(col: int) -> str:
        """Convert column number (1-8) to letter (A-H)."""
        return chr(ord('A') + col - 1)

    @staticmethod
    def letter_to_col(letter: str) -> int:
        """Convert column letter (A-H) to number (1-8)."""
        return ord(letter.upper()) - ord('A') + 1

    def all_tile_centers(self) -> dict[tuple[int, int], tuple[float, float]]:
        """Return pixel centers for all 64 tiles."""
        centers = {}
        for row in range(1, self.rows + 1):
            for col in range(1, self.cols + 1):
                centers[(row, col)] = self.tile_to_pixel(row, col)
        return centers


# Default configuration based on manual calibration
# Window size 1280x748, windowed mode, Max Board Scale 5x
DEFAULT_GRID = GridConfig()


def print_grid_map():
    """Print all tile centers for verification."""
    grid = DEFAULT_GRID
    print(f"Grid origin (1,A): ({grid.origin_x}, {grid.origin_y})")
    print(f"Tile size: {grid.tile_half_width*2} x {grid.tile_half_height*2}")
    print()
    for row in range(grid.rows, 0, -1):
        for col in range(1, grid.cols + 1):
            x, y = grid.tile_to_pixel(row, col)
            label = f"{row}{grid.col_to_letter(col)}"
            print(f"  {label}: ({x:6.1f}, {y:5.1f})", end="")
        print()


if __name__ == "__main__":
    print_grid_map()
