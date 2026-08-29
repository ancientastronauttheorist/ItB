"""Replay shipped ``ScorePositioning`` from explicit projected observations.

The Lua function is exact, including its short-circuit order, hard-coded stock
edges, asymmetric team selection, and half-point melee distance results.  The
native enemy candidate path is kept separate: its named integer invoker reaches
the pinned Lua 5.1 ``lua_tointeger`` implementation, whose x87 ``fistp`` result
depends on the active thread rounding-control mode.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.enemy_candidate_score_boundary import (
    EnemyCandidateScoreBoundaryError,
    validate_enemy_candidate_score_boundary_map_binding,
)
from src.observatory.enemy_position_score_helpers_boundary import (
    EnemyPositionScoreHelpersBoundaryError,
    validate_enemy_position_score_helpers_boundary_binding,
)
from src.observatory.enemy_position_observations_boundary import (
    EnemyPositionObservationsBoundaryError,
    validate_enemy_position_observations_boundary_binding,
)
from src.observatory.enemy_score_list_semantics import (
    EnemyScoreListSemanticsError,
    validate_enemy_score_list_semantics_binding,
)
from src.observatory.pe_anchor_map import PEAnchorError, PEImage
from src.observatory.pe_boundary_map import (
    PEBoundaryError,
    validate_pe_boundary_map,
)
from src.observatory.piston_setup_boundary import (
    PistonSetupBoundaryError,
    validate_piston_setup_boundary_map_binding,
)
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "lua_enemy_score_positioning_semantics"
REPLAY_KIND = "lua_enemy_score_positioning_projection_replay"
NATIVE_INTEGER_REPLAY_KIND = "native_lua_integer_x87_replay"
EXPECTED_BUILD_ID = "13725832"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_LUA_DLL_SHA256 = (
    "0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14"
)
EXPECTED_SCRIPTS_REVISION = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_INVENTORY_CANONICAL_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1
X87_ROUNDING_MODES = (
    "nearest_even",
    "down",
    "up",
    "toward_zero",
)


class EnemyScorePositioningSemanticsError(RuntimeError):
    """Raised when source binding or projected positioning replay is invalid."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
    {
        "id": "enemy_position_score_helpers_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_position_score_helpers_boundary.json"
        ),
        "file_sha256": (
            "989c2d74194b810e14ae8327b17cbaa9535a8ec83acedefad951bc9ad77c8ff9"
        ),
        "canonical_sha256": (
            "9f572158d5e8dc760974166a4ad6a21f68a68324d0ec6d97eb6f8d02d4fa3cd9"
        ),
        "role": (
            "Pins both native Pawn helper registrations/call paths and the "
            "unmodified shipped ScoreDanger=-10 / PositionScore=0 defaults."
        ),
    },
    {
        "id": "enemy_position_observations_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_position_observations_boundary.json"
        ),
        "file_sha256": (
            "8f0ab10d21a7fef4a4076ff2fc15ea7de7eb4892456f98cdb6b6ff0df92d4000"
        ),
        "canonical_sha256": (
            "c63820e6cf3bba78a3b010f7d478959aed2ff93faeb0be5c358a90c0b7621103"
        ),
        "role": (
            "Pins the exact native Board/Pawn observations consumed by "
            "ScorePositioning and distinguishes exact current carriers from "
            "candidate-time state that is not serialized."
        ),
    },
    {
        "id": "enemy_score_list_semantics",
        "path": (
            "data/observatory/callbacks/"
            "windows_build_13725832_31fe35265598_"
            "enemy_score_list_semantics.json"
        ),
        "file_sha256": (
            "a990c1ae3648618651c65096339a8a5f24d44407c422324c8cf43ac30dab11a6"
        ),
        "canonical_sha256": (
            "4871a8f128211e258f6737b2c221e5f73789a021a95ecd995e5d5a3a86566d60"
        ),
        "role": (
            "Pins the exact Lua-to-Lua consumer, including fractional movement "
            "accumulation and the strict below-minus-five cutoff."
        ),
    },
    {
        "id": "enemy_candidate_score_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_candidate_score_boundary.json"
        ),
        "file_sha256": (
            "c94f87833efafec1217eefd0b5aeef61dd79e46fb3c1255c558259af64596ad0"
        ),
        "canonical_sha256": (
            "c0eeed00ebb646371d3ca33cac9d1c52224bb67025d1b6e6fa41a74115a7a457"
        ),
        "role": "Pins the native post-ScorePositioning clamp and integer input.",
    },
    {
        "id": "reviewed_pe_boundaries",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_pe_boundaries.json"
        ),
        "file_sha256": (
            "a7c5bf375245ba058d59d3c92b73557b3620be4bf4bfae586acd36b59da3f2b3"
        ),
        "canonical_sha256": (
            "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        ),
        "role": (
            "Pins the ScorePositioning wrapper, named integer invoker, and "
            "their direct call edge."
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
        "role": "Pins DIR_START=0 and DIR_END=3 for the exact build.",
    },
)


