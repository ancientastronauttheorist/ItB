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
  `Timeline Playtime` string address is now only a re-pause oracle; the
  validated live numeric candidate is the screenshot frame clock.
## lightning_ui_timing_20260613_165234

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected screenshot timer: 0:00:14 (`14.624589s`)
- Red map timer source: screenshot frame clock from `memory_live_numeric_candidate`
- Red map paired post-detection timer: 0:00:15 (`15.419024s`)
- Archive click wall elapsed: 7.817s
- Intro continue wall elapsed: 10.306s
- Red map detected wall elapsed: 19.422s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_165234\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_165234\telemetry\screenshots\000011_1781387624901_gt0-00-14_opening_probe.png
- Note: frame filenames show the live memory clock held the previous timeline
  value (`0:21:53`) for five post-Start frames before resetting to the new run
  at `0:00:00`; timing reports must use the first trusted reset/current-run
  frame for red-map boundaries.
- Next patch: reduce the post-Continue red-probe gap and extend to
  `red_map_to_mission_preview` after user review.
## lightning_ui_timing_20260613_172050

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:14
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:14
- Archive click wall elapsed: 7.812s
- Intro continue wall elapsed: 10.309s
- Red map detected wall elapsed: 18.996s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_172050\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_172050\telemetry\screenshots\000012_1781389314601_gt0-00-14_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_172553

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:05
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.816s
- Intro continue wall elapsed: 10.335s
- Red map detected wall elapsed: 10.899s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_172553\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_172553\telemetry\screenshots\000011_1781389625381_gt0-00-05_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_172913

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.814s
- Intro continue wall elapsed: 10.312s
- Red map detected wall elapsed: 10.866s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_172913\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_172913\telemetry\screenshots\000012_1781389821097_gt0-00-06_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_5x_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.807s
- Intro continue wall elapsed: 10.311s
- Red map detected wall elapsed: 10.826s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_5x_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_5x_20260613_1\telemetry\screenshots\000012_1781390359710_gt0-00-06_opening_probe.png
- Next patch: Measure preview-to-deployment click after user review.
## lightning_ui_timing_5x_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.811s
- Intro continue wall elapsed: 10.316s
- Red map detected wall elapsed: 10.823s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_5x_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_5x_20260613_2\telemetry\screenshots\000012_1781390454624_gt0-00-06_opening_probe.png
- Next patch: Measure preview-to-deployment click after user review.
## lightning_ui_timing_5x_20260613_3

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.811s
- Intro continue wall elapsed: 10.309s
- Red map detected wall elapsed: 10.832s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_5x_20260613_3\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_5x_20260613_3\telemetry\screenshots\000012_1781390549201_gt0-00-06_opening_probe.png
- Next patch: Measure preview-to-deployment click after user review.
## lightning_ui_timing_5x_20260613_4

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.86s
- Intro continue wall elapsed: 10.308s
- Red map detected wall elapsed: 10.837s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_5x_20260613_4\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_5x_20260613_4\telemetry\screenshots\000012_1781390643385_gt0-00-06_opening_probe.png
- Next patch: Measure preview-to-deployment click after user review.
## lightning_ui_timing_5x_20260613_5

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.809s
- Intro continue wall elapsed: 10.307s
- Red map detected wall elapsed: 10.787s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_5x_20260613_5\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_5x_20260613_5\telemetry\screenshots\000011_1781390738806_gt0-00-06_opening_probe.png
- Next patch: Measure preview-to-deployment click after user review.
## lightning_ui_timing_startmission_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.928s
- Intro continue wall elapsed: 10.314s
- Red map detected wall elapsed: 10.876s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_20260613_1\telemetry\screenshots\000012_1781391314786_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.808s
- Intro continue wall elapsed: 10.312s
- Red map detected wall elapsed: 10.812s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_20260613_2\telemetry\screenshots\000012_1781391911616_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_20260613_3

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.834s
- Intro continue wall elapsed: 10.31s
- Red map detected wall elapsed: 10.829s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_20260613_3\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_20260613_3\telemetry\screenshots\000012_1781392300108_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_20260613_4

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.812s
- Intro continue wall elapsed: 10.309s
- Red map detected wall elapsed: 10.838s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_20260613_4\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_20260613_4\telemetry\screenshots\000012_1781392569781_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_20260613_5

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.81s
- Intro continue wall elapsed: 10.308s
- Red map detected wall elapsed: 10.842s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_20260613_5\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_20260613_5\telemetry\screenshots\000012_1781392675745_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_opt_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.813s
- Intro continue wall elapsed: 10.311s
- Red map detected wall elapsed: 10.864s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_opt_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_opt_20260613_1\telemetry\screenshots\000012_1781393226482_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_startmission_opt_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.809s
- Intro continue wall elapsed: 10.314s
- Red map detected wall elapsed: 10.848s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_startmission_opt_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_startmission_opt_20260613_2\telemetry\screenshots\000012_1781393375634_gt0-00-06_opening_probe.png
- Next patch: Measure deployment placement and confirm click after user review.
## lightning_ui_timing_deploy_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_deployed_mechs
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.942s
- Intro continue wall elapsed: 10.315s
- Red map detected wall elapsed: 10.922s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_deploy_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_deploy_20260613_1\telemetry\screenshots\000012_1781394034703_gt0-00-06_opening_probe.png
- Next patch: Measure deploy Confirm click after user review.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.96s
- Post-deploy frame in-game timer: 0:00:20
## lightning_ui_timing_deploy_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_deployed_mechs
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.954s
- Intro continue wall elapsed: 10.319s
- Red map detected wall elapsed: 10.902s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_deploy_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_deploy_20260613_2\telemetry\screenshots\000012_1781394333550_gt0-00-06_opening_probe.png
- Next patch: Measure deploy Confirm click after user review.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.864s
- Post-deploy frame in-game timer: 0:00:12
## lightning_ui_timing_deploy_20260613_3

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_deployed_mechs
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 8.049s
- Intro continue wall elapsed: 10.31s
- Red map detected wall elapsed: 10.947s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_deploy_20260613_3\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_deploy_20260613_3\telemetry\screenshots\000012_1781394541544_gt0-00-06_opening_probe.png
- Next patch: Measure deploy Confirm click after user review.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.78s
- Post-deploy frame in-game timer: 0:00:11
## lightning_ui_timing_deploy_repeat_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_deployed_mechs
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.809s
- Intro continue wall elapsed: 10.313s
- Red map detected wall elapsed: 10.835s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_deploy_repeat_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_deploy_repeat_20260613_1\telemetry\screenshots\000012_1781394875741_gt0-00-06_opening_probe.png
- Next patch: Measure deploy Confirm click after user review.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.963s
- Post-deploy frame in-game timer: 0:00:11
## lightning_ui_timing_deploy_repeat_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_deployed_mechs
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.822s
- Intro continue wall elapsed: 10.312s
- Red map detected wall elapsed: 10.843s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_deploy_repeat_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_deploy_repeat_20260613_2\telemetry\screenshots\000012_1781394983688_gt0-00-06_opening_probe.png
- Next patch: Measure deploy Confirm click after user review.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.968s
- Post-deploy frame in-game timer: 0:00:11
## lightning_ui_timing_confirm_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_opening_player_turn
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.811s
- Intro continue wall elapsed: 10.308s
- Red map detected wall elapsed: 10.977s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_confirm_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_confirm_20260613_1\telemetry\screenshots\000011_1781395655337_gt0-00-06_opening_probe.png
- Next patch: Compare bridge/player-turn timing with screenshot evidence; then measure first combat action.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.883s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:22
- First frame after bridge-ready timer: 0:00:22
- Post-confirm observed seconds: 18.198s
## lightning_ui_timing_confirm_20260613_2

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_opening_player_turn
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 8.05s
- Intro continue wall elapsed: 10.317s
- Red map detected wall elapsed: 10.888s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_confirm_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_confirm_20260613_2\telemetry\screenshots\000012_1781395830366_gt0-00-06_opening_probe.png
- Next patch: Compare bridge/player-turn timing with screenshot evidence; then measure first combat action.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.79s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:27
- First frame after bridge-ready timer: 0:00:27
- Post-confirm observed seconds: 15.715s
## lightning_ui_timing_combat_turn_20260613_1

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_combat_turn_2_player_ready
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.815s
- Intro continue wall elapsed: 10.311s
- Red map detected wall elapsed: 10.867s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_combat_turn_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_combat_turn_20260613_1\telemetry\screenshots\000012_1781396564638_gt0-00-06_opening_probe.png
- Next patch: Compare combat-turn bridge timing with screenshots; then measure the next combat turn or mission-clear branch.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.977s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:25
- First frame after bridge-ready timer: 0:00:25
- Post-confirm observed seconds: 14.202s
- Combat solver/action signal: cmd_auto_turn
- Combat auto_turn status: PLAN
- Combat actions completed: 3
- Combat auto_turn duration: 39.542s
- Combat auto_turn done timer: 0:00:35
- Combat End Turn click timer: 0:00:35
- Combat bridge left player timer: 0:00:42
- Combat bridge left-player note: superseded for this marker; the first version allowed a transient bridge error sample to count as non-player phase, and the classifier is now hardened to require a valid fresh bridge snapshot.
- Combat next player-turn bridge timer: 0:00:50
- Combat first frame after bridge-ready timer: 0:00:50
- Combat post-End-Turn observed seconds: 15.152s
## lightning_ui_timing_combat_turn_20260613_2

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_combat_turn_2_player_ready
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.811s
- Intro continue wall elapsed: 10.316s
- Red map detected wall elapsed: 10.916s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_combat_turn_20260613_2\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_combat_turn_20260613_2\telemetry\screenshots\000011_1781396862383_gt0-00-06_opening_probe.png
- Next patch: Diagnose combat auto_turn safety block before End Turn timing (death|Ranged_Rockthrow|attack).
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.896s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:22
- First frame after bridge-ready timer: 0:00:22
- Post-confirm observed seconds: 10.567s
- Combat solver/action signal: cmd_auto_turn
- Combat auto_turn status: FUZZY_INVESTIGATE_BLOCKED
- Combat actions completed: 3
- Combat safety stop: death|Ranged_Rockthrow|attack
- Combat policy update: future timing-lab fast attempts skip this class only when `auto_turn` completed the full opening squad action count and produced a held End Turn plan; ordinary play still investigates.
- Combat auto_turn duration: 37.119s
- Combat auto_turn done timer: 0:00:34
- Combat End Turn click timer: n/a
- Combat bridge left player timer: n/a
- Combat next player-turn bridge timer: n/a
- Combat first frame after bridge-ready timer: n/a
- Combat post-End-Turn observed seconds: n/a
## lightning_ui_timing_region_secured_20260613_1

