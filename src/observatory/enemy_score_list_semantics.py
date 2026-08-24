"""Replay shipped ``Skill:ScoreList`` and base ``GetTargetScore`` semantics.

The replay starts from projected ``SpaceDamage`` fields and resolved Board/Pawn
predicate observations.  It preserves source branch order, the dead/temp enemy
score reset, instant Time Pod veto, movement-position override, and the base
queued-versus-instant selection without fabricating future Board state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.enemy_candidate_score_boundary import (
    EnemyCandidateScoreBoundaryError,
    validate_enemy_candidate_score_boundary_map_binding,
)
from src.observatory.enemy_score_effect_ancestry import (
    EnemyScoreEffectAncestryError,
    validate_enemy_score_effect_ancestry_binding,
)
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "lua_enemy_score_list_semantics"
REPLAY_KIND = "lua_enemy_score_list_projection_replay"
BASE_REPLAY_KIND = "lua_enemy_base_target_score_projection_replay"
EXPECTED_BUILD_ID = "13725832"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_SCRIPTS_REVISION = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_INVENTORY_CANONICAL_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1
MAX_RECORDS = 4096
MAX_STRING_BYTES = 1 << 20
MAX_EXACT_LUA_NUMBER = 1 << 53


class EnemyScoreListSemanticsError(RuntimeError):
    """Raised when source binding or projected score replay is invalid."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
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
        "role": "Pins native extraction and adjustment of the Lua integer result.",
    },
    {
        "id": "enemy_score_effect_ancestry",
        "path": (
            "data/observatory/callbacks/"
            "windows_build_13725832_31fe35265598_"
            "enemy_score_effect_ancestry.json"
        ),
        "file_sha256": (
            "517c6fe435bc4a5cd6d50acad1693ba6241bb97c41171ab4823e3c87d8b0a179"
        ),
        "canonical_sha256": (
            "720f721d71869bcba25479410e124e666626d2b570c0dd3e5fb00acc50a86887"
        ),
        "role": (
            "Pins base-score dispatch, all active override routes, and the "
            "separation from the native Skill cache materializer."
        ),
    },
)


SOURCE_REGION_SPECS = (
    (
        "base_get_target_score",
        "Skill:GetTargetScore",
        378,
        422,
        "85b370b2d3d9d4284ce94f03844a5047da731a6f4c06a4198a0604561df6d5f4",
    ),
    (
        "is_enemy_helper",
        "isEnemy",
        395,
        126,
        "5d6a6d3148dd983676164d6c2cc633b1f126ee3d7bd56952ead4c1bd31c7a59d",
    ),
    (
        "score_list",
        "Skill:ScoreList",
        400,
        1541,
        "1876b72aa057f9575b53d745725b7372f9f3dc92ce1a0f4614ae71aebe7a223d",
    ),
)


_RECORD_FIELDS = {
    "loc",
    "iDamage",
    "sPawn",
    "is_movement",
    "move_start",
    "move_end",
    "board_is_valid",
    "board_is_pawn_space",
    "target_is_non_grid_structure",
    "target_team",
    "target_is_frozen",
    "target_is_targeted",
    "target_is_dead",
    "target_is_temp_unit",
    "board_is_building",
    "board_is_powered",
    "board_is_pod",
    "positioning_score",
}


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
        raise EnemyScoreListSemanticsError(f"{label} must be Boolean")
    return value


def _require_i32(value: Any, label: str) -> int:
    if type(value) is not int or not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyScoreListSemanticsError(
            f"{label} must be a signed 32-bit integer"
        )
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise EnemyScoreListSemanticsError(f"{label} must be a string")
    if len(value.encode("utf-8")) > MAX_STRING_BYTES:
        raise EnemyScoreListSemanticsError(f"{label} exceeds its byte cap")
    return value


def _normalize_point(value: Any, label: str) -> list[int]:
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemyScoreListSemanticsError(f"{label} must be [x,y]")
    return [
        _require_i32(value[0], f"{label}.x"),
        _require_i32(value[1], f"{label}.y"),
    ]


def _normalize_optional_point(value: Any, label: str) -> list[int] | None:
    return None if value is None else _normalize_point(value, label)


