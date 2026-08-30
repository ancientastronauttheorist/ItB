# Static map-data census

This directory is the publication boundary for build-keyed, non-executing
analysis of Into the Breach's Lua-form `.map` chunks. Eligible artifacts may
contain exact file identities, structural counts, field/type domains, and
aggregate string domains. They must not contain raw map source, layout-derived
hashes, per-map coordinates or tag membership, reconstructable layouts,
executed Lua, decompiler output, or absolute installation paths.

The current Windows artifact is
`windows_build_13725832_31fe35265598_map_census.json`. Its exact-install
verification establishes:

- all 376 `.map` chunks parse as one strict, declarative
  `file_stem = table` assignment without executing Lua;
- every global matches its filename stem, every chunk reports version 7 and
  dimensions `8 x 8`, and all 269 present `name` fields match the stem;
- 8,915 explicit tile records have unique in-bounds locations, ten observed
  field sequences, and nine observed numeric `terrain` values;
- all three spawn-related source tables are empty in every chunk;
- 381 zone instances use 25 observed keys and contain 2,535 in-bounds point
  entries, with no duplicates inside an individual zone array;
- 961 tag entries use 32 observed values with no per-map duplicates; and
- `maps/maphelper.lua` plus every data chunk is identity-matched to the prior
  compiled-but-never-executed Lua census.

The artifact's pretty-printed file SHA-256 is
`2f691d3084b7dc67490432ddfbee2a8a5ed19e786ebf16c7e0525ab4befd77f8`.
The verifier's canonical JSON SHA-256 is
`a7d849321392b0e6da7e95b2056104ed68a9c5fc03db5724647d470afe7ea26a`.

## Grammar and publication boundary

`src/observatory/lua_data.py` is a fail-closed parser, not a Lua runtime. It
accepts one global table assignment whose values are nonnegative integers,
unescaped short strings, booleans, nested tables, or `Point(integer,integer)`.
It rejects arbitrary identifiers, calls, operators, functions, multiple
statements, string escapes, excessive integer width, and excessive table
nesting, token count, table-entry count, string width, or source width.
Context-specific validation then requires the exact root/tile/zone/tag shapes
named in the artifact, rejects duplicate keys and coordinates, and fails on
currently unsupported nonempty source tables.

Per-map evidence publishes only the already-sealed source identity hash, field
sequences, counts, aggregate terrain counts, and zone names/counts. Coordinate
arrays, tag membership, layout-derived hashes, and raw source stay in the
owner's installed copy.
Aggregate domains retain only bounded identifier-shaped values such as tag
names, zone keys, pawn IDs, and custom ground-image basenames because those are
schema/domain facts, not reconstructable map layouts. A string outside those
strict publication forms fails the build instead of entering evidence.

## Build

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
python -X utf8 scripts/itb_map_census.py build `
  --install-dir $itbInstall `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --lua-census data/observatory/lua/windows_build_13725832_31fe35265598_lua51_census.json `
  --callback-index data/observatory/callbacks/windows_build_13725832_31fe35265598_callback_index.json `
  --output data/observatory/maps/windows_build_13725832_31fe35265598_map_census.json
```

The builder first regenerates and exact-matches the complete sealed
installation inventory. It then reruns the compiled Lua census verifier with
the exact callback index and inventoried Lua 5.1 DLL before accepting any
compiled-status join. Repository output is restricted to a direct child of
this directory and written atomically. An existing artifact of another kind is
never replaced.

## Verify

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
python -X utf8 scripts/itb_map_census.py verify `
  --install-dir $itbInstall `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --lua-census data/observatory/lua/windows_build_13725832_31fe35265598_lua51_census.json `
  --callback-index data/observatory/callbacks/windows_build_13725832_31fe35265598_callback_index.json `
  --evidence data/observatory/maps/windows_build_13725832_31fe35265598_map_census.json
```

Verification repeats the inventory attestation, complete compiled-Lua
verification and join, strict parse, schema checks, normalization, and
aggregation, then requires exact normalized equality.

## Claim boundary

This is a complete syntax/schema census for the sealed owner-build `.map`
corpus, not proof of engine semantics. In particular, numeric terrain and field
values remain observed identifiers; this artifact does not infer omitted-tile
defaults, runtime mutations, native parsing behavior, load success,
registration order, selection, or reachability. `maphelper.lua` behavior and
the Windows native directory-enumeration/bootstrap path remain separately
scoped Lua/native evidence. No pristine-depot or cross-build equality is
claimed.
