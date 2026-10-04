# Original Lua VM and game registry dependency closure

Follow-up: [stock grass Lua acquisition](solver_first_stock_lua_emitters.md) now
executes exact source slices and generated getters in this genuine VM. A separate
partial native Dust control reaches the image-cache entry; real resources,
loaded Move dispatch and completed Ground movement remain open. The report below
retains its earlier registry-only domain and historical source pins.

The movement acquisition previously stopped at original EXE `0x6c3ec`, an
unresolved `lua_pushvalue` import before the grounded pawn coordinate write.
A genuine guest VM now executes that import and the selected game registry/value
wrappers without supplied Lua return values. Stock emitter definitions, image
resources, loaded Move skills and complete N2 movement remain unacquired.

The [frozen report](../data/solver_first/s1_lua_vm_registry_20261003.json), SHA256
`35b77c45741b4bc24272b5689141b330060fec8868647db006af8ac2bd3d1b08`,
records **three attempted, three admitted, three matched, zero failed and zero
excluded** supplied-world cases. Positive 37 and negative -7 return number type3
and their signed values; the missing field returns nil type0, conversion0 and
reference `0xffffffff`. The type check distinguishes nil from numeric zero.
Every case restores stack depth0 and closes with no live allocations. These are
bounded VM/wrapper comparisons, not gameplay action admissions.

Build 13725832 remains pinned by EXE SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The installed x86 `lua5.1.dll` SHA256 is
`0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14`.
Solver baseline is `84c186ae440163056c5c39b9aea9c20e6f49983e`; simulator pins
remain 413. No solver semantics or production inputs change. Information mode
is synthetic offline oracle storage, with zero fair-input/held-out admissions.
The objective is typed observations and normal allocator ownership closure;
no search certificate or practical outcome/latency/memory comparison follows.

## Address space, source and supplied boundaries

The [module](../src/observatory/solver_first_lua_vm.py) maps the exact DLL at
`0x21000000`, separate from Board `0x10000000`, heap `0x20000000` and stack
`0x30000000`. Its preferred base overlaps Board. Its 5,595 HIGHLOW fixups have
no duplicate/out-of-image targets, canonical SHA256
`390ef02c9abc5de67ea94d6e4353d84cb06c4b37328b9ad295dbab359e0bc752`.
All 54 EXE Lua IAT entries bind to actual DLL exports. Original DLL instructions
are checked against relocation-derived source bytes; code pages are read/execute.
EXE instructions retain frozen owner-atlas admission. Unknown reached imports
fail closed; the accepted cases reach no external imports.

The [instruction map](../data/solver_first/s1_lua_vm_instruction_admission.json)
freezes 2,392 observed DLL points, widths and raw-byte hashes, raw SHA256
`195c5c3858a5cbd63c7e4e6d0ca3acf567e8a8f6c69de57bd9a2c04889cf2b22`.
The runner checks its pinned hash, rejects absent/different entries, and checks
unchanged bytes afterward. Source, original binaries and runtime identities are
also checked before/after acquisition. This is an observed-path map, not a DLL
function atlas, universal Lua proof or semantic coverage percentage. Expansion
requires new source-checked exploratory evidence and an explicitly refrozen map.

Original `lua_newstate` at DLL RVA `0x19ca0` takes allocator/userdata by x86
cdecl, returns its actual owned state and executes original protected
initialization. The supplied normal allocator validates userdata, exact old
size and liveness; moving reallocation preserves `min(old,new)` bytes before
retiring the old allocation. Free returns null. Seven caller returns are
admitted: `0x1206f`, `0x19892`, `0x198cd`, `0x19ae5`, `0x19b00`, `0x19b4a`,
`0x19cb8`. Each must immediately follow the last exact traced original CALL.
The callback returns by cdecl; the original caller cleans its four arguments.
It supplies allocation service, never Lua/game logic.

Original CRT `0x47c60`, 123 bytes, SHA256
`c24e8aaed4de58907df11c265260404d68e8b92e1a6373d11e2db8e73238e755`,
reads FS:[0] and explicitly handles `0xffffffff` as an empty SEH chain. This
source-backed sentinel is supplied. Default `luaL_newstate`, CRT/DLL loader
startup, panic, allocation failure and unwind branches remain outside the domain.

## Joined wrappers and retained audit

EXE `0x6c3e0`, 68 bytes, SHA256
`ed059e361991083be61a45e0ca5d238c252bc53c06df3ac8df9a9646dcad81ef`,
takes ECX=8-byte output, EDX=actual state and RET0; it creates a registry handle
to the actual global table. EXE `0x4e800`, 390 bytes, SHA256
`701d733376fa7687810c969eb708950d34eba50c92dd2f407eb07dd80d742f94`,
takes ECX=32-byte object plus a 24-byte inline MSVC string, RET24, and reads the
actual VM pointer supplied at VA `0x896048`. Its original lookup/reference
machinery returns the typed `ProbeValue` value. Those synthetic globals are
created by actual DLL APIs; source-correct emitter tables are not loaded.

Every marker definition, DLL API and game wrapper call retains its complete
private ordered instruction trace, imports and allocator slice immediately.
Each case also retains its whole 107-row allocator history, including five
null/zero callbacks. Independent source/receipt review verifies that call slices
concatenate exactly to that history, pointer/old-size transitions are valid and
all histories balance to zero. Counts, trace hashes, stack checks, source pins
and public/private typed observations reconcile; observed DLL entries union to
the frozen map. No full ordered read/write or whole-native-state proof is claimed.

The [attempt manifest](../data/solver_first/s1_lua_vm_acquisition_attempts_20261003.json)
keeps prior attempts and hashes. One failed prototype crossed an empty callback
mapping during translation; the explicit external allocator RET now bounds it.
A second used FS:[0]=0 and reached the nonempty-chain dereference at `0x47caf`;
the source-backed sentinel fixes that supplied-environment error. A successful
VM/API/close prototype and subsequent joined prototype remain separate; the
latter omitted some saved traces. The reusable acquisition retains all calls
and typed controls. Diagnostics are not discarded or promoted to gameplay proof.

## Continuation and reproduction

Continue: the reached Lua import and generic registry/value operations now have
same-address-space original execution evidence. Next load source-correct Ground
emitter definitions and actual image/resource objects, then establish loaded
Move/dispatcher context and joined N2 H8-to-G8 admission, callbacks and settlement.
Flying/busy changes, `image_count=0`, dummy textures or host coordinate writes
cannot establish the existing grounded scenario. Full enemy/environment/spawn
continuity, independent gameplay corpus, fair inputs and held-out practical
evaluation remain required. Complete S1 and all seven gates remain open;
original completed-action/full-turn admissions remain zero.

```text
python scripts/solver_first_lua_vm.py --executable <pinned-Breach.exe> --runtime-path <pinned-emulator-package> --output <new-report.json> --private-output-dir <new-private-directory>
```

Outputs are create-only. Run serially in a fresh process. Each call has a
two-million-instruction/ten-second limit; failures and exhausted/unadmitted
paths remain counted. Proprietary binaries and raw traces remain private;
public Git contains only tools, normalized facts and identities.
