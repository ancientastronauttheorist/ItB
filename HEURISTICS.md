# Lightning War Heuristics

- Screenshot timer beats logs or memory when deciding Lightning War pace.
- A visible pause menu with stable timer is a safe thinking state even if the
  bridge heartbeat is stale.
- `mission_preview_requires_route_validation` means no Start Mission click yet;
  first prove a route candidate or bridge-preview mission id.
- Optimize route/map reliability before combat speed; existing evidence says
  combat can beat the 3-minute mission ceiling.
- For Lightning War, ignore optional objectives when they cost time, but never
  accept grid collapse, pilot death, mech destruction, desync uncertainty, or
  unmodeled primary objective loss.
- If a mission consumes more than `0:03:00`, classify the timer leak as route,
  deployment, combat, reward/shop, or recovery before changing strategy.
- Line to keep: when paused behind an uncertain preview, reveal once, classify,
  and re-pause before any irreversible click.
- Do not spend live timer shopping for a perfect first mission; take the first
  proven baseline-safe low-friction mission and let bad slates reroll safely.
- Before acting on a saved next action, verify the current visible UI still
  matches its precondition.
- Distinguish setup-open Start from final timeline Start; the first opens
  verification, the second begins the live timeline.
- Repeated manual UI instructions should include the detected control crop and
  center.
- For repeated manual blockers, include an annotated screenshot target before
  declaring the resumed loop blocked.
- Resumed blocked audits need an explicit repeat count.
- Resumed blocker count `3/3` means set the goal blocked.
- For Lightning War, visible Start Mission text is the default commit target.
  Broad preview-board/dialogue-board commits are explicit fallback probes, not
  the normal path.
- A route preview that validates the expected mission but does not produce fresh
  deployment or combat proof is a stop, not a handoff.
- A visible Start Mission click with `NO_BRIDGE` or pause/menu still visible
  afterward is a failed transition until proven otherwise.
- Diagnostic `stale_bridge_preview_ignored_for_route_scoring` is evidence that
  stale bridge data was discarded, not a hard stale-bridge blocker by itself.
- Active Head Office intro with `CONTINUE` should not be reclassified as pause
  merely because OCR sees the top-left `MENU` tooltip.
- Paused HQ intro is a UI panel, not route/deployment proof; reveal or clear it
  before trusting stale deployment-looking bridge state.
- Strong pause-menu visual score plus heavy dark overlay is valid pause proof
  even before OCR is attached; use it to resume/reveal safely, then re-pause.
- Visible island map proof can outrank stale deployment bridge files, but it
  still cannot authorize Start Mission unless route identity or safe preview
  proof is assigned.
- For irregular corp-map regions, the red-blob centroid can miss the mission
  preview; prefer a click target just below the OCR route label near the mission
  objective icons.
- Unique visible route labels can choose which region to preview-probe, but they
  are not mission identity and must not bypass preview validation or Start
  Mission transition proof.
- If `clear_tail_pause` returns `NO_ACTION` while Head Office `CONTINUE` is
  still visible, block as `intro_continue_still_visible`; do not call the tail
  cleared or enter route/recommend logic.
- Route-name OCR click targets should stay close to the visible route label;
  dropping down onto objective icons can fail to open mission preview.
- If visible timer is already over `0:03:00` before first mission progress,
  restart before route probing; route-click tuning on a dead segment wastes the
  next attempt.
- Preserve dialogue-repeat preview probing for unknown safe Lightning auto-start
  probes, but keep Start Mission authority tied to verified mission identity or
  explicit safe visible OCR proof.
- Add visible-preview OCR vocabulary for hazard/objective words as soon as a
  live preview times out without a mission id; a missing pattern can convert a
  clean veto into a route-start timeout.
- Cataclysm preview text (`CATACLYSM`, `cataclysmic`, `fall into the depths`)
  means `Mission_Cataclysm`; speed auto-start policy should veto it before
  Start Mission.
- Structured visible-OCR speed vetoes should not depend on how the preview was
  selected; explicit retry indices need the same pre-start veto reporting as
  auto-start probes.
- A route-start envelope below observed screenshot/OCR latency creates false
  `route_start_click_failed` stops. Keep enough wall budget for one validation
  screenshot, but restart instead of spending it after the first-route gate.
- Existing-preview validation needs concrete preview proof. Do not treat
  `classifier_visible_ui` or `pause_ocr_override` from a pause-menu screenshot
  as authority when durable evidence still shows the island map.
- If `visible_preview_ocr` contains pause-menu text such as `Timeline
  Playtime`, `SAVE and QUIT`, and difficulty labels, the helper OCR'd the pause
  overlay, not a mission preview.
