"""Reproduce the exact-build enemy-death event and credit boundary.

This continuation joins queued ``SkillEffect.iOwner`` state to the native
death processor, the environment owner, mission event delivery, and the
per-pawn credit buckets.  It also resolves the shipped Lua ``Skill.OnKill``
question narrowly: the seven shipped assignments are localization metadata,
not Lua callback definitions.  Exact event-frame visibility, achievement
counters, specialized pawn classes, and non-Windows equivalence remain open.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.content_inventory import build_manifest
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)
from src.observatory.zero_hp_cleanup_boundary import (
    ZeroHpCleanupBoundaryError,
    validate_zero_hp_cleanup_boundary_map,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_death_event_credit_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class DeathEventCreditBoundaryError(RuntimeError):
    """Raised when the reviewed death-event/credit boundary cannot reproduce."""


DEPENDENCY_SPEC = {
    "id": "zero_hp_cleanup_boundary",
    "path": (
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json"
    ),
    "file_sha256": (
        "f73215a5e7b3d4ef273e85f04841c1f3f5d6f2c73eab8a964f867524bb33aad4"
    ),
    "canonical_sha256": (
        "bf9713a2b46c524373599666c5113c0995bd841411d777d3a810895be1a03064"
    ),
    "role": (
        "Pins the DAMAGE_DEATH HP-zero handoff, later IsDead classification, "
        "and conditional dead-noncorpse Board cleanup boundary."
    ),
}


BASE_SCRIPTS_INVENTORY_SPEC = {
    "path": (
        "data/observatory/inventories/windows_build_13725832_31fe35265598_"
        "post_native_boundaries_restore_20260822.json"
    ),
    "size": 125_456,
    "sha256": "4be0c9382ab38ec264dd4673180eedc0c20f826569f790219002c1a35dae9355",
    "scripts_file_count": 305,
    "scripts_byte_count": 15_967_494,
    "base_scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
    "overlay_path": "scripts/modloader.lua",
    "accepted_overlay_files": [
        {
            "id": "restored_project_bridge",
            "size": 132_609,
            "sha256": (
                "8d765cb4d501f1cdc83a6423ad7c2f66e01d98844ec3e8afd1f3c099e4763c10"
            ),
        },
        {
            "id": "current_project_bridge",
            "size": 315_652,
            "sha256": (
                "f94fabbe75aad2463e08ab28bf052e31db95b7724f31adbfc002aa102675f1a2"
            ),
        },
    ],
}

# Published artifacts retain the two bridge overlays that were accepted when
# their evidence bodies were created. Later project-only bridge revisions may
# be admitted here after exact hash review without rewriting those immutable
# native artifacts; every non-overlay scripts entry must still match.
POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS = (
    {
        "id": "mission_piston_v408_project_bridge",
        "size": 315_686,
        "sha256": (
            "5af8e809e6ed036084c84caed97f6a51a84785db2c2c0ee0c150da99adabf22d"
        ),
    },
    {
        "id": "score_positioning_x87_project_bridge",
        "size": 338_859,
        "sha256": (
            "0ad8f0c65ad25a646b16439a57bfd0e47d21f6b4b3ba4b8a5c8b5bac77775989"
        ),
    },
    {
        "id": "enemy_tournament_hw_project_bridge",
        "size": 357_175,
        "sha256": (
            "1abb8001eb6402c26d59fb09c05c78159a9199267130eecf9c73ccfd7879a5ac"
        ),
    },
    {
        "id": "enemy_target_area_callback_project_bridge",
        "size": 365_924,
        "sha256": (
            "07af106b8cc2abab88fd215ed0ddfe04fc138ba9c4987f2500a445509898071d"
        ),
    },
)


SOURCE_SPECS = (
    {
        "path": "scripts/environments.lua",
        "size": 8_924,
        "sha256": "5f8a7d74f537abb33bc88c1f9669f3f6fabdd5c8c51aad3486d2e965e4fb80ec",
        "symbols": ["Env_Attack:ApplyEffect", "ENV_EFFECT", "Board:AddEffect"],
    },
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
        "symbols": ["Skill", "Skill.OnKill"],
    },
    {
        "path": "scripts/advanced/ae_weapons.lua",
        "size": 124_520,
        "sha256": "5566b679c696ab489e40a0189d0a63b699d01e9657f79a20e6f119239af1680f",
        "symbols": [
            "Prime_KO_Crack:GetSkillEffect",
            "Brute_KO_Combo:GetSkillEffect",
            "Ranged_Arachnoid:GetSkillEffect",
            "Ranged_KO_Combo:GetSkillEffect",
            "Science_KO_Crack:GetSkillEffect",
            "Support_KO_GridCharger:GetSkillEffect",
        ],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257",
        "symbols": ["Mission:BaseUpdate", "Mission.KilledVek", "EVENT_ENEMY_KILLED"],
    },
    {
        "path": "scripts/localization/Global_ae.csv",
        "size": 43_128,
        "sha256": "b07fc5c5e2ffc0a167d538ae5f52c69c26e3560d949cb7837038a2252db3b01d",
        "symbols": ["Skill_OnKill"],
    },
    {
        "path": "scripts/localization/Weapons_ae.csv",
        "size": 158_355,
        "sha256": "1b61022ce01ba36400056d6f871c9c6e0bfebb68f7911d52141ba76cc0fd76e2",
        "symbols": [
            "Prime_KO_Crack_OnKill",
            "Brute_KO_Combo_OnKill",
            "Ranged_Arachnoid_OnKill",
            "Ranged_KO_Combo_OnKill",
            "Science_KO_Crack_OnKill",
            "Support_KO_GridCharger_OnKill",
        ],
    },
)


ONKILL_KEYS = (
    "Prime_KO_Crack_OnKill",
    "Brute_KO_Combo_OnKill",
    "Ranged_Arachnoid_OnKill",
    "Ranged_KO_Combo_OnKill",
    "Science_KO_Crack_OnKill",
    "Support_KO_GridCharger_OnKill",
)


ONKILL_OCCURRENCES = (
    ("scripts/advanced/ae_weapons.lua", 792, 'OnKill = "Prime_KO_Crack_OnKill",'),
    ("scripts/advanced/ae_weapons.lua", 1585, 'OnKill = "Brute_KO_Combo_OnKill",'),
    ("scripts/advanced/ae_weapons.lua", 2065, 'OnKill = "Ranged_Arachnoid_OnKill",'),
    ("scripts/advanced/ae_weapons.lua", 2505, 'OnKill = "Ranged_KO_Combo_OnKill",'),
    ("scripts/advanced/ae_weapons.lua", 3610, 'OnKill = "Science_KO_Crack_OnKill",'),
    ("scripts/advanced/ae_weapons.lua", 4288, 'OnKill = "Support_KO_GridCharger_OnKill",'),
    ("scripts/global.lua", 258, 'OnKill = "",'),
)


REGION_SPECS = (
    ("effect_enqueue", 0x001606C0, 0x00160752, "0a07ee9377f4bc3bc13be075ccd2a45a01719c8181e231a4450b56d6dd98f4ae", "Board SkillEffect enqueue body."),
    ("skill_effect_copy", 0x00160760, 0x00160879, "30471eac4d66d47a928438248a7d8f26e2c0a6384bafe7b0c02e42b2250efcd6", "SkillEffect copy constructor."),
    ("effect_dispatcher", 0x001610D0, 0x00161C6F, "ccbecc70505f546c2d068ad7c95121f0c631aa27dd197127904de3faaff307c2", "Board SkillEffect record dispatcher."),
    ("effect_queue_insert", 0x00175670, 0x00175723, "ed358e0a1cc8e7f64cc80923066f4e54b7c99c4ea138b0f9917f512f36981a4b", "0x7c-byte SkillEffect vector insertion."),
    ("mission_damage_caller", 0x00190F90, 0x001910FB, "e140fc9436709cdbbc08dd910a249f735478fce110305e926bda3032ddb6fb4f", "Caller of the separate Pawn mission-damage accumulator."),
    ("get_event_count", 0x0020E780, 0x0020E7C1, "1914235348cc79735d409cecfb4af66c02d538a9cad2badef3527beff5394e0e", "Native GameMap event-count reader."),
    ("pawn_definition_load", 0x0022C0F0, 0x0022CBB7, "9c705957ab7a8afa137bb56e4d075b40a29ca8da45222fd318f2c821ac138148", "Pawn definition loader containing the Minor field load."),
    ("death_processor", 0x0022D5F0, 0x0022E325, "69e9121e9272ec2d865777ba0e7d810202df5f05ec380ab66d40f72445a90737", "Native Pawn death event and credit processor."),
    ("pawn_xp_accumulator", 0x00234F90, 0x002353A8, "9df1cb97cfac61fbca076b1c2eb0b911cd2f13d1dba5bf4eff60a61c6d206d93", "Pawn XP and iKillCount accumulator."),
    ("pawn_credit_consumer", 0x0023CB90, 0x0023D049, "be27dbc108924da9c1f4ebffa2bd24a17e7f24dae465081896981f49052f4d06", "Per-Pawn kill/any-kill/XP bucket consumer."),
    ("is_mech_thunk", 0x0023C8D0, 0x0023C8D7, "93be70843ae650ab49f4da225e76da80df9b55151167e3f8c732eb0a9253fa90", "Registered Pawn IsMech field thunk."),
    ("get_team_thunk", 0x0023D850, 0x0023D857, "a33ed4c54f724b1cdd526b3c3e8bfc670f9881db0df0a549f9dd82f82745c8cf", "Registered Pawn GetTeam field thunk."),
    ("mission_damage_accumulator", 0x0023DE20, 0x0023E0E5, "1305e6172f10ae534928ba8cf65b5f73122acaa799119aad0260c35522a53c60", "Separate health-delta iMissionDamage accumulator."),
    ("pawn_definition_store", 0x00240AE0, 0x0024209E, "92ad8d746d427511dbd27a845faa17d22240a8fe703d48c10a4b92e85aacd3f9", "Pawn definition writer binding named counter fields."),
    ("binding_table", 0x00279880, 0x002816B6, "51f3a81b7b832098c11f81beb1c85e1fe488434adce745dd8af5cb5af64200c2", "Global/Pawn Lua registrations containing environment, team, event, and method bindings."),
    ("iowner_binding", 0x002838D0, 0x00283963, "d0b1ba039795a65addbdc54ded073f92aacfed4623ef8ad03e0f504afd154733", "SkillEffect iOwner property registration."),
    ("get_event_count_binding", 0x0028E750, 0x0028E7E3, "eceff826e25e3119a7b2ced1b278183a9556033181b984f016ce6736bd38b38c", "Luabind Game:GetEventCount method wrapper."),
    ("outer_main_update", 0x000E45E0, 0x000E5650, "b5c2bd4bddb20bbda2dd87e2202c607f9ad9d6e5444a8dd361511e0ed15b81c1", "Outer update containing the sole direct event-publish call."),
    ("event_recorder", 0x0009BE90, 0x0009BEFF, "689f97fb534e0f7e8792e4ed7508a851f42171c34158b044581b5c488c0baaa2", "Generic native event recorder."),
    ("event_publisher", 0x0009BF00, 0x0009BF88, "49ceab3bd5073935a21e3df26de48f3b7669318e80dcb569d8f694271fff3ee3", "Pending-to-readable event publisher/reset."),
    ("string_counter_increment", 0x0009C050, 0x0009C108, "9e086b91246f719c304e40b96ee288e0797fabfbe712a8522886d8d17b989501", "String-keyed native counter add-or-insert helper."),
    ("context_set", 0x0009C200, 0x0009C2E6, "9c4765daa69e1334667c6c74cbced7501857babb890120d38fcd7d63ee896bc7", "Current native owner/context assignment."),
    ("context_copy", 0x0009C320, 0x0009C415, "422b66aed91782b148b2c023349c2fee08d979e8ca9f1c3e027ac9411b5d659e", "Native owner/context copy constructor."),
    ("context_build", 0x0009C420, 0x0009C57D, "44c9d62cd979ccd12ad78a344595ca03c6b0a42564bed96333a34d793a369dcb", "Native owner/context constructor."),
)


CONTROL_WINDOW_SPECS = (
    ("iowner_field_binding", "iowner_binding", 0x00283913, "c74208905e8300c7420c5c000000c742145c000000", "Bind SkillEffect.iOwner to record offset +0x5c."),
    ("effect_enqueue_copy_and_queue", "effect_enqueue", 0x001606EB, "8d4508c745fc00000000508d8d74ffffffe85f000000c745f0000080bf8d8574ffffffc645fc01508d8e502c0000e8524f01008d45f0508d8e5c2c0000e8d3520100", "Copy the by-value 0x7c-byte SkillEffect, then append it to Board+0x2c50."),
    ("skill_effect_copy_owner", "skill_effect_copy", 0x00160811, "8d4e608b47488946488b474c89464c8b47508946508b47548946548b47588946588b475c89465c", "Copy source +0x5c into destination +0x5c with the adjacent scalar fields."),
    ("queue_copy_stride", "effect_queue_insert", 0x001756F2, "8b4e04894d08894df0c745fc0100000085c9740657e854b0feff8346047c", "Invoke the SkillEffect copy constructor and advance the vector by 0x7c."),
    ("dispatch_build_owner_context", "effect_dispatcher", 0x00161293, "ff75648d8db0feffffc645fc03e87bb1f3ff", "Pass by-value SkillEffect +0x5c ([ebp+0x64]) into the owner-context constructor."),
    ("dispatch_install_owner_context", "effect_dispatcher", 0x0016131F, "8d85b0feffff508d8dfcfcffffe8efaff3ffc645fc068b85fcfcffff83f8ff750a390554d28b00740aeb3a390554d28b007521a190d28b003b8538fdffff75148d9500fdffffb958d28b00e891d0f0ff84c075118d85fcfcffffb954d28b0050e87caef3ff", "Copy the context, compare current owner at 0x8bd254, and install the new context when needed."),
    ("context_build_owner_field", "context_build", 0x0009C44F, "8b45088d4f04c745fc010000008907", "Store the constructor integer argument as context field zero."),
    ("env_effect_registration", "binding_table", 0x0027DDE4, "e8f7e5deff68b09683008d8d04f9ffff518bc8e8542addff8bd88b4b08ff710468f0d8ffffff33ff15c0647d00ff73048b3b57ff15e4647d006af6ff33ff158c647d00", "Publish ENV_EFFECT through the Lua integer-registration import with value -10."),
    ("team_enemy_registration", "binding_table", 0x0027E93A, "e8a1dadeff68949783008d8d14f8ffff518bc8e8fe1eddff8bd88b4b08ff710468f0d8ffffff33ff15c0647d00ff73048b3b57ff15e4647d006a06ff33ff158c647d00", "Publish TEAM_ENEMY through the same import with value 6."),
    ("event_enemy_registration", "binding_table", 0x002805A7, "8b5de48d8df8fcffff8bd3e829bedeff68a49a83008d8dbcf5ffff518bc8e88602ddff68805581008bc8e8ba02ddff", "Bind EVENT_ENEMY_KILLED to the exact value object at VA 0x815580."),
    ("get_event_count_target_binding", "binding_table", 0x0027D243, "c745ec80e76000ff75f0518d4dec51518bc8e8f6140100", "Register native target RVA 0x20e780 through the GetEventCount wrapper."),
    ("get_event_count_name_binding", "get_event_count_binding", 0x0028E792, "c70264ba8300c742082894830089420c", "Name the registered Game method GetEventCount and retain its target."),
    ("minor_field_load", "pawn_definition_load", 0x0022C4A2, "6a056858608300c60000e81fbbddff8bcfe8f8cee1ff83ec188883d0100000", "Load Lua Pawn.Minor and store it at Pawn+0x10d0."),
    ("death_capture_owner_and_mech", "death_processor", 0x0022D63D, "8a86e40900008b3d54d28b0089bd18ffffff", "Read Pawn IsMech +0x9e4 and capture current context owner 0x8bd254."),
    ("enemy_team_gate", "death_processor", 0x0022D83C, "8b86b000000083f8060f85e9040000", "Require Pawn team +0xb0 to equal TEAM_ENEMY (6)."),
    ("enemy_event_minor_split", "death_processor", 0x0022D93E, "8a86d010000068ffffff7f84c075046a02eb026a0ce838e5e6ff", "Record event 2 for non-Minor enemies and event 12 for Minor enemies."),
    ("mech_owner_credit", "death_processor", 0x0022DA0A, "8bbd18ffffff83ff020f87820000008bd78d4dc0e88de8e3ff83ec18c645fc088bcc89a520ffffffba8061830050e80323e2ff83c4048d8ea4080000c645fc098b01ff500850c645fc08e8f7e5e6ff8d4dc0c645fc00e86ba3ddff8bd78d4dc0e841e8e3ff83ec18c645fc0a8bccba7861830050e8bd22e2ff83c4046a01e8c3e5e6ff8d4dc0c645fc00e837a3ddff", "For eligible deaths and owners 0..2, add victim XP to xp_<owner> and one to kill_<owner>."),
    ("environment_xp_credit", "death_processor", 0x0022DA9B, "83ec188bcc89a520ffffff687cfc8200e860a3ddff8d8ea4080000c645fc0b8b01ff500850c645fc00e887e5e6ff", "For eligible deaths and owners outside 0..2, add victim XP to env_xp."),
    ("any_kill_owner_credit", "death_processor", 0x0022DAC9, "8bd78d4dd8e8dde7e3ff83ec18c645fc0c8bccba9461830050e85922e2ff83c4046a01e85fe5e6ffc645fc00", "Add one to any_kill_<owner> after the eligibility-specific branch."),
    ("counter_add_or_insert", "string_counter_increment", 0x0009C07A, "803d50d28b0000755d837d20108d4d0c8b451c8d550c0f434d0c03c1837d20108d4d0c0f434d0c51525051e87622fdff83c408b938d28b00508d45f050e80441feff8d450cb938d28b0050e826190000837df000740a8d48188b45080101eb068b4d08894818", "Insert the supplied string-keyed value or add it to the existing value."),
    ("event_record_pending", "event_recorder", 0x0009BE96, "803d50d28b00005675588b7508b9b0d28b00a1a4d28b00897508ff04b08d4508508d45f850e8a00afeff8b45f88b4d0c894814a100d28b008b0dfcd18b002bc1c1f8023bf07d0e85f6780aff04b1", "Increment total and pending event arrays and retain the supplied payload."),
    ("event_publish_pending", "event_publisher", 0x0009BF06, "68fcd18b00b9f0d18b00e83bbafeff8d45fcc745fc00000000506a508d4df0c745f000000000c745f400000000c745f800000000e8711000008d45f0b9fcd18b0050e813bbfeff", "Copy pending event counts to the readable array, then reset pending storage."),
    ("event_count_read", "get_event_count", 0x0020E783, "a1f4d18b008b15f0d18b002bc28b4d08c1f8023bc87d1485c978108b048a85c00f95c184c974115dc20400", "Return the readable event count for a valid event ID."),
    ("outer_publish_before_state_update", "outer_main_update", 0x000E55A7, "e87487f9ffe84f69fbffe8ea53ffff8b4f188b01ff5004", "Call the event publisher before the following outer-state virtual update."),
    ("credit_read_three_buckets", "pawn_credit_consumer", 0x0023CBBD, "8b96a40900008d4dd8e8e5f6e2ff83ec18c745fc000000008bccba7861830050e85e31e1ff83c404e8b6f3e5ffc745fcffffffff8b4dec8945a483f910720f416a0151ff75d8e8f8abdcff83c40c8b96a40900008d4dd8e897f6e2ff83ec18c745fc010000008bccba9461830050e81031e1ff83c404e868f3e5ffc745fcffffffff8b4dec8945ac83f910720f416a0151ff75d8e8aaabdcff83c40c8b96a40900008d4dd8e849f6e2ff83ec18c745fc020000008bccba8061830050e8c230e1ff83c404e81af3e5ffc745fcffffffff8b4dec8945b883f910720f416a0151ff75d8e85cabdcff83c40c", "Read kill_<PawnID>, any_kill_<PawnID>, and xp_<PawnID>."),
    ("credit_clear_kill", "pawn_credit_consumer", 0x0023CCAD, "8d4dc0e8fbf5e2ff50ba78618300c745fc030000008d4dd8e87630e1ff83c404c645fc04b938d28b00837de8007507e8af0ce6ffeb108d45d850e8040de6ffc7401800000000", "Clear the consumed kill_<PawnID> map value."),
    ("credit_clear_any_kill", "pawn_credit_consumer", 0x0023CD3A, "8b96a40900008d4dc0e868f5e2ff50ba94618300c745fc050000008d4dd8e8e32fe1ff83c404c645fc06b938d28b00837de8007507e81c0ce6ffeb108d45d850e8710ce6ffc7401800000000", "Clear the consumed any_kill_<PawnID> map value."),
    ("credit_clear_xp", "pawn_credit_consumer", 0x0023CDCD, "8b96a40900008d4dc0e8d5f4e2ff50ba80618300c745fc070000008d4dd8e8502fe1ff83c404c645fc08b938d28b00837de8007507e8890be6ffeb108d45d850e8de0be6ffc7401800000000", "Clear the consumed xp_<PawnID> map value."),
    ("credit_apply_xp_and_kills", "pawn_credit_consumer", 0x0023CED3, "807dbf008b45b8c745fcffffffff74068b4da48d0448508bcee89f80ffff8b7dac85ff0f84310100008a86e409000084c00f842301000083ec188bcc685c5a8300e8f7aedcff8b068bce8b4004ffd084c0741683ec188bcc68a0a98200e8dbaedcff8b068bceff500c01be8c090000", "Apply XP plus Extra_XP's two-per-kill bonus, then add any-kill count to Mech iKills."),
    ("xp_add_i_kill_count", "pawn_xp_accumulator", 0x00234FC4, "83bb80090000000f84b90300008b75088d45c401b3600a0000", "When XP tracking is enabled, add the supplied XP to Pawn+0xa60 iKillCount."),
    ("bind_i_kills", "pawn_definition_store", 0x00241988, "6a0668746e8300c60000e83966dcff6a008bcfe81065e4ff578d8ba408000089838c090000", "Bind iKills to Pawn+0x98c."),
    ("bind_i_kill_count", "pawn_definition_store", 0x00241B95, "6a0a68586f8300c60000e82c64dcff6a008bcfe80363e4ff83ec188983600a0000", "Bind iKillCount to Pawn+0xa60."),
    ("bind_i_mission_damage", "pawn_definition_store", 0x00241F14, "68a46e8300e8f25edcff6a008bcfe8895fe4ff6aff6aff83ec18898370110000", "Bind iMissionDamage to Pawn+0x1170."),
    ("mission_damage_health_delta", "mission_damage_accumulator", 0x0023DEBE, "8b83a80800008bf08b8b080a00002bf101b370110000833d604d89000175060135349d8b00", "Add the Pawn health delta to iMissionDamage; this is separate from death-owner credit."),
    ("mission_damage_caller_edge", "mission_damage_caller", 0x00190FDF, "8bcfe83ace0a00", "Call the separate mission-damage accumulator for the selected Pawn."),
    ("is_mech_thunk", "is_mech_thunk", 0x0023C8D0, "8a81e4090000c3", "Read Pawn+0x9e4 as IsMech."),
    ("get_team_thunk", "get_team_thunk", 0x0023D850, "8b81b0000000c3", "Read Pawn+0xb0 as GetTeam."),
)


DIRECT_EDGE_SPECS = (
    ("enqueue_copies_effect", "effect_enqueue", 0x001606FC, "e85f000000", "skill_effect_copy", 0x00160760),
    ("enqueue_appends_effect", "effect_enqueue", 0x00160719, "e8524f0100", "effect_queue_insert", 0x00175670),
    ("queue_insert_copies_effect", "effect_queue_insert", 0x00175707, "e854b0feff", "skill_effect_copy", 0x00160760),
    ("dispatcher_builds_owner_context", "effect_dispatcher", 0x001612A0, "e87bb1f3ff", "context_build", 0x0009C420),
    ("dispatcher_copies_owner_context", "effect_dispatcher", 0x0016132C, "e8efaff3ff", "context_copy", 0x0009C320),
    ("dispatcher_sets_owner_context", "effect_dispatcher", 0x0016137F, "e87caef3ff", "context_set", 0x0009C200),
    ("enemy_death_records_event", "death_processor", 0x0022D953, "e838e5e6ff", "event_recorder", 0x0009BE90),
    ("death_adds_xp_bucket", "death_processor", 0x0022DA54, "e8f7e5e6ff", "string_counter_increment", 0x0009C050),
    ("death_adds_kill_bucket", "death_processor", 0x0022DA88, "e8c3e5e6ff", "string_counter_increment", 0x0009C050),
    ("death_adds_env_xp", "death_processor", 0x0022DAC4, "e887e5e6ff", "string_counter_increment", 0x0009C050),
    ("death_adds_any_kill", "death_processor", 0x0022DAEC, "e85fe5e6ff", "string_counter_increment", 0x0009C050),
    ("outer_update_publishes_events", "outer_main_update", 0x000E55AC, "e84f69fbff", "event_publisher", 0x0009BF00),
    ("pawn_consumes_xp", "pawn_credit_consumer", 0x0023CEEC, "e89f80ffff", "pawn_xp_accumulator", 0x00234F90),
    ("mission_damage_is_separate", "mission_damage_caller", 0x00190FE1, "e83ace0a00", "mission_damage_accumulator", 0x0023DE20),
    ("game_registers_get_event_count", "binding_table", 0x0027D255, "e8f6140100", "get_event_count_binding", 0x0028E750),
)


ABSOLUTE_REFERENCE_SPECS = (
    ("i_owner_name", 0x00435E90, b"iOwner\0", (0x0022984F, 0x0022994F, 0x00283916)),
    ("env_effect_name", 0x004396B0, b"ENV_EFFECT\0", (0x0027DDEA,)),
    ("team_enemy_name", 0x00439794, b"TEAM_ENEMY\0", (0x0027E940,)),
    ("event_enemy_killed_name", 0x00439AA4, b"EVENT_ENEMY_KILLED\0", (0x002805B8,)),
    ("get_event_count_name", 0x00439428, b"GetEventCount\0", (0x0028E79B,)),
    ("minor_name", 0x00436058, b"Minor\0", (0x0022C4A5,)),
    ("xp_prefix", 0x00436180, b"xp_\0", (0x0022DA33, 0x0023CC74, 0x0023CDDD, 0x0023F66A)),
    ("kill_prefix", 0x00436178, b"kill_\0", (0x0022DA79, 0x0023CBD8, 0x0023CCB7)),
    ("any_kill_prefix", 0x00436194, b"any_kill_\0", (0x0022DADD, 0x0023CC26, 0x0023CD4A)),
    ("env_xp_name", 0x0042FC7C, b"env_xp\0", (0x0018F20C, 0x0018F228, 0x0022DAA7)),
    ("i_kills_name", 0x00436E74, b"iKills\0", (0x00240612, 0x0024198B)),
    ("i_kill_count_name", 0x00436F58, b"iKillCount\0", (0x00240958, 0x00241B98)),
    ("i_mission_damage_name", 0x00436EA4, b"iMissionDamage\0", (0x00240755, 0x00241F15)),
)


DATA_ANCHOR_SPECS = (
    (
        "event_enemy_killed_value",
        0x00415580,
        bytes.fromhex("02000000"),
        "The exact value object passed by EVENT_ENEMY_KILLED registration begins with integer 2.",
    ),
)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise DeathEventCreditBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise DeathEventCreditBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise DeathEventCreditBoundaryError("reviewed direct edge is not CALL rel32")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _text_absolute_operand_rvas(
    image: Any,
    data: bytes,
    virtual_address: int,
) -> list[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise DeathEventCreditBoundaryError("file-backed executable .text section missing")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    needle = struct.pack("<I", virtual_address)
    result: list[int] = []
    cursor = 0
    while True:
        offset = body.find(needle, cursor)
        if offset < 0:
            return result
        result.append(section.virtual_address + offset)
        cursor = offset + 1


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise DeathEventCreditBoundaryError("file-backed executable .text section missing")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    result: set[int] = set()
    for offset in range(len(body) - 4):
        if body[offset] != 0xE8:
            continue
        source_rva = section.virtual_address + offset
        target = source_rva + 5 + struct.unpack_from("<i", body, offset + 1)[0]
        if target == target_rva:
            result.add(source_rva)
    return result


def _dependency_record() -> dict[str, str]:
    return dict(DEPENDENCY_SPEC)


def _source_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in SOURCE_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "boundary_basis": f"Ghidra 12.1.3 {basis}",
        }
        for region_id, start, end, digest, basis in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, str]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{source:08x}",
            "instruction_hex": encoded,
            "target_region": target_region,
            "target_rva": f"0x{target:08x}",
        }
        for edge_id, source_region, source, encoded, target_region, target in DIRECT_EDGE_SPECS
    ]


def _absolute_reference_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "string_rva": f"0x{rva:08x}",
            "string_hex": raw.hex(),
            "absolute_operand_rvas": [f"0x{item:08x}" for item in references],
        }
        for anchor_id, rva, raw, references in ABSOLUTE_REFERENCE_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "rva": f"0x{rva:08x}",
            "size": len(raw),
            "hex": raw.hex(),
            "meaning": meaning,
        }
        for anchor_id, rva, raw, meaning in DATA_ANCHOR_SPECS
    ]


def _onkill_records() -> list[dict[str, Any]]:
    return [
        {"path": path, "line": line, "source": source}
        for path, line, source in ONKILL_OCCURRENCES
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "shipped_onkill_is_localized_metadata",
            "classification": "fact",
            "claim": (
                "All seven OnKill occurrences in the exact accepted Lua tree are one "
                "empty Skill default plus six localization-key strings. Each key exists "
                "in Weapons_ae.csv, Skill_OnKill labels the UI as 'On Kill:', no exact "
                "Lua function defines any key, and all six mechanics are implemented "
                "inside their weapon GetSkillEffect definitions."
            ),
        },
        {
            "id": "skill_effect_owner_survives_queue",
            "classification": "fact",
            "claim": (
                "Luabind maps SkillEffect.iOwner to +0x5c. Board:AddEffect copies the "
                "0x7c-byte record into its queue; both copy paths preserve +0x5c."
            ),
        },
        {
            "id": "queued_owner_becomes_death_context",
            "classification": "fact",
            "claim": (
                "The SkillEffect dispatcher passes the by-value record's +0x5c field "
                "into a context whose first field is owner, copies it, and conditionally "
                "installs it at current-context address 0x8bd254 before effect work."
            ),
        },
        {
            "id": "environment_effect_owner_is_minus_ten",
            "classification": "fact",
            "claim": (
                "Both Env_Attack ApplyEffect branches set effect.iOwner=ENV_EFFECT before "
                "Board:AddEffect, and exact native registration publishes ENV_EFFECT=-10."
            ),
        },
        {
            "id": "ordinary_enemy_death_records_event_two",
            "classification": "fact",
            "claim": (
                "For non-Mech Pawn team 6 (TEAM_ENEMY), the death processor reads Minor "
                "at +0x10d0 and records event 2 with INT_MAX payload for non-Minor or "
                "event 12 for Minor. EVENT_ENEMY_KILLED is exactly event 2."
            ),
        },
        {
            "id": "mission_kill_event_delivery",
            "classification": "inference",
            "claim": (
                "The generic recorder increments pending event counts, the sole direct "
                "publisher copies pending to the readable array and resets pending, and "
                "registered Game:GetEventCount reads that array. Mission:BaseUpdate adds "
                "EVENT_ENEMY_KILLED to KilledVek for Kill Five and Pacifist objectives."
            ),
        },
        {
            "id": "owner_specific_credit_split",
            "classification": "fact",
            "claim": (
                "For non-Minor, XP-eligible enemy deaths, owners 0..2 receive xp_<owner> "
                "and kill_<owner>; all other owners receive env_xp. Every reviewed enemy "
                "death also writes any_kill_<owner>."
            ),
        },
        {
            "id": "environment_bypasses_mech_xp_and_kill_buckets",
            "classification": "inference",
            "claim": (
                "ENV_EFFECT owner -10 takes the outside-0..2 env_xp branch and names its "
                "unconditional bucket any_kill_-10. It therefore does not create the "
                "xp_<0..2>, kill_<0..2>, or any_kill_<0..2> entries consumed by those "
                "Mech owners, while the independent non-Minor mission event still fires."
            ),
        },
        {
            "id": "pawn_credit_consumer_and_named_fields",
            "classification": "fact",
            "claim": (
                "The per-Pawn consumer reads and clears kill_<PawnID>, any_kill_<PawnID>, "
                "and xp_<PawnID>; applies Extra_XP as two per kill; routes XP into "
                "iKillCount +0xa60; and adds any-kill count to Mech iKills +0x98c."
            ),
        },
        {
            "id": "mission_damage_is_separate",
            "classification": "fact",
            "claim": (
                "iMissionDamage is bound at Pawn+0x1170 and updated by a separate health-"
                "delta accumulator. It is not the death-source owner or kill-credit path."
            ),
        },
        {
            "id": "rust_environment_kill_model_already_conforms",
            "classification": "inference",
            "claim": (
                "Rust apply_env_danger already records lethal enemy deaths through the "
                "shared mission-kill predicate, whose ordinary rule excludes Minor enemy "
                "units. No reviewed native rule contradicts the current simulator, so no "
                "semantic change or simulator-version bump follows."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "native_only_onkill_offset_consumers",
            "question": "Does an unreviewed native-only path consume the Skill OnKill field by offset for any purpose beyond the mapped property/UI paths?",
            "next_evidence": "Exhaustively trace native field-offset consumers only if a concrete solver mismatch depends on them; no shipped Lua callback remains to find.",
        },
        {
            "id": "exact_event_frame_visibility",
            "question": "Does a death raised in a particular Board/effect pass become readable in the same outer update or the next one?",
            "next_evidence": "Capture or fully map Board/effect dispatch relative to the sole event publisher and Mission:BaseUpdate.",
        },
        {
            "id": "achievement_counter_tail",
            "question": "Which achievement-specific event and persistent profile counters consume each death category?",
            "next_evidence": "Trace only the named achievement path needed by a future conformance discrepancy.",
        },
        {
            "id": "specialized_enemy_death_classes",
            "question": "Which specialized subclasses or nonstandard teams alter the ordinary TEAM_ENEMY/Minor event and credit path?",
            "next_evidence": "Map concrete subclass/vtable cases instead of generalizing this ordinary Pawn path.",
        },
        {
            "id": "environment_any_kill_bucket_consumers",
            "question": "Can any non-Pawn subsystem consume the generated any_kill_-10 bucket?",
            "next_evidence": "Trace string-map readers for that exact key only if it becomes solver-relevant.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows depots implement the same owner, event, and credit path?",
            "next_evidence": "Repeat the build-keyed inventory and boundary map on another exact executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
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
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
        },
        "base_scripts_inventory": dict(BASE_SCRIPTS_INVENTORY_SPEC),
        "dependency": _dependency_record(),
        "sources": _source_records(),
        "lua_onkill_inventory": {
            "accepted_tree_lua_file_count": 153,
            "occurrence_count": len(ONKILL_OCCURRENCES),
            "occurrences": _onkill_records(),
            "localization_keys": list(ONKILL_KEYS),
            "matching_lua_function_definitions": [],
            "shipped_lua_callback_name_proven": False,
            "localized_metadata_proven": True,
        },
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "absolute_reference_inventory": _absolute_reference_records(),
        "data_anchors": _data_anchor_records(),
        "contracts": {
            "owner_pipeline": {
                "skill_effect_iowner_offset": "+0x5c",
                "skill_effect_size_bytes": 0x7C,
                "board_effect_vector_offset": "+0x2c50",
                "queued_copy_preserves_iowner": True,
                "dispatcher_by_value_iowner_stack_offset": "+0x64",
                "context_owner_field_offset": "+0x00",
                "current_owner_address": "0x008bd254",
                "environment_owner_name": "ENV_EFFECT",
                "environment_owner_value": -10,
                "environment_owner_pipeline_proven": True,
            },
            "enemy_classification": {
                "is_mech_offset": "+0x09e4",
                "team_offset": "+0x00b0",
                "team_enemy_value": 6,
                "minor_offset": "+0x10d0",
                "ordinary_path_requires_is_mech_false": True,
                "ordinary_path_requires_team_enemy": True,
            },
            "mission_event": {
                "event_enemy_killed_value": 2,
                "nonminor_enemy_event": 2,
                "minor_enemy_event": 12,
                "event_payload": "0x7fffffff",
                "recorder_increments_pending": True,
                "publisher_copies_pending_to_readable": True,
                "publisher_resets_pending": True,
                "get_event_count_reads_readable": True,
                "mission_base_update_consumes_event_enemy_killed": True,
                "exact_same_or_next_update_visibility_proven": False,
            },
            "credit": {
                "xp_and_kill_require_minor_false": True,
                "xp_and_kill_require_victim_eligibility_byte_nonzero": "+0x1175",
                "mech_owner_inclusive_range": [0, 2],
                "mech_owner_xp_bucket": "xp_<owner>",
                "mech_owner_kill_bucket": "kill_<owner>",
                "nonmech_owner_xp_bucket": "env_xp",
                "all_reviewed_enemy_deaths_bucket": "any_kill_<owner>",
                "environment_generates_mech_xp_or_kill_bucket": False,
                "pawn_consumer_id_offset": "+0x09a4",
                "pawn_consumer_clears_buckets": True,
                "extra_xp_bonus_per_kill": 2,
                "i_kills_offset": "+0x098c",
                "i_kill_count_offset": "+0x0a60",
                "i_mission_damage_offset": "+0x1170",
                "i_mission_damage_is_health_delta_not_death_credit": True,
            },
            "onkill": {
                "shipped_lua_occurrence_count": 7,
                "shipped_nonempty_value_count": 6,
                "all_nonempty_values_are_localization_keys": True,
                "matching_lua_function_definition_count": 0,
                "mechanics_implemented_in_get_skill_effect": True,
                "shipped_lua_callback_field_proven": False,
                "native_only_offset_consumers_exhausted": False,
            },
        },
        "findings": findings,
        "refines": {
            "artifact": DEPENDENCY_SPEC["path"],
            "unresolved_ids": [
                "on_kill_callback_dispatch",
                "kill_credit_and_owner_attribution",
            ],
            "qualification": (
                "The exact shipped OnKill values are now proven localization metadata, "
                "and the ordinary environment-owner, TEAM_ENEMY/Minor mission event, "
                "and per-Pawn credit split are mapped. Native-only OnKill offset "
                "consumers, exact frame timing, specialized classes, and achievements "
                "remain outside the closed portion."
            ),
        },
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "conforming_paths": [
                "rust_solver/src/enemy.rs::apply_env_danger",
                "rust_solver/src/board.rs::unit_counts_for_mission_kill",
                "rust_solver/src/board.rs::ActionResult::record_enemy_kill",
            ],
            "reason": (
                "The simulator already counts lethal environment deaths for ordinary "
                "non-Minor enemies and does not model environment kills as Mech XP/kill "
                "credit. The new exact-build evidence contradicts no transition rule."
            ),
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "The source verifier requires the exact accepted scripts tree except for one of two hash-pinned project bridge overlays.",
            "The ordinary event path is bounded to non-Mech TEAM_ENEMY Pawn death and its Minor split; specialized classes are not generalized.",
            "The event writer/publisher/reader chain is proven structurally, but exact visibility in a particular Board/effect frame is not.",
            "The absence of shipped Lua OnKill function definitions does not exhaust native-only consumers that might address the Skill field by offset.",
        ],
        "summary": {
            "source_count": len(SOURCE_SPECS),
            "dependency_count": 1,
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "absolute_reference_anchor_count": len(ABSOLUTE_REFERENCE_SPECS),
            "absolute_reference_count": sum(
                len(references)
                for _anchor_id, _rva, _raw, references in ABSOLUTE_REFERENCE_SPECS
            ),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "environment_owner_pipeline_proven": True,
            "mission_enemy_killed_event_proven": True,
            "environment_mech_credit_bypass_proven": True,
            "shipped_lua_onkill_callback_proven": False,
            "exact_event_frame_visibility_proven": False,
            "simulator_change_required": False,
        },
    }


def _verify_dependency(executable: Path, content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    path = repository_root / DEPENDENCY_SPEC["path"]
    if path.is_symlink() or not path.is_file():
        raise DeathEventCreditBoundaryError("zero-HP cleanup dependency missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_SPEC["file_sha256"]:
        raise DeathEventCreditBoundaryError("zero-HP cleanup dependency file differs")
    value = _read_json(path)
    if _canonical_sha256(value) != DEPENDENCY_SPEC["canonical_sha256"]:
        raise DeathEventCreditBoundaryError("zero-HP cleanup dependency fields differ")
    try:
        validate_zero_hp_cleanup_boundary_map(executable, content_root, value)
    except ZeroHpCleanupBoundaryError as exc:
        raise DeathEventCreditBoundaryError(
            f"zero-HP cleanup dependency differs: {exc}"
        ) from exc


def _verify_scripts_identity(content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    inventory_path = repository_root / BASE_SCRIPTS_INVENTORY_SPEC["path"]
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise DeathEventCreditBoundaryError(
            "base scripts inventory is not a regular non-symlink file"
        )
    inventory_bytes = inventory_path.read_bytes()
    if (
        len(inventory_bytes) != BASE_SCRIPTS_INVENTORY_SPEC["size"]
        or hashlib.sha256(inventory_bytes).hexdigest()
        != BASE_SCRIPTS_INVENTORY_SPEC["sha256"]
    ):
        raise DeathEventCreditBoundaryError("base scripts inventory differs")
    try:
        inventory = json.loads(inventory_bytes)
        baseline = inventory["content"]["scripts"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise DeathEventCreditBoundaryError(
            "base scripts inventory shape differs"
        ) from exc
    if (
        baseline.get("file_count")
        != BASE_SCRIPTS_INVENTORY_SPEC["scripts_file_count"]
        or baseline.get("byte_count")
        != BASE_SCRIPTS_INVENTORY_SPEC["scripts_byte_count"]
        or baseline.get("revision_sha256")
        != BASE_SCRIPTS_INVENTORY_SPEC["base_scripts_revision_sha256"]
        or not isinstance(baseline.get("files"), list)
    ):
        raise DeathEventCreditBoundaryError("base scripts inventory identity differs")

    actual = build_manifest(content_root, "scripts")
    if actual["file_count"] != BASE_SCRIPTS_INVENTORY_SPEC["scripts_file_count"]:
        raise DeathEventCreditBoundaryError("scripts file count differs")
    baseline_files = {entry["path"]: entry for entry in baseline["files"]}
    actual_files = {entry["path"]: entry for entry in actual["files"]}
    if baseline_files.keys() != actual_files.keys():
        raise DeathEventCreditBoundaryError("scripts paths differ")

    overlay_path = BASE_SCRIPTS_INVENTORY_SPEC["overlay_path"]
    for path, expected in baseline_files.items():
        if path != overlay_path and actual_files[path] != expected:
            raise DeathEventCreditBoundaryError(
                f"analysis-relevant scripts entry differs: {path}"
            )
    actual_overlay = actual_files[overlay_path]
    accepted_overlays = {
        (item["size"], item["sha256"])
        for item in (
            *BASE_SCRIPTS_INVENTORY_SPEC["accepted_overlay_files"],
            *POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS,
        )
    }
    if (actual_overlay["size"], actual_overlay["sha256"]) not in accepted_overlays:
        raise DeathEventCreditBoundaryError(
            "project bridge overlay is not an accepted hash-pinned version"
        )


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise DeathEventCreditBoundaryError("content root is not a directory")
    _verify_scripts_identity(root)

    source_bytes: dict[str, bytes] = {}
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise DeathEventCreditBoundaryError(
                f"source is missing or escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise DeathEventCreditBoundaryError(
                f"source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise DeathEventCreditBoundaryError(f"source differs: {spec['path']}")
        source_bytes[spec["path"]] = raw

    environments = source_bytes["scripts/environments.lua"]
    start = environments.index(b"function Env_Attack:ApplyEffect()")
    end = environments.index(b"function Env_Attack:MarkBoard", start)
    apply_body = environments[start:end]
    if (
        apply_body.count(b"effect.iOwner = ENV_EFFECT") != 2
        or apply_body.count(b"Board:AddEffect(effect)") != 2
    ):
        raise DeathEventCreditBoundaryError("Env_Attack owner/AddEffect contract differs")
    cursor = 0
    for _ in range(2):
        owner = apply_body.index(b"effect.iOwner = ENV_EFFECT", cursor)
        enqueue = apply_body.index(b"Board:AddEffect(effect)", owner)
        if enqueue <= owner:
            raise DeathEventCreditBoundaryError("Env_Attack owner lexical order differs")
        cursor = enqueue + 1

    scripts_root = root / "scripts"
    lua_files = sorted(
        (
            path
            for path in scripts_root.rglob("*.lua")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if len(lua_files) != 153:
        raise DeathEventCreditBoundaryError("accepted-tree Lua file count differs")
    occurrences: list[tuple[str, int, str]] = []
    lua_blobs: list[bytes] = []
    for path in lua_files:
        raw = path.read_bytes()
        lua_blobs.append(raw)
        for line_number, line in enumerate(raw.splitlines(), 1):
            if b"OnKill" in line:
                occurrences.append(
                    (
                        path.relative_to(root).as_posix(),
                        line_number,
                        line.decode("utf-8").strip(),
                    )
                )
    if occurrences != list(ONKILL_OCCURRENCES):
        raise DeathEventCreditBoundaryError("accepted-tree Lua OnKill inventory differs")

    for key in ONKILL_KEYS:
        encoded = key.encode("ascii")
        patterns = (
            b"function " + encoded + b"(",
            b"function " + encoded + b":",
            b"function " + encoded + b".",
            encoded + b" = function",
            encoded + b"=function",
        )
        if any(pattern in raw for raw in lua_blobs for pattern in patterns):
            raise DeathEventCreditBoundaryError(
                f"accepted-tree Lua unexpectedly defines OnKill key {key}"
            )

    weapons = source_bytes["scripts/advanced/ae_weapons.lua"]
    get_effect_names = (
        b"function Prime_KO_Crack:GetSkillEffect",
        b"function Brute_KO_Combo:GetSkillEffect",
        b"function Ranged_Arachnoid:GetSkillEffect",
        b"function Ranged_KO_Combo:GetSkillEffect",
        b"function Science_KO_Crack:GetSkillEffect",
        b"function Support_KO_GridCharger:GetSkillEffect",
    )
    if any(name not in weapons for name in get_effect_names):
        raise DeathEventCreditBoundaryError("OnKill weapon GetSkillEffect set differs")

    global_localization = source_bytes["scripts/localization/Global_ae.csv"]
    if not any(
        line.startswith(b"Skill_OnKill,On Kill:")
        for line in global_localization.splitlines()
    ):
        raise DeathEventCreditBoundaryError("Skill_OnKill localization differs")
    weapon_localization = source_bytes["scripts/localization/Weapons_ae.csv"]
    for key in ONKILL_KEYS:
        prefix = key.encode("ascii") + b","
        if not any(line.startswith(prefix) for line in weapon_localization.splitlines()):
            raise DeathEventCreditBoundaryError(
                f"OnKill localization key missing: {key}"
            )

    missions = source_bytes["scripts/missions/missions.lua"]
    required_mission = (
        b"function Mission:BaseUpdate()",
        b"self.KilledVek = self.KilledVek + Game:GetEventCount(EVENT_ENEMY_KILLED)",
    )
    if any(token not in missions for token in required_mission):
        raise DeathEventCreditBoundaryError("Mission KilledVek event consumer differs")


def build_death_event_credit_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build enemy-death event and credit boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise DeathEventCreditBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise DeathEventCreditBoundaryError("executable identity differs")

    _verify_dependency(executable, content_root)
    _verify_sources(content_root)

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        try:
            body = _region_bytes(image, data, start, end - start, ".text", region_id)
        except Exception as exc:
            raise DeathEventCreditBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise DeathEventCreditBoundaryError(f"region {region_id} bytes differ")
        region_ranges[region_id] = (start, end)

    decode_ranges: dict[str, tuple[int, int]] = {}
    for window_id, region_id, start, encoded_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise DeathEventCreditBoundaryError(f"control window {window_id} differs")
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start < start + len(expected) <= region_end:
            raise DeathEventCreditBoundaryError(f"control window {window_id} escapes region")
        decode_ranges[f"window_{window_id}"] = (start, start + len(expected))

    for edge_id, source_region, source, encoded_hex, target_region, target in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, source, len(expected)) != expected:
            raise DeathEventCreditBoundaryError(f"direct edge {edge_id} bytes differ")
        source_start, source_end = region_ranges[source_region]
        if not source_start <= source < source + len(expected) <= source_end:
            raise DeathEventCreditBoundaryError(f"direct edge {edge_id} escapes source region")
        target_start, target_end = region_ranges[target_region]
        if not target_start <= target < target_end:
            raise DeathEventCreditBoundaryError(f"direct edge {edge_id} escapes target region")
        if _direct_target(source, expected) != target:
            raise DeathEventCreditBoundaryError(f"direct edge {edge_id} target differs")
        decode_ranges[f"edge_{edge_id}"] = (source, source + len(expected))

    try:
        _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise DeathEventCreditBoundaryError(
            f"instruction alignment differs: {exc}"
        ) from exc

    for anchor_id, rva, raw, references in ABSOLUTE_REFERENCE_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise DeathEventCreditBoundaryError(f"data anchor {anchor_id} differs")
        actual = _text_absolute_operand_rvas(image, data, image.image_base + rva)
        if actual != list(references):
            raise DeathEventCreditBoundaryError(
                f"absolute reference inventory {anchor_id} differs"
            )

    for anchor_id, rva, raw, _meaning in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise DeathEventCreditBoundaryError(f"data anchor {anchor_id} differs")

    if _raw_rel32_call_sites(image, data, 0x0009BF00) != {0x000E55AC}:
        raise DeathEventCreditBoundaryError("event publisher direct-call inventory differs")

    return _expected_shape()


def validate_death_event_credit_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise DeathEventCreditBoundaryError("death event/credit boundary fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "environment_owner_pipeline_proven": True,
        "mission_enemy_killed_event_proven": True,
        "environment_mech_credit_bypass_proven": True,
        "shipped_lua_onkill_callback_proven": False,
        "exact_event_frame_visibility_proven": False,
        "simulator_change_required": False,
    }


def validate_death_event_credit_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, source, byte, or prose drift."""
    expected = build_death_event_credit_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise DeathEventCreditBoundaryError(
            "death event/credit boundary differs from exact-build analysis"
        )
    result = validate_death_event_credit_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_death_event_credit_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
