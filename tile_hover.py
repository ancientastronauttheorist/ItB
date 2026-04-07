#!/usr/bin/env python3
"""Convert visual tile coordinates (e.g. C5) to MCP screen pixel coordinates.

Usage:
    python3 tile_hover.py C5
    python3 tile_hover.py D7 B8 F3

Visual grid notation:
    Columns A-H (right edge labels), Rows 1-8 (left edge labels)
    A1 = bottom corner, H8 = top corner

Output: tile_name pixel_x pixel_y
"""

import sys
from src.control.executor import grid_to_mcp, recalibrate


def visual_to_save(tile: str) -> tuple[int, int]:
    """Convert visual notation like 'C5' to save file (x, y) coordinates.

    Visual: Row = 8 - save_x, Col = chr(72 - save_y)
    Inverse: save_x = 8 - row, save_y = 72 - ord(col_letter)
    """
    tile = tile.strip().upper()
    col_letter = tile[0]
    row_number = int(tile[1])

    if col_letter < 'A' or col_letter > 'H':
        raise ValueError(f"Column must be A-H, got '{col_letter}'")
    if row_number < 1 or row_number > 8:
        raise ValueError(f"Row must be 1-8, got {row_number}")

    save_x = 8 - row_number
    save_y = 72 - ord(col_letter)  # H=0, G=1, ..., A=7
    return save_x, save_y


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tile_hover.py C5 [D7 B8 ...]")
        sys.exit(1)

    recalibrate()

    for tile in sys.argv[1:]:
        try:
            save_x, save_y = visual_to_save(tile)
            px, py = grid_to_mcp(save_x, save_y)
            print(f"{tile.upper()} {px} {py}")
        except (ValueError, IndexError) as e:
            print(f"ERROR: {tile} — {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