- A stale or ignored bridge preview may veto a known speed-risk mission, but it
  cannot authorize Start Mission or replace visible route identity proof.
- When the branch is still under the first-route-start gate after a safe
  tooling fix, spend one guarded resume before abandoning the branch.
- Route-start timeout and preview-not-opened stops are restartable only when
  they are proven precombat/preview-only; deployment or combat evidence turns
  them into hard stop evidence instead.
- Live runner manifest metadata must be best-effort and bounded. Do not spawn
  `git` in a timed Lightning path when direct `.git/HEAD` file reads are enough.
- If visible timer proof is already over `0:03:00` before first-mission
  progress, abandon/reset before any route/deployment/combat optimization.
- A Detritus Head Office `CONTINUE` panel with active mission/deployment bridge
  context is not a safe planning state; reset or recover through the documented
  abandon path rather than thinking live on the clock.
- `Mission_Tides` visible OCR is a narrow Lightning War start authority when
  route policy does not veto it and post-start deployment must still verify the
  same mission id.
- OCR-only speed starts remain blocked for non-allowlisted missions; do not let
  one safe Tides exception become broad OCR commit authority.
- A macOS private-window/screen-audio access prompt is an external prompt stop
  sign. Save proof, stop live automation, and require user resolution before
  another screenshot, route, deployment, combat, or runner command.
- If a speed run reaches `route_auto_start_not_allowed` with
  `bridge_snapshot_unavailable_visible_island_map`, do not try to force Start
  Mission. Pause, preserve proof, inspect route telemetry, or reset from setup.
- Vetoed mission proof is useful progress: `Mission_Airstrike` visible OCR
  should block before Start Mission and then trigger a fast route retry or reset.
- A final paused branch under `0:03:00` is still dead if no route identity or
  safe handoff exists; timer headroom does not authorize ambiguous starts.
- A pending route-start retry needs the full context: visual index, click
  coordinates, expected mission, preview-close intent, verify-route mode, and
  start mode. Index alone can lose the safe handoff after a segment wall cap.
- `island_map_or_unknown` with zero extracted red mission regions is
  first-island/world-map evidence, not route-map proof. Retry the island click
  once, then block without recording `current_island`.
- Speed route-start budgets must leave time for at least one screenshot/OCR
  validation; too-small subcall caps create false click/preview failures.
- First-island picker proof beats route candidates. If the visible map has zero
  mission red regions, block as first-island selection even when save-backed or
  stale route candidates exist.
- Labeled route maps can have noisy preview-card scores; multiple visible route
  labels are strong evidence of a clean route map, not an occluding preview.
- On macOS, the Archive first-island control should target the island interior
  around window-local `(300,215)`; the older edge point can leave selection
  pending.
- After `current_island` or later run context is recorded,
  `island_map_or_unknown` plus zero extracted red regions is ambiguous selected
  island-map evidence, not enough to call the four-corporation picker.
- If a guarded resume stops at `route_auto_start_not_allowed` with
  `bridge_snapshot_unavailable_visible_island_map`, preserve proof and patch
  route extraction or reset; timer headroom is not Start Mission authority.
- If a no-bridge route stop leaves the map unpaused, run
  `lightning_ui ensure_pause --include-ocr` before thinking or editing.
- A recorded `current_island` is not enough to prove the first island opened;
  if unpaused picker evidence remains, confirm the same island through
  `lightning_select_first_island`.
- Pause-menu screenshots with `Timeline Playtime`, `pause_ocr_override`, or a
  heavy dark overlay must not be used as first-island picker proof.
- Real route labels without mission identity are still not Start Mission
  authority. If they appear near `0:03:00`, preserve proof and reset.
- After setup Start, dark transition frames must not authorize first-island
  coordinate clicks. Wait for a non-dark picker classification or block before
  clicking.
- On macOS, final setup-modal Start can overlap the Detritus island hit area
  during the transition. Use a short hold and require selected-corp OCR to
  match the requested first island before any island coordinate click.
- For first-island corp panels, title text beats dialogue text. A dialogue
  mention of `R.S.T.` does not prove R.S.T. when the selected panel title is
  Detritus.
- Multiple distinct visible route labels may choose which live-preview probe to
  attempt by visual index. They are not mission identity and must still pass
  opened-preview validation before Start Mission.
- For Lightning War safe auto-start probes, legacy dialogue/preview-board route
  modes should normalize to visible Start Mission after preview validation;
  broad board/dialogue commits are slow fallbacks and can trigger false
  route-start timeouts.
- Do not raise the route-start wall budget before reducing proof work; a bigger
  timeout can avoid a false stop while still burning enough visible timer to
  kill the first-mission gate.
