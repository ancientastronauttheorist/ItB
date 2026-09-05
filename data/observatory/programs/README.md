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
four outgoing direct calls are retained as opaque native edges. The body contains no
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
references remain unproved. Its first and second direct targets are now closed
below; the other two remain opaque.

## Native assertion-helper first-callee static boundary

`scripts/itb_native_assertion_helper_first_callee_static_boundary.py`
canonical-pins the exact assertion-helper receipt, rejoins its
`0x00379ccd -> 0x0038e392` edge, seals the relationship-defined target body
and CFG, accounts for both outgoing native edges and the complete PE-address
and non-control-immediate partitions, binds the body-local HIGHLOW relocation
sites, and scans every operand in every atlas range for the complete incoming
reference frontier.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_first_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --assertion-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_static_boundary.json

python -X utf8 scripts/itb_native_assertion_helper_first_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --assertion-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_assertion_helper_first_callee_static_boundary`. It seals exact
range `[0x0038e392,0x0038e3d1)`: 63 bytes, all 23 instruction points, and one
23-node / 23-edge CFG. The three terminal `ret` points prove syntax only. Its
complete outgoing-native partition retains opaque direct edges
`0x0038e3bc -> 0x00385bcc` and `0x0038e3c7 -> 0x00379ef2`. Direct and staged
Lua calls, indirect controls, the complete eight-register call audit,
BND-prefixed controls, segment-qualified memory, and interrupt syntax are
empty.

The three absolute-memory operands at `0x0038e3a8`, `0x0038e3af`, and
`0x0038e3b4` all name VA `0x008b7534` / RVA `0x004b7534`. That RVA lies in
writable `.data` but beyond its raw-backed end, so it is virtual-only and has
no file offset. The hash-pinned base-relocation directory contains the exact
matching HIGHLOW sites `0x0038e3a9`, `0x0038e3b0`, and `0x0038e3b6`. Four
ordinary immediates (`2`, `3`, `0x16`, and `0xffffffff`) are retained as
opaque comparison/data syntax.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one target reference survives: the parent
five-byte immediate `E8` call at `0x00379ccd`, from one owner. Comparison,
other-address, and absolute-memory entry references are empty. The artifact's
pretty-printed file SHA-256 is
`bc6e195e133fba208b13344aea8e211e44fc57e0399d860af38f2ab9ed3383f0`;
its canonical JSON SHA-256 is
`e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0`.

Publication validates one locked point-in-time snapshot and removes only its
own newly linked inode if final validation fails. The `__set_error_mode`,
`__errno`, and default Ghidra spellings remain metadata only. CRT identity,
source purpose, ABI, inputs, outputs, global-state meaning, runtime
reachability, ordering, effects, success, failure, normal return, dynamic or
computed references, un-atlased code, Lua-side references, and both child
behaviors remain unproved.

## Native assertion-helper first-callee direct-callee pair static boundary

`scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.py`
canonical-pins the first-callee receipt, rejoins both of its outgoing opaque
parents, seals the two relationship-defined target bodies and CFGs, proves
their complete outgoing/control and operand partitions, binds their exact
HIGHLOW frontier, and scans every operand in every atlas range for the full
paired incoming-reference frontier.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --first-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json

python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --first-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json
```

The artifact has analysis kind
`pe_native_assertion_helper_first_callee_direct_callee_pair_static_boundary`.
It rejoins exact parents `0x0038e3bc -> 0x00385bcc` and
`0x0038e3c7 -> 0x00379ef2`. Target `0x00385bcc` seals range
`[0x00385bcc,0x00385bdf)`: 19 bytes, seven instructions, and a 7-node /
6-edge CFG. Target `0x00379ef2` seals range
`[0x00379ef2,0x00379f02)`: 16 bytes, nine instructions, and a 9-node /
8-edge CFG. Their complete outgoing-native partitions retain opaque child
edges `0x00385bcc -> 0x0038edb6` and `0x00379ef9 -> 0x00379e77`.

The immediate at `0x00385bd5` names VA `0x008940d0` / RVA `0x004940d0`
in raw-backed writable `.data`, file offset `0x004922d0`. The hash-pinned
base-relocation directory contains the sole matching HIGHLOW site at
`0x00385bd6`; the second body has no HIGHLOW site. Ordinary immediates `0x10`
and `0x14` remain opaque. Direct/staged Lua calls, indirect controls, all eight
register-call forms, import/IAT body controls, BND-prefixed controls,
segment-qualified memory, and interrupt syntax are empty.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 479 target-entry references survive, all
five-byte immediate `E8` calls. Target `0x00385bcc` has 308 references from
202 owners; target `0x00379ef2` has 171 from 148 owners. Their union contains
202 owners and 350 target-owner pairs. The artifact's pretty-printed file
SHA-256 is
`40a83312f9867bcf385e836eb9547398803d8628a29c3d4716aec7ba4c21a493`;
its canonical JSON SHA-256 is
`e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378`.

For a new output, publication retains a content-addressed stage named
`.itb-observatory-stage-<pretty-printed-sha256>.json`, validates it through a
locked descriptor, and creates the destination with an atomic no-overwrite
hard link. The writer never unlinks, removes, renames, replaces, or truncates
an existing pathname. A differing/incomplete retained stage or any failure
after linking is preserved and blocks fail-closed until deliberate
maintenance; an exact stage and output are idempotently reusable. Windows
denies write/delete sharing and uses a mandatory full-range lock; POSIX locks
cover cooperating writers. Neither platform claims perpetual immutability
after the final locked snapshot.

The `__errno` and default Ghidra spellings remain metadata only. CRT identity,
source purpose, ABI, inputs, outputs, `.data` contents, runtime reachability,
effects, success, failure, normal return, computed or dynamic references,
un-atlased code, Lua-side references, and both child behaviors remain
unproved.

## Native assertion-helper direct-callee pair first-target child boundary

`scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.py`
canonical-pins the paired predecessor, rejoins its first opaque child edge,
seals the relationship-defined child body and CFG, proves its complete
outgoing/control and operand partitions, binds raw import and HIGHLOW syntax,
and scans every operand in every atlas range for the complete incoming
reference frontier.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --direct-callee-pair-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json

python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --direct-callee-pair-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json
```

The artifact has analysis kind
`pe_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary`.
It rejoins `0x00385bcc -> 0x0038edb6` and seals exact range
`[0x0038edb6,0x0038ee3b)`: 133 bytes, 53 instruction points, and a 53-node /
57-edge CFG. Its six outgoing immediate `E8` calls remain opaque native
edges. Direct/staged Lua calls, register calls, other indirect controls,
BND-prefixed controls, segment-qualified memory, and interrupt syntax are
empty.

Three body-local `FF 15` controls are raw-bound through the PE import
descriptor, ILT, IAT, hint, and import-name structures. Their
`GetLastError` and `SetLastError` spellings remain metadata only, and external
IAT-consumer closure is not claimed. Two absolute-memory operands name
raw-backed writable `.data` VA `0x00894290` / RVA `0x00494290`, file offset
`0x00492490`; one immediate names virtual-only writable `.data` VA
`0x008b7550` / RVA `0x004b7550` with no file offset. The hash-pinned base
relocation directory contains all six matching HIGHLOW sites. Four non-PE
immediates remain opaque comparison/data syntax.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly six target-entry references survive from
six owners, all five-byte immediate `E8` calls. The artifact's pretty-printed
file SHA-256 is
`eac8de889925d07bc807f1ec676c143348d2729bc51d6ecbc402f08ca2ef3eab`;
its canonical JSON SHA-256 is
`314c5817e3a1560c446853474cc0f86fbf3a8195fb60f48c85822a3ed8aca3bc`.

Publication uses the same retained content-addressed stage and atomic
no-overwrite hard-link protocol as the paired predecessor. The writer never
unlinks, removes, renames, replaces, or truncates a pathname. CRT identity,
source purpose, ABI, inputs, outputs, data and IAT contents, runtime
reachability, effects, normal return, computed or dynamic references,
un-atlased code, Lua-side references, and all six child behaviors remain
unproved. The pair's second child now has the structural receipt below.

## Native assertion-helper direct-callee pair second-target child boundary

`scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary.py`
owns its build, validation, encoding, and immutable writer machinery without
reconfiguring or delegating to the first-child module. The active artifact is
`windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json`, schema 2,
with analysis kind `pe_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2`.

It canonical-pins the paired predecessor and rejoins exact parent edge
`0x00379ef9 -> 0x00379e77` from owner `0x00379ef2`. It seals
`[0x00379e77,0x00379ef1)`: 122 bytes, 43 instruction points, and a 43-node /
44-edge CFG. Three direct native edges lead to `0x0038edb6`, `0x003574ca`,
and `0x00379f1f`; their behavior remains opaque. The final `E8` at
`0x00379eec` ends the declared body, so the finite graph has no fallthrough
there. This does not prove that the callee never returns.

Two opaque indirect controls use register ESI at `0x00379eb2` and an
absolute-memory slot at `0x00379eac`. The latter reads raw-backed,
non-writable `.rdata` VA `0x007d6580` / RVA `0x003d6580`, exactly at the
exclusive end of the IAT directory; it is not an import binding. Two data
operands name raw-backed writable `.data` RVA `0x00493f28`; another names
virtual-only `.data` RVA `0x004b7080`. Together with the control slot these
make four PE-address operands and four HIGHLOW sites. Two ordinary literals
remain opaque. The all-operand scan of 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions finds exactly two target-entry
references from two owners, both immediate `E8` calls including the parent.

The original schema-1 artifact remains preserved. Its body register-call audit
correctly recorded ESI, but its duplicate `native_calls.call_r32_audit` omitted
that site due to a case-sensitive generator comparison. Schema 2 corrects only
that audit plus schema/kind and `supersedes` provenance. The executable, body,
CFG, references, and other facts are unchanged. Both active register audits
agree; the active validator rejects the legacy inconsistent receipt. This
correction makes no semantic or coverage promotion.

The active pretty-printed file SHA-256 is
`9d5def6e41d69c2e2e231110c494f8a9f0e763c51b2df67102a73f133d27c1b5`;
its canonical JSON SHA-256 is
`918628e05e4579a40127416853ed5e1af91fa6516e86798a48107a65f433be19`.
Legacy raw and canonical hashes remain, respectively,
`25b174666130d3a5120dc4f01a66cdf3c5cdf657dd9010a2ba89f4137c902d0e` and
`149115c259e411889adc3acee6bccb5c84a09b7ac8acafa0060726d5ee3703ed`.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --direct-callee-pair-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json

python -X utf8 scripts/itb_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --direct-callee-pair-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json
```

