"""Reproduce and replay the exact native enemy-spawn candidate boundary.

The pinned Windows selector obtains an ordered enemy zone, filters it stably,
optionally retries that same zone in a turn-zero forest-clearing mode, and only
then constructs an emergency pool from the greatest valid x row.  This module
binds those rules to exact executable bytes and exposes an input-driven replay.

The replay never guesses Board:IsDangerous, BlockSpawn, occupancy, or future
RNG state.  Callers must provide the tile facts (or an equivalent predicate)
for the candidate-time Board snapshot; the existing native RNG helper can then
select from the resulting ordered pool when an exact pre-call state is known.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_spawn_candidate_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000

TEAM_PLAYER = 1
TEAM_ENEMY = 6
PATH_GROUND = 0
TURN_ZERO_FOREST_RETRY_MODE = 9
TERRAIN_ROAD = 0
TERRAIN_WATER = 3
TERRAIN_NATIVE_REJECT_5 = 5
TERRAIN_FOREST = 6
BLOCKED_NONE = 0
BLOCKED_TEMP = 1
BLOCKED_PERM = 2

POOL_ORDINARY_PRIMARY = "ordinary_primary"
POOL_ORDINARY_TURN_ZERO_FOREST_RETRY = "ordinary_turn_zero_forest_retry"
POOL_EMERGENCY_MAX_X_ROW = "emergency_max_x_row"
POOL_FAILURE = "failure"

Point = tuple[int, int]
ValidityPredicate = Callable[[Point, int], bool]


class EnemySpawnCandidateBoundaryError(RuntimeError):
    """Raised when the exact candidate boundary cannot reproduce."""


@dataclass(frozen=True)
class EnemySpawnTileFacts:
    """Explicit candidate-time inputs to the ordinary enemy predicate."""

    has_item: bool = False
    active_pod: bool = False
    block_spawn: int = BLOCKED_NONE
    dangerous: bool = False
    blocked_for_ground: bool = False
    terrain: int = TERRAIN_ROAD
    acid: bool = False
    existing_spawn_marker: bool = False


DEPENDENCY_SPECS = (
    {
        "id": "spawn_coordinate_paths",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_spawn_coordinate_paths.json"
        ),
        "file_sha256": (
            "ccc3064a6f1e14e740b1fc5cf2e3f6712dc95c1e8c92a979079b55431f55c32e"
        ),
        "canonical_sha256": (
            "6a5ee719660542979f0e827acd917e43640a018ec6101960e79bafb9a51ce5ed"
        ),
        "analysis_kind": "native_spawn_coordinate_path_map",
        "role": (
            "Pins the ordinary caller-60 and emergency caller-59 modulo "
            "selectors around the candidate construction mapped here."
        ),
    },
    {
        "id": "path_boundaries",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_path_boundaries.json"
        ),
        "file_sha256": (
            "098cbbc5a9dc4c99a07b5f85eac7aaa19812bf093249d1d3f6e6c5ec49277486"
        ),
        "canonical_sha256": (
            "99c8c30fa2e213039e6ba07f5f5062d6487aaa6286eee9cc9cb0cf6aaed23afc"
        ),
        "analysis_kind": "native_path_boundary_map",
        "role": (
            "Pins Pawn:GetPathProf, Board:IsBlocked, PATH_GROUND=0, and the "
            "Board path-manager vtable used by the enemy validity branch."
        ),
    },
    {
        "id": "final_cave_block_spawn_lifetime",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "final_cave_block_spawn_lifetime.json"
        ),
        "file_sha256": (
            "f596b594b3cf8ef160c0a7af84229fc4e1ad12278d41a4703daa13362fd0b3db"
        ),
        "canonical_sha256": (
            "69d63632fe6585ac02864e09e3106e796e47abadd65991e41e1b76a1e2370889"
        ),
        "analysis_kind": "final_cave_block_spawn_lifetime_boundary_map",
        "role": (
            "Pins BLOCKED_NONE/TEMP/PERM values 0/1/2 and the Point-keyed "
            "Board BlockSpawn map consulted by spawn validity."
        ),
    },
    {
        "id": "piston_setup_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_piston_setup_boundary.json"
        ),
        "file_sha256": (
            "dfd1ab705beee79f06a609865930f918b937745c22393f516c5f84720a69b230"
        ),
        "canonical_sha256": (
            "0368d923cef97c4bb500c287a355ae43b24c0d59bf81529731f2956a8fd7717f"
        ),
        "analysis_kind": "native_piston_setup_boundary_map",
        "role": (
            "Pins original Lua Point-list encounter order through GetZone and "
            "extract_table without a sorting step."
        ),
    },
    {
        "id": "enemy_position_observations",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_position_observations_boundary.json"
        ),
        "file_sha256": (
            "c6d168464c067c92f7366a0acf4a12561f2949af4f5491593d0f900519b56479"
        ),
        "canonical_sha256": (
            "b994f0a9fe464d885d7675819666be93e94bb8cef0a9939fba93d6a01b57af0b"
        ),
        "analysis_kind": "native_enemy_position_observations_boundary",
        "role": (
            "Pins Board:IsDangerous and active-pod semantics and records that "
            "exact dangerous state is not currently exported by the bridge."
        ),
    },
    {
        "id": "spawn_coordinate_state_replay",
        "path": (
            "data/observatory/captures/"
            "windows_build_13725832_owner_local_modified_20260822_"
            "spawn_coordinate_state_replay_receipt.json"
        ),
        "file_sha256": (
            "5ba273dc10faf62fa15010a5f1f269c7161613a6e0b4cf45965803178787dd31"
        ),
        "analysis_kind": "observatory_spawn_coordinate_state_replay_receipt",
        "role": (
            "Supplies a post-hoc exact pre-state and ordered five-point pool "
            "used only to join candidate replay to the existing RNG replay."
        ),
    },
)


REGION_SPECS = (
    {
        "id": "spawn_coordinate_selector",
        "start": 0x00172A90,
        "end": 0x00172EF6,
        "sha256": "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904",
        "basis": "Complete reviewed selector through RET.",
    },
    {
        "id": "spawn_validity",
        "start": 0x00172F00,
        "end": 0x001732C2,
        "sha256": "ece436016741d70821025fcc00b3e30965480a2b99a00960449e9262592956bb",
        "basis": "Complete reviewed spawn-validity predicate through RET.",
    },
    {
        "id": "named_zone_lookup",
        "start": 0x0016DF30,
        "end": 0x0016E12B,
        "sha256": "91f988fdcbeb90b07539b86903785687bcfd1864cdb0d72c5bc958319d02bfb3",
        "basis": "Complete reviewed named-zone lookup and enemy fallback through RET.",
    },
    {
        "id": "board_get_turn",
        "start": 0x0016CEC0,
        "end": 0x0016CEC7,
        "sha256": "277d038f2fa1c59d6c30ba494117b8c29d60a753a5059ce4ffdb9b9b7416093a",
        "basis": "Complete field reader through RET.",
    },
    {
        "id": "board_get_turn_registration",
        "start": 0x0027A581,
        "end": 0x0027A5A6,
        "sha256": "515efa4cbbce35df3cbe8ed1e1003346a85a5bc6c4ee3c1c568d67a7258ed4bd",
        "basis": "Instruction-aligned Luabind registration of Board:GetTurn.",
    },
    {
        "id": "pawn_get_path_prof",
        "start": 0x00232F90,
        "end": 0x002330CA,
        "sha256": "3cc91e8ef2be9950114b088f141a4087057bf7eee702aade83be716e1bccfa40",
        "basis": "Complete Pawn:GetPathProf member through RET.",
    },
    {
        "id": "board_is_pod",
        "start": 0x00172580,
        "end": 0x001725EA,
        "sha256": "04c19003a85b5a2687be2b27597d6fb7518cb79580a06e720eb64c7f8ed6ea03",
        "basis": "Complete Board:IsPod member through RET 0x08.",
    },
    {
        "id": "board_is_dangerous",
        "start": 0x001726A0,
        "end": 0x0017276E,
        "sha256": "c6e15d03f65fc709b28c8b15bf60cf5a7870700343d7b5be38ce7c3791d7f3f8",
        "basis": "Complete Board:IsDangerous member through RET 0x08.",
    },
    {
        "id": "set_terrain_core",
        "start": 0x00165F20,
        "end": 0x00165F6D,
        "sha256": "d77ae2e0dda86ba7f2de1c14f19e5aee25932ba99853c0802883aa4098ab857b",
        "basis": "Complete reviewed terrain setter core through RET 0x0c.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "enemy_source_dispatch",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172AD2,
        "hex": "8b450c8bc8c745fc000000006a018bb8b0000000897ddce872ad0c0084c0740f6a008d45bc8bcb50e821e0feffeb1a83ec188bcc68a0e98200e80053e9ff8d45bc8bcb50e815b4ffff508d4db0e88cdbf6ff",
        "meaning": "TEAM_PLAYER uses the deployment source; every other team requests the named enemy zone.",
    },
    {
        "id": "primary_stable_filter",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172B4F,
        "hex": "8b75cc8bc68b4dc82bc1c1f803c745e00000000085c074698bf98d59080f1f4000ff77048b4d0cff37e813040c008b4df050ff75dce87703000084c075218bc62bc3505357e8e7b91f008b4de083ee0883c40c8975cc4983ef0883eb08eb038b4de08bc6412b45c883c708c1f80383c308894de03bc872a9",
        "meaning": "Forward iteration erases invalid points by shifting the tail left, preserving source order.",
    },
    {
        "id": "turn_zero_mode9_retry_gate",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172BD0,
        "hex": "3bce0f94c084c00f849c00000083bba82c0000000f858f00000083ff010f84860000008d45b0508d4dc8e8b12ff5ff",
        "meaning": "An empty primary pool retries only at Board turn zero and only for a non-player pawn.",
    },
    {
        "id": "mode9_stable_filter",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172BFF,
        "hex": "8b75cc8bc68b4dc82bc1c1f803c745e00000000085c074628bf98d59080f1f4000ff77048b4d0cff37e863030c008b4df0506a09e8c802000084c075218bc62bc3505357e838b91f008b4de083ee0883c40c8975cc4983ef0883eb08eb038b4de08bc6412b45c883c708c1f80383c308894de03bc872aa8b4dc8",
        "meaning": "The retry recopies the original source and stably filters with literal validity mode 9.",
    },
    {
        "id": "emergency_grid_count",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172CA5,
        "hex": "8b45f0c645fc02895dec8b48542b4850b8abaaaa2af7e9d1fa8bc2c1e81f03c20f847901000033c9894de08b45f0c745e8000000008b405003c18b48042b08b8a903a85df7e9c1fa0c8bc2c1e81f03c20f84de0000000f1f440000",
        "meaning": "Emergency construction obtains actual Board width and height and initializes x-major/y-minor iteration.",
    },
    {
        "id": "emergency_mode6_validity",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172D00,
        "hex": "ff75e88b4d0cff75ece882020c008b4df050ff75dce8e601000084c00f8486000000",
        "meaning": "Every emergency point uses the pawn path profile and original enemy mode 6, never retry mode 9.",
    },
    {
        "id": "emergency_keep_max_x",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172D22,
        "hex": "8b45ec3bfe740839070f4cf78975c08b4de88d55d48945d4894dd83bd673383bfa77348bda2bdfc1fb033b75e475166a018d4dbce8f52bf4ff8b45c48b75c08b7dbc8945e485f674378b04df89068b44df04894604eb293bf3751c6a018d4dbce8c92bf4ff8b45c48b75c08b7dbc8b4de88945e48b45ec85f674058906894e04",
        "meaning": "A valid point on a greater x clears earlier rows; equal-x points append in ascending y order.",
    },
    {
        "id": "emergency_iteration",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172DA8,
        "hex": "8b45f08b5de843895de88b40500345e08b48042b08b8a903a85df7e9c1fa0c8bc2c1e81f03c23bd88b5de40f8227ffffff8b45f08345e00cff45ec8b48542b4850b8abaaaa2af7e98b4de0d1fa8bc2c1e81f03c23945ec0f82cbfeffff",
        "meaning": "The inner y loop completes before x advances, fixing emergency order to x-major then y-minor.",
    },
    {
        "id": "forest_clear_after_selection",
        "region_id": "spawn_coordinate_selector",
        "start": 0x00172E7B,
        "hex": "8b5cd1048b3cd18b75f08bce5357e8b2bcfeff83b8e02a000006750b6a0053578bcee87e30ffff8b7508893e895e04",
        "meaning": "A selected ordinary terrain-6 point is changed to terrain 0 before the coordinate is returned.",
    },
    {
        "id": "validity_common_rejections",
        "region_id": "spawn_validity",
        "start": 0x00172F28,
        "hex": "8bf9ff75148b5d08be06000000ff751083fb090f45f3e82deefeff83b8042b0000000f855c030000ff75148bcfff7510e813eefeff83b8e42a0000010f84420300008d4d10518d4dec518d8f58740000e8c3f1f5ff8b45ec837818020f84220300008d4510508d45ec508d8f58740000e8a3f1f5ff8b45ec837818010f8402030000ff75148bcfff7510e8e9f6ffff84c00f85ed020000",
        "meaning": "Every mode rejects an item, active pod state, permanent or temporary BlockSpawn, and Board:IsDangerous.",
    },
    {
        "id": "validity_existing_spawn_absence",
        "region_id": "spawn_validity",
        "start": 0x0017304C,
        "hex": "8d4d0c8bb7542d00008d551056ffb7502d0000e8bce6f5ff83c40839307519b8010000008b4df464890d00000000595f5e5b8be55dc21000",
        "meaning": "Validity succeeds only when the point is absent from the Board +0x2d50/+0x2d54 spawn-marker vector.",
    },
    {
        "id": "validity_enemy_ground_terrain",
        "region_id": "spawn_validity",
        "start": 0x0017309A,
        "hex": "6a00ff7514ff7510ffd084c075dcff75148bcfff7510e88bbafeff83b8e02a00000574c6ff75148bcfff7510e875bafeff83b8e02a000006750583fb0975abff75148bcfff7510e85abafeff83b8e02a0000037495ff75148bcfff7510e874ecfeff80b8f12a0000000f857bffffffff75148bcfff7510e85aecfeff80b8f02a0000000f8561ffffff",
        "meaning": "Enemy validity calls Board:IsBlocked with PATH_GROUND=0, rejects terrain 5, rejects forest except in original mode 9, and rejects water, acid, and the native danger byte.",
    },
    {
        "id": "zone_absent_enemy_fallback",
        "region_id": "named_zone_lookup",
        "start": 0x0016DFF6,
        "hex": "33db33ff33f6895ddc897de08975e468a0e982008d4d0cc645fc01e86a06f0ff85c00f85d40000008b4dd88d55c4528b01ff50048b4dd88d55c4528b0083e8038945ec8b01ff50048b55ec3b100f8da90000000f1f8000000000b9020000008955cc894de80f1f4400008d45cc894dd03bc773383bd877348bf02bf3c1fe033b7de475166a018d4ddce8cc78f4ff8b7de08b5ddc8b4de88b55ec85ff74318b04f389078b44f304894704eb233bfe75166a018d4ddce8a078f4ff8b7de08b5ddc8b4de88b55ec85ff74058917894f048b75e44183c708894de8897de083f9067c898b4dd8428955ec8d55c4528b01ff50048b55ec3b100f8c5effffff",
        "meaning": "When the enemy zone is absent, fallback points are x=width-3..width-1 and y=2..5 in x-major order.",
    },
    {
        "id": "active_pod_test",
        "region_id": "board_is_pod",
        "start": 0x00172580,
        "hex": "558bec83e4f85153568bf1578b86702d00003b450875488b86742d00003b450c753d8bbe702d00008bd88b0653578b4008ffd084c074118b46508d0c7f69f3bc2b0000033488eb0383c65c83bee42a000001750bb0015f5e5b8be55dc208005f5e32c05b8be55dc20800",
        "meaning": "Board:IsPod uses tile pod state 1 for the active pod coordinate; spawn validity directly rejects that same state value.",
    },
    {
        "id": "get_turn_field_reader",
        "region_id": "board_get_turn",
        "start": 0x0016CEC0,
        "hex": "8b81a82c0000c3",
        "meaning": "The registered Board:GetTurn reader returns Board +0x2ca8, the field tested by the retry gate.",
    },
)


DIRECT_EDGE_SPECS = (
    ("selector_to_is_team", "spawn_coordinate_selector", 0x00172AE9, "e872ad0c00", "pawn_is_team", 0x0023D860),
    ("selector_to_named_zone", "spawn_coordinate_selector", 0x00172B16, "e815b4ffff", "named_zone_lookup", 0x0016DF30),
    ("primary_to_get_path_prof", "spawn_coordinate_selector", 0x00172B78, "e813040c00", "pawn_get_path_prof", 0x00232F90),
    ("primary_to_validity", "spawn_coordinate_selector", 0x00172B84, "e877030000", "spawn_validity", 0x00172F00),
    ("mode9_to_get_path_prof", "spawn_coordinate_selector", 0x00172C28, "e863030c00", "pawn_get_path_prof", 0x00232F90),
    ("mode9_to_validity", "spawn_coordinate_selector", 0x00172C33, "e8c8020000", "spawn_validity", 0x00172F00),
    ("emergency_to_get_path_prof", "spawn_coordinate_selector", 0x00172D09, "e882020c00", "pawn_get_path_prof", 0x00232F90),
    ("emergency_to_validity", "spawn_coordinate_selector", 0x00172D15, "e8e6010000", "spawn_validity", 0x00172F00),
    ("selected_to_tile", "spawn_coordinate_selector", 0x00172E89, "e8b2bcfeff", "board_tile_lookup", 0x0015EB40),
    ("selected_to_set_terrain", "spawn_coordinate_selector", 0x00172E9D, "e87e30ffff", "set_terrain_core", 0x00165F20),
    ("validity_item_tile", "spawn_validity", 0x00172F3E, "e82deefeff", "board_tile_lookup_2", 0x00161D70),
    ("validity_pod_tile", "spawn_validity", 0x00172F58, "e813eefeff", "board_tile_lookup_2", 0x00161D70),
    ("validity_perm_block", "spawn_validity", 0x00172F78, "e8c3f1f5ff", "block_spawn_map_accessor", 0x000D2140),
    ("validity_temp_block", "spawn_validity", 0x00172F98, "e8a3f1f5ff", "block_spawn_map_accessor", 0x000D2140),
    ("validity_to_is_dangerous", "spawn_validity", 0x00172FB2, "e8e9f6ffff", "board_is_dangerous", 0x001726A0),
    ("validity_to_spawn_membership", "spawn_validity", 0x0017305F, "e8bce6f5ff", "point_vector_membership", 0x000D1720),
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


def _coerce_point(raw: Sequence[int], label: str) -> Point:
    if isinstance(raw, (str, bytes)):
        raise EnemySpawnCandidateBoundaryError(f"{label} must be an integer Point")
    try:
        valid = (
            len(raw) == 2
            and type(raw[0]) is int
            and type(raw[1]) is int
        )
    except (TypeError, IndexError):
        valid = False
    if not valid:
        raise EnemySpawnCandidateBoundaryError(f"{label} must be an integer Point")
    return int(raw[0]), int(raw[1])


def _validate_dimensions(width: int, height: int) -> None:
    if type(width) is not int or type(height) is not int:
        raise EnemySpawnCandidateBoundaryError("board dimensions must be integers")
    if not 1 <= width <= 255 or not 1 <= height <= 255:
        raise EnemySpawnCandidateBoundaryError("board dimensions must be in 1..255")


def default_enemy_spawn_zone(width: int = 8, height: int = 8) -> tuple[Point, ...]:
    """Return the exact absent-``enemy``-zone fallback order.

    The native loop does not use height while constructing y=2..5.  Requiring
    at least those rows keeps this replay inside the normal Board contract.
    """
    _validate_dimensions(width, height)
    if width < 3 or height < 6:
        raise EnemySpawnCandidateBoundaryError(
            "enemy-zone fallback requires width >= 3 and height >= 6"
        )
    return tuple((x, y) for x in range(width - 3, width) for y in range(2, 6))


def enemy_spawn_tile_is_valid(mode: int, facts: EnemySpawnTileFacts) -> bool:
    """Replay the ordinary enemy validity branch from explicit tile facts."""
    if mode not in (TEAM_ENEMY, TURN_ZERO_FOREST_RETRY_MODE):
        raise EnemySpawnCandidateBoundaryError("enemy validity mode must be 6 or 9")
    if type(facts.block_spawn) is not int:
        raise EnemySpawnCandidateBoundaryError("BlockSpawn value must be an integer")
    if (
        facts.has_item
        or facts.active_pod
        or facts.block_spawn in (BLOCKED_TEMP, BLOCKED_PERM)
        or facts.dangerous
        or facts.blocked_for_ground
        or facts.terrain in (TERRAIN_NATIVE_REJECT_5, TERRAIN_WATER)
        or (facts.terrain == TERRAIN_FOREST and mode != TURN_ZERO_FOREST_RETRY_MODE)
        or facts.acid
        or facts.existing_spawn_marker
    ):
        return False
    return True


def selected_terrain_after_spawn(pool_kind: str, terrain: int) -> int:
    """Replay the selector's terrain-6 cleanup for the retry result."""
    if pool_kind not in {
        POOL_ORDINARY_PRIMARY,
        POOL_ORDINARY_TURN_ZERO_FOREST_RETRY,
        POOL_EMERGENCY_MAX_X_ROW,
    }:
        raise EnemySpawnCandidateBoundaryError("unknown spawn pool kind")
    if (
        pool_kind == POOL_ORDINARY_TURN_ZERO_FOREST_RETRY
        and terrain == TERRAIN_FOREST
    ):
        return TERRAIN_ROAD
    return terrain


