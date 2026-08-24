"""Reproduce the exact-build native ``Pawn:IsCorpse`` classification map.

The earlier path and zero-HP maps proved what consumes ``IsCorpse``.  This
continuation closes the predicate's static inputs, ties mutation id 12 to the
registered ``LEADER_NECRO`` constant, and inventories every shipped Lua pawn
whose effective definition has ``Corpse=true``.  It deliberately does not
claim the frame at which a killed pawn enters or leaves native lifecycle
states 2/3/4.
"""

from __future__ import annotations

import hashlib
import json
import re
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
from src.observatory.specialized_enemy_death_boundary import (
    SpecializedEnemyDeathBoundaryError,
    validate_specialized_enemy_death_boundary_map,
)
from src.observatory.zero_hp_cleanup_boundary import (
    ZeroHpCleanupBoundaryError,
    validate_zero_hp_cleanup_boundary_map,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_corpse_classification_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class CorpseClassificationBoundaryError(RuntimeError):
    """Raised when the exact corpse-classification map cannot reproduce."""


DEPENDENCY_SPECS = (
    {
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
            "Pins the later dead-noncorpse Board erase and the complete "
            "IsCorpse consumer boundary."
        ),
    },
    {
        "id": "specialized_enemy_death_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "specialized_enemy_death_boundary.json"
        ),
        "file_sha256": (
            "704589f76307dc28b43e7db4ad18713750fdeb15b1a7d8851f48f9827edb9c21"
        ),
        "canonical_sha256": (
            "14c7459e04ba7781a6a3cf4889ed5b8847da42c1c41ca20d9f0bbc8eecb23731"
        ),
        "role": (
            "Pins the common Pawn constructor plus IsMech, team, Minor, "
            "and shipped-source classification context."
        ),
    },
)


SOURCE_SPECS = (
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
        "symbols": ["Pawn", "Corpse = false", "Minor = false"],
    },
    {
        "path": "scripts/pawns.lua",
        "size": 27_397,
        "sha256": "e999b8d98526c1e36f4746dd65b9d9e7ee3ca0b22029ed391d5b71fda49dc239",
        "symbols": ["Jelly_Health1", "Leader = LEADER_HEALTH"],
    },
    {
        "path": "scripts/advanced/ae_pawns.lua",
        "size": 18_501,
        "sha256": "e87efe90c0342f26969c14159e6b6c93766aeedcbc3319fb0f418048d129e9f4",
        "symbols": ["Jelly_Necro1", "Leader = LEADER_NECRO"],
    },
    {
        "path": "scripts/weapons_passive.lua",
        "size": 8_429,
        "sha256": "ba3555413140f1eb33c9cc94e0645d980950411524d96b96716f82dbb2512a47",
        "symbols": ["Passive_Psions", "Psion_Leech"],
    },
    {
        "path": "scripts/spawner_backend.lua",
        "size": 8_827,
        "sha256": "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301",
        "symbols": ["EnemyLists", "WeakPawns", "Spawner"],
    },
    {
        "path": "scripts/advanced/missions/grass/mission_armored_train.lua",
        "size": 2_126,
        "sha256": "4c1438bd02ffdcc0d4f975f432168d1d45017126f819995c86873978b67a288a",
        "symbols": ["Train_Armored_Damaged", "Train_Armored"],
    },
    {
        "path": "scripts/missions/acid/mission_laser.lua",
        "size": 2_111,
        "sha256": "e9195a160fd8a7b971555d767033eb7baea116668462cc0f50d22de01d2b13db",
        "symbols": ["Pawn_Laser_U", "Pawn_Laser_R", "Mission_Laser"],
    },
    {
        "path": "scripts/missions/acid/mission_piston.lua",
        "size": 2_420,
        "sha256": "1f426bad3b4149f0088831680264f716a3f9cc6acebf828306946c55990d51ad",
        "symbols": ["Pawn_Piston_U", "Pawn_Piston_R", "Mission_Piston"],
    },
    {
        "path": "scripts/missions/grass/mission_artillery.lua",
        "size": 2_777,
        "sha256": "fe78f546038a8a83a3db277ddd47a32c9be117db14f04ff51145dd880f8418f9",
        "symbols": ["ArchiveArtillery"],
    },
    {
        "path": "scripts/missions/grass/mission_dam.lua",
        "size": 1_922,
        "sha256": "bc677d4ea6f0dfc80b43b6711d1f20e3ea2d75fb87c869d59956c745830c7f08",
        "symbols": ["Dam_Pawn"],
    },
    {
        "path": "scripts/missions/grass/mission_satellites.lua",
        "size": 5_949,
        "sha256": "ad88320a25a411db2fb7de188b658e2705b2e6552a737f387d2ab9c982285301",
        "symbols": ["SatelliteRocket"],
    },
    {
        "path": "scripts/missions/mission_train.lua",
        "size": 4_193,
        "sha256": "a9ec7ce1ea386e3b82ecd992b6cacd8ca17990cb37f7109e8060140cbb3a5e0b",
        "symbols": ["Train_Pawn", "Train_Damaged"],
    },
    {
        "path": "scripts/missions/sand/mission_filler.lua",
        "size": 2_406,
        "sha256": "38e00c007476a42c05bbe4968f9b081de4bbdfb3761667b0e3e72c28c39079f9",
        "symbols": ["Filler_Pawn"],
    },
)


