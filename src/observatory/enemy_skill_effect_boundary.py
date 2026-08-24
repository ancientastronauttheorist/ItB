"""Replay the exact-build native SkillEffect materialization boundary.

This continuation starts with the target cache produced by the adjacent
``GetTargetArea`` wrapper.  It pins the selected-target membership gate,
``GetSkillEffect`` / ``GetFinalEffect_Helper`` dispatch, cache clear/replace,
per-``SpaceDamage`` annotation, Vek Hormones adjustment, and Boost adjustment
on Windows build 13725832.

The concrete Lua ``SkillEffect`` remains an explicit projected input.  The
replay transforms only fields read or written by this native boundary; it does
not fabricate subclass Lua mechanics, presentation records, or a future enemy
phase.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.death_event_credit_boundary import (
    DeathEventCreditBoundaryError,
    validate_death_event_credit_boundary_map_binding,
)
from src.observatory.enemy_target_area_callback_boundary import (
    EnemyTargetAreaCallbackBoundaryError,
    validate_enemy_target_area_callback_boundary_map_binding,
)
from src.observatory.pe_boundary_map import (
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_skill_effect_boundary_map"
REPLAY_KIND = "native_enemy_skill_effect_projection_replay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1
MAX_TARGET_POINTS = 4096
MAX_EFFECT_RECORDS = 4096
MAX_STRING_BYTES = 1 << 20


class EnemySkillEffectBoundaryError(RuntimeError):
    """Raised when the exact SkillEffect boundary cannot reproduce."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
    {
        "id": "enemy_target_area_callback",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_target_area_callback_boundary.json"
        ),
        "file_sha256": (
            "dc45fc0a32b52cff2e6fb400857fadeca85737f8329e9d32f5e6196e77ec6289"
        ),
        "canonical_sha256": (
            "bcac4ea3c6a6e5cec73d95ea27f0edab5ef592de09d135200ea5efb8b66c405f"
        ),
        "role": (
            "Pins the ordered target cache, stored origin/targets, TwoClick "
            "sentinel rule, and callback context immediately before this body."
        ),
    },
    {
        "id": "death_event_credit",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_death_event_credit_boundary.json"
        ),
        "file_sha256": (
            "5f4efd7b808a619630199a1f11628650a7ea09886377a10e3a9e3907587c4688"
        ),
        "canonical_sha256": (
            "780d1000112a4d801dd9df342a6aac5720dcb5d4fdc482c028416f7d9f18bbc7"
        ),
        "role": (
            "Pins SkillEffect.iOwner at +0x5c and its preservation through the "
            "queued-effect copy/dispatch chain."
        ),
    },
)


