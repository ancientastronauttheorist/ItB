# Whole-program native facts

This directory is the publication boundary for build-keyed whole-program
analysis of `Breach.exe`. Eligible artifacts contain normalized facts only:

- executable and content identity;
- function entry RVAs, body ranges, sizes, and SHA-256 values;
- Ghidra analysis names and their source classification;
- Ghidra-declared direct internal call edges;
- independently decoded, instruction-hash-pinned named-import call relations;
  and
- explicit discovery/omission counts.

Do not commit game binaries, copied executable bytes, disassembly, Ghidra
projects, decompiler output, reconstructed proprietary source, or absolute
installation paths. Keep those under the ignored `.local_decompile/` workbench.

## Export

Import the exact inventoried `Breach.exe` into a local Ghidra project stored
outside Git. Run `scripts/ghidra/ExportItbProgramFacts.java` after auto-analysis
finishes. The script accepts one argument: the destination TSV path.

The raw TSV is local working material. Normalize and verify it against the
exact executable and installation inventory:

```powershell
python -X utf8 scripts/itb_program_facts.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_post_spawn_coordinate_capsule_restore_20260829.json `
  --ghidra-facts .local_decompile/windows_build_13725832/program_facts.tsv `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json
```

Repository output is restricted to a direct child of this directory and is
written atomically. Existing non-atlas artifacts are never replaced.

## Verify

```powershell
python -X utf8 scripts/itb_program_facts.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_post_spawn_coordinate_capsule_restore_20260829.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json
```

A successful verification proves that every recorded body range and hash still
matches that executable. It does not prove Ghidra found every function, chose
every boundary correctly, or that every declared direct flow independently
decodes as a call instruction. It also does not resolve indirect calls or
recover semantics. Focused decoder-backed boundary artifacts remain the route
for promoting particular edges to independent instruction facts.

## Native-to-Lua direct-call census

`scripts/itb_native_lua_direct_calls.py` independently decodes every byte of
every recorded atlas body range with pinned Capstone 5.0.7. It retains only an
exact six-byte x86 `FF 15` call whose absolute operand equals one named
`lua5.1.dll` IAT slot. The normalized artifact is
`windows_build_13725832_31fe35265598_native_lua_direct_call_census.json`.

Build and verify it with:

```powershell
python -X utf8 scripts/itb_native_lua_direct_calls.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json

python -X utf8 scripts/itb_native_lua_direct_calls.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json
```

The current artifact completely decodes all 25,490 atlas ranges and 3,735,718
atlas body bytes into 1,153,814 instructions. It records 4,739 exact direct Lua
IAT calls in 1,787 atlas functions, and every one of the executable's 54 named
Lua imports has at least one retained site. Its pretty-printed file SHA-256 is
`6c4d1068da108d49084e19680caf4232ccf0950be1f595fe9417046a24a308a9`;
the verifier's canonical JSON SHA-256 is
`07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.

Publication is immutable: a byte-identical, deterministically encoded existing
artifact is re-read and reused without writing, while differing evidence or a
concurrently created destination is preserved and rejected rather than
overwritten.

This is complete only over the recorded atlas ranges and accepted `FF 15` call
form. It does not prove that the atlas discovered every function, that a call
executes at runtime, or that a function without a retained site never reaches
Lua indirectly. Direct API consumer, registration-builder, and registered-Lua-
callable relations can overlap. The census therefore publishes the positive
call relation independently; accounting schema 2 can represent overlapping
roles, and its direct-call adapter exact-rebuilds this census against the
installed executable before deriving only positive `lua_api_consumer` support.
It does not infer a negative boundary, C-closure target, registration,
ownership, or another role.

## Native Lua C-closure callback census

`scripts/itb_native_lua_cclosure_callbacks.py` exact-verifies the atlas and
direct-call census, stably rereads the executable, and re-decodes each owning
atlas range with pinned Capstone 5.0.7. It accepts a callback edge only when the
final three contiguous instructions before a direct `lua_pushcclosure` import
call are argument pushes and the callback argument is exact x86 `68 imm32`
whose image VA equals one non-thunk atlas entry.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_callbacks.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json

python -X utf8 scripts/itb_native_lua_cclosure_callbacks.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json
```

