"""Replay the exact-build native enemy candidate score adjustments.

The Windows build applies small but consequential native transformations around
the Lua ``ScorePositioning`` and ``GetTargetScore`` callbacks.  This module
binds those transformations to the pinned executable and exposes pure replay
helpers for the honest boundary inputs: callback integers, native Pawn fields,
and the selected-weapon vector count.

It does not execute Lua callbacks, construct target areas, or forecast a whole
enemy phase.  The ordinary solver therefore continues to consume the settled
live enemy queue.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.enemy_record_selector_boundary import (
    validate_enemy_record_selector_boundary_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
    validate_pe_boundary_map,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_candidate_score_boundary_map"
POSITIONING_REPLAY_KIND = "native_enemy_positioning_clamp_replay"
TARGET_SCORE_REPLAY_KIND = "native_enemy_target_score_replay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
NORMAL_CANDIDATE_MODE = 0
DEBUGAI_CANDIDATE_MODE = 1
SPECIAL_TARGET_SCORE_WEAPON_INDEX = 0x32
TARGET_HISTORY_MODIFIER = -5
PRIORITY_TARGET_MODIFIER = 10
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1


class EnemyCandidateScoreBoundaryError(RuntimeError):
    """Raised when the exact candidate-score boundary cannot reproduce."""


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
        "role": "Pins the Steam build and exact executable identity.",
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
            "Pins the candidate loop, callback wrappers, AI orchestrator, and "
            "their exact-build call graph."
        ),
    },
    {
        "id": "enemy_record_selector",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json"
        ),
        "file_sha256": (
            "73ccd7972fd25f2f455173673fed19b2310f6039e58b8cf5118236ff4f8b2022"
        ),
        "canonical_sha256": (
            "1a7ef818d1e889849e68301cb3e94d2291bc908f98b7501c5033d390ba110bfc"
        ),
        "role": (
            "Pins the downstream 24-byte record layout and tournament that "
            "consume these post-adjustment scores."
        ),
    },
)


REGION_SPECS = (
    (
        "normal_orchestrator",
        0x000F6390,
        0x000F6B74,
        "f788de533a9e841719e4611a646afccb11ac950835e379fa70296c24f98e9bb4",
        "Normal enemy-planning orchestrator and mode-zero call site.",
    ),
    (
        "score_positioning",
        0x000F7870,
        0x000F78EC,
        "9794db437203d18af0ce5245bc178f537e20f715b192c671cc7ecde7d279a42a",
        "Named ScorePositioning integer wrapper.",
    ),
    (
        "candidate_loop",
        0x000F78F0,
        0x000F7C17,
        "a162b5ead3bfcb851bf99f31b204485769570deb38fb6eb8102040214bcfc064",
        "Per-destination target enumeration and score materialization.",
    ),
    (
        "debugai_route",
        0x000F8240,
        0x000F8445,
        "38aae33db3275ed5eea690b2f6024af942471b82b31b735359723b7f3fcc9a74",
        "Debug-AI route and mode-one call site.",
    ),
    (
        "target_score",
        0x00229310,
        0x0022947F,
        "7316bcd20f712aa7232980057b847fcf30e5fe7ded97f96cd236dad0c8805405",
        "GetTargetScore resolver plus native pre/post modifiers.",
    ),
    (
        "skill_archive",
        0x00229820,
        0x0022991F,
        "ed82578b7a5100850869ad88ec99737018446faa7eb6be317bc5f6b8e701b485",
        "SkillManager archive path naming targetHistory and priorityTarget.",
    ),
    (
        "skill_load",
        0x00229920,
        0x00229B03,
        "687bb097bfc332c01c8aaf445dc93deed489914dab6da209856f7dfe013da758",
        "SkillManager load path assigning targetHistory and priorityTarget.",
    ),
    (
        "pawn_definition_apply",
        0x0022C0F0,
        0x0022CBB7,
        "9c705957ab7a8afa137bb56e4d075b40a29ca8da45222fd318f2c821ac138148",
        "Pawn definition application including health-component field copies.",
    ),
    (
        "injured_set",
        0x0022D5A0,
        0x0022D5ED,
        "ce09d50a1f2420db0bdf2210583c50cb2b143c87f7f7a0dabfb1bd4da78aa824",
        "Pawn injured-flag transition and exact injured event name.",
    ),
    (
        "health_set",
        0x0022FEF0,
        0x0022FF15,
        "276a0ece1a20befe08726299107dc5b1ca77c99a73e0de8dbfb9a27e3f6264d0",
        "SetHealth implementation clamping current health to maximum health.",
    ),
    (
        "selected_weapon_get",
        0x002398E0,
        0x0023990C,
        "3da9346e6494082f1008fcad3d91e031910702187ba9ccda1cc9e7ba1ef0ce1a",
        "GetSelectedWeapon implementation and out-of-range normalization.",
    ),
    (
        "selected_weapon_load",
        0x00239A20,
        0x00239A5F,
        "a6f0332464d3c33376267f00d6e527d93ae659a91787dce8c585d82f45c855eb",
        "Weapon field load into the native selected-weapon slot.",
    ),
    (
        "pawn_archive",
        0x0023FB40,
        0x00240ACF,
        "b3475222468769a173264dd29a9bb00d3980f563b0c4bb9243875b844450d270",
        "Pawn archive path containing iCurrentWeapon.",
    ),
    (
        "pawn_definition",
        0x00240AE0,
        0x0024209E,
        "92ad8d746d427511dbd27a845faa17d22240a8fe703d48c10a4b92e85aacd3f9",
        "Pawn definition loader containing iCurrentWeapon and health state.",
    ),
    (
        "health_state_load",
        0x002435F0,
        0x002438CF,
        "df34f791aa3204d9e12f2aa982d94dfd86016ff658d378ce7ae69545c3be9c94",
        "Named health, max_health, and bInjured state loader.",
    ),
    (
        "pawn_method_bindings",
        0x0027C0EA,
        0x0027C1BE,
        "01afd6c9bd6d58dcda7baa1fe7ecdbbd2bd01e67e667c37d4a94ed267cd46c13",
        "Instruction-aligned SetHealth and GetSelectedWeapon binding span.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "normal_mode_zero",
        "normal_orchestrator",
        0x000F6812,
        "8d4b14ff7304e8031400006a008d4b14e8890f0000",
        "Normal planning passes candidate mode zero to the record seed.",
    ),
    (
        "debugai_mode_one",
        "debugai_route",
        0x000F82E5,
        "578bcee833f9ffff8bcfe82c1714006a018bcee8b3f4ffff",
        "The debugai route refreshes Weapon and passes candidate mode one.",
    ),
    (
        "positioning_injured_one_hp_clamp",
        "candidate_loop",
        0x000F7A3D,
        "ff75108bcfff750ce826feffff8b77288bd88b550c895dc08a8ed608000084c98b4d10742a3b55dc75053b4de0742083bea808000001751785dbc74508000000008d45c08d75080f49c68b008945c0",
        (
            "After ScorePositioning, a moved bInjured Pawn at health one "
            "replaces every nonnegative result with the incoming mode."
        ),
    ),
    (
        "candidate_selected_weapon_normalization",
        "candidate_loop",
        0x000F7AD2,
        "8b914809000083faff74178b41082b4104c1f8033bd07c0ac7814809000000000000ff7604ff36ffb1480900008b4f28e809181300",
        (
            "Normalize an out-of-range non-minus-one selected weapon to zero "
            "before invoking GetTargetScore."
        ),
    ),
    (
        "target_modifier_fields_and_resolver_gate",
        "target_score",
        0x00229338,
        "8b450c33f68b5510394150750b395154bffbffffff0f44f73b4160750b3b5164b80a0000000f44f08b550885d2780d8b41082b4104c1f8033bd07c0983fa320f85ec000000",
        (
            "Apply targetHistory -5, let priorityTarget override with +10, "
            "then gate callback resolution by vector bounds or literal index 50."
        ),
    ),
    (
        "negative_modifier_positive_floor",
        "target_score",
        0x00229423,
        "8b4d0885c97e288bc69933c22bc23bc87f1d85f67919b8010000008b4df464890d00000000595f5e5b8be55dc20c008d0431",
        (
            "Floor a positive callback result at one when a negative modifier "
            "would otherwise reduce it to zero or below; otherwise add normally."
        ),
    ),
    (
        "skill_archive_priority_history",
        "skill_archive",
        0x002298DF,
        "ff7664ff766083ec188bcc68b45e8300e81ce5ddff8bcfe86547e2ffff7654ff765083ec188bcc68d45e8300e800e5ddff8bcfe84947e2ff",
        "Archive +0x60/+0x64 as priorityTarget and +0x50/+0x54 as targetHistory.",
    ),
    (
        "skill_load_priority_history",
        "skill_load",
        0x00229A69,
        "6a0e68b45e8300c60000e858e5ddff8d4424288bcf50e82cd7ecff6aff6aff83ec188b08894e608bcc8b40048946646a0dc741140f000000c741100000000068d45e8300c60100e81be5ddff8d4424288bcf50e8efd6ecff83ec188b08894e508bcc8b4004894654",
        "Load priorityTarget into +0x60/+0x64 and targetHistory into +0x50/+0x54.",
    ),
    (
        "pawn_health_component_copy",
        "pawn_definition_apply",
        0x0022C510,
        "e8db47ebff8bf0c645fc038b4e04898ba80800008b4e08898bac080000",
        "Copy health-component +0x04/+0x08 into Pawn +0x8a8/+0x8ac.",
    ),
    (
        "injured_flag_and_event",
        "injured_set",
        0x0022D5A0,
        "558bec51538a5d08568bf184db74318a86d608000084c075270f1005c85d890083ec108bc483ec188bcc68706183000f1100e839a8ddff6a018bcee870180000889ed60800005e5b595dc20400",
        "Use exact event name injured while reading and writing Pawn +0x8d6.",
    ),
    (
        "set_health_current_max_offsets",
        "health_set",
        0x0022FEF0,
        "558bec8d81ac080000568b75088d55083b308975080f4dd05e8b028981a80800005dc20400",
        "Clamp the input to +0x8ac and store current health at +0x8a8.",
    ),
    (
        "selected_weapon_archive",
        "pawn_archive",
        0x00240849,
        "83ec188bcc68e86e8300e8b875dcffffb7480900008bcee8cb84e9ff",
        "Archive Pawn +0x948 under iCurrentWeapon.",
    ),
    (
        "selected_weapon_definition_load",
        "pawn_definition",
        0x00241AB0,
        "6a0e68e86e8300c60000e81165dcffffb3480900008bcfe8e463e4ff83ec18898348090000",
        "Load iCurrentWeapon into Pawn +0x948.",
    ),
    (
        "health_state_named_fields",
        "health_state_load",
        0x0024379B,
        "6a0a6810708300c60000e82648dcffc745fc000000008bcf8b07ff5008508bcbc745fcffffffffe8e946e4ff8947088d770833c9c74508000000003b47048d45080f9cc18d0c8d0400000003cf8339000f4fc183ec188bcc8b008947046a06c741140f000000c7411000000000681c708300c60100e8bb47dcffff77048bcbe89146e4ff8bc88d45083b0e894d080f4dc683ec188bcc8b008947046a08c741140f000000c741100000000068e06f8300",
        "Load max_health, health, and bInjured into the native health component.",
    ),
    (
        "set_health_api_binding",
        "pawn_method_bindings",
        0x0027C0EA,
        "c745e8f0fe6200ff75f0c745ec00000000518d4de851684c8a83008bc8e8140b0100",
        "Bind SetHealth to RVA 0x0022fef0.",
    ),
    (
        "get_selected_weapon_api_binding",
        "pawn_method_bindings",
        0x0027C19C,
        "c745e8e0986300ff75f0c745ec00000000518d4de85168489083008bc8e8e2010100",
        "Bind GetSelectedWeapon to RVA 0x002398e0.",
    ),
)


DIRECT_EDGE_SPECS = (
    (
        "normal_orchestrator_to_record_seed",
        "normal_orchestrator",
        0x000F6822,
        "e8890f0000",
        0x000F77B0,
    ),
    (
        "debugai_to_record_seed",
        "debugai_route",
        0x000F82F8,
        "e8b3f4ffff",
        0x000F77B0,
    ),
    (
        "candidate_to_score_positioning",
        "candidate_loop",
        0x000F7A45,
        "e826feffff",
        0x000F7870,
    ),
    (
        "candidate_to_target_score",
        "candidate_loop",
        0x000F7B02,
        "e809181300",
        0x00229310,
    ),
    (
        "pawn_archive_to_skill_archive",
        "pawn_archive",
        0x00240A8C,
        "e88f8dfeff",
        0x00229820,
    ),
    (
        "pawn_definition_to_skill_load",
        "pawn_definition",
        0x0024200F,
        "e80c79feff",
        0x00229920,
    ),
    (
        "pawn_definition_to_health_state_first",
        "pawn_definition",
        0x002419AD,
        "e83e1c0000",
        0x002435F0,
    ),
    (
        "pawn_definition_to_health_state_second",
        "pawn_definition",
        0x00241A25,
        "e8c61b0000",
        0x002435F0,
    ),
)


DATA_ANCHOR_SPECS = (
    ("score_positioning_name", 0x0042A848, b"ScorePositioning\0"),
    ("debugai_name", 0x0042A864, b"debugai\0"),
    ("weapon_field_name", 0x0042B5EC, b"Weapon\0"),
    ("health_definition_name", 0x00435A28, b"Health\0"),
    ("priority_target_name", 0x00435EB4, b"priorityTarget\0"),
    ("target_history_name", 0x00435ED4, b"targetHistory\0"),
    ("injured_event_name", 0x00436170, b"injured\0"),
    ("current_weapon_name", 0x00436EE8, b"iCurrentWeapon\0"),
    ("injured_state_name", 0x00436FE0, b"bInjured\0"),
    ("max_health_name", 0x00437010, b"max_health\0"),
    ("health_name", 0x0043701C, b"health\0"),
    ("get_target_score_name", 0x004380DC, b"GetTargetScore\0"),
    ("set_health_name", 0x00438A4C, b"SetHealth\0"),
    ("get_health_name", 0x00438A58, b"GetHealth\0"),
    ("get_selected_weapon_name", 0x00439048, b"GetSelectedWeapon\0"),
)


METHOD_BINDING_SPECS = (
    {
        "id": "pawn_set_health",
        "method_name": "SetHealth",
        "name_anchor": "set_health_name",
        "registration_window": "set_health_api_binding",
        "implementation_region": "health_set",
        "implementation_rva": "0x0022fef0",
        "current_health_offset": "+0x8a8",
        "max_health_offset": "+0x8ac",
    },
    {
        "id": "pawn_get_selected_weapon",
        "method_name": "GetSelectedWeapon",
        "name_anchor": "get_selected_weapon_name",
        "registration_window": "get_selected_weapon_api_binding",
        "implementation_region": "selected_weapon_get",
        "implementation_rva": "0x002398e0",
        "selected_weapon_offset": "+0x948",
    },
)


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
        raise EnemyCandidateScoreBoundaryError(
            f"dependency is not a regular non-symlink file: {path}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyCandidateScoreBoundaryError(
            f"dependency must contain an object: {path}"
        )
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemyCandidateScoreBoundaryError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise EnemyCandidateScoreBoundaryError(
            f"RVA 0x{rva:08x} is not a direct rel32 call"
        )
    displacement = struct.unpack("<i", encoded[1:])[0]
    return rva + 5 + displacement


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnemyCandidateScoreBoundaryError(f"{name} must be an integer")
    if not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyCandidateScoreBoundaryError(
            f"{name} must fit in a signed 32-bit integer"
        )
    return value


def _require_nonnegative(name: str, value: Any) -> int:
    result = _require_int(name, value)
    if result < 0:
        raise EnemyCandidateScoreBoundaryError(f"{name} must be nonnegative")
    return result


def _require_bool(name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise EnemyCandidateScoreBoundaryError(f"{name} must be a boolean")
    return value


def _point(name: str, value: Any) -> tuple[int, int]:
    if (
        isinstance(value, (str, bytes, bytearray))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemyCandidateScoreBoundaryError(
            f"{name} must contain exactly two coordinates"
        )
    return (
        _require_int(f"{name}[0]", value[0]),
        _require_int(f"{name}[1]", value[1]),
    )


def _signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value <= SIGNED_MAX else value - (1 << 32)


def normalize_enemy_selected_weapon(
    weapon_index: int,
    weapon_count: int,
) -> dict[str, Any]:
    """Replay the candidate loop's selected-weapon normalization."""
    original = _require_int("weapon_index", weapon_index)
    count = _require_nonnegative("weapon_count", weapon_count)
    normalized = original
    if original != -1 and count <= original:
        normalized = 0
    return {
        "original_weapon_index": original,
        "weapon_count": count,
        "normalized_weapon_index": normalized,
        "changed": normalized != original,
    }