- Result: FAIL
- Branch: current_combat
- Boundary: current_combat_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: n/a
- Red map timer source: n/a
- Red map paired post-detection timer: n/a
- Archive click wall elapsed: n/a
- Intro continue wall elapsed: n/a
- Red map detected wall elapsed: n/a
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_region_secured_20260613_1\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Diagnose combat auto_turn safety block before End Turn timing.
- Region Secured loop status: FAIL
- Region Secured turns attempted: 1
- Last End Turn click timer: n/a
- Region Secured visible timer: n/a
- Region Secured visible elapsed after End Turn: n/a
- Continue hover control: reward_continue @ (None, None)
- Continue hover result: n/a screen=(None, None)
- Continue hover frame timer: n/a
## lightning_ui_timing_region_secured_20260613_3

- Result: PASS
- Branch: current_combat
- Boundary: current_combat_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: n/a
- Red map timer source: n/a
- Red map paired post-detection timer: n/a
- Archive click wall elapsed: n/a
- Intro continue wall elapsed: n/a
- Red map detected wall elapsed: n/a
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_region_secured_20260613_3\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Review Region Secured Continue hover coordinates, then append safe Continue click.
- Region Secured loop status: PASS
- Region Secured turns attempted: 0
- Last End Turn click timer: n/a
- Region Secured visible timer: 0:27:22
- Region Secured visible elapsed after End Turn: n/a
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:27:23
## lightning_ui_timing_region_secured_from_top_20260613_200511

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.819s
- Intro continue wall elapsed: 10.316s
- Red map detected wall elapsed: 10.925s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_region_secured_from_top_20260613_200511\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_region_secured_from_top_20260613_200511\telemetry\screenshots\000011_1781399160809_gt0-00-06_opening_probe.png
- Next patch: Fix combat post-End-Turn player-ready detection.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.883s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:26
- First frame after bridge-ready timer: 0:00:26
- Post-confirm observed seconds: 14.104s
- Region Secured loop status: FAIL
- Region Secured turns attempted: 3
- Last End Turn click timer: n/a
- Region Secured visible timer: n/a
- Region Secured visible elapsed after End Turn: n/a
- Continue hover control: reward_continue @ (None, None)
- Continue hover result: n/a screen=(None, None)
- Continue hover frame timer: n/a
## lightning_ui_timing_region_secured_from_top_fixed_20260613_201313

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.933s
- Intro continue wall elapsed: 10.312s
- Red map detected wall elapsed: 10.947s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_region_secured_from_top_fixed_20260613_201313\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_region_secured_from_top_fixed_20260613_201313\telemetry\screenshots\000011_1781399675648_gt0-00-06_opening_probe.png
- Next patch: Review Region Secured Continue hover coordinates, then append safe Continue click.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.881s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:26
- First frame after bridge-ready timer: 0:00:26
- Post-confirm observed seconds: 14.546s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:02:16
- Region Secured visible timer: 0:02:41
- Region Secured visible elapsed after End Turn: 15.178s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:42
## lightning_ui_timing_3x_top_1_20260613_202318

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.81s
- Intro continue wall elapsed: 10.321s
- Red map detected wall elapsed: 10.912s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_3x_top_1_20260613_202318\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_3x_top_1_20260613_202318\telemetry\screenshots\000011_1781400259564_gt0-00-06_opening_probe.png
- Next patch: Fix combat post-End-Turn player-ready detection.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.881s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:23
- First frame after bridge-ready timer: 0:00:23
- Post-confirm observed seconds: 11.222s
- Region Secured loop status: FAIL
- Region Secured turns attempted: 2
- Last End Turn click timer: n/a
- Region Secured visible timer: n/a
- Region Secured visible elapsed after End Turn: n/a
- Continue hover control: reward_continue @ (None, None)
- Continue hover result: n/a screen=(None, None)
- Continue hover frame timer: n/a
## lightning_ui_timing_3x_top_1b_20260613_202914

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.813s
- Intro continue wall elapsed: 10.311s
- Red map detected wall elapsed: 10.938s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_3x_top_1b_20260613_202914\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_3x_top_1b_20260613_202914\telemetry\screenshots\000011_1781400623360_gt0-00-06_opening_probe.png
- Next patch: Review Region Secured Continue hover coordinates, then append safe Continue click.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.878s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:25
- First frame after bridge-ready timer: 0:00:25
- Post-confirm observed seconds: 12.623s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:02:09
- Region Secured visible timer: 0:02:31
- Region Secured visible elapsed after End Turn: 14.419s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:32
## lightning_ui_timing_3x_top_2b_20260613_203708

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.814s
- Intro continue wall elapsed: 10.312s
- Red map detected wall elapsed: 10.892s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_3x_top_2b_20260613_203708\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_3x_top_2b_20260613_203708\telemetry\screenshots\000011_1781401112019_gt0-00-06_opening_probe.png
- Next patch: Review Region Secured Continue hover coordinates, then append safe Continue click.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.896s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:23
- First frame after bridge-ready timer: 0:00:23
- Post-confirm observed seconds: 11.207s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:02:07
- Region Secured visible timer: 0:02:31
- Region Secured visible elapsed after End Turn: 15.318s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:32
## lightning_ui_timing_3x_top_3_20260613_204446

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_hover
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.818s
- Intro continue wall elapsed: 10.315s
- Red map detected wall elapsed: 10.949s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_3x_top_3_20260613_204446\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_3x_top_3_20260613_204446\telemetry\screenshots\000011_1781401568988_gt0-00-06_opening_probe.png
- Next patch: Review Region Secured Continue hover coordinates, then append safe Continue click.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.903s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:21
- First frame after bridge-ready timer: 0:00:22
- Post-confirm observed seconds: 10.175s
- Region Secured loop status: PASS
- Region Secured turns attempted: 3
- Last End Turn click timer: 0:01:31
- Region Secured visible timer: 0:01:59
- Region Secured visible elapsed after End Turn: 19.739s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:00
## region_continue_click_watch_20260613_211117

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_click
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.817s
- Intro continue wall elapsed: 10.315s
- Red map detected wall elapsed: 10.959s
- Red regions: 2
- Contact sheet: recordings\region_continue_click_watch_20260613_211117\telemetry\contact_sheet.png
- Red map screenshot: recordings\region_continue_click_watch_20260613_211117\telemetry\screenshots\000011_1781403272270_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.767s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:23
- First frame after bridge-ready timer: 0:00:23
- Post-confirm observed seconds: 11.26s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:02:13
- Region Secured visible timer: 0:02:46
- Region Secured visible elapsed after End Turn: 23.476s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:47
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:02:47
- Continue click after frame timer: 0:02:48
## turn_audit_fast_20260613_213349

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_click
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.829s
- Intro continue wall elapsed: 10.344s
- Red map detected wall elapsed: 11.069s
- Red regions: 2
- Contact sheet: recordings\turn_audit_fast_20260613_213349\telemetry\contact_sheet.png
- Red map screenshot: recordings\turn_audit_fast_20260613_213349\telemetry\screenshots\000011_1781404557526_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.736s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:23
- First frame after bridge-ready timer: n/a
- Post-confirm observed seconds: 10.138s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:03:07
- Region Secured visible timer: 0:03:18
- Region Secured visible elapsed after End Turn: 0.35s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:03:19
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:03:19
- Continue click after frame timer: 0:03:21
- Turn sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done
- Player turns observed: 4
- Enemy phases observed: 5
- End Turn -> enemy bridge avg/max: 7.057s / 7.578s
- Enemy bridge -> next player avg/max: 8.995s / 10.994s
- End Turn -> next player avg/max: 16.052s / 17.954s
- Ready bridge -> first audit frame avg/max: n/a / n/a
- Ready bridge -> pause avg/max: n/a / n/a
- Terminal End Turn -> Region Secured: 11.035s
## turn_sequence_confirm_20260613_214704

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_click
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.845s
- Intro continue wall elapsed: 10.328s
- Red map detected wall elapsed: 10.944s
- Red regions: 2
- Contact sheet: recordings\turn_sequence_confirm_20260613_214704\telemetry\contact_sheet.png
- Red map screenshot: recordings\turn_sequence_confirm_20260613_214704\telemetry\screenshots\000011_1781405306252_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 1.032s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:13
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:24
- First frame after bridge-ready timer: n/a
- Post-confirm observed seconds: 10.936s
- Region Secured loop status: PASS
- Region Secured turns attempted: 3
- Last End Turn click timer: 0:02:46
- Region Secured visible timer: 0:03:13
- Region Secured visible elapsed after End Turn: 16.092s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:03:14
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:03:14
- Continue click after frame timer: 0:03:15
- Turn sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done
- Player turns observed: 3
- Enemy phases observed: 4
- End Turn -> enemy bridge avg/max: 9.818s / 11.478s
- Enemy bridge -> next player avg/max: 8.101s / 11.219s
- End Turn -> next player avg/max: 17.919s / 19.377s
- Ready bridge -> first audit frame avg/max: n/a / n/a
- Ready bridge -> pause avg/max: n/a / n/a
- Terminal End Turn -> Region Secured: 26.828s
## bridge_default_sequence_20260613_215902