The exact build has 15 direct `lua_pushcclosure` sites. Thirteen statically
pass an immediate callback address, resolving to 11 unique non-thunk atlas
entries; two reused targets account for the duplicate edges. The remaining
register- and memory-sourced callback arguments stay explicitly unresolved.
One resolved site passes its own containing function, all 11 callback targets
also directly call at least one Lua import, and three of those targets also
call `lua_pushcclosure`. Those overlaps are mechanical facts, not exclusive
semantic classifications.

The artifact's pretty-printed file SHA-256 is
`9cb573f3cf5831a93c53ee0d673666d853c7e2515eb5d2f24546099f59154579`;
its canonical JSON SHA-256 is
`cb594d7662778b98549bde5f460f1c9d8d0b30f3625d44953c392b8caa50b003`.
It does not claim runtime execution, a Lua-visible name, table identity,
registration lifetime, ownership, semantics, or targets for the two computed
arguments. Identical output is reused without writing, and differing or
concurrently created output is preserved and rejected; verification also
requires the deterministic pretty-printed bytes pinned above.

The accounting adapter for this artifact first rebuilds the exact direct-call
prerequisite, then rebuilds and canonical-compares the complete callback census
against the executable. A pointed callback target can derive only the positive
`cclosure_callback_target` role. It cannot derive runtime execution, a
Lua-visible name or export, table/global storage, lifetime, ownership,
`registered_lua_callable`, or a target for either unresolved computed argument.

## Native Lua C-closure setfield publication census

`scripts/itb_native_lua_cclosure_setfield_publications.py` starts from the
exact direct-call and immediate-callback artifacts and re-verifies both against
the installed executable. It accepts a publication only when a resolved
zero-upvalue callback call is followed contiguously in the same atlas range by
exact x86 encodings for `add esp,12`, `push imm32` key VA, `push -2`, a push of
the same Lua-state register, and a direct `FF 15` call to imported
`lua_setfield`. The key pointer must resolve to a bounded NUL-terminated
printable-ASCII string.

The public PE-free structural validator checks the complete callback
prerequisite, publication/unmatched partition, atlas and direct-setter joins,
reconstructible instruction hashes, aggregates, and summary without opening an
executable. That result is suitable for offline document composition only: it
cannot verify the pointed key bytes or decoded control flow, so it is not a
substitute for the exact `verify` command below.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_setfield_publications.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json

