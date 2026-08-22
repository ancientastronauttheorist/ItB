"""Deterministic data capsule and request for one-shot Lua RNG trials."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.raw_trace import arm_packet_sha256
from src.observatory.trace_codec import (
    EVENT_KINDS,
    TraceCodecError,
    build_identity_sha256,
    hook_coverage_sha256,
    validate_build_identity,
    validate_hook_coverage,
)


CAPSULE_SCHEMA_VERSION = 2
CAPSULE_KIND = "observatory_rng_trial_capsule"
RNG_SEED_HELPER_VERSION = "observatory-rng-seed-helper/1"
CAPSULE_PREFIX = "itb_observatory_rng_capsule_"
CAPSULE_SUFFIX = ".lua"
REQUEST_FILENAME = "itb_observatory_rng_trial.request"
REQUEST_TOKEN = "observatory-rng-trial-request/1"
MAX_CAPSULE_BYTES = 2 * 1024 * 1024
MAX_SAFE_LUA_INTEGER = (1 << 53) - 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_NONCE_RE = re.compile(r"^[0-9a-f]{32,64}$")
_RVA_RE = re.compile(r"^0x[0-9a-f]{8}$")
_CONDITIONS = frozenset({"control", "exact_hook"})
_CAPTURE_TRACKS = frozenset({"owner_local_modified", "pristine_reference"})
_PROBE_KINDS = frozenset({"random_int", "random_bool"})
_CAPSULE_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "capture_track",
        "arm_packet_sha256",
        "packet",
        "probe",
        "rng_control",
        "expected_save",
    }
)
_RNG_CONTROL_FIELDS = frozenset(
    {
        "kind",
        "seed",
        "expected_result",
        "helper_version",
        "helper_sha256",
        "executable_sha256",
        "build_id",
        "architecture",
        "rng_seed_rva",
        "rng_seed_region_sha256",
    }
)


class RngTrialCapsuleError(RuntimeError):
    """Raised when an RNG trial capsule or activation request is unsafe."""


def _exact_fields(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RngTrialCapsuleError(f"{label} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing:
        raise RngTrialCapsuleError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RngTrialCapsuleError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or abs(value) > MAX_SAFE_LUA_INTEGER:
        raise RngTrialCapsuleError(f"{label} must be a Lua-safe integer")
    if minimum is not None and value < minimum:
        raise RngTrialCapsuleError(f"{label} must be >= {minimum}")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise RngTrialCapsuleError(f"{label} must be lowercase SHA-256")
    return value


def _text(value: Any, label: str, *, limit: int = 256) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > limit:
        raise RngTrialCapsuleError(f"{label} must be bounded non-empty text")
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
        raise RngTrialCapsuleError(f"value is not canonical JSON: {exc}") from exc


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise RngTrialCapsuleError(f"value is not canonical JSON: {exc}") from exc


def _msvc_first_draw(seed: int) -> int:
    seed = _integer(seed, "native_seed", minimum=0)
    if seed > 0x7FFFFFFF:
        raise RngTrialCapsuleError("native_seed exceeds signed 32-bit range")
    state = (seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF
    return (state >> 16) & 0x7FFF


def msvc_random_int_first(seed: int, upper_bound: int) -> int:
    """Return the pinned Windows build's first random_int result after seeding."""
    upper_bound = _integer(upper_bound, "probe_upper_bound", minimum=2)
    if upper_bound > 0x7FFFFFFF:
        raise RngTrialCapsuleError("probe_upper_bound exceeds signed 32-bit range")
    return _msvc_first_draw(seed) % upper_bound


def msvc_random_bool_first(seed: int, argument: int) -> bool:
    """Return the pinned Windows build's first one-argument random_bool result."""
    argument = _integer(argument, "probe_argument", minimum=1)
    if argument > 0x7FFFFFFF:
        raise RngTrialCapsuleError("probe_argument exceeds signed 32-bit range")
    return _msvc_first_draw(seed) % argument == 0