def replay_enemy_positioning_clamp(
    raw_score: int,
    *,
    injured: bool,
    moved: bool,
    current_health: int,
    mode: int = NORMAL_CANDIDATE_MODE,
) -> dict[str, Any]:
    """Replay the post-``ScorePositioning`` injured/one-HP clamp."""
    score = _require_int("raw_score", raw_score)
    injured_value = _require_bool("injured", injured)
    moved_value = _require_bool("moved", moved)
    health = _require_int("current_health", current_health)
    selected_mode = _require_int("mode", mode)
    if selected_mode not in (NORMAL_CANDIDATE_MODE, DEBUGAI_CANDIDATE_MODE):
        raise EnemyCandidateScoreBoundaryError(
            "mode must be 0 (normal planning) or 1 (debugai)"
        )

    clamp_applied = (
        injured_value and moved_value and health == 1 and score >= 0
    )
    final_score = selected_mode if clamp_applied else score
    return {
        "analysis_kind": POSITIONING_REPLAY_KIND,
        "route": "normal_enemy_planning" if selected_mode == 0 else "debugai",
        "mode": selected_mode,
        "raw_score": score,
        "injured": injured_value,
        "moved": moved_value,
        "current_health": health,
        "clamp_applied": clamp_applied,
        "final_score": final_score,
        "mode_forces_target_area_evaluation": selected_mode != 0,
    }


