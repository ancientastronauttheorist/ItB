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

## Native Lua `__gc` metatable consumers

`scripts/itb_native_lua_cclosure_gc_metatable_consumers.py` composes the exact
closure-publication prerequisites into five `__gc` publication/consumer
records. Four records cover the null-gated bootstrap userdata/metatable chains
and their `lua_settable(LUA_REGISTRYINDEX)` stores. The fifth covers the raw
`luabind.function` registry cache and its sole decoded direct consumer.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_cclosure_gc_metatable_consumers.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_gc_metatable_consumers.json

python -X utf8 scripts/itb_native_lua_cclosure_gc_metatable_consumers.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_gc_metatable_consumers.json
```

The artifact seals eight core bodies / 1,924 bytes, 667 CFG nodes / 670 edges,
61 direct and 58 staged Lua calls, 66 semantic instruction points, 49
contiguous adjacency proofs, five callback identities, four initializer-
subtree edges, and the complete seven-reference scan for its central targets.
Its exact five-of-ten `__gc` partition is limited to normalized immediate-
C-closure setter publications; other native grammars, including staged rawset
writes in helpers `0x002eb990` and `0x002eba60`, remain outside that count.
Runtime dispatch, destructor behavior, ownership, allocation origin, lifetime,
and unmodeled indirect entries are not claimed.

The artifact's pretty-printed file SHA-256 is
`9d4435d6d67b5ab46b6391585fecb1e09dc3be926dac66aa04fa1b4c39e34fc7`;
its canonical JSON SHA-256 is
`4c2e4be756ef611f234d7d78418daf3fe16be2928ef440bb67b5a586df3bef8a`.
Existing byte-identical output is reused; symlink, reparse-point, non-regular,
differing, unrelated, or concurrently changed output is preserved and rejected.

## Native Lua registry-holder local-use/release census

`scripts/itb_native_lua_registry_holder_local_use_release.py` composes the
canonical program-facts, direct-Lua-call, and terminal-disposition artifacts
with the exact Windows executable. It replays the 107-byte producer at
`0x00057970`, then seals every immediate or absolute-memory atlas reference to
that producer and the bounded local holder-use/release grammar in each source.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_registry_holder_local_use_release.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_registry_holder_local_use_release_census.json

python -X utf8 scripts/itb_native_lua_registry_holder_local_use_release.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_registry_holder_local_use_release_census.json
```

The artifact contains one producer and exactly 46 callers in two address
clusters. Together they seal 47 bodies / 11,469 bytes, 4,177 CFG nodes / 4,360
edges, 98 direct Lua calls, and 276 register-indirect calls. Each 247-byte
caller retains 37 semantic points, all three staged-ESI API paths, an all-eight
`call r32` audit, its sole modeled entry, and the EBX window from constructor
return capture through the instruction before EBX is reused for a separate
temporary. That bounded window contains only the capture and the `[ebx+4]`
reference read; no holder-state equality is inferred for the later raw lookup.
The original local state/reference pair is conditionally passed to
`luaL_unref`, while the later second stack pair remains explicitly
unattributed.

The exhaustive scan decodes 25,312 atlas functions, 25,490 ranges, 3,735,718
bytes, and 1,153,814 instructions. Its complete 46-reference producer
partition consists only of the matching immediate five-byte `E8` calls, each
joined to its Ghidra-declared edge. Runtime execution, reference validity,
ownership, field clearing, destruction, indirect or un-atlased callers, and a
complete lifetime remain unclaimed.

The artifact's pretty-printed file SHA-256 is
`139ed2444ee9b8824a4913638214db8c68a7899340a5e53b955c4a367c576755`;
its canonical JSON SHA-256 is
`395603c2a163925fc202a5a35791200859313872c242fe5901e4de8c05ab892f`.
Existing byte-identical output is reused; symlink, reparse-point, non-regular,
differing, unrelated, or concurrently changed output is preserved and
rejected.

## Native Lua `property` factory chain

`scripts/itb_native_lua_property_factory_chain.py` exact-verifies the complete
publication and terminal-disposition prerequisite chain, then joins the unique
global `property` publication at callback call `0x002e6bc2` to factory callback
`0x002e67b0`, its single-result two-upvalue closure targeting `0x002eaa50`,
and the same returned callback's separate registry-holder producer at
`0x000579a2`. The alternate producer is explicitly not labeled factory-origin.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_property_factory_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_factory_chain.json

python -X utf8 scripts/itb_native_lua_property_factory_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_factory_chain.json
```

The artifact re-reads three bounded literals, keeping the colon-bearing
returned-callback message hash-only; seals 125 callback bytes in two full CFGs
with 45 nodes and 46 edges; joins all seven direct Lua import calls; and proves
that neither body contains any of the eight x86 `call r32` encodings. Its
two-target whole-atlas scan covers 25,490 ranges, 3,735,718 bytes, and
1,153,814 instructions. The exact five-reference partition is three closure producers
at `0x0005799c`, `0x002e67f4`, and `0x002e6bbc`, plus identity comparisons at
`0x002ea047` and `0x002ea172`; direct calls, absolute-memory references, and
other direct uses are empty.

Consumer branch behavior, descriptor/metamethod placement, upvalue callability,
callback-origin inference, registry validity, a durable global export, runtime
reachability, indirect/Lua-side consumers, and source-level property semantics
remain unclaimed. The artifact's pretty-printed file SHA-256 is
`5859871e2a61522a7f80a3b92f12ed705ad906b770c1fa2247877f16a066fa4b`;
its canonical JSON SHA-256 is
`aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua `property` consumer chain

