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
`data/observatory/programs/`. `scripts/itb_native_function_accounting.py`
builds a separate exact one-to-one review overlay; the atlas remains immutable
and every semantic promotion must come from a hash-pinned analyst registry and
exact-build repository evidence. `scripts/itb_native_lua_direct_calls.py`
independently decodes every atlas body range and publishes exact direct
`lua5.1.dll` IAT-call relations without treating those relations as exclusive
semantic roles. `scripts/itb_native_lua_cclosure_callbacks.py` then resolves
only the exact immediate callback arguments passed at direct
`lua_pushcclosure` sites, and
`scripts/itb_native_lua_cclosure_setfield_publications.py` proves the bounded
subset immediately stored through one exact `lua_setfield` grammar.
`scripts/itb_native_lua_cclosure_table_setter_publications.py` then consumes
only that artifact's unmatched frontier and proves the bounded subset passed
directly to `lua_settable` or `lua_rawset`.
`scripts/itb_native_lua_cclosure_indirect_settable_publications.py` proves the
three staged-register `lua_settable` paths with an exact CFG, dominance, and
all-path ESI-preservation proof, while
`scripts/itb_native_lua_cclosure_terminal_dispositions.py` independently
classifies the two single-result returns and one registry-reference holder.
Accounting protocol schema 2 represents native/Lua roles as composable
positive facts rather than a mutually exclusive enum.

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

- [x] Establish an exact one-to-one L0 accounting overlay for all 25,312 atlas
  functions. The initial empty review registry leaves every ownership and
  subsystem value unknown, records zero L1/L2 promotions and zero exclusions,
  and keeps 685 Ghidra-thunk flags plus 26 repeated-body groups as explicitly
  non-promoting review candidates.
- [x] Independently decode all 25,490 atlas ranges and 3,735,718 body bytes with
  pinned Capstone 5.0.7, yielding 1,153,814 instructions and an exact census of
  4,739 six-byte `FF 15` calls from 1,787 atlas functions to the 54 named
  `lua5.1.dll` IAT slots. This is a positive direct-call relation only; it does
  not claim runtime reachability, negative Lua-use results, ownership, or a
  mutually exclusive registration/callback role. Its accounting adapter
  exact-rebuilds and compares the whole census against the installed executable
  before deriving only positive `lua_api_consumer` support; it cannot support
  absence, another role, or another review dimension.
- [x] Partition all 15 direct `lua_pushcclosure` sites into 13 exact immediate
  callback edges and two unresolved computed arguments. The resolved sites
  identify 11 unique non-thunk atlas entries, include one self-edge, and prove
  real role overlap: all 11 targets directly call Lua imports and three also
  call `lua_pushcclosure`. The artifact does not infer registration names,
  table identities, runtime execution, or targets for computed arguments. Its
  accounting adapter exact-rebuilds the direct-call prerequisite and callback
  census before deriving only `cclosure_callback_target`; the stronger
  `registered_lua_callable` role remains unproven by that callback-only
  artifact.
- [x] Prove the first bounded native Lua publication edges without relying on
  string proximity or decompiler prose. An exact fall-through grammar joins
  three zero-upvalue immediate closures to three direct `lua_setfield` calls in
  caller RVA `0x002e6900`, storing distinct callback RVAs `0x002e6840`,
  `0x002e6880`, and `0x002e68b0` under key `__gc`. Ten other resolved callback
  sites remain explicitly unmatched. This proves static table-field storage,
  not the table's metatable/global identity, runtime reachability, persistence,
  or publication through another setter API.
- [x] Consume the ten-site unmatched setfield frontier with a second exact
  direct-setter grammar. Four more callback sites hand the newly constructed
  closure directly to `lua_settable` (three sites) or `lua_rawset` (one site)
  using signed table indices `-10002` or `-3`; the result has three unique
  callback targets and four builders. The six residual sites remain explicit.
  This proves the closure is the setter value, not the existing stack key,
  destination-table identity, global/module visibility, runtime execution, or
  an indirect-setter path.
- [x] Prove the three staged-register `lua_settable` publications in the
  six-site residual frontier. One exact caller-entry CFG has 260 instructions
  and 265 edges; the `lua_settable` IAT stage dominates every setter and later
  callback, no ESI writer lies on any stage-to-setter path, and alternate atlas
  or declared direct entries into the dominated region are rejected. This
  relies explicitly on the 32-bit Windows cdecl ESI-preservation and atlas-entry
  premises and still does not identify the stack key, table, Lua-visible name,
  runtime execution, or lifetime.
- [x] Recover exact key and destination provenance for all seven direct and
  staged-indirect table publications. Four finite Lua-stack grammars prove
  exact keys `super` (three sites), `__gc` (two), `class`, and `property`; five
  setters address Lua 5.1 `LUA_GLOBALSINDEX`, while both relative `-3` setters
  target freshly created unnamed tables. The deferred `super` proof also
  retains its alternate global `nil` write. These static facts do not prove a
  durable export, semantic identity for either fresh table, runtime execution,
  persistence, or source equivalence.
- [x] Promote the five reviewed `__gc` publication/consumer grammars into an
  executable-rebuilt census. Four conditional bootstrap chains create userdata
  and metatables before metamethod-capable registry stores; the fifth joins the
  raw-cached `luabind.function` helper to its sole decoded direct consumer. The
  artifact seals eight bodies / 1,924 bytes, 667 CFG nodes / 670 edges, 61
  direct and 58 staged Lua calls, 66 semantic points, 49 adjacency proofs, five
  callback identities, and the complete seven-reference central-target scan.
  Staged loads must dominate their calls, and whole-function interiors reject
  alternate atlas or declared-direct entries. The exact five-of-ten claim is
  limited to the normalized immediate-C-closure setter universe and does not
  assert runtime dispatch, finalization, ownership, lifetime, or all native
  `__gc` construction.
- [x] Close the immediate-closure disposition partition for all 13 resolved
  callback sites. In parallel with the indirect-setter proof, an exact terminal
  grammar classifies two closures as the sole conditional Lua callback result
  and one as a registry-referenced closure holder. Together the artifacts prove
  ten static table publications, two single-result returns, and one registry
  holder, with no site silently dropped or multiply classified. The return and
  registry facts do not themselves prove later invocation, ordinary Lua lookup,
  naming, reachability, ownership, or reference lifetime.
- [x] Upgrade the native review ledger to schema 2 with strict `unknown`,
  `none`, and `roles` boundary states plus independently supported,
  non-exclusive positive role atoms. The empty registry still leaves all
  25,312 functions at L0; the representation change does not promote facts.
- [ ] Review exact boundaries, ownership, and immediate references to promote
  every first-party atlas function to at least L1 or record a fact-backed
  exclusion. Reconcile the 281,434 executable-section bytes outside discovered
  atlas bodies, focused boundary extents that do not exactly join an atlas
  body, and 18,477 computed or unmapped call targets without silently changing
  the denominator. The direct-Lua census explains a decoder-backed subset of
  that omitted-call surface but does not rewrite the unchanged Ghidra omission
  counter. The L0 ledger has five production upstream-analysis adapters,
  narrowly limited to binary-reverified positive `lua_api_consumer`,
  `cclosure_callback_target`, `registered_lua_callable`, and
  `registration_builder` support. All three table-publication adapters accept
  only a direct callback aggregate for the registered-callable role or a direct
  caller aggregate for the builder role. The empty registry still promotes nothing,
  and every other assertion fails closed until a kind-specific adapter can
  derive it from independently verified evidence. Closure construction alone
  still does not prove Lua-visible registration, and the broader registration
  graph remains open work.
- [x] Produce and independently verify the exact-owner-build compiled Lua
  function/environment census: 529 chunks, 915 functions, 1,444 total
  prototypes, 173,619 instructions, 2,686 environment identifiers, all 757
  indexed callback definitions cross-checked, and all accepted/excluded source
  files accounted. Its load model has 523 claim-labeled edges: 145 compiler/
  source-derived facts and 378 explicit host assumptions. The model covers 520
  accepted chunks and explicitly leaves nine unrouted.
