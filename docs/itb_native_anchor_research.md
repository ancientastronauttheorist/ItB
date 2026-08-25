# Windows PE native-boundary research

## Status and evidence boundary

The targeted **offline** boundary pass is complete for the Observatory hook
plan on the pinned Windows executable. The work promotes the earlier named
string candidates into reviewed function boundaries for:

- all four `random_int` / `random_bool` overloads and their Luabind
  registration route;
- the shared native RNG and seed setter;
- `aiSeed` load, use, advance, and store;
- enemy target enumeration, `ScorePositioning`, `GetTargetScore`, and native
  equal-best tie-breaking;
- `GetTargetArea` / `GetSecondTargetArea` and `GetSkillEffect` dispatch;
- the final selected 24-byte AI decision-record copy; and
- the native path/reachability API, path profiles, Board search vtable, and
  Road Runner transit/destination boundary, followed by exact path costs,
  direction/priority ordering, reconstruction, ordinary occupancy,
  Massive-Water handling, and dead-versus-persistent-corpse occupancy.

“Complete” here means the focused static map needed to choose experiment
boundaries is finished. It does not mean the native engine is reconstructed.
The RNG-core transaction has since been exercised twice with build guards,
bounded records, and exact byte restoration, and all four Lua-exposed callback
families have natural runtime evidence. Three later `Spawner:NextPawn` spans
resolve the normal weak/pawn/upgrade draw order, and three counterbalanced
hardware-observer triplets correlate the final selected record to the immediate
Pawn action queue for a bounded Firefly scenario. Three spawn-replay captures
also recover the exact observable pre-call state class and reproduce the
captured pawn choices from their effective ratios and ordered candidates.
A separate one-shot hardware observer now closes the callback-time x87 seam:
three counterbalanced fresh-process triplets each hit the exact
`ScorePositioning -> lua_tointeger` frame chain immediately before `FISTP` and
record control word `0x027F` (nearest-even). All control/dormant/armed outcomes
match, and every debug register, VEH, file handle, and image seam is restored.
A later coordinate hardware observer resolves the standard selector's ordered
candidates, direct shared-RNG caller, and modulo rule. Three same-process
coordinate/RNG captures show that the selector ordinal is not stable under a
restored save plus fixed seed because particle, pilot-portrait, `UnitAcid`,
environment-XP, and Lua draws share the upstream stream. Whole-game native-RNG
observer neutrality, prospective selector-state delivery or complete upstream
replay, runtime inputs for the special coordinate paths, and broader
selected-action paths remain unresolved. One complete Firefly1 runtime
candidate payload plus selector-entry state is now sealed, but ordinary
prospective delivery and equivalent payloads for other shapes remain
unresolved. Native score adjustment around that payload is no longer
anonymous: a later exact-build continuation names the
injured/health/weapon/history/priority fields and closes the positioning clamp
and target-score modifier arithmetic. The post-callback record tournament is
also no longer an offline unknown: another exact-build continuation closes its
24-byte layout, comparator, displaced-primary fallback, and local draw grammar.
The native target-area callback wrapper is now closed as a parameterized
boundary too: `Skill +0x110` is joined to `Board +0x0c` and `Board:IsValid`,
invalid origins clear the cache, `TwoClick` selects the callback, and only
negative returned coordinates are filtered. Concrete Lua-produced points
remain explicit inputs.
Three later matched callback campaigns close those concrete inputs for the one
fixed Firefly1 shape: nine ordered target-area calls, 32 raw target-score
returns, and 33 raw SkillEffects. The first 32 effects match the score arguments;
the final effect repeats native selected input 5 and its `[3,4]` impact appears
in the same process's settled queue. A later three-triplet hardware campaign
also captures the selected native postprocessed `FireflyAtk1` at RVA
`0x00268323`, binding owner/source ancestry, origin/target, animation, damage,
and impact to the selected record and settled attack in one process. These
bounded results do not generalize other subclasses, materialization routes, or
prospective Board state.
The scheduler/fallback *control flow* is no longer unknown: exact
offline review identifies caller 59 as the logged emergency modulo selector
and caller 66 as without-replacement predicate ordering before a separate
ordinary selector call. A disposable installation is optional for those
owner-build questions and required only for a pristine stock-depot claim.
The three exact-build path maps close Henry Kwan's Road Runner occupancy rule,
weighted cost/priority ordering, ordinary team-agnostic pawn blocking, and
Massive Water traversal, then prove mode-1 occupancy as live-or-persistent-
corpse. A later exact-build map closes the one common `IsCorpse` predicate,
its mutation-12 fallback, and all 16 effective shipped corpse definitions.
Transient lifecycle/removal timing, point vectors, and `AddMove` step/scheduler
effects remain mismatch-driven.

The durable artifacts are:

- `data/observatory/native/windows_build_13725832_31fe35265598_pe_anchors.json`
  for exact strings, conservative initial references, imports, and PE identity;
- `data/observatory/native/windows_build_13725832_31fe35265598_pe_boundaries.json`
  for reviewed region hashes, mechanically decoded calls, classified findings,
  hook scope, and remaining runtime questions;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json`
  for the ordered destination-to-record pipeline, exact six-integer record
  layout, target-tie draw, record comparator, displaced-primary fallback,
  caller IDs 29 through 33, and pure selector replay from an observable
  selector-entry CRT state;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json`
  for the exact `bInjured`, health, selected-weapon, `targetHistory`, and
  `priorityTarget` field bindings; ordinary/debug route modes; positioning
  clamp; target-score modifiers and floor; and pure callback-boundary replay;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_target_area_boundary.json`
  for the complete ordinary pre-`GetTargetArea` gate, named smoke/Water
  predicates, usable-skill scan, `iBonusShift`/`IsMech` fields, literal-50
  `Skill_Repair` resolver, exact active `SkillList` census, and pure gate replay;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_target_area_callback_boundary.json`
  for the joined Board context/validity guard, `TwoClick` dispatch, invalid-
  origin cache clear, stable negative-coordinate filter, complete direct-caller
  inventories, and pure replay from an already-materialized callback PointList;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_skill_effect_boundary.json`
  for the selected-target membership gate, exact regular/final callback
  dispatch and argument order, cache clear/replace behavior, both record-vector
  annotation passes, Vek Hormones/Boost arithmetic, and pure projected replay
  from an already-materialized Lua SkillEffect;
- `data/observatory/captures/windows_build_13725832_owner_local_modified_20260824_enemy_materialized_effect_hw_receipt.json`
  for three counterbalanced runtime observations of the fixed selected
  Firefly1 postprocessed SkillEffect, same-process selected-record/effect/queue
  binding, matched semantic outcomes, and complete one-shot restoration; the
  matching cleanup receipt binds the rejected diagnostics and exact restore;
- `data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_effect_ancestry.json`
  for all 20 active shipped `GetTargetScore` bodies, their direct/nested/
  synthetic/no-effect routes, Shaman-to-Totem inheritance, and the zero direct
  Lua RNG-call census across all 186 active `GetSkillEffect` definitions;
- `data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_list_semantics.json`
  for the exact shipped base `GetTargetScore`, `isEnemy`, and `ScoreList`
  bodies, strict branch-order replay, instant/queued selection, and explicit
  projected Board/Pawn and `ScorePositioning` inputs;
- `data/observatory/callbacks/windows_build_13725832_31fe35265598_enemy_score_positioning_semantics.json`
  for every shipped global `ScorePositioning` branch, exact half-point melee
  arithmetic, the native named-integer join, and conversion replay under an
  explicit callback-time x87 rounding mode;
- `data/observatory/captures/windows_build_13725832_owner_local_modified_20260824_score_positioning_x87_receipt.json`
  for three exact-build runtime observations of x87 control word `0x027F`, six
  matched whole-game neutrality comparisons, complete one-shot observer
  restoration, and the resulting nearest-even conformance rule;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_position_score_helpers_boundary.json`
  for the exact `GetDangerScore`/`GetCustomPositionScore` registrations and
  call bodies, their generated Lua getters, and the unmodified shipped
  `ScoreDanger=-10` / `PositionScore=0` defaults;
- `data/observatory/native/windows_build_13725832_31fe35265598_enemy_position_observations_boundary.json`
  for all 17 named Board/Pawn observations used by `ScorePositioning`, their
  exact native meanings, pure predicate/distance replays, and the qualified
  current-state carrier matrix;
- `data/observatory/native/windows_build_13725832_31fe35265598_rng_return_ids.json`
  for deterministic small IDs covering all 118 raw `rel32` candidates to the
  shared RNG core. Eleven are matched to reviewed call edges; the other 107
  remain explicitly unclassified until runtime evidence or further review.