`scripts/itb_native_lua_property_consumer_chain.py` recursively exact-verifies
the normalized property-factory artifact, then seals the getter-like consumer
at `0x002ea110`, setter-like consumer at `0x002e9fd0`, and initializer at
`0x002ea2d0`. Build and verify it with the same prerequisite paths shown above,
plus the factory artifact:

```powershell
python -X utf8 scripts/itb_native_lua_property_consumer_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --property-factory-chain data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_factory_chain.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_consumer_chain.json

python -X utf8 scripts/itb_native_lua_property_consumer_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --property-factory-chain data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_factory_chain.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_consumer_chain.json
```

The artifact seals 706 bytes in three complete CFGs with 279 nodes and 286
edges, joins all 34 direct Lua-import calls, and proves five staged imports cover
all 23 EBX, ESI, and EDI calls while separately checking every x86 `call r32`
encoding. It records the two tag-match call arms, setter read-only arm, and
three distinct zero-upvalue placements: a getter under numeric raw key `1.0`, a
separate getter under `__index`, and the setter under `__newindex`.

Its three-target whole-atlas scan covers 25,490 ranges, 3,735,718 bytes, and
1,153,814 instructions. The exact six-reference partition contains three
closure producers, two getter-identity comparisons, and one direct initializer
call; absolute-memory and other direct uses are empty. Mismatch-branch
semantics, dynamic attachment or invocation, callback-origin inference,
callability, runtime reachability, and source-level property equivalence remain
unclaimed.

The artifact's pretty-printed file SHA-256 is
`1cc4b84cebb5b5fab17b059f8050bca477c6d27742efb267b7a29851d87d88a5`;
its canonical JSON SHA-256 is
`2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua `class` factory chain

`scripts/itb_native_lua_class_factory_chain.py` exact-verifies the complete
publication and terminal-disposition prerequisite chain, then joins the unique
global `class` publication at callback call `0x002e6ba1` to factory callback
`0x002ec220` and its single-result returned closure at `0x002ec328` targeting
`0x002ec110`. It re-reads four bounded literals, verifies and seals both exact
callback bodies and their full instruction-level CFGs, joins every profiled
direct Lua import call, proves a complete three-stage / nine-call EDI, ESI, and
EBX Lua-dispatch partition, and retains six exact direct native edges to four
unique helper targets without assigning helper semantics.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_class_factory_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json

python -X utf8 scripts/itb_native_lua_class_factory_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --callbacks data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json `
  --setfield-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json `
  --direct-table-setter-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_setter_publications.json `
  --indirect-settable-publications data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json `
  --table-key-provenance data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json
```

The two-target whole-atlas operand scan covers 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Its only references are the two immediate closure
producers at `0x002e6b9b` and `0x002ec322`; direct calls, comparisons,
memory-operand references, and other direct uses are empty. The artifact pins
one publication, one returned closure, four literals, 565 callback bytes, 199
CFG nodes, and 206 CFG edges. It does not claim a raw or durable export,
metamethod-free storage, runtime reachability, registry validity, helper
behavior, native type/ownership names, indirect or Lua-side consumers, or
source-level class/derivation equivalence.

The artifact's pretty-printed file SHA-256 is
`2fe1f0032564594d3b9be01e976e1c24c4ccfa60036e14432e44fc1503c6b6ae`;
its canonical JSON SHA-256 is
`824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua `class` returned-callback helper chain

`scripts/itb_native_lua_class_return_helper_chain.py` canonical-pins the exact
`class` factory artifact, seals the three helper bodies reached by its returned
callback, and scans every atlas operand for the complete helper-entry reference
frontier. The bounded slice deliberately excludes the factory-side initializer
`0x002eacf0` and retains alternate caller `0x002e7970` as reference-only.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_class_return_helper_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-factory data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_return_helper_chain.json

python -X utf8 scripts/itb_native_lua_class_return_helper_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-factory data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_return_helper_chain.json
```

The artifact has analysis kind `pe_native_lua_class_return_helper_chain`. It
seals helpers `0x002eb140`, `0x002eb560`, and `0x002ec050`: three bodies / 501
bytes, three CFGs / 190 nodes / 201 edges, all 14 direct Lua calls, and all six
EBX/EDI staged calls under a complete eight-encoding `call r32` audit. Three
bounded literals are exact-reread from non-writable `.rdata`:
`__luabind_classrep`, `__init`, and `__finalize`.

The normalized claims remain deliberately local. The first helper retains only
the argument-field guard, traversal, per-node calls, alias/external copy arms,
and eight-byte append grammar. The marker helper records a metamethod-capable
metatable-field truth test with normal stack restoration. The two-value helper
records `lua_next` iteration, skips the two exact keys, and requests
metamethod-capable assignment into the first entry value. It does not assign
class, inheritance, container, ownership, lifetime, or callee semantics.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly six helper references survive, all immediate
near calls: five from returned callback `0x002ec110` and the alternate
`0x002e7970 -> 0x002eb140` call at `0x002e7ce0`. Comparisons,
absolute-memory operands, and other direct-address uses are empty. Runtime
invocation, valid input values, successful calls, dynamic or Lua-side
consumers, and initializer behavior are outside this helper artifact. The
adjacent initializer artifact below closes that distinct static body.

