# ITB Engine Observatory data

This directory contains build-keyed, read-only evidence about installed
Into the Breach implementations. It must not contain game binaries or
proprietary decompiled source.

## Installation inventories

Create a deterministic inventory outside the installed game:

```text
python scripts/itb_content_inventory.py inventory \
  --install-dir "<Into the Breach install>" \
  --label "<provenance note>" \
  --output data/observatory/inventories/<snapshot>.json
```

The tool hashes the native executable, shared libraries, and every regular file
under `scripts/**` and `maps/**`. Paths are relative and slash-normalized.
Filesystem timestamps and the absolute installation path are excluded.
Symlinks are not followed. Steam build/depot evidence is accepted only when the
adjacent app manifest names the exact inventoried directory.

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

Matched runtime `IsCorpse()` values across pawn subclasses, transient-pawn
removal timing between actions, matched output vectors, and `AddMove`
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

This is a relative static order proof, not a runtime timestamp. The native
event that advances either always-blocked Final mission, queued `MissionEnd`
effect settlement, the cave countdown outcome, and non-Windows equivalence
remain explicit gaps. The following artifact closes the static cave-startup
order while retaining concrete RNG and settlement as gaps. No current-turn
Rust simulator change follows from either map; the safe boundary remains a
fresh bridge read after the live stage change.

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
The following artifact supersedes its first two map-choice questions; the
remaining startup boundaries stay explicit.

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
