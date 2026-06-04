# Lightning War Experiments

This log tracks Blitzkrieg Lightning War practice work. Use the pattern:
hypothesis -> segment -> evidence -> result -> derived rule -> code/docs update.

## 2026-06-03 - Outer Watchdog Evidence Tightening

Hypothesis: the high-level Python conductor can safely decide whether Codex may
think only if it understands the nested `lightning_pause_guard` result, not just
the top-level `status/reason`.

Segment: offline focused tests while the live run was parked in verified pause.
No combat or UI progression was executed.

Evidence:
- `lightning_ui guard_status` reported `status: OK`, `visible_ui: pause_menu`,
  and a persisted guard JSON before and after the test/edit window.
- `python -m pytest tests\test_lightning_war_conductor.py` passed.
- `python -m pytest tests\test_lightning_war_tools.py` passed.

Result: the outer watchdog now records nested pause-guard evidence, including
post-click `pause_verify`, screenshot paths, classifier crop scores, live bridge
snapshot summaries, timer probes, and the guard JSON path. A bare
`reason=pause_clicked` is no longer treated as safe without classifier or timer
stop proof.

Derived rule: for Lightning War, `safe_to_think=true` requires verified pause or
a proven non-live screen. A click label alone is not proof. When the lower guard
returns a `last_poll`, the conductor must inspect that nested payload because it
contains the real CV/timer proof.

Code/docs update:
- `scripts/lightning_war_conductor.py`
- `tests/test_lightning_war_conductor.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-03 - Setup Screen False Pause Positive

Hypothesis: the `bridge_snapshot_unavailable` practice stop was caused by
starting an instrumented segment from the new-run setup screen while the
Lightning UI classifier mislabeled that setup screen as `pause_menu`.

Segment: `python scripts\lightning_war_conductor.py --max-segments 1
--segment-steps 6 --time-limit 2 --max-wall-seconds 240 --settle-seconds 0`.

Evidence:
- The segment stopped safely with `reason=bridge_snapshot_unavailable` and
  `pause_guard` still safe.
- `lightning_peek bridge_unavailable_pause` captured
  `run_notes/lightning_war_smoke_2026-06-03/screenshots/023_bridge_unavailable_pause.png`.
- The screenshot visibly showed the Blitzkrieg new-run setup screen with Back
  and Start buttons, not the in-game pause menu.
- After the classifier patch, that screenshot classifies as `new_game_setup`
  with strong Back/Start crop scores.

Result: `new_game_setup` detection now runs before pause-menu detection. This
prevents the conductor from trying to resume a setup screen as though it were a
paused live run.

Derived rule: setup is safe to think because the Lightning clock has not started
or the run is parked before Start, but it must be named explicitly. Do not rely
on a generic dark-overlay pause-menu score when the setup Back/Start layout is
visible.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`
