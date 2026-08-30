# ITB Engine Observatory data

This directory contains build-keyed, read-only evidence about installed
Into the Breach implementations. It must not contain game binaries or
proprietary decompiled source.

The whole-program expansion is defined in
`docs/full_decompile_program.md`. Normalized Ghidra function atlases and their
publication rules live under `programs/`.

## Whole-program native atlas

`scripts/ghidra/ExportItbProgramFacts.java` exports every Ghidra-discovered
mapped function as normalized TSV: entry RVA, body ranges and SHA-256, analysis
name/source, thunk flag, and Ghidra-declared direct internal calls. It emits no bytes,
disassembly, or decompiler text.

`scripts/itb_program_facts.py build` verifies those ranges against the exact
inventoried PE before creating a deterministic artifact under `programs/`.
`verify` independently rechecks a committed atlas against the executable. See
`programs/README.md` for commands and limitations.

## Native function review accounting

`scripts/itb_native_function_accounting.py` derives a strict review overlay
from the exact-verified program atlas and a separately hash-pinned analyst
registry. The normalized artifact under `programs/` has exactly one record for
each of the 25,312 atlas functions and recomputes complete partitions for
level, boundary status, ownership, subsystem, native/Lua boundary state,
immediate-reference status, evidence class, and exclusion. Schema 2 separately
counts positive native/Lua roles because those roles can overlap and therefore
do not form a partition.

The initial ledger intentionally records all 25,312 functions at L0 and leaves
all ownership/subsystem classifications unresolved; it has zero L1/L2
promotions and zero reviewed exclusions. Ghidra's 685 thunk flags and 26
repeated-body groups are retained only as non-promoting review candidates.
Future claims must pass dedicated exact-dimensional review and typed-support
records, then reach hash-pinned upstream evidence through a registered
kind-specific adapter that derives the supported assertion. Three production
adapters exact-rebuild their evidence against the installed executable: the
direct-call census can derive only `lua_api_consumer`, the immediate C-closure
census can derive only `cclosure_callback_target`, and the setfield-publication
census can derive only `registered_lua_callable` for a pointed callback target
or `registration_builder` for a pointed caller aggregate. None proves a global
export, table identity, runtime execution, ownership, lifetime, or another
dimension. The empty registry still promotes no function beyond L0. No name,
namespace, address, body-size, duplicate-body, thunk, or Ghidra-call
heuristic can change a level or classification; unreachable, duplicate/thunk,
and data-only
exclusions also fail closed until their specialized proof contracts exist. See
`programs/README.md` for the full registry/evidence contract, commands, and
remaining atlas/callgraph gaps.

## Native-to-Lua direct-call census

`scripts/itb_native_lua_direct_calls.py` exact-verifies the native atlas, parses
the PE import table, and independently decodes every atlas body byte with
pinned Capstone 5.0.7. It retains only exact six-byte x86 `FF 15` calls whose
absolute operand is one named `lua5.1.dll` IAT slot. The normalized artifact
under `programs/` covers all 25,490 atlas ranges and 3,735,718 body bytes,
records 1,153,814 decoded instructions, and identifies 4,739 direct Lua import
calls in 1,787 atlas functions. All 54 named Lua imports have at least one
retained call site.

The result is a positive binary relation, not a semantic partition. It does not
claim runtime reachability, ownership, registration roles, callback roles,
indirect calls, or absence of Lua use outside a retained site. Direct API
consumer, C-closure callback-target, registration-builder, and registered-
callable roles can overlap, so the census remains a separate positive relation.
Accounting schema 2 can retain overlapping roles, and its narrowly allowlisted
adapter can use an exact binary-reverified census record only for positive
`lua_api_consumer` support.
It cannot infer absence, registration, callback status, ownership, or any other
role or dimension. See `programs/README.md` for exact commands, hashes, and
limitations.

## Native Lua C-closure callbacks

`scripts/itb_native_lua_cclosure_callbacks.py` exact-verifies the atlas and
direct-call census, then accepts only an immediate callback VA in one pinned
x86 `lua_pushcclosure` argument form. It partitions all 15 direct sites into 13
exact immediate callback edges and two unresolved computed arguments. The 13
edges resolve to 11 unique non-thunk atlas entries; one is a self-edge, all 11
targets also directly call Lua imports, and three targets also contain direct
`lua_pushcclosure` call sites.

The artifact claims only that an atlas entry is statically passed as a closure
callback argument. It does not infer a Lua-visible name, global registration,
runtime execution, ownership, semantics, or a target for either computed
argument. Accounting's callback adapter rebuilds the whole direct-call and
callback chain against the executable and can derive only the positive
`cclosure_callback_target` role. `registered_lua_callable` remains reserved for
future evidence that proves publication or registration beyond closure
construction. See `programs/README.md` for exact commands, hashes, and limits.

## Native Lua C-closure setfield publications

`scripts/itb_native_lua_cclosure_setfield_publications.py` exact-verifies the
direct-call and immediate-callback prerequisites, then accepts only one finite
x86 fall-through grammar: zero-upvalue closure construction, caller cleanup,
an immediate key pointer, table index `-2`, the same Lua-state register, and a
direct `lua_setfield` import call. It partitions all 13 resolved callback sites
into three exact table-field publications and ten unmatched sites. The three
accepted paths share caller RVA `0x002e6900`, store three distinct callback
targets under the exact bounded key `__gc`, and retain complete atlas and
instruction hashes without publishing executable bytes.

The module also exposes a PE-free whole-artifact structural validator for
offline composition checks. It revalidates the callback prerequisite, complete
partition, atlas/direct-call joins, reconstructible x86 hashes, aggregates, and
summary, but deliberately does not treat document consistency as binary proof;
key bytes and decoded control flow still require exact executable verification.

This proves static table-field storage of each newly constructed closure. It
does not identify the dynamic table as a metatable, prove global or module
export, establish runtime reachability or persistence, cover another setter
API, or resolve either computed callback argument. Accounting's
setfield-publication adapter rebuilds the direct-call and callback prerequisites
and exact-verifies the whole publication census against the executable. It can
derive only `registered_lua_callable` from one pointed callback aggregate or
`registration_builder` from one pointed caller aggregate. The artifact and
adapter do not themselves promote the empty review registry. See
`programs/README.md` for exact commands and hashes.

## Native Lua C-closure direct table-setter publications

`scripts/itb_native_lua_cclosure_table_setter_publications.py` exact-verifies
the direct-call, callback, and setfield-publication chain, then consumes only
the setfield census's ten-site unmatched frontier. It accepts one further
finite fall-through grammar: optional positive `add esp,imm8` cleanup, an exact
signed immediate table index other than the definitely invalid `0` and `-1`
forms, the same ABI-nonvolatile Lua-state register, and a direct `FF 15` call to
imported `lua_settable` or `lua_rawset`. The newly constructed closure remains
the setter's top-of-stack value; the pre-existing stack key is not guessed or
named.

The exact build partitions that frontier into four publications and six
still-unmatched sites. Three use `lua_settable` and one uses `lua_rawset`; table
indices are exactly `-10002` or `-3`, with three unique callback targets and
four builders. A PE-free structural validator independently rechecks the prior
frontier, signed x86 encodings, exact direct-setter joins, full partition,
aggregates, and summary without treating document consistency as binary proof.

This proves only that each static direct sequence hands the newly constructed
closure to the named table setter as its value. It does not recover the stack
key, identify the destination table, infer a global/module export or ordinary
Lua lookup name, establish runtime reachability or persistence, cover indirect
setter calls, or classify the remaining return/registry-reference paths. The
artifact does not itself promote the empty review registry. See
`programs/README.md` for exact commands and hashes.

Accounting's direct-table-setter adapter independently rebuilds and
exact-verifies the direct-call, callback, setfield, and table-setter chain. It
derives only `registered_lua_callable` from one pointed callback aggregate or
`registration_builder` from one pointed caller aggregate; every other role and
pointer form fails closed. Adding the adapter does not promote the empty review
registry.

## Native Lua C-closure indirect `lua_settable` publications

`scripts/itb_native_lua_cclosure_indirect_settable_publications.py` consumes
the direct-table-setter artifact's six residual sites and proves three further
static publications through a staged `lua_settable` import in `ESI`. The exact
grammar requires the unique `mov esi,[lua_settable IAT]` stage, a contiguous
cleanup/index/state/`call esi` tail, caller-entry reachability, stage dominance
of every setter and later callback, and no ESI writer on any stage-to-setter
path. The accepted indices are `-3` and `-10002`.

The artifact retains one normalized 260-node/265-edge caller CFG plus exact
dominance, path, atlas-entry, declared-direct-entry, instruction-hash, and
decoded ESI-write witnesses. Calls rely on the explicit 32-bit Windows cdecl
premise that `ESI` is callee-preserved. Exact rebuilding is required to derive
branch semantics and write classifications; the PE-free validator checks the
stored graph and recomputes its reachability/dominance claims but cannot turn
hashes into binary proof. Unmodeled indirect, exception, or fabricated
interior entries remain an explicit atlas-entry assumption.

This proves three conditional static setter edges, not the stack key,
destination table, Lua-visible name, global/module export, runtime execution,
or lifetime. The three terminal-disposition sites remain unmatched in this
artifact. See `programs/README.md` for exact commands and hashes.

## Native Lua C-closure terminal dispositions

`scripts/itb_native_lua_cclosure_terminal_dispositions.py` independently
consumes the same six-site residual frontier and recognizes three complete,
reviewed terminal forms. Two closures are followed contiguously by `eax = 1`
and an exact enumerated epilogue; each caller independently joins the callback
census as a native Lua callback target, so the closure is conditionally the
single returned Lua result. The third closure is duplicated, passed to
`luaL_ref` at registry index `-10000`, stored with the same Lua state in a
returned two-word holder, and then removed from the Lua stack.

The exact artifact leaves only the three indirect-setter sites unmatched, so
the indirect and terminal artifacts form complementary partitions of the
direct-setter residual frontier. These facts do not establish runtime
reachability, an ordinary Lua lookup path or name, registry-reference lifetime,
ownership, or source/behavioral equivalence. See `programs/README.md` for exact
commands and hashes.

## Compiled Lua census

`scripts/itb_lua_census.py` rebuilds the complete sealed installation
inventory, compiles every accepted script and Lua-form map chunk with the
inventoried 32-bit Lua 5.1 DLL, and parses the dumped chunks without executing
game code. It pairs all compiled nested prototypes with lexical function spans,
decodes identifier-only environment/member operations, cross-checks the 757-
definition callback index, and builds a claim-labeled static load model.

The normalized artifact under `lua/` contains 529 compiled chunks, 915 function
prototypes, 173,619 instructions, and 2,686 environment identifiers. Its 523
modeled edges comprise 145 compiler/source-derived edges and 378 explicitly
labeled assumptions; together they cover 520 accepted files and leave nine
explicitly unrouted in the model. Raw source, literal payloads, binary chunks,
absolute paths, and the owner's Mod Loader overlay are excluded. See
`lua/README.md` for exact build and verification commands and the boundary
between compiler-backed facts, loader assumptions, native-binding candidates,
and future semantic work.

## Static map-data census

`scripts/itb_map_census.py` rebuilds and exact-matches the sealed installation
inventory, joins every map-directory file to the compiled Lua census, then
parses all `.map` chunks with a strict declarative-data parser that never
executes Lua. Context validation rejects unknown fields, mixed table shapes,
duplicate keys or coordinates, out-of-bounds points, name/global mismatches,
unbounded input/allocation shapes, unpublishable string domains, and currently
unsupported nonempty source tables. The map command reruns the full Lua census
verifier before accepting compiled-status claims from that prerequisite.

The normalized artifact under `maps/` accounts for all 376 map-data chunks,
8,915 explicit unique in-bounds tile records, ten tile-field schemas, 25 zone
keys, and 32 tags. It contains source identity hashes, structural counts, and
small aggregate domains, but no layout-derived hashes, raw source,
per-map tag membership, or coordinate layouts. See `maps/README.md` for exact
build/verification commands and the boundary between observed grammar facts
and unresolved native consumer semantics.

## OpenGL shader interface census

`scripts/itb_shader_census.py` rebuilds and exact-matches the sealed
installation inventory, seals the separately scoped flat `shadersOGL/`
directory, and applies a strict non-executing lexical/interface parser to all
12 files. The normalized artifact under `shaders/` records exact file
identities, extension-based stage hints, duplicate groups, line-ending facts,
bounded interface/preprocessor/call identifiers, and counts. It contains no
raw source, expressions, literals, function bodies, compiler output, or
absolute paths.

The census accounts for 4,087 source bytes, eight entry points, ten uniform,
three attribute, and two varying identifiers, nine `texture2D` calls, and four
`discard` sites. See `shaders/README.md` for exact build and verification
commands and the boundary between lexical source facts and unresolved loader,
compiler, pipeline, and rendering behavior.

## FMOD bank and native interface census

`scripts/itb_fmod_census.py` exact-matches the sealed installation inventory,
seals the separate flat five-bank surface under `resources/`, validates every
bank as an exact-EOF RIFF/`FEV ` container, and joins bounded container facts
to the two shipped FMOD DLL export/version surfaces and `Breach.exe` imports.
The normalized artifact under `fmod/` contains whole-file identities,
aggregate RIFF/FourCC counts, bounded raw `FMT `/`FSB5` header words, SHA-256
identities for complete sorted named-export sets, ordinal-slot counts, exact
executable imports, and bank-basename literal locations. It contains no bank
payload bytes, decoded
event/string paths, samples, codecs, recursive topology, or isolated payload
fingerprints.

The census accounts for five banks and 168,821,378 bytes, 25,979 RIFF nodes,
689 recursive `WAV ` chunks, four `FSB5` signatures, two version-`1.10.2`
libraries with 1,429 named and zero ordinal-only exports, 22 named executable
imports, and one literal occurrence for each expected bank basename. See
`fmod/README.md` for exact build and verification commands and the boundary
between binary/container interface facts and unresolved audio/runtime
semantics.

## Resource archive census

`scripts/itb_resource_inventory.py` parses `resources/resource.dat` without
extracting it. The build step first rebuilds and exact-matches the sealed
installation inventory, including its resource archive path, size, and hash.
It then requires a strictly contiguous offset/record layout from the end of the
table through EOF, canonical unique UTF-8 paths, valid PNG/TrueType signatures,
and exact per-payload plus whole-archive hashes. Normalized
path/offset/size/hash inventories live under `resources/`; no asset payload
bytes are eligible for Git.

## Installation inventories

Create a deterministic inventory outside the installed game:

```text
python scripts/itb_content_inventory.py inventory \
  --install-dir "<Into the Breach install>" \
  --label "<provenance note>" \
  --output data/observatory/inventories/<snapshot>.json
```

The tool hashes the native executable, shared libraries, known opaque resource
archives, and every regular file under `scripts/**` and `maps/**`. Paths are
relative and slash-normalized. Filesystem timestamps and the absolute
installation path are excluded. Symlinks are not followed. Steam build/depot
evidence is accepted only when the adjacent app manifest names the exact
inventoried directory.

The committed Windows snapshot is explicitly a modified local installation,
not a vanilla-depot manifest. Its script tree includes the installed bridge and
backup artifacts. Re-run the inventory against clean platform depots before
claiming cross-platform content equality.

Compare two snapshots by content hash:

```text
python scripts/itb_content_inventory.py compare LEFT.json RIGHT.json
```

