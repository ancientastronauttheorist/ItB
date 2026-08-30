# Into the Breach full-decompile program

## Mission

Recover a reviewable, build-keyed description of every first-party code and
data surface required to explain the behavior of Into the Breach, then turn
that description into independently testable semantic specifications and, when
useful, clean-room implementations.

This expands the focused Engine Observatory. The Observatory intentionally
answered solver-blocking questions; this program adds a whole-program
denominator and accounts for every subsystem, including code that does not
currently affect the achievement bot.

“Full decompile” does not mean publishing a binary dump or bulk proprietary
pseudocode. Local analysis may use the owner's installed game and a private
Ghidra project. Git stores tools, build identities, normalized facts, analyst
claims, clean-room specifications, tests, and independently written code.

## Canonical target

The initial target is the currently installed Windows build:

| Field | Value |
|---|---|
| Steam app | `590380` |
| Steam build | `13725832` |
| Depot manifest | `590381 / 8335438558621014449` |
| Executable | 32-bit x86 PE, `Breach.exe`, 5,530,112 bytes |
| Executable SHA-256 | `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9` |
| Inventoried scripts tree | 305 files: 301 manifest files plus four local Mod Loader overlay/backup files |
| Shipped maps | 377 inventoried files |
| Resource archive | `resources/resource.dat`, 355,249,205 bytes, SHA-256 `fd933aa7d13fe02a9ea577eb100c779f053734816e6c87abae863ae1c9efa4d5` |

The accepted owner installation is not claimed to be a pristine Steam depot:
it contains the normal local Mod Loader integration. The read-only baseline on
2026-08-30 matched the sealed post-capsule inventory at all 689 then-inventoried
entries, with zero changes or omissions. The full-decompile baseline additionally
seals `resource.dat`, bringing the exact inventory to 690 entries. A clean-depot
inventory can be added later without overwriting or weakening this owner-build
provenance.

The resource archive has a deterministic metadata grammar and 2,854 validated
entries (2,703 PNG, 138 custom font records, and 13 TTF files). Its payloads
remain external; paths, types, extents, and hashes can be inventoried without
publishing assets. Twelve plaintext OpenGL shader/header files and the FMOD
bank/native interfaces now have separate exact-build metadata censuses; audio
payload decoding and runtime behavior remain outside those census claims.

Third-party libraries (`SDL2`, Lua 5.1, FMOD, Steam API, and the VC runtime) are
identified and interface-mapped but excluded from first-party semantic
coverage. They have their own upstream sources and licenses.

## Coverage ladder

Each native function, Lua function, map/data grammar, and subsystem advances
through explicit levels:

| Level | Meaning |
|---|---|
| L0 — Located | Stable build identity and address/source location exist. |
| L1 — Bounded | Extent, byte/source hash, ownership, and immediate references are recorded. |
| L2 — Classified | Purpose, subsystem, inputs/outputs, and native/Lua boundary are identified. |
| L3 — Decompiled | Control flow, state reads/writes, calls, constants, and failure paths are understood well enough to write an independent semantic description. |
| L4 — Specified | A clean-room executable specification or conformance vectors cover the behavior. |
| L5 — Reimplemented | Independently written Python/Rust/Lua code implements the specification. |
| L6 — Verified | Differential or runtime evidence demonstrates conformance on a declared domain. |

An item may instead be explicitly classified as third-party, compiler/runtime
scaffolding, unreachable for the shipped build, duplicate/thunk, or data-only.
Exclusion is an accounted result, not a silent gap.

The decompilation milestone is complete when every first-party native function
and shipped Lua/map surface is at L3 or has a reviewed exclusion, every global
state family has a typed ownership/lifecycle description, and every subsystem
entry point is connected in the call/binding graph. A complete independent
game recreation is a later L5/L6 milestone, not something function discovery
alone can claim.

## Publication and provenance rules

- Never commit game executables, DLLs, assets, copied machine-code bytes,
  disassembly listings, bulk Ghidra pseudocode, or reconstructed proprietary
  source.
