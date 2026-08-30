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
`147feaba792a06da19fa12876d0b58be4633f5ae917f243e447868d6fbbf80f1` and
`9f8739fe4a5c3bcfb9f10aeda9faf3333c96b3ea9ee130a00538aef87ce6dee5`.
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
fail closed. Three production adapters accept the direct-Lua-call, immediate
C-closure callback, and setfield-publication censuses. Each rebuilds and
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