def replay_enemy_target_score_wrapper(
    *,
    weapon_index: int,
    weapon_count: int,
    callback_score: int | None,
    target: Sequence[int],
    target_history: Sequence[int],
    priority_target: Sequence[int],
) -> dict[str, Any]:
    """Replay the native ``GetTargetScore`` wrapper around one callback result."""
    index = _require_int("weapon_index", weapon_index)
    count = _require_nonnegative("weapon_count", weapon_count)
    target_point = _point("target", target)
    history_point = _point("target_history", target_history)
    priority_point = _point("priority_target", priority_target)

    history_match = target_point == history_point
    priority_match = target_point == priority_point
    modifier = TARGET_HISTORY_MODIFIER if history_match else 0
    if priority_match:
        modifier = PRIORITY_TARGET_MODIFIER

    callback_invoked = (
        0 <= index < count or index == SPECIAL_TARGET_SCORE_WEAPON_INDEX
    )
    if callback_invoked:
        if callback_score is None:
            raise EnemyCandidateScoreBoundaryError(
                "callback_score is required when the native wrapper resolves a skill"
            )
        callback = _require_int("callback_score", callback_score)
        positive_floor_applied = (
            modifier < 0 and 0 < callback <= abs(modifier)
        )
        final_score = 1 if positive_floor_applied else _signed32(callback + modifier)
    else:
        if callback_score is not None:
            raise EnemyCandidateScoreBoundaryError(
                "callback_score must be null when the native wrapper skips the callback"
            )
        callback = None
        positive_floor_applied = False
        final_score = modifier

    return {
        "analysis_kind": TARGET_SCORE_REPLAY_KIND,
        "weapon_index": index,
        "weapon_count": count,
        "special_weapon_index": SPECIAL_TARGET_SCORE_WEAPON_INDEX,
        "target": list(target_point),
        "target_history": list(history_point),
        "priority_target": list(priority_point),
        "target_history_match": history_match,
        "priority_target_match": priority_match,
        "priority_overrode_history": history_match and priority_match,
        "native_modifier": modifier,
        "callback_invoked": callback_invoked,
        "callback_score": callback,
        "positive_floor_applied": positive_floor_applied,
        "final_score": final_score,
    }


