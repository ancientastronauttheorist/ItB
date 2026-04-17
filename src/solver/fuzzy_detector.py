"""Self-healing loop — fuzzy signal detector.

Wired from ``cmd_auto_turn`` immediately after ``classify_diff``. For each
per-sub-action desync, ``evaluate`` returns a JSON-safe dict carrying:

- the existing ``classify_diff`` output,
- a stable ``signature`` string for frequency dedup,
- a ``frequency`` count of how often that signature has fired this run
  (reading ``prior_events`` — the session's ``failure_events_this_run``
  window as of the *previous* desync),
- an ``asymmetry`` list describing unit-alive flips
  (``enemy_survived_unexpectedly`` etc.) — the single most diagnostic
  cue for "solver thinks it killed this Vek but it's still there",
- a ``proposed_tier`` / ``confidence`` pair the caller can act on
  (tier 1 = re-solve, already in place; tier 2 = soft-disable;
  tier 4 = narrate; see ``docs/self_healing_loop_design.md`` §Response).

Topology (diff-vs-AOE footprint check) is a deliberate TODO: the Rust
``WeaponDef`` footprint tables aren't exposed to Python yet, and doing
that properly is Phase 2 / P1-3 work. The field is included in the
output with ``None`` so downstream readers don't need a shape migration
when it lands.

Design principles:
- Pure function. No session mutation, no I/O. Caller reads the result
  and decides whether to mutate ``session.disabled_actions``.
- JSON-safe. Every field round-trips through ``json.dumps``.
- Forward-compatible shape. Fields not yet populated are ``None`` or
  empty list; never missing.
"""

from __future__ import annotations

from typing import Any, Iterable

# Categories that indicate a weapon-behavior drift worth soft-disabling
# rather than just re-solving. Click-miss and mech-position-wrong are
# execution bugs (Tier 1 — re-solve handles them); terrain / tile_status
# are frequently environmental (dust, acid pools) and hard to blame on
# one weapon. The list can grow as patterns emerge from the corpus.
_WEAPON_DRIFT_CATEGORIES = frozenset({
    "push_dir",
    "damage_amount",
    "grid_power",
    "death",
    "status",
})

# Frequency at which a weapon-drift category escalates from narrate
# (tier 4) to soft-disable (tier 2). Chosen conservative: two confirmed
# desyncs in a single run on the same (weapon, category, sub_action)
# signature is already strong evidence the sim is wrong, and three
# would waste a whole turn before we reacted.
_SOFT_DISABLE_THRESHOLD = 2


def _signature(
    classification: dict,
    context: dict,
) -> str:
    """Build a stable dedup key for frequency counting.

    Combines the category dimension with the most specific provenance we
    have at the hook site: the weapon and the sub-action. Mech uid and
    action index deliberately excluded — we want a Punch Mech pushing
    wrong on turn 3 and turn 5 to count as the same signature.
    """
    top = classification.get("top_category", "unknown")
    weapon = context.get("weapon") or ""
    sub = context.get("sub_action") or context.get("phase") or "unknown"
    return f"{top}|{weapon}|{sub}"


def _count_matching(prior_events: Iterable[dict], signature: str) -> int:
    """How many prior events share this signature? Lower bound on frequency.

    The caller is expected to pass the in-memory window; the detector does
    not reach back to failure_db.jsonl. Keeps evaluate() pure + cheap.
    """
    return sum(1 for ev in prior_events or [] if ev.get("signature") == signature)


def _detect_asymmetry(diff: Any) -> list[str]:
    """Classify unit alive-flips into direction-aware asymmetry tags.

    Every non-empty entry points at a specific solver mis-prediction the
    Phase 2 research pipeline can investigate:

    - ``enemy_survived_unexpectedly``: we expected the kill, it didn't
      happen. Usually armor / shield / frozen we missed.
    - ``enemy_died_unexpectedly``: game killed something we didn't
      expect to die. Fire tick, push-into-water we missed, chain effect.
    - ``mech_*``: same shape but for player units. Higher severity.
    """
    tags: set[str] = set()
    for ud in getattr(diff, "unit_diffs", []) or []:
        if ud.get("field") != "alive":
            continue
        predicted = ud.get("predicted")
        actual = ud.get("actual")
        utype = (ud.get("type") or "")
        is_mech = "Mech" in utype  # bridge convention: mech types contain "Mech"
        actor = "mech" if is_mech else "enemy"
        if predicted is True and actual is False:
            tags.add(f"{actor}_died_unexpectedly")
        elif predicted is False and actual is True:
            tags.add(f"{actor}_survived_unexpectedly")
    return sorted(tags)


