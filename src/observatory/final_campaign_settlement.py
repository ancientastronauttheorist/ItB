"""Reproduce the exact-build Final campaign-settlement boundary.

This immutable continuation starts at the shipped Final Cave
``Board:StartMechTravel()`` script and follows the pinned Windows executable
through travel settlement, completed-battle classification, run-save teardown,
profile result accounting, and activation of the final-victory presentation.

The map is a static control-flow and persistence-path proof.  It does not claim
wall-clock presentation timings, a particular live run's file contents, or
equivalence for another executable build.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_campaign_settlement_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
SUPERSEDED_END_SETTLEMENT_ARTIFACT_SHA256 = (
    "541237f7e723c1ec56b0328cb1f137f2a6725bda55c588d0a7ebc74adc55be0c"
)


class FinalCampaignSettlementError(RuntimeError):
    """Raised when the reviewed campaign-settlement map cannot be reproduced."""


SOURCE_SPECS = (
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": ["Mission_Final_Cave:MissionEnd"],
        "reviewed_lines": [[116, 124]],
    },
)


REGION_SPECS = (
    {
        "id": "delete_file_wrapper",
        "start": 0x0009E5D0,
        "end": 0x0009E738,
        "sha256": "79af732fc2168bbcf5a7603ea9a88a7b6dac6f8360d2396780d26156668d2dda",
        "boundary_basis": "Ghidra 12.1.3 file-delete wrapper function body.",
    },
    {
        "id": "write_file_wrapper",
        "start": 0x0009F7C0,
        "end": 0x0009FA00,
        "sha256": "01561e7242c90f977d206026344e2768627cdf9e70cd99f7220e7d93d24879eb",
        "boundary_basis": "Ghidra 12.1.3 file-write wrapper function body.",
    },
    {
        "id": "victory_achievement_dispatch",
        "start": 0x000ED630,
        "end": 0x000ED748,
        "sha256": "4e83bf6b640a82ceab6ce26c62ba7194cb24598f9d71106485084b2cce34ac19",
        "boundary_basis": "Ghidra 12.1.3 victory-key dispatch function body.",
    },
    {
        "id": "final_victory_initializer",
        "start": 0x001185F0,
        "end": 0x001187C3,
        "sha256": "2bbabcc45beee55f86ec0dcf6b1569859bc043a8b87feb4ed7c0b307d1f195bd",
        "boundary_basis": "Ghidra 12.1.3 final-victory controller initializer body.",
    },
    {
        "id": "final_victory_renderer",
        "start": 0x001187D0,
        "end": 0x0011C399,
        "sha256": "6536c902378c90294bfcdda9c422bc85da904bee708d88fc4a5abc084ff3b505",
        "boundary_basis": "Ghidra 12.1.3 final-victory/credits renderer body.",
    },
    {
        "id": "victory_profile_dispatch",
        "start": 0x00150140,
        "end": 0x001501E8,
        "sha256": "29bff5a9acedc9af4d5e0c6b038ecccd212ead182a70c55cd4b402722663775c",
        "boundary_basis": "Ghidra 12.1.3 victory profile-dispatch body.",
    },
    {
        "id": "profile_settlement",
        "start": 0x001501F0,
        "end": 0x0015024F,
        "sha256": "926d2e9269459ed4da76ebcaac51fedec97ef6551d727c74a6b692eb67df5929",
        "boundary_basis": "Ghidra 12.1.3 campaign-result profile settlement body.",
    },
    {
        "id": "profile_pending_flush",
        "start": 0x00152260,
        "end": 0x001523FC,
        "sha256": "dd0e9dff3a1ee83a5b7303c449f2f198e771107c4b4728cdce7abc58af8cc6d1",
        "boundary_basis": "Ghidra 12.1.3 pending profile/run buffer flush body.",
    },
    {
        "id": "profile_serializer_writer",
        "start": 0x00152400,
        "end": 0x00152C17,
        "sha256": "22bdf232b7b71f4a30d72cf3ed210a888338853b1490c644bd38d4355717d9a0",
        "boundary_basis": "Ghidra 12.1.3 profile serializer/write body.",
    },
    {
        "id": "board_travel_state_machine",
        "start": 0x00169BF0,
        "end": 0x0016A1F5,
        "sha256": "c047a08e5f274e629b6fec7151c94c89f5576ec3bbf11b0535546fb65d7c7877",
        "boundary_basis": "Ghidra 12.1.3 Board effect/travel update body.",
    },
    {
        "id": "start_mech_travel_handler",
        "start": 0x00174A80,
        "end": 0x00174CBA,
        "sha256": "04bea81c9dc876ea05a86141fb92b8e2ada82462309b550cce30523cebba146a",
        "boundary_basis": "Ghidra 12.1.3 StartMechTravel binding body.",
    },
    {
        "id": "boardplayer_state_six",
        "start": 0x00183C50,
        "end": 0x00183C5B,
        "sha256": "bbea90f22335daf7517a4cbfd792e41d6749d99dfb6e9f1996c0ad4d7dd522fa",
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer state-6 predicate body.",
    },
    {
        "id": "boardplayer_outcome",
        "start": 0x001937C0,
        "end": 0x001937C7,
        "sha256": "705bd97156f230addc79eb9489880df1d2a025762435056cf5a33937b8508e79",
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer outcome getter body.",
    },
    {
        "id": "profile_history_update",
        "start": 0x001E2730,
        "end": 0x001E28A0,
        "sha256": "cb501b7333e61b2c327c08ca3049a0235a8787306de4d2b22ee6100bd7275ab3",
        "boundary_basis": "Ghidra 12.1.3 historical campaign-stat update body.",
    },
    {
        "id": "campaign_end_manager",
        "start": 0x0020A670,
        "end": 0x0020A877,
        "sha256": "ea8b86f445ae612fbeeced4628a8cccc381018a6b8fcf454c83283f1489c62da",
        "boundary_basis": "Ghidra 12.1.3 campaign-end manager update body.",
    },
    {
        "id": "run_save_teardown",
        "start": 0x0020A880,
        "end": 0x0020AA32,
        "sha256": "074a7272115b3b67c3aafa6338366f21b29e610443e489e9a6672760f839cdf3",
        "boundary_basis": "Ghidra 12.1.3 completed-run save teardown body.",
    },
    {
        "id": "campaign_run_snapshot",
        "start": 0x0020D810,
        "end": 0x0020D834,
        "sha256": "761688b3281d264e11960323f778c976aa177cbb348669bfdd608b910711cd13",
        "boundary_basis": "Ghidra 12.1.3 campaign run-snapshot wrapper body.",
    },
    {
        "id": "world_map_battle_tick",
        "start": 0x0020EE60,
        "end": 0x0020F9F2,
        "sha256": "3ed314fbd5b9c24a0c017d5b29b10f059b951769e949b3a06907bfcf83f361ee",
        "boundary_basis": "Ghidra 12.1.3 world-map active-battle update body.",
    },
    {
        "id": "campaign_terminal_predicate",
        "start": 0x0020FA00,
        "end": 0x0020FA85,
        "sha256": "670b07eead8b3d75c12f18ffd3a26c0444b5c7e0a89a11e1ff7098e60ec27d11",
        "boundary_basis": "Ghidra 12.1.3 campaign terminal-result predicate body.",
    },
    {
        "id": "ordinary_mission_cleanup",
        "start": 0x0020FFE0,
        "end": 0x002102CC,
        "sha256": "b11fbe1c31cbdeb6da8bb6f73041bee4c48d723d47ac1201527aac2ded4fc8c3",
        "boundary_basis": "Ghidra 12.1.3 ordinary completed-mission cleanup body.",
    },
    {
        "id": "secured_island_count",
        "start": 0x002113E0,
        "end": 0x0021141B,
        "sha256": "a3be97dd1decdf525cef5c54d5a4995627d2e96e60632ebe0eec7593fa246e58",
        "boundary_basis": "Ghidra 12.1.3 four-island secured-flag counter body.",
    },
    {
        "id": "campaign_result_gateway",
        "start": 0x00217A20,
        "end": 0x00217D48,
        "sha256": "3675ae3b02423e82feaacebfb9c162550996a6d85bc6068214bf567a90333364",
        "boundary_basis": "Ghidra 12.1.3 campaign-result top-screen gateway body.",
    },
    {
        "id": "top_screen_dispatcher",
        "start": 0x00218200,
        "end": 0x0021973C,
        "sha256": "a7d82c875d51b357c40bd78762613567c2ea302e1e5875825a3d524573b6397d",
        "boundary_basis": "Ghidra 12.1.3 top-screen update/renderer dispatcher body.",
    },
    {
        "id": "start_mech_travel_registration_window",
        "start": 0x00279EC7,
        "end": 0x00279EE9,
        "sha256": "6ef6b686f82903d3ce3895a2e4f70d99e7caf31baaa014b5c79dc64d92cf1ecd",
        "boundary_basis": (
            "Instruction-aligned Luabind registration window inside a larger "
            "reviewed function; this is not a function boundary."
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "start_mech_travel_binding",
        "region_id": "start_mech_travel_registration_window",
        "reference_rva": 0x00279EDD,
        "instruction_hex": "689c868300",
        "string_rva": 0x0043869C,
        "text": "StartMechTravel",
        "role": "Names the Lua Board method registered to the pinned handler pointer.",
    },
    {
        "id": "big_bomb_lookup",
        "region_id": "start_mech_travel_handler",
        "reference_rva": 0x00174B53,
        "instruction_hex": "baeceb8200",
        "string_rva": 0x0042EBEC,
        "text": "BigBomb",
        "role": "Identifies the bomb pawn located by ordinary Final Cave travel setup.",
    },
    {
        "id": "lock_bomb_script",
        "region_id": "board_travel_state_machine",
        "reference_rva": 0x00169FB0,
        "instruction_hex": "6888e88200",
        "string_rva": 0x0042E888,
        "text": "Board:LockBomb()",
        "role": "Names the script queued after ordinary mech travel drains.",
    },
    {
        "id": "fade_explode_script",
        "region_id": "board_travel_state_machine",
        "reference_rva": 0x00169FDD,
        "instruction_hex": "686ce88200",
        "string_rva": 0x0042E86C,
        "text": "Board:Fade(FADE_EXPLODE)",
        "role": "Names the fade script queued after the bomb-lock script.",
    },
    {
        "id": "final_flavor_localization",
        "region_id": "final_victory_renderer",
        "reference_rva": 0x00119F2E,
        "instruction_hex": "68b4ba8200",
        "string_rva": 0x0042BAB4,
        "text": "Victory_Final_Flavor",
        "role": "Pins the final-victory flavor localization branch.",
    },
    {
        "id": "final_protected_localization",
        "region_id": "final_victory_renderer",
        "reference_rva": 0x0011A0DB,
        "instruction_hex": "689cba8200",
        "string_rva": 0x0042BA9C,
        "text": "Victory_Final_Protected",
        "role": "Pins the protected-population final-victory presentation.",
    },
    {
        "id": "final_billions_localization",
        "region_id": "final_victory_renderer",
        "reference_rva": 0x0011A2C5,
        "instruction_hex": "68e0ba8200",
        "string_rva": 0x0042BAE0,
        "text": "Victory_Final_Billions",
        "role": "Pins the billions-saved final-victory presentation.",
    },
    {
        "id": "profile_file",
        "region_id": "profile_serializer_writer",
        "reference_rva": 0x00152AD3,
        "instruction_hex": "688c108200",
        "string_rva": 0x0042108C,
        "text": "profile.lua",
        "role": "Names the persistent profile output selected by the settlement writer.",
    },
    {
        "id": "run_save_file",
        "region_id": "run_save_teardown",
        "reference_rva": 0x0020A90B,
        "instruction_hex": "6898108200",
        "string_rva": 0x00421098,
        "text": "saveData.lua",
        "role": "Names the primary completed-run save removed by teardown.",
    },
    {
        "id": "old_run_save_file",
        "region_id": "run_save_teardown",
        "reference_rva": 0x0020A956,
        "instruction_hex": "68cc108200",
        "string_rva": 0x004210CC,
        "text": "saveData.lua.old",
        "role": "Names the old completed-run save removed by teardown.",
    },
    {
        "id": "backup_run_save_file",
        "region_id": "run_save_teardown",
        "reference_rva": 0x0020A9A1,
        "instruction_hex": "6890d98200",
        "string_rva": 0x0042D990,
        "text": "saveData.lua.backup",
        "role": "Names the backup completed-run save removed by teardown.",
    },
    {
        "id": "victory_achievement_suffix",
        "region_id": "victory_achievement_dispatch",
        "reference_rva": 0x000ED669,
        "instruction_hex": "6878a28200",
        "string_rva": 0x0042A278,
        "text": "_Victory_",
        "role": "Pins construction of the squad/difficulty victory achievement key.",
    },
)


DATA_POINTER_SPECS = (
    {
        "id": "boardplayer_outcome_slot",
        "data_rva": 0x00430194,
        "vtable_va": 0x00830148,
        "slot_offset": 0x4C,
        "target_region": "boardplayer_outcome",
        "target_rva": 0x001937C0,
        "role": "BoardPlayer outcome-code virtual slot used by campaign classification.",
    },
    {
        "id": "boardplayer_state_six_slot",
        "data_rva": 0x0043019C,
        "vtable_va": 0x00830148,
        "slot_offset": 0x54,
        "target_region": "boardplayer_state_six",
        "target_rva": 0x00183C50,
        "role": "BoardPlayer completed-state virtual slot used by both consumers.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "start_travel_initialization",
        "region_id": "start_mech_travel_handler",
        "start_rva": 0x00174AAD,
        "instruction_hex": (
            "c787e0740000010000008d45e46a04c687d42c000000"
            "c787d02c00000000000050c787d82c000000009040e813f3ffff"
            "508d8fc02c0000e8772ff1ff"
        ),
        "meaning": "Enable travel mode, reset travel state, set 4.5, and populate +0x2cc0.",
    },
    {
        "id": "effect_queue_precedes_travel",
        "region_id": "board_travel_state_machine",
        "start_rva": 0x00169C46,
        "instruction_hex": "8b86502c00008d9e502c0000888d57ffffff3b43040f8491010000",
        "meaning": "Process Board +0x2c50 effects before entering the travel-vector path.",
    },
    {
        "id": "travel_queue_gate",
        "region_id": "board_travel_state_machine",
        "start_rva": 0x00169DF2,
        "instruction_hex": "8b86c02c00008dbec02c00003b47040f8423020000",
        "meaning": "Compare the +0x2cc0 travel vector begin/end before travel processing.",
    },
    {
        "id": "travel_completion_gate",
        "region_id": "board_travel_state_machine",
        "start_rva": 0x00169F67,
        "instruction_hex": (
            "8b073b47040f85ab00000080bedc740000000f859e000000"
            "8d8d58ffffff"
        ),
        "meaning": (
            "Require an empty travel vector and ordinary +0x74dc mode before "
            "final scripts."
        ),
    },
    {
        "id": "ordinary_cleanup_exclusion",
        "region_id": "world_map_battle_tick",
        "start_rva": 0x0020F0F5,
        "instruction_hex": (
            "8b018b4054ffd084c0746580bb2053000000742283bb34520000027d09"
            "80bb405300000074108b8704c200008a800c17000084c0743a83bf40c0000000742c"
            "8b8f04c200008a810c17000084c0751381c1cc2b0000898f50d600008b01ff5008"
            "eb096a008bcfe8800e0000e88bceecff"
        ),
        "meaning": (
            "State 6 reaches ordinary cleanup only outside the qualifying "
            "Final campaign case."
        ),
    },
    {
        "id": "campaign_eligibility",
        "region_id": "campaign_terminal_predicate",
        "start_rva": 0x0020FA31,
        "instruction_hex": (
            "80be2453000000744783be38520000027d0980be44530000007435"
            "8b8e04c2000085c9742b80b90c1700000075228b018b4054ffd084c07417"
        ),
        "meaning": (
            "Require Final campaign flags, an active non-tutorial battle, "
            "and state 6."
        ),
    },
    {
        "id": "campaign_result_mapping",
        "region_id": "campaign_terminal_predicate",
        "start_rva": 0x0020FA6A,
        "instruction_hex": "8b8e04c200008b01ff504c83e803f7d85e1bc083c002c3",
        "meaning": (
            "Map BoardPlayer outcome code 3 to result 2 and every other code "
            "to result 1."
        ),
    },
    {
        "id": "manager_settlement_order",
        "region_id": "campaign_end_manager",
        "start_rva": 0x0020A699,
        "instruction_hex": (
            "837e08010f85aa0000008b4e1085c90f849f000000e84d53000085c0"
            "0f8492000000e8c00100008b4e1083ec0c8bc48965f050e83f310000"
            "83ec18c745fc000000008bcc68dcdf8000e829d7dfffe87448f4ff8b4e10"
            "83c418ffb028010000e803530000508d4e2cc745fcffffffffe813d30000"
            "8b4e10c7460803000000e8e45200008b4e1083f8010f94c00fb6c050"
            "e8b26c00005083ec188bcc68dcdf8000e8d2d6dfffe81d48f4ff83c418"
            "8bc8e8a35af4ff"
        ),
        "meaning": (
            "Classify, tear down, snapshot, present, count islands, and settle "
            "profile in order."
        ),
    },
    {
        "id": "victory_gateway_branch",
        "region_id": "campaign_result_gateway",
        "start_rva": 0x00217A50,
        "instruction_hex": (
            "8b750883fe01c745fc000000000f94c00fb6c050e807fbffff8b5d0c"
            "899fdc0c000089b7d80c0000c787b4130000ffffffffc787c8110000ffffffff"
            "83fe010f85da000000c745c400000000c745c800000000c745cc00000000"
            "c645fc0133f68b45148b4d102bc1c1f80385c0745b908b04f183b8dc000000ff"
            "750a8a809000000084c074378b0cf18d45d850e8fe910000508d4dc4c645fc02"
            "e8217de3ffc645fc018b45ec83f810720f406a0150ff75d8e8f9fcdeff83c40c"
            "8b4d108b4514462bc1c1f8033bf072a65383ec0c8d45c48bcc50e8075de5ff"
            "8d8f68bd0000e8bc0af0ff"
        ),
        "meaning": (
            "Only campaign result 1 initializes the embedded final-victory "
            "controller."
        ),
    },
    {
        "id": "top_victory_dispatch",
        "region_id": "top_screen_dispatcher",
        "start_rva": 0x00218398,
        "instruction_hex": "8a8368bd00008d8b68bd000084c0740ae82304f0ff",
        "meaning": "An active embedded final controller dispatches the final renderer.",
    },
    {
        "id": "profile_settlement_fields",
        "region_id": "profile_settlement",
        "start_rva": 0x00150202,
        "instruction_hex": (
            "84db740657e834ffffffe83f40f8ff89be400100008d8ef4000000"
            "89414488594884db74138d47fe33d285c00f4fd08b8180000000ff0490"
            "e8f12409008bcee8ba210000"
        ),
        "meaning": (
            "Record island count, difficulty, win flag, win histogram, "
            "history, and profile write."
        ),
    },
    {
        "id": "profile_write_path",
        "region_id": "profile_serializer_writer",
        "start_rva": 0x00152AC8,
        "instruction_hex": (
            "8d45988bcf50e84d010000688c1082008bd0c645fc058d4db0e83a7aefff"
            "83c404c645fc078b45ac83f810720f406a0150ff7598e8ff4cebff83c40c"
            "83ec18c745ac0f0000008bccc745a800000000c6459800896594"
            "c741140f000000c74110000000008379141072048b01eb028bc16affc60000"
            "8d45c86a0050e88855ebff83ec18c645fc088bccc741140f000000"
            "c74110000000008379141072048b01eb028bc16affc600008d45b06a0050"
            "e85555ebffc645fc07e83cccf4ff"
        ),
        "meaning": (
            "Serialize the profile, select profile.lua, and invoke the exact "
            "file writer."
        ),
    },
    {
        "id": "delete_file_api",
        "region_id": "delete_file_wrapper",
        "start_rva": 0x0009E699,
        "instruction_hex": (
            "84db7469837d1c108d45086a000f43450850e898592e0083c40883f8ff744e"
            "837d1c108d45080f43450850ff15e0607d00"
        ),
        "meaning": "After an existence check, invoke the imported DeleteFileA slot.",
    },
    {
        "id": "create_always_api",
        "region_id": "write_file_wrapper",
        "start_rva": 0x0009F943,
        "instruction_hex": "0f43450868800000006a026a006a00680000004050ff15f4607d00",
        "meaning": "Open the selected path for GENERIC_WRITE with CREATE_ALWAYS.",
    },
    {
        "id": "write_file_api",
        "region_id": "write_file_wrapper",
        "start_rva": 0x0009F9BD,
        "instruction_hex": "837d34108d4dd06a0051ff75308d45200f4345205057ff15d4607d00",
        "meaning": "Pass the serialized buffer and length to the imported WriteFile slot.",
    },
    {
        "id": "victory_achievement_route",
        "region_id": "victory_profile_dispatch",
        "start_rva": 0x001501D0,
        "instruction_hex": "e87b40f8ff50ff75088d4e70e84fd4f9ff",
        "meaning": "Read difficulty and dispatch island-count victory accounting.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "tick_to_ordinary_cleanup",
        "source_region": "world_map_battle_tick",
        "from_rva": 0x0020F15B,
        "instruction_hex": "e8800e0000",
        "target_region": "ordinary_mission_cleanup",
        "target_rva": 0x0020FFE0,
        "meaning": "Ordinary state-6 cleanup target outside the Final exclusion.",
    },
    {
        "id": "manager_to_initial_predicate",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A6AE,
        "instruction_hex": "e84d530000",
        "target_region": "campaign_terminal_predicate",
        "target_rva": 0x0020FA00,
        "meaning": "Require a nonzero terminal campaign result.",
    },
    {
        "id": "manager_to_run_save_teardown",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A6BB,
        "instruction_hex": "e8c0010000",
        "target_region": "run_save_teardown",
        "target_rva": 0x0020A880,
        "meaning": "Remove the completed-run save set first.",
    },
    {
        "id": "manager_to_run_snapshot",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A6CC,
        "instruction_hex": "e83f310000",
        "target_region": "campaign_run_snapshot",
        "target_rva": 0x0020D810,
        "meaning": "Snapshot the run for result presentation.",
    },
    {
        "id": "manager_to_gateway_predicate",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A6F8,
        "instruction_hex": "e803530000",
        "target_region": "campaign_terminal_predicate",
        "target_rva": 0x0020FA00,
        "meaning": "Pass the exact result code to the presentation gateway.",
    },
    {
        "id": "manager_to_result_gateway",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A708,
        "instruction_hex": "e813d30000",
        "target_region": "campaign_result_gateway",
        "target_rva": 0x00217A20,
        "meaning": "Initialize the campaign result top screen.",
    },
    {
        "id": "manager_to_win_predicate",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A717,
        "instruction_hex": "e8e4520000",
        "target_region": "campaign_terminal_predicate",
        "target_rva": 0x0020FA00,
        "meaning": "Derive the exact result==1 profile win boolean.",
    },
    {
        "id": "manager_to_island_count",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A729,
        "instruction_hex": "e8b26c0000",
        "target_region": "secured_island_count",
        "target_rva": 0x002113E0,
        "meaning": "Count the four secured-island flags.",
    },
    {
        "id": "manager_to_profile_settlement",
        "source_region": "campaign_end_manager",
        "from_rva": 0x0020A748,
        "instruction_hex": "e8a35af4ff",
        "target_region": "profile_settlement",
        "target_rva": 0x001501F0,
        "meaning": "Record the island count and win boolean in the profile.",
    },
    {
        "id": "teardown_primary_delete",
        "source_region": "run_save_teardown",
        "from_rva": 0x0020A91A,
        "instruction_hex": "e8b13ce9ff",
        "target_region": "delete_file_wrapper",
        "target_rva": 0x0009E5D0,
        "meaning": "Delete saveData.lua.",
    },
    {
        "id": "teardown_old_delete",
        "source_region": "run_save_teardown",
        "from_rva": 0x0020A965,
        "instruction_hex": "e8663ce9ff",
        "target_region": "delete_file_wrapper",
        "target_rva": 0x0009E5D0,
        "meaning": "Delete saveData.lua.old.",
    },
    {
        "id": "teardown_backup_delete",
        "source_region": "run_save_teardown",
        "from_rva": 0x0020A9B0,
        "instruction_hex": "e81b3ce9ff",
        "target_region": "delete_file_wrapper",
        "target_rva": 0x0009E5D0,
        "meaning": "Delete saveData.lua.backup.",
    },
    {
        "id": "teardown_to_pending_flush",
        "source_region": "run_save_teardown",
        "from_rva": 0x0020AA14,
        "instruction_hex": "e84778f4ff",
        "target_region": "profile_pending_flush",
        "target_rva": 0x00152260,
        "meaning": "Flush pending profile state after clearing the run buffer.",
    },
    {
        "id": "gateway_to_victory_initializer",
        "source_region": "campaign_result_gateway",
        "from_rva": 0x00217B2F,
        "instruction_hex": "e8bc0af0ff",
        "target_region": "final_victory_initializer",
        "target_rva": 0x001185F0,
        "meaning": "Initialize final-victory state only in the result-1 branch.",
    },
    {
        "id": "top_to_victory_renderer",
        "source_region": "top_screen_dispatcher",
        "from_rva": 0x002183A8,
        "instruction_hex": "e82304f0ff",
        "target_region": "final_victory_renderer",
        "target_rva": 0x001187D0,
        "meaning": "Render the active final-victory controller.",
    },
    {
        "id": "profile_to_victory_dispatch",
        "source_region": "profile_settlement",
        "from_rva": 0x00150207,
        "instruction_hex": "e834ffffff",
        "target_region": "victory_profile_dispatch",
        "target_rva": 0x00150140,
        "meaning": "On win, dispatch victory achievement accounting.",
    },
    {
        "id": "profile_to_history",
        "source_region": "profile_settlement",
        "from_rva": 0x0015023A,
        "instruction_hex": "e8f1240900",
        "target_region": "profile_history_update",
        "target_rva": 0x001E2730,
        "meaning": "Update the campaign history record.",
    },
    {
        "id": "profile_to_writer",
        "source_region": "profile_settlement",
        "from_rva": 0x00150241,
        "instruction_hex": "e8ba210000",
        "target_region": "profile_serializer_writer",
        "target_rva": 0x00152400,
        "meaning": (
            "Serialize and write the updated profile when profile output is "
            "enabled."
        ),
    },
    {
        "id": "victory_to_achievement_key",
        "source_region": "victory_profile_dispatch",
        "from_rva": 0x001501DC,
        "instruction_hex": "e84fd4f9ff",
        "target_region": "victory_achievement_dispatch",
        "target_rva": 0x000ED630,
        "meaning": "Build and dispatch the squad/difficulty victory key.",
    },
    {
        "id": "profile_writer_to_file_writer",
        "source_region": "profile_serializer_writer",
        "from_rva": 0x00152B7F,
        "instruction_hex": "e83cccf4ff",
        "target_region": "write_file_wrapper",
        "target_rva": 0x0009F7C0,
        "meaning": "Persist serialized profile.lua bytes.",
    },
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


def _bytes_at(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    *,
    executable: bool | None = True,
    expected_section: str | None = None,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCampaignSettlementError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    section = next(
        (
            candidate
            for candidate in image.sections
            if candidate.virtual_address <= rva
            and rva + size
            <= candidate.virtual_address + candidate.raw_size
        ),
        None,
    )
    if section is None or (
        executable is not None and section.executable is not executable
    ):
        expected = "executable" if executable else "non-executable"
        raise FinalCampaignSettlementError(
            f"RVA 0x{rva:08x} is not in {expected} file-backed data"
        )
    if expected_section is not None and section.name != expected_section:
        raise FinalCampaignSettlementError(
            f"RVA 0x{rva:08x} section differs: "
            f"{expected_section!r} != {section.name!r}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCampaignSettlementError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


def _expected_sources() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "symbols": spec["symbols"],
            "reviewed_lines": spec["reviewed_lines"],
            "evidence_class": "fact",
        }
        for spec in SOURCE_SPECS
    ]


def _expected_regions() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
            "section": ".text",
            "boundary_basis": spec["boundary_basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_string_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "evidence_class": "fact",
            "reference_rva": f"0x{spec['reference_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "string_rva": f"0x{spec['string_rva']:08x}",
            "text": spec["text"],
            "role": spec["role"],
        }
        for spec in STRING_ANCHOR_SPECS
    ]


def _expected_data_pointers() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "data_rva": f"0x{spec['data_rva']:08x}",
            "section": ".rdata",
            "vtable_va": f"0x{spec['vtable_va']:08x}",
            "slot_offset": f"0x{spec['slot_offset']:02x}",
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + spec['target_rva']:08x}",
            "role": spec["role"],
        }
        for spec in DATA_POINTER_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start_rva']:08x}",
            "size": len(bytes.fromhex(spec["instruction_hex"])),
            "sha256": hashlib.sha256(
                bytes.fromhex(spec["instruction_hex"])
            ).hexdigest(),
            "instruction_hex": spec["instruction_hex"],
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "kind": "direct_rel32",
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "target": {
                "type": "region",
                "region": spec["target_region"],
                "rva": f"0x{spec['target_rva']:08x}",
            },
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "start_mech_travel": {
            "lua_entry": "Board:StartMechTravel()",
            "registration_handler_rva": "0x00174a80",
            "travel_mode_offset": "0x74e0",
            "travel_vector_offset": "0x2cc0",
            "initial_delay_seconds": 4.5,
            "ordinary_mode_flag_offset": "0x74dc",
            "ordinary_bomb_lookup": "BigBomb",
            "bomb_coordinate_offsets": ["0x74d4", "0x74d8"],
        },
        "travel_settlement": {
            "effect_vector_offset": "0x2c50",
            "travel_vector_offset": "0x2cc0",
            "effect_vector_checked_first": True,
            "final_script_order": [
                "Board:LockBomb()",
                "Board:Fade(FADE_EXPLODE)",
            ],
            "final_scripts_require_empty_travel_vector": True,
            "final_scripts_require_ordinary_mode": True,
        },
        "campaign_terminal_result": {
            "required_map_offsets": {
                "final_campaign_flag": "0x5324 != 0",
                "island_or_override": "0x5238 > 1 or 0x5344 != 0",
                "active_battle": "0xc204 != 0",
                "non_tutorial_battle": "battle+0x170c == 0",
            },
            "completed_state": 6,
            "boardplayer_state_vtable_offset": "0x54",
            "boardplayer_outcome_vtable_offset": "0x4c",
            "outcome_storage_offset": "0x1900",
            "result_mapping": {
                "outcome_code_3": 2,
                "every_other_outcome_code": 1,
            },
            "consumer_semantics": {
                "result_1": "campaign win",
                "result_2": "campaign non-win/loss",
            },
        },
        "campaign_settlement": {
            "manager_state_precondition": 1,
            "manager_state_after_handoff": 3,
            "ordered_steps": [
                "classify terminal campaign result",
                "remove run save and backups",
                "snapshot run presentation data",
                "open campaign result gateway",
                "derive result==1 win boolean",
                "count four secured-island flags",
                "settle profile result and request profile write",
            ],
            "run_save_files_removed": [
                "saveData.lua",
                "saveData.lua.old",
                "saveData.lua.backup",
            ],
            "secured_island_flag_offsets": [
                "0x15c",
                "0x2c8",
                "0x434",
                "0x5a0",
            ],
        },
        "profile_result": {
            "difficulty_offset": "0x138",
            "win_flag_offset": "0x13c",
            "island_count_offset": "0x140",
            "win_histogram_base_offset": "0x174",
            "win_histogram_index": "max(island_count - 2, 0)",
            "win_only_dispatch": "squad/difficulty _Victory_ achievement key",
            "history_update_invoked": True,
            "profile_output": "profile.lua",
            "writer_precondition": "profile serializer flag +0x54 is nonzero",
            "file_open_mode": "GENERIC_WRITE, CREATE_ALWAYS",
            "write_api": "WriteFile",
        },
        "final_victory_presentation": {
            "gateway_result_required": 1,
            "embedded_controller_offset": "0xbd68",
            "localization_keys": [
                "Victory_Final_Flavor",
                "Victory_Final_Protected",
                "Victory_Final_Billions",
            ],
            "shared_renderer_warning": (
                "The renderer is also reachable from a menu/credits route; "
                "campaign provenance comes from the result-1 gateway call."
            ),
        },
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Ghidra 12.1.3 decompiler, vtable, reference, imported-API, "
            "and call-graph review followed the shipped cave MissionEnd script "
            "through the exact campaign-end manager."
        ),
        "byte_verification": (
            "Capstone redecodes each published executable region from its "
            "declared start; the verifier rechecks exact windows, strings, "
            "vtable pointers, and every direct rel32 edge."
        ),
        "limitations": [
            (
                "Every native address and conclusion applies only to the "
                "pinned Windows executable."
            ),
            (
                "Static control flow proves relative ordering and reachable "
                "file/UI paths, not wall-clock timing or a particular live "
                "run's bytes."
            ),
            (
                "The profile writer's exact +0x54 precondition is preserved "
                "rather than silently assumed away."
            ),
            (
                "The profile value passed from +0x128 to the result gateway is "
                "intentionally not semantically named here."
            ),
            "macOS and other executable builds require independent maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "start_mech_travel_initializes_native_queue",
            "evidence_class": "inference",
            "claim": (
                "Mission_Final_Cave:MissionEnd's StartMechTravel script resolves "
                "to the pinned native handler. It enables Board travel mode, "
                "resets its state, sets 4.5 seconds, populates +0x2cc0, and in "
                "ordinary mode locates BigBomb and stores its coordinates."
            ),
            "supports": [
                "scripts/missions/final/mission_final_two.lua",
                "start_mech_travel_binding",
                "start_mech_travel_initialization",
                "big_bomb_lookup",
            ],
            "limitations": [
                "The travel-vector element schema is not reconstructed."
            ],
        },
        {
            "id": "travel_queue_finishes_with_bomb_lock_and_fade",
            "evidence_class": "inference",
            "claim": (
                "The Board update drains +0x2c50 effects before +0x2cc0 travel. "
                "Once ordinary travel is empty, the reviewed path constructs "
                "Board:LockBomb() followed by Board:Fade(FADE_EXPLODE)."
            ),
            "supports": [
                "effect_queue_precedes_travel",
                "travel_queue_gate",
                "travel_completion_gate",
                "lock_bomb_script",
                "fade_explode_script",
            ],
            "limitations": [
                "Individual animation timestamps remain runtime behavior."
            ],
        },
        {
            "id": "campaign_terminal_predicate_is_exact",
            "evidence_class": "inference",
            "claim": (
                "The campaign terminal predicate requires the pinned Final "
                "campaign flags, a non-tutorial active battle, and BoardPlayer "
                "state 6. It reads outcome +0x1900 through the exact vtable slot "
                "and returns result 2 for outcome code 3 or result 1 otherwise."
            ),
            "supports": [
                "campaign_eligibility",
                "campaign_result_mapping",
                "boardplayer_state_six_slot",
                "boardplayer_outcome_slot",
            ],
            "limitations": [
                "Win/loss names are assigned from the downstream UI/profile "
                "consumers, not a debug symbol."
            ],
        },
        {
            "id": "final_campaign_bypasses_ordinary_cleanup",
            "evidence_class": "inference",
            "claim": (
                "BoardPlayer state 6 is a common completed-battle state, not "
                "the victory screen itself. The world-map tick invokes ordinary "
                "mission cleanup only outside the matching Final campaign case, "
                "leaving the active battle for campaign-end settlement."
            ),
            "supports": [
                "ordinary_cleanup_exclusion",
                "tick_to_ordinary_cleanup",
                "campaign_terminal_result",
            ],
            "limitations": [
                "Other ordinary cleanup branches are outside this focused claim."
            ],
        },
        {
            "id": "campaign_manager_settles_in_order",
            "evidence_class": "inference",
            "claim": (
                "For manager state 1 and a nonzero terminal result, the campaign "
                "manager tears down the completed-run saves, snapshots run data, "
                "passes the result to the top screen, changes manager state to 3, "
                "derives result==1, counts secured islands, and settles the profile "
                "in that exact relative order."
            ),
            "supports": [
                "manager_settlement_order",
                "manager_to_run_save_teardown",
                "manager_to_run_snapshot",
                "manager_to_result_gateway",
                "manager_to_island_count",
                "manager_to_profile_settlement",
            ],
            "limitations": [
                "The run-snapshot record's individual presentation fields are "
                "not named."
            ],
        },
        {
            "id": "completed_run_saves_are_removed",
            "evidence_class": "inference",
            "claim": (
                "The teardown selects saveData.lua, saveData.lua.old, and "
                "saveData.lua.backup in order and calls the same wrapper for "
                "each; that wrapper reaches the imported DeleteFileA slot after "
                "an existence check."
            ),
            "supports": [
                "run_save_file",
                "old_run_save_file",
                "backup_run_save_file",
                "teardown_primary_delete",
                "teardown_old_delete",
                "teardown_backup_delete",
                "delete_file_api",
            ],
            "limitations": [
                "OS-level deletion failure remains possible and is handled by "
                "native error reporting."
            ],
        },
        {
            "id": "victory_profile_and_achievement_path",
            "evidence_class": "inference",
            "claim": (
                "Profile settlement stores difficulty, result==1, and secured "
                "island count, increments the win histogram only on a win, "
                "updates campaign history, and invokes profile serialization. "
                "The win-only branch constructs the squad/difficulty _Victory_ key."
            ),
            "supports": [
                "profile_settlement_fields",
                "profile_to_victory_dispatch",
                "profile_to_history",
                "profile_to_writer",
                "victory_achievement_route",
                "victory_achievement_suffix",
            ],
            "limitations": [
                "This does not prove an online Steam synchronization timestamp."
            ],
        },
        {
            "id": "profile_write_path_is_pinned",
            "evidence_class": "inference",
            "claim": (
                "When the serializer's exact +0x54 precondition is nonzero, "
                "the settlement writer serializes profile state, selects "
                "profile.lua, opens it with GENERIC_WRITE and CREATE_ALWAYS, "
                "and passes the buffer to WriteFile."
            ),
            "supports": [
                "profile_write_path",
                "profile_file",
                "profile_writer_to_file_writer",
                "create_always_api",
                "write_file_api",
            ],
            "limitations": ["Actual filesystem success remains an OS/runtime result."],
        },
        {
            "id": "final_victory_renderer_handoff",
            "evidence_class": "inference",
            "claim": (
                "Campaign result 1 alone feeds the run snapshot into the embedded "
                "final-victory controller at +0xbd68. The top-screen dispatcher "
                "then calls the renderer containing Victory_Final_Flavor, "
                "Victory_Final_Protected, and Victory_Final_Billions."
            ),
            "supports": [
                "victory_gateway_branch",
                "gateway_to_victory_initializer",
                "top_victory_dispatch",
                "top_to_victory_renderer",
                "final_flavor_localization",
                "final_protected_localization",
                "final_billions_localization",
            ],
            "limitations": [
                "The renderer is shared with a menu/credits route; the campaign "
                "gateway is the provenance link."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust combat-simulator semantic change follows. These are "
                "post-combat campaign persistence and presentation boundaries; "
                "the solver must still stop at the live terminal boundary and "
                "consume later state only from fresh bridge/profile evidence."
            ),
            "supports": [
                "campaign_manager_settles_in_order",
                "final_victory_renderer_handoff",
            ],
            "limitations": [
                "Concrete cave RNG and live scheduler conformance remain "
                "separate work."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "runtime_campaign_settlement_timing",
            "question": (
                "What are the concrete live timestamps and file contents for "
                "one completed campaign?"
            ),
            "static_status": (
                "Relative control flow and reachable persistence/UI paths are "
                "exact; no runtime trace is claimed."
            ),
            "next_evidence": (
                "Capture a matched build-keyed Final completion trace when "
                "native tracing is available."
            ),
        },
        {
            "id": "profile_gateway_value_0x128",
            "question": (
                "What source-level name belongs to the profile value passed "
                "from +0x128 to the result gateway?"
            ),
            "static_status": (
                "The offset and handoff are pinned, but the field name is "
                "intentionally unresolved."
            ),
            "next_evidence": "Correlate controlled profile values with the final summary UI.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS/native builds implement the same settlement boundary?",
            "static_status": "Only Windows build 13725832 is mapped.",
            "next_evidence": "Repeat the focused map against an exact macOS binary.",
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": len(SOURCE_SPECS),
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "data_pointer_count": len(DATA_POINTER_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "post_travel_campaign_victory_proven": True,
        "run_save_teardown_proven": True,
        "profile_result_write_path_proven": True,
        "final_victory_presentation_proven": True,
        "simulator_change_required": False,
    }


def _expected_shape() -> dict[str, Any]:
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
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
        },
        "supersedes": {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_end_settlement.json"
            ),
            "artifact_sha256": SUPERSEDED_END_SETTLEMENT_ARTIFACT_SHA256,
            "resolved_gap_ids": ["post_travel_campaign_victory"],
            "continuation": (
                "The earlier immutable map ends after the cave MissionEnd "
                "effect/activity-clear boundary. This map continues from the "
                "registered StartMechTravel handler through campaign settlement."
            ),
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": _expected_sources(),
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_string_anchors(),
        "data_pointers": _expected_data_pointers(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "contracts": _contracts(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCampaignSettlementError("content root is not a directory")
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCampaignSettlementError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCampaignSettlementError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCampaignSettlementError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise FinalCampaignSettlementError(
                f"Lua source identity differs: {spec['path']}"
            )


def build_final_campaign_settlement_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final campaign-settlement boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCampaignSettlementError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCampaignSettlementError("executable identity differs")
    _verify_sources(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image,
                data,
                spec["start"],
                size,
                ".text",
                spec["id"],
            )
        except Exception as exc:
            raise FinalCampaignSettlementError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCampaignSettlementError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCampaignSettlementError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalCampaignSettlementError(
                f"string anchor {spec['id']} differs"
            )
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalCampaignSettlementError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCampaignSettlementError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalCampaignSettlementError(
                f"string reference {spec['id']} target differs"
            )

    for spec in DATA_POINTER_SPECS:
        raw = _bytes_at(
            image,
            data,
            spec["data_rva"],
            4,
            executable=False,
            expected_section=".rdata",
        )
        (target_va,) = struct.unpack("<I", raw)
        if target_va != image.image_base + spec["target_rva"]:
            raise FinalCampaignSettlementError(
                f"data pointer {spec['id']} target differs"
            )
        if spec["data_rva"] != (
            spec["vtable_va"] - image.image_base + spec["slot_offset"]
        ):
            raise FinalCampaignSettlementError(
                f"data pointer {spec['id']} vtable offset differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCampaignSettlementError(
                f"data pointer {spec['id']} target is not an instruction"
            )

    region_by_id = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCampaignSettlementError(
                f"control window {spec['id']} differs"
            )
        region = region_by_id[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCampaignSettlementError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCampaignSettlementError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCampaignSettlementError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(spec["instruction_hex"])
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        if instruction is None or instruction[1] != expected:
            raise FinalCampaignSettlementError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCampaignSettlementError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCampaignSettlementError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    edges = {spec["id"]: spec["from_rva"] for spec in DIRECT_EDGE_SPECS}
    if not (
        edges["manager_to_initial_predicate"]
        < edges["manager_to_run_save_teardown"]
        < edges["manager_to_run_snapshot"]
        < edges["manager_to_gateway_predicate"]
        < edges["manager_to_result_gateway"]
        < edges["manager_to_win_predicate"]
        < edges["manager_to_island_count"]
        < edges["manager_to_profile_settlement"]
    ):
        raise FinalCampaignSettlementError("campaign manager order differs")
    if not (
        edges["teardown_primary_delete"]
        < edges["teardown_old_delete"]
        < edges["teardown_backup_delete"]
        < edges["teardown_to_pending_flush"]
    ):
        raise FinalCampaignSettlementError("run-save teardown order differs")
    if not (
        edges["profile_to_victory_dispatch"]
        < edges["profile_to_history"]
        < edges["profile_to_writer"]
    ):
        raise FinalCampaignSettlementError("profile settlement order differs")
    string_refs = {
        spec["id"]: spec["reference_rva"] for spec in STRING_ANCHOR_SPECS
    }
    if not string_refs["lock_bomb_script"] < string_refs["fade_explode_script"]:
        raise FinalCampaignSettlementError("travel final-script order differs")
    return _expected_shape()


def validate_final_campaign_settlement_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCampaignSettlementError("campaign map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCampaignSettlementError("campaign map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "post_travel_campaign_victory_proven": True,
        "run_save_teardown_proven": True,
        "profile_result_write_path_proven": True,
        "final_victory_presentation_proven": True,
        "simulator_change_required": False,
    }


def validate_final_campaign_settlement_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_campaign_settlement_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCampaignSettlementError(
            "campaign map differs from exact-build analysis"
        )
    result = validate_final_campaign_settlement_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_campaign_settlement_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
