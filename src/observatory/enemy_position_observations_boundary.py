"""Bind native ``ScorePositioning`` observations to exact current carriers.

The shipped Lua function calls a mixture of Board predicates, Pawn properties,
and two distance helpers.  This module pins those named Windows bindings and
their exact-build implementations, then provides narrow replays for the
semantics that can be reconstructed from an explicit observation packet.

The result is deliberately not a future enemy-phase predictor.  In particular,
``Board:IsDangerous`` is a native tile flag plus two Board Point vectors and is
not interchangeable with the bridge's ``Board:IsEnvironmentDanger`` scan.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.path_boundaries import (
    PathBoundaryError,
    validate_path_boundary_map_binding,
)
from src.observatory.path_cost_ordering import (
    PathCostOrderingError,
    validate_path_cost_ordering_map_binding,
)
from src.observatory.pe_anchor_map import PEAnchorError, PEImage
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    mask_lua_opaque,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_position_observations_boundary"
EXPECTED_BUILD_ID = "13725832"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_SCRIPTS_REVISION = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_INVENTORY_CANONICAL_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
IMAGE_BASE = 0x00400000
INT_MAX = (1 << 31) - 1
TEAM_PLAYER = 1
TEAM_ANY = 2
TEAM_ENEMY = 6
TERRAIN_BUILDING = 1
DIR_NONE = 4


class EnemyPositionObservationsBoundaryError(RuntimeError):
    """Raised when the exact observation boundary or replay differs."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
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
        "role": (
            "Pins the complete profile traversal and directional-wall bodies "
            "used by the distance-to-Pawn search."
        ),
    },
    {
        "id": "path_cost_ordering",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_path_cost_ordering.json"
        ),
        "file_sha256": (
            "f21127154c770ca5db14fec30ec8f9460c7694927bda2c152db1d9d0e3961fb5"
        ),
        "canonical_sha256": (
            "2bd57afec6c28ca75f7964995dd69125439fe913286a94a7a7fda877c0d0ad7d"
        ),
        "role": (
            "Pins the cached reachability search and unit edge-cost grammar "
            "used by Board:GetDistanceToPawn."
        ),
    },
)


SOURCE_FILES = (
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": (
            "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        ),
        "role": "Pins Pawn defaults and the ScorePositioning call site.",
    },
    {
        "path": "scripts/pawns.lua",
        "size": 27_397,
        "sha256": (
            "e999b8d98526c1e36f4746dd65b9d9e7ee3ca0b22029ed391d5b71fda49dc239"
        ),
        "role": "Pins the only two shipped AvoidingMines=true assignments.",
    },
)


AVOIDING_MINES_OCCURRENCES = (
    {"path": "scripts/global.lua", "line": 153, "column": 2, "value": False},
    {"path": "scripts/pawns.lua", "line": 1288, "column": 3, "value": True},
    {"path": "scripts/pawns.lua", "line": 1304, "column": 3, "value": True},
)


METHOD_BINDINGS = (
    {
        "id": "board_is_pod",
        "owner": "Board",
        "name": "IsPod",
        "name_rva": "0x004385e0",
        "registration_rva": "0x00279cdc",
        "registration_size": 34,
        "registration_sha256": "216804eaf647a9ef0ba46a7511954c6be38ab258535c1f11c9a970da52d246e6",
        "member_target_rva": "0x00172580",
        "implementation_rva": "0x00172580",
    },
    {
        "id": "board_is_dangerous_item",
        "owner": "Board",
        "name": "IsDangerousItem",
        "name_rva": "0x004385e8",
        "registration_rva": "0x00279d4b",
        "registration_size": 34,
        "registration_sha256": "83f78ab2af7b225e167e594f29a0e1c0d4764b707497c583ae41a7ea126d810c",
        "member_target_rva": "0x00172650",
        "implementation_rva": "0x00172650",
    },
    {
        "id": "board_is_dangerous",
        "owner": "Board",
        "name": "IsDangerous",
        "name_rva": "0x0043861c",
        "registration_rva": "0x00279d70",
        "registration_size": 34,
        "registration_sha256": "eab17162c1ee63b83c63a9fb4c06c66f3035d213af78fc7f9f0ec97da08831e1",
        "member_target_rva": "0x001726a0",
        "implementation_rva": "0x001726a0",
    },
    {
        "id": "board_get_terrain",
        "owner": "Board",
        "name": "GetTerrain",
        "name_rva": "0x004386c0",
        "registration_rva": "0x00279fa1",
        "registration_size": 34,
        "registration_sha256": "ef8cd4549bc103d9e776aa32989ba25886d468c3c66578353903c471dbeef043",
        "member_target_rva": "0x00104b70",
        "implementation_rva": "0x00104b70",
    },
    {
        "id": "board_is_building",
        "owner": "Board",
        "name": "IsBuilding",
        "name_rva": "0x004386d8",
        "registration_rva": "0x0027a010",
        "registration_size": 34,
        "registration_sha256": "53f9d576e0d4aa68c040b1d31614fb004c4b1ed338c4a2378e38fed41962cafa",
        "member_target_rva": "0x00168c00",
        "implementation_rva": "0x00168c00",
    },
    {
        "id": "board_is_pawn_team",
        "owner": "Board",
        "name": "IsPawnTeam",
        "name_rva": "0x004386f0",
        "registration_rva": "0x0027a0a4",
        "registration_size": 34,
        "registration_sha256": "7bf110e171a9a0531465d5b7ada4254bafb4fbc34ee8d78bd5d6733e6be9e3bc",
        "member_target_rva": "0x002e39d7",
        "implementation_rva": "0x0016fc50",
        "this_adjustment": 12,
        "vtable_slot_rva": "0x0042e2e0",
    },
    {
        "id": "board_is_targeted",
        "owner": "Board",
        "name": "IsTargeted",
        "name_rva": "0x0043881c",
        "registration_rva": "0x0027a55f",
        "registration_size": 34,
        "registration_sha256": "c27419572c664f07f5e0347cf610cd7e9ef23afbe084622622de82702887eead",
        "member_target_rva": "0x0016e760",
        "implementation_rva": "0x0016e760",
    },
    {
        "id": "board_is_fire",
        "owner": "Board",
        "name": "IsFire",
        "name_rva": "0x00438908",
        "registration_rva": "0x0027a860",
        "registration_size": 34,
        "registration_sha256": "de2add1a408ecea60cfaf3198f94b34c6115705ab9fab00e31c5a821f9e2dc87",
        "member_target_rva": "0x00168b50",
        "implementation_rva": "0x00168b50",
    },
    {
        "id": "board_is_smoke",
        "owner": "Board",
        "name": "IsSmoke",
        "name_rva": "0x00438924",
        "registration_rva": "0x0027a885",
        "registration_size": 34,
        "registration_sha256": "445622a476843d2590f1f67d8a7cd0b076b145830044534019f87189f1817283",
        "member_target_rva": "0x001662f0",
        "implementation_rva": "0x001662f0",
    },
    {
        "id": "board_get_distance_to_pawn",
        "owner": "Board",
        "name": "GetDistanceToPawn",
        "name_rva": "0x00438940",
        "registration_rva": "0x0027a936",
        "registration_size": 30,
        "registration_sha256": "a6b53c37db799573d7c1bf61d800136c7678b041f9b06a5cc7b3cbc7c04be39a",
        "member_target_rva": "0x00173c90",
        "implementation_rva": "0x00173c90",
        "dedicated_constructor_rva": "0x00289230",
    },
    {
        "id": "board_get_distance_to_building",
        "owner": "Board",
        "name": "GetDistanceToBuilding",
        "name_rva": "0x00438970",
        "registration_rva": "0x0027a957",
        "registration_size": 34,
        "registration_sha256": "8fe375417e1a0e400fff75dafca61d35b64c740a88fe487655a8d482e6641a47",
        "member_target_rva": "0x00173f30",
        "implementation_rva": "0x00173f30",
    },
    {
        "id": "board_is_spawning",
        "owner": "Board",
        "name": "IsSpawning",
        "name_rva": "0x004389b4",
        "registration_rva": "0x0027a9eb",
        "registration_size": 34,
        "registration_sha256": "de4e75e0457e706f80f39b68d0e7ab232eabf3453df902f2238c2acbf6f2ef36",
        "member_target_rva": "0x0016e4b0",
        "implementation_rva": "0x0016e4b0",
    },
    {
        "id": "pawn_is_avoiding_mines",
        "owner": "Pawn",
        "name": "IsAvoidingMines",
        "name_rva": "0x00438f70",
        "registration_rva": "0x0027bf47",
        "registration_size": 34,
        "registration_sha256": "965c22dc87b238d5e584ba09bb77f1a6c4845fa0d7db9d1bbb0e8f271350763e",
        "member_target_rva": "0x0023aea0",
        "implementation_rva": "0x0023aea0",
    },
    {
        "id": "pawn_get_team",
        "owner": "Pawn",
        "name": "GetTeam",
        "name_rva": "0x00439074",
        "registration_rva": "0x0027c1c1",
        "registration_size": 34,
        "registration_sha256": "ef6daf844d8d0df8bd6c920735f77996c14931c67e272b4e742ce32ea34a4de5",
        "member_target_rva": "0x0023d850",
        "implementation_rva": "0x0023d850",
    },
    {
        "id": "pawn_is_fire",
        "owner": "Pawn",
        "name": "IsFire",
        "name_rva": "0x00438908",
        "registration_rva": "0x0027c5b3",
        "registration_size": 34,
        "registration_sha256": "a0bc6f930e16ec5fabace04fd2bb16b4a5295f6edbdf2c7d4f70e42e162de75b",
        "member_target_rva": "0x0023d170",
        "implementation_rva": "0x0023d170",
    },
    {
        "id": "pawn_is_flying",
        "owner": "Pawn",
        "name": "IsFlying",
        "name_rva": "0x004391a0",
        "registration_rva": "0x0027c622",
        "registration_size": 34,
        "registration_sha256": "e48be6db3ad039859dbd4b04cef60ea6edea39faa3d890d7d7f126f99ad79549",
        "member_target_rva": "0x0023e490",
        "implementation_rva": "0x0023e490",
    },
    {
        "id": "pawn_is_ranged",
        "owner": "Pawn",
        "name": "IsRanged",
        "name_rva": "0x004391d4",
        "registration_rva": "0x0027c6d3",
        "registration_size": 34,
        "registration_sha256": "d7a296f1fdcb3f69b7c57516ebf4272041b2d4d0ee9c71c1d2579633a0893a8e",
        "member_target_rva": "0x0023f940",
        "implementation_rva": "0x0023f940",
    },
)


