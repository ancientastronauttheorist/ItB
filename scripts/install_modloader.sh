#!/usr/bin/env bash
# Copy src/bridge/modloader.lua into the Steam app bundle so the game
# picks up edits on next restart. Without this, the game keeps running
# the stale pre-change modloader and bridge edits silently no-op.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/src/bridge/modloader.lua"
DST="$HOME/Library/Application Support/Steam/steamapps/common/Into the Breach/Into the Breach.app/Contents/Resources/scripts/modloader.lua"

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: source not found: $SRC" >&2
  exit 1
fi

if [[ ! -d "$(dirname "$DST")" ]]; then
  echo "ERROR: Steam install dir not found: $(dirname "$DST")" >&2
  echo "Is Into the Breach installed via Steam?" >&2
  exit 1
fi

cp "$SRC" "$DST"
echo "Installed: $DST"
echo "Restart Into the Breach to load the new modloader."