python -X utf8 scripts/itb_native_lua_cclosure_setfield_publications.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json
```

The exact build has three accepted publications at closure/setter RVAs
`0x002e6a8c`/`0x002e6a9d`, `0x002e6af9`/`0x002e6b0a`, and
`0x002e6b66`/`0x002e6b77`. They store distinct callbacks at RVAs
`0x002e6840`, `0x002e6880`, and `0x002e68b0` through the shared caller at
`0x002e6900`; every key is exact text `__gc`. The remaining ten resolved
callback sites stay unmatched rather than inheriting a publication claim.

The artifact's pretty-printed file SHA-256 is
`4f4b8a6bd5dbcdaf116e215d38a0c2784b10d731d02d1300c11796045ea4cd5f`;
its canonical JSON SHA-256 is
`b9a77c1e5e37f251f44b4c1fac304ddbea5251c1cad164e0538c4970417608a6`.
It proves only static storage of the newly created closure into the designated
stack table field. It does not identify that table as a metatable, prove a
global/module export, runtime execution, reachability, persistence, later
contents, another setter form, or either unresolved callback target. Existing
byte-identical output is reused; differing or concurrent output is preserved
and rejected.

The accounting adapter for this artifact rebuilds the exact direct-call and
immediate-callback prerequisites, then exact-verifies and compares the complete
publication census against the executable. A direct
`/registered_targets/N` pointer can derive only the positive
`registered_lua_callable` role for that callback atlas record; a direct
`/builders/N` pointer can derive only the positive `registration_builder` role
for that caller atlas record. Every other pointer, role, and review dimension
is rejected. These roles mean only verified static closure construction and
table-field storage along the accepted fall-through path; they do not imply a
global/module export, table identity, runtime execution, reachability,
ownership, persistence, or a complete registration system.

## Native Lua C-closure direct table-setter publication census

`scripts/itb_native_lua_cclosure_table_setter_publications.py` exact-verifies
the direct-call, immediate-callback, and setfield-publication prerequisites,
then starts exclusively from the setfield artifact's ten unmatched resolved
sites. It accepts only a contiguous same-range form with no cleanup or one
positive, four-byte-aligned `83 c4 imm8` cleanup, a signed immediate table-index
push other than the definitely invalid `0` and `-1` forms, a push of the same
ABI-nonvolatile Lua-state register, and a direct `FF 15` call joined to the same
caller's exact `lua_settable` or `lua_rawset` census record.

The public PE-free structural validator rechecks the complete setfield
structural prerequisite, prior-frontier partition, atlas/callback/direct-setter
joins, signed `push imm8` or `push imm32` and optional-cleanup hashes,
contiguity, aggregates, and summary without opening an executable. It cannot
prove that those instructions or control-flow edges exist in the binary, so it
is not a substitute for exact verification.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_table_setter_publications.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json

python -X utf8 scripts/itb_native_lua_cclosure_table_setter_publications.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json
```

The exact build adds four publication edges: callback/setter RVAs
`0x002e6c01`/`0x002e6c10`, `0x002ea533`/`0x002ea53c`,
`0x002eb086`/`0x002eb092`, and `0x002eb2a5`/`0x002eb2b1`. Three call
`lua_settable`, one calls `lua_rawset`, and their signed table indices are
`-10002` or `-3`. They cover three unique callback targets and four builders;
six prior-frontier sites remain unmatched.

The artifact's pretty-printed file SHA-256 is
`9be33f9d20415f534f56ad591b2ef8a1bcff58726cffce62b869352a8837ee24`;
its canonical JSON SHA-256 is
`a6333ffefd9c9d0ed42bea28b9f5a6e82afff58fc7adb26293c34b5589cb5fa9`.
It proves only immediate static consumption of each new closure as the direct
setter's value. It does not recover the existing stack key, identify the table,
infer a global/module export or Lua-visible name, prove runtime execution or
persistence, cover indirect setter calls, or classify the remaining closure
return and registry-reference dispositions. Existing byte-identical output is
reused; differing or concurrent output is preserved and rejected.

## Native Lua C-closure indirect `lua_settable` publication census

`scripts/itb_native_lua_cclosure_indirect_settable_publications.py`
exact-verifies the complete direct-table-setter prerequisite and starts only
from its six still-unmatched resolved callback sites. It accepts the exact x86
Windows form in which the first callback is followed by a unique
`mov esi,[lua_settable IAT]` stage and each retained callback has a contiguous
positive aligned cleanup, signed valid table-index push, matching
ABI-nonvolatile state push, and `call esi` tail.

The builder decodes the complete caller-entry range into a normalized CFG,
rejects unsupported transfers, recomputes reachability and dominators, and
requires the setter stage to dominate every setter call and every later
callback. It also rejects an ESI write on any stage-to-setter path and audits
alternate atlas entries and declared direct calls into the dominated region.
Calls use the explicit 32-bit Windows cdecl premise that ESI is callee-saved;
unmodeled indirect, exception, or fabricated interior entries remain a stated
atlas-entry assumption. The PE-free validator checks the stored graph and
recomputes all graph proofs, but cannot derive branch or register-write
semantics from instruction hashes.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_indirect_settable_publications.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json

