# Lightning War UI Fast Path Notes

Last updated: 2026-06-23

## Global Rule

- Esc toggles pause even on UI screens where the gear/pause button is hidden.
- Never press Esc from a verified pause menu. Use visible pause proof first:
  menu overlay, `Timeline Playtime`, or pause timer OCR.
- If unsure, use the snapshot loop: resume, wait/click briefly, screenshot,
  Esc-pause, then think from the paused screenshot.
- Iteration loop:
  - Mode 1: stay paused, analyze screenshots/logs, test hypotheses, and patch
    scripts.
  - Mode 2: run the newest code as a race test, collect screenshots every 5s,
    and stop/restart as soon as mission timing is not achievement-viable.

## Title / Setup

- Title `New Game`: visible left menu row around window `(151,314)`.
  Dynamic helper sometimes misses/stalls; direct coordinate worked.
- Overwrite confirmation: `Yes` around screenshot/window `(566,456)`.
- Squad setup `Start`: top-right around window `(1005,96)`.
- Difficulty modal: Easy selected, all Advanced Content boxes empty/off,
  final `Start` bottom-right around window `(1072,641)`.
- Current helper issue: `setup_modal_start` releases on pause and can hide
  the first-island picker behind the pause menu. Fast recovery is:
  `lightning_ui menu_continue,island_archive,pause`.

## First Island Picker

- Archive known control: window `(300,215)`.
- R.S.T. known control: window `(345,508)`.
- After first-island selection, immediately pause. The intro dialogue appears
  behind pause with timer visible.

## Archive Intro / Map

- Archive intro bottom-right Continue is window `(1005,680)`.
- The route preview/probe path previously burned too much timer. Still veto
  `Mission_Airstrike` for Lightning if a safer route exists: the Time Pod /
  Kill-5 variant produced bad solver outcomes and timing loss in the 2026-06-23
  trial.
- Fresh12 Archive / Airstrike live proof made this a hard speed veto, not a
  preference. Martial District direct-start burst reached deployment at about
  `0:05:17`, turn 1 pause was about `0:06:11`, turn 2 post-action pause was
  about `0:06:52`, and enemy resolution left Electric and Wall destroyed by
  Air Support danger with the pause timer at about `0:07:18`. The post-action
  Reset Turn control was grey/disabled after bridge actions, so never accept
  mechs ending on Air Support danger during Lightning War attempts.
- Clean Archive map OCR/detection at timer `0:00:30` found:
  - Forgotten Hills region center `(698,356)`, OCR-safe click `(693,379)`.
  - The Library region center `(547,388)`, OCR-safe click `(568,387)`.
- Bad click: `(873,307)` hit the visible red sliver behind pause, but did not
  open a preview. It cost about 4 game seconds and should not be retried.
- The Library preview opens from `(568,387)` and shows a top advisor dialogue.
  Preview evidence at `0:00:55`: mission title `The Library`, objective
  `Vek Threat Detected!`, bonuses `Do not kill the Volatile Vek` and
  `Protect the Coal Plant`.
- Mission-preview advisor text box should be cleared from the safe left/top
  target around window `(220,175)`. The old top-center target `(575,203)`
  dismisses the dialogue but can click through into an underlying route region
  after the panel closes.
  Bottom-right `dialogue_textbox` `(1005,680)` is wrong here: it clicks the map
  under the preview and can collapse back to the island map.
- Opening Enemy Activity dialogue also clears from the same top-center target
  `(575,203)`. `Space`/`Enter` did not clear it in the 2026-06-23 trial, but
  two top-dialogue clicks did; after that a short enemy settle reached player
  turn.
- Preview-board/start click target remains window `(848,448)`, but only after
  the top advisor dialogue is cleared. Test burst for next run:
  `Esc -> click route -> click safe mission_preview_dialogue -> click route
  again -> click mission_preview_board -> Esc`.
