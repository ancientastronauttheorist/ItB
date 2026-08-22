"""Validate exact NextPawn replay inputs against a restored native checkpoint."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.observatory.msvc_rng_replay import (
    recover_observable_pre_state,
    recover_raw_pre_states,
    replay_results,
)
from src.observatory.native_checkpoint import (
    MAX_RECORDS,
    NativeCheckpointError,
    validate_native_checkpoint,
    validate_return_map_binding,
)


SCHEMA_VERSION = 1
LEDGER_KIND = "spawn_rng_replay_ledger"
CONTROLLER_VERSION = "observatory-spawn-replay-controller/1"
WRITE_MODE = "create_only"
SPAWNER_SOURCE_SHA256 = "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
SPAWNER_SOURCE_SUFFIX = "scripts/spawner_backend.lua"
SPAWNER_SOURCE_LINE = 174
RANDOM_ELEMENT_SOURCE_SHA256 = "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
RANDOM_ELEMENT_SOURCE_SUFFIX = "scripts/global.lua"
RANDOM_ELEMENT_SOURCE_LINE = 560
ANALYSIS_KIND = "spawn_rng_replay_capsule"

_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PAWN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,95}\Z")
_SCALAR_FIELDS = {
    "num_weak",
    "num_upgrades",
    "upgrade_streak",
    "num_spawns",
    "upgrade_max",
    "used_bosses",
    "num_bosses",
}


class SpawnReplayLedgerError(NativeCheckpointError):
    """Raised when replay evidence is malformed, incomplete, or inconsistent."""


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpawnReplayLedgerError(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    actual = set(value)
    if actual != fields:
        raise SpawnReplayLedgerError(
            f"{label} fields differ; "
            f"missing={sorted(fields - actual)}, unknown={sorted(actual - fields)}"
        )


def _integer(value: Any, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise SpawnReplayLedgerError(
            f"{label} must be an integer in [{low}, {high}]"
        )
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise SpawnReplayLedgerError(f"{label} must be boolean")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SpawnReplayLedgerError(f"{label} must be lowercase SHA-256")
    return value


def _pawn(value: Any, label: str) -> str:
    if type(value) is not str or _PAWN.fullmatch(value) is None:
        raise SpawnReplayLedgerError(f"{label} must be a canonical pawn name")
    return value


def _source(value: Any) -> None:
    source = _object(value, "spawn replay ledger.source_identity")
    _exact(
        source,
        {
            "spawner_expected_sha256",
            "spawner_expected_source_suffix",
            "spawner_expected_linedefined",
            "spawner_runtime_source",
            "spawner_runtime_linedefined",
            "random_element_expected_sha256",
            "random_element_expected_source_suffix",
            "random_element_expected_linedefined",
            "random_element_runtime_source",
            "random_element_runtime_linedefined",
            "source_locations_verified",
        },
        "spawn replay ledger.source_identity",
    )
    expected = {
        "spawner_expected_sha256": SPAWNER_SOURCE_SHA256,
        "spawner_expected_source_suffix": SPAWNER_SOURCE_SUFFIX,
        "spawner_expected_linedefined": SPAWNER_SOURCE_LINE,
        "random_element_expected_sha256": RANDOM_ELEMENT_SOURCE_SHA256,
        "random_element_expected_source_suffix": RANDOM_ELEMENT_SOURCE_SUFFIX,
        "random_element_expected_linedefined": RANDOM_ELEMENT_SOURCE_LINE,
    }
    for field, expected_value in expected.items():
        if source[field] != expected_value:
            raise SpawnReplayLedgerError(f"spawn replay source differs: {field}")
    for prefix, suffix, line in (
        ("spawner", SPAWNER_SOURCE_SUFFIX, SPAWNER_SOURCE_LINE),
        ("random_element", RANDOM_ELEMENT_SOURCE_SUFFIX, RANDOM_ELEMENT_SOURCE_LINE),
    ):
        runtime_source = source[f"{prefix}_runtime_source"]
        if (
            type(runtime_source) is not str
            or not runtime_source
            or len(runtime_source) > 1024
            or "\\" in runtime_source
            or not runtime_source.endswith(suffix)
            or source[f"{prefix}_runtime_linedefined"] != line
        ):
            raise SpawnReplayLedgerError(
                f"spawn replay runtime source differs: {prefix}"
            )
    if _boolean(
        source["source_locations_verified"],
        "spawn replay ledger.source_locations_verified",
    ) is not True:
        raise SpawnReplayLedgerError("spawn replay source locations are unverified")


def _integrity(value: Any) -> None:
    integrity = _object(value, "spawn replay ledger.integrity")
    zero_fields = {
        "nested_next_count",
        "nested_random_count",
        "observer_status_error_count",
        "span_overflow_count",
        "candidate_overflow_count",
        "invalid_candidate_count",
        "input_snapshot_error_count",
        "random_install_error_count",
        "candidate_count_mismatch_count",
        "active_depth",
    }
    _exact(
        integrity,
        {
            "complete",
            "next_wrapper_restored",
            "random_wrapper_restored",
            "restore_conflict",
        }
        | zero_fields,
        "spawn replay ledger.integrity",
    )
    for field in ("complete", "next_wrapper_restored", "random_wrapper_restored"):
        if _boolean(integrity[field], f"spawn replay integrity.{field}") is not True:
            raise SpawnReplayLedgerError(f"spawn replay integrity failed: {field}")
    if _boolean(
        integrity["restore_conflict"], "spawn replay integrity.restore_conflict"
    ) is not False:
        raise SpawnReplayLedgerError("spawn replay wrapper restoration conflicted")
    for field in zero_fields:
        _integer(integrity[field], f"spawn replay integrity.{field}", 0, 0)


def _ratio(value: Any, label: str) -> dict[str, Any]:
    ratio = _object(value, label)
    _exact(ratio, {"present", "numerator", "denominator"}, label)
    present = _boolean(ratio["present"], f"{label}.present")
    numerator = ratio["numerator"]
    denominator = ratio["denominator"]
    if present:
        numerator = _integer(numerator, f"{label}.numerator", -1_000_000, 1_000_000)
        denominator = _integer(
            denominator, f"{label}.denominator", -1_000_000, 1_000_000
        )
    elif numerator is not False or denominator is not False:
        raise SpawnReplayLedgerError(f"{label} absent values must be false")
    return {
        "present": present,
        "numerator": numerator,
        "denominator": denominator,
    }


def _inputs(value: Any, label: str) -> dict[str, Any]:
    inputs = _object(value, label)
    _exact(inputs, _SCALAR_FIELDS | {"curr_weak_ratio", "curr_upgrade_ratio"}, label)
    normalized: dict[str, Any] = {}
    for field in _SCALAR_FIELDS:
        raw = inputs[field]
        normalized[field] = (
            False
            if raw is False
            else _integer(raw, f"{label}.{field}", -1_000_000, 1_000_000)
        )
    normalized["curr_weak_ratio"] = _ratio(
        inputs["curr_weak_ratio"], f"{label}.curr_weak_ratio"
    )
    normalized["curr_upgrade_ratio"] = _ratio(
        inputs["curr_upgrade_ratio"], f"{label}.curr_upgrade_ratio"
    )
    return normalized


def validate_spawn_replay_ledger(
    value: Mapping[str, Any],
    *,
    capture_id: str,
    raw_record_count: int,
    expected_controller_sha256: str,
) -> list[dict[str, Any]]:
    """Validate and normalize one create-only spawn replay ledger."""
    ledger = _object(value, "spawn replay ledger")
    _exact(
        ledger,
        {
            "schema_version",
            "kind",
            "controller_version",
            "controller_sha256",
            "capture_id",
            "write_mode",
            "raw_record_count",
            "source_identity",
            "integrity",
            "spans",
            "summary",
        },
        "spawn replay ledger",
    )
    if ledger["schema_version"] != SCHEMA_VERSION or ledger["kind"] != LEDGER_KIND:
        raise SpawnReplayLedgerError("unsupported spawn replay ledger schema")
    if ledger["controller_version"] != CONTROLLER_VERSION:
        raise SpawnReplayLedgerError("spawn replay controller version differs")
    if _sha256(
        ledger["controller_sha256"], "spawn replay controller SHA-256"
    ) != _sha256(expected_controller_sha256, "expected controller SHA-256"):
        raise SpawnReplayLedgerError("spawn replay controller SHA-256 differs")
    if ledger["write_mode"] != WRITE_MODE:
        raise SpawnReplayLedgerError("spawn replay ledger is not create-only")
    if (
        type(ledger["capture_id"]) is not str
        or _ID.fullmatch(ledger["capture_id"]) is None
        or ledger["capture_id"] != capture_id
    ):
        raise SpawnReplayLedgerError("spawn replay capture ID differs")
    if _integer(
        ledger["raw_record_count"],
        "spawn replay raw_record_count",
        0,
        MAX_RECORDS,
    ) != raw_record_count:
        raise SpawnReplayLedgerError("spawn replay raw record count differs")
    _source(ledger["source_identity"])
    _integrity(ledger["integrity"])

    raw_spans = ledger["spans"]
    if not isinstance(raw_spans, list) or len(raw_spans) > 8:
        raise SpawnReplayLedgerError("spawn replay spans must be a bounded array")
    normalized: list[dict[str, Any]] = []
    previous_exit = 0
    for index, value_span in enumerate(raw_spans):
        label = f"spawn replay ledger.spans[{index}]"
        span = _object(value_span, label)
        _exact(
            span,
            {
                "span_id",
                "name",
                "detail",
                "inputs",
                "inputs_valid",
                "candidate_events",
                "selected_pawn",
                "selected_max_level",
                "boss_available",
                "random_wrapper_restored",
                "entry_count",
                "exit_count",
            },
            label,
        )
        if _integer(span["span_id"], f"{label}.span_id", 1, 8) != index + 1:
            raise SpawnReplayLedgerError("spawn replay span IDs are not contiguous")
        if span["name"] != "spawner_next_pawn" or span["detail"] != "normal":
            raise SpawnReplayLedgerError(f"{label} is not a normal NextPawn span")
        if _boolean(span["inputs_valid"], f"{label}.inputs_valid") is not True:
            raise SpawnReplayLedgerError(f"{label} input snapshot is invalid")
        inputs = _inputs(span["inputs"], f"{label}.inputs")
        entry = _integer(span["entry_count"], f"{label}.entry_count", 0, raw_record_count)
        exit_count = _integer(
            span["exit_count"], f"{label}.exit_count", 0, raw_record_count
        )
        if entry < previous_exit or exit_count - entry not in {3, 4}:
            raise SpawnReplayLedgerError(
                f"{label} overlaps or does not contain exactly 3/4 draws"
            )
        previous_exit = exit_count
        if _boolean(
            span["random_wrapper_restored"], f"{label}.random_wrapper_restored"
        ) is not True:
            raise SpawnReplayLedgerError(f"{label} random wrapper was not restored")
        selected_pawn = _pawn(span["selected_pawn"], f"{label}.selected_pawn")
        selected_max_level = _integer(
            span["selected_max_level"], f"{label}.selected_max_level", 1, 2
        )
        boss_available = _boolean(
            span["boss_available"], f"{label}.boss_available"
        )
        events = span["candidate_events"]
        if not isinstance(events, list) or len(events) != 1:
            raise SpawnReplayLedgerError(f"{label} must contain one candidate event")
        event_label = f"{label}.candidate_events[0]"
        event = _object(events[0], event_label)
        _exact(
            event,
            {
                "event_id",
                "entry_count",
                "exit_count",
                "detail",
                "list_length",
                "candidates_valid",
                "available",
                "selected_base",
            },
            event_label,
        )
        if event["event_id"] != 1 or event["detail"] != "normal":
            raise SpawnReplayLedgerError(f"{event_label} is not normal")
        if _boolean(
            event["candidates_valid"], f"{event_label}.candidates_valid"
        ) is not True:
            raise SpawnReplayLedgerError(f"{event_label} candidates are invalid")
        event_entry = _integer(
            event["entry_count"], f"{event_label}.entry_count", entry, exit_count
        )
        event_exit = _integer(
            event["exit_count"], f"{event_label}.exit_count", entry, exit_count
        )
        if event_entry != entry + 1 or event_exit != event_entry + 1:
            raise SpawnReplayLedgerError(
                f"{event_label} does not bound the second single native draw"
            )
        length = _integer(event["list_length"], f"{event_label}.list_length", 1, 64)
        available_raw = event["available"]
        if not isinstance(available_raw, list) or len(available_raw) != length:
            raise SpawnReplayLedgerError(f"{event_label}.available length differs")
        available = [
            _pawn(candidate, f"{event_label}.available[{candidate_index}]")
            for candidate_index, candidate in enumerate(available_raw)
        ]
        selected_base = _pawn(event["selected_base"], f"{event_label}.selected_base")
        if selected_base not in available or not selected_pawn.startswith(selected_base):
            raise SpawnReplayLedgerError(
                f"{event_label} selected pawn is inconsistent with candidates"
            )
        normalized.append(
            {
                "span_id": index + 1,
                "entry_count": entry,
                "exit_count": exit_count,
                "inputs": inputs,
                "available": available,
                "candidate_entry_count": event_entry,
                "candidate_exit_count": event_exit,
                "selected_base": selected_base,
                "selected_pawn": selected_pawn,
                "selected_max_level": selected_max_level,
                "boss_available": boss_available,
            }
        )
    summary = _object(ledger["summary"], "spawn replay ledger.summary")
    _exact(summary, {"span_count", "candidate_event_count", "complete"}, "spawn replay ledger.summary")
    if (
        _integer(summary["span_count"], "spawn replay summary.span_count", 0, 8)
        != len(normalized)
        or _integer(
            summary["candidate_event_count"],
            "spawn replay summary.candidate_event_count",
            0,
            8,
        )
        != len(normalized)
        or _boolean(summary["complete"], "spawn replay summary.complete") is not True
    ):
        raise SpawnReplayLedgerError("spawn replay summary differs")
    return normalized


def _required_scalar(inputs: Mapping[str, Any], field: str) -> int:
    value = inputs[field]
    if type(value) is not int:
        raise SpawnReplayLedgerError(f"spawn replay input {field} is unavailable")
    return value


def _effective_ratio(
    ratio: Mapping[str, Any], numerator_default: int
) -> tuple[int, int]:
    if ratio["present"] is not True or ratio["denominator"] == 0:
        return numerator_default, 5
    numerator = ratio["numerator"]
    denominator = ratio["denominator"]
    assert type(numerator) is int and type(denominator) is int
    if denominator <= 0:
        raise SpawnReplayLedgerError("spawn replay ratio denominator is not positive")
    return numerator, denominator


def analyze_spawn_replay(
    checkpoint: Mapping[str, Any],
    ledger: Mapping[str, Any],
    *,
    expected_controller_sha256: str,
    return_map: Mapping[str, Any],
    expected_identity: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict replay capsule from same-thread, source-bounded draws."""
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    if not verification["diagnostic_complete"]:
        raise SpawnReplayLedgerError("native checkpoint is incomplete")
    records = checkpoint["records"]
    if any(record["kind"] != "rng_core" for record in records):
        raise SpawnReplayLedgerError(
            "spawn replay requires an unmodified RNG-core checkpoint"
        )
    threads = {record["thread_slot"] for record in records}
    if len(threads) != 1:
        raise SpawnReplayLedgerError("spawn replay requires exactly one RNG thread")
    callers = validate_return_map_binding(checkpoint, return_map)
    spans = validate_spawn_replay_ledger(
        ledger,
        capture_id=checkpoint["capture_id"],
        raw_record_count=len(records),
        expected_controller_sha256=expected_controller_sha256,
    )
    if len(spans) != 1:
        raise SpawnReplayLedgerError("spawn replay capsule requires exactly one span")

    span = spans[0]
    enclosed = records[span["entry_count"] : span["exit_count"]]
    expected_callers = [21, 21, 21] + ([25] if len(enclosed) == 4 else [])
    if [record["caller_id"] for record in enclosed] != expected_callers:
        raise SpawnReplayLedgerError("spawn replay caller sequence differs")
    for caller_id, source_region in ((21, "random_int_1"), (25, "random_bool_1")):
        if caller_id in expected_callers:
            classification = callers.get(caller_id)
            if (
                not isinstance(classification, Mapping)
                or classification.get("status") != "reviewed_direct_call"
                or classification.get("source_region") != source_region
            ):
                raise SpawnReplayLedgerError(
                    f"spawn replay caller {caller_id} is not source-bound"
                )
    thread_slot = enclosed[0]["thread_slot"]
    if any(record["thread_slot"] != thread_slot for record in enclosed):
        raise SpawnReplayLedgerError("spawn replay draws cross threads")
    observed = tuple(record["result"] for record in enclosed)
    raw_pre_states = recover_raw_pre_states(observed)
    observable_state = recover_observable_pre_state(observed)
    if replay_results(observable_state, len(observed)) != observed:
        raise SpawnReplayLedgerError("observable state does not replay native draws")

    inputs = span["inputs"]
    num_weak = _required_scalar(inputs, "num_weak")
    num_upgrades = _required_scalar(inputs, "num_upgrades")
    weak_numerator, weak_denominator = _effective_ratio(
        inputs["curr_weak_ratio"], num_weak
    )
    upgrade_numerator, upgrade_denominator = _effective_ratio(
        inputs["curr_upgrade_ratio"], num_upgrades
    )
    weak_roll = observed[0] % weak_denominator
    weak_selected = weak_roll < weak_numerator
    candidate_index = observed[1] % len(span["available"])
    replayed_base = span["available"][candidate_index]
    if replayed_base != span["selected_base"]:
        raise SpawnReplayLedgerError("candidate modulo replay differs from selection")

    if inputs["curr_weak_ratio"]["present"] is False:
        upgrade_streak = 0
        used_bosses = 0
    else:
        upgrade_streak = _required_scalar(inputs, "upgrade_streak")
        used_bosses = (
            0 if inputs["used_bosses"] is False else inputs["used_bosses"]
        )
    assert type(used_bosses) is int
    num_bosses = 0 if inputs["num_bosses"] is False else inputs["num_bosses"]
    assert type(num_bosses) is int
    upgrade_roll = observed[2] % upgrade_denominator
    break_streak = (
        upgrade_numerator != upgrade_denominator
        and upgrade_streak >= max(1, num_upgrades - 1)
    )
    upgrade_selected = (
        upgrade_roll < upgrade_numerator
        and span["selected_max_level"] != 1
        and not break_streak
    )
    initial_level = 2 if upgrade_selected else 1
    suffix = span["selected_pawn"][len(span["selected_base"]) :]
    if suffix not in {"1", "2", "Boss"}:
        raise SpawnReplayLedgerError("selected pawn level suffix is unsupported")
    if initial_level == 1 and suffix != "1":
        raise SpawnReplayLedgerError("selected pawn contradicts upgrade branch")
    forced_downgrade = initial_level == 2 and suffix == "1"
    boss_guard = (
        initial_level == 2
        and not forced_downgrade
        and used_bosses < num_bosses
        and span["boss_available"]
        and span["selected_base"] != "Spider"
    )
    boss_draw = observed[3] if len(observed) == 4 else None
    boss_chance = max(3 - num_bosses, 1)
    boss_selected = boss_draw is not None and boss_draw % boss_chance == 0
    if boss_draw is not None and not boss_guard:
        raise SpawnReplayLedgerError("observed boss draw lacks its source guard")
    if boss_draw is None and boss_guard:
        raise SpawnReplayLedgerError("source boss guard lacks its required draw")
    expected_suffix = (
        "Boss"
        if boss_selected
        else "1"
        if initial_level == 1 or forced_downgrade
        else "2"
    )
    if suffix != expected_suffix:
        raise SpawnReplayLedgerError("selected pawn contradicts replayed final level")

    return {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "capture_id": checkpoint["capture_id"],
        "build_identity": dict(checkpoint["identity"]),
        "source_identity": dict(ledger["source_identity"]),
        "controller_sha256": ledger["controller_sha256"],
        "span_id": span["span_id"],
        "thread_slot": thread_slot,
        "raw_record_range": [span["entry_count"], span["exit_count"]],
        "native_results": list(observed),
        "raw_pre_state_candidates": [f"0x{state:08x}" for state in raw_pre_states],
        "observable_pre_state": observable_state,
        "observable_pre_state_hex": f"0x{observable_state:08x}",
        "raw_state_hidden_bit_ambiguous": True,
        "future_observable_stream_exact": True,
        "weak_branch": {
            "numerator": weak_numerator,
            "denominator": weak_denominator,
            "raw_result": observed[0],
            "modulo_result": weak_roll,
            "selected_weak": weak_selected,
        },
        "candidate_choice": {
            "available": span["available"],
            "raw_result": observed[1],
            "selected_index_zero_based": candidate_index,
            "selected_base": replayed_base,
        },
        "upgrade_branch": {
            "numerator": upgrade_numerator,
            "denominator": upgrade_denominator,
            "raw_result": observed[2],
            "modulo_result": upgrade_roll,
            "break_streak": break_streak,
            "selected_max_level": span["selected_max_level"],
            "selected_upgrade": upgrade_selected,
            "living_upgrade_cap_forced_downgrade": forced_downgrade,
        },
        "boss_branch": {
            "guard_reached": boss_guard,
            "boss_available": span["boss_available"],
            "chance": boss_chance if boss_guard else None,
            "raw_result": boss_draw,
            "selected_boss": boss_selected,
        },
        "selected_pawn": span["selected_pawn"],
        "replay_verified": True,
    }
