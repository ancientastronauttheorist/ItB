"""Classify tile terrain type from pixel colors.

Each terrain type in Into the Breach has a distinctive color palette.
We sample the bottom portion of each tile diamond (below any units/buildings)
and classify based on average color in HSV space.

This is the fast path — no hovering needed. Used during gameplay.
"""

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple


# HSV color ranges for terrain classification
# H: 0-180, S: 0-255, V: 0-255 (OpenCV convention)
# These will be refined from ground truth data
TERRAIN_COLORS = {
    "ground": {
        "hue_range": (25, 50),      # olive/green-brown
        "sat_range": (30, 150),
        "val_range": (50, 140),
    },
    "forest": {
        "hue_range": (30, 60),      # green with more saturation
        "sat_range": (80, 200),
        "val_range": (50, 150),
    },
    "water": {
        "hue_range": (90, 130),     # blue
        "sat_range": (50, 200),
        "val_range": (40, 160),
    },
    "sand": {
        "hue_range": (15, 35),      # warm yellow-brown
        "sat_range": (40, 180),
        "val_range": (100, 200),
    },
    "ice": {
        "hue_range": (85, 115),     # light blue
        "sat_range": (10, 80),
        "val_range": (150, 255),
    },
    "lava": {
        "hue_range": (0, 15),       # red-orange
        "sat_range": (100, 255),
        "val_range": (100, 255),
    },
    "mountain": {
        "hue_range": (10, 30),      # gray-brown
        "sat_range": (10, 60),
        "val_range": (80, 160),
    },
    "fire": {
        "hue_range": (5, 25),       # orange-red
        "sat_range": (150, 255),
        "val_range": (150, 255),
    },
}


def sample_terrain_colors(
    tile_img: np.ndarray,
    mask: np.ndarray | None = None,
) -> Tuple[float, float, float]:
    """Get average HSV color of the bottom portion of a tile.

    The bottom ~40% of the tile diamond is mostly terrain surface,
    while units/buildings extend upward.

    Returns:
        (avg_hue, avg_sat, avg_val) in OpenCV ranges.
    """
    h, w = tile_img.shape[:2]

    # Sample bottom 40% of tile
    y_start = int(h * 0.6)
    region = tile_img[y_start:, :]

    if mask is not None:
        mask_region = mask[y_start:]
        region = region[mask_region > 0]
    else:
        region = region.reshape(-1, 3)

    if len(region) == 0:
        return (0.0, 0.0, 0.0)

    hsv = cv2.cvtColor(region.reshape(1, -1, 3), cv2.COLOR_BGR2HSV)
    avg = hsv.mean(axis=1).mean(axis=0)
    return (float(avg[0]), float(avg[1]), float(avg[2]))


def classify_terrain_by_color(avg_hsv: Tuple[float, float, float]) -> str:
    """Classify terrain type from average HSV color.

    Returns:
        Terrain type string, or "unknown".
    """
    h, s, v = avg_hsv

    # Very dark = building shadow, chasm, or off-grid
    if v < 30:
        return "chasm"

    best_match = "unknown"
    best_score = float('inf')

    for terrain, ranges in TERRAIN_COLORS.items():
        h_lo, h_hi = ranges["hue_range"]
        s_lo, s_hi = ranges["sat_range"]
        v_lo, v_hi = ranges["val_range"]

        # Check if within range
        h_in = h_lo <= h <= h_hi
        s_in = s_lo <= s <= s_hi
        v_in = v_lo <= v <= v_hi

        if h_in and s_in and v_in:
            # Distance to range center
            h_center = (h_lo + h_hi) / 2
            s_center = (s_lo + s_hi) / 2
            v_center = (v_lo + v_hi) / 2
            score = abs(h - h_center) + abs(s - s_center) * 0.3 + abs(v - v_center) * 0.3
            if score < best_score:
                best_score = score
                best_match = terrain

    return best_match


