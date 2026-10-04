# Original stock grass emitter Lua dependency

The original DLL now interprets the exact stock `CreateClass`, `Emitter`,
`Emitter_Dust` and `Emitter_tiles_grass` source slices and executes their generated
getters. A separate partial native Dust constructor reaches the actual image-cache
entry with its correct receiver. The later [image-resource acquisition](solver_first_image_resources.md)
closes bounded original decode/copy/resource ownership with real external textures.
Cache registration, image metadata, original biome substitution, loaded Move
dispatch and completed Ground N2 movement remain open.

The [frozen report](../data/solver_first/s1_lua_emitters_20261003.json), raw SHA256
`2c6c8c2b6be3723d71910c3d83fb40a596c9a5a360926db803ba2d38abb9f3b4`, records
**one attempted, one admitted, one matched, zero failed and zero excluded**
stock-script world. Three tables yield 18 expected fields; 15 generated numeric
getters execute with the derived table as `self`. All three absent `Getimage`
fields remain nil: the original base table has no image key when getters are
generated. Integer-valued fields must also equal an integer pushed by the original
DLL, so conversion alone cannot conceal fractional values. Floating emitter
properties and complete particle state are ungraded.

| Table | image_count | max_particles | burst_count | layer | y | image |
| --- | --- | --- | --- | --- | --- | --- |
| Emitter | 1 | 32 | 0 | 2 | 0 | nil |
| Emitter_Dust | 1 | 32 | 15 | 1 | 10 | combat/tiles_grass/dust.png |
| Emitter_tiles_grass | 1 | 32 | 15 | 1 | 10 | combat/tiles_grass/dust.png |

These observations come from actual Lua tables, inheritance and generated Lua
closures, without host getter results or altered `image_count`. The original DLL
performs 306 calls and 465,855 traced instructions, reaches no external imports,
restores an empty stack, and closes with zero live allocations. Its 813 allocator
callbacks retain exact sizes, ownership and per-call slices. The separate positive,
negative and nil registry cases also reproduce with the original seven allocator
seams after the optional per-instance seam parameter change.

## Build, source and admission