def _validate_rng_packet(packet: Any, probe_kind: str) -> dict[str, Any]:
    if type(probe_kind) is not str or probe_kind not in _PROBE_KINDS:
        raise RngTrialCapsuleError("probe_kind must be random_int or random_bool")
    if not isinstance(packet, Mapping):
        raise RngTrialCapsuleError("arm packet must be an object")
    try:
        packet_digest = arm_packet_sha256(packet)
    except Exception as exc:
        raise RngTrialCapsuleError(f"invalid arm packet: {exc}") from exc
    if packet.get("arm_packet_schema_version") != 1:
        raise RngTrialCapsuleError("unsupported arm packet schema")
    try:
        build_identity = validate_build_identity(packet.get("build_identity"))
    except TraceCodecError as exc:
        raise RngTrialCapsuleError(f"invalid arm build identity: {exc}") from exc
    manifest = packet.get("manifest")
    policy = packet.get("policy")
    trusted = packet.get("trusted")
    plan = packet.get("hook_plan")
    if not all(isinstance(value, Mapping) for value in (manifest, policy, trusted)):
        raise RngTrialCapsuleError(
            "arm packet manifest, policy, and trusted identity must be objects"
        )
    if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
        raise RngTrialCapsuleError("arm packet hook plan must be an array")
    coverage = []
    installed = []
    for entry in plan:
        if not isinstance(entry, Mapping):
            raise RngTrialCapsuleError("hook plan entries must be objects")
        if set(entry) != {
            "hook_id",
            "event_kind",
            "target",
            "target_kind",
            "status",
            "source_sha256",
        }:
            raise RngTrialCapsuleError("hook plan entry fields are invalid")
        coverage.append({key: value for key, value in entry.items() if key != "hook_id"})
        if entry.get("status") == "installed":
            installed.append(entry)
    try:
        normalized_coverage = validate_hook_coverage(coverage)
    except TraceCodecError as exc:
        raise RngTrialCapsuleError(f"invalid arm hook coverage: {exc}") from exc
    if {entry["event_kind"] for entry in normalized_coverage} != set(EVENT_KINDS):
        raise RngTrialCapsuleError("hook plan must cover every event family")
    if len(installed) != 1 or installed[0].get("event_kind") != probe_kind:
        raise RngTrialCapsuleError(
            f"capsule requires exactly one installed {probe_kind} hook"
        )
    if (
        installed[0].get("target") != f"_G.{probe_kind}"
        or installed[0].get("target_kind") != "lua_global"
    ):
        raise RngTrialCapsuleError(f"installed {probe_kind} target is not exact")
    if policy.get("expected_phase") != "combat_enemy" or policy.get(
        "allowed_kinds"
    ) != [probe_kind]:
        raise RngTrialCapsuleError(
            f"arm policy is not the {probe_kind} enemy-phase policy"
        )
    if hook_coverage_sha256(normalized_coverage) != manifest.get(
        "hook_coverage_sha256"
    ) or manifest.get("hook_coverage_sha256") != trusted.get(
        "hook_coverage_sha256"
    ):
        raise RngTrialCapsuleError("arm hook coverage digest mismatch")
    if build_identity_sha256(build_identity) != manifest.get(
        "build_identity_sha256"
    ) or manifest.get("build_identity_sha256") != trusted.get(
        "build_identity_sha256"
    ):
        raise RngTrialCapsuleError("arm build identity digest mismatch")
    for field in (
        "controller_sha256",
        "installed_modloader_sha256",
        "config_sha256",
    ):
        if manifest.get(field) != trusted.get(field):
            raise RngTrialCapsuleError(f"arm {field} trusted digest mismatch")
    for field in (
        "max_events",
        "max_events_per_turn",
        "max_event_bytes",
        "max_total_event_bytes",
        "max_attempts",
        "max_bundle_bytes",
        "allowed_kinds",
    ):
        if manifest.get(field) != policy.get(field):
            raise RngTrialCapsuleError(f"arm policy field {field} mismatch")
    capture_id = _text(manifest.get("capture_id"), "manifest.capture_id", limit=128)
    if _CAPTURE_ID_RE.fullmatch(capture_id) is None:
        raise RngTrialCapsuleError("manifest.capture_id is invalid")
    _integer(manifest.get("checkpoint_seq"), "manifest.checkpoint_seq", minimum=0)
    nonce = _text(manifest.get("arm_nonce"), "manifest.arm_nonce", limit=64)
    if _NONCE_RE.fullmatch(nonce) is None:
        raise RngTrialCapsuleError("manifest.arm_nonce is invalid")
    _text(manifest.get("expected_mission_id"), "manifest.expected_mission_id")
    _integer(manifest.get("expected_turn"), "manifest.expected_turn", minimum=0)
    _integer(manifest.get("master_seed"), "manifest.master_seed")
    _text(manifest.get("region_id"), "manifest.region_id", limit=128)
    for field in (
        "timeline_fingerprint",
        "ai_seed_fingerprint",
        "controller_sha256",
        "installed_modloader_sha256",
        "build_identity_sha256",
        "config_sha256",
        "hook_coverage_sha256",
    ):
        _sha256(manifest.get(field), f"manifest.{field}")
    normalized = _json_copy(packet)
    if arm_packet_sha256(normalized) != packet_digest:
        raise RngTrialCapsuleError("arm packet changed during normalization")
    return normalized