CORPSE_TRUE_OCCURRENCES = (
    (
        "scripts/advanced/missions/grass/mission_armored_train.lua",
        21,
        "Train_Armored_Damaged",
    ),
    (
        "scripts/advanced/missions/grass/mission_armored_train.lua",
        46,
        "Train_Armored",
    ),
    ("scripts/missions/acid/mission_laser.lua", 47, "Pawn_Laser_U"),
    ("scripts/missions/acid/mission_piston.lua", 53, "Pawn_Piston_U"),
    ("scripts/missions/grass/mission_artillery.lua", 75, "ArchiveArtillery"),
    ("scripts/missions/grass/mission_dam.lua", 75, "Dam_Pawn"),
    ("scripts/missions/grass/mission_satellites.lua", 143, "SatelliteRocket"),
    ("scripts/missions/mission_train.lua", 109, "Train_Pawn"),
    ("scripts/missions/mission_train.lua", 123, "Train_Damaged"),
    ("scripts/missions/sand/mission_filler.lua", 43, "Filler_Pawn"),
)

INHERITED_CORPSE_TYPES = (
    ("Pawn_Laser_R", "Pawn_Laser_U"),
    ("Pawn_Laser_L", "Pawn_Laser_U"),
    ("Pawn_Laser_D", "Pawn_Laser_U"),
    ("Pawn_Piston_R", "Pawn_Piston_U"),
    ("Pawn_Piston_L", "Pawn_Piston_U"),
    ("Pawn_Piston_D", "Pawn_Piston_U"),
)

EFFECTIVE_CORPSE_TYPES = (
    "ArchiveArtillery",
    "Dam_Pawn",
    "Filler_Pawn",
    "Pawn_Laser_D",
    "Pawn_Laser_L",
    "Pawn_Laser_R",
    "Pawn_Laser_U",
    "Pawn_Piston_D",
    "Pawn_Piston_L",
    "Pawn_Piston_R",
    "Pawn_Piston_U",
    "SatelliteRocket",
    "Train_Armored",
    "Train_Armored_Damaged",
    "Train_Damaged",
    "Train_Pawn",
)


