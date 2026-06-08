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

