"""Reproduce the exact-build zero-HP Board cleanup boundary.

This continuation starts at the clamped Pawn HP-zero boundary, follows the
later same-routine virtual ``IsDead`` classification, and maps the conditional
Board-vector erase path.  It also inventories every absolute ``OnKill`` and
selected attribution/counter-name reference in the exact executable.  The map
is deliberately honest about the remaining seam: static references are not a
runtime Lua callback, kill-credit, or scheduler-timing proof.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.damage_death_boundary import (
    DamageDeathBoundaryError,
    validate_damage_death_boundary_map,
)
from src.observatory.path_occupancy_lifecycle import (
    PathOccupancyLifecycleError,
    validate_path_occupancy_lifecycle_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_zero_hp_cleanup_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class ZeroHpCleanupBoundaryError(RuntimeError):
    """Raised when the reviewed cleanup boundary cannot be reproduced."""


DEPENDENCY_SPECS = (
    (
        "damage_death_pawn_boundary",
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json",
        "af4cc9de107ab8e7c739e480ec1efda0a477db9c264bbef3452331a95f242ea1",
        "e9a1a70eae208851cb62bc2e022c97825a889beffa6322c02dfb7668c0de1af3",
        "Pins DAMAGE_DEATH status arithmetic and the clamped HP-zero handoff.",
    ),
    (
        "path_occupancy_lifecycle",
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json",
        "fb0537726b65a506f9548444c90e4e17a1ea2d201f60a04ad7ff728072629805",
        "2960b1ca1f48bb31faf9c684d86e868683ae934609612ded65beb61967f6859c",
        "Pins IsDead/IsCorpse bindings and live-or-persistent-corpse path occupancy.",
    ),
)


REGION_SPECS = (
    (
        "primary_sweep_caller",
        0x0016A8D0,
        0x0016BF62,
        "6d32a302492920ae4353af4505e792776a18c4f9d8c26bd6cf1f9861a6f9129d",
        True,
        "Ghidra 12.1.3 complete primary caller containing the reviewed sweep edge.",
    ),
    (
        "board_cleanup_sweep",
        0x0019E490,
        0x0019F78A,
        "ce761f3b9b4f96239fd5b5eb55a3f8d806d144206c3eac74543ba6f77f683b62",
        True,
        "Ghidra 12.1.3 complete Board sweep containing the pawn-vector erase path.",
    ),
    (
        "board_pawn_vector_find",
        0x001A00F0,
        0x001A0143,
        "750e2639c3de4cd54e49093e4af9ce0336bcbf5848fe711b445387ffbdbc3252",
        True,
        "Complete Board pawn-vector pointer-to-index search through both returns.",
    ),
    (
        "secondary_sweep_caller",
        0x001E9E60,
        0x001E9FED,
        "df8834614d7cbe4805e1b15558066807885750372e50b36a1b1e26552be1e5ec",
        True,
        "Ghidra 12.1.3 complete secondary iteration caller containing the sweep edge.",
    ),
    (
        "damage_core",
        0x001AC980,
        0x001AE080,
        "e6c2049faa497fb736263591ce7f102630148360777ac61bf1a5318a95819a28",
        True,
        "Dependency-pinned generic SpaceDamage core searched for direct callback edges.",
    ),
    (
        "iowner_reader_a",
        0x00229820,
        0x0022991F,
        "ed82578b7a5100850869ad88ec99737018446faa7eb6be317bc5f6b8e701b485",
        False,
        "Ghidra 12.1.3 function containing the first iOwner name reference.",
    ),
    (
        "iowner_reader_b",
        0x00229920,
        0x00229B03,
        "687bb097bfc332c01c8aaf445dc93deed489914dab6da209856f7dfe013da758",
        False,
        "Ghidra 12.1.3 function containing the second iOwner name reference.",
    ),
    (
        "pawn_is_corpse",
        0x0022CDE0,
        0x0022CE47,
        "806702601f6a75193f6479e0357150d5264c10b7661a434bac7eeb1a807606c7",
        True,
        "Complete native Pawn IsCorpse predicate through RET.",
    ),
    (
        "pawn_receiver",
        0x0022CE50,
        0x0022D593,
        "a57d332833c5c936594c510a42cf5074b3e07c4b9941443d7bd3d588b09cd818",
        True,
        "Dependency-pinned Pawn damage receiver searched for direct callback edges.",
    ),
    (
        "pawn_hp_delta",
        0x0022F830,
        0x0022FE84,
        "6c1724c8f74c8f4996451df3a9bd9d4587c6bb0c4a8ff6be9130e72c42c0689b",
        True,
        "Complete Pawn HP-delta routine including pre/post IsDead classification.",
    ),
    (
        "pawn_kill",
        0x0023D2E0,
        0x0023D34B,
        "0a5d113dc0441f670a948a57ee4e3b07593815596b049075d3303ec3a7fd2903",
        True,
        "Dependency-pinned explicit Pawn Kill implementation searched for direct callback edges.",
    ),
    (
        "pawn_definition_load",
        0x0023FB40,
        0x00240ACF,
        "b3475222468769a173264dd29a9bb00d3980f563b0c4bb9243875b844450d270",
        False,
        "Ghidra 12.1.3 definition-loading function containing named death/counter fields.",
    ),
    (
        "pawn_definition_store",
        0x00240AE0,
        0x0024209E,
        "92ad8d746d427511dbd27a845faa17d22240a8fe703d48c10a4b92e85aacd3f9",
        False,
        "Ghidra 12.1.3 definition-writing function containing named death/counter fields.",
    ),
    (
        "onkill_property_reader",
        0x0026CE10,
        0x00270608,
        "99c1dcb0826e4e11689f229c9b3815733b396a7fc70df9c9140d954b40d54162",
        False,
        "Ghidra 12.1.3 function containing two OnKill property-name references.",
    ),
    (
        "onkill_property_writer",
        0x00270610,
        0x00271C3B,
        "bd354b437ad4d0ae23eb648350b2a2aee9f11961dcca9bf1a6df15657475675d",
        False,
        "Ghidra 12.1.3 function containing two OnKill property-name references.",
    ),
    (
        "pawn_binding_table",
        0x00279880,
        0x002816B6,
        "51f3a81b7b832098c11f81beb1c85e1fe488434adce745dd8af5cb5af64200c2",
        False,
        "Ghidra 12.1.3 Pawn/global binding table containing EVENT_ENEMY_KILLED.",
    ),
    (
        "iowner_binding",
        0x002838D0,
        0x00283963,
        "d0b1ba039795a65addbdc54ded073f92aacfed4623ef8ad03e0f504afd154733",
        False,
        "Ghidra 12.1.3 function containing the third iOwner name reference.",
    ),
    (
        "pawn_is_dead_thunk",
        0x002E39A2,
        0x002E39A7,
        "2583df412e7df54ae54a5b27baf8262583a3e4de9ed4ddfd2fef4f3209c53670",
        True,
        "Complete registered Pawn IsDead virtual thunk at vtable slot +0x10.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "hp_existing_dead_noncorpse_guard",
        "pawn_hp_delta",
        0x0022F860,
        "8b068b4010ffd084c0740f8bcee86ed5ffff84c00f84ec050000",
        "An already-dead non-corpse exits before another HP delta is applied.",
    ),
    (
        "hp_post_delta_isdead_classification",
        "pawn_hp_delta",
        0x0022FDCA,
        "8b068bce8b4010ffd084c07429",
        "After the HP update, dispatch vtable slot +0x10 and branch on IsDead.",
    ),
    (
        "pawn_iscorpse_nontrivial_predicate",
        "pawn_is_corpse",
        0x0022CDE0,
        "5180b9e409000000750980b9800f00000074158b81e009000083f803740a83f802740583f804753b83b9e81000000c7423a154568d008b1558568d003bc2741f83380c740b83c0043bc275f432c059c33bc2740b6a0ce86508010084c0750432c059c3b00159c3",
        "IsCorpse uses several Pawn fields plus a constant-12 global/predicate path; it is not a single byte alias.",
    ),
    (
        "dead_noncorpse_cleanup_predicate",
        "board_cleanup_sweep",
        0x0019EF50,
        "8b86a00000008d3c8d000000008b1c3880bb25130000000f85bc00000080bb22090000000f85af00000080bb21090000000f85a20000008b038bcb8b4010ffd084c00f84910000008b837408000080b89e0600000075188a805c06000084c075788b83c41000003b83c8100000756a8a836409000084c075608bcbe810de080084c07555",
        "Require cleared state gates, virtual IsDead true, definition/state gates, Pawn+0x964 clear, and direct IsCorpse false before erase.",
    ),
    (
        "board_pawn_vector_erase",
        "board_cleanup_sweep",
        0x0019EFD4,
        "8b86a00000008b0407c686302600000185c0742e508bcee8001100003dffffff7f74268b8ea00000008b96a40000008d04818d48042bd1525150e86df51c0083c40c8386a4000000fc",
        "Mark Board cleanup, find the selected pointer, compact its tail when found, and decrement the pawn-vector end by four bytes.",
    ),
    (
        "board_pawn_vector_find_contract",
        "board_pawn_vector_find",
        0x001A00F0,
        "558bec568bf133d2578b86a40000002b86a0000000c1f80285c074248b8ea00000008b7d08393974228b86a4000000422b86a000000083c104c1f8023bd072e55fb8ffffff7f5e5dc204005f8bc25e5dc20400",
        "Search Board+[0xa0,0xa4) for the exact pointer and return its index or INT_MAX.",
    ),
    (
        "pawn_isdead_virtual_thunk",
        "pawn_is_dead_thunk",
        0x002E39A2,
        "8b01ff6010",
        "The registered IsDead thunk dispatches through Pawn vtable slot +0x10.",
    ),
)


DIRECT_EDGE_SPECS = (
    (
        "primary_caller_calls_cleanup_sweep",
        "primary_sweep_caller",
        0x0016AE58,
        "e833360300",
        "board_cleanup_sweep",
        0x0019E490,
    ),
    (
        "secondary_caller_calls_cleanup_sweep",
        "secondary_sweep_caller",
        0x001E9FB5,
        "e8d644fbff",
        "board_cleanup_sweep",
        0x0019E490,
    ),
    (
        "hp_existing_dead_guard_calls_iscorpse",
        "pawn_hp_delta",
        0x0022F86D,
        "e86ed5ffff",
        "pawn_is_corpse",
        0x0022CDE0,
    ),
    (
        "cleanup_sweep_calls_iscorpse",
        "board_cleanup_sweep",
        0x0019EFCB,
        "e810de0800",
        "pawn_is_corpse",
        0x0022CDE0,
    ),
    (
        "cleanup_sweep_finds_vector_index",
        "board_cleanup_sweep",
        0x0019EFEB,
        "e800110000",
        "board_pawn_vector_find",
        0x001A00F0,
    ),
    (
        "cleanup_sweep_compacts_pointer_tail",
        "board_cleanup_sweep",
        0x0019F00E,
        "e86df51c00",
        None,
        0x0036E580,
    ),
)


ABSOLUTE_REFERENCE_SPECS = (
    (
        "i_owner_name",
        0x00435E90,
        b"iOwner\0",
        (
            ("iowner_reader_a", 0x0022984E, "68905e8300", 1),
            ("iowner_reader_b", 0x0022994E, "68905e8300", 1),
            ("iowner_binding", 0x00283913, "c74208905e8300", 3),
        ),
        "Three exact iOwner name references; this is not a kill-credit flow.",
    ),
    (
        "owner_name",
        0x00436CFC,
        b"owner\0",
        (
            ("pawn_definition_load", 0x0023FD78, "68fc6c8300", 1),
            ("pawn_definition_store", 0x00240CCB, "68fc6c8300", 1),
        ),
        "Definition load/store name references.",
    ),
    (
        "death_seed_name",
        0x00436D14,
        b"death_seed\0",
        (
            ("pawn_definition_load", 0x0023FDDF, "68146d8300", 1),
            ("pawn_definition_store", 0x00240D7B, "68146d8300", 1),
        ),
        "Definition load/store name references.",
    ),
    (
        "is_corpse_field_name",
        0x00436E68,
        b"is_corpse\0",
        (
            ("pawn_definition_load", 0x0024065D, "68686e8300", 1),
            ("pawn_definition_store", 0x00240D19, "68686e8300", 1),
        ),
        "Definition load/store name references distinct from Pawn:IsCorpse dispatch.",
    ),
    (
        "i_kills_name",
        0x00436E74,
        b"iKills\0",
        (
            ("pawn_definition_load", 0x00240611, "68746e8300", 1),
            ("pawn_definition_store", 0x0024198A, "68746e8300", 1),
        ),
        "Definition load/store name references, not a proven increment site.",
    ),
    (
        "i_mission_damage_name",
        0x00436EA4,
        b"iMissionDamage\0",
        (
            ("pawn_definition_load", 0x00240754, "68a46e8300", 1),
            ("pawn_definition_store", 0x00241F14, "68a46e8300", 1),
        ),
        "Definition load/store name references, not a proven update site.",
    ),
    (
        "i_kill_count_name",
        0x00436F58,
        b"iKillCount\0",
        (
            ("pawn_definition_load", 0x00240957, "68586f8300", 1),
            ("pawn_definition_store", 0x00241B97, "68586f8300", 1),
        ),
        "Definition load/store name references, not a proven update site.",
    ),
    (
        "on_kill_name",
        0x0043819C,
        b"OnKill\0",
        (
            ("onkill_property_reader", 0x0026D118, "689c818300", 1),
            ("onkill_property_reader", 0x0026D157, "689c818300", 1),
            ("onkill_property_writer", 0x00270D2E, "689c818300", 1),
            ("onkill_property_writer", 0x00270D6D, "689c818300", 1),
        ),
        "All four absolute OnKill references are property-name access sites; no runtime dispatch edge is inferred.",
    ),
    (
        "event_enemy_killed_name",
        0x00439AA4,
        b"EVENT_ENEMY_KILLED\0",
        (("pawn_binding_table", 0x002805B7, "68a49a8300", 1),),
        "The sole absolute name reference is in the global/Pawn binding table.",
    ),
)


DIRECT_DISPATCH_SEARCH_REGIONS = (
    "damage_core",
    "pawn_receiver",
    "pawn_hp_delta",
    "pawn_kill",
    "board_cleanup_sweep",
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


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ZeroHpCleanupBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise ZeroHpCleanupBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise ZeroHpCleanupBoundaryError("reviewed direct edge is not CALL rel32")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _dependency_records() -> list[dict[str, str]]:
    return [
        {
            "id": dependency_id,
            "path": path,
            "file_sha256": file_digest,
            "canonical_sha256": canonical_digest,
            "role": role,
        }
        for dependency_id, path, file_digest, canonical_digest, role in DEPENDENCY_SPECS
    ]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "decoded_for_direct_edges": decode,
            "boundary_basis": basis,
        }
        for region_id, start, end, digest, decode, basis in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    records = []
    for edge_id, source_region, source, encoded, target_region, target in DIRECT_EDGE_SPECS:
        record = {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{source:08x}",
            "instruction_hex": encoded,
            "target_rva": f"0x{target:08x}",
        }
        if target_region is not None:
            record["target_region"] = target_region
        records.append(record)
    return records


def _absolute_reference_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "string_rva": f"0x{rva:08x}",
            "string_hex": raw.hex(),
            "references": [
                {
                    "containing_region": region_id,
                    "instruction_rva": f"0x{instruction_rva:08x}",
                    "instruction_hex": instruction_hex,
                    "absolute_operand_offset": operand_offset,
                }
                for region_id, instruction_rva, instruction_hex, operand_offset in references
            ],
            "meaning": meaning,
        }
        for anchor_id, rva, raw, references, meaning in ABSOLUTE_REFERENCE_SPECS
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "hp_delta_later_reclassifies_isdead_before_return",
            "classification": "fact",
            "claim": (
                "After applying the HP delta and further same-routine feedback "
                "logic, the Pawn HP routine dispatches virtual vtable slot "
                "+0x10 and branches on IsDead before returning; it does not "
                "directly call Pawn:Kill."
            ),
        },
        {
            "id": "cleanup_sweep_requires_dead_noncorpse",
            "classification": "fact",
            "claim": (
                "The later Board sweep enters its erase path only after three "
                "cleared Pawn state bytes, virtual IsDead true, additional "
                "definition/state gates, Pawn+0x964 clear, and direct "
                "Pawn:IsCorpse false."
            ),
        },
        {
            "id": "eligible_pointer_is_erased_from_board_vector",
            "classification": "inference",
            "claim": (
                "For a still-present eligible pointer, the exact helper finds "
                "its index, the sweep compacts the remaining pointer tail, and "
                "the Board pawn-vector end moves back four bytes."
            ),
        },
        {
            "id": "corpses_escape_this_erase_and_remain_path_relevant",
            "classification": "inference",
            "claim": (
                "IsCorpse true branches around this erase attempt. Joined to "
                "the path-lifecycle artifact, a retained dead corpse remains "
                "counted occupancy while a dead non-corpse does not."
            ),
        },
        {
            "id": "two_static_callers_do_not_prove_damage_relative_timing",
            "classification": "inference",
            "claim": (
                "The exact .text image contains two instruction-aligned direct "
                "calls to the sweep. Their existence proves callable update "
                "paths, not which pass follows a particular SpaceDamage or "
                "whether removal occurs between two specific effect records."
            ),
        },
        {
            "id": "onkill_references_are_not_dispatch_evidence",
            "classification": "inference",
            "claim": (
                "All four absolute OnKill-name references belong to two "
                "property-access functions, and none of the reviewed damage, "
                "HP, Pawn:Kill, or cleanup regions directly calls those "
                "functions. A generic or indirect Lua dispatcher remains open."
            ),
        },
        {
            "id": "named_credit_fields_do_not_close_attribution",
            "classification": "inference",
            "claim": (
                "The exact owner/death/counter strings are confined to the "
                "inventoried definition, accessor, or binding sites. Those "
                "references do not establish the source/team/owner assigned "
                "to an environment kill or any counter increment."
            ),
        },
        {
            "id": "no_solver_semantic_change_from_static_cleanup_shape",
            "classification": "inference",
            "claim": (
                "The current solver already distinguishes persistent corpse "
                "path occupancy from transient dead state. Because action-level "
                "sweep timing and callback/credit semantics remain unproven, "
                "this static continuation supplies no contradictory Rust rule."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "cleanup_scheduler_timing",
            "question": "Which Board pass removes a particular pawn after a particular damage record?",
            "next_evidence": "Capture matched effect-record, Board-sweep, and settled-read timing if a solver mismatch requires it.",
        },
        {
            "id": "subclass_death_and_corpse_results",
            "question": "Which concrete Pawn subclasses return dead/corpse at each lifecycle phase?",
            "next_evidence": "Capture or exhaustively map subclass vtables and the nontrivial IsCorpse predicate inputs.",
        },
        {
            "id": "on_kill_callback_dispatch",
            "question": "Which generic or indirect runtime edge invokes a Lua OnKill function?",
            "next_evidence": "Trace the Lua callback dispatcher; static property-name references are insufficient.",
        },
        {
            "id": "kill_credit_and_owner_attribution",
            "question": "What source/team/owner and mission or achievement credit follow environment DAMAGE_DEATH?",
            "next_evidence": "Trace runtime attribution objects and counter writes from the settled death event.",
        },
        {
            "id": "death_effect_and_presentation_tail",
            "question": "How do death effects, animation, and visual removal interleave with logical cleanup?",
            "next_evidence": "Map or capture GetDeathEffect/IsDeathEffect and active-effect scheduling only when logically relevant.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows depots implement the same cleanup path?",
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
            "platform": "windows",
            "architecture": "x86",
            "bits": 32,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
        },
        "dependencies": _dependency_records(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "absolute_reference_inventory": _absolute_reference_records(),
        "contracts": {
            "hp_zero_consumer": {
                "later_same_routine_virtual_method": "Pawn:IsDead",
                "vtable_slot": "+0x10",
                "before_hp_routine_return": True,
                "direct_pawn_kill_call_in_hp_routine": False,
                "already_dead_noncorpse_reentry_is_ignored": True,
            },
            "board_cleanup": {
                "reviewed_sweep_rva": "0x0019e490",
                "exact_direct_caller_rvas": ["0x0016ae58", "0x001e9fb5"],
                "candidate_state_byte_offsets_required_zero": [
                    "+0x1325",
                    "+0x0922",
                    "+0x0921",
                ],
                "requires_virtual_is_dead": True,
                "direct_is_corpse_call": True,
                "required_is_corpse_result": False,
                "additional_definition_or_state_gate": True,
                "pawn_byte_offset_required_zero": "+0x0964",
                "pawn_vector_begin_offset": "+0x00a0",
                "pawn_vector_end_offset": "+0x00a4",
                "pointer_stride_bytes": 4,
                "not_found_sentinel": "0x7fffffff",
                "valid_pointer_tail_compacted": True,
                "vector_end_decrement_bytes": 4,
                "exact_damage_relative_timing_proven": False,
            },
            "corpse_join": {
                "is_corpse_is_nontrivial_predicate": True,
                "corpse_true_skips_reviewed_erase": True,
                "retained_corpse_counts_path_occupancy": True,
                "retained_dead_noncorpse_counts_path_occupancy": False,
                "subclass_results_exhausted": False,
            },
            "callback_and_credit": {
                "absolute_onkill_reference_count": 4,
                "onkill_reference_function_count": 2,
                "event_enemy_killed_name_reference_count": 1,
                "direct_call_from_reviewed_death_regions_to_onkill_reference_functions": False,
                "lua_onkill_dispatch_proven": False,
                "kill_credit_or_owner_attribution_proven": False,
                "mission_or_achievement_counter_update_proven": False,
            },
        },
        "findings": findings,
        "refines": [
            {
                "artifact": DEPENDENCY_SPECS[0][1],
                "unresolved_ids": [
                    "zero_hp_corpse_and_removal_timing",
                    "on_kill_callback_dispatch",
                    "kill_credit_and_owner_attribution",
                    "specialized_pawn_subclass_tail",
                ],
                "qualification": (
                    "The later same-HP-routine IsDead consumer and conditional "
                    "dead-noncorpse Board-vector erase are now exact. Damage-relative timing, "
                    "subclass outcomes, callback dispatch, and attribution remain open."
                ),
            },
            {
                "artifact": DEPENDENCY_SPECS[1][1],
                "unresolved_ids": ["transient dead-pawn removal timing between separate player actions"],
                "qualification": (
                    "The structural erase predicate is now exact, but its timing "
                    "between particular actions or effect records is not."
                ),
            },
        ],
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "reason": (
                "The path model already distinguishes persistent corpses, and "
                "the new static evidence does not prove a different action-level "
                "cleanup, callback, or attribution order."
            ),
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "Raw absolute-reference completeness is limited to the file-backed .text section and the exact encoded virtual addresses.",
            "Absence of a direct CALL rel32 does not exclude a generic string lookup, virtual call, function pointer, or Lua dispatcher.",
            "The two sweep callers do not by themselves identify player-action, effect-record, or presentation timing.",
        ],
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "absolute_reference_anchor_count": len(ABSOLUTE_REFERENCE_SPECS),
            "absolute_reference_count": sum(
                len(references)
                for _anchor_id, _rva, _raw, references, _meaning in ABSOLUTE_REFERENCE_SPECS
            ),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "conditional_dead_noncorpse_board_erase_proven": True,
            "exact_cleanup_timing_proven": False,
            "callback_or_credit_tail_proven": False,
            "simulator_change_required": False,
        },
    }


def _verify_dependencies(
    executable: Path,
    content_root: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    values: dict[str, Mapping[str, Any]] = {}
    for dependency_id, relative, file_digest, canonical_digest, _role in DEPENDENCY_SPECS:
        path = repository_root / relative
        if path.is_symlink() or not path.is_file():
            raise ZeroHpCleanupBoundaryError(f"dependency {dependency_id} missing")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != file_digest:
            raise ZeroHpCleanupBoundaryError(f"dependency {dependency_id} file differs")
        value = _read_json(path)
        if _canonical_sha256(value) != canonical_digest:
            raise ZeroHpCleanupBoundaryError(f"dependency {dependency_id} fields differ")
        values[dependency_id] = value
    try:
        validate_damage_death_boundary_map(
            executable,
            content_root,
            values["damage_death_pawn_boundary"],
        )
    except DamageDeathBoundaryError as exc:
        raise ZeroHpCleanupBoundaryError(f"damage dependency differs: {exc}") from exc
    try:
        validate_path_occupancy_lifecycle_map(
            executable,
            values["path_occupancy_lifecycle"],
        )
    except PathOccupancyLifecycleError as exc:
        raise ZeroHpCleanupBoundaryError(f"path dependency differs: {exc}") from exc


def _text_absolute_operand_rvas(image: Any, data: bytes, virtual_address: int) -> list[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise ZeroHpCleanupBoundaryError("file-backed executable .text section missing")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    needle = struct.pack("<I", virtual_address)
    result: list[int] = []
    cursor = 0
    while True:
        offset = body.find(needle, cursor)
        if offset < 0:
            return result
        result.append(section.virtual_address + offset)
        cursor = offset + 1


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise ZeroHpCleanupBoundaryError("file-backed executable .text section missing")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    result: set[int] = set()
    for offset in range(len(body) - 4):
        if body[offset] != 0xE8:
            continue
        source_rva = section.virtual_address + offset
        target = source_rva + 5 + struct.unpack_from("<i", body, offset + 1)[0]
        if target == target_rva:
            result.add(source_rva)
    return result


def build_zero_hp_cleanup_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build zero-HP cleanup boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise ZeroHpCleanupBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise ZeroHpCleanupBoundaryError("executable identity differs")

    _verify_dependencies(executable, content_root)

    region_ranges: dict[str, tuple[int, int]] = {}
    decoded_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, decode, _basis in REGION_SPECS:
        try:
            body = _region_bytes(image, data, start, end - start, ".text", region_id)
        except Exception as exc:
            raise ZeroHpCleanupBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise ZeroHpCleanupBoundaryError(f"region {region_id} bytes differ")
        region_ranges[region_id] = (start, end)
        if decode:
            decoded_ranges[region_id] = (start, end)
    try:
        decoded = _decode_x86_regions(image, data, decoded_ranges)
    except Exception as exc:
        raise ZeroHpCleanupBoundaryError(str(exc)) from exc

    for window_id, region_id, start, encoded_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise ZeroHpCleanupBoundaryError(f"control window {window_id} differs")
        region_start, region_end = region_ranges[region_id]
        if not (region_start <= start < start + len(expected) <= region_end):
            raise ZeroHpCleanupBoundaryError(f"control window {window_id} escapes region")
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded[region_id].get(cursor)
            if instruction is None:
                raise ZeroHpCleanupBoundaryError(
                    f"control window {window_id} is not instruction-aligned"
                )
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise ZeroHpCleanupBoundaryError(
                f"control window {window_id} ends inside an instruction"
            )

    for edge_id, source_region, source, encoded_hex, target_region, target in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(encoded_hex)
        instruction = decoded[source_region].get(source)
        if instruction is None or instruction[1] != expected:
            raise ZeroHpCleanupBoundaryError(f"direct edge {edge_id} bytes differ")
        if _direct_target(source, expected) != target:
            raise ZeroHpCleanupBoundaryError(f"direct edge {edge_id} target differs")
        if target_region is not None:
            target_start, target_end = region_ranges[target_region]
            if not target_start <= target < target_end:
                raise ZeroHpCleanupBoundaryError(f"direct edge {edge_id} target escapes region")

    expected_sweep_calls = {0x0016AE58, 0x001E9FB5}
    if _raw_rel32_call_sites(image, data, 0x0019E490) != expected_sweep_calls:
        raise ZeroHpCleanupBoundaryError("cleanup sweep direct-call inventory differs")

    reference_decode_ranges: dict[str, tuple[int, int]] = {}
    for anchor_id, rva, raw, references, _meaning in ABSOLUTE_REFERENCE_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise ZeroHpCleanupBoundaryError(f"data anchor {anchor_id} differs")
        expected_operands = sorted(
            instruction_rva + operand_offset
            for _region_id, instruction_rva, _hex, operand_offset in references
        )
        actual_operands = _text_absolute_operand_rvas(
            image,
            data,
            image.image_base + rva,
        )
        if actual_operands != expected_operands:
            raise ZeroHpCleanupBoundaryError(
                f"absolute reference inventory {anchor_id} differs"
            )
        for index, (region_id, instruction_rva, instruction_hex, operand_offset) in enumerate(references):
            instruction_bytes = bytes.fromhex(instruction_hex)
            if _bytes_at(image, data, instruction_rva, len(instruction_bytes)) != instruction_bytes:
                raise ZeroHpCleanupBoundaryError(
                    f"absolute reference {anchor_id}[{index}] bytes differ"
                )
            region_start, region_end = region_ranges[region_id]
            if not region_start <= instruction_rva < instruction_rva + len(instruction_bytes) <= region_end:
                raise ZeroHpCleanupBoundaryError(
                    f"absolute reference {anchor_id}[{index}] escapes region"
                )
            needle = struct.pack("<I", image.image_base + rva)
            if instruction_bytes[operand_offset : operand_offset + 4] != needle:
                raise ZeroHpCleanupBoundaryError(
                    f"absolute reference {anchor_id}[{index}] operand differs"
                )
            reference_decode_ranges[f"reference_{anchor_id}_{index}"] = (
                instruction_rva,
                instruction_rva + len(instruction_bytes),
            )
    try:
        _decode_x86_regions(image, data, reference_decode_ranges)
    except Exception as exc:
        raise ZeroHpCleanupBoundaryError(
            f"absolute reference instruction alignment differs: {exc}"
        ) from exc

    onkill_ranges = (
        region_ranges["onkill_property_reader"],
        region_ranges["onkill_property_writer"],
    )
    direct_dispatch_edges: list[tuple[str, int, int]] = []
    for region_id in DIRECT_DISPATCH_SEARCH_REGIONS:
        for source_rva, (_mnemonic, encoded) in decoded[region_id].items():
            if len(encoded) != 5 or encoded[0] != 0xE8:
                continue
            target = _direct_target(source_rva, encoded)
            if any(start <= target < end for start, end in onkill_ranges):
                direct_dispatch_edges.append((region_id, source_rva, target))
    if direct_dispatch_edges:
        raise ZeroHpCleanupBoundaryError(
            "reviewed direct edge into OnKill-reference functions differs"
        )

    return _expected_shape()


def validate_zero_hp_cleanup_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise ZeroHpCleanupBoundaryError("zero-HP cleanup boundary fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "conditional_dead_noncorpse_board_erase_proven": True,
        "exact_cleanup_timing_proven": False,
        "callback_or_credit_tail_proven": False,
        "simulator_change_required": False,
    }


def validate_zero_hp_cleanup_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, byte, reference, or prose drift."""
    expected = build_zero_hp_cleanup_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise ZeroHpCleanupBoundaryError(
            "zero-HP cleanup boundary differs from exact-build analysis"
        )
    result = validate_zero_hp_cleanup_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_zero_hp_cleanup_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
