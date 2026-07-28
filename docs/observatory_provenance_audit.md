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
| Player weapons | 14 | 6 | 8 |
| Missions | 75 | 11 | 64 |
| Environments | 15 | 6 | 9 |
| Unique total | 96 | 24 | 72 |

Mission-specific environment files belong to both the mission and environment
categories, so category totals overlap while the summary counts unique paths.

The exact callback audit finds 742 active top-level callback definition
instances, representing 741 unique `path + symbol` pairs. Current provenance
names 80 definitions literally and leaves 662 unindexed. Category totals
overlap for mission-environment files. Most importantly, the two broad enemy
weapon files contain 40 callback definitions; the Starfish, Bouncer, Moth,
Tumblebug, and Centipede family records name ten literally and leave 30
unindexed. That is a precise indexing backlog, not evidence that all 30
behaviors are absent from Rust.

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
It remains `partial`: native path/effect helpers and exhaustive edge
conformance are not traced, even though the damage-only B variant now has a
dedicated end-to-end simulator case. This improves record granularity without
changing the file-index count because `weapons_prime.lua` was already present
in the umbrella record.
The reusable lexical inventory behind further family selection is documented
in [`observatory_player_weapon_id_index.md`](observatory_player_weapon_id_index.md).

The second slice, `player-weapon-rocket-artillery`, adds the exact
`weapons_ranged.lua` family and its inherited `LineArtillery:GetTargetArea`
source in `weapons_base.lua`. It ties all four `Ranged_Rocket` IDs to Rust
definitions, family smoke/push dispatch, and Rocket-focused generic artillery
targeting/replay regressions. It remains `partial` because Rust intentionally
filters intact building centers that Lua permits, while native effect ordering
and exhaustive collision/status conformance are unresolved. All four exact IDs
now have end-to-end damage, push, and smoke dispatch coverage.

The third slice, `player-weapon-aerial-bombs`, pins the exact
`weapons_brute.lua` family and all four `Brute_Jetmech` variants to Rust leap
simulation, landing restrictions, target enumeration, and transit-effect
scoring. It remains `partial`: native path/effect helpers and exhaustive
terrain/status ordering are not traced. Exact base/A/B/AB dispatch, damage,
smoke, and base-versus-upgraded range enumeration now have focused coverage.

The fourth slice, `player-weapon-reverse-thrusters`, adds the exact Advanced
Edition `ae_weapons.lua` source and all four `Brute_KickBack` variants. It
connects the Lua dash, distance-scaled backblast, smoke, and recoil behavior to
Rust landing checks, simulation, scoring, achievement events, and replay. It
remains `partial`: native path/effect helpers and exhaustive landing, terrain,
status, and collision behavior are untraced. Exact A/B range-three and AB
range-four dispatch now pins backblast damage, smoke, recoil, and movement.

The fifth slice, `player-weapon-control-shot`, reuses that exact
`ae_weapons.lua` hash but adds family-level evidence for all four
`Science_TC_Control` variants. It records a concrete fidelity gap rather than
raising the file count: Rust restricts first-click eligibility to enemies and
does not reproduce several Lua `IsControllable` branches, including powered,
guarding/burrower, base-move, grappled zero-speed, Snowmine, and VIP Truck
cases. Fixed adjacent first-click range and the separate maximum 2/3/3/4
controlled movement budgets are now explicit. Native pawn predicates, path
effects, and visible UI behavior remain unresolved.

The sixth slice, `player-weapon-needle-shot`, adds the previously unindexed
`weapons_technovek.lua` source plus inherited Spear targeting. It pins all four
`Vek_Hornet` IDs, exact 1/2/2/3 range and damage, full-line damage,
farthest-only push, collision regressions, and bridge replay. It remains
`partial`: native effect helpers are untraced, Rust deliberately omits an
otherwise-empty intact-building target that Lua publishes, and exhaustive
terrain/status/collision conformance is open.

The first family-level enemy-weapon slice, `enemy-weapon-starfish`, pins the
normal, alpha, and leader pawn-to-weapon mappings and all five family-specific
Lua callbacks across the exact Advanced Edition weapon and boss sources. The
two callbacks in the core enemy-weapon audit are now indexed. Rust's distinct
IDs, 1/2/3 diagonal damage, leader cardinal pushes, projected reach, threat
capture, prior-attack death, and ambiguous queued-marker handling all have
focused tests. Simulator v368 fixes a proven projection gap by queueing the
Starfish's sole Lua target—its own tile—when the known diagonal `ScoreList`
footprint is positive, instead of substituting scalar pseudo-pressure. The
record remains `partial`: native movement/candidate selection, every
`ScoreList` branch, effect helpers, and exhaustive edge/status/collision
behavior are not reproduced or independently traced.

The second family-level enemy-weapon slice, `enemy-weapon-bouncer`, pins normal,
alpha, and leader pawn-to-weapon mappings plus the exact Advanced Edition
weapon and boss effects. Distinct IDs, 1/3/2 damage, backward recoil, forward
target push, the leader's ordered three-tile sweep, collision, displacement,
and mission-order interactions have focused tests. It adds one literal
callback from the core enemy-weapon backlog without changing simulator
semantics. The record remains `partial`: native target selection and effect
helpers are untraced, exhaustive edge/status/collision conformance is open,
and the leader's generic edge-recoil policy lacks focused live evidence.

