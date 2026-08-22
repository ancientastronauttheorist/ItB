"""Deterministic data capsule and startup request for callback trials."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.callback_hook_plan import (
    CALLBACK_CONTROLLER_VERSION,
    CALLBACK_KINDS,
    validate_callback_hook_plan,
)
from src.observatory.raw_trace import arm_packet_sha256
from src.observatory.runtime_callback_bindings import (
    callback_binding_manifest_sha256,
    validate_runtime_callback_bindings,
)


CAPSULE_SCHEMA_VERSION = 1
CAPSULE_KIND = "observatory_callback_trial_capsule"
CAPSULE_PREFIX = "itb_observatory_callback_capsule_"
CAPSULE_SUFFIX = ".lua"
REQUEST_FILENAME = "itb_observatory_callback_trial.request"
REQUEST_TOKEN = "observatory-callback-trial-request/1"
REQUEST_TOKEN_WITH_CONTINUE = "observatory-callback-trial-request/2"
MAX_CAPSULE_BYTES = 4 * 1024 * 1024
MAX_SAFE_LUA_INTEGER = (1 << 53) - 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NONCE_RE = re.compile(r"^[0-9a-f]{32,64}$")
_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_CONDITIONS = frozenset({"control", "exact_hook"})
_CAPTURE_TRACKS = frozenset({"owner_local_modified", "pristine_reference"})
_BUILD_JOIN_FIELDS = (
    "platform",
    "architecture",
    "executable_sha256",
    "build_id",
    "depot_manifest",
    "scripts_revision_sha256",
    "maps_revision_sha256",
)
_CAPSULE_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "capture_track",
        "arm_packet_sha256",
        "packet",
        "callback_family",
        "binding_manifest_sha256",
        "binding_manifest",
        "callback_join_sha256",
        "callback_join",
        "expected_save",
    }
)
_EXPECTED_SAVE_FIELDS = frozenset(
    {"mission_id", "mission_slot", "turn", "master_seed", "region_id", "ai_seed"}
)


class CallbackTrialCapsuleError(RuntimeError):
    """Raised when a callback trial capsule or startup request is unsafe."""


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or abs(value) > MAX_SAFE_LUA_INTEGER:
        raise CallbackTrialCapsuleError(f"{label} must be a Lua-safe integer")
    if minimum is not None and value < minimum:
        raise CallbackTrialCapsuleError(f"{label} must be >= {minimum}")
    return value


def _text(value: Any, label: str, *, limit: int = 256) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > limit:
        raise CallbackTrialCapsuleError(f"{label} must be bounded non-empty text")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise CallbackTrialCapsuleError(f"{label} must be lowercase SHA-256")
    return value


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise CallbackTrialCapsuleError(f"{label} fields are invalid")
    return value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError) as exc:
        raise CallbackTrialCapsuleError(f"value is not canonical JSON: {exc}") from exc


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        _json_copy(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def _type_safe_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _type_safe_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_safe_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _validate_packet(
    packet: Any,
    binding_manifest: Mapping[str, Any],
    callback_join: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    if not isinstance(packet, Mapping):
        raise CallbackTrialCapsuleError("arm packet must be an object")
    normalized = _json_copy(packet)
    try:
        digest = arm_packet_sha256(normalized)
    except Exception as exc:
        raise CallbackTrialCapsuleError(f"invalid arm packet: {exc}") from exc
    manifest = normalized.get("manifest")
    plan = normalized.get("hook_plan")
    build = normalized.get("build_identity")
    if (
        normalized.get("arm_packet_schema_version") != 1
        or not isinstance(manifest, Mapping)
        or not isinstance(plan, list)
        or not isinstance(build, Mapping)
        or manifest.get("controller_version") != CALLBACK_CONTROLLER_VERSION
        or manifest.get("expected_phase") != "combat_enemy"
    ):
        raise CallbackTrialCapsuleError("arm packet is not a callback controller packet")
    installed = {
        entry.get("event_kind")
        for entry in plan
        if isinstance(entry, Mapping) and entry.get("status") == "installed"
    }
    if len(installed) != 1 or next(iter(installed)) not in CALLBACK_KINDS:
        raise CallbackTrialCapsuleError("arm packet must install exactly one callback family")
    family = next(iter(installed))
    try:
        validate_callback_hook_plan(
            plan,
            binding_manifest,
            callback_join,
            installed_kind=family,
        )
    except Exception as exc:
        raise CallbackTrialCapsuleError(f"callback hook plan is not exact: {exc}") from exc
    join_build = callback_join.get("build_identity")
    if not isinstance(join_build, Mapping) or any(
        not _type_safe_equal(join_build.get(field), build.get(field))
        for field in _BUILD_JOIN_FIELDS
    ):
        raise CallbackTrialCapsuleError("callback join does not match arm build identity")
    capture_id = _text(manifest.get("capture_id"), "manifest.capture_id", limit=128)
    if _CAPTURE_ID_RE.fullmatch(capture_id) is None:
        raise CallbackTrialCapsuleError("manifest.capture_id is invalid")
    nonce = _text(manifest.get("arm_nonce"), "manifest.arm_nonce", limit=64)
    if _NONCE_RE.fullmatch(nonce) is None:
        raise CallbackTrialCapsuleError("manifest.arm_nonce is invalid")
    _integer(manifest.get("checkpoint_seq"), "manifest.checkpoint_seq", minimum=0)
    _integer(manifest.get("expected_turn"), "manifest.expected_turn", minimum=0)
    _integer(manifest.get("master_seed"), "manifest.master_seed")
    for field in (
        "controller_sha256",
        "installed_modloader_sha256",
        "build_identity_sha256",
        "config_sha256",
        "hook_coverage_sha256",
        "timeline_fingerprint",
        "ai_seed_fingerprint",
    ):
        _sha256(manifest.get(field), f"manifest.{field}")
    return normalized, family


def build_callback_trial_capsule(
    arm_packet: Mapping[str, Any],
    binding_manifest: Mapping[str, Any],
    callback_join: Mapping[str, Any],
    *,
    capture_track: str,
    expected_mission_slot: str,
    expected_ai_seed: int,
) -> dict[str, Any]:
    """Build a strict data-only capsule for one natural callback family."""
    if capture_track not in _CAPTURE_TRACKS:
        raise CallbackTrialCapsuleError("capture_track is invalid")
    try:
        bindings = validate_runtime_callback_bindings(binding_manifest)
    except Exception as exc:
        raise CallbackTrialCapsuleError(f"invalid binding manifest: {exc}") from exc
    if not isinstance(callback_join, Mapping):
        raise CallbackTrialCapsuleError("callback join must be an object")
    join = _json_copy(callback_join)
    packet, family = _validate_packet(arm_packet, bindings, join)
    manifest = packet["manifest"]
    return {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "kind": CAPSULE_KIND,
        "capture_track": capture_track,
        "arm_packet_sha256": arm_packet_sha256(packet),
        "packet": packet,
        "callback_family": family,
        "binding_manifest_sha256": callback_binding_manifest_sha256(bindings),
        "binding_manifest": bindings,
        "callback_join_sha256": _canonical_sha256(join),
        "callback_join": join,
        "expected_save": {
            "mission_id": manifest["expected_mission_id"],
            "mission_slot": _text(
                expected_mission_slot, "expected_mission_slot", limit=128
            ),
            "turn": manifest["expected_turn"],
            "master_seed": manifest["master_seed"],
            "region_id": manifest["region_id"],
            "ai_seed": _integer(expected_ai_seed, "expected_ai_seed"),
        },
    }


def _lua_string(value: str) -> str:
    pieces = ['"']
    for byte in value.encode("utf-8", errors="strict"):
        if byte == 34:
            pieces.append(r'\"')
        elif byte == 92:
            pieces.append(r"\\")
        elif 32 <= byte <= 126:
            pieces.append(chr(byte))
        else:
            pieces.append(f"\\{byte:03d}")
    pieces.append('"')
    return "".join(pieces)


def _lua_transport(value: Any, *, path: str = "capsule") -> Any:
    if value is None:
        if path == "capsule.packet.build_identity.architectures":
            return None
        raise CallbackTrialCapsuleError(f"{path} contains unsupported JSON null")
    if type(value) in {bool, int, str}:
        if type(value) is int:
            _integer(value, path)
        return value
    if isinstance(value, list):
        return [
            _lua_transport(child, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if type(key) is not str:
                raise CallbackTrialCapsuleError(f"{path} contains a non-string key")
            child_path = f"{path}.{key}"
            child = value[key]
            if child is None and child_path == "capsule.packet.build_identity.architectures":
                continue
            result[key] = _lua_transport(child, path=child_path)
        return result
    raise CallbackTrialCapsuleError(
        f"{path} contains unsupported type {type(value).__name__}"
    )


def _render_lua(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return _lua_string(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        children = [
            " " * (indent + 2) + _render_lua(child, indent + 2) for child in value
        ]
        return "{\n" + ",\n".join(children) + "\n" + prefix + "}"
    if isinstance(value, Mapping):
        if not value:
            return "{}"
        children = [
            " " * (indent + 2)
            + "["
            + _lua_string(key)
            + "] = "
            + _render_lua(value[key], indent + 2)
            for key in sorted(value)
        ]
        return "{\n" + ",\n".join(children) + "\n" + prefix + "}"
    raise CallbackTrialCapsuleError("cannot render unsupported Lua value")


def render_callback_trial_capsule(capsule: Mapping[str, Any]) -> str:
    """Render a previously built capsule as deterministic data-only Lua."""
    capsule = _exact(capsule, _CAPSULE_FIELDS, "capsule")
    expected = _exact(capsule["expected_save"], _EXPECTED_SAVE_FIELDS, "expected_save")
    rebuilt = build_callback_trial_capsule(
        capsule["packet"],
        capsule["binding_manifest"],
        capsule["callback_join"],
        capture_track=capsule["capture_track"],
        expected_mission_slot=expected["mission_slot"],
        expected_ai_seed=expected["ai_seed"],
    )
    if not _type_safe_equal(_json_copy(capsule), rebuilt):
        raise CallbackTrialCapsuleError("capsule does not match its validated inputs")
    transported = _lua_transport(_json_copy(capsule))
    rendered = (
        "-- Generated data-only ITB Observatory callback trial capsule.\n"
        "return "
        + _render_lua(transported)
        + "\n"
    )
    if len(rendered.encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise CallbackTrialCapsuleError("rendered capsule exceeds its byte cap")
    return rendered


def callback_trial_capsule_sha256(rendered: str) -> str:
    if type(rendered) is not str:
        raise CallbackTrialCapsuleError("rendered capsule must be text")
    payload = rendered.encode("utf-8", errors="strict")
    if len(payload) > MAX_CAPSULE_BYTES:
        raise CallbackTrialCapsuleError("rendered capsule exceeds its byte cap")
    return hashlib.sha256(payload).hexdigest()


def callback_trial_capsule_filename(digest: str) -> str:
    return f"{CAPSULE_PREFIX}{_sha256(digest, 'capsule digest')}{CAPSULE_SUFFIX}"


def write_callback_trial_capsule(rendered: str, *, root: Path) -> Path:
    payload = rendered.encode("utf-8", errors="strict")
    digest = callback_trial_capsule_sha256(rendered)
    root = Path(os.path.abspath(Path(root).expanduser()))
    root.mkdir(parents=True, exist_ok=True)
    path = root / callback_trial_capsule_filename(digest)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CallbackTrialCapsuleError(
            f"immutable capsule already exists: {path.name}"
        ) from exc
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    if path.read_bytes() != payload:
        raise CallbackTrialCapsuleError("capsule verification failed")
    return path


def render_callback_trial_request(
    *,
    condition: str,
    activation_nonce: str,
    capsule_sha256: str,
    continue_helper_sha256: str | None = None,
) -> bytes:
    if condition not in _CONDITIONS:
        raise CallbackTrialCapsuleError("condition must be control or exact_hook")
    if type(activation_nonce) is not str or _NONCE_RE.fullmatch(activation_nonce) is None:
        raise CallbackTrialCapsuleError("activation nonce is invalid")
    _sha256(capsule_sha256, "capsule_sha256")
    if continue_helper_sha256 is not None:
        _sha256(continue_helper_sha256, "continue_helper_sha256")
        return (
            f"{REQUEST_TOKEN_WITH_CONTINUE}\n"
            f"condition={condition}\n"
            f"activation_nonce={activation_nonce}\n"
            f"capsule_sha256={capsule_sha256}\n"
            f"continue_helper_sha256={continue_helper_sha256}\n"
        ).encode("ascii")
    return (
        f"{REQUEST_TOKEN}\n"
        f"condition={condition}\n"
        f"activation_nonce={activation_nonce}\n"
        f"capsule_sha256={capsule_sha256}\n"
    ).encode("ascii")


def arm_callback_trial_request(
    *,
    bridge_root: Path,
    condition: str,
    activation_nonce: str,
    capsule_sha256: str,
    continue_helper_sha256: str | None = None,
) -> Path:
    payload = render_callback_trial_request(
        condition=condition,
        activation_nonce=activation_nonce,
        capsule_sha256=capsule_sha256,
        continue_helper_sha256=continue_helper_sha256,
    )
    root = Path(os.path.abspath(Path(bridge_root).expanduser()))
    if not root.is_dir():
        raise CallbackTrialCapsuleError("bridge root must already exist")
    path = root / REQUEST_FILENAME
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CallbackTrialCapsuleError("callback trial request is already armed") from exc
    return path
