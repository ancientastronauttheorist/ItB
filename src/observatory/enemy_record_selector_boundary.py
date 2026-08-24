"""Reproduce the exact-build native enemy record-selection tournament.

Windows build 13725832 materializes one 24-byte record for each accepted
enemy destination, then performs a second tournament over those records.
This module binds the reviewed producer, comparator, and RNG branches to the
pinned executable and replays the selector from its two honest boundaries:

* ordered post-callback target scores plus the CRT state immediately before a
  positive-best target tie; and
* ordered 24-byte candidate records plus the CRT state immediately before the
  record selector.

Lua/native callback evaluation and any RNG consumed while those records are
being materialized remain boundary inputs.  The ordinary solver still trusts
the settled live enemy queue rather than forecasting this hidden tournament.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.msvc_rng_replay import canonical_observable_state, draw
from src.observatory.path_cost_ordering import validate_path_cost_ordering_map
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
    validate_pe_boundary_map,
)
from src.observatory.rng_return_map import (
    _scan_rng_calls,
    validate_rng_return_map,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_record_selector_boundary_map"
REPLAY_ANALYSIS_KIND = "native_enemy_record_selector_replay"
TARGET_REPLAY_ANALYSIS_KIND = "native_enemy_target_tie_replay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_RNG_CALL_COUNT = 118
RNG_CORE_RVA = 0x00387F16
STOCK_BOARD_WIDTH = 8
STOCK_BOARD_HEIGHT = 8
FALLBACK_HARDCODED_MAX_COORDINATE = 7
MAX_REPLAY_RECORDS = 4096
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1


class EnemyRecordSelectorBoundaryError(RuntimeError):
    """Raised when the exact enemy record boundary cannot reproduce."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
    {
        "id": "identity_inventory",
        "path": (
            "data/observatory/inventories/"
            "windows_build_13725832_31fe35265598_local_modified.json"
        ),
        "file_sha256": (
            "319e24045af4ef52814e43b564bd0bfb31cc94c43949b4e4cd9d10d873e6e90f"
        ),
        "canonical_sha256": (
            "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
        ),
        "role": "Pins the Steam build and exact PE identity used by the base boundary validators.",
    },
    {
        "id": "pe_boundaries",
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
            "Pins the AI orchestrator, candidate loop, record selector, callback "
            "wrappers, selected-record copy, and shared RNG core."
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
            "Pins all 118 raw direct calls to the shared CRT core and stable IDs "
            "29 through 33 for the target and record tournaments."
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
            "Pins native unit-cost reachability and the returned point vector's "
            "lexicographic x-then-y order before the AI-specific filter."
        ),
    },
)