NATIVE_REGIONS = (
    ("board_is_pod", 0x00172580, 106, "04c19003a85b5a2687be2b27597d6fb7518cb79580a06e720eb64c7f8ed6ea03", "Candidate equals the Board pod point and the tile pod marker equals one."),
    ("board_get_terrain", 0x00104B70, 24, "bb0a4b8ace45f2208137e41a481c3d02d8c88c57e4b8def6e7d56776825eaf41", "Returns the selected tile terrain dword at +0x2ae0."),
    ("board_is_targeted", 0x0016E760, 198, "1fc492e2bd8ddf36545c8d365198266220fc8ae270584834da6f048fdbc50ab4", "Scans active Board objects and asks each target predicate about the Point."),
    ("board_is_smoke", 0x001662F0, 72, "7fd9bd9b5e6d81e4ec25278e26fdaf11f84cc576507b5278c6c4297c5d55e2e8", "Returns the valid tile smoke byte at +0x2b25."),
    ("board_is_fire", 0x00168B50, 83, "47375e562f03472f2a5113a18f3a01bd98d42b68eb7a8c9180069b1952540c4f", "Returns whether the valid tile fire dword at +0x2aec is nonzero."),
    ("board_is_spawning", 0x0016E4B0, 124, "78d607fec18d17442ef892f210ed5f8b5140d54bc35317b32f3b20a69c60100b", "Tests tile byte +0x27e8, then Board Point vector +0x2d50/+0x2d54."),
    ("board_is_dangerous_item", 0x00172650, 77, "b004ccd55b2fa6f4489aa7f1daafde27cb775f02b5ababd34e724521b882fcc2", "Selects the tile and invokes the exact embedded-item danger predicate."),
    ("tile_dangerous_item_core", 0x001A1270, 87, "bea7f9b5a0800c4bb29afb4df88d651aadae87805c8019cba1f5cd6b34f42fd3", "Requires an item and tests eight embedded SpaceDamage effects."),
    ("board_is_dangerous", 0x001726A0, 206, "c6e15d03f65fc709b28c8b15bf60cf5a7870700343d7b5be38ce7c3791d7f3f8", "Tests tile byte +0x2af0 and two Board-owned Point vectors."),
    ("board_is_building", 0x00168C00, 28, "dd8e526b31d9c1dba37385d664ddc76cdd32fae812334775e7c589e1aa164ab6", "Returns whether terrain +0x2ae0 equals one."),
    ("board_is_pawn_team", 0x0016FC50, 72, "aac917614c7bd4bef2cf9cb8f9b8ad78db2898a13648adf674b689bba93a3e69", "For an occupied tile, delegates the query to Pawn:IsTeam."),
    ("pawn_is_team", 0x0023D860, 209, "6f3a65620b7f448715c301400b1d26ce9784879254b5255b5772a1f95ad53906", "Implements special team queries; ScorePositioning uses only one and six."),
    ("board_get_distance_to_pawn", 0x00173C90, 348, "a78e58e1161895d3b8237ef823ed3d50fd8793c865dbb462fa05ef950cdb5f79", "Builds profile-six distances and minimizes across Pawns matching Pawn:IsTeam."),
    ("board_get_distance_to_building", 0x00173F30, 113, "85273d46807dd98b8f0d4f635ea11a9d165bf71242000a9754f584c048bd4d6b", "Returns minimum Manhattan distance to cached building Points."),
    ("board_rebuild_building_points", 0x001732F0, 400, "976153e7decaf1d7372e825dd99a8334ea2432ca62c9d0e9e9628abef583374c", "Clears the building Point cache and appends every tile whose terrain equals one."),
    ("pawn_is_avoiding_mines", 0x0023AEA0, 57, "ea98c01213b665dcf1c4d458586e2ddb9860de30abc1bc36314788d794e757a1", "Reads the exact Lua boolean property AvoidingMines."),
    ("pawn_get_team", 0x0023D850, 7, "a33ed4c54f724b1cdd526b3c3e8bfc670f9881db0df0a549f9dd82f82745c8cf", "Returns Pawn dword +0xb0."),
    ("pawn_is_flying", 0x0023E490, 225, "06fe4311381c6f3a5f31db9b53004c771762327a02ef33ced2c3af2bb021fbdb", "Combines the Lua Flying property and runtime byte +0x1314, then excludes dead Pawns."),
    ("pawn_is_fire", 0x0023D170, 7, "259360f841139af029982d66f7d2e5a0859318d972c8ffd445fe7782651efd71", "Returns Pawn byte +0x8d0."),
    ("pawn_is_ranged", 0x0023F940, 65, "63a7c7ed2a8c3d343132bba50f65de5f11b45c2526e1850b55d084a6306a94c8", "Reads exact Lua integer property Ranged and returns equality with one."),
    ("distance_to_pawn_binding_constructor", 0x00289230, 158, "82d77a3a18b2420f04afc803334b946e01177df4de474d27c660a184442870a4", "Hard-codes GetDistanceToPawn at VA 0x00838940."),
    ("is_pawn_team_thunk", 0x002E39D7, 8, "b7655f4aae69b7187b779cdc966f345e6a878c6ce4f756b676a079015b791f42", "Dispatches Board secondary-vtable slot +0x88."),
)


