# grid_to_mcp calibration — residual click-pipeline issues (2026-04-23)

## Context

PR #7 fixed the four constants in `src/control/executor.py::grid_to_mcp`
and added a sprite-position offset for mech-select clicks. Empirical
hover-verify on Pinnacle Frozen Plains showed F5 → image-pixel
(740, 412) correctly hits the F5 water tile per the game's "Water Tile"
tooltip.

Subsequent live-play attempt on Silicate Plains (same Pinnacle island,
different mission) showed the fix is **incomplete**.

## What works

- Hover tooltips match `grid_to_mcp` output for empty tiles.
- Sprite-offset select (tile_center − 150 py) selects the JetMech on F5.
- Weapon-slot UI coords (181, 553) / (245, 553) / (105, 553) correctly arm weapons.
- Deploy clicks land on the board and DO deploy mechs — the game accepts them.

## What doesn't work

### 1. Deploy clicks land on the "wrong" tile

On Silicate Plains, I tried to deploy at D7 (540, 412), E7 (590, 385),
and G7 (690, 330). Bridge state after deployment:

- PunchMech at **B6** (expected D7)
- JetMech at **C5** (expected E7)
- RocketMech at **E5** (expected G7)

The offsets aren't uniform:

- D7 → B6: ΔsaveX=+1 ΔsaveY=+2 → pixel Δ=(−50, +82.5)
- E7 → C5: ΔsaveX=+2 ΔsaveY=+2 → pixel Δ=(0, +110)
- G7 → E5: ΔsaveX=+2 ΔsaveY=+2 → pixel Δ=(0, +110)

Two of the three are consistently "2 tile-half-heights lower" but the
third is offset DIAGONALLY. No uniform correction will fix this.

### 2. Combat-action dispatches return click_miss

`click_action 0` plan for PunchMech B6 → D6 with Titan Fist at E6:

```
(490, 345)  Select PunchMech at B6  ← sprite offset from tile (490, 495)
(590, 440)  Move to D6
(396, 585)  Arm Prime_Punchmech
(640, 412)  Fire at E6
```

Batched dispatch returned 4-diff `click_miss`. Bridge state after:
all three mechs unchanged, still READY at deploy positions (B6, C5,
E5).

### 3. Hovering matches bridge state — clicking doesn't

The paradox: `mouse_move` to `grid_to_mcp(2,6) = (490, 495)` shows
the game's **correct B6 terrain tooltip** (matching what bridge says
is at B6). But clicking that same pixel doesn't select the PunchMech
that bridge says is at B6.

This rules out "formula is wrong for this mission" as a cause. The
coord IS the right pixel for hover purposes. The click hit-test is
doing something different than the hover hit-test.

## Hypotheses for the click-hover discrepancy

1. **Iso click hit-test uses a tighter bounding box than hover.** The
   game may accept hovers anywhere inside a tile's bounding rect but
   only register clicks at a specific inner region (e.g., the tile
   diamond's visible pixels only, excluding the corner triangles).
   This would explain clicks "falling through" to adjacent tiles
   while hovers report the intended tile.
2. **Sprite layering affects click dispatch but not hover.** Mech
   and building sprites draw above their tiles. Clicking on a pixel
   where a sprite is drawn might resolve to that sprite's unit rather
   than the tile below it. Hover shows tile info because tiles are
   the "ground plane" and display under sprites in the hover panel.
3. **The game has a separate click-translation-to-save-coords path
   that uses different math than the display-to-screen path.** The
   display renders iso tiles at one pixel layout; the click handler
   might map screen pixels back to board tiles via a slightly
   different formula that's off by a tile in certain directions.

## Proposed next steps (separate PR)

Run `scripts/calibrate_grid.py` (from Agent 2 in the 5-agent
investigation) and let it empirically derive:
- The correct pixel for each of 4 corner tiles for SELECTING a unit
  on that tile (not just hovering)
- Compare to the pixel that produces the correct hover tooltip
- If different, add a CLICK-SPECIFIC offset distinct from the hover
  offset

Alternative: implement the sprite-overlap workaround — for every
click, pre-hover at a set of candidate pixels around the intended
tile, find which one produces the correct tile's highlight, and
click there.

Or: use the claude-in-chrome MCP approach for click dispatch, which
uses DOM-based hit-testing rather than pixel-based. Not applicable
here (ItB is native not web) but a reminder that pixel-based click
in an iso game is fundamentally harder than it should be.

## State when giving up

Live run on Silicate Plains, Turn 1, combat_player. Three mechs
deployed (bridge positions B6/C5/E5). No mech actions executed this
turn. Board has Firefly/Shell Psion enemies with queued attacks.

The run is safe to abandon or continue manually (user clicks). It's
blocked for bot play until the click pipeline is further debugged.

## Rollback note

PR #7's grid_to_mcp fix IS correct for hover. Don't revert it. The
residual issue is that CLICKS need further calibration on top. Future
PR should build on the hover-verified formula, not replace it.
