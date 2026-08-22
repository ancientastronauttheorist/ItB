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
- the final selected 24-byte AI decision-record copy.

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
A later coordinate hardware observer resolves the standard selector's ordered
candidates, direct shared-RNG caller, and modulo rule. Three same-process
coordinate/RNG captures show that the selector ordinal is not stable under a
restored save plus fixed seed because particle, pilot-portrait, `UnitAcid`,
environment-XP, and Lua draws share the upstream stream. Whole-game native-RNG
observer neutrality, prospective selector-state delivery or complete upstream
replay, runtime inputs for the special coordinate paths, broader
selected-action paths, and the complete native candidate tournament remain
unresolved. The scheduler/fallback *control flow* is no longer unknown: exact
offline review identifies caller 59 as the logged emergency modulo selector
and caller 66 as without-replacement predicate ordering before a separate
ordinary selector call. A disposable installation is optional for those
owner-build questions and required only for a pristine stock-depot claim.

The durable artifacts are:

- `data/observatory/native/windows_build_13725832_31fe35265598_pe_anchors.json`
  for exact strings, conservative initial references, imports, and PE identity;
- `data/observatory/native/windows_build_13725832_31fe35265598_pe_boundaries.json`
  for reviewed region hashes, mechanically decoded calls, classified findings,
  hook scope, and remaining runtime questions;
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
| `GetSkillEffect` containing function | `0x00268050` | Dynamically obtains and copies the returned effect container |

The candidate loop preserves the returned target vector's order. For each
candidate it calls `GetTargetScore`; equal-best targets are stored and selected
with a direct `rand % equal_count` at RVA `0x000f7b62`. A Lua RNG wrapper misses
that choice.

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
5. **Completed for a bounded `Firefly1` queue path:** three counterbalanced
   triplets correlate one final selected record directly to one immediate queue
   commit on the same thread, with exact destination, target/shot, and
   weapon/skill agreement. Wider pawn types, multi-weapon selection,
   cancellation, and retarget paths remain untested.
6. Add native candidate records only if a solver mismatch needs more than the
   observed Lua `GetTargetScore` and `ScorePositioning` streams plus reviewed
   candidate-loop RNG caller IDs.
7. **Completed for all live series:** the callback/native, native-boundaries,
   spawn-replay, and spawn-coordinate cleanup receipts close all seven
   immutable campaign receipts' pending save/install fields. Each
   accepted/post-cleanup comparison matches 689/689, the 33-file save tree is
   byte-exact, the baseline Mod Loader hash is restored, and no active
   Observatory file remains. Repeat this gate after every future live series.

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