CONTROL_WINDOWS = (
    {
        "id": "space_damage_field_bindings",
        "start_rva": "0x0027ad76",
        "size": 140,
        "sha256": "7c40ef019e89ee225f54ac2e1f2f84552d5b58754e0bd3f75b788db750e6682c",
        "meaning": "Pins all relevant SpaceDamage field-name/offset pairs.",
    },
    {
        "id": "distance_profile_six_builder",
        "start_rva": "0x00173cba",
        "size": 28,
        "sha256": "634b9eac90220ddfb196cb966a4f3c12b7a24fcd8bc674faa9b1e85a7103e053",
        "meaning": "Passes literal low path profile six into the cached distance builder.",
    },
    {
        "id": "profile_six_traverses_every_valid_tile",
        "start_rva": "0x001a0162",
        "size": 33,
        "sha256": "3d20501621a6eac9bd1bb93c0d1bc9eb9711a7bef19c90562968381a92ff909e",
        "meaning": "Low profile six returns traversal true before terrain or occupancy tests.",
    },
    {
        "id": "profile_six_ignores_directional_walls",
        "start_rva": "0x001744a4",
        "size": 47,
        "sha256": "f162cc9641713cb41aa8cee69f5864fbac1a0b7e25f0c7c3965fbc501c7d9ddc",
        "meaning": "Low profile six returns no wall block, matching profiles one, three, and five.",
    },
)


CALL_EDGES = (
    ("dangerous_item_to_core_valid", 0x00172680, 0x001A1270, "e8ebeb0200"),
    ("dangerous_item_to_core_fallback", 0x00172691, 0x001A1270, "e8daeb0200"),
    ("targeted_to_point_predicate", 0x0016E7F1, 0x00228AB0, "e8baa20b00"),
    ("board_pawn_team_to_pawn_lookup", 0x0016FC85, 0x00171D00, "e876200000"),
    ("board_pawn_team_to_pawn_is_team", 0x0016FC8C, 0x0023D860, "e8cfdb0c00"),
    ("distance_to_pawn_to_profile_builder", 0x00173CD1, 0x000CEA50, "e87aadf5ff"),
    ("distance_to_pawn_to_pawn_is_team", 0x00173D00, 0x0023D860, "e85b9b0c00"),
    ("avoiding_mines_to_boolean_getter", 0x0023AECF, 0x000493B0, "e8dce4e0ff"),
    ("ranged_to_integer_getter", 0x0023F96F, 0x00049290, "e81c99e0ff"),
)


PROPERTY_STRINGS = (
    ("avoiding_mines_property", 0x0043699C, "AvoidingMines", 0x0023AEBC),
    ("flying_property", 0x00436014, "Flying", 0x0023E4E2),
    ("ranged_property", 0x0042C7B4, "Ranged", 0x0023F95C),
)


SPACE_DAMAGE_FIELDS = (
    ("iDamage", 0x08, 0x288C, 0, 0x00438A98),
    ("iPush", 0x0C, 0x2890, DIR_NONE, 0x00438A90),
    ("iShield", 0x10, 0x2894, 0, 0x00438AA8),
    ("iFire", 0x18, 0x289C, 0, 0x00438AB0),
    ("iFrozen", 0x1C, 0x28A0, 0, 0x00438AC0),
    ("iSmoke", 0x24, 0x28A8, 0, 0x00438AE0),
    ("iAcid", 0x28, 0x28AC, 0, 0x00438B2C),
    ("sPawn", 0xA4, 0x2938, "empty length at +0xb4", 0x00438AE8),
)


