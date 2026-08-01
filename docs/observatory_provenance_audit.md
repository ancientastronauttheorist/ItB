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
| Player weapons | 14 | 12 | 2 |
| Missions | 75 | 27 | 48 |
| Environments | 15 | 12 | 3 |
| Unique total | 96 | 46 | 50 |

Mission-specific environment files belong to both the mission and environment
categories, so category totals overlap while the summary counts unique paths.

The exact callback audit finds 742 active top-level callback definition
instances, representing 741 unique `path + symbol` pairs. Current provenance
names 200 definitions literally and leaves 542 unindexed. Category totals
overlap for mission-environment files. Most importantly, the two broad enemy
weapon files contain 40 callback definitions; the Starfish, Bouncer, Moth,
Tumblebug, Centipede, Digger, Shaman/Totem, and Crab/Scarab family records name
sixteen literally and leave 24 unindexed. That is a precise indexing backlog, not
evidence that all 24 behaviors are absent from Rust.

The Acid Vats slice adds the exact
`scripts/missions/acid/mission_barrels.lua` source and all nine of its active
callbacks. Lua places two neutral, two-HP `AcidVat` pawns from the satellite
zone, blocks mission end until the enemy-team `AcidVat` count reaches zero, and
awards full, partial, or failed reputation at zero, one, or any other remaining
vat count, respectively.
The source also converts a dead vat's tile to Water plus ACID. Rust preserves
that death terrain and the established AP Cannon regression ordering, where a
first target can enter the killed vat tile before the retained terrain conversion. Setup
randomness/IDs, objective UI timing, and exact effect scheduler ordering remain
explicit partial-coverage gaps.

The frozen-building mission slice adds the exact
`scripts/missions/snow/mission_freezebldg.lua` source and its four callbacks.
Lua snapshots the starting building coordinates, freezes them, and completes
the objective when at least five saved coordinates report not Frozen. It does
not check terrain, HP, or survival. Existing Python/Rust scoring requires an
alive, thawed building and is therefore documented as conservative rather than
source-exact: a controlled native capture must establish what `Board:IsFrozen`
returns for a destroyed original coordinate before rubble is credited or
denied.

The Crab/Scarab artillery slice reuses already-indexed exact base-game enemy,
weapon-base, and pawn sources, so it does not change the source-file totals. It
does name the previously unindexed `CrabAtk1:GetSkillEffect` callback. Both
families inherit cardinal selected targets at distance 2 through 5; Scarab
damages the selected tile, while Crab also damages the next tile forward, so a
legal range-five click can threaten range six. Rust now rejects illegal queued
clicks beyond five while retaining that one-tile Crab footprint. Concrete
projected queues remain legal from the current modeled origin; movement-based
pressure without a projected firing origin stays scalar instead of becoming an
impossible queued shot. Native target selection, movement, RNG, effect
scheduling, and exhaustive collision/status interactions remain explicit
partial-coverage gaps.

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

The seventh slice, `player-weapon-support-wind`, adds the exact
`weapons_support.lua` source and both `Support_Wind` IDs. It pins all sixteen
Lua target tiles, their four 2x2 zone groups, direction precedence, scan order,
zero-damage pushes, and base-versus-upgraded use limits to the Python and Rust
global-push implementations. Focused tests cover target directions, sequential
movement, building bump damage, and attack classification. It remains
`partial`: Rust intentionally searches one effect-equivalent representative per
zone, does not independently track the base weapon's cross-turn use limit, and
native effect scheduling, presentation, and pawn-space edge cases are untraced.

The eighth slice, `player-weapon-repulse`, adds the previously unindexed
`weapons_science.lua` source and separates all four Repulse IDs. Simulator
v375 preserves the common zero-damage outward pushes, B/AB Shield Friendly on
adjacent player-team pawns and buildings, and A/AB Shield Self after the four
adjacent effects. Save overlays, Python definitions, known Rust IDs, target
enumeration, simulation, and replay serialization are covered by focused
tests. It remains `partial`: Rust canonicalizes the source's five
effect-equivalent target choices to the center, while native combined
Shield/push/collision ordering, off-board targets, building edge states,
animations, and scheduling remain untraced.

