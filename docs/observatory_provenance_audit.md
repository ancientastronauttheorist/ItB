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
| Enemy weapons | 14 | 6 | 8 |
| Player weapons | 14 | 14 | 0 |
| Missions | 75 | 75 | 0 |
| Environments | 15 | 15 | 0 |
| Unique total | 108 | 100 | 8 |

Mission-specific environment files belong to both the mission and environment
categories, so category totals overlap while the summary counts unique paths.

The exact callback audit finds 757 active top-level callback definition
instances, representing 756 unique `path + symbol` pairs. Current provenance
names 410 definitions literally and leaves 347 unindexed. Category totals
overlap for mission-environment files. The enemy-weapon category now includes
the 12 Advanced Edition boss files in addition to the two broad weapon files:
55 definitions total, 23 provenance-indexed and 32 explicitly unindexed. This
scope expansion was driven by the first runtime callback manifest, whose 13
initially unmatched functions all came from those boss files. With the expanded
lexical index, all 65 observed runtime functions join exactly. The remaining
unindexed definitions are a precise provenance backlog, not evidence that their
behaviors are absent from Rust.

The base Battle/Survive/Volatile slice adds three exact shipped mission paths
in three bounded `partial` records. `mission_battle.lua` is exactly two CRLF
lines and `mission_survive.lua` is zero bytes, so both are deliberately indexed
as non-evidence: neither has a class or callback and neither supports the
existing route tags or any inferred inherited lifecycle. `Mission_Volatile`
supplies five active callbacks. It spawns and marks one exact
four-HP, MoveSpeed-3, `ScorpionAtk1`, `Explodes=true` GlowingScorpion,
and fails only if that stored target dies before `TargetLeft`. Its direct
callback contains a sole-enemy retreat branch guarded by `not
self.InfiniteSpawn`, but the shipped `Mission_Volatile -> Mission_Auto ->
Mission_Infinite` class chain leaves `InfiniteSpawn=true`, making that branch
unreachable in stock play. Existing objective protection and route handling
are policy/static-model anchors, not a claim that native spawn, scheduler, or
objective settlement is reproduced. Its commented-out custom death effect
remains inactive source text.

The shared Boss-core slice adds four exact shipped mission sources in one
bounded `partial` record and names all fourteen active callbacks among them:
eleven in `Mission_Boss`, one in Firefly Leader, two in Scorpion Leader, and
none in Beetle Leader. `Mission_Boss` creates the configured leader, stores its
ID, adds the Tower asset, and makes leader death the direct objective predicate;
the Tower bonus failure takes priority in its completion-status display. The
Beetle, Firefly, and Scorpion child definitions pin their respective stats and
weapons. Firefly's direct callback queues two four-damage opposing projectiles,
while Scorpion selects only itself, queues four cardinal two-damage melee hits,
and directly adds their sound effects and hold grapples. The shipped
`Misison_FireflyBoss_Obj` typo is intentionally recorded
verbatim. Existing objective metadata, Rust weapon mappings, and the paired-shot
threat check are implementation anchors only: native placement, inherited
targeting and movement, effect scheduling, liveness timing, Tower settlement,
and full mission conformance remain open.

The remaining base Boss Leader slice adds four exact shipped mission sources in
four bounded `partial` records and names all eighteen active callbacks among
them: eight in the Blob Boss source, one in Psion Abomination, three in Hive
Leader, and six in Spider Leader. Blob Boss records its five-death stored-ID
objective, the `BlobBoss -> BlobBossMed -> BlobBossSmall` aliases, and the
separate queued four-damage/move attack versus native death-split artillery;
candidate ordering, `random_removal`, and artillery scheduling are deliberately
open. Psion Abomination pins `Jelly_Boss` and `LEADER_BOSS`, but its inherited
tooltip/aura machinery is not attributed to the small mission source. Hive
Leader makes ordinary Vek spawn before requesting two `SlugEgg1` through
`FlyingSpawns`; because the helper is native, its placement, RNG, and whether
its effects are direct or queued remain gaps. Spider Leader directly requests
two initial eggs, alternates later 2/3 egg requests outside Easy, and its hatch
constructs an ordered `AddScript(RemovePawn)` plus non-queued `AddDamage` spawn
of exact `Spiderling1`. Existing static data, mappings, and tests are anchors,
not a claim that any native placement, helper, script scheduler, or mission
settlement is fully reproduced.