One-sided Lua or map files are `missing`; they are never excused as
platform-specific. One-sided native binaries on different build platforms are
`platform_specific`.

## Mechanics provenance

`mechanics_provenance.json` maps high-value shipped Lua functions to independent
Rust/Python implementations, tests, evidence classifications, and known gaps.
It is pinned to the exact platform, architecture, executable hash, depot/build,
and scripts/maps revisions in its referenced inventory.

Validate it with:

```text
python scripts/itb_provenance.py \
  data/observatory/mechanics_provenance.json \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json
```

Validation fails closed on build drift, stale Lua hashes, missing repository
paths, path escapes, duplicate keys/records/symbols, non-finite JSON,
unsupported status values, or a non-verified record without an explicit gap.
The inventory path embedded in the provenance file must resolve inside the
repository and its parsed content must equal the inventory supplied to the
validator.

Audit which high-value shipped Lua files are named by at least one provenance
record:

```text
python scripts/itb_provenance.py \
  data/observatory/mechanics_provenance.json \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  --audit-sources
```

The JSON output says only whether an exact source hash is indexed. It explicitly
does not equate source indexing with implemented or verified behavior.

Audit active top-level Lua callback declarations against exact provenance
symbols:

```text
python scripts/itb_callback_coverage.py \
  data/observatory/mechanics_provenance.json \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  "B:\SteamLibrary\steamapps\common\Into the Breach"
```

The callback audit hash-verifies every selected installed Lua file, masks
comments and strings, excludes nested and local functions, and joins exact
`path + hash + symbol` triples to the validated provenance index. A callback
reported as indexed is only named by a record; the report deliberately makes
no claim about runtime reachability, inheritance, Rust equivalence, test
adequacy, native helpers, or behavioral conformance.
Mission-environment files can belong to both categories, so category callback
totals intentionally overlap. The report distinguishes callback definition
instances from unique `path + symbol` pairs.

The build-keyed output currently used for runtime identity joins is committed
at
`callbacks/windows_build_13725832_31fe35265598_callback_index.json`. It contains
757 definitions across 108 selected source files (410 indexed by provenance and
347 explicitly unindexed) and has SHA-256
`eb73977455203cb50e26c3ee16033aa37677aad4c68c1344dfafc48181829952`.
It contains only normalized symbols, source locations/hashes, categories, and
indexing status—not Lua source text—and must be regenerated for any changed
inventory identity.

The first reversible-owner runtime capture is sealed at
`captures/windows_build_13725832_owner_local_modified_20260821_callback_receipt.json`.
The receipt binds the exact build and instrumentation identities, the failed-
closed `Garden_Atk` discovery attempt, two byte-identical fresh-process runtime
manifests, the 65/65 exact lexical join, and both targeted and whole-install
cleanup verification. Its SHA-256 is
`652876a007d8a5def0fde84d228e191303a48148666814a472c35a7059f5eb5b`.
The capture is explicitly `owner_local_modified`: it proves deterministic
callback identities for that inventoried build, not callback behavior, native
hook safety, solver equivalence, or pristine-depot neutrality.

Build a lexical player-weapon Lua-to-Rust ID index from the exact inventoried
files:

```text
python scripts/itb_weapon_coverage.py \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  "B:\SteamLibrary\steamapps\common\Into the Breach"
```

The second argument is the installation's content root (the directory
containing `scripts/`). The tool reads and hash-verifies all 14 selected Lua
files, masks Lua comments and strings, extracts active global constructor and
alias candidates, and joins them to direct `wid_from_str` arms. Plain-literal
Rust `|` alternatives are expanded one-for-one; unsupported match shapes still
fail closed. It emits JSON to stdout and never writes to the installation. An
exact ID match is not a claim about Rust weapon definitions, simulator behavior,
or conformance.

## Windows PE named anchors

Create a conservative string/address candidate map outside the game:

```text
python scripts/itb_pe_anchor_map.py \
  --executable "<Into the Breach>/Breach.exe" \
  --inventory data/observatory/inventories/<matching-snapshot>.json \
  --output data/observatory/native/<build-keyed-name>.json
```

The executable must match the supplied inventory's size, SHA-256, format, and
architecture. File output is restricted to direct children of this repository's
`data/observatory/native/` directory and uses atomic replacement; use stdout for
other workflows. Existing non-anchor artifacts, symlinks, game paths, bridge
paths, and session paths are never overwritten. The map contains no binary
bytes or decompiled source: string locations are facts, while pointer-shaped
values in executable sections remain explicitly labeled reference candidates
until a decoder and control-flow analysis confirm them. Named Lua C-API imports
and their IAT-slot RVAs are parsed as direct PE facts to support that later
control-flow work.

## Reviewed Windows PE boundaries

After focused decoding promotes candidate anchors, store only normalized
addresses, region SHA-256 values, decoded call edges, classified findings, and
explicit limitations in a `pe_reviewed_boundary_map`. Do not store executable
bytes or decompiled source. Verify the committed build-keyed artifact against
the exact PE and matching inventory:

```text
python scripts/itb_pe_boundary_map.py \
  --executable "<Into the Breach>/Breach.exe" \
  --inventory data/observatory/inventories/<matching-snapshot>.json \
  --evidence data/observatory/native/<build-keyed-boundaries>.json
```

Schema 1 verification requires the Python package `capstone==5.0.7`, matching
the decoder recorded in the artifact; a different version fails closed.

Validation fails closed on identity drift, unknown fields, malformed evidence,
region or summary mismatch, non-executable or non-file-backed ranges, changed
function hashes, incomplete Capstone 5.x decoding from a declared reviewed
region start, calls that do not begin on instruction boundaries relative to
that start, and mismatched IAT imports.

The verifier does **not** independently discover x86 function entries or prove
control-flow reachability. A shifted declared start can reframe embedded bytes,
so region starts and extents remain reviewed analyst evidence backed by Ghidra
and focused Capstone analysis. A successful result proves exact identity, bytes,
and decoding consistency conditional on those reviewed boundaries; it does not
turn a semantic inference into a runtime fact.

For Ghidra headless work, keep the project outside the repository in a path
keyed by the full executable SHA-256. The reusable
`scripts/ghidra/ExportItbBoundaryFacts.java` post-script emits deterministic TSV
function extents, hashes, calls, and references for explicitly supplied labeled
addresses. Treat that output as review input and publish only normalized JSON
whose identity, bytes, and declared-boundary-relative calls pass the verifier.

## Native enemy record selector boundary

`native/windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json`
continues the reviewed PE map through the complete post-callback enemy record
tournament. It binds ten function regions, nine normalized control windows,
17 direct calls, both default records, and RNG caller IDs 29 through 33. The
24-byte record is exactly six signed 32-bit integers: destination `(x,y)`,
target `(x,y)`, target score, and positioning score.

The parameterized replay preserves the native oddities instead of replacing
them with a cleaner policy. Scores below positioning `-10` are rejected;
strictly positive positioning beats strictly negative positioning regardless
of target score; all other comparisons are descending target score then
positioning score. Each strict improvement replaces the fallback with the
immediately displaced primary group, so that group is not a recomputed global
second best. Every nonempty primary spends a shared-CRT draw, including a
singleton. A nonempty displaced group then spends a 1-in-4 gate draw and, on
remainder zero, samples without replacement until it finds a positive-target,
nonnegative-position stock-interior record or exhausts the group.

The target-tie replay begins after callback/effect-side draws for one
destination. The record-selector replay begins after every complete candidate
record has been materialized. Neither API claims to reconstruct upstream Lua
subclass logic or provide an ordinary future-enemy solver input.

The later build-keyed runtime campaign under
`captures/windows_build_13725832_owner_local_modified_20260824_enemy_tournament_hw/`
provides one complete parameterized conformance vector. A no-detour x86
hardware observer copies the ordered records at selector entry, reads the
pinned shared CRT owner state before and after selection, and then captures the
selected record and immediate queue commit. Three fresh-process,
counterbalanced control/dormant/armed triplets all produce the same eight
records. Starting from `0xd6ac62fb`, exact replay consumes one caller-30 draw,
selects input 5, and reaches `0x6f5d21d2`; destination `[5,4]`, target `[4,4]`,
and skill 1 bind to the settled Firefly1 queue. All nine whole-game outcomes
share the same semantic hash, and the cleanup receipt proves the exact save,
Mod Loader, installation, bridge, and process restore.

The campaign receipt is
`windows_build_13725832_owner_local_modified_20260824_enemy_tournament_hw_receipt.json`;
its matching `_cleanup_receipt.json` closes the pending restore fields. The DLL
is deliberately omitted, while its reproducible build receipt and exact
hardware-breakpoint plan are committed under `native/`. This bounded capture
does not reveal each upstream Lua PointList, SkillEffect, callback value,
target-tie state, or candidate-time Board predicate, and it does not generalize
to other enemy, weapon, cancellation, or retarget paths. Ordinary solver input
still lacks both the prospective vector and selector-entry state, so the live
settled queue remains authoritative.

The subsequent one-family archive under
`captures/windows_build_13725832_owner_local_modified_20260824_enemy_target_area_callback/`
binds one upstream Lua payload to that tournament. Three fresh-process
control/exact pairs use condition orders control/exact, exact/control, and
control/exact. Every control contains zero observations; every exact trace
contains the same nine ordered `FireflyAtk1:GetTargetArea` calls with zero
drops, serialization errors, or restore conflicts. Calls 0–7 originate at the
eight native candidate destinations in exact order. For each origin `(x,y)`,
the returned list is
`[(x,y-1),(x+1,y),(x,y+1),(x-1,y)]`, and the corresponding native candidate
target is list index 3. Call 8 repeats selected input 5's `[5,4]` origin and
PointList. All paired whole-game outcomes share the tournament's semantic hash.

The immutable receipt is
`windows_build_13725832_owner_local_modified_20260824_enemy_target_area_callback_receipt.json`;
its matching `_cleanup_receipt.json` binds byte-identical pre/post 32-file save
manifests, exact restoration of the campaign's prior 315,686-byte Mod Loader,
removal of ten active-install experiment files and two bridge artifacts, and a
stopped game. The post-cleanup executable, six native libraries, 305 scripts,
and 377 maps equal the prior post-tournament content inventory; the changing
Steam appmanifest evidence hash is reported separately. This is deterministic
cross-campaign correlation for one fixed Firefly shape, not a same-process
dual-observer causal trace, a universal callback grammar, or a prospective
solver input.

The following one-family archive under
`captures/windows_build_13725832_owner_local_modified_20260824_enemy_target_score_callback/`
isolates `FireflyAtk1:GetTargetScore` for the same fixed scenario. Three fresh-
process control/exact pairs again use control/exact, exact/control, and
control/exact orders. Controls contain zero calls; every exact trace contains
the same 32 calls, zero integrity errors, and complete restoration of all 65
callback slots. The 15 score slots are the only installed family.

Those calls are eight consecutive groups of four. Each origin and target order
matches target-area calls 0–7, and all eight raw score vectors are
`[0,0,0,5]`. The unique raw best at index 3 equals the corresponding native
record target, and both its callback return and native target score are 5. The
separate target-area call 8 repeats selected destination `[5,4]`; no ninth score
group appears. This is bounded deterministic correlation across separately
matched campaigns, not a same-process causal ordering. Post-wrapper values for
the three losing targets, the native equal-best set and caller-29 state,
SkillEffects, and candidate-time Board predicates remain open.

The immutable target-score receipt is
`windows_build_13725832_owner_local_modified_20260824_enemy_target_score_callback_receipt.json`.
Its cleanup receipt binds byte-identical pre/post 32-file save manifests, exact
restoration of the prior 315,686-byte Mod Loader, removal of ten active-install
files and seven bridge artifacts, and a stopped game. A retained-output guard
rejected one pair-002 control attempt before any game command; its immutable
diagnostic is explicitly excluded from the six accepted trials. Post-cleanup
game content matches the target-area baseline except for separately reported
mutable appmanifest evidence. The later raw-effect and native-materialization
campaigns close the fixed selected effect but ordinary solver input still
cannot construct the prospective callback state, so simulator v408 is
unchanged.

The one-family archive under
`captures/windows_build_13725832_owner_local_modified_20260824_enemy_skill_effect_callback/`
isolates `FireflyAtk1:GetSkillEffect` in the same shape. Three counterbalanced
control/exact pairs capture the same 33 raw effects with zero drops/errors and
matched semantic outcomes. Calls 0–31 match the 32 score arguments; call 32
repeats selected score-side call 23 and the same process settles its `[3,4]`
impact. The immutable receipt and matching cleanup receipt bind the complete
trace, exact loader/save restore, 689/689 content match, and stopped game.

The no-detour hardware archive under
`captures/windows_build_13725832_owner_local_modified_20260824_enemy_materialized_effect_hw/`
continues selected input 5 through the native postprocess seam at RVA
`0x00268323` and its queue commit. Three fresh-process condition orders—
control/dormant/armed, armed/dormant/control, and dormant/control/armed—capture
the same owner/source ancestry `1303/6`, origin `[5,4]`, target `[4,4]`, and one
queued one-damage `ExploFirefly1` record at `[3,4]`. All nine successful
outcomes share semantic SHA
`957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673`;
all integrity counters are zero and native state restores completely.

The immutable receipt is
`windows_build_13725832_owner_local_modified_20260824_enemy_materialized_effect_hw_receipt.json`;
its matching `_cleanup_receipt.json` binds the two excluded rejected
diagnostics, exact 32-file pre/post save, restored 315,686-byte baseline loader,
689-entry post-cleanup inventory, zero active experiment/bridge residue, and
stopped game. The generated DLL is omitted; its reproducible build receipt and
exact hardware-breakpoint plan are committed under `native/`. This is a fixed
selected-path proof, not prospective input or a universal effect grammar.

Verify the immutable artifact against the pinned executable and replay a
captured record payload with:

```powershell
python scripts/itb_observatory_enemy_record_selector.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json

python scripts/itb_observatory_enemy_record_selector.py replay-selector `
  --records records.json `
  --rng-state 0x12345678
```

## Native enemy candidate-score boundary

`native/windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json`
closes the native arithmetic immediately around `ScorePositioning` and
`GetTargetScore`. It binds 16 exact code regions, 16 instruction windows,
eight direct calls, 15 string/data anchors, two Lua method bindings, and 14
adversarial replay vectors. Its raw SHA-256 is
`c94f87833efafec1217eefd0b5aeef61dd79e46fb3c1255c558259af64596ad0`;
its canonical document SHA-256 is
`c0eeed00ebb646371d3ca33cac9d1c52224bb67025d1b6e6fa41a74115a7a457`.

The prior anonymous positioning fields are `bInjured` at Pawn `+0x8d6` and
current `health` at `+0x8a8`. Ordinary enemy planning passes mode zero; only
`debugai` passes one. A moved, injured, one-HP pawn therefore has every
nonnegative `ScorePositioning` result replaced by zero in normal planning,
while a negative result survives. The selected weapon at `+0x948` is reset to
zero when it is non-minus-one and outside the weapon vector.

The native target-score wrapper assigns a `-5` modifier when the target equals
`targetHistory`, or `+10` when it equals `priorityTarget`; priority wins when
both points match. It calls Lua only for an in-range selected weapon or the
separate literal-index-50 resolver path. With a negative modifier, a positive
callback score no greater than the penalty floors to one; other sums use
signed 32-bit arithmetic.

These are parameterized inner-boundary replays. They require the Lua callback
result, target points, pawn state, weapon vector count, and route as inputs;
they do not construct a target area or forecast a whole enemy phase. Verify
the immutable artifact and replay JSON payloads with:

