# Hazardous Immortal Retrospective

Date: 2026-06-01 Steam-cache confirmation
Run: `20260531_181444_169`
Squad: Hazardous Mechs
Difficulty: Easy, Advanced Edition ON
Route: 4 Corporate Islands, ending on Detritus Corporate HQ
Target: Immortal

Outcome: **Immortal** unlocked. The Steam local cache moved `Ach_Detritus_B_2` to achieved with `bAchieved=true` and raised the confirmed achievement count to 51/70 after leaving the fourth island. The final Detritus Corporate HQ screen showed `Region Secured`, both HQ objectives checked, all three mech portraits present, and no KIA panel.

## What Worked

- Survival-first scoring was enough on Easy as long as battle-end mech state stayed authoritative. Optional objectives and grid/building trades were acceptable only when all mechs remained alive and fresh reads showed no disable risk.
- `auto_turn` remained the right combat primitive. It verified after each bridge move/attack, re-solved on desync, and emitted End Turn only after a threat audit.
- The final Detritus HQ was safer than it first looked once the Starfish Leader died early. The last-turn plan let a Moth retarget off the Corporate Tower while keeping all mechs alive.
- Grid-first shopping still mattered. After the perfect Detritus finish, the route bought +1 Grid Power to refill before leaving the island.

## Bot Lessons

- On Windows, live bridge state may be newest in `itb_state.json.tmp`; read the newest valid state file rather than treating `.tmp` as incomplete by default.
- Visible map and reward screens are authoritative when the bridge reports stale combat. During the HQ start flow, stale `Mission_Acid` turn 4 reads appeared while the screen was clearly the HQ map/preview; do not solve from those stale boards.
- Detritus Corporate HQ preview is a side-card/dialogue flow. A calibrated `mission_preview_board` click can hit a neighboring completed-region card when the HQ side-card is selected. Select the HQ region, verify the visible title/objectives, and click the visible side-card/preview deliberately.
- `lightning_ui` controls are useful outside Lightning War, but their classifiers can misname ordinary island-complete panels as `perfect_island_panel` or shop screens as pause. Use the screenshot evidence, not only the label.
- `modal_understood` and some panel controls can be vertically off on Windows. Promotion/reward panels may need direct visible-button clicks or updated calibration before relying on a named control.

## Follow-Up

- Keep `src/bridge/protocol.py`'s `.tmp` state fallback; it prevented stale-board recovery from derailing the final island.
- Keep the Windows shop controls (`shop_grid_power`, `shop_continue`) and corrected Detritus island-select calibration in `src/control/mac_click.py`.
- The active Hazardous target list is now closed. Future achievement selection can pivot to Blitzkrieg **Lightning War**, Cataclysm, Mist Eaters/Heat Sinkers/Arachnophiles, Bombermechs, or Random **Lucky Start**.