For PE-free consistency validation, use `verify-structure` with the same
predecessor, direct-call, program-facts, and evidence arguments, omitting
`--executable` and `--inventory`. Structural consistency is not binary proof.
The writer retains content-addressed staging and atomic no-overwrite hard-link
publication, with no pathname deletion or replacement. CRT identity, ABI,
source purpose, runtime execution, data contents, indirect targets, callee
behavior, and normal-return semantics remain unproved.

## Assertion second-child direct-callee frontier

`windows_build_13725832_31fe35265598_native_assertion_helper_second_child_callee_frontier.json`
has schema 1 and analysis kind `pe_native_assertion_helper_second_child_callee_frontier`.

The second-child direct-callee frontier now joins all three outgoing edges
from `0x00379e77`. Edge `0x00379e88 -> 0x0038edb6` reuses the first-child
receipt, and `0x00379ebd -> 0x003574ca` reuses the query-handler residual-callee
receipt. Each join agrees with its source edge, target atlas identity, and an
exact incoming-reference row in the reused receipt. Edge
`0x00379eec -> 0x00379f1f` receives a new 51-byte body boundary containing
20 instructions and a 20-node / 20-edge CFG.

The new body has two direct native calls (`0x00379f21 -> 0x0039cb92` and
`0x00379f3a -> 0x00379d28`), two absolute-memory imported calls, one
`INT 0x29`, six ordinary immediate operands, and two HIGHLOW relocations.
Raw descriptor/ILT/IAT/import-name hashes bind the imported calls to metadata
spellings `GetCurrentProcess` and `TerminateProcess`. Those names and the
Ghidra label `__invoke_watson` do not establish behavior. The interrupt's edge
to the next instruction is labeled `opaque_interrupt_possible_fallthrough`;
call edges likewise express only possible fallthrough. No runtime continuation,
termination, or normal-return claim follows from this graph.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 45 references from 45 owners point to the
new target, all immediate five-byte calls, including its parent. All three
immediate parent direct-callee bodies are now accounted for structurally;
the parent's indirect controls, the new body's two native descendants, and
all callee behaviors remain unresolved. There is no accounting-level promotion.

The builder independently verifies the exact PE and direct-call census,
rechecks the caller's three edges and both reused body byte identities, then
decodes the new body, raw import/relocation witnesses, and the whole-atlas
reference scan. It pins existing receipts by canonical hash; it does not
rerun their entire original analyses. The PE-free validator checks the
hash-pinned normalized receipt and recomputes source/edge/graph joins and
counts. That consistency check is not independent binary evidence.

New publication contains normalized facts and hashes, without instruction
bytes or disassembly. The writer keeps the retained content-addressed stage
and no-overwrite hard-link protocol, and requires the sealed frontier identity.
Pretty-printed file SHA-256:
`19a5d65db948083b985d0eca8757db5c4663d5892decdef69a1c87fb6b5de9f3`.
Canonical JSON SHA-256:
`39a712704c58f0789580ebac647ce13ae23681a1df12f0dc93d549159e37ddeb`.

```powershell
python -X utf8 scripts/itb_native_assertion_helper_second_child_callee_frontier.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --second-child data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json `
  --first-child data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json `
  --reused-callee data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_child_callee_frontier.json

python -X utf8 scripts/itb_native_assertion_helper_second_child_callee_frontier.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --second-child data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json `
  --first-child data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json `
  --reused-callee data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_child_callee_frontier.json

```

For `verify-structure`, pass the five source receipts and `--evidence`, and
omit `--executable` and `--inventory`.

## Assertion descendant pair

`windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json`
has schema 1 and analysis kind `pe_native_assertion_helper_descendant_pair`.

The paired receipt consumes the preceding frontier's two native edges:
`0x00379f21 -> 0x0039cb92` and `0x00379f3a -> 0x00379d28`, both from
`0x00379f1f`. Source edges, target atlas identities, and exact caller bytes
are rechecked. The source frontier is canonical-pinned; its entire original
analysis is not rerun.

Target `0x0039cb92` spans six bytes and one instruction. Its single-node CFG
has no local successor: the instruction jumps through IAT slot RVA
`0x003d6010`, bound by raw descriptor/ILT/IAT/import-name hashes to metadata
spelling `IsProcessorFeaturePresent`. This proves an import transfer boundary,
not imported behavior or a reviewed compiler/runtime exclusion.

Target `0x00379d28` spans 315 bytes and 78 instructions, with a 78-node /
81-edge instruction CFG. Five native calls reach three distinct targets:
`0x003586b6` twice, `0x00370960` twice, and `0x003574ca` once. Three body-local
import calls bind metadata spellings `IsDebuggerPresent`,
`SetUnhandledExceptionFilter`, and `UnhandledExceptionFilter`. Four
conditional branches and one return are retained as syntax. Calls have only
possible fallthrough edges; runtime return and exception semantics are unproved.

Across both bodies, 124 explicit operands include 44 memory expressions,
ten ordinary immediates, five absolute PE-address operands, and six
segment-register source operands. The SS/CS/DS/ES/FS/GS operands are stored
into EBP-relative word destinations; there are no segment-relative memory
dereferences in these bodies. Decoder access flags and memory-shaped operands
remain syntax: in particular, LEA does not establish a runtime memory read.
Five HIGHLOW sites cover the mapped data operand and four import controls.

The complete atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. The six-byte target has six incoming references
from six owners; the larger target has two from two owners. Their union is
eight references from six owners, all immediate five-byte calls. Both source
edges occur in that incoming frontier. Global IAT consumers, computed and
un-atlased references, native child behavior, imported implementations, runtime
context/exception-record identity, and accounting promotions remain outside
this proof.

Exact validation verifies the PE and direct-call census, caller and target
body bytes, decoded controls/operands, raw import and relocation witnesses,
and complete atlas entry references. PE-free validation recognizes the
hash-pinned normalized receipt and recomputes source/parent/graph/operand/count
joins; it does not independently prove the binary. Publication contains no
instruction bytes or disassembly and preserves immutable no-overwrite staging.
The file SHA-256 is
`0c7fbea632343e29a05e8e9ec67f695021bbc8154e2bc7d2661e6ac8c859c1bc`;
canonical JSON SHA-256 is
`47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b`.

