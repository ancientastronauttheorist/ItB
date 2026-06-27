# Powered Blast Bombermechs Retrospective

Date: 2026-06-11 CT
Run: `20260611_202233_019`
Squad: Bombermechs
Difficulty: Easy, Advanced Edition ON
Route: Archive
Target: Powered Blast

Outcome: **Powered Blast** unlocked. `python3 game_loop.py achievements --sync`
marked the achievement complete and raised the confirmed tracker to 53/70.

## Successful Line

The unlock happened on Archive `Mission_Artillery` turn 4.

Board ingredients:

- Pierce Mech at D2
- Walking Bomb at C2
- Scarab1 at B2 with 2 HP

Execution:

1. Archive Artillery fired at D2 to clear the Leaper/web pressure.
2. Bombling Mech moved to C6 and fired Bomb Dispenser at C2.
3. The Walking Bomb spawn produced a benign spawn diff, so `auto_turn`
   re-solved from the fresh bridge board.
4. Pierce Mech moved to D2 and fired AP Cannon at C2.
5. AP Cannon pierced the Walking Bomb and killed Scarab1 at B2.

The post-mission reward screen showed Region Secured, both objectives complete,
and civilians protected. The next Steam sync confirmed **Powered Blast**.

## What Worked

- Modeling Bomb Dispenser before continuing was necessary. `Ranged_DeployBomb`,
  `DeployUnit_Bomby`, and `DeployUnit_SelfDamage` needed Python/Rust coverage
  before the solver could reason about Bombermechs.
- The achievement-weight overlay mattered, but the exact opportunity only
  appeared after the Walking Bomb existed on the live board.
- The re-solve after the spawn diff was useful rather than suspicious: it found
  the actual Pierce Mech lane from D2 through C2 into B2.
- A 2-HP target is the cleanest practical setup. It avoids needing bump damage,
  terrain collision, or AP Cannon damage upgrades.

## Bot Lessons

- For Powered Blast, do not just deploy a bomb near an enemy. The AP Cannon
  shot must pierce the Walking Bomb as the first target and kill the enemy on
  the second hit.
- If `DeployUnit_Bomby` appears as stale research after it is already cataloged,
  resolve the queue with the known Walking Bomb reason before End Turn.
- A spawn verification diff from `Ranged_DeployBomb` can be nonblocking when
  the research queue is clear, the bridge state is fresh, and the follow-up
  re-solve verifies every action.
- The solver should keep the `powered_blast_bonus` event hook active only for
  the named target; generic Bombermechs play should still prioritize ordinary
  survival, objectives, and grid.

## Follow-Up

- Continue Bombermechs only if targeting **Hold the Door** or **No Survivors**;
  **Powered Blast** itself is complete.
- If future Bomb Dispenser turns keep reporting low-confidence spawn fuzzy
  detections, add a narrow normalizer so modeled deployable spawns do not look
  novel after v263+ support.
- For Hold the Door, extend the Bombermechs scoring path from single-shot
  Powered Blast geometry to cumulative Walking Bomb spawn-block accounting.
