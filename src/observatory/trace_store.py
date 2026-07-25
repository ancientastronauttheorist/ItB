"""Immutable, identity-gated storage for finalized Observatory traces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.itb_paths import get_artifact_path
from src.observatory.trace_codec import (
    HARD_MAX_BUNDLE_BYTES,
    TraceCodecError,
    encode_trace,
    parse_trace,
    validate_build_identity,
)
from src.observatory.raw_trace import arm_packet_sha256
from src.observatory.controller_bundle import controller_bundle_sha256


FINAL_TRACE_RE = re.compile(
    r"^itb_observatory_trace_"
    r"(?P<capture_id>[a-z0-9][a-z0-9._-]{0,127})_"
    r"(?P<checkpoint_seq>0|[1-9][0-9]*)_"
    r"(?P<sha256>[0-9a-f]{64})\.json$"
)
ARM_PACKET_RE = re.compile(
    r"^itb_observatory_arm_"
    r"(?P<capture_id>[a-z0-9][a-z0-9._-]{0,127})_"
    r"(?P<checkpoint_seq>0|[1-9][0-9]*)_"
    r"(?P<sha256>[0-9a-f]{64})\.json$"
)
RAW_CHECKPOINT_RE = re.compile(
    r"^itb_observatory_trace_"
    r"(?P<capture_id>[a-z0-9][a-z0-9._-]{0,127})_"
    r"(?P<checkpoint_seq>0|[1-9][0-9]*)\.raw$"
)
CONTROLLER_BUNDLE_RE = re.compile(
    r"^itb_observatory_controller_(?P<sha256>[0-9a-f]{64})\.lua$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TraceStoreError(RuntimeError):
    """Raised when trace persistence or identity selection is unsafe."""


class _DuplicateKeyError(ValueError):
    pass


def _object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TraceStoreError(f"{label} must be an object")
    return value


def _type_safe_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return (
            set(left) == set(right)
            and all(_type_safe_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_safe_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def build_identity_from_inventory(inventory: Any) -> dict[str, Any]:
    """Translate a content inventory into the strict trace identity schema."""
    root = _mapping(inventory, "inventory")
    if root.get("app_id") != "590380":
        raise TraceStoreError("inventory.app_id must be 590380")
    executable = _mapping(root.get("executable"), "inventory.executable")
    steam = _mapping(root.get("steam"), "inventory.steam")
    if steam.get("app_id") != "590380":
        raise TraceStoreError("inventory.steam.app_id must be 590380")
    content = _mapping(root.get("content"), "inventory.content")
    scripts = _mapping(
        content.get("scripts"),
        "inventory.content.scripts",
    )
    maps = _mapping(content.get("maps"), "inventory.content.maps")
    depots = steam.get("installed_depots")
    if not isinstance(depots, list) or len(depots) != 1:
        raise TraceStoreError(
            "inventory.steam.installed_depots must contain exactly one "
            "explicit trace depot"
        )
    first_depot = _mapping(
        depots[0],
        "inventory.steam.installed_depots[0]",
    )
    if (
        type(first_depot.get("depot_id")) is not str
        or not first_depot["depot_id"].isdigit()
    ):
        raise TraceStoreError(
            "inventory.steam.installed_depots[0].depot_id "
            "must be numeric text"
        )
    architecture = executable.get("architecture")
    architectures = (
        executable.get("architectures")
        if architecture == "universal"
        else None
    )
    evidence = steam.get("evidence")
    build_evidence = (
        "local_appmanifest"
        if isinstance(evidence, Mapping)
        and type(evidence.get("path")) is str
        and Path(evidence["path"]).name == "appmanifest_590380.acf"
        and type(evidence.get("sha256")) is str
        and _SHA256_RE.fullmatch(evidence["sha256"])
        else "unavailable"
    )
    identity = {
        "platform": root.get("platform"),
        "architecture": architecture,
        "architectures": architectures,
        "executable_sha256": executable.get("sha256"),
        "build_id": (
            steam.get("build_id")
            if build_evidence != "unavailable"
            else None
        ),
        "depot_manifest": (
            first_depot.get("manifest")
            if build_evidence != "unavailable"
            else None
        ),
        "build_evidence": build_evidence,
        "scripts_revision_sha256": scripts.get("revision_sha256"),
        "maps_revision_sha256": maps.get("revision_sha256"),
    }
    try:
        return validate_build_identity(identity)
    except TraceCodecError as exc:
        raise TraceStoreError(f"invalid inventory identity: {exc}") from exc


def require_authoritative_build_identity(identity: Any) -> dict[str, Any]:
    """Validate identity and reject evidence that cannot bind a build."""
    try:
        validated = validate_build_identity(identity)
    except TraceCodecError as exc:
        raise TraceStoreError(f"invalid expected build identity: {exc}") from exc
    if validated["build_evidence"] == "unavailable":
        raise TraceStoreError(
            "authoritative trace validation requires build/manifest evidence"
        )
    return validated


def final_trace_filename(
    capture_id: str,
    checkpoint_seq: int,
    sha256: str,
) -> str:
    candidate = (
        f"itb_observatory_trace_{capture_id}_{checkpoint_seq}_{sha256}.json"
    )
    match = FINAL_TRACE_RE.fullmatch(candidate)
    if (
        match is None
        or type(checkpoint_seq) is not int
        or int(match.group("checkpoint_seq")) != checkpoint_seq
        or type(sha256) is not str
        or match.group("sha256") != sha256
    ):
        raise TraceStoreError("invalid final trace identity")
    return candidate


def arm_packet_filename(
    capture_id: str,
    checkpoint_seq: int,
    sha256: str,
) -> str:
    candidate = (
        f"itb_observatory_arm_{capture_id}_{checkpoint_seq}_{sha256}.json"
    )
    match = ARM_PACKET_RE.fullmatch(candidate)
    if (
        match is None
        or type(checkpoint_seq) is not int
        or int(match.group("checkpoint_seq")) != checkpoint_seq
        or type(sha256) is not str
        or match.group("sha256") != sha256
    ):
        raise TraceStoreError("invalid arm packet identity")
    return candidate


def _root(root: Path | None) -> Path:
    selected = (
        get_artifact_path("observatory", "traces")
        if root is None
        else Path(root)
    )
    return selected.expanduser().resolve()


def _direct_final_path(path: Path, root: Path) -> tuple[str, int, str]:
    absolute = Path(os.path.abspath(path.expanduser()))
    if absolute.parent != root:
        raise TraceStoreError("trace must be a direct child of the trace root")
    match = FINAL_TRACE_RE.fullmatch(absolute.name)
    if match is None:
        raise TraceStoreError("not an immutable final trace filename")
    return (
        match.group("capture_id"),
        int(match.group("checkpoint_seq")),
        match.group("sha256"),
    )


def _fingerprint(
    stat_result: os.stat_result,
) -> tuple[int, int, int, int, int]:
    return (
        stat_result.st_dev,
        stat_result.st_ino,
        stat_result.st_mode,
        stat_result.st_size,
        stat_result.st_mtime_ns,
    )


def _stable_read_bytes(path: Path, max_bytes: int) -> bytes:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        entry_before = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise TraceStoreError(f"cannot stat file: {exc}") from exc
    if stat.S_ISLNK(entry_before.st_mode):
        raise TraceStoreError("symlinks are not accepted")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise TraceStoreError(f"cannot open file: {exc}") from exc
    try:
        handle_before = os.fstat(descriptor)
        if not stat.S_ISREG(handle_before.st_mode):
            raise TraceStoreError("file is not regular")
        if not os.path.samestat(entry_before, handle_before):
            raise TraceStoreError("directory entry changed before read")
        if handle_before.st_size > max_bytes:
            raise TraceStoreError("file exceeds hard size limit")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        handle_after = os.fstat(descriptor)
        try:
            entry_after = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise TraceStoreError(
                f"directory entry disappeared during read: {exc}"
            ) from exc
        if stat.S_ISLNK(entry_after.st_mode):
            raise TraceStoreError("directory entry became a symlink")
        if (
            _fingerprint(handle_before) != _fingerprint(handle_after)
            or not os.path.samestat(handle_after, entry_after)
        ):
            raise TraceStoreError("file changed during read")
        if len(raw) > max_bytes:
            raise TraceStoreError("file exceeds hard size limit")
        return raw
    finally:
        os.close(descriptor)


def stable_file_sha256(
    path: Path,
    *,
    max_bytes: int = HARD_MAX_BUNDLE_BYTES,
) -> str:
    """Hash one stable regular non-symlink file within an explicit byte cap."""
    return hashlib.sha256(_stable_read_bytes(Path(path), max_bytes)).hexdigest()


def _strict_json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
        ValueError,
    ) as exc:
        raise TraceStoreError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TraceStoreError(f"{label} must be a JSON object")
    return value


def _direct_named_path(
    path: Path,
    root: Path,
    pattern: re.Pattern[str],
    label: str,
) -> re.Match[str]:
    absolute = Path(os.path.abspath(path.expanduser()))
    if absolute.parent != root:
        raise TraceStoreError(f"{label} must be a direct child of its root")
    match = pattern.fullmatch(absolute.name)
    if match is None:
        raise TraceStoreError(f"invalid {label} filename")
    return match


def read_arm_packet(
    path: Path,
    *,
    expected_capture_id: str,
    expected_checkpoint_seq: int,
    expected_arm_sha256: str,
    root: Path,
) -> dict[str, Any]:
    """Read one exact immutable, content-addressed arm packet."""
    packet_root = _root(root)
    match = _direct_named_path(
        path, packet_root, ARM_PACKET_RE, "arm packet"
    )
    if (
        type(expected_arm_sha256) is not str
        or not _SHA256_RE.fullmatch(expected_arm_sha256)
    ):
        raise TraceStoreError("expected arm digest must be lowercase SHA-256")
    if (
        match.group("capture_id") != expected_capture_id
        or int(match.group("checkpoint_seq")) != expected_checkpoint_seq
        or match.group("sha256") != expected_arm_sha256
    ):
        raise TraceStoreError("arm packet filename identity mismatch")
    raw = _stable_read_bytes(Path(path), HARD_MAX_BUNDLE_BYTES)
    if hashlib.sha256(raw).hexdigest() != expected_arm_sha256:
        raise TraceStoreError("arm packet content digest mismatch")
    packet = _strict_json_object(raw, "arm packet")
    try:
        canonical_digest = arm_packet_sha256(packet)
    except Exception as exc:
        raise TraceStoreError(f"invalid arm packet: {exc}") from exc
    if canonical_digest != expected_arm_sha256:
        raise TraceStoreError("arm packet is not canonical")
    return packet


def read_raw_checkpoint(
    path: Path,
    *,
    expected_capture_id: str,
    expected_checkpoint_seq: int,
    expected_raw_sha256: str,
    root: Path,
    max_bytes: int,
) -> dict[str, Any]:
    """Read one exact raw Lua checkpoint without guessing a latest file."""
    raw_root = _root(root)
    match = _direct_named_path(
        path, raw_root, RAW_CHECKPOINT_RE, "raw checkpoint"
    )
    if (
        type(expected_raw_sha256) is not str
        or not _SHA256_RE.fullmatch(expected_raw_sha256)
    ):
        raise TraceStoreError("expected raw digest must be lowercase SHA-256")
    if (
        match.group("capture_id") != expected_capture_id
        or int(match.group("checkpoint_seq")) != expected_checkpoint_seq
    ):
        raise TraceStoreError("raw checkpoint filename identity mismatch")
    if (
        type(max_bytes) is not int
        or max_bytes < 1
        or max_bytes > HARD_MAX_BUNDLE_BYTES
    ):
        raise TraceStoreError("invalid raw checkpoint byte limit")
    raw = _stable_read_bytes(Path(path), max_bytes)
    if hashlib.sha256(raw).hexdigest() != expected_raw_sha256:
        raise TraceStoreError("raw checkpoint content digest mismatch")
    return _strict_json_object(raw, "raw checkpoint")


def read_final_trace(
    path: Path,
    *,
    expected_build_identity: Mapping[str, Any],
    expected_capture_identity: Mapping[str, Any],
    expected_trace_sha256: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Read one stable final bundle and require exact trusted identities."""
    trace_root = _root(root)
    capture_id, checkpoint_seq, filename_sha256 = _direct_final_path(
        Path(path),
        trace_root,
    )
    expected_build = require_authoritative_build_identity(
        expected_build_identity
    )
    if not isinstance(expected_capture_identity, Mapping):
        raise TraceStoreError("expected capture identity must be an object")
    if (
        type(expected_trace_sha256) is not str
        or not _SHA256_RE.fullmatch(expected_trace_sha256)
    ):
        raise TraceStoreError("expected trace digest must be lowercase SHA-256")
    if filename_sha256 != expected_trace_sha256:
        raise TraceStoreError("filename trace digest mismatch")
    raw = _stable_read_bytes(Path(path), HARD_MAX_BUNDLE_BYTES)
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_trace_sha256:
        raise TraceStoreError("trace content digest mismatch")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TraceStoreError("trace is not strict UTF-8") from exc
    try:
        trace = parse_trace(text)
    except TraceCodecError as exc:
        raise TraceStoreError(f"invalid final trace: {exc}") from exc

    if trace["capture_identity"]["capture_id"] != capture_id:
        raise TraceStoreError("filename capture identity mismatch")
    if trace["checkpoint"]["seq"] != checkpoint_seq:
        raise TraceStoreError("filename checkpoint sequence mismatch")
    if not _type_safe_equal(trace["build_identity"], expected_build):
        raise TraceStoreError("trace build identity mismatch")
    if not _type_safe_equal(
        trace["capture_identity"],
        dict(expected_capture_identity),
    ):
        raise TraceStoreError("trace capture identity mismatch")
    return trace