```powershell
python scripts/itb_observatory_enemy_candidate_score.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json

python scripts/itb_observatory_enemy_candidate_score.py replay-positioning `
  --payload positioning.json

python scripts/itb_observatory_enemy_candidate_score.py replay-target-score `
  --payload target-score.json
```

The positioning payload contains exactly `raw_score`, `injured`, `moved`,
`current_health`, and `mode`. The target-score payload contains exactly
`weapon_index`, `weapon_count`, nullable `callback_score`, `target`,
`target_history`, and `priority_target`.

## Native enemy target-area gate

`native/windows_build_13725832_31fe35265598_enemy_target_area_boundary.json`
continues immediately before the Lua `GetTargetArea` callback. It binds 26
exact code regions, 18 instruction windows, 13 direct calls, three complete
raw-call inventories, 16 string/data anchors, five Lua method bindings, and 17
adversarial replay vectors. Its raw SHA-256 is
`5ccb768da7e11df3e07dc5fca7fac55398bec51dde0c3f3d5f4b0df54d3ec08b`;
its canonical document SHA-256 is
`80b8f425daacfc82e5a320e9922bcd60d7c3ff676e400ea7e21d72e230d5f009`.

For ordinary mode zero, the exact gate is `IsActive`, not disabled by Smoke,
not a grounded nonflying Pawn in Water, `iBonusShift <= 0`, and either a usable
vector Skill or `IsMech`. Debugai mode one bypasses an ordinary failure. Smoke
requires an attached Board smoke tile and `not IsBusy`, then is suppressed by
either `IgnoreSmoke` or `Disable_Immunity`. Water is registered as terrain
value 3 and blocks only when `not IsBusy` and `not IsFlying`.

The usable-skill scan excludes exact IDs `Move` and `Move_Power`; every other
Skill is usable when `Limited == 0` or remaining uses at `+0x158` are positive.
Literal weapon index 50 is now named exactly: the resolver checks it before
vector bounds and returns a separately owned `Skill_Repair` shared pointer at
SkillManager `+0x68`, constructed from the shipped Lua symbol of the same name.
It is not vector slot 51. The candidate loop still rewrites selected index 50
to zero when the actual vector count is at most 50.

The exact 152-file shipped `.lua` census finds 206 visually matching one-line
`SkillList={...}` forms, but eight are inside block comments. The active result
is 198 assignments with arities 0/1/2 distributed 26/161/11 and maximum active
literal arity two. That source maximum supplies no stock literal route to a
vector count above 50, but it is deliberately not promoted to a universal
runtime bound across native equipment, save overlays, or mods.

Verify the immutable artifact and replay either the usable scan or the whole
pre-callback gate with:

```powershell
python scripts/itb_observatory_enemy_target_area.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_target_area_boundary.json

python scripts/itb_observatory_enemy_target_area.py replay-usable `
  --payload usable-skills.json

python scripts/itb_observatory_enemy_target_area.py replay-gate `
  --payload target-area-gate.json
```

The replay stops at whether native code invokes Lua. The later bounded
Firefly campaign captures one concrete ordered `GetTargetArea` sequence, but
other subclasses, later callback scores/effects, and prospective enemy-phase
state remain explicit runtime inputs. Rust still uses the settled live queue,
so simulator v408 remains current.

## Native enemy target-area callback wrapper

`native/windows_build_13725832_31fe35265598_enemy_target_area_callback_boundary.json`
continues through the native wrapper after the preceding eligibility gate. It
binds nine complete functions, 15 instruction windows, 13 direct calls, one
tail jump, both complete six-site direct-caller inventories, four data anchors,
one additional instruction anchor, and 12 adversarial replay vectors. Its raw
SHA-256 is
`dc45fc0a32b52cff2e6fb400857fadeca85737f8329e9d32f5e6196e77ec6289`;
its canonical document SHA-256 is
`bcac4ea3c6a6e5cec73d95ea27f0edab5ef592de09d135200ea5efb8b66c405f`.

`Skill +0x110` is now joined to the Board `+0x0c` secondary/path-manager
interface. `Board:AddPawn` passes that adjusted pointer to the SkillManager,
which writes it to every vector Skill and the separately owned repair Skill;
vtable slot `+0x14` is an exact `this -= 0x0c` thunk to `Board:IsValid`.

The wrapper stores the origin before testing it. An invalid origin invokes no
Lua callback, move-assigns an empty PointList over the old Skill target cache,
and returns empty. For a valid origin it invokes `GetSecondTargetArea` only
when `TwoClick` is true and neither stored second-target coordinate equals
`-1`; otherwise it invokes `GetTargetArea`. Values below `-1` do not fail that
second-target sentinel test.

After the selected callback returns, native code replaces the cache and erases
only points with negative x or y. Encounter order and duplicates survive, as
do nonnegative coordinates beyond the current Board dimensions. The replay
therefore accepts the selected callback's already-materialized ordered
PointList explicitly. Lua point construction remains a general input boundary;
the later target-area campaign supplies one fixed Firefly1 runtime vector
without claiming other subclasses or board states.

Verify or replay the immutable boundary with:

```powershell
python scripts/itb_observatory_enemy_target_area_callback.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_target_area_callback_boundary.json

python scripts/itb_observatory_enemy_target_area_callback.py replay `
  --payload target-area-callback.json
```

The payload contains exactly `board_width`, `board_height`, `origin`,
`cached_points`, `two_click`, `second_target`, `get_target_area_points`, and
`get_second_target_area_points`. Supply only the callback output selected by
the branch, or `null` for both outputs when the origin is invalid. The adjacent
native SkillEffect materialization body remains a separate continuation; no
Rust semantic or simulator-version change follows from this wrapper alone.

## Native enemy SkillEffect materialization boundary

`native/windows_build_13725832_31fe35265598_enemy_skill_effect_boundary.json`
continues from the cached target PointList through the native SkillEffect
cache body. It binds 16 complete reviewed functions, 14 instruction windows,
13 direct calls, both complete direct-caller inventories, 16 string/vtable
anchors, two additional instruction anchors, and six adversarial replay
vectors. Its raw SHA-256 is
`bd8fe003c19d8440569a7a6fb0ba1524481280e4f5dc31afdb5d93a2bc5d9c13`;
its canonical document SHA-256 is
`d3502ffc37ce5fb0a685e6df3587173f2076f0701e944dbd4888ee0f46711bdd`.

The selected target must occur exactly in the cached PointList. A miss resets
the selected target to `(-1,-1)`, invokes no Lua effect callback, clears both
cached record vectors, resets `SkillEffect.iOwner` to `-1`, and clears its
private Skill key. A hit uses `GetFinalEffect_Helper` only when `TwoClick` is
true and both second-target coordinates differ from literal `-1`; its exact
ordered PointList is `[origin, second target, selected target]`. All other
hits use `GetSkillEffect(origin, selected target)`.

The selected Lua result replaces the whole cache. Native code then walks both
`effect` and `q_effect`: an empty `sAnimation` defaults from `Explosion`, a
private origin of exactly `(-1,-1)` defaults from the Skill origin, and the
private source tag is overwritten from `Skill +0x150`. It writes owner and
Skill key before postprocessing both vectors. Vek Hormones and Boost damage
arithmetic, exact `Move`/`Move_Power` exclusions, special values `500`/`1000`,
signed wrapping, and the private boost marker are replayed in native order.

Verify or replay the immutable boundary with:

```powershell
python scripts/itb_observatory_enemy_skill_effect.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_skill_effect_boundary.json

python scripts/itb_observatory_enemy_skill_effect.py replay `
  --payload skill-effect-projection.json
```

The replay accepts only the fields this native body reads or writes; the
concrete Lua-produced `SkillEffect` is an explicit projected input. The exact
eight direct callers identify this body as a Board/SkillManager/Skill cache
materializer, not the enemy candidate scorer itself. The selected hardware
campaign above validates one fixed postprocessed Firefly1 payload through its
settled queue. Other subclasses/materialization routes and a prospective enemy
phase remain unresolved; the source-keyed successor below separately closes
score-side call ancestry. Simulator v408 remains current.

## Enemy score-to-SkillEffect source ancestry

`callbacks/windows_build_13725832_31fe35265598_enemy_score_effect_ancestry.json`
joins the native score callback boundary to every active shipped Lua
`GetTargetScore` definition. It verifies 152 analysis-relevant Lua files while
deliberately excluding the project-owned `scripts/modloader.lua` overlay. The
artifact's raw SHA-256 is
`517c6fe435bc4a5cd6d50acad1693ba6241bb97c41171ab4823e3c87d8b0a179`;
its canonical document SHA-256 is
`720f721d71869bcba25479410e124e666626d2b570c0dd3e5fb00acc50a86887`.

The tree contains exactly 20 active `GetTargetScore` definitions across 15
files. Four—`Skill`, both Centipedes, and the Mosquito boss—directly call the
actual `self:GetSkillEffect`. Shaman reaches the actual Totem effect indirectly
through four inherited `TotemAtk1:GetTargetScore` evaluations after its gates.
Dung, Scarab boss, Starfish boss, and Blobber score deliberately synthetic
local effects. The remaining eleven use constants or direct Board/deploy
logic without scoring an effect payload.

This resolves the score-side ancestry: `Skill:GetTargetScore` dispatches
`self:GetSkillEffect` directly in Lua and does not transit through the native
Skill cache materializer at RVA `0x00268050`. None of the 20 active score
bodies calls `GetFinalEffect` or `GetFinalEffect_Helper`. Across all 186 active
`GetSkillEffect` definitions, there are also zero direct calls to
`random_int`, `random_bool`, `random_element`, or `random_removal`.

Build or verify the immutable artifact with:

```powershell
python scripts/itb_observatory_enemy_score_effect_ancestry.py verify `
  --content-root "<Into the Breach>" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --callback-index data/observatory/callbacks/windows_build_13725832_31fe35265598_callback_index.json `
  --ancestry-map data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_effect_ancestry.json
```

The zero-RNG result is lexical and direct-call scoped. Native constructors or
Board/effect helpers reached transitively from those bodies are not yet proven
RNG-free, and future callback Board inputs/effect payloads still are not
ordinary bridge state. The settled enemy queue remains authoritative and
simulator v408 remains current.

## Enemy base ScoreList semantics

`callbacks/windows_build_13725832_31fe35265598_enemy_score_list_semantics.json`
pins the exact shipped `Skill:GetTargetScore`, `isEnemy`, and `Skill:ScoreList`
bodies and turns their source arithmetic into a strict projected replay. Its
raw SHA-256 is
`a990c1ae3648618651c65096339a8a5f24d44407c422324c8cf43ac30dab11a6`;
its canonical document SHA-256 is
`4871a8f128211e258f6737b2c221e5f73789a021a95ecd995e5d5a3a86566d60`.

The replay preserves source order rather than replacing it with a simplified
scoring policy. Movement is handled first and accumulates an explicit
`ScorePositioning` result. Non-grid structures precede Pawn-team checks. A
positive hit on a same-team Frozen target scores as an enemy only while that
target is not already targeted. A dead or temporary hostile Pawn assigns
`ScoreNothing` to the whole accumulated score instead of adding it. Powered
building damage follows, then an instant-only Time Pod veto, then the ordinary
`ScoreNothing` fallback. A final positioning sum strictly below `-5` replaces
the ordinary score.

Base `Skill:GetTargetScore` scores `q_effect` before `effect`. An instant score
strictly below `-20` returns `-100`; otherwise an empty queued vector uses the
instant score and every nonempty queued vector uses the queued score. Build or
verify the immutable artifact with:

```powershell
python scripts/itb_observatory_enemy_score_list_semantics.py verify `
  --content-root "<Into the Breach>" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --semantics-map data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_list_semantics.json
```

The replay consumes already-resolved Board/Pawn predicates and an explicit
`ScorePositioning` Lua number only where the source calls that function;
half-points from melee distance scoring remain fractional in this direct Lua
route. It does not invent future candidate state, evaluate the 19 custom score
overrides, or forecast a whole enemy phase. The settled queue remains
authoritative and simulator v408 remains current.

## Enemy ScorePositioning semantics

`callbacks/windows_build_13725832_31fe35265598_enemy_score_positioning_semantics.json`
continues the base score replay through the exact shipped global
`ScorePositioning` body. It also joins the exact `Breach.exe` callback wrapper
and named integer invoker to the installed `lua5.1.dll` `lua_tointeger` body.
Its raw SHA-256 is
`39da06fce775a06c5a8aed53ba004fab89e911811edf11c13977d2b87c472bb2`;
its canonical document SHA-256 is
`e6375c6d0ea6d8708db90e940aaefef35184315b81a6f9fd4233a11548b8d615`.

The projected replay preserves the complete source order: Pod, grounded Hole,
targeted danger score, Smoke, new Fire, spawning, generic mission danger,
avoided dangerous item, grounded Water, custom Pawn score, stock corner/edge,
then melee or ranged positioning. The ACID penalty line is commented out.
Custom score precedes the hard-coded `0`/`7` edge policy. A player Pawn selects
`TEAM_ENEMY`; every other team selects `TEAM_PLAYER`, exactly matching the
source's binary-team caveat.

Melee scoring checks four `DIR_START=0` through `DIR_END=3` slots in order,
testing the selected-team Pawn before a Building at each slot. With no adjacent
match it returns
`max(0,(10-min(distance-to-Pawn,distance-to-Building))/2)`, preserving
half-points for direct Lua consumers. Ranged interior positions return five.

The native callback route is deliberately separate. The pinned
`lua_tointeger` body loads the Lua double and executes x87 `FISTP`; its result
therefore depends on the active thread rounding-control mode. The immutable
static artifact replays all four x87 modes exactly. The later build-keyed
runtime campaign in
`captures/windows_build_13725832_owner_local_modified_20260824_score_positioning_x87/`
resolves the observed mode for this exact Windows build: three fresh-process,
counterbalanced control/dormant/armed triplets each captured one
`ScorePositioning -> named integer invoker -> integer helper -> lua_tointeger`
conversion immediately before `FISTP`. All three recorded control word
`0x027F` (`639`), whose rounding-control bits select nearest-even. All six
control comparisons matched semantically with zero differences, and every
armed snapshot reports complete debug-register/VEH/file/seam restoration. The
campaign and cleanup receipts are
`windows_build_13725832_owner_local_modified_20260824_score_positioning_x87_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260824_score_positioning_x87_cleanup_receipt.json`.
The capture-time project bridge is separately admitted to predecessor
source-tree verifiers as the 338,859-byte
`score_positioning_x87_project_bridge` overlay with SHA-256
`0ad8f0c65ad25a646b16439a57bfd0e47d21f6b4b3ba4b8a5c8b5bac77775989`;
the cleanup receipt proves the prior 315,686-byte installed bridge was restored
without rewriting that historical v408 overlay identity.
The later enemy-tournament bridge is independently admitted as the
357,175-byte `enemy_tournament_hw_project_bridge` overlay with SHA-256
`1abb8001eb6402c26d59fb09c05c78159a9199267130eecf9c73ccfd7879a5ac`;
its own cleanup receipt again proves the same 315,686-byte installed bridge was
restored. The subsequent one-family trial bridge is admitted as the
365,924-byte `enemy_target_area_callback_project_bridge` overlay with SHA-256
`07af106b8cc2abab88fd215ed0ddfe04fc138ba9c4987f2500a445509898071d`;
its cleanup receipt independently proves the same owner-installed baseline was
restored after the target-area campaign, and the later target-score campaign
reused that exact source overlay before independently restoring the same
baseline again. The selected-materialization campaign's final project bridge
is separately admitted as the 389,371-byte
`enemy_materialized_effect_hw_project_bridge` overlay with SHA-256
`232a2cd312c439652bf95b2dd2a9c56b4a65d17cc38c6e43666e983dbe9cf038`;
its cleanup receipt proves the exact baseline was restored again. All four
later overlay identities remain
immutable exact-hash exceptions for predecessor source-tree verifiers rather
than rewrites of their published artifacts.
This is an exact-build ordinary-callback observation, not a claim about every
future process or other Lua integer conversion. Build or verify the static
replay with:

```powershell
python scripts/itb_observatory_enemy_score_positioning.py verify `
  --content-root "<Into the Breach>" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --semantics-map data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_positioning_semantics.json
```