```powershell
python -X utf8 scripts/itb_native_assertion_helper_descendant_pair.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --frontier data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_child_callee_frontier.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json

python -X utf8 scripts/itb_native_assertion_helper_descendant_pair.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --frontier data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_child_callee_frontier.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json

```

For `verify-structure`, keep the three source arguments and `--evidence` and
omit `--executable` and `--inventory`.

## Assertion leaf-callee artifact

`windows_build_13725832_31fe35265598_native_assertion_helper_leaf_callees.json`
(schema 1, analysis kind `pe_native_assertion_helper_leaf_callees`) closes the
remaining two body boundaries beneath `0x00379d28`. All five parent native
calls are rejoined: two to `0x003586b6`, two to `0x00370960`, and one to the
previously sealed `0x003574ca`. The last join includes the existing receipt's
exact incoming-reference record; its body is not counted as newly analyzed.

The new bodies cover 354 bytes and 91 instructions:

- `0x003586b6`: eight bytes, two instructions, two CFG nodes and one edge.
  Its first instruction performs a 32-bit read-modify-write at RVA
  `0x004b6e58`. The independently checked instruction grammar establishes a
  zero result conditional on normal completion of that instruction, followed
  by near-return syntax. The location is writable, virtual-only `.data`;
  the receipt supplies no initial file contents, variable purpose, ownership,
  execution observation, concurrency guarantee, or normal function-return proof.
- `0x00370960`: 346 bytes, 89 instructions, 89 CFG nodes and 102 edges.
  Sixteen conditional branches, one unconditional internal branch, and three
  returns are retained. The analysis metadata calls it `_memset`; that label
  is not a semantic or compiler/runtime exclusion proof. REP STOSB appears as
  one syntactic node with possible-completion fallthrough. Its micro-iterations
  are not expanded. Scalar and SIMD memory expressions remain decoder syntax;
  direction, bounds, CPU support, exceptions, completion and full fill behavior
  are unproved. Legacy `66` prefixes are recorded without assuming every one
  means a word-sized operand.

Neither new body contains a call, import control, interrupt, indirect jump,
external branch or local fallthrough escape. The receipt records 157 explicit
operands, 34 memory expressions, 29 ordinary immediates, four absolute memory
operands and four HIGHLOW relocations. The repeated-string destination includes
an implicit ES segment; it is distinct from the preceding receipt's explicit
segment-register stores. LEA memory expressions do not imply a memory read.

The complete atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes
and 1,153,814 instructions. It finds two incoming calls from one owner for the
small body and 157 calls from 122 owners for the larger body, totaling 159
calls from 122 owners. Four parent edges join those new incoming references.
All observed entry references are immediate calls; computed, indirect,
data-only and un-atlased references remain outside the scan.

Exact verification replays the PE/direct-call prerequisites, parent caller
bytes, new body controls and operands, raw relocation witnesses and all-atlas
entry-reference scan. Parent and reused receipts are canonical-pinned without
rerunning their full analyses. PE-free verification recognizes the sealed
normalized artifact and checks internal joins; it is not independent binary
proof. Publication is immutable and contains no disassembly or copied bytes.
No accounting level or runtime ownership is promoted by this artifact.

Raw SHA-256: `0fbc28fb7e55a61538e74d07c667eb39796febe5ee181c345997f5f6180714ea`.
Canonical JSON SHA-256: `1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2`.

Build and verify with the same four source arguments:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_leaf_callees.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pair data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json `
  --reused-callee data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_leaf_callees.json
```

For `build`, replace `verify` with `build` and `--evidence` with `--output`.
For `verify-structure`, retain the four sources and `--evidence`, omitting
`--executable` and `--inventory`.

## Assertion fill-conformance artifact

`windows_build_13725832_31fe35265598_native_assertion_helper_fill_conformance.json`
(schema 1, `pe_native_assertion_helper_fill_conformance`) adds isolated exact-body
emulation evidence for `0x00370960`. An independent byte-fill specification
matches 14,616 finite matrix vectors and four null-destination zero-length
vectors. A direction-flag-set REP control is rejected for an out-of-interval
write. The traces cover 89 of 89 instruction nodes and 102 of 102 CFG edges;
repeated same-address REP events are excluded from that coverage count.

The receipt pins Unicorn 2.1.4, native core `(2, 1, 33621247)` and explicit
`UC_CPU_X86_HASWELL` model 19. Checks cover the destination-byte contract,
individual write bounds and write union, permitted data reads, return sentinel,
stack increment and preserved registers. Neither finite branch coverage nor
emulation is promoted to a universal, native-game, CRT-identity or ownership
claim. Full scope and reproduction commands are in
[`docs/native_fill_conformance.md`](../../../docs/native_fill_conformance.md).

Raw SHA-256: `2b252e9dfa988551c8a110d90abe539f20c00bbc62bea27c34f6441d6d67bcbf`.
Canonical SHA-256: `6f4bba8750713184f5de2bf119b36605078e4386e05712a2f686b6e744801246`.

## Assertion caller-fill artifact

`windows_build_13725832_31fe35265598_native_assertion_helper_caller_fill.json`
(schema 1, `pe_native_assertion_helper_caller_fill`) checks the 81-byte prefix
of `0x00379d28` through exclusive boundary `0x00379d79`, including its two
calls to the fill body and the optional eight-byte helper. Static interval
arithmetic establishes adjacent, disjoint 80- and 716-byte destinations before
the protected four-byte slot. Finite replay passes 256 prefix cases, 512 fill
observations and 128 optional-helper executions. All 25 prefix nodes are
observed; 111 total nodes across prefix/callees does not mean full-path coverage.
A DF-set negative control rejects an out-of-region write in the second fill.

Checks include exact argument and return frames, per-fill and final stack
oracles, individual permitted writes, register preservation, global-page
invariants, and shared 24-byte argument cleanup. Whole-caller return, later
pointer stores, runtime identity and accounting promotions remain open.
See [`docs/native_caller_fill.md`](../../../docs/native_caller_fill.md) for
frame intervals, domain limits, emulator pins and reproduction commands.

Raw SHA-256: `4206855ecf4c727e3a85ab9bb8fa5c2f37ecb1c51b2f7eb1f696c049d9754d48`.
Canonical SHA-256: `b89d1873e56c4afb27c96229c05a1a0516732a5bdc3d2151173baeb5d4a5b653`.

## Assertion frame-store artifact

`windows_build_13725832_31fe35265598_native_assertion_helper_frame_stores.json`
(schema 1, `pe_native_assertion_helper_frame_stores`) covers the 167-byte,
30-instruction slice `[0x00379d79,0x00379e20)`. A generic symbolic transfer
grammar matches an independent field overlay. All 256 finite boundary-state
cases pass exact ordered memory-event and whole-stack checks: 22 frame stores,
one temporary flags-stack write and six reads per case. Two incorrect oracles
are rejected. The first import instruction remains unexecuted.

Current pointer/register/flags provenance is kept separate from original
caller-state or context-structure claims. Runtime segments are zero; nonzero
selector runtime behavior and arbitrary volatile-input prefix reachability
remain unproved. See [`docs/native_frame_stores.md`](../../../docs/native_frame_stores.md)
for the field map, upper-halfword preservation, finite domain and commands.

Raw SHA-256: `09515f803d5b7bf9e6534a62540fbfb740f89d9b32216f2d6508e9ae1a54aef0`.
Canonical SHA-256: `69afa7ae52de9fe086d15f92350394518db88be433f7b9b3f5607c1a0a36d0b1`.

## Assertion import-handoff artifact

`windows_build_13725832_31fe35265598_native_assertion_helper_import_handoff.json`
joins the caller prefix and stores in the same emulator instance through
exclusive `0x00379e20`. Its 256 cases check actual volatile values against
independent arithmetic and check last-writer provenance before continuing
into the store overlay. There are 512 fill observations, 128 optional-helper
executions and 55 covered caller-prefix nodes. A changed boundary ECX is
rejected. Imports, record identity and whole-function return remain outside
this proof. See [`docs/native_import_handoff.md`](../../../docs/native_import_handoff.md).

Raw SHA-256: `c8262ccee8149477fc52f49e5a5fdc22cf4b7d6898f1eea26a763ab169c7af39`.
Canonical SHA-256: `21ed5942d039ec0e16c94f40447f0e15bebea6d74298a1af448eb93f55ce7712`.

## Windows x86 exception-layout compatibility