def _require_lua_number(value: Any, label: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise EnemyScoreListSemanticsError(
            f"{label} must be a finite Lua number"
        )
    if abs(value) > MAX_EXACT_LUA_NUMBER:
        raise EnemyScoreListSemanticsError(
            f"{label} leaves the exact Lua-number projection domain"
        )
    return value


def _normalize_optional_lua_number(
    value: Any,
    label: str,
) -> int | float | None:
    return None if value is None else _require_lua_number(value, label)


def _normalize_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RECORD_FIELDS:
        raise EnemyScoreListSemanticsError(
            f"{label} fields differ from the exact projection schema"
        )
    record = {
        "loc": _normalize_point(value["loc"], f"{label}.loc"),
        "iDamage": _require_i32(value["iDamage"], f"{label}.iDamage"),
        "sPawn": _require_string(value["sPawn"], f"{label}.sPawn"),
        "is_movement": _require_bool(
            value["is_movement"], f"{label}.is_movement"
        ),
        "move_start": _normalize_optional_point(
            value["move_start"], f"{label}.move_start"
        ),
        "move_end": _normalize_optional_point(
            value["move_end"], f"{label}.move_end"
        ),
        "board_is_valid": _require_bool(
            value["board_is_valid"], f"{label}.board_is_valid"
        ),
        "board_is_pawn_space": _require_bool(
            value["board_is_pawn_space"], f"{label}.board_is_pawn_space"
        ),
        "target_is_non_grid_structure": _require_bool(
            value["target_is_non_grid_structure"],
            f"{label}.target_is_non_grid_structure",
        ),
        "target_team": _require_i32(
            value["target_team"], f"{label}.target_team"
        ),
        "target_is_frozen": _require_bool(
            value["target_is_frozen"], f"{label}.target_is_frozen"
        ),
        "target_is_targeted": _require_bool(
            value["target_is_targeted"], f"{label}.target_is_targeted"
        ),
        "target_is_dead": _require_bool(
            value["target_is_dead"], f"{label}.target_is_dead"
        ),
        "target_is_temp_unit": _require_bool(
            value["target_is_temp_unit"], f"{label}.target_is_temp_unit"
        ),
        "board_is_building": _require_bool(
            value["board_is_building"], f"{label}.board_is_building"
        ),
        "board_is_powered": _require_bool(
            value["board_is_powered"], f"{label}.board_is_powered"
        ),
        "board_is_pod": _require_bool(
            value["board_is_pod"], f"{label}.board_is_pod"
        ),
        "positioning_score": _normalize_optional_lua_number(
            value["positioning_score"], f"{label}.positioning_score"
        ),
    }
    if record["is_movement"]:
        if record["move_start"] is None or record["move_end"] is None:
            raise EnemyScoreListSemanticsError(
                f"{label} movement requires start and end points"
            )
    elif record["move_start"] is not None or record["move_end"] is not None:
        raise EnemyScoreListSemanticsError(
            f"{label} non-movement must not supply movement points"
        )
    return record


def _normalize_records(value: Any, label: str) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise EnemyScoreListSemanticsError(f"{label} must be a record array")
    if len(value) > MAX_RECORDS:
        raise EnemyScoreListSemanticsError(f"{label} exceeds its record cap")
    return [
        _normalize_record(record, f"{label}[{index}]")
        for index, record in enumerate(value)
    ]


def _checked_add(
    left: int | float,
    right: int | float,
    label: str,
) -> int | float:
    result = left + right
    if not math.isfinite(result) or abs(result) > MAX_EXACT_LUA_NUMBER:
        raise EnemyScoreListSemanticsError(
            f"{label} leaves the exact Lua-number projection domain"
        )
    return result


def replay_enemy_score_list(
    *,
    records: Sequence[Any],
    queued: bool,
    pawn_space: Sequence[Any],
    pawn_team: int,
    team_none: int,
    score_enemy: int,
    score_friendly_damage: int,
    score_building: int,
    score_nothing: int,
) -> dict[str, Any]:
    """Replay ``Skill:ScoreList`` from resolved projected observations."""

    normalized = _normalize_records(records, "records")
    queued_value = _require_bool(queued, "queued")
    pawn = _normalize_point(pawn_space, "pawn_space")
    pawn_team_value = _require_i32(pawn_team, "pawn_team")
    team_none_value = _require_i32(team_none, "team_none")
    weights = {
        "score_enemy": _require_i32(score_enemy, "score_enemy"),
        "score_friendly_damage": _require_i32(
            score_friendly_damage, "score_friendly_damage"
        ),
        "score_building": _require_i32(score_building, "score_building"),
        "score_nothing": _require_i32(score_nothing, "score_nothing"),
    }

    score = 0
    position_score = 0
    trace: list[dict[str, Any]] = []
    for index, record in enumerate(normalized):
        moving_from_pawn = (
            record["is_movement"] and record["move_start"] == pawn
        )
        outer_gate = record["board_is_valid"] or moving_from_pawn
        step = {
            "index": index,
            "loc": record["loc"],
            "moving_from_pawn": moving_from_pawn,
            "outer_gate": outer_gate,
            "branch": "invalid_skip",
            "score_before": score,
            "position_score_before": position_score,
        }
        needs_positioning = outer_gate and record["is_movement"]
        if needs_positioning != (record["positioning_score"] is not None):
            raise EnemyScoreListSemanticsError(
                f"records[{index}].positioning_score presence differs from source call"
            )
        if not outer_gate:
            step["score_after"] = score
            step["position_score_after"] = position_score
            trace.append(step)
            continue

        damage = record["iDamage"]
        if record["is_movement"]:
            step["branch"] = "movement_position"
            position_score = _checked_add(
                position_score,
                record["positioning_score"],
                "position score",
            )
        elif record["board_is_pawn_space"] and record[
            "target_is_non_grid_structure"
        ]:
            step["branch"] = "non_grid_structure"
            score = _checked_add(score, weights["score_building"], "score")
        elif record["target_team"] == pawn_team_value and damage > 0:
            if record["target_is_frozen"] and not record["target_is_targeted"]:
                step["branch"] = "friendly_frozen_untargeted"
                score = _checked_add(score, weights["score_enemy"], "score")
            else:
                step["branch"] = "friendly_damage"
                score = _checked_add(
                    score,
                    weights["score_friendly_damage"],
                    "score",
                )
        elif (
            record["target_team"] != team_none_value
            and pawn_team_value != team_none_value
            and record["target_team"] != pawn_team_value
        ):
            if record["target_is_dead"] or record["target_is_temp_unit"]:
                step["branch"] = "enemy_dead_or_temp_reset"
                score = weights["score_nothing"]
            else:
                step["branch"] = "enemy_live"
                score = _checked_add(score, weights["score_enemy"], "score")
        elif (
            record["board_is_building"]
            and record["board_is_powered"]
            and damage > 0
        ):
            step["branch"] = "powered_building_damage"
            score = _checked_add(score, weights["score_building"], "score")
        elif (
            record["board_is_pod"]
            and not queued_value
            and (damage > 0 or record["sPawn"] != "")
        ):
            step["branch"] = "instant_pod_veto"
            step["score_after"] = -100
            step["position_score_after"] = position_score
            trace.append(step)
            return {
                "schema_version": SCHEMA_VERSION,
                "kind": REPLAY_KIND,
                "queued": queued_value,
                "record_count": len(normalized),
                "trace": trace,
                "ordinary_score": score,
                "position_score": position_score,
                "position_override": False,
                "early_return": "instant_pod_veto",
                "result": -100,
            }
        else:
            step["branch"] = "nothing"
            score = _checked_add(score, weights["score_nothing"], "score")
        step["score_after"] = score
        step["position_score_after"] = position_score
        trace.append(step)

    position_override = position_score < -5
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REPLAY_KIND,
        "queued": queued_value,
        "record_count": len(normalized),
        "trace": trace,
        "ordinary_score": score,
        "position_score": position_score,
        "position_override": position_override,
        "early_return": None,
        "result": position_score if position_override else score,
    }