def replay_enemy_spawn_candidate_pool(
    source_points: Sequence[Sequence[int]],
    board_width: int,
    board_height: int,
    turn: int,
    is_valid: ValidityPredicate,
) -> dict[str, Any]:
    """Construct the exact ordered pool without consuming an RNG draw."""
    _validate_dimensions(board_width, board_height)
    if type(turn) is not int or turn < 0:
        raise EnemySpawnCandidateBoundaryError("turn must be a nonnegative integer")
    if not callable(is_valid):
        raise EnemySpawnCandidateBoundaryError("is_valid must be callable")
    source = tuple(
        _coerce_point(point, f"source point {index}")
        for index, point in enumerate(source_points)
    )
    if len(set(source)) != len(source):
        raise EnemySpawnCandidateBoundaryError("source points must be unique")

    primary = tuple(point for point in source if is_valid(point, TEAM_ENEMY))
    if primary:
        kind = POOL_ORDINARY_PRIMARY
        mode = TEAM_ENEMY
        candidates = primary
        caller = 60
    else:
        retry = ()
        if turn == 0:
            retry = tuple(
                point
                for point in source
                if is_valid(point, TURN_ZERO_FOREST_RETRY_MODE)
            )
        if retry:
            kind = POOL_ORDINARY_TURN_ZERO_FOREST_RETRY
            mode = TURN_ZERO_FOREST_RETRY_MODE
            candidates = retry
            caller = 60
        else:
            emergency: tuple[Point, ...] = ()
            for x in range(board_width):
                row = tuple(
                    (x, y)
                    for y in range(board_height)
                    if is_valid((x, y), TEAM_ENEMY)
                )
                if row:
                    emergency = row
            if emergency:
                kind = POOL_EMERGENCY_MAX_X_ROW
                mode = TEAM_ENEMY
                candidates = emergency
                caller = 59
            else:
                kind = POOL_FAILURE
                mode = None
                candidates = ()
                caller = None

    return {
        "analysis_kind": "native_enemy_spawn_candidate_replay",
        "build_id": EXPECTED_BUILD_ID,
        "source_points": [[x, y] for x, y in source],
        "board_dimensions": [board_width, board_height],
        "turn": turn,
        "pool_kind": kind,
        "validation_mode": mode,
        "rng_caller_id": caller,
        "candidate_count": len(candidates),
        "candidates": [[x, y] for x, y in candidates],
        "rng_consumed": False,
        "selected_forest_becomes_road": (
            kind == POOL_ORDINARY_TURN_ZERO_FOREST_RETRY
        ),
    }