def build_rng_trial_capsule(
    arm_packet: Mapping[str, Any],
    *,
    capture_track: str,
    expected_mission_slot: str,
    expected_ai_seed: int,
    native_seed: int,
    seed_helper_sha256: str,
    rng_seed_rva: str,
    rng_seed_region_sha256: str,
    probe_kind: str = "random_int",
    probe_upper_bound: int = 65521,
    probe_argument: int = 2,
) -> dict[str, Any]:
    """Build the strict data-only capsule consumed by the Lua trial host."""
    packet = _validate_rng_packet(arm_packet, probe_kind)
    if capture_track not in _CAPTURE_TRACKS:
        raise RngTrialCapsuleError("capture_track is invalid")
    expected_mission_slot = _text(
        expected_mission_slot,
        "expected_mission_slot",
        limit=128,
    )
    expected_ai_seed = _integer(expected_ai_seed, "expected_ai_seed")
    if probe_kind == "random_int":
        probe_value = _integer(
            probe_upper_bound, "probe_upper_bound", minimum=2
        )
        if probe_value > 0x7FFFFFFF:
            raise RngTrialCapsuleError(
                "probe_upper_bound exceeds signed 32-bit range"
            )
        probe = {"kind": probe_kind, "upper_bound": probe_value}
        expected_result: int | bool = msvc_random_int_first(
            native_seed,
            probe_value,
        )
    else:
        probe_value = _integer(probe_argument, "probe_argument", minimum=1)
        if probe_value > 0x7FFFFFFF:
            raise RngTrialCapsuleError(
                "probe_argument exceeds signed 32-bit range"
            )
        probe = {"kind": probe_kind, "argument": probe_value}
        expected_result = msvc_random_bool_first(native_seed, probe_value)
    seed_helper_sha256 = _sha256(seed_helper_sha256, "seed_helper_sha256")
    rng_seed_region_sha256 = _sha256(
        rng_seed_region_sha256,
        "rng_seed_region_sha256",
    )
    if type(rng_seed_rva) is not str or _RVA_RE.fullmatch(rng_seed_rva) is None:
        raise RngTrialCapsuleError("rng_seed_rva must be a canonical 32-bit RVA")
    manifest = packet["manifest"]
    build_identity = packet["build_identity"]
    if (
        build_identity.get("platform") != "windows"
        or build_identity.get("architecture") != "x86"
    ):
        raise RngTrialCapsuleError("native seed control requires a Windows x86 build")
    return {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "kind": CAPSULE_KIND,
        "capture_track": capture_track,
        "arm_packet_sha256": arm_packet_sha256(packet),
        "packet": packet,
        "probe": probe,
        "rng_control": {
            "kind": "build_keyed_seed",
            "seed": native_seed,
            "expected_result": expected_result,
            "helper_version": RNG_SEED_HELPER_VERSION,
            "helper_sha256": seed_helper_sha256,
            "executable_sha256": build_identity["executable_sha256"],
            "build_id": build_identity["build_id"],
            "architecture": build_identity["architecture"],
            "rng_seed_rva": rng_seed_rva,
            "rng_seed_region_sha256": rng_seed_region_sha256,
        },
        "expected_save": {
            "mission_id": manifest["expected_mission_id"],
            "mission_slot": expected_mission_slot,
            "turn": manifest["expected_turn"],
            "master_seed": manifest["master_seed"],
            "region_id": manifest["region_id"],
            "ai_seed": expected_ai_seed,
        },
    }


def _lua_string(value: str) -> str:
    encoded = value.encode("utf-8", errors="strict")
    pieces: list[str] = ['"']
    for byte in encoded:
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
        raise RngTrialCapsuleError(f"{path} contains unsupported JSON null")
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
                raise RngTrialCapsuleError(f"{path} contains a non-string key")
            child = value[key]
            # Authoritative Windows build identities use JSON null for the
            # optional universal-architecture list. The Lua controller never
            # consumes this inner field, so omit that one transport-only null
            # instead of inventing a Lua sentinel with executable behavior.
            if child is None and path == "capsule.packet.build_identity" and key == "architectures":
                continue
            result[key] = _lua_transport(child, path=f"{path}.{key}")
        return result
    raise RngTrialCapsuleError(f"{path} contains unsupported type {type(value).__name__}")


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
            " " * (indent + 2) + _render_lua(child, indent + 2)
            for child in value
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
    raise RngTrialCapsuleError("cannot render unsupported Lua value")