The mountain, sinkhole, trapped-building, forest-fire, and shield-generator
slice adds six exact shipped mission sources in five bounded `partial` records.
`Mission_Force` supplies all eight callbacks: it starts by damaging up to three
Mountains, counts native `EVENT_MOUNTAIN_DESTROYED`, demands two destructions,
and combines that objective with forced Kill Five only for its completion-status
presentation. Existing bridge/Rust/safety counter plumbing is attached without
claiming native setup RNG, event timing, or compound mission-end conformance.
`Mission_Holes` supplies its two callbacks: it queues `GetSpawnCount` Hornets
and blocks an early end. Its Mite behavior is explicitly an inherited
`BONUS_SELFDAMAGE`/native dependency; existing infected-mech safety is not
misreported as being defined by this file. Mission routing now applies the
conservative `mite_counter` veto only when that exact bonus is present, while
retaining the veto when the bonus slate is unavailable or malformed.

Both shipped `Mission_Trapped` definitions are indexed. The Advanced Edition
definition is the effective listed source and adds `NonGrid` plus `SpawnMod=2`;
the older base file remains shipped evidence, not a claim that its setup runs in
the Advanced Edition load. Rust already maps the smoke-immune two-HP decoy and
its self-plus-cardinal-non-building `DAMAGE_DEATH` blast, while placement RNG,
native eligibility, and queued-effect edge cases remain partial. The Forest
Fire source now pins its sixteen-road setup cap, x-then-y fire scan, and 0/1/2
reputation tiers. Shared fire simulation and conservative route avoidance are
not an authoritative native Forest Fire counter.

The Shield Generator source now pins one-time `SetShield(true)` for each newly
seen pawn, starting-building shields, non-Zoltan/all-building removal after
generator death, and the generator-death objective. The generator is now also
mapped as a required destroy-objective unit, so final-turn safety blocks plans
that leave it alive. Current Rust's v280/v283
non-consuming and implicit-protection behavior is deliberately recorded as a
legacy live-derived inference, not source proof: its original Ricochet path was
later diagnosed as a native no-op and the observed Scorpion already had a
shield. Controlled direct-hit, push, and generator-death traces are required
before reconciling that inference with the exact Lua semantics.

The Acid-base native-phase slice adds four exact shipped mission sources in four
bounded `partial` records and names all fourteen active mission callbacks among
them, plus the two inherited `Laser_Base` construction callbacks.
Mission_Acid captures its ACID-water SpawnTable and its normal-then-one-ACIDed
Vek spawn ordering, but generic ACID bridge/Rust import and plan safety are not
misreported as a source-specific spawn forecast. Mission_Fence can place up to
five randomly selected directional native edge-wall segments. Mission_Laser
creates a neutral directional Corpse whose queued damage-five-to-one beam passes
pawns and stops at a building, mountain, or edge; that traversal is pinned to
the exact `weapons_base.lua` helpers rather than attributed only to the mission
file. Mission_Respawn records enemy
types and last spaces, then recreates dead non-Minor Vek at enemy-turn entry
with a new native identity and fallback enemy-zone placement. The latter three
are all exact-ID, fail-closed policies: default routing assigns a hard veto,
Lightning auto-start preserves it even for forced previews, and solve plus every
public End Turn route stop before planning or delivery because their native
wall, queued-beam, and resurrection phases are not simulated. The gates are safety evidence only,
not a claim of conformance to their native setup, RNG, geometry, effect queue,
or scheduling.

The Archive grass slice adds three exact shipped mission sources in three
bounded `partial` records and names all ten active callbacks among them.
Artillery Support creates and protects its stored two-HP ArchiveArtillery; its
source-defined two-hit artillery shot is already modeled, and objective metadata
now protects the live actor. The Python fallback now also pins its one-tile move
and default weapon, while native placement, LineArtillery legality, and effect
timing remain open.
Old Earth Mines is a zero-callback `Mission_MineBase` constructor: its
`Item_Mine`, spawn modifiers, selected bonus pool, and blocked Vek types are
catalogued without treating shared import/simulation as native placement
conformance. Defend the Tanks starts two disabled neutral Archive_Tanks, then
powers and de-neutralizes each survivor at player turn three, with a 2/1/0
survivor objective. Existing live-state objective protection and the separately
indexed cannon are linked, but native defended-zone selection and activation
scheduling are unforecast; its Python fallback now pins source MoveSpeed=4 and
default cannon, while full source-to-bridge actor conformance remains open.

