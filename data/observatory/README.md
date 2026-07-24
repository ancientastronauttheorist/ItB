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
paths, duplicate records, unsupported status values, or a non-verified record
without an explicit gap.