- [ ] Recover the complete native Lua-registration/bootstrap graph and resolve
  the census's host candidates, computed globals, loader assumptions, dynamic
  code generation, and runtime reachability. The immediate closure frontier is
  now completely dispositioned: ten of 13 sites are static table publications,
  two return the closure as one conditional Lua result, and one stores a
  registry reference in a returned holder. The class-return direct-address
  frontier is now closed: the factory artifact finds only the returned
  callback's producer and no direct native consumer, while the dependent helper
  artifact seals all three callback-side callees and every atlas-decoded direct
  reference to them. The dependent initializer artifact now also seals the
  distinct `0x002eacf0` construction body and proves that its only atlas-decoded
  direct reference is the factory call at `0x002ec302`. Continue with the
  remaining dynamic or indirect consumers, descriptor/bootstrap ownership,
  lifetime seams, and actual runtime reachability without merging conditional
  paths or ABI assumptions.
  The follow-up survey in
  `docs/native_lua_registration_bootstrap_survey.md` now accompanies the
  promoted exact five-site artifact: four conditional userdata/metatable
  construction chains ending in metamethod-capable registry-index assignments, plus the
  raw-cached `luabind.function` metatable helper and its sole decoded direct
  consumer. It also records the exact five-of-ten `__gc` publication partition
  and the stack-preserving initializer/helper seams. The census is now
  normalized and executable-rebuilt; runtime dispatch, ownership, and lifetime
  remain unproved.
  The adjacent registry-holder survey in
  `docs/native_lua_registry_holder_survey.md` also closes a finite declared
  direct-caller frontier for the returned holder: all 46 callers use one
  247-byte relative-offset grammar, read the returned `+4` registry reference,
  and conditionally attempt `luaL_unref` on the original local state/reference
  pair. The raw-lookup state comes from a separate temporary and is deliberately
  not equated with the holder state; ownership, execution, validity, indirect
  callers, and complete lifetime remain unproved. The normalized
  executable-rebuilt census now seals all 47 bodies / 11,469 bytes, 4,177 CFG
  nodes / 4,360 edges, 98 direct Lua calls, 276 register-indirect calls, 1,702
  caller semantic points, and all 46 bounded EBX-use windows. Its all-operand
  atlas scan covers 25,312 functions and proves the only 46 references to the
  producer are the declared immediate `E8` calls. Its canonical JSON SHA-256 is
  `395603c2a163925fc202a5a35791200859313872c242fe5901e4de8c05ab892f`.
  The dependent class-return helper artifact now closes the callback-side
  static helper seam without assigning source-level class semantics. It seals
  helpers `0x002eb140`, `0x002eb560`, and `0x002ec050`: 501 bytes, 190 CFG
  nodes / 201 edges, all 14 direct and six staged Lua calls, a complete
  eight-encoding register-call audit, three literals, and six outgoing native
  edges to five exact targets. Its all-operand atlas partition contains exactly
  six immediate direct calls: five from returned callback `0x002ec110` and one
  explicit alternate `0x002e7970 -> 0x002eb140` edge. The alternate caller is
  reference-only. The artifact's canonical JSON SHA-256 is
  `33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095`.
  The adjacent class-initializer artifact closes the formerly separate
  `0x002eacf0` tranche without assigning source class or lifetime semantics. It
  seals 612 bytes and a 185-node / 191-edge CFG, joins all 20 direct and six
  staged Lua calls under the complete eight-encoding register-call audit,
  exact-reads the three registry keys, and retains two outgoing native calls as
  opaque edge facts. Its all-operand atlas scan finds exactly one reference,
  the factory's conditional `0x002ec302 -> 0x002eacf0` call. The canonical JSON
  SHA-256 is
  `799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9`.
  The initializer's formerly opaque `0x0007c600` edge is now closed by a
  separate, recursively pinned helper artifact. It seals the exact 41-byte
  body and 16-node / 18-edge CFG, records the 24-byte immediate supplied to the
  analysis-labeled `operator_new` target, and partitions all nine atlas
  references as immediate direct calls from nine distinct owners. Nine bounded
  caller windows retain the adjacent `+0` / `+4` zero stores, helper call, and
  returned-EAX store without sealing the full 3,364 bytes of caller bodies.
  The canonical JSON SHA-256 is
  `994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb`;
  allocation success, source type, container, ownership, lifetime, caller
  execution, and runtime reachability remain unproved.
  The initializer's second formerly opaque edge is now closed by a distinct
  assertion-helper static boundary. It seals the exact 72-byte `0x00379cc2`
  body and 29-node / 30-edge CFG, retains four outgoing direct calls as opaque
  native edges, and rejoins the six-instruction initializer predecessor window
  without decoding its two non-writable `.rdata` pointers into source text.
  The exact all-operand atlas scan partitions 881 references from 660 owners;
  every survivor is a five-byte immediate `E8` call, with comparison,
  absolute-memory, and other-address partitions empty. The canonical JSON
  SHA-256 is
  `beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4`;
  analysis labels do not establish CRT identity, dialog/display behavior,
  termination, source equivalence, or runtime reachability. Its first and
  second direct targets are now closed below; two direct targets remain opaque.
  The dependent assertion-helper first-callee boundary canonical-pins that
  receipt and independently rejoins exact edge
  `0x00379ccd -> 0x0038e392`. It seals the exact 63-byte body, all 23
  instruction points, and a 23-node / 23-edge CFG with three terminal `ret`
  points retained as syntax only. Its complete outgoing partition contains
  two opaque native calls at `0x0038e3bc -> 0x00385bcc` and
  `0x0038e3c7 -> 0x00379ef2`; indirect, register, direct/staged Lua,
  BND-prefixed, segment-qualified, and interrupt controls are empty. Three
  absolute-memory operands name writable virtual-only `.data` VA
  `0x008b7534` / RVA `0x004b7534`, and their three exact HIGHLOW relocation
  sites are pinned. Four ordinary immediate operands are retained without
  semantic interpretation. The exhaustive all-operand atlas scan finds only
  the parent immediate `E8` reference from one owner. Its pretty-printed file
  SHA-256 is
  `bc6e195e133fba208b13344aea8e211e44fc57e0399d860af38f2ab9ed3383f0`;
  its canonical JSON SHA-256 is
  `e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0`.
  The `__set_error_mode` spelling remains analysis metadata only; CRT
  identity, ABI, argument/global meaning, runtime execution, effects, child
  behavior, and normal return remain unproved.
  Both of that first callee's outgoing targets are now closed together by a
  dependent paired boundary. It canonical-pins the first-callee receipt,
  rejoins exact edges `0x0038e3bc -> 0x00385bcc` and
  `0x0038e3c7 -> 0x00379ef2`, and seals 35 bytes, all 16 instruction points,
  and two CFGs totaling 16 nodes / 14 edges. The exhaustive all-operand atlas
  frontier contains exactly 479 five-byte immediate `E8` calls: 308 from 202
  owners to `0x00385bcc`, 171 from 148 owners to `0x00379ef2`, 202 unique
  owners, and 350 target-owner pairs. The first target's exact immediate at
  `0x00385bd5` names raw-backed writable `.data` VA `0x008940d0` / RVA
  `0x004940d0`; the matching HIGHLOW site at `0x00385bd6` is the only one in
  either body. Calls `0x00385bcc -> 0x0038edb6` and
  `0x00379ef9 -> 0x00379e77` remain opaque child edges. The pretty-printed file
  SHA-256 is
  `40a83312f9867bcf385e836eb9547398803d8628a29c3d4716aec7ba4c21a493`;
  the canonical JSON SHA-256 is
  `e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378`.
  Analysis-label meaning, source identity, ABI, data contents, runtime
  reachability, behavior, and normal return remain unproved.
  The pair's first outgoing child now has its own dependent static boundary.
  It canonical-pins the paired receipt, rejoins exact edge
  `0x00385bcc -> 0x0038edb6`, and seals range
  `[0x0038edb6,0x0038ee3b)`: 133 bytes, all 53 instruction points, and a
  53-node / 57-edge CFG. Six outgoing immediate `E8` calls remain opaque.
  Three body-local `FF 15` controls are bound through raw import-descriptor,
  ILT, IAT, hint, and import-name syntax to metadata spellings
  `GetLastError` and `SetLastError`; external IAT-consumer closure is not
  claimed. Two absolute-memory operands name raw-backed writable `.data` VA
  `0x00894290` / RVA `0x00494290`, and one immediate names virtual-only
  `.data` VA `0x008b7550` / RVA `0x004b7550`. Six exact HIGHLOW sites and four
  ordinary comparison/data literals are pinned. The exhaustive all-operand
  atlas scan finds exactly six target-entry references from six owners, all
  five-byte immediate `E8` calls. The pretty-printed file SHA-256 is
  `eac8de889925d07bc807f1ec676c143348d2729bc51d6ecbc402f08ca2ef3eab`;
  the canonical JSON SHA-256 is
  `314c5817e3a1560c446853474cc0f86fbf3a8195fb60f48c85822a3ed8aca3bc`.
  CRT identity, ABI, behavior, runtime reachability, child semantics, and
  normal return remain unproved.
  The pair's second child now has a dependent schema-2 static boundary. It
  rejoins `0x00379ef9 -> 0x00379e77` and seals 122 bytes, 43 instruction
  points, and a 43-node / 44-edge CFG. Three outgoing direct edges and two
  indirect controls remain behaviorally opaque. The absolute-memory control
  slot at RVA `0x003d6580` is at the exclusive end of the IAT and belongs to
  raw-backed `.rdata`, not an import. Four PE-address operands, four HIGHLOW
  sites, two ordinary literals, and two incoming references from two owners
  are pinned. The final E8's terminal graph node is a declared-body boundary,
  not a no-return claim. Schema 2 corrects a case-sensitive ESI omission in the
  duplicate native-call audit; the immutable schema-1 receipt remains retained
  and hash-bound by `supersedes`. The standalone validator and writer no longer
  mutate first-child module globals. The active file SHA-256 is
  `9d5def6e41d69c2e2e231110c494f8a9f0e763c51b2df67102a73f133d27c1b5`;
  its canonical JSON SHA-256 is
  `918628e05e4579a40127416853ed5e1af91fa6516e86798a48107a65f433be19`.
  Both immediate pair-child structures are now closed; their callee semantics
  and the whole assertion-helper graph are not. CRT identity, ABI, runtime
  reachability, indirect targets, child behavior, and normal return remain
  unproved.
  The second child's direct-callee frontier now composes all three edges:
  the existing `0x0038edb6` and `0x003574ca` body receipts are joined through
  exact incoming-reference rows, while `0x00379f1f` receives a new 51-byte,
  20-instruction boundary and 20-node / 20-edge CFG. That body has two direct
  native calls, two imported calls, one opaque interrupt, six ordinary
  immediates, two HIGHLOW sites, and 45 incoming references from 45 owners.
  Import metadata and possible interrupt/call fallthrough do not prove
  runtime termination or return. Exact validation rechecks the source caller
  and reused body bytes, new body/import/relocation facts, and complete atlas
  operand scan; reused receipts remain canonical-pinned without rerunning
  their whole original analyses. PE-free validation is explicitly hash-pinned
  receipt consistency, not binary proof. The file SHA-256 is
  `19a5d65db948083b985d0eca8757db5c4663d5892decdef69a1c87fb6b5de9f3`;
  canonical JSON SHA-256 is
  `39a712704c58f0789580ebac647ce13ae23681a1df12f0dc93d549159e37ddeb`.
  The parent's indirect controls, runtime behavior, and ownership/exclusion
  promotions remain open. The two target bodies are now sealed by the
  descendant-pair receipt: `0x0039cb92` is a six-byte, one-instruction import
  jump with no local CFG edge; `0x00379d28` is a 315-byte, 78-instruction body
  with 81 CFG edges. Together they retain five native calls, four import
  controls, 124 explicit operands, and five HIGHLOW sites. Six segment-register
  source operands use ordinary EBP-relative destinations, not segment-relative
  dereferences; decoder access flags and LEA operands do not establish runtime
  memory effects. The complete atlas scan finds eight incoming references
  across six owners (six/six for the thunk and two/two for the larger body).
  Both source edges are rechecked against caller bytes and incoming records.
  The artifact raw SHA-256 is
  `0c7fbea632343e29a05e8e9ec67f695021bbc8154e2bc7d2661e6ac8c859c1bc`;
  canonical JSON SHA-256 is
  `47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b`.
  Imported implementations, context identity, exception behavior, and
  ownership/exclusion proofs remain outside this structural receipt.
  A subsequent leaf-callee receipt rejoins all five native calls from
  `0x00379d28`, reusing `0x003574ca` and sealing `0x003586b6` (eight bytes,
  two instructions) and `0x00370960` (346 bytes, 89 instructions). It records
  103 instruction CFG edges, 157 explicit operands, four HIGHLOW sites and
  159 incoming calls across 122 owners; neither new body has outgoing calls.
  On normal completion, the small body's first instruction clears a 32-bit
  global location through a read-modify-write operation; its global purpose
  remains unknown. A subsequent fill-conformance receipt now supplies an
  independent byte-fill specification and isolated exact-body emulation for
  14,620 positive cases, plus one expected DF-set rejection. All 89 instruction
  nodes and 102 CFG edges are observed across scalar, REP and SIMD vectors.
  This is finite emulation evidence, not proof of all inputs, real-game
  execution, CRT identity or an accounting promotion. See
  `docs/native_fill_conformance.md` for domains, hashes and replay commands.
  A separate caller-fill composition receipt checks the 81-byte prefix of
  `0x00379d28` through exclusive stop `0x00379d79`: adjacent/disjoint 80- and
  716-byte regions, protected slot and saved-state preservation, exact call
  frames and shared 24-byte cleanup. Its 256 prefix cases yield 512 fill
  observations and 128 optional-helper executions. All 25 prefix nodes are
  observed; later stores and whole-caller behavior remain open. See
  `docs/native_caller_fill.md` for finite-domain and static-proof distinctions.
  The following `[0x00379d79,0x00379e20)` slice now has a symbolic store map
  matched to an independent overlay and 256 finite boundary-state replays.
  All 30 instructions, 22 frame stores, one temporary flags write and six
  reads are checked per case. Current pointer/register/flag provenance is
  explicit; the sampled volatile inputs are not claimed reachable through the
  earlier prefix. The first import call, record identity and later behavior
  remain open. See `docs/native_frame_stores.md` for the exact field map.
  A further same-instance composition now reaches exclusive `0x00379e20`
  from owner entry in 256 cases. It independently checks the actual volatile
  register values, last-writer provenance and cleanup flags before applying
  the store overlay. All 55 caller-prefix nodes are observed; the imported
  routines and whole-function return remain open. See
  `docs/native_import_handoff.md` for the composed proof and reproduction.
  A separate compiled x86 SDK probe measures 33 fields, matches the 8/80/716
  byte regions and all 22 frame stores, and retains 162 included-header hashes.
  Its compatibility map preserves the six two-byte selector writes inside
  four-byte SDK fields. This is external layout evidence, without identifying
  the game's toolchain or proving import consumption. See
  `docs/windows_exception_layout.md`.
  The six-instruction import-argument slice now symbolically passes the
  compatible pair at F-808 to the named `UnhandledExceptionFilter` boundary,
  under explicit normal-stdcall-return and caller-frame preservation
  assumptions for the preceding two imports. All three import bindings are
  rechecked against the PE; imported execution and the return tail remain
  open. See `docs/native_import_arguments.md`.
  The final 44-byte, 17-instruction return tail now has 16 Boolean predicate
  partitions and 1,728 integer-model cases, including a newly specified
  four-instruction equality checker. Its 864 direct modeled returns and
  864 open mismatch transfers remain conditional on the third import's
  return contract and protected words; the record buffers may change.
  See `docs/native_return_tail.md` for stack restoration and explicit gaps.
  Leaf-callee raw SHA-256 is
  `0fbc28fb7e55a61538e74d07c667eb39796febe5ee181c345997f5f6180714ea`;
  canonical JSON SHA-256 is
  `1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2`.
  The dependent assertion-helper second-callee boundary canonical-pins the
  assertion-helper parent receipt and independently rejoins exact edge
  `0x00379cdc -> 0x0038c89f`. It seals all six target bytes, both instruction
  points, and a 2-node / 1-edge CFG whose final `ret` remains terminal syntax,
  not a normal-return claim. The declared outgoing-native, indirect-control,
  direct/staged Lua, complete eight-register call, BND-prefixed,
  segment-qualified, interrupt, and non-PE-immediate partitions are empty.
  Its sole PE-address operand is the five-byte `A1` absolute-memory read at
  `0x0038c89f`. VA `0x008b7318` / RVA `0x004b7318` is proven to lie in the
  writable virtual-only tail of `.data`; it has no file offset and its contents
  remain opaque. The exhaustive all-operand atlas scan finds exactly three
  immediate `E8` entry references from three owners. Its pretty-printed file
  SHA-256 is
  `d9ae877fc1f9acb604a566470d0b8c2c1bb471701ef19de0e7c0a170e1287a07`;
  its canonical JSON SHA-256 is
  `ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7`.
  Default-label meaning, source identity, ABI, input/output meaning, `.data`
  contents, runtime reachability, effects, and normal return remain unproved.
  The self-linked helper's analysis-labeled target is now closed by a separate
  operator-new static boundary. It simultaneously revalidates the canonical-
  pinned predecessor evidence and the independently rebuilt whole-atlas
  reference record for exact edge `0x0007c602 -> 0x003574db`, then seals the
  51-byte target body, all 20 instructions, and a 20-node / 22-edge CFG. Four
  outgoing direct calls remain opaque. The complete entry frontier partitions
  1,233 references from 1,050 owners into 1,232 immediate `E8` calls and one
  declared `E9` reference at `0x00357874`; direct and staged Lua calls,
  `call r32`, and retained literals are empty. Its pretty-printed file SHA-256
  is `08cfc38143f47c4b4f737e4638f82495b5bfd22341626a1ee3d7ea66df2005e9`;
  its canonical JSON SHA-256 is
  `d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f`.
  The name remains an analysis label only; allocation semantics, ABI, success,
  ownership, lifetime, size meaning, normal return, runtime reachability,
  source identity, opaque-callee behavior, and computed, indirect, data,
  un-atlased, or Lua references remain unproved. Publication verifies one
  locked point-in-time snapshot, and failed published destinations are
  preserved for inspection rather than deleted.
  The operator-new target's second direct callee is now closed by a separate
  relationship-defined static boundary. It canonical-pins the operator-new
  receipt, independently rejoins exact edge
  `0x003574f3 -> 0x0035848f`, and seals the 28-byte body, all nine
  instructions, and a 9-node / 8-edge CFG. The last instruction is a direct
  call at the declared range end; `direct_call_range_end` records only that
  boundary and does not promote return or callee semantics. The artifact
  retains opaque outgoing edges `0x00358498 -> 0x00358477` and
  `0x003584a6 -> 0x00370dab`, plus the exact non-writable `.rdata` immediate
  pushed at `0x0035849d`. Its complete entry frontier is the one parent
  immediate `E8` call from one owner. Direct and staged Lua calls, the complete
  eight-register call audit, indirect controls, BND, segment-qualified, and
  interrupt partitions are empty. Its pretty-printed file SHA-256 is
  `c427f25ed77f605911ddea747fcda26b44814ca0060f0c4fce3bbffcfe717f25`;
  its canonical JSON SHA-256 is
  `ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856`.
  The default Ghidra name is metadata only; source purpose, ABI, exception
  behavior, runtime reachability, normal return, and callee behavior remain
  unproved. Both outgoing targets are now closed below.
  The dependent first-child boundary canonical-pins that receipt and rejoins
  exact edge `0x00358498 -> 0x00358477`. It seals the complete 24-byte body,
  all six instructions, and a 6-node / 5-edge CFG whose final `ret` remains
  terminal syntax rather than a normal-return claim. The target's declared
  outgoing-native, indirect-control, direct/staged Lua, eight-register call,
  BND, segment-qualified, and interrupt partitions are all empty. Two exact
  immediate operands land in non-writable file-backed `.rdata`; two zero
  immediates are retained separately as non-PE literals. Its complete incoming
  frontier is the single parent `E8` call from one owner. Its pretty-printed
  file SHA-256 is
  `7837f58f2f0b08968e29d42cb0e6da4aa405962e12b8ce956c9c8be187d2abc8`;
  its canonical JSON SHA-256 is
  `a82567f379b942b53f80b1f739a488e7de2637ea39e318f7a928af37900ae262`.
  Analysis-label meaning, source identity, ABI, input/output behavior,
  `.rdata` contents, runtime reachability, effects, and normal return remain
  unproved. With no outgoing native edge, this relationship-defined branch is
  closed.
  The dependent second-child boundary canonical-pins the same predecessor and
  rejoins exact edge `0x003584a6 -> 0x00370dab`. It seals all 110 body bytes,
  45 instructions, and a 45-node / 48-edge CFG. Its sole declared direct edge,
  `0x00370de0 -> 0x003581b3`, canonical-rejoins the previously sealed residual
  target receipt. Opaque indirect controls remain at `0x00370de5` (`call ESI`)
  and `0x00370e0a` (absolute-memory `FF 15`). The latter uses a non-writable
  `.rdata` IAT slot whose raw PE proof binds descriptor 7, thunk 91, matching
  ILT/IAT words and terminators, and the unique parsed `KERNEL32.dll` /
  `RaiseException` row; all names and behavior remain metadata only. Seven
  PE-address operands, seven non-PE immediate literals, and one exact
  `ES:[EDI]` segment-qualified syntax form complete separate partitions.
  Direct/staged Lua, BND-prefixed, and interrupt partitions are empty. One
  exhaustive traversal finds 481 immediate `E8` entry references from 414
  owners; an independent traversal finds three `FF 15` uses of the IAT slot
  from three owners. Its pretty-printed file SHA-256 is
  `e2b04a14adfa5440a1b01f978b8785a48b3f7cf6ed26d59577963a48d4eef365`;
  its canonical JSON SHA-256 is
  `87f650968e7858d1676b51a99b98822846db39577da2ef737d9e8d74f4c251a8`.
  Analysis/import-label meaning, ABI, exception or throw behavior, runtime
  execution, effects, and normal return remain unproved. This closes both
  relationship-defined direct children of the operator-new second callee.
  The operator-new target's smallest supported outgoing callee is now closed
  by a callnewh static boundary. It revalidates both the canonical-pinned
  operator-new evidence and the independently rebuilt exact
  `0x003574e3 -> 0x0038bbc4` reference, then seals 68 bytes, all 30
  instructions, and a 30-node / 31-edge CFG. Two direct native edges remain
  opaque at `0x0038bbd5 -> 0x0038bc08` and
  `0x0038bbff -> 0x003574ca`. The artifact also retains an unresolved
  absolute-memory call through non-writable `.rdata` at `0x0038bbe5`, an
  unresolved `call ESI` at `0x0038bbeb`, and an absolute read from writable
  `.data` at `0x0038bbca`. Its complete target frontier is four immediate
  `E8` calls from four owners; direct and staged Lua calls and literals are
  empty, while the complete eight-register audit contains the one ESI call.
  Its pretty-printed file SHA-256 is
  `5b1651f4b17b3d6531b71a19c828ab4700cebb19f444c5db6d694e5534793449`;
  its canonical JSON SHA-256 is
  `27f7495174094b3d6dca6acd6e9975a4dfa7d349f3bf974d40c3f5acd0b4eb45`.
  The `__callnewh` name is analysis metadata only: allocation, handler, ABI,
  success, ownership, lifetime, callee identity or behavior, normal return,
  runtime reachability, dynamic-target resolution, and source equivalence
  remain unproved.
  The sole direct callnewh-to-query target is now closed by a dependent static
  boundary. It canonical-pins the callnewh artifact, independently revalidates
  exact predecessor `0x0038bbd5 -> 0x0038bc08`, and seals the 70-byte body,
  all 19 instructions, and its 19-node / 18-edge CFG. Four outgoing direct
  native calls remain opaque. The artifact retains one absolute pointer push
  into non-writable file-backed `.rdata`, one read from writable file-backed
  `.data`, and one read from the writable virtual-only tail of `.data`; pointer
  contents and values remain opaque. Its all-atlas entry frontier is exactly
  one immediate `E8` call from one owner. Direct and staged Lua calls,
  `call r32`, and literals are empty. Its pretty-printed file SHA-256 is
  `a0e4913c271166ee3ebd0e429f86161d47f9108c5201d2de6d4219bae8b85263`;
  its canonical JSON SHA-256 is
  `742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705`.
  The `__query_new_handler`, SEH, lock, and security spellings remain analysis
  metadata only; handler/allocation behavior, pointer contents, ABI, success,
  ownership, lifetime, normal return, runtime reachability, source identity,
  and callee semantics remain unproved.
  The query handler's first direct target is now closed by a separate,
  relationship-defined boundary. It canonical-pins the query-handler artifact,
  independently rejoins exact edge `0x0038bc0f -> 0x003584b0`, and seals the
  target's complete 70-byte body, 21 instructions, and 21-node / 20-edge CFG.
  Its all-atlas entry frontier is 66 five-byte immediate `E8` calls from 66
  owners; comparison, other-address, and absolute-memory entry references are
  empty. The body has no direct native edge, Lua call, register call, or
  retained literal. Five opaque syntax records distinguish an absolute
  immediate into file-backed `.text`, an `FS:[0]` memory push, a writable
  file-backed `.data` read, an `FS:[0]` destination write, and a BND-prefixed
  return. Its pretty-printed file SHA-256 is
  `f4d43affe98441996f1d10086438c93136b181665c2039b9b1ae18beb618e6b4`;
  its canonical JSON SHA-256 is
  `b08dc12a2f4951817e4e7c24dbdfc4afec03550c2828d7d14c1d757404517d73`.
  The `__SEH_prolog4` analysis label does not prove purpose, SEH, prolog,
  exception, stack, register, security-cookie, ABI, state mutation, success,
  normal return, runtime execution, source identity, or operand contents.
  The first callee's absolute-immediate pointer target is now closed by a
  dependent relationship-defined boundary. It canonical-pins the first-callee
  artifact, rejoins the exact five-byte push at `0x003584b0`, and seals target
  `0x003729b0`: 358 bytes, all 120 instructions, and its 120-node / 130-edge
  CFG. Eleven exact outgoing native edges remain opaque. Direct/staged Lua
  calls and literals are empty; the full eight-register audit contains only
  `call ESI` at `0x00372a71`. The earlier ESI load at `0x00372a5f` does not
  establish the later call target across intervening direct call
  `0x00372a6c`. Six exact PE operands retain only `.data`/`.rdata` address,
  access, and section metadata. The all-atlas frontier is exactly three
  identical immediate pushes from three owners, all `other_address` uses, with
  direct-call, comparison, and absolute-memory partitions empty. Its
  pretty-printed file SHA-256 is
  `0fc22f514989853df44f285396b4f59683ee94f703fcc355b566ad6518783c4d`;
  its canonical JSON SHA-256 is
  `41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349`.
  The `__except_handler4` spelling remains analysis metadata only; purpose,
  exception or handler behavior, stack, register, security, ABI, target
  identity, state mutation, success, normal return, runtime execution, data
  meaning, and Lua-side references remain unproved.
  Four direct targets are now sealed as a layout-only adjacent cluster over
  `0x00378b3e..0x00378b9e`: 96 bytes, four distinct bodies, 51 instructions,
  and four CFGs totaling 51 nodes / 47 edges. All five parent `E8` records are
  cross-joined to the independently rebuilt whole-atlas frontier, which has
  sole owner `0x003729b0` and target partition `1/1/1/2`. The
  `0x00378b5d -> 0x00378a15` and `0x00378b7d -> 0x0039cb98` edges are closed
  by the dependent receipts below. The fourth-callee receipt also closes
  `0x00378b92 -> 0x00378a40`, so no declared cluster direct edge remains
  opaque.
  The complete register-call audit
  contains only `call ECX` at `0x00378b4e`; final `jmp ESI` at `0x00378b6c`
  is separately retained without a target-provenance claim across the
  intervening call. The
  complete PE-address operand universe is four file-backed non-writable
  `.text` immediates, including one opaque interior-body push, and zero
  absolute-memory operands. Direct/staged Lua evidence is empty without
  excluding a dynamic Lua target. Its pretty-printed file SHA-256 is
  `c7da48c159c104db62ce6f0a6c47e31e2739179d9435a49c52e2dfc3014bbaea`;
  its canonical JSON SHA-256 is
  `1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5`.
  Adjacency and analysis labels prove no semantic kinship, execution order,
  exception behavior, ABI, target identity, state mutation, runtime effect,
  or Lua-side meaning.
  The dependent adjacent-cluster second-callee boundary canonical-pins that
  receipt and rejoins exact edge `0x00378b5d -> 0x00378a15`. It seals all 31
  target bytes, all 16 instructions, and a 16-node / 15-edge CFG. Exact PE
  checks bind the target to `.text` file offset `0x00377e15`, pin the atlas
  neighbors ending at `0x00378a15` and beginning at `0x00378a34`, and retain
  one opaque immediate naming writable `.data` RVA `0x00494010`. The four
  file bytes at that operand are `20 05 93 19` and are hash-pinned without a
  contents or runtime-behavior claim. An exhaustive all-operand atlas scan
  finds exactly four immediate `E8` entry references from four owners. Its
  pretty-printed file SHA-256 is
  `f5f42474bb049805e9844ac5cb6bffe25f4a20b8caea22ef0120620fdaabd6b8`;
  its canonical JSON SHA-256 is
  `ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d`.
  The `__NLG_Notify` Ghidra label is metadata only. Purpose, source identity,
  ABI, arguments, outputs, behavior, invocation, effects, success, failure,
  termination, and normal return remain unproved.
  The dependent adjacent-cluster third-callee import-thunk boundary
  canonical-pins that receipt and rejoins exact edge
  `0x00378b7d -> 0x0039cb98`. It seals all six target bytes, the sole `FF 25`
  instruction, and a 1-node / 0-edge CFG whose indirect jump has no statically
  resolved successor. The exact PE32 import proof binds `.rdata` VA
  `0x007d6170` / RVA `0x003d6170` to the unique `KERNEL32.dll` / `RtlUnwind`
  named row with hint 1048, descriptor index 7, thunk index 92, a null import
  descriptor, and both KERNEL32 thunk-array terminators. An exhaustive
  all-operand atlas scan finds exactly three immediate `E8` entry references
  from three owners. A separate scan of the IAT-slot VA finds exactly two
  absolute-memory uses from two owners: `FF 15` at `0x00371024` and the target
  `FF 25` thunk. Its pretty-printed file SHA-256 is
  `2f56d4bc7413036890013f70de5e202835f3254491048f17612a76c80a072f9b`;
  its canonical JSON SHA-256 is
  `1222126b3527186a823ffb252a97ddc2beb7a0c4dc49b45e15e462fb244b2a5b`.
  Import/Ghidra names are metadata only. Loader resolution, unwind or
  exception behavior, ABI, execution, reachability, effects, and normal return
  remain unproved.
  The dependent adjacent-cluster fourth-callee boundary canonical-pins both
  the cluster and second-callee receipts, then rejoins exact edge
  `0x00378b92 -> 0x00378a40`. It seals all 144 target bytes, all 48
  instructions, and a 48-node / 51-edge CFG. Exact backing checks bind the
  target to `.text` file offset `0x00377e40`, a three-byte left atlas neighbor,
  a nine-byte left gap, a 110-byte un-atlased right span, and a 23-byte right
  atlas neighbor. The two gaps total 119 sealed un-atlased bytes. Its complete
  outgoing partition has two edges: `0x00378aae -> 0x00378a15` exactly rejoins
  the pinned second-callee evidence, while `0x00378abb -> 0x00378a34` retains
  one opaque three-byte child. Nine PE-address operands, six non-PE literals,
  and three FS-qualified memory forms are exhaustively retained. Separate
  all-atlas scans find exactly three immediate `E8` target-entry references
  from three owners and one `other_address` reference to endpoint
  `0x00378ad0`. Its pretty-printed file SHA-256 is
  `105170018df7456821dc09c7e762b933f490eb9544131cb94a4b8c49810669ed`;
  its canonical JSON SHA-256 is
  `1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5`.
  The `__local_unwind4` label is metadata only. Purpose, unwind behavior, ABI,
  execution, effects, success, failure, and normal return remain unproved.
  The cluster now has zero opaque declared direct edges.
  The dependent adjacent-cluster fourth-callee child boundary canonical-pins
  both the fourth- and second-callee receipts and seals the exact three-byte
  body at `0x00378a34`, both decoded instructions, and its 2-node / 1-edge
  CFG. Its only control transfer is opaque `CALL EAX`, followed by a
  no-immediate `RET`; direct native, direct or staged Lua, PE-address,
  literal, segment-qualified, BND, and interrupt partitions are empty. The
  nine-byte right gap and both nearest atlas neighbors are PE-backed and
  hash-pinned. An exhaustive all-atlas operand traversal finds exactly two
  immediate `E8` entry references from owners `0x00378965` and `0x00378a40`.
  Each owner has a complete exact CFG slice whose unique call predecessor
  loads EAX immediately from input-dependent computed memory, after a paired
  call to the second-callee target. Neither slice proves a constant,
  relocation, absolute PE address, import slot, or concrete indirect target.
  Its pretty-printed file SHA-256 is
  `61e0571607dd92e2861f06297a410c9766135c718b0420afbf3d7351d160b570`;
  its canonical JSON SHA-256 is
  `71f87f861758ba8ef7f7d9a6ac435bb05df38d81e7ff5c8e7fe8c95a4fb0e193`.
  The target EAX value, runtime destination, analysis-label meaning, ABI,
  behavior, execution, effects, success, failure, and normal return remain
  unproved.
  The fourth callee's right un-atlased span now has a relationship-only
  receipt over exact range `[0x00378ad0,0x00378b3e)`. It retains two
  code-candidate components, not function claims: a 70-byte / 21-instruction
  component with a 21-node / 21-edge CFG and a 40-byte / 13-instruction
  component with a 13-node / 12-edge CFG. Their disconnected union has 34
  nodes / 33 edges. Four `E8` controls exactly target the pinned bodies at
  `0x003574ca`, `0x00378a40` twice, and `0x00007e70`; the prerequisite
  residual, residual-callee, and fourth-callee receipts independently rejoin
  all three target identities and all four call sites. The complete operand
  partition has five PE-address control immediates, six non-PE immediates, and
  one explicit `RET 4`, with empty absolute-memory, register-call,
  segment-qualified, BND, interrupt, direct-Lua, and staged-Lua partitions.
  Exact `.text` backing starts at file offset `0x00377ed0`. The full atlas has
  zero overlapping ranges and exactly one reference into the span: the fourth
  callee's `PUSH 0x00778ad0` at `0x00378a54`. A whole-file dword scan finds the
  same address once at file offset `0x00377e55`; one HIGHLOW relocation at RVA
  `0x00378a55` backs it, while no relocation site or parsed import/IAT slot is
  inside the span. Its pretty-printed file SHA-256 is
  `43db988b412d01cfbe06adfb258e2dfb2a3dbba98bfcf8a65e4092165a86eec1`;
  its canonical JSON SHA-256 is
  `02a4e933250820874a6b8876e8092636747f780bde25f28103b4585651dc0359`.
  All bytes decode, but padding classification is explicitly withheld.
  Function identity, semantic kinship, ABI, purpose, runtime reachability,
  invocation, behavior, effects, success, failure, and normal return remain
  unproved. This closes the exact layout join from the fourth callee to the
  already sealed adjacent cluster beginning at `0x00378b3e`.
  The three non-cluster, non-deferred direct targets are now sealed as a
  relationship-only residual set at `0x00372970`, `0x00007e70`, and
  `0x003581b3`: 57 bytes, all 23 instructions, and three body-local CFGs
  totaling 23 nodes / 21 edges. The 50-byte body preserves one conditional,
  the `E8` call fallthrough, and an external `E9` transfer to `0x003574ca`;
  the one-byte body is a `RET`, while the six-byte `FF 25` body is explicitly
  an opaque indirect jump rather than a terminal return. The complete
  PE-address universe is three `.text` immediates and one absolute-memory
  `.rdata` operand. `call r32`, direct Lua, and locally evidenced staged Lua
  partitions are empty. The exhaustive atlas scan finds 736 references:
  719 `E8` calls plus 17 `E9` address uses from 560 owners and 563
  target-owner groups, partitioned `3/252/481` across the targets. Five
  residual parents, the five adjacent parents, and the deferred
  `0x00372a53 -> 0x0039d580` row form an exact 11-edge `5/5/1` partition. Its
  pretty-printed file SHA-256 is
  `13784d112c47e9de5b0a92f7cfaac17245a98afb48214699ed516360b6d4d702`;
  its canonical JSON SHA-256 is
  `0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d`.
  Relationship membership and decoded syntax do not prove semantic kinship,
  ABI, purpose, runtime reachability, termination, target identity, effect,
  data meaning, or Lua-side behavior.
  The previously deferred `0x0039d580` target is now sealed across both atlas
  ranges: 164 bytes, all 57 instructions, and one 57-node / 57-edge union CFG.
  Only `JE` sites `0x0039d5c9` and `0x0039d5e3` cross the range gap to
  `0x0039d61f`; both range-local `RET` instructions terminate without an
  invented gap fallthrough. The exact parent `0x00372a53 -> 0x0039d580`
  cross-joins the residual receipt and the exhaustive one-reference atlas
  frontier, completing the formerly deferred member of the pointer target's
  11-edge partition. Two opaque outgoing calls target `0x0039d640` and
  `0x0039d530`. Seven PE operands comprise six immediates plus one writable
  `.data` absolute-memory read at operand index 1; four exact `FS:[0]` sites
  remain a separate segment-qualified class. Indirect control, `call r32`,
  direct Lua, and staged Lua partitions are empty. Its pretty-printed file
  SHA-256 is
  `ecf806bea49d116e0dd785d5d22aab4a769b51634efd1545acefa303d5c17778`;
  its canonical JSON SHA-256 is
  `a19a16ff5b999872acba98381163dc7d67113864ff508454d63162aa719e1c4e`.
  Analysis labels, relationship membership, decoded controls, PE addresses,
  and segment-qualified syntax do not prove purpose, ABI, exception behavior,
  runtime reachability, successful return, state mutation, data contents, or
  Lua-side behavior.
  The two formerly opaque multi-range callees are now sealed as a paired
  relationship-only boundary. `0x0039d530` contributes 67 bytes / 33
  instructions and a 33-node / 36-edge CFG; `0x0039d640` contributes 49 bytes
  / 19 instructions and a 19-node / 19-edge CFG. Their exact parents
  `0x0039d5bf -> 0x0039d640` and `0x0039d5d9 -> 0x0039d530` rejoin the
  multi-range receipt and an exhaustive two-reference atlas frontier from
  sole owner `0x0039d580`. Six `.text` conditional-target immediates form the
  complete PE-address partition; outgoing direct edges, indirect control,
  `call r32`, segment-qualified memory, direct Lua, and locally evidenced
  staged Lua partitions are empty. Its pretty-printed file SHA-256 is
  `bffdbec3554c1969563d4ac235a2e7d150aff311b5b277a31a9f413a3b5094e2`;
  its canonical JSON SHA-256 is
  `c479ae8d802d848877f8fd57475d8909e0fe2129d25182996d16f599b6cbaf8c`.
  Relationship membership and decoded syntax do not prove semantic identity,
  purpose, ABI, runtime reachability, normal return, state mutation, data
  meaning, un-atlased references, or Lua-side behavior.
  The residual target set's callee at `0x003574ca` is now sealed as a separate
  relationship-only boundary: 17 bytes, all four instructions, and a 4-node /
  3-edge CFG. The exact body retains opaque `F2`-prefixed conditional, return,
  and external-jump syntax; the outgoing transfer targets `0x00357b6a`.
  Its complete PE-address partition is one writable `.data` absolute-memory
  read plus two `.text` immediates. Indirect controls, `call r32`,
  segment-qualified memory, direct Lua, and staged Lua partitions are empty.
  Both residual parents (`E8` at `0x0037298a`, `E9` at `0x0037299d`) rejoin
  the predecessor receipt. The exhaustive atlas frontier has 1,794 references
  from 1,620 owners: 1,790 standard `E8` calls, three `F2 E8` calls, and one
  `E9` address use. Its pretty-printed file SHA-256 is
  `548580d0fee7d612fe16bfe10b567ffd2c8d9a6add9cfd965a75c48c22123c2b`;
  its canonical JSON SHA-256 is
  `8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1`.
  Relationship membership, BND-prefixed syntax, decoded controls, and PE
  addresses do not prove security purpose, source identity, ABI, runtime
  reachability, termination, state mutation, data meaning, or Lua behavior.
  The residual callee's relationship-only external target `0x00357b6a` is now
  sealed in its own receipt: 251 bytes, all 56 instructions, and a 56-node /
  55-edge enriched CFG. Its exact terminal `CD 29` is opaque interrupt syntax
  only, without claiming runtime interruption or termination behavior. Two
  opaque `E8` edges leave the body: `E8 18 50 04 00` at
  `0x00357b75 -> 0x0039cb92` and `E8 E1 FE FF FF` at
  `0x00357c5c -> 0x00357b42`. Its 28 PE address operands split into four
  immediates and 24 writable `.data` absolute-memory operands (21 writes /
  three reads), with exactly six file-backed and 22 virtual-only records.
  Indirect controls, `call r32`, BND-prefixed controls, segment-qualified
  memory, direct Lua, and staged Lua partitions are empty. The full atlas
  scan has one target reference from one owner: the exact `F2 E9` at
  `0x003574d5` from `0x003574ca`, across 25,312 functions, 25,490 ranges,
  3,735,718 bytes, and 1,153,814 instructions. Its pretty-printed file
  SHA-256 is
  `366bbfcf22cf6ed4dd667308336036191651c4d6dba3d48e6ae51271b66998c6`;
  its canonical JSON SHA-256 is
  `0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9`.
  The first of those targets, relationship-only import thunk `0x0039cb92`, is
  now sealed separately: its complete body is the one 6-byte `FF 25 10 60 7D
  00` instruction, with a 1-node / 0-edge `indirect_jump` CFG (canonical
  SHA-256 `29e8bc268788c4dad137925a79b4350355d7f7db2dd2666bbc21399dd5bce60c`).
  It is not a return; its runtime target, execution, and OS semantics remain
  opaque. The sole local PE operand is a file-backed, nonwritable `.rdata`
  absolute-memory read at VA `0x007d6010` / RVA `0x003d6010`. Raw PE32 import
  metadata uniquely binds it to `KERNEL32.dll!IsProcessorFeaturePresent`, hint
  772, no ordinal; the binding is metadata only. The receipt seals the
  220-byte import directory (10 descriptors / 342 named / zero ordinal;
  KERNEL32 has 139 rows), retains parent `E8` at `0x00357b75`, and finds six
  all-atlas `E8` calls from six owners. A separate all-atlas IAT-slot scan
  finds exactly this one `FF 25` use. There are no outgoing direct calls,
  direct/staged Lua, `call r32`, BND, segment, or interrupt records. The scan
  covers 25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814
  instructions. Its pretty-printed file SHA-256 is
  `91397015cb9d8cd74fe2f18d648060c1e8cb28baa6b79f15f39e55ff77e3b71f`; its
  canonical JSON SHA-256 is
  `af117e253c45140863acc378051d6b5b1eba37458337aad43be6ef22d2589654`.
  The sibling relationship-only target `0x00357b42` is now sealed separately:
  its complete 40-byte body has 12 instructions and a 12-node / 11-edge CFG
  (canonical SHA-256
  `b3d334286def4ca119c59b70f91b17aa46c35b9737edf5088bf755b3f43e0b39`).
  Four `FF 15` call-fallthrough syntaxes read file-backed, nonwritable
  `.rdata` IAT slots. Raw PE32 metadata uniquely binds the slots to
  `KERNEL32.dll!SetUnhandledExceptionFilter`, `UnhandledExceptionFilter`,
  `GetCurrentProcess`, and `TerminateProcess`, with hints 1189, 1235, 448,
  and 1216 and no ordinals; these identities remain metadata only. The receipt
  rejoins parent `E8` at `0x00357c5c`, while the exhaustive target scan finds
  exactly two `E8` references from owners `0x00357b6a` and `0x00357c71`.
  Four separate IAT-slot closures find 3, 3, 5, and 13 all-atlas uses for slot
  RVAs `0x003d6014`, `0x003d6018`, `0x003d60e4`, and `0x003d60f0`,
  respectively; the 13-use set includes one `8B 3D` absolute-memory read and
  12 `FF 15` calls. Every closure scan checks immediate and pure
  absolute-memory operands across all 25,312 functions, 25,490 ranges,
  3,735,718 bytes, and 1,153,814 instructions. Outgoing direct calls,
  direct/staged Lua, `call r32`, BND, segment, and interrupt partitions are
  empty. Its pretty-printed file SHA-256 is
  `5ccb1830fe36c58579b35089c68b84f0eb34bd5303eab72c09d4ed6b8b3096d2`;
  its canonical JSON SHA-256 is
  `f82310c91d26d3580458decdd70450c130f965ea53134cf0a383b7f9e5ea56d4`.
  This branch's direct-target frontier is now closed. Relationship membership,
  analysis labels, import metadata, decoded syntax, and PE addresses do not
  prove purpose, source identity, ABI, runtime reachability, imported-function
  execution, termination, state mutation, normal return, data meaning, or
  Lua-side behavior.
  The query handler's 9-byte local target is now closed by a separate,
  recursively pinned boundary. It rejoins and independently revalidates
  `0x0038bc41 -> 0x0038bc51`, seals all four instructions and the 4-node /
  3-edge CFG, and retains the sole outgoing
  `0x0038bc53 -> 0x00388c0d` direct call as opaque. Its all-atlas entry
  frontier is exactly one immediate `E8` call from one owner; Lua calls,
  register calls, literals, and absolute-address records are empty. Its
  pretty-printed file SHA-256 is
  `3cc19d7a2fb7aac636aba2395692598dad8de7e51c5be9a12c75c30b33eb306c`;
  its canonical JSON SHA-256 is
  `01a03401fdbef4e6d1d575ab74e498b5271387a1ffde440c0dee44b28ad5439c`.
  Default and analysis-generated labels remain metadata only; helper purpose,
  unlock/lock behavior, ABI, argument meaning, success, state mutation,
  normal return, runtime reachability, source identity, and callee behavior
  remain unproved.
  The local helper's sole native target is now closed by a relationship-defined
  callee boundary. It canonical-pins the predecessor artifact, independently
  rejoins exact edge `0x0038bc53 -> 0x00388c0d`, and seals the complete
  23-byte body, all nine instructions, and its 9-node / 8-edge CFG. Its exact
  all-atlas entry frontier contains 29 immediate `E8` calls from 29 distinct
  owners; comparison, other-address, and absolute-memory entry references are
  empty. The body has no direct native edge, Lua call, register call, or
  retained literal. It does retain an absolute add operand into the
  virtual-only writable `.data` tail and an absolute-memory call through a
  file-backed non-writable `.rdata` slot. The sealed PE import table uniquely
  binds that slot to `KERNEL32.dll!LeaveCriticalSection`, hint 825, as metadata
  only. Its pretty-printed file SHA-256 is
  `2a0f26e367e6527890757e7fdafa9f621e3a0b07566fd7624807a5781b44ef95`;
  its canonical JSON SHA-256 is
  `c41457569fcc4f412c35de53f7830d6e4049791a4991062d341d73a756437310`.
  The `___acrt_unlock` analysis label and named import do not prove purpose,
  synchronization or lock/unlock behavior, ABI, argument meaning, state
  mutation, successful or normal return, runtime execution, source identity,
  or pointed-to data.
  The query handler's second direct target is now closed by another
  relationship-defined boundary. It canonical-pins the query-handler artifact,
  independently rejoins exact edge `0x0038bc1a -> 0x00388bc5`, and seals the
  target's complete 23-byte body, nine instructions, and 9-node / 8-edge CFG.
  Its all-atlas entry frontier is 26 immediate `E8` calls from 26 owners, with
  comparison, other-address, and absolute-memory entry references empty. The
  body has no direct native edge, Lua call, register call, or retained literal.
  Its absolute add operand names the same virtual-only writable `.data` RVA;
  its absolute-memory call uses the adjacent file-backed non-writable `.rdata`
  IAT slot. The sealed PE import table uniquely binds that slot to
  `KERNEL32.dll!EnterCriticalSection`, hint 238, as metadata only. Its
  pretty-printed file SHA-256 is
  `39daf451a37440201d5cadedf946da30d3fa90e1a23677bf39f913f4a8fa6d33`;
  its canonical JSON SHA-256 is
  `fd8836f3ccaa14ec45931d611f96122b7b64f2ca54331d6aa2730197c1f45b20`.
  The `___acrt_lock` analysis label and named import do not prove purpose,
  lock or synchronization semantics, ABI, argument meaning, state mutation,
  success, normal return, runtime execution, source identity, or pointed-to
  data.
  The query handler's fourth direct target is now closed by a separate
  relationship-defined boundary. It canonical-pins the query-handler artifact,
  independently rejoins exact edge `0x0038bc48 -> 0x003584f6`, and seals the
  target's complete 21-byte body, 11 instructions, and 11-node / 10-edge CFG.
  Its all-atlas entry frontier is 67 references from 67 owners: 66 five-byte
  immediate `E8` calls plus one six-byte BND-prefixed immediate jump at
  `0x0039d7c4`, classified as `other_address`. Comparison and absolute-memory
  entry references are empty. The body has no direct native edge, Lua call,
  register call, or retained literal. Its exact `FS:[0]` destination write is
  retained as opaque segment-relative syntax rather than mapped to a PE
  absolute address. Its pretty-printed file SHA-256 is
  `2af1d59469ee8213ea8ae29bd0df46969af1b7c4acc9453f9d24ae06b655f9a7`;
  its canonical JSON SHA-256 is
  `d89c9a6eb25d63cd08830a0ee7beab1df5413aa6eb2b05ac791b8c1b7fedc05e`.
  The `__SEH_epilog4` analysis label does not prove purpose, SEH, exception,
  epilog, stack, register, ABI, state mutation, success, normal return,
  runtime execution, source identity, or segment-relative contents.
  Two adjacent returned-closure surveys now trace the remaining static factory
  edges. `docs/native_lua_property_factory_survey.md` follows the global
  `property` callback through its exact one-or-two-argument grammar into a
  two-upvalue error-tag closure, then partitions all four direct-immediate tag
  references: the factory, an alternate registry-backed producer, and the
  `__index`/`__newindex` consumers that use upvalues one and two with distinct
  call arities. Callback identity alone deliberately does not establish which
  producer supplied a dynamic closure. The normalized executable-rebuilt core
  artifact now pins the unique publication, factory-returned closure, separate
  registry-holder producer, three bounded literals, the two callback bodies
  (125 bytes aggregate) and sealed CFGs, all seven direct Lua calls, an empty dynamic
  register-call partition, and the complete five-reference two-target atlas
  scan. Its canonical JSON SHA-256 is
  `aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e`.
  The adjacent consumer artifact now recursively binds that factory evidence
  and seals the getter-like consumer, setter-like consumer, and initializer:
  706 bytes, 279 CFG nodes, 286 CFG edges, all 34 direct Lua calls, and all 23
  EBX/ESI/EDI staged calls under a complete eight-encoding `call r32` audit.
  It normalizes both tag-match arms and the setter's read-only arm, while
  keeping both mismatch branches explicitly opaque at that artifact layer. It
  also distinguishes the first getter closure stored under numeric raw key
  `1.0` from the separately created `__index` getter and `__newindex` setter.
  Its exhaustive three-target
  atlas partition has six references: three closure producers, two getter
  identity comparisons, and the sole direct initializer call. The canonical
  JSON SHA-256 is
  `2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9`.
  The dependent mismatch-path artifact now removes that local opacity without
  weakening the consumer boundary. It recursively exact-verifies the complete
  consumer chain, seals the two source bodies and their 190-node / 195-edge
  CFGs, rejoins 78 path points to direct or staged Lua API identities, and
  publishes replayable normal-return stack traces for all three getter
  candidate sources and both setter storage arms. It retains the getter's
  distinct buried-stack shapes and proves `slot 4 = F` only under `N == 3`;
  for `N >= 4`, slot four is `I4`. Its canonical JSON SHA-256 is
  `49276d63020a536bdd456d3f36667428afff2b3d8b15e479eb5444c241b23263`.
  Runtime provenance, dynamic attachment and invocation, entry arity, durable
  mutation, and source-level property equivalence remain open.
  `docs/native_lua_property_residual_survey.md` now closes those two mismatch
  traces at the exact-build research layer. It preserves the setter's critical
  absolute-slot-four distinction instead of assuming three arguments, maps the
  initializer's `__luabind_class` marker and `__gc` closure, proves the ordered
  13-key / two-upvalue wrapper loop (with true flags only for `__unm` and
  `__len`), reconstructs the two-input wrapper callback, and closes a
  76-direct-caller frontier for the reusable numeric-slot-one recognizer. The
  residual helper target partition has 79 exact operands when the `__gc`
  cleanup helper is included. The two mismatch traces have now been promoted
  into the dependent executable-rebuilt artifact above. A second dependent
  initializer artifact now seals the 245-byte source body and 89-node / 91-edge
  CFG identity, 15 exact literals, the marker and zero-upvalue `__gc` closure
  placements, and the ordered 13-row / two-upvalue wrapper loop. Its 52-byte
  pointer array is exact-reread, with true Boolean flags only at `__unm` and
  `__len`; its canonical JSON SHA-256 is
  `b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4`.
  Cleanup-callback/helper behavior is now promoted by a dependent artifact. It
  recursively verifies the initializer, seals 201 bytes and 83-node / 86-edge
  CFG identity, joins all ten direct Lua calls and the `__finalize` literal,
  and reproduces the exact two-reference target partition. Its canonical JSON
  SHA-256 is
  `e2aaf57a9560f806814977ee30a48ce4d3afae35d00e78e3bcb39ebb9bfb7483`.
  Wrapper/recognizer behavior is now promoted by the second callback artifact.
  It recursively verifies the initializer, seals 395 bytes and 155-node /
  159-edge CFG identity, joins 20 direct and four register-staged Lua calls,
  exact-rereads `No such operator defined`, and reproduces one wrapper producer
  plus 76 recognizer calls from 76 owners as the complete 77-reference target
  partition. Its canonical JSON SHA-256 is
  `7db59f62fc9d70e3b2338bc0349afae91ee8c7b34099cd3b034c6c240b035fdc`.
  The fixed-point register proof preserves both valid last definitions for the
  error-path `call EBX` at `0x002ea25c`. Together the cleanup and operator
  artifacts close the reviewed 596-byte callback packet while retaining the
  wrapper's no-arity-guard and absolute-slot-three caveats and making no
  semantic-homogeneity claim about the 76 recognizer callers.
  `docs/native_lua_class_factory_survey.md` follows the global `class` callback
  through its exact string, numeric-string, and embedded-NUL guards, 72-byte
  userdata initialization and global assignment, into a returned one-upvalue
  callback. That callback checks both values for `__luabind_classrep`, mutates
  the captured object through a native helper, feeds two registry-reference
  pairs to a second helper, and copies one fixed word before returning zero.
  The normalized executable-rebuilt class artifact now pins the unique
  publication and returned-closure join, four literals, both reviewed callback
  bodies and sealed CFGs, all nine register-dispatched Lua calls under three
  exact IAT stages, six selected direct native edges, and the complete
  two-target 25,490-range / 1,153,814-instruction operand partition. Its
  canonical JSON SHA-256 is
  `824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc`.
  Helper-internal behavior from the wider survey remains outside this narrow
  artifact, as do runtime reachability, indirect/Lua-side consumers, registry
  validity, source class/derivation semantics, and source equivalence.
  `docs/native_lua_super_rebinding_survey.md` now closes the three proved
  `super` publication rows into one conditional rebinding chain: a zero-upvalue
  deprecation/error callback, a guarded two-upvalue replacement around an
  `__init` call, and that callback's pointer-driven self-replacement plus nil
  cleanup arms. A complete atlas operand scan finds exactly three direct target
  references, all closure producers and no direct native consumers. The
  normalized executable-rebuilt artifact now pins the three publication rows,
  three literals, four reviewed bodies and sealed CFGs, every direct Lua-call
  join, all 13 register-dispatched Lua calls under five exact IAT stages, and
  the complete 25,490-range / 1,153,814-instruction target-reference partition.
  Its canonical JSON SHA-256 is
  `da064ec63caddb0f3c7735caefa8397795455be76a9ead2ffc8ed678a9612ba4`.
  Runtime reachability, indirect/computed consumers, Lua-side invocation, and
  source equivalence remain open.
  Preliminary luabind-shaped pointer/name/builder candidates remain local
  research until every builder form and alternate compiler sequence has an
  exact, complete grammar.
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
- [ ] Populate the exact subsystem-ownership and exclusion partitions with
  reviewed evidence; the initial ledger's all-unknown/zero-exclusion baseline
  is accounting infrastructure, not semantic classification.

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