The sand Filler/Wind slice adds two exact shipped mission paths in two bounded
`partial` records and names the five active Filler callbacks, while also
completing the two omitted active callbacks in the existing Advanced Edition
Wind record. Mission_Filler
creates a protected Filler_Pawn at a native filler-zone point, clears its
starting crack, and turns it into Road; its self-targeted two-column north/south
terrain wave is catalogued but remains native-only because no Rust action model
reconstructs its hole stop, terrain writes, or queued presentation. The legacy
base `mission_wind.lua` is exactly two CRLF bytes with no declarations or
callbacks. It is indexed specifically to prevent attributing the existing
Advanced Edition wind model to an empty source; the authoritative behavior
evidence remains the separate `environment-mission-wind` record. The Filler
live-web safety block is explicitly a discrepancy policy beyond Filler's source
alive-only objective predicate.

The existing Advanced Edition Wind record now also names every active callback,
including `Start` and `IsEffect`, and separates two safety layers from source
simulation: a combat-player-only payload integrity gate requires authoritative
environment identity, source-reachable raw direction 0 (UP) or 2 (DOWN), two
matching complete lane columns selected from 1 through 5, and exact current
v2 `[x, y, 1, 0, 0]` warning entries before solve or End Turn; routing no longer
assigns this mission a stale critical-building tag. Both are fail-closed policy
evidence, not a reconstruction of wind RNG or native environment scheduling.

The Pinnacle mission slice adds five exact shipped sources in five bounded
`partial` records and names all sixteen active callbacks among them. Boom Bots
creates two live plus two frozen random Boom-bot variants, records their IDs,
and has a 0/1/2-reputation death counter; shared Rust explosive-decay coverage
is linked without claiming the native roster, placement, or objective timing.
Factory sources establish alternating intact-critical selection, a disabled
launched robot, and enemy-turn re-powering. Existing critical-building bridge
extraction and live attack-order preservation are attached, while native launch
and power scheduling remain open. Freeze Bots adds two random robots plus a
Freeze Tank and counts only living frozen stored IDs. Objective metadata now
matches all three source-selectable Snowtank, Snowlaser, and Snowart families;
final-turn safety blocks either thaw or loss, while native selection and counter
timing remain open. Freeze Mines is a zero-callback constructor: it only
sets `MineType = "Freeze_Mine"` on inherited `Mission_MineBase`; modeled mine
behavior does not prove native placement or RNG. Finally, Stasis creates two
random frozen, mission-critical bots on eligible inner-board ground points, but
defines no objective or reward semantics. Its attached regression only proves
that Stasis does not receive the separate Reactivation thaw rule.

The Acid Storm lifecycle slice adds the exact
`scripts/advanced/missions/acid/mission_acidstorm.lua` source and all six of
its active callbacks. Setup replaces one native-selected building with the
neutral enemy-team Storm Generator, starts full-board ACID rain, and ACIDs
every remaining building. While the generator lives, `UpdateMission` reapplies
ACID to every living pawn; after it dies, the callback stops the weather but
does not clear existing ACID. Simulator v391 now applies that refresh at
completed player-action and enemy-phase checkpoints, including fresh player
allies, enemy eggs/blobs/totems, and split children in solver and replay state.
Native setup selection, exact `Mission:BaseUpdate` scheduling between queued
micro-effects, weather presentation, and exhaustive status/terrain edges
remain explicit partial-coverage gaps.

The Disposal launcher slice adds the exact
`scripts/missions/acid/mission_disposal.lua` source, all seven of its active
callbacks, and the inherited `Grenade_Base:GetTargetArea` callback. Lua gives
the two-HP, immobile, nonpushable, smoke-immune player launcher every board
coordinate as a legal target, including its own tile. Its custom artillery
effect queues a lethal ACID cross and converts affected Mountains to Road.
Simulator v394 closes the prior self-target mismatch, exercises the resulting
launcher self-destruction, and reports that non-mech loss through protected-NPC
scoring instead of mech-casualty metrics. The record remains `partial`:
`Mission_Disposal:IsEndBlocked`'s compound launcher-alive plus
mountains-remaining gate is not modeled, native setup and effect ordering are
untraced, and no controlled self-fire UI capture was taken during the protected
achievement session.