- Keep Ghidra projects, raw exports, temporary decompiler text, and local game
  copies under `.local_decompile/` or another ignored directory.
- Commit only normalized addresses, hashes, call/reference facts, concise
  semantic claims, independently authored specifications, tests, and source.
- Pin every native claim to platform, architecture, executable hash, build,
  inventory, tool version, and evidence class.
- Separate facts, inferences, and hypotheses. A Ghidra name or boundary is not
  automatically a semantic fact.
- Validate static interpretations dynamically before using them as simulator
  truth when the behavior can affect live play.
- Preserve exact experiment cleanup receipts and never leave diagnostic hooks
  active in the ordinary game installation.

## Workstreams

### A. Target and whole-program atlas

1. Maintain owner and pristine-depot identities independently.
2. Export every Ghidra-discovered native function, discontiguous body range,
   analysis name, body hash, and Ghidra-declared direct internal call edge.
3. Measure discovered executable-byte coverage and unresolved call sites.
4. Re-run the export after every material Ghidra labeling/type pass so progress
   is content-addressed and reviewable.

`scripts/ghidra/ExportItbProgramFacts.java` and
`scripts/itb_program_facts.py` implement the first atlas pipeline. The output is
strictly verified against the exact PE and lives under
`data/observatory/programs/`.

### B. Shipped Lua, maps, shaders, and resource census

1. Maintain the compiler-verified complete function, environment-identifier,
   callback, and static-load census for every accepted Lua-form owner-build
   source. The current artifact compiles 529 chunks without executing them,
   accounts for 915 function prototypes, and names nine statically unrouted
   files.
2. Join unresolved environment/member candidates and loader assumptions to
   independently recovered native registration and bootstrap descriptors.
3. Maintain the strict, non-executing grammar and structural/domain census for
   all 376 map-data chunks, joined to the separately scoped `maphelper.lua`
   bootstrap evidence.
4. Validate `resource.dat` structurally and inventory record paths, types,
   extents, and payload hashes without committing payload bytes.
5. Maintain the exact non-executing lexical/interface census for all 12 OpenGL
   shader/header files and the metadata-only census for all five FMOD banks,
   both FMOD DLL export/version surfaces, and the executable import/literal
   interface.
6. Join Lua definitions and call sites to native registrations and the program
   atlas.
7. Mark localization, presentation-only declarations, and dead aliases without
   confusing source indexing with behavior verification.

### C. Native state and subsystem reconstruction

Classify atlas functions into at least:

- process/bootstrap and Lua binding;
- game/campaign/profile/achievement state;
- Board, Pawn, SkillEffect, animation, and event scheduling;
- player action legality and execution;
- enemy planning, spawn selection, and RNG;
- mission/environment/final-island flow;
- save/profile serialization;
- UI/input/windowing/rendering;
- audio; and
- platform/Steam integration.

For each subsystem, recover object layouts, ownership, state transitions,
registrations, virtual dispatch, serialization, and error paths before writing
an L3 semantic specification.

### D. Dynamic conformance laboratory

Reuse the Observatory's matched controls, hardware observers, Lua callback
traces, exact-build gates, state manifests, and cleanup protocol. Dynamic
experiments should answer a named static ambiguity or validate a bounded
specification—not merely collect activity.

### E. Clean-room reconstruction

Promote verified semantics into independently written modules. The current Rust
solver is already a strong combat reconstruction, but its coverage must be
measured against the atlas instead of treated as a proxy for the whole game.
Rendering and proprietary assets can remain external compatibility surfaces
until core engine semantics are reconstructed.

## Milestones

### M0 — Reproducible denominator

- [x] Exact owner-build inventory and executable identity.
- [x] Stable read-only post-experiment installation baseline.
- [x] Whole-program Ghidra export format.
- [x] Strict normalization and executable verification tooling.
- [x] First normalized atlas exported from the exact-build Ghidra 12.1.3
  project and independently verified: 25,312 functions, 25,490 body ranges,
  86,498 direct internal calls, and 3,735,718 unique discovered function bytes.
  Those declared bodies cover 92.99% of file-backed executable-section bytes;
  this is an auto-analysis body-coverage baseline, not proof of complete
  function discovery or semantic-decompilation progress. The export also
  records 18,477 computed or unmapped call targets as unresolved.
