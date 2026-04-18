"""Phase 2 #P2-5 weapon-def comparator tests.

The comparator is the regression harness — a mismatch it reports
should always be either a real sim bug OR a clearly-bad Vision read.
Tests guard both directions:

1. Known-good Vision output for a well-modeled weapon (Vice Fist):
   ZERO mismatches. If this starts firing, either WEAPON_DEFS drifted
   from the installed build or the parser lowered confidence on a
   clean read.
2. Simulated sim bugs (wrong damage, wrong push, wrong footprint):
   the comparator MUST flag them.
3. Unknown display names flag as "unknown_weapon" — surfaces weapons
   the Rust table hasn't learned yet.
4. Passive weapons don't trigger false positives on missing damage.
5. Low-confidence parses are suppressed entirely.
6. JSONL writer round-trips each mismatch with a ``timestamp`` and
   ``run_id``.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.research import comparator, vision


# ── display-name resolution ──────────────────────────────────────────────────


def test_resolve_known_weapon_name():
    assert comparator.resolve_weapon_id("Vice Fist") == "Prime_Shift"
    assert comparator.resolve_weapon_id("Titan Fist") == "Prime_Punchmech"


def test_resolve_is_case_insensitive():
    assert comparator.resolve_weapon_id("vice fist") == "Prime_Shift"
    assert comparator.resolve_weapon_id("VICE FIST") == "Prime_Shift"


def test_resolve_unknown_returns_none():
    assert comparator.resolve_weapon_id("Imaginary Weapon") is None
    assert comparator.resolve_weapon_id("") is None


# ── happy path: known-good Vice Fist ────────────────────────────────────────


def test_vice_fist_clean_vision_read_has_no_mismatches():
    parsed = vision.parse_weapon_preview({
        "name": "Vice Fist",
        "weapon_class": "Prime Class Weapon",
        "description": "Grab a unit and toss it behind you.",
        "damage": 1,
        "footprint_tiles": [[1, 0]],
        "push_directions": ["west"],
        "upgrades": ["Ally Immune", "+2 Damage"],
    })
    mm = comparator.compare_weapon(parsed)
    assert mm == [], f"Expected no mismatches, got: {mm}"


# ── damage mismatch ─────────────────────────────────────────────────────────


def test_damage_mismatch_is_high_severity():
    parsed = vision.parse_weapon_preview({
        "name": "Vice Fist",
        "damage": 5,  # Rust says 1
        "footprint_tiles": [[1, 0]],
        "push_directions": ["west"],
        "description": "Grab a unit and toss it behind you.",
    })
    mm = comparator.compare_weapon(parsed)
    damage_mm = [m for m in mm if m["field"] == "damage"]
    assert len(damage_mm) == 1
    assert damage_mm[0]["rust_value"] == 1
    assert damage_mm[0]["vision_value"] == 5
    assert damage_mm[0]["severity"] == "high"


def test_ring_aoe_vision_reads_outer_damage_not_flagged():
    """Cluster Artillery is ``damage=0, damage_outer=1`` — Vision reads
    "1" on the preview card (the outer-ring number). That's a correct
    observation, not a solver bug. Comparator should accept the match
    when Vision's number equals ``damage_outer`` on an aoe_adjacent +
    !aoe_center weapon. Exact replay of the P3-5 live-spin finding."""
    parsed = vision.parse_weapon_preview({
        "name": "Cluster Artillery",
        "damage": 1,  # matches damage_outer, not damage
        "footprint_tiles": [[-1, 0], [1, 0], [0, -1], [0, 1]],
        "push_directions": ["north", "south", "east", "west"],
        "description": "Ring damage + push outward.",
    })
    mm = comparator.compare_weapon(parsed)
    damage_mm = [m for m in mm if m["field"] == "damage"]
    assert damage_mm == [], (
        f"ring-AoE Vision match should not fire damage mismatch: {damage_mm}"
    )


def test_ring_aoe_genuine_damage_disagreement_still_flagged():
    """If Vision reports a number that matches NEITHER damage nor
    damage_outer, the mismatch still fires — the outer-damage relaxation
    is a valid-match widening, not a blanket suppression."""
    parsed = vision.parse_weapon_preview({
        "name": "Cluster Artillery",
        "damage": 3,  # neither damage (0) nor damage_outer (1)
        "footprint_tiles": [[-1, 0], [1, 0], [0, -1], [0, 1]],
        "push_directions": ["north", "south", "east", "west"],
        "description": "",
    })
    mm = comparator.compare_weapon(parsed)
    damage_mm = [m for m in mm if m["field"] == "damage"]
    assert len(damage_mm) == 1
    assert damage_mm[0]["vision_value"] == 3


# ── footprint_size mismatch ─────────────────────────────────────────────────


def test_footprint_mismatch_fires_on_wrong_size():
    # Vice Fist is single-tile target; claiming 5 tiles is wrong.
    parsed = vision.parse_weapon_preview({
        "name": "Vice Fist",
        "damage": 1,
        "footprint_tiles": [[1, 0], [2, 0], [0, 1], [1, 1], [2, 1]],
        "push_directions": ["west"],
        "description": "d",
    })
    mm = comparator.compare_weapon(parsed)
    f = [m for m in mm if m["field"] == "footprint_size"]
    assert len(f) == 1
    assert f[0]["severity"] == "medium"


def test_area_blast_expects_4_or_5_tiles():
    # Area Blast: self_aoe, aoe_adjacent, no center → expect 4 tiles.
    # Four adjacent tiles: clean match.
    parsed = vision.parse_weapon_preview({
        "name": "Area Blast",
        "damage": 1,
        "footprint_tiles": [[1, 0], [-1, 0], [0, 1], [0, -1]],
        "push_directions": ["north", "south", "east", "west"],
        "description": "Hit adjacent.",
        "weapon_class": "Prime Class Weapon",
    })
    mm = comparator.compare_weapon(parsed)
    assert not any(m["field"] == "footprint_size" for m in mm), mm


# ── push_arrows mismatch ─────────────────────────────────────────────────────


def test_push_shape_forward_expects_exactly_one_arrow():
    # Titan Fist: push="forward" — Vision claiming no push is wrong.
    parsed = vision.parse_weapon_preview({
        "name": "Titan Fist",
        "damage": 2,
        "footprint_tiles": [[1, 0]],
        "push_directions": [],
        "description": "Punch.",
    })
    mm = comparator.compare_weapon(parsed)
    p = [m for m in mm if m["field"] == "push_arrows"]
    assert len(p) == 1
    assert p[0]["rust_value"]["push_dir"] == "forward"


def test_push_shape_outward_expects_multiple_arrows():
    # Area Blast: push="outward" — expect ≥1 arrows (really 2-4).
    parsed = vision.parse_weapon_preview({
        "name": "Area Blast",
        "damage": 1,
        "footprint_tiles": [[1, 0], [-1, 0], [0, 1], [0, -1]],
        "push_directions": [],
        "description": "d",
    })
    mm = comparator.compare_weapon(parsed)
    # Empty pushes for an Outward weapon → flag.
    assert any(m["field"] == "push_arrows" for m in mm)


def test_push_shape_inward_tolerates_zero_arrows():
    """Pull weapons (Grav Well) don't render arrow glyphs in the preview —
    the pull is implicit in the projectile/target path. The comparator
    shouldn't flag a mismatch when Vision reads 0 arrows."""
    parsed = vision.parse_weapon_preview({
        "name": "Grav Well",
        "damage": 0,
        "footprint_tiles": [[1, -1]],
        "push_directions": [],
        "description": "Artillery weapon that pulls its target towards you.",
    })
    mm = comparator.compare_weapon(parsed)
    assert not any(m["field"] == "push_arrows" for m in mm), \
        f"inward weapons with 0 arrows should pass; got {mm}"


