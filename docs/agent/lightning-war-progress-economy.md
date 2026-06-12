# Lightning War Progress Economy

This note captures the control philosophy for earning Blitzkrieg's Lightning
War achievement: treat the in-game timer as the scarce currency, and spend it
only on proven state transitions that move the run closer to completing two
Corporate Islands.

## Objective Function

From Codex's perspective, the Lightning War run is not primarily a speedrun of
mouse clicks. It is an optimization problem:

```text
maximize verified achievement progress per in-game timer second
subject to hard safety, proof, and recovery constraints
```

Equivalently:

```text
expected achievement progress
- timer cost
- failure risk
- future friction
```

The key word is `verified`. A click is not progress by itself. A screenshot is
not progress by itself. Progress means the runner can prove that the game moved
to a better state for the achievement.

Examples:

| Burst | Progress value | Timer cost | Notes |
| --- | --- | --- | --- |
| Verified setup -> first island map paused | High | Small | Python must own the timer-starting gap. |
| Island map -> validated mission deployment | High | Medium | Only good if mission identity is proven. |
| Deployment -> first player turn paused | High | Medium | Deployment is often not pauseable. |
| Paused solve -> stored plan ready | High planning value | Zero or near-zero | Spend solver time here. |
| Stored plan -> next player turn paused | High | Medium | Execute through bridge and verify each action. |
| Result panel -> next mission preview/map paused | High | Medium | Panel chains are live-clock friction. |
| Live map inspection by Codex | Negative | High | Pause first or use a bounded local probe. |
| Wrong preview Start | Ambiguous | High risk | May move forward, but can poison the route. |

The conductor should prefer actions with high proven progress, low timer cost,
and low downstream uncertainty.

## State Model

Every state falls into one of three timer categories.

### Free While Paused

These are safe states for Codex/user thought:

- verified pause menu
- proven non-live setup/title/success/failure screen
- verified new-run setup before final Start

Allowed work:

- route thinking
- solver calls
- screenshot review
- dirty-frontier inspection
- diagnosis and patching
- telemetry review

The runner may spend generous wall time here because the achievement clock is
stopped or irrelevant. Pause proof must be real: a clicked pause control is not
enough without a pause-menu classifier, stable timer proof, or equivalent
evidence.

### Productive Live Time

These are live-clock spans worth buying when the preconditions are proven:

- final setup Start through first island handoff
- corporation selection and intro clear
- mission preview commit
- deployment and CONFIRM
- bridge action execution
- End Turn and enemy animation waits
- reward, pod, promotion, shop, and leave-island clears

Python owns these states. Codex should not think while the clock is running.
The local runner either advances deterministically, pauses as soon as possible,
or emits a hard stop with evidence.

### Waste Live Time

These should be hunted and removed:

- Codex thinking while the timer advances
- unpaused screenshot analysis
- repeated broad route clicks
- conservative waits after a detectable state is already present
- live UI inspection that could have been done from pause
- bridge retries from stale combat state
- generic panel clicks against an unclassified screen

Waste is not just slow; it also increases the chance that the screen and bridge
fall out of sync.

## Burst Protocol

The preferred control loop is "paused brain, live bursts":

1. Park in verified pause or another proven non-live state.
2. Build a handoff packet with screenshot, visible UI classification, bridge
   snapshot, timer proof, route/mission/turn, and last action.
3. Choose one small local verb.
4. Python unpauses if needed, executes the burst, and immediately seeks the
   next proven safe boundary.
5. Python verifies the postcondition and pause/non-live proof before Codex
   thinks again.

Useful local verbs:

- `peek_live(max_seconds, predicate)`
- `click_named_control(control)`
- `start_validated_mission(expected_mission_id)`
- `deploy_and_confirm`
- `solve_execute_turn`
- `clear_panel_chain`
- `shop_or_leave`
- `abandon_restart`

`peek_live` should be rare. It should mean "unpause until this predicate is
true or the cap expires", not "wait two seconds because we are unsure." Strong
predicates include:

- visible deployment zones
- fresh bridge heartbeat
- `phase == combat_player` with active mechs
- terminal/reward/shop/map UI detected
- visible pause menu after a pause click
- expected mission id after Start

If a predicate cannot be written, the state probably needs a better bridge
field, classifier, or deterministic helper.

## Progress Ledger

Each burst should log a compact progress ledger row:

```json
{
  "before_state": "pause_menu_on_mission_preview",
  "intended_progress_delta": "commit Mission_Tides and reach deployment",
  "timer_before": "00:04:12.300",
  "timer_after": "00:04:20.800",
  "timer_delta_seconds": 8.5,
  "postcondition": "deployment_zones_visible",
  "postcondition_proven": true,
  "pause_or_non_live_proven": false,
  "risk_or_loss_accepted": [],
  "next_safe_state": "must_act_deployment",
  "result": "progress"
}
```