def replay_enemy_spawn_candidate_pool_from_valid_points(
    source_points: Sequence[Sequence[int]],
    board_width: int,
    board_height: int,
    turn: int,
    valid_points_by_mode: Mapping[int, Collection[Sequence[int]]],
) -> dict[str, Any]:
    """Serializable-fixture wrapper around the predicate-driven replay."""
    normalized: dict[int, set[Point]] = {}
    for mode, points in valid_points_by_mode.items():
        if type(mode) is not int or mode not in (
            TEAM_ENEMY,
            TURN_ZERO_FOREST_RETRY_MODE,
        ):
            raise EnemySpawnCandidateBoundaryError("valid-point mode must be 6 or 9")
        normalized[mode] = {
            _coerce_point(point, f"mode {mode} valid point") for point in points
        }
    return replay_enemy_spawn_candidate_pool(
        source_points,
        board_width,
        board_height,
        turn,
        lambda point, mode: point in normalized.get(mode, set()),
    )


def _dependency_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
            "section": ".text",
            "boundary_basis": spec["basis"],
        }
        for spec in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start']:08x}",
            "size": len(bytes.fromhex(spec["hex"])),
            "instruction_hex": spec["hex"],
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{from_rva:08x}",
            "instruction_hex": instruction_hex,
            "target_id": target_id,
            "target_rva": f"0x{target_rva:08x}",
            "evidence_class": "fact",
        }
        for (
            edge_id,
            source_region,
            from_rva,
            instruction_hex,
            target_id,
            target_rva,
        ) in DIRECT_EDGE_SPECS
    ]