The dependent
`native/windows_build_13725832_31fe35265598_enemy_position_score_helpers_boundary.json`
closes the two native Pawn helpers for unmodified shipped definitions. Its raw
SHA-256 is
`989c2d74194b810e14ae8327b17cbaa9535a8ec83acedefad951bc9ad77c8ff9`;
its canonical document SHA-256 is
`9f572158d5e8dc760974166a4ad6a21f68a68324d0ec6d97eb6f8d02d4fa3cd9`.
The exact registrations bind a 57-byte `GetDangerScore` member and a 147-byte
`GetCustomPositionScore` member. The former constructs `GetScoreDanger`; the
latter invokes literal `GetPositionScore(point)`. Pinned `CreateClass(Pawn)`
source generates both getters from `ScoreDanger = -10` and
`PositionScore = 0`. All 152 inventoried shipped Lua files (the local
`modloader.lua` is deliberately excluded) contain no explicit field or getter
override, so those two stock results are exact and x87-rounding invariant.
Build or verify the helper artifact with:

```powershell
python scripts/itb_observatory_enemy_position_score_helpers.py verify `
  --content-root "<Into the Breach>" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_position_score_helpers_boundary.json
```

The second dependent artifact,
`native/windows_build_13725832_31fe35265598_enemy_position_observations_boundary.json`,
pins all 17 named Board/Pawn observations used by `ScorePositioning`, 22 native
regions, and the exact current-state carrier matrix. Its raw SHA-256 is
`5be65abbb996582666fca63fa6028431599627eeef24e4967cb524805de4ec8a`;
its canonical document SHA-256 is
`f7871672fac450ff60196638bb35e28fb865f11844ce2cab76e9ba8bcafc8329`.

`Board:IsDangerous` is a native tile flag plus two Point vectors, not
`Board:IsEnvironmentDanger`. `Board:IsDangerousItem` tests item presence and
eight embedded `SpaceDamage` conditions: damage, non-`DIR_NONE` push, shield,
fire, smoke, spawned Pawn, ACID, or frozen. Spawning is a tile flag or Point-
vector membership. Distance to a selected-team Pawn is Manhattan under exact
profile six; distance to a Building is Manhattan over the native cache rebuilt
from every terrain-1 tile. Current bridge fields now directly carry both
dangerous predicates and the live ordered Ranged/AvoidingMines values in
addition to the earlier exact current observations. The immutable current-only
receipt
`captures/windows_build_13725832_owner_local_modified_20260829_mission_power_turn1_current_position_carriers.json`
(SHA-256 `507a7cc3afc4a550174a1e83043a0cb2b9b65bc92c8112a0dbdb6a95b4c12a13`)
seals a stable before/after bridge/native sandwich: all 64 item-danger booleans,
ten ordered on-board Pawn flag records, no dangerous or dangerous-item points,
and the same four ordinary spawn candidates. Its installed overlay identity is
SHA-256 `42a0b9d49d1a95d9cea3dc716f0e68c60533e6b15b112ae993556c85b6ebfbec`
at 396,449 bytes. The Board snapshot at each future callback remains explicitly
unavailable. Verify the static boundary with:

```powershell
python scripts/itb_observatory_enemy_position_observations.py verify `
  --content-root "<Into the Breach>" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_position_observations_boundary.json
```

The native observation meanings and current-state carrier matrix are closed.
The candidate-time Board snapshot remains an explicit input. For this exact
Windows build, the observed callback-time x87 mode is
nearest-even; a new process is still re-observed rather than assumed when its
identity or control state is not bound. This local replay does not forecast the
enemy tournament or replace the settled queue; the Rust simulator consumes the
settled queue rather than executing `ScorePositioning`, so simulator v408
remains current.

## Native path and reachability boundaries

`native/windows_build_13725832_31fe35265598_path_boundaries.json` is the
separate exact-build movement map. It pins the Lua bindings for
`Board:GetSimpleReachable`, `Board:GetReachable`, `Board:GetPath`,
`Board:IsBlocked`, and `Pawn:GetPathProf`; all seven relevant `PATH_*`
constants; the Board grid-search vtable; 12 reviewed native regions; and the
control windows needed to separate transit from destination blocking.

For this build, `Pilot_Hotshot` selects `PATH_ROADRUNNER=4`. Profile 4 expands
through live occupied pawn tiles, but the later `Board:IsBlocked` filter keeps
those tiles out of the returned destinations. It remains subject to
directional walls and is not flight. Simulator v401 applies that exact
transit/stop distinction to ordinary and fixed-budget movement.

Verify the immutable map against the pinned executable with:

```powershell
python scripts/itb_observatory_path_boundaries.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --path-map data/observatory/native/windows_build_13725832_31fe35265598_path_boundaries.json
```

The follow-up
`native/windows_build_13725832_31fe35265598_path_cost_ordering.json` closes the
remaining offline cost/order branch for this build. It pins 26 reviewed code
or table regions and 14 control windows, including the native direction order
`(0,-1), (1,0), (0,1), (-1,0)`, unit-cost `GetReachable`, strict-improvement
predecessors, lexicographic `(x,y)` reachable output, and `GetPath`'s
`g + 1.01 * Manhattan` min-heap with `(x,y)` tie-breaking. Distinct-point
paths include both endpoints; a requested endpoint alone may bypass the normal
traversal rejection.

The same proof closes ordinary team handling and one solver-relevant uncommon
profile edge: low profiles 0/2 compare pawn identity without a team branch,
and `PATH_MASSIVE=2` can both cross and stop on Water. Simulator v402 corrects
ordinary Massive/Hotshot Water movement and archives the pre-v402 corpus as
`recordings/failure_db_snapshot_sim_v401.jsonl`.

Verify the immutable follow-up map with:

```powershell
python scripts/itb_observatory_path_cost_ordering.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --path-cost-map data/observatory/native/windows_build_13725832_31fe35265598_path_cost_ordering.json
```

The third exact-build map,
`native/windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json`,
joins the shipped `Pawn:IsDead` and `Pawn:IsCorpse` bindings to counted tile
occupancy, ordinary traversal, the concrete Board path-manager vtable, and
destination filtering. Mode 1 counts exactly a live pawn or a dead pawn whose
`IsCorpse()` predicate is true. Ordinary paths therefore block persistent
corpses but ignore a retained transient dead non-corpse; Road Runner may cross
a persistent corpse but the common destination filter still forbids stopping
there. Simulator v403 adds live/static lifecycle fields, source fallbacks,
path-only occupancy, projected-checkpoint preservation, and focused Rust/Python
regressions without changing broad same-effect corpse collision behavior. The
pre-v403 corpus is `recordings/failure_db_snapshot_sim_v402.jsonl`.

Verify the lifecycle map with:

```powershell
python scripts/itb_observatory_path_occupancy_lifecycle.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --path-occupancy-map data/observatory/native/windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json
```

The later corpse-classification artifact closes the common predicate and every
effective shipped `Corpse=true` definition. Multi-frame lifecycle-state and
transient-pawn removal timing, matched output vectors, and `AddMove`
step/scheduler effects remain dynamic or mismatch-driven questions.

## Native RNG return-address IDs

Build or verify the complete raw-call catalog only against the exact executable,
inventory, and reviewed boundary map:

```text
python scripts/itb_rng_return_map.py build \
  --executable "<Into the Breach>/Breach.exe" \
  --inventory data/observatory/inventories/<matching-snapshot>.json \
  --boundaries data/observatory/native/<build-keyed-boundaries>.json \
  --output data/observatory/native/<build-keyed-rng-return-ids>.json

python scripts/itb_rng_return_map.py verify \
  --executable "<Into the Breach>/Breach.exe" \
  --inventory data/observatory/inventories/<matching-snapshot>.json \
  --boundaries data/observatory/native/<build-keyed-boundaries>.json \
  --catalog data/observatory/native/<build-keyed-rng-return-ids>.json
```

ID 0 is reserved for an executed caller absent from the catalog. IDs 1..N are
assigned by sorted call RVA. The raw scan intentionally includes opcode-looking
bytes that may not be reachable instructions; only exact reviewed boundary-map
edges receive semantic labels. A native diagnostic stores the small ID, never
the absolute return address. Any observed ID 0 invalidates complete caller
attribution. File publication is create-only and restricted to direct JSON
children of `data/observatory/native/`; omit `--output` to use stdout elsewhere.

## RNG seed control and runtime evidence

`native/windows_build_13725832_31fe35265598_rng_seed_helper_receipt.json`
attests the reproducible one-purpose x86 seed-control helper. The helper source
and builder are committed; the generated DLL is intentionally not. Two clean
builds produced the same module and normalized receipt bytes. The helper is not
an observer or detour and exposes only the exact build-keyed seed operation.

`captures/windows_build_13725832_owner_local_modified_20260821_rng_pair004_rejected_receipt.json`
binds the first completed control/exact `_G.random_int` pair. It is negative
evidence: the wrapper restored correctly and emitted one finalized event, but
the unseeded fresh processes produced different probes and bridge outcomes.
Consequently it is rejected from neutrality evidence and motivated the seeded
schema-v2 protocol. That protocol accepts exactly one selected one-argument Lua
RNG family per pair (`random_int` or `random_bool`), verifies the pinned CRT
first-draw result with the correct integer/Boolean type, and keeps the other
family disabled.

`captures/windows_build_13725832_owner_local_modified_20260821_seeded_rng/`
contains pairs 007 through 012 and their finalized traces. The campaign receipt
binds three pairs per RNG family with counterbalanced condition order. All six
direct results matched; only two whole-game outcomes matched, while four
differed at the spawning-tile y coordinate. Treat the campaign as proof of
direct return preservation and exact restoration, not whole-game neutrality or
native spawn-selection semantics. The later
`captures/windows_build_13725832_owner_local_modified_20260822_native_campaign_cleanup_receipt.json`
closes the campaign receipt's then-pending install restoration: all 689 accepted
install entries and the sealed 33-file owner save now match exactly.

## Native RNG observer artifacts

`native/windows_build_13725832_31fe35265598_rng_core_observer_receipt.json`
attests two byte-identical builds of the 19,968-byte native observer (module
SHA-256
`8ef711798bd9d37fbff5e75eaac17c27189f9c25aa6f11122cb27068b5e2184c`).
The adjacent hook-plan and restore-hash documents are
the exact externally trusted transaction inputs. The generated DLL is omitted;
the committed source and builder reproduce it.

`captures/windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic/`
contains two counterbalanced live pairs created through one atomic
`OBS_NATIVE_RNG_SEED_AND_ARM` dispatch. The exact checkpoints contain 1,481 and
1,501 records, begin with the fixed seed's first result (`24356`), bind all
callers to the committed catalog, and report exact core-byte restoration with
no unknown caller or integrity error. The exact outcomes repeat, while the two
unobserved seeded controls select different spawn coordinates. The strict
receipt
`captures/windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic_receipt.json`
therefore classifies this as restored build-keyed stream observation, not
observer neutrality or spawn-selection semantics. Rebuild the receipt with:

```powershell
python scripts/itb_observatory_native_rng_campaign.py `
  data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic
```

## Spawn-boundary evidence

`captures/windows_build_13725832_owner_local_modified_20260822_spawn_span/`
contains three source-verified `Spawner:NextPawn` spans. They establish the
ordinary three-draw order—weak class, ordered candidate choice, then upgrade—
but the first campaign intentionally did not export enough inputs to replay the
choice.

`captures/windows_build_13725832_owner_local_modified_20260822_spawn_replay/`
contains three later counterbalanced control/replay pairs. Each replay binds a
complete restored native checkpoint to the exact effective ratios, ordered
candidate array, and selected pawn. Three consecutive MSVC results recover one
observable low-31-bit pre-call state class; the two possible raw states differ
only in hidden bit 31 and have the same future observable stream. The committed
capsules reproduce `Firefly2`, `Scarab2`, and `Firefly2` exactly. One paired
outcome matches and two differ only at the later spawn coordinate. Fresh
processes were naturally seeded, so this proves exact in-span replay and clean
restoration, not native-state-matched whole-game neutrality or coordinate
selection. The later coordinate campaigns below resolve the standard
coordinate selector itself while preserving this narrower replay claim.

Rebuild the replay receipt with:

```powershell
python scripts/itb_observatory_native_boundary_campaign.py spawn_replay `
  data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_spawn_replay
```

The replay campaign receipt is closed by
`captures/windows_build_13725832_owner_local_modified_20260822_spawn_replay_cleanup_receipt.json`.
Its post-cleanup inventory matches all 689 accepted owner-local entries, the
33-file save matches its sealed tree, the baseline Mod Loader is exact, and no
Observatory file remains in the active installation or bridge.

## Spawn-coordinate and shared-RNG evidence

`native/windows_build_13725832_31fe35265598_spawn_coordinate_hw_observer_receipt.json`
attests the no-entrypoint x86 hardware observer for the reviewed scheduler,
fallback-selector, and standard-selector seams. The generated DLL is omitted;
its source, exact breakpoint plan, deterministic builder, and two-build receipt
are committed. Three counterbalanced triplets under
`captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate/`
capture the same five candidates in the same order and prove that the standard
selector uses `raw_rng % candidate_count`. The bridge spawn marker matches the
indexed candidate in every armed run. The scheduler and fallback paths were not
observed.

`native/windows_build_13725832_31fe35265598_spawn_coordinate_paths.json`
closes the corresponding offline control-flow question without claiming
runtime reachability. It pins both reviewed function hashes, all direct callers,
three literal anchors, six exact control windows, and RNG caller IDs 59, 60,
and 66. Caller 59 is the logged emergency-placement selector after the ordinary
candidate vector is empty. Caller 66 samples a supplied point vector without
replacement for opaque predicate checks and, if that path proceeds, calls the
ordinary caller-60 selector separately; it does not choose the final coordinate.
The two unobserved paths therefore need a live capture only if a concrete
solver mismatch makes their runtime inputs relevant.

`native/windows_build_13725832_31fe35265598_enemy_spawn_candidate_boundary.json`
closes the selector's candidate-construction boundary. It binds nine exact
regions, 15 instruction-aligned control windows, 16 direct edges, and six
immutable upstream artifacts. For ordinary enemies, the named `enemy` zone is
used in original Lua encounter order; if it is absent, the exact 8x8 fallback
is `(5..7, 2..5)` in x-major order. The primary filter is stable. If it is
empty on Board turn zero, the original zone is stably retried with literal
validity mode 9, which admits Forest and clears a selected Forest tile to Road.
If that retry is unavailable or empty, native code scans the whole Board in
x-major/y-minor order and retains only valid points on the greatest x row.