def replay_enemy_base_target_score(
    *,
    effect_records: Sequence[Any],
    q_effect_records: Sequence[Any],
    pawn_space: Sequence[Any],
    pawn_team: int,
    team_none: int,
    score_enemy: int,
    score_friendly_damage: int,
    score_building: int,
    score_nothing: int,
) -> dict[str, Any]:
    """Replay shipped base ``Skill:GetTargetScore`` evaluation order."""

    common = {
        "pawn_space": pawn_space,
        "pawn_team": pawn_team,
        "team_none": team_none,
        "score_enemy": score_enemy,
        "score_friendly_damage": score_friendly_damage,
        "score_building": score_building,
        "score_nothing": score_nothing,
    }
    q_score = replay_enemy_score_list(
        records=q_effect_records,
        queued=True,
        **common,
    )
    instant_score = replay_enemy_score_list(
        records=effect_records,
        queued=False,
        **common,
    )
    q_empty = q_score["record_count"] == 0
    if instant_score["result"] < -20:
        branch = "instant_below_minus_twenty"
        result = -100
    elif q_empty:
        branch = "empty_q_effect_uses_instant"
        result = instant_score["result"]
    else:
        branch = "nonempty_q_effect_uses_queued"
        result = q_score["result"]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": BASE_REPLAY_KIND,
        "evaluation_order": ["q_effect", "effect"],
        "q_effect": q_score,
        "effect": instant_score,
        "q_effect_empty": q_empty,
        "selected_branch": branch,
        "result": result,
    }