- Result: PASS
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_region_secured_continue_click
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 7.842s
- Intro continue wall elapsed: 10.325s
- Red map detected wall elapsed: 10.992s
- Red regions: 2
- Contact sheet: recordings\bridge_default_sequence_20260613_215902\telemetry\contact_sheet.png
- Red map screenshot: recordings\bridge_default_sequence_20260613_215902\telemetry\screenshots\000011_1781406031291_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 1.04s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:24
- First frame after bridge-ready timer: n/a
- Post-confirm observed seconds: 11.372s
- Region Secured loop status: PASS
- Region Secured turns attempted: 3
- Last End Turn click timer: 0:02:38
- Region Secured visible timer: 0:03:05
- Region Secured visible elapsed after End Turn: 17.523s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:03:06
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:03:06
- Continue click after frame timer: 0:03:07
- Turn sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done
- Player turns observed: 3
- Enemy phases observed: 4
- End Turn -> enemy bridge avg/max: 7.944s / 7.944s
- Enemy bridge -> next player avg/max: 6.398s / 6.398s
- End Turn -> next player avg/max: 18.224s / 22.106s
- Ready bridge -> first audit frame avg/max: n/a / n/a
- Ready bridge -> pause avg/max: n/a / n/a
- Terminal End Turn -> Region Secured: 27.476s
## live_top_mainmenu_20260615_165306

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_10_missions
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.816s
- Intro continue wall elapsed: 10.307s
- Red map detected wall elapsed: 10.87s
- Red regions: 2
- Contact sheet: recordings\live_top_mainmenu_20260615_165306\telemetry\contact_sheet.png
- Red map screenshot: recordings\live_top_mainmenu_20260615_165306\telemetry\screenshots\000011_1781560437671_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.875s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:12
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:22
- First frame after bridge-ready timer: n/a
- Post-confirm observed seconds: 10.136s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:01:46
- Region Secured visible timer: 0:02:15
- Region Secured visible elapsed after End Turn: 20.034s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:02:16
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:02:16
- Continue click after frame timer: 0:02:17
- Post-Continue observed seconds: 8.688s
- Post-Continue next visible UI: island_map
- Post-Continue next visible timer: 0:02:26
- Turn sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done
- Player turns observed: 4
- Enemy phases observed: 5
- End Turn -> enemy bridge avg/max: 8.884s / 10.231s
- Enemy bridge -> next player avg/max: 6.483s / 9.328s
- End Turn -> next player avg/max: 15.368s / 15.902s
- Ready bridge -> first audit frame avg/max: 0.0s / 0.0s
- Ready bridge -> pause avg/max: 0.36s / 0.371s
- Terminal End Turn -> Region Secured: 28.978s
- Speed sequence expectation: MISMATCH
- Expected speed sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done
- Observed speed sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done
## live_top_mainmenu_20260615_170130

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_10_missions
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:06
- Archive click wall elapsed: 7.848s
- Intro continue wall elapsed: 10.311s
- Red map detected wall elapsed: 10.888s
- Red regions: 2
- Contact sheet: recordings\live_top_mainmenu_20260615_170130\telemetry\contact_sheet.png
- Red map screenshot: recordings\live_top_mainmenu_20260615_170130\telemetry\screenshots\000011_1781560950125_gt0-00-06_opening_probe.png
- Next patch: Learn the next post-Region-Secured island-map route step.
- Deploy recommended result: OK
- Deploy recommended placements: 3
- Deploy recommended duration: 0.778s
- Post-deploy frame in-game timer: n/a
- Deploy Confirm signal: deploy_recommended_result
- Deploy Confirm click timer: 0:00:11
- Opening player-turn signal: bridge_lua_live_snapshot
- Opening player-turn bridge timer: 0:00:22
- First frame after bridge-ready timer: n/a
- Post-confirm observed seconds: 9.808s
- Region Secured loop status: PASS
- Region Secured turns attempted: 4
- Last End Turn click timer: 0:01:39
- Region Secured visible timer: 0:01:48
- Region Secured visible elapsed after End Turn: 0.413s
- Continue hover control: reward_continue @ (1647, 985)
- Continue hover result: OK screen=(1647, 985)
- Continue hover frame timer: 0:01:50
- Continue click control: reward_continue @ (1647, 985)
- Continue click result: OK
- Continue click before timer: 0:01:50
- Continue click after frame timer: 0:01:51
- Post-Continue observed seconds: 10.256s
- Post-Continue next visible UI: pause_menu
- Post-Continue next visible timer: 0:01:54
- Turn sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done
- Player turns observed: 4
- Enemy phases observed: 5
- End Turn -> enemy bridge avg/max: 4.737s / 4.873s
- Enemy bridge -> next player avg/max: 8.435s / 8.56s
- End Turn -> next player avg/max: 13.172s / 13.433s
- Ready bridge -> first audit frame avg/max: 0.0s / 0.0s
- Ready bridge -> pause avg/max: 0.316s / 0.322s
- Terminal End Turn -> Region Secured: 9.246s
- Speed sequence expectation: MISMATCH
- Expected speed sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done
- Observed speed sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done
## live_top_mainmenu_20260615_171650