The artifact's pretty-printed file SHA-256 is
`aab9847af280484af26885f6390f586726fd173466b76d5f0b2cda104f836bec`;
its canonical JSON SHA-256 is
`33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native Lua `class` initializer chain

`scripts/itb_native_lua_class_initializer_chain.py` canonical-pins the exact
`class` factory artifact, rejoins its conditional initializer call, seals the
single factory-side initializer body, and scans every atlas operand for its
complete entry-reference frontier. The normalized evidence remains
offset-only: it assigns no source class, vtable, ownership, or lifetime names.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_class_initializer_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-factory data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json

python -X utf8 scripts/itb_native_lua_class_initializer_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-factory data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json
```

The artifact has analysis kind `pe_native_lua_class_initializer_chain`. It
seals initializer `0x002eacf0`: 612 bytes, one 185-node / 191-edge CFG, all 20
direct Lua calls, and all six EBX-staged calls under a complete eight-encoding
`call r32` audit. It exact-reads `__luabind_classes`,
`__luabind_cast_graph`, and `__luabind_class_id_map` from non-writable
`.rdata`, and retains the calls to `0x0007c600` and the assertion helper as two
opaque native-edge facts.

The offset grammar includes the fixed initial writes, three state/reference
pairs and their conditional prior unrefs, the registry-key lookups, the
`__luabind_classes` `+0x0c` guard and `+0x10` raw-reference read, and the later
stores through `+0x44`. `lua_gettable` is not treated as raw, and registry
values, reference validity, assertion termination, runtime success, ownership,
lifetime, and source equivalence remain unproved.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one initializer reference survives: the
factory's immediate `0x002ec302 -> 0x002eacf0` call. Comparisons,
absolute-memory operands, and other direct-address uses are empty.

The artifact's pretty-printed file SHA-256 is
`8bd9b4ad928675f0cb2e708ec6695daf1618dfbd3eff1324f8bfa7147bc9a4b2`;
its canonical JSON SHA-256 is
`799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9`.
Existing byte-identical output is reused; differing, unrelated, or concurrently
changed output is preserved and rejected.

## Native self-linked-record helper chain

`scripts/itb_native_self_linked_record_helper_chain.py` canonical-pins the
exact class-initializer artifact, rejoins its formerly opaque
`0x002ead8b -> 0x0007c600` edge, seals that helper's exact body and CFG, and
scans every atlas operand for its complete entry-reference frontier. The
normalized evidence records byte- and offset-level behavior only.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_self_linked_record_helper_chain.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-initializer data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_self_linked_record_helper_chain.json

python -X utf8 scripts/itb_native_self_linked_record_helper_chain.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-initializer data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_self_linked_record_helper_chain.json
```

The artifact has analysis kind `pe_native_self_linked_record_helper_chain`.
It seals helper `0x0007c600`: 41 bytes and one 16-node / 18-edge CFG. The body
passes immediate `24` to its sole direct native-call target, whose program-facts
name is analysis-labeled `operator_new` at `0x003574db`; retains the returned
EAX through exact stores at `+0`, `+4`, and `+8` under the distinct EAX,
EAX-plus-four, and EAX-plus-eight tests; writes word `0x0101` at `+0x0c`; and
returns EAX. The latter two tests are not ordinary returned-EAX null guards.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly nine helper references survive, all
immediate direct calls from nine distinct owners. The artifact also seals nine
bounded caller grammar windows: adjacent `+0` / `+4` zero stores, the helper
call, and a returned-EAX store after zero to two intervening instructions.
Those owner bodies and CFGs remain reference-only.

The artifact's pretty-printed file SHA-256 is
`50786d8c2b84702c3d0c246c90ee715afa7c7ef544ddf3fc8afb66e487a01d3c`;
its canonical JSON SHA-256 is
`994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb`.
Existing byte-identical output is reused; differing, unrelated, concurrently
changed, or same-inode-mutated existing output is preserved and rejected. A
new destination that fails final content validation is removed. Runtime
reachability, normal return, allocation success, pointer validity, source
type, tree/container/sentinel identity, ownership, lifetime, computed
references, indirect calls, and Lua-side consumers remain unproved.

## Native assertion-helper static boundary

`scripts/itb_native_assertion_helper_static_boundary.py` canonical-pins the
exact class-initializer artifact, rejoins its remaining
`0x002eae76 -> 0x00379cc2` edge, seals the exact target body and CFG, and scans
every atlas operand for the complete target-entry reference frontier. The
normalized artifact records byte-, control-flow-, and pointer-section syntax;
it does not promote Ghidra's analysis labels into source or runtime semantics.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-initializer data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json

python -X utf8 scripts/itb_native_assertion_helper_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --class-initializer data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json
```

The artifact has analysis kind
`pe_native_assertion_helper_static_boundary`. It seals helper `0x00379cc2`:
72 bytes, all 29 exact instruction points, and one 29-node / 30-edge CFG. Its
four outgoing direct calls remain opaque native edges. The body contains no
direct Lua call, staged Lua dispatch, `call r32`, or retained literal, and its
trailing `int3` does not prove termination.

The six-instruction initializer window retains the sentinel comparison and
branch, immediate `96`, two pointers proven only to lie in non-writable
`.rdata`, and the direct helper call. The all-operand scan covers 25,312
functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly
881 helper references survive from 660 owners, all five-byte immediate `E8`
calls; comparison, absolute-memory, and other direct-address partitions are
empty.

