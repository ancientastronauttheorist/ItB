"""Join exact spawn-coordinate events to the complete native RNG stream."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from src.observatory.native_checkpoint import validate_native_checkpoint
from src.observatory.rng_caller_roles import (
    RNGCallerRoleError,
    validate_rng_caller_role_map_binding,
)
from src.observatory.spawn_coordinate_hw import validate_spawn_coordinate_snapshot


SCHEMA_VERSION = 1
ANALYSIS_KIND = "spawn_coordinate_rng_attribution"

# These are the reviewed direct RNG-core call sites inside the three pinned
# coordinate-selection seams for Windows build 13725832.
CALLER_SPECS = {
    "scheduler_draw": {
        "caller_id": 66,
        "call_rva": "0x001751a6",
        "return_rva": "0x001751ab",
    },
    "selector_fallback_draw": {
        "caller_id": 59,
        "call_rva": "0x00172e16",
        "return_rva": "0x00172e1b",
    },
    "selector_standard_draw": {
        "caller_id": 60,
        "call_rva": "0x00172e70",
        "return_rva": "0x00172e75",
    },
}


class SpawnCoordinateRngError(RuntimeError):
    """Raised when a coordinate draw cannot be uniquely attributed."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpawnCoordinateRngError(f"{label} must be an object")
    return value


