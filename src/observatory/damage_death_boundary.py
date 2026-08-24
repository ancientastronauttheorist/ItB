"""Reproduce the exact-build native ``DAMAGE_DEATH`` pawn boundary.

The map follows the numeric sentinel from its Lua registration through
``SpaceDamage.iDamage``, pawn status handling, and the clamped HP delta.  It
deliberately stops at zero HP: corpse/removal timing, Lua ``OnKill`` dispatch,
and kill attribution remain separate runtime boundaries.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "damage_death_pawn_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class DamageDeathBoundaryError(RuntimeError):
    """Raised when the reviewed native boundary cannot be reproduced."""


SOURCE_SPECS = (
    {
        "path": "scripts/missions/final/env_final.lua",
        "size": 4_529,
        "sha256": "8d9220a9f7c0b6f3887ec8b9ffdd351b25cd4c53696d2f401c81dbeb932a6f33",
        "symbols": ["Env_Final:GetAttackEffect"],
        "required_fragments": [
            "local damage = SpaceDamage(location, DAMAGE_DEATH)",
            "damage.iTerrain = TERRAIN_ROAD",
            "damage.iTerrain = TERRAIN_LAVA",
        ],
        "meaning": (
            "Final Cave Rocks and tentacles construct ordinary SpaceDamage "
            "records with DAMAGE_DEATH before assigning Road or Lava."
        ),
    },
    {
        "path": "scripts/missions/final/env_volcano.lua",
        "size": 2_783,
        "sha256": "e3499feaaf71d01a78bd649915165ec1c6713d20baa39bb2ac12db7bb787ea16",
        "symbols": ["Env_Volcano:GetAttackEffect"],
        "required_fragments": [
            "local damage = SpaceDamage(location, DAMAGE_DEATH)",
            "damage.iFire = 1",
        ],
        "meaning": (
            "Surface-Final Rocks construct ordinary SpaceDamage records with "
            "DAMAGE_DEATH and Fire."
        ),
    },
)


REGION_SPECS = (
    (
        "value_bar_delta",
        0x000E0E90,
        0x000E0FD2,
        "f508bbcc78cab592433d1edfdbe4cf49e265c0056c0d287ab6de8abe1d792b8f",
        "Ghidra 12.1.3 clamped animated ValueBar delta routine.",
    ),
    (
        "apply_space_damage",
        0x00160110,
        0x001604BC,
        "1597eb6d490f3ae9ee95547a0caa83999502b4ba9c3423bc50b1dca7acc20210",
        "Previously reviewed Board SpaceDamage application body.",
    ),
    (
        "damage_core",
        0x001AC980,
        0x001AE080,
        "e6c2049faa497fb736263591ce7f102630148360777ac61bf1a5318a95819a28",
        "Ghidra 12.1.3 core tile/status SpaceDamage body.",
    ),
    (
        "pawn_receiver",
        0x0022CE50,
        0x0022D593,
        "a57d332833c5c936594c510a42cf5074b3e07c4b9941443d7bd3d588b09cd818",
        "Ghidra 12.1.3 Pawn SpaceDamage receiver.",
    ),
    (
        "hp_delta",
        0x0022F830,
        0x0022FE84,
        "6c1724c8f74c8f4996451df3a9bd9d4587c6bb0c4a8ff6be9130e72c42c0689b",
        "Ghidra 12.1.3 Pawn HP-delta and damage-feedback routine.",
    ),
    (
        "pawn_shield_setter",
        0x00236E80,
        0x00237351,
        "dbf3f11bce2f185f51f2f5fdcc2ad1859064fc5b90649fc5d465a3b6973f729f",
        "Ghidra 12.1.3 Pawn SetShield implementation.",
    ),
    (
        "pawn_frozen_setter",
        0x0023A200,
        0x0023A3F8,
        "40c7b221453e47c62a49ab57f89203a11f4598fa7fe7b239f2dd8b2411b1b452",
        "Ghidra 12.1.3 Pawn SetFrozen implementation.",
    ),
    (
        "pawn_acid_setter",
        0x0023D050,
        0x0023D0DE,
        "741ccbc17b3481a8c7777215f065274e086ac3302b5202472c5d6ff476d2ad3c",
        "Ghidra 12.1.3 Pawn SetAcid implementation.",
    ),
    (
        "pawn_kill",
        0x0023D2E0,
        0x0023D34B,
        "0a5d113dc0441f670a948a57ee4e3b07593815596b049075d3303ec3a7fd2903",
        "Ghidra 12.1.3 explicit Pawn Kill implementation used for contrast.",
    ),
    (
        "armor_predicate",
        0x0023F990,
        0x0023FA8C,
        "8944d71b556c5b8f6faf7422fbbcfd30ca629c20b6278b0652c3d6e2ec35eb16",
        "Ghidra 12.1.3 Pawn Armor predicate.",
    ),
    (
        "register_i_damage",
        0x0027ADF8,
        0x0027ADFF,
        "69def6baaf418ec286ee4cc6b44db912707c6cb95b9328a3173bb9e2eee9b895",
        "Instruction-aligned SpaceDamage iDamage field registration.",
    ),
    (
        "pawn_shield_registration",
        0x0027BFDB,
        0x0027BFFD,
        "2132c20fbc74550a0029eca24f0c537e5348d62f4fe2fc1c159252d49d288c7b",
        "Instruction-aligned Pawn SetShield registration.",
    ),
    (
        "pawn_acid_registration",
        0x0027C496,
        0x0027C4B8,
        "767288c58523a90f4b7d95d16e25d15f2e8d7244f3ac9e488312ef3e7bf8c744",
        "Instruction-aligned Pawn SetAcid registration.",
    ),
    (
        "pawn_frozen_registration",
        0x0027C784,
        0x0027C7A6,
        "9eae8b52ff02304cf2f837ce5729c48532fe47f9eccce82fbff21e8d1c6481a2",
        "Instruction-aligned Pawn SetFrozen registration.",
    ),
    (
        "damage_death_registration",
        0x0027FEA1,
        0x0027FEE2,
        "7cd70dd84bfa445e2c8ac91ddc268b47a6efef5f407268330bccf5bf1137e5bf",
        "Instruction-aligned Lua global registration for DAMAGE_DEATH.",
    ),
)


DATA_ANCHOR_SPECS = (
    ("armor_name", 0x00436408, b"Armor\0", "Armor property queried by the predicate."),
    ("set_acid_name", 0x004389C0, b"SetAcid\0", "Registered Pawn method name."),
    ("set_frozen_name", 0x004389C8, b"SetFrozen\0", "Registered Pawn method name."),
    ("i_damage_name", 0x00438A98, b"iDamage\0", "Registered SpaceDamage field name."),
    ("set_shield_name", 0x00438FA0, b"SetShield\0", "Registered Pawn method name."),
    ("damage_death_name", 0x004399D4, b"DAMAGE_DEATH\0", "Registered Lua sentinel name."),
)


METHOD_BINDING_SPECS = (
    (
        "pawn_set_shield",
        "set_shield_name",
        "pawn_shield_registration",
        "pawn_shield_setter",
        0x00236E80,
        "+0x8d4",
    ),
    (
        "pawn_set_frozen",
        "set_frozen_name",
        "pawn_frozen_registration",
        "pawn_frozen_setter",
        0x0023A200,
        "+0x8d1",
    ),
    (
        "pawn_set_acid",
        "set_acid_name",
        "pawn_acid_registration",
        "pawn_acid_setter",
        0x0023D050,
        "+0x8d3",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "damage_death_is_1000",
        "damage_death_registration",
        0x0027FEA1,
        "68d49983008d8d4cf6ffff518bc8e89c09ddff8bd88b4b08ff710468f0d8ffffff33ff15c0647d00ff73048b3b57ff15e4647d0068e8030000ff33ff158c647d00",
        "Register the DAMAGE_DEATH name and publish integer 1000 (0x3e8).",
    ),
    (
        "i_damage_is_record_offset_eight",
        "register_i_damage",
        0x0027ADF8,
        "6a0868988a8300",
        "Bind iDamage to SpaceDamage record offset +0x08.",
    ),
    (
        "tile_shield_special_values",
        "damage_core",
        0x001ACCE4,
        "8b45103df401000074073de8030000743f",
        "Recognize 500 and 1000 before the tile-level shield branch.",
    ),
    (
        "tile_shield_preserves_death",
        "damage_core",
        0x001ACD83,
        "8b45103df401000074073de80300007407c7451000000000",
        "Zero ordinary shielded damage but retain the 1000 sentinel.",
    ),
    (
        "pawn_shield_special_values",
        "pawn_receiver",
        0x0022CEDC,
        "81fff40100000f84b200000085ff0f8eaa00000081ffe8030000744f",
        "Route positive 1000 around the ordinary shield-zero assignment.",
    ),
    (
        "pawn_shield_is_cleared",
        "pawn_receiver",
        0x0022CF47,
        "6a008bcee8309f0000",
        "Call Pawn SetShield(false) while retaining DAMAGE_DEATH.",
    ),
    (
        "pawn_frozen_is_cleared_without_zeroing_death",
        "pawn_receiver",
        0x0022CF9A,
        "8a86d108000084c0742b81fff4010000742b85ff7e1f33c08bce81ffe8030000500f45f8897d10e83ad20000",
        "For a Frozen pawn, preserve only 1000 and call SetFrozen(false).",
    ),
    (
        "armor_reduces_positive_damage_by_one",
        "pawn_receiver",
        0x0022CFF2,
        "85c90f85ba0000008bcec68537ffffff01e88829010084c00f84830000008d4fffc78530ffffff0000000085c9898d38ffffff8d9530ffffff0f57c98d8538ffffff0f4ec28d8e3c1100008b3889bd38ffffff",
        "Query Armor, subtract one from positive damage, and clamp at zero.",
    ),
    (
        "acid_doubles_remaining_positive_damage",
        "pawn_receiver",
        0x0022D093,
        "8a86d308000084c0740803ff89bd38ffffff",
        "Read the Acid byte and double the post-Armor damage.",
    ),
    (
        "negative_hp_delta_handoff",
        "pawn_receiver",
        0x0022D470,
        "ffb53c0100008bc78bce6a01f7d850e8ac230000",
        "Negate effective damage and pass it to the Pawn HP-delta routine.",
    ),
    (
        "separate_building_terrain_kill_branch",
        "damage_core",
        0x001ADC71,
        "83bde4000000018bcb75416a01e8bd22ffff84c0742d6a018bcbe8b022ffff84c0740a8b83a00000008b08eb0233c96a00e839f60800",
        (
            "The core's direct Pawn:Kill call belongs to the separately reviewed "
            "Building-terrain occupant-removal branch, not the Pawn numeric-damage "
            "receiver-to-HP chain."
        ),
    ),
    (
        "hp_delta_uses_value_bar",
        "hp_delta",
        0x0022F899,
        "807d0c008d8ea408000088854bfdffff577407e8df15ebffeb098b86a4080000ff5004",
        "Apply the incoming delta to the Pawn's embedded ValueBar.",
    ),
    (
        "negative_value_bar_delta_clamps_at_zero",
        "value_bar_delta",
        0x000E0EB8,
        "8bf18b7d088d45f08b5e0485ff79118bd38d4d08f7da3bfa8955f00f4dc1eb108b4e088d55082bcb3bcf894df00f4dc28b3833c9c74508000000008d043b894604",
        "Cap a negative delta at minus-current before committing the new value.",
    ),
    (
        "shield_field_is_setter_owned",
        "pawn_shield_setter",
        0x002372C6,
        "83beb000000001c686d408000000",
        "The registered SetShield implementation clears Pawn+0x8d4.",
    ),
    (
        "frozen_field_is_setter_owned",
        "pawn_frozen_setter",
        0x0023A3B6,
        "518bcfe8f2d0e4ff889ed1080000",
        "The registered SetFrozen implementation commits Pawn+0x8d1.",
    ),
    (
        "acid_field_is_setter_owned",
        "pawn_acid_setter",
        0x0023D0C8,
        "84db0f8585000000889ed30800005e5b",
        "The registered SetAcid implementation commits Pawn+0x8d3.",
    ),
)


DIRECT_EDGE_SPECS = (
    ("apply_calls_damage_core", "apply_space_damage", 0x001602E5, "e896c60400", "damage_core", 0x001AC980),
    ("core_calls_pawn_receiver", "damage_core", 0x001AD07E, "e8cdfd0700", "pawn_receiver", 0x0022CE50),
    ("receiver_queries_armor", "pawn_receiver", 0x0022D003, "e888290100", "armor_predicate", 0x0023F990),
    ("receiver_clears_shield", "pawn_receiver", 0x0022CF4B, "e8309f0000", "pawn_shield_setter", 0x00236E80),
    ("receiver_clears_frozen", "pawn_receiver", 0x0022CFC1, "e83ad20000", "pawn_frozen_setter", 0x0023A200),
    ("receiver_calls_hp_delta", "pawn_receiver", 0x0022D47F, "e8ac230000", "hp_delta", 0x0022F830),
    ("hp_delta_calls_value_bar", "hp_delta", 0x0022F8AC, "e8df15ebff", "value_bar_delta", 0x000E0E90),
    (
        "building_terrain_branch_calls_pawn_kill",
        "damage_core",
        0x001ADCA2,
        "e839f60800",
        "pawn_kill",
        0x0023D2E0,
    ),
)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise DamageDeathBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise DamageDeathBoundaryError("reviewed direct edge is not x86 CALL rel32")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "basis": basis,
        }
        for region_id, start, end, digest, basis in REGION_SPECS
    ]


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "symbols": spec["symbols"],
            "meaning": spec["meaning"],
        }
        for spec in SOURCE_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "rva": f"0x{rva:08x}",
            "hex": raw.hex(),
            "meaning": meaning,
        }
        for anchor_id, rva, raw, meaning in DATA_ANCHOR_SPECS
    ]


def _method_binding_records() -> list[dict[str, Any]]:
    return [
        {
            "id": method_id,
            "name_anchor": name_anchor,
            "registration_region": registration_region,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
            "status_field_offset": field_offset,
        }
        for (
            method_id,
            name_anchor,
            registration_region,
            target_region,
            target_rva,
            field_offset,
        ) in METHOD_BINDING_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region": region_id,
            "start_rva": f"0x{start:08x}",
            "hex": encoded,
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{from_rva:08x}",
            "instruction_hex": instruction_hex,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
        }
        for (
            edge_id,
            source_region,
            from_rva,
            instruction_hex,
            target_region,
            target_rva,
        ) in DIRECT_EDGE_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "sentinel": {
            "lua_name": "DAMAGE_DEATH",
            "native_integer": 1000,
            "hex": "0x000003e8",
            "space_damage_field": "iDamage",
            "record_offset": "+0x08",
            "implementation_kind": (
                "special numeric damage through the Pawn receiver; the core's "
                "separate Building-terrain branch can call Pawn:Kill directly"
            ),
        },
        "pawn_status_order": {
            "ordered_steps": [
                "Shield side effect and SetShield(false)",
                "Frozen side effect and SetFrozen(false)",
                "Armor predicate and minus one with zero clamp",
                "Acid doubling",
                "negative HP delta",
            ],
            "shield_zeroes_damage_1000": False,
            "frozen_zeroes_damage_1000": False,
            "armored_damage_from_1000": 999,
            "acid_armored_damage_from_1000": 1998,
            "flight_test_in_generic_receiver": False,
            "massive_test_in_generic_receiver": False,
        },
        "hp_handoff": {
            "receiver_argument": "negative effective damage",
            "target": "Pawn embedded clamped ValueBar",
            "negative_delta_floor": "minus current HP",
            "zero_hp_when_current_hp_lte_effective_damage": True,
            "direct_pawn_kill_call_in_receiver_to_hp_chain": False,
            "separate_building_terrain_pawn_kill_call": True,
            "proven_terminal_boundary": "HP reaches zero",
        },
        "final_environment_join": {
            "final_cave_source_uses_sentinel": True,
            "volcano_rocks_source_uses_sentinel": True,
            "flying_immunity_in_generic_receiver": False,
            "massive_immunity_in_generic_receiver": False,
            "shield_or_frozen_survival_for_stock_hp": False,
            "current_rust_terminal_state_outcome_equivalent": True,
        },
        "scope_limit": {
            "corpse_or_removal_timing_proven": False,
            "lua_on_kill_dispatch_proven": False,
            "kill_credit_or_owner_attribution_proven": False,
            "specialized_subclass_overrides_exhausted": False,
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "damage_death_is_numeric_sentinel_1000",
            "classification": "fact",
            "claim": (
                "The exact Lua registration publishes DAMAGE_DEATH as 1000, "
                "and SpaceDamage registration binds iDamage at record +0x08."
            ),
        },
        {
            "id": "shield_and_frozen_do_not_absorb_damage_death",
            "classification": "fact",
            "claim": (
                "The Pawn receiver recognizes 1000 specially, clears Shield "
                "and Frozen through their registered setters, and preserves "
                "the positive sentinel instead of zeroing it."
            ),
        },
        {
            "id": "armor_and_acid_transform_but_do_not_cancel",
            "classification": "fact",
            "claim": (
                "Armor can reduce 1000 to 999 and Acid can double the "
                "remaining value; the native path is arithmetic rather than "
                "a literal bypass of those statuses."
            ),
        },
        {
            "id": "generic_receiver_has_no_flight_or_massive_immunity",
            "classification": "inference",
            "claim": (
                "The complete reviewed receiver has no flying or Massive "
                "predicate on this path, so those traits do not rescue an "
                "ordinary pawn from the sentinel HP delta."
            ),
        },
        {
            "id": "damage_death_reaches_clamped_hp_zero_boundary",
            "classification": "fact",
            "claim": (
                "The receiver negates effective damage, hands it to the Pawn "
                "HP routine, and the ValueBar clamps a negative delta at "
                "minus-current HP; sufficiently large sentinel damage reaches "
                "zero HP."
            ),
        },
        {
            "id": "direct_kill_edge_is_a_separate_terrain_branch",
            "classification": "inference",
            "claim": (
                "The one direct Pawn:Kill target in the reviewed core is the "
                "already-mapped Building-terrain occupant-removal branch. The "
                "Pawn numeric-damage receiver and HP-delta routine contain no "
                "direct call to Pawn:Kill."
            ),
        },
        {
            "id": "current_final_environment_outcome_is_conformant",
            "classification": "inference",
            "claim": (
                "For stock solver-supported Final Cave and Volcano pawn HP, "
                "the Rust terminal state is outcome-equivalent. No simulator "
                "semantic change follows from this boundary."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "zero_hp_corpse_and_removal_timing",
            "question": "When and how does each pawn class settle zero HP into corpse or removal state?",
            "next_evidence": "Trace the zero-HP consumer and Corpse predicate for ordinary and specialized pawns.",
        },
        {
            "id": "on_kill_callback_dispatch",
            "question": "Which native edge dispatches Lua OnKill after this HP-zero route?",
            "next_evidence": "Map the runtime callback dispatcher rather than the existing OnKill binding registrations.",
        },
        {
            "id": "kill_credit_and_owner_attribution",
            "question": "What source/team/owner credit is assigned to an environment DAMAGE_DEATH?",
            "next_evidence": "Trace copied SpaceDamage attribution fields into mission and achievement counters.",
        },
        {
            "id": "specialized_pawn_subclass_tail",
            "question": "Can any specialized pawn subclass alter the zero-HP tail without altering this receiver?",
            "next_evidence": "Inventory the zero-HP virtual consumers and corpse/death overrides by vtable.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows depots implement the same boundary?",
            "next_evidence": "Repeat the build-keyed inventory on another exact executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "architecture": "x86",
            "bits": 32,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
        },
        "sources": _source_records(),
        "regions": _region_records(),
        "data_anchors": _data_anchor_records(),
        "method_bindings": _method_binding_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "contracts": _contracts(),
        "findings": findings,
        "refines": {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_cave_drop_resolution.json"
            ),
            "unresolved_id": "death_damage_callbacks_and_attribution",
            "qualification": (
                "The numeric sentinel, status arithmetic, and HP-zero handoff "
                "are now exact; corpse/removal timing, OnKill, and attribution "
                "remain open sub-boundaries."
            ),
        },
        "unresolved": unresolved,
        "solver_impact": {
            "terminal_state_contradiction": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "precision_correction": (
                "Describe native DAMAGE_DEATH as Shield/Frozen cleanup plus "
                "Armor/Acid arithmetic and a clamped HP delta, not as a literal "
                "bypass of every status."
            ),
            "reason": (
                "The current direct lethal projection reaches the same stock "
                "terminal HP and cleared Shield/Frozen state."
            ),
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "A conditional emerge/spawn dispatcher at core +0x1526 is not claimed as the generic zero-HP death tail.",
            (
                "The reviewed core contains one direct PawnKill edge in its "
                "separate Building-terrain branch; neither the Pawn receiver nor "
                "the HP-delta routine directly calls PawnKill."
            ),
        ],
        "summary": {
            "source_count": len(SOURCE_SPECS),
            "region_count": len(REGION_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "method_binding_count": len(METHOD_BINDING_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "hp_zero_boundary_proven": True,
            "callback_or_credit_tail_proven": False,
            "simulator_change_required": False,
        },
    }


def _verify_sources(content_root: Path) -> None:
    for spec in SOURCE_SPECS:
        path = content_root / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise DamageDeathBoundaryError(f"source is unavailable: {spec['path']}")
        data = path.read_bytes()
        if len(data) != spec["size"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise DamageDeathBoundaryError(f"source identity differs: {spec['path']}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DamageDeathBoundaryError(f"source is not UTF-8: {spec['path']}") from exc
        for fragment in spec["required_fragments"]:
            if fragment not in text:
                raise DamageDeathBoundaryError(
                    f"source fragment differs: {spec['path']}:{fragment}"
                )


def build_damage_death_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build DAMAGE_DEATH pawn boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise DamageDeathBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise DamageDeathBoundaryError("executable identity differs")

    _verify_sources(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    region_bytes: dict[str, bytes] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        try:
            body = _region_bytes(image, data, start, end - start, ".text", region_id)
        except Exception as exc:
            raise DamageDeathBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise DamageDeathBoundaryError(f"region {region_id} bytes differ")
        ranges[region_id] = (start, end)
        region_bytes[region_id] = body
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise DamageDeathBoundaryError(str(exc)) from exc

    anchors = {
        anchor_id: (rva, raw)
        for anchor_id, rva, raw, _meaning in DATA_ANCHOR_SPECS
    }
    for anchor_id, rva, raw, _meaning in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise DamageDeathBoundaryError(f"data anchor {anchor_id} differs")

    i_damage_body = region_bytes["register_i_damage"]
    i_damage_rva, _ = anchors["i_damage_name"]
    if (
        b"\x6a\x08" not in i_damage_body
        or struct.pack("<I", image.image_base + i_damage_rva) not in i_damage_body
    ):
        raise DamageDeathBoundaryError("iDamage field binding differs")

    registration = region_bytes["damage_death_registration"]
    death_name_rva, _ = anchors["damage_death_name"]
    if (
        struct.pack("<I", image.image_base + death_name_rva) not in registration
        or b"\x68\xe8\x03\x00\x00" not in registration
    ):
        raise DamageDeathBoundaryError("DAMAGE_DEATH registration differs")

    for (
        method_id,
        name_anchor,
        registration_region,
        _target_region,
        target_rva,
        _field_offset,
    ) in METHOD_BINDING_SPECS:
        name_rva, _ = anchors[name_anchor]
        body = region_bytes[registration_region]
        if (
            struct.pack("<I", image.image_base + name_rva) not in body
            or struct.pack("<I", image.image_base + target_rva) not in body
        ):
            raise DamageDeathBoundaryError(f"method binding {method_id} differs")

    armor_rva, _ = anchors["armor_name"]
    if struct.pack("<I", image.image_base + armor_rva) not in region_bytes["armor_predicate"]:
        raise DamageDeathBoundaryError("Armor predicate name anchor differs")

    region_by_id = {
        region_id: (start, end)
        for region_id, start, end, _digest, _basis in REGION_SPECS
    }
    for window_id, region_id, start, instruction_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(instruction_hex)
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise DamageDeathBoundaryError(f"control window {window_id} differs")
        region_start, region_end = region_by_id[region_id]
        if not (region_start <= start < start + len(expected) <= region_end):
            raise DamageDeathBoundaryError(f"control window {window_id} escapes region")
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded[region_id].get(cursor)
            if instruction is None:
                raise DamageDeathBoundaryError(
                    f"control window {window_id} is not instruction-aligned"
                )
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise DamageDeathBoundaryError(
                f"control window {window_id} ends inside an instruction"
            )

    for (
        edge_id,
        source_region,
        from_rva,
        instruction_hex,
        target_region,
        target_rva,
    ) in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(instruction_hex)
        instruction = decoded[source_region].get(from_rva)
        if instruction is None or instruction[1] != expected:
            raise DamageDeathBoundaryError(f"direct edge {edge_id} bytes differ")
        if _direct_target(from_rva, expected) != target_rva:
            raise DamageDeathBoundaryError(f"direct edge {edge_id} target differs")
        if target_rva not in decoded[target_region]:
            raise DamageDeathBoundaryError(
                f"direct edge {edge_id} target is not an instruction"
            )

    pawn_kill_rva = region_by_id["pawn_kill"][0]
    direct_kill_edges: dict[str, set[int]] = {}
    for region_id in ("damage_core", "pawn_receiver", "hp_delta"):
        direct_kill_edges[region_id] = {
            rva
            for rva, (_mnemonic, encoded) in decoded[region_id].items()
            if len(encoded) == 5
            and encoded[0] == 0xE8
            and _direct_target(rva, encoded) == pawn_kill_rva
        }
    expected_kill_edges = {
        "damage_core": {0x001ADCA2},
        "pawn_receiver": set(),
        "hp_delta": set(),
    }
    if direct_kill_edges != expected_kill_edges:
        raise DamageDeathBoundaryError(
            "direct PawnKill edge inventory differs from reviewed boundary"
        )

    return _expected_shape()


def validate_damage_death_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise DamageDeathBoundaryError("DAMAGE_DEATH boundary fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "hp_zero_boundary_proven": True,
        "callback_or_credit_tail_proven": False,
        "simulator_change_required": False,
    }


def validate_damage_death_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, edge, or prose drift."""
    expected = build_damage_death_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise DamageDeathBoundaryError(
            "DAMAGE_DEATH boundary differs from exact-build analysis"
        )
    result = validate_damage_death_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_damage_death_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