The artifact's pretty-printed file SHA-256 is
`7fd6879c031ba4e665024789f3cbf9308c49ea3c649ca300b441ada38d9ade5e`;
its canonical JSON SHA-256 is
`beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4`.
Publication validates a stable locked destination at one explicit point in
time: Windows denies write/delete sharing and holds a mandatory full-range
lock; POSIX uses an advisory exclusive lock for cooperating writers. It does
not claim perpetual immutability after release. Runtime reachability,
invocation order or frequency, argument validity, CRT identity or ownership,
dialog/display behavior, normal return, abort, termination, source
equivalence, computed or indirect references, un-atlased code, and Lua-side
references remain unproved.

## Native operator-new static boundary

`scripts/itb_native_operator_new_static_boundary.py` canonical-pins the exact
self-linked-record helper artifact, rejoins its
`0x0007c602 -> 0x003574db` edge, seals the analysis-labeled target body and
CFG, and scans every atlas operand for the complete target-entry reference
frontier. The predecessor edge is validated simultaneously against the pinned
helper evidence and the independently rebuilt reference record. The artifact
records byte and control-flow syntax only; `operator_new` remains an analysis
label rather than a promoted source or runtime semantic.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_operator_new_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --self-linked-record-helper-chain data/observatory/programs/windows_build_13725832_31fe35265598_native_self_linked_record_helper_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json

python -X utf8 scripts/itb_native_operator_new_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --self-linked-record-helper-chain data/observatory/programs/windows_build_13725832_31fe35265598_native_self_linked_record_helper_chain.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json
```

The artifact has analysis kind `pe_native_operator_new_static_boundary`. It
seals target `0x003574db`: 51 bytes, all 20 exact instruction points, and one
20-node / 22-edge CFG. Its four outgoing direct calls remain opaque native
edges. Direct and staged Lua calls, `call r32`, and retained literals are
empty.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 1,233 target references survive from 1,050
owners: 1,232 five-byte immediate `E8` calls and one declared `E9` reference
at `0x00357874`. Comparison and absolute-memory partitions are empty.

The artifact's pretty-printed file SHA-256 is
`08cfc38143f47c4b4f737e4638f82495b5bfd22341626a1ee3d7ea66df2005e9`;
its canonical JSON SHA-256 is
`d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f`.
Publication validates a stable locked destination at one explicit point in
time: Windows denies write/delete sharing and holds a mandatory full-range
lock; POSIX uses an advisory exclusive lock for cooperating writers. It does
not claim perpetual immutability after release. If final validation of a
published destination fails, that destination is preserved for inspection;
only the private temporary is cleaned. Allocation semantics, ABI, success,
ownership, lifetime, size meaning, runtime reachability, normal return, source
identity, opaque-callee behavior, computed or indirect references, data
references, un-atlased code, and Lua-side references remain unproved.

## Native callnewh static boundary

`scripts/itb_native_callnewh_static_boundary.py` canonical-pins the exact
operator-new boundary, rejoins its `0x003574e3 -> 0x0038bbc4` edge, seals the
analysis-labeled target body and CFG, and scans every atlas operand for the
complete target-entry reference frontier. The predecessor edge is validated
both from the pinned artifact and from the independently rebuilt PE reference
record. The `__callnewh` spelling remains analysis metadata only.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_callnewh_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_callnewh_static_boundary.json

python -X utf8 scripts/itb_native_callnewh_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_callnewh_static_boundary.json
```

The artifact has analysis kind `pe_native_callnewh_static_boundary`. It seals
target `0x0038bbc4`: 68 bytes, all 30 exact instruction points, and one
30-node / 31-edge CFG. It retains two opaque direct native edges at
`0x0038bbd5 -> 0x0038bc08` and `0x0038bbff -> 0x003574ca`; an unresolved
absolute-memory call through non-writable `.rdata` at `0x0038bbe5`; an
unresolved `call ESI` at `0x0038bbeb`; and an absolute read from writable
`.data` at `0x0038bbca`. The complete eight-register call audit contains the
one ESI site. Direct and staged Lua calls and retained literals are empty.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly four target references survive from four
owners, all five-byte immediate `E8` calls; comparison, absolute-memory, and
other-address reference partitions are empty. The artifact's pretty-printed
file SHA-256 is
`5b1651f4b17b3d6531b71a19c828ab4700cebb19f444c5db6d694e5534793449`;
its canonical JSON SHA-256 is
`27f7495174094b3d6dca6acd6e9975a4dfa7d349f3bf974d40c3f5acd0b4eb45`.

Publication validates one locked point-in-time snapshot. Windows denies
write/delete sharing and takes a mandatory full-range lock; POSIX uses an
advisory exclusive lock for cooperating writers. Inherited output-root and
locking failures are normalized into the artifact's own error domain, and a
published destination that fails final validation is preserved for inspection.
Allocation, new-handler, ABI, success, ownership, lifetime, size meaning,
callee identity or behavior, normal return, runtime reachability,
dynamic-target resolution, source equivalence, data consumers, un-atlased
code, and Lua-side references remain unproved.

## Native query-new-handler static boundary

`scripts/itb_native_query_new_handler_static_boundary.py` canonical-pins the
exact callnewh boundary, rejoins its sole
`0x0038bbd5 -> 0x0038bc08` edge, seals the analysis-labeled target body and
CFG, and scans every atlas operand for the complete target-entry reference
frontier. The predecessor is validated both from the pinned callnewh evidence
and from the independently rebuilt PE reference record. The
`__query_new_handler` spelling remains analysis metadata only.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_new_handler_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --callnewh-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_callnewh_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json