def _pinned_return_callers(
    return_map: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    callers = return_map.get("callers")
    if not isinstance(callers, list):
        raise SpawnCoordinateRngError("RNG return map callers are missing")
    result: dict[str, Mapping[str, Any]] = {}
    for kind, spec in CALLER_SPECS.items():
        caller_id = spec["caller_id"]
        if caller_id > len(callers):
            raise SpawnCoordinateRngError(
                f"RNG return map lacks coordinate caller {caller_id}"
            )
        caller = _mapping(callers[caller_id - 1], f"return caller {caller_id}")
        if (
            caller.get("caller_id") != caller_id
            or caller.get("call_rva") != spec["call_rva"]
            or caller.get("return_rva") != spec["return_rva"]
        ):
            raise SpawnCoordinateRngError(
                f"coordinate caller {caller_id} differs from the pinned seam"
            )
        result[kind] = caller
    return result


def match_spawn_coordinate_rng_records(
    rng_records: Sequence[Mapping[str, Any]],
    coordinate_events: Sequence[Mapping[str, Any]],
    *,
    return_map: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Uniquely match each coordinate event by pinned caller and raw result.

    This is the narrow pure join used after both parent artifacts have passed
    their build-keyed validators.  A repeated result at the same direct caller
    is treated as ambiguous instead of selecting a convenient occurrence.
    """
    pinned = _pinned_return_callers(return_map)
    normalized_rng: list[Mapping[str, Any]] = []
    for index, record in enumerate(rng_records):
        item = _mapping(record, f"RNG record {index}")
        if (
            item.get("kind") != "rng_core"
            or item.get("seq") != index
            or type(item.get("caller_id")) is not int
            or type(item.get("result")) is not int
        ):
            raise SpawnCoordinateRngError("RNG records are not contiguous core draws")
        normalized_rng.append(item)

    attributed: list[dict[str, Any]] = []
    for event_index, raw_event in enumerate(coordinate_events):
        event = _mapping(raw_event, f"coordinate event {event_index}")
        kind = event.get("kind")
        if kind not in CALLER_SPECS or type(event.get("raw_rng")) is not int:
            raise SpawnCoordinateRngError(
                f"coordinate event {event_index} has an unsupported shape"
            )
        caller_id = CALLER_SPECS[kind]["caller_id"]
        matches = [
            record
            for record in normalized_rng
            if record["caller_id"] == caller_id
            and record["result"] == event["raw_rng"]
        ]
        if len(matches) != 1:
            qualifier = "missing" if not matches else "ambiguous"
            raise SpawnCoordinateRngError(
                f"coordinate event {event_index} RNG attribution is {qualifier}"
            )
        match = matches[0]
        sequence = match["seq"]
        prefix = normalized_rng[:sequence]
        caller_counts = Counter(item["caller_id"] for item in prefix)
        caller = pinned[kind]
        classification = caller.get("classification")
        attributed.append(
            {
                "coordinate_sequence": event.get("seq"),
                "kind": kind,
                "raw_rng": event["raw_rng"],
                "caller_id": caller_id,
                "call_rva": caller["call_rva"],
                "return_rva": caller["return_rva"],
                "caller_classification": (
                    dict(classification)
                    if isinstance(classification, Mapping)
                    else None
                ),
                "rng_sequence": sequence,
                "rng_ordinal": sequence + 1,
                "thread_slot": match.get("thread_slot"),
                "candidate_count": event.get("candidate_count"),
                "selected_index": event.get("selected_index"),
                "selected": event.get("selected"),
                "candidates": event.get("candidates"),
                "upstream_draw_count": sequence,
                "upstream_caller_counts": {
                    str(key): caller_counts[key] for key in sorted(caller_counts)
                },
                "preceding_rng_window": [
                    {
                        "seq": item["seq"],
                        "caller_id": item["caller_id"],
                        "result": item["result"],
                    }
                    for item in normalized_rng[max(0, sequence - 8) : sequence]
                ],
                "following_rng_window": [
                    {
                        "seq": item["seq"],
                        "caller_id": item["caller_id"],
                        "result": item["result"],
                    }
                    for item in normalized_rng[
                        sequence + 1 : min(len(normalized_rng), sequence + 5)
                    ]
                ],
            }
        )
    sequences = [item["rng_sequence"] for item in attributed]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise SpawnCoordinateRngError(
            "coordinate events do not map monotonically into the RNG stream"
        )
    return attributed


def attribute_spawn_coordinate_rng(
    checkpoint: Mapping[str, Any],
    coordinate_snapshot: Mapping[str, Any],
    *,
    coordinate_build_receipt: Mapping[str, Any],
    coordinate_module_sha256: str,
    return_map: Mapping[str, Any],
    expected_restore_hashes: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and join one same-process combined capture."""
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=checkpoint.get("identity"),
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    if not verification["diagnostic_complete"]:
        raise SpawnCoordinateRngError("RNG checkpoint is not diagnostically complete")
    coordinate = validate_spawn_coordinate_snapshot(
        coordinate_snapshot,
        build_receipt=coordinate_build_receipt,
        observed_module_sha256=coordinate_module_sha256,
    )
    if checkpoint.get("capture_id") != coordinate["capture_id"]:
        raise SpawnCoordinateRngError("combined capture IDs differ")

    rng_identity = _mapping(checkpoint.get("identity"), "checkpoint identity")
    coordinate_identity = _mapping(
        coordinate.get("identity"), "coordinate identity"
    )
    for field in (
        "platform",
        "architecture",
        "build_id",
        "executable_sha256",
        "executable_size",
        "inventory_sha256",
        "boundary_map_sha256",
    ):
        if rng_identity.get(field) != coordinate_identity.get(field):
            raise SpawnCoordinateRngError(
                f"combined observer identity differs for {field}"
            )

    events = match_spawn_coordinate_rng_records(
        checkpoint["records"], coordinate["records"], return_map=return_map
    )
    selector_events = [
        event for event in events if event["kind"].startswith("selector_")
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "capture_id": checkpoint["capture_id"],
        "identity": {
            field: rng_identity[field]
            for field in (
                "platform",
                "architecture",
                "build_id",
                "executable_sha256",
                "executable_size",
                "inventory_sha256",
                "boundary_map_sha256",
            )
        },
        "status": "attributed",
        "events": events,
        "summary": {
            "coordinate_event_count": len(events),
            "selector_event_count": len(selector_events),
            "all_events_uniquely_attributed": True,
            "pinned_direct_callers_verified": True,
            "rng_checkpoint_complete": True,
            "coordinate_observer_restored": True,
            "rng_core_observer_restored": True,
            "selector_rng_ordinals": [
                event["rng_ordinal"] for event in selector_events
            ],
            "selector_caller_ids": [
                event["caller_id"] for event in selector_events
            ],
        },
    }


def compare_spawn_coordinate_rng_attributions(
    analyses: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize which upstream callers vary before the coordinate draw."""
    if not analyses:
        raise SpawnCoordinateRngError("attribution comparison requires captures")
    selectors: list[Mapping[str, Any]] = []
    capture_ids: list[str] = []
    for index, raw in enumerate(analyses):
        analysis = _mapping(raw, f"analysis {index}")
        if (
            analysis.get("schema_version") != SCHEMA_VERSION
            or analysis.get("kind") != ANALYSIS_KIND
            or analysis.get("status") != "attributed"
        ):
            raise SpawnCoordinateRngError(f"analysis {index} is not attributed")
        events = analysis.get("events")
        if not isinstance(events, list):
            raise SpawnCoordinateRngError(f"analysis {index} events are missing")
        selected = [
            event
            for event in events
            if isinstance(event, Mapping)
            and str(event.get("kind", "")).startswith("selector_")
        ]
        if len(selected) != 1:
            raise SpawnCoordinateRngError(
                f"analysis {index} must contain exactly one selector event"
            )
        selectors.append(selected[0])
        capture_ids.append(str(analysis.get("capture_id")))

    all_ids = sorted(
        {
            int(caller_id)
            for selector in selectors
            for caller_id in selector["upstream_caller_counts"]
        }
    )
    varying: list[dict[str, Any]] = []
    for caller_id in all_ids:
        counts = [
            int(selector["upstream_caller_counts"].get(str(caller_id), 0))
            for selector in selectors
        ]
        if min(counts) != max(counts):
            varying.append(
                {
                    "caller_id": caller_id,
                    "counts": counts,
                    "minimum": min(counts),
                    "maximum": max(counts),
                    "spread": max(counts) - min(counts),
                }
            )
    ordinals = [int(selector["rng_ordinal"]) for selector in selectors]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "spawn_coordinate_rng_attribution_comparison",
        "capture_ids": capture_ids,
        "capture_count": len(selectors),
        "selector_caller_ids": [
            int(selector["caller_id"]) for selector in selectors
        ],
        "selector_raw_rng": [int(selector["raw_rng"]) for selector in selectors],
        "selector_rng_ordinals": ordinals,
        "ordinal_stable": len(set(ordinals)) == 1,
        "varying_upstream_callers": varying,
        "classification": (
            "coordinate_direct_caller_resolved_upstream_call_order_variable"
            if len(set(ordinals)) > 1
            else "coordinate_direct_caller_and_ordinal_stable"
        ),
    }


def explain_spawn_coordinate_rng_variation(
    analyses: Sequence[Mapping[str, Any]],
    *,
    caller_role_overlay: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Join variable upstream counts to the reviewed static caller roles."""
    comparison = compare_spawn_coordinate_rng_attributions(analyses)
    try:
        binding = validate_rng_caller_role_map_binding(
            caller_role_overlay,
            return_map,
        )
    except RNGCallerRoleError as exc:
        raise SpawnCoordinateRngError(str(exc)) from exc
    role_entries = caller_role_overlay.get("caller_roles")
    if not isinstance(role_entries, list):
        raise SpawnCoordinateRngError("caller-role overlay roles are missing")

    selectors: list[Mapping[str, Any]] = []
    for index, raw in enumerate(analyses):
        analysis = _mapping(raw, f"analysis {index}")
        events = analysis.get("events")
        if not isinstance(events, list):
            raise SpawnCoordinateRngError(f"analysis {index} events are missing")
        selector = [
            item
            for item in events
            if isinstance(item, Mapping)
            and str(item.get("kind", "")).startswith("selector_")
        ]
        if len(selector) != 1:
            raise SpawnCoordinateRngError(
                f"analysis {index} must contain exactly one selector event"
            )
        selectors.append(selector[0])

    groups: dict[tuple[str, str], list[int]] = {}
    caller_domains: dict[int, str] = {}
    for raw in role_entries:
        entry = _mapping(raw, "caller-role entry")
        caller_id = entry.get("caller_id")
        role_id = entry.get("role_id")
        domain = entry.get("domain")
        if type(caller_id) is not int or type(role_id) is not str or type(domain) is not str:
            raise SpawnCoordinateRngError("caller-role entry has an invalid shape")
        groups.setdefault((role_id, domain), []).append(caller_id)
        caller_domains[caller_id] = domain

    # Caller 21 is already reviewed in the original return map as the native
    # one-argument random_int boundary.  Its Lua origin is not visible at the
    # shared core, so keep it separate from both gameplay and presentation.
    groups[("lua_random_int_boundary", "shared_lua_boundary")] = [21]
    caller_domains[21] = "shared_lua_boundary"

    role_counts: list[dict[str, Any]] = []
    domain_counts: dict[str, list[int]] = {}
    for (role_id, domain), caller_ids in groups.items():
        counts = [
            sum(
                int(selector["upstream_caller_counts"].get(str(caller_id), 0))
                for caller_id in caller_ids
            )
            for selector in selectors
        ]
        if min(counts) == max(counts):
            continue
        role_counts.append(
            {
                "role_id": role_id,
                "domain": domain,
                "caller_ids": caller_ids,
                "counts": counts,
                "minimum": min(counts),
                "maximum": max(counts),
                "spread": max(counts) - min(counts),
            }
        )
        totals = domain_counts.setdefault(domain, [0] * len(selectors))
        for index, count in enumerate(counts):
            totals[index] += count

    varying_ids = {
        int(item["caller_id"])
        for item in comparison["varying_upstream_callers"]
    }
    classified_ids = set(caller_domains)
    unclassified_ids = sorted(varying_ids - classified_ids)
    classified_totals = [
        sum(
            int(selector["upstream_caller_counts"].get(str(caller_id), 0))
            for caller_id in varying_ids & classified_ids
        )
        for selector in selectors
    ]
    ordinals = comparison["selector_rng_ordinals"]
    ordinal_deltas = [value - ordinals[0] for value in ordinals]
    classified_deltas = [
        value - classified_totals[0] for value in classified_totals
    ]
    deltas_accounted = (
        not unclassified_ids and ordinal_deltas == classified_deltas
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "spawn_coordinate_rng_variation_explanation",
        "capture_ids": comparison["capture_ids"],
        "capture_count": comparison["capture_count"],
        "caller_role_overlay_sha256": binding["artifact_sha256"],
        "selector_caller_ids": comparison["selector_caller_ids"],
        "selector_raw_rng": comparison["selector_raw_rng"],
        "selector_rng_ordinals": ordinals,
        "ordinal_deltas_from_first": ordinal_deltas,
        "role_counts": role_counts,
        "domain_counts": [
            {"domain": domain, "counts": counts}
            for domain, counts in domain_counts.items()
        ],
        "classified_varying_caller_ids": sorted(varying_ids & classified_ids),
        "unclassified_varying_caller_ids": unclassified_ids,
        "classified_varying_draw_counts": classified_totals,
        "classified_count_deltas_from_first": classified_deltas,
        "ordinal_deltas_fully_accounted": deltas_accounted,
        "classification": (
            "coordinate_direct_caller_resolved_ordinal_variable_"
            "shared_presentation_rng"
            if deltas_accounted
            and any(item["domain"] == "presentation" for item in role_counts)
            else comparison["classification"]
        ),
    }
