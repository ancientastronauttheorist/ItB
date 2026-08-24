"""Reproduce and replay the exact-build Mission_Piston setup boundary.

The shipped mission chooses a Piston source from an ordered map zone, chooses
one eligible facing, and constructs a Pawn.  The first two choices use the
shared MSVC generator through random_int; the common Pawn constructor consumes
one additional raw rand result.  This module binds those facts to exact Windows
build 13725832 and replays StartMission from the observable RNG state just
before its first random_removal call.

Map selection and the incoming CRT state remain boundary inputs.  The ordinary
solver still consumes the settled live board rather than forecasting setup.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.final_cave_map_choice import (
    FinalCaveMapChoiceError,
    _map_metadata,
    _native_directory_entries,
    validate_final_cave_map_choice_map,
)
from src.observatory.msvc_rng_replay import canonical_observable_state, draw
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)
from src.observatory.piston_scheduler_boundary import (
    PistonSchedulerBoundaryError,
    validate_piston_scheduler_boundary_map,
)
from src.observatory.rng_return_map import _scan_rng_calls


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_piston_setup_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_MAPS_REVISION_SHA256 = (
    "a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4"
)
EXPECTED_RNG_CALL_COUNT = 118
RNG_CORE_RVA = 0x00387F16


class PistonSetupBoundaryError(RuntimeError):
    """Raised when the exact Piston setup boundary cannot reproduce."""


DEPENDENCY_SPECS = (
    {
        "id": "final_cave_map_choice",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_cave_map_choice.json"
        ),
        "file_sha256": (
            "dce09ab926596f90e521475f24c00604be31a15d3808ef1d863e0f037df6e6ef"
        ),
        "canonical_sha256": (
            "8068a847b328ba8137ff9c88864f66eaaa0bf93c5f8ba34aedd1b4115e7936db"
        ),
        "role": (
            "Pins exact Win32 map-directory enumeration, MAP_LIST registration "
            "order, RandomMap filtering, native retry policy, and positive-bound "
            "random_int advancement."
        ),
    },
    {
        "id": "piston_scheduler_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_piston_scheduler_boundary.json"
        ),
        "file_sha256": (
            "4de5af4130b0ec1c45eee6804471a0de9da31cfaf1d1bb60a0035c59d20b9a4e"
        ),
        "canonical_sha256": (
            "3579738e75297d27bae3cd3ca2ba8fabc938e4520371f1259a4c3ee91490074e"
        ),
        "role": (
            "Pins the exact shipped Mission_Piston source, its static Pawn "
            "definitions, Env_Null inheritance, and settled-board scheduler."
        ),
    },
    {
        "id": "rng_return_ids",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_rng_return_ids.json"
        ),
        "file_sha256": (
            "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
        ),
        "canonical_sha256": (
            "d8c7e65344b77cef66745b3c85f7d7ec507a05158586134e990ae2d1b97bd205"
        ),
        "role": (
            "Pins all 118 raw direct-call candidates to the shared MSVC RNG "
            "core, including random_int, the Pawn constructor, and the guarded "
            "invalid-position fallback."
        ),
    },
)


SOURCE_SPECS = (
    {
        "path": "scripts/missions/acid/mission_piston.lua",
        "size": 2_420,
        "sha256": "1f426bad3b4149f0088831680264f716a3f9cc6acebf828306946c55990d51ad",
        "symbols": [
            "Mission_Piston",
            "Mission_Piston:StartMission",
            "Pawn_Piston_U",
            "Pawn_Piston_R",
            "Pawn_Piston_D",
            "Pawn_Piston_L",
        ],
    },
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
        "symbols": ["random_element", "random_removal"],
    },
    {
        "path": "scripts/events.lua",
        "size": 7_405,
        "sha256": "c47c17d4e3a57638cacf4546b186360a867c0a9457f926fd9bb57febdb37535a",
        "symbols": ["extract_table"],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257",
        "symbols": ["Mission", "Mission:GetMapTag", "Mission:BaseStart"],
    },
    {
        "path": "scripts/environments.lua",
        "size": 8_924,
        "sha256": "5f8a7d74f537abb33bc88c1f9669f3f6fabdd5c8c51aad3486d2e965e4fb80ec",
        "symbols": ["Environment:Start", "Env_Null"],
    },
    {
        "path": "maps/maphelper.lua",
        "size": 2_093,
        "sha256": "f6455082a050f734ccc60ef3df6914619f5a250832a79f71e3ad6f1758431077",
        "symbols": ["AddMap", "RandomMap"],
    },
)


# terrain_by_x stores eight strings indexed by x, with each character indexed
# by y.  Missing map records are ordinary road terrain zero.
MAP_SPECS = (
    {
        "name": "acid0",
        "map_list_index": 0,
        "size": 2_433,
        "sha256": "9e3daeb115afa3d8e2a57bee1fb65595a517759420b0fe24498bc2c384502fc5",
        "terrain_by_x": (
            "44300344", "43100134", "31100113", "00000000",
            "00011000", "30000003", "43000034", "44300344",
        ),
        "zone": (
            (4, 7), (4, 6), (5, 6), (5, 5), (6, 5), (6, 2), (5, 2),
            (5, 1), (4, 1), (4, 0), (4, 2), (4, 5), (4, 4), (4, 3),
        ),
    },
    {
        "name": "acid1",
        "map_list_index": 1,
        "size": 1_665,
        "sha256": "d348086ab042d0bf2355699a32cb3c745cd144fbd772f43ba46e72ca55698a95",
        "terrain_by_x": (
            "00000000", "01011010", "01000010", "00000000",
            "33000033", "00000000", "00000000", "33033033",
        ),
        "zone": (
            (6, 7), (6, 6), (6, 4), (6, 3), (6, 1), (6, 0), (2, 4),
            (2, 3), (2, 0), (2, 7), (5, 7), (5, 6), (5, 3), (5, 4),
            (5, 1), (5, 0),
        ),
    },
    {
        "name": "acid10",
        "map_list_index": 2,
        "size": 1_884,
        "sha256": "b506dfdce356fa89e98393a33a30559e9b79ffd9547a1ddd0b559e92172f971a",
        "terrain_by_x": (
            "03011044", "00011004", "03000000", "31100010",
            "00000010", "30000000", "00000030", "33303033",
        ),
        "zone": (
            (4, 0), (6, 0), (5, 6), (4, 6), (3, 6), (2, 6), (5, 7),
            (1, 6), (5, 0),
        ),
    },
    {
        "name": "acid11",
        "map_list_index": 3,
        "size": 1_765,
        "sha256": "4f2118c94b92f695237ea1ea32a1522c97360d63e83cf375b8f59c3d4bd22767",
        "terrain_by_x": (
            "00000034", "01101034", "03300034", "03301033",
            "33101013", "00000000", "00000000", "00000000",
        ),
        "zone": (
            (2, 4), (6, 2), (6, 1), (6, 0), (5, 6), (5, 4), (5, 2),
            (6, 6), (6, 4),
        ),
    },
    {
        "name": "acid15",
        "map_list_index": 7,
        "size": 1_584,
        "sha256": "d6ce18751c114114f51b17501d5429c7a3d5a602abb6448cbe08722e0ccb90e2",
        "terrain_by_x": (
            "40000004", "40110104", "00110104", "00000000",
            "00010000", "03000300", "03303300", "00000004",
        ),
        "zone": ((3, 7), (4, 7), (5, 7), (6, 7), (4, 4), (4, 2), (2, 2)),
    },
    {
        "name": "acid3",
        "map_list_index": 9,
        "size": 1_793,
        "sha256": "73fc3730648a7dbb78cbc6881caa16fd007eb47abd18b4b7aa7f8d5856104588",
        "terrain_by_x": (
            "00001444", "01001144", "01000334", "00000334",
            "30010014", "30000000", "30000000", "33000000",
        ),
        "zone": ((4, 6), (3, 3), (4, 2), (5, 2), (5, 3), (5, 6), (6, 6)),
    },
    {
        "name": "acid4",
        "map_list_index": 10,
        "size": 1_638,
        "sha256": "b6971aa39ea88abe2a322f106c0e91491dbb182aa0b0448f25b2f8d6e798da8c",
        "terrain_by_x": (
            "00000000", "30130130", "30130130", "00000000",
            "00000000", "30130130", "30030030", "00000000",
        ),
        "zone": (
            (3, 2), (3, 3), (4, 3), (4, 2), (3, 0), (4, 0), (3, 5),
            (3, 6), (4, 6), (4, 5),
        ),
    },
)


DIRECTION_SPECS = (
    {"value": 0, "name": "up", "short": "U", "pawn_type": "Pawn_Piston_U", "delta": (0, -1)},
    {"value": 1, "name": "right", "short": "R", "pawn_type": "Pawn_Piston_R", "delta": (1, 0)},
    {"value": 2, "name": "down", "short": "D", "pawn_type": "Pawn_Piston_D", "delta": (0, 1)},
    {"value": 3, "name": "left", "short": "L", "pawn_type": "Pawn_Piston_L", "delta": (-1, 0)},
)
BLOCKED_FORWARD_TERRAINS = {1, 3, 4}


REGION_SPECS = (
    ("map_loader", 0x001622B0, 0x00163CFC, "8e232f9d11aee6d546e6496cd5dfeed93d28ad811d20ec2a8072456fc352edd0", "Ghidra map-loader body containing ordered zone ingestion."),
    ("getzone", 0x0016D9F0, 0x0016DB0F, "b9afd4ac0e799ba1608f2734a17ca4ef3cbcbad346ad32388a3d2bfd94148568", "Ghidra Board:GetZone target body."),
    ("zone_lookup", 0x0016DF30, 0x0016E12B, "91f988fdcbeb90b07539b86903785687bcfd1864cdb0d72c5bc958319d02bfb3", "Ghidra named-zone lookup and PointList copy body."),
    ("pointlist_copy", 0x0009A8E0, 0x0009A92F, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0", "Ghidra PointList order-preserving copy body."),
    ("zone_create", 0x0016C040, 0x0016C13D, "3a7263905c040c883afd7c5fcb7f9e562019da8096d05df6efa4763798a484f3", "Ghidra named-zone creation body."),
    ("zone_append", 0x0016E130, 0x0016E1F1, "d41216b10077d3ac9c4e75fb7e3faf820f648e5f84c774fbcb1006aa7c6e079d", "Ghidra first-occurrence-preserving zone append body."),
    ("isvalid", 0x00162280, 0x001622A7, "ccc44e753f417cb103727661382ad7b18cd729f23a1bed12057027a3ef1506b1", "Ghidra Board coordinate-validity body."),
    ("ispawnspace_thunk", 0x000E7180, 0x000E7185, "35db3b17881aa60eaa25d8781db30c6df0065324b7097613cbe416b3add2e77c", "Ghidra secondary-this virtual thunk."),
    ("ispawnspace_body", 0x0016FD50, 0x0016FD66, "b5eed1df511c992ecc74b23340515fe754981e7328c9cd6293c2771e0243e758", "Ghidra live-only Board:IsPawnSpace body."),
    ("occupancy", 0x0016FD70, 0x0016FDE1, "8bed0407e45f2443921799cbe630af6ddae0d7f14b1d3c6199c6e3de818d6f69", "Ghidra tile-occupant predicate body."),
    ("getterrain", 0x00104B70, 0x00104B88, "bb0a4b8ace45f2208137e41a481c3d02d8c88c57e4b8def6e7d56776825eaf41", "Ghidra Board:GetTerrain target body."),
    ("getterrain_core", 0x0015EB40, 0x0015EB83, "08b4eea50daec1988817c68bb6c65743e773f32a02a55f8b7f8627c387bf1d89", "Ghidra tile lookup body."),
    ("clearspace", 0x00165DD0, 0x00165F15, "4eb4b55bfd3cda41d98896abeceafaea532c172a54266971855913245dc5291d", "Ghidra Board:ClearSpace target body."),
    ("clear_tile", 0x00161F90, 0x00162051, "b9db32b4afd49798529efb1baad2a5fcb8007044303c68278a211aac1950bed6", "Ghidra tile-clear helper body."),
    ("tile_helper", 0x001A03C0, 0x001A0461, "057f64d0c20e9fc3018d5a9d4ef3a80cd6bc3d697612cef28233abccd968a93d", "Ghidra clear-space tile helper body."),
    ("set_edge", 0x001744E0, 0x0017457F, "69e0892bc47ce95193a48c4d89c6c9b5831aec7edcb2b25f8d01b34e17743388", "Ghidra edge-state mutator called by ClearSpace."),
    ("isedge", 0x00170A20, 0x00170A4D, "73584f34e6e823a5e2b92298f3c8562ff91d29aaf7432ffc2b6a39851c281c6f", "Ghidra Board:IsEdge target body."),
    ("addpawn", 0x0016E8C0, 0x0016EC8D, "c9031f10d38ba7cb28959b3460aec686a4366b4697accc7479638436aaa7280a", "Ghidra Board:AddPawn(Pawn*,Point) body."),
    ("invalid_addpawn_fallback", 0x00172A90, 0x00172EF6, "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904", "Ghidra random-position fallback used only for an invalid supplied point."),
    ("createpawn_wrapper", 0x00244FE0, 0x00245066, "f7148da1226256df25b4eb4aa019a4f7ffcf354bac806f6b18e7ead5aa3bf095", "Ghidra one-argument PAWN_FACTORY:CreatePawn wrapper."),
    ("pawn_factory", 0x00244DF0, 0x00244FE0, "15a9ff7b5140c97a90f9907c90c506d051136da05475580861c2ba557cf88559", "Ghidra named Pawn factory body."),
    ("pawn_factory_construct", 0x00245070, 0x0024524E, "a6960b16cf81bfc75671f7901ade8f6dff4e1320e003aa93a7a1a245b3acae7e", "Ghidra allocation and common-constructor body."),
    ("pawn_constructor", 0x0022A920, 0x0022BAC8, "f358d6de02d4e48a82c3a8d02fe52617cf280ea89bf959dcf0e4c4aadf60887d", "Ghidra common Pawn constructor body."),
    ("pawn_definition_loader", 0x0022C0F0, 0x0022CBB7, "9c705957ab7a8afa137bb56e4d075b40a29ca8da45222fd318f2c821ac138148", "Ghidra source-definition loader body."),
    ("skill_list", 0x00242C50, 0x00242C72, "c94aea5aaaeb5aee0af4941b2e9450260386d1d1edfcc04ddfa312b70130e9d5", "Ghidra skill-list wrapper reached by factory and AddPawn."),
    ("random_int", 0x000E0C20, 0x000E0C3A, "76e4d6f1289067724a2b6a8348ef91cb772a9bb12f6debf07b66efc11a6dd70e", "Ghidra one-argument random_int body."),
    ("rng_core", 0x00387F16, 0x00387F37, "3d7a67186e320b23a31d2ca6f9281211b373b60d44f35531cf4369da45cf0179", "Ghidra shared MSVC rand body."),
    ("bind_bool_point", 0x002871F0, 0x00287291, "5d882eebecbc2d19686bce0f8cb92d71e17d9c9b0ba718b4a0f6497ac4764126", "Ghidra Luabind bool(Board::*)(Point) helper."),
    ("bind_getterrain_point", 0x00286FF0, 0x00287091, "c1d7ea169676500c1b1e4acc0f063bc41cf52e37a473ecd201b0c89095a2b2dc", "Ghidra Luabind terrain(Board::*)(Point) helper."),
    ("bind_addpawn_point", 0x002881A0, 0x00288240, "b73cd813a1e33f0bf9c62b5794f095331024615f533bfe479d9b99afada2a29a", "Ghidra Luabind Point(Board::*)(Pawn*,Point) helper."),
    ("bind_getzone", 0x00288F10, 0x00288FB0, "af9093764dfb69798d2f67183f5c4af69b7476407dfbe68926a8962749d4ff06", "Ghidra Luabind PointList(Board::*)(string) helper."),
    ("bind_clearspace", 0x00287690, 0x00287731, "5087409c2d00e0936fa1d728db1a3dc204155bc6c02106cfef608d936f97118f", "Ghidra Luabind void(Board::*)(Point) helper."),
    ("bind_createpawn_one", 0x0028E930, 0x0028E9C3, "bbf8a4374671e2d654e62b93152f541b32b66cdf2e3a4ab68c412d194cc214ad", "Ghidra Luabind Pawn*(PawnFactory::*)(string) helper."),
)


CONTROL_WINDOW_SPECS = (
    ("zone_create_in_encounter_order", "map_loader", 0x001639DF, "83ec188d45d48bcc50e82372eeff8bcfe84c860000", "Create the named zone before visiting its Lua array."),
    ("zone_point_append", "map_loader", 0x00163A50, "8d85b8feffff508d8d14ffffffe8debbeeff8bd0c645fc248d8df8feffffe8cd310100ff7004ff308d45d483ec188bcc50e88a71eeff8bcfe8a3a60000", "Read each next Lua Point, preserve x/y, and append it."),
    ("zone_loop_advance", "map_loader", 0x00163A98, "8d8d14ffffffe89de6eeff8d55988d8d14ffffffe89f88f0ff84c0759b", "Advance the Lua array iterator and loop without sorting."),
    ("getzone_copy_chain", "getzone", 0x0016DA59, "8d45dc8bcf50e8cc0400008d45dcc645fc01508d4de8e86ccef2ff8d45e8c645fc02508bcee85dcef2ff", "Look up the named zone and copy the stored PointList twice without reordering."),
    ("zone_lookup_copy", "zone_lookup", 0x0016DFAD, "837de80074438d450c8bcf50e802a5f5ff83c0188bcb50e817c9f2ff", "Copy the found zone record PointList at record offset +0x18."),
    ("zone_unique_append", "zone_append", 0x0016E18A, "8b40183bc674168b4d248b552039107505394804740783c0083bc675f03bc7751b8d452050518d45088bcb50e805a3f5ff83c4048d4818e8ba6ef4ff", "Scan existing points and append only an unseen point, preserving first occurrence."),
    ("isvalid_bounds", "isvalid", 0x00162280, "558bec8b450885c078173b41487d128b450c85c0780b3b414c7d06b0015dc2080032c05dc20800", "Require nonnegative x/y below Board width/height."),
    ("ispawnspace_live_only", "ispawnspace_body", 0x0016FD50, "558bec8b016a01ff750cff75088b404cffd05dc20800", "Dispatch the live-only occupant predicate."),
    ("getterrain_tile_field", "getterrain", 0x00104B70, "558becff750cff7508e8c29f05008b80e02a00005dc20800", "Look up the tile and return its terrain field."),
    ("clearspace_reviewed_calls", "clearspace", 0x00165DDA, "ff750c8bf1ff7508e8a9c1ffff8b068bce8b5d0c8b7d08538b400857ffd084c074118b46508d0c7f69d3bc2b0000031488eb038d565c8bcae8a9a5030033ff0f1f800000000057ff750c8bceff75086a00e8b0e600004783ff047cea", "Clear the selected tile and four edge flags through reviewed non-RNG helpers."),
    ("isedge_bounds", "isedge", 0x00170A20, "558bec837d0800741e8b550c85d274178b414848394508740e8b414c483bd0740632c05dc20800b0015dc20800", "Return true exactly on x/y zero or width/height minus one."),
    ("addpawn_valid_guard", "addpawn", 0x0016E91B, "8b038bcbff7514ff75108b4008ffd084c07519568d45b08bcb50e8564100008b08894d108b4004894514eb06", "Call random-position fallback only when the supplied Point fails Board:IsValid."),
    ("createpawn_one_wrapper", "createpawn_wrapper", 0x00245004, "8bf16a0283ec18c745fc000000008bcc8d45086aff6a00c741140f000000c741100000000050c60100e89e30dcff8bcee8b7fdffff", "Forward one type name to the named Pawn factory."),
    ("construct_common_pawn", "pawn_factory_construct", 0x002451A0, "568bcbe87857feff", "Pass the source definition into the common Pawn constructor."),
    ("constructor_hidden_rng", "pawn_constructor", 0x0022B783, "8bcee866090000e887c71500898624090000", "Load the static definition, consume one raw RNG result, and store it at Pawn+0x924."),
    ("skill_list_wrapper", "skill_list", 0x00242C50, "558bec51ff750881c194000000c745fc00000000e8e766e0ff8b45088be55dc20400", "The reached skill-list wrapper is distinct from the neighboring two-draw AnimTracker constructor."),
    ("positive_bound_random_int", "random_int", 0x000E0C20, "558bec837d0800750433c05dc3e8e4722a0099f77d088bc25dc3", "Only bound zero skips the RNG; every positive Piston bound advances once and returns output modulo bound."),
    ("shared_msvc_rng", "rng_core", 0x00387F16, "e8176e0000694818fd43030081c1c39e2600894818c1e91081e1ff7f00008bc1c3", "Advance state by 0x343fd and 0x269ec3, then return bits 16 through 30."),
)


DIRECT_EDGE_SPECS = (
    ("map_loader_to_zone_create", "map_loader", 0x001639EF, "e84c860000", "zone_create", 0x0016C040, "Create each named zone in encounter order."),
    ("map_loader_to_zone_append", "map_loader", 0x00163A88, "e8a3a60000", "zone_append", 0x0016E130, "Append each converted Lua-array Point."),
    ("map_loader_embedded_pawn_path", "map_loader", 0x00163669, "e8021a0e00", "pawn_factory_construct", 0x00245070, "Map records with embedded pawns can construct them; all seven exact Piston maps have none."),
    ("getzone_to_lookup", "getzone", 0x0016DA5F, "e8cc040000", "zone_lookup", 0x0016DF30, "Look up the stored named zone."),
    ("getzone_first_copy", "getzone", 0x0016DA6F, "e86ccef2ff", "pointlist_copy", 0x0009A8E0, "Copy the lookup result."),
    ("getzone_second_copy", "getzone", 0x0016DA7E, "e85dcef2ff", "pointlist_copy", 0x0009A8E0, "Copy into the Luabind return value."),
    ("zone_lookup_to_copy", "zone_lookup", 0x0016DFC4, "e817c9f2ff", "pointlist_copy", 0x0009A8E0, "Copy the stored record PointList."),
    ("getterrain_to_tile_lookup", "getterrain", 0x00104B79, "e8c29f0500", "getterrain_core", 0x0015EB40, "Resolve the tile before reading terrain."),
    ("clearspace_to_clear_tile", "clearspace", 0x00165DE2, "e8a9c1ffff", "clear_tile", 0x00161F90, "Clear the selected source tile."),
    ("clearspace_to_tile_helper", "clearspace", 0x00165E12, "e8a9a50300", "tile_helper", 0x001A03C0, "Resolve the tile state used for clearing."),
    ("clearspace_to_edge_mutator", "clearspace", 0x00165E2B, "e8b0e60000", "set_edge", 0x001744E0, "Clear four directional edge flags."),
    ("addpawn_to_invalid_fallback", "addpawn", 0x0016E935, "e856410000", "invalid_addpawn_fallback", 0x00172A90, "Choose a random position only after supplied-coordinate invalidity."),
    ("addpawn_to_skill_list", "addpawn", 0x0016EAF0, "e85b410d00", "skill_list", 0x00242C50, "Read the created Pawn skill list without entering the adjacent RNG function."),
    ("createpawn_wrapper_to_factory", "createpawn_wrapper", 0x00245034, "e8b7fdffff", "pawn_factory", 0x00244DF0, "Forward the one-argument CreatePawn call."),
    ("factory_to_construct", "pawn_factory", 0x00244E56, "e815020000", "pawn_factory_construct", 0x00245070, "Allocate and construct the named Pawn."),
    ("factory_to_skill_list", "pawn_factory", 0x00244E98, "e8b3ddffff", "skill_list", 0x00242C50, "Read the static skill list through the non-RNG wrapper."),
    ("construct_to_constructor", "pawn_factory_construct", 0x002451A3, "e87857feff", "pawn_constructor", 0x0022A920, "Enter the common Pawn constructor."),
    ("constructor_to_definition_loader", "pawn_constructor", 0x0022B785, "e866090000", "pawn_definition_loader", 0x0022C0F0, "Load the static Piston definition before the hidden draw."),
    ("constructor_to_rng", "pawn_constructor", 0x0022B78A, "e887c71500", "rng_core", 0x00387F16, "Consume the one hidden constructor draw."),
    ("invalid_fallback_rng_one", "invalid_addpawn_fallback", 0x00172E16, "e8fb502100", "rng_core", 0x00387F16, "First RNG site in the invalid-coordinate fallback."),
    ("invalid_fallback_rng_two", "invalid_addpawn_fallback", 0x00172E70, "e8a1502100", "rng_core", 0x00387F16, "Second RNG site in the invalid-coordinate fallback."),
    ("random_int_to_rng", "random_int", 0x000E0C2D, "e8e4722a00", "rng_core", 0x00387F16, "Advance the shared generator for every positive bound."),
)


BINDING_SPECS = (
    ("isvalid_point", 0x00279C4C, "c745e8c3396e00ff75f0c745ec00000000518d4de85168d08583008bc8e882d50000", 0x006E39C3, 0, 0x00279C69, "bind_bool_point", 0x002871F0),
    ("ispawnspace_point", 0x00279C96, "c745e880714e00ff75f0c745ec0c000000518d4de85168c48583008bc8e838d50000", 0x004E7180, 12, 0x00279CB3, "bind_bool_point", 0x002871F0),
    ("getterrain_point", 0x00279FA1, "c745e8704b5000ff75f0c745ec00000000518d4de85168c08683008bc8e82dd00000", 0x00504B70, 0, 0x00279FBE, "bind_getterrain_point", 0x00286FF0),
    ("addpawn_pawn_point", 0x0027A14D, "c745e8c0e85600ff75f0c745ec00000000518d4de851518bc8e835e00000", 0x0056E8C0, 0, 0x0027A166, "bind_addpawn_point", 0x002881A0),
    ("getzone_string", 0x0027A53E, "c745e8f0d95600ff75f0c745ec00000000518d4de851518bc8e8b4e90000", 0x0056D9F0, 0, 0x0027A557, "bind_getzone", 0x00288F10),
    ("clearspace_point", 0x0027A9C6, "c745e8d05d5600ff75f0c745ec00000000518d4de85168888983008bc8e8a8cc0000", 0x00565DD0, 0, 0x0027A9E3, "bind_clearspace", 0x00287690),
    ("isedge_point", 0x0027AB0B, "c745e8200a5700ff75f0c745ec00000000518d4de851680c8a83008bc8e8c3c60000", 0x00570A20, 0, 0x0027AB28, "bind_bool_point", 0x002871F0),
    ("createpawn_one_string", 0x0027D375, "c745ece04f6400ff75f0518d4dec51518bc8e8a4150100", 0x00644FE0, None, 0x0027D387, "bind_createpawn_one", 0x0028E930),
)


DATA_POINTER_SPECS = (
    ("board_primary_isvalid_slot", 0x0042E304, ".rdata", "80225600", "isvalid", 0x00162280, "Board primary vtable slot +0x08 resolves the IsValid thunk to the exact bounds body."),
    ("board_secondary_occupancy_slot", 0x0042E2A4, ".rdata", "70fd5600", "occupancy", 0x0016FD70, "Board secondary vtable slot +0x4c resolves the occupancy predicate."),
    ("board_secondary_ispawnspace_slot", 0x0042E2A8, ".rdata", "50fd5600", "ispawnspace_body", 0x0016FD50, "Board secondary vtable slot +0x50 resolves IsPawnSpace."),
)


VECTOR_ANCHOR_SPECS = (
    ("VEC_UP", 0x00494DA4, "00000000ffffffff", (0, -1)),
    ("VEC_DOWN", 0x00494DAC, "0000000001000000", (0, 1)),
    ("VEC_RIGHT", 0x00494DB4, "0100000000000000", (1, 0)),
    ("VEC_LEFT", 0x00494DBC, "ffffffff00000000", (-1, 0)),
)


SCALAR_ANCHOR_SPECS = (
    ("DIR_UP", 0x0004B7FE, "6a00", 0),
    ("DIR_RIGHT", 0x0004B9A2, "6a01", 1),
    ("DIR_DOWN", 0x0004B88A, "6a02", 2),
    ("DIR_LEFT", 0x0004B916, "6a03", 3),
    ("DIR_START", 0x0004BABA, "6a00", 0),
    ("DIR_END", 0x0004BBD2, "6a03", 3),
)


STRING_ANCHOR_SPECS = (
    ("GetZone", 0x00438800, 0x00288F5F, "c7420800888300"),
    ("IsValid", 0x004385D0, 0x00279C62, "68d0858300"),
    ("IsPawnSpace", 0x004385C4, 0x00279CAC, "68c4858300"),
    ("GetTerrain", 0x004386C0, 0x00279FB7, "68c0868300"),
    ("AddPawn", 0x00438714, 0x002881EF, "c7420814878300"),
    ("ClearSpace", 0x00438988, 0x0027A9DC, "6888898300"),
    ("IsEdge", 0x00438A0C, 0x0027AB21, "680c8a8300"),
    ("CreatePawn", 0x00439488, 0x0028E978, "c7420888948300"),
    ("PAWN_FACTORY", 0x004396E0, 0x0027E048, "68e0968300"),
)


EXPECTED_REGION_RNG_CALLS = {
    "invalid_addpawn_fallback": (0x00172E16, 0x00172E70),
    "pawn_constructor": (0x0022B78A,),
    "random_int": (0x000E0C2D,),
}


_ENTRY_RE = re.compile(
    r'\{\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,'
    r'\s*\["terrain"\]\s*=\s*(\d+)'
)
_ZONE_RE = re.compile(r'\["pistons"\]\s*=\s*\{(.*?)\}', re.DOTALL)
_POINT_RE = re.compile(r'Point\(\s*(\d+)\s*,\s*(\d+)\s*\)')
_TAGS_RE = re.compile(r'\["tags"\]\s*=\s*\{([^}]*)\}')
_QUOTED_RE = re.compile(r'"([^"]+)"')


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
        raise PistonSetupBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise PistonSetupBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise PistonSetupBoundaryError("reviewed direct edge is not CALL rel32")
    return (rva + 5 + struct.unpack("<i", encoded[1:])[0]) & 0xFFFFFFFF


def _map_spec(map_name: str) -> Mapping[str, Any]:
    if type(map_name) is not str:
        raise PistonSetupBoundaryError("map name must be a string")
    for spec in MAP_SPECS:
        if spec["name"] == map_name:
            return spec
    raise PistonSetupBoundaryError(
        "map name must be one of " + ", ".join(spec["name"] for spec in MAP_SPECS)
    )


def _valid(point: tuple[int, int]) -> bool:
    return 0 <= point[0] < 8 and 0 <= point[1] < 8


def _edge(point: tuple[int, int]) -> bool:
    return point[0] in (0, 7) or point[1] in (0, 7)


def _terrain(spec: Mapping[str, Any], point: tuple[int, int]) -> int:
    if not _valid(point):
        return 0
    return int(spec["terrain_by_x"][point[0]][point[1]])


def _eligible_directions(
    spec: Mapping[str, Any],
    source: tuple[int, int],
    occupied: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for direction in DIRECTION_SPECS:
        dx, dy = direction["delta"]
        front = (source[0] + dx, source[1] + dy)
        terrain = _terrain(spec, front)
        if (
            terrain not in BLOCKED_FORWARD_TERRAINS
            and front not in occupied
            and _valid(front)
            and not _edge(front)
        ):
            choices.append(
                {
                    "native_value": direction["value"],
                    "direction": direction["name"],
                    "short": direction["short"],
                    "pawn_type": direction["pawn_type"],
                    "front": [front[0], front[1]],
                    "terrain": terrain,
                }
            )
    return choices


def _rng_draw(
    state: int,
    ordinal: int,
    source: str,
    bound: int | None,
) -> tuple[dict[str, Any], int]:
    result, next_state = draw(state)
    record: dict[str, Any] = {
        "ordinal": ordinal,
        "source": source,
        "state_before": f"0x{canonical_observable_state(state):08x}",
        "result": result,
        "state_after": f"0x{canonical_observable_state(next_state):08x}",
        "bound": bound,
        "remainder": None if bound is None else result % bound,
    }
    return record, next_state


def replay_piston_start_mission(
    map_name: str,
    pre_call_state: int,
) -> dict[str, Any]:
    """Replay StartMission from the state before its first zone-removal draw.

    The permanently hidden top state bit is canonicalized because it never
    changes any current or future MSVC rand result.
    """
    if type(pre_call_state) is not int or not 0 <= pre_call_state <= 0xFFFFFFFF:
        raise PistonSetupBoundaryError("RNG state must be a 32-bit unsigned integer")
    spec = _map_spec(map_name)
    initial_state = canonical_observable_state(pre_call_state)
    current_state = initial_state
    zone = [tuple(point) for point in spec["zone"]]
    occupied: set[tuple[int, int]] = set()
    attempts: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []
    transcript: list[dict[str, Any]] = []

    while len(placements) < 4 and zone:
        attempt_number = len(attempts) + 1
        zone_size_before = len(zone)
        candidate_draw, current_state = _rng_draw(
            current_state,
            len(transcript) + 1,
            "random_removal(pistons_zone)",
            zone_size_before,
        )
        transcript.append(candidate_draw)
        candidate_index = candidate_draw["remainder"]
        assert isinstance(candidate_index, int)
        source = zone.pop(candidate_index)
        choices = _eligible_directions(spec, source, occupied)
        attempt: dict[str, Any] = {
            "attempt": attempt_number,
            "zone_size_before": zone_size_before,
            "candidate_index_zero_based": candidate_index,
            "source": [source[0], source[1]],
            "eligible_directions": [item["short"] for item in choices],
            "accepted": bool(choices),
            "draws_consumed": 1 if not choices else 3,
        }
        if not choices:
            attempt["zone_size_after"] = len(zone)
            attempts.append(attempt)
            continue

        direction_draw, current_state = _rng_draw(
            current_state,
            len(transcript) + 1,
            "random_element(eligible_directions)",
            len(choices),
        )
        transcript.append(direction_draw)
        direction_index = direction_draw["remainder"]
        assert isinstance(direction_index, int)
        choice = choices[direction_index]
        constructor_draw, current_state = _rng_draw(
            current_state,
            len(transcript) + 1,
            "Pawn common constructor raw draw",
            None,
        )
        transcript.append(constructor_draw)

        occupied.add(source)
        front = tuple(choice["front"])
        removed_forward = False
        if front in zone:
            zone.remove(front)
            removed_forward = True
        placement = {
            "placement_index": len(placements) + 1,
            "source": [source[0], source[1]],
            "direction": choice["direction"],
            "direction_native_value": choice["native_value"],
            "pawn_type": choice["pawn_type"],
            "front": choice["front"],
            "constructor_raw_result": constructor_draw["result"],
            "forward_removed_from_zone": removed_forward,
        }
        placements.append(placement)
        attempt.update(
            {
                "chosen_direction_index_zero_based": direction_index,
                "chosen_direction": choice["short"],
                "constructor_raw_result": constructor_draw["result"],
                "forward_removed_from_zone": removed_forward,
                "zone_size_after": len(zone),
            }
        )
        attempts.append(attempt)

    rejected_count = sum(not item["accepted"] for item in attempts)
    return {
        "analysis_kind": "native_piston_start_mission_replay",
        "build_id": EXPECTED_BUILD_ID,
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "map_name": map_name,
        "boundary": (
            "observable MSVC state immediately before StartMission's first "
            "random_removal(pistons zone) draw"
        ),
        "input_state": f"0x{pre_call_state:08x}",
        "canonical_observable_pre_call_state": f"0x{initial_state:08x}",
        "canonical_observable_final_state": (
            f"0x{canonical_observable_state(current_state):08x}"
        ),
        "attempt_count": len(attempts),
        "accepted_count": len(placements),
        "rejected_count": rejected_count,
        "draw_count": len(transcript),
        "draw_count_formula_holds": (
            len(transcript) == len(attempts) + 2 * len(placements)
        ),
        "placements": placements,
        "attempts": attempts,
        "rng_transcript": transcript,
        "remaining_zone": [[point[0], point[1]] for point in zone],
        "occupied_piston_sources": [item["source"] for item in placements],
    }


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _source_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in SOURCE_SPECS]


def _initial_choice_records(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for point in spec["zone"]:
        choices = _eligible_directions(spec, tuple(point), set())
        result.append(
            {
                "source": [point[0], point[1]],
                "directions": [item["short"] for item in choices],
                "guaranteed_initial_rejection": not choices,
            }
        )
    return result


def _expected_map_tags(spec: Mapping[str, Any]) -> tuple[str, ...]:
    if spec["name"] in {"acid15", "acid4"}:
        return ("generic", "acid", "pistons")
    return ("generic", "acid", "acid_pool", "pistons")


def _map_records() -> list[dict[str, Any]]:
    return [
        {
            "candidate_index_zero_based": index,
            "map_list_index_zero_based": spec["map_list_index"],
            "map_name": spec["name"],
            "path": f"maps/{spec['name']}.map",
            "size": spec["size"],
            "sha256": spec["sha256"],
            "dimensions": [8, 8],
            "tags": list(_expected_map_tags(spec)),
            "terrain_encoding": "terrain_by_x[x][y], decimal terrain enum",
            "terrain_by_x": list(spec["terrain_by_x"]),
            "pistons_zone": [[point[0], point[1]] for point in spec["zone"]],
            "zone_size": len(spec["zone"]),
            "initial_eligible_directions": _initial_choice_records(spec),
            "embedded_pawns": [],
            "spawns": [],
            "spawn_ids": [],
            "spawn_points": [],
            "evidence_class": "fact",
        }
        for index, spec in enumerate(MAP_SPECS)
    ]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "start_rva": f"0x{item[1]:08x}",
            "end_rva_exclusive": f"0x{item[2]:08x}",
            "size": item[2] - item[1],
            "sha256": item[3],
            "section": ".text",
            "evidence_class": "fact",
            "boundary_basis": item[4],
        }
        for item in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "region": item[1],
            "start_rva": f"0x{item[2]:08x}",
            "size": len(bytes.fromhex(item[3])),
            "instruction_hex": item[3],
            "sha256": hashlib.sha256(bytes.fromhex(item[3])).hexdigest(),
            "evidence_class": "fact",
            "meaning": item[4],
        }
        for item in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "kind": "direct_rel32",
            "source_region": item[1],
            "from_rva": f"0x{item[2]:08x}",
            "instruction_hex": item[3],
            "target_region": item[4],
            "target_rva": f"0x{item[5]:08x}",
            "evidence_class": "fact",
            "meaning": item[6],
        }
        for item in DIRECT_EDGE_SPECS
    ]


def _binding_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "start_rva": f"0x{item[1]:08x}",
            "instruction_hex": item[2],
            "native_target_va": f"0x{item[3]:08x}",
            "native_target_rva": f"0x{item[3] - EXPECTED_IMAGE_BASE:08x}",
            "this_adjustment": item[4],
            "helper_call_rva": f"0x{item[5]:08x}",
            "helper_region": item[6],
            "helper_target_rva": f"0x{item[7]:08x}",
            "evidence_class": "fact",
        }
        for item in BINDING_SPECS
    ]


def _data_pointer_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "data_rva": f"0x{item[1]:08x}",
            "section": item[2],
            "data_hex": item[3],
            "target_region": item[4],
            "target_rva": f"0x{item[5]:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + item[5]:08x}",
            "evidence_class": "fact",
            "meaning": item[6],
        }
        for item in DATA_POINTER_SPECS
    ]


def _vector_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "data_rva": f"0x{item[1]:08x}",
            "section": ".data",
            "data_hex": item[2],
            "point": [item[3][0], item[3][1]],
            "evidence_class": "fact",
        }
        for item in VECTOR_ANCHOR_SPECS
    ]


def _scalar_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "instruction_rva": f"0x{item[1]:08x}",
            "instruction_hex": item[2],
            "value": item[3],
            "evidence_class": "fact",
        }
        for item in SCALAR_ANCHOR_SPECS
    ]


def _string_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "string_rva": f"0x{item[1]:08x}",
            "string_hex": (item[0] + "\0").encode("ascii").hex(),
            "reference_rva": f"0x{item[2]:08x}",
            "reference_hex": item[3],
            "evidence_class": "fact",
        }
        for item in STRING_ANCHOR_SPECS
    ]


def _replay_vectors() -> list[dict[str, Any]]:
    result = []
    for state in (0x00000000, 0x00000001, 0x12345678):
        for spec in MAP_SPECS:
            replay = replay_piston_start_mission(spec["name"], state)
            result.append(
                {
                    "map_name": spec["name"],
                    "pre_call_state": f"0x{state:08x}",
                    "accepted_count": replay["accepted_count"],
                    "rejected_count": replay["rejected_count"],
                    "draw_count": replay["draw_count"],
                    "final_state": replay["canonical_observable_final_state"],
                    "placements": replay["placements"],
                    "full_replay_canonical_sha256": _canonical_sha256(replay),
                }
            )
    return result


def _contracts() -> dict[str, Any]:
    return {
        "map_selection": {
            "mission_map_tags": ["pistons"],
            "mission_map_vetoes": [],
            "input_sector": "acid",
            "get_map_tag_draw": {
                "bound": 1,
                "advances_rng": True,
                "result": 0,
                "semantic_result": "pistons",
            },
            "candidate_order": [spec["name"] for spec in MAP_SPECS],
            "candidate_count": len(MAP_SPECS),
            "draw_per_random_map_attempt": 1,
            "random_map_bound": len(MAP_SPECS),
            "retry_reasons": ["mission veto", "already-used map"],
            "retry_limit": 10,
            "used_map_registry_available_to_solver": False,
            "selected_map_available_after_live_board_read": True,
        },
        "base_start_order": {
            "before_start_mission": [
                "optional AssetId building",
                "LiveEnvironment construction",
                "LiveEnvironment:Start",
            ],
            "mission_piston_asset_id": "",
            "mission_piston_environment": "Env_Null",
            "env_null_start_is_empty": True,
            "start_mission_position": 4,
            "after_start_mission": [
                "SetupDiffMod",
                "optional bonus debris",
                "SpawnPawns",
            ],
            "candidate_maps_have_embedded_pawns": False,
            "candidate_maps_have_spawn_entries": False,
            "initial_pawn_occupancy_during_piston_selection": [],
        },
        "zone_order": {
            "map_loader_source_order": "Lua array encounter order",
            "duplicate_policy": "append first occurrence only",
            "getzone_copy_preserves_order": True,
            "extract_table_indices": "1 through PointList:size in order",
            "sorting_step_present": False,
            "all_candidate_zones_unique": True,
            "all_candidate_zone_points_valid": True,
        },
        "direction_order": {
            "dir_start": 0,
            "dir_end": 3,
            "ordered_values": [
                {
                    "value": item["value"],
                    "name": item["name"],
                    "short": item["short"],
                    "pawn_type": item["pawn_type"],
                    "delta": list(item["delta"]),
                }
                for item in DIRECTION_SPECS
            ],
        },
        "candidate_predicate": {
            "terrain_rejections": {
                "TERRAIN_BUILDING": 1,
                "TERRAIN_WATER": 3,
                "TERRAIN_MOUNTAIN": 4,
            },
            "requires_not_pawn_space": True,
            "requires_valid": True,
            "requires_not_edge": True,
            "edge_coordinates": "x == 0, y == 0, x == width-1, or y == height-1",
            "placed_source_becomes_occupied_immediately": True,
            "chosen_front_removed_from_remaining_zone_if_present": True,
            "choices_recomputed_after_every_attempt": True,
        },
        "rng_grammar": {
            "core_transition": "state = state * 0x343fd + 0x269ec3 (mod 2^32)",
            "core_output": "(state >> 16) & 0x7fff",
            "observable_state_mask": "0x7fffffff",
            "candidate_draw": "one random_int(current zone size) on every attempt",
            "rejected_attempt_draws": 1,
            "accepted_attempt_draws": 3,
            "accepted_draw_order": [
                "random_int(current zone size)",
                "random_int(current eligible direction count)",
                "common Pawn constructor raw rand",
            ],
            "constructor_call_rva": "0x0022b78a",
            "constructor_caller_id": 108,
            "constructor_store_offset": "Pawn+0x924",
            "random_int_call_rva": "0x000e0c2d",
            "random_int_caller_id": 21,
            "draw_count_formula": "attempt_count + 2 * accepted_count",
            "all_start_mission_bounds_positive": True,
            "random_int_one_advances": True,
        },
        "guarded_paths": {
            "addpawn_invalid_fallback_call_rva": "0x0016e935",
            "fallback_rng_call_rvas": ["0x00172e16", "0x00172e70"],
            "fallback_rng_caller_ids": [59, 60],
            "fallback_reachable_for_candidate_zone_points": False,
            "reason": "Every candidate source is an in-bounds Point from an exact 8x8 map zone.",
            "skill_list_wrapper_rva": "0x00242c50",
            "adjacent_animtracker_rng_function_rva": "0x00242cb0",
            "adjacent_rng_caller_ids": [116, 117],
            "adjacent_rng_function_reached_by_piston_factory": False,
        },
        "replay_boundary": {
            "input": (
                "selected exact map name plus observable MSVC state immediately "
                "before StartMission's first zone-removal draw"
            ),
            "output": (
                "ordered attempts, placements, draw transcript, constructor raw "
                "results, remaining zone, and final observable state"
            ),
            "incoming_state_available_to_solver": False,
            "concrete_forecast_without_input_state": False,
            "settled_bridge_board_remains_authoritative": True,
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "piston_map_pool_and_zone_order",
            "classification": "fact",
            "claim": (
                "The exact installation admits seven acid-sector Piston maps in "
                "the pinned MAP_LIST order, and each pistons zone reaches Lua in "
                "its source encounter order without sorting."
            ),
        },
        {
            "id": "dynamic_placement_predicate",
            "classification": "fact",
            "claim": (
                "Every attempt removes one source, recomputes U/R/D/L choices, "
                "rejects blocked terrain, pawns, invalid points, and edges, then "
                "removes an accepted forward zone point if still present."
            ),
        },
        {
            "id": "rejected_attempt_draw_count",
            "classification": "fact",
            "claim": (
                "A rejected source consumes exactly its positive-bound candidate "
                "draw and no direction or Pawn-construction draw."
            ),
        },
        {
            "id": "hidden_constructor_draw",
            "classification": "fact",
            "claim": (
                "Every accepted placement consumes candidate and direction draws, "
                "then the common Pawn constructor unconditionally consumes one raw "
                "MSVC result and stores it at Pawn+0x924."
            ),
        },
        {
            "id": "invalid_fallback_excluded",
            "classification": "inference",
            "claim": (
                "AddPawn's random-position helper contains two RNG sites but is "
                "guarded by supplied-coordinate invalidity; all exact zone sources "
                "are valid, so neither site contributes to Piston setup."
            ),
        },
        {
            "id": "parameterized_replay_complete",
            "classification": "inference",
            "claim": (
                "Given the selected shipped map and incoming observable CRT state, "
                "the ordered Piston placements and outgoing observable state are "
                "fully replayable offline."
            ),
        },
        {
            "id": "solver_boundary_unchanged",
            "classification": "inference",
            "claim": (
                "Ordinary solving begins after setup and already reads ordered live "
                "Pistons. Without the incoming CRT state and used-map registry, Rust "
                "must not fabricate a pre-mission placement forecast."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "incoming_shared_crt_state",
            "question": "What is the shared CRT state immediately before the one-entry Piston map-tag draw?",
            "next_evidence": "Capture or recover the state at that exact boundary only if concrete pre-board forecasting becomes useful.",
        },
        {
            "id": "concrete_used_map_registry",
            "question": "Which Piston candidates are already used, and how many RandomMap attempts occur for one future mission?",
            "next_evidence": "Read the concrete campaign registry or observe the selected map; the retry grammar and seven-entry remainder mapping are already exact.",
        },
        {
            "id": "concrete_runtime_instances",
            "question": "What concrete Piston UIDs and constructor-field values materialize in a future mission?",
            "next_evidence": "Use the settled bridge board and, only if needed, the parameterized replay with a recovered incoming state.",
        },
        {
            "id": "modded_or_non_windows_setup",
            "question": "Do mods, macOS, or another depot preserve this exact setup boundary?",
            "next_evidence": "Build a separate executable/content/installation-keyed artifact before generalizing.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
    replay_vectors = _replay_vectors()
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
            "maps_revision_sha256": EXPECTED_MAPS_REVISION_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
        },
        "dependencies": _dependency_records(),
        "sources": _source_records(),
        "maps": _map_records(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "bindings": _binding_records(),
        "data_pointers": _data_pointer_records(),
        "vector_anchors": _vector_anchor_records(),
        "scalar_anchors": _scalar_anchor_records(),
        "string_anchors": _string_anchor_records(),
        "rng_call_inventory": {
            "raw_direct_call_candidate_count": EXPECTED_RNG_CALL_COUNT,
            "rng_core_rva": f"0x{RNG_CORE_RVA:08x}",
            "reviewed_region_calls": {
                region: [f"0x{rva:08x}" for rva in calls]
                for region, calls in EXPECTED_REGION_RNG_CALLS.items()
            },
            "all_other_pinned_regions_have_no_direct_rng_core_calls": True,
        },
        "contracts": _contracts(),
        "replay_vectors": replay_vectors,
        "findings": findings,
        "refines": [
            {
                "artifact": DEPENDENCY_SPECS[1]["path"],
                "resolved_unresolved_ids": ["mission_piston_setup_rng"],
                "qualification": (
                    "The stock setup grammar and parameterized replay are exact. "
                    "The incoming shared state, concrete used-map registry, and "
                    "future selected map remain runtime inputs rather than static facts."
                ),
            }
        ],
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction_found": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "current_simulator_version": 408,
            "reason": (
                "The Rust solver consumes the settled bridge board after setup. "
                "Replaying an unavailable pre-setup state would weaken, not improve, "
                "that authoritative boundary."
            ),
        },
        "notes": [
            "This is exact-build static evidence plus a parameterized offline replay, not a concrete runtime capture.",
            "Constructor raw result means the 15-bit rand return before any modulo; the purpose of Pawn+0x924 is outside this placement claim.",
            "The hidden top CRT state bit is discarded because it never changes any future observable result.",
            "Fresh bridge state remains authoritative for the selected map, Piston UIDs, and settled placement order.",
        ],
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "source_count": len(SOURCE_SPECS),
            "map_count": len(MAP_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "binding_count": len(BINDING_SPECS),
            "data_pointer_count": len(DATA_POINTER_SPECS),
            "vector_anchor_count": len(VECTOR_ANCHOR_SPECS),
            "scalar_anchor_count": len(SCALAR_ANCHOR_SPECS),
            "string_anchor_count": len(STRING_ANCHOR_SPECS),
            "replay_vector_count": len(replay_vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "candidate_order_proven": True,
            "zone_order_proven": True,
            "rejected_draw_count_proven": True,
            "constructor_draw_proven": True,
            "parameterized_replay_complete": True,
            "concrete_forecast_proven": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _verify_dependencies(executable: Path, content_root: Path) -> Mapping[str, Any]:
    repository_root = Path(__file__).resolve().parents[2]
    values: dict[str, Mapping[str, Any]] = {}
    validators = {
        "final_cave_map_choice": validate_final_cave_map_choice_map,
        "piston_scheduler_boundary": validate_piston_scheduler_boundary_map,
    }
    for spec in DEPENDENCY_SPECS:
        path = repository_root / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise PistonSetupBoundaryError(f"dependency missing: {spec['id']}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise PistonSetupBoundaryError(f"dependency file differs: {spec['id']}")
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise PistonSetupBoundaryError(f"dependency fields differ: {spec['id']}")
        values[spec["id"]] = value
        validator = validators.get(spec["id"])
        if validator is None:
            continue
        try:
            validator(executable, content_root, value)
        except (FinalCaveMapChoiceError, PistonSchedulerBoundaryError) as exc:
            raise PistonSetupBoundaryError(
                f"dependency does not reproduce: {spec['id']}: {exc}"
            ) from exc
    return values["rng_return_ids"]


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise PistonSetupBoundaryError("content root is not a directory")
    values: dict[str, bytes] = {}
    for spec in SOURCE_SPECS:
        source = root / spec["path"]
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise PistonSetupBoundaryError(
                f"source is missing or escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise PistonSetupBoundaryError(
                f"source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if len(raw) != spec["size"] or hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise PistonSetupBoundaryError(f"source identity differs: {spec['path']}")
        values[spec["path"]] = raw

    checks = {
        "scripts/missions/acid/mission_piston.lua": (
            b'MapTags = {"pistons"}',
            b"local zone = extract_table(Board:GetZone(\"pistons\"))",
            b"local p = random_removal(zone)",
            b"for dir = DIR_START, DIR_END do",
            b"not Board:IsPawnSpace(curr)",
            b"Board:IsValid(curr)",
            b"not Board:IsEdge(curr)",
            b"local dir = random_element(choices)",
            b"Board:ClearSpace(p)",
            b"Board:AddPawn(PAWN_FACTORY:CreatePawn(names[dir + 1]),p)",
            b"table.remove(zone,i)",
        ),
        "scripts/global.lua": (
            b"return list[random_int(#list)+1]",
            b"return table.remove(list,random_int(#list)+1)",
        ),
        "scripts/events.lua": (
            b"for i = 1, pointlist:size() do",
            b"ret[i] = pointlist:index(i)",
        ),
        "scripts/missions/missions.lua": (
            b'AssetId = ""',
            b"MapVetoes = {}",
            b"return random_element(self.MapTags)",
            b"self.LiveEnvironment:Start()",
            b"self:StartMission()",
            b"self:SetupDiffMod()",
            b"self:SpawnPawns(self:GetStartingPawns())",
        ),
        "scripts/environments.lua": (
            b"function Environment:Start() end",
            b"Env_Null = Environment:new",
        ),
        "maps/maphelper.lua": (
            b"MAP_LIST[#MAP_LIST+1] = mapname",
            b"for i,mapname in ipairs(MAP_LIST) do",
            b"return ret[random_int(#ret)+1]",
        ),
    }
    for path, tokens in checks.items():
        if any(token not in values[path] for token in tokens):
            raise PistonSetupBoundaryError(f"source semantics differ: {path}")


def _parse_map(raw: str) -> dict[str, Any]:
    dimension = re.search(
        r'\["dimensions"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)', raw
    )
    name = re.search(r'\["name"\]\s*=\s*"([^"]+)"', raw)
    zone = _ZONE_RE.search(raw)
    tags = _TAGS_RE.search(raw)
    if dimension is None or name is None or zone is None or tags is None:
        raise PistonSetupBoundaryError("Piston map structure differs")
    terrain: dict[tuple[int, int], int] = {}
    for x_text, y_text, terrain_text in _ENTRY_RE.findall(raw):
        point = (int(x_text), int(y_text))
        if point in terrain:
            raise PistonSetupBoundaryError("Piston map repeats a terrain Point")
        terrain[point] = int(terrain_text)
    rows = tuple(
        "".join(str(terrain.get((x, y), 0)) for y in range(8)) for x in range(8)
    )
    points = tuple(tuple(map(int, item)) for item in _POINT_RE.findall(zone.group(1)))
    return {
        "dimensions": (int(dimension.group(1)), int(dimension.group(2))),
        "name": name.group(1),
        "terrain_by_x": rows,
        "zone": points,
        "tags": tuple(_QUOTED_RE.findall(tags.group(1))),
        "empty_spawn_tables": all(
            re.search(rf'\["{field}"\]\s*=\s*\{{\s*\}}', raw)
            for field in ("spawns", "spawn_ids", "spawn_points")
        ),
        "embedded_pawn_field": bool(re.search(r'\["(?:pawn|sPawn)"\]', raw)),
    }


def _verify_maps(content_root: Path) -> None:
    root = content_root.resolve()
    entries = _native_directory_entries(root / "maps")
    registered = [entry[:-4] for entry in entries if "maphelper" not in entry]
    candidates: list[str] = []
    for map_name in registered:
        parsed_name, tags = _map_metadata(root / "maps" / f"{map_name}.map")
        if parsed_name != map_name:
            raise PistonSetupBoundaryError("registered map name differs")
        if "pistons" in tags and ("acid" in tags or "any_sector" in tags):
            candidates.append(map_name)
    expected_names = [spec["name"] for spec in MAP_SPECS]
    if candidates != expected_names:
        raise PistonSetupBoundaryError("Piston RandomMap candidate order differs")

    for spec in MAP_SPECS:
        if registered[spec["map_list_index"]] != spec["name"]:
            raise PistonSetupBoundaryError(
                f"Piston map registration index differs: {spec['name']}"
            )
        path = root / "maps" / f"{spec['name']}.map"
        if path.is_symlink() or not path.is_file():
            raise PistonSetupBoundaryError(f"Piston map is not a regular file: {path}")
        raw_bytes = path.read_bytes()
        if len(raw_bytes) != spec["size"] or hashlib.sha256(raw_bytes).hexdigest() != spec["sha256"]:
            raise PistonSetupBoundaryError(f"Piston map identity differs: {spec['name']}")
        parsed = _parse_map(raw_bytes.decode("utf-8"))
        expected = {
            "dimensions": (8, 8),
            "name": spec["name"],
            "terrain_by_x": spec["terrain_by_x"],
            "zone": spec["zone"],
            "tags": _expected_map_tags(spec),
            "empty_spawn_tables": True,
            "embedded_pawn_field": False,
        }
        if parsed != expected:
            raise PistonSetupBoundaryError(f"Piston map semantics differ: {spec['name']}")
        if len(set(spec["zone"])) != len(spec["zone"]) or any(
            not _valid(tuple(point)) for point in spec["zone"]
        ):
            raise PistonSetupBoundaryError(f"Piston zone validity differs: {spec['name']}")


def _verify_rng_catalog(
    data: bytes,
    image: Any,
    catalog: Mapping[str, Any],
) -> None:
    identity = catalog.get("identity")
    summary = catalog.get("summary")
    core = catalog.get("rng_core")
    callers = catalog.get("callers")
    if (
        not isinstance(identity, Mapping)
        or identity.get("executable_sha256") != EXPECTED_EXECUTABLE_SHA256
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or not isinstance(summary, Mapping)
        or summary.get("raw_call_candidate_count") != EXPECTED_RNG_CALL_COUNT
        or not isinstance(core, Mapping)
        or core.get("entry_rva") != f"0x{RNG_CORE_RVA:08x}"
        or not isinstance(callers, list)
    ):
        raise PistonSetupBoundaryError("RNG caller catalog identity differs")
    scanned = _scan_rng_calls(data, image, RNG_CORE_RVA)
    catalog_pairs = [
        (int(item["call_rva"], 16), item["section"])
        for item in callers
        if isinstance(item, Mapping)
    ]
    if scanned != catalog_pairs or len(scanned) != EXPECTED_RNG_CALL_COUNT:
        raise PistonSetupBoundaryError("RNG caller catalog no longer reproduces")
    by_rva = {int(item["call_rva"], 16): item for item in callers}
    expected_ids = {
        0x000E0C2D: 21,
        0x00172E16: 59,
        0x00172E70: 60,
        0x0022B78A: 108,
        0x00242D9E: 116,
        0x00242DB1: 117,
    }
    if any(by_rva[rva].get("caller_id") != caller_id for rva, caller_id in expected_ids.items()):
        raise PistonSetupBoundaryError("reviewed RNG caller IDs differ")
    for region_id, start, end, _digest, _basis in REGION_SPECS:
        actual = tuple(rva for rva, _section in scanned if start <= rva < end)
        expected = EXPECTED_REGION_RNG_CALLS.get(region_id, ())
        if actual != expected:
            raise PistonSetupBoundaryError(
                f"direct RNG calls differ in region: {region_id}"
            )


def _verify_native_boundaries(executable: Path, catalog: Mapping[str, Any]) -> None:
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise PistonSetupBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise PistonSetupBoundaryError("executable identity differs")

    ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        try:
            body = _region_bytes(image, data, start, end - start, ".text", region_id)
        except Exception as exc:
            raise PistonSetupBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise PistonSetupBoundaryError(f"region bytes differ: {region_id}")
        ranges[region_id] = (start, end)

    decode_ranges: dict[str, tuple[int, int]] = {}
    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"control window differs: {window_id}")
        region_start, region_end = ranges[region_id]
        if not region_start <= start < start + len(encoded) <= region_end:
            raise PistonSetupBoundaryError(f"control window escapes region: {window_id}")
        decode_ranges[f"window_{window_id}"] = (start, start + len(encoded))

    for edge_id, source_region, source, expected_hex, target_region, target, _meaning in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, source, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"direct edge differs: {edge_id}")
        if _direct_target(source, encoded) != target:
            raise PistonSetupBoundaryError(f"direct edge target differs: {edge_id}")
        source_start, source_end = ranges[source_region]
        target_start, target_end = ranges[target_region]
        if not source_start <= source < source + 5 <= source_end:
            raise PistonSetupBoundaryError(f"direct edge escapes source: {edge_id}")
        if not target_start <= target < target_end:
            raise PistonSetupBoundaryError(f"direct edge escapes target: {edge_id}")
        decode_ranges[f"edge_{edge_id}"] = (source, source + 5)

    for binding_id, start, expected_hex, target_va, adjustment, call_rva, helper_region, helper_target in BINDING_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"binding window differs: {binding_id}")
        if struct.pack("<I", target_va) not in encoded or (
            adjustment is not None and struct.pack("<I", adjustment) not in encoded
        ):
            raise PistonSetupBoundaryError(f"binding target differs: {binding_id}")
        call_bytes = _bytes_at(image, data, call_rva, 5)
        if _direct_target(call_rva, call_bytes) != helper_target:
            raise PistonSetupBoundaryError(f"binding helper target differs: {binding_id}")
        helper_start, helper_end = ranges[helper_region]
        if not helper_start <= helper_target < helper_end:
            raise PistonSetupBoundaryError(f"binding helper escapes region: {binding_id}")
        decode_ranges[f"binding_{binding_id}"] = (start, start + len(encoded))

    for pointer_id, data_rva, section_name, expected_hex, target_region, target_rva, _meaning in DATA_POINTER_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, data_rva, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"data pointer differs: {pointer_id}")
        section = next(
            (
                item for item in image.sections
                if item.virtual_address <= data_rva < item.virtual_address + item.raw_size
            ),
            None,
        )
        if section is None or section.name != section_name or section.executable:
            raise PistonSetupBoundaryError(f"data pointer section differs: {pointer_id}")
        (target_va,) = struct.unpack("<I", encoded)
        if target_va != image.image_base + target_rva:
            raise PistonSetupBoundaryError(f"data pointer target differs: {pointer_id}")
        target_start, target_end = ranges[target_region]
        if not target_start <= target_rva < target_end:
            raise PistonSetupBoundaryError(f"data pointer target escapes region: {pointer_id}")

    for anchor_id, data_rva, expected_hex, _point in VECTOR_ANCHOR_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, data_rva, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"vector anchor differs: {anchor_id}")
    for anchor_id, rva, expected_hex, _value in SCALAR_ANCHOR_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, rva, len(encoded)) != encoded:
            raise PistonSetupBoundaryError(f"scalar anchor differs: {anchor_id}")
        decode_ranges[f"scalar_{anchor_id}"] = (rva, rva + len(encoded))
    for anchor_id, string_rva, reference_rva, reference_hex in STRING_ANCHOR_SPECS:
        string_bytes = (anchor_id + "\0").encode("ascii")
        reference_bytes = bytes.fromhex(reference_hex)
        if _bytes_at(image, data, string_rva, len(string_bytes)) != string_bytes:
            raise PistonSetupBoundaryError(f"string anchor differs: {anchor_id}")
        if (
            _bytes_at(image, data, reference_rva, len(reference_bytes)) != reference_bytes
            or struct.pack("<I", image.image_base + string_rva) not in reference_bytes
        ):
            raise PistonSetupBoundaryError(f"string reference differs: {anchor_id}")
        decode_ranges[f"string_{anchor_id}"] = (
            reference_rva,
            reference_rva + len(reference_bytes),
        )

    try:
        decoded = _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise PistonSetupBoundaryError(f"instruction alignment differs: {exc}") from exc
    for name, (start, end) in decode_ranges.items():
        cursor = start
        while cursor < end:
            instruction = decoded[name].get(cursor)
            if instruction is None:
                raise PistonSetupBoundaryError(f"undecoded instruction in {name}")
            cursor += len(instruction[1])
        if cursor != end:
            raise PistonSetupBoundaryError(f"reviewed range ends inside instruction: {name}")

    _verify_rng_catalog(data, image, catalog)


def build_piston_setup_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact installation/build Piston setup boundary."""
    catalog = _verify_dependencies(executable, content_root)
    _verify_sources(content_root)
    _verify_maps(content_root)
    _verify_native_boundaries(executable, catalog)
    return _expected_shape()


def validate_piston_setup_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise PistonSetupBoundaryError("Piston setup boundary map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "candidate_order_proven": True,
        "zone_order_proven": True,
        "rejected_draw_count_proven": True,
        "constructor_draw_proven": True,
        "parameterized_replay_complete": True,
        "concrete_forecast_proven": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_piston_setup_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and reject dependency, source, map, byte, or prose drift."""
    expected = build_piston_setup_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise PistonSetupBoundaryError(
            "Piston setup boundary map differs from exact-build analysis"
        )
    result = validate_piston_setup_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_piston_setup_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