The same artifact pins the ordinary enemy rejection inputs: item, active pod,
temporary/permanent `BlockSpawn`, exact `Board:IsDangerous`, ground blocking,
terrain literals 5/6/Water, ACID, and existing spawn-marker membership. Smoke,
Fire, Frozen, and Targeted are not separate rejection gates on this branch.
Python and Rust replay the ordered pool from explicit candidate-time facts.
The bridge now exports the exact current ordered enemy zone, both
`Board:IsDangerous` and `Board:IsDangerousItem`,
`Board:IsBlocked(point, PATH_GROUND)`, and live ordered Pawn Ranged/
AvoidingMines observations.
The Windows-only read-only probe in
`src/observatory/native_spawn_input_reader.py` resolves the active Board through
the pinned host/Game/screen/BoardPlayer chain, then reads the complete 64-cell
Point-keyed `BlockSpawn` map and direct spawn-marker vector. It opens the
process with query/read access only, double-reads the native structures, emits
no addresses, and fails closed on build, controller, vtable, tree, vector, or
bridge-sandwich drift.

The first current-only proof is
`captures/windows_build_13725832_owner_local_modified_20260829_mission_power_turn1_native_spawn_candidate_replay.json`
(SHA-256 `680eaedea377f8c74313b717ba60c2d9a5ae4c851dbbaaec60388cfbedbdd15d`).
On a stable `Mission_Power` player-turn-one Board it observes all 64
`BlockSpawn` values as zero, an empty direct marker vector, and exactly four
ordinary candidates in native order: `[5,3]`, `[5,4]`, `[5,5]`, `[6,2]`.
This proves the complete carrier and replay path for that current snapshot. It
does not supply the Board after future player/environment changes or the shared
CRT state immediately before a future selector call, so it is not a production
spawn forecast and simulator v408 remains unchanged.

The selector-entry continuation is sealed by the content-addressed build receipt
`native/itb_observatory_spawn_coordinate_capsule_hw_observer_bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9.dll.receipt.json`
and plan
`native/windows_build_13725832_spawn_coordinate_capsule_hw_plan_e79fb1f734f06dee9862b15f29e0bbccfa82e34b3fe2506565ab56ad45d39ca1.json`.
Two independent `/Brepro` x86 builds produced the same 28,672 bytes. Machine
attestation proves a zero-entrypoint image and a 5,946-byte scalar hot section
with 1,545 decoded instructions, zero direct/indirect calls, zero Windows API
calls, and zero x87/MMX/SSE/AVX instructions. The observer installs no detour,
modifies no executable bytes, changes no page protection, and publishes no
pointer or address. As with the older Observatory helpers, the generated DLL is
deliberately omitted from the repository; the builder recreates the exact
content-addressed module.

DR3 observes the standard selector entry where `ECX` is the active Board and
the stack supplies the hidden Point result plus Pawn. The fixed capsule copies
Board width/height/turn, Pawn ID/team, all 64 tiles in x-major order, raw
pointer-free occupancy IDs, the complete Point-keyed `BlockSpawn` map, direct
spawn markers, and both native dangerous Point vectors. It records exact shared
CRT state before/after and pairs that entry one-to-one with the next DR1
fallback or DR2 standard selector draw. The strict validator rejects incomplete
maps, reordered or duplicate points, torn/restoration state, pointer leakage,
RNG-transition drift, or candidate/draw disagreement.

The separate bridge controller was first live-loaded into one fresh owner-track
game process without preparing a condition. The immutable dormant-load receipt
`captures/windows_build_13725832_owner_local_modified_20260829_spawn_coordinate_capsule_dormant_load_receipt.json`
(SHA-256 `5d3b03a5f191ab2bbf26d5c416d2e83b9e468dc1385c470b6c888374a5ab3435`)
binds the exact module, plan, build receipt, installed Mod Loader, process module
enumeration, and ACK `state=dormant consumed=false armed=false`. No prepare or
seed command ran, no breakpoint/VEH was armed, and no snapshot existed. This
proves a safely deployable dormant boundary, not a selector-time runtime
capture. The later campaign below supplies the required armed evidence.

The immutable campaign receipt
`captures/windows_build_13725832_owner_local_modified_20260829_spawn_coordinate_capsule_receipt.json`
(SHA-256 `c529484cd2bb1061ef2e3f3ccce80a61e5b9df94815b38ffcb8aa682ab7ef2a1`)
now seals three complete counterbalanced control/dormant/armed triplets. All
nine fresh processes began from the same 32-file save tree, used the exact
attested executable and three runtime modules, consumed native Continue,
executed the same three verified player actions, dispatched End Turn through
the synchronous reviewed native boundary, reached the next player turn, closed
gracefully without forced termination, and final-restored the save tree. The
receipt also binds nine isolated solver sessions and all 45 board/solve-input/
solve/threat-audit/resist-probe recording files.

Each armed trial captured exactly one complete standard-selector capsule. The
selector-entry Board carriers and ordered candidate vector were byte-identical
across all three observations (SHA-256
`5fb3354f837979a17e37a4a368f5c3dbc1459ba44b16f3f21b21e55ba026871a`
and `3c9733ff4d200282228073e351866fc7eead975aeec471d2214ab00e6bf5950d`).
The exact shared-RNG transitions differed: `0xecb653b5 -> 9054 ->
0xa35eb7a4` selected index 4 and `[6,5]`; `0x9fff3779 -> 4432 ->
0x91501c58` selected index 2 and `[5,4]`; and `0x30f73531 -> 14069 ->
0xb6f50330` selected index 4 and `[6,5]`. Every coordinate matched the
following bridge spawn marker. Every observer restored its debug registers,
VEH, file handle, and exact seam bytes and published no address or pointer.

This is exact selector-time capture and replay evidence, but it is not a
whole-game neutrality proof. Control versus dormant outcomes already selected
different next spawn coordinates in all three unarmed comparisons, so a
restored save plus fixed seed did not stabilize the shared stream before the
selector. Armed differences therefore cannot isolate an observer effect.
Transient dead/non-corpse occupancy, the Pawn path profile at entry, a complete
future forecast from ordinary solver input, and pristine-depot behavior remain
explicitly unproven. Rust continues to consume authoritative settled spawn
markers; no simulator change or version bump follows.

The seven rejected development attempts are preserved under
`captures/windows_build_13725832_owner_local_modified_20260829_spawn_coordinate_capsule_diagnostics/`:
the first exact process returned an error ACK because the previously cleaned-up
Continue helper was not installed, then closed through `WM_CLOSE`; the second
passed the exact three-module preflight and acknowledged native Continue, but
the external `tasklist.exe` process enumerator exceeded its five-second timeout
before bridge entry. Its condition could not prove a close method, while the
campaign final verifier found the game stopped and reproduced the sealed save
tree. The lifecycle now uses the native Windows process-snapshot API instead of
that external command. The third startup then reached an exact `Mission_Power`
player turn with three live active player units, but exposed that the raw Lua
bridge intentionally has no top-level `active_mechs` summary field; it closed
cleanly through `WM_CLOSE` and final-restored the same tree. Readiness now derives
the existing solver actor count from authoritative bridge unit records, including
weapon-bearing controllable allies. The first condition and campaign lifecycle
SHA-256 values are respectively
`03cfc134c11d6c828ab24f2bbca5758d8b482a02e3feb0f1e83713953620c0af` and
`3d6fb1ce0f4b997463b6978689d2bd54e578a03fd64c76d702396a4846533569`;
the second values are
`f48b367889a3c39131d39795fecf973fe20aacb38e552fdfd31483d2c0572ac2`
and `43a5c8f22506f715bbb3e6252c60f6c34d5f6c56cb55502a82a13269bff251eb`;
the third values are
`299f51db573b3b4c68a93900cc1cca425f5052ed7d3f5886b18e1be16f1f5759`
and `86a66bd0fa4343b3a226f430575f5c18e3dcd28e2eaa33b7acbf8cfcac42f396`.
The fourth startup crossed bridge readiness and entered `auto_turn`, but the
directly imported trial runner inherited the Windows legacy output codec and
raised before returning its reservation when a board description contained
`→`. The boundary aborted, the pause guard succeeded, the process closed through
`WM_CLOSE`, and the save final-restored exactly. Imported trials now establish
UTF-8 before solver output, and mutable recording roots are resolved at call time
so the already-set external artifact root is honored. Its condition, campaign,
and trial lifecycle SHA-256 values are respectively
`ef94e724e8c12bf573f22ed10588a8e90de587e2a4d1e79e1b235dd4aefd1ac0`,
`6202a30bec34e296232393d706608cb80bc6100dfb0ee951dbadd4f701a7ef05`, and
`9a1108128160ba45edb40dee98bfbf301d54fbfbd110a7dc37f62e8e7a0b883c`.
Three further attempts reached the reviewed dirty frontier but could not create
the required opaque reservation: the first exposed the exact one-shot consent
requirement and failed closed when synthetic Escape input was denied; the next
proved that posting Escape was not enough to visually verify the black-window
pause state; and the third proved the calibrated pause-button fallback could
not acquire the global cursor. All three aborted before capsule preparation or
End Turn, closed through `WM_CLOSE`, and final-restored the same save tree. The
successful campaign removes those global-input dependencies by consuming the
reviewed dirty consent per condition and dispatching End Turn synchronously
through the exact build-pinned native helper.

The one-condition trial runner
`scripts/itb_observatory_spawn_coordinate_capsule_trial.py` rejects any module,
receipt, or Windows executable other than the exact content-addressed build
before touching the isolated session. It also requires an exact stopped-game
start-state proof that predates the bound `Breach.exe` PID/creation FILETIME. It
asks `auto_turn` to spend the player actors and reserve an opaque local End Turn,
prepares the requested control/dormant/armed boundary only after that reservation
exists, invokes the existing guarded local dispatcher, and keeps the boundary
alive until a fresh `Mission_Power` player turn with a larger turn number is
visible. It then finishes/restores the observer before taking and verifying a
pause screenshot. An armed trial is accepted only when its native selected-
coordinate order exactly matches the bridge's next-turn spawning markers; the
copied snapshot is removed from the bridge only after that correlation and
immutable artifact writes succeed.

`scripts/itb_observatory_spawn_coordinate_capsule_condition.py` owns the full
reversible lifecycle for one condition. Before restoring or launching, it
requires the exact capsule observer, Continue helper, and RNG-seed helper at
their content-addressed names in the executable's `scripts` directory. With the
game stopped, it then restores and byte-verifies the exact baseline save,
publishes the start-state proof, creates a no-authority session sandbox, arms the
fixed native Continue startup request, launches the exact executable, binds the
launched process identity, requires the exact startup ACK, waits for the same
initial `Mission_Power` bridge state, and runs the trial. It then
releases only its own session lock and closes that same process through
`WM_CLOSE`; PID/path replacement, a forced termination, or a process left
running rejects the lifecycle.

The offline sealer
`scripts/itb_observatory_spawn_coordinate_capsule_campaign.py` accepts exactly
three triplets with these counterbalanced orders:
`control,dormant,armed`; `armed,control,dormant`; and
`dormant,armed,control`. Every condition must contain only its trial, outcome,
start-state proof, isolated session, and lifecycle, plus the armed snapshot and
rebuilt correlation. Its campaign-level `recordings` tree must contain exactly
one run directory per isolated session and exactly one board, solve input,
solve result, threat audit, and resist probe for that mission/turn. It proves
nine distinct process identities, one exact
executable, one exact installed three-module set, and one starting save tree;
exact per-condition restore/launch/Continue/bridge/trial/close chains; and a
campaign-level stopped-game restore after the ninth condition. It rejects
condition-order drift, extra files, digest drift,
incomplete restoration, observer-output leakage from control/dormant conditions,
or any native/bridge coordinate disagreement. Whole-game semantic differences
are sealed losslessly and prevent a neutrality claim; complete unarmed
control/dormant drift is reported separately from armed differences.

`scripts/itb_observatory_spawn_coordinate_capsule_campaign_run.py` conducts all
nine lifecycles, attempts the final baseline restore even after an early rejected
condition, writes the campaign lifecycle, and only then imports a byte-identical
tree into a fresh repository destination and seals it. It never overwrites an
existing campaign or receipt and never force-kills the game. The sealed receipt
therefore closes save restoration itself. The matching cleanup receipt
`captures/windows_build_13725832_owner_local_modified_20260829_spawn_coordinate_capsule_cleanup_receipt.json`
closes its remaining installation fields: the active Mod Loader is restored to
SHA-256 `5af8e809...abf22d`, all three experimental DLLs are absent, the
installation matches all 689 entries in the prior accepted owner-local restore,
the bridge has no Observatory residue, the same 32-file save tree still matches,
and `Breach.exe` is stopped. Exact removed bytes remain in recoverable owner
staging.

Create the baseline only while the game is stopped, then run the campaign from
fresh external and repository destinations:

```powershell
python scripts/itb_observatory_pair_state.py snapshot `
  --save-root "<Into The Breach save root>" `
  --output-root "<fresh external baseline root>" `
  --capture-track owner_local_modified

python scripts/itb_observatory_pair_state.py verify `
  --save-root "<Into The Breach save root>" `
  --snapshot-root "<external baseline root>"

python scripts/itb_observatory_spawn_coordinate_capsule_campaign_run.py `
  --artifact-root "<fresh external campaign root>" `
  --repository-campaign-root "data/observatory/captures/<fresh capsule campaign>" `
  --receipt-output "data/observatory/captures/<fresh capsule receipt>.json" `
  --save-root "<Into The Breach save root>" `
  --snapshot-root "<external baseline root>" `
  --source-session sessions/active_session.json `
  --executable "<Into the Breach>/Breach.exe" `
  --build-receipt data/observatory/native/itb_observatory_spawn_coordinate_capsule_hw_observer_bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9.dll.receipt.json `
  --module "<installed exact capsule DLL>"
```

Capture and verify the current-only joined artifact with:

```powershell
python scripts/itb_observatory_native_spawn_inputs.py `
  --with-bridge-replay `
  --output recordings/observatory/<capture>.json

python scripts/itb_observatory_native_spawn_inputs.py `
  --verify recordings/observatory/<capture>.json
```

Verify the immutable static map with:

```powershell
python scripts/itb_observatory_enemy_spawn_candidate_boundary.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_enemy_spawn_candidate_boundary.json
```

`captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng/`
contains three later same-process captures that combine that observer with the
complete RNG-core stream. The coordinate draw uniquely maps to caller ID 60 at
ordinals 1495, 1475, and 1450, with raw values `3642`, `15777`, and `30530`.
The static overlay
`native/windows_build_13725832_31fe35265598_rng_caller_roles.json` keeps the
original return-map digest intact while pinning five function hashes, 14
literal anchors, and the 13 variable callers needed for explanation. The
classified upstream-count deltas exactly reproduce the ordinal deltas. Most
variation is presentation work sharing the native stream: particle emitters
consume 1233/1188/1200 draws and `UnitAcid` effects consume 30/54/18; pilot
portrait draws add 8/8/7. This is a conformance result and a prediction guard,
not permission to synthesize a future coordinate from a save plus seed.

The derived receipt
`captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_state_replay_receipt.json`
now makes the post-hoc selector state explicit without changing either
immutable source receipt. Each caller-60 event begins a contiguous three-result
native window. Those windows recover observable pre-states `0x161229bc`,
`0x495e317b`, and `0x2c54aa4a`; advancing once reproduces raw results `3642`,
`15777`, and `30530`, whose modulo indices select `[5,4]`, `[5,4]`, and `[5,2]`
from the preserved five-point order. Rust carries the same input-driven replay
primitive and a capture-backed test. Ordinary bridge state still does not
deliver a future selector state before the call, so the non-fabrication guard
remains unchanged and no simulator-version bump follows. Rebuild the derived
receipt with:

```powershell
python scripts/itb_observatory_spawn_coordinate_state_replay.py
```

Rebuild the immutable receipts with:

```powershell
python scripts/itb_observatory_native_boundary_campaign.py spawn_coordinate `
  data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate
python scripts/itb_observatory_native_boundary_campaign.py spawn_coordinate_rng `
  data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng
```

Reproduce the caller-role overlay against the exact executable with
`scripts/itb_observatory_rng_caller_roles.py verify`, and reproduce the static
coordinate path map with
`scripts/itb_observatory_spawn_coordinate_paths.py verify`. The cleanup receipt
`captures/windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_cleanup_receipt.json`
closes both coordinate receipts: all 689 install entries and all 33 sealed save
files match, the baseline Mod Loader is restored, and no diagnostic remains in
the active install or bridge.

## Callback slot evidence and trial tooling

The final callback-binding captures ending in
`callback_bindings_live_slot_update.json` and
`callback_bindings_live_slot_update_repeat.json` are fresh-process,
byte-identical 131,137-byte documents. They resolve 81 runtime roots and 324
method records to 65 defining slots without invoking or wrapping a callback.
The raw SHA-256 is
`39f1dda91de64a9b4b976a3ed3c12c93ae588ee5bcf6be66731c33b4b91abb24`;
the canonical document SHA-256 is
`d6b25a368df6cbe9d556f56c7dc0e94531369d0ac2f97ad5ac0d4a169b7d9eb3`.
The build identity, both artifacts, collector hashes, and inert-enumeration
claim are sealed in
`captures/windows_build_13725832_owner_local_modified_20260822_callback_bindings_receipt.json`.

`scripts/itb_observatory_callback_trial.py` builds a content-addressed capsule
and exact one-family plan from those slot bindings and the source join. The Lua
host/controller supports `ScorePositioning`, `GetTargetScore`, `GetTargetArea`,
and `GetSkillEffect`, restores all slots before create-only publication, and
leaves the RNG globals untouched.

`captures/windows_build_13725832_owner_local_modified_20260822_natural_callbacks/`
archives five natural pairs covering all four families. They contain 622
attempts and 620 bounded events, restore every slot, and report no serialization
or restore error. `ScorePositioning`, `GetTargetArea`, and `GetTargetScore`
match their paired whole-game outcomes. Two counterbalanced `GetSkillEffect`
pairs repeat the same event stream and condition-specific outcomes, but their
control/exact outcomes differ only at the next spawn coordinate. The receipt
`captures/windows_build_13725832_owner_local_modified_20260822_natural_callback_campaign_receipt.json`
keeps invocation/restoration separate from whole-game neutrality. Rebuild it
with:

```powershell
python scripts/itb_observatory_callback_campaign.py `
  data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_natural_callbacks
```

The callback campaign's in-process Continue/End Turn helper is reproducible
from `src/native/observatory_continue.c` with
`scripts/build_itb_observatory_continue_helper.py`. Two independent `/Brepro`
builds produced the same 78,848-byte DLL and the same normalized receipt bytes.
The generated DLL is intentionally omitted. Its exact build receipt and the
two-build attestation are:

- `native/windows_build_13725832_31fe35265598_callback_gameflow_helper_receipt.json`
- `native/windows_build_13725832_31fe35265598_callback_gameflow_helper_reproducibility.json`

The active installation and bridge must contain no Observatory diagnostic file
after a campaign. Generated helpers and modified loader copies remain only in
recoverable owner staging after the durable evidence and final cleanup receipt
are verified. `scripts/itb_observatory_cleanup.py` is dry-run by default,
requires the exact baseline Mod Loader hash, confines deletions to
`scripts/{itb_observatory_,observatory_}*` and matching bridge files, and needs
`--allow-cleanup` before changing either root.

The later closure receipt
`captures/windows_build_13725832_owner_local_modified_20260822_callback_native_campaign_cleanup_receipt.json`
(SHA-256
`e95ca9273cec02173a9fcd23b0c8bc47e07b0da7c890856e2a196f7997e65758`)
closes both new campaign receipts' pending save/install fields. It binds a
689/689 accepted-install match, the restored 33-file owner-save tree, the exact
baseline loader, zero active Observatory files, and the preserved recoverable
staging area.

## Final phase-scheduler boundary

`native/windows_build_13725832_31fe35265598_final_phase_scheduler.json`
joins four exact shipped Lua files to seven reviewed native functions, seven
named-string anchors, seven instruction-start control windows, and seven direct
call edges. It proves the relative Windows-build handoff boundary without
storing function bodies, proprietary source, or decompiler output:

- the ordinary readiness path queries `IsEndBlocked`, and a true result vetoes
  that path;
- the reviewed completion branch evaluates `IsNextPhase` before dispatching
  `MissionEnd`;
- the primary orchestrator later evaluates `IsNextPhase` again and calls the
  phase-transition routine only for a true result;
- that routine dispatches `GAME.CreateNextPhase`; and
- shipped Lua replaces the current mission slot with
  `CreateMission(Mission_Final_Cave)` for `Mission_Final`.

Verify the exact executable, source hashes, region hashes, callback strings,
control windows, and call edges with:

```powershell
python scripts/itb_observatory_final_phase_scheduler.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --scheduler-map data/observatory/native/windows_build_13725832_31fe35265598_final_phase_scheduler.json
```

This is a relative static order proof, not a runtime timestamp. Its conservative
`final_end_state_trigger` and `mission_end_effect_settlement` gaps are resolved
by the follow-up below. Later immutable continuations also resolve the Final
Cave countdown result and post-travel campaign path. Cave initialization
outputs and non-Windows equivalence remain explicit gaps. No current-turn Rust
simulator change follows; the safe boundary remains a fresh bridge read after
the live stage change.

## Final end and MissionEnd settlement boundary

`native/windows_build_13725832_31fe35265598_final_end_settlement.json`
supersedes two gaps in the scheduler artifact. It joins three exact shipped Lua
files to 15 reviewed native regions, four callback-string anchors, two vtable
pointers, 11 instruction-start control windows, and eight direct call edges.
For the pinned Windows build it establishes that:

- end readiness calls the current `GetTurnLimit` and returns true when an active
  Board exists, the current turn equals that limit, and BoardPlayer state is 2;
- that exact return occurs before the fallback `IsEndBlocked` dispatch, so both
  shipped Final stages use the ordinary limit boundary despite their always-true
  overrides; the cave's source-level `TurnLimit + 2` replacement extension moves
  the queried boundary;
- both Final `MissionEnd` callbacks route `Board:AddEffect` through the reviewed
  native binding into the Board effect vector at `+0x2c50`;
- a nonempty vector yields Board activity reason 6 through the pinned Board and
  BoardPlayer vtable slots; and
- after `MissionEnd` requests completion state 5, the primary orchestrator does
  not reach `IsNextPhase` and the phase/exit handoff until comprehensive Board
  activity is clear.

Verify the executable, exact sources, region hashes, strings, vtable pointers,
control windows, and direct edges with:

```powershell
python scripts/itb_observatory_final_end_settlement.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --settlement-map data/observatory/native/windows_build_13725832_31fe35265598_final_end_settlement.json
```

The map proves ordinary queue-empty/activity-clear ordering, not wall-clock
timing or arbitrary modified-effect cancellation. Its narrowed countdown gap
is resolved by the outcome continuation below, and its post-`StartMechTravel`
gap is resolved by the campaign continuation after that. It requires no Rust
simulator change.

## Final Cave countdown outcome boundary

`native/windows_build_13725832_31fe35265598_final_cave_outcome.json`
resolves the earlier `cave_countdown_outcome` gap. It joins the exact shipped
Final Cave source to ten reviewed native regions, eight string anchors, four
jump/vtable pointers, 18 instruction-start control windows, and eight direct
call edges. For the pinned Windows build it establishes that:

- BoardPlayer initializes primary outcome `+0x1900` and secondary outcome
  `+0x1904` to pending code 2;
- the state jump table sends state 2 through nonforced classification and state
  0 through forced classification;
- on the ordinary state-2 path, current turn equal to the current
  `GetTurnLimit` writes outcome code 1, selects the Final victory route,
  dispatches `MissionEnd`, and requests completion state 5;
- the closed ready-to-code-1 path contains no bomb, objective, or
  `IsEndBlocked` query;
- a missing bomb instead queues `AddBomb` and adds two to `TurnLimit`, so bomb
  destruction delays the reached countdown boundary rather than directly
  selecting terminal failure; and
- only a still-pending forced state-0 evaluation calls the exact registered
  `Board:GetPawnCount(TEAM_MECH)` path (`TEAM_MECH == 4`), writing failure code
  3 when that result is zero.

The downstream campaign artifact maps code 3 to campaign result 2 and other
committed results, including code 1, to result 1. Verify the executable, exact
source, regions, strings, jump/vtable pointers, control windows, and calls with:

```powershell
python scripts/itb_observatory_final_cave_outcome.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --outcome-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_outcome.json
```

This outcome map does not itself predict replacement-bomb timing or
coordinates. The materialization continuation below closes the generic native
drop path while retaining the runtime-dependent coordinate and cadence gates.

## Final Cave replacement-bomb boundary

`native/windows_build_13725832_31fe35265598_final_cave_replacement.json`
resolves the earlier broad `replacement_materialization` gap and splits its
remaining runtime inputs into narrower explicit gaps. It joins three exact
shipped Lua files to 28 reviewed native code/registration regions, six string
anchors, five vtable pointers, 20 instruction-start control windows, and 19
direct call edges. For the pinned Windows build it establishes that:

- the primary orchestrator runs the Board effect update before `BaseUpdate`,
  whose shipped implementation later calls `Mission_Final_Cave:UpdateMission`;
  a replacement effect queued there cannot dispatch during that already-finished
  Board-update pass;
- the exact `Board:IsBusy` binding uses the Board secondary-vtable activity
  slot, and a nonempty effect vector at `+0x2c50` yields reason 6, preventing an
  immediate repeat while the new batch remains queued;
- `SkillEffect:AddDropper` writes kind 4 and immediately makes independent
  full `0x134`-byte `SpaceDamage` copies, so later Lua mutation cannot alter an
  already appended dropper record;
- `Board:AddEffect` queues the copied batch, and a later eligible Board update
  removes and dispatches one batch through the exact native effect slot;
- kind 4 creates `PylonAnimation`, whose constructor preserves the record at
  `+0x2dc`; its landing callback invokes the impact slot, which applies that
  retained record through the Board; and
- a nonempty `sPawn` goes through the pawn factory and exact `Board:AddPawn`
  body at the original `SpaceDamage` coordinates when native blocker admission
  accepts the point. Because shipped `AddBomb` set `sPawn="BigBomb"` before the
  immediate copy, an accepted selected point materializes a `BigBomb` when the
  drop lands. The later drop-resolution continuation pins the preceding
  kill-and-blocker-recheck gate.

Verify the executable, exact sources, region hashes, strings, vtable pointers,
control windows, and direct edges with:

```powershell
python scripts/itb_observatory_final_cave_replacement.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --replacement-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_replacement.json
```

The candidate enumeration and interior preference are exact, but the
callback-time occupancy/environment set, variable `random_removal` draw count,
incoming shared CRT state, concrete coordinate, new pawn UID, and wall-clock
delay are not ordinary solver inputs. The cadence continuation below closes
the semantic repeated-cycle gap without making those concrete values
predictable. Simulator v406 already records the exact `+2` extension and every
snapshot-reachable candidate without fabricating a pawn or UID, then stops for
a fresh settled bridge read. The native proof validates that boundary; no Rust
semantic change follows.

## Final Cave replacement cadence boundary

`native/windows_build_13725832_31fe35265598_final_cave_replacement_cadence.json`
continues the materialization map through the active-animation scheduler. It
binds one exact shipped Lua file, eight reviewed native regions, three data
anchors, six vtable pointers, eight instruction-start control windows, and one
direct call edge. For the pinned Windows build it establishes that:

- the Board effect update calls the effect dispatcher with `this` adjusted to
  primary Board `+0x0c`; the dispatcher's vector at relative `+0x2d14` is
  therefore the primary Board active-animation vector at `+0x2d20`;
- the kind-4 factory result enters that vector, which the activity routine
  checks through animation slot `+0x0c` and reports as activity reason 8;
- exact `game.lua` values make the dropper's `+0x1d4` fall field start
  strictly negative; both the lifetime and activity predicates remain true
  while it is negative;
- the active loop keeps and updates the Pylon until its landing update clamps
  that field nonnegative and synchronously invokes impact; and
- no `UpdateMission` callback can observe a nonbusy, still-missing bomb between
  dispatch and impact. Each later `+2`/replacement cycle therefore requires a
  later loss of the materialized bomb and another idle callback.

Verify the executable, exact source values, region/data hashes, vtable
pointers, control windows, and direct edge with:

```powershell
python scripts/itb_observatory_final_cave_replacement_cadence.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --cadence-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_replacement_cadence.json
```

This proves semantic repeat ordering, not the selected coordinate, RNG state,
new UID, or wall-clock presentation duration. The mandatory fresh settled
bridge read therefore remains unchanged.

## Final campaign settlement boundary

`native/windows_build_13725832_31fe35265598_final_campaign_settlement.json`
continues from the cave's `Board:StartMechTravel()` script through campaign
classification, save/profile settlement, and final-victory presentation. It
binds one exact shipped Lua file, 24 reviewed native regions, 12 string
anchors, two BoardPlayer vtable pointers, 16 instruction-start control
windows, and 20 direct call edges. For the pinned Windows build it establishes
that:

- `StartMechTravel` enables Board travel mode, initializes the `+0x2cc0`
  travel vector with a 4.5-second state value, and in ordinary mode locates
  `BigBomb` and stores its coordinates;
- the Board update drains `+0x2c50` effects before `+0x2cc0` travel and, once
  ordinary travel is empty, constructs `Board:LockBomb()` followed by
  `Board:Fade(FADE_EXPLODE)`;
- BoardPlayer state 6 is a common completed-battle state, while the world-map
  tick deliberately withholds ordinary cleanup for a qualifying Final
  campaign;
- the campaign predicate maps BoardPlayer outcome code 3 to result 2 and every
  other outcome to result 1, with downstream consumers identifying result 1
  as the campaign-win route;
- the campaign manager removes `saveData.lua`, `.old`, and `.backup`, snapshots
  presentation data, opens the result gateway, derives the win boolean, counts
  four secured-island flags, and settles the profile in that relative order;
- the win path records difficulty, result, island count, history/histogram, and
  the squad/difficulty `_Victory_` achievement route, then invokes the
  conditional `profile.lua` serializer/write path; and
- result 1 initializes the embedded final-victory controller whose renderer
  contains `Victory_Final_Flavor`, `Victory_Final_Protected`, and
  `Victory_Final_Billions`.

Verify the executable, exact source, regions, strings, vtable pointers, control
windows, and direct edges with:

```powershell
python scripts/itb_observatory_final_campaign_settlement.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --campaign-map data/observatory/native/windows_build_13725832_31fe35265598_final_campaign_settlement.json
```

