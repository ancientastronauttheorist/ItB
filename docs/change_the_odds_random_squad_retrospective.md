# Change the Odds Random Squad Retrospective

Run `20260527_152006_916` completed **Change the Odds** on 2026-05-27 with Random Squad on Easy. Steam sync confirmed 47/70 achievements immediately afterward.

## What Worked

- Easy Balanced Roll was sufficient. The squad did not need to win the timeline; it only needed to survive one profitable island and reach the shop with enough reputation/assets.
- The achievement cares about visible Grid Defense, not Grid Power. The winning shop line filled Grid Power to `7/7`, then bought Overpower Grid until defense reached 30%.
- Selling assets after the first island was enough. Archive HQ left the run with enough reputation plus spare weapons/pilots to push Grid Defense from 15% to 30%.
- Non-desync dirty losses were acceptable for this target after review. Grid, optional objectives, and even a mech/pilot loss could be spent as long as the timeline reached the shop and no board uncertainty remained.

## What Bit Us

- Two real desyncs appeared during the run and had to be fixed before continuing. Mission_Mines turn 4 proved that killing or moving one web source does not free a mech while another live queued web source still targets it; this became simulator v233, commit `4ba590d`.
- Corporate HQ turn 1 proved that plain Titan Fist can kill `BlobB` at B6 and still corpse-bump Boulder/Rockart Mech at A6; this became simulator v234, commit `353d9f7`.
- The old strategy note understated the math. The first five overpowers are +2% each, but later overpowers are +1%, so no-bonus runs need 10 total overpowered Grid Power from the normal 15% start.
- The achievement can tempt over-investment into combat upgrades. For this route, shop purchases should remain grid-first until the popup appears.

## Carry Forward

For future Random Squad achievement routes, treat **Change the Odds** as closed unless Steam sync contradicts the 2026-05-27 47/70 cache. If rerunning it for regression, avoid Unfair, buy Grid Power to full before cores/weapons, and sell spare weapons/pilots after a profitable first island until visible Grid Defense reaches 30%. Do not leave the shop early just because the grid is full.