REGION_SPECS = (
    (
        "lua_string_equal",
        0x0007C7B0,
        0x0007C805,
        "c0a0823d4c48882c5b64ac059812e6b1adcb02780effe5e037e1f46cc0aa74ea",
        "Exact native std::string equality helper used for Move_Power.",
    ),
    (
        "point_vector_append",
        0x000B5080,
        0x000B50F2,
        "5fa5ce9bd76705a63de61684acbfb6b6147c4be3da1e4f86cb9bc991d3f748eb",
        "Complete eight-byte Point vector append helper.",
    ),
    (
        "skill_effect_copy",
        0x00160760,
        0x00160879,
        "30471eac4d66d47a928438248a7d8f26e2c0a6384bafe7b0c02e42b2250efcd6",
        "Complete 0x7c-byte SkillEffect copy constructor.",
    ),
    (
        "friendly_target_predicate",
        0x0016FC50,
        0x0016FC98,
        "aac917614c7bd4bef2cf9cb8f9b8ad78db2898a13648adf674b689bba93a3e69",
        "Board secondary-vtable target-team predicate.",
    ),
    (
        "friendly_owner_predicate",
        0x0016FCF0,
        0x0016FD16,
        "e0e785a3aad74dbaa0d97fd1b12360c2df7ecaf4c82af55faf0866128f75e422",
        "Board secondary-vtable owner-team predicate.",
    ),
    (
        "boosted_owner_predicate",
        0x0016FD20,
        0x0016FD43,
        "74d49bcafae258d46a513bf008f35473918c6b53ebadd95d628c110f5d951a4f",
        "Board secondary-vtable owner Boost predicate.",
    ),
    (
        "skill_effect_move_assign",
        0x00178240,
        0x001783ED,
        "e4312b34a0b20c8e9f06e12335424565a0f069c6bd4f1162a3ac4ecfb5c4a3f3",
        "Complete SkillEffect move-assignment body.",
    ),
    (
        "space_damage_ctor",
        0x001999A0,
        0x00199C3D,
        "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d",
        "Complete default 0x134-byte SpaceDamage constructor.",
    ),
    (
        "pawn_boost_predicate",
        0x00234C70,
        0x00234CC3,
        "8f8552ea81239134b413758ce8e181db99d51903552a9fa2b38f2239880bb290",
        "Pawn Boost/Arrogant_Boost predicate used by the Board wrapper.",
    ),
    (
        "pawn_team_predicate",
        0x0023D860,
        0x0023D931,
        "6f3a65620b7f448715c301400b1d26ce9784879254b5255b5772a1f95ad53906",
        "Pawn team-class predicate; mode six accepts hostile teams.",
    ),
    (
        "skill_effect_clear",
        0x00256250,
        0x002562B0,
        "1a940afe5f395d8cfd6bbd5ae1efdce0d3fbfebb1e93e4d6245b292c81569fa5",
        "Clear both effect vectors, reset iOwner, and clear the private skill key.",
    ),
    (
        "skill_effect_annotation",
        0x00267710,
        0x0026791D,
        "771a522903bf79af9e8e0aad8d137275aedbde53ab1eb8e9cec0d365a3fae647",
        "Annotate both SpaceDamage vectors and return the moved effect.",
    ),
    (
        "skill_effect_materialize",
        0x00268050,
        0x0026833F,
        "6bb49352f06f6b4c19cc0e469e8d6e2a95afc87c8214eb68e85fdd5d5085155a",
        "Selected-target gate, Lua callback dispatch, cache, and postprocess body.",
    ),
    (
        "skill_effect_postprocess",
        0x00268340,
        0x0026856F,
        "595e58ad603664da5ba5270a18c14b93690c929d9e5ee2c36fa0c5ab5a2f673c",
        "Vek Hormones and Boost postprocessor for one SpaceDamage vector.",
    ),
    (
        "get_final_effect_converter",
        0x00271FC0,
        0x0027206C,
        "105f3fbbe975ec6d860d09dfb0f8260619f1a36558188d7e1dc1f42aa6989db4",
        "GetFinalEffect_Helper Lua-result to SkillEffect converter.",
    ),
    (
        "get_skill_effect_converter",
        0x00272190,
        0x00272240,
        "363cb9a295dee60f4a5a20ebdaca51838c6cc8f8d4a1972cba7342d6c520bc40",
        "GetSkillEffect Lua-result to SkillEffect converter.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "target_membership_and_clear",
        "skill_effect_materialize",
        0x00268080,
        "8b871c0100008d9f240100008b8f180100003bc874198b33393175088b51043b5304740783c1083bc875ed3bc8751a8d4f18c703ffffffffc74304ffffffffe88ce1feffe95a020000",
        "Scan cached points; on a miss reset selected target and clear the cached effect.",
    ),
    (
        "two_click_gate",
        "skill_effect_materialize",
        0x002680EA,
        "68fc808300c60000e8d9fed9ff8d8f34010000e8ae12deff84c00f84da00000083bf20020000ff0f84cd00000083bf24020000ff0f84c0000000",
        "Require TwoClick plus both second-target coordinates different from -1.",
    ),
    (
        "final_argument_order",
        "skill_effect_materialize",
        0x00268139,
        "8d872c010000c745fc00000000508d4de4e831cfe4ff8d8720020000508d4de4e822cfe4ff538d4de4e819cfe4ff",
        "Append origin, second target, and selected target in that exact order.",
    ),
    (
        "final_callback_replace",
        "skill_effect_materialize",
        0x00268172,
        "68507f8300e894fcd9ff83ec18c645fc018bc489a554ffffff8d8f3401000050e8b911deff83ec0cc645fc028bcc8d45e4898d50ffffff50e83127e3ff8d8558ffffffc645fc0050e8019e00008d4f1850e87800f1ff",
        "Invoke GetFinalEffect_Helper, convert, and move-replace the effect cache.",
    ),
    (
        "regular_callback_replace",
        "skill_effect_materialize",
        0x002681E4,
        "ff7304ff33ffb730010000ffb72c01000083ec188bcc89a550ffffff68407f8300e806fcd9ff83ec18c745fc030000008d8f3401000054e83011deff8d8558ffffffc745fcffffffff50e85d9f00008d4f1850e80400f1ff",
        "Invoke GetSkillEffect(origin,target), convert, and move-replace the cache.",
    ),
    (
        "explosion_annotation_install",
        "skill_effect_materialize",
        0x00268247,
        "83ec188bf489a550ffffff83ec188bcc68807f8300e8affbd9ff568d8f34010000e8430fdeffc745fc04000000ff73048bb750010000ff338d5f18ffb730010000ffb72c01000083ec7c8bcc53e8c784efff8bd6c745fcffffffff8d8d58ffffffe863f4ffff81c4a40000008bcb50e885fff0ff8d8d58ffffffe8da61eaff",
        "Copy the cache, apply Explosion/origin/source annotations, and replace it.",
    ),
    (
        "owner_key_and_both_postprocess",
        "skill_effect_materialize",
        0x002682C6,
        "8b87880100008d8f340100008947748d45d850e87210deff508d4f78e86921deff8b45ec83f810720f6a014050ff75d8e805f5d9ff83c40c538bcfc745ec0f000000c745e800000000c645d800e8280000008d47248bcf50e81d000000",
        "Write iOwner and the private skill key, then postprocess effect before q_effect.",
    ),
    (
        "first_record_annotation",
        "skill_effect_annotation",
        0x002677A0,
        "837c3e4800751c8d4f3803ce8d85940000003bc8740d6aff6a0050e81009daff8b750883bc3e9c000000ff8d0c3e752483b9a0000000ff751b8b858400000089819c0000008b85880000008981a00000008b75088b45f04389843ec0000000",
        "For effect records, default empty sAnimation and (-1,-1) origin, then write +0xc0.",
    ),
    (
        "second_record_annotation",
        "skill_effect_annotation",
        0x00267850,
        "837c3e4800751c8d4f3803ce8d85940000003bc8740d6aff6a0050e86008daff8b751483bc3e9c000000ff8d0c3e752483b9a0000000ff751b8b858400000089819c0000008b85880000008981a00000008b75148b45f04389843ec0000000",
        "Repeat the same annotation for q_effect records.",
    ),
    (
        "friendly_fire_gate_and_amount",
        "skill_effect_postprocess",
        0x0026834C,
        "83ec188bd98bcc6a14c741140f000000c741100000000068687f8300c60100e860fcd9ffe88b63ffff8b750883c41884c00f84120100008b8b100100006a06ffb3880100008b018b8084000000ffd084c00f84f200000083ec18c7442428010000008bcc68a47f8300e856fad9ffe84163ffff83c41884c0740ac744241003000000eb3e83ec188bcc688c7f8300e831fad9ffe81c63ffff83c41884c0751b83ec188bcc68bc7f8300e816fad9ffe80163ffff83c41884c07408c744241002000000",
        "Base Vek Hormones plus hostile owner gate; AB=3, A/B=2, base=1.",
    ),
    (
        "friendly_fire_record_adjust",
        "skill_effect_postprocess",
        0x00268430,
        "8b168b443a083df4010000743285c07e2e3de803000074278b8b100100006a06ff743a048b01ff343a8b8088000000ffd084c0740a8b068b4c2410014c0708",
        "Add the Vek Hormones amount only to positive non-500/non-1000 damage on hostile targets.",
    ),
    (
        "boost_gate",
        "skill_effect_postprocess",
        0x00268495,
        "837b141072048b0beb028bcb8b7b10b8040000003bf8baa0a782000f42c750e8f73ce0ff83c40485c0750b83ff0472060f869b000000ba888083008bcbe8d942e1ff84c00f85870000008b8b10010000ffb3880100008b018b808c000000ffd084c0746d",
        "Exclude exact Move and Move_Power, then require the owner Boost predicate.",
    ),
    (
        "boost_record_adjust",
        "skill_effect_postprocess",
        0x00268515,
        "8b0e03cf8b510881faf4010000741d85d27e0e81fae803000074068d42018941088d420983f8087703ff4908c6413101",
        "Boost regular positive damage by one, -9..-1 by minus one, and set private byte +0x31.",
    ),
    (
        "effect_clear_fields",
        "skill_effect_clear",
        0x00256253,
        "8bf98b5f108b770c3bf37412908bcee83980ebff81c6340100003bf375ef8b470c8947108b5f048b373bf374118bcee81980ebff81c6340100003bf375ef8b078d4f606a0089470468dcdf8000c7475cffffffffe8241ddbff",
        "Destroy q_effect then effect records, set iOwner=-1, and clear +0x60.",
    ),
)