The ninth slice, `player-weapon-deploy-tank`, adds the previously unindexed
`weapons_deploy.lua` source plus its inherited `TankDefault` target/effect
callbacks in `weapons_base.lua`. The exact base cannon deals zero damage and
pushes the first projectile blocker forward; the upgraded cannon inherits the
same path and push with two damage. Rust keeps one adjacent representative for
each cardinal direction, then traces the projectile to its first blocker.
Focused Rust and Python tests now cover both base push and upgraded
damage-plus-push without changing simulator semantics. The record remains
`partial`: native `Board:GetSimpleReachable`, the complete legal target area,
`GetProjectileEnd`, exhaustive path/blocker cases, and `SpaceDamage` ordering
are untraced.

The first dedicated mission-conversion slice, `mission-hacking-conversion`,
adds the previously unindexed `mission_hacking.lua` source and the exact
`Mission:BaseUpdate` callback that dispatches its update. Simulator v376
replaces the hostile `Snowtank1` with a fresh active `Snowtank1_Player` after
the exact stored facility dies, using the paired `BotID` and `HackID` exported
by the Lua bridge instead of guessing from pawn type. It preserves only the
bot's tile and Shield, assigns the Mark I cannon, stores the fresh UID back as
`BotID`, excludes the intentional UID replacement from death accounting, and
matches live fresh UIDs by type plus tile during verification. Focused tests
cover strict bridge/reader/model/serde identity handling, round trips, an
unrelated `Snowtank1` regression, source-defined state reset, player-action and
enemy-tail boundaries, cannon use, death accounting, and UID drift. The record
remains `partial`: legacy or not-yet-installed bridge payloads omit the pair and
therefore fail closed, native setup RNG/placement is unmodeled, and per-update
timing against animations or an already queued enemy bot attack remains
untraced.

The second dedicated mission slice, `mission-satellite-launch`, adds the
previously unindexed `mission_satellites.lua` source and all nine of its active
callbacks. It pins two random non-adjacent setup tiles, turns-one-and-three
powering, the source distinction between a gone/saved rocket and a
present/destroyed one, exact SatelliteRocket stats, and the four queued
cardinal `DAMAGE_DEATH` effects followed by `FlyAway`. Simulator v377 keeps the
exact mission-scoped `queued_launch` bridge bit through projected checkpoints,
applies observed exhaust after queued Vek attacks, kills an enemy still on an
exact source-defined exhaust tile, removes only the still-live launching rocket
without counting a death, and clears consumed markers. Legacy markers without
exact rocket identity retain conservative no-kill credit.
Focused tests cover mission/type scoping, round trips, grounded versus flying
exhaust, destroyed-versus-launched identity, death accounting, stale marker
cleanup, and the existing threat-audit regressions. The record remains
`partial`: setup RNG/native helpers, the native cause of flyer immunity, exact
effect scheduling, unusual displacement/race states, and direct Satellite
objective scoring remain open.

The `snow-bot-family-and-defense` slice adds the exact `weapons_snow.lua`,
`Mission_BotDefense`, and Bot Leader sources, plus all thirteen active
callbacks across those files. It traces the Snowtank fire cannon, queued
Snowlaser, Snowart's range-2-to-5 target-plus-perpendicular artillery, and
Mine-Bot Setup: an otherwise zero-speed bot receives native reachable-path
destinations out to three tiles, lays `Freeze_Mine` on its origin, then moves.
It also records that Bot Defense changes the two exact `Snowmine1` pawns to the
player team and scores only those stored IDs, and that the Bot Leader inherits
Snowart's footprint while selecting queued self-repair when damaged. The v378
implementation links Mine-Bot actor/target/simulation handling, static
Snow-family definitions, and queued-artillery side-hit threat coverage. The
record remains `partial`: native `GetReachable`/`GetPath`/path-profile behavior,
`AvoidingMines`, movement/item scheduling, setup placement, and enemy AI/RNG
are all explicitly outside the proven contract.

