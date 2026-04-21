"""Protocol gate for the self-healing loop research step.

Pure helper. Given a novelty dict (shape matches
``unknown_detector.detect_unknowns``), return a RESEARCH_REQUIRED error
envelope that tells the harness to run ``cmd_research_next`` before any
solver call. Returns ``None`` when no novelty is present.

Python can't drive ``mcp__computer-use__*`` directly — those are
harness-side tools. So the "inline" part of the self-healing loop is a
detection flag plus a protocol gate, not a blocking Python call. See
``docs/self_healing_loop_design.md`` §Missing wire and CLAUDE.md rule 20.
"""

from __future__ import annotations


def research_gate_envelope(unknowns: dict | None) -> dict | None:
    """Return the RESEARCH_REQUIRED envelope iff ``unknowns`` is non-empty.

    Covers the four novelty axes from ``detect_unknowns``: pawn
    ``types``, ``terrain_ids``, ``weapons``, and ``screens``. Any one
    of them being non-empty trips the gate. Callers pass whichever
    keys are populated; missing keys default to empty.
    """
    if not unknowns:
        return None
    types = list(unknowns.get("types") or [])
    terrain = list(unknowns.get("terrain_ids") or [])
    weapons = list(unknowns.get("weapons") or [])
    screens = list(unknowns.get("screens") or [])
    if not types and not terrain and not weapons and not screens:
        return None
    return {
        "error": "RESEARCH_REQUIRED",
        "unknowns": {
            "types": types,
            "terrain_ids": terrain,
            "weapons": weapons,
            "screens": screens,
        },
        "next": "cmd_research_next",
        "message": (
            "Novelty on the board — research before solving. "
            "See CLAUDE.md rule 20."
        ),
    }