DIRECT_EDGE_SPECS = (
    ("miss_to_clear", "skill_effect_materialize", 0x002680BF, "e88ce1feff", "skill_effect_clear", 0x00256250, "Clear on target-cache miss."),
    ("append_origin", "skill_effect_materialize", 0x0026814A, "e831cfe4ff", "point_vector_append", 0x000B5080, "Append origin first."),
    ("append_second", "skill_effect_materialize", 0x00268159, "e822cfe4ff", "point_vector_append", 0x000B5080, "Append second target second."),
    ("append_selected", "skill_effect_materialize", 0x00268162, "e819cfe4ff", "point_vector_append", 0x000B5080, "Append selected target third."),
    ("convert_final", "skill_effect_materialize", 0x002681BA, "e8019e0000", "get_final_effect_converter", 0x00271FC0, "Convert final-effect result."),
    ("install_final", "skill_effect_materialize", 0x002681C3, "e87800f1ff", "skill_effect_move_assign", 0x00178240, "Install final effect."),
    ("convert_regular", "skill_effect_materialize", 0x0026822E, "e85d9f0000", "get_skill_effect_converter", 0x00272190, "Convert regular effect result."),
    ("install_regular", "skill_effect_materialize", 0x00268237, "e80400f1ff", "skill_effect_move_assign", 0x00178240, "Install regular effect."),
    ("copy_for_annotation", "skill_effect_materialize", 0x00268294, "e8c784efff", "skill_effect_copy", 0x00160760, "Copy complete cached effect."),
    ("annotate_effect", "skill_effect_materialize", 0x002682A8, "e863f4ffff", "skill_effect_annotation", 0x00267710, "Annotate both record vectors."),
    ("install_annotation", "skill_effect_materialize", 0x002682B6, "e885fff0ff", "skill_effect_move_assign", 0x00178240, "Install annotated copy."),
    ("postprocess_effect", "skill_effect_materialize", 0x00268313, "e828000000", "skill_effect_postprocess", 0x00268340, "Postprocess effect vector first."),
    ("postprocess_q_effect", "skill_effect_materialize", 0x0026831E, "e81d000000", "skill_effect_postprocess", 0x00268340, "Postprocess q_effect vector second."),
)


CALL_INVENTORY_SPECS = (
    (
        "skill_effect_materialize_callers",
        0x00268050,
        (
            (0x0016B0DB, "Board master-update cache refresh path 1"),
            (0x0016B6FC, "Board master-update cache refresh path 2"),
            (0x0016E7CF, "Board actor traversal cache refresh"),
            (0x00228044, "SkillManager queued-target refresh"),
            (0x00228F44, "SkillManager translated-target refresh"),
            (0x002689B9, "Skill origin/target update"),
            (0x0026A223, "Skill secondary-effect refresh"),
            (0x0026A7FE, "Skill target reset"),
        ),
    ),
    (
        "skill_effect_annotation_callers",
        0x00267710,
        (
            (0x0022E9DD, "additional native SkillEffect annotation path 1"),
            (0x0022ED2A, "additional native SkillEffect annotation path 2"),
            (0x002682A8, "reviewed Skill cache materialization path"),
        ),
    ),
)


DATA_ANCHOR_SPECS = (
    ("move_id", 0x0042A7A0, ".rdata", "4d6f766500", "Exact Move Skill ID used by the Boost exclusion."),
    ("arrogant_boost", 0x00436608, ".rdata", "4172726f67616e745f426f6f737400", "Exact Arrogant_Boost field used by Pawn Boost evaluation."),
    ("get_skill_effect", 0x00437F40, ".rdata", "476574536b696c6c45666665637400", "Exact GetSkillEffect callback name."),
    ("get_final_effect_helper", 0x00437F50, ".rdata", "47657446696e616c4566666563745f48656c70657200", "Exact GetFinalEffect_Helper callback name."),
    ("passive_friendly_fire", 0x00437F68, ".rdata", "506173736976655f467269656e646c794669726500", "Exact Vek Hormones base passive ID."),
    ("explosion", 0x00437F80, ".rdata", "4578706c6f73696f6e00", "Exact Explosion field name."),
    ("passive_friendly_fire_a", 0x00437F8C, ".rdata", "506173736976655f467269656e646c79466972655f4100", "Exact Vek Hormones A ID."),
    ("passive_friendly_fire_ab", 0x00437FA4, ".rdata", "506173736976655f467269656e646c79466972655f414200", "Exact Vek Hormones AB ID."),
    ("passive_friendly_fire_b", 0x00437FBC, ".rdata", "506173736976655f467269656e646c79466972655f4200", "Exact Vek Hormones B ID."),
    ("move_power_id", 0x00438088, ".rdata", "4d6f76655f506f77657200", "Exact Move_Power Skill ID used by the Boost exclusion."),
    ("two_click", 0x004380FC, ".rdata", "54776f436c69636b00", "Exact TwoClick field name."),
    ("i_damage", 0x00438A98, ".rdata", "6944616d61676500", "Registered SpaceDamage iDamage name."),
    ("s_animation", 0x00438AD4, ".rdata", "73416e696d6174696f6e00", "Registered SpaceDamage sAnimation name."),
    ("friendly_owner_slot", 0x0042E2DC, ".rdata", "f0fc5600", "Board secondary slot +0x84 points to RVA 0x0016fcf0."),
    ("friendly_target_slot", 0x0042E2E0, ".rdata", "50fc5600", "Board secondary slot +0x88 points to RVA 0x0016fc50."),
    ("boosted_owner_slot", 0x0042E2E4, ".rdata", "20fd5600", "Board secondary slot +0x8c points to RVA 0x0016fd20."),
)


