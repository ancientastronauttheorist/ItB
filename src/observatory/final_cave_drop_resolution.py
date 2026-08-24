"""Reproduce the exact-build Final Cave drop-resolution boundary.

This continuation joins the shipped startup and replacement records to the
native terrain, building-health, occupied-tile, and ``sPawn`` application
paths.  It proves the ordinary two-hit pylon materialization and the BigBomb
replacement rule without claiming concrete RNG results or presentation time.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.final_cave_block_spawn_lifetime import (
    FinalCaveBlockSpawnLifetimeError,
    validate_final_cave_block_spawn_lifetime_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_cave_drop_resolution_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class FinalCaveDropResolutionError(RuntimeError):
    """Raised when the reviewed drop-resolution map cannot be reproduced."""


LUA_SOURCE_SPEC = {
    "path": "scripts/missions/final/mission_final_two.lua",
    "size": 4_887,
    "sha256": "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c",
    "symbols": [
        "Mission_Final_Cave:StartMission",
        "Mission_Final_Cave:AddBomb",
    ],
}


DEPENDENCY_SPECS = (
    (
        "final_end_settlement",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_end_settlement.json",
        "541237f7e723c1ec56b0328cb1f137f2a6725bda55c588d0a7ebc74adc55be0c",
        "Pins the activity-clear Surface handoff into phase transition at BoardPlayer state five.",
    ),
    (
        "final_cave_startup",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup.json",
        "4cf2f05a267ed87a8cf5b14edbc874343a3969cef2dfb98e849f645ec177f942",
        "Pins all nine exact map zones and the four reserved deployment points.",
    ),
    (
        "final_cave_startup_spawn_order",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup_spawn_order.json",
        "b798a97c582be31ffba3d173e00b24eefae32a9725d03fe7a2260ca1403214f4",
        "Pins synchronous logical enemy admission before queued drop impacts.",
    ),
    (
        "final_cave_startup_effect_order",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup_effect_order.json",
        "a5290868718a0912c50c1caf914f7a6203d781d7a4b137352c9caf61c2c031df",
        "Pins two independent consecutive dropper records per pylon.",
    ),
    (
        "final_cave_replacement",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_replacement.json",
        "b08b6d96d4d4ba0f53c024b301b17a039c8deb944632bbc6b8b4000a6e20af50",
        "Pins the copied BigBomb record, drop impact, pawn factory, and AddPawn path.",
    ),
    (
        "final_cave_replacement_cadence",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_replacement_cadence.json",
        "578275064f6f55ca170128d954613d846eb9398a239c2462de87356549ca7b4e",
        "Pins each PylonAnimation as busy and retained through synchronous impact.",
    ),
    (
        "final_cave_block_spawn_lifetime",
        "data/observatory/native/windows_build_13725832_31fe35265598_final_cave_block_spawn_lifetime.json",
        "69d63632fe6585ac02864e09e3106e796e47abadd65991e41e1b76a1e2370889",
        "Pins ordinary pylon occupancy exclusion and permanent spawn blocking.",
    ),
)


REGION_SPECS = (
    ("value_bar_add", 0x000E0E30, 0x000E0E86, "bf75206014fdb840f943775fbfdfdd45e68229db122259779e37a5cbb127d7c5", "Ghidra 12.1.3 ValueBar clamped-delta method."),
    ("value_bar_get_max", 0x000E10D0, 0x000E10D4, "916ae10aa3fd76a4d5b25b2fb66e9df0fd04957c7ab10930268d1ed7808be689", "Ghidra 12.1.3 ValueBar maximum getter."),
    ("is_pawn_space_thunk", 0x000E7180, 0x000E7185, "35db3b17881aa60eaa25d8781db30c6df0065324b7097613cbe416b3add2e77c", "Instruction-aligned IsPawnSpace secondary-vtable thunk."),
    ("apply_space_damage", 0x00160110, 0x001604BC, "1597eb6d490f3ae9ee95547a0caa83999502b4ba9c3423bc50b1dca7acc20210", "Previously reviewed Board SpaceDamage application body."),
    ("preserved_pawn_readd", 0x00173480, 0x0017357C, "aaeda259965db9a087df7f6593e6515192cbc5a3572dd21fbb28a3c0bbeaf6b6", "Ghidra 12.1.3 phase-carried pawn admission loop."),
    ("base_start_dispatch", 0x001831C0, 0x0018334F, "fe91da3c9574d19e0e017385e9c5dfb1b47c3a9ef22ef009edb5ac92d1e162ec", "Previously reviewed BaseStart dispatch body."),
    ("phase_pawn_transport", 0x00183C60, 0x00183D1D, "aed0bc63dbfabfaf1a8f658c98d694332df4c9713cec4cbd4deff7dd4e639999", "Ghidra 12.1.3 phase-carried pawn transport wrapper."),
    ("phase_transition", 0x001891D0, 0x0018964D, "3a5b364d9af48610bb07f8e44d5cb9ddb4051f4cb4a5fa0ad0db8eb51522073f", "Previously reviewed phase-transition body."),
    ("set_terrain", 0x001A1BA0, 0x001A1F93, "cbd9f47a5841c88e21dff5ad5a20144bd10290c8ac627cda9618683987e3df97", "Ghidra 12.1.3 BoardSpace terrain setter body."),
    ("set_building_terrain", 0x001A1FA0, 0x001A209D, "92a0e16b107b424639a70aed1a8b2f767d8a798f207b1d51724803802795e80c", "Ghidra 12.1.3 building materialization body."),
    ("tile_value_bar_initializer", 0x0019D416, 0x0019D428, "e340b59272c198ca70609ccc67dd527915179f9229c6ee68a1eb27cf17ae854b", "Instruction-aligned BoardSpace ValueBar initializer window."),
    ("tile_has_live_occupant", 0x0019FF40, 0x0019FFD3, "1e3282851e31b74bfaba10d692ac4c31517d7416d47201c7e2eb5fdf36e4b1f1", "Ghidra 12.1.3 tile live-occupant predicate."),
    ("apply_damage_core", 0x001AC980, 0x001AE080, "e6c2049faa497fb736263591ce7f102630148360777ac61bf1a5318a95819a28", "Ghidra 12.1.3 core SpaceDamage terrain/status body."),
    ("kill_tile_occupants", 0x001B0490, 0x001B04D7, "b8e27fd5c8b5f4d184172f1bfab883545b8612a9a112a54425225c7dce7cd72c", "Ghidra 12.1.3 all-tile-occupants removal loop."),
    ("pawn_set_space", 0x002301B0, 0x00230317, "bb2f39cac0a81d266296d890dc52d4755da0b60c5c517dd0ee08b714bf10eb3c", "Ghidra 12.1.3 Pawn logical-space setter body."),
    ("pawn_set_space_entry", 0x00230320, 0x00230339, "a5034f607b779f10498f79683ac5401dd25c6387a3def070de3776488265865c", "Ghidra 12.1.3 Pawn SetSpace public entry wrapper."),
    ("pawn_kill", 0x0023D2E0, 0x0023D34B, "0a5d113dc0441f670a948a57ee4e3b07593815596b049075d3303ec3a7fd2903", "Ghidra 12.1.3 Pawn Kill implementation."),
    ("register_i_terrain", 0x0027AD6C, 0x0027AD76, "785a2036a6d7ee80d94f61c5eaef856fbbcce937f2bb80fbc31aba9952e6469d", "Instruction-aligned SpaceDamage iTerrain field registration."),
    ("register_s_pawn", 0x0027ADA8, 0x0027ADB2, "1872116caaed5e1253bc2d7725837ba287095059a5a31f95a946ea1311999b18", "Instruction-aligned SpaceDamage sPawn field registration."),
    ("register_i_damage", 0x0027ADF8, 0x0027ADFF, "69def6baaf418ec286ee4cc6b44db912707c6cb95b9328a3173bb9e2eee9b895", "Instruction-aligned SpaceDamage iDamage field registration."),
    ("register_is_blocked", 0x00279ABE, 0x00279AE3, "721e51ca77d6c25f19459451ef0866e66465e499dc573ab76e7223b1c46e02ae", "Instruction-aligned Board IsBlocked method registration."),
    ("register_is_pawn_space", 0x00279C93, 0x00279CB8, "f98b67d10209a99a642d4d71611f9363dabce588f9d5a1fe90778335ff53de1d", "Instruction-aligned Board IsPawnSpace method registration."),
    ("register_is_terrain", 0x00279F79, 0x00279F9E, "e6d52fbb7e7959e179434dc62c43761734bdad780f39aa67d9157370ce4cadda", "Instruction-aligned Board IsTerrain method registration."),
    ("register_pawn_kill", 0x0027C3E1, 0x0027C406, "d235cfc28f44928ab6c2024e8cfffc9d77d8083e3543e18bdf9906277ec59ef4", "Instruction-aligned Pawn Kill method registration."),
    ("is_terrain_thunk", 0x002E399D, 0x002E39A2, "7c836e74657fc808255a968c47fe3e344c8eebaa98e5d9c1a709ac32e09b51c8", "Instruction-aligned IsTerrain secondary-vtable thunk."),
    ("is_blocked_thunk", 0x002E39DF, 0x002E39E4, "36dd204b8c08514e55c5a4541c381d9c6c48ecda338001b0ac93e247ec819e94", "Instruction-aligned IsBlocked primary-vtable thunk."),
)


DATA_ANCHOR_SPECS = (
    ("i_damage_name", 0x00438A98, b"iDamage\0", "Registered SpaceDamage damage field."),
    ("s_pawn_name", 0x00438AE8, b"sPawn\0", "Registered SpaceDamage pawn-name field."),
    ("i_terrain_name", 0x00438B40, b"iTerrain\0", "Registered SpaceDamage terrain field."),
    ("is_blocked_name", 0x00438530, b"IsBlocked\0", "Registered Board method name."),
    ("is_pawn_space_name", 0x004385C4, b"IsPawnSpace\0", "Registered Board method name."),
    ("is_terrain_name", 0x004386CC, b"IsTerrain\0", "Registered Board method name."),
    ("pawn_kill_name", 0x0043911C, b"Kill\0", "Registered Pawn method name."),
    (
        "value_bar_vtable",
        0x00428F7C,
        struct.pack("<III", 0x004E1AD0, 0x004E0E30, 0x004E10D0),
        "BoardSpace embedded ValueBar vtable: destructor, delta, maximum.",
    ),
    (
        "board_apply_space_damage_slot",
        0x0042E258,
        struct.pack("<I", 0x00560110),
        "Board secondary-vtable slot zero points to SpaceDamage application.",
    ),
)


FIELD_BINDING_SPECS = (
    ("i_damage", "i_damage_name", "register_i_damage", 0x08),
    ("s_pawn", "s_pawn_name", "register_s_pawn", 0xA4),
    ("i_terrain", "i_terrain_name", "register_i_terrain", 0xDC),
)


METHOD_BINDING_SPECS = (
    ("board_is_blocked", "is_blocked_name", "register_is_blocked", "is_blocked_thunk", 0x002E39DF, 0),
    ("board_is_pawn_space", "is_pawn_space_name", "register_is_pawn_space", "is_pawn_space_thunk", 0x000E7180, 0x0C),
    ("board_is_terrain", "is_terrain_name", "register_is_terrain", "is_terrain_thunk", 0x002E399D, 0x0C),
    ("pawn_kill", "pawn_kill_name", "register_pawn_kill", "pawn_kill", 0x0023D2E0, 0),
)


CONTROL_WINDOW_SPECS = (
    ("phase_collects_carried_pawns", "phase_transition", 0x00189200, "6a048d4d8c33db895d98518b4804c7805c45000001000000e8d3abfeff8d4da4895dfce8b8100d00c645fc0133ff8b45908b4d8c2bc1c1f80285c00f84c20100008b04b98d4da48945988d459850e87d25f1ff", "Snapshot the old Board's carried pawn pointers and append every selected pointer to the phase transport."),
    ("phase_readd_before_base_start", "phase_transition", 0x0018952C, "83ec4c8d45a48bcc50e89631faff8bcbe81fa7ffff8bcbe8789cffff", "Copy and re-admit the carried-pawn transport, then call BaseStart only after that admission returns."),
    ("phase_transport_dispatch", "phase_pawn_transport", 0x00183C88, "83ec4cc745fc000000008d45088bcc50e8338afaff8b4e04e8dbf7feff", "Copy the incoming transport and synchronously pass it to the new Board's carried-pawn admission loop."),
    ("state_five_skips_auto_deploy", "phase_pawn_transport", 0x00183CEA, "833dd49c8b0001751083bec80f00000574078bcee81d000000", "The optional native auto-deployment tail is skipped whenever BoardPlayer state equals five."),
    ("carried_pawns_offboard_and_readded", "preserved_pawn_readd", 0x001734B2, "33db8b450c2b4508c1f80285c00f849b0000008d773c8b4d086aff6aff8b0c99e849ce0b008b45088b0c9839b94409000074178bd789b944090000f7da8d470c1bd223d052e8b4520b008b45088d3c988b46043bf873268b0e3bcf77202bf9c1ff023b46087508518bcee84f82f2ff8b4e0485c9741f8b068b04b8eb163b46087508518bcee83482f2ff8b4e0485c974048b0789018b450c432b4508834604048b7df0c1f8023bd80f8268ffffff", "For each transported pawn, call SetSpace(-1,-1), attach it to the replacement Board, append it to that Board's pawn vector, and continue through the complete transport."),
    ("pawn_space_fields_commit", "pawn_set_space", 0x0023029D, "8b86ec0800008986f40800008b86f00800008986f80800008b45088986ec0800008b450c8986f0080000c686810f000000", "SetSpace preserves the prior point, commits the supplied x/y as the pawn's logical coordinates, and clears the pending-space flag."),
    ("terrain_field_dispatch", "apply_damage_core", 0x001ADA0D, "8b85e400000083f80a0f84ac020000", "Read iTerrain and skip explicit terrain work only for TERRAIN_NONE (10)."),
    ("building_or_generic_terrain", "apply_damage_core", 0x001ADC71, "83bde4000000018bcb75416a01e8bd22ffff84c0742d6a018bcbe8b022ffff84c0740a8b83a00000008b08eb0233c96a00e839f608006a018bcbe89022ffff84c075d38bcbe8e542ffffeb0bffb5e4000000e8d83effff", "Building terrain removes live occupants before its setter; every other explicit terrain uses SetTerrain."),
    ("building_repeat_full_hp", "set_building_terrain", 0x001A1FB5, "83bee02a00000175628b46788d7e743b470875338b078bcfff500840c744240c0000000089470833d23b47048d44240c0f9cc28d14950400000003d7833a000f4fc28b008947048b078bcf6a01ff5004", "An already-full building raises its ValueBar maximum by one and applies a +1 delta."),
    ("building_first_application", "set_building_terrain", 0x001A2020, "8d567433c9c74208010000008d44240c837a0401c744240c000000000f9fc16a018d0c8d0400000003ca8339000f4fc18bce8b008942048b4208894204e83efbffff", "A non-building tile is initialized to current/max one before SetTerrain(Building)."),
    ("value_bar_initializer", "tile_value_bar_initializer", 0x0019D416, "8d8e94000000c746747c8f8200e83846f4ff", "BoardSpace installs the pinned ValueBar vtable at tile+0x74."),
    ("value_bar_add_delta", "value_bar_add", 0x000E0E30, "558bec568b7508578bf985f679098b4704f7d83bf0eb088b47082b47043bc60f4cf0c74508000000000177048d4d088b470433d23947088bc60f9cc28d14950400000003d7833a000f4fca8b09894f045f5e5dc20400", "ValueBar slot +4 adds and clamps the requested delta."),
    ("value_bar_maximum", "value_bar_get_max", 0x000E10D0, "8b4108c3", "ValueBar slot +8 returns the maximum."),
    ("core_before_spawn", "apply_space_damage", 0x001602D1, "8d4ff4ff750cff7508e8911a00008bc8c645fc00e896c6040083bde40000000175088d4ff4e8f52f0100", "Board application completes the core terrain/status body before inspecting sPawn."),
    ("spawn_collision_kill", "apply_space_damage", 0x001602FB, "83bdbc000000000f84640100008b078bcfff750cff75088b4050ffd084c07415ff750c8d4ff4ff7508e8471a00008bc8e860010500", "A nonempty sPawn checks IsPawnSpace and removes every occupant before blocker admission."),
    ("spawn_blocker_recheck", "apply_space_damage", 0x00160330, "8b47f48d4ff46a00ff750cff75088b400cffd084c0742e8b078bcf6a03ff750cff75088b407cffd084c075198b078bcf6a09ff750cff75088b407cffd084c00f84f7000000", "After removal, IsBlocked is rerun; only Water or Chasm may pass a still-blocked result."),
    ("spawn_factory_add", "apply_space_damage", 0x00160375, "8b47f48d4ff46a00ff750cff75088b400cffd0ffb5c40000008845d783ec188bccc741140f000000c74110000000008379141072048b01eb028bc16affc600008d85ac0000006a0050e80d7deaffb9f06b8d00e8234a0e008bd88d4ff4a154d28b008983201300008d45c8ff750cff75085350e8d3e40000", "The accepted path constructs the named pawn and calls Board:AddPawn at the original x/y."),
    ("kill_tile_loop", "kill_tile_occupants", 0x001B0490, "56578bf933f68b87a40000002b87a0000000c1f80285c0742b0f1f80000000008b8fa00000006a008b0cb1e820ce08008b87a4000000462b87a0000000c1f8023bf072dc5f5ec3", "Iterate every tile pawn pointer and invoke Pawn:Kill(false)."),
    ("pawn_kill_logical_clear", "pawn_kill", 0x0023D307, "8b068b4010ffd084c075326a9c8d8ea4080000c6862109000001c74628ffffffffc74620ffffffffc74624ffffffffe8553beaff6a008bcee85cd7ffff", "A live pawn receives the removal flag and current/related coordinates -1 before cleanup."),
)


DIRECT_EDGE_SPECS = (
    ("phase_to_pawn_transport", "phase_transition", 0x0018953C, "e81fa7ffff", "phase_pawn_transport", 0x00183C60),
    ("phase_to_base_start_dispatch", "phase_transition", 0x00189543, "e8789cffff", "base_start_dispatch", 0x001831C0),
    ("pawn_transport_to_readd", "phase_pawn_transport", 0x00183CA0, "e8dbf7feff", "preserved_pawn_readd", 0x00173480),
    ("pawn_transport_to_optional_auto_deploy", "phase_pawn_transport", 0x00183CFE, "e81d000000", None, 0x00183D20),
    ("readd_to_set_space_entry", "preserved_pawn_readd", 0x001734D2, "e849ce0b00", "pawn_set_space_entry", 0x00230320),
    ("set_space_entry_to_body", "pawn_set_space_entry", 0x0023032E, "e87dfeffff", "pawn_set_space", 0x002301B0),
    ("apply_to_core", "apply_space_damage", 0x001602E5, "e896c60400", "apply_damage_core", 0x001AC980),
    ("core_to_occupant_predicate_a", "apply_damage_core", 0x001ADC7E, "e8bd22ffff", "tile_has_live_occupant", 0x0019FF40),
    ("core_to_occupant_predicate_b", "apply_damage_core", 0x001ADC8B, "e8b022ffff", "tile_has_live_occupant", 0x0019FF40),
    ("core_to_pawn_kill", "apply_damage_core", 0x001ADCA2, "e839f60800", "pawn_kill", 0x0023D2E0),
    ("core_to_set_building", "apply_damage_core", 0x001ADCB6, "e8e542ffff", "set_building_terrain", 0x001A1FA0),
    ("core_to_set_terrain", "apply_damage_core", 0x001ADCC3, "e8d83effff", "set_terrain", 0x001A1BA0),
    ("first_building_to_set_terrain", "set_building_terrain", 0x001A205D, "e83efbffff", "set_terrain", 0x001A1BA0),
    ("apply_to_kill_tile_occupants", "apply_space_damage", 0x0016032B, "e860010500", "kill_tile_occupants", 0x001B0490),
    ("kill_tile_to_pawn_kill", "kill_tile_occupants", 0x001B04BB, "e820ce0800", "pawn_kill", 0x0023D2E0),
    ("apply_to_pawn_factory", "apply_space_damage", 0x001603C8, "e8234a0e00", None, 0x00244DF0),
    ("apply_to_board_add_pawn", "apply_space_damage", 0x001603E8, "e8d3e40000", None, 0x0016E8C0),
)


CAPTURE_SPECS = (
    {
        "path": "recordings/20260430_230740_117/m05_turn_00_board.json",
        "size": 15_586,
        "sha256": "2a9186612e5fd0f655a40d76f777c64b8f65937bb4562bbb35d62172a7bc6b33",
        "map_source": "maps/caveAE4.map",
        "pylons": [[1, 5], [2, 1], [3, 1], [5, 3], [5, 4], [6, 1], [6, 6]],
        "bomb": [3, 4],
    },
    {
        "path": "recordings/20260506_114649_974/m26_turn_00_board.json",
        "size": 17_310,
        "sha256": "4a2e1604fe4d1a4a74e155be4eb719a6ffba6df5fe9d135d5ab93c454cf08f67",
        "map_source": "maps/cave2.map",
        "pylons": [[0, 5], [1, 5], [2, 2], [4, 5], [5, 1], [6, 1], [6, 6]],
        "bomb": [3, 4],
    },
    {
        "path": "recordings/20260510_213059_819/m22_turn_00_board.json",
        "size": 18_920,
        "sha256": "c3d668af9953df0b0635d2208991a689423e7f95f4cfed7c89ae54dd66539d2b",
        "map_source": "maps/caveAE2.map",
        "pylons": [[1, 2], [1, 6], [3, 6], [4, 1], [5, 5], [6, 2], [6, 3]],
        "bomb": [3, 4],
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


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveDropResolutionError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveDropResolutionError(f"RVA 0x{rva:08x} is not E8 rel32")
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def _expected_regions() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "evidence_class": "fact",
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "section": ".text",
            "boundary_basis": basis,
        }
        for region_id, start, end, digest, basis in REGION_SPECS
    ]


def _expected_data_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "evidence_class": "fact",
            "rva": f"0x{rva:08x}",
            "section": ".rdata",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hex": raw.hex(),
            "meaning": meaning,
        }
        for anchor_id, rva, raw, meaning in DATA_ANCHOR_SPECS
    ]


def _expected_field_bindings() -> list[dict[str, Any]]:
    return [
        {
            "id": field_id,
            "evidence_class": "fact",
            "name_anchor": name_anchor,
            "registration_region": region_id,
            "record_offset": f"+0x{offset:02x}",
        }
        for field_id, name_anchor, region_id, offset in FIELD_BINDING_SPECS
    ]


def _expected_method_bindings() -> list[dict[str, Any]]:
    return [
        {
            "id": method_id,
            "evidence_class": "fact",
            "name_anchor": name_anchor,
            "registration_region": registration_region,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
            "this_adjustment": this_adjustment,
        }
        for (
            method_id,
            name_anchor,
            registration_region,
            target_region,
            target_rva,
            this_adjustment,
        ) in METHOD_BINDING_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "evidence_class": "fact",
            "region_id": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(instruction_hex)),
            "sha256": hashlib.sha256(bytes.fromhex(instruction_hex)).hexdigest(),
            "instruction_hex": instruction_hex,
            "meaning": meaning,
        }
        for window_id, region_id, start, instruction_hex, meaning in CONTROL_WINDOW_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "evidence_class": "fact",
            "source_region": source_region,
            "from_rva": f"0x{from_rva:08x}",
            "instruction_hex": instruction_hex,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
        }
        for (
            edge_id,
            source_region,
            from_rva,
            instruction_hex,
            target_region,
            target_rva,
        ) in DIRECT_EDGE_SPECS
    ]


def _expected_corroboration() -> list[dict[str, Any]]:
    return [
        {
            "evidence_class": "corroboration",
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "mission_id": "Mission_Final_Cave",
            "turn": 0,
            "matched_map_source": spec["map_source"],
            "pylon_points": spec["pylons"],
            "pylon_count": 7,
            "pylon_hp_values": [2, 2, 2, 2, 2, 2, 2],
            "bigbomb_point": spec["bomb"],
            "identity_limit": (
                "The retained board did not independently record its executable hash; "
                "it corroborates the source/native interpretation but is not build identity."
            ),
        }
        for spec in CAPTURE_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "space_damage_layout": {
            "iDamage": "+0x08",
            "sPawn": "+0xa4",
            "sPawn_length": "+0xb4",
            "iTerrain": "+0xdc",
        },
        "terrain_then_spawn_order": {
            "core_damage_and_terrain_before_sPawn": True,
            "building_terrain_value": 1,
            "road_terrain_value": 0,
            "terrain_none_value": 10,
            "building_uses_special_setter": True,
            "other_explicit_terrain_uses_generic_setter": True,
        },
        "ordinary_pylons": {
            "pylons_per_map": 7,
            "dropper_records_per_pylon": 2,
            "construction_tile_unoccupied": True,
            "source_i_damage": 0,
            "first_impact_current_hp": 1,
            "first_impact_max_hp": 1,
            "second_impact_current_hp": 2,
            "second_impact_max_hp": 2,
            "later_startup_enemy_admission_rejected_by_permanent_block": True,
            "retained_capture_count": 3,
        },
        "pre_start_occupancy": {
            "exact_map_spawn_lists_empty": True,
            "surface_transition_boardplayer_state": 5,
            "carried_pawn_logical_coordinates_before_base_start": [-1, -1],
            "carried_pawn_readd_returns_before_base_start": True,
            "state_five_skips_native_auto_deploy_tail": True,
            "only_source_reachable_pre_pylon_spawn": (
                "optional enemy at bomb_loc"
            ),
            "bomb_loc_is_deployment_tile": True,
            "deployment_and_pylon_zones_disjoint_on_all_maps": True,
            "deployment_and_mountain_zones_disjoint_on_all_maps": True,
            "ordinary_pylon_is_pawn_space_at_construction": False,
        },
        "sPawn_collision": {
            "checks_occupancy_before_blocker_recheck": True,
            "occupied_tile_action": "Pawn:Kill(false) for every tile occupant",
            "live_pawn_logical_coordinates_cleared_to_minus_one": True,
            "blocker_recheck_after_removal": True,
            "still_blocked_water_or_chasm_allowed": True,
            "other_still_blocked_tiles_abort_before_factory": True,
            "accepted_path_constructs_named_pawn": True,
            "accepted_path_adds_at_original_coordinates": True,
        },
        "final_cave_bomb": {
            "record_sPawn": "BigBomb",
            "record_iTerrain": 0,
            "optional_enemy_spawned_at_same_reserved_point": True,
            "startup_bomb_point_not_spawn_blocked": True,
            "optional_enemy_is_replaced_when_branch_taken": True,
            "replacement_candidates_exclude_player_building_environment_danger": True,
            "replacement_candidates_do_not_exclude_enemy": True,
            "replacement_candidates_do_not_exclude_spawn_block_map": True,
            "selected_enemy_killed_before_blocker_recheck": True,
            "bigbomb_materializes_only_if_blocker_recheck_passes": True,
            "destroyed_pylon_permanent_block_can_abort_after_enemy_kill": True,
        },
        "solver_handoff": {
            "simulator_change_required": False,
            "reason": (
                "The solver starts from a fresh settled bridge board, which already "
                "contains 2-HP pylons and the resolved replacement result. "
                "Replacement projection must keep its pending marker and must not "
                "fabricate RNG, a coordinate, a UID, an enemy death, or successful "
                "BigBomb materialization before that read."
            ),
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "space_damage_layout_is_exact",
            "evidence_class": "fact",
            "claim": "Exact native registration binds iDamage, sPawn, and iTerrain to SpaceDamage offsets +0x08, +0xa4, and +0xdc.",
            "supports": ["i_damage", "s_pawn", "i_terrain"],
        },
        {
            "id": "terrain_precedes_spawn_resolution",
            "evidence_class": "inference",
            "claim": "Board application completes the core damage/terrain path before the nonempty-sPawn branch. BigBomb therefore assigns Road before occupied-tile removal and pawn admission.",
            "supports": ["core_before_spawn", "terrain_field_dispatch", "building_or_generic_terrain", "apply_to_core", "core_to_set_terrain"],
        },
        {
            "id": "carried_pawns_are_offboard_before_startmission",
            "evidence_class": "inference",
            "claim": (
                "Phase transition copies every carried pawn pointer into its "
                "transport, loads the replacement Board, and sends the complete "
                "transport through SetSpace(-1,-1) plus new-Board admission. That "
                "loop returns before BaseStart. The exact Surface handoff reaches "
                "transition in BoardPlayer state five, which skips the optional "
                "native auto-deployment tail, so "
                "no carried surface coordinate can occupy a pylon during its "
                "Board:IsPawnSpace construction check."
            ),
            "supports": [
                "final_end_settlement",
                "phase_collects_carried_pawns",
                "phase_readd_before_base_start",
                "phase_transport_dispatch",
                "state_five_skips_auto_deploy",
                "carried_pawns_offboard_and_readded",
                "pawn_space_fields_commit",
                "phase_to_pawn_transport",
                "phase_to_base_start_dispatch",
                "pawn_transport_to_readd",
                "pawn_transport_to_optional_auto_deploy",
                "readd_to_set_space_entry",
                "set_space_entry_to_body",
            ],
        },
        {
            "id": "ordinary_pylons_materialize_at_two_hp",
            "evidence_class": "inference",
            "claim": "All exact cave maps have empty spawn lists. Carried pawns remain offboard through BaseStart entry; StartMission's only pre-pylon spawn is confined to a deployment tile, and every deployment zone is disjoint from pylons. Each ordinary pylon therefore keeps zero damage: its first independent record creates a 1/1 Building and the identical second record raises the embedded ValueBar maximum to two and applies +1, leaving a 2/2 pylon. Three retained exact-map turn-zero boards corroborate seven 2-HP pylons each.",
            "supports": ["final_cave_startup", "carried_pawns_are_offboard_before_startmission", "final_cave_startup_effect_order", "final_cave_block_spawn_lifetime", "building_first_application", "building_repeat_full_hp", "value_bar_initializer", "value_bar_add_delta", "value_bar_maximum"],
        },
        {
            "id": "occupied_spawn_records_kill_before_recheck",
            "evidence_class": "inference",
            "claim": "For nonempty sPawn, native application calls the registered Pawn:Kill(false) on every current tile occupant, which flags a live pawn for removal and clears its logical coordinates, then reruns IsBlocked before factory construction and Board:AddPawn.",
            "supports": ["spawn_collision_kill", "kill_tile_loop", "pawn_kill_logical_clear", "spawn_blocker_recheck", "spawn_factory_add", "pawn_kill"],
        },
        {
            "id": "startup_optional_enemy_is_replaced_by_bigbomb",
            "evidence_class": "inference",
            "claim": "When the shipped optional branch places an enemy at bomb_loc, that deployment point is disjoint from both temporary mountain and permanent pylon blocks. The later Road+sPawn BigBomb record therefore removes the enemy with Pawn:Kill(false), passes its blocker recheck, and materializes BigBomb at the same reserved point; it is neither a failed spawn nor a displacement.",
            "supports": [LUA_SOURCE_SPEC["path"], "final_cave_startup", "final_cave_block_spawn_lifetime", "terrain_precedes_spawn_resolution", "occupied_spawn_records_kill_before_recheck"],
        },
        {
            "id": "replacement_enemy_collision_is_blocker_conditional",
            "evidence_class": "inference",
            "claim": "Later AddBomb selection excludes player occupancy, Buildings, and environment danger, but excludes neither enemies nor the spawn-block map. An enemy at impact is killed before IsBlocked is rerun, and BigBomb is added only if that recheck passes. A destroyed pylon point can retain BLOCKED_PERM, so selecting that point can kill its enemy yet abort before BigBomb construction.",
            "supports": [LUA_SOURCE_SPEC["path"], "final_cave_replacement", "final_cave_block_spawn_lifetime", "occupied_spawn_records_kill_before_recheck"],
        },
        {
            "id": "solver_boundary_remains_settled_read",
            "evidence_class": "inference",
            "claim": "No Rust semantic change follows: settled bridge input already includes the resolved pylons, terrain, occupants, and whether BigBomb materialized. Pending replacement remains intentionally non-fabricated until a new settled read.",
            "supports": ["ordinary_pylons_materialize_at_two_hp", "startup_optional_enemy_is_replaced_by_bigbomb", "replacement_enemy_collision_is_blocker_conditional"],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "death_damage_callbacks_and_attribution",
            "question": "What complete callback/corpse/credit sequence follows DAMAGE_DEATH?",
            "static_status": "This map closes direct Pawn:Kill(false) replacement, not every numeric/death-damage status and callback branch.",
            "next_evidence": "Trace the generic DAMAGE_DEATH core separately if kill attribution becomes solver-visible.",
        },
        {
            "id": "adversarial_modified_collisions",
            "question": "What happens for modified effects on Water, Chasm, corpses, multi-space pawns, or other unusual blockers?",
            "static_status": "The exact blocker exceptions, shipped startup path, and later permanent-pylon abort are pinned; other adversarial identities are not source-reachable here.",
            "next_evidence": "Build a separate controlled-case matrix rather than extending this ordinary-source claim.",
        },
        {
            "id": "concrete_replacement_point_and_block_state",
            "question": "Which later replacement point is selected and does a surviving spawn block reject BigBomb?",
            "static_status": "Selection does not exclude the spawn-block map. A selected enemy is killed before recheck, but BLOCKED_PERM on a destroyed pylon aborts materialization.",
            "next_evidence": "Consume the fresh settled bridge board rather than predicting the runtime point or block state.",
        },
        {
            "id": "startup_visual_impact_interleave",
            "question": "How do simultaneous drop animations overlap on screen?",
            "static_status": "Both records reach impact and their settled state is exact; wall-clock visual ordering is not.",
            "next_evidence": "Capture timestamped presentation telemetry only if UI automation needs it.",
        },
        {
            "id": "concrete_startup_rng_coordinates_and_uids",
            "question": "Which concrete enemy identities, selector points, and UIDs occur in a future startup?",
            "static_status": "Collision behavior is exact for any selected occupant; concrete RNG outputs remain runtime inputs.",
            "next_evidence": "Consume the fresh settled bridge board.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do other executable builds resolve drops identically?",
            "static_status": "Native evidence is keyed only to Windows build 13725832.",
            "next_evidence": "Produce an independent build-keyed map.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    dependencies = [
        {
            "id": dependency_id,
            "artifact": artifact,
            "artifact_sha256": digest,
            "role": role,
        }
        for dependency_id, artifact, digest, role in DEPENDENCY_SPECS
    ]
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
            "base_scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": [{**LUA_SOURCE_SPEC, "evidence_class": "fact"}],
        },
        "dependencies": dependencies,
        "runtime_corroboration": _expected_corroboration(),
        "supersedes": {
            "artifact": next(
                artifact
                for dependency_id, artifact, _digest, _role in DEPENDENCY_SPECS
                if dependency_id == "final_cave_startup_effect_order"
            ),
            "resolved_facets": [
                "pre_start_pylon_occupancy",
                "ordinary_pylon_terrain_and_health",
                "bigbomb_terrain_before_spawn",
                "occupied_sPawn_collision_order",
                "startup_optional_enemy_replacement",
                "ordinary_startup_drop_collision",
            ],
            "remaining_gap_ids": [item["id"] for item in _unresolved()],
        },
        "refines": {
            "artifact": next(
                artifact
                for dependency_id, artifact, _digest, _role in DEPENDENCY_SPECS
                if dependency_id == "final_cave_replacement"
            ),
            "finding": "bigbomb_drop_resolution_path_is_exact",
            "qualification": (
                "The dispatch-to-AddPawn route is exact, but factory construction "
                "and AddPawn occur only when the post-occupant blocker recheck "
                "accepts the selected point."
            ),
        },
        "method": {
            "boundary_review": "Focused Ghidra 12.1.3 phase-carried Pawn SetSpace, SpaceDamage layout, terrain, ValueBar, Board predicate, Pawn Kill, and AddPawn admission review.",
            "binary_verification": "Capstone 5.0.7 rechecks every region, control window, registration pointer, vtable pointer, and direct E8 edge.",
            "source_review": "The exact startup Lua/map tree, empty cave-map spawn lists, Final Cave source, seven immutable predecessor artifacts, and a fresh accepted-tree spawn-block lifetime reproduction bind source-reachable record order and occupancy.",
            "corroboration_review": "Three hash-pinned historical turn-zero boards are joined to exact cave map pylon zones; they corroborate 2-HP settled pylons without asserting executable identity.",
            "limitations": [
                "Every native address applies only to the pinned Windows executable.",
                "Historical board captures are corroboration, not executable identity evidence.",
                "Concrete RNG results, UIDs, and wall-clock presentation remain runtime inputs.",
                "A later replacement's concrete point and surviving spawn-block state remain runtime inputs.",
                "Generic DAMAGE_DEATH callbacks and adversarial modified-state collisions remain separate boundaries.",
            ],
        },
        "contracts": _contracts(),
        "regions": _expected_regions(),
        "data_anchors": _expected_data_anchors(),
        "field_bindings": _expected_field_bindings(),
        "method_bindings": _expected_method_bindings(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": {
            "lua_source_count": 1,
            "dependency_count": len(DEPENDENCY_SPECS),
            "runtime_corroboration_count": len(CAPTURE_SPECS),
            "region_count": len(REGION_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "field_binding_count": len(FIELD_BINDING_SPECS),
            "method_binding_count": len(METHOD_BINDING_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "finding_count": len(_findings()),
            "unresolved_count": len(_unresolved()),
            "ordinary_pylon_two_hp_proven": True,
            "pre_start_pylon_occupancy_excluded": True,
            "terrain_before_spawn_proven": True,
            "occupied_sPawn_collision_order_proven": True,
            "optional_startup_enemy_replacement_proven": True,
            "simulator_change_required": False,
        },
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_source(content_root: Path, startup: Mapping[str, Any]) -> None:
    support_specs = [
        *startup["sources"]["lua_files"],
        *startup["sources"]["maps"],
    ]
    for spec in support_specs:
        support_path = content_root / spec["path"]
        if support_path.is_symlink() or not support_path.is_file():
            raise FinalCaveDropResolutionError(
                f"startup source {spec['path']} is not a regular file"
            )
        support_raw = support_path.read_bytes()
        if (
            len(support_raw) != spec["size"]
            or hashlib.sha256(support_raw).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveDropResolutionError(
                f"startup source {spec['path']} differs"
            )

    path = content_root / LUA_SOURCE_SPEC["path"]
    raw = path.read_bytes()
    if (
        len(raw) != LUA_SOURCE_SPEC["size"]
        or hashlib.sha256(raw).hexdigest() != LUA_SOURCE_SPEC["sha256"]
    ):
        raise FinalCaveDropResolutionError("Final Cave source identity differs")
    text = raw.decode("utf-8")
    for needle in (
        "Board:SpawnPawn(self:NextPawn(),bomb_loc)",
        "building.iTerrain = TERRAIN_BUILDING",
        'effect:AddDropper(building,"combat/tiles_grass/building_fall.png")\r\n\t\teffect:AddDropper(building,"combat/tiles_grass/building_fall.png")',
        'add_bomb.sPawn = "BigBomb"',
        "add_bomb.iTerrain = TERRAIN_ROAD",
    ):
        if needle not in text:
            raise FinalCaveDropResolutionError("Final Cave source contract differs")

    for map_spec in startup["sources"]["maps"]:
        map_text = (content_root / map_spec["path"]).read_text(encoding="utf-8")
        for needle in (
            '["spawns"] = {},',
            '["spawn_ids"] = {},',
            '["spawn_points"] = {},',
        ):
            if needle not in map_text:
                raise FinalCaveDropResolutionError(
                    f"cave map {map_spec['path']} has a nonempty spawn contract"
                )
        pylons = {tuple(point) for point in map_spec["zones"]["pylons"]}
        deployment = {
            tuple(point) for point in map_spec["zones"]["deployment"]
        }
        mountains = {
            tuple(point) for point in map_spec["zones"]["mountain"]
        }
        if (
            pylons & deployment
            or mountains & deployment
            or pylons & mountains
        ):
            raise FinalCaveDropResolutionError(
                f"cave map {map_spec['path']} has overlapping deployment, pylon, or mountain zones"
            )


def _verify_dependencies(repository_root: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for dependency_id, relative, digest, _role in DEPENDENCY_SPECS:
        path = repository_root / relative
        if path.is_symlink() or not path.is_file():
            raise FinalCaveDropResolutionError(f"dependency {dependency_id} missing")
        value = _read_json(path)
        if not isinstance(value, Mapping) or _canonical_sha256(value) != digest:
            raise FinalCaveDropResolutionError(f"dependency {dependency_id} differs")
        values[dependency_id] = value
    return values


def _verify_corroboration(repository_root: Path, startup: Mapping[str, Any]) -> None:
    source_maps = {
        item["path"]: sorted(item["zones"]["pylons"])
        for item in startup["sources"]["maps"]
    }
    for spec in CAPTURE_SPECS:
        path = repository_root / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise FinalCaveDropResolutionError(f"capture {spec['path']} missing")
        raw = path.read_bytes()
        if len(raw) != spec["size"] or hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise FinalCaveDropResolutionError(f"capture {spec['path']} differs")
        value = json.loads(raw)
        board = value["data"]["bridge_state"]
        if board.get("mission_id") != "Mission_Final_Cave" or board.get("turn") != 0:
            raise FinalCaveDropResolutionError(f"capture {spec['path']} phase differs")
        buildings = sorted(
            [int(tile["x"]), int(tile["y"]), int(tile.get("building_hp", 0))]
            for tile in board["tiles"]
            if tile.get("terrain") == "building"
        )
        expected_buildings = sorted([x, y, 2] for x, y in spec["pylons"])
        if buildings != expected_buildings:
            raise FinalCaveDropResolutionError(f"capture {spec['path']} pylons differ")
        if sorted(spec["pylons"]) != source_maps.get(spec["map_source"]):
            raise FinalCaveDropResolutionError(f"capture {spec['path']} map join differs")
        bombs = sorted(
            [int(unit["x"]), int(unit["y"])]
            for unit in board["units"]
            if unit.get("type") == "BigBomb"
        )
        if bombs != [spec["bomb"]]:
            raise FinalCaveDropResolutionError(f"capture {spec['path']} bomb differs")


def build_final_cave_drop_resolution_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final Cave drop-resolution map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveDropResolutionError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveDropResolutionError("executable identity differs")

    repository_root = Path(__file__).resolve().parents[2]
    dependencies = _verify_dependencies(repository_root)
    try:
        validate_final_cave_block_spawn_lifetime_map(
            executable,
            content_root,
            dependencies["final_cave_block_spawn_lifetime"],
        )
    except FinalCaveBlockSpawnLifetimeError as exc:
        raise FinalCaveDropResolutionError(
            f"live spawn-block lifetime dependency differs: {exc}"
        ) from exc
    _verify_source(content_root, dependencies["final_cave_startup"])
    _verify_corroboration(repository_root, dependencies["final_cave_startup"])

    ranges: dict[str, tuple[int, int]] = {}
    region_bytes: dict[str, bytes] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        try:
            body = _region_bytes(image, data, start, end - start, ".text", region_id)
        except Exception as exc:
            raise FinalCaveDropResolutionError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise FinalCaveDropResolutionError(f"region {region_id} bytes differ")
        ranges[region_id] = (start, end)
        region_bytes[region_id] = body
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveDropResolutionError(str(exc)) from exc

    anchors = {anchor_id: (rva, raw) for anchor_id, rva, raw, _meaning in DATA_ANCHOR_SPECS}
    for anchor_id, rva, raw, _meaning in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise FinalCaveDropResolutionError(f"data anchor {anchor_id} differs")

    for _field_id, name_anchor, region_id, offset in FIELD_BINDING_SPECS:
        name_rva, _raw = anchors[name_anchor]
        body = region_bytes[region_id]
        if struct.pack("<I", image.image_base + name_rva) not in body:
            raise FinalCaveDropResolutionError(f"field binding {region_id} name differs")
        encoded_offset = bytes([0x6A, offset]) if offset < 0x80 else b"\x68" + struct.pack("<I", offset)
        if encoded_offset not in body:
            raise FinalCaveDropResolutionError(f"field binding {region_id} offset differs")

    for (
        method_id,
        name_anchor,
        registration_region,
        _target_region,
        target_rva,
        this_adjustment,
    ) in METHOD_BINDING_SPECS:
        name_rva, _raw = anchors[name_anchor]
        body = region_bytes[registration_region]
        if struct.pack("<I", image.image_base + name_rva) not in body:
            raise FinalCaveDropResolutionError(f"method binding {method_id} name differs")
        if struct.pack("<I", image.image_base + target_rva) not in body:
            raise FinalCaveDropResolutionError(f"method binding {method_id} target differs")
        adjustment = b"\xc7\x45\xec" + struct.pack("<I", this_adjustment)
        if adjustment not in body:
            raise FinalCaveDropResolutionError(f"method binding {method_id} adjustment differs")

    region_by_id = {region_id: (start, end) for region_id, start, end, _digest, _basis in REGION_SPECS}
    for window_id, region_id, start, instruction_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(instruction_hex)
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise FinalCaveDropResolutionError(f"control window {window_id} differs")
        region_start, region_end = region_by_id[region_id]
        if not (region_start <= start < start + len(expected) <= region_end):
            raise FinalCaveDropResolutionError(f"control window {window_id} escapes region")
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded[region_id].get(cursor)
            if instruction is None:
                raise FinalCaveDropResolutionError(f"control window {window_id} is not instruction-aligned")
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise FinalCaveDropResolutionError(f"control window {window_id} ends inside an instruction")

    for (
        edge_id,
        source_region,
        from_rva,
        instruction_hex,
        target_region,
        target_rva,
    ) in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(instruction_hex)
        instruction = decoded[source_region].get(from_rva)
        if instruction is None or instruction[1] != expected:
            raise FinalCaveDropResolutionError(f"direct edge {edge_id} bytes differ")
        if _direct_target(from_rva, expected) != target_rva:
            raise FinalCaveDropResolutionError(f"direct edge {edge_id} target differs")
        if target_region is not None and target_rva not in decoded[target_region]:
            raise FinalCaveDropResolutionError(f"direct edge {edge_id} target is not an instruction")

    return _expected_shape()


def validate_final_cave_drop_resolution_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise FinalCaveDropResolutionError("drop-resolution map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "ordinary_pylon_two_hp_proven": True,
        "pre_start_pylon_occupancy_excluded": True,
        "terrain_before_spawn_proven": True,
        "occupied_sPawn_collision_order_proven": True,
        "optional_startup_enemy_replacement_proven": True,
        "simulator_change_required": False,
    }


def validate_final_cave_drop_resolution_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, dependency, byte, or prose drift."""
    expected = build_final_cave_drop_resolution_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveDropResolutionError(
            "drop-resolution map differs from exact-build analysis"
        )
    result = validate_final_cave_drop_resolution_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_drop_resolution_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