def _propose_response(
    classification: dict,
    frequency: int,
    asymmetry: list[str],
) -> tuple[int, float]:
    """Pick a response tier + confidence from the signal dimensions.

    Tier semantics (``docs/self_healing_loop_design.md`` §Response):
      1 — re-solve (already handled by cmd_auto_turn's inline path)
      2 — soft-disable the suspect weapon
      4 — narrate and continue (no mitigation)
    Tier 3 (JSON weapon override) is intentionally not returned here —
    that's Phase 3, gated on tests/weapon_overrides/ regression boards.

    Confidence is the probability the proposed tier is the right call,
    not the probability of the signal being real. Used downstream by the
    narrator and by the blocklist writer as a dampener.
    """
    top = classification.get("top_category", "unknown")
    model_gap = bool(classification.get("model_gap", False))

    # Execution bugs — re-solve path already handles them. No extra response.
    if top in ("click_miss", "mech_position_wrong"):
        return 1, 0.8

    # Weapon-drift pattern with enough evidence to soft-disable.
    if top in _WEAPON_DRIFT_CATEGORIES and frequency + 1 >= _SOFT_DISABLE_THRESHOLD:
        # Confidence grows with frequency but caps — a pattern seen 5x
        # isn't meaningfully more confident than 3x at tier-2 granularity.
        conf = min(0.5 + 0.1 * (frequency + 1), 0.9)
        return 2, conf

    # Known model gap that's already tagged — narrate is all we can do
    # until there's a Python sim fix or a JSON override.
    if model_gap:
        return 4, 0.7

    # First occurrence of a weapon-drift category: narrate, watch for
    # recurrence next turn.
    if top in _WEAPON_DRIFT_CATEGORIES:
        return 4, 0.4

    return 4, 0.3


def evaluate(
    diff: Any,
    classification: dict,
    context: dict | None = None,
    prior_events: Iterable[dict] | None = None,
) -> dict:
    """Score a per-sub-action desync and propose a response.

    Args:
        diff: ``DiffResult`` from ``src.solver.verify.diff_states``. Only
            ``unit_diffs`` is read directly (for asymmetry); ``classify_diff``
            already summarized everything else.
        classification: Output of ``src.solver.verify.classify_diff``.
        context: Caller-supplied provenance — ``mech_uid``, ``phase``,
            ``sub_action``, ``action_index``, ``turn``, ``weapon``, ``target``.
            Passed through to the result so downstream log readers can
            reconstruct origin without rejoining against failure_db.
        prior_events: Iterable of prior fuzzy-signal dicts from this run
            (``session.failure_events_this_run`` at the hook site). Not
            mutated. If None, frequency is 0.

    Returns:
        JSON-serializable dict with ``version: 1`` shape. See module
        docstring for field semantics.
    """
    ctx = dict(context or {})
    signature = _signature(classification, ctx)
    frequency = _count_matching(prior_events or [], signature)
    asymmetry = _detect_asymmetry(diff)
    proposed_tier, confidence = _propose_response(classification, frequency, asymmetry)

    out = {
        "version": 1,
        "top_category": classification.get("top_category"),
        "categories": list(classification.get("categories", [])),
        "subcategory": classification.get("subcategory"),
        "model_gap": bool(classification.get("model_gap", False)),
        "signature": signature,
        "frequency": frequency,
        "asymmetry": asymmetry,
        "topology": None,  # TODO(P1-3+): diff-vs-AOE footprint check
        "proposed_tier": proposed_tier,
        "confidence": confidence,
        "context": ctx,
    }
    return out
