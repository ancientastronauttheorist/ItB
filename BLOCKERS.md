# Lightning War Blockers

## Active

- Achievement not earned.
- A real macOS private-window / screen-audio access prompt is covering the
  paused game. The user must authorize or dismiss it; the runner must not click
  it automatically.
- No second-island progress or Lightning War unlock proof exists.
- Latest branch `20260621_225418_964` is paused on an ambiguous route preview
  and external prompt; do not start a mission from it.

## Reduced This Loop

- Airstrike OCR identity is now narrowed to `air support`.
- `Protect the Emergency Batteries` no longer identifies `Mission_Airstrike`;
  it can appear alongside `Mission_Tides` and must not create a false conflict.
- Stale conflict-cache entries from the old matcher no longer hard-prune a
  route candidate after the OCR fix.
- Standalone `lightning_segment --route-auto-start` now consumes and records
  session route-probe cache, reducing repeated failed live-preview probes.
- Session cache recording is limited to real failed route-start probes, avoiding
  dry-run writes and noisy success records.
- Explicit route-probe cache injection bypasses session cache loading, so
  callers can still provide an exact cache context.
- Route-probe hard-prune cache matches now require exact first-island,
  routing, and mission-index scope; stale labels from another route scope no
  longer skip a candidate.
- Blank session island scope now falls back to a normal probe instead of
  applying session cache.
- Route-probe cache remains live-proven on Archive: candidate 0 Airstrike was
  pruned before candidate 1 was tried.
- The conflict guard is live-proven safe: ambiguous known OCR stopped before
  Start Mission.

## Remaining Route Block

- Safe OCR preview is not enough by itself; Start Mission must be visibly
  clicked and post-start mission identity must be proved before deployment.
- Unlabeled or duplicate-labeled multi-region live-preview probes still block
  as `multi_region_live_preview_probe_without_route_identity`.
- Vetoes are safe but slow; avoid repeating expensive veto probes when cache or
  route scoring can choose a better candidate. Cache is still proof for
  selection only, not Start Mission authority.
- Deployment handoff after a verified route start must still recognize
  deployable screens quickly enough to preserve the `0:03:00` segment gate.

## Risk Controls

- One live/session-touching `game_loop.py` command at a time.
- Timer truth remains screenshot/OCR only.
- Stop on prompt, route mismatch, missing timer proof, research/safety/desync,
  terminal text, or screenshot-proven segment over `0:03:00`.
