"""Seal a counterbalanced seeded Observatory RNG campaign.

The campaign receipt deliberately separates the narrow Lua-boundary result
from whole-game neutrality.  A return-preserving wrapper can match the seeded
probe while the following native RNG stream still differs; the receipt keeps
those two claims independent and fails closed on any unexpected artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.rng_trial_outcome import compare_rng_trial_outcomes
from src.observatory.rng_trial_result import (
    compare_rng_trial_results,
    validate_rng_trial_result,
)
from src.observatory.trace_codec import parse_trace


RECEIPT_SCHEMA_VERSION = 1
RECEIPT_KIND = "observatory_seeded_rng_campaign_receipt"
PAIR_NAMES = tuple(f"pair{number:03d}" for number in range(7, 13))
PAIR_FILES = frozenset(
    {
        "arm_packet.json",
        "capsule.lua",
        "capture_identity.json",
        "config.json",
        "control_outcome.json",
        "control_result.json",
        "exact_hook_outcome.json",
        "exact_hook_result.json",
        "finalized_trace.json",
        "hook_plan.json",
        "outcome_comparison.json",
        "pair_plan.json",
        "raw_checkpoint.json",
        "result_comparison.json",
    }
)
_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RngCampaignReceiptError(RuntimeError):
    """Raised when a seeded campaign cannot support the bounded receipt."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RngCampaignReceiptError(f"invalid JSON artifact {path}: {exc}") from exc


