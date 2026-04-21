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
from src.research import capture, community_fetch, comparator, vision, wiki_client


# ── gate predicate ────────────────────────────────────────────────────────


def _has_terrain_on_board(board: Board, terrain_id: str) -> bool:
    """Return True if any 8x8 tile has the given terrain id."""
    tiles = getattr(board, "tiles", None)
    if tiles is None:
        return False
    for x in range(8):
        for y in range(8):
            try:
                if tiles[x][y].terrain == terrain_id:
                    return True
            except (IndexError, KeyError, TypeError):
                continue
    return False


def has_actionable_research(session: RunSession, board: Board) -> bool:
    """True iff a pending non-background entry is resolvable right now.

    Used by ``cmd_read`` to fire the research gate when the queue
    carries entries that detect_unknowns didn't flag this turn — most
    notably ``kind="behavior_novelty"`` entries enqueued during a prior
    turn's per-sub-action desync handling.

    Background kinds that do not trip the gate:

    - ``mech_weapon`` — weapon-def regression probe, auto-enqueued for
      every live mech. Resolved opportunistically via
      ``research_probe_mech``; not a reason to block the solver.

    Gate-triggering kinds (``None`` / ``behavior_novelty`` / ``enemy_weapon``
    / ``screen`` / terrain-only): require a live target on the board
    for unit-keyed entries, or terrain presence for terrain-only entries.
    Weapon + screen entries are gate-worthy on their own but get
    re-flagged by ``detect_unknowns`` every turn they remain novel, so
    we need not re-check them here.
    """
    for entry in session.research_queue:
        if entry.get("status") != "pending":
            continue
        if entry.get("kind") == "mech_weapon":
            continue  # background probe
        if _find_unit_for_entry(board, entry) is not None:
            return True
        terrain_id = entry.get("terrain_id")
        if terrain_id and _has_terrain_on_board(board, terrain_id):
            return True
    return False


# ── research_id assignment ────────────────────────────────────────────────


def _assign_or_reuse_research_id(entry: dict) -> tuple[str, bool]:
    """Return ``(research_id, is_new)`` for an entry about to be processed.

    If the entry is already ``in_progress`` and carries a
    ``research_id``, reuse it. That lets idempotent callers (CLI
    scripts, testing loops) invoke ``begin_*`` multiple times without
    orphaning earlier IDs — the stored ID stays stable, and
    ``attempts`` doesn't double-count.

    Otherwise generate a fresh UUID, which the caller will write
    back onto the entry along with any status/attempts bookkeeping.
    """
    if entry.get("status") == "in_progress":
        existing = entry.get("research_id")
        if isinstance(existing, str) and existing:
            return existing, False
    new_id = uuid.uuid4().hex[:12]
    entry["research_id"] = new_id
    return new_id, True


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


