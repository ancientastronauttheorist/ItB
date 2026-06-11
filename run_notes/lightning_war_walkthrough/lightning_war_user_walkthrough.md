# Lightning War User Walkthrough Notes

Date started: 2026-06-09

Purpose: capture the user's step-by-step Lightning War loop from my point of
view so the loop can later be run autonomously.

## Operating Style

- User will watch the screen and give small steps.
- I should move slowly, take screenshots/evidence at novel screens, and record
  edge cases as they happen.
- These notes are observational and procedural. They should preserve what was
  visible, what I inferred, and what exact action followed.

## Step 1 - Title Screen Baseline

Screenshot: [main_menu_start.png](main_menu_start.png)

Visible state:

- Full-screen Into the Breach title screen.
- Large `INTO THE BREACH` logo across the upper left/top.
- Left-side vertical menu contains, from top to bottom:
  `Continue`, `New Game`, `Options`, `Credits`, `Quit`.
- Lower-left profile panel shows `Profile: Alpha`, with `Achievements` and
  `Statistics` below.
- Bottom-right version text shows `Steam v. 1.2.93 (3-12-2024)`.

User instruction:

- The Lightning War loop always starts from this screen.
- First action after recognizing this screen: click `New Game`.

My automation note:

- The `New Game` menu item is the second large left-menu option, directly below
  `Continue`.
- In the captured 2048x1152 window screenshot, the visual center of `New Game`
  is approximately window-local `(118, 289)`.
- Do not choose `Continue` for this walkthrough start state, even if it is
  available.

Observed edge case on first attempt:

- I used the repo's calibrated `lightning_ui title_new_game` helper.
- The helper reported a successful click at window-local `(170, 315)` against a
  2560x1441 window.
- Resulting screen was not new-run setup. It was a live deployment screen:
  [after_title_new_game_misclick_deployment.png](after_title_new_game_misclick_deployment.png)
- This strongly suggests the calibrated Windows/title helper clicked too high
  for the current scaling/window geometry and selected `Continue`, or otherwise
  resumed an existing timeline.
- Future autonomous loop should not trust this helper blindly. It should either
  click the visually measured `New Game` row center for the current screenshot
  geometry or verify the post-click screen is new-run setup before proceeding.
- Stop condition: if clicking `New Game` lands on deployment/combat/island map,
  do not continue with the run setup sequence. Record evidence and recover back
  to the title/new-run setup path under explicit guidance.

Implementation update:

- Added a dynamic title-menu target finder in `src/control/mac_click.py`.
- `title_new_game` now captures the live game window, finds the actual title
  menu rows in screenshot pixels, selects row index `1` (`New Game`), scales
  that screenshot target back into the active window coordinate space, and
  clicks that derived point.
- This handles window location, screen resolution, and Windows DPI scaling
  differences. The same capture-and-scale flow uses the existing cross-platform
  screenshot helper, so it is intended to work on both Windows and macOS.
- The saved real baseline screenshot resolves `New Game` to approximately
  `(172, 360)` in its 2560x1441 screenshot, not the old fixed `(170, 315)`.
- Focused tests cover synthetic row detection and screenshot-to-window scaling.

## Step 2 - Existing Timeline Warning

Screenshot: [start_new_game_overwrite_prompt.png](start_new_game_overwrite_prompt.png)

Visible state after the corrected dynamic click:

- The title screen darkens under a centered modal.
- Modal title: `Start New Game`.
- Modal text: `You currently have a game in progress. Starting a new one will
  permanently erase it. Continue?`
- Two buttons are visible at the bottom of the modal: `YES` on the left and
  `NO` on the right.

My automation note:

- This prompt means the `New Game` button was clicked correctly.
- The loop must treat this as a confirmation gate, not as a failure.
- User policy for Lightning War walkthrough: click `YES`.
- Observed on Windows: the first `YES` click highlighted the button but did not
  accept the prompt:
  [overwrite_yes_highlighted_first_click.png](overwrite_yes_highlighted_first_click.png)
- A second click on the highlighted `YES` accepted the prompt and reached the
  new-run setup/loadout screen:
  [after_overwrite_yes_new_run_setup.png](after_overwrite_yes_new_run_setup.png)
- Future loop rule: after clicking `YES`, verify whether the modal cleared. If
  it is still visible and `YES` is highlighted, click `YES` one more time; do
  not click `NO`.

## Step 3 - New-Run Setup And Squad Requirement

Starting screenshot: [after_overwrite_yes_new_run_setup.png](after_overwrite_yes_new_run_setup.png)

Visible state:

- New-run setup/loadout hangar is visible.
- Top-right buttons: `Back` and `Start`.
- Right panel shows squad name `Blitzkrieg`.
- The three mechs shown are `Lightning Mech`, `Hook Mech`, and `Boulder Mech`.
- Lower-right panel button: `Change Squad`.
- Time Traveler panel shows `Bethany Jones`.

User instruction:

- For the Lightning War loop, this screen is already set correctly.
- Required invariant for this achievement: squad must be `Blitzkrieg`.
- Current pilot is Bethany because shield is useful, but the pilot is not the
  general requirement.
- Explore the `Change Squad` flow anyway so the bot can recover if Blitzkrieg
  is not already selected.

My automation note:

- Before pressing `Start`, verify the visible setup has squad `Blitzkrieg`.
- If not, use `Change Squad` to select it.
- Observed on Windows: first click on `Change Squad` highlighted the button;
  second click opened the squad picker.

## Step 4 - Squad Selection Page 1

Screenshot: [squad_selection_page1_blitzkrieg_visible.png](squad_selection_page1_blitzkrieg_visible.png)

Visible state:

- Center modal/panel title: `Squad Selection`.
- Top-right coin count: `12`.
- Bottom text: `Page 1 of 2`.
- Page 1 contains the following rows:
  `Random Squad`, `Custom Squad`, `Rift Walkers`, `Rusting Hulks`,
  `Zenith Guard`, `Blitzkrieg`, `Steel Judoka`, `Flame Behemoths`.
- `Blitzkrieg` is visible in the right column, third named-squad row, between
  `Rusting Hulks` and `Flame Behemoths`.

My automation note:

- For Lightning War, choose `Blitzkrieg`.
- If already on page 1, no page navigation is needed.
- Click the `Blitzkrieg` row/card, not `Random Squad` or `Custom Squad`.
- User note: because `Blitzkrieg` is on page 1, the loop should never need to
  click page 2 for Lightning War.
- Click the `Blitzkrieg` button/icons of the three mechs. The row highlights
  when hovered:
  [blitzkrieg_row_highlighted_tooltip.png](blitzkrieg_row_highlighted_tooltip.png)
- Observed on Windows: first click highlighted the row and showed the
  `Blitzkrieg` tooltip; second click selected the squad.
- Successful selection returns to the new-run setup/loadout screen with
  `Blitzkrieg` still shown in the right panel:
  [after_select_blitzkrieg_setup.png](after_select_blitzkrieg_setup.png)

## Step 5 - Setup Start Button

Starting state:

- New-run setup/loadout screen.
- Squad is verified as `Blitzkrieg`.
- Top-right `Start` button is visible.

User instruction:

- From here, click `Start`.

Observed behavior:

- First `Start` click highlighted the button but did not advance:
  [setup_start_highlighted_first_click.png](setup_start_highlighted_first_click.png)
- Second `Start` click opened the `Difficulty Setup` modal:
  [difficulty_setup_easy_ae_off.png](difficulty_setup_easy_ae_off.png)

Difficulty setup visible state:

- Modal title: `Difficulty Setup`.
- `Easy` is selected.
- `Normal`, `Hard`, and `Unfair` are unselected.
- All Advanced Content boxes are unchecked:
  `Enemy Units`, `Missions`, `Equipment`, `Pilot Abilities`.

My automation note:

- Clicking setup `Start` does not immediately begin the run. It opens the
  difficulty/Advanced Content confirmation modal.
- For this walkthrough state, Easy + Advanced Content off is the visible setup.
- User hypothesis for repeated first-click highlights: Codex focus often moves
  to the Codex app while typing instructions, so the first game click may only
  refocus/hover the game. Future automation should ensure the game window is
  focused before interpreting a single highlighted button as requiring a true
  double-click.

## Step 6 - Difficulty Setup Modal

Starting screenshot: [difficulty_setup_easy_ae_off.png](difficulty_setup_easy_ae_off.png)

User instruction:

