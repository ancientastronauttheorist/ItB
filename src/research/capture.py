"""MCP capture-plan builders for Phase 2 tooltip research.

Python can't itself drive the ``mcp__computer-use__*`` tools — those
are invoked by the harness (Claude) each round. So this module's
shape mirrors ``src/control/executor.py``: we compute the full plan
(a list of batch actions + a list of zoom crop rectangles) and hand
it back. The caller dispatches the batch, then zooms into each
region for Vision extraction.

The plan builders are pure functions. They read
``data/ui_regions.json`` (calibrated in #P2-1) and the current
Quartz window bounds via ``src.capture.detect_grid.find_game_window``
so the regions scale with the live window.

Three capture modes:

- **unit** — click a mech or enemy on the board. Yields name_tag +
  unit_status crops. For enemies, that's all — ITB's enemy panel
  doesn't surface a weapon preview. For mechs, chain a subsequent
  ``build_weapon_hover_plan`` per weapon slot.
- **weapon** — hover a mech weapon icon to pop the weapon_preview
  panel (the AOE mini-board). This is the regression-harness input
  the design doc highlighted.
- **terrain** — hover a tile (no click) to pop the terrain tooltip
  in the bottom-right region.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.capture.detect_grid import WindowInfo, find_game_window

UI_REGIONS_PATH = Path(__file__).parent.parent.parent / "data" / "ui_regions.json"


# ── data loading ──────────────────────────────────────────────────────────────


@dataclass
class UiRegions:
    """In-memory form of ``data/ui_regions.json``.

    ``regions`` keys (name_tag, unit_status, weapon_preview, terrain_tooltip)
    map to a ``(x0, y0, x1, y1)`` tuple in MCP screenshot coordinate space,
    already scaled for the current window. ``neutral_hover`` is the
    pre-click dismiss target — also scaled.
    """
    regions: dict[str, tuple[int, int, int, int]]
    neutral_hover: tuple[int, int]
    reference_window: WindowInfo
    current_window: WindowInfo


def load_ui_regions(path: Path | None = None) -> dict:
    """Load the raw JSON at ``data/ui_regions.json``.

    Kept separate from ``resolve_ui_regions`` so tests can pass in
    hand-crafted region dicts without touching the filesystem.
    """
    p = path or UI_REGIONS_PATH
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        if path is not None:
            raise

    rel = UI_REGIONS_PATH.relative_to(UI_REGIONS_PATH.parent.parent.parent).as_posix()
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=UI_REGIONS_PATH.parent.parent.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def resolve_ui_regions(
    raw: dict,
    current_window: WindowInfo | None = None,
) -> UiRegions:
    """Scale the calibrated regions to the current game-window bounds.

    The reference calibration assumed window at (200, 137) size 1280x748.
    If the live window has moved or resized, each region is translated
    and scaled the same way ``grid_from_window`` handles tile coords.

    Args:
        raw: Output of ``load_ui_regions``.
        current_window: Override for tests. If None, calls
            ``find_game_window()`` and raises if the window isn't up.

    Returns:
        UiRegions with bounds in current MCP coord space.
    """
    ref = raw["reference_window"]
    ref_win = WindowInfo(
        x=ref["x"], y=ref["y"],
        width=ref["width"], height=ref["height"],
    )
    cur = current_window
    if cur is None:
        cur = find_game_window()
        if cur is None:
            raise RuntimeError(
                "Game window not found — research capture requires "
                "Into the Breach to be running and visible."
            )

    sx = cur.width / ref_win.width
    sy = cur.height / ref_win.height
    dx = cur.x - ref_win.x
    dy = cur.y - ref_win.y

    def scale(x: int, y: int) -> tuple[int, int]:
        # Anchor the scale to the reference-window origin, then translate.
        rx = ref_win.x + (x - ref_win.x) * sx
        ry = ref_win.y + (y - ref_win.y) * sy
        return (int(round(rx + dx)), int(round(ry + dy)))

    regions: dict[str, tuple[int, int, int, int]] = {}
    for name, data in raw["regions"].items():
        x0, y0, x1, y1 = data["bounds"]
        rx0, ry0 = scale(x0, y0)
        rx1, ry1 = scale(x1, y1)
        regions[name] = (rx0, ry0, rx1, ry1)

    nh = raw["neutral_hover"]["coordinate"]
    neutral_hover = _resolve_neutral_hover(scale(nh[0], nh[1]), cur)

    return UiRegions(
        regions=regions,
        neutral_hover=neutral_hover,
        reference_window=ref_win,
        current_window=cur,
    )


def _resolve_neutral_hover(
    scaled: tuple[int, int],
    cur: WindowInfo,
) -> tuple[int, int]:
    """Return a safe neutral_hover MCP coord.

    The calibrated neutral_hover point ``(1100, 100)`` sits 37px ABOVE
    the reference window's top edge (win.y=137). That's fine when the
    live window is near the reference origin — y=100 is still on-screen.
    But when the window moves up (e.g. user repositions it or macOS
    hides the menu bar), the scaled y can go negative and MCP rejects
    the batch: ``coordinate must be a tuple of non-negative numbers``.

    Fix: if the scaled point would land off-screen (negative x or y),
    snap to a genuinely-safe spot just inside the top edge of the
    current window, horizontally centered. Still away from interactive
    UI — name tag, weapon rail, and terrain tooltip all live in the
    lower half — but guaranteed on-screen and still effective at
    dismissing residual hover state.
    """
    nh_x, nh_y = scaled
    if nh_x < 0 or nh_y < 0:
        margin = 5
        nh_x = int(round(cur.x + cur.width / 2))
        nh_y = max(0, cur.y + margin)
    return (nh_x, nh_y)


# ── plan builders ────────────────────────────────────────────────────────────


def build_unit_capture_plan(
    target_mcp: tuple[int, int],
    ui: UiRegions,
    crops: tuple[str, ...] = ("name_tag", "unit_status"),
    dismiss_wait_s: float = 0.4,
    post_click_wait_s: float = 0.8,
) -> dict:
    """Return a plan dict to select a unit and capture its panels.

    The caller dispatches ``plan["batch"]`` via
    ``mcp__computer-use__computer_batch``, then iterates ``plan["crops"]``
    calling ``mcp__computer-use__zoom`` on each rect to grab the image
    for Vision. A final screenshot lives at the end of the batch so
    the zoom regions have a fresh base image to index into.

    Args:
        target_mcp: MCP coord of the tile to click (grid_to_mcp output).
        ui: Resolved UI regions for the current window.
        crops: Subset of region names to return crops for. Defaults to
            ``name_tag`` + ``unit_status``; pass the full tuple including
            ``weapon_preview`` only when the caller then chains a
            ``build_weapon_hover_plan`` first.
        dismiss_wait_s: Dwell time after the neutral-hover move so any
            residual tooltip fades before the click fires.
        post_click_wait_s: Dwell time after the click so the panel
            animation settles before the screenshot.

    Returns:
        ``{"batch": [...], "crops": [{"name": str, "region": (x0,y0,x1,y1)}]}``.
    """
    batch = [
        {"action": "mouse_move", "coordinate": list(ui.neutral_hover)},
        {"action": "wait", "duration": dismiss_wait_s},
        {"action": "left_click", "coordinate": list(target_mcp)},
        {"action": "wait", "duration": post_click_wait_s},
        {"action": "screenshot"},
    ]
    crop_rects = [
        {"name": name, "region": ui.regions[name]}
        for name in crops
        if name in ui.regions
    ]
    return {"batch": batch, "crops": crop_rects}


def build_weapon_hover_plan(
    weapon_icon_mcp: tuple[int, int],
    ui: UiRegions,
    hover_wait_s: float = 1.2,
) -> dict:
    """Return a plan dict to hover a weapon icon and capture the preview panel.

    Assumes the mech is already selected (so the weapon icons are
    visible). Hovering pops the weapon_preview panel; the batch
    finishes with a screenshot, and the returned crop names the
    ``weapon_preview`` region for Vision.

    Args:
        weapon_icon_mcp: MCP coord of the weapon icon to hover.
        ui: Resolved UI regions for the current window.
        hover_wait_s: Dwell time after the hover so the panel fully
            materializes (measured ~1s for the mini-board to render
            all AOE dots in the reference build).
    """
    batch = [
        {"action": "mouse_move", "coordinate": list(weapon_icon_mcp)},
        {"action": "wait", "duration": hover_wait_s},
        {"action": "screenshot"},
    ]
    crops = [{"name": "weapon_preview", "region": ui.regions["weapon_preview"]}]
    return {"batch": batch, "crops": crops}


def build_weapon_probe_plan(
    target_mcp: tuple[int, int],
    weapon_icon_mcp: tuple[int, int],
    ui: UiRegions,
    dismiss_wait_s: float = 0.4,
    post_click_wait_s: float = 0.8,
    hover_wait_s: float = 1.2,
) -> dict:
    """Return a plan to select a mech and capture a single weapon preview.

    Composes ``build_unit_capture_plan`` and ``build_weapon_hover_plan``
    into one batch — the mech has to be selected before its weapon
    rail is interactive, and doing both in a single dispatch spares
    the harness a round-trip to re-screenshot between steps.

    Sequence: neutral dismiss → click mech → wait for panel → hover
    the weapon icon → wait for preview → screenshot. One crop,
    ``weapon_preview``, which is what the comparator consumes.
    """
    batch = [
        {"action": "mouse_move", "coordinate": list(ui.neutral_hover)},
        {"action": "wait", "duration": dismiss_wait_s},
        {"action": "left_click", "coordinate": list(target_mcp)},
        {"action": "wait", "duration": post_click_wait_s},
        {"action": "mouse_move", "coordinate": list(weapon_icon_mcp)},
        {"action": "wait", "duration": hover_wait_s},
        {"action": "screenshot"},
    ]
    crops = [{"name": "weapon_preview", "region": ui.regions["weapon_preview"]}]
    return {"batch": batch, "crops": crops}


def build_terrain_hover_plan(
    tile_mcp: tuple[int, int],
    ui: UiRegions,
    hover_wait_s: float = 0.6,
) -> dict:
    """Return a plan dict to hover a tile and capture the terrain tooltip.

    Distinct from ``build_unit_capture_plan`` — no click, no neutral
    dismiss. The terrain tooltip appears on raw hover in the bottom-right
    panel, including when a unit occupies the tile (the unit's status
    effects surface there too).
    """
    batch = [
        {"action": "mouse_move", "coordinate": list(tile_mcp)},
        {"action": "wait", "duration": hover_wait_s},
        {"action": "screenshot"},
    ]
    crops = [{"name": "terrain_tooltip", "region": ui.regions["terrain_tooltip"]}]
    return {"batch": batch, "crops": crops}


# ── convenience: mech weapon-icon positions ──────────────────────────────────

# Weapon icons live in a horizontal rail under the name tag at the
# calibrated positions below (for the reference window). The leftmost
# slot is the mech portrait (not a weapon); the next two slots are
# Prime / Secondary weapons.
_REF_WEAPON_ICON_CENTERS: tuple[tuple[int, int], ...] = (
    (316, 670),   # slot 1 — secondary / repair icon
    (388, 670),   # slot 2 — prime weapon
)


# Number of probeable weapon-icon slots in the mech UI rail. The
# auto-enqueue site (``cmd_read``) uses this to avoid loading UiRegions
# (which needs a live game window) just to count slots.
WEAPON_SLOT_COUNT: int = len(_REF_WEAPON_ICON_CENTERS)


# Subset of ``range(WEAPON_SLOT_COUNT)`` that auto-enqueue should
# actually probe. Slot 0 is the Repair icon on every Rift Walkers
# mech: hovering it pops a "Mech Repair" tooltip that renders in a
# different region than the calibrated weapon_preview crop, so those
# probes always come back with 0 confidence. Slot 1 is the prime
# weapon on every squad.
#
# Squads with a real secondary weapon in slot 0 (Rusting Hulks, Zenith
# Guard, etc.) will need this tuple expanded — at that point the
# preview crop may also need per-slot tuning. For manual one-off
# probing, ``research_probe_mech <tile> 0`` still works.
PROBEABLE_WEAPON_SLOTS: tuple[int, ...] = (1,)


def weapon_icon_positions(ui: UiRegions) -> list[tuple[int, int]]:
    """Scaled MCP positions of the weapon icons in the mech UI rail.

    The exact slot count depends on the mech (some have 1 active
    weapon + Repair, some have 2 actives + Repair). The caller loops
    these positions and asks Vision to name each; empty/passive slots
    return low-confidence and are dropped.
    """
    ref = ui.reference_window
    cur = ui.current_window
    sx = cur.width / ref.width
    sy = cur.height / ref.height
    out: list[tuple[int, int]] = []
    for x, y in _REF_WEAPON_ICON_CENTERS:
        rx = ref.x + (x - ref.x) * sx + (cur.x - ref.x)
        ry = ref.y + (y - ref.y) * sy + (cur.y - ref.y)
        out.append((int(round(rx)), int(round(ry))))
    return out
