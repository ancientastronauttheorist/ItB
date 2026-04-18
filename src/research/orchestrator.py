"""Between-turn research orchestrator — ties queue → plan → submit.

Python can't drive ``mcp__computer-use__*`` directly (those are
harness-side tools). So the orchestrator exposes a two-step split
that matches how ``cmd_click_action`` / ``cmd_click_end_turn`` work:

1. ``begin_research(session, board)`` — pick the next pending queue
   entry whose type (or terrain) actually appears on the current
   board, resolve its MCP coord, build the capture plan, and mark
   the entry ``in_progress``. Returns ``None`` when nothing to do.

2. ``submit_research(session, research_id, vision_responses, run_id)``
   — parse each crop's Vision JSON, store the merged result on the
   queue entry, optionally run the weapon-def comparator, and mark
   the entry ``done``.

Claude (the harness) dispatches the batch, zooms each crop region,
applies the matching Vision prompt, then calls ``submit_research``
with the raw JSON per crop.

Scope: unit research (enemies and mechs). Terrain-only research is
a later follow-up — the hover plan exists in ``capture.py`` but
orchestrator-side target selection needs a "pick a tile with this
terrain_id" search that's cleaner to add alongside a terrain test
case.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.control.executor import grid_to_mcp
from src.loop.session import RunSession
from src.model.board import Board
from src.research import capture, comparator, vision


# ── target picking ────────────────────────────────────────────────────────


def _find_unit_for_entry(board: Board, entry: dict) -> Any | None:
    """Return a live ``Unit`` whose type matches ``entry['type']``, else None.

    Exact type match is expected — ``detect_unknowns`` wrote the type
    string into the entry, so re-using it here round-trips cleanly.
    """
    type_name = entry.get("type", "")
    if not type_name:
        return None
    for u in board.units:
        if u.hp <= 0:
            continue
        if u.type == type_name:
            return u
    return None


def _crops_for_kind(kind: str) -> tuple[str, ...]:
    """Return the default crop set per target kind.

    Enemies don't surface a weapon_preview on selection — ITB draws
    enemy attack AOE directly on the main board. Mechs show their
    weapon rail in unit_status; the weapon_preview is captured by a
    separate hover plan (future work).
    """
    if kind == "mech":
        return ("name_tag", "unit_status")
    return ("name_tag", "unit_status")


# ── begin / submit ────────────────────────────────────────────────────────


def begin_research(
    session: RunSession,
    board: Board,
    *,
    ui: capture.UiRegions | None = None,
) -> dict | None:
    """Pick the next researchable entry and build its capture plan.

    Skips entries whose target type isn't visible on the current
    board, bumping their ``attempts`` and leaving them ``pending`` so
    a later turn can pick them up when the unit reappears.

    Returns None when the queue has no processable entries.
    """
    if ui is None:
        ui = capture.resolve_ui_regions(capture.load_ui_regions())

    # Pick the first pending entry whose target is on board.
    chosen_entry = None
    chosen_unit = None
    for entry in session.research_queue:
        if entry.get("status") != "pending":
            continue
        unit = _find_unit_for_entry(board, entry)
        if unit is not None:
            chosen_entry = entry
            chosen_unit = unit
            break
        # Target not on board — defer but count the attempt.
        entry["attempts"] = entry.get("attempts", 0) + 1

    if chosen_entry is None or chosen_unit is None:
        return None

    target_mcp = grid_to_mcp(chosen_unit.x, chosen_unit.y)
    kind = "mech" if chosen_unit.is_mech else "enemy"
    crops = _crops_for_kind(kind)
    plan = capture.build_unit_capture_plan(target_mcp=target_mcp, ui=ui, crops=crops)

    research_id = uuid.uuid4().hex[:12]
    # Stash the key fields on the entry so submit_research can look it up
    # without re-doing the search. Dedup key stays (type, terrain_id).
    chosen_entry["status"] = "in_progress"
    chosen_entry["attempts"] = chosen_entry.get("attempts", 0) + 1
    chosen_entry["research_id"] = research_id
    chosen_entry["last_kind"] = kind

    # Prompt templates travel with the plan so the harness knows what
    # to ask Vision per crop. Keeping them inline removes a round-trip
    # back to Python just to fetch prompts.
    prompts = {name: vision.PROMPTS[name] for name in crops if name in vision.PROMPTS}

    return {
        "research_id": research_id,
        "target": {
            "type": chosen_entry.get("type"),
            "terrain_id": chosen_entry.get("terrain_id"),
            "kind": kind,
            "position_bridge": [chosen_unit.x, chosen_unit.y],
            "target_mcp": list(target_mcp),
        },
        "plan": plan,
        "prompts": prompts,
        "next_step": (
            "dispatch plan.batch via computer_batch, zoom each "
            "plan.crops[i].region, apply prompts[crop_name] to produce "
            "JSON per crop, then call cmd_research_submit with the "
            "research_id and {crop_name: json_string} dict"
        ),
    }


def _lookup_by_research_id(session: RunSession, research_id: str) -> dict | None:
    for entry in session.research_queue:
        if entry.get("research_id") == research_id:
            return entry
    return None


def submit_research(
    session: RunSession,
    research_id: str,
    vision_responses: dict[str, Any],
    *,
    run_id: str = "",
    mismatches_path: Any = None,
    confidence_floor: float = 0.5,
) -> dict:
    """Parse Vision JSONs, store on entry, run comparator, mark done.

    ``vision_responses`` keys: ``name_tag``, ``unit_status``,
    ``weapon_preview``, ``terrain_tooltip``. Each value is either a
    raw string (Claude's JSON output) or an already-parsed dict.
    Missing crops are fine — the parser handles empty input by
    returning a zero-confidence placeholder.

    Comparator runs only on ``weapon_preview`` (the regression
    harness target). Everything else just populates the result dict
    for later analysis.
    """
    entry = _lookup_by_research_id(session, research_id)
    if entry is None:
        return {"error": f"unknown research_id: {research_id}"}

    parsed: dict[str, Any] = {}
    for crop_name, raw in (vision_responses or {}).items():
        parser = vision.PARSERS.get(crop_name)
        if parser is None:
            continue
        parsed[crop_name] = parser(raw)

    mismatches: list[dict] = []
    weapon_parsed = parsed.get("weapon_preview")
    if weapon_parsed is not None:
        mismatches = comparator.compare_and_log(
            weapon_parsed,
            path=mismatches_path,
            run_id=run_id,
            confidence_floor=confidence_floor,
        )

    # Decide final status. If every returned crop was below the wiki
    # fallback threshold we mark "failed" so the next turn can either
    # retry (via re-enqueue) or hand off to the wiki client. Otherwise
    # the entry is "done" and the result is cached for post-run analysis.
    trustworthy = any(
        p.get("confidence", 0.0) > confidence_floor
        for p in parsed.values()
    )
    final_status = "done" if trustworthy else "failed"

    session.mark_research(
        entry.get("type", ""),
        entry.get("terrain_id"),
        final_status,
        result={
            "parsed": parsed,
            "mismatches": mismatches,
        },
    )
    # Keep research_id around in the stored entry — post-hoc analysis
    # joins mismatches back to the triggering research call.
    entry["research_id"] = research_id

    return {
        "research_id": research_id,
        "status": final_status,
        "parsed": parsed,
        "mismatches": mismatches,
    }