REGION_SPECS = (
    (
        "ai_orchestrator",
        0x000F6390,
        0x000F6B74,
        "f788de533a9e841719e4611a646afccb11ac950835e379fa70296c24f98e9bb4",
        "Enemy planning orchestrator containing the selected 24-byte record copy.",
    ),
    (
        "record_seed",
        0x000F77B0,
        0x000F7861,
        "5d2584690702b34d171a9c2b0fd0447ad3b5366b2505d970ad328ffe6b0e4db4",
        "Sequential destination-to-record driver through RET 0x08.",
    ),
    (
        "score_positioning",
        0x000F7870,
        0x000F78EC,
        "9794db437203d18af0ce5245bc178f537e20f715b192c671cc7ecde7d279a42a",
        "Enemy ScorePositioning wrapper.",
    ),
    (
        "candidate_loop",
        0x000F78F0,
        0x000F7C17,
        "a162b5ead3bfcb851bf99f31b204485769570deb38fb6eb8102040214bcfc064",
        "Per-destination target tournament and 24-byte record append.",
    ),
    (
        "movement_candidates",
        0x000F7C20,
        0x000F7DCD,
        "4aec4d865b7b82ebc4602f83680461a57e50f0f81615dfeacc5c910e35b3672d",
        "Reachable destination acquisition, in-place filtering, and current-tile append.",
    ),
    (
        "record_selector",
        0x000F7DD0,
        0x000F817F,
        "ab07271dab17b1f63227885cd1d1560ca227a85588f18915f477864b3f2ec8fe",
        "Complete 24-byte record comparator, tie draw, fallback gate, and return.",
    ),
    (
        "record_vector_append",
        0x000F8450,
        0x000F84DD,
        "36df4007aafc94bac75fca5db6537e875aaf3513393848cee5b831bce42b4e58",
        "One-record 0x18-byte vector append.",
    ),
    (
        "record_vector_assign",
        0x000F84E0,
        0x000F864A,
        "f841cf6db3d379bf9a3d80f89f4cc7a542bc761d09b48f6d66be65784b35beb5",
        "24-byte vector assignment used to retain the displaced primary group.",
    ),
    (
        "record_vector_grow",
        0x000F8650,
        0x000F86D9,
        "a1724473a44e04a2bec4721499f6db347597d05939f6cc575ed5fa5b9cd96c30",
        "24-byte record vector growth helper.",
    ),
    (
        "fallback_random_remove",
        0x000F8880,
        0x000F88E4,
        "c1b2fc21f4341c477514c8b616e0d1cd5dc0794171c190c8b6c5ef84f358b2cc",
        "Random fallback record copy-and-remove helper through RET.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "record_seed_order",
        "record_seed",
        0x000F77D8,
        "0000000f1f4400008b7e188d04dd000000008b4e2803f8e89cb713008b4e2450ff77048b01ff378b4014ffd084c075278b4e288d04dd000000008b7e188d54241003f8528b01ff50288b0f3b0875238b4f043b4804751b8b46188d0cdd00000000ff740804ff34088bceff7508e8a60000008b461c432b46",
        "Consume the destination vector sequentially and invoke one candidate build for each accepted point.",
    ),
    (
        "target_tournament",
        "candidate_loop",
        0x000F7AA8,
        "8b45c82b45c4c1f8038945ec85c00f847c0000008b75c490ff7604ff36518b4f2852e8510013008b4f288b914809000083faff74178b41082b4104c1f8033bd07c0ac7814809000000000000ff7604ff36ffb1480900008b4f28e8091813008b4d083bc17c160f4f5dd08d4dd056895dd4894508e85fd5fbff8b5dd483c608836dec0174088b4d108b550ceb8b8b75d88b4f286a01ff75e0ff75dce8688613008b4dd03bcb7433837d08007e2d2bd9c1fb0385db750433d2eb08e8af03290099f7fb8b5dd08b4d08894dbc8b04d38945b48b44d3048945b8eb068b4dbc8b5dd0",
        "Accumulate equal maximum post-wrapper target scores from an initial best of zero and draw only when the maximum is positive.",
    ),
    (
        "interior_flag_and_record_append",
        "candidate_loop",
        0x000F7B88,
        "837de8008b57247426837de40074208b4248483945e874178b424c483945e4740e85c97e0a837dc0007c04c64714018d45ac508d4f08e88d0800008b4f286a01ff75e0ff75dce8dd851300",
        "Set the interior-favorable flag for positive-target/nonnegative-position records and append the complete record.",
    ),
    (
        "movement_reachability_filter_append",
        "movement_candidates",
        0x000F7CE5,
        "e8661b14008bcbff7004ff30e89ab213008b4f2450568d44242c50e8db6afdff8d5f18508bcbe8a089feff8b4c241c85c974158b4424242bc16a08c1f8035051e8d6faf0ff83c40c8b430433c92b03c1f803894c240c85c07470908b3b8d04cd000000008b4d0803f8894424148b4424108b40248b30e830b2130050ff77048b460cff378b7c241c8b4f24ffd084c074248b03034424148b4b048d50082bca515250e8f46727008b4c241883c40c834304f849eb048b4c240c8b4304412b03c1f803894c240c3bc872918b4f288d542414528b01ff5028508bcbe8bcd2fbff",
        "Acquire native reachability, preserve returned order while filtering in place, then append the pawn's current point.",
    ),
    (
        "selector_scan_and_compare",
        "record_selector",
        0x000F7E53,
        "33c9894de88b53088b7b2403d1833a008b4a04741485c974108b474848390274088b474c483bc8750a807b14000f8596000000837a14f60f8c8c0000003b75f0746d8b7a1485ff79078b4e1485c97f1c8b4e1485c9790485ff7f1d8b42103b461075023bf90f9fc084c0750c8b42103b461075553bf975518bc785c0790485c97f2d85c9790485c07f138b52108b76103bd675023bc10f9fc084c074128d45d4508d4dc8e8e40500008b45d48945d88b43088d4dd40345e850e83f0500008b7dd88b75d4897df0eb038b7df0",
        "Apply the interior and -10 gates, compare records, retain ties, and replace the fallback with the displaced primary group on each strict improvement.",
    ),
    (
        "selector_primary_draw",
        "record_selector",
        0x000F7F49,
        "3bf70f84ab0100002bfeb8abaaaa2af7efc1fa028bfac1ef1f03fa750433d2eb08e8a7ff280099f7ff8b5dc88d04520f100cc6f30f7e44c6100f114db8660fd645e4",
        "Choose one primary record with raw rand modulo count; every nonempty primary group reaches the draw.",
    ),
    (
        "selector_fallback_gate_and_loop",
        "record_selector",
        0x000F7F8B,
        "3b5dcc0f84f6000000e87dff2800250300008079054883c8fc400f85db0000008d55c88d4d90e8ca0800008b75cc8bc68b5dc82bc3f30f7e45a00f104d908945e00f1f40008b7da08b55a48b4d948b459085ff7e1685d2781285c0740e85c9740a83f807740583f907756c3bde7468b8abaaaa2af76de0c1fa028bfac1ef1f03fa750433d2eb08e8fffe280099f7ff8d04528bce0f1004c38d04c38d50182bca510f1145a852f30f7e401050660fd645ece83f6527000f104da883c40c83ee18f30f7e45ec836de0180f114d90660fd645a0e96effffff8b75d485ff7e1d85d2781985c0741585c9741183f807740c83f9077407660fd645e4eb040f104db8",
        "Spend the 1-in-4 fallback gate, sample the displaced group without replacement, and accept only a positive-target/nonnegative-position stock-interior record.",
    ),
    (
        "selector_empty_default",
        "record_selector",
        0x000F80FC,
        "8b5ddc8b4dd08b7dc80f280500d88300eb0433db33c98b45080f1100f30f7e45a066",
        "Return the exact no-selection record without an RNG draw when no primary record survives.",
    ),
    (
        "fallback_random_remove",
        "fallback_random_remove",
        0x000F8880,
        "5356578bfab8abaaaa2a8bd98b77042b37f7eec1fa028bf2c1ee1f03f2750433d2eb08e86ef6280099f7fe8b078d0c52c1e1030f1004010f1103f30f7e44011003c18b4f04660fd643108d50182bca515250e8a95c2700834704e883c40c8bc35f5e5bc3",
        "Choose one 24-byte fallback record with raw rand modulo count, copy it, remove it, and shrink the vector.",
    ),
)