python -X utf8 scripts/itb_native_query_new_handler_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --callnewh-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_callnewh_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_new_handler_static_boundary`. It seals target `0x0038bc08`:
70 bytes, all 19 exact instruction points, and one 19-node / 18-edge CFG. Four
outgoing direct native calls remain opaque. Its three absolute-address syntax
records distinguish one non-writable file-backed `.rdata` pointer, one
writable file-backed `.data` read, and one writable virtual-only `.data` read.
No pointer content or runtime value is decoded.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one target reference survives from one
owner, a five-byte immediate `E8` call; comparison, absolute-memory, and
other-address reference partitions are empty. Direct and staged Lua calls,
the complete eight-register call audit, and retained literals are empty.

The artifact's pretty-printed file SHA-256 is
`a0e4913c271166ee3ebd0e429f86161d47f9108c5201d2de6d4219bae8b85263`;
its canonical JSON SHA-256 is
`742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705`.
Publication validates one locked point-in-time snapshot, normalizes inherited
publisher errors into this artifact's domain, and preserves a published
destination after failed final validation. Handler/allocation behavior, SEH,
lock, security, pointer contents, ABI, success, ownership, lifetime, source
identity, callee behavior, normal return, runtime reachability, computed or
indirect references, data consumers, un-atlased code, and Lua-side references
remain unproved.

## Native query-handler first-callee static boundary

`scripts/itb_native_query_handler_first_callee_static_boundary.py`
canonical-pins the query-handler evidence, rejoins exact predecessor
`0x0038bc0f -> 0x003584b0`, seals the complete relationship-defined target
body and CFG, and scans every atlas operand for the target-entry frontier. The
target's `__SEH_prolog4` spelling is retained only as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_static_boundary`. It seals target
`0x003584b0`: 70 bytes, all 21 exact instruction points, and one 21-node /
20-edge CFG. The body has no direct native edge, direct or staged Lua call,
`call r32`, or retained literal.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 66 target-entry references survive from
66 owners, all five-byte immediate `E8` calls. Comparison, other-address, and
absolute-memory entry-reference partitions are empty, and structural
verification requires the explicit 66-owner partition.

Five exact syntax records remain opaque. The immediate at `0x003584b0` names
VA `0x007729b0` / RVA `0x003729b0` in file-backed non-writable `.text`; its
contents and target identity are not assigned here. The memory push at
`0x003584b5` and destination write at `0x003584ee` use segment-relative
`FS:[0]` operands and are not represented as PE absolute addresses. The
absolute read at `0x003584cd` names VA `0x00893f28` / RVA `0x00493f28` in
file-backed writable `.data`. The final instruction at `0x003584f4` has exact
two-byte BND-prefixed-return syntax. Executable validation derives each
operand class, access direction, segment or absolute value, section span, and
instruction identity through Capstone without assigning runtime meaning.

The artifact's pretty-printed file SHA-256 is
`f4d43affe98441996f1d10086438c93136b181665c2039b9b1ae18beb618e6b4`;
its canonical JSON SHA-256 is
`b08dc12a2f4951817e4e7c24dbdfc4afec03550c2828d7d14c1d757404517d73`.
Publication validates one locked point-in-time snapshot, requires the exact
owner partition during structural verification, normalizes inherited errors,
blocks writer contention, preserves existing published evidence after failed
final validation, and removes a failed private publication. The analysis
label does not prove purpose, SEH, prolog, exception, stack, register,
security-cookie, ABI, argument meaning, state mutation, success, normal
return, runtime reachability, source identity, or operand contents. Dynamic,
computed, indirect, data, un-atlased, and Lua-side references remain unproved.

## Native query-handler first-callee pointer-target static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_static_boundary.py`
canonical-pins the first-callee and query-handler evidence, rejoins the exact
absolute-immediate pointer syntax at `0x003584b0`, seals the complete pointed-to
body and CFG, and scans every atlas immediate and absolute-memory operand for
the target frontier. The target's `__except_handler4` spelling is retained only
as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --first-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_static_boundary.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --first-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_static_boundary.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_static_boundary`. The
predecessor is the exact five-byte `PUSH imm32` at `0x003584b0`, naming VA
`0x007729b0` / RVA `0x003729b0` in file-backed non-writable `.text`; it is an
opaque address use, not a declared direct call. The artifact seals target
`0x003729b0`: 358 bytes, all 120 exact instruction points, and one 120-node /
130-edge CFG.

Eleven exact native direct edges remain opaque:
`0x003729db -> 0x00372970`, `0x003729e4 -> 0x00007e70`,
`0x00372a2a -> 0x00378b3e`, `0x00372a53 -> 0x0039d580`,
`0x00372a6c -> 0x003581b3`, `0x00372a80 -> 0x00378b6e`,
`0x00372ac9 -> 0x00378b87`, `0x00372ad2 -> 0x00372970`,
`0x00372af1 -> 0x00378b87`, `0x00372b00 -> 0x00372970`, and
`0x00372b10 -> 0x00378b55`. Direct and staged Lua calls and retained literals
are empty. The complete eight-register audit contains only `call ESI` at
`0x00372a71`. Although `0x00372a5f` has exact ESI-load syntax, the intervening
direct call at `0x00372a6c` prevents this static receipt from assigning the
later call's target identity.

Six non-control PE operand records remain opaque. `0x003729cd` reads VA
`0x00893f28` / RVA `0x00493f28` in writable `.data`. `0x00372a45` reads VA
`0x007f2750` / RVA `0x003f2750` in non-writable `.rdata`; `0x00372a4e` carries
the same address as an immediate, and `0x00372a5f` loads from it into ESI.
The immediates at `0x00372ab9` and `0x00372ae4` name the `.data` address. All
six operands are file-backed, and their contents and runtime meanings remain
unassigned.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly three target references survive, from
owners `0x003584b0`, `0x0039d580`, and `0x0039d770`. Each has identical
five-byte immediate-push syntax and is classified as `other_address`; direct
call, comparison, and absolute-memory target-reference partitions are empty.
Structural verification requires the exact three-owner partition.

The artifact's pretty-printed file SHA-256 is
`0fc22f514989853df44f285396b4f59683ee94f703fcc355b566ad6518783c4d`;
its canonical JSON SHA-256 is
`41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing published evidence
after failed final validation, and removes a failed private publication. The
analysis label and decoded syntax do not prove purpose, exception or handler
behavior, stack or security semantics, ABI, argument meaning, register values,
target identity, state mutation, success, normal return, runtime reachability,
dynamic or computed references, data consumers, un-atlased code, or Lua-side
references.