def replay_enemy_candidate_target_score(
    *,
    weapon_index: int,
    weapon_count: int,
    callback_score: int | None,
    target: Sequence[int],
    target_history: Sequence[int],
    priority_target: Sequence[int],
) -> dict[str, Any]:
    """Replay candidate normalization followed by the target-score wrapper."""
    normalization = normalize_enemy_selected_weapon(weapon_index, weapon_count)
    result = replay_enemy_target_score_wrapper(
        weapon_index=normalization["normalized_weapon_index"],
        weapon_count=normalization["weapon_count"],
        callback_score=callback_score,
        target=target,
        target_history=target_history,
        priority_target=priority_target,
    )
    result["candidate_weapon_normalization"] = normalization
    return result


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
            "size": len(expected),
            "data_hex": expected.hex(),
            "text": expected[:-1].decode("ascii"),
        }
        for anchor_id, rva, expected in DATA_ANCHOR_SPECS
    ]


def _method_binding_records() -> list[dict[str, str]]:
    return [dict(item) for item in METHOD_BINDING_SPECS]


def _position_vector(
    vector_id: str,
    raw_score: int,
    *,
    injured: bool,
    moved: bool,
    current_health: int,
    mode: int,
) -> dict[str, Any]:
    result = replay_enemy_positioning_clamp(
        raw_score,
        injured=injured,
        moved=moved,
        current_health=current_health,
        mode=mode,
    )
    return {
        "id": vector_id,
        "kind": "positioning_clamp",
        "input": {
            "raw_score": raw_score,
            "injured": injured,
            "moved": moved,
            "current_health": current_health,
            "mode": mode,
        },
        "expected": {
            "clamp_applied": result["clamp_applied"],
            "final_score": result["final_score"],
            "route": result["route"],
        },
    }


