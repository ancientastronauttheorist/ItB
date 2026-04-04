"""Extract individual tile images from an Into the Breach screenshot.

Each tile is an isometric diamond. We extract the axis-aligned bounding
rectangle for each tile, plus a diamond-masked version for cleaner matching.
"""

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path

from src.capture.grid import GridConfig, DEFAULT_GRID


def extract_tile_rect(
    image: np.ndarray,
    row: int,
    col: int,
    grid: GridConfig = DEFAULT_GRID,
    padding: int = 5,
) -> np.ndarray:
    """Extract the bounding rectangle for a single tile.

    Args:
        image: Full screenshot as BGR numpy array.
        row: Row number (1-8).
        col: Column number (1-8, where A=1).
        grid: Grid configuration.
        padding: Extra pixels around the diamond bounding box.

    Returns:
        Cropped tile image (BGR).
    """
    cx, cy = grid.tile_to_pixel(row, col)
    hw = grid.tile_half_width + padding
    hh = grid.tile_half_height + padding

    x1 = max(0, int(cx - hw))
    y1 = max(0, int(cy - hh))
    x2 = min(image.shape[1], int(cx + hw))
    y2 = min(image.shape[0], int(cy + hh))

    return image[y1:y2, x1:x2].copy()


def create_diamond_mask(width: int, height: int) -> np.ndarray:
    """Create a diamond-shaped mask for a tile.

    Returns:
        Single-channel mask (255 inside diamond, 0 outside).
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    cx, cy = width // 2, height // 2
    hw, hh = width // 2, height // 2

    pts = np.array([
        [cx, cy - hh],      # top
        [cx + hw, cy],       # right
        [cx, cy + hh],       # bottom
        [cx - hw, cy],       # left
    ], dtype=np.int32)

    cv2.fillPoly(mask, [pts], 255)
    return mask


def extract_tile_diamond(
    image: np.ndarray,
    row: int,
    col: int,
    grid: GridConfig = DEFAULT_GRID,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract a tile with diamond mask applied.

    Returns:
        (tile_image, mask) - tile with black outside diamond, and the mask.
    """
    tile = extract_tile_rect(image, row, col, grid, padding=0)
    mask = create_diamond_mask(tile.shape[1], tile.shape[0])
    masked = cv2.bitwise_and(tile, tile, mask=mask)
    return masked, mask


def extract_all_tiles(
    image: np.ndarray,
    grid: GridConfig = DEFAULT_GRID,
) -> dict[tuple[int, int], np.ndarray]:
    """Extract bounding rectangles for all 64 tiles.

    Returns:
        Dict mapping (row, col) to cropped tile image.
    """
    tiles = {}
    for row in range(1, grid.rows + 1):
        for col in range(1, grid.cols + 1):
            tiles[(row, col)] = extract_tile_rect(image, row, col, grid)
    return tiles


def save_tile_grid(
    image: np.ndarray,
    output_dir: Path,
    grid: GridConfig = DEFAULT_GRID,
) -> None:
    """Extract and save all 64 tiles as individual images.

    Files are named like tile_1A.png, tile_2B.png, etc.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in range(1, grid.rows + 1):
        for col in range(1, grid.cols + 1):
            tile = extract_tile_rect(image, row, col, grid)
            letter = grid.col_to_letter(col)
            filename = f"tile_{row}{letter}.png"
            cv2.imwrite(str(output_dir / filename), tile)


def get_tile_terrain_region(
    image: np.ndarray,
    row: int,
    col: int,
    grid: GridConfig = DEFAULT_GRID,
) -> np.ndarray:
    """Extract just the bottom portion of a tile (terrain, no sprites on top).

    The bottom ~40% of the diamond contains mostly terrain color,
    while units/buildings extend upward from the tile surface.
    """
    cx, cy = grid.tile_to_pixel(row, col)
    hw = grid.tile_half_width
    hh = grid.tile_half_height

    # Bottom portion of the diamond (below center)
    y_start = int(cy)
    y_end = int(cy + hh)
    x_start = max(0, int(cx - hw * 0.6))
    x_end = min(image.shape[1], int(cx + hw * 0.6))

    return image[y_start:y_end, x_start:x_end].copy()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        screenshot = "assets/screenshots/mission_reference.png"
    else:
        screenshot = sys.argv[1]

    img = cv2.imread(screenshot)
    if img is None:
        print(f"Could not load {screenshot}")
        sys.exit(1)

    out_dir = Path("assets/sprites/tiles")
    save_tile_grid(img, out_dir)
    print(f"Saved 64 tiles to {out_dir}")
