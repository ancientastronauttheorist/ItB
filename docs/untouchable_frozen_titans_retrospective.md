# Untouchable Frozen Titans Retrospective

Date: 2026-05-22
Run: `20260522_133722_695`
Squad: Frozen Titans
Difficulty: Easy, Advanced Edition ON
Island: Archive
Target: Finish one Corporate Island without taking mech damage

Outcome: **Untouchable unlocked in-game** after Corporate HQ / `Mission_StarfishBoss`. The reward flow showed **Achievement! Untouchable** on the island map. The immediate `python3 game_loop.py achievements --sync` still reported 39/70 from Steam/client cache, so the tracker may lag the visible game award.

## What Worked

- Easy Island 1 was the right pressure level. Archive let the run finish before higher-tier Vek and dense spawn patterns made no-HP positioning brittle.
- Frozen Titans were viable once the bot treated mech HP as the only sacred resource. The successful route accepted ordinary grid/building risk where needed and ended HQ at grid `6/7`.
- The run stayed disciplined about safety blocks: no dirty consent for `mech_hp_loss`, exact review for any grid/building trade, and a fresh read before clicking End Turn when a warning mentioned mech status.
- Mission avoidance mattered as much as tactics. The run succeeded after explicitly avoiding Mite / Old Earth mine missions, Bad Repairs, webber-heavy boards, volatile Vek, trains, and heavy environmental chaos.
- The final HQ fight showed the clean pattern: kill or freeze the boss, remove direct mech threats first, and click End Turn only after the threat audit and actual bridge state both agree that mech HP remains full.

## Bot Lessons

- For active Untouchable runs, `mech_hp_loss` is a restart condition, not a dirty-plan tradeoff. Repaired damage is still invalid.
- Building/grid/objective damage is strategically spendable. Keep grid at 2+ when possible so one model miss does not collapse the timeline.
- Manual low-score lines are legitimate only after a fresh-board audit predicts no mech HP loss and no hidden damage event; otherwise trust the solver or restart.
- Shields are valuable because they can absorb hits without HP loss, but do not assume every shield interaction cancels Vek intent. Fresh-read queued targets after Spartan Shield lines against projectile-grapple enemies.
- The game awarding Untouchable is more authoritative than immediate Steam cache sync. Record the visible popup and re-sync later if the cache remains stale.

## Follow-Up

The achievement is complete from the game's perspective. Keep `data/achievements_detailed.json` sync-aware rather than hand-forcing the Steam flag unless repeated cache syncs continue to lag, but avoid targeting Untouchable again unless the visible popup is later contradicted.
