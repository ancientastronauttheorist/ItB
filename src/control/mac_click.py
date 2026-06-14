"""Small macOS click helpers for trusted UI buttons.

This module is intentionally narrow: it clicks already-calibrated screen
coordinates such as the End Turn button. Combat tile clicks still flow through
the bridge or Computer Use planners.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import time
import shutil
import tempfile
import ctypes
from pathlib import Path


@dataclass(frozen=True)
class KnownWindowControl:
    """A trusted window-local control that can be clicked without scouting."""

    name: str
    window_x: int
    window_y: int
    description: str
    settle_seconds: float = 0.15
    hold_seconds: float = 0.3

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "window_x": self.window_x,
            "window_y": self.window_y,
            "description": self.description,
            "settle_seconds": self.settle_seconds,
            "hold_seconds": self.hold_seconds,
        }


KNOWN_WINDOW_CONTROLS: dict[str, KnownWindowControl] = {
    "pause": KnownWindowControl(
        name="pause",
        window_x=38,
        window_y=28,
        description="Pause / open game menu",
        settle_seconds=0.2,
    ),
    "menu_continue": KnownWindowControl(
        name="menu_continue",
        window_x=491,
        window_y=251,
        description="Pause menu Continue",
        settle_seconds=0.2,
    ),
    "pause_main_menu": KnownWindowControl(
        name="pause_main_menu",
        window_x=491,
        window_y=403,
        description="Pause menu Main Menu",
        settle_seconds=0.8,
    ),
    "title_continue": KnownWindowControl(
        name="title_continue",
        window_x=170,
        window_y=251,
        description="Title screen Continue",
        settle_seconds=1.0,
    ),
    "title_new_game": KnownWindowControl(
        name="title_new_game",
        window_x=170,
        window_y=315,
        description="Title screen New Game",
        settle_seconds=1.0,
    ),
    "setup_start": KnownWindowControl(
        name="setup_start",
        window_x=1005,
        window_y=96,
        description="New-run setup Start",
        settle_seconds=1.0,
    ),
    "setup_back": KnownWindowControl(
        name="setup_back",
        window_x=290,
        window_y=83,
        description="New-run setup Back",
        settle_seconds=0.8,
    ),
    "setup_advanced_enemies": KnownWindowControl(
        name="setup_advanced_enemies",
        window_x=646,
        window_y=304,
        description="Setup Advanced Content Enemy Units toggle",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "setup_advanced_missions": KnownWindowControl(
        name="setup_advanced_missions",
        window_x=646,
        window_y=379,
        description="Setup Advanced Content Missions toggle",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "setup_advanced_equipment": KnownWindowControl(
        name="setup_advanced_equipment",
        window_x=646,
        window_y=454,
        description="Setup Advanced Content Equipment toggle",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "setup_advanced_pilots": KnownWindowControl(
        name="setup_advanced_pilots",
        window_x=646,
        window_y=529,
        description="Setup Advanced Content Pilot Abilities toggle",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "setup_change_squad": KnownWindowControl(
        name="setup_change_squad",
        window_x=807,
        window_y=539,
        description="New-run setup Change Squad",
        settle_seconds=0.5,
    ),
    "squad_zenith_guard": KnownWindowControl(
        name="squad_zenith_guard",
        window_x=520,
        window_y=356,
        description="Squad selection Zenith Guard",
        settle_seconds=0.8,
    ),
    "setup_modal_start": KnownWindowControl(
        name="setup_modal_start",
        window_x=1072,
        window_y=641,
        description="Difficulty setup modal Start",
        settle_seconds=1.0,
    ),
    "reward_continue": KnownWindowControl(
        name="reward_continue",
        window_x=1005,
        window_y=654,
        description="Reward / Region Secured Continue",
        settle_seconds=0.35,
    ),
    "bottom_continue": KnownWindowControl(
        name="bottom_continue",
        window_x=1005,
        window_y=680,
        description="Bottom-right Continue panel",
        settle_seconds=0.65,
    ),
    "pod_open_door": KnownWindowControl(
        name="pod_open_door",
        window_x=965,
        window_y=485,
        description="Pod Recovered Open Door",
        settle_seconds=1.2,
    ),
    "dialogue_textbox": KnownWindowControl(
        name="dialogue_textbox",
        window_x=250,
        window_y=205,
        description="Advisor dialogue text box dismiss",
        settle_seconds=0.45,
    ),
    "mission_preview_board": KnownWindowControl(
        name="mission_preview_board",
        window_x=848,
        window_y=448,
        description="Large mission preview board / Start Mission text",
        settle_seconds=0.8,
    ),
    "deploy_confirm": KnownWindowControl(
        name="deploy_confirm",
        window_x=106,
        window_y=164,
        description="Deployment Confirm",
        settle_seconds=0.5,
    ),
    "deploy_slot_0": KnownWindowControl(
        name="deploy_slot_0",
        window_x=102,
        window_y=250,
        description="Deployment mech slot 0",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "deploy_slot_1": KnownWindowControl(
        name="deploy_slot_1",
        window_x=102,
        window_y=388,
        description="Deployment mech slot 1",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "deploy_slot_2": KnownWindowControl(
        name="deploy_slot_2",
        window_x=102,
        window_y=520,
        description="Deployment mech slot 2",
        settle_seconds=0.08,
        hold_seconds=0.12,
    ),
    "modal_understood": KnownWindowControl(
        name="modal_understood",
        window_x=666,
        window_y=520,
        description="Modal / promotion Understood",
        settle_seconds=0.25,
    ),
    "kia_understood": KnownWindowControl(
        name="kia_understood",
        window_x=666,
        window_y=443,
        description="KIA / timeline modal Understood",
        settle_seconds=0.25,
    ),
    "panel_continue": KnownWindowControl(
        name="panel_continue",
        window_x=846,
        window_y=550,
        description="Dialogue / reward panel Continue",
        settle_seconds=0.35,
    ),
    "perfect_reward_weapon": KnownWindowControl(
        name="perfect_reward_weapon",
        window_x=456,
        window_y=480,
        description="Perfect Island left reward card",
        settle_seconds=0.25,
    ),
    "perfect_reward_pilot": KnownWindowControl(
        name="perfect_reward_pilot",
        window_x=637,
        window_y=480,
        description="Perfect Island middle reward card",
        settle_seconds=0.25,
    ),
    "perfect_reward_grid": KnownWindowControl(
        name="perfect_reward_grid",
        window_x=817,
        window_y=480,
        description="Perfect Island +2 Grid reward card",
        settle_seconds=0.35,
    ),
    "spend_reputation": KnownWindowControl(
        name="spend_reputation",
        window_x=641,
        window_y=650,
        description="Island complete Spend Reputation",
        settle_seconds=0.35,
    ),
    "shop_grid_power": KnownWindowControl(
        name="shop_grid_power",
        window_x=920,
        window_y=225,
        description="Shop +1 Grid Power supply card",
        settle_seconds=0.35,
    ),
    "shop_continue": KnownWindowControl(
        name="shop_continue",
        window_x=850,
        window_y=690,
        description="Shop Continue",
        settle_seconds=0.6,
    ),
    "leave_island": KnownWindowControl(
        name="leave_island",
        window_x=641,
        window_y=704,
        description="Island complete Leave Island",
        settle_seconds=0.6,
    ),
    "leave_confirm_yes": KnownWindowControl(
        name="leave_confirm_yes",
        window_x=568,
        window_y=444,
        description="Leave Island confirmation Yes",
        settle_seconds=0.6,
    ),
    "end_turn_confirm_yes": KnownWindowControl(
        name="end_turn_confirm_yes",
        window_x=568,
        window_y=396,
        description="End Turn active-units confirmation Yes",
        settle_seconds=0.2,
    ),
    "leave_confirm_no": KnownWindowControl(
        name="leave_confirm_no",
        window_x=713,
        window_y=444,
        description="Leave Island confirmation No",
        settle_seconds=0.25,
    ),
    "title_new_game_confirm_yes": KnownWindowControl(
        name="title_new_game_confirm_yes",
        window_x=568,
        window_y=444,
        description="Title New Game overwrite confirmation Yes",
        settle_seconds=1.0,
    ),
    "abandon_timeline": KnownWindowControl(
        name="abandon_timeline",
        window_x=490,
        window_y=591,
        description="Pause menu Abandon Timeline",
        settle_seconds=0.35,
    ),
    "abandon_confirm_yes": KnownWindowControl(
        name="abandon_confirm_yes",
        window_x=568,
        window_y=444,
        description="Abandon Timeline confirmation Yes",
        settle_seconds=0.8,
    ),
    "reset_turn": KnownWindowControl(
        name="reset_turn",
        window_x=520,
        window_y=58,
        description="Top-bar Reset Turn",
        settle_seconds=0.35,
    ),
    "abandon_pilot_available": KnownWindowControl(
        name="abandon_pilot_available",
        window_x=95,
        window_y=254,
        description="Abandon Timeline available pilot marker",
        settle_seconds=0.8,
    ),
    "abandon_pilot_slot": KnownWindowControl(
        name="abandon_pilot_slot",
        window_x=491,
        window_y=329,
        description="Abandon Timeline left carry-forward pilot selection",
        settle_seconds=0.8,
    ),
    "abandon_pilot_slot_two_left": KnownWindowControl(
        name="abandon_pilot_slot_two_left",
        window_x=562,
        window_y=329,
        description="Abandon Timeline left two-pilot carry-forward selection",
        settle_seconds=0.8,
    ),
    "abandon_pilot_slot_two_right": KnownWindowControl(
        name="abandon_pilot_slot_two_right",
        window_x=704,
        window_y=329,
        description="Abandon Timeline right two-pilot carry-forward selection",
        settle_seconds=0.8,
    ),
    "abandon_pilot_slot_wide": KnownWindowControl(
        name="abandon_pilot_slot_wide",
        window_x=632,
        window_y=329,
        description="Abandon Timeline middle carry-forward pilot selection",
        settle_seconds=0.8,
    ),
    "abandon_pilot_slot_right": KnownWindowControl(
        name="abandon_pilot_slot_right",
        window_x=773,
        window_y=329,
        description="Abandon Timeline right carry-forward pilot selection",
        settle_seconds=0.8,
    ),
    "island_archive": KnownWindowControl(
        name="island_archive",
        window_x=215,
        window_y=288,
        description="Island select Archive",
        settle_seconds=0.6,
    ),
    "island_rst": KnownWindowControl(
        name="island_rst",
        window_x=345,
        window_y=508,
        description="Island select R.S.T.",
        settle_seconds=0.6,
    ),
    "island_pinnacle": KnownWindowControl(
        name="island_pinnacle",
        window_x=635,
        window_y=368,
        description="Island select Pinnacle",
        settle_seconds=0.6,
    ),
    "island_detritus": KnownWindowControl(
        name="island_detritus",
        window_x=1070,
        window_y=550,
        description="Island select Detritus",
        settle_seconds=0.6,
    ),
    "end_turn": KnownWindowControl(
        name="end_turn",
        window_x=126,
        window_y=120,
        description="Click End Turn",
        settle_seconds=0.15,
    ),
}

_CONTROL_ALIASES = {
    "continue": "menu_continue",
    "resume": "menu_continue",
    "unpause": "menu_continue",
    "main_menu": "pause_main_menu",
    "pause_main": "pause_main_menu",
    "new_game": "title_new_game",
    "title_new": "title_new_game",
    "start": "setup_start",
    "start_run": "setup_start",
    "new_run_start": "setup_start",
    "adv_enemies": "setup_advanced_enemies",
    "advanced_enemies": "setup_advanced_enemies",
    "adv_missions": "setup_advanced_missions",
    "advanced_missions": "setup_advanced_missions",
    "adv_equipment": "setup_advanced_equipment",
    "advanced_equipment": "setup_advanced_equipment",
    "adv_pilots": "setup_advanced_pilots",
    "advanced_pilots": "setup_advanced_pilots",
    "change_squad": "setup_change_squad",
    "squad_change": "setup_change_squad",
    "zenith": "squad_zenith_guard",
    "zenith_guard": "squad_zenith_guard",
    "modal_start": "setup_modal_start",
    "difficulty_start": "setup_modal_start",
    "reward": "reward_continue",
    "region_secured_continue": "reward_continue",
    "ceo_continue": "reward_continue",
    "island_intro_continue": "bottom_continue",
    "bottom_right_continue": "bottom_continue",
    "pod_open": "pod_open_door",
    "open_pod": "pod_open_door",
    "open_door": "pod_open_door",
    "dialogue": "dialogue_textbox",
    "dialogue_continue": "dialogue_textbox",
    "textbox": "dialogue_textbox",
    "start_mission": "mission_preview_board",
    "mission_start": "mission_preview_board",
    "preview_board": "mission_preview_board",
    "confirm": "deploy_confirm",
    "confirm_deploy": "deploy_confirm",
    "deployment_confirm": "deploy_confirm",
    "slot0": "deploy_slot_0",
    "slot1": "deploy_slot_1",
    "slot2": "deploy_slot_2",
    "deploy0": "deploy_slot_0",
    "deploy1": "deploy_slot_1",
    "deploy2": "deploy_slot_2",
    "understood": "modal_understood",
    "promotion_understood": "modal_understood",
    "modal_continue": "modal_understood",
    "pilot_kia_understood": "kia_understood",
    "kia": "kia_understood",
    "perfect_continue": "panel_continue",
    "perfect_reward_continue": "panel_continue",
    "reward_grid": "perfect_reward_grid",
    "grid_reward": "perfect_reward_grid",
    "perfect_grid": "perfect_reward_grid",
    "shop": "spend_reputation",
    "store": "spend_reputation",
    "leave": "leave_island",
    "next_island": "leave_island",
    "leave_yes": "leave_confirm_yes",
    "confirm_leave": "leave_confirm_yes",
    "end_turn_yes": "end_turn_confirm_yes",
    "confirm_end_turn": "end_turn_confirm_yes",
    "leave_no": "leave_confirm_no",
    "title_new_game_yes": "title_new_game_confirm_yes",
    "title_confirm_yes": "title_new_game_confirm_yes",
    "new_game_confirm_yes": "title_new_game_confirm_yes",
    "abandon": "abandon_timeline",
    "abandon_yes": "abandon_confirm_yes",
    "confirm_abandon": "abandon_confirm_yes",
    "abandon_pilot": "abandon_pilot_slot",
    "timeline_pilot": "abandon_pilot_slot",
    "archive": "island_archive",
    "rst": "island_rst",
    "r.s.t.": "island_rst",
    "r.s.t": "island_rst",
    "pinnacle": "island_pinnacle",
    "detritus": "island_detritus",
    "turn": "end_turn",
    "end": "end_turn",
}


def _normalize_control_name(name: str) -> str:
    normalized = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _CONTROL_ALIASES.get(normalized, normalized)


_WINDOWS_CONTROL_OVERRIDES: dict[str, tuple[int, int]] = {
    "pause": (38, 28),
    "pause_main_menu": (1131, 774),
    "setup_start": (1712, 477),
    "setup_back": (1510, 477),
    "setup_advanced_enemies": (1287, 635),
    "setup_advanced_missions": (1287, 708),
    "setup_advanced_equipment": (1287, 781),
    "setup_advanced_pilots": (1287, 854),
    "setup_change_squad": (1615, 1077),
    "squad_zenith_guard": (1040, 713),
    "setup_modal_start": (1704, 974),
    "menu_continue": (1129, 582),
    "bottom_continue": (1633, 1009),
    "reward_continue": (1647, 985),
    "pod_open_door": (1605, 795),
    "dialogue_textbox": (1390, 555),
    "modal_understood": (1290, 885),
    "panel_continue": (1500, 900),
    "perfect_reward_grid": (1460, 810),
    "leave_island": (1280, 1395),
    "leave_confirm_yes": (1208, 795),
    "end_turn_confirm_yes": (1208, 742),
    "title_new_game_confirm_yes": (1208, 795),
    "mission_preview_board": (1460, 780),
    "deploy_confirm": (240, 235),
    "abandon_timeline": (1131, 924),
    "abandon_confirm_yes": (1208, 795),
    "abandon_pilot_slot": (1205, 660),
    "abandon_pilot_slot_two_left": (1205, 660),
    "abandon_pilot_slot_two_right": (1385, 660),
    "abandon_pilot_slot_wide": (1295, 660),
    "abandon_pilot_slot_right": (1385, 660),
    "island_archive": (600, 430),
    "island_rst": (850, 960),
    "end_turn": (252, 190),
}


def _platform_control(control: KnownWindowControl) -> KnownWindowControl:
    if os.name != "nt":
        return control
    override = _WINDOWS_CONTROL_OVERRIDES.get(control.name)
    if override is None:
        return control
    return KnownWindowControl(
        name=control.name,
        window_x=override[0],
        window_y=override[1],
        description=f"{control.description} (Windows calibrated)",
        settle_seconds=control.settle_seconds,
        hold_seconds=control.hold_seconds,
    )


def list_known_window_controls() -> dict[str, dict]:
    """Return calibrated controls keyed by canonical name."""
    return {
        name: _platform_control(control).to_dict()
        for name, control in KNOWN_WINDOW_CONTROLS.items()
    }


def find_title_menu_button_target(
    image_path: str | Path,
    *,
    row_index: int = 1,
) -> dict:
    """Find a title-screen menu row center from the actual window screenshot.

    ``row_index=1`` targets the second row, which is ``New Game`` on the title
    screen. The returned ``image_x``/``image_y`` are screenshot pixels; callers
    should scale them to the current window coordinate space before clicking.
    """
    try:
        from PIL import Image
    except Exception as exc:
        return {"status": "UNAVAILABLE", "error": f"PIL unavailable: {exc}"}

    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return {"status": "ERROR", "error": f"failed to open screenshot: {exc}"}

    width, height = image.size
    if width <= 0 or height <= 0:
        return {"status": "ERROR", "error": "empty screenshot"}

    pixels = image.load()
    x_limit = max(80, min(width, int(width * 0.28)))
    y_start = max(0, int(height * 0.10))
    y_stop = min(height, int(height * 0.48))
    min_dark_for_row = max(40, int(x_limit * 0.20))
    min_bright_for_row = 8

    row_hits: list[tuple[int, int, int]] = []
    for y in range(y_start, y_stop):
        dark = 0
        bright = 0
        for x in range(0, x_limit):
            r, g, b = pixels[x, y]
            if r <= 45 and g <= 45 and b <= 65:
                dark += 1
            if r >= 180 and g >= 180 and b >= 180:
                bright += 1
        if dark >= min_dark_for_row:
            row_hits.append((y, dark, bright))

    runs: list[dict] = []
    current: list[tuple[int, int, int]] = []
    last_y = None
    for hit in row_hits:
        y = hit[0]
        if last_y is None or y <= last_y + 1:
            current.append(hit)
        else:
            if current:
                runs.append(_summarize_title_menu_run(current, pixels, x_limit))
            current = [hit]
        last_y = y
    if current:
        runs.append(_summarize_title_menu_run(current, pixels, x_limit))

    candidates = [
        run
        for run in runs
        if run["height"] >= max(8, int(height * 0.008))
        and run["width"] >= max(90, int(width * 0.08))
    ]
    candidates.sort(key=lambda item: item["image_y"])
    effective_row_index = row_index
    if row_index == 1 and len(candidates) == 4:
        # A disabled Continue row can be too dim to classify as a menu button.
        # In that state the four detected rows are New Game, Options, Credits,
        # and Quit, so the New Game target is the first detected row.
        effective_row_index = 0
    if len(candidates) <= effective_row_index:
        return {
            "status": "NOT_FOUND",
            "reason": "not_enough_title_menu_rows",
            "row_index": row_index,
            "effective_row_index": effective_row_index,
            "candidate_count": len(candidates),
            "image_size": [width, height],
            "search_region": [0, y_start, x_limit, y_stop],
            "runs": runs[:8],
        }

    target = candidates[effective_row_index]
    return {
        "status": "OK",
        "row_index": row_index,
        "effective_row_index": effective_row_index,
        "image_x": int(round(target["image_x"])),
        "image_y": int(round(target["image_y"])),
        "image_size": [width, height],
        "search_region": [0, y_start, x_limit, y_stop],
        "target_row": target,
        "candidate_rows": candidates[:5],
    }


def _summarize_title_menu_run(
    rows: list[tuple[int, int, int]],
    pixels,
    x_limit: int,
) -> dict:
    min_y = rows[0][0]
    max_y = rows[-1][0]
    min_x = x_limit
    max_x = 0
    dark_total = 0
    bright_total = 0
    for y, dark, bright in rows:
        dark_total += dark
        bright_total += bright
        for x in range(0, x_limit):
            r, g, b = pixels[x, y]
            if r <= 45 and g <= 45 and b <= 65:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
    if min_x > max_x:
        min_x = 0
        max_x = 0
    return {
        "image_x": (min_x + max_x) / 2,
        "image_y": (min_y + max_y) / 2,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "width": max_x - min_x + 1,
        "height": max_y - min_y + 1,
        "dark": dark_total,
        "bright": bright_total,
    }


def click_title_new_game_dynamic(
    *,
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 1.0,
    hold_seconds: float = 0.3,
) -> dict:
    """Click the title-screen New Game row using live screenshot geometry."""
    bounds = _get_window_bounds(app_name)
    if bounds is None:
        return {
            "status": "ERROR",
            "error": "could not read app window bounds",
            "control": "title_new_game",
        }

    from src.capture.window import take_screenshot

    with tempfile.NamedTemporaryFile(
        prefix="itb_title_new_game_",
        suffix=".png",
        delete=False,
    ) as fh:
        screenshot_path = Path(fh.name)
    try:
        take_screenshot(screenshot_path, bounds=bounds)
        target = find_title_menu_button_target(screenshot_path, row_index=1)
    finally:
        try:
            screenshot_path.unlink()
        except OSError:
            pass

    if target.get("status") != "OK":
        target["control"] = "title_new_game"
        return target

    image_w, image_h = target["image_size"]
    scale_x = bounds["width"] / image_w if image_w else 1.0
    scale_y = bounds["height"] / image_h if image_h else 1.0
    window_x = int(round(target["image_x"] * scale_x))
    window_y = int(round(target["image_y"] * scale_y))
    description = "Title screen New Game (dynamic screenshot target)"

    if dry_run:
        return {
            "status": "DRY_RUN",
            "control": "title_new_game",
            "window_x": window_x,
            "window_y": window_y,
            "window_bounds": bounds,
            "target": target,
            "description": description,
        }

    result = click_window_point(
        window_x,
        window_y,
        description=description,
        app_name=app_name,
        dry_run=False,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    result["control"] = "title_new_game"
    result["dynamic_target"] = target
    result["coordinate_scale"] = {"x": scale_x, "y": scale_y}
    return result



def _pyautogui_click(x: int, y: int, *, hold_seconds: float = 0.3) -> dict:
    """Click a global screen point with PyAutoGUI, if available."""
    try:
        import pyautogui
    except Exception as exc:
        return {"status": "ERROR", "error": f"pyautogui unavailable: {exc}"}
    try:
        pyautogui.moveTo(int(x), int(y), duration=0.05)
        pyautogui.mouseDown(int(x), int(y))
        time.sleep(max(0.0, hold_seconds))
        pyautogui.mouseUp(int(x), int(y))
    except Exception as exc:
        return {"status": "ERROR", "error": f"pyautogui click failed: {exc}"}
    return {"status": "OK", "hold_seconds": hold_seconds}


def _applescript_click(
    x: int,
    y: int,
    *,
    app_name: str,
) -> dict:
    """Click a global screen point via System Events."""
    script = f'''
    tell application "{app_name}" to activate
    delay 0.05
    tell application "System Events"
        click at {{{x}, {y}}}
    end tell
    '''
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "ERROR", "error": f"osascript timed out: {exc}"}

    if proc.returncode != 0:
        return {
            "status": "ERROR",
            "error": proc.stderr.strip() or proc.stdout.strip() or "click failed",
        }
    return {"status": "OK"}


def _windows_sendinput_click(
    x: int,
    y: int,
    *,
    hold_seconds: float = 0.3,
    pre_click_seconds: float = 0.08,
) -> dict:
    """Click a global screen point with Win32 raw input.

    PyAutoGUI can report success while some Windows games ignore the generated
    mouse event. Into the Breach already needs raw scancodes for Escape, so use
    the same lower-level input path for calibrated clicks.
    """
    if os.name != "nt":
        return {"status": "SKIPPED", "reason": "not_windows"}
    try:
        from ctypes import wintypes

        INPUT_MOUSE = 0
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("union", INPUT_UNION),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        user32.SetCursorPos.restype = wintypes.BOOL
        user32.SendInput.argtypes = [
            wintypes.UINT,
            ctypes.POINTER(INPUT),
            ctypes.c_int,
        ]
        user32.SendInput.restype = wintypes.UINT

        if not user32.SetCursorPos(int(x), int(y)):
            return {
                "status": "ERROR",
                "error": f"SetCursorPos failed: WinError {ctypes.get_last_error()}",
            }
        if pre_click_seconds > 0:
            time.sleep(max(0.0, pre_click_seconds))

        down = INPUT(
            type=INPUT_MOUSE,
            union=INPUT_UNION(
                mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
            ),
        )
        sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        if sent != 1:
            return {
                "status": "ERROR",
                "error": (
                    f"SendInput mouse down sent {sent}/1 events; "
                    f"WinError {ctypes.get_last_error()}"
                ),
            }
        time.sleep(max(0.0, hold_seconds))
        up = INPUT(
            type=INPUT_MOUSE,
            union=INPUT_UNION(
                mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)
            ),
        )
        sent = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        if sent != 1:
            return {
                "status": "ERROR",
                "error": (
                    f"SendInput mouse up sent {sent}/1 events; "
                    f"WinError {ctypes.get_last_error()}"
                ),
            }
    except Exception as exc:
        return {"status": "ERROR", "error": f"win32 SendInput click failed: {exc}"}
    return {
        "status": "OK",
        "hold_seconds": hold_seconds,
        "pre_click_seconds": max(0.0, pre_click_seconds),
    }


def _get_window_bounds(app_name: str) -> dict | None:
    """Return the front window bounds for ``app_name`` via System Events."""
    if shutil.which("osascript") is None:
        try:
            from src.capture.detect_grid import find_game_window

            win = find_game_window()
        except Exception:
            return None
        return {
            "x": int(win.x),
            "y": int(win.y),
            "width": int(win.width),
            "height": int(win.height),
        }

    script = f'''
    tell application "{app_name}" to activate
    delay 0.05
    tell application "System Events"
        tell process "{app_name}"
            set frontmost to true
            set winPos to position of window 1
            set winSize to size of window 1
            return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
        end tell
    end tell
    '''
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        x, y, width, height = [
            int(part.strip()) for part in proc.stdout.strip().split(",", 3)
        ]
    except ValueError:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


def _windows_activate_app_window(app_name: str) -> dict:
    """Bring the matching Windows game window foreground before raw input."""
    if os.name != "nt":
        return {"status": "SKIPPED", "reason": "not_windows"}
    try:
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        enum_proc_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )
        user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL

        needle = str(app_name or "").lower()
        matches: list[tuple[int, str]] = []

        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if needle in title.lower():
                matches.append((int(hwnd), title))
                return False
            return True

        user32.EnumWindows(enum_proc_type(enum_proc), 0)
        if not matches:
            return {
                "status": "ERROR",
                "error": f"no visible window title matched {app_name!r}",
            }
        hwnd, title = matches[0]
        hwnd_obj = wintypes.HWND(hwnd)
        user32.ShowWindow(hwnd_obj, 9)  # SW_RESTORE
        foreground_ok = bool(user32.SetForegroundWindow(hwnd_obj))
        return {
            "status": "OK",
            "hwnd": hwnd,
            "title": title,
            "foreground_ok": foreground_ok,
            "win_error": ctypes.get_last_error() if not foreground_ok else 0,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": f"Windows foreground failed: {exc}"}


def click_screen_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
    hold_seconds: float = 0.3,
    pre_click_seconds: float | None = None,
) -> dict:
    """Activate the game and click a screen-coordinate point via AppleScript."""
    x = int(x)
    y = int(y)
    if dry_run:
        return {
            "status": "DRY_RUN",
            "x": x,
            "y": y,
            "description": description,
        }

    focus_result = None
    if os.name == "nt":
        focus_result = _windows_activate_app_window(app_name)
        time.sleep(0.05)

    if os.name == "nt":
        click_result = _windows_sendinput_click(
            x,
            y,
            hold_seconds=hold_seconds,
            pre_click_seconds=0.08 if pre_click_seconds is None else pre_click_seconds,
        )
        backend = "win32_sendinput"
    else:
        click_result = _pyautogui_click(x, y, hold_seconds=hold_seconds)
        backend = "pyautogui"
    fallback_error = None
    if click_result.get("status") != "OK":
        fallback_error = click_result.get("error")
        click_result = _pyautogui_click(x, y, hold_seconds=hold_seconds)
        backend = "pyautogui"
    if click_result.get("status") != "OK" and os.name != "nt":
        fallback_error = fallback_error or click_result.get("error")
        click_result = _applescript_click(x, y, app_name=app_name)
        backend = "applescript"

    if click_result.get("status") != "OK":
        return {
            "status": "ERROR",
            "error": click_result.get("error", "click failed"),
            "pyautogui_error": fallback_error,
            "x": x,
            "y": y,
            "description": description,
        }

    if settle_seconds > 0:
        time.sleep(settle_seconds)

    return {
        "status": "OK",
        "x": x,
        "y": y,
        "description": description,
        "backend": backend,
        "hold_seconds": click_result.get("hold_seconds"),
        "pre_click_seconds": click_result.get("pre_click_seconds"),
        "focus": focus_result,
    }


def press_key(
    key: str,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.08,
) -> dict:
    """Activate the game and press a trusted non-combat UI key."""
    key = str(key)
    normalized_key = key.strip().lower()
    if dry_run:
        return {"status": "DRY_RUN", "key": key, "description": description}
    if os.name == "nt":
        windows_scan_codes = {
            "esc": ("esc", 0x01),
            "escape": ("esc", 0x01),
            "enter": ("enter", 0x1C),
            "return": ("enter", 0x1C),
            "space": ("space", 0x39),
        }
        scan_code = windows_scan_codes.get(normalized_key)
        if scan_code is not None:
            canonical_key, windows_scan_code = scan_code
            focus_result = _windows_activate_app_window(app_name)
            time.sleep(0.05)
            result = _windows_press_scancode(
                windows_scan_code,
                key=canonical_key,
                description=description,
                settle_seconds=settle_seconds,
            )
            result["focus"] = focus_result
            return result
    if os.name == "nt" and normalized_key in {"esc", "escape"}:
        focus_result = _windows_activate_app_window(app_name)
        time.sleep(0.05)
        result = _windows_press_escape(
            description=description,
            settle_seconds=settle_seconds,
        )
        result["focus"] = focus_result
        return result
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        pass
    try:
        import pyautogui

        pyautogui.press(key)
    except Exception as exc:
        return {"status": "ERROR", "error": f"pyautogui key failed: {exc}"}
    if settle_seconds > 0:
        time.sleep(settle_seconds)
    return {
        "status": "OK",
        "key": key,
        "description": description,
        "backend": "pyautogui",
    }


def _windows_press_escape(
    *,
    description: str = "",
    settle_seconds: float = 0.08,
) -> dict:
    """Send Escape as a raw Windows scancode.

    Into the Breach on Windows can ignore PyAutoGUI's virtual-key style Escape,
    while a direct scancode SendInput toggles the pause menu reliably.
    """
    return _windows_press_scancode(
        0x01,
        key="esc",
        description=description,
        settle_seconds=settle_seconds,
    )


def _windows_press_scancode(
    scan_code: int,
    *,
    key: str,
    description: str = "",
    settle_seconds: float = 0.08,
) -> dict:
    """Send a keyboard scancode through Win32 raw input."""
    try:
        from ctypes import wintypes

        INPUT_KEYBOARD = 1
        KEYEVENTF_SCANCODE = 0x0008
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("union", INPUT_UNION),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SendInput.argtypes = [
            wintypes.UINT,
            ctypes.POINTER(INPUT),
            ctypes.c_int,
        ]
        user32.SendInput.restype = wintypes.UINT

        inputs = (INPUT * 2)(
            INPUT(
                type=INPUT_KEYBOARD,
                union=INPUT_UNION(
                    ki=KEYBDINPUT(0, scan_code, KEYEVENTF_SCANCODE, 0, 0)
                ),
            ),
            INPUT(
                type=INPUT_KEYBOARD,
                union=INPUT_UNION(
                    ki=KEYBDINPUT(
                        0,
                        scan_code,
                        KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP,
                        0,
                        0,
                    )
                ),
            ),
        )
        sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        if sent != 2:
            return {
                "status": "ERROR",
                "error": (
                    f"SendInput sent {sent}/2 events; "
                    f"WinError {ctypes.get_last_error()}"
                ),
                "key": key,
                "description": description,
                "backend": "win32_sendinput",
            }
    except Exception as exc:
        return {
            "status": "ERROR",
            "error": f"win32 SendInput key failed: {exc}",
            "key": key,
            "description": description,
            "backend": "win32_sendinput",
        }
    if settle_seconds > 0:
        time.sleep(settle_seconds)
    return {
        "status": "OK",
        "key": key,
        "description": description,
        "backend": "win32_sendinput",
    }


def click_window_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
    hold_seconds: float = 0.3,
) -> dict:
    """Click a point relative to the game window's top-left corner."""
    x = int(x)
    y = int(y)
    if dry_run:
        return {
            "status": "DRY_RUN",
            "window_x": x,
            "window_y": y,
            "description": description,
        }

    bounds = _get_window_bounds(app_name)
    if bounds is None:
        return {
            "status": "ERROR",
            "error": "could not read app window bounds",
            "window_x": x,
            "window_y": y,
            "description": description,
        }

    screen_x = int(bounds["x"] + x)
    screen_y = int(bounds["y"] + y)
    result = click_screen_point(
        screen_x,
        screen_y,
        description=description,
        app_name=app_name,
        dry_run=False,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    result["window_x"] = x
    result["window_y"] = y
    result["window_bounds"] = bounds
    return result


def click_known_window_control(
    name: str,
    *,
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float | None = None,
    hold_seconds: float | None = None,
) -> dict:
    """Click one of the calibrated, trusted game-window controls."""
    key = _normalize_control_name(name)
    control = KNOWN_WINDOW_CONTROLS.get(key)
    if control is None:
        return {
            "status": "ERROR",
            "error": f"unknown control: {name}",
            "known_controls": sorted(KNOWN_WINDOW_CONTROLS),
        }
    if key == "title_new_game":
        return click_title_new_game_dynamic(
            app_name=app_name,
            dry_run=dry_run,
            settle_seconds=(
                control.settle_seconds
                if settle_seconds is None else float(settle_seconds)
            ),
            hold_seconds=(
                control.hold_seconds
                if hold_seconds is None else float(hold_seconds)
            ),
        )
    control = _platform_control(control)
    result = click_window_point(
        control.window_x,
        control.window_y,
        description=control.description,
        app_name=app_name,
        dry_run=dry_run,
        settle_seconds=(
            control.settle_seconds
            if settle_seconds is None else float(settle_seconds)
        ),
        hold_seconds=(
            control.hold_seconds
            if hold_seconds is None else float(hold_seconds)
        ),
    )
    result["control"] = control.name
    return result


def click_known_window_sequence(
    names: list[str],
    *,
    app_name: str = "Into the Breach",
    dry_run: bool = False,
) -> dict:
    """Click several calibrated controls using one window-bounds lookup."""
    requested = [str(name).strip() for name in names if str(name).strip()]
    if not requested:
        return {"status": "ERROR", "error": "no controls requested"}

    controls: list[KnownWindowControl] = []
    for name in requested:
        key = _normalize_control_name(name)
        control = KNOWN_WINDOW_CONTROLS.get(key)
        if control is None:
            return {
                "status": "ERROR",
                "error": f"unknown control: {name}",
                "known_controls": sorted(KNOWN_WINDOW_CONTROLS),
            }
        controls.append(_platform_control(control))

    if dry_run:
        return {
            "status": "DRY_RUN",
            "sequence": [control.to_dict() for control in controls],
        }

    bounds = _get_window_bounds(app_name)
    if bounds is None:
        return {
            "status": "ERROR",
            "error": "could not read app window bounds",
            "controls": [control.name for control in controls],
        }

    results = []
    for control in controls:
        screen_x = int(bounds["x"] + control.window_x)
        screen_y = int(bounds["y"] + control.window_y)
        result = click_screen_point(
            screen_x,
            screen_y,
            description=control.description,
            app_name=app_name,
            dry_run=False,
            settle_seconds=control.settle_seconds,
            hold_seconds=control.hold_seconds,
        )
        result["control"] = control.name
        result["window_x"] = control.window_x
        result["window_y"] = control.window_y
        result["window_bounds"] = bounds
        results.append(result)
        if result.get("status") != "OK":
            return {
                "status": "ERROR",
                "error": result.get("error", "click failed"),
                "controls": [control.name for control in controls],
                "completed": results,
                "window_bounds": bounds,
            }

    return {
        "status": "OK",
        "controls": [control.name for control in controls],
        "completed": results,
        "window_bounds": bounds,
    }
