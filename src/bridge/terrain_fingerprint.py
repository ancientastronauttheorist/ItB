"""Mid-mission terrain stage-change detection.

Some Into the Breach final missions swap their terrain wholesale partway
through combat (R.S.T.'s ``Mission_Final`` is the canonical case: a volcano
arena with a central lava field and ring of volcano cones gives way to a
caverns arena with the Renfield Bomb objective). The bridge always reports
the current terrain on every read, but our solver was treating the stage-1
terrain as authoritative for the whole mission — predicted_states from the
pre-swap solve would disagree with the post-swap actual board, and the
desync diff was too noisy to surface as a single research-gate signal.

This module produces a stable structural fingerprint per turn so the
read path can detect "the floor swapped under us mid-fight" and emit a
clear signal that downstream code (auto_turn, replay, the harness) can
act on.

Design notes:

* **Structural terrain only.** We hash the ``terrain`` string of each
  tile (one of: ``ground``, ``water``, ``mountain``, ``lava``, ``forest``,
  ``sand``, ``ice``, ``chasm``, ``rubble``, ``building``). Status overlays
  (fire, smoke, acid, frozen, cracked, conveyor, mines, pod) are
  intentionally excluded — they mutate every turn, and a stage swap will
  be visible in the structural channel alone.

* **Building HP is ignored.** A destroyed building flips terrain
  ``building`` → ``ground`` only when the engine actually rubble-izes
  the tile; until then ``terrain`` stays ``building`` regardless of HP.
  That keeps the hash stable across "took 2 dmg of 2" mutations.

* **Threshold-based.** Normal turn-over-turn mutation produces small
  structural deltas (mountain→rubble at most 1–2 tiles per turn, an
  occasional ice→water from cracked-ice). A stage swap reorganizes
  the entire arena. We flag at >= 16 changed tiles (25% of the 64-tile
  board), which sits comfortably above natural mutation while well
  below the dozens of changed tiles a stage swap produces.

* **Mission-scoped.** A new mission_index is expected to change
  terrain wholesale; the detector only fires when the swap happens
  *within* the same mission_index AND turn > 0.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


# Terrain class constants — keep in sync with TERRAIN_NAMES in
# src/bridge/modloader.lua. ``rubble`` is a derived class the bridge
# emits when terrain_id == 2; mountains report terrain_id == 4 with an
# HP field, so a fully-destroyed mountain shows up here as ``rubble``
# only once the engine swaps the terrain class itself.
_KNOWN_TERRAIN_CLASSES = frozenset({
    "ground", "building", "rubble", "water", "mountain",
    "lava", "forest", "sand", "ice", "chasm", "acid",
})

# Default threshold: at least 25% of the 64-tile board must change
# structural class for a stage swap to fire. Empirically a destroyed
# mountain or melted ice changes 1-2 tiles per turn; the volcano →
# caverns swap on Mission_Final changes 40+ tiles in one go.
DEFAULT_CHANGE_THRESHOLD = 16


@dataclass(frozen=True)
class TerrainFingerprint:
    """Stable structural fingerprint of an 8x8 terrain board.

    ``hash`` is a hex-truncated SHA-256 of the row-major 64-character
    class string. ``classes`` is the same data in raw form so callers
    that want a per-tile diff don't have to rehash.
    """
    hash: str
    classes: str  # 64 chars; 1 letter per tile, row-major (x outer, y inner)
    mission_index: int
    turn: int


def _tile_class_letter(terrain: str) -> str:
    """Map a terrain string to a single character for the class array.

    Unknown terrain falls through to ``?`` so a future modloader change
    that introduces a new class doesn't silently collide with an
    existing letter. The detector treats ``?`` as just another class.
    """
    return {
        "ground":   "g",
        "building": "b",
        "rubble":   "r",
        "water":    "w",
        "mountain": "m",
        "lava":     "l",
        "forest":   "f",
        "sand":     "s",
        "ice":      "i",
        "chasm":    "c",
    }.get(terrain, "?")


def fingerprint_from_bridge_tiles(
    tiles: list[dict],
    *,
    mission_index: int,
    turn: int,
) -> TerrainFingerprint:
    """Build a TerrainFingerprint from the bridge ``tiles`` list.

    Each entry must have ``x``, ``y`` and ``terrain`` keys (the shape
    emitted by ``modloader.lua``'s ``state.tiles``). Tiles missing or
    out-of-range default to ``ground`` for the class char so the hash
    stays defined even on a partial dump.
    """
    grid = [["g"] * 8 for _ in range(8)]
    for td in tiles or []:
        x = td.get("x", -1)
        y = td.get("y", -1)
        if 0 <= x < 8 and 0 <= y < 8:
            grid[x][y] = _tile_class_letter(td.get("terrain", "ground"))
    flat = "".join(grid[x][y] for x in range(8) for y in range(8))
    digest = hashlib.sha256(flat.encode("ascii")).hexdigest()[:16]
    return TerrainFingerprint(
        hash=digest,
        classes=flat,
        mission_index=mission_index,
        turn=turn,
    )


def fingerprint_from_board(board, *, mission_index: int, turn: int) -> TerrainFingerprint:
    """Build a TerrainFingerprint from a Python ``Board`` instance.

    Accepts ``src.model.board.Board`` (any object exposing
    ``board.tiles[x][y].terrain``). Used by tests and the ``replay``
    path where the raw bridge tile dict isn't available.
    """
    grid = [["g"] * 8 for _ in range(8)]
    for x in range(8):
        for y in range(8):
            t = board.tiles[x][y]
            grid[x][y] = _tile_class_letter(getattr(t, "terrain", "ground"))
    flat = "".join(grid[x][y] for x in range(8) for y in range(8))
    digest = hashlib.sha256(flat.encode("ascii")).hexdigest()[:16]
    return TerrainFingerprint(
        hash=digest,
        classes=flat,
        mission_index=mission_index,
        turn=turn,
    )


def diff_count(prev: TerrainFingerprint, curr: TerrainFingerprint) -> int:
    """Number of tiles whose structural class differs between two prints."""
    if not prev or not curr:
        return 0
    return sum(1 for a, b in zip(prev.classes, curr.classes) if a != b)


def is_stage_change(
    prev: TerrainFingerprint | None,
    curr: TerrainFingerprint,
    *,
    threshold: int = DEFAULT_CHANGE_THRESHOLD,
) -> bool:
    """Return True when ``curr`` looks like a wholesale stage swap from ``prev``.

    Conditions (all must hold):

    * ``prev`` exists (we need a previous turn to compare against),
    * same ``mission_index`` (cross-mission terrain churn is normal,
      handled by ``_auto_advance_mission`` which clears the anchor),
    * ``curr.turn > prev.turn`` (turn-0 reads on a brand-new mission
      look like a swap relative to the previous mission's last turn —
      the mission_index gate above already covers that, but the turn
      ordering check guards against bridge replays of the same turn),
    * the hash differs (cheap fast-path),
    * structural diff count crosses ``threshold``.
    """
    if prev is None:
        return False
    if prev.mission_index != curr.mission_index:
        return False
    if curr.turn <= prev.turn:
        return False
    if prev.hash == curr.hash:
        return False
    return diff_count(prev, curr) >= threshold


def fingerprint_to_session_dict(fp: TerrainFingerprint) -> dict:
    """Serialize a fingerprint for storage in active_session.json."""
    return {
        "hash": fp.hash,
        "classes": fp.classes,
        "mission_index": fp.mission_index,
        "turn": fp.turn,
    }


def fingerprint_from_session_dict(d: dict | None) -> TerrainFingerprint | None:
    """Deserialize the inverse of ``fingerprint_to_session_dict``."""
    if not d:
        return None
    try:
        return TerrainFingerprint(
            hash=d["hash"],
            classes=d["classes"],
            mission_index=d["mission_index"],
            turn=d["turn"],
        )
    except (KeyError, TypeError):
        return None