def load_final_trace(
    capture_id: str,
    checkpoint_seq: int,
    *,
    expected_build_identity: Mapping[str, Any],
    expected_capture_identity: Mapping[str, Any],
    expected_trace_sha256: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Select exactly one immutable checkpoint; never guess a latest file."""
    trace_root = _root(root)
    filename = final_trace_filename(
        capture_id,
        checkpoint_seq,
        expected_trace_sha256,
    )
    return read_final_trace(
        trace_root / filename,
        expected_build_identity=expected_build_identity,
        expected_capture_identity=expected_capture_identity,
        expected_trace_sha256=expected_trace_sha256,
        root=trace_root,
    )


def list_final_traces(root: Path | None = None) -> list[Path]:
    """List only immutable final bundles, ignoring raw and temporary files."""
    trace_root = _root(root)
    if not trace_root.exists():
        return []
    if not trace_root.is_dir():
        raise TraceStoreError("trace root is not a directory")
    return sorted(
        (
            entry
            for entry in trace_root.iterdir()
            if entry.is_file()
            and not entry.is_symlink()
            and FINAL_TRACE_RE.fullmatch(entry.name)
        ),
        key=lambda entry: entry.name,
    )


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if os.name == "nt":
            return
        raise TraceStoreError(
            f"cannot open trace directory for fsync: {exc}"
        ) from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if os.name != "nt":
            raise TraceStoreError(
                f"cannot fsync trace directory: {exc}"
            ) from exc
    finally:
        os.close(descriptor)


def _remove_new_file(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except FileNotFoundError:
        return
    except OSError as chmod_exc:
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            raise chmod_exc
    path.unlink()


def _publish_create_only(
    content: bytes,
    final_path: Path,
    *,
    max_bytes: int,
) -> None:
    temp_name = (
        f".{final_path.name}.{os.getpid()}."
        f"{secrets.token_hex(8)}.publishing"
    )
    temp_path = final_path.parent / temp_name
    published = False
    try:
        with temp_path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if os.name == "nt":
            os.rename(temp_path, final_path)
            published = True
        else:
            os.link(temp_path, final_path)
            published = True
            temp_path.unlink()
        _fsync_directory(final_path.parent)
        if _stable_read_bytes(final_path, max_bytes) != content:
            raise TraceStoreError("published content changed before verification")
    except FileExistsError as exc:
        raise TraceStoreError("immutable output already exists") from exc
    except TraceStoreError:
        if published:
            try:
                _remove_new_file(final_path)
            except OSError as cleanup_exc:
                raise TraceStoreError(
                    "publication failed and final cleanup was unsuccessful: "
                    f"{cleanup_exc}"
                )
        raise
    except OSError as exc:
        if published:
            try:
                _remove_new_file(final_path)
            except OSError as cleanup_exc:
                raise TraceStoreError(
                    "publication failed and final cleanup was unsuccessful: "
                    f"{cleanup_exc}"
                ) from exc
        raise TraceStoreError(f"cannot publish immutable output: {exc}") from exc
    finally:
        try:
            _remove_new_file(temp_path)
        except FileNotFoundError:
            pass


def write_arm_packet(
    packet: Mapping[str, Any],
    *,
    root: Path,
) -> Path:
    """Publish one canonical arm packet immutably and content-address it."""
    try:
        rendered = (
            json.dumps(
                packet,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        digest = arm_packet_sha256(packet)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise TraceStoreError(f"cannot publish invalid arm packet: {exc}") from exc
    rendered_bytes = rendered.encode("utf-8")
    if len(rendered_bytes) > HARD_MAX_BUNDLE_BYTES:
        raise TraceStoreError("arm packet exceeds hard size limit")
    manifest = _mapping(packet.get("manifest"), "arm packet manifest")
    capture_id = manifest.get("capture_id")
    checkpoint_seq = manifest.get("checkpoint_seq")
    packet_root = _root(root)
    try:
        packet_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TraceStoreError(f"cannot create arm packet root: {exc}") from exc
    final_path = packet_root / arm_packet_filename(
        capture_id, checkpoint_seq, digest
    )
    _publish_create_only(
        rendered_bytes,
        final_path,
        max_bytes=HARD_MAX_BUNDLE_BYTES,
    )
    return final_path


def write_controller_bundle(bundle: str, *, root: Path) -> Path:
    """Publish one deterministic self-contained Lua controller bundle."""
    if type(bundle) is not str:
        raise TraceStoreError("controller bundle must be text")
    try:
        rendered_bytes = bundle.encode("utf-8", errors="strict")
        digest = controller_bundle_sha256(bundle)
    except (UnicodeEncodeError, RuntimeError) as exc:
        raise TraceStoreError(f"invalid controller bundle: {exc}") from exc
    if len(rendered_bytes) > HARD_MAX_BUNDLE_BYTES:
        raise TraceStoreError("controller bundle exceeds hard size limit")
    bundle_root = _root(root)
    try:
        bundle_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TraceStoreError(
            f"cannot create controller bundle root: {exc}"
        ) from exc
    final_path = bundle_root / (
        f"itb_observatory_controller_{digest}.lua"
    )
    if CONTROLLER_BUNDLE_RE.fullmatch(final_path.name) is None:
        raise TraceStoreError("invalid controller bundle identity")
    _publish_create_only(
        rendered_bytes,
        final_path,
        max_bytes=HARD_MAX_BUNDLE_BYTES,
    )
    return final_path


def write_final_trace(
    trace: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> Path:
    """Publish a complete bundle atomically without replacing prior evidence."""
    try:
        rendered = encode_trace(trace)
        snapshot = parse_trace(rendered)
    except TraceCodecError as exc:
        raise TraceStoreError(f"cannot publish invalid trace: {exc}") from exc
    require_authoritative_build_identity(snapshot["build_identity"])
    capture_id = snapshot["capture_identity"]["capture_id"]
    checkpoint_seq = snapshot["checkpoint"]["seq"]
    rendered_bytes = rendered.encode("utf-8")
    trace_sha256 = hashlib.sha256(rendered_bytes).hexdigest()
    trace_root = _root(root)
    try:
        trace_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TraceStoreError(f"cannot create trace root: {exc}") from exc
    final_path = trace_root / final_trace_filename(
        capture_id,
        checkpoint_seq,
        trace_sha256,
    )
    temp_name = (
        f".{final_path.name}.{os.getpid()}."
        f"{secrets.token_hex(8)}.publishing"
    )
    temp_path = trace_root / temp_name
    published = False
    try:
        with temp_path.open("xb") as handle:
            handle.write(rendered_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if os.name == "nt":
            os.rename(temp_path, final_path)
            published = True
        else:
            os.link(temp_path, final_path)
            published = True
            temp_path.unlink()
        _fsync_directory(trace_root)
        published_bytes = _stable_read_bytes(
            final_path,
            HARD_MAX_BUNDLE_BYTES,
        )
        if hashlib.sha256(published_bytes).hexdigest() != trace_sha256:
            raise TraceStoreError(
                "published trace digest changed before verification"
            )
    except FileExistsError as exc:
        raise TraceStoreError("final trace already exists") from exc
    except TraceStoreError:
        if published:
            try:
                _remove_new_file(final_path)
            except OSError as cleanup_exc:
                raise TraceStoreError(
                    "publication failed and final cleanup was unsuccessful: "
                    f"{cleanup_exc}"
                )
        raise
    except OSError as exc:
        if published:
            try:
                _remove_new_file(final_path)
            except OSError as cleanup_exc:
                raise TraceStoreError(
                    "publication failed and final cleanup was unsuccessful: "
                    f"{cleanup_exc}"
                ) from exc
        raise TraceStoreError(f"cannot publish final trace: {exc}") from exc
    finally:
        try:
            _remove_new_file(temp_path)
        except FileNotFoundError:
            pass
    return final_path


def summarize_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, compact evidence summary."""
    events = trace["events"]
    counts = Counter(event["kind"] for event in events)
    hook_counts = Counter(
        entry["status"] for entry in trace["hook_coverage"]
    )
    return {
        "schema_version": trace["schema_version"],
        "build_identity": dict(trace["build_identity"]),
        "capture_id": trace["capture_identity"]["capture_id"],
        "mission_id": trace["checkpoint"]["mission_id"],
        "turn": trace["checkpoint"]["turn"],
        "phase": trace["checkpoint"]["phase"],
        "checkpoint_seq": trace["checkpoint"]["seq"],
        "checkpoint_reason": trace["checkpoint"]["reason"],
        "event_counts": dict(sorted(counts.items())),
        "hook_status_counts": dict(sorted(hook_counts.items())),
        "summary": dict(trace["summary"]),
    }


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load a strict JSON object for CLI trust inputs."""
    try:
        raw = _stable_read_bytes(Path(path), HARD_MAX_BUNDLE_BYTES)
    except TraceStoreError as exc:
        raise TraceStoreError(f"cannot read {label}: {exc}") from exc
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
        ValueError,
    ) as exc:
        raise TraceStoreError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TraceStoreError(f"{label} must be a JSON object")
    return value
