"""Small macOS click helpers for trusted UI buttons.

This module is intentionally narrow: it clicks already-calibrated screen
coordinates such as the End Turn button. Combat tile clicks still flow through
the bridge or Computer Use planners.
"""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
import shutil


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
        window_y=58,
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
    "title_continue": KnownWindowControl(
        name="title_continue",
        window_x=170,
        window_y=251,
        description="Title screen Continue",
        settle_seconds=1.0,
    ),
    "setup_start": KnownWindowControl(
        name="setup_start",
        window_x=1005,
        window_y=96,
        description="New-run setup Start",
        settle_seconds=1.0,
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
        settle_seconds=0.7,
    ),
    "dialogue_textbox": KnownWindowControl(
        name="dialogue_textbox",
        window_x=250,
        window_y=205,
        description="Advisor dialogue text box dismiss",
        settle_seconds=0.25,
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
        window_y=518,
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
    "leave_confirm_no": KnownWindowControl(
        name="leave_confirm_no",
        window_x=713,
        window_y=444,
        description="Leave Island confirmation No",
        settle_seconds=0.25,
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
    "abandon_pilot_slot": KnownWindowControl(
        name="abandon_pilot_slot",
        window_x=490,
        window_y=329,
        description="Abandon Timeline pilot selection",
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
    "leave_no": "leave_confirm_no",
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


def list_known_window_controls() -> dict[str, dict]:
    """Return calibrated controls keyed by canonical name."""
    return {name: control.to_dict() for name, control in KNOWN_WINDOW_CONTROLS.items()}


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


def click_screen_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
    hold_seconds: float = 0.3,
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

    click_result = _pyautogui_click(x, y, hold_seconds=hold_seconds)
    backend = "pyautogui"
    fallback_error = None
    if click_result.get("status") != "OK":
        fallback_error = click_result.get("error")
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
    if dry_run:
        return {"status": "DRY_RUN", "key": key, "description": description}
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
        controls.append(control)

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
