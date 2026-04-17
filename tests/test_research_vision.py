"""Phase 2 #P2-4 Vision parser tests.

The parsers are the contract boundary between Claude Vision output
and the downstream weapon-def comparator. Vision sometimes wraps JSON
in markdown fences, embeds it in prose, or uses close-but-not-canonical
field names — the parsers MUST coerce all of that into a predictable
shape so the comparator can diff without caring.

Tests cover:

1. ``_extract_json`` handles markdown fences, prose prefixes, and
   malformed input without crashing.
2. Each parser produces the right shape on a clean input AND degrades
   gracefully on missing fields.
3. ``parse_weapon_preview`` — the regression harness input — correctly
   normalizes footprint_tiles from several input shapes, and emits
   a confidence score that makes wiki fallback decisions sensible.
4. ``should_fall_back_to_wiki`` behaves at the confidence threshold.
"""

from __future__ import annotations

from src.research import vision


# ── _extract_json ────────────────────────────────────────────────────────────


def test_extract_json_clean_object():
    assert vision._extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_markdown_fence():
    txt = "```json\n{\"a\": 1}\n```"
    assert vision._extract_json(txt) == {"a": 1}


def test_extract_json_strips_prose_prefix():
    txt = "Here's the extraction:\n{\"name\": \"Vice Fist\"}"
    assert vision._extract_json(txt) == {"name": "Vice Fist"}


def test_extract_json_returns_none_on_malformed():
    assert vision._extract_json("") is None
    assert vision._extract_json("nothing json here") is None
    assert vision._extract_json("{not valid json") is None


def test_extract_json_handles_nested_braces():
    txt = '{"outer": {"inner": 1}, "list": [1,2]}'
    result = vision._extract_json(txt)
    assert result == {"outer": {"inner": 1}, "list": [1, 2]}


# ── parse_name_tag ───────────────────────────────────────────────────────────


def test_parse_name_tag_full_mech():
    txt = ('{"name": "Judo Mech", "hp": 3, "move": 5, '
           '"class_icons": ["damages_mountain", "destroys_buildings"]}')
    out = vision.parse_name_tag(txt)
    assert out["name"] == "Judo Mech"
    assert out["hp"] == 3
    assert out["move"] == 5
    assert out["class_icons"] == ["damages_mountain", "destroys_buildings"]
    assert out["confidence"] >= 0.9


def test_parse_name_tag_enemy_no_move():
    txt = '{"name": "Firefly Leader", "hp": 3, "move": null, "class_icons": []}'
    out = vision.parse_name_tag(txt)
    assert out["name"] == "Firefly Leader"
    assert out["move"] is None
    # Name + hp give >0.7 confidence even without class icons.
    assert out["confidence"] >= 0.7


def test_parse_name_tag_missing_name_low_confidence():
    out = vision.parse_name_tag('{"hp": 3}')
    assert out["name"] == ""
    assert out["confidence"] < 0.5


def test_parse_name_tag_accepts_dict_directly():
    # Callers that already have a parsed dict shouldn't round-trip via str.
    out = vision.parse_name_tag({"name": "X", "hp": 1, "move": 2})
    assert out["name"] == "X"
    assert out["hp"] == 1


# ── parse_unit_status ────────────────────────────────────────────────────────


def test_parse_unit_status_mech():
    txt = ('{"kind": "mech", "pilot_name": "Charlie Ferry", '
           '"weapon_slot_count": 2}')
    out = vision.parse_unit_status(txt)
    assert out["kind"] == "mech"
    assert out["pilot_name"] == "Charlie Ferry"
    assert out["weapon_slot_count"] == 2
    assert out["confidence"] >= 0.9


def test_parse_unit_status_enemy_no_pilot():
    out = vision.parse_unit_status(
        '{"kind": "enemy", "pilot_name": null, "weapon_slot_count": 0}'
    )
    assert out["kind"] == "enemy"
    assert out["pilot_name"] is None
    assert out["weapon_slot_count"] == 0


def test_parse_unit_status_clamps_weapon_slot_count():
    out = vision.parse_unit_status(
        '{"kind": "mech", "weapon_slot_count": 99}'
    )
    assert out["weapon_slot_count"] == 2


def test_parse_unit_status_unknown_kind_lowers_confidence():
    out = vision.parse_unit_status('{"kind": "robot", "pilot_name": null}')
    assert out["kind"] == "unknown"
    assert out["confidence"] < 0.5


# ── parse_weapon_preview ────────────────────────────────────────────────────


_VICE_FIST_JSON = (
    '{'
    '"name": "Vice Fist", '
    '"weapon_class": "Prime Class Weapon", '
    '"description": "Grab a unit and toss it behind you.", '
    '"damage": 1, '
    '"footprint_tiles": [[1, 0]], '
    '"push_directions": ["west"], '
    '"upgrades": ["Ally Immune", "+2 Damage"]'
    '}'
)


def test_parse_weapon_preview_vice_fist_full_confidence():
    out = vision.parse_weapon_preview(_VICE_FIST_JSON)
    assert out["name"] == "Vice Fist"
    assert out["weapon_class"] == "Prime Class Weapon"
    assert out["damage"] == 1
    assert out["footprint_tiles"] == [(1, 0)]
    assert out["push_directions"] == ["west"]
    assert out["upgrades"] == ["Ally Immune", "+2 Damage"]
    # Name + class + description + damage + footprint + upgrades → full.
    assert out["confidence"] >= 0.9


