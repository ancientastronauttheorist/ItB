# Lightning War Strategy

## Current Best Plan

Pause the live ladder until the user resolves the macOS private-window /
screen-audio prompt, then return to verified setup before another speed burst.
The next runner should benefit from the Airstrike OCR narrowing:
`Protect the Emergency Batteries` no longer creates a false Airstrike conflict
when a route is actually `Mission_Tides`.

After setup proof, rerun:

```bash
python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3
```

## Expected Improvement

- Tides previews with emergency-battery bonus text should now classify as
  `Mission_Tides`, allowing the existing narrow Tides start authority to
  proceed when all other route-start guards pass.
- Airstrike remains veto-only through the distinctive `air support` text.
- Route-probe cache still avoids repeating a vetoed candidate, but cache data
  remains selection/ranking evidence only, never Start Mission authority.
- Standalone `lightning_segment --route-auto-start` now consumes and updates
  the session route-probe cache, so resume commands should avoid reprobing
  already failed live-preview candidates.
- Route-probe cache writes happen only after real failed route-start probes;
  successful starts and dry-runs should leave the session cache untouched.
- Explicit `route_probe_cache` arguments remain authoritative; standalone
  segment cache loading is only the default when no cache is injected.
- Stale unknown-OCR cache entries from the old emergency-battery/Airstrike
  matcher are ignored unless they carry a still-valid unknown OCR reason.
- Hard-prune cache entries require exact first-island, routing, and
  mission-index scope; missing or mismatched scope falls back to a fresh probe.

## Route Policy

- Route labels are selection evidence, not mission identity.
- Route starts require verified mission identity or narrowly safe preview OCR
  plus strict mismatch/deployment verification.
- Force defensive-shield OCR and Tides OCR can authorize Start Mission only
  with visible Start Mission and post-start mission proof.
- Solar, Airstrike, and Volatile preview OCR are veto-only.
- If the first mission is not safely startable before visible timer `0:03:00`,
  reset rather than probing further.

## Timing Policy

- Raw screenshots beat parsed OCR when they disagree.
- Do not run live commands while the macOS prompt is visible.
- Once a mission segment is screenshot-proven over `0:03:00`, stop proof play
  and reset/improve.
