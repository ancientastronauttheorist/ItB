# Hook Mech & Grappling Hook — Implementation Spec

Internal names: `WallMech` chassis, `Brute_Grapple` weapon. Bridge currently mislabels weapon as `Vice Fist` due to `weapon_overrides_staged.jsonl` pollution — **bug to fix**. In-game display confirmed as **Grappling Hook** via live hover test 2026-04-23.

## 1. Squad & mech stats

**Squad:** Blitzkrieg (Lightning Mech + Hook Mech + Boulder Mech). Unlockable for 3 coins.

**Hook Mech base stats** (empirically confirmed 2026-04-23 via in-game tooltip):

| Field | Value | Notes |
|---|---|---|
| Class | **Brute** | |
| HP | **3** | |
| Move | **3** | One less than typical 4 (armor tradeoff) |
| Mass | **Massive** (mountain icon confirmed on-screen) | Not affected by single-tile pushes; blocks line-of-sight for non-artillery |
| Flying | No | |
| Stable | No (separate from Massive) | |
| **Armor** | **YES, innate (shield icon confirmed on-screen)** | Weapon damage −1. Push/blocking/fire unaffected. Baked into the chassis. |
| Core cost (weapon start) | 0 (starter) | |

**Key flag for solver:** Hook Mech must instantiate with `armor=True` AND `massive=True`. Both are confirmed on the in-game stat row (mountain + shield icons beside move speed).

## 2. Grappling Hook — execution order

**In-game tooltip (verbatim):** "Use a grapple to pull Mech towards objects, or units to the Mech." — dual-mode pull confirmed.

**Targeting:**
1. Fires **only in cardinal directions** (N/E/S/W).
2. **Line range: unlimited (up to map edge) but requires line of sight** — the first thing in the line is the target. Mountains, buildings, mechs, Vek, rocks, boulders, or Stable objects all block and become the target.
3. Valid first-hit targets: Vek, other mechs, rocks/boulders, Civilian Buildings, Mountains, Stable enemies/objects. Cannot target an empty tile — you target whatever is first in the line.

**Resolution (once target is locked):**
1. **If target is movable** (non-Stable Vek/mech, rock/boulder): target is pulled toward the Hook Mech, stopping on the tile **adjacent to the Hook Mech**. All tiles between are ignored — target glides over water/chasm/fire/mines/time pods without triggering anything.
2. **If target is immovable** (Stable Vek, Mountain, Civilian Building, immovable object): **the Hook Mech pulls itself** toward the target, landing on the tile **adjacent to the target**. Same "transit ignored" rule.
3. **If target is an ally mech**: default pulls the **ally** toward the Hook Mech.

**Damage:** **None.** The weapon deals 0 damage and applies no push/bump rules on pass-through tiles. Route results through a dedicated "pull to adjacent tile" routine — NOT through `apply_push` / `apply_bump_damage`.

**Landing-tile hazards:** standard on-land effects apply at the final tile only: fire/ACID/water/chasm/mine/smoke trigger as if the unit walked into that tile. Flying Vek pulled into water survive; non-flying drown. Frozen Vek can be pulled into water and drown (frozen protects from damage, not terrain death).

**Power cost:** 1 (single power pip on weapon icon).

## 3. Upgrade paths

**Only ONE upgrade slot** (empirically confirmed — no second upgrade visible in tooltip):

| Upgrade | Cost | Effect |
|---|---|---|
| **Shield Ally** | **1 power** (single pip) | When used on an ally mech, the ally gains a **Shield** on arrival. |

No damage upgrade, no range upgrade (range is infinite), no +power upgrade. One of the most compact upgrade trees in the game.

## 4. Edge cases / interactions

- **Stable units cannot be pulled** — the weapon inverts and pulls the Hook Mech instead. This is the defining dual-mode rule.
- **Massive / Large Vek**: pullable as long as not Stable. Size doesn't matter; only Stable does.
- **Frozen units**: pullable. Being dragged into water still drowns them (frozen protects from damage, not from terrain death).
- **Webbed units**: pullable. Pulling breaks the web.
- **Shielded units**: pullable. Shield unaffected (no damage dealt).
- **Mountains**: become anchor → self-pull. Not damaged (0 dmg).
- **Civilian buildings**: anchor → self-pull. Not damaged.
- **Rocks/Boulders** (1-HP placed objects from the Boulder Mech): movable, not Stable — pullable. Core Blitzkrieg synergy (pull a boulder into position to extend Electric Whip chain).
- **Time pods, fire, mines, acid pools on intervening tiles**: ignored during pull transit. Only the landing tile matters.
- **Conveyor belts**: no special interaction documented. Pulled unit lands on the adjacent tile; if that tile is a conveyor, it moves next conveyor tick normally.
- **Teleporter pads** (sim v8): our `apply_teleport_on_land` fires on any move-end. If the landing tile is a pad, swap should trigger. **Needs in-game confirmation.**
- **Spider eggs, Blobs**: pullable (neither is Stable).
- **Psion**: pullable (Psions are non-Stable flyers).
- **Train cars (Armored Train)**: the train is Stable → Hook Mech self-pulls toward it. Cannot pull the train.
- **Destination tile always = adjacent to mech (or adjacent to anchor).** Never a mid-line stop, never bumps into the mech itself.
- **Firing while webbed/frozen/smoke'd**: Webbed = can still attack. Frozen = cannot act. Smoke on Hook Mech's own tile = cannot attack.
- **"Push damage" rules don't apply** — pull is not push, weapon deals no damage.

## 5. Open questions (verify in-game)

1. **Teleporter-pad landing**: does the pulled unit trigger the swap when it lands on a pad adjacent to the mech?
2. **Self-pull landing on a pad** during Stable-target pull.
3. **Is an ally mech targetable without the Shield Ally upgrade?** Community guides imply yes (reposition an ally), but untested.
4. **Pulling emerging (not-yet-spawned) Vek** — not documented.
5. **Stable Vek at distance 1** — does weapon grey out (self-pull no-op) or fail gracefully?
6. **Earth Mover's Filler_Pawn** (friendly NPC): almost certainly pullable, untested.

## 6. Solver/bridge implementation notes

- Bridge bug: `WallMech` currently reports weapon `Vice Fist` (display_name from `weapon_overrides_staged.jsonl` row with `weapon_id: Prime_Shift`). Actual weapon is **Grappling Hook** / `Brute_Grapple`. The staged overrides are pollution from a vision-comparator demo run and should be purged or ignored.
- Route Grappling Hook through a new pull handler. Do NOT reuse push-chain code.
- Transit tiles MUST be ignored (no bump damage on tiles between source and destination).
- Landing tile triggers standard move-end hooks: ACID absorb, fire, drown, teleport swap.
- On Stable target: swap source/destination logic (mech moves, not target).

## Sources

- [Grappling Hook - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Grappling_Hook)
- [Hook Mech - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Hook_Mech)
- [Blitzkrieg - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Blitzkrieg)
- [Passives - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Passives)
- [Attacks - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Attacks)
- [Know your Breach: Guide to the Squads - Steam](https://steamcommunity.com/sharedfiles/filedetails/?id=1615974379)
- [Allow Hook Mech, Grappling Hook decide type of attack - Subset Games Forum](https://subsetgames.com/forum/viewtopic.php?t=32826)
- Live in-game hover test 2026-04-23 (pilot Pierre Waller)
- Local: `data/ref_squads_and_mechs.md`, `data/wiki_raw/Blitzkrieg.json`
