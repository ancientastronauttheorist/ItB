# Hazardous Healing and Overkill Retrospective

Date: 2026-05-24 sync confirmation
Run: `20260522_193613_471`
Squad: Hazardous Mechs
Difficulty: Easy, Advanced Edition ON
Route: 4 Corporate Islands plus Volcanic Hive
Targets: Healing, Overkill

Outcome: **Healing** and **Overkill** unlocked. The run reached the Victory screen with the Hazardous Mechs, but the immediate local sync still showed 40/70 because Steam was being used in offline mode. After Steam was brought online and Into the Breach was restarted, `python3 game_loop.py achievements --sync` confirmed 42/70 and marked both achievements complete.

## What Worked

- Powered `Passive_Leech_A` mattered. With +1 Heal, each qualifying kill-heal could restore up to 2 HP, making Healing possible without needing ten separate kill credits.
- The achievement target needed deliberately "dirty" tactical shaping. The best Healing lines were not always the prettiest safety/score lines; Leap Mech and UnstableTank needed to spend HP, then claim kills while damaged.
- Overkill came from the straightforward Hazardous combo: apply A.C.I.D., then hit with powered `Brute_Unstable_AB`. The Volcanic Hive `Mission_Final` turn 2 replay recorded `enemy_damage_dealt = 8`.
- Running the full timeline was useful even after the target battle windows. The final victory kept the run alive long enough to verify that no late simulator fix had poisoned the save.

## Bot Lessons

- Do not conclude that an achievement failed solely from an offline Steam cache sync. If the game is offline or Steam is offline, record the suspected unlock, then re-sync after Steam is online and the game has restarted.
- For Healing, reward actual HP restored, not theoretical Nanobots triggers. A kill at full or capped HP may not advance the achievement.
- Keep the Nano Mech/passive alive when possible, but live evidence in this run reinforced that the passive can remain active through dangerous Hazardous timing windows.
- Hazardous achievement runs stress unusual simulator surfaces: self-damage revive timing, powered weapon IDs, ACID doubling, corpse pushes, terrain kills, occupied Ice, lava/final cave hazards, and Viscera Nanobots status handling.

## Follow-Up

Hazardous Mechs now have **Healing**, **Overkill**, and **Immortal** complete. The later Immortal route is documented in `docs/immortal_hazardous_retrospective.md`; its lesson is the inverse of this Healing/Overkill run: preserve battle-end mech survival above optional objectives, kills, reputation, and aggressive self-damage shaping.
