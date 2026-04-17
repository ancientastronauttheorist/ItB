"""Self-healing loop — fuzzy signal detector (Phase 0 stub).

This is the seam between the mature ``classify_diff`` pipeline and the
richer signal model described in ``docs/self_healing_loop_design.md``
(Detection section). Phase 0 ships the interface only: ``evaluate``
takes the same inputs the design's detector will eventually consume
and returns a dict that carries the classification forward unchanged.

Nothing downstream depends on the extra fields yet. The hook in
``cmd_auto_turn`` appends every return value onto
``session.failure_events_this_run`` and attaches it to the failure_db
record as ``fuzzy_signal``, so real runs start producing a corpus
we can mine when Phase 1 (#P1-1) fleshes out the logic.

Planned future fields (see design doc §Detection):
    - diff_topology:        inside/outside the action's AOE footprint
    - asymmetry:            over- vs under-estimate of kills
    - frequency:            how often this signature has fired this run
    - proposed_tier:        1 (re-solve) / 2 (soft-disable) / 4 (narrate)
    - confidence:           0–1 for the proposed response
"""

from __future__ import annotations

from typing import Any


def evaluate(
    diff: Any,
    classification: dict,
    context: dict | None = None,
) -> dict:
    """Return a fuzzy-signal dict for a single per-sub-action desync.

    Args:
        diff: ``DiffResult`` from ``src.solver.verify.diff_states``. The
            stub doesn't inspect it; Phase 1 will use ``diff.tile_diffs``
            topology and unit kill/survive asymmetry.
        classification: Output of ``src.solver.verify.classify_diff`` —
            ``{top_category, categories, subcategory, model_gap}``.
        context: Optional caller-supplied context (``mech_uid``, ``phase``,
            ``action_index``, ``turn``, ``sub_action``). Passed through to
            the result so log readers can reconstruct origin without
            re-joining against the failure_db record.

    Returns:
        A JSON-serializable dict. For Phase 0 this is essentially the
        classification plus the context — same shape Phase 1 will extend.
    """
    ctx = dict(context or {})
    return {
        "version": 0,
        "top_category": classification.get("top_category"),
        "categories": list(classification.get("categories", [])),
        "subcategory": classification.get("subcategory"),
        "model_gap": bool(classification.get("model_gap", False)),
        "context": ctx,
    }