`windows_build_13725832_31fe35265598_windows_exception_layout.json` records an
independent compiled SDK probe: 33 measured fields, three structure sizes,
four-byte pointers and `CONTEXT_CONTROL`. Its map matches all 22 frame stores
while preserving six two-byte writes inside four-byte selector fields.
The 162 included headers are hashed. This proves compatibility with the
selected SDK layout, without identifying the game's compiler or proving
import consumption or native object validity. See
[`docs/windows_exception_layout.md`](../../../docs/windows_exception_layout.md).

Canonical SHA-256: `c71a3142e5fc172a6a686a1b83f3bce3a9af181142c8386276ed481f2861acef`.
Raw SHA-256: `dc11ac81b491707444e5b54cbe6edbf8b25d9985b757d9e4fe4c444e8fb5cd55`.

## Conditional assertion import arguments

`windows_build_13725832_31fe35265598_native_assertion_helper_import_arguments.json`
seals six instructions and 23 bytes from the first import to the unexecuted
`UnhandledExceptionFilter` call. Its symbolic transfer assumes normal stdcall
returns and preserved caller-owned frame memory; it derives a null argument
for the second call and the pair pointer F-808 at ESP F-816 for the third. Three
IAT bindings are freshly rechecked. No imported implementation is executed.
See [`docs/native_import_arguments.md`](../../../docs/native_import_arguments.md).

Canonical SHA-256: `a5db0b615b94a1291132a500fd025a74aeb4b0f8b78409f5d91bb30a6d4e282f`.
Raw SHA-256: `0c37b9bd564224d0d2593a3b9d9b573aadbf42e847b40587fada7a188c6c6933`.

## Native assertion-helper second-callee static boundary

`scripts/itb_native_assertion_helper_second_callee_static_boundary.py`
canonical-pins the exact assertion-helper receipt, rejoins its
`0x00379cdc -> 0x0038c89f` edge, seals the relationship-defined target body
and CFG, proves its complete empty outgoing/control partitions, and scans every
operand in every atlas range for the full incoming reference frontier.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_assertion_helper_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --assertion-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_assertion_helper_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --assertion-helper-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_assertion_helper_second_callee_static_boundary`. It seals target
`0x0038c89f`: six bytes, both exact instruction points, and one 2-node / 1-edge
CFG. Its last `ret` is terminal syntax only. Declared outgoing native calls,
indirect controls, direct/staged Lua calls, the complete eight-register call
audit, non-PE immediates, BND-prefixed controls, segment-qualified memory, and
interrupt syntax are all complete empty partitions.

The one PE-address operand is operand 1 of the exact five-byte `A1` read at
`0x0038c89f`, naming VA `0x008b7318` / RVA `0x004b7318`. The address is within
writable `.data` but beyond its raw-backed end, so the receipt records it as
virtual-only with no file offset and leaves its contents opaque.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly three target references survive from three
owners, all immediate `E8` calls at `0x00379cdc`, `0x00392d68`, and
`0x00392f34`; comparison, other-address, and absolute-memory entry references
are empty. The artifact's pretty-printed file SHA-256 is
`d9ae877fc1f9acb604a566470d0b8c2c1bb471701ef19de0e7c0a170e1287a07`;
its canonical JSON SHA-256 is
`ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7`.
Publication validates one locked point-in-time snapshot. The default
`FUN_0078c89f` label, source purpose, ABI, inputs, outputs, `.data` contents,
runtime reachability, effects, success, failure, normal return, dynamic or
computed references, un-atlased code, and Lua-side references remain unproved.
With no outgoing native edge, this relationship-defined branch ends here.

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

## Native operator-new second-callee static boundary

`scripts/itb_native_operator_new_second_callee_static_boundary.py`
canonical-pins the exact operator-new receipt, rejoins its
`0x003574f3 -> 0x0035848f` edge, seals the relationship-defined target body
and CFG, and scans every operand in every atlas range for the complete incoming
reference frontier. The predecessor join is checked both against the pinned
artifact and against the independently rebuilt PE reference row.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_operator_new_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_operator_new_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_operator_new_second_callee_static_boundary`. It seals target
`0x0035848f`: 28 bytes, all nine exact instruction points, and one 9-node /
8-edge CFG. It retains opaque direct edges
`0x00358498 -> 0x00358477` and `0x003584a6 -> 0x00370dab`. The latter ends
the declared range, so its final CFG node is `direct_call_range_end`; this does
not claim that the target returns or assign either callee behavior. The exact
PE-address operand partition contains both `.text` call targets and the
non-writable file-backed `.rdata` immediate pushed at `0x0035849d`.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one target reference survives from one
owner: the parent five-byte immediate `E8` call at `0x003574f3`. Comparison,
absolute-memory, and other-address partitions are empty. Direct and staged Lua
calls, the complete eight-register call audit, indirect controls, BND,
segment-qualified, and interrupt syntax are empty.

The artifact's pretty-printed file SHA-256 is
`c427f25ed77f605911ddea747fcda26b44814ca0060f0c4fce3bbffcfe717f25`;
its canonical JSON SHA-256 is
`ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856`.
Publication validates one locked point-in-time snapshot. The default
`FUN_0075848f` name remains analysis metadata only; source purpose, ABI,
exception behavior, argument meaning, normal return, runtime reachability,
source equivalence, callee behavior, computed or indirect references, data
consumers, un-atlased code, and Lua-side references remain unproved. Both
outgoing targets are now closed below.

## Native operator-new second-callee first-callee static boundary

`scripts/itb_native_operator_new_second_callee_first_callee_static_boundary.py`
canonical-pins the exact second-callee receipt, rejoins its
`0x00358498 -> 0x00358477` edge, seals the relationship-defined target body
and CFG, and scans every operand in every atlas range for the complete incoming
reference frontier. It also proves the declared outgoing-native partition is
empty before publishing that fact.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_operator_new_second_callee_first_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_first_callee_static_boundary.json

python -X utf8 scripts/itb_native_operator_new_second_callee_first_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_first_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_operator_new_second_callee_first_callee_static_boundary`. It seals
target `0x00358477`: 24 bytes, all six exact instruction points, and one
6-node / 5-edge CFG. Its final `ret` is terminal syntax only. The target has no
declared outgoing native edge, indirect control, direct or staged Lua call,
register call, BND prefix, segment-qualified memory, or interrupt syntax. Two
exact immediates name non-writable file-backed `.rdata` at RVAs `0x003f1a0c`
and `0x003f1a04`; two zero immediates form a separate complete non-PE-literal
partition.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one target reference survives from one
owner: the parent five-byte immediate `E8` call at `0x00358498`. Comparison,
absolute-memory, and other-address partitions are empty. The artifact's
pretty-printed file SHA-256 is
`7837f58f2f0b08968e29d42cb0e6da4aa405962e12b8ce956c9c8be187d2abc8`;
its canonical JSON SHA-256 is
`a82567f379b942b53f80b1f739a488e7de2637ea39e318f7a928af37900ae262`.
Publication validates one locked point-in-time snapshot. The default
`FUN_00758477` name and both `.rdata` contents remain metadata only. Source
purpose, ABI, inputs, outputs, state mutation, runtime reachability, normal
return, source equivalence, data consumers, un-atlased code, and Lua-side
references remain unproved. With no outgoing native edge, this branch ends.

## Native operator-new second-callee second-callee static boundary

`scripts/itb_native_operator_new_second_callee_second_callee_static_boundary.py`
canonical-pins the exact second-callee receipt, rejoins its
`0x003584a6 -> 0x00370dab` edge, seals the relationship-defined target body
and CFG, and scans every operand in every atlas range for the complete incoming
reference frontier. It also canonical-joins the target's one outgoing direct
edge to the body and CFG already sealed by the residual-direct-target-set
receipt, exact-proves one PE import-table row, and independently scans every
atlas operand for all uses of that row's IAT slot.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_operator_new_second_callee_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_operator_new_second_callee_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --operator-new-second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_operator_new_second_callee_second_callee_static_boundary`. It seals
target `0x00370dab`: 110 bytes, all 45 exact instruction points, and one
45-node / 48-edge CFG. Its one declared direct native call at
`0x00370de0 -> 0x003581b3` rejoins the already sealed residual target. Two
indirect controls remain opaque: `call ESI` at `0x00370de5` and absolute-memory
`FF 15` at `0x00370e0a`. The latter reads VA `0x007d616c` / RVA `0x003d616c`
from non-writable file-backed `.rdata`.