- Ensure difficulty is `Easy`.
- Advanced Content does not matter for this Lightning War loop; any of the four
  Advanced Content toggles may be selected or unselected.
- After ensuring `Easy`, click the modal `Start` button.

Observed action:

- I clicked the already-selected `Easy` button first. This served as both
  difficulty confirmation and a safe game-focus click.
- Then I clicked the modal `Start` button.

Result:

- The game advanced to first island selection:
  [first_island_selection_after_start.png](first_island_selection_after_start.png)
- The top timer was visible and ticking (`0:00:12` in the captured frame), so
  from this point onward the Lightning War clock is live.

My automation note:

- Do not spend unnecessary thinking time after this point unless the game is
  paused or otherwise proven non-live.
- Difficulty must be Easy before modal Start.
- Advanced Content state is not a blocker for this loop.

## Rehearsal - Main Menu To Island Selection

Screenshot: [rehearsal_main_menu_to_island_selection.png](rehearsal_main_menu_to_island_selection.png)

Observed result:

- Starting from the main menu, the learned path reached first island selection.
- The overwrite prompt appeared and was handled with `YES`.
- Setup used existing `Blitzkrieg`.
- Difficulty modal was handled by ensuring `Easy`, then clicking `Start`.
- The resulting screen matched the earlier first island-selection state.

Automation note:

- This confirms the branch sequence is viable from the main menu.
- The top timer is live at island selection, so the autonomous loop should be
  prepared to choose an island immediately or pause/prove a safe state.

## Timing Probe - Difficulty Start To Island Selection

Artifacts directory:
[timing_start_to_grid_20260609_133819](timing_start_to_grid_20260609_133819/)

Contact sheet:
[contact_sheet.png](timing_start_to_grid_20260609_133819/contact_sheet.png)

User instruction:

- From the `Difficulty Setup` modal, ensure the game is focused.
- Ensure difficulty says `Easy`.
- Click the modal `Start` button.
- Capture the game window every 0.5 seconds for the next 15 seconds.

Observed timing:

- Captured 31 frames from t=0.0 through t=15.0, using modal `Start` mouse-up as
  t=0.
- t=0.0 to t=4.0: setup hangar/load transition still visible.
- t=4.5: island map appears.
- t=5.5: island-selection UI/top timer and left mech list are visible.
- t=6.0 onward: island-selection screen appears visually stable.

Automation note:

- The Lightning War timer starts immediately after the modal `Start`.
- For future timing-sensitive runs, assume first island selection becomes
  actionable around 5.5-6.0 seconds after the modal `Start` click on this
  machine, pending more samples.

## Timing Probe - First Island Click From Startup

### Returning To Main Menu Between Trials

User instruction:

- From the island map, return to the main menu with `Esc`, then click
  `Main Menu`.

Observed edge case:

- Sending the `Esc` key did not open the menu when the game window had lost
  focus to Codex.
- Clicking the calibrated pause/menu control at window `(38, 28)` reliably
  focused the game and opened the same in-game menu.

Observed menu geometry on the 2560x1441 Windows window:

- `Main Menu` button center: about window `(1130, 775)`.
- Do not confuse this with the right-side squad summary panel. A previous
  misread of the scaled screenshot put the x coordinate too far right.
- After clicking `Main Menu`, the game returns directly to the title screen.

### 7.0 Second Island Click Trial

Artifacts directory:
[island_click_timing_20260609_145339_delay_7.0s](island_click_timing_20260609_145339_delay_7.0s/)

Contact sheet:
[contact_sheet.png](island_click_timing_20260609_145339_delay_7.0s/contact_sheet.png)

Observed result:

- Starting from the main menu, the learned setup path reached the difficulty
  modal.
- Modal `Start` was treated as t=0.
- Archive island was clicked at about t=7.0.
- Result: success. The first island region zoom/intro sequence appeared after
  the click.

Automation note:

- A 7.0 second wait after modal `Start` is currently known-good on this
  machine.

### 7.0 Second Island Click Repeat Check

Initial repeat artifact directory:
[island_click_7s_repeat_20260609_150828](island_click_7s_repeat_20260609_150828/)

Corrected held-click artifact directory:
[island_click_7s_repeat_held_20260609_151129](island_click_7s_repeat_held_20260609_151129/)

User instruction:

- Try the 7.0 second timing three times to ensure it works.

Harness edge case:

- The first repeat batch used quick `pyautogui.click` calls. The click events
  fired at about t=7.11, but the contact sheets showed the test harness was not
  matching the repo's calibrated click behavior closely enough.
- I reran the three repeats with held clicks: press, hold about 0.3 seconds,
  then release. This matches the existing `lightning_ui` calibrated click style
  more closely.

Corrected observed result:

- Trial 1 contact sheet:
  [contact_sheet.png](island_click_7s_repeat_held_20260609_151129/trial_01_delay_7.0s/contact_sheet.png)
- Trial 2 contact sheet:
  [contact_sheet.png](island_click_7s_repeat_held_20260609_151129/trial_02_delay_7.0s/contact_sheet.png)
- Trial 3 contact sheet:
  [contact_sheet.png](island_click_7s_repeat_held_20260609_151129/trial_03_delay_7.0s/contact_sheet.png)
- All three corrected trials reached the Archive island region/Head Office
  dialogue after the scheduled 7.0 second island click.
- Because the island click is held for about 0.3 seconds, the mouse-up timestamp
  appears around t=7.64, while the click action begins at t=7.0.

Automation note:

- Use held UI clicks for this timing-sensitive section.
- A 7.0 second delay from difficulty modal `Start` mouse-up to Archive
  island click is repeat-confirmed for three held-click trials on this machine.
- The click target used was Archive island at window `(600, 430)`.

## Timing Probe - Archive Intro Continue Button

Artifacts directory:
[continue_button_timing_20260609_152937](continue_button_timing_20260609_152937/)

Contact sheet:
[contact_sheet.png](continue_button_timing_20260609_152937/contact_sheet.png)

User instruction:

- Start from the main menu again.
- Ensure the game is focused before doing anything in it.
- Continue taking screenshots every 0.5 seconds to find when the `CONTINUE`
  button first becomes available after selecting the island.

Observed setup:

- Returned to the main menu.
- Used the dynamic title-screen `New Game` detector to both focus the game and
  avoid raw-coordinate title-menu misses.
- Reached the difficulty modal with Blitzkrieg and `Easy`.
- Treated difficulty modal `Start` mouse-up as t=0.
- Used the repeat-confirmed held Archive island click beginning at t=7.0.

Observed timing:

- t=9.0 frame: Archive office scene is visible, but the bottom-right `CONTINUE`
  button is not yet visible.
- t=9.5 frame: bottom-right `CONTINUE` button is visible.
- Actual capture timestamp for that t=9.5 frame was about t=9.69.

Automation note:

- Earliest screenshot-confirmed `CONTINUE` availability is t=9.5 from
  difficulty modal `Start` mouse-up.
- Relative to the scheduled island click start at t=7.0, this is about
  2.5 seconds later.
- Relative to the held island click mouse-up, measured at about t=7.64, this is
  about 1.9 seconds later.

### 9.5 Second Continue Click Test

Artifacts directory:
[continue_click_test_9p5_20260609_153450](continue_click_test_9p5_20260609_153450/)

Contact sheet:
[contact_sheet.png](continue_click_test_9p5_20260609_153450/contact_sheet.png)

User instruction:

- Start from the main menu and test whether clicking the Archive intro
  `CONTINUE` button at t=9.5 works.

Observed result:

- Used dynamic title-screen `New Game` click to focus the game and avoid title
  menu coordinate misses.
- Treated difficulty modal `Start` mouse-up as t=0.
- Began held Archive island click at t=7.0.
- Began held `CONTINUE` click at t=9.5.
- The held `CONTINUE` click released at about t=10.18.
- Result: success. The screen advanced past the Archive Head Office intro to
  the Archive region map.

Automation note:

- t=9.5 is currently validated for the first Archive intro `CONTINUE` click
  when using the held-click method.
- The click target used was bottom-right `CONTINUE` at window `(1633, 1009)`.

## Timing Probe - Red Mission Detection And Click

Single-test artifacts directory:
[red_mission_click_test_0p5_20260609_154752](red_mission_click_test_0p5_20260609_154752/)

Five-loop artifacts directory:
[red_mission_click_5loop_0p5_20260609_155634](red_mission_click_5loop_0p5_20260609_155634/)

User instruction:

- After the Archive intro `CONTINUE` click, find any red mission and click it
  quickly.