- Result: FAIL
- Branch: archive_intro.default
- Boundary: main_menu_to_archive_red_map_to_10_missions
- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles
- Red map detected in-game timer: 0:00:06
- Red map timer source: memory_live_numeric_candidate
- Red map paired post-detection timer: 0:00:07
- Archive click wall elapsed: 8.048s
- Intro continue wall elapsed: 10.329s
- Red map detected wall elapsed: 10.975s
- Red regions: 2
- Contact sheet: recordings\live_top_mainmenu_20260615_171650\telemetry\contact_sheet.png
- Red map screenshot: recordings\live_top_mainmenu_20260615_171650\telemetry\screenshots\000012_1781561863191_gt0-00-06_opening_probe.png
- Next patch: Fix combat-to-Region-Secured timing loop startup.
- Turn sequence: n/a
- Player turns observed: 0
- Enemy phases observed: 0
- End Turn -> enemy bridge avg/max: n/a / n/a
- Enemy bridge -> next player avg/max: n/a / n/a
- End Turn -> next player avg/max: n/a / n/a
- Ready bridge -> first audit frame avg/max: n/a / n/a
- Ready bridge -> pause avg/max: n/a / n/a
- Terminal End Turn -> Region Secured: n/a
- Speed sequence expectation: MISMATCH
- Expected speed sequence: enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done
- Observed speed sequence: n/a
