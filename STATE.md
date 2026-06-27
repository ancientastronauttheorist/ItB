# Lightning War State

Last updated: 2026-06-21 late CT, after Airstrike OCR narrowing, stale-cache
bypass, session route-probe cache integration, and exact route-scope cache
guards for standalone segments.

## Current Run Facts

- Goal remains incomplete: no mission was started in the latest speed ladder.
- Latest recordings:
  - `recordings/20260621_224439_478`: Archive candidate 0, `Mission_Airstrike`
    vetoed before Start.
  - `recordings/20260621_224949_737`: R.S.T. candidate 1 blocked by
    `conflicting_known_preview_text_matches`.
  - `recordings/20260621_225418_964`: Archive candidate 1 repeated the same
    OCR conflict, then stopped on a real macOS external prompt.
- Current visible state is paused with a macOS prompt asking to let Codex
  bypass the system private-window picker and directly access screen/audio.
  The runner will not click it automatically.

## Evidence

- `run_notes/lightning_war_smoke_2026-06-21/screenshots/107_speed_attempt1_airstrike_terminal_pause_0139.png`
  is the stronger first-attempt terminal proof, showing `0:01:39` after the
  Airstrike veto path. Earlier telemetry logged `0:00:56`, and auxiliary
  screenshot `104` shows a later rehome/reset state at `0:01:14`.
- `run_notes/lightning_war_smoke_2026-06-21/screenshots/108_speed_attempt2_conflict_terminal_pause_0149.png`
  is the stronger second-attempt terminal proof, showing `0:01:49` after the
  route OCR conflict. Earlier telemetry logged `0:01:14`, and auxiliary
  screenshot `105` shows a later rehome/reset state at `0:01:00`.
- `run_notes/lightning_war_smoke_2026-06-21/screenshots/106_speed_attempt3_privacy_prompt_pause_0135.png`
  shows the third attempt paused at `0:01:35` behind the macOS prompt.

## Live Progress This Loop

- Reset from the older dead `0:02:08` branch to verified setup.
- Ran non-timer preflight; ignored save/profile timer output per Lightning
  timer policy.
- Ran `python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3`.
- Live-proved the route-probe cache: after Archive candidate 0 Airstrike veto,
  the next Archive attempt pruned candidate 0 and tried candidate 1.
- Live-proved the OCR conflict guard under the previous code: ambiguous Tides
  plus emergency-battery text blocked before Start Mission instead of
  authorizing a bad route.
- Found and fixed the overly broad Airstrike OCR pattern: `Protect the
  Emergency Batteries` can appear on a Tides preview and is not mission
  identity.
- Added a direct regression proving emergency-battery objective text alone
  stays `UNKNOWN`, not Airstrike.
- Prevented stale `conflicting_known_preview_text_matches` cache entries from
  hard-pruning a route after OCR identity rules change.
- Wired `cmd_lightning_segment(... route_auto_start=True)` to consume
  `RunSession.lightning_route_probe_cache` when no explicit cache is injected,
  and to save new failed-probe cache entries back to the session.
- Tightened session cache writes so successful route starts do not emit noisy
  skipped records, and dry-runs do not write route-probe cache.
- Added a guard proving explicit `route_probe_cache` arguments bypass session
  cache loading/merging.
- Tightened route-probe hard-prune matching so cached failed probes require the
  same first island, routing mode, and mission index; missing scope now probes
  instead of pruning.
- Added regression coverage for mismatched island/routing, unscoped cache
  entries, and blank session island scope falling back to a normal probe.

## Verification

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route/OCR/cache pytest passed: `16 passed, 535 deselected`.

## Current Position

- Stop live automation until the user resolves the macOS prompt.
- After prompt resolution, reset or recover to verified setup before another
  speed attempt; do not start from the ambiguous paused route preview.
- Standalone resume segments can now use session route-probe cache directly,
  so prefer `primary_next_command`/resume only after fresh proof and prompt
  resolution.