- The red mission locations change between loops, so this must be visual and
  general, not a fixed coordinate.
- Important correction: take a fresh screenshot at the actual detection moment.
  Do not detect from an older saved screenshot or reference frame.

Detector notes:

- Capture a fresh live frame after the `CONTINUE` step.
- Search the island map area, currently ROI x=`520..2320`, y=`240..1320`.
- Use a red-dominant mask:
  `r >= 55`, `r >= g * 1.35`, `r >= b * 1.25`,
  `(r - g) >= 18`, and `(r - b) >= 12`.
- Run OpenCV connected components on the mask.
- Keep substantial red regions: area at least `3000`, width at least `60`,
  height at least `60`.
- Choose the largest surviving component and click its centroid.

Single prototype result:

- A first proof-of-concept detector found and clicked a red mission from a fresh
  frame and opened a mission preview.
- That prototype used slow pixel scanning, so it was useful as a correctness
  check but too slow for the timing target.

Five-loop optimized result:

- The optimized NumPy/OpenCV detector ran in about `65..81 ms` per detection.
- It opened a mission preview in all five loops.
- Trial 1 clicked target `(1665, 750)` and opened `Martial District`.
- Trial 2 clicked target `(1717, 922)` and opened `Old Earth Park`.
- Trial 3 clicked target `(1717, 923)` and opened `Accord Repository`.
- Trial 4 clicked target `(1653, 745)` and opened `Renovation Complex`.
- Trial 5 clicked target `(1062, 694)` and opened `Archivist Hall`; this trial
  found two valid red components and selected the larger one.

Timing caveat:

- In the five-loop harness, the requested red click was scheduled at t=`10.0`,
  which is 0.5 seconds after the t=`9.5` `CONTINUE` click schedule.
- Because the test harness was also taking screenshots and using held clicks,
  observed red click elapsed times landed around t=`11.4`.
- So the current evidence says the red mission detector is fast and general,
  and the contact frames show red missions available by the first post-continue
  map frames, but a stricter scheduler is still needed if we want an exact
  0.5-second mechanical proof.

Automation note:

- Always focus the game before the menu sequence.
- For the red mission step, always perform this order:
  fresh screenshot -> detect red mission component -> click detected centroid.
- Never reuse a screenshot for the click decision.


## Timing Probe - Mission Preview Board / Start Mission Click

Preview hover artifacts directory:
[mission_board_click_timing_20260609_0p5_probe](mission_board_click_timing_20260609_0p5_probe/)

Board-click artifacts directory:
[mission_board_start_click_20260609](mission_board_start_click_20260609/)

Corrected three-loop repeat directory:
[mission_board_3loop_main_menu_corrected_20260609](mission_board_3loop_main_menu_corrected_20260609/)

User instruction:

- After clicking a red mission, click the minimap/preview board to start the
  mission.
- Take one screenshot with the mouse off the board and one with the mouse on
  the board, so the yellow hover highlight and `Start Mission` text can be
  learned.
- Take screenshots every 0.5 seconds after the red mission click to identify
  the fastest available click time.
- Stop after the actual game board/deployment screen loads.

Observed hover behavior:

- With the mouse off the board, the mission preview card and board are visible,
  but the preview board is not yellow-highlighted.
- With the mouse at window `(1450, 790)`, the preview board highlights yellow
  and shows `Start Mission`.
- In this sample an advisor dialogue was still visible, but the board hover and
  `Start Mission` state still worked.

Observed timing after red mission click:

- The mission preview board was already visible at the first captured frame,
  t=`0.0` after the red mission click returned.
- It remained visible and stable at t=`0.5`, t=`1.0`, t=`1.5`, and later frames.
- This supports clicking the preview board as soon as the red mission click has
  opened the preview, with no extra 1.5 second wait needed in this sample.

General click rule:

- Prefer the existing visible `Start Mission` detector when available. It looks
  for the yellow `Start Mission` text/hover state and produces a fresh target
  from the current screenshot.
- The calibrated fallback target on this 2560x1441 Windows window is
  `mission_preview_board` at window `(1450, 790)`.
- In proportional terms, this is about x=`0.566` and y=`0.548` of the current
  window size, centered on the large isometric preview board.

Click result:

- Clicked the highlighted preview board at `(1450, 790)`.
- The deployment/game board was visible by the first post-click capture,
  t=`0.5` after the click.
- Stopped on the deployment screen labeled `Deploying Lightning Mech`, before
  making any deployment choices.

Three-loop repeat result:

- A first repeat attempt was discarded because the reset verifier was too loose:
  later trials reached deployment, but their starting frames were not actually
  the title screen.
- The corrected repeat restarted the game between trials and verified the title
  menu with the dynamic title-row detector before clicking `New Game`.
- Corrected Trial 1: started from verified title screen, clicked red mission
  target `(1665, 750)`, clicked the preview board, and reached deployment at
  t=`0.5` after the preview-board click.
- Corrected Trial 2: started from verified title screen, clicked red mission
  target `(1717, 922)`, clicked the preview board, and reached deployment at
  t=`0.5`.
- Corrected Trial 3: started from verified title screen, clicked red mission
  target `(1062, 694)`, clicked the preview board, and reached deployment at
  t=`0.5`.
- Result: `3/3` successful from a verified main menu/title start.

Automation note:

- Order for this step:
  fresh preview screenshot -> detect/hover `Start Mission` board -> held click
  preview board -> wait for deployment board.
- If using fixed coordinates as a fallback, click the center of the large
  preview board, not the mission text card.
- Do not trust a reset unless the next run has a fresh title-screen screenshot
  and the title-row detector confirms the `New Game` row. Deployment screens can
  absorb clicks and create false-positive repeat runs if reset is not verified.

### 6.5 Second Island Click Trial

Artifacts directory:
[island_click_timing_20260609_150309_delay_6.5s](island_click_timing_20260609_150309_delay_6.5s/)

Contact sheet:
[contact_sheet.png](island_click_timing_20260609_150309_delay_6.5s/contact_sheet.png)

Observed result:

- Modal `Start` was treated as t=0.
- The scheduled Archive click fired at t=6.613.
- At that moment the island-selection map was not actionable yet; the frame at
  t=6.5 still showed the setup/load transition rather than the stable island
  map.
- The first-island selection map appeared later, around t=11.5 in this sample,
  but the scheduled click had already been spent.
- Result: fail as an island-click timing. It did not enter the island region
  screen.

Automation note:

- With the current click/capture method, 6.5 seconds is too early.
- The current bracket is: 7.0 seconds succeeds, 6.5 seconds fails.
- If we want a tighter threshold later, test between these values, such as
  6.75 seconds, rather than continuing downward by 0.5 seconds.

## Timing Probe - First Deployment Click

Artifacts directory:
[deployment_start_timing_20260609_0p5_from_setup](deployment_start_timing_20260609_0p5_from_setup/)

Contact sheet:
[contact_sheet.png](deployment_start_timing_20260609_0p5_from_setup/contact_sheet.png)

User instruction:

- From the normal Lightning War startup path, learn how quickly deployment can
  begin after clicking the mission preview board.
- Initial expectation: deployment may be ready after only t=`0.5`.

Observed setup issue:

- The first attempt intended to start from the main menu did not leave the title
  screen because the `Start New Game` overwrite prompt appeared and needed an
  explicit `Yes`.
- That failed frame is kept in
  [deployment_start_timing_20260609_0p5](deployment_start_timing_20260609_0p5/),
  but it is not deployment timing evidence. It is a reminder that the loop must
  gate on the overwrite modal before assuming it is on setup.
- After clicking `Yes`, the setup screen was verified and the timing probe
  continued from there with the normal already-learned sequence.

Timing sequence:

- Clicked setup `Start`.
- Clicked `Easy`, then clicked the difficulty modal `Start`; the modal `Start`
  mouse-up is t=`0`.
- Clicked Archive at t=`7.0`.
- Clicked `Continue` at t=`9.5`.
- Took a fresh screenshot, found a red mission region, and clicked it.
- Hovered/clicked the mission preview board.
- Captured the deployment board at t=`0.5` after the preview-board click.
- Immediately clicked a detected yellow deployment region.
- Captured the follow-up deployment state at about t=`1.0`.

Observed result:

- At t=`0.5` after clicking the mission preview board, the deployment screen was
  already visible and ready. The screen showed `Deploying Lightning Mech` and
  yellow deployment tiles.
- The first deployment click was accepted immediately after that t=`0.5`
  capture.