- Once visible-text route-start is live-proven and route-ready repeats under
  the first-mission pace gate, a `12s` speed subcall cap is too small for
  preview/OCR/start validation. Give speed route-start the full `30s` floor and
  judge pace by visible timer proof.
- A failed third-attempt first-island selection after two route-start timeouts
  is cleanup evidence, not proof that route-start got worse; reset to setup and
  fix the repeated route-start stop first.
- `Mission_Force` / R.S.T. defensive-shield preview text is distinctive and is
  not speed-vetoed; it can be narrow Lightning War visible-OCR start authority
  when followed by visible Start Mission and post-start mission-id proof.
- `Mission_Solar` preview OCR is useful veto evidence only. Solar remains a
  speed-risk mission and should trigger retry/reset rather than Start Mission.
- For OCR-labelled route probes, the OCR label click target is safer than the
  red-region centroid on compact Archive maps; use label coordinates for OCR
  probes while keeping generic distinct-label probes on visual-index handling.
- Opening a safe Force preview is not enough; route-start must click visible
  Start Mission and prove the post-start mission id quickly, or preserve an
  exact safe-preview handoff instead of spending the whole subcall.
- A failed third-attempt Pinnacle first-island cleanup after Archive/R.S.T.
  route gates is cleanup evidence, not a reason to broaden route-start safety.
- A corporation-picker/first-island screen with no mission red regions is safe
  to click the requested island only when the selected-corp identity is
  unreadable; readable wrong-corp panels still block.
- Route map previews still require mission OCR authority before Start Mission;
  first-island fallback evidence must not leak into route-start authority.
- Solar and Airstrike preview vetoes are useful evidence but too expensive to
  repeat; cache or pre-rank away from veto-prone candidates before spending
  another full route-start probe.
- Route-probe cache may choose which preview to try next, but it must never be
  Start Mission authority.
- In speed mode, use Archive/R.S.T./Archive for three-attempt first-island
  cycling unless the user changes the preferred island.
- If an opened preview shows `Do not kill the Volatile Vek` or `Protect the
  Power Generator`, treat it as `Mission_Volatile` speed-veto evidence and
  return quickly; a `route_start_subcall_timeout` on visible Volatile text is a
  tooling bug.
- When a final branch is paused under `0:03:00` but route-start timed out, do
  not use the timer headroom to click Start Mission. Patch the proof path,
  then reset from verified setup.
- After a preview opens, visible OCR veto checks must run before slow
  post-preview route recommendation refreshes. Veto evidence is allowed to
  block quickly, but it is not Start Mission authority.
- If a first mission reaches deployment only after multiple route-start segment
  caps, completing combat may be useful telemetry but cannot become Lightning
  War proof once visible timer exceeds `0:03:00`.
- A bridge phase of `combat_enemy` with no mechs and deployment zones can still
  be a deployable screen; `deploy_recommended` can recover it, but the recovery
  is too slow for proof unless automated inside the runner.
- `Mission_Tides` can be route-safe, but it is not automatically pace-safe; the
  route/deploy handoff must be fast enough to leave combat inside the segment
  gate.
- Once screenshot/OCR proves a mission segment is over `0:03:00`, stop live
  proof play and reset/improve. Do not spend more End Turn clicks on that
  branch except for deliberate offline telemetry.
- `Protect the Emergency Batteries` is not Airstrike mission identity by
  itself; it can appear alongside a Tides preview. Use distinctive `air
  support` text for `Mission_Airstrike`.
- Emergency-battery objective text alone should classify as unknown mission
  identity, causing a safe route block rather than a false Airstrike result.
- Unknown-OCR route-probe cache entries are only durable when the OCR reason is
  still valid; stale conflicts from old matcher rules should not hard-prune a
  candidate after an OCR fix.
- Standalone route-auto-start resume commands should consume and update the
  same session route-probe cache as the runner, but cache remains selection
  evidence only.
- Route-probe cache writes should be restricted to real failed route-start
  probes; successful starts and dry-runs should not mutate cache state.
- Explicit route-probe cache inputs should bypass session cache loading; the
  session cache is only a default for standalone route-auto-start segments.
- Route-probe hard-prune cache entries require exact first-island, routing, and
  mission-index scope. If scope is missing or mismatched, probe again instead
  of silently skipping a candidate with a reused label or visual index.
- Blank session island scope should disable hard-prune cache use for that
  segment; the speed cost of one extra probe is safer than a false skip.
- If parsed OCR timer and raw screenshot timer disagree, preserve and trust the
  raw screenshot for pace/proof decisions.
- A macOS private-window/screen-audio access prompt is not a recoverable route
  blocker for automation; stop live commands until the user resolves it.