def _find_terrain_tile(board: Board, terrain_id: str) -> tuple[int, int] | None:
    """Return the first (x, y) bridge coord whose tile matches ``terrain_id``.

    Terrain-only research entries (``type=""``, ``terrain_id="quicksand"``)
    target a tile rather than a unit. The first matching tile wins —
    multiple tiles of the same novel terrain share a tooltip, so picking
    any one is sufficient.
    """
    if not terrain_id:
        return None
    tiles = getattr(board, "tiles", None)
    if tiles is None:
        return None
    for x in range(8):
        for y in range(8):
            try:
                if tiles[x][y].terrain == terrain_id:
                    return (x, y)
            except (IndexError, KeyError, TypeError):
                continue
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

    # Pick the first pending entry whose target is resolvable on the
    # current board. Unit entries need a live matching unit; terrain-
    # only entries (type="", terrain_id=X) need a tile with that terrain.
    chosen_entry = None
    chosen_unit = None
    chosen_tile: tuple[int, int] | None = None
    for entry in session.research_queue:
        if entry.get("status") != "pending":
            continue
        type_name = entry.get("type", "")
        terrain_id = entry.get("terrain_id")

        if type_name:
            unit = _find_unit_for_entry(board, entry)
            if unit is not None:
                chosen_entry = entry
                chosen_unit = unit
                break
            entry["attempts"] = entry.get("attempts", 0) + 1
            continue

        if terrain_id:
            tile = _find_terrain_tile(board, terrain_id)
            if tile is not None:
                chosen_entry = entry
                chosen_tile = tile
                break
            entry["attempts"] = entry.get("attempts", 0) + 1
            continue

        # Malformed entry (no type, no terrain) — defer silently.
        entry["attempts"] = entry.get("attempts", 0) + 1

    if chosen_entry is None:
        return None

    # Branch on unit vs terrain target.
    if chosen_unit is not None:
        target_mcp = grid_to_mcp(chosen_unit.x, chosen_unit.y)
        kind = "mech" if chosen_unit.is_mech else "enemy"
        crops = _crops_for_kind(kind)
        plan = capture.build_unit_capture_plan(
            target_mcp=target_mcp, ui=ui, crops=crops,
        )
        prompts = {
            name: vision.PROMPTS[name]
            for name in crops if name in vision.PROMPTS
        }
        position_bridge = [chosen_unit.x, chosen_unit.y]
        next_step = (
            "dispatch plan.batch via computer_batch, zoom each "
            "plan.crops[i].region, apply prompts[crop_name] to produce "
            "JSON per crop, then call cmd_research_submit with the "
            "research_id and {crop_name: json_string} dict"
        )
    else:
        assert chosen_tile is not None  # picker invariant
        bx, by = chosen_tile
        target_mcp = grid_to_mcp(bx, by)
        kind = "terrain"
        plan = capture.build_terrain_hover_plan(tile_mcp=target_mcp, ui=ui)
        prompts = {"terrain_tooltip": vision.PROMPTS["terrain_tooltip"]}
        position_bridge = [bx, by]
        next_step = (
            "dispatch plan.batch via computer_batch, zoom "
            "plan.crops[0].region (terrain_tooltip), apply "
            "prompts.terrain_tooltip to produce JSON, then call "
            "cmd_research_submit with the research_id and "
            '{"terrain_tooltip": json_string}'
        )

    research_id = uuid.uuid4().hex[:12]
    # Stash the key fields on the entry so submit_research can look it up
    # without re-doing the search. Dedup key stays (type, terrain_id, kind, slot).
    chosen_entry["status"] = "in_progress"
    chosen_entry["attempts"] = chosen_entry.get("attempts", 0) + 1
    chosen_entry["research_id"] = research_id
    chosen_entry["last_kind"] = kind

    return {
        "research_id": research_id,
        "target": {
            "type": chosen_entry.get("type"),
            "terrain_id": chosen_entry.get("terrain_id"),
            "kind": kind,
            "position_bridge": position_bridge,
            "target_mcp": list(target_mcp),
        },
        "plan": plan,
        "prompts": prompts,
        "next_step": next_step,
    }


def _find_mech_at(board: Board, bridge_x: int, bridge_y: int) -> Any | None:
    """Return the live mech at the given bridge coord, or None."""
    for u in board.units:
        if u.hp <= 0:
            continue
        if not getattr(u, "is_mech", False):
            continue
        if u.x == bridge_x and u.y == bridge_y:
            return u
    return None


