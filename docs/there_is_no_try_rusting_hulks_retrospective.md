# There is No Try Rusting Hulks Retrospective

Date: 2026-05-19
Run: `20260519_154655_297`
Squad: Rusting Hulks
Difficulty: Easy
Target: Finish 3 Corporate Islands without failing an objective

Outcome: **There is No Try unlocked**. The run completed Detritus Disposal, Archive Inc., and R.S.T. Corporation with every mission objective credited. The in-game achievement toast appeared after leaving the third island; after saving, quitting, and reopening the game, `python3 game_loop.py achievements --sync` confirmed Steam/client cache at `35/70`.

## Route

### Island 1: Detritus Disposal

- Site C / `Mission_Acid`: `Kill 4 or fewer Enemies` and `Protect the Coal Plant` credited.
- Waste Chambers / `Mission_BeltRandom`: `Kill at least 5 enemies` credited.
- Downtown / `Mission_Belt`: `Knock Mites off the Mechs`, `Protect Emergency Batteries`, and `Protect Time Pod` credited.
- The Wasteland / `Mission_Civilians`: VIPs defended 2/2.
- Corporate HQ / `Mission_BlobberBoss`: Blobber Leader destroyed and Corporate Tower protected.

### Island 2: Archive Inc.

- The Library / `Mission_Airstrike`: mech-damage objective credited, Old Earth Bar protected, Time Pod recovered.
- Archivist Hall / `Mission_Volatile`: Volatile Vek survived and Emergency Batteries protected.
- Research Center / `Mission_Survive`: `Kill 4 or fewer Enemies` credited exactly at 4/4.
- Archival Flats / `Mission_Tides`: mites cleared, Power Generator protected.
- Corporate HQ / `Mission_FireflyBoss`: Firefly Leader destroyed and Corporate Tower protected.

### Island 3: R.S.T. Corporation

- Blast Bunker / `Mission_Filler`: Earth Mover defended and `<4 Mech Damage` credited.
- Scorched Earth / `Mission_Volatile`: Volatile Vek, Coal Plant, and Time Pod all protected.
- Thunderbolt Grid / `Mission_Lightning`: `<3 Grid Damage`, Emergency Batteries, and Time Pod all credited.
- Phoenix Park / `Mission_Trapped`: Coal Plant protected.
- Corporate HQ / `Mission_BeetleBoss`: Beetle Leader destroyed and Corporate Tower protected.

## Operational Notes

- This achievement is objective-only: ordinary grid/building losses were allowed only when no mission objective, Time Pod, protected unit, or boss/tower objective failed.
- Several final-turn dirty or threat-audit holds were advanced only after exact review showed objective counters remained safe.
- The unlock did not show up in Steam cache immediately after the third HQ. The decisive UI transition was leaving the third island; the Steam sync caught up after save-quit-reopen.