- The follow-up screenshot showed the first mech placed and the next deployment
  step active.

Automation note:

- Deployment can begin at t=`0.5` after clicking the mission preview board in
  this sample.
- The current yellow visual detector is enough for this proof, but not final:
  it merged several adjacent yellow deployment tiles into one large connected
  region. For a robust loop, split the yellow mask into tile centers or prefer
  bridge deployment data once the bridge reports deployment.
- A clean full-start repeat should make the overwrite-modal gate explicit:
  title `New Game` -> if `Start New Game` appears, click `Yes` -> verify setup
  -> continue the learned timing sequence.

## Timing Probe - Deploy, Confirm, Enemy Turn

Primary artifacts directory:
[deploy_confirm_enemy_timing_visual_8loop_25s_20260609](deploy_confirm_enemy_timing_visual_8loop_25s_20260609/)

Earlier diagnostic artifacts:

- [deploy_confirm_enemy_timing_8loop_20260609](deploy_confirm_enemy_timing_8loop_20260609/)
- [deploy_confirm_enemy_timing_8loop_20260609_retry](deploy_confirm_enemy_timing_8loop_20260609_retry/)
- [deploy_confirm_enemy_timing_visual_8loop_20260609](deploy_confirm_enemy_timing_visual_8loop_20260609/)

User instruction:

- From the main menu, run the learned Lightning War startup path.
- Once deployment is visible, measure how quickly the existing deployment code
  can place mechs, click `Confirm`, and wait through the enemy's opening turn.
- Capture screenshots every t=`0.5` during the deployment/confirm/enemy-turn
  window.
- Run the probe eight times because enemy turn length varies.

Diagnostic lessons before the final 8-loop batch:

- Do not poll the bridge inside a t=`0.5` screenshot cadence loop. Bridge reads
  can block long enough to destroy the cadence.
- Do not use the built-in red region extractor for this specific first-island
  screen. It clicked the red territory mass instead of the actionable mission
  target in the diagnostic run.
- Use the relaxed fresh-red detector from the notes:
  ROI x=`520..2320`, y=`240..1320`;
  `r >= 55`, `r >= g*1.35`, `r >= b*1.25`,
  `(r-g) >= 18`, `(r-b) >= 12`;
  OpenCV connected components with area `>=3000` and width/height `>=60`;
  click the largest component centroid.
- The unconditional post-`New Game` `Yes` gate was harmless in these screenshots
  when the overwrite modal was not present, and clears the modal when it is
  present. Prefer a true modal detector later, but this gate worked for the
  timing batch.

Final 8-loop timing batch:

| Trial | deploy_recommended elapsed | Confirm clicked at | First visible `PLAYER TURN` | Enemy span after Confirm |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.788s | 2.792s | 10.581s | 7.789s |
| 2 | 1.562s | 2.538s | 11.967s | 9.429s |
| 3 | 1.547s | 2.553s | 16.326s | 13.773s |
| 4 | 1.660s | 2.602s | 10.401s | 7.799s |
| 5 | 1.557s | 2.505s | 16.254s | 13.749s |
| 6 | 1.757s | 2.752s | 10.597s | 7.845s |
| 7 | 1.760s | 2.716s | 11.533s | 8.817s |
| 8 | 1.800s | 2.756s | 17.028s | 14.272s |

Observed result:

- `deploy_recommended` successfully placed all three mechs in every final
  trial.
- Placement duration range: `1.547s..1.800s`.
- Confirm click time from deployment-ready timing start:
  `2.505s..2.792s`.
- Slowest observed enemy opening turn:
  `14.272s` after the Confirm click, in Trial 8.
- Slowest observed total deployment-ready-to-player-turn time:
  `17.028s`, also in Trial 8.

Automation note:

- From the deployment-ready screen, existing code can place mechs and click
  Confirm in under `3.0s` in these samples.
- After Confirm, do not assume the first player turn is ready before `15s`.
- Conservative rule for the current loop: wait/check at about `16s` after
  Confirm before beginning turn-1 combat automation.
- Equivalent deployment-start guard: wait/check at about `18s` after entering
  the deployment timing step.
- Keep taking screenshots or visible-state checks during development; enemy
  turn animations and mission opening dialogue can vary by map.

## Live Probe - Pause, Bridge Read, Solver, End Turn

Artifacts from this probe:

- [live_probe_after_new_game.png](live_probe_after_new_game.png)
- [live_probe_route_stop.png](live_probe_route_stop.png)
- [live_probe_after_route_start_block.png](live_probe_after_route_start_block.png)
- [live_probe_route_retry_after.png](live_probe_route_retry_after.png)
- [live_probe_after_preview_board_click.png](live_probe_after_preview_board_click.png)
- [live_probe_after_esc_pause_turn1.png](live_probe_after_esc_pause_turn1.png)
- [live_probe_after_second_esc.png](live_probe_after_second_esc.png)
- [live_probe_after_pause_icon_turn1.png](live_probe_after_pause_icon_turn1.png)
- [live_probe_after_actual_pause_gear.png](live_probe_after_actual_pause_gear.png)
- [live_probe_final_paused.png](live_probe_final_paused.png)

User instruction:

- From the main menu, reach the first combat player turn.
- Enter the pause menu with `Esc` if possible.
- Read the board from the bridge while paused, feed it to the solver, unpause,
  execute the solver's move with the existing scripts, then press `End Turn`.

Observed flow:

- Dynamic `title_new_game` correctly clicked the `New Game` row from the title
  screen.
- The `Start New Game` overwrite modal appeared. A fresh screenshot detected
  the modal, then clicked `YES` twice at current-window coordinate
  approximately `(1208, 797)`. The double click cleared the focus/highlight
  edge case and reached the Blitzkrieg loadout screen.
- `verify_setup --difficulty 0 --advanced-content any` initially failed on the
  loadout screen, which is expected because it only verifies the difficulty
  modal after the loadout `Start`.
- `setup_start` reached the difficulty modal. `verify_setup` then passed:
  difficulty `Easy`, Blitzkrieg already selected, Advanced Content state
  irrelevant for this loop.
- A bounded `lightning_start_run` probe selected Archive, but stopped before
  deployment because route scoring vetoed `Mission_Artillery`. For this
  walkthrough probe, the user had said any red mission is acceptable, so route
  scoring should not block the mechanics rehearsal.
- `lightning_capture` is not Windows-ready in this tree: it attempted macOS
  `screencapture` and failed with `WinError 2`. Use
  `src.capture.window.take_screenshot` on Windows until that command is fixed.
- `lightning_route_start --no-route-check` also proved too strict for this
  manual walkthrough state. It sent an `esc` key via `win32_sendinput`, but the
  visual verifier reported `pause_not_verified` even when a manual screenshot
  showed the pause menu was actually open. This verifier needs adjustment before
  trusting it in the loop.
- Manual route start from the live map worked:
  click the upper red mission at about `(1070, 660)`, then click the calibrated
  `mission_preview_board` at `(1450, 790)`.
- The mission reached deployment. `deploy_recommended` successfully deployed all
  three mechs by bridge and verified them:
  ElectricMech to `D5`, WallMech to `C6`, RockartMech to `F5`.
- `deploy_confirm` at `(240, 235)` started the opening enemy turn.
- Waiting `16s` after Confirm was sufficient to reach turn-1 player control.

Pause findings:

- Pressing lowercase `esc` via `src.control.mac_click.press_key("esc")` did not
  open the pause menu on this combat screen. The first and second attempts left
  the game in normal player-turn UI with a mech selected.
- The existing `lightning_ui pause` control is not Windows-calibrated for this
  window. It clicked `(38, 28)`, but the visible gear was around `(168, 130)`.
- Clicking the actual visible gear coordinate `(168, 130)` opened the pause
  menu reliably.
- Automation rule for this Windows setup: use the visible/calibrated pause gear
  coordinate, not `Esc`, until we improve key/focus handling and update the
  Windows pause control override.

Bridge and solver while paused:

- A paused `read` succeeded from the bridge:
  phase `combat_player`, turn `1`, grid `5/7`, three ready mechs.
- Threat summary from the paused read:
  one threatened building, `E7`, attacked by a Scarab at `E2`.
- `solve --time-limit 10` succeeded while paused and returned:
  1. `WallMech, move C6->D4, fire Grappling Hook at D2`
  2. `RockartMech, fire Rock Launcher at F2`
  3. `ElectricMech, fire Chain Whip at D4`
