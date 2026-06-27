from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lightning_war_fast_walkthrough.py"
SPEC = importlib.util.spec_from_file_location("lightning_war_fast_walkthrough", SCRIPT)
fast = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = fast
SPEC.loader.exec_module(fast)


def test_terminal_pause_like_result_screen_clicks_reward_continue():
    visible = {
        "status": "OK",
        "visible_ui": "pause_menu",
        "recommended_control": "menu_continue",
        "dark_overlay_fraction": 0.95,
        "scores": {
            "pause_menu": {"score": 0.19},
            "perfect_reward_choice": {"score": 0.66},
        },
        "bridge_refine_snapshot": {
            "status": "OK",
            "in_active_mission": False,
            "active_mechs": 0,
        },
    }

    assert fast.clear_control_for_visible_ui(visible) == "reward_continue"


def test_terminal_pause_like_result_with_dialogue_clicks_reward_continue():
    visible = {
        "status": "OK",
        "visible_ui": "pause_menu",
        "recommended_control": "menu_continue",
        "dark_overlay_fraction": 0.95,
        "scores": {
            "pause_menu": {"score": 0.19},
            "mission_preview_dialogue": {"score": 0.77},
        },
        "bridge_refine_snapshot": {
            "status": "OK",
            "in_active_mission": False,
            "active_mechs": 0,
        },
    }

    assert fast.clear_control_for_visible_ui(visible) == "reward_continue"


def test_no_bridge_pause_like_result_with_dialogue_clicks_reward_continue():
    visible = {
        "status": "OK",
        "visible_ui": "pause_menu",
        "recommended_control": "menu_continue",
        "dark_overlay_fraction": 0.95,
        "scores": {
            "pause_menu": {"score": 0.19},
            "mission_preview_dialogue": {"score": 0.77},
            "perfect_reward_choice": {"score": 0.66},
        },
        "bridge_refine_snapshot": {
            "status": "NO_BRIDGE",
        },
    }

    assert fast.clear_control_for_visible_ui(visible) == "reward_continue"
