# Windows Support

The live achievement loop is now verified on Windows. Run `20260529_164303_219`
completed a two-island Easy Custom Squad victory on Windows with Combat Mech,
Laser Mech, and Aegis Mech, and the Steam client cache marked
**Class Specialist** (`Ach_Custom_2`) achieved at `2026-05-30T00:15:07Z`.

## What Works

- Lua bridge IPC uses a platform-specific bridge directory through
  `src.itb_paths.get_bridge_dir()`.
- Windows default bridge path:
  `~/Documents/My Games/Into The Breach/itb_bridge`.
- Windows default save path:
  `~/Documents/My Games/Into The Breach/profile_Alpha`.
- `src/capture/window.py` and `src/capture/detect_grid.py` find the game window
  with Win32 APIs instead of Quartz.
- Screenshots use PIL `ImageGrab` on Windows.
- Session locking uses `msvcrt.locking` on Windows and `fcntl` on Unix-like
  systems.

## Operational Notes

Use `python -X utf8 game_loop.py ...` from PowerShell when console encoding might
touch board glyphs, achievement names, or Lua text. Keep the same live-run safety
rules as macOS: run session-touching `game_loop.py` commands one at a time, trust
the bridge for combat state, and use screen evidence for reward, shop, and
victory panels.

The macOS `scripts/install_modloader.sh` still installs into the Steam app bundle.
On Windows, install `src/bridge/modloader.lua` into the ITB-ModLoader location
used by the game, then restart Into the Breach. Set `ITB_SAVE_DIR` or
`ITB_BRIDGE_DIR` only when the game uses nonstandard locations.

## Verified Achievement Route

Class Specialist is complete with a Custom Squad of three different Prime-class
mechs:

- Combat Mech
- Laser Mech
- Aegis Mech

The run won Detritus, Archive, and the Volcanic Hive on Easy with Advanced
Edition enabled. The route accepted reviewed ordinary grid/building losses where
needed, but preserved the timeline and the Renfield Bomb through final cave.
