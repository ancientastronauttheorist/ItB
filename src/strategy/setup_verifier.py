"""Visual checks for the new-run difficulty setup screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised only on missing dependency
    Image = None

from src.capture.window import get_window_bounds, is_game_frontmost, take_screenshot

BASE_SIZE = (1280, 748)

ADVANCED_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "key": "enemy_units",
        "label": "Enemy Units",
        "icon_box": (558, 274, 616, 344),
        "checkbox_box": (628, 286, 664, 322),
        "click": (646, 304),
        "colorfulness_threshold": 0.06,
    },
    {
        "key": "missions",
        "label": "Missions",
        "icon_box": (558, 350, 616, 418),
        "checkbox_box": (628, 361, 664, 397),
        "click": (646, 379),
        "colorfulness_threshold": 0.05,
    },
    {
        "key": "equipment",
        "label": "Equipment",
        "icon_box": (558, 426, 616, 493),
        "checkbox_box": (628, 436, 664, 472),
        "click": (646, 454),
        "colorfulness_threshold": 0.11,
    },
    {
        "key": "pilot_abilities",
        "label": "Pilot Abilities",
        "icon_box": (558, 503, 616, 570),
        "checkbox_box": (628, 511, 664, 547),
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
CHECKBOX_PRESENT_BRIGHTNESS_THRESHOLD = 0.08
CHECKBOX_ENABLED_BRIGHTNESS_THRESHOLD = 0.25


@dataclass(frozen=True)
class SetupCheck:
    status: str
    expected_difficulty: int
    actual_difficulty: int | None
    setup_screen_detected: bool
    setup_signature: dict[str, Any]
    advanced: list[dict[str, Any]]
    missing_advanced: list[str]
    unexpected_advanced: list[str]
    desired_advanced: str
    screenshot_path: str | None
    window_focus_verified: bool
    window_bounds: dict[str, Any] | None
    click_plan: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expected_difficulty": self.expected_difficulty,
            "actual_difficulty": self.actual_difficulty,
            "setup_screen_detected": self.setup_screen_detected,
            "setup_signature": self.setup_signature,
            "advanced": self.advanced,
            "missing_advanced": self.missing_advanced,
            "unexpected_advanced": self.unexpected_advanced,
            "desired_advanced": self.desired_advanced,
            "screenshot_path": self.screenshot_path,
            "window_focus_verified": self.window_focus_verified,
            "window_bounds": self.window_bounds,
            "click_plan": self.click_plan,
        }


def capture_and_check_setup(
    *,
    expected_difficulty: int = 0,
    require_all_advanced: bool = True,
    advanced_content: str | None = None,
    output_path: str | Path = "tmp/new_run_setup_check.png",
) -> SetupCheck:
    if Image is None:
        raise RuntimeError("Pillow is required for setup verification")
    bounds = get_window_bounds()
    frontmost = is_game_frontmost() if bounds else False
    screenshot = take_screenshot(output_path, bounds=bounds)
    bounds_dict = dict(bounds) if bounds else None
    bounds = bounds or {}
    window_size = (
        int(bounds.get("width", BASE_SIZE[0])),
        int(bounds.get("height", BASE_SIZE[1])),
    )
    with Image.open(screenshot) as img:
        return analyze_setup_image(
            img.convert("RGB"),
            expected_difficulty=expected_difficulty,
            require_all_advanced=require_all_advanced,
            advanced_content=advanced_content,
            screenshot_path=str(screenshot),
            click_window_size=window_size,
            window_focus_verified=bounds_dict is not None and frontmost,
            window_bounds=bounds_dict,
        )


def analyze_setup_image(
    img: "Image.Image",
    *,
    expected_difficulty: int = 0,
    require_all_advanced: bool = True,
    advanced_content: str | None = None,
    screenshot_path: str | None = None,
    click_window_size: tuple[int, int] | None = None,
    window_focus_verified: bool = True,
    window_bounds: dict[str, Any] | None = None,
) -> SetupCheck:
    if expected_difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {expected_difficulty!r}")
    desired_advanced = (
        advanced_content
        if advanced_content is not None
        else ("on" if require_all_advanced else "any")
    )
    if desired_advanced not in {"on", "off", "any"}:
        raise ValueError(f"unknown advanced content mode {desired_advanced!r}")

    sx, sy = _scale_for(img)
    if click_window_size is None:
        click_sx, click_sy = sx, sy
    else:
        click_sx = click_window_size[0] / BASE_SIZE[0]
        click_sy = click_window_size[1] / BASE_SIZE[1]
    advanced: list[dict[str, Any]] = []
    click_plan: list[dict[str, Any]] = []
    for item in ADVANCED_ITEMS:
        icon_score = _icon_colorfulness(img, _scale_box(item["icon_box"], sx, sy))
        checkbox = _checkbox_brightness(img, _scale_box(item["checkbox_box"], sx, sy))
        threshold = float(item["colorfulness_threshold"])
        checkbox_present = (
            checkbox["bright_ratio"] >= CHECKBOX_PRESENT_BRIGHTNESS_THRESHOLD
        )
        enabled = (
            checkbox_present
            and checkbox["bright_ratio"] >= CHECKBOX_ENABLED_BRIGHTNESS_THRESHOLD
        )
        cx, cy = _scale_point(item["click"], click_sx, click_sy)
        row = {
            "key": item["key"],
            "label": item["label"],
            "enabled": enabled,
            "colorfulness": round(icon_score, 3),
            "threshold": threshold,
            "checkbox_present": checkbox_present,
            "checkbox_brightness": checkbox["bright_ratio"],
            "checkbox_enabled_threshold": CHECKBOX_ENABLED_BRIGHTNESS_THRESHOLD,
            "click": {"x": cx, "y": cy, "coordinate_space": "window"},
        }
        advanced.append(row)

    present_count = sum(1 for row in advanced if row["checkbox_present"])
    setup_screen_detected = present_count >= 3
    setup_signature = {
        "advanced_checkbox_present_count": present_count,
        "advanced_checkbox_required_count": 3,
        "checkbox_present_brightness_threshold": CHECKBOX_PRESENT_BRIGHTNESS_THRESHOLD,
        "checkbox_enabled_brightness_threshold": CHECKBOX_ENABLED_BRIGHTNESS_THRESHOLD,
        "window_focus_verified": bool(window_focus_verified),
    }
    if setup_screen_detected:
        for row in advanced:
            if desired_advanced == "on" and not row["enabled"]:
                click_plan.append({
                    "type": "left_click",
                    "x": row["click"]["x"],
                    "y": row["click"]["y"],
                    "coordinate_space": "window",
                    "description": f"Enable Advanced Content: {row['label']}",
                })
            elif desired_advanced == "off" and row["enabled"]:
                click_plan.append({
                    "type": "left_click",
                    "x": row["click"]["x"],
                    "y": row["click"]["y"],
                    "coordinate_space": "window",
                    "description": f"Disable Advanced Content: {row['label']}",
                })

    difficulty_scores = {
        value: _yellow_border_ratio(img, _scale_box(info["button_box"], sx, sy))
        for value, info in DIFFICULTIES.items()
    }
    actual_difficulty = max(difficulty_scores, key=difficulty_scores.get)
    if difficulty_scores[actual_difficulty] < YELLOW_BORDER_THRESHOLD:
        actual_difficulty = None
    if not setup_screen_detected:
        actual_difficulty = None

    if setup_screen_detected and actual_difficulty != expected_difficulty:
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
    unexpected = [row["label"] for row in advanced if row["enabled"]]
    if desired_advanced == "on":
        ok_advanced = setup_screen_detected and not missing
    elif desired_advanced == "off":
        ok_advanced = setup_screen_detected and not unexpected
    else:
        ok_advanced = setup_screen_detected
    ok_difficulty = setup_screen_detected and actual_difficulty == expected_difficulty
    status = "PASS" if ok_advanced and ok_difficulty and window_focus_verified else "FAIL"
    if not window_focus_verified:
        click_plan = []

    return SetupCheck(
        status=status,
        expected_difficulty=expected_difficulty,
        actual_difficulty=actual_difficulty,
        setup_screen_detected=setup_screen_detected,
        setup_signature=setup_signature,
        advanced=advanced,
        missing_advanced=missing,
        unexpected_advanced=unexpected,
        desired_advanced=desired_advanced,
        screenshot_path=screenshot_path,
        window_focus_verified=bool(window_focus_verified),
        window_bounds=window_bounds,
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


def _checkbox_brightness(img: "Image.Image", box: tuple[int, int, int, int]) -> dict[str, float]:
    crop = img.crop(box)
    pixels = list(crop.getdata())
    if not pixels:
        return {"bright_ratio": 0.0}
    bright = 0
    for r, g, b in pixels:
        if max(r, g, b) >= 170:
            bright += 1
    return {"bright_ratio": round(bright / len(pixels), 3)}


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
