"""Unit tests for the mid-mission terrain stage-change detector.

Covers the fingerprint hash itself (deterministic + sensitive only to
structural terrain), the ``is_stage_change`` predicate gates
(mission_index, turn ordering, threshold), and the integration path
through ``_detect_terrain_stage_change`` (session updates, banner-fire
condition, mission-boundary reset via ``_auto_advance_mission``).
"""

from __future__ import annotations

from src.bridge.terrain_fingerprint import (
    DEFAULT_CHANGE_THRESHOLD,
    TerrainFingerprint,
    diff_count,
    fingerprint_from_bridge_tiles,
    fingerprint_from_session_dict,
    fingerprint_to_session_dict,
    is_stage_change,
)
import pytest

from src.loop.commands import (
    _auto_advance_mission,
    _detect_terrain_stage_change,
)
from src.loop.session import RunSession


@pytest.fixture(autouse=True)
def _no_session_disk_writes(monkeypatch):
    """Block ``RunSession.save`` from touching the real session file.

    ``_detect_terrain_stage_change`` persists the session on every call;
    without this fixture the tests would acquire ``sessions/active_session.json.lock``
    and clobber a real run. Mirrors the pattern in
    ``tests/test_disabled_actions_load_prune.py``.
    """
    monkeypatch.setattr(RunSession, "save", lambda self, path=None: None)


def _all_ground_tiles() -> list[dict]:
    """An 8x8 board of plain ground tiles."""
    return [
        {"x": x, "y": y, "terrain": "ground"}
        for x in range(8) for y in range(8)
    ]


def _volcano_tiles() -> list[dict]:
    """Stage-1 fingerprint — central lava field, ring of mountains.

    Mirrors the structural look of Mission_Final stage 1 (volcano arena):
    a dense lava patch in the middle, mountains around the perimeter,
    rest plain ground.
    """
    tiles = _all_ground_tiles()
    grid = {(t["x"], t["y"]): t for t in tiles}
    # Central 4x4 lava block (16 tiles)
    for x in range(2, 6):
        for y in range(2, 6):
            grid[(x, y)]["terrain"] = "lava"
    # Perimeter mountains (12 tiles on outer edge corners + sides)
    for x, y in [
        (0, 0), (0, 7), (7, 0), (7, 7),  # corners
        (0, 3), (0, 4), (7, 3), (7, 4),  # mid edges
        (3, 0), (4, 0), (3, 7), (4, 7),
    ]:
        grid[(x, y)]["terrain"] = "mountain"
    return list(grid.values())


def _caverns_tiles() -> list[dict]:
    """Stage-2 fingerprint — cavern arena, lava patches scattered.

    Wholly different structural pattern: the central lava block is gone,
    replaced by ground; chasm patches replace the perimeter mountains;
    a few new lava tiles appear scattered around. ~40 tiles change.
    """
    tiles = _all_ground_tiles()
    grid = {(t["x"], t["y"]): t for t in tiles}
    # Scattered lava patches in a different pattern
    for x, y in [(1, 5), (5, 1), (6, 6), (2, 3), (4, 4)]:
        grid[(x, y)]["terrain"] = "lava"
    # Chasms along a different perimeter pattern
    for x in range(8):
        grid[(x, 0)]["terrain"] = "chasm"
        grid[(x, 7)]["terrain"] = "chasm"
    return list(grid.values())


# ---------------------------------------------------------------------------
# Fingerprint primitives
# ---------------------------------------------------------------------------

def test_fingerprint_is_deterministic():
    fp1 = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=3, turn=0,
    )
    fp2 = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=3, turn=0,
    )
    assert fp1.hash == fp2.hash
    assert fp1.classes == fp2.classes
    assert len(fp1.classes) == 64