def render_rng_trial_capsule(capsule: Mapping[str, Any]) -> str:
    """Render a validated capsule as deterministic data-only Lua source."""
    capsule = _exact_fields(capsule, _CAPSULE_FIELDS, "capsule")
    _exact_fields(capsule["rng_control"], _RNG_CONTROL_FIELDS, "capsule.rng_control")
    probe = capsule.get("probe")
    if not isinstance(probe, Mapping):
        raise RngTrialCapsuleError("capsule.probe must be an object")
    probe_kind = probe.get("kind")
    rebuilt = build_rng_trial_capsule(
        capsule["packet"],
        capture_track=capsule["capture_track"],
        expected_mission_slot=capsule["expected_save"]["mission_slot"],
        expected_ai_seed=capsule["expected_save"]["ai_seed"],
        native_seed=capsule["rng_control"]["seed"],
        seed_helper_sha256=capsule["rng_control"]["helper_sha256"],
        rng_seed_rva=capsule["rng_control"]["rng_seed_rva"],
        rng_seed_region_sha256=capsule["rng_control"][
            "rng_seed_region_sha256"
        ],
        probe_kind=probe_kind,
        probe_upper_bound=probe.get("upper_bound", 65521),
        probe_argument=probe.get("argument", 2),
    )
    if _canonical_json(_json_copy(capsule)) != _canonical_json(rebuilt):
        raise RngTrialCapsuleError("capsule does not match its validated inputs")
    transported = _lua_transport(rebuilt)
    rendered = (
        "-- Generated data-only ITB Observatory RNG trial capsule.\n"
        "return "
        + _render_lua(transported)
        + "\n"
    )
    if len(rendered.encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise RngTrialCapsuleError("rendered capsule exceeds its byte cap")
    return rendered


def rng_trial_capsule_sha256(rendered: str) -> str:
    if type(rendered) is not str:
        raise RngTrialCapsuleError("rendered capsule must be text")
    try:
        payload = rendered.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise RngTrialCapsuleError("rendered capsule is not UTF-8") from exc
    if len(payload) > MAX_CAPSULE_BYTES:
        raise RngTrialCapsuleError("rendered capsule exceeds its byte cap")
    return hashlib.sha256(payload).hexdigest()


def rng_trial_capsule_filename(digest: str) -> str:
    return f"{CAPSULE_PREFIX}{_sha256(digest, 'capsule digest')}{CAPSULE_SUFFIX}"


def write_rng_trial_capsule(rendered: str, *, root: Path) -> Path:
    """Create and verify one immutable content-addressed capsule."""
    payload = rendered.encode("utf-8", errors="strict")
    digest = rng_trial_capsule_sha256(rendered)
    root = Path(os.path.abspath(Path(root).expanduser()))
    root.mkdir(parents=True, exist_ok=True)
    path = root / rng_trial_capsule_filename(digest)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RngTrialCapsuleError("immutable capsule already exists") from exc
    except OSError as exc:
        try:
            path.unlink()
        except OSError:
            pass
        raise RngTrialCapsuleError(f"cannot publish capsule: {exc}") from exc
    if path.read_bytes() != payload:
        try:
            path.unlink()
        except OSError:
            pass
        raise RngTrialCapsuleError("published capsule failed verification")
    return path


def render_rng_trial_request(
    *,
    condition: str,
    activation_nonce: str,
    capsule_sha256: str,
) -> bytes:
    """Return the exact bounded startup request accepted by Mod Loader."""
    if condition not in _CONDITIONS:
        raise RngTrialCapsuleError("condition must be control or exact_hook")
    if type(activation_nonce) is not str or _NONCE_RE.fullmatch(activation_nonce) is None:
        raise RngTrialCapsuleError("activation nonce must be 32 to 64 lowercase hex")
    _sha256(capsule_sha256, "capsule_sha256")
    return (
        f"{REQUEST_TOKEN}\n"
        f"condition={condition}\n"
        f"activation_nonce={activation_nonce}\n"
        f"capsule_sha256={capsule_sha256}\n"
    ).encode("ascii")


def arm_rng_trial_request(
    *,
    bridge_root: Path,
    condition: str,
    activation_nonce: str,
    capsule_sha256: str,
) -> Path:
    """Create and fsync one fixed-name request without replacing anything."""
    payload = render_rng_trial_request(
        condition=condition,
        activation_nonce=activation_nonce,
        capsule_sha256=capsule_sha256,
    )
    root = Path(os.path.abspath(Path(bridge_root).expanduser()))
    root.mkdir(parents=True, exist_ok=True)
    path = root / REQUEST_FILENAME
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RngTrialCapsuleError("RNG trial startup request already exists") from exc
    except OSError as exc:
        try:
            path.unlink()
        except OSError:
            pass
        raise RngTrialCapsuleError(f"cannot arm RNG trial request: {exc}") from exc
    return path