- Better preview start burst found later: `Esc -> route click -> Space -> Enter
  -> mission_preview_board -> wait -> Esc` reached deployment at `0:00:27`.
- Route-start must snap-pause after Start Mission. A later fresh run clicked
  Start Mission, reached deployment live around `0:01:09`, and was not paused
  until `0:01:13`; that leak is large enough to kill a 2-minute mission.
- Current failed run reached pause timer `0:01:27` still on the map. Restart
  rather than continue this attempt for a 2-minute mission target.
- Fresh13 Archive route recovery burned to pause timer about `0:01:11` without
  deployment. The Pasture preview opened at `0:00:48`, but dismissing the
  mission advisor with old `(575,203)` click-through selected Corporate HQ
  underneath at `0:00:50`. Patch: `mission_preview_dialogue` now uses
  `(220,175)` to stay on the advisor text instead of the route map.
- Fresh14 coordinate lesson: Codex-rendered screenshots are visually scaled in
  chat; derive route clicks from `lightning_map_regions --screenshot-path`,
  not eyeballed display pixels. On the Archive map with Retrospect Park /
  Artifact Vaults, correct window targets were Retrospect `(814,456)` and
  Artifact `(935,440)`. Earlier hand clicks around `(640,395)` did nothing.
- Fresh14 route lesson: Retrospect Park preview at timer `0:00:11` proved
  `Mission_Airstrike` / `AIR SUPPORT`, so hard-veto it. SaveData identified
  Artifact Vaults as `Mission_Survive`; start it only from a clean map state,
  because trying to switch after the Airstrike preview tripped the route-start
  safety recovery and returned to setup.
- Fresh15 Archive map at timer `0:00:05` had Restoration Center and Preserved
  Farms. SaveData did not expose route identities until preview, but
  `lightning_map_regions --screenshot-path` gave correct targets: Restoration
  `(567,404)`, Preserved `(596,527)`. Preserved preview at `0:00:11` proved
  `Mission_Tides` / `TIDAL WAVES`; abandon this roll instead of committing.
- Fresh16 R.S.T. first-island route auto-start reached the map labels Rust
  Dunes / Corporate HQ / Cleft / Maglev Bunkers, then spent to visible timer
  about `0:00:45` before stopping on a Solar Farms preview. OCR proof showed
  `Mission_Solar` / `Defend the Solar Farms` / `Block Vek Spawning 3 times`.
  Treat R.S.T. first-island route probing as data-collection only unless a
  direct cached safe mission appears; Archive remains the preferred speed roll.
- Fresh17 Archive setup Start reached the first-island picker under pause at
  about `0:00:02` with all four corporation labels visible, but the post-Esc
  live reclassification failed and re-paused instead of clicking Archive.
  Patch: when the paused screenshot already proves first-island picker text or
  a corporation panel, trust that proof after the Esc resume and continue to
  the requested island click.
- Fresh18 showed the same setup Start state classified as a generic pause menu
  over the picker rather than strong picker text, so the first patch did not
  fire. Patch follow-up: any pause immediately after verified setup Start is
  treated as sufficient first-island picker proof, because the command's next
  fixed action is only the requested island click.
- Fresh17 continued by standalone Archive select: route map at `0:00:28`
  showed Corporate HQ, The Library, and Artifact Vaults. Auto-start probed
  `Mission_Dam` first and `Mission_Satellite` second, then stopped paused at
  about `0:00:51`. Both are Lightning speed vetoes; abandon this roll. The
  useful signal is that standalone first-island recovery still burns too much
  timer, so use patched `lightning_start_run` directly for the next fresh run.

## Deployment

- `deploy_recommended` must not be called while the pause menu is visible. In
  the fresh2 Martial District run, bridge deployment timed out from pause,
  fell back to UI placement, and burned roughly `0:01:13` -> `0:01:39`.
- Patch preference: resume first, deploy through the bridge with
  `verify_after=False`, disable UI fallback for Lightning speed attempts, click
  Confirm, then snap-pause or enter a pause-before-solve combat loop.