SOURCE_REGION = {
    "id": "score_positioning",
    "source_path": "scripts/global.lua",
    "symbol": "ScorePositioning",
    "line": 446,
    "body_size": 2075,
    "body_sha256": (
        "320210ee36aaf90a77e661e33e5c162bd9734066479f5b4052ec23276f9dfff5"
    ),
}


NATIVE_REGIONS = (
    {
        "id": "score_positioning_wrapper",
        "image": "Breach.exe",
        "start_rva": "0x000f7870",
        "size": 124,
        "sha256": (
            "9794db437203d18af0ce5245bc178f537e20f715b192c671cc7ecde7d279a42a"
        ),
        "meaning": (
            "Calls the named integer invoker for ScorePositioning after its "
            "separate native eligibility checks."
        ),
    },
    {
        "id": "named_integer_invoker",
        "image": "Breach.exe",
        "start_rva": "0x000f8770",
        "size": 259,
        "sha256": (
            "59607f3c4741577e11c570b31aeb3dfaadec00d85ec8a69e024a7f06760e584e"
        ),
        "meaning": "Looks up the actual callback and extracts a Lua integer.",
    },
    {
        "id": "lua_tointeger",
        "image": "lua5.1.dll",
        "start_rva": "0x000016d0",
        "size": 125,
        "sha256": (
            "2d935d28eefdd86c2035f20567820a17c7bc0b9941b5343bf3475fcf7c30b2ab"
        ),
        "conversion_instruction_hex": "dd45f0db5de4",
        "conversion_instructions": [
            "fld qword ptr [ebp-0x10]",
            "fistp dword ptr [ebp-0x1c]",
        ],
        "meaning": (
            "Loads the Lua double and converts it with x87 FISTP under the "
            "thread's active rounding-control mode."
        ),
    },
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


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EnemyScorePositioningSemanticsError(f"{label} must be Boolean")
    return value


def _require_optional_bool(value: Any, label: str) -> bool | None:
    return None if value is None else _require_bool(value, label)


def _require_i32(value: Any, label: str) -> int:
    if type(value) is not int or not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyScorePositioningSemanticsError(
            f"{label} must be a signed 32-bit integer"
        )
    return value


def _require_optional_i32(value: Any, label: str) -> int | None:
    return None if value is None else _require_i32(value, label)


def _point(value: Any, label: str) -> list[int]:
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemyScorePositioningSemanticsError(f"{label} must be [x,y]")
    return [
        _require_i32(value[0], f"{label}.x"),
        _require_i32(value[1], f"{label}.y"),
    ]


def _optional_bool_vector(value: Any, label: str) -> list[bool] | None:
    if value is None:
        return None
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 4
    ):
        raise EnemyScorePositioningSemanticsError(
            f"{label} must be a four-entry Boolean array or null"
        )
    return [_require_bool(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _exact_number(numerator: int, denominator: int = 1) -> dict[str, Any]:
    if denominator not in (1, 2) or numerator < SIGNED_MIN or numerator > -SIGNED_MIN:
        raise EnemyScorePositioningSemanticsError("invalid exact replay number")
    if denominator == 2 and numerator % 2 == 0:
        numerator //= 2
        denominator = 1
    value: int | float = (
        numerator if denominator == 1 else numerator / denominator
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
    }


def _x87_round(numerator: int, denominator: int, mode: str) -> int:
    if mode not in X87_ROUNDING_MODES:
        raise EnemyScorePositioningSemanticsError(
            "x87_rounding_mode must be nearest_even, down, up, or toward_zero"
        )
    if denominator not in (1, 2):
        raise EnemyScorePositioningSemanticsError(
            "denominator must be one or two"
        )
    if mode == "down":
        result = numerator // denominator
    elif mode == "up":
        result = -((-numerator) // denominator)
    elif mode == "toward_zero":
        result = (
            numerator // denominator
            if numerator >= 0
            else -((-numerator) // denominator)
        )
    else:
        sign = -1 if numerator < 0 else 1
        quotient, remainder = divmod(abs(numerator), denominator)
        if remainder * 2 > denominator or (
            remainder * 2 == denominator and quotient % 2 == 1
        ):
            quotient += 1
        result = sign * quotient
    if not SIGNED_MIN <= result <= SIGNED_MAX:
        raise EnemyScorePositioningSemanticsError(
            "x87 integer result leaves signed 32-bit replay domain"
        )
    return result


def replay_score_positioning_native_integer(
    *,
    numerator: int,
    denominator: int,
    x87_rounding_mode: str,
) -> dict[str, Any]:
    """Replay the pinned ``lua_tointeger`` FISTP conversion parametrically."""

    numerator_value = _require_i32(numerator, "numerator")
    if type(denominator) is not int or denominator not in (1, 2):
        raise EnemyScorePositioningSemanticsError(
            "denominator must be one or two"
        )
    if type(x87_rounding_mode) is not str:
        raise EnemyScorePositioningSemanticsError(
            "x87_rounding_mode must be text"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": NATIVE_INTEGER_REPLAY_KIND,
        "input": {
            "numerator": numerator_value,
            "denominator": denominator,
        },
        "x87_rounding_mode": x87_rounding_mode,
        "result": _x87_round(
            numerator_value,
            denominator,
            x87_rounding_mode,
        ),
    }


def _finish(
    *,
    point: list[int],
    branch: str,
    numerator: int,
    denominator: int = 1,
    selected_enemy_team: str | None,
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    exact = _exact_number(numerator, denominator)
    conversions = {
        mode: _x87_round(exact["numerator"], exact["denominator"], mode)
        for mode in X87_ROUNDING_MODES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REPLAY_KIND,
        "point": point,
        "selected_enemy_team": selected_enemy_team,
        "selected_branch": branch,
        "trace": trace,
        "lua_result_exact": exact,
        "lua_result": exact["value"],
        "native_integer_by_x87_mode": conversions,
    }


def replay_enemy_score_positioning(
    *,
    point: Sequence[Any],
    board_is_pod: bool,
    terrain_is_hole: bool,
    pawn_is_flying: bool,
    board_is_targeted: bool,
    pawn_danger_score: int | None,
    board_is_smoke: bool,
    board_is_fire: bool,
    pawn_is_fire: bool,
    board_is_spawning: bool,
    board_is_dangerous: bool,
    board_is_dangerous_item: bool,
    pawn_is_avoiding_mines: bool,
    terrain_is_water: bool,
    pawn_custom_position_score: int | None,
    pawn_team_is_player: bool | None,
    pawn_is_ranged: bool | None,
    adjacent_selected_enemy_pawn: Sequence[Any] | None,
    adjacent_building: Sequence[Any] | None,
    distance_to_selected_enemy_pawn: int | None,
    distance_to_building: int | None,
) -> dict[str, Any]:
    """Replay shipped ``ScorePositioning`` from explicit predicate results."""

    location = _point(point, "point")
    pod = _require_bool(board_is_pod, "board_is_pod")
    hole = _require_bool(terrain_is_hole, "terrain_is_hole")
    flying = _require_bool(pawn_is_flying, "pawn_is_flying")
    targeted = _require_bool(board_is_targeted, "board_is_targeted")
    danger = _require_optional_i32(pawn_danger_score, "pawn_danger_score")
    smoke = _require_bool(board_is_smoke, "board_is_smoke")
    fire = _require_bool(board_is_fire, "board_is_fire")
    pawn_fire = _require_bool(pawn_is_fire, "pawn_is_fire")
    spawning = _require_bool(board_is_spawning, "board_is_spawning")
    dangerous = _require_bool(board_is_dangerous, "board_is_dangerous")
    dangerous_item = _require_bool(
        board_is_dangerous_item,
        "board_is_dangerous_item",
    )
    avoids_mines = _require_bool(
        pawn_is_avoiding_mines,
        "pawn_is_avoiding_mines",
    )
    water = _require_bool(terrain_is_water, "terrain_is_water")
    custom = _require_optional_i32(
        pawn_custom_position_score,
        "pawn_custom_position_score",
    )
    player_team = _require_optional_bool(
        pawn_team_is_player,
        "pawn_team_is_player",
    )
    ranged = _require_optional_bool(pawn_is_ranged, "pawn_is_ranged")
    adjacent_pawns = _optional_bool_vector(
        adjacent_selected_enemy_pawn,
        "adjacent_selected_enemy_pawn",
    )
    adjacent_buildings = _optional_bool_vector(
        adjacent_building,
        "adjacent_building",
    )
    pawn_distance = _require_optional_i32(
        distance_to_selected_enemy_pawn,
        "distance_to_selected_enemy_pawn",
    )
    building_distance = _require_optional_i32(
        distance_to_building,
        "distance_to_building",
    )
    if pawn_distance is not None and pawn_distance < 0:
        raise EnemyScorePositioningSemanticsError(
            "distance_to_selected_enemy_pawn must be nonnegative"
        )
    if building_distance is not None and building_distance < 0:
        raise EnemyScorePositioningSemanticsError(
            "distance_to_building must be nonnegative"
        )
    trace: list[dict[str, Any]] = []

    def no_late_inputs(*, allow_danger: bool = False, allow_custom: bool = False) -> None:
        if (danger is not None) != allow_danger:
            raise EnemyScorePositioningSemanticsError(
                "pawn_danger_score presence differs from source call"
            )
        if (custom is not None) != allow_custom:
            raise EnemyScorePositioningSemanticsError(
                "pawn_custom_position_score presence differs from source call"
            )
        if any(
            item is not None
            for item in (
                player_team,
                ranged,
                adjacent_pawns,
                adjacent_buildings,
                pawn_distance,
                building_distance,
            )
        ):
            raise EnemyScorePositioningSemanticsError(
                "late positioning inputs are present before their source calls"
            )

    trace.append({"call": "Board:IsPod", "result": pod})
    if pod:
        no_late_inputs()
        return _finish(
            point=location,
            branch="pod",
            numerator=-100,
            selected_enemy_team=None,
            trace=trace,
        )

    trace.append({"call": "Board:GetTerrain==TERRAIN_HOLE", "result": hole})
    if hole and not flying:
        no_late_inputs()
        return _finish(
            point=location,
            branch="grounded_hole",
            numerator=-10,
            selected_enemy_team=None,
            trace=trace,
        )

    trace.append({"call": "Board:IsTargeted", "result": targeted})
    if targeted:
        no_late_inputs(allow_danger=True)
        return _finish(
            point=location,
            branch="targeted_danger_score",
            numerator=danger,
            selected_enemy_team=None,
            trace=trace
            + [{"call": "Pawn:GetDangerScore", "result": danger}],
        )
    if danger is not None:
        raise EnemyScorePositioningSemanticsError(
            "pawn_danger_score presence differs from source call"
        )

    for call, result, branch, score in (
        ("Board:IsSmoke", smoke, "smoke", -2),
        ("Board:IsFire AND NOT Pawn:IsFire", fire and not pawn_fire, "new_fire", -10),
        ("Board:IsSpawning", spawning, "spawning", -10),
        ("Board:IsDangerous", dangerous, "dangerous", -10),
        (
            "Board:IsDangerousItem AND Pawn:IsAvoidingMines",
            dangerous_item and avoids_mines,
            "dangerous_item_avoided",
            -10,
        ),
        (
            "terrain==TERRAIN_WATER AND NOT Pawn:IsFlying",
            water and not flying,
            "grounded_water",
            -5,
        ),
    ):
        trace.append({"call": call, "result": result})
        if result:
            no_late_inputs()
            return _finish(
                point=location,
                branch=branch,
                numerator=score,
                selected_enemy_team=None,
                trace=trace,
            )

    if custom is None:
        raise EnemyScorePositioningSemanticsError(
            "pawn_custom_position_score presence differs from source call"
        )
    trace.append({"call": "Pawn:GetCustomPositionScore", "result": custom})
    if custom != 0:
        if any(
            item is not None
            for item in (
                player_team,
                ranged,
                adjacent_pawns,
                adjacent_buildings,
                pawn_distance,
                building_distance,
            )
        ):
            raise EnemyScorePositioningSemanticsError(
                "late positioning inputs are present before their source calls"
            )
        return _finish(
            point=location,
            branch="custom_nonzero",
            numerator=custom,
            selected_enemy_team=None,
            trace=trace,
        )

    edge_x = location[0] in (0, 7)
    edge_y = location[1] in (0, 7)
    trace.append({"operation": "hardcoded_edge_test", "edge_x": edge_x, "edge_y": edge_y})
    if edge_x and edge_y:
        if any(
            item is not None
            for item in (
                player_team,
                ranged,
                adjacent_pawns,
                adjacent_buildings,
                pawn_distance,
                building_distance,
            )
        ):
            raise EnemyScorePositioningSemanticsError(
                "late positioning inputs are present before their source calls"
            )
        return _finish(
            point=location,
            branch="stock_corner",
            numerator=-2,
            selected_enemy_team=None,
            trace=trace,
        )
    if edge_x or edge_y:
        if any(
            item is not None
            for item in (
                player_team,
                ranged,
                adjacent_pawns,
                adjacent_buildings,
                pawn_distance,
                building_distance,
            )
        ):
            raise EnemyScorePositioningSemanticsError(
                "late positioning inputs are present before their source calls"
            )
        return _finish(
            point=location,
            branch="stock_edge",
            numerator=0,
            selected_enemy_team=None,
            trace=trace,
        )

    if player_team is None or ranged is None:
        raise EnemyScorePositioningSemanticsError(
            "interior positioning requires team and ranged observations"
        )
    selected_team = "TEAM_ENEMY" if player_team else "TEAM_PLAYER"
    trace.append(
        {
            "call": "Pawn:GetTeam",
            "pawn_team_is_player": player_team,
            "selected_enemy_team": selected_team,
        }
    )
    trace.append({"call": "Pawn:IsRanged", "result": ranged})
    if ranged:
        if any(
            item is not None
            for item in (
                adjacent_pawns,
                adjacent_buildings,
                pawn_distance,
                building_distance,
            )
        ):
            raise EnemyScorePositioningSemanticsError(
                "melee-only inputs are present for a ranged source branch"
            )
        return _finish(
            point=location,
            branch="ranged_interior",
            numerator=5,
            selected_enemy_team=selected_team,
            trace=trace,
        )

    if adjacent_pawns is None or adjacent_buildings is None:
        raise EnemyScorePositioningSemanticsError(
            "melee positioning requires four ordered adjacency observations"
        )
    for direction in range(4):
        pawn_match = adjacent_pawns[direction]
        trace.append(
            {
                "call": "Board:IsPawnTeam",
                "direction_offset": direction,
                "selected_enemy_team": selected_team,
                "result": pawn_match,
            }
        )
        if pawn_match:
            if pawn_distance is not None or building_distance is not None:
                raise EnemyScorePositioningSemanticsError(
                    "distance inputs are present before their source calls"
                )
            return _finish(
                point=location,
                branch="melee_adjacent_enemy_pawn",
                numerator=5,
                selected_enemy_team=selected_team,
                trace=trace,
            )
        building_match = adjacent_buildings[direction]
        trace.append(
            {
                "call": "Board:IsBuilding",
                "direction_offset": direction,
                "result": building_match,
            }
        )
        if building_match:
            if pawn_distance is not None or building_distance is not None:
                raise EnemyScorePositioningSemanticsError(
                    "distance inputs are present before their source calls"
                )
            return _finish(
                point=location,
                branch="melee_adjacent_building",
                numerator=5,
                selected_enemy_team=selected_team,
                trace=trace,
            )

    if pawn_distance is None or building_distance is None:
        raise EnemyScorePositioningSemanticsError(
            "nonadjacent melee positioning requires both distance observations"
        )
    closest = min(pawn_distance, building_distance)
    numerator = max(0, 10 - closest)
    trace.extend(
        [
            {"call": "Board:GetDistanceToPawn", "result": pawn_distance},
            {"call": "Board:GetDistanceToBuilding", "result": building_distance},
            {
                "operation": "math.max(0,(10-min(distance_pawn,distance_building))/2)",
                "closest": closest,
                "numerator": numerator,
                "denominator": 2,
            },
        ]
    )
    return _finish(
        point=location,
        branch="melee_distance",
        numerator=numerator,
        denominator=2,
        selected_enemy_team=selected_team,
        trace=trace,
    )


def _base_input(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "point": [3, 3],
        "board_is_pod": False,
        "terrain_is_hole": False,
        "pawn_is_flying": False,
        "board_is_targeted": False,
        "pawn_danger_score": None,
        "board_is_smoke": False,
        "board_is_fire": False,
        "pawn_is_fire": False,
        "board_is_spawning": False,
        "board_is_dangerous": False,
        "board_is_dangerous_item": False,
        "pawn_is_avoiding_mines": False,
        "terrain_is_water": False,
        "pawn_custom_position_score": 0,
        "pawn_team_is_player": False,
        "pawn_is_ranged": True,
        "adjacent_selected_enemy_pawn": None,
        "adjacent_building": None,
        "distance_to_selected_enemy_pawn": None,
        "distance_to_building": None,
    }
    value.update(overrides)
    return value


def _replay_vectors() -> list[dict[str, Any]]:
    cases = [
        ("pod_precedes_everything", _base_input(board_is_pod=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("grounded_hole", _base_input(terrain_is_hole=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("targeted_uses_danger_score", _base_input(board_is_targeted=True, pawn_danger_score=-7, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("smoke_precedes_fire", _base_input(board_is_smoke=True, board_is_fire=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("new_fire", _base_input(board_is_fire=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("dangerous_item_requires_avoidance", _base_input(board_is_dangerous_item=True, pawn_is_avoiding_mines=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("grounded_water_is_minus_five", _base_input(terrain_is_water=True, pawn_custom_position_score=None, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("custom_precedes_edge", _base_input(point=[0, 0], pawn_custom_position_score=8, pawn_team_is_player=None, pawn_is_ranged=None)),
        ("stock_corner", _base_input(point=[0, 7], pawn_team_is_player=None, pawn_is_ranged=None)),
        ("stock_edge", _base_input(point=[0, 3], pawn_team_is_player=None, pawn_is_ranged=None)),
        ("ranged_interior", _base_input()),
        (
            "nonplayer_melee_adjacent_pawn_selects_player_team",
            _base_input(
                pawn_is_ranged=False,
                adjacent_selected_enemy_pawn=[False, True, False, False],
                adjacent_building=[False, False, False, False],
            ),
        ),
        (
            "melee_adjacent_building",
            _base_input(
                pawn_is_ranged=False,
                adjacent_selected_enemy_pawn=[False, False, False, False],
                adjacent_building=[False, False, True, False],
            ),
        ),
        (
            "melee_odd_distance_returns_half_point",
            _base_input(
                pawn_is_ranged=False,
                adjacent_selected_enemy_pawn=[False, False, False, False],
                adjacent_building=[False, False, False, False],
                distance_to_selected_enemy_pawn=3,
                distance_to_building=8,
            ),
        ),
    ]
    return [
        {
            "id": vector_id,
            "input": payload,
            "expected": replay_enemy_score_positioning(**payload),
        }
        for vector_id, payload in cases
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "hazard_short_circuit_order_is_exact",
            "classification": "fact",
            "claim": (
                "Pod, grounded Hole, targeted danger, Smoke, new Fire, spawning, "
                "generic danger, avoided dangerous item, and grounded Water "
                "short-circuit in that order."
            ),
        },
        {
            "id": "acid_penalty_is_inactive",
            "classification": "fact",
            "claim": (
                "The only Board:IsAcid positioning line is commented out, so the "
                "shipped function deliberately applies no ACID penalty."
            ),
        },
        {
            "id": "custom_score_precedes_stock_edges",
            "classification": "fact",
            "claim": (
                "A nonzero Pawn custom score returns before the hard-coded x/y "
                "zero-or-seven corner and edge policy."
            ),
        },
        {
            "id": "enemy_team_selection_is_binary",
            "classification": "fact",
            "claim": (
                "TEAM_PLAYER selects TEAM_ENEMY; every other Pawn team selects "
                "TEAM_PLAYER, matching the source's explicit black/white caveat."
            ),
        },
        {
            "id": "melee_adjacency_order_is_exact",
            "classification": "fact",
            "claim": (
                "For each of four DIR_START-through-DIR_END slots, melee scoring "
                "checks selected-team Pawn first and Building second, returning "
                "five at the first match."
            ),
        },
        {
            "id": "melee_distance_preserves_half_points",
            "classification": "fact",
            "claim": (
                "Without adjacency, melee scoring returns max(0,(10-min(Pawn "
                "distance,Building distance))/2) as a Lua number, so odd "
                "differences remain half-points in direct Lua callers."
            ),
        },
        {
            "id": "ranged_interior_returns_five",
            "classification": "fact",
            "claim": "A ranged Pawn that reaches the interior tail returns five.",
        },
        {
            "id": "stock_pawn_score_helpers_resolve_to_inherited_defaults",
            "classification": "fact",
            "claim": (
                "The exact native Pawn helpers dispatch generated GetScoreDanger "
                "and GetPositionScore methods. Unmodified shipped Pawn definitions "
                "inherit ScoreDanger=-10 and PositionScore=0 with no explicit "
                "getter or field override in the shipped Lua corpus."
            ),
        },
        {
            "id": "native_integer_rounding_depends_on_x87_control",
            "classification": "fact",
            "claim": (
                "The native named integer route reaches lua_tointeger, whose exact "
                "pinned DLL body converts the double with x87 FISTP; the four-mode "
                "replay therefore requires the active thread rounding mode."
            ),
        },
        {
            "id": "native_observation_boundaries_and_current_carriers_are_exact",
            "classification": "fact",
            "claim": (
                "Every named Board/Pawn observation used by ScorePositioning "
                "is pinned to its exact-build native binding and implementation. "
                "The current bridge carries or exactly derives most current-state "
                "values, while native dangerous flags/effects and a future "
                "candidate-time Board snapshot remain explicit inputs."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "x87_rounding_mode_at_callback",
            "question": "Which x87 rounding-control mode is active at each native callback?",
            "static_status": (
                "The call-local wrapper and lua_tointeger bodies are exact, but "
                "the thread control word is runtime state rather than an image constant."
            ),
        },
        {
            "id": "runtime_or_modded_pawn_score_mutation",
            "question": "Can runtime code or a mod replace either inherited Pawn score value/getter?",
            "static_status": (
                "The native dispatch and unmodified shipped defaults are exact. "
                "Runtime mutation and non-inventoried mods remain outside the "
                "immutable stock-content claim."
            ),
        },
        {
            "id": "prospective_board_observations",
            "question": "Can every candidate Board predicate and distance be known prospectively?",
            "static_status": (
                "The native meanings and current-state carrier matrix are exact, "
                "but ordinary bridge state does not serialize the Board snapshot "
                "at each future candidate callback in the native tournament."
            ),
        },
        {
            "id": "complete_enemy_phase_forecast",
            "question": "Can this local replay replace the authoritative settled queue?",
            "static_status": (
                "No; target/effect construction, custom score callbacks, movement "
                "candidates, shared RNG, and complete records remain external."
            ),
        },
    ]


def _expected_shape() -> dict[str, Any]:
    vectors = _replay_vectors()
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "lua5_1_sha256": EXPECTED_LUA_DLL_SHA256,
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION,
        },
        "dependencies": [dict(spec) for spec in DEPENDENCY_SPECS]
        + [
            {
                "id": "accepted_local_inventory",
                "path": (
                    "data/observatory/inventories/"
                    "windows_build_13725832_31fe35265598_local_modified.json"
                ),
                "canonical_sha256": EXPECTED_INVENTORY_CANONICAL_SHA256,
                "role": "Pins exact source, executable, and Lua DLL bytes.",
            }
        ],
        "source_regions": [dict(SOURCE_REGION)],
        "native_regions": [dict(region) for region in NATIVE_REGIONS],
        "contracts": {
            "source_branch_order": [
                "pod",
                "grounded_hole",
                "targeted_danger_score",
                "smoke",
                "new_fire",
                "spawning",
                "dangerous",
                "dangerous_item_avoided",
                "grounded_water",
                "custom_nonzero",
                "stock_corner",
                "stock_edge",
                "melee_or_ranged_tail",
            ],
            "inactive_source_branch": "commented Board:IsAcid penalty",
            "stock_edge_coordinates": [0, 7],
            "melee_direction_slots": [0, 1, 2, 3],
            "melee_per_direction_call_order": [
                "Board:IsPawnTeam",
                "Board:IsBuilding",
            ],
            "melee_distance_expression": (
                "max(0,(10-min(distance_to_selected_enemy_pawn,"
                "distance_to_building))/2)"
            ),
            "direct_lua_consumer_preserves_fraction": True,
            "native_integer_api": "lua_tointeger",
            "native_conversion_instruction": "x87 FISTP dword",
            "native_integer_rounding_modes": list(X87_ROUNDING_MODES),
            "native_integer_rounding_mode_is_runtime_input": True,
            "unmodified_shipped_danger_score": -10,
            "unmodified_shipped_custom_position_score": 0,
            "stock_helper_defaults_require_runtime_rounding_mode": False,
            "native_board_predicate_semantics_complete": True,
            "current_state_carrier_matrix_complete": True,
            "candidate_time_board_snapshot_is_input": True,
            "future_board_state_is_not_fabricated": True,
        },
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "score_positioning_projection_complete": True,
            "lua_fractional_result_complete": True,
            "native_integer_conversion_parametric_complete": True,
            "x87_rounding_mode_observed": False,
            "native_pawn_score_helpers_complete": True,
            "unmodified_shipped_pawn_score_defaults_complete": True,
            "native_board_predicate_semantics_complete": True,
            "current_state_carrier_matrix_complete": True,
            "prospective_board_observations_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS) + 1,
            "source_region_count": 1,
            "native_region_count": len(NATIVE_REGIONS),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "score_positioning_projection_complete": True,
            "native_integer_conversion_parametric_complete": True,
            "x87_rounding_mode_observed": False,
            "native_pawn_score_helpers_complete": True,
            "native_board_predicate_semantics_complete": True,
            "current_state_carrier_matrix_complete": True,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _read_repo_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EnemyScorePositioningSemanticsError(
            f"not a regular dependency: {path}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyScorePositioningSemanticsError(
            f"dependency is not an object: {path}"
        )
    return value


def _verify_dependencies(content_root: Path, inventory: Mapping[str, Any]) -> None:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyScorePositioningSemanticsError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_repo_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyScorePositioningSemanticsError(
                f"dependency fields differ: {spec['id']}"
            )
        values[spec["id"]] = value
    try:
        validate_enemy_score_list_semantics_binding(
            values["enemy_score_list_semantics"]
        )
        validate_enemy_position_score_helpers_boundary_binding(
            values["enemy_position_score_helpers_boundary"]
        )
        validate_enemy_position_observations_boundary_binding(
            values["enemy_position_observations_boundary"]
        )
        validate_enemy_candidate_score_boundary_map_binding(
            values["enemy_candidate_score_boundary"]
        )
        validate_piston_setup_boundary_map_binding(
            values["piston_setup_boundary"]
        )
        validate_pe_boundary_map(
            content_root / "Breach.exe",
            values["reviewed_pe_boundaries"],
            inventory=inventory,
        )
    except (
        EnemyScoreListSemanticsError,
        EnemyPositionScoreHelpersBoundaryError,
        EnemyPositionObservationsBoundaryError,
        EnemyCandidateScoreBoundaryError,
        PistonSetupBoundaryError,
        PEBoundaryError,
    ) as exc:
        raise EnemyScorePositioningSemanticsError(
            f"dependency binding differs: {exc}"
        ) from exc


def _verify_source(content_root: Path, inventory: Mapping[str, Any]) -> None:
    if not isinstance(inventory, Mapping):
        raise EnemyScorePositioningSemanticsError("inventory must be an object")
    if _canonical_sha256(inventory) != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise EnemyScorePositioningSemanticsError("inventory fields differ")
    try:
        entries = inventory["content"]["scripts"]["files"]
        entry = next(
            item for item in entries if item.get("path") == "scripts/global.lua"
        )
        text = read_exact_inventory_file(
            content_root,
            PurePosixPath("scripts/global.lua"),
            expected_size=entry.get("size"),
            expected_sha256=entry.get("sha256"),
        )
        spans = lua_function_spans(mask_lua_opaque(text))
    except (KeyError, StopIteration, TypeError, WeaponCoverageError) as exc:
        raise EnemyScorePositioningSemanticsError(
            f"global.lua inventory/source differs: {exc}"
        ) from exc
    prefix = "function ScorePositioning"
    matches = [(start, end) for start, end in spans if text.startswith(prefix, start)]
    if len(matches) != 1:
        raise EnemyScorePositioningSemanticsError(
            "ScorePositioning function boundary differs"
        )
    start, end = matches[0]
    raw = text[start:end].encode("utf-8")
    if (
        text.count("\n", 0, start) + 1 != SOURCE_REGION["line"]
        or len(raw) != SOURCE_REGION["body_size"]
        or hashlib.sha256(raw).hexdigest() != SOURCE_REGION["body_sha256"]
    ):
        raise EnemyScorePositioningSemanticsError(
            "ScorePositioning source body differs"
        )


def _verify_lua_integer_region(content_root: Path, inventory: Mapping[str, Any]) -> None:
    try:
        entry = next(
            item
            for item in inventory["native_libraries"]
            if item.get("path") == "lua5.1.dll"
        )
    except (KeyError, StopIteration, TypeError) as exc:
        raise EnemyScorePositioningSemanticsError(
            "lua5.1.dll inventory entry differs"
        ) from exc
    path = content_root / "lua5.1.dll"
    if path.is_symlink() or not path.is_file():
        raise EnemyScorePositioningSemanticsError(
            "lua5.1.dll is not a regular non-symlink file"
        )
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != before.st_size
        or len(raw) != entry.get("size")
        or hashlib.sha256(raw).hexdigest() != entry.get("sha256")
        or entry.get("sha256") != EXPECTED_LUA_DLL_SHA256
    ):
        raise EnemyScorePositioningSemanticsError(
            "lua5.1.dll differs from the accepted inventory"
        )
    try:
        image = PEImage(raw)
        offset = image.rva_span_to_file_offset(0x000016D0, 125)
    except PEAnchorError as exc:
        raise EnemyScorePositioningSemanticsError(
            f"lua5.1.dll PE differs: {exc}"
        ) from exc
    if offset is None:
        raise EnemyScorePositioningSemanticsError(
            "lua_tointeger region is not mapped"
        )
    body = raw[offset : offset + 125]
    if (
        hashlib.sha256(body).hexdigest()
        != NATIVE_REGIONS[2]["sha256"]
        or bytes.fromhex(NATIVE_REGIONS[2]["conversion_instruction_hex"])
        not in body
    ):
        raise EnemyScorePositioningSemanticsError(
            "lua_tointeger conversion body differs"
        )


def build_enemy_score_positioning_semantics(
    content_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact source/native join after verifying all pinned bytes."""

    _verify_source(content_root, inventory)
    _verify_dependencies(content_root, inventory)
    _verify_lua_integer_region(content_root, inventory)
    return _expected_shape()


def validate_enemy_score_positioning_semantics_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields and replay vectors without external reads."""

    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyScorePositioningSemanticsError(
            "enemy ScorePositioning fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "score_positioning_projection_complete": True,
        "native_integer_conversion_parametric_complete": True,
        "x87_rounding_mode_observed": False,
        "native_pawn_score_helpers_complete": True,
        "native_board_predicate_semantics_complete": True,
        "current_state_carrier_matrix_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_score_positioning_semantics(
    content_root: Path,
    inventory: Mapping[str, Any],
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and reject source, native-library, dependency, or replay drift."""

    expected = build_enemy_score_positioning_semantics(content_root, inventory)
    if dict(value) != expected:
        raise EnemyScorePositioningSemanticsError(
            "enemy ScorePositioning map differs from exact analysis"
        )
    result = validate_enemy_score_positioning_semantics_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_score_positioning_semantics(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