def _replay_vectors() -> list[dict[str, Any]]:
    vectors = [
        {
            "id": "stable_primary_filter",
            "source_points": [[5, 2], [5, 3], [5, 4], [6, 2], [6, 5]],
            "board_dimensions": [8, 8],
            "turn": 1,
            "valid_points": [
                {"mode": 6, "points": [[5, 4], [6, 2]]},
                {"mode": 9, "points": []},
            ],
        },
        {
            "id": "turn_zero_mode9_retry",
            "source_points": [[5, 2], [5, 3], [5, 4], [6, 2], [6, 5]],
            "board_dimensions": [8, 8],
            "turn": 0,
            "valid_points": [
                {"mode": 6, "points": []},
                {"mode": 9, "points": [[5, 3], [6, 5]]},
            ],
        },
        {
            "id": "later_turn_skips_mode9_and_keeps_emergency_max_x",
            "source_points": [[5, 2], [5, 3]],
            "board_dimensions": [8, 8],
            "turn": 1,
            "valid_points": [
                {"mode": 6, "points": [[3, 7], [6, 5], [7, 1], [7, 3]]},
                {"mode": 9, "points": [[5, 2], [5, 3]]},
            ],
        },
        {
            "id": "turn_zero_retry_empty_then_emergency",
            "source_points": [[5, 2], [5, 3]],
            "board_dimensions": [8, 8],
            "turn": 0,
            "valid_points": [
                {"mode": 6, "points": [[4, 6], [6, 2], [6, 7]]},
                {"mode": 9, "points": []},
            ],
        },
        {
            "id": "complete_failure",
            "source_points": [[5, 2]],
            "board_dimensions": [8, 8],
            "turn": 0,
            "valid_points": [
                {"mode": 6, "points": []},
                {"mode": 9, "points": []},
            ],
        },
    ]
    for vector in vectors:
        by_mode = {
            item["mode"]: item["points"] for item in vector["valid_points"]
        }
        vector["expected"] = replay_enemy_spawn_candidate_pool_from_valid_points(
            vector["source_points"],
            vector["board_dimensions"][0],
            vector["board_dimensions"][1],
            vector["turn"],
            by_mode,
        )
    return vectors