python -X utf8 scripts/itb_native_lua_cclosure_indirect_settable_publications.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json
```

The exact artifact proves callback/setter pairs
`0x002e69f1`/`0x002e6a03`, `0x002e6ba1`/`0x002e6bb0`, and
`0x002e6bc2`/`0x002e6bd1`. Their table indices are `-3`, `-10002`, and
`-10002`; they cover three callback targets, one builder, and one setter stage.
The retained CFG has 260 nodes and 265 edges, with 294 total
stage-to-setter-path nodes. The other three residual sites remain explicit.

The artifact's pretty-printed file SHA-256 is
`cd87cf7e5b6edd3595a11b1d06accb965680baed3d85533fbf4c347ec1153710`;
its canonical JSON SHA-256 is
`50790f8372d90ab11e44a483a39bd575e5af10ceb037c1aa557e4ebf801ac682`.
It proves only conditional static `lua_settable` consumption of each closure,
not a key, destination-table identity, Lua-visible name, runtime execution, or
lifetime. Existing byte-identical output is reused; differing or concurrent
output is preserved and rejected.

## Native Lua C-closure table-key provenance census

`scripts/itb_native_lua_cclosure_table_key_provenance.py` exact-verifies the
full direct and staged-indirect publication chain, then composes all seven
table-setter sites under four finite x86/Lua-stack grammars. Each grammar
requires a bounded non-writable NUL-terminated ASCII literal, exact
`lua_pushstring` provenance, the complete zero- or two-upvalue producer chain,
and preservation of the key below the closure until the retained setter
consumes the key/value pair. Register-indirect calls require caller-entry CFG
dominance of an exact `mov ebx,[IAT]` stage and no EBX writer on any
stage-to-call path under the stated 32-bit Windows cdecl premise.

The guarded register-count form proves that `ESI == 0` only on the path to its
closure call. The deferred two-upvalue `super` form separately proves that its
pre-branch key arguments dominate the publication-arm `call ebx`; its exact
four-instruction register-only interior is pinned so neither an ESP change nor
a native stack-memory store can overwrite those arguments. The alternate arm
writes `nil` under the same global key. The PE-free validator recomputes graph
continuity, fallthrough edges,
dominance, path sets, register-write exclusions, entry audits, producer
adjacency, literal metadata, destinations, and aggregates. Decoded branch and
register-write semantics plus actual literal bytes still require exact rebuild.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_table_key_provenance.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json

python -X utf8 scripts/itb_native_lua_cclosure_table_key_provenance.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json
```

The exact keys are `super` at callback calls `0x002e6c01`, `0x002eb086`, and
`0x002eb2a5`; `__gc` at `0x002e69f1` and `0x002ea533`; `class` at
`0x002e6ba1`; and `property` at `0x002e6bc2`. Five sites use Lua 5.1's
`LUA_GLOBALSINDEX` value `-10002`. The two `-3` sites are independently tied to
fresh unnamed tables created immediately before their key/closure pairs. This
does not name those tables, prove a durable global export, bypass
`__newindex`, establish runtime reachability or persistence, or recover source.

The artifact's pretty-printed file SHA-256 is
`4b37f2206e05b2b881ae6b550df494f908f40eb0beb76b132d3a75364935734e`;
its canonical JSON SHA-256 is
`8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua `super` rebinding chain

`scripts/itb_native_lua_super_rebinding.py` exact-verifies the complete
publication prerequisite chain and selects the three global `super`
publications at callback calls `0x002e6c01`, `0x002eb086`, and `0x002eb2a5`.
It re-reads three bounded literals, verifies four exact atlas bodies, rebuilds
and seals their instruction-level CFGs, joins every profiled direct Lua import
call, proves a complete five-stage / 13-call EBX-and-ESI Lua dispatch partition,
and scans all exact atlas ranges for operands equal to callback VAs
`0x006e6810` or `0x006eb230`. The exact partition contains only closure producers at
`0x002e6bfb`, `0x002eb080`, and `0x002eb29f`; direct calls, comparisons,
memory-operand references, and other direct uses are all empty.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_super_rebinding.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_super_rebinding.json

python -X utf8 scripts/itb_native_lua_super_rebinding.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_super_rebinding.json
```