- `data/observatory/native/windows_build_13725832_31fe35265598_rng_caller_roles.json`
  for a separate, return-map-preserving semantic overlay on the 13 callers
  needed to explain coordinate-ordinal drift. Five reviewed function extents,
  14 literal anchors, and one direct call edge bind the presentation/gameplay
  roles without changing the checkpointed return-map digest.
- `data/observatory/native/windows_build_13725832_31fe35265598_spawn_coordinate_paths.json`
  for the exact scheduler/fallback/ordinary control-flow map. It binds callers
  59, 60, and 66, both function hashes, all seven direct callsites, three log
  or class strings, and six branch/vector/modulo windows.
- `data/observatory/native/windows_build_13725832_31fe35265598_path_boundaries.json`
  for the exact path API bindings and constants, Board search vtable, 12
  reviewed region hashes, four direct call edges, and the Road Runner
  transit-versus-stop proof.
- `data/observatory/native/windows_build_13725832_31fe35265598_path_cost_ordering.json`
  for 26 reviewed code/table regions, 14 control windows, the exact direction
  and priority comparators, reachable output order, GetPath reconstruction,
  ordinary identity-based occupancy, and Massive-Water proof.
- `data/observatory/native/windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json`
  for eight reviewed regions, ten control windows, the `Pawn:IsDead` and
  `Pawn:IsCorpse` bindings, mode-1 counted occupancy, the concrete Board path-
  manager vtable, and ordinary/Road Runner corpse transit-versus-stop proof.
- `data/observatory/native/windows_build_13725832_31fe35265598_corpse_classification_boundary.json`
  for the complete common `Pawn:IsCorpse` body, exact loader/mutation fields,
  the registered `LEADER_NECRO=12` fallback, complete direct-call inventories,
  and the accepted shipped tree's ten explicit plus six inherited corpse
  types.
- `data/observatory/native/windows_build_13725832_31fe35265598_final_end_settlement.json`
  for the Final turn-limit/state-2 end-readiness short circuit, native
  `Board:AddEffect` enqueue path, Board/BoardPlayer activity vtables, and the
  activity-clear completion handoff.
- `data/observatory/native/windows_build_13725832_31fe35265598_final_campaign_settlement.json`
  for the cave `StartMechTravel` queue, completed-campaign predicate, ordinary
  cleanup exclusion, run-save teardown, profile result/write path, and
  final-victory renderer handoff.

The boundary artifact contains no executable bytes or decompiled source. The
verifier rechecks its 32 region hashes and decodes its 35 high-value direct
calls at instruction boundaries relative to the reviewed region starts:

```powershell
python scripts/itb_pe_boundary_map.py `
  --executable "<Into the Breach>\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_local_modified.json `
  --evidence data/observatory/native/windows_build_13725832_31fe35265598_pe_boundaries.json
