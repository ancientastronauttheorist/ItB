"""Phase 2 #P2-3 capture-plan builder tests.

The plan builders are pure — they compute MCP coordinates and batch
action lists without touching the live game. We verify:

1. ``data/ui_regions.json`` round-trips cleanly through ``load_ui_regions``.
2. ``resolve_ui_regions`` is a no-op when the current window matches the
   reference, and scales/translates correctly when it doesn't.
3. Each plan builder emits the expected MCP action sequence and the
   correct crop region names.
"""

from __future__ import annotations

from src.capture.detect_grid import WindowInfo
from src.research import capture


REF_WINDOW = WindowInfo(x=200, y=137, width=1280, height=748)


def _raw_regions() -> dict:
    return {
        "reference_window": {
            "x": 200, "y": 137, "width": 1280, "height": 748,
        },
        "regions": {
            "name_tag": {"bounds": [178, 558, 410, 603]},
            "unit_status": {"bounds": [178, 618, 442, 728]},
            "weapon_preview": {"bounds": [480, 355, 610, 720]},
            "terrain_tooltip": {"bounds": [980, 635, 1225, 725]},
        },
        "neutral_hover": {"coordinate": [1100, 100]},
    }


# ── ui_regions.json on-disk compatibility ────────────────────────────────────


def test_real_ui_regions_json_loads_and_resolves():
    raw = capture.load_ui_regions()
    ui = capture.resolve_ui_regions(raw, current_window=REF_WINDOW)
    assert set(ui.regions.keys()) >= {
        "name_tag", "unit_status", "weapon_preview", "terrain_tooltip",
    }


# ── resolve_ui_regions scaling ───────────────────────────────────────────────


def test_resolve_is_noop_when_current_window_matches_reference():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    assert ui.regions["name_tag"] == (178, 558, 410, 603)
    assert ui.regions["weapon_preview"] == (480, 355, 610, 720)
    assert ui.neutral_hover == (1100, 100)


def test_resolve_translates_when_window_moves():
    moved = WindowInfo(x=500, y=337, width=1280, height=748)  # shifted +300,+200
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=moved)
    # Pure translation — same scale — every coord shifts by (+300, +200).
    assert ui.regions["name_tag"] == (178 + 300, 558 + 200, 410 + 300, 603 + 200)
    assert ui.neutral_hover == (1100 + 300, 100 + 200)


def test_resolve_scales_when_window_resizes():
    # Double size, anchored at same origin. Bounds scale proportionally.
    big = WindowInfo(x=200, y=137, width=2560, height=1496)
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=big)
    # At the reference origin (200, 137) the scaling anchor point is
    # zero. Points offset from the anchor double.
    x0 = 200 + (178 - 200) * 2  # = 156
    y0 = 137 + (558 - 137) * 2  # = 979
    x1 = 200 + (410 - 200) * 2  # = 620
    y1 = 137 + (603 - 137) * 2  # = 1069
    assert ui.regions["name_tag"] == (x0, y0, x1, y1)


# ── plan builders ────────────────────────────────────────────────────────────


def test_unit_capture_plan_shape_for_enemy():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    plan = capture.build_unit_capture_plan(target_mcp=(740, 366), ui=ui)
    actions = [a["action"] for a in plan["batch"]]
    # Neutral dismiss, wait, click target, wait, screenshot.
    assert actions == ["mouse_move", "wait", "left_click", "wait", "screenshot"]
    # First mouse_move goes to neutral_hover; click goes to target.
    assert plan["batch"][0]["coordinate"] == [1100, 100]
    assert plan["batch"][2]["coordinate"] == [740, 366]
    # Default crops: name_tag + unit_status (enemy case — no weapon preview).
    names = [c["name"] for c in plan["crops"]]
    assert names == ["name_tag", "unit_status"]
    # Regions carry the calibrated bounds.
    assert plan["crops"][0]["region"] == (178, 558, 410, 603)


def test_unit_capture_plan_respects_custom_crop_list():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    plan = capture.build_unit_capture_plan(
        target_mcp=(500, 500), ui=ui,
        crops=("name_tag",),
    )
    assert [c["name"] for c in plan["crops"]] == ["name_tag"]


def test_unit_capture_plan_ignores_unknown_crop_names():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    plan = capture.build_unit_capture_plan(
        target_mcp=(500, 500), ui=ui,
        crops=("name_tag", "not_a_real_region"),
    )
    # Unknown names silently dropped — a forward-compat seam for new
    # regions that aren't calibrated yet.
    assert [c["name"] for c in plan["crops"]] == ["name_tag"]


def test_weapon_hover_plan_shape():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    plan = capture.build_weapon_hover_plan(weapon_icon_mcp=(388, 670), ui=ui)
    actions = [a["action"] for a in plan["batch"]]
    assert actions == ["mouse_move", "wait", "screenshot"]
    assert plan["batch"][0]["coordinate"] == [388, 670]
    assert [c["name"] for c in plan["crops"]] == ["weapon_preview"]
    assert plan["crops"][0]["region"] == (480, 355, 610, 720)


def test_terrain_hover_plan_shape():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    plan = capture.build_terrain_hover_plan(tile_mcp=(694, 400), ui=ui)
    actions = [a["action"] for a in plan["batch"]]
    assert actions == ["mouse_move", "wait", "screenshot"]
    assert [c["name"] for c in plan["crops"]] == ["terrain_tooltip"]


def test_weapon_icon_positions_returns_two_slots_at_reference():
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=REF_WINDOW)
    slots = capture.weapon_icon_positions(ui)
    # Reference calibration: two weapon slots in the rail.
    assert len(slots) == 2
    assert slots[0] == (316, 670)
    assert slots[1] == (388, 670)


def test_weapon_icon_positions_translates_with_window_move():
    moved = WindowInfo(x=500, y=337, width=1280, height=748)
    ui = capture.resolve_ui_regions(_raw_regions(), current_window=moved)
    slots = capture.weapon_icon_positions(ui)
    assert slots[0] == (316 + 300, 670 + 200)
    assert slots[1] == (388 + 300, 670 + 200)
