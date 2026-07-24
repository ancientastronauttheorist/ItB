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

Extract the build-keyed record-level work queue with the same validator:

```text
python scripts/itb_provenance.py \
  data/observatory/mechanics_provenance.json \
  data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json \
  --audit-gaps
```

The gap audit emits validated source paths, known gaps, and classification-
preserving hypothesis/unresolved evidence for every non-verified record, plus
any verified record that still carries open evidence. The deterministic
alphabetical output is a work inventory, not a severity ranking or permission
to change solver behavior without the normal simulator-version and
conformance-test discipline.

The validator first proves that the inventory content exactly matches the path
embedded in the provenance document, validates all source hashes, and checks
repository references. Repository symbols without whitespace or wildcards are
also treated as literal anchors and must occur in their claimed file; this
catches a real test or implementation symbol being attributed to the wrong
module. Descriptive labels and asterisk (`*`) wildcard families remain
human-reviewed. The audit then selects high-value Lua paths from that inventory;
it never scans or modifies the installed game.

## Current result

For the modified local Windows inventory at scripts revision
`591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155`:

| Category | Candidate files | Indexed | Unindexed |
|---|---:|---:|---:|
| Spawn selection | 3 | 3 | 0 |
| Enemy scoring | 1 | 1 | 0 |
| Enemy weapons | 2 | 2 | 0 |
| Player weapons | 14 | 5 | 9 |
| Missions | 75 | 5 | 70 |
| Environments | 15 | 4 | 11 |
| Unique total | 96 | 17 | 79 |

Mission-specific environment files belong to both the mission and environment
categories, so category totals overlap while the summary counts unique paths.

This is not evidence that spawn, scoring, or enemy weapons are complete: their
existing records remain `native_dependency` or `partial`. All three selected
spawn files are now named, including the exact 16-cell difficulty/sector matrix
in `scripts/spawner.lua`, but Rust still projects marker persistence/blocking
without applying that matrix or materializing the selected pawn. Native roster
selection, RNG state, and call order remain unresolved. Conversely, the large
player-weapon and mission gaps mean the current broad records do not enumerate
most exact source files, even where Rust behavior and tests already exist.

The first family-level player-weapon slice is
`player-weapon-titan-fist`. It pins the exact `weapons_prime.lua` hash, all four
`Prime_Punchmech` Lua variants, their Rust `WId`/melee/charge implementations,
and focused definition, simulator, solver-targeting, and bridge-replay tests.
It remains `partial`: native path/effect helpers are not traced, the B variant
lacks a dedicated end-to-end simulator case, and exhaustive edge conformance is
not claimed. This improves record granularity without changing the file-index
count because `weapons_prime.lua` was already present in the umbrella record.
The reusable lexical inventory behind further family selection is documented
in [`observatory_player_weapon_id_index.md`](observatory_player_weapon_id_index.md).

The second slice, `player-weapon-rocket-artillery`, adds the exact
`weapons_ranged.lua` family and its inherited `LineArtillery:GetTargetArea`
source in `weapons_base.lua`. It ties all four `Ranged_Rocket` IDs to Rust
definitions, family smoke/push dispatch, and Rocket-focused generic artillery
targeting/replay regressions. It remains `partial` because Rust intentionally
filters intact building centers that Lua permits, while native effect ordering,
dedicated B/AB end-to-end cases, and exhaustive collision/status conformance
are unresolved.

The third slice, `player-weapon-aerial-bombs`, pins the exact
`weapons_brute.lua` family and all four `Brute_Jetmech` variants to Rust leap
simulation, landing restrictions, target enumeration, and transit-effect
scoring. It remains `partial`: native path/effect helpers are not traced,
damage-two variants lack exact-ID end-to-end simulator cases, and the current
range-upgraded transit tests call `sim_leap` directly with the unchanged base
ID and definition at distance three, bypassing B/AB dispatch and range-three
target enumeration.

The fourth slice, `player-weapon-reverse-thrusters`, adds the exact Advanced
Edition `ae_weapons.lua` source and all four `Brute_KickBack` variants. It
connects the Lua dash, distance-scaled backblast, smoke, and recoil behavior to
Rust landing checks, simulation, scoring, achievement events, and replay. It
remains `partial`: behavior tests use only the base ID, native path/effect
helpers are untraced, and the range-three/range-four variants lack exact-ID
end-to-end targeting and damage cases.

The fifth slice, `player-weapon-control-shot`, reuses that exact
`ae_weapons.lua` hash but adds family-level evidence for all four
`Science_TC_Control` variants. It records a concrete fidelity gap rather than
raising the file count: Rust restricts first-click eligibility to enemies and
does not reproduce several Lua `IsControllable` branches, including powered,
guarding/burrower, base-move, grappled zero-speed, Snowmine, and VIP Truck
cases. Fixed adjacent first-click range and the separate maximum 2/3/3/4
controlled movement budgets are now explicit. Native pawn predicates, path
effects, and visible UI behavior remain unresolved.

The first mission-environment slice, `environment-mission-wind`, pins the
self-contained Advanced Edition Wind mission source to direction parsing and
pre-attack push simulation plus four focused tests, including three
live-derived regressions.
It remains `partial`: Rust consumes bridge-supplied lanes/direction rather than
reproducing Lua/native RNG planning, and native scheduler plus
bridge-extraction conformance remain unresolved.

The second mission-environment slice, `environment-mission-tides`, pins the
exact base Tidal Waves mission to warning ingestion, post-attack danger
resolution, observed flyer damage, pod destruction, and projected/replayed
lane advancement. It remains `partial`: Rust does not convert flooded tiles to
water, reproduce Lua's permanent spawn blocking, or reconstruct the native
environment scheduler and `SpaceDamage.iTerrain` semantics. The exact
attack-before-wave and flyer-damage rules are supported by live-derived
regressions, not by the Lua file alone.

The third mission-environment slice, `environment-final-cave-danger`, pins the
exact Final Cave `env_final.lua` source to Rust's marked-tile lethal-danger
ingestion and its live-derived stale-flying-immunity regression. It remains
`partial`: Rust consumes the selected mask without reproducing the four-phase
selector, modes, RNG, scheduling, BigBomb exclusion, or enemy avoidance, and
does not apply the source's road/lava terrain aftermath. `env_volcano.lua`
remains unindexed because no focused Rust mode, terrain, fire, phase, or
selection conformance test exists yet.

## Highest-value expansion order

1. Continue splitting player weapons into family-level records, using the Titan
   Fist slice as the minimum evidence pattern.
2. Add mission records only when a static callback, Rust transition, and
   regression fixture can be named precisely; do not bulk-index files merely to
   improve the count.
3. Add `env_volcano.lua` only after exact mode, phase-order, terrain, fire, and
   selection conformance tests exist.
4. Keep native-dependent target selection and RNG records non-verified until a
   build-keyed trace supplies the missing boundary evidence.

The audit should trend toward fewer unindexed files, but the governing metric is
trustworthy file-to-implementation evidence, not 100% indexing by itself.
