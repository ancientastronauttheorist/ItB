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