def test_parse_weapon_preview_accepts_dict_footprint_entries():
    # Vision sometimes returns [{dx:1,dy:0}] instead of [[1,0]] —
    # parser must accept both shapes without penalty.
    raw = {
        "name": "W",
        "description": "d",
        "damage": 1,
        "footprint_tiles": [{"dx": 1, "dy": 0}, {"x": 0, "y": 1}],
        "push_directions": [],
        "upgrades": [],
    }
    out = vision.parse_weapon_preview(raw)
    assert (1, 0) in out["footprint_tiles"]
    assert (0, 1) in out["footprint_tiles"]


def test_parse_weapon_preview_normalizes_push_directions():
    raw = {"name": "W", "push_directions": ["N", "down", "garbage", "East"]}
    out = vision.parse_weapon_preview(raw)
    # N → north, down → south, East → east, garbage dropped.
    assert out["push_directions"] == ["north", "south", "east"]


def test_parse_weapon_preview_drops_confidence_on_coerced_footprint():
    # Each unparseable entry knocks confidence down.
    raw = {
        "name": "W",
        "description": "d",
        "damage": 1,
        "footprint_tiles": ["a", "b", "c"],  # three unparseable entries
        "push_directions": [],
        "upgrades": [],
    }
    out = vision.parse_weapon_preview(raw)
    assert out["footprint_tiles"] == []
    # With 3 coerced-garbage entries, -0.15; no footprint bonus.
    # Baseline: name(0.4) + description(0.15) + damage(0.1) = 0.65
    # After coercion penalty: <= 0.5.
    assert out["confidence"] <= 0.5


def test_parse_weapon_preview_missing_footprint_lowers_confidence():
    raw = {"name": "W", "description": "d", "damage": 1}
    out = vision.parse_weapon_preview(raw)
    assert out["footprint_tiles"] == []
    # No +0.25 footprint bonus → ceiling 0.65.
    assert out["confidence"] < 0.7


def test_parse_weapon_preview_passive_weapon_does_not_require_damage():
    # Passives (e.g. Charlie Ferry's +1 Reactor) have "Passive" in text
    # and no damage. Make sure the parser doesn't penalize that.
    raw = {
        "name": "Mech Reactor",
        "weapon_class": "Passive",
        "description": "PASSIVE: +1 Reactor Core to your Grid.",
        "damage": 0,
        "footprint_tiles": [],
        "push_directions": [],
        "upgrades": [],
    }
    out = vision.parse_weapon_preview(raw)
    assert out["name"] == "Mech Reactor"
    # Name + class + description + damage-credit for "passive" text
    # → at least 0.7.
    assert out["confidence"] >= 0.6


def test_parse_weapon_preview_empty_input_gives_zero_confidence():
    out = vision.parse_weapon_preview("")
    assert out["confidence"] == 0.0
    assert out["footprint_tiles"] == []


# ── parse_terrain_tooltip ───────────────────────────────────────────────────


def test_parse_terrain_tooltip_ground():
    out = vision.parse_terrain_tooltip(
        '{"terrain": "Ground Tile", "effect": "No special effect.", '
        '"status_effects": []}'
    )
    assert out["terrain"] == "Ground Tile"
    assert out["effect"] == "No special effect."
    assert out["status_effects"] == []
    assert out["confidence"] == 1.0


def test_parse_terrain_tooltip_with_status():
    out = vision.parse_terrain_tooltip(
        '{"terrain": "Water", "effect": "Drowns non-flying ground units.", '
        '"status_effects": ["Frozen"]}'
    )
    assert out["terrain"] == "Water"
    assert "Frozen" in out["status_effects"]


def test_parse_terrain_tooltip_no_terrain_low_confidence():
    out = vision.parse_terrain_tooltip('{"terrain": "", "effect": ""}')
    assert out["confidence"] == 0.0


# ── confidence gating ───────────────────────────────────────────────────────


def test_wiki_fallback_triggers_when_below_threshold():
    low = {"confidence": 0.3}
    assert vision.should_fall_back_to_wiki(low) is True


def test_wiki_fallback_suppressed_when_high_confidence():
    high = {"confidence": 0.9}
    assert vision.should_fall_back_to_wiki(high) is False


def test_wiki_fallback_triggers_at_exact_threshold():
    at = {"confidence": vision.CONFIDENCE_WIKI_FALLBACK}
    # <= is inclusive — at-threshold means "not trusted enough" → consult wiki.
    assert vision.should_fall_back_to_wiki(at) is True


# ── prompt sanity ────────────────────────────────────────────────────────────


def test_all_prompt_keys_match_parser_keys():
    assert set(vision.PROMPTS.keys()) == set(vision.PARSERS.keys())


def test_weapon_preview_prompt_asks_for_required_fields():
    # The prompt is what Claude sees — if it doesn't request a field,
    # the parser will never see it. Guard against drift between the
    # prompt and the parser contract.
    p = vision.PROMPT_WEAPON_PREVIEW.lower()
    for required in ("name", "damage", "footprint_tiles", "push_directions"):
        assert required in p, f"weapon_preview prompt missing field: {required}"