DIRECT_EDGE_SPECS = (
    ("seed_builds_candidate", "record_seed", 0x000F7845, "e8a6000000", 0x000F78F0),
    ("candidate_gets_target_area", "candidate_loop", 0x000F7A14, "e817181300", 0x00229230),
    ("candidate_scores_position", "candidate_loop", 0x000F7A45, "e826feffff", 0x000F7870),
    ("candidate_prepares_target", "candidate_loop", 0x000F7ACA, "e851001300", 0x00227B20),
    ("candidate_scores_target", "candidate_loop", 0x000F7B02, "e809181300", 0x00229310),
    ("candidate_target_tie_rng", "candidate_loop", 0x000F7B62, "e8af032900", RNG_CORE_RVA),
    ("candidate_appends_record", "candidate_loop", 0x000F7BBE, "e88d080000", 0x000F8450),
    ("movement_gets_reachable", "movement_candidates", 0x000F7D00, "e8db6afdff", 0x000CE7E0),
    ("movement_moves_point_vector", "movement_candidates", 0x000F7D0B, "e8a089feff", 0x000E06B0),
    ("movement_appends_current", "movement_candidates", 0x000F7DBF, "e8bcd2fbff", 0x000B5080),
    ("selector_copies_displaced_primary", "record_selector", 0x000F7EF7, "e8e4050000", 0x000F84E0),
    ("selector_appends_primary", "record_selector", 0x000F7F0C, "e83f050000", 0x000F8450),
    ("selector_primary_rng", "record_selector", 0x000F7F6A, "e8a7ff2800", RNG_CORE_RVA),
    ("selector_fallback_gate_rng", "record_selector", 0x000F7F94, "e87dff2800", RNG_CORE_RVA),
    ("selector_first_fallback_remove", "record_selector", 0x000F7FB1, "e8ca080000", 0x000F8880),
    ("selector_later_fallback_rng", "record_selector", 0x000F8012, "e8fffe2800", RNG_CORE_RVA),
    ("fallback_remove_rng", "fallback_random_remove", 0x000F88A3, "e86ef62800", RNG_CORE_RVA),
)


DATA_ANCHOR_SPECS = (
    (
        "candidate_target_default",
        0x0043CE90,
        "ffffffffffffffff0000000000000000",
        "Per-destination target defaults are (-1,-1,0,0).",
    ),
    (
        "no_selection_record",
        0x0043D800,
        "ffffffffffffffffffffffffffffffff0000000000000000",
        "The empty selector returns (-1,-1,-1,-1,0,0).",
    ),
)


RNG_ROLE_SPECS = (
    (29, 0x000F7B62, "candidate_target_tie", "One draw for any positive equal-best target group, including a singleton."),
    (30, 0x000F7F6A, "selector_primary", "One draw for every nonempty primary record group, including a singleton."),
    (31, 0x000F7F94, "selector_fallback_gate", "One draw whose low two bits gate fallback exploration at remainder zero."),
    (32, 0x000F8012, "selector_later_fallback_remove", "One draw for each fallback removal after the helper's first removal."),
    (33, 0x000F88A3, "selector_first_fallback_remove", "One draw in the copy-and-remove helper for the first fallback attempt."),
)