# ── unknown_weapon ──────────────────────────────────────────────────────────


def test_unknown_weapon_name_flags_as_high_severity():
    parsed = vision.parse_weapon_preview({
        "name": "Imaginary Death Ray",
        "damage": 9,
        "footprint_tiles": [[1, 0]],
        "push_directions": [],
        "description": "d",
    })
    mm = comparator.compare_weapon(parsed)
    assert len(mm) == 1
    assert mm[0]["field"] == "unknown_weapon"
    assert mm[0]["severity"] == "high"


# ── confidence floor ────────────────────────────────────────────────────────


def test_low_confidence_parse_suppresses_comparison():
    # A parse with confidence=0.3 shouldn't contribute mismatches even
    # if the Vision output is totally wrong — noise in → noise out.
    parsed = {
        "name": "Imaginary",  # unknown weapon would normally flag
        "damage": 0,
        "footprint_tiles": [],
        "push_directions": [],
        "confidence": 0.3,
    }
    mm = comparator.compare_weapon(parsed)
    assert mm == []


def test_confidence_floor_inclusive():
    parsed = {
        "name": "Vice Fist",
        "damage": 1,
        "footprint_tiles": [[1, 0]],
        "push_directions": ["west"],
        "confidence": 0.5,  # equal to default floor → suppressed
    }
    mm = comparator.compare_weapon(parsed)
    assert mm == []


