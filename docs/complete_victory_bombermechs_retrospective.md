# Complete Victory Bombermechs Retrospective

Date: 2026-06-24
Run: `20260624_083454_845`
Squad: Bombermechs
Difficulty: Easy
Advanced Edition: On

## Result

**Complete Victory** unlocked after a two-island Bombermechs victory and final Volcanic Hive clear. The profile tracker reached `Global_Victory_Complete = 10`, the ITB log wrote `Set Steam Achievement Ach_Global_Victory_Complete`, and the Steam local cache marked `Ach_Global_Victory_Complete` achieved with unlock time `2026-06-24T17:12:30Z`.

This confirmed the practical route for the long-term squad-victory achievement: any 10 distinct squad wins count in the Advanced Edition era, and a 2-island Easy victory is enough.

## Verification Evidence

- Visible screen: `Victory!`
- Profile file: `profile_Alpha/profile.lua`, tracker `Global_Victory_Complete = 10`.
- ITB log: `Set Steam Achievement Ach_Global_Victory_Complete`.
- Steam local cache: `achieved = 1` for `Complete Victory`.

Steam was offline, so the local cache and ITB log were the authoritative confirmation path. The cache path was under `Steam/userdata/<steam_user_id>/config/librarycache/590380.json`.

## Final Cave Emergency

The final cave reached turn 4 with grid `5/7`, Renfield Bomb alive at `D5`, and no clean candidate in the first 1000 solver candidates. The top candidate preserved the timeline but predicted one mech HP loss, which fails the narrow final-cave pylon-loss exception because that exception requires all mechs to survive without HP/status/danger debt.

A deeper sweep found candidate rank `1880` as the best emergency-valid tradeoff:

1. PierceMech `F4 -> F5`, AP Cannon at `F6`.
2. BomblingMech `D3 -> C3`.
3. ExchangeMech `C4 -> D3`, Force Swap `C3/G3`.

Predicted outcome:

- Grid `5 -> 2`.
- Pylons `7 -> 6`.
- Pylon HP `14 -> 11`.
- Renfield Bomb alive.
- All mechs alive with no HP/status/danger debt.
- No timeline collapse.

The exact dirty token was `5b451b2e54c02adf`. `auto_turn` executed all three bridge actions and each action verified. The threat audit still saw the reviewed B3 pylon hit, which matched the consented emergency loss, so the held End Turn click was dispatched.

## Lessons

- For final cave, do not stop at the top dirty candidate when it carries mech HP debt. Exact candidate-rank searches can expose lower-scoring lines that satisfy the final-cave emergency predicate.
- Validate manual geometry ideas with `project_plan` or replay before live execution. A plausible manual line in this run failed because one move was out of range and another destination was blocked.
- After final End Turn, the bridge may briefly show a stale or post-action combat board with `active_mechs = 0`; visible screen and save/profile evidence are more authoritative for victory verification.
- Offline achievement verification should use all available local signals: visible victory, profile tracker, ITB log, and Steam client cache.
