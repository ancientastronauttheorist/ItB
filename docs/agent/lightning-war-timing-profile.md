# Lightning War Timing Profile

This notebook explains the executable timings stored in
`data/lightning_war_timing_profile.json`.

## main_menu_to_archive_red_map

- Status: PASS on `lightning_ui_timing_20260613_145559`
- Timer zero: lower difficulty setup Start click
- Time source: wall-clock `perf_counter`, not the in-game top-right timer
- Profile Archive click wall elapsed: 7.975s
- Profile intro Continue wall elapsed: 10.509s
- Profile red detection wall elapsed: 19.276s with 2 red regions
- In-game timer: not recorded by opening lab v1
- Pass condition: at least one red Archive mission region detected on the map
- Next patch: capture top-right or memory-reader game timer alongside wall
  elapsed, then extend to `red_map_to_mission_preview`.

## lightning_ui_timing_20260613_145305

- Result: FAIL
- Branch: archive_intro.extra_dialogue
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Time source: wall-clock `perf_counter`, not the in-game top-right timer
- Archive click wall elapsed: 9.45s
- Intro continue wall elapsed: 10.369s
- Red map detected wall elapsed: n/a
- In-game timer: not recorded by opening lab v1
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_20260613_145305\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Improve Archive intro wait/dismissal or red-region detector.

## lightning_ui_timing_20260613_145559

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Time source: wall-clock `perf_counter`, not the in-game top-right timer
- Archive click wall elapsed: 7.975s
- Intro continue wall elapsed: 10.509s
- Red map detected wall elapsed: 19.276s
- In-game timer: not recorded by opening lab v1
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_145559\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_145559\telemetry\screenshots\000014_1781380617192_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_150106

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Time source: wall-clock `perf_counter`, not the in-game top-right timer
- Archive click wall elapsed: 7.978s
- Intro continue wall elapsed: 10.315s
- Red map detected wall elapsed: 19.413s
- In-game timer: not recorded by opening lab v1
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_150106\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_150106\telemetry\screenshots\000013_1781380924854_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