- Plan safety was `WARN` but not blocking: predicted `2` mech HP loss and
  WallMech on fire. No grid/building/objective block.

Execution result:

- `menu_continue` at `(1129, 582)` unpaused successfully.
- `auto_turn --time-limit 10 --max-wait 5` fresh-read, re-solved the same plan,
  executed all three actions through the bridge, and verified every action:
  move PASS, attack PASS, attack PASS, attack PASS.
- Threat audit passed: `E7` was covered because the attacking Scarab was killed.
- `auto_turn` emitted the End Turn click plan at Windows window-local
  `(252, 190)`.
- `lightning_ui end_turn` clicked End Turn successfully.
- After an `8s` wait, `read` reported turn `2`, phase `combat_player`,
  grid still `5/7`, and post-enemy analysis said predictions matched.

Automation notes from this probe:

- The core pause-read-solve-unpause-execute-End-Turn loop works once the pause
  state is reached.
- Prefer `auto_turn` for execution rather than manually replaying stored
  `execute <index>` calls; it fresh-reads, re-solves, executes, and verifies
  after each action.
- Current blockers to fully autonomous startup are UI-specific, not solver
  specific:
  route-start verifier misclassifies pause on Windows, `lightning_capture` is
  macOS-only, and the pause control needs a Windows coordinate override.

## Escape Toggle Investigation

Artifacts from this probe:

- [esc_probe_01_before_scancode_from_pause.png](esc_probe_01_before_scancode_from_pause.png)
- [esc_probe_02_after_scancode_from_pause.png](esc_probe_02_after_scancode_from_pause.png)
- [esc_probe_03_after_scancode_from_combat.png](esc_probe_03_after_scancode_from_combat.png)
- [esc_probe_04_before_pyautogui_from_pause.png](esc_probe_04_before_pyautogui_from_pause.png)
- [esc_probe_05_after_pyautogui_from_pause.png](esc_probe_05_after_pyautogui_from_pause.png)
- [esc_probe_06_after_pyautogui_escape.png](esc_probe_06_after_pyautogui_escape.png)
- [esc_patch_verify_01_before_press_key.png](esc_patch_verify_01_before_press_key.png)
- [esc_patch_verify_02_after_press_key_from_pause.png](esc_patch_verify_02_after_press_key_from_pause.png)
- [esc_patch_verify_03_after_press_key_from_combat.png](esc_patch_verify_03_after_press_key_from_combat.png)
- [esc_patch_verify_04_after_lightning_ui_pause_override.png](esc_patch_verify_04_after_lightning_ui_pause_override.png)

Question:

- `Esc` should toggle the pause menu. During the live probe, lowercase
  `press_key("esc")` did not visibly open pause, even after two attempts.

Root cause:

- The general `src.control.mac_click.press_key` helper used `pyautogui.press`
  on Windows.
- `pyautogui.press("esc")` and `pyautogui.press("escape")` both returned
  success from the library, but the game did not react. From a verified pause
  menu, both calls left the pause menu unchanged.
- The native Windows scancode path from `src.native.lldb_pause_probe` did work:
  `_windows_press_escape` sent scan code `0x01` through `SendInput`, toggled
  from pause to combat, and toggled from combat back to pause.

Fix applied:

- `src/control/mac_click.py` now routes Windows `press_key("esc")` and
  `press_key("escape")` through raw `SendInput` scancode Escape instead of
  PyAutoGUI.
- The Windows `pause` control override was updated to `(168, 130)`, matching the
  visible gear in the current 2560x1441 Windows capture. The old `(38, 28)`
  coordinate was not on the visible gear for this window.

Verification:

- After the patch, `press_key("esc")` reported backend `win32_sendinput`,
  toggled from the pause menu to combat, and toggled from combat back to the
  pause menu.
- `lightning_ui pause` now reports window coordinate `(168, 130)` and opens the
  pause menu from combat.
- `python -m py_compile src/control/mac_click.py` passed.

Automation rule:

- On Windows, use the shared `press_key("esc")` helper after this patch when an
  Escape toggle is desired. It now uses the proven scancode path.
- `lightning_ui pause` is also valid as a visual/icon fallback after the Windows
  coordinate override.

## Bridge Heartbeat, Focus, And Pause

Question:

- Determine what makes the Lua bridge heartbeat go stale: Codex focus, the pause
  menu, or something else.

Findings:

- The heartbeat is written from `Mission.BaseUpdate` in
  `src/bridge/modloader.lua`.
- Clicking into the Codex window did **not** stop the heartbeat in the live
  Windows setup. While Codex was the active window for about `9s`, the heartbeat
  age stayed around `0.0-0.01s`, and both `alive_1s` and `alive_5s` remained
  true.
- A real ITB pause menu opened with the Windows scancode Escape **did** stop the
  heartbeat. The heartbeat age increased steadily; after about `1.26s`,
  `alive_1s` became false, and after about `5.28s`, `alive_5s` became false.
- Unpausing with the same raw Escape path revived the heartbeat immediately. The
  first post-unpause sample showed heartbeat age around `0.012s` and both
  liveness checks true.

Important correction:

- A previous pause probe used generic `pyautogui.press("esc")`, which Into the
  Breach can ignore on Windows. That made it look as though pause did not stale
  the heartbeat. The valid Windows test must use the shared `press_key("esc")`
  helper, which routes Escape through raw `SendInput`.

Automation rule:

- Codex focus alone is not a bridge-heartbeat problem when ITB remains visible
  and ticking.
- Treat a stale heartbeat while the pause menu is open as normal and safe, not
  as a bridge failure.
- Do not send bridge combat commands after sitting in the pause menu for more
  than about `5s` without first unpausing and waiting for a fresh heartbeat.
- The fast walkthrough now has a post-`menu_continue` heartbeat guard before
  `auto_turn`: wait until `is_bridge_alive(max_stale_sec=1.0)` is true, then
  begin solver/bridge execution.

Repeat toggle probe:

- Starting from a long-paused menu state, heartbeat age was already stale at
  about `169s`.
- Three raw-Escape unpause/pause cycles behaved the same way:
  - Immediately after unpause, heartbeat age reset to about `0.002-0.005s`, and
    both `alive_1s` and `alive_5s` were true.
  - Immediately after pausing again, heartbeat age began increasing from about
    `0.25s`.
  - Around `1.26s` paused, `alive_1s` became false.
  - Around `5.27s` paused, `alive_5s` became false.
- Conclusion: the pause menu reliably suspends the Lua `BaseUpdate` heartbeat;
  unpause reliably restarts it on the next tick.
- Loop implication: pause can remain the safe thinking surface for Lightning
  War. The bridge-heartbeat invariant moves to the live burst boundary: after
  leaving pause, wait for a fresh heartbeat, then solve/execute.

## Paused Read And Solver Test

Question:

- Can the loop save in-game timer time by staying in the pause menu while
  reading bridge state and running the Rust solver, or do those steps require a
  live Lua heartbeat?

Test setup:

- Ran the fast walkthrough from the title screen with `--stop-after-pause`.
- It reached turn `1`, mission `Mission_Tides`, then paused after the opening
  enemy turn at about `30.628s` timer-relative.
- Deployment was:
  - ElectricMech at `E5`.
  - WallMech at `F6`.
  - RockartMech at `B5`.

Observed result:

- After sitting paused long enough for the bridge heartbeat to be stale,
  `game_loop.py read` still succeeded from the bridge and returned
  `phase=combat_player`, `turn=1`, `active_mechs=3`, grid `5/7`.
- The measured heartbeat age before the second read was about `64.8s`;
  `alive_1s=false` and `alive_5s=false`.
- `game_loop.py solve --time-limit 10` also succeeded while still paused.
  Rust solver time was `0.22s`, with `6/6` permutations complete and a
  `CLEAN` selected plan:
  1. `WallMech, move F6->D7`
  2. `RockartMech, move B5->C7, fire Rock Launcher at C2`
  3. `ElectricMech, move E5->D3, fire Chain Whip at D4`
- Repeating both `read` and `solve` with the heartbeat still stale returned the
  same board and same plan.

Practical rule:

- A fresh heartbeat is **not** required for paused board read or Rust solving
  when the bot itself just paused from a known actionable combat-player state.
- Keep the game paused for `read`, safety review, and `solve` to avoid spending
  in-game timer time.
- Still require a fresh heartbeat after unpausing and before bridge command
  execution, because paused Lua cannot process live combat commands and the
  board must be proven ticking before actions are sent.

## Paused Solve Execute Fast-Mode Trial

