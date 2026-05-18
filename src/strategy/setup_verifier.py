"""Visual checks for the new-run difficulty setup screen.

The Advanced Content checkboxes are visually odd: the small square mostly
behaves as a hover target, while enabled content is most reliably shown by the
colored icon beside the row. Disabled rows render that icon as grayscale.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised only on missing dependency
    Image = None

from src.capture.window import get_window_bounds, take_screenshot

BASE_SIZE = (1280, 748)

ADVANCED_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "key": "enemy_units",
        "label": "Enemy Units",
        "icon_box": (558, 274, 616, 344),
        "click": (646, 304),
        "colorfulness_threshold": 0.06,
    },
    {
        "key": "missions",
        "label": "Missions",
        "icon_box": (558, 350, 616, 418),
        "click": (646, 379),
        "colorfulness_threshold": 0.05,
    },
    {
        "key": "equipment",
        "label": "Equipment",
        "icon_box": (558, 426, 616, 493),
        "click": (646, 454),
        "colorfulness_threshold": 0.11,
    },
    {
        "key": "pilot_abilities",
        "label": "Pilot Abilities",
        "icon_box": (558, 503, 616, 570),
        "click": (646, 529),
        "colorfulness_threshold": 0.10,
    },
)

DIFFICULTIES: dict[int, dict[str, Any]] = {
    0: {"label": "Easy", "button_box": (909, 250, 1122, 317), "click": (1016, 284)},
    1: {"label": "Normal", "button_box": (909, 326, 1122, 391), "click": (1016, 359)},
    2: {"label": "Hard", "button_box": (909, 402, 1122, 466), "click": (1016, 434)},
    3: {"label": "Unfair", "button_box": (909, 477, 1122, 541), "click": (1016, 509)},
}

YELLOW_BORDER_THRESHOLD = 0.025


@dataclass(frozen=True)
class SetupCheck:
    status: str
    expected_difficulty: int
    actual_difficulty: int | None
    advanced: list[dict[str, Any]]
    missing_advanced: list[str]
    screenshot_path: str | None
    click_plan: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expected_difficulty": self.expected_difficulty,
            "actual_difficulty": self.actual_difficulty,
            "advanced": self.advanced,
            "missing_advanced": self.missing_advanced,
            "screenshot_path": self.screenshot_path,
            "click_plan": self.click_plan,
        }


def capture_and_check_setup(
    *,
    expected_difficulty: int = 0,
    require_all_advanced: bool = True,
    output_path: str | Path = "tmp/new_run_setup_check.png",
) -> SetupCheck:
    if Image is None:
        raise RuntimeError("Pillow is required for setup verification")
    screenshot = take_screenshot(output_path)
    bounds = get_window_bounds() or {}
    window_size = (
        int(bounds.get("width", BASE_SIZE[0])),
        int(bounds.get("height", BASE_SIZE[1])),
    )
    with Image.open(screenshot) as img:
        return analyze_setup_image(
            img.convert("RGB"),
            expected_difficulty=expected_difficulty,
            require_all_advanced=require_all_advanced,
            screenshot_path=str(screenshot),
            click_window_size=window_size,
        )


def analyze_setup_image(
    img: "Image.Image",
    *,
    expected_difficulty: int = 0,
    require_all_advanced: bool = True,
    screenshot_path: str | None = None,
    click_window_size: tuple[int, int] | None = None,
) -> SetupCheck:
    if expected_difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {expected_difficulty!r}")

    sx, sy = _scale_for(img)
    if click_window_size is None:
        click_sx, click_sy = sx, sy
    else:
        click_sx = click_window_size[0] / BASE_SIZE[0]
        click_sy = click_window_size[1] / BASE_SIZE[1]
    advanced: list[dict[str, Any]] = []
    click_plan: list[dict[str, Any]] = []
    for item in ADVANCED_ITEMS:
        score = _icon_colorfulness(img, _scale_box(item["icon_box"], sx, sy))
        threshold = float(item["colorfulness_threshold"])
        enabled = score >= threshold
        cx, cy = _scale_point(item["click"], click_sx, click_sy)
        row = {
            "key": item["key"],
            "label": item["label"],
            "enabled": enabled,
            "colorfulness": round(score, 3),
            "threshold": threshold,
            "click": {"x": cx, "y": cy, "coordinate_space": "window"},
        }
        advanced.append(row)
        if require_all_advanced and not enabled:
            click_plan.append({
                "type": "left_click",
                "x": cx,
                "y": cy,
                "coordinate_space": "window",
                "description": f"Enable Advanced Content: {item['label']}",
            })

    difficulty_scores = {
        value: _yellow_border_ratio(img, _scale_box(info["button_box"], sx, sy))
        for value, info in DIFFICULTIES.items()
    }
    actual_difficulty = max(difficulty_scores, key=difficulty_scores.get)
    if difficulty_scores[actual_difficulty] < YELLOW_BORDER_THRESHOLD:
        actual_difficulty = None

    if actual_difficulty != expected_difficulty:
        cx, cy = _scale_point(
            DIFFICULTIES[expected_difficulty]["click"],
            click_sx,
            click_sy,
        )
        click_plan.append({
            "type": "left_click",
            "x": cx,
            "y": cy,
            "coordinate_space": "window",
            "description": (
                f"Select difficulty: {DIFFICULTIES[expected_difficulty]['label']}"
            ),
        })

    missing = [row["label"] for row in advanced if not row["enabled"]]
    ok_advanced = (not require_all_advanced) or not missing
    ok_difficulty = actual_difficulty == expected_difficulty
    status = "PASS" if ok_advanced and ok_difficulty else "FAIL"

    return SetupCheck(
        status=status,
        expected_difficulty=expected_difficulty,
        actual_difficulty=actual_difficulty,
        advanced=advanced,
        missing_advanced=missing,
        screenshot_path=screenshot_path,
        click_plan=click_plan,
    )


def _scale_for(img: "Image.Image") -> tuple[float, float]:
    return (img.width / BASE_SIZE[0], img.height / BASE_SIZE[1])


def _scale_point(point: tuple[int, int], sx: float, sy: float) -> tuple[int, int]:
    return (int(round(point[0] * sx)), int(round(point[1] * sy)))


def _scale_box(
    box: tuple[int, int, int, int],
    sx: float,
    sy: float,
) -> tuple[int, int, int, int]:
    x0, y0 = _scale_point((box[0], box[1]), sx, sy)
    x1, y1 = _scale_point((box[2], box[3]), sx, sy)
    return (x0, y0, x1, y1)


def _icon_colorfulness(img: "Image.Image", box: tuple[int, int, int, int]) -> float:
    crop = img.crop(box)
    scores: list[float] = []
    for r, g, b in crop.getdata():
        if max(r, g, b) < 45:
            continue
        scores.append((max(r, g, b) - min(r, g, b)) / 255.0)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _yellow_border_ratio(img: "Image.Image", box: tuple[int, int, int, int]) -> float:
    crop = img.crop(box)
    pixels = list(crop.getdata())
    if not pixels:
        return 0.0
    yellow = 0
    for r, g, b in pixels:
        if r >= 185 and g >= 150 and b <= 160 and (r - b) >= 50:
            yellow += 1
    return yellow / len(pixels)