The raw PE proof binds that slot to descriptor index 7 and thunk index 91,
matching ILT/IAT words, both thunk-array terminators, hint 945, and the unique
parsed `KERNEL32.dll` / `RaiseException` row. This is import metadata only.
The complete PE-address partition contains six immediate operands plus the one
absolute-memory slot operand. Seven non-PE immediates form a separate complete
partition. One `F3 A5` at `0x00370dc2` is retained as exact `ES:[EDI]`
segment-qualified write syntax. Direct and staged Lua, BND-prefixed, and
interrupt partitions are empty; the complete eight-register audit contains
only the ESI call.

The entry scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes, and
1,153,814 instructions. Exactly 481 target-entry references from 414 owners
survive, all five-byte immediate `E8` calls. The independent IAT-slot scan over
the same scope finds exactly three absolute-memory `FF 15` uses from three
owners. The artifact's pretty-printed file SHA-256 is
`e2b04a14adfa5440a1b01f978b8785a48b3f7cf6ed26d59577963a48d4eef365`;
its canonical JSON SHA-256 is
`87f650968e7858d1676b51a99b98822846db39577da2ef737d9e8d74f4c251a8`.
Publication validates one locked point-in-time snapshot. The
`__CxxThrowException@8`, library, and import spellings remain metadata only.
Source purpose, ABI, exception or throw behavior, runtime reachability,
imported-call execution, effects, normal return, source equivalence, dynamic or
computed references, data consumers, un-atlased code, and Lua-side references
remain unproved. Its sole direct child is already sealed, so this branch ends
and both direct children of the operator-new second callee are closed.

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
`0x00378b92 -> 0x00378a40`. All three edges are closed by the dependent
receipts below, so the cluster has no opaque declared direct edge remaining.
The complete eight-register call audit
contains only `call ECX` at `0x00378b4e`. The final `jmp ESI` at
`0x00378b6c` is retained as opaque indirect-control syntax. Although
`0x00378b57` has exact `MOV ESI,ECX` bytes, the intervening direct call at
`0x00378b5d` prevents this static receipt from assigning provenance or target
identity to the jump.

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

## Native query adjacent-cluster second-callee static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.py`
canonical-pins the adjacent-cluster artifact, rejoins its exact
`0x00378b5d -> 0x00378a15` edge, seals the relationship-defined 31-byte target
and CFG, binds its exact PE backing and neighboring atlas boundaries, and
performs a whole-atlas scan for every static reference to the target entry.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --adjacent-callee-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --adjacent-callee-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary`.
It seals `0x00378a15`: 31 exact bytes, all 16 instructions, and a 16-node /
15-edge CFG. The target is bound to file-backed non-writable `.text` at file
offset `0x00377e15`. The exact left atlas neighbor at `0x00378a0c` ends at the
target, and the right neighbor at `0x00378a34` begins at the target end. These
adjacency facts prove layout only.

The body has no outgoing native direct edge, direct or staged Lua call,
register call, or indirect control. Its one PE-address operand is the
immediate at `0x00378a17`, naming writable file-backed `.data` VA
`0x00894010` / RVA `0x00494010` / file offset `0x00492210`. The exact four
file bytes are `20 05 93 19`, with SHA-256
`f0a19effaf081c6247b43afd3bc9f70ea771353137f4cce3ac38833893543af1`.
Their contents and runtime meaning remain opaque. The final `RET 4` operand is
retained separately as non-PE immediate syntax.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly four target-entry references survive, all
immediate `E8` calls at `0x003788ca`, `0x003789c7`, `0x00378aae`, and
`0x00378b5d` from four owners. The final row exactly rejoins the parent edge.
The artifact's pretty-printed file SHA-256 is
`f5f42474bb049805e9844ac5cb6bffe25f4a20b8caea22ef0120620fdaabd6b8`;
its canonical JSON SHA-256 is
`ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d`.

Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing evidence after
failed final validation, and removes a failed private publication. The
`__NLG_Notify` Ghidra name is analysis metadata only. Source identity, purpose,
ABI, arguments, outputs, behavior, invocation, effects, success, failure,
termination, normal return, computed references, un-atlased code, and Lua-side
references remain unproved.

## Native query adjacent-cluster third-callee import-thunk static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.py`
canonical-pins the adjacent-cluster artifact, rejoins its exact
`0x00378b7d -> 0x0039cb98` edge, seals the relationship-defined six-byte
target and CFG, validates the complete raw PE import binding, and performs
separate whole-atlas scans for the target entry and IAT-slot VA.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --parent-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --parent-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary`.
It seals `0x0039cb98`: six bytes, one exact `FF 25` instruction, and a
1-node / 0-edge CFG with `indirect_jump` flow and no successor. The sole PE
operand is the absolute-memory read of non-writable, file-backed `.rdata` VA
`0x007d6170` / RVA `0x003d6170`.

The raw PE32 proof binds that slot to the unique `KERNEL32.dll` /
`RtlUnwind` named-import row with hint 1048. It cross-checks import descriptor
index 7, thunk index 92, both ILT/IAT words, the NUL-terminated library and
hint/name bytes, null descriptor index 10, both KERNEL32 table terminators at
index 139, and the parsed 342-row import census. Every one of the 52 published
binding fields is reconstructed from the PE and compared before publication.

The all-operand scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly three target-entry references survive,
all immediate `E8` calls at `0x00378889`, `0x00378913`, and `0x00378b7d`
from three owners. The separate IAT-slot scan finds exactly two
absolute-memory reads from two owners: an `FF 15` call at `0x00371024` and the
target `FF 25` jump. The artifact's pretty-printed file SHA-256 is
`2f56d4bc7413036890013f70de5e202835f3254491048f17612a76c80a072f9b`;
its canonical JSON SHA-256 is
`1222126b3527186a823ffb252a97ddc2beb7a0c4dc49b45e15e462fb244b2a5b`.

Import and Ghidra names are metadata only. Loader resolution, unwind or
exception behavior, ABI, invocation, execution, effects, reachability,
termination, normal return, computed references, un-atlased code, and Lua-side
references remain unproved.

## Native query adjacent-cluster fourth-callee static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.py`
canonical-pins both the adjacent-cluster and second-callee artifacts, rejoins
exact parent edge `0x00378b92 -> 0x00378a40`, seals the complete target body and
CFG, validates its PE and neighboring gap backing, and performs separate
whole-atlas scans for the target entry and the pushed target-end address.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --adjacent-callee-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --adjacent-callee-cluster-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json `
  --second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary`.
It seals `0x00378a40`: 144 exact bytes, all 48 instructions, and a 48-node /
51-edge CFG. The exact parent record binds the 23-byte source at `0x00378b87`,
the five-byte `E8` at `0x00378b92`, and both atlas identities. The target's
Ghidra `__local_unwind4` name is analysis metadata only.

The target is bound to file-backed non-writable `.text` at file offset
`0x00377e40`. Its nearest left atlas body is the three-byte target at
`0x00378a34`, followed by nine exact `CC` bytes before the target entry. The
target ends at `0x00378ad0`; an exact 110-byte un-atlased span then reaches the
23-byte right atlas neighbor at `0x00378b3e`. Both gaps are marked unowned by
the atlas and total 119 sealed bytes. These facts prove layout and backing only.

The complete outgoing direct-edge partition is
`0x00378aae -> 0x00378a15` and `0x00378abb -> 0x00378a34`. The first edge
exactly rejoins the canonical-pinned second-callee receipt; the latter retains
an opaque three-byte `FF D0 C3` child. No direct or staged Lua call, register
call, or other indirect-control instruction survives. Six non-PE immediate
literals and three FS-qualified absolute-memory syntax records are retained
without assigning semantics.

Exactly nine PE-address operands survive: eight immediates and one
absolute-memory read. The latter names writable `.data` VA `0x00893f28` / RVA
`0x00493f28` / file offset `0x00492128`; exact bytes `4e e6 40 bb` have
SHA-256
`ce27c3a226b06f760dc303582e2dd3ab690a1634fdced2e53b238a4e947cd75f`.
All operand backing is hash-pinned without a contents or runtime-behavior
claim.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly three target-entry
references survive, all immediate `E8` calls at `0x00378b92`, `0x00386e8f`,
and `0x00386fb7` from three owners. A separate endpoint traversal finds exactly
one `other_address` reference: the target's `PUSH 0x00778ad0` at `0x00378a54`.
The artifact's pretty-printed file SHA-256 is
`105170018df7456821dc09c7e762b933f490eb9544131cb94a4b8c49810669ed`;
its canonical JSON SHA-256 is
`1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5`.

Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves differing existing output,
and removes a failed private publication. Analysis labels, adjacency, FS
syntax, addresses, and decoded control flow do not prove source identity,
purpose, unwind or exception behavior, ABI, arguments, outputs, invocation,
effects, success, failure, termination, normal return, dynamic references,
un-atlased execution, or Lua-side behavior. This closes the adjacent cluster's
last opaque declared direct edge.