The third family-level enemy-weapon slice, `enemy-weapon-moth`, pins normal and
alpha pawn mappings, their exact Advanced Edition effect, and inherited
`LineArtillery` targeting. Simulator v369 fixes the proven range mismatch:
Rust and Python definitions plus queued resolution now enforce Lua's cardinal
distances 2–5, and webbed projection no longer invents distance-six/seven targets. Exact
1/3 damage, valid and invalid range boundaries, recoil, killed-target
collision, prior-corpse ordering, train interaction, marker reconciliation,
and threat auditing have focused tests. The record remains `partial`: native
movement/selection and effect helpers are untraced, mobile projection is
heuristic, and exhaustive edge/status/collision behavior remains open.

The fourth family-level enemy-weapon slice, `enemy-weapon-tumblebug`, pins the
live `Dung1`/`Dung2`/ranged `DungBoss` pawn and weapon IDs, all four family
callbacks, the neutral `BombRock`, and the Leader's inherited two-rock variant.
Simulator v370 fixes proven gaps: live IDs now round-trip canonically without
collapsing the Leader onto the Alpha weapon, Python preserves the live Leader
ranged flag, and next-turn projection materializes the immediate one/two
boulders before queueing the first-tile hit.
Source-stated Pod/chasm/water/occupied boundaries, the blocked-first/second-rock
dependency, chain detonation, existing enemy-phase ordering, Python aliases,
the positive ScoreList gate, and threat auditing have focused tests. The record
remains `partial`: mobile movement and direction selection are heuristic,
`Board:GetDeployLocScore` and native tie-breaking are untraced, current-turn
execution consumes bridge-selected boulders, and exhaustive
terrain/status/scheduler behavior remains open. The exact Leader source is
outside the audit's selected 96-file high-value candidate set, so this family
does not change the source-index totals.

The fifth family-level enemy-weapon slice, `enemy-weapon-centipede`, pins the
normal, Alpha, and Leader pawn/weapon IDs, damage values, unlimited projectile
range, ACID impact T, direct-enemy candidate rejection, and the Leader's strict
pre-impact ACID trail. Exact mappings plus normal/Alpha/Leader damage and ACID
footprints, ground/water conversion, board-edge impact, Python definitions,
known types, and static pawn metadata have focused tests. The record remains
`partial`: current-turn resolution consumes the bridge-selected target, mobile
projection is generic, and native movement, candidate enumeration,
`GetProjectileEnd`, `ScoreList`, effect scheduling, selection, and tie-breaking
remain untraced. The pawn and Leader files are outside the audit's selected
96-file high-value source set, so the family indexes two callbacks without
changing source-index totals.

The first mission-objective slice, `mission-supply-train`, pins both the base
Supply Train mission and the Advanced Edition Armored Train child. It covers
the inherited mission lifecycle, two-tile normal/damaged replacements,
one-reputation degradation, normal stop-on-block versus armored
destroy-and-charge movement, and source-defined smoke/fire immunities.
Simulator v371 fixes the proven fire mismatch: all four train identities now
reject ignition and stale fire ticks, while Python fallback metadata preserves
the standard train's move-zero, nonpushable, and smoke/fire flags. Focused
tests cover clear, blocked, frozen, smoked, shielded, replaced, degraded, and
fire-exposed trains. The record remains `partial`: Rust infers rail direction
from serialized multi-space tiles, and native blocker, effect queue, pawn
factory, objective UI, scheduler, corpse, and exhaustive terrain/status
semantics remain untraced.

The second mission-objective slice, `mission-reactivation`, pins the compact
Pinnacle thaw mission's exact frozen roster setup and two-per-enemy-turn
callback. Rust's pre-attack hook and three focused tests preserve the important
thaw cap and mission gate. The record remains `partial` and names the known
selection mismatch explicitly: Lua randomly consumes only IDs captured at
mission start, including dead or already-thawed entries, while Rust
deterministically thaws the lowest-UID living frozen enemies on the current
board. Setup placement, spawner/native robot choice, RNG state, and helper
ordering remain untraced.

The third mission-objective slice, `mission-dam-flood`, pins the exact
two-tile, two-HP destroy objective and its one-shot 2-by-7 Water conversion.
Rust's damage/flood path plus Python objective metadata have focused coverage
for multi-tile HP, flood ordering, pod destruction, fire clearing, drowning,
Blast Psion side effects, and the enemy-phase burning-dam guard. It remains
`partial`: live placement and initial Water are consumed from the bridge,
native objective/scheduler/effect helpers are untraced, and presentation-only
shake, bounce, delay, voice, and UI behavior are intentionally omitted.

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
lane advancement. Rust now applies exact full-row water conversion and derives
the permanent spawn-block boundary plus markerless future warning from the
source `Index`. It remains `partial`: the dormant bridge export has not been
installed during the protected live session, native blocked-cell and scheduler
helpers are untraced, and flyer/timing evidence remains live-derived.

The inherited `environment-mission-terratide` slice pins its exact Advanced
Edition source plus the base Tides implementation. It covers full-row smoke,
pre-attack cancellation, reverse warning advancement, and the fact that a
prior-row building does not shadow the next warning. It remains `partial`
because the bridge does not export `Env_Terratide.Index`, native scheduling and
smoke interactions are not exhaustive, and initial smoke/permanent spawn setup
is consumed from live state rather than independently generated.

The Conveyor Belt slice, `environment-mission-belt-conveyors`, adds the exact
`mission_belt.lua` source and all 12 of its top-level callbacks. It connects
live bridge/save extraction to engine-direction normalization, standard
before-attack and random after-attack movement, threat auditing, and projected
checkpoint round-trips. Simulator v367 fixes a proven checkpoint bug where
already-normalized directions 0 and 2 were serialized as raw engine values and
normalized a second time on reload. The record remains `partial`: native path,
quarter, RNG, setup, scheduler, and effect-order behavior is not reproduced or
independently traced, and live extraction/status/collision coverage is not
exhaustive.

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