The tenth player-weapon slice, `player-weapon-passive-board-effects`, adds the
previously unindexed `weapons_passive.lua`, `advanced/ae_weapons_base.lua`, and
`advanced/ae_weapons.lua` sources. It records all 22 powered base-game IDs over
15 passive families, the four base-only Advanced Edition passives, and all 14
passive tooltip callbacks, while keeping these global board modifiers out of
clickable Rust `WId` action slots. Simulator v379 preserves the exact Storm
Generator 1/2 and Vek Hormones 1/2/2/3 magnitudes, repeats Repair over every
living player Mech, shields surviving damaged buildings immediately, and
exempts player Mechs from spawn-block damage under Stabilizers. Simulator v380
adds player-phase numeric-damage protection for Networked Shielding and
post-attack actual unit/building HP-loss evaluation for Void Shocker, including
the source-defined `VoidShockImmune` pawn flag. Nanofilter Mending and Heat
Engines are source-catalogued under their shipped names, and the orphan
localization-only Void Shocker upgrade is deliberately not modeled because the
source, executable, and save corpus expose no runtime upgrade ID. The bridge's
direct Repair executor mirrors the source TEAM_MECH loop, and raw-loadout plus
powered-mod save overlays retain exact passive variants. Psionic Receiver,
Ammo Generator, Critical Shields, Forestry Nano, native Networked
Armor/Kickoff timing, exhaustive Auto-Shields scheduling, and unusual native
terrain/script ordering around the v380 passives remain explicit gaps pending
controlled build-keyed traces.

The eleventh player-weapon slice, `player-weapon-firestorm-generator`, proves a
source-level targeting override that the simulator previously missed. Although
base `LineArtillery` starts at distance two, `Science_RainingFire` replaces its
target callback and enumerates every cardinal tile from distance one through
`ArtillerySize`; its base/A/B/AB maxima are 2/3/4/5. Simulator v381 therefore
restores adjacent Firestorm targets in definitions, solver enumeration, effect
pruning, and execution. The endpoint receives Fire plus forward push, while
only non-endpoint line tiles receive the intermediate Fire effect. Native
helper ordering and exhaustive status, terrain, pod, collision, and death-chain
interactions remain explicitly partial.

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

The sixth family-level enemy-weapon slice, `enemy-weapon-digger`, pins the
self-only target, exact cardinal `PATH_PROJECTILE`/Water/Time-Pod wall
predicate, separate queued 1/2 damage, Digger pawn mappings, and the neutral
one-HP zero-move `Wall` definition. Simulator v384 closes the proven state gap:
source-eligible empty cardinals now retain real neutral Wall pawns after the
Digger's own hit in native up/right/down/left source order, and those pawns
block or collide with later attacks. Focused
tests cover base/Alpha damage, each established exclusion, later-projectile
collision, board capacity, and the existing destroyed-Wall action-boundary
cleanup. A retained bridge board independently corroborates persistent live
Walls. The record remains `partial`: exact native `sPawn` scheduler timing,
`PATH_PROJECTILE` and placement behavior across less common terrain/status
combinations, native capacity, movement/selection, attack-order choice, and RNG
remain untraced. Both source files were already indexed, so source totals do
not change; its two literal callbacks reduce the exact callback backlog.

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

The fourth mission-objective slice, `mission-teleporter-pads`, pins the compact
mission setup that searches each quarter for an unblocked valid point, with
explicit list-exhaustion behavior, then pairs four results into two native
teleporter links. The bridge captures live pairs with mission-lifecycle
cleanup, and Rust scopes them to `Mission_Teleporter` before applying
bidirectional landing swaps. Focused tests cover scoping, both pair directions,
ordinary and lethal-mine landings, empty pairs, and post-swap targeting. It
remains `partial`: quarter selection, validity/blocking helpers, RNG,
`Board:AddTeleport`, native timing/chaining, and UI behavior are not
independently reproduced.

The fifth mission-objective slice, `mission-acid-tank`, adds the exact compact
A.C.I.D. Tank mission and all six active callbacks. Its source fixes the ally
at one HP and Move four, defines a zero-damage/no-push ACID projectile, counts
the native `EVENT_ACID_DESTROYED` counter, and awards full credit at four.
Simulator v383 closes
a concrete fallback contradiction: Python static state and Rust payloads that
omit movement now use Move four instead of the generic Move three. Both import
paths prefer current move, then base move, then that source default, so
explicit live movement remains authoritative. Existing cannon, acid-event
counter, and final-turn safety tests plus new fallback proofs cover the bounded
contract. The record remains `partial`: native placement, event production,
projectile endpoint helpers, scheduler/status interactions, partial-reward UI,
and missing-weapon legacy payloads stay explicit engine dependencies.