def test_fingerprint_ignores_status_overlays():
    """Fire / smoke / acid / frozen / cracked / pod / mines are ignored."""
    plain = _all_ground_tiles()
    fp_plain = fingerprint_from_bridge_tiles(plain, mission_index=0, turn=0)

    overlays = _all_ground_tiles()
    # Toss in every status overlay we strip — none should change the hash.
    overlays[0].update({"fire": True, "smoke": True, "acid": True})
    overlays[5].update({"frozen": True, "cracked": True, "pod": True})
    overlays[10].update({"freeze_mine": True, "old_earth_mine": True})
    overlays[12].update({"conveyor": 1})
    fp_overlays = fingerprint_from_bridge_tiles(
        overlays, mission_index=0, turn=0,
    )
    assert fp_plain.hash == fp_overlays.hash


def test_fingerprint_changes_on_terrain_swap():
    fp_v = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=0,
    )
    fp_c = fingerprint_from_bridge_tiles(
        _caverns_tiles(), mission_index=0, turn=1,
    )
    assert fp_v.hash != fp_c.hash
    # The two synthetic boards above should differ on at least the
    # threshold's worth of tiles.
    assert diff_count(fp_v, fp_c) >= DEFAULT_CHANGE_THRESHOLD


def test_fingerprint_round_trips_through_session_dict():
    fp = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=2, turn=4,
    )
    rt = fingerprint_from_session_dict(fingerprint_to_session_dict(fp))
    assert rt == fp


def test_fingerprint_from_session_dict_handles_none_and_garbage():
    assert fingerprint_from_session_dict(None) is None
    assert fingerprint_from_session_dict({}) is None
    assert fingerprint_from_session_dict({"hash": "x"}) is None  # missing keys


# ---------------------------------------------------------------------------
# is_stage_change predicate
# ---------------------------------------------------------------------------

def test_is_stage_change_no_prior_fingerprint_does_not_fire():
    fp = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=0,
    )
    assert is_stage_change(None, fp) is False


def test_is_stage_change_cross_mission_does_not_fire():
    """Mission boundary already handles this; detector ignores it."""
    fp_prev = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=4,
    )
    fp_curr = fingerprint_from_bridge_tiles(
        _caverns_tiles(), mission_index=1, turn=0,
    )
    assert is_stage_change(fp_prev, fp_curr) is False


def test_is_stage_change_same_turn_does_not_fire():
    """Turn 1 read twice in a row (e.g. retry) shouldn't fire."""
    fp_prev = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=1,
    )
    fp_curr = fingerprint_from_bridge_tiles(
        _caverns_tiles(), mission_index=0, turn=1,
    )
    assert is_stage_change(fp_prev, fp_curr) is False


def test_is_stage_change_below_threshold_does_not_fire():
    """A handful of mountains becoming rubble must not trip the gate."""
    fp_prev = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=0,
    )
    # Mutate just 3 tiles — well under the 16-tile threshold.
    mutated = _volcano_tiles()
    mutated[0]["terrain"] = "rubble"
    mutated[1]["terrain"] = "rubble"
    mutated[2]["terrain"] = "ground"
    fp_curr = fingerprint_from_bridge_tiles(
        mutated, mission_index=0, turn=1,
    )
    assert is_stage_change(fp_prev, fp_curr) is False


def test_is_stage_change_volcano_to_caverns_fires():
    fp_prev = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=2,
    )
    fp_curr = fingerprint_from_bridge_tiles(
        _caverns_tiles(), mission_index=0, turn=3,
    )
    assert is_stage_change(fp_prev, fp_curr) is True


def test_is_stage_change_custom_threshold():
    fp_prev = fingerprint_from_bridge_tiles(
        _volcano_tiles(), mission_index=0, turn=0,
    )
    mutated = _volcano_tiles()
    # Change exactly 5 tiles.
    for i in range(5):
        mutated[i]["terrain"] = "water"
    fp_curr = fingerprint_from_bridge_tiles(
        mutated, mission_index=0, turn=1,
    )
    # Default threshold (16) → no fire; threshold 5 → fires.
    assert is_stage_change(fp_prev, fp_curr) is False
    assert is_stage_change(fp_prev, fp_curr, threshold=5) is True