def _target_vector(
    vector_id: str,
    *,
    weapon_index: int,
    weapon_count: int,
    callback_score: int | None,
    target: Sequence[int] = (3, 3),
    target_history: Sequence[int] = (1, 1),
    priority_target: Sequence[int] = (6, 6),
    candidate: bool = False,
) -> dict[str, Any]:
    replay = (
        replay_enemy_candidate_target_score
        if candidate
        else replay_enemy_target_score_wrapper
    )
    result = replay(
        weapon_index=weapon_index,
        weapon_count=weapon_count,
        callback_score=callback_score,
        target=target,
        target_history=target_history,
        priority_target=priority_target,
    )
    expected = {
        "weapon_index": result["weapon_index"],
        "native_modifier": result["native_modifier"],
        "callback_invoked": result["callback_invoked"],
        "positive_floor_applied": result["positive_floor_applied"],
        "priority_overrode_history": result["priority_overrode_history"],
        "final_score": result["final_score"],
    }
    if candidate:
        expected["candidate_weapon_normalization"] = result[
            "candidate_weapon_normalization"
        ]
    return {
        "id": vector_id,
        "kind": "candidate_target_score" if candidate else "target_score_wrapper",
        "input": {
            "weapon_index": weapon_index,
            "weapon_count": weapon_count,
            "callback_score": callback_score,
            "target": list(target),
            "target_history": list(target_history),
            "priority_target": list(priority_target),
        },
        "expected": expected,
    }


