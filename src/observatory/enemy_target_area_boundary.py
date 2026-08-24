"""Replay the exact-build native enemy target-area eligibility boundary.

The Windows enemy candidate loop applies a native gate before it asks a Skill
for ``GetTargetArea``.  This module binds that gate, the usable-skill scan, and
the literal repair-skill resolver to the pinned build.  The pure replay accepts
native method results and Skill fields as honest boundary inputs.

It does not execute Lua ``GetTargetArea``, materialize returned target points,
or forecast a complete future enemy phase.  The settled live queue therefore
remains authoritative for ordinary solver use.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.enemy_candidate_score_boundary import (
    DEBUGAI_CANDIDATE_MODE,
    NORMAL_CANDIDATE_MODE,
    EnemyCandidateScoreBoundaryError,
    normalize_enemy_selected_weapon,
    validate_enemy_candidate_score_boundary_map,
)
from src.observatory.pe_boundary_map import (
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_target_area_boundary_map"
USABLE_SCAN_REPLAY_KIND = "native_enemy_usable_skill_scan_replay"
TARGET_AREA_GATE_REPLAY_KIND = "native_enemy_target_area_gate_replay"
SKILL_RESOLUTION_REPLAY_KIND = "native_enemy_skill_resolution_replay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
REPAIR_SKILL_INDEX = 0x32
REPAIR_SKILL_ID = "Skill_Repair"
MOVE_SKILL_IDS = ("Move", "Move_Power")
TERRAIN_WATER = 3
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1


class EnemyTargetAreaBoundaryError(RuntimeError):
    """Raised when the exact target-area boundary cannot reproduce."""


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
        "role": (
            "Pins the executable and the exact installed scripts inventory used "
            "for the source-static SkillList census."
        ),
    },
    {
        "id": "enemy_candidate_score",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json"
        ),
        "file_sha256": (
            "c94f87833efafec1217eefd0b5aeef61dd79e46fb3c1255c558259af64596ad0"
        ),
        "canonical_sha256": (
            "c0eeed00ebb646371d3ca33cac9d1c52224bb67025d1b6e6fa41a74115a7a457"
        ),
        "role": (
            "Pins normal/debug candidate modes and the selected-weapon "
            "normalization immediately adjacent to this gate."
        ),
    },
)


REGION_SPECS = (
    (
        "candidate_loop",
        0x000F78F0,
        0x000F7C17,
        "a162b5ead3bfcb851bf99f31b204485769570deb38fb6eb8102040214bcfc064",
        "Per-destination candidate loop containing the target-area gate.",
    ),
    (
        "lua_string_equal",
        0x0007C7B0,
        0x0007C805,
        "c0a0823d4c48882c5b64ac059812e6b1adcb02780effe5e037e1f46cc0aa74ea",
        "Exact native Skill-ID equality helper used for Move_Power.",
    ),
    (
        "skill_manager_ctor",
        0x00226F00,
        0x00227084,
        "3524ac242335de198252f75161f4499f06d5b8f1be7e845d6eddfe61f9ed8dac",
        "SkillManager constructor that owns the separate repair shared pointer.",
    ),
    (
        "consume_skill",
        0x00227BF0,
        0x00227E17,
        "612697e5d8ec51a2bd9fad39587e64aaaa5c99ebcb67ea0a819a578ff1b13078",
        "Skill-consumption path decrementing remaining limited uses.",
    ),
    (
        "usable_skill_scan",
        0x00229020,
        0x002290C5,
        "8d9a2a5a30f4c1913871ff99d606166376c8f24c8bef2324b52fe63d43b743f0",
        "Complete vector scan used by the ordinary candidate gate.",
    ),
    (
        "target_area",
        0x00229230,
        0x00229307,
        "9156f8498c8e6cb817eb0d75123888ebff9331f90745ecb9e857ebe45d3c82b1",
        "Target-area wrapper, resolver gate, and Lua callback dispatch.",
    ),
    (
        "reset_skill_uses",
        0x00229760,
        0x0022981E,
        "6a3be562d8e86276a9a585e810a2a5178e47040034d4e95194ac0eac76ae28a1",
        "Vector and repair-skill limited-use reset path.",
    ),
    (
        "resolve_skill",
        0x00229BB0,
        0x00229C0D,
        "3315ee0d31c687a99829b097af3b67be361be8b59d42d5d0a8bd1f876146d598",
        "Skill resolver that checks literal 50 before vector bounds.",
    ),
    (
        "repair_factory",
        0x0022A240,
        0x0022A2EF,
        "aa2f887477481e5dc5dc20676815d6b4339fcc4e2a9131e65548a75270068fb1",
        "Factory constructing the separate Skill_Repair object.",
    ),
    (
        "is_busy",
        0x0022CCE0,
        0x0022CDC9,
        "3314bb928c7e662f17ec11fd5f5134256c0259818b74fd01d9e921f6617e2344",
        "Pawn IsBusy implementation shared by smoke and Water predicates.",
    ),
    (
        "action_state",
        0x0023A880,
        0x0023A8D9,
        "0d95224bcfdac74b4752858fd41556c4d8c7a7dff05bc935772cc761ff8c9c81",
        "Setter storing iBonusShift and naming shifty/postmove state.",
    ),
    (
        "is_mech_getter",
        0x0023C8D0,
        0x0023C8D7,
        "93be70843ae650ab49f4da225e76da80df9b55151167e3f8c732eb0a9253fa90",
        "Seven-byte IsMech getter reading Pawn +0x9e4.",
    ),
    (
        "smoke_disabled",
        0x0023D940,
        0x0023D998,
        "ae384c65865c9ef578af34774906083e7a4ca10be1cf6da0441bdfe0b4623758",
        "Smoke attack-disable predicate with two immunity checks.",
    ),
    (
        "smoke_present",
        0x0023D9A0,
        0x0023DA16,
        "42644a702cdef2597de5410e80d06169fae844d1acfebc54e1c8832d369e87f2",
        "Board smoke lookup combined with not-IsBusy.",
    ),
    (
        "grounded_water",
        0x0023DA20,
        0x0023DA75,
        "f23c0bb268bb0c9177aa69ea97c38ab59dd5a81128cd494ca6752db089fe2591",
        "Water, not-IsBusy, and not-IsFlying predicate.",
    ),
    (
        "is_flying",
        0x0023E490,
        0x0023E571,
        "06fe4311381c6f3a5f31db9b53004c771762327a02ef33ced2c3af2bb021fbdb",
        "Pawn IsFlying implementation called by the Water predicate.",
    ),
    (
        "is_active",
        0x0023E8B0,
        0x0023E939,
        "449310a80188de96a31ca52afdd3c1db0784bfd136322352f467c2d770ff41b9",
        "Pawn IsActive implementation called first by the candidate gate.",
    ),
    (
        "pawn_archive",
        0x0023FB40,
        0x00240ACF,
        "b3475222468769a173264dd29a9bb00d3980f563b0c4bb9243875b844450d270",
        "Pawn archive path binding +0xa64 to iBonusShift.",
    ),
    (
        "skill_ctor",
        0x002670B0,
        0x00267639,
        "4a0466f114c734bd512c85f5bc0834433380daead50236bf634161f0ea7d965c",
        "Generic Skill constructor loading Lua Limited into +0x160.",
    ),
    (
        "board_terrain_binding",
        0x00279F79,
        0x00279F9E,
        "e6d52fbb7e7959e179434dc62c43761734bdad780f39aa67d9157370ce4cadda",
        "Instruction-aligned Board IsTerrain Lua binding span.",
    ),
    (
        "pawn_ismech_binding",
        0x0027C273,
        0x0027C298,
        "4e34f6150e313bbc12831d15183d99e29cf486b144503586c9eec85a688531ab",
        "Instruction-aligned Pawn IsMech Lua binding span.",
    ),
    (
        "pawn_isbusy_binding",
        0x0027C298,
        0x0027C2BD,
        "c34469c57e542adc6f71d768df0c5300fc4c1b94e2ad553884ea4f1bad27d76b",
        "Instruction-aligned Pawn IsBusy Lua binding span.",
    ),
    (
        "pawn_isactive_binding",
        0x0027C42B,
        0x0027C450,
        "2ba76e30d7e471e04693f72d31896ecb90f4b23ed070ab59af59d4f5732ffe71",
        "Instruction-aligned Pawn IsActive Lua binding span.",
    ),
    (
        "pawn_isflying_binding",
        0x0027C61F,
        0x0027C644,
        "2ff0a59e9599c8698514a2aff0bd6b000006e38ca7d62440d419dc066a0205b4",
        "Instruction-aligned Pawn IsFlying Lua binding span.",
    ),
    (
        "terrain_water_constant_binding",
        0x0027EFA6,
        0x0027EFE4,
        "bb4bd0466fea1c52a560f087b275395e303ad512ddca2465754e2a42ed8e13c8",
        "Global registration span binding TERRAIN_WATER to integer three.",
    ),
    (
        "terrain_vtable_thunk",
        0x002E399D,
        0x002E39A2,
        "7c836e74657fc808255a968c47fe3e344c8eebaa98e5d9c1a709ac32e09b51c8",
        "Board IsTerrain thunk dispatching vtable slot +0x7c.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "candidate_gate_and_dispatch",
        "candidate_loop",
        0x000F7994,
        "8b77288bcee8126f140084c074348bcee8975f140084c075298bcee86c60140084c0751e83be640a0000007f158bcee85816130084c075108a86e409000084c07506807d080074618b4f288b914809000083faff74178b41082b4104c1f8033bd07c0ac7814809000000000000ff75108d45d0ff750cffb1480900008b4f2850e817181300",
        (
            "Require IsActive, no smoke disable, no grounded Water, iBonusShift "
            "<= 0, and a usable skill or IsMech; mode one bypasses failure, then "
            "selected-weapon normalization precedes target-area dispatch."
        ),
    ),
    (
        "usable_skill_predicate",
        "usable_skill_scan",
        0x00229052,
        "8b34fb837e141072048b0eeb028bce8b5e10b8040000003bd8baa0a782000f42c350e83731e4ff83c40485c0750783fb0472027629ba888083008bcee81d37e5ff84c0751983be6001000000740983be58010000007e07b201",
        (
            "Exclude exact IDs Move and Move_Power, then accept Limited==0 or "
            "remaining uses at +0x158 greater than zero."
        ),
    ),
    (
        "target_area_resolver_gate",
        "target_area",
        0x00229257,
        "8b550cc745f00000000085d2780d8b41082b4104c1f8033bd07c0583fa327566528d45e850e82f090000c745fc00000000ff75148b08ff7510ff7508e8280a0400",
        "Invoke the resolver/callback only for a vector index or literal 50.",
    ),
    (
        "resolve_repair_before_vector",
        "resolve_skill",
        0x00229BB3,
        "8b550c5683fa3275148d41688b4d0850e8785fe4ff8b45085e5dc2080085d278248b41082b4104c1f8033bd07d178b41048b4d088d04d050e8505fe4ff8b45085e5dc208008b45085ec70000000000c74004000000005dc20800",
        "Resolve literal 50 from SkillManager +0x68 before testing vector bounds.",
    ),
    (
        "manager_owns_repair",
        "skill_manager_ctor",
        0x00226FD6,
        "c7466800000000c7466c0000000083ec08c645fc028d5508c74508000000008d4de4e84332000083c4088b108b4804c70000000000c74004000000008b7e6c894e6c895668",
        "Construct and store the separate repair shared pointer at +0x68/+0x6c.",
    ),
    (
        "repair_factory_skill_id",
        "repair_factory",
        0x0022A2B9,
        "83ec188bcc68f85d8300e848dbddff8b45f08bcb6a01ff30e8dacd0300",
        "Pass native string Skill_Repair into the generic Skill constructor.",
    ),
    (
        "limited_load",
        "skill_ctor",
        0x002674B6,
        "6a07c741140f000000c7411000000000681c7f8300c60100e8fd0adaff8bcbe8b61ddeff8bce898660010000",
        "Load Lua Limited and store it at Skill +0x160.",
    ),
    (
        "limited_consume",
        "consume_skill",
        0x00227DAD,
        "83bf60010000007406ff8f580100008bcfe82d0c0400",
        "Decrement +0x158 only when Limited at +0x160 is nonzero.",
    ),
    (
        "limited_reset_vector",
        "reset_skill_uses",
        0x00229780,
        "8b43048b3cf083bf6001000000743883ec188bcc6810818300e872e6ddffe85d4f03000fb6c883c4188b876001000003c180bf2902000000898758010000740740898758010000",
        "Rebuild each vector Skill's remaining-use value at +0x158.",
    ),
    (
        "limited_reset_repair",
        "reset_skill_uses",
        0x002297D5,
        "8b736883be6001000000743683ec188bcc6810818300e820e6ddffe80b4f03000fb6c083c41803866001000080be2902000000898658010000740740898658010000",
        "Apply the same limited-use reset to the separate repair Skill.",
    ),
    (
        "smoke_immunity_gate",
        "smoke_disabled",
        0x0023D947,
        "e85400000084c0744183ec188bcc689c6a8300e8b1a4dcff8d8e94000000e846bae0ff84c0752383ec188bcc6824068300e893a4dcff8b068bce8b4004ffd084c07507b0015e8be55dc332c05e8be55dc3",
        "Smoke disables only when IgnoreSmoke and Disable_Immunity are both false.",
    ),
    (
        "smoke_tile_and_busy",
        "smoke_present",
        0x0023D9AA,
        "8bf98bb74409000085f674578b87f00800008bceffb7f00800008b9fec080000894424108b06538b4008ffd084c074138b46508d0c5b6974240cbc2b0000033488eb0383c65c80be252b00000074148bcfe8e0f2feff84c07509b0015f5e5b8be55dc3",
        "Require an attached Board, smoke on the current tile, and not IsBusy.",
    ),
    (
        "water_busy_flying",
        "grounded_water",
        0x0023DA2A,
        "8b8e4409000085c9743a8b410c83c10c6a03ffb6f0080000ffb6ec0800008b407cffd084c0741d8bcee888f2feff84c075128bcee82d0a000084c07507b0015e8be55dc3",
        "Require Board IsTerrain(...,3), not IsBusy, and not IsFlying.",
    ),
    (
        "bonus_shift_archive",
        "pawn_archive",
        0x0024096E,
        "83bf640a0000007e1c83ec188bcc684c6f8300e88a74dcffffb7640a00008bcee89d83e9ff",
        "Archive positive Pawn +0xa64 under exact field name iBonusShift.",
    ),
    (
        "bonus_shift_state",
        "action_state",
        0x0023A880,
        "558bec83e4f8518b4508568bf183ec1083f8018986640a00008bc40f1005b85d89000f1100750c83ec188bcc68b4638300eb0a83ec188bcc68fc638300e84ed5dcff6a018bcee88545ffffc6861c090000015e8be55dc20400",
        "Store +0xa64 and name value one shifty, otherwise postmove.",
    ),
    (
        "is_mech_field_getter",
        "is_mech_getter",
        0x0023C8D0,
        "8a81e4090000c3",
        "Return the byte at Pawn +0x9e4.",
    ),
    (
        "terrain_water_constant",
        "terrain_water_constant_binding",
        0x0027EFA6,
        "68549883008d8d90f7ffff518bc8e89718ddff8bd88b4b08ff710468f0d8ffffff33ff15c0647d00ff73048b3b57ff15e4647d006a03ff33ff158c647d00",
        "Register TERRAIN_WATER with exact integer value three.",
    ),
    (
        "terrain_thunk",
        "terrain_vtable_thunk",
        0x002E399D,
        "8b01ff607c",
        "Dispatch Board IsTerrain through vtable slot +0x7c.",
    ),
)


DIRECT_EDGE_SPECS = (
    ("candidate_to_is_active", "candidate_loop", 0x000F7999, "e8126f1400", 0x0023E8B0),
    ("candidate_to_smoke_disabled", "candidate_loop", 0x000F79A4, "e8975f1400", 0x0023D940),
    ("candidate_to_grounded_water", "candidate_loop", 0x000F79AF, "e86c601400", 0x0023DA20),
    ("candidate_to_usable_scan", "candidate_loop", 0x000F79C3, "e858161300", 0x00229020),
    ("candidate_to_target_area", "candidate_loop", 0x000F7A14, "e817181300", 0x00229230),
    ("target_area_to_resolver", "target_area", 0x0022927C, "e82f090000", 0x00229BB0),
    ("target_area_to_lua_callback", "target_area", 0x00229293, "e8280a0400", 0x00269CC0),
    ("manager_ctor_to_repair_factory", "skill_manager_ctor", 0x00226FF8, "e843320000", 0x0022A240),
    ("repair_factory_to_skill_ctor", "repair_factory", 0x0022A2D1, "e8dacd0300", 0x002670B0),
    ("smoke_disabled_to_smoke_present", "smoke_disabled", 0x0023D947, "e854000000", 0x0023D9A0),
    ("smoke_present_to_is_busy", "smoke_present", 0x0023D9FB, "e8e0f2feff", 0x0022CCE0),
    ("grounded_water_to_is_busy", "grounded_water", 0x0023DA53, "e888f2feff", 0x0022CCE0),
    ("grounded_water_to_is_flying", "grounded_water", 0x0023DA5E, "e82d0a0000", 0x0023E490),
)


CALL_INVENTORY_SPECS = (
    ("repair_factory_callers", 0x0022A240, (0x00226FF8,)),
    (
        "target_area_callers",
        0x00229230,
        (0x000F7A14, 0x00183164, 0x00193AFF),
    ),
    (
        "usable_skill_scan_callers",
        0x00229020,
        (0x000F79C3, 0x0018654F, 0x00186A4F, 0x0018F10B, 0x00234E6D),
    ),
)


DATA_ANCHOR_SPECS = (
    ("move_skill_id", 0x0042A7A0, b"Move\0"),
    ("disable_immunity_name", 0x00430624, b"Disable_Immunity\0"),
    ("repair_skill_id", 0x00435DF8, b"Skill_Repair\0"),
    ("shifty_state_name", 0x004363B4, b"shifty\0"),
    ("postmove_state_name", 0x004363FC, b"postmove\0"),
    ("ignore_smoke_name", 0x00436A9C, b"IgnoreSmoke\0"),
    ("bonus_shift_name", 0x00436F4C, b"iBonusShift\0"),
    ("limited_name", 0x00437F1C, b"Limited\0"),
    ("move_power_skill_id", 0x00438088, b"Move_Power\0"),
    ("get_target_area_name", 0x004380A4, b"GetTargetArea\0"),
    ("is_busy_name", 0x00438578, b"IsBusy\0"),
    ("is_terrain_name", 0x004386CC, b"IsTerrain\0"),
    ("is_mech_name", 0x00439098, b"IsMech\0"),
    ("is_active_name", 0x00439130, b"IsActive\0"),
    ("is_flying_name", 0x004391A0, b"IsFlying\0"),
    ("terrain_water_name", 0x00439854, b"TERRAIN_WATER\0"),
)


METHOD_BINDING_SPECS = (
    {
        "id": "pawn_is_mech",
        "method_name": "IsMech",
        "name_anchor": "is_mech_name",
        "registration_region": "pawn_ismech_binding",
        "implementation_region": "is_mech_getter",
        "implementation_rva": "0x0023c8d0",
        "pawn_offset": "+0x9e4",
    },
    {
        "id": "pawn_is_busy",
        "method_name": "IsBusy",
        "name_anchor": "is_busy_name",
        "registration_region": "pawn_isbusy_binding",
        "implementation_region": "is_busy",
        "implementation_rva": "0x0022cce0",
    },
    {
        "id": "pawn_is_active",
        "method_name": "IsActive",
        "name_anchor": "is_active_name",
        "registration_region": "pawn_isactive_binding",
        "implementation_region": "is_active",
        "implementation_rva": "0x0023e8b0",
    },
    {
        "id": "pawn_is_flying",
        "method_name": "IsFlying",
        "name_anchor": "is_flying_name",
        "registration_region": "pawn_isflying_binding",
        "implementation_region": "is_flying",
        "implementation_rva": "0x0023e490",
    },
    {
        "id": "board_is_terrain",
        "method_name": "IsTerrain",
        "name_anchor": "is_terrain_name",
        "registration_region": "board_terrain_binding",
        "implementation_region": "terrain_vtable_thunk",
        "implementation_rva": "0x002e399d",
        "vtable_slot": "+0x7c",
    },
)


EXPECTED_MAX_SKILL_LIST_OCCURRENCES = (
    ("scripts/advanced/ae_pawns.lua", 489, ("Ranged_SmokeFire", "Passive_HealingSmoke")),
    ("scripts/advanced/ae_pawns.lua", 563, ("Science_RainingFire", "Passive_FireBoost")),
    ("scripts/advanced/ae_pawns.lua", 717, ("Ranged_SmokeFire", "Passive_HealingSmoke")),
    ("scripts/advanced/missions/acid/mission_missiles.lua", 51, ("Missiles_Shield", "Missiles_OneDmg")),
    ("scripts/missions/bosses/bot.lua", 49, ("SnowBossAtk", "BossHeal")),
    ("scripts/missions/bosses/bot.lua", 74, ("SnowBossAtk2", "BossHeal")),
    ("scripts/pawns.lua", 93, ("Science_Gravwell", "Passive_FriendlyFire")),
    ("scripts/pawns.lua", 111, ("Ranged_Rocket", "Passive_Electric")),
    ("scripts/pawns.lua", 165, ("Prime_Flamethrower", "Passive_FlameImmune")),
    ("scripts/pawns.lua", 246, ("Science_Pullmech", "Science_Shield")),
    ("scripts/pawns.lua", 393, ("Science_AcidShot", "Passive_Leech")),
)


EXPECTED_BLOCK_COMMENTED_SKILL_LIST_MATCHES = (
    ("scripts/advanced/ae_pawns.lua", 316),
    ("scripts/advanced/ae_pawns.lua", 333),
    ("scripts/advanced/ae_pawns.lua", 351),
    ("scripts/advanced/ae_pawns.lua", 595),
    ("scripts/advanced/ae_pawns.lua", 614),
    ("scripts/weapons_deploy.lua", 452),
    ("scripts/weapons_deploy.lua", 456),
    ("scripts/weapons_deploy.lua", 460),
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
        raise EnemyTargetAreaBoundaryError(
            f"dependency is not a regular non-symlink file: {path}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyTargetAreaBoundaryError(
            f"dependency must contain an object: {path}"
        )
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemyTargetAreaBoundaryError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise EnemyTargetAreaBoundaryError(
            f"RVA 0x{rva:08x} is not a direct rel32 call"
        )
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    result: set[int] = set()
    for section in image.sections:
        if not section.executable:
            continue
        body = data[section.raw_offset : section.raw_offset + section.raw_size]
        for offset in range(0, max(0, len(body) - 4)):
            if body[offset] != 0xE8:
                continue
            source = section.virtual_address + offset
            target = source + 5 + struct.unpack_from("<i", body, offset + 1)[0]
            if target == target_rva:
                result.add(source)
    return result


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnemyTargetAreaBoundaryError(f"{name} must be an integer")
    if not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyTargetAreaBoundaryError(
            f"{name} must fit in a signed 32-bit integer"
        )
    return value


def _require_nonnegative(name: str, value: Any) -> int:
    result = _require_int(name, value)
    if result < 0:
        raise EnemyTargetAreaBoundaryError(f"{name} must be nonnegative")
    return result


def _require_bool(name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise EnemyTargetAreaBoundaryError(f"{name} must be a boolean")
    return value


def _validated_skills(skills: Any) -> list[dict[str, Any]]:
    if isinstance(skills, (str, bytes, bytearray)) or not isinstance(
        skills, Sequence
    ):
        raise EnemyTargetAreaBoundaryError("skills must be an array")
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(skills):
        if not isinstance(raw, Mapping) or set(raw) != {
            "id",
            "limited",
            "remaining_uses",
        }:
            raise EnemyTargetAreaBoundaryError(
                f"skills[{index}] fields differ from the exact schema"
            )
        skill_id = raw["id"]
        if not isinstance(skill_id, str) or not skill_id:
            raise EnemyTargetAreaBoundaryError(
                f"skills[{index}].id must be a nonempty string"
            )
        result.append(
            {
                "id": skill_id,
                "limited": _require_int(
                    f"skills[{index}].limited", raw["limited"]
                ),
                "remaining_uses": _require_int(
                    f"skills[{index}].remaining_uses",
                    raw["remaining_uses"],
                ),
            }
        )
    return result


def replay_usable_skill_scan(skills: Any) -> dict[str, Any]:
    """Replay the vector scan used by the ordinary target-area gate."""
    normalized = _validated_skills(skills)
    entries = []
    usable_indices = []
    for index, skill in enumerate(normalized):
        skill_id = skill["id"]
        if skill_id == "Move":
            usable = False
            reason = "excluded_move"
        elif skill_id == "Move_Power":
            usable = False
            reason = "excluded_move_power"
        elif skill["limited"] == 0:
            usable = True
            reason = "unlimited"
        elif skill["remaining_uses"] > 0:
            usable = True
            reason = "limited_with_remaining_use"
        else:
            usable = False
            reason = "limited_exhausted"
        if usable:
            usable_indices.append(index)
        entries.append(
            {
                "index": index,
                **skill,
                "usable": usable,
                "reason": reason,
            }
        )
    return {
        "analysis_kind": USABLE_SCAN_REPLAY_KIND,
        "skill_count": len(normalized),
        "excluded_skill_ids": list(MOVE_SKILL_IDS),
        "skill_fields": {
            "remaining_uses_offset": "+0x158",
            "limited_offset": "+0x160",
        },
        "entries": entries,
        "usable_indices": usable_indices,
        "has_usable_skill": bool(usable_indices),
    }


def resolve_enemy_skill_index(
    weapon_index: int,
    weapon_count: int,
) -> dict[str, Any]:
    """Replay literal-50-first resolution from a SkillManager."""
    index = _require_int("weapon_index", weapon_index)
    count = _require_nonnegative("weapon_count", weapon_count)
    if index == REPAIR_SKILL_INDEX:
        resolution = "repair"
        skill_id = REPAIR_SKILL_ID
        vector_index = None
    elif 0 <= index < count:
        resolution = "vector"
        skill_id = None
        vector_index = index
    else:
        resolution = "null"
        skill_id = None
        vector_index = None
    return {
        "analysis_kind": SKILL_RESOLUTION_REPLAY_KIND,
        "weapon_index": index,
        "weapon_count": count,
        "repair_skill_index": REPAIR_SKILL_INDEX,
        "resolution": resolution,
        "skill_id": skill_id,
        "vector_index": vector_index,
    }


def replay_enemy_target_area_gate(
    *,
    candidate_mode: int,
    board_attached: bool,
    active: bool,
    smoke_on_tile: bool,
    busy: bool,
    ignore_smoke: bool,
    disable_immunity: bool,
    terrain_is_water: bool,
    flying: bool,
    bonus_shift: int,
    is_mech: bool,
    skills: Any,
    selected_weapon: int,
) -> dict[str, Any]:
    """Replay the native gate through resolver/callback eligibility."""
    mode = _require_int("candidate_mode", candidate_mode)
    if mode not in (NORMAL_CANDIDATE_MODE, DEBUGAI_CANDIDATE_MODE):
        raise EnemyTargetAreaBoundaryError(
            "candidate_mode must be 0 (normal planning) or 1 (debugai)"
        )
    attached = _require_bool("board_attached", board_attached)
    active_value = _require_bool("active", active)
    smoke_value = _require_bool("smoke_on_tile", smoke_on_tile)
    busy_value = _require_bool("busy", busy)
    ignore_value = _require_bool("ignore_smoke", ignore_smoke)
    immunity_value = _require_bool("disable_immunity", disable_immunity)
    water_value = _require_bool("terrain_is_water", terrain_is_water)
    flying_value = _require_bool("flying", flying)
    shift = _require_int("bonus_shift", bonus_shift)
    mech_value = _require_bool("is_mech", is_mech)
    selected = _require_int("selected_weapon", selected_weapon)
    usable = replay_usable_skill_scan(skills)

    smoke_present = attached and smoke_value and not busy_value
    smoke_disabled = smoke_present and not ignore_value and not immunity_value
    grounded_water = (
        attached and water_value and not busy_value and not flying_value
    )
    ordinary_eligible = (
        active_value
        and not smoke_disabled
        and not grounded_water
        and shift <= 0
        and (usable["has_usable_skill"] or mech_value)
    )
    mode_override = mode != NORMAL_CANDIDATE_MODE
    wrapper_invoked = ordinary_eligible or mode_override

    normalization = None
    resolution = None
    lua_callback_invoked = False
    if wrapper_invoked:
        try:
            normalization = normalize_enemy_selected_weapon(
                selected,
                usable["skill_count"],
            )
        except EnemyCandidateScoreBoundaryError as exc:
            raise EnemyTargetAreaBoundaryError(str(exc)) from exc
        resolution = resolve_enemy_skill_index(
            normalization["normalized_weapon_index"],
            usable["skill_count"],
        )
        if resolution["resolution"] == "vector":
            vector_index = resolution["vector_index"]
            assert vector_index is not None
            resolution["skill_id"] = usable["entries"][vector_index]["id"]
        lua_callback_invoked = resolution["resolution"] != "null"

    return {
        "analysis_kind": TARGET_AREA_GATE_REPLAY_KIND,
        "route": "normal_enemy_planning" if mode == 0 else "debugai",
        "candidate_mode": mode,
        "board_attached": attached,
        "active": active_value,
        "smoke": {
            "smoke_on_tile": smoke_value,
            "busy": busy_value,
            "ignore_smoke": ignore_value,
            "disable_immunity": immunity_value,
            "smoke_present_for_gate": smoke_present,
            "attack_disabled": smoke_disabled,
        },
        "water": {
            "terrain_constant": TERRAIN_WATER,
            "terrain_is_water": water_value,
            "busy": busy_value,
            "flying": flying_value,
            "grounded_nonflying_in_water": grounded_water,
        },
        "bonus_shift": shift,
        "bonus_shift_blocks": shift > 0,
        "is_mech": mech_value,
        "usable_skill_scan": usable,
        "ordinary_eligible": ordinary_eligible,
        "mode_override": mode_override,
        "target_area_wrapper_invoked": wrapper_invoked,
        "selected_weapon_normalization": normalization,
        "skill_resolution": resolution,
        "lua_get_target_area_invoked": lua_callback_invoked,
        "returned_target_points": "boundary_input_not_replayed",
    }


_SKILL_LIST_RE = re.compile(r"\bSkillList\s*=\s*\{([^{}\r\n]*)\}")
_LUA_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')


def _long_bracket(text: str, offset: int) -> tuple[int, str] | None:
    if offset >= len(text) or text[offset] != "[":
        return None
    cursor = offset + 1
    while cursor < len(text) and text[cursor] == "=":
        cursor += 1
    if cursor >= len(text) or text[cursor] != "[":
        return None
    equals = cursor - offset - 1
    return cursor + 1, "]" + ("=" * equals) + "]"


def _strip_lua_comments(text: str) -> str:
    output: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text.startswith("--", cursor):
            bracket = _long_bracket(text, cursor + 2)
            if bracket is not None:
                body_start, closing = bracket
                end = text.find(closing, body_start)
                end = len(text) if end < 0 else end + len(closing)
            else:
                end = text.find("\n", cursor)
                end = len(text) if end < 0 else end
            output.extend("\n" if char == "\n" else " " for char in text[cursor:end])
            cursor = end
            continue
        char = text[cursor]
        if char in ("\'", '"'):
            quote = char
            start = cursor
            cursor += 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                cursor += 1
                if text[cursor - 1] == quote:
                    break
            output.append(text[start:cursor])
            continue
        bracket = _long_bracket(text, cursor)
        if bracket is not None:
            body_start, closing = bracket
            end = text.find(closing, body_start)
            end = len(text) if end < 0 else end + len(closing)
            output.append(text[cursor:end])
            cursor = end
            continue
        output.append(char)
        cursor += 1
    return "".join(output)


def _parse_skill_list_body(body: str, label: str) -> list[str]:
    values = []
    cursor = 0
    for match in _LUA_STRING_RE.finditer(body):
        separator = body[cursor : match.start()]
        if separator.strip(" \t,"):
            raise EnemyTargetAreaBoundaryError(
                f"nonliteral SkillList entry in {label}"
            )
        if values and "," not in separator:
            raise EnemyTargetAreaBoundaryError(
                f"missing SkillList separator in {label}"
            )
        literal = match.group(0)
        values.append(literal[1:-1])
        cursor = match.end()
    if body[cursor:].strip(" \t,"):
        raise EnemyTargetAreaBoundaryError(
            f"nonliteral SkillList tail in {label}"
        )
    return values


def _extract_literal_skill_lists(path: str, text: str) -> list[dict[str, Any]]:
    stripped = _strip_lua_comments(text)
    result = []
    for line_number, line in enumerate(stripped.splitlines(), 1):
        for match in _SKILL_LIST_RE.finditer(line):
            skills = _parse_skill_list_body(
                match.group(1),
                f"{path}:{line_number}",
            )
            result.append(
                {
                    "path": path,
                    "line": line_number,
                    "arity": len(skills),
                    "skills": skills,
                }
            )
    return result


def _expected_source_inventory() -> dict[str, Any]:
    return {
        "inventory_dependency": "identity_inventory",
        "selection": (
            "Every inventory path ending .lua except the mutable project overlay "
            "scripts/modloader.lua; backup suffixes do not end .lua."
        ),
        "verified_lua_file_count": 152,
        "raw_non_line_comment_literal_match_count": 206,
        "block_commented_literal_match_count": 8,
        "block_commented_matches": [
            {"path": path, "line": line}
            for path, line in EXPECTED_BLOCK_COMMENTED_SKILL_LIST_MATCHES
        ],
        "active_literal_skill_list_assignment_count": 198,
        "active_arity_distribution": {"0": 26, "1": 161, "2": 11},
        "maximum_literal_arity": 2,
        "maximum_occurrences": [
            {
                "path": path,
                "line": line,
                "skills": list(skills),
            }
            for path, line, skills in EXPECTED_MAX_SKILL_LIST_OCCURRENCES
        ],
        "repair_sources": [
            {
                "path": "scripts/weapons_base.lua",
                "sha256": "bdb55457746d08b46e8b62ad7cfc27f0a08bde9fab7397a4780dfe945b5f8f38",
                "size": 21_524,
                "definition_line": 795,
                "effect_line": 806,
                "symbols": ["Skill_Repair", "Skill_Repair:GetSkillEffect"],
            },
            {
                "path": "scripts/advanced/ae_weapons_base.lua",
                "sha256": "4444af60a0b4d38894690425a83a4f610cbdc88f20b3fb322db410f257a89742",
                "size": 1_604,
                "override_line": 4,
                "symbols": ["Skill_Repair:GetSkillEffect"],
            },
        ],
        "scope_note": (
            "The literal-source maximum does not prove a universal runtime vector "
            "maximum after native equipment, save overlays, or mods."
        ),
    }


def _verify_core_lua_sources(
    content_root: Path,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    root = content_root.resolve()
    if not root.is_dir():
        raise EnemyTargetAreaBoundaryError("content root is not a directory")
    try:
        entries = inventory["content"]["scripts"]["files"]
    except (KeyError, TypeError) as exc:
        raise EnemyTargetAreaBoundaryError(
            "identity inventory scripts shape differs"
        ) from exc
    if not isinstance(entries, list):
        raise EnemyTargetAreaBoundaryError(
            "identity inventory scripts files must be an array"
        )

    selected = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise EnemyTargetAreaBoundaryError("inventory script entry is not an object")
        path = raw.get("path")
        if not isinstance(path, str):
            raise EnemyTargetAreaBoundaryError("inventory script path is not a string")
        if not path.endswith(".lua") or path == "scripts/modloader.lua":
            continue
        if path in seen:
            raise EnemyTargetAreaBoundaryError(f"duplicate inventory path: {path}")
        seen.add(path)
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise EnemyTargetAreaBoundaryError(f"unsafe inventory path: {path}")
        source = root.joinpath(*relative.parts)
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise EnemyTargetAreaBoundaryError(
                f"source is missing or escapes content root: {path}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise EnemyTargetAreaBoundaryError(
                f"source is not a regular non-symlink file: {path}"
            )
        raw_bytes = resolved.read_bytes()
        if (
            isinstance(raw.get("size"), bool)
            or not isinstance(raw.get("size"), int)
            or len(raw_bytes) != raw["size"]
            or hashlib.sha256(raw_bytes).hexdigest() != raw.get("sha256")
        ):
            raise EnemyTargetAreaBoundaryError(f"source identity differs: {path}")
        selected.append((path, raw_bytes.decode("utf-8")))

    raw_occurrences = []
    occurrences = []
    for path, text in selected:
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("--"):
                continue
            raw_occurrences.extend(
                {"path": path, "line": line_number}
                for _match in _SKILL_LIST_RE.finditer(line)
            )
        occurrences.extend(_extract_literal_skill_lists(path, text))
    distribution = Counter(item["arity"] for item in occurrences)
    maximum = max(distribution, default=0)
    maximum_occurrences = sorted(
        (
            {
                "path": item["path"],
                "line": item["line"],
                "skills": item["skills"],
            }
            for item in occurrences
            if item["arity"] == maximum
        ),
        key=lambda item: (item["path"], item["line"]),
    )
    actual = {
        "inventory_dependency": "identity_inventory",
        "selection": (
            "Every inventory path ending .lua except the mutable project overlay "
            "scripts/modloader.lua; backup suffixes do not end .lua."
        ),
        "verified_lua_file_count": len(selected),
        "raw_non_line_comment_literal_match_count": len(raw_occurrences),
        "block_commented_literal_match_count": len(raw_occurrences) - len(occurrences),
        "block_commented_matches": sorted(
            (
                item
                for item in raw_occurrences
                if (item["path"], item["line"])
                not in {(active["path"], active["line"]) for active in occurrences}
            ),
            key=lambda item: (item["path"], item["line"]),
        ),
        "active_literal_skill_list_assignment_count": len(occurrences),
        "active_arity_distribution": {
            str(key): distribution[key] for key in sorted(distribution)
        },
        "maximum_literal_arity": maximum,
        "maximum_occurrences": maximum_occurrences,
        "repair_sources": _expected_source_inventory()["repair_sources"],
        "scope_note": _expected_source_inventory()["scope_note"],
    }
    expected = _expected_source_inventory()
    if actual != expected:
        raise EnemyTargetAreaBoundaryError(
            "literal SkillList source inventory differs"
        )
    return actual


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


def _call_inventory_records() -> list[dict[str, Any]]:
    return [
        {
            "id": inventory_id,
            "evidence_class": "fact",
            "target_rva": f"0x{target:08x}",
            "raw_rel32_call_sites": [f"0x{site:08x}" for site in sites],
            "complete_for_exact_executable": True,
        }
        for inventory_id, target, sites in CALL_INVENTORY_SPECS
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


def _skill(skill_id: str, limited: int = 0, remaining: int = 0) -> dict[str, Any]:
    return {
        "id": skill_id,
        "limited": limited,
        "remaining_uses": remaining,
    }


def _gate_vector(vector_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "candidate_mode": 0,
        "board_attached": True,
        "active": True,
        "smoke_on_tile": False,
        "busy": False,
        "ignore_smoke": False,
        "disable_immunity": False,
        "terrain_is_water": False,
        "flying": False,
        "bonus_shift": 0,
        "is_mech": False,
        "skills": [_skill("FireflyAtk1")],
        "selected_weapon": 0,
    }
    payload.update(overrides)
    result = replay_enemy_target_area_gate(**payload)
    normalization = result["selected_weapon_normalization"]
    resolution = result["skill_resolution"]
    return {
        "id": vector_id,
        "kind": "target_area_gate",
        "input": payload,
        "expected": {
            "ordinary_eligible": result["ordinary_eligible"],
            "mode_override": result["mode_override"],
            "target_area_wrapper_invoked": result["target_area_wrapper_invoked"],
            "lua_get_target_area_invoked": result["lua_get_target_area_invoked"],
            "normalized_weapon_index": (
                None if normalization is None else normalization["normalized_weapon_index"]
            ),
            "resolution": None if resolution is None else resolution["resolution"],
        },
    }


def _replay_vectors() -> list[dict[str, Any]]:
    return [
        {
            "id": "move_and_exhausted_are_not_usable",
            "kind": "usable_skill_scan",
            "input": {
                "skills": [
                    _skill("Move"),
                    _skill("Move_Power"),
                    _skill("BossHeal", limited=1, remaining=0),
                ]
            },
            "expected": {"usable_indices": [], "has_usable_skill": False},
        },
        {
            "id": "unlimited_and_remaining_limited_are_usable",
            "kind": "usable_skill_scan",
            "input": {
                "skills": [
                    _skill("FireflyAtk1"),
                    _skill("BossHeal", limited=2, remaining=1),
                ]
            },
            "expected": {"usable_indices": [0, 1], "has_usable_skill": True},
        },
        {
            "id": "literal_50_resolves_repair_before_vector",
            "kind": "skill_resolution",
            "input": {"weapon_index": 50, "weapon_count": 51},
            "expected": {"resolution": "repair", "skill_id": "Skill_Repair"},
        },
        {
            "id": "ordinary_vector_resolution",
            "kind": "skill_resolution",
            "input": {"weapon_index": 1, "weapon_count": 2},
            "expected": {"resolution": "vector", "vector_index": 1},
        },
        {
            "id": "invalid_resolution_is_null",
            "kind": "skill_resolution",
            "input": {"weapon_index": -1, "weapon_count": 2},
            "expected": {"resolution": "null", "skill_id": None},
        },
        _gate_vector("ordinary_usable_skill_passes"),
        _gate_vector("inactive_blocks", active=False),
        _gate_vector("smoke_blocks", smoke_on_tile=True),
        _gate_vector(
            "ignore_smoke_bypasses_smoke",
            smoke_on_tile=True,
            ignore_smoke=True,
        ),
        _gate_vector(
            "disable_immunity_bypasses_smoke",
            smoke_on_tile=True,
            disable_immunity=True,
        ),
        _gate_vector("grounded_water_blocks", terrain_is_water=True),
        _gate_vector(
            "flying_bypasses_water",
            terrain_is_water=True,
            flying=True,
        ),
        _gate_vector(
            "busy_suppresses_smoke_and_water_predicates",
            smoke_on_tile=True,
            terrain_is_water=True,
            busy=True,
        ),
        _gate_vector("positive_bonus_shift_blocks", bonus_shift=1),
        _gate_vector(
            "mech_fallback_passes_without_usable_skill",
            is_mech=True,
            skills=[_skill("Move"), _skill("BossHeal", limited=1, remaining=0)],
            selected_weapon=-1,
        ),
        _gate_vector(
            "debugai_mode_bypasses_every_ordinary_failure",
            candidate_mode=1,
            board_attached=False,
            active=False,
            smoke_on_tile=True,
            terrain_is_water=True,
            bonus_shift=4,
            skills=[],
            selected_weapon=-1,
        ),
        _gate_vector(
            "literal_50_normalizes_to_zero_for_small_vector",
            selected_weapon=50,
            skills=[_skill("FireflyAtk1"), _skill("BossHeal")],
        ),
    ]


def _contracts() -> dict[str, Any]:
    return {
        "candidate_route": {
            "normal_mode": NORMAL_CANDIDATE_MODE,
            "debugai_mode": DEBUGAI_CANDIDATE_MODE,
            "mode_one_bypasses_ordinary_gate_failure": True,
            "ordinary_gate": (
                "IsActive AND NOT smoke_disabled AND NOT grounded_nonflying_in_water "
                "AND iBonusShift <= 0 AND (has_usable_skill OR IsMech)"
            ),
        },
        "field_bindings": {
            "is_mech": {
                "pawn_offset": "+0x9e4",
                "native_method": "IsMech",
            },
            "bonus_shift": {
                "pawn_offset": "+0xa64",
                "archive_name": "iBonusShift",
                "positive_value_blocks_ordinary_gate": True,
                "state_names": {"1": "shifty", "other": "postmove"},
            },
            "remaining_uses": {"skill_offset": "+0x158"},
            "limited": {
                "skill_offset": "+0x160",
                "lua_name": "Limited",
            },
            "repair_shared_pointer": {
                "skill_manager_object_offset": "+0x68",
                "skill_manager_control_offset": "+0x6c",
                "skill_id": REPAIR_SKILL_ID,
                "resolver_index": REPAIR_SKILL_INDEX,
                "stored_outside_weapon_vector": True,
            },
        },
        "smoke_predicate": {
            "smoke_present": "board_attached AND smoke_on_tile AND NOT IsBusy",
            "attack_disabled": (
                "smoke_present AND NOT IgnoreSmoke AND NOT Disable_Immunity"
            ),
        },
        "water_predicate": {
            "terrain_constant_name": "TERRAIN_WATER",
            "terrain_constant_value": TERRAIN_WATER,
            "grounded_nonflying_in_water": (
                "board_attached AND IsTerrain(tile, TERRAIN_WATER) AND "
                "NOT IsBusy AND NOT IsFlying"
            ),
        },
        "usable_skill_scan": {
            "scan_order": "weapon vector order",
            "excluded_exact_ids": list(MOVE_SKILL_IDS),
            "usable": "Limited == 0 OR remaining_uses > 0",
            "short_circuits_scan": False,
        },
        "target_area_dispatch": {
            "selected_weapon_normalization": (
                "if selected != -1 and selected >= vector_count, write zero"
            ),
            "resolver_order": ["literal_50_repair", "in_range_vector", "null"],
            "lua_callback": "GetTargetArea",
            "callback_result_replayed": False,
        },
        "source_static_bound": {
            "exact_core_lua_file_count": 152,
            "raw_non_line_comment_literal_match_count": 206,
            "block_commented_literal_match_count": 8,
            "active_literal_skill_list_assignment_count": 198,
            "maximum_literal_skill_list_arity": 2,
            "runtime_vector_count_universally_bounded": False,
        },
        "solver_conformance": {
            "authoritative_current_enemy_action": "settled live bridge queue",
            "future_target_area_forecast_added": False,
            "rust_change_required": False,
            "simulator_version": 408,
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "ordinary_target_area_gate_closed",
            "classification": "inference",
            "claim": (
                "The exact normal-route predicate is fully parameterized by IsActive, "
                "the named smoke and Water helpers, iBonusShift, the usable-skill scan, "
                "and IsMech. Debugai mode one bypasses an ordinary failure."
            ),
        },
        {
            "id": "smoke_and_water_helpers_named",
            "classification": "inference",
            "claim": (
                "Smoke disables attacks only on an attached Board smoke tile while not "
                "busy and without IgnoreSmoke or Disable_Immunity. Terrain three is the "
                "registered TERRAIN_WATER value; it blocks only a not-busy, nonflying Pawn."
            ),
        },
        {
            "id": "usable_skill_rule_closed",
            "classification": "inference",
            "claim": (
                "The vector scan excludes exact IDs Move and Move_Power and otherwise "
                "accepts an unlimited Skill or a limited Skill with positive remaining uses."
            ),
        },
        {
            "id": "literal_50_is_repair",
            "classification": "inference",
            "claim": (
                "Literal index 50 resolves before vector bounds to the separately owned "
                "Skill_Repair shared pointer. It is not vector slot 51."
            ),
        },
        {
            "id": "small_vector_normalization",
            "classification": "inference",
            "claim": (
                "The candidate loop rewrites selected index 50 to zero whenever the vector "
                "count is at most 50, before target-area dispatch. The exact shipped one-line "
                "SkillList definitions have maximum literal arity two, but that source fact "
                "is not promoted to a universal runtime vector-count theorem."
            ),
        },
        {
            "id": "no_solver_semantic_change",
            "classification": "fact",
            "claim": (
                "The Rust solver consumes settled queued actions and lacks the prospective "
                "callback payload. No simulator contradiction or version change follows."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "lua_target_points",
            "boundary": (
                "The ordered PointList returned by each concrete Lua GetTargetArea callback "
                "remains a runtime input and is not synthesized by this replay."
            ),
        },
        {
            "id": "prospective_runtime_payload",
            "boundary": (
                "Ordinary solver input does not contain a complete prospective Pawn/Skill "
                "snapshot, callback outputs, or shared RNG state for a future enemy phase."
            ),
        },
        {
            "id": "runtime_vector_upper_bound",
            "boundary": (
                "The exact literal SkillList census has maximum arity two, but native "
                "equipment/save overlays and mods prevent claiming that every possible "
                "runtime vector count is at most 50."
            ),
        },
        {
            "id": "platform_scope",
            "boundary": (
                "The native byte and call-graph claims bind only Windows build 13725832; "
                "macOS and other depots require their own artifacts."
            ),
        },
    ]


def _expected_shape() -> dict[str, Any]:
    replay_vectors = _replay_vectors()
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "generated_from": {
            "method": "exact-build static disassembly plus hash-pinned Lua census",
            "platform": "windows",
            "architecture": "x86",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": "0x00400000",
            "evidence_policy": (
                "Exact bytes and sources are facts; named control-flow semantics are "
                "bounded inferences; Lua callback output remains an explicit boundary."
            ),
        },
        "dependencies": _dependency_records(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "call_inventories": _call_inventory_records(),
        "data_anchors": _data_anchor_records(),
        "method_bindings": _method_binding_records(),
        "source_inventory": _expected_source_inventory(),
        "contracts": _contracts(),
        "findings": findings,
        "unresolved": unresolved,
        "replay_vectors": replay_vectors,
        "notes": [
            "This is exact-build static evidence and pure replay, not a runtime trace.",
            "Candidate mode one is the pinned debugai route, not ordinary planning.",
            "The mutable project modloader overlay is excluded from the shipped Lua census.",
            "Returned target points and later scores/selection remain outside this artifact.",
        ],
        "summary": {
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "call_inventory_count": len(CALL_INVENTORY_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "method_binding_count": len(METHOD_BINDING_SPECS),
            "verified_core_lua_file_count": 152,
            "raw_non_line_comment_literal_match_count": 206,
            "block_commented_literal_match_count": 8,
            "active_literal_skill_list_assignment_count": 198,
            "maximum_literal_skill_list_arity": 2,
            "replay_vector_count": len(replay_vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "ordinary_target_area_gate_complete": True,
            "repair_sentinel_resolved": True,
            "lua_target_area_output_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _verify_dependencies(executable: Path) -> Mapping[str, Any]:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise EnemyTargetAreaBoundaryError(
                f"dependency is not a regular non-symlink file: {spec['id']}"
            )
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyTargetAreaBoundaryError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyTargetAreaBoundaryError(
                f"dependency fields differ: {spec['id']}"
            )
        values[spec["id"]] = value
    try:
        validate_enemy_candidate_score_boundary_map(
            executable,
            values["enemy_candidate_score"],
        )
    except EnemyCandidateScoreBoundaryError as exc:
        raise EnemyTargetAreaBoundaryError(
            f"enemy candidate-score dependency differs: {exc}"
        ) from exc
    return values["identity_inventory"]


def _verify_native(executable: Path) -> None:
    data, image, sha256 = _load_executable(executable)
    if sha256 != EXPECTED_EXECUTABLE_SHA256 or len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise EnemyTargetAreaBoundaryError("executable identity differs")
    if image.architecture != "x86" or image.bits != 32:
        raise EnemyTargetAreaBoundaryError("expected a PE32 x86 executable")
    if image.image_base != EXPECTED_IMAGE_BASE:
        raise EnemyTargetAreaBoundaryError("PE image base differs")

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        body = _region_bytes(image, data, start, end - start, ".text", region_id)
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise EnemyTargetAreaBoundaryError(f"region differs: {region_id}")
        region_ranges[region_id] = (start, end)
    _decode_x86_regions(image, data, region_ranges)

    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(expected_hex)
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start or start + len(expected) > region_end:
            raise EnemyTargetAreaBoundaryError(
                f"control window escapes region: {window_id}"
            )
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise EnemyTargetAreaBoundaryError(
                f"control window differs: {window_id}"
            )

    for edge_id, _source, call_rva, expected_hex, target_rva in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, call_rva, len(expected))
        if actual != expected or _direct_target(call_rva, actual) != target_rva:
            raise EnemyTargetAreaBoundaryError(f"direct edge differs: {edge_id}")

    for inventory_id, target, expected_sites in CALL_INVENTORY_SPECS:
        if _raw_rel32_call_sites(image, data, target) != set(expected_sites):
            raise EnemyTargetAreaBoundaryError(
                f"direct-call inventory differs: {inventory_id}"
            )

    for anchor_id, rva, expected in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemyTargetAreaBoundaryError(
                f"data anchor differs: {anchor_id}"
            )


def build_enemy_target_area_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Build the exact artifact after verifying every native/source input."""
    inventory = _verify_dependencies(executable)
    _verify_native(executable)
    _verify_core_lua_sources(content_root, inventory)
    return _expected_shape()


def validate_enemy_target_area_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields without requiring the installed game."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyTargetAreaBoundaryError("target-area boundary fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "ordinary_target_area_gate_complete": True,
        "repair_sentinel_resolved": True,
        "lua_target_area_output_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_target_area_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject byte, source, dependency, or replay drift."""
    expected = build_enemy_target_area_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise EnemyTargetAreaBoundaryError(
            "target-area boundary differs from exact-build analysis"
        )
    result = validate_enemy_target_area_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_target_area_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