- [ ] Add a pristine-depot inventory when it can be obtained without risking
  the owner's working installation.

### M1 — Complete surface census

- [ ] Classify every atlas function at L0/L1.
- [x] Produce and independently verify the exact-owner-build compiled Lua
  function/environment census: 529 chunks, 915 functions, 1,444 total
  prototypes, 173,619 instructions, 2,686 environment identifiers, all 757
  indexed callback definitions cross-checked, and all accepted/excluded source
  files accounted. Its load model has 523 claim-labeled edges: 145 compiler/
  source-derived facts and 378 explicit host assumptions. The model covers 520
  accepted chunks and explicitly leaves nine unrouted.
- [ ] Recover the complete native Lua-registration/bootstrap graph and resolve
  the census's host candidates, computed globals, loader assumptions, dynamic
  code generation, and runtime reachability.
- [x] Produce and independently verify the exact-owner-build map-data grammar
  census: all 376 chunks strictly parsed without execution, 8,915 unique
  in-bounds explicit tile records, ten tile schemas, 25 zone keys, and 32 tag
  values. Per-map coordinate layouts and raw source remain outside Git;
  numeric field meanings and native consumer behavior remain explicit gaps.
- [x] Produce and independently verify the metadata-only `resource.dat`
  census: 2,854 contiguous unique records, with per-payload hashes and no asset
  bytes committed.
- [x] Produce and independently verify the metadata-only plaintext shader
  census: all 12 files and 4,087 bytes sealed, eight entry points, 48 interface
  declarations, seven preprocessor symbols, nine texture calls, and four
  discard sites, with raw source and render semantics explicitly excluded.
- [x] Produce and independently verify the metadata-only FMOD bank and
  native-library interface census: five exact banks totaling 168,821,378
  bytes, 25,979 bounded RIFF nodes, 689 recursive `WAV ` chunks, four `FSB5`
  signatures, two version-`1.10.2` DLLs with 1,429 named and zero ordinal-only
  exports, 22 named executable imports, and all five bank basename literals.
  Event/string paths, payload bytes, codecs, samples, recursive topology, and
  runtime semantics remain explicitly excluded.
- [ ] Establish subsystem ownership and exclusion counts.

### M2 — Core runtime model

- [ ] Process/bootstrap and Lua registration graph.
- [ ] Core object layouts and ownership.
- [ ] Event/effect/animation scheduler.
- [ ] Save/profile serialization and versioning.

### M3 — Complete game rules

- [ ] Player action legality and execution.
- [ ] Enemy planning and spawn behavior beyond the existing bounded cases.
- [ ] Mission/environment and final-island transitions.
- [ ] Campaign economy, pilots, upgrades, achievements, and run generation.

### M4 — Presentation and platform shell

- [ ] UI state machine and input routing.
- [ ] Rendering/resource interfaces.
- [ ] Audio interfaces.
- [ ] Steam/platform services and error behavior.

### M5 — Independent conformance build

- [ ] L4 specifications for every first-party subsystem.
- [ ] L5 clean-room implementations where required for a standalone engine.
- [ ] Differential suites and declared L6 conformance domains.
- [ ] Independent boot-to-credits run using legally supplied external assets.

## Working cadence

Keep commits small and durable. A normal tranche is:

1. sync and verify the exact target;
2. export or investigate one non-overlapping surface;
3. record facts and explicit gaps;
4. add a validator or regression before promoting a claim;
5. commit the tool, evidence, specification, and tests together; and
6. push the branch immediately.

Never mix live-run artifacts or unrelated user changes into decompilation
commits. Raw local analysis is reproducible working state; normalized evidence
and clean-room specifications are the durable project record.