def _contracts() -> dict[str, Any]:
    return {
        "enemy_source": {
            "team": TEAM_ENEMY,
            "named_zone": "enemy",
            "zone_order": "original Lua encounter order, first occurrence unique",
            "absent_zone_fallback_formula": (
                "for x in width-3..width-1, for y in 2..5, append Point(x,y)"
            ),
            "fallback_8x8": [list(point) for point in default_enemy_spawn_zone()],
        },
        "primary_filter": {
            "validation_mode": TEAM_ENEMY,
            "path_profile_source": "Pawn:GetPathProf",
            "erase_semantics": "stable; surviving source order is preserved",
        },
        "turn_zero_retry": {
            "requires_primary_empty": True,
            "requires_board_turn": 0,
            "excluded_team": TEAM_PLAYER,
            "validation_mode": TURN_ZERO_FOREST_RETRY_MODE,
            "validation_mode_is_path_profile": False,
            "source_is_original_zone_copy": True,
            "selected_terrain_6_becomes": TERRAIN_ROAD,
        },
        "emergency": {
            "requires_ordinary_empty": True,
            "iteration_order": "x-major then y-minor over the actual Board",
            "validation_mode": TEAM_ENEMY,
            "retention": "only valid points on the greatest x with any valid point",
            "same_row_order": "ascending y",
            "selector_rng_caller_id": 59,
            "empty_result": [-1, -1],
        },
        "ordinary_selector_rng_caller_id": 60,
        "enemy_validity": {
            "common_rejections": [
                "any item",
                "tile pod state equals 1",
                "BlockSpawn value equals BLOCKED_TEMP=1 or BLOCKED_PERM=2",
                "Board:IsDangerous(point)",
            ],
            "enemy_rejections": [
                "Board:IsBlocked(point, PATH_GROUND=0)",
                "terrain literal 5",
                "terrain 6 unless original validity mode is 9",
                "TERRAIN_WATER=3",
                "acid tile byte",
                "native dangerous tile byte",
                "membership in Board Point vector +0x2d50/+0x2d54",
            ],
            "not_separate_rejections": ["smoke", "fire", "frozen", "targeted"],
            "existing_marker_test": (
                "direct Point-vector membership, not the tile-byte half of Board:IsSpawning"
            ),
        },
    }