def begin_weapon_probe(
    session: RunSession,
    board: Board,
    bridge_x: int,
    bridge_y: int,
    slot: int,
    *,
    ui: capture.UiRegions | None = None,
) -> dict:
    """Start a one-shot weapon-slot probe for the mech at ``(bridge_x, bridge_y)``.

    Unlike ``begin_research`` (queue-driven), this is called directly
    by the ``research_probe_mech`` CLI — the harness decides which
    mech and which slot. We still record the probe on
    ``session.research_queue`` with ``kind="mech_weapon"`` so
    ``submit_research`` can look it up by ``research_id`` and so the
    same tuple isn't probed twice in a mission.

    Returns a plan envelope identical in shape to ``begin_research``
    so the harness can dispatch either one uniformly. Validation
    failures return ``{"error": ...}`` instead — the CLI layer prints
    them.
    """
    if ui is None:
        ui = capture.resolve_ui_regions(capture.load_ui_regions())

    unit = _find_mech_at(board, bridge_x, bridge_y)
    if unit is None:
        return {"error": f"No live mech at bridge ({bridge_x},{bridge_y})"}

    icon_positions = capture.weapon_icon_positions(ui)
    if slot < 0 or slot >= len(icon_positions):
        return {
            "error": (
                f"slot {slot} out of range "
                f"(mech has {len(icon_positions)} weapon slots)"
            )
        }

    target_mcp = grid_to_mcp(unit.x, unit.y)
    icon_mcp = icon_positions[slot]
    plan = capture.build_weapon_probe_plan(
        target_mcp=target_mcp,
        weapon_icon_mcp=icon_mcp,
        ui=ui,
    )

    # Idempotent queue entry: per-mech-type per-slot. If this probe
    # already ran this mission, ``enqueue_research`` returns False and
    # we reuse the existing entry so ``submit_research`` can still
    # look it up by research_id below.
    mech_type = getattr(unit, "type", "")
    turn = getattr(session, "current_turn", 0)
    session.enqueue_research(
        mech_type, None, turn,
        kind="mech_weapon", slot=slot,
    )
    entry = None
    for e in session.research_queue:
        if (
            e.get("type") == mech_type
            and e.get("kind") == "mech_weapon"
            and e.get("slot") == slot
        ):
            entry = e
            break
    if entry is None:
        # Shouldn't happen — enqueue_research just ran. Defensive
        # fallback so we never return a plan with no backing entry.
        return {"error": "failed to materialize research queue entry"}

    research_id, is_new = _assign_or_reuse_research_id(entry)
    if is_new:
        entry["status"] = "in_progress"
        entry["attempts"] = entry.get("attempts", 0) + 1
    entry["last_kind"] = "mech_weapon"

    prompts = {"weapon_preview": vision.PROMPTS["weapon_preview"]}

    return {
        "research_id": research_id,
        "target": {
            "type": mech_type,
            "terrain_id": None,
            "kind": "mech_weapon",
            "slot": slot,
            "position_bridge": [unit.x, unit.y],
            "target_mcp": list(target_mcp),
            "weapon_icon_mcp": list(icon_mcp),
        },
        "plan": plan,
        "prompts": prompts,
        "next_step": (
            "dispatch plan.batch via computer_batch, zoom "
            "plan.crops[0].region (weapon_preview), apply "
            "prompts.weapon_preview to produce JSON, then call "
            "cmd_research_submit with the research_id and "
            '{"weapon_preview": json_string}'
        ),
    }


def _lookup_by_research_id(session: RunSession, research_id: str) -> dict | None:
    for entry in session.research_queue:
        if entry.get("research_id") == research_id:
            return entry
    return None


def _pick_wiki_title(entry: dict, parsed: dict) -> str | None:
    """Pick the best page title for a wiki fallback lookup.

    Preference order: ``weapon_preview.name`` (when probing a weapon
    slot) → ``name_tag.name`` (unit probes) → ``entry["type"]``
    (what the queue was originally keyed on). Returns None when no
    candidate is usable — in that case wiki fallback is skipped.
    """
    for crop_name in ("weapon_preview", "name_tag"):
        crop = parsed.get(crop_name) or {}
        candidate = crop.get("name")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    et = (entry.get("type") or "").strip()
    return et or None


def _try_wiki_fallback(
    entry: dict,
    parsed: dict,
    *,
    fetcher: Any = None,
    cache_dir: Any = None,
) -> dict | None:
    """Run a best-effort wiki lookup for a low-confidence submission.

    Returns the wiki payload (non-empty dict) on success, or None
    when no title could be picked, the page didn't exist, or the
    fetch raised. The caller decides what to do with the payload —
    currently we only stash it on the entry as a diagnostic, upgrade
    the status to "done", and mark the source as "wiki" so downstream
    filters can distinguish Vision-verified from wiki-fallback data.
    """
    title = _pick_wiki_title(entry, parsed)
    if title is None:
        return None
    try:
        payload = wiki_client.fetch_weapon(
            title, fetcher=fetcher, cache_dir=cache_dir,
        )
    except Exception:
        return None
    if not payload:
        return None
    return payload