INSTRUCTION_ANCHOR_SPECS = (
    ("register_s_animation", 0x0027ADB9, "6a3868d48a8300", "Bind SpaceDamage.sAnimation to +0x38."),
    ("register_i_damage", 0x0027ADF8, "6a0868988a8300", "Bind SpaceDamage.iDamage to +0x08."),
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
        raise EnemySkillEffectBoundaryError(f"not a regular dependency: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemySkillEffectBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemySkillEffectBoundaryError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    return data[offset : offset + size]


def _rel32_target(rva: int, encoded: bytes, opcode: int) -> int:
    if len(encoded) != 5 or encoded[0] != opcode:
        raise EnemySkillEffectBoundaryError("expected a five-byte rel32 instruction")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None:
        raise EnemySkillEffectBoundaryError("missing .text section")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    sites: set[int] = set()
    for offset in range(0, max(0, len(body) - 4)):
        if body[offset] != 0xE8:
            continue
        site = section.virtual_address + offset
        if _rel32_target(site, body[offset : offset + 5], 0xE8) == target_rva:
            sites.add(site)
    return sites


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EnemySkillEffectBoundaryError(f"{label} must be Boolean")
    return value


def _require_i32(value: Any, label: str) -> int:
    if type(value) is not int or not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemySkillEffectBoundaryError(f"{label} must be a signed 32-bit integer")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise EnemySkillEffectBoundaryError(f"{label} must be a string")
    if len(value.encode("utf-8")) > MAX_STRING_BYTES:
        raise EnemySkillEffectBoundaryError(f"{label} exceeds its byte cap")
    return value


def _normalize_point(value: Any, label: str) -> list[int]:
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemySkillEffectBoundaryError(f"{label} must be [x,y]")
    return [
        _require_i32(value[0], f"{label}.x"),
        _require_i32(value[1], f"{label}.y"),
    ]


def _normalize_points(value: Any, label: str) -> list[list[int]]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(value, Sequence):
        raise EnemySkillEffectBoundaryError(f"{label} must be a point array")
    if len(value) > MAX_TARGET_POINTS:
        raise EnemySkillEffectBoundaryError(f"{label} exceeds its point cap")
    return [_normalize_point(point, f"{label}[{index}]") for index, point in enumerate(value)]


_RECORD_FIELDS = {
    "loc",
    "iDamage",
    "sAnimation",
    "piOrigin",
    "native_source_tag",
    "native_boost_marker",
}
_EFFECT_FIELDS = {"effect", "q_effect", "iOwner", "native_skill_key"}
_PASSIVE_FIELDS = {"base", "a", "b", "ab"}


def _normalize_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RECORD_FIELDS:
        raise EnemySkillEffectBoundaryError(f"{label} fields differ from the projection schema")
    return {
        "loc": _normalize_point(value["loc"], f"{label}.loc"),
        "iDamage": _require_i32(value["iDamage"], f"{label}.iDamage"),
        "sAnimation": _require_string(value["sAnimation"], f"{label}.sAnimation"),
        "piOrigin": _normalize_point(value["piOrigin"], f"{label}.piOrigin"),
        "native_source_tag": _require_i32(
            value["native_source_tag"], f"{label}.native_source_tag"
        ),
        "native_boost_marker": _require_bool(
            value["native_boost_marker"], f"{label}.native_boost_marker"
        ),
    }


def _normalize_record_list(value: Any, label: str) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(value, Sequence):
        raise EnemySkillEffectBoundaryError(f"{label} must be a record array")
    if len(value) > MAX_EFFECT_RECORDS:
        raise EnemySkillEffectBoundaryError(f"{label} exceeds its record cap")
    return [_normalize_record(record, f"{label}[{index}]") for index, record in enumerate(value)]


def _normalize_effect(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _EFFECT_FIELDS:
        raise EnemySkillEffectBoundaryError(f"{label} fields differ from the projection schema")
    return {
        "effect": _normalize_record_list(value["effect"], f"{label}.effect"),
        "q_effect": _normalize_record_list(value["q_effect"], f"{label}.q_effect"),
        "iOwner": _require_i32(value["iOwner"], f"{label}.iOwner"),
        "native_skill_key": _require_string(
            value["native_skill_key"], f"{label}.native_skill_key"
        ),
    }


def _normalize_optional_effect(value: Any, label: str) -> dict[str, Any] | None:
    return None if value is None else _normalize_effect(value, label)


def _normalize_passives(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != _PASSIVE_FIELDS:
        raise EnemySkillEffectBoundaryError("friendly_fire_passives fields differ")
    return {name: _require_bool(value[name], f"friendly_fire_passives.{name}") for name in sorted(_PASSIVE_FIELDS)}


def _wrap_i32(value: int) -> int:
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _record_ref(list_name: str, index: int) -> dict[str, Any]:
    return {"list": list_name, "index": index}


def _adjustment(list_name: str, index: int, before: int, after: int) -> dict[str, Any]:
    return {"list": list_name, "index": index, "before": before, "after": after}


def replay_enemy_skill_effect_boundary(
    *,
    cached_target_points: Sequence[Any],
    selected_target: Sequence[Any],
    origin: Sequence[Any],
    two_click: bool,
    second_target: Sequence[Any],
    cached_effect: Mapping[str, Any],
    get_skill_effect: Mapping[str, Any] | None,
    get_final_effect: Mapping[str, Any] | None,
    explosion: str,
    skill_source_tag: int,
    owner_id: int,
    skill_id: str,
    skill_key: str,
    friendly_fire_passives: Mapping[str, Any],
    friendly_fire_owner_matches_team6: bool,
    friendly_fire_target_points: Sequence[Any],
    owner_boosted: bool,
) -> dict[str, Any]:
    """Replay the native boundary over its exact observable projection."""

    cached_points = _normalize_points(cached_target_points, "cached_target_points")
    selected = _normalize_point(selected_target, "selected_target")
    origin_point = _normalize_point(origin, "origin")
    second = _normalize_point(second_target, "second_target")
    two_click_value = _require_bool(two_click, "two_click")
    current_effect = _normalize_effect(cached_effect, "cached_effect")
    regular_effect = _normalize_optional_effect(get_skill_effect, "get_skill_effect")
    final_effect = _normalize_optional_effect(get_final_effect, "get_final_effect")
    explosion_value = _require_string(explosion, "explosion")
    source_tag = _require_i32(skill_source_tag, "skill_source_tag")
    owner = _require_i32(owner_id, "owner_id")
    skill_id_value = _require_string(skill_id, "skill_id")
    skill_key_value = _require_string(skill_key, "skill_key")
    passives = _normalize_passives(friendly_fire_passives)
    friendly_owner = _require_bool(
        friendly_fire_owner_matches_team6,
        "friendly_fire_owner_matches_team6",
    )
    friendly_targets = _normalize_points(
        friendly_fire_target_points, "friendly_fire_target_points"
    )
    boosted = _require_bool(owner_boosted, "owner_boosted")

    target_was_cached = selected in cached_points
    if not target_was_cached:
        if regular_effect is not None or final_effect is not None:
            raise EnemySkillEffectBoundaryError(
                "a target-cache miss must not supply either callback result"
            )
        current_effect["effect"] = []
        current_effect["q_effect"] = []
        current_effect["iOwner"] = -1
        current_effect["native_skill_key"] = ""
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": REPLAY_KIND,
            "target_was_cached": False,
            "selected_target": [-1, -1],
            "callback": None,
            "callback_arguments": None,
            "cache_action": "clear",
            "cached_effect": current_effect,
            "postprocess": None,
        }

    use_final = two_click_value and second[0] != -1 and second[1] != -1
    if use_final:
        if final_effect is None or regular_effect is not None:
            raise EnemySkillEffectBoundaryError(
                "GetFinalEffect_Helper requires only its selected projection"
            )
        materialized = copy.deepcopy(final_effect)
        callback = "GetFinalEffect_Helper"
        callback_arguments: dict[str, Any] = {
            "ordered_points": [origin_point, second, selected]
        }
    else:
        if regular_effect is None or final_effect is not None:
            raise EnemySkillEffectBoundaryError(
                "GetSkillEffect requires only its selected projection"
            )
        materialized = copy.deepcopy(regular_effect)
        callback = "GetSkillEffect"
        callback_arguments = {"origin": origin_point, "target": selected}

    explosion_defaulted: list[dict[str, Any]] = []
    origin_defaulted: list[dict[str, Any]] = []
    source_tag_written: list[dict[str, Any]] = []
    for list_name in ("effect", "q_effect"):
        for index, record in enumerate(materialized[list_name]):
            reference = _record_ref(list_name, index)
            if record["sAnimation"] == "":
                record["sAnimation"] = explosion_value
                explosion_defaulted.append(reference)
            if record["piOrigin"] == [-1, -1]:
                record["piOrigin"] = list(origin_point)
                origin_defaulted.append(reference)
            record["native_source_tag"] = source_tag
            source_tag_written.append(reference)

    materialized["iOwner"] = owner
    materialized["native_skill_key"] = skill_key_value

    friendly_bonus = 0
    if passives["base"] and friendly_owner:
        if passives["ab"]:
            friendly_bonus = 3
        elif passives["a"] or passives["b"]:
            friendly_bonus = 2
        else:
            friendly_bonus = 1
    friendly_target_set = {tuple(point) for point in friendly_targets}
    friendly_adjustments: list[dict[str, Any]] = []
    boost_adjustments: list[dict[str, Any]] = []
    boost_marked: list[dict[str, Any]] = []
    boost_active = boosted and skill_id_value not in {"Move", "Move_Power"}

    for list_name in ("effect", "q_effect"):
        for index, record in enumerate(materialized[list_name]):
            damage = record["iDamage"]
            if (
                friendly_bonus
                and damage > 0
                and damage not in {500, 1000}
                and tuple(record["loc"]) in friendly_target_set
            ):
                after = _wrap_i32(damage + friendly_bonus)
                record["iDamage"] = after
                friendly_adjustments.append(
                    _adjustment(list_name, index, damage, after)
                )

            if boost_active:
                before = record["iDamage"]
                after = before
                if before != 500:
                    if before > 0 and before != 1000:
                        after = _wrap_i32(before + 1)
                    if -9 <= before <= -1:
                        after = _wrap_i32(after - 1)
                record["iDamage"] = after
                record["native_boost_marker"] = True
                boost_marked.append(_record_ref(list_name, index))
                if after != before:
                    boost_adjustments.append(
                        _adjustment(list_name, index, before, after)
                    )

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": REPLAY_KIND,
        "target_was_cached": True,
        "selected_target": selected,
        "callback": callback,
        "callback_arguments": callback_arguments,
        "cache_action": "replace",
        "cached_effect": materialized,
        "postprocess": {
            "vector_order": ["effect", "q_effect"],
            "explosion_defaulted": explosion_defaulted,
            "origin_defaulted": origin_defaulted,
            "source_tag_written": source_tag_written,
            "iOwner_written": owner,
            "native_skill_key_written": skill_key_value,
            "friendly_fire": {
                "active": friendly_bonus > 0,
                "bonus": friendly_bonus,
                "adjustments": friendly_adjustments,
            },
            "boost": {
                "active": boost_active,
                "adjustments": boost_adjustments,
                "marked": boost_marked,
            },
        },
    }


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {"id": region_id, "start": start, "end": end, "sha256": digest, "basis": basis}
        for region_id, start, end, digest, basis in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {"id": window_id, "region_id": region_id, "rva": rva, "bytes": encoded, "meaning": meaning}
        for window_id, region_id, rva, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "call_rva": call_rva,
            "bytes": encoded,
            "target_region": target_region,
            "target_rva": target_rva,
            "meaning": meaning,
        }
        for edge_id, source_region, call_rva, encoded, target_region, target_rva, meaning in DIRECT_EDGE_SPECS
    ]