The normalized chain records one zero-upvalue deprecation/error callback and
two two-upvalue dynamic/self-replacement publications, their alternate and
post-call `nil` cleanup requests, the exact `__init` calls, and normal return
counts. The artifact covers 25,490 ranges, 3,735,718 bytes, and 1,153,814
decoded instructions. It does not prove runtime reachability, guard meanings,
native type or ownership identities, registry validity, successful calls,
metamethod-free persistence, indirect/computed or Lua-side consumers, or
source equivalence.

The artifact's pretty-printed file SHA-256 is
`3b79c82dde6b1bdb7e0b36f9612dc4e5d598b7505ab76411ad6035dccafe34a2`;
its canonical JSON SHA-256 is
`da064ec63caddb0f3c7735caefa8397795455be76a9ead2ffc8ed678a9612ba4`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua C-closure terminal-disposition census

`scripts/itb_native_lua_cclosure_terminal_dispositions.py` independently
starts from the same six-site direct-table-setter residual frontier and accepts
only three complete reviewed sequences. Two variants end immediately in
`eax = 1` plus an enumerated native epilogue; their callers independently join
the callback census as constructed native callbacks, bounding the claim to a
conditional single-Lua-result closure return. The holder variant reconstructs
two same-state registry lookups supplying the closure's upvalues, exact closure
duplication, `luaL_ref(L,-10000)`, same-holder state/reference stores,
`lua_settop(L,-2)`, and return of that holder.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_terminal_dispositions.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json

python -X utf8 scripts/itb_native_lua_cclosure_terminal_dispositions.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json
```

The exact dispositions are a registry-reference holder at callback call
`0x000579a2` and single-result closure returns at `0x002e67fa` and
`0x002ec328`. The artifact leaves exactly the three indirect-setter calls
unmatched, making the two artifacts complementary six-site partitions. Its
pretty-printed file SHA-256 is
`99644fed0a247caa45ee914375d2969377d9913fcf825a56d3fdecc671228731`;
its canonical JSON SHA-256 is
`74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85`.
It does not prove runtime execution, Lua-visible naming or ordinary lookup,
registry-reference lifetime, ownership, or source/behavioral equivalence.
Existing byte-identical output is reused; differing or concurrent output is
preserved and rejected.

## Native function review accounting

The program-facts atlas is also the immutable denominator for a separate
one-to-one review ledger:

- `windows_build_13725832_31fe35265598_native_function_review_registry.json`
  contains only explicit analyst claims and is pinned to the canonical atlas
  hash;
- `windows_build_13725832_31fe35265598_native_function_accounting.json`
  contains exactly one derived record for every atlas function; and
- `scripts/itb_native_function_accounting.py` exact-verifies the executable,
  inventory, atlas, registry, repository evidence, and rebuilt ledger before
  accepting the result.

Build and verify the ledger with:

```powershell
python -X utf8 scripts/itb_native_function_accounting.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --registry data/observatory/programs/windows_build_13725832_31fe35265598_native_function_review_registry.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_function_accounting.json