def has_building(tile_img: np.ndarray) -> bool:
    """Detect if a tile has a building on it.

    Buildings have distinctive tall rectangular shapes with
    yellow-lit windows on a gray structure.
    """
    h, w = tile_img.shape[:2]

    # Check top half for tall gray structures
    top_half = tile_img[:h//2, :]
    hsv = cv2.cvtColor(top_half, cv2.COLOR_BGR2HSV)

    # Buildings are gray (low saturation) with moderate value
    gray_mask = (hsv[:, :, 1] < 40) & (hsv[:, :, 2] > 80) & (hsv[:, :, 2] < 200)
    gray_ratio = gray_mask.sum() / gray_mask.size

    # Buildings also have yellow windows
    yellow_mask = (hsv[:, :, 0] > 15) & (hsv[:, :, 0] < 35) & \
                  (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 150)
    yellow_ratio = yellow_mask.sum() / yellow_mask.size

    return gray_ratio > 0.15 and yellow_ratio > 0.02


def has_unit(tile_img: np.ndarray) -> bool:
    """Detect if a tile has any unit (mech or Vek) on it.

    Units extend above the tile surface and have more varied colors
    than plain terrain.
    """
    h, w = tile_img.shape[:2]

    # Check upper portion for non-terrain pixels
    upper = tile_img[:int(h * 0.4), :]

    # Units tend to have higher color variance than empty tiles
    if upper.size == 0:
        return False

    gray = cv2.cvtColor(upper, cv2.COLOR_BGR2GRAY)
    variance = gray.var()

    return variance > 800  # threshold to be tuned


def detect_attack_arrow(tile_img: np.ndarray) -> str:
    """Detect red attack direction arrows on a tile.

    Returns:
        Direction string: "N", "S", "E", "W", or "" if none.
    """
    hsv = cv2.cvtColor(tile_img, cv2.COLOR_BGR2HSV)

    # Red arrows: hue near 0 or 170-180, high saturation
    red_mask = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 165)) & \
               (hsv[:, :, 1] > 150) & (hsv[:, :, 2] > 100)

    red_ratio = red_mask.sum() / red_mask.size
    if red_ratio < 0.005:  # less than 0.5% red pixels = no arrow
        return ""

    # Find centroid of red pixels to determine direction
    h, w = tile_img.shape[:2]
    cy, cx = h // 2, w // 2

    red_points = np.where(red_mask)
    if len(red_points[0]) == 0:
        return ""

    red_cy = red_points[0].mean()
    red_cx = red_points[1].mean()

    # Arrow points in the attack direction
    dy = red_cy - cy
    dx = red_cx - cx

    if abs(dy) > abs(dx):
        return "S" if dy > 0 else "N"
    else:
        return "E" if dx > 0 else "W"


def calibrate_from_ground_truth(
    tiles_dir: Path,
    ground_truth: dict,
) -> dict:
    """Calibrate color ranges from labeled tile images.

    Args:
        tiles_dir: Directory with tile_1A.png, tile_2B.png, etc.
        ground_truth: Dict mapping "1A" -> {"terrain": "ground", ...}

    Returns:
        Updated color ranges per terrain type.
    """
    color_samples = {}

    for label, info in ground_truth.items():
        terrain = info.get("terrain", "unknown")
        if terrain == "unknown":
            continue

        tile_path = tiles_dir / f"tile_{label}.png"
        if not tile_path.exists():
            continue

        img = cv2.imread(str(tile_path))
        if img is None:
            continue

        avg_hsv = sample_terrain_colors(img)

        if terrain not in color_samples:
            color_samples[terrain] = []
        color_samples[terrain].append(avg_hsv)

    # Compute ranges from samples
    ranges = {}
    for terrain, samples in color_samples.items():
        arr = np.array(samples)
        ranges[terrain] = {
            "hue_range": (float(arr[:, 0].min() - 5), float(arr[:, 0].max() + 5)),
            "sat_range": (float(arr[:, 1].min() - 10), float(arr[:, 1].max() + 10)),
            "val_range": (float(arr[:, 2].min() - 10), float(arr[:, 2].max() + 10)),
            "samples": len(samples),
        }
        print(f"{terrain}: H={ranges[terrain]['hue_range']}, "
              f"S={ranges[terrain]['sat_range']}, V={ranges[terrain]['val_range']} "
              f"({len(samples)} samples)")

    return ranges
