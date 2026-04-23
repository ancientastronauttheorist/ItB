# grid_to_mcp calibration broken — ROOT CAUSE FOUND (2026-04-23)

## TL;DR

Calibration in `src/control/executor.py::grid_to_mcp` was wrong from the
start. 2026-04-07's "calibration" was off by **Y step 26% too large
(34.57 vs 27.5) and Y origin ~187 px high**. `auto_turn` (Lua bridge,
no MCP clicks) masked the bug for 12 days. First real use of
`click_action` on 2026-04-11 failed 50% immediately and was silently
abandoned for `auto_turn`.

Fixed in PR #7 follow-up commit.

## The fix

Three code changes to `src/control/executor.py`:

### 1. Grid origin + step constants

```
_H8_WIN_REL_X:  494.0 → 475.0
_H8_WIN_REL_Y:   56.0 → 243.0
_STEP_X:        46.21 → 50.0
_STEP_Y:        34.57 → 27.5
```

These reproduce `data/grid_reference.json`'s measured corners exactly
at window (215, 32). Empirically verified by hovering at the new
`grid_to_mcp(F5) = (740, 412)` and seeing the game's "Water Tile"
tooltip — correct terrain for F5 under a flying mech.

Derivation (from grid_reference.json corners):
- `H8_WIN_REL = (690-215, 275-32) = (475, 243)`
- `step_x = (H1_x - H8_x)/7 = 50.0`
- `step_y = (A1_y - H8_y)/14 = (660-275)/14 = 27.5`

### 2. Mech-select sprite offset

`plan_single_mech` now clicks the mech's **sprite position** (tile
center - 150 px in Y), not the tile center. For flying mechs over
water, clicking the tile hits the water tile but not the mech
hovering above it. The sprite is ~150 px above the tile center and is
visually always on the mech's body. Empirically confirmed:
`(740, 412)` click highlighted the F5 water tile but did not select
the JetMech; `(740, 262)` click selected the JetMech.

### 3. Weapon-slot UI offsets

`_UI_WEAPON_SLOT_1 = (191, 528) → (181, 553)`
`_UI_WEAPON_SLOT_2 = (255, 528) → (245, 553)`
`_UI_REPAIR_BUTTON = (111, 528) → (105, 553)`

The old Y (528) was off by 25 px. Empirically verified weapon icon
center is at image (396, 585) for this squad; clicking it armed
Aerial Bombs and showed the weapon tooltip. The (181, 553)
window-relative offset + window (215, 32) = (396, 585).

## Residual issue: target-tile clicks sometimes miss due to sprite overlap

**Not fixed in this PR.** When a dash weapon targets a tile that sits
visually beneath a large building sprite, the click's pixel hit-test
resolves to the BUILDING rather than the tile underneath. Example
this session: JetMech dash targeting E4 at (740, 468) — E4 is empty
ground per bridge state, but the F7 / F6 building column renders a
sprite that visually overlaps E4. Clicking (740, 468) shows
"Civilian Building" tooltip and cancels the armed weapon.

This is a known limitation of isometric pixel-based click testing.
Possible fixes:
- **Click offset per tile based on surrounding buildings** — expensive
  to compute, brittle
- **Target alternate tile in the same dash path** — Aerial Bombs
  tracks from start to end; any valid intermediate also works
- **Use a "click nearest valid orange highlight" strategy** — requires
  OCR / color detection on the active screen
- **Fall back to a different weapon/plan if target is visually
  occluded** — the solver doesn't know about sprite overlap

Safe for follow-up. The core calibration fix unblocks the happy path
(mech on clear terrain, target on clear terrain).

## Empirical verification checklist

Once this fix is merged, the user should verify in a live session:

1. `python3 tile_hover.py F5` emits `(740, 412)` at window (215, 32)
2. `mouse_move` to `(740, 412)` shows the expected F5 terrain tooltip
3. `mouse_move` to `(740, 262)` shows the Jet Mech's tooltip or
   selects the mech on click
4. `game_loop.py click_action 0` emits sprite-offset selects, correct
   weapon coord, correct target tile
5. At least ONE complete dispatch (select → arm → click target) on a
   board where the target is NOT occluded by a building sprite
   completes without `click_miss` in `verify_action`

## Git archaeology notes (from sibling agent)

- 2026-04-07 `9e998be`: the "calibration" commit that introduced the
  wrong constants. Corner-hover was verified for CURSOR position
  but not for MECH SELECTION — the two are not equivalent under an
  incorrect formula.
- 2026-04-10 `a9d567e`: MCP click rewrite, `click_action` introduced
  with the broken constants
- 2026-04-11: first live use, 50% `click_miss`, silently abandoned
- 2026-04-12 onward: all runs used `auto_turn` (Lua bridge) → bug
  never re-exercised until 2026-04-23

No code changes to `grid_to_mcp` at any point after `9e998be`. The
breakage was always latent, not a regression.