Question:

- Does the optimized loop work from the main menu in fast-mode: solve while
  paused, unpause only for stored action execution, verify each action, then
  End Turn?

Implementation under test:

- Added experimental `--paused-solve-execute` to
  `scripts/lightning_war_fast_walkthrough.py`.
- The guarded test path:
  1. Runs `read` and `solve` while paused.
  2. Unpauses with `menu_continue`.
  3. Waits for a fresh heartbeat.
  4. Executes stored action indices with `cmd_execute`.
  5. Runs `cmd_verify_action` after each action.
  6. Runs a fresh post-action `read`.
  7. Refuses to click End Turn if `threatened_buildings > 0`.

One-turn fast-mode result:

- Command:
  `python scripts/lightning_war_fast_walkthrough.py --paused-solve-execute --post-end-turn-wait-seconds 0.5 --post-end-turn-max-wait-seconds 30`
- Result: success for turn `1`.
- Paused solve completed, all stored actions executed, all three
  `verify_action` calls passed, post-action read showed
  `threatened_buildings=0`, End Turn was observed, and the loop paused on turn
  `2` at about `58.9s` timer-relative.

Full-mission fast-mode result:

- Command:
  `python scripts/lightning_war_fast_walkthrough.py --full-mission --paused-solve-execute --post-end-turn-wait-seconds 0.5 --post-end-turn-max-wait-seconds 30 --result-screenshot-cadence 0.5 --terminal-visual-settle-seconds 2.5 --max-mission-turns 6`
- Result: blocked on turn `1` of `Mission_Dam`.
- Action `2` (`RockartMech, move D5->B4, fire Rock Launcher at H4`) executed
  through the bridge, but `verify_action 2` returned `DESYNC`, category
  `terrain`, failure id
  `20260609_184046_189_m17_t01_per_action_desync_a2`.
- The runner stopped and parked instead of clicking End Turn. Evidence:
  `run_notes/lightning_war_walkthrough/paused_solve_full_mission_attempt_1.log`
  and
  `run_notes/lightning_war_walkthrough/paused_solve_full_mission_desync_state.png`.

Follow-up terrain timing check:

- The user visually noticed the six disputed tiles were already water on
  screen. I unpaused, did not click End Turn, and read the bridge again.
- The first fresh read after unpause reported the six tiles as water, matching
  the simulator prediction:
  `C4`, `B4`, `A4`, `C3`, `B3`, `A3`.
- A second read after another `2s` still reported those tiles as water.
- Updated diagnosis: this was not a wrong dam-water prediction. It was a
  verification timing issue. The bridge action ACK and unit positions were
  current, but the dam terrain transformation had not been reflected in the
  bridge snapshot used by immediate `verify_action`.

Practical rule:

- Paused solve plus stored action execution is promising and can save timer
  time, but it is not default-safe yet.
- Keep `auto_turn` as the default full-mission path until the stored-plan path
  gets the same post-action threat/desync recovery behavior as `auto_turn`.
- The experimental path must continue to verify every action, but terrain-only
  desyncs immediately after a terrain-changing action should be retried after a
  short live-tick delay before blocking. `Mission_Dam` dam-water conversion is
  the first confirmed case.
- Stop before End Turn on any persistent `DESYNC` or fresh post-action threat.

Follow-up run with delayed verify retry:

- Added a narrow delayed retry for immediate verification desyncs whose
  categories are only `terrain` and/or `death`.
- A new full-mission paused-solve run made it through turns `1-3` and stopped
  safely on turn `4` of `Mission_Artillery`.
- Stop reason:
  `PAUSED_STORED_PLAN_THREAT_AUDIT_BLOCKED`.
- Fresh post-action read showed `threatened_buildings=1`:
  `Building G3 by Scorpion1 at G2`.
- All four stored actions individually verified as `PASS`, but the post-action
  threat audit still found the building threat:
  1. `ArchiveArtillery` -> `OK SKIP 470`
  2. `RockartMech, move F5->G5, fire Rock Launcher at G2` -> `PASS`
  3. `ElectricMech, move D6->D5, fire Chain Whip at E5` -> `PASS`
  4. `WallMech, fire Grappling Hook at D5` -> `PASS`
- Evidence:
  `run_notes/lightning_war_walkthrough/paused_solve_full_mission_attempt_3.log`
  and
  `run_notes/lightning_war_walkthrough/paused_solve_attempt_3_stop_state.png`.
- Updated diagnosis: the delayed verification retry helps with dam terrain lag,
  but the stored-plan path still needs a proper post-action threat audit and
  recovery loop. The action-level verifier can pass while the overall turn is
  strategically unsafe.

Solver timing and Lightning speed loss policy:

- Recent recorded solve artifacts show the Rust solver is extremely fast for
  this loop:
  - Normal 3-mech turns: about `0.03s..0.7s` in recent samples.
  - `Mission_Dam` turn 1: about `0.48s`.
  - `Mission_Artillery` with the Archive artillery ally:
    turn 1 `2.56s`, turn 2 `2.59s`, turn 3 `2.85s`, turn 4 `3.70s`.
  - All of these completed all permutations and did not time out.
- Because paused solving does not spend the in-game timer, the fast runner now
  defaults to a `30s` solve budget.
- Added `--allow-lightning-speed-building-damage`, default enabled, for the
  paused-solve path. It allows ordinary post-action building threats when the
  grid would survive, and still records the allowance in the run result.

Manual continuation of the turn-4 `Mission_Artillery` stop:

- The paused-solve path had stopped before End Turn because post-action read
  saw `Building G3 by Scorpion1 at G2`.
- Under the Lightning War speed policy, I unpaused, waited for a fresh
  heartbeat, clicked End Turn, and watched the result flow.
- The mission reached `Region Secured` with both objectives checked:
  `Defend the Artillery Support` and `Protect the Emergency Batteries`.
- Visible game timer on the result screen: `0:02:08`.
- Grid remained `5/7`.
- Evidence:
  `run_notes/lightning_war_walkthrough/allow_building_threat_result_state.png`.

Updated practical rule:

- For Lightning War, do not block solely because an ordinary building is
  threatened after all actions, provided grid power would survive and no
  objective/protected target failure is indicated.
- Continue blocking on persistent action desyncs, objective failure, protected
  unit/objective threats, timeline collapse, or grid loss that could end the
  run.

## Opening Enemy Turn Readiness Timing

Question:

- The first enemy turn after deployment appears visually complete before the
  script notices it. Determine whether bridge or memory evidence can safely
  identify our first actionable player turn around the `0:19-0:23` game-timer
  range.

Probe result:

- Starting from main menu, the fast path reached deploy Confirm at about
  `15.8s` after the Lightning War timer began.
- Bridge samples after Confirm:
  - Through about `22.6s` timer-relative, bridge stayed
    `phase=combat_enemy`, `turn=0`, `active_mechs=0`.
  - Around `23.6s`, bridge flipped to `phase=combat_player`, `turn=1`, but
    `active_mechs=0`.
  - Around `25.7s`, bridge reported `phase=combat_player` with
    `active_mechs=3`, which is the first safe point for `auto_turn`.
- Memory context scanning did not provide a reliable turn-ready signal. It
  selected stale/irrelevant `GameData.current.time`-like values. A focused f32
  scan found moving timer-like values near `19-29s`, but no direct
  player-turn/actionability indicator better than the bridge.

Automation rule:

- After deployment Confirm, do not wait a fixed `16s` before polling. Start
  polling around `7s` after Confirm and require the bridge condition
  `phase == combat_player` plus `active_mechs > 0`.
- `phase == combat_player` alone is not enough; in this probe it appeared about
  `2s` before active mechs were ready.

## Full Mission Fast-Mode Timing Probe

Reference screen:

- Saved a user-identified mission-complete / `Region Secured` reference screen:
  `run_notes/lightning_war_walkthrough/region_secured_reference_20260609_215847.png`.
- This screen can include a CEO dialogue box over the `Region Secured` card.
  The visible Continue button is lower than the generic Windows
  `reward_continue` calibration; the observed button center was about
  `(1630, 985)` window-relative on a `2560x1441` window.

Successful full-mission run:

- A full fast-mode run from main menu completed a `Mission_Train` in `3` combat
  player turns and stopped on a `Region Secured` screen.