# ---------------------------------------------------------------------------
# Integration: _detect_terrain_stage_change + RunSession
# ---------------------------------------------------------------------------

def test_detect_seeds_anchor_on_first_read():
    """First read of a fresh mission seeds the fingerprint without firing."""
    s = RunSession(
        run_id="test", squad="rift_walkers", current_mission="Mission_Final",
        mission_index=0,
    )
    bridge = {"turn": 0, "tiles": _volcano_tiles()}
    out = _detect_terrain_stage_change(s, bridge)
    assert out is None
    assert s.last_terrain_fingerprint is not None
    assert s.last_terrain_fingerprint["turn"] == 0
    assert s.terrain_stage_change_pending is False


def test_detect_no_swap_normal_turn_progression():
    """Same terrain on turn 1 vs turn 0 is the common case — no fire."""
    s = RunSession(
        run_id="test", squad="rift_walkers", current_mission="Mission_Final",
        mission_index=0,
    )
    _detect_terrain_stage_change(s, {"turn": 0, "tiles": _volcano_tiles()})
    out = _detect_terrain_stage_change(
        s, {"turn": 1, "tiles": _volcano_tiles()},
    )
    assert out is None
    assert s.terrain_stage_change_pending is False
    assert s.last_terrain_fingerprint["turn"] == 1


def test_detect_volcano_to_caverns_fires_and_records():
    s = RunSession(
        run_id="test", squad="rift_walkers", current_mission="Mission_Final",
        mission_index=4,
    )
    _detect_terrain_stage_change(s, {"turn": 2, "tiles": _volcano_tiles()})
    out = _detect_terrain_stage_change(
        s, {"turn": 3, "tiles": _caverns_tiles()},
    )
    assert out is not None
    assert out["mission_index"] == 4
    assert out["mission"] == "Mission_Final"
    assert out["prev_turn"] == 2
    assert out["curr_turn"] == 3
    assert out["tiles_changed"] >= DEFAULT_CHANGE_THRESHOLD
    assert s.terrain_stage_change_pending is True
    # A decision row should have been logged for the harness.
    labels = [d["label"] for d in s.decisions]
    assert "terrain_stage_change" in labels


def test_mission_boundary_clears_anchor():
    """`_auto_advance_mission` resets the anchor + pending flag.

    Without this, jumping from Mission_A turn 5 (volcano) into
    Mission_B turn 0 (forest) would look like a stage swap.
    """
    s = RunSession(
        run_id="test", squad="rift_walkers",
        current_mission="Mission_Volcano", mission_index=2,
    )
    _detect_terrain_stage_change(s, {"turn": 5, "tiles": _volcano_tiles()})
    s.terrain_stage_change_pending = True  # simulate a previously-fired swap
    changed = _auto_advance_mission(s, {"mission_id": "Mission_Forest"})
    assert changed is True
    assert s.last_terrain_fingerprint is None
    assert s.terrain_stage_change_pending is False


def test_session_round_trip_persists_fingerprint(tmp_path):
    """Round-trip the new fields through to_dict / from_dict."""
    s = RunSession(run_id="test", squad="rift_walkers", mission_index=1)
    _detect_terrain_stage_change(s, {"turn": 0, "tiles": _volcano_tiles()})
    s.terrain_stage_change_pending = True
    rt = RunSession.from_dict(s.to_dict())
    assert rt.last_terrain_fingerprint == s.last_terrain_fingerprint
    assert rt.terrain_stage_change_pending is True


def test_legacy_session_load_defaults_fields():
    """Legacy session JSON without the new fields loads cleanly."""
    legacy = {
        "run_id": "legacy",
        "squad": "rift_walkers",
        # ... none of the new fields present
    }
    rt = RunSession.from_dict(legacy)
    assert rt.last_terrain_fingerprint is None
    assert rt.terrain_stage_change_pending is False