def _replay_vectors() -> list[dict[str, Any]]:
    return [
        _position_vector(
            "normal_injured_moved_one_hp_positive_to_zero",
            7,
            injured=True,
            moved=True,
            current_health=1,
            mode=0,
        ),
        _position_vector(
            "normal_injured_negative_preserved",
            -3,
            injured=True,
            moved=True,
            current_health=1,
            mode=0,
        ),
        _position_vector(
            "debugai_injured_moved_one_hp_positive_to_one",
            7,
            injured=True,
            moved=True,
            current_health=1,
            mode=1,
        ),
        _position_vector(
            "not_moved_no_clamp",
            7,
            injured=True,
            moved=False,
            current_health=1,
            mode=0,
        ),
        _position_vector(
            "health_two_no_clamp",
            7,
            injured=True,
            moved=True,
            current_health=2,
            mode=0,
        ),
        _target_vector(
            "unmodified_callback",
            weapon_index=0,
            weapon_count=2,
            callback_score=7,
        ),
        _target_vector(
            "history_penalty",
            weapon_index=0,
            weapon_count=2,
            callback_score=9,
            target=(1, 1),
        ),
        _target_vector(
            "history_positive_floor",
            weapon_index=0,
            weapon_count=2,
            callback_score=5,
            target=(1, 1),
        ),
        _target_vector(
            "priority_bonus",
            weapon_index=0,
            weapon_count=2,
            callback_score=2,
            target=(6, 6),
        ),
        _target_vector(
            "priority_overrides_history",
            weapon_index=0,
            weapon_count=2,
            callback_score=2,
            target=(4, 4),
            target_history=(4, 4),
            priority_target=(4, 4),
        ),
        _target_vector(
            "invalid_weapon_skips_callback",
            weapon_index=-1,
            weapon_count=2,
            callback_score=None,
            target=(1, 1),
        ),
        _target_vector(
            "literal_50_wrapper_exception",
            weapon_index=50,
            weapon_count=2,
            callback_score=4,
            target=(1, 1),
        ),
        _target_vector(
            "candidate_normalizes_out_of_range_to_zero",
            weapon_index=50,
            weapon_count=2,
            callback_score=4,
            candidate=True,
        ),
        _target_vector(
            "signed_add_wraps",
            weapon_index=0,
            weapon_count=2,
            callback_score=SIGNED_MAX,
            target=(6, 6),
        ),
    ]