def _expected_shape() -> dict[str, Any]:
    vectors = _replay_vectors()
    unresolved = [
        {
            "id": "candidate_time_board_is_dangerous",
            "question": "What exact Board:IsDangerous result exists at each future candidate check?",
            "current_carrier": None,
            "next_evidence": "Export the native tile byte and two Point vectors or capture the predicate result at this boundary.",
        },
        {
            "id": "candidate_time_block_spawn_value",
            "question": "What exact Point-keyed BlockSpawn value exists at each future candidate check?",
            "current_carrier": None,
            "next_evidence": "Export the native BlockSpawn map or capture values at this boundary.",
        },
        {
            "id": "future_pre_call_rng_state",
            "question": "What shared CRT state enters a future caller-59 or caller-60 selection?",
            "current_carrier": None,
            "next_evidence": "Use the dormant build-keyed RNG capsule; do not infer the state from save data.",
        },
        {
            "id": "fallback_runtime_reachability",
            "question": "Which unmodified encounters naturally reach the absent-zone or emergency branches?",
            "current_carrier": None,
            "next_evidence": "Capture branch identity during a matched native run if natural reachability matters.",
        },
        {
            "id": "non_windows_or_modified_builds",
            "question": "Do other depots or mods preserve this exact boundary?",
            "current_carrier": None,
            "next_evidence": "Build a separate executable/content-keyed artifact before generalizing.",
        },
    ]
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
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
        },
        "dependencies": _dependency_records(),
        "method": {
            "boundary_review": (
                "Focused Ghidra 12.1.3 decompilation and x86 control-flow review "
                "joined the selector, validity predicate, named-zone fallback, "
                "GetTurn field reader, path profile, danger, pod, and terrain setter."
            ),
            "binary_verification": (
                "Capstone rechecks every region, instruction-aligned control window, "
                "direct E8 target, string anchor, and immutable upstream dependency."
            ),
            "limitations": [
                "Semantic names are conservative inferences over exact machine-code facts.",
                "Static control flow does not prove natural runtime reachability.",
                "The replay requires candidate-time predicate inputs and never reads a stale save as their substitute.",
                "The artifact applies only to the exact owner-observed Windows executable.",
            ],
        },
        "constants": {
            "TEAM_PLAYER": TEAM_PLAYER,
            "TEAM_ENEMY": TEAM_ENEMY,
            "PATH_GROUND": PATH_GROUND,
            "TURN_ZERO_FOREST_RETRY_MODE": TURN_ZERO_FOREST_RETRY_MODE,
            "TERRAIN_ROAD": TERRAIN_ROAD,
            "TERRAIN_WATER": TERRAIN_WATER,
            "TERRAIN_NATIVE_REJECT_5": TERRAIN_NATIVE_REJECT_5,
            "TERRAIN_FOREST": TERRAIN_FOREST,
            "BLOCKED_NONE": BLOCKED_NONE,
            "BLOCKED_TEMP": BLOCKED_TEMP,
            "BLOCKED_PERM": BLOCKED_PERM,
        },
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_call_edges": _direct_edge_records(),
        "method_bindings": [
            {
                "owner": "Board",
                "name": "GetTurn",
                "string_rva": "0x00438814",
                "string_hex": "4765745475726e00",
                "member_store_rva": "0x0027a584",
                "member_store_hex": "c745e8c0ce5600",
                "name_reference_rva": "0x0027a59a",
                "name_reference_hex": "6814888300",
                "native_entry_rva": "0x0016cec0",
                "field_offset": "0x2ca8",
                "evidence_class": "fact",
            }
        ],
        "contracts": _contracts(),
        "replay_vectors": vectors,
        "capture_join": {
            "source_dependency": "spawn_coordinate_state_replay",
            "observable_pre_state": 370_289_084,
            "observable_pre_state_hex": "0x161229bc",
            "raw_rng": 3_642,
            "candidates": [[5, 2], [5, 3], [5, 4], [6, 2], [6, 5]],
            "selected_index": 2,
            "selected": [5, 4],
            "scope": "post-hoc exact replay; not a future-state forecast",
        },
        "unresolved": unresolved,
        "solver_impact": {
            "native_candidate_replay_added": True,
            "production_forecast_enabled": False,
            "simulator_contradiction_found": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "current_simulator_version": 408,
            "reason": (
                "The construction/order algorithm is exact, but future exact "
                "Board:IsDangerous, BlockSpawn, and pre-call RNG state remain inputs."
            ),
        },
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "replay_vector_count": len(vectors),
            "unresolved_count": len(unresolved),
            "enemy_source_order_proven": True,
            "primary_stable_filter_proven": True,
            "turn_zero_mode9_retry_proven": True,
            "emergency_max_x_row_proven": True,
            "enemy_validity_rejections_proven": True,
            "parameterized_replay_complete": True,
            "concrete_forecast_proven": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _read_dependency(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EnemySpawnCandidateBoundaryError(
            f"dependency cannot be read: {path}"
        ) from exc
    if not isinstance(value, Mapping):
        raise EnemySpawnCandidateBoundaryError(f"dependency is not an object: {path}")
    return value


def _verify_dependencies(repository_root: Path) -> None:
    root = repository_root.resolve()
    for spec in DEPENDENCY_SPECS:
        path = root / spec["path"]
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise EnemySpawnCandidateBoundaryError(
                f"dependency is missing or escapes repository root: {spec['id']}"
            ) from exc
        if path.is_symlink() or not resolved.is_file():
            raise EnemySpawnCandidateBoundaryError(
                f"dependency is not a regular non-symlink file: {spec['id']}"
            )
        raw = resolved.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemySpawnCandidateBoundaryError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_dependency(resolved)
        if value.get("analysis_kind", value.get("kind")) != spec["analysis_kind"]:
            raise EnemySpawnCandidateBoundaryError(
                f"dependency analysis kind differs: {spec['id']}"
            )
        if "canonical_sha256" in spec and _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemySpawnCandidateBoundaryError(
                f"dependency fields differ: {spec['id']}"
            )


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemySpawnCandidateBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    section = next(
        (
            item
            for item in image.sections
            if item.virtual_address <= rva
            and rva + size <= item.virtual_address + item.raw_size
        ),
        None,
    )
    if section is None or not section.executable:
        raise EnemySpawnCandidateBoundaryError(f"RVA 0x{rva:08x} is not executable")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise EnemySpawnCandidateBoundaryError("reviewed edge is not CALL rel32")
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def build_enemy_spawn_candidate_boundary_map(
    executable: Path,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Reproduce the exact-build candidate boundary map."""
    if repository_root is None:
        repository_root = Path(__file__).resolve().parents[2]
    _verify_dependencies(repository_root)
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise EnemySpawnCandidateBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise EnemySpawnCandidateBoundaryError("executable identity differs")

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image, data, spec["start"], size, ".text", spec["id"]
            )
        except Exception as exc:
            raise EnemySpawnCandidateBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise EnemySpawnCandidateBoundaryError(f"region {spec['id']} differs")
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise EnemySpawnCandidateBoundaryError(str(exc)) from exc

    regions = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        start = spec["start"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise EnemySpawnCandidateBoundaryError(
                f"control window {spec['id']} differs"
            )
        region = regions[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise EnemySpawnCandidateBoundaryError(
                f"control window {spec['id']} escapes its region"
            )
        cursor = start
        while cursor < start + len(encoded):
            instruction = decoded[spec["region_id"]].get(cursor)
            if instruction is None:
                raise EnemySpawnCandidateBoundaryError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise EnemySpawnCandidateBoundaryError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for (
        edge_id,
        source_region,
        from_rva,
        instruction_hex,
        _target_id,
        target_rva,
    ) in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(instruction_hex)
        instruction = decoded[source_region].get(from_rva)
        if instruction is None or instruction[1] != expected:
            raise EnemySpawnCandidateBoundaryError(f"direct edge {edge_id} differs")
        if _direct_target(from_rva, expected) != target_rva:
            raise EnemySpawnCandidateBoundaryError(
                f"direct edge {edge_id} target differs"
            )

    get_turn_string = b"GetTurn\0"
    string_rva = 0x00438814
    offset = image.rva_span_to_file_offset(string_rva, len(get_turn_string))
    if offset is None or data[offset : offset + len(get_turn_string)] != get_turn_string:
        raise EnemySpawnCandidateBoundaryError("Board:GetTurn string differs")
    for rva, encoded_hex in (
        (0x0027A584, "c745e8c0ce5600"),
        (0x0027A59A, "6814888300"),
    ):
        encoded = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, rva, len(encoded)) != encoded:
            raise EnemySpawnCandidateBoundaryError("Board:GetTurn binding differs")
    return _expected_shape()


def validate_enemy_spawn_candidate_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the executable."""
    if not isinstance(value, Mapping):
        raise EnemySpawnCandidateBoundaryError("candidate boundary map must be an object")
    if dict(value) != _expected_shape():
        raise EnemySpawnCandidateBoundaryError("candidate boundary map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "enemy_source_order_proven": True,
        "primary_stable_filter_proven": True,
        "turn_zero_mode9_retry_proven": True,
        "emergency_max_x_row_proven": True,
        "enemy_validity_rejections_proven": True,
        "parameterized_replay_complete": True,
        "concrete_forecast_proven": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_spawn_candidate_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Rebuild and reject dependency, byte, address, or prose drift."""
    expected = build_enemy_spawn_candidate_boundary_map(executable, repository_root)
    if dict(value) != expected:
        raise EnemySpawnCandidateBoundaryError(
            "candidate boundary map differs from exact-build analysis"
        )
    result = validate_enemy_spawn_candidate_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_spawn_candidate_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
