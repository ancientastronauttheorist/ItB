"""Bind the shipped Lua ancestry between enemy scoring and SkillEffects.

The native candidate wrapper invokes the dynamically resolved
``GetTargetScore`` callback.  This source-keyed continuation inventories every
active definition of that method, classifies whether it materializes the
actual Skill effect, a synthetic scoring effect, or no effect payload, and
checks every active ``GetSkillEffect`` body for explicit shipped Lua RNG calls.

It deliberately does not claim that native constructors or arbitrary bound
helpers are RNG-free, nor does it fabricate prospective callback inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.enemy_candidate_score_boundary import (
    EnemyCandidateScoreBoundaryError,
    validate_enemy_candidate_score_boundary_map_binding,
)
from src.observatory.enemy_skill_effect_boundary import (
    EnemySkillEffectBoundaryError,
    validate_enemy_skill_effect_boundary_map_binding,
)
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    _LUA_CONSTRUCTOR_RE,
    _constructor_end,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "lua_enemy_score_effect_ancestry"
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
EXPECTED_CALLBACK_INDEX_CANONICAL_SHA256 = (
    "56e19cdced8326d1401c7c9ea3baf033c9eb3b5e50825aac922ac90669b4ad71"
)
EXPECTED_EFFECT_BODY_MANIFEST_SHA256 = (
    "da84da86aaab86046b530547644307dd7159b2589f7a06be20fc0bd122899290"
)
EXPECTED_SCRIPT_FILE_COUNT = 305
EXPECTED_LUA_FILE_COUNT = 153
EXPECTED_ANALYSIS_LUA_FILE_COUNT = 152
EXPECTED_CALLBACK_DEFINITION_COUNT = 757
EXPECTED_TARGET_SCORE_DEFINITION_COUNT = 20
EXPECTED_SKILL_EFFECT_DEFINITION_COUNT = 186
EXPECTED_SKILL_EFFECT_SOURCE_FILE_COUNT = 45
EXPLICIT_RNG_NAMES = (
    "random_int",
    "random_bool",
    "random_element",
    "random_removal",
)


class EnemyScoreEffectAncestryError(RuntimeError):
    """Raised when the exact source ancestry no longer reproduces."""


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
        "role": (
            "Pins the native GetTargetScore wrapper, callback boundary, and "
            "pre/post-callback score adjustments."
        ),
    },
    {
        "id": "enemy_skill_effect_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "enemy_skill_effect_boundary.json"
        ),
        "file_sha256": (
            "bd8fe003c19d8440569a7a6fb0ba1524481280e4f5dc31afdb5d93a2bc5d9c13"
        ),
        "canonical_sha256": (
            "d3502ffc37ce5fb0a685e6df3587173f2076f0701e944dbd4888ee0f46711bdd"
        ),
        "role": (
            "Pins the separate native cache materializer so direct Lua "
            "score-side effect construction is not conflated with it."
        ),
    },
)


# path, source SHA, line, symbol, body SHA, body bytes, payload route,
# reviewed actual-effect cardinality, self-effect calls, local constructors,
# ScoreList calls, nested GetTargetScore receivers.
TARGET_SCORE_SPECS = (
    (
        "scripts/advanced/ae_weapons_enemy.lua",
        "db757b1afa790fe3f7576930abd0c7e4cf5d8b9dc7308aa15ce9a9736f224d13",
        127,
        "ShamanAtk1:GetTargetScore",
        "21addce7ee850e5d56be59f85f10b6b46490dc6f58a516e895b0c8b485d52330",
        400,
        "nested_actual_effect",
        "zero on board edge or negative deploy score; otherwise four TotemAtk1 base-score calls",
        0,
        0,
        0,
        ("TotemAtk1",),
    ),
    (
        "scripts/advanced/ae_weapons_enemy.lua",
        "db757b1afa790fe3f7576930abd0c7e4cf5d8b9dc7308aa15ce9a9736f224d13",
        462,
        "DungAtk1:GetTargetScore",
        "91b5927d00e10141b56bf69dacce77ccdce5dc1b5643aae60ad7dcf18b15b223",
        1005,
        "synthetic_local_effect",
        "zero actual effects; one local fake q_effect is scored",
        0,
        1,
        1,
        (),
    ),
    (
        "scripts/advanced/bosses/blobber.lua",
        "0044135d2690c28b7f3a4178c010a0e97d12a07873276a2cc735a4331b0f728c",
        103,
        "BlobAtkB:GetTargetScore",
        "49c4dd5866d8311e35b0608c8aac9809e3d799f28577ba134a202a26439beaaa",
        58,
        "no_effect_payload",
        "zero; returns literal 100",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/advanced/bosses/centipede.lua",
        "eaa9a21947be4b7aa8e016558aadc79cb528f1bfa3cf20c2fd747ff947711ef0",
        46,
        "CentipedeAtkB:GetTargetScore",
        "58e7e0e932a8ffcbaa44388ab6523d73ec835e0d7a883abf4be8ca0cc4d16809",
        452,
        "direct_actual_effect",
        "zero when p2 is TEAM_ENEMY; otherwise one self GetSkillEffect q_effect",
        1,
        1,
        1,
        (),
    ),
    (
        "scripts/advanced/bosses/mosquito.lua",
        "4c67917a6d7ce4c8f11a3ca7b1f45e6c692d8fd35b6636d38d176f1dfabbfd16",
        38,
        "MosquitoAtkB:GetTargetScore",
        "0b1bf8074d148be8eba929cad6e4a8583ae1fc70481df4f7e4d5e2c70605e926",
        202,
        "direct_actual_effect",
        "zero when p2 is a Mech; otherwise one self GetSkillEffect q_effect",
        1,
        0,
        1,
        (),
    ),
    (
        "scripts/advanced/bosses/scarab.lua",
        "0600e298add07db560176c7b6efdfe8b4fca5dfde93c86457dd7ffd3961b6e29",
        46,
        "ScarabAtkB:GetTargetScore",
        "2774030e5b48ab7d754e4eeaffbeb3081d3e0f5c271cf67b3ec6fb1b6ebc15fc",
        161,
        "synthetic_local_effect",
        "zero actual effects; one local four-damage q_effect is scored",
        0,
        1,
        1,
        (),
    ),
    (
        "scripts/advanced/bosses/starfish.lua",
        "6d7d122e7be43abf535bf4295afde222aeb6d61482a97d7787d1f962b585fe94",
        50,
        "StarfishAtkB1:GetTargetScore",
        "7b24174c8a010f3799dca8f0ae3b561c164ae635fdae548cc3d56cec8fa657e7",
        301,
        "synthetic_local_effect",
        "zero actual effects; one local four-diagonal q_effect is scored",
        0,
        1,
        1,
        (),
    ),
    (
        "scripts/advanced/missions/grass/mission_armored_train.lua",
        "4c1438bd02ffdcc0d4f975f432168d1d45017126f819995c86873978b67a288a",
        95,
        "Armored_Train_Move:GetTargetScore",
        "92fc9e1e5832c37de77669e6b8a0cba4b443a171af4538b56ee82ee1ef627b8d",
        77,
        "no_effect_payload",
        "zero; returns DAMAGE_DEATH",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/global.lua",
        "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
        378,
        "Skill:GetTargetScore",
        "85b370b2d3d9d4284ce94f03844a5047da731a6f4c06a4198a0604561df6d5f4",
        422,
        "direct_actual_effect",
        "exactly one dynamic self GetSkillEffect; scores both instant and queued lists",
        1,
        0,
        2,
        (),
    ),
    (
        "scripts/missions/acid/mission_laser.lua",
        "e9195a160fd8a7b971555d767033eb7baea116668462cc0f50d22de01d2b13db",
        74,
        "Laser_U_Atk:GetTargetScore",
        "c5beff104a2a9ec2c2200a64134266bb0f401eed91cc115e6ce46cc70e4e0afa",
        61,
        "no_effect_payload",
        "zero; returns literal 100",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/missions/acid/mission_piston.lua",
        "1f426bad3b4149f0088831680264f716a3f9cc6acebf828306946c55990d51ad",
        73,
        "Piston_U_Atk:GetTargetScore",
        "eb534619214e6bbcd1916c92fa7179614e2dd6b0e36d618969fdb085e1b34eb4",
        62,
        "no_effect_payload",
        "zero; returns literal 100",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/missions/bosses/spider.lua",
        "f7d81d714922e1b5b22d5b76a8edcb6fb96dd61ae5b20a3008c66b5068046455",
        114,
        "SpiderlingHatch1:GetTargetScore",
        "702ab7285f09ae8999d3978d4c39848a2a128db674998e4dee85589b0e26218f",
        60,
        "no_effect_payload",
        "zero; returns literal 10",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/missions/mission_train.lua",
        "a9ec7ce1ea386e3b82ecd992b6cacd8ca17990cb37f7109e8060140cbb3a5e0b",
        181,
        "Train_Move:GetTargetScore",
        "0f892447d559f7c8ff90a9bfc928af66c4cdc3b799ef060995ded08e7b80bc4f",
        60,
        "no_effect_payload",
        "zero; returns literal 100",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/missions/sand/mission_filler.lua",
        "38e00c007476a42c05bbe4968f9b081de4bbdfb3761667b0e3e72c28c39079f9",
        65,
        "Filler_Attack:GetTargetScore",
        "d8efcacb642913fe46f4f327d8d3f40eb42ca87f36c244bb78e07695528a5e97",
        58,
        "no_effect_payload",
        "zero; returns literal 10",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/weapons_base.lua",
        "bdb55457746d08b46e8b62ad7cfc27f0a08bde9fab7397a4780dfe945b5f8f38",
        230,
        "SelfTarget:GetTargetScore",
        "4cc8b8851206b15f7c44cec22184db1f1413e9b952db180fd4ac91e164d2b293",
        58,
        "no_effect_payload",
        "zero; returns literal 10",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/weapons_enemy.lua",
        "5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b",
        312,
        "CentipedeAtk1:GetTargetScore",
        "d1c647ad3bb6c323ca5ff13791c46ee8327744cc115370e1c33cedd0d4ab05ce",
        452,
        "direct_actual_effect",
        "zero when p2 is TEAM_ENEMY; otherwise one self GetSkillEffect q_effect",
        1,
        1,
        1,
        (),
    ),
    (
        "scripts/weapons_enemy.lua",
        "5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b",
        648,
        "BlobberAtk1:GetTargetScore",
        "79205b6ce78c98c730992ac36abe0fd79c4a02a473fe5c89d3413b5aca5562fc",
        467,
        "synthetic_local_effect",
        "zero actual effects; one local five-record q_effect is scored",
        0,
        1,
        1,
        (),
    ),
    (
        "scripts/weapons_enemy.lua",
        "5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b",
        732,
        "BlobAtk1:GetTargetScore",
        "100a77f996a51a8403b559826a46b06972de0165f108c91d7cf25c09dbc4f921",
        58,
        "no_effect_payload",
        "zero; returns literal 100",
        0,
        0,
        0,
        (),
    ),
    (
        "scripts/weapons_enemy.lua",
        "5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b",
        776,
        "SpiderAtk1:GetTargetScore",
        "b0fade2b9ec4d6e2c647a43438b70ff265efe252b3a585238fb64699b585956f",
        620,
        "no_effect_payload",
        "zero actual effects; board/deploy scoring only",
        0,
        1,
        0,
        (),
    ),
    (
        "scripts/weapons_enemy.lua",
        "5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b",
        840,
        "WebeggHatch1:GetTargetScore",
        "9f6a5439576366a9bc4bd48c75af992da3d22b094f266a10595ec2200ecffe31",
        56,
        "no_effect_payload",
        "zero; returns literal 10",
        0,
        0,
        0,
        (),
    ),
)


_METHOD_RE = re.compile(
    r"^[ \t]*(?P<function>function)[ \t]+"
    r"(?P<owner>[A-Za-z_][A-Za-z0-9_]*):"
    r"(?P<method>GetTargetScore|GetSkillEffect)[ \t]*\(",
    re.MULTILINE,
)
_TARGET_SCORE_IDENTIFIER_RE = re.compile(r"\bGetTargetScore\b")
_SELF_EFFECT_RE = re.compile(r"\bself\s*:\s*GetSkillEffect\s*\(")
_FINAL_EFFECT_RE = re.compile(r"\bGetFinalEffect(?:_Helper)?\s*\(")
_SKILL_EFFECT_CTOR_RE = re.compile(r"\bSkillEffect\s*\(")
_SCORE_LIST_RE = re.compile(r"\bScoreList\s*\(")
_NESTED_TARGET_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:\s*GetTargetScore\s*\("
)
_EXPLICIT_RNG_RE = re.compile(
    r"\b(?:" + "|".join(EXPLICIT_RNG_NAMES) + r")\s*\("
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


def _read_repo_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EnemyScoreEffectAncestryError(f"not a regular dependency: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyScoreEffectAncestryError(f"dependency is not an object: {path}")
    return value


def _verify_native_dependencies() -> None:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyScoreEffectAncestryError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_repo_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyScoreEffectAncestryError(
                f"dependency fields differ: {spec['id']}"
            )
        values[spec["id"]] = value
    try:
        validate_enemy_candidate_score_boundary_map_binding(
            values["enemy_candidate_score_boundary"]
        )
        validate_enemy_skill_effect_boundary_map_binding(
            values["enemy_skill_effect_boundary"]
        )
    except (EnemyCandidateScoreBoundaryError, EnemySkillEffectBoundaryError) as exc:
        raise EnemyScoreEffectAncestryError(
            f"native dependency binding differs: {exc}"
        ) from exc


def _validate_documents(
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    if not isinstance(inventory, Mapping) or not isinstance(callback_index, Mapping):
        raise EnemyScoreEffectAncestryError("inventory and callback index must be objects")
    if _canonical_sha256(inventory) != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise EnemyScoreEffectAncestryError("inventory fields differ")
    if _canonical_sha256(callback_index) != EXPECTED_CALLBACK_INDEX_CANONICAL_SHA256:
        raise EnemyScoreEffectAncestryError("callback index fields differ")

    try:
        scripts = inventory["content"]["scripts"]
        entries = scripts["files"]
        callbacks = callback_index["callbacks"]
        identity = callback_index["build_identity"]
        summary = callback_index["summary"]
    except (KeyError, TypeError) as exc:
        raise EnemyScoreEffectAncestryError("dependency schema differs") from exc
    if (
        scripts["revision_sha256"] != EXPECTED_SCRIPTS_REVISION
        or identity["scripts_revision_sha256"] != EXPECTED_SCRIPTS_REVISION
        or identity["build_id"] != EXPECTED_BUILD_ID
        or identity["executable_sha256"] != EXPECTED_EXECUTABLE_SHA256
        or summary["callback_definitions"] != EXPECTED_CALLBACK_DEFINITION_COUNT
        or not isinstance(entries, list)
        or not isinstance(callbacks, list)
    ):
        raise EnemyScoreEffectAncestryError("dependency identity or counts differ")
    return entries, callbacks


def _inventory_entry_map(entries: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if len(entries) != EXPECTED_SCRIPT_FILE_COUNT:
        raise EnemyScoreEffectAncestryError("script inventory file count differs")
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise EnemyScoreEffectAncestryError("script inventory entry is not an object")
        path = entry.get("path")
        if not isinstance(path, str) or path in result:
            raise EnemyScoreEffectAncestryError("script inventory path differs")
        result[path] = entry
    lua_count = sum(path.endswith(".lua") for path in result)
    if lua_count != EXPECTED_LUA_FILE_COUNT:
        raise EnemyScoreEffectAncestryError("accepted Lua file count differs")
    return result


def _read_lua_sources(
    content_root: Path,
    entries: dict[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for path, entry in entries.items():
        if not path.endswith(".lua") or path == "scripts/modloader.lua":
            continue
        try:
            relative = PurePosixPath(path)
            text = read_exact_inventory_file(
                content_root,
                relative,
                expected_size=entry.get("size"),
                expected_sha256=entry.get("sha256"),
            )
            masked = mask_lua_opaque(text)
            spans = lua_function_spans(masked)
        except WeaponCoverageError as exc:
            raise EnemyScoreEffectAncestryError(
                f"cannot analyze exact source {path}: {exc}"
            ) from exc
        span_by_start = {start: (start, end) for start, end in spans}
        definitions: dict[tuple[str, int], tuple[int, int, re.Match[str]]] = {}
        for match in _METHOD_RE.finditer(masked):
            start = match.start("function")
            span = span_by_start.get(start)
            if span is None:
                raise EnemyScoreEffectAncestryError(
                    f"callback function boundary differs: {path}"
                )
            symbol = f"{match.group('owner')}:{match.group('method')}"
            line = text.count("\n", 0, start) + 1
            key = (symbol, line)
            if key in definitions:
                raise EnemyScoreEffectAncestryError(
                    f"duplicate callback definition: {path}:{line}:{symbol}"
                )
            definitions[key] = (span[0], span[1], match)
        sources[path] = {
            "text": text,
            "masked": masked,
            "spans": spans,
            "definitions": definitions,
            "source_sha256": entry["sha256"],
        }
    if len(sources) != EXPECTED_ANALYSIS_LUA_FILE_COUNT:
        raise EnemyScoreEffectAncestryError("analysis-relevant Lua file count differs")
    return sources


def _callback_rows(
    callbacks: list[Mapping[str, Any]],
    suffix: str,
) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in callbacks
        if isinstance(row, Mapping)
        and isinstance(row.get("symbol"), str)
        and row["symbol"].endswith(suffix)
    ]
    return sorted(rows, key=lambda row: (row["source_path"], row["line"], row["symbol"]))


def _body_record(
    row: Mapping[str, Any],
    sources: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    path = row["source_path"]
    source = sources.get(path)
    if source is None or row.get("source_sha256") != source["source_sha256"]:
        raise EnemyScoreEffectAncestryError(f"callback source differs: {path}")
    key = (row["symbol"], row["line"])
    definition = source["definitions"].get(key)
    if definition is None:
        raise EnemyScoreEffectAncestryError(
            f"callback definition differs: {path}:{row['line']}:{row['symbol']}"
        )
    start, end, match = definition
    text = source["text"]
    masked = source["masked"]
    raw = text[start:end].encode("utf-8")
    body = masked[match.end() : end]
    return {
        "source_path": path,
        "source_sha256": row["source_sha256"],
        "line": row["line"],
        "symbol": row["symbol"],
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_size": len(raw),
        "self_effect_calls": len(_SELF_EFFECT_RE.findall(body)),
        "skill_effect_constructors": len(_SKILL_EFFECT_CTOR_RE.findall(body)),
        "score_list_calls": len(_SCORE_LIST_RE.findall(body)),
        "nested_target_score_receivers": _NESTED_TARGET_RE.findall(body),
        "get_final_effect_calls": len(_FINAL_EFFECT_RE.findall(body)),
        "explicit_rng_calls": len(_EXPLICIT_RNG_RE.findall(body)),
    }


def _expected_target_score_records() -> list[dict[str, Any]]:
    records = []
    for (
        path,
        source_sha256,
        line,
        symbol,
        body_sha256,
        body_size,
        payload_route,
        actual_effect_cardinality,
        self_effect_calls,
        skill_effect_constructors,
        score_list_calls,
        nested_receivers,
    ) in TARGET_SCORE_SPECS:
        records.append(
            {
                "source_path": path,
                "source_sha256": source_sha256,
                "line": line,
                "symbol": symbol,
                "body_sha256": body_sha256,
                "body_size": body_size,
                "payload_route": payload_route,
                "actual_effect_cardinality": actual_effect_cardinality,
                "self_effect_calls": self_effect_calls,
                "skill_effect_constructors": skill_effect_constructors,
                "score_list_calls": score_list_calls,
                "nested_target_score_receivers": list(nested_receivers),
                "get_final_effect_calls": 0,
                "explicit_rng_calls": 0,
            }
        )
    return records


def _verify_target_score_records(
    rows: list[Mapping[str, Any]],
    sources: Mapping[str, dict[str, Any]],
) -> None:
    actual = [_body_record(row, sources) for row in rows]
    expected = _expected_target_score_records()
    comparable = [
        {
            key: record[key]
            for key in record
            if key not in {"payload_route", "actual_effect_cardinality"}
        }
        for record in expected
    ]
    if actual != comparable:
        raise EnemyScoreEffectAncestryError("GetTargetScore bodies or calls differ")


def _verify_active_definition_census(
    rows: list[Mapping[str, Any]],
    suffix: str,
    sources: Mapping[str, dict[str, Any]],
) -> None:
    indexed = {
        (row["source_path"], row["line"], row["symbol"])
        for row in rows
    }
    parsed = {
        (path, line, symbol)
        for path, source in sources.items()
        for symbol, line in source["definitions"]
        if symbol.endswith(suffix)
    }
    if parsed != indexed:
        raise EnemyScoreEffectAncestryError(
            f"active {suffix[1:]} definition census differs"
        )


def _verify_occurrence_census(sources: Mapping[str, dict[str, Any]]) -> None:
    raw_count = sum(
        len(_TARGET_SCORE_IDENTIFIER_RE.findall(source["text"]))
        for source in sources.values()
    )
    active_count = sum(
        len(_TARGET_SCORE_IDENTIFIER_RE.findall(source["masked"]))
        for source in sources.values()
    )
    if raw_count != 22 or active_count != 21:
        raise EnemyScoreEffectAncestryError("GetTargetScore occurrence census differs")
    garden = sources["scripts/weapons_enemy.lua"]
    raw_match = re.search(
        r"function\s+Garden_Atk:GetTargetScore\s*\(", garden["text"]
    )
    if (
        raw_match is None
        or garden["text"].count("\n", 0, raw_match.start()) + 1 != 895
        or garden["masked"][raw_match.start() : raw_match.end()].strip()
    ):
        raise EnemyScoreEffectAncestryError(
            "commented Garden_Atk:GetTargetScore exclusion differs"
        )


def _verify_effect_census(
    rows: list[Mapping[str, Any]],
    sources: Mapping[str, dict[str, Any]],
) -> None:
    if (
        len(rows) != EXPECTED_SKILL_EFFECT_DEFINITION_COUNT
        or len({row["source_path"] for row in rows})
        != EXPECTED_SKILL_EFFECT_SOURCE_FILE_COUNT
    ):
        raise EnemyScoreEffectAncestryError("GetSkillEffect definition count differs")
    records = [_body_record(row, sources) for row in rows]
    if any(record["explicit_rng_calls"] for record in records):
        raise EnemyScoreEffectAncestryError(
            "GetSkillEffect gained an explicit shipped Lua RNG helper call"
        )
    manifest = [
        {
            key: record[key]
            for key in (
                "source_path",
                "source_sha256",
                "line",
                "symbol",
                "body_sha256",
                "body_size",
            )
        }
        for record in records
    ]
    if _canonical_sha256(manifest) != EXPECTED_EFFECT_BODY_MANIFEST_SHA256:
        raise EnemyScoreEffectAncestryError("GetSkillEffect body manifest differs")


def _verify_class_anchors(sources: Mapping[str, dict[str, Any]]) -> None:
    global_source = sources["scripts/global.lua"]
    create_class = next(
        (
            (start, end)
            for start, end in global_source["spans"]
            if global_source["text"].startswith("function CreateClass", start)
        ),
        None,
    )
    if create_class is None:
        raise EnemyScoreEffectAncestryError("CreateClass function is absent")
    start, end = create_class
    raw = global_source["text"][start:end].encode("utf-8")
    if (
        global_source["text"].count("\n", 0, start) + 1 != 86
        or len(raw) != 430
        or hashlib.sha256(raw).hexdigest()
        != "214fce796c535562d79f4cdeef89be1e098b7652b2444c6957702b6a6aed29f9"
    ):
        raise EnemyScoreEffectAncestryError("CreateClass body differs")
    line = global_source["text"].splitlines(keepends=True)[322].encode("utf-8")
    if (
        len(line) != 20
        or hashlib.sha256(line).hexdigest()
        != "81b92a105871e9919e5a72df0124ee75a0ce138a2ed65848cabf8032214e196e"
    ):
        raise EnemyScoreEffectAncestryError("CreateClass(Skill) anchor differs")

    enemy_source = sources["scripts/advanced/ae_weapons_enemy.lua"]
    constructor = next(
        (
            match
            for match in _LUA_CONSTRUCTOR_RE.finditer(enemy_source["masked"])
            if match.group(1) == "TotemAtk1"
        ),
        None,
    )
    if constructor is None or constructor.group(2) != "Skill":
        raise EnemyScoreEffectAncestryError("TotemAtk1 Skill parent differs")
    constructor_end = _constructor_end(enemy_source["masked"], constructor)
    if constructor_end is None:
        raise EnemyScoreEffectAncestryError("TotemAtk1 constructor boundary differs")
    raw = enemy_source["text"][constructor.start() : constructor_end].encode("utf-8")
    if (
        enemy_source["text"].count("\n", 0, constructor.start()) + 1 != 182
        or len(raw) != 467
        or hashlib.sha256(raw).hexdigest()
        != "e45d0f887ade5017c56fc1817e2abba823781870cdb27e9335413e55aea521d2"
    ):
        raise EnemyScoreEffectAncestryError("TotemAtk1 constructor differs")
    totem_effect = enemy_source["definitions"].get(
        ("TotemAtk1:GetSkillEffect", 201)
    )
    if totem_effect is None:
        raise EnemyScoreEffectAncestryError("TotemAtk1:GetSkillEffect differs")
    raw = enemy_source["text"][totem_effect[0] : totem_effect[1]].encode("utf-8")
    if (
        len(raw) != 427
        or hashlib.sha256(raw).hexdigest()
        != "0943923866e4613565b59c0be69a28a3244022a52d809478418884b3bdf8e865"
    ):
        raise EnemyScoreEffectAncestryError("TotemAtk1 effect body differs")


def _verify_sources(
    content_root: Path,
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
) -> None:
    entries, callbacks = _validate_documents(inventory, callback_index)
    entry_map = _inventory_entry_map(entries)
    sources = _read_lua_sources(content_root, entry_map)
    target_rows = _callback_rows(callbacks, ":GetTargetScore")
    effect_rows = _callback_rows(callbacks, ":GetSkillEffect")
    if len(target_rows) != EXPECTED_TARGET_SCORE_DEFINITION_COUNT:
        raise EnemyScoreEffectAncestryError("GetTargetScore definition count differs")
    _verify_active_definition_census(target_rows, ":GetTargetScore", sources)
    _verify_active_definition_census(effect_rows, ":GetSkillEffect", sources)
    _verify_occurrence_census(sources)
    _verify_target_score_records(target_rows, sources)
    _verify_effect_census(effect_rows, sources)
    _verify_class_anchors(sources)


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS] + [
        {
            "id": "accepted_local_inventory",
            "path": (
                "data/observatory/inventories/"
                "windows_build_13725832_31fe35265598_local_modified.json"
            ),
            "canonical_sha256": EXPECTED_INVENTORY_CANONICAL_SHA256,
            "role": "Pins all 305 scripts entries and the accepted 153-file Lua tree.",
        },
        {
            "id": "lua_callback_index",
            "path": (
                "data/observatory/callbacks/"
                "windows_build_13725832_31fe35265598_callback_index.json"
            ),
            "canonical_sha256": EXPECTED_CALLBACK_INDEX_CANONICAL_SHA256,
            "role": "Pins all active callback definition identities and source hashes.",
        },
    ]


def _class_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": "create_class",
            "source_path": "scripts/global.lua",
            "line": 86,
            "body_size": 430,
            "body_sha256": (
                "214fce796c535562d79f4cdeef89be1e098b7652b2444c6957702b6a6aed29f9"
            ),
            "meaning": (
                "new sets the child table metatable to self and writes self.__index=self."
            ),
        },
        {
            "id": "create_class_skill",
            "source_path": "scripts/global.lua",
            "line": 323,
            "body_size": 20,
            "body_sha256": (
                "81b92a105871e9919e5a72df0124ee75a0ce138a2ed65848cabf8032214e196e"
            ),
            "meaning": "Installs the reviewed inheritance constructor on Skill.",
        },
        {
            "id": "totem_atk1_constructor",
            "source_path": "scripts/advanced/ae_weapons_enemy.lua",
            "line": 182,
            "declared_parent": "Skill",
            "body_size": 467,
            "body_sha256": (
                "e45d0f887ade5017c56fc1817e2abba823781870cdb27e9335413e55aea521d2"
            ),
            "meaning": (
                "TotemAtk1 has no GetTargetScore override and inherits Skill:GetTargetScore."
            ),
        },
        {
            "id": "totem_atk1_effect",
            "source_path": "scripts/advanced/ae_weapons_enemy.lua",
            "line": 201,
            "body_size": 427,
            "body_sha256": (
                "0943923866e4613565b59c0be69a28a3244022a52d809478418884b3bdf8e865"
            ),
            "meaning": (
                "The inherited base scorer dynamically dispatches this Totem effect body."
            ),
        },
    ]


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "base_score_directly_materializes_actual_effect",
            "classification": "fact",
            "claim": (
                "Skill:GetTargetScore directly calls self:GetSkillEffect once, scores "
                "effect and q_effect, rejects instant scores below -20, and otherwise "
                "prefers queued score whenever q_effect is nonempty."
            ),
        },
        {
            "id": "score_side_effect_bypasses_native_cache_materializer",
            "classification": "inference",
            "claim": (
                "The native score wrapper invokes Lua GetTargetScore, whose source "
                "directly dispatches GetSkillEffect. That route does not call the "
                "separate native Skill cache materializer at RVA 0x00268050."
            ),
        },
        {
            "id": "four_direct_actual_effect_definitions",
            "classification": "fact",
            "claim": (
                "Exactly Skill, CentipedeAtk1, CentipedeAtkB, and MosquitoAtkB "
                "GetTargetScore definitions directly call self:GetSkillEffect."
            ),
        },
        {
            "id": "shaman_nested_totem_effect_route",
            "classification": "fact",
            "claim": (
                "ShamanAtk1 calls TotemAtk1:GetTargetScore in four directions after "
                "its gates. TotemAtk1 inherits Skill:GetTargetScore and therefore "
                "materializes TotemAtk1:GetSkillEffect on each nested evaluation."
            ),
        },
        {
            "id": "four_synthetic_score_effects",
            "classification": "fact",
            "claim": (
                "DungAtk1, ScarabAtkB, StarfishAtkB1, and BlobberAtk1 score a "
                "locally constructed synthetic SkillEffect rather than their actual "
                "GetSkillEffect payload."
            ),
        },
        {
            "id": "eleven_effect_payload_free_scores",
            "classification": "fact",
            "claim": (
                "The remaining eleven active definitions use constants or direct "
                "Board/deploy logic without scoring an actual or synthetic effect payload."
            ),
        },
        {
            "id": "score_callbacks_never_call_final_effect",
            "classification": "fact",
            "claim": (
                "None of the 20 active GetTargetScore bodies calls GetFinalEffect or "
                "GetFinalEffect_Helper; the base score route always uses GetSkillEffect."
            ),
        },
        {
            "id": "skill_effect_bodies_have_no_explicit_lua_rng_calls",
            "classification": "fact",
            "claim": (
                "Across all 186 active GetSkillEffect definitions, there are zero "
                "direct calls to random_int, random_bool, random_element, or "
                "random_removal."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "native_bound_helper_rng",
            "question": (
                "Can a native constructor or Board/effect helper called from a score "
                "body consume the shared CRT RNG indirectly?"
            ),
            "static_status": (
                "Explicit shipped Lua RNG calls are absent; transitive native-bound "
                "helper call graphs are not exhaustively proven RNG-free."
            ),
        },
        {
            "id": "prospective_callback_inputs",
            "question": (
                "Can every future Board query and concrete effect payload be supplied "
                "before the engine commits the enemy queue?"
            ),
            "static_status": (
                "Ancestry and bodies are exact, but prospective Board/callback inputs "
                "are not ordinary bridge state."
            ),
        },
        {
            "id": "modified_or_other_builds",
            "question": "Does the same callback ancestry hold on another content tree?",
            "static_status": (
                "All counts, bodies, inheritance anchors, and conclusions are exact "
                "to the accepted build-keyed Windows tree."
            ),
        },
    ]


def _expected_shape() -> dict[str, Any]:
    callbacks = _expected_target_score_records()
    findings = _findings()
    unresolved = _unresolved()
    route_counts = {
        route: sum(record["payload_route"] == route for record in callbacks)
        for route in (
            "direct_actual_effect",
            "nested_actual_effect",
            "synthetic_local_effect",
            "no_effect_payload",
        )
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION,
        },
        "dependencies": _dependency_records(),
        "source_scope": {
            "inventory_script_file_count": EXPECTED_SCRIPT_FILE_COUNT,
            "accepted_lua_file_count": EXPECTED_LUA_FILE_COUNT,
            "analysis_lua_file_count": EXPECTED_ANALYSIS_LUA_FILE_COUNT,
            "excluded_project_bridge_overlay": "scripts/modloader.lua",
            "callback_index_definition_count": EXPECTED_CALLBACK_DEFINITION_COUNT,
            "raw_get_target_score_identifier_count": 22,
            "active_get_target_score_identifier_count": 21,
            "active_get_target_score_definition_count": (
                EXPECTED_TARGET_SCORE_DEFINITION_COUNT
            ),
            "active_nondefinition_get_target_score_call_count": 1,
            "excluded_commented_definition": {
                "source_path": "scripts/weapons_enemy.lua",
                "line": 895,
                "symbol": "Garden_Atk:GetTargetScore",
            },
        },
        "class_anchors": _class_anchors(),
        "target_score_callbacks": callbacks,
        "skill_effect_census": {
            "active_definition_count": EXPECTED_SKILL_EFFECT_DEFINITION_COUNT,
            "source_file_count": EXPECTED_SKILL_EFFECT_SOURCE_FILE_COUNT,
            "body_manifest_sha256": EXPECTED_EFFECT_BODY_MANIFEST_SHA256,
            "searched_explicit_rng_helpers": list(EXPLICIT_RNG_NAMES),
            "explicit_rng_call_count": 0,
            "native_bound_helper_rng_complete": False,
        },
        "contracts": {
            "native_to_lua": (
                "native GetTargetScore wrapper -> dynamically resolved Lua GetTargetScore"
            ),
            "base_lua_route": (
                "Skill:GetTargetScore -> self:GetSkillEffect -> ScoreList"
            ),
            "native_cache_route": (
                "separate Skill cache materializer -> GetSkillEffect or "
                "GetFinalEffect_Helper -> annotations/postprocess"
            ),
            "score_route_uses_native_cache_materializer": False,
            "score_route_uses_final_effect": False,
            "settled_queue_remains_authoritative": True,
        },
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "active_target_score_definition_census_complete": True,
            "score_side_effect_ancestry_complete": True,
            "explicit_lua_rng_census_complete": True,
            "transitive_native_helper_rng_complete": False,
            "prospective_callback_inputs_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": len(_dependency_records()),
            "class_anchor_count": len(_class_anchors()),
            "target_score_definition_count": len(callbacks),
            "target_score_source_file_count": len(
                {record["source_path"] for record in callbacks}
            ),
            "route_counts": route_counts,
            "skill_effect_definition_count": EXPECTED_SKILL_EFFECT_DEFINITION_COUNT,
            "skill_effect_source_file_count": EXPECTED_SKILL_EFFECT_SOURCE_FILE_COUNT,
            "explicit_lua_rng_call_count": 0,
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "score_side_effect_ancestry_complete": True,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def build_enemy_score_effect_ancestry(
    content_root: Path,
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact ancestry artifact after verifying every source input."""
    _verify_native_dependencies()
    _verify_sources(content_root, inventory, callback_index)
    return _expected_shape()


def validate_enemy_score_effect_ancestry_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without reading the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyScoreEffectAncestryError("enemy score-effect ancestry fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "score_side_effect_ancestry_complete": True,
        "transitive_native_helper_rng_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_score_effect_ancestry(
    content_root: Path,
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the ancestry artifact and reject source or dependency drift."""
    expected = build_enemy_score_effect_ancestry(
        content_root,
        inventory,
        callback_index,
    )
    if dict(value) != expected:
        raise EnemyScoreEffectAncestryError(
            "enemy score-effect ancestry differs from exact source analysis"
        )
    result = validate_enemy_score_effect_ancestry_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_score_effect_ancestry(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
