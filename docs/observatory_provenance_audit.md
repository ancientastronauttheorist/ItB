# Observatory provenance source-index audit

## Purpose

The build-keyed mechanics provenance index explains which shipped Lua evidence
supports each Rust coverage claim. This audit answers a narrower, mechanical
question:

> Which high-value shipped Lua files appear in at least one provenance record?

“Indexed” does **not** mean implemented, conformant, or verified. Those claims
remain record-level evidence with explicit coverage and known gaps.

Run the deterministic read-only audit with:

```text
python scripts/itb_provenance.py \
  data/observatory/mechanics_provenance.json \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  --audit-sources
```

The validator first proves that the inventory content exactly matches the path
embedded in the provenance document, validates all source hashes, and checks
repository references. The audit then selects high-value Lua paths from that
inventory; it never scans or modifies the installed game.

## Current result

For the modified local Windows inventory at scripts revision
`591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155`:

| Category | Candidate files | Indexed | Unindexed |
|---|---:|---:|---:|
| Spawn selection | 3 | 2 | 1 |
| Enemy scoring | 2 | 2 | 0 |
| Enemy weapons | 2 | 2 | 0 |
| Player weapons | 14 | 1 | 13 |
| Missions | 75 | 1 | 74 |
| Environments | 15 | 1 | 14 |
| Unique total | 97 | 9 | 88 |

Mission-specific environment files belong to both the mission and environment
categories, so category totals overlap while the summary counts unique paths.

This is not evidence that spawn, scoring, or enemy weapons are complete: their
existing records remain `native_dependency` or `partial`. The spawn audit also
shows that `scripts/spawner.lua`, which contains difficulty/island parameters,
is not yet named by the provenance index. Conversely, the large player-weapon
and mission gaps mean the current broad records do not enumerate most exact
source files, even where Rust behavior and tests already exist.

## Highest-value expansion order

1. Split player weapons into family-level records and tie each exact source hash
   to its `WId`/simulator cases and focused tests.
2. Add mission records only when a static callback, Rust transition, and
   regression fixture can be named precisely; do not bulk-index files merely to
   improve the count.
3. Add `env_final.lua` and `env_volcano.lua` alongside exact phase-order and
   effect conformance tests.
4. Keep native-dependent target selection and RNG records non-verified until a
   build-keyed trace supplies the missing boundary evidence.

The audit should trend toward fewer unindexed files, but the governing metric is
trustworthy file-to-implementation evidence, not 100% indexing by itself.