## Native query pointer-target adjacent-callee cluster static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.py`
canonical-pins the first-callee pointer-target artifact, rejoins five exact
parent edges, and seals four distinct atlas bodies whose ranges happen to be
contiguous. The shared span is a layout receipt only and carries no claim of
semantic kinship or execution order.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary`.
Its layout-only span is `0x00378b3e..0x00378b9e` exclusive: 96 bytes with
SHA-256
`90bbfc64c1432f6b635812d241f996137a7e02d88381c66e66955102f1f9d48d`.
It contains four separate bodies:

- `0x00378b3e`: 23 bytes, 16 instructions, 16-node / 15-edge CFG.
- `0x00378b55`: 25 bytes, 11 instructions, 11-node / 10-edge CFG.
- `0x00378b6e`: 25 bytes, 15 instructions, 15-node / 14-edge CFG.
- `0x00378b87`: 23 bytes, 9 instructions, 9-node / 8-edge CFG.

The five parent joins are `0x00372a2a -> 0x00378b3e`,
`0x00372b10 -> 0x00378b55`, `0x00372a80 -> 0x00378b6e`, and
`0x00372ac9 -> 0x00378b87` plus `0x00372af1 -> 0x00378b87`. Each copied
parent record is cross-checked against an independently rebuilt whole-atlas
row, including instruction, source/owner and target atlas identities, and the
normalized Ghidra edge.

The cluster's complete declared outgoing-edge partition is
`0x00378b5d -> 0x00378a15`, `0x00378b7d -> 0x0039cb98`, and
`0x00378b92 -> 0x00378a40`. The complete eight-register call audit contains
only `call ECX` at `0x00378b4e`. The final `jmp ESI` at `0x00378b6c` is
retained as opaque indirect-control syntax. Although `0x00378b57` has exact
`MOV ESI,ECX` bytes, the intervening direct call at `0x00378b5d` prevents this
static receipt from assigning provenance or target identity to the jump.

The exact PE-address operand universe is four operand-zero immediates, all in
file-backed non-writable `.text`, with no absolute-memory operand. Three are
the outgoing `E8` targets. The remaining `PUSH` at `0x00378b77` names VA
`0x00778b82` / RVA `0x00378b82`, an address inside the same body; its purpose
remains opaque. Direct and staged Lua evidence is empty, but this does not
prove that the dynamic ECX target is non-Lua.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly five target references survive, all
five-byte immediate `E8` calls from sole owner `0x003729b0`. Target counts are
`1/1/1/2` in entry order; comparison, other-address, and absolute-memory
partitions are empty. Structural verification requires the exact target and
owner partitions.

The artifact's pretty-printed file SHA-256 is
`c7da48c159c104db62ce6f0a6c47e31e2739179d9435a49c52e2dfc3014bbaea`;
its canonical JSON SHA-256 is
`1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing evidence after
failed final validation, and removes a failed private publication. Adjacency,
analysis labels, decoded registers, and addresses do not prove shared purpose,
execution order, exception behavior, ABI, argument meaning, target identity,
state mutation, success, normal return, runtime reachability, dynamic or
computed references, data consumers, un-atlased code, or Lua-side behavior.