def _canonical_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise RngCampaignReceiptError(f"receipt is not canonical JSON: {exc}") from exc
    return (encoded + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise RngCampaignReceiptError(
            f"artifact is outside the repository: {path}"
        ) from exc
    payload = path.read_bytes()
    return {
        "path": relative,
        "size": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RngCampaignReceiptError(f"{label} must be an object")
    return value


def _pair_number(name: str) -> int:
    if name not in PAIR_NAMES:
        raise RngCampaignReceiptError(f"unexpected campaign pair {name!r}")
    return int(name[-3:])


def _expected_probe_kind(pair_number: int) -> str:
    return "random_int" if pair_number <= 9 else "random_bool"


def _condition_order(control: Mapping[str, Any], exact: Mapping[str, Any]) -> str:
    control_epoch = control["runtime_before"]["now_epoch"]
    exact_epoch = exact["runtime_before"]["now_epoch"]
    if control_epoch == exact_epoch:
        raise RngCampaignReceiptError("paired condition start times are identical")
    return "control_then_exact" if control_epoch < exact_epoch else "exact_then_control"


def _validate_pair(
    pair_dir: Path,
    *,
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pair_number = _pair_number(pair_dir.name)
    actual_files = frozenset(
        child.name for child in pair_dir.iterdir() if child.is_file()
    )
    if actual_files != PAIR_FILES:
        missing = sorted(PAIR_FILES - actual_files)
        extra = sorted(actual_files - PAIR_FILES)
        raise RngCampaignReceiptError(
            f"{pair_dir.name} artifact set mismatch; missing={missing}, extra={extra}"
        )

    plan = _require_mapping(_load_json(pair_dir / "pair_plan.json"), "pair plan")
    capture_id = plan.get("capture_id")
    if type(capture_id) is not str or _CAPTURE_ID_RE.fullmatch(capture_id) is None:
        raise RngCampaignReceiptError("pair capture_id is invalid")
    probe_kind = _expected_probe_kind(pair_number)
    if (
        plan.get("kind") != "observatory_rng_trial_pair_plan"
        or plan.get("capture_track") != "owner_local_modified"
        or plan.get("probe_kind") != probe_kind
    ):
        raise RngCampaignReceiptError(f"{pair_dir.name} pair plan identity mismatch")

    control = validate_rng_trial_result(
        _load_json(pair_dir / "control_result.json"),
        expected_condition="control",
    )
    exact = validate_rng_trial_result(
        _load_json(pair_dir / "exact_hook_result.json"),
        expected_condition="exact_hook",
    )
    if control["capture_id"] != capture_id or exact["capture_id"] != capture_id:
        raise RngCampaignReceiptError(f"{pair_dir.name} result capture_id mismatch")
    if control["probe"]["kind"] != probe_kind:
        raise RngCampaignReceiptError(f"{pair_dir.name} probe family mismatch")

    direct = compare_rng_trial_results(
        control,
        exact,
        expected_capsule_sha256=control["capsule_sha256"],
        expected_arm_packet_sha256=control["arm_packet_sha256"],
    )
    stored_direct = _load_json(pair_dir / "result_comparison.json")
    if direct != stored_direct or direct.get("status") != "matched":
        raise RngCampaignReceiptError(f"{pair_dir.name} direct comparison drift")

    control_outcome = _load_json(pair_dir / "control_outcome.json")
    exact_outcome = _load_json(pair_dir / "exact_hook_outcome.json")
    outcome = compare_rng_trial_outcomes(
        control_outcome,
        exact_outcome,
        capture_id=capture_id,
    )
    stored_outcome = _load_json(pair_dir / "outcome_comparison.json")
    if outcome != stored_outcome:
        raise RngCampaignReceiptError(f"{pair_dir.name} outcome comparison drift")
    for difference in outcome["differences"]:
        if difference.get("path") != "/spawning_tiles/0/1":
            raise RngCampaignReceiptError(
                f"{pair_dir.name} has an unclassified semantic difference"
            )

    trace = parse_trace(
        (pair_dir / "finalized_trace.json").read_text(encoding="utf-8")
    )
    if (
        trace["capture_identity"]["capture_id"] != capture_id
        or trace["summary"]["accepted_events"] != 1
        or len(trace["events"]) != 1
        or trace["events"][0]["kind"] != probe_kind
        or trace["events"][0]["payload"]["result"] != exact["probe"]["result"]
    ):
        raise RngCampaignReceiptError(f"{pair_dir.name} finalized trace mismatch")

    raw = _require_mapping(
        _load_json(pair_dir / "raw_checkpoint.json"), "raw checkpoint"
    )
    summary = _require_mapping(raw.get("summary"), "raw checkpoint summary")
    attempted = _require_mapping(raw.get("attempted_calls"), "attempted calls")
    if (
        raw.get("capture_id") != capture_id
        or summary.get("accepted_events") != 1
        or summary.get("dropped_events") != 0
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
        or attempted.get(probe_kind) != 1
        or any(value != (1 if kind == probe_kind else 0) for kind, value in attempted.items())
    ):
        raise RngCampaignReceiptError(f"{pair_dir.name} raw checkpoint is not clean")

    artifacts = {
        name.removesuffix(".json").removesuffix(".lua"): _artifact(
            pair_dir / name, repository_root
        )
        for name in sorted(PAIR_FILES)
    }
    order = _condition_order(control, exact)
    expected_order = (
        "exact_then_control" if pair_number % 2 == 1 else "control_then_exact"
    )
    if order != expected_order:
        raise RngCampaignReceiptError(f"{pair_dir.name} counterbalance order drift")

    pair_receipt = {
        "pair": pair_dir.name,
        "capture_id": capture_id,
        "probe_kind": probe_kind,
        "condition_order": order,
        "direct_boundary": {
            "status": "matched",
            "probe": direct["probe"],
            "rng_control": direct["rng_control"],
        },
        "whole_game_outcome": {
            "status": outcome["status"],
            "difference_count": outcome["difference_count"],
            "differences": outcome["differences"],
        },
        "trace_sha256": artifacts["finalized_trace"]["sha256"],
        "artifacts": artifacts,
    }
    runtime_identity = direct["runtime_identity"]
    build_identity = trace["build_identity"]
    return pair_receipt, runtime_identity, build_identity


def build_seeded_rng_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate all six archived pairs and return a deterministic receipt."""
    campaign_root = Path(campaign_root)
    repository_root = Path(repository_root)
    if not campaign_root.is_dir():
        raise RngCampaignReceiptError("campaign root is not a directory")
    actual_dirs = tuple(
        sorted(child.name for child in campaign_root.iterdir() if child.is_dir())
    )
    if actual_dirs != PAIR_NAMES:
        raise RngCampaignReceiptError(
            f"campaign pair set mismatch: expected {PAIR_NAMES}, found {actual_dirs}"
        )

    pairs: list[dict[str, Any]] = []
    runtime_identity: dict[str, Any] | None = None
    build_identity: dict[str, Any] | None = None
    for name in PAIR_NAMES:
        pair, current_runtime, current_build = _validate_pair(
            campaign_root / name,
            repository_root=repository_root,
        )
        if runtime_identity is None:
            runtime_identity = current_runtime
            build_identity = current_build
        elif current_runtime != runtime_identity or current_build != build_identity:
            raise RngCampaignReceiptError(f"{name} campaign identity drift")
        pairs.append(pair)

    assert runtime_identity is not None and build_identity is not None
    matched_outcomes = sum(
        pair["whole_game_outcome"]["status"] == "matched" for pair in pairs
    )
    mismatched_outcomes = len(pairs) - matched_outcomes
    if matched_outcomes != 2 or mismatched_outcomes != 4:
        raise RngCampaignReceiptError("unexpected whole-game outcome distribution")
    helper_hashes = {
        pair["direct_boundary"]["rng_control"]["helper_sha256"] for pair in pairs
    }
    seeds = {pair["direct_boundary"]["rng_control"]["seed"] for pair in pairs}
    if len(helper_hashes) != 1 or seeds != {324508639}:
        raise RngCampaignReceiptError("campaign seed-control identity drift")

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "capture_track": "owner_local_modified",
        "build_identity": build_identity,
        "runtime_identity": runtime_identity,
        "campaign": {
            "pair_count": len(pairs),
            "probe_families": {"random_int": 3, "random_bool": 3},
            "condition_orders": {
                "control_then_exact": 3,
                "exact_then_control": 3,
            },
            "fixed_seed": 324508639,
            "seed_helper_sha256": next(iter(helper_hashes)),
        },
        "results": {
            "direct_boundary_matches": 6,
            "whole_game_matches": matched_outcomes,
            "whole_game_mismatches": mismatched_outcomes,
            "mismatch_scope": ["/spawning_tiles/0/1"],
            "classification": "return_preserving_but_not_whole_game_neutral",
        },
        "claims": {
            "proven": [
                "All six selected one-argument Lua RNG wrappers returned the exact seeded value.",
                "Each exact condition emitted one schema-v2 event and restored its Lua target without conflict.",
                "The six pairs are fresh-state and evenly counterbalanced by condition order.",
            ],
            "not_proven": [
                "Whole-game behavior neutrality of either Lua wrapper.",
                "Complete native RNG call order or caller attribution.",
                "Native spawn-selection RNG semantics.",
            ],
        },
        "pairs": pairs,
        "restore": {
            "save_tree_sha256": runtime_identity["timeline_fingerprint"],
            "save_restored_to_sealed_baseline": True,
            "install_restoration_pending": True,
        },
    }


def publish_seeded_rng_campaign_receipt(
    campaign_root: Path,
    *,
    repository_root: Path,
    output: Path,
) -> tuple[Path, str]:
    """Create one receipt without overwriting an existing artifact."""
    receipt = build_seeded_rng_campaign_receipt(
        campaign_root,
        repository_root=repository_root,
    )
    payload = _canonical_bytes(receipt)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RngCampaignReceiptError(f"receipt already exists: {output}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return output, _sha256_bytes(payload)