## Native query adjacent-cluster fourth-callee child static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.py`
canonical-pins the fourth- and second-callee artifacts, rejoins the exact
fourth-callee edge to `0x00378a34`, seals the complete child body and CFG,
checks both caller-side EAX loaders, and scans every atlas operand for the
target-entry frontier.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --fourth-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json `
  --second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --fourth-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json `
  --second-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary`.
It seals `0x00378a34`: three exact bytes, both decoded instructions, and a
2-node / 1-edge CFG. The body is `CALL EAX; RET`. The call is retained as one
opaque register control whose static target is not proved; the return has no
explicit immediate. Direct native, direct or staged Lua, PE-address, non-PE
literal, segment-qualified memory, BND, and interrupt partitions are empty.

The target is bound to file-backed non-writable `.text` at file offset
`0x00377e34`. Its exact left atlas neighbor ends at the target entry. The
target ends at a nine-byte `CC` gap, after which the 144-byte fourth-callee
body begins at `0x00378a40`. Both neighbor bodies and the complete gap are
hash-pinned without a semantic-kinship or runtime claim.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly two target-entry
references survive, both immediate `E8` calls: `0x003789d0` from owner
`0x00378965` and `0x00378abb` from owner `0x00378a40`. No absolute-memory,
comparison, or other-address entry reference survives.

Both owner CFGs and exact caller windows are sealed. The unique CFG
predecessor of each child call loads EAX immediately from input-dependent
computed memory: `[EBX+ESI*4+8]` in the first owner and `[EBX+8]` in the
second. Each window also rejoins the pinned second-callee receipt's preceding
call and proves that EAX is reloaded afterward. Neither slice supplies a
constant, relocation, absolute PE address, import slot, or concrete indirect
target.

The artifact's pretty-printed file SHA-256 is
`61e0571607dd92e2861f06297a410c9766135c718b0420afbf3d7351d160b570`;
its canonical JSON SHA-256 is
`71f87f861758ba8ef7f7d9a6ac435bb05df38d81e7ff5c8e7fe8c95a4fb0e193`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves differing existing output,
and removes a failed private publication. Analysis labels, EAX contents,
indirect destination, source identity, ABI, arguments, outputs, invocation,
behavior, effects, success, failure, termination, and normal return remain
unproved.

## Native query fourth-callee right un-atlased-span static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.py`
canonical-pins the fourth-callee, fourth-callee-child, residual-target-set,
residual-callee, direct-call, and program-facts artifacts. It seals the complete
110-byte un-atlased range, two conservative code-candidate CFG components,
their finite control and operand frontiers, exact PE backing, and exhaustive
atlas, whole-file, relocation, and import scans.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --fourth-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json `
  --fourth-callee-child-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --residual-direct-target-set-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --fourth-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json `
  --fourth-callee-child-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --residual-direct-target-set-callee-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary`.
It seals exact range `[0x00378ad0,0x00378b3e)` at `.text` file offset
`0x00377ed0`. All 110 bytes decode into 34 instructions. Component A is 70
bytes / 21 instructions with a 21-node / 21-edge CFG; component B is 40 bytes
/ 13 instructions with a 13-node / 12-edge CFG. Their disconnected union has
34 nodes / 33 edges. The records are code candidates only: zero undecoded bytes
are proved, while padding classification and semantic function boundaries are
explicitly withheld.

Four direct `E8` controls survive: `0x00378aeb -> 0x003574ca`,
`0x00378afd -> 0x00378a40`, `0x00378b1b -> 0x00007e70`, and
`0x00378b32 -> 0x00378a40`. All target bodies rejoin canonical-pinned
prerequisite receipts. The complete operand partition contains the four calls
and one internal `JE` as five PE-address immediates, six ordinary immediates,
and explicit `RET 4`. Absolute-memory/IAT operands, register calls, other
indirect controls, segment-qualified memory, BND controls, interrupts, direct
Lua calls, and staged Lua dispatches are empty.

The exhaustive atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718
bytes, and 1,153,814 instructions. It finds one reference anywhere in the
span: `PUSH 0x00778ad0` at `0x00378a54`, owned by the fourth callee. The
whole-file dword scan finds the same address once at file offset `0x00377e55`.
One HIGHLOW relocation at RVA `0x00378a55`, represented by bytes `55 3a` at
relocation-entry file offset `0x00532e08`, backs that value. No relocation site
and none of the 342 parsed named-import IAT slots lies inside the span.

The artifact's pretty-printed file SHA-256 is
`43db988b412d01cfbe06adfb258e2dfb2a3dbba98bfcf8a65e4092165a86eec1`;
its canonical JSON SHA-256 is
`02a4e933250820874a6b8876e8092636747f780bde25f28103b4585651dc0359`.
Publication validates one locked point-in-time snapshot, preserves differing
existing output, and removes failed private publication. Decoded syntax,
adjacency, and static references do not prove function identity, compiler or
exception semantics, ABI, arguments, register meaning, purpose, runtime
reachability, invocation, ordering, frequency, behavior, effects, success,
failure, termination, normal return, or Lua-side meaning. This closes the exact
layout join from the fourth callee to the already sealed adjacent cluster
beginning at `0x00378b3e`.

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

## Native query pointer-target multi-range static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_multirange_static_boundary.py`
canonical-pins the pointer-target and residual target-set receipts, rejoins the
residual receipt's sole deferred parent, and seals target `0x0039d580` across
both of its declared atlas ranges. The relationship defines the target; its
analysis label remains metadata only.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_multirange_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --residual-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_multirange_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --pointer-target-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json `
  --residual-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_multirange_static_boundary`.
It seals two noncontiguous ranges belonging to one atlas body:

- `0x0039d580`: 137 bytes, 46 instructions, range SHA-256
  `98edd5e264a7f1418f99230107c71b0b73b6548eb6fe58ef8fc2a1109206a995`.
- `0x0039d61f`: 27 bytes, 11 instructions, range SHA-256
  `ab46e67da4115aebf6a5313ddc6cb66c1c70f6ddaf8e4cf5951e10f55f884990`.

The joined body is 164 bytes with SHA-256
`1f4270f944215528deb2ae971345d562d784bd50acc000041cce365911b5ea67`.
Its custom union CFG has 57 nodes / 57 edges and canonical SHA-256
`9f88252951d61c605a8deea0eb6e3e9cf1e85453e1515aded9c62b5539214d94`.
Conditional branches at `0x0039d5c9` and `0x0039d5e3` each preserve their
first-range fallthrough and cross-range successor `0x0039d61f`. The `RET`
instructions at `0x0039d608` and `0x0039d639` are terminal; no CFG edge is
invented across the undeclared gap.

The complete outgoing direct-edge partition contains opaque calls
`0x0039d5bf -> 0x0039d640` and `0x0039d5d9 -> 0x0039d530`. Those targets are
sealed by atlas identity and remain the next decompile frontier. Indirect
controls and the all-eight-register `FF D0..D7` call audit are empty. The
pinned direct-call census has no direct Lua record for this entry, and absent
local `call r32` syntax yields no staged Lua record without classifying an
unknown dynamic target.

Seven typed PE-address operands are complete: six immediate operands and one
absolute-memory operand. The immediates cover two opaque pushes, two call
targets, and the two cross-range conditional targets. The absolute-memory read
at `0x0039d59c` is operand index 1 and names VA `0x00893f28` / RVA
`0x00493f28` in file-backed writable `.data`. Four separate segment-qualified
memory operands occur at `0x0039d58f`, `0x0039d5aa`, `0x0039d5fa`, and
`0x0039d62b`; they retain exact `FS:[0]` syntax and access/index facts while
remaining excluded from the PE absolute-memory class.

The pointer parent exactly cross-joins the residual artifact's sole deferred
row, `0x00372a53 -> 0x0039d580`. The exhaustive operand scan covers 25,312
functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly
one target reference survives: that immediate `E8` call from sole owner
`0x003729b0`; other-address and absolute-memory reference classes are empty.
Canonical owner, target-owner, and target-reference partition SHA-256 values
are `48a52d8519a9fcf7342f56530716af793f15fc620eddf0b856c0f303f37b93b6`,
`99510bf1ab711cd75f2eae4ec0f11de440eeb945b4d792956e64debdff48a1b2`,
and `82cbfb9dd0e25c2b8393c971ab66eb3c4de7b419718b89c1036ae18a164698c9`.

