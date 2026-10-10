# Lightning War Next Action

## Best Next Action

Ask the user to resolve the macOS prompt shown in:

```text
run_notes/lightning_war_smoke_2026-06-21/screenshots/106_speed_attempt3_privacy_prompt_pause_0135.png
```

After it is authorized or dismissed, capture fresh visible setup/timer proof,
recover or abandon to verified setup, then rerun:

```bash
python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3
```

The Airstrike OCR fix is already applied and verified, so the next speed run
should not block a Tides preview merely because `Protect the Emergency
Batteries` is visible.

Standalone resume segments now load/save the session route-probe cache. If a
resume is needed after prompt resolution and fresh proof, prefer the emitted
`primary_next_command`; it should avoid reprobing candidates already learned
bad by the runner.

Cache writes are limited to real failed route-start probes; successful starts
and dry-runs do not mutate the session route-probe cache.
Explicit `route_probe_cache` inputs bypass session cache loading, so runner or
test callers can still provide an exact cache context.
Hard-prune cache entries require exact first-island, routing, and mission-index
scope; missing or mismatched scope falls back to a fresh probe.
Blank session island scope also falls back to probing, which is slower but
safer than pruning across an unknown route context.

## Watch Points

- Timer truth is screenshot/OCR only.
- Do not run live UI/screenshot/game commands while the macOS prompt is
  unresolved.
- Route-probe cache is selection/ranking only, never Start Mission authority.
- Stale conflict-cache entries from the old Airstrike/Tides matcher are ignored
  unless they carry a still-valid unknown OCR reason.
- Do not use route-probe cache across islands, routing modes, or mission
  indices; scope mismatches are deliberately non-pruning.
- Do not broaden OCR starts. Solar, Airstrike, and Volatile remain veto-only;
  Force/Tides authority still requires visible Start Mission and post-start
  mission-id proof.
- Stop on missing timer proof, route mismatch, external prompts, research,
  safety/desync, terminal text, or screenshot-proven segment over `0:03:00`.

## Next Prompt

`/goal continue: Lightning War Blitzkrieg. Latest speed ladder ran three precombat attempts: 20260621_224439_478 Airstrike veto, 20260621_224949_737 OCR conflict, and 20260621_225418_964 repeated OCR conflict then stopped on a real macOS private-window/screen-audio prompt. Strong terminal proof screenshots are 107_airstrike_terminal_pause_0139, 108_conflict_terminal_pause_0149, and 106_privacy_prompt_pause_0135; prefer those visible screenshots over telemetry clock fields. Do not run live UI/screenshot/game commands until the user resolves the macOS prompt. This loop narrowed Airstrike visible-preview OCR to only air support; Protect the Emergency Batteries is not Airstrike identity because it appeared on a Tides preview, emergency-battery text alone is regression-tested as UNKNOWN, stale conflicting-OCR cache entries are ignored, standalone route-auto-start segments now consume/save session route-probe cache, cache writes are limited to real failed route-start probes, explicit route_probe_cache inputs bypass session cache loading, and route-probe hard-prunes now require exact first-island/routing/mission-index scope with blank session island treated as non-pruning. py_compile passed and focused route/OCR/cache pytest passed (16 passed, 535 deselected). Next: after user resolves the prompt, capture fresh visible proof, reset/recover to verified setup, then run python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3. Stop on route mismatch, ambiguous Start Mission/deployment transition, research/safety/desync, external prompt, terminal text, missing timer proof, or screenshot-proven segment >3:00.`