def _record(
    *,
    loc: tuple[int, int] = (2, 3),
    damage: int = 1,
    pawn: str = "",
    movement: bool = False,
    move_start: tuple[int, int] | None = None,
    move_end: tuple[int, int] | None = None,
    valid: bool = True,
    pawn_space: bool = False,
    non_grid: bool = False,
    team: int = 0,
    frozen: bool = False,
    targeted: bool = False,
    dead: bool = False,
    temp: bool = False,
    building: bool = False,
    powered: bool = False,
    pod: bool = False,
    positioning: int | float | None = None,
) -> dict[str, Any]:
    return {
        "loc": list(loc),
        "iDamage": damage,
        "sPawn": pawn,
        "is_movement": movement,
        "move_start": None if move_start is None else list(move_start),
        "move_end": None if move_end is None else list(move_end),
        "board_is_valid": valid,
        "board_is_pawn_space": pawn_space,
        "target_is_non_grid_structure": non_grid,
        "target_team": team,
        "target_is_frozen": frozen,
        "target_is_targeted": targeted,
        "target_is_dead": dead,
        "target_is_temp_unit": temp,
        "board_is_building": building,
        "board_is_powered": powered,
        "board_is_pod": pod,
        "positioning_score": positioning,
    }


def _score_input(records: list[dict[str, Any]], queued: bool = False) -> dict[str, Any]:
    return {
        "records": records,
        "queued": queued,
        "pawn_space": [4, 5],
        "pawn_team": 6,
        "team_none": 0,
        "score_enemy": 5,
        "score_friendly_damage": -2,
        "score_building": 5,
        "score_nothing": 0,
    }


