# Class Specialist Windows Retrospective

Run `20260529_164303_219` completed **Class Specialist** on 2026-05-30
with a Custom Squad of Combat Mech, Laser Mech, and Aegis Mech on Easy.
The Steam client cache confirmed `Ach_Custom_2` at `2026-05-30T00:15:07Z`,
raising the local checklist to 48/70.

This was also the first full achievement victory completed by the live loop on
Windows. The bridge used the Windows save root under
`Documents/My Games/Into The Breach`, IPC files under `itb_bridge`, Win32 window
detection, PIL screenshots, and Windows file locking. The tactical loop stayed
the same: bridge reads for combat, bridge execution for mech actions, verified
sub-actions, and calibrated End Turn clicks.

## Route Notes

- Squad: Combat Mech, Laser Mech, Aegis Mech.
- Requirement satisfied: three different Prime-class mechs in a Custom Squad.
- Difficulty: Easy, Advanced Edition ON, two-island victory.
- Islands cleared before Hive: Detritus and Archive.
- Archive shop bought Grid Power first, then Sidewinder Fist, Stabilizers,
  Reactor Core, and final grid-defense overcharge.

## Tactical Notes

The run accepted ordinary achievement-hunt grid/building losses after dirty
frontier review, but never accepted timeline collapse, board uncertainty, or
Renfield Bomb loss. In the final island, the first battle took one unavoidable
building/grid loss while preserving all pilots and mechs. In final cave, the
solver repeatedly prioritized moving mechs off lethal volcanic hazard tiles and
preserving the Renfield Bomb over kills or pylon HP.

## Future Guidance

Treat **Class Specialist** as closed unless a future Steam sync contradicts the
Windows Steam cache. The proven route is now Prime-class Custom Squad on Easy:
Combat Mech for displacement, Laser Mech for reach, and Aegis Mech for armored
control. The route is a useful regression guard for Windows live-control support,
platform-specific bridge paths, and final-cave hazard triage.