REGION_SPECS = (
    {
        "id": "pawn_definition_load",
        "start": 0x0022C0F0,
        "end": 0x0022CBB7,
        "sha256": "9c705957ab7a8afa137bb56e4d075b40a29ca8da45222fd318f2c821ac138148",
        "basis": "Ghidra 12.1.3 complete Pawn definition-loading function.",
    },
    {
        "id": "pawn_is_corpse",
        "start": 0x0022CDE0,
        "end": 0x0022CE47,
        "sha256": "806702601f6a75193f6479e0357150d5264c10b7661a434bac7eeb1a807606c7",
        "basis": "Complete common Pawn IsCorpse member through RET.",
    },
    {
        "id": "pawn_set_mutation",
        "start": 0x0023AC60,
        "end": 0x0023AE46,
        "sha256": "78573b62ffc8222b2d76b08fc27f17601cba8798433cfe1f7b50a777a60dd579",
        "basis": "Ghidra 12.1.3 complete SetMutation implementation.",
    },
    {
        "id": "mutation_eligibility",
        "start": 0x0023D6A0,
        "end": 0x0023D84E,
        "sha256": "9bc34a54ae7162e7dcdb636d199b1a3b7aaeae86631d15543ed4c70152e113b0",
        "basis": "Complete common mutation-eligibility predicate through RET 0x04.",
    },
    {
        "id": "set_mutation_binding",
        "start": 0x0027C6F5,
        "end": 0x0027C71A,
        "sha256": "efbc6cd42ab38d9707fd889242656822f61075e43dba9e7f71220989720446a6",
        "basis": "Complete Luabind SetMutation registration block.",
    },
    {
        "id": "leader_necro_registration",
        "start": 0x00280943,
        "end": 0x00280985,
        "sha256": "0199a8bd15b7e9486a0b769ac3a2b1b59688a6351d4ecf127da5cc54a3afe52c",
        "basis": "Complete LEADER_NECRO name/value registration block.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "load_corpse_property",
        "region": "pawn_definition_load",
        "start": 0x0022C24D,
        "hex": "6a06681c608300c60000e874bdddff8bcfe84dd1e1ff83ec188883800f0000",
        "meaning": "Load Lua Corpse and store its boolean at Pawn+0xf80.",
    },
    {
        "id": "load_leader_property",
        "region": "pawn_definition_load",
        "start": 0x0022C328,
        "hex": "6a066824608300c60000e899bcddff8bcfe852cfe1ff83ec18898318130000",
        "meaning": "Load Lua Leader and store its integer at Pawn+0x1318.",
    },
    {
        "id": "load_minor_property",
        "region": "pawn_definition_load",
        "start": 0x0022C4A2,
        "hex": "6a056858608300c60000e81fbbddff8bcfe8f8cee1ff83ec188883d0100000",
        "meaning": "Load Lua Minor and store its boolean at Pawn+0x10d0.",
    },
    {
        "id": "load_default_faction_property",
        "region": "pawn_definition_load",
        "start": 0x0022C7E0,
        "hex": "6a0e688c608300c60000e8e1b7ddff8bcfe89acae1ff83ec188983bc100000",
        "meaning": "Load Lua DefaultFaction and store its integer at Pawn+0x10bc.",
    },
    {
        "id": "complete_is_corpse_predicate",
        "region": "pawn_is_corpse",
        "start": 0x0022CDE0,
        "hex": (
            "5180b9e409000000750980b9800f00000074158b81e009000083f803740a"
            "83f802740583f804753b83b9e81000000c7423a154568d008b1558568d00"
            "3bc2741f83380c740b83c0043bc275f432c059c33bc2740b6a0ce8650801"
            "0084c0750432c059c3b00159c3"
        ),
        "meaning": (
            "Common IsCorpse source/Mech and lifecycle-state gate, mutation-12 "
            "availability lookup, eligibility call, and both returns."
        ),
    },
    {
        "id": "set_mutation_field_write",
        "region": "pawn_set_mutation",
        "start": 0x0023AC82,
        "hex": (
            "39b7e81000000f84a40100008b078b4010ffd084c0741e8b87e810000083f8"
            "06741383f807740e83f80a740983f8090f857b0100008b078bcf8b4010ffd0"
            "8844241385f675220f1005b85d890083ec108bcc83ec180f1101548bcfe87e"
            "47ffff568bcfe86641ffff89b7e8100000"
        ),
        "meaning": "SetMutation compares and then writes the selected integer at Pawn+0x10e8.",
    },
    {
        "id": "mutation_12_team_and_passive_gate",
        "region": "mutation_eligibility",
        "start": 0x0023D7E2,
        "hex": (
            "83f806750983bebc10000000742e80bee409000000750a83f8040f94c084c0"
            "743583ec188bcc68b46b8300e8fea5dcffe8e90e020083c41884c0741a"
        ),
        "meaning": (
            "For non-mode-8 mutations, ordinary TEAM_ENEMY/default-faction "
            "pawns pass directly; other recipients require Mech/team-4 status "
            "and the Psion_Leech passive."
        ),
    },
    {
        "id": "mutation_12_leader_and_minor_exclusions",
        "region": "mutation_eligibility",
        "start": 0x0023D81E,
        "hex": (
            "83be1813000000740839bee8100000740980bed01000000074918b4c242c33c0"
            "5f5e5b33cce8829c11008be55dc20400"
        ),
        "meaning": (
            "A nonzero Leader with current mutation equal to the requested id, "
            "or any Minor pawn, fails eligibility."
        ),
    },
    {
        "id": "set_mutation_luabind_registration",
        "region": "set_mutation_binding",
        "start": 0x0027C6F5,
        "hex": "c745e860ac6300c745ec00000000ff75f0ff75f0518d4de85168049283008bc8e806050100",
        "meaning": "Bind the SetMutation name to native RVA 0x0023ac60.",
    },
    {
        "id": "leader_necro_value_registration",
        "region": "leader_necro_registration",
        "start": 0x00280943,
        "hex": (
            "68e49a83008d8d14f5ffff518bc8e8fafedcff68505681008bc8e82effdcff"
            "8d8d14f5ffffe873ecdcff8d8d88fcffffe848badeff8bd38d8d80fcffffe8"
            "5bbadeff"
        ),
        "meaning": "Register LEADER_NECRO using the data object whose first integer is 12.",
    },
)


DATA_ANCHOR_SPECS = (
    ("corpse_name", 0x0043601C, b"Corpse\0", (0x0022C250,)),
    ("leader_name", 0x00436024, b"Leader\0", (0x0022C32B,)),
    ("minor_name", 0x00436058, b"Minor\0", (0x0022C4A5,)),
    (
        "default_faction_name",
        0x0043608C,
        b"DefaultFaction\0",
        (0x0022C7E3,),
    ),
    (
        "psion_leech_name",
        0x00436BB4,
        b"Psion_Leech\0",
        (0x0023D7B4, 0x0023D809),
    ),
    ("set_mutation_name", 0x00439204, b"SetMutation\0", (0x0027C70F,)),
    ("leader_necro_name", 0x00439AE4, b"LEADER_NECRO\0", (0x00280944,)),
    ("leader_necro_value", 0x00415650, b"\x0c\x00\x00\x00", (0x00280957,)),
)