- The invalid ElectricMech placement attempt showed that stale/UI fallback
  deployment can select red non-deploy tiles. Treat UI fallback deployment as
  data-collection only, not achievement-run safe.

## Timing Lessons

- Before a fresh timed run, verify `settings.lua`: `speed=1000`,
  `timer_ui=1`, `no_confirm=0`. A hidden drop to `speed=428` caused a
  preflight stop and would make animations too slow.
- Screenshot sampling is allowed for UI timing experiments. Manual
  `lightning_capture` / `lightning_snap_pause` screenshots and runner
  telemetry screenshots now keep a default rolling cap of 360 PNGs, roughly
  three 2-minute missions at one screenshot per second. Override with
  `ITB_LIGHTNING_SCREENSHOT_CAP`; use `0`/`off` only for a deliberate local
  debugging burst.
- `lightning_snap_pause --run-seconds 0.1` can spend 4-5 seconds in practice;
  do not use it for trivial checks.
- `lightning_snap_pause --run-seconds 2` spent about 10-11 live seconds in the
  2026-06-23 combat-opening trial because it does initial pause classification,
  capture, then post-pause proof. Use `lightning_fast_burst` for known UI
  timing paths.
- New fast primitive:
  `python3 game_loop.py lightning_fast_burst LABEL --sequence 'control,wait:2'`
  verifies pause first, Esc-resumes, executes fixed controls/keys/waits,
  screenshots, immediately Esc-pauses, then classifies after pause.
  Validation: `end_turn,wait:0.25,end_turn,wait:2.0` live burst was `5.536s`
  and paused at visible timer `0:02:13`.
- Route probing plus OCR can spend 30-60 seconds; prefer direct route start
  or accept first playable route when targeting ~2:00 per mission.
