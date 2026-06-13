# Lightning War Timing Profile

This notebook explains the executable timings stored in
`data/lightning_war_timing_profile.json`.

## main_menu_to_archive_red_map

- Status: PASS on `lightning_ui_timing_20260613_145559`
- Timer zero: lower difficulty setup Start click
- Profile Archive click: 7.975s
- Profile intro Continue click: 10.509s
- Profile red detection: 19.276s with 2 red regions
- Pass condition: at least one red Archive mission region detected on the map
- Next patch: extend to `red_map_to_mission_preview` after user review.

## lightning_ui_timing_20260613_145305

- Result: FAIL
- Branch: archive_intro.extra_dialogue
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Archive click: 9.45s
- Intro continue: 10.369s
- Red map detected: n/a
- Red regions: None
- Contact sheet: recordings\lightning_ui_timing_20260613_145305\telemetry\contact_sheet.png
- Red map screenshot: None
- Next patch: Improve Archive intro wait/dismissal or red-region detector.

## lightning_ui_timing_20260613_145559

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Archive click: 7.975s
- Intro continue: 10.509s
- Red map detected: 19.276s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_145559\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_145559\telemetry\screenshots\000014_1781380617192_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
## lightning_ui_timing_20260613_150106

- Result: PASS
- Branch: archive_intro.default
- Boundary: main menu -> lower Start timer zero -> Archive -> red map
- Archive click: 7.978s
- Intro continue: 10.315s
- Red map detected: 19.413s
- Red regions: 2
- Contact sheet: recordings\lightning_ui_timing_20260613_150106\telemetry\contact_sheet.png
- Red map screenshot: recordings\lightning_ui_timing_20260613_150106\telemetry\screenshots\000013_1781380924854_opening_probe.png
- Next patch: Extend to red_map_to_mission_preview after user review.