Build 13725832 remains pinned by EXE SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`
and actual installed x86 DLL SHA256
`0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14`.
The [earlier VM acquisition](solver_first_lua_vm_registry.md) supplies unchanged
relocation/IAT checks, normal custom allocation and the source-backed empty SEH
chain. The baseline solver is `84c186ae440163056c5c39b9aea9c20e6f49983e`;
simulator version remains 413. This tranche changes offline acquisition tools,
not solver rules or production inputs.

The [new module](../src/observatory/solver_first_lua_emitters.py) loads four complete
source slices in dependency order. Original `global.lua` raw SHA256 is
`96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2`;
its `CreateClass` bytes1776..2208 are used. Original `emitters.lua` raw SHA256 is
`6e599b71006cde4ceb85ff4fa17c8bc88aa0e6173d7d16dff8139fa569f38cd1`;
the base bytes2..418, Dust3565..3822 and grass3866..3951 are used. End offsets are
exclusive. Exact raw-slice hashes are checked, including CRLF bytes. All other
emitter definitions, the full global file and native game bootstrap are outside
this bounded domain. Whole-file attempts remain retained; one exhausted the
existing per-call budget, and earlier ones exposed undeclared boundaries.

Actual `luaopen_base` supplies `pairs` and `setmetatable`; its result count and
stack depth are both2 before restoration. Layer globals are seeded through
actual Lua APIs from independently pinned original registration: Front1, Back2.
Native registration windows `0x280b04`/`0x280b46`, static DWORDs `0x415578`/
`0x41555c`, and consumer `0x50890` establish those integer inputs. Namespace
bootstrap `0x279880` itself is not executed.

The [new instruction map](../data/solver_first/s1_lua_emitter_instruction_admission.json)
freezes 12,329 observed DLL instruction points, widths and raw source-byte hashes,
raw SHA256 `4e5bcc3c410fb3e10c37fee8cbe417b8efe23fc4d5f9521ac4a98d55c7a2f6b3`.
It is separate from the earlier registry-only map. The tool verifies its exact
identity before and after a frozen run, and rejects absent instructions. Source,
runtime, original scripts and binaries are checked for changes. The map is an
observed-path admission, not a function atlas or universal interpreter proof.

Twelve additional source-reviewed allocator returns cover C closure/Proto creation,
parser buffer/array growth and settlement, and scratch-buffer release. Together
with the earlier seven, 19 returns are permitted; this frozen world observes18.
Every callback must immediately follow the exact traced original CALL and obey
the original userdata, pointer, old-size and new-size protocol. The earlier VM
runner retains its seven-return default.

## Narrow supplied storage boundary and grading controls

Original scalar character search at DLL `0x234a8` has terminal DWORD reads at
`0x234e0` and `0x23527`. They may include bytes after a string's final NUL.
The supplied allocator now explicitly zeroes padding in its 16-byte rounded
blocks. Only these two original PCs may read up to three padding bytes, with
read width4, a live same-block allocation, its original string pointer, an
in-request NUL in that word, and the rounded capacity bound. Writes, freed-block
accesses and other overreads retain the exact-size guard. The frozen world has
eight such reads. Eleven exact DLL source windows pin the allocator/library/
character-search dependencies. Default CRT startup, allocation failure and game
loader/FPU setup remain unacquired.

Independent review identified a weakness in the first grader: integer conversion
alone was insufficient. Both its exploratory and frozen receipts remain private
and are labeled conversion-only in the attempt manifest. The strengthened grader
uses actual `lua_equal`; a separate synthetic original-DLL control returns1 and
1.5. Their equality to their integer conversions is respectively1 and0. In this
supplied guest, 1.5 converts to2. A prototype that assumed conversion1 is retained
as failed; the corrected control tests equality without relying on rounding
direction. This is a bounded grading sensitivity check, not gate6 completion.

## Actual native resource frontier

One source-checked exploratory native control calls original EXE `0xbb910` with
the stock Dust name as an inline MSVC string. It reaches `0xbcd90`, `0xbe6f0`,
then the first instruction of image lookup `0xbe8f0` with ECX=`0x8d5660`, after
42,558 traced instructions. The probe deliberately stops before that entry
executes. It supplies no cache/resource return, claims no successful constructor,
and retains partial process ownership. Dust shares the stock grass image and
defaults; this control does not prove actual biome substitution, grass-name
ownership or the original grounded action.

This constructor control is exploratory, with source-byte checks and no frozen
DLL instruction-map admission. It reaches four supplied successful EXE
`HeapAlloc` responses through the previously admitted original allocator seam.
At the stop, 286 Lua and four EXE allocations remain live; no constructor cleanup
or allocation closure is claimed. The zero-external-import/zero-live-allocation
claim above belongs solely to the separately frozen script world.

The remaining source-backed resource requirement is concrete. Lookup tries the
image under `img/`, then `img/advanced/`, then `nullResource.png`. Empty buckets
alone cannot finish: missing fallback recursively re-enters lookup. A genuine
resource wrapper/object is needed; the caller reads its width/height and constructs
the image. Dummy textures, zero image count or supplied final dimensions do not
close the selected Ground N2 scenario.

The [attempt manifest](../data/solver_first/s1_lua_emitter_acquisition_attempts_20261003.json)
retains all 23 mixed world attempts: nine interpreter prototypes, four whole-file
prototypes, four bounded stock worlds, two numeric-control worlds, one partial
native constructor and three earlier-registry compatibility worlds. They are not
aggregated as gameplay fidelity passes. Private source packets and raw receipts
remain outside public Git. Independent review checks source pins, typed values,
call traces, allocator slices, ownership and the map union; full ordered memory
comparison remains unclaimed.

## Solver-facing exit and continuation

Information mode is a source-correct supplied offline oracle, with no fair-player
or held-out admissions. The objective is stock Lua inheritance/getter and normal
ownership closure. **Original completed-action/full-turn admissions, gate and
ledger promotions remain zero.** No search certificate or held-out practical
outcome/latency/memory improvement follows; complete S1 and all seven gates remain
open. The measured call timing describes acquisition, not planner performance.

Continue because two named uncertainties were removed: stock grass definitions
can execute in the genuine VM, and a native stock-image control reaches the exact
resource receiver. Next acquire source-correct image resources, native emitter
completion and loaded Move/dispatcher context, then join original H8-to-G8 action
admission, callbacks and settlement. Enemy/environment/spawn continuation and the
independent full-turn exit test are still required.

```text
python scripts/solver_first_lua_emitters.py --executable <pinned-Breach.exe> --runtime-path <pinned-emulator-package> --output <new-report.json> --private-output-dir <new-private-directory>
```

Outputs are create-only; run serially in a fresh process. The two-million-
instruction/ten-second emulator timeout remains per call. Failed/exhausted paths
remain counted, with supplied boundaries explicit.