## Native query pointer-target residual direct-target-set static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.py`
canonical-pins the pointer-target and adjacent-cluster artifacts and seals the
three direct targets outside that cluster and the deferred multi-range target.
This is a relationship coverage set, not a claim that the noncontiguous bodies
share purpose or behavior.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --adjacent-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --adjacent-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary`.
It seals three distinct atlas bodies:

- `0x00372970`: 50 bytes, 21 instructions, 21-node / 21-edge body-local CFG.
- `0x00007e70`: one-byte `RET`, one instruction, 1-node / 0-edge CFG.
- `0x003581b3`: six-byte `FF 25` indirect jump, one instruction, 1-node /
  0-edge body-local CFG.

The `0x00372970` projection preserves conditional successors
`0x00372982/0x0037298f`, keeps the `E8` at `0x0037298a` as a call fallthrough,
and represents final `E9` at `0x0037299d` as an external direct branch with no
body-local successor. That `E9` independently rejoins the sole top-level
out-of-body transfer and outgoing native record. Both it and the preceding
`E8` target `0x003574ca`; their behavior remains opaque. The `0x003581b3`
node is an `indirect_jump`, not a terminal instruction. Its absolute-memory
operand names VA `0x007d6580` / RVA `0x003d6580` in file-backed non-writable
`.rdata`, without assigning the dynamic jump target.

The typed PE-address operand audit is complete across immediate and
absolute-memory classes: conditional `JE`, `E8`, and external `E9` targets are
three file-backed `.text` immediates; the `FF 25` pointer location is the sole
absolute-memory `.rdata` operand. The all-eight-register `FF D0..D7` audit is
empty. The pinned census has no direct Lua record for these entries, and local
call-r32 syntax is absent; the empty staged partition does not exclude
computed, dynamic, or Lua-side targets.

All eleven direct edges of pointer target `0x003729b0` form an exact unique
partition: five residual parents, five adjacent-cluster parents, and one
deferred `0x00372a53 -> 0x0039d580` parent. The adjacent rows rejoin the pinned
cluster artifact. Each residual parent also cross-joins its independently
rebuilt whole-atlas reference row.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 736 references survive: 719 immediate
`E8` direct calls and 17 immediate `E9` other-address uses, with no
absolute-memory target reference. Target counts are `3/252/481` in artifact
body order; owner counts are `1/246/316`. There are 560 distinct owners and
563 target-owner groups. Canonical partition hashes are
`7208e20dcdff5e939aef709c668036da819b44bd609ee34b5bbfe09109492587`,
`cf1feca3f9046f1e0f2f06230bc009518f70b2f3926981fbcdf5e7848416bdac`,
and `e66aafd7e8153496d8f89842adb8ee37412180600ff09edd908f341a2a7187f8`
for the global-owner, target-owner, and target-reference projections.

The artifact's pretty-printed file SHA-256 is
`13784d112c47e9de5b0a92f7cfaac17245a98afb48214699ed516360b6d4d702`;
its canonical JSON SHA-256 is
`0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d`.
Publication validates one locked point-in-time snapshot, rejects writer
contention and out-of-root destinations, preserves differing existing
evidence, and cleans failed private publication. Relationship membership,
analysis labels, decoded controls, and addresses do not prove semantic
kinship, ABI, purpose, input/output meaning, runtime reachability, ordering,
termination, target identity, state mutation, success, effect, data consumers,
un-atlased code, or Lua-side behavior.

## Native query-new-handler local-helper static boundary

`scripts/itb_native_query_new_handler_local_helper_static_boundary.py`
canonical-pins the exact query-new-handler boundary, rejoins its
`0x0038bc41 -> 0x0038bc51` edge, seals the complete target body and CFG, and
scans every atlas operand for the complete target-entry reference frontier.
The predecessor is validated both from the pinned query evidence and from the
independently rebuilt PE reference record. The target's default
`FUN_0078bc51` spelling is retained only as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_new_handler_local_helper_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-new-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_local_helper_static_boundary.json

python -X utf8 scripts/itb_native_query_new_handler_local_helper_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-new-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_local_helper_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_new_handler_local_helper_static_boundary`. It seals target
`0x0038bc51`: 9 bytes, all four exact instruction points, and one 4-node /
3-edge CFG. Its sole outgoing direct call at
`0x0038bc53 -> 0x00388c0d` remains opaque.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one target reference survives from one
owner, a five-byte immediate `E8` call; comparison, absolute-memory, and
other-address partitions are empty. Direct and staged Lua calls, the complete
eight-register call audit, retained literals, and absolute-address records are
also empty.

The artifact's pretty-printed file SHA-256 is
`3cc19d7a2fb7aac636aba2395692598dad8de7e51c5be9a12c75c30b33eb306c`;
its canonical JSON SHA-256 is
`01a03401fdbef4e6d1d575ab74e498b5271387a1ffde440c0dee44b28ad5439c`.
Publication validates one locked point-in-time snapshot, requires the explicit
owner partition during structural verification, normalizes inherited errors,
and preserves a published destination after failed final validation. Helper
purpose, unlock or lock semantics, ABI, argument meaning, success, state
mutation, normal return, runtime reachability, source identity, callee
behavior, dynamic or computed references, data consumers, un-atlased code,
and Lua-side references remain unproved.

## Native query local-helper callee static boundary

`scripts/itb_native_query_local_helper_callee_static_boundary.py`
canonical-pins the query local-helper evidence, rejoins exact predecessor
`0x0038bc53 -> 0x00388c0d`, seals the complete relationship-defined target
body and CFG, and scans every atlas operand for the target-entry frontier. The
target's `___acrt_unlock` spelling is retained only as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_local_helper_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --local-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_local_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_local_helper_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_local_helper_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --local-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_local_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_local_helper_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_local_helper_callee_static_boundary`. It seals target
`0x00388c0d`: 23 bytes, all nine exact instruction points, and one 9-node /
8-edge CFG. The body has no direct native edge, direct or staged Lua call,
`call r32`, or retained literal.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 29 target-entry references survive from
29 owners, all five-byte immediate `E8` calls. Comparison, other-address, and
absolute-memory entry-reference partitions are empty, and the explicit owner
partition is required during structural verification.