RECORD_FIELDS = (
    "destination_x",
    "destination_y",
    "target_x",
    "target_y",
    "target_score",
    "positioning_score",
)
TARGET_FIELDS = ("x", "y", "score")
DEFAULT_RECORD = {
    "destination_x": -1,
    "destination_y": -1,
    "target_x": -1,
    "target_y": -1,
    "target_score": 0,
    "positioning_score": 0,
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EnemyRecordSelectorBoundaryError(
            f"dependency is not a regular non-symlink file: {path}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyRecordSelectorBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemyRecordSelectorBoundaryError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise EnemyRecordSelectorBoundaryError("reviewed direct edge is not CALL rel32")
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def _require_signed(value: Any, label: str) -> int:
    if type(value) is not int or not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyRecordSelectorBoundaryError(
            f"{label} must be a signed 32-bit integer"
        )
    return value


def _require_state(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise EnemyRecordSelectorBoundaryError(
            "RNG state must be a 32-bit unsigned integer"
        )
    return value


def _require_dimension(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= SIGNED_MAX:
        raise EnemyRecordSelectorBoundaryError(
            f"{label} must be a positive signed 32-bit integer"
        )
    return value


def _normalize_record(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(RECORD_FIELDS):
        raise EnemyRecordSelectorBoundaryError(
            f"{label} fields must be exactly {list(RECORD_FIELDS)}"
        )
    return {field: _require_signed(value[field], f"{label}.{field}") for field in RECORD_FIELDS}


def _normalize_records(values: Any) -> list[dict[str, int]]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EnemyRecordSelectorBoundaryError("records must be an array")
    if len(values) > MAX_REPLAY_RECORDS:
        raise EnemyRecordSelectorBoundaryError("record count exceeds replay limit")
    return [_normalize_record(value, f"records[{index}]") for index, value in enumerate(values)]


def _normalize_targets(values: Any) -> list[dict[str, int]]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EnemyRecordSelectorBoundaryError("targets must be an array")
    if len(values) > MAX_REPLAY_RECORDS:
        raise EnemyRecordSelectorBoundaryError("target count exceeds replay limit")
    result: list[dict[str, int]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping) or set(value) != set(TARGET_FIELDS):
            raise EnemyRecordSelectorBoundaryError(
                f"targets[{index}] fields must be exactly {list(TARGET_FIELDS)}"
            )
        result.append(
            {field: _require_signed(value[field], f"targets[{index}].{field}") for field in TARGET_FIELDS}
        )
    return result


def _dynamic_interior(record: Mapping[str, int], width: int, height: int) -> bool:
    return (
        record["destination_x"] != 0
        and record["destination_y"] != 0
        and record["destination_x"] != width - 1
        and record["destination_y"] != height - 1
    )


def _fallback_accepts(record: Mapping[str, int]) -> bool:
    return (
        record["target_score"] > 0
        and record["positioning_score"] >= 0
        and record["destination_x"] != 0
        and record["destination_y"] != 0
        and record["destination_x"] != FALLBACK_HARDCODED_MAX_COORDINATE
        and record["destination_y"] != FALLBACK_HARDCODED_MAX_COORDINATE
    )


def compare_enemy_records(left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
    """Return -1, 0, or 1 using the native selector's ranking relation."""
    first = _normalize_record(left, "left")
    second = _normalize_record(right, "right")
    left_position = first["positioning_score"]
    right_position = second["positioning_score"]
    if left_position < 0 < right_position:
        return -1
    if right_position < 0 < left_position:
        return 1
    left_key = (first["target_score"], left_position)
    right_key = (second["target_score"], right_position)
    return (left_key > right_key) - (left_key < right_key)


def _draw_event(
    state: int,
    *,
    caller_id: int,
    call_rva: int,
    source: str,
    bound: int,
) -> tuple[int, int, dict[str, Any]]:
    if bound <= 0:
        raise EnemyRecordSelectorBoundaryError("native modulo bound must be positive")
    pre_state = canonical_observable_state(state)
    result, next_state = draw(state)
    index = result % bound
    return index, next_state, {
        "draw_index": 0,
        "source": source,
        "caller_id": caller_id,
        "call_rva": f"0x{call_rva:08x}",
        "canonical_observable_pre_call_state": f"0x{pre_state:08x}",
        "raw_result": result,
        "bound": bound,
        "modulo_result": index,
        "canonical_observable_post_call_state": (
            f"0x{canonical_observable_state(next_state):08x}"
        ),
    }


def replay_enemy_target_tie(
    destination_x: int,
    destination_y: int,
    positioning_score: int,
    targets: Sequence[Mapping[str, Any]],
    rng_state: int,
) -> dict[str, Any]:
    """Build one candidate record from ordered post-wrapper target scores.

    ``rng_state`` is the state at the exact local tie boundary after every
    callback/effect-side draw for this destination has already occurred.
    """
    destination_x = _require_signed(destination_x, "destination_x")
    destination_y = _require_signed(destination_y, "destination_y")
    positioning_score = _require_signed(positioning_score, "positioning_score")
    current_state = _require_state(rng_state)
    normalized = _normalize_targets(targets)
    best_score = 0
    equal_best_indices: list[int] = []
    for index, target in enumerate(normalized):
        score = target["score"]
        if score < best_score:
            continue
        if score > best_score:
            equal_best_indices.clear()
        best_score = score
        equal_best_indices.append(index)

    transcript: list[dict[str, Any]] = []
    selected_target_index: int | None = None
    target_x = -1
    target_y = -1
    stored_score = 0
    if best_score > 0 and equal_best_indices:
        choice, current_state, event = _draw_event(
            current_state,
            caller_id=29,
            call_rva=0x000F7B62,
            source="positive_equal_best_target",
            bound=len(equal_best_indices),
        )
        event["draw_index"] = 1
        transcript.append(event)
        selected_target_index = equal_best_indices[choice]
        selected = normalized[selected_target_index]
        target_x = selected["x"]
        target_y = selected["y"]
        stored_score = best_score

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": TARGET_REPLAY_ANALYSIS_KIND,
        "input_state": f"0x{rng_state:08x}",
        "canonical_observable_pre_call_state": (
            f"0x{canonical_observable_state(rng_state):08x}"
        ),
        "target_count": len(normalized),
        "maximum_score_from_zero": best_score,
        "equal_best_target_indices": equal_best_indices,
        "selected_target_index": selected_target_index,
        "record": {
            "destination_x": destination_x,
            "destination_y": destination_y,
            "target_x": target_x,
            "target_y": target_y,
            "target_score": stored_score,
            "positioning_score": positioning_score,
        },
        "rng_transcript": transcript,
        "draw_count": len(transcript),
        "canonical_observable_final_state": (
            f"0x{canonical_observable_state(current_state):08x}"
        ),
    }


def replay_enemy_record_selector(
    records: Sequence[Mapping[str, Any]],
    rng_state: int,
    *,
    board_width: int = STOCK_BOARD_WIDTH,
    board_height: int = STOCK_BOARD_HEIGHT,
) -> dict[str, Any]:
    """Replay the complete record-level selector from its first local draw."""
    normalized = _normalize_records(records)
    current_state = _require_state(rng_state)
    width = _require_dimension(board_width, "board_width")
    height = _require_dimension(board_height, "board_height")

    interior_favorable = any(
        _dynamic_interior(record, width, height)
        and record["target_score"] > 0
        and record["positioning_score"] >= 0
        for record in normalized
    )
    primary: list[tuple[int, dict[str, int]]] = []
    displaced: list[tuple[int, dict[str, int]]] = []
    eligible_indices: list[int] = []
    rejected: list[dict[str, Any]] = []

    for input_index, record in enumerate(normalized):
        if interior_favorable and not _dynamic_interior(record, width, height):
            rejected.append({"input_index": input_index, "reason": "edge_after_interior_favorable"})
            continue
        if record["positioning_score"] < -10:
            rejected.append({"input_index": input_index, "reason": "positioning_below_minus_ten"})
            continue
        eligible_indices.append(input_index)
        if not primary:
            primary.append((input_index, record))
            continue
        comparison = compare_enemy_records(record, primary[0][1])
        if comparison == 0:
            primary.append((input_index, record))
        elif comparison > 0:
            displaced = list(primary)
            primary = [(input_index, record)]

    transcript: list[dict[str, Any]] = []
    fallback_attempts: list[dict[str, Any]] = []
    primary_selected: tuple[int, dict[str, int]] | None = None
    selected: tuple[int | None, dict[str, int], str]
    fallback_gate_remainder: int | None = None
    fallback_explored = False

    if not primary:
        selected = (None, dict(DEFAULT_RECORD), "default")
    else:
        choice, current_state, event = _draw_event(
            current_state,
            caller_id=30,
            call_rva=0x000F7F6A,
            source="primary_record_group",
            bound=len(primary),
        )
        event["draw_index"] = len(transcript) + 1
        transcript.append(event)
        primary_selected = primary[choice]
        selected = (primary_selected[0], dict(primary_selected[1]), "primary")

        if displaced:
            fallback_gate_remainder, current_state, event = _draw_event(
                current_state,
                caller_id=31,
                call_rva=0x000F7F94,
                source="displaced_primary_gate",
                bound=4,
            )
            event["draw_index"] = len(transcript) + 1
            transcript.append(event)
            if fallback_gate_remainder == 0:
                fallback_explored = True
                remaining = list(displaced)
                first = True
                while remaining:
                    caller_id = 33 if first else 32
                    call_rva = 0x000F88A3 if first else 0x000F8012
                    source = (
                        "first_displaced_primary_remove"
                        if first
                        else "later_displaced_primary_remove"
                    )
                    choice, current_state, event = _draw_event(
                        current_state,
                        caller_id=caller_id,
                        call_rva=call_rva,
                        source=source,
                        bound=len(remaining),
                    )
                    event["draw_index"] = len(transcript) + 1
                    transcript.append(event)
                    candidate = remaining.pop(choice)
                    accepted = _fallback_accepts(candidate[1])
                    fallback_attempts.append(
                        {
                            "attempt_index": len(fallback_attempts) + 1,
                            "input_index": candidate[0],
                            "accepted": accepted,
                        }
                    )
                    if accepted:
                        selected = (
                            candidate[0],
                            dict(candidate[1]),
                            "displaced_primary_fallback",
                        )
                        break
                    first = False

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": REPLAY_ANALYSIS_KIND,
        "input_state": f"0x{rng_state:08x}",
        "canonical_observable_pre_call_state": (
            f"0x{canonical_observable_state(rng_state):08x}"
        ),
        "board_dimensions": [width, height],
        "record_count": len(normalized),
        "interior_favorable": interior_favorable,
        "eligible_input_indices": eligible_indices,
        "rejected_records": rejected,
        "primary_input_indices": [item[0] for item in primary],
        "displaced_primary_input_indices": [item[0] for item in displaced],
        "primary_selected_input_index": (
            None if primary_selected is None else primary_selected[0]
        ),
        "fallback_gate_remainder": fallback_gate_remainder,
        "fallback_explored": fallback_explored,
        "fallback_attempts": fallback_attempts,
        "selected_source": selected[2],
        "selected_input_index": selected[0],
        "selected_record": selected[1],
        "rng_transcript": transcript,
        "draw_count": len(transcript),
        "canonical_observable_final_state": (
            f"0x{canonical_observable_state(current_state):08x}"
        ),
    }


def _dependency_records() -> list[dict[str, str]]:
    return [dict(item) for item in DEPENDENCY_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "evidence_class": "fact",
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": sha256,
            "section": ".text",
            "boundary_basis": basis,
        }
        for region_id, start, end, sha256, basis in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "evidence_class": "fact",
            "region_id": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "evidence_class": "fact",
            "source_region": source_region,
            "from_rva": f"0x{call_rva:08x}",
            "instruction_hex": encoded,
            "target_rva": f"0x{target_rva:08x}",
        }
        for edge_id, source_region, call_rva, encoded, target_rva in DIRECT_EDGE_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "evidence_class": "fact",
            "rva": f"0x{rva:08x}",
            "size": len(bytes.fromhex(encoded)),
            "data_hex": encoded,
            "meaning": meaning,
        }
        for anchor_id, rva, encoded, meaning in DATA_ANCHOR_SPECS
    ]


def _rng_role_records() -> list[dict[str, Any]]:
    return [
        {
            "caller_id": caller_id,
            "call_rva": f"0x{call_rva:08x}",
            "role": role,
            "meaning": meaning,
        }
        for caller_id, call_rva, role, meaning in RNG_ROLE_SPECS
    ]


def _target_vector(
    vector_id: str,
    destination: tuple[int, int],
    position: int,
    targets: list[dict[str, int]],
    state: int,
) -> dict[str, Any]:
    result = replay_enemy_target_tie(
        destination[0], destination[1], position, targets, state
    )
    return {
        "id": vector_id,
        "kind": "target_tie",
        "input": {
            "destination": list(destination),
            "positioning_score": position,
            "targets": targets,
            "rng_state": f"0x{state:08x}",
        },
        "expected": {
            "equal_best_target_indices": result["equal_best_target_indices"],
            "selected_target_index": result["selected_target_index"],
            "record": result["record"],
            "draw_count": result["draw_count"],
            "canonical_observable_final_state": result[
                "canonical_observable_final_state"
            ],
        },
    }


def _selector_vector(
    vector_id: str,
    records: list[dict[str, int]],
    state: int,
) -> dict[str, Any]:
    result = replay_enemy_record_selector(records, state)
    return {
        "id": vector_id,
        "kind": "record_selector",
        "input": {"records": records, "rng_state": f"0x{state:08x}"},
        "expected": {
            "interior_favorable": result["interior_favorable"],
            "eligible_input_indices": result["eligible_input_indices"],
            "primary_input_indices": result["primary_input_indices"],
            "displaced_primary_input_indices": result[
                "displaced_primary_input_indices"
            ],
            "primary_selected_input_index": result[
                "primary_selected_input_index"
            ],
            "fallback_gate_remainder": result["fallback_gate_remainder"],
            "fallback_attempts": result["fallback_attempts"],
            "selected_source": result["selected_source"],
            "selected_input_index": result["selected_input_index"],
            "selected_record": result["selected_record"],
            "draw_count": result["draw_count"],
            "canonical_observable_final_state": result[
                "canonical_observable_final_state"
            ],
        },
    }


def _record(
    destination_x: int,
    destination_y: int,
    target_score: int,
    positioning_score: int,
    *,
    target_x: int = 4,
    target_y: int = 4,
) -> dict[str, int]:
    return {
        "destination_x": destination_x,
        "destination_y": destination_y,
        "target_x": target_x,
        "target_y": target_y,
        "target_score": target_score,
        "positioning_score": positioning_score,
    }


def _replay_vectors() -> list[dict[str, Any]]:
    return [
        _target_vector(
            "target_no_positive",
            (3, 3),
            2,
            [{"x": 1, "y": 1, "score": -2}, {"x": 2, "y": 2, "score": 0}],
            0,
        ),
        _target_vector(
            "target_positive_singleton_draw",
            (3, 3),
            2,
            [{"x": 1, "y": 1, "score": 4}],
            0,
        ),
        _target_vector(
            "target_equal_best_ordered_modulo",
            (3, 3),
            2,
            [{"x": 1, "y": 1, "score": 5}, {"x": 6, "y": 6, "score": 5}],
            1,
        ),
        _selector_vector("selector_empty_no_draw", [], 0),
        _selector_vector("selector_singleton_primary_draw", [_record(3, 3, 5, 0)], 0),
        _selector_vector(
            "selector_equal_primary_ordered_modulo",
            [_record(2, 2, 5, 0), _record(3, 3, 5, 0)],
            1,
        ),
        _selector_vector(
            "selector_positive_position_beats_negative",
            [_record(2, 2, 100, -1), _record(3, 3, 1, 1)],
            0,
        ),
        _selector_vector(
            "selector_fallback_gate_miss",
            [_record(2, 2, 2, 0), _record(3, 3, 3, 0)],
            0,
        ),
        _selector_vector(
            "selector_fallback_gate_hit",
            [_record(2, 2, 2, 0), _record(3, 3, 3, 0)],
            2,
        ),
        _selector_vector(
            "selector_invalid_fallback_exhausted",
            [_record(2, 2, 0, 0), _record(3, 3, 0, 0), _record(4, 4, 1, 0)],
            2,
        ),
        _selector_vector(
            "selector_interior_flag_filters_earlier_edge",
            [_record(0, 2, 99, 3), _record(3, 3, 1, 0)],
            0,
        ),
        _selector_vector(
            "selector_position_cutoff_is_inclusive_minus_ten",
            [_record(2, 2, 99, -11), _record(3, 3, 1, -10)],
            0,
        ),
        _selector_vector(
            "selector_fallback_is_displaced_not_global_second",
            [_record(2, 2, 1, 0), _record(3, 3, 3, 0), _record(4, 4, 2, 0)],
            2,
        ),
    ]


def _contracts() -> dict[str, Any]:
    return {
        "record_layout": {
            "size_bytes": 24,
            "encoding": "six little-endian signed 32-bit integers",
            "fields": [
                {"offset": 0, "name": "destination_x"},
                {"offset": 4, "name": "destination_y"},
                {"offset": 8, "name": "target_x"},
                {"offset": 12, "name": "target_y"},
                {"offset": 16, "name": "target_score"},
                {"offset": 20, "name": "positioning_score"},
            ],
            "candidate_target_default": [-1, -1, 0, 0],
            "empty_selection_default": [-1, -1, -1, -1, 0, 0],
        },
        "destination_order": {
            "reachable_input_order": ["x", "y"],
            "ai_filter_preserves_order": True,
            "current_pawn_tile_appended_after_filtered_reachable": True,
            "record_seed_consumes_sequentially": True,
            "later_edge_destinations_skipped_after_interior_favorable": True,
        },
        "target_tournament": {
            "input_score": "post-native-wrapper GetTargetScore integer",
            "initial_best_score": 0,
            "negative_scores_discarded": True,
            "zero_scores_may_accumulate_but_are_never_selected": True,
            "strict_improvement_clears_equal_best": True,
            "equal_score_preserves_returned_target_order": True,
            "positive_best_draw_even_singleton": True,
            "no_positive_best_draw_count": 0,
            "no_positive_target": [-1, -1],
            "stored_no_positive_score": 0,
            "boundary_state": (
                "CRT state immediately before RVA 0x000f7b62, after all "
                "callback/effect-side draws for that destination"
            ),
        },
        "interior_favorable": {
            "predicate": (
                "runtime-dimension interior destination AND target_score > 0 "
                "AND positioning_score >= 0"
            ),
            "selector_effect": "when true, reject every edge destination including earlier records",
        },
        "record_selector": {
            "scan_order": "original 24-byte record vector order",
            "minimum_positioning_score_inclusive": -10,
            "special_comparison": (
                "strictly positive positioning beats strictly negative positioning "
                "regardless of target score"
            ),
            "ordinary_comparison": ["target_score descending", "positioning_score descending"],
            "ties_preserve_encounter_order": True,
            "strict_improvement_action": (
                "replace the fallback with the entire displaced primary group, "
                "clear primary, then append the improving record"
            ),
            "fallback_is_global_second_best": False,
            "empty_draw_count": 0,
            "primary_draw_even_singleton": True,
            "fallback_gate_modulus": 4,
            "fallback_gate_accept_remainder": 0,
            "fallback_sampling": "uniform raw-rand modulo remaining count without replacement",
            "fallback_acceptance": {
                "target_score_minimum": 1,
                "positioning_score_minimum": 0,
                "destination_coordinates_rejected": [0, 7],
                "hardcoded_stock_max_coordinate": 7,
            },
            "primary_draw_precedes_gate_and_is_not_refunded": True,
        },
        "replay_boundary": {
            "target_inputs": [
                "ordered post-wrapper target coordinates and scores",
                "post-clamp positioning score",
                "observable CRT state at the local positive-best tie boundary",
            ],
            "selector_inputs": [
                "ordered complete 24-byte records",
                "runtime board width and height",
                "observable CRT state immediately before selector primary choice",
            ],
            "parameterized_target_tie_complete": True,
            "parameterized_record_selector_complete": True,
            "upstream_callback_materialization_complete": False,
            "complete_enemy_phase_forecast": False,
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "movement_destination_pipeline",
            "evidence_class": "inference",
            "claim": (
                "The AI destination producer retains native GetReachable order through "
                "an in-place destination filter, appends the pawn's current tile, and "
                "the record driver consumes the resulting points sequentially."
            ),
            "limitations": [
                "Opaque virtual predicate inputs and callback-produced record values remain runtime state."
            ],
        },
        {
            "id": "candidate_record_and_target_tie",
            "evidence_class": "inference",
            "claim": (
                "Each accepted destination produces six signed 32-bit fields. The "
                "target tournament starts at score zero, keeps returned-order equal "
                "maxima, and spends caller-ID 29 once whenever the maximum is positive, "
                "including singleton maxima."
            ),
            "limitations": [
                "Scores are post-wrapper integers; this artifact does not replay Lua or native effect construction."
            ],
        },
        {
            "id": "interior_favorable_short_circuit",
            "evidence_class": "inference",
            "claim": (
                "An interior positive-target/nonnegative-position record sets a sticky "
                "flag. Later edge destinations are not materialized, and the selector "
                "also rejects any earlier edge records."
            ),
            "limitations": ["Interior uses runtime dimensions in the main producer and selector."],
        },
        {
            "id": "record_comparator_and_displaced_group",
            "evidence_class": "inference",
            "claim": (
                "Records below positioning -10 are rejected. Positive positioning has "
                "one special advantage over negative positioning; all other comparisons "
                "are descending target score then positioning score. A strict improvement "
                "replaces, rather than merges, the displaced-primary fallback group."
            ),
            "limitations": ["The fallback is not a recomputed global second-best set."],
        },
        {
            "id": "selector_rng_grammar",
            "evidence_class": "inference",
            "claim": (
                "Every nonempty selector spends caller-ID 30 before any fallback logic. "
                "A nonempty displaced group then spends caller-ID 31; remainder zero out "
                "of four samples that group without replacement through IDs 33 then 32."
            ),
            "limitations": [
                "The fallback acceptance path hardcodes edge coordinate 7 even though the main scan reads runtime dimensions."
            ],
        },
        {
            "id": "solver_scope_unchanged",
            "evidence_class": "fact",
            "claim": (
                "This is a parameterized offline replay boundary. The solver has neither "
                "the complete native candidate records nor the selector-entry CRT state "
                "and continues to consume the settled live enemy queue."
            ),
            "limitations": ["No Rust simulator semantic change follows from this artifact alone."],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "upstream_callback_materialization",
            "question": "What exact ordered records arise before the selector in every enemy decision?",
            "static_status": (
                "Destination and record container order are exact, but subclass callbacks, "
                "native effect construction, and their shared-RNG draws are boundary inputs."
            ),
            "next_evidence": (
                "Capture an ordered record payload with per-callback identities and the "
                "observable CRT state immediately before the selector."
            ),
        },
        {
            "id": "special_positioning_clamp_fields",
            "question": "What shipped semantic names belong to the candidate loop's special positioning-clamp fields?",
            "static_status": (
                "The clamp branch and offsets are byte-pinned, but this artifact does not "
                "assign speculative names to the Pawn fields or incoming mode word."
            ),
            "next_evidence": "Trace their exact Lua/native bindings or stable RTTI-backed accessors.",
        },
        {
            "id": "ordinary_solver_inputs",
            "question": "Can the exact tournament become an ordinary next-turn solver input?",
            "static_status": (
                "The live bridge exposes the settled queue, not complete future records or "
                "the selector-entry CRT state."
            ),
            "next_evidence": (
                "Add a behavior-neutral record-level observer only if future conformance work "
                "requires forecasting rather than consuming the settled queue."
            ),
        },
        {
            "id": "non_windows_or_modified_builds",
            "question": "Does this grammar remain identical on other builds or modified content?",
            "static_status": "Every address, byte, caller ID, and replay claim is exact-build scoped.",
            "next_evidence": "Repeat inventory and reviewed boundary mapping for each additional executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    dependencies = _dependency_records()
    regions = _region_records()
    windows = _control_window_records()
    edges = _direct_edge_records()
    anchors = _data_anchor_records()
    rng_roles = _rng_role_records()
    vectors = _replay_vectors()
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "architecture": "x86",
            "bits": 32,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
        },
        "dependencies": dependencies,
        "method": {
            "tools": [
                {
                    "name": "Ghidra",
                    "version": "12.1.3",
                    "role": "Read-only function extents, call graph, and bounded decompiler corroboration.",
                },
                {
                    "name": "Capstone",
                    "version": SUPPORTED_CAPSTONE_VERSION,
                    "role": "Independent complete x86 decoding and direct-call verification.",
                },
                {
                    "name": "ITB exact-build verifier",
                    "version": "schema 1",
                    "role": "Dependency, executable, region, window, constant, caller-ID, and replay-vector validation.",
                },
            ],
            "procedure": [
                "Validate the prior inventory, PE boundary map, RNG return catalog, and path-order map against the installed executable.",
                "Hash complete reviewed functions and pin only normalized machine-code windows, calls, constants, and control-flow claims.",
                "Reimplement the target tie and 24-byte record selector as pure MSVC-state replays and retain adversarial replay vectors.",
            ],
            "limitations": [
                "No executable bytes or proprietary decompiled source are stored.",
                "Function semantics remain reviewed analyst evidence even though all published bytes and edges reproduce.",
                "The replay starts after callback/effect-side RNG for each target tie or after all candidate records for the record selector.",
                "No claim is made for macOS, another Windows build, or modified native code.",
            ],
        },
        "regions": regions,
        "control_windows": windows,
        "direct_call_edges": edges,
        "data_anchors": anchors,
        "rng_call_roles": rng_roles,
        "contracts": _contracts(),
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_change_required": False,
            "current_simulator_version": 408,
            "reason": (
                "The solver consumes the settled live queue and lacks complete record "
                "payloads plus selector-entry state; this proof corrects provenance and "
                "enables future conformance capture without changing simulated semantics."
            ),
        },
        "summary": {
            "dependency_count": len(dependencies),
            "region_count": len(regions),
            "control_window_count": len(windows),
            "direct_edge_count": len(edges),
            "data_anchor_count": len(anchors),
            "rng_role_count": len(rng_roles),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "record_size_bytes": 24,
            "parameterized_target_tie_complete": True,
            "parameterized_record_selector_complete": True,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _verify_dependencies(executable: Path) -> dict[str, Mapping[str, Any]]:
    loaded: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        value = _read_json(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyRecordSelectorBoundaryError(
                f"dependency file hash differs: {spec['id']}"
            )
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyRecordSelectorBoundaryError(
                f"dependency canonical hash differs: {spec['id']}"
            )
        loaded[spec["id"]] = value

    inventory = loaded["identity_inventory"]
    boundaries = loaded["pe_boundaries"]
    catalog = loaded["rng_return_ids"]
    try:
        validate_pe_boundary_map(executable, boundaries, inventory=inventory)
        validate_rng_return_map(
            executable,
            catalog,
            boundaries,
            inventory=inventory,
        )
        validate_path_cost_ordering_map(executable, loaded["path_cost_ordering"])
    except Exception as exc:
        raise EnemyRecordSelectorBoundaryError(
            f"base native dependency validation failed: {exc}"
        ) from exc
    return loaded


def _verify_native(executable: Path, dependencies: Mapping[str, Mapping[str, Any]]) -> None:
    data, image, executable_sha256 = _load_executable(executable)
    if executable_sha256 != EXPECTED_EXECUTABLE_SHA256:
        raise EnemyRecordSelectorBoundaryError("executable SHA-256 differs")
    if len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise EnemyRecordSelectorBoundaryError("executable size differs")
    if image.architecture != "x86" or image.bits != 32:
        raise EnemyRecordSelectorBoundaryError("expected a PE32 x86 executable")
    if image.image_base != EXPECTED_IMAGE_BASE:
        raise EnemyRecordSelectorBoundaryError("PE image base differs")

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        body = _region_bytes(image, data, start, end - start, ".text", region_id)
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise EnemyRecordSelectorBoundaryError(f"region differs: {region_id}")
        region_ranges[region_id] = (start, end)
    _decode_x86_regions(image, data, region_ranges)

    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(expected_hex)
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start or start + len(expected) > region_end:
            raise EnemyRecordSelectorBoundaryError(
                f"control window escapes region: {window_id}"
            )
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise EnemyRecordSelectorBoundaryError(
                f"control window differs: {window_id}"
            )

    for edge_id, _source, call_rva, expected_hex, target_rva in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, call_rva, len(expected))
        if actual != expected or _direct_target(call_rva, actual) != target_rva:
            raise EnemyRecordSelectorBoundaryError(f"direct edge differs: {edge_id}")

    for anchor_id, rva, expected_hex, _meaning in DATA_ANCHOR_SPECS:
        expected = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemyRecordSelectorBoundaryError(f"data anchor differs: {anchor_id}")

    scanned = _scan_rng_calls(data, image, RNG_CORE_RVA)
    if len(scanned) != EXPECTED_RNG_CALL_COUNT:
        raise EnemyRecordSelectorBoundaryError("raw RNG call count differs")
    scanned_rvas = [rva for rva, _section in scanned]
    catalog = dependencies["rng_return_ids"]
    callers = catalog.get("callers")
    if not isinstance(callers, list):
        raise EnemyRecordSelectorBoundaryError("RNG dependency callers are missing")
    by_id = {
        item.get("caller_id"): item
        for item in callers
        if isinstance(item, Mapping)
    }
    for caller_id, call_rva, _role, _meaning in RNG_ROLE_SPECS:
        item = by_id.get(caller_id)
        if item is None or item.get("call_rva") != f"0x{call_rva:08x}":
            raise EnemyRecordSelectorBoundaryError(
                f"RNG caller role differs: {caller_id}"
            )
        if call_rva not in scanned_rvas:
            raise EnemyRecordSelectorBoundaryError(
                f"RNG caller is absent from raw scan: {caller_id}"
            )


def build_enemy_record_selector_boundary_map(executable: Path) -> dict[str, Any]:
    """Build the exact expected artifact after verifying every native input."""
    dependencies = _verify_dependencies(executable)
    _verify_native(executable, dependencies)
    return _expected_shape()


def validate_enemy_record_selector_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields without requiring the installed executable."""
    if not isinstance(value, Mapping):
        raise EnemyRecordSelectorBoundaryError("enemy selector map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise EnemyRecordSelectorBoundaryError("enemy selector map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "record_size_bytes": 24,
        "parameterized_target_tie_complete": True,
        "parameterized_record_selector_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_record_selector_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject byte, dependency, or replay drift."""
    expected = build_enemy_record_selector_boundary_map(executable)
    if dict(value) != expected:
        raise EnemyRecordSelectorBoundaryError(
            "enemy selector map differs from executable analysis"
        )
    result = validate_enemy_record_selector_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_record_selector_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