- R.S.T. first route was too slow: ~2:00 before turn 1. Avoid R.S.T. early.
- Timing trial data:
  - Route-start wrong sliver click: `0:00:26` -> `0:00:30`, no preview.
  - Clean map snapshot loop: evidence `0:00:30`, pause proof `0:00:33`.
  - The Library visible-text route attempt: `0:00:33` -> preview evidence
    `0:00:35`, then bad bottom dialogue path eventually left map at `0:00:49`
    and pause proof `0:00:52`.
  - Repeated wrong dialogue route attempt showed preview at `0:00:55`, then
    still returned to map. Avoid visible-text/dialogue-bottom path entirely.
  - Current Archive Preserved Farms trial: deployment visible at `0:00:27`, but
    slow preflight/deploy/debug left combat paused at `0:01:45`; opening
    dialogue text cleared by top dialogue clicks, player turn captured at
    `0:01:55`, turn 1 solver actions paused at `0:02:10`, fast end-turn paused
    at `0:02:13`. Restart this run; keep the UI discoveries.
  - Fresh2 Archive Martial District / `Mission_Artillery`: setup helper landed
    on island picker live at `0:00:10` and paused at `0:00:15`; map intro clear
    reached map at `0:00:40`; route/deployment leaks reached deployment pause
    around `0:01:13`; corrected deployment reached opening banter at `0:01:39`;
    player turn UI visible at `0:01:52`; bridge refresh and turn-1 solve/actions
    paused at `0:02:13`; end-turn burst paused during enemy activity at
    `0:02:23`. This is not achievement-viable and should be abandoned rather
    than played out.
  - Fresh3 setup found a release bug: `setup_modal_start` was releasing at
    window `(38,58)`, which hit the pause gear on the first-island picker and
    burned `0:00:10` -> `0:00:34` before Archive was safely paused. The release
    point is now removed.
  - Fresh3 Archive map coordinates at 1280x748 window: Central Museums / Train
    center around `(565,371)`, Artifact Vaults around `(694,359)`.
  - Fresh3 route policy correctly vetoed `Mission_Artillery`, then selected
    `Mission_Train`, but after clearing the preview advisor text the Start
    Mission OCR disappeared. A compact Central sequence opened the preview;
    one additional `mission_preview_board` click started deployment at visible
    timer `0:01:23`.
  - Patch rule from fresh3: if the preview mission is verified and Start text is
    missing after dialogue clear, click the large preview board once and require
    deployment/combat proof. If no transition is proven, pause before blocking.
  - Fresh3 deployment patch proved progress from pause: resume before
    `deploy_recommended`, bridge deploy with UI fallback disabled, and reach
    fresh `Mission_Train` bridge state in enemy/deployment transition. The run
    was already dead on timer (`~0:01:52` before player turn), so restart after
    carrying the data forward.
  - Fresh4 Archive Antiquity Row / `Mission_Airstrike`: route/map/deployment
    still leaked heavily. Deployment visible at `0:01:18`, combat paused around
    `0:01:41`, clean player turn at `0:01:51`, turn 1 paused after actions at
    `0:02:08`, turn 2 paused after actions at `0:02:43`, and cleanup enemy
    activity paused at `0:03:09`. The useful finding is controller overhead:
    `lightning_auto_turn_pause` spent about 14 live seconds in
    `resume_before_execute`, and `lightning_end_turn_pause --run-seconds 5`
    produced 11-14 second live bursts. Patch: `lightning_snap_pause` now writes
    a verified pause guard, and the combat/end-turn wrappers may Esc-resume
    from that fresh guard without re-OCRing the pause menu. The guard is
    invalidated immediately after fast resume so it cannot be reused while live.
  - Fresh5 Archive / `Mission_Tides`: fixed the `lightning_attempt`
    paused-solve default before this run, so combat thinking stayed paused, but
    setup/route retries still burned the mission. First mission completed and
    Region Secured OCR showed `0:04:31`; pause menu OCR after continue showed
    `0h 4m 56s`. Keep as Mode 2 failure data, abandon, and rerun with
    `lightning_autonomous` defaulting to `--iteration-mode flipflop`,
    race cadence `5s`, and the preview-board route start mode that reached
    deployment in this run.
  - Fresh5 setup confirmed the first-island mismatch path was still unsafe:
    final setup Start landed on a Detritus corporation panel and the helper
    returned blocked while the timer kept running to `0:00:19`/`0:00:30`.
    Manual recovery `island_archive,wait:0.8` from pause reached Archive map at
    `0:00:32`, so a wrong corp panel is still a safe first-island picker
    surface. Patch: `lightning_start_run` now recovers by clicking the requested
    island instead of blocking live.
  - Fresh5 Archive intro must be cleared before route clicks: the first
    Colonial/Remembrance click only opened "Archive Inc. Head Office"; a single
    `bottom_continue,wait:0.6` cleared it at `0:00:36`.
  - Fresh5 Remembrance Point / `Mission_Volatile` was a bad speed route. It hit
    deployment around `0:00:41`, but `lightning_attempt` spent about 51 wall
    seconds for deploy + one turn because CLI defaults still used the heavy
    pause-before-solve path. Turn 2 paused at `0:02:05` with no clean plan:
    every candidate predicted at least one grid/building hit. Patch: Lightning
    loop/attempt/segment CLI defaults now use `pause_before_solve=False`; keep
    the explicit flag only for diagnostics.
  - Fresh6 showed setup Start reaches the first-island surface paused at
    `0:00:09`, but the picker detector rejected the pause overlay and the
    recovery path burned to `0:00:30`. Patch: when the pause menu text includes
    all four first-island corporation labels, `lightning_start_run` resumes and
    clicks the requested first island instead of blocking.
  - Fresh6 Archive top route / Restoration Center committed to
    `Mission_Artillery` (bonus: Defend Artillery Support, Protect Power
    Generator). Deployment initial screenshot showed `0:01:15`; first turn
    ended and paused around `0:02:16`. This route is not speed viable unless
    reached much earlier; prefer preview validation or a different first island
    when Archive offers only Artillery/Volatile-style choices.
  - Fresh7 verified the pause-menu first-island recovery path but still burned
    too much UI time. After a blocked picker recovery, manual
    `island_pinnacle,wait:0.8` reached the Pinnacle map at `0:00:48`; one
    `bottom_continue,wait:0.6` cleared the intro at `0:00:49`. Pinnacle map
    regions were Frozen Plains / Ice Forest / Cold Storage. A preview-only
    Frozen Plains probe burned to `0:01:04` and learned stale
    `Mission_FreezeBots` evidence; direct Ice Forest `preview-board` committed
    to `Mission_Stasis` deployment at `0:01:22` with objectives "End with less
    than 4 Mech Damage" and "Protect the Coal Plant". Deployment plus turn 1
    reached enemy phase at about `0:02:16`, so the attempt was abandoned.
    Patch: Lightning speed deployment now caps the deploy->player-turn wait
    floor at 18s instead of 30s, and the runner's flip-flop screenshot cadence
    is applied immediately when telemetry starts/rehomes.
  - Fresh8 start-run recovery still diverged in the standalone
    `lightning_select_first_island` path: after setup Start, the run sat live
    on the Detritus corp panel until the timer reached `0:01:35`; manual Esc
    verified pause at `0:01:43`. Patch: standalone first-island recovery now
    accepts any `_lightning_first_island_picker_ready` surface, including a
    non-target corporation panel, and clicks the requested island from there
    instead of blocking on the bare `island_map_or_unknown` classifier.
    Proof on the dead run: recovery selected Archive and verified pause at
    visible timer `0:01:59`; still too slow, but no longer left the game live
    and blocked at first-island recovery.
  - Fresh9 Mode 2 from verified setup still blocked after Start and returned
    live on the Detritus corp panel at visible timer `0:00:11`; manual Esc
    verified pause at `0:00:22`. Patch: `lightning_start_run` now treats any
    pause menu immediately after setup Start as an assumed first-island picker
    recovery surface, resumes only long enough to require
    `_lightning_first_island_picker_ready`, and re-pauses before blocking if
    that proof is still missing.
  - Fresh9 continued as data after manual recovery: `lightning_select_first_island`
    reached Archive paused at `0:00:39`; route auto-start reached Archive map
    around `0:00:44`, previewed `Mission_Tanks`, and stopped at `0:01:00`
    because the OCR proof was veto-only. Explicit `Mission_Tanks` commit did
    reach deployment paused at `0:01:35`. Deployment placed all three mechs and
    clicked Confirm, but the combat loop timed out waiting through enemy/deploy
    transition; visible timer reached about `0:02:18`. Conclusion: the first
    island plus route path is the dominant leak; route probes and conservative
    preview proof need a fast cached/direct path before more full runs.
  - Fresh10 RST attempt proved the broad post-Start pause recovery branch fired,
    but `_lightning_resume_if_paused` returned `None` after reclassifying the
    already-proven pause menu; the command returned while live on the Detritus
    panel at `0:00:17`, manual Esc verified pause at `0:00:48`. Patch: when
    `post_setup_start_ui` itself proves a pause menu, the recovery branch uses
    a single direct Esc resume fallback instead of trusting a second classifier
    pass.
    Standalone RST recovery proof selected RST and returned paused at `0:01:04`,
    so it is safe but still much too slow; next proof must be the patched
    `lightning_start_run` path on a fresh setup.
  - Fresh11 Archive / Tides Mode 2 failed the mission gate: first mission timer
    reached `0:03:02` after a reset-turn recovery. Tides turn 1 had no clean
    candidate; the accepted speed-loss line left the run late, repeated
    Enemy Activity probes carried the timer from `0:02:12` to `0:02:34`, and
    the final-turn Chain Whip caused an unexpected grid drop plus a poisoned
    re-solve that predicted mech loss. Patch: `Mission_Tides` is now a
    Lightning speed-route veto and is no longer an OCR-only fast-start permit.
  - Fresh19 proved the patched setup-start recovery can now reach an Archive
    map safely at about `0:00:27`, but route probing remains the dominant leak:
    Archive previewed Tanks (`defend the tanks`) then Mines
    (`old earth proximity mines`) and stopped around `0:01:15` with no
    auto-startable route. The route-gate restart then surfaced a Detritus
    corporation panel live; manual `modal_understood` plus `ensure_pause`
    paused at about `0:00:59`, so future race attempts should tighten the
    first-mission route-start gate and keep restart recovery pause-first.
  - Fresh20 with `visible-text` route start reduced good setup starts to
    about `0:00:21`-`0:00:26` and made bad route rolls fail faster:
    Archive Dam/Satellite, RST Terraform/unknown, and Archive Volatile were
    all vetoed without mission start. A later RST restart hit
    `recorded_first_island_selection_map_requires_confirm` and repeatedly
    re-entered a live unknown first-island map until manual interrupt and
    `ensure_pause` paused around `0:01:06`; patch: autonomous segment recovery
    now treats that reason as a first-island selector handoff and uses the
    rotated attempt island instead of looping.
  - Fresh21 Mode 2 with flip-flop screenshots reached Archive paused at about
    `0:00:25`. The route segment spent one unknown-preview probe, then found
    Train and clicked Start; pause proof showed `0:00:51` before deployment.
    Deployment succeeded, turn 1 solved in about 10.6s, but post-enemy/combat
    waits pushed the visible pause timer to `0:02:21` at turn 2 and `0:02:44`
    after manual stop/ensure-pause. This is data, not a keeper: patch speed
    routing so Lightning War treats unknown OCR preview probes as hard stops
    instead of retrying another live preview inside the same first-mission
    gate.
  - Fresh22 speed branch proof hit the user's requested opening precision:
    after setup Start, the fast intro burst selected the first island and
    returned to a verified pause menu at visible timer `0:00:07`. This beats
    the first-island click target (`~0:00:03`) and leaves enough budget for
    deployment if route selection stops wasting preview time. The next leak was
    route auto-start: route-ready took about 5.1s, then an unknown candidate
    previewed as `Mission_Mines` and blocked at about 22.3s segment elapsed.
    Patch: speed-vetoed preview identities now hard-prune the route probe
    cache, not only the old small retry-suppress set, so a learned
    `Mission_Mines`/Volatile/Tides/etc. visual signature is skipped on later
    attempts instead of reprobed. Focused proof:
    `test_lightning_segment_records_speed_veto_probe_in_session_cache`.
  - Fresh23 from title/main menu proved two cold-start UI facts. First, title
    OCR must beat pause geometry: the title screen can be dimmed enough that
    old classification called it `pause_menu`; patch added a title OCR override
    for `Continue/New Game/Options/Credits/Quit/Profile`. Second, after
    Difficulty Setup Start the game can briefly return to the title menu with a
    fresh Continue entry before exposing first-island selection. Patch:
    `lightning_start_run` now immediately clicks `title_continue` and repeats
    the first-island picker wait instead of treating the title as a failed
    pause or thinking live. Focused proofs:
    `test_lightning_title_ocr_beats_pause_menu_override` and
    `test_lightning_start_run_continues_from_title_after_setup_start`.
  - Fresh24 repeated the good opening under race mode: first-island/map pause
    appeared at visible `0:00:09`-`0:00:12`, still inside the user's
    `<=0:00:20` opening target. The leak was route probing/commit. Bad OCR
    identities `Mission_Dam`, `Mission_Mines`, `Mission_Tanks`, and
    `Mission_Volatile` were correctly vetoed, but an OCR-authorized
    `Mission_Force` preview stalled because Start text disappeared after the
    advisor dialogue and the compact retry refused the classifier's
    `mission_preview_panel`/dialogue underlay. Patch: compact preview commit
    builders now accept `mission_preview_panel` as a verified retry context
    after OCR-authorized preview proof, so the runner can try the selected
    region/compact card immediately instead of spending the whole route-start
    gate. Focused proof:
    `test_lightning_atomic_start_uses_compact_preview_after_dialogue_missing_text`.
  - Fresh25 interrupted safely at a verified pause menu around visible
    `0:00:28` after another unknown preview leak. OCR saw only route/map
    labels (`Mercury Ridge`, `Corporate HQ`, `Hardened Shale`) and no mission
    objective text, then the old path still ran the slower recommendation/OCR
    ladder before blocking. Patch: Lightning War speed auto-start probes with
    no expected mission now fail fast from the first paused visible-preview OCR
    when it returns `no_known_preview_text_match`; baseline/manual validated
    starts keep the deeper bridge/recommendation checks. Focused proof:
    `test_lightning_route_start_speed_unknown_visible_preview_fails_fast`.
  - Fresh26 proved the good opening is repeatable but route probes still cost
    too much. Fresh starts paused at visible `0:00:11` and `0:00:18`; bad
    route probes then stopped at about `0:00:14`/`0:00:23`, but the
    `route_start` substep still spent 16.9s-23.8s before returning. Patch:
    Lightning War auto-start preview probes now use a 0.12s region settle, and
    any non-OK visible preview OCR result (`no_known_preview_text_match`,
    `conflicting_known_preview_text_matches`, etc.) fails fast from that first
    screenshot without bridge recommendation fallback. Focused proofs:
    `test_lightning_route_start_speed_unknown_visible_preview_fails_fast` and
    `test_lightning_route_start_speed_conflicting_visible_preview_fails_fast`.
  - Fresh27 restart blocker analysis: the first-island click/retry reached a
    verified pause over deployment at visible `0:00:12`, but speed mode judged
    the older pre-pause island-picker screenshot as latest evidence and
    blocked with `first_island_selection_pending_unverified`. Patch: include
    `pause_after_first_island.pause_verify` before stale click snapshots in
    the first-island selection evidence order. Focused proof:
    `test_lightning_start_run_speed_trusts_verified_pause_over_stale_picker`.
  - Fresh28 route-start leak: RST at visible `0:00:13` found Train, OCR
    authorized `Mission_Train`, but Start text vanished after dialogue and the
    old atomic path spent 37.5s through board/sticky retry before the
    first-mission gate stopped at `0:00:46`. Patch: trusted visible OCR
    previews now try compact preview region/side-card commit immediately after
    dialogue dismissal, before the slow board probe/recommendation ladder.
    Focused proof:
    `test_lightning_atomic_start_uses_compact_preview_after_dialogue_missing_text`.
  - Fresh29 route-probe loop leak: several fresh starts hit
    `route_auto_start_not_allowed` at visible `0:00:08`-`0:00:17` because the
    route plan had a visual region index but no mission id. The selected
    preview OCR returned `no_known_preview_text_match` or
    `conflicting_known_preview_text_matches`; old Lightning War speed policy
    treated that as a terminal block and sometimes failed to persist the
    compact block into the probe cache. Patch: unknown-preview OCR is now a
    retryable live probe result even in speed mode, so the same segment jumps
    to the next visible route candidate; compact blocked summaries also carry
    the OCR reason into the route-probe cache so restarts prune known-bad
    ambiguous regions. Focused proofs:
    `test_lightning_segment_speed_retries_unknown_preview_probe` and
    `test_lightning_route_probe_cache_records_compact_unknown_preview_block`.
  - Fresh30 follow-up: the first Fresh29 run still stopped at visible
    `0:00:10` because the paused preview OCR reason was
    `conflicting_known_preview_text_matches`, which was not in the unknown OCR
    retry/cache set. Patch: treat conflicting known preview matches the same
    as no-match for Lightning War speed probing, so it advances to another
    region or records a durable prune entry instead of ending the attempt.
    Focused proof:
    `test_lightning_route_probe_cache_records_compact_conflicting_preview_block`.
  - Fresh31 post-dialogue leak: after resuming from a paused partial attempt,
    trusted OCR identified `Mission_Force`, but the Start text vanished after
    the advisor dialogue and the old trusted compact path only ran when the
    route handoff had explicit region coordinates. Visual-index route starts
    therefore skipped the fast compact side-card commit and spent ~43s before
    the first-mission route-start gate saw visible `0:00:59`. Patch: trusted
    OCR previews now always try the compact post-dialogue commit; when no
    region point is available the region retry is skipped and the side-card
    commit is used immediately. Focused proof:
    `test_lightning_atomic_start_uses_side_card_after_dialogue_without_region_point`.
  - Fresh32 retry leak: a fresh race start reached the island map inside the
    target (`0:00:13`) and correctly identified a speed-vetoed
    `Mission_Artillery`, but the segment treated
    `route_preview_auto_start_vetoed_before_start` as a terminal suppression
    (`vetoed_mission_retry_suppressed:Mission_Artillery`) instead of caching
    that tile and probing the next visible region. Patch: Lightning War
    speed-vetoed live previews are now retryable; the existing hard-prune
    cache still suppresses that same tile within the exact route scope.
    Focused proof:
    `test_lightning_segment_retries_after_speed_vetoed_probe_preview`.
  - Fresh33 external prompt/system stall: the next race preserved the opening
    budget (`0:00:12`) but stalled inside screenshot capture while
    `get_window_bounds()` waited on `osascript`; a macOS
    `Codex is requesting to bypass the system private window picker` prompt
    was visible over the island map and the old policy refused to clear it.
    The correct Allow click maps from OCR image center `(1250, 860)` through
    Retina window coordinates to screen `(840, 462)` for the current window.
    Patch: screenshot window-bounds lookup now has a 1.5s timeout plus cached
    fallback, and Lightning UI handlers use the standing-approved OCR-based
    `click_macos_privacy_prompt_allow` helper instead of blocking for user
    approval. Focused proofs:
    `test_lightning_handle_screen_clicks_system_privacy_prompt_allow` and
    `test_lightning_start_run_blocks_only_when_prompt_allow_click_fails`.
  - Fresh34 follow-up: a restarted route attempt stalled in
    `activate_game_window()` during the post-dialogue visible Start Mission
    screenshot, and the privacy prompt helper initially failed when visual
    prompt scoring succeeded but OCR observations were absent. Patch:
    `activate_game_window()` is now bounded to 0.75s and rate-limited for 5s;
    the privacy prompt Allow helper falls back to the upper button inside the
    detected prompt button box (`source=prompt_button_region_upper_button`).
    Live proof: the fallback cleared the prompt and `ensure_pause` verified a
    pause menu over the R.S.T. map at visible `0:02:05`. Focused proof:
    `test_macos_privacy_prompt_allow_target_falls_back_to_button_region`.
  - Fresh35 route-start overlay leak: the next autonomous loop kept reaching
    safe route previews at visible `0:00:12`, but after advisor dialogue the
    verified preview sat underneath the pause menu. The old trusted OCR path
    tried compact/board commits without first resuming, so clicks could land
    on the pause overlay and the segment abandoned with
    `route_preview_start_text_missing_after_dialogue`. Patch: trusted
    Lightning War OCR previews now use the existing paused-preview commit
    helper first when the post-dialogue screenshot is a pause menu. That
    helper resumes, clicks the preview board, screenshots immediately, Esc
    pauses, and verifies deployment before any thinking. Focused proof:
    `test_lightning_atomic_start_uses_paused_preview_board_after_trusted_ocr`
    plus the sticky-dialogue route-start regression slice.