def _call_inventory_records() -> list[dict[str, Any]]:
    return [
        {
            "id": inventory_id,
            "target_rva": target_rva,
            "sites": [{"rva": site, "role": role} for site, role in sites],
        }
        for inventory_id, target_rva, sites in CALL_INVENTORY_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {"id": anchor_id, "rva": rva, "section": section, "bytes": encoded, "meaning": meaning}
        for anchor_id, rva, section, encoded, meaning in DATA_ANCHOR_SPECS
    ]


def _instruction_anchor_records() -> list[dict[str, Any]]:
    return [
        {"id": anchor_id, "rva": rva, "bytes": encoded, "meaning": meaning}
        for anchor_id, rva, encoded, meaning in INSTRUCTION_ANCHOR_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "skill_layout": {
            "cached_effect": "+0x18",
            "cached_target_points": "+0x118..+0x120",
            "selected_target": "+0x124/+0x128",
            "origin": "+0x12c/+0x130",
            "lua_skill_key": "+0x134",
            "native_source_tag": "+0x150",
            "owner_id": "+0x188",
            "second_target": "+0x220/+0x224",
        },
        "skill_effect_layout": {
            "size": "0x7c",
            "effect_vector": "+0x00",
            "q_effect_vector": "+0x0c",
            "iOwner": "+0x5c",
            "private_skill_key": "+0x60",
        },
        "space_damage_projection": {
            "stride": "0x134",
            "loc": "+0x00/+0x04",
            "iDamage": "+0x08",
            "sAnimation": "+0x38",
            "sAnimation_length": "+0x48",
            "private_boost_marker": "+0x31",
            "private_origin": "+0x9c/+0xa0",
            "private_source_tag": "+0xc0",
        },
        "target_membership": {
            "comparison": "ordered linear scan for exact x/y equality",
            "miss_selected_target": [-1, -1],
            "miss_callback_count": 0,
            "miss_cache_action": "clear both vectors, iOwner=-1, private key empty",
        },
        "callback_dispatch": {
            "regular": "GetSkillEffect(origin, selected_target)",
            "final": "GetFinalEffect_Helper([origin, second_target, selected_target])",
            "final_gate": "TwoClick and second_target.x != -1 and second_target.y != -1",
            "cache_install": "move-replace complete converted SkillEffect",
        },
        "annotation_order": [
            "default empty sAnimation from Explosion",
            "default private origin only when both coordinates are -1",
            "overwrite private source tag",
            "write SkillEffect.iOwner",
            "write SkillEffect private skill key",
            "postprocess effect",
            "postprocess q_effect",
        ],
        "friendly_fire": {
            "shipped_name": "Vek Hormones",
            "base_required": True,
            "owner_team_mode": 6,
            "target_team_mode": 6,
            "base_bonus": 1,
            "a_or_b_bonus": 2,
            "ab_bonus": 3,
            "damage_gate": "iDamage > 0 and iDamage != 500 and iDamage != 1000",
        },
        "boost": {
            "excluded_exact_skill_ids": ["Move", "Move_Power"],
            "positive_adjust": "+1 except 500 and 1000",
            "negative_adjust": "-1 only for original values -9 through -1",
            "marker_write": "private record byte +0x31 = 1 for every record",
            "integer_arithmetic": "32-bit wrapping",
        },
        "projection_boundary": {
            "lua_skill_effect_payload_is_input": True,
            "unmentioned_record_fields_are_not_fabricated": True,
            "board_team_and_boost_predicate_results_are_inputs": True,
            "complete_enemy_phase_is_not_forecast": True,
        },
    }