def _replay_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    cases = [
        (
            "invalid_record_is_skipped",
            _score_input([_record(valid=False)]),
        ),
        (
            "frozen_untargeted_friend_scores_as_enemy",
            _score_input([_record(team=6, frozen=True)]),
        ),
        (
            "dead_enemy_resets_accumulated_score",
            _score_input(
                [
                    _record(team=1),
                    _record(loc=(3, 3), team=1, dead=True),
                ]
            ),
        ),
        (
            "instant_pod_veto",
            _score_input([_record(team=0, pod=True)]),
        ),
        (
            "movement_position_overrides_ordinary_score",
            _score_input(
                [
                    _record(team=1),
                    _record(
                        loc=(5, 5),
                        movement=True,
                        move_start=(4, 5),
                        move_end=(5, 5),
                        valid=False,
                        positioning=-6,
                    ),
                ]
            ),
        ),
        (
            "fractional_movement_sum_preserves_lua_number",
            _score_input(
                [
                    _record(
                        movement=True,
                        move_start=(4, 5),
                        move_end=(3, 5),
                        positioning=-10,
                    ),
                    _record(
                        loc=(5, 5),
                        movement=True,
                        move_start=(4, 5),
                        move_end=(5, 5),
                        positioning=4.5,
                    ),
                ]
            ),
        ),
    ]
    for vector_id, payload in cases:
        vectors.append(
            {
                "id": vector_id,
                "replay": "score_list",
                "input": payload,
                "expected": replay_enemy_score_list(**payload),
            }
        )

    base_payload = {
        "effect_records": [_record(team=6)],
        "q_effect_records": [_record(team=1)],
        "pawn_space": [4, 5],
        "pawn_team": 6,
        "team_none": 0,
        "score_enemy": 5,
        "score_friendly_damage": -30,
        "score_building": 5,
        "score_nothing": 0,
    }
    vectors.append(
        {
            "id": "instant_catastrophe_overrides_nonempty_queue",
            "replay": "base_target_score",
            "input": base_payload,
            "expected": replay_enemy_base_target_score(**base_payload),
        }
    )
    return vectors


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "source_path": "scripts/global.lua",
            "symbol": symbol,
            "line": line,
            "body_size": size,
            "body_sha256": digest,
        }
        for region_id, symbol, line, size, digest in SOURCE_REGION_SPECS
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "score_list_branch_order_is_exact",
            "classification": "fact",
            "claim": (
                "Each valid or source-moving record checks movement, non-grid "
                "structure, friendly damage, enemy, powered building, instant Pod, "
                "then ScoreNothing in that order."
            ),
        },
        {
            "id": "dead_or_temp_enemy_resets_score",
            "classification": "fact",
            "claim": (
                "A hostile dead or temporary Pawn assigns score=ScoreNothing; it "
                "does not add ScoreNothing and can erase prior accumulated score."
            ),
        },
        {
            "id": "frozen_friend_can_score_as_enemy",
            "classification": "fact",
            "claim": (
                "Positive damage to a same-team Frozen target that is not already "
                "targeted adds ScoreEnemy instead of ScoreFriendlyDamage."
            ),
        },
        {
            "id": "instant_pod_veto_is_ordered_and_queued_exempt",
            "classification": "fact",
            "claim": (
                "An otherwise unmatched Pod record returns -100 immediately only "
                "for the instant vector and positive damage or nonempty sPawn."
            ),
        },
        {
            "id": "movement_position_below_minus_five_overrides_score",
            "classification": "fact",
            "claim": (
                "Movement ScorePositioning Lua numbers, including half-points, "
                "accumulate separately; a final total below -5 replaces the "
                "ordinary list score."
            ),
        },
        {
            "id": "base_target_score_evaluates_queue_then_instant",
            "classification": "fact",
            "claim": (
                "Base GetTargetScore scores q_effect first and effect second, returns "
                "-100 when instant score is below -20, otherwise returns instant only "
                "for an empty q_effect and queued score for every nonempty q_effect."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "score_positioning_body",
            "question": "How are the projected movement positioning scores computed?",
            "static_status": (
                "ScoreList call placement and threshold are exact; ScorePositioning "
                "remains an explicit resolved input to this replay."
            ),
        },
        {
            "id": "prospective_board_observations",
            "question": "Can all conditional Board/Pawn observations be known prospectively?",
            "static_status": (
                "The strict replay consumes explicit observations but the ordinary "
                "bridge does not serialize a future candidate tournament."
            ),
        },
        {
            "id": "custom_score_callbacks",
            "question": "Are all 19 non-base score definitions pure replayable?",
            "static_status": (
                "Their ancestry is classified, but their callback-specific Board "
                "logic remains separate from this base ScoreList artifact."
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
                "role": "Pins the exact global.lua bytes and scripts revision.",
            }
        ],
        "source_regions": _source_records(),
        "contracts": {
            "record_order": "input vector order",
            "outer_gate": "Board:IsValid(loc) or movement starts at Pawn:GetSpace()",
            "branch_order": [
                "movement_position",
                "non_grid_structure",
                "friendly_damage",
                "enemy",
                "powered_building_damage",
                "instant_pod_veto",
                "nothing",
            ],
            "enemy_helper": (
                "both teams differ and neither equals the projected TEAM_NONE"
            ),
            "movement_position_override": "sum < -5",
            "instant_catastrophe_gate": "instant_score < -20 => -100",
            "base_vector_choice": (
                "empty q_effect uses instant; nonempty q_effect uses queued"
            ),
            "numeric_scope": (
                "damage, teams, and score weights are signed 32-bit; positioning "
                "values and accumulators are exact finite Lua numbers within 2^53"
            ),
            "score_positioning_is_projected_input": True,
            "future_board_state_is_not_fabricated": True,
        },
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "score_list_projection_complete": True,
            "base_get_target_score_projection_complete": True,
            "score_positioning_complete": False,
            "prospective_board_observations_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS) + 1,
            "source_region_count": len(SOURCE_REGION_SPECS),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "score_list_projection_complete": True,
            "base_get_target_score_projection_complete": True,
            "score_positioning_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _read_repo_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EnemyScoreListSemanticsError(f"not a regular dependency: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyScoreListSemanticsError(f"dependency is not an object: {path}")
    return value


def _verify_dependencies() -> None:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyScoreListSemanticsError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_repo_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyScoreListSemanticsError(
                f"dependency fields differ: {spec['id']}"
            )
        values[spec["id"]] = value
    try:
        validate_enemy_candidate_score_boundary_map_binding(
            values["enemy_candidate_score_boundary"]
        )
        validate_enemy_score_effect_ancestry_binding(
            values["enemy_score_effect_ancestry"]
        )
    except (EnemyCandidateScoreBoundaryError, EnemyScoreEffectAncestryError) as exc:
        raise EnemyScoreListSemanticsError(
            f"dependency binding differs: {exc}"
        ) from exc


def _verify_source(content_root: Path, inventory: Mapping[str, Any]) -> None:
    if not isinstance(inventory, Mapping):
        raise EnemyScoreListSemanticsError("inventory must be an object")
    if _canonical_sha256(inventory) != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise EnemyScoreListSemanticsError("inventory fields differ")
    entries = inventory["content"]["scripts"]["files"]
    entry = next(
        (item for item in entries if item.get("path") == "scripts/global.lua"),
        None,
    )
    if entry is None:
        raise EnemyScoreListSemanticsError("global.lua inventory entry is absent")
    try:
        text = read_exact_inventory_file(
            content_root,
            PurePosixPath("scripts/global.lua"),
            expected_size=entry.get("size"),
            expected_sha256=entry.get("sha256"),
        )
        masked = mask_lua_opaque(text)
        spans = lua_function_spans(masked)
    except WeaponCoverageError as exc:
        raise EnemyScoreListSemanticsError(f"global.lua differs: {exc}") from exc
    for region_id, symbol, line, size, digest in SOURCE_REGION_SPECS:
        prefix = f"function {symbol}"
        matches = [
            (start, end)
            for start, end in spans
            if text.startswith(prefix, start)
        ]
        if len(matches) != 1:
            raise EnemyScoreListSemanticsError(
                f"source function boundary differs: {region_id}"
            )
        start, end = matches[0]
        raw = text[start:end].encode("utf-8")
        if (
            text.count("\n", 0, start) + 1 != line
            or len(raw) != size
            or hashlib.sha256(raw).hexdigest() != digest
        ):
            raise EnemyScoreListSemanticsError(
                f"source function differs: {region_id}"
            )


def build_enemy_score_list_semantics(
    content_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact source artifact after verifying dependencies and bytes."""
    _verify_dependencies()
    _verify_source(content_root, inventory)
    return _expected_shape()


def validate_enemy_score_list_semantics_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields and replay vectors without external reads."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyScoreListSemanticsError("enemy score-list fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "score_list_projection_complete": True,
        "base_get_target_score_projection_complete": True,
        "score_positioning_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_score_list_semantics(
    content_root: Path,
    inventory: Mapping[str, Any],
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject source, dependency, or replay drift."""
    expected = build_enemy_score_list_semantics(content_root, inventory)
    if dict(value) != expected:
        raise EnemyScoreListSemanticsError(
            "enemy score-list map differs from exact source analysis"
        )
    result = validate_enemy_score_list_semantics_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_score_list_semantics(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