python -X utf8 scripts/itb_native_function_accounting.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --registry data/observatory/programs/windows_build_13725832_31fe35265598_native_function_review_registry.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_function_accounting.json
```

The initial registry deliberately has no claims. The resulting ledger accounts
for all 25,312 atlas functions at L0, with all 25,312 ownership and subsystem
values still `unknown`, zero L1/L2 promotions, and zero reviewed exclusions.
It separately exposes 685 Ghidra-thunk flags and 26 repeated-body groups
covering 64 functions as review candidates. Those candidates never change a
review field, level, ownership, or exclusion.

The ledger and empty registry now use accounting protocol schema 2. The
registry's raw and canonical SHA-256 values are respectively
`910320d150e7aa6977ce08fcaa9a71823f82f181624efd7a59932a5e7d55910d` and
`1f3226a6939b21126bc7e3514b4ef9784590935c5ef6017b7e025c83b994f3c4`.
The derived ledger's raw and canonical SHA-256 values are respectively
`1e262a170c8bd2c93da168bebdd7f163f9a0b89e0a47ef99c9b807bd19781550` and
`da45da1dc7c53a1898a5707c968f394a1903ed3aca472e69f1c6a522e6337148`.
Existing byte-identical deterministic output is reused; differing, reformatted,
or concurrent output is never overwritten.

Every future registry claim must be in increasing RVA order and pin the
canonical hash of the complete atlas function record. Levels are derived
rather than trusted. L1 requires a reviewed exact boundary, resolved
ownership, reviewed immediate references, and fact/inference evidence; L2
also requires first-party subsystem, purpose, inputs/outputs, and native/Lua
boundary evidence. The boundary is a strict object with state `unknown`,
`none`, or `roles`; positive roles are sorted, independently supported, and
non-exclusive. `none` requires comprehensive whole-field support, while every
positive role requires an exact `native_lua_role` support atom. L0 records
cannot publish resolved L1/L2 fields,
and L1 records cannot publish the L2-only fields, so hypothesis or partial
claims cannot silently alter the authoritative ownership/subsystem partitions.

Promotions use a fail-closed three-layer evidence contract:

1. A dedicated `pe_native_function_review_evidence` record must repeat every
   claimed dimension exactly, carry the complete type-strict atlas build
   identity, and cite every support class required by the derived level.
2. Each cited `pe_native_function_support_evidence` record must bind its class
   to the canonical hash of the exact structured assertion, carry evidence at
   least as strong as the claim, and contain nonempty sorted repository-local
   source references.
3. Every upstream source kind must have a registered kind-specific adapter.
   The adapter validates that artifact's native schema and derives the
   structured assertion; repeating an assertion hash in an unknown JSON kind
   is never accepted.

All paths, file hashes, JSON pointers, identities, and pointed records are
verified on every build. Windows drive-relative paths, NTFS alternate data
streams, reserved names, symlinks, junctions, and changed parent directories
fail closed. Five production adapters accept the direct-Lua-call, immediate
C-closure callback, setfield-publication, direct-table-setter-publication, and
staged-indirect-settable-publication censuses. Each rebuilds and
canonical-compares its complete evidence chain against the exact executable
once per source artifact per accounting build. They derive only
`lua_api_consumer`, `cclosure_callback_target`, and the role-specific
`registered_lua_callable` or `registration_builder` facts described above.
None can support `none`, an unlisted role, or any ownership, reference,
semantic, boundary, or exclusion dimension. The empty registry therefore still
leaves every function at L0.

Only third-party and compiler-runtime exclusions have a generic v2 shape, and
they still require typed ownership plus exclusion support through an
allowlisted adapter. `unreachable`, `duplicate_thunk`, and `data_only` fail
closed until specialized proofs exist: complete roots/reachability for the
first, a retained canonical target plus proven transfer/equivalence for the
second, and an independently proven boundary misclassification for the third.

The ledger does not turn Ghidra names, namespaces, address neighborhoods,
sizes, thunk flags, repeated bodies, or call records into ownership or
semantics. Its 25,312-record denominator is still the Ghidra-discovered atlas,
whose bodies cover 92.99% of file-backed executable-section bytes. The
remaining 281,434 executable bytes, 18,477 computed or unmapped call targets,
indirect flow, focused regions that do not exactly match atlas bodies, and all
L3 behavior remain explicit future work.