DIRECT_EDGE_SPECS = (
    {
        "id": "is_corpse_calls_mutation_eligibility",
        "source_region": "pawn_is_corpse",
        "from": 0x0022CE36,
        "hex": "e865080100",
        "target_region": "mutation_eligibility",
        "target": 0x0023D6A0,
    },
)


CALL_INVENTORY_SPECS = (
    {
        "id": "pawn_is_corpse_direct_calls",
        "target": 0x0022CDE0,
        "call_sites": (
            0x0016B2AE,
            0x0016C79A,
            0x0016C86D,
            0x00173E7E,
            0x0019D668,
            0x0019D74A,
            0x0019EFCB,
            0x0019FFA4,
            0x001A2E73,
            0x001ADE48,
            0x0022BEF7,
            0x0022CDA5,
            0x0022EC58,
            0x0022F86D,
            0x002303E8,
            0x00230FFD,
            0x0023281B,
            0x002328F3,
            0x00232EF9,
            0x00234731,
            0x00234B33,
            0x00234EA9,
            0x002367CF,
            0x00239CAF,
            0x0023BCAF,
            0x00240670,
            0x00240D2F,
        ),
    },
    {
        "id": "mutation_eligibility_direct_calls",
        "target": 0x0023D6A0,
        "call_sites": (
            0x0016B2E9,
            0x0016C003,
            0x0022CE36,
            0x0022E58D,
            0x0022E84C,
            0x0022F49F,
            0x0023BD85,
            0x0023C537,
            0x0023F9F4,
        ),
    },
    {
        "id": "pawn_set_mutation_direct_calls",
        "target": 0x0023AC60,
        "call_sites": (0x0016B307, 0x0016C018),
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


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise CorpseClassificationBoundaryError(
            f"RVA 0x{rva:08x} is not file-backed"
        )
    return data[offset : offset + size]


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    result: set[int] = set()
    for section in image.sections:
        if not section.executable:
            continue
        body = data[section.raw_offset : section.raw_offset + section.raw_size]
        for offset in range(0, max(0, len(body) - 4)):
            if body[offset] != 0xE8:
                continue
            source_rva = section.virtual_address + offset
            target = source_rva + 5 + struct.unpack_from("<i", body, offset + 1)[0]
            if target == target_rva:
                result.add(source_rva)
    return result


def _absolute_va_sites(image: Any, data: bytes, va: int) -> set[int]:
    needle = struct.pack("<I", va)
    result: set[int] = set()
    for section in image.sections:
        body = data[section.raw_offset : section.raw_offset + section.raw_size]
        cursor = 0
        while True:
            offset = body.find(needle, cursor)
            if offset < 0:
                break
            result.add(section.virtual_address + offset)
            cursor = offset + 1
    return result


def _direct_target(source_rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise CorpseClassificationBoundaryError("direct edge is not rel32 CALL")
    return source_rva + 5 + struct.unpack_from("<i", encoded, 1)[0]


def _line_code(line: str) -> str:
    return line.split("--", 1)[0]


def _verify_dependency(
    spec: Mapping[str, str],
    executable: Path,
    content_root: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / spec["path"]
    if path.is_symlink() or not path.is_file():
        raise CorpseClassificationBoundaryError(
            f"dependency is missing or unsafe: {spec['id']}"
        )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
        raise CorpseClassificationBoundaryError(
            f"dependency file differs: {spec['id']}"
        )
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpseClassificationBoundaryError(
            f"dependency JSON differs: {spec['id']}"
        ) from exc
    if not isinstance(value, dict) or _canonical_sha256(value) != spec["canonical_sha256"]:
        raise CorpseClassificationBoundaryError(
            f"dependency canonical fields differ: {spec['id']}"
        )
    try:
        if spec["id"] == "zero_hp_cleanup_boundary":
            validate_zero_hp_cleanup_boundary_map(
                executable,
                content_root,
                value,
            )
        else:
            validate_specialized_enemy_death_boundary_map(
                executable,
                content_root,
                value,
            )
    except (ZeroHpCleanupBoundaryError, SpecializedEnemyDeathBoundaryError) as exc:
        raise CorpseClassificationBoundaryError(
            f"dependency binding differs: {spec['id']}"
        ) from exc


def _definition_owner(lines: list[str], line_number: int) -> str | None:
    # Pawn table declarations in the shipped corpus begin at column zero;
    # properties inside those tables are indented.  Keeping that distinction
    # prevents a nearby property such as Health or Neutral from being mistaken
    # for the owner of an indented Corpse=true entry.
    declaration = re.compile(r"^([A-Za-z_]\w*)[ \t]*=")
    for index in range(line_number - 2, max(-1, line_number - 30), -1):
        code = _line_code(lines[index])
        match = declaration.search(code)
        if match and match.group(1) != "Corpse":
            return match.group(1)
    return None


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise CorpseClassificationBoundaryError("content root is not a directory")

    selected: dict[str, str] = {}
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise CorpseClassificationBoundaryError(
                f"source is missing or escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise CorpseClassificationBoundaryError(
                f"source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if len(raw) != spec["size"] or hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise CorpseClassificationBoundaryError(f"source differs: {spec['path']}")
        text = raw.decode("utf-8")
        if any(symbol not in text for symbol in spec["symbols"]):
            raise CorpseClassificationBoundaryError(
                f"source symbol differs: {spec['path']}"
            )
        selected[spec["path"]] = text

    lua_paths = sorted(
        (
            path
            for path in (root / "scripts").rglob("*.lua")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if len(lua_paths) != 153:
        raise CorpseClassificationBoundaryError("accepted-tree Lua file count differs")

    active_text_parts: list[str] = []
    actual_true: list[tuple[str, int, str]] = []
    corpse_overrides: dict[str, bool] = {}
    for path in lua_paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        active_lines = [_line_code(line) for line in lines]
        active_text_parts.append("\n".join(active_lines))
        for line_number, code in enumerate(active_lines, 1):
            property_match = re.search(
                r"\bCorpse\s*=\s*(true|false)\b",
                code,
            )
            if property_match:
                owner = _definition_owner(lines, line_number)
                if owner is None:
                    raise CorpseClassificationBoundaryError(
                        "Corpse property owner differs"
                    )
                value = property_match.group(1) == "true"
                previous = corpse_overrides.get(owner)
                if previous is not None and previous is not value:
                    raise CorpseClassificationBoundaryError(
                        f"conflicting Corpse override appeared: {owner}"
                    )
                corpse_overrides[owner] = value
                if value:
                    actual_true.append((relative, line_number, owner))

    if actual_true != list(CORPSE_TRUE_OCCURRENCES):
        raise CorpseClassificationBoundaryError("active Corpse=true inventory differs")

    active_joined = "\n".join(active_text_parts)
    inheritance_edges = re.findall(
        r"(?m)^[ \t]*([A-Za-z_]\w*)[ \t]*=[ \t]*"
        r"([A-Za-z_]\w*)[ \t]*:[ \t]*new[ \t]*\{",
        active_joined,
    )
    explicit_types = {item[2] for item in CORPSE_TRUE_OCCURRENCES}
    effective_types = set(explicit_types)
    changed = True
    while changed:
        changed = False
        for child, parent in inheritance_edges:
            if (
                parent in effective_types
                and corpse_overrides.get(child) is not False
                and child not in effective_types
            ):
                effective_types.add(child)
                changed = True

    effective_actual = tuple(sorted(effective_types))
    if effective_actual != EFFECTIVE_CORPSE_TYPES:
        raise CorpseClassificationBoundaryError(
            "effective Corpse=true inventory differs"
        )

    inherited_actual: set[tuple[str, str]] = set()
    for pawn_type in effective_types - explicit_types:
        effective_parents = {
            parent
            for child, parent in inheritance_edges
            if child == pawn_type and parent in effective_types
        }
        if len(effective_parents) != 1:
            raise CorpseClassificationBoundaryError(
                f"effective Corpse parent differs: {pawn_type}"
            )
        inherited_actual.add((pawn_type, effective_parents.pop()))
    if inherited_actual != set(INHERITED_CORPSE_TYPES):
        raise CorpseClassificationBoundaryError(
            "Corpse=true inheritance inventory differs"
        )

    global_lua = selected["scripts/global.lua"]
    for pattern in (
        r"(?m)^[ \t]*Corpse[ \t]*=[ \t]*false,",
        r"(?m)^[ \t]*Minor[ \t]*=[ \t]*false,",
        r"(?m)^[ \t]*Leader[ \t]*=[ \t]*LEADER_NONE,",
        r"(?m)^[ \t]*DefaultFaction[ \t]*=[ \t]*FACTION_DEFAULT,",
    ):
        if not re.search(pattern, global_lua):
            raise CorpseClassificationBoundaryError("global Pawn defaults differ")

    if len(re.findall(r"\bJelly_Necro1\b", active_joined)) != 1:
        raise CorpseClassificationBoundaryError("Jelly_Necro1 reachability differs")
    if len(re.findall(r"\bLEADER_NECRO\b", active_joined)) != 1:
        raise CorpseClassificationBoundaryError("LEADER_NECRO reachability differs")
    if len(re.findall(r"\bPsion_Leech\b", active_joined)) != 1:
        raise CorpseClassificationBoundaryError("Psion_Leech inventory differs")
    if re.search(r"\bSetMutation\s*\(", active_joined):
        raise CorpseClassificationBoundaryError("shipped Lua SetMutation call appeared")

    ae_pawns = selected["scripts/advanced/ae_pawns.lua"]
    if not re.search(
        r"Jelly_Necro1\s*=\s*Jelly_Health1:new\s*\{[\s\S]*?"
        r"Leader\s*=\s*LEADER_NECRO,",
        ae_pawns,
    ):
        raise CorpseClassificationBoundaryError("dormant Necro definition differs")
    if re.search(
        r"(?:AddPawn|CreatePawn)\s*\(\s*[\"']Jelly_Necro1[\"']",
        active_joined,
    ):
        raise CorpseClassificationBoundaryError("Jelly_Necro1 factory route appeared")

    for path, prefix in (
        ("scripts/missions/acid/mission_piston.lua", "Pawn_Piston"),
        ("scripts/missions/acid/mission_laser.lua", "Pawn_Laser"),
    ):
        text = selected[path]
        expected_names = (
            f'{{ "{prefix}_U", "{prefix}_R", "{prefix}_D", "{prefix}_L" }}'
        )
        if expected_names not in text or "PAWN_FACTORY:CreatePawn(names[dir + 1])" not in text:
            raise CorpseClassificationBoundaryError(
                f"directional mission factory route differs: {prefix}"
            )


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
            "boundary_basis": spec["basis"],
        }
        for spec in REGION_SPECS
    ]


def _source_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in SOURCE_SPECS]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region": spec["region"],
            "start_rva": f"0x{spec['start']:08x}",
            "size": len(bytes.fromhex(spec["hex"])),
            "instruction_hex": spec["hex"],
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "rva": f"0x{rva:08x}",
            "size": len(raw),
            "hex": raw.hex(),
            "absolute_reference_rvas": [f"0x{item:08x}" for item in references],
            "complete_absolute_reference_inventory": True,
        }
        for anchor_id, rva, raw, references in DATA_ANCHOR_SPECS
    ]


def _direct_edge_records() -> list[dict[str, str]]:
    return [
        {
            "id": spec["id"],
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from']:08x}",
            "instruction_hex": spec["hex"],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target']:08x}",
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _call_inventory_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "target_rva": f"0x{spec['target']:08x}",
            "direct_call_sites": [f"0x{item:08x}" for item in spec["call_sites"]],
            "complete_raw_rel32_inventory": True,
        }
        for spec in CALL_INVENTORY_SPECS
    ]


def _expected_shape() -> dict[str, Any]:
    source_types = [item[2] for item in CORPSE_TRUE_OCCURRENCES]
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
        "dependencies": [dict(spec) for spec in DEPENDENCY_SPECS],
        "sources": _source_records(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "data_anchors": _data_anchor_records(),
        "direct_edges": _direct_edge_records(),
        "call_inventories": _call_inventory_records(),
        "source_inventory": {
            "global_corpse_default": False,
            "explicit_corpse_true_occurrences": [
                {"path": path, "line": line, "pawn_type": pawn_type}
                for path, line, pawn_type in CORPSE_TRUE_OCCURRENCES
            ],
            "explicit_corpse_true_types": source_types,
            "inherited_corpse_types": [
                {"pawn_type": child, "parent_type": parent}
                for child, parent in INHERITED_CORPSE_TYPES
            ],
            "effective_corpse_types": list(EFFECTIVE_CORPSE_TYPES),
            "explicit_type_count": len(source_types),
            "inherited_type_count": len(INHERITED_CORPSE_TYPES),
            "effective_type_count": len(EFFECTIVE_CORPSE_TYPES),
            "directional_piston_types": [
                "Pawn_Piston_U",
                "Pawn_Piston_R",
                "Pawn_Piston_D",
                "Pawn_Piston_L",
            ],
            "directional_laser_types": [
                "Pawn_Laser_U",
                "Pawn_Laser_R",
                "Pawn_Laser_D",
                "Pawn_Laser_L",
            ],
        },
        "contracts": {
            "common_predicate": {
                "native_rva": "0x0022cde0",
                "single_common_member": True,
                "subclass_vtable_dispatch_inside_predicate": False,
                "complete_direct_call_count": 27,
                "source_corpse_field_offset": "0x0f80",
                "is_mech_field_offset": "0x09e4",
                "internal_lifecycle_state_offset": "0x09e0",
                "mutation_field_offset": "0x10e8",
                "special_lifecycle_states": [2, 3, 4],
                "required_mutation_id_for_special_states": 12,
                "plain_language": (
                    "Outside internal lifecycle states 2/3/4, a Mech or a "
                    "Corpse=true pawn returns true. Other cases require mutation "
                    "12 to be current or globally available and eligible."
                ),
            },
            "mutation_12_eligibility": {
                "helper_rva": "0x0023d6a0",
                "registered_name": "LEADER_NECRO",
                "registered_value": 12,
                "current_mutation_setter_name": "SetMutation",
                "current_mutation_setter_rva": "0x0023ac60",
                "team_field_offset": "0x00b0",
                "default_faction_field_offset": "0x10bc",
                "is_mech_field_offset": "0x09e4",
                "leader_field_offset": "0x1318",
                "minor_field_offset": "0x10d0",
                "ordinary_enemy_team_value": 6,
                "ordinary_enemy_default_faction_value": 0,
                "alternate_team_value": 4,
                "alternate_recipient_passive": "Psion_Leech",
                "current_leader_self_excluded": True,
                "minor_recipient_excluded": True,
                "teleporter_is_an_input": False,
            },
            "shipped_reachability": {
                "jelly_necro_table_defined": True,
                "jelly_necro_parent": "Jelly_Health1",
                "jelly_necro_leader": "LEADER_NECRO",
                "jelly_necro_other_active_lua_references": 0,
                "jelly_necro_add_pawn_calls": 0,
                "jelly_necro_factory_calls": 0,
                "jelly_necro_spawner_entries": 0,
                "shipped_lua_set_mutation_calls": 0,
                "mutation_12_reachable_from_accepted_shipped_lua": False,
                "modded_or_direct_native_mutation_12_outside_scope": True,
            },
            "solver_conformance": {
                "bridge_current_field": "corpse",
                "bridge_static_field": "corpse_on_death",
                "python_static_type_count": 16,
                "rust_static_type_count": 16,
                "all_effective_source_types_already_covered": True,
                "current_bridge_value_remains_authoritative": True,
                "simulator_contradiction_found": False,
                "simulator_change_required": False,
                "simulator_version": 407,
            },
        },
        "findings": [
            {
                "id": "iscorpse_is_one_common_member",
                "classification": "fact",
                "claim": (
                    "Pawn:IsCorpse is one direct common member with 27 complete "
                    "raw-rel32 call sites; it performs no subclass vtable dispatch."
                ),
            },
            {
                "id": "definition_fields_are_exact",
                "classification": "fact",
                "claim": (
                    "The exact definition loader maps Corpse to +0xf80, Leader "
                    "to +0x1318, Minor to +0x10d0, and DefaultFaction to +0x10bc."
                ),
            },
            {
                "id": "fallback_is_necro_mutation",
                "classification": "fact",
                "claim": (
                    "The predicate's constant-12 fallback is the registered "
                    "LEADER_NECRO mutation, not a Teleporter or subclass flag."
                ),
            },
            {
                "id": "necro_is_dormant_in_shipped_lua",
                "classification": "fact",
                "claim": (
                    "Jelly_Necro1 is defined once but has no shipped AddPawn, "
                    "factory, spawner, mission, or other source reference; shipped "
                    "Lua also never calls SetMutation."
                ),
            },
            {
                "id": "sixteen_effective_source_corpse_types",
                "classification": "fact",
                "claim": (
                    "The accepted 153-file Lua tree has ten explicit Corpse=true "
                    "types and six inheriting directional bodies, for exactly "
                    "16 effective source corpse types."
                ),
            },
            {
                "id": "solver_static_inventory_conforms",
                "classification": "fact",
                "claim": (
                    "Python and Rust already cover all 16 effective source types, "
                    "and the bridge exports both current IsCorpse and static "
                    "Corpse=true state, so no simulator change follows."
                ),
            },
        ],
        "qualification": (
            "Static class and field reachability is exact for build 13725832 and "
            "the accepted shipped Lua tree. The action/frame transitions into "
            "internal lifecycle states 2/3/4 and the exact removal frame remain "
            "outside this artifact."
        ),
        "refines": [
            {
                "artifact": DEPENDENCY_SPECS[0]["path"],
                "narrowed_unresolved_id": "subclass_death_and_corpse_results",
                "resolved_scope": (
                    "There is no subclass-specific IsCorpse implementation on "
                    "this build; its common static inputs and all effective "
                    "shipped Corpse=true definitions are exact."
                ),
                "remaining_scope": (
                    "The action/frame transitions into lifecycle states 2/3/4 "
                    "and the resulting removal frame remain unproven."
                ),
            }
        ],
        "solver_impact": {
            "simulator_contradiction_found": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "simulator_version": 407,
            "reason": (
                "The bridge exports current and static corpse state, and Python "
                "plus Rust already cover every effective shipped corpse type."
            ),
        },
        "notes": [
            "This is exact-build static evidence, not a runtime frame trace.",
            "Internal lifecycle state +0x9e0 is conservatively named by role only.",
            "Mission_Piston remains safety-gated until its action/cleanup order is proven.",
            "Modded or direct-native mutation-12 activation is outside shipped-source scope.",
        ],
        "unresolved": [
            {
                "id": "lifecycle_state_transition_timing",
                "question": (
                    "At which action/frame boundaries do killed pawns enter and "
                    "leave internal lifecycle states 2/3/4?"
                ),
                "next_evidence": (
                    "Map the state-transition callers or run a bounded multi-frame "
                    "IsDead/IsCorpse capture on a disposable mission state."
                ),
            },
            {
                "id": "mission_piston_action_order",
                "question": (
                    "How does native Mission_Auto schedule live Piston actions "
                    "relative to damage, corpse state, and Board cleanup?"
                ),
                "next_evidence": (
                    "Capture a controlled Mission_Piston action/corpse timeline; "
                    "do not remove the existing safety gate from this static map."
                ),
            },
        ],
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "source_count": len(SOURCE_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "call_inventory_count": len(CALL_INVENTORY_SPECS),
            "finding_count": 6,
            "unresolved_count": 2,
            "explicit_corpse_type_count": 10,
            "inherited_corpse_type_count": 6,
            "effective_corpse_type_count": 16,
            "common_predicate_proven": True,
            "mutation_12_identity_proven": True,
            "shipped_mutation_12_reachable": False,
            "simulator_contradiction_found": False,
            "simulator_change_required": False,
            "simulator_version": 407,
        },
    }


def build_corpse_classification_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build corpse-classification boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise CorpseClassificationBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise CorpseClassificationBoundaryError("executable identity differs")

    for spec in DEPENDENCY_SPECS:
        _verify_dependency(spec, executable, content_root)
    _verify_sources(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        try:
            body = _region_bytes(
                image,
                data,
                spec["start"],
                spec["end"] - spec["start"],
                ".text",
                spec["id"],
            )
        except Exception as exc:
            raise CorpseClassificationBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise CorpseClassificationBoundaryError(
                f"region bytes differ: {spec['id']}"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])

    decode_ranges: dict[str, tuple[int, int]] = {}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["start"], len(encoded)) != encoded:
            raise CorpseClassificationBoundaryError(
                f"control window differs: {spec['id']}"
            )
        start, end = ranges[spec["region"]]
        if not start <= spec["start"] < spec["start"] + len(encoded) <= end:
            raise CorpseClassificationBoundaryError(
                f"control window escapes region: {spec['id']}"
            )
        decode_ranges[spec["id"]] = (spec["start"], spec["start"] + len(encoded))

    try:
        decoded = _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise CorpseClassificationBoundaryError(
            f"instruction alignment differs: {exc}"
        ) from exc
    for name, (start, end) in decode_ranges.items():
        cursor = start
        instructions = decoded[name]
        while cursor < end:
            instruction = instructions.get(cursor)
            if instruction is None:
                raise CorpseClassificationBoundaryError(
                    f"undecoded instruction in {name}"
                )
            cursor += len(instruction[1])
        if cursor != end:
            raise CorpseClassificationBoundaryError(
                f"reviewed range ends inside instruction: {name}"
            )

    for anchor_id, rva, raw, references in DATA_ANCHOR_SPECS:
        if _bytes_at(image, data, rva, len(raw)) != raw:
            raise CorpseClassificationBoundaryError(
                f"data anchor differs: {anchor_id}"
            )
        va = image.image_base + rva
        if _absolute_va_sites(image, data, va) != set(references):
            raise CorpseClassificationBoundaryError(
                f"absolute reference inventory differs: {anchor_id}"
            )

    for spec in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["from"], len(encoded)) != encoded:
            raise CorpseClassificationBoundaryError(
                f"direct edge differs: {spec['id']}"
            )
        if _direct_target(spec["from"], encoded) != spec["target"]:
            raise CorpseClassificationBoundaryError(
                f"direct edge target differs: {spec['id']}"
            )

    for spec in CALL_INVENTORY_SPECS:
        if _raw_rel32_call_sites(image, data, spec["target"]) != set(
            spec["call_sites"]
        ):
            raise CorpseClassificationBoundaryError(
                f"direct-call inventory differs: {spec['id']}"
            )

    return _expected_shape()


def validate_corpse_classification_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise CorpseClassificationBoundaryError(
            "corpse-classification boundary fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "common_predicate_proven": True,
        "mutation_12_identity_proven": True,
        "effective_corpse_type_count": len(EFFECTIVE_CORPSE_TYPES),
        "shipped_mutation_12_reachable": False,
        "simulator_contradiction_found": False,
        "simulator_change_required": False,
        "simulator_version": 407,
    }


def validate_corpse_classification_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, source, byte, or prose drift."""
    expected = build_corpse_classification_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise CorpseClassificationBoundaryError(
            "corpse-classification boundary differs from exact-build analysis"
        )
    result = validate_corpse_classification_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_corpse_classification_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
