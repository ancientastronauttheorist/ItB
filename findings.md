# Memory Probe Findings

Date: 2026-06-08
Host: Windows, Steam Into the Breach process `Breach.exe`

## Pause Menu Detection

The Windows memory probe can detect the pause menu after switching Esc input
from virtual-key events to hardware scancode events.

Validated pause-menu candidates from `validate-cycles`:

```text
0x0000000000acc7e8 width=4 values 1->0->1->0->1->0->1
0x0000000000c800fc width=4 values 1->0->1->0->1->0->1
```

For this run:

- `1` means the pause menu is closed.
- `0` means the pause menu is open.
- `0x0000000000acc7e8` was inside `Breach.exe` at module-relative offset
  `0x4bc7e8` during the validation run.

Evidence was written locally under:

```text
run/pause_probe_windows_scancode_20260608_validate/pause_probe_validated_cycles.json
```

## Mission Select Memory Strings

A read-only string scan found mission/island state serialized in process memory.
The strongest current-state-looking hit included:

```text
["region6"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Excavation Site", },
["region7"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ... },
["iBattleRegion"] = 5
```

`Old Town` was also present in memory, but most hits were static Archive
region-name tables or older serialized island snapshots. This means raw string
presence is useful but needs freshness/ranking before it can reliably identify
current selectable mission regions.

Evidence was written locally under:

```text
run/mission_select_memory_strings_20260608.json
```

## In-Game Timer

The visible in-game timer can be read from memory as a live `f32` seconds
value. A direct heap address was found first:

```text
0x00000000117ee284 as f32 seconds
```

Validation against screenshots:

```text
Screenshot before: 1:03:33 = 3813s
Memory before:     3813.152s

Screenshot after:  1:03:38 = 3818s
Memory after:      3818.370s

Memory delta:      5.219s
Wall elapsed:      5.224s
```

A one-hop module-relative pointer path was also found:

```text
Breach.exe+0x7d9c -> +0xef49
```

Validation of the pointer path:

```text
Breach.exe base: 0x610000
root address:    0x00617d9c
pointer value:   0x117df34b
timer address:   0x117ee294
value before:    4267.548s
value after:     4271.841s
elapsed wall:    4.232s
```

The path value matched the direct timer value exactly during validation. Because
this was validated in one live process, it should be rechecked after a full game
restart before treating the path as permanent.

Evidence was written locally under:

```text
run/timer_memory_probe_20260608/timer_f32_candidate_validation.json
run/timer_memory_probe_20260608/timer_pointer_path_validation.json
```

## Grid Power and Grid Defense

Process memory contains serialized `GameData` copies with the live grid fields.
The strongest current-state hit during this run was:

```text
0x0000000003fc9d8c
network = 5
networkMax = 7
overflow = 0
difficulty = 0
ach_squad = "Detritus_A"
```

`network` and `networkMax` are the current and maximum Power Grid values.
`overflow` is the permanent overpowered Grid Defense bonus counter.

Other matching copies were found at:

```text
0x0000000011576fec
0x00000000167c936c
```

Some older serialized copies also remain in memory, so consumers should rank
matches by freshness/current seed/current squad/current section instead of
trusting the first grid-shaped hit.

The visible Grid Defense value is computed from difficulty base defense,
`overflow`, and active pilot skills. For the current screen, the user observed
`18%` Grid Defense. A later pilot panel check on the Lightning Mech showed
Bethany Jones had:

```text
Max Level
Starting Shield
+3 Grid DEF
+1 Mech Move
```

The matching memory block had Bethany as `level=2 skill1=2 skill2=1`, so the
correct level-up perk interpretation for this case is `skill1=2` = `+3 Grid
DEF` and `skill2=1` = `+1 Mech Move`.

The memory-backed Grid Defense formula was:

```text
base defense on Easy/Normal/Hard = 15
overflow = 0
Bethany active skill1 = 2 = +3 Grid DEF
Bethany active skill2 = 1 = +1 Mech Move, no grid effect
Penny level 0 saved skills ignored
Mateo level 0 saved skills ignored

15 + 0 + 3 = 18
```

Screenshot capture through Computer Use failed during this check with:

```text
SetIsBorderRequired failed: No such interface supported (0x80004002)
```

Evidence was written locally under:

```text
run/grid_memory_probe_20260608/grid_network_string_scan.json
run/grid_memory_probe_20260608/grid_values_reread.json
```

## Pilot Skill Level Gating

Current pilot blocks in process memory showed:

```text
0x0000000003fca1f7 Bethany Jones level=2 skill1=2 skill2=1
0x0000000003fca2fc Penny         level=0 skill1=3 skill2=1
0x0000000003fca3d3 Mateo Volkov  level=0 skill1=3 skill2=1
```

The important rule is that saved skill slots can exist before they are active:

```text
skill1 is active only when level >= 1
skill2 is active only when level >= 2
```

Level 0 pilots may already have future `skill1` and `skill2` values in memory,
but those stored future skills do not affect current stats.

Evidence was written locally under:

```text
run/grid_memory_probe_20260608/grid_current_pilot_scan.json
```

## Pilot Skill IDs

Local installed game text, wiki/internal-order notes, and the current live
Bethany UI observation agree on this level-up perk ID map:

```text
0  +2 Mech HP        piloted mech HP +2
1  +1 Mech Move      piloted mech move +1
2  +3 Grid DEF       grid defense +3 percentage points
3  +1 Mech Reactor   piloted mech reactor +1
4  Opener            Boost and +2 Move on the first turn
5  Finisher/Closer   Boost and +2 Move on the last turn
6  Popular Hero      pilot sells for 4 reputation
7  Thick Skin        immune to A.C.I.D. and Fire
8  Skilled           +1 Move and +2 Mech HP
9  Invulnerable      pilot does not die when the mech is defeated
10 Adrenaline        +1 Move per Vek killed in the current battle
11 Masochist/Pain    +2 Move when not at full health
12 Technician/Regen  repair 1 HP at the start of each turn
13 Conservative      limited-use weapon bonus
```

Local source anchors:

```text
B:\SteamLibrary\steamapps\common\Into the Breach\scripts\text.lua
B:\SteamLibrary\steamapps\common\Into the Breach\scripts\localization\Tooltips.csv
B:\SteamLibrary\steamapps\common\Into the Breach\scripts\localization\Tooltips_ae.csv
B:\SteamLibrary\steamapps\common\Into the Breach\scripts\pilots.lua
```

Online anchors:

```text
https://intothebreach.fandom.com/wiki/Skills
https://www.reddit.com/r/IntoTheBreach/comments/wy4n6w/picking_pilot_skills/
```

The installed scripts expose names, descriptions, unique pilot skills, and
skill blacklists. They do not appear to expose a direct numeric ID table for
level-up perks, so the numeric mapping is treated as wiki/internal-order
knowledge cross-checked against the local text and the live Bethany/Grid Defense
result.

Important parser caveat: `0` is both the internal ID for `+2 Mech HP` and the
default-looking value seen in locked or absent slots. Consumers must gate slots
by pilot level first:

```text
level >= 1 => skill1 is active, even when skill1 == 0
level >= 2 => skill2 is active, even when skill2 == 0
level 0    => saved skill1/skill2 values are future choices and inactive
```