This is an exact relative control-flow and reachable persistence/presentation
proof. It does not claim live timestamps, OS file-operation success, a
particular completed run's file contents, or non-Windows equivalence. The
profile writer's native `+0x54` precondition remains explicit. These are
post-combat boundaries, so no Rust combat-simulator change follows.

## Final Cave startup boundary

`native/windows_build_13725832_31fe35265598_final_cave_startup.json`
continues the exact-build handoff from `GAME.CreateNextPhase`. It binds six
reviewed native regions, seven callback-string anchors, five instruction-start
control windows, five direct call edges, six exact shipped Lua files, and the
complete exact maps revision. It establishes that:

- native code selects and loads the map before dispatching mission
  `BaseStart`;
- the nonempty `final_cave` map tag takes the native `RandomMap` path;
- exactly nine installed maps carry that tag, all with the same four center
  deployment tiles, seven pylon tiles, and three or four mountain tiles;
- `BaseStart` runs `Env_Final:Start`, cave `StartMission`, difficulty setup,
  and ordinary starting spawns in that relative order; and
- exact Lua fixes the source-level RNG skeleton for the lava path, bomb and
  three-Mech placement, mountain and pylon queue order, and boss selection.

The bomb plus Mech IDs 0, 1, and 2 have 24 source-reachable assignments over
the four shared center tiles. Verify the executable, selected Lua sources,
complete maps revision, map fields, native regions, callback strings, control
windows, and call edges with:

```powershell
python scripts/itb_observatory_final_cave_startup.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --startup-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup.json
```

This immutable first artifact does not select a concrete map, replay native
RNG, prove whether `random_int(1)` advances state, resolve nested `NextPawn` or
spawn-coordinate draws, or establish when the queued startup effect settles.
The following map-choice artifact supersedes its first two map-choice
questions. The startup spawn-order continuation after it resolves the native
spawn path and logical-admission facet without rewriting this first artifact.

## Final Cave map-choice boundary

`native/windows_build_13725832_31fe35265598_final_cave_map_choice.json`
binds the exact shipped `maps/maphelper.lua` implementation to nine reviewed
native regions, the named Win32 directory-enumeration imports, and this exact
installation's returned map order. It establishes that:

- native bootstrap loads `maphelper.lua`, enumerates the `maps` directory with
  `FindFirstFileA` / `FindNextFileA` without sorting, strips the four-character
  extension, and calls `AddMap` in returned order;
- `RandomMap` preserves that order, filters by both mission tag and sector,
  contains no Advanced Edition filter, and draws exactly once for a nonempty
  candidate list;
- the current installation orders the eligible maps as `cave1` through
  `cave5`, followed by `caveAE1` through `caveAE4`;
- the native selector can retry vetoed or already-used maps, but the inherited
  cave veto list is empty and no cave candidate is reachable earlier on an
  ordinary first Final Cave transition; and
- exact one-argument `random_int` bytes prove `random_int(1)` advances the
  shared CRT RNG and returns zero. The next map draw advances again and selects
  candidate index `rng_output % 9`.

Verify the executable, reviewed sources, complete maps revision, native Win32
directory order, region hashes, anchors, control windows, and call edges with:

```powershell
python scripts/itb_observatory_final_cave_map_choice.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --map-choice data/observatory/native/windows_build_13725832_31fe35265598_final_cave_map_choice.json
```

Directory enumeration order belongs to the installation/filesystem, not just
the file hashes, so copying or reinstalling the same bytes requires
reverification. The incoming CRT state is still absent from ordinary bridge
state; therefore the concrete map is not forecast and the solver still takes
a fresh settled bridge read after the stage change.

## Final Cave startup spawn-order boundary

`native/windows_build_13725832_31fe35265598_final_cave_startup_spawn_order.json`
joins the immutable startup map to the exact native `SpawnPawn` overloads,
the standard coordinate-selector map, and the effect/materialization maps. It
binds two exact shipped Lua files, 12 reviewed native regions, two registration
name anchors, nine instruction-start control windows, and 11 direct call
edges. For the pinned Windows build it establishes that:

- native registration maps the same `SpawnPawn` name to an explicit-point
  wrapper and a no-point wrapper; the latter supplies `(-1,-1)`, while the
  former preserves its parsed Point;
- the implicit enemy path calls the exact standard coordinate selector, then
  synchronously writes its returned Point to the pawn's logical space before
  `Board:SpawnPawn` returns;
- cave mountain and pylon `BlockSpawn` calls synchronously write the tile's
  block field while `StartMission` is still constructing the effect, so those
  writes finish before the later boss and ordinary implicit spawn calls;
- the primary orchestrator performs its only Board master update before the
  phase transition that dispatches `BaseStart`, with no second Board update
  later in that pass; and
- `StartMission` queues the combined effect and then admits the boss, while
  `BaseStart` subsequently admits ordinary starting pawns. Boss and ordinary
  identities and logical spaces therefore commit before the queued Mech
  `SetSpace` scripts or rock, pylon, and bomb droppers can dispatch.

Verify the executable, exact sources, region/data hashes, control windows,
call edges, lexical source order, and primary-orchestrator call inventory with:

```powershell
python scripts/itb_observatory_final_cave_startup_spawn_order.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --spawn-order-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup_spawn_order.json
```

This closes logical startup admission order, not concrete `NextPawn` results,
selector candidates/outputs, UIDs, visual animation overlap, or wall-clock
presentation timing. Those values still arrive through the fresh settled
bridge read, so no Rust simulator semantic change follows.

## Final Cave startup effect-order boundary

`native/windows_build_13725832_31fe35265598_final_cave_startup_effect_order.json`
continues the startup and spawn-order maps through the exact registered
`SkillEffect` builders, common record append, ordered dispatcher, Board damage
apply slot, and Lua evaluator. It binds the shipped Final Cave source, 20
reviewed native regions, six registration names and bindings, one Board vtable
slot, nine instruction-start control windows, 15 direct calls, and two Lua 5.1
imports. For Windows build `13725832` it establishes that:

- the shipped `IsRelease()` wrapper returns true, so `FAST_VERSION` is false
  and all three voice records plus every release-only delay are present;
- `AddVoice`, `AddDelay`, `AddDropper`, `AddScript`, and `AddBoardShake`
  append independent `0x134`-byte records immediately and in source-call order;
- the dispatcher starts at record zero, advances one record at a time, and on
  a nonzero delay stores the suffix beginning at the next record with the
  delay value, preserving order when work resumes;
- the three Mech script records reach Board SpaceDamage apply and are attempted
  synchronously through `luaL_loadbuffer` and `lua_pcall` in IDs 0, 1, 2 order;
- every one of the seven pylons contributes two independent consecutive
  building-dropper records before its following `0.5` delay; and
- exact three-mountain maps construct 44 records, while four-mountain maps
  construct 46, ordered as initial delay/shake, mountain pairs, Mech scripts,
  pylon pairs, and the final bomb dropper.

Verify the executable, source, region/data hashes, registrations, vtable slot,
control windows, direct/import calls, and lexical schedule with:

```powershell
python scripts/itb_observatory_final_cave_startup_effect_order.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --effect-order-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_startup_effect_order.json
```

The delay values are scheduler inputs, not measured wall-clock seconds, and
two consecutive droppers prove two record/animation creations rather than
their eventual visual impact order or overlap. Concrete RNG results,
coordinates, UIDs, and modified-state error/collision behavior remain outside
this map. The following lifetime continuation closes the ordinary spawn-block
facet, and the drop-resolution continuation after it closes the shipped
terrain/occupant consequences, without changing the fresh settled-read solver
boundary.

## Final Cave spawn-block lifetime boundary

`native/windows_build_13725832_31fe35265598_final_cave_block_spawn_lifetime.json`
joins the startup maps to native `BlockSpawn`, spawn validity,
`ClearBlockSpawns`, the battle phase driver, and Board reset. It binds the
shipped Final Cave source, 11 reviewed native regions, 11 data anchors, three
constant and two method registrations, 13 instruction-start control windows,
11 direct call edges, complete raw `E8` caller catalogs for three key targets,
and the reviewed `Board+0x7458` field-reference inventory. For Windows build
`13725832` it establishes that:

- native registration binds `BLOCKED_NONE=0`, `BLOCKED_TEMP=1`, and
  `BLOCKED_PERM=2`;
- `BlockSpawn` synchronously writes its supplied integer to the Point-keyed
  Board map, and native spawn validity rejects both values one and two before
  its remaining tile rules;
- `ClearBlockSpawns` changes only value one to zero and preserves value two;
- the stage-start phase-one and end-turn mode-six paths do not run that
  cleanup, while the player-turn mode-one path runs it before constructing the
  player-turn UI;
- Final Cave mountain temporary blocks therefore constrain startup selection
  and survive stage-start settlement, then clear before the first actionable
  player state; permanent pylon blocks constrain startup selection and survive
  ordinary player-turn cleanup; and
- permanent is Board-scoped, not immortal: full Board reset writes zero across
  all 8x8 entries, and an explicit later `BlockSpawn` can overwrite a value.

Verify the executable, exact source, accepted-tree Lua search, region/data hashes,
registrations, control windows, direct edges, and raw callsite catalogs with:

```powershell
python scripts/itb_observatory_final_cave_block_spawn_lifetime.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --lifetime-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_block_spawn_lifetime.json
```

The verifier requires all 304 analysis-relevant scripts entries to match the
hash-pinned baseline inventory and permits only one of two hash-pinned project
bridge overlays at `scripts/modloader.lua`; it searches all 153 Lua files in
either accepted tree for the `ClearBlockSpawns` identifier. Other modified
scripts can still invoke the registered method and belong to another content
identity. The native block map is not exported in ordinary bridge state, and
arbitrary dropper collisions, visual overlap, concrete RNG outputs,
coordinates, and UIDs remain outside this map. Settled bridge state already
contains the actionable terrain and units, so no Rust semantic change follows.

## Final Cave drop-resolution boundary

`native/windows_build_13725832_31fe35265598_final_cave_drop_resolution.json`
joins the startup, effect-order, spawn-block, replacement, and cadence maps to
the native phase-carried-pawn, `SpaceDamage` field-layout, and apply paths. It
binds the exact startup Lua/map tree, seven dependency artifact hashes, three
retained turn-zero boards, 26 reviewed native regions, nine data anchors,
three field and four method
registrations, 19 instruction-start control windows, and 17 direct call edges.
For Windows build `13725832` it establishes that:

- native registration binds `iDamage`, `sPawn`, and `iTerrain` to record
  offsets `+0x08`, `+0xa4`, and `+0xdc`;
- core damage and terrain application finishes before the nonempty-`sPawn`
  branch, so the BigBomb record assigns Road before occupant replacement;
- after loading the replacement Board, phase transition passes every carried
  pawn through `SetSpace(-1,-1)` and completes that admission loop before
  dispatching `BaseStart`; the exact Surface handoff reaches BoardPlayer state
  five, which skips the only native auto-deployment tail; the exact cave maps
  have empty spawn lists, while the only source-reachable pre-pylon spawn uses
  a deployment tile disjoint from every pylon zone;
- an ordinary pylon's first zero-damage Building record creates a 1/1
  Building, while its independent duplicate raises the embedded `ValueBar`
  maximum and current value to 2/2; three retained exact-map turn-zero boards
  corroborate seven 2-HP pylons each;
- a nonempty `sPawn` record calls registered `Pawn:Kill(false)` on every tile
  occupant, clears live-pawn logical coordinates, reruns `IsBlocked`, and only
  then constructs and adds the named pawn at the original point;
- the optional startup enemy at `bomb_loc` is on a deployment tile disjoint
  from temporary mountain and permanent pylon zones, so it is deliberately
  replaced by BigBomb;
- a later replacement point occupied by an enemy follows the same
  kill-then-recheck order, but BigBomb is added only if that blocker recheck
  passes; a destroyed pylon can retain its permanent spawn block and make the
  record abort after killing the enemy; and
- settled bridge state already contains these results, so pending replacement
  remains non-fabricated until the next settled read and no Rust semantic
  change follows.

Verify the executable, exact source and dependencies, retained captures,
region/data hashes, registrations, control windows, and direct edges with:

```powershell
python scripts/itb_observatory_final_cave_drop_resolution.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --resolution-map data/observatory/native/windows_build_13725832_31fe35265598_final_cave_drop_resolution.json
```

This map does not generalize the ordinary shipped result to arbitrary modified
Water, Chasm, corpse, multi-space, or unusual-blocker collisions. A later
destroyed-pylon permanent-block collision is explicitly conditional; its
concrete selected point and block state remain runtime inputs. The map also
does not close generic `DAMAGE_DEATH` callbacks/attribution, concrete startup
RNG outputs, UIDs, visual impact interleave, or non-Windows builds.

## DAMAGE_DEATH pawn/HP boundary

`native/windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json`
follows the exact registered `DAMAGE_DEATH` value through the shared
`SpaceDamage` core, Pawn receiver, status setters, HP routine, and embedded
clamped `ValueBar`. It binds both Final environment sources, 15 reviewed
native regions, six data anchors, three registered status setters, 16
instruction-start control windows, and eight direct call edges. For Windows
build `13725832` it establishes that:

- `DAMAGE_DEATH` is the integer `1000`, stored in `SpaceDamage.iDamage` at
  record offset `+0x08`; it is special numeric damage, not an unconditional
  direct `Pawn:Kill` operation;
- Shield and Frozen recognize the sentinel, run their normal registered clear
  setters, and do not reduce it to zero;
- Armor still subtracts one (`1000` to `999`) and ACID still doubles the
  remaining positive damage; “lethal bypasses all statuses” is therefore an
  outcome shorthand, not the native arithmetic;
- the generic Pawn receiver contains no flying or Massive immunity test, then
  negates the effective damage and sends it to the Pawn HP routine;
- the embedded `ValueBar` caps a negative delta at minus-current HP, proving
  zero HP for stock supported pawn health; and
- the reviewed core's one direct `Pawn:Kill` edge belongs to its separate
  Building-terrain occupant-removal branch. Neither the Pawn numeric receiver
  nor the HP-delta routine directly calls `Pawn:Kill`.

Verify the executable, exact Final Cave/Volcano sources, region/data hashes,
registrations, control windows, complete reviewed direct-`Pawn:Kill` edge
inventory, and call edges with:

```powershell
python scripts/itb_observatory_damage_death.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json
```

This closes the stock Final Cave/Volcano Pawn HP outcome without requiring a
Rust semantic change. The continuations below map conditional Board erase,
ordinary event/credit dispatch, same-update visibility, and shipped specialized
classification. The corpse-classification successor below also closes the
predicate's static fields, common implementation, mutation-12 fallback, and
shipped source inventory. Exact damage-relative lifecycle timing, native-only
`OnKill` field-offset consumers, and non-Windows equivalence remain separate
boundaries.

## Zero-HP Board cleanup boundary

`native/windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json`
continues from the exact `DAMAGE_DEATH` HP-zero artifact and joins it to the
existing live-or-persistent-corpse path artifact. It binds 18 reviewed native
regions, seven instruction-start control windows, six direct edges, nine
named data anchors, and all 20 absolute references to those names in the
file-backed `.text` section. For Windows build `13725832` it establishes that:

- after applying the HP delta and further same-routine feedback logic, the
  Pawn HP routine dispatches virtual `IsDead` at vtable slot `+0x10` before
  returning; it does not directly call `Pawn:Kill`;
- a later Board sweep has exactly two encoded, instruction-aligned direct
  callers in the exact `.text` image;
