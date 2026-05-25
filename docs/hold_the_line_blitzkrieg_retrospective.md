# Blitzkrieg Hold the Line Retrospective

Date: 2026-05-24
Run: `20260524_195401_412`
Squad: Blitzkrieg
Difficulty: Normal, Advanced Edition ON
Route: Detritus
Target: Hold the Line

Outcome: **Hold the Line** unlocked and `python3 game_loop.py achievements --sync` confirmed 43/70 achievements. The successful turn was Detritus Corporate HQ / `Mission_BlobberBoss` turn 3.

## Successful Line

The key spawn cluster was four emerging Vek markers at bridge coordinates:

- `[5, 4]` = D3
- `[5, 5]` = C3
- `[6, 5]` = C2
- `[7, 5]` = C1

The final blockers before End Turn were:

- WallMech on D3
- RockartMech on C3
- ElectricMech on C2
- RockThrown on C1

Manual bridge actions:

1. Repair ElectricMech on C2, leaving it as the C2 blocker.
2. Move WallMech from E6 to D3, then skip to keep it parked.
3. Move RockartMech from B5 to C3.
4. Fire Rock Launcher at C1 to create the fourth blocker.
5. Click End Turn.

The enemy phase consumed all four spawn markers and Steam immediately reported **Hold the Line** complete on sync.

## What Worked

- Normal difficulty produced enough spawn density. Easy was too sparse for reliable four-marker turns.
- Boss/HQ turns were useful because they can present several spawn markers immediately after deployment and continue spawning under pressure.
- The core Blitzkrieg pattern was still correct: two body blockers, one existing body blocker, and one Boulder Mech rock.
- Direct bridge actions were safer than hand-clicking tiles for the final attempt because each sub-action could be read back from the fresh bridge state.
- Repairing Electric before the block turn mattered. It had enough HP to survive blocking after prior spawn-bank damage.

## Bot Lessons

- The solver top-K sweep is a powerful precheck, but it can miss an achievement-specific geometry that is visibly legal in the engine. In this case, a 100k candidate sweep reported no four-block candidate, yet the bridge-executed line blocked all four markers.
- For `Hold the Line`, a marker already occupied by a mech should be treated as a valuable blocker even if that mech only repairs/skips. The achievement does not require every action to be offensive.
- `spawning_tiles` is the reliable raw field for exact marker coordinates; summary `spawn_points` is only a count.
- When the user explicitly authorizes an achievement Hail Mary, the loop can deviate from the solver if every manual sub-action is verified by `read` before the next action.
- The tactical cost can be acceptable. The unlock turn lost grid and failed the Blobber Leader bonus, but the achievement completed and the island was still secured.

## Follow-Up

- Investigate why `solve_top_k` / `project_plan` did not surface the C2/D3/C3/C1 blocker line. Likely areas: repair/skip action scoring, neutral rock spawn-block projection, or candidate pruning around dense occupied spawn clusters.
- Add a dedicated `Hold the Line` helper that enumerates blocker assignments directly from `spawning_tiles`: body blockers, existing occupied markers, deployable/rock blockers, and final HP survival.
- Next Blitzkrieg-specific target is **Lightning War**. It should use a very different policy: speed over spawn banking.
