# September 11 decompilation continuation

This pass continues on the explicitly authorized `codex/full-decompile` branch
from `d6f5bbd8`. New work stopped at the requested September 12, 2026
02:00 America/Chicago deadline (07:00 UTC), followed by this closing handoff.
Full-game decompilation remains unfinished; accounting promotions are zero.

## Durable checkpoints

| Commit | Result | Native cases or model work |
|---|---|---:|
| `87f327eb` | [One red-uncle recoloring](native_tree_recolor_return.md) | 320 |
| `ff4376f2` | [Independent canonical insertion](native_tree_balancing_semantics.md) | 7,855 model insertions |
| `eae34b50` | [Canonical attachment and balancing](native_tree_balancing_conformance.md) | 1,329 |
| `23adf59c` | [Empty hint normal return](native_tree_empty_hint.md) | 1,600 |
| `85a5ec50` | [Strict minimum/end hints](native_tree_extreme_hint.md) | 3,200 |
| `5a22e303` | [Interior lower-bound hints](native_tree_interior_hint.md) | 2,016 |
| `55f45596` | Caller-local result slots | 8,145 default replays unchanged |
| `20cdba23` | [Whole insertion normal returns](native_tree_insert_return.md) | 942 |
| `538133de` | [Native successor](native_lua_tree_successor_conformance.md) | 972 |
| `f00af324` | [Independent class tree-copy model](native_lua_class_tree_semantics.md) | 16 model tests |
| `0769a544` | Actual class caller stack and return address | Original return receipt unchanged |
| `1b8427e9` | Actual insertion node/key/result mappings | Four default receipts unchanged; four relocated native cases |
| `a7f78bb6` | [Native class tree-copy prefix](native_lua_class_tree_conformance.md) | 192 |
| `9786e698` | [Class transfer, spare append and return](native_lua_class_spare_return_conformance.md) | 1,152 |
| `b7764915` | Actual first-vector allocation/growth caller mapping | Three original receipts unchanged |
| `13e8fa14` | [Class transfer, first vector allocation and return](native_lua_class_empty_vector_return_conformance.md) | 576 |
| `3a992d4c` | Actual successful old-buffer deallocation mapping | Four original receipts unchanged; 77 mapping tests |
| `f14df926` | [Class return with an internal spare-capacity argument](native_lua_class_internal_spare_return_conformance.md) | 1,344 |
| `95a23843` | [Class old-vector growth, copying, free and return](native_lua_class_old_vector_return_conformance.md) | 1,536 |
| `e2bda2f5` | Actual old-buffer pointer/base mappings | 130 mapping tests; two default receipts unchanged |
| `b510541f` | [Internal argument reallocation and return](native_lua_class_internal_growth_return_conformance.md) | 1,152 |
| `733652aa` | [Whole insertion with variable byte keys](native_tree_byte_key_insert_return_conformance.md) | 2,826 |
| `df78e650` | Checked class byte-key mapping | 22 tests; default prefix receipt unchanged |
| `e9987e04` | [Standalone class operation model](native_lua_class_operation_semantics.md) | 44 model/projection tests |
| `f826d7ee` | [Whole class return with variable byte keys](native_lua_class_byte_key_return_conformance.md) | 1,152 |
| `e76813cf` | [Independent filtered Lua transfer requests](native_lua_table_transfer_semantics.md) | 14 model tests |
| `2f127b33` | [Native marker and partial-EAX return](native_lua_class_marker_conformance.md) | 576 |
| `d08f9bac` | [Native filtered Lua table transfer](native_lua_table_transfer_conformance.md) | 320 |
| `0075be08` | [Exact returned-callback integration dossier](native_lua_class_callback_integration.md) | 269-byte owner; actual frames and boundaries |
| `d5922fff` | Checked actual-caller marker/table mappings | 25 relocated native cases; both default receipts unchanged |

The canonical native balancing domain covers repeated recoloring, both mirrored
triangles and lines, root and nonroot rotations, and all four non-nil subtree
transfers. Six loaded generic sites are unreachable under the canonical input
invariants; the balancing document identifies them precisely.

Hint compositions use actual native comparison, predecessor, attachment,
balancing and normal return machinery. Interior hints perform two comparisons,
up to seven ordered predecessor-slot writes, and both attachment alternatives.
The enclosing insertion owner uses a result at `O-8`, above hint entry
`H=O-40`; the explicit output interface preserves that caller-owned storage and
keeps the independent result check effective even on a stack page.

## Evidence and validation

Exact executable: Windows build 13725832, SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Private execution uses Capstone 5.0.7 and Unicorn 2.1.4. Public artifacts contain
normalized instruction witnesses, synthetic cases and digests, without native
binaries, raw disassembly or bulk pseudocode. Individual documents provide
canonical/encoded receipt hashes, source pins, scopes and reproduction commands.