- the sweep reaches its Pawn-vector erase path only after three state bytes
  are clear, virtual `IsDead` is true, extra definition/state gates pass,
  Pawn byte `+0x964` is clear, and direct `Pawn:IsCorpse` returns false;
- for a still-present eligible pointer, the exact helper returns its vector
  index, the tail is compacted, and the vector end moves back four bytes;
- `IsCorpse == true` skips this erase path. Joined to the path artifact, a
  retained corpse remains counted occupancy while a dead non-corpse does not;
- the exact `OnKill` string has four absolute references, all in two
  property-access functions. None of the reviewed damage, HP, explicit-Kill,
  or cleanup regions directly calls those functions; and
- `EVENT_ENEMY_KILLED` has one absolute binding-table reference, while the
  inventoried owner/death/counter strings occur in definition, accessor, or
  binding sites. Those names do not prove runtime dispatch or attribution.

Verify the executable, both predecessor artifacts and sources, every region
hash, instruction window, direct edge, exact sweep-caller inventory, and all
absolute-reference inventories with:

```powershell
python scripts/itb_observatory_zero_hp_cleanup.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --cleanup-map data/observatory/native/windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json
```

This is a structural cleanup proof, not a scheduling trace. Its static
`IsCorpse` inputs and shipped definitions are closed by the later corpse-
classification successor, but it still does not prove which sweep follows a
particular damage/effect record, frame-by-frame lifecycle transitions, the
generic or indirect Lua `OnKill` dispatcher, kill owner/team/counter updates,
death-effect presentation, or another depot. Those limits are why this tranche
requires no Rust semantic or simulator-version change.

## Enemy-death event and credit boundary

`native/windows_build_13725832_31fe35265598_death_event_credit_boundary.json`
continues from the zero-HP artifact through the ordinary native enemy-death
event and credit paths. It binds 24 native regions, 37 instruction-start
control windows, 15 direct edges, 13 named absolute-reference anchors with 27
references, six exact sources, and the accepted 305-file scripts tree. For
Windows build `13725832` it establishes that:

- the exact shipped Lua tree has seven `OnKill` occurrences: one empty `Skill`
  default and six localization-key values. It has no matching Lua callback
  definition, and all six mechanics are inline in their weapons'
  `GetSkillEffect` bodies;
- luabind registers `SkillEffect.iOwner` at record offset `+0x5c`;
  `Board:AddEffect` and both exact copy paths preserve it, and the dispatcher
  installs the copied owner as its current native owner context;
- both `Env_Attack:ApplyEffect` branches assign `ENV_EFFECT` before enqueueing,
  and exact registration gives `ENV_EFFECT` the integer value `-10`;
- the ordinary non-Mech `TEAM_ENEMY` death path emits event 2 for a non-Minor
  pawn and event 12 for a Minor pawn. Event 2 is exactly
  `EVENT_ENEMY_KILLED`; its pending/readable counter path reaches
  `Mission:BaseUpdate` and the `KilledVek` mission field;
- non-Minor, XP-eligible victims credit owners 0 through 2 through
  `xp_<owner>` and `kill_<owner>`, while other owners use `env_xp`. The
  reviewed path also names `any_kill_<owner>`, and each Mech consumes only its
  own Pawn-ID buckets; and
- environment owner `-10` therefore bypasses Mech XP, kill, and any-kill
  buckets while the independent non-Minor mission event still fires.
  `iMissionDamage` is instead a health-delta accumulator.

Verify the executable, predecessor map, exact sources and scripts tree, region
and data hashes, instruction windows, direct edges, owner/event/credit
contracts, and absolute-reference inventories with:

```powershell
python scripts/itb_observatory_death_event_credit.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --credit-map data/observatory/native/windows_build_13725832_31fe35265598_death_event_credit_boundary.json
```

Rust already applied the matching ordinary mission-kill rule to lethal
environment damage and excluded Minor enemies; the focused Final Cave
regression locked that portion. The event-frame successor below closes the
exact same-outer-update versus next-update question, and the specialized-death
successor closes shipped boss/Minor classification plus the missing IsMech
filter. Native-only `OnKill` field-offset consumers, achievement/profile
tails, the semantic name and complete writer set for Pawn byte `+0x1175`,
consumers of `any_kill_-10`, and non-Windows depots remain open.

## Board-death event frame visibility

`native/windows_build_13725832_31fe35265598_event_frame_visibility.json`
continues from the enemy-death/credit and Final Cave replacement maps. It binds
13 native regions, 16 instruction-start control windows, nine direct edges,
two vtable pointers, the exact `BaseUpdate` string reference, and the pinned
Mission source. For Windows build `13725832` it establishes that:

- the sole direct pending-event publisher runs before the same outer update's
  `Game` vtable-slot-`+0x04` call;
- the same outer object constructs that exact Game type and stores it at the
  dispatched `+0x18` field; its vtable slot is the exact Game update, whose
  active battle-mode branch directly enters the battle controller update;
- the battle update invokes its active `BoardPlayer` at vtable slot `+0x10`,
  and the exact BoardPlayer vtable maps that slot to the primary orchestrator;
- the orchestrator runs Board master update and its effect-queue pass before
  preparing and invoking `Mission:BaseUpdate`;
- an enemy-death event recorded during that Board/effect pass therefore enters
  pending storage after the current update's only publication point, so the
  later same-update `BaseUpdate` cannot read it; and
- the next ordinary outer update promotes that pending batch before its Game
  and BoardPlayer work, so its later `BaseUpdate` can read it. Multiple deaths
  from one pass become readable together.

Verify the executable, both predecessor artifacts, exact Mission source,
region hashes, instruction windows, direct edges, vtable pointers, string
anchor, and sole publisher-call inventory with:

```powershell
python scripts/itb_observatory_event_frame_visibility.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --visibility-map data/observatory/native/windows_build_13725832_31fe35265598_event_frame_visibility.json
```

“Next ordinary outer update” is a control-flow result, not a fixed wall-clock
frame guarantee: pause, mission teardown, or a terminal transition can delay or
end the consumer path. The proof is scoped to events recorded during normal
Board/effect processing and does not generalize event producers elsewhere in
the outer loop or another depot. This scheduling detail contradicts no Rust
board transition, so no simulator semantic or version change follows.

## Specialized-enemy death boundary

`native/windows_build_13725832_31fe35265598_specialized_enemy_death_boundary.json`
continues from the ordinary death-event map through the exact named Pawn
factory, common constructor/update route, and complete shipped boss/Minor
source inventory. It binds eight native regions, 12 instruction-start control
windows, six direct edges, three complete raw-rel32 call inventories, one data
anchor, and 15 selected source files. For Windows build `13725832` it
establishes that:

- `Mission_Boss:StartBoss` uses the one-argument named factory; its wrapper
  selects `GetDefaultTeam`, allocates a single 0x1328-byte common Pawn object,
  installs the common Pawn vtable, defaults `IsMech` and `Minor` false, then
  loads Lua `Minor` at Pawn `+0x10d0`;
- Board master update reaches the shared Pawn update, whose guarded call is
  the sole direct caller of the common death processor;
- once reached, ordinary event 2 requires `IsMech=false`, `TEAM_ENEMY=6`, and
  `Minor=false`; a Minor enemy uses event 12 instead. Leader, tier, boss,
  Psion, and Pawn type name do not gate this split;
- the accepted 153-file Lua tree has exactly 17 active `Minor=true`
  definitions, no child derived from one of those types, and 21 nonempty boss
  objectives that retain the global non-Minor default;
- all 21 boss objectives and all three Blob Boss forms therefore count as
  ordinary enemy kills, while `BlobB`, `TotemB`, `SlugEgg1`, and
  `SpiderlingEgg1` are Minor boss auxiliaries and do not; and
- shipped Lua reaches no enemy-team Mech. Its three `SetMech()` calls are
  tutorial player-team units, and its only `SetTeam()` mutation also selects
  `TEAM_PLAYER`.

Verify the executable, predecessor map, exact source tree, region/control
hashes, call edges and inventories, source classification, and solver binding
with:

```powershell
python scripts/itb_observatory_specialized_enemy_death.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_specialized_enemy_death_boundary.json
```

The native IsMech exclusion exposed a real but vanilla-dormant Rust mismatch.
Simulator v407 now uses `enemy && !is_mech && !minor` before the existing
`Mission_AcidTank` ACID filter; the pre-v407 corpus is archived as
`recordings/failure_db_snapshot_sim_v406.jsonl`. Detailed Mech-branch side
effects, modded factory/mutation paths, and non-Windows equivalence remain
outside this exact shipped-build result.

## Native corpse-classification boundary

`native/windows_build_13725832_31fe35265598_corpse_classification_boundary.json`
continues from the zero-HP cleanup and specialized-enemy maps through the
complete common `Pawn:IsCorpse` predicate and accepted shipped Lua corpse
inventory. It binds six native regions, ten instruction-start control windows,
eight data anchors with complete absolute-reference inventories, three
complete raw-rel32 call inventories, 13 exact selected sources, and both
predecessor artifacts. For Windows build `13725832` it establishes that:

- `Pawn:IsCorpse` is one common member with exactly 27 direct rel32 callers;
  the predicate contains no subclass-vtable dispatch;
- outside internal lifecycle states 2, 3, and 4, a Mech or a pawn loaded from
  `Corpse=true` returns true directly. Other cases require mutation 12 to be
  current or globally available and accepted by the common eligibility helper;
- the exact Pawn loader stores `Corpse` at `+0xf80`, `Leader` at `+0x1318`,
  `Minor` at `+0x10d0`, and `DefaultFaction` at `+0x10bc`; `SetMutation`
  writes the current mutation at `+0x10e8`;
- exact global registration identifies value 12 as `LEADER_NECRO`, not a
  Teleporter flag. Its alternate-recipient branch uses the `Psion_Leech`
  passive, and Minor recipients plus an already-current leader are excluded;
- `Jelly_Necro1` is the accepted tree's sole `LEADER_NECRO` definition, but
  no shipped mission, spawner, factory, or other active Lua reference reaches
  it, and shipped Lua never calls `SetMutation`;
- the 153-file tree has exactly ten explicit `Corpse=true` definitions and six
  inheriting Laser/Piston directional bodies, for 16 effective types; and
- the bridge already exports current `IsCorpse()` plus source-static
  `corpse_on_death`, while Python and Rust already cover all 16 types. No
  simulator contradiction or version change followed from this artifact;
  simulator v407 remained current at its publication.

Verify both predecessor maps, the executable, exact sources and accepted tree,
region/control hashes, data anchors, call inventories, classification, and
solver binding with:

```powershell
python scripts/itb_observatory_corpse_classification.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_corpse_classification_boundary.json
```

This is exact static classification, not a frame scheduler trace. At this
artifact stage, the action boundaries that enter or leave lifecycle states
2/3/4 and the exact `Mission_Auto` ordering of Piston damage, corpse state, and
Board cleanup remained open. The successor below closes the stock
Mission_Piston scheduler question without generalizing every lifecycle state.
Modded/direct-native mutation-12 activation and non-Windows depots also remain
outside this result.

## Native Mission_Piston scheduler boundary

`native/windows_build_13725832_31fe35265598_piston_scheduler_boundary.json`
joins the corpse-classification and event-frame maps to the exact shipped
Piston, mission-base, and environment sources. It binds 21 native regions, 15
instruction-start control windows, 13 direct call edges, three vtable pointers,
and the `Board:GetPawns` binding anchor. For Windows build `13725832` it
establishes that:

- `Board:GetPawns` filters the Board pawn vector without sorting it;
- AI planning copies that vector and stably retains team-6 or Neutral pawns,
  while queued-pawn execution scans the same vector and returns the first
  still-queued pawn;
- the queued predicate requires a skill manager, valid target coordinates, and
  a nonnegative action index, with Board activity required to clear before the
  next selection;
- explicit `Pawn:Kill`, standalone reset, and the tail of shared Pawn update
  clear the target/action fields. A Piston killed before its vector slot loses
  its push while `Corpse=true` preserves the wreck as occupancy; and
- `Mission_Piston` declares no Environment override and inherits no-op
  `Env_Null`, so no environment action changes the Piston/Vek interleave.

Verify the executable, both predecessor maps, exact selected sources,
region/control hashes, direct edges, pointers, and solver binding with:

```powershell
python scripts/itb_observatory_piston_scheduler.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_piston_scheduler_boundary.json
```

Simulator v408 preserves native Board-vector order in the bridge, interleaves
each living Piston push with queued Vek in Rust, and cancels dead-Piston actions
without deleting their corpse occupancy. Complete known active, corpse-only,
and empty payloads are forecastable; missing, partial, duplicated,
orientation-mismatched, or reordered evidence still fails closed. The pre-v408
corpus is archived as `recordings/failure_db_snapshot_sim_v407.jsonl`. At this
artifact stage, setup RNG and rejected-placement draw order remained open; the
successor below closes that parameterized stock boundary. General non-Piston
lifecycle states 2/3/4, presentation-only timing, mods, and non-Windows depots
remain separate gaps.
The deployed v408 bridge is admitted as a separately hash-pinned
post-publication overlay by predecessor source-tree verifiers; their published
evidence bodies and original overlay inventories remain byte-immutable.

## Native Mission_Piston setup boundary and replay

`native/windows_build_13725832_31fe35265598_piston_setup_boundary.json`
refines the scheduler artifact with the exact pre-board setup grammar. It binds
33 native regions, 18 instruction-aligned control windows, 22 direct edges,
eight Lua bindings, the native direction constants/vectors, the complete
118-entry direct RNG-call catalog, six exact Lua sources, and all seven eligible
map files. For the current Windows installation it proves:

- the `RandomMap(pistons, acid)` pool is `acid0`, `acid1`, `acid10`, `acid11`,
  `acid15`, `acid3`, and `acid4` in that order;
- native map loading preserves each `pistons` Lua array's first-occurrence
  order, `Board:GetZone` copies it without sorting, and `extract_table` indexes
  it unchanged;
- every attempt consumes one positive-bound `random_int` for
  `random_removal`; a rejected source stops there, while an accepted source
  consumes a direction draw and one unconditional raw draw in the common Pawn
  constructor;
- `Board:AddPawn` has a two-RNG random-position fallback, but that call is
  guarded by coordinate invalidity and cannot run for the exact valid 8x8 zone
  points; and
- the exact draw formula is `attempts + 2 * accepted placements`. The bundled
  replay dynamically accounts for new Piston occupancy and removal of the
  chosen forward zone point.

Reverify the executable, predecessor artifacts, source/map identities, native
regions and calls, bindings, direction anchors, and RNG catalog with:

```powershell
python scripts/itb_observatory_piston_setup.py verify `
  --executable "<Into the Breach>\Breach.exe" `
  --content-root "<Into the Breach>" `
  --boundary-map data/observatory/native/windows_build_13725832_31fe35265598_piston_setup_boundary.json
```

Replay one selected map from the observable MSVC state immediately before
`StartMission`'s first zone-removal draw with:

```powershell
python scripts/itb_observatory_piston_setup.py replay `
  --map-name acid1 `
  --rng-state 0x12345678
```

This closes the old `mission_piston_setup_rng` gap as a parameterized exact
boundary, not as a concrete future forecast. The shared CRT state before the
one-entry map-tag draw, the current used-map registry/retry count, and the
future selected map are not ordinary solver inputs. Rust therefore remains at
simulator v408 and continues to consume the authoritative settled bridge board.
Concrete runtime UIDs/constructor values, mods, other depots, and non-Windows
equivalence remain outside the artifact.