The first lethal mission-environment slice, `environment-mission-airstrike`,
pins its exact five-tile cross for marking, `DAMAGE_DEATH`, and temporary spawn
blocking plus the inherited `Env_Attack` staging callbacks. The bridge and Rust
classify the live danger as lethal without flyer immunity, with focused tests
for empty/occupied cracked Ground and stale immunity input. It remains
`partial`: Rust consumes live markers rather than reproducing quarter
selection, validity, native RNG, spawn-block lifecycle, or scheduler order,
and native `SpaceDamage` behavior is not independently traced end-to-end.

The `environment-sand-terrain-hazards` slice adds the exact Cataclysm,
Lightning, and Seismic mission sources plus four previously unnamed base
environment helpers. Simulator v382 closes two concrete projection gaps:
Cataclysm and Seismic now convert every bridge-selected non-building danger
tile to Chasm, while Lightning remains lethal to flyers without changing
terrain; resolved non-Tides danger markers no longer repeat forever in
projected or replayed boards. The record remains `partial`: Rust consumes the
current selected mask but cannot reconstruct Cataclysm Index, Seismic Path,
Lightning/Seismic location queues, native selection/order/RNG, spawn-block
lifecycle, or the next warning. Those dependencies stay explicit rather than
being replaced by deterministic guesses.

The Sandstorm slice, `environment-mission-sandstorm`, adds the exact
`mission_sandstorm.lua` source and closes a proven simulator contradiction.
The Lua environment creates/removes smoke and converts Sand, Road, and Water,
but never assigns damage; the bridge's warning markers previously entered
Rust and Python as generic 1-damage danger, costing phantom mech HP and grid.
Simulator v372 now mission-scopes those markers out of the damage path, with
focused loader and enemy-phase regressions. It remains `partial`: the bridge
does not export the live `Row`, so two-row smoke and terrain progression,
mission-start random Sand placement, native timing, and interactions are not
yet reproduced.

The Ice Storm slice, `environment-mission-ice-storm`, pins its four-center
without-replacement selection, exact 3-by-3 Frozen effect, and inherited
`Env_Attack` staging callbacks. Simulator v373 closes four source
contradictions: marked buildings and mountains now freeze, applying Frozen
clears Fire, and flying Vek receive the same freeze reward as ground Vek. The
safety audit now counts current or incoming unshielded building Ice as
protection against exactly one queued hit because the first hit only thaws it.
The record remains `partial`: Rust consumes live markers rather than
reproducing the center pool or native RNG, native scheduler and presentation
details are untraced and conflicting Shield evidence requires a controlled
native reproducer. Until then, v373 conservatively preserves the pre-existing
live-derived Shield-consumption behavior. The Acid subclass is tracked by the
separate NanoStorm record below.

The NanoStorm slice, `environment-mission-nanostorm`, adds the exact 284-byte
Advanced Edition mission source and its inherited `Env_SnowStorm` callbacks.
The source fixes the effect at one damage plus ACID, excludes buildings during
selection, and does not exempt flying pawns. Simulator v374 preserves the live
warning mask on a dedicated ACID subset, applies the damage/status to ordinary
ground and flying units, leaves ACID on empty compatible tiles, rejects stale
building markers, and round-trips the NanoStorm identity. It remains
`partial`: Rust consumes the selected mask rather than reproducing native RNG,
and combined Shield/Frozen/death plus mountain/terrain `SpaceDamage` ordering
still needs controlled native evidence.

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

The neutral mission-hazard slice, `mission-piston-trash-compactors`, adds the
previously unindexed `mission_piston.lua` source and all three active callbacks.
It pins exact randomized placement constraints, the four one-HP immobile
nonpushable neutral pawn identities, and their zero-damage one-tile forward
push construction. Simulator v386 adds a complete mission-scoped bridge
payload, strict unit/orientation corroboration, neutral/static-trait
preservation, projected JSON round-tripping, and non-overridable solve plus End
Turn gates. It remains `partial`: native `Mission_Auto` ordering relative to
Vek and environment effects, `Corpse=true` blocker/action lifecycle, setup RNG,
`Board:ClearSpace`, and `SpaceDamage` queue timing are not traced. The bridge
change is committed but intentionally not installed or exercised during the
protected live achievement session, so no push replay is claimed.

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