The artifact's pretty-printed file SHA-256 is
`ecf806bea49d116e0dd785d5d22aab4a769b51634efd1545acefa303d5c17778`;
its canonical JSON SHA-256 is
`a19a16ff5b999872acba98381163dc7d67113864ff508454d63162aa719e1c4e`.
Publication validates one locked point-in-time snapshot, rejects writer
contention and out-of-root destinations, preserves differing existing
evidence, and cleans failed private publication. Relationship membership,
analysis labels, decoded syntax, PE addresses, and `FS:[0]` spelling do not
prove purpose, ABI, inputs or outputs, exception behavior, runtime reachability,
execution order, state mutation, success, normal return, data contents,
un-atlased references, or Lua-side behavior.

## Native query pointer-target multi-range direct-callee pair static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.py`
canonical-pins the multi-range receipt, rejoins both of its outgoing opaque
calls, and seals their two target bodies without assigning either a source
name or purpose.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --multirange-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --multirange-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary`.
It seals two complete single-range atlas bodies:

- `0x0039d530`: 67 bytes, 33 instructions, body SHA-256
  `e2091fa15d6c96ccd134af2a889036e32422bcca28ff80076dc78453ad534f3b`,
  atlas-record SHA-256
  `8bf9de6d5005bace77c5efac9dc74cf7c7189a6892d9c823af9a02a697eed765`,
  and a 33-node / 36-edge CFG with canonical SHA-256
  `f189c9abc78a31c21e1b5e479382105374ab05508d05b181cedd61083d3999cb`.
- `0x0039d640`: 49 bytes, 19 instructions, body SHA-256
  `722744bdeb5185942d2f7905fe9b7988f786d2e7c22cf081747858f79cafea03`,
  atlas-record SHA-256
  `e07de0003b517cac5faf02a21e32552db3980edb296719910d04db79d6e59597`,
  and a 19-node / 19-edge CFG with canonical SHA-256
  `94c13ceee9fdf0c3d9feeb6664abca7380f97df101a86dcc5265e12461bee80e`.

The first CFG retains conditional successors at `0x0039d54f`, `0x0039d559`,
`0x0039d562`, and `0x0039d56a`, with terminal `RET` at `0x0039d572`. The
second retains conditionals at `0x0039d64e` and `0x0039d661`, with terminal
`RET` sites `0x0039d653` and `0x0039d670`. Each body-local CFG hash is derived
from and exactly rejoins its emitted graph object.

The complete local PE-address partition contains those six conditional-target
immediates, all in file-backed nonwritable `.text`. Outgoing declared direct
edges, opaque indirect controls, all eight `FF D0..D7` register-call buckets,
segment-qualified memory, direct Lua calls, and locally evidenced staged Lua
dispatches are empty.

The exact parent rows are `0x0039d5bf -> 0x0039d640` and
`0x0039d5d9 -> 0x0039d530`, both from owner `0x0039d580`; every instruction,
source/target atlas identity, and normalized Ghidra edge cross-joins the
multi-range artifact. The exhaustive scan decodes all 25,312 functions,
25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions while checking both
immediate and pure absolute-memory operands. Exactly those two immediate `E8`
references survive from the sole owner. Owner, target-owner, and
target-reference partition SHA-256 values are
`751468fb4a47b8885547c9880c5a755f2b225f6c2f8253acc56f8231830bb5d6`,
`73f08fc635b2768f2e4fad7baf1861126489488faf00af74b8ef36d9c86a3ce0`,
and `4bc97f58b81bf1a9d3f70d3054f3df61718b7bed2d090b3cd63ac71f97716339`.

The artifact's pretty-printed file SHA-256 is
`bffdbec3554c1969563d4ac235a2e7d150aff311b5b277a31a9f413a3b5094e2`;
its canonical JSON SHA-256 is
`c479ae8d802d848877f8fd57475d8909e0fe2129d25182996d16f599b6cbaf8c`.
Publication uses the immutable locked writer with destination restriction,
existing-content preservation, contention defense, and failed-private-output
cleanup. Relationship membership, adjacency, decoded controls, PE addresses,
and analysis labels do not prove semantic kinship, purpose, ABI, inputs or
outputs, runtime reachability, execution order, state mutation, success,
normal return, data contents, un-atlased references, or Lua-side behavior.

## Native query pointer-target residual-set callee static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.py`
canonical-pins the residual direct-target-set receipt, rejoins its two exact
transfers to `0x003574ca`, and seals the complete target body without assigning
a source name, security purpose, or runtime behavior.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --residual-direct-target-set-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary`.
It seals the complete 17-byte body at `0x003574ca`, all four instructions, body
SHA-256
`5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375`,
atlas-record SHA-256
`931454ae86cb6a227c6182c1abea3b232ee77a68a443b5a98f358f2418ff44b0`,
and a 4-node / 3-edge body-local CFG with canonical SHA-256
`96b4b9365583495d1aa25d002d4833a064caf3792125584a8a6916bda9eb1a9d`.
The graph retains an `F2`-prefixed conditional at `0x003574d0`, terminal return
at `0x003574d3`, and external unconditional transfer
`0x003574d5 -> 0x00357b6a`; all three remain opaque BND-prefixed syntax rather
than claims about prefix semantics or target behavior.

The complete PE-address partition contains one absolute-memory read of
VA `0x00893f28` / RVA `0x00493f28` in file-backed writable `.data`, plus two
file-backed nonwritable `.text` immediates. Indirect control, all eight
`FF D0..D7` register-call buckets, segment-qualified memory, direct Lua calls,
and locally evidenced staged Lua dispatches are empty. The opaque outgoing
target at `0x00357b6a` rejoins its 251-byte atlas record without sealing that
target's behavior.

The exact residual parents are `0x0037298a -> 0x003574ca` via `E8` and
`0x0037299d -> 0x003574ca` via `E9`, both from owner `0x00372970`. Every
instruction and source/target atlas identity cross-joins the prerequisite
receipt. The exhaustive scan decodes all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 1,794 references survive
from 1,620 owners: 1,790 standard `E8` calls, three `F2 E8` calls, and the one
parent `E9` address use. Owner, target-owner, and target-reference partition
SHA-256 values are
`2496424b11c54f2dc558861a9469e4364f470a1b373cb93ed0b00eb4944790de`,
`e581d35f505204c2623a22d21e63fa5852d323a9e59ac2248ad6b681a178bfbb`,
and `64e5b02dda9ed08d40341ce46043a78eb705724bdf057ad885d59ef36feb993e`.

The artifact's pretty-printed file SHA-256 is
`548580d0fee7d612fe16bfe10b567ffd2c8d9a6add9cfd965a75c48c22123c2b`;
its canonical JSON SHA-256 is
`8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1`.
Publication uses the immutable locked writer. Relationship membership,
analysis labels, decoded controls, BND-prefixed syntax, and PE addresses do
not prove security or cookie purpose, source identity, ABI, runtime
reachability, execution order, termination, state mutation, success, normal
return, data contents, un-atlased references, or Lua-side behavior.

## Native query pointer-target residual-set callee external-target static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.py`
canonical-pins the relationship-only external target of the preceding callee
receipt, independently rejoins the exact `F2 E9` parent, seals its full body
and enriched CFG, and scans every atlas operand for its complete entry frontier
without assigning a source name, purpose, ABI, or runtime behavior.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary`.
It seals complete relationship-only target `0x00357b6a`: 251 bytes, all 56
instructions, body SHA-256
`0a7f470e5151d95873547c1201fe9ad8d4c502d6afc9b530de59d9390eb9c0ed`,
atlas-record SHA-256
`324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074`,
and a 56-node / 55-edge enriched CFG with canonical SHA-256
`020e22523160d01f527e80e62320f1052dc8654755d8aee3b8a88ae4dcc14048`.
The `CD 29` at `0x00357b81` is a terminal opaque interrupt-syntax node only;
it does not claim runtime interruption or termination semantics.

The two outgoing opaque direct edges are `E8 18 50 04 00` at
`0x00357b75 -> 0x0039cb92` (instruction SHA-256
`53a83b7d8c828fb30d1db99cb34f3ef39a9efff5068be6a8a626d05b2323b8df`)
and `E8 E1 FE FF FF` at `0x00357c5c -> 0x00357b42` (instruction SHA-256
`d26d2f0423b8246000842d5f509221ff9bd0a727fd2fdbe6dfd975e060afd344`).
The complete PE-address partition has four immediates and 24 pure
absolute-memory operands in writable `.data`: 21 writes and three reads.
Exactly six records are file-backed and 22 are explicitly virtual-only.
`call r32`, indirect controls, BND-prefixed control syntax,
segment-qualified memory, direct Lua calls, and locally evidenced staged Lua
dispatches are empty.

The predecessor join is solely `F2 E9` at `0x003574d5`, from owner
`0x003574ca` to `0x00357b6a`; it is also the sole all-atlas target reference
(one reference / one owner, `other_address`). The exhaustive scan covers all
25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions.
Owner, target-owner, and target-reference partition SHA-256 values are
`2a2416dd95714b643e9479120de7fa221ca334afb358d3c3ebed2cfd155be7ba`,
`2947e96c511745d6e8cdeec79be647a470829e7aad9ea2156e72a2894370e492`,
and `c8390fdbf8e42e8a1fa6256377a5ddb23304a651eae818eaebf2a3f23a5c31bf`.

The artifact's pretty-printed file SHA-256 is
`366bbfcf22cf6ed4dd667308336036191651c4d6dba3d48e6ae51271b66998c6`;
its canonical JSON SHA-256 is
`0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9`.
Publication uses the immutable locked writer. Relationship membership, analysis
labels, decoded syntax, the `CD 29` terminal node, and PE addresses do not
prove purpose, source identity, ABI, runtime reachability, execution order,
interrupt or termination behavior, state mutation, success, normal return,
data contents, un-atlased references, or Lua-side behavior.

## Native query pointer-target residual-set callee external-target import-thunk static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.py`
canonical-pins the predecessor's first opaque direct target as a
relationship-only PE import-thunk boundary, independently rejoins its exact
parent, seals its one-instruction body and CFG, validates raw PE32 import-table
metadata, and scans both the complete target frontier and all-atlas uses of the
referenced IAT slot without assigning behavior, ABI, or runtime semantics.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary`.
It seals complete relationship-only target `0x0039cb92`: the one 6-byte
`FF 25 10 60 7D 00` instruction, body SHA-256
`247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7`,
atlas-record SHA-256
`495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e`, and
a 1-node / 0-edge `indirect_jump` CFG with canonical SHA-256
`29e8bc268788c4dad137925a79b4350355d7f7db2dd2666bbc21399dd5bce60c`.
It is not a return; runtime target, execution, and OS semantics are opaque.

The sole local PE operand is a file-backed, nonwritable `.rdata`
absolute-memory read at VA `0x007d6010` / RVA `0x003d6010`. Raw PE32 import
metadata uniquely binds its IAT slot to `KERNEL32.dll!IsProcessorFeaturePresent`
(hint 772, no ordinal), but this is metadata only. It seals the 220-byte import
directory (10 descriptors, 342 named imports, zero ordinal imports, 139
KERNEL32 rows). The exact descriptor, ILT, IAT, and hint/name record SHA-256
values are respectively
`fe01ec3285fd8be5c0857ae597b2ac4a14de3579860f5f3577a6bdbe8595bc10`,
`4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61`,
`4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61`, and
`bd0a4eda3c3cad901506880438be40e8c7fe64cb99de20e10c67759b071b7f47`; the
import-directory SHA-256 is
`788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65`.

Outgoing direct edges, direct/staged Lua, `call r32`, BND-prefixed controls,
segment-qualified memory, and interrupt syntax are empty. The predecessor
parent is `E8` at `0x00357b75`. The complete target frontier is exactly six
`E8` calls from six owners. Its all-atlas IAT-slot scan finds exactly one use,
this `FF 25` instruction. Both scans cover 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Owner, target-owner, and
target-reference partition SHA-256 values are
`1bbecba81a7d7aa4aeca7f1f710d6f01f560569ffa80408e47615ced30e2abcd`,
`3a8c2764b1ef2d34109ba3afefbceac6055183a06bf28065f29b231f54dd0f8c`, and
`4ac37284ab3f41c7661c27432c2e89564f73e16913fa0f183b564f6d2330604e`.

The artifact's pretty-printed file SHA-256 is
`91397015cb9d8cd74fe2f18d648060c1e8cb28baa6b79f15f39e55ff77e3b71f`; its
canonical JSON SHA-256 is
`af117e253c45140863acc378051d6b5b1eba37458337aad43be6ef22d2589654`.
Publication uses the immutable locked writer. Its formerly retained sibling
`0x00357b42` is sealed by the boundary below. Relationship membership,
analysis labels, import metadata, decoded syntax, and PE addresses do not
prove purpose, source identity, ABI, runtime reachability, target resolution,
execution order, state mutation, success, normal return, data contents,
un-atlased references, or Lua-side behavior.

## Native query pointer-target residual-set callee external-target second-callee static boundary

`scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.py`
canonical-pins the predecessor's second opaque direct target as a
relationship-only native boundary, independently rejoins the exact parent,
seals its complete body and CFG, validates four raw PE32 import bindings, and
closes the complete entry and IAT-slot operand frontiers without assigning
behavior, ABI, source identity, or runtime semantics.

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.json

python -X utf8 scripts/itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --predecessor-static-boundary data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.json
```