def _record(
    loc: tuple[int, int],
    damage: int,
    *,
    animation: str = "",
    pi_origin: tuple[int, int] = (-1, -1),
    source_tag: int = 2,
    boost_marker: bool = False,
) -> dict[str, Any]:
    return {
        "loc": list(loc),
        "iDamage": damage,
        "sAnimation": animation,
        "piOrigin": list(pi_origin),
        "native_source_tag": source_tag,
        "native_boost_marker": boost_marker,
    }


def _effect(effect: list[dict[str, Any]], q_effect: list[dict[str, Any]]) -> dict[str, Any]:
    return {"effect": effect, "q_effect": q_effect, "iOwner": -1, "native_skill_key": "old"}


def _base_input() -> dict[str, Any]:
    return {
        "cached_target_points": [[2, 3]],
        "selected_target": [2, 3],
        "origin": [4, 5],
        "two_click": False,
        "second_target": [-1, -1],
        "cached_effect": _effect([_record((0, 0), 9)], []),
        "get_skill_effect": _effect([_record((2, 3), 1)], []),
        "get_final_effect": None,
        "explosion": "ExploAir2",
        "skill_source_tag": 1,
        "owner_id": 17,
        "skill_id": "FireflyAtk1",
        "skill_key": "FireflyAtk1",
        "friendly_fire_passives": {"base": False, "a": False, "b": False, "ab": False},
        "friendly_fire_owner_matches_team6": False,
        "friendly_fire_target_points": [],
        "owner_boosted": False,
    }