def _canonical_sha256(value: Mapping[str, Any] | list[Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_rva(value: str) -> int:
    return int(value, 16)


def _require_i32(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnemyPositionObservationsBoundaryError(f"{label} must be an integer")
    if not -(1 << 31) <= value <= INT_MAX:
        raise EnemyPositionObservationsBoundaryError(
            f"{label} must be a signed 32-bit integer"
        )
    return value


def _point(value: Any, label: str, *, require_valid: bool = True) -> tuple[int, int]:
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemyPositionObservationsBoundaryError(f"{label} must be [x,y]")
    x = _require_i32(value[0], f"{label}.x")
    y = _require_i32(value[1], f"{label}.y")
    if require_valid and not (0 <= x < 8 and 0 <= y < 8):
        raise EnemyPositionObservationsBoundaryError(
            f"{label} must be a valid stock-board Point"
        )
    return x, y


def _point_set(values: Any, label: str) -> set[tuple[int, int]]:
    if isinstance(values, (str, bytes, bytearray, Mapping)) or not isinstance(
        values, Sequence
    ):
        raise EnemyPositionObservationsBoundaryError(f"{label} must be a Point list")
    return {_point(value, f"{label}[{index}]") for index, value in enumerate(values)}


def replay_board_is_dangerous(
    point: Sequence[int],
    *,
    tile_flag: bool,
    first_points: Sequence[Sequence[int]],
    second_points: Sequence[Sequence[int]],
) -> bool:
    """Replay valid-tile ``Board:IsDangerous`` exactly."""

    candidate = _point(point, "point")
    if not isinstance(tile_flag, bool):
        raise EnemyPositionObservationsBoundaryError("tile_flag must be boolean")
    return (
        tile_flag
        or candidate in _point_set(first_points, "first_points")
        or candidate in _point_set(second_points, "second_points")
    )


def replay_board_is_spawning(
    point: Sequence[int],
    *,
    tile_flag: bool,
    spawning_points: Sequence[Sequence[int]],
) -> bool:
    """Replay valid-tile ``Board:IsSpawning`` exactly."""

    candidate = _point(point, "point")
    if not isinstance(tile_flag, bool):
        raise EnemyPositionObservationsBoundaryError("tile_flag must be boolean")
    return tile_flag or candidate in _point_set(spawning_points, "spawning_points")


def replay_board_is_dangerous_item(
    *,
    item_present: bool,
    i_damage: int = 0,
    i_push: int = DIR_NONE,
    i_shield: int = 0,
    i_fire: int = 0,
    i_smoke: int = 0,
    s_pawn_present: bool = False,
    i_acid: int = 0,
    i_frozen: int = 0,
) -> bool:
    """Replay the embedded item ``SpaceDamage`` danger predicate."""

    if not isinstance(item_present, bool) or not isinstance(s_pawn_present, bool):
        raise EnemyPositionObservationsBoundaryError(
            "item_present and s_pawn_present must be boolean"
        )
    fields = {
        "i_damage": _require_i32(i_damage, "i_damage"),
        "i_push": _require_i32(i_push, "i_push"),
        "i_shield": _require_i32(i_shield, "i_shield"),
        "i_fire": _require_i32(i_fire, "i_fire"),
        "i_smoke": _require_i32(i_smoke, "i_smoke"),
        "i_acid": _require_i32(i_acid, "i_acid"),
        "i_frozen": _require_i32(i_frozen, "i_frozen"),
    }
    return item_present and (
        fields["i_damage"] != 0
        or fields["i_push"] != DIR_NONE
        or fields["i_shield"] != 0
        or fields["i_fire"] != 0
        or fields["i_smoke"] != 0
        or s_pawn_present
        or fields["i_acid"] != 0
        or fields["i_frozen"] != 0
    )


def replay_score_team_match(actual_team: int, query_team: int) -> bool:
    """Replay ``Pawn:IsTeam`` for the two ScorePositioning query values."""

    actual = _require_i32(actual_team, "actual_team")
    query = _require_i32(query_team, "query_team")
    if query == TEAM_PLAYER:
        return actual == TEAM_PLAYER
    if query == TEAM_ENEMY:
        return actual >= TEAM_ENEMY
    raise EnemyPositionObservationsBoundaryError(
        "query_team must be TEAM_PLAYER=1 or TEAM_ENEMY=6"
    )


def replay_board_is_pawn_team(
    occupant_team: int | None, query_team: int
) -> bool:
    """Replay ``Board:IsPawnTeam`` for ScorePositioning's team queries."""

    query = _require_i32(query_team, "query_team")
    if query not in (TEAM_PLAYER, TEAM_ENEMY):
        raise EnemyPositionObservationsBoundaryError(
            "query_team must be TEAM_PLAYER=1 or TEAM_ENEMY=6"
        )
    if occupant_team is None:
        return False
    return replay_score_team_match(occupant_team, query)


def replay_distance_to_pawn(
    point: Sequence[int],
    pawns: Sequence[Mapping[str, Any]],
    query_team: int,
) -> int:
    """Replay profile-six minimum Pawn distance on the stock 8x8 Board."""

    origin = _point(point, "point")
    query = _require_i32(query_team, "query_team")
    if query not in (TEAM_PLAYER, TEAM_ENEMY):
        raise EnemyPositionObservationsBoundaryError(
            "query_team must be TEAM_PLAYER=1 or TEAM_ENEMY=6"
        )
    if isinstance(pawns, (str, bytes, bytearray, Mapping)) or not isinstance(
        pawns, Sequence
    ):
        raise EnemyPositionObservationsBoundaryError("pawns must be a list")
    best = INT_MAX
    for index, pawn in enumerate(pawns):
        if not isinstance(pawn, Mapping) or set(pawn) != {"point", "team"}:
            raise EnemyPositionObservationsBoundaryError(
                f"pawns[{index}] must contain exactly point and team"
            )
        team = _require_i32(pawn["team"], f"pawns[{index}].team")
        target = _point(pawn["point"], f"pawns[{index}].point", require_valid=False)
        if not (0 <= target[0] < 8 and 0 <= target[1] < 8):
            continue
        if replay_score_team_match(team, query):
            best = min(best, abs(origin[0] - target[0]) + abs(origin[1] - target[1]))
    return best


def replay_distance_to_building(
    point: Sequence[int], building_points: Sequence[Sequence[int]]
) -> int:
    """Replay minimum Manhattan distance to the exact native building cache."""

    origin = _point(point, "point")
    points = _point_set(building_points, "building_points")
    return min(
        (abs(origin[0] - target[0]) + abs(origin[1] - target[1]) for target in points),
        default=INT_MAX,
    )


def replay_pawn_is_ranged(lua_integer: int) -> bool:
    """Replay the exact integer-equals-one Ranged property test."""

    return _require_i32(lua_integer, "lua_integer") == 1


def replay_pawn_is_avoiding_mines(lua_boolean: bool) -> bool:
    """Replay the exact boolean AvoidingMines property result."""

    if not isinstance(lua_boolean, bool):
        raise EnemyPositionObservationsBoundaryError("lua_boolean must be boolean")
    return lua_boolean


def replay_pawn_is_flying(
    *, definition_flying: bool, runtime_flying: bool, pawn_is_dead: bool
) -> bool:
    """Replay the exact native Flying/property/death composition."""

    if not all(
        isinstance(value, bool)
        for value in (definition_flying, runtime_flying, pawn_is_dead)
    ):
        raise EnemyPositionObservationsBoundaryError(
            "flying inputs must be boolean"
        )
    return (definition_flying or runtime_flying) and not pawn_is_dead


def _bridge_point_sequence(value: Any, label: str) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        raise EnemyPositionObservationsBoundaryError(
            f"{label} must be a Point list"
        )
    points = tuple(
        _point(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    )
    if len(set(points)) != len(points):
        raise EnemyPositionObservationsBoundaryError(
            f"{label} contains duplicate Points"
        )
    return points


def bridge_native_enemy_position_observations(
    bridge_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate exact current native inputs used by ``ScorePositioning``.

    The result is intentionally current-only. It proves that a fresh bridge
    state carries the direct native predicates without promoting that state to
    the later enemy candidate callback time.
    """
    if not isinstance(bridge_data, Mapping):
        raise EnemyPositionObservationsBoundaryError(
            "bridge state must be a mapping"
        )
    position = bridge_data.get("native_enemy_position_inputs")
    spawn = bridge_data.get("native_enemy_spawn_inputs")
    if not isinstance(position, Mapping) or not isinstance(spawn, Mapping):
        raise EnemyPositionObservationsBoundaryError(
            "native enemy-position bridge inputs are unavailable"
        )
    if (
        position.get("schema_version") != SCHEMA_VERSION
        or position.get("current_snapshot_only") is not True
        or position.get("dangerous_item_tiles_complete") is not True
        or position.get("pawn_flags_ordered_complete") is not True
        or spawn.get("schema_version") != SCHEMA_VERSION
        or spawn.get("current_snapshot_only") is not True
        or spawn.get("dangerous_tiles_complete") is not True
    ):
        raise EnemyPositionObservationsBoundaryError(
            "native enemy-position bridge inputs are incomplete"
        )

    dangerous = _bridge_point_sequence(
        spawn.get("dangerous_tiles"), "dangerous_tiles"
    )
    dangerous_items = _bridge_point_sequence(
        position.get("dangerous_item_tiles"), "dangerous_item_tiles"
    )
    raw_tiles = bridge_data.get("tiles")
    if not isinstance(raw_tiles, list):
        raise EnemyPositionObservationsBoundaryError(
            "bridge tiles must be a list"
        )
    tile_item_points: set[tuple[int, int]] = set()
    tile_points: set[tuple[int, int]] = set()
    for index, tile in enumerate(raw_tiles):
        if not isinstance(tile, Mapping):
            raise EnemyPositionObservationsBoundaryError(
                f"bridge tile {index} must be a mapping"
            )
        point = _point(
            [tile.get("x"), tile.get("y")],
            f"bridge tile {index}",
        )
        if point in tile_points:
            raise EnemyPositionObservationsBoundaryError(
                "bridge tiles contain duplicate Points"
            )
        tile_points.add(point)
        item_danger = tile.get("dangerous_item")
        if type(item_danger) is not bool:
            raise EnemyPositionObservationsBoundaryError(
                "bridge tile dangerous_item must be Boolean"
            )
        if item_danger:
            tile_item_points.add(point)
    expected_points = {(x, y) for x in range(8) for y in range(8)}
    if tile_points != expected_points:
        raise EnemyPositionObservationsBoundaryError(
            "bridge tiles must cover the complete 8x8 Board"
        )
    if tile_item_points != set(dangerous_items):
        raise EnemyPositionObservationsBoundaryError(
            "dangerous-item bridge carriers disagree"
        )

    raw_flags = position.get("pawn_flags_ordered")
    if not isinstance(raw_flags, list):
        raise EnemyPositionObservationsBoundaryError(
            "pawn_flags_ordered must be a list"
        )
    pawn_flags: dict[int, dict[str, bool]] = {}
    ordered_uids: list[int] = []
    for index, entry in enumerate(raw_flags):
        if not isinstance(entry, Mapping) or set(entry) != {
            "uid",
            "ranged",
            "avoiding_mines",
        }:
            raise EnemyPositionObservationsBoundaryError(
                f"pawn_flags_ordered[{index}] fields differ"
            )
        uid = _require_i32(entry["uid"], f"pawn_flags_ordered[{index}].uid")
        ranged = entry["ranged"]
        avoiding_mines = entry["avoiding_mines"]
        if uid < 0 or type(ranged) is not bool or type(avoiding_mines) is not bool:
            raise EnemyPositionObservationsBoundaryError(
                f"pawn_flags_ordered[{index}] values differ"
            )
        if uid in pawn_flags:
            raise EnemyPositionObservationsBoundaryError(
                "pawn_flags_ordered contains duplicate UIDs"
            )
        ordered_uids.append(uid)
        pawn_flags[uid] = {
            "ranged": ranged,
            "avoiding_mines": avoiding_mines,
        }

    raw_units = bridge_data.get("units")
    if not isinstance(raw_units, list):
        raise EnemyPositionObservationsBoundaryError(
            "bridge units must be a list"
        )
    primary_uids: list[int] = []
    for index, unit in enumerate(raw_units):
        if not isinstance(unit, Mapping):
            raise EnemyPositionObservationsBoundaryError(
                f"bridge unit {index} must be a mapping"
            )
        if unit.get("is_extra_tile") is True:
            continue
        uid = _require_i32(unit.get("uid"), f"bridge unit {index}.uid")
        ranged = unit.get("ranged")
        avoiding_mines = unit.get("avoiding_mines")
        if (
            uid < 0
            or type(ranged) is not int
            or ranged not in (0, 1)
            or type(avoiding_mines) is not bool
        ):
            raise EnemyPositionObservationsBoundaryError(
                f"bridge unit {index} native position flags differ"
            )
        if uid in primary_uids:
            raise EnemyPositionObservationsBoundaryError(
                "bridge primary units contain duplicate UIDs"
            )
        primary_uids.append(uid)
        if pawn_flags.get(uid) != {
            "ranged": ranged == 1,
            "avoiding_mines": avoiding_mines,
        }:
            raise EnemyPositionObservationsBoundaryError(
                "pawn flag bridge carriers disagree"
            )
    if primary_uids != ordered_uids:
        raise EnemyPositionObservationsBoundaryError(
            "pawn flag order differs from the native Board pawn order"
        )

    return {
        "dangerous_points": frozenset(dangerous),
        "dangerous_item_points": frozenset(dangerous_items),
        "pawn_flags": pawn_flags,
        "pawn_order": tuple(ordered_uids),
        "complete_for_current_score_positioning": True,
        "current_snapshot_only": True,
        "future_candidate_time": False,
    }


def _region_bytes(image: PEImage, raw: bytes, rva: int, size: int) -> bytes:
    try:
        offset = image.rva_span_to_file_offset(rva, size)
    except PEAnchorError as exc:
        raise EnemyPositionObservationsBoundaryError(
            f"PE region differs at RVA 0x{rva:08x}: {exc}"
        ) from exc
    if offset is None:
        raise EnemyPositionObservationsBoundaryError(
            f"PE region is unmapped at RVA 0x{rva:08x}"
        )
    return raw[offset : offset + size]


def _read_executable(
    content_root: Path, inventory: Mapping[str, Any]
) -> tuple[bytes, PEImage]:
    try:
        entry = inventory["executable"]
    except (KeyError, TypeError) as exc:
        raise EnemyPositionObservationsBoundaryError(
            "executable inventory entry differs"
        ) from exc
    candidate = content_root / "Breach.exe"
    if candidate.is_symlink() or not candidate.is_file():
        raise EnemyPositionObservationsBoundaryError(
            "Breach.exe is not a regular non-symlink file"
        )
    before = candidate.stat()
    raw = candidate.read_bytes()
    after = candidate.stat()
    digest = hashlib.sha256(raw).hexdigest()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != EXPECTED_EXECUTABLE_SIZE
        or len(raw) != entry.get("size")
        or digest != EXPECTED_EXECUTABLE_SHA256
        or digest != entry.get("sha256")
    ):
        raise EnemyPositionObservationsBoundaryError(
            "Breach.exe differs from accepted inventory"
        )
    try:
        image = PEImage(raw)
    except PEAnchorError as exc:
        raise EnemyPositionObservationsBoundaryError(
            f"Breach.exe PE image differs: {exc}"
        ) from exc
    return raw, image


def _verify_source(content_root: Path, inventory: Mapping[str, Any]) -> None:
    try:
        block = inventory["content"]["scripts"]
        entries = {item["path"]: item for item in block["files"]}
        if block["revision_sha256"] != EXPECTED_SCRIPTS_REVISION:
            raise KeyError("scripts revision")
    except (KeyError, TypeError) as exc:
        raise EnemyPositionObservationsBoundaryError(
            "script inventory fields differ"
        ) from exc
    sources: dict[str, str] = {}
    try:
        for spec in SOURCE_FILES:
            entry = entries[spec["path"]]
            if entry.get("size") != spec["size"] or entry.get("sha256") != spec["sha256"]:
                raise KeyError(spec["path"])
            sources[spec["path"]] = read_exact_inventory_file(
                content_root,
                PurePosixPath(spec["path"]),
                expected_size=spec["size"],
                expected_sha256=spec["sha256"],
            )
    except (KeyError, TypeError, WeaponCoverageError) as exc:
        raise EnemyPositionObservationsBoundaryError(
            f"source file differs: {exc}"
        ) from exc
    actual: list[dict[str, Any]] = []
    pattern = re.compile(r"\bAvoidingMines\b\s*=\s*(true|false)\b")
    for path in sorted(sources):
        text = sources[path]
        masked = mask_lua_opaque(text)
        for match in pattern.finditer(masked):
            line_start = text.rfind("\n", 0, match.start()) + 1
            actual.append(
                {
                    "path": path,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "column": match.start() - line_start + 1,
                    "value": match.group(1) == "true",
                }
            )
    if actual != list(AVOIDING_MINES_OCCURRENCES):
        raise EnemyPositionObservationsBoundaryError(
            "AvoidingMines source census differs"
        )


def _read_repo_dependency(spec: Mapping[str, Any]) -> Mapping[str, Any]:
    path = REPO_ROOT / str(spec["path"])
    if path.is_symlink() or not path.is_file():
        raise EnemyPositionObservationsBoundaryError(
            f"not a regular dependency: {path}"
        )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
        raise EnemyPositionObservationsBoundaryError(
            f"dependency file hash differs: {spec['id']}"
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnemyPositionObservationsBoundaryError(
            f"dependency JSON differs: {spec['id']}"
        ) from exc
    if not isinstance(value, Mapping) or _canonical_sha256(value) != spec["canonical_sha256"]:
        raise EnemyPositionObservationsBoundaryError(
            f"dependency fields differ: {spec['id']}"
        )
    return value


def _verify_dependencies() -> None:
    for spec in DEPENDENCY_SPECS:
        value = _read_repo_dependency(spec)
        try:
            if spec["id"] == "path_boundaries":
                validate_path_boundary_map_binding(value)
            else:
                validate_path_cost_ordering_map_binding(value)
        except (PathBoundaryError, PathCostOrderingError) as exc:
            raise EnemyPositionObservationsBoundaryError(
                f"dependency binding differs: {spec['id']}: {exc}"
            ) from exc


def _verify_native(raw: bytes, image: PEImage) -> None:
    for region_id, start, size, digest, _meaning in NATIVE_REGIONS:
        body = _region_bytes(image, raw, start, size)
        if hashlib.sha256(body).hexdigest() != digest:
            raise EnemyPositionObservationsBoundaryError(
                f"native region differs: {region_id}"
            )
    for spec in METHOD_BINDINGS:
        start = _parse_rva(spec["registration_rva"])
        body = _region_bytes(image, raw, start, spec["registration_size"])
        if hashlib.sha256(body).hexdigest() != spec["registration_sha256"]:
            raise EnemyPositionObservationsBoundaryError(
                f"method registration differs: {spec['id']}"
            )
        encoded_name = spec["name"].encode("ascii") + b"\0"
        if _region_bytes(image, raw, _parse_rva(spec["name_rva"]), len(encoded_name)) != encoded_name:
            raise EnemyPositionObservationsBoundaryError(
                f"method name differs: {spec['id']}"
            )
    for spec in CONTROL_WINDOWS:
        body = _region_bytes(
            image, raw, _parse_rva(spec["start_rva"]), spec["size"]
        )
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise EnemyPositionObservationsBoundaryError(
                f"control window differs: {spec['id']}"
            )
    for edge_id, instruction, target, encoded_hex in CALL_EDGES:
        encoded = bytes.fromhex(encoded_hex)
        if _region_bytes(image, raw, instruction, len(encoded)) != encoded:
            raise EnemyPositionObservationsBoundaryError(
                f"call edge differs: {edge_id}"
            )
        displacement = struct.unpack("<i", encoded[1:])[0]
        if encoded[0] != 0xE8 or instruction + len(encoded) + displacement != target:
            raise EnemyPositionObservationsBoundaryError(
                f"call edge target differs: {edge_id}"
            )
    for string_id, rva, value, reference in PROPERTY_STRINGS:
        encoded = value.encode("ascii") + b"\0"
        if _region_bytes(image, raw, rva, len(encoded)) != encoded:
            raise EnemyPositionObservationsBoundaryError(
                f"property string differs: {string_id}"
            )
        if _region_bytes(image, raw, reference, 5) != b"\x68" + struct.pack(
            "<I", IMAGE_BASE + rva
        ):
            raise EnemyPositionObservationsBoundaryError(
                f"property reference differs: {string_id}"
            )
    for field_name, _record_offset, _tile_offset, _neutral, rva in SPACE_DAMAGE_FIELDS:
        encoded = field_name.encode("ascii") + b"\0"
        if _region_bytes(image, raw, rva, len(encoded)) != encoded:
            raise EnemyPositionObservationsBoundaryError(
                f"SpaceDamage field name differs: {field_name}"
            )
    if _region_bytes(image, raw, 0x0042E2E0, 4) != struct.pack("<I", 0x0056FC50):
        raise EnemyPositionObservationsBoundaryError(
            "Board IsPawnTeam vtable slot differs"
        )


def _replay_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []

    dangerous_cases = (
        ("danger_tile_flag", [3, 3], True, [], [], True),
        ("danger_first_vector", [3, 3], False, [[3, 3]], [], True),
        ("danger_second_vector", [3, 3], False, [], [[3, 3]], True),
        ("danger_absent", [3, 3], False, [[2, 3]], [[3, 2]], False),
    )
    for vector_id, point, flag, first, second, expected in dangerous_cases:
        vectors.append(
            {
                "id": vector_id,
                "kind": "board_is_dangerous",
                "input": {
                    "point": point,
                    "tile_flag": flag,
                    "first_points": first,
                    "second_points": second,
                },
                "expected": expected,
            }
        )

    neutral_item = {
        "item_present": True,
        "i_damage": 0,
        "i_push": DIR_NONE,
        "i_shield": 0,
        "i_fire": 0,
        "i_smoke": 0,
        "s_pawn_present": False,
        "i_acid": 0,
        "i_frozen": 0,
    }
    vectors.extend(
        [
            {
                "id": "dangerous_item_neutral_tuple",
                "kind": "board_is_dangerous_item",
                "input": dict(neutral_item),
                "expected": False,
            },
            {
                "id": "dangerous_item_damage",
                "kind": "board_is_dangerous_item",
                "input": {**neutral_item, "i_damage": 1},
                "expected": True,
            },
            {
                "id": "dangerous_item_non_none_push",
                "kind": "board_is_dangerous_item",
                "input": {**neutral_item, "i_push": 0},
                "expected": True,
            },
            {
                "id": "dangerous_item_spawned_pawn",
                "kind": "board_is_dangerous_item",
                "input": {**neutral_item, "s_pawn_present": True},
                "expected": True,
            },
        ]
    )

    vectors.extend(
        [
            {
                "id": "enemy_query_accepts_specialized_enemy_team",
                "kind": "score_team_match",
                "input": {"actual_team": 7, "query_team": TEAM_ENEMY},
                "expected": True,
            },
            {
                "id": "empty_pawn_tile_is_false_for_score_query",
                "kind": "board_is_pawn_team",
                "input": {"occupant_team": None, "query_team": TEAM_ENEMY},
                "expected": False,
            },
            {
                "id": "distance_to_enemy_uses_manhattan_and_team_filter",
                "kind": "distance_to_pawn",
                "input": {
                    "point": [3, 3],
                    "pawns": [
                        {"point": [3, 2], "team": TEAM_PLAYER},
                        {"point": [6, 5], "team": TEAM_ENEMY},
                        {"point": [-1, -1], "team": TEAM_ENEMY},
                    ],
                    "query_team": TEAM_ENEMY,
                },
                "expected": 5,
            },
            {
                "id": "distance_to_pawn_empty_is_int_max",
                "kind": "distance_to_pawn",
                "input": {
                    "point": [3, 3],
                    "pawns": [],
                    "query_team": TEAM_PLAYER,
                },
                "expected": INT_MAX,
            },
            {
                "id": "distance_to_building_is_manhattan",
                "kind": "distance_to_building",
                "input": {
                    "point": [3, 3],
                    "building_points": [[0, 0], [5, 4]],
                },
                "expected": 3,
            },
            {
                "id": "distance_to_building_empty_is_int_max",
                "kind": "distance_to_building",
                "input": {"point": [3, 3], "building_points": []},
                "expected": INT_MAX,
            },
            {
                "id": "ranged_requires_exact_integer_one",
                "kind": "pawn_is_ranged",
                "input": {"lua_integer": 2},
                "expected": False,
            },
            {
                "id": "dead_pawn_suppresses_flying",
                "kind": "pawn_is_flying",
                "input": {
                    "definition_flying": True,
                    "runtime_flying": False,
                    "pawn_is_dead": True,
                },
                "expected": False,
            },
        ]
    )
    return vectors


def _carrier_matrix() -> list[dict[str, Any]]:
    return [
        {"observation": "Board:IsPod", "carrier": "tiles[].pod", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:GetTerrain", "carrier": "tiles[].terrain_id", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsTargeted", "carrier": "targeted_tiles", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsSmoke", "carrier": "tiles[].smoke", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsFire", "carrier": "tiles[].fire", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Pawn:IsFire", "carrier": "units[].fire", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsSpawning", "carrier": "spawning_tiles", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Pawn:IsFlying", "carrier": "units[].flying", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Pawn:GetTeam", "carrier": "units[].team", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsBuilding", "carrier": "tiles[].terrain_id == 1", "status": "exact_current_derivation", "source": "native terrain equality"},
        {"observation": "Board:IsPawnTeam for team 1/6", "carrier": "occupied units[].team", "status": "exact_current_derivation_if_native_occupant_is_identified", "source": "native Pawn:IsTeam"},
        {"observation": "Board:GetDistanceToPawn for team 1/6", "carrier": "units[].{x,y,team}", "status": "exact_current_derivation", "source": "profile-six Manhattan replay"},
        {"observation": "Board:GetDistanceToBuilding", "carrier": "native building Point cache", "status": "exact_replay_from_explicit_cache", "source": "native terrain-1 cache builder"},
        {"observation": "Pawn:IsRanged", "carrier": "units[].ranged plus native_enemy_position_inputs.pawn_flags_ordered", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Pawn:IsAvoidingMines", "carrier": "units[].avoiding_mines plus native_enemy_position_inputs.pawn_flags_ordered", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsDangerous", "carrier": "native_enemy_spawn_inputs.dangerous_tiles", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
        {"observation": "Board:IsDangerousItem", "carrier": "tiles[].dangerous_item plus native_enemy_position_inputs.dangerous_item_tiles", "status": "direct_exact_current", "source": "src/bridge/modloader.lua"},
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {"id": "all_named_observation_bindings_are_exact", "classification": "fact", "claim": "Seventeen Board/Pawn names used by ScorePositioning bind to the reviewed exact-build members; IsPawnTeam reaches its implementation through secondary-vtable slot +0x88."},
        {"id": "dangerous_is_not_environment_danger", "classification": "fact", "claim": "Board:IsDangerous tests tile byte +0x2af0 and exact Point membership in Board vectors +0x7460 and +0x7470; it does not call Board:IsEnvironmentDanger."},
        {"id": "dangerous_item_has_eight_effect_tests", "classification": "fact", "claim": "An item is dangerous only when present and at least one of iDamage, non-DIR_NONE iPush, iShield, iFire, iSmoke, nonempty sPawn, iAcid, or iFrozen is active."},
        {"id": "spawning_has_two_native_sources", "classification": "fact", "claim": "Board:IsSpawning returns true from either tile byte +0x27e8 or membership in Board Point vector +0x2d50/+0x2d54."},
        {"id": "targeted_is_direct_object_membership", "classification": "fact", "claim": "Board:IsTargeted walks active Board objects and returns true at the first object whose native Point predicate matches; the bridge's direct all-board scan preserves that result."},
        {"id": "score_team_queries_are_simple", "classification": "fact", "claim": "For ScorePositioning's only queries, TEAM_PLAYER=1 requires exact team one and TEAM_ENEMY=6 accepts every actual team greater than or equal to six."},
        {"id": "pawn_distance_is_manhattan", "classification": "inference", "claim": "GetDistanceToPawn uses literal low profile six; exact traversal and wall bodies admit every valid cardinal neighbor at unit cost, so its minimum distance to a matching on-board Pawn is Manhattan and empty is INT_MAX."},
        {"id": "building_distance_uses_terrain_one_cache", "classification": "fact", "claim": "The native cache builder clears +0x2c44/+0x2c48 and appends every terrain-one Point; GetDistanceToBuilding returns minimum Manhattan distance over that explicit cache or INT_MAX when empty."},
        {"id": "pawn_definition_flags_are_exact_live_carriers", "classification": "fact", "claim": "IsRanged is exact Lua integer equality with one; IsAvoidingMines is an exact Lua boolean; IsFlying combines its Lua property and runtime byte then rejects dead Pawns. The current bridge now calls and exports all three live predicates without replacing them with stock type assumptions."},
        {"id": "no_solver_contradiction", "classification": "inference", "claim": "These findings refine prospective native enemy scoring inputs; the Rust solver still consumes the settled queue and no current simulator rule contradicts the boundary."},
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {"id": "candidate_time_board_snapshot", "question": "What are all observations at each future candidate's exact callback time?", "static_status": "The native meanings are exact, but a settled current bridge read is not a post-player-action, per-candidate enemy callback snapshot."},
        {"id": "complete_enemy_phase_forecast", "question": "Does this observation closure produce a full native enemy tournament?", "static_status": "No; concrete future callback payloads, candidate records, shared RNG state, and selector entry remain separate inputs."},
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
    vectors = _replay_vectors()
    carriers = _carrier_matrix()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION,
        },
        "dependencies": [dict(spec) for spec in DEPENDENCY_SPECS]
        + [
            {
                "id": "accepted_local_inventory",
                "path": "data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json",
                "canonical_sha256": EXPECTED_INVENTORY_CANONICAL_SHA256,
                "role": "Pins the exact executable and shipped Lua source files.",
            }
        ],
        "source_files": [dict(spec) for spec in SOURCE_FILES],
        "avoiding_mines_source_census": [
            dict(item) for item in AVOIDING_MINES_OCCURRENCES
        ],
        "method_bindings": [dict(spec) for spec in METHOD_BINDINGS],
        "native_regions": [
            {
                "id": region_id,
                "start_rva": f"0x{start:08x}",
                "size": size,
                "sha256": digest,
                "meaning": meaning,
            }
            for region_id, start, size, digest, meaning in NATIVE_REGIONS
        ],
        "control_windows": [dict(spec) for spec in CONTROL_WINDOWS],
        "call_edges": [
            {
                "id": edge_id,
                "instruction_rva": f"0x{instruction:08x}",
                "target_rva": f"0x{target:08x}",
                "instruction_hex": encoded,
            }
            for edge_id, instruction, target, encoded in CALL_EDGES
        ],
        "property_strings": [
            {
                "id": string_id,
                "rva": f"0x{rva:08x}",
                "value": value,
                "reference_instruction_rva": f"0x{reference:08x}",
            }
            for string_id, rva, value, reference in PROPERTY_STRINGS
        ],
        "contracts": {
            "scope": "valid Points on the shipped 8x8 Board",
            "team_values": {
                "TEAM_PLAYER": TEAM_PLAYER,
                "TEAM_ANY": TEAM_ANY,
                "TEAM_ENEMY": TEAM_ENEMY,
            },
            "terrain_building": TERRAIN_BUILDING,
            "dir_none": DIR_NONE,
            "dangerous": {
                "tile_flag_offset": "+0x2af0",
                "first_point_vector": "+0x7460/+0x7464",
                "second_point_vector": "+0x7470/+0x7474",
                "environment_danger_is_not_a_substitute": True,
            },
            "dangerous_item": {
                "item_presence_offset": "+0x2b04",
                "embedded_space_damage_base": "+0x2884",
                "fields": [
                    {
                        "name": name,
                        "record_offset": f"+0x{record_offset:02x}",
                        "tile_test_offset": f"+0x{tile_offset:04x}",
                        "neutral": neutral,
                    }
                    for name, record_offset, tile_offset, neutral, _rva in SPACE_DAMAGE_FIELDS
                ],
                "safe_tuple": {
                    "iDamage": 0,
                    "iPush": DIR_NONE,
                    "iShield": 0,
                    "iFire": 0,
                    "iSmoke": 0,
                    "sPawn": "empty",
                    "iAcid": 0,
                    "iFrozen": 0,
                },
            },
            "spawning": {
                "tile_flag_offset": "+0x27e8",
                "point_vector": "+0x2d50/+0x2d54",
            },
            "targeted": {
                "board_object_vector": "+0x3c/+0x40",
                "active_virtual_slot": "+0x18",
                "point_predicate_rva": "0x00228ab0",
            },
            "building": {
                "terrain_offset": "+0x2ae0",
                "terrain_value": TERRAIN_BUILDING,
                "point_cache": "+0x2c44/+0x2c48",
                "distance": "minimum Manhattan or INT_MAX",
            },
            "pawn_distance": {
                "board_pawn_vector": "+0x3c/+0x40",
                "path_profile": 6,
                "valid_grid_distance": "Manhattan",
                "empty_result": INT_MAX,
            },
            "pawn_fields": {
                "team": "+0xb0",
                "fire": "+0x8d0 byte",
                "runtime_flying": "+0x1314 byte",
                "Ranged": "Lua integer equals 1",
                "AvoidingMines": "Lua boolean",
            },
            "board_is_pawn_team_empty_team_any_result": True,
            "score_positioning_never_queries_team_any": True,
        },
        "observation_carriers": carriers,
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "native_named_bindings_complete": True,
            "native_score_positioning_observation_semantics_complete": True,
            "current_state_carrier_matrix_complete": True,
            "prospective_board_observations_complete": False,
            "direct_dangerous_bridge_carriers_complete": True,
            "runtime_mutated_definition_flags_complete": True,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS) + 1,
            "source_file_count": len(SOURCE_FILES),
            "method_binding_count": len(METHOD_BINDINGS),
            "native_region_count": len(NATIVE_REGIONS),
            "control_window_count": len(CONTROL_WINDOWS),
            "call_edge_count": len(CALL_EDGES),
            "carrier_count": len(carriers),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "native_score_positioning_observation_semantics_complete": True,
            "prospective_board_observations_complete": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def build_enemy_position_observations_boundary(
    content_root: Path, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the exact native observation map after fail-closed verification."""

    if not isinstance(inventory, Mapping):
        raise EnemyPositionObservationsBoundaryError("inventory must be an object")
    if _canonical_sha256(inventory) != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise EnemyPositionObservationsBoundaryError("inventory fields differ")
    _verify_dependencies()
    _verify_source(content_root, inventory)
    raw, image = _read_executable(content_root, inventory)
    _verify_native(raw, image)
    return _expected_shape()


def validate_enemy_position_observations_boundary_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields and replay vectors without external reads."""

    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyPositionObservationsBoundaryError(
            "enemy position observation fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "native_score_positioning_observation_semantics_complete": True,
        "current_state_carrier_matrix_complete": True,
        "prospective_board_observations_complete": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_position_observations_boundary(
    content_root: Path,
    inventory: Mapping[str, Any],
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and validate the committed exact-build artifact."""

    expected = build_enemy_position_observations_boundary(content_root, inventory)
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise EnemyPositionObservationsBoundaryError(
            "enemy position observation map differs from exact-build analysis"
        )
    result = validate_enemy_position_observations_boundary_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_position_observations_boundary(
    value: Mapping[str, Any]
) -> str:
    """Encode a deterministic publication or verification result."""

    if not isinstance(value, Mapping):
        raise EnemyPositionObservationsBoundaryError("value must be an object")
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
