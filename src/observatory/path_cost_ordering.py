"""Reproduce exact-build native path-cost and ordering evidence.

This map continues the narrower movement-boundary review in
``path_boundaries.py``.  It pins the graph-search costs, cardinal expansion
order, priority comparators, reachable-result ordering, GetPath reconstruction,
and the ordinary PATH_GROUND/PATH_MASSIVE occupancy branch for the exact
owner-observed Windows executable.

The artifact contains normalized addresses, hashes, short control windows, and
bounded analyst conclusions.  It contains neither the executable nor recovered
proprietary source.
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
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_path_cost_ordering_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000


class PathCostOrderingError(RuntimeError):
    """Raised when the exact native path-cost map cannot be reproduced."""


# Function extents are analyst-reviewed boundaries.  Table records live in the
# executable .text section but are intentionally excluded from linear decoding.
REGION_SPECS = (
    (
        "direction_initializer",
        0x00003030,
        0x00003081,
        "4d2d793080eed2c8234ef3e4eaf3d64219e33a475b44fa51ca9faa182ca0479d",
        ".text",
        True,
        "Complete initializer through RET.",
    ),
    (
        "coordinate_tree_successor",
        0x0006DF30,
        0x0006DF7F,
        "539e52ffef66379c5aa4c31b81f540f6b75b9b347b09e1af9d146a42ee7d8991",
        ".text",
        True,
        "Complete in-order tree-successor helper through RET.",
    ),
    (
        "point_vector_append",
        0x000B5080,
        0x000B50F2,
        "5fa5ce9bd76705a63de61684acbfb6b6147c4be3da1e4f86cb9bc991d3f748eb",
        ".text",
        True,
        "Complete eight-byte Point vector append helper through RET 0x04.",
    ),
    (
        "reachable_core",
        0x000CE7E0,
        0x000CE9A0,
        "f7b3287d2854115b30ad2d6126d9d573c37d5fabfdd471f1776c5f911990926f",
        ".text",
        True,
        "Complete GetReachable core through RET 0x14.",
    ),
    (
        "reachable_search",
        0x000CEC40,
        0x000CF2F0,
        "05bebc52863ead8a3ea9a0272301253f726dd03f94a56e1491f7ab7202963645",
        ".text",
        True,
        "Complete cached reachability search through RET 0x14.",
    ),
    (
        "path_core",
        0x000CF410,
        0x000CF9DF,
        "3477ed0edb02f50d6e5f92b5c09596c6d6bcc30398a3f5636e3091c3db1f75b4",
        ".text",
        True,
        "Complete GetPath core through RET 0x18.",
    ),
    (
        "tree_payload_copy",
        0x000D15E0,
        0x000D1620,
        "507e5edbb29fd8dfc326ea15c3c15843ee737badfaefa476d8f0d9a566abad7f",
        ".text",
        True,
        "Complete coordinate/cost payload-copy helper through RET 0x04.",
    ),
    (
        "point_vector_reverse",
        0x000D16E0,
        0x000D1716,
        "b713ab8e36aaf7d763c78d8ca6304ccc9c390ceb6c28924d7fddba9d108d5fb7",
        ".text",
        True,
        "Complete eight-byte element reversal helper through RET.",
    ),
    (
        "coordinate_tree_copy",
        0x000D1760,
        0x000D17D2,
        "6dbe226efddcf3a06e9ebc076e6b70512bddbfe74f5e1a8a4a852367c7d7716b",
        ".text",
        True,
        "Complete coordinate-keyed tree copy helper through RET 0x08.",
    ),
    (
        "priority_tree_copy",
        0x000D17F0,
        0x000D1862,
        "a405f7f1ada696034bfea2395aa830dad24c97802ca4f3f3c202eb0dd7eadc0e",
        ".text",
        True,
        "Complete float-priority tree copy helper through RET 0x08.",
    ),
    (
        "priority_tree_lookup",
        0x000D1880,
        0x000D18E3,
        "4e6e0510ba2e54696ea9c692818f0eed29b02aba384b530db8086c6e14a27e6f",
        ".text",
        True,
        "Complete comparator-guided lookup through RET 0x04.",
    ),
    (
        "coordinate_tree_lookup",
        0x000D18F0,
        0x000D1930,
        "84992b1545c29b84bc8f0ca6dadc94d53e208e3fcbb8cc9736325b84fa939a68",
        ".text",
        True,
        "Complete coordinate-keyed lookup through RET 0x04.",
    ),
    (
        "priority_tree_insert",
        0x000D1F90,
        0x000D20B6,
        "f62dd9b1b9d9cdb8a0d68616ee7191af0740b289a572630fff0323af4cea1395",
        ".text",
        True,
        "Complete float-priority tree insertion through RET 0x10.",
    ),
    (
        "path_heap_sift_up",
        0x000D2810,
        0x000D28AB,
        "5019bdf06f0b291c1d6397f95182ef0e48fd11b43d8337253d21abea29d00d0e",
        ".text",
        True,
        "Complete path-heap sift-up helper through RET.",
    ),
    (
        "path_heap_pop_adjust",
        0x000D28B0,
        0x000D298C,
        "38db964bac25c57e8d124ad6106a62491f03c15a7ea920ed025147ea0165a051",
        ".text",
        True,
        "Complete path-heap pop adjustment through RET.",
    ),
    (
        "source_cost",
        0x00162190,
        0x001621A9,
        "48f2c07051a81213375e8c72e3306f9267f137f802e2919ec844229a55854e4a",
        ".text",
        True,
        "Complete Board GridSearch source-cost slot through RET 0x0c.",
    ),
    (
        "destination_cost",
        0x001621B0,
        0x00162207,
        "f9e54dda1470ed6304c725ee7247dacdf3f18ccb9f6ccca11807711f5436cbf1",
        ".text",
        True,
        "Complete Board GridSearch destination-cost slot through RET 0x0c.",
    ),
    (
        "pawn_id_or_sentinel",
        0x0019FF10,
        0x0019FF35,
        "269813c828af7ecbbb0558efdc4d4954cf5c56ef3b96f47c7ef92b68f1b445fe",
        ".text",
        True,
        "Complete counted-pawn identifier helper through RET.",
    ),
    (
        "counted_occupancy",
        0x0019FF40,
        0x0019FFD3,
        "1e3282851e31b74bfaba10d692ac4c31517d7416d47201c7e2eb5fdf36e4b1f1",
        ".text",
        True,
        "Complete tile counted-occupancy predicate through RET 0x04.",
    ),
    (
        "grid_tile_can_traverse",
        0x001A0150,
        0x001A0288,
        "548085ece564eb40e21535d5cbd8eb55b6f3fe2c60c35400ecd9028537f081ee",
        ".text",
        True,
        "Complete per-tile traversal predicate through RET 0x04.",
    ),
    (
        "tile_destination_cost",
        0x001A0290,
        0x001A02D7,
        "0e20d6c1229b605a5ce92653c1bbd1588a31e5f697ea02ead6f000039119cbba",
        ".text",
        True,
        "Complete per-tile destination-cost function through RET 0x04.",
    ),
    (
        "tile_destination_cost_tables",
        0x001A02D8,
        0x001A02FC,
        "558cda5596f0931907dac9cbe5b3535140a15c7f5e88c40f9e6ce1fe44262b34",
        ".text",
        False,
        "Contiguous jump-target and selector tables after the cost function.",
    ),
    (
        "tile_first_counted_pawn",
        0x001AF360,
        0x001AF37C,
        "761941ae627ce459aad2abf2a04e78931393efb363984d0c4bebfad71555bc0c",
        ".text",
        True,
        "Complete first-counted-pawn helper through RET.",
    ),
    (
        "grid_tile_stop_blocking",
        0x001AF400,
        0x001AF49B,
        "5be95f7c4ca4a25d9f6b0da4c1cf0c26d2579524bf702763bca85afdf554581d",
        ".text",
        True,
        "Complete profile/terrain stop-blocking predicate through RET 0x04.",
    ),
    (
        "grid_tile_stop_table",
        0x001AF49C,
        0x001AF4C0,
        "a4c100e024ff5c7255c3eb72f939d16f681eba3983196ebfbb14f70590983693",
        ".text",
        False,
        "Contiguous nine-entry terrain jump table.",
    ),
    (
        "pawn_non_grid_property",
        0x0023E140,
        0x0023E179,
        "23bfeb409937ae8e493d68bbda323ffc601c461b71f619bf5306cf441ec9c33b",
        ".text",
        True,
        "Complete Pawn NonGrid property query through RET.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "reachable_output_coordinate_tree",
        "reachable_core",
        0x000CE8A1,
        "8d462050e8462f00008d4dc0c645fc018d46285150e8a52e00008b46308945c88b46348945ccc645fc028b75c0c745dcffffffffc745e0ffffffffc745e400007a448b06c745e80000000089450c903bc6744083c0108d4ddc50e8e02c0000395de87f22ff75108b078bcfff75e0ff75dc8b400cffd084c0750c8d45dc508d4dd0e85967feff8d4d0ce801f6f9ff8b450cebbc",
        "GetReachable copies the coordinate-keyed result tree, walks it in-order, filters cost and stop blocking, and appends points without reordering.",
    ),
    (
        "reachable_budget_guard",
        "reachable_search",
        0x000CEF5C,
        "50e8de3100008b8558ffffff8b4d0c3948180f8d21020000",
        "A node whose stored cost is greater than or equal to the movement budget is not expanded further.",
    ),
    (
        "reachable_neighbor_order_and_traversal",
        "reachable_search",
        0x000CEF80,
        "8b04f5b4578d00ff75088b0cf5b8578d0003c78b55b803ca8945bc8b035652894dc08bcb8b401057c745c400007a44ffd084c00f85c5010000ff75088b038bcbff75c0ff75bc8b4014ffd084c00f84ab010000",
        "Each of four initialized direction pairs is checked first for a directional wall and then for traversal eligibility.",
    ),
    (
        "reachable_strict_cost_update",
        "reachable_search",
        0x000CF017,
        "8d4588508d8550ffffff508d4de0e8163100008b8550ffffff8d4de08b401803c78945e88d45bc508d8548ffffff50e8f53000008b8548ffffff8b4de83b48180f8d1e010000",
        "The candidate edge cost is added to the current cost; a candidate greater than or equal to the stored cost is discarded.",
    ),
    (
        "path_start_priority_zero",
        "path_core",
        0x000CF4E2,
        "c645fc048d4dd88b4510898570ffffff8b4514898574ffffff8d8570ffffff50c78578ffffff00000000e81f2500008d4dc0c74008000000008d8570ffffff50e8592700008d8d58ffffffc64008018d8570ffffff50e853090000",
        "GetPath inserts the start coordinate with g=0 and heap priority 0.",
    ),
    (
        "path_endpoint_traversal_exception",
        "path_core",
        0x000CF600,
        "ff750c8b3ccdb8578d008b558803fa8b34cdb4578d008b03037584518b4d848b401052518bcb89b570ffffff89bd74ffffffc78578ffffff00007a44ffd084c00f8581010000ff750c8b038bcb57568b4014ffd084c075123b75180f85660100003b7d1c0f855d010000",
        "GetPath admits a traversal-rejected neighbor only when that neighbor is the requested endpoint.",
    ),
    (
        "path_strict_cost_update",
        "path_core",
        0x000CF6E5,
        "8d4584508d4dd8e83f230000518d4dc08b40080145808d8570ffffff50ffb54cffffff8d856cffffff50e83c2d000083bd6cffffff00741b8d8570ffffff508d4dd8e8042300008b4d803b48080f8d8f000000",
        "GetPath records a predecessor only for a strictly lower g cost; equal-cost alternatives do not replace it.",
    ),
    (
        "path_weighted_manhattan_priority",
        "path_core",
        0x000CF747,
        "8b4d848948088b4d8889480c8b451c2bc7998bc88b451833ca2bc68b75802bca9933c22bc203c8660f6ec60f5bc08d8570ffffff50660f6ec98d8d58ffffff0f5bc9f30f590d78cb8300f30f58c8f30f118d78ffffffe8ee060000",
        "The heap priority is g plus Manhattan distance multiplied by the pinned float at RVA 0x0043cb78.",
    ),
    (
        "path_reconstruct_and_reverse",
        "path_core",
        0x000CF85A,
        "33db33f633c0895d8489758889458cc645fc058b4d188b7d1c898d7cffffff898d68ffffff89bd6cffffff3b4d1075093b7d140f849a0000008d9568ffffff3bd673313bda772d8bfa2bfbc1ff033bf075106a018d4d84e89a60feff8b75888b5d8485f674318b04fb89068b44fb04894604eb233bf075166a018d4d84e87460feff8b75888b5d848b8d7cffffff85f67405890e897e048d8568ffffff83c608508d4da8897588e83a2200008b48088b780c898d7cffffff898d68ffffff89bd6cffffff85c9780b8b458c85ff0f8958ffffff8d8568ffffff508d4d84e84457feff8b7d888b75845756e8971d0000",
        "Reconstruction appends endpoint-to-start predecessors, appends the start, then reverses the eight-byte Point vector.",
    ),
    (
        "ordinary_occupancy_gate",
        "grid_tile_can_traverse",
        0x001A01B9,
        "83f802530f94450be84afdffff3bc78bce6a010f94c7e86cfdffff84c074168bcee881f100008bc8e85adf090084c07404b301eb0232db6a018bcee847fdffff84c0740484ff74488b8ee02a000083f901743d84db7539389eac230000740983becc2300000f7c1083f9030f94c084c07406807d0b00741883f904741383f909740e5b5fb8010000005e8be55dc204005b5f33c05e8be55d",
        "Low profiles 0/2 compare the counted pawn identifier with the moving identifier and block a different occupant without consulting team.",
    ),
    (
        "massive_water_branch",
        "grid_tile_can_traverse",
        0x001A0201,
        "8b8ee02a000083f901743d84db7539389eac230000740983becc2300000f7c1083f9030f94c084c07406807d0b00741883f904741383f909740e",
        "For terrain 3, the traversal rejection is conditional on the low profile not being PATH_MASSIVE=2.",
    ),
    (
        "water_stop_handler",
        "grid_tile_stop_blocking",
        0x001AF473,
        "85f6740583fe0775e35fb8010000005e5d",
        "The terrain-3 stop handler blocks PATH_GROUND=0 and PATH_BURROWER=7, but not PATH_MASSIVE=2.",
    ),
    (
        "path_heap_parent_comparator",
        "path_heap_sift_up",
        0x000D2830,
        "f30f1047088d145bf30f104c96080f2ec89ff6c4447b080f2fc80f97c0eb168b04968b0f3bc175078b4496043b47048b4dfc0f9fc084c07428",
        "Heap sift-up compares float priority first, then x, then y.",
    ),
    (
        "path_heap_child_comparator",
        "path_heap_pop_adjust",
        0x000D28ED,
        "f30f104c8e08f30f10448efc0f2ec89ff6c4447b080f2fc80f97c0eb198b048e8b548ef43bc275088b448e043b448ef88b55fc0f9fc084c08d7aff8d0c5b0f44fa",
        "Heap pop selects the lesser child by float priority, then x, then y.",
    ),
)


DIRECTION_SPECS = (
    (0, 0x0041A640, 0x004D57B4, 0, -1),
    (1, 0x0041A638, 0x004D57BC, 1, 0),
    (2, 0x0041A630, 0x004D57C4, 0, 1),
    (3, 0x0041A628, 0x004D57CC, -1, 0),
)

HEURISTIC_RVA = 0x0043CB78
HEURISTIC_HEX = "ae47813f"
HEURISTIC_WEIGHT = struct.unpack("<f", bytes.fromhex(HEURISTIC_HEX))[0]
NON_GRID_STRING_RVA = 0x00436C04

PROFILE_3_TARGET_RVAS = (0x001A02CE, 0x001A02B2, 0x001A02CE)
PROFILE_3_SELECTORS = (0, 1, 0, 2, 2, 0, 0, 0)
OTHER_PROFILE_TARGET_RVAS = (0x001A02CE, 0x001A02CE)
OTHER_PROFILE_SELECTORS = (0, 0, 0, 1, 1, 0, 0, 0)
STOP_TARGET_RVAS = (
    0x001AF467,
    0x001AF493,
    0x001AF473,
    0x001AF42B,
    0x001AF487,
    0x001AF493,
    0x001AF493,
    0x001AF493,
    0x001AF446,
)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bytes_at(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    *,
    executable: bool | None = None,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise PathCostOrderingError(f"RVA 0x{rva:08x} is not file-backed")
    section = next(
        (
            item
            for item in image.sections
            if item.virtual_address <= rva
            and rva + size <= item.virtual_address + item.raw_size
        ),
        None,
    )
    if section is None:
        raise PathCostOrderingError(f"RVA 0x{rva:08x} has no containing section")
    if executable is not None and section.executable != executable:
        raise PathCostOrderingError(f"RVA 0x{rva:08x} section permissions differ")
    return data[offset : offset + size]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "evidence_class": "fact",
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "section": section,
            "decoded_as_code": decode,
            "boundary_basis": basis,
        }
        for region_id, start, end, digest, section, decode, basis in REGION_SPECS
    ]


def _control_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region_id": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _expected_shape() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "upstream_path_boundary_artifact": {
                "path": "data/observatory/native/windows_build_13725832_31fe35265598_path_boundaries.json",
                "file_sha256": "098cbbc5a9dc4c99a07b5f85eac7aaa19812bf093249d1d3f6e6c5ec49277486",
                "canonical_sha256": "99c8c30fa2e213039e6ba07f5f5062d6487aaa6286eee9cc9cb0cf6aaed23afc",
            },
        },
        "method": {
            "boundary_review": "Focused x86 disassembly traced the Board grid-search slots, reachability tree, path heap, predecessor reconstruction, tile costs, direction initializer, and ordinary occupancy branch; every published region and control window is byte-bound to the exact executable.",
            "limitations": [
                "Semantic role names are bounded analyst inferences over exact machine-code facts.",
                "Static ordering is not a matched runtime GetReachable/GetPath capture.",
                "The counted-occupancy helper's dead/corpse classification remains unresolved.",
                "AddMove interruption, per-step item effects, and scheduler timing remain outside this artifact.",
                "Solver safety exclusions for ACID, Lava, and other hazardous voluntary moves remain distinct from native path legality.",
                "The artifact applies only to the exact owner-observed Windows executable.",
            ],
        },
        "regions": _region_records(),
        "control_windows": _control_windows(),
        "direction_order": [
            {
                "index": index,
                "source_rva": f"0x{source:08x}",
                "runtime_destination_rva": f"0x{destination:08x}",
                "x_delta": x,
                "y_delta": y,
                "evidence_class": "fact",
            }
            for index, source, destination, x, y in DIRECTION_SPECS
        ],
        "cost_tables": {
            "source_cost": {
                "value": 0,
                "evidence_class": "fact",
            },
            "destination_cost": {
                "exact_argument_3": {
                    "terrain_1": 1000,
                    "all_other_terrain": 1,
                },
                "all_other_arguments": {
                    "all_terrain": 1,
                },
                "profile_3_target_rvas": [
                    f"0x{rva:08x}" for rva in PROFILE_3_TARGET_RVAS
                ],
                "profile_3_selectors_for_terrain_0_through_7": list(
                    PROFILE_3_SELECTORS
                ),
                "other_profile_target_rvas": [
                    f"0x{rva:08x}" for rva in OTHER_PROFILE_TARGET_RVAS
                ],
                "other_profile_selectors_for_terrain_0_through_7": list(
                    OTHER_PROFILE_SELECTORS
                ),
                "evidence_class": "fact",
            },
        },
        "ordering": {
            "reachable_open_priority": ["integer_cost_as_float", "x", "y"],
            "reachable_equal_cost_replaces_predecessor": False,
            "reachable_output_order": ["x", "y"],
            "path_heap_priority": ["g_plus_weighted_manhattan", "x", "y"],
            "path_heuristic": {
                "rva": f"0x{HEURISTIC_RVA:08x}",
                "hex": HEURISTIC_HEX,
                "weight": HEURISTIC_WEIGHT,
            },
            "path_equal_g_replaces_predecessor": False,
            "path_distinct_points_include_start": True,
            "path_distinct_points_include_destination": True,
            "path_endpoint_may_bypass_traversal_rejection": True,
            "evidence_class": "inference",
        },
        "ordinary_occupancy": {
            "profiles": [0, 2],
            "same_pawn_id_may_transit": True,
            "different_counted_pawn_id_blocks_transit": True,
            "team_comparison_present": False,
            "non_grid_property_string_rva": f"0x{NON_GRID_STRING_RVA:08x}",
            "dead_or_corpse_classification": "unresolved",
            "evidence_class": "inference",
        },
        "terrain_3_water": {
            "stop_jump_target_rva": f"0x{STOP_TARGET_RVAS[2]:08x}",
            "path_ground_0_can_transit": False,
            "path_ground_0_can_stop": False,
            "path_massive_2_can_transit": True,
            "path_massive_2_can_stop": True,
            "evidence_class": "inference",
        },
        "conclusions": [
            {
                "id": "reachable_search_is_unit_cost",
                "evidence_class": "inference",
                "claim": "GetReachable admits only traversal-approved neighbors. Every such edge has cost 1: the source-cost slot returns 0, the destination-cost slot returns 1 for every admitted tile, and the exact-profile-3 terrain-1 cost of 1000 is unreachable because that traversal branch rejects terrain 1.",
            },
            {
                "id": "reachable_output_is_coordinate_sorted",
                "evidence_class": "inference",
                "claim": "GetReachable walks the copied coordinate-keyed tree in order and appends accepted points directly, so its returned Point vector is lexicographic by x and then y, independent of expansion discovery order.",
            },
            {
                "id": "path_uses_weighted_astar_and_strict_predecessors",
                "evidence_class": "inference",
                "claim": "For distinct valid points, GetPath uses a min-heap ordered by (g + 1.01 * Manhattan, x, y), keeps only strict g improvements, reconstructs from destination predecessors, appends the start, and reverses the vector; both endpoints are present.",
            },
            {
                "id": "path_endpoint_has_a_traversal_exception",
                "evidence_class": "inference",
                "claim": "GetPath may admit the requested endpoint after can_traverse rejects it. An exact literal path argument 3 therefore pays destination cost 1000 for a terrain-1 endpoint; other destination costs remain 1.",
            },
            {
                "id": "ordinary_occupancy_is_pawn_id_not_team_based",
                "evidence_class": "inference",
                "claim": "PATH_GROUND=0 and PATH_MASSIVE=2 reject a counted occupant whose pawn identifier differs from the mover and allow the same identifier; the reviewed branch contains no team comparison.",
            },
            {
                "id": "path_massive_allows_water",
                "evidence_class": "inference",
                "claim": "Terrain 3 is Water for the shipped Lua constants. PATH_MASSIVE=2 passes both the traversal predicate and the destination stop predicate, while PATH_GROUND=0 fails both.",
            },
            {
                "id": "solver_had_a_massive_water_gap",
                "evidence_class": "inference",
                "claim": "The reviewed Rust v401 ordinary movement branch rejected Water for every non-flying unit even when the bridge supplied Massive=true; simulator v402 narrows that rejection so Massive units can use native-legal Water routes.",
            },
        ],
        "summary": {
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direction_order": [[x, y] for _i, _s, _d, x, y in DIRECTION_SPECS],
            "reachable_edge_cost": 1,
            "reachable_output_order": ["x", "y"],
            "path_heuristic_weight": HEURISTIC_WEIGHT,
            "path_priority_order": ["f", "x", "y"],
            "path_includes_both_endpoints": True,
            "ordinary_occupancy_team_agnostic": True,
            "massive_water_transit": True,
            "massive_water_stop": True,
            "simulator_version": 402,
            "remaining_runtime_proof": [
                "matched native GetReachable and GetPath output vectors",
                "dead pawn and corpse occupancy classification",
                "AddMove step effects, interruption, and scheduler timing",
                "non-Windows build equivalence",
            ],
        },
    }


def build_path_cost_ordering_map(executable: Path) -> dict[str, Any]:
    """Reproduce the exact-build native path-cost and ordering map."""
    expected = _expected_shape()
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise PathCostOrderingError("executable identity differs")

    decoded_regions: dict[str, tuple[int, int]] = {}
    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_digest, _section, decode, _basis in REGION_SPECS:
        body = _bytes_at(image, data, start, end - start, executable=True)
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise PathCostOrderingError(f"region {region_id} bytes differ")
        region_ranges[region_id] = (start, end)
        if decode:
            decoded_regions[region_id] = (start, end)

    try:
        decoded = _decode_x86_regions(image, data, decoded_regions)
    except Exception as exc:
        raise PathCostOrderingError(str(exc)) from exc

    for window_id, region_id, start, encoded_hex, _meaning in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(encoded_hex)
        region_start, region_end = region_ranges[region_id]
        if not (region_start <= start and start + len(encoded) <= region_end):
            raise PathCostOrderingError(f"control window {window_id} leaves its region")
        if _bytes_at(image, data, start, len(encoded), executable=True) != encoded:
            raise PathCostOrderingError(f"control window {window_id} differs")
        if start not in decoded[region_id]:
            raise PathCostOrderingError(
                f"control window {window_id} does not begin at an instruction"
            )

    for index, source, _destination, x, y in DIRECTION_SPECS:
        encoded = _bytes_at(image, data, source, 8, executable=False)
        if struct.unpack("<ii", encoded) != (x, y):
            raise PathCostOrderingError(f"direction {index} source differs")
    for index, source, destination, _x, _y in DIRECTION_SPECS:
        expected_copy = (
            b"\xa1"
            + struct.pack("<I", image.image_base + source)
            + b"\xa3"
            + struct.pack("<I", image.image_base + destination)
            + b"\xa1"
            + struct.pack("<I", image.image_base + source + 4)
            + b"\xa3"
            + struct.pack("<I", image.image_base + destination + 4)
        )
        if _bytes_at(
            image,
            data,
            0x00003030 + index * len(expected_copy),
            len(expected_copy),
            executable=True,
        ) != expected_copy:
            raise PathCostOrderingError(f"direction {index} initializer differs")

    heuristic = _bytes_at(image, data, HEURISTIC_RVA, 4, executable=False)
    if heuristic.hex() != HEURISTIC_HEX or struct.unpack("<f", heuristic)[0] != HEURISTIC_WEIGHT:
        raise PathCostOrderingError("path heuristic differs")

    if _bytes_at(image, data, NON_GRID_STRING_RVA, 8) != b"NonGrid\0":
        raise PathCostOrderingError("NonGrid property string differs")

    profile3_targets = struct.unpack(
        "<III", _bytes_at(image, data, 0x001A02D8, 12, executable=True)
    )
    if tuple(value - image.image_base for value in profile3_targets) != PROFILE_3_TARGET_RVAS:
        raise PathCostOrderingError("profile-3 cost targets differ")
    if tuple(_bytes_at(image, data, 0x001A02E4, 8, executable=True)) != PROFILE_3_SELECTORS:
        raise PathCostOrderingError("profile-3 cost selectors differ")

    other_targets = struct.unpack(
        "<II", _bytes_at(image, data, 0x001A02EC, 8, executable=True)
    )
    if tuple(value - image.image_base for value in other_targets) != OTHER_PROFILE_TARGET_RVAS:
        raise PathCostOrderingError("other-profile cost targets differ")
    if tuple(_bytes_at(image, data, 0x001A02F4, 8, executable=True)) != OTHER_PROFILE_SELECTORS:
        raise PathCostOrderingError("other-profile cost selectors differ")

    stop_targets = struct.unpack(
        "<" + "I" * len(STOP_TARGET_RVAS),
        _bytes_at(image, data, 0x001AF49C, 4 * len(STOP_TARGET_RVAS), executable=True),
    )
    if tuple(value - image.image_base for value in stop_targets) != STOP_TARGET_RVAS:
        raise PathCostOrderingError("stop-blocking terrain table differs")

    return expected


def validate_path_cost_ordering_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without requiring the executable."""
    if not isinstance(value, Mapping):
        raise PathCostOrderingError("path cost ordering map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise PathCostOrderingError("path cost ordering map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "reachable_edge_cost": 1,
        "reachable_output_order": ["x", "y"],
        "path_heuristic_weight": HEURISTIC_WEIGHT,
        "massive_water_transit": True,
        "massive_water_stop": True,
        "simulator_version": 402,
    }


def validate_path_cost_ordering_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject byte, address, or prose drift."""
    expected = build_path_cost_ordering_map(executable)
    if dict(value) != expected:
        raise PathCostOrderingError(
            "path cost ordering map differs from executable analysis"
        )
    result = validate_path_cost_ordering_map_binding(value)
    result["status"] = "verified"
    return result


def encode_path_cost_ordering_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
