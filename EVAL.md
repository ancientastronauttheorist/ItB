# Lightning War Evaluation

## Success Metric

Earn Lightning War with Blitzkrieg by completing the first two Corporate
Islands under `0:30:00` visible Timeline Playtime, with each mission segment
Start-to-Start at or under `0:03:00`.

## Current Loop Score

- Progress: 2/5. The latest speed ladder made no mission-start progress, but
  it live-proved safe Airstrike veto, route-cache pruning, and the OCR conflict
  stop before an ambiguous Start Mission. Offline work now prevents stale
  conflict-cache pruning and lets standalone resume segments use/write the
  session route-probe cache without noisy success records or dry-run writes,
  while preserving explicit cache injection semantics and requiring exact
  route scope before cache hard-prunes.
- Evidence: 5/5. Screenshots 107 and 108 preserve the strongest attempt 1/2
  terminal timer proofs, and screenshot 106 preserves the real macOS prompt
  stop at `0:01:35`.
- Artifacts: 5/5. Root artifacts now point at the current recordings,
  screenshots, patch, prompt blocker, and next command.
- Heuristics: 5/5. Added the emergency-battery/Tides OCR rule, the
  emergency-battery-alone unknown guard, stale OCR-cache bypass, session-cache
  resume behavior, dry-run cache-write guard, explicit-cache bypass guard, and
  exact-scope route-cache guard, blank-island cache fallback, plus reinforced
  external-prompt stop policy.
- Risk: 5/5. No combat commands or Start Mission clicks were forced through
  ambiguous proof; the runner stopped on the external prompt.
- Clarity: 5/5. Next action is user prompt resolution, then setup proof, then
  speed rerun with the narrowed OCR matcher.

Average: 4.5/5.

## Verification

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route/OCR/cache pytest:
  `python3 -m pytest tests/test_lightning_war_tools.py -q -k 'lightning_segment_ignores_session_route_probe_cache_without_island_scope or lightning_route_probe_cache_requires_exact_route_scope or lightning_segment_records_failed_probe_in_session_cache or lightning_segment_explicit_route_probe_cache_bypasses_session or lightning_segment_uses_session_route_probe_cache_for_auto_start or lightning_segment_dry_run_does_not_record_failed_probe or lightning_route_probe_cache_ignores_stale_conflicting_ocr_prune or lightning_segment_blocks_retry_when_probe_cache_prunes_remaining_candidate or lightning_auto_start_skips_cached_failed_labeled_probe or lightning_visible_preview_ocr_detects_air_support_batteries or lightning_visible_preview_ocr_tides_with_emergency_batteries_not_airstrike or lightning_visible_preview_ocr_emergency_batteries_alone_is_unknown or lightning_visible_preview_ocr_blocks_conflicting_mission_matches or lightning_visible_preview_ocr_detects_proximity_mines_with_spawn_bonus or lightning_visible_preview_ocr_rejects_generic_spawn_block_as_force or lightning_visible_preview_ocr_detects_defensive_shields_force or lightning_visible_preview_ocr_detects_tides'`
  passed with `16 passed, 535 deselected`.

## Result

Achievement not earned yet. The next loop is improved because Tides previews
with emergency-battery objective text no longer conflict with Airstrike, and
emergency-battery text alone cannot silently become Airstrike identity again.
Standalone route-auto-start resumes also now carry learned route-probe cache
without relying on the runner to inject it, while successful starts and dry-runs
do not write cache records.
Explicit `route_probe_cache` injection still bypasses session loading, so
callers can intentionally test or override cache behavior.
Cache hard-prunes now require exact route scope, so an old label/index cannot
silently skip a later island or mission.
If the session lacks current island scope, cache is ignored and the runner
probes normally.
