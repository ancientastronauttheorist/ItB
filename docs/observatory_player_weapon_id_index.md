# Observatory player-weapon Lua/Rust ID index

## Purpose

The player-weapon provenance backlog needs a reproducible first question before
family-level behavior review:

> Which active top-level Lua constructor or preservation-alias IDs have an
> exact direct arm in Rust `wid_from_str`?

`scripts/itb_weapon_coverage.py` answers only that lexical question. It binds
the result to the exact inventory build identity, verifies the size and SHA-256
of every selected Lua file before parsing, hashes normalized UTF-8
`rust_solver/src/weapons.rs`, and emits deterministic JSON without source
bodies or absolute paths.

Run it against the current Windows installation with:

```text
python scripts/itb_weapon_coverage.py \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  "B:\SteamLibrary\steamapps\common\Into the Breach"
```

The tool is read-only. The content root can point at another exact installation
or extracted depot; stale or missing bytes fail closed against the supplied
inventory.

## Conservative extraction contract

The Lua scanner masks short strings, generalized long-bracket strings, line
comments, and generalized long comments while preserving offsets. It then:

- retains active bare global `ID = Parent:new{...}` and
  `ID = Parent:new(ExistingTable)` constructors outside functions and table
  literals;
- retains a bare `ID = OtherID` alias chain only when it eventually reaches an
  active constructor candidate; dangling chains and constructor-free cycles are
  excluded;
- excludes locals, qualified/table fields, function-local assignments, and
  opaque/commented text;
- records source hash, line/column, constructor form, declared parent, selected
  target/effect method names, family/variant classification, and duplicates;
- groups `_AB`, `_A`, and `_B` only when the exact stripped base is also an
  active candidate.

The Rust scanner reads only the explicit `#[repr(u8)] WId` variants and direct
literal arms inside `wid_from_str`, after masking line and nested block comments
without hiding string literals. It rejects duplicate literals, duplicate or
out-of-range discriminants, missing referenced variants, and unsupported
complex arms. Many Lua IDs may legitimately map to one `WId`; those reverse
mappings are preserved rather than collapsed.

## Current exact-inventory result

For Windows build `13725832`, executable
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`,
and modified-install scripts revision
`591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155`:

| Measure | Count |
|---|---:|
| Exact selected Lua files | 14 |
| Active constructor candidates | 465 |
| Preservation aliases | 4 |
| Unique candidate IDs | 469 |
| Exact direct `wid_from_str` matches | 154 |
| No exact direct match | 315 |
| Ambiguous duplicate Lua IDs | 0 |
| Rust mappings outside selected definitions | 109 |
| Many-to-one Rust `WId` variants | 33 |

`scripts/advanced/ae_weapons_base.lua` and
`scripts/weapons_experiment.lua` contain zero active candidates under this
contract and remain present in the file-level output. The four aliases are the
obsolete `DeploySkill_SGenerator*` preservation names pointing at active
`DeploySkill_ShieldTank*` candidates.

These counts describe the exact modified-install inventory, not independently
verified vanilla depot bytes. They are also not behavioral coverage:

- an exact mapping does not prove a populated `WEAPONS` definition, target
  legality, simulator dispatch, test coverage, native helper semantics, or
  runtime load order;
- an absent mapping does not prove unsupported behavior because save overlays,
  aliases, inheritance, and runtime-only handling need separate review;
- Rust-only mappings include enemy, mission, compatibility, and other IDs
  outside this deliberately selected player-weapon source set.

## How to use the index

Use exact matches to choose small, well-tested families for provenance slices,
as with Titan Fist. For each family, separately inspect its Lua effect/target
functions, all powered variants, Rust definitions and dispatch, focused tests,
native-helper dependencies, and known edge gaps. Use absent and many-to-one
entries as review queues, never as automatic bug reports.

The next useful extension is a checked family-level report that joins this
lexical evidence to explicit Rust definition, dispatch, and test symbols
without upgrading any record to verified conformance automatically.