The Terraformer sweep slice adds the exact
`scripts/missions/sand/mission_terraform.lua` source and all eight of its active
callbacks while reusing the already-indexed inherited `Skill:GetTargetArea`.
Lua checks only still-custom `ground_grass.png` points inside
`Board:GetZone("grass")`, not every matching map sprite, and its two-row by
three-wide attack clears that custom marker unconditionally even when Mountain
terrain is retained. The exact inventoried maps prove decorative off-zone grass
on maps 2 and 3 and objective Mountain grass on map 2. Simulator v395 clears
Mountain objective grass, while the dormant bridge exports the exact live
zone-filtered remainder and distinguishes an authoritative empty result. The
record remains `partial`: the bridge is intentionally uninstalled during the
protected session, so the old fresh-turn save fallback still conservatively
overcounts decorative markers; native mission-end/UI scheduling and exhaustive
`DAMAGE_DEATH`/custom-script ordering also remain open.

The Repair Platform slice adds the exact
`scripts/advanced/missions/grass/mission_repair.lua`, inherited
`scripts/missions/mission_minebase.lua`, and `scripts/items.lua` sources plus
all six mission callbacks. The sources prove eight inner-board repair-item
placements, deployment-time mech HP reduction, pickup-minus-undo objective
arithmetic, and completion at three uses. Existing bridge, Rust landing,
objective scoring, deployment reservation, and bounded settlement behavior are
connected to focused live-derived regressions without overclaiming the native
event producer: player-mech-only credit, enemy consumption/healing, undo
timing, and exhaustive `SpaceDamage(-10)` interactions remain explicit gaps.

The Detritus Contraption slice adds exact
`scripts/advanced/missions/acid/mission_missiles.lua` evidence plus the
inherited `Support_Missiles` and `Skill:GetTargetZone` callbacks. Lua awards
zero, one, or two reputation at 0–1, 2–3, or 4 shots, respectively, and its
commented-out death branch proves that losing the Contraption does not itself
fail the objective. Both Limited=2 barrages use friendly-fire all-pawn
targeting, exclude the source, and queue impacts in x-then-y order. Existing
Rust global-effect ordering, Shield no-op objective use, secondary-only actor
eligibility, turn-boundary slot depletion, delayed-effect settlement, and
decorative-conveyor regression provide the implementation anchors. Direct
mid-turn `ShotsUsed`, native pawn-space edges, artillery scheduling, setup, and
ZONE_ALL presentation remain partial-coverage gaps.

The Renfield Bomb slice adds the exact
`scripts/missions/sand/mission_bomb.lua` source and its four mission callbacks,
plus the inherited `Mission:AddDefended` helper. Lua creates two one-HP,
zero-move, fire-immune `ProtoBomb` pawns and awards full, partial, or failed
reputation for two, one, or zero survivors. Simulator v396 now prevents direct
ignition and clears stale Fire without tick damage; Python static metadata and
the threat audit preserve the same immunity. The solver intentionally protects
both bombs instead of accepting the source's partial reward. Native
`Corpse=false`/`Explodes=true` death behavior, placement RNG, explosion order,
objective scheduling, and Mission_Infinite spawns remain explicit gaps.

The Nano Silos VIP slice adds the exact
`scripts/advanced/missions/acid/mission_civilians.lua` source and its eight
active callback definition instances; its first empty `NextTurn` definition is
immediately overwritten. Lua creates two one-HP `VIP_Truck` pawns with
`MoveSpeed=0`, `IgnoreSmoke=true`, and a Limited=2 range-three path-move skill.
Simulator v396 now enumerates and executes that skill through Smoke. A narrow
turn-boundary save overlay blanks the exact primary slot at zero uses only when
the player actors are fresh, save and bridge turns plus mission, UID, type,
slot, and weapon identity all match, preventing a stale mid-turn third
move while stale or malformed evidence fails open. Native path helpers,
AddMove scheduling, setup RNG, objective/voice presentation, and inherited
spawn behavior remain partial-coverage gaps.

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

