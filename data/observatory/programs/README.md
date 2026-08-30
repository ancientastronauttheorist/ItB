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
`5933a073d0797a4d3dad9459a4cc320b6a139b934cc139dbb3f940d12cfa26c8` and
`7eeac18e0d9a8efe85f87e5e8d392ead3fdf70b958e683a4d86b13ff7f2cbd07`.
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
fail closed. Two production adapters accept the direct-Lua-call and immediate
C-closure callback censuses. Each rebuilds and canonical-compares its complete
evidence chain against the exact executable once per source artifact per
accounting build. They derive only `lua_api_consumer` and
`cclosure_callback_target`, respectively; neither can support `none`, another
role, or any ownership, reference, semantic, boundary, or exclusion dimension.
The empty registry therefore still leaves every function at L0.

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