The ledger lets failed attempts answer the important questions:

- Which bursts bought real progress?
- Which bursts spent timer without changing state?
- Which state proofs were too conservative?
- Which mission types were expensive in practice?
- Which panel chains consumed the saved combat time?
- Which restarts were cheaper than recovery?

Over time, route scoring should learn from this ledger instead of relying only
on static mission preferences.

## One-Way Gates

The runner should be aggressive on proven low-risk actions, but conservative
before irreversible gates.

High-risk gates:

- final setup Start
- corporation selection after timer start
- mission Start
- deployment CONFIRM
- End Turn
- shop purchases when grid is low
- abandon/restart

Before these gates, require enough proof to answer:

1. What state are we in?
2. What action is being committed?
3. What postcondition should prove success?
4. What are the timer and safety risks?
5. Can we recover faster than restarting if this goes wrong?

After these gates, do not hand live control back to Codex. Python continues to
the next safe boundary.

## Combat Policy

Combat should be bridge-first and solver-owned:

1. From pause, briefly unpause if needed to refresh the heartbeat.
2. Pause again and solve from a fresh bridge state.
3. Select a candidate under the Lightning War speed policy.
4. Unpause and execute stored bridge actions.
5. Verify after each action.
6. Click End Turn with calibrated controls.
7. Wait for next player turn, terminal panel, or blocker.
8. Pause immediately once the next player turn is available.

Codex should not manually choose move/attack lines during ordinary play. If the
solver blocks, Codex may inspect the frontier only after the game is parked in
pause or another safe state.

Lightning War can accept some ugly outcomes when they are predicted and logged:

- missed pods
- optional objective loss
- imperfect islands
- low reputation
- non-terminal grid or building damage when grid stays above zero
- nonlethal mech HP loss only when the speed policy explicitly allows it

Still hard stop or restart on:

- grid collapse
- pilot death or unhandled KIA screen
- mech destruction when the runner cannot safely continue
- stale/uncertain combat board
- unresolved desync
- unknown loss kinds
- route mismatch into an unplayable or hard-veto mission

## UI Tail Policy

The achievement clock is often lost outside combat. Reward, pod, promotion,
shop, island-leave, HQ, and intro panels must be treated as first-class live
bursts rather than cleanup afterthoughts.

Rules:

- Use named controls and panel-chain handlers, not broad generic clicks.
- Clear safe chains locally until map/shop/preview/pause is proven.
- If grid is below max, buy Grid Power first.
- If grid is full and no deterministic high-value purchase is required, leave.
- Ignore pods and optional rewards when they add timer friction.
- Preserve screenshots and UI classifications for unexpected panels.

False positives are expected. Island-complete screens can resemble KIA or
reward panels, setup can resemble pause, and dialogue can hide Start Mission.
Bridge refinement, OCR, and current screenshot evidence should decide the
specific control.

## Relationship To The Fast Walkthrough

The fast walkthrough script is best viewed as a catalog of proven live bursts:

- startup setup and first island timing
- known corporation and Continue controls
- deployment and CONFIRM cadence
- paused solve plus stored action execution
- End Turn observation
- result-panel and next-mission clears

It should not become the sole strategy. Fixed timings are excellent when the
state is known, but brittle when route slate, dialogue, deployment, or reward
chains vary.

The optimal architecture is a hybrid:

- use the fast walkthrough's timings for known high-progress bursts
- use pause proof and handoff packets for uncertain decisions
- keep Codex as the paused planner/debugger
- keep Python as the live-clock actor

## Implementation Direction

Short-term improvements:

- Add progress-ledger events to Lightning War telemetry.
- Label each burst as `progress`, `waste`, `safety_stop`, `restart`, or
  `evidence_only`.
- Convert repeated "wait N seconds" logic into `wait_until(predicate, cap)`.
- Track start-to-start mission cost including route, deployment, combat, UI
  tails, shop, leave, and next Start.
- Record which route decisions were proven by bridge, OCR, screenshot, or
  inferred stale state.

Medium-term improvements:

- Score route candidates by expected progress per timer second.
- Learn empirical mission costs from attempt telemetry.
- Detect and summarize the largest timer waste after every attempt.
- Promote repeated screenshot/classifier pain into bridge fields or named
  controls.
- Keep a small library of safe live bursts with explicit preconditions and
  postconditions.

Long-term target:

```text
Python continuously chains the best proven live bursts.
Codex thinks only from verified safe states.
Telemetry explains every second spent.
The run restarts quickly when expected progress per timer second is no longer
good enough to beat 30:00.
```

That is the Lightning War north star: spend timer only when the run is buying
verified progress toward two secured Corporate Islands.