```

Region starts and extents are analyst-reviewed inputs from Ghidra plus focused
Capstone analysis. The verifier does not independently discover function
entries or prove reachability; it proves exact bytes and decoding consistency
conditional on those reviewed starts.

## Exact identity

| Field | Value |
|---|---|
| Platform / format / architecture | Windows / PE32 / x86 |
| Steam build | `13725832` |
| Windows depot / manifest | `590381` / `8335438558621014449` |
| Executable SHA-256 | `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9` |
| Image base | `0x00400000` |
| Scripts revision | `591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155` |
| Maps revision | `a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4` |

The local scripts revision remains modified by the installed bridge and backup
files. That does not change `Breach.exe`, but the content identity remains part
of every experiment key. The PE CodeView record is an `RSDS` fact with GUID
`a842b21e-6b7c-43b5-ac68-b0231cef7684`, age 1, and Windows-only build path
`D:\bigbrother\Kaiju\bin\Breach.pdb`.

## RNG registration and exact leaf behavior

The earlier `random_int` and `random_bool` candidates are real Luabind function
registration descriptors. The registration builder constructs both overloads
of each name. Its signature-specific path eventually creates a Lua C closure
through imported `lua_pushcclosure`; the name-binding path writes through
`lua_settable`.

This corrects the former `lua_setfield` hypothesis. The executable imports
`lua_setfield`, but its direct call sites belong to generic library setup, not
the reviewed random-function registration route.

| Lua-visible overload | Native RVA | Reviewed behavior |
|---|---:|---|
| `random_int(max)` | `0x000e0c20` | `max == 0` returns zero without consuming RNG; otherwise signed `rand % max` |
| `random_int(lo, hi)` | `0x000e0c40` | equal bounds return `lo` without consuming RNG; otherwise `lo + rand % (hi - lo)` |
| `random_bool(n)` | `0x000e0cb0` | `(rand % n) == 0`; no zero-divisor guard |
| `random_bool(a, b)` | `0x000e0cd0` | `(rand % b) < a`; no zero-divisor guard |

For ordinary positive arguments, both integer ranges are upper-exclusive.
Unusual negative arguments and zero-divisor behavior are direct implementation
facts, not promoted public API contracts.

The normal success paths are strongly non-yielding: each leaf performs scalar
work and calls only the reviewed RNG core; this PE neither imports nor contains
the exact string `lua_yield`. That is sufficient to justify a disposable
experiment with the dormant return-preserving Lua wrapper. It is not proof that
an installed wrapper or native detour preserves errors, longjmps, timing, or
gameplay outcomes.

## Native RNG and `aiSeed`

The shared core is the linked MSVC CRT per-thread generator, not Park-Miller:

```text
state = state * 0x343fd + 0x269ec3       (32-bit wrap)
result = (state >> 16) & 0x7fff
```

| Boundary | RVA | Static fact |
|---|---:|---|
| RNG core | `0x00387f16` | Reads and updates the per-thread state field at `+0x18` |
| Seed setter | `0x00387f37` | Writes the same state field |
| AI seed-advance helper | `0x000e0bf0` | Draws a new value, retries up to ten times when equal to the old seed, then uses the documented fallback |
| Enemy planning orchestrator | `0x000f6390` | Seeds from the AI object's `+0x80`, selects an action record, advances/stores `aiSeed`, then later reseeds the CRT state |
| `aiSeed` archive/write side | `0x000f6ce0` | Associates the exact `aiSeed` key with object `+0x80` |
| `aiSeed` archive/read side | `0x000f6e10` | Restores the keyed value to object `+0x80`, with a shared-RNG default |

The same core is called by all four Lua bindings and directly by native enemy
decision code. A raw `.text` scan finds 118 `rel32` call encodings to it.
Consequently:

- wrapping `_G.random_int` / `_G.random_bool` records Lua-resolved calls only;
- hooking the four native leaves records calls through those bindings only;
- observing RVA `0x00387f16` records the complete shared stream but needs a
  bounded return-address ID to retain semantic origin.

The old assumption that Lua global wrappers could capture the full enemy RNG
stream is therefore disproven for this build.

## Enemy decision tournament

| Boundary | RVA | Reviewed role |
|---|---:|---|
| Enemy `ScorePositioning` wrapper | `0x000f7870` | Dynamically looks up the named method and extracts an integer |
| Candidate / target loop | `0x000f78f0` | Gets the target vector, consumes it sequentially, applies positioning and target scores, retains equal bests, and breaks ties natively |
| Higher-level record selector | `0x000f7dd0` | Selects a 24-byte candidate record and contains three additional direct RNG-core calls |
| Named integer invoker | `0x000f8770` | Enters an actual-object lookup path whose helper calls `lua_getfield` |
| Target-area wrapper | `0x00229230` | Enters the dynamic target-area implementation used by the candidate loop |
| `GetTargetScore` | `0x00229310` | Applies native modifiers, resolves the actual skill, and dynamically obtains the callback score |
| `GetTargetArea` / `GetSecondTargetArea` | `0x00269cc0` | Selects the applicable callback, copies its vector, and filters invalid negative coordinates |
| SkillEffect cache materializer | `0x00268050` | Gates on cached-target membership, invokes the applicable Lua effect callback, replaces the cache, annotates both vectors, and applies native damage modifiers |
| Selected SkillEffect postprocess seam | `0x00268323` | Runs after both effect/q_effect passes; the hardware campaign samples the selected cache here before its queue commit |

The candidate loop preserves the returned target vector's order. For each
candidate it calls `GetTargetScore`; equal-best targets are stored and selected
with a direct `rand % equal_count` at RVA `0x000f7b62`. A Lua RNG wrapper misses
that choice.

The candidate-score continuation closes the native pre/post-callback
arithmetic. Pawn `+0x8d6` is the archived `bInjured` byte, `+0x8a8` is current
`health`, and `+0x948` is `iCurrentWeapon` / Lua `GetSelectedWeapon`. Ordinary
planning passes candidate mode zero; only `debugai` passes one. After
`ScorePositioning`, a moved, injured pawn at exactly one HP has a nonnegative
result replaced with the mode value, so normal planning clamps it to zero;
negative scores are preserved. Before target-area work and again before each
target score, a non-minus-one selected weapon at or beyond the vector count is
rewritten to zero.

The `GetTargetScore` wrapper binds SkillManager point fields `targetHistory`
at `+0x50/+0x54` and `priorityTarget` at `+0x60/+0x64`. A history match assigns
`-5`; a priority match assigns `+10` and overrides history. The callback is
resolved only for an in-range weapon index or literal index 50. An invalid
index returns the native modifier without a callback. When the modifier is
negative and a positive callback result is no larger than its magnitude, the
wrapper returns one; otherwise it uses signed 32-bit addition. The shipped
meaning of literal 50 is closed by the target-area continuation below.

The target-area continuation resolves the complete native gate before that
callback. Normal mode zero requires `IsActive`, no effective Smoke, no grounded
nonflying Water state, `iBonusShift +0xa64 <= 0`, and either a usable Skill or
`IsMech +0x9e4`; debugai mode one bypasses an ordinary failure. Smoke requires
an attached Board smoke tile and `not IsBusy`, then is suppressed by
`IgnoreSmoke` or `Disable_Immunity`. The exact global registration binds
`TERRAIN_WATER=3`, and that predicate additionally requires `not IsBusy` and
`not IsFlying`.

The usable-skill scan walks vector order, excludes exact IDs `Move` and
`Move_Power`, and accepts any other Skill with `Limited +0x160 == 0` or
remaining uses `+0x158 > 0`. Resolver index 50 is tested before vector bounds
and returns the SkillManager-owned `+0x68` shared pointer constructed with ID
`Skill_Repair`; it is not vector slot 51. Candidate normalization nevertheless
rewrites selected index 50 to zero whenever the vector count is at most 50.
The hash-pinned 152-file Lua census distinguishes 206 visually matching
one-line `SkillList` forms from eight inside block comments: 198 are active,
with arity distribution 26/161/11 for zero/one/two and maximum active literal
arity two. That source maximum is not a universal runtime or modded bound.

The callback-wrapper continuation closes the next native layer. `Board:AddPawn`
passes `Board +0x0c` to the SkillManager context writer, which stores it at
`+0x110` on every vector Skill and the separate repair Skill. That secondary
vtable's slot `+0x14` is a `this -= 0x0c` thunk to the exact `Board:IsValid`
bounds body. The wrapper stores its origin, invokes no Lua callback when that
origin is invalid, move-assigns a fresh empty PointList over the old target
cache, and returns empty.

For a valid origin, `GetSecondTargetArea(origin, second_target)` is selected
only when `TwoClick` is true and both second-target coordinates differ from
literal `-1`; otherwise the wrapper invokes `GetTargetArea(origin)`. After Lua
result conversion, native code replaces the cache and stably erases points
whose x or y is negative. It does not reapply `Board:IsValid` to returned
points, so duplicates, encounter order, and positive out-of-board coordinates
survive. The pure replay starts with that already-materialized ordered
PointList and therefore does not claim the concrete Lua construction itself.

The SkillEffect continuation closes the adjacent cache body without
overclaiming the Lua payload. The selected target must exactly match one point
in the cached target vector. A miss stores `(-1,-1)`, invokes no callback,
clears both cached `SpaceDamage` vectors, resets `SkillEffect.iOwner +0x5c` to
`-1`, and clears the private Skill key. A hit invokes
`GetFinalEffect_Helper([origin, second target, selected target])` only when
`TwoClick` is true and both second-target coordinates differ from literal
`-1`; otherwise it invokes `GetSkillEffect(origin, selected target)`. The
converted callback result move-replaces the complete old cache.

Native annotation then walks `effect` followed by `q_effect`. Empty
`sAnimation +0x38` defaults from dynamic `Explosion`; the private point at
`+0x9c/+0xa0` defaults from the Skill origin only when both coordinates are
`-1`; and private `+0xc0` is always overwritten from the constructor-supplied
Skill source tag at `+0x150`. Native code next writes owner and Skill key, then
postprocesses both vectors. Vek Hormones adds one, two, or three to eligible
positive hostile-on-hostile damage, excluding exact special values 500 and
1000. Boost runs afterward, excludes exact Skill IDs `Move` and `Move_Power`,
adds one to ordinary positive damage, subtracts one only from `-9..-1`, and
sets private byte `+0x31` on every record. Arithmetic wraps as signed 32-bit.

The main body has exactly eight direct native callers, all in reviewed
Board/SkillManager/Skill cache-refresh paths. That census proves this body is
a cache materializer, not that it is the candidate scorer's score-side
`GetSkillEffect` route. The pure replay therefore accepts the concrete Lua
SkillEffect and resolved Board predicate results as inputs; subclass payloads,
selector-entry shared state, and a future enemy phase remain unresolved.

The selected-materialization hardware campaign validates one concrete use of
that cache body. Across three counterbalanced control/dormant/armed triplets,
the selected input-5 path always reaches the postprocess seam with
`FireflyAtk1`, owner and Skill owner 1303, source tag 6, origin `[5,4]`, target
`[4,4]`, no instant record, and one queued one-damage `ExploFirefly1` record at
`[3,4]`. Its private origin/source/boost fields are `[5,4]`, 6, and false. The
same observer then sees the queue commit, and all nine successful outcomes
match semantically. This closes only the selected fixed path; it does not turn
the static parameterized replay into a prospective multi-shape forecast.

The source-keyed ancestry continuation closes that score-side call question.
The accepted tree has 22 raw `GetTargetScore` identifier occurrences: one
commented `Garden_Atk` definition is masked, leaving 20 active definitions and
one active Shaman-to-Totem call. Exact `CreateClass` semantics install
`self.__index=self`; `TotemAtk1 = Skill:new{...}` has no score override, so the
Shaman call resolves to `Skill:GetTargetScore` and dynamically invokes
`TotemAtk1:GetSkillEffect`.

`Skill:GetTargetScore` itself calls `self:GetSkillEffect` once, scores both
instant and queued vectors, rejects an instant score below `-20`, and otherwise
uses the queued score whenever that vector is nonempty. The two Centipede
scorers and Mosquito boss are the other three direct actual-effect callers.
Dung, Scarab boss, Starfish boss, and Blobber score synthetic local effects;
the remaining eleven active definitions score no effect payload. No score body
calls `GetFinalEffect` or its helper.

This proves that score-time Lua effect construction bypasses the native cache
materializer at `0x00268050`; the two paths must not be merged. A complete
body-manifest census of all 186 active `GetSkillEffect` definitions also finds
zero direct calls to `random_int`, `random_bool`, `random_element`, or
`random_removal`. That does not prove every native-bound constructor or Board/
effect helper transitively RNG-free, nor provide future Board queries and
effect payloads before queue commitment.

The next source-keyed artifact closes the arithmetic inside the inherited base
score route without pretending those future inputs are already observable.
Its exact `Skill:ScoreList` replay preserves movement-first handling, the
non-grid-structure branch before Pawn-team scoring, the special untargeted-
Frozen-friendly `ScoreEnemy` case, powered-building scoring, the instant-only
Time Pod veto, and the final positioning override strictly below `-5`.
Notably, a dead or temporary hostile Pawn assigns `score = ScoreNothing`; it
can erase an earlier positive total instead of merely contributing a neutral
term. This Lua-to-Lua route preserves fractional `ScorePositioning` values,
including the melee-distance branch's half-points, before applying that cutoff.

The joined base `Skill:GetTargetScore` replay scores `q_effect` before
`effect`, converts an instant result strictly below `-20` to `-100`, then uses
the instant result only when the queued vector is empty. It consumes explicit
Board/Pawn predicate observations and an explicit `ScorePositioning` result at
the exact call sites. `ScorePositioning` itself, prospective Board state, and
the 19 custom score callbacks remain separate continuations, so this is not a
future enemy-phase forecast and does not replace the settled queue.

The `ScorePositioning` successor closes that remaining global source body from
projected observations. Its exact short-circuit order is Pod, grounded Hole,
targeted danger score, Smoke, new Fire, spawning, generic danger, avoided
dangerous item, grounded Water, custom Pawn score, stock corner/edge, then the
melee/ranged tail. The ACID check is inactive commented source. Custom score
precedes the hard-coded `0`/`7` edges, and the binary team expression selects
`TEAM_ENEMY` only for a player Pawn and `TEAM_PLAYER` for every other team.

Melee scoring checks the four exact direction slots in order, testing a Pawn
of the selected team before a Building, and otherwise returns the half-point-
preserving Lua expression based on the smaller Pawn/Building distance. The
direct Lua `ScoreList` route retains that fraction. The separate native
candidate route enters the pinned named integer invoker and installed
`lua5.1.dll` `lua_tointeger`; its exact body uses x87 `FISTP`. Conversion is
therefore replayable for each of the four x87 rounding modes. The later runtime
campaign resolves the observed mode for this exact Windows build to
nearest-even: every fresh armed process records control word `0x027F` at the
exact conversion boundary. This remains a build/process-scoped observation,
not an assumption about other builds or arbitrary Lua integer calls.

The next native/source join resolves both Pawn helpers. The unique
`GetDangerScore` registration points to a 57-byte body that supplies
`ScoreDanger` to a shared `Get`-prefix dispatcher, producing
`GetScoreDanger`. The unique `GetCustomPositionScore` registration points to a
147-byte body that resolves literal `GetPositionScore` and supplies the
candidate Point. Both paths require a Lua number and reach the pinned
`lua_tointeger` import. Exact `CreateClass(Pawn)` source synthesizes those two
getters from the base fields, while the complete 152-file shipped Lua census
contains only `ScoreDanger = -10` and `PositionScore = 0` and no explicit
getter/field override. The unmodified shipped helper results are therefore
exact and independent of x87 rounding mode.

The following native observation join closes the remaining predicate meanings,
not the future tournament. All 17 named Board/Pawn bindings are exact.
`Board:IsDangerous` reads a native tile flag plus two Point vectors and is not
the bridge's `Board:IsEnvironmentDanger`; `Board:IsDangerousItem` requires item
presence and tests the embedded `SpaceDamage` damage, push, shield, fire,
smoke, spawned-Pawn, ACID, and frozen fields. `Board:IsSpawning` combines its
tile flag and Point vector, while `Board:IsTargeted` scans active Board objects.
Team queries one and six mean exact player and actual team at least six.
Profile-six distance to a matching Pawn reduces to Manhattan distance, and the
Building distance is Manhattan over a cache rebuilt from every terrain-1 tile.

The ordinary bridge directly carries or exactly derives most current values.
It does not directly carry the two dangerous predicates, runtime-exact Ranged
or AvoidingMines mutations, or the Board snapshot at each later candidate
callback. Runtime/mod mutations and that candidate-time snapshot remain
explicit inputs. The callback-time x87 seam is resolved to nearest-even for the
attested Windows build, but the future tournament is still not fabricated.

The exact-build selector continuation resolves the higher-level grammar. The
movement producer retains native `GetReachable` `(x,y)` order through its
in-place filter, appends the current pawn tile, and the record driver consumes
that vector sequentially. Each record stores destination `(x,y)`, target
`(x,y)`, post-wrapper target score, and positioning score as six signed
32-bit integers. A positive best target always consumes caller ID 29, even for
a singleton; no positive best retains target `(-1,-1)` and score zero without a
tie draw.

At record level, positioning below `-10` is rejected. Strictly positive
positioning beats strictly negative positioning regardless of target score;
otherwise comparison is descending target score then positioning score. Ties
retain encounter order. A strict improvement replaces the fallback with the
entire displaced primary group, so a later intermediate record does not turn
that fallback into a recomputed global second-best set. Every nonempty primary
spends caller ID 30, including singletons. A nonempty displaced group then
spends caller ID 31; remainder zero modulo four samples without replacement
through caller ID 33 followed by ID 32. The rare acceptance test requires a
positive target, nonnegative positioning, and destination coordinates other
than `0` or the hardcoded stock maximum `7`.

`replay_enemy_target_tie` therefore starts at the local tie boundary after any
callback/effect-side draws, while `replay_enemy_record_selector` starts after
all ordered 24-byte records exist. Those two parameterized boundaries are
complete; upstream callback materialization and a prospective solver payload
are not.

All named callbacks are looked up on the actual object. Wrapping only the base
`Skill` method can therefore miss subclass overrides. A runtime hook plan must
enumerate exact loaded function identities and publish a coverage manifest.

The second `ScorePositioning` string reference at RVA `0x0016ce68` is not a
second enemy-decision path. Its containing function at RVA `0x0016cdd0` is the
`GetDeployLocScore` deployment scorer.

## Selected action boundary

The higher-level selector returns one 24-byte record. At RVA
`0x000f683c..0x000f684f`, the AI orchestrator copies that record into object
offsets `+0x50..+0x67`. The archive-side names identify:

- `+0x50/+0x54` as `aiDest`;
- `+0x58/+0x5c` as `aiTarget`.

This is the narrowest proven final selected-record boundary and is suitable for
correlation in a disposable trace. Static evidence alone does **not** establish
that this copy is the later Pawn action or animation queue commit. The later
build-keyed hardware-observer campaign supplies that missing dynamic link for
one bounded `Firefly1` scenario: in all three armed runs, one selected record is
followed immediately on the same thread by one queue commit for the same pawn;
`aiDest` equals queue origin, `aiTarget` equals queue target and shot, and
current weapon equals queued skill. The three counterbalanced
control/dormant/armed outcomes are semantically identical, every debug register
and observer resource is restored, and no executable bytes are modified. This
supports `enemy_action_selected` for that shape, not a universal claim about
cancellation, retargeting, multi-weapon enemies, or every Pawn queue path.

## Native path, cost, and ordering boundary

The exact-build path map binds `Board:GetSimpleReachable`,
`Board:GetReachable`, `Board:GetPath`, `Board:IsBlocked`, and
`Pawn:GetPathProf` to their reviewed native entries. It also pins
`PATH_GROUND=0`, `PATH_FLYER=1`, `PATH_MASSIVE=2`, `PATH_PROJECTILE=3`,
`PATH_ROADRUNNER=4`, `PATH_BURROWER=7`, and `PATH_PHASING=9` through their Lua
global registrations.

`Pilot_Hotshot` takes the `PATH_ROADRUNNER` branch. That branch checks terrain
without calling the ordinary occupancy helper, so occupied live pawn tiles can
be search nodes. `GetReachable` nevertheless invokes the Board vtable's
`IsBlocked` slot before returning a destination, and that concrete predicate
rejects occupied pawn spaces. Profile 4 also remains blocked by directional
walls and is distinct from `PATH_FLYER`. This closes Henry Kwan's solver gap;
simulator v401 now traverses but never returns those occupied tiles.

The follow-up cost/order map traces the same build's source/destination-cost
slots, reachability trees, GetPath heap and predecessor map, direction-table
initializer, ordinary occupancy branch, and result reconstruction. Native
`GetReachable` uses only unit-cost admitted edges, expands from direction pairs
`(0,-1),(1,0),(0,1),(-1,0)`, retains an existing predecessor on equal cost,
and returns accepted points in lexicographic `(x,y)` order. `GetPath` uses a
min-heap ordered by `g + 1.01 * Manhattan`, then `x,y`; it accepts a blocked
requested endpoint, retains only strict-g predecessor improvements, and
returns both endpoints for distinct points.

The ordinary low-profile branch compares pawn identifier rather than team, so
any differently identified counted pawn blocks profiles 0/2 while the mover's
own identifier is exempt. `PATH_MASSIVE=2` passes both Water traversal and stop
checks. Simulator v402 fixes the v401 ordinary-movement omission of Massive
and Road Runner Water routes while preserving solver-side Chasm/Lava and ACID
safety policy.

The lifecycle continuation joins the native `Pawn:IsDead` virtual thunk and
direct `Pawn:IsCorpse` binding to the counted-occupancy helper. Mode 1 counts
an entry when `not IsDead()` or `IsCorpse()`. Ordinary traversal and the
concrete Board destination wrapper both use mode 1: a persistent corpse blocks
ordinary transit and every stop, while a retained transient dead non-corpse
does neither. `PATH_ROADRUNNER=4` exits before occupancy, so it may cross a
persistent corpse, but the common destination wrapper still prevents stopping
there. Simulator v403 carries live/static lifecycle identity through the
bridge, model, Rust paths, verification, and projected checkpoints while
leaving general same-effect corpse collision behavior unchanged. The later
corpse-classification continuation closes the common predicate and static
shipped types; removal/lifecycle timing, output vectors, and `AddMove`
scheduling remain unpromoted.

Reverify the artifact with
`scripts/itb_observatory_path_boundaries.py verify` against the exact
executable. Its verifier checks the embedded identity, region/control-window
bytes, API/global bindings, vtable slots, and direct calls; reviewed function
starts and semantic interpretations remain analyst evidence.

Reverify the cost/order continuation with
`scripts/itb_observatory_path_cost_ordering.py verify`; it independently
checks every region hash, instruction-start control window, initialized
direction pair, cost/stop jump table, property string, and the exact 1.01
float constant.

Reverify the lifecycle continuation with
`scripts/itb_observatory_path_occupancy_lifecycle.py verify`; it checks the
exact executable identity, all eight region hashes, all ten instruction-start
control windows, both lifecycle bindings, path-manager slots, mode-1 predicate,
and ordinary/Road Runner transit-versus-stop conclusions.

## DAMAGE_DEATH Pawn/HP boundary

The exact-build map
`data/observatory/native/windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json`
joins the registered integer sentinel to `SpaceDamage.iDamage`, the generic
Pawn receiver, registered status setters, the HP-delta routine, and its
embedded clamped `ValueBar`. It proves numeric value 1000 at record offset
`+0x08`; Shield/Frozen clearing without absorption; Armor subtraction and ACID
doubling; no flying/Massive immunity test in that receiver; and a negative HP
delta capped at minus-current HP. Stock supported Final Cave and Volcano pawns
therefore reach zero HP, matching the existing Rust terminal result.

The verifier also inventories direct calls to `Pawn:Kill` across the reviewed
core, Pawn receiver, and HP routine. The sole core call is the separately
reviewed Building-terrain occupant-removal branch; neither the receiver nor HP
routine directly calls it. The continuation below narrows zero-HP settlement;
Lua `OnKill`, attribution, lifecycle timing, and other platforms stay open.

Reverify it with
`scripts/itb_observatory_damage_death.py verify` against the exact executable,
content root, and committed boundary map. The verifier checks exact source and
executable identity, all region/data hashes, registered field and status
bindings, instruction-start windows, call targets, and the complete reviewed
direct-`Pawn:Kill` edge inventory.

## Zero-HP Board cleanup boundary

The exact-build continuation
`data/observatory/native/windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json`
maps the structural seam after HP zero. After applying the HP delta and further
same-routine feedback logic, the HP routine checks virtual `IsDead` through
vtable slot `+0x10` before returning. A later Board sweep reaches its erase
path only for a candidate that passes cleared state and definition gates,
returns true from virtual `IsDead`, has Pawn byte `+0x964` clear, and returns
false from direct `Pawn:IsCorpse`. Its exact pointer-index helper searches
Board vector `[+0xa0,+0xa4)`, the erase path compacts a found tail, and the
vector end decreases by one pointer. `IsCorpse == true` escapes that path and,
through the predecessor path artifact, remains counted occupancy while
retained.

The exact `.text` image has two instruction-aligned direct calls to the sweep,
but those call sites do not identify which pass follows a particular damage
record. The artifact therefore closes the conditional erase shape without
claiming between-effect or between-action timing.

The same verifier scans all file-backed `.text` bytes for exact virtual-address
operands. `OnKill` has four absolute references in two property-access
functions, `EVENT_ENEMY_KILLED` has one in the global/Pawn binding table, and
the selected owner/death/counter names occur only at the inventoried definition,
accessor, or binding sites. None of the reviewed damage, HP, explicit-Kill, or
cleanup functions directly calls either `OnKill`-reference function. This is
useful negative evidence, not a generic/indirect Lua dispatch or kill-credit
proof.

Reverify it with `scripts/itb_observatory_zero_hp_cleanup.py verify`. Exact
damage-relative sweep timing, Lua callback dispatch, source/team/owner and
counter attribution, death-effect presentation, and non-Windows equivalence
remain open at this structural boundary. The ordinary enemy event and credit
path continues below, and the later corpse-classification map closes static
predicate/type inputs. No Rust change follows from the structural continuation.

## Enemy-death event and credit boundary

The exact-build continuation
`data/observatory/native/windows_build_13725832_31fe35265598_death_event_credit_boundary.json`
joins the queued `SkillEffect.iOwner` field to the ordinary enemy-death event
and credit writers. Luabind maps `iOwner` to `+0x5c`; `Board:AddEffect` copies
the complete 0x7c-byte record, both reviewed copy paths preserve the field, and
the dispatcher installs it as its current owner context. Both shipped
`Env_Attack:ApplyEffect` branches set `iOwner=ENV_EFFECT`, whose exact native
registration is integer `-10`.

For a non-Mech `TEAM_ENEMY` death, the native path records event 2 with
`INT_MAX` payload when `Minor` is false and event 12 when it is true. Event 2
is the exact `EVENT_ENEMY_KILLED` registration. Its generic recorder increments
the pending array, the sole direct publisher copies pending to the readable
array and resets pending, `Game:GetEventCount` reads that array, and
`Mission:BaseUpdate` adds the value to `KilledVek`. The artifact does not claim
whether a death raised in a particular Board/effect pass becomes readable in
that same outer update or the next.

The ordinary credit branch is independent. For non-Minor, XP-eligible victims,
owners 0 through 2 write `xp_<owner>` and `kill_<owner>`; every other owner
writes `env_xp`. The reviewed path also writes `any_kill_<owner>`. Each Pawn
consumer reads and clears only the three buckets for its own ID, adds the
`Extra_XP` bonus, then updates `iKillCount` and Mech `iKills`.
`iMissionDamage` is a separate health-delta accumulator. Environment owner
`-10` therefore cannot create any Mech owner's XP, kill, or any-kill entry,
while the independent non-Minor enemy-killed mission event still fires.

The source-side `OnKill` hypothesis is also narrower now. Across the accepted
305-file scripts tree, all seven occurrences are one empty `Skill` default plus
six localization keys; no matching Lua callback function exists, and each
weapon implements its mechanic inline in `GetSkillEffect`. This does not
exhaust native-only consumers that address a Skill field by offset.

Reverify the chain with
`scripts/itb_observatory_death_event_credit.py verify`. Rust's lethal
environment path already records the same ordinary mission kill and excludes
Minor enemies; the focused Final Cave regression locks that portion. The
event-frame successor below closes exact visibility, and the specialized-death
successor after it closes shipped boss/Minor classification plus the missing
Rust IsMech filter. Achievement/profile tails, `any_kill_-10` consumers, the
complete meaning/writer set for Pawn byte `+0x1175`, native-only `OnKill`
consumers, and non-Windows equivalence remain open.

## Board-death event frame visibility

The exact-build successor
`data/observatory/native/windows_build_13725832_31fe35265598_event_frame_visibility.json`
joins the pending/readable event buffers to the complete active-battle update
chain. The outer main update has one direct event-publisher call, then invokes
`Game` vtable slot `+0x04`. The same outer object constructs that exact Game
type and retains it at the dispatched `+0x18` field. Its vtable targets the
mapped Game update; the active mode-1 branch directly enters battle update.
That routine invokes the present controller at `+0xc204` through vtable slot
`+0x10`. Both normal construction paths store an exact BoardPlayer there, and the
BoardPlayer vtable maps `+0x10` to the primary orchestrator.

The orchestrator calls Board master update first. That body reaches the Board
effect queue, then returns before the orchestrator constructs the exact
`BaseUpdate` name and calls the named Mission invoker. Consequently, a death
recorded during Board/effect processing writes pending state after this outer
update's only publication point. `Mission:BaseUpdate` later in that same update
reads the old readable array and cannot see the death. At the start of the next
ordinary outer update, the sole publisher promotes the accumulated pending
batch before Game/battle/BoardPlayer dispatch, so the later `BaseUpdate` can
read it.

Reverify the chain with
`scripts/itb_observatory_event_frame_visibility.py verify`. “Next ordinary
outer update” assumes the active battle and Mission callback path still run;
it is not a wall-clock promise across pause, teardown, or terminal transition.
Events raised outside Board/effect processing, the cached-controller helper's
concrete return type, terminal teardown delivery, and other depots remain
separate questions. The solver does not model intra-update Lua callback
visibility, so no Rust semantic change or version bump follows.

## Specialized-enemy death boundary

The exact-build successor
`data/observatory/native/windows_build_13725832_31fe35265598_specialized_enemy_death_boundary.json`
joins `Mission_Boss:StartBoss` to the one-argument native Pawn factory, common
constructor, Board-driven shared Pawn update, and sole common death-processor
call. The wrapper supplies selector 2, resolves `GetDefaultTeam`, allocates
0x1328 bytes, invokes the common constructor, installs the common Pawn vtable,
defaults `IsMech` and `Minor` false, and then loads the Lua definition's
`Minor` value into Pawn `+0x10d0`. There is no hidden boss subclass constructor
on this reviewed route.

Once the common death processor is reached, its ordinary event predicate is
exactly non-Mech, team 6, then non-Minor event 2 versus Minor event 12. The
complete reviewed body does not gate that split on Leader, Tier, boss, Psion,
or Pawn type name. The accepted Lua tree has exactly 17 active Minor
definitions and no child derived from one. Its 21 nonempty `BossPawn` values
are literal `TEAM_ENEMY` definitions retaining global `Minor=false`.
Consequently every boss objective and each of `BlobBoss`, `BlobBossMed`, and
`BlobBossSmall` raises ordinary event 2, while the four boss-specific Minor
auxiliaries `BlobB`, `TotemB`, `SlugEgg1`, and `SpiderlingEgg1` raise event 12.

The only three shipped `SetMech()` calls construct tutorial player-team mechs;
the only `SetTeam()` call also selects `TEAM_PLAYER`. Thus the Rust discrepancy
was not vanilla-reachable, but it still contradicted the exact native
predicate. Simulator v407 adds the missing `!is_mech` test before preserving
the Minor and Acid Tank filters, with the pre-v407 corpus archived as
`recordings/failure_db_snapshot_sim_v406.jsonl`. Reverify the complete chain
with `scripts/itb_observatory_specialized_enemy_death.py verify`. Detailed
alternate Mech-death effects, mods, and non-Windows depots remain separate.

## Native corpse-classification boundary

The exact-build successor
`data/observatory/native/windows_build_13725832_31fe35265598_corpse_classification_boundary.json`
joins the prior zero-HP and specialized-death maps to the complete common
`Pawn:IsCorpse` member. It has exactly 27 raw-rel32 direct callers and contains
no subclass-vtable dispatch. Outside internal lifecycle states 2, 3, and 4, a
Mech or a Pawn loaded from `Corpse=true` returns true immediately; the other
path requires mutation 12 to be current or globally available and accepted by
the shared eligibility helper.

Exact definition loading maps `Corpse` to Pawn `+0xf80`, `Leader` to `+0x1318`,
`Minor` to `+0x10d0`, and `DefaultFaction` to `+0x10bc`. The bound
`SetMutation` implementation writes current mutation at `+0x10e8`. Exact
global registration maps mutation value 12 to `LEADER_NECRO`; Teleporter's
source field is separate and is not an `IsCorpse` input. The relevant
eligibility route admits ordinary default-faction team-6 pawns directly, uses
`Psion_Leech` for the alternate Mech/team-4 route, and rejects Minor recipients
plus an already-current Leader.

The accepted 153-file Lua tree defines `Jelly_Necro1` once as a
`Jelly_Health1` child with `LEADER_NECRO`, but has no mission, spawner, factory,
other active reference, or `SetMutation` call that reaches mutation 12. The
same scan finds ten explicit `Corpse=true` definitions and six inheriting
directional Laser/Piston bodies. All 16 effective types already have Python and
Rust static fallback coverage, and the bridge already exports both current
`IsCorpse()` and source-static `Corpse`. Simulator v407 therefore needs no
change.

Reverify the executable, both predecessor maps, exact selected sources and
accepted Lua inventory, region/control windows, data references, call
inventories, and solver binding with
`scripts/itb_observatory_corpse_classification.py verify`. This is a static
classification proof. At this artifact stage, action/frame transitions into
lifecycle states 2/3/4, exact dead-pawn removal timing, and `Mission_Piston`
action/cleanup order remained open. The successor below closes the stock
Mission_Piston scheduler question without generalizing those lifecycle states.
Modded/direct-native mutation paths and other depots are outside scope.

## Native Mission_Piston scheduler boundary

The exact-build successor
`data/observatory/native/windows_build_13725832_31fe35265598_piston_scheduler_boundary.json`
joins the corpse-classification and event-frame maps to the shipped Piston,
mission-base, and environment sources. Native `Board:GetPawns` returns the
Board pawn vector in pointer order. Enemy planning copies that same vector and
stably retains team-6 pawns or pawns with `Neutral` set; execution repeatedly
selects the first still-queued pawn from the same vector. No UID sort or
separate Piston phase exists.

The queued predicate requires a skill manager, valid target coordinates, and a
nonnegative action index. Board activity is checked before every selection, so
an earlier effect settles before the next pawn is chosen. Both explicit
`Pawn:Kill` and the tail of the shared Pawn update clear the target and action
fields before returning. A Piston killed before its slot therefore loses its
push, while `Corpse=true` keeps the dead body as occupancy. The shipped
`Mission_Piston` declares no Environment override and inherits `Env_Null`, whose
`IsEffect` and `ApplyEffect` are both false. Living Piston pushes and queued Vek
therefore interleave exactly in Board-vector order with no environment action
inserted between them.

Simulator v408 preserves that native order in the bridge payload, interleaves
Piston and Vek actions in Rust, cancels dead-Piston pushes without deleting the
corpse, and replaces the old active/corpse blanket veto with a completeness
gate. A known active, corpse-only, or empty Piston state can now be projected;
missing, partial, duplicated, or reordered payloads still fail closed. The
pre-v408 corpus is archived as
`recordings/failure_db_snapshot_sim_v407.jsonl`.

Reverify the executable, predecessor maps, selected sources, native regions,
control windows, calls, pointers, and solver binding with
`scripts/itb_observatory_piston_scheduler.py verify`. Mission setup RNG and
rejected-placement draw order remained open at that artifact stage. The setup
successor below closes the parameterized stock boundary; general non-Piston
lifecycle states 2/3/4, presentation-only timing, mods, and non-Windows depots
remain separate gaps.

## Native Mission_Piston setup boundary

The exact-build successor
`data/observatory/native/windows_build_13725832_31fe35265598_piston_setup_boundary.json`
joins the scheduler and map-choice artifacts to the exact Piston/global/event/
mission/environment/map-helper sources, seven shipped candidate maps, native
zone storage, all placement predicates, Pawn creation, and the complete raw
RNG caller catalog.

The current installation's eligible order is `acid0`, `acid1`, `acid10`,
`acid11`, `acid15`, `acid3`, and `acid4`. Native map loading visits each zone
array in encounter order, appends only the first occurrence of a Point, and
`Board:GetZone` returns order-preserving copies; `extract_table` then indexes
the PointList from one through its size. All seven maps are 8x8 with no embedded
or initial spawn pawns before `StartMission`. Direction registration is exactly
U/R/D/L values 0/1/2/3 with vectors `(0,-1)`, `(1,0)`, `(0,1)`, and `(-1,0)`.

Every loop attempt first consumes `random_int(#zone)` through
`random_removal`. If no direction survives the exact terrain, live-pawn,
validity, and non-edge predicates, the attempt consumes no more RNG. An
accepted source consumes `random_int(#choices)`, clears its source, and evaluates
`PAWN_FACTORY:CreatePawn` before `Board:AddPawn`. The one-argument factory
reaches the common Pawn constructor, whose unconditional call at RVA
`0x0022b78a` consumes a raw MSVC result and stores it at `Pawn+0x924`. Thus a
rejection costs one draw and an acceptance costs three. The random-position
fallback inside `AddPawn` contains RNG calls at RVAs `0x00172e16` and
`0x00172e70`, but the exact guard reaches it only for an invalid supplied Point;
every Piston zone source is valid, so neither call participates. The reached
skill-list wrapper at `0x00242c50` is likewise distinct from the neighboring
two-draw AnimTracker constructor at `0x00242cb0`.

`replay_piston_start_mission` now reproduces the ordered attempts, dynamic
occupancy, forward-zone removal, placements, constructor results, and outgoing
observable MSVC state from a selected map plus the observable state immediately
before the first zone-removal draw. Reverify the full exact-installation join
with `scripts/itb_observatory_piston_setup.py verify`, or run a parameterized
case with its `replay --map-name ... --rng-state ...` command.

The one-entry `Mission:GetMapTag` call advances once, and each native map retry
advances once against the seven-entry pool. A concrete future placement still
requires the incoming shared CRT state, used-map registry/retry count, and
selected map, none of which is exposed in ordinary solver state. Consequently
the settled bridge board remains authoritative and simulator v408 does not
change. Concrete runtime UIDs/constructor-field values, mods, other depots, and
non-Windows equivalence remain outside scope.

## Reproducible analysis workflow

The reviewed pass used Capstone 5.0.7 plus Ghidra 12.1.3 with JDK 21. The Ghidra
project was stored outside the repository under a directory keyed by the full
executable hash. Only function extents, references, calls, and hashes were
exported; temporary decompiler output stayed outside the repository.

`scripts/ghidra/ExportItbBoundaryFacts.java` is a reusable headless exporter.
It accepts an output path followed by labeled addresses and emits deterministic
TSV metadata, function extents/hashes, direct calls, and references. The TSV is
an analyst input, not the published evidence: normalize reviewed conclusions
into the JSON artifact and run the independent Python verifier before commit.

Do not use a Ghidra project, address, function hash, or conclusion with another
platform or executable hash.

## Community evidence

Community work remains useful for feasibility and independent probes:

- The Mod Loader README at pinned commit
  [`cba102c7`](https://github.com/itb-community/ITB-ModLoader/blob/cba102c7f41ffec3ca55cc4b7fa964dab51d3a44/README.md)
  documents a Windows-only loader boundary.
- The attributed historical proxy at pinned commit
  [`de060823`](https://github.com/AUTOMATIC1111/IntoTheBreachLua/blob/de0608234f8920379e968ba6efb41e85b0704b50/lua-hooks.cc)
  demonstrates Lua API forwarding hooks, but does not prove equivalence or
  safety for current binaries.
- Community
  [`memedit`](https://github.com/itb-community/memedit/tree/8f809a0d69d4652e041a545f58c33a8927472d39)
  and its
  [`Board:GetAttackOrder`](https://github.com/itb-community/memedit/blob/8f809a0d69d4652e041a545f58c33a8927472d39/functions/board.lua)
  accessor provide useful phase/orchestration probes. Its version-string
  calibration must be strengthened to the full Observatory identity.
- KnightMiner's historical
  [public-function inventory](https://gist.github.com/KnightMiner/2f308a3747461748d6a2186d823e3424)
  remains lead generation, not negative evidence for omitted names.

The inventoried `lua5.1.dll` is 419,840 bytes with SHA-256
`0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14`.
At the pinned Mod Loader revision this identity corresponds to the preserved
original DLL, not its smaller proxy. The completed offline pass did not install
a proxy. Subsequent owner-track experiments used the ordinary Mod Loader and a
separate one-purpose seed-control DLL; they did not replace `lua5.1.dll`.

## Remaining proof

The broad static boundary search is no longer the blocker. The reversible-owner
track is accepted for build-keyed work, so a disposable installation is optional
unless the desired claim is pristine-depot neutrality. Dynamic work now remains:

1. **Completed for bounded observation:** the atomic RNG-core series produced
   two complete, single-threaded checkpoints (1,481 and 1,501 records) with no
   unknown callers or integrity errors and exact trusted-byte restoration.
   Both start with seeded result `24356`. The observer is not promoted as
   whole-game neutral because control/exact outcomes differ at the next spawn
   coordinate.
2. **Completed for the normal `Spawner:NextPawn` path:** three source-verified,
   cleanly restored spans each enclose exactly three caller-21 native draws.
   Their source order is weak-class choice, available-pawn choice, then upgrade
   choice. Three later replay captures recover the exact observable pre-call
   state class, retain the exact runtime available-array order, and reproduce
   every selected pawn. The optional boss `random_bool` branch did not execute.
   Ordinary solver input still lacks the capsule before the call, and coordinate
   selection occurs outside this span.
3. **Completed for the standard spawn-coordinate path:** three
   control/dormant/armed hardware-observer triplets capture the same ordered
   five candidates and prove `selected = candidates[raw_rng % 5]`. Three later
   combined captures join the selector event to caller ID 60 in the complete
   RNG-core stream at ordinals 1495, 1475, and 1450. Every varying upstream
   caller is classified by the static overlay or the already-reviewed caller-21
   Lua leaf; classified count deltas `[0,-20,-45]` exactly match the ordinal
   deltas. Presentation functions account for 1271, 1250, and 1225 draws, so a
   fixed seed plus ordinary save state is not a stable prediction boundary.
   Scheduler and fallback selector paths remain unexercised at runtime. Their
   offline semantics are now resolved: caller 59 is emergency placement after
   the ordinary vector empties, while caller 66 samples predicate-check order
   without replacement and delegates the final coordinate to caller 60.
4. **Completed for natural invocation/restoration:** five callback pairs cover
   all exact defining slots for `ScorePositioning`, `GetTargetArea`,
   `GetTargetScore`, and `GetSkillEffect`. They record 622 attempts and 620
   bounded events with no adapter or restoration error. Only the three
   non-`GetSkillEffect` pairs match whole-game outcomes; two counterbalanced
   `GetSkillEffect` pairs repeat a spawn-coordinate-only mismatch.
   **Completed for a neutral synthetic `GetSkillEffect` shape:** three fresh-
   process pairs on the fixed no-spawn Firefly1 mission capture the same 33
   calls with matching outcomes, zero drops/errors/conflicts, and full slot
   restoration. Calls 0–31 are the source-proven score-side materializations;
   call 32 repeats the selected raw effect and matches the settled queue impact.
5. **Completed for a bounded `Firefly1` queue path:** three counterbalanced
   triplets correlate one final selected record directly to one immediate queue
   commit on the same thread, with exact destination, target/shot, and
   weapon/skill agreement. Wider pawn types, multi-weapon selection,
   cancellation, and retarget paths remain untested.
   **Completed offline for the preceding record selector:** the exact 24-byte
   field layout, movement-vector consumption order, positive-best target draw,
   positioning/score comparator, displaced-primary fallback, 1-in-4 gate, and
   without-replacement sampling are replayable from ordered post-callback
   records plus the selector-entry observable CRT state. Complete callback
   materialization and that prospective state/payload remain runtime inputs.
   **Completed offline for native candidate-score adjustments:** ordinary and
   debug route modes, the injured one-HP positioning clamp, selected-weapon
   normalization, history/priority target modifiers, callback resolver branch,
   positive-score floor, and signed addition are replayable from explicit
   callback and pawn/skill inputs.
   **Completed offline for `ScorePositioning` observations:** all 17 named
   Board/Pawn bindings and their native meanings are exact, including the two-
   vector dangerous predicate, eight-field dangerous-item test, spawn sources,
   team matching, and Manhattan Pawn/Building distances. The current carrier
   matrix is explicit; direct dangerous carriers, live definition mutations,
   and the candidate-time Board snapshot remain unavailable inputs rather than
   unknown native semantics.
   **Completed at runtime for native integer rounding:** three fresh armed
   processes record x87 control word `0x027F` immediately before the exact
   `ScorePositioning` `FISTP`, while all six control comparisons match and every
   observer restores completely. The offline replay therefore selects
   nearest-even for this exact build; Rust still consumes the settled queue and
   needs no simulator-version change.
   **Completed offline for the native target-area gate:** the active/smoke/
   Water/bonus-shift/usable-skill/IsMech predicate and literal-50
   `Skill_Repair` resolver are replayable from explicit inputs.
   **Completed offline for the target-area callback wrapper:** Board validity,
   invalid-origin cache clearing, `TwoClick` callback selection, cache
   replacement, stable negative-coordinate filtering, and return copying are
   replayable from an already-materialized callback PointList. Concrete Lua
   target-point construction and the complete prospective payload remain
   outside this boundary.
   **Completed at runtime for one concrete callback payload:** separate matched
   campaigns bind the complete Firefly1 target-area, raw target-score, and raw
   SkillEffect sequences to the native eight-record tournament. The final
   effect repeat and settled action are same-process; cross-family/native joins
   remain deterministic cross-campaign correlations.
   **Completed at runtime for one selected native materialization:** three
   counterbalanced triplets bind input 5 through the exact postprocess seam to
   one queued `ExploFirefly1` damage record at `[3,4]` and the settled attack.
   All nine outcomes match, every observer restores completely, and two failed
   attempts are preserved only as rejected diagnostics. Other shapes and
   prospective delivery remain open.
6. **Completed offline for native path costs, ordering, and corpse occupancy:** the exact
   API/profile/vtable map proves profile-4 traversal through live occupants plus
   separate occupied-stop rejection. The follow-up map resolves unit
   reachability costs, `(x,y)` result order, weighted GetPath priority and
   endpoint reconstruction, identity-not-team occupancy, and Massive Water. A
   third map proves mode-1 live-or-persistent-corpse occupancy and Road Runner's
   corpse transit/no-stop split.
   Simulator v401 implements Road Runner occupancy; v402 implements the proven
   Water correction; v403 implements corpse lifecycle pathing. The later
   classification map proves one common `IsCorpse` body, exact field inputs,
   dormant mutation-12 reachability, and all 16 shipped corpse types; Rust
   already conforms at v407. Removal/lifecycle timing, matched vectors, and
   `AddMove` execution remain mismatch-driven.
7. **Completed offline for the Final surface-to-cave startup boundary:** the
   initial seven-region map proves the ordinary `IsEndBlocked` veto,
   `IsNextPhase` before `MissionEnd`, and the later `IsNextPhase`-guarded
   `GAME.CreateNextPhase` dispatch. The settlement follow-up resolves its two
   conservative gaps: current `GetTurnLimit` equality with an active Board in
   BoardPlayer state 2 returns ready before `IsEndBlocked`, and a Final
   `MissionEnd` `Board:AddEffect` remains Board activity until the effect vector
   and comprehensive activity gate clear. Exact shipped Lua selects
   `Mission_Final_Cave` and replaces the current mission slot once that branch
   is reached. The startup exact-build map continues through native
   map selection/loading and `BaseStart`, inventories all nine `final_cave`
   maps and their startup zones, and pins the shipped Lua call skeleton from
   the one-entry map tag through lava-path, bomb/Mech, dropper, boss,
   difficulty, and ordinary spawn work. A second follow-up proves shipped
   `RandomMap` filtering, the current unsorted Win32 registration order, the
   absence of an Advanced Edition filter, the empty cave veto set, ordinary
   first-transition used-map noncollision, and two exact pre-environment RNG
   draws: `random_int(1)` advances and returns zero, then `random_int(9)` maps
   its remainder to the nine ordered candidates. A third continuation resolves
   the countdown outcome: state 2 performs nonforced classification, exact
   current-limit readiness writes outcome code 1 without a bomb, objective, or
   `IsEndBlocked` recheck, and only forced state 0 can write code 3 when the
   exact registered `Board:GetPawnCount(TEAM_MECH)` result is zero. Missing-bomb
   source handling therefore delays the reached boundary by replacing the bomb
   and adding two turns rather than directly selecting failure. The campaign
   continuation maps code 3 to result 2 and other committed outcomes to the
   result-1 victory/save/profile/final-presentation route. A fourth continuation
   closes the broad replacement-materialization path: the Board effect update
   precedes `BaseUpdate`; `AddDropper` immediately snapshots the complete
   `SpaceDamage`; `AddEffect` queues it for a later eligible Board update; kind
   4 constructs `PylonAnimation`; and landing applies the preserved
   `sPawn="BigBomb"` record through the pawn factory and exact `Board:AddPawn`
   body when native blocker admission accepts the selected point. The later
   drop-resolution continuation pins the preceding occupant-kill and blocker
   recheck, including the possible permanent-block abort. A fifth continuation
   closes semantic repeat cadence: the secondary-`this` dispatcher appends the Pylon to primary
   Board's active-animation vector, `IsBusy` sees it as activity reason 8 while
   its fall field is negative, and the landing update synchronously impacts
   before that busy predicate can clear. A duplicate replacement cannot be
   queued before impact, and another `+2` cycle requires a later bomb loss plus
   a new idle callback. A sixth continuation closes the startup's logical
   spawn-admission seam: exact native registration distinguishes explicit and
   implicit `SpawnPawn`; the implicit enemy path synchronously calls the
   standard coordinate selector and commits its result through `SetSpace`;
   `BlockSpawn` writes are synchronous; and the only Board update in that
   orchestrator pass precedes phase transition. The boss and ordinary enemy
   identities/spaces therefore commit before queued Mech scripts and
   rock/pylon/bomb droppers can dispatch. A seventh continuation closes the
   ordinary spawn-block lifetime seam: exact registration binds none/temp/perm
   to 0/1/2; both temporary and permanent values reject native spawn
   candidates; `ClearBlockSpawns` changes only temporary value 1 to zero; and
   only player-turn mode 1 invokes that cleanup, before player-turn UI.
   Stage-start phase 1 and end-turn mode 6 skip it, so cave mountain marks
   constrain startup selection and survive startup settlement before clearing
   at the first player turn, while pylon marks survive ordinary turn cleanup.
   Full Board reset zeros the 8x8 map, bounding permanent to the Board rather
   than claiming immortal storage. The incoming CRT state, concrete later
   identities and coordinates, visual animation interleave,
   callback-time replacement candidate set, selected coordinate, UID,
   wall-clock presentation duration, live campaign-settlement timing, and
   non-Windows equivalence remain open; no speculative Rust forecast follows.
8. **Completed offline for the generic Pawn `DAMAGE_DEATH` HP boundary:** the
   exact Lua registration publishes integer 1000, and `SpaceDamage.iDamage`
   is bound at record offset `+0x08`. The core and Pawn receiver preserve that
   sentinel through Shield and Frozen while calling their normal clear
   setters, then apply ordinary Armor subtraction and ACID doubling before
   handing a negative delta to the Pawn's
   clamped `ValueBar`. The receiver has no flying or Massive immunity test, so
   stock supported Final Cave and Volcano pawns reach zero HP. The reviewed
   core does contain one direct `Pawn:Kill` edge, but it is the separately
   mapped Building-terrain occupant-removal branch; neither the numeric Pawn
   receiver nor HP-delta routine calls it. The Rust terminal outcome is already
   equivalent. A build-keyed continuation now proves the later same-HP-routine
   virtual `IsDead` classification and conditional Board-vector erase for a
   dead non-corpse passing all additional native gates. It also proves that
   corpses skip that erase path. A second build-keyed continuation now proves
   the ordinary environment-owned event and credit chain: queued
   `SkillEffect.iOwner` reaches the dispatcher, `ENV_EFFECT` is `-10`, non-Minor
   enemy death raises exact `EVENT_ENEMY_KILLED=2`, Minor raises event 12, and
   environment credit bypasses all Mech-ID XP/kill/any-kill buckets while the
   mission event remains independent. The accepted shipped Lua tree has no
   `OnKill` callback definition; its seven occurrences are one empty default
   plus six localization keys for inline `GetSkillEffect` mechanics. A third
   build-keyed continuation closes event-frame visibility, and a fourth closes
   the shipped specialized class/team outcomes while simulator v407 restores
   the native non-Mech predicate. A fifth continuation closes the one common
   `IsCorpse` implementation, exact fields, dormant Necro mutation fallback,
   and every effective shipped corpse definition; bridge/Python/Rust already
   conform at v407. Exact damage-relative lifecycle/sweep timing, native-only
   Skill field-offset consumers, achievement/profile tails, death presentation,
   and non-Windows equivalence remain open.
9. Add a complete runtime candidate record only if a solver mismatch needs
   more than the observed Lua callback streams, exact native score adjustments,
   and reviewed candidate/selector RNG grammar.
10. **Completed for every sealed live series through the selected Firefly
   materialization campaign:** the associated cleanup receipts close every pending save/install
   field. The current post-cleanup inventory matches 689/689 prior content
   entries, the campaign's 32-file save tree is byte-exact, the baseline Mod
   Loader hash is restored, and no active Observatory file remains. Repeat this
   gate after every future live series.

The exact isolation gate, helper constraints, counterbalanced experiment order,
abort rules, and cleanup proof are in `docs/observatory_capture_campaign.md`.
The repository validates matched-trial receipts, bounded native diagnostic
checkpoints, runtime callback manifests, spawn RNG spans, and selected-record
queue correlations. Runtime pair 004 remains explicitly rejected evidence:
different fresh-process RNG probes disproved the old unseeded method. Seeded
pairs 007 through 012 then matched all six direct wrapper results and restored
every target, while four of six whole-game outcomes still differed only in the
spawn coordinate. The correct conclusion is return preservation without a
whole-game neutrality claim, not a simulator rule for spawn selection. The
later atomic native campaign and natural callback campaign are sealed in
`windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260822_natural_callback_campaign_receipt.json`.
Their restoration is closed by
`windows_build_13725832_owner_local_modified_20260822_callback_native_campaign_cleanup_receipt.json`.
The later spawn and selected-action evidence is sealed in
`windows_build_13725832_owner_local_modified_20260822_spawn_span_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260822_selected_queue_receipt.json`;
their restoration is closed by
`windows_build_13725832_owner_local_modified_20260822_native_boundaries_cleanup_receipt.json`.
The coordinate candidate/modulo evidence and same-process RNG attribution are
sealed in
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_receipt.json`;
their restoration is closed by
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_cleanup_receipt.json`.
The bounded Firefly tournament, target-area, target-score, raw SkillEffect, and
selected native materialization evidence is sealed in the corresponding
`windows_build_13725832_owner_local_modified_20260824_enemy_*_receipt.json`
files under `data/observatory/captures/`; each campaign has a matching cleanup
receipt that closes its pending restore fields.
