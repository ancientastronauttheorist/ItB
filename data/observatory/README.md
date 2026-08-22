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
`1f207101f8826c1c131f432ca0670e45dcec8ef74b04a4f3395b55b16a2757fd`.
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
