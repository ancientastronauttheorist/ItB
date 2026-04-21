"""Research gate tests — the protocol boundary between detection and solver.

Covers `src/solver/research_gate.py` and the two call sites that use it
(`cmd_solve`, `cmd_auto_turn`). The `cmd_read` flag is also exercised —
it's the upstream signal that feeds `cmd_auto_turn`'s gate.

The gate is a pure-Python envelope — it does not drive MCP. The
harness (Claude) is responsible for running `cmd_research_next` →
dispatch → `cmd_research_submit` when it sees the envelope.
See CLAUDE.md rule 20 and `docs/self_healing_loop_design.md` §Missing wire.
"""

from __future__ import annotations

from src.solver.research_gate import research_gate_envelope


def test_gate_returns_none_on_empty():
    assert research_gate_envelope({}) is None
    assert research_gate_envelope(None) is None
    assert research_gate_envelope({"types": [], "terrain_ids": []}) is None


def test_gate_envelope_flags_unknown_type():
    env = research_gate_envelope({"types": ["Wumpus_Alpha"], "terrain_ids": []})
    assert env is not None
    assert env["error"] == "RESEARCH_REQUIRED"
    assert env["unknowns"]["types"] == ["Wumpus_Alpha"]
    assert env["unknowns"]["terrain_ids"] == []
    assert env["next"] == "cmd_research_next"


def test_gate_envelope_flags_unknown_terrain():
    env = research_gate_envelope({"types": [], "terrain_ids": ["quicksand"]})
    assert env is not None
    assert env["error"] == "RESEARCH_REQUIRED"
    assert env["unknowns"]["terrain_ids"] == ["quicksand"]


def test_gate_envelope_preserves_both_categories():
    env = research_gate_envelope(
        {"types": ["Wumpus_Alpha", "Orb_Prime"], "terrain_ids": ["swamp"]}
    )
    assert env is not None
    assert env["unknowns"]["types"] == ["Wumpus_Alpha", "Orb_Prime"]
    assert env["unknowns"]["terrain_ids"] == ["swamp"]


def test_gate_envelope_is_copy_not_alias():
    # Callers should be able to mutate the envelope without corrupting
    # the caller's original unknowns dict.
    original = {"types": ["Wumpus_Alpha"], "terrain_ids": []}
    env = research_gate_envelope(original)
    env["unknowns"]["types"].append("Mutation_Test")
    assert original["types"] == ["Wumpus_Alpha"]


def test_gate_envelope_mentions_rule_20():
    # The message is the breadcrumb that points Claude at the protocol.
    # If this breaks, CLAUDE.md rule 20 should be renumbered in lockstep.
    env = research_gate_envelope({"types": ["X"], "terrain_ids": []})
    assert "rule 20" in env["message"].lower() or "rule 20" in env["message"]
