"""Phase 4 P4-1d — stage mined candidates as override drafts.

One layer above ``pattern_miner`` (P4-1a) and ``board_extractor``
(P4-1c). Given the miner's output, this module:

1. Picks candidates that have auto-generatable override dicts.
   Vision-source candidates have stageable fields (damage,
   damage_outer, push, …) that ``_mismatch_to_candidate`` already
   knows how to translate. failure_db candidates are left as
   "needs manual override" pointers — a human has to author the
   Rust patch.

2. Extracts a regression fixture per candidate via P4-1c.

3. Verifies the override actually moves the solver (P4-1c verifier).
   Non-observable drafts get skipped, not staged — otherwise the
   P3-7 gate would reject them in CI anyway.

4. Appends verified drafts to ``data/weapon_overrides_staged.jsonl``
   using the same ``stage_candidates`` path P3-5 uses, so the
   existing ``review_overrides list / accept / reject`` CLI
   (P3-6) promotes / rejects them identically.

What this does NOT do:

- No git branch creation. No ``gh pr create``. That's a follow-up
  once we've validated the staged output on real patterns.
- No auto-commit. The human still has to commit the fixture and
  staged entry deliberately.
- No review bypass. The P3-7 regression gate still gates promotion.

``dry_run=True`` (default) produces the full report with zero disk
writes, zero solver invocations past verification, and zero staging.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.research import board_extractor
from src.research.pattern_miner import MinedCandidate
from src.solver.weapon_overrides import (
    DEFAULT_STAGED_PATH,
    _mismatch_to_candidate,
    stage_candidates,
)


@dataclass
class DraftOutcome:
    """What happened to one candidate on one drafter run."""

    candidate: MinedCandidate
    status: str                        # "staged" | "skipped"
    reason: str                        # human-readable
    fixture_path: Path | None = None
    override_entry: dict | None = None  # what would be / was staged
    verification: dict | None = None    # serialized VerificationResult


@dataclass
class DraftReport:
    outcomes: list[DraftOutcome] = field(default_factory=list)
    dry_run: bool = True

    @property
    def staged_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "staged")

    @property
    def skipped_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "skipped")


# ── candidate → override dict ──────────────────────────────────────────────


def _override_for_candidate(candidate: MinedCandidate) -> dict | None:
    """Build the override dict the drafter would stage for this candidate.

    Vision-source candidates reuse the existing
    ``_mismatch_to_candidate`` path so the staged schema matches what
    P3-5 writes today. failure_db candidates can't auto-generate an
    override (we don't know which field to patch) — return None and
    the drafter skips them with a "manual override required" note.
    """
    sig = candidate.signature
    if sig.source != "vision":
        return None
    sample = next(iter(candidate.sample_entries), None)
    if sample is None:
        return None
    # Reconstruct the minimal mismatch dict `_mismatch_to_candidate` expects.
    mm = {
        "weapon_id": sig.weapon_id,
        "field": sig.field,
        "rust_value": sample.get("rust_value"),
        "vision_value": sample.get("vision_value"),
        "severity": sample.get("severity"),
        "confidence": sample.get("confidence"),
        "display_name": sample.get("display_name"),
    }
    return _mismatch_to_candidate(mm, run_id=sample.get("run_id", ""))


# ── drafter ────────────────────────────────────────────────────────────────


def draft_from_candidates(
    candidates: list[MinedCandidate],
    *,
    dry_run: bool = True,
    verify: bool = True,
    max_stage: int | None = None,
    time_limit: float = 2.0,
    recordings_root: Path | str | None = None,
    output_dir: Path | str | None = None,
    staged_path: Path | str | None = None,
) -> DraftReport:
    """Stage (or report-only) override drafts for mined candidates.

    Ordering: callers pass in candidates already sorted by the miner
    (deterministic). This function walks them in order and applies
    ``max_stage`` as an absolute cap — not a per-weapon quota — so a
    single noisy weapon can't starve the queue of other fixes.

    ``verify=False`` skips the P4-1c verifier (solver import).
    Useful for fast dry-runs or CI smoke tests that don't have the
    wheel installed. When off, every candidate's verification is
    recorded as ``{"skipped": True}``.
    """
    report = DraftReport(dry_run=dry_run)
    stage_path = Path(staged_path) if staged_path is not None else DEFAULT_STAGED_PATH

    staged_so_far = 0
    for cand in candidates:
        if max_stage is not None and staged_so_far >= max_stage:
            report.outcomes.append(DraftOutcome(
                candidate=cand, status="skipped",
                reason=f"max_stage cap reached ({max_stage})",
            ))
            continue

        override = _override_for_candidate(cand)
        if override is None:
            report.outcomes.append(DraftOutcome(
                candidate=cand, status="skipped",
                reason=("no auto-generated override — failure_db "
                        "candidates need a hand-authored Rust patch"),
            ))
            continue

        fixture_path = board_extractor.extract_regression_board(
            cand,
            recordings_root=recordings_root,
            output_dir=output_dir,
            overwrite=False,
        ) if not dry_run else _dry_extract(cand, recordings_root)
        if fixture_path is None:
            report.outcomes.append(DraftOutcome(
                candidate=cand, status="skipped",
                reason=("no recording available for this signature — "
                        "P4-1c extractor returned None"),
                override_entry=override,
            ))
            continue

        verification_dict: dict[str, Any] = {"skipped": True}
        if verify and fixture_path.exists():
            try:
                vr = board_extractor.verify_observable_change(
                    fixture_path, override, time_limit=time_limit,
                )
                verification_dict = {
                    "observable_change": vr.observable_change,
                    "reason": vr.reason,
                    "plan_changed": vr.plan_changed,
                    "score_delta": vr.score_delta,
                }
                if not vr.observable_change:
                    report.outcomes.append(DraftOutcome(
                        candidate=cand, status="skipped",
                        reason=f"verifier: {vr.reason}",
                        fixture_path=fixture_path,
                        override_entry=override,
                        verification=verification_dict,
                    ))
                    continue
            except ImportError:
                # itb_solver not available — treat like verify=False but
                # make it visible in the report so the caller doesn't
                # think every candidate passed.
                verification_dict = {"skipped": True, "reason": "itb_solver not importable"}

        if not dry_run:
            # Stage exactly one representative mismatch — `sample_entries`
            # may hold up to ``sample_cap`` rows, but those are all
            # the same signature; feeding them all in would write
            # duplicate staged entries for the reviewer to wade through.
            stage_candidates(
                cand.sample_entries[:1],
                run_id=_best_run_id(cand),
                path=stage_path,
                severity_threshold=_threshold_for_field(cand.signature.field),
            )
            staged_so_far += 1

        report.outcomes.append(DraftOutcome(
            candidate=cand, status="staged",
            reason=("dry-run — would stage" if dry_run else "appended to staged.jsonl"),
            fixture_path=fixture_path,
            override_entry=override,
            verification=verification_dict,
        ))

    return report


def _dry_extract(cand: MinedCandidate, recordings_root: Path | str | None) -> Path | None:
    """Dry-run extraction: return where the fixture WOULD be written
    without touching disk. Uses the same first-available-ref logic
    as the real extractor so the report reflects reality."""
    from src.research.pattern_miner import DEFAULT_RECORDINGS_ROOT
    rr = Path(recordings_root) if recordings_root is not None else DEFAULT_RECORDINGS_ROOT
    weapon_id = cand.signature.weapon_id
    if not weapon_id or weapon_id.startswith("?:"):
        return None
    for run_id, mission, turn in cand.board_refs:
        if mission < 0 or turn < 0 or not run_id:
            continue
        src = rr / run_id / f"m{int(mission):02d}_turn_{int(turn):02d}_board.json"
        if src.exists():
            # Return a path pointer without writing.
            return board_extractor.DEFAULT_OUTPUT_DIR / f"{weapon_id}_{cand.signature.hash8()}.json"
    return None


def _best_run_id(cand: MinedCandidate) -> str:
    """Return the first non-empty run_id among the candidate's refs.

    Used only for ``source_run_id`` tagging on staged entries; the
    specific run doesn't matter for the patch itself.
    """
    for run_id, _m, _t in cand.board_refs:
        if run_id:
            return run_id
    return ""


def _threshold_for_field(field_name: str) -> str:
    """Map a Vision comparator field to the severity threshold that
    makes ``stage_candidates`` accept it. Damage mismatches come in
    as ``severity=high``; footprint/push hits are lower. Using the
    per-field threshold keeps the drafter behaviour symmetric with
    the miner's own vision-channel threshold choices."""
    if field_name == "damage":
        return "high"
    return "low"