def _replay_vectors() -> list[dict[str, Any]]:
    vectors: list[tuple[str, dict[str, Any]]] = []
    vectors.append(("regular_callback", _base_input()))

    invalid = _base_input()
    invalid["selected_target"] = [7, 7]
    invalid["get_skill_effect"] = None
    vectors.append(("target_cache_miss_clears", invalid))

    final = _base_input()
    final["two_click"] = True
    final["second_target"] = [6, 5]
    final["get_skill_effect"] = None
    final["get_final_effect"] = _effect(
        [_record((2, 3), 2, animation="kept", pi_origin=(-1, 4))],
        [_record((1, 1), -1)],
    )
    final["owner_boosted"] = True
    vectors.append(("final_order_and_boost", final))

    partial_sentinel = _base_input()
    partial_sentinel["two_click"] = True
    partial_sentinel["second_target"] = [-1, -2]
    vectors.append(("partial_minus_one_uses_regular", partial_sentinel))

    hormones = _base_input()
    hormones["get_skill_effect"] = _effect(
        [_record((2, 3), 499), _record((9, 9), 4)],
        [_record((2, 3), 1000)],
    )
    hormones["friendly_fire_passives"] = {"base": True, "a": False, "b": False, "ab": True}
    hormones["friendly_fire_owner_matches_team6"] = True
    hormones["friendly_fire_target_points"] = [[2, 3]]
    hormones["owner_boosted"] = True
    vectors.append(("hormones_then_boost", hormones))

    move = _base_input()
    move["skill_id"] = "Move_Power"
    move["owner_boosted"] = True
    vectors.append(("move_power_excludes_boost", move))

    return [
        {"id": vector_id, "input": payload, "expected": replay_enemy_skill_effect_boundary(**payload)}
        for vector_id, payload in vectors
    ]


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "selected_target_membership_is_hard_gate",
            "classification": "fact",
            "claim": (
                "The selected target must match one cached Point exactly. A miss resets "
                "the selected target, invokes no Lua effect callback, clears both cached "
                "record vectors, sets iOwner=-1, and clears the private skill key."
            ),
        },
        {
            "id": "two_click_final_argument_order",
            "classification": "fact",
            "claim": (
                "TwoClick plus two non-minus-one second-target coordinates selects "
                "GetFinalEffect_Helper with [origin, second target, selected target]; "
                "all other cached-target cases use GetSkillEffect(origin,target)."
            ),
        },
        {
            "id": "callback_result_replaces_complete_cache",
            "classification": "fact",
            "claim": (
                "Each selected Lua result is converted to a complete SkillEffect and "
                "move-assigned over the prior cache before native annotations."
            ),
        },
        {
            "id": "both_record_vectors_receive_annotations",
            "classification": "fact",
            "claim": (
                "Every record in effect and q_effect receives the same ordered pass: "
                "empty sAnimation defaults from Explosion, (-1,-1) private origin "
                "defaults from the Skill origin, and private +0xc0 is overwritten from "
                "Skill +0x150."
            ),
        },
        {
            "id": "owner_and_skill_key_written_before_damage_postprocess",
            "classification": "fact",
            "claim": (
                "Skill +0x188 is written to SkillEffect.iOwner +0x5c and the Skill's "
                "Lua lookup key is copied to private effect +0x60 before effect then "
                "q_effect are postprocessed."
            ),
        },
        {
            "id": "vek_hormones_adjustment_is_exact",
            "classification": "fact",
            "claim": (
                "Vek Hormones requires a hostile owner and hostile target. It adds "
                "one for base, two for A or B, and three for AB only to positive "
                "iDamage values other than 500 and 1000."
            ),
        },
        {
            "id": "boost_adjustment_is_exact",
            "classification": "fact",
            "claim": (
                "For a Boosted owner and any exact Skill ID except Move/Move_Power, "
                "native code adds one to regular positive damage, subtracts one from "
                "-9..-1, leaves 500/1000 special values alone, and sets private +0x31 "
                "on every record."
            ),
        },
        {
            "id": "this_is_not_the_enemy_scorer",
            "classification": "scope",
            "claim": (
                "The exact eight-caller inventory binds this as a Skill effect-cache "
                "materializer used by Board/SkillManager/Skill refresh paths. It does "
                "not by itself prove where a Lua GetSkillEffect body participates in "
                "enemy candidate scoring."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "concrete_lua_skill_effect_payloads",
            "question": "What complete record payload does every Lua weapon subclass return?",
            "static_status": "Converters and cache ownership are exact; subclass record construction remains Lua-defined.",
            "next_evidence": "Use source-exact subclass models or bounded callback traces as mechanic-specific inputs.",
        },
        {
            "id": "private_source_tag_friendly_name",
            "question": "What shipped C++ enum name corresponds to Skill +0x150 / SpaceDamage +0xc0?",
            "static_status": "Construction, default value, overwrite, copies, and offsets are exact; the debug symbol/name is absent.",
            "next_evidence": "Name it only if another registration/archive/RTTI path exposes the enum label.",
        },
        {
            "id": "full_board_predicate_reconstruction",
            "question": "Can every owner/target team and Boost predicate be rebuilt prospectively from ordinary solver input?",
            "static_status": "Native predicates are pinned, but the pure projection accepts their resolved Boolean/point results.",
            "next_evidence": "Join exact Board/Pawn state only where settled bridge fields do not already decide the predicate.",
        },
        {
            "id": "enemy_score_side_effect_route",
            "question": "Which Lua GetSkillEffect invocations are score-side effects versus cache/execution materialization?",
            "static_status": "This body's complete direct callers are known; no caller is labeled as the candidate-score wrapper itself.",
            "next_evidence": "Trace Lua-level call ancestry or finish the separate score-side Lua/native call graph.",
        },
        {
            "id": "complete_enemy_phase",
            "question": "Can this projection replace the settled queued-action bridge state?",
            "static_status": "No. Candidate payloads, subclass Lua mechanics, shared RNG entry state, and later action scheduling remain inputs.",
            "next_evidence": "Keep the settled queue authoritative and convert only proven mismatch-specific mechanics into Rust tests.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    dependencies = _dependency_records()
    regions = _region_records()
    windows = _control_window_records()
    direct_edges = _direct_edge_records()
    call_inventories = _call_inventory_records()
    data_anchors = _data_anchor_records()
    instruction_anchors = _instruction_anchor_records()
    vectors = _replay_vectors()
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable": "Breach.exe",
            "sha256": EXPECTED_EXECUTABLE_SHA256,
            "size": EXPECTED_EXECUTABLE_SIZE,
            "architecture": "x86",
            "bits": 32,
            "image_base": EXPECTED_IMAGE_BASE,
        },
        "dependencies": dependencies,
        "native_regions": regions,
        "control_windows": windows,
        "direct_edges": direct_edges,
        "call_inventories": call_inventories,
        "data_anchors": data_anchors,
        "instruction_anchors": instruction_anchors,
        "contracts": _contracts(),
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "parameterized_native_materializer_complete": True,
            "target_membership_and_clear_complete": True,
            "callback_selection_and_argument_order_complete": True,
            "annotation_and_damage_postprocess_complete": True,
            "concrete_lua_skill_effect_payloads_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": len(dependencies),
            "region_count": len(regions),
            "control_window_count": len(windows),
            "direct_edge_count": len(direct_edges),
            "call_inventory_count": len(call_inventories),
            "data_anchor_count": len(data_anchors),
            "instruction_anchor_count": len(instruction_anchors),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "parameterized_native_materializer_complete": True,
            "target_membership_and_clear_complete": True,
            "callback_selection_and_argument_order_complete": True,
            "annotation_and_damage_postprocess_complete": True,
            "concrete_lua_skill_effect_payloads_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _verify_dependencies() -> None:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemySkillEffectBoundaryError(f"dependency file differs: {spec['id']}")
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemySkillEffectBoundaryError(f"dependency fields differ: {spec['id']}")
        values[spec["id"]] = value
    try:
        validate_enemy_target_area_callback_boundary_map_binding(
            values["enemy_target_area_callback"]
        )
        validate_death_event_credit_boundary_map_binding(values["death_event_credit"])
    except (EnemyTargetAreaCallbackBoundaryError, DeathEventCreditBoundaryError) as exc:
        raise EnemySkillEffectBoundaryError(f"native dependency binding differs: {exc}") from exc


def _verify_native(executable: Path) -> None:
    data, image, executable_sha256 = _load_executable(executable)
    if executable_sha256 != EXPECTED_EXECUTABLE_SHA256:
        raise EnemySkillEffectBoundaryError("executable SHA-256 differs")
    if len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise EnemySkillEffectBoundaryError("executable size differs")
    if image.architecture != "x86" or image.bits != 32:
        raise EnemySkillEffectBoundaryError("expected a PE32 x86 executable")
    if image.image_base != EXPECTED_IMAGE_BASE:
        raise EnemySkillEffectBoundaryError("PE image base differs")

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        body = _region_bytes(image, data, start, end - start, ".text", region_id)
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise EnemySkillEffectBoundaryError(f"region differs: {region_id}")
        region_ranges[region_id] = (start, end)
    decoded_regions = _decode_x86_regions(image, data, region_ranges)

    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(expected_hex)
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start or start + len(expected) > region_end:
            raise EnemySkillEffectBoundaryError(f"control window escapes region: {window_id}")
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise EnemySkillEffectBoundaryError(f"control window differs: {window_id}")
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded_regions[region_id].get(cursor)
            if instruction is None:
                raise EnemySkillEffectBoundaryError(
                    f"control window is not instruction-aligned: {window_id}"
                )
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise EnemySkillEffectBoundaryError(
                f"control window ends inside an instruction: {window_id}"
            )

    for edge_id, _source, call_rva, expected_hex, _target_id, target_rva, _meaning in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, call_rva, len(expected))
        if actual != expected or _rel32_target(call_rva, actual, 0xE8) != target_rva:
            raise EnemySkillEffectBoundaryError(f"direct edge differs: {edge_id}")

    for inventory_id, target_rva, sites in CALL_INVENTORY_SPECS:
        expected_sites = {site for site, _role in sites}
        if _raw_rel32_call_sites(image, data, target_rva) != expected_sites:
            raise EnemySkillEffectBoundaryError(
                f"direct-call inventory differs: {inventory_id}"
            )

    for anchor_id, rva, expected_section, expected_hex, _meaning in DATA_ANCHOR_SPECS:
        expected = bytes.fromhex(expected_hex)
        section = next(
            (
                candidate
                for candidate in image.sections
                if candidate.virtual_address <= rva
                and rva + len(expected) <= candidate.virtual_address + candidate.raw_size
            ),
            None,
        )
        if section is None or section.name != expected_section:
            raise EnemySkillEffectBoundaryError(f"data anchor section differs: {anchor_id}")
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemySkillEffectBoundaryError(f"data anchor differs: {anchor_id}")
        if anchor_id.endswith("_slot"):
            target = struct.unpack("<I", expected)[0] - EXPECTED_IMAGE_BASE
            expected_target = {
                "friendly_owner_slot": 0x0016FCF0,
                "friendly_target_slot": 0x0016FC50,
                "boosted_owner_slot": 0x0016FD20,
            }[anchor_id]
            if target != expected_target:
                raise EnemySkillEffectBoundaryError(f"vtable target differs: {anchor_id}")

    instruction_ranges: dict[str, tuple[int, int]] = {}
    for anchor_id, rva, expected_hex, _meaning in INSTRUCTION_ANCHOR_SPECS:
        expected = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemySkillEffectBoundaryError(f"instruction anchor differs: {anchor_id}")
        instruction_ranges[anchor_id] = (rva, rva + len(expected))
    _decode_x86_regions(image, data, instruction_ranges)


def build_enemy_skill_effect_boundary_map(executable: Path) -> dict[str, Any]:
    """Build the exact expected artifact after verifying native inputs."""
    _verify_dependencies()
    _verify_native(executable)
    return _expected_shape()


def validate_enemy_skill_effect_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the executable."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemySkillEffectBoundaryError("SkillEffect boundary fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "parameterized_native_materializer_complete": True,
        "concrete_lua_skill_effect_payloads_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_skill_effect_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject byte, dependency, or replay drift."""
    expected = build_enemy_skill_effect_boundary_map(executable)
    if dict(value) != expected:
        raise EnemySkillEffectBoundaryError(
            "SkillEffect boundary map differs from exact-build analysis"
        )
    result = validate_enemy_skill_effect_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_skill_effect_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