The Hornet slice adds the exact `scripts/missions/bosses/hornet.lua` source while
reusing already-indexed base enemy, pawn, and global target-area sources. The
ordinary Hornet queues one adjacent damage; Alpha Hornet inherits a two-damage
attack and adds the same damage one tile farther in the selected direction;
Hornet Leader queues two damage on three consecutive tiles. Its inherited
native target area uses simple reachability with unlimited path size and no
corner allowance. Rust/Python preserve raw `piQueuedShot`/`piOrigin` alongside
the normalized target, so a pushed Hornet retains its source direction or full
leader offset and the threat audit rechecks every line tile. The record names
both previously unindexed Hornet effect callbacks and keeps native boss
targeting/scoring, obstacles, exact scheduler order, and every Hornet Acid
behavior as explicit partial-coverage gaps.

The Cluster Artillery slice reuses already-indexed `weapons_ranged.lua`,
`weapons_base.lua`, and `pawns.lua` source files, so source totals do not
change. Its four exact effective IDs retain a harmless selected center, a
one- or two-damage cardinal outer ring, and the Buildings Immune direct-damage
exception on A/AB while preserving physical collision damage. The record adds
the previously unindexed inherited `ArtilleryDefault:GetSkillEffect` callback.
Native target selection, effect scheduling, and exhaustive collision/status
interactions remain partial-coverage gaps.

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
`Science_TC_Control` variants. v390 follows the source's ordered adjacent
first-click predicate: pawn space, guarding unless Burrower, powered, not
Frozen, then Snowmine1/VIP_Truck or current move-or-explicit-grappled plus
base move. It deliberately has no team or projectile-blocker condition, and
uses the separate fixed 2/3/3/4 controlled-movement budgets. The bridge now
captures the native predicate values and validates both native target lists
before `GetFinalEffect`. Exact Windows static evidence now pins native unit
costs, direction and tie comparators, output/reconstruction order, ordinary
identity-based occupancy, Road Runner, Massive Water, and mode-1 live-or-
persistent-corpse occupancy. Simulator v403 preserves the corpse distinction
through bridge/model/checkpoints. The record remains `partial`: extra-tile
identity, runtime `IsCorpse()` subclass/removal timing, no-op destinations,
native `AddMove` sequencing, visible UI, and achievement credit still need
controlled evidence.

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
record remains `partial`: exact Windows static evidence now pins basic native
path costs, directions, tie comparators, result/reconstruction order, ordinary
identity-based occupancy, Road Runner, Massive Water, and persistent-corpse
mode-1 occupancy. `AvoidingMines`, matched Mine-Bot path vectors, runtime corpse
subclass/removal timing, movement/item scheduling, setup placement, and enemy
AI/RNG remain outside the proven contract.

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
terrain/status/scheduler behavior remains open. The exact Leader source is now
inside the expanded 108-file high-value set and indexed by this record; it adds
no active top-level callback definition of its own.

The fifth family-level enemy-weapon slice, `enemy-weapon-centipede`, pins the
normal, Alpha, and Leader pawn/weapon IDs, damage values, unlimited projectile
range, ACID impact T, direct-enemy candidate rejection, and the Leader's strict
pre-impact ACID trail. Exact mappings plus normal/Alpha/Leader damage and ACID
footprints, ground/water conversion, board-edge impact, Python definitions,
known types, and static pawn metadata have focused tests. The record remains
`partial`: current-turn resolution consumes the bridge-selected target, mobile
projection is generic, and native movement, candidate enumeration,
`GetProjectileEnd`, `ScoreList`, effect scheduling, selection, and tie-breaking
remain untraced. The pawn file remains outside the callback audit's selected
source set, while the Leader file is now inside the expanded Advanced boss
enemy-weapon scope and its runtime callbacks join by exact source line.

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
source `Index`. Conditional on the existing warning-mask bridge contract,
simulator v392 also performs source-consistent recovery of that current Index
from a legacy visible warning only when every marker lies on one source-valid
row, allowing a later fully hidden lane to advance again at deeper projection;
empty, row-zero, and multi-row legacy masks remain fail-closed. This is not an
end-to-end proof that native `Board:IsEnvironmentDanger` exactly equals Lua's
marker mask. The record remains `partial`: the dormant bridge export has not
been installed during the protected live session, native blocked-cell and
scheduler helpers are untraced, and flyer/timing evidence remains live-derived.