Important semantic tranches received independent review. Focused validations:
recolor 348 passed; canonical model 37 passed; balancing 36 passed; empty hints
41 passed across the main run and corrected test rerun; extreme hints 31 passed;
interior hints 31 passed; caller-local output 62 passed. These are overlapping
focused runs, not a unique combined-suite total. Exact replay uses subprocesses.

The last completed tree/vector regression passed **2,430 tests with 74 gated
skips** in 445.31 seconds across 62 files. It covers checkpoints through
`f826d7ee`; the newer Lua helpers have separate focused validations below.
Each native checkpoint also includes a separate exact executable subprocess
rebuild. Later focused results include old-vector return 26; old-buffer mappings
130; internal growth 27; byte-key insertion 24; class key mapping 22; logical
class operation 44. All 32 class byte-key tests were verified across an initial
run plus one corrected empty-source-page test rerun; exact native reproduction
passed in the initial run. These overlapping focused results are not a unique
combined-suite total. The later table request model passed 14 tests; all 16
marker tests were verified across the initial run and a corrected mutation-test
rerun, with exact native reproduction in the initial run. Native table transfer
passed 16 tests in 12.19 seconds including exact byte-identical CLI reproduction.
The actual-caller marker mapping passed 31 tests in 9.51 seconds, including nine
relocated native cases and the default 576-case rebuild; the original marker's
15 non-CLI tests also passed in 6.36 seconds. The table proof and mapping suites
passed 46 tests in 15.15 seconds, including 16 relocated native cases and the
default 320-case rebuild. These later focused runs overlap and are separate
from the 2,430-test broad total.
The final semantic checkpoint `d5922fff` was pushed and its local/tracking
identities matched. The closing documentation commit is pushed separately;
its final remote verification is reported in the task. Pre-existing user
changes remain outside all checkpoint commits.
The protected-work hash snapshot is private at
`.local_decompile/sep11/protected_work.json`.

For a focused replay of the final mapping tranche on this Windows checkout:

```powershell
$env:PYTHONPATH='.local_decompile/fill_runtime;.'
$env:ITB_EXACT_EXE='B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
python -m pytest -q tests/test_itb_native_lua_class_marker_caller_mapping.py tests/test_itb_native_lua_table_transfer_conformance.py tests/test_itb_native_lua_table_transfer_caller_mapping.py
```

The private dependency directory supplies the pinned native engines. Keep
native execution inside the tests' subprocesses and run pytest serially. The
expanded broad-suite file list and completed log are private at
`.local_decompile/sep11/regression_tests.txt` and `regression.log`. These are
reproduction aids, not additional public receipts or a claim that gated cases
ran in the broad suite.

## Current continuation and remaining scope

The class operation now has finite normal-return proofs for disjoint canonical
trees and external/internal spare appends, first null-vector allocation, small
old-vector growth and internal argument relocation. Variable byte-key families
include empty/prefix strings, high-bit boundaries and long common prefixes.
The logical model explicitly rejects growth beyond three live records and
signed-byte-span edge domains rather than extrapolating from the small corpus.

Completed neighboring Lua helpers cover native marker return and two-value
filtered transfer with explicitly supplied normal Lua API responses. The Lua VM,
installed DLL, metamethod behavior and heap effects remain separate boundaries.

The next target is the [enclosing callback at 0x002ec110](native_lua_class_callback_integration.md).
Its local record lives on the caller stack with a zero first word; the two table
helpers run at different native depths and logical prefix lengths. Both Lua
helpers now have checked caller mapping interfaces and native cases at the real
continuations, including table prefix one. The dossier records the exact calls,
returns, retained arguments and remaining class-record relocation requirements.
Start with the external-spare class family, record address S+28 for class entry
S, and independently preserve its caller region at and above S+8 before joining the
entire callback. Do not mistake the mapping tests for a continuous callback run.

Unaligned/partial internal records, larger live-vector copying, allocation/free
failure, assertion failure, actual heap implementation, exception delivery,
arbitrary string/tree domains and broader enclosing Lua callers remain open.
Synthetic FS state proves normal registration restoration, not Windows exception
delivery. No proof here alone establishes complete game behavior or whole-program
coverage.

Protected-file verification at 07:00 UTC: all 11 files in the private start-of-run
hash snapshot were unchanged. Other pre-existing work remains unstaged. The
continuation automation was changed to PAUSED at the stop, confirmed by the
automation tool and its persisted configuration. No test or native build remains
active. Full-game decompilation is still unfinished.
