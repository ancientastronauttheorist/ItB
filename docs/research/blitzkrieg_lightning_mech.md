# Lightning Mech & Electric Whip — Implementation Reference

Internal names: `ElectricMech` chassis, `Chain Whip` weapon (bridge display). Wiki calls the weapon "Electric Whip"; the achievement text uses "Chain Whip" — same weapon.

## 1. Mech Base Stats

| Stat | Base | Notes |
|---|---|---|
| Class | **Prime** | Blitzkrieg squad |
| HP | **3** (wiki cached data) | Our `pawn_stats.py` has `move_speed=3, massive=True` — **verify in-game** |
| Move | **3** | |
| Mass | **Normal** (not Massive) | Affected by pushes. Codebase has `massive=True` — likely wrong, verify. |
| Armor | None | |
| Flying | No | |
| Stable | No | |
| Innate passives | None | |
| Core cost to add Whip to a different mech | **1 Core** (if not the starting weapon) | |

## 2. Electric Whip — Execution Order

**Targeting pattern:** Fires at one of the 4 cardinally adjacent tiles (up/down/left/right). Range = 1 tile. Target tile must contain a "conductor" (Vek, mech, building, rock, Train — anything that conducts; see §4).

**Chain algorithm (step-by-step, as the sim should implement it):**

1. Pick the target adjacent tile. Lightning Mech's own tile is NOT the first node; the first damaged node is the adjacent target.
2. From the current node, find all cardinally-adjacent tiles that contain a conductor and haven't been visited. Pursue them one at a time — the chain visits every reachable conductor exactly once (flood fill over the conductor graph). The chain never visits a tile twice.
3. At each visited node, apply **weapon damage = 2** (base). Damage is applied per-node individually, so each node rolls against its own Armor / ACID / Shield.
4. Damage application order appears to be BFS/DFS from the origin, deterministic, though not documented — **open question** (§5).
5. The chain only stops when no unvisited adjacent conductor exists. No HP-drop, no distance cap, no branching limit. (20+ hits demonstrated by community — Subset Games forum thread "Massive 20-tile electric whip".)

**Does NOT push.** No knockback, no direction. Pure damage.

**No status applied.** Does not set fire, ACID, smoke, frozen, or shield.

**Self-damage:** the mech is the source, not a node. But if the chain loops back to an adjacent tile containing the Lightning Mech via a path through buildings/other conductors, it WILL damage itself. **Verify in-game.**

## 3. Upgrade Paths

| Upgrade | Cost | Effect |
|---|---|---|
| Building Chain (A) | **1 Core** | Chain passes through Grid Buildings without damaging them. They still conduct. Strongly recommended first. |
| +1 Damage (B) | **3 Cores** — **verify exact split (power bar vs cores)** | All nodes in chain take +1 damage (base becomes 3). |

Both upgrades stack. Fully upgraded: 3 damage per node, buildings pass through freely.

## 4. Edge Cases & Interactions

**Conductors (chain passes through and damages each):**
- Vek (all types, including flying like Hornet)
- Player mechs (chain damages them — signature footgun; confirmed community reports of self-hits setting allies on fire)
- Grid Buildings (damaged for 1 without upgrade; passed through damage-free with Building Chain upgrade)
- Boulder Mech's deployed rock (conducts)
- Mountains — **open question**, not cited; community suggests "common earth elements" conduct
- Supply Train — conducts AND can be destroyed, despite being friendly
- Psion Tyrant, Spider Leader, etc. — treated as normal Vek nodes
- Eggs (Spider/Blobber) — **open question**

**Non-conductors (chain stops / does not cross):**
- Empty ground, water, chasm, lava, ice — empty terrain does not conduct
- Smoke tiles with no unit
- Rubble (destroyed mountain) — **open question**

**Status interactions at a node:**
- **Armor:** −1 damage (floor 0), standard weapon damage rule
- **ACID:** ×2 damage, standard
- **Shield:** absorbs one damage instance. Chain still conducts through the shielded unit. **Bug:** hitting a shielded/frozen Supply Train removes the shield/frozen AND deals damage (same instance breaks shield and also damages — community-reported bug)
- **Frozen:** takes 0 damage but unfreezes. Chain should still conduct through. **Verify** whether a unit that dies/unfreezes mid-chain still conducts for downstream nodes.
- **Smoke on the target tile:** smoke on Lightning Mech = can't attack. Smoke on a chain-node tile does NOT stop conduction.
- **Webbed:** webbed Vek are still units and still conduct; damage unwebs per standard rules.
- **Emerging Vek:** do NOT occupy the tile this turn. Chain does not pass through them.

**Known bugs:**
- Shielded/Frozen Supply Train: shield/frozen consumed AND train damaged in same hit.

## 5. Open Questions (Verify In-Game)

1. **Exact base HP and Move** — wiki says 3/3; our `pawn_stats.py` has massive=True which contradicts.
2. **+1 Damage upgrade exact power cost** — verify the power-bar + core split.
3. **Chain damage ORDER** — when two branches exist, which resolves first? Expectation: chain computed on snapshot, damage applied simultaneously. **Verify.**
4. **Can chain revisit a tile?** Answer appears to be NO; each tile visited once. Confirm.
5. **Mountains / rubble / spawning-eggs as conductors** — not explicitly documented; test in-game.
6. **Does chain hit Lightning Mech itself if path wraps around?** Strongly implied yes but not explicitly confirmed.
7. **Blobs, WebbEggs, Filler_Pawn, Train_Pawn** — all likely conduct but need per-pawn confirmation.

## Sources

- [Electric Whip - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Electric_Whip)
- [Lightning Mech - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Lightning_Mech)
- [Blitzkrieg - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Blitzkrieg)
- [Massive 20-tile electric whip - Subset Games Forum](https://subsetgames.com/forum/viewtopic.php?t=32916)
- [Suggestion Lightning Mech - Electric Whip - Subset Games Forum](https://subsetgames.com/forum/viewtopic.php?t=32844)
- [Advice for the Lightning Squad needed - Steam Discussions](https://steamcommunity.com/app/590380/discussions/0/1697167803858868133/)
- [Tips, Tricks and Infos - Steam Guide](https://steamcommunity.com/sharedfiles/filedetails/?id=1386007005)
- [Supply Train - Into the Breach Wiki](https://intothebreach.fandom.com/wiki/Supply_Train)
- Local cache: `data/wiki_raw/Blitzkrieg.json`
