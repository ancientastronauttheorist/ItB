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