# ── passive sanity ──────────────────────────────────────────────────────────


def test_passive_weapon_with_no_damage_produces_no_mismatch():
    # Passive: damage=0, no footprint, no push. A clean read = no flags.
    parsed = vision.parse_weapon_preview({
        "name": "Electric Smoke",  # Passive_Electric display name
        "damage": 0,
        "footprint_tiles": [],
        "push_directions": [],
        "description": "PASSIVE: smoke tiles damage enemies.",
        "weapon_class": "Passive",
    })
    # If the display name isn't in WEAPON_DEFS (passives use various
    # names), the unknown_weapon branch handles it. We just check
    # there's no false-positive "missing damage" flag.
    mm = comparator.compare_weapon(parsed)
    assert not any(m["field"] == "damage" for m in mm)


# ── JSONL writer ────────────────────────────────────────────────────────────


def test_append_mismatches_round_trips_each_record(tmp_path: Path):
    path = tmp_path / "mm.jsonl"
    mismatches = [
        {
            "weapon_id": "Prime_Shift",
            "display_name": "Vice Fist",
            "field": "damage",
            "rust_value": 1,
            "vision_value": 5,
            "severity": "high",
            "confidence": 1.0,
        },
        {
            "weapon_id": "Prime_Shift",
            "display_name": "Vice Fist",
            "field": "footprint_size",
            "rust_value": "[1,1]",
            "vision_value": 4,
            "severity": "medium",
            "confidence": 1.0,
        },
    ]
    n = comparator.append_mismatches(mismatches, path=path, run_id="RUN42")
    assert n == 2

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    rec0 = json.loads(lines[0])
    assert rec0["weapon_id"] == "Prime_Shift"
    assert rec0["field"] == "damage"
    assert rec0["run_id"] == "RUN42"
    assert "timestamp" in rec0
    assert rec0["severity"] == "high"


def test_append_mismatches_is_append_only(tmp_path: Path):
    path = tmp_path / "mm.jsonl"
    comparator.append_mismatches([{"field": "x", "weapon_id": "a",
                                   "display_name": "", "rust_value": 0,
                                   "vision_value": 0, "severity": "low",
                                   "confidence": 1.0}], path=path)
    comparator.append_mismatches([{"field": "y", "weapon_id": "b",
                                   "display_name": "", "rust_value": 0,
                                   "vision_value": 0, "severity": "low",
                                   "confidence": 1.0}], path=path)
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_compare_and_log_no_mismatch_writes_nothing(tmp_path: Path):
    path = tmp_path / "mm.jsonl"
    parsed = vision.parse_weapon_preview({
        "name": "Vice Fist",
        "damage": 1,
        "footprint_tiles": [[1, 0]],
        "push_directions": ["west"],
        "description": "d",
    })
    out = comparator.compare_and_log(parsed, path=path)
    assert out == []
    assert not path.exists()


def test_compare_and_log_writes_on_mismatch(tmp_path: Path):
    path = tmp_path / "mm.jsonl"
    parsed = vision.parse_weapon_preview({
        "name": "Vice Fist",
        "damage": 99,
        "footprint_tiles": [[1, 0]],
        "push_directions": ["west"],
        "description": "d",
    })
    out = comparator.compare_and_log(parsed, path=path, run_id="r1")
    assert out
    assert path.exists()
    rec = json.loads(path.read_text().strip().split("\n")[0])
    assert rec["run_id"] == "r1"
    assert rec["field"] == "damage"