One absolute add operand points into the virtual-only writable `.data` tail at
VA `0x008b70a8` / RVA `0x004b70a8`. One absolute-memory call uses the
file-backed non-writable `.rdata` slot at VA `0x007d6080` / RVA `0x003d6080`.
The sealed PE import table contains exactly one row for that slot:
`KERNEL32.dll!LeaveCriticalSection`, hint 825, no ordinal. This is import-table
metadata only, not proof of runtime execution or synchronization behavior.

The artifact's pretty-printed file SHA-256 is
`2a0f26e367e6527890757e7fdafa9f621e3a0b07566fd7624807a5781b44ef95`;
its canonical JSON SHA-256 is
`c41457569fcc4f412c35de53f7830d6e4049791a4991062d341d73a756437310`.
Publication validates one locked point-in-time snapshot, requires the exact
owner partition during structural verification, normalizes inherited errors,
blocks writer contention, preserves existing published evidence after failed
final validation, and removes a failed private publication. The analysis
label and named import do not prove purpose, lock/unlock semantics, ABI,
argument meaning, state mutation, success, normal return, runtime
reachability, source identity, or pointed-to data. Dynamic, computed,
indirect, data, un-atlased, and Lua-side references remain unproved.

## Native query-handler second-callee static boundary

`scripts/itb_native_query_handler_second_callee_static_boundary.py`
canonical-pins the query-handler evidence, rejoins exact predecessor
`0x0038bc1a -> 0x00388bc5`, seals the complete relationship-defined target
body and CFG, and scans every atlas operand for the target-entry frontier. The
target's `___acrt_lock` spelling is retained only as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_second_callee_static_boundary`. It seals target
`0x00388bc5`: 23 bytes, all nine exact instruction points, and one 9-node /
8-edge CFG. The body has no direct native edge, direct or staged Lua call,
`call r32`, or retained literal.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 26 target-entry references survive from
26 owners, all five-byte immediate `E8` calls. Comparison, other-address, and
absolute-memory entry-reference partitions are empty, and structural
verification requires the explicit 26-owner partition.

The add at `0x00388bce` points into the virtual-only writable `.data` tail at
VA `0x008b70a8` / RVA `0x004b70a8`. The absolute-memory call at
`0x00388bd4` uses the file-backed non-writable `.rdata` slot at VA
`0x007d6084` / RVA `0x003d6084`. The sealed PE import table has exactly one
row for that slot: `KERNEL32.dll!EnterCriticalSection`, hint 238, no ordinal.
This is import-table metadata only, not proof of runtime execution or
synchronization behavior.

The artifact's pretty-printed file SHA-256 is
`39daf451a37440201d5cadedf946da30d3fa90e1a23677bf39f913f4a8fa6d33`;
its canonical JSON SHA-256 is
`fd8836f3ccaa14ec45931d611f96122b7b64f2ca54331d6aa2730197c1f45b20`.
Publication validates one locked point-in-time snapshot, requires the exact
owner partition during structural verification, normalizes inherited errors,
blocks writer contention, preserves existing published evidence after failed
final validation, and removes a failed private publication. The analysis
label and named import do not prove purpose, lock or synchronization
semantics, ABI, argument meaning, state mutation, success, normal return,
runtime reachability, source identity, or pointed-to data. Dynamic, computed,
indirect, data, un-atlased, and Lua-side references remain unproved.

## Native query-handler fourth-callee static boundary

`scripts/itb_native_query_handler_fourth_callee_static_boundary.py`
canonical-pins the query-handler evidence, rejoins exact predecessor
`0x0038bc48 -> 0x003584f6`, seals the complete relationship-defined target
body and CFG, and scans every atlas operand for the target-entry frontier. The
target's `__SEH_epilog4` spelling is retained only as analysis metadata.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_fourth_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_fourth_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_fourth_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --query-handler-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_fourth_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_fourth_callee_static_boundary`. It seals target
`0x003584f6`: 21 bytes, all 11 exact instruction points, and one 11-node /
10-edge CFG. The body has no direct native edge, direct or staged Lua call,
`call r32`, or retained literal.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 67 target-entry references survive from
67 owners. Sixty-six are five-byte immediate `E8` calls. The remaining row is
the six-byte BND-prefixed immediate jump at `0x0039d7c4`, owned by
`0x0039d7b9`; it is classified as `other_address`, has no call form, and is
rejoined to its normalized Ghidra edge. Comparison and absolute-memory
entry-reference partitions are empty, and structural verification requires
the explicit 67-owner partition.

The instruction at `0x003584f9` has an exact segment-relative destination
write using `FS:[0]`. The record pins the seven instruction bytes, SHA-256,
operand index, segment, displacement, absent base/index, and write access. It
is deliberately not represented as a PE absolute address and does not assign
meaning to the segment-relative location or pointed-to data.

The artifact's pretty-printed file SHA-256 is
`2af1d59469ee8213ea8ae29bd0df46969af1b7c4acc9453f9d24ae06b655f9a7`;
its canonical JSON SHA-256 is
`d89c9a6eb25d63cd08830a0ee7beab1df5413aa6eb2b05ac791b8c1b7fedc05e`.
Publication validates one locked point-in-time snapshot, requires the exact
owner partition during structural verification, normalizes inherited errors,
blocks writer contention, preserves existing published evidence after failed
final validation, and removes a failed private publication. The analysis
label does not prove purpose, SEH, exception, epilog, stack, register, ABI,
argument meaning, state mutation, success, normal return, runtime
reachability, source identity, or segment-relative contents. Dynamic,
computed, indirect, data, un-atlased, and Lua-side references remain unproved.

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