- Important marks from that run:
  - Timer start: `7.991s` after script launch.
  - Deploy Confirm live: `15.704s` timer-relative.
  - First actionable player turn after opening enemy phase:
    `30.132s` timer-relative.
  - Turn 1 End Turn click: `41.965s`; next player turn ready at `55.033s`.
  - Turn 2 End Turn click: `80.040s`; next player turn ready at `92.586s`.
  - Turn 3 End Turn click: `116.651s`; bridge terminal transition observed at
    `129.070s`.
- Practical interpretation: in this run, the mission-complete state was reached
  about `12.4s` after the final End Turn click, with the game timer around
  `0:02:09`. A screenshot taken shortly afterward showed the `Region Secured`
  Continue button visible at game timer `0:02:18`.

Edge cases discovered:

- `End Turn` sometimes needs an observer/retry path. A simple single calibrated
  click can leave bridge state at `phase=combat_player`, `active_mechs=0`.
  Reuse the existing `_observe_end_turn_after_click` and retryable-click logic
  after every visual End Turn click.
- The visible UI classifier can mislabel the `Region Secured` result panel as
  `perfect_reward_choice` or `island_map_or_unknown`. Do not rely on classifier
  name alone for final-result timing.
- Final mission completion may first show a CEO dialogue over the board/result
  flow. Treat a non-active-mission bridge snapshot plus visible post-mission
  dialogue as terminal enough to stop timed combat input and inspect.
- The stable timing screenshot folder is
  `run_notes/lightning_war_walkthrough/timing_screenshots/`. Each post-End-Turn
  sample should write a fresh image there and record both
  `elapsed_after_end_turn_seconds` and `game_timer_seconds`.

Next automation fix:

- In full-mission mode, after a bridge terminal transition, continue taking
  visible screenshots for a short window instead of returning immediately.
- Also stop if bridge says `in_active_mission == false`, even when the UI
  classifier still says `island_map_or_unknown`, because that covers the
  post-mission dialogue/result sequence.

Follow-up visual timing from paused post-mission dialogue:

- Starting from a paused post-mission dialogue screen, click pause-menu
  `Continue`, then capture every `0.5s`.
- Evidence folder:
  `run_notes/lightning_war_walkthrough/mission_complete_continue_probe/20260609_222256/`.
- Contact sheet:
  `run_notes/lightning_war_walkthrough/mission_complete_continue_probe/20260609_222256/contact_sheet.png`.
- Observed sequence after unpause:
  - `+0.001s`: post-mission CEO dialogue over the board.
  - `+0.501s`: `MISSION COMPLETE` banner visible.
  - `+1.000s` to `+1.501s`: banner fading / transition.
  - `+2.001s`: `Region Secured` card is visible with the `Continue` button.
  - `+2.501s` onward: `Region Secured` card remains stable and clickable.
- Practical rule: if the loop reaches/pauses on post-mission dialogue after the
  final End Turn, unpause and wait about `2.0s` before expecting the
  `Region Secured` Continue button to be available. Use `2.5s` as a safer
  click delay until we collect more samples.

## Three-Pass Region Secured Validation

Goal:

- Run fast-mode from main menu to the `Region Secured` Continue button several
  times to validate the timing against varying mission layouts and turn counts.

Observer fix:

- One pre-fix pass reached the `Region Secured` Continue screen visually, but
  the automation raised `END_TURN_CLICK_NOT_OBSERVED` on the final turn because
  bridge samples stayed briefly at `phase=combat_player`, `active_mechs=0`
  before terminal state. The parked snapshot already showed
  `in_active_mission=false`, `phase=unknown`, `active_mechs=0`,
  `deployment_zone_count=0`.
- Fix: if the End Turn observer does not see a clean transition, continue into
  the post-End-Turn terminal/player-turn watcher. If no terminal or next player
  turn appears, preserve the strict `END_TURN_CLICK_NOT_OBSERVED` error.

Clean validation passes after the fix:

- Attempt 2: completed in `3` combat turns. Deploy Confirm at `15.865s`,
  opening player-turn pause at `31.483s`, final End Turn click at `102.652s`,
  terminal/result watcher returned at `143.454s`. Visual confirmation:
  `run_notes/lightning_war_walkthrough/attempt_2_current_state.png`, visible
  game timer `0:02:30`.
- Attempt 3: completed in `3` combat turns. Deploy Confirm at `15.660s`,
  opening player-turn pause at `30.033s`, final End Turn click at `111.123s`,
  terminal/result watcher returned at `148.754s`. Visual confirmation:
  `run_notes/lightning_war_walkthrough/attempt_3_current_state.png`, visible
  game timer `0:02:35`.
- Attempt 4: completed in `4` combat turns. Deploy Confirm at `15.606s`,
  opening player-turn pause at `25.606s`, final End Turn click at `117.509s`,
  terminal/result watcher returned at `149.485s`. Visual confirmation:
  `run_notes/lightning_war_walkthrough/attempt_4_current_state.png`, visible
  game timer `0:02:33`.

Practical rule:

- The run can require either `3` or `4` player turns depending on the generated
  mission. Keep `--max-mission-turns 6`.
- The final-result watcher should allow at least `30s` after each End Turn. In
  these clean passes, the script reached and confirmed the result screen by
  about `143.5-149.5s` timer-relative, with the visible game timer around
  `0:02:30-0:02:35`.
- Continue treating `in_active_mission=false` plus
  `phase=unknown/combat_player`, `active_mechs=0`, and no deployment zone as
  terminal enough to stop combat input and watch for the result panel.

## First-Island Completion Probe

Goal:

- Extend the Lightning War fast loop past one mission and determine what new UI
  appears when the first island is fully cleared.

Result:

- A live run from main menu cleared Archive, including the Hive Leader/HQ
  mission, and reached the second island mission map.
- The first island required `5` missions in this sample:
  four ordinary red missions, then the Hive Leader mission at Corporate HQ.
- The first-island clear happened around visible game timer `0:32:00` after
  leaving Archive and selecting R.S.T.

New transition states:

- `POD RECOVERED`: the Open Door text is on the pod panel at about
  `(1690, 700)` window-relative on the `2560x1441` Windows window. It can take
  a short moment for the pod contents to appear after the click. Once contents
  are shown, the lower-right Continue is handled by the normal
  `reward_continue`/bottom-right target around `(1605-1633, 990-1009)`.
- Boss `Region Secured` can show CEO dialogue over the result card. Dismiss the
  dialogue text box around `(1280, 520)` first, then click the visible Continue
  around `(1630, 985)`.
- Promotion panels can appear after the boss result. Click `Understood` around
  `(1290, 885)`.
- `Perfect Island!` first shows an intro Continue at about `(1500, 900)`.
  The reward-choice screen can be misclassified as `pause_menu`; use visible
  text instead. For the current speed policy, choose `+2 Grid Def` at about
  `(1460, 810)`.
- The island-complete menu shows `SPEND REPUTATION` and `LEAVE ISLAND`. For the
  speed loop, click `Leave Island` at about `(1280, 1395)`.
- Leaving with unspent reputation opens a confirmation modal. Click `YES` at
  about `(1205, 795)`.
- The next-island world map appears with the next island highlighted. Clicking
  the selected island starts its HQ intro dialogue; the first observed next
  island was R.S.T. The HQ intro Continue uses the same bottom-right target
  around `(1630, 1010)`, after which the second island mission map is ready.

Classifier cautions:

- `perfect_reward_choice`, `kia_panel`, `pause_menu`, `deployment_screen`, and
  `island_map_or_unknown` all produced false positives during island-complete
  transitions. Use visible text and screenshots for transition panels instead
  of the classifier label alone.
- Treat `Region Secured` text, `POD RECOVERED`, `Perfect Island!`,
  `SPEND REPUTATION`, `Leave Island`, and `Head Office` intro text as stronger
  routing signals than the raw classifier name.

Automation changes from this probe:

- `scripts/lightning_war_fast_walkthrough.py --island-loop` has a
  `--continue-after-island` option to leave the completed island, accept the
  unspent-reputation confirmation, clear the next HQ intro, and open the next
  island's first mission preview when possible.
- Windows control overrides were updated for pod open, dialogue dismissal,
  promotion Understood, perfect-island Continue/reward, and Leave Island.

## Two-Island Discovery Pass

Goal:

- Run the loop slowly enough to patch UI edge cases as they appear, with the
  real Lightning War target in mind: clear the first two Corporate Islands with
  Blitzkrieg. This was a discovery pass, not a valid timed achievement attempt.

Result:

- The loop successfully reached the post-second-island boundary after clearing
  Archive and R.S.T., including both Hive Leader/HQ missions.