The inherited `environment-mission-terratide` slice pins its exact Advanced
Edition source plus the base Tides implementation. It covers full-row smoke,
pre-attack cancellation, reverse warning advancement, and the fact that a
prior-row building does not shadow the next warning. Simulator v393 extends
the dormant inherited `Index` and `Planned` exports to Terratide. Only explicit
`Planned=true` authorizes reconstruction of a complete markerless
`y=7-Index` smoke lane and reverse-mapped advancement across projection/replay
depth; `Planned=false` suppresses both, because Lua leaves Index intact after
`ApplyEffect`. The projection does not invent Tides' water-only permanent
spawn blocks. One source-valid legacy warning row can recover the same scalar;
empty, row-seven, and multi-row masks retain the prior fail-closed shift. It
remains `partial` because those bridge exports have not been installed or
live-captured, native scheduling and smoke interactions are not exhaustive,
and initial y=7 smoke is consumed from live state rather than independently
generated.

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

The third mission-environment slice, `environment-final-cave-danger`, now pins
both Final Cave `env_final.lua` and inherited `Env_Attack` scheduling to a
bounded v405 current-selection model. The bridge atomically exports Mode,
Phase, Ordered, Instant, WaterTarget, the otherwise-unused LavaPath, and exact
matching Locations/Planned; Python and Rust reject source-unreachable state,
turn disagreement, warning-mask drift, or nonlethal/flying-immune encodings
before solve or End Turn. Rust resolves the selected list before queued Vek
attacks: both Rocks and tentacles use `DAMAGE_DEATH` against grounded, flying,
Massive, Shielded, and Frozen pawns, then assign Road or Lava respectively.
Projection consumes the current payload without inventing the next selector.

Two git-preserved Final Cave runs corroborate phase-one Rocks, phase-two
Mech-position tentacles, Mountain-to-Road and Ground-to-Lava aftermath, one
complete six-tile Instant Rocks conversion, and one complete cardinal crossing
row. Their immutable ledger is
`data/observatory/captures/historical_git_mission_final_cave_runs.json`; it also
records where the old non-atomic bridge sampled ambiguous Instant boundaries.
The record remains `partial`: future quarter/cluster/crossing selection RNG,
unused `GetCrossPath` call order, BigBomb exclusion, native scheduler tracing,
and `Board:SetDangerous` enemy planning are not reproduced. Bomb replacement
and the surface/cave lifecycle remain in their separate record. The preceding
`env_volcano.lua` stage retains the bounded v404 model described below.

The two-stage Final mission slice, `mission-final-surface-and-cave-lifecycle`,
indexes all fifteen callback definitions in `mission_final.lua` and
`mission_final_two.lua`, plus the cave source's local `SpawnMechs` helper. The
surface source adds a random leader only on Hard
or Unfair, builds lethal occupied pylons on enemy turn zero, restores the fixed
four-space supervolcano, blocks ordinary ending, and queues the falling-board
handoff to `Mission_Final_Cave`. The cave source reserves a random deployment
point for BigBomb, may first spawn a normal pawn there, drops the mountain and
pylon setup, relocates all three Mechs, spawns a random leader, and delegates
ordinary spawning. Its `IsFinalTurn` returns false, and each nonbusy missing-
bomb update chooses another valid point, drops BigBomb, and extends `TurnLimit`
by two. BigBomb's exact four-HP, neutral, no-corpse, fire-ignoring, immobile
TEAM_PLAYER definition is pinned, but the source does not state that its loss
is terminal. Current liveness/pylon safety and volcano-to-caverns fingerprint
tests are conservative live-state and policy anchors, not reproduction of
native RNG, effects, collisions, scheduling, phase handoff, or mission-end
settlement.

The final Volcano-environment slice, `environment-final-volcano-cycle`, closed
the then-selected mechanical source index at 96/96. The later runtime-driven
Advanced boss expansion raised the current scope to 108 files, of which 100 are
provenance-indexed; the eight newly visible unindexed boss files remain explicit
backlog. Its selector toggles before choosing, yielding exactly Lava, Rocks,
Lava, Rocks over phases one through four. Lava consumes one of two starting
points and extends up to three right/down non-Lava, non-Mountain, non-Building
steps; Rocks chooses at most one non-sentinel point from each inherited quarter.
The effects are respectively Lava terrain conversion and lethal fire-setting
artillery, while `Ordered=true` consumes selected locations from the front.

