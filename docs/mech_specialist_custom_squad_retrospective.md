# Mech Specialist / Flight Specialist Retrospective

Run `20260526_204256_831` completed **Mech Specialist** and **Flight Specialist** on 2026-05-27 with Custom Squad 3x Ice Mech on Easy. Steam sync confirmed 46/70 achievements immediately afterward.

## What Worked

- 3x Ice Mech double-dipped both requirements: three copies of the exact same mech, and three flying mechs.
- Failed optional leader bonuses did not matter. Archive HQ left the Firefly Leader alive/frozen, but Region Secured was enough for the achievement route.
- Final-cave priorities were correct when they favored Renfield Bomb survival and grid above zero over kills, reputation, and pylon HP.
- When Codex Computer Use disappeared after a reboot, bridge combat commands still worked. Activating Into the Breach and clicking the latest `click_end_turn` screen coordinate with `pyautogui` was enough, as long as every click was followed by a fresh `read`.

## What Bit Us

- Bethany's Ice Mech entered the final cave disabled, leaving only two active Ice Mechs and the Renfield Bomb. The route still succeeded, but future triple-Ice runs should verify all three mechs after final-cave deployment before assuming normal action economy.
- Cryo shots repeatedly produced status-only desyncs or self-freeze debt. These were usually tactical, not fatal, but they made the dirty frontier important.
- `saveData` intermittently reported `mission_ending` while the visible final cave and raw bridge state were still live. Visual + bridge state won; repeated End Turn clicks without a fresh bridge read would have been unsafe.
- Research gates for ordinary final-cave units such as Hornet and Renfield Bomb still matter. Clear them before continuing, even late in a successful achievement push.

## Carry Forward

For future Custom Squad attempts, 3x Ice Mech is now the default proven route only if the target still benefits from it. Otherwise pivot to remaining Custom/Random goals such as **Class Specialist**, **Change the Odds**, **Loot Boxes!**, **Lucky Start**, or **Engineering Dropout**. Do not retarget **Mech Specialist** or **Flight Specialist** unless a future Steam sync contradicts the 2026-05-27 46/70 cache.