def _contracts() -> dict[str, Any]:
    return {
        "field_bindings": {
            "current_health": {
                "pawn_offset": "+0x8a8",
                "component_offset": "+0x04",
                "native_name": "health",
                "setter": "SetHealth",
            },
            "max_health": {
                "pawn_offset": "+0x8ac",
                "component_offset": "+0x08",
                "native_name": "max_health",
            },
            "injured": {
                "pawn_offset": "+0x8d6",
                "component_offset": "+0x32",
                "native_state_name": "bInjured",
                "native_event_name": "injured",
            },
            "selected_weapon": {
                "pawn_offset": "+0x948",
                "archive_name": "iCurrentWeapon",
                "load_field": "Weapon",
                "lua_getter": "GetSelectedWeapon",
            },
            "target_history": {
                "owner": "Pawn SkillManager base",
                "x_offset": "+0x50",
                "y_offset": "+0x54",
                "archive_name": "targetHistory",
                "modifier": TARGET_HISTORY_MODIFIER,
            },
            "priority_target": {
                "owner": "Pawn SkillManager base",
                "x_offset": "+0x60",
                "y_offset": "+0x64",
                "archive_name": "priorityTarget",
                "modifier": PRIORITY_TARGET_MODIFIER,
                "overrides_target_history": True,
            },
        },
        "positioning_clamp": {
            "callback": "ScorePositioning",
            "predicate": (
                "bInjured AND destination differs from current Pawn point AND "
                "health == 1 AND callback_score >= 0"
            ),
            "replacement": "candidate mode integer",
            "normal_route_mode": NORMAL_CANDIDATE_MODE,
            "debugai_route_mode": DEBUGAI_CANDIDATE_MODE,
            "negative_callback_score_preserved": True,
            "normal_route_nonnegative_replacement": 0,
            "debugai_route_nonnegative_replacement": 1,
        },
        "selected_weapon_normalization": {
            "predicate": "selected_weapon != -1 AND weapon_count <= selected_weapon",
            "replacement": 0,
            "negative_values_below_minus_one_preserved": True,
            "performed_before_target_area": True,
            "performed_again_before_each_target_score": True,
        },
        "target_score_wrapper": {
            "callback": "GetTargetScore",
            "modifier_order": [
                "start at 0",
                "targetHistory match assigns -5",
                "priorityTarget match assigns +10 and overrides history",
            ],
            "callback_resolver_predicate": (
                "0 <= selected_weapon < weapon_count OR selected_weapon == 50"
            ),
            "invalid_weapon_result": "native modifier without callback",
            "special_resolver_weapon_index": SPECIAL_TARGET_SCORE_WEAPON_INDEX,
            "negative_modifier_positive_floor": (
                "if 0 < callback_score <= abs(modifier), return 1"
            ),
            "otherwise": "signed 32-bit callback_score + modifier",
        },
        "replay_boundary": {
            "inputs": [
                "post-Lua ScorePositioning integer",
                "post-Lua GetTargetScore integer when the native resolver invokes it",
                "native Pawn health, injured, selected-weapon, and target-history fields",
                "weapon vector count and normal/debug route",
            ],
            "native_pre_post_adjustments_complete": True,
            "lua_callback_implementation_complete": False,
            "target_area_construction_complete": False,
            "complete_candidate_materialization": False,
            "complete_enemy_phase_forecast": False,
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "positioning_clamp_fields_resolved",
            "evidence_class": "inference",
            "claim": (
                "The prior anonymous candidate-clamp fields are the Pawn bInjured "
                "byte and current health integer. Normal planning passes zero, so a "
                "moved injured one-HP pawn cannot retain a positive positioning score."
            ),
            "limitations": [
                "The Lua ScorePositioning callback remains an input to this replay."
            ],
        },
        {
            "id": "debug_route_is_distinct",
            "evidence_class": "fact",
            "claim": (
                "Only the reviewed debugai route passes mode one; the ordinary enemy "
                "orchestrator passes mode zero."
            ),
            "limitations": [
                "The artifact does not treat debugai observations as ordinary runtime behavior."
            ],
        },
        {
            "id": "target_history_and_priority_modifiers",
            "evidence_class": "inference",
            "claim": (
                "The GetTargetScore wrapper subtracts five at targetHistory and adds "
                "ten at priorityTarget, with priorityTarget winning when both match."
            ),
            "limitations": [
                "The game-specific code that sets those two points is not replayed here."
            ],
        },
        {
            "id": "positive_callback_floor",
            "evidence_class": "fact",
            "claim": (
                "A negative native modifier never turns a positive callback score into "
                "zero or a negative score; results within the penalty magnitude become one."
            ),
            "limitations": ["Other sums follow native signed 32-bit arithmetic."],
        },
        {
            "id": "candidate_weapon_normalization_precedes_wrapper",
            "evidence_class": "inference",
            "claim": (
                "The candidate loop rewrites an out-of-range selected weapon to zero "
                "before target-area and target-score work, while the wrapper itself has "
                "a separate literal-index-50 resolver exception."
            ),
            "limitations": [
                "The shipped semantic name of literal index 50 remains unresolved."
            ],
        },
        {
            "id": "solver_scope_unchanged",
            "evidence_class": "fact",
            "claim": (
                "These helpers close native arithmetic around callback results but do "
                "not provide future callback outputs or target areas to the solver."
            ),
            "limitations": [
                "No Rust simulator change or version bump follows from this boundary alone."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "lua_callback_materialization",
            "question": (
                "What exact values and shared-RNG draws occur inside each shipped "
                "ScorePositioning and GetTargetScore implementation?"
            ),
            "static_status": (
                "Native dispatch, field adjustment, and post-callback arithmetic are "
                "exact; the Lua callback body remains a boundary input."
            ),
            "next_evidence": (
                "Use build-keyed callback identities and bounded result/RNG capture only "
                "where settled-queue conformance exposes a real difference."
            ),
        },
        {
            "id": "target_area_eligibility_and_construction",
            "question": (
                "Which exact Pawn predicates admit ordinary GetTargetArea evaluation, "
                "and what ordered points does each implementation return?"
            ),
            "static_status": (
                "Mode one forces the native gate, but the ordinary predicate and Lua "
                "target-area construction are not parameterized here."
            ),
            "next_evidence": (
                "Continue offline predicate naming, then retain target-area outputs as "
                "inputs unless a behavior-neutral capture is necessary."
            ),
        },
        {
            "id": "literal_weapon_index_50",
            "question": "What shipped concept owns the GetTargetScore resolver sentinel 50?",
            "static_status": (
                "The literal branch and resolver behavior are byte-pinned, but no stable "
                "archive or Lua name has yet been tied to the number."
            ),
            "next_evidence": "Trace all callers that can pass 50 into the SkillManager resolver.",
        },
        {
            "id": "complete_candidate_records_and_rng_entry",
            "question": (
                "Can every ordered 24-byte record and selector-entry CRT state be "
                "reconstructed before the settled enemy queue exists?"
            ),
            "static_status": (
                "This artifact closes two native score adjustments but not all callback, "
                "effect, and shared-RNG materialization."
            ),
            "next_evidence": (
                "Compose only after the remaining GetTargetArea/GetSkillEffect and "
                "callback-RNG seams are independently proven."
            ),
        },
        {
            "id": "non_windows_or_modified_builds",
            "question": "Do the same fields and arithmetic hold on other native builds?",
            "static_status": "Every address, byte, field offset, and name is exact-build scoped.",
            "next_evidence": "Repeat inventory and reviewed mapping for each executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    dependencies = _dependency_records()
    regions = _region_records()
    windows = _control_window_records()
    edges = _direct_edge_records()
    anchors = _data_anchor_records()
    bindings = _method_binding_records()
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
                    "role": (
                        "Read-only function extents, string references, call graph, "
                        "and bounded decompiler corroboration."
                    ),
                },
                {
                    "name": "Capstone",
                    "version": SUPPORTED_CAPSTONE_VERSION,
                    "role": "Independent complete x86 decoding and direct-call validation.",
                },
                {
                    "name": "ITB exact-build verifier",
                    "version": "schema 1",
                    "role": (
                        "Dependency, PE identity, region, window, string, edge, binding, "
                        "and replay-vector validation."
                    ),
                },
            ],
            "procedure": [
                "Validate the pinned inventory, PE boundary map, and downstream record-selector artifact.",
                "Trace anonymous field offsets through exact archive strings and Lua method bindings.",
                "Hash complete reviewed functions and retain only normalized machine-code windows and facts.",
                "Reimplement the native clamp, weapon normalization, and score wrapper as pure signed-32-bit replays.",
            ],
            "limitations": [
                "No executable bytes or proprietary decompiled source are stored.",
                "Lua callback results, target areas, and effect-side RNG remain boundary inputs.",
                "No claim is made for macOS, another Windows build, or modified native code.",
            ],
        },
        "regions": regions,
        "control_windows": windows,
        "direct_call_edges": edges,
        "data_anchors": anchors,
        "method_bindings": bindings,
        "contracts": _contracts(),
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_change_required": False,
            "current_simulator_version": 408,
            "reason": (
                "The solver consumes the settled enemy queue and still lacks future Lua "
                "callback outputs, complete candidate records, and selector-entry state."
            ),
        },
        "summary": {
            "dependency_count": len(dependencies),
            "region_count": len(regions),
            "control_window_count": len(windows),
            "direct_edge_count": len(edges),
            "data_anchor_count": len(anchors),
            "method_binding_count": len(bindings),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "native_pre_post_adjustments_complete": True,
            "complete_candidate_materialization": False,
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
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["file_sha256"]:
            raise EnemyCandidateScoreBoundaryError(
                f"dependency file hash differs: {spec['id']}"
            )
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyCandidateScoreBoundaryError(
                f"dependency canonical hash differs: {spec['id']}"
            )
        loaded[spec["id"]] = value

    try:
        validate_pe_boundary_map(
            executable,
            loaded["pe_boundaries"],
            inventory=loaded["identity_inventory"],
        )
        validate_enemy_record_selector_boundary_map(
            executable,
            loaded["enemy_record_selector"],
        )
    except Exception as exc:
        raise EnemyCandidateScoreBoundaryError(
            f"base native dependency validation failed: {exc}"
        ) from exc
    return loaded


def _verify_native(executable: Path) -> None:
    data, image, executable_sha256 = _load_executable(executable)
    if executable_sha256 != EXPECTED_EXECUTABLE_SHA256:
        raise EnemyCandidateScoreBoundaryError("executable SHA-256 differs")
    if len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise EnemyCandidateScoreBoundaryError("executable size differs")
    if image.architecture != "x86" or image.bits != 32:
        raise EnemyCandidateScoreBoundaryError("expected a PE32 x86 executable")
    if image.image_base != EXPECTED_IMAGE_BASE:
        raise EnemyCandidateScoreBoundaryError("PE image base differs")

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        body = _region_bytes(image, data, start, end - start, ".text", region_id)
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise EnemyCandidateScoreBoundaryError(f"region differs: {region_id}")
        region_ranges[region_id] = (start, end)
    _decode_x86_regions(image, data, region_ranges)

    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(expected_hex)
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start or start + len(expected) > region_end:
            raise EnemyCandidateScoreBoundaryError(
                f"control window escapes region: {window_id}"
            )
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise EnemyCandidateScoreBoundaryError(
                f"control window differs: {window_id}"
            )

    for edge_id, _source, call_rva, expected_hex, target_rva in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, call_rva, len(expected))
        if actual != expected or _direct_target(call_rva, actual) != target_rva:
            raise EnemyCandidateScoreBoundaryError(f"direct edge differs: {edge_id}")

    for anchor_id, rva, expected in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemyCandidateScoreBoundaryError(
                f"data anchor differs: {anchor_id}"
            )


def build_enemy_candidate_score_boundary_map(executable: Path) -> dict[str, Any]:
    """Build the exact expected artifact after verifying every native input."""
    _verify_dependencies(executable)
    _verify_native(executable)
    return _expected_shape()


def validate_enemy_candidate_score_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields without requiring the installed executable."""
    if not isinstance(value, Mapping):
        raise EnemyCandidateScoreBoundaryError("candidate score map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise EnemyCandidateScoreBoundaryError("candidate score map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "native_pre_post_adjustments_complete": True,
        "complete_candidate_materialization": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_candidate_score_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject byte, dependency, or replay drift."""
    expected = build_enemy_candidate_score_boundary_map(executable)
    if dict(value) != expected:
        raise EnemyCandidateScoreBoundaryError(
            "candidate score map differs from executable analysis"
        )
    result = validate_enemy_candidate_score_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_candidate_score_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