Simulator v404 upgrades the bounded current-turn behavior without pretending to
predict native RNG. The bridge exports `Mode`, `Phase`, remaining `LavaStart`,
and the exact ordered `Locations`/`Planned` selection atomically. Python and
Rust reject source-unreachable state, turn disagreement, warning masks, and
mode-specific encodings before solve or End Turn. Rust then applies Rocks before
queued Vek attacks or permanently converts Lava, including drowning and Fire
status rules, and clears the resolved payload rather than inventing the next
selection. Two git-preserved live runs corroborate Lava/Rocks/Lava/Rocks,
terrain conversion, Rocks Fire, and one pre-attack Rock kill; their immutable
ledger is
`data/observatory/captures/historical_git_mission_final_volcano_runs.json`.
Because those historical recordings lack a build identity and future selector
RNG plus exact scheduler edges remain native dependencies, provenance stays
`partial`. `Mission_Final` is no longer broadly picker-vetoed, but its dedicated
payload gate remains non-overridable whenever current evidence is incomplete.

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

The tutorial/trailer slice adds the three exact shipped `Mission_Tutorial`
sources and their 17 defined callable callbacks: four each from the base and
Advanced Edition trailer definitions, and nine from the standard tutorial.
The exact `GetScripts` loader actively imports the standard tutorial, comments
out the Advanced Edition trailer entry, and omits the base trailer entry; the
two trailer definitions are therefore dormant/unrouted by the shipped list,
not competing active mission definitions. `CreateTutorial` constructs the
standard `Mission_Tutorial`. Its fixed Vek and mech sequence still runs through
native pawn construction, spawn queuing, tips, selection/arming/undo checks,
and `BlockNextTurn` state machines. The bridge normalizes the separately
constructed source name to exact `Mission_Tutorial`; a non-overridable gate
then blocks solver/auto-turn/public-End-Turn/Lightning-route forecasting of
that native lifecycle. The static metadata entry and gate do not imply trailer
effect, tutorial UI, spawn/UID allocation, objective settlement, or campaign
lifecycle conformance.

The SnowBattle/helper slice adds the exact `Mission_SnowBattle` constructor and
its sole `StartMission` callback, plus the shared `Freeze_Tank` helper source.
Lua requests two normally added `NextRobot` pawns that it does not explicitly
freeze and one additional explicitly frozen `NextRobot` pawn during setup;
all candidate selection, placement, IDs, and
inherited lifecycle stay native. The live bridge therefore consumes the
already-created board rather than forecasting setup, and the record introduces
neither fake dynamic `forced_pawns` metadata nor a mission gate. The shared
helper now anchors the existing one-HP, move-four, player-team, no-corpse
Corporate tank and its zero-damage, no-push freeze projectile mapping
in Python and Rust, while retaining targeting/timing as native behavior.

The last two player-source files are now exact-indexed without assigning false
runtime weight. `weapons_experiment.lua` is comment-only and defines nothing.
`weapons_structure.lua` contains an airfield pawn, an all-board one-damage plus
four-push `Structure_Force`, and a TEAM_PLAYER-wide healing
`Structure_Repair`, but the shipped `GetScripts` list omits both files and no
other installed script references their paths or identifiers. They are
dormant/unrouted legacy evidence, not active weapon implementation claims; in
particular, `Structure_Repair` is not the loaded `Support_Repair`.

The active Support Force slice instead follows the exact loaded
`weapons_support.lua` definition through inherited `Grenade_Base` all-board
targeting and its direct one-damage center plus four outward zero-damage pushes.
`drops.lua` puts `Support_Force` in both the normal weapon and pod decks, making
it stock drop-reachable. Simulator v399 adds the exact ID/static definition,
all 64 source-legal targets with true-no-op action pruning, and the center plus
outward-push effect, including building/grid bump accounting. Native
presentation, exhaustive effect ordering, drop RNG, and the base weapon's
cross-turn `Limited=1` state remain partial gaps.

## Highest-value expansion order

1. Continue splitting player weapons into family-level records, using the Titan
   Fist slice as the minimum evidence pattern.
2. Add mission records only when a static callback, Rust transition, and
   regression fixture can be named precisely; do not bulk-index files merely to
   improve the count.
3. Keep the indexed `env_volcano.lua` record partial until future selector RNG,
   build-keyed runtime edge capture, and full scheduler conformance exist; the
   exact current phase, mode, selected order, terrain, and Fire contract is v404.
4. Keep native-dependent target selection and RNG records non-verified until a
   build-keyed trace supplies the missing boundary evidence.

The audit should trend toward fewer unindexed files, but the governing metric is
trustworthy file-to-implementation evidence, not 100% indexing by itself.
