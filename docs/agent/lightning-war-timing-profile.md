# Lightning War Timing Profile

This notebook explains the executable timings stored in
`data/lightning_war_timing_profile.json`.

## main_menu_to_archive_red_map

- Status: PASS on `lightning_ui_timing_20260613_145559`
- Timer zero: lower difficulty setup Start click
- Primary time source: wall-clock for the promoted boundary; validated live
  numeric memory timer is available for the current process/session
- Red-map in-game timer: not recorded for the current promoted pass
- Memory probe validation: `0x00000000122e5dbc` as `f32_seconds` is the
  validated live numeric timer for PID 2100. It advanced `3.993896s` over a
  `4.000087s` live track, then `3.994507s` over a second `4.000677s` live
  track; after re-pausing it matched pause-menu `Timeline Playtime` at
  `0:21:11` and `0:21:27` respectively, with fractional seconds preserved in
  memory.
- Pause-menu oracle: `0x00000000138a5900` is a process-local
  `Timeline Playtime` render/cache string. It is useful after re-pausing, but
  it stayed stale while the live top-right timer advanced and must not be used
  as the screenshot frame clock.
- Profile Archive click wall elapsed: 7.975s
- Profile intro Continue wall elapsed: 10.509s
- Profile red detection wall elapsed: 19.276s with 2 red regions
- Pass condition: at least one red Archive mission region detected on the map
- Next patch: rerun the opening lab with
  `--memory-live-timer-address 0x00000000122e5dbc --memory-live-timer-kind f32_seconds`,
  then promote the best screenshot-anchored memory timer timing and extend to
  `red_map_to_mission_preview`.

## lightning_ui_timing_20260613_145305

- Result: FAIL
- Branch: archive_intro.extra_dialogue
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: wall-clock only; in-game timer was not captured
- Archive click wall elapsed: 9.45s
- Intro continue wall elapsed: 10.369s
- Red map detected wall elapsed: n/a
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_20260613_145305\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Improve Archive intro wait/dismissal or red-region detector.

## lightning_ui_timing_20260613_145559

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: wall-clock only; in-game timer was not captured
- Archive click wall elapsed: 7.975s
- Intro continue wall elapsed: 10.509s
- Red map detected wall elapsed: 19.276s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_145559\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_145559\telemetry\screenshots\000014_1781380617192_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_150106

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: wall-clock only; in-game timer was not captured
- Archive click wall elapsed: 7.978s
- Intro continue wall elapsed: 10.315s
- Red map detected wall elapsed: 19.413s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_150106\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_150106\telemetry\screenshots\000013_1781380924854_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_150850

- Result: FAIL
- Branch: archive_intro.extra_dialogue
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: in-game save/profile `current.time` achievement clock
- Red map detected in-game timer: 0:00:04
- Archive click wall elapsed: 7.808s
- Intro continue wall elapsed: 10.306s
- Red map detected wall elapsed: n/a
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_20260613_150850\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Improve Archive intro wait/dismissal or red-region detector.
## lightning_ui_timing_20260613_151431

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: memory probe `visible_timer_string`; fallback save/profile `current.time`
- Red map detected in-game timer: 8:16:32
- Red map timer source: memory_visible_timer_context
- Archive click wall elapsed: 7.818s
- Intro continue wall elapsed: 12.742s
- Red map detected wall elapsed: 24.924s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_151431\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_151431\telemetry\screenshots\000004_1781381740968_opening_probe.png
- Next patch: Do not promote this pass. Its memory context selected `8:16:32`
  while the paired screenshot showed the top-right timer at `0:00:20`, proving
  unanchored context selection is stale/noisy.

## memory_probe_cycles_20260613_pause_timeline

- Result: PAUSE_MENU_ORACLE_CURRENT_PROCESS
- PID: 2100
- Oracle address: `0x00000000138a5900`
- Scope: current Windows process/session only; rediscover after restart, PID
  change, modloader reload, or platform change.
- Evidence: cycle0 screenshot showed `0h 0m 46s`; cycle1 found
  `0h 1m 04s`; cycle2 reread the same address as `0h 1m 27s`; cycle3 reread it
  as `0h 1m 48s`; the follow-up pause guard screenshot showed `0h 2m 14s`, and
  `read-address 0x00000000138a5900` returned `0:02:14`.
- Evidence files:
  `run_notes\lightning_ui_timing_loop\memory_probe_cycle1_64_string_addresses.json`,
  `run_notes\lightning_ui_timing_loop\memory_probe_cycle2_87_string_address_tracking.json`,
  `run_notes\lightning_ui_timing_loop\memory_probe_cycle3_108_tracking.json`.
- Rejected signals: cycle0/1 `f32` candidates had no stable same-address
  intersection, rereading cycle0 candidates at 64s did not produce near-64
  values, and other string addresses either froze at old values or became
  unrelated text.
- Next patch: use this only as the post-pause ground-truth oracle. Do not use
  it for live screenshot filenames.

## memory_probe_live_numeric_20260613

- Result: VALIDATED_CURRENT_PROCESS
- PID: 2100
- Live timer address: `0x00000000122e5dbc`
- Kind: `f32_seconds`
- Validation cycle 1:
  `run_notes\lightning_ui_timing_loop\memory_numeric_score_live_1254_cycle1.json`
  reported one validated candidate. It advanced `1259.680420 -> 1263.674316`
  over `4.000087s`, then after re-pausing read `0:21:11` against pause-menu
  Playtime `0:21:11`.
- Validation cycle 2:
  `run_notes\lightning_ui_timing_loop\memory_numeric_track_address_122e5dbc_cycle2.json`
  advanced `1276.528564 -> 1280.523071` over `4.000677s`; final paused read
  was `1287.440186s`, matching pause-menu Playtime `0:21:27` with fractional
  seconds preserved.
- 2 Hz screenshot filename smoke:
  `recordings\lightning_live_numeric_filename_smoke_20260613_162932` captured
  six frames with filenames advancing from `gt0-21-40` through `gt0-21-44`;
  no frames dropped, and memory clock sample latency was `0.0s` after the
  initial reader open.
- Usage for this process/session:
  `python scripts/lightning_war_timing_lab.py --memory-live-timer-address 0x00000000122e5dbc --memory-live-timer-kind f32_seconds`
- Scope: current Windows process/session only; rediscover after restart, PID
  change, modloader reload, or platform change.

## manual_probe_20260613_1517

- Result: SUPERSEDED_DIAGNOSTIC
- Visible screenshot timer: `0h 0m 38s`
- Screenshot: run_notes\lightning_ui_timing_loop\timer_probe_expected_38_screen.png
- Probe: run_notes\lightning_ui_timing_loop\timer_probe_expected_38_words.json
- Memory result: explicit expected `0:00:38` found stable `f32` candidates at
  `38.0` and nearby `38.005`, matching the paused screenshot timer.
- Note: this proved parsing of pause-menu word-form timers, but the later
  toggle cycles showed `f32` candidates can be stale copies. The calibrated
  `Timeline Playtime` string address is now the trusted current-process method.