- R.S.T. also required `5` missions in this sample: four ordinary red missions,
  then the Corporate HQ mission.
- After the second island was left, the game naturally advanced toward a third
  island intro. For Lightning War, this is already past the achievement target.

Post-mission result screens:

- The CEO dialogue drawn over a `Region Secured` card is decorative in these
  result screens. Clicking the dialogue textbox did not dismiss it. The active
  control is still the card's `Continue` button.
- Result-card `Continue` has at least two observed vertical positions on the
  `2560x1441` Windows window:
  - upper result card: about `(1647, 985)`;
  - lower result card / failed-objective layout: about `(1647, 1018)`.
- Practical rule: use a two-height `reward_continue` sweep and verify that the
  screen advanced. Do not assume one fixed lower-right point handles every
  `Region Secured` card.

Promotion and reward-panel cautions:

- Promotion panels can be misclassified as `kia_panel`,
  `island_map_or_unknown`, or another broad transition state.
- When a post-result panel shows an `Understood`-style modal, use the
  `modal_understood` target around `(1290, 885)`.
- `perfect_reward_choice` can also be a false positive for an ordinary result
  card. Prefer visible text such as `Perfect Island!`, reward options, and
  `Region Secured` over the classifier name by itself.

Island transition after first island:

- The island-complete screen may classify as `island_map` while showing
  `SPEND REPUTATION` and `LEAVE ISLAND`. In the speed loop, click
  `Leave Island`.
- The unspent-reputation confirmation `YES` button is about `(1208, 795)` on
  the observed Windows window. The older base coordinate near `(568, 444)`
  only dismissed or missed the prompt and did not leave the island.
- On the world map after Archive, R.S.T. was highlighted. Clicking about
  `(850, 960)` opened the R.S.T. Head Office intro, and the normal
  bottom-right Continue opened the R.S.T. island map.

Second-island HQ edge case:

- The Corporate HQ / Hive Leader mission can show a warning panel on the island
  map. A stale bridge snapshot can still look like an active mission, so do not
  deploy purely from bridge state when the screen is visibly still on the map.
- After clicking the HQ mission preview board, verify that the visible UI is
  actually `deployment_screen`. If not, click the preview board again a small
  number of times before calling deployment.
- This visual deployment verification prevents the loop from trying
  `deploy_recommended` while still stuck on a mission-preview or warning panel.

Lightning War stop condition:

- The achievement only requires the first two Corporate Islands. After clearing
  the second island and accepting `Leave Island` confirmation, stop the
  Lightning War loop instead of selecting a third island.
- Current implementation treats `mission_index >= 10` after the second
  `leave_confirm_yes` as `SECOND_ISLAND_COMPLETE`.

Implementation changes from this pass:

- Added a two-height result-card Continue sweep.
- Added Windows overrides for `leave_confirm_yes` and `island_rst`.
- Added promotion/result routing fixes for the known false classifiers.
- Added deployment-screen verification after mission-preview board clicks.
- Added resume helpers for continuing from an island map or from an already
  open deployment screen during discovery runs.

## Two-Island Slow Rerun Addendum

Date: 2026-06-10.

Outcome:

- A slow two-island discovery rerun cleared Archive and R.S.T. with Blitzkrieg,
  including both Corporate HQ / Hive Leader missions.
- After accepting `Leave Island` on R.S.T., the game advanced to the next
  island/final phase. This is past the Lightning War achievement boundary.
- The observed in-game timer after leaving R.S.T. was about `1:38:38` in this
  intentionally slow patched discovery pass. This pass was not a timed attempt.

New edge cases and rules:

- Do not click red missions immediately after a `Region Secured` panel if the
  large green `REGION SECURED` sweep is still animating over the map. The map
  can show old red regions during that transition. Sample red-region centers
  until the signature is stable before clicking the next mission.
- A stale bridge payload can report `in_active_mission=true`,
  `turn=0`, and deployment zones while the screen is visibly still on the
  island map. Do not accept that state as deployment-ready when
  `bridge_heartbeat_alive=false` or `bridge_heartbeat_stale=true`.
- On Windows, raw PyAutoGUI clicks can report success while the game is not
  foreground. Foreground the Into the Breach HWND before trusted window clicks;
  the click result now records this focus attempt.
- `auto_turn` can return `INVESTIGATE` after all actions are executed and the
  End Turn click is held. In the observed R.S.T. HQ case, the investigation was
  a benign non-worse diff: predicted building HP `1`, actual building HP `2`,
  and grid remained `7/7`. For Lightning War speed policy, it is safe to
  continue only when every investigation snapshot has actual grid/building HP
  greater than or equal to predicted and the threat audit is clear.
- R.S.T. `Perfect Island!` has two states. First click the dialogue Continue at
  about `(1500, 900)` on the `2560x1441` Windows window. Then select `+2 Grid`
  at about `(1460, 810)`. The first state can be misclassified as `pause_menu`.
- The screenshot viewer may scale images; use pixel evidence from the saved
  screenshot when calibrating coordinates. The R.S.T. Perfect Island Continue
  looked lower in the viewer, but the actual button center was near `y=900`.

Patch follow-ups from this rerun:

- `click_stable_red_mission_after_result()` waits out post-result map
  animations before choosing the next red region.
- Result clearing now rechecks visible UI after each panel click before probing
  for red missions, so intermediate island-complete panels are not skipped.
- The fast walkthrough accepts only benign `INVESTIGATE` results under the
  Lightning speed policy by reading each snapshot `context.json`.
- Windows trusted clicks now attempt to foreground the game window before
  sending raw mouse input.

## Fast-Mode Timing Investigation

Date: 2026-06-10.

Observed issues:

- During the real fast-mode attempt, the game briefly entered the pause menu,
  immediately unpaused, and then waited several seconds before mech actions
  began.
- After mission completion, the Region Secured Continue button was visible but
  the loop was slow to click it.

Findings:

- The attempted command did not pass `--paused-solve-execute`, and the script
  default was still the live `auto_turn` path. That path clicks
  `menu_continue` first, waits for a fresh heartbeat, and then runs
  `cmd_auto_turn`, so solving/diagnosis happens while the in-game timer is
  ticking. This exactly explains the visible pause flash followed by delayed
  mech actions.
- The post-End-Turn watcher still had timing-probe behavior enabled for the
  real attempt: every poll wrote a timing screenshot and then took a separate
  classifier screenshot. It also ran OCR-backed result audits before returning.
  That is good for measurement, but it is unnecessary overhead when the goal is
  to click Region Secured Continue as soon as it appears.
- The result clearer also used OCR snapshots and conservative fixed sleeps for
  every transition click, even when the visible UI was already an obvious
  reward / Region Secured panel.

Patch follow-ups:

- `--paused-solve-execute` is now enabled by default for this fast walkthrough.
  Use `--no-paused-solve-execute` only for deliberate live-`auto_turn` testing.
- Post-End-Turn timing screenshots and OCR result audits are now opt-in via
  `--record-timing-screenshots` and `--ocr-result-audit`.
- The default post-End-Turn minimum wait is now `0.5s`, matching the fast-mode
  probes.
- Result clearing now uses non-OCR visible classification first and shorter
  transition settles, so obvious Region Secured / reward Continue panels should
  be clicked much sooner.

Follow-up Continue-button edge case:

- A `Region Secured` card can appear with an advisor dialogue strip still open
  across the top. On Windows without OCR, the visual classifier can mislabel
  this as `perfect_reward_choice` because the lower card resembles the perfect
  reward crop.
- In this state the visible Continue button may not activate reliably until the
  dialogue strip is dismissed. The fast clearer now treats
  `in_active_mission=false`, `active_mechs=0`, and a strong dialogue-strip
  visual score as a terminal-dialogue overlay, clicks the dialogue textbox
  first, then proceeds to the result Continue.

Follow-up deployment speed issue:

- The fast walkthrough had accumulated several conservative deployment waits:
  `0.5s` after mission-preview click before checking deployment, another
  `0.5s` `deploy-ready` wait, a `0.5s` post-bridge-deploy verification sleep
  inside `deploy_recommended`, and up to `4s` waiting after Confirm before
  retrying.
- These waits were useful while hardening stale-bridge and focus issues, but
  they are too expensive for the real Lightning War loop. The timed fast
  walkthrough now checks deployment after `0.15s`, uses no extra deploy-ready
  wait by default, calls `deploy_recommended(..., verify_after=False)`, and
  verifies the deployment commit through the faster Confirm/live-bridge wait.