The artifact has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary`.
It seals complete relationship-only target `0x00357b42`: 40 bytes, all 12
instructions, body SHA-256
`5a4568c1047a793bff70d7632cc28b29500160dea29a7a4b913c8416835bee26`,
atlas-record SHA-256
`c3417b9783a2a113a7f51883f10fd57557b7457ca184638a679cf15ac7ed863e`,
and a 12-node / 11-edge CFG with canonical SHA-256
`b3d334286def4ca119c59b70f91b17aa46c35b9737edf5088bf755b3f43e0b39`.

Four `FF 15` call-fallthrough syntaxes read file-backed, nonwritable `.rdata`
IAT slots. Raw PE32 metadata uniquely binds them to
`KERNEL32.dll!SetUnhandledExceptionFilter` (RVA `0x003d60e4`, hint 1189),
`UnhandledExceptionFilter` (`0x003d6018`, 1235), `GetCurrentProcess`
(`0x003d60f0`, 448), and `TerminateProcess` (`0x003d6014`, 1216), all named
and non-ordinal. These are metadata-only bindings. The exact 220-byte import
directory has ten descriptors, 342 named imports, zero ordinal imports, and
139 KERNEL32 rows. Exact mode rereads and hashes the descriptor, ILT, IAT,
hint/name, and library spans for every binding.

The predecessor parent is `E8 E1 FE FF FF` at `0x00357c5c`. The complete
target frontier contains exactly that call plus `E8 05 FE FF FF` at
`0x00357d38`, from two distinct owners. Owner, target-owner, and
target-reference partition SHA-256 values are
`952f4d8d2d4027d45635f916a9f0160b633762f836754533bbb06ba29ae6ec3c`,
`ac04221eb3f1206725537a9fa5a263ad86b263e4d28dd8139f387fd294dc4614`,
and `0a36c89948e227a42750480cf04dbb59625da7d8d1437454a2e68ca4beade141`.
Four independent IAT-slot scans close respectively 3, 3, 5, and 13 uses for
RVAs `0x003d6014`, `0x003d6018`, `0x003d60e4`, and `0x003d60f0`. The final
set contains 12 `FF 15` calls and one `8B 3D` absolute-memory read. Each scan
checks both immediate and pure absolute-memory operands across 25,312
functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions.

Outgoing direct calls, direct/staged Lua, `call r32`, BND-prefixed controls,
segment-qualified memory, and interrupt syntax are empty. The artifact's
pretty-printed file SHA-256 is
`5ccb1830fe36c58579b35089c68b84f0eb34bd5303eab72c09d4ed6b8b3096d2`;
its canonical JSON SHA-256 is
`f82310c91d26d3580458decdd70450c130f965ea53134cf0a383b7f9e5ea56d4`.
Publication uses the immutable locked writer. This branch's direct-target
frontier is closed. The retained `___raise_securityfailure` analysis label,
relationship membership, import metadata, decoded syntax, and PE addresses do
not prove semantic identity, security, exception or termination behavior,
purpose, source identity, ABI, runtime reachability, imported-function
execution, state mutation, success, normal return, data contents, un-atlased
references, or Lua-side behavior.

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
