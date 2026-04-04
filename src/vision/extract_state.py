"""Extract full board state from a screenshot.

This is the main entry point for Phase 2. Given a screenshot (either from
the computer-use tool or screencapture), it:
1. Detects the grid position
2. Extracts each tile
3. Classifies terrain and detects units
4. Returns a structured BoardState
"""

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path

from src.capture.grid import GridConfig
from src.capture.detect_grid import detect_grid
from src.vision.tile_extractor import extract_tile_rect, extract_tile_diamond
from src.vision.terrain_classifier import (
    sample_terrain_colors,
    classify_terrain_by_color,
    has_building,
    has_unit,
    detect_attack_arrow,
)
from src.vision.board_scanner import BoardState, TileState


def extract_board_state(
    image: np.ndarray,
    grid: GridConfig | None = None,
) -> BoardState:
    """Extract the full board state from a screenshot.

    Args:
        image: BGR screenshot as numpy array.
        grid: Grid configuration. If None, auto-detects from window position.

    Returns:
        BoardState with all 64 tiles classified.
    """
    if grid is None:
        grid = detect_grid()
        if grid is None:
            raise RuntimeError("Could not detect game window")

    board = BoardState()

    for row in range(1, 9):
        for col in range(1, 9):
            tile_img = extract_tile_rect(image, row, col, grid, padding=2)

            # Classify terrain from bottom portion colors
            avg_hsv = sample_terrain_colors(tile_img)
            terrain = classify_terrain_by_color(avg_hsv)

            # Check for building
            if has_building(tile_img):
                terrain = "building"

            # Detect attack arrows
            arrow = detect_attack_arrow(tile_img)

            # Check for unit presence
            occupant = ""
            if has_unit(tile_img):
                occupant = "unknown_unit"

            tile = TileState(
                row=row,
                col=col,
                terrain=terrain,
                occupant=occupant,
                attack_direction=arrow,
            )
            board.tiles.append(tile)

    return board


def draw_board_overlay(
    image: np.ndarray,
    board: BoardState,
    grid: GridConfig,
) -> np.ndarray:
    """Draw the detected board state as an overlay on the screenshot.

    Color codes:
    - Green outline: ground
    - Dark green fill: forest
    - Blue: water
    - Gray: building
    - Red arrow: attack direction
    - Yellow dot: unit present
    """
    overlay = image.copy()

    terrain_colors = {
        "ground": (0, 180, 0),
        "forest": (0, 120, 0),
        "water": (200, 100, 0),
        "sand": (0, 180, 220),
        "ice": (220, 200, 150),
        "mountain": (100, 100, 100),
        "building": (180, 180, 180),
        "chasm": (40, 0, 40),
        "fire": (0, 80, 255),
        "lava": (0, 0, 200),
        "unknown": (0, 0, 255),
    }

    hw = int(grid.tile_half_width)
    hh = int(grid.tile_half_height)

    for tile in board.tiles:
        cx, cy = grid.tile_to_pixel(tile.row, tile.col)
        cx, cy = int(cx), int(cy)

        # Draw diamond outline
        color = terrain_colors.get(tile.terrain, (0, 0, 255))
        pts = np.array([
            [cx, cy - hh],
            [cx + hw, cy],
            [cx, cy + hh],
            [cx - hw, cy],
        ], dtype=np.int32)
        cv2.polylines(overlay, [pts], True, color, 1)

        # Label with terrain initial
        label = tile.terrain[0].upper() if tile.terrain != "unknown" else "?"
        cv2.putText(overlay, label, (cx - 5, cy + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

        # Mark units with yellow dot
        if tile.occupant:
            cv2.circle(overlay, (cx, cy - hh // 2), 3, (0, 255, 255), -1)

        # Draw attack arrow
        if tile.attack_direction:
            arrow_len = 12
            dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)
                      }.get(tile.attack_direction, (0, 0))
            cv2.arrowedLine(
                overlay,
                (cx, cy),
                (cx + dx * arrow_len, cy + dy * arrow_len),
                (0, 0, 255), 2, tipLength=0.4
            )

    return overlay


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.vision.extract_state <screenshot.png> [output.json]")
        sys.exit(1)

    img_path = sys.argv[1]
    img = cv2.imread(img_path)
    if img is None:
        print(f"Could not load {img_path}")
        sys.exit(1)

    grid = detect_grid()
    if grid is None:
        print("Game window not found - using default grid")
        from src.capture.grid import DEFAULT_GRID
        grid = DEFAULT_GRID

    board = extract_board_state(img, grid)

    # Print summary
    terrains = {}
    units = 0
    arrows = 0
    for t in board.tiles:
        terrains[t.terrain] = terrains.get(t.terrain, 0) + 1
        if t.occupant:
            units += 1
        if t.attack_direction:
            arrows += 1

    print(f"Board state extracted: {len(board.tiles)} tiles")
    print(f"Terrain: {terrains}")
    print(f"Units detected: {units}")
    print(f"Attack arrows: {arrows}")

    # Save overlay
    overlay = draw_board_overlay(img, board, grid)
    overlay_path = img_path.replace(".png", "_overlay.png")
    cv2.imwrite(overlay_path, overlay)
    print(f"Overlay saved to {overlay_path}")

    # Save JSON
    if len(sys.argv) > 2:
        board.to_json(sys.argv[2])
        print(f"Board state saved to {sys.argv[2]}")