def submit_research(
    session: RunSession,
    research_id: str,
    vision_responses: dict[str, Any],
    *,
    run_id: str = "",
    mismatches_path: Any = None,
    confidence_floor: float = 0.5,
    wiki_fallback: bool = True,
    wiki_fetcher: Any = None,
    wiki_cache_dir: Any = None,
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

    When every parser returned confidence ≤ ``confidence_floor`` and
    ``wiki_fallback`` is enabled, the function retries via
    ``wiki_client.fetch_weapon`` before marking the entry failed.
    A hit upgrades the status to ``done`` with
    ``result["source"] = "wiki"``; a miss leaves it ``failed``.
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
    staged_candidates: list[dict] = []
    weapon_parsed = parsed.get("weapon_preview")
    if weapon_parsed is not None:
        mismatches = comparator.compare_and_log(
            weapon_parsed,
            path=mismatches_path,
            run_id=run_id,
            confidence_floor=confidence_floor,
        )
        # Phase 3 P3-5: auto-stage high-severity mismatches with
        # stageable fields (currently just ``damage``) into
        # data/weapon_overrides_staged.jsonl. The CLI
        # ``game_loop.py review_overrides`` promotes these after a
        # human approves — we never auto-commit to the base file.
        if mismatches:
            from src.solver.weapon_overrides import stage_candidates
            staged_candidates = stage_candidates(mismatches, run_id=run_id)

    # Decide final status. If every returned crop was below the wiki
    # fallback threshold we mark "failed" so the next turn can either
    # retry (via re-enqueue) or hand off to the wiki client. Otherwise
    # the entry is "done" and the result is cached for post-run analysis.
    trustworthy = any(
        p.get("confidence", 0.0) > confidence_floor
        for p in parsed.values()
    )
    source = "vision"
    wiki_payload: dict | None = None
    if trustworthy:
        final_status = "done"
    else:
        if wiki_fallback:
            wiki_payload = _try_wiki_fallback(
                entry, parsed,
                fetcher=wiki_fetcher, cache_dir=wiki_cache_dir,
            )
        if wiki_payload:
            final_status = "done"
            source = "wiki"
        else:
            final_status = "failed"

    result_payload: dict[str, Any] = {
        "parsed": parsed,
        "mismatches": mismatches,
        "source": source,
    }
    if wiki_payload is not None:
        result_payload["wiki_fallback"] = wiki_payload
    if staged_candidates:
        result_payload["staged_candidates"] = staged_candidates

    # Missing wire #4: emit community-fetch query URLs so the harness
    # can WebFetch Steam discussions + r/IntoTheBreach and persist
    # excerpts via cmd_research_attach_community. Best-effort — only
    # emit when we have a usable target name.
    community_title = _pick_wiki_title(entry, parsed)
    if community_title:
        queries = community_fetch.build_queries(community_title)
        if queries:
            result_payload["community_queries"] = {
                "target_name": community_title,
                "queries": queries,
            }

    session.mark_research(
        entry.get("type", ""),
        entry.get("terrain_id"),
        final_status,
        result=result_payload,
        kind=entry.get("kind"),
        slot=entry.get("slot"),
    )
    # Keep research_id around in the stored entry — post-hoc analysis
    # joins mismatches back to the triggering research call.
    entry["research_id"] = research_id

    return {
        "research_id": research_id,
        "status": final_status,
        "source": source,
        "parsed": parsed,
        "mismatches": mismatches,
        "wiki_fallback": wiki_payload,
        "staged_candidates": staged_candidates,
        "community_queries": result_payload.get("community_queries"),
    }
