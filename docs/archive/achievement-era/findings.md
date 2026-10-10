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

After restart, the original module-relative pause field
`Breach.exe+0x4bc7e8` stayed readable but stopped tracking the visible menu
state. A fresh Python-scancode Esc probe found many process-local toggle
candidates, with the cleanest validated heap hit:

```text
0x0000000008b3a5dc width=4 values 1->0->1->0->1->0->1
```

This confirms the pause toggle bytes are useful live hints, not durable
addresses.

## Pause State From Timer Motion

A better general pause/open detector is the visible timer's motion:

```text
pause menu open   => visible timer string stays fixed
pause menu closed => visible timer string advances
```

Visual screenshots confirmed this on the island map:

```text
menu open:   3h 6m 48s -> 3h 6m 48s over 5 seconds
menu closed: 3:06:49  -> 3:06:54 over 5 seconds
```

Memory context string reads matched the same behavior:

```text
closed context: 3:08:38 -> 3:08:41
open context:   3:09:13 -> 3:09:13
```

The f32 timer scan found stable timer copies in this restart state, even while
the visible timer was ticking, so it is not the right detector for pause/menu
state here. Use the visible timer string context instead:

```text
python scripts/itb_timer_memory_probe.py watch-context --pid <pid> --sample-seconds 5
```

Evidence was written locally under:

```text
run/restart_validation_20260608/timer_visual_pause_check/
run/restart_validation_20260608/timer_visual_closed_check/
run/restart_validation_20260608/visible_timer_context_closed_5s.json
run/restart_validation_20260608/visible_timer_context_open_5s.json
run/restart_validation_20260608/visible_timer_context_watch_open.json
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

## Post-Restart Validation

After a full game restart on 2026-06-08, `Breach.exe` relaunched as PID `9852`
with the same module base observed earlier:

```text
Breach.exe base = 0x610000
```

The pause-menu module-relative offset still resolved to the same absolute
address:

```text
Breach.exe+0x4bc7e8 = 0x0000000000acc7e8
read value = 0
```

The value was readable after restart, but automated Esc injection failed during
this pass (`SendInput` returned `0`), so the open/closed parity was not
revalidated after restart.

The old timer pointer path did not survive the restart:

```text
Breach.exe+0x7d9c read pointer 0x117df33b
pointer + 0xef49 = 0x117ee284
timer read = failed
```

This confirms the earlier caveat: the timer pointer path is a useful one-run
finding, not a permanent address chain. A fresh `f32` rescan near the visible
`1:52:xx` timer range found stable candidates while the game appeared to be in
a pause/menu layer, but did not re-establish a moving live timer address.

Fresh memory still contained serialized `GameData` blocks after restart. The
strongest current-looking block during this pass had:

```text
network = 7
networkMax = 7
overflow = 13
difficulty = 0
seed = 26377
mechs = {"LeapMech", "UnstableTank", "NanoMech"}
pilot0 = Kazaaakpleth level=1 skill1=8 skill2=0
pilot1 = Tatiana Perez level=2 skill1=1 skill2=3
pilot2 = Zera level=1 skill1=7 skill2=11
```

This reinforces the stale-copy warning: old Detritus/Bethany blocks were still
present in memory, but were not the current run context. It also reinforces
level-gating: Zera had `level=1` with a stored `skill2=11`, so `skill2` must
remain inactive until `level >= 2`; Kazaaakpleth had `level=1 skill2=0`, showing
that a zero-valued locked slot can appear even though `0` is also the real
`+2 Mech HP` ID once a slot is unlocked.

Evidence was written locally under:

```text
run/restart_validation_20260608/restart_memory_validation.json
run/restart_validation_20260608/pause_restart_toggle_validation.json
run/restart_validation_20260608/timer_restart_f32_rescan.json
```

## Hardened Timer Resolver Direction

The one-run pointer path should be replaced with a resolver workflow:

```text
1. Collect context timer hints from serialized UI/save text in memory.
2. Ignore wall-clock timestamp strings such as `Mon Jun 08 22:38:17 2026 UTC`.
3. Prefer repeated visible timer strings over the largest timer-like string.
4. Scan readable process memory for plausible f32 seconds values near the hint.
5. Re-read candidates after a delay.
6. Prefer candidates whose delta matches wall time when the game is unpaused.
7. While paused, accept only lower-confidence stable candidates close to the
   expected visible timer.
8. Generate module-relative pointer roots only as process-specific hints.
```

A reusable Windows probe now exists at:

```text
scripts/itb_timer_memory_probe.py
```

Example command:

```text
python scripts/itb_timer_memory_probe.py scan --pid <pid> --sample-seconds 1.5 --output run/restart_validation_20260608/timer_hardened_scan.json
```

The first hardened pass on restarted PID `9852` still used a max-context
heuristic. It inferred `2:07:08` and found stable f32 candidates near that value
while the game was paused/menu-layered. The best paused candidate was:

```text
address = 0x0000000017506d20
before = 7627.814941
after = 7627.814941
status = paused_expected_match
game_timer = 2:07:07
```

It also found a new pointer-root hint for this process:

```text
Breach.exe+0x418210 -> pointer 0x174fe149, field_offset 0x8bd7
```

This is not considered durable until it is revalidated after another restart.

After another restart, `Breach.exe` relaunched as PID `29936`, still with module
base `0x610000`. The earlier direct timer pointer and the PID `9852`
pointer-root hint did not provide a durable address. A larger context sample
also revealed false positive clock strings such as:

```text
Mon Jun 08 22:38:17 2026 UTC
```

The probe was hardened to skip those timestamp contexts, collect more context
hits by default, and select the repeated visible timer mode instead of the
largest timer-like value. On PID `29936`, the hardened pass selected
`2:00:13` from four repeated visible timer strings and found paused/stable f32
candidates near that value:

```text
address = 0x0000000018285a64
before = 7212.357910
after = 7212.357910
status = paused_expected_match
game_timer = 2:00:12
```

Its best pointer-root hint was different again:

```text
Breach.exe+0xa4cbc -> pointer 0x1827e900, field_offset 0x7164
```

The durable piece is the resolver strategy: rediscover the f32 timer each run,
then optionally cache and revalidate pointer-root hints only inside the same
process. A moving candidate sampled while unpaused is still required before any
single address should be called the live in-game timer.

Evidence was written locally under:

```text
run/restart_validation_20260608/timer_hardened_scan_auto.json
run/restart_validation_20260608/timer_hardened_scan_restart2_mode.json
run/restart_validation_20260608/timer_hardened_scan_restart2_hardened.json
run/restart_validation_20260608/timer_probe_console_summary_smoke.json
```
