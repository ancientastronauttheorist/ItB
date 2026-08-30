"""Build-keyed review accounting over the whole-program native function atlas.

The accounting overlay never promotes Ghidra names, namespaces, thunk flags,
body equality, or address proximity into semantic classifications.  Every
promotion is an explicit, hash-pinned registry claim backed by a repository
evidence record.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from src.observatory.program_facts import (
    ProgramFactsError,
    validate_program_facts,
)


SCHEMA_VERSION = 2
ANALYSIS_KIND = "pe_native_function_accounting"
VERIFICATION_KIND = "pe_native_function_accounting_verification"
REGISTRY_KIND = "pe_native_function_review_registry"
REVIEW_EVIDENCE_KIND = "pe_native_function_review_evidence"
SUPPORT_EVIDENCE_KIND = "pe_native_function_support_evidence"
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_TEXT = 1024
_RVA_RE = re.compile(r"0x(?:[0-9a-f]{8}|[0-9a-f]{16})\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
_DIRECTORY_ID_FIELDS = ("st_dev", "st_ino")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    *(f"COM{index}" for index in "¹²³"),
    *(f"LPT{index}" for index in "¹²³"),
}

BOUNDARY_STATUSES = {"reviewed_exact", "reviewed_conflict"}
OWNERSHIPS = {"unknown", "first_party", "third_party", "compiler_runtime"}
SUBSYSTEMS = {
    "unknown",
    "process_bootstrap_lua_binding",
    "game_campaign_profile_achievement",
    "board_pawn_skill_effect_scheduler",
    "player_action",
    "enemy_planning_spawn_rng",
    "mission_environment_final_flow",
    "save_profile_serialization",
    "ui_input_rendering",
    "audio",
    "platform_steam",
    "compiler_runtime",
    "third_party",
}
NATIVE_LUA_BOUNDARY_STATES = {
    "unknown",
    "none",
    "roles",
}
NATIVE_LUA_ROLES = {
    "cclosure_callback_target",
    "lua_api_consumer",
    "registration_builder",
    "registered_lua_callable",
}
REFERENCE_STATUSES = {"atlas_declared_direct_only", "reviewed_immediate"}
EXCLUSIONS = {
    "none",
    "third_party",
    "compiler_runtime",
    "unreachable",
    "duplicate_thunk",
    "data_only",
}
EVIDENCE_CLASSES = {"fact", "inference", "hypothesis"}
CLAIMED_LEVELS = {"L0", "L1", "L2", "EXCLUDED"}
SUPPORT_CLASSES = {
    "boundary",
    "ownership",
    "immediate_references",
    "semantic_io",
    "native_lua_boundary",
    "native_lua_role",
    "exclusion",
}
_REVIEW_RECORD_FIELDS = {
    "entry_rva",
    "atlas_record_sha256",
    "boundary_status",
    "ownership",
    "subsystem",
    "purpose",
    "inputs_outputs",
    "native_lua_boundary",
    "reference_status",
    "exclusion",
    "evidence_class",
    "rationale",
    "support",
}
_SUPPORT_RECORD_FIELDS = {
    "entry_rva",
    "atlas_record_sha256",
    "support_class",
    "role",
    "assertion_sha256",
    "evidence_class",
    "statement",
    "sources",
}
_NATIVE_LUA_DIRECT_CALL_ANALYSIS_KIND = (
    "pe_native_lua_direct_import_call_census"
)
_NATIVE_LUA_CCLOSURE_CALLBACK_ANALYSIS_KIND = (
    "pe_native_lua_immediate_cclosure_callback_census"
)
_NATIVE_LUA_CCLOSURE_SETFIELD_PUBLICATION_ANALYSIS_KIND = (
    "pe_native_lua_immediate_cclosure_setfield_publication_census"
)
_UPSTREAM_ADAPTERS: dict[str, Any] = {}


class NativeFunctionAccountingError(RuntimeError):
    """Raised when native review accounting is stale or overclaims evidence."""


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise NativeFunctionAccountingError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeFunctionAccountingError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise NativeFunctionAccountingError(f"{label} must be an array")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise NativeFunctionAccountingError(f"{label} must be bounded text")
    if len(value) > MAX_TEXT or "\0" in value or any(
        ord(character) < 0x20 and character not in "\t\n\r"
        for character in value
    ):
        raise NativeFunctionAccountingError(f"{label} must be bounded text")
    return value


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _unknown_native_lua_boundary() -> dict[str, Any]:
    return {"state": "unknown", "roles": []}


def _native_lua_boundary(value: Any, label: str) -> dict[str, Any]:
    boundary = _mapping(value, label)
    _exact_keys(boundary, {"state", "roles"}, label)
    state = _text(boundary["state"], f"{label}.state")
    if state not in NATIVE_LUA_BOUNDARY_STATES:
        raise NativeFunctionAccountingError(
            f"{label}.state is unsupported: {state}"
        )
    roles = _array(boundary["roles"], f"{label}.roles")
    normalized_roles = [
        _text(role, f"{label}.roles[{index}]")
        for index, role in enumerate(roles)
    ]
    if any(role not in NATIVE_LUA_ROLES for role in normalized_roles):
        unknown = sorted(set(normalized_roles) - NATIVE_LUA_ROLES)
        raise NativeFunctionAccountingError(
            f"{label}.roles has unsupported role(s): {unknown}"
        )
    if normalized_roles != sorted(set(normalized_roles)):
        raise NativeFunctionAccountingError(
            f"{label}.roles must be unique and canonically sorted"
        )
    if state == "roles" and not normalized_roles:
        raise NativeFunctionAccountingError(
            f"{label}.roles state requires at least one positive role"
        )
    if state in {"unknown", "none"} and normalized_roles:
        raise NativeFunctionAccountingError(
            f"{label}.{state} state cannot publish positive roles"
        )
    return {"state": state, "roles": normalized_roles}


def _rva(value: Any, label: str) -> str:
    if type(value) is not str or _RVA_RE.fullmatch(value) is None:
        raise NativeFunctionAccountingError(f"{label} must be a canonical RVA")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise NativeFunctionAccountingError(f"{label} must be lowercase SHA-256")
    return value


def _validate_json_tree(value: Any, label: str = "value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_tree(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise NativeFunctionAccountingError(
                    f"{label} contains a non-text key"
                )
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise NativeFunctionAccountingError(
        f"{label} contains a non-JSON or floating-point value"
    )


def _canonical_bytes(value: Any) -> bytes:
    _validate_json_tree(value)
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise NativeFunctionAccountingError(
            f"value cannot be canonically encoded: {exc}"
        ) from exc
    return (rendered + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def atlas_record_sha256(function: Mapping[str, Any]) -> str:
    """Return the exact canonical identity used to pin one atlas join."""
    return _canonical_sha256(function)


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _safe_repo_path(value: Any, label: str) -> PurePosixPath:
    value = _text(value, label)
    windows_path = PureWindowsPath(value)
    if (
        "\\" in value
        or ":" in value
        or windows_path.drive
        or windows_path.root
        or any(character in value for character in '<>"|?*\t\r\n')
    ):
        raise NativeFunctionAccountingError(
            f"{label} must be a normalized repository path"
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != value
    ):
        raise NativeFunctionAccountingError(
            f"{label} must be a normalized repository path"
        )
    for part in path.parts:
        reserved_stem = part.split(".", 1)[0].rstrip(" ").upper()
        if (
            part.endswith((" ", "."))
            or reserved_stem in _WINDOWS_RESERVED_NAMES
        ):
            raise NativeFunctionAccountingError(
                f"{label} must be a normalized repository path"
            )
    return path


def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeFunctionAccountingError(
                f"duplicate JSON object key in evidence: {key}"
            )
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise NativeFunctionAccountingError(
        f"floating-point JSON is unsupported in evidence: {value}"
    )


def _reject_constant(value: str) -> None:
    raise NativeFunctionAccountingError(f"invalid JSON constant in evidence: {value}")


def _read_repo_json(
    repo_root: Path,
    relative: PurePosixPath,
    expected_sha256: str,
) -> Mapping[str, Any]:
    raw_root = Path(os.path.abspath(repo_root))
    try:
        root_info = raw_root.lstat()
    except OSError as exc:
        raise NativeFunctionAccountingError(
            "repository root is not a readable real directory"
        ) from exc
    if (
        stat.S_ISLNK(root_info.st_mode)
        or _is_reparse(root_info)
        or not stat.S_ISDIR(root_info.st_mode)
    ):
        raise NativeFunctionAccountingError(
            "repository root is not a readable real directory"
        )
    root = raw_root.resolve(strict=True)
    parent_chain: list[tuple[Path, os.stat_result]] = [(raw_root, root_info)]
    current = root
    for part in relative.parts[:-1]:
        current /= part
        try:
            parent_info = current.lstat()
        except OSError as exc:
            raise NativeFunctionAccountingError(
                f"evidence parent is not readable: {relative}"
            ) from exc
        try:
            resolved_parent = current.resolve(strict=True)
        except OSError as exc:
            raise NativeFunctionAccountingError(
                f"evidence parent changed while resolving: {relative}"
            ) from exc
        if (
            stat.S_ISLNK(parent_info.st_mode)
            or _is_reparse(parent_info)
            or not stat.S_ISDIR(parent_info.st_mode)
            or not resolved_parent.is_relative_to(root)
        ):
            raise NativeFunctionAccountingError(
                f"evidence parent is not a contained real directory: {relative}"
            )
        parent_chain.append((current, parent_info))
    path = current / relative.parts[-1]
    try:
        link_before = path.lstat()
        resolved = path.resolve(strict=True)
        path_before = path.stat()
    except OSError as exc:
        raise NativeFunctionAccountingError(
            f"evidence file is not readable: {relative}"
        ) from exc
    if (
        stat.S_ISLNK(link_before.st_mode)
        or _is_reparse(link_before)
        or not stat.S_ISREG(path_before.st_mode)
        or not resolved.is_relative_to(root)
        or path_before.st_size > MAX_EVIDENCE_BYTES
    ):
        raise NativeFunctionAccountingError(
            f"evidence file is not a contained bounded regular file: {relative}"
        )
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if any(
                getattr(path_before, field) != getattr(handle_before, field)
                for field in _STABLE_STAT_FIELDS
            ):
                raise NativeFunctionAccountingError(
                    f"evidence file changed while opening: {relative}"
                )
            payload = stream.read(handle_before.st_size + 1)
            handle_after = os.fstat(stream.fileno())
    except OSError as exc:
        raise NativeFunctionAccountingError(
            f"evidence file could not be read: {relative}"
        ) from exc
    path_after = path.stat()
    link_after = path.lstat()
    parents_changed = False
    for parent, parent_before in parent_chain:
        try:
            parent_after = parent.lstat()
        except OSError:
            parents_changed = True
            break
        if (
            stat.S_ISLNK(parent_after.st_mode)
            or _is_reparse(parent_after)
            or not stat.S_ISDIR(parent_after.st_mode)
            or any(
                getattr(parent_before, field) != getattr(parent_after, field)
                for field in _DIRECTORY_ID_FIELDS
            )
        ):
            parents_changed = True
            break
    if (
        len(payload) != handle_before.st_size
        or parents_changed
        or any(
            getattr(handle_before, field) != getattr(handle_after, field)
            or getattr(handle_after, field) != getattr(path_after, field)
            or getattr(link_before, field) != getattr(link_after, field)
            for field in _STABLE_STAT_FIELDS
        )
        or stat.S_ISLNK(link_after.st_mode)
        or _is_reparse(link_after)
    ):
        raise NativeFunctionAccountingError(
            f"evidence file changed while reading: {relative}"
        )
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_sha256:
        raise NativeFunctionAccountingError(
            f"evidence file SHA-256 differs: {relative}"
        )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_json_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFunctionAccountingError(
            f"evidence file is not strict JSON: {relative}"
        ) from exc
    return _mapping(value, f"evidence file {relative}")


def _json_pointer(document: Any, pointer: Any, label: str) -> Any:
    if type(pointer) is not str or not pointer.startswith("/") or len(pointer) > 1024:
        raise NativeFunctionAccountingError(
            f"{label} must be a non-root JSON pointer"
        )
    value = document
    for raw_part in pointer[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", raw_part):
            raise NativeFunctionAccountingError(f"{label} has an invalid escape")
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping):
            if part not in value:
                raise NativeFunctionAccountingError(f"{label} does not resolve")
            value = value[part]
        elif type(value) is list:
            if (
                not part.isascii()
                or not part.isdecimal()
                or (len(part) > 1 and part.startswith("0"))
            ):
                raise NativeFunctionAccountingError(
                    f"{label} has an invalid array index"
                )
            index = int(part)
            if index >= len(value):
                raise NativeFunctionAccountingError(f"{label} does not resolve")
            value = value[index]
        else:
            raise NativeFunctionAccountingError(f"{label} does not resolve")
    return value


def _identity_matches(
    evidence: Mapping[str, Any],
    atlas_identity: Mapping[str, Any],
    label: str,
) -> None:
    candidates = [
        evidence[key]
        for key in ("identity", "build_identity")
        if key in evidence
    ]
    if len(candidates) != 1:
        raise NativeFunctionAccountingError(
            f"{label} needs exactly one identity/build_identity object"
        )
    identity = _mapping(candidates[0], f"{label} identity")
    identity_keys = set(identity)
    atlas_keys = set(atlas_identity)
    if identity_keys != atlas_keys:
        raise NativeFunctionAccountingError(
            f"{label} identity fields differ; "
            f"missing={sorted(atlas_keys - identity_keys)}, "
            f"unknown={sorted(identity_keys - atlas_keys)}"
        )
    for key in sorted(atlas_keys):
        if _canonical_bytes(identity[key]) != _canonical_bytes(atlas_identity[key]):
            raise NativeFunctionAccountingError(
                f"{label} identity differs at {key}"
            )


def _validate_evidence_document(
    document: Mapping[str, Any],
    *,
    kind: str,
    label: str,
) -> None:
    _exact_keys(
        document,
        {"schema_version", "analysis_kind", "build_identity", "records"},
        label,
    )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != SCHEMA_VERSION
    ):
        raise NativeFunctionAccountingError(
            f"{label} has an unsupported evidence schema"
        )
    if document["analysis_kind"] != kind:
        raise NativeFunctionAccountingError(
            f"{label} is not {kind} evidence"
        )
    if not _array(document["records"], f"{label}.records"):
        raise NativeFunctionAccountingError(f"{label}.records must be non-empty")


def _direct_record_pointer(pointer: str, label: str) -> None:
    if re.fullmatch(r"/records/(?:0|[1-9][0-9]*)", pointer) is None:
        raise NativeFunctionAccountingError(
            f"{label} must point directly to one records entry"
        )


def _support_assertion(
    review: Mapping[str, Any],
    support_class: str,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    boundary = _native_lua_boundary(
        review["native_lua_boundary"], "review.native_lua_boundary"
    )
    if support_class == "native_lua_role":
        if role is None or role not in boundary["roles"]:
            raise NativeFunctionAccountingError(
                "native_lua_role support must bind one reviewed positive role"
            )
        return {"native_lua_role": role}
    if support_class == "native_lua_boundary":
        if role is not None or boundary["state"] != "none":
            raise NativeFunctionAccountingError(
                "native_lua_boundary support only proves a reviewed none state"
            )
        return {"native_lua_boundary": boundary}
    fields_by_class = {
        "boundary": ("boundary_status",),
        "ownership": ("ownership",),
        "immediate_references": ("reference_status",),
        "semantic_io": ("subsystem", "purpose", "inputs_outputs"),
        "exclusion": ("exclusion",),
    }
    fields = fields_by_class.get(support_class)
    if fields is None:
        raise NativeFunctionAccountingError(
            f"unsupported support assertion class: {support_class}"
        )
    return {field: review[field] for field in fields}


def _adapt_native_lua_direct_call_census(
    document: Mapping[str, Any],
    *,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    source_sha256: str,
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    json_pointer: str,
    entry_rva: str,
    atlas_record_identity: str,
    support_class: str,
    role: str | None,
    label: str,
) -> dict[str, Any]:
    """Derive only the positive direct-Lua-consumer role atom."""
    if support_class != "native_lua_role" or role != "lua_api_consumer":
        raise NativeFunctionAccountingError(
            f"{label} direct Lua calls prove only the lua_api_consumer role"
        )
    _direct_record_pointer(json_pointer, f"{label}.json_pointer")

    # Keep evidence-kind validation adapter-local and avoid introducing a
    # module-load dependency cycle as the adapter set grows.
    from src.observatory import native_lua_direct_calls as direct_calls

    cache_key = (_NATIVE_LUA_DIRECT_CALL_ANALYSIS_KIND, source_sha256)
    if cache_key not in verification_cache:
        try:
            verification = direct_calls.validate_native_lua_direct_call_census(
                executable,
                document,
                program_facts,
                inventory=inventory,
            )
        except direct_calls.NativeLuaDirectCallError as exc:
            raise NativeFunctionAccountingError(
                f"{label} direct Lua census failed exact binary verification: "
                f"{exc}"
            ) from exc
        verification_cache[cache_key] = verification

    target = _mapping(
        _json_pointer(document, json_pointer, f"{label}.json_pointer"),
        f"{label} pointed direct-call record",
    )

    if (
        target.get("entry_rva") != entry_rva
        or target.get("atlas_record_sha256") != atlas_record_identity
    ):
        raise NativeFunctionAccountingError(
            f"{label} direct Lua census does not describe the exact atlas record"
        )
    calls = target.get("direct_lua_import_calls")
    if type(calls) is not list or not calls:
        raise NativeFunctionAccountingError(
            f"{label} direct Lua census record has no retained direct calls"
        )
    if target.get("direct_call_count") != len(calls):
        raise NativeFunctionAccountingError(
            f"{label} direct Lua census call count differs"
        )
    return {
        "assertion": {"native_lua_role": "lua_api_consumer"},
        "evidence_class": "fact",
        "statement": (
            "The exact executable and atlas function contain at least one "
            "verified direct call to a named Lua 5.1 import."
        ),
    }


def _adapt_native_lua_cclosure_callback_census(
    document: Mapping[str, Any],
    *,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    source_sha256: str,
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    json_pointer: str,
    entry_rva: str,
    atlas_record_identity: str,
    support_class: str,
    role: str | None,
    label: str,
) -> dict[str, Any]:
    """Derive only a verified immediate C-closure-target role atom."""
    if support_class != "native_lua_role" or role != "cclosure_callback_target":
        raise NativeFunctionAccountingError(
            f"{label} immediate C-closure callbacks prove only the "
            "cclosure_callback_target role"
        )
    if re.fullmatch(r"/callback_targets/(?:0|[1-9][0-9]*)", json_pointer) is None:
        raise NativeFunctionAccountingError(
            f"{label}.json_pointer must point directly to one callback target"
        )

    # Both imports are lazy: the callback census imports accounting's atlas
    # record helper, and the direct census is its exact binary prerequisite.
    from src.observatory import native_lua_cclosure_callbacks as callbacks
    from src.observatory import native_lua_direct_calls as direct_calls_module

    cache_key = (_NATIVE_LUA_CCLOSURE_CALLBACK_ANALYSIS_KIND, source_sha256)
    if cache_key not in verification_cache:
        try:
            direct_calls = direct_calls_module.build_native_lua_direct_call_census(
                executable,
                program_facts,
                inventory=inventory,
            )
            verification = callbacks.validate_native_lua_cclosure_callback_census(
                executable,
                document,
                direct_calls,
                program_facts,
                inventory=inventory,
            )
        except (
            direct_calls_module.NativeLuaDirectCallError,
            callbacks.NativeLuaCClosureError,
        ) as exc:
            raise NativeFunctionAccountingError(
                f"{label} C-closure callback census failed exact binary "
                f"verification: {exc}"
            ) from exc
        verification_cache[cache_key] = verification

    target = _mapping(
        _json_pointer(document, json_pointer, f"{label}.json_pointer"),
        f"{label} pointed callback target",
    )
    if (
        target.get("callback_entry_rva") != entry_rva
        or target.get("callback_atlas_record_sha256")
        != atlas_record_identity
    ):
        raise NativeFunctionAccountingError(
            f"{label} callback target does not describe the exact atlas record"
        )
    resolved_site_count = target.get("resolved_site_count")
    if type(resolved_site_count) is not int or resolved_site_count <= 0:
        raise NativeFunctionAccountingError(
            f"{label} callback target has no resolved immediate sites"
        )
    return {
        "assertion": {"native_lua_role": "cclosure_callback_target"},
        "evidence_class": "fact",
        "statement": (
            "The exact executable contains a verified direct "
            "lua_pushcclosure site statically passing this exact atlas entry "
            "as its immediate C callback target; this does not prove runtime "
            "execution or Lua-visible registration."
        ),
    }


def _adapt_native_lua_cclosure_setfield_publication_census(
    document: Mapping[str, Any],
    *,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    source_sha256: str,
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    json_pointer: str,
    entry_rva: str,
    atlas_record_identity: str,
    support_class: str,
    role: str | None,
    label: str,
) -> dict[str, Any]:
    """Derive only exact static setfield publication role atoms."""
    if support_class != "native_lua_role":
        raise NativeFunctionAccountingError(
            f"{label} setfield publications prove only native Lua roles"
        )
    if role == "registered_lua_callable":
        pointer_pattern = r"/registered_targets/(?:0|[1-9][0-9]*)"
        pointer_description = "one registered callback target"
        target_label = "registered callback target"
        target_fields = {
            "callback_entry_rva",
            "callback_atlas_record_sha256",
            "publication_site_count",
            "builder_entry_rvas",
            "key_texts",
        }
        record_entry_field = "callback_entry_rva"
        record_hash_field = "callback_atlas_record_sha256"
    elif role == "registration_builder":
        pointer_pattern = r"/builders/(?:0|[1-9][0-9]*)"
        pointer_description = "one registration builder"
        target_label = "registration builder"
        target_fields = {
            "builder_entry_rva",
            "builder_atlas_record_sha256",
            "publication_site_count",
            "registered_callback_entry_rvas",
            "key_texts",
        }
        record_entry_field = "builder_entry_rva"
        record_hash_field = "builder_atlas_record_sha256"
    else:
        raise NativeFunctionAccountingError(
            f"{label} setfield publications prove only the "
            "registered_lua_callable or registration_builder role"
        )
    if re.fullmatch(pointer_pattern, json_pointer) is None:
        raise NativeFunctionAccountingError(
            f"{label}.json_pointer must point directly to {pointer_description}"
        )

    # Imports stay lazy because the publication and callback modules use the
    # accounting atlas-record helper while constructing their exact joins.
    from src.observatory import native_lua_cclosure_callbacks as callbacks
    from src.observatory import (
        native_lua_cclosure_setfield_publications as publications,
    )
    from src.observatory import native_lua_direct_calls as direct_calls_module

    cache_key = (
        _NATIVE_LUA_CCLOSURE_SETFIELD_PUBLICATION_ANALYSIS_KIND,
        source_sha256,
    )
    if cache_key not in verification_cache:
        try:
            direct_calls = direct_calls_module.build_native_lua_direct_call_census(
                executable,
                program_facts,
                inventory=inventory,
            )
            callback_census = callbacks.build_native_lua_cclosure_callback_census(
                executable,
                direct_calls,
                program_facts,
                inventory=inventory,
            )
            verification = (
                publications.validate_native_lua_cclosure_setfield_publication_census(
                    executable,
                    document,
                    direct_calls,
                    callback_census,
                    program_facts,
                    inventory=inventory,
                )
            )
        except (
            direct_calls_module.NativeLuaDirectCallError,
            callbacks.NativeLuaCClosureError,
            publications.NativeLuaCClosurePublicationError,
        ) as exc:
            raise NativeFunctionAccountingError(
                f"{label} C-closure setfield publication census failed exact "
                f"binary verification: {exc}"
            ) from exc
        verification_cache[cache_key] = verification

    target = _mapping(
        _json_pointer(document, json_pointer, f"{label}.json_pointer"),
        f"{label} pointed {target_label}",
    )
    _exact_keys(target, target_fields, f"{label} pointed {target_label}")
    if (
        target.get(record_entry_field) != entry_rva
        or target.get(record_hash_field) != atlas_record_identity
    ):
        raise NativeFunctionAccountingError(
            f"{label} {target_label} does not describe the exact atlas record"
        )
    publication_site_count = target.get("publication_site_count")
    if type(publication_site_count) is not int or publication_site_count <= 0:
        raise NativeFunctionAccountingError(
            f"{label} {target_label} has no exact publication sites"
        )
    if role == "registered_lua_callable":
        statement = (
            "The exact executable contains a verified static fall-through path "
            "that creates this immediate native C closure and stores it through "
            "lua_setfield into a Lua table field; this does not prove a global "
            "export, table identity, runtime execution, reachability, or lifetime."
        )
    else:
        statement = (
            "The exact executable and atlas function contain one or more "
            "verified static immediate-C-closure table-field publication paths; "
            "this does not prove ownership, a complete binding system, runtime "
            "execution, reachability, or lifetime."
        )
    return {
        "assertion": {"native_lua_role": role},
        "evidence_class": "fact",
        "statement": statement,
    }


_UPSTREAM_ADAPTERS[_NATIVE_LUA_DIRECT_CALL_ANALYSIS_KIND] = (
    _adapt_native_lua_direct_call_census
)
_UPSTREAM_ADAPTERS[_NATIVE_LUA_CCLOSURE_CALLBACK_ANALYSIS_KIND] = (
    _adapt_native_lua_cclosure_callback_census
)
_UPSTREAM_ADAPTERS[
    _NATIVE_LUA_CCLOSURE_SETFIELD_PUBLICATION_ANALYSIS_KIND
] = _adapt_native_lua_cclosure_setfield_publication_census


def _upstream_references(
    value: Any,
    *,
    label: str,
    repo_root: Path,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    atlas_identity: Mapping[str, Any],
    entry_rva: str,
    atlas_record_identity: str,
    support_class: str,
    role: str | None,
    expected_assertion: Mapping[str, Any],
    claim_evidence_class: str,
    support_evidence_path: PurePosixPath,
    review_evidence_path: PurePosixPath,
) -> list[dict[str, Any]]:
    raw_sources = _array(value, label)
    if not raw_sources:
        raise NativeFunctionAccountingError(f"{label} must be non-empty")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    evidence_strength = {"hypothesis": 0, "inference": 1, "fact": 2}
    for index, raw_source in enumerate(raw_sources):
        item_label = f"{label}[{index}]"
        source = _mapping(raw_source, item_label)
        _exact_keys(source, {"path", "sha256", "json_pointer"}, item_label)
        relative = _safe_repo_path(source["path"], f"{item_label}.path")
        if relative in {support_evidence_path, review_evidence_path}:
            raise NativeFunctionAccountingError(
                f"{item_label} cannot self-cite review/support evidence"
            )
        sha256 = _sha256(source["sha256"], f"{item_label}.sha256")
        pointer = _text(source["json_pointer"], f"{item_label}.json_pointer")
        key = (relative.as_posix(), pointer)
        if key in seen:
            raise NativeFunctionAccountingError(
                f"duplicate upstream evidence reference: {key}"
            )
        seen.add(key)
        document = _read_repo_json(repo_root, relative, sha256)
        upstream_kind = _text(
            document.get("analysis_kind"), f"{item_label}.analysis_kind"
        )
        adapter = _UPSTREAM_ADAPTERS.get(upstream_kind)
        if adapter is None:
            raise NativeFunctionAccountingError(
                f"{item_label} uses an unsupported upstream analysis kind: "
                f"{upstream_kind}"
            )
        derived = _mapping(
            adapter(
                document,
                executable=executable,
                inventory=inventory,
                program_facts=program_facts,
                source_sha256=sha256,
                verification_cache=verification_cache,
                json_pointer=pointer,
                entry_rva=entry_rva,
                atlas_record_identity=atlas_record_identity,
                support_class=support_class,
                role=role,
                label=item_label,
            ),
            f"{item_label} adapter result",
        )
        _exact_keys(
            derived,
            {"assertion", "evidence_class", "statement"},
            f"{item_label} adapter result",
        )
        derived_assertion = _mapping(
            derived["assertion"], f"{item_label} derived assertion"
        )
        if _canonical_bytes(derived_assertion) != _canonical_bytes(
            expected_assertion
        ):
            raise NativeFunctionAccountingError(
                f"{item_label} describes a different structured assertion"
            )
        source_class = _text(
            derived["evidence_class"], f"{item_label}.evidence_class"
        )
        if source_class not in EVIDENCE_CLASSES:
            raise NativeFunctionAccountingError(
                f"{item_label}.evidence_class is unsupported: {source_class}"
            )
        if evidence_strength[source_class] < evidence_strength[claim_evidence_class]:
            raise NativeFunctionAccountingError(
                f"{item_label} is weaker than the claim evidence class"
            )
        _text(derived["statement"], f"{item_label}.statement")
        normalized.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256,
                "json_pointer": pointer,
            }
        )
    if normalized != sorted(
        normalized,
        key=lambda item: (item["path"], item["json_pointer"]),
    ):
        raise NativeFunctionAccountingError(f"{label} must be canonically sorted")
    return normalized


def _support_references(
    value: Any,
    *,
    label: str,
    repo_root: Path,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    atlas_identity: Mapping[str, Any],
    entry_rva: str,
    atlas_record_identity: str,
    review_evidence_path: PurePosixPath,
    required_classes: set[str],
    claim_evidence_class: str,
    expected_review: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_support = _array(value, label)
    if not raw_support:
        raise NativeFunctionAccountingError(f"{label} must be non-empty")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str, str]] = set()
    observed_classes: set[str] = set()
    observed_roles: set[str] = set()
    evidence_strength = {"hypothesis": 0, "inference": 1, "fact": 2}
    for index, raw_item in enumerate(raw_support):
        item_label = f"{label}[{index}]"
        item = _mapping(raw_item, item_label)
        _exact_keys(
            item,
            {"support_class", "role", "path", "sha256", "json_pointer"},
            item_label,
        )
        support_class = _text(
            item["support_class"], f"{item_label}.support_class"
        )
        if support_class not in SUPPORT_CLASSES:
            raise NativeFunctionAccountingError(
                f"{item_label}.support_class is unsupported: {support_class}"
            )
        role = item["role"]
        if support_class == "native_lua_role":
            role = _text(role, f"{item_label}.role")
            boundary = _native_lua_boundary(
                expected_review["native_lua_boundary"],
                "review.native_lua_boundary",
            )
            if boundary["state"] != "roles" or role not in boundary["roles"]:
                raise NativeFunctionAccountingError(
                    f"{item_label}.role is not a reviewed positive role"
                )
        elif role is not None:
            raise NativeFunctionAccountingError(
                f"{item_label}.role must be null outside native_lua_role support"
            )
        relative = _safe_repo_path(item["path"], f"{item_label}.path")
        if relative == review_evidence_path:
            raise NativeFunctionAccountingError(
                f"{item_label} cannot cite its own review-evidence file"
            )
        sha256 = _sha256(item["sha256"], f"{item_label}.sha256")
        pointer = _text(item["json_pointer"], f"{item_label}.json_pointer")
        _direct_record_pointer(pointer, f"{item_label}.json_pointer")
        key = (support_class, role, relative.as_posix(), pointer)
        if key in seen:
            raise NativeFunctionAccountingError(
                f"duplicate support evidence reference: {key}"
            )
        seen.add(key)
        document = _read_repo_json(repo_root, relative, sha256)
        _validate_evidence_document(
            document,
            kind=SUPPORT_EVIDENCE_KIND,
            label=item_label,
        )
        _identity_matches(document, atlas_identity, item_label)
        target = _mapping(
            _json_pointer(document, pointer, f"{item_label}.json_pointer"),
            f"{item_label} pointed support record",
        )
        _exact_keys(target, _SUPPORT_RECORD_FIELDS, f"{item_label} record")
        if (
            _rva(target["entry_rva"], f"{item_label}.entry_rva") != entry_rva
            or _sha256(
                target["atlas_record_sha256"],
                f"{item_label}.atlas_record_sha256",
            )
            != atlas_record_identity
        ):
            raise NativeFunctionAccountingError(
                f"{item_label} does not support the exact atlas record"
            )
        if target["support_class"] != support_class:
            raise NativeFunctionAccountingError(
                f"{item_label} support class differs from its source record"
            )
        if target["role"] != role:
            raise NativeFunctionAccountingError(
                f"{item_label} role differs from its source record"
            )
        expected_assertion_sha256 = _canonical_sha256(
            _support_assertion(expected_review, support_class, role=role)
        )
        if (
            _sha256(
                target["assertion_sha256"],
                f"{item_label}.assertion_sha256",
            )
            != expected_assertion_sha256
        ):
            raise NativeFunctionAccountingError(
                f"{item_label} supports a different structured assertion"
            )
        source_class = _text(
            target["evidence_class"], f"{item_label}.evidence_class"
        )
        if source_class not in EVIDENCE_CLASSES:
            raise NativeFunctionAccountingError(
                f"{item_label}.evidence_class is unsupported: {source_class}"
            )
        if evidence_strength[source_class] < evidence_strength[claim_evidence_class]:
            raise NativeFunctionAccountingError(
                f"{item_label} is weaker than the claim evidence class"
            )
        _text(target["statement"], f"{item_label}.statement")
        _upstream_references(
            target["sources"],
            label=f"{item_label}.sources",
            repo_root=repo_root,
            executable=executable,
            inventory=inventory,
            program_facts=program_facts,
            verification_cache=verification_cache,
            atlas_identity=atlas_identity,
            entry_rva=entry_rva,
            atlas_record_identity=atlas_record_identity,
            support_class=support_class,
            role=role,
            expected_assertion=_support_assertion(
                expected_review, support_class, role=role
            ),
            claim_evidence_class=claim_evidence_class,
            support_evidence_path=relative,
            review_evidence_path=review_evidence_path,
        )
        observed_classes.add(support_class)
        if support_class == "native_lua_role":
            observed_roles.add(role)
        normalized.append(
            {
                "support_class": support_class,
                "role": role,
                "path": relative.as_posix(),
                "sha256": sha256,
                "json_pointer": pointer,
            }
        )
    if observed_classes != required_classes:
        raise NativeFunctionAccountingError(
            f"{label} classes differ; missing="
            f"{sorted(required_classes - observed_classes)}, "
            f"unexpected={sorted(observed_classes - required_classes)}"
        )
    expected_roles = set(
        _native_lua_boundary(
            expected_review["native_lua_boundary"],
            "review.native_lua_boundary",
        )["roles"]
    )
    if observed_roles != expected_roles:
        raise NativeFunctionAccountingError(
            f"{label} native Lua roles differ; missing="
            f"{sorted(expected_roles - observed_roles)}, unexpected="
            f"{sorted(observed_roles - expected_roles)}"
        )
    if normalized != sorted(
        normalized,
        key=lambda item: (
            item["support_class"],
            "" if item["role"] is None else item["role"],
            item["path"],
            item["json_pointer"],
        ),
    ):
        raise NativeFunctionAccountingError(f"{label} must be canonically sorted")
    return normalized


def _evidence_references(
    value: Any,
    *,
    label: str,
    repo_root: Path,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    atlas_identity: Mapping[str, Any],
    entry_rva: str,
    atlas_record_identity: str,
    expected_review: Mapping[str, Any],
    required_support_classes: set[str],
) -> list[dict[str, str]]:
    raw_references = _array(value, label)
    if not raw_references:
        raise NativeFunctionAccountingError(f"{label} must be non-empty")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    compared_fields = _REVIEW_RECORD_FIELDS - {"rationale", "support"}
    for index, raw_reference in enumerate(raw_references):
        item_label = f"{label}[{index}]"
        reference = _mapping(raw_reference, item_label)
        _exact_keys(reference, {"path", "sha256", "json_pointer"}, item_label)
        relative = _safe_repo_path(reference["path"], f"{item_label}.path")
        sha256 = _sha256(reference["sha256"], f"{item_label}.sha256")
        pointer = _text(
            reference["json_pointer"],
            f"{item_label}.json_pointer",
        )
        _direct_record_pointer(pointer, f"{item_label}.json_pointer")
        key = (relative.as_posix(), pointer)
        if key in seen:
            raise NativeFunctionAccountingError(f"duplicate evidence reference: {key}")
        seen.add(key)
        document = _read_repo_json(repo_root, relative, sha256)
        _validate_evidence_document(
            document,
            kind=REVIEW_EVIDENCE_KIND,
            label=item_label,
        )
        _identity_matches(document, atlas_identity, item_label)
        target = _mapping(
            _json_pointer(document, pointer, f"{item_label}.json_pointer"),
            f"{item_label} pointed review record",
        )
        _exact_keys(target, _REVIEW_RECORD_FIELDS, f"{item_label} record")
        for field in sorted(compared_fields):
            if target[field] != expected_review[field]:
                raise NativeFunctionAccountingError(
                    f"{item_label} review dimension differs at {field}"
                )
        _text(target["rationale"], f"{item_label}.rationale")
        _support_references(
            target["support"],
            label=f"{item_label}.support",
            repo_root=repo_root,
            executable=executable,
            inventory=inventory,
            program_facts=program_facts,
            verification_cache=verification_cache,
            atlas_identity=atlas_identity,
            entry_rva=entry_rva,
            atlas_record_identity=atlas_record_identity,
            review_evidence_path=relative,
            required_classes=required_support_classes,
            claim_evidence_class=expected_review["evidence_class"],
            expected_review=expected_review,
        )
        normalized.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256,
                "json_pointer": pointer,
            }
        )
    if normalized != sorted(
        normalized,
        key=lambda item: (item["path"], item["json_pointer"]),
    ):
        raise NativeFunctionAccountingError(f"{label} must be canonically sorted")
    return normalized


def _derive_level(review: Mapping[str, Any]) -> str:
    exclusion = review["exclusion"]
    if exclusion != "none":
        if exclusion in {"unreachable", "duplicate_thunk", "data_only"}:
            raise NativeFunctionAccountingError(
                f"{exclusion} exclusions are unsupported until their "
                "type-specific proof contract is implemented"
            )
        if (
            review["boundary_status"] != "reviewed_exact"
            or review["evidence_class"] != "fact"
        ):
            raise NativeFunctionAccountingError(
                "reviewed exclusions require exact boundaries and fact evidence"
            )
        if exclusion == "third_party" and (
            review["ownership"] != "third_party"
            or review["subsystem"] != "third_party"
        ):
            raise NativeFunctionAccountingError(
                "third-party exclusions need matching ownership and subsystem"
            )
        if exclusion == "compiler_runtime" and (
            review["ownership"] != "compiler_runtime"
            or review["subsystem"] != "compiler_runtime"
        ):
            raise NativeFunctionAccountingError(
                "compiler/runtime exclusions need matching ownership and subsystem"
            )
        return "EXCLUDED"

    level = "L0"
    if (
        review["boundary_status"] == "reviewed_exact"
        and review["ownership"] != "unknown"
        and review["reference_status"] == "reviewed_immediate"
        and review["evidence_class"] in {"fact", "inference"}
    ):
        level = "L1"
    if (
        level == "L1"
        and review["ownership"] == "first_party"
        and review["subsystem"]
        not in {"unknown", "compiler_runtime", "third_party"}
        and review["purpose"] is not None
        and review["inputs_outputs"] is not None
        and _native_lua_boundary(
            review["native_lua_boundary"], "review.native_lua_boundary"
        )["state"]
        != "unknown"
    ):
        level = "L2"
    return level


def _validate_authoritative_dimensions(
    review: Mapping[str, Any],
    achieved_level: str,
) -> None:
    if achieved_level == "L0":
        expected = {
            "ownership": "unknown",
            "subsystem": "unknown",
            "purpose": None,
            "inputs_outputs": None,
            "native_lua_boundary": _unknown_native_lua_boundary(),
            "reference_status": "atlas_declared_direct_only",
            "exclusion": "none",
        }
    elif achieved_level == "L1":
        expected = {
            "subsystem": "unknown",
            "purpose": None,
            "inputs_outputs": None,
            "native_lua_boundary": _unknown_native_lua_boundary(),
            "exclusion": "none",
        }
    elif achieved_level == "EXCLUDED":
        expected = {
            "purpose": None,
            "inputs_outputs": None,
            "native_lua_boundary": _unknown_native_lua_boundary(),
            "reference_status": "atlas_declared_direct_only",
        }
    else:
        return
    drift = [
        field
        for field, expected_value in expected.items()
        if review[field] != expected_value
    ]
    if drift:
        raise NativeFunctionAccountingError(
            f"{achieved_level} cannot publish dimensions reserved for a "
            f"higher or type-specific level: {sorted(drift)}"
        )


def _required_support_classes(
    review: Mapping[str, Any],
    achieved_level: str,
) -> set[str]:
    required = {"boundary"}
    if achieved_level in {"L1", "L2", "EXCLUDED"}:
        required.add("ownership")
    if achieved_level in {"L1", "L2"}:
        required.add("immediate_references")
    if achieved_level == "L2":
        required.add("semantic_io")
        native_lua_boundary = _native_lua_boundary(
            review["native_lua_boundary"], "review.native_lua_boundary"
        )
        if native_lua_boundary["state"] == "none":
            required.add("native_lua_boundary")
        elif native_lua_boundary["state"] == "roles":
            required.add("native_lua_role")
        else:  # pragma: no cover - _derive_level excludes unknown for L2
            raise NativeFunctionAccountingError(
                "L2 requires a reviewed native/Lua boundary state"
            )
    if achieved_level == "EXCLUDED":
        required.add("exclusion")
    return required


def _normalize_claims(
    registry: Mapping[str, Any],
    *,
    functions_by_entry: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
    executable: Path,
    inventory: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    verification_cache: dict[tuple[str, str], Mapping[str, Any]],
    atlas_identity: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    previous_entry = ""
    for index, raw_claim in enumerate(_array(registry.get("claims"), "registry.claims")):
        label = f"registry.claims[{index}]"
        claim = _mapping(raw_claim, label)
        _exact_keys(
            claim,
            {
                "entry_rva",
                "atlas_record_sha256",
                "claimed_level",
                "boundary_status",
                "ownership",
                "subsystem",
                "purpose",
                "inputs_outputs",
                "native_lua_boundary",
                "reference_status",
                "exclusion",
                "evidence_class",
                "evidence",
            },
            label,
        )
        entry = _rva(claim["entry_rva"], f"{label}.entry_rva")
        if entry <= previous_entry:
            raise NativeFunctionAccountingError(
                "registry claims must have unique increasing entry RVAs"
            )
        previous_entry = entry
        function = functions_by_entry.get(entry)
        if function is None:
            raise NativeFunctionAccountingError(
                f"registry claim references an unknown atlas entry: {entry}"
            )
        expected_record_sha256 = atlas_record_sha256(function)
        if (
            _sha256(
                claim["atlas_record_sha256"],
                f"{label}.atlas_record_sha256",
            )
            != expected_record_sha256
        ):
            raise NativeFunctionAccountingError(
                f"registry claim has a stale atlas record identity: {entry}"
            )
        boundary_status = _text(
            claim["boundary_status"], f"{label}.boundary_status"
        )
        ownership = _text(claim["ownership"], f"{label}.ownership")
        subsystem = _text(claim["subsystem"], f"{label}.subsystem")
        native_lua_boundary = _native_lua_boundary(
            claim["native_lua_boundary"], f"{label}.native_lua_boundary"
        )
        reference_status = _text(
            claim["reference_status"], f"{label}.reference_status"
        )
        exclusion = _text(claim["exclusion"], f"{label}.exclusion")
        evidence_class = _text(
            claim["evidence_class"], f"{label}.evidence_class"
        )
        claimed_level = _text(
            claim["claimed_level"], f"{label}.claimed_level"
        )
        allowed_checks = (
            (boundary_status, BOUNDARY_STATUSES, "boundary_status"),
            (ownership, OWNERSHIPS, "ownership"),
            (subsystem, SUBSYSTEMS, "subsystem"),
            (reference_status, REFERENCE_STATUSES, "reference_status"),
            (exclusion, EXCLUSIONS, "exclusion"),
            (evidence_class, EVIDENCE_CLASSES, "evidence_class"),
            (claimed_level, CLAIMED_LEVELS, "claimed_level"),
        )
        for observed, allowed, field in allowed_checks:
            if observed not in allowed:
                raise NativeFunctionAccountingError(
                    f"{label}.{field} is unsupported: {observed}"
                )
        review = {
            "reviewed": True,
            "boundary_status": boundary_status,
            "ownership": ownership,
            "subsystem": subsystem,
            "purpose": _optional_text(claim["purpose"], f"{label}.purpose"),
            "inputs_outputs": _optional_text(
                claim["inputs_outputs"], f"{label}.inputs_outputs"
            ),
            "native_lua_boundary": native_lua_boundary,
            "reference_status": reference_status,
            "exclusion": exclusion,
            "evidence_class": evidence_class,
        }
        achieved_level = _derive_level(review)
        if claimed_level != achieved_level:
            raise NativeFunctionAccountingError(
                f"{entry} claimed {claimed_level} but derives {achieved_level}"
            )
        _validate_authoritative_dimensions(review, achieved_level)
        expected_evidence_review = {
            "entry_rva": entry,
            "atlas_record_sha256": expected_record_sha256,
            **{
                field: review[field]
                for field in _REVIEW_RECORD_FIELDS
                if field not in {
                    "entry_rva",
                    "atlas_record_sha256",
                    "rationale",
                    "support",
                }
            },
        }
        review["evidence"] = _evidence_references(
            claim["evidence"],
            label=f"{label}.evidence",
            repo_root=repo_root,
            executable=executable,
            inventory=inventory,
            program_facts=program_facts,
            verification_cache=verification_cache,
            atlas_identity=atlas_identity,
            entry_rva=entry,
            atlas_record_identity=expected_record_sha256,
            expected_review=expected_evidence_review,
            required_support_classes=_required_support_classes(review, achieved_level),
        )
        review["achieved_level"] = achieved_level
        claims[entry] = review
    return claims


def _default_review() -> dict[str, Any]:
    return {
        "reviewed": False,
        "boundary_status": "atlas_analysis_only",
        "ownership": "unknown",
        "subsystem": "unknown",
        "purpose": None,
        "inputs_outputs": None,
        "native_lua_boundary": _unknown_native_lua_boundary(),
        "reference_status": "atlas_declared_direct_only",
        "exclusion": "none",
        "evidence_class": "unresolved",
        "evidence": [],
        "achieved_level": "L0",
    }


def _count_partition(
    counter: Counter[str],
    *,
    field: str,
    categories: set[str],
) -> list[dict[str, Any]]:
    unknown = set(counter) - categories
    if unknown:
        raise NativeFunctionAccountingError(
            f"{field} partition has unsupported categories: {sorted(unknown)}"
        )
    return [
        {field: category, "functions": counter[category]}
        for category in sorted(categories)
    ]


def _validate_registry(
    registry: Mapping[str, Any],
    atlas_sha256: str,
) -> None:
    _validate_json_tree(registry, "registry")
    _exact_keys(
        registry,
        {"schema_version", "analysis_kind", "atlas_canonical_sha256", "claims"},
        "registry",
    )
    if (
        type(registry["schema_version"]) is not int
        or registry["schema_version"] != SCHEMA_VERSION
    ):
        raise NativeFunctionAccountingError("unsupported review registry schema")
    if registry["analysis_kind"] != REGISTRY_KIND:
        raise NativeFunctionAccountingError("review registry kind differs")
    if (
        _sha256(
            registry["atlas_canonical_sha256"],
            "registry.atlas_canonical_sha256",
        )
        != atlas_sha256
    ):
        raise NativeFunctionAccountingError(
            "review registry is pinned to a different atlas"
        )
    _array(registry["claims"], "registry.claims")


def _assert_publication_safe(value: Any, label: str = "artifact") -> None:
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is str:
        if len(value) > MAX_TEXT or "\0" in value:
            raise NativeFunctionAccountingError(
                f"{label} contains an unbounded string"
            )
        is_json_pointer = label.endswith(".json_pointer")
        if re.search(r"(?:^|\s)[A-Za-z]:[\\/]", value) or (
            not is_json_pointer and value.startswith(("/", "\\\\"))
        ):
            raise NativeFunctionAccountingError(
                f"{label} contains an absolute path"
            )
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _assert_publication_safe(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str or len(key) > 128:
                raise NativeFunctionAccountingError(
                    f"{label} has an invalid field name"
                )
            _assert_publication_safe(item, f"{label}.{key}")
        return
    raise NativeFunctionAccountingError(
        f"{label} contains a non-publication value"
    )


def build_native_function_accounting(
    executable: Path,
    program_facts: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Build an exact one-to-one review overlay over a verified native atlas."""
    _validate_json_tree(program_facts, "program_facts")
    _validate_json_tree(inventory, "inventory")
    try:
        atlas_verification = validate_program_facts(
            executable,
            program_facts,
            inventory=inventory,
        )
    except ProgramFactsError as exc:
        raise NativeFunctionAccountingError(
            f"program-facts prerequisite failed verification: {exc}"
        ) from exc
    atlas_sha256 = _canonical_sha256(program_facts)
    if atlas_verification.get("evidence_sha256") != atlas_sha256:
        raise NativeFunctionAccountingError(
            "program-facts verifier canonical identity disagrees"
        )
    _validate_registry(registry, atlas_sha256)

    atlas_identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    raw_functions = _array(program_facts.get("functions"), "program_facts.functions")
    functions_by_entry: dict[str, Mapping[str, Any]] = {}
    previous_entry = ""
    for index, raw_function in enumerate(raw_functions):
        function = _mapping(raw_function, f"program_facts.functions[{index}]")
        entry = _rva(function.get("entry_rva"), f"function[{index}].entry_rva")
        if entry <= previous_entry or entry in functions_by_entry:
            raise NativeFunctionAccountingError(
                "program-facts functions are not unique and sorted"
            )
        previous_entry = entry
        functions_by_entry[entry] = function

    upstream_verification_cache: dict[
        tuple[str, str], Mapping[str, Any]
    ] = {}
    claims = _normalize_claims(
        registry,
        functions_by_entry=functions_by_entry,
        repo_root=repo_root,
        executable=executable,
        inventory=inventory,
        program_facts=program_facts,
        verification_cache=upstream_verification_cache,
        atlas_identity=atlas_identity,
    )
    calls = _array(
        program_facts.get("ghidra_declared_direct_calls"),
        "program_facts.ghidra_declared_direct_calls",
    )
    outgoing: Counter[str] = Counter()
    incoming: Counter[str] = Counter()
    calls_without_target_entry = 0
    for index, raw_call in enumerate(calls):
        call = _mapping(raw_call, f"program_facts call {index}")
        source = _rva(call.get("source_entry_rva"), f"call[{index}].source")
        outgoing[source] += 1
        target_entry = call.get("target_entry_rva")
        if target_entry is None:
            calls_without_target_entry += 1
        else:
            incoming[_rva(target_entry, f"call[{index}].target_entry")] += 1

    normalized_functions: list[dict[str, Any]] = []
    body_groups: dict[str, list[str]] = {}
    level_counts: Counter[str] = Counter()
    ownership_counts: Counter[str] = Counter()
    subsystem_counts: Counter[str] = Counter()
    boundary_status_counts: Counter[str] = Counter()
    native_lua_boundary_state_counts: Counter[str] = Counter()
    native_lua_role_counts: Counter[str] = Counter()
    reference_status_counts: Counter[str] = Counter()
    exclusion_counts: Counter[str] = Counter()
    evidence_class_counts: Counter[str] = Counter()
    name_source_counts: Counter[str] = Counter()
    reviewed_count = 0
    thunk_entries: list[str] = []
    for entry, function in functions_by_entry.items():
        body_sha256 = _sha256(function.get("body_sha256"), f"{entry}.body_sha256")
        body_groups.setdefault(body_sha256, []).append(entry)
        name_source = _text(function.get("name_source"), f"{entry}.name_source")
        namespace = _text(
            function.get("namespace"),
            f"{entry}.namespace",
            allow_empty=True,
        )
        thunk = function.get("thunk")
        if type(thunk) is not bool:
            raise NativeFunctionAccountingError(f"{entry}.thunk must be boolean")
        if thunk:
            thunk_entries.append(entry)
        review = claims.get(entry, _default_review())
        reviewed_count += int(review["reviewed"])
        level_counts[review["achieved_level"]] += 1
        ownership_counts[review["ownership"]] += 1
        subsystem_counts[review["subsystem"]] += 1
        boundary_status_counts[review["boundary_status"]] += 1
        native_lua_boundary = _native_lua_boundary(
            review["native_lua_boundary"], "review.native_lua_boundary"
        )
        native_lua_boundary_state_counts[native_lua_boundary["state"]] += 1
        for role in native_lua_boundary["roles"]:
            native_lua_role_counts[role] += 1
        reference_status_counts[review["reference_status"]] += 1
        exclusion_counts[review["exclusion"]] += 1
        evidence_class_counts[review["evidence_class"]] += 1
        name_source_counts[name_source] += 1
        normalized_functions.append(
            {
                "entry_rva": entry,
                "atlas_record_sha256": atlas_record_sha256(function),
                "ghidra_analysis": {
                    "name_source": name_source,
                    "namespace": namespace,
                    "thunk": thunk,
                    "declared_call_records_out": outgoing[entry],
                    "declared_call_records_in": incoming[entry],
                },
                "review": review,
            }
        )

    repeated_groups = [
        {"body_sha256": sha256, "entry_rvas": entries}
        for sha256, entries in sorted(body_groups.items())
        if len(entries) > 1
    ]
    atlas_summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(atlas_identity),
        "atlas": {
            "analysis_kind": program_facts.get("analysis_kind"),
            "canonical_sha256": atlas_sha256,
            "ghidra_facts_sha256": _mapping(
                program_facts.get("ghidra"), "program_facts.ghidra"
            ).get("facts_sha256"),
            "function_count": atlas_summary.get("function_count"),
            "body_range_count": atlas_summary.get("body_range_count"),
            "unique_function_body_bytes": atlas_summary.get(
                "unique_function_body_bytes"
            ),
            "executable_file_bytes": atlas_summary.get("executable_file_bytes"),
            "coverage_basis_points": atlas_summary.get(
                "ghidra_function_discovery_coverage_basis_points"
            ),
            "declared_direct_call_records": atlas_summary.get(
                "ghidra_declared_direct_internal_call_count"
            ),
            "omitted_call_targets": atlas_summary.get("omitted_call_target_count"),
        },
        "registry": {
            "analysis_kind": registry.get("analysis_kind"),
            "canonical_sha256": _canonical_sha256(registry),
            "claim_count": len(claims),
        },
        "functions": normalized_functions,
        "review_candidates": {
            "affects_review_or_level": False,
            "ghidra_thunk_flagged_entry_rvas": thunk_entries,
            "repeated_body_groups": repeated_groups,
        },
        "method": {
            "atlas_prerequisite_exactly_verified": True,
            "one_record_per_atlas_function": True,
            "default_level": "L0",
            "promotion_source": (
                "only sorted registry claims whose exact-dimensional review "
                "records have typed support and allowlisted upstream adapters"
            ),
            "registered_upstream_analysis_adapters": sorted(_UPSTREAM_ADAPTERS),
            "promotions_fail_closed_without_an_upstream_adapter": True,
            "heuristics_affect_review_or_level": False,
            "native_lua_boundary_model": (
                "A boundary has state unknown, none, or roles. Roles are sorted "
                "positive facts and may overlap; their absence is not inferred "
                "unless state is reviewed none."
            ),
            "native_lua_role_support": (
                "Each reviewed positive role needs one exact native_lua_role "
                "support atom; the atom set must equal the reviewed role set."
            ),
            "level_rules": {
                "L0": "exact atlas location and body identity only",
                "L1": (
                    "reviewed exact boundary, resolved ownership, reviewed "
                    "immediate references, and fact/inference evidence"
                ),
                "L2": (
                    "L1 plus first-party subsystem, purpose, inputs/outputs, "
                    "and a reviewed native/Lua boundary state with positive, "
                    "non-exclusive roles where applicable"
                ),
                "EXCLUDED": (
                    "reviewed exact boundary and fact evidence for a supported "
                    "third-party or compiler-runtime exclusion"
                ),
            },
            "unsupported_exclusion_proofs": [
                "data_only",
                "duplicate_thunk",
                "unreachable",
            ],
            "not_claimed": [
                "complete native-function discovery beyond the Ghidra atlas",
                "independent decoding or completeness of Ghidra-declared calls",
                "per-function accounting for computed or unmapped calls",
                "ownership or semantics from names, namespaces, addresses, sizes, "
                "thunk flags, or repeated bodies",
                "automatic promotion of focused native-region artifacts",
                "L3 control-flow or state semantics",
            ],
        },
        "summary": {
            "atlas_functions": len(normalized_functions),
            "reviewed_functions": reviewed_count,
            "unreviewed_functions": len(normalized_functions) - reviewed_count,
            "level_L0": level_counts["L0"],
            "level_L1": level_counts["L1"],
            "level_L2": level_counts["L2"],
            "reviewed_exclusions": level_counts["EXCLUDED"],
            "ownership_unknown": ownership_counts["unknown"],
            "subsystem_unknown": subsystem_counts["unknown"],
            "level_counts": _count_partition(
                level_counts,
                field="level",
                categories=CLAIMED_LEVELS,
            ),
            "boundary_status_counts": _count_partition(
                boundary_status_counts,
                field="boundary_status",
                categories=BOUNDARY_STATUSES | {"atlas_analysis_only"},
            ),
            "ownership_counts": _count_partition(
                ownership_counts,
                field="ownership",
                categories=OWNERSHIPS,
            ),
            "subsystem_counts": _count_partition(
                subsystem_counts,
                field="subsystem",
                categories=SUBSYSTEMS,
            ),
            "native_lua_boundary_state_counts": _count_partition(
                native_lua_boundary_state_counts,
                field="native_lua_boundary_state",
                categories=NATIVE_LUA_BOUNDARY_STATES,
            ),
            "native_lua_role_counts": [
                {"native_lua_role": role, "functions": native_lua_role_counts[role]}
                for role in sorted(NATIVE_LUA_ROLES)
            ],
            "native_lua_roles_are_nonexclusive": True,
            "reference_status_counts": _count_partition(
                reference_status_counts,
                field="reference_status",
                categories=REFERENCE_STATUSES | {"atlas_declared_direct_only"},
            ),
            "exclusion_counts": _count_partition(
                exclusion_counts,
                field="exclusion",
                categories=EXCLUSIONS,
            ),
            "evidence_class_counts": _count_partition(
                evidence_class_counts,
                field="evidence_class",
                categories=EVIDENCE_CLASSES | {"unresolved"},
            ),
            "ghidra_thunk_flagged": len(thunk_entries),
            "repeated_body_groups": len(repeated_groups),
            "functions_in_repeated_body_groups": sum(
                len(group["entry_rvas"]) for group in repeated_groups
            ),
            "name_source_counts": [
                {"name_source": key, "functions": name_source_counts[key]}
                for key in sorted(name_source_counts)
            ],
            "ghidra_declared_call_records": len(calls),
            "declared_calls_without_target_entry": calls_without_target_entry,
            "omitted_call_targets": atlas_summary.get("omitted_call_target_count"),
            "schema_violations": 0,
        },
    }
    if sum(level_counts.values()) != len(normalized_functions):
        raise NativeFunctionAccountingError("function level partition is incomplete")
    for label, counter in (
        ("boundary status", boundary_status_counts),
        ("ownership", ownership_counts),
        ("subsystem", subsystem_counts),
        ("native/Lua boundary state", native_lua_boundary_state_counts),
        ("reference status", reference_status_counts),
        ("exclusion", exclusion_counts),
        ("evidence class", evidence_class_counts),
    ):
        if sum(counter.values()) != len(normalized_functions):
            raise NativeFunctionAccountingError(
                f"function {label} partition is incomplete"
            )
    _assert_publication_safe(result)
    return result


def validate_native_function_accounting(
    executable: Path,
    evidence: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare a native accounting artifact."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_function_accounting(
        executable,
        program_facts,
        registry,
        inventory=inventory,
        repo_root=repo_root,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeFunctionAccountingError(
            "evidence does not match the exact rebuilt accounting overlay"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": rebuilt["build_identity"],
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": rebuilt["summary"],
    }


def encode_native_function_accounting(value: Mapping[str, Any]) -> str:
    """Encode normalized accounting evidence with deterministic formatting."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
