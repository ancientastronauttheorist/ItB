"""Self-healing loop Phase 2 research pipeline.

Exposes capture-plan builders and the (soon-to-land) Vision extractor
for the between-turn research processor. See
``docs/self_healing_loop_design.md#research`` for the flow.

Nothing in this package runs during a combat turn — the orchestrator
must only call these between turns, between missions, or from a
non-combat screen (visual stall + recursion risk otherwise).
"""
