# Investigation: grid_to_mcp broken for current display setup

## Symptom

2026-04-23 live play session on a Pinnacle Frozen Plains mission:
every tile-click missed. `game_loop.py click_action <i>` dispatched
via `computer_batch` → `verify_action` returns `desync` with
category `click_miss` every time. `cmd_solve --beam 2` plan itself
was sane (score 121k, 3 sensible actions); the clicks just didn't
land on the intended tiles.

## Evidence

### The coord systems don't agree

- `python3 tile_hover.py F5` returns `(755, 261)` — this matches
  `src/control/executor.py::grid_to_mcp(3, 2)` which produces
  `(755, 261)` via:

  ```
  ox = win.x + 494 * sx    # win.x = 215, sx = 1.0
  oy = win.y + 56 * sy
  step_x = 46.21 * sx
  step_y = 34.57 * sy
  ```

- `mouse_move` to image-pixel `(755, 261)` lands on a **Ground Tile
  tooltip** — not F5 (which should have the Jet Mech).
- `mouse_move` to `(740, 413)` (from `grid_reference.json`'s formula)
  lands on a **Water Tile tooltip** — correct terrain for F5 (flying
  mech over water), but clicking doesn't select the mech.
- `mouse_move` to `(690, 660)` (grid_reference's claimed A1 origin)
  lands OUTSIDE the board — tile tooltip is empty.

### The window hasn't moved

Quartz reports window at `(215, 32, 1280, 748)` consistently across
the session.

### Non-tile clicks work

`mouse_move` to image-pixel `(280, 122)` correctly hovers the End
Turn button (visible white-border highlight). Per CLAUDE.md, End Turn
is at window-relative `(95, 78)` ⇒ logical `(310, 110)`. That gives
an image-to-logical mapping of `(280/310, 122/110) = (0.903, 1.109)`
— non-uniform.

### Two different formulas in the repo disagree

- `executor.py::grid_to_mcp` — logical-coord formula calibrated to
  a 1280×748 window
- `data/grid_reference.json` — image-pixel formula with origin
  `(1, A) = (690, 660)`, `row_step = (-50, -27.5)`, `col_step =
  (50, -27.5)`

Neither matches the actual on-screen tile positions this session.

## Corpus sweep of when this might have broken

Not done as part of this investigation. Candidates:

1. **Display change** — main display logical resolution is
   `1680×1050` now; previous calibration may have assumed a
   different resolution.
2. **Screenshot scale change** — the MCP tool reports coords in
   `image_pixels`. Observed screenshot dimensions this session are
   ~`1389×867`, giving an image-to-logical ratio of ~`0.827`. If
   prior sessions had `image == logical` (no compositor
   downscaling), the formulas would have worked as-is.
3. **ItB version / window chrome change** — unlikely (Steam version
   string in `grid_reference.json` matches; 3-12-2024).

## Proposed fix (next session)

Write a dedicated calibration tool `scripts/calibrate_grid.py` that:

1. Takes a fresh screenshot
2. Uses `mouse_move` + `zoom` at a known UI anchor (End Turn
   button) to confirm the image-to-screen coord mapping is 1:1
3. For each of 4 corner tiles (A1, A8, H1, H8), does a binary
   search of hover positions until the correct tile-tooltip fires
4. Fits a single affine transform `image_pixel = f(save_x, save_y)`
   from the 4 corners
5. Emits updated calibration constants to write back to
   `executor.py` (and/or deprecate `data/grid_reference.json`)

This replaces both the logical-coord formula and the old
image-pixel formula with **measured coordinates for the current
setup**.

Gate: the calibration needs to be re-run whenever the display or
MCP screenshot scale changes. Add a runtime sanity check to
`cmd_solve` (or `auto_turn`) that hovers a known tile during
initialization and refuses to proceed if the tooltip is wrong.

## State of the run when giving up

- `solver/beam-cmd-integration` PR #5 has merged (beam flag
  available via `--beam {0,1,2}`)
- Live run: Pinnacle Robotics → Frozen Plains, Turn 1, combat_player
- No mech actions actually executed this turn
- Three bonus objectives visible (Kill 7, Protect Coal Plant,
  Protect Time Pod)
- Game window still open; Jet/Arti/Science mechs at deploy positions
  F5 / C5 / G6; JetMech has Aerial Bombs ready

Next session: close the game (or abandon this run), fix the
calibration, then re-attempt a fresh run.

## Rollback note

No code change in this investigation — just this doc. If future
readers see similar `click_miss` behavior, reopen and read this
first.
