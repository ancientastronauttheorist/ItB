# Solver Goal Principles

This project should treat the solver as a tactical judge, not only as a scalar score optimizer.

Into the Breach is a game of irreversible losses, action economy, and exact tactical prevention. A solver that simply maximizes a weighted score can make choices that look numerically reasonable but feel strategically wrong, such as trading one grid for a kill, a spawn block, or a cleaner board. Strong play should be much more reluctant to make that trade.

## North Star

Win the campaign by preserving irreversible value.

The default tactical rule is simple:

> Prevent building damage unless the alternative is worse in campaign value.

This includes damage that does not immediately reduce the visible grid meter. A building HP loss is still a real loss: it can become grid damage later, it consumes buffer, and it often signals that the solver accepted an unsafe plan.

## Priority Order

The solver should rank outcomes lexicographically before applying softer weighted scoring.

1. Do not lose the run.

   Avoid grid collapse, mission-critical unit death, objective failure that ends the mission, or any forced line that makes victory impossible.

2. Do not take building or grid damage.

   Treat any building hit as a red-alert event. This includes partial damage to multi-HP buildings, delayed grid-meter updates, and hits that might be resisted by grid defense. Grid defense is luck, not a plan.

3. Do not fail valuable objectives.

   Protect bonus objectives, grid-reward buildings, pods, trains, bombs, terraforming targets, satellite launches, and other mission-specific value. Some objectives can justify a grid trade, but that trade must be explicit and rare.

4. Preserve next-turn action economy.

   Mech HP often matters less than buildings because it resets after the mission, but disabled, dead, webbed, frozen, stranded, or badly positioned mechs can cost future actions. Losing action economy is dangerous because it creates the next building loss.

5. Improve board control.

   Kill or disable Vek, block spawns when safe, reduce queued threats, smoke or redirect attacks, and position the squad near future building clusters.

6. Optimize secondary value.

   After the above are safe, optimize XP, clean kills, achievement progress, elegant positioning, and other nice-to-haves.

## Clean Plan Rule

The solver should prefer clean plans as a hard phase of search:

1. Generate candidate plans.
2. Filter for plans with no building damage, no grid damage, and no objective damage.
3. If any clean plan exists, choose only among clean plans.
4. If no clean plan exists, enter emergency mode and minimize irreversible harm.
5. Apply weighted scoring only after the current priority tier is settled.

This structure prevents a high kill score or positional bonus from accidentally buying a building hit.

## Emergency Mode

Emergency mode should activate whenever the best known projection loses grid, damages a building, fails an objective, or creates a severe next-turn action collapse.

When emergency mode is active, the solver should broaden its search before conceding the loss:

- Allow soft-disabled or low-confidence weapons if they can improve building/grid outcome.
- Consider mech body-blocking even if it costs HP.
- Consider ugly swaps, self-damage, fire, acid, or temporary positional sacrifices.
- Use mission units and controllable allies as first-class actors.
- Preserve every action that can affect a building-threatening attack during pruning.
- Prefer "one mech takes damage" over "one building takes damage" in nearly all normal cases.

Only after these options fail should the solver accept building or grid damage.

## Mission Units

Friendly controllable units are not flavor. They are action economy.

Mission units such as the Terraformer, tanks, artillery helpers, bombs, and other controllables should be treated as active player units when they are alive, active, and have a usable weapon or mission action. Their survival, readiness, and objective contribution should be part of the solver's core model.

For missions with a special action, the solver should understand what that action is for. For example, a Terraformer action is not merely another attack; it is tied to a mission objective and should be scored accordingly.

## Building Damage Accounting

The solver should track building value through more than the visible grid number.

Important signals include:

- `grid_power`
- total building HP
- per-building HP changes
- buildings destroyed
- objective-building HP and survival
- whether a queued enemy attack still hits a building after the plan

If `grid_power` stays the same but building HP drops, the plan should still be considered dirty.

## What We Learned From The Lightning Point Loss

In the Lightning Point Terraformer mission, the solver predicted a grid drop before the turn ended and still accepted the plan. That is the failure pattern this document is meant to prevent.

The solver should have treated the predicted grid loss as an emergency, expanded its options, and refused to end the turn until it had either found a clean plan or produced evidence that no clean plan existed.

The better design is not just "adjust the weights." The better design is to make the solver obey tactical priorities first, then use weights inside the safest available tier.

## Implementation Direction

Good next steps:

- Add a forecast-loss gate before End Turn.
- Make building HP loss a first-class dirty-plan signal.
- Run emergency search when projected grid or building HP drops.
- Let emergency search use soft-disabled weapons when they improve irreversible outcomes.
- Rename and normalize "active mechs" into "active player units" where mission units are intended.
- Add regression tests from real failed turns where the solver accepted predicted grid or building damage.
- Make pruning threat-aware enough that building-saving actions are never discarded early.

The solver should feel like a cautious expert player: calm about taking mech damage, ruthless about preventing building hits, and willing to use strange-looking tactics when they preserve irreversible value.
