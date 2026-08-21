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
