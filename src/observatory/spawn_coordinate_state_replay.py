"""Recover exact spawn-selector replay vectors from accepted native captures.

The combined 2026-08-22 campaign captured the complete native RNG stream and
the standard spawn-coordinate decision in the same process.  Three consecutive
MSVC ``rand()`` results around each selector call recover one unique observable
pre-call state class.  This module joins those immutable artifacts, verifies
their original campaign and cleanup receipts, and emits strict replay vectors.

The result is deliberately post-hoc evidence.  It does not claim that ordinary
bridge state exposes the recovered value before a future selector executes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.msvc_rng_replay import (
    MsvcRngReplayError,
    canonical_observable_state,
    draw,
    recover_raw_pre_states,
    replay_results,
)
from src.observatory.native_boundary_campaign import (
    build_spawn_coordinate_rng_campaign_receipt,
)


SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_spawn_coordinate_state_replay_receipt"
CAMPAIGN_RELATIVE = Path(
    "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng"
)
SOURCE_RECEIPT_RELATIVE = Path(
    "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822_"
    "spawn_coordinate_rng_receipt.json"
)
CLEANUP_RECEIPT_RELATIVE = Path(
    "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822_"
    "spawn_coordinate_rng_cleanup_receipt.json"
)


class SpawnCoordinateStateReplayError(ValueError):
    """Raised when immutable coordinate/RNG evidence does not join exactly."""


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a receipt with the repository's canonical JSON convention."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise SpawnCoordinateStateReplayError(
            f"value is not canonical JSON: {exc}"
        ) from exc
    return (encoded + "\n").encode("utf-8")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpawnCoordinateStateReplayError(f"{label} must be an object")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise SpawnCoordinateStateReplayError(f"{label} must be an array")
    return value


def _load(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SpawnCoordinateStateReplayError(f"cannot load {label}: {exc}") from exc
    return _mapping(value, label)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise SpawnCoordinateStateReplayError(
            f"artifact is outside repository: {path}"
        ) from exc
    payload = path.read_bytes()
    return {
        "path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def _artifact_path(
    metadata: Mapping[str, Any], repository_root: Path, label: str
) -> Path:
    if set(metadata) != {"path", "sha256", "size"}:
        raise SpawnCoordinateStateReplayError(f"{label} metadata fields differ")
    relative = metadata.get("path")
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise SpawnCoordinateStateReplayError(f"{label} path is invalid")
    path = (repository_root / relative).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise SpawnCoordinateStateReplayError(
            f"{label} escapes the repository"
        ) from exc
    if (
        not path.is_file()
        or metadata.get("size") != path.stat().st_size
        or metadata.get("sha256") != _sha256(path)
    ):
        raise SpawnCoordinateStateReplayError(f"{label} artifact identity differs")
    return path


def _point(value: Any, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(coordinate) is not int or not 0 <= coordinate <= 7 for coordinate in value)
    ):
        raise SpawnCoordinateStateReplayError(f"{label} must be an in-board point")
    return [value[0], value[1]]


def recover_selector_replay_vector(
    *,
    pair: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    attribution: Mapping[str, Any],
    coordinate_analysis: Mapping[str, Any],
) -> dict[str, Any]:
    """Recover and verify one exact observable selector-state vector."""
    pair_name = pair.get("pair")
    capture_id = pair.get("capture_id")
    if not isinstance(pair_name, str) or not isinstance(capture_id, str):
        raise SpawnCoordinateStateReplayError("pair identity is invalid")
    if checkpoint.get("capture_id") != capture_id:
        raise SpawnCoordinateStateReplayError(f"{pair_name} checkpoint capture differs")
    if attribution.get("capture_id") != capture_id:
        raise SpawnCoordinateStateReplayError(f"{pair_name} attribution capture differs")
    if coordinate_analysis.get("capture_id") != capture_id:
        raise SpawnCoordinateStateReplayError(f"{pair_name} analysis capture differs")

    summary = _mapping(checkpoint.get("summary"), f"{pair_name} checkpoint summary")
    integrity = _mapping(
        checkpoint.get("integrity"), f"{pair_name} checkpoint integrity"
    )
    records = _sequence(checkpoint.get("records"), f"{pair_name} checkpoint records")
    if (
        summary.get("capture_complete") is not True
        or summary.get("thread_count") != 1
        or summary.get("record_count") != len(records)
        or integrity.get("hook_bytes_restored") is not True
    ):
        raise SpawnCoordinateStateReplayError(f"{pair_name} checkpoint is incomplete")

    events = _sequence(attribution.get("events"), f"{pair_name} attribution events")
    analysis_events = _sequence(
        coordinate_analysis.get("events"), f"{pair_name} analysis events"
    )
    if len(events) != 1 or len(analysis_events) != 1:
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} must contain exactly one selector event"
        )
    event = _mapping(events[0], f"{pair_name} selector event")
    analysis_event = _mapping(analysis_events[0], f"{pair_name} analysis event")
    selector = _mapping(pair.get("selector"), f"{pair_name} receipt selector")
    expected_selector = {
        "call_rva": "0x00172e70",
        "caller_id": 60,
        "return_rva": "0x00172e75",
    }
    if any(event.get(key) != value for key, value in expected_selector.items()):
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} is not the standard selector boundary"
        )
    for field in (
        "call_rva",
        "caller_id",
        "return_rva",
        "rng_sequence",
        "rng_ordinal",
        "raw_rng",
        "candidate_count",
        "candidates",
        "selected_index",
        "selected",
    ):
        if selector.get(field) != event.get(field):
            raise SpawnCoordinateStateReplayError(
                f"{pair_name} selector field differs: {field}"
            )

    sequence = event.get("rng_sequence")
    ordinal = event.get("rng_ordinal")
    if (
        type(sequence) is not int
        or type(ordinal) is not int
        or ordinal != sequence + 1
        or sequence < 0
        or sequence + 3 > len(records)
    ):
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} lacks a three-result recovery window"
        )
    window = records[sequence : sequence + 3]
    for offset, raw_record in enumerate(window):
        record = _mapping(raw_record, f"{pair_name} RNG record {sequence + offset}")
        if (
            record.get("kind") != "rng_core"
            or record.get("seq") != sequence + offset
            or record.get("thread_slot") != event.get("thread_slot")
            or type(record.get("result")) is not int
        ):
            raise SpawnCoordinateStateReplayError(
                f"{pair_name} RNG recovery window is not contiguous"
            )
    if window[0].get("caller_id") != 60 or window[0].get("result") != event.get(
        "raw_rng"
    ):
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} selector does not start the recovery window"
        )

    observed = [record["result"] for record in window]
    try:
        raw_pre_states = recover_raw_pre_states(observed)
    except MsvcRngReplayError as exc:
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} RNG state recovery failed: {exc}"
        ) from exc
    if len(raw_pre_states) != 2 or raw_pre_states[0] ^ raw_pre_states[1] != 0x80000000:
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} RNG results do not recover one observable state"
        )
    observable_pre_state = canonical_observable_state(raw_pre_states[0])
    if list(replay_results(observable_pre_state, 3)) != observed:
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} recovered state does not replay the native window"
        )
    replayed_raw, replayed_post_state = draw(observable_pre_state)

    candidates = _sequence(event.get("candidates"), f"{pair_name} candidates")
    candidate_count = event.get("candidate_count")
    selected_index = event.get("selected_index")
    selected = _point(event.get("selected"), f"{pair_name} selected point")
    normalized_candidates = [
        _point(candidate, f"{pair_name} candidate {index}")
        for index, candidate in enumerate(candidates)
    ]
    if (
        type(candidate_count) is not int
        or candidate_count != len(normalized_candidates)
        or candidate_count == 0
        or type(selected_index) is not int
        or not 0 <= selected_index < candidate_count
        or replayed_raw != event.get("raw_rng")
        or selected_index != replayed_raw % candidate_count
        or normalized_candidates[selected_index] != selected
    ):
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} state/candidate replay does not select the native point"
        )
    if (
        analysis_event.get("raw_rng") != replayed_raw
        or analysis_event.get("candidate_count") != candidate_count
        or analysis_event.get("candidates") != normalized_candidates
        or analysis_event.get("selected_index") != selected_index
        or analysis_event.get("selected") != selected
    ):
        raise SpawnCoordinateStateReplayError(
            f"{pair_name} coordinate analysis differs from the replay"
        )

    return {
        "capture_id": capture_id,
        "candidate_count": candidate_count,
        "candidates": normalized_candidates,
        "native_result_window": observed,
        "observable_post_state": canonical_observable_state(replayed_post_state),
        "observable_post_state_hex": (
            f"0x{canonical_observable_state(replayed_post_state):08x}"
        ),
        "observable_pre_state": observable_pre_state,
        "observable_pre_state_hex": f"0x{observable_pre_state:08x}",
        "pair": pair_name,
        "raw_pre_state_candidates_hex": [
            f"0x{state:08x}" for state in raw_pre_states
        ],
        "raw_rng": replayed_raw,
        "rng_ordinal": ordinal,
        "rng_sequence": sequence,
        "selected": selected,
        "selected_index": selected_index,
    }


def _validate_cleanup(
    cleanup: Mapping[str, Any],
    *,
    source_receipt_path: Path,
) -> None:
    evidence = _mapping(
        cleanup.get("campaign_evidence"), "cleanup campaign evidence"
    )
    source = _mapping(
        evidence.get("spawn_coordinate_rng"), "cleanup source receipt"
    )
    expected = {
        "path": SOURCE_RECEIPT_RELATIVE.as_posix(),
        "sha256": _sha256(source_receipt_path),
        "size": source_receipt_path.stat().st_size,
    }
    if dict(source) != expected:
        raise SpawnCoordinateStateReplayError(
            "cleanup receipt does not bind the immutable source receipt"
        )
    install = _mapping(cleanup.get("install_restore"), "cleanup install restore")
    comparison = _mapping(
        install.get("comparison_summary"), "cleanup install comparison"
    )
    save = _mapping(cleanup.get("save_restore"), "cleanup save restore")
    bridge = _mapping(cleanup.get("bridge_cleanup"), "cleanup bridge cleanup")
    terminal = _mapping(cleanup.get("terminal_state"), "cleanup terminal state")
    expected_terminal = {
        "game_process_running": False,
        "gameflow_helper_installed": False,
        "rng_core_observer_installed": False,
        "rng_seed_helper_installed": False,
        "spawn_coordinate_observer_installed": False,
    }
    if (
        comparison
        != {"changed": 0, "identical": 689, "missing": 0, "platform_specific": 0}
        or install.get("remaining_experimental_file_count") != 0
        or save.get("file_set_and_bytes_match") is not True
        or bridge.get("remaining_observatory_file_count") != 0
        or dict(terminal) != expected_terminal
    ):
        raise SpawnCoordinateStateReplayError(
            "coordinate/RNG cleanup receipt is not fully closed"
        )


def build_spawn_coordinate_state_replay_receipt(
    repository_root: Path,
) -> dict[str, Any]:
    """Build a strict derived receipt from immutable accepted campaign files."""
    repo = repository_root.resolve()
    campaign_root = repo / CAMPAIGN_RELATIVE
    source_receipt_path = repo / SOURCE_RECEIPT_RELATIVE
    cleanup_receipt_path = repo / CLEANUP_RECEIPT_RELATIVE

    rebuilt_source = build_spawn_coordinate_rng_campaign_receipt(
        campaign_root,
        repository_root=repo,
    )
    committed_source = _load(source_receipt_path, "source campaign receipt")
    if rebuilt_source != committed_source:
        raise SpawnCoordinateStateReplayError(
            "source campaign receipt does not rebuild from immutable artifacts"
        )
    cleanup = _load(cleanup_receipt_path, "source cleanup receipt")
    _validate_cleanup(cleanup, source_receipt_path=source_receipt_path)

    source_pairs = _sequence(rebuilt_source.get("pairs"), "source campaign pairs")
    vectors: list[dict[str, Any]] = []
    for pair_value in source_pairs:
        pair = _mapping(pair_value, "source campaign pair")
        pair_name = pair.get("pair")
        if not isinstance(pair_name, str):
            raise SpawnCoordinateStateReplayError("source pair name is invalid")
        artifacts = _mapping(pair.get("artifacts"), f"{pair_name} artifacts")
        checkpoint_path = _artifact_path(
            _mapping(artifacts.get("rng_checkpoint"), f"{pair_name} checkpoint artifact"),
            repo,
            f"{pair_name} checkpoint",
        )
        attribution_path = _artifact_path(
            _mapping(artifacts.get("attribution"), f"{pair_name} attribution artifact"),
            repo,
            f"{pair_name} attribution",
        )
        analysis_path = _artifact_path(
            _mapping(
                artifacts.get("coordinate_analysis"),
                f"{pair_name} analysis artifact",
            ),
            repo,
            f"{pair_name} coordinate analysis",
        )
        vector = recover_selector_replay_vector(
            pair=pair,
            checkpoint=_load(checkpoint_path, f"{pair_name} checkpoint"),
            attribution=_load(attribution_path, f"{pair_name} attribution"),
            coordinate_analysis=_load(analysis_path, f"{pair_name} analysis"),
        )
        vector["artifacts"] = {
            "attribution": dict(artifacts["attribution"]),
            "coordinate_analysis": dict(artifacts["coordinate_analysis"]),
            "rng_checkpoint": dict(artifacts["rng_checkpoint"]),
        }
        vectors.append(vector)

    if [vector["pair"] for vector in vectors] != ["pair001", "pair002", "pair003"]:
        raise SpawnCoordinateStateReplayError("source pair order differs")
    build_identity = _mapping(
        rebuilt_source.get("build_identity"), "source build identity"
    )
    return {
        "build_identity": dict(build_identity),
        "capture_track": "owner_local_modified",
        "claims": {
            "not_proven": [
                "Ordinary bridge delivery of selector-time native state before a future spawn decision.",
                "A stable RNG ordinal from save state or the fixed seed; presentation draws moved the selector across ordinals 1495, 1475, and 1450.",
                "Scheduler or emergency-fallback runtime behavior; all three joined decisions used standard caller 60.",
                "Pristine-depot or non-Windows equivalence.",
            ],
            "proven": [
                "Each same-process selector event begins a contiguous three-result native RNG window that recovers exactly two raw pre-states differing only in hidden bit 31.",
                "The canonical low-31-bit pre-state reproduces the selector's native raw RNG result and the following two native results in every capture.",
                "Applying raw_rng modulo the preserved ordered candidate count selects the exact native spawn coordinate in all three captures.",
                "The source campaign rebuilds exactly and its cleanup receipt binds a restored 689-entry installation, exact save tree, empty active Observatory residue, and stopped game.",
            ],
        },
        "kind": RECEIPT_KIND,
        "results": {
            "classification": (
                "selector_time_observable_state_recovered_post_hoc_"
                "exact_replay_not_prospective"
            ),
            "observable_pre_states": [
                vector["observable_pre_state_hex"] for vector in vectors
            ],
            "raw_rng_values": [vector["raw_rng"] for vector in vectors],
            "replay_count": len(vectors),
            "selected_coordinates": [vector["selected"] for vector in vectors],
            "selected_indices": [vector["selected_index"] for vector in vectors],
        },
        "schema_version": SCHEMA_VERSION,
        "solver_conformance": {
            "remaining_guard": (
                "Do not forecast a future spawn coordinate unless an exact pre-call "
                "state and ordered candidate capsule is available before selection."
            ),
            "resolved_replay": (
                "Advance the observable MSVC state once, then select "
                "candidates[raw_rng % candidate_count]."
            ),
            "rust_module": "rust_solver/src/native_rng.rs",
            "rust_test": (
                "rust_solver/tests/observatory_spawn_coordinate_state_replay.rs"
            ),
            "simulator_version_bump_required": False,
        },
        "source_evidence": {
            "cleanup_receipt": _artifact(cleanup_receipt_path, repo),
            "coordinate_rng_receipt": _artifact(source_receipt_path, repo),
        },
        "vectors": vectors,
    }
